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
)
from .scheduler import TimetableEngine


# ─────────────────────────────────────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────────────────────────────────────

def ok(data, status_code: int = 200) -> Response:
    return Response({"ok": True, "data": data}, status=status_code)


def err(message: str, detail: str = "", status_code: int = 400) -> Response:
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
    inst = _institution(request)
    if inst:
        return Term.objects.filter(institution=inst, is_current=True).first()
    return None


def _institution(request) -> Institution | None:
    return Institution.objects.first()


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _term_dict(t: Term) -> dict:
    return {
        "id":               str(t.id),
        "name":             t.name,
        "start_date":       str(t.start_date),
        "end_date":         str(t.end_date),
        "teaching_weeks":   t.teaching_weeks,
        "is_current":       t.is_current,
        "current_week":     t.week_number,
        "weeks_remaining":  t.weeks_remaining,
        "college_year":     t.college_year,
        "college_semester": t.college_semester,
    }


def _period_dict(p: Period) -> dict:
    import datetime as dt
    def _dur(s, e):
        try:
            if isinstance(s, str): s = dt.time.fromisoformat(s[:5])
            if isinstance(e, str): e = dt.time.fromisoformat(e[:5])
            today = dt.date.today()
            return (
                dt.datetime.combine(today, e) - dt.datetime.combine(today, s)
            ).seconds / 3600
        except Exception:
            return 0
    return {
        "id":       str(p.id),
        "label":    p.label,
        "start":    str(p.start_time),
        "end":      str(p.end_time),
        "order":    p.order,
        "is_break": p.is_break,
        "duration": _dur(p.start_time, p.end_time),
    }


def _trainer_dict(t: Trainer, include_load: bool = False) -> dict:
    d = {
        "id":                   str(t.id),
        "staff_id":             t.staff_id,
        "title":                t.title,
        "first_name":           t.first_name,
        "last_name":            t.last_name,
        "full_name":            t.full_name,
        "short_name":           t.short_name,
        "email":                t.email,
        "phone":                getattr(t, "phone", "") or "",
        "department":           t.department.name,
        "department_id":        str(t.department_id),
        "institution_id":       str(t.institution_id),
        "employment_type":      t.get_employment_type_display(),
        "employment_type_code": t.employment_type,
        "max_periods_per_week": t.max_periods_per_week,
        "available_days":       t.available_days or [],
        "is_active":            t.is_active,
    }
    if include_load and hasattr(t, "_scheduled_periods"):
        d["scheduled_periods_this_term"] = t._scheduled_periods
    return d


def _unit_dict(u: CurriculumUnit) -> dict:
    return {
        "id":               str(u.id),
        "code":             u.code,
        "name":             u.name,
        "term_number":      u.term_number,
        "credit_hours":     u.credit_hours,
        "periods_per_week": u.periods_per_week,
        "unit_type":        u.get_unit_type_display(),
        "is_double":        u.periods_per_week >= 2,
        "is_outsourced":    u.is_outsourced,
    }


def _scheduled_unit_dict(su: ScheduledUnit) -> dict:
    return {
        "id":              str(su.id),
        "term":            str(su.term_id),
        "curriculum_unit": str(su.curriculum_unit_id),
        "cohort":          str(su.cohort_id) if su.cohort_id else None,
        "trainer":         str(su.trainer_id) if su.trainer_id else None,
        "room":            str(su.room_id) if su.room_id else None,
        "unit_code":       su.curriculum_unit.code,
        "unit_name":       su.curriculum_unit.name,
        "cohort_name":     su.cohort.name if su.cohort else None,
        "trainer_name":    su.trainer.short_name if su.trainer else None,
        "trainer_full":    f"{su.trainer.title} {su.trainer.last_name}" if su.trainer else None,
        "room_code":       su.room.code if su.room else None,
        "room_capacity":   su.room.capacity if su.room else None,
        "day":             su.day,
        "period":          str(su.period_id),
        "period_label":    su.period.label if su.period else None,
        "period_start":    str(su.period.start_time) if su.period else None,
        "period_end":      str(su.period.end_time) if su.period else None,
        "sequence":        su.sequence,
        "is_combined":     su.is_combined,
        "combined_key":    su.combined_key or "",
        "status":          su.status,
        "published_at":    su.published_at.isoformat() if getattr(su, "published_at", None) else None,
        "notes":           su.notes or "",
    }


def _enrolment_dict(e: CohortEnrolment) -> dict:
    return {
        "id":               str(e.id),
        "cohort_id":        str(e.cohort_id),
        "cohort_name":      e.cohort.name,
        "programme":        e.cohort.programme.name,
        "programme_code":   e.cohort.programme.code,
        "programme_id":     str(e.cohort.programme_id),
        "college_term_id":  str(e.college_term_id),
        "college_term_name": e.college_term.name,
        "programme_term":   e.programme_term,
        "status":           e.status,
        "is_graduating":    e.is_graduating,
        "student_count":    e.cohort.student_count,
        "notes":            e.notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Institution / Setup views
# ─────────────────────────────────────────────────────────────────────────────

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
        inst  = _institution(request)
        depts = Department.objects.filter(institution=inst, is_active=True).order_by("name")
        return ok([
            {
                "id": str(d.id), "code": d.code, "name": d.name,
                "hod": d.hod, "institution_id": str(d.institution_id),
                "is_active": d.is_active,
            }
            for d in depts
        ])

    def post(self, request):
        inst = _institution(request)
        data = request.data
        try:
            d = Department.objects.create(
                institution=inst,
                code=data["code"],
                name=data["name"],
                hod=data.get("hod", ""),
            )
            return ok(
                {"id": str(d.id), "code": d.code, "name": d.name,
                 "hod": d.hod, "institution_id": str(d.institution_id),
                 "is_active": d.is_active},
                201,
            )
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


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

    def post(self, request):
        data = request.data
        try:
            dept = get_object_or_404(Department, id=data["department_id"])
            p = Programme.objects.create(
                department=dept,
                code=data["code"],
                name=data["name"],
                level=data.get("level", "CERT"),
                total_terms=int(data.get("total_terms", 4)),
                sharing_group=data.get("sharing_group", ""),
            )
            return ok({"id": str(p.id), "code": p.code, "name": p.name}, 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


class CurriculumView(APIView):
    """GET /api/curriculum/?programme=<id>&term_number=<n>"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog_id  = request.query_params.get("programme")
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
        inst    = _institution(request)
        periods = Period.objects.filter(institution=inst).order_by("order")
        return ok([_period_dict(p) for p in periods])

    def post(self, request):
        inst = _institution(request)
        data = request.data
        try:
            period = Period.objects.create(
                institution=inst,
                label=data["label"],
                start_time=data.get("start") or data.get("start_time"),
                end_time=data.get("end") or data.get("end_time"),
                order=Period.objects.filter(institution=inst).count() + 1,
                is_break=bool(data.get("is_break", False)),
            )
            return ok(_period_dict(period), 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), traceback.format_exc(), 500)


class RoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst      = _institution(request)
        qs        = Room.objects.filter(institution=inst, is_active=True).order_by("code")
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

    def post(self, request):
        inst = _institution(request)
        data = request.data
        try:
            r = Room.objects.create(
                institution=inst,
                code=data["code"],
                name=data.get("name", data["code"]),
                room_type=data.get("room_type", "CLASSROOM"),
                capacity=int(data.get("capacity", 30)),
                building=data.get("building", ""),
                features=data.get("features", []),
            )
            return ok({"id": str(r.id), "code": r.code, "name": r.name}, 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


class TrainerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst      = _institution(request)
        dept_id   = request.query_params.get("department")
        unit_id   = request.query_params.get("unit")
        qs        = Trainer.objects.filter(institution=inst, is_active=True).select_related("department")
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if unit_id:
            qs = qs.filter(qualified_units__id=unit_id)
        return ok([_trainer_dict(t) for t in qs.order_by("last_name")])

    def post(self, request):
        import time
        inst = _institution(request)
        data = request.data
        try:
            dept     = get_object_or_404(Department, id=data["department_id"])
            staff_id = data.get("staff_id", "").strip() or f"TRN-{int(time.time()*1000) % 1000000}"
            t = Trainer.objects.create(
                institution=inst,
                department=dept,
                staff_id=staff_id,
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                title=data.get("title", ""),
                employment_type=data.get("employment_type", "FT"),
                max_periods_per_week=int(data.get("max_periods_per_week", 20)),
                available_days=data.get("available_days", []),
            )
            return ok(_trainer_dict(t), 201)
        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), status_code=500)


class TermListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst  = _institution(request)
        terms = Term.objects.filter(institution=inst).order_by("-start_date")
        return ok([_term_dict(t) for t in terms])

    def post(self, request):
        inst = _institution(request)
        data = request.data
        college_year     = data.get("college_year")
        college_semester = data.get("college_semester")

        if college_year and college_semester:
            try:
                college_year     = int(college_year)
                college_semester = int(college_semester)
                assert college_semester in (1, 2, 3)
            except (ValueError, AssertionError):
                return err("college_year must be an integer; college_semester must be 1, 2 or 3")
            start_date, end_date = CollegeCalendar.semester_dates(college_year, college_semester)
            sem_labels = {1: "Sem 1", 2: "Sem 2", 3: "Sem 3"}
            name = data.get("name", f"{inst.short_name} – {sem_labels[college_semester]} {college_year}")
        else:
            try:
                name             = data["name"]
                start_date       = data["start_date"]
                end_date         = data["end_date"]
                college_year     = data.get("college_year")
                college_semester = data.get("college_semester")
            except KeyError as e:
                return err(f"Missing field: {e}")

        try:
            term = Term.objects.create(
                institution      = inst,
                name             = name,
                start_date       = start_date,
                end_date         = end_date,
                teaching_weeks   = int(data.get("teaching_weeks", 14)),
                is_current       = bool(data.get("is_current", False)),
                college_year     = college_year,
                college_semester = college_semester,
            )
            return ok(_term_dict(term), 201)
        except Exception as e:
            return err(str(e), traceback.format_exc(), 500)


# ─────────────────────────────────────────────────────────────────────────────
# CollegeCalendarView
# ─────────────────────────────────────────────────────────────────────────────

class CollegeCalendarView(APIView):
    """GET /api/calendar/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        today_year, today_sem = CollegeCalendar.current_semester()
        sems_window = self._semester_window(today_year, today_sem, back=2, forward=2)

        term_map: dict[tuple[int, int], Term] = {}
        for t in Term.objects.filter(institution=inst):
            if t.college_year and t.college_semester:
                term_map[(t.college_year, t.college_semester)] = t

        cohorts = list(
            Cohort.objects.filter(
                programme__department__institution=inst, is_active=True
            ).select_related("programme")
        )

        semesters = []
        for year, sem in sems_window:
            is_current = (year == today_year and sem == today_sem)
            is_past    = (year * 3 + sem) < (today_year * 3 + today_sem)
            term       = term_map.get((year, sem))

            cohort_entries = []
            for c in cohorts:
                prog_term = CollegeCalendar.cohort_term_at(
                    c.start_year, c.start_month, year, sem, c.programme.total_terms
                )
                if prog_term is None:
                    continue
                cohort_entries.append({
                    "cohort_id":           str(c.id),
                    "cohort_name":         c.name,
                    "programme":           c.programme.name,
                    "programme_code":      c.programme.code,
                    "programme_term":      prog_term,
                    "current_stored_term": c.current_term,
                    "is_new_intake":       prog_term == 1,
                    "is_graduating":       prog_term == c.programme.total_terms,
                    "student_count":       c.student_count,
                })

            can_advance = False
            if is_current and term:
                next_year, next_sem = CollegeCalendar.next_semester(year, sem)
                has_next_term   = (next_year, next_sem) in term_map
                published_count = ScheduledUnit.objects.filter(
                    term=term, status="PUBLISHED"
                ).count()
                can_advance = has_next_term and published_count > 0

            semesters.append({
                "year":         year,
                "semester":     sem,
                "label":        CollegeCalendar.semester_label(year, sem),
                "is_current":   is_current,
                "is_past":      is_past,
                "term":         _term_dict(term) if term else None,
                "cohorts":      cohort_entries,
                "cohort_count": len(cohort_entries),
                "can_advance":  can_advance,
            })

        current_entry = next((s for s in semesters if s["is_current"]), None)
        return ok({
            "today":     {"year": today_year, "semester": today_sem},
            "current":   current_entry,
            "semesters": semesters,
        })

    def _semester_window(self, year, sem, back, forward):
        cur_idx = year * 3 + (sem - 1)
        result  = []
        for idx in range(cur_idx - back, cur_idx + forward + 1):
            y, s = divmod(idx, 3)
            result.append((y, s + 1))
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Cohorts & Progression
# ─────────────────────────────────────────────────────────────────────────────

class CohortListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prog_id = request.query_params.get("programme")
        qs      = Cohort.objects.filter(is_active=True).select_related("programme")
        if prog_id:
            qs = qs.filter(programme_id=prog_id)

        # Pre-fetch the latest enrolment per cohort (any term, any status)
        # so completed cohorts whose enrolment is in a past term are still found.
        enrolment_map: dict[str, CohortEnrolment] = {}
        for e in (
            CohortEnrolment.objects
            .filter(cohort__in=qs)
            .select_related("cohort")
            .order_by("cohort_id", "-created_at")
            .distinct("cohort_id")
        ):
            enrolment_map[str(e.cohort_id)] = e

        result = []
        for c in qs.order_by("-start_year", "programme"):
            enrolment = enrolment_map.get(str(c.id))
            result.append({
                "id":                    str(c.id),
                "name":                  c.name,
                "programme":             c.programme.name,
                "programme_id":          str(c.programme_id),
                "current_term":          c.current_term,
                "computed_current_term": c.computed_current_term,
                "term_is_synced":        c.term_is_synced,
                "total_terms":           c.programme.total_terms,
                "student_count":         c.student_count,
                "start_year":            c.start_year,
                "start_month":           c.start_month,
                "is_active":             c.is_active,
                "progress":              c.progress_summary,
                "enrolment_id":     str(enrolment.id) if enrolment else None,
                "enrolment_status": enrolment.status if enrolment else None,
                "programme_term":   enrolment.programme_term if enrolment else c.current_term,
                "is_enrolled":      enrolment is not None and enrolment.status == CohortEnrolment.ACTIVE,
            })
        return ok(result)

    def post(self, request):
        data = request.data
        try:
            programme = get_object_or_404(Programme, id=data["programme_id"])
            cohort    = Cohort.objects.create(
                programme=programme,
                name=data["name"],
                start_year=int(data["start_year"]),
                start_month=int(data["start_month"]),
                current_term=int(data.get("current_term", 1)),
                student_count=int(data.get("student_count", 0)),
            )
            # Auto-enrol in the current college term so current_term
            # is immediately synced via the post_save signal.
            inst         = _institution(request)
            current_term = Term.objects.filter(
                institution=inst, is_current=True
            ).first()
            if current_term:
                CohortEnrolment.objects.create(
                    cohort=cohort,
                    college_term=current_term,
                    programme_term=cohort.computed_current_term,
                    status=CohortEnrolment.ACTIVE,
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
        cohort    = get_object_or_404(Cohort, id=cohort_id)
        term      = _term_from_request(request)
        enrolment = cohort.active_enrolment(college_term=term) if term else cohort.active_enrolment()

        all_units = CurriculumUnit.objects.filter(
            programme=cohort.programme, is_active=True
        ).order_by("term_number", "position")

        records = {
            str(pr.curriculum_unit_id): pr
            for pr in ProgressRecord.objects.filter(cohort=cohort)
        }

        units_by_term: dict[int, list] = {}
        for u in all_units:
            pr = records.get(str(u.id))
            units_by_term.setdefault(u.term_number, []).append({
                "unit_id":         str(u.id),
                "code":            u.code,
                "name":            u.name,
                "credit_hours":    u.credit_hours,
                "unit_type":       u.get_unit_type_display(),
                "status":          pr.status if pr else ProgressRecord.NOT_STARTED,
                "score":           float(pr.score) if pr and pr.score else None,
                "started_at":      str(pr.started_at) if pr and pr.started_at else None,
                "completed_at":    str(pr.completed_at) if pr and pr.completed_at else None,
                "is_current_term": u.term_number == cohort.current_term,
            })

        ct       = cohort.current_term
        covered  = {tn: u for tn, u in units_by_term.items() if tn < ct}
        current  = {tn: u for tn, u in units_by_term.items() if tn == ct}
        upcoming = {tn: u for tn, u in units_by_term.items() if tn == ct + 1}

        return ok({
            "cohort_id":             str(cohort.id),
            "cohort_name":           cohort.name,
            "programme":             cohort.programme.name,
            "current_term":          cohort.current_term,
            "computed_current_term": cohort.computed_current_term,
            "term_is_synced":        cohort.term_is_synced,
            "total_terms":           cohort.programme.total_terms,
            "enrolment":             _enrolment_dict(enrolment) if enrolment else None,
            "summary":               cohort.progress_summary,
            "terms":                 units_by_term,
            "covered":               covered,
            "current":               current,
            "upcoming":              upcoming,
        })


class AdvanceCohortView(APIView):
    """POST /api/cohorts/<id>/advance/ — move a single cohort to its next term."""
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
    """POST /api/cohorts/<id>/progress/update/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, cohort_id):
        cohort     = get_object_or_404(Cohort, id=cohort_id)
        unit_id    = request.data.get("unit_id")
        new_status = request.data.get("status")
        score      = request.data.get("score")

        if not unit_id or not new_status:
            return err("unit_id and status are required")
        if new_status not in {
            ProgressRecord.NOT_STARTED, ProgressRecord.IN_PROGRESS,
            ProgressRecord.COMPLETED, ProgressRecord.DEFERRED,
        }:
            return err(f"Invalid status: {new_status}")

        unit      = get_object_or_404(CurriculumUnit, id=unit_id, programme=cohort.programme)
        term      = _term_from_request(request)
        enrolment = cohort.active_enrolment(college_term=term) if term else cohort.active_enrolment()

        pr, _ = ProgressRecord.objects.get_or_create(
            cohort=cohort,
            curriculum_unit=unit,
            defaults={"term": term, "enrolment": enrolment},
        )
        pr.status = new_status
        if score is not None:
            pr.score = score
        if new_status == ProgressRecord.IN_PROGRESS and not pr.started_at:
            pr.started_at = date.today()
        if new_status == ProgressRecord.COMPLETED and not pr.completed_at:
            pr.completed_at = date.today()
        if pr.enrolment is None and enrolment:
            pr.enrolment = enrolment
        pr.save()

        return ok({
            "unit":   unit.code,
            "cohort": cohort.name,
            "status": pr.status,
            "score":  float(pr.score) if pr.score else None,
        })


# ─────────────────────────────────────────────────────────────────────────────
# CohortEnrolment CRUD
# ─────────────────────────────────────────────────────────────────────────────

class CohortEnrolmentListView(APIView):
    """
    GET  /api/enrolments/?term=<id>&status=ACTIVE&cohort=<id>
    POST /api/enrolments/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term      = _term_from_request(request)
        status    = request.query_params.get("status", "")
        cohort_id = request.query_params.get("cohort")

        qs = CohortEnrolment.objects.select_related(
            "cohort__programme", "college_term"
        )
        if term:
            qs = qs.filter(college_term=term)
        if status:
            qs = qs.filter(status=status)
        if cohort_id:
            qs = qs.filter(cohort_id=cohort_id)

        return ok([_enrolment_dict(e) for e in qs.order_by("cohort__name")])

    def post(self, request):
        data = request.data
        try:
            cohort = get_object_or_404(Cohort, id=data["cohort_id"])
            term   = get_object_or_404(Term,   id=data["term_id"])

            enrolment, created = CohortEnrolment.objects.get_or_create(
                cohort=cohort,
                college_term=term,
                defaults={
                    "programme_term": int(data["programme_term"]),
                    "status":         data.get("status", CohortEnrolment.ACTIVE),
                    "notes":          data.get("notes", ""),
                },
            )
            if not created:
                return err(
                    f"{cohort.name} already has an enrolment for {term.name}",
                    status_code=409,
                )

            AuditLog.objects.create(
                action="PROGRESS",
                performed_by=request.user,
                term=term,
                description=(
                    f"Enrolment created: {cohort.name} → T{enrolment.programme_term} "
                    f"in {term.name}"
                ),
            )
            return ok(_enrolment_dict(enrolment), 201)

        except KeyError as e:
            return err(f"Missing field: {e}")
        except Exception as e:
            return err(str(e), traceback.format_exc(), 500)


class CohortEnrolmentDetailView(APIView):
    """
    GET    /api/enrolments/<id>/
    PUT    /api/enrolments/<id>/
    DELETE /api/enrolments/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        e = get_object_or_404(
            CohortEnrolment.objects.select_related("cohort__programme", "college_term"),
            id=pk,
        )
        return ok(_enrolment_dict(e))

    def put(self, request, pk):
        e    = get_object_or_404(CohortEnrolment, id=pk)
        data = request.data
        old_status = e.status

        for field in ("status", "notes", "programme_term"):
            if field in data:
                setattr(e, field, data[field])
        e.save()

        AuditLog.objects.create(
            action="PROGRESS",
            performed_by=request.user,
            term=e.college_term,
            description=(
                f"Enrolment updated: {e.cohort.name} in {e.college_term.name} — "
                f"status {old_status} → {e.status}"
            ),
        )
        return ok(_enrolment_dict(e))

    def delete(self, request, pk):
        e    = get_object_or_404(CohortEnrolment, id=pk)
        name = f"{e.cohort.name} in {e.college_term.name}"
        e.delete()
        return ok({"deleted": True, "enrolment": name})


# ─────────────────────────────────────────────────────────────────────────────
# AdvanceAllCohortsView
# ─────────────────────────────────────────────────────────────────────────────

class AdvanceAllCohortsView(APIView):
    """
    POST /api/term/advance-all/
    GET  /api/term/advance-all/?term=<id>   (preview alias)

    Two-phase flow
    --------------
    phase=preview  → returns what will happen (no writes)
    phase=confirm  → executes the move atomically

    POST body (preview):
      { "phase": "preview", "term_id": "<uuid>" }

    POST body (confirm):
      {
        "phase":     "confirm",
        "term_id":   "<uuid>",
        "overrides": { "<unit_id>": false }
      }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self._preview(request)

    def post(self, request):
        phase = request.data.get("phase", "preview")
        if phase == "preview":
            return self._preview(request)
        if phase == "confirm":
            return self._confirm(request)
        return err(f"Unknown phase '{phase}'. Use 'preview' or 'confirm'.")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve(self, request) -> tuple[Term | None, Term | None]:
        term = _term_from_request(request)
        if not term:
            return None, None
        next_term = self._next_term(term)
        return term, next_term

    def _next_term(self, term: Term) -> Term | None:
        if not (term.college_year and term.college_semester):
            return None
        next_year, next_sem = CollegeCalendar.next_semester(
            term.college_year, term.college_semester
        )
        return Term.objects.filter(
            institution=term.institution,
            college_year=next_year,
            college_semester=next_sem,
        ).first()

    def _active_enrolments(self, term: Term) -> list[CohortEnrolment]:
        return list(
            CohortEnrolment.objects.filter(
                college_term=term,
                status=CohortEnrolment.ACTIVE,
            ).select_related("cohort__programme").order_by("cohort__name")
        )

    def _new_intakes(self, term: Term, next_term: Term | None) -> list[Cohort]:
        """Cohorts with no enrolment in current or next term — new intakes."""
        if not next_term:
            return []
        already_enrolled_ids = set(
            CohortEnrolment.objects.filter(
                college_term__in=[term, next_term]
            ).values_list("cohort_id", flat=True)
        )
        return list(
            Cohort.objects.filter(is_active=True)
            .exclude(id__in=already_enrolled_ids)
            .select_related("programme")
            .order_by("name")
        )

    # ── Preview ───────────────────────────────────────────────────────────────

    def _preview(self, request) -> Response:
        term, next_term = self._resolve(request)
        if not term:
            return err("Provide term_id or set a current term", status_code=404)

        active_enrolments = self._active_enrolments(term)
        new_intakes       = self._new_intakes(term, next_term)

        advancing  = []
        graduating = []

        for enrolment in active_enrolments:
            units = enrolment.unit_preview()
            entry = {
                "enrolment_id":      str(enrolment.id),
                "cohort_id":         str(enrolment.cohort_id),
                "cohort_name":       enrolment.cohort.name,
                "programme":         enrolment.cohort.programme.name,
                "programme_code":    enrolment.cohort.programme.code,
                "from_term":         enrolment.programme_term,
                "to_term":           enrolment.programme_term + 1,
                "is_graduating":     enrolment.is_graduating,
                "student_count":     enrolment.cohort.student_count,
                "units_to_complete": units,
            }
            advancing.append(entry)
            if enrolment.is_graduating:
                graduating.append({
                    "cohort_id":   str(enrolment.cohort_id),
                    "cohort_name": enrolment.cohort.name,
                    "programme":   enrolment.cohort.programme.name,
                })

        return ok({
            "current_term":            _term_dict(term),
            "next_term":               _term_dict(next_term) if next_term else None,
            "next_term_exists":        next_term is not None,
            "advancing_cohorts":       advancing,
            "new_intakes": [
                {
                    "cohort_id":    str(c.id),
                    "cohort_name":  c.name,
                    "programme":    c.programme.name,
                    "student_count": c.student_count,
                }
                for c in new_intakes
            ],
            "graduating_cohorts":       graduating,
            "total_cohorts_advancing":  len(advancing),
            "total_new_intakes":        len(new_intakes),
        })

    # ── Confirm ───────────────────────────────────────────────────────────────

    def _confirm(self, request) -> Response:
        term, next_term = self._resolve(request)
        if not term:
            return err("Provide term_id or set a current term", status_code=404)

        overrides: dict      = request.data.get("overrides", {})
        cohorts_advanced     = 0
        units_completed      = 0
        skipped_units        = 0
        log_lines: list[str] = []

        try:
            with transaction.atomic():
                active_enrolments = self._active_enrolments(term)

                for enrolment in active_enrolments:
                    cohort    = enrolment.cohort
                    units     = enrolment.unit_preview()
                    completed = skipped = 0

                    # 1. Mark units complete in ProgressRecord
                    for u in units:
                        uid = u["unit_id"]
                        if overrides.get(uid) is False:
                            skipped_units += 1
                            skipped       += 1
                            continue
                        if not u["mark_complete"]:
                            skipped_units += 1
                            skipped       += 1
                            continue

                        pr, _ = ProgressRecord.objects.get_or_create(
                            cohort=cohort,
                            curriculum_unit_id=uid,
                            defaults={"term": term, "enrolment": enrolment},
                        )
                        if pr.enrolment_id is None:
                            pr.enrolment = enrolment
                        pr.status       = ProgressRecord.COMPLETED
                        pr.completed_at = date.today()
                        if not pr.started_at:
                            pr.started_at = date.today()
                        pr.save(update_fields=[
                            "status", "completed_at", "started_at",
                            "enrolment", "updated_at",
                        ])
                        completed       += 1
                        units_completed += 1

                    # 2. Close current enrolment
                    enrolment.status = CohortEnrolment.COMPLETED
                    enrolment.save(update_fields=["status", "updated_at"])

                    # 3. Create next enrolment (or mark graduated)
                    if next_term:
                        next_prog_term = enrolment.programme_term + 1
                        if next_prog_term <= cohort.programme.total_terms:
                            CohortEnrolment.objects.create(
                                cohort=cohort,
                                college_term=next_term,
                                programme_term=next_prog_term,
                                status=CohortEnrolment.ACTIVE,
                            )
                            cohorts_advanced += 1
                            log_lines.append(
                                f"{cohort.name}: T{enrolment.programme_term} → "
                                f"T{next_prog_term} "
                                f"({completed} completed, {skipped} skipped)"
                            )
                        else:
                            CohortEnrolment.objects.create(
                                cohort=cohort,
                                college_term=next_term,
                                programme_term=enrolment.programme_term,
                                status=CohortEnrolment.COMPLETED,
                                notes="Graduated",
                            )
                            log_lines.append(
                                f"{cohort.name}: GRADUATED after T{enrolment.programme_term}"
                            )

                # 4. Enrol new intakes for next term at programme_term = 1
                if next_term:
                    for cohort in self._new_intakes(term, next_term):
                        CohortEnrolment.objects.get_or_create(
                            cohort=cohort,
                            college_term=next_term,
                            defaults={
                                "programme_term": 1,
                                "status": CohortEnrolment.ACTIVE,
                            },
                        )
                        log_lines.append(
                            f"{cohort.name}: NEW INTAKE → T1 in {next_term.name}"
                        )

                # 5. Activate the next term
                if next_term:
                    Term.objects.filter(
                        institution=term.institution, is_current=True
                    ).exclude(pk=next_term.pk).update(is_current=False)
                    next_term.is_current = True
                    next_term.save(update_fields=["is_current", "updated_at"])

        except Exception:
            return err("Advance failed", traceback.format_exc(), 500)

        AuditLog.objects.create(
            action="PROGRESS",
            performed_by=request.user,
            term=term,
            description=(
                f"Semester advance: {cohorts_advanced} cohorts advanced, "
                f"{units_completed} units completed, {skipped_units} skipped."
            ),
            payload={
                "cohorts_advanced":    cohorts_advanced,
                "units_completed":     units_completed,
                "skipped_units":       skipped_units,
                "next_term_id":        str(next_term.id) if next_term else None,
                "next_term_activated": next_term is not None,
                "detail":              log_lines,
            },
        )

        return ok({
            "cohorts_advanced":    cohorts_advanced,
            "units_completed":     units_completed,
            "skipped_units":       skipped_units,
            "new_term_is_current": next_term is not None,
            "next_term":           _term_dict(next_term) if next_term else None,
            "detail":              log_lines,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Constraints
# ─────────────────────────────────────────────────────────────────────────────

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
        from .serializers import ConstraintSerializer
        return ok(ConstraintSerializer(qs.order_by("-is_hard", "scope"), many=True).data)

    def post(self, request):
        from .serializers import ConstraintSerializer
        ser = ConstraintSerializer(data=request.data)
        if ser.is_valid():
            c = ser.save()
            return ok({"id": str(c.id)}, 201)
        return err(str(ser.errors), status_code=400)


class ConstraintDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, constraint_id):
        c    = get_object_or_404(Constraint, id=constraint_id)
        data = request.data
        c.scope          = data.get("scope",      c.scope)
        c.rule           = data.get("rule",       c.rule)
        c.is_hard        = bool(data.get("is_hard",   c.is_hard))
        c.parameters     = data.get("parameters", c.parameters)
        c.notes          = data.get("notes",      c.notes)
        c.is_active      = bool(data.get("is_active", c.is_active))
        c.cohort_id          = data.get("cohort",          c.cohort_id)
        c.curriculum_unit_id = data.get("curriculum_unit", c.curriculum_unit_id)
        c.save()
        return ok({"id": str(c.id), "updated": True})

    def delete(self, request, constraint_id):
        c = get_object_or_404(Constraint, id=constraint_id)
        c.delete()
        return Response(status=204)


# ─────────────────────────────────────────────────────────────────────────────
# Trainer Availability
# ─────────────────────────────────────────────────────────────────────────────

class TrainerAvailabilityView(APIView):
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


# ─────────────────────────────────────────────────────────────────────────────
# Pre-generation Validation
# ─────────────────────────────────────────────────────────────────────────────

class ValidateView(APIView):
    """GET /api/timetable/validate/?term=<uuid>"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term = _term_from_request(request)
        if not term:
            return err("Provide term_id or set a current term", status_code=404)

        inst     = term.institution
        blocking = []
        warnings = []

        cohorts = list(
            Cohort.objects.filter(
                programme__department__institution=inst, is_active=True
            ).select_related("programme")
        )
        all_trainers = list(
            Trainer.objects.filter(institution=inst, is_active=True).select_related("department")
        )
        rooms   = list(Room.objects.filter(institution=inst, is_active=True))
        periods = list(Period.objects.filter(institution=inst, is_break=False))
        days    = list(inst.days_of_week)
        total_slots = len(days) * len(periods)

        units_per_trainer: dict[str, list] = defaultdict(list)
        cohorts_checked = units_checked = 0

        for cohort in cohorts:
            # Use enrolment-based programme_term if available
            enrolment  = cohort.active_enrolment(college_term=term)
            prog_term  = enrolment.programme_term if enrolment else cohort.current_term
            units      = list(
                CurriculumUnit.objects.filter(
                    programme=cohort.programme,
                    term_number=prog_term,
                    is_active=True,
                ).prefetch_related("qualified_trainers")
            )
            cohorts_checked += 1
            units_checked   += len(units)

            sessions_needed = sum(u.periods_per_week for u in units)
            if sessions_needed > total_slots:
                warnings.append({
                    "type":      "SLOT_SHORTAGE",
                    "cohort":    cohort.name,
                    "needed":    sessions_needed,
                    "available": total_slots,
                    "message":   f"Needs {sessions_needed} sessions but only {total_slots} slots available",
                })

            for unit in units:
                outsourced = getattr(unit, "is_outsourced", False)
                if not outsourced and cohort.student_count > 0:
                    if not any(r.capacity >= cohort.student_count for r in rooms):
                        warnings.append({
                            "type":              "NO_SUITABLE_ROOM",
                            "cohort":            cohort.name,
                            "unit_code":         unit.code,
                            "unit_name":         unit.name,
                            "students":          cohort.student_count,
                            "max_room_capacity": max((r.capacity for r in rooms), default=0),
                            "message":           f"No room with capacity ≥ {cohort.student_count} students",
                        })
                if outsourced:
                    continue
                qualified = list(unit.qualified_trainers.filter(is_active=True))
                if not qualified:
                    blocking.append({
                        "type":      "NO_TRAINER",
                        "cohort":    cohort.name,
                        "unit_code": unit.code,
                        "unit_name": unit.name,
                        "message":   "No qualified trainer assigned — unit cannot be scheduled",
                    })
                    continue
                if len(qualified) == 1:
                    units_per_trainer[str(qualified[0].id)].append((cohort.name, unit.code))

        for t in all_trainers:
            tid    = str(t.id)
            needed = sum(
                u.periods_per_week
                for u in CurriculumUnit.objects.filter(
                    qualified_trainers=t,
                    programme__department__institution=inst,
                    is_active=True,
                    is_outsourced=False,
                ).filter(
                    programme__cohorts__current_term__isnull=False
                ).distinct()
            )
            if needed > t.max_periods_per_week:
                warnings.append({
                    "type":            "TRAINER_OVERLOAD",
                    "trainer_name":    f"{t.first_name} {t.last_name}",
                    "trainer_id":      tid,
                    "sessions_needed": needed,
                    "max_periods":     t.max_periods_per_week,
                    "message":         (
                        f"{t.first_name} {t.last_name} qualified for {needed} sessions "
                        f"but max is {t.max_periods_per_week}/week"
                    ),
                })
            sole_units = units_per_trainer.get(tid, [])
            if len(sole_units) >= 3:
                warnings.append({
                    "type":         "SINGLE_TRAINER_BOTTLENECK",
                    "trainer_name": f"{t.first_name} {t.last_name}",
                    "trainer_id":   tid,
                    "sole_units":   sole_units,
                    "units_count":  len(sole_units),
                    "message":      (
                        f"{t.first_name} {t.last_name} is the only trainer "
                        f"for {len(sole_units)} units"
                    ),
                })

        return ok({
            "blocking":     blocking,
            "warnings":     warnings,
            "can_generate": len(blocking) == 0,
            "summary": {
                "blocking_count":  len(blocking),
                "warning_count":   len(warnings),
                "cohorts_checked": cohorts_checked,
                "units_checked":   units_checked,
            },
        })


# ─────────────────────────────────────────────────────────────────────────────
# Timetable generation
# ─────────────────────────────────────────────────────────────────────────────

class GenerateView(APIView):
    """POST /api/timetable/generate/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term = _term_from_request(request)
        if not term:
            return err("Provide term_id or set a current term")
        try:
            Conflict.objects.filter(term=term).delete()
            engine = TimetableEngine(term)
            result = engine.run(delete_existing_drafts=True)
        except Exception:
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
    """POST /api/timetable/publish/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        term  = _term_from_request(request)
        force = bool(request.data.get("force", False))
        if not term:
            return err("Provide term_id or set a current term")
        pending_high = Conflict.objects.filter(
            term=term, severity="HIGH", resolution_status="PENDING"
        ).count()
        if pending_high and not force:
            return Response(
                {
                    "ok": False,
                    "error": f"{pending_high} unresolved HIGH conflicts. Resolve them or pass force=true.",
                    "pending_conflicts": pending_high,
                },
                status=409,
            )
        draft_count = ScheduledUnit.objects.filter(term=term, status="DRAFT").count()
        if not draft_count:
            return err("No drafts found. Run /generate first.")
        try:
            with transaction.atomic():
                published_count = self._dedup_and_publish(term)
        except Exception:
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
        ScheduledUnit.objects.filter(term=term, status="PUBLISHED").delete()
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


# ─────────────────────────────────────────────────────────────────────────────
# Timetable reading
# ─────────────────────────────────────────────────────────────────────────────

class MasterTimetableView(APIView):
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
            .select_related("curriculum_unit", "cohort", "trainer", "room", "period")
            .order_by("day", "period__order", "cohort")
        )
        grid: dict = {day: {str(p.id): [] for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid and pid in grid[su.day]:
                grid[su.day][pid].append(_scheduled_unit_dict(su))
        return ok({
            "term":           term.name,
            "term_id":        str(term.id),
            "status":         target,
            "days":           days,
            "periods":        [_period_dict(p) for p in periods],
            "teaching_weeks": term.teaching_weeks,
            "grid":           grid,
            "total_entries":  sum(len(v) for day in grid.values() for v in day.values()),
        })


class CohortTimetableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cohort_id):
        cohort  = get_object_or_404(Cohort, id=cohort_id)
        term    = _term_from_request(request)
        if not term:
            return err("No current term", status_code=404)
        inst    = term.institution
        periods = list(Period.objects.filter(institution=inst, is_break=False).order_by("order"))
        days    = list(inst.days_of_week)
        entries = (
            ScheduledUnit.objects.filter(term=term, cohort=cohort, status__in=["DRAFT", "PUBLISHED"])
            .select_related("curriculum_unit", "trainer", "room", "period")
            .order_by("day", "period__order")
        )
        grid: dict = {day: {str(p.id): None for p in periods} for day in days}
        for su in entries:
            pid = str(su.period_id)
            if su.day in grid:
                grid[su.day][pid] = _scheduled_unit_dict(su)
        return ok({
            "cohort":          cohort.name,
            "cohort_id":       str(cohort.id),
            "programme":       cohort.programme.name,
            "current_term":    cohort.current_term,
            "student_count":   cohort.student_count,
            "term":            term.name,
            "term_id":         str(term.id),
            "days":            days,
            "periods":         [_period_dict(p) for p in periods],
            "grid":            grid,
            "classes_per_week": entries.count(),
            "progress":        cohort.progress_summary,
        })


class TrainerTimetableView(APIView):
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
            ScheduledUnit.objects.filter(term=term, trainer=trainer, status__in=["DRAFT", "PUBLISHED"])
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
            "trainer":              trainer.full_name,
            "trainer_id":           str(trainer.id),
            "staff_id":             trainer.staff_id,
            "department":           trainer.department.name,
            "employment_type":      trainer.get_employment_type_display(),
            "max_periods_per_week": trainer.max_periods_per_week,
            "term":                 term.name,
            "term_id":              str(term.id),
            "days":                 days,
            "periods":              [_period_dict(p) for p in periods],
            "grid":                 grid,
            "periods_this_week":    total_periods,
            "capacity_remaining":   max(0, trainer.max_periods_per_week - total_periods),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Manual entry edits
# ─────────────────────────────────────────────────────────────────────────────

class ScheduledUnitDetailView(APIView):
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


# ─────────────────────────────────────────────────────────────────────────────
# Conflicts
# ─────────────────────────────────────────────────────────────────────────────

class ConflictListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term       = _term_from_request(request)
        res_status = request.query_params.get("status", "")
        qs         = Conflict.objects.filter(term=term)
        if res_status:
            qs = qs.filter(resolution_status=res_status)
        qs = qs.select_related("cohort", "trainer", "room", "curriculum_unit").order_by(
            "-severity", "-created_at"
        )
        return ok([
            {
                "id":                str(c.id),
                "term":              str(c.term_id),
                "conflict_type":     c.conflict_type,
                "severity":          c.severity,
                "description":       c.description,
                "cohort":            str(c.cohort_id) if c.cohort_id else None,
                "cohort_name":       c.cohort.name if c.cohort_id else None,
                "trainer":           str(c.trainer_id) if c.trainer_id else None,
                "trainer_name":      c.trainer.short_name if c.trainer_id else None,
                "room":              str(c.room_id) if c.room_id else None,
                "room_code":         c.room.code if c.room_id else None,
                "curriculum_unit":   str(c.curriculum_unit_id) if c.curriculum_unit_id else None,
                "unit_code":         c.curriculum_unit.code if c.curriculum_unit_id else None,
                "resolution_status": c.resolution_status,
                "resolved_by":       None,
                "resolved_at":       None,
                "resolution_note":   c.resolution_note if hasattr(c, "resolution_note") else "",
                "involved_entries":  [],
                "created_at":        c.created_at.isoformat(),
            }
            for c in qs
        ])


class ResolveConflictView(APIView):
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


# ─────────────────────────────────────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────────────────────────────────────

def _html_table(title, subtitle, days, periods, grid, caption="") -> str:
    head_cells = "".join(
        f"<th>{p.label}<br><small>{p.start_time:%H:%M}–{p.end_time:%H:%M}</small></th>"
        for p in periods
    )
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
                        f"<span>{e.get('trainer_name','')}</span><br>"
                        f"<em>{e.get('room_code','')} · {e.get('cohort_name','')}</em>"
                        f"</div>"
                        for e in items
                    )
                else:
                    e = items
                    content = (
                        f"<div class='entry'>"
                        f"<strong>{e['unit_code']}</strong> {e['unit_name']}<br>"
                        f"<span>{e.get('trainer_name','')}</span><br>"
                        f"<em>{e.get('room_code','')}</em>"
                        f"</div>"
                    )
                cells += f"<td>{content}</td>"
            else:
                cells += "<td class='empty'>–</td>"
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
            title=f"Master Timetable – {term.name}",
            subtitle=inst.name,
            days=days,
            periods=periods,
            grid=grid,
            caption=f"Weekly recurring template · {term.teaching_weeks} teaching weeks",
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="master_{term.name}.html"'
        return resp


class ExportTrainerView(APIView):
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
            title=f"Timetable – {trainer.full_name}",
            subtitle=f"{trainer.department.name} · {term.name}",
            days=days,
            periods=periods,
            grid=grid,
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="trainer_{trainer.staff_id}.html"'
        return resp


class ExportCohortView(APIView):
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
            title=f"Timetable – {cohort.name}",
            subtitle=f"{cohort.programme.name} · {term.name}",
            days=days,
            periods=periods,
            grid=grid,
        )
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'inline; filename="cohort_{cohort.name}.html"'
        return resp


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        inst = _institution(request)
        term = _term_from_request(request)

        stats = {
            "institution": inst.name if inst else "",
            "trainers":    Trainer.objects.filter(institution=inst, is_active=True).count(),
            "rooms":       Room.objects.filter(institution=inst, is_active=True).count(),
            "cohorts":     Cohort.objects.filter(
                               programme__department__institution=inst, is_active=True
                           ).count(),
            "programmes":  Programme.objects.filter(
                               department__institution=inst, is_active=True
                           ).count(),
        }

        if term:
            base_qs     = ScheduledUnit.objects.filter(term=term)
            pub_count   = base_qs.filter(status="PUBLISHED").count()
            draft_count = base_qs.filter(status="DRAFT").count()

            conflict_counts = dict(
                Conflict.objects.filter(term=term)
                .values_list("resolution_status")
                .annotate(n=Count("id"))
                .order_by()
            )

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
                "id":              str(term.id),
                "name":            term.name,
                "teaching_weeks":  term.teaching_weeks,
                "current_week":    term.week_number,
                "weeks_remaining": term.weeks_remaining,
                "published":       pub_count,
                "drafts":          draft_count,
                "conflicts": {
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
            stats["recent_activity"] = [
                {
                    "action": a.get_action_display(),
                    "by":     a.performed_by.username if a.performed_by else "System",
                    "at":     a.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "note":   a.description[:80],
                }
                for a in AuditLog.objects.filter(term=term).order_by("-timestamp")[:8]
            ]
        else:
            stats["term"] = None

        return ok(stats)


class TrainerDashboardView(APIView):
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
            ScheduledUnit.objects.filter(
                term=term, trainer=trainer, status__in=["DRAFT", "PUBLISHED"]
            ).select_related("curriculum_unit", "cohort", "room", "period")
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
            "term":               term.name,
            "teaching_weeks":     term.teaching_weeks,
            "current_week":       term.week_number,
            "classes_this_week":  len(entries),
            "periods_scheduled":  len(entries),
            "max_periods":        trainer.max_periods_per_week,
            "capacity_remaining": max(0, trainer.max_periods_per_week - len(entries)),
            "days":               days,
            "periods":            [_period_dict(p) for p in periods],
            "grid":               grid,
            "qualified_units":    CurriculumUnit.objects.filter(
                qualified_trainers=trainer, is_active=True
            ).count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Curriculum Unit detail + trainer assignment
# ─────────────────────────────────────────────────────────────────────────────

class CurriculumUnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        return ok({
            **_unit_dict(u),
            "qualified_trainers": [
                {
                    "id":           str(ut.trainer.id),
                    "name":         ut.trainer.short_name,
                    "trainer_type": ut.trainer_type,
                    "label":        ut.label,
                }
                for ut in u.unit_trainers.select_related("trainer").all()
            ],
        })

    def put(self, request, unit_id):
        u    = get_object_or_404(CurriculumUnit, id=unit_id)
        data = request.data
        for field in ("code", "name", "term_number", "periods_per_week",
                      "credit_hours", "unit_type", "notes", "is_outsourced"):
            if field in data:
                setattr(u, field, data[field])
        u.save()
        return ok(_unit_dict(u))


class CurriculumUnitTrainersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        u = get_object_or_404(CurriculumUnit, id=unit_id)
        return ok([
            {
                "id":           str(ut.trainer.id),
                "name":         ut.trainer.short_name,
                "trainer_type": ut.trainer_type,
                "label":        ut.label,
            }
            for ut in u.unit_trainers.select_related("trainer").all()
        ])

    def post(self, request, unit_id):
        u          = get_object_or_404(CurriculumUnit, id=unit_id)
        trainer_id = request.data.get("trainer_id")
        ttype      = request.data.get("trainer_type", "INTERNAL")
        label      = request.data.get("label", "")
        if not trainer_id:
            return err("trainer_id required")
        trainer = get_object_or_404(Trainer, id=trainer_id)
        ut, created = CurriculumUnitTrainer.objects.get_or_create(
            curriculum_unit=u, trainer=trainer,
            defaults={"trainer_type": ttype, "label": label},
        )
        if not created:
            ut.trainer_type = ttype
            ut.label        = label
            ut.save()
        return ok({
            "id":           str(trainer.id),
            "name":         trainer.short_name,
            "trainer_type": ut.trainer_type,
            "label":        ut.label,
        })

    def delete(self, request, unit_id):
        u          = get_object_or_404(CurriculumUnit, id=unit_id)
        trainer_id = request.data.get("trainer_id")
        if not trainer_id:
            return err("trainer_id required")
        CurriculumUnitTrainer.objects.filter(
            curriculum_unit=u, trainer_id=trainer_id
        ).delete()
        return ok({"deleted": True})


# ─────────────────────────────────────────────────────────────────────────────
# Detail views (GET / PUT / DELETE by ID)
# ─────────────────────────────────────────────────────────────────────────────

class DepartmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        d = get_object_or_404(Department, id=pk)
        return ok({"id": str(d.id), "code": d.code, "name": d.name,
                   "hod": d.hod, "institution_id": str(d.institution_id), "is_active": d.is_active})

    def put(self, request, pk):
        d    = get_object_or_404(Department, id=pk)
        data = request.data
        for field in ("code", "name", "hod", "is_active"):
            if field in data:
                setattr(d, field, data[field])
        d.save()
        return ok({"id": str(d.id), "code": d.code, "name": d.name,
                   "hod": d.hod, "institution_id": str(d.institution_id), "is_active": d.is_active})

    def delete(self, request, pk):
        d = get_object_or_404(Department, id=pk)
        d.is_active = False
        d.save(update_fields=["is_active"])
        return ok({"deleted": True})


class ProgrammeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        p = get_object_or_404(Programme, id=pk)
        return ok({
            "id": str(p.id), "code": p.code, "name": p.name,
            "level": p.get_level_display(), "department": p.department.name,
            "department_id": str(p.department_id),
            "total_terms": p.total_terms, "sharing_group": p.sharing_group,
        })

    def put(self, request, pk):
        p    = get_object_or_404(Programme, id=pk)
        data = request.data
        for field in ("code", "name", "level", "total_terms", "sharing_group", "is_active"):
            if field in data:
                setattr(p, field, data[field])
        if "department_id" in data:
            p.department = get_object_or_404(Department, id=data["department_id"])
        p.save()
        return ok({"id": str(p.id), "code": p.code, "name": p.name})

    def delete(self, request, pk):
        p = get_object_or_404(Programme, id=pk)
        p.is_active = False
        p.save(update_fields=["is_active"])
        return ok({"deleted": True})


class RoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        r = get_object_or_404(Room, id=pk)
        return ok({
            "id": str(r.id), "code": r.code, "name": r.name,
            "room_type": r.get_room_type_display(), "capacity": r.capacity,
            "building": r.building, "features": r.features,
        })

    def put(self, request, pk):
        r    = get_object_or_404(Room, id=pk)
        data = request.data
        for field in ("code", "name", "room_type", "capacity", "building", "features", "is_active"):
            if field in data:
                setattr(r, field, data[field])
        r.save()
        return ok({"id": str(r.id), "code": r.code, "name": r.name})

    def delete(self, request, pk):
        r = get_object_or_404(Room, id=pk)
        r.is_active = False
        r.save(update_fields=["is_active"])
        return ok({"deleted": True})


class TrainerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        t = get_object_or_404(Trainer, id=pk)
        return ok(_trainer_dict(t))

    def put(self, request, pk):
        t    = get_object_or_404(Trainer, id=pk)
        data = request.data
        for field in ("staff_id", "full_name", "short_name", "email",
                      "employment_type", "max_periods_per_week", "is_active"):
            if field in data:
                setattr(t, field, data[field])
        if "department_id" in data:
            t.department = get_object_or_404(Department, id=data["department_id"])
        t.save()
        return ok(_trainer_dict(t))

    def delete(self, request, pk):
        t = get_object_or_404(Trainer, id=pk)
        t.is_active = False
        t.save(update_fields=["is_active"])
        return ok({"deleted": True})


class CohortDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        c = get_object_or_404(Cohort, id=pk)
        return ok({
            "id": str(c.id), "name": c.name,
            "programme": c.programme.name, "programme_id": str(c.programme_id),
            "current_term": c.current_term,
            "computed_current_term": c.computed_current_term,
            "term_is_synced": c.term_is_synced,
            "student_count": c.student_count,
            "start_year": c.start_year, "start_month": c.start_month,
            "is_active": c.is_active,
        })

    def put(self, request, pk):
        c    = get_object_or_404(Cohort, id=pk)
        data = request.data
        for field in ("name", "student_count", "start_year", "start_month", "is_active"):
            if field in data:
                setattr(c, field, data[field])
        # current_term is managed via enrolments — do not allow direct edits
        c.save()
        return ok({"id": str(c.id), "name": c.name})

    def delete(self, request, pk):
        c = get_object_or_404(Cohort, id=pk)
        c.delete()
        return ok({"deleted": True})


class PeriodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        p = get_object_or_404(Period, id=pk)
        return ok(_period_dict(p))

    def put(self, request, pk):
        p    = get_object_or_404(Period, id=pk)
        data = request.data
        for field in ("label", "start_time", "end_time", "order", "is_break"):
            if field in data:
                setattr(p, field, data[field])
        p.save()
        return ok(_period_dict(p))

    def delete(self, request, pk):
        p = get_object_or_404(Period, id=pk)
        p.delete()
        return ok({"deleted": True})


class TermDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        t = get_object_or_404(Term, id=pk)
        return ok(_term_dict(t))

    def put(self, request, pk):
        t    = get_object_or_404(Term, id=pk)
        data = request.data
        for field in ("name", "start_date", "end_date", "teaching_weeks", "is_current"):
            if field in data:
                setattr(t, field, data[field])
        t.save()
        return ok(_term_dict(t))

    def delete(self, request, pk):
        t = get_object_or_404(Term, id=pk)
        t.delete()
        return ok({"deleted": True})