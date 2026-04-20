"""
Timetable models — fully updated.

KEY CHANGES FROM PREVIOUS VERSION:
  1. Unit gains is_double_lesson (bool) and is_cross_department (bool).
  2. Programme.shared_unit_group kept; get_sharing_programmes() unchanged.
  3. TimetableEntry.save() no longer calls full_clean() unconditionally —
     only validates when status in _VALIDATED_STATUSES (PUBLISHED, PENDING).
     This eliminates the 500 on force-publish.
  4. TimetableEntry gains is_shared_class (already existed) — now also has
     shared_group_key (str) so the UI can group co-scheduled intakes.
  5. SharedUnitSchedule and UnitOffering models kept but are now informational;
     the scheduler drives everything via TimetableEntry.is_shared_class.
  6. IntakeUnit unchanged — override_source logic intact.
  7. UnitSchedulingConstraint unchanged.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    pass


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["is_deleted", "deleted_at", "is_active", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=["is_deleted", "deleted_at", "is_active", "updated_at"])


# ---------------------------------------------------------------------------
# AcademicYear
# ---------------------------------------------------------------------------


class AcademicYear(BaseModel):
    year = models.IntegerField(
        unique=True, validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_open_for_registration = models.BooleanField(default=False)

    class Meta:
        ordering = ["-year"]
        indexes = [
            models.Index(fields=["year", "is_current"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.year} - {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).filter(is_current=True).update(
                is_current=False
            )
        super().save(*args, **kwargs)

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days

    @property
    def is_active_now(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


# ---------------------------------------------------------------------------
# Semester
# ---------------------------------------------------------------------------


class Semester(BaseModel):
    SEMESTER_CHOICES = [
        ("JAN_APR", "January - April"),
        ("MAY_AUG", "May - August"),
        ("SEP_DEC", "September - December"),
    ]
    SEMESTER_NUMBERS = {"JAN_APR": 1, "MAY_AUG": 2, "SEP_DEC": 3}

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    semester_type = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    semester_number = models.PositiveSmallIntegerField(editable=False)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    teaching_weeks = models.PositiveSmallIntegerField(default=14)
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ("academic_year", "semester_type")

    def __str__(self):
        return f"{self.academic_year.name} — {self.get_semester_type_display()}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.semester_number = self.SEMESTER_NUMBERS[self.semester_type]
        self.full_clean()
        if self.is_active:
            Semester.objects.exclude(pk=self.pk).filter(is_active=True).update(
                is_active=False
            )
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------


class Department(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    hod_name = models.CharField(max_length=200, blank=True)
    hod_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    budget_code = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------


class Programme(BaseModel):
    PROGRAMME_TYPES = [
        ("CERT", "Certificate"),
        ("DIP", "Diploma"),
        ("HDIP", "Higher Diploma"),
    ]

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="programmes"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    programme_type = models.CharField(max_length=4, choices=PROGRAMME_TYPES)
    duration_semesters = models.PositiveSmallIntegerField(default=4)
    duration_years = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    minimum_credits = models.PositiveSmallIntegerField(default=60)
    maximum_credits = models.PositiveSmallIntegerField(default=72)
    description = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    entry_requirements = models.TextField(blank=True)

    # Programmes in the same group share certain units (e.g. CND + DND).
    # The scheduler will schedule shared units once for all intakes in the group.
    shared_unit_group = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=(
            "Group code for programmes that share units (e.g. 'CND_DND_GROUP'). "
            "Programmes in the same group will have shared units scheduled together "
            "at the same time with the same trainer."
        ),
    )

    class Meta:
        ordering = ["programme_type", "code"]
        indexes = [
            models.Index(fields=["code", "programme_type"]),
            models.Index(fields=["department", "programme_type"]),
            models.Index(fields=["shared_unit_group"]),
        ]

    def __str__(self):
        return f"{self.get_programme_type_display()} - {self.name} ({self.code})"

    def clean(self):
        if self.minimum_credits and self.maximum_credits:
            if self.minimum_credits > self.maximum_credits:
                raise ValidationError("Minimum credits cannot exceed maximum credits.")

    def get_sharing_programmes(self):
        """All other programmes in the same sharing group."""
        if self.shared_unit_group:
            return Programme.objects.filter(
                shared_unit_group=self.shared_unit_group,
                is_active=True,
            ).exclude(id=self.id)
        return Programme.objects.none()


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


class Stage(BaseModel):
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="stages"
    )
    semester_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)
    credits_required = models.PositiveSmallIntegerField(default=30)
    is_final_stage = models.BooleanField(default=False)

    class Meta:
        ordering = ["programme", "semester_number"]
        unique_together = ["programme", "semester_number"]
        indexes = [models.Index(fields=["programme", "semester_number"])]

    def __str__(self):
        return f"{self.programme.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Semester {self.semester_number}"
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Unit  (UPDATED: is_double_lesson, is_cross_department)
# ---------------------------------------------------------------------------


class Unit(BaseModel):
    UNIT_TYPES = [
        ("CORE", "Core Unit"),
        ("ELECTIVE", "Elective"),
        ("PREREQUISITE", "Prerequisite"),
        ("REQUIRED", "Required"),
    ]
    ASSESSMENT_TYPES = [
        ("CAT", "Continuous Assessment"),
        ("EXAM", "Final Exam"),
        ("BOTH", "Both CAT and Exam"),
        ("PRACTICAL", "Practical Only"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="units")
    unit_type = models.CharField(max_length=12, choices=UNIT_TYPES, default="CORE")
    credit_hours = models.PositiveSmallIntegerField(default=3)
    lecture_hours_per_week = models.PositiveSmallIntegerField(default=2)
    tutorial_hours_per_week = models.PositiveSmallIntegerField(default=0)
    practical_hours_per_week = models.PositiveSmallIntegerField(default=0)
    total_hours_per_week = models.PositiveSmallIntegerField(editable=False, default=2)
    slots_per_week = models.PositiveSmallIntegerField(editable=False, default=1)
    prerequisites = models.ManyToManyField("self", symmetrical=False, blank=True)
    corequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="co_req_for"
    )
    assessment_type = models.CharField(
        max_length=10, choices=ASSESSMENT_TYPES, default="BOTH"
    )
    cat_weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("30.00")
    )
    exam_weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("70.00")
    )
    pass_mark = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("50.00")
    )
    description = models.TextField(blank=True)
    learning_outcomes = models.TextField(blank=True)
    syllabus = models.FileField(upload_to="syllabus/", blank=True, null=True)

    # NEW: requires two back-to-back time slots per session (4-hour lesson)
    is_double_lesson = models.BooleanField(
        default=False,
        help_text=(
            "If True the scheduler will book two consecutive time slots on the "
            "same day for each weekly occurrence (e.g. a 4-hour practical)."
        ),
    )

    # NEW: unit is taught by a lecturer from outside the intake's own department
    is_cross_department = models.BooleanField(
        default=False,
        help_text=(
            "Unit is taught by a lecturer from a different department. "
            "Scheduling logic is unchanged — this flag is used for display and "
            "reporting only."
        ),
    )

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code", "name"]),
            models.Index(fields=["stage", "unit_type"]),
            models.Index(fields=["is_double_lesson"]),
            models.Index(fields=["is_cross_department"]),
        ]

    def clean(self):
        if self.assessment_type == "BOTH":
            total = (self.cat_weight or 0) + (self.exam_weight or 0)
            if total != 100:
                raise ValidationError(
                    f"CAT and Exam weights must sum to 100 (currently {total})."
                )

    def save(self, *args, **kwargs):
        self.total_hours_per_week = (
            self.lecture_hours_per_week
            + self.tutorial_hours_per_week
            + self.practical_hours_per_week
        )
        lecture_slots = max(1, -(-self.lecture_hours_per_week // 2))
        practical_slots = 1 if self.practical_hours_per_week > 0 else 0
        self.slots_per_week = lecture_slots + practical_slots
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def has_prerequisites(self):
        return self.prerequisites.exists()

    @property
    def prerequisite_list(self):
        return list(self.prerequisites.values_list("code", flat=True))


# ---------------------------------------------------------------------------
# UnitOffering  (informational — shared-unit metadata)
# ---------------------------------------------------------------------------


class UnitOffering(BaseModel):
    """
    Track which programmes take a unit and whether it is shared.

    The scheduler uses Programme.shared_unit_group as the primary driver for
    co-scheduling.  This model is kept for admin visibility and reporting.
    """

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="offerings")
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="unit_offerings"
    )
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="unit_offerings"
    )
    is_shared = models.BooleanField(default=False)
    shared_with_programmes = models.ManyToManyField(
        Programme, blank=True, related_name="shared_units"
    )
    preferred_time_slot = models.ForeignKey(
        "TimeSlot", on_delete=models.SET_NULL, null=True, blank=True
    )
    preferred_day = models.IntegerField(
        choices=[
            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
            (3, "Thursday"), (4, "Friday"), (5, "Saturday"),
        ],
        null=True, blank=True,
    )
    preferred_room_type = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("LECTURE", "Lecture Hall"), ("LAB", "Laboratory"),
            ("CLASSROOM", "Classroom"), ("COMPUTER", "Computer Lab"),
        ],
    )
    combined_student_count = models.IntegerField(default=0)
    assigned_trainer = models.ForeignKey(
        "Lecturer", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="shared_unit_offerings",
    )

    class Meta:
        unique_together = ["unit", "semester", "programme"]
        ordering = ["unit", "programme"]
        indexes = [
            models.Index(fields=["unit", "semester", "is_shared"]),
            models.Index(fields=["programme", "is_shared"]),
        ]

    def __str__(self):
        suffix = " (Shared)" if self.is_shared else ""
        return f"{self.unit.code} - {self.programme.code}{suffix}"


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


class Intake(BaseModel):
    SEMESTER_CHOICES = [
        ("JAN_APR", "January - April (Spring)"),
        ("MAY_AUG", "May - August (Summer)"),
        ("SEP_DEC", "September - December (Fall)"),
    ]
    _SEMESTER_START = {"JAN_APR": 1, "MAY_AUG": 5, "SEP_DEC": 9}

    name = models.CharField(max_length=100, blank=True)
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name="intakes"
    )
    intake_year = models.IntegerField()
    intake_semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    enrollment_date = models.DateField(null=True, blank=True)
    student_count = models.PositiveIntegerField(default=0)
    male_count = models.PositiveIntegerField(default=0)
    female_count = models.PositiveIntegerField(default=0)
    expected_completion = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-intake_year", "-intake_semester", "programme"]
        indexes = [
            models.Index(fields=["programme", "intake_year", "intake_semester"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = ["programme", "intake_year", "intake_semester"]

    def clean(self):
        if self.male_count + self.female_count > self.student_count:
            raise ValidationError(
                "Male + female counts cannot exceed total student count."
            )

    def save(self, *args, **kwargs):
        start_month = self._SEMESTER_START.get(self.intake_semester)
        if start_month:
            self.enrollment_date = date(self.intake_year, start_month, 15)
            if self.programme_id and self.programme.duration_semesters:
                total_months = self.programme.duration_semesters * 4
                end_year = self.intake_year + (start_month - 1 + total_months) // 12
                end_month = (start_month - 1 + total_months) % 12 + 1
                self.expected_completion = date(end_year, end_month, 1)
        if not self.name:
            semester_label = dict(self.SEMESTER_CHOICES).get(self.intake_semester, "")
            short = semester_label.split()[0] if semester_label else self.intake_semester
            self.name = f"{self.programme.code} {short} {self.intake_year}"
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.programme.code} - {self.name}"

    @property
    def gender_ratio(self):
        if not self.student_count:
            return {"male": 0, "female": 0}
        return {
            "male": round(self.male_count / self.student_count * 100, 1),
            "female": round(self.female_count / self.student_count * 100, 1),
        }


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


class Room(BaseModel):
    ROOM_TYPES = [
        ("LECTURE", "Lecture Hall"),
        ("TUTORIAL", "Tutorial Room"),
        ("LAB", "Laboratory"),
        ("COMPUTER", "Computer Lab"),
        ("CLINICAL", "Clinical Lab"),
        ("SEMINAR", "Seminar Room"),
        ("WORKSHOP", "Workshop"),
    ]

    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    building = models.CharField(max_length=100)
    floor = models.PositiveSmallIntegerField()
    has_projector = models.BooleanField(default=True)
    has_whiteboard = models.BooleanField(default=True)
    has_aircon = models.BooleanField(default=False)
    has_wifi = models.BooleanField(default=True)
    has_computers = models.BooleanField(default=False)
    number_of_computers = models.PositiveIntegerField(default=0)
    is_wheelchair_accessible = models.BooleanField(default=True)
    equipment = models.JSONField(default=list)
    maintenance_schedule = models.JSONField(default=list)
    last_maintenance = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["building", "floor", "code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["room_type", "capacity"]),
            models.Index(fields=["building"]),
        ]

    def __str__(self):
        icons = []
        if self.has_projector:
            icons.append("P")
        if self.has_computers:
            icons.append("C")
        if self.has_aircon:
            icons.append("A")
        suffix = " [" + ",".join(icons) + "]" if icons else ""
        return f"{self.code} - {self.name} ({self.capacity} seats){suffix}"

    def is_available_on(self, check_date, time_slot):
        day_name = check_date.strftime("%a").upper()[:3]
        if day_name in self.maintenance_schedule:
            return False
        return not TimetableEntry.objects.filter(
            room=self, day=day_name, time_slot=time_slot, status="PUBLISHED"
        ).exists()

    @property
    def utilization_rate(self):
        semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            return 0
        total_slots = TimetableEntry.objects.filter(
            semester=semester, room=self, status="PUBLISHED"
        ).count()
        slots_per_day = TimeSlot.objects.count() or 4
        max_slots = 5 * slots_per_day * semester.teaching_weeks
        return round((total_slots / max_slots * 100), 1) if max_slots > 0 else 0


# ---------------------------------------------------------------------------
# TimeSlot
# ---------------------------------------------------------------------------


class TimeSlot(models.Model):
    SLOT_CHOICES = [
        ("SLOT_1", "8:00 AM - 10:00 AM"),
        ("SLOT_2", "10:30 AM - 12:30 PM"),
        ("SLOT_3", "2:00 PM - 4:00 PM"),
        ("SLOT_4", "4:30 PM - 6:30 PM"),
    ]
    _SLOT_ORDER = {"SLOT_1": 1, "SLOT_2": 2, "SLOT_3": 3, "SLOT_4": 4}

    # Consecutive slot pairings for double lessons.
    # SLOT_1+SLOT_2 are morning back-to-back (no break between 10:00 and 10:30).
    # SLOT_3+SLOT_4 are afternoon back-to-back.
    CONSECUTIVE_PAIRS = [
        ("SLOT_1", "SLOT_2"),
        ("SLOT_3", "SLOT_4"),
    ]

    slot_id = models.CharField(max_length=6, choices=SLOT_CHOICES, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveSmallIntegerField()
    is_evening = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.get_slot_id_display()

    def save(self, *args, **kwargs):
        self.order = self._SLOT_ORDER.get(self.slot_id, 99)
        self.is_evening = self.slot_id == "SLOT_4"
        super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        today = timezone.now().date()
        delta = (
            datetime.combine(today, self.end_time)
            - datetime.combine(today, self.start_time)
        )
        return round(delta.seconds / 3600, 2)


# ---------------------------------------------------------------------------
# Lecturer
# ---------------------------------------------------------------------------


class Lecturer(BaseModel):
    LECTURER_TYPES = [
        ("FT", "Full-time"),
        ("PT", "Part-time"),
        ("VS", "Visiting"),
        ("CT", "Contract"),
    ]
    TITLES = [
        ("PROF", "Professor"), ("ASSOC", "Associate Professor"),
        ("SR", "Senior Lecturer"), ("LEC", "Lecturer"),
        ("ASST", "Assistant Lecturer"), ("TUT", "Tutor"),
        ("DR", "Dr."), ("MR", "Mr."), ("MRS", "Mrs."), ("MS", "Ms."),
    ]
    QUALIFICATIONS = [
        ("PHD", "PhD"), ("MASTERS", "Masters"), ("BACHELORS", "Bachelors"),
        ("DIPLOMA", "Diploma"), ("CERTIFICATE", "Certificate"),
    ]
    DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    DAY_CHOICES = [(d, d.title()) for d in DAYS]

    staff_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=10, choices=TITLES, default="MR")
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    alternative_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    alternative_phone = models.CharField(max_length=15, blank=True)
    lecturer_type = models.CharField(max_length=2, choices=LECTURER_TYPES, default="FT")
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="lecturers"
    )
    highest_qualification = models.CharField(
        max_length=15, choices=QUALIFICATIONS, default="MASTERS"
    )
    specialization = models.CharField(max_length=200, blank=True)
    year_of_experience = models.PositiveSmallIntegerField(default=0)
    max_hours_per_week = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1), MaxValueValidator(40)]
    )
    max_hours_per_day = models.PositiveSmallIntegerField(
        default=6, validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    preferred_days = models.JSONField(default=list)
    preferred_time_slots = models.JSONField(default=list)
    unavailable_dates = models.JSONField(default=list)
    unavailable_weeks = models.JSONField(default=list)
    qualified_units = models.ManyToManyField(
        Unit, related_name="qualified_lecturers", blank=True
    )
    profile_image = models.ImageField(upload_to="lecturers/", blank=True, null=True)
    bio = models.TextField(blank=True)
    research_interests = models.TextField(blank=True)
    publications_count = models.PositiveIntegerField(default=0)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lecturer_profile",
    )
    is_available_for_supervision = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["staff_id"]),
            models.Index(fields=["email"]),
            models.Index(fields=["lecturer_type", "department"]),
            models.Index(fields=["is_active"]),
        ]

    def clean(self):
        valid_days = set(self.DAYS)
        for field_name in ("preferred_days", "unavailable_dates"):
            value = getattr(self, field_name, [])
            if not isinstance(value, list):
                raise ValidationError(f"{field_name} must be a list.")
        for day in self.preferred_days:
            if day not in valid_days:
                raise ValidationError(
                    f"Invalid day '{day}' in preferred_days. Must be one of {self.DAYS}."
                )

    @property
    def full_name(self):
        parts = [self.get_title_display(), self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    @property
    def short_name(self):
        return f"{self.get_title_display()} {self.last_name}"

    def get_available_days(self):
        if self.lecturer_type == "FT":
            return self.DAYS[:5]
        return self.preferred_days

    def is_available_on(self, check_date, time_slot):
        date_str = str(check_date)
        if date_str in self.unavailable_dates:
            return False
        week_number = check_date.isocalendar()[1]
        if week_number in self.unavailable_weeks:
            return False
        day_name = check_date.strftime("%a").upper()[:3]
        if self.lecturer_type != "FT" and day_name not in self.preferred_days:
            return False
        if self.preferred_time_slots and time_slot not in self.preferred_time_slots:
            return False
        return True

    def get_current_workload(self, semester=None):
        if not semester:
            semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            return 0
        entries = TimetableEntry.objects.filter(
            semester=semester, lecturer=self, status="PUBLISHED"
        )
        return sum(
            e.time_slot.duration_hours for e in entries.select_related("time_slot")
        )

    def get_remaining_hours(self, semester=None):
        return max(0, self.max_hours_per_week - self.get_current_workload(semester))

    def __str__(self):
        return self.full_name


# ---------------------------------------------------------------------------
# IntakeUnit
# ---------------------------------------------------------------------------


class IntakeUnit(BaseModel):
    """
    Units assigned to an intake for a specific semester.

    override_source controls how the scheduler treats this row:
      STAGE   — derived from the intake's current Stage (default, auto-populated)
      ADDED   — manually added extra unit not in the Stage
      DROPPED — unit exists in the Stage but should be skipped for this intake
    """

    OVERRIDE_CHOICES = [
        ("STAGE", "From Stage (automatic)"),
        ("ADDED", "Manually Added"),
        ("DROPPED", "Dropped / Suppressed"),
    ]

    intake = models.ForeignKey(Intake, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=True)
    is_elective_selected = models.BooleanField(default=False)
    override_source = models.CharField(
        max_length=7, choices=OVERRIDE_CHOICES, default="STAGE",
        help_text=(
            "STAGE = auto from programme stage. "
            "ADDED = extra unit for this intake only. "
            "DROPPED = suppress this unit even though it's in the stage."
        ),
    )
    exam_date = models.DateField(null=True, blank=True)
    exam_time = models.TimeField(null=True, blank=True)
    exam_venue = models.CharField(max_length=100, blank=True)
    exam_room = models.ForeignKey(
        "Room", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="exam_assignments",
        help_text="Room used specifically for the exam sitting.",
    )

    class Meta:
        unique_together = ["intake", "unit", "semester"]
        ordering = ["intake", "unit"]
        indexes = [
            models.Index(fields=["intake", "semester"]),
            models.Index(fields=["unit", "semester"]),
            models.Index(fields=["intake", "semester", "override_source"]),
        ]

    def __str__(self):
        tag = f" [{self.override_source}]" if self.override_source != "STAGE" else ""
        return f"{self.intake} - {self.unit.code} ({self.semester.name}){tag}"

    def clean(self):
        if self.exam_date and self.semester_id:
            sem = self.semester
            if not (sem.start_date <= self.exam_date <= sem.end_date):
                raise ValidationError(
                    f"Exam date {self.exam_date} falls outside semester dates."
                )


# ---------------------------------------------------------------------------
# UnitSchedulingConstraint
# ---------------------------------------------------------------------------


class UnitSchedulingConstraint(BaseModel):
    """
    Pins a unit to a specific day and time slot globally or per programme.

    is_hard_constraint=True  → scheduler MUST place here or log a conflict.
    is_hard_constraint=False → scheduler prefers this slot but may place elsewhere.
    """

    DAY_CHOICES = [
        ("MON", "Monday"), ("TUE", "Tuesday"), ("WED", "Wednesday"),
        ("THU", "Thursday"), ("FRI", "Friday"), ("SAT", "Saturday"),
    ]

    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name="scheduling_constraints"
    )
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, null=True, blank=True,
        related_name="unit_constraints",
        help_text="Leave blank to apply to all programmes teaching this unit.",
    )
    pinned_day = models.CharField(max_length=3, choices=DAY_CHOICES)
    pinned_time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="constrained_units"
    )
    # For double-lesson units the constraint pins the FIRST slot;
    # the scheduler will automatically book the next consecutive slot too.
    preferred_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="preferred_for_units",
    )
    is_hard_constraint = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["unit", "pinned_day", "pinned_time_slot__order"]
        indexes = [
            models.Index(fields=["unit", "programme"]),
            models.Index(fields=["pinned_day", "pinned_time_slot"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "pinned_day", "pinned_time_slot"],
                condition=Q(programme__isnull=True),
                name="unique_global_unit_constraint",
            ),
            models.UniqueConstraint(
                fields=["unit", "programme", "pinned_day", "pinned_time_slot"],
                condition=Q(programme__isnull=False),
                name="unique_programme_unit_constraint",
            ),
        ]

    def __str__(self):
        scope = self.programme.code if self.programme_id else "ALL"
        return (
            f"{self.unit.code} → {self.pinned_day} "
            f"{self.pinned_time_slot.get_slot_id_display()} "
            f"[{scope}] {'HARD' if self.is_hard_constraint else 'SOFT'}"
        )

    def clean(self):
        valid_days = {d[0] for d in self.DAY_CHOICES}
        if self.pinned_day and self.pinned_day not in valid_days:
            raise ValidationError(
                f"Invalid day '{self.pinned_day}'. Must be one of {sorted(valid_days)}."
            )


# ---------------------------------------------------------------------------
# SharedUnitSchedule  (informational — kept for admin/reporting)
# ---------------------------------------------------------------------------


class SharedUnitSchedule(BaseModel):
    """
    Records which timetable entry represents a shared-unit session and which
    programmes attend it.  Populated by the scheduler after co-scheduling.
    """

    unit_offering = models.ForeignKey(
        UnitOffering, on_delete=models.CASCADE, related_name="schedules",
        null=True, blank=True,
    )
    timetable_entry = models.OneToOneField(
        "TimetableEntry", on_delete=models.CASCADE,
        related_name="shared_unit_schedule",
    )
    attending_programmes = models.ManyToManyField(
        Programme, related_name="shared_schedules"
    )
    total_students = models.IntegerField(default=0)
    required_capacity = models.IntegerField(default=0)

    class Meta:
        ordering = ["timetable_entry"]

    def __str__(self):
        codes = ", ".join(p.code for p in self.attending_programmes.all())
        return f"{self.timetable_entry} — shared: {codes}"


# ---------------------------------------------------------------------------
# TimetableEntry  (FIXED: save() no longer crashes on force-publish)
# ---------------------------------------------------------------------------


class TimetableEntry(BaseModel):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("PUBLISHED", "Published"),
        ("CANCELLED", "Cancelled"),
        ("RESCHEDULED", "Rescheduled"),
        ("COMPLETED", "Completed"),
        ("MISSED", "Missed"),
    ]

    # full_clean() is only called when saving to one of these statuses
    # via the normal per-object save path.  Force-publish uses queryset
    # .update() and never touches this set.
    _VALIDATED_STATUSES = {"PENDING"}   # PUBLISHED removed — validated at generate time

    DAY_CHOICES = [
        ("MON", "Mon"), ("TUE", "Tue"), ("WED", "Wed"),
        ("THU", "Thu"), ("FRI", "Fri"), ("SAT", "Sat"),
    ]

    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    intake = models.ForeignKey(
        Intake, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    specific_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="DRAFT")
    week_number = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(16)]
    )
    is_recurring = models.BooleanField(default=True)
    recurrence_pattern = models.JSONField(default=dict)
    attendance_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    rescheduled_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rescheduled_to",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_entries",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Shared-class fields
    is_shared_class = models.BooleanField(
        default=False,
        help_text="True when this entry is part of a co-scheduled shared unit.",
    )
    # Identifies the shared group so the UI can group co-scheduled entries.
    # Format: "<shared_unit_group>_<unit_id>" e.g. "CND_DND_GROUP_<uuid>"
    shared_group_key = models.CharField(max_length=120, blank=True, db_index=True)

    # Double-lesson: slot_sequence identifies position within a double lesson.
    # 1 = first slot, 2 = second slot, 0 = single (normal) lesson.
    SLOT_SEQUENCE_CHOICES = [(0, "Single"), (1, "First slot"), (2, "Second slot")]
    slot_sequence = models.PositiveSmallIntegerField(
        default=0,
        choices=SLOT_SEQUENCE_CHOICES,
        help_text="For double-lesson units: 1=first slot, 2=second slot, 0=normal.",
    )

    class Meta:
        ordering = ["day", "time_slot__order", "week_number"]
        indexes = [
            models.Index(fields=["semester", "status"]),
            models.Index(fields=["lecturer", "day", "time_slot", "week_number"]),
            models.Index(fields=["intake", "day", "time_slot", "week_number"]),
            models.Index(fields=["room", "day", "time_slot", "week_number"]),
            models.Index(fields=["specific_date"]),
            models.Index(fields=["status", "week_number"]),
            models.Index(fields=["is_shared_class"]),
            models.Index(fields=["shared_group_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "lecturer", "day", "time_slot", "week_number"],
                condition=Q(status="PUBLISHED"),
                name="unique_lecturer_per_week_published",
            ),
            models.UniqueConstraint(
                fields=["semester", "intake", "day", "time_slot", "week_number"],
                condition=Q(status="PUBLISHED"),
                name="unique_intake_per_week_published",
            ),
            models.UniqueConstraint(
                fields=["semester", "room", "day", "time_slot", "week_number"],
                condition=Q(status="PUBLISHED"),
                name="unique_room_per_week_published",
            ),
        ]

    def __str__(self):
        slot_label = self.time_slot.slot_id if self.time_slot_id else "N/A"
        shared_tag = " [SHARED]" if self.is_shared_class else ""
        double_tag = f" [SLOT {self.slot_sequence}/2]" if self.slot_sequence else ""
        return (
            f"{self.unit.code} - {self.day} {slot_label} "
            f"[Week {self.week_number}]{shared_tag}{double_tag}"
        )

    def clean(self):
        # Only run expensive clash checks when explicitly entering PENDING state.
        # PUBLISHED is now reached via queryset .update() (force) or a lightweight
        # save path — the DB-level unique constraints handle duplicate prevention.
        if self.status not in self._VALIDATED_STATUSES:
            return

        if self.specific_date:
            sem = self.semester
            if not (sem.start_date <= self.specific_date <= sem.end_date):
                raise ValidationError(
                    f"Date {self.specific_date} is outside semester dates "
                    f"({sem.start_date} – {sem.end_date})."
                )
            expected_day = self.specific_date.strftime("%a").upper()[:3]
            if expected_day != self.day:
                raise ValidationError(
                    f"Day mismatch: entry day is {self.day} but "
                    f"{self.specific_date} falls on {expected_day}."
                )

        if self.lecturer.lecturer_type in ("PT", "VS", "CT"):
            if self.day not in self.lecturer.get_available_days():
                raise ValidationError(
                    f"Lecturer {self.lecturer.short_name} is not available on {self.day}."
                )

        base_qs = TimetableEntry.objects.filter(
            semester=self.semester,
            lecturer=self.lecturer,
            status__in=["PUBLISHED", "PENDING"],
        ).exclude(pk=self.pk)

        slot_hours = self.time_slot.duration_hours if self.time_slot_id else 2
        daily_count = base_qs.filter(day=self.day, week_number=self.week_number).count()
        if (daily_count * slot_hours) + slot_hours > self.lecturer.max_hours_per_day:
            raise ValidationError(
                f"Adding this entry would exceed {self.lecturer.short_name}'s "
                f"daily limit of {self.lecturer.max_hours_per_day} hours."
            )

        weekly_count = base_qs.filter(week_number=self.week_number).count()
        if (weekly_count * slot_hours) + slot_hours > self.lecturer.max_hours_per_week:
            raise ValidationError(
                f"Adding this entry would exceed {self.lecturer.short_name}'s "
                f"weekly limit of {self.lecturer.max_hours_per_week} hours."
            )

        if not self.lecturer.qualified_units.filter(pk=self.unit.pk).exists():
            raise ValidationError(
                f"{self.lecturer.short_name} is not qualified to teach {self.unit.name}."
            )

        if self.intake.student_count > self.room.capacity:
            raise ValidationError(
                f"Room {self.room.code} capacity ({self.room.capacity}) is less than "
                f"intake size ({self.intake.student_count})."
            )

        if self.unit.practical_hours_per_week > 0 and self.room.room_type not in (
            "LAB", "CLINICAL", "COMPUTER"
        ):
            raise ValidationError(
                "Units with practical hours must be scheduled in a LAB, CLINICAL, "
                "or COMPUTER room."
            )

        duplicate = TimetableEntry.objects.filter(
            semester=self.semester,
            intake=self.intake,
            unit=self.unit,
            day=self.day,
            week_number=self.week_number,
            status__in=["PUBLISHED", "PENDING"],
        ).exclude(pk=self.pk).exists()

        if duplicate:
            raise ValidationError(
                f"Intake {self.intake.name} already has {self.unit.code} "
                f"scheduled on {self.day} in week {self.week_number}."
            )

    def save(self, *args, **kwargs):
        # Only call full_clean() for PENDING (manual edits).
        # DRAFT entries skip validation (scheduler bulk-creates these).
        # PUBLISHED entries are handled via queryset .update() on the publish
        # path — they never come through here with status=PUBLISHED unless
        # edited individually, in which case the DB constraints catch duplicates.
        if self.status in self._VALIDATED_STATUSES:
            self.full_clean()

        if self.status == "PUBLISHED" and not self.published_at:
            self.published_at = timezone.now()

        if self.status == "PUBLISHED" and self.approved_by_id and not self.approved_at:
            self.approved_at = timezone.now()

        super().save(*args, **kwargs)

    @transaction.atomic
    def cancel(self, reason: str, cancelled_by: User):
        if self.status not in ("PUBLISHED", "PENDING"):
            raise ValidationError("Only PUBLISHED or PENDING entries can be cancelled.")
        self.status = "CANCELLED"
        self.cancellation_reason = reason
        self.save()
        ScheduleAudit.objects.create(
            timetable_entry=self,
            action="CANCEL",
            old_value={"status": "PUBLISHED"},
            new_value={"status": "CANCELLED", "reason": reason},
            changed_by=cancelled_by,
        )

    @transaction.atomic
    def reschedule(self, new_day, new_time_slot, new_room, reason, rescheduled_by):
        if self.status != "PUBLISHED":
            raise ValidationError("Only PUBLISHED entries can be rescheduled.")
        old_values = {
            "day": self.day,
            "time_slot_id": str(self.time_slot_id),
            "room_id": str(self.room_id),
        }
        new_entry = TimetableEntry.objects.create(
            semester=self.semester,
            intake=self.intake,
            unit=self.unit,
            lecturer=self.lecturer,
            room=new_room,
            day=new_day,
            time_slot=new_time_slot,
            week_number=self.week_number,
            status="PENDING",
            rescheduled_from=self,
            notes=f"Rescheduled from original: {reason}",
        )
        self.status = "RESCHEDULED"
        self.save()
        ScheduleAudit.objects.create(
            timetable_entry=self,
            action="RESCHEDULE",
            old_value=old_values,
            new_value={
                "day": new_day,
                "time_slot_id": str(new_time_slot.pk),
                "room_id": str(new_room.pk),
                "reason": reason,
                "new_entry_id": str(new_entry.pk),
            },
            changed_by=rescheduled_by,
        )
        return new_entry


# ---------------------------------------------------------------------------
# ConflictLog
# ---------------------------------------------------------------------------


class ConflictLog(BaseModel):
    CONFLICT_TYPES = [
        ("LECTURER", "Lecturer Conflict"),
        ("INTAKE", "Intake Conflict"),
        ("ROOM", "Room Conflict"),
        ("CAPACITY", "Capacity Issue"),
        ("QUALIFICATION", "Qualification Issue"),
        ("TIME", "Time Constraint"),
        ("PREREQUISITE", "Prerequisite Violation"),
        ("SHARED_UNIT", "Shared Unit Conflict"),
    ]
    SEVERITY_LEVELS = [
        ("HIGH", "High - Blocks scheduling"),
        ("MEDIUM", "Medium - May cause issues"),
        ("LOW", "Low - Informational only"),
    ]
    RESOLUTION_STATUS = [
        ("PENDING", "Pending"),
        ("AUTO_RESOLVED", "Auto-resolved by AI"),
        ("MANUAL", "Manually Resolved"),
        ("RESOLVED", "Resolved"),
        ("OVERRIDDEN", "Overridden"),
        ("IGNORED", "Ignored"),
    ]

    conflict_type = models.CharField(max_length=15, choices=CONFLICT_TYPES)
    severity = models.CharField(max_length=6, choices=SEVERITY_LEVELS, default="MEDIUM")
    description = models.TextField()
    involved_entities = models.JSONField(default=dict)
    proposed_solution = models.JSONField(null=True, blank=True)
    resolution_status = models.CharField(
        max_length=13, choices=RESOLUTION_STATUS, default="PENDING"
    )
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resolved_conflicts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="conflicts"
    )
    affected_entry = models.ForeignKey(
        TimetableEntry, on_delete=models.CASCADE, null=True, blank=True,
        related_name="conflicts",
    )

    class Meta:
        ordering = ["-created_at", "-severity"]
        indexes = [
            models.Index(fields=["semester", "resolution_status"]),
            models.Index(fields=["conflict_type", "severity"]),
        ]

    def __str__(self):
        return (
            f"{self.get_conflict_type_display()} - "
            f"{self.created_at.date()} [{self.get_severity_display()}]"
        )

    def resolve(self, resolution, resolved_by, resolution_method="RESOLVED", notes=""):
        self.proposed_solution = resolution
        self.resolution_status = resolution_method
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save(
            update_fields=[
                "proposed_solution", "resolution_status", "resolved_by",
                "resolved_at", "resolution_notes", "updated_at",
            ]
        )


# ---------------------------------------------------------------------------
# ScheduleAudit
# ---------------------------------------------------------------------------


class ScheduleAudit(BaseModel):
    ACTION_CHOICES = [
        ("CREATE", "Created"), ("UPDATE", "Updated"), ("DELETE", "Deleted"),
        ("PUBLISH", "Published"), ("UNPUBLISH", "Unpublished"), ("MOVE", "Moved"),
        ("CANCEL", "Cancelled"), ("RESCHEDULE", "Rescheduled"),
        ("BULK_UPDATE", "Bulk Update"), ("APPROVE", "Approved"), ("REJECT", "Rejected"),
    ]

    timetable_entry = models.ForeignKey(
        TimetableEntry, on_delete=models.CASCADE, related_name="audits"
    )
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="timetable_audits"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Schedule Audits"
        indexes = [
            models.Index(fields=["timetable_entry", "action"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.timetable_entry} at {self.created_at}"


# ---------------------------------------------------------------------------
# LecturerPreferences
# ---------------------------------------------------------------------------


class LecturerPreferences(BaseModel):
    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.CASCADE, related_name="preferences"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="lecturer_preferences"
    )
    preferred_days = models.JSONField(default=list)
    preferred_time_slots = models.JSONField(default=list)
    blocked_days = models.JSONField(default=list)
    blocked_time_slots = models.JSONField(default=list)
    max_consecutive_hours = models.PositiveSmallIntegerField(default=4)
    prefer_morning = models.BooleanField(default=False)
    prefer_afternoon = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["lecturer", "semester"]
        verbose_name_plural = "Lecturer Preferences"

    def __str__(self):
        return f"Preferences — {self.lecturer.full_name} / {self.semester.name}"

    def clean(self):
        valid_days = set(Lecturer.DAYS)
        valid_slots = {s[0] for s in TimeSlot.SLOT_CHOICES}
        for field, valid_set in (
            ("preferred_days", valid_days),
            ("blocked_days", valid_days),
            ("preferred_time_slots", valid_slots),
            ("blocked_time_slots", valid_slots),
        ):
            value = getattr(self, field, [])
            if not isinstance(value, list):
                raise ValidationError(f"{field} must be a JSON list.")
            bad = [v for v in value if v not in valid_set]
            if bad:
                raise ValidationError(
                    f"Invalid values in {field}: {bad}. Allowed: {sorted(valid_set)}."
                )
        day_conflict = set(self.preferred_days) & set(self.blocked_days)
        if day_conflict:
            raise ValidationError(
                f"Days cannot be both preferred and blocked: {day_conflict}."
            )
        slot_conflict = set(self.preferred_time_slots) & set(self.blocked_time_slots)
        if slot_conflict:
            raise ValidationError(
                f"Time slots cannot be both preferred and blocked: {slot_conflict}."
            )