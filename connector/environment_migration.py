"""Idempotent, value-preserving migration of the protected BBS environment."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


ENVIRONMENT_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True)
class EnvironmentMigrationResult:
    created: bool
    changed: bool
    added_keys: tuple[str, ...]


def _keys(lines: list[str]) -> set[str]:
    keys: set[str] = set()
    for line in lines:
        match = ENVIRONMENT_KEY.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def _default_entries(lines: list[str]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in lines:
        match = ENVIRONMENT_KEY.match(line)
        if match:
            entries.append((match.group(1), line.rstrip("\r\n")))
    return entries


def ensure_environment_defaults(
    target: Path,
    defaults: Path,
) -> EnvironmentMigrationResult:
    """Create or append missing settings without changing existing values.

    Existing lines, comments, ordering, and secret values remain byte-for-byte
    unchanged. Only absent keys from the packaged example are appended.
    """
    default_text = defaults.read_text(encoding="utf-8-sig")
    default_lines = default_text.splitlines()
    entries = _default_entries(default_lines)
    if not entries:
        raise ValueError(f"No environment settings were found in {defaults}.")

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        _atomic_write(target, default_text)
        return EnvironmentMigrationResult(
            created=True,
            changed=True,
            added_keys=tuple(key for key, _line in entries),
        )

    existing_text = target.read_text(encoding="utf-8-sig")
    existing_keys = _keys(existing_text.splitlines())
    missing = [(key, line) for key, line in entries if key not in existing_keys]
    if not missing:
        return EnvironmentMigrationResult(False, False, ())

    newline = "\r\n" if "\r\n" in existing_text else "\n"
    prefix = existing_text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    addition = [
        "",
        "# Settings added by BMX Broadcast Suite; existing values were preserved.",
        *(line for _key, line in missing),
    ]
    _atomic_write(target, prefix + newline.join(addition) + newline)
    return EnvironmentMigrationResult(
        created=False,
        changed=True,
        added_keys=tuple(key for key, _line in missing),
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="")
    os.replace(temporary, path)
