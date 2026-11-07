from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.memberships.models import Membership

User = get_user_model()


# --------------------------------------------------------------------------------------------
# Registration (input)
# --------------------------------------------------------------------------------------------
class ClinicRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)  # blank / whitespace-only is rejected
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")


class AdminRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    # max_length also stops absurdly long passwords being used to burn CPU in the hasher.
    password = serializers.CharField(
        max_length=128, write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists.", code="email_taken"
            )
        return value

    def validate(self, attrs):
        # Run Django's password policy (length, common passwords, similarity to name/email...).
        candidate = User(
            email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"]
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class RegisterClinicSerializer(serializers.Serializer):
    """Unknown fields (is_staff, role, slug, is_active, ...) are silently ignored, so a client
    cannot grant itself privileges by adding extra keys."""

    clinic = ClinicRegistrationSerializer()
    admin = AdminRegistrationSerializer()


# --------------------------------------------------------------------------------------------
# Output shapes (also drive the OpenAPI documentation)
# --------------------------------------------------------------------------------------------
class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]
        read_only_fields = fields


class ClinicSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ["id", "name", "slug", "branding_mode", "is_active"]
        read_only_fields = fields


class ClinicDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ["id", "name", "slug", "email", "phone", "branding_mode", "is_active"]
        read_only_fields = fields


class MembershipSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "role", "status"]
        read_only_fields = fields


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class RegistrationResponseSerializer(serializers.Serializer):
    user = UserSummarySerializer()
    clinic = ClinicDetailSerializer()
    membership = MembershipSummarySerializer()
    tokens = TokenPairSerializer()


class MeMembershipSerializer(serializers.ModelSerializer):
    clinic = ClinicSummarySerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "role", "status", "clinic"]
        read_only_fields = fields


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    memberships = MeMembershipSerializer(many=True)
    needs_clinic_selection = serializers.BooleanField()


# --------------------------------------------------------------------------------------------
# Logout (input)
# --------------------------------------------------------------------------------------------
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)
