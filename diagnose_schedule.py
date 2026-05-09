import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetabler.settings')
django.setup()

from timetable.models import ScheduledUnit, Term, Cohort, CurriculumUnit
from django.db.models import Count

term = Term.objects.filter(is_current=True).first()

# CHN SEPT 24 - what's missing
c = Cohort.objects.get(name='CHN SEPT 24')
placed_codes = set(ScheduledUnit.objects.filter(cohort=c, term=term, status='DRAFT').values_list('curriculum_unit__code', flat=True))
expected = CurriculumUnit.objects.filter(programme=c.programme, term_number=c.current_term, is_active=True)
print('=== CHN SEPT 24 missing ===')
for u in expected:
    if u.code not in placed_codes:
        print(f'  {u.code}  {u.name}  trainer_required={u.requires_trainer if hasattr(u, "requires_trainer") else "N/A"}')

# Over-placed cohorts - find duplicates
print()
for name in ['DHN MAY 24', 'CND SEPT 25', 'CHN MAY 25', 'DHN SEPT 24', 'DHNT SEPT 25', 'DND JAN 26', 'DND SEPT 25', 'DHN MAY 25', 'CND JAN 26']:
    try:
        cx = Cohort.objects.get(name=name)
    except:
        continue
    dups = (ScheduledUnit.objects
            .filter(cohort=cx, term=term, status='DRAFT')
            .values('curriculum_unit__code')
            .annotate(n=Count('id'))
            .filter(n__gt=1))
    if dups:
        print(f'=== {name} duplicates ===')
        for d in dups:
            print(f"  {d['curriculum_unit__code']} x{d['n']}")
