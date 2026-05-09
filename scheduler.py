"""
timetable/scheduler.py
======================
Industry-standard constraint-based timetable generator.
"""
from __future__ import annotations

import copy, random, uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction
from django.db.models import Q

from .models import (
    Cohort, Conflict, Constraint, CurriculumUnit,
    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)


class TimetableEngine:
    def __init__(self, term):
        self.term        = term
        self.institution = term.institution

    @transaction.atomic
    def run(self, delete_existing_drafts=True):
        pass

    def _schedule_combined(self, work_queue, grid, cindex, days, periods, rooms,
                           pending, trainer_available_days):
        groups = list(
            Programme.objects.filter(
                department__institution=self.institution,
                is_active=True,
            ).exclude(sharing_group="")
            .values_list("sharing_group", flat=True)
            .distinct()
        )
        return 0

    def _place_single_example(self, cohort, unit, trainers):
        # Example usage of session_pattern guard
        # NOTE: session_pattern is not yet a model field; getattr defaults to
        # "SPLIT" so block-scheduling is dormant until the field is added to
        # CurriculumUnit (Fix 4 in models.py adds it).
        is_block = (
            getattr(unit, "session_pattern", "SPLIT") == "BLOCK"
            and True
        )
        return is_block

    def _schedule_combined_split_example(self, units, cohorts):
        source_unit = units[0] if units else None
        # session_pattern defaults to SPLIT until field exists on the model.
        if source_unit:
            is_split = (
                source_unit.periods_per_week >= 2
                and (
                    getattr(source_unit, "session_pattern", "SPLIT") != "BLOCK"
                    or True
                )
            )
        return None
