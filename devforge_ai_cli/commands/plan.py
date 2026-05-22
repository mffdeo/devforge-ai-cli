import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.planner import generate_plan, parse_spec
from devforge_ai_cli.core.project import require_init

_DRAFT_WARNING = "SPEC status is Draft. Consider approving/reviewing before planning."


def run_plan(spec: str, plain: bool, output_json: bool, cwd: Path | None = None) -> None:
    base = cwd or Path.cwd()
    require_init(base)

    # require scan
    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    if not profile_path.exists():
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print(
            f"[{t.AMBER}]⚠ project-profile.json não encontrado. "
            f"Rode: devforge scan[/{t.AMBER}]"
        )
        raise SystemExit(1)

    # require spec file
    spec_path = Path(spec)
    if not spec_path.is_absolute():
        spec_path = base / spec
    if not spec_path.exists():
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print(f"[{t.RED}]✗ SPEC não encontrada: {spec}[/{t.RED}]")
        raise SystemExit(1)

    spec_status = parse_spec(spec_path).get("status", "Unknown")
    warning = _DRAFT_WARNING if str(spec_status).lower() == "draft" else None

    result = generate_plan(spec_path=spec_path, base=base)

    append_event(get_audit_file(base), {
        "event": "plan.generated",
        "spec_id": result.spec_id,
        "plan_id": result.plan_id,
        "context_pack_id": result.context_pack_id,
        "policy_decision": result.policy_decision,
        "prcp_level": result.prcp_level,
        "required_evidence": result.required_evidence,
        "generated_files": result.generated_files,
        "implementation_brief_path": result.implementation_brief_path,
    })

    agent_prompt = (
        f'Implemente a feature usando o briefing em '
        f'{result.implementation_brief_path}'
    )

    if output_json:
        print(json.dumps({
            "spec_id": result.spec_id,
            "plan_id": result.plan_id,
            "context_pack_id": result.context_pack_id,
            "policy_decision": result.policy_decision,
            "prcp_level": result.prcp_level,
            "tasks": result.tasks,
            "allowed_uses": result.allowed_uses,
            "blocked_uses": result.blocked_uses,
            "required_evidence": result.required_evidence,
            "generated_files": result.generated_files,
            "implementation_brief_path": result.implementation_brief_path,
            "agent_prompt": agent_prompt,
            "spec_status": spec_status,
            "warning": warning,
            "next_step": "devforge policy check --diff",
        }))
    elif plain:
        if warning:
            print(f"[DevForge] Warning: {warning}")
        print(f"[DevForge] Plan Pack gerado: {result.plan_id}")
        print(f"SPEC: {result.spec_id} — {result.spec_title}")
        print(f"PRCP: {result.prcp_level}")
        print(f"Política: {result.policy_decision}")
        for task in result.tasks:
            print(f"  - [{task['id']}] {task['description']}")
        print(f"Evidências: {', '.join(result.required_evidence)}")
        for f in result.generated_files:
            print(f"  {f}")
        print()
        print("Próximo passo: peça ao seu agente de IA:")
        print(f'  "{agent_prompt}"')
        print()
        print("Depois rode: devforge policy check --diff")
    else:
        if warning:
            from devforge_ai_cli.ui import theme as t
            from devforge_ai_cli.ui.console import console
            console.print(f"[{t.AMBER}]⚠ {warning}[/{t.AMBER}]")
        from devforge_ai_cli.ui.renderers.plan_screen import render_plan
        render_plan(result)
