import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init
from devforge_ai_cli.evidence.collector import collect_evidence
from devforge_ai_cli.evidence.writer import write_evidence_pack


def run_evidence(issue: str, plain: bool, output_json: bool, cwd: Path | None = None) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    devforge_dir = get_devforge_dir(base)

    # require scan
    profile_path = devforge_dir / "prcp" / "project-profile.json"
    if not profile_path.exists():
        _warn("⚠ project-profile.json não encontrado. Rode: devforge scan")
        raise SystemExit(1)

    # require plan
    plans_dir = devforge_dir / "plans"
    if not plans_dir.exists() or not any(plans_dir.glob("PLAN-*.md")):
        _warn("⚠ Nenhum plano encontrado. Rode: devforge plan --spec <arquivo>")
        raise SystemExit(1)

    # require policy check
    policy_check_path = devforge_dir / "policy" / "POLICY-CHECK-LATEST.json"
    if not policy_check_path.exists():
        _warn("⚠ POLICY-CHECK-LATEST.json não encontrado. Rode: devforge policy check --diff")
        raise SystemExit(1)

    policy_check = json.loads(policy_check_path.read_text(encoding="utf-8"))

    evidence = collect_evidence(issue_id=issue, policy_check=policy_check, base=base)
    generated_files = write_evidence_pack(evidence=evidence, base=base)

    append_event(get_audit_file(base), {
        "event": "evidence.generated",
        "issue_id": issue,
        "evidence_id": evidence["evidence_id"],
        "status": evidence["status"],
        "final_decision": evidence["final_decision"],
        "policy_decision": evidence["policy_decision"],
        "required_evidence": evidence["required_evidence"],
        "missing_evidence": evidence["missing_evidence"],
        "generated_files": generated_files,
    })

    if output_json:
        print(json.dumps({
            "evidence_id": evidence["evidence_id"],
            "issue_id": evidence["issue_id"],
            "status": evidence["status"],
            "policy_decision": evidence["policy_decision"],
            "prcp_level": evidence["prcp_level"],
            "tests_passed": evidence["tests_passed"],
            "human_review_required": evidence["human_review_required"],
            "final_decision": evidence["final_decision"],
            "changed_files": evidence["changed_files"],
            "required_evidence": evidence["required_evidence"],
            "evidence_status": evidence["evidence_status"],
            "evidence_details": evidence["evidence_details"],
            "review_request_present": evidence["review_request_present"],
            "review_request_paths": evidence["review_request_paths"],
            "generated_files": generated_files,
            "next_step": "Abrir pull request com evidence pack anexado." if evidence["final_decision"] == "ready_for_pr" else "Solicitar revisão humana.",
        }))
    elif plain:
        print(f"[DevForge] Evidence Pack gerado: {evidence['evidence_id']}")
        print(f"Status: {evidence['status']}")
        print(f"Policy: {evidence['policy_decision']}")
        print(f"Final decision: {evidence['final_decision']}")
        for f in generated_files:
            print(f"  {f}")
    else:
        from devforge_ai_cli.ui.renderers.evidence_screen import render_evidence
        render_evidence(evidence, generated_files)

    return evidence["exit_code"]


def _warn(msg: str) -> None:
    from devforge_ai_cli.ui import theme as t
    from devforge_ai_cli.ui.console import console
    console.print(f"[{t.AMBER}]{msg}[/{t.AMBER}]")
