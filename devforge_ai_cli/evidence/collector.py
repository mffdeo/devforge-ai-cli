import subprocess
from pathlib import Path

from devforge_ai_cli.core.paths import get_devforge_dir


def _check_test_report(base: Path, devforge_dir: Path) -> str:
    checks = [
        devforge_dir / "test-reports",
        devforge_dir / "evidence",
    ]
    for d in checks:
        if d.exists() and any(d.glob("test-report*")):
            return "present"
    for pattern in ["pytest*.xml", "coverage.xml", "junit.xml", "test-report.md"]:
        if list(base.rglob(pattern))[:1]:
            return "present"
    return "missing"


def _check_human_review(devforge_dir: Path) -> str:
    reviews_dir = devforge_dir / "reviews"
    if reviews_dir.exists() and any(reviews_dir.glob("HUMAN-REVIEW*")):
        return "present"
    return "missing"


def _check_rollback_plan(base: Path, devforge_dir: Path) -> str:
    for d in [devforge_dir / "rollback", devforge_dir / "evidence"]:
        if d.exists() and any(d.glob("ROLLBACK*")):
            return "present"
        if d.exists() and any(d.glob("rollback*")):
            return "present"
    for pattern in ["ROLLBACK*.md", "rollback*.md"]:
        if list(base.rglob(pattern))[:1]:
            return "present"
    return "missing"


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


def collect_evidence(issue_id: str, policy_check: dict, base: Path) -> dict:
    devforge_dir = get_devforge_dir(base)

    policy_decision = policy_check.get("decision", "REQUIRE_APPROVAL")
    prcp_level = policy_check.get("prcp_level", "Standard")
    changed_files = policy_check.get("changed_files", [])
    required_evidence = policy_check.get("required_evidence", ["audit_log"])
    reasons = policy_check.get("reasons", [])

    # re-evaluate evidence status from filesystem
    evidence_status: dict[str, str] = {}
    for ev in required_evidence:
        if ev == "test_report":
            evidence_status[ev] = _check_test_report(base, devforge_dir)
        elif ev == "human_review":
            evidence_status[ev] = _check_human_review(devforge_dir)
        elif ev == "rollback_plan":
            evidence_status[ev] = _check_rollback_plan(base, devforge_dir)
        elif ev == "audit_log":
            evidence_status[ev] = (
                "present" if (devforge_dir / "audit" / "audit.ndjson").exists() else "missing"
            )
        else:
            evidence_status[ev] = "unknown"

    missing_evidence = [k for k, v in evidence_status.items() if v == "missing"]
    tests_passed = evidence_status.get("test_report", "missing") == "present"
    human_review_required = "human_review" in required_evidence

    # final decision
    if policy_decision == "DENY":
        status = "denied"
        final_decision = "denied"
        exit_code = 2
    elif policy_decision == "REQUIRE_APPROVAL":
        if missing_evidence:
            status = "ready_for_review"
            final_decision = "pending_human_review"
        else:
            status = "ready_for_review"
            final_decision = "pending_human_review"
        exit_code = 1
    else:  # ALLOW
        if missing_evidence:
            status = "blocked_missing_evidence"
            final_decision = "blocked_missing_evidence"
            exit_code = 1
        else:
            status = "ready_for_pr"
            final_decision = "ready_for_pr"
            exit_code = 0

    diff_stat = _get_diff_stat(base)

    # collect items actually present for the pack
    collected_items = [
        ("diff", "present" if changed_files or diff_stat else "empty"),
    ] + [(ev, evidence_status.get(ev, "missing")) for ev in required_evidence]

    return {
        "evidence_id": f"EVID-{issue_id}",
        "issue_id": issue_id,
        "status": status,
        "policy_decision": policy_decision,
        "prcp_level": prcp_level,
        "tests_passed": tests_passed,
        "human_review_required": human_review_required,
        "final_decision": final_decision,
        "exit_code": exit_code,
        "changed_files": changed_files,
        "required_evidence": required_evidence,
        "evidence_status": evidence_status,
        "missing_evidence": missing_evidence,
        "reasons": reasons,
        "diff_stat": diff_stat,
        "collected_items": collected_items,
    }
