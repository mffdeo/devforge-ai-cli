import typer

from devforge_ai_cli import __version__
from devforge_ai_cli.commands import evidence as evidence_cmd
from devforge_ai_cli.commands import init as init_cmd
from devforge_ai_cli.commands import plan as plan_cmd
from devforge_ai_cli.commands import policy_check as policy_cmd
from devforge_ai_cli.commands import pr_ready as pr_ready_cmd
from devforge_ai_cli.commands import review as review_cmd
from devforge_ai_cli.commands import scan as scan_cmd

app = typer.Typer(
    name="devforge",
    help="Local-first governance CLI for AI-assisted SDLC.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

policy_app = typer.Typer(
    name="policy",
    help="Policy gate commands.",
    no_args_is_help=True,
)
app.add_typer(policy_app, name="policy")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"devforge {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command()
def init(
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Bootstrap local governance in the current repository."""
    init_cmd.run_init(plain=plain, output_json=output_json)


@app.command()
def scan(
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Scan repository for stack, CI and risk signals."""
    scan_cmd.run_scan_cmd(plain=plain, output_json=output_json)


@app.command()
def plan(
    spec: str = typer.Option(..., "--spec", help="Path to the SPEC file."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Generate a governed plan from a SPEC."""
    plan_cmd.run_plan(spec=spec, plain=plain, output_json=output_json)


@policy_app.command("check")
def policy_check(
    diff: bool = typer.Option(False, "--diff", help="Evaluate against current git diff."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Evaluate current diff against local policies."""
    exit_code = policy_cmd.run_policy_check(diff=diff, plain=plain, output_json=output_json)
    raise typer.Exit(code=exit_code)


@app.command()
def evidence(
    issue: str = typer.Option(..., "--issue", help="Issue ID to collect evidence for."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Collect and package evidence before a PR."""
    exit_code = evidence_cmd.run_evidence(issue=issue, plain=plain, output_json=output_json)
    raise typer.Exit(code=exit_code)


@app.command("pr-ready")
def pr_ready(
    issue: str = typer.Option(..., "--issue", help="Issue ID to prepare PR guidance for."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Prepare commit and PR guidance after an approved Evidence Pack."""
    exit_code = pr_ready_cmd.run_pr_ready(issue=issue, plain=plain, output_json=output_json)
    raise typer.Exit(code=exit_code)


@app.command()
def review(
    issue: str = typer.Option(..., "--issue", help="Issue or SPEC ID for the review."),
    reviewer: str | None = typer.Option(None, "--reviewer", help="Reviewer name (overrides detection)."),
    role: str | None = typer.Option(None, "--role", help="Reviewer role (e.g. Maintainer)."),
    approve: bool = typer.Option(False, "--approve", help="Approve without interactive prompt."),
    yes: bool = typer.Option(False, "--yes", help="Skip every confirmation (CI use)."),
    notes: str | None = typer.Option(None, "--notes", help="Optional reviewer notes."),
    show_diff: bool = typer.Option(False, "--show-diff", help="Print `git diff --stat` before asking for approval."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Record an explicit human review approval for the current issue."""
    exit_code = review_cmd.run_review(
        issue=issue,
        reviewer=reviewer,
        role=role,
        approve=approve,
        yes=yes,
        notes=notes,
        show_diff=show_diff,
        plain=plain,
        output_json=output_json,
    )
    raise typer.Exit(code=exit_code)
