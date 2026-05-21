# DevForge CLI

> **Local-first governance CLI for AI-assisted SDLC.**
> Classifique risco, controle contexto, aplique políticas e gere evidências auditáveis antes do merge.

[![CI](https://github.com/mffdeo/devforge-ai-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mffdeo/devforge-ai-cli/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## O que é o DevForge CLI?

**DevForge CLI** é uma ferramenta open-source para ajudar desenvolvedores e times a governar mudanças feitas com IA antes do merge.

Ele não é uma IDE. Ele não é um agente de código. Ele não substitui Cursor, Claude Code, Codex, Copilot ou qualquer outro agente.

> **Agentes executam. DevForge governa.**

Antes de uma mudança entrar no repositório principal, o DevForge CLI ajuda a responder:

- Essa mudança toca áreas sensíveis?
- Qual é o risco proporcional da alteração?
- Qual contexto a IA poderia usar?
- Quais políticas se aplicam?
- Quais evidências precisam existir antes do merge?
- Existe trilha auditável do que aconteceu?

---

## Fluxo principal

```
init → scan → plan → policy check → evidence
```

![DevForge CLI — fluxo principal](docs/assets/screenshots/how-it-works.png)

> Um único repositório local detém todo o estado de governança.
> SPEC, plano, contexto, política, evidência e trilha de auditoria
> ficam dentro do projeto — sem cloud login, saídas em Markdown + JSON,
> revisão humana quando o risco exige.

O diagrama acima resume a sequência em três blocos:

- **R1 — Author + Workspace.** O autor escreve a `SPEC`, roda `devforge init` e o repositório passa a carregar `.devforge/config.yml` ao lado de IDE, agente e Git.
- **R2 — Scan + Governance core.** `devforge scan` classifica risco e detecta áreas sensíveis. `devforge plan --spec` produz o **PRCP baseline**, o **Context Pack** e a **Policy Decision** (`ALLOW` / `REQUIRE_APPROVAL`).
- **R3 — Policy gate + Review.** `devforge policy check --diff` avalia o diff contra a política. `devforge evidence --issue …` emite o **Evidence Pack** auditável (`EVID-…`) que acompanha o PR.

---

## Instalação

### A partir do GitHub (recomendado para o MVP)

O pacote ainda não foi publicado no PyPI. Instale diretamente do repositório:

**Com pipx:**
```bash
pipx install git+https://github.com/mffdeo/devforge-ai-cli.git
```

**Com uv:**
```bash
uv tool install git+https://github.com/mffdeo/devforge-ai-cli.git
```

Depois:
```bash
devforge --version
```

### Para desenvolvimento local

```bash
git clone https://github.com/mffdeo/devforge-ai-cli.git
cd devforge-ai-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
devforge --help
```

---

## Quickstart

```bash
# 1. Inicialize a governança local
devforge init

# 2. Escaneie stack, risco e áreas sensíveis
devforge scan

# 3. Crie uma SPEC de mudança
mkdir -p specs
# edite specs/SPEC-AUTH-001.md

# 4. Gere um plano governado
devforge plan --spec specs/SPEC-AUTH-001.md

# 5. Implemente com seu editor, agente ou IDE

# 6. Verifique política antes do merge
devforge policy check --diff

# 7. Gere o pacote de evidência
devforge evidence --issue ISSUE-AUTH-001
```

---

## Exemplo: Plantão Fácil

Imagine um sistema de troca de plantões. Você quer implementar login com e-mail/senha e controle de papéis (admin, supervisor, operador).

Essa mudança toca autenticação, permissões e dados pessoais. O DevForge CLI eleva o risco para `Hardened` e exige evidências antes do merge.

Ver exemplo completo em [`examples/plantao-facil/`](examples/plantao-facil/).

---

## Comandos

| Comando | O que faz |
|---|---|
| `devforge init` | Cria `.devforge/` com estrutura local |
| `devforge scan` | Detecta stack, CI e áreas sensíveis |
| `devforge plan --spec <arquivo>` | Gera Plan Pack, Context Pack e Policy Decision |
| `devforge policy check --diff` | Avalia diff Git contra políticas locais |
| `devforge evidence --issue <ID>` | Monta Evidence Pack auditável |

**Opções globais disponíveis em todos os comandos:**
- `--plain` — saída texto simples (sem Rich)
- `--json` — saída JSON válida para automação
- `--version` — exibe a versão

**Exit codes:**
- `0` — ALLOW / pronto para PR
- `1` — REQUIRE_APPROVAL / evidência pendente
- `2` — DENY / mudança bloqueada

---

## Saídas geradas

```
.devforge/
├── config.yml
├── audit/
│   └── audit.ndjson
├── context/
│   └── context-pack.md
├── evidence/
│   ├── EVID-ISSUE-AUTH-001.json
│   └── EVID-ISSUE-AUTH-001.md
├── plans/
│   └── PLAN-SPEC-AUTH-001.md
├── policy/
│   ├── POLICY-CHECK-LATEST.json
│   └── POLICY-DECISION-SPEC-AUTH-001.json
└── prcp/
    ├── project-profile.json
    └── scan-report.md
```

---

## O que o DevForge CLI não é

- Não é uma IDE
- Não é um agente de código
- Não chama LLM por padrão
- Não envia código para a nuvem
- Não requer cloud login
- Não é um SaaS
- Não substitui GitHub, GitLab ou Jira

No MVP: `local-first · determinístico · sem cloud · Markdown + JSON · auditável`

---

## Roadmap

### MVP Community (v0.1.0)
- [x] `devforge init`
- [x] `devforge scan`
- [x] `devforge plan`
- [x] `devforge policy check`
- [x] `devforge evidence`
- [x] audit trail local (NDJSON)
- [x] saída Markdown + JSON
- [x] `--plain` e `--json`
- [x] exemplo Plantão Fácil
- [x] GitHub Pages
- [x] CI com pytest

### Próximo
- [ ] GitHub Actions integration
- [ ] policy packs customizados
- [ ] múltiplos perfis PRCP
- [ ] integração MCP local
- [ ] adapters para agentes e IDEs

---

## Contribuindo

Contribuições são bem-vindas. Veja [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/mffdeo/devforge-ai-cli.git
cd devforge-ai-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
```

---

## Licença

MIT License. Ver [LICENSE](LICENSE).

---

> **Before merging AI-assisted code, run DevForge.**
