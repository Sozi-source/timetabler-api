from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import (
    AcademicYear, Semester, Department, Programme, Stage, Unit,
    Intake, IntakeUnit, Lecturer, LecturerPreferences, Room,
    TimeSlot, TimetableEntry, ConflictLog, ScheduleAudit,
)

# ============== Base Serializers ==============

class BaseModelSerializer(serializers.ModelSerializer):
    created_at_display = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", source='created_at', read_only=True
    )
    updated_at_display = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", source='updated_at', read_only=True
    )

    class Meta:
        abstract = True


# ============== Academic Structure Serializers ==============

class AcademicYearSerializer(BaseModelSerializer):
    is_active_now = serializers.BooleanField(read_only=True)
    duration_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = AcademicYear
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by']


class SemesterSerializer(BaseModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    academic_year_year = serializers.IntegerField(source='academic_year.year', read_only=True)
    semester_type_display = serializers.CharField(source='get_semester_type_display', read_only=True)
    current_week = serializers.IntegerField(read_only=True)
    weeks_remaining = serializers.IntegerField(read_only=True)
    add_drop_deadline = serializers.DateField(required=False, allow_null=True)
    withdrawal_deadline = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = Semester
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'semester_number']


class DepartmentSerializer(BaseModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProgrammeSerializer(BaseModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    programme_type_display = serializers.CharField(source='get_programme_type_display', read_only=True)

    class Meta:
        model = Programme
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class StageSerializer(BaseModelSerializer):
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    programme_code = serializers.CharField(source='programme.code', read_only=True)

    class Meta:
        model = Stage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class UnitSerializer(BaseModelSerializer):
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    stage_semester_number = serializers.IntegerField(source='stage.semester_number', read_only=True)
    programme_code = serializers.CharField(source='stage.programme.code', read_only=True)
    unit_type_display = serializers.CharField(source='get_unit_type_display', read_only=True)
    assessment_type_display = serializers.CharField(source='get_assessment_type_display', read_only=True)
    prerequisites_list = serializers.SerializerMethodField()
    corequisites_list = serializers.SerializerMethodField()
    has_prerequisites = serializers.BooleanField(read_only=True)

    class Meta:
        model = Unit
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_hours_per_week', 'slots_per_week']

    def get_prerequisites_list(self, obj):
        return [{'code': u.code, 'name': u.name, 'id': str(u.id)} for u in obj.prerequisites.all()]

    def get_corequisites_list(self, obj):
        return [{'code': u.code, 'name': u.name, 'id': str(u.id)} for u in obj.corequisites.all()]


# ============== Intake and Student Management ==============

class IntakeUnitSerializer(BaseModelSerializer):
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    unit_credit_hours = serializers.IntegerField(source='unit.credit_hours', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    semester_type = serializers.CharField(source='semester.semester_type', read_only=True)

    class Meta:
        model = IntakeUnit
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IntakeSerializer(BaseModelSerializer):
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    programme_code = serializers.CharField(source='programme.code', read_only=True)
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    academic_year_year = serializers.IntegerField(source='academic_year.year', read_only=True)
    gender_ratio = serializers.DictField(read_only=True)
    # FIX: correct related_name — IntakeUnit has no explicit related_name, so Django
    # uses the default accessor 'intakeunit_set' on Intake. This is correct.
    units_detail = IntakeUnitSerializer(source='intakeunit_set', many=True, read_only=True)

    class Meta:
        model = Intake
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IntakeDetailSerializer(IntakeSerializer):
    """Detailed intake serializer with additional information."""
    total_units = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()

    class Meta(IntakeSerializer.Meta):
        fields = '__all__'

    def get_total_units(self, obj):
        return obj.units.count()

    def get_total_students(self, obj):
        return obj.student_count

    def get_completion_percentage(self, obj):
        if obj.expected_completion and obj.enrollment_date:
            total_days = (obj.expected_completion - obj.enrollment_date).days
            elapsed_days = (timezone.now().date() - obj.enrollment_date).days
            if total_days > 0:
                return min(100, max(0, int((elapsed_days / total_days) * 100)))
        return 0


# ============== Lecturer Management ==============

class LecturerPreferencesSerializer(BaseModelSerializer):
    lecturer_name = serializers.CharField(source='lecturer.full_name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)

    class Meta:
        model = LecturerPreferences
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class LecturerSerializer(BaseModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    full_name = serializers.SerializerMethodField()
    short_name = serializers.SerializerMethodField()
    lecturer_type_display = serializers.CharField(source='get_lecturer_type_display', read_only=True)
    title_display = serializers.CharField(source='get_title_display', read_only=True)
    qualified_units_detail = UnitSerializer(source='qualified_units', many=True, read_only=True)
    available_days_display = serializers.SerializerMethodField()
    current_workload = serializers.SerializerMethodField()

    class Meta:
        model = Lecturer
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

    def get_full_name(self, obj):
        return obj.full_name

    def get_short_name(self, obj):
        return obj.short_name

    def get_available_days_display(self, obj):
        if obj.lecturer_type == 'FT':
            return "Monday - Friday"
        return ", ".join([day.title() for day in obj.preferred_days])

    def get_current_workload(self, obj):
        semester = Semester.objects.filter(is_active=True).first()
        if semester:
            return obj.get_current_workload(semester)
        return 0


class LecturerDetailSerializer(LecturerSerializer):
    """Detailed lecturer serializer with statistics."""
    # FIX: related_name on LecturerPreferences.lecturer is 'preferences', not 'lecturerpreferences_set'
    preferences = LecturerPreferencesSerializer(source='preferences', many=True, read_only=True)
    total_qualified_units = serializers.SerializerMethodField()
    availability_summary = serializers.SerializerMethodField()

    class Meta(LecturerSerializer.Meta):
        fields = '__all__'

    def get_total_qualified_units(self, obj):
        return obj.qualified_units.count()

    def get_availability_summary(self, obj):
        semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            return {}

        booked_slots = TimetableEntry.objects.filter(
            semester=semester,
            lecturer=obj,
            status='PUBLISHED',
            is_deleted=False
        ).count()

        return {
            'total_booked_hours': booked_slots * 2,
            'max_hours_per_week': obj.max_hours_per_week,
            'remaining_hours': max(0, obj.max_hours_per_week - (booked_slots * 2)),
            'available_days': obj.get_available_days(),
            'utilization_percentage': (
                (booked_slots * 2 / obj.max_hours_per_week * 100)
                if obj.max_hours_per_week > 0 else 0
            ),
        }


# ============== Room and Facility Management ==============

class RoomSerializer(BaseModelSerializer):
    room_type_display = serializers.CharField(source='get_room_type_display', read_only=True)
    # FIX: utilization_rate is a @property, not a callable — use SerializerMethodField
    utilization_rate = serializers.SerializerMethodField()
    equipment_list = serializers.ListField(source='equipment', read_only=True)

    class Meta:
        model = Room
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_utilization_rate(self, obj):
        # utilization_rate is a property that internally fetches the active semester
        return obj.utilization_rate


# FIX: TimeSlot does NOT extend BaseModel, so use plain ModelSerializer
class TimeSlotSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_slot_id_display', read_only=True)
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = TimeSlot
        fields = '__all__'

    def get_duration_hours(self, obj):
        from datetime import datetime, date
        delta = (
            datetime.combine(date.today(), obj.end_time)
            - datetime.combine(date.today(), obj.start_time)
        )
        return delta.seconds / 3600


# ============== Timetable Management ==============

class TimetableEntrySerializer(BaseModelSerializer):
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    lecturer_name = serializers.SerializerMethodField()
    lecturer_short_name = serializers.SerializerMethodField()
    intake_name = serializers.CharField(source='intake.name', read_only=True)
    intake_code = serializers.CharField(source='intake.programme.code', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    room_code = serializers.CharField(source='room.code', read_only=True)
    time_display = serializers.CharField(source='time_slot.get_slot_id_display', read_only=True)
    day_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)

    class Meta:
        model = TimetableEntry
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at', 'approved_at']

    def get_lecturer_name(self, obj):
        return obj.lecturer.full_name

    def get_lecturer_short_name(self, obj):
        return obj.lecturer.short_name

    def get_day_display(self, obj):
        return dict(obj._meta.get_field('day').choices).get(obj.day, obj.day)


class TimetableEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating timetable entries with validation."""

    class Meta:
        model = TimetableEntry
        fields = '__all__'

    def validate(self, data):
        # Validate that lecturer is qualified for the unit
        if not data['lecturer'].qualified_units.filter(id=data['unit'].id).exists():
            raise serializers.ValidationError(
                f"Lecturer {data['lecturer'].full_name} is not qualified to teach {data['unit'].name}"
            )

        # Validate room capacity
        if data['intake'].student_count > data['room'].capacity:
            raise serializers.ValidationError(
                f"Room capacity ({data['room'].capacity}) is less than intake size ({data['intake'].student_count})"
            )

        # Validate part-time lecturer availability
        if data['lecturer'].lecturer_type == 'PT':
            if data['day'] not in data['lecturer'].get_available_days():
                raise serializers.ValidationError(
                    f"Part-time lecturer not available on {data['day']}"
                )

        return data


class TimetableEntryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating timetable entries."""

    class Meta:
        model = TimetableEntry
        fields = ['day', 'time_slot', 'room', 'status', 'week_number', 'notes']

    def validate(self, data):
        instance = self.instance
        semester = instance.semester

        # Check for conflicts when promoting to PUBLISHED
        if data.get('status') == 'PUBLISHED' and instance.status != 'PUBLISHED':
            day = data.get('day', instance.day)
            time_slot = data.get('time_slot', instance.time_slot)
            room = data.get('room', instance.room)
            week_number = data.get('week_number', instance.week_number)

            # Lecturer conflict
            if TimetableEntry.objects.filter(
                semester=semester,
                lecturer=instance.lecturer,
                day=day,
                time_slot=time_slot,
                week_number=week_number,
                status='PUBLISHED',
                is_deleted=False,
            ).exclude(id=instance.id).exists():
                raise serializers.ValidationError(
                    f"Lecturer already has a class at {day} {time_slot.get_slot_id_display()} in week {week_number}"
                )

            # Intake conflict
            if TimetableEntry.objects.filter(
                semester=semester,
                intake=instance.intake,
                day=day,
                time_slot=time_slot,
                week_number=week_number,
                status='PUBLISHED',
                is_deleted=False,
            ).exclude(id=instance.id).exists():
                raise serializers.ValidationError(
                    f"Intake already has a class at {day} {time_slot.get_slot_id_display()} in week {week_number}"
                )

            # Room conflict
            if TimetableEntry.objects.filter(
                semester=semester,
                room=room,
                day=day,
                time_slot=time_slot,
                week_number=week_number,
                status='PUBLISHED',
                is_deleted=False,
            ).exclude(id=instance.id).exists():
                raise serializers.ValidationError(
                    f"Room already booked at {day} {time_slot.get_slot_id_display()} in week {week_number}"
                )

        return data


# ============== Timetable Grid Serializers ==============

class TimetableCellSerializer(serializers.Serializer):
    """Serializer for a single timetable cell."""
    id = serializers.UUIDField()
    unit_code = serializers.CharField()
    unit_name = serializers.CharField()
    lecturer = serializers.CharField()
    lecturer_id = serializers.UUIDField()
    room = serializers.CharField()
    room_code = serializers.CharField()
    intake = serializers.CharField()
    intake_id = serializers.UUIDField()


class TimetableGridSerializer(serializers.Serializer):
    """Serializer for master timetable grid."""
    semester = serializers.CharField()
    semester_id = serializers.UUIDField()
    days = serializers.ListField(child=serializers.CharField())
    slot_labels = serializers.DictField()
    grid = serializers.DictField()
    week_number = serializers.IntegerField()
    total_weeks = serializers.IntegerField()


class PersonalTimetableSerializer(serializers.Serializer):
    """Serializer for personal lecturer timetable."""
    lecturer_id = serializers.UUIDField()
    lecturer_name = serializers.CharField()
    lecturer_type = serializers.CharField()
    available_days = serializers.ListField(child=serializers.CharField())
    semester = serializers.CharField()
    semester_id = serializers.UUIDField()
    days = serializers.ListField(child=serializers.CharField())
    slot_labels = serializers.DictField()
    grid = serializers.DictField()
    week_number = serializers.IntegerField()
    total_weeks = serializers.IntegerField()
    total_hours = serializers.IntegerField()
    max_hours_per_week = serializers.IntegerField()
    hours_remaining = serializers.IntegerField()
    weekly_breakdown = serializers.DictField()


# ============== Conflict and Audit Serializers ==============

class ConflictLogSerializer(BaseModelSerializer):
    conflict_type_display = serializers.CharField(source='get_conflict_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    resolution_status_display = serializers.CharField(source='get_resolution_status_display', read_only=True)
    resolved_by_name = serializers.SerializerMethodField()
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    affected_entry_detail = TimetableEntrySerializer(source='affected_entry', read_only=True)

    class Meta:
        model = ConflictLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_resolved_by_name(self, obj):
        return obj.resolved_by.username if obj.resolved_by else None


class ScheduleAuditSerializer(BaseModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField()
    timetable_entry_detail = TimetableEntrySerializer(source='timetable_entry', read_only=True)

    class Meta:
        model = ScheduleAudit
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_changed_by_name(self, obj):
        return obj.changed_by.username if obj.changed_by else None


# ============== Dashboard and Statistics Serializers ==============

class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics."""
    total_lecturers = serializers.IntegerField()
    total_rooms = serializers.IntegerField()
    total_intakes = serializers.IntegerField()
    total_units = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    total_programmes = serializers.IntegerField()
    current_semester = serializers.DictField(required=False)
    lecturer_workload = serializers.ListField()
    recent_activities = serializers.ListField()


class SemesterStatisticsSerializer(serializers.Serializer):
    """Serializer for semester statistics."""
    total_classes = serializers.IntegerField()
    published_classes = serializers.IntegerField()
    draft_classes = serializers.IntegerField()
    cancelled_classes = serializers.IntegerField()
    lecturers_utilized = serializers.IntegerField()
    rooms_utilized = serializers.IntegerField()
    intakes_scheduled = serializers.IntegerField()
    conflicts = serializers.IntegerField()
    utilization_rate = serializers.FloatField()
    current_week = serializers.IntegerField()
    weeks_remaining = serializers.IntegerField()


# ============== Request/Response Serializers ==============

class GenerateTimetableRequestSerializer(serializers.Serializer):
    """Serializer for timetable generation request."""
    semester_id = serializers.UUIDField()
    algorithm = serializers.ChoiceField(choices=['OR_TOOLS', 'AI', 'HYBRID'], default='HYBRID')
    prioritize = serializers.ListField(child=serializers.CharField(), required=False)
    max_iterations = serializers.IntegerField(default=1000, min_value=100, max_value=10000)


class MoveSlotRequestSerializer(serializers.Serializer):
    """Serializer for moving a timetable slot."""
    new_day = serializers.ChoiceField(choices=['MON', 'TUE', 'WED', 'THU', 'FRI'])
    new_time_slot_id = serializers.UUIDField()
    new_room_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True)


class BulkImportLecturersSerializer(serializers.Serializer):
    """Serializer for bulk lecturer import."""
    lecturers = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of lecturer objects to import",
    )


class BulkImportUnitsSerializer(serializers.Serializer):
    """Serializer for bulk unit import."""
    stage_id = serializers.UUIDField()
    units = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of unit objects to import",
    )


class AssignUnitsToIntakeSerializer(serializers.Serializer):
    """Serializer for assigning units to intake."""
    semester_id = serializers.UUIDField()
    units = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of unit assignments",
    )


# ============== User and Authentication Serializers ==============

class UserSerializer(serializers.ModelSerializer):
    """Serializer for Django User model."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_staff', 'is_active']
        read_only_fields = ['id', 'is_staff', 'is_active']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


# FIX: UserProfileSerializer should not have model = User and try to serialize
# lecturer_profile as if it's a User field. Use a plain Serializer instead.
class UserProfileSerializer(serializers.Serializer):
    """Serializer for user profile with lecturer details."""
    user = UserSerializer(read_only=True)
    # lecturer_profile is the related_name on Lecturer.user OneToOneField
    lecturer_profile = LecturerSerializer(read_only=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    is_superuser = serializers.BooleanField(source='user.is_superuser', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    last_login = serializers.DateTimeField(source='user.last_login', read_only=True)


# ============== Export Serializers ==============

class ExportFilterSerializer(serializers.Serializer):
    """Serializer for export filters."""
    semester_id = serializers.UUIDField(required=False)
    week_number = serializers.IntegerField(required=False, min_value=1, max_value=16)
    format = serializers.ChoiceField(choices=['PDF', 'EXCEL', 'CSV'], default='PDF')
    include_headers = serializers.BooleanField(default=True)
    orientation = serializers.ChoiceField(choices=['PORTRAIT', 'LANDSCAPE'], default='LANDSCAPE')


class TimetableExportDataSerializer(serializers.Serializer):
    """Serializer for timetable export data."""
    semester_name = serializers.CharField()
    semester_id = serializers.UUIDField()
    export_date = serializers.DateTimeField()
    week_number = serializers.IntegerField()
    days = serializers.ListField(child=serializers.CharField())
    time_slots = serializers.ListField()
    data = serializers.DictField()
    metadata = serializers.DictField(required=False)


# ============== WebSocket Serializers ==============

class WebSocketMessageSerializer(serializers.Serializer):
    """Serializer for WebSocket messages."""
    type = serializers.ChoiceField(choices=[
        'ping', 'lock_request', 'release_lock', 'conflict_check',
        'get_active_users', 'timetable_update',
    ])
    data = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(required=False)


class WebSocketLockRequestSerializer(serializers.Serializer):
    """Serializer for lock request."""
    slot_id = serializers.CharField()
    day = serializers.ChoiceField(choices=['MON', 'TUE', 'WED', 'THU', 'FRI'])
    time_slot_id = serializers.UUIDField()
    week_number = serializers.IntegerField(min_value=1, max_value=16)


# ============== AI Chat Serializers ==============

class AIChatRequestSerializer(serializers.Serializer):
    """Serializer for AI chat request."""
    message = serializers.CharField(max_length=1000)
    semester_id = serializers.UUIDField(required=False)
    context = serializers.DictField(required=False)


class AIChatResponseSerializer(serializers.Serializer):
    """Serializer for AI chat response."""
    success = serializers.BooleanField()
    response = serializers.CharField()
    suggested_actions = serializers.ListField(child=serializers.CharField(), required=False)
    data = serializers.DictField(required=False)
    error = serializers.CharField(required=False)