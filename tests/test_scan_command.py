import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.scanner import (
    _detect_database_signals,
    _detect_sensitive_areas,
    _detect_stack,
    run_scan,
)


def _init(tmp_path: Path) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)


# ── require init ──────────────────────────────────────────────────────────────

def test_scan_requires_init(tmp_path):
    with pytest.raises(SystemExit):
        run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)


# ── file generation ───────────────────────────────────────────────────────────

def test_scan_generates_project_profile(tmp_path):
    _init(tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    assert (tmp_path / ".devforge" / "prcp" / "project-profile.json").exists()


def test_scan_generates_scan_report(tmp_path):
    _init(tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    assert (tmp_path / ".devforge" / "prcp" / "scan-report.md").exists()


def test_scan_records_audit_event(tmp_path):
    _init(tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    scan_events = [e for e in events if e["event"] == "scan.completed"]
    assert len(scan_events) == 1
    assert "baseline_level" in scan_events[0]


# ── stack detection ───────────────────────────────────────────────────────────

def test_scan_detects_node_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"test","dependencies":{}}')
    stack, _, _ = _detect_stack(tmp_path)
    assert "Node" in stack


def test_scan_detects_typescript_from_tsconfig(tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}")
    stack, _, _ = _detect_stack(tmp_path)
    assert "TypeScript" in stack


def test_scan_detects_nextjs_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies":{"next":"^14.0.0"}}')
    stack, _, _ = _detect_stack(tmp_path)
    assert any("Next.js" in s for s in stack)


def test_scan_detects_python_from_pyproject_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-app"\n')
    stack, _, _ = _detect_stack(tmp_path)
    assert "Python" in stack


def test_scan_detects_fastapi(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    stack, _, _ = _detect_stack(tmp_path)
    assert "FastAPI" in stack


def test_scan_detects_github_actions_as_ci(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI")
    _, ci, _ = _detect_stack(tmp_path)
    assert ci == "GitHub Actions"


# ── sensitive area detection ──────────────────────────────────────────────────

def test_scan_detects_auth_by_path(tmp_path):
    (tmp_path / "auth.py").write_text("# auth module")
    areas = _detect_sensitive_areas(tmp_path)
    assert "auth" in areas


def test_scan_detects_login_by_content(tmp_path):
    (tmp_path / "routes.py").write_text("def login_user(): pass")
    areas = _detect_sensitive_areas(tmp_path)
    assert "login" in areas


def test_scan_detects_db_create_py_as_database_signal(tmp_path):
    (tmp_path / "db_create.py").write_text("# nothing useful here")
    _, extra_areas = _detect_database_signals(tmp_path)
    assert "database" in extra_areas


def test_scan_detects_sqlite_content(tmp_path):
    (tmp_path / "app.py").write_text(
        "import sqlite3\n"
        "conn = sqlite3.connect('todo.db')\n"
    )
    extra_db, extra_areas = _detect_database_signals(tmp_path)
    assert "database" in extra_areas
    assert "sqlite" in extra_areas
    assert "SQLite" in extra_db


def test_scan_detects_create_table_in_schema_sql(tmp_path):
    (tmp_path / "schema.sql").write_text(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);\n"
    )
    _, extra_areas = _detect_database_signals(tmp_path)
    assert "database" in extra_areas
    assert "schema" in extra_areas


def test_scan_detects_alembic_directory(tmp_path):
    (tmp_path / "alembic").mkdir()
    _, extra_areas = _detect_database_signals(tmp_path)
    assert "database" in extra_areas


def test_scan_detects_sqlite_file_suffix(tmp_path):
    (tmp_path / "todo.sqlite3").write_text("")
    extra_db, extra_areas = _detect_database_signals(tmp_path)
    assert "database" in extra_areas
    assert "sqlite" in extra_areas
    assert "SQLite" in extra_db


def test_scan_has_database_true_on_flask_todo_like_project(tmp_path):
    """Regression test: a small Flask project with db_create.py + sqlite must
    surface has_database=True and 'database' in sensitive_areas."""
    _init(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="todo"\ndependencies = ["flask"]\n'
    )
    (tmp_path / "db_create.py").write_text(
        "import sqlite3\n"
        "conn = sqlite3.connect('todo.db')\n"
        "conn.execute('CREATE TABLE todos (id INTEGER PRIMARY KEY)')\n"
    )
    result = run_scan("todo", tmp_path)
    assert result.signals["has_database"] is True
    assert "database" in result.sensitive_areas
    assert "SQLite" in result.databases_detected


def test_scan_database_alone_does_not_elevate_to_hardened(tmp_path):
    """Having a database without auth/personal-data must NOT elevate the
    initial scan to Hardened — the signal stays available for policy check."""
    _init(tmp_path)
    (tmp_path / "schema.sql").write_text("CREATE TABLE foo (id INT);\n")
    (tmp_path / "db.py").write_text("import sqlite3\n")
    result = run_scan("db-only", tmp_path)
    assert result.signals["has_database"] is True
    assert result.task_elevation != "Hardened"


def test_scan_detects_permission_by_folder_name(tmp_path):
    (tmp_path / "permissions").mkdir()
    (tmp_path / "permissions" / "__init__.py").write_text("")
    areas = _detect_sensitive_areas(tmp_path)
    assert "permission" in areas or "permissions" in areas


# ── output modes ──────────────────────────────────────────────────────────────

def test_scan_json_output(tmp_path, capsys):
    _init(tmp_path)
    capsys.readouterr()  # descarta output do init
    run_scan_cmd(plain=False, output_json=True, cwd=tmp_path)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "project_name" in data
    assert "detected_stack" in data
    assert "sensitive_areas" in data
    assert "signals" in data
    assert "baseline_level" in data
    assert "task_elevation" in data
    assert "generated_files" in data
    assert "next_steps" in data


def test_scan_plain_output(tmp_path, capsys):
    _init(tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    captured = capsys.readouterr()
    assert "[DevForge]" in captured.out
    assert "PRCP baseline" in captured.out


# ── idempotency ───────────────────────────────────────────────────────────────

def test_scan_is_idempotent(tmp_path):
    _init(tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    profile = tmp_path / ".devforge" / "prcp" / "project-profile.json"
    assert profile.exists()
    data = json.loads(profile.read_text())
    assert "prcp" in data


# ── project-profile.json content ─────────────────────────────────────────────

def test_scan_profile_json_content(tmp_path):
    _init(tmp_path)
    (tmp_path / "package.json").write_text('{"dependencies":{"next":"^14.0.0"}}')
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    data = json.loads((tmp_path / ".devforge" / "prcp" / "project-profile.json").read_text())
    assert data["prcp"]["baseline_level"] in ("Minimal", "Standard", "Hardened", "Critical")
    assert data["prcp"]["task_elevation"] in ("Minimal", "Standard", "Hardened", "Critical")
    assert "signals" in data
    assert "detected_stack" in data
