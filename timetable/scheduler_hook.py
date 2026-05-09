"""
timetable/scheduler_hook.py
============================
Drop-in helper that makes TimetableEngine read TermTrainerAssignment
before falling back to the qualified_trainers pool.

HOW TO USE
----------
In your scheduler.py, wherever you currently pick a trainer for a unit,
replace the existing trainer-selection logic with a call to resolve_trainer().

Example — inside TimetableEngine.run() or _schedule_unit():

    from .scheduler_hook import resolve_trainer

    trainer = resolve_trainer(
        term=self.term,
        cohort=cohort,
        unit=unit,
        fallback_pool=list(unit.qualified_trainers.filter(is_active=True)),
    )
    if trainer is None:
        # log conflict: no trainer available
        ...

resolve_trainer() returns a Trainer instance or None.
"""

from __future__ import annotations
from typing import Optional

from .models import Trainer, CurriculumUnit, Cohort, Term, TermTrainerAssignment


def resolve_trainer(
    term: Term,
    cohort: Cohort,
    unit: CurriculumUnit,
    fallback_pool: list[Trainer],
) -> Optional[Trainer]:
    """
    Return the trainer who should teach `unit` for `cohort` in `term`.

    Priority order:
      1. Explicit TermTrainerAssignment for this (term, cohort, unit)
      2. First trainer in `fallback_pool` (the qualified_trainers pool)
      3. None — caller must log a conflict

    Args:
        term:          The college Term being scheduled.
        cohort:        The Cohort being scheduled.
        unit:          The CurriculumUnit to be taught.
        fallback_pool: Pre-fetched list of active qualified trainers for this
                       unit. Pass an empty list if none are qualified.

    Returns:
        A Trainer instance, or None if no trainer can be found.
    """
    # 1. Check for an explicit term-specific assignment
    try:
        assignment = TermTrainerAssignment.objects.select_related("trainer").get(
            term=term,
            cohort=cohort,
            curriculum_unit=unit,
        )
        trainer = assignment.trainer
        # Confirm the assigned trainer is still active
        if trainer.is_active:
            return trainer
        # Assigned trainer is inactive — fall through to pool
    except TermTrainerAssignment.DoesNotExist:
        pass

    # 2. Fall back to qualified_trainers pool (pass the already-loaded list
    #    to avoid an extra DB query)
    if fallback_pool:
        return fallback_pool[0]

    # 3. No trainer available
    return None


def build_assignment_map(term: Term) -> dict[tuple, Trainer]:
    """
    Pre-load all TermTrainerAssignments for a term into a fast lookup dict.

    Use this at the START of TimetableEngine.run() to avoid N+1 queries
    during generation:

        from .scheduler_hook import build_assignment_map
        self._assignment_map = build_assignment_map(self.term)

    Then in _schedule_unit():
        key = (str(cohort.id), str(unit.id))
        trainer = self._assignment_map.get(key) or fallback_pool[0]

    Returns:
        dict mapping (str(cohort_id), str(curriculum_unit_id)) → Trainer
    """
    assignments = (
        TermTrainerAssignment.objects
        .filter(term=term, trainer__is_active=True)
        .select_related("trainer")
    )
    return {
        (str(a.cohort_id), str(a.curriculum_unit_id)): a.trainer
        for a in assignments
    }