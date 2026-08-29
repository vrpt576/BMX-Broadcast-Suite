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
)
# Theme *lookups* (GET) are broadcast data: overlays fetch the active theme's
# colors/typography client-side from whatever host the overlay page was
# loaded from (see connector/routes/lineup.py's applyTheme()). Gating those
# reads behind the admin token broke overlays for every non-loopback client
# (any LAN OBS machine, any browser other than one on the BBS host itself) —
# the fetch would come back 403, the overlay would silently keep its bundled
# default colors, and it would look like "the theme only works on
# 127.0.0.1". Only *mutating* theme requests (save/reset) are treated as
# admin actions.
THEME_API_PREFIX = "/api/themes"

# The Setup wizard creates database accounts (Part 2) and installs software
# with system-level privileges (Part 1). Loopback-only, always -- unlike
# every other admin path above, NO admin token can ever substitute for
# being physically at (or remoted into) the BBS host itself. See
# connector/routes/setup.py and test_setup_route.py's
# test_a_non_loopback_request_is_refused_even_with_a_valid_admin_token.
SETUP_API_PREFIX = "/api/setup"


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
    if path.startswith(SETUP_API_PREFIX):
        if method == "OPTIONS" or is_local_client(client_host):
            return AccessDecision(True)
        return AccessDecision(
            False,
            403,
            "The Setup wizard creates database accounts and installs software -- it is only "
            "reachable from the BBS host itself, regardless of any admin token.",
        )

    if method == "OPTIONS" or is_local_client(client_host):
        return AccessDecision(True)

    admin_path = (
        path != "/api/configuration/public"
        and any(path.startswith(prefix) for prefix in ADMIN_API_PREFIXES)
    )
    # A theme path is admin-gated only when it's mutating (PUT save, POST
    # reset). GET reads stay public read-only broadcast data, same as
    # lineup/current/results, so LAN overlays can render the selected theme.
    if path.startswith(THEME_API_PREFIX) and method not in SAFE_METHODS:
        admin_path = True
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
