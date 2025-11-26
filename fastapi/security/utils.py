"""Security utilities stub matching FastAPI's interface."""

from __future__ import annotations

from typing import Tuple


def get_authorization_scheme_param(
    authorization_header_value: str | None,
) -> Tuple[str, str]:
    """Parse an Authorization header into scheme and credentials.

    Matches the behavior of ``fastapi.security.utils.get_authorization_scheme_param``.

    Args:
        authorization_header_value: The value of the Authorization header,
            e.g., "Bearer token123" or "Basic dXNlcjpwYXNz".

    Returns:
        A tuple of (scheme, credentials). Both are empty strings if the header
        is missing or malformed.
    """
    if not authorization_header_value:
        return "", ""

    parts = authorization_header_value.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


__all__ = ["get_authorization_scheme_param"]
