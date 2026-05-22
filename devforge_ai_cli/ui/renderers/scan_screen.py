from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devforge_ai_cli.core.scanner import ScanResult
from devforge_ai_cli.ui import theme as t
from devforge_ai_cli.ui.console import console

_HEADER = (
    f"[bold {t.CYAN}]DevForge CLI[/bold {t.CYAN}]"
    f" [{t.TEXT}]—[/{t.TEXT}]"
    f" [bold {t.TEXT}]Community Edition[/bold {t.TEXT}]"
)
_TAGLINE = f"[{t.MUTED}]Mapeamento de stack, risco e áreas sensíveis[/{t.MUTED}]"


def _bool_str(val: bool) -> str:
    return f"[bold {t.GREEN}]true[/bold {t.GREEN}]" if val else f"[{t.MUTED}]false[/{t.MUTED}]"


def _signals_table(signals: dict) -> Table:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style=t.MUTED, min_width=30)
    tbl.add_column()

    display = {
        "touches_auth": signals.get("touches_auth", False),
        "personal_data_possible": signals.get("personal_data_possible", False),
        "external_integrations": signals.get("external_integrations", False),
        "production_impact": signals.get("production_impact", "low"),
        "has_ci": signals.get("has_ci", False),
        "has_tests": signals.get("has_tests", False),
        "has_docker": signals.get("has_docker", False),
        "has_database": signals.get("has_database", False),
    }

    for key, val in display.items():
        if isinstance(val, bool):
            rendered = _bool_str(val)
        else:
            color = t.AMBER if val == "medium" else (t.RED if val == "high" else t.GREEN)
            rendered = f"[bold {color}]{val}[/bold {color}]"
        tbl.add_row(f"- {key}:", rendered)

    return tbl


def _summary_panel(result: ScanResult) -> Panel:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="right", style=f"bold {t.CYAN}", min_width=2)
    grid.add_column(style=f"bold {t.TEXT}", min_width=16)
    grid.add_column(style=t.MUTED)

    stack_summary = " · ".join(result.detected_stack[:4]) if result.detected_stack else "–"
    sensitive_summary = ", ".join(result.sensitive_areas[:4]) if result.sensitive_areas else "–"
    if len(result.sensitive_areas) > 4:
        sensitive_summary += f" +{len(result.sensitive_areas) - 4}"

    rows = [
        ("1", "Stack",      stack_summary),
        ("2", result.baseline_level, "Baseline PRCP"),
        ("3", "Sensibilidade", sensitive_summary),
        ("4", "Próximo",    f"[{t.CYAN}]{result.suggested_next_command}[/{t.CYAN}]"),
    ]
    for num, label, desc in rows:
        grid.add_row(num, label, desc)

    footer = Text.from_markup(
        f"\n[{t.MUTED}]Local-first · Sem cloud · Sem logs externos[/{t.MUTED}]"
    )

    return Panel(
        Group(grid, footer),
        title=f"[bold {t.PURPLE}]Resumo do scan[/bold {t.PURPLE}]",
        border_style=t.CYAN,
        padding=(1, 2),
    )


def render_scan(result: ScanResult) -> None:
    console.print()
    console.print(Panel(
        f"{_HEADER}\n{_TAGLINE}",
        border_style=t.CYAN,
        padding=(0, 2),
    ))
    console.print()

    # Stack line
    stack_str = " · ".join(result.detected_stack) if result.detected_stack else "nenhuma detectada"
    ci_str = result.ci_detected or "não detectado"
    sensitive_str = ", ".join(result.sensitive_areas) if result.sensitive_areas else "nenhuma"

    # Generated files
    files_grid = Table.grid(padding=(0, 1))
    files_grid.add_column(style=t.MUTED)
    for f in result.generated_files:
        files_grid.add_row(f"  [{t.CYAN}]{f}[/{t.CYAN}]")

    # Next steps
    next_grid = Table.grid(padding=(0, 1))
    next_grid.add_column(style=f"bold {t.CYAN}", justify="right", min_width=2)
    next_grid.add_column(style=t.TEXT)
    steps = [
        ("1.", "Revisar paths sensíveis"),
        ("2.", f"Confirmar baseline PRCP [{t.AMBER}]{result.baseline_level}[/{t.AMBER}]"),
        ("3.", f"Rodar: [{t.CYAN}]{result.suggested_next_command}[/{t.CYAN}]"),
    ]
    for num, step in steps:
        next_grid.add_row(num, step)

    elevation_color = t.RED if result.task_elevation == "Hardened" else t.AMBER
    baseline_color = t.GREEN if result.baseline_level == "Standard" else t.MUTED

    left_items = [
        Text.from_markup(
            f"[bold {t.CYAN}][DevForge][/bold {t.CYAN}] Escaneando repositório..."
        ),
        Text(""),
        Text.from_markup(
            f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Stack detectada:[/{t.MUTED}] "
            f"[bold {t.TEXT}]{stack_str}[/bold {t.TEXT}]"
        ),
        Text.from_markup(
            f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]CI detectado:[/{t.MUTED}] "
            f"[bold {t.TEXT}]{ci_str}[/bold {t.TEXT}]"
        ),
    ]

    if result.databases_detected:
        databases_str = " · ".join(result.databases_detected)
        left_items.append(Text.from_markup(
            f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Banco detectado:[/{t.MUTED}] "
            f"[bold {t.TEXT}]{databases_str}[/bold {t.TEXT}]"
        ))

    left_items.extend([
        Text.from_markup(
            f"[bold {t.GREEN}]✓[/bold {t.GREEN}] [{t.MUTED}]Áreas sensíveis encontradas:[/{t.MUTED}] "
            f"[{t.AMBER}]{sensitive_str}[/{t.AMBER}]"
        ),
        Text(""),
        Text.from_markup(
            f"[{t.MUTED}]PRCP baseline do projeto:[/{t.MUTED}] "
            f"[bold {baseline_color}]{result.baseline_level}[/bold {baseline_color}]"
        ),
        Text.from_markup(
            f"[{t.MUTED}]Elevação por tarefa:[/{t.MUTED}] "
            f"[bold {elevation_color}]{result.task_elevation}[/bold {elevation_color}]"
        ),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Principais sinais[/bold {t.TEXT}]"),
        _signals_table(result.signals),
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Arquivos gerados[/bold {t.TEXT}]"),
        files_grid,
        Text(""),
        Text.from_markup(f"[bold {t.TEXT}]Próximos passos sugeridos[/bold {t.TEXT}]"),
        next_grid,
    ])

    left = Group(*left_items)

    left_panel = Panel(left, border_style=t.CYAN, padding=(1, 2))
    console.print(Columns([left_panel, _summary_panel(result)], equal=False, expand=True))
    console.print()
