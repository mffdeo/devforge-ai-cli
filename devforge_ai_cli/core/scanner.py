import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.core.ignore import should_ignore_path
from devforge_ai_cli.core.paths import get_devforge_dir

_AUTH_KEYWORDS = {
    "auth", "login", "logout", "permission", "permissions",
    "role", "roles", "rbac", "jwt",
}
_SECURITY_KEYWORDS = {"token", "secret", "password", "senha"}
_KEY_KEYWORDS = {"api_key", "private_key"}
_PERSONAL_DATA_KEYWORDS = {
    "email", "cpf", "phone", "telefone", "address", "endereco", "endereço",
    "full_name", "first_name", "last_name", "nome_completo", "birthdate", "birth_date", "data_nascimento",
    "personal data", "dados pessoais", "document", "documento", "cnpj",
    "data de nascimento", "full name", "nome completo",
}
_USER_CONTEXT_KEYWORDS = {"username", "user_id", "user email", "user password", "user cpf", "user document", "user profile", "auth user"}
_USER_INTERACTION_KEYWORDS = {"input", "enter", "choice", "option", "user input"}
_WEAK_KEYWORDS = {"user", "users", "rg"}
_RISK_KEYWORDS = {
    "payment", "billing", "pagamento", "cobrança",
    "migration", "database", "middleware",
}
_RAW_KEYWORDS = sorted(
    _AUTH_KEYWORDS
    | _SECURITY_KEYWORDS
    | _KEY_KEYWORDS
    | _PERSONAL_DATA_KEYWORDS
    | _USER_CONTEXT_KEYWORDS
    | _USER_INTERACTION_KEYWORDS
    | _WEAK_KEYWORDS
    | _RISK_KEYWORDS
)
_RG_CONTEXT_KEYWORDS = {
    "documento", "document", "identidade", "cpf", "nome",
    "data de nascimento", "cadastro",
}

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
    project_type: str = "unknown"
    detected_stack: list[str] = field(default_factory=list)
    ci_detected: str | None = None
    databases_detected: list[str] = field(default_factory=list)
    architecture_summary: str = "Project architecture could not be confidently inferred."
    has_database: bool = False
    has_auth: bool = False
    personal_data_possible: bool = False
    external_integrations: bool = False
    production_impact: str = "low"
    sensitive_areas: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    baseline_level: str = "Minimal"
    task_elevation: str = "Standard"
    confidence: str = "low"
    profile_status: str = "draft"
    requires_agent_review: bool = True
    requires_user_approval: bool = True
    assumptions: list[str] = field(default_factory=list)
    gray_areas: list[str] = field(default_factory=list)
    source: str = "deterministic"
    project_signals: dict = field(default_factory=dict)
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generated_files: list[str] = field(default_factory=list)
    suggested_next_spec: str | None = None
    suggested_next_command: str = 'devforge specify --idea "Describe your feature idea"'


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

    if "Python" not in stack and _python_files(base):
        stack.append("Python")

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


def _python_files(base: Path) -> list[Path]:
    files: list[Path] = []
    for path in base.rglob("*.py"):
        try:
            rel = path.relative_to(base)
        except ValueError:
            continue
        if should_ignore_path(rel, excluded_suffixes=set()):
            continue
        if path.is_file():
            files.append(path)
    return files


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
        if should_ignore_path(path.relative_to(base), excluded_suffixes=set()):
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


def _collect_keyword_hits(base: Path) -> dict[str, dict[str, list[str]]]:
    raw_hits: dict[str, list[str]] = {}
    user_interaction_hits: dict[str, list[str]] = {}
    strong_sensitive_hits: dict[str, list[str]] = {}
    weak_sensitive_hits: dict[str, list[str]] = {}

    for path in base.rglob("*"):
        if should_ignore_path(path.relative_to(base), excluded_suffixes=set()):
            continue

        rel = str(path.relative_to(base))
        name = path.name
        _collect_hits_for_text(
            text=name,
            rel=rel,
            raw_hits=raw_hits,
            user_interaction_hits=user_interaction_hits,
            strong_sensitive_hits=strong_sensitive_hits,
            weak_sensitive_hits=weak_sensitive_hits,
        )

        if path.is_file() and path.suffix in _SCAN_EXTENSIONS:
            try:
                with open(path, "r", errors="ignore") as f:
                    content = f.read(8192)
                _collect_hits_for_text(
                    text=content,
                    rel=rel,
                    raw_hits=raw_hits,
                    user_interaction_hits=user_interaction_hits,
                    strong_sensitive_hits=strong_sensitive_hits,
                    weak_sensitive_hits=weak_sensitive_hits,
                )
            except (OSError, PermissionError):
                pass

    return {
        "raw_keyword_hits": raw_hits,
        "user_interaction_hits": user_interaction_hits,
        "strong_sensitive_hits": strong_sensitive_hits,
        "weak_sensitive_hits": weak_sensitive_hits,
    }


def _collect_hits_for_text(
    text: str,
    rel: str,
    raw_hits: dict[str, list[str]],
    user_interaction_hits: dict[str, list[str]],
    strong_sensitive_hits: dict[str, list[str]],
    weak_sensitive_hits: dict[str, list[str]],
) -> None:
    for keyword in _RAW_KEYWORDS:
        if _keyword_present(text, keyword):
            _add_hit(raw_hits, keyword, rel)

    for keyword in _USER_INTERACTION_KEYWORDS:
        if _keyword_present(text, keyword):
            _add_hit(user_interaction_hits, keyword, rel)

    for keyword in _AUTH_KEYWORDS | _SECURITY_KEYWORDS | _KEY_KEYWORDS | _PERSONAL_DATA_KEYWORDS | _USER_CONTEXT_KEYWORDS:
        if _keyword_present(text, keyword):
            _add_hit(strong_sensitive_hits, keyword, rel)

    if _rg_sensitive(text):
        _add_hit(strong_sensitive_hits, "rg", rel)
    elif _keyword_present(text, "rg"):
        _add_hit(weak_sensitive_hits, "rg", rel)

    for keyword in {"user", "users"}:
        if _keyword_present(text, keyword):
            _add_hit(weak_sensitive_hits, keyword, rel)


def _keyword_present(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None


def _rg_sensitive(text: str) -> bool:
    if not _keyword_present(text, "rg"):
        return False
    lowered = text.lower()
    if re.search(r"(?<![A-Za-z0-9])rg(?![A-Za-z0-9])", text, flags=re.IGNORECASE):
        return True
    return any(_keyword_present(lowered, keyword) for keyword in _RG_CONTEXT_KEYWORDS)


def _add_hit(hits: dict[str, list[str]], keyword: str, rel: str) -> None:
    paths = hits.setdefault(keyword, [])
    if rel not in paths:
        paths.append(rel)


def _detect_sensitive_areas(base: Path) -> list[str]:
    keyword_hits = _collect_keyword_hits(base)
    found = _sensitive_areas_from_hits(keyword_hits["strong_sensitive_hits"])
    return sorted(found)


def _sensitive_areas_from_hits(keyword_hits: dict[str, list[str]], extra_areas: set[str] | None = None) -> set[str]:
    found: set[str] = set(extra_areas or set())
    hit_keys = set(keyword_hits)
    if hit_keys & _AUTH_KEYWORDS:
        found.update(sorted(hit_keys & _AUTH_KEYWORDS))
    if hit_keys & (_SECURITY_KEYWORDS | _KEY_KEYWORDS):
        found.update(sorted(hit_keys & (_SECURITY_KEYWORDS | _KEY_KEYWORDS)))
    if hit_keys & _PERSONAL_DATA_KEYWORDS:
        found.update(sorted(hit_keys & _PERSONAL_DATA_KEYWORDS))
    if hit_keys & (_USER_CONTEXT_KEYWORDS | {"rg"}):
        found.update(sorted(hit_keys & (_USER_CONTEXT_KEYWORDS | {"rg"})))
    if hit_keys & _RISK_KEYWORDS:
        found.update(sorted(hit_keys & _RISK_KEYWORDS))
    return found


def _compute_signals(
    sensitive_areas: list[str],
    stack: list[str],
    ci: str | None,
    databases: list[str],
    base: Path,
    keyword_hits: dict[str, list[str]] | None = None,
) -> dict:
    sa = set(sensitive_areas)
    keyword_hits = keyword_hits or {}
    raw_hits = keyword_hits.get("raw_keyword_hits", {})
    user_interaction_hits = keyword_hits.get("user_interaction_hits", {})
    hit_keys = set(raw_hits)

    touches_auth = bool(sa & _AUTH_KEYWORDS)
    personal_data = bool(sa & (_PERSONAL_DATA_KEYWORDS | _SECURITY_KEYWORDS | _KEY_KEYWORDS | {"rg"}))
    external = bool(sa & {"payment", "billing", "pagamento", "cobrança"}) or bool(databases)

    prod_impact = (
        "high" if any(k in sa for k in {"auth", "permission", "payment", "token", "secret", "password"})
        else "medium" if any(k in sa for k in {"user", "database", "migration"})
        else "low"
    )

    has_database = bool(databases) or bool(sa & {"database", "sqlite", "schema"})

    return {
        "touches_auth": touches_auth,
        "personal_data_possible": personal_data,
        "external_integrations": external,
        "production_impact": prod_impact,
        "user_interaction": bool(user_interaction_hits) or "input" in hit_keys or _project_uses_input(base),
        "has_ci": ci is not None,
        "has_tests": _has_tests(base),
        "has_docker": any("docker" in s.lower() for s in stack),
        "has_database": has_database,
    }


def _project_uses_input(base: Path) -> bool:
    for path in _python_files(base):
        try:
            if "input(" in path.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


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


def _collect_project_signals(
    base: Path,
    stack: list[str],
    ci: str | None,
    databases: list[str],
    keyword_hits: dict[str, dict[str, list[str]]],
    signals: dict,
    confidence: str,
) -> dict:
    extension_counts: dict[str, int] = {}
    sample_files: list[str] = []
    for path in base.rglob("*"):
        try:
            rel = path.relative_to(base)
        except ValueError:
            continue
        if should_ignore_path(rel, excluded_suffixes=set()) or not path.is_file():
            continue
        suffix = path.suffix.lower() or "<none>"
        extension_counts[suffix] = extension_counts.get(suffix, 0) + 1
        if len(sample_files) < 50:
            sample_files.append(str(rel))

    return {
        "files": {
            "sample": sample_files,
            "extensions": dict(sorted(extension_counts.items())),
        },
        "stack_candidates": stack,
        "ci_candidate": ci,
        "database_candidates": databases,
        "raw_keyword_hits": [
            {"keyword": keyword, "paths": paths}
            for keyword, paths in sorted(keyword_hits["raw_keyword_hits"].items())
        ],
        "user_interaction_hits": [
            {"keyword": keyword, "paths": paths}
            for keyword, paths in sorted(keyword_hits["user_interaction_hits"].items())
        ],
        "strong_sensitive_hits": [
            {"keyword": keyword, "paths": paths}
            for keyword, paths in sorted(keyword_hits["strong_sensitive_hits"].items())
        ],
        "weak_sensitive_hits": [
            {"keyword": keyword, "paths": paths}
            for keyword, paths in sorted(keyword_hits["weak_sensitive_hits"].items())
        ],
        "signals": signals,
        "confidence": confidence,
        "notes": [
            "Deterministic signals are conservative and may need agent-assisted review.",
            "CLI input() is treated as local user interaction, not personal data by itself.",
        ],
    }


def _infer_project_type(stack: list[str], base: Path, databases: list[str]) -> str:
    lowered = {item.lower() for item in stack}
    if "fastapi" in lowered or "django" in lowered or "flask" in lowered:
        return "python_web"
    if "python" in lowered:
        py_files = _python_files(base)
        if _project_uses_input(base) or len(py_files) <= 3:
            return "python_cli"
        return "generic_python"
    if "next.js" in " ".join(lowered) or "react" in " ".join(lowered):
        return "web_app"
    if "node" in lowered:
        return "node_project"
    if databases:
        return "data_or_database_project"
    return "unknown"


def _architecture_summary(project_type: str, stack: list[str], signals: dict) -> str:
    if project_type == "python_cli":
        return "Python command-line project with local user interaction."
    if project_type == "generic_python":
        return "Python project without a detected web framework."
    if project_type == "python_web":
        return "Python web application based on detected framework signals."
    if signals.get("has_database"):
        return "Project includes database or schema-related signals."
    if stack:
        return f"Project appears to use {', '.join(stack)}."
    return "Project architecture could not be confidently inferred from deterministic signals."


def _confidence_and_gray_areas(
    project_type: str,
    stack: list[str],
    keyword_hits: dict[str, dict[str, list[str]]],
    signals: dict,
) -> tuple[str, list[str], list[str]]:
    assumptions: list[str] = []
    gray_areas: list[str] = []
    confidence = "medium"

    if not stack:
        confidence = "low"
        gray_areas.append("Confirmar stack principal do projeto.")
    else:
        assumptions.append(f"Stack inferred from deterministic files: {', '.join(stack)}.")

    if project_type in {"python_cli", "generic_python"}:
        assumptions.append("Projeto Python inferido por arquivos .py versionados.")
        if signals.get("user_interaction"):
            assumptions.append("input() foi tratado como interação local de CLI, não como dado pessoal.")

    weak_hits = keyword_hits.get("weak_sensitive_hits", {})
    if project_type not in {"python_cli", "generic_python"} and (weak_hits.get("user") or weak_hits.get("users")):
        gray_areas.append("Verificar se ocorrências de user/users são apenas interação local ou representam identidade persistida.")

    if signals.get("has_database"):
        gray_areas.append("Confirmar se os sinais de banco representam schema produtivo ou armazenamento local simples.")

    if not gray_areas and stack:
        confidence = "high"

    return confidence, assumptions, gray_areas


def _write_scan_files(base: Path, result: ScanResult) -> list[str]:
    devforge_dir = get_devforge_dir(base)
    prcp_dir = devforge_dir / "prcp"
    prcp_dir.mkdir(exist_ok=True)
    context_dir = devforge_dir / "context"
    context_dir.mkdir(exist_ok=True)

    profile = {
        "project_name": result.project_name,
        "project_type": result.project_type,
        "scanned_at": result.scanned_at,
        "detected_stack": result.detected_stack,
        "architecture_summary": result.architecture_summary,
        "has_database": result.has_database,
        "has_auth": result.has_auth,
        "personal_data_possible": result.personal_data_possible,
        "external_integrations": result.external_integrations,
        "production_impact": result.production_impact,
        "ci_detected": result.ci_detected,
        "databases_detected": result.databases_detected,
        "sensitive_areas": result.sensitive_areas,
        "signals": result.signals,
        "prcp": {
            "baseline_level": result.baseline_level,
            "task_elevation": result.task_elevation,
        },
        "confidence": result.confidence,
        "profile_status": result.profile_status,
        "requires_agent_review": result.requires_agent_review,
        "requires_user_approval": result.requires_user_approval,
        "assumptions": result.assumptions,
        "gray_areas": result.gray_areas,
        "source": result.source,
    }

    signals_path = prcp_dir / "project-signals.json"
    signals_path.write_text(
        json.dumps(result.project_signals, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    brief_path = context_dir / "project-profile-brief.md"
    brief_path.write_text(_render_project_profile_brief(result), encoding="utf-8")

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
        "",
        "## Project Profile",
        "",
        f"- Type: {result.project_type}",
        f"- Confidence: {result.confidence}",
        f"- Source: {result.source}",
        f"- Profile Status: {result.profile_status}",
        f"- Requires Agent Review: {str(result.requires_agent_review).lower()}",
        f"- Requires User Approval: {str(result.requires_user_approval).lower()}",
    ]
    if result.signals.get("user_interaction"):
        report_lines.extend([
            "",
            "## Notes",
            "",
            "CLI input detected as local user interaction, not personal data by itself.",
        ])
    report_path = prcp_dir / "scan-report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return [
        str(signals_path.relative_to(base)),
        str(brief_path.relative_to(base)),
        str(profile_path.relative_to(base)),
        str(report_path.relative_to(base)),
    ]


def _render_project_profile_brief(result: ScanResult) -> str:
    return "\n".join([
        f"# DevForge Project Profile Brief — {result.project_name}",
        "",
        "## Purpose",
        "",
        "Analyze this repository and improve `.devforge/prcp/project-profile.json`.",
        "",
        "## Hard rules",
        "",
        "- Do not implement code.",
        "- Do not alter application files.",
        "- Only update `.devforge/prcp/project-profile.json` if changes are needed.",
        "- Do not treat `input()` in a local CLI as personal data automatically.",
        "- Distinguish local user interaction from personal data collection or persistence.",
        "",
        "## Analyze",
        "",
        "- stack and project type",
        "- architecture summary",
        "- real database, auth, personal-data and integration risks",
        "- production impact",
        "- assumptions and gray areas",
        "",
        "## Deterministic signals",
        "",
        "```json",
        json.dumps(result.project_signals, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Expected Project Profile fields",
        "",
        "- project_name",
        "- project_type",
        "- detected_stack",
        "- architecture_summary",
        "- has_database",
        "- has_auth",
        "- personal_data_possible",
        "- external_integrations",
        "- production_impact",
        "- sensitive_areas",
        "- prcp.baseline_level",
        "- prcp.task_elevation",
        "- confidence",
        "- assumptions",
        "- gray_areas",
        "- source: agent_assisted",
        "- profile_status: reviewed",
        "- requires_user_approval: true",
        "",
    ])


_AUTH_AREA_TAGS = {"auth", "login", "logout", "permission", "permissions", "rbac", "role", "roles"}
def _suggest_next_spec(base: Path, sensitive_areas: list[str]) -> str | None:
    """Pick the SPEC file to suggest in scan output.

    Order of preference:
      1. If sensitive_areas mention auth/login/permissions AND a SPEC
         whose filename contains 'AUTH' exists, suggest that one.
      2. Otherwise, the first *.md inside specs/ in alphabetical order.
      3. If no SPEC exists, return None so scan can suggest devforge specify.
    """
    specs_dir = base / "specs"
    if not specs_dir.is_dir():
        return None

    md_files = sorted(p for p in specs_dir.glob("*.md") if p.is_file())
    if not md_files:
        return None

    if _AUTH_AREA_TAGS & set(sensitive_areas):
        for p in md_files:
            if "auth" in p.name.lower():
                return f"specs/{p.name}"

    return f"specs/{md_files[0].name}"


def _suggest_next_command(suggested_next_spec: str | None) -> str:
    if suggested_next_spec:
        return f"devforge plan --spec {suggested_next_spec}"
    return 'devforge specify --idea "Describe your feature idea"'


def _recommended_next_command(result: ScanResult) -> str:
    if result.confidence in {"low", "medium"} or result.gray_areas:
        return "devforge scan --agent codex"
    return _suggest_next_command(result.suggested_next_spec)


def run_scan(project_name: str, base: Path) -> ScanResult:
    stack, ci, databases = _detect_stack(base)
    extra_db, extra_db_areas = _detect_database_signals(base)
    for label in extra_db:
        if label not in databases:
            databases.append(label)
    keyword_hits = _collect_keyword_hits(base)
    sensitive_areas = sorted(_sensitive_areas_from_hits(keyword_hits["strong_sensitive_hits"], extra_db_areas))
    signals = _compute_signals(sensitive_areas, stack, ci, databases, base, keyword_hits)
    baseline, elevation = _calculate_prcp(signals, stack)
    project_type = _infer_project_type(stack, base, databases)
    confidence, assumptions, gray_areas = _confidence_and_gray_areas(
        project_type, stack, keyword_hits, signals
    )
    project_signals = _collect_project_signals(
        base, stack, ci, databases, keyword_hits, signals, confidence
    )

    suggested_next_spec = _suggest_next_spec(base, sensitive_areas)
    result = ScanResult(
        project_name=project_name,
        project_type=project_type,
        detected_stack=stack,
        ci_detected=ci,
        databases_detected=databases,
        architecture_summary=_architecture_summary(project_type, stack, signals),
        has_database=signals["has_database"],
        has_auth=signals["touches_auth"],
        personal_data_possible=signals["personal_data_possible"],
        external_integrations=signals["external_integrations"],
        production_impact=signals["production_impact"],
        sensitive_areas=sensitive_areas,
        signals=signals,
        baseline_level=baseline,
        task_elevation=elevation,
        confidence=confidence,
        profile_status="draft",
        requires_agent_review=confidence != "high",
        requires_user_approval=True,
        assumptions=assumptions,
        gray_areas=gray_areas,
        source="deterministic",
        project_signals=project_signals,
        suggested_next_spec=suggested_next_spec,
    )
    result.suggested_next_command = _recommended_next_command(result)
    result.generated_files = _write_scan_files(base, result)
    return result
