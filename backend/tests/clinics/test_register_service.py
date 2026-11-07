"""Service-level tests: the all-or-nothing and concurrency guarantees of clinic registration."""
import pytest
from django.contrib.auth import get_user_model

from apps.clinics import models as clinic_models
from apps.clinics.models import Clinic
from apps.clinics.services import (
    SLUG_RETRY_ATTEMPTS,
    EmailAlreadyRegistered,
    RegistrationUnavailable,
    register_clinic,
)
from apps.memberships.models import Membership

pytestmark = pytest.mark.django_db
User = get_user_model()

CLINIC = {"name": "Taken Name", "email": "c@example.com", "phone": ""}
ADMIN = {"email": "admin@example.com", "password": "Correct-Horse-Battery-9",
         "first_name": "A", "last_name": "B"}


def counts():
    return User.objects.count(), Clinic.objects.count(), Membership.objects.count()


def test_success_creates_all_three_records():
    result = register_clinic(clinic_data=dict(CLINIC), admin_data=dict(ADMIN))
    assert result.membership.user == result.user
    assert result.membership.clinic == result.clinic
    assert counts() == (1, 1, 1)


def test_failure_after_user_and_clinic_creation_rolls_everything_back(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("simulated crash while creating the membership")

    monkeypatch.setattr(Membership.objects, "create", explode)
    before = counts()
    with pytest.raises(RuntimeError):
        register_clinic(clinic_data=dict(CLINIC), admin_data=dict(ADMIN))
    assert counts() == before  # no orphan user, no orphan clinic


def test_email_registered_at_the_same_instant_is_reported_cleanly(make_user):
    make_user("admin@example.com")
    before = counts()
    with pytest.raises(EmailAlreadyRegistered):
        register_clinic(clinic_data=dict(CLINIC), admin_data=dict(ADMIN))
    assert counts() == before


def test_slug_collision_from_a_simultaneous_registration_is_retried(monkeypatch, make_clinic):
    make_clinic("Taken Name")  # owns slug "taken-name"
    real = clinic_models.generate_unique_slug
    calls = []

    def losing_the_race_once(name):
        calls.append(name)
        return "taken-name" if len(calls) == 1 else real(name)  # 1st call: stale answer

    monkeypatch.setattr(clinic_models, "generate_unique_slug", losing_the_race_once)
    result = register_clinic(clinic_data=dict(CLINIC), admin_data=dict(ADMIN))

    assert len(calls) == 2
    assert result.clinic.slug == "taken-name-2"
    assert result.membership.status == Membership.Status.ACTIVE


def test_giving_up_after_repeated_collisions_leaves_nothing_behind(monkeypatch, make_clinic):
    make_clinic("Taken Name")
    monkeypatch.setattr(clinic_models, "generate_unique_slug", lambda name: "taken-name")
    before = counts()
    with pytest.raises(RegistrationUnavailable):
        register_clinic(clinic_data=dict(CLINIC), admin_data=dict(ADMIN))
    assert counts() == before
    assert SLUG_RETRY_ATTEMPTS >= 3


def test_api_reports_503_service_busy_when_retries_are_exhausted(monkeypatch, make_clinic):
    from rest_framework.test import APIClient

    make_clinic("Taken Name")
    monkeypatch.setattr(clinic_models, "generate_unique_slug", lambda name: "taken-name")
    response = APIClient().post(
        "/api/v1/auth/register-clinic/", {"clinic": CLINIC, "admin": ADMIN}, format="json"
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_busy"
    assert not User.objects.filter(email="admin@example.com").exists()
