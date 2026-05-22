import typer

from devforge_ai_cli import __version__
from devforge_ai_cli.commands import evidence as evidence_cmd
from devforge_ai_cli.commands import implement as implement_cmd
from devforge_ai_cli.commands import init as init_cmd
from devforge_ai_cli.commands import plan as plan_cmd
from devforge_ai_cli.commands import policy_check as policy_cmd
from devforge_ai_cli.commands import pr_ready as pr_ready_cmd
from devforge_ai_cli.commands import review as review_cmd
from devforge_ai_cli.commands import scan as scan_cmd
from devforge_ai_cli.commands import specify as specify_cmd

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
def specify(
    idea: str | None = typer.Option(None, "--idea", help="Feature idea to turn into a SPEC."),
    spec: str | None = typer.Option(None, "--spec", help="Existing SPEC path to review or approve."),
    title: str | None = typer.Option(None, "--title", help="SPEC title override."),
    spec_id: str | None = typer.Option(None, "--spec-id", help="SPEC ID override."),
    agent: str = typer.Option("none", "--agent", help="External agent to refine the SPEC. Supported: none, codex, custom."),
    command: str | None = typer.Option(None, "--command", help="Shell command used when --agent custom is selected."),
    interactive: bool = typer.Option(False, "--interactive", help="Ask clarifying questions interactively."),
    approve: bool = typer.Option(False, "--approve", help="Mark the generated SPEC as Approved."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation before running an external agent."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show generated paths without writing files."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Turn a feature idea into a testable DevForge SPEC."""
    exit_code = specify_cmd.run_specify(
        idea=idea,
        spec=spec,
        title=title,
        spec_id=spec_id,
        agent=agent,
        command=command,
        interactive=interactive,
        approve=approve,
        yes=yes,
        dry_run=dry_run,
        plain=plain,
        output_json=output_json,
    )
    raise typer.Exit(code=exit_code)


@app.command()
def plan(
    spec: str = typer.Option(..., "--spec", help="Path to the SPEC file."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Generate a governed plan from a SPEC."""
    plan_cmd.run_plan(spec=spec, plain=plain, output_json=output_json)


@app.command()
def implement(
    spec: str = typer.Option(..., "--spec", help="Path to the SPEC file."),
    agent: str = typer.Option("codex", "--agent", help="External agent to call. Supported: codex, custom."),
    command: str | None = typer.Option(None, "--command", help="Shell command used when --agent custom is selected."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation before running the agent."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the command without running it."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    output_json: bool = typer.Option(False, "--json", help="JSON output for automation."),
) -> None:
    """Call an external AI coding agent using the DevForge implementation brief."""
    exit_code = implement_cmd.run_implement(
        spec=spec,
        agent=agent,
        command=command,
        yes=yes,
        dry_run=dry_run,
        plain=plain,
        output_json=output_json,
    )
    raise typer.Exit(code=exit_code)


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
