from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devforge_ai_cli.core.planner import PlanResult
from devforge_ai_cli.ui import theme as t
from devforge_ai_cli.ui.console import console

_HEADER = (
    f"[bold {t.CYAN}]DevForge CLI[/bold {t.CYAN}]"
    f" [{t.TEXT}]—[/{t.TEXT}]"
    f" [bold {t.TEXT}]Community Edition[/bold {t.TEXT}]"
)
_TAGLINE = f"[{t.MUTED}]Plano governado com Context Pack e evidências requeridas[/{t.MUTED}]"


def _decision_color(decision: str) -> str:
    return {
        "REQUIRE_APPROVAL": t.AMBER,
        "ALLOW": t.GREEN,
        "DENY": t.RED,
    }.get(decision, t.MUTED)


def _tasks_table(tasks: list[dict]) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=f"bold {t.CYAN}", min_width=16)
    tbl.add_column(style=t.TEXT)
    for task in tasks:
        tbl.add_row(f"- {task['id']}", task["description"])
    return tbl


def _context_table(result: PlanResult) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=t.MUTED, min_width=22)
    tbl.add_column(style=t.TEXT)
    tbl.add_row("allowed_uses:", ", ".join(result.allowed_uses[:3]))
    tbl.add_row("blocked_uses:", ", ".join(result.blocked_uses[:3]))
    tbl.add_row("required_evidence:", ", ".join(result.required_evidence))
    return tbl


def _files_table(files: list[str]) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=f"bold {t.CYAN}")
    for f in files:
        tbl.add_row(f"  {f}")
    return tbl


def _summary_panel(result: PlanResult) -> Panel:
    # Tasks section
    tasks_grid = Table.grid(padding=(0, 1))
    tasks_grid.add_column(style=f"bold {t.CYAN}", justify="right", min_width=2)
    tasks_grid.add_column(style=t.MUTED)
    for i, task in enumerate(result.tasks, 1):
        tasks_grid.add_row(str(i), f"[{t.CYAN}]{task['id']}[/{t.CYAN}] {task['description']}")

    # Allowed uses
    allowed_text = Text.from_markup(
        f"[{t.MUTED}]" + ", ".join(result.allowed_uses[:3]) + f"[/{t.MUTED}]"
    )

    # Blocked uses
    blocked_text = Text.from_markup(
        f"[{t.RED}]" + ", ".join(result.blocked_uses[:3]) + f"[/{t.RED}]"
    )

    # Evidence
    evidence_text = Text.from_markup(
        f"[{t.AMBER}]" + ", ".join(result.required_evidence) + f"[/{t.AMBER}]"
    )

    body = Group(
        Text.from_markup(f"[bold {t.TEXT}]Tarefas[/bold {t.TEXT}]"),
        tasks_grid,
        Text(""),
        Text.from_markup(f"[bold {t.GREEN}]Allowed uses[/bold {t.GREEN}]"),
        allowed_text,
        Text(""),
        Text.from_markup(f"[bold {t.RED}]Blocked uses[/bold {t.RED}]"),
        blocked_text,
        Text(""),
        Text.from_markup(f"[bold {t.AMBER}]Evidence required[/bold {t.AMBER}]"),
        evidence_text,
    )

    return Panel(
        body,
        title=f"[bold {t.PURPLE}]Resumo do plan[/bold {t.PURPLE}]",
        border_style=t.CYAN,
        padding=(1, 2),
    )


def render_plan(result: PlanResult) -> None:
    console.print()
    console.print(Panel(
        f"{_HEADER}\n{_TAGLINE}",
        border_style=t.CYAN,
        padding=(0, 2),
    ))
    console.print()

    dc = _decision_color(result.policy_decision)

    left = Group(
        Text.from_markup(
            f"[bold {t.CYAN}][DevForge][/bold {t.CYAN}] Gerando Plan Pack governado..."
        ),
        Text(""),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]SPEC carregada:[/{t.MUTED}] "
            f"[bold {t.TEXT}]{result.spec_path}[/bold {t.TEXT}]"
        ),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]PRCP aplicado:[/{t.MUTED}] "
            f"[bold {t.AMBER}]{result.prcp_level}[/bold {t.AMBER}]"
        ),
        Text.from_markup(
            f"[bold {t.GREEN}]✔[/bold {t.GREEN}] [{t.MUTED}]Política inicial:[/{t.MUTED}] "
            f"[bold {dc}]{result.policy_decision}[/bold {dc}]"
        ),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Plan Pack[/bold {t.TEXT}]"),
        _tasks_table(result.tasks),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Context Pack[/bold {t.TEXT}]"),
        _context_table(result),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Arquivos gerados[/bold {t.TEXT}]"),
        _files_table(result.generated_files),
        Text(""),
        Text.from_markup(
            f"[{t.MUTED}]Próximo passo:[/{t.MUTED}] "
            f"[bold {t.CYAN}]devforge policy check --diff[/bold {t.CYAN}]"
        ),
    )

    left_panel = Panel(left, border_style=t.CYAN, padding=(1, 2))
    console.print(Columns([left_panel, _summary_panel(result)], equal=False, expand=True))
    console.print()
