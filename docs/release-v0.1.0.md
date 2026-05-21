# Release v0.1.0 — Community MVP

## O que entra no MVP

O DevForge CLI v0.1.0 entrega o fluxo principal de governança local:

```
init → scan → plan → policy check → review → evidence
```

### Comandos incluídos

| Comando | Status |
|---|---|
| `devforge init` | Funcional |
| `devforge scan` | Funcional |
| `devforge plan --spec` | Funcional |
| `devforge policy check --diff` | Funcional |
| `devforge review --issue` | Funcional |
| `devforge evidence --issue` | Funcional |

### Artefatos gerados

- `.devforge/config.yml`
- `.devforge/prcp/project-profile.json`
- `.devforge/prcp/scan-report.md`
- `.devforge/plans/PLAN-<SPEC-ID>.md`
- `.devforge/context/context-pack.md`
- `.devforge/policy/POLICY-DECISION-<SPEC-ID>.json`
- `.devforge/policy/POLICY-CHECK-LATEST.json`
- `.devforge/reviews/HUMAN-REVIEW-<SPEC-ID>.md`
- `.devforge/evidence/EVID-<ISSUE-ID>.json`
- `.devforge/evidence/EVID-<ISSUE-ID>.md`
- `.devforge/audit/audit.ndjson`

---

## O que não entra no v0.1.0

- Publicação no PyPI (instalar via GitHub)
- GitHub Actions integration como gate automático
- Policy packs customizados via arquivo externo
- MCP integration
- Dashboard web
- Múltiplos perfis PRCP configuráveis
- Suporte Windows nativo (não testado)
- Enterprise features

---

## Limitações conhecidas

1. **Stack detection** é baseada em heurísticas simples de arquivos e conteúdo. Pode não detectar todas as tecnologias.
2. **Detecção de secrets** (DENY) é conservadora — baseada em marcadores explícitos como `-----BEGIN RSA PRIVATE KEY-----`. Não substitui scanners especializados.
3. **Git diff** detecta arquivos staged, unstaged e untracked. Em repos com muitos arquivos untracked não relacionados, pode gerar ruído.
4. **PRCP classification** é determinística — não usa LLM. Pode classificar como Hardened mais do que necessário para projetos simples que têm "auth" no nome de algum arquivo.
5. **Python 3.12+ obrigatório** — não testado em versões anteriores.

---

## Como testar localmente

```bash
git clone https://github.com/mffdeo/devforge-ai-cli.git
cd devforge-ai-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Rodar testes
pytest -v

# Rodar lint
ruff check .

# Testar o fluxo completo
mkdir -p /tmp/test-project && cd /tmp/test-project
git init && git config user.email "test@test.com" && git config user.name "Test"
echo "# Test" > README.md && git add . && git commit -m "init"

devforge init
devforge scan
mkdir -p specs
# criar specs/SPEC-001.md
devforge plan --spec specs/SPEC-001.md
devforge policy check --diff
devforge evidence --issue ISSUE-001
```

---

## Como instalar como usuário real

```bash
pipx install git+https://github.com/mffdeo/devforge-ai-cli.git
devforge --help
```

---

## Como contribuir no v0.1.0

Ver [CONTRIBUTING.md](../CONTRIBUTING.md).

As contribuições mais bem-vindas agora são:

1. **Testar em projetos reais** e abrir issues com feedback
2. **Policy packs** para stacks específicas (Rails, Java, Go...)
3. **Exemplos** além do Plantão Fácil
4. **Documentação** em inglês
5. **Windows support** — não testado
