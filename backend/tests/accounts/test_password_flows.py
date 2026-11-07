import re
from urllib.parse import unquote

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
RESET = "/api/v1/auth/password-reset/"
CONFIRM = "/api/v1/auth/password-reset/confirm/"
CHANGE = "/api/v1/auth/password/change/"
LOGIN = "/api/v1/auth/token/"
REFRESH = "/api/v1/auth/token/refresh/"
NEW_PASSWORD = "A-Brand-New-Passw0rd!"


def post(url, data=None):
    return APIClient().post(url, data or {}, format="json")


def link_params():
    body = mail.outbox[-1].body
    return {"uid": unquote(re.search(r"uid=([^\s&]+)", body).group(1)),
            "token": unquote(re.search(r"token=([^\s&]+)", body).group(1))}


# --- reset request --------------------------------------------------------------------------

def test_reset_request_for_existing_user_sends_one_email(user):
    assert post(RESET, {"email": "doctor@example.com"}).status_code == 202
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["doctor@example.com"]
    assert AuditLog.objects.filter(action="auth.password_reset_requested", actor=user).exists()


def test_reset_request_answers_identically_for_unknown_emails(user):
    known = post(RESET, {"email": "doctor@example.com"})
    unknown = post(RESET, {"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mail.outbox) == 1  # only the real account received anything


def test_reset_request_ignores_inactive_users(user):
    user.is_active = False
    user.save()
    assert post(RESET, {"email": "doctor@example.com"}).status_code == 202
    assert len(mail.outbox) == 0


def test_reset_requests_are_rate_limited(user):
    codes = [post(RESET, {"email": "doctor@example.com"}).status_code for _ in range(6)]
    assert codes == [202] * 5 + [429]


# --- reset confirm --------------------------------------------------------------------------

def test_reset_changes_password_and_signs_out_everywhere(user, user_password):
    old_tokens = post(LOGIN, {"email": user.email, "password": user_password}).json()
    post(RESET, {"email": user.email})
    response = post(CONFIRM, {**link_params(), "new_password": NEW_PASSWORD})
    assert response.status_code == 200

    assert post(LOGIN, {"email": user.email, "password": user_password}).status_code == 401
    assert post(LOGIN, {"email": user.email, "password": NEW_PASSWORD}).status_code == 200
    assert post(REFRESH, {"refresh": old_tokens["refresh"]}).status_code == 401
    assert AuditLog.objects.filter(action="auth.password_reset_completed", actor=user).exists()


def test_reset_link_works_only_once(user):
    post(RESET, {"email": user.email})
    params = link_params()
    assert post(CONFIRM, {**params, "new_password": NEW_PASSWORD}).status_code == 200
    assert post(CONFIRM, {**params, "new_password": "Yet-Another-Passw0rd!"}).status_code == 400


def test_reset_rejects_weak_passwords_and_keeps_the_link_usable(user, user_password):
    post(RESET, {"email": user.email})
    params = link_params()
    weak = post(CONFIRM, {**params, "new_password": "password123456"})
    assert weak.status_code == 400
    assert "new_password" in weak.json()["error"]["details"]
    user.refresh_from_db()
    assert user.check_password(user_password)  # nothing changed
    # NB: logging in here would (by Django's design) invalidate the link, because last_login is
    # part of the link's signature - so we deliberately check the password directly instead.
    assert post(CONFIRM, {**params, "new_password": NEW_PASSWORD}).status_code == 200


@pytest.mark.parametrize("uid,token", [("garbage", "x"), ("", ""), ("MQ", "not-a-token")])
def test_reset_rejects_malformed_links(uid, token):
    assert post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD}).status_code == 400


def test_reset_link_for_one_user_cannot_reset_another(user, make_user):
    other = make_user("other@example.com")
    post(RESET, {"email": user.email})
    params = link_params()
    import base64
    forged = base64.urlsafe_b64encode(str(other.pk).encode()).decode().rstrip("=")
    assert post(CONFIRM, {"uid": forged, "token": params["token"], "new_password": NEW_PASSWORD}).status_code == 400


def test_completing_a_reset_verifies_the_email(make_user):
    person = make_user("unverified@example.com", email_verified_at=None)
    post(RESET, {"email": person.email})
    post(CONFIRM, {**link_params(), "new_password": NEW_PASSWORD})
    person.refresh_from_db()
    assert person.email_verified_at is not None


# --- change password ------------------------------------------------------------------------

def test_change_requires_login():
    assert post(CHANGE, {"old_password": "x", "new_password": "y"}).status_code == 401


def test_change_rejects_wrong_current_password(user):
    response = authenticated_client(user).post(
        CHANGE, {"old_password": "Wrong-Password-1", "new_password": NEW_PASSWORD}, format="json")
    assert response.status_code == 400
    assert "old_password" in response.json()["error"]["details"]


def test_change_rejects_weak_new_password(user, user_password):
    response = authenticated_client(user).post(
        CHANGE, {"old_password": user_password, "new_password": "short"}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "new_password" in response.json()["error"]["details"]


def test_change_revokes_other_sessions_but_keeps_this_device_logged_in(user, user_password):
    other_device = post(LOGIN, {"email": user.email, "password": user_password}).json()
    response = authenticated_client(user).post(
        CHANGE, {"old_password": user_password, "new_password": NEW_PASSWORD}, format="json")
    assert response.status_code == 200
    fresh = response.json()

    assert post(REFRESH, {"refresh": other_device["refresh"]}).status_code == 401
    assert post(REFRESH, {"refresh": fresh["refresh"]}).status_code == 200
    assert post(LOGIN, {"email": user.email, "password": NEW_PASSWORD}).status_code == 200
    assert AuditLog.objects.filter(action="auth.password_changed", actor=user).exists()


def test_logging_in_invalidates_an_outstanding_reset_link(user, user_password):
    """Documented Django behaviour we rely on: if the user remembers their password and logs in,
    stale reset links die."""
    post(RESET, {"email": user.email})
    params = link_params()
    assert post(LOGIN, {"email": user.email, "password": user_password}).status_code == 200
    assert post(CONFIRM, {**params, "new_password": NEW_PASSWORD}).status_code == 400
