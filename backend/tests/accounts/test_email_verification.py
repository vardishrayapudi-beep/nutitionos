import re
from urllib.parse import unquote

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from tests.support.api import authenticated_client

pytestmark = pytest.mark.django_db
REGISTER = "/api/v1/auth/register-clinic/"
VERIFY = "/api/v1/auth/verify-email/"
RESEND = "/api/v1/auth/verify-email/resend/"


def register(email="new.admin@example.com"):
    return APIClient().post(REGISTER, {
        "clinic": {"name": "Verify Clinic", "email": "c@example.com"},
        "admin": {"email": email, "password": "Correct-Horse-Battery-9", "first_name": "N", "last_name": "A"},
    }, format="json")


def token_from_outbox(index=-1):
    # The link is percent-encoded; a browser/frontend decodes it before sending it back.
    return unquote(re.search(r"token=([^\s&]+)", mail.outbox[index].body).group(1))


def test_registration_sends_a_verification_email_with_a_link_to_the_frontend(settings):
    assert register().status_code == 201
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["new.admin@example.com"]
    assert message.body.count(f"{settings.FRONTEND_BASE_URL}/verify-email?token=") == 1


def test_a_new_account_starts_unverified(django_user_model):
    register()
    assert django_user_model.objects.get(email="new.admin@example.com").email_verified_at is None


def test_verification_link_verifies_the_account_and_is_audited(django_user_model):
    register()
    response = APIClient().post(VERIFY, {"token": token_from_outbox()}, format="json")
    assert response.status_code == 200 and response.json() == {"verified": True}
    user = django_user_model.objects.get(email="new.admin@example.com")
    assert user.email_verified_at is not None
    assert AuditLog.objects.filter(action="auth.email_verified", actor=user).exists()


def test_me_reports_verification_state(django_user_model):
    body = register().json()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    assert client.get("/api/v1/auth/me/").json()["email_verified"] is False
    client.post(VERIFY, {"token": token_from_outbox()}, format="json")
    assert client.get("/api/v1/auth/me/").json()["email_verified"] is True


def test_verifying_twice_is_harmless():
    register()
    token = token_from_outbox()
    assert APIClient().post(VERIFY, {"token": token}, format="json").status_code == 200
    assert APIClient().post(VERIFY, {"token": token}, format="json").status_code == 200


@pytest.mark.parametrize("bad", ["", "garbage", "abc:def:ghi"])
def test_invalid_tokens_are_rejected(bad):
    response = APIClient().post(VERIFY, {"token": bad}, format="json")
    assert response.status_code == 400


def test_tampered_token_is_rejected():
    register()
    token = token_from_outbox()
    assert APIClient().post(VERIFY, {"token": token[:-3] + "xyz"}, format="json").status_code == 400


def test_expired_token_is_rejected(settings):
    register()
    token = token_from_outbox()
    settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS = -1
    assert APIClient().post(VERIFY, {"token": token}, format="json").status_code == 400


def test_link_is_dead_after_the_email_address_changes(django_user_model):
    register()
    token = token_from_outbox()
    user = django_user_model.objects.get(email="new.admin@example.com")
    user.email = "different@example.com"
    user.save()
    assert APIClient().post(VERIFY, {"token": token}, format="json").status_code == 400


def test_deactivated_user_cannot_verify(django_user_model):
    register()
    token = token_from_outbox()
    django_user_model.objects.filter(email="new.admin@example.com").update(is_active=False)
    assert APIClient().post(VERIFY, {"token": token}, format="json").status_code == 400


def test_resend_sends_a_new_email_to_unverified_users(django_user_model):
    body = register().json()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    assert client.post(RESEND).status_code == 202
    assert len(mail.outbox) == 2


def test_resend_does_nothing_for_verified_users(user):
    assert authenticated_client(user).post(RESEND).status_code == 202
    assert len(mail.outbox) == 0


def test_resend_requires_login():
    assert APIClient().post(RESEND).status_code == 401


def test_registration_still_succeeds_when_the_mail_server_is_down(settings):
    settings.EMAIL_BACKEND = "tests.support.broken_mail.BrokenBackend"
    assert register().status_code == 201
