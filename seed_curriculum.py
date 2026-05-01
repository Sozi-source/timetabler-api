"""
seed_curriculum.py
==================
Unified curriculum seed for the ICMHS Nutrition & Dietetics department.

Tuple format (all programmes):
    (code, name, term_number, position, unit_type, periods_per_week, credit_hours)
    (code, name, term_number, position, unit_type, periods_per_week, credit_hours, is_active)

PPW rule:
    - Regular units:        periods_per_week = credit_hours / 2
    - Clinical Rotation:    periods_per_week = 8,  credit_hours = 480
    - Industrial Attachment:periods_per_week = 0,  credit_hours = 480, is_active = False

Run:
    python seed_curriculum.py
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from timetable.models import Programme, CurriculumUnit, Department  # noqa: E402

# ─── Config ────────────────────────────────────────────────────────────────────

DEPARTMENT_ID = "10804c9d-b55c-48a4-a06d-72150016bab7"
SHARING_GROUP  = "ICMHS_NUTRITION"

# fmt: off
PROGRAMMES = [

    # ══════════════════════════════════════════════════════════════════════════
    # CERTIFICATE IN NUTRITION AND DIETETICS  (6 terms)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "code":        "CND",
        "name":        "CERTIFICATE IN NUTRITION AND DIETETICS",
        "level":       "CERT",
        "total_terms": 6,
        "units": [
            # ── Term 1 ──────────────────────────────────────────────────────
            ("CND1101", "Communication Skills",                          1, 1, "CORE",      1, 2),
            ("CND1102", "Entrepreneurship",                              1, 2, "CORE",      1, 2),
            ("CND1103", "HIV/AIDS Management",                           1, 3, "CORE",      1, 2),
            ("CND1104", "Principles of Human Nutrition",                 1, 4, "CORE",      2, 4),
            ("CND1105", "Human Anatomy and Physiology",                  1, 5, "CORE",      2, 4),
            ("CND1106", "Applied Physical Sciences I (Chemistry)",       1, 6, "PRACTICAL", 2, 4),
            # ── Term 2 ──────────────────────────────────────────────────────
            ("CND1201", "ICT",                                           2, 1, "CORE",      2, 4),
            ("CND1202", "Diet Therapy",                                  2, 2, "CORE",      2, 4),
            ("CND1203", "Food Safety and Hygiene",                       2, 3, "CORE",      1, 2),
            ("CND1204", "Applied Physical Sciences II (Physics)",        2, 4, "CORE",      1, 2),
            ("CND1205", "Legal Aspects in Nutrition and Dietetics",      2, 5, "CORE",      2, 4),
            ("CND1206", "Introduction to Nutrition Care Process",        2, 6, "CORE",      1, 2),
            # ── Term 3 ──────────────────────────────────────────────────────
            ("CND1301", "Basic Mathematics",                             3, 1, "CORE",      2, 4),
            ("CND1302", "Meal Planning, Management and Service",         3, 2, "PRACTICAL", 2, 4),
            ("CND1303", "Maternal and Child Nutrition",                  3, 3, "CORE",      1, 2),
            ("CND1304", "Food Production for Invalids and Convalescent", 3, 4, "PRACTICAL", 2, 4),
            ("CND1305", "Nutrition in HIV and AIDS",                     3, 5, "CORE",      1, 2),
            ("CND1306", "Nutrition Anthropology",                        3, 6, "CORE",      1, 2),
            ("CND1307", "Introduction to Primary Health Care",           3, 7, "CORE",      1, 2),
            # ── Term 4 ──────────────────────────────────────────────────────
            ("CND2101", "Management of Malnutrition",                    4, 1, "CORE",      1, 2),
            ("CND2102", "Life Skills",                                   4, 2, "CORE",      1, 2),
            ("CND2103", "Clinical Rotation",                             4, 3, "PRACTICAL", 8, 480),
            ("CND2104", "Nutrition in the Lifespan",                     4, 4, "CORE",      1, 2),
            ("CND2105", "Introduction to Behavioural Science",           4, 5, "CORE",      1, 2),
            ("CND2106", "Food Science",                                  4, 6, "PRACTICAL", 2, 4),
            ("CND2107", "Applied Biological Sciences",                   4, 7, "PRACTICAL", 2, 4),
            # ── Term 5 (Industrial Attachment) ──────────────────────────────
            ("CND2201", "Industrial Attachment (Clinical Setting)",      5, 1, "PROJECT",   0, 480, False),
            # ── Term 6 ──────────────────────────────────────────────────────
            ("CND2301", "Nutrition in Emergencies",                      6, 1, "CORE",      1, 2),
            ("CND2302", "Nutrition Assessment and Surveillance",         6, 2, "CORE",      1, 2),
            ("CND2303", "Community Diagnosis and Mobilization",          6, 3, "CORE",      1, 2),
            ("CND2304", "Demonstration Techniques",                      6, 4, "PRACTICAL", 1, 2),
            ("CND2305", "Nutrition for Vulnerable Groups",               6, 5, "CORE",      1, 2),
            ("CND2306", "Agricultural Production",                       6, 6, "CORE",      2, 4),
            ("CND2307", "Trade Project and Business Plan",               6, 7, "PROJECT",   1, 2),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CERTIFICATE IN HUMAN NUTRITION  (6 terms)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "code":        "CHN",
        "name":        "CERTIFICATE IN HUMAN NUTRITION",
        "level":       "CERT",
        "total_terms": 6,
        "units": [
            # ── Term 1 ──────────────────────────────────────────────────────
            ("CCU1101", "Communication Skills",                          1, 1, "CORE",      1, 2),
            ("CCU1102", "Entrepreneurship",                              1, 2, "CORE",      1, 2),
            ("CCU1105", "HIV/AIDS Management",                           1, 3, "CORE",      1, 2),
            ("CCU1106", "ICT",                                           1, 4, "CORE",      2, 4),
            ("CCU1107", "Human Anatomy and Physiology",                  1, 5, "CORE",      2, 4),
            ("CHN1101", "Applied Physical Sciences I (Chemistry)",       1, 6, "PRACTICAL", 2, 4),
            # ── Term 2 ──────────────────────────────────────────────────────
            ("CHN1301", "Diet Therapy",                                  2, 1, "CORE",      2, 4),
            ("CHN1201", "Principles of Human Nutrition",                 2, 2, "CORE",      2, 4),
            ("CHN1203", "Food Safety and Hygiene",                       2, 3, "CORE",      1, 2),
            ("CHN1204", "Applied Physical Sciences II (Physics)",        2, 4, "CORE",      1, 2),
            ("CHN1306", "Legal Aspects in Nutrition and Dietetics",      2, 5, "CORE",      2, 4),
            ("CHN1304", "Nutrition Care Process",                        2, 6, "CORE",      2, 4),
            # ── Term 3 ──────────────────────────────────────────────────────
            ("CCU1111", "Basic Mathematics",                             3, 1, "CORE",      2, 4),
            ("CHN1206", "Meal Planning, Management and Service",         3, 2, "PRACTICAL", 2, 4),
            ("CHN2205", "Maternal and Child Nutrition",                  3, 3, "CORE",      2, 4),
            ("CHN2203", "Food Production for Invalids and Convalescent", 3, 4, "PRACTICAL", 2, 4),
            ("CHN2307", "Nutrition in HIV and AIDS",                     3, 5, "CORE",      1, 2),
            ("CHN2302", "Nutrition Anthropology",                        3, 6, "CORE",      1, 2),
            ("CHN1305", "Introduction to Primary Health Care",           3, 7, "CORE",      1, 2),
            # ── Term 4 ──────────────────────────────────────────────────────
            ("CHN2304", "Nutrition in Emergencies",                      4, 1, "CORE",      1, 2),
            ("CHN2207", "Nutrition Assessment and Surveillance",         4, 2, "CORE",      1, 2),
            ("CHN2204", "Nutrition in the Lifespan",                     4, 3, "CORE",      1, 2),
            ("CCU1110", "Life Skills",                                   4, 4, "CORE",      1, 2),
            ("CHN1308", "Clinical Rotation",                             4, 5, "PRACTICAL", 8, 480),
            ("CHN1202", "Food Science",                                  4, 6, "PRACTICAL", 2, 4),
            ("CHN1303", "Applied Biological Sciences",                   4, 7, "PRACTICAL", 2, 4),
            # ── Term 5 (Industrial Attachment) ──────────────────────────────
            ("CHN2101", "Industrial Attachment (Clinical Setting)",      5, 1, "PROJECT",   0, 480, False),
            # ── Term 6 ──────────────────────────────────────────────────────
            ("CHN2305", "Community Diagnosis and Mobilization",          6, 1, "CORE",      1, 2),
            ("CHN2306", "Demonstration Techniques",                      6, 2, "PRACTICAL", 1, 2),
            ("CHN2308", "Nutrition for Vulnerable Groups",               6, 3, "CORE",      1, 2),
            ("CHN2201", "Introduction to Behavioural Science",           6, 4, "CORE",      1, 2),
            ("CHN2202", "Management of Malnutrition",                    6, 5, "CORE",      1, 2),
            ("CHN2309", "Agricultural Production",                       6, 6, "CORE",      2, 4),
            ("CHN2206", "Trade Project and Business Plan",               6, 7, "PROJECT",   1, 2),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # DIPLOMA IN NUTRITION AND DIETETICS  (9 terms)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "code":        "DND",
        "name":        "DIPLOMA IN NUTRITION AND DIETETICS",
        "level":       "DIPLOMA",
        "total_terms": 9,
        "units": [
            # ── Term 1 ──────────────────────────────────────────────────────
            ("DND1101", "Communication Skills",                             1, 1, "CORE",      1, 2),
            ("DND1102", "Entrepreneurship",                                 1, 2, "CORE",      1, 2),
            ("DND1103", "HIV/AIDS Management",                              1, 3, "CORE",      1, 2),
            ("DND1104", "Principles of Human Nutrition",                    1, 4, "CORE",      2, 4),
            ("DND1105", "Human Anatomy and Physiology",                     1, 5, "CORE",      2, 4),
            ("DND1106", "Applied Physical Sciences I (Chemistry)",          1, 6, "PRACTICAL", 2, 4),
            # ── Term 2 ──────────────────────────────────────────────────────
            ("DND1201", "ICT",                                              2, 1, "CORE",      2, 4),
            ("DND1202", "Diet Therapy I",                                   2, 2, "CORE",      2, 4),
            ("DND1203", "Food Safety and Hygiene",                          2, 3, "CORE",      1, 2),
            ("DND1204", "Applied Physical Sciences II (Physics)",           2, 4, "CORE",      1, 2),
            ("DND1205", "Legal Aspects in Nutrition and Dietetics",         2, 5, "CORE",      2, 4),
            ("DND1206", "Nutrition Care Process",                           2, 6, "CORE",      2, 4),
            # ── Term 3 ──────────────────────────────────────────────────────
            ("DND1301", "Basic Mathematics",                                3, 1, "CORE",      2, 4),
            ("DND1302", "Meal Planning, Management and Service",            3, 2, "PRACTICAL", 2, 4),
            ("DND1303", "Maternal and Child Nutrition",                     3, 3, "CORE",      1, 2),
            ("DND1304", "Food Production for Invalids and Convalescent",    3, 4, "PRACTICAL", 2, 4),
            ("DND1305", "Nutrition in HIV and AIDS",                        3, 5, "CORE",      1, 2),
            ("DND1306", "Nutrition Anthropology",                           3, 6, "CORE",      1, 2),
            ("DND1307", "Introduction to Primary Health Care",              3, 7, "CORE",      1, 2),
            # ── Term 4 ──────────────────────────────────────────────────────
            ("DND2101", "Management of Malnutrition",                       4, 1, "CORE",      1, 2),
            ("DND2102", "Life Skills",                                      4, 2, "CORE",      1, 2),
            ("DND2103", "Clinical Rotation",                                4, 3, "PRACTICAL", 8, 480),
            ("DND2104", "Nutrition in the Lifespan",                        4, 4, "CORE",      1, 2),
            ("DND2105", "Diet Therapy II",                                  4, 5, "CORE",      2, 4),
            ("DND2106", "Principles of Food Processing and Preservation",   4, 6, "PRACTICAL", 2, 4),
            ("DND2107", "First Aid",                                        4, 7, "CORE",      1, 2),
            # ── Term 5 (Industrial Attachment I) ────────────────────────────
            ("DND2201", "Industrial Attachment I",                          5, 1, "PROJECT",   0, 480, False),
            # ── Term 6 ──────────────────────────────────────────────────────
            ("DND2301", "Nutrition in Emergencies",                         6, 1, "CORE",      1, 2),
            ("DND2302", "Nutrition Assessment and Surveillance",            6, 2, "CORE",      1, 2),
            ("DND2303", "Introduction to Microbiology",                     6, 3, "CORE",      1, 2),
            ("DND2304", "Introduction to Biostatistics",                    6, 4, "CORE",      2, 4),
            ("DND2305", "Biochemistry I",                                   6, 5, "CORE",      1, 2),
            ("DND2306", "Research Methods",                                 6, 6, "CORE",      2, 4),
            ("DND2307", "Principles of Nutrition and Behaviour",            6, 7, "CORE",      1, 2),
            # ── Term 7 ──────────────────────────────────────────────────────
            ("DND3101", "Food Security",                                    7, 1, "CORE",      1, 2),
            ("DND3102", "Communicable and Non-Communicable Disease",        7, 2, "CORE",      2, 4),
            ("DND3103", "Food Microbiology and Parasitology",               7, 3, "PRACTICAL", 2, 4),
            ("DND3104", "Diet Therapy III",                                 7, 4, "CORE",      2, 4),
            ("DND3105", "Community Partnership Skills",                     7, 5, "CORE",      1, 2),
            ("DND3106", "Biochemistry II",                                  7, 6, "CORE",      2, 4),
            # ── Term 8 ──────────────────────────────────────────────────────
            ("DND3201", "Product Development, Marketing and Sales",         8, 1, "CORE",      1, 2),
            ("DND3202", "Industrial Organization and Management",           8, 2, "CORE",      1, 2),
            ("DND3203", "Nutrition Epidemiology",                           8, 3, "CORE",      2, 4),
            ("DND3204", "Nutrition Education and Counselling",              8, 4, "CORE",      2, 4),
            ("DND3205", "Agricultural Production",                          8, 5, "CORE",      2, 4),
            ("DND3206", "Trade Project and Business Plan",                  8, 6, "PROJECT",   1, 2),
            # ── Term 9 (Industrial Attachment II) ───────────────────────────
            ("DND3301", "Industrial Attachment II",                         9, 1, "PROJECT",   0, 480, False),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # DIPLOMA IN HUMAN NUTRITION  (9 terms)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "code":        "DHN",
        "name":        "DIPLOMA IN HUMAN NUTRITION",
        "level":       "DIPLOMA",
        "total_terms": 9,
        "units": [
            # ── Term 1 ──────────────────────────────────────────────────────
            ("DCU1101",  "Communication Skills",                            1, 1, "CORE",      1, 2),
            ("DCU1102",  "Entrepreneurship",                                1, 2, "CORE",      1, 2),
            ("DCU1105",  "HIV/AIDS Management",                             1, 3, "CORE",      1, 2),
            ("DCU1106",  "ICT",                                             1, 4, "CORE",      2, 4),
            ("DCU1107",  "Human Anatomy and Physiology",                    1, 5, "CORE",      2, 4),
            ("DHN1101",  "Applied Physical Sciences I (Chemistry)",         1, 6, "PRACTICAL", 2, 4),
            ("DHN1103",  "Introduction to Nutrition and Dietetics",         1, 7, "CORE",      1, 2),
            # ── Term 2 ──────────────────────────────────────────────────────
            ("DHN1203",  "Diet Therapy I",                                  2, 1, "CORE",      2, 4),
            ("DHN1207",  "Principles of Human Nutrition",                   2, 2, "CORE",      2, 4),
            ("DHN1206",  "Food Safety and Hygiene",                         2, 3, "CORE",      1, 2),
            ("DHN1208",  "Applied Physical Sciences II (Physics)",          2, 4, "CORE",      1, 2),
            ("DHN1303",  "Legal Aspects in Nutrition and Dietetics",        2, 5, "CORE",      2, 4),
            ("DHN1307",  "Nutrition Care Process",                          2, 6, "CORE",      1, 2),
            # ── Term 3 ──────────────────────────────────────────────────────
            ("DCU1111",  "Basic Mathematics",                               3, 1, "CORE",      2, 4),
            ("DHN1209",  "Meal Planning, Management and Service",           3, 2, "PRACTICAL", 2, 4),
            ("DHN1304",  "Maternal and Child Nutrition",                    3, 3, "CORE",      1, 2),
            ("DHN1305",  "Food Production for Invalids and Convalescent",   3, 4, "PRACTICAL", 2, 4),
            ("DHN1205",  "Nutrition in HIV and AIDS",                       3, 5, "CORE",      1, 2),
            ("DHN1209B", "Nutrition Anthropology",                          3, 6, "CORE",      1, 2),
            ("DHN2207",  "Introduction to Primary Health Care",             3, 7, "CORE",      1, 2),
            # ── Term 4 ──────────────────────────────────────────────────────
            ("DHN3204",  "Nutrition in Emergencies",                        4, 1, "CORE",      1, 2),
            ("DHN3106",  "Nutrition Assessment and Surveillance",           4, 2, "CORE",      1, 2),
            ("DHN2302",  "Nutrition in the Lifespan",                       4, 3, "CORE",      1, 2),
            ("DHN1306",  "Clinical Rotation",                               4, 4, "PRACTICAL", 8, 480),
            ("DCU1110",  "Life Skills",                                     4, 5, "CORE",      1, 2),
            ("DCU1104",  "First Aid",                                       4, 6, "CORE",      1, 2),
            # ── Term 5 (Industrial Attachment I) ────────────────────────────
            ("DHN2101",  "Industrial Attachment I (Clinical Setting)",      5, 1, "PROJECT",   0, 480, False),
            # ── Term 6 ──────────────────────────────────────────────────────
            ("DHN2201",  "Introduction to Microbiology",                    6, 1, "CORE",      1, 2),
            ("DHN2202",  "Introduction to Biostatistics",                   6, 2, "CORE",      2, 4),
            ("DHN2203",  "Biochemistry I",                                  6, 3, "CORE",      1, 2),
            ("DHN2204",  "Principles of Food Processing and Preservation",  6, 4, "PRACTICAL", 2, 4),
            ("DHN2205",  "Diet Therapy II",                                 6, 5, "CORE",      2, 4),
            ("DHN2305",  "Principles of Nutrition and Behaviour",           6, 6, "CORE",      2, 4),
            ("DHN2201B", "Management of Malnutrition",                      6, 7, "CORE",      1, 2),
            # ── Term 7 ──────────────────────────────────────────────────────
            ("DHN2307",  "Research Methods",                                7, 1, "CORE",      2, 4),
            ("DHN2303",  "Communicable and Non-Communicable Disease",       7, 2, "CORE",      2, 4),
            ("DHN3102",  "Food Security",                                   7, 3, "CORE",      1, 2),
            ("DHN3103",  "Food Microbiology and Parasitology",              7, 4, "PRACTICAL", 2, 4),
            ("DHN3104",  "Diet Therapy III",                                7, 5, "CORE",      2, 4),
            ("DHN2304",  "Biochemistry II",                                 7, 6, "CORE",      2, 4),
            ("DHN3105",  "Nutrition Education and Counselling",             7, 7, "CORE",      2, 4),
            # ── Term 8 ──────────────────────────────────────────────────────
            ("DHN3201",  "Product Development, Marketing and Sales",        8, 1, "CORE",      1, 2),
            ("DHN3202",  "Industrial Organization and Management",          8, 2, "CORE",      1, 2),
            ("DHN3203",  "Nutrition Epidemiology",                          8, 3, "CORE",      2, 4),
            ("DHN3206",  "Community Partnership Skills",                    8, 4, "CORE",      1, 2),
            ("DHN3205",  "Trade Project and Business Plan",                 8, 5, "PROJECT",   1, 2),
            ("DHN3209",  "Agricultural Production",                         8, 6, "CORE",      2, 4),
            # ── Term 9 (Industrial Attachment II) ───────────────────────────
            ("DHN3301",  "Industrial Attachment II (Clinical Setting)",     9, 1, "PROJECT",   0, 480, False),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # DIPLOMA IN NUTRITION AND DIETETICS (TRANSITION)  (4 terms)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "code":        "DHNT",
        "name":        "DIPLOMA IN NUTRITION AND DIETETICS (TRANS)",
        "level":       "DIPLOMA",
        "total_terms": 4,
        "units": [
            # ── Term 1 ──────────────────────────────────────────────────────
            ("DHNT2301", "First Aid",                                       1, 1, "CORE",      1, 2),
            ("DHNT2302", "Introduction to Biostatistics",                   1, 2, "CORE",      2, 4),
            ("DHNT2303", "Introduction to Microbiology",                    1, 3, "CORE",      1, 2),
            ("DHNT2304", "Diet Therapy II",                                 1, 4, "CORE",      2, 4),
            ("DHNT2305", "Biochemistry I",                                  1, 5, "CORE",      1, 2),
            ("DHNT2306", "Principles of Food Processing and Preservation",  1, 6, "PRACTICAL", 2, 4),
            ("DHNT2307", "Research Methods",                                1, 7, "CORE",      2, 4),
            # ── Term 2 ──────────────────────────────────────────────────────
            ("DHNT3101", "Communicable Diseases",                           2, 1, "CORE",      1, 2),
            ("DHNT3102", "Principles of Nutrition and Behaviour",           2, 2, "CORE",      2, 4),
            ("DHNT3103", "Food Security",                                   2, 3, "CORE",      1, 2),
            ("DHNT3104", "Diet Therapy III",                                2, 4, "CORE",      2, 4),
            ("DHNT3105", "Community Partnership Skills",                    2, 5, "CORE",      1, 2),
            ("DHNT3106", "Non-Communicable Diseases",                       2, 6, "CORE",      1, 2),
            ("DHNT3107", "Biochemistry II",                                 2, 7, "CORE",      2, 4),
            # ── Term 3 ──────────────────────────────────────────────────────
            ("DHNT3201", "Nutrition Education and Counselling",             3, 1, "CORE",      2, 4),
            ("DHNT3202", "Food Microbiology and Parasitology",              3, 2, "PRACTICAL", 2, 4),
            ("DHNT3203", "Nutrition Epidemiology",                          3, 3, "CORE",      2, 4),
            ("DHNT3204", "Product Development, Marketing and Sales",        3, 4, "CORE",      1, 2),
            ("DHNT3205", "Industrial Organization and Management",          3, 5, "CORE",      1, 2),
            ("DHNT3206", "Trade Project and Business Plan",                 3, 6, "PROJECT",   1, 2),
            # ── Term 4 (Industrial Attachment) ──────────────────────────────
            ("DHNT3301", "Industrial Attachment",                           4, 1, "PROJECT",   0, 480, False),
        ],
    },
]
# fmt: on

# ─── Seed logic ────────────────────────────────────────────────────────────────

def parse_unit(t: tuple) -> dict:
    """Unpack a unit tuple into a dict. Handles 7- and 8-element tuples."""
    if len(t) == 8:
        code, name, term_number, position, unit_type, periods_per_week, credit_hours, is_active = t
    else:
        code, name, term_number, position, unit_type, periods_per_week, credit_hours = t
        is_active = True
    return dict(
        code=code,
        name=name,
        term_number=term_number,
        position=position,
        unit_type=unit_type,
        periods_per_week=periods_per_week,
        credit_hours=credit_hours,
        is_active=is_active,
    )


def seed():
    department = Department.objects.get(id=DEPARTMENT_ID)
    total_created = total_updated = 0

    for prog_def in PROGRAMMES:
        sep = "=" * 62
        print(f"\n{sep}\n{prog_def['name']}\n{sep}")

        programme, prog_created = Programme.objects.update_or_create(
            code=prog_def["code"],
            department=department,
            defaults={
                "name":          prog_def["name"],
                "level":         prog_def["level"],
                "total_terms":   prog_def["total_terms"],
                "sharing_group": SHARING_GROUP,
                "is_active":     True,
            },
        )
        action = "CREATED" if prog_created else "updated"
        print(f"  Programme {action}: {programme.id}")

        pc = pu = 0
        for raw in prog_def["units"]:
            u = parse_unit(raw)
            unit, created = CurriculumUnit.objects.update_or_create(
                programme=programme,
                code=u["code"],
                defaults={
                    "name":             u["name"],
                    "term_number":      u["term_number"],
                    "position":         u["position"],
                    "unit_type":        u["unit_type"],
                    "periods_per_week": u["periods_per_week"],
                    "credit_hours":     u["credit_hours"],
                    "is_active":        u["is_active"],
                    "notes":            "",
                },
            )
            flag = " [INACTIVE]" if not u["is_active"] else ""
            label = "Created" if created else "Updated"
            print(f"    {label}: [T{u['term_number']}] {u['code']}  {u['name']}{flag}")
            if created:
                pc += 1
            else:
                pu += 1

        print(f"  → {pc} created, {pu} updated")
        total_created += pc
        total_updated += pu

    print(f"\n{'─'*62}")
    print(f"TOTAL: {total_created} created, {total_updated} updated")
    print(f"{'─'*62}")
    for prog_def in PROGRAMMES:
        try:
            p = Programme.objects.get(code=prog_def["code"], department=department)
            total    = CurriculumUnit.objects.filter(programme=p).count()
            inactive = CurriculumUnit.objects.filter(programme=p, is_active=False).count()
            active   = total - inactive
            print(f"  {p.code:<6} {total:>3} units  ({active} active, {inactive} inactive)")
        except Programme.DoesNotExist:
            print(f"  {prog_def['code']}: NOT FOUND")


if __name__ == "__main__":
    seed()