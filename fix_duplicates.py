import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetabler.settings')
django.setup()

from timetable.models import ScheduledUnit, Term, Cohort
from django.db.models import Count

term = Term.objects.filter(is_current=True).first()
deleted_total = 0

cohorts = Cohort.objects.filter(is_active=True)
for cohort in cohorts:
    # Find duplicated curriculum_unit placements for this cohort
    dups = (ScheduledUnit.objects
            .filter(cohort=cohort, term=term, status='DRAFT')
            .values('curriculum_unit')
            .annotate(n=Count('id'))
            .filter(n__gt=1))

    for dup in dups:
        cu_id = dup['curriculum_unit']
        entries = list(ScheduledUnit.objects
                       .filter(cohort=cohort, term=term, status='DRAFT', curriculum_unit_id=cu_id)
                       .order_by('created_at'))
        # Keep the first, delete the rest
        to_delete = entries[1:]
        for e in to_delete:
            e.delete()
            deleted_total += 1
        print(f"  {cohort.name} | {entries[0].curriculum_unit.code} | kept 1, deleted {len(to_delete)}")

print(f"\nTotal duplicates removed: {deleted_total}")
