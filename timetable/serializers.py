"""
timetable/serializers.py
========================
DRF serializers for write operations (POST/PUT/PATCH).

Read responses use plain dicts (see views.py helpers) for maximum control
and performance. Serializers are used for:
  - Input validation on write endpoints
  - Nested reads where DRF depth makes things cleaner
  - API schema generation (drf-spectacular / drf-yasg)

Naming convention
-----------------
  <Model>Serializer      — full read/write serializer
  <Model>WriteSerializer — write-only (validation + create/update)
  <Model>ReadSerializer  — read-only (used for nested output)
"""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from .models import (
    AuditLog, Cohort, Conflict, Constraint, CurriculumUnit,
    Department, Institution, Period, Programme, ProgressRecord,
    Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared field helpers
# ─────────────────────────────────────────────────────────────────────────────

class UUIDRelatedField(serializers.PrimaryKeyRelatedField):
    """Return UUIDs as strings in serialized output."""
    def to_representation(self, value):
        return str(value.pk)


# ─────────────────────────────────────────────────────────────────────────────
# Institution
# ─────────────────────────────────────────────────────────────────────────────

class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Institution
        fields = [
            "id", "name", "short_name", "country", "timezone",
            "days_of_week", "allow_back_to_back", "max_periods_per_day",
        ]
        read_only_fields = ["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Department
# ─────────────────────────────────────────────────────────────────────────────

class DepartmentSerializer(serializers.ModelSerializer):
    institution_id = serializers.UUIDField(write_only=True)

    class Meta:
        model  = Department
        fields = ["id", "code", "name", "hod", "email", "is_active", "institution_id"]
        read_only_fields = ["id"]

    def validate_institution_id(self, value):
        if not Institution.objects.filter(id=value).exists():
            raise serializers.ValidationError("Institution not found.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Programme
# ─────────────────────────────────────────────────────────────────────────────

class ProgrammeReadSerializer(serializers.ModelSerializer):
    department = serializers.StringRelatedField()
    level      = serializers.CharField(source="get_level_display")

    class Meta:
        model  = Programme
        fields = ["id", "code", "name", "level", "department", "total_terms", "sharing_group", "is_active"]


class ProgrammeWriteSerializer(serializers.ModelSerializer):
    department_id = serializers.UUIDField()

    class Meta:
        model  = Programme
        fields = ["code", "name", "level", "department_id", "total_terms", "sharing_group", "is_active"]

    def validate_department_id(self, value):
        if not Department.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active department not found.")
        return value

    def create(self, validated_data):
        dept_id = validated_data.pop("department_id")
        return Programme.objects.create(department_id=dept_id, **validated_data)

    def update(self, instance, validated_data):
        dept_id = validated_data.pop("department_id", None)
        if dept_id:
            instance.department_id = dept_id
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# CurriculumUnit
# ─────────────────────────────────────────────────────────────────────────────

class CurriculumUnitReadSerializer(serializers.ModelSerializer):
    unit_type          = serializers.CharField(source="get_unit_type_display")
    programme_code     = serializers.CharField(source="programme.code", read_only=True)
    qualified_trainers = serializers.SerializerMethodField()

    class Meta:
        model  = CurriculumUnit
        fields = [
            "id", "programme_code", "term_number", "position", "code",
            "name", "unit_type", "credit_hours", "periods_per_week",
            "is_active", "notes", "qualified_trainers",
        ]

    def get_qualified_trainers(self, obj):
        return [
            {"id": str(t.id), "name": t.short_name}
            for t in obj.qualified_trainers.filter(is_active=True)
        ]


class CurriculumUnitWriteSerializer(serializers.ModelSerializer):
    programme_id       = serializers.UUIDField()
    qualified_trainers = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )

    class Meta:
        model  = CurriculumUnit
        fields = [
            "programme_id", "term_number", "position", "code",
            "name", "unit_type", "credit_hours", "periods_per_week",
            "is_active", "notes", "qualified_trainers",
        ]

    def validate_programme_id(self, value):
        if not Programme.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active programme not found.")
        return value

    def validate_periods_per_week(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("periods_per_week must be between 1 and 5.")
        return value

    def _set_trainers(self, instance, trainer_ids):
        if trainer_ids is not None:
            trainers = Trainer.objects.filter(id__in=trainer_ids, is_active=True)
            instance.qualified_trainers.set(trainers)

    def create(self, validated_data):
        trainer_ids = validated_data.pop("qualified_trainers", None)
        prog_id     = validated_data.pop("programme_id")
        instance    = CurriculumUnit.objects.create(programme_id=prog_id, **validated_data)
        self._set_trainers(instance, trainer_ids)
        return instance

    def update(self, instance, validated_data):
        trainer_ids = validated_data.pop("qualified_trainers", None)
        prog_id     = validated_data.pop("programme_id", None)
        if prog_id:
            instance.programme_id = prog_id
        instance = super().update(instance, validated_data)
        self._set_trainers(instance, trainer_ids)
        return instance


# ─────────────────────────────────────────────────────────────────────────────
# Period
# ─────────────────────────────────────────────────────────────────────────────

class PeriodSerializer(serializers.ModelSerializer):
    duration_hours = serializers.FloatField(read_only=True)

    class Meta:
        model  = Period
        fields = ["id", "institution", "label", "start_time", "end_time", "order", "is_break", "duration_hours"]
        read_only_fields = ["id", "duration_hours"]

    def validate(self, data):
        if data.get("start_time") and data.get("end_time"):
            if data["start_time"] >= data["end_time"]:
                raise serializers.ValidationError("end_time must be after start_time.")
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Room
# ─────────────────────────────────────────────────────────────────────────────

class RoomSerializer(serializers.ModelSerializer):
    room_type_display = serializers.CharField(source="get_room_type_display", read_only=True)

    class Meta:
        model  = Room
        fields = [
            "id", "institution", "code", "name", "room_type", "room_type_display",
            "capacity", "building", "floor", "is_active", "features",
        ]
        read_only_fields = ["id", "room_type_display"]

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Room capacity must be at least 1.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Term
# ─────────────────────────────────────────────────────────────────────────────

class TermSerializer(serializers.ModelSerializer):
    week_number    = serializers.IntegerField(read_only=True)
    weeks_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Term
        fields = [
            "id", "institution", "name", "start_date", "end_date",
            "teaching_weeks", "is_current", "week_number", "weeks_remaining",
        ]
        read_only_fields = ["id", "week_number", "weeks_remaining"]

    def validate(self, data):
        start = data.get("start_date")
        end   = data.get("end_date")
        if start and end and start >= end:
            raise serializers.ValidationError({"end_date": "end_date must be after start_date."})
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Trainer
# ─────────────────────────────────────────────────────────────────────────────

class TrainerReadSerializer(serializers.ModelSerializer):
    department        = serializers.StringRelatedField()
    employment_type   = serializers.CharField(source="get_employment_type_display")

    class Meta:
        model  = Trainer
        fields = [
            "id", "staff_id", "title", "first_name", "last_name", "email",
            "phone", "department", "employment_type", "max_periods_per_week",
            "available_days", "is_active",
        ]


class TrainerWriteSerializer(serializers.ModelSerializer):
    institution_id = serializers.UUIDField()
    department_id  = serializers.UUIDField()

    class Meta:
        model  = Trainer
        fields = [
            "institution_id", "department_id", "staff_id", "title",
            "first_name", "last_name", "email", "phone", "employment_type",
            "max_periods_per_week", "available_days", "is_active",
        ]

    def validate_department_id(self, value):
        if not Department.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active department not found.")
        return value

    def validate_max_periods_per_week(self, value):
        if value < 1 or value > 80:
            raise serializers.ValidationError("max_periods_per_week must be between 1 and 80.")
        return value

    def create(self, validated_data):
        inst_id = validated_data.pop("institution_id")
        dept_id = validated_data.pop("department_id")
        return Trainer.objects.create(
            institution_id=inst_id,
            department_id=dept_id,
            **validated_data
        )

    def update(self, instance, validated_data):
        inst_id = validated_data.pop("institution_id", None)
        dept_id = validated_data.pop("department_id", None)
        if inst_id:
            instance.institution_id = inst_id
        if dept_id:
            instance.department_id = dept_id
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# TrainerAvailability
# ─────────────────────────────────────────────────────────────────────────────

class TrainerAvailabilitySerializer(serializers.ModelSerializer):
    VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}

    class Meta:
        model  = TrainerAvailability
        fields = ["id", "trainer", "term", "day", "period", "is_available", "reason", "notes"]
        read_only_fields = ["id"]

    def validate_day(self, value):
        if value.upper() not in self.VALID_DAYS:
            raise serializers.ValidationError(f"Day must be one of: {', '.join(sorted(self.VALID_DAYS))}")
        return value.upper()


# ─────────────────────────────────────────────────────────────────────────────
# Cohort
# ─────────────────────────────────────────────────────────────────────────────

class CohortReadSerializer(serializers.ModelSerializer):
    programme    = serializers.StringRelatedField()
    progress     = serializers.SerializerMethodField()

    class Meta:
        model  = Cohort
        fields = [
            "id", "name", "programme", "start_year", "start_month",
            "current_term", "student_count", "is_active", "progress",
        ]

    def get_progress(self, obj):
        return obj.progress_summary


class CohortWriteSerializer(serializers.ModelSerializer):
    programme_id = serializers.UUIDField()

    class Meta:
        model  = Cohort
        fields = [
            "programme_id", "name", "start_year", "start_month",
            "current_term", "student_count", "is_active",
        ]

    def validate_programme_id(self, value):
        if not Programme.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active programme not found.")
        return value

    def validate_start_month(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError("start_month must be between 1 and 12.")
        return value

    def validate(self, data):
        prog_id = data.get("programme_id")
        current = data.get("current_term", 1)
        if prog_id:
            prog = Programme.objects.filter(id=prog_id).first()
            if prog and current > prog.total_terms:
                raise serializers.ValidationError(
                    {"current_term": f"current_term cannot exceed programme's total_terms ({prog.total_terms})."}
                )
        return data

    def create(self, validated_data):
        prog_id = validated_data.pop("programme_id")
        return Cohort.objects.create(programme_id=prog_id, **validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# ProgressRecord
# ─────────────────────────────────────────────────────────────────────────────

class ProgressRecordWriteSerializer(serializers.Serializer):
    unit_id    = serializers.UUIDField()
    status     = serializers.ChoiceField(choices=[
        ProgressRecord.NOT_STARTED,
        ProgressRecord.IN_PROGRESS,
        ProgressRecord.COMPLETED,
        ProgressRecord.DEFERRED,
    ])
    score      = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True,
        min_value=0, max_value=100,
    )

    def validate_unit_id(self, value):
        if not CurriculumUnit.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("CurriculumUnit not found.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Constraint
# ─────────────────────────────────────────────────────────────────────────────

class ConstraintSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Constraint
        fields = [
            "id", "scope", "rule", "is_hard",
            "curriculum_unit", "trainer", "room", "cohort",
            "parameters", "is_active", "notes",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        # At least one entity reference is required
        entity_fields = ["curriculum_unit", "trainer", "room", "cohort"]
        if not any(data.get(f) for f in entity_fields):
            raise serializers.ValidationError(
                "At least one of curriculum_unit, trainer, room, or cohort must be set."
            )

        # Validate parameter keys per rule
        rule   = data.get("rule")
        params = data.get("parameters", {})
        required_params = {
            "PIN_DAY_PERIOD": ["day", "period_id"],
            "PIN_DAY":        ["day"],
            "PREFERRED_ROOM": ["room_id"],
            "AVOID_DAY":      ["day"],
            "AVOID_PERIOD":   ["period_id"],
            "MAX_PER_DAY":    ["max"],
        }
        needed = required_params.get(rule, [])
        missing = [k for k in needed if k not in params]
        if missing:
            raise serializers.ValidationError(
                {"parameters": f"Rule '{rule}' requires parameter(s): {', '.join(missing)}"}
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# ScheduledUnit
# ─────────────────────────────────────────────────────────────────────────────

class ScheduledUnitReadSerializer(serializers.ModelSerializer):
    unit_code    = serializers.CharField(source="curriculum_unit.code", read_only=True)
    unit_name    = serializers.CharField(source="curriculum_unit.name", read_only=True)
    cohort_name  = serializers.CharField(source="cohort.name", read_only=True)
    trainer_name = serializers.CharField(source="trainer.short_name", read_only=True)
    room_code    = serializers.CharField(source="room.code", read_only=True)
    period_label = serializers.CharField(source="period.label", read_only=True)

    class Meta:
        model  = ScheduledUnit
        fields = [
            "id", "term", "cohort", "cohort_name", "curriculum_unit",
            "unit_code", "unit_name", "trainer", "trainer_name",
            "room", "room_code", "day", "period", "period_label",
            "sequence", "is_combined", "combined_key", "status",
            "published_at", "notes",
        ]
        read_only_fields = fields


class ScheduledUnitEditSerializer(serializers.ModelSerializer):
    """Used for PUT on individual entries — partial reassignment only."""
    trainer_id = serializers.UUIDField(required=False)
    room_id    = serializers.UUIDField(required=False)
    period_id  = serializers.UUIDField(required=False)
    day        = serializers.CharField(required=False, max_length=3)
    notes      = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model  = ScheduledUnit
        fields = ["trainer_id", "room_id", "period_id", "day", "notes"]

    VALID_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}

    def validate_day(self, value):
        if value.upper() not in self.VALID_DAYS:
            raise serializers.ValidationError(f"Invalid day. Must be one of: {', '.join(sorted(self.VALID_DAYS))}")
        return value.upper()

    def validate_trainer_id(self, value):
        if not Trainer.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active trainer not found.")
        return value

    def validate_room_id(self, value):
        if not Room.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Active room not found.")
        return value

    def validate_period_id(self, value):
        if not Period.objects.filter(id=value).exists():
            raise serializers.ValidationError("Period not found.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Conflict
# ─────────────────────────────────────────────────────────────────────────────

class ConflictReadSerializer(serializers.ModelSerializer):
    conflict_type = serializers.CharField(source="get_conflict_type_display")
    cohort_name   = serializers.CharField(source="cohort.name", read_only=True, allow_null=True)
    trainer_name  = serializers.CharField(source="trainer.short_name", read_only=True, allow_null=True)
    room_code     = serializers.CharField(source="room.code", read_only=True, allow_null=True)
    unit_code     = serializers.CharField(source="curriculum_unit.code", read_only=True, allow_null=True)

    class Meta:
        model  = Conflict
        fields = [
            "id", "term", "conflict_type", "severity", "description",
            "cohort", "cohort_name", "trainer", "trainer_name",
            "room", "room_code", "curriculum_unit", "unit_code",
            "resolution_status", "resolved_by", "resolved_at", "resolution_note",
            "created_at",
        ]
        read_only_fields = fields


class ConflictResolveSerializer(serializers.Serializer):
    note   = serializers.CharField(allow_blank=True, default="")
    method = serializers.ChoiceField(
        choices=["RESOLVED", "OVERRIDDEN", "IGNORED"],
        default="RESOLVED",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Timetable generation
# ─────────────────────────────────────────────────────────────────────────────

class GenerateSerializer(serializers.Serializer):
    term_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_term_id(self, value):
        if value and not Term.objects.filter(id=value).exists():
            raise serializers.ValidationError("Term not found.")
        return value


class PublishSerializer(serializers.Serializer):
    term_id = serializers.UUIDField(required=False, allow_null=True)
    force   = serializers.BooleanField(default=False)

    def validate_term_id(self, value):
        if value and not Term.objects.filter(id=value).exists():
            raise serializers.ValidationError("Term not found.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# AuditLog (read-only)
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogSerializer(serializers.ModelSerializer):
    action       = serializers.CharField(source="get_action_display")
    performed_by = serializers.StringRelatedField()

    class Meta:
        model  = AuditLog
        fields = ["id", "timestamp", "action", "performed_by", "term", "description", "payload"]
        read_only_fields = fields