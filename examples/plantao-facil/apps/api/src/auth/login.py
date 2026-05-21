# Exemplo de mudança sensível — login com e-mail e papel
# Esta é a mudança que o DevForge CLI detecta como REQUIRE_APPROVAL

from dataclasses import dataclass


@dataclass
class LoginResult:
    email: str
    role: str
    authenticated: bool


def login(email: str, password: str) -> LoginResult:
    """Stub de login para demonstração do DevForge CLI."""
    # Em produção: validar contra banco de dados com hash seguro
    # Aqui apenas simulamos o fluxo para fins de exemplo
    return LoginResult(email=email, role="operator", authenticated=False)


def get_role(email: str) -> str:
    """Retorna o papel do usuário."""
    # Em produção: buscar do banco de dados
    roles = {
        "admin@plantaofacil.com": "admin",
        "supervisor@plantaofacil.com": "supervisor",
    }
    return roles.get(email, "operator")
