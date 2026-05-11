"""
patch_scheduler.py
Run with: python patch_scheduler.py
Works regardless of Windows/Unix line endings.
"""
import re, shutil, sys
from pathlib import Path

target = Path("timetable/scheduler.py")
if not target.exists():
    sys.exit(f"ERROR: {target} not found. Run from your project root.")

shutil.copy(target, target.with_suffix(".py.bak"))
print(f"Backup saved to {target.with_suffix('.py.bak')}")

src = target.read_text(encoding="utf-8")

# Normalise to LF for matching, we'll restore original endings at the end
original_has_crlf = "\r\n" in src
src = src.replace("\r\n", "\n")

changes = 0

# ── Change 1: import ──────────────────────────────────────────────────────────
old = (
    "from .models import (\n"
    "    Cohort, Conflict, Constraint, CurriculumUnit,\n"
    "    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    ")"
)
new = (
    "from .models import (\n"
    "    Cohort, Conflict, Constraint, CurriculumUnit,\n"
    "    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    "    TermTrainerAssignment,\n"
    ")"
)
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Change 1: TermTrainerAssignment added to imports")
    changes += 1
else:
    print("WARN Change 1 not matched")

# ── Change 2: term_assignments lookup ────────────────────────────────────────
old = (
    "        result = GenerationResult(term=self.term, total_required=total_required)\n"
    "\n"
    "        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────"
)
new = (
    "        result = GenerationResult(term=self.term, total_required=total_required)\n"
    "\n"
    "        # ── Term-specific trainer override lookup ─────────────────────────\n"
    "        # Key: (cohort_id_str, curriculum_unit_id_str) -> [Trainer]\n"
    "        # When a TermTrainerAssignment exists for this cohort+unit+term,\n"
    "        # only that trainer is offered to the Placer instead of the full pool.\n"
    "        term_assignments: dict[tuple[str, str], list[Trainer]] = {}\n"
    "        for tta in TermTrainerAssignment.objects.filter(\n"
    "            term=self.term,\n"
    "            trainer__is_active=True,\n"
    "        ).select_related(\"trainer\"):\n"
    "            key = (str(tta.cohort_id), str(tta.curriculum_unit_id))\n"
    "            term_assignments[key] = [tta.trainer]\n"
    "\n"
    "        # ── Step 3: schedule COMBINED sessions (shared classes) ───────────"
)
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Change 2: term_assignments lookup inserted")
    changes += 1
else:
    print("WARN Change 2 not matched")

# ── Change 3: call site A (pre-check loop) ───────────────────────────────────
old = (
    "            for unit in unit_list:\n"
    "                qualified = [t for t in unit.qualified_trainers.all() if t.is_active]\n"
    "                if not qualified and not getattr(unit, \"is_outsourced\", False):\n"
    "                    no_trainer_units.append((cohort, unit))\n"
    "                    placed_keys.add(f\"{cohort_id}_{unit.id}\")   # prevent re-try\n"
    "                else:\n"
    "                    viable.append(unit)"
)
new = (
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
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Change 3: call site A (pre-check loop) patched")
    changes += 1
else:
    print("WARN Change 3 not matched")

# ── Change 4: call site B (pass loop) ────────────────────────────────────────
old = (
    "                    qualified = [t for t in unit.qualified_trainers.all() if t.is_active]\n"
    "                    pr        = placer.place(cohort, unit, qualified)"
)
new = (
    "                    ta_key    = (cohort_id, str(unit.id))\n"
    "                    qualified = term_assignments.get(ta_key) or [\n"
    "                        t for t in unit.qualified_trainers.all() if t.is_active\n"
    "                    ]\n"
    "                    pr = placer.place(cohort, unit, qualified)"
)
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Change 4: call site B (pass loop) patched")
    changes += 1
else:
    print("WARN Change 4 not matched")

# Restore original line endings if file was CRLF
if original_has_crlf:
    src = src.replace("\n", "\r\n")

target.write_text(src, encoding="utf-8")
print(f"\n{changes}/4 changes applied.")
if changes == 4:
    print("All done. Regenerate your timetable to verify.")
else:
    print("Some changes were skipped — check warnings above.")
