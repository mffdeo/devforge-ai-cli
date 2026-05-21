# Rollback Plan — SPEC-AUTH-001

## Objetivo

Descrever o procedimento de rollback caso a implementação de login/RBAC cause problemas em produção.

## Gatilhos para rollback

- Taxa de erro de login > 5% nos primeiros 30 minutos após deploy.
- Usuários admin bloqueados do sistema.
- Falha em criar sessão para qualquer papel.
- Erros 500 em rotas de autenticação.

## Procedimento

1. Reverter o deploy para a versão anterior via pipeline CI/CD.
2. Validar que o login funciona com usuário de teste.
3. Notificar equipe via canal de incidentes.
4. Abrir issue de post-mortem.

## Tempo estimado de rollback

< 5 minutos com pipeline automatizado.

## Contato de emergência

- Tech Lead: @supervisor
- Operações: canal #ops no Slack

## Referência

- SPEC: SPEC-AUTH-001
- Issue: ISSUE-AUTH-001
- Evidence Pack: EVID-ISSUE-AUTH-001
