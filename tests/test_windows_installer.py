from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_wizard_and_builder_are_present():
    assert (ROOT / "scripts" / "install-wizard-windows.ps1").is_file()
    assert (ROOT / "scripts" / "build-windows-installer.ps1").is_file()


def test_wizard_uses_existing_supported_installers():
    text = (ROOT / "scripts" / "install-wizard-windows.ps1").read_text(encoding="utf-8")
    assert "install-windows.ps1" in text
    assert "install-service-windows.ps1" in text
    assert "BMX Broadcast Suite 1.2.8" in text


def test_wizard_documentation_is_linked():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "wizard-installer-windows.md" in readme
    assert "wizard-installer-windows.md" in docs_index
