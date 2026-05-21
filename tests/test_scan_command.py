import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.scanner import _detect_sensitive_areas, _detect_stack


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
