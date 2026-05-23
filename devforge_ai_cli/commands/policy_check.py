import json
from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.evidence_rules import (
    check_review_request,
    evaluate_required_evidence,
)
from devforge_ai_cli.core.git import (
    filter_ignored_diff_content,
    get_changed_files,
    get_diff_content,
)
from devforge_ai_cli.core.ignore import should_ignore_path
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init
from devforge_ai_cli.core.review_brief import (
    render_review_brief,
    suggested_ai_review_prompt,
)
from devforge_ai_cli.policy_engine.engine import evaluate_policy


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
        diff_content = filter_ignored_diff_content(get_diff_content(base))
    else:
        changed_files = []
        diff_content = ""

    result = evaluate_policy(
        changed_files=changed_files,
        diff_content=diff_content,
        profile=profile,
        existing_policy=existing_policy,
    )

    spec_id = existing_policy.get("spec_id")
    # The issue id used by `devforge evidence --issue` defaults to the
    # current SPEC id, so we never echo back a stale ISSUE-AUTH-001.
    evidence_issue_id = spec_id or "<ISSUE-ID>"
    matches = evaluate_required_evidence(
        result["required_evidence"], base, devforge_dir, spec_id=spec_id
    )
    evidence_status = {name: m.status for name, m in matches.items()}
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
    missing_evidence = [k for k, v in evidence_status.items() if v == "missing"]

    review_request = check_review_request(base, devforge_dir)

    # PRCP separation (see the longer comment near the payload below).
    project_prcp_baseline = profile.get("prcp", {}).get("task_elevation", "Standard")
    effective_prcp_level = existing_policy.get("prcp_level", project_prcp_baseline)
    prcp_level = effective_prcp_level  # used by Rich renderer and audit

    # ── review brief for AI-assisted review ─────────────────────────────────
    review_brief_relpath: str | None = None
    ai_review_prompt: str | None = None
    human_review_missing = (
        result["decision"] == "REQUIRE_APPROVAL"
        and "human_review" in result["required_evidence"]
        and evidence_status.get("human_review") == "missing"
        and spec_id is not None
    )
    if human_review_missing:
        brief_pc = {
            **result,
            "evidence_status": evidence_status,
            "evidence_details": evidence_details,
            "review_request_paths": review_request.matched_paths,
            "prcp_level": effective_prcp_level,
            "project_prcp_baseline": project_prcp_baseline,
            "effective_prcp_level": effective_prcp_level,
        }
        brief_path = render_review_brief(base, spec_id, brief_pc)
        review_brief_relpath = str(brief_path.relative_to(base))
        ai_review_prompt = suggested_ai_review_prompt(spec_id)

    # Rebuild recommended_actions so we only suggest evidences that are
    # still missing. The engine emits the generic list per required item;
    # we drop items already present, point human_review at the guided
    # review flow (AI-assisted review + devforge review), and append a
    # SPEC-specific evidence command at the end.
    recommended: list[str] = []
    if "test_report" in result["required_evidence"] and evidence_status.get("test_report") == "missing":
        recommended.append("Rodar testes e anexar test_report")
    if "rollback_plan" in result["required_evidence"] and evidence_status.get("rollback_plan") == "missing":
        recommended.append("Criar rollback plan")
    if human_review_missing:
        recommended.append(f"Revisão assistida: peça a uma IA: \"{ai_review_prompt}\"")
        recommended.append(f"Registrar revisão humana: devforge review --issue {evidence_issue_id}")
    recommended.append(f"Gerar evidence pack: devforge evidence --issue {evidence_issue_id}")
    result["recommended_actions"] = recommended

    timestamp = datetime.now(timezone.utc).isoformat()
    # PRCP separation:
    #   project_prcp_baseline = task_elevation as decided by `devforge scan`
    #   effective_prcp_level  = PRCP applied by `devforge plan` for this SPEC
    #                           (it can be higher than the project baseline
    #                            when the SPEC itself touches a database).
    # `prcp_level` keeps existing call sites working and now points at the
    # effective value — never at the baseline alone.
    # (computed earlier so the review brief uses the same numbers)
    policy_source = str(existing_policy_files[0].relative_to(base)) if existing_policy_files else None

    payload = {
        **result,
        "evidence_status": evidence_status,
        "evidence_details": evidence_details,
        "missing_evidence": missing_evidence,
        "review_request_present": review_request.present,
        "review_request_paths": review_request.matched_paths,
        "review_brief_path": review_brief_relpath,
        "suggested_ai_review_prompt": ai_review_prompt,
        "policy_source": policy_source,
        "project_prcp_baseline": project_prcp_baseline,
        "effective_prcp_level": effective_prcp_level,
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
            "evidence_details": evidence_details,
            "review_request_present": review_request.present,
            "review_request_paths": review_request.matched_paths,
            "review_brief_path": review_brief_relpath,
            "suggested_ai_review_prompt": ai_review_prompt,
            "recommended_actions": result["recommended_actions"],
            "generated_files": generated_files,
            "evidence_issue_id": evidence_issue_id,
            "project_prcp_baseline": project_prcp_baseline,
            "effective_prcp_level": effective_prcp_level,
            "next_step": f"devforge evidence --issue {evidence_issue_id}",
        }))
    elif plain:
        print(f"[DevForge] Decision: {result['decision']}")
        print(f"Pode avançar agora? {'Sim' if result['can_advance_now'] else 'Não ainda'}")
        print(f"Arquivos analisados: {result['files_count']}")
        for r in result["reasons"]:
            print(f"  - {r}")
        for ev in result["required_evidence"]:
            detail = evidence_details.get(ev, {})
            status = detail.get("status", "unknown")
            if status == "present":
                paths = ", ".join(detail.get("matched_paths") or [])
                rule = detail.get("matched_rule", "")
                print(f"  - {ev}: present [{rule}] → {paths}")
            else:
                expected = ", ".join(detail.get("expected_paths") or [])
                print(f"  - {ev}: missing — esperado em: {expected}")
                for note in detail.get("notes", []):
                    print(f"      note: {note}")
        if review_request.present and "human_review" in result["required_evidence"]:
            print(
                f"  - review_request: present → {', '.join(review_request.matched_paths)} "
                "(não substitui human_review aprovado)"
            )
        if result["recommended_actions"]:
            print("Recommended actions:")
            for action in result["recommended_actions"]:
                print(f"  - {action}")
        print(f"Next step: devforge evidence --issue {evidence_issue_id}")
        print(f"Exit code: {result['exit_code']}")
    else:
        from devforge_ai_cli.ui.renderers.policy_screen import render_policy
        render_policy(
            result, evidence_status, result["files_count"], prcp_level, timestamp,
            evidence_issue_id=evidence_issue_id,
        )

    return result["exit_code"]
