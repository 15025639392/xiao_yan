from app.usecases.ai_collaboration_coach import (
    CollaborationEvidence,
    build_clarification_frame,
    build_preference_candidate,
    build_review_from_evidence,
)


def test_review_from_incomplete_evidence_refuses_completion_claim():
    review = build_review_from_evidence(
        CollaborationEvidence(
            original_intent="让 Codex 修复登录错误",
            external_ai_result="Codex 说已经修好了",
        )
    )

    assert review.stage == "result_review"
    assert not review.can_make_completion_claim
    assert "external_ai_prompt" in review.evidence_gaps
    assert "evidence" in review.evidence_gaps
    assert "还不能给完整完成度结论" in review.completion_assessment
    assert "交给外部 AI 的提示词" in review.next_prompt


def test_review_from_complete_evidence_can_continue_structured_review():
    review = build_review_from_evidence(
        CollaborationEvidence(
            original_intent="让 Codex 补一个回归测试",
            external_ai_prompt="只补测试，不改实现",
            external_ai_result="已新增测试",
            evidence="pytest services/core/tests/test_example.py passed",
            known_risks="未跑全量测试",
            user_notes="担心它改了实现",
        )
    )

    assert review.can_make_completion_claim
    assert review.evidence_gaps == []
    assert "可以进入意图对齐" in review.completion_assessment


def test_preference_candidate_is_explainable_and_optional():
    candidate = build_preference_candidate(
        task_domain="编程",
        preference="先限制文件范围，再让外部 AI 实现",
    )

    assert candidate == "用户在编程协作中偏好先限制文件范围，再让外部 AI 实现"
    assert build_preference_candidate(task_domain="", preference="先审阅") is None


def test_clarification_frame_keeps_thinking_partner_layers():
    frame = build_clarification_frame("result_review")

    assert frame.stage == "result_review"
    assert frame.layers == (
        "task",
        "intent",
        "tradeoff",
        "consistency",
        "collaboration_method",
    )
    assert "当前证据足不足以支持完成度判断？" in frame.focus_questions
    assert "保留用户的最终判断权" in frame.human_decision_hint


def test_general_clarification_frame_routes_to_current_blocker():
    frame = build_clarification_frame("general")

    assert "用户现在卡在意图、上下文、结果审阅还是下一轮表达？" in frame.focus_questions
    assert "是否有一个需要用户先决定的关键取舍？" in frame.focus_questions
