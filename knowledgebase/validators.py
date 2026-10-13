import re

from django.core.exceptions import ValidationError

from .constants import DocumentStatus

_EXTERNAL_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def clean_external_user_id(value):
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    if not _EXTERNAL_ID.fullmatch(value):
        raise ValueError("Invalid external user id")
    return value


def validate_status(value):
    if value not in DocumentStatus.values:
        raise ValidationError(
            "Invalid status %(value)r. Allowed: %(allowed)s.",
            code="invalid_status",
            params={"value": value, "allowed": ", ".join(DocumentStatus.values)},
        )


def validate_status_transition(current, new):
    validate_status(new)
    if current == DocumentStatus.REMOVED and new != DocumentStatus.REMOVED:
        raise ValidationError(
            "A REMOVED document cannot change to %(new)s.",
            code="invalid_transition",
            params={"new": new},
        )
