# Command Reference — DevForge CLI

DevForge CLI is experimental. Commands are functional, but their outputs are drafts and should be reviewed before use.

The CLI is not a production compliance system and does not prove that a change is safe, legal, secure, or ready to merge.

## Suggested Flow

```text
init -> scan -> specify -> plan -> implement -> policy check -> review -> evidence -> pr-ready
```

Not every project needs every step. Review the generated artifacts and adapt the flow to your repository.

---

## devforge init

Creates the local `.devforge/` structure.

```bash
devforge init [--plain] [--json]
```

Creates:

```text
.devforge/
├── config.yml
├── audit/audit.ndjson
├── context/
├── evidence/
├── plans/
├── policy/
└── prcp/
```

Exit code: `0`.

---

## devforge scan

Collects deterministic project signals and creates a draft Project Profile.

```bash
devforge scan [--agent none|codex|custom] [--command "..."] [--dry-run] [--yes] [--plain] [--json]
```

Generates:

- `.devforge/prcp/project-signals.json`
- `.devforge/context/project-profile-brief.md`
- `.devforge/prcp/project-profile.json`
- `.devforge/prcp/scan-report.md`

Important:

- The deterministic scan is only a draft.
- `input()`, `user`, `session`, or similar generic terms may not mean personal data or auth.
- If confidence is low or medium, review the Project Profile or use an external agent with `devforge scan --agent codex`.
- Approve the profile explicitly with `devforge profile approve`.

Exit code: `0`.

---

## devforge profile approve

Marks the current Project Profile as approved after user review.

```bash
devforge profile approve [--yes] [--plain] [--json]
```

This command does not prove that the profile is correct. It records that the user reviewed and accepted it for the local workflow.

---

## devforge specify

Turns a feature idea into a draft SPEC.

```bash
devforge specify --idea "Describe your feature idea" [--plain] [--json]
devforge specify --spec specs/SPEC-ID.md --interactive
devforge specify --spec specs/SPEC-ID.md --approve
```

Generates:

- `specs/<SPEC-ID>.md`
- `.devforge/context/specification-brief-<SPEC-ID>.md`

Important:

- The generated SPEC is a draft unless approved.
- Gray areas should be reviewed before planning.
- Approval means "good enough for this local experiment", not formal product approval.

---

## devforge plan --spec

Generates plan artifacts from a SPEC.

```bash
devforge plan --spec specs/SPEC-ID.md [--plain] [--json]
```

Requires:

- `devforge init`
- `devforge scan`
- a Project Profile file
- a SPEC file

Generates:

- `.devforge/plans/PLAN-<SPEC-ID>.md`
- `.devforge/context/context-pack.md`
- `.devforge/context/agent-instructions.md`
- `.devforge/context/implementation-brief-<SPEC-ID>.md`
- `.devforge/policy/POLICY-DECISION-<SPEC-ID>.json`

Important:

- The planner is experimental.
- It should follow the Project Profile and SPEC, but generated tasks and policy decisions require review.
- `session` / `sessao` alone should not be interpreted as authentication.
- Negative scope such as "no database" or "sem banco" should not be treated as database work.

Exit code: `0`.

---

## devforge implement

Optionally calls an external local coding agent using the generated Implementation Brief.

```bash
devforge implement --spec specs/SPEC-ID.md --agent codex
devforge implement --spec specs/SPEC-ID.md --agent custom --command "codex"
devforge implement --spec specs/SPEC-ID.md --agent custom --command "echo" --dry-run
```

Important:

- This command is opt-in.
- It does not commit, push, merge, generate evidence, or record human review.
- It invokes a local tool installed by the user.
- Review all changes after the agent runs.

Next step:

```bash
devforge policy check --diff
```

---

## devforge policy check --diff

Evaluates the current Git diff against the local policy engine and latest Policy Decision.

```bash
devforge policy check --diff [--plain] [--json]
```

Requires:

- `devforge init`
- `devforge scan`
- `devforge plan`

Decisions:

- `ALLOW`
- `REQUIRE_APPROVAL`
- `DENY`

Important:

- The policy engine is experimental.
- It is not a compliance framework.
- Review the reasons and required evidence.
- Generated `.devforge/` files are not treated as application code.

Exit codes:

- `0` — ALLOW
- `1` — REQUIRE_APPROVAL or precondition failure
- `2` — DENY

---

## devforge review

Records explicit human review for an issue or SPEC.

```bash
devforge review --issue SPEC-ID --approve [--reviewer "Name"] [--plain] [--json]
```

Important:

- Human review is only satisfied by explicit review artifacts.
- AI review notes do not replace human approval.
- This command records a local review artifact and audit event.

---

## devforge evidence --issue

Builds an Evidence Pack from the latest policy check.

```bash
devforge evidence --issue SPEC-ID [--plain] [--json]
```

Collects required evidence such as:

- `test_report`
- `human_review`
- `rollback_plan`
- `audit_log`

Only required evidence is enforced. For lightweight local changes, the required evidence may be just `test_report` and `audit_log`.

Generates:

- `.devforge/evidence/EVID-<ISSUE-ID>.json`
- `.devforge/evidence/EVID-<ISSUE-ID>.md`

---

## devforge pr-ready

Prepares commit and PR guidance after an approved Evidence Pack.

```bash
devforge pr-ready --issue SPEC-ID [--plain] [--json]
```

Generates:

- `.devforge/pr/PR-<ISSUE-ID>.md`
- `.devforge/pr/commit-plan-<ISSUE-ID>.md`

Important:

- It does not run `git add`.
- It does not commit.
- It does not push.
- It does not merge.
- Treat the generated PR body and commit plan as guidance.

---

## Common Flags

| Flag | Description |
|---|---|
| `--plain` | Plain text output |
| `--json` | JSON output for automation |
| `--help` | Show command help |
| `--version` / `-v` | Show version |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success / ALLOW / ready state |
| `1` | REQUIRE_APPROVAL / missing evidence / precondition failure |
| `2` | DENY |

Always inspect generated artifacts before relying on them.
