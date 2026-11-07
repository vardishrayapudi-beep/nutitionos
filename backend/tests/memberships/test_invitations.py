import re
from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.memberships.models import Invitation, Membership
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
LIST = "/api/v1/clinics/invitations/"
ACCEPT = "/api/v1/auth/invitations/accept/"
GOOD_PASSWORD = "Correct-Horse-Battery-9"


def emailed_token(index=-1):
    return unquote(re.search(r"token=([^\s&]+)", mail.outbox[index].body).group(1))


def invite(admin, clinic=None, email="newdoc@example.com", role="doctor"):
    return authenticated_client(admin, clinic).post(LIST, {"email": email, "role": role}, format="json")


def accept(token, **extra):
    return APIClient().post(ACCEPT, {"token": token, **extra}, format="json")


NEW_PERSON = {"password": GOOD_PASSWORD, "first_name": "New", "last_name": "Doc"}


# --- creating -------------------------------------------------------------------------------

def test_admin_invites_by_email_and_the_token_is_never_in_the_api_response(admin_a, clinic_a):
    response = invite(admin_a, email="  NewDoc@Example.com ")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newdoc@example.com" and body["status"] == "pending" and body["role"] == "doctor"
    token = emailed_token()
    assert token not in response.content.decode()
    assert set(body) == {"id", "email", "role", "status", "expires_at", "created_at"}
    assert mail.outbox[0].to == ["newdoc@example.com"]
    assert "Clinic A" in mail.outbox[0].subject


def test_only_a_hash_of_the_token_is_stored(admin_a):
    invite(admin_a)
    token = emailed_token()
    stored = Invitation.objects.get()
    assert token not in stored.token_hash and len(stored.token_hash) == 64


def test_non_admins_cannot_invite(doctor_a):
    assert invite(doctor_a).status_code == 403
    assert len(mail.outbox) == 0


def test_cannot_invite_an_existing_active_member(admin_a, doctor_a):
    response = invite(admin_a, email="doctor.a@example.com")
    assert response.status_code == 409 and response.json()["error"]["code"] == "already_member"


def test_reinviting_revokes_the_previous_invitation(admin_a):
    invite(admin_a)
    first = emailed_token()
    invite(admin_a)
    assert accept(first, **NEW_PERSON).status_code == 400
    assert accept(emailed_token(), **NEW_PERSON).status_code == 201


def test_invitation_creation_is_audited_without_the_address(admin_a):
    invite(admin_a)
    event = AuditLog.objects.get(action="invitation.created")
    assert event.metadata == {"role": "doctor"}


def test_invitation_role_must_be_valid(admin_a):
    assert invite(admin_a, role="superhero").status_code == 400
    assert authenticated_client(admin_a).post(LIST, {"email": "bad"}, format="json").status_code == 400


# --- listing, revoking, resending (tenant isolation) ---------------------------------------

def test_invitations_are_isolated_between_clinics(admin_a, admin_b):
    invite(admin_a)
    mine = Invitation.objects.get()
    # (invitations have no GET-detail route, so check list + destroy + resend isolation explicitly)
    assert str(mine.id) in {r["id"] for r in authenticated_client(admin_a).get(LIST).json()["results"]}
    assert str(mine.id) not in {r["id"] for r in authenticated_client(admin_b).get(LIST).json()["results"]}
    assert authenticated_client(admin_b).delete(f"{LIST}{mine.id}/").status_code == 404
    assert authenticated_client(admin_b).post(f"{LIST}{mine.id}/resend/").status_code == 404
    mine.refresh_from_db()
    assert mine.status == "pending"


def test_non_admins_cannot_list_invitations(doctor_a):
    assert authenticated_client(doctor_a).get(LIST).status_code == 403


def test_revoking_kills_the_token(admin_a):
    invite(admin_a)
    invitation = Invitation.objects.get()
    assert authenticated_client(admin_a).delete(f"{LIST}{invitation.id}/").status_code == 204
    assert accept(emailed_token(), **NEW_PERSON).status_code == 400
    assert authenticated_client(admin_a).delete(f"{LIST}{invitation.id}/").status_code == 400  # already revoked
    assert AuditLog.objects.filter(action="invitation.revoked").exists()


def test_resend_issues_a_fresh_token_and_retires_the_old_one(admin_a):
    invite(admin_a)
    old = emailed_token()
    invitation = Invitation.objects.get()
    assert authenticated_client(admin_a).post(f"{LIST}{invitation.id}/resend/").status_code == 202
    assert len(mail.outbox) == 2 and emailed_token() != old
    assert accept(old, **NEW_PERSON).status_code == 400
    assert accept(emailed_token(), **NEW_PERSON).status_code == 201


# --- accepting: brand-new person -------------------------------------------------------------

def test_new_person_accepts_gets_verified_account_membership_and_tokens(admin_a, clinic_a, django_user_model):
    invite(admin_a, role="staff")
    response = accept(emailed_token(), **NEW_PERSON)
    assert response.status_code == 201
    body = response.json()
    user = django_user_model.objects.get(email="newdoc@example.com")
    assert user.email_verified_at is not None and user.check_password(GOOD_PASSWORD)
    membership = Membership.objects.get(user=user, clinic=clinic_a)
    assert (membership.role, membership.status) == ("staff", "active")
    assert body["tokens"]["access"] and body["clinic"]["slug"] == clinic_a.slug
    assert Invitation.objects.get().status == "accepted"
    assert AuditLog.objects.filter(action="invitation.accepted", actor=user).exists()
    # the returned token works straight away on a clinic endpoint
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    assert client.get("/api/v1/clinics/me/").status_code == 200


def test_an_invitation_can_only_be_used_once(admin_a):
    invite(admin_a)
    token = emailed_token()
    assert accept(token, **NEW_PERSON).status_code == 201
    assert accept(token, **NEW_PERSON).status_code == 400


def test_new_person_must_supply_name_and_a_strong_password(admin_a):
    invite(admin_a)
    token = emailed_token()
    missing = accept(token)
    assert missing.status_code == 400
    assert {"password", "first_name", "last_name"} <= set(missing.json()["error"]["details"])
    weak = accept(token, **{**NEW_PERSON, "password": "password123456"})
    assert weak.status_code == 400 and "password" in weak.json()["error"]["details"]
    assert accept(token, **NEW_PERSON).status_code == 201  # still usable after failed attempts


# --- accepting: someone who already has an account ------------------------------------------

def test_existing_user_must_be_logged_in_as_the_invited_address(admin_a, make_user, clinic_a):
    person = make_user("newdoc@example.com", email_verified_at=None)
    stranger = make_user("stranger@example.com")
    invite(admin_a, role="doctor")
    token = emailed_token()

    anonymous = accept(token)
    assert anonymous.status_code == 400 and anonymous.json()["error"]["code"] == "login_required"

    wrong = authenticated_client(stranger).post(ACCEPT, {"token": token}, format="json")
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "invitation_wrong_account"

    right = authenticated_client(person).post(ACCEPT, {"token": token}, format="json")
    assert right.status_code == 201 and right.json()["tokens"] is None
    person.refresh_from_db()
    assert person.email_verified_at is not None
    assert Membership.objects.get(user=person, clinic=clinic_a).role == "doctor"


def test_accepting_reactivates_a_suspended_member_with_the_new_role(admin_a, make_user, make_membership, clinic_a):
    person = make_user("newdoc@example.com")
    make_membership(person, clinic_a, Membership.Role.STAFF, Membership.Status.SUSPENDED)
    invite(admin_a, role="doctor")
    authenticated_client(person).post(ACCEPT, {"token": emailed_token()}, format="json")
    membership = Membership.objects.get(user=person, clinic=clinic_a)
    assert (membership.role, membership.status) == ("doctor", "active")


def test_a_person_can_join_a_second_clinic(admin_b, make_user, make_membership, clinic_a, clinic_b):
    person = make_user("newdoc@example.com")
    make_membership(person, clinic_a, Membership.Role.DOCTOR)
    invite(admin_b, clinic_b, role="doctor")
    assert authenticated_client(person).post(ACCEPT, {"token": emailed_token()}, format="json").status_code == 201
    me = authenticated_client(person).get("/api/v1/auth/me/").json()
    assert me["needs_clinic_selection"] is True


# --- bad tokens give one indistinguishable answer -------------------------------------------

def test_unknown_expired_revoked_and_inactive_clinic_tokens_are_indistinguishable(admin_a, clinic_a):
    invite(admin_a)
    expired_token = emailed_token()
    Invitation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

    invite(admin_a, email="second@example.com")
    revoked_token = emailed_token()
    authenticated_client(admin_a).delete(f"{LIST}{Invitation.objects.get(email='second@example.com').id}/")

    invite(admin_a, email="third@example.com")
    inactive_token = emailed_token()
    clinic_a.is_active = False
    clinic_a.save()

    answers = [accept(t, **NEW_PERSON) for t in (expired_token, revoked_token, inactive_token, "totally-unknown")]
    assert {a.status_code for a in answers} == {400}
    assert len({str(a.json()) for a in answers}) == 1


def test_accepting_is_rate_limited():
    codes = [accept("guess-%d" % i).status_code for i in range(11)]
    assert codes[:10] == [400] * 10 and codes[10] == 429


def test_pending_invitations_do_not_grant_access_before_acceptance(admin_a, make_user):
    outsider = make_user("newdoc@example.com")
    invite(admin_a)
    assert authenticated_client(outsider).get("/api/v1/clinics/me/").status_code == 403
