import re

from devforge_ai_cli.policy_engine.decisions import PolicyDecision
from devforge_ai_cli.policy_engine.rules import (
    AUTH_KWS,
    DATA_KWS,
    DB_CONTENT_KWS,
    DB_KWS,
    SECRET_EXPOSURE_MARKERS,
)

_AUTH_NEGATION_PATTERNS = (
    r"\bsem\s+(?:login\s*/\s*auth|login|auth|autenticação|autenticacao|senha|token|permissões|permissoes|papéis|papeis)\b",
    r"\bn[aã]o\s+(?:adicionar|usar|criar|implementar|exigir)\s+(?:login|auth|autenticação|autenticacao|senha|token|permissões|permissoes|papéis|papeis)\b",
    r"\bno\s+(?:login|auth|authentication|password|token|rbac|roles?|permissions?)\b",
    r"\bwithout\s+(?:login|auth|authentication|password|token|rbac|roles?|permissions?)\b",
)
_DB_NEGATION_PATTERNS = (
    r"\bsem\s+(?:arquivo|persistência|persistencia|banco|db|database|sqlite|schema|tabela|migração|migracao|migration|migrate)(?:(?:\s*/\s*|\s*,\s*|\s*;\s*|\s+ou\s+|\s+e\s+)(?:arquivo|persistência|persistencia|banco|db|database|sqlite|schema|tabela|migração|migracao|migration|migrate))*\b",
    r"\bn[aã]o\s+(?:adicionar|usar|criar|alterar|persistir|tocar|exigir)\s+(?:arquivo|persistência|persistencia|banco|db|database|sqlite|schema|tabela|migração|migracao|migration|migrate)\b",
    r"\bno\s+(?:file|db|database|sqlite|schema|persistence|migration)\b",
    r"\bwithout\s+(?:file|db|database|sqlite|schema|persistence|migration)\b",
)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sim", "s"}
    return bool(value)


def _strip_patterns(text: str, patterns: tuple[str, ...]) -> str:
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _policy_content_for_detection(diff_content: str) -> str:
    cleaned = diff_content.lower()
    cleaned = _strip_patterns(cleaned, _AUTH_NEGATION_PATTERNS)
    cleaned = _strip_patterns(cleaned, _DB_NEGATION_PATTERNS)
    return cleaned


def _profile_bool(profile: dict, key: str, signal_key: str | None = None) -> bool:
    if key in profile:
        return _as_bool(profile.get(key))
    return _as_bool(profile.get("signals", {}).get(signal_key or key))


def _is_low_risk_python_cli_profile(profile: dict) -> bool:
    production_impact = str(profile.get("production_impact", "low")).lower()
    return (
        profile.get("project_type") == "python_cli"
        and not _profile_bool(profile, "has_database")
        and not _profile_bool(profile, "has_auth", "touches_auth")
        and not _profile_bool(profile, "personal_data_possible")
        and not _profile_bool(profile, "external_integrations")
        and production_impact not in {"high", "critical", "production"}
    )


def _is_light_plan_policy(existing_policy: dict | None, profile: dict) -> bool:
    if not existing_policy:
        return False
    return (
        existing_policy.get("decision") == PolicyDecision.ALLOW.value
        and existing_policy.get("domain") in {"cli_session_history", "generic_cli_feature"}
        and existing_policy.get("prcp_level") in {"Minimal", "Standard"}
        and set(existing_policy.get("required_evidence", [])) <= {"test_report", "audit_log"}
        and _is_low_risk_python_cli_profile(profile)
    )


def evaluate_policy(
    changed_files: list[str],
    diff_content: str,
    profile: dict,
    existing_policy: dict | None,
) -> dict:
    reasons: list[str] = []
    diff_lower = _policy_content_for_detection(diff_content)
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
    light_plan_policy = _is_light_plan_policy(existing_policy, profile)

    if task_elevation == "Hardened" and not light_plan_policy:
        _add(reasons, "hardened_prcp")
    if _as_bool(profile.get("has_auth", signals.get("touches_auth"))):
        _add(reasons, "touches_auth")
    if _as_bool(profile.get("personal_data_possible", signals.get("personal_data_possible"))):
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
