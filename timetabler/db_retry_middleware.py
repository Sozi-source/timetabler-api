
# timetabler/db_retry_middleware.py
from django.db import connection
from django.db.utils import OperationalError
import time

class DBRetryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        retries = 3
        for attempt in range(retries):
            try:
                connection.ensure_connection()
                break
            except OperationalError:
                if attempt < retries - 1:
                    connection.close()
                    time.sleep(2 ** attempt)
                else:
                    pass
        return self.get_response(request)
