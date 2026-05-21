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
_TAGLINE = f"[{t.MUTED}]Policy gate antes do merge[/{t.MUTED}]"


def _decision_color(decision: str) -> str:
    return {"ALLOW": t.GREEN, "REQUIRE_APPROVAL": t.AMBER, "DENY": t.RED}.get(decision, t.MUTED)


def _advance_label(can_advance: bool) -> str:
    if can_advance:
        return f"[bold {t.GREEN}]Sim[/bold {t.GREEN}]"
    return f"[bold {t.RED}]Não ainda[/bold {t.RED}]"


def _evidence_status_table(evidence_status: dict[str, str]) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=t.MUTED, min_width=20)
    tbl.add_column()
    for ev, status in evidence_status.items():
        color = t.GREEN if status == "present" else t.RED
        tbl.add_row(f"- {ev}:", f"[bold {color}]{status}[/bold {color}]")
    return tbl


def _list_table(items: list[str], bullet: str = "-", color: str = t.TEXT) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=color)
    for item in items:
        tbl.add_row(f"{bullet} {item}")
    return tbl


def _numbered_table(items: list[str], color: str = t.TEXT) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=f"bold {t.CYAN}", justify="right", min_width=2)
    tbl.add_column(style=color)
    for i, item in enumerate(items, 1):
        tbl.add_row(str(i), item)
    return tbl


def _summary_panel(
    result: dict,
    evidence_status: dict[str, str],
    files_count: int,
    prcp_level: str,
    timestamp: str,
) -> Panel:
    decision = result["decision"]
    dc = _decision_color(decision)

    reasons_grid = Table.grid(padding=(0, 1))
    reasons_grid.add_column(style=t.MUTED)
    for r in result["reasons"]:
        reasons_grid.add_row(f"- {r}")

    evidence_grid = Table.grid(padding=(0, 1))
    evidence_grid.add_column(style=t.MUTED)
    for ev in result["required_evidence"]:
        evidence_grid.add_row(f"- {ev}")

    short_ts = timestamp[:19].replace("T", " ") if timestamp else "–"

    stats_grid = Table.grid(padding=(0, 2))
    stats_grid.add_column(style=t.MUTED)
    stats_grid.add_column(style=t.TEXT)
    stats_grid.add_row("Arquivos analisados:", str(files_count))
    stats_grid.add_row("Policy rules:", str(len(result["reasons"])))
    stats_grid.add_row("Gate processado em:", short_ts)

    body = Group(
        Text.from_markup(f"[bold {dc}]{decision}[/bold {dc}]"),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Reasons[/bold {t.TEXT}]"),
        reasons_grid,
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Required evidence[/bold {t.TEXT}]"),
        evidence_grid,
        Text(""),
        stats_grid,
    )

    return Panel(
        body,
        title=f"[bold {t.PURPLE}]Resumo do gate de políticas[/bold {t.PURPLE}]",
        border_style=t.CYAN,
        padding=(1, 2),
    )


def render_policy(
    result: dict,
    evidence_status: dict[str, str],
    files_count: int,
    prcp_level: str,
    timestamp: str,
    evidence_issue_id: str = "<ISSUE-ID>",
) -> None:
    console.print()
    console.print(Panel(
        f"{_HEADER}\n{_TAGLINE}",
        border_style=t.CYAN,
        padding=(0, 2),
    ))
    console.print()

    decision = result["decision"]
    dc = _decision_color(decision)
    can_advance = result["can_advance_now"]
    exit_code = result["exit_code"]

    left = Group(
        Text.from_markup(
            f"[bold {t.CYAN}][DevForge][/bold {t.CYAN}] Avaliando mudança atual..."
        ),
        Text(""),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]Diff analisado:[/{t.MUTED}] "
            f"[bold {t.TEXT}]{files_count} arquivo(s)[/bold {t.TEXT}]"
        ),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]Context Pack carregado[/{t.MUTED}]"
        ),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]Policy rules carregadas[/{t.MUTED}]"
        ),
        Text(""),
        Text.from_markup(
            f"[{t.MUTED}]Decision:[/{t.MUTED}] [bold {dc}]{decision}[/bold {dc}]"
        ),
        Text.from_markup(
            f"[{t.MUTED}]Pode avançar agora?[/{t.MUTED}] {_advance_label(can_advance)}"
        ),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Reasons[/bold {t.TEXT}]"),
        _list_table(result["reasons"], color=t.MUTED),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Required evidence[/bold {t.TEXT}]"),
        _list_table(result["required_evidence"], color=t.MUTED),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Evidence status[/bold {t.TEXT}]"),
        _evidence_status_table(evidence_status),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Recommended actions[/bold {t.TEXT}]"),
        _numbered_table(result["recommended_actions"], color=t.MUTED),
        Text(""),
        Text.from_markup(
            f"[{t.MUTED}]Exit code:[/{t.MUTED}] [bold {dc}]{exit_code}[/bold {dc}]"
        ),
        Text.from_markup(
            f"[{t.MUTED}]Próximo passo:[/{t.MUTED}] "
            f"[bold {t.CYAN}]devforge evidence --issue {evidence_issue_id}[/bold {t.CYAN}]"
        ),
    )

    left_panel = Panel(left, border_style=t.CYAN, padding=(1, 2))
    right_panel = _summary_panel(result, evidence_status, files_count, prcp_level, timestamp)
    console.print(Columns([left_panel, right_panel], equal=False, expand=True))
    console.print()
