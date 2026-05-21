import json
from pathlib import Path

from devforge_ai_cli.core.paths import get_devforge_dir


def write_evidence_pack(evidence: dict, cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    evidence_dir = get_devforge_dir(base) / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    evidence_id = evidence["evidence_id"]

    json_path = evidence_dir / f"{evidence_id}.json"
    json_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = evidence_dir / f"{evidence_id}.md"
    md_path.write_text(
        f"# Evidence Pack — {evidence_id}\n\n"
        f"**Issue:** {evidence['issue_id']}\n"
        f"**Status:** {evidence['status']}\n"
        f"**Generated:** {evidence['timestamp']}\n\n"
        f"## Policy Decision\n\n{evidence['policy_decision']}\n\n"
        f"## Checklist\n\n"
        f"- Tests passed: {evidence['tests_passed']}\n"
        f"- Human review required: {evidence['human_review_required']}\n"
        f"- Rollback plan: {evidence['rollback_plan']}\n\n"
        f"## Audit\n\nSee `.devforge/audit/audit.ndjson`\n",
        encoding="utf-8",
    )

    return md_path
