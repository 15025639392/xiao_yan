import pytest

from app.llm.schemas import ChatSubmissionResult
from app.platform_adapters.chat_submission_bridge import build_decision_draft_from_chat_submission


def test_chat_submission_bridge_builds_stable_decision_draft():
    submission = ChatSubmissionResult(
        response_id="resp_1",
        assistant_message_id="assistant_1",
        request_key="request_1",
        reasoning_session_id="reasoning_1",
    )

    draft = build_decision_draft_from_chat_submission(
        submission=submission,
        output_text="先接住对方问题，再给一个很轻的起步建议。",
        preferred_kind="comment_reply",
        supporting_points=["先回答核心问题", "再给最小行动建议"],
        metadata={"source_route": "chat"},
    )

    assert draft.kind == "comment_reply"
    assert draft.text == "先接住对方问题，再给一个很轻的起步建议。"
    assert draft.request_key == "request_1"
    assert draft.assistant_message_id == "assistant_1"
    assert draft.reasoning_session_id == "reasoning_1"
    assert draft.metadata["source_route"] == "chat"


def test_chat_submission_bridge_rejects_blank_output_text():
    submission = ChatSubmissionResult(
        response_id="resp_2",
        assistant_message_id="assistant_2",
    )

    with pytest.raises(ValueError, match="chat submission output_text cannot be blank"):
        build_decision_draft_from_chat_submission(
            submission=submission,
            output_text="   ",
        )
