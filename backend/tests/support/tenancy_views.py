"""A throw-away clinic-scoped API used only by tests, built on Membership (which has a ``clinic``
foreign key). It exercises the multi-tenancy plumbing exactly as real endpoints will use it."""
from rest_framework import serializers, viewsets

from apps.memberships.mixins import ClinicScopedQuerysetMixin
from apps.memberships.models import Membership
from apps.memberships.permissions import HasActiveClinicMembership, IsClinicAdmin


class MembershipTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "user", "clinic", "role", "status"]
        read_only_fields = ["id", "clinic"]  # clinic comes from the server, never the client


class MembershipTestViewSet(ClinicScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipTestSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasActiveClinicMembership()]
        return [IsClinicAdmin()]
