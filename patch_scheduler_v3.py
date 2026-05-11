"""
patch_scheduler_v3.py
=====================
Makes the scheduler use ONLY TermTrainerAssignment for trainer resolution.
qualified_trainers on CurriculumUnit is ignored entirely.

Run with: python patch_scheduler_v3.py
"""
import shutil, sys
from pathlib import Path

target = Path("timetable/scheduler.py")
if not target.exists():
    sys.exit(f"ERROR: {target} not found. Run from your project root.")

shutil.copy(target, target.with_suffix(".py.bak3"))
print(f"Backup saved to {target.with_suffix('.py.bak3')}")

src = target.read_text(encoding="utf-8")
original_has_crlf = "\r\n" in src
src = src.replace("\r\n", "\n")

changes = 0

# ── Change 1 ──────────────────────────────────────────────────────────────────
# Pre-check loop (call site A): use only term_assignments, no fallback.
# Units with no assignment → no_trainer_units immediately.

old1 = (
    "            for unit in unit_list:\n"
    "                ta_key    = (cohort_id, str(unit.id))\n"
    "                qualified = term_assignments.get(ta_key) or [\n"
    "                    t for t in unit.qualified_trainers.all() if t.is_active\n"
    "                ]\n"
    "                if not qualified and not getattr(unit, \"is_outsourced\", False):\n"
    "                    no_trainer_units.append((cohort, unit))\n"
    "                    placed_keys.add(f\"{cohort_id}_{unit.id}\")\n"
    "                else:\n"
    "                    viable.append(unit)"
)
new1 = (
    "            for unit in unit_list:\n"
    "                ta_key    = (cohort_id, str(unit.id))\n"
    "                qualified = term_assignments.get(ta_key, [])\n"
    "                if not qualified and not getattr(unit, \"is_outsourced\", False):\n"
    "                    no_trainer_units.append((cohort, unit))\n"
    "                    placed_keys.add(f\"{cohort_id}_{unit.id}\")\n"
    "                else:\n"
    "                    viable.append(unit)"
)

if old1 in src:
    src = src.replace(old1, new1, 1)
    print("[OK] Change 1: pre-check loop uses only term_assignments")
    changes += 1
else:
    print("WARN Change 1 not matched")

# ── Change 2 ──────────────────────────────────────────────────────────────────
# Pass loop (call site B): use only term_assignments, no fallback.

old2 = (
    "                    ta_key    = (cohort_id, str(unit.id))\n"
    "                    qualified = term_assignments.get(ta_key) or [\n"
    "                        t for t in unit.qualified_trainers.all() if t.is_active\n"
    "                    ]\n"
    "                    pr = placer.place(cohort, unit, qualified)"
)
new2 = (
    "                    ta_key    = (cohort_id, str(unit.id))\n"
    "                    qualified = term_assignments.get(ta_key, [])\n"
    "                    pr = placer.place(cohort, unit, qualified)"
)

if old2 in src:
    src = src.replace(old2, new2, 1)
    print("[OK] Change 2: pass loop uses only term_assignments")
    changes += 1
else:
    print("WARN Change 2 not matched")

# ── Change 3 ──────────────────────────────────────────────────────────────────
# _schedule_combined: use term_assignments for trainer resolution.
# Instead of intersecting qualified_trainer sets, look up the assigned trainer
# per cohort. If all cohorts share the same assigned trainer → use them.
# If assignments differ or are missing → skip this combined unit (it will be
# placed individually per cohort in the pass loop).

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
new3 = (
    "                    # Resolve trainer from TermTrainerAssignment only.\n"
    "                    # Collect assigned trainer ids for each cohort in this group.\n"
    "                    assigned_ids = [\n"
    "                        term_assignments[(cid, str(cohort_unit_map[cid].id))][0].id\n"
    "                        for cid in cohort_unit_map\n"
    "                        if (cid, str(cohort_unit_map[cid].id)) in (term_assignments or {})\n"
    "                    ]\n"
    "                    # All cohorts must share the same assigned trainer to combine.\n"
    "                    unique_assigned = list(dict.fromkeys(str(i) for i in assigned_ids))\n"
    "                    if len(unique_assigned) == 1:\n"
    "                        # All cohorts agree on one trainer — use them.\n"
    "                        qualified = list(\n"
    "                            Trainer.objects.filter(id=unique_assigned[0], is_active=True)\n"
    "                        )\n"
    "                    elif len(unique_assigned) > 1:\n"
    "                        # Cohorts have different assigned trainers — cannot combine.\n"
    "                        # Each cohort will be placed individually in the pass loop.\n"
    "                        continue\n"
    "                    else:\n"
    "                        # No assignments at all — skip combined, handle individually.\n"
    "                        continue\n"
    "\n"
    "                    if not qualified:\n"
    "                        continue"
)

if old3 in src:
    src = src.replace(old3, new3, 1)
    print("[OK] Change 3: _schedule_combined uses only term_assignments")
    changes += 1
else:
    print("WARN Change 3 not matched")

# ── Change 4 ──────────────────────────────────────────────────────────────────
# _sort_by_difficulty still calls qualified_trainers.all() for sorting.
# Replace it with term_assignments count instead.

old4 = (
    "            trainer_counts = [\n"
    "                len([t for t in u.qualified_trainers.all() if t.is_active])\n"
    "                for u in units\n"
    "            ]"
)
new4 = (
    "            trainer_counts = [\n"
    "                1 if (cohort_id, str(u.id)) in _ta_ids else 0\n"
    "                for u in units\n"
    "            ]"
)

# This one also needs _ta_ids to be available in the sort lambda.
# We inject it via a closure by patching the difficulty() function header.
old4b = (
    "        def difficulty(item: tuple) -> tuple:\n"
    "            cohort_id, (cohort, units) = item\n"
    "            if not units:\n"
    "                return (0, 0, 99.0, 0)"
)
new4b = (
    "        _ta_ids = set(term_assignments.keys()) if term_assignments else set()\n"
    "\n"
    "        def difficulty(item: tuple) -> tuple:\n"
    "            cohort_id, (cohort, units) = item\n"
    "            if not units:\n"
    "                return (0, 0, 99.0, 0)"
)

if old4 in src and old4b in src:
    src = src.replace(old4, new4, 1)
    src = src.replace(old4b, new4b, 1)
    print("[OK] Change 4: difficulty sort uses term_assignments instead of qualified_trainers")
    changes += 1
else:
    if old4 not in src:
        print("WARN Change 4a not matched (trainer_counts block)")
    if old4b not in src:
        print("WARN Change 4b not matched (difficulty function header)")

# Restore line endings
if original_has_crlf:
    src = src.replace("\n", "\r\n")

target.write_text(src, encoding="utf-8")
print(f"\n{changes}/4 changes applied.")
if changes == 4:
    print("All done. Regenerate your timetable to verify.")
else:
    print("Some changes skipped — check warnings above.")
