import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.implement import run_implement
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.paths import get_audit_file

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas de um Todo App Flask/SQLite.
## Riscos
- Toca schema SQLite.
"""


def _write_spec(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    return spec


def _setup_planned(tmp_path: Path) -> Path:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    spec = _write_spec(tmp_path)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    return spec


def _write_fake_agent(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-agent.sh"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s' \"$1\" > implemented-prompt.txt\n"
        "printf 'agent ok\\n'\n"
    )
    return fake


def test_implement_fails_without_devforge(tmp_path: Path):
    spec = _write_spec(tmp_path)
    with pytest.raises(SystemExit):
        run_implement(
            spec=str(spec),
            agent="codex",
            command=None,
            yes=False,
            dry_run=True,
            plain=True,
            output_json=False,
            cwd=tmp_path,
        )


def test_implement_fails_without_plan_implementation_brief(tmp_path: Path, capsys):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    spec = _write_spec(tmp_path)
    capsys.readouterr()
    rc = run_implement(
        spec=str(spec),
        agent="codex",
        command=None,
        yes=False,
        dry_run=True,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "devforge plan --spec" in out


def test_implement_dry_run_shows_command_and_does_not_execute(tmp_path: Path, capsys):
    spec = _setup_planned(tmp_path)
    fake = _write_fake_agent(tmp_path)
    capsys.readouterr()
    rc = run_implement(
        spec=str(spec),
        agent="custom",
        command=f"sh {fake.name}",
        yes=False,
        dry_run=True,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "sh fake-agent.sh" in out
    assert "implementation-brief-SPEC-PRIORITY-001.md" in out
    assert not (tmp_path / "implemented-prompt.txt").exists()


def test_implement_json_returns_valid_json(tmp_path: Path, capsys):
    spec = _setup_planned(tmp_path)
    capsys.readouterr()
    rc = run_implement(
        spec=str(spec),
        agent="codex",
        command=None,
        yes=False,
        dry_run=True,
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["spec_id"] == "SPEC-PRIORITY-001"
    assert data["agent"] == "codex"
    assert data["dry_run"] is True
    assert data["next_step"] == "devforge policy check --diff"


def test_implement_yes_executes_fake_command(tmp_path: Path):
    spec = _setup_planned(tmp_path)
    fake = _write_fake_agent(tmp_path)
    rc = run_implement(
        spec=str(spec),
        agent="custom",
        command=f"sh {fake.name}",
        yes=True,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 0
    prompt = (tmp_path / "implemented-prompt.txt").read_text()
    assert "Implemente a feature usando .devforge/context/implementation-brief-SPEC-PRIORITY-001.md" in prompt


def test_implement_records_audit_events(tmp_path: Path):
    spec = _setup_planned(tmp_path)
    fake = _write_fake_agent(tmp_path)
    run_implement(
        spec=str(spec),
        agent="custom",
        command=f"sh {fake.name}",
        yes=True,
        dry_run=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    event_names = [event["event"] for event in events]
    assert "agent.implementation.started" in event_names
    assert "agent.implementation.finished" in event_names
    finished = [event for event in events if event["event"] == "agent.implementation.finished"][-1]
    assert finished["spec_id"] == "SPEC-PRIORITY-001"
    assert finished["exit_code"] == 0


def test_implement_next_step_is_policy_check(tmp_path: Path, capsys):
    spec = _setup_planned(tmp_path)
    capsys.readouterr()
    run_implement(
        spec=str(spec),
        agent="codex",
        command=None,
        yes=False,
        dry_run=True,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert "Next step: devforge policy check --diff" in capsys.readouterr().out
