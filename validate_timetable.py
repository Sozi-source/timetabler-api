"""
validate_timetable.py
=====================
Interactive pre-generation validator for the ICMHS timetabling system.
Run this before every Generate to catch data problems early.

Usage:
    python validate_timetable.py
"""

import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from collections import defaultdict
from timetable.models import (
    Cohort, Term, CurriculumUnit, Trainer,
    Room, Period, TrainerAvailability, ScheduledUnit
)

# ── Colours ────────────────────────────────────────────────────────────────────
try:
    import colorama; colorama.init()
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
except ImportError:
    RED = YELLOW = GREEN = CYAN = BOLD = RESET = ""

def header(text):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")

def ok(msg):    print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def error(msg): print(f"  {RED}✗{RESET}  {msg}")
def info(msg):  print(f"     {msg}")

def pause():
    input(f"\n{BOLD}  Press Enter to continue...{RESET}")

# ── Data loading ───────────────────────────────────────────────────────────────
def load_context():
    term = Term.objects.filter(is_current=True).first()
    if not term:
        print(f"{RED}No current term found. Set a term as current in admin.{RESET}")
        sys.exit(1)

    DAYS = ["MON", "TUE", "WED", "THU", "FRI"]
    periods = list(Period.objects.filter(
        institution=term.institution, is_break=False
    ).order_by("order"))
    all_slots = {(d, p.id) for d in DAYS for p in periods}

    cohorts = list(Cohort.objects.filter(is_active=True).order_by("name"))
    trainers = list(Trainer.objects.filter(institution=term.institution, is_active=True))
    rooms = list(Room.objects.filter(institution=term.institution, is_active=True))

    # Trainer availability
    trainer_avail = defaultdict(set)
    for ta in TrainerAvailability.objects.filter(term=term, is_available=True):
        trainer_avail[ta.trainer_id].add((ta.day, ta.period_id))

    # Trainer current load (existing DRAFT sessions)
    trainer_load = defaultdict(int)
    for su in ScheduledUnit.objects.filter(term=term, status="DRAFT"):
        if su.trainer_id:
            trainer_load[su.trainer_id] += 1

    return dict(
        term=term, DAYS=DAYS, periods=periods, all_slots=all_slots,
        cohorts=cohorts, trainers=trainers, rooms=rooms,
        trainer_avail=trainer_avail, trainer_load=trainer_load
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def check_no_trainer(ctx):
    """Units with zero qualified trainers and not outsourced."""
    header("CHECK 1 — Units with no qualified trainer")
    issues = []
    for cohort in ctx["cohorts"]:
        units = CurriculumUnit.objects.filter(
            programme=cohort.programme,
            term_number=cohort.current_term,
            is_active=True
        )
        for unit in units:
            if getattr(unit, "is_outsourced", False):
                continue
            trainers = list(unit.qualified_trainers.filter(is_active=True))
            if not trainers:
                issues.append((cohort.name, unit.code, unit.name))

    if not issues:
        ok("All active units have at least one qualified trainer.")
        return []

    error(f"{len(issues)} unit(s) have NO qualified trainer assigned:")
    for cohort_name, code, name in issues:
        info(f"{cohort_name:20}  {code}  {name}")

    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] Mark these units as OUTSOURCED (no trainer required)")
    print("  [2] Assign a trainer to each unit now")
    print("  [3] Skip (leave as-is, these will fail to schedule)")

    choice = input(f"\n  {BOLD}Your choice [1/2/3]: {RESET}").strip()

    if choice == "1":
        for cohort_name, code, name in issues:
            unit = CurriculumUnit.objects.filter(code=code).first()
            unit.is_outsourced = True
            unit.save()
            ok(f"{code} marked as outsourced")

    elif choice == "2":
        active_trainers = ctx["trainers"]
        print(f"\n  {BOLD}Available trainers:{RESET}")
        for i, t in enumerate(active_trainers, 1):
            load = ctx["trainer_load"].get(t.id, 0)
            print(f"  [{i}] {t.first_name} {t.last_name} (current load: {load})")

        for cohort_name, code, name in issues:
            unit = CurriculumUnit.objects.filter(code=code).first()
            sel = input(f"\n  Trainer for {code} ({cohort_name}) [number or Enter to skip]: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(active_trainers):
                trainer = active_trainers[int(sel) - 1]
                unit.qualified_trainers.add(trainer)
                ok(f"{code} → {trainer.first_name} {trainer.last_name}")
            else:
                warn(f"{code} skipped")
    else:
        warn("Skipped — these units will remain unscheduled.")

    return issues


def check_single_trainer(ctx):
    """Units with only one qualified trainer."""
    header("CHECK 2 — Units with only ONE qualified trainer (bottleneck risk)")
    issues = []
    for cohort in ctx["cohorts"]:
        units = CurriculumUnit.objects.filter(
            programme=cohort.programme,
            term_number=cohort.current_term,
            is_active=True
        )
        for unit in units:
            if getattr(unit, "is_outsourced", False):
                continue
            trainers = list(unit.qualified_trainers.filter(is_active=True))
            if len(trainers) == 1:
                t = trainers[0]
                load = ctx["trainer_load"].get(t.id, 0)
                issues.append((cohort.name, unit.code, t.first_name, t.last_name, load))

    if not issues:
        ok("No single-trainer bottlenecks found.")
        return []

    warn(f"{len(issues)} unit(s) have only ONE qualified trainer:")
    for cohort_name, code, fn, ln, load in issues:
        info(f"{cohort_name:20}  {code}  → {fn} {ln} (load: {load})")

    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] Add a backup trainer to flagged units")
    print("  [2] Skip (scheduler will use the single trainer)")

    choice = input(f"\n  {BOLD}Your choice [1/2]: {RESET}").strip()

    if choice == "1":
        active_trainers = ctx["trainers"]
        print(f"\n  {BOLD}Available trainers:{RESET}")
        for i, t in enumerate(active_trainers, 1):
            load = ctx["trainer_load"].get(t.id, 0)
            print(f"  [{i}] {t.first_name} {t.last_name} (load: {load})")

        for cohort_name, code, fn, ln, load in issues:
            unit = CurriculumUnit.objects.filter(code=code).first()
            sel = input(f"\n  Backup trainer for {code} ({cohort_name}) [number or Enter to skip]: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(active_trainers):
                trainer = active_trainers[int(sel) - 1]
                unit.qualified_trainers.add(trainer)
                ok(f"{code} backup → {trainer.first_name} {trainer.last_name}")
            else:
                warn(f"{code} skipped")
    else:
        warn("Skipped — single-trainer units may fail if trainer is overloaded.")

    return issues


def check_trainer_overload(ctx):
    """Trainers whose scheduled periods exceed their max_periods_per_week."""
    header("CHECK 3 — Trainer overload (exceeding max periods per week)")
    issues = []
    for t in ctx["trainers"]:
        load = ctx["trainer_load"].get(t.id, 0)
        max_pw = getattr(t, "max_periods_per_week", None)
        if max_pw and load > max_pw:
            issues.append((t, load, max_pw))

    if not issues:
        ok("No trainers are over their weekly maximum.")
        return []

    for t, load, max_pw in issues:
        error(f"{t.first_name} {t.last_name}: {load} sessions (max {max_pw})")

    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] Show which sessions to consider reassigning")
    print("  [2] Increase max_periods_per_week for affected trainers")
    print("  [3] Skip")

    choice = input(f"\n  {BOLD}Your choice [1/2/3]: {RESET}").strip()

    if choice == "1":
        term = ctx["term"]
        for t, load, max_pw in issues:
            excess = load - max_pw
            print(f"\n  {BOLD}{t.first_name} {t.last_name} — last {excess} session(s) scheduled:{RESET}")
            sus = ScheduledUnit.objects.filter(
                term=term, trainer=t, status="DRAFT"
            ).select_related("cohort", "curriculum_unit").order_by("day", "period_id")
            for su in sus[max_pw:]:
                print(f"    {su.cohort.name}  {su.curriculum_unit.code}  {su.day} p{su.period_id}")
        warn("No changes made — reassign manually in admin or re-generate.")

    elif choice == "2":
        for t, load, max_pw in issues:
            val = input(f"  New max for {t.first_name} {t.last_name} (current {max_pw}, Enter to skip): ").strip()
            if val.isdigit():
                t.max_periods_per_week = int(val)
                t.save()
                ok(f"{t.first_name} {t.last_name} max → {val}")
    else:
        warn("Skipped.")

    return issues


def check_room_capacity(ctx):
    """Are there enough rooms for the peak number of simultaneous sessions?"""
    header("CHECK 4 — Room capacity (peak slot demand)")
    term = ctx["term"]
    DAYS = ctx["DAYS"]
    periods = ctx["periods"]

    slot_demand = defaultdict(int)
    for cohort in ctx["cohorts"]:
        units = CurriculumUnit.objects.filter(
            programme=cohort.programme,
            term_number=cohort.current_term,
            is_active=True
        )
        total = sum(u.periods_per_week for u in units)
        # Rough estimate: spread evenly across available slots
        slots = len(DAYS) * len(periods)
        if slots:
            for d in DAYS:
                for p in periods:
                    slot_demand[(d, p.id)] += total / slots

    peak = max(slot_demand.values()) if slot_demand else 0
    num_rooms = len(ctx["rooms"])

    if peak <= num_rooms:
        ok(f"Peak estimated demand ({peak:.1f}) fits within {num_rooms} rooms.")
    else:
        warn(f"Peak estimated demand ({peak:.1f}) may exceed {num_rooms} rooms.")
        info("Consider adding rooms or staggering cohort schedules.")

    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] List all active rooms")
    print("  [2] Continue")

    choice = input(f"\n  {BOLD}Your choice [1/2]: {RESET}").strip()
    if choice == "1":
        for r in ctx["rooms"]:
            cap = getattr(r, "capacity", "?")
            print(f"    {r.name}  (capacity: {cap})")

    return []


def check_slot_availability(ctx):
    """Cohorts whose curriculum demands more periods than available weekly slots."""
    header("CHECK 5 — Cohort slot sufficiency")
    issues = []
    total_slots = len(ctx["DAYS"]) * len(ctx["periods"])

    for cohort in ctx["cohorts"]:
        units = CurriculumUnit.objects.filter(
            programme=cohort.programme,
            term_number=cohort.current_term,
            is_active=True
        )
        demand = sum(u.periods_per_week for u in units)
        if demand > total_slots:
            issues.append((cohort.name, demand, total_slots))

    if not issues:
        ok(f"All cohorts fit within {total_slots} available weekly slots.")
        return []

    for name, demand, slots in issues:
        error(f"{name}: needs {demand} periods but only {slots} slots exist per week")

    warn("These cohorts CANNOT be fully scheduled. Reduce curriculum periods or add slots.")
    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] Show which units are contributing most periods")
    print("  [2] Skip")

    choice = input(f"\n  {BOLD}Your choice [1/2]: {RESET}").strip()
    if choice == "1":
        for cohort in ctx["cohorts"]:
            if cohort.name not in [i[0] for i in issues]:
                continue
            units = CurriculumUnit.objects.filter(
                programme=cohort.programme,
                term_number=cohort.current_term,
                is_active=True
            ).order_by("-periods_per_week")
            print(f"\n  {cohort.name}:")
            for u in units:
                print(f"    {u.code}  {u.periods_per_week} periods/week")

    return issues


def check_existing_clashes(ctx):
    """Check for clashes in already-scheduled sessions."""
    header("CHECK 6 — Existing schedule clashes")
    term = ctx["term"]

    cohort_slots  = defaultdict(list)
    trainer_slots = defaultdict(list)
    room_slots    = defaultdict(list)

    for su in ScheduledUnit.objects.filter(term=term, status="DRAFT").select_related(
        "cohort", "curriculum_unit", "trainer", "room"
    ):
        key = (su.day, su.period_id)
        cohort_slots[(su.cohort_id, *key)].append(su)
        if su.trainer_id:
            trainer_slots[(su.trainer_id, *key)].append(su)
        if su.room_id:
            room_slots[(su.room_id, *key)].append(su)

    clash_found = False

    for (cid, day, pid), sus in cohort_slots.items():
        if len(sus) > 1:
            clash_found = True
            codes = ", ".join(s.curriculum_unit.code for s in sus)
            error(f"Cohort clash: {sus[0].cohort.name} {day} p{pid} → {codes}")

    for (tid, day, pid), sus in trainer_slots.items():
        cohort_ids = {s.cohort_id for s in sus}
        if len(sus) > 1 and len(cohort_ids) == 1:
            clash_found = True
            codes = ", ".join(s.curriculum_unit.code for s in sus)
            error(f"Trainer clash: {sus[0].trainer.first_name} {sus[0].trainer.last_name} {day} p{pid} → {codes}")

    for (rid, day, pid), sus in room_slots.items():
        cohort_ids = {s.cohort_id for s in sus}
        if len(sus) > 1 and len(cohort_ids) == 1:
            clash_found = True
            codes = ", ".join(s.curriculum_unit.code for s in sus)
            error(f"Room clash: {sus[0].room.name} {day} p{pid} → {codes}")

    if not clash_found:
        ok("No clashes found in current schedule.")

    print(f"\n  {BOLD}Options:{RESET}")
    print("  [1] Clear all DRAFT sessions and re-generate fresh")
    print("  [2] Continue without clearing")

    choice = input(f"\n  {BOLD}Your choice [1/2]: {RESET}").strip()
    if choice == "1":
        count = ScheduledUnit.objects.filter(term=term, status="DRAFT").count()
        confirm = input(f"  Delete {count} DRAFT sessions? [yes/no]: ").strip().lower()
        if confirm == "yes":
            ScheduledUnit.objects.filter(term=term, status="DRAFT").delete()
            ok(f"Cleared {count} sessions. Ready for fresh generation.")
        else:
            warn("Cancelled.")

    return []


def summary_report(ctx):
    """Final placement summary."""
    header("PLACEMENT SUMMARY")
    term = ctx["term"]
    all_ok = True
    for cohort in ctx["cohorts"]:
        units = CurriculumUnit.objects.filter(
            programme=cohort.programme,
            term_number=cohort.current_term,
            is_active=True
        )
        expected = sum(u.periods_per_week for u in units)
        placed = ScheduledUnit.objects.filter(
            cohort=cohort, term=term, status="DRAFT"
        ).count()
        if placed >= expected:
            ok(f"{cohort.name:20}  {placed:3} / {expected:3}")
        else:
            all_ok = False
            error(f"{cohort.name:20}  {placed:3} / {expected:3}  SHORT {expected - placed}")

    if all_ok:
        print(f"\n  {GREEN}{BOLD}All cohorts fully scheduled ✓{RESET}")
    else:
        print(f"\n  {YELLOW}{BOLD}Some cohorts still have gaps — run checks above to resolve.{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

CHECKS = [
    ("Units with no qualified trainer",         check_no_trainer),
    ("Single-trainer bottlenecks",              check_single_trainer),
    ("Trainer overload (over max periods)",     check_trainer_overload),
    ("Room capacity check",                     check_room_capacity),
    ("Cohort slot sufficiency",                 check_slot_availability),
    ("Existing schedule clashes",               check_existing_clashes),
    ("Placement summary",                       summary_report),
]

def main():
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}{CYAN}   ICMHS Timetable Pre-Generation Validator{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}")

    ctx = load_context()
    term = ctx["term"]
    cohorts = ctx["cohorts"]
    print(f"\n  Term   : {BOLD}{term}{RESET}")
    print(f"  Cohorts: {len(cohorts)}")
    print(f"  Rooms  : {len(ctx['rooms'])}")
    print(f"  Periods: {len(ctx['periods'])} per day × {len(ctx['DAYS'])} days = {len(ctx['periods'])*len(ctx['DAYS'])} slots/week")

    while True:
        print(f"\n{BOLD}  ── Main Menu ──────────────────────────────────────────{RESET}")
        print("  [0] Run ALL checks in sequence")
        for i, (label, _) in enumerate(CHECKS, 1):
            print(f"  [{i}] {label}")
        print("  [Q] Quit")

        choice = input(f"\n  {BOLD}Select [0-{len(CHECKS)}/Q]: {RESET}").strip().upper()

        if choice == "Q":
            print(f"\n  {GREEN}Done. Run 'Generate' when ready.{RESET}\n")
            break
        elif choice == "0":
            for label, fn in CHECKS:
                fn(ctx)
                pause()
        elif choice.isdigit() and 1 <= int(choice) <= len(CHECKS):
            CHECKS[int(choice) - 1][1](ctx)
        else:
            warn("Invalid choice.")

if __name__ == "__main__":
    main()
