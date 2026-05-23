# Lessons Learned

DevForge CLI started as an attempt to build a local-first governance layer for AI-assisted software development. The code works as an experiment, but the most important result was the learning process.

## Initial Attempt

The first version assumed that a deterministic CLI could inspect a repository, classify risk, generate a plan, check policy, and produce evidence before merge.

That led to a useful workflow:

```text
init -> scan -> plan -> policy check -> review -> evidence
```

Later iterations added:

```text
specify -> implement -> pr-ready
```

The workflow was directionally right. The weak part was assuming deterministic heuristics could reliably understand arbitrary projects.

## Tests With A Todo App

The Todo App test was useful because it had realistic web-app signals:

- task creation;
- SQLite schema changes;
- rollback needs;
- manual test reports;
- human review;
- evidence packaging;
- PR guidance.

In that context, DevForge produced helpful artifacts. The Evidence Pack and PR Ready Pack were especially useful because they made the merge handoff explicit.

It also exposed risk-classification issues. Some early decisions stayed in `pending_human_review` even when human review was present. That forced a clearer rule set for status and `final_decision`.

## Tests With A Calculator CLI

The calculator CLI was a better stress test.

The project was intentionally simple:

- a Python CLI;
- no database;
- no authentication;
- no cloud;
- no personal data;
- local session state only.

The desired feature was "history of calculations during the session." Deterministic heuristics initially overreacted:

- the word "session" could be confused with authentication context;
- `input()` looked like user data;
- negative scope such as "no database" could still trigger database risk;
- a lightweight local feature could be pushed into `Hardened` / `REQUIRE_APPROVAL`.

This showed that false positives are not just bugs in keyword lists. They are a sign that the architecture should separate raw signals, reasoning, and approval.

## Problems With Deterministic Heuristics

Heuristics are useful for collecting signals:

- file extensions;
- framework hints;
- presence of migrations;
- changed paths;
- obvious secrets;
- generated artifact locations.

They are not enough to understand intent.

Examples:

- `user` can mean a local CLI user, not personal data.
- `session` can mean a local runtime session, not authenticated session.
- `no database` contains the word `database`, but the intent is the opposite.
- a repository can contain auth files while a SPEC has nothing to do with auth.

The lesson: deterministic logic should produce a draft, not a final conclusion.

## Governance Harness Discovery

The strongest idea was not the scanner. It was the harness.

DevForge became more useful when it acted as a local structure for:

- Project Profile;
- Specification Brief;
- SPEC;
- Plan Pack;
- Context Pack;
- Implementation Brief;
- Agent Instructions;
- Policy Decision;
- Human Review;
- Evidence Pack;
- PR Ready guidance.

Those artifacts help humans and agents coordinate. They make assumptions visible and reviewable.

## Scanner vs Agent-Assisted Reasoning

A deterministic scanner can say:

- "I found Python files."
- "I found a migrations directory."
- "I found a diff touching auth paths."
- "I found a possible secret marker."

It should not confidently say:

- "This project handles personal data" from weak words alone.
- "This feature is auth" from `session` alone.
- "This change is high risk" without considering approved project context and SPEC scope.

Agent-assisted reasoning would be better suited to produce a draft Project Profile and identify gray areas, but it should still be reviewed by the user.

The better flow is:

```text
signals -> agent-assisted profile -> user approval -> planning -> policy -> evidence
```

## What I Would Do Differently

If I rebuilt DevForge from scratch, I would:

- Start with the artifact model, not the scanner.
- Treat deterministic scan output as raw evidence only.
- Require explicit Project Profile approval earlier.
- Make gray areas first-class in every phase.
- Use an external agent only for reasoning over briefs, not hidden automation.
- Keep all generated decisions explainable and editable.
- Avoid product claims until the system has been tested across many real projects.

## Final Takeaway

DevForge CLI is best understood as a personal experiment in AI-assisted software governance.

The project did not prove that a CLI can automatically govern any repository. It showed something more useful: AI-assisted development benefits from local, inspectable, structured handoffs that humans can review before trusting.

This file may become the basis for a future write-up about what I tried to build, what broke, and what I learned about AI-assisted software development.
