import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()
from timetable.models import Programme, Department, Trainer, CurriculumUnit

DEPARTMENT_ID = "837d0854-4e1f-4744-9afb-6fd4b9d12dfa"
SHARING_GROUP = "ICMHS_NUTRITION"
TRAINER_MAP = {
    "ICM001": "9a2f6634-96d9-4939-a7ea-7ad65e66caac",
    "ICM002": "2f42bf9c-bb33-4499-b483-bde56867ae30",
    "ICM003": "0790c314-a7b2-4be1-8910-2ad322914bd5",
    "ICM004": "6b6ea44c-cba1-4aa8-bfc9-d4f6dc8184be",
    "ICM005": "f3fefd6c-5c8e-4e0a-8244-6e2b6d09b0e0",
    "ICM006": "86e316e6-6797-4371-ae8d-6c7fbd90cac7",
    "ICM007": "30a68d02-4d7b-448b-a6c5-08f54a4dda41",
}
HOD="ICM001"; COORD="ICM002"; WAMBUI="ICM003"; WANJOHI="ICM004"; KWAMBOKA="ICM005"; AYUMA="ICM006"; KIRIMI="ICM007"
INACTIVE=False

PROGRAMMES = [
    {"name":"CERTIFICATE IN HUMAN NUTRITION","code":"CHN","level":"CERT","total_terms":6,"units":[
        ("CCU1101","Communication Skills",1,1,"CORE",2,2,[COORD,AYUMA]),
        ("CCU1102","Entrepreneurship",1,2,"CORE",2,2,[HOD,COORD]),
        ("CCU1105","HIV/AIDS Management",1,3,"CORE",2,2,[WANJOHI,AYUMA]),
        ("CCU1106","ICT",1,4,"CORE",4,4,[KIRIMI,AYUMA]),
        ("CCU1107","Human Anatomy and Physiology",1,5,"CORE",4,4,[WAMBUI]),
        ("CHN1101","Physical Sciences I",1,6,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("CHN1301","Diet Therapy",2,1,"CORE",4,4,[COORD,WAMBUI]),
        ("CHN1201","Principles of Human Nutrition",2,2,"CORE",4,4,[COORD,WAMBUI]),
        ("CHN1203","Food Safety and Hygiene",2,3,"CORE",2,2,[KWAMBOKA,AYUMA]),
        ("CHN1204","Physical Science II (Physics)",2,4,"CORE",2,2,[KIRIMI]),
        ("CHN1306","Legal Aspects in Nutrition and Dietetics",2,5,"CORE",4,4,[HOD,COORD]),
        ("CHN1304","Nutrition Care Process",2,6,"CORE",4,4,[COORD,WAMBUI]),
        ("CCU1111","Basic Mathematics",3,1,"CORE",4,4,[KIRIMI,AYUMA]),
        ("CHN1206","Meal Planning, Management and Service",3,2,"PRACTICAL",4,4,[KWAMBOKA,COORD]),
        ("CHN2205","Maternal and Child Nutrition",3,3,"CORE",4,4,[AYUMA,WAMBUI]),
        ("CHN2203","Food Production for Invalids and Convalescents",3,4,"PRACTICAL",4,4,[KWAMBOKA]),
        ("CHN2307","Nutrition in HIV/AIDS",3,5,"CORE",2,2,[WANJOHI,AYUMA]),
        ("CHN2302","Nutrition Anthropology",3,6,"CORE",2,2,[WANJOHI,COORD]),
        ("CHN1305","Introduction to Primary Health Care",3,7,"CORE",2,2,[WANJOHI,AYUMA]),
        ("CHN2304","Nutrition in Emergencies",4,1,"CORE",2,2,[WANJOHI,AYUMA]),
        ("CHN2207","Nutrition Assessment and Surveillance",4,2,"CORE",2,2,[AYUMA,COORD]),
        ("CHN2204","Nutrition in the Lifespan",4,3,"CORE",2,2,[COORD,WAMBUI]),
        ("CCU1110","Life Skills",4,4,"CORE",2,2,[AYUMA,WANJOHI]),
        ("CHN1308","Clinical Rotation",4,5,"PRACTICAL",8,1,[WAMBUI]),
        ("CHN1202","Food Science",4,6,"PRACTICAL",4,4,[KWAMBOKA]),
        ("CHN1303","Applied Biological Sciences",4,7,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("CHN2101","Industrial Attachment (Clinical Setting)",5,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
        ("CHN2305","Community Diagnosis and Mobilization",6,1,"CORE",2,2,[WANJOHI]),
        ("CHN2306","Demonstration Techniques",6,2,"PRACTICAL",2,2,[AYUMA,KWAMBOKA]),
        ("CHN2308","Nutrition for Vulnerable Groups",6,3,"CORE",2,2,[COORD,WAMBUI]),
        ("CHN2201","Introduction to Behavioural Science",6,4,"CORE",2,2,[AYUMA,WANJOHI]),
        ("CHN2202","Management of Malnutrition",6,5,"CORE",2,2,[COORD,WAMBUI]),
        ("CHN2309","Agricultural Production",6,6,"CORE",4,4,[WANJOHI]),
        ("CHN2206","Trade Project and Business Plan",6,7,"PROJECT",2,2,[HOD,COORD]),
    ]},
    {"name":"DIPLOMA IN NUTRITION AND DIETETICS","code":"DND","level":"DIPLOMA","total_terms":9,"units":[
        ("DND1101","Communication Skills",1,1,"CORE",2,2,[COORD,AYUMA]),
        ("DND1102","Entrepreneurship",1,2,"CORE",2,2,[HOD,COORD]),
        ("DND1103","HIV/AIDS Management",1,3,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND1104","Principles of Human Nutrition",1,4,"CORE",4,4,[COORD,WAMBUI]),
        ("DND1105","Human Anatomy and Physiology",1,5,"CORE",4,4,[WAMBUI]),
        ("DND1106","Applied Physical Sciences I (Chemistry)",1,6,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("DND1201","ICT",2,1,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DND1202","Diet Therapy I",2,2,"CORE",4,4,[COORD,WAMBUI]),
        ("DND1203","Food Safety and Hygiene",2,3,"CORE",2,2,[KWAMBOKA,AYUMA]),
        ("DND1204","Applied Physical Sciences II (Physics)",2,4,"CORE",2,2,[KIRIMI]),
        ("DND1205","Legal Aspects in Nutrition and Dietetics",2,5,"CORE",4,4,[HOD,COORD]),
        ("DND1206","Nutrition Care Process",2,6,"CORE",4,4,[COORD,WAMBUI]),
        ("DND1301","Basic Mathematics",3,1,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DND1302","Meal Planning, Management and Service",3,2,"PRACTICAL",4,4,[KWAMBOKA,COORD]),
        ("DND1303","Maternal and Child Nutrition",3,3,"CORE",2,2,[AYUMA,WAMBUI]),
        ("DND1304","Food Production for Invalids and Convalescent",3,4,"PRACTICAL",4,4,[KWAMBOKA]),
        ("DND1305","Nutrition in HIV and AIDS",3,5,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND1306","Nutrition Anthropology",3,6,"CORE",2,2,[WANJOHI,COORD]),
        ("DND1307","Introduction to Primary Health Care",3,7,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND2101","Management of Malnutrition",4,1,"CORE",2,2,[COORD,WAMBUI]),
        ("DND2102","Life Skills",4,2,"CORE",2,2,[AYUMA,WANJOHI]),
        ("DND2103","Clinical Rotation",4,3,"PRACTICAL",8,1,[WAMBUI]),
        ("DND2104","Nutrition in the Lifespan",4,4,"CORE",2,2,[COORD,WAMBUI]),
        ("DND2105","Diet Therapy II",4,5,"CORE",4,4,[COORD,WAMBUI]),
        ("DND2106","Principles of Food Processing and Preservation",4,6,"PRACTICAL",4,4,[KWAMBOKA]),
        ("DND2107","First Aid",4,7,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND2201","Industrial Attachment I",5,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
        ("DND2301","Nutrition in Emergencies",6,1,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND2302","Nutrition Assessment and Surveillance",6,2,"CORE",2,2,[AYUMA,COORD]),
        ("DND2303","Introduction to Microbiology",6,3,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DND2304","Introduction to Biostatistics",6,4,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DND2305","Biochemistry I",6,5,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DND2306","Research Methods",6,6,"CORE",4,4,[HOD,COORD]),
        ("DND2307","Principles of Nutrition and Behaviour",6,7,"CORE",2,2,[AYUMA,WANJOHI]),
        ("DND3101","Food Security",7,1,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND3102","Communicable and Non-Communicable Disease",7,2,"CORE",4,4,[WANJOHI,WAMBUI]),
        ("DND3103","Food Microbiology and Parasitology",7,3,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("DND3104","Diet Therapy III",7,4,"CORE",4,4,[COORD,WAMBUI]),
        ("DND3105","Community Partnership Skills",7,5,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DND3106","Biochemistry II",7,6,"CORE",4,4,[KIRIMI,KWAMBOKA]),
        ("DND3201","Product Development, Marketing and Sales",8,1,"CORE",2,2,[KWAMBOKA,COORD]),
        ("DND3202","Industrial Organization and Management",8,2,"CORE",2,2,[HOD,COORD]),
        ("DND3203","Nutrition Epidemiology",8,3,"CORE",4,4,[AYUMA,COORD]),
        ("DND3204","Nutrition Education and Counselling",8,4,"CORE",4,4,[AYUMA,WAMBUI]),
        ("DND3205","Agricultural Production",8,5,"CORE",4,4,[WANJOHI]),
        ("DND3206","Trade Project and Business Plan",8,6,"PROJECT",2,2,[HOD,COORD]),
        ("DND3301","Industrial Attachment II",9,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
    ]},
    {"name":"DIPLOMA IN HUMAN NUTRITION","code":"DHN","level":"DIPLOMA","total_terms":9,"units":[
        ("DCU1101","Communication Skills",1,1,"CORE",2,2,[COORD,AYUMA]),
        ("DCU1102","Entrepreneurship",1,2,"CORE",2,2,[HOD,COORD]),
        ("DCU1105","HIV/AIDS Management",1,3,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DCU1106","ICT",1,4,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DCU1107","Human Anatomy and Physiology",1,5,"CORE",4,4,[WAMBUI]),
        ("DHN1101","Physical Sciences I (Chemistry)",1,6,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("DHN1103","Introduction to Nutrition and Dietetics",1,7,"CORE",2,2,[COORD,WAMBUI]),
        ("DHN1203","Diet Therapy I",2,1,"CORE",4,4,[COORD,WAMBUI]),
        ("DHN1207","Principles of Human Nutrition",2,2,"CORE",4,4,[COORD,WAMBUI]),
        ("DHN1206","Food Safety and Hygiene",2,3,"CORE",2,2,[KWAMBOKA,AYUMA]),
        ("DHN1208","Physical Sciences II (Physics)",2,4,"CORE",2,2,[KIRIMI]),
        ("DHN1303","Legal Aspects in Nutrition and Dietetics",2,5,"CORE",4,4,[HOD,COORD]),
        ("DHN1307","Nutrition Care Process",2,6,"CORE",2,2,[COORD,WAMBUI]),
        ("DCU1111","Basic Mathematics",3,1,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DHN1209","Meal Planning, Management and Service",3,2,"PRACTICAL",4,4,[KWAMBOKA,COORD]),
        ("DHN1304","Maternal and Child Nutrition",3,3,"CORE",2,2,[AYUMA,WAMBUI]),
        ("DHN1305","Food Production for Invalids and Convalescent",3,4,"PRACTICAL",4,4,[KWAMBOKA]),
        ("DHN1205","Nutrition in HIV and AIDS",3,5,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN1209B","Nutrition Anthropology",3,6,"CORE",2,2,[WANJOHI,COORD]),
        ("DHN2207","Introduction to Primary Health Care",3,7,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN3204","Nutrition in Emergencies",4,1,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN3106","Nutrition Assessment and Surveillance",4,2,"CORE",2,2,[AYUMA,COORD]),
        ("DHN2302","Nutrition in the Lifespan",4,3,"CORE",2,2,[COORD,WAMBUI]),
        ("DHN1306","Clinical Rotation",4,4,"PRACTICAL",8,1,[WAMBUI]),
        ("DCU1110","Life Skills",4,5,"CORE",2,2,[AYUMA,WANJOHI]),
        ("DCU1104","First Aid",4,6,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN2101","Industrial Attachment I (Clinical Setting)",5,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
        ("DHN2201","Introduction to Microbiology",6,1,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DHN2202","Introduction to Biostatistics",6,2,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DHN2203","Biochemistry I",6,3,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DHN2204","Principles of Food Processing and Preservation",6,4,"PRACTICAL",4,4,[KWAMBOKA]),
        ("DHN2205","Diet Therapy II",6,5,"CORE",4,4,[COORD,WAMBUI]),
        ("DHN2305","Principles of Nutrition and Behaviour",6,6,"CORE",4,4,[AYUMA,WANJOHI]),
        ("DHN2201B","Management of Malnutrition",6,7,"CORE",2,2,[COORD,WAMBUI]),
        ("DHN2307","Research Methods",7,1,"CORE",4,4,[HOD,COORD]),
        ("DHN2303","Communicable and Non-Communicable Disease",7,2,"CORE",4,4,[WANJOHI,WAMBUI]),
        ("DHN3102","Food Security",7,3,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN3103","Food Microbiology and Parasitology",7,4,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("DHN3104","Diet Therapy III",7,5,"CORE",4,4,[COORD,WAMBUI]),
        ("DHN2304","Biochemistry II",7,6,"CORE",4,4,[KIRIMI,KWAMBOKA]),
        ("DHN3105","Nutrition Education and Counselling",7,7,"CORE",4,4,[AYUMA,WAMBUI]),
        ("DHN3201","Product Development, Marketing and Sales",8,1,"CORE",2,2,[KWAMBOKA,COORD]),
        ("DHN3202","Industrial Organization and Management",8,2,"CORE",2,2,[HOD,COORD]),
        ("DHN3203","Nutrition Epidemiology",8,3,"CORE",4,4,[AYUMA,COORD]),
        ("DHN3206","Community Partnership Skills",8,4,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHN3205","Trade Project and Business Plan",8,5,"PROJECT",2,2,[HOD,COORD]),
        ("DHN3209","Agricultural Production",8,6,"CORE",4,4,[WANJOHI]),
        ("DHN3301","Industrial Attachment II (Clinical Setting)",9,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
    ]},
    {"name":"DIPLOMA IN NUTRITION AND DIETETICS (TRANS)","code":"DHNT","level":"DIPLOMA","total_terms":4,"units":[
        ("DHNT2301","First Aid",1,1,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHNT2302","Introduction to Biostatistics",1,2,"CORE",4,4,[KIRIMI,AYUMA]),
        ("DHNT2303","Introduction to Microbiology",1,3,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DHNT2304","Diet Therapy II",1,4,"CORE",4,4,[COORD,WAMBUI]),
        ("DHNT2305","Basic Biochemistry I",1,5,"CORE",2,2,[KIRIMI,KWAMBOKA]),
        ("DHNT2306","Principles of Food Processing and Preservation",1,6,"PRACTICAL",4,4,[KWAMBOKA]),
        ("DHNT2307","Research Methods",1,7,"CORE",4,4,[HOD,COORD]),
        ("DHNT3101","Communicable Diseases",2,1,"CORE",2,2,[WANJOHI,WAMBUI]),
        ("DHNT3102","Principles of Nutrition and Behaviour",2,2,"CORE",4,4,[AYUMA,WANJOHI]),
        ("DHNT3103","Food Security",2,3,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHNT3104","Diet Therapy III",2,4,"CORE",4,4,[COORD,WAMBUI]),
        ("DHNT3105","Community Partnership Skills",2,5,"CORE",2,2,[WANJOHI,AYUMA]),
        ("DHNT3106","Non-Communicable Diseases",2,6,"CORE",2,2,[WANJOHI,WAMBUI]),
        ("DHNT3107","Basic Biochemistry II",2,7,"CORE",4,4,[KIRIMI,KWAMBOKA]),
        ("DHNT3201","Nutrition Education and Counselling",3,1,"CORE",4,4,[AYUMA,WAMBUI]),
        ("DHNT3202","Food Microbiology and Parasitology",3,2,"PRACTICAL",4,4,[KIRIMI,KWAMBOKA]),
        ("DHNT3203","Nutrition Epidemiology",3,3,"CORE",4,4,[AYUMA,COORD]),
        ("DHNT3204","Product Development, Marketing and Sales",3,4,"CORE",2,2,[KWAMBOKA,COORD]),
        ("DHNT3205","Industrial Organization and Management",3,5,"CORE",2,2,[HOD,COORD]),
        ("DHNT3206","Trade Project",3,6,"PROJECT",2,2,[HOD,COORD]),
        ("DHNT3301","Industrial Attachment",4,1,"PROJECT",0,0,[COORD,WAMBUI],INACTIVE),
    ]},
]

department = Department.objects.get(id=DEPARTMENT_ID)
trainers = {sid: Trainer.objects.get(id=uid) for sid, uid in TRAINER_MAP.items()}
total_created = 0; total_updated = 0

for prog_def in PROGRAMMES:
    print(f"\n{'='*60}\n{prog_def['name']}\n{'='*60}")
    programme, prog_created = Programme.objects.update_or_create(
        code=prog_def["code"], department=department,
        defaults={"name":prog_def["name"],"level":prog_def["level"],"total_terms":prog_def["total_terms"],"sharing_group":SHARING_GROUP,"is_active":True}
    )
    print(f"  Programme {'created' if prog_created else 'updated'}: {programme.id}")
    pc = 0; pu = 0
    for unit_tuple in prog_def["units"]:
        if len(unit_tuple)==8:
            code,name,term_num,position,unit_type,credit_hours,ppw,trainer_ids=unit_tuple; is_active=True
        else:
            code,name,term_num,position,unit_type,credit_hours,ppw,trainer_ids,is_active=unit_tuple
        unit,created=CurriculumUnit.objects.update_or_create(
            programme=programme,code=code,
            defaults={"name":name,"term_number":term_num,"position":position,"unit_type":unit_type,"credit_hours":credit_hours,"periods_per_week":ppw,"is_active":is_active,"notes":""}
        )
        unit.qualified_trainers.set([trainers[sid] for sid in trainer_ids])
        flag="" if is_active else " [INACTIVE]"
        print(f"  {'Created' if created else 'Updated'}: [T{term_num}] {code} {name}{flag}")
        if created: pc+=1
        else: pu+=1
    print(f"  -> {pc} created, {pu} updated")
    total_created+=pc; total_updated+=pu

print(f"\nDONE: {total_created} created, {total_updated} updated")
for prog_def in PROGRAMMES:
    try:
        p=Programme.objects.get(code=prog_def["code"],department=department)
        c=CurriculumUnit.objects.filter(programme=p).count()
        i=CurriculumUnit.objects.filter(programme=p,is_active=False).count()
        print(f"  {p.code}: {c} units ({i} inactive)")
    except: print(f"  {prog_def['code']}: not found")