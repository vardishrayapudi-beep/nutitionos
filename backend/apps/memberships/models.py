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

    @property
    def grants_access(self) -> bool:
        """True only for an ACTIVE membership in an ACTIVE clinic.

        Must stay identical to ``tenancy.active_memberships_for`` (a test enforces this).
        """
        return self.is_active_member and self.clinic.is_active

    def __str__(self):
        return f"{self.user} @ {self.clinic} ({self.role}, {self.status})"


class Invitation(TimeStampedUUIDModel):
    """An offer to join a clinic, delivered ONLY by email.

    The raw token exists in exactly one place - the invitee's inbox. We store just its SHA-256
    hash, so a database leak cannot be turned into working invitations, and the API never returns
    the token (otherwise an admin could accept an invitation themselves and claim someone else's
    email address).
    """

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # At most one open invitation per clinic + email (re-inviting revokes the old one).
            models.UniqueConstraint(
                fields=["clinic", "email"],
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="memberships_one_open_invitation_per_email",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["clinic_admin", "doctor", "staff"]),
                name="memberships_invitation_role_valid",
            ),
        ]

    @property
    def status(self) -> str:
        from django.utils import timezone

        if self.accepted_at:
            return "accepted"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "pending"

    def __str__(self):
        return f"Invitation({self.email} -> {self.clinic_id}, {self.status})"
