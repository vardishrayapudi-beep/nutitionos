from drf_spectacular.utils import extend_schema
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.memberships.permissions import HasActiveClinicMembership, IsClinicAdmin
from apps.memberships.tenancy import get_request_membership

from .serializers import ClinicSelfSerializer


class ClinicMeView(APIView):
    """The caller's active clinic. Any member can read it; only an administrator can edit it."""

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [HasActiveClinicMembership()]
        return [IsClinicAdmin()]

    @extend_schema(responses=ClinicSelfSerializer)
    def get(self, request):
        membership = get_request_membership(request)
        return Response(ClinicSelfSerializer(membership.clinic, context={"membership": membership}).data)

    @extend_schema(request=ClinicSelfSerializer, responses=ClinicSelfSerializer)
    def patch(self, request):
        membership = get_request_membership(request)
        serializer = ClinicSelfSerializer(
            membership.clinic, data=request.data, partial=True, context={"membership": membership}
        )
        serializer.is_valid(raise_exception=True)
        changed = sorted(f for f, v in serializer.validated_data.items() if getattr(membership.clinic, f) != v)
        serializer.save()
        if changed:
            audit.record(action="clinic.updated", request=request, target=membership.clinic, fields=changed)
        return Response(serializer.data)
