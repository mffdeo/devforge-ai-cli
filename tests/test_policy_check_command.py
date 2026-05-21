import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.policy_engine.engine import evaluate_policy

# ── helpers ───────────────────────────────────────────────────────────────────

SPEC_AUTH = """\
# SPEC-AUTH-001 — Login e RBAC básico
## Objetivo
Login com e-mail e senha.
## Riscos
- Toca autenticação.
"""

PROFILE_HARDENED = {
    "prcp": {"baseline_level": "Standard", "task_elevation": "Hardened"},
    "signals": {"touches_auth": True, "personal_data_possible": True, "has_database": True},
    "sensitive_areas": ["auth", "login", "permission"],
}

PROFILE_STANDARD = {
    "prcp": {"baseline_level": "Standard", "task_elevation": "Standard"},
    "signals": {},
    "sensitive_areas": [],
}

EXISTING_POL_REQUIRE = {"decision": "REQUIRE_APPROVAL"}
EXISTING_POL_ALLOW = {"decision": "ALLOW"}


def _full_setup(tmp_path: Path) -> Path:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-AUTH-001.md"
    spec.write_text(SPEC_AUTH)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    return spec


def _call(tmp_path, *, files=None, content="", plain=True, output_json=False):
    return run_policy_check(
        diff=False,
        plain=plain,
        output_json=output_json,
        cwd=tmp_path,
        changed_files_override=files or [],
        diff_content_override=content,
    )


# ── preconditions ─────────────────────────────────────────────────────────────

def test_policy_requires_init(tmp_path):
    with pytest.raises(SystemExit):
        run_policy_check(diff=False, plain=True, output_json=False, cwd=tmp_path)


def test_policy_requires_scan(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    with pytest.raises(SystemExit):
        run_policy_check(diff=False, plain=True, output_json=False, cwd=tmp_path)


def test_policy_requires_plan(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    with pytest.raises(SystemExit):
        run_policy_check(diff=False, plain=True, output_json=False, cwd=tmp_path)


# ── engine unit tests (no git needed) ────────────────────────────────────────

def test_engine_no_changes_returns_allow():
    result = evaluate_policy([], "", PROFILE_STANDARD, None)
    assert result["decision"] == "ALLOW"
    assert result["can_advance_now"] is True
    assert result["exit_code"] == 0


def test_engine_auth_file_returns_require_approval():
    result = evaluate_policy(
        ["apps/api/src/auth/login.py"], "", PROFILE_STANDARD, None
    )
    assert result["decision"] == "REQUIRE_APPROVAL"
    assert result["exit_code"] == 1
    assert "touches_auth" in result["reasons"]


def test_engine_permission_file_returns_require_approval():
    result = evaluate_policy(
        ["src/permissions/rbac.py"], "", PROFILE_STANDARD, None
    )
    assert result["decision"] == "REQUIRE_APPROVAL"
    assert "touches_auth" in result["reasons"]


def test_engine_migration_requires_rollback_plan():
    result = evaluate_policy(
        ["db/migrations/0042_add_roles.py"], "", PROFILE_STANDARD, None
    )
    assert "rollback_plan" in result["required_evidence"]


def test_engine_hardened_returns_require_approval():
    # Hardened PRCP + alguma mudança real → REQUIRE_APPROVAL
    result = evaluate_policy(["src/main.py"], "", PROFILE_HARDENED, None)
    assert result["decision"] == "REQUIRE_APPROVAL"
    assert "hardened_prcp" in result["reasons"]


def test_engine_secret_marker_returns_deny():
    diff_with_secret = (
        "+-----BEGIN RSA PRIVATE KEY-----\n"
        "+MIIEowIBAAKCAQEA...\n"
        "+-----END RSA PRIVATE KEY-----\n"
    )
    result = evaluate_policy([], diff_with_secret.lower(), PROFILE_STANDARD, None)
    assert result["decision"] == "DENY"
    assert result["exit_code"] == 2


def test_engine_require_approval_from_existing_policy():
    result = evaluate_policy(
        ["src/main.py"], "", PROFILE_STANDARD, EXISTING_POL_REQUIRE
    )
    assert result["decision"] == "REQUIRE_APPROVAL"
    assert "previous_policy_require_approval" in result["reasons"]


def test_engine_required_evidence_hardened():
    result = evaluate_policy(["src/auth.py"], "", PROFILE_HARDENED, None)
    assert "test_report" in result["required_evidence"]
    assert "human_review" in result["required_evidence"]
    assert "rollback_plan" in result["required_evidence"]
    assert "audit_log" in result["required_evidence"]


# ── command-level tests ───────────────────────────────────────────────────────

def test_policy_check_no_changes_allow(tmp_path):
    _full_setup(tmp_path)
    exit_code = _call(tmp_path, files=[])
    assert exit_code == 0


def test_policy_check_auth_file_require_approval(tmp_path):
    _full_setup(tmp_path)
    exit_code = _call(tmp_path, files=["apps/api/src/auth/login.py"])
    assert exit_code == 1


def test_policy_check_generates_latest_json(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path, files=["auth.py"])
    check = tmp_path / ".devforge" / "policy" / "POLICY-CHECK-LATEST.json"
    assert check.exists()
    data = json.loads(check.read_text())
    assert "decision" in data
    assert "can_advance_now" in data
    assert "reasons" in data
    assert "evidence_status" in data


def test_policy_check_records_audit_event(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    events = [json.loads(l) for l in audit.read_text().splitlines()]
    pc_events = [e for e in events if e["event"] == "policy.checked"]
    assert len(pc_events) >= 1
    e = pc_events[-1]
    assert "decision" in e
    assert "required_evidence" in e
    assert "missing_evidence" in e


def test_policy_check_calculates_evidence_status(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path, files=["auth.py"])
    data = json.loads((tmp_path / ".devforge" / "policy" / "POLICY-CHECK-LATEST.json").read_text())
    assert "evidence_status" in data
    assert "audit_log" in data["evidence_status"]
    # audit_log exists because init/scan/plan already wrote events
    assert data["evidence_status"]["audit_log"] == "present"


def test_policy_check_json_output(tmp_path, capsys):
    _full_setup(tmp_path)
    capsys.readouterr()
    _call(tmp_path, files=["auth.py"], output_json=True, plain=False)
    data = json.loads(capsys.readouterr().out)
    assert "decision" in data
    assert "can_advance_now" in data
    assert "exit_code" in data
    assert "changed_files" in data
    assert "files_count" in data
    assert "reasons" in data
    assert "required_evidence" in data
    assert "evidence_status" in data
    assert "recommended_actions" in data
    assert "generated_files" in data
    assert "next_step" in data


def test_policy_check_plain_output(tmp_path, capsys):
    _full_setup(tmp_path)
    capsys.readouterr()
    _call(tmp_path, files=[], plain=True)
    out = capsys.readouterr().out
    assert "[DevForge]" in out
    assert "Decision" in out
