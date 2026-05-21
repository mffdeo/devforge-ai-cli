"""Central ignore rules for scan, policy check and evidence.

A single source of truth for which directories and file suffixes the
DevForge CLI must treat as non-application context: virtual envs, git
metadata, caches, build artifacts, local databases, and generated
governance state under .devforge/ (except the ones explicitly read by
evidence collectors).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDED_DIRS: set[str] = {
    ".git",
    ".devforge",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
    ".cache",
    "coverage",
}

DEFAULT_EXCLUDED_SUFFIXES: set[str] = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
}


def _path_parts(path: str | Path) -> tuple[str, ...]:
    if isinstance(path, Path):
        raw = str(path)
    else:
        raw = path
    raw = raw.replace("\\", "/").strip()
    if not raw:
        return ()
    return tuple(p for p in raw.split("/") if p and p != ".")


def should_ignore_path(
    path: str | Path,
    excluded_dirs: Iterable[str] | None = None,
    excluded_suffixes: Iterable[str] | None = None,
) -> bool:
    """Return True when path falls inside an ignored dir or has an ignored suffix.

    Works with both Path and str. Path separators are normalized so the
    same call site works on POSIX and Windows. Comparison is by exact
    path segment, not substring — 'envelope/foo.py' is not ignored just
    because 'env' is excluded.
    """
    parts = _path_parts(path)
    if not parts:
        return False

    dirs = set(excluded_dirs) if excluded_dirs is not None else DEFAULT_EXCLUDED_DIRS
    if any(p in dirs for p in parts):
        return True

    suffixes = set(excluded_suffixes) if excluded_suffixes is not None else DEFAULT_EXCLUDED_SUFFIXES
    last = parts[-1].lower()
    return any(last.endswith(suf) for suf in suffixes)
