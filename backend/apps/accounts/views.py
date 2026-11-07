from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.clinics.services import (
    EmailAlreadyRegistered,
    RegistrationUnavailable,
    register_clinic,
)
from apps.memberships.models import Membership

from .serializers import (
    LogoutSerializer,
    MeSerializer,
    RegisterClinicSerializer,
    RegistrationResponseSerializer,
)


class ServiceBusy(APIException):
    status_code = 503
    default_detail = "The service is busy. Please try again in a moment."
    default_code = "service_busy"


class RegisterClinicView(APIView):
    """Create a clinic workspace plus its first administrator. Public, strictly rate-limited."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    @extend_schema(
        summary="Register a clinic and its first administrator",
        request=RegisterClinicSerializer,
        responses={201: RegistrationResponseSerializer},
    )
    def post(self, request):
        serializer = RegisterClinicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = register_clinic(clinic_data=data["clinic"], admin_data=data["admin"])
        except EmailAlreadyRegistered:
            # Two sign-ups with the same email raced past the serializer's check.
            raise serializers.ValidationError(
                {"admin": {"email": ["An account with this email already exists."]}}
            )
        except RegistrationUnavailable:
            raise ServiceBusy()

        refresh = RefreshToken.for_user(result.user)
        body = RegistrationResponseSerializer(
            {
                "user": result.user,
                "clinic": result.clinic,
                "membership": result.membership,
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            }
        ).data
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """Exchange email + password for an access token (15 min) and a refresh token (7 days)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"


class TokenRefreshRotatingView(TokenRefreshView):
    """Exchange a refresh token for a new access token. The old refresh token is retired
    (rotation + blacklist), so a stolen token is usable at most once."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_token_refresh"


class LogoutView(APIView):
    """Revoke a refresh token. Idempotent: an already-revoked or invalid token also gives 204,
    because the end state - that token is unusable - is what the caller wants."""

    authentication_classes = []  # the refresh token itself is the credential
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_logout"

    @extend_schema(
        summary="Log out (revoke a refresh token)",
        request=LogoutSerializer,
        responses={204: OpenApiResponse(description="Token revoked (or was already unusable)")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Who am I, and which clinics can I act for?

    Deliberately does NOT resolve a clinic: it must work for users who have no membership yet,
    and it is how the frontend learns which ``X-Clinic-Id`` values are valid.
    """

    @extend_schema(summary="Current user and their clinic memberships", responses=MeSerializer)
    def get(self, request):
        user = request.user
        memberships = list(
            Membership.objects.filter(user=user).select_related("clinic").order_by("created_at")
        )
        usable = sum(1 for membership in memberships if membership.grants_access)
        body = MeSerializer(
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "memberships": memberships,
                "needs_clinic_selection": usable > 1,
            }
        ).data
        return Response(body)
