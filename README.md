# DevForge CLI Landing Page

Landing page estática e responsiva do **DevForge CLI**, criada para ficar visualmente fiel à imagem de referência `docs/reference/langPage.png`.

## Como abrir

Abra `index.html` diretamente no navegador.

## Como rodar com servidor local

```bash
python -m http.server 3000
```

Depois acesse:

```text
http://localhost:3000
```

## Estrutura

```text
devforge-cli-landing/
├── index.html
├── styles.css
├── script.js
├── assets/
│   └── devforge-logo.svg
└── docs/
    └── reference/
        └── langPage.png
```

## Ajustes principais

- Dark mode técnico com grid, brilho e acentos em azul neon.
- Hero com terminal grande.
- Cards de resumo.
- Fluxo: Init → Scan → Plan → Policy Check → Evidence.
- Cards técnicos: PRCP Scan, Context Pack, Policy Gate, Evidence Pack, Local-first e Auditável.
- Blocos de CLI na prática.
- Área de instalação e CTA para GitHub.
- Botões de copiar comandos.
