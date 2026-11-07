"""Membership and invitation rules. Views call these; they own the business logic."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.clinics.models import Clinic

from .errors import (
    AlreadyMember,
    InvitationInvalid,
    LastAdminError,
    LoginRequired,
    WrongAccount,
)
from .models import Invitation, Membership

User = get_user_model()


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


# --------------------------------------------------------------------------------------------
# Invitations
# --------------------------------------------------------------------------------------------
def create_invitation(*, clinic: Clinic, invited_by, email: str, role: str):
    """Create an invitation (revoking any open one for the same email). Returns (invitation, raw_token)."""
    email = User.objects.normalize_email(email)
    if Membership.objects.filter(
        clinic=clinic, user__email=email, status=Membership.Status.ACTIVE
    ).exists():
        raise AlreadyMember()

    raw_token = secrets.token_urlsafe(32)
    with transaction.atomic():
        Invitation.objects.filter(
            clinic=clinic, email=email, accepted_at__isnull=True, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
        invitation = Invitation.objects.create(
            clinic=clinic,
            email=email,
            role=role,
            token_hash=hash_token(raw_token),
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=settings.INVITATION_VALID_DAYS),
        )
    return invitation, raw_token


def reissue_invitation(invitation: Invitation):
    """Replace a still-open invitation with a fresh token and a fresh expiry (the 'resend' action)."""
    if invitation.accepted_at or invitation.revoked_at:
        raise InvitationInvalid()
    return create_invitation(
        clinic=invitation.clinic, invited_by=invitation.invited_by,
        email=invitation.email, role=invitation.role,
    )


def revoke_invitation(invitation: Invitation) -> None:
    if invitation.accepted_at or invitation.revoked_at:
        raise InvitationInvalid()
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at", "updated_at"])


def find_open_invitation(raw_token: str):
    invitation = (
        Invitation.objects.select_related("clinic")
        .filter(token_hash=hash_token(raw_token or ""))
        .first()
    )
    if invitation is None or invitation.status != "pending" or not invitation.clinic.is_active:
        return None
    return invitation


def accept_invitation(*, raw_token: str, acting_user=None, new_account: dict | None = None):
    """Accept an invitation.

    - Email already has an account -> the caller must be logged in AS that account.
    - No account yet -> ``new_account`` (password, first_name, last_name) creates one; because the
      token arrived by email, the new account's address counts as verified.
    Returns (membership, user, created_user).
    """
    invitation = find_open_invitation(raw_token)
    if invitation is None:
        raise InvitationInvalid()

    existing = User.objects.filter(email=invitation.email).first()
    created_user = False
    with transaction.atomic():
        if existing is not None:
            if acting_user is None or not getattr(acting_user, "is_authenticated", False):
                raise LoginRequired()
            if acting_user.pk != existing.pk:
                raise WrongAccount()
            user = existing
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
                user.save(update_fields=["email_verified_at", "updated_at"])
        else:
            data = new_account or {}
            missing = {f: ["This field is required."] for f in ("password", "first_name", "last_name") if not data.get(f)}
            if missing:
                raise serializers.ValidationError(missing)
            candidate = User(email=invitation.email, first_name=data["first_name"], last_name=data["last_name"])
            try:
                validate_password(data["password"], user=candidate)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=invitation.email, password=data["password"],
                        first_name=data["first_name"], last_name=data["last_name"],
                        email_verified_at=timezone.now(),
                    )
            except IntegrityError:
                raise InvitationInvalid()  # someone registered this email a moment ago
            created_user = True

        membership, _ = Membership.objects.update_or_create(
            user=user, clinic=invitation.clinic,
            defaults={"role": invitation.role, "status": Membership.Status.ACTIVE},
        )
        invitation.accepted_at = timezone.now()
        invitation.accepted_by = user
        invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    return membership, user, created_user


# --------------------------------------------------------------------------------------------
# Membership changes
# --------------------------------------------------------------------------------------------
def update_membership(*, membership: Membership, role: str | None = None, status: str | None = None):
    """Change a member's role and/or status, never leaving a clinic without an active admin.

    The clinic row is locked for the duration so two admins cannot demote each other at the
    same moment and leave the clinic with nobody in charge.
    """
    with transaction.atomic():
        Clinic.objects.select_for_update().get(pk=membership.clinic_id)
        membership.refresh_from_db()
        new_role = role or membership.role
        new_status = status or membership.status

        was_active_admin = (
            membership.role == Membership.Role.CLINIC_ADMIN
            and membership.status == Membership.Status.ACTIVE
        )
        stays_active_admin = (
            new_role == Membership.Role.CLINIC_ADMIN and new_status == Membership.Status.ACTIVE
        )
        if was_active_admin and not stays_active_admin:
            other_admins = Membership.objects.filter(
                clinic_id=membership.clinic_id,
                role=Membership.Role.CLINIC_ADMIN,
                status=Membership.Status.ACTIVE,
            ).exclude(pk=membership.pk).count()
            if other_admins == 0:
                raise LastAdminError()

        old = (membership.role, membership.status)
        membership.role, membership.status = new_role, new_status
        membership.save(update_fields=["role", "status", "updated_at"])
    return membership, old
