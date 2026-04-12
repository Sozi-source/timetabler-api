from django.contrib import admin
from django.utils.html import format_html
from .models import *

class BaseAdmin(admin.ModelAdmin):
    readonly_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AcademicYear)
class AcademicYearAdmin(BaseAdmin):
    list_display = ['year', 'name', 'start_date', 'end_date', 'is_current', 'is_active']
    list_filter = ['is_current', 'is_active']
    search_fields = ['year', 'name']
    actions = ['set_as_current']
    
    def set_as_current(self, request, queryset):
        queryset.update(is_current=True)
        AcademicYear.objects.exclude(id__in=queryset.values_list('id', flat=True)).update(is_current=False)
        self.message_user(request, "Selected academic year(s) set as current.")
    set_as_current.short_description = "Set selected as current academic year"


@admin.register(Semester)
class SemesterAdmin(BaseAdmin):
    list_display = ['academic_year', 'semester_type', 'start_date', 'end_date', 'is_active', 'current_week_display']
    list_filter = ['academic_year', 'semester_type', 'is_active']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    
    def current_week_display(self, obj):
        return obj.current_week
    current_week_display.short_description = 'Current Week'


@admin.register(Department)
class DepartmentAdmin(BaseAdmin):
    list_display = ['code', 'name', 'hod_name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'hod_name']


@admin.register(Programme)
class ProgrammeAdmin(BaseAdmin):
    list_display = ['code', 'name', 'programme_type', 'department', 'duration_semesters', 'is_active']
    list_filter = ['programme_type', 'department', 'is_active']
    search_fields = ['code', 'name']


@admin.register(Stage)
class StageAdmin(BaseAdmin):
    list_display = ['programme', 'semester_number', 'name', 'is_active']
    list_filter = ['programme', 'is_active']
    search_fields = ['name']


@admin.register(Unit)
class UnitAdmin(BaseAdmin):
    list_display = ['code', 'name', 'stage', 'unit_type', 'credit_hours', 'slots_per_week', 'is_active']
    list_filter = ['unit_type', 'stage', 'is_active']
    search_fields = ['code', 'name']
    filter_horizontal = ['prerequisites', 'corequisites']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'stage', 'unit_type', 'description')
        }),
        ('Hours and Credits', {
            'fields': ('credit_hours', 'lecture_hours_per_week', 'tutorial_hours_per_week', 'practical_hours_per_week')
        }),
        ('Assessment', {
            'fields': ('assessment_type', 'cat_weight', 'exam_weight', 'pass_mark')
        }),
        ('Prerequisites', {
            'fields': ('prerequisites', 'corequisites')
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )


class IntakeUnitInline(admin.TabularInline):
    """Inline editor for units assigned to an intake, replacing filter_horizontal."""
    model = IntakeUnit
    extra = 1
    fields = ['unit', 'semester', 'is_mandatory', 'is_elective_selected', 'exam_date', 'exam_venue']
    autocomplete_fields = ['unit', 'semester']


@admin.register(Intake)
class IntakeAdmin(BaseAdmin):
    list_display = ['name', 'programme', 'stage', 'academic_year', 'student_count', 'is_active']
    list_filter = ['programme', 'stage', 'academic_year', 'is_active']
    search_fields = ['name']
    # 'units' has a through model (IntakeUnit) so filter_horizontal is not supported.
    # Use the inline below to manage unit assignments instead.
    inlines = [IntakeUnitInline]


@admin.register(IntakeUnit)
class IntakeUnitAdmin(BaseAdmin):
    list_display = ['intake', 'unit', 'semester', 'is_mandatory']
    list_filter = ['semester', 'is_mandatory']
    search_fields = ['intake__name', 'unit__code']


@admin.register(Lecturer)
class LecturerAdmin(BaseAdmin):
    list_display = ['staff_id', 'full_name_display', 'lecturer_type', 'department', 'max_hours_per_week', 'is_active']
    list_filter = ['lecturer_type', 'department', 'is_active']
    search_fields = ['staff_id', 'first_name', 'last_name', 'email']
    filter_horizontal = ['qualified_units']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('staff_id', 'title', 'first_name', 'middle_name', 'last_name',
                       'email', 'alternative_email', 'phone', 'alternative_phone')
        }),
        ('Professional Information', {
            'fields': ('lecturer_type', 'department', 'highest_qualification',
                       'specialization', 'year_of_experience', 'bio')
        }),
        ('Schedule Settings', {
            'fields': ('max_hours_per_week', 'max_hours_per_day', 'preferred_days',
                       'preferred_time_slots', 'unavailable_dates', 'unavailable_weeks')
        }),
        ('Qualifications', {
            'fields': ('qualified_units',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_available_for_supervision')
        })
    )
    
    def full_name_display(self, obj):
        return obj.full_name
    full_name_display.short_description = 'Name'


@admin.register(Room)
class RoomAdmin(BaseAdmin):
    list_display = ['code', 'name', 'room_type', 'capacity', 'building', 'floor', 'has_projector', 'is_active']
    list_filter = ['room_type', 'building', 'has_projector', 'has_aircon', 'is_active']
    search_fields = ['code', 'name', 'building']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_id', 'start_time', 'end_time', 'order', 'is_evening']
    list_editable = ['order']
    ordering = ['order']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(BaseAdmin):
    list_display = ['unit', 'lecturer', 'intake', 'room', 'day', 'time_slot', 'week_number', 'status', 'color_status']
    list_filter = ['status', 'day', 'semester', 'week_number']
    search_fields = ['unit__code', 'lecturer__first_name', 'lecturer__last_name', 'intake__name']
    date_hierarchy = 'created_at'
    readonly_fields = ['published_at', 'approved_at']
    
    def color_status(self, obj):
        colors = {
            'PUBLISHED': 'green',
            'DRAFT': 'orange',
            'PENDING': 'blue',
            'CANCELLED': 'red',
            'RESCHEDULED': 'purple',
            'COMPLETED': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    color_status.short_description = 'Status'


@admin.register(ConflictLog)
class ConflictLogAdmin(BaseAdmin):
    list_display = ['conflict_type', 'severity', 'description_short', 'resolution_status', 'created_at']
    list_filter = ['conflict_type', 'severity', 'resolution_status', 'semester']
    search_fields = ['description']
    readonly_fields = ['created_at', 'updated_at']
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'


@admin.register(ScheduleAudit)
class ScheduleAuditAdmin(admin.ModelAdmin):
    list_display = ['timetable_entry', 'action', 'changed_by', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['timetable_entry__unit__code', 'changed_by__username']
    readonly_fields = ['created_at']


@admin.register(LecturerPreferences)
class LecturerPreferencesAdmin(admin.ModelAdmin):
    list_display = ['lecturer', 'semester', 'prefer_morning', 'prefer_afternoon', 'max_consecutive_hours']
    list_filter = ['semester', 'prefer_morning', 'prefer_afternoon']
    search_fields = ['lecturer__first_name', 'lecturer__last_name']


# Custom Admin Site Configuration
admin.site.site_header = "Timetable Management System"
admin.site.site_title = "Timetable Admin"
admin.site.index_title = "Welcome to Timetable Management System"