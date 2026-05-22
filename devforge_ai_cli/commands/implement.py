from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.planner import parse_spec
from devforge_ai_cli.core.project import require_init

NEXT_STEP = "devforge policy check --diff"


def run_implement(
    spec: str,
    agent: str,
    command: str | None,
    yes: bool,
    dry_run: bool,
    plain: bool,
    output_json: bool,
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    spec_path = Path(spec)
    if not spec_path.is_absolute():
        spec_path = base / spec
    if not spec_path.exists():
        result = _failure(
            spec_id=None,
            agent=agent,
            command_args=[],
            implementation_brief_path=None,
            reason=f"SPEC não encontrada: {spec}",
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    spec_data = parse_spec(spec_path)
    spec_id = spec_data["spec_id"]
    devforge_dir = get_devforge_dir(base)
    brief_path = devforge_dir / "context" / f"implementation-brief-{spec_id}.md"
    brief_rel = str(brief_path.relative_to(base))

    if not brief_path.exists():
        result = _failure(
            spec_id=spec_id,
            agent=agent,
            command_args=[],
            implementation_brief_path=brief_rel,
            reason=f"Implementation brief não encontrado. Rode `devforge plan --spec {spec}` antes de implementar.",
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    prompt = f"Implemente a feature usando {brief_rel}"
    try:
        command_args = _resolve_command(agent=agent, command=command, prompt=prompt)
    except ValueError as exc:
        result = _failure(
            spec_id=spec_id,
            agent=agent,
            command_args=[],
            implementation_brief_path=brief_rel,
            reason=str(exc),
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    if dry_run:
        result = _result(
            spec_id=spec_id,
            agent=agent,
            command_args=command_args,
            implementation_brief_path=brief_rel,
            exit_code=0,
            executed=False,
            dry_run=True,
        )
        _emit(result, plain=plain, output_json=output_json)
        return 0

    if not plain and not output_json:
        _emit_preview(
            spec_id=spec_id,
            agent=agent,
            command_args=command_args,
            implementation_brief_path=brief_rel,
        )
    if not yes and not output_json:
        answer = input("Continuar? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "s", "sim"}:
            result = _result(
                spec_id=spec_id,
                agent=agent,
                command_args=command_args,
                implementation_brief_path=brief_rel,
                exit_code=1,
                executed=False,
                dry_run=False,
                reason="Execução cancelada pelo usuário.",
            )
            _emit(result, plain=plain, output_json=output_json)
            return 1
    elif not yes and output_json:
        result = _result(
            spec_id=spec_id,
            agent=agent,
            command_args=command_args,
            implementation_brief_path=brief_rel,
            exit_code=1,
            executed=False,
            dry_run=False,
            reason="Use --yes para executar em modo JSON ou --dry-run para inspecionar.",
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    append_event(
        get_audit_file(base),
        {
            "event": "agent.implementation.started",
            "spec_id": spec_id,
            "agent": agent,
            "command": shlex.join(command_args),
            "implementation_brief_path": brief_rel,
        },
    )

    stdout = ""
    stderr = ""
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

    append_event(
        get_audit_file(base),
        {
            "event": "agent.implementation.finished",
            "spec_id": spec_id,
            "agent": agent,
            "command": shlex.join(command_args),
            "implementation_brief_path": brief_rel,
            "exit_code": exit_code,
        },
    )

    result = _result(
        spec_id=spec_id,
        agent=agent,
        command_args=command_args,
        implementation_brief_path=brief_rel,
        exit_code=exit_code,
        executed=True,
        dry_run=False,
        stdout=stdout,
        stderr=stderr,
    )
    _emit(result, plain=plain, output_json=output_json)
    return exit_code


def _resolve_command(agent: str, command: str | None, prompt: str) -> list[str]:
    normalized = agent.lower().strip()
    if normalized == "codex":
        base_command = shlex.split(command) if command else ["codex"]
    elif normalized == "custom":
        if not command:
            raise ValueError("--agent custom exige --command.")
        base_command = shlex.split(command)
    elif normalized in {"claude", "opencode"}:
        raise ValueError(f"--agent {agent} ainda não está implementado neste ciclo.")
    else:
        raise ValueError(f"Agente não suportado: {agent}. Use codex ou custom.")
    return [*base_command, prompt]


def _result(
    spec_id: str,
    agent: str,
    command_args: list[str],
    implementation_brief_path: str | None,
    exit_code: int,
    executed: bool,
    dry_run: bool,
    reason: str | None = None,
    stdout: str = "",
    stderr: str = "",
) -> dict:
    return {
        "spec_id": spec_id,
        "agent": agent,
        "command": shlex.join(command_args) if command_args else None,
        "command_args": command_args,
        "implementation_brief_path": implementation_brief_path,
        "exit_code": exit_code,
        "executed": executed,
        "dry_run": dry_run,
        "reason": reason,
        "stdout": stdout,
        "stderr": stderr,
        "next_step": NEXT_STEP,
    }


def _failure(
    spec_id: str | None,
    agent: str,
    command_args: list[str],
    implementation_brief_path: str | None,
    reason: str,
) -> dict:
    return {
        "spec_id": spec_id,
        "agent": agent,
        "command": shlex.join(command_args) if command_args else None,
        "command_args": command_args,
        "implementation_brief_path": implementation_brief_path,
        "exit_code": 1,
        "executed": False,
        "dry_run": False,
        "reason": reason,
        "stdout": "",
        "stderr": "",
        "next_step": NEXT_STEP,
    }


def _emit_preview(
    spec_id: str,
    agent: str,
    command_args: list[str],
    implementation_brief_path: str,
) -> None:
    print("[DevForge] Implementação por agente externo")
    print(f"spec_id: {spec_id}")
    print(f"implementation_brief: {implementation_brief_path}")
    print(f"agent: {agent}")
    print(f"command: {shlex.join(command_args)}")
    print("Aviso: o agente pode alterar arquivos; revise com policy check depois.")


def _emit(result: dict, plain: bool, output_json: bool) -> None:
    if output_json:
        print(json.dumps(result, ensure_ascii=False))
        return

    if result.get("reason") and not result.get("executed") and not result.get("dry_run"):
        print(f"[DevForge] Implement não executado: {result['reason']}")
        if result.get("implementation_brief_path"):
            print(f"Implementation brief: {result['implementation_brief_path']}")
        print(f"Next step: {result['next_step']}")
        return

    print("[DevForge] Implement")
    print(f"spec_id: {result['spec_id']}")
    print(f"implementation_brief: {result['implementation_brief_path']}")
    print(f"agent: {result['agent']}")
    print(f"command: {result['command']}")
    if result["dry_run"]:
        print("dry_run: true")
        print("Nenhum agente foi executado.")
    else:
        print(f"exit_code: {result['exit_code']}")
        if result.get("stdout"):
            print("stdout:")
            print(result["stdout"].rstrip())
        if result.get("stderr"):
            print("stderr:")
            print(result["stderr"].rstrip())
    print(f"Next step: {result['next_step']}")
