from rest_framework.permissions import BasePermission

from .models import Membership
from .tenancy import get_request_membership


class HasActiveClinicMembership(BasePermission):
    """The caller is logged in AND acting for a clinic they actively belong to.

    Tenant-resolution errors (no membership, ambiguous clinic, ...) are raised as API errors
    with specific codes instead of a bare 403.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        get_request_membership(request)
        return True


class ClinicRolePermission(BasePermission):
    """Base class: allow only members whose role in the ACTIVE clinic is in ``allowed_roles``."""

    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return get_request_membership(request).role in self.allowed_roles


class IsClinicAdmin(ClinicRolePermission):
    allowed_roles = (Membership.Role.CLINIC_ADMIN,)


class IsClinicDoctor(ClinicRolePermission):
    allowed_roles = (Membership.Role.DOCTOR,)


class IsClinicAdminOrDoctor(ClinicRolePermission):
    allowed_roles = (Membership.Role.CLINIC_ADMIN, Membership.Role.DOCTOR)
