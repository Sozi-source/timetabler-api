"""
timetable/signals.py
====================
Cache invalidation and audit logging for ScheduledUnit.

Signal registration
───────────────────
Signals are auto-discovered because timetable/apps.py does:

    def ready(self):
        import timetable.signals  # noqa: F401

This avoids double-registration in development (which would cause duplicate
AuditLog rows and redundant cache deletes on every save).
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

from .models import Trainer, AuditLog, ScheduledUnit


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _clear_timetable_cache_for_instance(instance: ScheduledUnit) -> None:
    """
    Delete all cache keys that could contain stale data for this entry's term.
    Compatible with every Django cache backend (LocMemCache, Redis, Memcached, etc.).
    """
    try:
        term_id = instance.term_id
        if not term_id:
            return

        # Invalidate master timetable for this term
        cache.delete(f"master_timetable_{term_id}")

        # Invalidate every trainer's personal timetable for this term
        trainer_ids = Trainer.objects.filter(
            is_active=True
        ).values_list("id", flat=True)

        for tid in trainer_ids:
            cache.delete(f"trainer_timetable_{tid}_{term_id}")

        # Invalidate cohort timetable cache if cohort is set
        if instance.cohort_id:
            cache.delete(f"cohort_timetable_{instance.cohort_id}_{term_id}")

    except Exception:
        # Cache errors must never propagate into the request/save cycle.
        pass


def _log_audit(scheduled_unit: ScheduledUnit, action: str, old_value=None, new_value=None) -> None:
    """
    Create an AuditLog row, swallowing all exceptions so audit logging
    never breaks the main save/delete path.
    """
    try:
        AuditLog.objects.create(
            scheduled_unit=scheduled_unit,
            action=action,
            old_value=old_value,
            new_value=new_value,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────
# Cache signals
# ─────────────────────────────────────────────

@receiver(post_save, sender=ScheduledUnit)
def clear_timetable_cache(sender, instance, created, **kwargs):
    """Invalidate cached timetable data whenever a ScheduledUnit is saved."""
    _clear_timetable_cache_for_instance(instance)


@receiver(post_delete, sender=ScheduledUnit)
def clear_timetable_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cached timetable data whenever a ScheduledUnit is deleted."""
    _clear_timetable_cache_for_instance(instance)


# ─────────────────────────────────────────────
# Audit signals
# ─────────────────────────────────────────────

@receiver(pre_save, sender=ScheduledUnit)
def track_timetable_changes(sender, instance, **kwargs):
    """
    Snapshot field values before a save so post_save can diff them.
    Uses _id suffix for FK fields to avoid extra DB hits and get
    stable, JSON-serialisable values.
    """
    if not instance.pk:
        return  # New instance — nothing to diff

    try:
        old = ScheduledUnit.objects.get(pk=instance.pk)
    except ScheduledUnit.DoesNotExist:
        return

    tracked = {
        "day":             ("day",              "day"),
        "period":          ("period_id",        "period_id"),
        "room":            ("room_id",          "room_id"),
        "trainer":         ("trainer_id",       "trainer_id"),
        "status":          ("status",           "status"),
        "curriculum_unit": ("curriculum_unit_id", "curriculum_unit_id"),
    }

    changes = {}
    for label, (old_attr, new_attr) in tracked.items():
        old_val = getattr(old, old_attr)
        new_val = getattr(instance, new_attr)
        if old_val != new_val:
            changes[label] = {"old": str(old_val), "new": str(new_val)}

    if changes:
        instance._changes = changes


@receiver(post_save, sender=ScheduledUnit)
def create_audit_log(sender, instance, created, **kwargs):
    """
    Write an AuditLog row after every save.
    CREATE — logs the creation timestamp.
    UPDATE — logs the full field-level diff captured by track_timetable_changes.
    """
    if created:
        _log_audit(
            instance,
            action="CREATE",
            new_value={"created_at": timezone.now().isoformat()},
        )
    elif hasattr(instance, "_changes"):
        _log_audit(
            instance,
            action="UPDATE",
            old_value={k: v["old"] for k, v in instance._changes.items()},
            new_value={k: v["new"] for k, v in instance._changes.items()},
        )


@receiver(post_delete, sender=ScheduledUnit)
def log_deletion(sender, instance, **kwargs):
    """
    Record a DELETE audit entry after a ScheduledUnit is removed.
    Cache invalidation is handled separately by clear_timetable_cache_on_delete.
    """
    _log_audit(
        instance,
        action="DELETE",
        old_value={"deleted_at": timezone.now().isoformat()},
    )