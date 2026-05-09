"""
fix_and_clear.py
================
Run this AFTER every Generate to:
1. Place any sessions the scheduler left short
2. Clear stale conflict records for fully-placed units
3. Print a clean final summary
"""

import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from collections import defaultdict
from django.db import IntegrityError
from timetable.models import (
    Cohort, Term, ScheduledUnit, CurriculumUnit,
    Room, Period, TrainerAvailability, Conflict
)

term = Term.objects.filter(is_current=True).first()
print(f"Term: {term}\n")

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]
periods = list(Period.objects.filter(
    institution=term.institution, is_break=False
).order_by("order"))

# ── Build occupancy grids ──────────────────────────────────────────────────────
cohort_busy  = defaultdict(set)
trainer_busy = defaultdict(set)
room_busy    = defaultdict(set)
unit_periods = defaultdict(set)

for su in ScheduledUnit.objects.filter(term=term, status="DRAFT"):
    slot = (su.day, su.period_id)
    cohort_busy[su.cohort_id].add(slot)
    if su.trainer_id:
        trainer_busy[su.trainer_id].add(slot)
    if su.room_id:
        room_busy[su.room_id].add(slot)
    unit_periods[(su.cohort_id, su.curriculum_unit_id)].add(su.period_id)

# ── Trainer availability ───────────────────────────────────────────────────────
trainer_avail = defaultdict(set)
for ta in TrainerAvailability.objects.filter(term=term, is_available=True):
    trainer_avail[ta.trainer_id].add((ta.day, ta.period_id))

all_slots = {(d, p.id) for d in DAYS for p in periods}

def free_slots_for_trainer(trainer_id):
    avail = trainer_avail.get(trainer_id)
    if avail is None:
        avail = all_slots
    return avail - trainer_busy[trainer_id]

def slot_is_safe(cohort_id, unit_id, period_id, slot):
    if slot in cohort_busy[cohort_id]:
        return False
    if period_id in unit_periods[(cohort_id, unit_id)]:
        return False
    return True

# ── Collect shorts ─────────────────────────────────────────────────────────────
to_fix = []
for cohort in Cohort.objects.filter(is_active=True).order_by("name"):
    units = CurriculumUnit.objects.filter(
        programme=cohort.programme,
        term_number=cohort.current_term,
        is_active=True
    )
    for unit in units:
        placed = ScheduledUnit.objects.filter(
            cohort=cohort, term=term,
            curriculum_unit=unit, status="DRAFT"
        ).count()
        need = unit.periods_per_week - placed
        if need <= 0:
            continue
        outsourced = getattr(unit, "is_outsourced", False)
        qualified = [] if outsourced else list(
            unit.qualified_trainers.filter(is_active=True)
        )
        to_fix.append((cohort, unit, need, qualified, outsourced))

print(f"Found {len(to_fix)} unit/cohort combo(s) needing placement\n")

# ── Place missing sessions ─────────────────────────────────────────────────────
rooms = list(Room.objects.filter(institution=term.institution, is_active=True))
placed_count = 0
failed = []

def do_create(cohort, unit, day, period, room, trainer):
    try:
        ScheduledUnit.objects.create(
            cohort=cohort, term=term, curriculum_unit=unit,
            day=day, period=period, room=room,
            trainer=trainer, status="DRAFT", is_combined=False
        )
        return True
    except IntegrityError:
        return False

for cohort, unit, need, qualified, outsourced in to_fix:
    days_used = set()
    for _ in range(need):
        placed = False

        if outsourced:
            for day in DAYS:
                if day in days_used:
                    continue
                for period in periods:
                    slot = (day, period.id)
                    if not slot_is_safe(cohort.id, unit.id, period.id, slot):
                        continue
                    room = next((r for r in rooms if slot not in room_busy[r.id]), None)
                    if room is None:
                        continue
                    if do_create(cohort, unit, day, period, room, None):
                        cohort_busy[cohort.id].add(slot)
                        room_busy[room.id].add(slot)
                        unit_periods[(cohort.id, unit.id)].add(period.id)
                        days_used.add(day)
                        placed_count += 1
                        placed = True
                    break
                if placed:
                    break
            if not placed:
                failed.append((cohort.name, unit.code, "OUTSOURCED — no free cohort+room slot"))
            continue

        if not qualified:
            failed.append((cohort.name, unit.code, "NO TRAINER ASSIGNED"))
            continue

        trainer_load = {t.id: len(trainer_busy[t.id]) for t in qualified}
        sorted_trainers = sorted(qualified, key=lambda t: trainer_load[t.id])

        for day in DAYS:
            if day in days_used:
                continue
            for period in periods:
                slot = (day, period.id)
                if not slot_is_safe(cohort.id, unit.id, period.id, slot):
                    continue
                trainer = next(
                    (t for t in sorted_trainers
                     if slot in free_slots_for_trainer(t.id)),
                    None
                )
                if trainer is None:
                    continue
                room = next((r for r in rooms if slot not in room_busy[r.id]), None)
                if room is None:
                    continue
                if do_create(cohort, unit, day, period, room, trainer):
                    cohort_busy[cohort.id].add(slot)
                    trainer_busy[trainer.id].add(slot)
                    room_busy[room.id].add(slot)
                    unit_periods[(cohort.id, unit.id)].add(period.id)
                    days_used.add(day)
                    placed_count += 1
                    placed = True
                break
            if placed:
                break

        if not placed:
            failed.append((cohort.name, unit.code, "No free trainer+room+cohort slot"))

print(f"Placed {placed_count} additional session(s)")

if failed:
    print(f"\n=== Still unplaceable ({len(failed)}) ===")
    for cn, code, reason in failed:
        print(f"  {cn:20}  {code}  {reason}")
else:
    print("All shorts resolved ✓")

# ── Clear stale conflict records ───────────────────────────────────────────────
print("\n=== Clearing stale conflict records ===")
cleared = 0
for c in Conflict.objects.filter(term=term):
    if c.curriculum_unit is None or c.cohort is None:
        c.delete()
        cleared += 1
        continue
    placed = ScheduledUnit.objects.filter(
        cohort=c.cohort, term=term,
        curriculum_unit=c.curriculum_unit,
        status="DRAFT"
    ).count()
    needed = c.curriculum_unit.periods_per_week
    if placed >= needed:
        c.delete()
        cleared += 1

print(f"Cleared {cleared} stale conflict(s)")
remaining = Conflict.objects.filter(term=term).count()
print(f"Remaining genuine conflicts: {remaining}")
if remaining:
    for c in Conflict.objects.filter(term=term).select_related("cohort", "curriculum_unit"):
        unit_code = c.curriculum_unit.code if c.curriculum_unit else "?"
        cohort_name = c.cohort.name if c.cohort else "?"
        print(f"  {cohort_name:20}  {unit_code}  [{c.conflict_type}] {c.description}")

# ── Final summary ──────────────────────────────────────────────────────────────
print("\n=== Final placement summary ===")
all_ok = True
for cohort in Cohort.objects.filter(is_active=True).order_by("name"):
    units = CurriculumUnit.objects.filter(
        programme=cohort.programme,
        term_number=cohort.current_term,
        is_active=True
    )
    expected = sum(u.periods_per_week for u in units)
    placed = ScheduledUnit.objects.filter(
        cohort=cohort, term=term, status="DRAFT"
    ).count()
    status = "OK" if placed >= expected else f"SHORT {expected - placed}"
    if placed < expected:
        all_ok = False
    print(f"  {cohort.name:20}  {placed:3} / {expected:3}  {status}")

if all_ok:
    print("\n  All cohorts fully scheduled ✓")
else:
    print("\n  Run validate_timetable.py to fix remaining gaps.")
