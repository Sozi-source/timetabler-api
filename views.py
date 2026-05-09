"""
timetable/views.py
==================
Clean, flat REST API.  Every endpoint returns a predictable shape:
  { "ok": true,  "data": {...} }
  { "ok": false, "error": "...", "detail": "..." }

Endpoint map
------------
── Institution / setup ──────────────────────────────────────────────────────
GET  /api/institution/                          InstitutionView
GET  /api/departments/                          DepartmentListView
GET  /api/programmes/                           ProgrammeListView
GET  /api/curriculum/?programme=<id>&term=<n>  CurriculumView
GET  /api/periods/                              PeriodListView
GET  /api/rooms/                                RoomListView
GET  /api/trainers/                             TrainerListView
GET  /api/terms/                                TermListView

── Cohorts & progression ────────────────────────────────────────────────────
GET  /api/cohorts/                              CohortListView
GET  /api/cohorts/<id>/progress/               CohortProgressView
POST /api/cohorts/<id>/advance/                AdvanceCohortView
POST /api/cohorts/<id>/progress/update/        UpdateProgressView

── Enrolments ───────────────────────────────────────────────────────────────
GET  /api/enrolments/                          CohortEnrolmentListView
POST /api/enrolments/                          CohortEnrolmentListView
GET  /api/enrolments/<id>/                     CohortEnrolmentDetailView
PUT  /api/enrolments/<id>/                     CohortEnrolmentDetailView
DEL  /api/enrolments/<id>/                     CohortEnrolmentDetailView

── Semester advancement ─────────────────────────────────────────────────────
GET  /api/term/advance-all/?term=<id>          AdvanceAllCohortsView (preview)
POST /api/term/advance-all/                    AdvanceAllCohortsView (confirm)

── Constraints ──────────────────────────────────────────────────────────────
GET  /api/constraints/                          ConstraintListView
POST /api/constraints/                          ConstraintListView
PUT  /api/constraints/<id>/                     ConstraintDetailView
DEL  /api/constraints/<id>/                     ConstraintDetailView

── Timetable generation ─────────────────────────────────────────────────────
POST /api/timetable/generate/                   GenerateView
POST /api/timetable/publish/                    PublishView
DEL  /api/timetable/drafts/                     DeleteDraftsView

── Timetable reading ────────────────────────────────────────────────────────
GET  /api/timetable/master/?term=<id>           MasterTimetableView
GET  /api/timetable/cohort/<id>/?term=<id>      CohortTimetableView
GET  /api/timetable/trainer/<id>/?term=<id>     TrainerTimetableView

── Conflicts ────────────────────────────────────────────────────────────────
GET  /api/conflicts/?term=<id>                  ConflictListView
POST /api/conflicts/<id>/resolve/               ResolveConflictView

── Exports ──────────────────────────────────────────────────────────────────
GET  /api/export/master/?term=<id>&fmt=html     ExportMasterView
GET  /api/export/trainer/<id>/?term=<id>        ExportTrainerView
GET  /api/export/cohort/<id>/?term=<id>         ExportCohortView

── Dashboard ────────────────────────────────────────────────────────────────
GET  /api/dashboard/                            DashboardView
GET  /api/dashboard/trainer/                    TrainerDashboardView

── Calendar ─────────────────────────────────────────────────────────
GET  /api/calendar/                             CollegeCalendarView

── Validation ───────────────────────────────────────────────────────
GET  /api/timetable/validate/?term=<id>         ValidateView

── Scheduled unit detail ────────────────────────────────────────────
GET  /api/timetable/entries/<id>/               ScheduledUnitDetailView
PUT  /api/timetable/entries/<id>/               ScheduledUnitDetailView
DEL  /api/timetable/entries/<id>/               ScheduledUnitDetailView

── Trainer availability ─────────────────────────────────────────────
GET  /api/trainers/<id>/availability/?term=<id> TrainerAvailabilityView
POST /api/trainers/<id>/availability/           TrainerAvailabilityView

── Term trainer assignments ─────────────────────────────────────────
GET  /api/term-assignments/                     TermTrainerAssignmentListView
POST /api/term-assignments/                     TermTrainerAssignmentListView
GET  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView
PUT  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView
DEL  /api/term-assignments/<id>/                TermTrainerAssignmentDetailView
GET  /api/term-assignments/by-unit/             TermTrainerAssignmentByUnitView
POST /api/term-assignments/bulk/                TermTrainerAssignmentBulkView
"""

from __future__ import annotations

import traceback
from collections import defaultdict
from datetime import date

from django.db import transaction
from django.db.models import Count, Q, F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AuditLog, Cohort, CohortEnrolment, Conflict, Constraint,
    CurriculumUnit, CurriculumUnitTrainer,
    CollegeCalendar, Department, Institution, Period, Programme,
    ProgressRecord, Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
    TermTrainerAssignment,
)
from .scheduler import TimetableEngine
from .serializers import ConstraintSerializer


def _unit_dict(u):
    return {
        "id":               str(u.id),
        "code":             u.code,
        "name":             u.name,
        "term_number":      u.term_number,
        "credit_hours":     u.credit_hours,
        "periods_per_week": u.periods_per_week,
        "session_pattern":  u.session_pattern,
        "unit_type":        u.get_unit_type_display(),
        "is_double":        u.periods_per_week >= 2,
        "is_outsourced":    u.is_outsourced,
    }


class ConstraintListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unit_id    = request.query_params.get("unit")
        cohort_id  = request.query_params.get("cohort")
        trainer_id = request.query_params.get("trainer")
        qs = Constraint.objects.select_related("curriculum_unit", "cohort", "trainer", "room")
        if unit_id:
            qs = qs.filter(curriculum_unit_id=unit_id)
        if cohort_id:
            qs = qs.filter(cohort_id=cohort_id)
        if trainer_id:
            qs = qs.filter(trainer_id=trainer_id)
        return ok(ConstraintSerializer(qs.order_by("-is_hard", "scope"), many=True).data)

    def post(self, request):
        ser = ConstraintSerializer(data=request.data)
        if ser.is_valid():
            c = ser.save()
            return ok({"id": str(c.id)}, 201)
        return err(str(ser.errors), status_code=400)


def _tta_dict(a):
    return {"id": str(a.id)}


class TermTrainerAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = TermTrainerAssignment.objects.all()
        return ok([_tta_dict(a) for a in qs])

    def post(self, request):
        data = request.data
        try:
            term    = get_object_or_404(Term,           id=data["term_id"])
            cohort  = get_object_or_404(Cohort,         id=data["cohort_id"])
            unit    = get_object_or_404(CurriculumUnit, id=data["curriculum_unit_id"])
            trainer = get_object_or_404(Trainer,        id=data["trainer_id"])
            assignment, created = TermTrainerAssignment.objects.update_or_create(
                term=term, cohort=cohort, curriculum_unit=unit,
                defaults={"trainer": trainer, "notes": data.get("notes", "")},
            )
            return ok(_tta_dict(assignment), 201 if created else 200)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)
