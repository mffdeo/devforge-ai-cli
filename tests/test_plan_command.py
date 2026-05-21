import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.planner import (
    classify_spec_domain,
    compute_effective_prcp,
    determine_policy,
    generate_tasks,
    parse_spec,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

SPEC_AUTH_CONTENT = """\
# SPEC-AUTH-001 — Login e RBAC básico

## Objetivo

Permitir login com e-mail e senha.

## Critérios de aceite

- AC-001: Usuário consegue fazer login.
- AC-002: Usuário não autenticado não acessa rotas protegidas.

## Riscos

- Toca autenticação.
- Toca permissões.
"""

SPEC_GENERIC_CONTENT = """\
# SPEC-DASH-001 — Dashboard de métricas

## Objetivo

Exibir métricas gerais do sistema.

## Critérios de aceite

- AC-001: Dashboard carrega em menos de 2s.
"""


SPEC_PRIORITY_CONTENT = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas

## Objetivo

Adicionar prioridade às tarefas de um Todo App Flask/SQLite.

## Critérios de aceite

- AC-001: Toda tarefa tem um campo prioridade.
- AC-002: A prioridade padrão é Média.
- AC-003: A lista exibe a prioridade junto da tarefa.

## Riscos

- Toca o schema SQLite (CREATE TABLE / ALTER TABLE).
- Migração leve do banco local.
"""


def _init_and_scan(tmp_path: Path) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)


def _make_spec(tmp_path: Path, content: str = SPEC_AUTH_CONTENT, name: str = "SPEC-AUTH-001.md") -> Path:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(exist_ok=True)
    spec = specs_dir / name
    spec.write_text(content)
    return spec


# ── require init ──────────────────────────────────────────────────────────────

def test_plan_requires_init(tmp_path):
    spec = _make_spec(tmp_path)
    with pytest.raises(SystemExit):
        run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)


# ── require scan ──────────────────────────────────────────────────────────────

def test_plan_requires_scan(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    spec = _make_spec(tmp_path)
    with pytest.raises(SystemExit):
        run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)


# ── require spec file ─────────────────────────────────────────────────────────

def test_plan_fails_if_spec_missing(tmp_path):
    _init_and_scan(tmp_path)
    with pytest.raises(SystemExit):
        run_plan(spec=str(tmp_path / "specs" / "MISSING.md"), plain=True, output_json=False, cwd=tmp_path)


# ── spec parsing ──────────────────────────────────────────────────────────────

def test_plan_reads_spec_markdown(tmp_path):
    spec = _make_spec(tmp_path)
    data = parse_spec(spec)
    assert data["spec_id"] == "SPEC-AUTH-001"
    assert "Login" in data["title"] or "RBAC" in data["title"]
    assert "objetivo" in data["sections"] or "critérios de aceite" in data["sections"]


def test_plan_infers_spec_id_from_filename(tmp_path):
    spec = _make_spec(tmp_path, content="# Dashboard", name="SPEC-DASH-999.md")
    data = parse_spec(spec)
    assert data["spec_id"] == "SPEC-DASH-999"


# ── file generation ───────────────────────────────────────────────────────────

def test_plan_generates_plan_pack(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    assert (tmp_path / ".devforge" / "plans" / "PLAN-SPEC-AUTH-001.md").exists()


def test_plan_generates_context_pack(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    ctx = tmp_path / ".devforge" / "context" / "context-pack.md"
    assert ctx.exists()
    content = ctx.read_text()
    assert "Allowed Uses" in content
    assert "Blocked Uses" in content
    assert "Required Evidence" in content


def test_plan_generates_policy_decision(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    pol = tmp_path / ".devforge" / "policy" / "POLICY-DECISION-SPEC-AUTH-001.json"
    assert pol.exists()
    data = json.loads(pol.read_text())
    assert "decision" in data
    assert "required_evidence" in data


# ── audit trail ───────────────────────────────────────────────────────────────

def test_plan_records_audit_event(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    plan_events = [e for e in events if e["event"] == "plan.generated"]
    assert len(plan_events) == 1
    e = plan_events[0]
    assert e["spec_id"] == "SPEC-AUTH-001"
    assert "policy_decision" in e
    assert "required_evidence" in e


# ── policy decision ───────────────────────────────────────────────────────────

def test_plan_require_approval_when_hardened(tmp_path):
    profile = {
        "prcp": {"task_elevation": "Hardened", "baseline_level": "Standard"},
        "signals": {"touches_auth": True, "personal_data_possible": True},
        "sensitive_areas": ["auth", "login"],
    }
    spec_data = {"content": "# SPEC-001\n## Objetivo\nLogin simples.", "sections": {}}
    decision, required = determine_policy(profile, spec_data)
    assert decision == "REQUIRE_APPROVAL"


def test_plan_required_evidence_when_hardened(tmp_path):
    profile = {
        "prcp": {"task_elevation": "Hardened"},
        "signals": {"touches_auth": True},
        "sensitive_areas": ["auth"],
    }
    spec_data = {"content": "auth login password", "sections": {}}
    _, required = determine_policy(profile, spec_data)
    assert "test_report" in required
    assert "human_review" in required
    assert "rollback_plan" in required
    assert "audit_log" in required


def test_plan_allow_when_no_sensitive(tmp_path):
    profile = {
        "prcp": {"task_elevation": "Standard", "baseline_level": "Standard"},
        "signals": {},
        "sensitive_areas": [],
    }
    spec_data = {"content": "# Dashboard\n## Objetivo\nMétricas gerais.", "sections": {}}
    decision, required = determine_policy(profile, spec_data)
    assert decision in ("ALLOW", "REQUIRE_APPROVAL")  # ALLOW for truly clean specs


# ── task generation ───────────────────────────────────────────────────────────

def test_plan_generates_auth_tasks_for_auth_spec(tmp_path):
    profile = {"sensitive_areas": ["auth", "login"], "signals": {}}
    spec_data = {"content": "auth login password", "sections": {}}
    tasks = generate_tasks("SPEC-AUTH-001", spec_data, profile)
    assert len(tasks) == 5
    assert all("id" in t and "description" in t for t in tasks)
    assert any("auth" in t["description"].lower() or "permiss" in t["description"].lower() for t in tasks)


# ── SPEC-PRIORITY: domain classification, tasks, PRCP, policy ────────────────

def test_classify_priority_spec_is_task_priority_with_db(tmp_path):
    spec_data = {"content": SPEC_PRIORITY_CONTENT, "sections": {}}
    domain, touches_database = classify_spec_domain(spec_data, profile={})
    assert domain == "task_priority"
    assert touches_database is True


def test_plan_priority_spec_does_not_generate_auth_tasks(tmp_path):
    profile = {"sensitive_areas": ["database", "sqlite"], "signals": {"has_database": True}}
    spec_data = {"content": SPEC_PRIORITY_CONTENT, "sections": {}}
    tasks = generate_tasks("SPEC-PRIORITY-001", spec_data, profile)
    joined = " ".join(t["description"].lower() for t in tasks)
    assert "autenticação" not in joined
    assert "permissões e papéis" not in joined
    assert "auth" not in joined


def test_plan_priority_spec_generates_priority_tasks(tmp_path):
    profile = {"sensitive_areas": ["database", "sqlite"], "signals": {"has_database": True}}
    spec_data = {"content": SPEC_PRIORITY_CONTENT, "sections": {}}
    tasks = generate_tasks("SPEC-PRIORITY-001", spec_data, profile)
    ids = [t["id"] for t in tasks]
    joined = " ".join(t["description"].lower() for t in tasks)
    assert ids[0] == "TASK-PRIORITY-001"
    assert any("prioridade" in t["description"].lower() for t in tasks)
    assert any("tarefa" in t["description"].lower() for t in tasks)
    assert "schema sqlite" in joined or "schema" in joined


def test_plan_priority_spec_applies_hardened_prcp(tmp_path):
    profile = {"prcp": {"task_elevation": "Standard"}, "signals": {}, "sensitive_areas": []}
    spec_data = {"content": SPEC_PRIORITY_CONTENT, "sections": {}}
    effective = compute_effective_prcp(profile, spec_data)
    assert effective == "Hardened"


def test_plan_priority_spec_requires_approval_and_human_review(tmp_path):
    profile = {"prcp": {"task_elevation": "Standard"}, "signals": {}, "sensitive_areas": []}
    spec_data = {"content": SPEC_PRIORITY_CONTENT, "sections": {}}
    decision, required = determine_policy(profile, spec_data)
    assert decision == "REQUIRE_APPROVAL"
    assert "test_report" in required
    assert "human_review" in required
    assert "rollback_plan" in required
    assert "audit_log" in required


def test_plan_priority_spec_ignores_auth_in_profile_sensitive_areas(tmp_path):
    """Regression: a project may have auth files detected by scan
    (user.py, login.py, permissions/), so sensitive_areas inherits
    'auth'. A SPEC clearly about task priority must NOT inherit that
    domain. The SPEC headline owns the classification."""
    profile = {
        "sensitive_areas": ["auth", "login", "permissions", "user", "database", "sqlite"],
        "signals": {"has_database": True, "touches_auth": True},
    }
    spec_data = {
        "spec_id": "SPEC-PRIORITY-001",
        "title": "Prioridade em tarefas",
        "content": SPEC_PRIORITY_CONTENT,
        "sections": {"objetivo": "Adicionar prioridade às tarefas de um Todo App Flask/SQLite."},
    }
    domain, _ = classify_spec_domain(spec_data, profile)
    assert domain == "task_priority"

    tasks = generate_tasks("SPEC-PRIORITY-001", spec_data, profile)
    joined = " ".join(t["description"].lower() for t in tasks)
    for forbidden in ("autenticação", "permissões", "papéis", "auth"):
        assert forbidden not in joined, f"task de auth vazou: {forbidden!r}"


def test_plan_priority_spec_ignores_incidental_auth_word_in_body(tmp_path):
    """Regression: body mentions 'sessão' incidentally (e.g. 'a ordem
    persiste durante a sessão'). The headline still wins."""
    content = SPEC_PRIORITY_CONTENT + "\n## Notas\n\nA ordem de prioridade persiste durante a sessão do usuário.\n"
    spec_data = {
        "spec_id": "SPEC-PRIORITY-001",
        "title": "Prioridade em tarefas",
        "content": content,
        "sections": {"objetivo": "Adicionar prioridade às tarefas."},
    }
    domain, _ = classify_spec_domain(spec_data, profile={})
    assert domain == "task_priority"


def test_plan_priority_spec_end_to_end_with_auth_profile(tmp_path):
    """Full pipeline regression of the bug the user hit: a Flask Todo
    project where scan also flagged auth (user.py) must still produce
    the task_priority template for SPEC-PRIORITY-001."""
    _init_and_scan(tmp_path)
    # Pollute the scan profile to simulate auth detection in the real project.
    profile_path = tmp_path / ".devforge" / "prcp" / "project-profile.json"
    profile = json.loads(profile_path.read_text())
    profile["sensitive_areas"] = sorted(set(profile.get("sensitive_areas", [])) | {"auth", "login", "permissions"})
    profile["signals"]["touches_auth"] = True
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))

    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    plan_md = (tmp_path / ".devforge" / "plans" / "PLAN-SPEC-PRIORITY-001.md").read_text()
    plan_lower = plan_md.lower()

    for forbidden in ("mapear fluxo de autenticação", "permissões e papéis", "testes mínimos de auth"):
        assert forbidden not in plan_lower, f"task de auth vazou no PLAN.md: {forbidden!r}"

    for required in (
        "mapear modelo atual de tarefas",
        "adicionar campo de prioridade ao schema sqlite",
        "atualizar formulário de criação de tarefa",
        "exibir prioridade na lista de tarefas",
        'definir valor padrão "média"',
        "preparar testes manuais e rollback plan",
    ):
        assert required in plan_lower, f"task de priority faltando no PLAN.md: {required!r}"


def test_plan_priority_spec_end_to_end(tmp_path):
    """Run the actual command and inspect generated artifacts."""
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    plan_md = (tmp_path / ".devforge" / "plans" / "PLAN-SPEC-PRIORITY-001.md").read_text()
    assert "Hardened" in plan_md
    assert "autenticação" not in plan_md.lower()
    assert "prioridade" in plan_md.lower()

    pol = json.loads(
        (tmp_path / ".devforge" / "policy" / "POLICY-DECISION-SPEC-PRIORITY-001.json").read_text()
    )
    assert pol["decision"] == "REQUIRE_APPROVAL"
    assert pol["prcp_level"] == "Hardened"
    assert "human_review" in pol["required_evidence"]
    assert "rollback_plan" in pol["required_evidence"]

    ctx = (tmp_path / ".devforge" / "context" / "context-pack.md").read_text()
    assert "schema local" in ctx
    # blocked uses still bloqueando segredos/tokens/senhas/dados pessoais
    for blocked in ("segredos reais", "tokens de produção", "senhas", "dados pessoais brutos"):
        assert blocked in ctx


# ── output modes ──────────────────────────────────────────────────────────────

def test_plan_json_output(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    capsys.readouterr()
    run_plan(spec=str(spec), plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "spec_id" in data
    assert "plan_id" in data
    assert "context_pack_id" in data
    assert "policy_decision" in data
    assert "prcp_level" in data
    assert "tasks" in data
    assert "allowed_uses" in data
    assert "blocked_uses" in data
    assert "required_evidence" in data
    assert "generated_files" in data
    assert "next_step" in data


def test_plan_plain_output(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    capsys.readouterr()
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "[DevForge]" in out
    assert "SPEC" in out
    assert "PRCP" in out


# ── idempotency ───────────────────────────────────────────────────────────────

def test_plan_is_idempotent(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    plan_file = tmp_path / ".devforge" / "plans" / "PLAN-SPEC-AUTH-001.md"
    assert plan_file.exists()
