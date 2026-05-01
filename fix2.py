c=open('timetable/scheduler.py','r',encoding='utf-8').read()
o='.prefetch_related("qualified_trainers")'
n='.prefetch_related("qualified_trainers","unit_trainers__trainer")'
r=c.replace(o,n)
open('timetable/scheduler.py','w',encoding='utf-8').write(r)
print('done' if o in c else 'NOT FOUND')
