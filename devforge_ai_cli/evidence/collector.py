import subprocess
from pathlib import Path

from devforge_ai_cli.core.evidence_rules import (
    check_review_request,
    evaluate_required_evidence,
)
from devforge_ai_cli.core.paths import get_devforge_dir


def _get_diff_stat(base: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=base, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        r2 = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=base, capture_output=True, text=True, timeout=10,
        )
        return r2.stdout.strip() if r2.returncode == 0 else ""
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _spec_id_from_issue(issue_id: str) -> str | None:
    """Best-effort: 'ISSUE-PRIORITY-001' → 'SPEC-PRIORITY-001'."""
    if not issue_id:
        return None
    if issue_id.upper().startswith("ISSUE-"):
        return "SPEC-" + issue_id[6:]
    if issue_id.upper().startswith("SPEC-"):
        return issue_id
    return None


def collect_evidence(issue_id: str, policy_check: dict, base: Path) -> dict:
    devforge_dir = get_devforge_dir(base)

    policy_decision = policy_check.get("decision", "REQUIRE_APPROVAL")
    # Carry both PRCP levels from the policy check. prcp_level (effective)
    # remains for backwards compatibility, but downstream consumers can now
    # disambiguate project baseline vs SPEC-effective elevation.
    effective_prcp_level = (
        policy_check.get("effective_prcp_level")
        or policy_check.get("prcp_level")
        or "Standard"
    )
    project_prcp_baseline = (
        policy_check.get("project_prcp_baseline")
        or policy_check.get("prcp_level")
        or effective_prcp_level
    )
    prcp_level = effective_prcp_level
    changed_files = policy_check.get("changed_files", [])
    required_evidence = policy_check.get("required_evidence", ["audit_log"])
    reasons = policy_check.get("reasons", [])

    spec_id = _spec_id_from_issue(issue_id)
    matches = evaluate_required_evidence(
        required_evidence, base, devforge_dir, spec_id=spec_id
    )
    evidence_status: dict[str, str] = {name: m.status for name, m in matches.items()}
    evidence_details = {
        name: {
            "status": m.status,
            "matched_paths": m.matched_paths,
            "matched_rule": m.matched_rule,
            "expected_paths": m.expected_paths,
            "notes": m.notes,
        }
        for name, m in matches.items()
    }
    review_request = check_review_request(base, devforge_dir)

    missing_evidence = [k for k, v in evidence_status.items() if v == "missing"]
    tests_passed = evidence_status.get("test_report", "missing") == "present"
    human_review_required = "human_review" in required_evidence

    human_review_status = evidence_status.get("human_review", "missing")

    # Final decision is derived from the policy gate plus the evidence that
    # is actually present now. A recorded human review must never remain in a
    # pending_human_review state.
    if policy_decision == "DENY":
        status = "blocked"
        final_decision = "denied"
        exit_code = 2
    elif policy_decision == "REQUIRE_APPROVAL":
        if human_review_status == "missing":
            status = "waiting_for_human_review"
            final_decision = "pending_human_review"
            exit_code = 1
        elif missing_evidence:
            status = "missing_required_evidence"
            final_decision = "pending_required_evidence"
            exit_code = 1
        else:
            status = "ready_for_merge"
            final_decision = "approved_with_human_review"
            exit_code = 0
    else:  # ALLOW
        if missing_evidence:
            status = "missing_required_evidence"
            final_decision = "pending_required_evidence"
            exit_code = 1
        else:
            status = "ready_for_merge"
            final_decision = "allowed"
            exit_code = 0

    diff_stat = _get_diff_stat(base)

    collected_items = [
        ("diff", "present" if changed_files or diff_stat else "empty"),
    ] + [(ev, evidence_status.get(ev, "missing")) for ev in required_evidence]

    return {
        "evidence_id": f"EVID-{issue_id}",
        "issue_id": issue_id,
        "status": status,
        "policy_decision": policy_decision,
        "prcp_level": prcp_level,
        "project_prcp_baseline": project_prcp_baseline,
        "effective_prcp_level": effective_prcp_level,
        "tests_passed": tests_passed,
        "human_review_required": human_review_required,
        "final_decision": final_decision,
        "exit_code": exit_code,
        "changed_files": changed_files,
        "required_evidence": required_evidence,
        "evidence_status": evidence_status,
        "evidence_details": evidence_details,
        "review_request_present": review_request.present,
        "review_request_paths": review_request.matched_paths,
        "missing_evidence": missing_evidence,
        "reasons": reasons,
        "diff_stat": diff_stat,
        "collected_items": collected_items,
    }
