import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.clinics.models import Clinic
from apps.memberships.models import Membership
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
User = get_user_model()
URL = "/api/v1/auth/register-clinic/"


def payload(**admin_overrides):
    admin = {
        "email": "Dr.Priya@Sunrise.example.com",
        "password": "Correct-Horse-Battery-9",
        "first_name": "Priya",
        "last_name": "Sharma",
    }
    admin.update(admin_overrides)
    return {
        "clinic": {"name": "Sunrise Nutrition Clinic", "email": "hello@sunrise.example.com",
                   "phone": "+91 98765 43210"},
        "admin": admin,
    }


def register(data):
    return APIClient().post(URL, data, format="json")


def nothing_was_created(users_before, clinics_before, memberships_before):
    assert User.objects.count() == users_before
    assert Clinic.objects.count() == clinics_before
    assert Membership.objects.count() == memberships_before


def counts():
    return User.objects.count(), Clinic.objects.count(), Membership.objects.count()


# --- the happy path -------------------------------------------------------------------------

def test_registration_creates_clinic_admin_and_active_membership():
    response = register(payload())
    assert response.status_code == 201
    body = response.json()

    user = User.objects.get(id=body["user"]["id"])
    assert user.email == "dr.priya@sunrise.example.com"  # normalised
    assert user.check_password("Correct-Horse-Battery-9")
    assert (user.is_staff, user.is_superuser, user.is_active) == (False, False, True)

    clinic = Clinic.objects.get(id=body["clinic"]["id"])
    assert (clinic.name, clinic.slug) == ("Sunrise Nutrition Clinic", "sunrise-nutrition-clinic")
    assert clinic.branding_mode == Clinic.BrandingMode.PLATFORM
    assert clinic.is_active is True

    membership = Membership.objects.get(user=user, clinic=clinic)
    assert (membership.role, membership.status) == ("clinic_admin", "active")
    assert body["membership"] == {"id": str(membership.id), "role": "clinic_admin", "status": "active"}


def test_response_never_contains_the_password():
    response = register(payload())
    assert "Correct-Horse-Battery-9" not in response.content.decode()
    assert "password" not in response.json()["user"]


def test_returned_tokens_work_immediately():
    body = register(payload()).json()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.json()["memberships"][0]["role"] == "clinic_admin"

    refreshed = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": body["tokens"]["refresh"]}, format="json")
    assert refreshed.status_code == 200


def test_phone_is_optional():
    data = payload()
    del data["clinic"]["phone"]
    assert register(data).status_code == 201


def test_two_clinics_with_the_same_name_get_distinct_slugs():
    first = register(payload()).json()["clinic"]["slug"]
    second = register(payload(email="other@example.com")).json()["clinic"]["slug"]
    assert (first, second) == ("sunrise-nutrition-clinic", "sunrise-nutrition-clinic-2")


# --- validation: nothing is created on any failure ------------------------------------------

def test_duplicate_email_is_rejected_case_insensitively(django_user_model):
    django_user_model.objects.create_user(email="dr.priya@sunrise.example.com", password="Whatever-123456")
    before = counts()
    response = register(payload(email="DR.PRIYA@SUNRISE.EXAMPLE.COM"))
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "email" in error["details"]["admin"]
    nothing_was_created(*before)


@pytest.mark.parametrize("bad_password", [
    "short1!",                          # too short
    "password123456",                   # common password
    "1234567890123",                    # entirely numeric
    "priya.sharma@clinic.example.com",  # too similar to the account's own details
])
def test_weak_passwords_are_rejected(bad_password):
    before = counts()
    response = register(payload(email="priya.sharma@clinic.example.com", password=bad_password))
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]["admin"]
    nothing_was_created(*before)


def test_absurdly_long_password_is_rejected_before_hashing():
    response = register(payload(password="a1B!" * 200))
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]["admin"]


def test_missing_fields_are_reported_for_both_sections():
    response = register({})
    assert response.status_code == 400
    details = response.json()["error"]["details"]
    assert "clinic" in details and "admin" in details


def test_blank_and_whitespace_only_clinic_names_are_rejected():
    for name in ("", "    "):
        data = payload()
        data["clinic"]["name"] = name
        assert register(data).status_code == 400


@pytest.mark.parametrize("bad_email", ["not-an-email", "a@", "@b.com", ""])
def test_invalid_emails_are_rejected(bad_email):
    data = payload(email=bad_email)
    assert register(data).status_code == 400
    data = payload()
    data["clinic"]["email"] = bad_email
    assert register(data).status_code == 400


# --- mass-assignment: clients cannot grant themselves privileges ----------------------------

def test_privileged_fields_in_the_payload_are_ignored():
    data = payload()
    data["admin"].update({"is_staff": True, "is_superuser": True, "is_active": False, "role": "staff"})
    data["clinic"].update({"slug": "admin", "is_active": False, "branding_mode": "white_label"})
    data["membership"] = {"role": "staff", "status": "suspended"}
    body = register(data).json()

    user = User.objects.get(id=body["user"]["id"])
    assert (user.is_staff, user.is_superuser, user.is_active) == (False, False, True)
    clinic = Clinic.objects.get(id=body["clinic"]["id"])
    assert clinic.slug == "sunrise-nutrition-clinic"
    assert (clinic.is_active, clinic.branding_mode) == (True, "platform")
    membership = Membership.objects.get(user=user)
    assert (membership.role, membership.status) == ("clinic_admin", "active")


def test_new_clinic_admin_cannot_see_any_other_clinic(make_clinic):
    other = make_clinic("Somebody Else")
    body = register(payload()).json()
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    clinic_ids = {m["clinic"]["id"] for m in me.get("/api/v1/auth/me/").json()["memberships"]}
    assert clinic_ids == {body["clinic"]["id"]}
    assert str(other.id) not in clinic_ids


# --- abuse protection -----------------------------------------------------------------------

def test_registration_is_strictly_rate_limited():
    client = APIClient()
    statuses = [client.post(URL, {}, format="json").status_code for _ in range(6)]
    assert statuses == [400, 400, 400, 400, 400, 429]
    assert client.post(URL, {}, format="json").json()["error"]["code"] == "throttled"
