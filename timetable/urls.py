"""
timetable/urls.py
"""
from . import ai_views
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views

urlpatterns = [

    #AI Views
    path("ai/chat/", ai_views.AIChatView.as_view()),

    # ── Auth ─────────────────────────────────────────────────────────────────
    path("auth/login/",                 obtain_auth_token),
    path("auth/me/",                    views.MeView.as_view()),

    # ── Institution / Setup ──────────────────────────────────────────────────
    path("institution/",                views.InstitutionView.as_view()),
    path("departments/",                views.DepartmentListView.as_view()),
    path("departments/<uuid:pk>/",       views.DepartmentDetailView.as_view()),
    path("programmes/",                 views.ProgrammeListView.as_view()),
    path("programmes/<uuid:pk>/",        views.ProgrammeDetailView.as_view()),
    
    path("curriculum/",                views.CurriculumView.as_view()),
    path('curriculum/<uuid:unit_id>/',          views.CurriculumUnitDetailView.as_view()),
    path('curriculum/<uuid:unit_id>/trainers/', views.CurriculumUnitTrainersView.as_view()),
    path("periods/",                    views.PeriodListView.as_view()),
    path("periods/<int:pk>/",            views.PeriodDetailView.as_view()),
    path("rooms/",                      views.RoomListView.as_view()),
    path("rooms/<uuid:pk>/",             views.RoomDetailView.as_view()),
    path("trainers/",                   views.TrainerListView.as_view()),
    path("trainers/<uuid:pk>/",          views.TrainerDetailView.as_view()),
    path("terms/",                      views.TermListView.as_view()),
    path("terms/<uuid:pk>/",             views.TermDetailView.as_view()),

    # ── Trainer availability ─────────────────────────────────────────────────
    path("trainers/<uuid:trainer_id>/availability/", views.TrainerAvailabilityView.as_view()),

    # ── Cohorts & Progression ────────────────────────────────────────────────
    path("cohorts/",                    views.CohortListView.as_view()),
    path("cohorts/<uuid:pk>/",           views.CohortDetailView.as_view()),
    path("cohorts/<uuid:cohort_id>/progress/",        views.CohortProgressView.as_view()),
    path("cohorts/<uuid:cohort_id>/advance/",         views.AdvanceCohortView.as_view()),
    path("cohorts/<uuid:cohort_id>/progress/update/", views.UpdateProgressView.as_view()),

    # ── Constraints ──────────────────────────────────────────────────────────
    path("constraints/",                views.ConstraintListView.as_view()),
    path("constraints/<uuid:constraint_id>/", views.ConstraintDetailView.as_view()),

    # ── Timetable generation ─────────────────────────────────────────────────
    path("timetable/generate/",         views.GenerateView.as_view()),
    path("timetable/publish/",          views.PublishView.as_view()),
    path("timetable/drafts/",           views.DeleteDraftsView.as_view()),

    # ── Timetable reading ────────────────────────────────────────────────────
    path("timetable/master/",           views.MasterTimetableView.as_view()),
    path("timetable/cohort/<uuid:cohort_id>/",   views.CohortTimetableView.as_view()),
    path("timetable/trainer/<uuid:trainer_id>/", views.TrainerTimetableView.as_view()),

    # ── Individual entry edit ────────────────────────────────────────────────
    path("timetable/entry/<uuid:entry_id>/", views.ScheduledUnitDetailView.as_view()),

    # ── Conflicts ────────────────────────────────────────────────────────────
    path("conflicts/",                  views.ConflictListView.as_view()),
    path("conflicts/<uuid:conflict_id>/resolve/", views.ResolveConflictView.as_view()),

    # ── Exports ──────────────────────────────────────────────────────────────
    path("export/master/",              views.ExportMasterView.as_view()),
    path("export/trainer/<uuid:trainer_id>/", views.ExportTrainerView.as_view()),
    path("export/cohort/<uuid:cohort_id>/",   views.ExportCohortView.as_view()),

    # ── Dashboards ───────────────────────────────────────────────────────────
    path("dashboard/",                  views.DashboardView.as_view()),
    path("dashboard/trainer/",          views.TrainerDashboardView.as_view()),
]




