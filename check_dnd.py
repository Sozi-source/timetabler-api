from timetable.models import Term, ScheduledUnit, Cohort, Period, CurriculumUnit, Programme

term = Term.objects.filter(is_current=True).first()
cohort = Cohort.objects.get(name__icontains='DND JAN 26')

entries = ScheduledUnit.objects.filter(term=term, cohort=cohort, status='DRAFT').values('day','period_id','curriculum_unit__code')
print('DND JAN 26 scheduled slots:')
for e in sorted(entries, key=lambda x: (x['day'], str(x['period_id']))):
    print(f"  {e['day']} period={e['period_id']}  unit={e['curriculum_unit__code']}")

print()
periods = Period.objects.filter(is_break=False)
for p in periods:
    days_used = list(ScheduledUnit.objects.filter(term=term, cohort=cohort, period=p, status='DRAFT').values_list('day', flat=True))
    print(f'Period {p.label} (id={p.id}): used on {days_used}')

print()
print('DND Term 2 units:')
prog = Programme.objects.get(code='DND')
units = CurriculumUnit.objects.filter(programme=prog, term_number=2, is_active=True)
for u in units:
    placed = ScheduledUnit.objects.filter(term=term, curriculum_unit=u, status='DRAFT').count()
    trainers = list(u.qualified_trainers.filter(is_active=True).values_list('first_name', flat=True))
    print(f'  {u.code}  type={u.unit_type}  ppw={u.periods_per_week}  placed={placed}  trainers={trainers}')
