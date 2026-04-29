from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CollaborationStage = Literal[
    "context_packaging",
    "result_review",
    "next_prompt",
    "general",
]

ClarificationLayer = Literal[
    "task",
    "intent",
    "tradeoff",
    "consistency",
    "collaboration_method",
]


REQUIRED_REVIEW_EVIDENCE_FIELDS = (
    "original_intent",
    "external_ai_prompt",
    "external_ai_result",
)

RECOMMENDED_REVIEW_EVIDENCE_FIELDS = (
    "evidence",
    "known_risks",
    "user_notes",
)


@dataclass(frozen=True)
class CollaborationEvidence:
    original_intent: str = ""
    external_ai_prompt: str = ""
    external_ai_result: str = ""
    evidence: str = ""
    known_risks: str = ""
    user_notes: str = ""

    def missing_required_fields(self) -> list[str]:
        return [
            field_name
            for field_name in REQUIRED_REVIEW_EVIDENCE_FIELDS
            if not str(getattr(self, field_name, "")).strip()
        ]

    def missing_recommended_fields(self) -> list[str]:
        return [
            field_name
            for field_name in RECOMMENDED_REVIEW_EVIDENCE_FIELDS
            if not str(getattr(self, field_name, "")).strip()
        ]


@dataclass(frozen=True)
class CollaborationReview:
    stage: CollaborationStage
    completion_assessment: str
    evidence_gaps: list[str] = field(default_factory=list)
    next_action: str = ""
    next_prompt: str = ""
    preference_candidates: list[str] = field(default_factory=list)
    can_make_completion_claim: bool = False


@dataclass(frozen=True)
class ClarificationFrame:
    stage: CollaborationStage
    layers: tuple[ClarificationLayer, ...]
    focus_questions: tuple[str, ...]
    human_decision_hint: str


def build_clarification_frame(stage: CollaborationStage) -> ClarificationFrame:
    layers: tuple[ClarificationLayer, ...] = (
        "task",
        "intent",
        "tradeoff",
        "consistency",
        "collaboration_method",
    )
    return ClarificationFrame(
        stage=stage,
        layers=layers,
        focus_questions=_stage_focus_questions(stage),
        human_decision_hint="保留用户的最终判断权；小晏只帮助看清意图、取舍、证据和下一轮协作方式。",
    )


def build_review_from_evidence(evidence: CollaborationEvidence) -> CollaborationReview:
    missing_required = evidence.missing_required_fields()
    missing_recommended = evidence.missing_recommended_fields()
    if missing_required:
        return CollaborationReview(
            stage="result_review",
            completion_assessment="我现在只能基于你给出的材料做有限判断，还不能给完整完成度结论。",
            evidence_gaps=[*missing_required, *missing_recommended],
            next_action="请先补齐最小协作证据包，再继续审阅。",
            next_prompt=build_minimum_evidence_request(missing_required, missing_recommended),
            can_make_completion_claim=False,
        )

    return CollaborationReview(
        stage="result_review",
        completion_assessment="最小协作证据包已具备，可以进入意图对齐、偏航点和风险审阅。",
        evidence_gaps=missing_recommended,
        next_action="基于当前证据审阅外部 AI 结果，并把结论转成下一轮协作语言。",
        can_make_completion_claim=not missing_recommended,
    )


def build_minimum_evidence_request(
    missing_required: list[str] | tuple[str, ...],
    missing_recommended: list[str] | tuple[str, ...] = (),
) -> str:
    required_text = "、".join(_field_label(item) for item in missing_required)
    recommended_text = "、".join(_field_label(item) for item in missing_recommended)
    lines = ["请先补齐这次 AI 协作的证据包。"]
    if required_text:
        lines.append(f"最少还需要：{required_text}。")
    if recommended_text:
        lines.append(f"如果方便，也请补充：{recommended_text}。")
    return "\n".join(lines)


def build_preference_candidate(
    *,
    task_domain: str,
    preference: str,
) -> str | None:
    normalized_domain = task_domain.strip()
    normalized_preference = preference.strip()
    if not normalized_domain or not normalized_preference:
        return None
    return f"用户在{normalized_domain}协作中偏好{normalized_preference}"


def _field_label(field_name: str) -> str:
    labels = {
        "original_intent": "原始需求",
        "external_ai_prompt": "交给外部 AI 的提示词",
        "external_ai_result": "外部 AI 的输出或总结",
        "evidence": "关键证据（测试、来源、diff、截图或验证结果）",
        "known_risks": "已知风险",
        "user_notes": "用户最不放心的地方",
    }
    return labels.get(field_name, field_name)


def _stage_focus_questions(stage: CollaborationStage) -> tuple[str, ...]:
    if stage == "context_packaging":
        return (
            "用户真正想让外部 AI 完成什么？",
            "哪些上下文是必要材料，哪些只是噪音？",
            "这次请求的非目标和验收标准是什么？",
        )
    if stage == "result_review":
        return (
            "外部 AI 的结果是否回应了原始意图？",
            "当前证据足不足以支持完成度判断？",
            "下一轮应该补证据、纠偏，还是先让用户做取舍？",
        )
    if stage == "next_prompt":
        return (
            "下一轮只需要外部 AI 修正哪一个核心偏差？",
            "需要明确禁止外部 AI 做什么？",
            "这轮结果要用什么证据验证？",
        )
    return (
        "用户现在卡在意图、上下文、结果审阅还是下一轮表达？",
        "继续使用外部 AI 是否仍有收益？",
        "是否有一个需要用户先决定的关键取舍？",
    )
