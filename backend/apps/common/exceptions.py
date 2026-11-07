"""One consistent error envelope for the whole API.

Every error response looks like:

    {"error": {"code": "<machine_code>", "message": "<human text>", "details": <null | object>}}

so the React frontend can handle failures in a single place.
"""
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django returns a generic 500 (no stack trace leaked)

    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        message = "The submitted data is invalid."
        details = data
    elif isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        code = getattr(detail, "code", "error")
        message = str(detail)
        details = None
    else:
        code = "error"
        message = "The request could not be completed."
        details = data

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
