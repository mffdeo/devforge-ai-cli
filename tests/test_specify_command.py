import json
import re
from pathlib import Path

from typer.testing import CliRunner

from devforge_ai_cli.cli import app
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.specify import run_specify
from devforge_ai_cli.core.paths import get_audit_file
from devforge_ai_cli.core.scanner import run_scan

PRIORITY_IDEA = "Permitir que cada tarefa tenha prioridade Baixa, Média ou Alta"


def _init(tmp_path: Path) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)


def _normalize_cli_output(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"[╭╮╰╯─│]", " ", text)
    return " ".join(text.split())


def test_specify_creates_priority_spec_from_idea(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    spec = tmp_path / "specs" / "SPEC-PRIORITY-001.md"
    assert spec.exists()
    content = spec.read_text()
    assert "# SPEC-PRIORITY-001 — Prioridade em tarefas" in content
    assert "Status: Draft" in content
    assert "Requirement Traceability" in content


def test_specify_creates_specification_brief(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    brief = tmp_path / ".devforge" / "context" / "specification-brief-SPEC-PRIORITY-001.md"
    assert brief.exists()
    content = brief.read_text()
    assert "Original idea" in content
    assert PRIORITY_IDEA in content
    assert "devforge plan --spec specs/SPEC-PRIORITY-001.md" in content


def test_specify_uses_project_profile_json(tmp_path: Path):
    _init(tmp_path)
    (tmp_path / "calculator.py").write_text("print(1 + 1)\n")
    run_scan("calculator", tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    content = (
        tmp_path / ".devforge" / "context" / "specification-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert "Project Profile Context" in content
    assert "project_type: python_cli" in content


def test_specify_json_returns_spec_path_and_next_step(tmp_path: Path, capsys):
    _init(tmp_path)
    capsys.readouterr()
    rc = run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["spec_path"] == "specs/SPEC-PRIORITY-001.md"
    assert data["status"] == "Draft"
    assert data["approved"] is False
    assert data["gray_areas_status"] == "unresolved"
    assert data["next_step"] == "devforge specify --spec specs/SPEC-PRIORITY-001.md --interactive"
    assert data["next_steps"] == [
        "devforge specify --spec specs/SPEC-PRIORITY-001.md --interactive",
        "devforge specify --spec specs/SPEC-PRIORITY-001.md --approve",
        "devforge plan --spec specs/SPEC-PRIORITY-001.md",
    ]
    assert data["dry_run"] is False


def test_specify_dry_run_does_not_write_files(tmp_path: Path):
    _init(tmp_path)
    rc = run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=True,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 0
    assert not (tmp_path / "specs" / "SPEC-PRIORITY-001.md").exists()
    assert not (
        tmp_path / ".devforge" / "context" / "specification-brief-SPEC-PRIORITY-001.md"
    ).exists()


def test_specify_approve_marks_status_approved(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=True,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    content = (tmp_path / "specs" / "SPEC-PRIORITY-001.md").read_text()
    assert "Status: Approved" in content


def test_specify_without_approve_marks_status_draft(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    content = (tmp_path / "specs" / "SPEC-PRIORITY-001.md").read_text()
    assert "Status: Draft" in content


def test_specify_records_audit_event(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    assert "spec.generated" in [event["event"] for event in events]


def test_specify_approve_records_audit_event(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=True,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    assert "spec.approved" in [event["event"] for event in events]


def test_specify_plain_output(tmp_path: Path, capsys):
    _init(tmp_path)
    capsys.readouterr()
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert "[DevForge] Specify" in out
    assert "spec_id: SPEC-PRIORITY-001" in out
    assert "status: Draft" in out
    assert "gray_areas_status: unresolved" in out
    assert "SPEC gerada como Draft." in out
    assert "Existem gray areas para revisar antes do planejamento." in out
    assert "devforge specify --spec specs/SPEC-PRIORITY-001.md --interactive" in out
    assert "devforge specify --spec specs/SPEC-PRIORITY-001.md --approve" in out
    assert "After approval:" in out
    assert "devforge plan --spec specs/SPEC-PRIORITY-001.md" in out


def test_specify_idea_with_gray_areas_does_not_recommend_plan_as_only_next_step(
    tmp_path: Path,
    capsys,
):
    _init(tmp_path)
    capsys.readouterr()
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert "Next steps:" in out
    assert "Next step:\ndevforge plan" not in out
    assert "Resolve gray areas:" in out


def test_specify_existing_spec_approve_marks_status_approved(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    run_specify(
        idea=None,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=True,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        spec="specs/SPEC-PRIORITY-001.md",
        cwd=tmp_path,
    )
    content = (tmp_path / "specs" / "SPEC-PRIORITY-001.md").read_text()
    assert "Status: Approved" in content


def test_specify_existing_spec_approve_records_audit_event(tmp_path: Path):
    _init(tmp_path)
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    run_specify(
        idea=None,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=False,
        approve=True,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        spec="specs/SPEC-PRIORITY-001.md",
        cwd=tmp_path,
    )
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    approved = [event for event in events if event["event"] == "spec.approved"]
    assert approved
    assert approved[-1]["spec_id"] == "SPEC-PRIORITY-001"


def test_specify_idea_interactive_records_clarified_decisions(
    tmp_path: Path,
    monkeypatch,
):
    _init(tmp_path)
    answers = iter([
        "Prioridades fixas.",
        "Sim, fora do MVP.",
        "Sim, fora do MVP.",
        "Sim, Média.",
        "n",
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=True,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    spec_content = (tmp_path / "specs" / "SPEC-PRIORITY-001.md").read_text()
    brief_content = (
        tmp_path / ".devforge" / "context" / "specification-brief-SPEC-PRIORITY-001.md"
    ).read_text()
    assert "Status: Draft" in spec_content
    assert "## Clarified Decisions" in spec_content
    assert "Prioridades fixas." in brief_content


def test_specify_idea_interactive_allows_approval_at_end(
    tmp_path: Path,
    monkeypatch,
):
    _init(tmp_path)
    answers = iter([
        "Prioridades fixas.",
        "Sim, fora do MVP.",
        "Sim, fora do MVP.",
        "Sim, Média.",
        "y",
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="none",
        command=None,
        interactive=True,
        approve=False,
        yes=False,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    content = (tmp_path / "specs" / "SPEC-PRIORITY-001.md").read_text()
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    assert "Status: Approved" in content
    assert "spec.approved" in [event["event"] for event in events]


def test_specify_help_is_registered():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    output = _normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "specify" in output


def test_specify_dry_run_with_custom_agent_does_not_execute(tmp_path: Path):
    _init(tmp_path)
    rc = run_specify(
        idea=PRIORITY_IDEA,
        title=None,
        spec_id=None,
        agent="custom",
        command="echo",
        interactive=False,
        approve=False,
        yes=False,
        dry_run=True,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 0
    assert not (tmp_path / "specs" / "SPEC-PRIORITY-001.md").exists()
