from pathlib import Path

from devforge_ai_cli.core.project import require_init


def run_plan(spec: str, plain: bool, output_json: bool, cwd: Path | None = None) -> None:
    require_init(cwd)
    if output_json:
        import json
        print(json.dumps({"status": "not_implemented", "command": "plan", "spec": spec}))
        return
    if plain:
        print(f"devforge plan --spec {spec}: coming soon")
        return
    from devforge_ai_cli.ui import theme as t
    from devforge_ai_cli.ui.console import console
    console.print(f"[{t.AMBER}]devforge plan — em breve[/{t.AMBER}]")
