
c = open('timetable/scheduler.py', 'r', encoding='utf-8').read()
lines = c.splitlines(keepends=True)

# ── Find key line numbers ──────────────────────────────────────────────────
write_start = next(i for i,l in enumerate(lines) if '    def _write(' in l and 'self,' not in l)
write_end   = next(i for i in range(write_start+1, len(lines)) if lines[i].startswith('# ---') or (lines[i].startswith('    def ') and i > write_start+3))

combined_start = next(i for i,l in enumerate(lines) if 'ScheduledUnit.objects.update_or_create(' in l and 'cohort_unit' in lines[i-2])
combined_end   = next(i for i in range(combined_start, len(lines)) if 'return True' in lines[i]) + 1

run_delete_end = next(i for i,l in enumerate(lines) if "# 2. Load reference data" in l)

return_line = None
for i in range(len(lines)-1, 0, -1):
    if '        return result' in lines[i]:
        return_line = i
        break

print(f"_write block:    lines {write_start+1}-{write_end}")
print(f"combined block:  lines {combined_start+1}-{combined_end}")
print(f"run init at:     line  {run_delete_end+1}")
print(f"final return at: line  {return_line+1}")

# ── Build new _write method ───────────────────────────────────────────────
new_write = """    def _write(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainer:  Trainer,
        room:     Room,
        day:      str,
        period:   Period,
        sequence: int,
    ) -> ScheduledUnit:
        # Accumulate in memory — flushed to DB in one bulk_create at end of run()
        import uuid as _uuid
        entry = ScheduledUnit(
            id=str(_uuid.uuid4()),
            term=self.term,
            cohort=cohort,
            curriculum_unit=unit,
            period=period,
            trainer=trainer,
            room=room,
            day=day,
            sequence=sequence,
            status="DRAFT",
        )
        self._pending.append(entry)
        key = SlotKey(day, str(period.id))
        self.grid.mark(str(trainer.id), str(cohort.id), str(room.id), key)
        return entry

"""

# ── Build new combined block ──────────────────────────────────────────────
new_combined = """                for cohort in cohorts:
                    cohort_unit = cohort_unit_map[str(cohort.id)]
                    import uuid as _uuid
                    self._pending.append(ScheduledUnit(
                        id=str(_uuid.uuid4()),
                        term=self.term,
                        cohort=cohort,
                        curriculum_unit=cohort_unit,
                        period=period,
                        trainer=trainer,
                        room=room,
                        day=day,
                        sequence=0,
                        status="DRAFT",
                        is_combined=True,
                        combined_key=combined_key,
                    ))
                return True
"""

# ── Pending buffer init ───────────────────────────────────────────────────
pending_init = "        # 1b. Pending write buffer — flushed at end in one bulk_create\n        self._pending: list = []\n\n"

# ── Bulk create flush ─────────────────────────────────────────────────────
bulk_flush = """        # Flush all accumulated writes in ONE DB round-trip
        if self._pending:
            ScheduledUnit.objects.bulk_create(
                self._pending,
                update_conflicts=True,
                unique_fields=["term", "cohort", "curriculum_unit", "period"],
                update_fields=["trainer", "room", "day", "sequence", "status",
                               "is_combined", "combined_key"],
            )
"""

# ── Splice everything in (work from bottom to top to preserve line numbers) ─
# 1. Insert bulk_flush before final return
lines.insert(return_line, bulk_flush)

# 2. Insert pending_init before "# 2. Load reference data"  
lines.insert(run_delete_end, pending_init)

# Recalculate line numbers after insertions (both were before write_start)
offset = 2  # we inserted 2 blocks above write_start
write_start += offset
write_end   += offset
combined_start += offset
combined_end   += offset

# 3. Replace combined update_or_create block
lines[combined_start:combined_end] = [new_combined]

# 4. Replace _write method
# Find actual end of _write (just before next section or class-level def)
actual_write_end = write_end
new_lines = lines[:write_start] + [new_write] + lines[actual_write_end:]

result = ''.join(new_lines)

# Verify the changes landed
checks = [
    ('self._pending.append(entry)' in result, '_write uses _pending'),
    ('self._pending: list = []' in result, 'pending buffer init in run()'),
    ('bulk_create' in result, 'bulk_create flush present'),
    ('update_or_create' not in result.split('_try_place_combined')[1] if '_try_place_combined' in result else True, 'combined no longer uses update_or_create'),
]

all_ok = True
for ok, msg in checks:
    status = 'OK' if ok else 'FAIL'
    print(f"  {status}: {msg}")
    if not ok:
        all_ok = False

if all_ok:
    open('timetable/scheduler.py', 'w', encoding='utf-8').write(result)
    print("scheduler.py written successfully")
else:
    print("ABORTED — did not write file due to check failures")
    # Debug: show update_or_create occurrences
    for i, l in enumerate(result.splitlines(), 1):
        if 'update_or_create' in l:
            print(f"  update_or_create still at line {i}: {l.strip()}")
