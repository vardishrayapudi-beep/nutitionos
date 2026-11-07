"""The one function the rest of the code base uses to write audit events."""
from rest_framework.throttling import BaseThrottle

from .models import AuditLog

# Keys that must never appear in audit metadata (sensitive personal / secret content).
FORBIDDEN_METADATA_KEYS = frozenset({
    "password", "new_password", "old_password", "token", "access", "refresh", "secret",
    "email", "phone", "name", "first_name", "last_name", "full_name", "date_of_birth", "dob",
    "address", "note", "notes", "text",
})


def _clean_metadata(metadata: dict) -> dict:
    bad = FORBIDDEN_METADATA_KEYS.intersection(k.lower() for k in metadata)
    if bad:
        raise ValueError(f"Audit metadata must not contain sensitive keys: {sorted(bad)}")
    return metadata


def record(*, action, request=None, clinic=None, actor=None, actor_type=None,
           target=None, target_type="", target_id="", **metadata) -> AuditLog:
    """Write one audit event.

    Missing details are filled in from ``request`` when given: the authenticated user, the
    clinic resolved for that request, the client address and the request id.
    """
    _clean_metadata(metadata)

    ip_address = request_id = None
    if request is not None:
        user = getattr(request, "user", None)
        if actor is None and user is not None and getattr(user, "is_authenticated", False) \
                and hasattr(user, "pk") and user.__class__.__name__ != "PortalPrincipal":
            actor = user
        if clinic is None:
            membership = getattr(request, "_tenant_membership", None)
            clinic = membership.clinic if membership is not None else None
        ip_address = BaseThrottle().get_ident(request) or None
        request_id = getattr(request, "request_id", None) or getattr(
            getattr(request, "_request", None), "request_id", None
        )

    if target is not None:
        target_type = target_type or target.__class__.__name__
        target_id = target_id or str(target.pk)

    if actor_type is None:
        actor_type = "user" if actor is not None else "system"

    return AuditLog.objects.create(
        action=action,
        clinic=clinic,
        actor=actor,
        actor_type=actor_type,
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        metadata=metadata,
        ip_address=ip_address,
        request_id=request_id or "",
    )
