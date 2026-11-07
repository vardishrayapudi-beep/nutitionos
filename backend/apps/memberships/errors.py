from rest_framework.exceptions import APIException


class InvitationInvalid(APIException):
    """Deliberately one message for unknown / expired / revoked / used tokens (no probing)."""

    status_code = 400
    default_detail = "This invitation is invalid or has expired."
    default_code = "invalid_invitation"


class AlreadyMember(APIException):
    status_code = 409
    default_detail = "This person is already an active member of the clinic."
    default_code = "already_member"


class LastAdminError(APIException):
    status_code = 409
    default_detail = "A clinic must always keep at least one active administrator."
    default_code = "last_admin"


class LoginRequired(APIException):
    status_code = 400
    default_detail = "An account with this email already exists. Log in first, then accept the invitation."
    default_code = "login_required"


class WrongAccount(APIException):
    status_code = 403
    default_detail = "This invitation was sent to a different email address."
    default_code = "invitation_wrong_account"
