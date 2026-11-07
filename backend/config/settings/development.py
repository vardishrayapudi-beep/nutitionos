"""Local development settings."""
from config import env

from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = env.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-do-not-use-in-production")
ALLOWED_HOSTS = env.get_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
API_DOCS_ENABLED = True
