# SPEC-AUTH-001 — Login e RBAC básico

## Objetivo

Permitir login com e-mail e senha e controle básico de papéis no sistema Plantão Fácil.

## História de usuário

Como supervisor, quero acessar o sistema com login seguro para aprovar ou recusar solicitações de troca de plantão.

## Critérios de aceite

- AC-001: Usuário consegue fazer login com e-mail e senha.
- AC-002: Usuário não autenticado não acessa rotas protegidas.
- AC-003: Admin consegue visualizar lista de usuários cadastrados.
- AC-004: Operador não consegue acessar área administrativa.
- AC-005: Erros de login não vazam informação sensível (sem hint sobre se e-mail existe).

## Fora de escopo

- Login social (Google, GitHub).
- SSO corporativo.
- MFA.
- Recuperação de senha.
- Refresh tokens.

## Riscos

- Toca autenticação — área sensível de alta criticidade.
- Toca permissões e papéis (RBAC) — pode bloquear acesso ao sistema se implementado errado.
- Pode envolver dados pessoais (e-mail dos usuários).
- Falha de autenticação pode comprometer a segurança de todo o sistema.

## Evidências esperadas

- Test report com cobertura de auth e permissões.
- Human review de tech lead ou arquiteto de segurança.
- Rollback plan documentado.
- Audit trail atualizado.
