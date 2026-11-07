"""Business operations that span several tables. Views stay thin; rules live here."""
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.memberships.models import Membership

from .models import Clinic

User = get_user_model()

SLUG_RETRY_ATTEMPTS = 5


class EmailAlreadyRegistered(Exception):
    """The admin's email belongs to an existing user."""


class RegistrationUnavailable(Exception):
    """Could not reserve a unique clinic URL name after several attempts. Safe to retry."""


@dataclass(frozen=True)
class RegistrationResult:
    user: "User"
    clinic: Clinic
    membership: Membership


def _create_clinic_with_retry(clinic_data: dict) -> Clinic:
    """Create a clinic, retrying if a simultaneous registration grabbed the same slug.

    Slugs are generated with a check-then-insert, so two registrations with the same name
    can pick the same slug at the same instant. The database UNIQUE constraint rejects the
    loser; we simply try again, which now computes a fresh suffix. Each attempt runs in its
    own savepoint so a failed insert does not poison the surrounding transaction.
    """
    for _ in range(SLUG_RETRY_ATTEMPTS):
        try:
            with transaction.atomic():
                return Clinic.objects.create(**clinic_data)
        except IntegrityError:
            continue
    raise RegistrationUnavailable()


def register_clinic(*, clinic_data: dict, admin_data: dict) -> RegistrationResult:
    """Create a clinic, its first administrator and their active membership - all or nothing.

    ``admin_data`` must hold already-validated email, password, first_name and last_name.
    The new account gets NO special flags: it is a normal user whose only privilege is an
    active ``clinic_admin`` membership in its own, brand-new clinic.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=admin_data["email"],
                    password=admin_data["password"],
                    first_name=admin_data["first_name"],
                    last_name=admin_data["last_name"],
                )
        except IntegrityError:
            # Only the unique-email rule can fail here (two sign-ups with one email at once).
            raise EmailAlreadyRegistered() from None

        clinic = _create_clinic_with_retry(clinic_data)
        membership = Membership.objects.create(
            user=user,
            clinic=clinic,
            role=Membership.Role.CLINIC_ADMIN,
            status=Membership.Status.ACTIVE,
        )
    return RegistrationResult(user=user, clinic=clinic, membership=membership)
