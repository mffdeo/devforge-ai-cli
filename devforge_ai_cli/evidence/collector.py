from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.core.paths import get_devforge_dir


def collect_evidence(issue_id: str, cwd: Path | None = None) -> dict:
    base = cwd or Path.cwd()
    devforge_dir = get_devforge_dir(base)
    evidence_dir = devforge_dir / "evidence"

    evidence = {
        "issue_id": issue_id,
        "evidence_id": f"EVID-{issue_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "tests_passed": False,
        "human_review_required": True,
        "rollback_plan": False,
        "policy_decision": "REQUIRE_APPROVAL",
    }

    if (evidence_dir / f"test-report-{issue_id}.md").exists():
        evidence["tests_passed"] = True

    if (evidence_dir / f"rollback-{issue_id}.md").exists():
        evidence["rollback_plan"] = True

    if evidence["tests_passed"] and evidence["rollback_plan"]:
        evidence["status"] = "ready_for_review"

    return evidence
