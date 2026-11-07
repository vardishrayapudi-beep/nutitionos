from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedUUIDModel


class DoctorProfile(TimeStampedUUIDModel):
    """A doctor's professional identity. Belongs to the PERSON, not to a clinic.

    - Only the doctor can edit it (a clinic admin must not be able to change the registration
      number a visiting doctor also uses at another clinic).
    - ``verification_status`` is set only by platform operators (Django admin) after checking
      the registration number with the issuing medical council. Changing the registration
      number sends the profile back to ``unverified``.
    """

    class Verification(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Verification in progress"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="doctor_profile")
    specialization = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50)
    verification_status = models.CharField(
        max_length=20, choices=Verification.choices, default=Verification.UNVERIFIED
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(verification_status__in=["unverified", "pending", "verified", "rejected"]),
                name="doctors_verification_status_valid",
            ),
            # Verified profiles must say when and by whom.
            models.CheckConstraint(
                condition=~models.Q(verification_status="verified") | models.Q(verified_at__isnull=False),
                name="doctors_verified_has_timestamp",
            ),
        ]

    @property
    def is_verified(self) -> bool:
        return self.verification_status == self.Verification.VERIFIED

    def __str__(self):
        return f"Dr {self.user.get_full_name() or self.user.email} ({self.verification_status})"


def is_verified_doctor(user) -> bool:
    profile = getattr(user, "doctor_profile", None)
    return bool(profile and profile.is_verified)
