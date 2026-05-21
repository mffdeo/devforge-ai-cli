import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.agent_instructions import render_agent_instructions
from devforge_ai_cli.core.config import DevForgeConfig, write_config
from devforge_ai_cli.core.git import detect_project_name
from devforge_ai_cli.core.paths import get_audit_file, get_config_file, get_devforge_dir

SUBDIRS = ["prcp", "context", "plans", "policy", "evidence", "pr", "audit"]


def run_init(plain: bool, output_json: bool, cwd: Path | None = None) -> None:
    base = cwd or Path.cwd()
    devforge_dir = get_devforge_dir(base)

    if devforge_dir.exists():
        if output_json:
            print(json.dumps({"status": "already_initialized", "devforge_dir": str(devforge_dir)}))
        elif plain:
            print(f"[DevForge] .devforge/ já existe em: {devforge_dir}")
        else:
            from devforge_ai_cli.ui import theme as t
            from devforge_ai_cli.ui.console import console
            console.print(f"[{t.AMBER}]⚠ .devforge/ já existe neste repositório.[/{t.AMBER}]")
        return

    project_name = detect_project_name(base)

    devforge_dir.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (devforge_dir / subdir).mkdir(exist_ok=True)

    config = DevForgeConfig(project_name=project_name)
    write_config(get_config_file(base), config)

    render_agent_instructions(base)

    append_event(get_audit_file(base), {
        "event": "init",
        "project": project_name,
        "edition": "community",
    })

    if output_json:
        print(json.dumps({
            "status": "ok",
            "project": project_name,
            "devforge_dir": str(devforge_dir),
        }))
    elif plain:
        print(f"[DevForge] Setup concluído para: {project_name}")
        print(f"Estrutura criada em: {devforge_dir}")
    else:
        from devforge_ai_cli.ui.renderers.init_screen import render_init
        render_init(project_name=project_name, devforge_dir=devforge_dir)
