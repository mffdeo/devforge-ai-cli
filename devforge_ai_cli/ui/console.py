from rich.console import Console
from rich.theme import Theme

from devforge_ai_cli.ui import theme as t

_theme = Theme({
    "cyan": t.CYAN,
    "green": t.GREEN,
    "amber": t.AMBER,
    "red": t.RED,
    "purple": t.PURPLE,
    "df.text": t.TEXT,
    "df.muted": t.MUTED,
})

console = Console(theme=_theme, highlight=False)
