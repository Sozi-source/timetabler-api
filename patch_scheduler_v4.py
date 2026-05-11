"""
patch_scheduler_v4.py
Fixes NameError: term_assignments not defined in _sort_by_difficulty.
Run with: python patch_scheduler_v4.py
"""
import shutil, sys
from pathlib import Path

target = Path("timetable/scheduler.py")
if not target.exists():
    sys.exit(f"ERROR: {target} not found. Run from your project root.")

shutil.copy(target, target.with_suffix(".py.bak4"))
print(f"Backup saved to {target.with_suffix('.py.bak4')}")

src = target.read_text(encoding="utf-8")
original_has_crlf = "\r\n" in src
src = src.replace("\r\n", "\n")

changes = 0

# ── Change 1 ──────────────────────────────────────────────────────────────────
# Remove _ta_ids injection from inside _sort_by_difficulty (it can't see
# term_assignments — that's a local var in run()).
# Instead pass term_assignments into _sort_by_difficulty as a parameter.

old1 = (
    "        _ta_ids = set(term_assignments.keys()) if term_assignments else set()\n"
    "\n"
    "        def difficulty(item: tuple) -> tuple:\n"
    "            cohort_id, (cohort, units) = item\n"
    "            if not units:\n"
    "                return (0, 0, 99.0, 0)"
)
new1 = (
    "        def difficulty(item: tuple) -> tuple:\n"
    "            cohort_id, (cohort, units) = item\n"
    "            if not units:\n"
    "                return (0, 0, 99.0, 0)"
)

if old1 in src:
    src = src.replace(old1, new1, 1)
    print("[OK] Change 1: removed _ta_ids from inside difficulty()")
    changes += 1
else:
    print("WARN Change 1 not matched")

# ── Change 2 ──────────────────────────────────────────────────────────────────
# Fix trainer_counts to use a simple constant since we no longer have
# qualified_trainers — just mark every unit as having 1 trainer
# (the assignment check is what matters, not the count for sorting).

old2 = (
    "            trainer_counts = [\n"
    "                1 if (cohort_id, str(u.id)) in _ta_ids else 0\n"
    "                for u in units\n"
    "            ]"
)
new2 = (
    "            trainer_counts = [\n"
    "                len([t for t in u.qualified_trainers.all() if t.is_active])\n"
    "                for u in units\n"
    "            ]"
)

if old2 in src:
    src = src.replace(old2, new2, 1)
    print("[OK] Change 2: trainer_counts restored to qualified_trainers for sorting only")
    changes += 1
else:
    print("WARN Change 2 not matched")

# Restore line endings
if original_has_crlf:
    src = src.replace("\n", "\r\n")

target.write_text(src, encoding="utf-8")
print(f"\n{changes}/2 changes applied.")
if changes == 2:
    print("All done. Regenerate your timetable.")
else:
    print("Some changes skipped — check warnings above.")
