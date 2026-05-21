"""`devforge review --issue` — guided human review."""

import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.review import run_review
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.paths import get_audit_file, get_config_file, get_devforge_dir

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas Flask/SQLite.
## Riscos
- Toca schema SQLite.
"""


def _setup(tmp_path: Path) -> Path:
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    return spec


# ── preconditions ────────────────────────────────────────────────────────────


def test_review_requires_policy_check_latest(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    with pytest.raises(SystemExit):
        run_review(
            issue="SPEC-PRIORITY-001",
            reviewer="Tester",
            role=None, approve=True, yes=True, notes=None,
            plain=True, output_json=False, cwd=tmp_path,
        )


# ── file generation ──────────────────────────────────────────────────────────


def test_review_generates_human_review_md(tmp_path: Path):
    _setup(tmp_path)
    rc = run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos",
        role="Maintainer",
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    assert rc == 0
    out = tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md"
    assert out.exists()
    content = out.read_text()
    assert "SPEC-PRIORITY-001" in content
    assert "Marcos" in content
    assert "Approved" in content
    assert "Maintainer" in content


def test_review_uses_dynamic_issue_id(tmp_path: Path):
    _setup(tmp_path)
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    assert not (tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-ISSUE-AUTH-001.md").exists()


def test_review_records_audit_event(tmp_path: Path):
    _setup(tmp_path)
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    audit = get_audit_file(tmp_path)
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    rec = [e for e in events if e["event"] == "human_review.recorded"]
    assert rec, "expected human_review.recorded event"
    e = rec[-1]
    assert e["issue_id"] == "SPEC-PRIORITY-001"
    assert e["decision"] == "Approved"
    assert e["reviewer"] == "Marcos"
    assert e["generated_file"].endswith("HUMAN-REVIEW-SPEC-PRIORITY-001.md")


# ── JSON output ──────────────────────────────────────────────────────────────


def test_review_json_output(tmp_path: Path, capsys):
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role="Maintainer",
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert data["issue_id"] == "SPEC-PRIORITY-001"
    assert data["reviewer"] == "Marcos"
    assert data["decision"] == "Approved"
    assert data["generated_file"].endswith("HUMAN-REVIEW-SPEC-PRIORITY-001.md")
    assert data["reviewer_source"] == "cli_arg"
    assert "evidence_status" in data
    assert data["next_step"] == "devforge evidence --issue SPEC-PRIORITY-001"


# ── reviewer resolution ──────────────────────────────────────────────────────


def test_review_uses_cli_reviewer_when_provided(tmp_path: Path, capsys):
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Alice", role=None,
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert data["reviewer"] == "Alice"
    assert data["reviewer_source"] == "cli_arg"


def test_review_uses_devforge_config_when_no_cli(tmp_path: Path, capsys, monkeypatch):
    _setup(tmp_path)
    # Inject reviewer_name into .devforge/config.yml
    cfg_path = get_config_file(tmp_path)
    cfg_path.write_text(cfg_path.read_text() + "reviewer_name: ConfigUser\n")
    # Block git so we don't accidentally fall through to git_config.
    import devforge_ai_cli.commands.review as review_mod

    def fake_run(*a, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer=None, role=None,
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert data["reviewer"] == "ConfigUser"
    assert data["reviewer_source"] == "devforge_config"


def test_review_uses_git_user_name_as_suggestion(tmp_path: Path, capsys, monkeypatch):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    def fake_run(args, **kw):
        class R:
            pass
        r = R()
        if args[:3] == ["git", "config", "user.name"]:
            r.returncode = 0
            r.stdout = "GitUser\n"
        elif args[:3] == ["git", "config", "user.email"]:
            r.returncode = 0
            r.stdout = "git@example.com\n"
        else:
            r.returncode = 1
            r.stdout = ""
        return r
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer=None, role=None,
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert data["reviewer"] == "GitUser"
    assert data["reviewer_source"] == "git_config"


def test_review_falls_back_to_prompt(tmp_path: Path, capsys, monkeypatch):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    # Block any reviewer_name in config and any git output
    def fake_run(*a, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    # Interactive prompt — run without --plain/--json
    inputs = iter(["TypedUser", "y"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
    capsys.readouterr()
    rc = run_review(
        issue="SPEC-PRIORITY-001",
        reviewer=None, role=None,
        approve=False, yes=False, notes=None,
        plain=False, output_json=False, cwd=tmp_path,
    )
    assert rc == 0
    out = tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md"
    assert out.exists()
    md = out.read_text()
    assert "TypedUser" in md
    assert "`prompt`" in md


# ── approval flow ────────────────────────────────────────────────────────────


def test_review_does_not_generate_when_user_says_no(tmp_path: Path, monkeypatch, capsys):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    def fake_run(args, **kw):
        class R:
            returncode = 0
            stdout = "GitUser\n"
        return R()
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    # User confirms reviewer but rejects approval
    inputs = iter(["", "n"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
    capsys.readouterr()
    rc = run_review(
        issue="SPEC-PRIORITY-001",
        reviewer=None, role=None,
        approve=False, yes=False, notes=None,
        plain=False, output_json=False, cwd=tmp_path,
    )
    assert rc == 1
    assert not (tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").exists()


def test_review_approve_requires_reviewer(tmp_path: Path, monkeypatch):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    def fake_run(*a, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit):
        run_review(
            issue="SPEC-PRIORITY-001",
            reviewer=None, role=None,
            approve=True, yes=True, notes=None,
            plain=True, output_json=False, cwd=tmp_path,
        )


def test_review_records_reviewer_source(tmp_path: Path, capsys):
    """The audit event and the generated MD must both surface the source."""
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Alice", role=None,
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    audit = get_audit_file(tmp_path)
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    rec = [e for e in events if e["event"] == "human_review.recorded"][-1]
    assert rec["reviewer_source"] == "cli_arg"
    md = (tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").read_text()
    assert "`cli_arg`" in md


# ── no hardcoded reviewer name ───────────────────────────────────────────────


def test_review_does_not_use_hardcoded_name(tmp_path: Path, monkeypatch, capsys):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    # No git, no config, no CLI arg → must NOT silently invent a name.
    def fake_run(*a, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    # Non-interactive path (--json) and no reviewer provided → must exit
    capsys.readouterr()
    with pytest.raises(SystemExit):
        run_review(
            issue="SPEC-PRIORITY-001",
            reviewer=None, role=None,
            approve=True, yes=True, notes=None,
            plain=False, output_json=True, cwd=tmp_path,
        )


# ── policy_check feedback loop ──────────────────────────────────────────────


def test_policy_check_recommends_devforge_review_when_human_review_missing(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert any(
        "devforge review --issue SPEC-PRIORITY-001" in a
        for a in data["recommended_actions"]
    )


def test_policy_check_omits_review_after_human_review_present(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    # Generate the human review
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions = " | ".join(data["recommended_actions"])
    assert "devforge review --issue" not in actions
    assert "devforge evidence --issue SPEC-PRIORITY-001" in actions


def test_review_prints_summary_before_prompt(tmp_path: Path, capsys, monkeypatch):
    """In interactive (non --plain / non --json) mode the briefing must be
    printed before the approval prompt — reasons, changed_files,
    evidence_status, files-to-review, what-to-check checklist."""
    _setup(tmp_path)
    # Avoid the reviewer prompt by passing --reviewer; force "no" on approval
    inputs = iter(["n"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
    capsys.readouterr()
    rc = run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=False, yes=False, notes=None,
        plain=False, output_json=False, cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert rc == 1
    # Summary blocks
    assert "Human review — SPEC-PRIORITY-001" in out
    assert "Reasons:" in out
    assert "Changed files" in out
    assert "Required evidence:" in out
    assert "Arquivos para revisar:" in out
    assert "O que revisar:" in out
    # Checklist items
    assert "A SPEC foi revisada?" in out
    assert "O test report está presente?" in out
    assert "O diff não contém segredo, token ou credencial?" in out
    # SPEC and Plan Pack listed in arquivos para revisar
    assert "specs/SPEC-PRIORITY-001.md" in out
    assert ".devforge/plans/PLAN-SPEC-PRIORITY-001.md" in out


def test_review_prompt_wording_was_updated():
    """The input() prompt itself is monkeypatched in tests, so we sanity
    check the wording from the source instead."""
    from pathlib import Path as _P
    src = _P(__file__).parent.parent / "devforge_ai_cli" / "commands" / "review.py"
    text = src.read_text(encoding="utf-8")
    assert "Você revisou os itens acima e aprova esta revisão humana?" in text


def test_review_summary_in_plain_mode_too(tmp_path: Path, capsys):
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert "Human review — SPEC-PRIORITY-001" in out
    assert "Reasons:" in out
    assert "Required evidence:" in out


def test_review_no_response_does_not_generate_and_emits_clear_message(
    tmp_path: Path, capsys, monkeypatch
):
    _setup(tmp_path)
    inputs = iter(["n"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
    capsys.readouterr()
    rc = run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=False, yes=False, notes=None,
        plain=False, output_json=False, cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert not (
        tmp_path / ".devforge" / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md"
    ).exists()
    assert "Revisão humana não registrada" in out
    assert "Revise os arquivos listados e rode novamente" in out


def test_review_show_diff_includes_diff_stat(tmp_path: Path, capsys, monkeypatch):
    _setup(tmp_path)
    import devforge_ai_cli.commands.review as review_mod

    def fake_run(args, **kw):
        class R:
            pass
        r = R()
        if args[:2] == ["git", "diff"]:
            r.returncode = 0
            r.stdout = " app.py | 5 ++++-\n 1 file changed, 4 insertions(+), 1 deletion(-)\n"
        else:
            r.returncode = 1
            r.stdout = ""
        return r
    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
        show_diff=True,
    )
    out = capsys.readouterr().out
    assert "Diff stat:" in out
    assert "app.py" in out
    assert "1 file changed" in out


def test_review_json_mode_does_not_print_summary(tmp_path: Path, capsys):
    """JSON consumers must get a clean machine-readable payload only."""
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=False, output_json=True, cwd=tmp_path,
    )
    out = capsys.readouterr().out
    # The whole stdout should be parseable JSON
    data = json.loads(out)
    assert data["decision"] == "Approved"
    assert "O que revisar" not in out
    assert "Arquivos para revisar" not in out


def test_policy_check_generates_review_brief_when_human_review_missing(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert data["review_brief_path"] == ".devforge/context/review-brief-SPEC-PRIORITY-001.md"
    assert (tmp_path / data["review_brief_path"]).exists()
    md = (tmp_path / data["review_brief_path"]).read_text()
    # Must surface the SPEC, must NOT empower IA to approve
    assert "SPEC-PRIORITY-001" in md
    assert "A IA NÃO aprova a revisão humana" in md
    assert "devforge review --issue SPEC-PRIORITY-001" in md


def test_policy_check_json_includes_review_brief_path_and_prompt(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    assert "review_brief_path" in data
    assert "suggested_ai_review_prompt" in data
    assert data["suggested_ai_review_prompt"].startswith("Revise a mudança usando")
    assert ".devforge/context/review-brief-SPEC-PRIORITY-001.md" in data["suggested_ai_review_prompt"]


def test_policy_check_recommended_actions_include_ai_review_prompt(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions_text = " | ".join(data["recommended_actions"])
    assert "Revisão assistida" in actions_text
    assert ".devforge/context/review-brief-SPEC-PRIORITY-001.md" in actions_text
    assert "devforge review --issue SPEC-PRIORITY-001" in actions_text
    assert "devforge evidence --issue SPEC-PRIORITY-001" in actions_text


def test_policy_check_drops_ai_review_when_human_review_present(
    tmp_path: Path, capsys
):
    _setup(tmp_path)
    dd = get_devforge_dir(tmp_path)
    (dd / "reviews").mkdir(exist_ok=True)
    (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").write_text("Approved\n")
    capsys.readouterr()
    run_policy_check(
        diff=False, plain=False, output_json=True, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    data = json.loads(capsys.readouterr().out)
    actions_text = " | ".join(data["recommended_actions"])
    assert "Revisão assistida" not in actions_text
    assert "devforge review --issue" not in actions_text
    assert data["review_brief_path"] is None
    assert data["suggested_ai_review_prompt"] is None


def test_review_summary_includes_review_brief_path(tmp_path: Path, capsys):
    _setup(tmp_path)
    capsys.readouterr()
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role=None,
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    out = capsys.readouterr().out
    assert "Review brief: .devforge/context/review-brief-SPEC-PRIORITY-001.md" in out
    assert "Sugestão para revisão assistida com IA" in out
    assert "Revise a mudança usando" in out


def test_full_flow_remains_green(tmp_path: Path):
    """init → scan → plan → policy check → review → policy check → evidence."""
    spec = _setup(tmp_path)
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos", role="Maintainer",
        approve=True, yes=True, notes=None,
        plain=True, output_json=False, cwd=tmp_path,
    )
    # Re-run policy check; it should reflect the now-present human_review.
    rc = run_policy_check(
        diff=False, plain=True, output_json=False, cwd=tmp_path,
        changed_files_override=["app.py"], diff_content_override="",
    )
    # REQUIRE_APPROVAL still → exit 1 expected from policy_check engine.
    assert rc == 1
    # devforge artifacts exist
    dd = get_devforge_dir(tmp_path)
    assert (dd / "reviews" / "HUMAN-REVIEW-SPEC-PRIORITY-001.md").exists()
    assert (dd / "policy" / "POLICY-DECISION-SPEC-PRIORITY-001.json").exists()
    assert spec.exists()
