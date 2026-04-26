"""
timetable/views.py
==================
Clean, flat REST API.  Every endpoint returns a predictable shape:
  { "ok": true,  "data": {...} }
  { "ok": false, "error": "...", "detail": "..." }

Endpoint map
------------
â”€â”€ Institution / setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/institution/                          InstitutionView
GET  /api/departments/                          DepartmentListView
GET  /api/programmes/                           ProgrammeListView
GET  /api/curriculum/?programme=<id>&term=<n>  CurriculumView
GET  /api/periods/                              PeriodListView
GET  /api/rooms/                                RoomListView
GET  /api/trainers/                             TrainerListView
GET  /api/terms/                                TermListView

â”€â”€ Cohorts & progression â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/cohorts/                              CohortListView
GET  /api/cohorts/<id>/progress/               CohortProgressView
POST /api/cohorts/<id>/advance/                AdvanceCohortView
POST /api/cohorts/<id>/progress/update/        UpdateProgressView

â”€â”€ Constraints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/constraints/                          ConstraintListView
POST /api/constraints/                          ConstraintListView
PUT  /api/constraints/<id>/                     ConstraintDetailView
DEL  /api/constraints/<id>/                     ConstraintDetailView

â”€â”€ Timetable generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
POST /api/timetable/generate/                   GenerateView
POST /api/timetable/publish/                    PublishView
DEL  /api/timetable/drafts/                     DeleteDraftsView

â”€â”€ Timetable reading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/timetable/master/?term=<id>           MasterTimetableView
GET  /api/timetable/cohort/<id>/?term=<id>      CohortTimetableView
GET  /api/timetable/trainer/<id>/?term=<id>     TrainerTimetableView

â”€â”€ Conflicts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/conflicts/?term=<id>                  ConflictListView
POST /api/conflicts/<id>/resolve/               ResolveConflictView

â”€â”€ Exports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/export/master/?term=<id>&fmt=html     ExportMasterView
GET  /api/export/trainer/<id>/?term=<id>        ExportTrainerView

â”€â”€ Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GET  /api/dashboard/                            DashboardView
GET  /api/dashboard/trainer/                    TrainerDashboardView
"""

from __future__ import annotations

import traceback
from datetime import date

from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AuditLog, Cohort, Conflict, Constraint, CurriculumUnit, CurriculumUnitTrainer,
    Department, Institution, Period, Programme, ProgressRecord,
    Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)
from .scheduler import TimetableEngine


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Response helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ok(data, status_code=200) -> Response:
    return Response({"ok": True, "data": data}, status=status_code)


def err(message: str, detail: str = "", status_code=400) -> Response:
    payload = {"ok": False, "error": message}
    if detail:
        payload["detail"] = detail
    return Response(payload, status=status_code)


def _term_from_request(request) -> Term | None:
    tid = (
        request.query_params.get("term")
        or request.data.get("term")
        or request.data.get("term_id")
        or request.query_params.get("term_id")
    )
    if tid:
        return Term.objects.filter(id=tid).first()
    # Fall back to current term for the institution
    inst = _institution(request)
    if inst:
        return Term.objects.filter(institution=inst, is_current=True).first()
    return None


def _institution(request) -> Institution | None:
    # In a multi-tenant setup resolve from user profile or header.
    # For single-institution setups, just return the first one.
    return Institution.objects.filter().first()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Serialisation helpers  (plain dicts â€” no DRF serializers needed for reads)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _period_dict(p: Period) -> dict:
    return {
        "id":       str(p.id),
        "label":    p.label,
        "start":    str(p.start_time),
        "end":      str(p.end_time),
        "order":    p.order,
        "duration": p.duration_hours,
    }


def _trainer_dict(t: Trainer, include_load: bool = False) -> dict:
    d = {
        "id":              str(t.id),
        "staff_id":        t.staff_id,
        "full_name":       t.full_name,
        "short_name":      t.short_name,
        "department":      t.department.name,
        "employment_type": t.get_employment_type_display(),
        "max_periods_per_week": t.max_periods_per_week,
        "email":           t.email,
    }
    if include_load and hasattr(t, "_scheduled_periods"):
        d["scheduled_periods_this_term"] = t._scheduled_periods
    return d


def _unit_dict(u: CurriculumUnit) -> dict:
    return {
        "id":              str(u.id),
        "code":            u.code,
        "name":            u.name,
        "term_number":     u.term_number,
        "credit_hours":    u.credit_hours,
        "periods_per_week": u.periods_per_week,
        "unit_type":       u.get_unit_type_display(),
        "is_double":       u.periods_per_week >= 2,
        "is_outsourced":   u.is_outsourced,
    }


def _scheduled_unit_dict(su: ScheduledUnit) -> dict:
    return {
        "id":              str(su.id),
        "unit_code":       su.curriculum_unit.code,
        "unit_name":       su.curriculum_unit.name,
        "cohort":          su.cohort.name,
        "cohort_id":       str(su.cohort_id),
        "trainer":         su.trainer.short_name,
        "trainer_id":      str(su.trainer_id),
        "room":            su.room.code,
        "room_id":         str(su.room_id),
        "room_capacity":   su.room.capacity,
        "day":             su.day,
        "period_label":    su.period.label,
        "period_id":       str(su.period_id),
        "period_start":    str(su.period.start_time),
        "period_end":      str(su.period.end_time),
        "sequence":        su.sequence,
        "is_combined":     su.is_combined,
        "combined_key":    su.combined_key,
        "status":          su.status,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Institution / Setup views
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class InstitutionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        if not inst:
            return err("No institution configured", status_code=404)
        return ok({
            "id":                  str(inst.id),
            "name":                inst.name,
            "short_name":          inst.short_name,
            "timezone":            inst.timezone,
            "days_of_week":        inst.days_of_week,
            "max_periods_per_day": inst.max_periods_per_day,
            "allow_back_to_back":  inst.allow_back_to_back,
        })


class DepartmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        depts = Department.objects.filter(institution=inst, is_active=True).order_by("name")
        return ok([
            {"id": str(d.id), "code": d.code, "name": d.name, "hod": d.hod}
            for d in depts
        ])


class ProgrammeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        dept_id = request.query_params.get("department")
        qs = Programme.objects.filter(is_active=True).select_related("department")
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return ok([
            {
                "id":           str(p.id),
                "code":         p.code,
                "name":         p.name,
                "level":        p.get_level_display(),
                "department":   p.department.name,
                "total_terms":  p.total_terms,
                "sharing_group": p.sharing_group,
            }
            for p in qs.order_by("code")
        ])


class CurriculumView(APIView):
    """
    GET /api/curriculum/?programme=<id>&term_number=<n>
    Returns all CurriculumUnits for a programme (optionally filtered by term).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog_id = request.query_params.get("programme")
        term_num = request.query_params.get("term_number")

        if not prog_id:
            return err("programme query param required")

        qs = CurriculumUnit.objects.filter(
            programme_id=prog_id, is_active=True
        ).prefetch_related("qualified_trainers").order_by("term_number", "position")

        if term_num:
            qs = qs.filter(term_number=term_num)

        return ok([
            {
                **_unit_dict(u),
                "qualified_trainers": [
                    {"id": str(t.id), "name": t.short_name}
                    for t in u.qualified_trainers.all()
                ],
            }
            for u in qs
        ])


class PeriodListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        periods = Period.objects.filter(institution=inst).order_by("order")
        return ok([_period_dict(p) for p in periods])


class RoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        qs = Room.objects.filter(institution=inst, is_active=True).order_by("code")
        room_type = request.query_params.get("room_type")
        if room_type:
            qs = qs.filter(room_type=room_type)
        return ok([
            {
                "id":        str(r.id),
                "code":      r.code,
                "name":      r.name,
                "room_type": r.get_room_type_display(),
                "capacity":  r.capacity,
                "building":  r.building,
                "features":  r.features,
            }
            for r in qs
        ])


class TrainerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        dept_id = request.query_params.get("department")
        unit_id = request.query_params.get("unit")

        qs = Trainer.objects.filter(institution=inst, is_active=True).select_related("department")
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if unit_id:
            qs = qs.filter(qualified_units__id=unit_id)

        return ok([_trainer_dict(t) for t in qs.order_by("last_name")])


class TermListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        terms = Term.objects.filter(institution=inst).order_by("-start_date")
        return ok([
            {
                "id":             str(t.id),
                "name":           t.name,
                "start_date":     str(t.start_date),
                "end_date":       str(t.end_date),
                "teaching_weeks": t.teaching_weeks,
                "is_current":     t.is_current,
                "current_week":   t.week_number,
                "weeks_remaining": t.weeks_remaining,
            }
            for t in terms
        ])

    def post(self, request):
        """Create a new term."""
        inst = _institution(request)
        data = request.data
        try:
            term = Term.objects.create(
                institution=inst,
                name=data["name"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                teaching_weeks=int(data.get("teaching_weeks", 14)),
                is_current=bool(data.get("is_current", False)),
            )
            return ok({"id": str(term.id), "name": term.name}, status_code=201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), traceback.format_exc(), 500)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Cohorts & Progression
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CohortListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog_id = request.query_params.get("programme")
        qs = Cohort.objects.filter(is_active=True).select_related("programme")
        if prog_id:
            qs = qs.filter(programme_id=prog_id)
        return ok([
            {
                "id":           str(c.id),
                "name":         c.name,
                "programme":    c.programme.name,
                "programme_id": str(c.programme_id),
                "current_term": c.current_term,
                "student_count": c.student_count,
                "start_year":   c.start_year,
                "start_month":  c.start_month,
                "progress":     c.progress_summary,
            }
            for c in qs.order_by("-start_year", "programme")
        ])

    def post(self, request):
        """Create a cohort."""
        data = request.data
        try:
            programme = get_object_or_404(Programme, id=data["programme_id"])
            cohort = Cohort.objects.create(
                programme=programme,
                name=data["name"],
                start_year=int(data["start_year"]),
                start_month=int(data["start_month"]),
                current_term=int(data.get("current_term", 1)),
                student_count=int(data.get("student_count", 0)),
            )
            return ok({"id": str(cohort.id), "name": cohort.name}, 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), traceback.format_exc(), 500)


class CohortProgressView(APIView):
    """GET /api/cohorts/<id>/progress/?term=<term_id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        term   = _term_from_request(request)

        # All curriculum units for this programme
        all_units = CurriculumUnit.objects.filter(
            programme=cohort.programme, is_active=True
        ).order_by("term_number", "position")

        # Progress records
        records = {
            str(pr.curriculum_unit_id): pr
            for pr in ProgressRecord.objects.filter(cohort=cohort)
        }

        units_by_term: dict[int, list] = {}
        for u in all_units:
            pr = records.get(str(u.id))
            units_by_term.setdefault(u.term_number, []).append({
                "unit_id":    str(u.id),
                "code":       u.code,
                "name":       u.name,
                "credit_hours": u.credit_hours,
                "unit_type":  u.get_unit_type_display(),
                "status":     pr.status if pr else ProgressRecord.NOT_STARTED,
                "score":      float(pr.score) if pr and pr.score else None,
                "started_at":    str(pr.started_at) if pr and pr.started_at else None,
                "completed_at":  str(pr.completed_at) if pr and pr.completed_at else None,
                "is_current_term": u.term_number == cohort.current_term,
            })

        return ok({
            "cohort_id":    str(cohort.id),
            "cohort_name":  cohort.name,
            "programme":    cohort.programme.name,
            "current_term": cohort.current_term,
            "total_terms":  cohort.programme.total_terms,
            "summary":      cohort.progress_summary,
            "terms":        units_by_term,
        })


class AdvanceCohortView(APIView):
    """POST /api/cohorts/<id>/advance/ â€” move cohort to next term."""
    permission_classes = [IsAuthenticated]

    def post(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        if cohort.current_term >= cohort.programme.total_terms:
            return err("Cohort is already in the final term")
        old_term = cohort.current_term
        cohort.advance_term()
        AuditLog.objects.create(
            action="PROGRESS",
            performed_by=request.user,
            description=f"Cohort {cohort.name} advanced from term {old_term} to {cohort.current_term}",
        )
        return ok({"cohort": cohort.name, "from_term": old_term, "to_term": cohort.current_term})


class UpdateProgressView(APIView):
    """
    POST /api/cohorts/<id>/progress/update/
    Body: { "unit_id": "...", "status": "COMPLETED", "score": 72.5 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        unit_id = request.data.get("unit_id")
        new_status = request.data.get("status")
        score = request.data.get("score")

        if not unit_id or not new_status:
            return err("unit_id and status are required")
        if new_status not in {ProgressRecord.NOT_STARTED, ProgressRecord.IN_PROGRESS,
                               ProgressRecord.COMPLETED, ProgressRecord.DEFERRED}:
            return err(f"Invalid status: {new_status}")

        unit = get_object_or_404(CurriculumUnit, id=unit_id, programme=cohort.programme)
        term = _term_from_request(request)

        pr, created = ProgressRecord.objects.get_or_create(
            cohort=cohort,
            curriculum_unit=unit,
            defaults={"term": term},
        )
        pr.status = new_status
        if score is not None:
            pr.score = score
        if new_status == ProgressRecord.IN_PROGRESS and not pr.started_at:
            pr.started_at = date.today()
        if new_status == ProgressRecord.COMPLETED and not pr.completed_at:
            pr.completed_at = date.today()
        pr.save()

        return ok({
            "unit":   unit.code,
            "cohort": cohort.name,
            "status": pr.status,
            "score":  float(pr.score) if pr.score else None,
        })


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Constraints
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ConstraintListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unit_id    = request.query_params.get("unit")
        cohort_id  = request.query_params.get("cohort")
        trainer_id = request.query_params.get("trainer")

        qs = Constraint.objects.filter(is_active=True)
        if unit_id:
            qs = qs.filter(curriculum_unit_id=unit_id)
        if cohort_id:
            qs = qs.filter(cohort_id=cohort_id)
        if trainer_id:
            qs = qs.filter(trainer_id=trainer_id)

        return ok([
            {
                "id":          str(c.id),
                "scope":       c.scope,
                "rule":        c.rule,
                "is_hard":     c.is_hard,
                "parameters":  c.parameters,
                "notes":       c.notes,
                "unit":        c.curriculum_unit.code if c.curriculum_unit_id else None,
                "cohort":      c.cohort.name if c.cohort_id else None,
                "trainer":     c.trainer.short_name if c.trainer_id else None,
                "room":        c.room.code if c.room_id else None,
            }
            for c in qs.order_by("-is_hard", "scope")
        ])

    def post(self, request):
        data = request.data
        try:
            c = Constraint.objects.create(
                scope=data["scope"],
                rule=data["rule"],
                is_hard=bool(data.get("is_hard", True)),
                curriculum_unit_id=data.get("unit_id"),
                cohort_id=data.get("cohort_id"),
                trainer_id=data.get("trainer_id"),
                room_id=data.get("room_id"),
                parameters=data.get("parameters", {}),
                notes=data.get("notes", ""),
            )
            return ok({"id": str(c.id)}, 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


class ConstraintDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, constraint_id):
        c    = get_object_or_404(Constraint, id=constraint_id)
        data = request.data
        c.is_hard    = bool(data.get("is_hard", c.is_hard))
        c.parameters = data.get("parameters", c.parameters)
        c.notes      = data.get("notes", c.notes)
        c.is_active  = bool(data.get("is_active", c.is_active))
        c.save()
        return ok({"id": str(c.id), "updated": True})

    def delete(self, request, constraint_id):
        c = get_object_or_404(Constraint, id=constraint_id)
        c.is_active = False
        c.save(update_fields=["is_active"])
        return ok({"deleted": True})


class TrainerAvailabilityView(APIView):
    """
    GET  /api/trainers/<id>/availability/?term=<id>
    POST /api/trainers/<id>/availability/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, trainer_id):
        trainer = get_object_or_404(Trainer, id=trainer_id)
        term    = _term_from_request(request)
        rules   = TrainerAvailability.objects.filter(
            trainer=trainer, term=term
        ).select_related("period").order_by("day", "period__order")
        return ok([
            {
                "id":           str(r.id),
                "day":          r.day,
                "period":       _period_dict(r.period) if r.period_id else None,
                "is_available": r.is_available,
                "reason":       r.reason,
                "notes":        r.notes,
            }
            for r in rules
        ])

    def post(self, request, trainer_id):
        trainer = get_object_or_404(Trainer, id=trainer_id)
        term    = _term_from_request(request)
        data    = request.data
        rule, created = TrainerAvailability.objects.update_or_create(
            trainer=trainer,
            term=term,
            day=data["day"],
            period_id=data.get("period_id"),
            defaults={
                "is_available": bool(data.get("is_available", False)),
                "reason":       data.get("reason", "UNAVAILABLE"),
                "notes":        data.get("notes", ""),
            },
        )
        return ok({"id": str(rule.id), "created": created}, 201 if created else 200)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Timetable generation
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class GenerateView(APIView):
    """
    POST /api/timetable/generate/
    Body: { "term_id": "..." }

    Clears DRAFT entries, runs the engine, returns summary.
    Does NOT publish.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term = _term_from_request(request)
        if not term:
            return err("Provide term_id or set a current term")

        try:
            engine = TimetableEngine(term)
            result = engine.run(delete_existing_drafts=True)
        except Exception as e:
            return err("Generation failed", traceback.format_exc(), 500)

        AuditLog.objects.create(
            action="GENERATE",
            performed_by=request.user,
            term=term,
            description=f"Timetable generated for {term.name}",
            payload=result.summary(),
        )
        return ok(result.summary(), 202)


class PublishView(APIView):
    """
    POST /api/timetable/publish/
    Body: { "term_id": "...", "force": false }

    Promotes DRAFT â†’ PUBLISHED in a single atomic UPDATE.
    Deduplicates drafts first to avoid DB constraint violations.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term  = _term_from_request(request)
        force = bool(request.data.get("force", False))

        if not term:
            return err("Provide term_id or set a current term")

        # Check unresolved HIGH conflicts
        pending_high = Conflict.objects.filter(
            term=term, severity="HIGH", resolution_status="PENDING"
        ).count()
        if pending_high and not force:
            return Response(
                {
                    "ok": False,
                    "error": f"{pending_high} unresolved HIGH conflicts. "
                             "Resolve them or pass force=true.",
                    "pending_conflicts": pending_high,
                },
                status=409,
            )

        draft_count = ScheduledUnit.objects.filter(term=term, status="DRAFT").count()
        if not draft_count:
            return err("No drafts found. Run /generate first.")

        try:
            with transaction.atomic():
                # Step 1: remove duplicate drafts (same cohort/trainer/room Ã— day Ã— period)
                published_count = self._dedup_and_publish(term)
        except Exception as e:
            return err("Publish failed", traceback.format_exc(), 500)

        AuditLog.objects.create(
            action="PUBLISH",
            performed_by=request.user,
            term=term,
            description=f"Published {published_count} entries for {term.name}",
            payload={"published": published_count, "force": force},
        )
        return ok({"published": published_count, "term": term.name})

    def _dedup_and_publish(self, term: Term) -> int:
        # Delete old PUBLISHED rows (they will be replaced)
        ScheduledUnit.objects.filter(term=term, status="PUBLISHED").delete()

                # Dedup NON-combined drafts only: keep lowest pk per (cohort/trainer/room x day x period)
        # Combined sessions legitimately share trainer/room slots across cohorts - skip them
        for field in ("cohort_id", "trainer_id", "room_id"):
            rows = list(
                ScheduledUnit.objects.filter(term=term, status="DRAFT", is_combined=False)
                .values("id", field, "day", "period_id")
                .order_by("created_at")
            )
            seen: set[tuple] = set()
            to_delete = []
            for row in rows:
                key = (row[field], row["day"], row["period_id"])
                if key in seen:
                    to_delete.append(row["id"])
                else:
                    seen.add(key)
            if to_delete:
                ScheduledUnit.objects.filter(id__in=to_delete).delete()

        # Promote
        now = timezone.now()
        return ScheduledUnit.objects.filter(term=term, status="DRAFT").update(
            status="PUBLISHED", published_at=now
        )


class DeleteDraftsView(APIView):
    """DELETE /api/timetable/drafts/?term=<id>"""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        term = _term_from_request(request)
        if not term:
            return err("Provide term_id")
        count, _ = ScheduledUnit.objects.filter(term=term, status="DRAFT").delete()
        AuditLog.objects.create(
            action="DELETE",
            performed_by=request.user,
            term=term,
            description=f"Deleted {count} draft entries for {term.name}",
        )
        return ok({"deleted": count})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Timetable reading
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MasterTimetableView(APIView):
    """
    GET /api/timetable/master/?term=<id>&status=PUBLISHED

    Returns a grid:
    {
      "grid": {
        "MON": {
          "<period_id>": [ { ...entry }, ... ]
        }
      }
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term   = _term_from_request(request)
        target = request.query_params.get("status", "PUBLISHED")

        if not term:
            return err("No current term. Provide term_id.", status_code=404)

        inst    = term.institution
        days    = list(inst.days_of_week)
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))

        entries = (
            ScheduledUnit.objects.filter(term=term, status=target)
            .select_related(
                "curriculum_unit", "cohort", "trainer", "room", "period"
            )
            .order_by("day", "period__order", "cohort")
        )

        grid: dict = {day: {str(p.id): [] for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid and pid in grid[su.day]:
                grid[su.day][pid].append(_scheduled_unit_dict(su))

        return ok({
            "term":          term.name,
            "term_id":       str(term.id),
            "status":        target,
            "days":          days,
            "periods":       [_period_dict(p) for p in periods],
            "teaching_weeks": term.teaching_weeks,
            "grid":          grid,
            # Stats
            "total_entries": sum(
                len(v) for day in grid.values() for v in day.values()
            ),
        })


class CohortTimetableView(APIView):
    """GET /api/timetable/cohort/<id>/?term=<id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, cohort_id):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        term   = _term_from_request(request)
        if not term:
            return err("No current term", status_code=404)

        inst    = term.institution
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))
        days    = list(inst.days_of_week)

        entries = (
            ScheduledUnit.objects.filter(term=term, cohort=cohort, status="PUBLISHED")
            .select_related("curriculum_unit", "trainer", "room", "period")
            .order_by("day", "period__order")
        )

        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = _scheduled_unit_dict(su)

        return ok({
            "cohort":         cohort.name,
            "cohort_id":      str(cohort.id),
            "programme":      cohort.programme.name,
            "current_term":   cohort.current_term,
            "student_count":  cohort.student_count,
            "term":           term.name,
            "term_id":        str(term.id),
            "days":           days,
            "periods":        [_period_dict(p) for p in periods],
            "grid":           grid,
            "classes_per_week": entries.count(),
            "progress":       cohort.progress_summary,
        })


class TrainerTimetableView(APIView):
    """GET /api/timetable/trainer/<id>/?term=<id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, trainer_id):
        trainer = get_object_or_404(Trainer, id=trainer_id)
        term    = _term_from_request(request)
        if not term:
            return err("No current term", status_code=404)

        inst    = term.institution
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))
        days    = list(inst.days_of_week)

        entries = (
            ScheduledUnit.objects.filter(term=term, trainer=trainer, status="PUBLISHED")
            .select_related("curriculum_unit", "cohort", "room", "period")
            .order_by("day", "period__order")
        )

        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        total_periods = 0
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = _scheduled_unit_dict(su)
                total_periods += 1

        return ok({
            "trainer":         trainer.full_name,
            "trainer_id":      str(trainer.id),
            "staff_id":        trainer.staff_id,
            "department":      trainer.department.name,
            "employment_type": trainer.get_employment_type_display(),
            "max_periods_per_week": trainer.max_periods_per_week,
            "term":            term.name,
            "term_id":         str(term.id),
            "days":            days,
            "periods":         [_period_dict(p) for p in periods],
            "grid":            grid,
            "periods_this_week": total_periods,
            "capacity_remaining": max(0, trainer.max_periods_per_week - total_periods),
        })


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Manual entry edits
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ScheduledUnitDetailView(APIView):
    """
    GET  /api/timetable/entry/<id>/
    PUT  /api/timetable/entry/<id>/   â€” reassign trainer/room/day/period
    DEL  /api/timetable/entry/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, entry_id):
        su = get_object_or_404(
            ScheduledUnit.objects.select_related(
                "curriculum_unit", "cohort", "trainer", "room", "period"
            ),
            id=entry_id,
        )
        return ok(_scheduled_unit_dict(su))

    def put(self, request, entry_id):
        su   = get_object_or_404(ScheduledUnit, id=entry_id)
        data = request.data
        old  = _scheduled_unit_dict(su)

        if "trainer_id" in data:
            su.trainer = get_object_or_404(Trainer, id=data["trainer_id"])
        if "room_id" in data:
            su.room = get_object_or_404(Room, id=data["room_id"])
        if "day" in data:
            su.day = data["day"]
        if "period_id" in data:
            su.period = get_object_or_404(Period, id=data["period_id"])
        if "notes" in data:
            su.notes = data["notes"]

        try:
            su.save()
        except Exception as e:
            return err(str(e), status_code=400)

        AuditLog.objects.create(
            action="EDIT",
            performed_by=request.user,
            term=su.term,
            description=f"Edited entry {su.id}",
            payload={"before": old, "after": _scheduled_unit_dict(su)},
        )
        return ok(_scheduled_unit_dict(su))

    def delete(self, request, entry_id):
        su = get_object_or_404(ScheduledUnit, id=entry_id)
        su.delete()
        return ok({"deleted": True})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Conflicts
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ConflictListView(APIView):
    """GET /api/conflicts/?term=<id>&status=PENDING"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term      = _term_from_request(request)
        res_status = request.query_params.get("status", "PENDING")

        qs = Conflict.objects.filter(term=term, resolution_status=res_status).order_by(
            "-severity", "-created_at"
        )
        return ok([
            {
                "id":           str(c.id),
                "type":         c.get_conflict_type_display(),
                "severity":     c.severity,
                "description":  c.description,
                "unit":         c.curriculum_unit.code if c.curriculum_unit_id else None,
                "cohort":       c.cohort.name if c.cohort_id else None,
                "trainer":      c.trainer.short_name if c.trainer_id else None,
                "room":         c.room.code if c.room_id else None,
                "status":       c.resolution_status,
                "created_at":   c.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for c in qs
        ])


class ResolveConflictView(APIView):
    """POST /api/conflicts/<id>/resolve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conflict_id):
        conflict = get_object_or_404(Conflict, id=conflict_id)
        note     = request.data.get("note", "")
        method   = request.data.get("method", "RESOLVED")

        conflict.resolve(note=note, resolved_by=request.user, method=method)
        AuditLog.objects.create(
            action="RESOLVE",
            performed_by=request.user,
            term=conflict.term,
            description=f"Conflict {conflict.id} resolved: {note}",
        )
        return ok({"resolved": True, "conflict_id": str(conflict.id)})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Exports
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _html_table(title, subtitle, days, periods, grid, caption="") -> str:
    head_cells = "".join(f"<th>{p.label}<br><small>{p.start_time:%H:%M}â€“{p.end_time:%H:%M}</small></th>" for p in periods)
    rows = ""
    for day in days:
        cells = ""
        for p in periods:
            pid   = str(p.id)
            items = grid[day].get(pid)
            if items:
                if isinstance(items, list):
                    content = "".join(
                        f"<div class='entry'>"
                        f"<strong>{e['unit_code']}</strong> {e['unit_name']}<br>"
                        f"<span>{e['trainer']}</span><br>"
                        f"<em>{e['room']} â€” {e['cohort']}</em>"
                        f"</div>"
                        for e in items
                    )
                else:
                    e = items
                    content = (
                        f"<div class='entry'>"
                        f"<strong>{e['unit_code']}</strong> {e['unit_name']}<br>"
                        f"<span>{e['trainer']}</span><br>"
                        f"<em>{e['room']}</em>"
                        f"</div>"
                    )
                cells += f"<td>{content}</td>"
            else:
                cells += "<td class='empty'>â€”</td>"
        rows += f"<tr><td class='day'>{day}</td>{cells}</tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 24px; color: #1a1a2e; }}
  h1   {{ margin: 0 0 4px; font-size: 1.5rem; }}
  h2   {{ margin: 0 0 16px; font-size: 1rem; color: #555; font-weight: 400; }}
  p.caption {{ color:#777; font-size:0.85rem; margin-bottom:16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th   {{ background: #16213e; color: #fff; padding: 10px 8px; text-align: center; }}
  td   {{ border: 1px solid #dde; padding: 8px; vertical-align: top; min-width: 120px; }}
  td.day {{ font-weight: bold; background: #f0f4ff; text-align: center; }}
  td.empty {{ color: #bbb; text-align: center; }}
  .entry {{ margin-bottom: 6px; padding: 6px; background: #eef2ff; border-radius: 4px; }}
  .entry strong {{ color: #16213e; display: block; }}
  .entry span {{ color: #0f3460; font-size: 0.8rem; }}
  .entry em {{ color: #555; font-size: 0.78rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<h2>{subtitle}</h2>
{f'<p class="caption">{caption}</p>' if caption else ''}
<table>
  <thead><tr><th>Day</th>{head_cells}</tr></thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""


class ExportMasterView(APIView):
    """GET /api/export/master/?term=<id>&fmt=html"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term = _term_from_request(request)
        if not term:
            return err("No term found", status_code=404)

        inst    = term.institution
        days    = list(inst.days_of_week)
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))

        entries = ScheduledUnit.objects.filter(term=term, status="PUBLISHED").select_related(
            "curriculum_unit", "cohort", "trainer", "room", "period"
        )

        grid: dict = {day: {str(p.id): [] for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid and pid in grid[su.day]:
                grid[su.day][pid].append(_scheduled_unit_dict(su))

        html = _html_table(
            title=f"Master Timetable â€” {term.name}",
            subtitle=inst.name,
            days=days,
            periods=periods,
            grid=grid,
            caption=f"Weekly recurring template Â· {term.teaching_weeks} teaching weeks",
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="master_{term.name}.html"'
        return resp


class ExportTrainerView(APIView):
    """GET /api/export/trainer/<id>/?term=<id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, trainer_id):
        trainer = get_object_or_404(Trainer, id=trainer_id)
        term    = _term_from_request(request)
        if not term:
            return err("No term found", status_code=404)

        inst    = term.institution
        days    = list(inst.days_of_week)
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))

        entries = ScheduledUnit.objects.filter(
            term=term, trainer=trainer, status="PUBLISHED"
        ).select_related("curriculum_unit", "cohort", "room", "period")

        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = _scheduled_unit_dict(su)

        html = _html_table(
            title=f"Timetable â€” {trainer.full_name}",
            subtitle=f"{trainer.department.name} Â· {term.name}",
            days=days,
            periods=periods,
            grid=grid,
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="trainer_{trainer.staff_id}.html"'
        return resp


class ExportCohortView(APIView):
    """GET /api/export/cohort/<id>/?term=<id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, cohort_id):
        cohort  = get_object_or_404(Cohort, id=cohort_id)
        term    = _term_from_request(request)
        if not term:
            return err("No term found", status_code=404)

        inst    = term.institution
        days    = list(inst.days_of_week)
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))

        entries = ScheduledUnit.objects.filter(
            term=term, cohort=cohort, status="PUBLISHED"
        ).select_related("curriculum_unit", "trainer", "room", "period")

        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = _scheduled_unit_dict(su)

        html = _html_table(
            title=f"Timetable â€” {cohort.name}",
            subtitle=f"{cohort.programme.name} Â· {term.name}",
            days=days,
            periods=periods,
            grid=grid,
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="cohort_{cohort.name}.html"'
        return resp


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Dashboard
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        term = _term_from_request(request)

        # Base counts â€” all in a few queries
        stats = {
            "institution":   inst.name if inst else "",
            "trainers":      Trainer.objects.filter(institution=inst, is_active=True).count(),
            "rooms":         Room.objects.filter(institution=inst, is_active=True).count(),
            "cohorts":       Cohort.objects.filter(
                                 programme__department__institution=inst, is_active=True
                             ).count(),
            "programmes":    Programme.objects.filter(
                                 department__institution=inst, is_active=True
                             ).count(),
        }

        if term:
            base_qs = ScheduledUnit.objects.filter(term=term)
            pub_count   = base_qs.filter(status="PUBLISHED").count()
            draft_count = base_qs.filter(status="DRAFT").count()

            # Conflict counts
            conflict_counts = dict(
                Conflict.objects.filter(term=term)
                .values_list("resolution_status")
                .annotate(n=Count("id"))
                .order_by()
            )

            # Trainer workload (ONE query via annotation â€” no N+1)
            trainer_load = list(
                Trainer.objects.filter(institution=inst, is_active=True)
                .annotate(
                    periods_scheduled=Count(
                        "scheduled_units",
                        filter=Q(
                            scheduled_units__term=term,
                            scheduled_units__status="PUBLISHED",
                        ),
                    )
                )
                .select_related("department")
                .order_by("-periods_scheduled")[:10]
            )

            stats["term"] = {
                "id":             str(term.id),
                "name":           term.name,
                "teaching_weeks": term.teaching_weeks,
                "current_week":   term.week_number,
                "weeks_remaining": term.weeks_remaining,
                "published":      pub_count,
                "drafts":         draft_count,
                "conflicts":      {
                    "pending":  conflict_counts.get("PENDING", 0),
                    "resolved": conflict_counts.get("RESOLVED", 0),
                    "total":    sum(conflict_counts.values()),
                },
            }
            stats["trainer_workload"] = [
                {
                    "id":                str(t.id),
                    "name":              t.short_name,
                    "department":        t.department.name,
                    "periods_scheduled": t.periods_scheduled,
                    "max_periods":       t.max_periods_per_week,
                    "load_pct":          round(
                        t.periods_scheduled / t.max_periods_per_week * 100, 1
                    ) if t.max_periods_per_week else 0,
                }
                for t in trainer_load
            ]

            # Recent audit entries
            stats["recent_activity"] = [
                {
                    "action":    a.get_action_display(),
                    "by":        a.performed_by.username if a.performed_by else "System",
                    "at":        a.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "note":      a.description[:80],
                }
                for a in AuditLog.objects.filter(term=term).order_by("-timestamp")[:8]
            ]
        else:
            stats["term"] = None

        return ok(stats)


class TrainerDashboardView(APIView):
    """Personal dashboard for logged-in trainer."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "trainer_profile"):
            return err("User is not linked to a trainer profile", status_code=403)

        trainer = request.user.trainer_profile
        term    = _term_from_request(request)
        if not term:
            return err("No current term", status_code=404)

        inst    = term.institution
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))
        days    = list(inst.days_of_week)

        entries = list(
            ScheduledUnit.objects.filter(term=term, trainer=trainer, status="PUBLISHED")
            .select_related("curriculum_unit", "cohort", "room", "period")
            .order_by("day", "period__order")
        )

        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = {
                    "unit_code": su.curriculum_unit.code,
                    "unit_name": su.curriculum_unit.name,
                    "cohort":    su.cohort.name,
                    "room":      su.room.code,
                }

        return ok({
            "trainer": {
                "id":              str(trainer.id),
                "full_name":       trainer.full_name,
                "staff_id":        trainer.staff_id,
                "department":      trainer.department.name,
                "employment_type": trainer.get_employment_type_display(),
            },
            "term":              term.name,
            "teaching_weeks":    term.teaching_weeks,
            "current_week":      term.week_number,
            "classes_this_week": len(entries),
            "periods_scheduled": len(entries),
            "max_periods":       trainer.max_periods_per_week,
            "capacity_remaining": max(0, trainer.max_periods_per_week - len(entries)),
            "days":              days,
            "periods":           [_period_dict(p) for p in periods],
            "grid":              grid,
            "qualified_units":   CurriculumUnit.objects.filter(
                qualified_trainers=trainer, is_active=True
            ).count(),
        })

# -------------------------------------------------------------------------
# Auth
# -------------------------------------------------------------------------

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "ok": True,
            "data": {
                "id":         str(user.id),
                "username":   user.username,
                "first_name": user.first_name,
                "last_name":  user.last_name,
                "email":      user.email,
                "role":       "ADMIN" if user.is_staff else "TRAINER",
            }
        })


# -----------------------------------------------------------------------------
# Curriculum Unit Detail  +  Trainer assignment
# -----------------------------------------------------------------------------

class CurriculumUnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        return ok({
            **_unit_dict(u),
            'qualified_trainers': [
                {'id': str(ut.trainer.id), 'name': ut.trainer.short_name, 'trainer_type': ut.trainer_type, 'label': ut.label}
                for ut in u.unit_trainers.select_related('trainer').all()
            ],
        })

    def put(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        data = request.data
        for field in ('code','name','term_number','periods_per_week','credit_hours','unit_type','notes','is_outsourced'):
            if field in data:
                setattr(u, field, data[field])
        u.save()
        return ok(_unit_dict(u))


class CurriculumUnitTrainersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        return ok([{'id': str(ut.trainer.id), 'name': ut.trainer.short_name, 'trainer_type': ut.trainer_type, 'label': ut.label} for ut in u.unit_trainers.select_related('trainer').all()])

    def post(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        trainer_id = request.data.get('trainer_id')
        ttype = request.data.get('trainer_type', 'INTERNAL')
        label = request.data.get('label', '')
        if not trainer_id:
            return err('trainer_id required')
        trainer = get_object_or_404(Trainer, id=trainer_id)
        ut, created = CurriculumUnitTrainer.objects.get_or_create(curriculum_unit=u, trainer=trainer, defaults={'trainer_type': ttype, 'label': label})
        if not created:
            ut.trainer_type = ttype
            ut.label = label
            ut.save()
        return ok({'id': str(trainer.id), 'name': trainer.short_name, 'trainer_type': ut.trainer_type, 'label': ut.label})

    def delete(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        trainer_id = request.data.get('trainer_id')
        if not trainer_id:
            return err('trainer_id required')
        CurriculumUnitTrainer.objects.filter(curriculum_unit=u, trainer_id=trainer_id).delete()
        return ok({'deleted': True})






