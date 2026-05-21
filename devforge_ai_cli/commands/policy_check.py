from pathlib import Path

from devforge_ai_cli.core.project import require_init


def run_policy_check(diff: bool, plain: bool, output_json: bool, cwd: Path | None = None) -> None:
    require_init(cwd)
    if output_json:
        import json
        print(json.dumps({"status": "not_implemented", "command": "policy check"}))
        return
    if plain:
        print("devforge policy check: coming soon")
        return
    from devforge_ai_cli.ui import theme as t
    from devforge_ai_cli.ui.console import console
    console.print(f"[{t.AMBER}]devforge policy check — em breve[/{t.AMBER}]")
