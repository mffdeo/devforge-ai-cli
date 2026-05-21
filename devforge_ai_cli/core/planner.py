import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from devforge_ai_cli.core.agent_instructions import render_agent_instructions
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

_AUTH_KWS = {"auth", "login", "logout", "jwt", "token", "password", "secret", "rbac", "role", "roles", "permission", "permissions"}
_AUTH_EXTRA_TERMS = {"senha", "sessão", "session"}
_PAYMENT_KWS = {"payment", "billing", "pagamento", "cobrança"}
_DB_KWS = {"migration", "database", "schema", "migrate"}
_DB_EXTRA_TERMS = {"banco", "sqlite", "tabela", "create table", "alter table", "drop table"}
_TASK_PRIORITY_TERMS = {"prioridade", "priority", "tarefa", "task", "todo"}

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
    SPEC text or scan profile show database/schema work.
    """
    profile = profile or {}
    content = _spec_lower(spec_data)
    sensitive = set(profile.get("sensitive_areas", []))
    signals = profile.get("signals", {})

    spec_id = (spec_data.get("spec_id") or "").lower()
    title = (spec_data.get("title") or "").lower()
    sections = spec_data.get("sections") or {}
    objective = (sections.get("objetivo") or sections.get("objective") or "").lower()
    headline = f"{spec_id} {title} {objective}".strip()

    touches_database = (
        _hits(content, _DB_KWS | _DB_EXTRA_TERMS)
        or bool(_DB_KWS & sensitive)
        or bool({"database", "schema", "sqlite"} & sensitive)
        or bool(signals.get("has_database", False))
    )

    if headline:
        if _hits(headline, _TASK_PRIORITY_TERMS):
            return "task_priority", touches_database
        if _hits(headline, _AUTH_KWS | _AUTH_EXTRA_TERMS):
            return "auth", touches_database
        if _hits(headline, _PAYMENT_KWS):
            return "payment", touches_database

    if _hits(content, _AUTH_KWS | _AUTH_EXTRA_TERMS) or bool(_AUTH_KWS & sensitive):
        return "auth", touches_database
    if _hits(content, _PAYMENT_KWS) or bool(_PAYMENT_KWS & sensitive):
        return "payment", touches_database
    if _hits(content, _TASK_PRIORITY_TERMS):
        return "task_priority", touches_database
    return "generic_feature", touches_database


def compute_effective_prcp(profile: dict, spec_data: dict) -> str:
    """Return the PRCP the plan should apply, which can elevate the scan baseline.

    Today the only elevation rule at plan time is: if the SPEC itself
    declares database/schema work, the plan applies Hardened regardless
    of the scan baseline. Auth/personal-data already elevate at scan time.
    """
    baseline = profile.get("prcp", {}).get("task_elevation", "Standard")
    _, touches_database = classify_spec_domain(spec_data, profile)
    if touches_database:
        return "Hardened"
    return baseline


def compute_allowed_uses(spec_data: dict, profile: dict | None = None) -> list[str]:
    """Allowed uses for the Context Pack, expanded when the SPEC needs them."""
    uses = list(ALLOWED_USES)
    _, touches_database = classify_spec_domain(spec_data, profile or {})
    if touches_database and "schema local" not in uses:
        uses.append("schema local")
    return uses


@dataclass
class PlanResult:
    spec_id: str
    plan_id: str
    context_pack_id: str
    spec_path: str
    spec_title: str
    prcp_level: str
    policy_decision: str
    tasks: list[dict]
    allowed_uses: list[str]
    blocked_uses: list[str]
    required_evidence: list[str]
    generated_files: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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

    return {
        "spec_id": spec_id,
        "title": title,
        "content": content,
        "sections": sections,
    }


def generate_tasks(spec_id: str, spec_data: dict, profile: dict) -> list[dict]:
    domain, _ = classify_spec_domain(spec_data, profile)
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
    signals = profile.get("signals", {})

    hardened = effective_prcp == "Hardened"
    touches_auth = signals.get("touches_auth", False) or domain == "auth"
    personal_data = signals.get("personal_data_possible", False)
    spec_has_risk = domain in {"auth", "payment"}

    if hardened or touches_auth or personal_data or spec_has_risk or touches_database:
        decision = PolicyDecision.REQUIRE_APPROVAL
        required = ["test_report", "human_review", "rollback_plan", "audit_log"]
    else:
        decision = PolicyDecision.ALLOW
        required = ["audit_log"]

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

    return generated


def generate_plan(spec_path: Path, base: Path) -> PlanResult:
    spec_data = parse_spec(spec_path)
    spec_id = spec_data["spec_id"]

    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    profile: dict = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))

    prcp_level = compute_effective_prcp(profile, spec_data)
    tasks = generate_tasks(spec_id, spec_data, profile)
    policy_decision, required_evidence = determine_policy(profile, spec_data)
    allowed_uses = compute_allowed_uses(spec_data, profile)

    result = PlanResult(
        spec_id=spec_id,
        plan_id=f"PLAN-{spec_id}",
        context_pack_id=f"CTX-{spec_id}",
        spec_path=str(spec_path),
        spec_title=spec_data["title"],
        prcp_level=prcp_level,
        policy_decision=policy_decision,
        tasks=tasks,
        allowed_uses=allowed_uses,
        blocked_uses=BLOCKED_USES,
        required_evidence=required_evidence,
    )
    result.generated_files = _write_plan_files(base, result)
    return result
