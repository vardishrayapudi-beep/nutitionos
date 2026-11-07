"""Guards the 'secure by default' API configuration and the shared error format."""
import pytest
from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

factory = APIRequestFactory()


class _UnprotectedByDeveloperView(APIView):
    """Simulates a future endpoint where a developer forgot to set permissions."""

    def get(self, request):
        return Response({"secret": "patient data"})


class _InvalidView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise serializers.ValidationError({"email": ["This field is required."]})


def test_default_permission_is_authenticated():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]


@pytest.mark.django_db
def test_endpoint_without_explicit_permissions_rejects_anonymous_users():
    response = _UnprotectedByDeveloperView.as_view()(factory.get("/x/"))
    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"
    assert "patient data" not in str(response.data)


def test_validation_errors_use_standard_envelope():
    response = _InvalidView.as_view()(factory.post("/x/", {}, format="json"))
    assert response.status_code == 400
    error = response.data["error"]
    assert error["code"] == "validation_error"
    assert error["details"] == {"email": ["This field is required."]}


@pytest.mark.django_db
def test_jwt_settings_rotate_and_blacklist_refresh_tokens():
    jwt = settings.SIMPLE_JWT
    assert jwt["ROTATE_REFRESH_TOKENS"] is True
    assert jwt["BLACKLIST_AFTER_ROTATION"] is True
    assert jwt["ACCESS_TOKEN_LIFETIME"].total_seconds() <= 15 * 60


def test_api_docs_exposed_in_development_only_by_default():
    from config.settings import base

    assert base.API_DOCS_ENABLED is False
    assert settings.API_DOCS_ENABLED is True  # development settings in use for tests


def test_production_password_hasher_is_pbkdf2():
    from config.settings import base

    assert base.PASSWORD_HASHERS == ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]


def test_client_ip_never_comes_from_a_spoofable_header_by_default():
    """NUM_PROXIES=None would make DRF trust X-Forwarded-For and defeat all rate limits."""
    assert settings.REST_FRAMEWORK["NUM_PROXIES"] == 0


def test_auth_endpoints_have_dedicated_throttle_rates():
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope in ("auth_login", "auth_register", "auth_token_refresh", "auth_logout"):
        assert scope in rates
