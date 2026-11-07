"""Reusable helpers for API tests. Every future clinic-owned endpoint should be covered by
``assert_clinic_isolation`` - that is how "a clinic must never access another clinic's records"
is enforced automatically from now on."""
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken


def authenticated_client(user, clinic=None) -> APIClient:
    """An API client logged in with a real JWT (so the whole auth path is exercised)."""
    credentials = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}
    if clinic is not None:
        credentials["HTTP_X_CLINIC_ID"] = str(clinic.id)
    client = APIClient()
    client.credentials(**credentials)
    return client


def assert_clinic_isolation(*, owner_client, intruder_client, list_url, detail_url, owned_id,
                            update_payload=None):
    """Assert that ``intruder_client`` (another clinic) can neither see nor touch a resource
    that belongs to ``owner_client``'s clinic, and that the resource is left unharmed."""
    owned_id = str(owned_id)

    # The owner can see their own resource.
    owner_rows = owner_client.get(list_url).json()["results"]
    assert owned_id in {row["id"] for row in owner_rows}, "owner cannot see own resource"
    assert owner_client.get(detail_url).status_code == 200

    # The intruder cannot see it in lists...
    intruder_response = intruder_client.get(list_url)
    assert intruder_response.status_code == 200
    assert owned_id not in {row["id"] for row in intruder_response.json()["results"]}, \
        "LEAK: other clinic's resource appears in a list"

    # ...and every direct access is "not found" (404, never 403 - existence is not revealed).
    assert intruder_client.get(detail_url).status_code == 404
    assert intruder_client.patch(detail_url, update_payload or {}, format="json").status_code == 404
    assert intruder_client.delete(detail_url).status_code == 404

    # The failed attacks changed nothing.
    assert owner_client.get(detail_url).status_code == 200
