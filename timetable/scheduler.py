"""
timetable/scheduler.py
======================
Industry-standard constraint-based timetable generator.

Architecture
------------
1. OccupancyGrid     – O(1) lookup for trainer/cohort/room availability
2. ConstraintIndex   – fast access to all rules for a unit/cohort/trainer
3. CandidateBuilder  – builds ordered slot candidates from constraints
4. Placer            – tries to place one (cohort, unit) pair
5. TimetableEngine   – orchestrates the whole generation run

Generation strategy
-------------------
Priority order (most constrained first):
  1. Hard-pinned units (PIN_DAY_PERIOD constraints)
  2. Combined/shared units (multiple cohorts, large rooms needed)
  3. Double/consecutive period units
  4. Single period units sorted by fewest available trainers (tightest first)

Conflict resolution
-------------------
  PASS 1 – Strict:    respects all hard constraints, no overlap
  PASS 2 – Relaxed:   soft constraints may be skipped
  PASS 3 – Emergency: trainer clash allowed with Conflict log, room reused

Any unresolved unit after all passes → Conflict record (HIGH severity).
Coordinator resolves via dashboard.

Fixes applied (2026-05-01)
--------------------------
BUG 1: Only one cohort scheduled
  - _sort_by_difficulty now snapshots unit lists AFTER combined scheduling
    so mutations don't produce empty lists for cohorts.
  - Empty cohort lists are filtered out before main scheduling loop.
  - Unplaced units with no trainers now log a Conflict instead of silently
    disappearing.

BUG 2: Constraints (PIN_DAY_PERIOD) not respected
  - ConstraintIndex.get_pin() now also reads constraints saved with
    curriculum_unit_id set (not just those indexed at load time, which
    required the view to pass "unit_id" correctly).
  - Added get_pinned_day() for PIN_DAY rule support.
  - _place_single now filters candidate days using PIN_DAY constraints too.
  - Constraint POST in views.py must pass "unit_id" key (see views.py fix).

PERF (2026-05-01)
-----------------
  - All ScheduledUnit DB writes are now deferred and flushed as a single
    bulk_create(update_conflicts=True) call at the end of run().
    This eliminates N+1 round-trips to the remote DB (was ~25 individual
    update_or_create calls × ~4 s latency = 100 s wasted).
  - _sort_by_difficulty uses prefetched qualified_trainers (no extra queries).
  - Conflict rows are also bulk_created in one call.
"""

from __future__ import annotations

import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction
from django.db.models import Prefetch, Q

from .models import (
    Cohort, Conflict, Constraint, CurriculumUnit,
    Period, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SlotKey:
    day: str
    period_id: str          # Period.pk (string form)

    def __hash__(self):
        return hash((self.day, self.period_id))

    def __eq__(self, other):
        return self.day == other.day and self.period_id == other.period_id


@dataclass
class PlacementResult:
    success:   bool
    unit:      CurriculumUnit = None
    cohort:    Cohort = None
    reason:    str = ""
    pass_name: str = ""


@dataclass
class GenerationResult:
    term:                Term = None
    placed:              int = 0
    total_required:      int = 0
    combined_placed:     int = 0
    unresolved:          list = field(default_factory=list)
    emergency_placements: list = field(default_factory=list)

    def summary(self) -> dict:
        from timetable.models import ScheduledUnit, Cohort, CurriculumUnit
        placed = ScheduledUnit.objects.filter(
            term=self.term, status="DRAFT"
        ).values("cohort", "curriculum_unit").distinct().count()

        total = 0
        for c in Cohort.objects.filter(is_active=True):
            total += CurriculumUnit.objects.filter(
                programme=c.programme,
                term_number=c.current_term,
                is_active=True,
                is_outsourced=False,
            ).count()

        rate = round(placed / total * 100, 1) if total else 0
        return {
            "term":               str(self.term),
            "placed":             placed,
            "total_required":     total,
            "completion_rate":    rate,
            "combined_placed":    self.combined_placed,
            "unresolved_count":   len(self.unresolved),
            "emergency_count":    len(self.emergency_placements),
            "unresolved":         self.unresolved,
            "emergency_placements": self.emergency_placements,
        }


# ---------------------------------------------------------------------------
# OccupancyGrid
# ---------------------------------------------------------------------------

class OccupancyGrid:
    """
    In-memory O(1) occupancy tracker.
    Built from ONE query on existing ScheduledUnit rows for the term.
    Updated as new slots are placed (no further DB reads needed).
    """

    def __init__(self):
        self._trainer: dict[str, set[SlotKey]] = defaultdict(set)
        self._cohort:  dict[str, set[SlotKey]] = defaultdict(set)
        self._room:    dict[str, set[SlotKey]] = defaultdict(set)
        self._trainer_day_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._cohort_day_count:  dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    @classmethod
    def build(cls, term: Term) -> "OccupancyGrid":
        grid = cls()
        qs = ScheduledUnit.objects.filter(
            term=term, status__in=["DRAFT", "PUBLISHED"]
        ).values("trainer_id", "cohort_id", "room_id", "day", "period_id")
        for row in qs:
            key = SlotKey(row["day"], str(row["period_id"]))
            grid._trainer[str(row["trainer_id"])].add(key)
            grid._cohort[str(row["cohort_id"])].add(key)
            grid._room[str(row["room_id"])].add(key)
            grid._trainer_day_count[str(row["trainer_id"])][row["day"]] += 1
            grid._cohort_day_count[str(row["cohort_id"])][row["day"]] += 1
        return grid

    def trainer_busy(self, trainer_id: str, key: SlotKey) -> bool:
        return key in self._trainer[trainer_id]

    def cohort_busy(self, cohort_id: str, key: SlotKey) -> bool:
        return key in self._cohort[cohort_id]

    def room_busy(self, room_id: str, key: SlotKey) -> bool:
        return key in self._room[room_id]

    def trainer_day_periods(self, trainer_id: str, day: str) -> int:
        return self._trainer_day_count[trainer_id][day]

    def cohort_day_periods(self, cohort_id: str, day: str) -> int:
        return self._cohort_day_count[cohort_id][day]

    def mark(self, trainer_id: str, cohort_id: str, room_id: str, key: SlotKey) -> None:
        self._trainer[trainer_id].add(key)
        self._cohort[cohort_id].add(key)
        self._room[room_id].add(key)
        self._trainer_day_count[trainer_id][key.day] += 1
        self._cohort_day_count[cohort_id][key.day] += 1

    def unmark(self, trainer_id: str, cohort_id: str, room_id: str, key: SlotKey) -> None:
        self._trainer[trainer_id].discard(key)
        self._cohort[cohort_id].discard(key)
        self._room[room_id].discard(key)
        self._trainer_day_count[trainer_id][key.day] = max(
            0, self._trainer_day_count[trainer_id][key.day] - 1
        )
        self._cohort_day_count[cohort_id][key.day] = max(
            0, self._cohort_day_count[cohort_id][key.day] - 1
        )


# ---------------------------------------------------------------------------
# ConstraintIndex
# ---------------------------------------------------------------------------

class ConstraintIndex:
    """
    Pre-loads all active constraints for a term's units, cohorts, and trainers.
    Provides fast look-up helpers used by the Placer.

    FIX: constraints are now also indexed by curriculum_unit_id directly so
    that PIN_DAY_PERIOD rules are always found regardless of how the view
    saved them.
    """

    def __init__(self, term: Term, unit_ids, cohort_ids, trainer_ids):
        self._by_unit:    dict[str, list[Constraint]] = defaultdict(list)
        self._by_cohort:  dict[str, list[Constraint]] = defaultdict(list)
        self._by_trainer: dict[str, list[Constraint]] = defaultdict(list)

        qs = Constraint.objects.filter(
            is_active=True
        ).filter(
            Q(curriculum_unit_id__in=unit_ids) |
            Q(cohort_id__in=cohort_ids) |
            Q(trainer_id__in=trainer_ids)
        ).select_related("curriculum_unit", "cohort", "trainer")

        for c in qs:
            if c.curriculum_unit_id:
                self._by_unit[str(c.curriculum_unit_id)].append(c)
            if c.cohort_id:
                self._by_cohort[str(c.cohort_id)].append(c)
            if c.trainer_id:
                self._by_trainer[str(c.trainer_id)].append(c)

        # Pre-load trainer unavailability
        self._blocked: dict[str, set[SlotKey]] = defaultdict(set)
        avail_qs = TrainerAvailability.objects.filter(
            term=term, is_available=False, trainer_id__in=trainer_ids
        ).select_related("period")
        for av in avail_qs:
            if av.period_id:
                self._blocked[str(av.trainer_id)].add(
                    SlotKey(av.day, str(av.period_id))
                )
            else:
                # Whole day blocked
                self._blocked[str(av.trainer_id)].add(
                    SlotKey(av.day, "__ALL__")
                )

    def unit_constraints(self, unit_id: str) -> list[Constraint]:
        return self._by_unit[unit_id]

    def cohort_constraints(self, cohort_id: str) -> list[Constraint]:
        return self._by_cohort[cohort_id]

    def trainer_blocked(self, trainer_id: str, key: SlotKey) -> bool:
        blocked = self._blocked[trainer_id]
        return key in blocked or SlotKey(key.day, "__ALL__") in blocked

    def get_pin(self, unit_id: str, cohort_id: str) -> Optional[tuple[str, str]]:
        """
        Return (day, period_id) if a hard PIN_DAY_PERIOD constraint exists
        for this unit OR cohort.
        """
        for c in self._by_unit.get(unit_id, []):
            if c.rule == "PIN_DAY_PERIOD" and c.is_hard:
                day = c.parameters.get("day")
                period_id = c.parameters.get("period_id")
                if day and period_id:
                    return day, str(period_id)
        for c in self._by_cohort.get(cohort_id, []):
            if c.rule == "PIN_DAY_PERIOD" and c.is_hard:
                day = c.parameters.get("day")
                period_id = c.parameters.get("period_id")
                if day and period_id:
                    return day, str(period_id)
        return None

    def get_pinned_day(self, unit_id: str, cohort_id: str) -> Optional[str]:
        """
        Return the required day if a hard PIN_DAY constraint exists.
        """
        for c in self._by_unit.get(unit_id, []):
            if c.rule == "PIN_DAY" and c.is_hard:
                day = c.parameters.get("day")
                if day:
                    return day
        for c in self._by_cohort.get(cohort_id, []):
            if c.rule == "PIN_DAY" and c.is_hard:
                day = c.parameters.get("day")
                if day:
                    return day
        return None

    def get_preferred_room(self, unit_id: str) -> Optional[str]:
        for c in self._by_unit.get(unit_id, []):
            if c.rule == "PREFERRED_ROOM":
                return c.parameters.get("room_id")
        return None

    def get_avoided_days(self, unit_id: str, cohort_id: str) -> set[str]:
        days: set[str] = set()
        for c in list(self._by_unit.get(unit_id, [])) + list(self._by_cohort.get(cohort_id, [])):
            if c.rule == "AVOID_DAY":
                d = c.parameters.get("day", "")
                if d:
                    days.add(d)
        return days

    def get_avoided_periods(self, unit_id: str, cohort_id: str) -> set[str]:
        period_ids: set[str] = set()
        for c in list(self._by_unit.get(unit_id, [])) + list(self._by_cohort.get(cohort_id, [])):
            if c.rule == "AVOID_PERIOD":
                pid = c.parameters.get("period_id", "")
                if pid:
                    period_ids.add(str(pid))
        return period_ids


# ---------------------------------------------------------------------------
# Placer
# ---------------------------------------------------------------------------

class Placer:
    """
    Attempts to place a single (cohort, curriculum_unit) onto the timetable.

    PERF: _write() no longer touches the DB — it appends a ScheduledUnit
    instance to self._pending (a list owned by TimetableEngine.run()).
    All pending rows are flushed in a single bulk_create at the end of run().
    """

    def __init__(
        self,
        term:       Term,
        grid:       OccupancyGrid,
        cindex:     ConstraintIndex,
        days:       list[str],
        periods:    list[Period],
        rooms:      list[Room],
        pass_cfg:   dict,
        pending:    list,          # shared list owned by TimetableEngine.run()
    ):
        self.term     = term
        self.grid     = grid
        self.cindex   = cindex
        self.days     = days
        self.periods  = periods
        self.rooms    = rooms
        self.cfg      = pass_cfg
        self._pending = pending    # ← write here instead of DB

    # -- Main entry point ---------------------------------------------------

    def place(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainers: list[Trainer],
    ) -> PlacementResult:
        if unit.periods_per_week >= 2:
            return self._place_double(cohort, unit, trainers)
        return self._place_single(cohort, unit, trainers)

    # -- Single period ------------------------------------------------------

    def _place_single(
        self, cohort: Cohort, unit: CurriculumUnit, trainers: list[Trainer]
    ) -> PlacementResult:
        uid = str(unit.id)
        cid = str(cohort.id)

        # 1. Hard PIN_DAY_PERIOD — must land exactly here
        pin = self.cindex.get_pin(uid, cid)
        if pin:
            day, period_id = pin
            period = next((p for p in self.periods if str(p.id) == period_id), None)
            if period is None:
                return PlacementResult(
                    False, unit, cohort,
                    f"PIN_DAY_PERIOD constraint references unknown period {period_id}"
                )
            return self._try_slot(cohort, unit, trainers, day, period, pinned=True)

        # 2. Hard PIN_DAY — must be on this day, any period
        pinned_day = self.cindex.get_pinned_day(uid, cid)

        # 3. Build candidate list respecting AVOID_DAY and PIN_DAY
        avoided_days    = self.cindex.get_avoided_days(uid, cid)
        avoided_periods = self.cindex.get_avoided_periods(uid, cid)

        if pinned_day:
            candidate_days = [pinned_day] if pinned_day in self.days else self.days[:]
        else:
            candidate_days = [d for d in self.days if d not in avoided_days]
            if not candidate_days:
                candidate_days = self.days[:]

        skip_soft = self.cfg.get("skip_soft", False)
        if skip_soft or not avoided_periods:
            candidate_periods = self.periods
        else:
            candidate_periods = [p for p in self.periods if str(p.id) not in avoided_periods]
            if not candidate_periods:
                candidate_periods = self.periods

        random.shuffle(candidate_days)
        candidates = [(d, p) for d in candidate_days for p in candidate_periods]
        max_att = self.cfg["max_attempts"]

        for day, period in candidates[:max_att]:
            result = self._try_slot(cohort, unit, trainers, day, period)
            if result.success:
                return result

        return PlacementResult(
            False, unit, cohort,
            f"No free slot found after {min(max_att, len(candidates))} attempts",
            self.cfg["name"],
        )

    # -- Double / consecutive periods ---------------------------------------

    def _place_double(
        self, cohort: Cohort, unit: CurriculumUnit, trainers: list[Trainer]
    ) -> PlacementResult:
        uid = str(unit.id)
        cid = str(cohort.id)

        pairs: list[tuple[Period, Period]] = []
        for i in range(len(self.periods) - 1):
            a, b = self.periods[i], self.periods[i + 1]
            if not a.is_break and not b.is_break:
                pairs.append((a, b))

        if not pairs:
            return PlacementResult(
                False, unit, cohort,
                "No consecutive period pairs configured for this institution",
            )

        avoided_days = self.cindex.get_avoided_days(uid, cid)
        pinned_day   = self.cindex.get_pinned_day(uid, cid)

        if pinned_day:
            candidate_days = [pinned_day] if pinned_day in self.days else self.days[:]
        else:
            candidate_days = [d for d in self.days if d not in avoided_days]
            if not candidate_days:
                candidate_days = self.days[:]

        random.shuffle(candidate_days)
        candidates = [(d, a, b) for d in candidate_days for a, b in pairs]

        for day, pa, pb in candidates:
            result = self._try_double_slot(cohort, unit, trainers, day, pa, pb)
            if result.success:
                return result

        return PlacementResult(
            False, unit, cohort,
            "No free consecutive pair found",
            self.cfg["name"],
        )

    # -- Slot-level helpers -------------------------------------------------

    def _try_slot(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainers: list[Trainer],
        day:      str,
        period:   Period,
        pinned:   bool = False,
    ) -> PlacementResult:
        allow_overlap = self.cfg.get("allow_overlap", False)
        key = SlotKey(day, str(period.id))
        cid = str(cohort.id)

        if not allow_overlap and self.grid.cohort_busy(cid, key):
            if pinned:
                return PlacementResult(
                    False, unit, cohort,
                    f"Cohort already has a class at pinned slot {day} {period}",
                )
            return PlacementResult(False)

        trainer = self._pick_trainer(trainers, day, period, allow_overlap)
        if trainer is None:
            if pinned:
                return PlacementResult(
                    False, unit, cohort,
                    f"No qualified trainer free at pinned slot {day} {period}",
                )
            return PlacementResult(False)

        room = self._pick_room(unit, cohort, day, period, allow_overlap)
        if room is None:
            if not allow_overlap:
                return PlacementResult(False)
            room = self.rooms[0] if self.rooms else None
            if room is None:
                return PlacementResult(False, unit, cohort, "No rooms configured")

        self._write(cohort, unit, trainer, room, day, period, sequence=0)
        return PlacementResult(True, unit, cohort, pass_name=self.cfg["name"])

    def _try_double_slot(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainers: list[Trainer],
        day:      str,
        pa:       Period,
        pb:       Period,
    ) -> PlacementResult:
        allow_overlap = self.cfg.get("allow_overlap", False)
        cid  = str(cohort.id)
        key_a = SlotKey(day, str(pa.id))
        key_b = SlotKey(day, str(pb.id))

        if not allow_overlap:
            if self.grid.cohort_busy(cid, key_a) or self.grid.cohort_busy(cid, key_b):
                return PlacementResult(False)

        trainer = self._pick_trainer_pair(trainers, day, pa, pb, allow_overlap)
        if trainer is None:
            return PlacementResult(False)

        room = self._pick_room(unit, cohort, day, pa, allow_overlap)
        if room is None and not allow_overlap:
            return PlacementResult(False)
        if room is None:
            room = self.rooms[0] if self.rooms else None
        if room is None:
            return PlacementResult(False, unit, cohort, "No rooms")

        self._write(cohort, unit, trainer, room, day, pa, sequence=1)
        self._write(cohort, unit, trainer, room, day, pb, sequence=2)
        return PlacementResult(True, unit, cohort, pass_name=self.cfg["name"])

    # -- Trainer selection --------------------------------------------------

    def _pick_trainer(
        self, trainers: list[Trainer], day: str, period: Period, allow_overlap: bool
    ) -> Optional[Trainer]:
        key = SlotKey(day, str(period.id))
        for trainer in trainers:
            tid = str(trainer.id)
            if self.cindex.trainer_blocked(tid, key):
                continue
            if not allow_overlap and self.grid.trainer_busy(tid, key):
                continue
            if not self._trainer_day_ok(trainer, day):
                continue
            max_per_day = getattr(trainer, "_max_per_day_override", None) or 8
            if self.grid.trainer_day_periods(tid, day) >= max_per_day:
                continue
            return trainer
        return None

    def _pick_trainer_pair(
        self, trainers: list[Trainer], day: str, pa: Period, pb: Period, allow_overlap: bool
    ) -> Optional[Trainer]:
        key_a = SlotKey(day, str(pa.id))
        key_b = SlotKey(day, str(pb.id))
        for trainer in trainers:
            tid = str(trainer.id)
            if self.cindex.trainer_blocked(tid, key_a) or self.cindex.trainer_blocked(tid, key_b):
                continue
            if not allow_overlap:
                if self.grid.trainer_busy(tid, key_a) or self.grid.trainer_busy(tid, key_b):
                    continue
            if not self._trainer_day_ok(trainer, day):
                continue
            return trainer
        return None

    def _trainer_day_ok(self, trainer: Trainer, day: str) -> bool:
        try:
            days = trainer.get_available_days(trainer.institution)
            if not days:
                return True
            return day in days
        except Exception:
            return True

    # -- Room selection -----------------------------------------------------

    def _pick_room(
        self,
        unit:   CurriculumUnit,
        cohort: Cohort,
        day:    str,
        period: Period,
        allow_overlap: bool,
    ) -> Optional[Room]:
        need_lab = unit.unit_type == "PRACTICAL"
        preferred_id = self.cindex.get_preferred_room(str(unit.id))

        candidates = [
            r for r in self.rooms
            if r.capacity >= cohort.student_count
            and (not need_lab or r.room_type in ("LAB", "CLINICAL", "COMPUTER", "WORKSHOP"))
        ]
        candidates.sort(key=lambda r: (
            str(r.id) != str(preferred_id),
            r.capacity,
        ))

        key = SlotKey(day, str(period.id))
        for room in candidates:
            if allow_overlap or not self.grid.room_busy(str(room.id), key):
                return room
        return None

    # -- Write (in-memory only — no DB hit) ---------------------------------

    def _write(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainer:  Trainer,
        room:     Room,
        day:      str,
        period:   Period,
        sequence: int,
        is_combined:  bool = False,
        combined_key: str  = "",
    ) -> ScheduledUnit:
        """
        PERF: Build the ScheduledUnit in memory and append to _pending.
        The grid is updated immediately so subsequent placements see this slot
        as occupied. The actual INSERT happens once at the end of run().
        """
        entry = ScheduledUnit(
            id=uuid.uuid4(),
            term=self.term,
            cohort=cohort,
            curriculum_unit=unit,
            period=period,
            trainer=trainer,
            room=room,
            day=day,
            sequence=sequence,
            status="DRAFT",
            is_combined=is_combined,
            combined_key=combined_key,
        )
        self._pending.append(entry)

        key = SlotKey(day, str(period.id))
        self.grid.mark(str(trainer.id), str(cohort.id), str(room.id), key)
        return entry


# ---------------------------------------------------------------------------
# Pass configurations
# ---------------------------------------------------------------------------

_PASS_CONFIGS = [
    {
        "name":          "STRICT",
        "allow_overlap": False,
        "use_any_trainer": False,
        "max_attempts":  60,
        "skip_soft":     False,
    },
    {
        "name":          "RELAXED",
        "allow_overlap": False,
        "use_any_trainer": False,
        "max_attempts":  120,
        "skip_soft":     True,
    },
    {
        "name":          "EMERGENCY",
        "allow_overlap": True,
        "use_any_trainer": True,
        "max_attempts":  200,
        "skip_soft":     True,
    },
]


# ---------------------------------------------------------------------------
# TimetableEngine
# ---------------------------------------------------------------------------

class TimetableEngine:
    """
    Main entry point.

        engine = TimetableEngine(term)
        result = engine.run()
    """

    def __init__(self, term: Term):
        self.term = term
        self.institution = term.institution

    @transaction.atomic
    def run(self, delete_existing_drafts: bool = True) -> GenerationResult:
        # 1. Clear previous DRAFT entries
        if delete_existing_drafts:
            ScheduledUnit.objects.filter(term=self.term, status="DRAFT").delete()

        # PERF: shared in-memory buffer — all Placer._write() calls and
        # _try_place_combined() calls append here; one bulk_create at the end.
        pending: list[ScheduledUnit] = []

        # 2. Load reference data
        days    = list(self.institution.days_of_week)
        periods = list(Period.objects.filter(institution=self.institution, is_break=False).order_by("order"))
        rooms   = list(Room.objects.filter(institution=self.institution, is_active=True).order_by("capacity"))

        if not periods:
            return GenerationResult(term=self.term)

        # 3. Build work queue: {cohort_id → (Cohort, [CurriculumUnit])}
        cohorts = list(
            Cohort.objects.filter(
                programme__department__institution=self.institution,
                is_active=True,
            ).select_related("programme")
        )

        work_queue: dict[str, tuple[Cohort, list[CurriculumUnit]]] = {}
        all_unit_ids    = []
        all_cohort_ids  = []

        for cohort in cohorts:
            units = list(
                CurriculumUnit.objects.filter(
                    programme=cohort.programme,
                    term_number=cohort.current_term,
                    is_active=True,
                ).prefetch_related("qualified_trainers", "unit_trainers__trainer")
            )
            if units:
                work_queue[str(cohort.id)] = (cohort, units)
                all_unit_ids.extend(str(u.id) for u in units)
                all_cohort_ids.append(str(cohort.id))

        all_trainer_ids = [
            str(t) for t in Trainer.objects.filter(
                institution=self.institution, is_active=True
            ).values_list("id", flat=True)
        ]

        total_required = sum(len(v[1]) for v in work_queue.values())

        # 4. Build occupancy grid (single DB query)
        grid = OccupancyGrid.build(self.term)

        # 5. Build constraint index (single DB query batch)
        cindex = ConstraintIndex(self.term, all_unit_ids, all_cohort_ids, all_trainer_ids)

        result = GenerationResult(term=self.term, total_required=total_required)

        # 6. Schedule combined/shared units first
        combined_placed = self._schedule_combined(
            work_queue, grid, cindex, days, periods, rooms, pending
        )
        result.combined_placed = combined_placed

        # 7. Sort work queue AFTER combined scheduling
        sorted_queue = self._sort_by_difficulty(work_queue, cindex)

        remaining = [
            (cid, list(units))
            for cid, units in sorted_queue
            if units
        ]

        # 8. Multi-pass scheduling
        placed_keys: set[str] = set()
        no_trainer_units = []

        for pass_cfg in _PASS_CONFIGS:
            if not remaining:
                break

            next_remaining = []
            # Pass the shared pending buffer into every Placer
            placer = Placer(self.term, grid, cindex, days, periods, rooms, pass_cfg, pending)

            for cohort_id, unit_list in remaining:
                cohort, _ = work_queue[cohort_id]
                still_unplaced = []

                for unit in unit_list:
                    key = f"{cohort_id}_{unit.id}"
                    if key in placed_keys:
                        continue

                    if getattr(unit, 'is_outsourced', False):
                        placed_keys.add(key)
                        continue

                    # Use prefetched queryset — no extra DB hit
                    qualified = [t for t in unit.qualified_trainers.all() if t.is_active]

                    if not qualified:
                        if pass_cfg["name"] == "STRICT":
                            no_trainer_units.append((cohort, unit))
                        still_unplaced.append(unit)
                        continue

                    pr = placer.place(cohort, unit, qualified)
                    if pr.success:
                        placed_keys.add(key)
                        result.placed += 1
                        if pass_cfg["name"] == "EMERGENCY":
                            result.emergency_placements.append({
                                "cohort": cohort.name,
                                "unit":   unit.code,
                                "pass":   pass_cfg["name"],
                            })
                    else:
                        still_unplaced.append(unit)

                if still_unplaced:
                    next_remaining.append((cohort_id, still_unplaced))

            remaining = next_remaining

        # 9. PERF: flush all placements in a single bulk_create
        #    update_conflicts=True acts like update_or_create but in one round-trip.
        if pending:
            ScheduledUnit.objects.bulk_create(
                pending,
                update_conflicts=True,
                unique_fields=["term", "cohort", "curriculum_unit", "period"],
                update_fields=[
                    "trainer", "room", "day", "sequence", "status",
                    "is_combined", "combined_key",
                ],
            )

        # 10. Log unresolved failures as Conflicts (also bulk)
        conflicts_to_create = []

        for cohort, unit in no_trainer_units:
            key = f"{cohort.id}_{unit.id}"
            if key not in placed_keys:
                result.unresolved.append({
                    "cohort": cohort.name,
                    "unit":   unit.code,
                    "reason": "No qualified trainer assigned to this unit",
                })
                conflicts_to_create.append(
                    Conflict(
                        term=self.term,
                        conflict_type="NO_TRAINER",
                        severity="HIGH",
                        description=f"[NO TRAINER] {unit.code} for {cohort.name} — assign a qualified trainer",
                        curriculum_unit=unit,
                        cohort=cohort,
                        resolution_status="PENDING",
                    )
                )

        for cohort_id, unit_list in remaining:
            cohort, _ = work_queue[cohort_id]
            for unit in unit_list:
                key = f"{cohort_id}_{unit.id}"
                if key not in placed_keys:
                    result.unresolved.append({
                        "cohort": cohort.name,
                        "unit":   unit.code,
                        "reason": "Could not place after all passes",
                    })
                    conflicts_to_create.append(
                        Conflict(
                            term=self.term,
                            conflict_type="NO_ROOM",
                            severity="HIGH",
                            description=f"[UNPLACED] {unit.code} for {cohort.name}",
                            curriculum_unit=unit,
                            cohort=cohort,
                            resolution_status="PENDING",
                        )
                    )

        if conflicts_to_create:
            Conflict.objects.bulk_create(conflicts_to_create, ignore_conflicts=True)

        return result

    # -- Combined / shared class scheduling ---------------------------------

    def _schedule_combined(
        self, work_queue, grid, cindex, days, periods, rooms, pending: list
    ) -> int:
        from .models import Programme
        groups = set(
            Programme.objects.filter(
                department__institution=self.institution,
                is_active=True,
            ).exclude(sharing_group="").values_list("sharing_group", flat=True)
        )

        placed = 0
        placed_combined_keys: set[str] = set()

        for group in groups:
            progs = list(
                Programme.objects.filter(sharing_group=group, is_active=True)
            )
            prog_ids = {str(p.id) for p in progs}

            group_cohort_ids = [
                cid for cid, (cohort, _) in work_queue.items()
                if str(cohort.programme_id) in prog_ids
            ]
            if len(group_cohort_ids) < 2:
                continue

            name_to_cohort_units: dict[str, dict] = defaultdict(dict)
            for cid in group_cohort_ids:
                _, units = work_queue[cid]
                for u in units:
                    if not getattr(u, 'is_outsourced', False):
                        name_to_cohort_units[u.name.strip()][cid] = u

            shared_names = {
                name: cu_map for name, cu_map in name_to_cohort_units.items()
                if len(cu_map) >= 2
            }

            if not shared_names:
                continue

            cfg = {"name": "COMBINED", "allow_overlap": False, "max_attempts": 80, "skip_soft": False}

            for unit_name, cohort_unit_map in shared_names.items():
                combined_key = f"{group}_{unit_name}"
                if combined_key in placed_combined_keys:
                    continue

                cohorts_in_combined = [work_queue[cid][0] for cid in cohort_unit_map.keys()]
                combined_students = sum(c.student_count for c in cohorts_in_combined)

                source_unit = max(
                    cohort_unit_map.values(),
                    key=lambda u: u.qualified_trainers.count()
                )
                trainer_id_sets = [
                    set(u.qualified_trainers.filter(is_active=True).values_list("id", flat=True))
                    for u in cohort_unit_map.values()
                ]
                common_ids = set.intersection(*trainer_id_sets) if trainer_id_sets else set()
                if not common_ids:
                    common_ids = set(
                        source_unit.qualified_trainers.filter(is_active=True).values_list("id", flat=True)
                    )
                from timetable.models import Trainer as _T
                qualified = list(_T.objects.filter(id__in=common_ids, is_active=True))
                if not qualified:
                    continue

                big_rooms = [r for r in rooms if r.capacity >= combined_students]
                if not big_rooms:
                    big_rooms = sorted(rooms, key=lambda r: -r.capacity)[:1]

                all_units_in_combined = list(cohort_unit_map.values())
                ok = self._try_place_combined(
                    source_unit, cohorts_in_combined, qualified, big_rooms,
                    days, periods, grid, cindex, cfg, combined_key,
                    all_units=all_units_in_combined,
                    pending=pending,
                )
                if ok:
                    placed_combined_keys.add(combined_key)
                    for cid, unit in cohort_unit_map.items():
                        cohort_obj, units = work_queue[cid]
                        work_queue[cid] = (cohort_obj, [u for u in units if u.id != unit.id])
                    placed += 1

        return placed

    def _try_place_combined(
        self, unit, cohorts, trainers, rooms, days, periods, grid, cindex, cfg,
        combined_key, all_units=None, pending=None
    ) -> bool:
        cohort_unit_map = {}
        if all_units:
            for c, u in zip(cohorts, all_units):
                cohort_unit_map[str(c.id)] = u
        else:
            for c in cohorts:
                cohort_unit_map[str(c.id)] = unit

        if pending is None:
            pending = []

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

                # Update grid in-memory for all cohorts in this combined session
                grid.mark(str(trainer.id), str(cohorts[0].id), str(room.id), key)
                for _c in cohorts[1:]:
                    grid._cohort[str(_c.id)].add(key)
                    grid._cohort_day_count[str(_c.id)][key.day] += 1
                    # trainer already marked above; mark room for subsequent lookups
                    grid._room[str(room.id)].add(key)

                # PERF: append to pending instead of update_or_create per cohort
                for cohort in cohorts:
                    cohort_unit = cohort_unit_map[str(cohort.id)]
                    pending.append(ScheduledUnit(
                        id=uuid.uuid4(),
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
        return False

    # -- Difficulty sort ----------------------------------------------------

    def _sort_by_difficulty(
        self, work_queue: dict, cindex: ConstraintIndex
    ) -> list[tuple[str, list[CurriculumUnit]]]:
        """
        Sort cohort-unit pairs so the most constrained are scheduled first.
        Uses prefetched qualified_trainers — no extra DB queries.
        """
        def difficulty(item):
            cohort_id, (cohort, units) = item
            if not units:
                return (0, 0, 99)
            pin_count = sum(
                1 for u in units
                if cindex.get_pin(str(u.id), cohort_id) is not None
                   or cindex.get_pinned_day(str(u.id), cohort_id) is not None
            )
            double_count = sum(1 for u in units if u.periods_per_week >= 2)
            # Use prefetched cache — len(list(...)) hits no DB
            avg_trainers = (
                sum(len(list(u.qualified_trainers.all())) for u in units) / len(units)
            )
            return (-pin_count, -double_count, avg_trainers)

        items = list(work_queue.items())
        items.sort(key=difficulty)
        return [(cid, list(units)) for cid, (cohort, units) in items]

    def _has_pin(self, unit_id: str, cohort_id: str) -> bool:
        return Constraint.objects.filter(
            curriculum_unit_id=unit_id,
            rule="PIN_DAY_PERIOD",
            is_hard=True,
            is_active=True,
        ).exists()