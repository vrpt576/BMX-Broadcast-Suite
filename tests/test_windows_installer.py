import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "windows"
UPGRADE_CODE = "D7F3D76D-1478-4D91-8A53-6E2689D809B6"


def test_msi_release_version_and_upgrade_identity():
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")

    assert '$Version = "1.3.2"' in builder
    assert 'Version="$(var.ProductVersion)"' in product
    assert f'UpgradeCode="{UPGRADE_CODE}"' in product
    assert "MajorUpgrade" in product


def test_msi_sources_replace_iexpress_chain():
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")
    assert '$InstallerName = "BMX-Broadcast-Suite-Setup-v$Version.msi"' in builder
    assert "wix.dll" in builder and "Product.wxs" in builder
    forbidden = ("iexpress", "wextract", "setup.vbs", "wscript.exe", "ExecutionPolicy Bypass")
    for value in forbidden:
        assert value.lower() not in (builder + product).lower()


def test_offline_dependency_install_pins_python_3_12_not_ambient_path():
    """The dependency lock ships cp312 wheels (matching the embedded
    3.12.10 runtime), and pip's own wheel-compatibility check is decided
    by whichever interpreter runs it -- so this must resolve an actual
    Python 3.12, not just invoke bare `python` and trust it's 3.12. A
    system with a newer Python earlier on PATH than 3.12 (a completely
    ordinary machine state, not a misconfiguration) used to fail deep
    inside pip on the first compiled wheel with a confusing "no matching
    distribution", rather than a clear version error up front."""
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
    assert "function Resolve-BuildPython" in builder
    assert "py -3.12" in builder
    assert "$BuildPython = Resolve-BuildPython" in builder
    assert "& $BuildPython -m pip install" in builder
    assert "& python -m pip install" not in builder


def test_msi_is_offline_native_and_preserves_programdata():
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")
    assert "--no-index" in builder and "--require-hashes" in builder
    assert "ServiceInstall" in product and 'Name="BMXBroadcastSuite"' in product
    assert "MajorUpgrade" in product and "ServiceControl" in product
    assert "CommonAppDataFolder" in product and 'Permanent="yes"' in product
    assert "PURGEUSERDATA" in product and "RemoveFolderEx" in product
    assert "ProgramFiles64Folder" in product
    assert "RegistrySearch" in product and "ODBC Driver 18 for SQL Server" in product
    assert 'Name="UserDataInitialized"' in product
    assert 'Source="$(var.SeedRoot)\\bbs.env"' not in product


def test_program_files_is_read_only_at_runtime_and_fully_removed():
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")
    service = (PACKAGING / "BBSService.xml").read_text(encoding="utf-8")

    assert "PYTHONDONTWRITEBYTECODE" in service
    assert "-B -m connector.run" in service
    assert 'Property="INSTALLFOLDER" On="uninstall"' in product
    assert 'Condition="REMOVE = &quot;ALL&quot;"' in product
    assert "__pycache__" in builder and 'Filter "*.pyc"' in builder
    assert "taskkill" not in (product + service + builder).lower()


def test_programdata_is_preserved_unless_explicitly_purged():
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")
    assert 'Property="BBSUSERDATAPATH" On="uninstall"' in product
    assert 'Condition="PURGEUSERDATA = 1 AND REMOVE = &quot;ALL&quot;"' in product
    assert 'Permanent="yes"' in product


def test_legacy_upgrade_is_narrowly_scoped():
    product = (PACKAGING / "Product.wxs").read_text(encoding="utf-8")
    assert 'schtasks.exe /End /TN &quot;BMX Broadcast Suite&quot;' in product
    assert 'schtasks.exe /Delete /F /TN &quot;BMX Broadcast Suite&quot;' in product
    assert "taskkill" not in product.lower()
    assert "LEGACYINSTALLDIR = INSTALLFOLDER" in product
    assert "BMXBroadcastSuite" in product


def test_every_locked_build_artifact_exists_and_matches_hash():
    lock = json.loads((PACKAGING / "dependency-lock.json").read_text(encoding="utf-8"))
    for artifact in lock["artifacts"]:
        path = PACKAGING / artifact["path"]
        assert path.is_file(), artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == artifact["sha256"]


def test_wheel_lock_covers_exact_wheelhouse():
    lock = (PACKAGING / "requirements-lock.txt").read_text(encoding="utf-8").lower()
    wheels = list((PACKAGING / "dependencies" / "wheels").glob("*.whl"))
    assert wheels
    for wheel in wheels:
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert f"sha256:{digest}" in lock, wheel.name


def test_release_gate_records_signature_defender_and_exact_hash():
    gate = (ROOT / "scripts" / "test-windows-release-artifact.ps1").read_text(encoding="utf-8")
    for value in ("Get-AuthenticodeSignature", "Update-MpSignature", "Start-MpScan", "Get-MpComputerStatus", "Get-FileHash"):
        assert value in gate
    assert "Do not publish" in gate


def test_obsolete_script_bootstrap_is_not_present():
    for name in (
        "install-wizard-windows.ps1", "register-uninstall-windows.ps1",
        "uninstall-windows.ps1", "uninstall-worker-windows.ps1",
        "start-windows-background.ps1",
    ):
        assert not (ROOT / "scripts" / name).exists()
