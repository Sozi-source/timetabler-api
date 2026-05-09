lines = open('timetable/views.py', encoding='utf-8').readlines()

# Find ConflictListView
start = None
for i, l in enumerate(lines):
    if 'class ConflictListView' in l:
        start = i
        break

if start is None:
    print('NOT FOUND')
else:
    for i, l in enumerate(lines[start:start+12], start=start+1):
        print(i, repr(l))
