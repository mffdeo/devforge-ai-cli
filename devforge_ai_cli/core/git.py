import subprocess
from pathlib import Path

from devforge_ai_cli.core.ignore import should_ignore_path


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
            cwd=base, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        result = subprocess.run(
            ["git", "diff"],
            cwd=base, capture_output=True, text=True, timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def get_changed_files(cwd: Path | None = None) -> list[str]:
    base = cwd or Path.cwd()
    files: list[str] = []

    # Modified tracked files (staged and unstaged)
    for args in [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ]:
        try:
            r = subprocess.run(args, cwd=base, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                files.extend(f.strip() for f in r.stdout.splitlines() if f.strip())
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # New/untracked files via git status --porcelain
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=base, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if len(line) > 3:
                    fname = line[3:].strip()
                    if fname:
                        files.append(fname)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    deduped = list(dict.fromkeys(files))
    return [f for f in deduped if not should_ignore_path(f)]


def get_diff_content(cwd: Path | None = None, max_bytes: int = 50_000) -> str:
    base = cwd or Path.cwd()
    content = ""
    for args in [["git", "diff"], ["git", "diff", "--cached"]]:
        if len(content) >= max_bytes:
            break
        try:
            r = subprocess.run(args, cwd=base, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                remaining = max_bytes - len(content)
                content += r.stdout[:remaining]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    return content


def filter_ignored_diff_content(diff_content: str) -> str:
    """Drop unified-diff file sections for ignored paths.

    `get_changed_files()` already filters `.devforge/`, venvs and caches,
    but raw `git diff` content still includes those generated files. Policy
    checks must not treat DevForge's own out-of-scope wording as application
    risk signals.
    """
    kept: list[str] = []
    current: list[str] = []
    ignored = False

    def flush() -> None:
        if current and not ignored:
            kept.extend(current)

    for line in diff_content.splitlines(keepends=True):
        if line.startswith("diff --git "):
            flush()
            current = [line]
            ignored = False
            parts = line.strip().split()
            if len(parts) >= 4:
                path = parts[3]
                if path.startswith("b/"):
                    path = path[2:]
                ignored = should_ignore_path(path)
            continue
        current.append(line)

    flush()
    return "".join(kept)
