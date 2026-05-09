import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from collections import defaultdict
from timetable.models import ScheduledUnit, Term

term = Term.objects.filter(is_current=True).first()
qs = ScheduledUnit.objects.filter(term=term, status="DRAFT").select_related(
    "cohort", "curriculum_unit", "trainer", "room", "period"
)

cohort_slots   = defaultdict(list)
trainer_slots  = defaultdict(list)
room_slots     = defaultdict(list)

for su in qs:
    key = (su.day, su.period_id)
    cohort_slots[(su.cohort_id, *key)].append(su)
    if su.trainer_id:
        trainer_slots[(su.trainer_id, *key)].append(su)
    if su.room_id:
        room_slots[(su.room_id, *key)].append(su)

print("=== Cohort slot clashes (same cohort, same slot, >1 unit) ===")
found = False
for (cid, day, pid), sus in cohort_slots.items():
    if len(sus) > 1:
        found = True
        names = ", ".join(s.curriculum_unit.code for s in sus)
        print(f"  {sus[0].cohort.name} {day} p{pid}: {names}")
if not found:
    print("  None found ✓")

print("\n=== Trainer slot clashes (EXCLUDING combined sessions) ===")
found = False
for (tid, day, pid), sus in trainer_slots.items():
    cohort_ids = {s.cohort_id for s in sus}
    if len(sus) > 1 and len(cohort_ids) == 1:
        found = True
        names = ", ".join(s.curriculum_unit.code for s in sus)
        print(f"  Trainer {sus[0].trainer.name} {day} p{pid}: {names}")
if not found:
    print("  None found ✓")

print("\n=== Room slot clashes (same room, same slot, >1 unit) ===")
found = False
for (rid, day, pid), sus in room_slots.items():
    cohort_ids = {s.cohort_id for s in sus}
    if len(sus) > 1 and len(cohort_ids) == 1:
        found = True
        names = ", ".join(s.curriculum_unit.code for s in sus)
        print(f"  Room {sus[0].room.name} {day} p{pid}: {names}")
if not found:
    print("  None found ✓")
