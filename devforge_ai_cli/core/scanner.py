import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.core.paths import get_devforge_dir

_SKIP_DIRS = {
    ".devforge", ".git", "node_modules", "__pycache__",
    ".venv", "venv", ".next", "dist", "build", ".cache",
}

_SENSITIVE_KEYWORDS = [
    "auth", "login", "logout", "permission", "permissions",
    "role", "roles", "rbac", "user", "users",
    "jwt", "token", "secret", "password",
    "cpf", "email", "payment", "billing",
    "migration", "database", "middleware",
]

_DB_MAP = {
    "pg": "PostgreSQL", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mysql2": "MySQL", "mysql": "MySQL",
    "sqlite3": "SQLite", "sqlite": "SQLite",
    "redis": "Redis",
    "mongoose": "MongoDB", "mongodb": "MongoDB",
}

_SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".json", ".toml"}

# ── Database heuristics ───────────────────────────────────────────────────────
# Filenames, directories, suffixes, and content patterns that indicate the
# project owns a database (schema, migrations, connection layer). These signals
# expand has_database beyond the package.json / docker-compose detection and
# also feed sensitive_areas so that policy check can react when the diff
# touches them.

_DB_FILENAMES = {
    "db_create.py", "db.py", "database.py", "models.py", "schema.sql",
}
_DB_DIRS = {"migrations", "migration", "alembic"}
_DB_SUFFIXES = (".sqlite", ".sqlite3", ".db")
_DB_CONTENT_EXTS = _SCAN_EXTENSIONS | {".sql"}
_DB_CONTENT_PATTERNS = (
    "sqlite3", "sqlite", "sqlalchemy",
    "create table", "alter table", "drop table", "insert into",
    "db.create_all", "connect(",
)
_DB_SQLITE_TOKENS = {"sqlite", "sqlite3"}
_DB_SCHEMA_TOKENS = {"create table", "alter table", "drop table"}


@dataclass
class ScanResult:
    project_name: str
    detected_stack: list[str] = field(default_factory=list)
    ci_detected: str | None = None
    databases_detected: list[str] = field(default_factory=list)
    sensitive_areas: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    baseline_level: str = "Minimal"
    task_elevation: str = "Standard"
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generated_files: list[str] = field(default_factory=list)
    suggested_next_spec: str = "specs/SPEC-EXAMPLE-001.md"


def _detect_stack(base: Path) -> tuple[list[str], str | None, list[str]]:
    stack: list[str] = []
    ci: str | None = None
    databases: list[str] = []

    # Node / JS / TS frameworks
    pkg_json = base / "package.json"
    if pkg_json.exists():
        stack.append("Node")
        try:
            pkg = json.loads(pkg_json.read_text(errors="ignore"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                raw = deps["next"].lstrip("^~>=<").split(".")[0]
                stack.append(f"Next.js {raw}")
            elif "react" in deps:
                raw = deps["react"].lstrip("^~>=<").split(".")[0]
                stack.append(f"React {raw}")
            if "vite" in deps:
                stack.append("Vite")
            for dep, label in _DB_MAP.items():
                if dep in deps and label not in databases:
                    databases.append(label)
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    if (base / "tsconfig.json").exists() and "TypeScript" not in stack:
        stack.append("TypeScript")

    # Python / frameworks
    for pf in [base / "pyproject.toml", base / "requirements.txt", base / "setup.py"]:
        if pf.exists():
            if "Python" not in stack:
                stack.append("Python")
            try:
                content = pf.read_text(errors="ignore").lower()
                if "fastapi" in content and "FastAPI" not in stack:
                    stack.append("FastAPI")
                elif "django" in content and "Django" not in stack:
                    stack.append("Django")
                elif "flask" in content and "Flask" not in stack:
                    stack.append("Flask")
            except OSError:
                pass
            break

    # Docker / compose
    if (base / "Dockerfile").exists():
        stack.append("Docker")
    for dcf in ["docker-compose.yml", "docker-compose.yaml"]:
        dc = base / dcf
        if dc.exists():
            if "Docker" not in stack:
                stack.append("Docker")
            try:
                content = dc.read_text(errors="ignore").lower()
                for pattern, label in _DB_MAP.items():
                    if pattern in content and label not in databases:
                        databases.append(label)
            except OSError:
                pass

    # CI
    if (base / ".github" / "workflows").is_dir():
        ci = "GitHub Actions"
    elif (base / ".gitlab-ci.yml").exists():
        ci = "GitLab CI"
    elif (base / "Jenkinsfile").exists():
        ci = "Jenkins"
    elif (base / ".circleci").is_dir():
        ci = "CircleCI"

    return stack, ci, databases


def _has_tests(base: Path) -> bool:
    for d in ["tests", "test", "__tests__", "spec"]:
        if (base / d).is_dir():
            return True
    return (
        bool(list(base.rglob("test_*.py"))[:1])
        or bool(list(base.rglob("*.test.ts"))[:1])
        or bool(list(base.rglob("*.spec.ts"))[:1])
    )


def _detect_database_signals(base: Path) -> tuple[list[str], set[str]]:
    """Look for filename/dir/content signals that indicate a database.

    Returns (extra_databases, extra_areas):
      - extra_databases: extra labels for ScanResult.databases_detected
        (SQLite is added when SQLite-specific signals appear).
      - extra_areas: subset of {'database', 'sqlite', 'schema'} to merge
        into sensitive_areas so downstream consumers (planner, policy
        check) can react when the diff touches DB code.
    """
    saw_db = False
    saw_sqlite = False
    saw_schema = False

    for path in base.rglob("*"):
        if any(skip in path.parts for skip in _SKIP_DIRS):
            continue

        name = path.name.lower()

        if path.is_dir():
            if name in _DB_DIRS:
                saw_db = True
            continue

        if not path.is_file():
            continue

        if name in _DB_FILENAMES:
            saw_db = True
            if name == "schema.sql":
                saw_schema = True

        for suf in _DB_SUFFIXES:
            if name.endswith(suf):
                saw_db = True
                saw_sqlite = True
                break

        if path.suffix.lower() in _DB_CONTENT_EXTS:
            try:
                with open(path, "r", errors="ignore") as f:
                    content = f.read(8192).lower()
            except (OSError, PermissionError):
                continue
            for pat in _DB_CONTENT_PATTERNS:
                if pat in content:
                    saw_db = True
                    if pat in _DB_SQLITE_TOKENS:
                        saw_sqlite = True
                    if pat in _DB_SCHEMA_TOKENS:
                        saw_schema = True

    extra_databases: list[str] = ["SQLite"] if saw_sqlite else []
    extra_areas: set[str] = set()
    if saw_db:
        extra_areas.add("database")
    if saw_sqlite:
        extra_areas.add("sqlite")
    if saw_schema:
        extra_areas.add("schema")
    return extra_databases, extra_areas


def _detect_sensitive_areas(base: Path) -> list[str]:
    found: set[str] = set()

    for path in base.rglob("*"):
        if any(skip in path.parts for skip in _SKIP_DIRS):
            continue

        name = path.name.lower()
        for kw in _SENSITIVE_KEYWORDS:
            if kw in name:
                found.add(kw)

        if path.is_file() and path.suffix in _SCAN_EXTENSIONS:
            try:
                with open(path, "r", errors="ignore") as f:
                    content = f.read(8192).lower()
                for kw in _SENSITIVE_KEYWORDS:
                    if kw in content:
                        found.add(kw)
            except (OSError, PermissionError):
                pass

    return sorted(found)


def _compute_signals(
    sensitive_areas: list[str],
    stack: list[str],
    ci: str | None,
    databases: list[str],
    base: Path,
) -> dict:
    sa = set(sensitive_areas)
    auth_kws = {"auth", "login", "logout", "jwt", "token", "password", "secret", "rbac", "role", "roles", "permission", "permissions"}
    pdata_kws = {"user", "users", "cpf", "email", "payment", "billing"}

    touches_auth = bool(sa & auth_kws)
    personal_data = bool(sa & pdata_kws)
    external = bool(sa & {"payment", "billing"}) or bool(databases)

    prod_impact = (
        "high" if any(k in sa for k in {"auth", "permission", "payment"})
        else "medium" if any(k in sa for k in {"user", "database", "migration"})
        else "low"
    )

    has_database = bool(databases) or bool(sa & {"database", "sqlite", "schema"})

    return {
        "touches_auth": touches_auth,
        "personal_data_possible": personal_data,
        "external_integrations": external,
        "production_impact": prod_impact,
        "has_ci": ci is not None,
        "has_tests": _has_tests(base),
        "has_docker": any("docker" in s.lower() for s in stack),
        "has_database": has_database,
    }


def _calculate_prcp(signals: dict, stack: list[str]) -> tuple[str, str]:
    has_real_app = len(stack) >= 2
    baseline = "Standard" if has_real_app else "Minimal"

    # Having a database alone does not elevate to Hardened in the initial
    # scan. The signal stays in `has_database` / sensitive_areas so the
    # policy check can elevate when a diff actually touches db_create.py,
    # migrations or schema.
    elevates = (
        signals.get("touches_auth")
        or signals.get("personal_data_possible")
    )
    elevation = "Hardened" if elevates else baseline
    return baseline, elevation


def _write_scan_files(base: Path, result: ScanResult) -> list[str]:
    devforge_dir = get_devforge_dir(base)
    prcp_dir = devforge_dir / "prcp"
    prcp_dir.mkdir(exist_ok=True)

    profile = {
        "project_name": result.project_name,
        "scanned_at": result.scanned_at,
        "detected_stack": result.detected_stack,
        "ci_detected": result.ci_detected,
        "databases_detected": result.databases_detected,
        "sensitive_areas": result.sensitive_areas,
        "signals": result.signals,
        "prcp": {
            "baseline_level": result.baseline_level,
            "task_elevation": result.task_elevation,
        },
    }

    profile_path = prcp_dir / "project-profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    report_lines = [
        f"# Scan Report — {result.project_name}",
        "",
        f"**Scanned at:** {result.scanned_at}",
        "",
        "## Detected Stack",
        "",
        f"{', '.join(result.detected_stack) or 'None detected'}",
        "",
        "## CI",
        "",
        f"{result.ci_detected or 'Not detected'}",
        "",
        "## Databases",
        "",
        f"{', '.join(result.databases_detected) or 'None detected'}",
        "",
        "## Sensitive Areas",
        "",
        f"{', '.join(result.sensitive_areas) or 'None detected'}",
        "",
        "## Signals",
        "",
        "```json",
        json.dumps(result.signals, indent=2),
        "```",
        "",
        "## PRCP",
        "",
        f"- Baseline: {result.baseline_level}",
        f"- Task Elevation: {result.task_elevation}",
    ]
    report_path = prcp_dir / "scan-report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return [
        str(profile_path.relative_to(base)),
        str(report_path.relative_to(base)),
    ]


_AUTH_AREA_TAGS = {"auth", "login", "logout", "permission", "permissions", "rbac", "role", "roles"}
_DEFAULT_SUGGESTED_SPEC = "specs/SPEC-EXAMPLE-001.md"


def _suggest_next_spec(base: Path, sensitive_areas: list[str]) -> str:
    """Pick the SPEC file to suggest in scan output.

    Order of preference:
      1. If sensitive_areas mention auth/login/permissions AND a SPEC
         whose filename contains 'AUTH' exists, suggest that one.
      2. Otherwise, the first *.md inside specs/ in alphabetical order.
      3. Fallback to specs/SPEC-EXAMPLE-001.md.
    """
    specs_dir = base / "specs"
    if not specs_dir.is_dir():
        return _DEFAULT_SUGGESTED_SPEC

    md_files = sorted(p for p in specs_dir.glob("*.md") if p.is_file())
    if not md_files:
        return _DEFAULT_SUGGESTED_SPEC

    if _AUTH_AREA_TAGS & set(sensitive_areas):
        for p in md_files:
            if "auth" in p.name.lower():
                return f"specs/{p.name}"

    return f"specs/{md_files[0].name}"


def run_scan(project_name: str, base: Path) -> ScanResult:
    stack, ci, databases = _detect_stack(base)
    extra_db, extra_db_areas = _detect_database_signals(base)
    for label in extra_db:
        if label not in databases:
            databases.append(label)
    sensitive_areas = sorted(set(_detect_sensitive_areas(base)) | extra_db_areas)
    signals = _compute_signals(sensitive_areas, stack, ci, databases, base)
    baseline, elevation = _calculate_prcp(signals, stack)

    result = ScanResult(
        project_name=project_name,
        detected_stack=stack,
        ci_detected=ci,
        databases_detected=databases,
        sensitive_areas=sensitive_areas,
        signals=signals,
        baseline_level=baseline,
        task_elevation=elevation,
        suggested_next_spec=_suggest_next_spec(base, sensitive_areas),
    )
    result.generated_files = _write_scan_files(base, result)
    return result
