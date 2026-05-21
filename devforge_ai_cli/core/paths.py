from pathlib import Path

DEVFORGE_DIR_NAME = ".devforge"
PACKAGE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"


def get_devforge_dir(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / DEVFORGE_DIR_NAME


def get_config_file(cwd: Path | None = None) -> Path:
    return get_devforge_dir(cwd) / "config.yml"


def get_audit_file(cwd: Path | None = None) -> Path:
    return get_devforge_dir(cwd) / "audit" / "audit.ndjson"
