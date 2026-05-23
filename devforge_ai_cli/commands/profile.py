from __future__ import annotations

import json
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.paths import get_audit_file, get_devforge_dir
from devforge_ai_cli.core.project import require_init


def run_profile_approve(
    yes: bool,
    plain: bool,
    output_json: bool,
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)
    profile_path = get_devforge_dir(base) / "prcp" / "project-profile.json"
    if not profile_path.exists():
        result = {
            "approved": False,
            "exit_code": 1,
            "reason": "project-profile.json não encontrado. Rode: devforge scan",
        }
        _emit(result, plain=plain, output_json=output_json)
        return 1

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not output_json:
        _print_summary(profile)

    approved = yes
    if not yes and not output_json:
        answer = input("Aprovar Project Profile? [y/N] ").strip().lower()
        approved = answer in {"y", "yes", "s", "sim"}

    if not approved:
        result = {
            "approved": False,
            "exit_code": 1,
            "profile_status": profile.get("profile_status", "draft"),
            "reason": "Project Profile não aprovado.",
        }
        _emit(result, plain=plain, output_json=output_json)
        return 1

    profile["profile_status"] = "approved"
    profile["approved_by_user"] = True
    profile["requires_user_approval"] = False
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    append_event(get_audit_file(base), {
        "event": "project_profile.approved",
        "project_name": profile.get("project_name"),
        "project_type": profile.get("project_type"),
        "confidence": profile.get("confidence"),
        "source": profile.get("source"),
        "profile_status": "approved",
    })

    result = {
        "approved": True,
        "exit_code": 0,
        "profile_status": "approved",
        "profile_path": str(profile_path.relative_to(base)),
        "source": profile.get("source"),
        "approved_by_user": True,
    }
    _emit(result, plain=plain, output_json=output_json)
    return 0


def _print_summary(profile: dict) -> None:
    prcp = profile.get("prcp", {})
    print("[DevForge] Project Profile")
    print(f"project_type: {profile.get('project_type', 'unknown')}")
    print(f"stack: {', '.join(profile.get('detected_stack', [])) or 'unknown'}")
    print(f"architecture_summary: {profile.get('architecture_summary', '')}")
    print(f"has_database: {str(profile.get('has_database', False)).lower()}")
    print(f"has_auth: {str(profile.get('has_auth', False)).lower()}")
    print(f"personal_data_possible: {str(profile.get('personal_data_possible', False)).lower()}")
    print(f"external_integrations: {str(profile.get('external_integrations', False)).lower()}")
    print(f"prcp_baseline: {prcp.get('baseline_level', 'unknown')}")
    print(f"task_elevation: {prcp.get('task_elevation', 'unknown')}")
    print(f"confidence: {profile.get('confidence', 'unknown')}")
    print(f"source: {profile.get('source', 'unknown')}")
    print(f"profile_status: {profile.get('profile_status', 'draft')}")
    if profile.get("assumptions"):
        print("assumptions:")
        for item in profile["assumptions"]:
            print(f"- {item}")
    if profile.get("gray_areas"):
        print("gray_areas:")
        for item in profile["gray_areas"]:
            print(f"- {item}")


def _emit(result: dict, plain: bool, output_json: bool) -> None:
    if output_json:
        print(json.dumps(result, ensure_ascii=False))
        return
    if result.get("approved"):
        print("[DevForge] Project Profile aprovado.")
        print(f"profile_status: {result['profile_status']}")
        return
    print(f"[DevForge] Project Profile não aprovado: {result.get('reason')}")
