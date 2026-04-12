from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'academic-years', views.AcademicYearViewSet, basename='academic-year')
router.register(r'semesters', views.SemesterViewSet, basename='semester')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'programmes', views.ProgrammeViewSet, basename='programme')
router.register(r'stages', views.StageViewSet, basename='stage')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'intakes', views.IntakeViewSet, basename='intake')
router.register(r'lecturers', views.LecturerViewSet, basename='lecturer')
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'time-slots', views.TimeSlotViewSet, basename='time-slot')
router.register(r'timetable-entries', views.TimetableEntryViewSet, basename='timetable-entry')
router.register(r'conflicts', views.ConflictViewSet, basename='conflict')

urlpatterns = [
    # Router endpoints (CRUD)
    path('', include(router.urls)),

    # Timetable views
    path('timetable/master/', views.MasterTimetableView.as_view(), name='master-timetable'),
    path('timetable/personal/', views.PersonalTimetableView.as_view(), name='personal-timetable'),

    # Scheduling
    path('schedule/generate/', views.GenerateTimetableView.as_view(), name='schedule-generate'),
    path('schedule/publish/', views.PublishTimetableView.as_view(), name='schedule-publish'),

    # Export
    path('export/master-pdf/', views.ExportMasterPDFView.as_view(), name='export-master-pdf'),
    path('export/personal-pdf/<uuid:lecturer_id>/', views.ExportPersonalPDFView.as_view(), name='export-personal-pdf'),
    path('export/excel/', views.ExportExcelView.as_view(), name='export-excel'),

    # Dashboard
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/lecturer/', views.LecturerDashboardView.as_view(), name='lecturer-dashboard'),

    # WebSocket
    path('websocket/token/', views.WebSocketTokenView.as_view(), name='websocket-token'),
]