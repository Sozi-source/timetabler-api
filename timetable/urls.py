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
    # API endpoints
    path('api/', include(router.urls)),
    
    # Timetable views
    path('api/timetable/master/', views.MasterTimetableView.as_view(), name='master-timetable'),
    path('api/timetable/personal/', views.PersonalTimetableView.as_view(), name='personal-timetable'),
    
    # Scheduling endpoints
    path('api/schedule/generate/', views.GenerateTimetableView.as_view(), name='schedule-generate'),
    path('api/schedule/publish/', views.PublishTimetableView.as_view(), name='schedule-publish'),
    
    # Export endpoints
    path('api/export/master-pdf/', views.ExportMasterPDFView.as_view(), name='export-master-pdf'),
    path('api/export/personal-pdf/<uuid:lecturer_id>/', views.ExportPersonalPDFView.as_view(), name='export-personal-pdf'),
    path('api/export/excel/', views.ExportExcelView.as_view(), name='export-excel'),
    
    # Dashboard endpoints
    path('api/dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('api/dashboard/lecturer/', views.LecturerDashboardView.as_view(), name='lecturer-dashboard'),
    
    # WebSocket token
    path('api/websocket/token/', views.WebSocketTokenView.as_view(), name='websocket-token'),
]