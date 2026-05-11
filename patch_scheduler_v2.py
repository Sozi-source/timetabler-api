"""
patch_scheduler_v2.py
Fixes combined session scheduling to also honour TermTrainerAssignment.
Run with: python patch_scheduler_v2.py
"""
import shutil, sys
from pathlib import Path

target = Path("timetable/scheduler.py")
if not target.exists():
    sys.exit(f"ERROR: {target} not found. Run from your project root.")

shutil.copy(target, target.with_suffix(".py.bak2"))
print(f"Backup saved to {target.with_suffix('.py.bak2')}")

src = target.read_text(encoding="utf-8")
original_has_crlf = "\r\n" in src
src = src.replace("\r\n", "\n")

changes = 0

# ── Change 1 ─────────────────────────────────────────────────────────────────
# Pass term_assignments into _schedule_combined so it can honour them.
# Find the call to _schedule_combined inside run() and add term_assignments arg.

old1 = (
    "        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────\n"
    "        combined_placed = self._schedule_combined(\n"
    "            work_queue, grid, cindex, days, periods, rooms,\n"
    "            pending, trainer_available_days,\n"
    "        )"
)
new1 = (
    "        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────\n"
    "        combined_placed = self._schedule_combined(\n"
    "            work_queue, grid, cindex, days, periods, rooms,\n"
    "            pending, trainer_available_days, term_assignments,\n"
    "        )"
)

if old1 in src:
    src = src.replace(old1, new1, 1)
    print("[OK] Change 1: term_assignments passed into _schedule_combined call")
    changes += 1
else:
    print("WARN Change 1 not matched")

# ── Change 2 ─────────────────────────────────────────────────────────────────
# Update _schedule_combined signature to accept term_assignments.

old2 = (
    "    def _schedule_combined(\n"
    "        self,\n"
    "        work_queue:             dict[str, tuple[Cohort, list[CurriculumUnit]]],\n"
    "        grid:                   OccupancyGrid,\n"
    "        cindex:                 ConstraintIndex,\n"
    "        days:                   list[str],\n"
    "        periods:                list[Period],\n"
    "        rooms:                  list[Room],\n"
    "        pending:                list[ScheduledUnit],\n"
    "        trainer_available_days: dict[str, Optional[set[str]]],\n"
    "    ) -> int:"
)
new2 = (
    "    def _schedule_combined(\n"
    "        self,\n"
    "        work_queue:             dict[str, tuple[Cohort, list[CurriculumUnit]]],\n"
    "        grid:                   OccupancyGrid,\n"
    "        cindex:                 ConstraintIndex,\n"
    "        days:                   list[str],\n"
    "        periods:                list[Period],\n"
    "        rooms:                  list[Room],\n"
    "        pending:                list[ScheduledUnit],\n"
    "        trainer_available_days: dict[str, Optional[set[str]]],\n"
    "        term_assignments:       dict[tuple[str, str], list[Trainer]] = None,\n"
    "    ) -> int:"
)

if old2 in src:
    src = src.replace(old2, new2, 1)
    print("[OK] Change 2: _schedule_combined signature updated")
    changes += 1
else:
    print("WARN Change 2 not matched")

# ── Change 3 ─────────────────────────────────────────────────────────────────
# Inside _schedule_combined, after building trainer_id_sets / common_ids,
# check term_assignments: if all cohorts in the combined group have the same
# assigned trainer for this unit, use that trainer instead of the pool.

old3 = (
    "                    # Find a trainer common to ALL cohorts' qualified sets\n"
    "                    trainer_id_sets = [\n"
    "                        {str(t.id) for t in u.qualified_trainers.all()}\n"
    "                        for u in cohort_unit_map.values()\n"
    "                    ]\n"
    "                    common_ids = set.intersection(*trainer_id_sets) if trainer_id_sets else set()\n"
    "                    if not common_ids:\n"
    "                        # Fall back to source unit's trainers\n"
    "                        source_unit = next(iter(cohort_unit_map.values()))\n"
    "                        common_ids  = {str(t.id) for t in source_unit.qualified_trainers.all()}\n"
    "\n"
    "                    qualified = list(\n"
    "                        Trainer.objects.filter(id__in=common_ids, is_active=True)\n"
    "                    )\n"
    "                    if not qualified:\n"
    "                        continue"
)
new3 = (
    "                    # Find a trainer common to ALL cohorts' qualified sets\n"
    "                    trainer_id_sets = [\n"
    "                        {str(t.id) for t in u.qualified_trainers.all()}\n"
    "                        for u in cohort_unit_map.values()\n"
    "                    ]\n"
    "                    common_ids = set.intersection(*trainer_id_sets) if trainer_id_sets else set()\n"
    "                    if not common_ids:\n"
    "                        # Fall back to source unit's trainers\n"
    "                        source_unit = next(iter(cohort_unit_map.values()))\n"
    "                        common_ids  = {str(t.id) for t in source_unit.qualified_trainers.all()}\n"
    "\n"
    "                    qualified = list(\n"
    "                        Trainer.objects.filter(id__in=common_ids, is_active=True)\n"
    "                    )\n"
    "                    if not qualified:\n"
    "                        continue\n"
    "\n"
    "                    # ── Honour TermTrainerAssignment for combined sessions ──\n"
    "                    # If every cohort in this group has the same assigned trainer\n"
    "                    # for this unit, move that trainer to the front of the list\n"
    "                    # so _place_combined_single/split picks them first.\n"
    "                    if term_assignments:\n"
    "                        assigned_ids = [\n"
    "                            term_assignments[(cid, str(cohort_unit_map[cid].id))][0].id\n"
    "                            for cid in cohort_unit_map\n"
    "                            if (cid, str(cohort_unit_map[cid].id)) in term_assignments\n"
    "                        ]\n"
    "                        if assigned_ids and len(set(str(i) for i in assigned_ids)) == 1:\n"
    "                            preferred_id = str(assigned_ids[0])\n"
    "                            qualified.sort(\n"
    "                                key=lambda t: (0 if str(t.id) == preferred_id else 1)\n"
    "                            )"
)

if old3 in src:
    src = src.replace(old3, new3, 1)
    print("[OK] Change 3: combined session prefers assigned trainer")
    changes += 1
else:
    print("WARN Change 3 not matched")

# Restore line endings
if original_has_crlf:
    src = src.replace("\n", "\r\n")

target.write_text(src, encoding="utf-8")
print(f"\n{changes}/3 changes applied.")
if changes == 3:
    print("All done. Regenerate your timetable to verify.")
else:
    print("Some changes were skipped — check warnings above.")
