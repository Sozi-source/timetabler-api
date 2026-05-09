"""
apply_patches.py
================
Run from your Django project root (same folder as manage.py):

    python apply_patches.py

Paths are resolved relative to this script's location, so it works
on Windows, macOS, and Linux without any changes.
"""
import os, sys

# ── Resolve paths relative to this script, not the working directory ─────────
HERE        = os.path.dirname(os.path.abspath(__file__))
VIEWS       = os.path.join(HERE, "timetable", "views.py")
SERIALIZERS = os.path.join(HERE, "timetable", "serializers.py")
SCHEDULER   = os.path.join(HERE, "timetable", "scheduler.py")
MODELS      = os.path.join(HERE, "timetable", "models.py")

# ── Sanity-check that every file exists before touching anything ──────────────
missing = [p for p in (VIEWS, SERIALIZERS, SCHEDULER, MODELS) if not os.path.exists(p)]
if missing:
    print("\nERROR: could not find the following files:")
    for p in missing:
        print(f"  {p}")
    print("\nMake sure apply_patches.py is in the same folder as manage.py,")
    print("and that the timetable/ app directory is directly inside it.")
    sys.exit(1)

results = []

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def write(p, t):
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)

def apply(fix_id, path, old, new, desc):
    src = read(path)
    if old not in src:
        results.append(("SKIP", fix_id, desc, "target string not found — already patched or text differs"))
        return
    write(path, src.replace(old, new, 1))
    results.append(("OK", fix_id, desc, ""))


# ── FIX 1 ── views.py: add TermTrainerAssignment to model imports ─────────────
apply(
    "1",
    VIEWS,
    "from .models import (\n"
    "    AuditLog, Cohort, CohortEnrolment, Conflict, Constraint,\n"
    "    CurriculumUnit, CurriculumUnitTrainer,\n"
    "    CollegeCalendar, Department, Institution, Period, Programme,\n"
    "    ProgressRecord, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    ")",
    "from .models import (\n"
    "    AuditLog, Cohort, CohortEnrolment, Conflict, Constraint,\n"
    "    CurriculumUnit, CurriculumUnitTrainer,\n"
    "    CollegeCalendar, Department, Institution, Period, Programme,\n"
    "    ProgressRecord, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    "    TermTrainerAssignment,\n"
    ")",
    "Add TermTrainerAssignment to views.py top-level imports (prevents NameError)",
)


# ── FIX 2a ── views.py: hoist ConstraintSerializer to module level ────────────
apply(
    "2a",
    VIEWS,
    "from .scheduler import TimetableEngine\n",
    "from .scheduler import TimetableEngine\n"
    "from .serializers import ConstraintSerializer\n",
    "ConstraintSerializer imported at module level in views.py",
)

# ── FIX 2b ── views.py: remove lazy import inside ConstraintListView.get ──────
apply(
    "2b",
    VIEWS,
    "        from .serializers import ConstraintSerializer\n"
    "        return ok(ConstraintSerializer(qs.order_by(\"-is_hard\", \"scope\"), many=True).data)",
    "        return ok(ConstraintSerializer(qs.order_by(\"-is_hard\", \"scope\"), many=True).data)",
    "Removed lazy ConstraintSerializer import from ConstraintListView.get",
)

# ── FIX 2c ── views.py: remove lazy import inside ConstraintListView.post ─────
apply(
    "2c",
    VIEWS,
    "    def post(self, request):\n"
    "        from .serializers import ConstraintSerializer\n"
    "        ser = ConstraintSerializer(data=request.data)",
    "    def post(self, request):\n"
    "        ser = ConstraintSerializer(data=request.data)",
    "Removed lazy ConstraintSerializer import from ConstraintListView.post",
)


# ── FIX 3a ── scheduler.py: hoist Programme import to module level ────────────
apply(
    "3a",
    SCHEDULER,
    "from .models import (\n"
    "    Cohort, Conflict, Constraint, CurriculumUnit,\n"
    "    Period, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    ")",
    "from .models import (\n"
    "    Cohort, Conflict, Constraint, CurriculumUnit,\n"
    "    Period, Programme, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,\n"
    ")",
    "Programme added to scheduler.py module-level imports",
)

# ── FIX 3b ── scheduler.py: remove local Programme import inside method ────────
apply(
    "3b",
    SCHEDULER,
    "        from .models import Programme\n\n"
    "        groups = list(",
    "        groups = list(",
    "Removed redundant local import of Programme inside _schedule_combined",
)

# ── FIX 3c ── scheduler.py: document session_pattern guard (Placer) ───────────
apply(
    "3c",
    SCHEDULER,
    "        is_block = (\n"
    "            getattr(unit, \"session_pattern\", \"SPLIT\") == \"BLOCK\"\n"
    "            and len(all_pins) < 2\n"
    "        )",
    "        # NOTE: session_pattern is not yet a model field; getattr defaults to\n"
    "        # \"SPLIT\" so block-scheduling is dormant until the field is added to\n"
    "        # CurriculumUnit (Fix 4 in models.py adds it).\n"
    "        is_block = (\n"
    "            getattr(unit, \"session_pattern\", \"SPLIT\") == \"BLOCK\"\n"
    "            and len(all_pins) < 2\n"
    "        )",
    "Documented session_pattern getattr guard in Placer._place",
)

# ── FIX 3d ── scheduler.py: document guard in _schedule_combined ───────────────
apply(
    "3d",
    SCHEDULER,
    "                    is_split = (\n"
    "                        source_unit.periods_per_week >= 2\n"
    "                        and (\n"
    "                            getattr(source_unit, \"session_pattern\", \"SPLIT\") != \"BLOCK\"\n"
    "                            or len(all_pins) >= 2\n"
    "                        )\n"
    "                    )",
    "                    # session_pattern defaults to SPLIT until field exists on the model.\n"
    "                    is_split = (\n"
    "                        source_unit.periods_per_week >= 2\n"
    "                        and (\n"
    "                            getattr(source_unit, \"session_pattern\", \"SPLIT\") != \"BLOCK\"\n"
    "                            or len(all_pins) >= 2\n"
    "                        )\n"
    "                    )",
    "Documented session_pattern guard in _schedule_combined",
)


# ── FIX 4 ── models.py: add session_pattern field to CurriculumUnit ───────────
apply(
    "4",
    MODELS,
    "    is_outsourced      = models.BooleanField(\n"
    "        default=False,\n"
    "        help_text=\"Unit is taught by an external/outsourced trainer\",\n"
    "    )",
    "    SESSION_PATTERN_CHOICES = [\n"
    "        (\"SPLIT\", \"Split \u2014 one session per day across multiple days\"),\n"
    "        (\"BLOCK\", \"Block \u2014 consecutive periods on the same day\"),\n"
    "    ]\n"
    "    session_pattern    = models.CharField(\n"
    "        max_length=5,\n"
    "        choices=SESSION_PATTERN_CHOICES,\n"
    "        default=\"SPLIT\",\n"
    "        help_text=\"SPLIT = one session per day; BLOCK = consecutive double period\",\n"
    "    )\n"
    "    is_outsourced      = models.BooleanField(\n"
    "        default=False,\n"
    "        help_text=\"Unit is taught by an external/outsourced trainer\",\n"
    "    )",
    "Added session_pattern field to CurriculumUnit model",
)


# ── FIX 5 ── views.py: add missing views to endpoint map docstring ─────────────
apply(
    "5",
    VIEWS,
    "── Dashboard \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\nGET  /api/dashboard/                            DashboardView\n"
    "GET  /api/dashboard/trainer/                    TrainerDashboardView\n"
    '"""',
    "── Dashboard \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\nGET  /api/dashboard/                            DashboardView\n"
    "GET  /api/dashboard/trainer/                    TrainerDashboardView\n"
    "\n"
    "── Calendar \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
    "GET  /api/calendar/                             CollegeCalendarView\n"
    "\n"
    "── Validation \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
    "GET  /api/timetable/validate/?term=<id>         ValidateView\n"
    "\n"
    "── Scheduled unit detail \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
    "GET  /api/timetable/entries/<id>/               ScheduledUnitDetailView\n"
    "PUT  /api/timetable/entries/<id>/               ScheduledUnitDetailView\n"
    "DEL  /api/timetable/entries/<id>/               ScheduledUnitDetailView\n"
    "\n"
    "── Trainer availability \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
    "GET  /api/trainers/<id>/availability/?term=<id> TrainerAvailabilityView\n"
    "POST /api/trainers/<id>/availability/           TrainerAvailabilityView\n"
    "\n"
    "── Term trainer assignments \u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n"
    "GET  /api/term-assignments/                     TermTrainerAssignmentListView\n"
    "POST /api/term-assignments/                     TermTrainerAssignmentListView\n"
    "GET  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView\n"
    "PUT  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView\n"
    "DEL  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView\n"
    "GET  /api/term-assignments/by-unit/             TermTrainerAssignmentByUnitView\n"
    "POST /api/term-assignments/bulk/                TermTrainerAssignmentBulkView\n"
    '"""',
    "Added 11 undocumented endpoints to views.py module docstring",
)


# ── FIX 6a ── serializers.py: add session_pattern to read serializer ──────────
apply(
    "6a",
    SERIALIZERS,
    "            \"id\", \"programme_code\", \"term_number\", \"position\", \"code\",\n"
    "            \"name\", \"unit_type\", \"credit_hours\", \"periods_per_week\",\n"
    "            \"is_active\", \"notes\", \"qualified_trainers\",\n"
    "        ]",
    "            \"id\", \"programme_code\", \"term_number\", \"position\", \"code\",\n"
    "            \"name\", \"unit_type\", \"credit_hours\", \"periods_per_week\",\n"
    "            \"session_pattern\", \"is_active\", \"notes\", \"qualified_trainers\",\n"
    "        ]",
    "session_pattern added to CurriculumUnitReadSerializer.fields",
)

# ── FIX 6b ── serializers.py: add session_pattern to write serializer ─────────
apply(
    "6b",
    SERIALIZERS,
    "            \"programme_id\", \"term_number\", \"position\", \"code\",\n"
    "            \"name\", \"unit_type\", \"credit_hours\", \"periods_per_week\",\n"
    "            \"is_active\", \"notes\", \"qualified_trainers\",\n"
    "        ]",
    "            \"programme_id\", \"term_number\", \"position\", \"code\",\n"
    "            \"name\", \"unit_type\", \"credit_hours\", \"periods_per_week\",\n"
    "            \"session_pattern\", \"is_active\", \"notes\", \"qualified_trainers\",\n"
    "        ]",
    "session_pattern added to CurriculumUnitWriteSerializer.fields",
)


# ── FIX 7 ── views.py: expose session_pattern in _unit_dict ──────────────────
apply(
    "7",
    VIEWS,
    "        \"periods_per_week\": u.periods_per_week,\n"
    "        \"unit_type\":        u.get_unit_type_display(),",
    "        \"periods_per_week\": u.periods_per_week,\n"
    "        \"session_pattern\":  u.session_pattern,\n"
    "        \"unit_type\":        u.get_unit_type_display(),",
    "session_pattern exposed in _unit_dict API response helper",
)


# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 72)
print(f"  {'ID':<4} {'STATUS':<6}  DESCRIPTION")
print("=" * 72)
ok_n = skip_n = 0
for status, fid, desc, note in results:
    icon = "+" if status == "OK" else "-"
    print(f"  {icon} {fid:<4} [{status}]  {desc}")
    if note:
        print(f"             note: {note}")
    if status == "OK":
        ok_n += 1
    else:
        skip_n += 1
print("=" * 72)
print(f"  Applied: {ok_n}   Skipped: {skip_n}")
print()
if ok_n > 0:
    print("  Next step: python manage.py makemigrations timetable && python manage.py migrate")
print()
