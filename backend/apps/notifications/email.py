"""Transactional emails. Each function returns True/False and NEVER raises: a mail-server hiccup
must not turn a successful registration or invitation into an error (the user can resend)."""
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _frontend_link(path: str, **params) -> str:
    query = f"?{urlencode(params)}" if params else ""
    return f"{settings.FRONTEND_BASE_URL}/{path.lstrip('/')}{query}"


def _send(kind: str, to_email: str, subject: str, body: str) -> bool:
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 - deliberately broad, see module docstring
        logger.exception("Could not send %s email", kind)  # recipient intentionally not logged
        return False


def send_verification_email(user, token: str) -> bool:
    link = _frontend_link("verify-email", token=token)
    body = (
        f"Hello {user.first_name or ''},\n\n"
        "Please confirm your email address to finish setting up your Nutrition OS account:\n\n"
        f"{link}\n\n"
        "This link works for 3 days. If you did not create an account, ignore this email.\n"
    )
    return _send("verification", user.email, "Confirm your Nutrition OS email address", body)


def send_password_reset_email(user, uid: str, token: str) -> bool:
    link = _frontend_link("reset-password", uid=uid, token=token)
    body = (
        f"Hello {user.first_name or ''},\n\n"
        "We received a request to reset your Nutrition OS password. Use this link within 1 hour:\n\n"
        f"{link}\n\n"
        "If you did not ask for this, you can ignore this email - your password will not change.\n"
    )
    return _send("password_reset", user.email, "Reset your Nutrition OS password", body)


def send_invitation_email(*, to_email: str, clinic_name: str, inviter_name: str, role_label: str,
                          raw_token: str, valid_days: int) -> bool:
    link = _frontend_link("accept-invitation", token=raw_token)
    body = (
        f"{inviter_name or 'A colleague'} invited you to join {clinic_name} on Nutrition OS "
        f"as {role_label}.\n\nAccept the invitation here:\n\n{link}\n\n"
        f"This invitation expires in {valid_days} days. If you were not expecting it, ignore this email.\n"
    )
    return _send("invitation", to_email, f"You're invited to join {clinic_name} on Nutrition OS", body)
