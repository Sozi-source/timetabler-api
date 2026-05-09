"""
diagnose_deep.py  — run from timetabler/
    python diagnose_deep.py
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from timetable.models import (
    Cohort, Term, ScheduledUnit, CurriculumUnit,
    Trainer, Programme, Period, Room,
)
from timetable.scheduler import OccupancyGrid, ConstraintIndex, SlotKey

term = Term.objects.filter(is_current=True).first()
inst = term.institution
days    = list(inst.days_of_week)
periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))
rooms   = list(Room.objects.filter(institution=inst, is_active=True))

all_trainers = list(Trainer.objects.filter(institution=inst, is_active=True))
all_cohorts  = list(Cohort.objects.filter(programme__department__institution=inst, is_active=True))

all_unit_ids    = [str(x) for x in CurriculumUnit.objects.filter(
    programme__department__institution=inst, is_active=True
).values_list("id", flat=True)]
all_cohort_ids  = [str(c.id) for c in all_cohorts]
all_trainer_ids = [str(t.id) for t in all_trainers]

grid   = OccupancyGrid.build(term)
cindex = ConstraintIndex(term, all_unit_ids, all_cohort_ids, all_trainer_ids)

# ── 1. SPLIT SESSION FAILURES ───────────────────────────────────────────────
print("=== SPLIT SESSION FAILURES ===")
problem_units = [
    ("CND SEPT 25", "CND1302"),
    ("CND SEPT 25", "CND1304"),
    ("DHN MAY 24",  "DHN2307"),
    ("DHN MAY 24",  "DHN3105"),
    ("DHN JAN 24",  "DHN3203"),
    ("DND JAN 26",  "DND1205"),
]

for cohort_name, unit_code in problem_units:
    try:
        cohort = Cohort.objects.get(name=cohort_name)
        unit   = CurriculumUnit.objects.get(code=unit_code)
    except Exception as e:
        print(f"  {cohort_name}/{unit_code}: NOT FOUND ({e})")
        continue

    cid = str(cohort.id)
    placed = list(ScheduledUnit.objects.filter(
        cohort=cohort, term=term, status="DRAFT", curriculum_unit=unit
    ).values("day", "period_id"))

    active_trainers = [t for t in unit.qualified_trainers.all() if t.is_active]
    trainer_loads   = [
        (t.last_name, grid.trainer_week_periods(str(t.id)), t.max_periods_per_week)
        for t in active_trainers
    ]

    free_slots = []
    for day in days:
        for p in periods:
            key = SlotKey(day, str(p.id))
            if grid.cohort_busy(cid, key):
                continue
            for t in active_trainers:
                tid = str(t.id)
                if grid.trainer_week_periods(tid) < t.max_periods_per_week:
                    if not grid.trainer_busy(tid, key):
                        if not cindex.trainer_blocked(tid, key):
                            free_slots.append((day, getattr(p, "label", str(p.id)), t.last_name))
                            break

    print(f"\n  {cohort_name}/{unit_code} | needs={unit.periods_per_week} placed={len(placed)}")
    print(f"    Already placed at: {placed}")
    print(f"    Trainer loads:     {trainer_loads}")
    print(f"    Free slots ({len(free_slots)}): {free_slots[:10]}")
    if not free_slots:
        print(f"    !! NO FREE SLOTS")

print()

# ── 2. CHN MAY 25 vs DHN MAY 25 ────────────────────────────────────────────
print("=== MISSING COMBINED: CHN MAY 25 vs DHN MAY 25 ===")
try:
    chn = Cohort.objects.get(name="CHN MAY 25")
    dhn = Cohort.objects.get(name="DHN MAY 25")
    chn_units = list(CurriculumUnit.objects.filter(programme=chn.programme, term_number=chn.current_term, is_active=True))
    dhn_units = list(CurriculumUnit.objects.filter(programme=dhn.programme, term_number=dhn.current_term, is_active=True))
    chn_names = {u.name.strip(): u for u in chn_units}
    dhn_names = {u.name.strip(): u for u in dhn_units}
    shared    = set(chn_names.keys()) & set(dhn_names.keys())
    print(f"  CHN MAY 25 current_term={chn.current_term} sharing_group='{chn.programme.sharing_group}'")
    print(f"  DHN MAY 25 current_term={dhn.current_term} sharing_group='{dhn.programme.sharing_group}'")
    print(f"  Shared unit names ({len(shared)}): {sorted(shared)}")
    print(f"  CHN-only: {[chn_names[n].code for n in set(chn_names)-shared]}")
    print(f"  DHN-only: {[dhn_names[n].code for n in set(dhn_names)-shared]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()

# ── 3. ALL cohort term numbers ───────────────────────────────────────────────
print("=== COHORT TERM NUMBERS & SHARING GROUPS ===")
for c in sorted(all_cohorts, key=lambda x: x.name):
    n = CurriculumUnit.objects.filter(programme=c.programme, term_number=c.current_term, is_active=True).count()
    print(f"  {c.name} | term={c.current_term} | group='{c.programme.sharing_group}' | units={n}")

print()

# ── 4. No-trainer units ──────────────────────────────────────────────────────
print("=== UNITS WITH NO ACTIVE TRAINER ===")
for cohort in sorted(all_cohorts, key=lambda x: x.name):
    units = CurriculumUnit.objects.filter(
        programme=cohort.programme, term_number=cohort.current_term, is_active=True
    ).prefetch_related("qualified_trainers")
    for u in units:
        active = [t for t in u.qualified_trainers.all() if t.is_active]
        if not active:
            placed = ScheduledUnit.objects.filter(cohort=cohort, term=term, curriculum_unit=u, status="DRAFT").count()
            print(f"  {cohort.name} | {u.code} '{u.name}' | outsourced={getattr(u,'is_outsourced',False)} | {placed}/{u.periods_per_week}")

print()

# ── 5. Trainer utilisation ───────────────────────────────────────────────────
print("=== TRAINER UTILISATION ===")
for t in sorted(all_trainers, key=lambda x: x.last_name):
    load = grid.trainer_week_periods(str(t.id))
    print(f"  {t.last_name} | {load}/{t.max_periods_per_week} | {t.max_periods_per_week - load} free")
