AUTH_KWS = {
    "auth", "login", "logout", "jwt", "token", "secret",
    "password", "rbac", "role", "roles", "permission", "permissions", "middleware",
}
DATA_KWS = {"user", "users", "cpf", "email"}
PAYMENT_KWS = {"payment", "billing"}
DB_KWS = {"migration", "database"}
DB_CONTENT_KWS = {"migration", "alter table", "create table", "drop table"}
CI_INFRA_KWS = {"docker-compose", "dockerfile", ".github/workflows"}

SENSITIVE_PATH_KWS: list[str] = sorted(
    AUTH_KWS | DATA_KWS | PAYMENT_KWS | DB_KWS | CI_INFRA_KWS
)

SENSITIVE_CONTENT_KWS: list[str] = sorted(
    AUTH_KWS | DATA_KWS | PAYMENT_KWS | DB_CONTENT_KWS
)

SECRET_EXPOSURE_MARKERS: list[str] = [
    "-----begin rsa private key-----",
    "-----begin private key-----",
    "-----begin ec private key-----",
    "aws_secret_access_key =",
    "aws_access_key_id =",
]
