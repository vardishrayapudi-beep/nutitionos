from rest_framework import serializers

from apps.memberships.serializers import MemberUserSerializer

from .models import DoctorProfile


class DoctorProfileSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ["id", "user", "specialization", "registration_number",
                  "verification_status", "verified_at"]
        read_only_fields = ["id", "user", "verification_status", "verified_at"]

    def validate_specialization(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_registration_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value
