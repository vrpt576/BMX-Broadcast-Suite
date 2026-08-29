"""ODBC driver detection and prerequisite installation.

BBS must start and serve every page even when no usable SQL Server ODBC
driver is installed -- this module only ever reports status and, on
explicit request from the Setup page, installs the driver. It never blocks
import or startup, and never runs anything without an operator's explicit
action (see connector/routes/setup.py).

Redistribution of the bundled installer is confirmed by the Microsoft ODBC
Driver 18 for SQL Server EULA's "Distributable Code" section, which grants
distribution rights to code listed on the REDIST list; that list
(https://aka.ms/odbc18eularedist) reads in full: "The entire package may be
redistributed." Verified 2026-08-29 -- see
packaging/windows/dependencies/ODBC-Driver-LICENSE.rtf for the complete
EULA text shipped alongside the driver.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

try:
    import pyodbc
except ImportError:  # pragma: no cover - enables tests without native ODBC
    pyodbc = None  # type: ignore[assignment]

# Newest-first. BBS's own connection string (Settings.sql_driver) always
# asks for Driver 18 specifically; Driver 17 is accepted here as a working
# fallback for a track that already has it, not something BBS installs.
ACCEPTABLE_DRIVERS: tuple[str, ...] = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)

# Current as of 2026-08-29 -- see docs/sqorz-live-timing.md's sibling,
# docs/setup-wizard.md, for how to refresh this if Microsoft ships a newer
# driver before the bundled copy is updated.
DOWNLOAD_URL = "https://go.microsoft.com/fwlink/?linkid=2358430"
DOWNLOAD_VERSION_AT_TIME_OF_WRITING = "18.6.2.1"

# A real installer is several MB; anything drastically smaller means the
# download didn't get the real file (a redirect page, an error body, a
# truncated transfer) -- refuse to run msiexec against it.
MIN_PLAUSIBLE_INSTALLER_BYTES = 1_000_000


class OdbcInstallError(RuntimeError):
    """Raised when installing the ODBC driver fails or is refused."""


@dataclass(frozen=True)
class OdbcDriverStatus:
    installed_drivers: list[str]
    preferred_driver: str | None
    acceptable: bool


def detect() -> OdbcDriverStatus:
    """Never raises -- pyodbc missing or drivers() failing both report as
    "nothing usable found", not an error."""
    if pyodbc is None:
        return OdbcDriverStatus(installed_drivers=[], preferred_driver=None, acceptable=False)
    try:
        drivers = list(pyodbc.drivers())
    except Exception:  # noqa: BLE001 - detection must never be fatal
        drivers = []
    preferred = next((driver for driver in ACCEPTABLE_DRIVERS if driver in drivers), None)
    return OdbcDriverStatus(
        installed_drivers=drivers,
        preferred_driver=preferred,
        acceptable=preferred is not None,
    )


def bundled_installer_path(install_root: Path) -> Path | None:
    """The installed-payload location, or (for a source checkout, so this is
    testable and usable without a full MSI build) the packaging dependency
    location. None if neither exists."""
    candidates = (
        install_root / "prerequisites" / "msodbcsql18-x64.msi",
        install_root / "packaging" / "windows" / "dependencies" / "msodbcsql18-x64.msi",
    )
    return next((path for path in candidates if path.exists()), None)


def bundled_license_path(install_root: Path) -> Path | None:
    candidates = (
        install_root / "prerequisites" / "ODBC-Driver-LICENSE.rtf",
        install_root / "packaging" / "windows" / "dependencies" / "ODBC-Driver-LICENSE.rtf",
    )
    return next((path for path in candidates if path.exists()), None)


def download_installer(destination: Path, *, timeout: float = 120.0) -> Path:
    """Fallback source: fetch the current driver directly from Microsoft.

    No hash pin is possible here (unlike the bundled copy) since this always
    fetches whatever Microsoft currently serves at the redistributable link
    -- that's the whole point of this being the fallback, not the primary
    source. A plausibility check guards against silently "installing" a
    redirect/error page.
    """
    request = Request(DOWNLOAD_URL, headers={"User-Agent": "BBS-Setup/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator, not fatal to BBS
        raise OdbcInstallError(f"Could not download the ODBC driver: {exc}") from exc
    if len(data) < MIN_PLAUSIBLE_INSTALLER_BYTES:
        raise OdbcInstallError(
            f"Downloaded file is only {len(data)} bytes -- too small to be the real "
            "installer. Not installing it."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def install_from_msi(
    msi_path: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    """Silently install the given MSI, accepting Microsoft's EULA on the
    operator's behalf via the documented IACCEPTMSODBCSQLLICENSETERMS
    property.

    Only ever call this after the operator has explicitly consented in the
    Setup page UI -- BBS shows the actual EULA text (see
    bundled_license_path) and requires an explicit "I agree, install"
    action before this function is ever reached. See the EULA's
    "Distribution Requirements" (2.b): distributors must "require ...
    external end users to agree to terms that protect it and Microsoft at
    least as much as this agreement" -- the operator's own explicit consent
    in the Setup page is what satisfies that, not this flag alone.
    """
    if not msi_path.exists():
        raise OdbcInstallError(f"Installer not found: {msi_path}")
    try:
        result = run(
            [
                "msiexec",
                "/i",
                str(msi_path),
                "IACCEPTMSODBCSQLLICENSETERMS=YES",
                "/qn",
                "/norestart",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator, not fatal to BBS
        raise OdbcInstallError(f"Could not run the installer: {exc}") from exc
    if result.returncode != 0:
        raise OdbcInstallError(
            f"The installer exited with code {result.returncode}: "
            f"{(result.stderr or result.stdout or '').strip()[:2000]}"
        )
