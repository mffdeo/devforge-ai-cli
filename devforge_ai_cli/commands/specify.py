from __future__ import annotations

import json
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file
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
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    collected_idea = idea.strip() if idea else ""
    interactive_notes: dict[str, str] = {}
    if not collected_idea and interactive:
        interactive_notes = _collect_interactive_notes()
        collected_idea = interactive_notes["feature"]

    if not collected_idea:
        result = _failure("Informe --idea ou use --interactive.")
        _emit(result, plain=plain, output_json=output_json)
        return 1

    resolved_title = (title or _infer_title(collected_idea)).strip()
    resolved_spec_id = (spec_id or _infer_spec_id(collected_idea, resolved_title)).strip().upper()
    status = "Approved" if approve else "Draft"

    spec_rel = f"specs/{resolved_spec_id}.md"
    brief_rel = f".devforge/context/specification-brief-{resolved_spec_id}.md"
    assumptions = _assumptions_for(collected_idea)
    gray_areas = _gray_areas_for(collected_idea)
    next_step = f"devforge plan --spec {spec_rel}"

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
    )

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
            next_step=next_step,
            agent=normalized_agent,
            executed=False,
            dry_run=True,
            command_args=command_args,
        )
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
        append_event(
            get_audit_file(base),
            {
                "event": "spec.approved",
                "spec_id": resolved_spec_id,
                "spec_path": spec_rel,
                "status": status,
            },
        )

    executed = False
    exit_code = 0
    stdout = ""
    stderr = ""
    if command_args:
        if not plain and not output_json:
            _emit_agent_preview(resolved_spec_id, brief_rel, normalized_agent, command_args)
        if not yes and not output_json:
            answer = input("Continuar? [y/N] ").strip().lower()
            if answer not in {"y", "yes", "s", "sim"}:
                result = _result(
                    spec_id=resolved_spec_id,
                    spec_path=spec_rel,
                    specification_brief_path=brief_rel,
                    status=status,
                    title=resolved_title,
                    idea=collected_idea,
                    assumptions=assumptions,
                    gray_areas=gray_areas,
                    next_step=next_step,
                    agent=normalized_agent,
                    executed=False,
                    dry_run=False,
                    command_args=command_args,
                    reason="Execução do agente cancelada pelo usuário.",
                )
                _emit(result, plain=plain, output_json=output_json)
                return 1
        elif not yes and output_json:
            result = _result(
                spec_id=resolved_spec_id,
                spec_path=spec_rel,
                specification_brief_path=brief_rel,
                status=status,
                title=resolved_title,
                idea=collected_idea,
                assumptions=assumptions,
                gray_areas=gray_areas,
                next_step=next_step,
                agent=normalized_agent,
                executed=False,
                dry_run=False,
                command_args=command_args,
                reason="Use --yes para executar agente em modo JSON ou --dry-run para inspecionar.",
            )
            _emit(result, plain=plain, output_json=output_json)
            return 1

        executed = True
        try:
            completed = subprocess.run(
                command_args,
                cwd=base,
                capture_output=True,
                text=True,
                timeout=None,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except FileNotFoundError as exc:
            exit_code = 127
            stderr = str(exc)

    result = _result(
        spec_id=resolved_spec_id,
        spec_path=spec_rel,
        specification_brief_path=brief_rel,
        status=status,
        title=resolved_title,
        idea=collected_idea,
        assumptions=assumptions,
        gray_areas=gray_areas,
        next_step=next_step,
        agent=normalized_agent,
        executed=executed,
        dry_run=False,
        command_args=command_args,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )
    _emit(result, plain=plain, output_json=output_json)
    return exit_code


def _collect_interactive_notes() -> dict[str, str]:
    return {
        "feature": input("Qual feature você quer construir? ").strip(),
        "problem": input("Qual problema ela resolve? ").strip(),
        "user": input("Quem é o usuário? ").strip(),
        "success": input("O que significa sucesso? ").strip(),
        "out_of_scope": input("O que está fora de escopo? ").strip(),
        "risk": input("Há algum risco conhecido? ").strip(),
    }


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
) -> str:
    return "\n".join([
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


def _result(
    spec_id: str,
    spec_path: str,
    specification_brief_path: str,
    status: str,
    title: str,
    idea: str,
    assumptions: list[str],
    gray_areas: list[str],
    next_step: str,
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
        "title": title,
        "idea": idea,
        "assumptions": assumptions,
        "gray_areas": gray_areas,
        "next_step": next_step,
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
        "title": None,
        "idea": None,
        "assumptions": [],
        "gray_areas": [],
        "next_step": None,
        "agent": None,
        "executed": False,
        "dry_run": False,
        "command": None,
        "exit_code": 1,
        "reason": reason,
        "stdout": "",
        "stderr": "",
    }


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
    print(f"spec_path: {result['spec_path']}")
    print(f"specification_brief: {result['specification_brief_path']}")
    print(f"status: {result['status']}")
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
    print()
    print("Original idea:")
    print(result["idea"])
    print()
    print("Gray areas:")
    for item in result["gray_areas"]:
        print(f"- {item}")
    if result.get("stdout"):
        print()
        print("stdout:")
        print(result["stdout"].rstrip())
    if result.get("stderr"):
        print()
        print("stderr:")
        print(result["stderr"].rstrip())
    print()
    print("Next step:")
    print(result["next_step"])
