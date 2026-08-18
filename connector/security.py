"""Network access policy for public graphics, controls, and administration."""

from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from ipaddress import ip_address
from typing import Mapping

from connector.config import Settings


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ADMIN_API_PREFIXES = (
    "/api/configuration",
    "/api/diagnostics",
    "/api/logs",
    "/api/themes",
)


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    status_code: int = 200
    detail: str = ""


def is_local_client(host: str | None) -> bool:
    """Recognize loopback clients without trusting proxy-supplied headers."""
    if not host:
        return False
    normalized = host.split("%", 1)[0].strip().lower()
    if normalized in {"localhost", "testclient"}:
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _bearer_token(headers: Mapping[str, str]) -> str:
    authorization = headers.get("authorization", "").strip()
    scheme, _, value = authorization.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


def _matches(candidate: str, expected: str) -> bool:
    return bool(candidate and expected) and compare_digest(candidate, expected)


def _authorized(
    headers: Mapping[str, str],
    *,
    expected: str,
    header_name: str,
) -> bool:
    return _matches(headers.get(header_name, ""), expected) or _matches(
        _bearer_token(headers), expected
    )


def evaluate_http_access(
    settings: Settings,
    *,
    method: str,
    path: str,
    client_host: str | None,
    headers: Mapping[str, str],
) -> AccessDecision:
    """Return the access decision for one HTTP request.

    Read-only broadcast APIs remain reachable when an operator explicitly
    binds BBS to the LAN. Mutations and sensitive operational data require a
    loopback client or the corresponding opt-in token.
    """
    method = method.upper()
    if method == "OPTIONS" or is_local_client(client_host):
        return AccessDecision(True)

    admin_path = (
        path != "/api/configuration/public"
        and any(path.startswith(prefix) for prefix in ADMIN_API_PREFIXES)
    )
    if method in SAFE_METHODS and not admin_path:
        return AccessDecision(True)

    if admin_path:
        if not settings.remote_admin_enabled:
            return AccessDecision(
                False,
                403,
                "Remote administration is disabled.",
            )
        if not settings.admin_token:
            return AccessDecision(
                False,
                503,
                "Remote administration is enabled but no admin token is configured.",
            )
        if _authorized(
            headers,
            expected=settings.admin_token,
            header_name="x-bbs-admin-token",
        ):
            return AccessDecision(True)
        return AccessDecision(False, 401, "A valid BBS admin token is required.")

    if method not in SAFE_METHODS:
        if not settings.remote_control_enabled:
            return AccessDecision(False, 403, "Remote operator control is disabled.")
        if not settings.control_token and not settings.admin_token:
            return AccessDecision(
                False,
                503,
                "Remote operator control is enabled but no control token is configured.",
            )
        if _authorized(
            headers,
            expected=settings.control_token,
            header_name="x-bbs-control-token",
        ) or _authorized(
            headers,
            expected=settings.admin_token,
            header_name="x-bbs-admin-token",
        ):
            return AccessDecision(True)
        return AccessDecision(False, 401, "A valid BBS control token is required.")

    return AccessDecision(False, 403, "Remote access is not permitted.")
