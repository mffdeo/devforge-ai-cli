# Security Policy

## Reportar uma vulnerabilidade

Se você encontrar uma vulnerabilidade de segurança, **não abra uma issue pública**.

Envie um e-mail para: cursosacessototal@gmail.com

Inclua:
- Descrição do problema
- Passos para reproduzir
- Impacto potencial
- Versão afetada

Você receberá uma resposta em até 72 horas.

---

## Compromisso local-first

O DevForge CLI é projetado para operar **sem enviar dados para fora da sua máquina**:

- Nenhum código ou diff é enviado para servidores externos.
- Nenhuma telemetria silenciosa.
- Nenhuma autenticação em serviços de nuvem.
- Todos os artefatos ficam em `.devforge/` dentro do seu repositório.

---

## Cuidado com audit logs e secrets

O audit trail em `.devforge/audit/audit.ndjson` pode conter nomes de arquivos e metadados de diff. **Não faça commit de `.devforge/` se o seu repositório for público**, a menos que você tenha revisado o conteúdo.

Recomendação: adicione `.devforge/` ao `.gitignore` do seu projeto se não quiser versionar os artefatos de governança.

---

## Detecção de secrets no policy check

O comando `devforge policy check --diff` inclui detecção conservadora de possíveis exposições de segredos (chaves privadas RSA, variáveis AWS). Se detectado, o resultado é `DENY` (exit code 2). Essa detecção é local e baseada em padrões simples — não substitui um scanner especializado.

---

## Escopo de segurança do MVP v0.1.0

- Análise local de diff Git
- Detecção de padrões por regex simples
- Sem execução de código do usuário
- Sem parsing de binários
- Sem acesso a rede (exceto o que o próprio Git já faz)

---

## Dependências

As dependências principais são: `typer`, `rich`, `pydantic`, `pyyaml`, `jinja2`. Mantenha-as atualizadas. Use `pip audit` ou `uv audit` para verificar vulnerabilidades conhecidas.
