from django.apps import AppConfig

class TimetableConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timetable'
    verbose_name = 'Timetable Management System'

    def ready(self):
        # Import signals only when app is ready
        import timetable.signals