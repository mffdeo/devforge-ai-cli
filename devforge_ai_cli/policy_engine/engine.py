from devforge_ai_cli.policy_engine.decisions import PolicyDecision
from devforge_ai_cli.policy_engine.rules import (
    AUTH_KWS,
    DATA_KWS,
    DB_CONTENT_KWS,
    DB_KWS,
    SECRET_EXPOSURE_MARKERS,
)


def evaluate_policy(
    changed_files: list[str],
    diff_content: str,
    profile: dict,
    existing_policy: dict | None,
) -> dict:
    reasons: list[str] = []
    diff_lower = diff_content.lower()
    all_paths = " ".join(changed_files).lower()

    # ── no changes ────────────────────────────────────────────────────────────
    if not changed_files and not diff_content.strip():
        return {
            "decision": PolicyDecision.ALLOW.value,
            "can_advance_now": True,
            "exit_code": 0,
            "changed_files": [],
            "files_count": 0,
            "reasons": ["no_changes_detected"],
            "required_evidence": ["audit_log"],
            "recommended_actions": [],
        }

    # ── file path signals ─────────────────────────────────────────────────────
    if any(kw in all_paths for kw in AUTH_KWS):
        reasons.append("touches_auth")
    if any(kw in all_paths for kw in DATA_KWS):
        _add(reasons, "sensitive_data_possible")
    if any(kw in all_paths for kw in DB_KWS):
        _add(reasons, "db_migration_detected")

    # ── diff content signals ──────────────────────────────────────────────────
    if diff_lower:
        if any(kw in diff_lower for kw in AUTH_KWS):
            _add(reasons, "touches_auth")
        if any(kw in diff_lower for kw in DATA_KWS):
            _add(reasons, "sensitive_data_possible")
        if any(kw in diff_lower for kw in DB_CONTENT_KWS):
            _add(reasons, "db_migration_detected")

    # ── PRCP signals ──────────────────────────────────────────────────────────
    prcp = profile.get("prcp", {})
    signals = profile.get("signals", {})
    task_elevation = prcp.get("task_elevation", "Standard")

    if task_elevation == "Hardened":
        _add(reasons, "hardened_prcp")
    if signals.get("touches_auth"):
        _add(reasons, "touches_auth")
    if signals.get("personal_data_possible"):
        _add(reasons, "sensitive_data_possible")

    # ── existing policy ───────────────────────────────────────────────────────
    if existing_policy and existing_policy.get("decision") == "REQUIRE_APPROVAL":
        _add(reasons, "previous_policy_require_approval")

    # ── human review required ─────────────────────────────────────────────────
    needs_human = any(r in reasons for r in (
        "touches_auth", "sensitive_data_possible", "hardened_prcp",
        "previous_policy_require_approval",
    ))
    if needs_human:
        _add(reasons, "human_review_required")

    # ── secret exposure detection (DENY) ─────────────────────────────────────
    is_deny = any(marker in diff_lower for marker in SECRET_EXPOSURE_MARKERS)

    # ── required evidence ─────────────────────────────────────────────────────
    required_evidence: list[str] = []
    if changed_files:
        required_evidence.append("test_report")
    if "human_review_required" in reasons:
        required_evidence.append("human_review")
    needs_rollback = (
        any(r in reasons for r in ("touches_auth", "sensitive_data_possible", "hardened_prcp", "db_migration_detected"))
        or task_elevation == "Hardened"
    )
    if needs_rollback:
        required_evidence.append("rollback_plan")
    required_evidence.append("audit_log")

    # ── decision ──────────────────────────────────────────────────────────────
    if is_deny:
        decision = PolicyDecision.DENY
        can_advance = False
        exit_code = 2
    elif reasons:
        decision = PolicyDecision.REQUIRE_APPROVAL
        can_advance = False
        exit_code = 1
    else:
        decision = PolicyDecision.ALLOW
        can_advance = True
        exit_code = 0

    # ── recommended actions ───────────────────────────────────────────────────
    recommended: list[str] = []
    if "test_report" in required_evidence:
        recommended.append("Rodar testes e anexar test_report")
    if "human_review" in required_evidence:
        recommended.append("Solicitar revisão humana")
    if "rollback_plan" in required_evidence:
        recommended.append("Criar rollback plan")
    recommended.append("Gerar evidence pack: devforge evidence --issue <ID>")

    return {
        "decision": decision.value,
        "can_advance_now": can_advance,
        "exit_code": exit_code,
        "changed_files": changed_files,
        "files_count": len(changed_files),
        "reasons": reasons,
        "required_evidence": required_evidence,
        "recommended_actions": recommended,
    }


def _add(lst: list[str], item: str) -> None:
    if item not in lst:
        lst.append(item)
