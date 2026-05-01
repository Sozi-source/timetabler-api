c=open('timetable/scheduler.py','r',encoding='utf-8').read()
fixes=[]
old1=c[c.find('def _write'):c.find('# -- Pass configurations')].rstrip()
print('old1 length:',len(old1))
print(repr(old1[-100:]))
