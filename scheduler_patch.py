import re

with open('timetable/scheduler.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    # -- Double / consecutive periods ---------------------------------------

    def _place_double(
        self, cohort: Cohort, unit: CurriculumUnit, trainers: list[Trainer]
    ) -> PlacementResult:
        uid = str(unit.id)
        cid = str(cohort.id)

        pairs: list[tuple[Period, Period]] = [
            (self.periods[i], self.periods[i + 1])
            for i in range(len(self.periods) - 1)
            if not self.periods[i].is_break and not self.periods[i + 1].is_break
        ]

        if not pairs:
            return PlacementResult(False, unit, cohort, "No consecutive period pairs configured")

        avoided_days = self.cindex.get_avoided_days(uid, cid)
        pinned_day   = self.cindex.get_pinned_day(uid, cid)

        if pinned_day:
            candidate_days = [pinned_day] if pinned_day in self.days else list(self.days)
        else:
            candidate_days = [d for d in self.days if d not in avoided_days] or list(self.days)

        shuffled_days = candidate_days[:]
        random.shuffle(shuffled_days)
        candidates = [(d, pa, pb) for d in shuffled_days for pa, pb in pairs]

        for day, pa, pb in candidates:
            result = self._try_double_slot(cohort, unit, trainers, day, pa, pb)
            if result.success:
                return result

        return PlacementResult(False, unit, cohort, "No free consecutive pair found", self.cfg["name"])'''

new = '''    # -- Double / consecutive periods ---------------------------------------

    def _place_double(
        self, cohort: Cohort, unit: CurriculumUnit, trainers: list[Trainer]
    ) -> PlacementResult:
        uid = str(unit.id)
        cid = str(cohort.id)

        pairs: list[tuple[Period, Period]] = [
            (self.periods[i], self.periods[i + 1])
            for i in range(len(self.periods) - 1)
            if not self.periods[i].is_break and not self.periods[i + 1].is_break
        ]

        if not pairs:
            return PlacementResult(False, unit, cohort, "No consecutive period pairs configured")

        avoided_days = self.cindex.get_avoided_days(uid, cid)
        pinned_day   = self.cindex.get_pinned_day(uid, cid)

        if pinned_day:
            candidate_days = [pinned_day] if pinned_day in self.days else list(self.days)
        else:
            candidate_days = [d for d in self.days if d not in avoided_days] or list(self.days)

        shuffled_days = candidate_days[:]
        random.shuffle(shuffled_days)

        # PASS 1 — prefer days where this cohort has NO other sessions yet.
        # This spreads double-period units across the week rather than stacking
        # them on days already occupied by the cohort.
        light_days  = [d for d in shuffled_days if self.grid.cohort_day_periods(cid, d) == 0]
        medium_days = [d for d in shuffled_days if 0 < self.grid.cohort_day_periods(cid, d) < 3]
        heavy_days  = [d for d in shuffled_days if self.grid.cohort_day_periods(cid, d) >= 3]

        ordered_days = light_days + medium_days + heavy_days

        for day in ordered_days:
            for pa, pb in pairs:
                result = self._try_double_slot(cohort, unit, trainers, day, pa, pb)
                if result.success:
                    return result

        return PlacementResult(False, unit, cohort, "No free consecutive pair found", self.cfg["name"])'''

if old in content:
    content = content.replace(old, new)
    with open('timetable/scheduler.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: _place_double patched')
else:
    print('ERROR: Pattern not found')
