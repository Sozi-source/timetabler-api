"""
timetable/models.py
===================
Industry-standard timetabling system.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class TimeStampedModel(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CurriculumUnit(TimeStampedModel):
    UNIT_TYPE_CHOICES = [
        ("CORE",      "Core"),
        ("ELECTIVE",  "Elective"),
        ("PRACTICAL", "Practical"),
        ("PROJECT",   "Project"),
    ]

    programme          = models.ForeignKey("Programme", on_delete=models.CASCADE,
                                           related_name="curriculum_units")
    term_number        = models.PositiveSmallIntegerField()
    position           = models.PositiveSmallIntegerField(default=1)
    code               = models.CharField(max_length=30)
    name               = models.CharField(max_length=200)
    unit_type          = models.CharField(max_length=10, choices=UNIT_TYPE_CHOICES, default="CORE")
    credit_hours       = models.PositiveSmallIntegerField(default=3)
    periods_per_week   = models.PositiveSmallIntegerField(default=1)
    SESSION_PATTERN_CHOICES = [
        ("SPLIT", "Split — one session per day across multiple days"),
        ("BLOCK", "Block — consecutive periods on the same day"),
    ]
    session_pattern    = models.CharField(
        max_length=5,
        choices=SESSION_PATTERN_CHOICES,
        default="SPLIT",
        help_text="SPLIT = one session per day; BLOCK = consecutive double period",
    )
    is_outsourced      = models.BooleanField(
        default=False,
        help_text="Unit is taught by an external/outsourced trainer",
    )
    is_active          = models.BooleanField(default=True)
    notes              = models.TextField(blank=True)

    class Meta:
        abstract = False
