# Exemplo: Plantão Fácil

Sistema de troca de plantões com autenticação e controle de papéis (admin, supervisor, operador).

## Cenário

A equipe quer implementar login com e-mail/senha e RBAC básico. Essa mudança toca:

- Autenticação
- Permissões e papéis
- Dados pessoais (e-mail)
- Rotas protegidas

O DevForge CLI classifica essa tarefa como **Hardened** e exige evidências antes do merge.

---

## Fluxo completo

```bash
# 1. Inicializar governança
devforge init

# 2. Escanear o projeto
devforge scan

# 3. Criar plano a partir da SPEC
devforge plan --spec specs/SPEC-AUTH-001.md

# 4. Implementar a mudança (simulada em apps/api/src/auth/login.py)

# 5. Verificar política
devforge policy check --diff
# → Decision: REQUIRE_APPROVAL (exit 1)
# → touches_auth, sensitive_data_possible, human_review_required

# 6. Registrar revisão humana
devforge review --issue ISSUE-AUTH-001 --approve
# → generated: .devforge/reviews/HUMAN-REVIEW-ISSUE-AUTH-001.md

# 7. Gerar evidence pack
devforge evidence --issue ISSUE-AUTH-001
# → status: ready_for_merge
# → final_decision: approved_with_human_review
```

---

## Resultado esperado do policy check

```
Decision: REQUIRE_APPROVAL
Pode avançar agora? Não ainda

Reasons:
- touches_auth
- sensitive_data_possible
- human_review_required

Required evidence:
- test_report
- human_review
- rollback_plan
- audit_log
```

---

## Estrutura do exemplo

```
examples/plantao-facil/
├── specs/
│   └── SPEC-AUTH-001.md      ← especificação da mudança
├── apps/
│   └── api/src/auth/
│       └── login.py           ← mudança sensível simulada
└── docs/
    └── rollback/
        └── SPEC-AUTH-001.md   ← rollback plan
```

---

## PR com Evidence Pack

O PR deve carregar:

```markdown
## DevForge Evidence

- Evidence Pack: `.devforge/evidence/EVID-ISSUE-AUTH-001.md`
- Policy Decision: `REQUIRE_APPROVAL`
- PRCP: `Hardened`
- Tests: pending
- Human Review: required
- Rollback Plan: present
```
