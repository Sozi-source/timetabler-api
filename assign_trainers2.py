from timetable.models import CurriculumUnit, Trainer

mary    = Trainer.objects.get(last_name='Kaganjo')
milkah  = Trainer.objects.get(last_name='Wambui')
fiona   = Trainer.objects.get(last_name='Kwamboka')
maureen = Trainer.objects.get(last_name='Ayuma')

assignments = [
    ('CHN1202', [fiona, maureen]),
    ('CHN1308', [mary, fiona]),
    ('CHN2309', [milkah, fiona]),
    ('CHN2306', [milkah, fiona]),
    ('DHN3201', [mary, fiona]),
    ('DHN1306', [mary, fiona]),
    ('DHN2204', [milkah, fiona]),
    ('DHNT3204', [mary, fiona]),
    ('DHNT3201', [mary, milkah]),
    ('DND1206', [mary, fiona]),
    ('CND1106', [fiona, maureen]),
]

for code, trainers in assignments:
    for u in CurriculumUnit.objects.filter(code=code):
        for t in trainers:
            u.qualified_trainers.add(t)
        current = list(u.qualified_trainers.values_list('last_name', flat=True))
        print(code, u.programme.code, current)
