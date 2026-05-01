"""
cleanup_stale_units.py
======================
Deletes CurriculumUnit records in the database that are no longer
present in the seed file, identified per programme by course code.

Usage:
    # Dry run first (recommended) — shows what WOULD be deleted:
    python cleanup_stale_units.py --dry-run

    # Actually delete:
    python cleanup_stale_units.py
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetabler.settings")
django.setup()

from timetable.models import Programme, CurriculumUnit, Department  # noqa: E402

# ─── Config (must match seed_curriculum.py) ────────────────────────────────────

DEPARTMENT_ID = "10804c9d-b55c-48a4-a06d-72150016bab7"

# All valid course codes per programme code, extracted from the seed
SEED_UNITS: dict[str, set[str]] = {
    "CND": {
        "CND1101","CND1102","CND1103","CND1104","CND1105","CND1106",
        "CND1201","CND1202","CND1203","CND1204","CND1205","CND1206",
        "CND1301","CND1302","CND1303","CND1304","CND1305","CND1306","CND1307",
        "CND2101","CND2102","CND2103","CND2104","CND2105","CND2106","CND2107",
        "CND2201",
        "CND2301","CND2302","CND2303","CND2304","CND2305","CND2306","CND2307",
    },
    "CHN": {
        "CCU1101","CCU1102","CCU1105","CCU1106","CCU1107","CHN1101",
        "CHN1301","CHN1201","CHN1203","CHN1204","CHN1306","CHN1304",
        "CCU1111","CHN1206","CHN2205","CHN2203","CHN2307","CHN2302","CHN1305",
        "CHN2304","CHN2207","CHN2204","CCU1110","CHN1308","CHN1202","CHN1303",
        "CHN2101",
        "CHN2305","CHN2306","CHN2308","CHN2201","CHN2202","CHN2309","CHN2206",
    },
    "DND": {
        "DND1101","DND1102","DND1103","DND1104","DND1105","DND1106",
        "DND1201","DND1202","DND1203","DND1204","DND1205","DND1206",
        "DND1301","DND1302","DND1303","DND1304","DND1305","DND1306","DND1307",
        "DND2101","DND2102","DND2103","DND2104","DND2105","DND2106","DND2107",
        "DND2201",
        "DND2301","DND2302","DND2303","DND2304","DND2305","DND2306","DND2307",
        "DND3101","DND3102","DND3103","DND3104","DND3105","DND3106",
        "DND3201","DND3202","DND3203","DND3204","DND3205","DND3206",
        "DND3301",
    },
    "DHN": {
        "DCU1101","DCU1102","DCU1105","DCU1106","DCU1107","DHN1101","DHN1103",
        "DHN1203","DHN1207","DHN1206","DHN1208","DHN1303","DHN1307",
        "DCU1111","DHN1209","DHN1304","DHN1305","DHN1205","DHN1209B","DHN2207",
        "DHN3204","DHN3106","DHN2302","DHN1306","DCU1110","DCU1104",
        "DHN2101",
        "DHN2201","DHN2202","DHN2203","DHN2204","DHN2205","DHN2305","DHN2201B",
        "DHN2307","DHN2303","DHN3102","DHN3103","DHN3104","DHN2304","DHN3105",
        "DHN3201","DHN3202","DHN3203","DHN3206","DHN3205","DHN3209",
        "DHN3301",
    },
    "DHNT": {
        "DHNT2301","DHNT2302","DHNT2303","DHNT2304","DHNT2305","DHNT2306","DHNT2307",
        "DHNT3101","DHNT3102","DHNT3103","DHNT3104","DHNT3105","DHNT3106","DHNT3107",
        "DHNT3201","DHNT3202","DHNT3203","DHNT3204","DHNT3205","DHNT3206",
        "DHNT3301",
    },
}

# ─── Main ──────────────────────────────────────────────────────────────────────

def cleanup(dry_run: bool = True):
    mode = "DRY RUN" if dry_run else "LIVE DELETE"
    print(f"\n{'='*62}")
    print(f"  STALE UNIT CLEANUP  [{mode}]")
    print(f"{'='*62}")

    if dry_run:
        print("  ⚠  No changes will be made. Pass no flags to delete.\n")

    department = Department.objects.get(id=DEPARTMENT_ID)
    total_stale = 0

    for prog_code, valid_codes in SEED_UNITS.items():
        try:
            programme = Programme.objects.get(code=prog_code, department=department)
        except Programme.DoesNotExist:
            print(f"\n[{prog_code}] Programme not found in DB — skipping.")
            continue

        # All units in DB for this programme
        db_units = CurriculumUnit.objects.filter(programme=programme)
        stale = db_units.exclude(code__in=valid_codes)
        count = stale.count()

        print(f"\n[{prog_code}] {programme.name}")
        print(f"  DB total: {db_units.count()}  |  Seed total: {len(valid_codes)}  |  Stale: {count}")

        if count == 0:
            print("  ✓ No stale records.")
            continue

        for unit in stale:
            status = "" if unit.is_active else " [INACTIVE]"
            print(f"  {'WOULD DELETE' if dry_run else 'DELETING'}: [T{unit.term_number}] {unit.code}  {unit.name}{status}")

        if not dry_run:
            deleted, _ = stale.delete()
            print(f"  → Deleted {deleted} record(s).")

        total_stale += count

    print(f"\n{'─'*62}")
    if dry_run:
        print(f"  TOTAL stale records found: {total_stale}")
        print(f"  Run without --dry-run to permanently delete them.")
    else:
        print(f"  TOTAL deleted: {total_stale}")
    print(f"{'─'*62}\n")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    cleanup(dry_run=dry_run)
