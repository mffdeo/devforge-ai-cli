import json
import shlex
import subprocess
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.git import detect_project_name
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init
from devforge_ai_cli.core.scanner import run_scan


def run_scan_cmd(
    plain: bool,
    output_json: bool,
    cwd: Path | None = None,
    agent: str = "none",
    command: str | None = None,
    dry_run: bool = False,
    yes: bool = False,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    project_name = detect_project_name(base)
    result = run_scan(project_name=project_name, base=base)
    agent_result = _run_agent_if_requested(
        base=base,
        agent=agent,
        command=command,
        dry_run=dry_run,
        yes=yes,
        plain=plain,
        output_json=output_json,
    )

    append_event(get_audit_file(base), {
        "event": "scan.completed",
        "project": result.project_name,
        "project_type": result.project_type,
        "detected_stack": result.detected_stack,
        "baseline_level": result.baseline_level,
        "task_elevation": result.task_elevation,
        "confidence": result.confidence,
        "profile_status": result.profile_status,
        "requires_agent_review": result.requires_agent_review,
        "requires_user_approval": result.requires_user_approval,
        "source": result.source,
        "signals": result.signals,
        "generated_files": result.generated_files,
        "agent": agent,
        "agent_executed": agent_result["executed"],
        "agent_dry_run": agent_result["dry_run"],
    })

    if output_json:
        print(json.dumps({
            "project_name": result.project_name,
            "project_type": result.project_type,
            "detected_stack": result.detected_stack,
            "architecture_summary": result.architecture_summary,
            "ci_detected": result.ci_detected,
            "databases_detected": result.databases_detected,
            "has_database": result.has_database,
            "has_auth": result.has_auth,
            "personal_data_possible": result.personal_data_possible,
            "external_integrations": result.external_integrations,
            "production_impact": result.production_impact,
            "sensitive_areas": result.sensitive_areas,
            "signals": result.signals,
            "baseline_level": result.baseline_level,
            "task_elevation": result.task_elevation,
            "confidence": result.confidence,
            "profile_status": result.profile_status,
            "requires_agent_review": result.requires_agent_review,
            "requires_user_approval": result.requires_user_approval,
            "assumptions": result.assumptions,
            "gray_areas": result.gray_areas,
            "source": result.source,
            "generated_files": result.generated_files,
            "suggested_next_spec": result.suggested_next_spec,
            "suggested_next_command": result.suggested_next_command,
            "recommended_next_step": result.suggested_next_command,
            "agent": agent_result,
            "next_steps": [
                "Review preliminary Project Profile",
                "Approve profile with devforge profile approve when ready",
                result.suggested_next_command,
            ],
        }, ensure_ascii=False))
    elif plain:
        print("[DevForge] Signals collected")
        print("[DevForge] Preliminary project profile")
        print(f"[DevForge] Project type: {result.project_type}")
        print(f"[DevForge] Stack: {', '.join(result.detected_stack) or 'nenhuma'}")
        print(f"[DevForge] Profile confidence: {result.confidence}")
        print(f"[DevForge] Profile status: {result.profile_status}")
        print(f"[DevForge] Source: {result.source}")
        if result.requires_agent_review:
            print("[DevForge] Project profile is preliminary.")
            print("[DevForge] Recommended: devforge scan --agent codex")
            print("[DevForge] Do not treat this profile as final until reviewed or approved.")
        if result.ci_detected:
            print(f"[DevForge] CI detectado: {result.ci_detected}")
        if result.databases_detected:
            print(f"[DevForge] Banco detectado: {', '.join(result.databases_detected)}")
        if result.gray_areas:
            print("[DevForge] Gray areas:")
            for item in result.gray_areas:
                print(f"  - {item}")
        print(f"[DevForge] Áreas sensíveis: {', '.join(result.sensitive_areas) or 'nenhuma'}")
        print(f"[DevForge] PRCP baseline: {result.baseline_level}")
        print(f"[DevForge] Elevação por tarefa: {result.task_elevation}")
        for f in result.generated_files:
            print(f"  {f}")
        if agent_result["command"]:
            print(f"[DevForge] Agent command: {agent_result['command']}")
            if agent_result["dry_run"]:
                print("[DevForge] Dry run: agente não executado.")
            elif agent_result["executed"]:
                print(f"[DevForge] Agent exit_code: {agent_result['exit_code']}")
        print(f"[DevForge] Recommended review: {result.suggested_next_command}")
    else:
        from devforge_ai_cli.ui.renderers.scan_screen import render_scan
        render_scan(result)
    return agent_result["exit_code"]


def _run_agent_if_requested(
    base: Path,
    agent: str,
    command: str | None,
    dry_run: bool,
    yes: bool,
    plain: bool,
    output_json: bool,
) -> dict:
    normalized = agent.lower().strip()
    if normalized == "none":
        return _agent_result(agent=normalized, command_args=[], exit_code=0, executed=False, dry_run=False)

    brief_rel = ".devforge/context/project-profile-brief.md"
    profile_rel = ".devforge/prcp/project-profile.json"
    prompt = (
        f"Analyze the project using {brief_rel}. Do not implement code. "
        f"Do not alter application files. Only improve {profile_rel} if needed."
    )
    try:
        command_args = _resolve_agent_command(normalized, command, prompt)
    except ValueError as exc:
        return _agent_result(
            agent=normalized,
            command_args=[],
            exit_code=1,
            executed=False,
            dry_run=False,
            stderr=str(exc),
        )

    if dry_run:
        return _agent_result(
            agent=normalized,
            command_args=command_args,
            exit_code=0,
            executed=False,
            dry_run=True,
        )

    if not plain and not output_json:
        print("[DevForge] Scan agent")
        print(f"agent: {normalized}")
        print(f"command: {shlex.join(command_args)}")
        print("Aviso: o agente deve atualizar apenas o Project Profile, sem alterar código.")
    if not yes and not output_json:
        answer = input("Continuar? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "s", "sim"}:
            return _agent_result(
                agent=normalized,
                command_args=command_args,
                exit_code=1,
                executed=False,
                dry_run=False,
                stderr="Execução do agente cancelada pelo usuário.",
            )
    elif not yes and output_json:
        return _agent_result(
            agent=normalized,
            command_args=command_args,
            exit_code=1,
            executed=False,
            dry_run=False,
            stderr="Use --yes para executar agente em modo JSON ou --dry-run para inspecionar.",
        )

    append_event(get_audit_file(base), {
        "event": "scan.agent.started",
        "agent": normalized,
        "command": shlex.join(command_args),
        "profile_brief_path": brief_rel,
    })
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
    if exit_code == 0:
        _mark_profile_agent_assisted(get_devforge_dir(base) / "prcp" / "project-profile.json")
    append_event(get_audit_file(base), {
        "event": "scan.agent.finished",
        "agent": normalized,
        "command": shlex.join(command_args),
        "exit_code": exit_code,
    })
    return _agent_result(
        agent=normalized,
        command_args=command_args,
        exit_code=exit_code,
        executed=True,
        dry_run=False,
        stdout=stdout,
        stderr=stderr,
    )


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


def _agent_result(
    agent: str,
    command_args: list[str],
    exit_code: int,
    executed: bool,
    dry_run: bool,
    stdout: str = "",
    stderr: str = "",
) -> dict:
    return {
        "agent": agent,
        "command": shlex.join(command_args) if command_args else None,
        "exit_code": exit_code,
        "executed": executed,
        "dry_run": dry_run,
        "stdout": stdout,
        "stderr": stderr,
    }


def _mark_profile_agent_assisted(profile_path: Path) -> None:
    if not profile_path.exists():
        return
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    profile["source"] = "agent_assisted"
    profile["profile_status"] = "reviewed"
    profile["requires_agent_review"] = False
    profile["requires_user_approval"] = True
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
