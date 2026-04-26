import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8-sig") as f:
    content = f.read()

content = content.replace("\r\n", "\n")

old = '''            # Find overlapping units
            unit_sets = []
            for cid in group_cohort_ids:
                _, units = work_queue[cid]
                unit_sets.append({str(u.id): u for u in units})

            shared_ids = set(unit_sets[0].keys())
            for s in unit_sets[1:]:
                shared_ids &= set(s.keys())

            if not shared_ids:
                continue

            cohorts_in_group = [work_queue[cid][0] for cid in group_cohort_ids]
            combined_students = sum(c.student_count for c in cohorts_in_group)

            # Large pass_cfg for combined classes (strict)
            cfg = {"name": "COMBINED", "allow_overlap": False, "max_attempts": 80, "skip_soft": False}

            for uid in shared_ids:
                unit = unit_sets[0][uid]
                combined_key = f"{group}_{uid}"
                if combined_key in placed_combined_keys:
                    continue

                qualified = list(unit.qualified_trainers.filter(is_active=True))
                if not qualified:
                    continue

                # Need a room big enough for all cohorts combined
                big_rooms = [r for r in rooms if r.capacity >= combined_students]
                if not big_rooms:
                    big_rooms = sorted(rooms, key=lambda r: -r.capacity)[:1]

                ok = self._try_place_combined(
                    unit, cohorts_in_group, qualified, big_rooms,
                    days, periods, grid, cindex, cfg, combined_key
                )
                if ok:
                    placed_combined_keys.add(combined_key)
                    # Remove from individual cohort queues
                    for cid in group_cohort_ids:
                        _, units = work_queue[cid]
                        work_queue[cid] = (work_queue[cid][0], [u for u in units if str(u.id) != uid])
                    placed += 1'''

new = '''            # Find overlapping units by NAME (units with same name across cohorts in group)
            # Build map: unit_name -> {cohort_id: unit}
            from collections import defaultdict
            name_to_cohort_units = defaultdict(dict)
            for cid in group_cohort_ids:
                _, units = work_queue[cid]
                for u in units:
                    if not getattr(u, 'is_outsourced', False):
                        name_to_cohort_units[u.name.strip()][cid] = u

            # Only combine names that appear in 2+ cohorts
            shared_names = {name: cu_map for name, cu_map in name_to_cohort_units.items()
                           if len(cu_map) >= 2}

            if not shared_names:
                continue

            cfg = {"name": "COMBINED", "allow_overlap": False, "max_attempts": 80, "skip_soft": False}

            for unit_name, cohort_unit_map in shared_names.items():
                combined_key = f"{group}_{unit_name}"
                if combined_key in placed_combined_keys:
                    continue

                cohorts_in_combined = [work_queue[cid][0] for cid in cohort_unit_map.keys()]
                combined_students = sum(c.student_count for c in cohorts_in_combined)

                # Use the unit with the most trainers as source
                source_unit = max(cohort_unit_map.values(),
                                 key=lambda u: u.qualified_trainers.count())
                qualified = list(source_unit.qualified_trainers.filter(is_active=True))
                if not qualified:
                    continue

                big_rooms = [r for r in rooms if r.capacity >= combined_students]
                if not big_rooms:
                    big_rooms = sorted(rooms, key=lambda r: -r.capacity)[:1]

                all_units_in_combined = list(cohort_unit_map.values())
                ok = self._try_place_combined(
                    source_unit, cohorts_in_combined, qualified, big_rooms,
                    days, periods, grid, cindex, cfg, combined_key,
                    all_units=all_units_in_combined
                )
                if ok:
                    placed_combined_keys.add(combined_key)
                    # Remove all matched units from individual queues
                    for cid, unit in cohort_unit_map.items():
                        _, units = work_queue[cid]
                        work_queue[cid] = (work_queue[cid][0],
                                          [u for u in units if u.id != unit.id])
                    placed += 1'''

if old in content:
    content = content.replace(old, new)
    print("Fix 1 OK: combined matcher updated to use names")
else:
    print("Fix 1 MISS")

# Fix 2: update _try_place_combined to accept all_units and write each cohort's own unit
old2 = '''    def _try_place_combined(
        self, unit, cohorts, trainers, rooms, days, periods, grid, cindex, cfg, combined_key
    ) -> bool:
        for day in days:
            for period in periods:
                key = SlotKey(day, str(period.id))
                # All cohorts free?
                if any(grid.cohort_busy(str(c.id), key) for c in cohorts):
                    continue
                trainer = None
                for t in trainers:
                    if not grid.trainer_busy(str(t.id), key) and not cindex.trainer_blocked(str(t.id), key):
                        trainer = t
                        break
                if trainer is None:
                    continue
                room = next((r for r in rooms if not grid.room_busy(str(r.id), key)), None)
                if room is None:
                    continue
                # Place for all cohorts
                for cohort in cohorts:
                    ScheduledUnit.objects.update_or_create(
                        term=self.term,
                        cohort=cohort,
                        curriculum_unit=unit,
                        period=period,
                        defaults={
                            "trainer":     trainer,
                            "room":        room,
                            "day":         day,
                            "sequence":    0,
                            "status":      "DRAFT",
                            "is_combined": True,
                            "combined_key": combined_key,
                        },
                    )
                    grid.mark(str(trainer.id), str(cohort.id), str(room.id), key)
                return True
        return False'''

new2 = '''    def _try_place_combined(
        self, unit, cohorts, trainers, rooms, days, periods, grid, cindex, cfg, combined_key,
        all_units=None
    ) -> bool:
        # all_units: list of CurriculumUnit, one per cohort (same order as cohorts)
        # If not provided, use the same unit for all cohorts
        cohort_unit_map = {}
        if all_units:
            for c, u in zip(cohorts, all_units):
                cohort_unit_map[str(c.id)] = u
        else:
            for c in cohorts:
                cohort_unit_map[str(c.id)] = unit

        for day in days:
            for period in periods:
                key = SlotKey(day, str(period.id))
                if any(grid.cohort_busy(str(c.id), key) for c in cohorts):
                    continue
                trainer = None
                for t in trainers:
                    if not grid.trainer_busy(str(t.id), key) and not cindex.trainer_blocked(str(t.id), key):
                        trainer = t
                        break
                if trainer is None:
                    continue
                room = next((r for r in rooms if not grid.room_busy(str(r.id), key)), None)
                if room is None:
                    continue
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
                    grid.mark(str(trainer.id), str(cohort.id), str(room.id), key)
                return True
        return False'''

if old2 in content:
    content = content.replace(old2, new2)
    print("Fix 2 OK: _try_place_combined updated")
else:
    print("Fix 2 MISS")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
