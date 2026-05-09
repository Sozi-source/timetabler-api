"""
timetable/serializers.py
========================
DRF serializers.
"""
from rest_framework import serializers
from .models import (
    AuditLog, Cohort, Conflict, Constraint, CurriculumUnit,
    Department, Institution, Period, Programme, ProgressRecord,
    Room, ScheduledUnit, Term, Trainer, TrainerAvailability,
)


class CurriculumUnitReadSerializer(serializers.ModelSerializer):
    unit_type          = serializers.CharField(source="get_unit_type_display")
    programme_code     = serializers.CharField(source="programme.code", read_only=True)
    qualified_trainers = serializers.SerializerMethodField()

    class Meta:
        model  = CurriculumUnit
        fields = [
            "id", "programme_code", "term_number", "position", "code",
            "name", "unit_type", "credit_hours", "periods_per_week",
            "session_pattern", "is_active", "notes", "qualified_trainers",
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
            "session_pattern", "is_active", "notes", "qualified_trainers",
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


class ConstraintSerializer(serializers.ModelSerializer):
    unit_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()

    class Meta:
        model  = Constraint
        fields = [
            "id", "scope", "rule", "is_hard",
            "curriculum_unit", "trainer", "room", "cohort",
            "unit_name", "unit_code",
            "parameters", "is_active", "notes",
        ]
        read_only_fields = ["id", "unit_name", "unit_code"]

    def get_unit_name(self, obj):
        return obj.curriculum_unit.name if obj.curriculum_unit_id else None

    def get_unit_code(self, obj):
        return obj.curriculum_unit.code if obj.curriculum_unit_id else None

    def validate(self, data):
        entity_fields = ["curriculum_unit", "trainer", "room", "cohort"]
        if not any(data.get(f) for f in entity_fields):
            raise serializers.ValidationError(
                "At least one of curriculum_unit, trainer, room, or cohort must be set."
            )
        return data
