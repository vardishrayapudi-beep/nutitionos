from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from .tenancy import get_request_clinic


class ClinicScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A foreign-key field that only accepts objects belonging to the caller's clinic.

    Use it on write serializers for every relation to a clinic-owned model, e.g. a
    prescription's ``patient``. An id from another clinic is rejected with the same
    "does not exist" error as a random id, so cross-clinic ids cannot be probed.
    """

    def __init__(self, *args, clinic_field="clinic", **kwargs):
        self.clinic_field = clinic_field
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if queryset is None:
            return None
        request = self.context.get("request")
        if request is None:
            raise ImproperlyConfigured(
                "ClinicScopedPrimaryKeyRelatedField needs the request in the serializer context."
            )
        return queryset.filter(**{self.clinic_field: get_request_clinic(request)})
