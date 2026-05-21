# Exemplo: Plantão Fácil

Sistema de troca de plantões com autenticação e controle de papéis (admin, supervisor, operador).

## Fluxo DevForge CLI

```bash
devforge init
devforge scan
devforge plan --spec specs/SPEC-AUTH-001.md
devforge policy check --diff
devforge evidence --issue ISSUE-AUTH-001
```

## Por que o PRCP é Hardened aqui?

Esta mudança toca: autenticação, permissões, dados pessoais e rotas protegidas.
O DevForge CLI eleva o risco para `Hardened` e exige: relatório de testes,
plano de rollback, revisão humana e trilha de auditoria.
