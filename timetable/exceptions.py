"""
timetable/exceptions.py
=======================
Custom DRF exception handler that normalises all error responses to:
  { "ok": false, "error": "...", "detail": "..." }

This keeps error shapes consistent with the ok() / err() helpers in views.py.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Call DRF's default handler first to get the standard Response,
    then reformat it to match our API envelope.
    """
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data

        # DRF returns either a dict or a list; normalise both
        if isinstance(data, dict):
            # Extract the human-readable message
            detail = data.get("detail", "")
            if not detail:
                # Flatten field errors into a single string
                parts = []
                for field, errors in data.items():
                    if isinstance(errors, list):
                        parts.append(f"{field}: {'; '.join(str(e) for e in errors)}")
                    else:
                        parts.append(str(errors))
                detail = " | ".join(parts)
        else:
            detail = str(data)

        error_msg = _status_to_message(response.status_code)

        response.data = {
            "ok":     False,
            "error":  error_msg,
            "detail": detail,
        }

    return response


def _status_to_message(status_code: int) -> str:
    mapping = {
        400: "Bad request",
        401: "Authentication required",
        403: "Permission denied",
        404: "Not found",
        405: "Method not allowed",
        409: "Conflict",
        429: "Too many requests",
        500: "Internal server error",
        503: "Service unavailable",
    }
    return mapping.get(status_code, f"HTTP {status_code}")