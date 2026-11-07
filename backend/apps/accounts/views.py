from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.audit import service as audit
from apps.notifications import email as mail
from apps.clinics.services import (
    EmailAlreadyRegistered,
    RegistrationUnavailable,
    register_clinic,
)
from apps.memberships import services as membership_services
from apps.memberships.models import Membership
from apps.memberships.serializers import InvitationAcceptSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication

from . import services, tokens
from .serializers import (
    LogoutSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterClinicSerializer,
    RegistrationResponseSerializer,
    VerifyEmailSerializer,
)

User = get_user_model()


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

        audit.record(action="clinic.registered", request=request, clinic=result.clinic,
                     actor=result.user, target=result.clinic)
        mail.send_verification_email(result.user, tokens.make_email_verification_token(result.user))

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

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        audit.record(action="auth.login", request=request, actor=serializer.user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


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
                "email_verified": user.is_email_verified,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "memberships": memberships,
                "needs_clinic_selection": usable > 1,
            }
        ).data
        return Response(body)


class VerifyEmailView(APIView):
    """Confirm an email address using the link sent by email."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_verify_email"

    @extend_schema(
        summary="Verify email address",
        request=VerifyEmailSerializer,
        responses={200: OpenApiResponse(description="Email verified")},
    )
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.verify_email(serializer.validated_data["token"])
        if user is None:
            raise serializers.ValidationError(
                {"token": ["This verification link is invalid or has expired."]}, code="invalid_token"
            )
        audit.record(action="auth.email_verified", request=request, actor=user)
        return Response({"verified": True})


class ResendVerificationView(APIView):
    """Send a fresh verification email to the logged-in user (no-op if already verified)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_verify_email"

    @extend_schema(summary="Resend verification email", request=None,
                   responses={202: OpenApiResponse(description="Email queued")})
    def post(self, request):
        user = request.user
        if not user.is_email_verified:
            mail.send_verification_email(user, tokens.make_email_verification_token(user))
        return Response({"detail": "If your email is not yet verified, a new link has been sent."},
                        status=status.HTTP_202_ACCEPTED)


class PasswordResetRequestView(APIView):
    """Ask for a password-reset email. Always answers the same way (no account enumeration)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    @extend_schema(summary="Request a password reset email", request=PasswordResetRequestSerializer,
                   responses={202: OpenApiResponse(description="Always returned")})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_email(serializer.validated_data["email"])
        user = User.objects.filter(email=email, is_active=True).first()
        if user is not None and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            mail.send_password_reset_email(user, uid, default_token_generator.make_token(user))
            audit.record(action="auth.password_reset_requested", request=request, actor=user)
        return Response({"detail": "If an account exists for that email, a reset link has been sent."},
                        status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    """Set a new password using the emailed link; signs the user out everywhere."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    @extend_schema(summary="Complete a password reset", request=PasswordResetConfirmSerializer,
                   responses={200: OpenApiResponse(description="Password changed")})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = None
        try:
            user = User.objects.filter(pk=force_str(urlsafe_base64_decode(data["uid"])), is_active=True).first()
        except (ValueError, TypeError, OverflowError, UnicodeDecodeError, DjangoValidationError):
            user = None  # uid was not valid base64 / not a valid user id
        if user is None or not default_token_generator.check_token(user, data["token"]):
            raise serializers.ValidationError(
                {"token": ["This reset link is invalid or has expired."]}, code="invalid_token"
            )

        from .serializers import _check_new_password
        try:
            _check_new_password(data["new_password"], user)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.detail})

        user.set_password(data["new_password"])
        if user.email_verified_at is None:  # receiving the email proves ownership
            user.email_verified_at = timezone.now()
        user.save()
        services.revoke_all_sessions(user)
        audit.record(action="auth.password_reset_completed", request=request, actor=user)
        return Response({"detail": "Your password has been changed. Please log in."})


class PasswordChangeView(APIView):
    """Change password while logged in. Other sessions are revoked; this device gets new tokens."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_change"

    @extend_schema(summary="Change password", request=PasswordChangeSerializer,
                   responses={200: OpenApiResponse(description="New token pair")})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        services.revoke_all_sessions(user)
        audit.record(action="auth.password_changed", request=request, actor=user)
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class AcceptInvitationView(APIView):
    """Accept a clinic invitation using the token from the email.

    Public, but a valid access token is honoured: people who already have an account must be logged
    in as the invited address; new people choose a password here and are logged straight in.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_invitation_accept"

    @extend_schema(summary="Accept a clinic invitation", request=InvitationAcceptSerializer,
                   responses={201: OpenApiResponse(description="Joined")})
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership, user, created_user = membership_services.accept_invitation(
            raw_token=data["token"],
            acting_user=request.user if request.user.is_authenticated else None,
            new_account={k: data.get(k) for k in ("password", "first_name", "last_name")},
        )
        audit.record(action="invitation.accepted", request=request, clinic=membership.clinic,
                     actor=user, target=membership, role=membership.role)
        body = {
            "membership": {"id": str(membership.id), "role": membership.role, "status": membership.status},
            "clinic": {"id": str(membership.clinic.id), "name": membership.clinic.name,
                       "slug": membership.clinic.slug},
            "tokens": None,
        }
        if created_user:
            refresh = RefreshToken.for_user(user)
            body["tokens"] = {"access": str(refresh.access_token), "refresh": str(refresh)}
        return Response(body, status=status.HTTP_201_CREATED)
