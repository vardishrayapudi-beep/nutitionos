"""Tenant resolution: which clinic is this request acting for?

Rules (the multi-tenancy contract - see docs/architecture.md):

1. The clinic is derived from the authenticated user's ACTIVE membership in an ACTIVE clinic.
2. A clinic id supplied by the client is never trusted. The optional ``X-Clinic-Id`` header is
   only a *selector* among the user's own memberships (for people who work at several clinics)
   and is always validated against them.
3. If the selected clinic is not one of the user's active memberships, the answer is the same
   whether that clinic exists or not, so nothing about other tenants leaks.
"""
import uuid

from rest_framework.exceptions import APIException, NotAuthenticated, ParseError, PermissionDenied

from .models import Membership

CLINIC_HEADER = "X-Clinic-Id"
_CLINIC_META_KEY = "HTTP_X_CLINIC_ID"
_CACHE_ATTR = "_tenant_membership"


class EmailNotVerified(PermissionDenied):
    default_detail = "Please verify your email address before using clinic features."
    default_code = "email_not_verified"


class NoActiveMembership(PermissionDenied):
    default_detail = "You do not have an active membership in any clinic."
    default_code = "no_active_membership"


class ClinicAccessDenied(PermissionDenied):
    default_detail = "You do not have access to the selected clinic."
    default_code = "clinic_access_denied"


class ClinicSelectionRequired(APIException):
    status_code = 400
    default_detail = (
        f"You belong to more than one clinic. Send the {CLINIC_HEADER} header to choose one."
    )
    default_code = "clinic_selection_required"


class InvalidClinicHeader(ParseError):
    default_detail = f"The {CLINIC_HEADER} header must be a valid clinic id."
    default_code = "invalid_clinic_header"


def active_memberships_for(user):
    """A user's usable memberships: active membership, in an active clinic."""
    return Membership.objects.filter(
        user=user,
        status=Membership.Status.ACTIVE,
        clinic__is_active=True,
    ).select_related("clinic")


def resolve_membership(request) -> Membership:
    user = request.user
    if not user or not user.is_authenticated:
        raise NotAuthenticated()
    if not user.is_email_verified:
        raise EmailNotVerified()

    memberships = list(active_memberships_for(user))
    if not memberships:
        raise NoActiveMembership()

    selected = request.META.get(_CLINIC_META_KEY)
    if selected:
        try:
            clinic_id = uuid.UUID(selected.strip())
        except ValueError:
            raise InvalidClinicHeader()
        for membership in memberships:
            if membership.clinic_id == clinic_id:
                return membership
        raise ClinicAccessDenied()

    if len(memberships) == 1:
        return memberships[0]
    raise ClinicSelectionRequired()


def get_request_membership(request) -> Membership:
    """Resolve once per request and cache, so permissions and views share one DB query."""
    membership = getattr(request, _CACHE_ATTR, None)
    if membership is None:
        membership = resolve_membership(request)
        setattr(request, _CACHE_ATTR, membership)
    return membership


def get_request_clinic(request):
    return get_request_membership(request).clinic
