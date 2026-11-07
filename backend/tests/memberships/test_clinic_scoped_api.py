"""End-to-end proof of tenant isolation through real HTTP requests with real JWTs.

Uses a test-only API (tests/support/tenancy_views.py) built on the same mixin and permission
classes that real endpoints will use.
"""
import pytest
from rest_framework_simplejwt.tokens import AccessToken

from apps.memberships.models import Membership
from tests.support.api import assert_clinic_isolation, authenticated_client

pytestmark = pytest.mark.django_db

LIST_URL = "/test-api/memberships/"


@pytest.fixture(autouse=True)
def _use_test_urlconf(settings):
    settings.ROOT_URLCONF = "tests.support.urls"


def detail_url(membership_id):
    return f"{LIST_URL}{membership_id}/"


def rows(response):
    return {row["id"] for row in response.json()["results"]}


def membership_of(person, clinic):
    return Membership.objects.get(user=person, clinic=clinic)


# --- authentication and tenant resolution at the HTTP layer ---------------------------------

def test_anonymous_request_is_rejected(client):
    response = client.get(LIST_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_user_with_no_membership_is_rejected(make_user):
    response = authenticated_client(make_user()).get(LIST_URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "no_active_membership"


def test_members_only_see_their_own_clinic(admin_a, doctor_a, admin_b, clinic_a):
    response = authenticated_client(admin_a).get(LIST_URL)
    assert response.status_code == 200
    assert rows(response) == {
        str(membership_of(admin_a, clinic_a).id),
        str(membership_of(doctor_a, clinic_a).id),
    }


def test_clinic_in_query_string_is_ignored(admin_a, admin_b, clinic_a, clinic_b):
    """A client cannot widen its view by passing ?clinic=<someone else>."""
    response = authenticated_client(admin_a).get(LIST_URL, {"clinic": str(clinic_b.id)})
    assert response.status_code == 200
    assert str(membership_of(admin_b, clinic_b).id) not in rows(response)


# --- the reusable cross-clinic isolation check ----------------------------------------------

def test_clinic_isolation_for_membership_resource(admin_a, doctor_a, admin_b, clinic_a):
    target = membership_of(doctor_a, clinic_a)
    assert_clinic_isolation(
        owner_client=authenticated_client(admin_a),
        intruder_client=authenticated_client(admin_b),
        list_url=LIST_URL,
        detail_url=detail_url(target.id),
        owned_id=target.id,
        update_payload={"role": "staff"},
    )
    target.refresh_from_db()
    assert target.role == Membership.Role.DOCTOR  # the intruder's PATCH changed nothing


# --- creating records -----------------------------------------------------------------------

def test_clinic_comes_from_the_server_not_the_request_body(
    admin_a, make_user, clinic_a, clinic_b
):
    newcomer = make_user()
    response = authenticated_client(admin_a).post(
        LIST_URL,
        {"user": str(newcomer.id), "role": "staff", "status": "invited", "clinic": str(clinic_b.id)},
        format="json",
    )
    assert response.status_code == 201
    created = Membership.objects.get(id=response.json()["id"])
    assert created.clinic == clinic_a  # NOT clinic_b, despite what the client sent


def test_role_permissions_doctor_can_read_but_not_write(doctor_a, make_user):
    client = authenticated_client(doctor_a)
    assert client.get(LIST_URL).status_code == 200
    response = client.post(
        LIST_URL, {"user": str(make_user().id), "role": "staff", "status": "active"}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


# --- access revocation takes effect immediately ---------------------------------------------

def test_suspending_a_membership_blocks_an_already_issued_token(admin_a, clinic_a):
    client = authenticated_client(admin_a)  # token issued while the user was active
    assert client.get(LIST_URL).status_code == 200

    Membership.objects.filter(user=admin_a, clinic=clinic_a).update(
        status=Membership.Status.SUSPENDED
    )
    response = client.get(LIST_URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "no_active_membership"


def test_deactivating_a_clinic_blocks_all_its_members(admin_a, clinic_a):
    client = authenticated_client(admin_a)
    clinic_a.is_active = False
    clinic_a.save()
    assert client.get(LIST_URL).status_code == 403


def test_deactivated_user_cannot_use_an_existing_token(admin_a):
    client = authenticated_client(admin_a)
    admin_a.is_active = False
    admin_a.save()
    assert client.get(LIST_URL).status_code == 401


def test_invited_but_not_accepted_membership_grants_nothing(make_user, make_membership, clinic_a):
    person = make_user()
    make_membership(person, clinic_a, status=Membership.Status.INVITED)
    assert authenticated_client(person).get(LIST_URL).status_code == 403


# --- people who work at more than one clinic ------------------------------------------------

@pytest.fixture
def visiting_doctor(make_user, make_membership, clinic_a, clinic_b, admin_a, admin_b):
    person = make_user("visiting@example.com")
    make_membership(person, clinic_a, Membership.Role.DOCTOR)
    make_membership(person, clinic_b, Membership.Role.DOCTOR)
    return person


def test_multi_clinic_user_must_choose_a_clinic(visiting_doctor):
    response = authenticated_client(visiting_doctor).get(LIST_URL)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "clinic_selection_required"


def test_header_switches_between_clinics_without_mixing_data(
    visiting_doctor, admin_a, admin_b, clinic_a, clinic_b
):
    in_a = rows(authenticated_client(visiting_doctor, clinic_a).get(LIST_URL))
    in_b = rows(authenticated_client(visiting_doctor, clinic_b).get(LIST_URL))
    assert str(membership_of(admin_a, clinic_a).id) in in_a
    assert str(membership_of(admin_b, clinic_b).id) not in in_a
    assert str(membership_of(admin_b, clinic_b).id) in in_b
    assert str(membership_of(admin_a, clinic_a).id) not in in_b
    assert in_a.isdisjoint(in_b)


def test_role_is_evaluated_per_clinic(make_user, make_membership, clinic_a, clinic_b, admin_a, admin_b):
    person = make_user()
    make_membership(person, clinic_a, Membership.Role.CLINIC_ADMIN)
    make_membership(person, clinic_b, Membership.Role.STAFF)
    payload = lambda: {"user": str(make_user().id), "role": "staff", "status": "invited"}  # noqa: E731
    assert authenticated_client(person, clinic_a).post(LIST_URL, payload(), format="json").status_code == 201
    assert authenticated_client(person, clinic_b).post(LIST_URL, payload(), format="json").status_code == 403


def test_foreign_and_nonexistent_clinics_are_indistinguishable(admin_a, clinic_b):
    import uuid

    foreign = authenticated_client(admin_a, clinic_b).get(LIST_URL)
    nonexistent = authenticated_client(admin_a).get(LIST_URL, HTTP_X_CLINIC_ID=str(uuid.uuid4()))
    assert foreign.status_code == nonexistent.status_code == 403
    assert foreign.json() == nonexistent.json()


def test_malformed_clinic_header_returns_400(admin_a):
    response = authenticated_client(admin_a).get(LIST_URL, HTTP_X_CLINIC_ID="nope")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_clinic_header"


# --- token hygiene --------------------------------------------------------------------------

def test_jwt_contains_no_clinic_role_or_personal_data(admin_a):
    payload = AccessToken.for_user(admin_a).payload
    assert set(payload) <= {"token_type", "exp", "iat", "jti", "user_id"}
    assert admin_a.email not in str(payload)


# --- schema generation does not need a request ----------------------------------------------

def test_mixin_is_safe_during_openapi_schema_generation():
    from tests.support.tenancy_views import MembershipTestViewSet

    view = MembershipTestViewSet()
    view.swagger_fake_view = True
    assert view.get_queryset().count() == 0
