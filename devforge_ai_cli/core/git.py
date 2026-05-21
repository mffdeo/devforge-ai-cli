import subprocess
from pathlib import Path


def detect_project_name(cwd: Path | None = None) -> str:
    base = cwd or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=base,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            name = url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return name
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return base.name


def get_git_diff(cwd: Path | None = None) -> str:
    base = cwd or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "diff", "--staged"],
            cwd=base,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        result = subprocess.run(
            ["git", "diff"],
            cwd=base,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""
