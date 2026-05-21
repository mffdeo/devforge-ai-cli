from __future__ import annotations

import json
import re
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.evidence_rules import evaluate_required_evidence
from devforge_ai_cli.core.ignore import should_ignore_path
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init

DO_NOT_COMMIT = [
    ".venv/",
    "venv/",
    "env/",
    "todo.db",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".ruff_cache/",
]

_COMMAND_RE = re.compile(
    r"\b(pytest|ruff|npm\s+test|npm\s+run\s+\w+|pnpm\s+\w+|yarn\s+\w+|"
    r"cargo\s+test|go\s+test|make\s+\w+)\b.*"
)


def run_pr_ready(
    issue: str,
    plain: bool,
    output_json: bool,
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    devforge_dir = get_devforge_dir(base)
    evidence_id = f"EVID-{issue}"
    evidence_json_path = devforge_dir / "evidence" / f"{evidence_id}.json"
    evidence_md_path = devforge_dir / "evidence" / f"{evidence_id}.md"

    if not evidence_json_path.exists() or not evidence_md_path.exists():
        result = _not_ready_result(
            issue=issue,
            status="missing_evidence_pack",
            final_decision="missing_evidence_pack",
            reasons=[
                f"Evidence Pack não encontrado: {evidence_json_path.relative_to(base)}",
                f"Evidence Pack não encontrado: {evidence_md_path.relative_to(base)}",
            ],
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    evidence = json.loads(evidence_json_path.read_text(encoding="utf-8"))
    policy_check = _read_policy_check(devforge_dir)
    spec_id = _spec_id_from_issue(issue)
    required_evidence = evidence.get("required_evidence", [])
    evidence_status = evidence.get("evidence_status", {})

    errors = _readiness_errors(evidence, evidence_status)
    if errors:
        result = _not_ready_result(
            issue=issue,
            status=evidence.get("status", "unknown"),
            final_decision=evidence.get("final_decision", "unknown"),
            reasons=errors,
        )
        _emit(result, plain=plain, output_json=output_json)
        return 1

    matches = evaluate_required_evidence(
        required_evidence,
        base,
        devforge_dir,
        spec_id=spec_id,
    )
    evidence_paths = {
        name: match.matched_paths
        for name, match in matches.items()
        if match.present and match.matched_paths
    }

    spec_path = _first_existing_rel(base, [base / "specs" / f"{spec_id}.md"])
    plan_path = _first_existing_rel(
        base,
        [
            devforge_dir / "plans" / f"PLAN-{spec_id}.md",
            devforge_dir / "plans" / f"PLAN-{issue}.md",
        ],
    )
    evidence_json_rel = str(evidence_json_path.relative_to(base))
    evidence_md_rel = str(evidence_md_path.relative_to(base))

    suggested_files = _suggested_files_to_commit(
        evidence=evidence,
        spec_path=spec_path,
        evidence_paths=evidence_paths,
        evidence_json_rel=evidence_json_rel,
        evidence_md_rel=evidence_md_rel,
    )
    suggested_commit_message = _suggest_commit_message(issue, spec_path, base)
    validation_commands = _extract_validation_commands(base, evidence_paths, evidence_md_rel)

    pr_dir = devforge_dir / "pr"
    pr_dir.mkdir(parents=True, exist_ok=True)
    pr_body_path = pr_dir / f"PR-{issue}.md"
    commit_plan_path = pr_dir / f"commit-plan-{issue}.md"

    title = _suggest_pr_title(issue, spec_path, base)
    summary = _spec_summary(spec_path, base) if spec_path else f"Change for {issue}."
    pr_body = _render_pr_body(
        title=title,
        summary=summary,
        evidence=evidence,
        policy_check=policy_check,
        issue=issue,
        spec_path=spec_path,
        plan_path=plan_path,
        evidence_paths=evidence_paths,
        evidence_json_rel=evidence_json_rel,
        evidence_md_rel=evidence_md_rel,
        validation_commands=validation_commands,
    )
    commit_plan = _render_commit_plan(
        issue=issue,
        suggested_files=suggested_files,
        suggested_commit_message=suggested_commit_message,
    )
    pr_body_path.write_text(pr_body, encoding="utf-8")
    commit_plan_path.write_text(commit_plan, encoding="utf-8")

    pr_body_rel = str(pr_body_path.relative_to(base))
    commit_plan_rel = str(commit_plan_path.relative_to(base))

    append_event(
        get_audit_file(base),
        {
            "event": "pr_ready.generated",
            "issue_id": issue,
            "pr_body_path": pr_body_rel,
            "commit_plan_path": commit_plan_rel,
            "status": evidence["status"],
            "final_decision": evidence["final_decision"],
        },
    )

    result = {
        "issue_id": issue,
        "status": evidence["status"],
        "final_decision": evidence["final_decision"],
        "ready_for_pr": True,
        "pr_body_path": pr_body_rel,
        "commit_plan_path": commit_plan_rel,
        "suggested_commit_message": suggested_commit_message,
        "suggested_files_to_commit": suggested_files,
        "do_not_commit": DO_NOT_COMMIT,
        "next_step": f"Open a pull request using {pr_body_rel}.",
    }
    _emit(result, plain=plain, output_json=output_json)
    return 0


def _read_policy_check(devforge_dir: Path) -> dict:
    policy_check_path = devforge_dir / "policy" / "POLICY-CHECK-LATEST.json"
    if not policy_check_path.exists():
        return {}
    return json.loads(policy_check_path.read_text(encoding="utf-8"))


def _spec_id_from_issue(issue_id: str) -> str:
    if issue_id.upper().startswith("ISSUE-"):
        return "SPEC-" + issue_id[6:]
    return issue_id


def _readiness_errors(evidence: dict, evidence_status: dict) -> list[str]:
    errors: list[str] = []
    status = evidence.get("status")
    final_decision = evidence.get("final_decision")
    policy_decision = evidence.get("policy_decision")
    changed_files = evidence.get("changed_files", [])
    required_evidence = evidence.get("required_evidence", [])

    if status != "ready_for_merge":
        errors.append("status precisa ser ready_for_merge")
    if final_decision not in {"allowed", "approved_with_human_review"}:
        errors.append("final_decision precisa ser allowed ou approved_with_human_review")
    if not changed_files:
        errors.append("diff precisa estar presente")
    for name in ("test_report", "rollback_plan"):
        if name in required_evidence and evidence_status.get(name) != "present":
            errors.append(f"{name} precisa estar present")
    if (
        policy_decision == "REQUIRE_APPROVAL"
        and evidence_status.get("human_review") != "present"
    ):
        errors.append("human_review precisa estar present para REQUIRE_APPROVAL")
    return errors


def _not_ready_result(
    issue: str,
    status: str,
    final_decision: str,
    reasons: list[str],
) -> dict:
    commands = [
        "devforge policy check --diff",
        f"devforge review --issue {issue}",
        f"devforge evidence --issue {issue}",
    ]
    return {
        "issue_id": issue,
        "status": status,
        "final_decision": final_decision,
        "ready_for_pr": False,
        "pr_body_path": None,
        "commit_plan_path": None,
        "suggested_commit_message": None,
        "suggested_files_to_commit": [],
        "do_not_commit": DO_NOT_COMMIT,
        "next_step": "Run: " + " && ".join(commands),
        "reasons": reasons,
        "required_previous_commands": commands,
    }


def _first_existing_rel(base: Path, candidates: list[Path]) -> str | None:
    for path in candidates:
        if path.exists():
            return str(path.relative_to(base))
    return None


def _allowed_governance_path(path: str) -> bool:
    return path.startswith((
        ".devforge/test-reports/",
        ".devforge/reviews/",
        ".devforge/evidence/",
    ))


def _should_suggest(path: str) -> bool:
    return _allowed_governance_path(path) or not should_ignore_path(path)


def _append_unique(paths: list[str], path: str | None) -> None:
    if path and path not in paths and _should_suggest(path):
        paths.append(path)


def _suggested_files_to_commit(
    evidence: dict,
    spec_path: str | None,
    evidence_paths: dict[str, list[str]],
    evidence_json_rel: str,
    evidence_md_rel: str,
) -> list[str]:
    files: list[str] = []
    evidence_file_set = {
        path
        for paths in evidence_paths.values()
        for path in paths
    }
    for path in evidence.get("changed_files", []):
        if path == spec_path or path in evidence_file_set:
            continue
        _append_unique(files, path)
    _append_unique(files, spec_path)
    for name in ("rollback_plan", "test_report", "human_review"):
        for path in evidence_paths.get(name, []):
            _append_unique(files, path)
    _append_unique(files, evidence_md_rel)
    _append_unique(files, evidence_json_rel)
    return files


def _read_text_if_exists(base: Path, rel_path: str | None) -> str:
    if not rel_path:
        return ""
    path = base / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _spec_title(spec_path: str | None, base: Path) -> str | None:
    text = _read_text_if_exists(base, spec_path)
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _suggest_commit_message(issue: str, spec_path: str | None, base: Path) -> str:
    title = (_spec_title(spec_path, base) or issue).lower()
    if "priority" in title or "prioridade" in title:
        return "feat: add task priority with DevForge evidence"
    if "auth" in title or "login" in title or "rbac" in title:
        return "feat: add auth flow with DevForge evidence"
    return f"feat: complete {issue} with DevForge evidence"


def _suggest_pr_title(issue: str, spec_path: str | None, base: Path) -> str:
    commit_message = _suggest_commit_message(issue, spec_path, base)
    title = commit_message.removeprefix("feat: ").strip()
    return title[:1].upper() + title[1:]


def _spec_summary(spec_path: str | None, base: Path) -> str:
    text = _read_text_if_exists(base, spec_path)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower() in {"## objetivo", "## objective"}:
            for candidate in lines[idx + 1:]:
                stripped = candidate.strip("- ").strip()
                if stripped:
                    if stripped.startswith("## "):
                        break
                    return stripped
    return _spec_title(spec_path, base) or "Change approved by DevForge Evidence Pack."


def _extract_validation_commands(
    base: Path,
    evidence_paths: dict[str, list[str]],
    evidence_md_rel: str,
) -> list[str]:
    commands: list[str] = []
    paths = [*evidence_paths.get("test_report", []), evidence_md_rel]
    for rel_path in paths:
        text = _read_text_if_exists(base, rel_path)
        for raw_line in text.splitlines():
            line = raw_line.strip().strip("`").strip()
            line = line.removeprefix("- ").strip()
            match = _COMMAND_RE.search(line)
            if match:
                command = match.group(0).strip()
                if command not in commands:
                    commands.append(command)
    return commands


def _render_pr_body(
    title: str,
    summary: str,
    evidence: dict,
    policy_check: dict,
    issue: str,
    spec_path: str | None,
    plan_path: str | None,
    evidence_paths: dict[str, list[str]],
    evidence_json_rel: str,
    evidence_md_rel: str,
    validation_commands: list[str],
) -> str:
    reasons = evidence.get("reasons") or policy_check.get("reasons") or []
    baseline = evidence.get("project_prcp_baseline") or policy_check.get("project_prcp_baseline")
    effective = evidence.get("effective_prcp_level") or policy_check.get("effective_prcp_level")
    human_review_paths = evidence_paths.get("human_review", [])

    validation = "\n".join(f"- `{cmd}`" for cmd in validation_commands) or "- No validation commands detected in evidence."
    reasons_md = "\n".join(f"- {reason}" for reason in reasons) or "- none"
    human_review_md = ", ".join(human_review_paths) or "not required"

    return f"""# {title}

## Summary

{summary}

## DevForge Governance

- Issue: {issue}
- Policy decision: {evidence.get("policy_decision")}
- Final decision: {evidence.get("final_decision")}
- Status: {evidence.get("status")}
- Evidence Pack: {evidence_md_rel}
- Evidence Pack JSON: {evidence_json_rel}

## Evidence

- SPEC: {spec_path or "not found"}
- Plan Pack: {plan_path or "not found"}
- Test Report: {", ".join(evidence_paths.get("test_report", [])) or "not required"}
- Rollback Plan: {", ".join(evidence_paths.get("rollback_plan", [])) or "not required"}
- Human Review: {human_review_md}
- Evidence Pack: {evidence_md_rel}

## Risk

- PRCP baseline: {baseline or "unknown"}
- Effective PRCP level: {effective or evidence.get("prcp_level") or "unknown"}

Reasons:
{reasons_md}

## Validation

{validation}

## Checklist Before Merge

- [ ] Confirm changed files match the SPEC scope.
- [ ] Confirm test report evidence is attached when required.
- [ ] Confirm rollback plan is attached when required.
- [ ] Confirm human review is attached when policy requires approval.
- [ ] Attach this PR body and the Evidence Pack to the pull request.
"""


def _render_commit_plan(
    issue: str,
    suggested_files: list[str],
    suggested_commit_message: str,
) -> str:
    files_md = "\n".join(f"- {path}" for path in suggested_files) or "- none"
    do_not_commit_md = "\n".join(f"- {path}" for path in DO_NOT_COMMIT)
    git_add = "git add " + " ".join(suggested_files) if suggested_files else "git add <files>"
    git_commit = f'git commit -m "{suggested_commit_message}"'

    return f"""# Commit Plan — {issue}

## Suggested Files To Commit

{files_md}

## Do Not Commit

{do_not_commit_md}

## Suggested Commit Message

`{suggested_commit_message}`

## Suggested Commands

```bash
{git_add}
{git_commit}
git push -u origin HEAD
```

These commands are suggestions only. `devforge pr-ready` does not run git add, commit or push.
"""


def _emit(result: dict, plain: bool, output_json: bool) -> None:
    if output_json:
        print(json.dumps(result, ensure_ascii=False))
        return

    if not result["ready_for_pr"]:
        print("[DevForge] PR Ready Pack não gerado")
        for reason in result.get("reasons", []):
            print(f"- {reason}")
        print("Run:")
        for command in result.get("required_previous_commands", []):
            print(f"- {command}")
        return

    print("DevForge PR Ready Pack gerado")
    print()
    print("Suggested files to commit:")
    for path in result["suggested_files_to_commit"]:
        print(f"- {path}")
    print()
    print("Do not commit:")
    for path in result["do_not_commit"]:
        print(f"- {path}")
    print()
    print("Suggested commit:")
    print(f'git commit -m "{result["suggested_commit_message"]}"')
    print()
    print("PR body:")
    print(result["pr_body_path"])
