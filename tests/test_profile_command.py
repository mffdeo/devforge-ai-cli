import json
from pathlib import Path

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.profile import run_profile_approve
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.paths import get_audit_file


def _init_and_scan(tmp_path: Path) -> None:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    (tmp_path / "calculator.py").write_text("print(1 + 1)\n")
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)


def test_profile_approve_marks_profile_approved(tmp_path: Path):
    _init_and_scan(tmp_path)
    rc = run_profile_approve(yes=True, plain=True, output_json=False, cwd=tmp_path)
    profile = json.loads((tmp_path / ".devforge" / "prcp" / "project-profile.json").read_text())
    assert rc == 0
    assert profile["profile_status"] == "approved"
    assert profile["approved_by_user"] is True
    assert profile["requires_user_approval"] is False


def test_profile_approve_records_audit_event(tmp_path: Path):
    _init_and_scan(tmp_path)
    run_profile_approve(yes=True, plain=True, output_json=False, cwd=tmp_path)
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    assert "project_profile.approved" in [event["event"] for event in events]
