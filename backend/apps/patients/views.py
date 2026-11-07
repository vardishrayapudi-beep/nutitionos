from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import service as audit
from apps.memberships.mixins import ClinicScopedQuerysetMixin
from apps.memberships.permissions import HasActiveClinicMembership, IsClinicAdminOrDoctor
from apps.memberships.tenancy import get_request_clinic

from . import services
from .models import Patient
from .serializers import (
    AssignDoctorSerializer,
    ConsentSerializer,
    MonitoringSerializer,
    PatientSerializer,
    PatientWriteSerializer,
)


class PatientViewSet(ClinicScopedQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Patients of the caller's clinic. Any active member can read and register patients;
    assigning doctors and switching on doctor monitoring needs an admin or doctor.

    There is no DELETE: patients are archived (``is_active=false``) so clinical history survives.
    """

    queryset = Patient.objects.select_related("assigned_doctor__user").all()
    serializer_class = PatientSerializer
    filterset_fields = ["assigned_doctor", "consent_status", "is_active"]
    search_fields = ["first_name", "last_name", "patient_code", "phone"]
    ordering_fields = ["last_name", "first_name", "created_at", "patient_code"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("assign_doctor", "monitoring"):
            return [IsClinicAdminOrDoctor()]
        return [HasActiveClinicMembership()]

    def get_queryset(self):
        queryset = super().get_queryset()
        # The list hides archived patients unless the caller filters on is_active explicitly.
        if self.action == "list" and "is_active" not in self.request.query_params:
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return PatientWriteSerializer
        return PatientSerializer

    @extend_schema(request=PatientWriteSerializer, responses={201: PatientSerializer})
    def create(self, request, *args, **kwargs):
        serializer = PatientWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = services.create_patient(
            clinic=get_request_clinic(request), created_by=request.user, data=dict(serializer.validated_data)
        )
        audit.record(action="patient.created", request=request, target=patient)
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        patient = self.get_object()
        audit.record(action="patient.viewed", request=request, target=patient)
        return Response(PatientSerializer(patient).data)

    @extend_schema(request=PatientWriteSerializer, responses=PatientSerializer)
    def partial_update(self, request, *args, **kwargs):
        patient = self.get_object()
        serializer = PatientWriteSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changed = sorted(f for f, v in serializer.validated_data.items() if getattr(patient, f) != v)
        patient = serializer.save()
        if changed:
            audit.record(action="patient.updated", request=request, target=patient, fields=changed)
            if "is_active" in changed:
                audit.record(action="patient.archived" if not patient.is_active else "patient.restored",
                             request=request, target=patient)
        return Response(PatientSerializer(patient).data)

    @extend_schema(request=AssignDoctorSerializer, responses=PatientSerializer)
    @action(detail=True, methods=["post"], url_path="assign-doctor")
    def assign_doctor(self, request, pk=None):
        patient = self.get_object()
        serializer = AssignDoctorSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        doctor = serializer.validated_data["doctor"]
        services.assign_doctor(patient, doctor)
        audit.record(action="patient.doctor_assigned", request=request, target=patient,
                     doctor_membership_id=str(doctor.id) if doctor else None)
        return Response(PatientSerializer(patient).data)

    @extend_schema(request=ConsentSerializer, responses=PatientSerializer)
    @action(detail=True, methods=["post"])
    def consent(self, request, pk=None):
        patient = self.get_object()
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.record_consent(patient, status=data["status"], version=data["version"],
                                method=data["method"], ai_photo_analysis=data.get("ai_photo_analysis"))
        audit.record(action="patient.consent_recorded", request=request, target=patient,
                     status=patient.consent_status, version=patient.consent_version,
                     method=data["method"], ai_photo_analysis=patient.ai_photo_analysis_consent)
        return Response(PatientSerializer(patient).data)

    @extend_schema(request=MonitoringSerializer, responses=PatientSerializer)
    @action(detail=True, methods=["post"])
    def monitoring(self, request, pk=None):
        patient = self.get_object()
        serializer = MonitoringSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enabled = serializer.validated_data["enabled"]
        if enabled and not patient.has_consent:
            raise ValidationError({"enabled": ["Doctor monitoring needs the patient's consent first."]})
        patient.doctor_monitoring_enabled = enabled
        patient.save(update_fields=["doctor_monitoring_enabled", "updated_at"])
        audit.record(action="patient.monitoring_changed", request=request, target=patient, enabled=enabled)
        return Response(PatientSerializer(patient).data)
