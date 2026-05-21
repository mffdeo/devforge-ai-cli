"""Evidence recognition by directory + semantic pattern, plus
review_request vs human_review separation."""

import json
from pathlib import Path

from devforge_ai_cli.commands.evidence import run_evidence
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.evidence_rules import (
    check_evidence,
    check_human_review,
    check_review_request,
    check_rollback_plan,
    check_test_report,
)
from devforge_ai_cli.core.paths import get_devforge_dir

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas de um Todo App Flask/SQLite.
## Critérios de aceite
- AC-001: Toda tarefa tem um campo prioridade.
## Riscos
- Toca schema SQLite.
"""


def _setup_priority(tmp_path: Path) -> Path:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    return spec


# ── test_report ───────────────────────────────────────────────────────────────


def test_test_report_recognized_by_devforge_test_reports_md(tmp_path: Path):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "test-reports").mkdir(exist_ok=True)
    (dd / "test-reports" / "SPEC-PRIORITY-001-manual.md").write_text("# manual\n")
    em = check_test_report(tmp_path, dd, spec_id="SPEC-PRIORITY-001")
    assert em.present
    assert em.matched_rule == "strict"
    assert any("test-reports/SPEC-PRIORITY-001-manual.md" in p for p in em.matched_paths)


def test_test_report_missing_lists_expected_paths(tmp_path: Path):
    _setup_priority(tmp_path)
    em = check_test_report(tmp_path, get_devforge_dir(tmp_path), spec_id="SPEC-PRIORITY-001")
    assert not em.present
    assert any(".devforge/test-reports/SPEC-PRIORITY-001-manual.md" in p for p in em.expected_paths)


# ── rollback_plan ─────────────────────────────────────────────────────────────


def test_rollback_plan_recognized_by_docs_rollback_md(tmp_path: Path):
    _setup_priority(tmp_path)
    (tmp_path / "docs" / "rollback").mkdir(parents=True)
    (tmp_path / "docs" / "rollback" / "SPEC-PRIORITY-001.md").write_text("# rollback\n")
    em = check_rollback_plan(tmp_path, get_devforge_dir(tmp_path), spec_id="SPEC-PRIORITY-001")
    assert em.present
    assert em.matched_rule == "strict"
    assert any("docs/rollback/SPEC-PRIORITY-001.md" in p for p in em.matched_paths)


def test_rollback_plan_recognized_by_devforge_rollback_md(tmp_path: Path):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "rollback").mkdir(exist_ok=True)
    (dd / "rollback" / "ROLLBACK-SPEC-PRIORITY-001.md").write_text("# rb\n")
    em = check_rollback_plan(tmp_path, dd, spec_id="SPEC-PRIORITY-001")
    assert em.present
    assert em.matched_rule == "strict"


# ── human_review vs review_request ────────────────────────────────────────────


def test_human_review_not_satisfied_by_generic_review_file(tmp_path: Path):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    # An agent-written file with no HUMAN-REVIEW prefix
    (dd / "reviews" / "SPEC-PRIORITY-001-review.md").write_text("# agent review request\n")
    em = check_human_review(tmp_path, dd, spec_id="SPEC-PRIORITY-001")
    assert not em.present
    assert em.matched_rule == "missing"
    # The file is surfaced as evidence that *a* review file exists,
    # but the rule did not accept it as approval.
    assert any("SPEC-PRIORITY-001-review.md" in p for p in em.matched_paths)


def test_review_request_picks_up_generic_review_file(tmp_path: Path):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "SPEC-PRIORITY-001-review.md").write_text("# agent review request\n")
    rr = check_review_request(tmp_path, dd)
    assert rr.present
    assert any("SPEC-PRIORITY-001-review.md" in p for p in rr.matched_paths)


def test_human_review_accepted_with_explicit_prefix(tmp_path: Path):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").write_text("Approved by maintainer\n")
    em = check_human_review(tmp_path, dd, spec_id="SPEC-PRIORITY-001")
    assert em.present
    assert em.matched_rule == "strict"


# ── policy check shows expected paths when human_review is missing ────────────


def test_policy_check_plain_shows_expected_paths_for_missing_evidence(
    tmp_path: Path, capsys
):
    _setup_priority(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
        changed_files_override=["app.py"],
        diff_content_override="",
    )
    out = capsys.readouterr().out
    assert "human_review: missing" in out
    assert ".devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md" in out


def test_policy_check_json_exposes_evidence_details_and_review_request(
    tmp_path: Path, capsys
):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "SPEC-PRIORITY-001-review.md").write_text("agent request\n")
    capsys.readouterr()
    run_policy_check(
        diff=False,
        plain=False,
        output_json=True,
        cwd=tmp_path,
        changed_files_override=["app.py"],
        diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert "evidence_details" in data
    hr = data["evidence_details"]["human_review"]
    assert hr["status"] == "missing"
    assert any(
        ".devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md" in p
        for p in hr["expected_paths"]
    )
    assert data["review_request_present"] is True


# ── evidence command exposes matched_paths and matched_rule ──────────────────


def test_evidence_recognizes_natural_paths_end_to_end(tmp_path: Path, capsys):
    # Plant DB signal so policy_check engine elevates and asks for rollback_plan
    (tmp_path / "db_create.py").write_text(
        "import sqlite3\nsqlite3.connect('todo.db')\nconn.execute('CREATE TABLE x(id INT)')\n"
    )
    spec = _setup_priority(tmp_path)
    # Drop evidences in the natural locations the agent would use:
    dd = get_devforge_dir(tmp_path)
    (dd / "test-reports").mkdir(exist_ok=True)
    (dd / "test-reports" / "SPEC-PRIORITY-001-manual.md").write_text("# manual\n")
    (tmp_path / "docs" / "rollback").mkdir(parents=True)
    (tmp_path / "docs" / "rollback" / "SPEC-PRIORITY-001.md").write_text("# rb\n")
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").write_text("Approved\n")

    # Run policy check to refresh the latest snapshot. Diff content carries
    # 'CREATE TABLE' so the engine sets db_migration_detected and requires
    # rollback_plan.
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py", "db_create.py"],
        diff_content_override="--- a/db_create.py\n+++ b/db_create.py\n+CREATE TABLE tasks (id INT);\n",
    )

    capsys.readouterr()
    rc = run_evidence(
        issue="ISSUE-PRIORITY-001",
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    out = capsys.readouterr().out
    data = json.loads(out)
    details = data["evidence_details"]
    assert details["test_report"]["status"] == "present"
    assert details["test_report"]["matched_rule"] == "strict"
    assert any(
        ".devforge/test-reports/SPEC-PRIORITY-001-manual.md" in p
        for p in details["test_report"]["matched_paths"]
    )
    assert details["rollback_plan"]["status"] == "present"
    assert any(
        "docs/rollback/SPEC-PRIORITY-001.md" in p
        for p in details["rollback_plan"]["matched_paths"]
    )
    assert details["human_review"]["status"] == "present"
    assert details["human_review"]["matched_rule"] == "strict"
    # REQUIRE_APPROVAL is satisfied when all required evidence, including
    # human_review, is present.
    assert rc == 0
    assert data["status"] == "ready_for_merge"
    assert data["final_decision"] == "approved_with_human_review"
    # spec is used by linter; touch it
    assert spec.exists()


# ── implementation-brief includes expected paths per evidence ────────────────


def test_implementation_brief_includes_expected_paths_per_evidence(tmp_path: Path):
    _setup_priority(tmp_path)
    brief = (
        tmp_path / ".devforge" / "context" / "implementation-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert ".devforge/test-reports/SPEC-PRIORITY-001-manual.md" in brief
    assert "docs/rollback/SPEC-PRIORITY-001.md" in brief
    assert ".devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md" in brief


# ── policy_check: dynamic issue id and recommended actions ───────────────────


def test_policy_check_does_not_hardcode_issue_auth_001(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert "ISSUE-AUTH-001" not in data["next_step"]
    assert not any("ISSUE-AUTH-001" in a for a in data["recommended_actions"])
    assert data["evidence_issue_id"] == "SPEC-PRIORITY-001"


def test_policy_check_next_step_uses_current_spec_id(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert data["next_step"] == "devforge evidence --issue SPEC-PRIORITY-001"
    assert any(
        "devforge evidence --issue SPEC-PRIORITY-001" in a
        for a in data["recommended_actions"]
    )


def test_policy_check_omits_test_report_action_when_present(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "test-reports").mkdir(exist_ok=True)
    (dd / "test-reports" / "SPEC-PRIORITY-001-manual.md").write_text("# manual\n")
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions = " | ".join(data["recommended_actions"])
    assert "test_report" not in actions
    assert "Rodar testes" not in actions


def test_policy_check_omits_rollback_action_when_present(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    # Plant rollback so it counts as present
    (tmp_path / "docs" / "rollback").mkdir(parents=True)
    (tmp_path / "docs" / "rollback" / "SPEC-PRIORITY-001.md").write_text("# rb\n")
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py", "db_create.py"],
        diff_content_override="--- a/db_create.py\n+++ b/db_create.py\n+CREATE TABLE x(id INT);\n",
    )
    data = json.loads(capsys.readouterr().out)
    actions = " | ".join(data["recommended_actions"])
    assert "rollback_plan" not in actions
    assert "Criar rollback plan" not in actions


def test_policy_check_includes_human_review_action_when_missing(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions = " | ".join(data["recommended_actions"])
    # Should now point at the guided review command, not the bare "Solicitar"
    assert "devforge review --issue SPEC-PRIORITY-001" in actions
    assert "Solicitar revisão humana" not in actions


def test_policy_check_omits_human_review_action_when_present(tmp_path: Path, capsys):
    _setup_priority(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").write_text("Approved\n")
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions = " | ".join(data["recommended_actions"])
    assert "Solicitar revisão humana" not in actions
    assert "devforge review --issue" not in actions
    # And the only remaining action is the evidence pack
    assert any("devforge evidence --issue SPEC-PRIORITY-001" in a for a in data["recommended_actions"])


# ── check_evidence dispatcher ────────────────────────────────────────────────


def test_check_evidence_dispatches_audit_log(tmp_path: Path):
    _setup_priority(tmp_path)
    em = check_evidence("audit_log", tmp_path, get_devforge_dir(tmp_path))
    assert em.present
    assert em.matched_rule == "strict"
