"""Settings shared by every environment. Environment-specific files import * from here."""
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # -> backend/

# Reads backend/.env if present. Real environment variables always take precedence.
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # ArrayField etc.
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # needed for refresh-token rotation/revocation
    "drf_spectacular",
    "django_filters",
    # Local
    "apps.common",
    "apps.accounts",
    "apps.clinics",
    "apps.memberships",
    "apps.doctors",
    "apps.patients",
    "apps.audit",
    "apps.notifications",
]

AUTH_USER_MODEL = "accounts.User"  # MUST be set before the first migration is ever run

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database (PostgreSQL only - no SQLite fallback, so dev behaves like production)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.get("DB_NAME", "nutrition_os"),
        "USER": env.get("DB_USER", "nutrition_os"),
        "PASSWORD": env.get("DB_PASSWORD", required=True),
        "HOST": env.get("DB_HOST", "localhost"),
        "PORT": env.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"  # our own models use UUIDs explicitly

# ---------------------------------------------------------------------------
# Authentication / passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Password-reset links stay valid for one hour only.
PASSWORD_RESET_TIMEOUT = 3600

# One strong hasher, listed explicitly (a new project has no legacy hashes to keep verifying).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]

# JWTs carry ONLY the user id - never medical or personal details.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# Django REST Framework - secure by default
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Every endpoint requires login unless it explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        # Stricter limits for credential-related endpoints (see apps/accounts/views.py)
        "auth_login": "10/min",
        "auth_register": "5/hour",
        "auth_token_refresh": "30/min",
        "auth_logout": "30/min",
        "auth_verify_email": "20/hour",
        "auth_password_reset": "5/hour",
        "auth_password_change": "10/hour",
        "auth_invitation_accept": "10/hour",
    },
    # How many trusted reverse proxies sit in front of Django. 0 = trust only the TCP peer address.
    # NEVER leave this unset: DRF would then trust a client-supplied X-Forwarded-For header, and
    # anyone could dodge every rate limit by sending a different fake value on each request.
    "NUM_PROXIES": env.get_int("NUM_PROXIES", 0),
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Nutrition OS API",
    "DESCRIPTION": "Clinic-based medical nutrition management platform.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Several models share a "status" field with different choices; give each enum a stable name.
    "ENUM_NAME_OVERRIDES": {
        "MembershipStatusEnum": "apps.memberships.models.Membership.Status",
        "MembershipRoleEnum": "apps.memberships.models.Membership.Role",
        "ConsentMethodEnum": "apps.patients.models.Patient.ConsentMethod",
        "ConsentStatusEnum": "apps.patients.models.Patient.Consent",
    },
}

# Interactive API docs are only exposed where explicitly enabled (see urls.py).
API_DOCS_ENABLED = False
ADMIN_URL = env.get("DJANGO_ADMIN_URL", "admin/")

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True  # store everything as UTC in the database

# ---------------------------------------------------------------------------
# Static files (private patient photos will NOT live here - see roadmap Sprint 6)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Logging - console only. Never log request bodies, tokens or patient data.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---------------------------------------------------------------------------
# Email (verification, invitations, password reset)
# ---------------------------------------------------------------------------
# Development prints emails to the console; production must configure real SMTP (see production.py).
EMAIL_BACKEND = env.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env.get("EMAIL_HOST", "localhost")
EMAIL_PORT = env.get_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env.get_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env.get("DEFAULT_FROM_EMAIL", "Nutrition OS <no-reply@localhost>")
# Where the web frontend lives; used to build links inside emails.
FRONTEND_BASE_URL = env.get("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
EMAIL_VERIFICATION_MAX_AGE_SECONDS = 3 * 24 * 3600
INVITATION_VALID_DAYS = env.get_int("INVITATION_VALID_DAYS", 7)
