HIGH_RISK_PATTERNS = [
    "auth", "authentication", "permission", "authorization",
    "password", "secret", "token", "personal", "cpf", "email",
    "payment", "billing", "database", "migration", "admin",
]


def evaluate_rules(diff_text: str) -> dict:
    text = diff_text.lower()
    triggered = [
        f"touches_{p}" for p in HIGH_RISK_PATTERNS if p in text
    ]
    return {"triggered": triggered}
