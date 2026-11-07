import pytest
from rest_framework.test import APIClient

from apps.memberships.models import Membership
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
URL = "/api/v1/auth/me/"


def test_anonymous_request_is_rejected():
    response = APIClient().get(URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_returns_profile_and_the_memberships_of_the_caller(admin_a, clinic_a):
    body = authenticated_client(admin_a).get(URL).json()
    assert body["id"] == str(admin_a.id)
    assert body["email"] == "admin.a@example.com"
    assert body["needs_clinic_selection"] is False
    assert len(body["memberships"]) == 1
    membership = body["memberships"][0]
    assert (membership["role"], membership["status"]) == ("clinic_admin", "active")
    assert membership["clinic"]["id"] == str(clinic_a.id)
    assert set(membership["clinic"]) == {"id", "name", "slug", "branding_mode", "is_active"}


def test_never_exposes_secrets_or_privilege_flags(admin_a):
    body = authenticated_client(admin_a).get(URL).json()
    assert set(body) == {"id", "email", "email_verified", "first_name", "last_name", "memberships",
                         "needs_clinic_selection"}


def test_does_not_leak_other_clinics_or_their_members(admin_a, admin_b, doctor_a, clinic_b):
    text = authenticated_client(admin_a).get(URL).content.decode()
    assert str(clinic_b.id) not in text
    assert "admin.b@example.com" not in text
    assert "doctor.a@example.com" not in text


def test_user_without_any_clinic_gets_an_empty_list(make_user):
    body = authenticated_client(make_user()).get(URL).json()
    assert body["memberships"] == []
    assert body["needs_clinic_selection"] is False


def test_multi_clinic_user_is_told_to_choose(make_user, make_membership, clinic_a, clinic_b):
    person = make_user()
    make_membership(person, clinic_a)
    make_membership(person, clinic_b)
    body = authenticated_client(person).get(URL).json()
    assert body["needs_clinic_selection"] is True
    assert len(body["memberships"]) == 2


def test_only_usable_memberships_count_towards_clinic_selection(
    make_user, make_membership, clinic_a, clinic_b, make_clinic
):
    person = make_user()
    make_membership(person, clinic_a)  # usable
    make_membership(person, clinic_b, status=Membership.Status.SUSPENDED)
    inactive_clinic = make_clinic("Closed Clinic", is_active=False)
    make_membership(person, inactive_clinic)

    body = authenticated_client(person).get(URL).json()
    assert body["needs_clinic_selection"] is False
    statuses = {m["clinic"]["name"]: (m["status"], m["clinic"]["is_active"]) for m in body["memberships"]}
    assert statuses["Clinic B"] == ("suspended", True)  # the user is allowed to see their own status
    assert statuses["Closed Clinic"] == ("active", False)


def test_invited_membership_is_visible_but_not_selectable(make_user, make_membership, clinic_a):
    person = make_user()
    make_membership(person, clinic_a, status=Membership.Status.INVITED)
    body = authenticated_client(person).get(URL).json()
    assert body["memberships"][0]["status"] == "invited"
    assert body["needs_clinic_selection"] is False


def test_works_without_choosing_a_clinic_and_ignores_the_clinic_header(
    make_user, make_membership, clinic_a, clinic_b
):
    person = make_user()
    make_membership(person, clinic_a)
    make_membership(person, clinic_b)
    client = authenticated_client(person)  # two clinics, no header: tenant endpoints would 400
    assert client.get(URL).status_code == 200
    assert client.get(URL, HTTP_X_CLINIC_ID="not-even-a-uuid").status_code == 200


def test_query_count_does_not_grow_with_the_number_of_memberships(
    make_user, make_membership, make_clinic, django_assert_max_num_queries
):
    person = make_user()
    for index in range(6):
        make_membership(person, make_clinic(f"Clinic {index}"))
    client = authenticated_client(person)
    with django_assert_max_num_queries(3):  # authentication + one joined membership query
        assert client.get(URL).status_code == 200


def test_deactivated_user_with_a_valid_token_is_rejected(admin_a):
    client = authenticated_client(admin_a)
    admin_a.is_active = False
    admin_a.save()
    assert client.get(URL).status_code == 401
