from devforge_ai_cli.policy_engine.decisions import PolicyDecision
from devforge_ai_cli.policy_engine.rules import evaluate_rules


def run_policy_check(diff_text: str) -> dict:
    result = evaluate_rules(diff_text)
    triggered = result["triggered"]

    decision = PolicyDecision.ALLOW if not triggered else PolicyDecision.REQUIRE_APPROVAL
    required_evidence = ["test_report", "human_review", "rollback_plan"] if triggered else []

    return {
        "decision": decision.value,
        "reasons": triggered,
        "required_evidence": required_evidence,
        "can_proceed": decision == PolicyDecision.ALLOW,
    }
