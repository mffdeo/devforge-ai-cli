SENSITIVE_PATTERNS = [
    "auth", "authentication", "autenticação",
    "permission", "permissão", "authorization",
    "password", "senha", "secret", "token",
    "personal", "pessoal", "cpf", "email",
    "payment", "pagamento", "billing",
    "database", "migration", "schema",
    "admin", "root",
    "prod", "production", "produção",
]

PRCP_LEVELS = ["Minimal", "Standard", "Hardened", "Critical"]


def classify_prcp(signals: list[str]) -> str:
    count = len(signals)
    if count == 0:
        return "Minimal"
    elif count <= 2:
        return "Standard"
    elif count <= 5:
        return "Hardened"
    return "Critical"
