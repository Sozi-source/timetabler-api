from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from .models import TimetableEntry, ScheduleAudit, ConflictLog

@receiver(post_save, sender=TimetableEntry)
def clear_timetable_cache(sender, instance, created, **kwargs):
    """Clear cache when timetable changes"""
    cache.delete_pattern(f"*master_timetable*")
    cache.delete_pattern(f"*personal_timetable*")
    cache.delete_pattern(f"*timetable_stats*")


@receiver(pre_save, sender=TimetableEntry)
def track_timetable_changes(sender, instance, **kwargs):
    """Track changes to timetable entries for audit"""
    if instance.pk:
        try:
            old_instance = TimetableEntry.objects.get(pk=instance.pk)
            changes = {}
            
            # Track significant field changes
            fields_to_track = ['day', 'time_slot', 'room', 'status', 'week_number']
            for field in fields_to_track:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    changes[field] = {'old': str(old_value), 'new': str(new_value)}
            
            if changes:
                # Store changes in cache or log (will be saved after save)
                instance._changes = changes
        except TimetableEntry.DoesNotExist:
            pass


@receiver(post_save, sender=TimetableEntry)
def create_audit_log(sender, instance, created, **kwargs):
    """Create audit log for timetable changes"""
    if hasattr(instance, '_changes'):
        ScheduleAudit.objects.create(
            timetable_entry=instance,
            action='UPDATE',
            old_value=instance._changes,
            new_value={'updated_at': timezone.now().isoformat()}
        )
    elif created:
        ScheduleAudit.objects.create(
            timetable_entry=instance,
            action='CREATE',
            new_value={'created_at': timezone.now().isoformat()}
        )


@receiver(post_delete, sender=TimetableEntry)
def log_deletion(sender, instance, **kwargs):
    """Log deletion of timetable entries"""
    ScheduleAudit.objects.create(
        timetable_entry=instance,
        action='DELETE',
        old_value={'deleted_at': timezone.now().isoformat()}
    )