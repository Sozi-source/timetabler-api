import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8-sig") as f:
    content = f.read()

content = content.replace("\r\n", "\n")

# Find the exact location using a unique substring
marker = 'cohort_unit_map[str(cohort.id)]\n                    ScheduledUnit.objects.update_or_create('
idx = content.find(marker)
if idx == -1:
    print("ERROR: marker not found")
    sys.exit(1)

# Find the start of 'for cohort in cohorts:' before the marker
start = content.rfind("                for cohort in cohorts:", 0, idx)
if start == -1:
    print("ERROR: for loop start not found")
    sys.exit(1)

# Find 'return True' after the marker
end_marker = "                return True"
end = content.find(end_marker, idx)
if end == -1:
    print("ERROR: return True not found")
    sys.exit(1)
end += len(end_marker)

old_block = content[start:end]
print("Found block:")
print(repr(old_block[:100]))

new_block = '''                # Mark trainer+room+first cohort in grid before placing
                grid.mark(str(trainer.id), str(cohorts[0].id), str(room.id), key)
                for cohort in cohorts:
                    cohort_unit = cohort_unit_map[str(cohort.id)]
                    ScheduledUnit.objects.update_or_create(
                        term=self.term,
                        cohort=cohort,
                        curriculum_unit=cohort_unit,
                        period=period,
                        defaults={
                            "trainer":      trainer,
                            "room":         room,
                            "day":          day,
                            "sequence":     0,
                            "status":       "DRAFT",
                            "is_combined":  True,
                            "combined_key": combined_key,
                        },
                    )
                    # Mark additional cohort slots as busy
                    if str(cohort.id) != str(cohorts[0].id):
                        grid._cohort[str(cohort.id)].add(key)
                        grid._cohort_day_count[str(cohort.id)][key.day] += 1
                return True'''

content = content[:start] + new_block + content[end:]

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fix OK: grid.mark() added to _try_place_combined")
