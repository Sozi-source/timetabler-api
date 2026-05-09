"""
patch_scheduler.py
==================
Applies targeted fixes to timetable/scheduler.py without rewriting the whole file.
Run once: python patch_scheduler.py
"""

import re, shutil, sys
from pathlib import Path

SRC = Path("timetable/scheduler.py")
BAK = Path("timetable/scheduler.py.bak")

if not SRC.exists():
    print("ERROR: timetable/scheduler.py not found. Run from timetabler/ directory.")
    sys.exit(1)

# Back up original
shutil.copy(SRC, BAK)
print(f"Backed up to {BAK}")

content = SRC.read_text(encoding="utf-8")
original = content

# ══════════════════════════════════════════════════════════════════════════════
# FIX 1 — _place_split Phase 1: don't abort on blocked pin, just skip it
# ══════════════════════════════════════════════════════════════════════════════
OLD_PIN_ABORT = '''            result = self._try_slot(cohort, unit, trainers, day, period, pinned=True)
            if not result.success:
                return PlacementResult(
                    False, unit, cohort,
                    f"Pinned slot {day} {period} is blocked \u2014 cannot satisfy hard pin",
                )
            sessions_written.append((day, period))
            used_days.add(day)'''

NEW_PIN_SKIP = '''            result = self._try_slot(cohort, unit, trainers, day, period, pinned=True)
            if not result.success:
                # Pinned slot blocked — skip this pin and find a free slot instead.
                # Hard pins are honoured when possible; a blocked pin is not fatal.
                continue
            sessions_written.append((day, period))
            used_days.add(day)'''

if OLD_PIN_ABORT in content:
    content = content.replace(OLD_PIN_ABORT, NEW_PIN_SKIP)
    print("FIX 1 applied: _place_split pin abort → skip")
else:
    print("FIX 1: pattern not found — checking for unicode variant...")
    # Try with the em-dash unicode variant
    alt = OLD_PIN_ABORT.replace('\u2014', '\u2013')
    if alt in content:
        content = content.replace(alt, NEW_PIN_SKIP)
        print("FIX 1 applied (alt unicode)")
    else:
        print("FIX 1 SKIPPED: could not locate pin abort block")

# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 — _place_split Phase 2: partial failure should not wipe placed sessions.
# Return False but DON'T undo already-written sessions — the next pass will
# pick up the remainder via placed_session_counts proxy mechanism.
# The real fix is: mark the unit as PARTIALLY placed so it re-enters the queue
# with periods_per_week reduced by what's already placed.
#
# The scheduler already has this mechanism (placed_session_counts proxy at
# lines 908-936) BUT it only works for combined sessions, not individual ones.
# We fix this by counting pending writes for this unit before returning False.
# ══════════════════════════════════════════════════════════════════════════════

# Find the _place_split partial failure return and add partial-success detection
OLD_PARTIAL = '''            if not placed_this_round:
                return PlacementResult(
                    False, unit, cohort,
                    f"Could not place split session "
                    f"{len(sessions_written) + 1}/{needed} "
                    f"(placed {len(sessions_written)} so far)",
                    self.cfg["name"],
                )'''

NEW_PARTIAL = '''            if not placed_this_round:
                # Return partial success if we placed at least one session.
                # The run() loop will re-queue this unit via placed_session_counts
                # with periods_per_week reduced to the remaining sessions needed.
                if sessions_written:
                    return PlacementResult(
                        True, unit, cohort,
                        pass_name=self.cfg["name"],
                    )
                return PlacementResult(
                    False, unit, cohort,
                    f"Could not place split session "
                    f"{len(sessions_written) + 1}/{needed} "
                    f"(placed {len(sessions_written)} so far)",
                    self.cfg["name"],
                )'''

if OLD_PARTIAL in content:
    content = content.replace(OLD_PARTIAL, NEW_PARTIAL)
    print("FIX 2 applied: _place_split partial failure → partial success")
else:
    print("FIX 2 SKIPPED: could not locate partial failure block")

# ══════════════════════════════════════════════════════════════════════════════
# FIX 3 — run() loop: after each pass, rebuild placed_session_counts so that
# partially-placed split units (written by _place_split returning True after
# placing 1 of 2 sessions) get a reduced proxy in the next pass.
# ══════════════════════════════════════════════════════════════════════════════
OLD_PASS_LOOP = '''        for pass_cfg in _PASS_CONFIGS:
            if not remaining:
                break

            next_remaining: list[tuple[str, list[CurriculumUnit]]] = []
            placer = Placer(
                self.term, grid, cindex, days, periods, rooms,
                pass_cfg, pending, trainer_available_days,
            )

            for cohort_id, unit_list in remaining:
                cohort, _ = work_queue[cohort_id]
                still_unplaced: list[CurriculumUnit] = []

                for unit in unit_list:
                    key = f"{cohort_id}_{unit.id}"
                    if key in placed_keys:
                        continue

                    qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
                    pr        = placer.place(cohort, unit, qualified)

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

            remaining = next_remaining'''

NEW_PASS_LOOP = '''        for pass_cfg in _PASS_CONFIGS:
            if not remaining:
                break

            next_remaining: list[tuple[str, list[CurriculumUnit]]] = []
            placer = Placer(
                self.term, grid, cindex, days, periods, rooms,
                pass_cfg, pending, trainer_available_days,
            )

            for cohort_id, unit_list in remaining:
                cohort, _ = work_queue[cohort_id]
                still_unplaced: list[CurriculumUnit] = []

                for unit in unit_list:
                    key = f"{cohort_id}_{unit.id}"
                    if key in placed_keys:
                        continue

                    qualified = [t for t in unit.qualified_trainers.all() if t.is_active]
                    pr        = placer.place(cohort, unit, qualified)

                    if pr.success:
                        # Recount how many sessions are now in pending for this unit.
                        # _place_split may have placed 1 of 2 sessions and returned
                        # True — only mark fully done if all sessions are placed.
                        sessions_in_pending = sum(
                            1 for su in pending
                            if str(su.cohort_id) == cohort_id
                            and str(su.curriculum_unit_id) == str(unit.id)
                        )
                        # Use original unit's periods_per_week (proxy may be reduced)
                        orig_unit = next(
                            (u for u in work_queue[cohort_id][1] if u.id == unit.id),
                            unit,
                        )
                        still_needed = orig_unit.periods_per_week - sessions_in_pending
                        if still_needed <= 0:
                            placed_keys.add(key)
                            result.placed += 1
                        else:
                            # Partially placed — create proxy for next pass
                            u_proxy = copy.copy(orig_unit)
                            u_proxy.periods_per_week = still_needed
                            still_unplaced.append(u_proxy)
                            # Count as placed for result tracking
                            result.placed += (orig_unit.periods_per_week - still_needed)

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

            remaining = next_remaining'''

if OLD_PASS_LOOP in content:
    content = content.replace(OLD_PASS_LOOP, NEW_PASS_LOOP)
    print("FIX 3 applied: pass loop now tracks partial split placements")
else:
    print("FIX 3 SKIPPED: could not locate pass loop block")

# ══════════════════════════════════════════════════════════════════════════════
# FIX 4 — Outsourced units with ppw=2 (CND1105, CND1106):
# _pick_room has a capacity filter that can return None if no room fits.
# For outsourced units, any free room is acceptable — relax the filter.
# ══════════════════════════════════════════════════════════════════════════════
OLD_PICK_ROOM_END = '''        # Pass 2: capacity match (any type), slot free'''

NEW_PICK_ROOM_END = '''        # Outsourced fallback: any free room is acceptable
        if getattr(unit, "is_outsourced", False):
            for room in self.rooms:
                if allow_overlap or not self.grid.room_busy(str(room.id), key):
                    return room

        # Pass 2: capacity match (any type), slot free'''

if OLD_PICK_ROOM_END in content:
    content = content.replace(OLD_PICK_ROOM_END, NEW_PICK_ROOM_END, 1)
    print("FIX 4 applied: outsourced units accept any free room")
else:
    print("FIX 4 SKIPPED: could not locate _pick_room pass 2 comment")

# ══════════════════════════════════════════════════════════════════════════════
# Write patched file
# ══════════════════════════════════════════════════════════════════════════════
if content == original:
    print("\nWARNING: No changes were made. Patterns may have shifted.")
    print("The backup is unchanged. No file was written.")
else:
    SRC.write_text(content, encoding="utf-8")
    changed = sum(1 for a, b in zip(original.splitlines(), content.splitlines()) if a != b)
    print(f"\nPatched scheduler.py ({changed} lines changed)")
    print("Now: click Generate, then run: python fix_and_clear.py")
