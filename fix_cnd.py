from timetable.models import Programme, Cohort, Department
from datetime import date

dept = Department.objects.get(id="837d0854-4e1f-4744-9afb-6fd4b9d12dfa")

old = Programme.objects.get(code="1905", department=dept)
old.code = "CND"
old.sharing_group = "ICMHS_NUTRITION"
old.save()
print("Fixed CND programme:", old.code, old.name)

def calc_term(start_year, start_month):
    today = date.today()
    def t(m): return 0 if m<=4 else 1 if m<=8 else 2
    return max(1, (today.year*3 + t(today.month)) - (start_year*3 + t(start_month)) + 1)

cnd = Programme.objects.get(code="CND", department=dept)
cohorts = [
    ("CND SEPT 2025", 2025, 9, 10),
    ("CND JAN 2026",  2026, 1, 10),
]
for name, sy, sm, sc in cohorts:
    ct = calc_term(sy, sm)
    c, created = Cohort.objects.update_or_create(
        programme=cnd, name=name,
        defaults={"start_year":sy,"start_month":sm,"current_term":ct,"student_count":sc,"is_active":True}
    )
    action = "Created" if created else "Updated"
    print(action + ": " + name + " | Term " + str(ct))

print()
for c in Cohort.objects.filter(programme__department=dept).order_by("programme__code","start_year","start_month"):
    print("  " + c.programme.code + " | " + c.name + " | Term " + str(c.current_term) + " | " + str(c.student_count) + " students")