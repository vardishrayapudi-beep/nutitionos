import pytest

from apps.audit.models import AuditLog
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
URL = "/api/v1/clinics/me/"


def test_any_member_can_read_their_clinic(admin_a, doctor_a, clinic_a):
    for person, role in ((admin_a, "clinic_admin"), (doctor_a, "doctor")):
        body = authenticated_client(person).get(URL).json()
        assert body["id"] == str(clinic_a.id)
        assert body["my_role"] == role
        assert set(body) == {"id", "name", "slug", "email", "phone", "branding_mode", "is_active", "my_role"}


def test_each_clinic_sees_only_itself(admin_a, admin_b, clinic_a, clinic_b):
    assert authenticated_client(admin_a).get(URL).json()["id"] == str(clinic_a.id)
    assert authenticated_client(admin_b).get(URL).json()["id"] == str(clinic_b.id)


def test_anonymous_and_unverified_users_are_refused(client, make_user, make_membership, clinic_a):
    assert client.get(URL).status_code == 401
    unverified = make_user(email_verified_at=None)
    make_membership(unverified, clinic_a)
    response = authenticated_client(unverified).get(URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


def test_admin_can_edit_name_email_phone_and_branding(admin_a, clinic_a):
    response = authenticated_client(admin_a).patch(
        URL, {"name": "Renamed Clinic", "email": "new@clinic.example.com", "phone": "+91 99999 00000",
              "branding_mode": "white_label"}, format="json")
    assert response.status_code == 200
    clinic_a.refresh_from_db()
    assert (clinic_a.name, clinic_a.email, clinic_a.branding_mode) == (
        "Renamed Clinic", "new@clinic.example.com", "white_label")


def test_slug_and_active_flag_cannot_be_changed_by_the_clinic(admin_a, clinic_a):
    original_slug = clinic_a.slug
    authenticated_client(admin_a).patch(URL, {"slug": "hijacked", "is_active": False}, format="json")
    clinic_a.refresh_from_db()
    assert clinic_a.slug == original_slug and clinic_a.is_active is True


@pytest.mark.parametrize("role_fixture", ["doctor_a"])
def test_non_admins_cannot_edit(request, role_fixture, clinic_a):
    person = request.getfixturevalue(role_fixture)
    response = authenticated_client(person).patch(URL, {"name": "Nope"}, format="json")
    assert response.status_code == 403
    clinic_a.refresh_from_db()
    assert clinic_a.name != "Nope"


def test_staff_cannot_edit(make_user, make_membership, clinic_a):
    staff = make_user()
    make_membership(staff, clinic_a)  # default role is staff
    assert authenticated_client(staff).patch(URL, {"name": "Nope"}, format="json").status_code == 403


def test_a_clinic_admin_cannot_edit_another_clinic(admin_a, admin_b, clinic_b):
    authenticated_client(admin_a).patch(URL, {"name": "Takeover"}, format="json")
    clinic_b.refresh_from_db()
    assert clinic_b.name == "Clinic B"


def test_invalid_values_are_rejected(admin_a):
    client = authenticated_client(admin_a)
    assert client.patch(URL, {"email": "not-an-email"}, format="json").status_code == 400
    assert client.patch(URL, {"name": "  "}, format="json").status_code == 400
    assert client.patch(URL, {"branding_mode": "rainbow"}, format="json").status_code == 400


def test_edit_is_audited_with_field_names_only(admin_a, clinic_a):
    authenticated_client(admin_a).patch(URL, {"name": "Secret New Name"}, format="json")
    event = AuditLog.objects.get(action="clinic.updated")
    assert event.clinic == clinic_a and event.actor == admin_a
    assert event.metadata == {"fields": ["name"]}
    assert "Secret New Name" not in str(event.metadata)


def test_unchanged_patch_is_not_audited(admin_a, clinic_a):
    authenticated_client(admin_a).patch(URL, {"name": clinic_a.name}, format="json")
    assert not AuditLog.objects.filter(action="clinic.updated").exists()
