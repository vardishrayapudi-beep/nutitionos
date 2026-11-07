"""Stateless, expiring tokens for email verification (signed with SECRET_KEY)."""
from django.conf import settings
from django.core import signing

_SALT = "accounts.email-verification.v1"


def make_email_verification_token(user) -> str:
    # Binding the current email means changing the address invalidates any older link.
    return signing.dumps({"u": str(user.pk), "e": user.email}, salt=_SALT)


def read_email_verification_token(token: str) -> dict:
    """Return the payload or raise ``signing.BadSignature`` (includes SignatureExpired)."""
    return signing.loads(token, salt=_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS)
