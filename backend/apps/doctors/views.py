from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response

from apps.audit import service as audit
from apps.memberships.models import Membership
from apps.memberships.permissions import HasActiveClinicMembership, IsClinicDoctor
from apps.memberships.tenancy import get_request_clinic

from .models import DoctorProfile
from .serializers import DoctorProfileSerializer


class ProfileExists(APIException):
    status_code = 409
    default_detail = "You already have a doctor profile."
    default_code = "profile_exists"


class DoctorProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Doctor profiles of the caller's clinic.

    Tenancy: a profile has no clinic column (it belongs to the person), so visibility is derived
    from membership - only doctors with an ACTIVE doctor membership in the caller's clinic.
    Only the owner can create/edit their own profile.
    """

    tenant_scope_note = "via membership: doctors with an active doctor membership in the caller's clinic"
    serializer_class = DoctorProfileSerializer
    queryset = DoctorProfile.objects.all()
    filterset_fields = ["verification_status"]
    search_fields = ["user__first_name", "user__last_name", "specialization"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsClinicDoctor()]
        return [HasActiveClinicMembership()]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        clinic = get_request_clinic(self.request)
        # ONE filter() call so all three conditions must hold for the SAME membership row.
        return queryset.filter(
            user__memberships__clinic=clinic,
            user__memberships__role=Membership.Role.DOCTOR,
            user__memberships__status=Membership.Status.ACTIVE,
        ).distinct()

    def create(self, request, *args, **kwargs):
        if DoctorProfile.objects.filter(user=request.user).exists():
            raise ProfileExists()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(user=request.user)
        audit.record(action="doctor_profile.created", request=request, target=profile)
        return Response(self.get_serializer(profile).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        profile = self.get_object()
        if profile.user_id != request.user.pk:
            raise PermissionDenied("You can only edit your own doctor profile.")
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        number_changed = (
            "registration_number" in serializer.validated_data
            and serializer.validated_data["registration_number"] != profile.registration_number
        )
        extra = {}
        if number_changed:  # a different number needs fresh verification
            extra.update(verification_status=DoctorProfile.Verification.UNVERIFIED,
                         verified_at=None, verified_by=None)
        profile = serializer.save(**extra)
        audit.record(action="doctor_profile.updated", request=request, target=profile,
                     fields=sorted(serializer.validated_data), verification_reset=number_changed)
        return Response(self.get_serializer(profile).data)
