import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Liveness/readiness probe for uptime monitors and load balancers.

    Public by design, so it returns nothing beyond up/down status.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []  # monitors must never be rate-limited

    @extend_schema(
        summary="Service health check",
        responses={200: OpenApiResponse(description="Service and database are up"),
                   503: OpenApiResponse(description="Database unreachable")},
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            logger.exception("Health check: database unreachable")
            return Response({"status": "unavailable", "database": "down"}, status=503)
        return Response({"status": "ok", "database": "up"})
