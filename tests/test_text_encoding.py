"""Guard user-visible project text against known encoding corruption."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".desktop",
    ".html",
    ".ini",
    ".iss",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".service",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
}
SOURCE_DIRS = {
    "assets",
    "connector",
    "controller",
    "database",
    "docs",
    "examples",
    "exporter",
    "overlay",
    "packaging",
    "scripts",
    "tests",
    "themes",
}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}

# Escapes keep this test from matching its own source.
MOJIBAKE_SEQUENCES = (
    "\ufffd",
    "\u00c3\u00a2\u00e2\u201a\u00ac",
    "\u00c3\u00a2\u00e2\u20ac\u201d",
    "\u00c3\u00a2\u00e2\u20ac\u201c",
    "\u00c3\u00a2\u00e2\u20ac\u00a6",
    "\u00c3\u201a\u00c2\u00b7",
    "\u00c3\u0192",
    "\u00e2\u2014\u20ac",
    "\u00e2\u2013\u00b6",
    "\u00c2\u00b7",
    "\u00e2\u20ac\u00a6",
    "\u00e2\u20ac\u201d",
)


def _project_text_files():
    root_files = (
        path
        for path in ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    )
    nested_files = (
        path
        for directory in SOURCE_DIRS
        if (ROOT / directory).is_dir()
        for path in (ROOT / directory).rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not EXCLUDED_PARTS.intersection(path.parts)
        and not path.name.endswith(".bak")
    )
    yield from root_files
    yield from nested_files


def test_user_visible_text_has_no_known_mojibake() -> None:
    failures: list[str] = []
    for path in _project_text_files():
        text = path.read_text(encoding="utf-8")
        for sequence in MOJIBAKE_SEQUENCES:
            if sequence in text:
                failures.append(f"{path.relative_to(ROOT)} contains {sequence!r}")

    assert not failures, "Known mojibake found:\n" + "\n".join(failures)
