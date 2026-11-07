"""Production settings. Everything sensitive must come from environment variables."""
from django.core.exceptions import ImproperlyConfigured

from config import env

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = env.get("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = env.get_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

API_DOCS_ENABLED = env.get_bool("API_DOCS_ENABLED", default=False)

# --- HTTPS and cookie hardening ---
SECURE_SSL_REDIRECT = True
# Only correct when running behind a reverse proxy that sets X-Forwarded-Proto and strips
# any client-supplied value. Revisit when the deployment target is chosen (Sprint 7).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Ramp HSTS up gradually: start at 1 hour, raise to 31536000 (1 year) once HTTPS is proven.
SECURE_HSTS_SECONDS = env.get_int("SECURE_HSTS_SECONDS", 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.get_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
