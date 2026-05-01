from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timetable', '0004_fix_combined_slot_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE timetable_scheduledunit
                DROP CONSTRAINT IF EXISTS uniq_trainer_slot;
                ALTER TABLE timetable_scheduledunit
                DROP CONSTRAINT IF EXISTS uniq_cohort_slot;
                ALTER TABLE timetable_scheduledunit
                DROP CONSTRAINT IF EXISTS uniq_room_slot;

                ALTER TABLE timetable_scheduledunit
                ADD CONSTRAINT uniq_cohort_unit_period
                UNIQUE (term_id, cohort_id, curriculum_unit_id, period_id);
            """,
            reverse_sql="""
                ALTER TABLE timetable_scheduledunit
                DROP CONSTRAINT IF EXISTS uniq_cohort_unit_period;
            """
        ),
    ]
