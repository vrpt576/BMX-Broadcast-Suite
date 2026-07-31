from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIZARD_SCRIPTS = (
    "install-windows.ps1",
    "install-service-windows.ps1",
    "start-windows-background.ps1",
    "start-tray-windows.ps1",
    "restore-user-data-windows.ps1",
    "register-uninstall-windows.ps1",
    "uninstall-service-windows.ps1",
    "uninstall-windows.ps1",
    "uninstall-worker-windows.ps1",
)


def test_windows_wizard_and_builder_are_present():
    assert (ROOT / "scripts" / "install-wizard-windows.ps1").is_file()
    assert (ROOT / "scripts" / "build-windows-installer.ps1").is_file()
    assert (ROOT / "scripts" / "uninstall-windows.ps1").is_file()
    assert (ROOT / "scripts" / "uninstall-worker-windows.ps1").is_file()
    assert (ROOT / "scripts" / "register-uninstall-windows.ps1").is_file()
    assert (ROOT / "scripts" / "restore-user-data-windows.ps1").is_file()
    for script in WIZARD_SCRIPTS:
        assert (ROOT / "scripts" / script).is_file()


def test_builder_requires_and_packages_every_wizard_script_from_git():
    text = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(
        encoding="utf-8"
    )
    for script in WIZARD_SCRIPTS:
        assert f"scripts/{script}" in text
    assert "ls-files --error-unmatch" in text
    assert "checkout-index --all --force" in text
    assert "Indexed installer payload is incomplete" in text


def test_wizard_uses_existing_supported_installers():
    text = (ROOT / "scripts" / "install-wizard-windows.ps1").read_text(encoding="utf-8")
    assert "install-windows.ps1" in text
    assert "install-service-windows.ps1" in text
    assert "restore-user-data-windows.ps1" in text
    assert "register-uninstall-windows.ps1" in text
    assert "start-windows-background.ps1" in text
    assert "Start-ScheduledTask" not in text
    assert "BMX Broadcast Suite 1.2.9" in text


def test_wizard_documentation_is_linked():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "wizard-installer-windows.md" in readme
    assert "wizard-installer-windows.md" in docs_index


def test_windows_uninstaller_is_scoped_and_preserves_operator_data():
    worker = (ROOT / "scripts" / "uninstall-worker-windows.ps1").read_text(
        encoding="utf-8"
    )
    registration = (ROOT / "scripts" / "register-uninstall-windows.ps1").read_text(
        encoding="utf-8"
    )

    assert "Test-PathInsideRoot" in worker
    assert "connector\\.(run|tray_windows)" in worker
    assert "Win32_Process" in worker
    assert "Stop-Process" in worker
    assert "BMXBroadcastSuite" in registration
    assert "UninstallString" in registration
    assert "QuietUninstallString" in registration
    for path in (".env", "connector\\logs", "themes", "data"):
        assert path in worker


def test_windows_background_start_is_console_free_and_installer_waits_for_health():
    service = (ROOT / "scripts" / "install-service-windows.ps1").read_text(
        encoding="utf-8"
    )
    wizard = (ROOT / "scripts" / "install-wizard-windows.ps1").read_text(
        encoding="utf-8"
    )
    builder = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(
        encoding="utf-8"
    )

    background = (ROOT / "scripts" / "start-windows-background.ps1").read_text(
        encoding="utf-8"
    )

    assert ".venv\\Scripts\\python.exe" in service
    assert "pythonw.exe" not in service
    assert "-m connector.run" in service
    assert "WorkingDirectory" in service
    assert "Scheduled Task was created with an unexpected action" in service
    assert "Scheduled Task exited during startup" in service
    assert ".venv\\Scripts\\python.exe" in background
    assert "WindowStyle Hidden" in background
    assert "startup-error.log" in background
    assert "-NoAutoStart" not in wizard
    assert "/health" in wizard
    assert "did not become ready within 30 seconds" in wizard
    assert "Machine startup was requested" in wizard
    assert "Remove-PartialIntegration" in wizard
    assert "-DataDir $DataRoot" in wizard
    assert wizard.index("register-uninstall-windows.ps1") > wizard.index(
        "if (-not $ready)"
    )
    assert "setup.vbs" in builder
    assert "wscript.exe setup.vbs" in builder


def test_windows_runtime_data_is_outside_program_files():
    installer = (ROOT / "scripts" / "install-windows.ps1").read_text(
        encoding="utf-8"
    )
    restore = (ROOT / "scripts" / "restore-user-data-windows.ps1").read_text(
        encoding="utf-8"
    )
    config = (ROOT / "connector" / "config.py").read_text(encoding="utf-8")

    assert "[string]$DataDir" in installer
    assert "connector\\logs" in installer
    assert "BMX Broadcast Suite\\UserData" in restore
    assert "WINDOWS_DATA_DIRECTORY" in config
    assert "windows_user_data_root" in config
    assert "runtime_root()" in config
