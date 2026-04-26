"""
timetable/models.py
===================
Industry-standard timetabling system.

Design principles
-----------------
* FLAT over deep â€” fewer models, clearer foreign keys, no hidden syncs.
* One source of truth â€” CurriculumUnit owns what units exist per programme-stage.
  ScheduledUnit owns what is on the timetable. No IntakeUnit / Stage sync dance.
* Template-first â€” the timetable is a weekly recurring template (one row per
  programme Ã— unit Ã— slot). Physical week expansion is done in the view/export
  layer, never stored.
* Constraint-driven â€” hard/soft constraints are data, not code paths.
* Progression tracking â€” StudentProgress records which units a student-group
  has completed, is doing, or has yet to start.
* Venue & trainer availability â€” first-class models, not JSON blobs.
* Works for any institution â€” no assumptions about semester count, year length,
  or curriculum shape.

Model map
---------
Institution          â€” the top-level tenant (multi-institution ready)
Department           â€” faculty/school/department
Programme            â€” any qualification with a curriculum
CurriculumUnit       â€” a unit at a specific position in a programme's curriculum
Cohort               â€” a group of students doing a programme (intake)
Trainer              â€” lecturer/instructor/facilitator
Room                 â€” any schedulable space (classroom, lab, online)
Period               â€” a named time-slot (e.g. "Period 1 08:00-10:00")
Term                 â€” an academic term/semester
Constraint           â€” scheduling rule (hard or soft) for a unit/trainer/room
ScheduledUnit        â€” one row in the master timetable template
ProgressRecord       â€” cohort's completion status per curriculum unit
TrainerAvailability  â€” days/periods a trainer is available each term
Conflict             â€” unresolved clash found during generation
AuditLog             â€” immutable change trail
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.utils import timezone


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers / Mixins
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TimeStampedModel(models.Model):
    """Abstract base â€” UUID pk, created/updated timestamps, soft-delete."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Institution (multi-tenancy ready â€” leave as single row if not needed)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Institution(TimeStampedModel):
    name          = models.CharField(max_length=200, unique=True)
    short_name    = models.CharField(max_length=50)
    country       = models.CharField(max_length=100, blank=True)
    timezone      = models.CharField(max_length=60, default="Africa/Nairobi")
    # Timetable policy knobs â€” institutions differ
    days_of_week  = models.JSONField(
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Department
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Department(TimeStampedModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="departments"
    )
    name        = models.CharField(max_length=200)
    code        = models.CharField(max_length=20)
    hod         = models.CharField(max_length=200, blank=True)
    email       = models.EmailField(blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering            = ["name"]
        unique_together     = [("institution", "code")]

    def __str__(self):
        return f"{self.code} â€“ {self.name}"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Programme
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Programme(TimeStampedModel):
    LEVEL_CHOICES = [
        ("CERT",   "Certificate"),
        ("DIP",    "Diploma"),
        ("HDIP",   "Higher Diploma"),
        ("DEG",    "Degree"),
        ("PG_DIP", "Postgraduate Diploma"),
        ("MASTERS","Masters"),
        ("PHD",    "PhD"),
        ("OTHER",  "Other"),
    ]

    department   = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="programmes"
    )
    name         = models.CharField(max_length=200)
    code         = models.CharField(max_length=30, unique=True)
    level        = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    total_terms  = models.PositiveSmallIntegerField(
        default=4,
        help_text="Total number of teaching terms in the programme",
    )
    # Programmes that share units are linked via a group code.
    # Any programmes with the same sharing_group will have their overlapping
    # curriculum units scheduled together (combined class).
    sharing_group = models.CharField(
        max_length=60, blank=True, db_index=True,
        help_text="Set the same value on programmes that share units.",
    )
    is_active    = models.BooleanField(default=True)

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CurriculumUnit  (replaces Stage + Unit + IntakeUnit in one clean model)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CurriculumUnit(TimeStampedModel):
    """
    A unit at a specific position in a programme's curriculum.

    term_number  â€” which term it belongs to (1-based, e.g. 1 = first term).
    position     â€” order within that term (for display sorting).

    There is NO separate Stage model. A "stage" is simply a term_number.
    This avoids the fragile IntakeUnit sync that caused bugs in the old code.
    """
    UNIT_TYPE_CHOICES = [
        ("CORE",      "Core"),
        ("ELECTIVE",  "Elective"),
        ("PRACTICAL", "Practical"),
        ("PROJECT",   "Project"),
    ]

    programme        = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="curriculum_units"
    )
    term_number      = models.PositiveSmallIntegerField(
        help_text="Which term (1 = first term of programme)",
    )
    position         = models.PositiveSmallIntegerField(default=1)
    code             = models.CharField(max_length=30)
    name             = models.CharField(max_length=200)
    unit_type        = models.CharField(
        max_length=10, choices=UNIT_TYPE_CHOICES, default="CORE"
    )
    credit_hours     = models.PositiveSmallIntegerField(default=3)
    # How many periods per week this unit needs on the timetable
    periods_per_week = models.PositiveSmallIntegerField(
        default=1,
        help_text="1 = single period, 2 = double period (consecutive)",
    )
    # Trainers qualified to teach this unit (M2M for flexibility)
    qualified_trainers = models.ManyToManyField(
        "Trainer", blank=True, related_name="qualified_units", through="CurriculumUnitTrainer"
    )
    is_outsourced    = models.BooleanField(default=False, help_text='Unit is taught by an external/outsourced trainer')
    is_active        = models.BooleanField(default=True)
    notes            = models.TextField(blank=True)

    class Meta:
        ordering        = ["programme", "term_number", "position"]
        unique_together = [("programme", "code")]
        indexes         = [
            models.Index(fields=["programme", "term_number"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.programme.code} T{self.term_number} â€“ {self.code} {self.name}"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Cohort  (replaces Intake â€” cleaner name, same concept)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


# -----------------------------------------------------------------------------
# CurriculumUnitTrainer  (through model for qualified_trainers)
# -----------------------------------------------------------------------------
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
        help_text="Optional custom label e.g. 'HOD Physics dept'"
    )

    class Meta:
        unique_together = [("curriculum_unit", "trainer")]
        ordering = ["trainer_type", "trainer__last_name"]

    def __str__(self):
        return f"{self.curriculum_unit.code} - {self.trainer.short_name} ({self.trainer_type})"

class Cohort(TimeStampedModel):
    """
    A group of students admitted to a programme at a specific time.
    current_term is the term they are currently studying.
    It is set manually or via the advance_term() helper.
    """
    programme     = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="cohorts"
    )
    name          = models.CharField(max_length=100)
    # When they started (year + month is enough for any institution)
    start_year    = models.PositiveSmallIntegerField()
    start_month   = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    current_term  = models.PositiveSmallIntegerField(
        default=1,
        help_text="Which programme term this cohort is currently in",
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
        return f"{self.programme.code} â€“ {self.name}"

    # â”€â”€ Progression helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def current_units(self) -> models.QuerySet:
        """Units the cohort is studying this term."""
        return CurriculumUnit.objects.filter(
            programme=self.programme,
            term_number=self.current_term,
            is_active=True,
        )

    def completed_units(self) -> models.QuerySet:
        """Units marked completed in progress records."""
        completed_ids = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.COMPLETED
        ).values_list("curriculum_unit_id", flat=True)
        return CurriculumUnit.objects.filter(id__in=completed_ids)

    def remaining_units(self) -> models.QuerySet:
        """Future curriculum units not yet completed."""
        completed_ids = ProgressRecord.objects.filter(
            cohort=self, status=ProgressRecord.COMPLETED
        ).values_list("curriculum_unit_id", flat=True)
        return CurriculumUnit.objects.filter(
            programme=self.programme,
            term_number__gt=self.current_term,
            is_active=True,
        ).exclude(id__in=completed_ids)

    def advance_term(self, by: int = 1) -> None:
        """Move cohort to the next term (call at end of term)."""
        max_term = self.programme.total_terms
        self.current_term = min(self.current_term + by, max_term)
        self.save(update_fields=["current_term", "updated_at"])

    @property
    def progress_summary(self) -> dict:
        total     = CurriculumUnit.objects.filter(
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ProgressRecord  (tracks student-group progression through curriculum)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    term            = models.ForeignKey(
        "Term", on_delete=models.CASCADE, related_name="progress_records"
    )
    status          = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=NOT_STARTED
    )
    started_at      = models.DateField(null=True, blank=True)
    completed_at    = models.DateField(null=True, blank=True)
    score           = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    notes           = models.TextField(blank=True)

    class Meta:
        unique_together = [("cohort", "curriculum_unit", "term")]
        ordering        = ["cohort", "curriculum_unit__term_number", "curriculum_unit__position"]
        indexes         = [
            models.Index(fields=["cohort", "status"]),
            models.Index(fields=["curriculum_unit", "status"]),
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Room
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    institution  = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="rooms"
    )
    code         = models.CharField(max_length=20)
    name         = models.CharField(max_length=100)
    room_type    = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES)
    capacity     = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    building     = models.CharField(max_length=100, blank=True)
    floor        = models.SmallIntegerField(default=0)
    is_active    = models.BooleanField(default=True)
    features     = models.JSONField(
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Period  (replaces TimeSlot â€” cleaner name, same concept)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Period(models.Model):
    """
    A named time block (e.g. Period 1: 08:00-10:00).
    Belongs to an institution â€” different institutions may have different
    period structures.
    """
    institution  = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="periods"
    )
    label        = models.CharField(
        max_length=30, help_text='e.g. "Period 1" or "Morning Block"'
    )
    start_time   = models.TimeField()
    end_time     = models.TimeField()
    order        = models.PositiveSmallIntegerField()
    is_break     = models.BooleanField(
        default=False,
        help_text="Mark breaks so the scheduler skips them",
    )

    class Meta:
        ordering        = ["institution", "order"]
        unique_together = [("institution", "order")]

    def __str__(self):
        return f"{self.label} ({self.start_time:%H:%M}â€“{self.end_time:%H:%M})"

    @property
    def duration_hours(self) -> float:
        today = date.today()
        delta = (
            datetime.combine(today, self.end_time)
            - datetime.combine(today, self.start_time)
        )
        return round(delta.seconds / 3600, 2)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Term  (replaces Semester â€” institution-agnostic)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Term(TimeStampedModel):
    """
    An academic term for an institution.
    name is free-form so any convention works (Semester 1, Term 2, Q3, etc.).
    """
    institution    = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="terms"
    )
    name           = models.CharField(max_length=100)
    start_date     = models.DateField()
    end_date       = models.DateField()
    teaching_weeks = models.PositiveSmallIntegerField(default=14)
    is_current     = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        indexes  = [
            models.Index(fields=["institution", "is_current"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.institution.short_name} â€“ {self.name}"

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Trainer  (replaces Lecturer)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Trainer(TimeStampedModel):
    EMPLOYMENT_CHOICES = [
        ("FT", "Full-time"),
        ("PT", "Part-time"),
        ("VS", "Visiting"),
        ("CT", "Contract"),
    ]

    institution      = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="trainers"
    )
    department       = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="trainers"
    )
    staff_id         = models.CharField(max_length=30, unique=True)
    title            = models.CharField(max_length=20, blank=True)
    first_name       = models.CharField(max_length=100)
    last_name        = models.CharField(max_length=100)
    email            = models.EmailField(unique=True)
    phone            = models.CharField(max_length=20, blank=True)
    employment_type  = models.CharField(
        max_length=2, choices=EMPLOYMENT_CHOICES, default="FT"
    )
    max_periods_per_week = models.PositiveSmallIntegerField(
        default=20,
        help_text="Maximum teaching periods (not hours) per week",
    )
    # Full-time staff available all institution days by default.
    # Part-time / visiting â€” store their specific available days as a list.
    available_days   = models.JSONField(
        default=list,
        help_text=(
            'Specific days available, e.g. ["MON","WED","FRI"]. '
            "Leave empty for FT staff (means all institution days)."
        ),
    )
    user             = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="trainer_profile",
    )
    is_active        = models.BooleanField(default=True)

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
        """Return the effective days this trainer is available."""
        if self.employment_type == "FT" and not self.available_days:
            return list(institution.days_of_week)
        return list(self.available_days)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TrainerAvailability  (per-term availability / blocking)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TrainerAvailability(TimeStampedModel):
    """
    Blocks or declares specific periods unavailable for a trainer in a term.
    The scheduler checks this before assigning any slot.
    """
    BLOCK_REASON_CHOICES = [
        ("LEAVE",       "Annual Leave"),
        ("SICK",        "Sick Leave"),
        ("TRAINING",    "Training / Conference"),
        ("ADMIN",       "Administrative Duty"),
        ("UNAVAILABLE", "Unavailable (no reason)"),
        ("PREFERRED",   "Preferred slot (soft)"),
    ]

    trainer       = models.ForeignKey(
        Trainer, on_delete=models.CASCADE, related_name="availability_rules"
    )
    term          = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="trainer_availability"
    )
    day           = models.CharField(max_length=3)   # MON, TUE, â€¦
    period        = models.ForeignKey(
        Period, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Leave blank to block the entire day",
    )
    is_available  = models.BooleanField(
        default=False,
        help_text="False = BLOCKED, True = explicitly available (for soft preferences)",
    )
    reason        = models.CharField(
        max_length=15, choices=BLOCK_REASON_CHOICES, default="UNAVAILABLE"
    )
    notes         = models.TextField(blank=True)

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Constraint  (scheduling rules â€” hard and soft)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Constraint(TimeStampedModel):
    """
    A scheduling rule that the engine must (HARD) or should (SOFT) respect.

    scope    â€” what the rule applies to (unit, trainer, room, cohort)
    rule     â€” what the rule says

    Supported rule types
    --------------------
    PIN_DAY_PERIOD   â€” must be on a specific day + period
    PIN_DAY          â€” must be on a specific day (any period)
    PREFERRED_ROOM   â€” try to use this room
    AVOID_DAY        â€” avoid a given day
    AVOID_PERIOD     â€” avoid a given period
    BACK_TO_BACK     â€” schedule consecutive periods (for double units)
    MAX_PER_DAY      â€” maximum periods per day for a cohort/trainer
    """

    SCOPE_CHOICES = [
        ("UNIT",    "Curriculum Unit"),
        ("TRAINER", "Trainer"),
        ("ROOM",    "Room"),
        ("COHORT",  "Cohort"),
    ]
    RULE_CHOICES = [
        ("PIN_DAY_PERIOD",  "Pin to day + period"),
        ("PIN_DAY",         "Pin to day (any period)"),
        ("PREFERRED_ROOM",  "Preferred room"),
        ("AVOID_DAY",       "Avoid day"),
        ("AVOID_PERIOD",    "Avoid period"),
        ("BACK_TO_BACK",    "Schedule back-to-back"),
        ("MAX_PER_DAY",     "Max periods per day"),
    ]

    scope          = models.CharField(max_length=8, choices=SCOPE_CHOICES)
    rule           = models.CharField(max_length=20, choices=RULE_CHOICES)
    is_hard        = models.BooleanField(
        default=True,
        help_text="Hard constraints must be satisfied. Soft = try but can skip.",
    )
    # At most one of these points to the constrained entity
    curriculum_unit = models.ForeignKey(
        CurriculumUnit, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints"
    )
    trainer        = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints"
    )
    room           = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints"
    )
    cohort         = models.ForeignKey(
        Cohort, null=True, blank=True, on_delete=models.CASCADE,
        related_name="constraints"
    )
    # Rule parameters â€” flexible JSON payload
    # PIN_DAY_PERIOD:  {"day": "MON", "period_id": "<uuid>"}
    # PIN_DAY:         {"day": "WED"}
    # PREFERRED_ROOM:  {"room_id": "<uuid>"}
    # AVOID_DAY:       {"day": "FRI"}
    # AVOID_PERIOD:    {"period_id": "<uuid>"}
    # MAX_PER_DAY:     {"max": 2}
    parameters     = models.JSONField(default=dict)
    is_active      = models.BooleanField(default=True)
    notes          = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_hard", "scope", "rule"]
        indexes  = [
            models.Index(fields=["curriculum_unit", "is_active"]),
            models.Index(fields=["trainer", "is_active"]),
            models.Index(fields=["cohort", "is_active"]),
        ]

    def __str__(self):
        hardness = "HARD" if self.is_hard else "SOFT"
        return f"[{hardness}] {self.scope} {self.rule} â€“ {self.parameters}"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ScheduledUnit  (the master timetable template)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ScheduledUnit(TimeStampedModel):
    """
    One row in the weekly timetable template.

    Represents: cohort X studies curriculum_unit Y with trainer Z
                in room R on day D at period P during term T.

    This is a TEMPLATE â€” it repeats every teaching week of the term.
    week_number is NOT stored; derive it in the view layer if needed.

    For double/consecutive periods, two ScheduledUnit rows are created
    (same unit, same day, consecutive periods) linked by sequence (1 and 2).

    status
    ------
    DRAFT      â€” generated, not published
    PUBLISHED  â€” live and visible to students / trainers
    CANCELLED  â€” cancelled for this term
    """

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
        Trainer, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    room            = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    day             = models.CharField(max_length=3)       # MON, TUE, â€¦
    period          = models.ForeignKey(
        Period, on_delete=models.CASCADE, related_name="scheduled_units"
    )
    # For consecutive double periods: sequence = 1 for first slot, 2 for second
    sequence        = models.PositiveSmallIntegerField(
        default=0,
        help_text="0 = single period; 1 = first of a pair; 2 = second of a pair",
    )
    # Combined classes: multiple cohorts attending the same session
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
            # Prevent trainer double-booking (published only)
            UniqueConstraint(
                fields=["term", "trainer", "day", "period"],
                condition=Q(status="PUBLISHED"),
                name="uniq_trainer_slot_published",
            ),
            # Prevent cohort double-booking (published only)
            UniqueConstraint(
                fields=["term", "cohort", "day", "period"],
                condition=Q(status="PUBLISHED"),
                name="uniq_cohort_slot_published",
            ),
            # Prevent room double-booking (published only)
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Conflict  (clashes found during / after generation)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Conflict(TimeStampedModel):
    """
    A scheduling conflict that could not be auto-resolved.
    The scheduler creates these; coordinators resolve them.
    """
    TYPE_CHOICES = [
        ("TRAINER_CLASH",  "Trainer double-booked"),
        ("ROOM_CLASH",     "Room double-booked"),
        ("COHORT_CLASH",   "Cohort double-booked"),
        ("NO_TRAINER",     "No qualified trainer"),
        ("NO_ROOM",        "No suitable room"),
        ("CONSTRAINT",     "Constraint violated"),
        ("CAPACITY",       "Room capacity exceeded"),
    ]
    SEVERITY_CHOICES = [
        ("HIGH",   "High â€“ blocks publishing"),
        ("MEDIUM", "Medium â€“ possible issue"),
        ("LOW",    "Low â€“ informational"),
    ]
    RESOLUTION_CHOICES = [
        ("PENDING",   "Pending"),
        ("RESOLVED",  "Resolved"),
        ("OVERRIDDEN","Overridden"),
        ("IGNORED",   "Ignored"),
    ]

    term            = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="conflicts"
    )
    conflict_type   = models.CharField(max_length=15, choices=TYPE_CHOICES)
    severity        = models.CharField(
        max_length=6, choices=SEVERITY_CHOICES, default="HIGH"
    )
    description     = models.TextField()
    # What was being scheduled when the conflict was found
    curriculum_unit = models.ForeignKey(
        CurriculumUnit, null=True, blank=True, on_delete=models.SET_NULL
    )
    cohort          = models.ForeignKey(
        Cohort, null=True, blank=True, on_delete=models.SET_NULL
    )
    trainer         = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.SET_NULL
    )
    room            = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.SET_NULL
    )
    # Resolution
    resolution_status = models.CharField(
        max_length=10, choices=RESOLUTION_CHOICES, default="PENDING"
    )
    resolved_by     = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="resolved_conflicts"
    )
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

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
            "resolution_note", "updated_at"
        ])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AuditLog  (immutable change trail)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AuditLog(models.Model):
    """Immutable â€” never delete rows from this table."""

    ACTION_CHOICES = [
        ("GENERATE",  "Timetable Generated"),
        ("PUBLISH",   "Timetable Published"),
        ("DELETE",    "Timetable Deleted"),
        ("EDIT",      "Entry Edited"),
        ("CANCEL",    "Entry Cancelled"),
        ("RESOLVE",   "Conflict Resolved"),
        ("PROGRESS",  "Progress Updated"),
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
    payload      = models.JSONField(default=dict)   # before/after snapshots

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} by {self.performed_by} @ {self.timestamp:%Y-%m-%d %H:%M}"





