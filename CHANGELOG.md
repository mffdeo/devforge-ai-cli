# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-05-21

### Added

- `devforge init` — bootstrap local governance structure (`.devforge/`)
- `devforge scan` — detect stack (Node, Python, Docker, CI), sensitive areas and compute PRCP baseline
- `devforge plan --spec <file>` — generate Plan Pack, Context Pack and initial Policy Decision from a SPEC
- `devforge policy check --diff` — evaluate git diff against local policies; returns ALLOW / REQUIRE_APPROVAL / DENY
- `devforge evidence --issue <ID>` — collect and package evidence before a PR
- Local audit trail in NDJSON format (`.devforge/audit/audit.ndjson`)
- Markdown + JSON outputs for all generated artifacts
- `--plain` flag for simple text output (no Rich)
- `--json` flag for automation-friendly JSON output
- Exit codes: 0 (ALLOW), 1 (REQUIRE_APPROVAL), 2 (DENY)
- Rich terminal UI faithful to reference screenshots
- Plantão Fácil example (`examples/plantao-facil/`)
- GitHub Pages landing page
- CI with pytest and ruff

### Architecture

- `devforge_ai_cli/core/` — paths, config, git, scanner, planner
- `devforge_ai_cli/prcp/` — PRCP evaluator and risk signals
- `devforge_ai_cli/policy_engine/` — rules, decisions, engine
- `devforge_ai_cli/evidence/` — collector and writer
- `devforge_ai_cli/audit/` — NDJSON audit trail
- `devforge_ai_cli/ui/` — theme, console, renderers per command
- `devforge_ai_cli/templates/` — Jinja2 templates for Markdown/JSON artifacts

### Notes

- Package name: `devforge-ai-cli` (not published to PyPI yet — install from GitHub)
- Primary command: `devforge`
- No LLM calls, no cloud, no daemon, no telemetry
- Python 3.12+ required
