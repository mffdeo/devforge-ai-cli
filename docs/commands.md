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
- Áreas sensíveis: auth, login, permissions, JWT, migrations, dados pessoais, pagamentos, database, sqlite, schema
- Bancos por arquivo/conteúdo: `db_create.py`, `db.py`, `database.py`, `models.py`, `schema.sql`, `migrations/`, `alembic/`, `*.sqlite`, `*.sqlite3`, `*.db`, e padrões como `sqlite3`, `SQLAlchemy`, `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, `db.create_all`
- Sinais: `touches_auth`, `personal_data_possible`, `has_database`, `has_ci`...

**Próximo passo sugerido:**
- Primeira `.md` em `specs/` em ordem alfabética; preferência por uma SPEC com `AUTH` no nome se o projeto tiver sinais de auth/login/permissions. Fallback: `specs/SPEC-EXAMPLE-001.md`.

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
Quando a política retorna `REQUIRE_APPROVAL`, rode `devforge review --issue <ISSUE-ID>` antes de gerar um Evidence Pack pronto para merge.

**Coleta:**
- Changed files do último policy check
- Diff stat do Git
- Status de cada evidência obrigatória:
  - `test_report` — busca em `.devforge/test-reports/`, `coverage.xml`, `pytest*.xml`
  - `human_review` — busca em `.devforge/reviews/HUMAN-REVIEW-*.md`
  - `rollback_plan` — busca em `.devforge/rollback/ROLLBACK-*.md`
  - `audit_log` — sempre presente se `devforge init` foi rodado

**Final decisions:**
- `allowed` — ALLOW + evidências mínimas presentes
- `approved_with_human_review` — REQUIRE_APPROVAL + todas evidências obrigatórias presentes, incluindo `human_review`
- `pending_human_review` — REQUIRE_APPROVAL + `human_review` ausente
- `pending_required_evidence` — evidências obrigatórias ausentes
- `denied` — policy check foi DENY

**Gera:**
- `.devforge/evidence/EVID-<ISSUE-ID>.json`
- `.devforge/evidence/EVID-<ISSUE-ID>.md`

**Exit codes:**
- `0` — ready_for_merge
- `1` — pending_human_review ou pending_required_evidence
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
| `0` | Sucesso / ALLOW aprovado / REQUIRE_APPROVAL aprovado com revisão humana |
| `1` | REQUIRE_APPROVAL / evidência pendente / erro de precondição |
| `2` | DENY / mudança bloqueada |
