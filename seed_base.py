import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from timetable.models import Institution, Department, Trainer

# Institution
inst, created = Institution.objects.update_or_create(
    name="Imperial College of Medical and Health Sciences",
    defaults={
        "short_name": "ICMHS",
        "country": "Kenya",
        "timezone": "Africa/Nairobi",
        "days_of_week": ["MON","TUE","WED","THU","FRI"],
        "allow_back_to_back": True,
        "max_periods_per_day": 4,
    }
)
print(f"Institution ({'created' if created else 'updated'}): {inst.name} | ID: {inst.id}")

# Department
dept, created = Department.objects.update_or_create(
    name="Human Nutrition and Dietetics",
    defaults={
        "code": "HND",
        "institution": inst,
        "is_active": True,
    }
)
print(f"Department ({'created' if created else 'updated'}): {dept.name} | ID: {dept.id}")

# Trainers
TRAINERS = [
    {"staff_id": "ICM001", "name": "Wilfred Osozi",  "short_name": "Osozi"},
    {"staff_id": "ICM002", "name": "Mary Kaganjo",   "short_name": "Kaganjo"},
    {"staff_id": "ICM003", "name": "Milkah Wambui",  "short_name": "Wambui"},
    {"staff_id": "ICM004", "name": "Martin Wanjohi", "short_name": "Wanjohi"},
    {"staff_id": "ICM005", "name": "Fiona Kwamboka", "short_name": "Kwamboka"},
    {"staff_id": "ICM006", "name": "Maureen Ayuma",  "short_name": "Ayuma"},
    {"staff_id": "ICM007", "name": "Elias Kirimi",   "short_name": "Kirimi"},
]

print("\nTrainers:")
for t in TRAINERS:
    trainer, created = Trainer.objects.update_or_create(
        staff_id=t["staff_id"],
        defaults={
            "name": t["name"],
            "short_name": t["short_name"],
            "department": dept,
            "is_active": True,
        }
    )
    print(f"  {trainer.staff_id} | {trainer.name} | ID: {trainer.id}")

print(f"\nDEPARTMENT_ID = \"{dept.id}\"")
print("TRAINER_MAP = {")
for t in Trainer.objects.filter(department=dept).order_by("staff_id"):
    print(f'    "{t.staff_id}": "{t.id}",')
print("}")