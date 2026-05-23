import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.planner import generate_plan, parse_spec
from devforge_ai_cli.core.project import require_init

_DRAFT_WARNING = "SPEC status is Draft. Consider resolving gray areas and approving it before planning."


def _profile_warning(profile: dict) -> str | None:
    if profile.get("profile_status") == "approved":
        return None
    parts = ["Project Profile is preliminary and not approved."]
    if profile.get("requires_agent_review"):
        parts.append("Recommended: devforge scan --agent codex.")
    parts.append("Approve it with: devforge profile approve.")
    return " ".join(parts)


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
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    warnings = []
    if str(spec_status).lower() == "draft":
        warnings.append(_DRAFT_WARNING)
    profile_warning = _profile_warning(profile)
    if profile_warning:
        warnings.append(profile_warning)
    warning = " ".join(warnings) if warnings else None

    result = generate_plan(spec_path=spec_path, base=base)

    append_event(get_audit_file(base), {
        "event": "plan.generated",
        "spec_id": result.spec_id,
        "plan_id": result.plan_id,
        "context_pack_id": result.context_pack_id,
        "policy_decision": result.policy_decision,
        "prcp_level": result.prcp_level,
        "domain": result.domain,
        "plan_confidence": result.plan_confidence,
        "plan_recommendation": result.plan_recommendation,
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
            "domain": result.domain,
            "plan_confidence": result.plan_confidence,
            "plan_recommendation": result.plan_recommendation,
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
        print(f"Domain: {result.domain}")
        print(f"PRCP: {result.prcp_level}")
        print(f"Plan confidence: {result.plan_confidence}")
        if result.plan_recommendation:
            print(f"Recommended review: {result.plan_recommendation}")
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
