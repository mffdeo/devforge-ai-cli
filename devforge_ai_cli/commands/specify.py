from __future__ import annotations

import json
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.planner import parse_spec
from devforge_ai_cli.core.project import require_init

PRIORITY_ID = "SPEC-PRIORITY-001"
PRIORITY_TITLE = "Prioridade em tarefas"


def run_specify(
    idea: str | None,
    title: str | None,
    spec_id: str | None,
    agent: str,
    command: str | None,
    interactive: bool,
    approve: bool,
    yes: bool,
    dry_run: bool,
    plain: bool,
    output_json: bool,
    spec: str | None = None,
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    if spec:
        return _run_existing_spec(
            base=base,
            spec=spec,
            interactive=interactive,
            approve=approve,
            dry_run=dry_run,
            plain=plain,
            output_json=output_json,
        )

    collected_idea = idea.strip() if idea else ""
    interactive_notes: dict[str, str] = {}
    if not collected_idea and interactive:
        interactive_notes = _collect_interactive_notes()
        collected_idea = interactive_notes["feature"]

    if not collected_idea:
        result = _failure("Informe --idea, --spec ou use --interactive.")
        _emit(result, plain=plain, output_json=output_json)
        return 1

    resolved_title = (title or _infer_title(collected_idea)).strip()
    resolved_spec_id = (spec_id or _infer_spec_id(collected_idea, resolved_title)).strip().upper()
    spec_rel = f"specs/{resolved_spec_id}.md"
    brief_rel = f".devforge/context/specification-brief-{resolved_spec_id}.md"
    assumptions = _assumptions_for(collected_idea)
    gray_areas = _gray_areas_for(collected_idea)
    project_profile = _load_project_profile(base)
    clarified_decisions: list[dict[str, str]] = []

    if interactive and not dry_run:
        clarified_decisions = _collect_gray_area_decisions(gray_areas)
        if not approve:
            approve = _ask_approve_now()

    status = "Approved" if approve else "Draft"
    gray_areas_status = _gray_areas_status(status, gray_areas, clarified_decisions)
    next_steps = _next_steps(spec_rel, status, gray_areas_status)

    spec_content = _render_spec(
        spec_id=resolved_spec_id,
        title=resolved_title,
        status=status,
        idea=collected_idea,
        assumptions=assumptions,
        interactive_notes=interactive_notes,
    )
    brief_content = _render_specification_brief(
        spec_id=resolved_spec_id,
        idea=collected_idea,
        assumptions=assumptions,
        gray_areas=gray_areas,
        spec_rel=spec_rel,
        clarified_decisions=clarified_decisions,
        project_profile=project_profile,
    )
    if clarified_decisions:
        spec_content = _with_clarified_decisions(spec_content, clarified_decisions)

    normalized_agent = agent.lower().strip()
    prompt = (
        f"Refine the generated SPEC using {brief_rel}. Do not implement code. "
        "Only improve the SPEC."
    )
    command_args: list[str] = []
    if normalized_agent != "none":
        try:
            command_args = _resolve_agent_command(normalized_agent, command, prompt)
        except ValueError as exc:
            result = _failure(str(exc))
            _emit(result, plain=plain, output_json=output_json)
            return 1

    if dry_run:
        result = _result(
            spec_id=resolved_spec_id,
            spec_path=spec_rel,
            specification_brief_path=brief_rel,
            status=status,
            title=resolved_title,
            idea=collected_idea,
            assumptions=assumptions,
            gray_areas=gray_areas,
            gray_areas_status=gray_areas_status,
            clarified_decisions=clarified_decisions,
            next_steps=next_steps,
            agent=normalized_agent,
            executed=False,
            dry_run=True,
            command_args=command_args,
        )
        _attach_profile_warning(result, project_profile)
        _emit(result, plain=plain, output_json=output_json)
        return 0

    spec_path = base / spec_rel
    brief_path = base / brief_rel
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(spec_content, encoding="utf-8")
    brief_path.write_text(brief_content, encoding="utf-8")

    append_event(
        get_audit_file(base),
        {
            "event": "spec.generated",
            "spec_id": resolved_spec_id,
            "spec_path": spec_rel,
            "specification_brief_path": brief_rel,
            "status": status,
        },
    )
    if approve:
        _record_spec_approved(base, resolved_spec_id, spec_rel)

    executed, exit_code, stdout, stderr = _maybe_run_agent(
        base=base,
        spec_id=resolved_spec_id,
        specification_brief_path=brief_rel,
        agent=normalized_agent,
        command_args=command_args,
        yes=yes,
        plain=plain,
        output_json=output_json,
    )
    if exit_code != 0 and command_args and not executed:
        result = _result(
            spec_id=resolved_spec_id,
            spec_path=spec_rel,
            specification_brief_path=brief_rel,
            status=status,
            title=resolved_title,
            idea=collected_idea,
            assumptions=assumptions,
            gray_areas=gray_areas,
            gray_areas_status=gray_areas_status,
            clarified_decisions=clarified_decisions,
            next_steps=next_steps,
            agent=normalized_agent,
            executed=False,
            dry_run=False,
            command_args=command_args,
            exit_code=exit_code,
            reason=stderr,
        )
        _attach_profile_warning(result, project_profile)
        _emit(result, plain=plain, output_json=output_json)
        return exit_code

    result = _result(
        spec_id=resolved_spec_id,
        spec_path=spec_rel,
        specification_brief_path=brief_rel,
        status=status,
        title=resolved_title,
        idea=collected_idea,
        assumptions=assumptions,
        gray_areas=gray_areas,
        gray_areas_status=gray_areas_status,
        clarified_decisions=clarified_decisions,
        next_steps=next_steps,
        agent=normalized_agent,
        executed=executed,
        dry_run=False,
        command_args=command_args,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )
    _attach_profile_warning(result, project_profile)
    _emit(result, plain=plain, output_json=output_json)
    return exit_code


def _run_existing_spec(
    base: Path,
    spec: str,
    interactive: bool,
    approve: bool,
    dry_run: bool,
    plain: bool,
    output_json: bool,
) -> int:
    spec_path = _resolve_spec_path(base, spec)
    if not spec_path.exists():
        result = _failure(f"SPEC não encontrada: {spec}")
        _emit(result, plain=plain, output_json=output_json)
        return 1

    spec_data = parse_spec(spec_path)
    resolved_spec_id = spec_data["spec_id"]
    resolved_title = spec_data["title"]
    spec_rel = _relpath(spec_path, base)
    brief_rel = f".devforge/context/specification-brief-{resolved_spec_id}.md"
    brief_path = base / brief_rel
    idea = _extract_original_idea(brief_path) or spec_data["content"].splitlines()[0]
    assumptions = _extract_brief_list(brief_path, "Clarifying assumptions")
    gray_areas = _extract_brief_list(brief_path, "Gray areas") or _gray_areas_for(
        f"{resolved_spec_id} {resolved_title} {spec_data['content']}"
    )
    clarified_decisions = _extract_clarified_decisions(brief_path)
    project_profile = _load_project_profile(base)

    status = spec_data.get("status", "Draft")
    if interactive and not dry_run:
        clarified_decisions.extend(_collect_gray_area_decisions(gray_areas))
        if not approve:
            approve = _ask_approve_now()
    if approve:
        status = "Approved"

    gray_areas_status = _gray_areas_status(status, gray_areas, clarified_decisions)
    next_steps = _next_steps(spec_rel, status, gray_areas_status)

    if dry_run:
        result = _result(
            spec_id=resolved_spec_id,
            spec_path=spec_rel,
            specification_brief_path=brief_rel,
            status=status,
            title=resolved_title,
            idea=idea,
            assumptions=assumptions,
            gray_areas=gray_areas,
            gray_areas_status=gray_areas_status,
            clarified_decisions=clarified_decisions,
            next_steps=next_steps,
            agent="none",
            executed=False,
            dry_run=True,
            command_args=[],
        )
        _attach_profile_warning(result, project_profile)
        _emit(result, plain=plain, output_json=output_json)
        return 0

    spec_content = spec_path.read_text(encoding="utf-8", errors="ignore")
    spec_content = _set_spec_status(spec_content, status)
    if interactive and clarified_decisions:
        spec_content = _with_clarified_decisions(spec_content, clarified_decisions)
    spec_path.write_text(spec_content, encoding="utf-8")

    if brief_path.exists() and interactive and clarified_decisions:
        brief_content = brief_path.read_text(encoding="utf-8", errors="ignore")
        brief_path.write_text(
            _with_clarified_decisions(brief_content, clarified_decisions),
            encoding="utf-8",
        )

    if approve:
        _record_spec_approved(base, resolved_spec_id, spec_rel)

    result = _result(
        spec_id=resolved_spec_id,
        spec_path=spec_rel,
        specification_brief_path=brief_rel,
        status=status,
        title=resolved_title,
        idea=idea,
        assumptions=assumptions,
        gray_areas=gray_areas,
        gray_areas_status=gray_areas_status,
        clarified_decisions=clarified_decisions,
        next_steps=next_steps,
        agent="none",
        executed=False,
        dry_run=False,
        command_args=[],
    )
    _attach_profile_warning(result, project_profile)
    _emit(result, plain=plain, output_json=output_json)
    return 0


def _collect_interactive_notes() -> dict[str, str]:
    return {
        "feature": input("Qual feature você quer construir? ").strip(),
        "problem": input("Qual problema ela resolve? ").strip(),
        "user": input("Quem é o usuário? ").strip(),
        "success": input("O que significa sucesso? ").strip(),
        "out_of_scope": input("O que está fora de escopo? ").strip(),
        "risk": input("Há algum risco conhecido? ").strip(),
    }


def _collect_gray_area_decisions(gray_areas: list[str]) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    if not gray_areas:
        return decisions
    print("Gray areas para revisar:")
    for gray_area in gray_areas:
        answer = input(f"- {gray_area} ").strip()
        if answer:
            decisions.append({"question": gray_area, "answer": answer})
    return decisions


def _ask_approve_now() -> bool:
    answer = input("Aprovar SPEC agora? [y/N] ").strip().lower()
    return answer in {"y", "yes", "s", "sim"}


def _is_priority_idea(text: str) -> bool:
    lowered = text.lower()
    return "prioridade" in lowered and ("tarefa" in lowered or "task" in lowered)


def _infer_title(idea: str) -> str:
    if _is_priority_idea(idea):
        return PRIORITY_TITLE
    cleaned = re.sub(r"\s+", " ", idea.strip(" ."))
    cleaned = re.sub(r"^(quero|permitir|adicionar|criar|implementar)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^que\s+", "", cleaned, flags=re.I)
    words = cleaned.split()
    return " ".join(words[:6]).capitalize() if words else "Nova feature"


def _infer_spec_id(idea: str, title: str) -> str:
    if _is_priority_idea(idea):
        return PRIORITY_ID
    slug = _slugify(title)
    return f"SPEC-{slug or 'FEATURE'}-001"


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[A-Za-z0-9]+", ascii_text.upper())
    stopwords = {"A", "O", "AS", "OS", "DE", "DA", "DO", "DAS", "DOS", "EM", "PARA", "QUE"}
    useful = [token for token in tokens if token not in stopwords]
    return "-".join(useful[:3])


def _assumptions_for(idea: str) -> list[str]:
    if _is_priority_idea(idea):
        return [
            "Prioridades são fixas: Baixa, Média, Alta.",
            "Prioridade padrão: Média.",
            "Ordenação por prioridade fica fora do MVP.",
            "Filtro por prioridade fica fora do MVP.",
            "Tarefas antigas devem ser preservadas.",
        ]
    return [
        "A primeira versão deve focar no menor comportamento testável.",
        "A feature deve preservar dados existentes quando houver persistência.",
        "Automação, filtros e ordenação ficam fora do MVP salvo quando explicitamente pedidos.",
    ]


def _load_project_profile(base: Path) -> dict:
    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    if not profile_path.exists():
        return {}
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _profile_warning(profile: dict) -> str | None:
    if not profile or profile.get("profile_status") == "approved":
        return None
    parts = ["Project Profile is preliminary and not approved."]
    if profile.get("requires_agent_review"):
        parts.append("Recommended: devforge scan --agent codex.")
    parts.append("Approve it with: devforge profile approve.")
    return " ".join(parts)


def _attach_profile_warning(result: dict, profile: dict) -> None:
    warning = _profile_warning(profile)
    if warning:
        result["profile_warning"] = warning


def _gray_areas_for(idea: str) -> list[str]:
    if _is_priority_idea(idea):
        return [
            "Prioridades serão fixas ou customizáveis?",
            "Ordenação fica fora do MVP?",
            "Filtro fica fora do MVP?",
            "Tarefas antigas devem receber Média?",
        ]
    return [
        "Quais casos de uso são obrigatórios no MVP?",
        "Quais dados existentes precisam ser preservados?",
        "Há restrições de segurança, privacidade ou schema?",
        "Quais comportamentos ficam explicitamente fora do escopo?",
    ]


def _gray_areas_status(
    status: str,
    gray_areas: list[str],
    clarified_decisions: list[dict[str, str]],
) -> str:
    if not gray_areas:
        return "none"
    if status == "Approved" or clarified_decisions:
        return "resolved"
    return "unresolved"


def _next_steps(spec_rel: str, status: str, gray_areas_status: str) -> list[str]:
    plan = f"devforge plan --spec {spec_rel}"
    if status == "Approved":
        return [plan]
    if gray_areas_status == "unresolved":
        return [
            f"devforge specify --spec {spec_rel} --interactive",
            f"devforge specify --spec {spec_rel} --approve",
            plan,
        ]
    return [
        f"devforge specify --spec {spec_rel} --approve",
        plan,
    ]


def _render_spec(
    spec_id: str,
    title: str,
    status: str,
    idea: str,
    assumptions: list[str],
    interactive_notes: dict[str, str],
) -> str:
    if spec_id == PRIORITY_ID or _is_priority_idea(idea):
        return _render_priority_spec(spec_id, title, status)

    problem = interactive_notes.get("problem") or f"O usuário precisa de uma mudança descrita como: {idea}."
    success = interactive_notes.get("success") or "A mudança é verificável por critérios de aceite independentes."
    out_of_scope = interactive_notes.get("out_of_scope") or "Automação adicional"
    risk = interactive_notes.get("risk") or "Escopo ainda pode precisar de refinamento antes da implementação."
    requirement_prefix = _slugify(title).split("-")[0] or "FEATURE"

    return "\n".join([
        f"# {spec_id} — {title}",
        "",
        f"Status: {status}",
        "",
        "## Problem Statement",
        "",
        problem,
        success,
        "",
        "## Goals",
        "",
        "- [ ] Entregar o comportamento principal descrito na ideia.",
        "- [ ] Tornar a mudança verificável por critérios de aceite.",
        "",
        "## Out of Scope",
        "",
        "| Feature | Reason |",
        "| ------- | ------ |",
        f"| {out_of_scope} | Fora do MVP inicial |",
        "",
        "## User Stories",
        "",
        "### P1: Comportamento principal ⭐ MVP",
        "",
        "**User Story**:",
        "As a user, I want the requested feature so that I can complete the intended workflow.",
        "",
        "**Why P1**:",
        "É o comportamento central da feature.",
        "",
        "**Acceptance Criteria**:",
        "1. WHEN o usuário executa o fluxo principal THEN o sistema SHALL entregar o comportamento esperado.",
        "2. WHEN entradas obrigatórias estiverem ausentes THEN o sistema SHALL usar um comportamento seguro.",
        "3. WHEN o resultado for exibido THEN o sistema SHALL apresentar informação suficiente para validação.",
        "",
        "**Independent Test**:",
        "Executar o fluxo principal e verificar se o resultado esperado aparece.",
        "",
        "## Edge Cases",
        "",
        "- WHEN entrada estiver ausente THEN o sistema SHALL usar fallback seguro.",
        "- WHEN entrada for inválida THEN o sistema SHALL evitar perda de dados.",
        "",
        "## Requirement Traceability",
        "",
        "| Requirement ID | Story | Phase | Status |",
        "| -------------- | ----- | ----- | ------ |",
        f"| {requirement_prefix}-01 | P1: Comportamento principal | Design | Pending |",
        "",
        "## Risks",
        "",
        f"- {risk}",
        "",
        "## Expected Evidence",
        "",
        "- test_report",
        "- rollback_plan",
        "- human_review",
        "- audit_log",
        "- evidence_pack",
        "",
        "## Success Criteria",
        "",
        "- [ ] Fluxo principal funciona.",
        "- [ ] Critérios de aceite são testáveis.",
        *[f"- [ ] {assumption}" for assumption in assumptions[:2]],
        "",
    ])


def _render_priority_spec(spec_id: str, title: str, status: str) -> str:
    return f"""# {spec_id} — {title}

Status: {status}

## Problem Statement

Usuários precisam identificar quais tarefas são mais importantes sem depender apenas da ordem de criação.
A feature adiciona prioridade explícita às tarefas para facilitar triagem visual no Todo App.

## Goals

- [ ] Permitir que o usuário defina prioridade Baixa, Média ou Alta ao criar uma tarefa.
- [ ] Exibir a prioridade salva na listagem de tarefas.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Ordenação por prioridade | Fora do MVP inicial |
| Filtro por prioridade | Fora do MVP inicial |
| Login/autenticação | Fora do escopo da feature |

## User Stories

### P1: Criar tarefa com prioridade ⭐ MVP

**User Story**:
As a user, I want to assign a priority to a task so that I can identify what is more important.

**Why P1**:
É o comportamento central da feature.

**Acceptance Criteria**:
1. WHEN o usuário cria uma tarefa escolhendo prioridade THEN o sistema SHALL salvar a tarefa com a prioridade escolhida.
2. WHEN o usuário cria uma tarefa sem prioridade explícita THEN o sistema SHALL usar "Média" como prioridade padrão.
3. WHEN a tarefa aparece na lista THEN o sistema SHALL exibir a prioridade salva.

**Independent Test**:
Criar uma tarefa com prioridade Alta e verificar se ela aparece na lista com "Alta".

### P2: Preservar tarefas existentes

**User Story**:
As a user, I want existing tasks to remain available after the change so that I do not lose local data.

**Acceptance Criteria**:
1. WHEN o banco local já possui tarefas THEN o sistema SHALL preservar essas tarefas após a migração.
2. WHEN a coluna de prioridade não existe THEN o sistema SHALL aplicar valor padrão "Média" às tarefas existentes.

**Independent Test**:
Criar tarefa antes da migração, aplicar a mudança e verificar se a tarefa continua existindo.

### P3: Ordenar por prioridade

Nice-to-have fora do MVP inicial.

## Edge Cases

- WHEN priority estiver ausente THEN o sistema SHALL usar "Média".
- WHEN priority for inválida THEN o sistema SHALL normalizar para "Média".
- WHEN houver tarefas antigas no banco THEN o sistema SHALL preservar os registros existentes.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PRIORITY-01 | P1: Criar tarefa com prioridade | Design | Pending |
| PRIORITY-02 | P1: Exibir prioridade na lista | Design | Pending |
| PRIORITY-03 | P2: Preservar tarefas existentes | Design | Pending |

## Risks

- Toca banco SQLite.
- Pode exigir alteração de schema.
- Pode quebrar tarefas antigas se a migração for mal feita.

## Expected Evidence

- test_report
- rollback_plan
- human_review
- audit_log
- evidence_pack

## Success Criteria

- [ ] Usuário consegue criar tarefa com prioridade Baixa, Média ou Alta.
- [ ] Tarefas sem prioridade explícita usam Média.
- [ ] Tarefas existentes são preservadas.
- [ ] Prioridade aparece na listagem.
"""


def _render_specification_brief(
    spec_id: str,
    idea: str,
    assumptions: list[str],
    gray_areas: list[str],
    spec_rel: str,
    clarified_decisions: list[dict[str, str]],
    project_profile: dict | None = None,
) -> str:
    project_profile = project_profile or {}
    lines = [
        f"# DevForge Specification Brief — {spec_id}",
        "",
        "## Purpose",
        "",
        "This brief captures the user's feature idea and turns it into a testable, traceable SPEC.",
        "",
        "## Original idea",
        "",
        idea,
        "",
        "## Clarifying assumptions",
        "",
        *[f"- {item}" for item in assumptions],
        "",
        "## Gray areas",
        "",
        *[f"- {item}" for item in gray_areas],
        "",
    ]
    if project_profile:
        lines.extend([
            "## Project Profile Context",
            "",
            f"- project_type: {project_profile.get('project_type', 'unknown')}",
            f"- detected_stack: {', '.join(project_profile.get('detected_stack', [])) or 'unknown'}",
            f"- confidence: {project_profile.get('confidence', 'unknown')}",
            f"- source: {project_profile.get('source', 'unknown')}",
            "",
        ])
    if clarified_decisions:
        lines.extend(_clarified_decision_lines(clarified_decisions))
        lines.append("")
    lines.extend([
        "## Generated SPEC",
        "",
        "Path:",
        spec_rel,
        "",
        "## Next step",
        "",
        "Review the generated SPEC.",
        "",
        "If approved, run:",
        "",
        f"devforge plan --spec {spec_rel}",
        "",
    ])
    return "\n".join(lines)


def _resolve_agent_command(agent: str, command: str | None, prompt: str) -> list[str]:
    if agent == "codex":
        base_command = shlex.split(command) if command else ["codex"]
    elif agent == "custom":
        if not command:
            raise ValueError("--agent custom exige --command.")
        base_command = shlex.split(command)
    else:
        raise ValueError(f"Agente não suportado: {agent}. Use none, codex ou custom.")
    return [*base_command, prompt]


def _maybe_run_agent(
    base: Path,
    spec_id: str,
    specification_brief_path: str,
    agent: str,
    command_args: list[str],
    yes: bool,
    plain: bool,
    output_json: bool,
) -> tuple[bool, int, str, str]:
    if not command_args:
        return False, 0, "", ""

    if not plain and not output_json:
        _emit_agent_preview(spec_id, specification_brief_path, agent, command_args)
    if not yes and not output_json:
        answer = input("Continuar? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "s", "sim"}:
            return False, 1, "", "Execução do agente cancelada pelo usuário."
    elif not yes and output_json:
        return False, 1, "", "Use --yes para executar agente em modo JSON ou --dry-run para inspecionar."

    try:
        completed = subprocess.run(
            command_args,
            cwd=base,
            capture_output=True,
            text=True,
            timeout=None,
        )
        return True, completed.returncode, completed.stdout, completed.stderr
    except FileNotFoundError as exc:
        return True, 127, "", str(exc)


def _result(
    spec_id: str,
    spec_path: str,
    specification_brief_path: str,
    status: str,
    title: str,
    idea: str,
    assumptions: list[str],
    gray_areas: list[str],
    gray_areas_status: str,
    clarified_decisions: list[dict[str, str]],
    next_steps: list[str],
    agent: str,
    executed: bool,
    dry_run: bool,
    command_args: list[str],
    exit_code: int = 0,
    reason: str | None = None,
    stdout: str = "",
    stderr: str = "",
) -> dict:
    return {
        "spec_id": spec_id,
        "spec_path": spec_path,
        "specification_brief_path": specification_brief_path,
        "status": status,
        "approved": status == "Approved",
        "title": title,
        "idea": idea,
        "assumptions": assumptions,
        "gray_areas": gray_areas,
        "gray_areas_status": gray_areas_status,
        "clarified_decisions": clarified_decisions,
        "next_step": next_steps[0] if next_steps else None,
        "next_steps": next_steps,
        "agent": agent,
        "executed": executed,
        "dry_run": dry_run,
        "command": shlex.join(command_args) if command_args else None,
        "exit_code": exit_code,
        "reason": reason,
        "stdout": stdout,
        "stderr": stderr,
    }


def _failure(reason: str) -> dict:
    return {
        "spec_id": None,
        "spec_path": None,
        "specification_brief_path": None,
        "status": None,
        "approved": False,
        "title": None,
        "idea": None,
        "assumptions": [],
        "gray_areas": [],
        "gray_areas_status": "unknown",
        "clarified_decisions": [],
        "next_step": None,
        "next_steps": [],
        "agent": None,
        "executed": False,
        "dry_run": False,
        "command": None,
        "exit_code": 1,
        "reason": reason,
        "stdout": "",
        "stderr": "",
    }


def _resolve_spec_path(base: Path, spec: str) -> Path:
    spec_path = Path(spec)
    if spec_path.is_absolute():
        return spec_path
    return base / spec_path


def _relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _set_spec_status(content: str, status: str) -> str:
    if re.search(r"^Status:\s*.+$", content, flags=re.MULTILINE | re.IGNORECASE):
        return re.sub(
            r"^Status:\s*.+$",
            f"Status: {status}",
            content,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(index + 1, "")
            lines.insert(index + 2, f"Status: {status}")
            return "\n".join(lines) + "\n"
    return f"Status: {status}\n\n{content}"


def _extract_original_idea(brief_path: Path) -> str:
    if not brief_path.exists():
        return ""
    return _extract_section_text(brief_path.read_text(encoding="utf-8", errors="ignore"), "Original idea")


def _extract_brief_list(brief_path: Path, section: str) -> list[str]:
    if not brief_path.exists():
        return []
    body = _extract_section_text(brief_path.read_text(encoding="utf-8", errors="ignore"), section)
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _extract_section_text(content: str, section: str) -> str:
    pattern = rf"^##\s+{re.escape(section)}\s*$"
    match = re.search(pattern, content, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", content[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(content)
    return content[start:end].strip()


def _extract_clarified_decisions(brief_path: Path) -> list[dict[str, str]]:
    if not brief_path.exists():
        return []
    body = _extract_section_text(
        brief_path.read_text(encoding="utf-8", errors="ignore"),
        "Clarified decisions",
    )
    decisions: list[dict[str, str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        raw = stripped[2:]
        if ": " in raw:
            question, answer = raw.split(": ", 1)
            decisions.append({"question": question.strip(), "answer": answer.strip()})
    return decisions


def _with_clarified_decisions(content: str, decisions: list[dict[str, str]]) -> str:
    if not decisions:
        return content
    content = _remove_section(content, "Clarified Decisions").rstrip()
    return "\n".join([content, "", *_clarified_decision_lines(decisions), ""])


def _remove_section(content: str, section: str) -> str:
    pattern = rf"^##\s+{re.escape(section)}\s*$"
    match = re.search(pattern, content, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return content
    start = match.start()
    next_match = re.search(r"^##\s+", content[match.end():], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(content)
    return (content[:start] + content[end:]).rstrip() + "\n"


def _clarified_decision_lines(decisions: list[dict[str, str]]) -> list[str]:
    lines = ["## Clarified Decisions", ""]
    seen: set[tuple[str, str]] = set()
    for decision in decisions:
        question = decision["question"].strip()
        answer = decision["answer"].strip()
        key = (question, answer)
        if not question or not answer or key in seen:
            continue
        seen.add(key)
        lines.append(f"- {question}: {answer}")
    return lines


def _record_spec_approved(base: Path, spec_id: str, spec_path: str) -> None:
    append_event(
        get_audit_file(base),
        {
            "event": "spec.approved",
            "spec_id": spec_id,
            "spec_path": spec_path,
            "status": "Approved",
        },
    )


def _emit_agent_preview(
    spec_id: str,
    specification_brief_path: str,
    agent: str,
    command_args: list[str],
) -> None:
    print("[DevForge] Specify agent")
    print(f"spec_id: {spec_id}")
    print(f"specification_brief: {specification_brief_path}")
    print(f"agent: {agent}")
    print(f"command: {shlex.join(command_args)}")
    print("Aviso: o agente pode alterar a SPEC; não implemente código nesta etapa.")


def _emit(result: dict, plain: bool, output_json: bool) -> None:
    if output_json:
        print(json.dumps(result, ensure_ascii=False))
        return

    if result.get("reason") and not result.get("spec_id"):
        print(f"[DevForge] Specify não executado: {result['reason']}")
        return

    print("[DevForge] Specify")
    print()
    print(f"spec_id: {result['spec_id']}")
    if result["status"] != "Approved":
        print(f"spec_path: {result['spec_path']}")
        print(f"specification_brief: {result['specification_brief_path']}")
    print(f"status: {result['status']}")
    if result.get("gray_areas"):
        print(f"gray_areas_status: {result['gray_areas_status']}")
    if result.get("dry_run"):
        print("dry_run: true")
        print("Nenhum arquivo foi escrito.")
    if result.get("command"):
        print(f"agent: {result['agent']}")
        print(f"command: {result['command']}")
        if result.get("executed"):
            print(f"exit_code: {result['exit_code']}")
    if result.get("reason"):
        print(f"reason: {result['reason']}")
    if result.get("profile_warning"):
        print()
        print(f"[DevForge] Warning: {result['profile_warning']}")

    if result["status"] == "Draft" and result.get("gray_areas_status") == "unresolved":
        print()
        print("SPEC gerada como Draft.")
        print("Existem gray areas para revisar antes do planejamento.")

    if result.get("idea") and result["status"] != "Approved":
        print()
        print("Original idea:")
        print(result["idea"])

    if result.get("gray_areas") and result["status"] != "Approved":
        print()
        print("Gray areas:")
        for item in result["gray_areas"]:
            print(f"- {item}")

    if result.get("clarified_decisions") and result["status"] != "Approved":
        print()
        print("Clarified decisions:")
        for decision in result["clarified_decisions"]:
            print(f"- {decision['question']}: {decision['answer']}")

    if result.get("stdout"):
        print()
        print("stdout:")
        print(result["stdout"].rstrip())
    if result.get("stderr"):
        print()
        print("stderr:")
        print(result["stderr"].rstrip())

    print()
    if result["status"] == "Approved":
        print("SPEC aprovada.")
        print("Next step:")
        print(result["next_steps"][0])
    elif result.get("gray_areas_status") == "unresolved":
        print("Next steps:")
        print("1. Resolve gray areas:")
        print(f"   {result['next_steps'][0]}")
        print()
        print("2. Approve SPEC when ready:")
        print(f"   {result['next_steps'][1]}")
        print()
        print("3. After approval:")
        print(f"   {result['next_steps'][2]}")
    else:
        print("Next steps:")
        print("1. Approve SPEC when ready:")
        print(f"   {result['next_steps'][0]}")
        print()
        print("2. After approval:")
        print(f"   {result['next_steps'][1]}")
