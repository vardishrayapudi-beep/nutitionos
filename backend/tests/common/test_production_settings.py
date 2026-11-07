"""Production must fail closed: it refuses to start with missing or weak secrets."""
import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

STRONG_KEY = "k" * 60


def load_production(monkeypatch, **env):
    base_env = {
        "DJANGO_SECRET_KEY": STRONG_KEY,
        "DJANGO_ALLOWED_HOSTS": "nutritionos.example.com",
        "DB_PASSWORD": "not-empty",
    }
    base_env.update(env)
    for name, value in base_env.items():
        monkeypatch.setenv(name, value)
    # Re-execute BOTH modules: production does `from .base import *`, and base holds the
    # database-password check, so a cached base module would hide that failure.
    for module in ("config.settings.production", "config.settings.base"):
        sys.modules.pop(module, None)
    return importlib.import_module("config.settings.production")


@pytest.fixture(autouse=True)
def _discard_reloaded_settings_modules():
    yield
    for module in ("config.settings.production", "config.settings.base"):
        sys.modules.pop(module, None)


def test_valid_production_configuration_enables_https_hardening(monkeypatch):
    prod = load_production(monkeypatch)
    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS > 0
    assert prod.API_DOCS_ENABLED is False  # API surface not advertised by default


@pytest.mark.parametrize("bad_key", ["", "short", "k" * 49])
def test_missing_or_weak_secret_key_is_refused(monkeypatch, bad_key):
    with pytest.raises(ImproperlyConfigured):
        load_production(monkeypatch, DJANGO_SECRET_KEY=bad_key)


def test_missing_allowed_hosts_is_refused(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_production(monkeypatch, DJANGO_ALLOWED_HOSTS="")


def test_missing_database_password_is_refused(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_production(monkeypatch, DB_PASSWORD="")
