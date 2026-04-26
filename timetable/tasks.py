"""
timetable/tasks.py
==================

Celery task that runs timetable generation asynchronously.

WHY ASYNC:
  Generation writes 5,000–15,000 TimetableEntry rows (14 weeks × intakes ×
  units × 1-4 slots).  Doing that synchronously in a Django view always hits
  the HTTP gateway timeout.  Instead the view returns 202 + task_id instantly;
  the client polls /schedule/generate/status/<task_id>/ until done.

BULK-WRITE STRATEGY:
  Old code: one update_or_create() per entry  →  up to 15,000 round-trips.
  New code:
    1. Collect every TimetableEntry object in a Python list (no DB write yet).
    2. At the end of each week-batch, call bulk_create(…, update_conflicts=True)
       — one INSERT … ON CONFLICT DO UPDATE per week.
  Result: 14 bulk INSERTs instead of 15,000 individual ones.

PROGRESS TRACKING:
  The task stores progress in Django's cache so the status endpoint can
  stream live feedback to the frontend without polling the DB.

CELERY SETUP (add to settings.py if not already present):
    CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 1800       # 30 min hard limit
    CELERY_TASK_SOFT_TIME_LIMIT = 1500  # 25 min soft limit (raises SoftTimeLimitExceeded)
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import (
    ConflictLog, Intake, IntakeUnit, Lecturer, Room,
    Semester, Stage, TimeSlot, TimetableEntry, Unit, UnitSchedulingConstraint,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants (duplicated from views.py to keep tasks self-contained)
# ─────────────────────────────────────────────────────────────────────────────

_DAYS = ["MON", "TUE", "WED", "THU", "FRI"]

_DOUBLE_LESSON_PAIRS = [
    ("SLOT_1", "SLOT_2"),
    ("SLOT_3", "SLOT_4"),
]

_RETRY_CONFIGS = [
    {"name": "STRICT",    "allow_overlap": False, "use_any_lecturer": False, "max_attempts": 50},
    {"name": "RELAXED",   "allow_overlap": False, "use_any_lecturer": False, "max_attempts": 100},
    {"name": "EMERGENCY", "allow_overlap": True,  "use_any_lecturer": True,  "max_attempts": 200},
]

_PROGRESS_TTL = 3600  # cache progress for 1 hour


# ─────────────────────────────────────────────────────────────────────────────
# Progress helpers
# ─────────────────────────────────────────────────────────────────────────────

def _progress_key(task_id: str) -> str:
    return f"timetable_gen_progress_{task_id}"


def _set_progress(task_id: str, data: dict) -> None:
    cache.set(_progress_key(task_id), data, timeout=_PROGRESS_TTL)


def get_task_progress(task_id: str) -> dict | None:
    """Called by the status view to retrieve live progress."""
    return cache.get(_progress_key(task_id))


# ─────────────────────────────────────────────────────────────────────────────
# In-memory occupancy cache
# ─────────────────────────────────────────────────────────────────────────────

class OccupancyCache:
    """
    Loaded once from DB at task start.  All checks are O(1) set lookups.
    Updated in-memory as entries are scheduled (before bulk_create flushes).
    """

    def __init__(self):
        self._lecturer: dict[str, set] = defaultdict(set)
        self._intake:   dict[str, set] = defaultdict(set)
        self._room:     dict[str, set] = defaultdict(set)
        self._lec_hours: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))

    @classmethod
    def build(cls, semester: Semester) -> "OccupancyCache":
        c = cls()
        qs = TimetableEntry.objects.filter(
            semester=semester,
            status__in=["DRAFT", "PUBLISHED"],
        ).values(
            "lecturer_id", "intake_id", "room_id",
            "day", "time_slot__slot_id", "week_number",
            "time_slot__start_time", "time_slot__end_time",
        )
        for row in qs:
            key = (row["day"], row["time_slot__slot_id"], row["week_number"])
            c._lecturer[str(row["lecturer_id"])].add(key)
            c._intake[str(row["intake_id"])].add(key)
            c._room[str(row["room_id"])].add(key)
            s, e = row["time_slot__start_time"], row["time_slot__end_time"]
            if s and e:
                hrs = (datetime.combine(datetime.today(), e)
                       - datetime.combine(datetime.today(), s)).seconds / 3600.0
            else:
                hrs = 0.0
            c._lec_hours[str(row["lecturer_id"])][row["week_number"]] += hrs
        return c

    # ── Busy checks ──

    def lecturer_busy(self, lid, day, slot_id, week) -> bool:
        return (day, slot_id, week) in self._lecturer[str(lid)]

    def intake_busy(self, iid, day, slot_id, week) -> bool:
        return (day, slot_id, week) in self._intake[str(iid)]

    def room_busy(self, rid, day, slot_id, week) -> bool:
        return (day, slot_id, week) in self._room[str(rid)]

    def lecturer_hours(self, lid, week) -> float:
        return self._lec_hours[str(lid)][week]

    # ── Mark (called for buffered entries before flush) ──

    def mark(self, lid, iid, rid, day, slot_id, week, hours: float = 0) -> None:
        key = (day, slot_id, week)
        self._lecturer[str(lid)].add(key)
        self._intake[str(iid)].add(key)
        self._room[str(rid)].add(key)
        self._lec_hours[str(lid)][week] += hours


# ─────────────────────────────────────────────────────────────────────────────
# Small pure helpers
# ─────────────────────────────────────────────────────────────────────────────

def _slot_hours(ts: TimeSlot) -> float:
    return ts.duration_hours


def _slot_date(semester: Semester, week: int, day: str) -> date:
    offsets = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4}
    ws = semester.start_date - timedelta(days=semester.start_date.weekday())
    ws += timedelta(weeks=week - 1)
    return ws + timedelta(days=offsets.get(day, 0))


def _resolve_stage(intake: Intake, semester: Semester) -> Stage | None:
    SEM_NUM = {"JAN_APR": 1, "MAY_AUG": 2, "SEP_DEC": 3}
    isn = SEM_NUM.get(intake.intake_semester)
    csn = SEM_NUM.get(semester.semester_type)
    if not isn or not csn:
        return None
    year_diff = semester.academic_year.year - intake.intake_year
    elapsed = year_diff * 3 + (csn - isn) + 1
    if elapsed < 1 or elapsed > intake.programme.duration_semesters:
        return None
    return Stage.objects.filter(
        programme=intake.programme, semester_number=elapsed
    ).first()


def _sync_stage_units(intake: Intake, semester: Semester, stage: Stage) -> None:
    existing = set(
        IntakeUnit.objects.filter(intake=intake, semester=semester)
        .values_list("unit_id", flat=True)
    )
    new_ids = list(
        Unit.objects.filter(stage=stage).values_list("id", flat=True)
    )
    rows = [
        IntakeUnit(intake=intake, unit_id=uid, semester=semester,
                   override_source="STAGE", is_mandatory=True)
        for uid in new_ids if uid not in existing
    ]
    if rows:
        IntakeUnit.objects.bulk_create(rows, ignore_conflicts=True)


def _effective_units(intake: Intake, semester: Semester) -> list[Unit]:
    ids = list(
        IntakeUnit.objects.filter(
            intake=intake, semester=semester,
            override_source__in=["STAGE", "ADDED"],
        ).values_list("unit_id", flat=True)
    )
    return list(Unit.objects.filter(id__in=ids).order_by("code"))


def _get_constraint(unit: Unit, intake: Intake) -> UnitSchedulingConstraint | None:
    c = UnitSchedulingConstraint.objects.filter(
        unit=unit, programme=intake.programme, is_active=True,
    ).select_related("pinned_time_slot", "preferred_room").first()
    return c or UnitSchedulingConstraint.objects.filter(
        unit=unit, programme__isnull=True, is_active=True,
    ).select_related("pinned_time_slot", "preferred_room").first()


def _get_double_pairs(time_slots: list[TimeSlot]) -> list[tuple]:
    slot_map = {ts.slot_id: ts for ts in time_slots}
    return [(slot_map[a], slot_map[b])
            for a, b in _DOUBLE_LESSON_PAIRS
            if a in slot_map and b in slot_map]


def _lecturer_available_days(lecturer: Lecturer) -> list[str]:
    _map = {"monday": "MON", "tuesday": "TUE", "wednesday": "WED",
            "thursday": "THU", "friday": "FRI",
            "mon": "MON", "tue": "TUE", "wed": "WED", "thu": "THU", "fri": "FRI"}
    raw = lecturer.get_available_days() if hasattr(lecturer, "get_available_days") else []
    return [_map.get(str(d).strip().lower(), str(d).strip().upper()) for d in (raw or [])]


def _lecturer_free(lecturer, semester, day, slots, week, allow_overlap, occ) -> bool:
    if allow_overlap:
        return True
    avail = _lecturer_available_days(lecturer)
    if avail and day not in avail:
        return False
    if week in (getattr(lecturer, "unavailable_weeks", None) or []):
        return False
    unavail_dates = getattr(lecturer, "unavailable_dates", None) or []
    if unavail_dates:
        slot_dt = _slot_date(semester, week, day)
        blocked = set()
        for d in unavail_dates:
            if isinstance(d, date):
                blocked.add(d)
            else:
                try:
                    blocked.add(datetime.strptime(str(d), "%Y-%m-%d").date())
                except ValueError:
                    pass
        if slot_dt in blocked:
            return False
    max_h = getattr(lecturer, "max_hours_per_week", None)
    if max_h:
        if occ.lecturer_hours(lecturer.id, week) + sum(_slot_hours(ts) for ts in slots) > max_h:
            return False
    lid = str(lecturer.id)
    return not any(occ.lecturer_busy(lid, day, ts.slot_id, week) for ts in slots)


def _pick_room(unit, student_count, day, slots, all_weeks, allow_overlap, occ,
               preferred_room=None) -> Room | None:
    qs = Room.objects.filter(is_active=True, capacity__gte=student_count)
    if unit.practical_hours_per_week > 0:
        qs = qs.filter(room_type__in=["LAB", "CLINICAL", "COMPUTER"])
    rooms = list(qs.order_by("capacity"))
    if preferred_room and (preferred_room.capacity >= student_count and
            (unit.practical_hours_per_week == 0 or
             preferred_room.room_type in ("LAB", "CLINICAL", "COMPUTER"))):
        rooms = [preferred_room] + [r for r in rooms if r.id != preferred_room.id]
    if allow_overlap:
        return rooms[0] if rooms else None
    for room in rooms:
        rid = str(room.id)
        if all(not occ.room_busy(rid, day, ts.slot_id, w)
               for w in all_weeks for ts in slots):
            return room
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Buffered entry builder — no DB writes until flush
# ─────────────────────────────────────────────────────────────────────────────

class EntryBuffer:
    """
    Accumulates TimetableEntry objects in memory.

    flush() calls bulk_create with update_conflicts=True (PostgreSQL
    INSERT … ON CONFLICT DO UPDATE), which is a single round-trip per batch.

    For SQLite (dev) update_conflicts is not supported so we fall back to
    ignore_conflicts=True (no upsert — safe because drafts are wiped before
    generation starts).
    """

    # Unique fields that identify a row (mirror the get_or_create lookup keys).
    _UNIQUE_FIELDS = ["semester_id", "intake_id", "unit_id", "week_number", "time_slot_id"]
    _UPDATE_FIELDS = ["lecturer_id", "room_id", "day", "status", "is_recurring",
                      "slot_sequence", "is_shared_class", "shared_group_key"]

    def __init__(self):
        self._buf: list[TimetableEntry] = []
        self._seen: set[tuple] = set()  # dedup within buffer

    def add(self, *, semester, intake, unit, lecturer, room, day,
            time_slot, week, slot_sequence=0, is_shared=False,
            shared_group_key="", occ: OccupancyCache) -> None:
        key = (semester.id, intake.id, unit.id, week, time_slot.id)
        if key in self._seen:
            return
        self._seen.add(key)

        self._buf.append(TimetableEntry(
            semester=semester,
            intake=intake,
            unit=unit,
            lecturer=lecturer,
            room=room,
            day=day,
            time_slot=time_slot,
            week_number=week,
            status="DRAFT",
            is_recurring=True,
            slot_sequence=slot_sequence,
            is_shared_class=is_shared,
            shared_group_key=shared_group_key,
        ))

        # Keep occupancy cache warm immediately (before flush).
        occ.mark(lecturer.id, intake.id, room.id, day,
                 time_slot.slot_id, week, _slot_hours(time_slot))

    def flush(self) -> int:
        if not self._buf:
            return 0

        from django.db import connection as _conn
        using_pg = _conn.vendor == "postgresql"

        if using_pg:
            TimetableEntry.objects.bulk_create(
                self._buf,
                update_conflicts=True,
                unique_fields=self._UNIQUE_FIELDS,
                update_fields=self._UPDATE_FIELDS,
            )
        else:
            # SQLite / other — ignore duplicates (drafts wiped beforehand).
            TimetableEntry.objects.bulk_create(self._buf, ignore_conflicts=True)

        n = len(self._buf)
        self._buf.clear()
        self._seen.clear()
        return n

    def __len__(self):
        return len(self._buf)


# ─────────────────────────────────────────────────────────────────────────────
# Core scheduler (stateless functions — called by the Celery task)
# ─────────────────────────────────────────────────────────────────────────────

def _find_single_slot(intake, unit, lecturers, constraint, time_slots,
                      allow_overlap, max_att, all_weeks, occ, semester):
    """Return (day, ts, lec, room) or None."""
    iid = str(intake.id)
    is_constrained = bool(constraint)

    if constraint:
        candidates = [(constraint.pinned_day, constraint.pinned_time_slot)]
    else:
        days = _DAYS.copy(); random.shuffle(days)
        candidates = [(d, ts) for d in days for ts in time_slots]

    outer = candidates if constraint else candidates[:max_att]

    for day, ts in outer:
        if not allow_overlap:
            if any(occ.intake_busy(iid, day, ts.slot_id, w) for w in all_weeks):
                if is_constrained:
                    break
                continue
        for lec in lecturers:
            if not all(_lecturer_free(lec, semester, day, [ts], w, allow_overlap, occ)
                       for w in all_weeks):
                continue
            pref = constraint.preferred_room if constraint and constraint.preferred_room_id else None
            room = _pick_room(unit, intake.student_count, day, [ts],
                              all_weeks, allow_overlap, occ, pref)
            if not room:
                if not allow_overlap:
                    continue
                room = Room.objects.filter(is_active=True).first()
            if room:
                return day, ts, lec, room
    return None


def _find_double_slots(intake, unit, lecturers, constraint, double_pairs,
                       allow_overlap, max_att, all_weeks, occ, semester):
    """Return (lec, session1, session2) where session = (day, slot_a, slot_b, room), or None."""
    if not double_pairs:
        return None
    iid = str(intake.id)

    if constraint:
        pinned = constraint.pinned_time_slot.slot_id
        all_cands = ([(constraint.pinned_day, a, b) for a, b in double_pairs
                      if a.slot_id == pinned]
                     or [(constraint.pinned_day, a, b) for a, b in double_pairs])
    else:
        all_cands = [(d, a, b) for d in _DAYS for a, b in double_pairs]
        random.shuffle(all_cands)

    outer = all_cands if constraint else all_cands[:max_att]

    for lec in lecturers:
        valid = []
        for day, slot_a, slot_b in outer:
            if valid and day == valid[0][0]:
                continue
            if not allow_overlap:
                if any(occ.intake_busy(iid, day, ts.slot_id, w)
                       for w in all_weeks for ts in [slot_a, slot_b]):
                    continue
            if not all(_lecturer_free(lec, semester, day, [slot_a, slot_b], w, allow_overlap, occ)
                       for w in all_weeks):
                continue
            room = _pick_room(unit, intake.student_count, day, [slot_a, slot_b],
                              all_weeks, allow_overlap, occ)
            if not room:
                if not allow_overlap:
                    continue
                room = Room.objects.filter(is_active=True).first()
            if room:
                valid.append((day, slot_a, slot_b, room))
            if len(valid) == 2:
                break
        if len(valid) == 2:
            return lec, valid[0], valid[1]
    return None


def _schedule_intake_unit(semester, intake, unit, config, time_slots,
                           double_pairs, all_weeks, occ, buf: EntryBuffer) -> dict:
    """Try to place *unit* for *intake* into *buf*.  Returns {success, reason}."""
    if not IntakeUnit.objects.filter(
        intake=intake, unit=unit, semester=semester,
        override_source__in=["STAGE", "ADDED"],
    ).exists():
        return {"success": False, "reason": "Unit not active for this intake"}

    qualified = list(unit.qualified_lecturers.filter(is_active=True))
    if not qualified:
        if config["use_any_lecturer"]:
            qualified = list(Lecturer.objects.filter(is_active=True))
        else:
            return {"success": False, "reason": "No qualified lecturers available"}
    if not qualified:
        return {"success": False, "reason": "No lecturers in system"}

    constraint   = _get_constraint(unit, intake)
    allow        = config["allow_overlap"]
    max_att      = config["max_attempts"]

    if unit.is_double_lesson:
        result = _find_double_slots(intake, unit, qualified, constraint,
                                    double_pairs, allow, max_att, all_weeks, occ, semester)
        if not result:
            return {"success": False,
                    "reason": f"No double-slot pair found for {unit.code}"}
        lec, sess1, sess2 = result
        for week in all_weeks:
            day1, sa1, sb1, room1 = sess1
            buf.add(semester=semester, intake=intake, unit=unit,
                    lecturer=lec, room=room1, day=day1, time_slot=sa1,
                    week=week, slot_sequence=1, occ=occ)
            buf.add(semester=semester, intake=intake, unit=unit,
                    lecturer=lec, room=room1, day=day1, time_slot=sb1,
                    week=week, slot_sequence=2, occ=occ)
            day2, sa2, sb2, room2 = sess2
            buf.add(semester=semester, intake=intake, unit=unit,
                    lecturer=lec, room=room2, day=day2, time_slot=sa2,
                    week=week, slot_sequence=3, occ=occ)
            buf.add(semester=semester, intake=intake, unit=unit,
                    lecturer=lec, room=room2, day=day2, time_slot=sb2,
                    week=week, slot_sequence=4, occ=occ)
    else:
        result = _find_single_slot(intake, unit, qualified, constraint,
                                   time_slots, allow, max_att, all_weeks, occ, semester)
        if not result:
            return {"success": False,
                    "reason": f"No slot found for {unit.code} after {max_att} attempts"}
        day, ts, lec, room = result
        for week in all_weeks:
            buf.add(semester=semester, intake=intake, unit=unit,
                    lecturer=lec, room=room, day=day, time_slot=ts,
                    week=week, slot_sequence=0, occ=occ)

    return {"success": True, "reason": None}


def _schedule_shared_units(semester, required, time_slots, double_pairs,
                            all_weeks, occ, buf: EntryBuffer) -> tuple[set, int]:
    from django.db.models import Count
    pre_scheduled: set[tuple] = set()
    shared_count = 0

    groups = list(
        __import__("timetable.models", fromlist=["Programme"])
        .Programme.objects.filter(is_active=True)
        .exclude(shared_unit_group__isnull=True)
        .exclude(shared_unit_group="")
        .values("shared_unit_group")
        .annotate(n=Count("id")).filter(n__gt=1)
        .values_list("shared_unit_group", flat=True)
    )
    if not groups:
        return pre_scheduled, shared_count

    # Build programme→intake from prefetched set.
    all_intakes = list(Intake.objects.filter(id__in=required.keys(), is_active=True)
                       .select_related("programme"))
    intake_by_prog = {str(i.programme_id): i for i in all_intakes}

    from .models import Programme
    for group_code in groups:
        programmes = list(Programme.objects.filter(
            shared_unit_group=group_code, is_active=True))
        prog_to_intake = {str(p.id): intake_by_prog[str(p.id)]
                          for p in programmes if str(p.id) in intake_by_prog}
        if len(prog_to_intake) < 2:
            continue

        intakes = list(prog_to_intake.values())
        iids = [i.id for i in intakes]

        rows = IntakeUnit.objects.filter(
            intake_id__in=iids, semester=semester,
            override_source__in=["STAGE", "ADDED"],
        ).values("intake_id", "unit_id")
        sets_by_intake: dict = defaultdict(set)
        for row in rows:
            sets_by_intake[str(row["intake_id"])].add(row["unit_id"])
        shared_ids = set.intersection(*[sets_by_intake[str(i.id)] for i in intakes]) \
            if intakes else set()
        if not shared_ids:
            continue

        combined_count = sum(i.student_count for i in intakes)

        for unit in Unit.objects.filter(id__in=shared_ids):
            qualified = list(unit.qualified_lecturers.filter(is_active=True))
            if not qualified:
                continue
            constraint = _get_constraint(unit, intakes[0])
            group_key = f"{group_code}_{unit.id}"

            placed = False
            if unit.is_double_lesson:
                if constraint:
                    pinned = constraint.pinned_time_slot.slot_id
                    cands = [(constraint.pinned_day, a, b)
                             for a, b in double_pairs if a.slot_id == pinned] \
                        or [(constraint.pinned_day, a, b) for a, b in double_pairs]
                else:
                    cands = [(d, a, b) for d in _DAYS for a, b in double_pairs]
                    random.shuffle(cands)

                for day, slot_a, slot_b in cands:
                    for lec in qualified:
                        if not all(_lecturer_free(lec, semester, day, [slot_a, slot_b], w, False, occ)
                                   for w in all_weeks):
                            continue
                        if any(occ.intake_busy(str(i.id), day, ts.slot_id, w)
                               for i in intakes for ts in [slot_a, slot_b] for w in all_weeks):
                            continue
                        room = _pick_room(unit, combined_count, day,
                                          [slot_a, slot_b], all_weeks, False, occ)
                        if not room:
                            continue
                        for week in all_weeks:
                            for intake in intakes:
                                buf.add(semester=semester, intake=intake, unit=unit,
                                        lecturer=lec, room=room, day=day, time_slot=slot_a,
                                        week=week, slot_sequence=1, is_shared=True,
                                        shared_group_key=group_key, occ=occ)
                                buf.add(semester=semester, intake=intake, unit=unit,
                                        lecturer=lec, room=room, day=day, time_slot=slot_b,
                                        week=week, slot_sequence=2, is_shared=True,
                                        shared_group_key=group_key, occ=occ)
                        placed = True
                        break
                    if placed:
                        break
            else:
                if constraint:
                    cands_s = [(constraint.pinned_day, constraint.pinned_time_slot)]
                else:
                    days = _DAYS.copy(); random.shuffle(days)
                    cands_s = [(d, ts) for d in days for ts in time_slots]

                for day, ts in cands_s:
                    for lec in qualified:
                        if not all(_lecturer_free(lec, semester, day, [ts], w, False, occ)
                                   for w in all_weeks):
                            continue
                        if any(occ.intake_busy(str(i.id), day, ts.slot_id, w)
                               for i in intakes for w in all_weeks):
                            continue
                        room = _pick_room(unit, combined_count, day, [ts], all_weeks, False, occ)
                        if not room:
                            continue
                        for week in all_weeks:
                            for intake in intakes:
                                buf.add(semester=semester, intake=intake, unit=unit,
                                        lecturer=lec, room=room, day=day, time_slot=ts,
                                        week=week, slot_sequence=0, is_shared=True,
                                        shared_group_key=group_key, occ=occ)
                        placed = True
                        break
                    if placed:
                        break

            if placed:
                for i in intakes:
                    for week in all_weeks:
                        pre_scheduled.add((str(i.id), str(unit.id), week))
            shared_count += 1

    return pre_scheduled, shared_count


# ─────────────────────────────────────────────────────────────────────────────
# Celery task
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, name="timetable.generate")
def generate_timetable_task(self, semester_id: str) -> dict:
    """
    Async timetable generation.

    Returns a result dict that Celery stores in the result backend.
    Progress is also written to the cache so the status endpoint can
    stream it without hitting the result backend.
    """
    task_id = self.request.id

    def progress(step: str, pct: int, **extra):
        data = {"step": step, "percent": pct, "task_id": task_id,
                "status": "RUNNING", **extra}
        _set_progress(task_id, data)
        self.update_state(state="PROGRESS", meta=data)

    try:
        semester = Semester.objects.select_related("academic_year").get(id=semester_id)
    except Semester.DoesNotExist:
        err = {"status": "FAILURE", "error": f"Semester {semester_id} not found"}
        _set_progress(task_id, err)
        return err

    progress("Clearing previous drafts", 2)

    from .views import _delete_all_drafts, _clear_timetable_cache
    with transaction.atomic():
        deleted = _delete_all_drafts(semester)

    progress("Building required-unit map", 8)

    # ── Build required map ───────────────────────────────────────────────────
    intakes = list(Intake.objects.filter(is_active=True).select_related("programme"))
    required: dict[Any, list[Unit]] = {}
    for intake in intakes:
        stage = _resolve_stage(intake, semester)
        if stage is None:
            continue
        _sync_stage_units(intake, semester, stage)
        units = _effective_units(intake, semester)
        if units:
            required[intake.id] = units

    if not required:
        result = {
            "status": "SUCCESS", "scheduled": 0, "total_required": 0,
            "completion_rate": 0, "deleted_drafts": deleted,
            "message": "No units to schedule",
        }
        _set_progress(task_id, {**result, "percent": 100})
        return result

    total_required = sum(len(v) for v in required.values())
    progress("Loading occupancy cache", 12)

    time_slots  = list(TimeSlot.objects.all().order_by("order"))
    double_pairs = _get_double_pairs(time_slots)
    all_weeks    = list(range(1, semester.teaching_weeks + 1))
    occ          = OccupancyCache.build(semester)
    buf          = EntryBuffer()
    intake_map   = {i.id: i for i in intakes if i.id in required}

    # ── Pass 0: shared units ─────────────────────────────────────────────────
    progress("Scheduling shared units", 15)
    pre_scheduled, shared_count = _schedule_shared_units(
        semester, required, time_slots, double_pairs, all_weeks, occ, buf)

    # Flush shared-unit entries once before main loop.
    buf.flush()
    progress("Shared units flushed", 18)

    # ── Passes 1–3: per-intake units ─────────────────────────────────────────
    scheduled_keys: set[str] = set()
    on_attachment: list[str] = []
    all_failures: list[dict] = []

    total_intakes = len(required)
    intakes_done  = 0

    for config in _RETRY_CONFIGS:
        if not required:
            break
        pass_failures: list[dict] = []
        newly_done: set = set()

        for intake_id, units in list(required.items()):
            intake = intake_map.get(intake_id)
            if intake is None:
                del required[intake_id]; continue

            if _resolve_stage(intake, semester) is None:
                on_attachment.append(intake.name)
                del required[intake_id]; continue

            for unit in list(units):
                key = f"{intake_id}_{unit.id}"
                if key in scheduled_keys:
                    newly_done.add(unit.id); continue
                if all((str(intake_id), str(unit.id), w) in pre_scheduled
                       for w in all_weeks):
                    scheduled_keys.add(key); newly_done.add(unit.id); continue

                ok = _schedule_intake_unit(
                    semester, intake, unit, config,
                    time_slots, double_pairs, all_weeks, occ, buf)

                if ok["success"]:
                    scheduled_keys.add(key); newly_done.add(unit.id)
                else:
                    pass_failures.append({
                        "intake": intake.name, "unit": unit.code,
                        "reason": ok["reason"], "retry_level": config["name"],
                    })

            # Flush per-intake to bound memory usage.
            buf.flush()
            intakes_done += 1
            pct = 18 + int(intakes_done / max(total_intakes, 1) * 70)
            progress(f"{config['name']}: processed {intake.name}", min(pct, 88))

        all_failures = pass_failures
        for iid in list(required):
            required[iid] = [u for u in required[iid] if u.id not in newly_done]
            if not required[iid]:
                del required[iid]

    # Flush any remaining buffered entries.
    buf.flush()

    # ── Bulk-create conflict logs ────────────────────────────────────────────
    progress("Writing conflict logs", 90)
    if all_failures:
        ConflictLog.objects.bulk_create([
            ConflictLog(
                semester=semester, conflict_type="TIME", severity="HIGH",
                description=(f"[FAIL] {f['unit']} for {f['intake']}: "
                             f"{f['reason']} (pass: {f['retry_level']})"),
                resolution_status="PENDING",
            )
            for f in all_failures
        ], ignore_conflicts=True)

    _clear_timetable_cache(semester_id=semester.id)

    count = len(scheduled_keys)
    rate  = round(count / total_required * 100, 1) if total_required else 0

    result = {
        "status": "SUCCESS",
        "scheduled": count,
        "total_required": total_required,
        "completion_rate": rate,
        "shared_units_scheduled": shared_count,
        "deleted_drafts": deleted,
        "on_attachment": list(set(on_attachment)),
        "failed_placements": all_failures,
        "emergency_placements": [f for f in all_failures if f["retry_level"] == "EMERGENCY"],
        "needs_manual_review": any(f["retry_level"] == "EMERGENCY" for f in all_failures),
    }

    progress("Complete", 100, **{k: v for k, v in result.items()
                                  if k not in ("status",)})
    _set_progress(task_id, {**result, "percent": 100})
    return result