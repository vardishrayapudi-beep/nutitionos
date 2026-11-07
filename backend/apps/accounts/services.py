from django.contrib.auth import get_user_model
from django.core import signing
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from . import tokens

User = get_user_model()


def revoke_all_sessions(user) -> int:
    """Blacklist every outstanding refresh token of the user. Returns how many were revoked.

    Access tokens already issued remain valid until they expire (max 15 minutes).
    """
    revoked = 0
    for outstanding in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=outstanding)
        revoked += int(created)
    return revoked


def verify_email(token: str):
    """Mark the email in a valid verification token as verified. Returns the user or None."""
    try:
        data = tokens.read_email_verification_token(token)
    except signing.BadSignature:
        return None
    user = User.objects.filter(pk=data.get("u"), email=data.get("e"), is_active=True).first()
    if user is None:
        return None
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
    return user
