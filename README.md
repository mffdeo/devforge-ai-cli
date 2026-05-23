# DevForge CLI

> **A local-first experiment for AI-assisted software governance.**

[![CI](https://github.com/mffdeo/devforge-ai-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mffdeo/devforge-ai-cli/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

DevForge CLI is a personal learning project. It is not a production governance product, not a compliance tool, and not a universal repository scanner.

The project explores one question:

> What would a local-first governance harness for AI-assisted development look like?

---

## What This Is

DevForge CLI is an experimental command-line tool that organizes local artifacts around an AI-assisted development workflow:

- feature specification;
- project profile and risk signals;
- implementation briefs;
- policy checks;
- human review notes;
- evidence packs;
- pull request guidance.

It writes Markdown and JSON files under `.devforge/` so the workflow can be inspected, versioned, and reviewed locally.

It does **not** call an internal LLM. Optional commands can invoke an external local agent configured by the user, but that is opt-in.

---

## Why I Built It

I wanted to understand how much structure is needed around AI-generated code before a change reaches a pull request.

The initial idea was simple: before merging AI-assisted code, the tool would scan the repository, classify risk, produce a plan, require evidence, and guide the user through review.

That idea was useful, but the real tests exposed an important limitation: deterministic heuristics cannot reliably understand every project.

---

## The Workflow I Wanted

The intended workflow became:

```text
init -> scan -> specify -> plan -> implement -> policy check -> review -> evidence -> pr-ready
```

In practice:

```bash
devforge init
devforge scan
devforge specify --idea "Add task priority"
devforge plan --spec specs/SPEC-PRIORITY-001.md
devforge implement --spec specs/SPEC-PRIORITY-001.md --agent codex
devforge policy check --diff
devforge review --issue SPEC-PRIORITY-001
devforge evidence --issue SPEC-PRIORITY-001
devforge pr-ready --issue SPEC-PRIORITY-001
```

The important part is not automation for its own sake. The goal is to make handoffs, assumptions, policy decisions, and evidence explicit.

---

## Current Capabilities

DevForge CLI currently includes:

- `devforge init` to create local `.devforge/` governance folders;
- `devforge scan` to collect deterministic project signals and draft a Project Profile;
- `devforge profile approve` to explicitly approve a Project Profile;
- `devforge specify` to generate a testable SPEC from a feature idea;
- `devforge plan --spec` to generate a Plan Pack, Context Pack, Policy Decision, Agent Instructions, and Implementation Brief;
- `devforge implement` to optionally call an external local coding agent using the implementation brief;
- `devforge policy check --diff` to evaluate the current diff against local rules;
- `devforge review` to record explicit human review;
- `devforge evidence` to collect an Evidence Pack;
- `devforge pr-ready` to prepare commit and PR guidance without committing or pushing.

These commands are functional, but their outputs should be treated as reviewable drafts, not final decisions.

---

## What Worked

The project worked well as a workflow harness:

- It produced useful Markdown and JSON artifacts.
- It made implicit handoffs explicit.
- It separated implementation from review and evidence.
- It helped clarify what a PR should include.
- It created an audit trail that is easy to inspect locally.
- It made it easier to see when human review should be required.

The most useful parts were the briefs, evidence packs, audit trail, and PR guidance.

---

## What Did Not Work

The deterministic scanner and planner were too brittle when treated as universal understanding.

Real tests showed false positives:

- a simple Python CLI calculator was initially treated as higher risk than it was;
- local `input()` was easy to confuse with personal data;
- the word "session" / "sessão" could be mistaken for authentication;
- phrases like "no database" or "sem banco" could still trigger database risk if handled naively;
- generic project words could push the planner toward specific templates such as auth.

Those issues are not just keyword bugs. They show that repository understanding needs context, review, and probably agent-assisted reasoning.

---

## Key Lessons Learned

1. A deterministic scan should collect signals, not pretend to know the project.
2. A Project Profile should be reviewed and approved by a human.
3. The best role for DevForge is not "universal scanner"; it is "governance harness".
4. AI-assisted development needs structured handoffs more than another autonomous agent.
5. Policy decisions must stay proportional to the actual project and SPEC.
6. Outputs should be reviewable drafts, not unquestioned truth.

See [LESSONS_LEARNED.md](LESSONS_LEARNED.md) for the longer write-up.

---

## Current Limitations

- The scanner is heuristic and incomplete.
- The policy engine is experimental and not a compliance framework.
- Risk classification can still be wrong.
- The generated SPEC, plan, and evidence require human review.
- The project does not prove legal, security, privacy, or regulatory compliance.
- There is no guarantee that the tool understands your architecture.
- External agent execution is opt-in and depends on tools installed locally by the user.
- Some experimental commands may change behavior or be simplified in future versions.

Do not use this as a production approval system without your own review, tests, and controls.

---

## Ideal Future Architecture

If I continued this as a serious system, I would split it into three layers:

1. **Deterministic signals**
   - file types;
   - framework hints;
   - changed files;
   - policy packs;
   - audit trail.

2. **Agent-assisted reasoning**
   - project profile refinement;
   - SPEC clarification;
   - risk analysis;
   - implementation handoff review;
   - evidence completeness review.

3. **Human-confirmed governance**
   - approved Project Profile;
   - approved SPEC;
   - explicit review;
   - traceable policy decisions;
   - PR-ready package.

The CLI should remain local-first and transparent. The AI should help reason over context, but the user should approve the important decisions.

---

## How To Try It Locally

The package is not published to PyPI. Install from GitHub or run from source.

With `pipx`:

```bash
pipx install git+https://github.com/mffdeo/devforge-ai-cli.git
```

With `uv`:

```bash
uv tool install git+https://github.com/mffdeo/devforge-ai-cli.git
```

For local development:

```bash
git clone https://github.com/mffdeo/devforge-ai-cli.git
cd devforge-ai-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
ruff check .
```

Try the full experimental flow:

```bash
devforge init
devforge scan
devforge profile approve
devforge specify --idea "Describe your feature idea"
devforge specify --spec specs/<SPEC-ID>.md --approve
devforge plan --spec specs/<SPEC-ID>.md
devforge implement --spec specs/<SPEC-ID>.md --agent custom --command "echo" --dry-run
The `echo` command is used here as a safe dry-run example. In a real experiment, replace it with your local coding agent command.
devforge policy check --diff
devforge review --issue <SPEC-ID>
devforge evidence --issue <SPEC-ID>
devforge pr-ready --issue <SPEC-ID>
```

Review every generated artifact before using it.

---

## Project Status: Experimental / Learning Project

DevForge CLI is a lab project.

It is useful as a record of experiments around AI-assisted SDLC governance. It is not marketed as a finished product and should not be treated as a complete security, compliance, or review system.

The most valuable outcome was the lesson: **the right shape is a local-first AI governance harness, not a deterministic tool that claims to understand every project.**

---

## License

MIT License. See [LICENSE](LICENSE).
