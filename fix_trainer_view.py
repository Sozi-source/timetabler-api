content = open('timetable/views.py', 'r', encoding='utf-8').read()
old = 'ScheduledUnit.objects.filter(term=term, trainer=trainer, status="PUBLISHED")'
new = 'ScheduledUnit.objects.filter(term=term, trainer=trainer, status=request.query_params.get("status", "DRAFT"))'
if old in content:
    content = content.replace(old, new)
    open('timetable/views.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - string not found')
