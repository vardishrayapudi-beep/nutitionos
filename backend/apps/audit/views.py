import django_filters
from rest_framework import mixins, viewsets

from apps.memberships.mixins import ClinicScopedQuerysetMixin
from apps.memberships.permissions import IsClinicAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["action", "actor_type", "target_type", "target_id"]


class AuditLogViewSet(ClinicScopedQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """Read-only audit trail of the caller's clinic. Administrators only."""

    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsClinicAdmin]
    filterset_class = AuditLogFilter
    ordering_fields = ["created_at"]
