"""Project PRCP baseline vs SPEC-effective PRCP level + agent anti-impersonation
notice in implementation-brief / review-brief."""

import json
from pathlib import Path

from devforge_ai_cli.commands.evidence import run_evidence
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.review import run_review
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.paths import get_devforge_dir

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas de um Todo App Flask/SQLite.
## Riscos
- Toca schema SQLite (CREATE TABLE / ALTER TABLE).
"""


def _setup_db_touching_spec(tmp_path: Path) -> None:
    """Scan baseline stays Standard (project tem só Flask), mas o plan eleva
    para Hardened porque a SPEC toca schema."""
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="todo"\ndependencies = ["flask"]\n'
    )
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)


# ── plan elevates effective; scan baseline stays ────────────────────────────


def test_scan_baseline_stays_standard_while_plan_applies_hardened(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    dd = get_devforge_dir(tmp_path)
    profile = json.loads((dd / "prcp" / "project-profile.json").read_text())
    pol = json.loads((dd / "policy" / "POLICY-DECISION-SPEC-PRIORITY-001.json").read_text())
    # scan baseline is Standard for a plain Flask project
    assert profile["prcp"]["task_elevation"] == "Standard"
    # plan applies Hardened because the SPEC itself touches schema
    assert pol["prcp_level"] == "Hardened"


# ── policy_check exposes both ────────────────────────────────────────────────


def test_policy_check_json_separates_baseline_and_effective(tmp_path: Path, capsys):
    _setup_db_touching_spec(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert data["project_prcp_baseline"] == "Standard"
    assert data["effective_prcp_level"] == "Hardened"


def test_policy_check_latest_json_persists_both_prcp_fields(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    latest = json.loads(
        (get_devforge_dir(tmp_path) / "policy" / "POLICY-CHECK-LATEST.json").read_text()
    )
    assert latest["project_prcp_baseline"] == "Standard"
    assert latest["effective_prcp_level"] == "Hardened"


# ── review brief shows both ─────────────────────────────────────────────────


def test_review_brief_distinguishes_baseline_and_effective(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    brief = (
        get_devforge_dir(tmp_path)
        / "context"
        / "review-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert "**Project PRCP baseline:** `Standard`" in brief
    assert "**Effective PRCP for this SPEC:** `Hardened`" in brief
    # The brief MUST NOT advertise plain Standard alone for a Hardened SPEC
    assert "PRCP level: Standard" not in brief


# ── evidence pack registers both ────────────────────────────────────────────


def test_evidence_pack_records_both_prcp_levels(tmp_path: Path, capsys):
    _setup_db_touching_spec(tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    capsys.readouterr()
    run_evidence(
        issue="ISSUE-PRIORITY-001",
        plain=False, output_json=True, cwd=tmp_path,
    )
    payload_lines = capsys.readouterr().out
    # run_evidence might return non-zero exit; we only need the JSON
    data = json.loads(payload_lines)
    # the collector copies both, even though the public JSON keeps only prcp_level
    # for backwards compat — inspect the EVID-*.json on disk instead.
    evid = json.loads(
        (get_devforge_dir(tmp_path) / "evidence" / "EVID-ISSUE-PRIORITY-001.json").read_text()
    )
    assert evid["effective_prcp_level"] == "Hardened"
    assert evid["project_prcp_baseline"] == "Standard"
    assert data["evidence_id"] == "EVID-ISSUE-PRIORITY-001"


# ── anti-impersonation notice ───────────────────────────────────────────────


def test_implementation_brief_warns_against_creating_human_review(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    brief = (
        get_devforge_dir(tmp_path) / "context" / "implementation-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert "Sobre revisão humana" in brief
    assert (
        "agente **não** deve criar `.devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md`"
        in brief
    )
    assert (
        "exclusivamente por\n  `devforge review --issue SPEC-PRIORITY-001`"
        in brief
    )
    assert "AI-REVIEW-NOTES-SPEC-PRIORITY-001.md" in brief
    assert "REVIEW-REQUEST-SPEC-PRIORITY-001.md" in brief


def test_review_brief_warns_against_creating_human_review(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    brief = (
        get_devforge_dir(tmp_path)
        / "context"
        / "review-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert "Não criar `.devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md`" in brief
    assert "AI-REVIEW-NOTES-SPEC-PRIORITY-001.md" in brief
    assert "REVIEW-REQUEST-SPEC-PRIORITY-001.md" in brief


# ── full flow stays green ────────────────────────────────────────────────────


def test_full_flow_with_dual_prcp_remains_green(tmp_path: Path):
    _setup_db_touching_spec(tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    rc = run_evidence(
        issue="ISSUE-PRIORITY-001",
        plain=True, output_json=False, cwd=tmp_path,
    )
    # Evidence still exits 1 because REQUIRE_APPROVAL + missing test_report/rollback
    assert rc in (0, 1)
    # All artifacts exist
    dd = get_devforge_dir(tmp_path)
    assert (dd / "plans" / "PLAN-SPEC-PRIORITY-001.md").exists()
    assert (dd / "policy" / "POLICY-DECISION-SPEC-PRIORITY-001.json").exists()
    assert (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").exists()
    assert (dd / "evidence" / "EVID-ISSUE-PRIORITY-001.json").exists()
