path = 'timetable/scheduler.py'
with open(path, 'r', encoding='utf-8-sig') as f:
    content = f.read()
content = content.replace('\r\n', '\n')

old = (
    '                # Mark trainer+room+first cohort in grid before placing\n'
    '                grid.mark(str(trainer.id), str(cohorts[0].id), str(room.id), key)\n'
    '                for cohort in cohorts:\n'
    '                    cohort_unit = cohort_unit_map[str(cohort.id)]\n'
    '                    ScheduledUnit.objects.update_or_create(\n'
    '                        term=self.term,\n'
    '                        cohort=cohort,\n'
    '                        curriculum_unit=cohort_unit,\n'
    '                        period=period,\n'
    '                        defaults={\n'
    '                            "trainer":      trainer,\n'
    '                            "room":         room,\n'
    '                            "day":          day,\n'
    '                            "sequence":     0,\n'
    '                            "status":       "DRAFT",\n'
    '                            "is_combined":  True,\n'
    '                            "combined_key": combined_key,\n'
    '                        },\n'
    '                    )\n'
    '                    # Mark additional cohort slots as busy\n'
    '                    if str(cohort.id) != str(cohorts[0].id):\n'
    '                        grid._cohort[str(cohort.id)].add(key)\n'
    '                        grid._cohort_day_count[str(cohort.id)][key.day] += 1\n'
    '                return True'
)

new = (
    '                # Mark trainer+room+first cohort in grid before placing\n'
    '                grid.mark(str(trainer.id), str(cohorts[0].id), str(room.id), key)\n'
    '                # Mark ALL remaining cohorts so individual pass cannot reuse this trainer slot\n'
    '                for _c in cohorts[1:]:\n'
    '                    grid._cohort[str(_c.id)].add(key)\n'
    '                    grid._cohort_day_count[str(_c.id)][key.day] += 1\n'
    '                # Mark trainer slot as globally busy (block for all cohorts)\n'
    '                for _c in cohorts[1:]:\n'
    '                    grid._trainer[str(trainer.id)].add(key)\n'
    '                for cohort in cohorts:\n'
    '                    cohort_unit = cohort_unit_map[str(cohort.id)]\n'
    '                    ScheduledUnit.objects.update_or_create(\n'
    '                        term=self.term,\n'
    '                        cohort=cohort,\n'
    '                        curriculum_unit=cohort_unit,\n'
    '                        period=period,\n'
    '                        defaults={\n'
    '                            "trainer":      trainer,\n'
    '                            "room":         room,\n'
    '                            "day":          day,\n'
    '                            "sequence":     0,\n'
    '                            "status":       "DRAFT",\n'
    '                            "is_combined":  True,\n'
    '                            "combined_key": combined_key,\n'
    '                        },\n'
    '                    )\n'
    '                return True'
)

if old in content:
    content = content.replace(old, new)
    print('Fix OK: trainer slot now marked busy for all cohorts after combined placement')
else:
    print('MISS')
    idx = content.find('Mark trainer+room+first')
    print(repr(content[idx-10:idx+400]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
