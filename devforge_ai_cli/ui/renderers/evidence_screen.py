from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devforge_ai_cli.ui import theme as t
from devforge_ai_cli.ui.console import console

_HEADER = (
    f"[bold {t.CYAN}]DevForge CLI[/bold {t.CYAN}]"
    f" [{t.TEXT}]—[/{t.TEXT}]"
    f" [bold {t.TEXT}]Community Edition[/bold {t.TEXT}]"
)
_TAGLINE = f"[{t.MUTED}]Evidence Pack antes do merge[/{t.MUTED}]"


def _decision_color(decision: str) -> str:
    return {"ALLOW": t.GREEN, "REQUIRE_APPROVAL": t.AMBER, "DENY": t.RED}.get(decision, t.MUTED)


def _status_color(status: str) -> str:
    return {
        "ready_for_pr": t.GREEN,
        "ready_for_review": t.AMBER,
        "pending_human_review": t.AMBER,
        "blocked_missing_evidence": t.RED,
        "denied": t.RED,
    }.get(status, t.MUTED)


def _bool_icon(val: bool) -> str:
    return f"[bold {t.GREEN}]true[/bold {t.GREEN}]" if val else f"[{t.MUTED}]false[/{t.MUTED}]"


def _evidence_summary_panel(evidence: dict, generated_files: list[str]) -> Panel:
    dc = _decision_color(evidence["policy_decision"])
    sc = _status_color(evidence["status"])

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style=t.MUTED, min_width=22)
    grid.add_column()

    grid.add_row("Issue:", f"[bold {t.TEXT}]{evidence['issue_id']}[/bold {t.TEXT}]")
    grid.add_row("Evidence ID:", f"[{t.CYAN}]{evidence['evidence_id']}[/{t.CYAN}]")
    grid.add_row("Status:", f"[bold {sc}]{evidence['status']}[/bold {sc}]")
    grid.add_row(
        "Tests Passed:",
        _bool_icon(evidence["tests_passed"]),
    )
    grid.add_row(
        "Policy:",
        f"[bold {dc}]{evidence['policy_decision']}[/bold {dc}]",
    )

    # Evidence items
    files_grid = Table.grid(padding=(0, 1))
    files_grid.add_column(style=t.MUTED)
    files_grid.add_column(style=t.MUTED, min_width=14)
    files_grid.add_column()
    for item, status in evidence.get("collected_items", []):
        icon = f"[{t.GREEN}]✓[/{t.GREEN}]" if status == "present" else f"[{t.MUTED}]·[/{t.MUTED}]"
        files_grid.add_row(icon, item, f"[{t.MUTED}]{status}[/{t.MUTED}]")

    return Panel(
        Group(
            grid,
            Text(""),
            files_grid,
        ),
        title=f"[bold {t.PURPLE}]Evidence Summary[/bold {t.PURPLE}]",
        border_style=t.CYAN,
        padding=(1, 2),
    )


def render_evidence(evidence: dict, generated_files: list[str]) -> None:
    console.print()
    console.print(Panel(
        f"{_HEADER}\n{_TAGLINE}",
        border_style=t.CYAN,
        padding=(0, 2),
    ))
    console.print()

    dc = _decision_color(evidence["policy_decision"])
    sc = _status_color(evidence["status"])
    final_color = _status_color(evidence["final_decision"])

    # Checklist of collected items
    check_items: list[str] = [
        f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Issue carregada:[/{t.MUTED}] "
        f"[bold {t.TEXT}]{evidence['issue_id']}[/bold {t.TEXT}]",
        f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Diff anexado[/{t.MUTED}]",
    ]
    for ev, status in evidence["evidence_status"].items():
        icon = f"[bold {t.GREEN}]✓[/bold {t.GREEN}]" if status == "present" else f"[{t.MUTED}]·[/{t.MUTED}]"
        label = ev.replace("_", " ").capitalize()
        check_items.append(f"{icon} [{t.MUTED}]{label}:[/{t.MUTED}] [{t.MUTED}]{status}[/{t.MUTED}]")
    check_items.append(
        f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Audit trail atualizado[/{t.MUTED}]"
    )

    # Evidence pack summary table
    pack_grid = Table.grid(padding=(0, 1))
    pack_grid.add_column(style=t.MUTED, min_width=26)
    pack_grid.add_column()
    pack_grid.add_row("id:", f"[bold {t.CYAN}]{evidence['evidence_id']}[/bold {t.CYAN}]")
    pack_grid.add_row("status:", f"[bold {sc}]{evidence['status']}[/bold {sc}]")
    pack_grid.add_row("tests_passed:", _bool_icon(evidence["tests_passed"]))
    pack_grid.add_row(
        "human_review_required:",
        _bool_icon(evidence["human_review_required"]),
    )
    pack_grid.add_row(
        "final_decision:",
        f"[bold {final_color}]{evidence['final_decision']}[/bold {final_color}]",
    )

    # Files table
    files_grid = Table.grid(padding=(0, 1))
    files_grid.add_column(style=f"bold {t.CYAN}")
    for f in generated_files:
        files_grid.add_row(f"  {f}")

    # Summary bullets
    summary_lines: list[str] = []
    if evidence["missing_evidence"]:
        summary_lines.append(f"[{t.RED}]- Evidências ausentes: {', '.join(evidence['missing_evidence'])}[/{t.RED}]")
    else:
        summary_lines.append(f"[{t.GREEN}]- Evidência mínima presente[/{t.GREEN}]")
    if evidence["changed_files"]:
        summary_lines.append(f"[{t.MUTED}]- Mudança rastreável[/{t.MUTED}]")
    if evidence["human_review_required"]:
        summary_lines.append(f"[{t.AMBER}]- Pronta para revisão humana[/{t.AMBER}]")
    else:
        summary_lines.append(f"[{t.GREEN}]- Pronta para PR[/{t.GREEN}]")

    workflow = (
        f"[{t.MUTED}]init[/{t.MUTED}] [{t.CYAN}]→[/{t.CYAN}] "
        f"[{t.MUTED}]scan[/{t.MUTED}] [{t.CYAN}]→[/{t.CYAN}] "
        f"[{t.MUTED}]plan[/{t.MUTED}] [{t.CYAN}]→[/{t.CYAN}] "
        f"[{t.MUTED}]policy check[/{t.MUTED}] [{t.CYAN}]→[/{t.CYAN}] "
        f"[bold {t.CYAN}]evidence[/bold {t.CYAN}]"
    )

    left_items: list = [
        Text.from_markup(
            f"[bold {t.CYAN}][DevForge][/bold {t.CYAN}] Montando Evidence Pack..."
        ),
        Text(""),
    ]
    for line in check_items:
        left_items.append(Text.from_markup(line))

    left_items += [
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Evidence Pack[/bold {t.TEXT}]"),
        pack_grid,
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Arquivos gerados[/bold {t.TEXT}]"),
        files_grid,
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Resumo[/bold {t.TEXT}]"),
    ]
    for line in summary_lines:
        left_items.append(Text.from_markup(line))

    left_items += [
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Workflow completo[/bold {t.TEXT}]"),
        Text.from_markup(workflow),
        Text(""),
        Text.from_markup(
            f"[bold {t.GREEN}]✓ Evidence Pack pronto.[/bold {t.GREEN}] "
            f"[{t.MUTED}]Governança local-first, revisão humana sempre.[/{t.MUTED}]"
        ),
    ]

    left_panel = Panel(Group(*left_items), border_style=t.CYAN, padding=(1, 2))
    right_panel = _evidence_summary_panel(evidence, generated_files)
    console.print(Columns([left_panel, right_panel], equal=False, expand=True))
    console.print()
