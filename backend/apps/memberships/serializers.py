from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Invitation, Membership

User = get_user_model()


class MemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "status", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    # 'invited' is not a state an admin can move someone into.
    status = serializers.ChoiceField(
        choices=[(Membership.Status.ACTIVE, "Active"), (Membership.Status.SUSPENDED, "Suspended")],
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide role and/or status.")
        return attrs


class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "status", "expires_at", "created_at"]
        read_only_fields = ["id", "status", "expires_at", "created_at"]

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(max_length=128, required=False, trim_whitespace=False, write_only=True)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
