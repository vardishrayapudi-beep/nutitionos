from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import Patient, generate_patient_code


class PatientCodeTaken(APIException):
    status_code = 409
    default_detail = "That patient code is already used in this clinic."
    default_code = "patient_code_taken"


def create_patient(*, clinic, created_by, data: dict) -> Patient:
    """Create a patient; generates a clinic-unique code unless the clinic supplied one."""
    supplied_code = data.pop("patient_code", "") or ""
    if supplied_code:
        try:
            with transaction.atomic():
                return Patient.objects.create(clinic=clinic, created_by=created_by,
                                              patient_code=supplied_code, **data)
        except IntegrityError:
            raise PatientCodeTaken()
    for _ in range(10):
        try:
            with transaction.atomic():
                return Patient.objects.create(clinic=clinic, created_by=created_by,
                                              patient_code=generate_patient_code(), **data)
        except IntegrityError:
            continue
    raise APIException("Could not allocate a patient code, please retry.")


def assign_doctor(patient: Patient, membership) -> Patient:
    patient.assigned_doctor = membership
    patient.save(update_fields=["assigned_doctor", "updated_at"])
    return patient


def record_consent(patient: Patient, *, status: str, version: str, method: str,
                   ai_photo_analysis: bool | None = None) -> Patient:
    """Record the patient's consent decision. Granting needs a notice version; withdrawing also
    switches off everything that depended on consent."""
    if status == Patient.Consent.GRANTED:
        if not version:
            raise serializers.ValidationError({"version": ["The notice version the patient agreed to is required."]})
        patient.consent_status = Patient.Consent.GRANTED
        patient.consented_at = timezone.now()
        patient.consent_version = version
        patient.consent_method = method
    elif status == Patient.Consent.WITHDRAWN:
        patient.consent_status = Patient.Consent.WITHDRAWN
        patient.ai_photo_analysis_consent = False
        patient.doctor_monitoring_enabled = False
    else:
        raise serializers.ValidationError({"status": ["Use 'granted' or 'withdrawn'."]})
    if ai_photo_analysis is not None and status == Patient.Consent.GRANTED:
        patient.ai_photo_analysis_consent = ai_photo_analysis
    patient.save()
    return patient
