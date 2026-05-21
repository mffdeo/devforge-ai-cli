"""Central recognition rules for required evidence.

Single source of truth for both `devforge policy check` and
`devforge evidence`. Evidence files created naturally by agents
(`.devforge/test-reports/SPEC-PRIORITY-001-manual.md`,
`docs/rollback/SPEC-PRIORITY-001.md`, ...) are now recognized without
the need for aliases like `test_report.md`.

A SPEC-aware id (spec_id, issue_id) can be passed to make the rules
prefer files that match the current work.

human_review is intentionally strict: only `HUMAN-REVIEW-*.md` in
`.devforge/reviews/` counts as "human review approved". Generic review
files written by an agent count as `review_request` (informational), not
as approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from devforge_ai_cli.core.ignore import should_ignore_path


@dataclass
class EvidenceMatch:
    """Result of checking a single piece of required evidence."""

    name: str
    present: bool = False
    matched_paths: list[str] = field(default_factory=list)
    matched_rule: str = "missing"  # 'strict' | 'weak' | 'missing'
    expected_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "present" if self.present else "missing"


def _rel(base: Path, p: Path) -> str:
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def _glob_files(directory: Path, pattern: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def _rglob_files(base: Path, pattern: str) -> list[Path]:
    out: list[Path] = []
    for p in base.rglob(pattern):
        rel = p.relative_to(base) if p.is_absolute() else p
        if not p.is_file():
            continue
        if should_ignore_path(rel):
            continue
        out.append(p)
    return sorted(out)


def _expected_test_report(spec_id: str | None) -> list[str]:
    out = [
        f".devforge/test-reports/{spec_id}-manual.md" if spec_id else ".devforge/test-reports/<SPEC-ID>-manual.md",
        ".devforge/test-reports/*.md",
        "pytest*.xml | coverage.xml | junit.xml (anywhere outside ignored dirs)",
    ]
    return out


def _expected_rollback(spec_id: str | None) -> list[str]:
    return [
        f"docs/rollback/{spec_id}.md" if spec_id else "docs/rollback/<SPEC-ID>.md",
        ".devforge/rollback/ROLLBACK-*.md",
    ]


def _expected_human_review(spec_id: str | None) -> list[str]:
    return [
        f".devforge/reviews/HUMAN-REVIEW-{spec_id}.md" if spec_id else ".devforge/reviews/HUMAN-REVIEW-<SPEC-ID>.md",
    ]


def _expected_audit_log() -> list[str]:
    return [".devforge/audit/audit.ndjson"]


def check_test_report(base: Path, devforge_dir: Path, spec_id: str | None = None) -> EvidenceMatch:
    em = EvidenceMatch(name="test_report", expected_paths=_expected_test_report(spec_id))

    # Strict: any .md inside .devforge/test-reports/
    test_reports = devforge_dir / "test-reports"
    matches = _glob_files(test_reports, "*.md")
    if matches:
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p) for p in matches]
        return em

    # Weak fallbacks: legacy aliases inside .devforge/evidence/
    legacy_dir = devforge_dir / "evidence"
    legacy = _glob_files(legacy_dir, "test-report*")
    if legacy:
        em.present = True
        em.matched_rule = "weak"
        em.matched_paths = [_rel(base, p) for p in legacy]
        return em

    # Weaker fallbacks: report files anywhere in the repo
    for pattern in ("pytest*.xml", "coverage.xml", "junit.xml", "test-report.md"):
        hits = _rglob_files(base, pattern)
        if hits:
            em.present = True
            em.matched_rule = "weak"
            em.matched_paths = [_rel(base, p) for p in hits]
            return em

    return em


def check_rollback_plan(base: Path, devforge_dir: Path, spec_id: str | None = None) -> EvidenceMatch:
    em = EvidenceMatch(name="rollback_plan", expected_paths=_expected_rollback(spec_id))

    # Strict: docs/rollback/*.md
    docs_rollback = base / "docs" / "rollback"
    matches = _glob_files(docs_rollback, "*.md")
    if matches:
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p) for p in matches]
        return em

    # Strict: .devforge/rollback/*.md
    df_rollback = devforge_dir / "rollback"
    matches = _glob_files(df_rollback, "ROLLBACK*.md") + _glob_files(df_rollback, "rollback*.md")
    if matches:
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p) for p in matches]
        return em

    # Weak: legacy aliases inside .devforge/evidence/
    legacy = _glob_files(devforge_dir / "evidence", "rollback*") + _glob_files(devforge_dir / "evidence", "ROLLBACK*")
    if legacy:
        em.present = True
        em.matched_rule = "weak"
        em.matched_paths = [_rel(base, p) for p in legacy]
        return em

    # Weakest: anywhere in the repo
    for pattern in ("ROLLBACK*.md", "rollback*.md"):
        hits = _rglob_files(base, pattern)
        if hits:
            em.present = True
            em.matched_rule = "weak"
            em.matched_paths = [_rel(base, p) for p in hits]
            return em

    return em


def check_human_review(base: Path, devforge_dir: Path, spec_id: str | None = None) -> EvidenceMatch:
    em = EvidenceMatch(name="human_review", expected_paths=_expected_human_review(spec_id))

    reviews_dir = devforge_dir / "reviews"

    # Strict: HUMAN-REVIEW-*.md  (case-insensitive on the prefix)
    strict = _glob_files(reviews_dir, "HUMAN-REVIEW*.md") + _glob_files(reviews_dir, "human-review*.md")
    if strict:
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p) for p in strict]
        return em

    # Otherwise, any .md in .devforge/reviews/ is logged as a review_request
    other = _glob_files(reviews_dir, "*.md")
    if other:
        em.notes.append(
            "found generic review files; counted only as review_request, not as human_review approval"
        )
        # store these in matched_paths so the caller can surface them
        em.matched_paths = [_rel(base, p) for p in other]
        em.matched_rule = "missing"  # human_review is still missing
    return em


def check_review_request(base: Path, devforge_dir: Path) -> EvidenceMatch:
    """Auxiliary signal: any .md in .devforge/reviews/ is a review request,
    even if it does not satisfy human_review."""
    em = EvidenceMatch(name="review_request", expected_paths=[".devforge/reviews/*.md"])
    reviews_dir = devforge_dir / "reviews"
    matches = _glob_files(reviews_dir, "*.md")
    if matches:
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p) for p in matches]
    return em


def check_audit_log(base: Path, devforge_dir: Path) -> EvidenceMatch:
    em = EvidenceMatch(name="audit_log", expected_paths=_expected_audit_log())
    p = devforge_dir / "audit" / "audit.ndjson"
    if p.exists():
        em.present = True
        em.matched_rule = "strict"
        em.matched_paths = [_rel(base, p)]
    return em


def check_evidence(
    name: str,
    base: Path,
    devforge_dir: Path,
    spec_id: str | None = None,
) -> EvidenceMatch:
    """Dispatch to the right rule by evidence name."""
    if name == "test_report":
        return check_test_report(base, devforge_dir, spec_id=spec_id)
    if name == "rollback_plan":
        return check_rollback_plan(base, devforge_dir, spec_id=spec_id)
    if name == "human_review":
        return check_human_review(base, devforge_dir, spec_id=spec_id)
    if name == "audit_log":
        return check_audit_log(base, devforge_dir)
    if name == "review_request":
        return check_review_request(base, devforge_dir)
    em = EvidenceMatch(name=name)
    em.notes.append(f"unknown evidence type: {name}")
    return em


def evaluate_required_evidence(
    required: list[str],
    base: Path,
    devforge_dir: Path,
    spec_id: str | None = None,
) -> dict[str, EvidenceMatch]:
    """Run every required check and return name → EvidenceMatch."""
    return {name: check_evidence(name, base, devforge_dir, spec_id=spec_id) for name in required}
