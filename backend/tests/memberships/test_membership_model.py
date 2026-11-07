import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.memberships.models import Membership

pytestmark = pytest.mark.django_db


def test_new_membership_defaults_to_least_privileged_status(make_user, clinic_a):
    membership = Membership.objects.create(
        user=make_user(), clinic=clinic_a, role=Membership.Role.DOCTOR
    )
    assert membership.status == Membership.Status.INVITED
    assert membership.is_active_member is False


def test_active_membership_reports_active(make_user, make_membership, clinic_a):
    membership = make_membership(make_user(), clinic_a)
    assert membership.is_active_member is True


def test_a_user_can_have_only_one_membership_per_clinic(make_user, make_membership, clinic_a):
    person = make_user()
    make_membership(person, clinic_a)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_membership(person, clinic_a, Membership.Role.DOCTOR)


def test_a_user_can_belong_to_several_clinics_with_different_roles(
    make_user, make_membership, clinic_a, clinic_b
):
    person = make_user()
    make_membership(person, clinic_a, Membership.Role.DOCTOR)
    make_membership(person, clinic_b, Membership.Role.STAFF)
    assert {m.clinic_id: m.role for m in person.memberships.all()} == {
        clinic_a.id: "doctor",
        clinic_b.id: "staff",
    }


def test_database_rejects_unknown_role_even_when_validation_is_bypassed(make_user, clinic_a):
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.bulk_create(
            [Membership(user=make_user(), clinic=clinic_a, role="superhero", status="active")]
        )


def test_database_rejects_unknown_status_even_when_validation_is_bypassed(make_user, clinic_a):
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.bulk_create(
            [Membership(user=make_user(), clinic=clinic_a, role="doctor", status="godmode")]
        )


def test_clinic_with_memberships_cannot_be_deleted(make_user, make_membership, clinic_a):
    make_membership(make_user(), clinic_a)
    with pytest.raises(ProtectedError):
        clinic_a.delete()


def test_user_with_memberships_cannot_be_deleted(make_user, make_membership, clinic_a):
    person = make_user()
    make_membership(person, clinic_a)
    with pytest.raises(ProtectedError):
        person.delete()


def test_clinic_exposes_its_memberships(make_user, make_membership, clinic_a, clinic_b):
    make_membership(make_user(), clinic_a)
    make_membership(make_user(), clinic_a)
    make_membership(make_user(), clinic_b)
    assert clinic_a.memberships.count() == 2
    assert clinic_b.memberships.count() == 1


@pytest.mark.parametrize("status", list(Membership.Status))
@pytest.mark.parametrize("clinic_active", [True, False])
def test_grants_access_matches_the_query_that_enforces_access(
    make_user, make_membership, make_clinic, status, clinic_active
):
    """Two definitions of 'has access' must never drift apart."""
    from apps.memberships.tenancy import active_memberships_for

    person = make_user()
    clinic = make_clinic()
    membership = make_membership(person, clinic, status=status)
    clinic.is_active = clinic_active
    clinic.save()

    fresh = Membership.objects.select_related("clinic").get(pk=membership.pk)
    assert fresh.grants_access == active_memberships_for(person).filter(pk=fresh.pk).exists()
    assert fresh.grants_access == (status == Membership.Status.ACTIVE and clinic_active)
