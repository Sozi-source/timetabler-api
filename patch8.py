path = 'timetable/views.py'
with open(path, 'r', encoding='utf-8-sig') as f:
    content = f.read()
content = content.replace('\r\n', '\n')

# Find and replace the exact block using a unique marker
old_marker = '# Dedup drafts: keep lowest pk per (cohort/trainer/room'
new_line = '        # Dedup NON-combined drafts only: keep lowest pk per (cohort/trainer/room x day x period)\n        # Combined sessions legitimately share trainer/room slots across cohorts - skip them'

if old_marker not in content:
    print('MISS - marker not found')
else:
    # Replace the filter line inside the dedup loop
    old_filter = '                ScheduledUnit.objects.filter(term=term, status="DRAFT")\n                .values("id", field, "day", "period_id")'
    new_filter = '                ScheduledUnit.objects.filter(term=term, status="DRAFT", is_combined=False)\n                .values("id", field, "day", "period_id")'
    
    if old_filter in content:
        # Also fix the comment line
        idx = content.find(old_marker)
        end = content.find('\n', idx)
        content = content[:idx] + new_line + content[end:]
        content = content.replace(old_filter, new_filter)
        print('Fix OK')
    else:
        print('MISS - filter line not found')
        idx = content.find(old_marker)
        print(repr(content[idx:idx+300]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
