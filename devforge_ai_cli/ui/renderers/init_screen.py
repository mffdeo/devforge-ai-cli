from pathlib import Path

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from devforge_ai_cli.ui import theme as t
from devforge_ai_cli.ui.console import console

_HEADER = (
    f"[bold {t.CYAN}]DevForge CLI[/bold {t.CYAN}]"
    f" [{t.TEXT}]—[/{t.TEXT}]"
    f" [bold {t.TEXT}]Community Edition[/bold {t.TEXT}]"
)
_TAGLINE = f"[{t.MUTED}]Governança local-first para SDLC com IA[/{t.MUTED}]"


def _commands_panel() -> Panel:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="right", style=f"bold {t.CYAN}", min_width=2)
    grid.add_column(min_width=14)
    grid.add_column(style=t.MUTED)

    rows = [
        ("1", f"[bold {t.CYAN}]init[/bold {t.CYAN}]",         "Setup inicial do projeto"),
        ("2", f"[bold {t.TEXT}]scan[/bold {t.TEXT}]",          "Escaneia o repositório"),
        ("3", f"[bold {t.TEXT}]plan[/bold {t.TEXT}]",          "Gera plano com spec"),
        ("4", f"[bold {t.TEXT}]policy check[/bold {t.TEXT}]",  "Avalia política de conformidade"),
        ("5", f"[bold {t.TEXT}]evidence[/bold {t.TEXT}]",      "Coleta e reporta evidências"),
    ]
    for num, cmd, desc in rows:
        grid.add_row(num, cmd, desc)

    return Panel(
        grid,
        title=f"[bold {t.PURPLE}]Comandos principais[/bold {t.PURPLE}]",
        border_style=t.CYAN,
        padding=(1, 2),
    )


def _config_table() -> Table:
    tbl = Table.grid(padding=(0, 2))
    tbl.add_column(style=t.MUTED, min_width=52)
    tbl.add_column()

    tbl.add_row(
        "? Criar estrutura .devforge/ neste repositório?",
        f"[bold {t.GREEN}]Yes[/bold {t.GREEN}]  [{t.PURPLE}]community[/{t.PURPLE}]",
    )
    tbl.add_row(
        "? Ativar trilha de auditoria local (audit.ndjson)?",
        f"[bold {t.GREEN}]Sim[/bold {t.GREEN}]",
    )
    tbl.add_row(
        "? Formato de saída padrão:",
        f"[bold {t.TEXT}]Markdown + JSON[/bold {t.TEXT}]",
    )
    tbl.add_row(
        "? Cloud login obrigatório?",
        f"[bold {t.GREEN}]Não[/bold {t.GREEN}]",
    )
    return tbl


def _devforge_tree() -> Tree:
    tree = Tree(f"[bold {t.CYAN}].devforge/[/bold {t.CYAN}]")
    tree.add(f"[{t.MUTED}]config.yml[/{t.MUTED}]")
    for d in ["prcp/", "context/", "plans/", "policy/", "evidence/"]:
        tree.add(f"[{t.MUTED}]{d}[/{t.MUTED}]")
    audit = tree.add(f"[{t.MUTED}]audit/[/{t.MUTED}]")
    audit.add(f"[{t.MUTED}]audit.ndjson[/{t.MUTED}]")
    return tree


def render_init(project_name: str, devforge_dir: Path) -> None:
    console.print()
    console.print(Panel(
        f"{_HEADER}\n{_TAGLINE}",
        border_style=t.CYAN,
        padding=(0, 2),
    ))
    console.print()

    left = Group(
        Text.from_markup(
            f"[bold {t.CYAN}][DevForge][/bold {t.CYAN}] Bem-vindo ao setup inicial"
        ),
        Text(""),
        Text.from_markup(
            f"[{t.MUTED}]Projeto detectado:[/{t.MUTED}] [bold {t.TEXT}]{project_name}[/bold {t.TEXT}]"
        ),
        Text(""),
        _config_table(),
        Text(""),
        Text.from_markup(f"[{t.MUTED}]Criando estrutura...[/{t.MUTED}]"),
        Text(""),
        _devforge_tree(),
        Text(""),
        Text.from_markup(f"[bold {t.GREEN}]✓ Setup concluído[/bold {t.GREEN}]"),
        Text.from_markup(
            f"[{t.MUTED}]Próximos passos:[/{t.MUTED}] [bold {t.CYAN}]devforge scan[/bold {t.CYAN}]"
        ),
    )

    left_panel = Panel(left, border_style=t.CYAN, padding=(1, 2))
    console.print(Columns([left_panel, _commands_panel()], equal=False, expand=True))
    console.print()
