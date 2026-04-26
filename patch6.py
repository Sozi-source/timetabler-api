path = 'timetable/scheduler.py'
with open(path, 'r', encoding='utf-8-sig') as f:
    content = f.read()
content = content.replace('\r\n', '\n')

old = (
    '                source_unit = max(cohort_unit_map.values(),\n'
    '                                 key=lambda u: u.qualified_trainers.count())\n'
    '                qualified = list(source_unit.qualified_trainers.filter(is_active=True))\n'
    '                if not qualified:\n'
    '                    continue'
)

new = (
    '                source_unit = max(cohort_unit_map.values(),\n'
    '                                 key=lambda u: u.qualified_trainers.count())\n'
    '                # Use intersection of qualified trainers across all units in group\n'
    '                trainer_id_sets = [\n'
    '                    set(u.qualified_trainers.filter(is_active=True).values_list("id", flat=True))\n'
    '                    for u in cohort_unit_map.values()\n'
    '                ]\n'
    '                common_ids = set.intersection(*trainer_id_sets) if trainer_id_sets else set()\n'
    '                if not common_ids:\n'
    '                    common_ids = set(\n'
    '                        source_unit.qualified_trainers.filter(is_active=True).values_list("id", flat=True)\n'
    '                    )\n'
    '                from timetable.models import Trainer as _T\n'
    '                qualified = list(_T.objects.filter(id__in=common_ids, is_active=True))\n'
    '                if not qualified:\n'
    '                    continue'
)

if old in content:
    content = content.replace(old, new)
    print('Fix OK')
else:
    print('MISS - showing context:')
    idx = content.find('source_unit = max')
    print(repr(content[idx-20:idx+300]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
