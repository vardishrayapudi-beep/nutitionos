from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.common.validators import POSTAL_CODE_RE, normalize_phone
from apps.memberships.fields import ClinicScopedPrimaryKeyRelatedField
from apps.memberships.models import Membership

from .models import MEASUREMENT_TYPES, Patient


class AssignedDoctorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "name"]
        read_only_fields = fields

    def get_name(self, membership) -> str:
        return membership.user.get_full_name() or membership.user.email


class PatientSerializer(serializers.ModelSerializer):
    assigned_doctor = AssignedDoctorSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "patient_code", "first_name", "last_name", "date_of_birth", "phone", "email",
            "postal_code", "assigned_doctor", "consent_status", "consented_at", "consent_version",
            "consent_method", "ai_photo_analysis_consent", "doctor_monitoring_enabled",
            "tracked_measurements", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PatientWriteSerializer(serializers.ModelSerializer):
    """Input for create/update. Consent, monitoring and doctor assignment have their own
    endpoints so each change is deliberate and audited."""

    patient_code = serializers.RegexField(r"^[A-Za-z0-9_-]{1,32}$", required=False, allow_blank=True)
    tracked_measurements = serializers.ListField(
        child=serializers.ChoiceField(choices=MEASUREMENT_TYPES), required=False, allow_empty=True
    )

    class Meta:
        model = Patient
        fields = ["patient_code", "first_name", "last_name", "date_of_birth", "phone", "email",
                  "postal_code", "tracked_measurements", "is_active"]
        extra_kwargs = {"first_name": {"trim_whitespace": True}, "last_name": {"trim_whitespace": True},
                        "email": {"required": False, "allow_blank": True},
                        "postal_code": {"required": False, "allow_blank": True}}

    def validate_patient_code(self, value):
        return value.strip().upper()

    def validate_date_of_birth(self, value):
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if today.year - value.year > 120:
            raise serializers.ValidationError("Please check the date of birth.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def validate_postal_code(self, value):
        if value and not POSTAL_CODE_RE.match(value):
            raise serializers.ValidationError("Enter a valid 6-digit PIN code.")
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate_tracked_measurements(self, value):
        return sorted(set(value))

    def validate(self, attrs):
        if self.instance is not None and "patient_code" in attrs and attrs["patient_code"] != self.instance.patient_code:
            raise serializers.ValidationError({"patient_code": ["A patient code cannot be changed."]})
        return attrs


class AssignDoctorSerializer(serializers.Serializer):
    # Only ACTIVE doctor memberships of the caller's own clinic are accepted.
    doctor = ClinicScopedPrimaryKeyRelatedField(
        queryset=Membership.objects.filter(role=Membership.Role.DOCTOR, status=Membership.Status.ACTIVE)
        .select_related("user"),
        allow_null=True,
    )


class ConsentSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("granted", "granted"), ("withdrawn", "withdrawn")])
    version = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    method = serializers.ChoiceField(choices=Patient.ConsentMethod.choices, default=Patient.ConsentMethod.IN_CLINIC)
    ai_photo_analysis = serializers.BooleanField(required=False)


class MonitoringSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
