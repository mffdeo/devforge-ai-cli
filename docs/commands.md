# Referência de Comandos — DevForge CLI

## devforge init

Bootstrap da governança local no repositório atual.

```bash
devforge init [--plain] [--json]
```

**O que cria:**

```
.devforge/
├── config.yml
├── audit/audit.ndjson
├── context/
├── evidence/
├── plans/
├── policy/
└── prcp/
```

**Exit code:** sempre 0.

---

## devforge scan

Escaneia o repositório para detectar stack, CI e áreas sensíveis.

```bash
devforge scan [--plain] [--json]
```

**Detecta:**
- Stack: Node.js, TypeScript, Python, FastAPI, Django, Docker, CI (GitHub Actions, GitLab CI...)
- Áreas sensíveis: auth, login, permissions, JWT, migrations, dados pessoais, pagamentos
- Sinais: `touches_auth`, `personal_data_possible`, `has_database`, `has_ci`...

**Gera:**
- `.devforge/prcp/project-profile.json`
- `.devforge/prcp/scan-report.md`

**Exit code:** sempre 0.

---

## devforge plan --spec

Gera Plan Pack governado a partir de uma SPEC.

```bash
devforge plan --spec specs/SPEC-AUTH-001.md [--plain] [--json]
```

**Requer:** `devforge init` e `devforge scan` anteriores.

**Lê:** SPEC em Markdown para extrair spec_id, título, objetivos, riscos.

**Gera:**
- `.devforge/plans/PLAN-SPEC-AUTH-001.md`
- `.devforge/context/context-pack.md`
- `.devforge/policy/POLICY-DECISION-SPEC-AUTH-001.json`

**Policy Decision inicial:**
- `REQUIRE_APPROVAL` se task_elevation for Hardened ou SPEC mencionar auth/permissões/dados pessoais
- `ALLOW` se não houver sinais sensíveis

**Exit code:** sempre 0.

---

## devforge policy check --diff

Avalia o diff Git atual contra políticas locais.

```bash
devforge policy check --diff [--plain] [--json]
```

**Requer:** `devforge init`, `devforge scan`, `devforge plan`.

**Analisa:**
- Arquivos modificados (staged, unstaged, untracked)
- Conteúdo do diff (limite: 50KB)
- Profile PRCP do scan
- Policy Decision prévia do plan

**Decisions:**
- `ALLOW` — mudança sem sinais sensíveis
- `REQUIRE_APPROVAL` — toca auth, permissões, dados pessoais, migration, ou PRCP Hardened
- `DENY` — diff contém marcadores de chave privada ou segredo evidente

**Gera:**
- `.devforge/policy/POLICY-CHECK-LATEST.json`

**Exit codes:**
- `0` — ALLOW
- `1` — REQUIRE_APPROVAL
- `2` — DENY

---

## devforge evidence --issue

Monta Evidence Pack auditável antes do PR/merge.

```bash
devforge evidence --issue ISSUE-AUTH-001 [--plain] [--json]
```

**Requer:** `devforge init`, `devforge scan`, `devforge plan`, `devforge policy check`.

**Coleta:**
- Changed files do último policy check
- Diff stat do Git
- Status de cada evidência obrigatória:
  - `test_report` — busca em `.devforge/test-reports/`, `coverage.xml`, `pytest*.xml`
  - `human_review` — busca em `.devforge/reviews/HUMAN-REVIEW-*.md`
  - `rollback_plan` — busca em `.devforge/rollback/ROLLBACK-*.md`
  - `audit_log` — sempre presente se `devforge init` foi rodado

**Final decisions:**
- `ready_for_pr` — ALLOW + todas evidências presentes
- `pending_human_review` — REQUIRE_APPROVAL (esperado)
- `blocked_missing_evidence` — evidências críticas ausentes
- `denied` — policy check foi DENY

**Gera:**
- `.devforge/evidence/EVID-<ISSUE-ID>.json`
- `.devforge/evidence/EVID-<ISSUE-ID>.md`

**Exit codes:**
- `0` — ready_for_pr
- `1` — pending_human_review ou blocked_missing_evidence
- `2` — denied

---

## Flags globais

| Flag | Descrição |
|---|---|
| `--plain` | Saída texto simples, sem painéis Rich |
| `--json` | Saída JSON válida no stdout |
| `--version` / `-v` | Exibe versão e sai |
| `--help` | Exibe ajuda |

---

## Exit codes

| Código | Significado |
|---|---|
| `0` | Sucesso / ALLOW / ready_for_pr |
| `1` | REQUIRE_APPROVAL / evidência pendente / erro de precondição |
| `2` | DENY / mudança bloqueada |
