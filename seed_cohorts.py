import os, django
from datetime import date
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()
from timetable.models import Programme, Cohort, Department

DEPARTMENT_ID = "837d0854-4e1f-4744-9afb-6fd4b9d12dfa"

def calc_current_term(start_year, start_month):
    """Calculate current term based on admission date. 3 terms/year: Jan, May, Sep."""
    today = date.today()
    # Map month to term index within year (0-based)
    def month_to_term(m):
        if m <= 4: return 0   # Jan-Apr
        elif m <= 8: return 1  # May-Aug
        else: return 2         # Sep-Dec
    start_term_index = start_year * 3 + month_to_term(start_month)
    today_term_index = today.year * 3 + month_to_term(today.month)
    elapsed = today_term_index - start_term_index
    return max(1, elapsed + 1)  # current term (1-based, minimum 1)

COHORTS = [
    # (programme_code, name, start_year, start_month, student_count)
    ("CHN",  "CHN SEPT 2024", 2024, 9,  10),
    ("CHN",  "CHN JAN 2025",  2025, 1,  10),
    ("CHN",  "CHN MAY 2025",  2025, 5,  10),
    ("CND",  "CND SEPT 2025", 2025, 9,  10),
    ("DHN",  "DHN JAN 2024",  2024, 1,  10),
    ("DHN",  "DHN MAY 2025",  2025, 5,  10),
    ("DND",  "DND SEPT 2025", 2025, 9,  10),
    ("DHNT", "DHNT SEPT 2025",2025, 9,  10),
    ("DND",  "DND JAN 2026",  2026, 1,  10),
]

department = Department.objects.get(id=DEPARTMENT_ID)
created_count = 0
updated_count = 0

print("=" * 60)
print("Seeding Cohorts")
print("=" * 60)

for prog_code, name, start_year, start_month, student_count in COHORTS:
    try:
        programme = Programme.objects.get(code=prog_code, department=department)
    except Programme.DoesNotExist:
        print(f"  SKIPPED: Programme {prog_code} not found")
        continue

    current_term = calc_current_term(start_year, start_month)

    cohort, created = Cohort.objects.update_or_create(
        programme=programme,
        name=name,
        defaults={
            "start_year":    start_year,
            "start_month":   start_month,
            "current_term":  current_term,
            "student_count": student_count,
            "is_active":     True,
        }
    )

    status = "Created" if created else "Updated"
    print(f"  {status}: {name} | Programme: {prog_code} | Current term: {current_term} | Students: {student_count}")
    if created: created_count += 1
    else: updated_count += 1

print()
print("=" * 60)
print(f"Done: {created_count} created, {updated_count} updated")
print()
print("All cohorts:")
for c in Cohort.objects.filter(programme__department=department).order_by("programme__code", "start_year", "start_month"):
    print(f"  {c.programme.code} | {c.name} | Term {c.current_term} | {c.student_count} students")