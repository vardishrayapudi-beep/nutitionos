import pytest
from django.db import OperationalError
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health_ok_without_authentication(client):
    response = client.get(reverse("common:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_returns_503_when_database_down(client, monkeypatch):
    def boom(*args, **kwargs):
        raise OperationalError("simulated outage")

    monkeypatch.setattr("apps.common.views.connection.cursor", boom)
    response = client.get(reverse("common:health"))
    assert response.status_code == 503
    assert response.json()["database"] == "down"
