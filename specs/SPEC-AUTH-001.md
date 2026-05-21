# SPEC-AUTH-001 — Login e RBAC básico

## Objetivo

Permitir login com e-mail e senha e controle básico de papéis no sistema.

## História de usuário

Como supervisor, quero acessar o sistema com login seguro para aprovar ou recusar solicitações.

## Critérios de aceite

- AC-001: Usuário consegue fazer login com e-mail e senha.
- AC-002: Usuário não autenticado não acessa rotas protegidas.
- AC-003: Admin consegue visualizar usuários cadastrados.
- AC-004: Operador não consegue acessar área administrativa.
- AC-005: Erros de login não vazam informação sensível.

## Fora de escopo

- Login social.
- SSO.
- MFA.
- Recuperação de senha.

## Riscos

- Toca autenticação.
- Toca permissões.
- Pode envolver dados pessoais.
- Pode bloquear acesso ao sistema se implementado errado.

## Evidências esperadas

- Test report.
- Human review.
- Rollback plan.
