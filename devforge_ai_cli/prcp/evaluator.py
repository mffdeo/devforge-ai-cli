from pathlib import Path

from devforge_ai_cli.prcp.signals import SENSITIVE_PATTERNS, classify_prcp

_EXTENSIONS = [".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml"]
_SKIP_DIRS = {".devforge", ".git", "node_modules", "__pycache__", ".venv", "venv"}


def evaluate_prcp(cwd: Path | None = None) -> dict:
    base = cwd or Path.cwd()
    found: list[str] = []

    for ext in _EXTENSIONS:
        for f in base.rglob(f"*{ext}"):
            if any(skip in f.parts for skip in _SKIP_DIRS):
                continue
            try:
                content = f.read_text(errors="ignore").lower()
                for pattern in SENSITIVE_PATTERNS:
                    if pattern in content and pattern not in found:
                        found.append(pattern)
            except (PermissionError, OSError):
                continue

    level = classify_prcp(found)
    return {"level": level, "signals": found[:10]}
