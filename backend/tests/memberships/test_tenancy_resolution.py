"""Unit tests for 'which clinic is this request acting for?'"""
import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.memberships.models import Membership
from apps.memberships.tenancy import (
    ClinicAccessDenied,
    ClinicSelectionRequired,
    InvalidClinicHeader,
    NoActiveMembership,
    get_request_clinic,
    get_request_membership,
    resolve_membership,
)

pytestmark = pytest.mark.django_db
factory = APIRequestFactory()


def make_request(user, clinic_header=None):
    extra = {"HTTP_X_CLINIC_ID": clinic_header} if clinic_header is not None else {}
    request = Request(factory.get("/", **extra))
    request.user = user
    return request


def test_single_active_membership_is_resolved_without_header(admin_a, clinic_a):
    membership = resolve_membership(make_request(admin_a))
    assert membership.clinic == clinic_a
    assert membership.role == Membership.Role.CLINIC_ADMIN


def test_anonymous_user_is_not_authenticated():
    with pytest.raises(NotAuthenticated):
        resolve_membership(make_request(AnonymousUser()))


def test_user_without_any_membership_is_rejected(make_user):
    with pytest.raises(NoActiveMembership):
        resolve_membership(make_request(make_user()))


@pytest.mark.parametrize("status", [Membership.Status.INVITED, Membership.Status.SUSPENDED])
def test_non_active_memberships_grant_no_access(make_user, make_membership, clinic_a, status):
    person = make_user()
    make_membership(person, clinic_a, status=status)
    with pytest.raises(NoActiveMembership):
        resolve_membership(make_request(person))


def test_inactive_clinic_grants_no_access(admin_a, clinic_a):
    clinic_a.is_active = False
    clinic_a.save()
    with pytest.raises(NoActiveMembership):
        resolve_membership(make_request(admin_a))


def test_user_in_several_clinics_must_choose(make_user, make_membership, clinic_a, clinic_b):
    person = make_user()
    make_membership(person, clinic_a)
    make_membership(person, clinic_b)
    with pytest.raises(ClinicSelectionRequired):
        resolve_membership(make_request(person))


def test_header_selects_among_own_memberships(make_user, make_membership, clinic_a, clinic_b):
    person = make_user()
    make_membership(person, clinic_a)
    make_membership(person, clinic_b)
    assert resolve_membership(make_request(person, str(clinic_b.id))).clinic == clinic_b
    assert resolve_membership(make_request(person, str(clinic_a.id))).clinic == clinic_a


def test_header_naming_a_foreign_clinic_is_denied_even_for_single_clinic_users(admin_a, clinic_b):
    """A one-clinic user must NOT silently fall back to their own clinic - and must not get in."""
    with pytest.raises(ClinicAccessDenied):
        resolve_membership(make_request(admin_a, str(clinic_b.id)))


def test_header_for_suspended_membership_is_denied(
    make_user, make_membership, clinic_a, clinic_b
):
    person = make_user()
    make_membership(person, clinic_a)
    make_membership(person, clinic_b, status=Membership.Status.SUSPENDED)
    with pytest.raises(ClinicAccessDenied):
        resolve_membership(make_request(person, str(clinic_b.id)))


def test_unknown_clinic_gives_the_same_error_as_a_foreign_clinic(admin_a, clinic_b):
    with pytest.raises(ClinicAccessDenied) as foreign:
        resolve_membership(make_request(admin_a, str(clinic_b.id)))
    with pytest.raises(ClinicAccessDenied) as nonexistent:
        resolve_membership(make_request(admin_a, str(uuid.uuid4())))
    assert str(foreign.value.detail) == str(nonexistent.value.detail)


@pytest.mark.parametrize("bad_value", ["not-a-uuid", "1", "' OR 1=1 --"])
def test_malformed_header_is_rejected(admin_a, bad_value):
    with pytest.raises(InvalidClinicHeader):
        resolve_membership(make_request(admin_a, bad_value))


def test_resolution_costs_one_query_and_is_cached_per_request(
    admin_a, django_assert_num_queries
):
    request = make_request(admin_a)
    with django_assert_num_queries(1):
        first = get_request_membership(request)
    with django_assert_num_queries(0):
        assert get_request_membership(request) is first
        assert get_request_clinic(request) == first.clinic
