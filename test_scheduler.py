import django, os, traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetabler.settings')
django.setup()
from timetable.models import Term
from timetable.scheduler import TimetableEngine
term = Term.objects.get(id='17cf960c-10dc-4c31-b38f-67cb5de2bcb7')
try:
    engine = TimetableEngine(term)
    result = engine.run(delete_existing_drafts=True)
    print(result.summary())
except Exception as e:
    traceback.print_exc()
