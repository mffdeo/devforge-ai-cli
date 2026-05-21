# Contributing to DevForge CLI

Contributions are welcome! This document describes how to set up your environment, run tests, and submit changes.

---

## Setup local

```bash
git clone https://github.com/mffdeo/devforge-ai-cli.git
cd devforge-ai-cli
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Rodar testes

```bash
pytest -v
```

## Lint

```bash
ruff check .
```

---

## Padrão de branches

- `main` — estável, CI deve passar sempre
- `feat/<nome>` — nova funcionalidade
- `fix/<nome>` — correção de bug
- `docs/<nome>` — apenas documentação
- `chore/<nome>` — manutenção sem mudança de comportamento

---

## Como abrir uma issue

Use os templates em `.github/ISSUE_TEMPLATE/`:

- **Bug report** — algo que deveria funcionar e não funciona
- **Feature request** — ideia de nova funcionalidade
- **Policy pack request** — proposta de novo conjunto de regras

---

## Como propor um policy pack

Policy packs ficam em `policy-packs/`. Um pack é um arquivo YAML com regras de decisão:

```yaml
name: my-pack
version: "0.1.0"
description: Descrição do pack.

rules:
  - id: my-rule
    description: O que essa regra detecta
    patterns: [keyword1, keyword2]
    decision: REQUIRE_APPROVAL
    reasons: [touches_sensitive_area]
```

Abra uma issue com o template `policy_pack_request.md` antes de submeter um PR.

---

## Regras obrigatórias para o MVP

1. **Não adicionar chamadas LLM** sem discussão e ADR.
2. **Não adicionar cloud/SaaS** sem discussão e ADR.
3. **Não criar daemon** ou processo em background.
4. **Não adicionar telemetria silenciosa**.
5. **Manter `--plain` e `--json`** funcionando em qualquer novo comando.
6. **Manter exit codes** consistentes: 0=ALLOW, 1=REQUIRE_APPROVAL, 2=DENY.
7. **Escrever testes** para qualquer novo comando ou lógica de decisão.
8. **Não quebrar `docs/index.html`** — a landing page é parte do repositório.

---

## Pull request checklist

Veja `.github/pull_request_template.md`.

---

## Dúvidas

Abra uma issue ou discussion no repositório.
