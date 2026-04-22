"""Validate drafts and actions against the XHS work policy."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import XhsWorkPolicy


@dataclass(frozen=True)
class XhsPolicyViolation:
    """A single policy violation found in a draft or action."""
    rule: str  # human-readable name of the violated rule
    severity: str  # "error" | "warning"
    message: str


@dataclass(frozen=True)
class XhsPolicyCheckResult:
    """Result of checking a draft against the work policy."""
    violations: tuple[XhsPolicyViolation, ...]
    ok: bool  # True iff no severity=error violations

    @property
    def errors(self) -> list[XhsPolicyViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[XhsPolicyViolation]:
        return [v for v in self.violations if v.severity == "warning"]


def check_draft_against_policy(draft: dict, policy: XhsWorkPolicy) -> XhsPolicyCheckResult:
    """Check a draft dict against the work policy.

    Returns errors for hard violations (forbidden keywords, length bounds)
    and warnings for soft violations (missing required keywords).
    """
    violations: list[XhsPolicyViolation] = []
    title = str(draft.get("title", "")).lower()
    body = str(draft.get("body", ""))

    # Hard: forbidden keywords in title or body
    for kw in policy.forbidden_keywords:
        if kw.lower() in title or kw.lower() in body.lower():
            violations.append(XhsPolicyViolation(
                rule="forbidden_keyword",
                severity="error",
                message=f"包含禁用词「{kw}」，草稿已拦截",
            ))

    # Soft: missing required keywords
    if policy.required_keywords:
        body_lower = body.lower()
        missing = [kw for kw in policy.required_keywords if kw.lower() not in body_lower]
        if missing:
            violations.append(XhsPolicyViolation(
                rule="required_keyword",
                severity="warning",
                message=f"缺少要求关键词：{', '.join(missing)}",
            ))

    # Soft: body too short
    if policy.min_body_chars > 0 and len(body) < policy.min_body_chars:
        violations.append(XhsPolicyViolation(
            rule="min_body_chars",
            severity="warning",
            message=f"正文过短（{len(body)} < {policy.min_body_chars}字），可能影响互动",
        ))

    # Hard: body too long
    if policy.max_body_chars > 0 and len(body) > policy.max_body_chars:
        violations.append(XhsPolicyViolation(
            rule="max_body_chars",
            severity="error",
            message=f"正文过长（{len(body)} > {policy.max_body_chars}字），已被截断",
        ))
        # Truncate the body in-place for correction
        draft["body"] = body[:policy.max_body_chars]

    return XhsPolicyCheckResult(
        violations=tuple(violations),
        ok=not any(v.severity == "error" for v in violations),
    )


def can_post_today(already_posted_today: int, policy: XhsWorkPolicy) -> bool:
    """Check whether a post is allowed given today's count and the policy limit."""
    if policy.max_posts_per_day <= 0:
        return True
    return already_posted_today < policy.max_posts_per_day
