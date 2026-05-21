import json
from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.git import get_changed_files, get_diff_content
from devforge_ai_cli.core.ignore import should_ignore_path
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init
from devforge_ai_cli.policy_engine.engine import evaluate_policy


def _check_evidence_status(required_evidence: list[str], devforge_dir: Path) -> dict[str, str]:
    status: dict[str, str] = {}
    for ev in required_evidence:
        if ev == "test_report":
            evidence_dir = devforge_dir / "evidence"
            reports_dir = devforge_dir / "test-reports"
            base = devforge_dir.parent
            present = (
                reports_dir.exists()
                or (evidence_dir.exists() and any(evidence_dir.glob("test-report*")))
                or any(
                    not should_ignore_path(p.relative_to(base))
                    for p in base.rglob("pytest*.xml")
                )
                or any(
                    not should_ignore_path(p.relative_to(base))
                    for p in base.rglob("coverage.xml")
                )
            )
        elif ev == "human_review":
            reviews_dir = devforge_dir / "reviews"
            present = reviews_dir.exists() and any(reviews_dir.glob("HUMAN-REVIEW*"))
        elif ev == "rollback_plan":
            rollback_dir = devforge_dir / "rollback"
            evidence_dir = devforge_dir / "evidence"
            present = (
                (rollback_dir.exists() and any(rollback_dir.glob("ROLLBACK*")))
                or (evidence_dir.exists() and any(evidence_dir.glob("rollback*")))
            )
        elif ev == "audit_log":
            present = (devforge_dir / "audit" / "audit.ndjson").exists()
        else:
            present = False
        status[ev] = "present" if present else "missing"
    return status


def run_policy_check(
    diff: bool,
    plain: bool,
    output_json: bool,
    cwd: Path | None = None,
    changed_files_override: list[str] | None = None,
    diff_content_override: str | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    devforge_dir = get_devforge_dir(base)

    # require scan
    profile_path = devforge_dir / "prcp" / "project-profile.json"
    if not profile_path.exists():
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print(f"[{t.AMBER}]⚠ project-profile.json não encontrado. Rode: devforge scan[/{t.AMBER}]")
        raise SystemExit(1)

    # require plan
    policy_dir = devforge_dir / "policy"
    existing_policy_files = list(policy_dir.glob("POLICY-DECISION-*.json")) if policy_dir.exists() else []
    if not existing_policy_files:
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print(f"[{t.AMBER}]⚠ Nenhuma Policy Decision encontrada. Rode: devforge plan --spec <arquivo>[/{t.AMBER}]")
        raise SystemExit(1)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    existing_policy = json.loads(
        max(existing_policy_files, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    )

    # git diff
    if changed_files_override is not None:
        changed_files = [f for f in changed_files_override if not should_ignore_path(f)]
        diff_content = diff_content_override or ""
    elif diff:
        changed_files = get_changed_files(base)
        diff_content = get_diff_content(base)
    else:
        changed_files = []
        diff_content = ""

    result = evaluate_policy(
        changed_files=changed_files,
        diff_content=diff_content,
        profile=profile,
        existing_policy=existing_policy,
    )

    evidence_status = _check_evidence_status(result["required_evidence"], devforge_dir)
    missing_evidence = [k for k, v in evidence_status.items() if v == "missing"]

    timestamp = datetime.now(timezone.utc).isoformat()
    prcp_level = profile.get("prcp", {}).get("task_elevation", "Standard")
    policy_source = str(existing_policy_files[0].relative_to(base)) if existing_policy_files else None

    payload = {
        **result,
        "evidence_status": evidence_status,
        "missing_evidence": missing_evidence,
        "policy_source": policy_source,
        "prcp_level": prcp_level,
        "timestamp": timestamp,
    }

    # write POLICY-CHECK-LATEST.json
    policy_dir.mkdir(exist_ok=True)
    check_path = policy_dir / "POLICY-CHECK-LATEST.json"
    check_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    generated_files = [str(check_path.relative_to(base))]

    append_event(get_audit_file(base), {
        "event": "policy.checked",
        "decision": result["decision"],
        "can_advance_now": result["can_advance_now"],
        "changed_files_count": result["files_count"],
        "reasons": result["reasons"],
        "required_evidence": result["required_evidence"],
        "missing_evidence": missing_evidence,
        "generated_files": generated_files,
    })

    if output_json:
        print(json.dumps({
            "decision": result["decision"],
            "can_advance_now": result["can_advance_now"],
            "exit_code": result["exit_code"],
            "changed_files": result["changed_files"],
            "files_count": result["files_count"],
            "reasons": result["reasons"],
            "required_evidence": result["required_evidence"],
            "evidence_status": evidence_status,
            "recommended_actions": result["recommended_actions"],
            "generated_files": generated_files,
            "next_step": "devforge evidence --issue <ISSUE-ID>",
        }))
    elif plain:
        print(f"[DevForge] Decision: {result['decision']}")
        print(f"Pode avançar agora? {'Sim' if result['can_advance_now'] else 'Não ainda'}")
        print(f"Arquivos analisados: {result['files_count']}")
        for r in result["reasons"]:
            print(f"  - {r}")
        for ev in result["required_evidence"]:
            print(f"  - {ev}: {evidence_status.get(ev, 'unknown')}")
        print(f"Exit code: {result['exit_code']}")
    else:
        from devforge_ai_cli.ui.renderers.policy_screen import render_policy
        render_policy(result, evidence_status, result["files_count"], prcp_level, timestamp)

    return result["exit_code"]
