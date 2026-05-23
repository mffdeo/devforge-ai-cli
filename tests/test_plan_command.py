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

SPEC_CALC_HISTORY_CONTENT = """\
# SPEC-HISTORICO-CALCULOS-SESSAO-001 — Histórico de cálculos da sessão

Status: Approved

## Objetivo

Adicionar histórico de cálculos da sessão na calculadora CLI.

## Escopo

- Histórico apenas em memória durante a sessão.
- Sem arquivo.
- Sem banco.
- Sem nuvem.
- Sem login/auth.
- Sem dados pessoais.

## Critérios de aceite

- O sistema registra operações válidas com expressão e resultado.
- Operações inválidas não entram no histórico.
- O usuário consegue exibir o histórico durante a sessão local.
- O histórico é perdido ao encerrar a aplicação.
"""

SPEC_GENERIC_CLI_CONTENT = """\
# SPEC-MENU-CLI-001 — Melhorar menu da CLI

Status: Approved

## Objetivo

Melhorar as mensagens do menu local da CLI.

## Critérios de aceite

- O menu mostra opções claras para o usuário local.
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


def _python_cli_profile(
    *,
    confidence: str = "high",
    profile_status: str = "approved",
    requires_agent_review: bool = False,
) -> dict:
    return {
        "project_name": "calculator",
        "project_type": "python_cli",
        "detected_stack": ["Python"],
        "architecture_summary": "Python command-line calculator.",
        "has_database": False,
        "has_auth": False,
        "personal_data_possible": False,
        "external_integrations": False,
        "production_impact": "low",
        "sensitive_areas": [],
        "signals": {
            "touches_auth": False,
            "personal_data_possible": False,
            "external_integrations": False,
            "production_impact": "low",
            "user_interaction": True,
            "has_ci": False,
            "has_tests": False,
            "has_docker": False,
            "has_database": False,
        },
        "prcp": {"baseline_level": "Minimal", "task_elevation": "Minimal"},
        "confidence": confidence,
        "profile_status": profile_status,
        "requires_agent_review": requires_agent_review,
        "requires_user_approval": profile_status != "approved",
        "approved_by_user": profile_status == "approved",
        "assumptions": ["Python CLI calculator."],
        "gray_areas": [],
        "source": "user_confirmed" if profile_status == "approved" else "deterministic",
    }


def _write_project_profile(tmp_path: Path, profile: dict) -> None:
    prcp_dir = tmp_path / ".devforge" / "prcp"
    prcp_dir.mkdir(parents=True, exist_ok=True)
    (prcp_dir / "project-profile.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False)
    )


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
    assert "Project Profile" in content
    assert "status: draft" in content
    assert "source: deterministic" in content
    assert "confidence:" in content


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


def test_plan_generic_spec_does_not_inherit_auth_template_from_profile(tmp_path):
    profile = {
        "project_type": "python_web",
        "has_auth": True,
        "sensitive_areas": ["auth", "login", "permissions"],
        "signals": {"touches_auth": True},
        "prcp": {"task_elevation": "Standard"},
    }
    spec_data = {
        "spec_id": "SPEC-DASH-001",
        "title": "Dashboard de métricas",
        "content": SPEC_GENERIC_CONTENT,
        "sections": {"objetivo": "Exibir métricas gerais do sistema."},
    }
    domain, _ = classify_spec_domain(spec_data, profile)
    assert domain == "generic_feature"

    tasks = generate_tasks("SPEC-DASH-001", spec_data, profile)
    joined = " ".join(t["description"].lower() for t in tasks)
    for forbidden in ("autenticação", "permissões", "papéis", "auth"):
        assert forbidden not in joined


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


# ── Python CLI session history: avoid auth/db bias ──────────────────────────

def test_plan_python_cli_session_history_is_not_auth_domain(tmp_path):
    profile = _python_cli_profile()
    spec_data = {
        "spec_id": "SPEC-HISTORICO-CALCULOS-SESSAO-001",
        "title": "Histórico de cálculos da sessão",
        "content": SPEC_CALC_HISTORY_CONTENT,
        "sections": {"objetivo": "Adicionar histórico de cálculos da sessão na calculadora CLI."},
    }
    domain, touches_database = classify_spec_domain(spec_data, profile)
    assert domain == "cli_session_history"
    assert touches_database is False


def test_plan_session_word_alone_does_not_classify_auth(tmp_path):
    profile = _python_cli_profile()
    spec_data = {
        "spec_id": "SPEC-SESSAO-LOCAL-001",
        "title": "Sessão local",
        "content": "# SPEC-SESSAO-LOCAL-001\n\nDados durante a sessão de uso local.",
        "sections": {"objetivo": "Manter dados durante a sessão local."},
    }
    domain, touches_database = classify_spec_domain(spec_data, profile)
    assert domain == "generic_cli_feature"
    assert touches_database is False


def test_plan_session_history_in_memory_session_does_not_classify_auth(tmp_path):
    profile = _python_cli_profile()
    spec_data = {
        "spec_id": "SPEC-SESSION-HISTORY-001",
        "title": "Session history",
        "content": "# SPEC-SESSION-HISTORY-001\n\nKeep in-memory session history for CLI usage.",
        "sections": {"objective": "Keep in-memory session history."},
    }
    domain, touches_database = classify_spec_domain(spec_data, profile)
    assert domain == "cli_session_history"
    assert touches_database is False


def test_plan_negated_database_scope_does_not_touch_database(tmp_path):
    profile = _python_cli_profile()
    content = SPEC_CALC_HISTORY_CONTENT + "\n## Fora de escopo\n\n- Sem banco/schema/migração.\n"
    spec_data = {
        "spec_id": "SPEC-HISTORICO-CALCULOS-SESSAO-001",
        "title": "Histórico de cálculos da sessão",
        "content": content,
        "sections": {"objetivo": "Adicionar histórico de cálculos da sessão na calculadora CLI."},
    }
    domain, touches_database = classify_spec_domain(spec_data, profile)
    assert domain == "cli_session_history"
    assert touches_database is False


def test_plan_python_cli_history_effective_prcp_is_not_hardened(tmp_path):
    profile = _python_cli_profile()
    spec_data = {
        "spec_id": "SPEC-HISTORICO-CALCULOS-SESSAO-001",
        "title": "Histórico de cálculos da sessão",
        "content": SPEC_CALC_HISTORY_CONTENT,
        "sections": {"objetivo": "Adicionar histórico de cálculos da sessão na calculadora CLI."},
    }
    assert compute_effective_prcp(profile, spec_data) in {"Minimal", "Standard"}
    assert compute_effective_prcp(profile, spec_data) != "Hardened"


def test_plan_python_cli_history_ignores_stale_hardened_profile_when_profile_is_low_risk(tmp_path):
    profile = _python_cli_profile()
    profile["prcp"]["task_elevation"] = "Hardened"
    profile["prcp"]["baseline_level"] = "Minimal"
    spec_data = {
        "spec_id": "SPEC-HISTORICO-CALCULOS-SESSAO-001",
        "title": "Histórico de cálculos da sessão",
        "content": SPEC_CALC_HISTORY_CONTENT,
        "sections": {"objetivo": "Adicionar histórico de cálculos da sessão na calculadora CLI."},
    }
    assert compute_effective_prcp(profile, spec_data) == "Minimal"


def test_plan_python_cli_history_generates_no_auth_db_cloud_tasks(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(tmp_path, _python_cli_profile())
    spec = _make_spec(
        tmp_path,
        content=SPEC_CALC_HISTORY_CONTENT,
        name="SPEC-HISTORICO-CALCULOS-SESSAO-001.md",
    )

    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    plan_md = (
        tmp_path
        / ".devforge"
        / "plans"
        / "PLAN-SPEC-HISTORICO-CALCULOS-SESSAO-001.md"
    ).read_text()
    plan_lower = plan_md.lower()

    for required in (
        "mapear fluxo atual da calculadora cli",
        "adicionar histórico em memória da sessão",
        "registrar operações válidas com expressão e resultado",
        "exibir histórico por opção do menu ou antes de sair",
        "garantir que operações inválidas não entrem no histórico",
        "preparar teste manual da calculadora cli",
    ):
        assert required in plan_lower

    for forbidden in (
        "mapear fluxo de autenticação",
        "permissões",
        "papéis",
        "login",
        "schema sqlite",
        "sqlite",
        "cloud",
    ):
        assert forbidden not in plan_lower


def test_plan_python_cli_history_policy_is_allow_without_human_review_or_rollback(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(tmp_path, _python_cli_profile())
    spec = _make_spec(
        tmp_path,
        content=SPEC_CALC_HISTORY_CONTENT,
        name="SPEC-HISTORICO-CALCULOS-SESSAO-001.md",
    )

    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    policy = json.loads(
        (
            tmp_path
            / ".devforge"
            / "policy"
            / "POLICY-DECISION-SPEC-HISTORICO-CALCULOS-SESSAO-001.json"
        ).read_text()
    )
    assert policy["decision"] == "ALLOW"
    assert policy["prcp_level"] in {"Minimal", "Standard"}
    assert policy["required_evidence"] == ["test_report", "audit_log"]
    assert "human_review" not in policy["required_evidence"]
    assert "rollback_plan" not in policy["required_evidence"]

    context = (tmp_path / ".devforge" / "context" / "context-pack.md").read_text()
    required_context = context.split("## Required Evidence", maxsplit=1)[1]
    assert "test_report" in required_context
    assert "audit_log" in required_context
    assert "human_review" not in required_context
    assert "rollback_plan" not in required_context


def test_plan_python_cli_history_plain_output_shows_light_policy(tmp_path, capsys):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(tmp_path, _python_cli_profile())
    spec = _make_spec(
        tmp_path,
        content=SPEC_CALC_HISTORY_CONTENT,
        name="SPEC-HISTORICO-CALCULOS-SESSAO-001.md",
    )

    capsys.readouterr()
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out

    assert "Domain: cli_session_history" in out
    assert "PRCP: Hardened" not in out
    assert "Política: ALLOW" in out
    assert "Evidências: test_report, audit_log" in out
    assert "human_review" not in out
    assert "rollback_plan" not in out


def test_plan_python_cli_history_handles_string_false_profile_values(tmp_path):
    profile = _python_cli_profile()
    profile["has_database"] = "false"
    profile["has_auth"] = "false"
    profile["personal_data_possible"] = "false"
    profile["external_integrations"] = "false"
    profile["signals"]["has_database"] = "false"
    profile["signals"]["touches_auth"] = "false"
    profile["signals"]["personal_data_possible"] = "false"
    profile["signals"]["external_integrations"] = "false"
    spec_data = {
        "spec_id": "SPEC-HISTORICO-CALCULOS-SESSAO-001",
        "title": "Histórico de cálculos da sessão",
        "content": SPEC_CALC_HISTORY_CONTENT,
        "sections": {"objetivo": "Adicionar histórico de cálculos da sessão na calculadora CLI."},
    }

    assert compute_effective_prcp(profile, spec_data) in {"Minimal", "Standard"}
    decision, required = determine_policy(profile, spec_data)
    assert decision == "ALLOW"
    assert required == ["test_report", "audit_log"]


def test_plan_python_cli_history_context_blocks_out_of_scope_uses(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(tmp_path, _python_cli_profile())
    spec = _make_spec(
        tmp_path,
        content=SPEC_CALC_HISTORY_CONTENT,
        name="SPEC-HISTORICO-CALCULOS-SESSAO-001.md",
    )

    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    context = (tmp_path / ".devforge" / "context" / "context-pack.md").read_text()
    assert "calculator.py" in context
    assert "fluxo CLI local" in context
    assert "histórico em memória" in context
    assert "testes manuais" in context
    assert "py_compile" in context
    for blocked in (
        "login/auth",
        "banco",
        "cloud",
        "persistência em arquivo quando fora de escopo",
        "dados pessoais",
        "segredos/tokens",
        "integração externa",
    ):
        assert blocked in context


def test_implementation_brief_keeps_python_cli_history_scope(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(tmp_path, _python_cli_profile())
    spec = _make_spec(
        tmp_path,
        content=SPEC_CALC_HISTORY_CONTENT,
        name="SPEC-HISTORICO-CALCULOS-SESSAO-001.md",
    )

    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)

    brief = (
        tmp_path
        / ".devforge"
        / "context"
        / "implementation-brief-SPEC-HISTORICO-CALCULOS-SESSAO-001.md"
    ).read_text()
    assert "histórico de cálculos da sessão" in brief.lower()
    assert "Adicionar histórico em memória da sessão" in brief
    assert "não adicionar login" in brief
    assert "não adicionar autenticação" in brief
    assert "não adicionar cloud" in brief
    assert "não adicionar integração externa" in brief
    assert "não adicionar banco se a SPEC não pedir" in brief
    assert "não persistir dados em arquivo se estiver fora de escopo" in brief
    assert "não transformar sessão local em sessão autenticada" in brief


def test_plan_requires_approval_for_secret_feature(tmp_path):
    profile = _python_cli_profile()
    spec_data = {
        "spec_id": "SPEC-SECRET-001",
        "title": "Configurar token de API",
        "content": "# SPEC-SECRET-001\n\n## Objetivo\n\nConfigurar token de API externa.",
        "sections": {"objetivo": "Configurar token de API externa."},
    }
    decision, required = determine_policy(profile, spec_data)
    assert decision == "REQUIRE_APPROVAL"
    assert "human_review" in required
    assert "rollback_plan" in required


def test_plan_low_confidence_ambiguous_cli_spec_uses_generic_plan(tmp_path, capsys):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print('calculator')\n")
    _write_project_profile(
        tmp_path,
        _python_cli_profile(
            confidence="low",
            profile_status="draft",
            requires_agent_review=True,
        ),
    )
    spec = _make_spec(
        tmp_path,
        content=SPEC_GENERIC_CLI_CONTENT,
        name="SPEC-MENU-CLI-001.md",
    )

    capsys.readouterr()
    run_plan(spec=str(spec), plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)

    assert data["domain"] == "generic_cli_feature"
    assert data["plan_confidence"] == "low"
    assert "devforge scan --agent codex" in data["plan_recommendation"]
    task_text = " ".join(task["description"].lower() for task in data["tasks"])
    assert "mapear fluxo cli atual" in task_text
    assert "implementar comportamento solicitado na spec" in task_text
    assert "autenticação" not in task_text
    assert "schema" not in task_text


def test_plan_generates_implementation_brief(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    brief = tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md"
    assert brief.exists()


def test_implementation_brief_contains_spec_id(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    brief = (tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md").read_text()
    assert "SPEC-PRIORITY-001" in brief


def test_implementation_brief_references_plan_context_agent_policy(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    brief = (tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md").read_text()
    assert ".devforge/plans/PLAN-SPEC-PRIORITY-001.md" in brief
    assert ".devforge/context/context-pack.md" in brief
    assert ".devforge/context/agent-instructions.md" in brief
    assert ".devforge/policy/POLICY-DECISION-SPEC-PRIORITY-001.json" in brief


def test_implementation_brief_contains_user_prompt(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    brief = (tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md").read_text()
    assert "Implemente a feature usando o briefing em" in brief
    assert "implementation-brief-SPEC-PRIORITY-001.md" in brief


def test_implementation_brief_includes_objective_acceptance_and_risks(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    brief = (tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md").read_text()
    assert "Adicionar prioridade às tarefas" in brief
    assert "Toda tarefa tem um campo prioridade" in brief
    assert "Toca o schema SQLite" in brief


def test_plan_json_exposes_implementation_brief_path(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    capsys.readouterr()
    run_plan(spec=str(spec), plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "implementation_brief_path" in data
    assert data["implementation_brief_path"].endswith("implementation-brief-SPEC-PRIORITY-001.md")
    assert "agent_prompt" in data
    assert "implementation-brief-SPEC-PRIORITY-001.md" in data["agent_prompt"]


def test_plan_audit_event_includes_implementation_brief_path(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path, content=SPEC_PRIORITY_CONTENT, name="SPEC-PRIORITY-001.md")
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    plan_events = [e for e in events if e["event"] == "plan.generated"]
    assert plan_events
    assert plan_events[-1]["implementation_brief_path"].endswith(
        "implementation-brief-SPEC-PRIORITY-001.md"
    )


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


def test_plan_with_draft_spec_warns_but_continues(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(
        tmp_path,
        content="# SPEC-DRAFT-001 — Draft\n\nStatus: Draft\n\n## Objetivo\n\nValidar warning.",
        name="SPEC-DRAFT-001.md",
    )
    capsys.readouterr()
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "SPEC status is Draft. Consider resolving gray areas and approving it before planning." in out
    assert (tmp_path / ".devforge" / "plans" / "PLAN-SPEC-DRAFT-001.md").exists()


def test_plan_warns_when_project_profile_not_approved(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(
        tmp_path,
        content="# SPEC-APPROVED-001 — Approved\n\nStatus: Approved\n\n## Objetivo\n\nValidar profile warning.",
        name="SPEC-APPROVED-001.md",
    )
    capsys.readouterr()
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "Project Profile is preliminary and not approved." in out
    assert "devforge profile approve" in out


def test_plan_with_approved_spec_does_not_warn(tmp_path, capsys):
    _init_and_scan(tmp_path)
    spec = _make_spec(
        tmp_path,
        content="# SPEC-APPROVED-001 — Approved\n\nStatus: Approved\n\n## Objetivo\n\nValidar sem warning.",
        name="SPEC-APPROVED-001.md",
    )
    capsys.readouterr()
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "SPEC status is Draft" not in out
    assert (tmp_path / ".devforge" / "plans" / "PLAN-SPEC-APPROVED-001.md").exists()


# ── idempotency ───────────────────────────────────────────────────────────────

def test_plan_is_idempotent(tmp_path):
    _init_and_scan(tmp_path)
    spec = _make_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    plan_file = tmp_path / ".devforge" / "plans" / "PLAN-SPEC-AUTH-001.md"
    assert plan_file.exists()
