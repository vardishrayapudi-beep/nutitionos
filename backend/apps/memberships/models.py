from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Membership(TimeStampedUUIDModel):
    """Connects a User to a Clinic with a role. This is the ONLY source of tenant access.

    A person may belong to several clinics (e.g. a visiting doctor), with a different role
    in each - which is why role and status live here and not on the User.
    """

    class Role(models.TextChoices):
        CLINIC_ADMIN = "clinic_admin", "Clinic administrator"
        DOCTOR = "doctor", "Doctor"
        STAFF = "staff", "Clinic staff"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited (not yet accepted)"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended (access revoked)"

    # PROTECT: users and clinics are deactivated, never deleted, so the history of who had
    # access to what survives (healthcare audit requirement).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    # Default is the least-privileged state: access must be granted deliberately.
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "clinic"], name="memberships_one_per_user_per_clinic"),
            models.CheckConstraint(
                condition=models.Q(role__in=["clinic_admin", "doctor", "staff"]),
                name="memberships_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["invited", "active", "suspended"]),
                name="memberships_status_valid",
            ),
        ]

    @property
    def is_active_member(self) -> bool:
        return self.status == self.Status.ACTIVE

    def __str__(self):
        return f"{self.user} @ {self.clinic} ({self.role}, {self.status})"
