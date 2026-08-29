"""ODBC driver detection and prerequisite installation -- never fatal, never
runs anything without an explicit, already-consented-to install call."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from connector.services import odbc_service


class FakeDrivers:
    def __init__(self, drivers: list[str]) -> None:
        self._drivers = drivers

    def drivers(self) -> list[str]:
        return self._drivers


class ExplodingDrivers:
    def drivers(self) -> list[str]:
        raise RuntimeError("driver manager unavailable")


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detects_driver_18_as_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "pyodbc", FakeDrivers(["SQL Server", "ODBC Driver 18 for SQL Server"]))
    status = odbc_service.detect()
    assert status.acceptable is True
    assert status.preferred_driver == "ODBC Driver 18 for SQL Server"
    assert "ODBC Driver 18 for SQL Server" in status.installed_drivers


def test_falls_back_to_driver_17_when_18_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "pyodbc", FakeDrivers(["ODBC Driver 17 for SQL Server"]))
    status = odbc_service.detect()
    assert status.acceptable is True
    assert status.preferred_driver == "ODBC Driver 17 for SQL Server"


def test_no_acceptable_driver_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "pyodbc", FakeDrivers(["SQL Server Native Client 11.0"]))
    status = odbc_service.detect()
    assert status.acceptable is False
    assert status.preferred_driver is None
    assert status.installed_drivers == ["SQL Server Native Client 11.0"]


def test_pyodbc_not_installed_degrades_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "pyodbc", None)
    status = odbc_service.detect()
    assert status.acceptable is False
    assert status.installed_drivers == []


def test_drivers_call_raising_degrades_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "pyodbc", ExplodingDrivers())
    status = odbc_service.detect()
    assert status.acceptable is False
    assert status.installed_drivers == []


# ---------------------------------------------------------------------------
# Locating the bundled installer / license
# ---------------------------------------------------------------------------


def test_bundled_installer_path_finds_the_installed_payload_location(tmp_path: Path) -> None:
    prereq_dir = tmp_path / "prerequisites"
    prereq_dir.mkdir()
    msi = prereq_dir / "msodbcsql18-x64.msi"
    msi.write_bytes(b"fake msi")
    assert odbc_service.bundled_installer_path(tmp_path) == msi


def test_bundled_installer_path_falls_back_to_the_dev_checkout_location(tmp_path: Path) -> None:
    dev_dir = tmp_path / "packaging" / "windows" / "dependencies"
    dev_dir.mkdir(parents=True)
    msi = dev_dir / "msodbcsql18-x64.msi"
    msi.write_bytes(b"fake msi")
    assert odbc_service.bundled_installer_path(tmp_path) == msi


def test_bundled_installer_path_is_none_when_neither_exists(tmp_path: Path) -> None:
    assert odbc_service.bundled_installer_path(tmp_path) is None


def test_bundled_license_path_mirrors_the_same_search(tmp_path: Path) -> None:
    assert odbc_service.bundled_license_path(tmp_path) is None
    dev_dir = tmp_path / "packaging" / "windows" / "dependencies"
    dev_dir.mkdir(parents=True)
    license_file = dev_dir / "ODBC-Driver-LICENSE.rtf"
    license_file.write_text("{\\rtf1 license}")
    assert odbc_service.bundled_license_path(tmp_path) == license_file


# ---------------------------------------------------------------------------
# install_from_msi -- never runs without the caller already having consent
# ---------------------------------------------------------------------------


def test_install_from_msi_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(odbc_service.OdbcInstallError, match="not found"):
        odbc_service.install_from_msi(tmp_path / "does-not-exist.msi")


def test_install_from_msi_runs_msiexec_silently_with_the_license_flag(tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake msi")
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    odbc_service.install_from_msi(msi, run=fake_run)

    assert len(calls) == 1
    args = calls[0]
    assert args[0] == "msiexec"
    assert str(msi) in args
    assert "IACCEPTMSODBCSQLLICENSETERMS=YES" in args
    assert "/qn" in args


def test_install_from_msi_raises_with_the_real_error_on_failure(tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake msi")

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1603, stdout="", stderr="Fatal error during installation.")

    with pytest.raises(odbc_service.OdbcInstallError, match="1603"):
        odbc_service.install_from_msi(msi, run=fake_run)


def test_install_from_msi_never_raises_a_bare_exception_from_a_broken_subprocess_call(
    tmp_path: Path,
) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake msi")

    def exploding_run(args, **kwargs):
        raise OSError("msiexec.exe not found")

    with pytest.raises(odbc_service.OdbcInstallError, match="msiexec"):
        odbc_service.install_from_msi(msi, run=exploding_run)


# ---------------------------------------------------------------------------
# download_installer -- the (b) fallback
# ---------------------------------------------------------------------------


def test_download_installer_rejects_an_implausibly_small_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TinyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"not a real installer"

    monkeypatch.setattr(odbc_service, "urlopen", lambda *a, **k: TinyResponse())

    with pytest.raises(odbc_service.OdbcInstallError, match="too small"):
        odbc_service.download_installer(tmp_path / "driver.msi")


def test_download_installer_saves_a_plausible_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"X" * (odbc_service.MIN_PLAUSIBLE_INSTALLER_BYTES + 1)

    class BigResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return payload

    monkeypatch.setattr(odbc_service, "urlopen", lambda *a, **k: BigResponse())

    destination = tmp_path / "nested" / "driver.msi"
    result = odbc_service.download_installer(destination)

    assert result == destination
    assert destination.read_bytes() == payload


def test_download_installer_degrades_a_network_failure_to_odbc_install_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def boom(*a, **k):
        raise OSError("network unreachable")

    monkeypatch.setattr(odbc_service, "urlopen", boom)

    with pytest.raises(odbc_service.OdbcInstallError, match="download"):
        odbc_service.download_installer(tmp_path / "driver.msi")
