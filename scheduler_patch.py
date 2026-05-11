"""
PATCH — make the scheduler honour TermTrainerAssignment
=======================================================

Apply these three changes to timetable/scheduler.py.

CHANGE 1 — Add TermTrainerAssignment to the import block
---------------------------------------------------------
Find the existing import block (around line 14–22):

    from .models import (
        Cohort, Conflict, Constraint, CurriculumUnit,
        Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
    )

Replace with:

    from .models import (
        Cohort, Conflict, Constraint, CurriculumUnit,
        Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
        TermTrainerAssignment,
    )


CHANGE 2 — Build a term-assignment lookup in TimetableEngine.run()
------------------------------------------------------------------
Find this block in run() (just after grid and cindex are built, Step 3 comment):

    result = GenerationResult(term=self.term, total_required=total_required)

    # ── Step 3: schedule COMBINED sessions (shared classes) ───────────

Add the lookup BETWEEN those two lines so it reads:

    result = GenerationResult(term=self.term, total_required=total_required)

    # ── Term-specific trainer override lookup ─────────────────────────
    # Key: (cohort_id_str, curriculum_unit_id_str) → [Trainer, ...]
    # If a TermTrainerAssignment exists for this cohort+unit+term, that
    # specific trainer is used instead of the full qualified_trainers pool.
    term_assignments: dict[tuple[str, str], list[Trainer]] = {}
    for tta in TermTrainerAssignment.objects.filter(
        term=self.term,
        trainer__is_active=True,
    ).select_related("trainer"):
        key = (str(tta.cohort_id), str(tta.curriculum_unit_id))
        term_assignments[key] = [tta.trainer]

    # ── Step 3: schedule COMBINED sessions (shared classes) ───────────


CHANGE 3 — Use the lookup at both trainer-resolution call sites
---------------------------------------------------------------
There are two places in run() where qualified trainers are fetched.
Replace BOTH of them.

--- CALL SITE A: just before no_trainer_units pre-check (around "Step 4" area) ---

Find:
    for cohort_id, unit_list in remaining:
        cohort, _ = work_queue[cohort_id]
        viable   = []
        for unit in unit_list:
            qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
            if not qualified and not getattr(unit, "is_outsourced", False):
                no_trainer_units.append((cohort, unit))
                placed_keys.add(f"{cohort_id}_{unit.id}")   # prevent re-try
            else:
                viable.append(unit)
        if viable:
            units_needing_passes.append((cohort_id, viable))

Replace with:
    for cohort_id, unit_list in remaining:
        cohort, _ = work_queue[cohort_id]
        viable   = []
        for unit in unit_list:
            ta_key    = (cohort_id, str(unit.id))
            qualified = term_assignments.get(ta_key) or [
                t for t in unit.qualified_trainers.all() if t.is_active
            ]
            if not qualified and not getattr(unit, "is_outsourced", False):
                no_trainer_units.append((cohort, unit))
                placed_keys.add(f"{cohort_id}_{unit.id}")
            else:
                viable.append(unit)
        if viable:
            units_needing_passes.append((cohort_id, viable))

--- CALL SITE B: inside the pass loop (Steps 5-7) ---

Find:
    for unit in unit_list:
        key = f"{cohort_id}_{unit.id}"
        if key in placed_keys:
            continue

        qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
        pr        = placer.place(cohort, unit, qualified)

Replace with:
    for unit in unit_list:
        key = f"{cohort_id}_{unit.id}"
        if key in placed_keys:
            continue

        ta_key    = (cohort_id, str(unit.id))
        qualified = term_assignments.get(ta_key) or [
            t for t in unit.qualified_trainers.all() if t.is_active
        ]
        pr = placer.place(cohort, unit, qualified)


WHY THIS WORKS
--------------
term_assignments is keyed by (cohort_id, curriculum_unit_id) — the exact
pairing that TermTrainerAssignment uses (with a unique constraint on
term + cohort + curriculum_unit).  When a specific assignment exists,
only that trainer is put in the `qualified` list the Placer receives, so
the Placer's load-balancing loop has only one candidate and must pick them.
When no assignment exists the original fallback (all active qualified
trainers) is used unchanged — zero regression for unassigned units.

The combined-session path (_schedule_combined) already resolves trainers
from the intersection of qualified sets; TermTrainerAssignment only applies
to individual cohort placements, which is correct — a combined session
might serve cohorts with different per-cohort assignments, so letting the
combiner use the shared pool and letting the individual passes honour
assignments is the right split.
"""
