import json
from pathlib import Path

from typer.testing import CliRunner

from devforge_ai_cli.cli import app
from devforge_ai_cli.commands.evidence import run_evidence
from devforge_ai_cli.commands.init import run_init
from devforge_ai_cli.commands.plan import run_plan
from devforge_ai_cli.commands.policy_check import run_policy_check
from devforge_ai_cli.commands.pr_ready import run_pr_ready
from devforge_ai_cli.commands.review import run_review
from devforge_ai_cli.commands.scan import run_scan_cmd
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir

SPEC_PRIORITY = """\
# SPEC-PRIORITY-001 — Prioridade em tarefas
## Objetivo
Adicionar prioridade às tarefas de um Todo App Flask/SQLite.
## Critérios de aceite
- AC-001: Toda tarefa tem um campo prioridade.
## Riscos
- Toca schema SQLite.
"""

CHANGED_FILES = [
    "app.py",
    "db_create.py",
    "templates/index.html",
    "docs/",
    "specs/",
    ".devforge/",
    ".devforge/audit/",
    ".devforge/pr/",
    ".devforge/pr/commit-plan-SPEC-PRIORITY-001.md",
    ".venv/bin/python",
    "todo.db",
    "__pycache__/app.cpython-312.pyc",
    "data.sqlite",
    "cache.db",
]


def _write_app_files(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('todo')\n")
    (tmp_path / "db_create.py").write_text("CREATE_TABLE = 'tasks'\n")
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "index.html").write_text("<p>priority</p>\n")
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    (tmp_path / "__pycache__").mkdir(exist_ok=True)
    (tmp_path / "__pycache__" / "app.cpython-312.pyc").write_text("")
    (tmp_path / "todo.db").write_text("")
    (tmp_path / "data.sqlite").write_text("")
    (tmp_path / "cache.db").write_text("")


def _setup_base(tmp_path: Path) -> Path:
    _write_app_files(tmp_path)
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_scan_cmd(plain=True, output_json=False, cwd=tmp_path)
    specs = tmp_path / "specs"
    specs.mkdir(exist_ok=True)
    spec = specs / "SPEC-PRIORITY-001.md"
    spec.write_text(SPEC_PRIORITY)
    run_plan(spec=str(spec), plain=True, output_json=False, cwd=tmp_path)
    return spec


def _run_policy(tmp_path: Path) -> None:
    run_policy_check(
        diff=False,
        plain=True,
        output_json=False,
        cwd=tmp_path,
        changed_files_override=CHANGED_FILES,
        diff_content_override="--- a/db_create.py\n+++ b/db_create.py\n+CREATE TABLE tasks (id INT);\n",
    )


def _plant_test_and_rollback(tmp_path: Path) -> None:
    dd = get_devforge_dir(tmp_path)
    (dd / "test-reports").mkdir(exist_ok=True)
    (dd / "test-reports" / "SPEC-PRIORITY-001-manual.md").write_text(
        "# Test report\n\n```bash\npytest -v\nruff check .\n```\n"
    )
    (tmp_path / "docs" / "rollback").mkdir(parents=True)
    (tmp_path / "docs" / "rollback" / "SPEC-PRIORITY-001.md").write_text("# rollback\n")


def _setup_ready_evidence(tmp_path: Path) -> None:
    _setup_base(tmp_path)
    _run_policy(tmp_path)
    _plant_test_and_rollback(tmp_path)
    run_review(
        issue="SPEC-PRIORITY-001",
        reviewer="Marcos",
        role="Maintainer",
        approve=True,
        yes=True,
        notes=None,
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    _run_policy(tmp_path)
    rc = run_evidence(
        issue="SPEC-PRIORITY-001",
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 0


def test_pr_ready_fails_when_evidence_pack_does_not_exist(tmp_path: Path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    rc = run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 1


def test_pr_ready_fails_when_evidence_pack_is_not_ready_for_merge(tmp_path: Path):
    _setup_base(tmp_path)
    _run_policy(tmp_path)
    rc_evidence = run_evidence(
        issue="SPEC-PRIORITY-001",
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc_evidence == 1
    rc = run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 1


def test_pr_ready_generates_pr_body_markdown(tmp_path: Path):
    _setup_ready_evidence(tmp_path)
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=True, output_json=False, cwd=tmp_path)
    pr_body = tmp_path / ".devforge" / "pr" / "PR-SPEC-PRIORITY-001.md"
    assert pr_body.exists()
    content = pr_body.read_text()
    assert "DevForge Governance" in content
    assert "approved_with_human_review" in content


def test_pr_ready_generates_commit_plan_markdown(tmp_path: Path):
    _setup_ready_evidence(tmp_path)
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=True, output_json=False, cwd=tmp_path)
    commit_plan = tmp_path / ".devforge" / "pr" / "commit-plan-SPEC-PRIORITY-001.md"
    assert commit_plan.exists()
    content = commit_plan.read_text()
    assert "Required Files To Commit" in content
    assert "Optional Files" in content
    assert "Copy/paste git add" in content
    assert "Optional git add" in content
    assert "Usually copy the PR body into the Pull Request instead of committing these files." in content
    assert "git add app.py" in content
    assert "git add .devforge/pr/PR-SPEC-PRIORITY-001.md" in content
    assert 'git commit -m "feat: add task priority with DevForge evidence"' in content
    assert "git push -u origin HEAD" in content


def test_pr_ready_json_returns_ready_for_pr_true_when_evidence_is_approved(
    tmp_path: Path,
    capsys,
):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    rc = run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ready_for_pr"] is True
    assert data["status"] == "ready_for_merge"
    assert data["final_decision"] == "approved_with_human_review"
    assert data["git_commit_command"] == 'git commit -m "feat: add task priority with DevForge evidence"'
    assert data["git_push_command"] == "git push -u origin HEAD"


def test_pr_ready_includes_application_files_and_evidence_in_suggested_files(tmp_path: Path):
    _setup_ready_evidence(tmp_path)
    capsys_data = {}
    rc = run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    assert rc == 0
    # Read generated JSON-equivalent from the commit plan inputs through another run.
    result_path = tmp_path / ".devforge" / "pr" / "commit-plan-SPEC-PRIORITY-001.md"
    capsys_data["content"] = result_path.read_text()
    content = capsys_data["content"]
    assert "- app.py" in content
    assert "- db_create.py" in content
    assert "- templates/index.html" in content
    assert "- specs/SPEC-PRIORITY-001.md" in content
    assert "- .devforge/test-reports/SPEC-PRIORITY-001-manual.md" in content
    assert "- .devforge/reviews/HUMAN-REVIEW-SPEC-PRIORITY-001.md" in content
    assert "- .devforge/evidence/EVID-SPEC-PRIORITY-001.md" in content
    assert "- .devforge/evidence/EVID-SPEC-PRIORITY-001.json" in content
    lines = content.splitlines()
    assert "- docs/" not in lines
    assert "- specs/" not in lines


def test_pr_ready_excludes_local_env_cache_and_database_files(tmp_path: Path, capsys):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=False,
        output_json=True,
        cwd=tmp_path,
    )
    data = json.loads(capsys.readouterr().out)
    suggested = "\n".join(data["suggested_files_to_commit"])
    assert ".venv/bin/python" not in suggested
    assert "todo.db" not in suggested
    assert "__pycache__/app.cpython-312.pyc" not in suggested
    assert "data.sqlite" not in suggested
    assert "cache.db" not in suggested
    assert ".devforge/audit" not in suggested
    assert ".devforge/pr" not in suggested
    assert ".venv/" in data["do_not_commit"]
    assert "*.db" in data["do_not_commit"]
    assert "*.sqlite" in data["do_not_commit"]
    assert "__pycache__/" in data["do_not_commit"]
    assert "*.pyc" in data["do_not_commit"]


def test_pr_ready_does_not_suggest_docs_dir_when_specific_rollback_exists(
    tmp_path: Path,
    capsys,
):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "docs/" not in data["suggested_files_to_commit"]
    assert "docs/rollback/SPEC-PRIORITY-001.md" in data["suggested_files_to_commit"]


def test_pr_ready_does_not_suggest_specs_dir_when_specific_spec_exists(
    tmp_path: Path,
    capsys,
):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "specs/" not in data["suggested_files_to_commit"]
    assert "specs/SPEC-PRIORITY-001.md" in data["suggested_files_to_commit"]


def test_pr_ready_does_not_duplicate_parent_dir_and_child_file(
    tmp_path: Path,
    capsys,
):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    suggested = data["suggested_files_to_commit"]
    assert len(suggested) == len(set(suggested))
    for path in suggested:
        prefix = path.rstrip("/") + "/"
        assert not any(other != path and other.startswith(prefix) for other in suggested)


def test_pr_ready_json_returns_deduplicated_suggested_files(tmp_path: Path, capsys):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert data["suggested_files_to_commit"] == list(dict.fromkeys(data["suggested_files_to_commit"]))
    assert ".devforge/pr/PR-SPEC-PRIORITY-001.md" in data["optional_files"]
    assert ".devforge/pr/commit-plan-SPEC-PRIORITY-001.md" in data["optional_files"]
    assert ".devforge/pr/commit-plan-SPEC-PRIORITY-001.md" not in data["suggested_files_to_commit"]


def test_pr_ready_plain_includes_copy_paste_git_commands(tmp_path: Path, capsys):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "Copy/paste git add:" in out
    assert "git add app.py" in out
    assert 'git commit -m "feat: add task priority with DevForge evidence"' in out
    assert "Suggested push:" in out
    assert "git push -u origin HEAD" in out


def test_pr_ready_json_includes_git_add_commands(tmp_path: Path, capsys):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "git add app.py" in data["git_add_commands"]
    assert "git add specs/SPEC-PRIORITY-001.md" in data["git_add_commands"]


def test_pr_ready_json_includes_optional_git_add_commands(tmp_path: Path, capsys):
    _setup_ready_evidence(tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=False, output_json=True, cwd=tmp_path)
    data = json.loads(capsys.readouterr().out)
    assert "git add .devforge/pr/PR-SPEC-PRIORITY-001.md" in data["optional_git_add_commands"]
    assert (
        "git add .devforge/pr/commit-plan-SPEC-PRIORITY-001.md"
        in data["optional_git_add_commands"]
    )


def test_pr_ready_records_audit_event(tmp_path: Path):
    _setup_ready_evidence(tmp_path)
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=True, output_json=False, cwd=tmp_path)
    events = [json.loads(line) for line in get_audit_file(tmp_path).read_text().splitlines()]
    event = [e for e in events if e["event"] == "pr_ready.generated"][-1]
    assert event["issue_id"] == "SPEC-PRIORITY-001"
    assert event["status"] == "ready_for_merge"
    assert event["final_decision"] == "approved_with_human_review"
    assert event["pr_body_path"] == ".devforge/pr/PR-SPEC-PRIORITY-001.md"
    assert event["commit_plan_path"] == ".devforge/pr/commit-plan-SPEC-PRIORITY-001.md"
    assert "timestamp" in event


def test_cli_help_registers_pr_ready_command():
    runner = CliRunner()
    result = runner.invoke(app, ["pr-ready", "--help"])
    assert result.exit_code == 0
    assert "Prepare commit and PR guidance after an approved Evidence Pack." in result.output


def test_init_scan_plan_policy_review_evidence_pr_ready_flow_remains_green(tmp_path: Path):
    _setup_ready_evidence(tmp_path)
    rc = run_pr_ready(
        issue="SPEC-PRIORITY-001",
        plain=True,
        output_json=False,
        cwd=tmp_path,
    )
    assert rc == 0


def test_pr_ready_failure_output_mentions_previous_commands(tmp_path: Path, capsys):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    capsys.readouterr()
    run_pr_ready(issue="SPEC-PRIORITY-001", plain=True, output_json=False, cwd=tmp_path)
    out = capsys.readouterr().out
    assert "devforge policy check --diff" in out
    assert "devforge review --issue SPEC-PRIORITY-001" in out
    assert "devforge evidence --issue SPEC-PRIORITY-001" in out
