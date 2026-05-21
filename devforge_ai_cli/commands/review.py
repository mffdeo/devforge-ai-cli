"""`devforge review --issue <ID>` — guided human review."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from devforge_ai_cli.audit.ndjson import append_event
from devforge_ai_cli.core.config import read_config
from devforge_ai_cli.core.paths import (
    TEMPLATES_DIR,
    get_audit_file,
    get_config_file,
    get_devforge_dir,
)
from devforge_ai_cli.core.project import require_init


@dataclass
class _Reviewer:
    name: str | None
    email: str | None
    source: str  # 'cli_arg' | 'devforge_config' | 'git_config' | 'git_config_global' | 'prompt' | 'unknown'


def _git_value(args: list[str], cwd: Path) -> str | None:
    try:
        r = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            val = r.stdout.strip()
            return val or None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    return None


def _resolve_reviewer(
    cwd: Path,
    cli_reviewer: str | None,
    cli_role: str | None,
    yes: bool,
    interactive: bool,
) -> _Reviewer:
    if cli_reviewer:
        return _Reviewer(name=cli_reviewer, email=None, source="cli_arg")

    # devforge config
    try:
        cfg = read_config(get_config_file(cwd))
        if cfg.reviewer_name:
            suggested = _Reviewer(name=cfg.reviewer_name, email=None, source="devforge_config")
            return _confirm_or_prompt(suggested, yes=yes, interactive=interactive)
    except (FileNotFoundError, OSError, ValueError):
        pass

    # git config local
    name = _git_value(["git", "config", "user.name"], cwd)
    email = _git_value(["git", "config", "user.email"], cwd)
    if name:
        suggested = _Reviewer(name=name, email=email, source="git_config")
        return _confirm_or_prompt(suggested, yes=yes, interactive=interactive)

    # git config global
    name = _git_value(["git", "config", "--global", "user.name"], cwd)
    email = _git_value(["git", "config", "--global", "user.email"], cwd)
    if name:
        suggested = _Reviewer(name=name, email=email, source="git_config_global")
        return _confirm_or_prompt(suggested, yes=yes, interactive=interactive)

    if interactive:
        typed = input("Nome do revisor: ").strip()
        if typed:
            return _Reviewer(name=typed, email=None, source="prompt")

    return _Reviewer(name=None, email=None, source="unknown")


def _confirm_or_prompt(suggested: _Reviewer, *, yes: bool, interactive: bool) -> _Reviewer:
    if yes or not interactive:
        return suggested
    label = f"{suggested.name}" + (f" <{suggested.email}>" if suggested.email else "")
    print(f"Reviewer detectado: {label} ({suggested.source})")
    ans = input("Usar este reviewer? [Y/n] ").strip().lower()
    if ans in ("", "y", "yes", "s", "sim"):
        return suggested
    typed = input("Nome do revisor: ").strip()
    if typed:
        return _Reviewer(name=typed, email=None, source="prompt")
    return suggested


def _ask_approval(yes: bool, approve: bool, interactive: bool) -> bool:
    if approve or yes:
        return True
    if not interactive:
        return False
    ans = input(
        "Você revisou os itens acima e aprova esta revisão humana? [y/N] "
    ).strip().lower()
    return ans in ("y", "yes", "s", "sim")


def _files_to_review(issue: str, policy_check: dict, base: Path) -> list[str]:
    """Concrete file list the reviewer should open before approving."""
    files: list[str] = []
    devforge_dir = get_devforge_dir(base)

    # SPEC and Plan Pack
    spec_md = base / "specs" / f"{issue}.md"
    if spec_md.exists():
        files.append(str(spec_md.relative_to(base)))
    plan_md = devforge_dir / "plans" / f"PLAN-{issue}.md"
    if plan_md.exists():
        files.append(str(plan_md.relative_to(base)))

    # Changed files from the latest policy check
    for f in policy_check.get("changed_files", []) or []:
        if f not in files:
            files.append(f)

    # Recognized evidence files (matched_paths from evidence_details)
    details = policy_check.get("evidence_details", {}) or {}
    for name in ("test_report", "rollback_plan"):
        for p in (details.get(name) or {}).get("matched_paths", []) or []:
            if p not in files:
                files.append(p)

    # Review request files (if any) — surfaced so the reviewer can see what
    # the agent prepared as a review request.
    for p in policy_check.get("review_request_paths", []) or []:
        if p not in files:
            files.append(p)

    return files


def _diff_summary(base: Path) -> str:
    """Best-effort `git diff --stat` text. Falls back to empty string."""
    parts: list[str] = []
    for args in (["git", "diff", "--stat"], ["git", "diff", "--cached", "--stat"]):
        try:
            r = subprocess.run(
                args, cwd=base, capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts.append(r.stdout.rstrip())
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    return "\n".join(parts)


_CHECKLIST = [
    "A SPEC foi revisada?",
    "O Plan Pack foi seguido?",
    "A implementação ficou limitada ao escopo?",
    "Os arquivos alterados fazem sentido?",
    "O test report está presente?",
    "O rollback plan está presente (quando exigido)?",
    "O diff não contém segredo, token ou credencial?",
    "Não foi adicionado login/auth/cloud fora do escopo?",
]


def _print_review_summary(
    issue: str,
    policy_check: dict,
    base: Path,
    show_diff: bool,
) -> None:
    """Render the review briefing to stdout BEFORE asking for approval.

    Used in both Rich and --plain mode. --json mode does not call this; the
    machine consumer already gets the same data structurally.
    """
    print(f"════ Human review — {issue} ════")
    print(f"Policy decision: {policy_check.get('decision', '?')}")
    print(f"PRCP level:      {policy_check.get('prcp_level', '?')}")

    reasons = policy_check.get("reasons", []) or []
    print("\nReasons:")
    if reasons:
        for r in reasons:
            print(f"  - {r}")
    else:
        print("  (nenhuma reason registrada)")

    changed = policy_check.get("changed_files", []) or []
    print(f"\nChanged files ({len(changed)}):")
    if changed:
        for f in changed:
            print(f"  - {f}")
    else:
        print("  (sem arquivos alterados no snapshot do policy check)")

    required = policy_check.get("required_evidence", []) or []
    status = policy_check.get("evidence_status", {}) or {}
    details = policy_check.get("evidence_details", {}) or {}
    print("\nRequired evidence:")
    for ev in required:
        st = status.get(ev, "unknown")
        paths = (details.get(ev) or {}).get("matched_paths") or []
        if st == "present" and paths:
            print(f"  - {ev}: present → {', '.join(paths)}")
        elif st == "present":
            print(f"  - {ev}: present")
        else:
            expected = (details.get(ev) or {}).get("expected_paths") or []
            esc = f" — esperado em: {', '.join(expected)}" if expected else ""
            print(f"  - {ev}: missing{esc}")

    rr_paths = policy_check.get("review_request_paths", []) or []
    if rr_paths:
        print("\nReview request files (não substituem human_review):")
        for p in rr_paths:
            print(f"  - {p}")

    files = _files_to_review(issue, policy_check, base)
    print("\nArquivos para revisar:")
    if files:
        for f in files:
            print(f"  - {f}")
    else:
        print("  (sem arquivos vinculados)")

    if show_diff:
        ds = _diff_summary(base)
        print("\nDiff stat:")
        if ds:
            for line in ds.splitlines():
                print(f"  {line}")
        else:
            print("  (sem diff disponível)")

    print("\nO que revisar:")
    for q in _CHECKLIST:
        print(f"  - {q}")

    nxt = policy_check.get("next_step")
    if nxt:
        print(f"\nNext step (após review): {nxt}")
    print()


def _render(
    base: Path,
    issue_id: str,
    reviewer: _Reviewer,
    role: str | None,
    policy_check: dict,
    notes: str | None,
) -> Path:
    from jinja2 import Environment, FileSystemLoader

    devforge_dir = get_devforge_dir(base)
    reviews_dir = devforge_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    out = reviews_dir / f"HUMAN-REVIEW-{issue_id}.md"

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    tmpl = env.get_template("human-review.md.j2")
    out.write_text(
        tmpl.render(
            issue_id=issue_id,
            reviewer=reviewer.name,
            role=role,
            reviewer_source=reviewer.source,
            policy_decision=policy_check.get("decision", "REQUIRE_APPROVAL"),
            prcp_level=policy_check.get("prcp_level", "Standard"),
            reasons=policy_check.get("reasons", []),
            changed_files=policy_check.get("changed_files", []),
            evidence_status=policy_check.get("evidence_status", {}),
            notes=notes,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        encoding="utf-8",
    )
    return out


def _warn(msg: str) -> None:
    from devforge_ai_cli.ui import theme as t
    from devforge_ai_cli.ui.console import console
    console.print(f"[{t.AMBER}]{msg}[/{t.AMBER}]")


def run_review(
    issue: str,
    reviewer: str | None,
    role: str | None,
    approve: bool,
    yes: bool,
    notes: str | None,
    plain: bool,
    output_json: bool,
    show_diff: bool = False,
    cwd: Path | None = None,
) -> int:
    base = cwd or Path.cwd()
    require_init(base)

    devforge_dir = get_devforge_dir(base)

    # require a previous policy check snapshot
    latest = devforge_dir / "policy" / "POLICY-CHECK-LATEST.json"
    if not latest.exists():
        _warn(
            "⚠ POLICY-CHECK-LATEST.json não encontrado. "
            "Rode: devforge policy check --diff"
        )
        raise SystemExit(1)

    policy_check = json.loads(latest.read_text(encoding="utf-8"))

    interactive = not (plain or output_json)
    reviewer_obj = _resolve_reviewer(
        base, cli_reviewer=reviewer, cli_role=role, yes=yes, interactive=interactive,
    )

    if approve and not reviewer_obj.name:
        _warn(
            "⚠ --approve exige um reviewer. Use --reviewer \"<Nome>\" "
            "ou configure git user.name."
        )
        raise SystemExit(1)

    if not reviewer_obj.name:
        _warn(
            "⚠ Nenhum reviewer detectado. Use --reviewer \"<Nome>\" ou "
            "configure git user.name."
        )
        raise SystemExit(1)

    # Show the briefing before asking for approval (skip in --json so
    # automation gets a clean machine-readable payload).
    if not output_json:
        _print_review_summary(issue, policy_check, base, show_diff)

    approved = _ask_approval(yes=yes, approve=approve, interactive=interactive)
    if not approved:
        msg = "Revisão humana não registrada. Revise os arquivos listados e rode novamente."
        if output_json:
            print(json.dumps({
                "issue_id": issue,
                "reviewer": reviewer_obj.name,
                "reviewer_source": reviewer_obj.source,
                "decision": "NotApproved",
                "generated_file": None,
                "evidence_status": policy_check.get("evidence_status", {}),
                "next_step": "Reveja a SPEC e o Plan Pack antes de aprovar.",
            }))
        else:
            print(f"[DevForge] {msg}")
        return 1

    out_path = _render(base, issue, reviewer_obj, role, policy_check, notes)

    timestamp = datetime.now(timezone.utc).isoformat()
    relpath = str(out_path.relative_to(base))
    append_event(get_audit_file(base), {
        "event": "human_review.recorded",
        "issue_id": issue,
        "reviewer": reviewer_obj.name,
        "reviewer_source": reviewer_obj.source,
        "decision": "Approved",
        "generated_file": relpath,
        "timestamp": timestamp,
    })

    next_step = f"devforge evidence --issue {issue}"
    if output_json:
        print(json.dumps({
            "issue_id": issue,
            "reviewer": reviewer_obj.name,
            "reviewer_source": reviewer_obj.source,
            "role": role,
            "decision": "Approved",
            "generated_file": relpath,
            "evidence_status": policy_check.get("evidence_status", {}),
            "next_step": next_step,
        }))
    elif plain:
        print(f"[DevForge] Human review registrada: {relpath}")
        print(f"Reviewer: {reviewer_obj.name} ({reviewer_obj.source})")
        print("Decision: Approved")
        print(f"Next step: {next_step}")
    else:
        from devforge_ai_cli.ui import theme as t
        from devforge_ai_cli.ui.console import console
        console.print()
        console.print(f"[bold {t.GREEN}]✓ Human review registrada[/bold {t.GREEN}]")
        console.print(f"  Reviewer: [bold]{reviewer_obj.name}[/bold] ({reviewer_obj.source})")
        console.print(f"  Decision: [bold {t.GREEN}]Approved[/bold {t.GREEN}]")
        console.print(f"  File: [{t.CYAN}]{relpath}[/{t.CYAN}]")
        console.print()
        console.print(f"Próximo passo: [bold {t.CYAN}]{next_step}[/bold {t.CYAN}]")
    return 0
