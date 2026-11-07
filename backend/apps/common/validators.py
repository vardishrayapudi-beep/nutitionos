import re

from django.core.exceptions import ValidationError

_PHONE_CLEAN = re.compile(r"[\s\-().]")


def normalize_phone(value: str, default_country_code: str = "91") -> str:
    """Return an E.164 phone number (+<country><number>) or raise ValidationError.

    Accepts '+91 98765-43210', '098765 43210' or a bare 10-digit Indian number.
    """
    raw = _PHONE_CLEAN.sub("", value or "")
    if raw.startswith("+"):
        digits = raw[1:]
    elif raw.startswith("00"):
        digits = raw[2:]
    else:
        digits = raw.lstrip("0") if len(raw.lstrip("0")) == 10 else raw
        if len(digits) == 10:
            digits = default_country_code + digits
    if not digits.isdigit() or not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValidationError("Enter a valid phone number, e.g. +91 98765 43210.")
    return f"+{digits}"


POSTAL_CODE_RE = re.compile(r"^[1-9][0-9]{5}$")  # Indian PIN code
