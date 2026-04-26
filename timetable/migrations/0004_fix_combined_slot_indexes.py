from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0003_add_is_outsourced_to_curriculum_unit"),
    ]

    operations = [
        migrations.RunSQL(
            "DROP INDEX IF EXISTS uniq_trainer_slot_published;",
            reverse_sql="",
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS uniq_cohort_slot_published;",
            reverse_sql="",
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS uniq_room_slot_published;",
            reverse_sql="",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS uniq_trainer_slot_published ON timetable_scheduledunit (term_id, trainer_id, day, period_id) WHERE status = 'PUBLISHED' AND is_combined = FALSE;",
            reverse_sql="DROP INDEX IF EXISTS uniq_trainer_slot_published;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS uniq_cohort_slot_published ON timetable_scheduledunit (term_id, cohort_id, day, period_id) WHERE status = 'PUBLISHED' AND is_combined = FALSE;",
            reverse_sql="DROP INDEX IF EXISTS uniq_cohort_slot_published;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS uniq_room_slot_published ON timetable_scheduledunit (term_id, room_id, day, period_id) WHERE status = 'PUBLISHED' AND is_combined = FALSE;",
            reverse_sql="DROP INDEX IF EXISTS uniq_room_slot_published;",
        ),
    ]
