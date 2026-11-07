import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.models import TimeStampedUUIDModel

# No 0/O/1/I/L: patient codes are read aloud and written by hand.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_patient_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


MEASUREMENT_TYPES = ["weight_kg", "waist_cm", "hip_cm", "height_cm", "blood_pressure_systolic",
                     "blood_pressure_diastolic", "blood_glucose_mgdl"]


def default_tracked_measurements():
    return ["weight_kg"]


class Patient(TimeStampedUUIDModel):
    """A person under a clinic's care. Every patient belongs to exactly one clinic."""

    class Consent(models.TextChoices):
        PENDING = "pending", "Pending"
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class ConsentMethod(models.TextChoices):
        IN_CLINIC = "in_clinic", "Recorded by clinic (e.g. signed form)"
        PORTAL = "patient_portal", "Given by the patient in the portal"

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="patients")
    # Clinic-scoped: two clinics may both have patient "A1B2C3D4".
    patient_code = models.CharField(max_length=32)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=16)  # E.164
    email = models.EmailField(blank=True)
    postal_code = models.CharField(max_length=6, blank=True)  # used to look up nearby groceries
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    # Through Membership so "this doctor really works at this clinic" is checkable.
    assigned_doctor = models.ForeignKey(
        "memberships.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_patients"
    )

    # --- consent (explicit, versioned, never pre-ticked) ---
    consent_status = models.CharField(max_length=12, choices=Consent.choices, default=Consent.PENDING)
    consented_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)
    consent_method = models.CharField(max_length=16, choices=ConsentMethod.choices, blank=True)
    ai_photo_analysis_consent = models.BooleanField(default=False)
    # Whether the clinic may see what the patient logs (check-ins, photos, AI estimates...).
    doctor_monitoring_enabled = models.BooleanField(default=False)

    tracked_measurements = ArrayField(models.CharField(max_length=40), default=default_tracked_measurements, blank=True)
    is_active = models.BooleanField(default=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "patient_code"], name="patients_code_unique_per_clinic"),
            models.CheckConstraint(
                condition=models.Q(consent_status__in=["pending", "granted", "withdrawn"]),
                name="patients_consent_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(consent_status="granted") | models.Q(consented_at__isnull=False),
                name="patients_granted_consent_has_timestamp",
            ),
        ]
        indexes = [models.Index(fields=["clinic", "last_name", "first_name"], name="patients_clinic_name_idx")]

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_consent(self) -> bool:
        return self.consent_status == self.Consent.GRANTED

    def __str__(self):
        return f"{self.patient_code} ({self.clinic_id})"
