import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()
from timetable.models import Programme, CurriculumUnit, Department

DEPARTMENT_ID = "10804c9d-b55c-48a4-a06d-72150016bab7"

department = Department.objects.get(id=DEPARTMENT_ID)

programme, created = Programme.objects.update_or_create(
    code="CND",
    defaults={
        "department": department,
        "name": "CERTIFICATE IN NUTRITION AND DIETETICS",
        "level": "CERT",
        "total_terms": 6,
        "sharing_group": "ICMHS_NUTRITION",
        "is_active": True,
    }
)
print(f"Programme {'created' if created else 'updated'}: {programme.id} | {programme.name} | {programme.total_terms} terms")

UNITS = [
    # (code, name, term, position, unit_type, periods_per_week, credit_hours, is_active)
    # YEAR 1 SEM 1 — Term 1
    ("CND1101", "Communication Skills",                      1, 1, "CORE",       2, 2),
    ("CND1102", "Entrepreneurship",                          1, 2, "CORE",       2, 2),
    ("CND1103", "HIV/AIDS Management",                       1, 3, "CORE",       2, 2),
    ("CND1104", "Principles of Human Nutrition",             1, 4, "CORE",       4, 4),
    ("CND1105", "Human Anatomy and Physiology",              1, 5, "CORE",       4, 4),
    ("CND1106", "Applied Physical Sciences I (Chemistry)",   1, 6, "PRACTICAL",  4, 4),
    # YEAR 1 SEM 2 — Term 2
    ("CND1201", "ICT",                                       2, 1, "CORE",       4, 4),
    ("CND1202", "Diet Therapy",                              2, 2, "CORE",       4, 4),
    ("CND1203", "Food Safety and Hygiene",                   2, 3, "CORE",       2, 2),
    ("CND1204", "Applied Physical Science II (Physics)",     2, 4, "CORE",       2, 2),
    ("CND1205", "Legal Aspects in Nutrition and Dietetics",  2, 5, "CORE",       4, 4),
    ("CND1206", "Introduction to Nutrition Care Process",    2, 6, "CORE",       2, 2),
    # YEAR 1 SEM 3 — Term 3
    ("CND1301", "Basic Mathematics",                         3, 1, "CORE",       4, 4),
    ("CND1302", "Meal Planning, Management and Service",     3, 2, "PRACTICAL",  4, 4),
    ("CND1303", "Maternal and Child Health Nutrition",       3, 3, "CORE",       2, 2),
    ("CND1304", "Food Production for Invalids and Convalescents", 3, 4, "PRACTICAL", 4, 4),
    ("CND1305", "Nutrition in HIV/AIDS",                     3, 5, "CORE",       2, 2),
    ("CND1306", "Nutrition Anthropology",                    3, 6, "CORE",       2, 2),
    ("CND1307", "Introduction to Primary Health Care",       3, 7, "CORE",       2, 2),
    # YEAR 2 SEM 1 — Term 4
    ("CND2101", "Management of Malnutrition",                4, 1, "CORE",       2, 2),
    ("CND2102", "Life Skills",                               4, 2, "CORE",       2, 2),
    ("CND2103", "Clinical Rotation",                         4, 3, "PRACTICAL",  8, 1),
    ("CND2104", "Nutrition in the Lifespan",                 4, 4, "CORE",       2, 2),
    ("CND2105", "Introduction to Behavioral Science",        4, 5, "CORE",       2, 2),
    ("CND2106", "Food Science",                              4, 6, "PRACTICAL",  4, 4),
    ("CND2107", "Applied Biological Sciences",               4, 7, "PRACTICAL",  4, 4),
    # YEAR 2 SEM 2 — Term 5 (Industrial Attachment — inactive/no periods)
    ("CND2201", "Industrial Attachment (Clinical Setting)",  5, 1, "PROJECT",    0, 0, False),
    # YEAR 2 SEM 3 — Term 6
    ("CND2301", "Nutrition in Emergencies",                  6, 1, "CORE",       2, 2),
    ("CND2302", "Nutrition Assessment and Surveillance",     6, 2, "CORE",       2, 2),
    ("CND2303", "Community Diagnosis and Mobilization",      6, 3, "CORE",       2, 2),
    ("CND2304", "Demonstration Techniques",                  6, 4, "PRACTICAL",  2, 2),
    ("CND2305", "Nutrition for Vulnerable Groups",           6, 5, "CORE",       2, 2),
    ("CND2306", "Agricultural Production",                   6, 6, "CORE",       4, 4),
    ("CND2307", "Trade Project and Business Plan",           6, 7, "PROJECT",    2, 2),
]

created_count = 0
updated_count = 0

for unit_tuple in UNITS:
    if len(unit_tuple) == 8:
        code, name, term_num, position, unit_type, ppw, credit_hours, is_active = unit_tuple
    else:
        code, name, term_num, position, unit_type, ppw, credit_hours = unit_tuple
        is_active = True

    unit, created = CurriculumUnit.objects.update_or_create(
        programme=programme, code=code,
        defaults={
            "name":             name,
            "term_number":      term_num,
            "position":         position,
            "unit_type":        unit_type,
            "periods_per_week": ppw,
            "credit_hours":     credit_hours,
            "is_active":        is_active,
            "notes":            "",
        }
    )
    flag = " [INACTIVE]" if not is_active else ""
    print(f"  {'Created' if created else 'Updated'}: [T{term_num}] {code} {name}{flag}")
    if created: created_count += 1
    else: updated_count += 1

print(f"\nDONE: {created_count} created, {updated_count} updated")
total = CurriculumUnit.objects.filter(programme=programme).count()
inactive = CurriculumUnit.objects.filter(programme=programme, is_active=False).count()
print(f"CND: {total} units total ({inactive} inactive)")
