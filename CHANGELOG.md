# Changelog

All notable changes to this project will be documented in this file.

---

## Unreleased - v0.2.0-lab

### Changed

- Repositioned DevForge CLI as a personal experimental learning project rather than a production-ready governance product.
- Updated README and landing page language to avoid claims of universal repository understanding or real compliance guarantees.
- Documented the core lesson from real tests: deterministic heuristics are useful for raw signals, but not enough to understand arbitrary projects.
- Clarified the intended future direction as a local-first AI governance harness for briefs, handoffs, policy gates, human review, evidence, and PR guidance.

### Added

- Added `LESSONS_LEARNED.md` with notes from the Todo App and calculator CLI experiments, including what worked, what failed, and what should be designed differently.

---

## 0.1.1 - Scan heuristics patch

### Fixed

- `devforge scan` now detects database signals from files such as `db_create.py`, `database.py`, `schema.sql`, `migrations/`, `*.db`, `*.sqlite`, and content such as `sqlite3`, `CREATE TABLE`, `ALTER TABLE`, and `DROP TABLE`.
- `devforge scan` no longer suggests `devforge plan --spec specs/auth.md` by default for generic projects.
- Scan next-step suggestion now uses the first existing SPEC in `specs/`, or falls back to `specs/SPEC-EXAMPLE-001.md`.

---

## [0.1.0] - 2026-05-21

### Added

- `devforge init` — bootstrap local governance structure under `.devforge/`.
- `devforge scan` — detect stack signals, sensitive areas, and compute a PRCP baseline.
- `devforge plan --spec <file>` — generate Plan Pack, Context Pack, and initial Policy Decision from a SPEC.
- `devforge policy check --diff` — evaluate git diff against local policies and return `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`.
- `devforge evidence --issue <ID>` — collect and package evidence before a PR.
- Local audit trail in NDJSON format at `.devforge/audit/audit.ndjson`.
- Markdown and JSON outputs for generated artifacts.
- `--plain` flag for simple text output without Rich rendering.
- `--json` flag for automation-friendly JSON output.
- Exit codes:
  - `0` — `ALLOW`
  - `1` — `REQUIRE_APPROVAL`
  - `2` — `DENY`
- Rich terminal UI based on the original reference screenshots.
- Plantão Fácil example under `examples/plantao-facil/`.
- GitHub Pages landing page.
- CI with `pytest` and `ruff`.

### Architecture

- `devforge_ai_cli/core/` — paths, config, git, scanner, planner.
- `devforge_ai_cli/prcp/` — PRCP evaluator and risk signals.
- `devforge_ai_cli/policy_engine/` — rules, decisions, engine.
- `devforge_ai_cli/evidence/` — collector and writer.
- `devforge_ai_cli/audit/` — NDJSON audit trail.
- `devforge_ai_cli/ui/` — theme, console, renderers per command.
- `devforge_ai_cli/templates/` — Jinja2 templates for Markdown and JSON artifacts.

### Notes

- Package name: `devforge-ai-cli`.
- Primary command: `devforge`.
- Not published to PyPI yet. Install from GitHub.
- No internal LLM calls.
- No cloud requirement.
- No daemon.
- No telemetry.
- Python 3.12+ required.
