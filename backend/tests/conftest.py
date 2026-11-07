import pytest


@pytest.fixture
def user_password():
    return "Str0ng-Test-Passw0rd!"


@pytest.fixture
def user(django_user_model, user_password):
    return django_user_model.objects.create_user(
        email="doctor@example.com",
        password=user_password,
        first_name="Asha",
        last_name="Rao",
    )


@pytest.fixture
def superuser(django_user_model, user_password):
    return django_user_model.objects.create_superuser(
        email="root@example.com",
        password=user_password,
        first_name="Platform",
        last_name="Operator",
    )


# ---------------------------------------------------------------------------
# Multi-tenant fixtures (Sprint 1, Day 2)
# ---------------------------------------------------------------------------
import itertools  # noqa: E402

from django.core.cache import cache  # noqa: E402

from apps.clinics.models import Clinic  # noqa: E402
from apps.memberships.models import Membership  # noqa: E402
from tests.support.api import authenticated_client  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """Throttle counters live in the cache; never let one test's requests affect another."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_clinic(db):
    counter = itertools.count(1)

    def _make(name=None, **kwargs):
        n = next(counter)
        kwargs.setdefault("email", f"clinic{n}@example.com")
        return Clinic.objects.create(name=name or f"Test Clinic {n}", **kwargs)

    return _make


@pytest.fixture
def make_user(django_user_model, user_password):
    counter = itertools.count(1)

    def _make(email=None, **kwargs):
        n = next(counter)
        return django_user_model.objects.create_user(
            email=email or f"person{n}@example.com", password=user_password, **kwargs
        )

    return _make


@pytest.fixture
def make_membership(db):
    def _make(user, clinic, role=Membership.Role.STAFF, status=Membership.Status.ACTIVE):
        return Membership.objects.create(user=user, clinic=clinic, role=role, status=status)

    return _make


@pytest.fixture
def api_client_for():
    return authenticated_client


@pytest.fixture
def clinic_a(make_clinic):
    return make_clinic("Clinic A")


@pytest.fixture
def clinic_b(make_clinic):
    return make_clinic("Clinic B")


@pytest.fixture
def admin_a(make_user, make_membership, clinic_a):
    person = make_user("admin.a@example.com")
    make_membership(person, clinic_a, Membership.Role.CLINIC_ADMIN)
    return person


@pytest.fixture
def doctor_a(make_user, make_membership, clinic_a):
    person = make_user("doctor.a@example.com")
    make_membership(person, clinic_a, Membership.Role.DOCTOR)
    return person


@pytest.fixture
def admin_b(make_user, make_membership, clinic_b):
    person = make_user("admin.b@example.com")
    make_membership(person, clinic_b, Membership.Role.CLINIC_ADMIN)
    return person
