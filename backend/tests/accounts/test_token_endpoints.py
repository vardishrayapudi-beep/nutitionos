import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/token/"
REFRESH = "/api/v1/auth/token/refresh/"
LOGOUT = "/api/v1/auth/logout/"


def post(url, data=None, **extra):
    return APIClient().post(url, data or {}, format="json", **extra)


def login(email, password):
    return post(LOGIN, {"email": email, "password": password})


# --- login ----------------------------------------------------------------------------------

def test_login_returns_access_and_refresh_tokens(user, user_password):
    response = login("doctor@example.com", user_password)
    assert response.status_code == 200
    assert set(response.json()) == {"access", "refresh"}


def test_login_email_is_case_insensitive(user, user_password):
    assert login("  DOCTOR@Example.COM ", user_password).status_code == 200


def test_login_records_last_login(user, user_password):
    assert user.last_login is None
    login("doctor@example.com", user_password)
    user.refresh_from_db()
    assert user.last_login is not None


def test_wrong_password_and_unknown_email_are_indistinguishable(user):
    """No user enumeration: the response must not reveal whether the email exists."""
    wrong_password = login("doctor@example.com", "Not-The-Password-1")
    unknown_email = login("nobody@example.com", "Not-The-Password-1")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "no_active_account"


def test_deactivated_user_cannot_log_in(user, user_password):
    user.is_active = False
    user.save()
    assert login("doctor@example.com", user_password).status_code == 401


def test_user_without_any_clinic_can_still_log_in(make_user, user_password):
    person = make_user("loner@example.com")
    assert login(person.email, user_password).status_code == 200


def test_missing_credentials_give_a_validation_error():
    response = post(LOGIN, {})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_tokens_carry_only_the_user_id(user, user_password):
    tokens = login("doctor@example.com", user_password).json()
    for token_class, token in ((AccessToken, tokens["access"]), (RefreshToken, tokens["refresh"])):
        payload = token_class(token).payload
        assert set(payload) <= {"token_type", "exp", "iat", "jti", "user_id"}
        assert payload["user_id"] == str(user.id)
        assert user.email not in str(payload)


def test_login_response_never_echoes_the_password(user, user_password):
    assert user_password not in login("doctor@example.com", user_password).content.decode()


def test_login_is_rate_limited_per_client_even_with_spoofed_forwarding_headers(user):
    """Brute-force protection. Rotating a fake X-Forwarded-For must NOT reset the counter."""
    attempts = [
        post(LOGIN, {"email": "doctor@example.com", "password": "Wrong-Password-1"},
             HTTP_X_FORWARDED_FOR=f"203.0.113.{i}")
        for i in range(10)
    ]
    assert {r.status_code for r in attempts} == {401}

    blocked = post(LOGIN, {"email": "doctor@example.com", "password": "Wrong-Password-1"},
                   HTTP_X_FORWARDED_FOR="198.51.100.77")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "throttled"


# --- refresh --------------------------------------------------------------------------------

def tokens_for(user, user_password):
    return login(user.email, user_password).json()


def test_refresh_rotates_the_refresh_token(user, user_password):
    original = tokens_for(user, user_password)
    response = post(REFRESH, {"refresh": original["refresh"]})
    assert response.status_code == 200
    rotated = response.json()
    assert rotated["access"] and rotated["refresh"]
    assert rotated["refresh"] != original["refresh"]


def test_a_used_refresh_token_cannot_be_used_again(user, user_password):
    original = tokens_for(user, user_password)
    assert post(REFRESH, {"refresh": original["refresh"]}).status_code == 200
    replay = post(REFRESH, {"refresh": original["refresh"]})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "token_not_valid"


def test_the_new_refresh_token_keeps_working(user, user_password):
    first = post(REFRESH, {"refresh": tokens_for(user, user_password)["refresh"]}).json()
    assert post(REFRESH, {"refresh": first["refresh"]}).status_code == 200


def test_deactivated_user_cannot_refresh(user, user_password):
    original = tokens_for(user, user_password)
    user.is_active = False
    user.save()
    assert post(REFRESH, {"refresh": original["refresh"]}).status_code == 401


def test_garbage_refresh_token_is_rejected():
    assert post(REFRESH, {"refresh": "definitely.not.ajwt"}).status_code == 401


def test_an_access_token_is_not_accepted_as_a_refresh_token(user, user_password):
    access = tokens_for(user, user_password)["access"]
    assert post(REFRESH, {"refresh": access}).status_code == 401


# --- logout ---------------------------------------------------------------------------------

def test_logout_revokes_the_refresh_token(user, user_password):
    tokens = tokens_for(user, user_password)
    assert post(LOGOUT, {"refresh": tokens["refresh"]}).status_code == 204
    assert post(REFRESH, {"refresh": tokens["refresh"]}).status_code == 401


def test_logout_is_idempotent(user, user_password):
    tokens = tokens_for(user, user_password)
    assert post(LOGOUT, {"refresh": tokens["refresh"]}).status_code == 204
    assert post(LOGOUT, {"refresh": tokens["refresh"]}).status_code == 204


def test_logout_with_an_invalid_token_is_a_harmless_204():
    assert post(LOGOUT, {"refresh": "garbage"}).status_code == 204


def test_logout_requires_the_refresh_field():
    response = post(LOGOUT, {})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
