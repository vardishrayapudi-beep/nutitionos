import pytest

from apps.audit.models import AuditLog
from apps.memberships.models import Membership
from tests.support.api import assert_clinic_isolation, authenticated_client

pytestmark = pytest.mark.django_db
LIST = "/api/v1/clinics/members/"


def detail(membership):
    return f"{LIST}{membership.id}/"


def membership_of(person, clinic):
    return Membership.objects.get(user=person, clinic=clinic)


def test_members_can_list_colleagues_in_their_clinic_only(admin_a, doctor_a, admin_b, clinic_a):
    body = authenticated_client(doctor_a).get(LIST).json()
    emails = {row["user"]["email"] for row in body["results"]}
    assert emails == {"admin.a@example.com", "doctor.a@example.com"}
    assert set(body["results"][0]) == {"id", "user", "role", "status", "created_at"}
    assert set(body["results"][0]["user"]) == {"id", "email", "first_name", "last_name"}  # no password etc.


def test_cross_clinic_isolation(admin_a, doctor_a, admin_b, clinic_a):
    target = membership_of(doctor_a, clinic_a)
    assert_clinic_isolation(
        owner_client=authenticated_client(admin_a), intruder_client=authenticated_client(admin_b),
        list_url=LIST, detail_url=detail(target), owned_id=target.id, update_payload={"role": "staff"},
    )
    target.refresh_from_db()
    assert target.role == Membership.Role.DOCTOR


def test_filter_and_search(admin_a, doctor_a):
    client = authenticated_client(admin_a)
    assert {r["role"] for r in client.get(LIST, {"role": "doctor"}).json()["results"]} == {"doctor"}
    found = client.get(LIST, {"search": "doctor.a"}).json()["results"]
    assert [r["user"]["email"] for r in found] == ["doctor.a@example.com"]


def test_admin_can_change_role_and_it_is_audited(admin_a, doctor_a, clinic_a):
    target = membership_of(doctor_a, clinic_a)
    response = authenticated_client(admin_a).patch(detail(target), {"role": "staff"}, format="json")
    assert response.status_code == 200 and response.json()["role"] == "staff"
    event = AuditLog.objects.get(action="member.role_changed")
    assert event.metadata == {"old_role": "doctor", "new_role": "staff"}
    assert event.target_id == str(target.id)


def test_non_admins_cannot_change_anything(admin_a, doctor_a, clinic_a):
    target = membership_of(admin_a, clinic_a)
    assert authenticated_client(doctor_a).patch(detail(target), {"role": "staff"}, format="json").status_code == 403
    target.refresh_from_db()
    assert target.role == Membership.Role.CLINIC_ADMIN


def test_suspending_a_member_locks_them_out_immediately(admin_a, doctor_a, clinic_a):
    doctor_client = authenticated_client(doctor_a)
    assert doctor_client.get(LIST).status_code == 200
    target = membership_of(doctor_a, clinic_a)
    authenticated_client(admin_a).patch(detail(target), {"status": "suspended"}, format="json")
    response = doctor_client.get(LIST)
    assert response.status_code == 403 and response.json()["error"]["code"] == "no_active_membership"
    assert AuditLog.objects.filter(action="member.status_changed").exists()


def test_a_suspended_member_can_be_reactivated(admin_a, doctor_a, clinic_a):
    target = membership_of(doctor_a, clinic_a)
    client = authenticated_client(admin_a)
    client.patch(detail(target), {"status": "suspended"}, format="json")
    client.patch(detail(target), {"status": "active"}, format="json")
    assert authenticated_client(doctor_a).get(LIST).status_code == 200


# --- the last-admin rule --------------------------------------------------------------------

def test_the_only_admin_cannot_demote_or_suspend_themselves(admin_a, clinic_a):
    own = membership_of(admin_a, clinic_a)
    client = authenticated_client(admin_a)
    for payload in ({"role": "doctor"}, {"status": "suspended"}, {"role": "staff", "status": "suspended"}):
        response = client.patch(detail(own), payload, format="json")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "last_admin"
    own.refresh_from_db()
    assert (own.role, own.status) == ("clinic_admin", "active")


def test_an_admin_can_step_down_when_another_admin_remains(admin_a, doctor_a, clinic_a):
    authenticated_client(admin_a).patch(detail(membership_of(doctor_a, clinic_a)), {"role": "clinic_admin"}, format="json")
    own = membership_of(admin_a, clinic_a)
    assert authenticated_client(admin_a).patch(detail(own), {"role": "doctor"}, format="json").status_code == 200


def test_two_admins_cannot_both_leave(admin_a, doctor_a, clinic_a):
    first, second = membership_of(admin_a, clinic_a), membership_of(doctor_a, clinic_a)
    authenticated_client(admin_a).patch(detail(second), {"role": "clinic_admin"}, format="json")
    assert authenticated_client(admin_a).patch(detail(first), {"status": "suspended"}, format="json").status_code == 200
    # admin_a is suspended now; the remaining admin must not be able to remove themselves
    response = authenticated_client(doctor_a).patch(detail(second), {"role": "staff"}, format="json")
    assert response.status_code == 409


def test_suspended_admins_do_not_count_as_available_admins(admin_a, make_user, make_membership, clinic_a):
    ghost = make_user()
    make_membership(ghost, clinic_a, Membership.Role.CLINIC_ADMIN, Membership.Status.SUSPENDED)
    response = authenticated_client(admin_a).patch(detail(membership_of(admin_a, clinic_a)), {"role": "staff"}, format="json")
    assert response.status_code == 409


# --- input rules ----------------------------------------------------------------------------

def test_cannot_move_someone_into_invited_state_or_send_empty_or_unknown_values(admin_a, doctor_a, clinic_a):
    target, client = detail(membership_of(doctor_a, clinic_a)), authenticated_client(admin_a)
    assert client.patch(target, {"status": "invited"}, format="json").status_code == 400
    assert client.patch(target, {}, format="json").status_code == 400
    assert client.patch(target, {"role": "superhero"}, format="json").status_code == 400


def test_user_details_cannot_be_edited_through_this_endpoint(admin_a, doctor_a, clinic_a):
    target = membership_of(doctor_a, clinic_a)
    authenticated_client(admin_a).patch(detail(target), {"user": {"email": "evil@example.com"}, "clinic": "x"}, format="json")
    doctor_a.refresh_from_db()
    assert doctor_a.email == "doctor.a@example.com"


def test_there_is_no_delete_or_create(admin_a, doctor_a, clinic_a):
    client = authenticated_client(admin_a)
    assert client.delete(detail(membership_of(doctor_a, clinic_a))).status_code == 405
    assert client.post(LIST, {}, format="json").status_code == 405
