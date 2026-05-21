"""Centralized exclusion rules + agent-instructions.md generation."""

import json
from pathlib import Path

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.ignore import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_SUFFIXES,
    should_ignore_path,
)
from devforge_ai_cli.evidence.collector import collect_evidence

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas de um Todo App Flask/SQLite.
## Riscos
- Toca schema SQLite (CREATE TABLE / ALTER TABLE).
"""


# ── should_ignore_path ───────────────────────────────────────────────────────


def test_should_ignore_path_defaults_loaded():
    assert ".venv" in DEFAULT_EXCLUDED_DIRS
    assert ".devforge" in DEFAULT_EXCLUDED_DIRS
    assert ".db" in DEFAULT_EXCLUDED_SUFFIXES


def test_should_ignore_path_accepts_str_and_path():
    assert should_ignore_path(".venv/lib/python3.12/site-packages/foo.py") is True
    assert should_ignore_path(Path(".venv/bin/python")) is True


def test_should_ignore_path_normalizes_windows_separators():
    assert should_ignore_path(".venv\\Lib\\site-packages\\foo.py") is True


def test_should_ignore_path_segment_match_not_substring():
    # 'envelope/foo.py' must NOT be ignored just because 'env' is excluded.
    assert should_ignore_path("envelope/foo.py") is False


def test_should_ignore_path_suffix_matching():
    assert should_ignore_path("data/todo.db") is True
    assert should_ignore_path("data/todo.sqlite") is True
    assert should_ignore_path("module.pyc") is True


def test_should_ignore_path_keeps_application_files():
    for ok in ("app.py", "db_create.py", "templates/index.html", "tests/test_app.py"):
        assert should_ignore_path(ok) is False


# ── scan ignores .venv / .devforge but still sees .sqlite files ─────────────


def test_scan_ignores_venv_directory(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    venv_pkg = tmp_path / ".venv" / "lib" / "python3.12" / "site-packages"
    venv_pkg.mkdir(parents=True)
    (venv_pkg / "auth.py").write_text("def login(): pass\n")
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    profile = json.loads(
        (tmp_path / ".devforge" / "prcp" / "project-profile.json").read_text()
    )
    assert "auth" not in profile["sensitive_areas"]


def test_scan_ignores_devforge_directory(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    # Plant a misleading file inside .devforge/audit/ — must not pollute scan.
    (tmp_path / ".devforge" / "audit" / "login.py").write_text("def auth(): pass\n")
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    profile = json.loads(
        (tmp_path / ".devforge" / "prcp" / "project-profile.json").read_text()
    )
    assert "auth" not in profile["sensitive_areas"]


# ── git.get_changed_files filters via should_ignore_path ────────────────────


def test_get_changed_files_filters_ignored(monkeypatch, tmp_path: Path):
    import devforge_ai_cli.core.git as gitmod

    class _R:
        def __init__(self, out: str):
            self.returncode = 0
            self.stdout = out

    def fake_run(args, **kwargs):
        if args[:3] == ["git", "diff", "--name-only"]:
            return _R("app.py\n.venv/bin/python\n")
        if args[:4] == ["git", "diff", "--cached", "--name-only"]:
            return _R(".devforge/policy/POLICY-CHECK-LATEST.json\n")
        if args[:3] == ["git", "status", "--porcelain"]:
            return _R("?? todo.db\n?? db_create.py\n")
        return _R("")

    monkeypatch.setattr(gitmod.subprocess, "run", fake_run)
    files = gitmod.get_changed_files(tmp_path)

    assert "app.py" in files
    assert "db_create.py" in files
    assert ".venv/bin/python" not in files
    assert ".devforge/policy/POLICY-CHECK-LATEST.json" not in files
    assert "todo.db" not in files


# ── policy check honors filtering ───────────────────────────────────────────


def _setup_priority_plan(tmp_path: Path) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)


def test_policy_check_ignores_venv_and_devforge_in_override(tmp_path: Path, capsys):
    _setup_priority_plan(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False,
        plain=False,
        output_json=True,
        cwd=tmp_path,
        changed_files_override=[
            "app.py",
            "db_create.py",
            "templates/index.html",
            ".venv/bin/python",
            ".venv/lib/python3.12/site-packages/flask/app.py",
            ".devforge/policy/POLICY-CHECK-LATEST.json",
            ".devforge/audit/audit.ndjson",
            "todo.db",
            "instance/site.sqlite3",
            "module.pyc",
        ],
        diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    cf = set(data["changed_files"])
    assert "app.py" in cf
    assert "db_create.py" in cf
    assert "templates/index.html" in cf
    for ignored in (
        ".venv/bin/python",
        ".venv/lib/python3.12/site-packages/flask/app.py",
        ".devforge/policy/POLICY-CHECK-LATEST.json",
        ".devforge/audit/audit.ndjson",
        "todo.db",
        "instance/site.sqlite3",
        "module.pyc",
    ):
        assert ignored not in cf, f"deveria ter sido ignorado: {ignored}"


# ── evidence does not pull .venv/.devforge into changed_files ────────────────


def test_evidence_does_not_include_venv_in_changed_files(tmp_path: Path):
    _setup_priority_plan(tmp_path)
    # Run a policy check with mixed files. Filtering happens in policy_check
    # before changed_files is recorded; evidence then reads that snapshot.
    run_policy_check(
        diff=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
        changed_files_override=["app.py", ".venv/bin/python", "todo.db"],
        diff_content_override="",
    )
    latest = json.loads(
        (tmp_path / ".devforge" / "policy" / "POLICY-CHECK-LATEST.json").read_text()
    )
    payload = collect_evidence("ISSUE-PRIORITY-001", latest, tmp_path)
    cf = set(payload["changed_files"])
    assert "app.py" in cf
    assert ".venv/bin/python" not in cf
    assert "todo.db" not in cf


# ── agent-instructions.md ───────────────────────────────────────────────────


def _agent_md(tmp_path: Path) -> str:
    return (tmp_path / ".devforge" / "context" / "agent-instructions.md").read_text(
        encoding="utf-8"
    )


def test_init_creates_agent_instructions(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    p = tmp_path / ".devforge" / "context" / "agent-instructions.md"
    assert p.exists()


def test_agent_instructions_lists_venv_as_forbidden_context(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    md = _agent_md(tmp_path)
    assert "`.venv/`" in md
    assert "Do not scan or use as source context" in md


def test_agent_instructions_allows_venv_bin_python_for_execution(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    md = _agent_md(tmp_path)
    assert "Execution exception" in md
    assert ".venv/bin/python" in md


def test_agent_instructions_allows_reading_devforge_plans_context_policy(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    md = _agent_md(tmp_path)
    # Both in "Allowed context" and the dedicated "DevForge artifacts" block
    assert "`.devforge/plans/`" in md
    assert "`.devforge/context/`" in md
    assert "`.devforge/policy/`" in md


def test_agent_instructions_forbids_treating_audit_evidence_prcp_as_code(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    md = _agent_md(tmp_path)
    assert "`.devforge/audit/`" in md
    assert "`.devforge/evidence/`" in md
    assert "`.devforge/prcp/`" in md
    assert "must not treat these as application code" in md


def test_plan_updates_agent_instructions_with_spec_and_policy(tmp_path: Path):
    _setup_priority_plan(tmp_path)
    md = _agent_md(tmp_path)
    assert "Current SPEC context" in md
    assert "SPEC-PRIORITY-001" in md
    assert "REQUIRE_APPROVAL" in md
    assert "Hardened" in md
    # Recommended scope copied from plan tasks
    assert "Adicionar campo de prioridade ao schema SQLite" in md
