from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Clinic


class ClinicSelfSerializer(serializers.ModelSerializer):
    """The caller's own clinic. Only a few fields may be changed; the slug never changes."""

    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = ["id", "name", "slug", "email", "phone", "branding_mode", "is_active", "my_role"]
        read_only_fields = ["id", "slug", "is_active", "my_role"]

    @extend_schema_field(serializers.CharField())
    def get_my_role(self, clinic):
        return self.context["membership"].role
