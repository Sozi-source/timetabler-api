"""
timetable/models.py
===================
Industry-standard timetabling system.

Design principles
-----------------
* FLAT over deep — fewer models, clearer foreign keys, no hidden syncs.
* One source of truth — CurriculumUnit owns what units exist per programme-stage.
  ScheduledUnit owns what is on the timetable. No IntakeUnit / Stage sync dance.
* Template-first — the timetable is a weekly recurring template (one row per
  programme × unit × slot). Physical week expansion is done in the view/export
  layer, never stored.
* Constraint-driven — hard/soft constraints are data, not code paths.
* Enrolment-based progression — CohortEnrolment is the authoritative record of
  which programme term a cohort studies in a given college semester. Cohort.current_term
  is a cached convenience field kept in sync by signals.
* Venue & trainer availability — first-class models, not JSON blobs.
* Works for any institution — no assumptions about semester count, year length,
  or curriculum shape.

Model map
---------
Institution          — the top-level tenant (multi-institution ready)
Department           — faculty/school/department
Programme            — any qualification with a curriculum
CurriculumUnit       — a unit at a specific position in a programme's curriculum
CurriculumUnitTrainer — through model linking units to qualified trainers
Cohort               — a group of students doing a programme (intake)
CohortEnrolment      — authoritative record: which programme term a cohort
                       studies in a given college semester
Trainer              — lecturer/instructor/facilitator
Room                 — any schedulable space (classroom, lab, online)
Period               — a named time-slot (e.g. "Period 1 08:00-10:00")
Term                 — an academic term/semester
Constraint           — scheduling rule (hard or soft) for a unit/trainer/room
ScheduledUnit        — one row in the master timetable template
ProgressRecord       — cohort's completion status per curriculum unit
TrainerAvailability  — days/periods a trainer is available each term
Conflict             — unresolved clash found during generation
AuditLog             — immutable change trail
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Mixins
# ─────────────────────────────────────────────────────────────────────────────

class TimeStampedModel(models.Model):
    """Abstract base — UUID pk, created/updated timestamps, soft-delete."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True


# ─────────────────────────────────────────────────────────────────────────────
# Institution (multi-tenancy ready — leave as single row if not needed)
# ─────────────────────────────────────────────────────────────────────────────

class Institution(TimeStampedModel):
    name               = models.CharField(max_length=200, unique=True)
    short_name         = models.CharField(max_length=50)
    country            = models.CharField(max_length=100, blank=True)
    timezone           = models.CharField(max_length=60, default="Africa/Nairobi")
    days_of_week       = models.JSONField(
        default=list,
        help_text='Ordered list e.g. ["MON","TUE","WED","THU","FRI"]',
    )
    allow_back_to_back = models.BooleanField(
        default=True,
        help_text="Whether consecutive periods for the same trainer are allowed",
    )
    max_periods_per_day = models.PositiveSmallIntegerField(default=4)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


# ─────────────────────────────────────────────────────────────────────────────
# Department
# ─────────────────────────────────────────────────────────────────────────────

class Department(TimeStampedModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="departments"
    )
    name      = models.CharField(max_length=200)
    code      = models.CharField(max_length=20)
    hod       = models.CharField(max_length=200, blank=True)
    email     = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering        = ["name"]
        unique_together = [("institution", "code")]

    def __str__(self):
        return f"{self.code} — {self.name}"


# ─────────────────────────────────────────────────────────────────────────────
# Programme
# ─────────────────────────────────────────────────────────────────────────────

class Programme(TimeStampedModel):
    LEVEL_CHOICES = [
        ("CERT",    "Certificate"),
        ("DIP",     "Diploma"),
        ("HDIP",    "Higher Diploma"),
        ("DEG",     "Degree"),
        ("PG_DIP",  "Postgraduate Diploma"),
        ("MASTERS", "Masters"),
        ("PHD",     "PhD"),
        ("OTHER",   "Other"),
    ]

    department    = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="programmes"
    )
    name          = models.CharField(max_length=200)
    code          = models.CharField(max_length=30, unique=True)
    level         = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    has_attachment     = models.BooleanField(default=False)
    attachment_term    = models.PositiveSmallIntegerField(
    null=True, blank=True,
    help_text="Which term number is the attachment/industrial placement",
)
    total_terms   = models.PositiveSmallIntegerField(
        default=4,
        help_text="Total number of teaching terms in the programme",
    )
    sharing_group = models.CharField(
        max_length=60, blank=True, db_index=True,
        help_text="Set the same value on programmes that share units.",
    )
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"[{self.code}] {self.name}"

    @property
    def sharing_partners(self):
        if not self.sharing_group:
            return Programme.objects.none()
        return Programme.objects.filter(
            sharing_group=self.sharing_group, is_active=True
        ).exclude(pk=self.pk)


# ─────────────────────────────────────────────────────────────────────────────
# CurriculumUnit
# ─────────────────────────────────────────────────────────────────────────────

class CurriculumUnit(TimeStampedModel):
    """
    A unit at a specific position in a programme's curriculum.
    term_number — which term it belongs to (1-based).
    position    — order within that term (for display sorting).
    """
    UNIT_TYPE_CHOICES = [
        ("CORE",      "Core"),
        ("ELECTIVE",  "Elective"),
        ("PRACTICAL", "Practical"),
        ("PROJECT",   "Project"),
    ]

    programme          = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="curriculum_units"
    )
    term_number        = models.PositiveSmallIntegerField(
        help_text="Which term (1 = first term of programme)",
    )
    position           = models.PositiveSmallIntegerField(default=1)
    code               = models.CharField(max_length=30)
    name               = models.CharField(max_length=200)
    unit_type          = models.CharField(
        max_length=10, choices=UNIT_TYPE_CHOICES, default="CORE"
    )
    credit_hours       = models.PositiveSmallIntegerField(default=3)
    periods_per_week   = models.PositiveSmallIntegerField(
        default=1,
        help_text="1 = single period, 2 = double period (consecutive)",
    )
    qualified_trainers = models.ManyToManyField(
        "Trainer",
        blank=True,
        related_name="qualified_units",
        through="CurriculumUnitTrainer",
    )
    is_outsourced      = models.BooleanField(
        default=False,
        help_text="Unit is taught by an external/outsourced trainer",
    )
    is_active          = models.BooleanField(default=True)
    notes              = models.TextField(blank=True)

    class Meta:
        ordering        = ["programme", "term_number", "position"]
        unique_together = [("programme", "code")]
        indexes         = [
            models.Index(fields=["programme", "term_number"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.programme.code} T{self.term_number} — {self.code} {self.name}"


# ─────────────────────────────────────────────────────────────────────────────
# CurriculumUnitTrainer  (through model for qualified_trainers)
# ─────────────────────────────────────────────────────────────────────────────

class CurriculumUnitTrainer(TimeStampedModel):
    TRAINER_TYPE_CHOICES = [
        ("INTERNAL",   "Internal"),
        ("OUTSOURCED", "Outsourced"),
    ]

    curriculum_unit = models.ForeignKey(
        CurriculumUnit, on_delete=models.CASCADE, related_name="unit_trainers"
    )
    trainer = models.ForeignKey(
        "Trainer", on_delete=models.CASCADE, related_name="unit_assignments"
    )
    trainer_type = models.CharField(
        max_length=10, choices=TRAINER_TYPE_CHOICES, default="INTERNAL"
    )
    label = models.CharField(
        max_length=100, blank=True,
        help_text="Optional custom label e.g. 'HOD Physics dept'",
    )

    class Meta:
        unique_together = [("curriculum_unit", "trainer")]
        ordering        = ["trainer_type", "trainer__last_name"]

    def __str__(self):
        return (
            f"{self.curriculum_unit.code} - "
            f"{self.trainer.short_name} ({self.trainer_type})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cohort
# ─────────────────────────────────────────────────────────────────────────────

class Cohort(TimeStampedModel):
    """
    A group of students admitted to a programme at a specific time.

    current_term is a CACHED field — it reflects the programme_term from the
    cohort's latest ACTIVE CohortEnrolment. It is kept in sync automatically
    via post_save / post_delete signals on CohortEnrolment.

    Do NOT set current_term directly in application code; create or update
    CohortEnrolment records instead. The only exception is the backfill
    management command and the legacy advance_term() helper (kept for
    scheduler compatibility).
    """
    programme     = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="cohorts"
    )
    name          = models.CharField(max_length=100)
    start_year    = models.PositiveSmallIntegerField()
    start_month   = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    # Cached from latest active CohortEnrolment — do not set directly.
    current_term  = models.PositiveSmallIntegerField(
        default=1,
        help_text="Cached from latest active enrolment. Do not edit directly.",
    )
    student_count = models.PositiveIntegerField(default=0)
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering        = ["-start_year", "-start_month", "programme"]
        unique_together = [("programme", "start_year", "start_month")]
        indexes         = [
            models.Index(fields=["programme", "is_active"]),
            models.Index(fields=["current_term"]),
        ]

    def __str__(self):
        return f"{self.programme.code} — {self.name}"

    # ── Enrolment helpers ─────────────────────────────────────────────────────

    def active_enrolment(self, college_term=None):
        """
        Return the ACTIVE CohortEnrolment for the given college term,
        or the most recent ACTIVE enrolment if no term is given.
        """
        qs = self.enrolments.filter(status=CohortEnrolment.ACTIVE)
        if college_term:
            return qs.filter(college_term=college_term).first()
        return qs.order_by("-college_term__start_date").first()

    def enrolment_for_term(self, college_term):
        """Return the enrolment (any status) for a specific college term."""
        return self.enrolments.filter(college_term=college_term).first()

    def sync_current_term_cache(self) -> bool:
        """
        Update the cached current_term from the latest active enrolment.
        Called automatically by post_save / post_delete signals on CohortEnrolment.
        Returns True if the value changed and was saved.
        """
        enrolment = self.active_enrolment()
        new_val   = enrolment.programme_term if enrolment else 1
        if self.current_term != new_val:
            self.current_term = new_val
            self.save(update_fields=["current_term", "updated_at"])
            return True
        return False

    # ── Legacy / scheduler helpers ────────────────────────────────────────────

    def current_units(self):
        """Units the cohort is studying this term (uses cached current_term)."""
        return CurriculumUnit.objects.filter(
            programme=self.programme,
            term_number=self.current_term,
            is_active=True,
        )

    def completed_units(self):
        completed_ids = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.COMPLETED
        ).values_list("curriculum_unit_id", flat=True)
        return CurriculumUnit.objects.filter(id__in=completed_ids)

    def remaining_units(self):
        completed_ids = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.COMPLETED
        ).values_list("curriculum_unit_id", flat=True)
        return CurriculumUnit.objects.filter(
            programme=self.programme,
            term_number__gt=self.current_term,
            is_active=True,
        ).exclude(id__in=completed_ids)

    def advance_term(self, by: int = 1) -> None:
        """
        Legacy helper — still works but the preferred approach is to let
        AdvanceAllCohortsView create new CohortEnrolment records, which
        will update current_term via signal automatically.
        """
        max_term          = self.programme.total_terms
        self.current_term = min(self.current_term + by, max_term)
        self.save(update_fields=["current_term", "updated_at"])

    # ── Calendar-derived helpers (for display / CollegeCalendarView) ──────────

    
    @property
    def computed_current_term(self) -> int:
        today = date.today()
        start = date(self.start_year, self.start_month, 1)
        if today < start:
            return 1
        # Each college semester = 1 term (4 months)
        cohort_sem = (
            1 if self.start_month <= 4 else
            2 if self.start_month <= 8 else 3
        )
        cohort_idx  = self.start_year * 3 + (cohort_sem - 1)
        today_year, today_sem = CollegeCalendar.semester_for_date(today)
        today_idx   = today_year * 3 + (today_sem - 1)
        elapsed     = today_idx - cohort_idx  # semesters elapsed
        term        = elapsed + 1
        return max(1, min(term, self.programme.total_terms))

    @property
    def term_is_synced(self) -> bool:
        """True if current_term matches the computed calendar value."""
        return self.current_term == self.computed_current_term

    @property
    def progress_summary(self) -> dict:
        total = CurriculumUnit.objects.filter(
            programme=self.programme, is_active=True
        ).count()
        completed = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.COMPLETED
        ).count()
        in_progress = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.IN_PROGRESS
        ).count()
        return {
            "total":       total,
            "completed":   completed,
            "in_progress": in_progress,
            "remaining":   total - completed - in_progress,
            "percentage":  round(completed / total * 100, 1) if total else 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CohortEnrolment  — authoritative record of term progression
# ─────────────────────────────────────────────────────────────────────────────

class CohortEnrolment(TimeStampedModel):
    """
    One row per cohort per college semester.

    programme_term  — which term of their programme they study THIS semester.
                      e.g. CND JAN 26 is in programme_term=2 during Sem 2 2026.

    status          — lifecycle state for this enrolment period:
      ACTIVE      — cohort is studying this semester (normal)
      DEFERRED    — cohort has paused for this semester only
      COMPLETED   — cohort finished this programme term this semester
      WITHDRAWN   — cohort left the programme

    Deferral is modelled here, not on the Cohort. A deferred cohort simply
    has no ACTIVE enrolment for that semester — their programme_term does
    not advance. When they resume, a new enrolment is created with the
    same programme_term they paused at.

    Signals on this model keep Cohort.current_term in sync automatically.
    """

    ACTIVE    = "ACTIVE"
    DEFERRED  = "DEFERRED"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"

    STATUS_CHOICES = [
        (ACTIVE,    "Active"),
        (DEFERRED,  "Deferred"),
        (COMPLETED, "Completed"),
        (WITHDRAWN, "Withdrawn"),
    ]

    cohort         = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="enrolments"
    )
    college_term   = models.ForeignKey(
        "Term", on_delete=models.CASCADE, related_name="enrolments"
    )
    programme_term = models.PositiveSmallIntegerField(
        help_text="Which term of their programme this cohort studies this semester",
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=ACTIVE
    )
    notes  = models.TextField(blank=True)

    class Meta:
        unique_together = [("cohort", "college_term")]
        ordering        = ["college_term__start_date", "cohort__name"]
        indexes         = [
            models.Index(fields=["cohort", "status"]),
            models.Index(fields=["college_term", "status"]),
            models.Index(fields=["programme_term"]),
        ]
        constraints = [
            # A cohort may only have one ACTIVE enrolment per college term.
            # (unique_together already enforces one row per cohort+term, which
            #  implies this, but we keep it explicit for documentation.)
        ]

    def __str__(self):
        return (
            f"{self.cohort.name} | {self.college_term.name} | "
            f"T{self.programme_term} [{self.status}]"
        )

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.status == self.ACTIVE

    @property
    def is_graduating(self) -> bool:
        """True if this is the cohort's final programme term."""
        return self.programme_term >= self.cohort.programme.total_terms

    # ── Unit helpers ──────────────────────────────────────────────────────────

    def get_units(self):
        """All active curriculum units for this enrolment's programme term."""
        return CurriculumUnit.objects.filter(
            programme=self.cohort.programme,
            term_number=self.programme_term,
            is_active=True,
        ).order_by("position")

    def get_scheduled_unit_ids(self) -> set:
        """IDs of units that appeared on the timetable this semester."""
        return set(
            ScheduledUnit.objects.filter(
                term=self.college_term,
                cohort=self.cohort,
                status__in=["DRAFT", "PUBLISHED"],
            ).values_list("curriculum_unit_id", flat=True).distinct()
        )

    def unit_preview(self) -> list[dict]:
        """
        Returns each unit for this enrolment with a mark_complete flag
        indicating whether it appeared on the timetable this semester.
        Used by AdvanceAllCohortsView._preview() and ._confirm().
        """
        scheduled_ids = self.get_scheduled_unit_ids()
        return [
            {
                "unit_id":       str(u.id),
                "code":          u.code,
                "name":          u.name,
                "credit_hours":  u.credit_hours,
                "mark_complete": str(u.id) in {str(i) for i in scheduled_ids},
            }
            for u in self.get_units()
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Signals — keep Cohort.current_term cache in sync with CohortEnrolment
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=CohortEnrolment)
def _sync_cohort_term_on_enrolment_save(sender, instance, **kwargs):
    """
    Keep Cohort.current_term in sync whenever an enrolment is saved.

    Auto-completes ACTIVE enrolments only when BOTH conditions are true:
      1. The cohort is at or past their final programme term.
      2. The college term has already ended (end_date < today).

    This ensures cohorts currently in their final term (still studying)
    are NOT prematurely marked COMPLETED — only past-term stragglers are.
    Cohorts advanced via AdvanceAllCohortsView are set COMPLETED explicitly
    by that view and bypass this check entirely.
    """
    try:
        cohort = instance.cohort
        if (
            instance.status == CohortEnrolment.ACTIVE
            and instance.programme_term >= cohort.programme.total_terms
            and instance.college_term.end_date < date.today()
        ):
            # Use update() to avoid re-triggering this signal recursively
            CohortEnrolment.objects.filter(pk=instance.pk).update(
                status=CohortEnrolment.COMPLETED
            )
            instance.refresh_from_db()

        cohort.sync_current_term_cache()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            f"_sync_cohort_term_on_enrolment_save failed for {instance}: {e}",
            exc_info=True,
        )


@receiver(post_delete, sender=CohortEnrolment)
def _sync_cohort_term_on_enrolment_delete(sender, instance, **kwargs):
    """Keep Cohort.current_term in sync when an enrolment is deleted."""
    try:
        instance.cohort.sync_current_term_cache()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ProgressRecord  (tracks cohort progression through curriculum units)
# ─────────────────────────────────────────────────────────────────────────────

class ProgressRecord(TimeStampedModel):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    DEFERRED    = "DEFERRED"

    STATUS_CHOICES = [
        (NOT_STARTED, "Not Started"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED,   "Completed"),
        (DEFERRED,    "Deferred"),
    ]

    cohort          = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="progress_records"
    )
    curriculum_unit = models.ForeignKey(
        CurriculumUnit, on_delete=models.CASCADE, related_name="progress_records"
    )
    # The college term in which this unit was studied — kept for backwards
    # compatibility and reporting. enrolment is the richer reference.
    term            = models.ForeignKey(
        "Term", on_delete=models.CASCADE, related_name="progress_records"
    )
    # FK to enrolment — the precise context (which semester this was studied).
    # Nullable for backwards-compat; always populated for new records.
    enrolment       = models.ForeignKey(
        CohortEnrolment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records",
        help_text="The enrolment period during which this unit was studied.",
    )
    status      = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=NOT_STARTED
    )
    started_at  = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    score       = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    notes       = models.TextField(blank=True)

    class Meta:
        # One progress record per cohort × unit (across all time).
        # The enrolment / term fields record *when* it was completed.
        unique_together = [("cohort", "curriculum_unit")]
        ordering        = [
            "cohort",
            "curriculum_unit__term_number",
            "curriculum_unit__position",
        ]
        indexes = [
            models.Index(fields=["cohort", "status"]),
            models.Index(fields=["curriculum_unit", "status"]),
            models.Index(fields=["enrolment"]),
        ]

    def __str__(self):
        return f"{self.cohort} | {self.curriculum_unit.code} | {self.status}"

    def mark_completed(self, score=None) -> None:
        self.status       = self.COMPLETED
        self.completed_at = date.today()
        if score is not None:
            self.score = score
        self.save(update_fields=["status", "completed_at", "score", "updated_at"])

    def mark_in_progress(self) -> None:
        self.status     = self.IN_PROGRESS
        self.started_at = date.today()
        self.save(update_fields=["status", "started_at", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# Room
# ─────────────────────────────────────────────────────────────────────────────

class Room(TimeStampedModel):
    ROOM_TYPE_CHOICES = [
        ("CLASSROOM", "Classroom"),
        ("LAB",       "Laboratory"),
        ("COMPUTER",  "Computer Lab"),
        ("CLINICAL",  "Clinical Lab"),
        ("WORKSHOP",  "Workshop"),
        ("SEMINAR",   "Seminar Room"),
        ("HALL",      "Lecture Hall"),
        ("ONLINE",    "Online / Virtual"),
        ("OTHER",     "Other"),
    ]

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="rooms"
    )
    code        = models.CharField(max_length=20)
    name        = models.CharField(max_length=100)
    room_type   = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES)
    capacity    = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    building    = models.CharField(max_length=100, blank=True)
    floor       = models.SmallIntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    features    = models.JSONField(
        default=list,
        help_text='e.g. ["projector","whiteboard","aircon"]',
    )

    class Meta:
        ordering        = ["building", "code"]
        unique_together = [("institution", "code")]
        indexes         = [
            models.Index(fields=["room_type", "capacity"]),
            models.Index(fields=["institution", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.capacity})"


# ─────────────────────────────────────────────────────────────────────────────
# Period
# ─────────────────────────────────────────────────────────────────────────────

class Period(models.Model):
    """
    A named time block (e.g. Period 1: 08:00-10:00).
    Belongs to an institution — different institutions may have different
    period structures.
    """
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="periods"
    )
    label       = models.CharField(
        max_length=30, help_text='e.g. "Period 1" or "Morning Block"'
    )
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    order       = models.PositiveSmallIntegerField()
    is_break    = models.BooleanField(
        default=False,
        help_text="Mark breaks so the scheduler skips them",
    )

    class Meta:
        ordering        = ["institution", "order"]
        unique_together = [("institution", "order")]

    def __str__(self):
        return f"{self.label} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    @property
    def duration_hours(self) -> float:
        today = date.today()
        delta = (
            datetime.combine(today, self.end_time)
            - datetime.combine(today, self.start_time)
        )
        return round(delta.seconds / 3600, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Term
# ─────────────────────────────────────────────────────────────────────────────

class Term(TimeStampedModel):
    """
    An academic term for an institution.
    college_year / college_semester encode the fixed 3-semester calendar:
      Sem 1 = Jan–Apr, Sem 2 = May–Aug, Sem 3 = Sep–Dec.
    """
    institution      = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="terms"
    )
    name             = models.CharField(max_length=100)
    start_date       = models.DateField()
    end_date         = models.DateField()
    teaching_weeks   = models.PositiveSmallIntegerField(default=14)
    is_current       = models.BooleanField(default=False)
    college_year     = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Calendar year this college semester belongs to, e.g. 2026",
    )
    college_semester = models.PositiveSmallIntegerField(
        null=True, blank=True,
        choices=[
            (1, "Semester 1 (Jan–Apr)"),
            (2, "Semester 2 (May–Aug)"),
            (3, "Semester 3 (Sep–Dec)"),
        ],
        help_text="Which college-wide semester: 1=Jan, 2=May, 3=Sep",
    )

    class Meta:
        ordering = ["-start_date"]
        indexes  = [
            models.Index(fields=["institution", "is_current"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["college_year", "college_semester"]),
        ]

    def __str__(self):
        return f"{self.institution.short_name} – {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("end_date must be after start_date.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_current:
            Term.objects.filter(
                institution=self.institution, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @property
    def week_number(self) -> int:
        today = timezone.now().date()
        if today < self.start_date:
            return 0
        elapsed = (today - self.start_date).days // 7 + 1
        return max(0, min(elapsed, self.teaching_weeks))

    @property
    def weeks_remaining(self) -> int:
        return max(0, self.teaching_weeks - self.week_number)


# ─────────────────────────────────────────────────────────────────────────────
# CollegeCalendar  — stateless utility for the 3-semester year
# ─────────────────────────────────────────────────────────────────────────────

class CollegeCalendar:
    """
    Sem 1 → 1 Jan – 30 Apr
    Sem 2 → 1 May – 31 Aug
    Sem 3 → 1 Sep – 31 Dec
    """
    SEM_START_MONTH: dict[int, int] = {1: 1, 2: 5, 3: 9}
    SEM_END_MONTH:   dict[int, int] = {1: 4, 2: 8, 3: 12}

    @staticmethod
    def semester_for_date(d: date) -> tuple[int, int]:
        m = d.month
        if m <= 4:
            return d.year, 1
        if m <= 8:
            return d.year, 2
        return d.year, 3

    @staticmethod
    def current_semester() -> tuple[int, int]:
        return CollegeCalendar.semester_for_date(date.today())

    @staticmethod
    def next_semester(year: int, semester: int) -> tuple[int, int]:
        if semester == 3:
            return year + 1, 1
        return year, semester + 1

    @staticmethod
    def semester_dates(year: int, semester: int) -> tuple[date, date]:
        start_month = CollegeCalendar.SEM_START_MONTH[semester]
        end_month   = CollegeCalendar.SEM_END_MONTH[semester]
        end_day     = 30 if end_month == 4 else 31
        return date(year, start_month, 1), date(year, end_month, end_day)

    @staticmethod
    def cohort_term_at(
        cohort_start_year: int,
        cohort_start_month: int,
        college_year: int,
        college_semester: int,
        total_terms: int,
    ) -> int | None:
        """
        Return which programme term a cohort was/is in during a given
        college semester, or None if they hadn't started yet.
        """
        target_idx       = college_year * 3 + (college_semester - 1)
        cohort_sem       = (
            1 if cohort_start_month <= 4 else
            2 if cohort_start_month <= 8 else 3
        )
        cohort_start_idx = cohort_start_year * 3 + (cohort_sem - 1)
        elapsed          = target_idx - cohort_start_idx
        if elapsed < 0:
            return None
        return min(elapsed + 1, total_terms)

    @staticmethod
    def semester_label(year: int, semester: int) -> str:
        labels = {1: "Jan–Apr", 2: "May–Aug", 3: "Sep–Dec"}
        return f"Sem {semester} – {year} ({labels[semester]})"


# ─────────────────────────────────────────────────────────────────────────────
# Trainer
# ─────────────────────────────────────────────────────────────────────────────

class Trainer(TimeStampedModel):
    EMPLOYMENT_CHOICES = [
        ("FT", "Full-time"),
        ("PT", "Part-time"),
        ("VS", "Visiting"),
        ("CT", "Contract"),
    ]

    institution          = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="trainers"
    )
    department           = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="trainers"
    )
    staff_id             = models.CharField(max_length=30, unique=True)
    title                = models.CharField(max_length=20, blank=True)
    first_name           = models.CharField(max_length=100)
    last_name            = models.CharField(max_length=100)
    email                = models.EmailField(unique=True)
    phone                = models.CharField(max_length=20, blank=True)
    employment_type      = models.CharField(
        max_length=2, choices=EMPLOYMENT_CHOICES, default="FT"
    )
    max_periods_per_week = models.PositiveSmallIntegerField(
        default=20,
        help_text="Maximum teaching periods (not hours) per week",
    )
    available_days       = models.JSONField(
        default=list,
        help_text=(
            'Specific days available, e.g. ["MON","WED","FRI"]. '
            "Leave empty for FT staff (means all institution days)."
        ),
    )
    user      = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="trainer_profile",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes  = [
            models.Index(fields=["institution", "is_active"]),
            models.Index(fields=["department"]),
            models.Index(fields=["employment_type"]),
        ]

    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name}".strip()

    @property
    def full_name(self) -> str:
        return f"{self.title} {self.first_name} {self.last_name}".strip()

    @property
    def short_name(self) -> str:
        return f"{self.title} {self.last_name}".strip()

    def get_available_days(self, institution: Institution) -> list[str]:
        if self.employment_type == "FT" and not self.available_days:
            return list(institution.days_of_week)
        return list(self.available_days)


# ─────────────────────────────────────────────────────────────────────────────
# TrainerAvailability
# ─────────────────────────────────────────────────────────────────────────────

class TrainerAvailability(TimeStampedModel):
    BLOCK_REASON_CHOICES = [
        ("LEAVE",       "Annual Leave"),
        ("SICK",        "Sick Leave"),
        ("TRAINING",    "Training / Conference"),
        ("ADMIN",       "Administrative Duty"),
        ("UNAVAILABLE", "Unavailable (no reason)"),
        ("PREFERRED",   "Preferred slot (soft)"),
    ]

    trainer      = models.ForeignKey(
        Trainer, on_delete=models.CASCADE, related_name="availability_rules"
    )
    term         = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="trainer_availability"
    )
    day          = models.CharField(max_length=3)   # MON, TUE, …
    period       = models.ForeignKey(
        Period, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Leave blank to block the entire day",
    )
    is_available = models.BooleanField(
        default=False,
        help_text="False = BLOCKED, True = explicitly available (for soft preferences)",
    )
    reason       = models.CharField(
        max_length=15, choices=BLOCK_REASON_CHOICES, default="UNAVAILABLE"
    )
    notes        = models.TextField(blank=True)

    class Meta:
        ordering = ["trainer", "day", "period__order"]
        indexes  = [
            models.Index(fields=["trainer", "term"]),
            models.Index(fields=["day", "is_available"]),
        ]

    def __str__(self):
        slot = str(self.period) if self.period_id else "all day"
        flag = "AVAILABLE" if self.is_available else "BLOCKED"
        return f"{self.trainer.short_name} {self.day} {slot} [{flag}]"


# ─────────────────────────────────────────────────────────────────────────────
# Constraint
# ─────────────────────────────────────────────────────────────────────────────

class Constraint(TimeStampedModel):
    SCOPE_CHOICES = [
        ("UNIT",    "Curriculum Unit"),
        ("TRAINER", "Trainer"),
        ("ROOM",    "Room"),
        ("COHORT",  "Cohort"),
    ]
    RULE_CHOICES = [
        ("PIN_DAY_PERIOD", "Pin to day + period"),
        ("PIN_DAY",        "Pin to day (any period)"),
        ("PREFERRED_ROOM", "Preferred room"),
        ("AVOID_DAY",      "Avoid day"),
        ("AVOID_PERIOD",   "Avoid period"),
        ("BACK_TO_BACK",   "Schedule back-to-back"),
        ("MAX_PER_DAY",    "Max periods per day"),
    ]

    scope           = models.CharField(max_length=8, choices=SCOPE_CHOICES)
    rule            = models.CharField(max_length=20, choices=RULE_CHOICES)
    is_hard         = models.BooleanField(
        default=True,
        help_text="Hard constraints must be satisfied. Soft = try but can skip.",
    )
    curriculum_unit = models.ForeignKey(
        CurriculumUnit, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints",
    )
    trainer         = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints",
    )
    room            = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints",
    )
    cohort          = models.ForeignKey(
        Cohort, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints",
    )
    parameters      = models.JSONField(default=dict)
    is_active       = models.BooleanField(default=True)
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_hard", "scope", "rule"]
        indexes  = [
            models.Index(fields=["curriculum_unit", "is_active"]),
            models.Index(fields=["trainer", "is_active"]),
            models.Index(fields=["cohort", "is_active"]),
        ]

    def __str__(self):
        hardness = "HARD" if self.is_hard else "SOFT"
        return f"[{hardness}] {self.scope} {self.rule} — {self.parameters}"


# ─────────────────────────────────────────────────────────────────────────────
# ScheduledUnit  (the master timetable template)
# ─────────────────────────────────────────────────────────────────────────────

class ScheduledUnit(TimeStampedModel):
    STATUS_CHOICES = [
        ("DRAFT",     "Draft"),
        ("PUBLISHED", "Published"),
        ("CANCELLED", "Cancelled"),
    ]

    term            = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    cohort          = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    curriculum_unit = models.ForeignKey(
        CurriculumUnit, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    trainer         = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="scheduled_units",
    )
    room            = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    day             = models.CharField(max_length=3)
    period          = models.ForeignKey(
        Period, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    sequence        = models.PositiveSmallIntegerField(
        default=0,
        help_text="0 = single period; 1 = first of a pair; 2 = second of a pair",
    )
    is_combined     = models.BooleanField(default=False)
    combined_key    = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Shared key linking rows for combined cohorts",
    )
    status          = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="DRAFT"
    )
    published_at    = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ["day", "period__order", "cohort"]
        indexes  = [
            models.Index(fields=["term", "status"]),
            models.Index(fields=["trainer", "day", "period"]),
            models.Index(fields=["cohort", "day", "period"]),
            models.Index(fields=["room", "day", "period"]),
            models.Index(fields=["combined_key"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=["term", "trainer", "day", "period"],
                condition=Q(status="PUBLISHED"),
                name="uniq_trainer_slot_published",
            ),
            UniqueConstraint(
                fields=["term", "cohort", "day", "period"],
                condition=Q(status="PUBLISHED"),
                name="uniq_cohort_slot_published",
            ),
            UniqueConstraint(
                fields=["term", "room", "day", "period"],
                condition=Q(status="PUBLISHED"),
                name="uniq_room_slot_published",
            ),
        ]

    def __str__(self):
        tag = f" [{self.sequence}/2]" if self.sequence else ""
        return (
            f"{self.curriculum_unit.code} | {self.cohort} | "
            f"{self.day} {self.period}{tag}"
        )

    def publish(self) -> None:
        self.status       = "PUBLISHED"
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# Conflict
# ─────────────────────────────────────────────────────────────────────────────

class Conflict(TimeStampedModel):
    TYPE_CHOICES = [
        ("TRAINER_CLASH", "Trainer double-booked"),
        ("ROOM_CLASH",    "Room double-booked"),
        ("COHORT_CLASH",  "Cohort double-booked"),
        ("NO_TRAINER",    "No qualified trainer"),
        ("NO_ROOM",       "No suitable room"),
        ("CONSTRAINT",    "Constraint violated"),
        ("CAPACITY",      "Room capacity exceeded"),
    ]
    SEVERITY_CHOICES = [
        ("HIGH",   "High — blocks publishing"),
        ("MEDIUM", "Medium — possible issue"),
        ("LOW",    "Low — informational"),
    ]
    RESOLUTION_CHOICES = [
        ("PENDING",    "Pending"),
        ("RESOLVED",   "Resolved"),
        ("OVERRIDDEN", "Overridden"),
        ("IGNORED",    "Ignored"),
    ]

    term              = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="conflicts"
    )
    conflict_type     = models.CharField(max_length=15, choices=TYPE_CHOICES)
    severity          = models.CharField(
        max_length=6, choices=SEVERITY_CHOICES, default="HIGH"
    )
    description       = models.TextField()
    curriculum_unit   = models.ForeignKey(
        CurriculumUnit, null=True, blank=True, on_delete=models.SET_NULL
    )
    cohort            = models.ForeignKey(
        Cohort, null=True, blank=True, on_delete=models.SET_NULL
    )
    trainer           = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.SET_NULL
    )
    room              = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.SET_NULL
    )
    resolution_status = models.CharField(
        max_length=10, choices=RESOLUTION_CHOICES, default="PENDING"
    )
    resolved_by       = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="resolved_conflicts",
    )
    resolved_at       = models.DateTimeField(null=True, blank=True)
    resolution_note   = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-severity"]
        indexes  = [
            models.Index(fields=["term", "resolution_status"]),
            models.Index(fields=["conflict_type", "severity"]),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.get_conflict_type_display()}"

    def resolve(self, note: str, resolved_by: User, method: str = "RESOLVED") -> None:
        self.resolution_status = method
        self.resolved_by       = resolved_by
        self.resolved_at       = timezone.now()
        self.resolution_note   = note
        self.save(update_fields=[
            "resolution_status", "resolved_by", "resolved_at",
            "resolution_note", "updated_at",
        ])


# ─────────────────────────────────────────────────────────────────────────────
# AuditLog  (immutable change trail)
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(models.Model):
    """Immutable — never delete rows from this table."""

    ACTION_CHOICES = [
        ("GENERATE", "Timetable Generated"),
        ("PUBLISH",  "Timetable Published"),
        ("DELETE",   "Timetable Deleted"),
        ("EDIT",     "Entry Edited"),
        ("CANCEL",   "Entry Cancelled"),
        ("RESOLVE",  "Conflict Resolved"),
        ("PROGRESS", "Progress Updated"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp    = models.DateTimeField(auto_now_add=True, db_index=True)
    action       = models.CharField(max_length=10, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    term         = models.ForeignKey(
        Term, null=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    description  = models.TextField()
    payload      = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} by {self.performed_by} @ {self.timestamp:%Y-%m-%d %H:%M}"