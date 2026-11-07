import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_admin_changelist_loads_for_superuser(client, superuser):
    client.force_login(superuser)
    response = client.get(reverse("admin:accounts_user_changelist"))
    assert response.status_code == 200


def test_admin_add_user_form_creates_user_with_normalised_email(client, superuser, django_user_model):
    client.force_login(superuser)
    url = reverse("admin:accounts_user_add")
    assert client.get(url).status_code == 200

    response = client.post(url, {
        "email": "New.Person@Example.com",
        "first_name": "New",
        "last_name": "Person",
        "password1": "Another-Str0ng-Pass!",
        "password2": "Another-Str0ng-Pass!",
    })
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="new.person@example.com").exists()


def test_admin_is_forbidden_for_non_staff_user(client, user):
    client.force_login(user)
    response = client.get(reverse("admin:accounts_user_changelist"))
    assert response.status_code == 302  # redirected to admin login, not granted access
    assert "login" in response["Location"]
