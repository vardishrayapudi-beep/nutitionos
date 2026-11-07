from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit import service as audit
from apps.notifications import email as mail

from . import services
from .mixins import ClinicScopedQuerysetMixin
from .models import Invitation, Membership
from .permissions import HasActiveClinicMembership, IsClinicAdmin
from .serializers import (
    InvitationSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
)
from .tenancy import get_request_clinic, get_request_membership

ROLE_LABELS = dict(Membership.Role.choices)


class MemberViewSet(ClinicScopedQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Members of the caller's clinic. Everyone can look; only admins can change roles/status.

    There is no DELETE: access is withdrawn by suspending, which keeps the history.
    """

    queryset = Membership.objects.select_related("user").all()
    serializer_class = MemberSerializer
    filterset_fields = ["role", "status"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasActiveClinicMembership()]
        return [IsClinicAdmin()]

    def get_serializer_class(self):
        return MemberUpdateSerializer if self.action == "partial_update" else MemberSerializer

    @extend_schema(request=MemberUpdateSerializer, responses=MemberSerializer)
    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        serializer = MemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated, (old_role, old_status) = services.update_membership(
            membership=membership,
            role=serializer.validated_data.get("role"),
            status=serializer.validated_data.get("status"),
        )
        if updated.role != old_role:
            audit.record(action="member.role_changed", request=request, target=updated,
                         old_role=old_role, new_role=updated.role)
        if updated.status != old_status:
            audit.record(action="member.status_changed", request=request, target=updated,
                         old_status=old_status, new_status=updated.status)
        return Response(MemberSerializer(updated).data)


class InvitationViewSet(ClinicScopedQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                        mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Admin-only. Invitations are delivered by email; the token is never returned by the API."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    permission_classes = [IsClinicAdmin]
    filterset_fields = ["role"]

    def perform_create(self, serializer):
        clinic = get_request_clinic(self.request)
        membership = get_request_membership(self.request)
        invitation, raw_token = services.create_invitation(
            clinic=clinic, invited_by=self.request.user,
            email=serializer.validated_data["email"], role=serializer.validated_data["role"],
        )
        serializer.instance = invitation
        self._email(invitation, raw_token, membership)
        audit.record(action="invitation.created", request=self.request, target=invitation,
                     role=invitation.role)

    def _email(self, invitation, raw_token, membership):
        mail.send_invitation_email(
            to_email=invitation.email, clinic_name=invitation.clinic.name,
            inviter_name=membership.user.get_full_name(), role_label=ROLE_LABELS[invitation.role],
            raw_token=raw_token, valid_days=settings.INVITATION_VALID_DAYS,
        )

    def perform_destroy(self, instance):
        services.revoke_invitation(instance)
        audit.record(action="invitation.revoked", request=self.request, target=instance)

    @extend_schema(request=None, responses={202: OpenApiResponse(description="New email sent")})
    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        old = self.get_object()
        invitation, raw_token = services.reissue_invitation(old)
        self._email(invitation, raw_token, get_request_membership(request))
        audit.record(action="invitation.resent", request=request, target=invitation)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_202_ACCEPTED)
