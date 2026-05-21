from pathlib import Path

from devforge_ai_cli.core.paths import get_devforge_dir


def is_initialized(cwd: Path | None = None) -> bool:
    return get_devforge_dir(cwd).exists()


def require_init(cwd: Path | None = None) -> None:
    if not is_initialized(cwd):
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print(
            f"[{t.AMBER}]⚠ Repositório não inicializado. Execute: devforge init[/{t.AMBER}]"
        )
        raise SystemExit(1)
