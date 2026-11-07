from .permissions import HasActiveClinicMembership
from .tenancy import get_request_clinic


class ClinicScopedQuerysetMixin:
    """Put FIRST in the bases of any DRF view over a model that has a ``clinic`` foreign key.

        class PatientViewSet(ClinicScopedQuerysetMixin, viewsets.ModelViewSet):
            queryset = Patient.objects.all()

    - Every read is filtered to the caller's active clinic, so another clinic's rows are
      simply "not found" (404, never 403, so their existence is not revealed).
    - Every create stamps the clinic from the server-side membership; a ``clinic`` value in the
      request body is ignored as long as the serializer treats the field as read-only.
    - The clinic is resolved here even if a developer replaces ``permission_classes``, so
      forgetting the permission class cannot silently disable tenant filtering.
    """

    permission_classes = [HasActiveClinicMembership]
    clinic_field = "clinic"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):  # drf-spectacular schema generation
            return queryset.none()
        return queryset.filter(**{self.clinic_field: get_request_clinic(self.request)})

    def perform_create(self, serializer):
        serializer.save(**{self.clinic_field: get_request_clinic(self.request)})
