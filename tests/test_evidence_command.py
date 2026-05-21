import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.evidence import run_evidence
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.scan import run_scan_cmd

# ── helpers ───────────────────────────────────────────────────────────────────

SPEC_AUTH = """\
# SPEC-AUTH-001 — Login e RBAC básico
## Objetivo
Login com e-mail e senha.
## Riscos
- Toca autenticação.
"""

POLICY_REQUIRE = {
    "decision": "REQUIRE_APPROVAL",
    "can_advance_now": False,
    "exit_code": 1,
    "changed_files": ["apps/api/src/auth/login.py"],
    "files_count": 1,
    "reasons": ["touches_auth", "human_review_required"],
    "required_evidence": ["test_report", "human_review", "rollback_plan", "audit_log"],
    "evidence_status": {
        "test_report": "missing",
        "human_review": "missing",
        "rollback_plan": "missing",
        "audit_log": "present",
    },
    "prcp_level": "Hardened",
    "timestamp": "2026-05-21T00:00:00Z",
}

POLICY_ALLOW = {
    "decision": "ALLOW",
    "can_advance_now": True,
    "exit_code": 0,
    "changed_files": [],
    "files_count": 0,
    "reasons": ["no_changes_detected"],
    "required_evidence": ["audit_log"],
    "evidence_status": {"audit_log": "present"},
    "prcp_level": "Minimal",
    "timestamp": "2026-05-21T00:00:00Z",
}

POLICY_DENY = {
    "decision": "DENY",
    "can_advance_now": False,
    "exit_code": 2,
    "changed_files": ["secret.env"],
    "files_count": 1,
    "reasons": ["secret_exposure_detected"],
    "required_evidence": ["audit_log"],
    "evidence_status": {"audit_log": "present"},
    "prcp_level": "Critical",
    "timestamp": "2026-05-21T00:00:00Z",
}


def _write_policy_check(tmp_path: Path, policy: dict) -> None:
    policy_dir = tmp_path / ".devforge" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "POLICY-CHECK-LATEST.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )


def _write_plan_stub(tmp_path: Path) -> None:
    plans_dir = tmp_path / ".devforge" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "PLAN-SPEC-AUTH-001.md").write_text("# Plan\n")


def _full_setup(tmp_path: Path, policy: dict = POLICY_REQUIRE) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    (specs / "SPEC-AUTH-001.md").write_text(SPEC_AUTH)
    run_plan(spec=str(specs / "SPEC-AUTH-001.md"), plain=True, output_json=False, cwd=tmp_path)
    _write_policy_check(tmp_path, policy)


def _call(tmp_path, *, issue="ISSUE-AUTH-001", plain=True, output_json=False):
    return run_evidence(issue=issue, plain=plain, output_json=output_json, cwd=tmp_path)


# ── preconditions ─────────────────────────────────────────────────────────────

def test_evidence_requires_init(tmp_path):
    with pytest.raises(SystemExit):
        run_evidence(issue="ISSUE-AUTH-001", plain=True, output_json=False, cwd=tmp_path)


def test_evidence_requires_scan(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    with pytest.raises(SystemExit):
        run_evidence(issue="ISSUE-AUTH-001", plain=True, output_json=False, cwd=tmp_path)


def test_evidence_requires_plan(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    with pytest.raises(SystemExit):
        run_evidence(issue="ISSUE-AUTH-001", plain=True, output_json=False, cwd=tmp_path)


def test_evidence_requires_policy_check(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    _write_plan_stub(tmp_path)
    with pytest.raises(SystemExit):
        run_evidence(issue="ISSUE-AUTH-001", plain=True, output_json=False, cwd=tmp_path)


# ── file generation ───────────────────────────────────────────────────────────

def test_evidence_generates_markdown(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    md = tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.md"
    assert md.exists()
    content = md.read_text()
    assert "EVID-ISSUE-AUTH-001" in content
    assert "ISSUE-AUTH-001" in content
    assert "Evidence Status" in content


def test_evidence_generates_json(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    j = tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json"
    assert j.exists()
    data = json.loads(j.read_text())
    assert data["evidence_id"] == "EVID-ISSUE-AUTH-001"
    assert data["issue_id"] == "ISSUE-AUTH-001"
    assert "status" in data
    assert "final_decision" in data
    assert "evidence_status" in data


# ── audit trail ───────────────────────────────────────────────────────────────

def test_evidence_records_audit_event(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    ev_events = [e for e in events if e["event"] == "evidence.generated"]
    assert len(ev_events) >= 1
    e = ev_events[-1]
    assert e["issue_id"] == "ISSUE-AUTH-001"
    assert e["evidence_id"] == "EVID-ISSUE-AUTH-001"
    assert "final_decision" in e
    assert "missing_evidence" in e


# ── evidence content ──────────────────────────────────────────────────────────

def test_evidence_includes_changed_files(tmp_path):
    _full_setup(tmp_path, POLICY_REQUIRE)
    _call(tmp_path)
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    assert "changed_files" in data


def test_evidence_includes_required_evidence(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    assert "required_evidence" in data
    assert len(data["required_evidence"]) > 0


def test_evidence_calculates_missing_evidence(tmp_path):
    _full_setup(tmp_path, POLICY_REQUIRE)
    _call(tmp_path)
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    # human_review and rollback_plan should be missing
    assert "evidence_status" in data
    assert data["evidence_status"].get("audit_log") == "present"


# ── decision logic ────────────────────────────────────────────────────────────

def test_evidence_deny_returns_exit_code_2(tmp_path):
    _full_setup(tmp_path, POLICY_DENY)
    exit_code = _call(tmp_path)
    assert exit_code == 2
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    assert data["final_decision"] == "denied"
    assert data["status"] == "denied"


def test_evidence_require_approval_returns_pending_human_review(tmp_path):
    _full_setup(tmp_path, POLICY_REQUIRE)
    exit_code = _call(tmp_path)
    assert exit_code == 1
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    assert data["final_decision"] == "pending_human_review"
    assert data["human_review_required"] is True


def test_evidence_allow_with_all_evidence_returns_ready_for_pr(tmp_path):
    _full_setup(tmp_path, POLICY_ALLOW)
    exit_code = _call(tmp_path)
    assert exit_code == 0
    data = json.loads((tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json").read_text())
    assert data["final_decision"] == "ready_for_pr"


# ── output modes ──────────────────────────────────────────────────────────────

def test_evidence_json_output(tmp_path, capsys):
    _full_setup(tmp_path)
    capsys.readouterr()
    _call(tmp_path, output_json=True, plain=False)
    data = json.loads(capsys.readouterr().out)
    assert "evidence_id" in data
    assert "issue_id" in data
    assert "status" in data
    assert "policy_decision" in data
    assert "prcp_level" in data
    assert "tests_passed" in data
    assert "human_review_required" in data
    assert "final_decision" in data
    assert "changed_files" in data
    assert "required_evidence" in data
    assert "evidence_status" in data
    assert "generated_files" in data
    assert "next_step" in data


def test_evidence_plain_output(tmp_path, capsys):
    _full_setup(tmp_path)
    capsys.readouterr()
    _call(tmp_path, plain=True)
    out = capsys.readouterr().out
    assert "[DevForge]" in out
    assert "EVID-ISSUE-AUTH-001" in out
    assert "Status" in out


# ── idempotency ───────────────────────────────────────────────────────────────

def test_evidence_is_idempotent(tmp_path):
    _full_setup(tmp_path)
    _call(tmp_path)
    _call(tmp_path)
    j = tmp_path / ".devforge" / "evidence" / "EVID-ISSUE-AUTH-001.json"
    assert j.exists()
