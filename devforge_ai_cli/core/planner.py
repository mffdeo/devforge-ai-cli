import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
_PAYMENT_KWS = {"payment", "billing", "pagamento", "cobrança"}
_DB_KWS = {"migration", "database", "schema", "migrate"}

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
    "generic": [
        ("Revisar escopo e critérios de aceite", "review"),
        ("Mapear dependências e impacto", "arch"),
        ("Definir testes mínimos", "test"),
        ("Preparar rollback plan", "rollback"),
        ("Solicitar revisão humana", "review"),
    ],
}


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
    content = spec_data["content"].lower()
    sensitive = set(profile.get("sensitive_areas", []))
    signals = profile.get("signals", {})

    is_auth = bool(_AUTH_KWS & sensitive) or any(k in content for k in _AUTH_KWS)
    is_payment = bool(_PAYMENT_KWS & sensitive) or any(k in content for k in _PAYMENT_KWS)
    is_db = bool(_DB_KWS & sensitive) or signals.get("has_database", False)

    if is_auth:
        key = "auth"
    elif is_payment:
        key = "payment"
    elif is_db:
        key = "database"
    else:
        key = "generic"

    prefix = _task_prefix(spec_id)
    templates = _TASK_TEMPLATES[key]

    return [
        {"id": f"TASK-{prefix}-{i:03d}", "description": desc, "type": typ}
        for i, (desc, typ) in enumerate(templates, start=1)
    ]


def determine_policy(profile: dict, spec_data: dict) -> tuple[str, list[str]]:
    signals = profile.get("signals", {})
    prcp = profile.get("prcp", {})
    task_elevation = prcp.get("task_elevation", "Standard")
    content = spec_data["content"].lower()

    hardened = task_elevation == "Hardened"
    touches_auth = signals.get("touches_auth", False)
    personal_data = signals.get("personal_data_possible", False)
    has_db = signals.get("has_database", False)

    # also check spec content for explicit risk keywords
    spec_has_risk = any(k in content for k in _AUTH_KWS | _PAYMENT_KWS)

    if hardened or touches_auth or personal_data or spec_has_risk:
        decision = PolicyDecision.REQUIRE_APPROVAL
        required = ["test_report", "human_review", "rollback_plan", "audit_log"]
    elif has_db:
        decision = PolicyDecision.REQUIRE_APPROVAL
        required = ["test_report", "rollback_plan", "audit_log"]
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

    return generated


def generate_plan(spec_path: Path, base: Path) -> PlanResult:
    spec_data = parse_spec(spec_path)
    spec_id = spec_data["spec_id"]

    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    profile: dict = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))

    prcp_level = profile.get("prcp", {}).get("task_elevation", "Standard")
    tasks = generate_tasks(spec_id, spec_data, profile)
    policy_decision, required_evidence = determine_policy(profile, spec_data)

    result = PlanResult(
        spec_id=spec_id,
        plan_id=f"PLAN-{spec_id}",
        context_pack_id=f"CTX-{spec_id}",
        spec_path=str(spec_path),
        spec_title=spec_data["title"],
        prcp_level=prcp_level,
        policy_decision=policy_decision,
        tasks=tasks,
        allowed_uses=ALLOWED_USES,
        blocked_uses=BLOCKED_USES,
        required_evidence=required_evidence,
    )
    result.generated_files = _write_plan_files(base, result)
    return result
