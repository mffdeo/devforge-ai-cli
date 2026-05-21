import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.git import detect_project_name
from devforge_ai_cli.core.paths import get_audit_file
from devforge_ai_cli.core.project import require_init
from devforge_ai_cli.core.scanner import run_scan


def run_scan_cmd(plain: bool, output_json: bool, cwd: Path | None = None) -> None:
    base = cwd or Path.cwd()
    require_init(base)

    project_name = detect_project_name(base)
    result = run_scan(project_name=project_name, base=base)

    append_event(get_audit_file(base), {
        "event": "scan.completed",
        "project": result.project_name,
        "detected_stack": result.detected_stack,
        "baseline_level": result.baseline_level,
        "task_elevation": result.task_elevation,
        "signals": result.signals,
        "generated_files": result.generated_files,
    })

    if output_json:
        print(json.dumps({
            "project_name": result.project_name,
            "detected_stack": result.detected_stack,
            "ci_detected": result.ci_detected,
            "databases_detected": result.databases_detected,
            "sensitive_areas": result.sensitive_areas,
            "signals": result.signals,
            "baseline_level": result.baseline_level,
            "task_elevation": result.task_elevation,
            "generated_files": result.generated_files,
            "suggested_next_spec": result.suggested_next_spec,
            "next_steps": [
                "Revisar paths sensíveis",
                "Confirmar baseline PRCP",
                f"devforge plan --spec {result.suggested_next_spec}",
            ],
        }))
    elif plain:
        print(f"[DevForge] Stack detectada: {', '.join(result.detected_stack) or 'nenhuma'}")
        if result.ci_detected:
            print(f"[DevForge] CI detectado: {result.ci_detected}")
        if result.databases_detected:
            print(f"[DevForge] Banco detectado: {', '.join(result.databases_detected)}")
        print(f"[DevForge] Áreas sensíveis: {', '.join(result.sensitive_areas) or 'nenhuma'}")
        print(f"[DevForge] PRCP baseline: {result.baseline_level}")
        print(f"[DevForge] Elevação por tarefa: {result.task_elevation}")
        for f in result.generated_files:
            print(f"  {f}")
        print(f"[DevForge] Próximo: devforge plan --spec {result.suggested_next_spec}")
    else:
        from devforge_ai_cli.ui.renderers.scan_screen import render_scan
        render_scan(result)
