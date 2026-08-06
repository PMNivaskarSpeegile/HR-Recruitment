"""
Consistent API error responses + logging of unexpected failures.

WHY: a frontend is far easier to build when EVERY error looks the same. DRF's
default error shapes vary; we wrap them into one predictable envelope:

    { "success": false, "status_code": 400, "error": { ...details... } }

Unhandled (500) errors are logged with a full traceback and, in production,
returned as a generic message so we never leak internals to the client.
"""
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("ats")


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    view = context.get("view")

    if response is not None:
        response.data = {
            "success": False,
            "status_code": response.status_code,
            "error": response.data,
        }
        return response

    # response is None => an exception DRF doesn't handle (i.e. a real 500).
    logger.exception("Unhandled server error in %s: %s", view, exc)

    if settings.DEBUG:
        # Let Django's debug page surface the traceback during development.
        return None

    return Response(
        {
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error": {"detail": "An internal server error occurred."},
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
