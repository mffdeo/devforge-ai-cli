"""Render `.devforge/context/agent-instructions.md` from a Jinja2 template.

A generic file is written on `devforge init`. The same file is enriched
with SPEC/Plan/Policy context on `devforge plan --spec`. The file is
guidance for AI coding agents (Cursor, Claude Code, Codex, Continue,
OpenCode, ...) — not a blocking mechanism. DevForge does not create
AGENTS.md, CLAUDE.md, GEMINI.md or .cursor/rules.
"""

from __future__ import annotations

from pathlib import Path

from devforge_ai_cli.core.paths import TEMPLATES_DIR, get_devforge_dir

_AGENT_INSTRUCTIONS_REL = "context/agent-instructions.md"


def agent_instructions_path(base: Path) -> Path:
    return get_devforge_dir(base) / _AGENT_INSTRUCTIONS_REL


def render_agent_instructions(
    base: Path,
    *,
    spec_id: str | None = None,
    plan_id: str | None = None,
    policy_decision: str | None = None,
    prcp_level: str | None = None,
    allowed_uses: list[str] | None = None,
    blocked_uses: list[str] | None = None,
    required_evidence: list[str] | None = None,
    recommended_scope: list[str] | None = None,
) -> Path:
    """Write `.devforge/context/agent-instructions.md`.

    Called twice in a typical flow:
      - by `devforge init` with no SPEC context (all kwargs left as None);
      - by `devforge plan --spec` with the SPEC/Plan/Policy fields
        populated, so the file gains a "Current SPEC context" section.
    """
    from jinja2 import Environment, FileSystemLoader

    out = agent_instructions_path(base)
    out.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    tmpl = env.get_template("agent-instructions.md.j2")
    out.write_text(
        tmpl.render(
            spec_id=spec_id,
            plan_id=plan_id,
            policy_decision=policy_decision,
            prcp_level=prcp_level,
            allowed_uses=allowed_uses or [],
            blocked_uses=blocked_uses or [],
            required_evidence=required_evidence or [],
            recommended_scope=recommended_scope or [],
        ),
        encoding="utf-8",
    )
    return out
