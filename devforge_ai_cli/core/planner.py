import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from devforge_ai_cli.core.agent_instructions import render_agent_instructions
from devforge_ai_cli.core.evidence_rules import check_evidence
from devforge_ai_cli.core.paths import TEMPLATES_DIR, get_devforge_dir
from devforge_ai_cli.policy_engine.decisions import PolicyDecision

ALLOWED_USES = [
    "arquitetura",
    "testes",
    "revisão",
    "arquivos de código versionados",
    "contratos públicos",
    "documentação do projeto",
]

BLOCKED_USES = [
    "segredos reais",
    "tokens de produção",
    "senhas",
    "dados pessoais brutos",
    "dumps de banco",
    "credenciais privadas",
]

CLI_BLOCKED_USES = [
    "login/auth",
    "banco",
    "cloud",
    "persistência em arquivo quando fora de escopo",
    "dados pessoais",
    "segredos/tokens",
    "integração externa",
]

_AUTH_KWS = {
    "auth", "login", "logout", "jwt", "oauth", "token", "password", "secret",
    "rbac", "role", "roles", "permission", "permissions",
}
_AUTH_EXTRA_TERMS = {"senha", "autenticação", "authentication", "permissões", "papéis"}
_AUTH_PHRASES = {
    "sessão autenticada", "authenticated session", "session cookie",
    "usuário autenticado", "authenticated user", "cadastro de usuário",
    "user registration", "auth user",
}
_AUTH_NEGATION_PATTERNS = (
    r"\bsem\s+(?:login\s*/\s*auth|login|auth|autenticação|autenticacao|senha|token|permissões|permissoes|papéis|papeis)\b",
    r"\bn[aã]o\s+(?:adicionar|usar|criar|implementar|exigir)\s+(?:login|auth|autenticação|autenticacao|senha|token|permissões|permissoes|papéis|papeis)\b",
    r"\bno\s+(?:login|auth|authentication|password|token|rbac|roles?|permissions?)\b",
    r"\bwithout\s+(?:login|auth|authentication|password|token|rbac|roles?|permissions?)\b",
)
_LOCAL_SESSION_TERMS = {
    "histórico da sessão", "sessão local", "sessão de uso", "durante a sessão",
    "session history", "in-memory session", "local session",
}
_PAYMENT_KWS = {"payment", "billing", "pagamento", "cobrança"}
_DB_KWS = {"migration", "database", "schema", "migrate"}
_DB_EXTRA_TERMS = {"banco", "db", "sqlite", "tabela", "create table", "alter table", "drop table"}
_DB_NEGATION_TERMS = (
    "arquivo",
    "persistência",
    "persistencia",
    "banco",
    "db",
    "database",
    "sqlite",
    "schema",
    "tabela",
    "migração",
    "migracao",
    "migration",
    "migrate",
)
_DB_NEGATION_CHAIN = "|".join(re.escape(term) for term in _DB_NEGATION_TERMS)
_DB_NEGATION_PATTERNS = (
    rf"\bsem\s+(?:{_DB_NEGATION_CHAIN})(?:(?:\s*/\s*|\s*,\s*|\s*;\s*|\s+ou\s+|\s+e\s+)(?:{_DB_NEGATION_CHAIN}))*\b",
    rf"\bn[aã]o\s+(?:adicionar|usar|criar|alterar|persistir|tocar|exigir)\s+(?:{_DB_NEGATION_CHAIN})(?:(?:\s*/\s*|\s*,\s*|\s*;\s*|\s+ou\s+|\s+e\s+)(?:{_DB_NEGATION_CHAIN}))*\b",
    r"\bno\s+(?:file|db|database|sqlite|schema|persistence|migration)\b",
    r"\bwithout\s+(?:file|db|database|sqlite|schema|persistence|migration)\b",
)
_EXTERNAL_KWS = {
    "cloud", "nuvem", "api externa", "external integration", "integração externa",
    "integracao externa", "webhook", "aws", "gcp", "azure", "s3", "stripe",
}
_EXTERNAL_NEGATION_PATTERNS = (
    r"\bsem\s+(?:cloud|nuvem|api externa|integração externa|integracao externa|webhook|aws|gcp|azure|s3|stripe)\b",
    r"\bn[aã]o\s+(?:adicionar|usar|criar|integrar|chamar|exigir)\s+(?:cloud|nuvem|api externa|integração externa|integracao externa|webhook|aws|gcp|azure|s3|stripe)\b",
    r"\bno\s+(?:cloud|external integration|webhook|aws|gcp|azure|s3|stripe)\b",
    r"\bwithout\s+(?:cloud|external integration|webhook|aws|gcp|azure|s3|stripe)\b",
)
_SECRET_KWS = {"secret", "segredo", "segredos", "token", "api_key", "private_key", "credential", "credencial"}
_SECRET_NEGATION_PATTERNS = (
    r"\bsem\s+(?:segredos?|tokens?|secret|credentials?|credenciais?|api[_-]?key|private[_-]?key)\b",
    r"\bn[aã]o\s+(?:adicionar|usar|criar|exigir|tocar)\s+(?:segredos?|tokens?|secret|credentials?|credenciais?|api[_-]?key|private[_-]?key)\b",
    r"\bno\s+(?:secrets?|tokens?|credentials?|api[_-]?key|private[_-]?key)\b",
    r"\bwithout\s+(?:secrets?|tokens?|credentials?|api[_-]?key|private[_-]?key)\b",
)
_TASK_PRIORITY_TERMS = {"prioridade", "priority"}
_TASK_CONTEXT_TERMS = {"tarefa", "tarefas", "task", "tasks", "todo", "todos"}
_CALC_HISTORY_TERMS = {"histórico", "historico", "history", "cálculo", "calculo", "calculation", "calculator", "calculadora"}
_PLAN_REVIEW_RECOMMENDATION = (
    "Review this plan before implementation; consider devforge scan --agent codex "
    "for assisted project profiling."
)

_TASK_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "auth": [
        ("Mapear fluxo de autenticação", "arch"),
        ("Revisar permissões e papéis", "review"),
        ("Definir testes mínimos de auth", "test"),
        ("Preparar rollback plan", "rollback"),
        ("Solicitar revisão humana", "review"),
    ],
    "payment": [
        ("Mapear fluxo de pagamento", "arch"),
        ("Revisar compliance e conformidade", "review"),
        ("Definir testes mínimos de pagamento", "test"),
        ("Preparar rollback plan", "rollback"),
        ("Solicitar revisão humana", "review"),
    ],
    "database": [
        ("Mapear mudanças de schema", "arch"),
        ("Revisar migrations e rollback de banco", "review"),
        ("Definir testes de migração", "test"),
        ("Preparar rollback plan", "rollback"),
        ("Solicitar revisão humana", "review"),
    ],
    "task_priority": [
        ("Mapear modelo atual de tarefas", "arch"),
        ("Adicionar campo de prioridade ao schema SQLite", "schema"),
        ("Atualizar formulário de criação de tarefa", "ui"),
        ("Exibir prioridade na lista de tarefas", "ui"),
        ('Definir valor padrão "Média"', "config"),
        ("Preparar testes manuais e rollback plan", "rollback"),
    ],
    "cli_session_history": [
        ("Mapear fluxo atual da calculadora CLI", "arch"),
        ("Adicionar histórico em memória da sessão", "feature"),
        ("Registrar operações válidas com expressão e resultado", "feature"),
        ("Exibir histórico por opção do menu ou antes de sair", "ui"),
        ("Garantir que operações inválidas não entrem no histórico", "test"),
        ("Preparar teste manual da calculadora CLI", "test"),
    ],
    "generic_cli_feature": [
        ("Mapear fluxo CLI atual", "arch"),
        ("Implementar comportamento solicitado na SPEC", "feature"),
        ("Atualizar mensagens/opções do menu se necessário", "ui"),
        ("Validar fluxo manualmente", "test"),
        ("Registrar test_report", "test"),
    ],
    "generic": [
        ("Revisar escopo e critérios de aceite", "review"),
        ("Mapear dependências e impacto", "arch"),
        ("Definir testes mínimos", "test"),
        ("Preparar rollback plan", "rollback"),
        ("Solicitar revisão humana", "review"),
    ],
}


def _spec_lower(spec_data: dict) -> str:
    return spec_data.get("content", "").lower()


def _hits(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sim", "s"}
    return bool(value)


def _strip_patterns(text: str, patterns: tuple[str, ...]) -> str:
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _auth_hits(text: str) -> bool:
    text = _strip_patterns(text.lower(), _AUTH_NEGATION_PATTERNS)
    if any(phrase in text for phrase in _AUTH_PHRASES):
        return True
    return _hits(text, _AUTH_KWS | _AUTH_EXTRA_TERMS)


def _database_hits(text: str) -> bool:
    cleaned = _strip_patterns(text.lower(), _DB_NEGATION_PATTERNS)
    return _hits(cleaned, _DB_KWS | _DB_EXTRA_TERMS)


def _external_hits(text: str) -> bool:
    cleaned = _strip_patterns(text.lower(), _EXTERNAL_NEGATION_PATTERNS)
    return _hits(cleaned, _EXTERNAL_KWS)


def _secret_hits(text: str) -> bool:
    cleaned = _strip_patterns(text.lower(), _SECRET_NEGATION_PATTERNS)
    return _hits(cleaned, _SECRET_KWS)


def _task_priority_hits(text: str) -> bool:
    lowered = text.lower()
    return _hits(lowered, _TASK_PRIORITY_TERMS) and _hits(lowered, _TASK_CONTEXT_TERMS)


def _local_session_hits(text: str) -> bool:
    text = text.lower()
    return any(term in text for term in _LOCAL_SESSION_TERMS)


def _cli_history_hits(text: str) -> bool:
    lowered = text.lower()
    return _hits(lowered, _CALC_HISTORY_TERMS) and (
        _local_session_hits(lowered)
        or "memória" in lowered
        or "memoria" in lowered
        or "in-memory" in lowered
    )


def _profile_bool(profile: dict, top_level: str, signal_key: str | None = None) -> bool:
    if top_level in profile:
        return _as_bool(profile.get(top_level))
    signals = profile.get("signals", {})
    return _as_bool(signals.get(signal_key or top_level, False))


def _low_risk_python_cli_profile(profile: dict) -> bool:
    production_impact = str(profile.get("production_impact", "low")).lower()
    if profile.get("project_type") != "python_cli":
        return False
    return (
        not _profile_bool(profile, "has_database")
        and not _profile_bool(profile, "has_auth", "touches_auth")
        and not _profile_bool(profile, "personal_data_possible")
        and not _profile_bool(profile, "external_integrations")
        and production_impact not in {"high", "critical", "production"}
    )


def _profile_baseline(profile: dict) -> str:
    prcp = profile.get("prcp", {})
    baseline = prcp.get("task_elevation") or prcp.get("baseline_level") or "Standard"
    if _low_risk_python_cli_profile(profile):
        baseline_level = prcp.get("baseline_level", baseline)
        if baseline == "Hardened" and baseline_level in {"Minimal", "Standard"}:
            return baseline_level
    return baseline


def _spec_declares_high_impact(spec_data: dict) -> bool:
    content = _spec_lower(spec_data)
    return _hits(content, {"produção", "production", "critical", "crítico", "critico", "alto impacto"})


def _spec_declares_strong_risk(spec_data: dict) -> bool:
    content = _spec_lower(spec_data)
    return (
        _auth_hits(content)
        or _database_hits(content)
        or _external_hits(content)
        or _secret_hits(content)
        or _spec_declares_high_impact(spec_data)
    )


def _is_lightweight_python_cli_feature(profile: dict, spec_data: dict) -> bool:
    classification = classify_plan(spec_data, profile)
    return (
        _low_risk_python_cli_profile(profile)
        and classification.domain in {"cli_session_history", "generic_cli_feature"}
        and not classification.touches_database
        and not _spec_declares_strong_risk(spec_data)
    )


@dataclass(frozen=True)
class _PlanClassification:
    domain: str
    touches_database: bool
    plan_confidence: str
    plan_recommendation: str = ""


def _confidence_for(profile: dict, *, clear_domain: bool) -> str:
    profile_confidence = str(profile.get("confidence", "low")).lower()
    profile_approved = profile.get("profile_status") == "approved"
    requires_agent_review = _as_bool(profile.get("requires_agent_review", False))

    if clear_domain:
        if profile_approved and profile_confidence == "high":
            return "high"
        return "medium"
    if requires_agent_review or profile_confidence in {"", "unknown", "low"}:
        return "low"
    return "medium"


def _classification(
    domain: str,
    touches_database: bool,
    profile: dict,
    *,
    clear_domain: bool,
) -> _PlanClassification:
    confidence = _confidence_for(profile, clear_domain=clear_domain)
    recommendation = _PLAN_REVIEW_RECOMMENDATION if confidence != "high" else ""
    return _PlanClassification(
        domain=domain,
        touches_database=touches_database,
        plan_confidence=confidence,
        plan_recommendation=recommendation,
    )


def classify_plan(spec_data: dict, profile: dict | None = None) -> _PlanClassification:
    """Infer SPEC domain, DB impact and planner confidence.

    The planner is intentionally conservative: specific templates are used
    only when the SPEC has a clear domain signal. Ambiguous specs fall back
    to a project-type generic plan and expose plan_confidence for review.
    """
    profile = profile or {}
    content = _spec_lower(spec_data)

    spec_id = (spec_data.get("spec_id") or "").lower()
    title = (spec_data.get("title") or "").lower()
    sections = spec_data.get("sections") or {}
    objective = (sections.get("objetivo") or sections.get("objective") or "").lower()
    headline = f"{spec_id} {title} {objective}".strip()

    touches_database = _database_hits(content)
    project_type = profile.get("project_type", "")

    if headline:
        if _task_priority_hits(headline):
            return _classification("task_priority", touches_database, profile, clear_domain=True)
        if project_type == "python_cli" and _cli_history_hits(headline):
            return _classification("cli_session_history", touches_database, profile, clear_domain=True)
        if _auth_hits(headline):
            return _classification("auth", touches_database, profile, clear_domain=True)
        if _hits(headline, _PAYMENT_KWS):
            return _classification("payment", touches_database, profile, clear_domain=True)
        if _database_hits(headline):
            return _classification("database", touches_database, profile, clear_domain=True)

    if project_type == "python_cli" and _cli_history_hits(content):
        return _classification("cli_session_history", touches_database, profile, clear_domain=True)
    if project_type == "python_cli":
        return _classification("generic_cli_feature", touches_database, profile, clear_domain=False)
    if _auth_hits(content):
        return _classification("auth", touches_database, profile, clear_domain=True)
    if _hits(content, _PAYMENT_KWS):
        return _classification("payment", touches_database, profile, clear_domain=True)
    if _task_priority_hits(content):
        return _classification("task_priority", touches_database, profile, clear_domain=True)
    if touches_database:
        return _classification("database", touches_database, profile, clear_domain=True)
    return _classification("generic_feature", touches_database, profile, clear_domain=False)


def classify_spec_domain(spec_data: dict, profile: dict | None = None) -> tuple[str, bool]:
    """Infer SPEC domain and whether it touches a database.

    Returns (domain, touches_database) where domain is one of:
      'auth', 'payment', 'task_priority', 'generic_feature'.

    The classifier is headline-first: the SPEC id, title and objective
    section have absolute precedence over the body and over the scan
    profile's sensitive_areas. This protects against two real-world
    sources of false positives:

      1. The project has auth-related files (user.py, login.py,
         permissions/) detected by scan, so sensitive_areas inherits
         'auth'. A SPEC about task priority must NOT inherit that.
      2. The SPEC body mentions an auth-ish word incidentally (e.g.
         "a ordem de prioridade persiste durante a sessão do usuário").
         The headline still owns the classification.

    Only when the headline is silent do we fall back to scanning the
    full content and the scan profile.

    touches_database stays orthogonal to the domain and is True when the
    SPEC text declares database/schema work.
    """
    plan = classify_plan(spec_data, profile)
    return plan.domain, plan.touches_database


def compute_effective_prcp(profile: dict, spec_data: dict) -> str:
    """Return the PRCP the plan should apply, which can elevate the scan baseline.

    Today the only elevation rule at plan time is: if the SPEC itself
    declares database/schema work, the plan applies Hardened regardless
    of the scan baseline. Auth/personal-data already elevate at scan time.
    """
    baseline = _profile_baseline(profile)
    _, touches_database = classify_spec_domain(spec_data, profile)
    if _is_lightweight_python_cli_feature(profile, spec_data):
        return baseline if baseline in {"Minimal", "Standard"} else "Standard"
    if touches_database:
        return "Hardened"
    return baseline


def compute_allowed_uses(spec_data: dict, profile: dict | None = None) -> list[str]:
    """Allowed uses for the Context Pack, expanded when the SPEC needs them."""
    uses = list(ALLOWED_USES)
    profile = profile or {}
    _, touches_database = classify_spec_domain(spec_data, profile)
    if profile.get("project_type") == "python_cli":
        cli_items = ["calculator.py", "fluxo CLI local", "testes manuais", "py_compile"]
        if classify_plan(spec_data, profile).domain == "cli_session_history":
            cli_items.insert(2, "histórico em memória")
        for item in cli_items:
            if item not in uses:
                uses.append(item)
    if touches_database and "schema local" not in uses:
        uses.append("schema local")
    return uses


def compute_blocked_uses(spec_data: dict, profile: dict | None = None) -> list[str]:
    uses = list(BLOCKED_USES)
    profile = profile or {}
    if profile.get("project_type") == "python_cli":
        for item in CLI_BLOCKED_USES:
            if item not in uses:
                uses.append(item)
    return uses


@dataclass
class PlanResult:
    spec_id: str
    plan_id: str
    context_pack_id: str
    spec_path: str
    spec_title: str
    domain: str
    prcp_level: str
    plan_confidence: str
    plan_recommendation: str
    policy_decision: str
    tasks: list[dict]
    allowed_uses: list[str]
    blocked_uses: list[str]
    required_evidence: list[str]
    project_profile: dict = field(default_factory=dict)
    generated_files: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    implementation_brief_path: str = ""


def _task_prefix(spec_id: str) -> str:
    parts = spec_id.split("-")
    if parts and parts[0].upper() in ("SPEC", "US", "FEATURE"):
        inner = parts[1:-1] if len(parts) > 2 and parts[-1].isdigit() else parts[1:]
        return "-".join(inner) if inner else "TASK"
    return parts[0] if parts else "TASK"


def parse_spec(spec_path: Path) -> dict[str, Any]:
    content = spec_path.read_text(encoding="utf-8", errors="ignore")

    # spec_id from filename
    spec_id = re.sub(r"\.md$", "", spec_path.name, flags=re.IGNORECASE).upper()

    # title from first heading
    title = spec_id
    first_h1 = re.match(r"^#\s+(.+)", content, re.MULTILINE)
    if first_h1:
        raw = first_h1.group(1).strip()
        # "SPEC-AUTH-001 — Login e RBAC" → extract spec_id and title
        m = re.match(r"^([A-Z][A-Z0-9\-]+)\s+[—–-]\s+(.+)$", raw)
        if m:
            spec_id = m.group(1).strip()
            title = m.group(2).strip()
        else:
            title = raw

    # parse sections
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line[3:].strip().lower()
            lines = []
        elif not line.startswith("# "):
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()

    status = "Unknown"
    status_match = re.search(r"^Status:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
    if status_match:
        status = status_match.group(1).strip()

    return {
        "spec_id": spec_id,
        "title": title,
        "status": status,
        "content": content,
        "sections": sections,
    }


def generate_tasks(spec_id: str, spec_data: dict, profile: dict) -> list[dict]:
    domain = classify_plan(spec_data, profile).domain
    template_key = domain if domain in _TASK_TEMPLATES else "generic"

    prefix = _task_prefix(spec_id)
    templates = _TASK_TEMPLATES[template_key]

    return [
        {"id": f"TASK-{prefix}-{i:03d}", "description": desc, "type": typ}
        for i, (desc, typ) in enumerate(templates, start=1)
    ]


def determine_policy(profile: dict, spec_data: dict) -> tuple[str, list[str]]:
    domain, touches_database = classify_spec_domain(spec_data, profile)
    effective_prcp = compute_effective_prcp(profile, spec_data)

    hardened = effective_prcp == "Hardened"
    touches_auth = domain == "auth" or (
        _profile_bool(profile, "has_auth", "touches_auth")
    )
    personal_data = _profile_bool(profile, "personal_data_possible")
    external_integration = _profile_bool(profile, "external_integrations") or _external_hits(_spec_lower(spec_data))
    secrets = _secret_hits(_spec_lower(spec_data))
    high_impact = str(profile.get("production_impact", "low")).lower() in {"high", "critical", "production"}
    high_impact = high_impact or _spec_declares_high_impact(spec_data)
    spec_has_risk = domain in {"auth", "payment"}

    if _is_lightweight_python_cli_feature(profile, spec_data):
        decision = PolicyDecision.ALLOW
        required = ["test_report", "audit_log"]
    elif (
        hardened
        or touches_auth
        or personal_data
        or external_integration
        or secrets
        or high_impact
        or spec_has_risk
        or touches_database
    ):
        decision = PolicyDecision.REQUIRE_APPROVAL
        required = ["test_report", "human_review", "rollback_plan", "audit_log"]
    else:
        decision = PolicyDecision.ALLOW
        required = ["test_report", "audit_log"] if domain in {"cli_session_history", "generic_cli_feature"} else ["audit_log"]

    return decision.value, required


def _write_plan_files(base: Path, result: PlanResult) -> list[str]:
    from jinja2 import Environment, FileSystemLoader

    devforge_dir = get_devforge_dir(base)
    for d in ("plans", "context", "policy"):
        (devforge_dir / d).mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    generated: list[str] = []

    # Plan Pack
    plan_path = devforge_dir / "plans" / f"PLAN-{result.spec_id}.md"
    tmpl = env.get_template("plan-pack.md.j2")
    plan_path.write_text(
        tmpl.render(
            spec_id=result.spec_id,
            spec_title=result.spec_title,
            spec_path=result.spec_path,
            timestamp=result.generated_at,
            prcp_level=result.prcp_level,
            domain=result.domain,
            plan_confidence=result.plan_confidence,
            plan_recommendation=result.plan_recommendation,
            tasks=result.tasks,
            policy_decision=result.policy_decision,
        ),
        encoding="utf-8",
    )
    generated.append(str(plan_path.relative_to(base)))

    # Context Pack
    ctx_path = devforge_dir / "context" / "context-pack.md"
    tmpl = env.get_template("context-pack.md.j2")
    ctx_path.write_text(
        tmpl.render(
            spec_id=result.spec_id,
            timestamp=result.generated_at,
            allowed_uses=result.allowed_uses,
            blocked_uses=result.blocked_uses,
            required_evidence=result.required_evidence,
            project_profile=result.project_profile,
            plan_confidence=result.plan_confidence,
            plan_recommendation=result.plan_recommendation,
        ),
        encoding="utf-8",
    )
    generated.append(str(ctx_path.relative_to(base)))

    # Policy Decision JSON
    pol_path = devforge_dir / "policy" / f"POLICY-DECISION-{result.spec_id}.json"
    pol_path.write_text(
        json.dumps(
            {
                "id": f"POL-{result.spec_id}",
                "spec_id": result.spec_id,
                "plan_id": result.plan_id,
                "decision": result.policy_decision,
                "prcp_level": result.prcp_level,
                "domain": result.domain,
                "plan_confidence": result.plan_confidence,
                "plan_recommendation": result.plan_recommendation,
                "required_evidence": result.required_evidence,
                "timestamp": result.generated_at,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    generated.append(str(pol_path.relative_to(base)))

    agent_path = render_agent_instructions(
        base,
        spec_id=result.spec_id,
        plan_id=result.plan_id,
        policy_decision=result.policy_decision,
        prcp_level=result.prcp_level,
        allowed_uses=result.allowed_uses,
        blocked_uses=result.blocked_uses,
        required_evidence=result.required_evidence,
        recommended_scope=[t["description"] for t in result.tasks],
    )
    generated.append(str(agent_path.relative_to(base)))

    brief_path = _write_implementation_brief(base, env, result)
    generated.append(str(brief_path.relative_to(base)))
    result.implementation_brief_path = str(brief_path.relative_to(base))

    return generated


def _extract_objective(sections: dict) -> str:
    for key in ("objetivo", "objective", "goal"):
        if sections.get(key):
            return sections[key].strip()
    return ""


def _extract_bulleted(sections: dict, keys: tuple[str, ...]) -> list[str]:
    """Pull bullet items (lines starting with - or *) from the first
    matching section. Falls back to non-empty stripped lines."""
    for key in keys:
        body = sections.get(key)
        if not body:
            continue
        items: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("-", "*", "•")):
                items.append(stripped.lstrip("-*• ").strip())
            else:
                items.append(stripped)
        return [i for i in items if i]
    return []


def _compute_in_scope(spec_data: dict, profile: dict, base: Path) -> list[str]:
    """Best-effort guess of in-scope paths based on the project and SPEC.

    Always-allowed: docs/rollback/, .devforge/test-reports/, .devforge/reviews/
    (where the agent may drop generated evidence).

    Project hints: include common application files that exist (app.py,
    db_create.py, models.py, templates/) and the SPEC file itself.
    """
    candidates: list[str] = []
    for name in ("app.py", "db_create.py", "database.py", "models.py", "main.py"):
        if (base / name).exists():
            candidates.append(name)
    if profile.get("project_type") == "python_cli":
        for path in sorted(base.glob("*.py")):
            candidates.append(path.name)
    for name in ("templates", "static", "src", "lib"):
        if (base / name).is_dir():
            candidates.append(f"{name}/")
    # SPEC itself
    spec_rel = spec_data.get("relpath")
    if spec_rel:
        candidates.append(spec_rel)
    candidates.append(".devforge/test-reports/")
    if profile.get("project_type") != "python_cli":
        candidates.extend([
            "docs/rollback/",
            ".devforge/reviews/",
        ])
    # de-dup preserving order
    seen: set[str] = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def _write_implementation_brief(base: Path, env, result: PlanResult) -> Path:
    devforge_dir = get_devforge_dir(base)
    brief_path = devforge_dir / "context" / f"implementation-brief-{result.spec_id}.md"

    spec_data = result._spec_data  # set by generate_plan, see below
    profile = result._profile or {}

    sections = spec_data.get("sections") or {}
    objective = _extract_objective(sections)
    acceptance_criteria = _extract_bulleted(sections, ("critérios de aceite", "criterios de aceite", "acceptance criteria"))
    risks = _extract_bulleted(sections, ("riscos", "risks"))

    spec_path_abs = Path(result.spec_path)
    try:
        spec_relpath = str(spec_path_abs.relative_to(base))
    except ValueError:
        spec_relpath = result.spec_path

    in_scope = _compute_in_scope({**spec_data, "relpath": spec_relpath}, profile, base)

    compile_targets = " ".join(
        p for p in in_scope if p.endswith(".py")
    ) or "app.py"

    devforge_dir = get_devforge_dir(base)
    evidence_paths = [
        {
            "name": ev,
            "paths": check_evidence(ev, base, devforge_dir, spec_id=result.spec_id).expected_paths,
        }
        for ev in result.required_evidence
    ]

    tmpl = env.get_template("implementation-brief.md.j2")
    brief_path.write_text(
        tmpl.render(
            spec_id=result.spec_id,
            spec_title=result.spec_title,
            spec_relpath=spec_relpath,
            plan_id=result.plan_id,
            objective=objective,
            acceptance_criteria=acceptance_criteria,
            risks=risks,
            tasks=result.tasks,
            in_scope=in_scope,
            compile_targets=compile_targets,
            required_evidence=result.required_evidence,
            evidence_paths=evidence_paths,
            project_profile=profile,
        ),
        encoding="utf-8",
    )
    return brief_path


def generate_plan(spec_path: Path, base: Path) -> PlanResult:
    spec_data = parse_spec(spec_path)
    spec_id = spec_data["spec_id"]

    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    profile: dict = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))

    classification = classify_plan(spec_data, profile)
    prcp_level = compute_effective_prcp(profile, spec_data)
    tasks = generate_tasks(spec_id, spec_data, profile)
    policy_decision, required_evidence = determine_policy(profile, spec_data)
    allowed_uses = compute_allowed_uses(spec_data, profile)
    blocked_uses = compute_blocked_uses(spec_data, profile)

    result = PlanResult(
        spec_id=spec_id,
        plan_id=f"PLAN-{spec_id}",
        context_pack_id=f"CTX-{spec_id}",
        spec_path=str(spec_path),
        spec_title=spec_data["title"],
        domain=classification.domain,
        prcp_level=prcp_level,
        plan_confidence=classification.plan_confidence,
        plan_recommendation=classification.plan_recommendation,
        policy_decision=policy_decision,
        tasks=tasks,
        allowed_uses=allowed_uses,
        blocked_uses=blocked_uses,
        required_evidence=required_evidence,
        project_profile=profile,
    )
    # Attach the parsed SPEC and scan profile so _write_implementation_brief
    # can pull objective/acceptance/risks without re-parsing.
    result._spec_data = spec_data  # type: ignore[attr-defined]
    result._profile = profile  # type: ignore[attr-defined]
    result.generated_files = _write_plan_files(base, result)
    return result
