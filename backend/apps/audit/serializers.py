from rest_framework import serializers

from apps.memberships.serializers import MemberUserSerializer

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = MemberUserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "actor", "actor_type", "action", "target_type", "target_id",
                  "metadata", "ip_address", "request_id"]
        read_only_fields = fields
