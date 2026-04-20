from __future__ import annotations

from typing import Any

from app.platform_adapters.base import BasePlatformAdapter, parse_datetime
from app.platform_adapters.models import CanonicalEvent, CanonicalUser, CoreDecision, PlatformAction


class WechatManualAdapter(BasePlatformAdapter):
    platform = "wechat_manual"

    def parse_event(self, payload: dict[str, Any]) -> CanonicalEvent:
        contact = payload.get("contact") if isinstance(payload.get("contact"), dict) else {}
        message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        thread_id = str(
            payload.get("conversation_id")
            or message.get("conversation_id")
            or contact.get("thread_id")
            or contact.get("id")
            or "wechat_manual_thread"
        )
        user_id = str(contact.get("id") or message.get("sender_id") or "wechat_manual_user")
        user = CanonicalUser(
            platform=self.platform,
            user_id=user_id,
            display_name=_clean_text(contact.get("name")),
            profile_hint=_clean_text(contact.get("remark")),
            metadata={"source": "manual_import"},
        )
        return CanonicalEvent(
            platform=self.platform,
            event_id=str(message.get("id") or payload.get("event_id") or f"{thread_id}:manual"),
            event_type="message",
            thread_id=thread_id,
            occurred_at=parse_datetime(message.get("sent_at") or payload.get("occurred_at")),
            text=_clean_text(message.get("text") or payload.get("text")),
            user=user,
            raw_payload=payload,
            metadata={"scene": _clean_text(payload.get("scene")) or "manual_copilot"},
        )

    def render_actions(
        self,
        event: CanonicalEvent,
        user: CanonicalUser,
        decision: CoreDecision,
    ) -> list[PlatformAction]:
        action_type = "reply_suggestion" if decision.kind == "reply_suggestion" else "follow_up_suggestion"
        title = f"给{user.display_name or user.user_id}的建议"
        return [self._build_action(event=event, decision=decision, action_type=action_type, title=title)]


class XiaohongshuAdapter(BasePlatformAdapter):
    platform = "xiaohongshu"

    def parse_event(self, payload: dict[str, Any]) -> CanonicalEvent:
        author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
        thread_id = str(payload.get("note_id") or payload.get("comment_id") or "xiaohongshu_thread")
        event_type = "comment" if payload.get("comment_text") else "post"
        text = _clean_text(payload.get("comment_text") or payload.get("note_text") or payload.get("caption"))
        user = CanonicalUser(
            platform=self.platform,
            user_id=str(author.get("id") or payload.get("author_id") or "xiaohongshu_author"),
            display_name=_clean_text(author.get("name")),
            profile_hint=_clean_text(author.get("bio")),
            metadata={"source": "drafting"},
        )
        return CanonicalEvent(
            platform=self.platform,
            event_id=str(payload.get("event_id") or payload.get("comment_id") or payload.get("note_id") or thread_id),
            event_type=event_type,
            thread_id=thread_id,
            occurred_at=parse_datetime(payload.get("occurred_at") or payload.get("published_at")),
            text=text,
            user=user,
            raw_payload=payload,
            metadata={
                "topic": _clean_text(payload.get("topic")),
                "note_title": _clean_text(payload.get("title") or payload.get("note_title")),
                "source_scene": _clean_text(payload.get("source_scene")),
            },
        )

    def render_actions(
        self,
        event: CanonicalEvent,
        user: CanonicalUser,
        decision: CoreDecision,
    ) -> list[PlatformAction]:
        action_type = "comment_reply_candidate" if decision.kind == "comment_reply" else "note_draft_candidate"
        title = "小红书评论回复候选" if action_type == "comment_reply_candidate" else "小红书笔记草稿"
        return [self._build_action(event=event, decision=decision, action_type=action_type, title=title)]


class WechatOfficialAdapter(BasePlatformAdapter):
    platform = "wechat_official"

    def parse_event(self, payload: dict[str, Any]) -> CanonicalEvent:
        follower = payload.get("follower") if isinstance(payload.get("follower"), dict) else {}
        user = CanonicalUser(
            platform=self.platform,
            user_id=str(follower.get("openid") or payload.get("openid") or "wechat_official_user"),
            display_name=_clean_text(follower.get("nickname")),
            metadata={"source": "placeholder"},
        )
        thread_id = str(payload.get("conversation_id") or user.user_id)
        return CanonicalEvent(
            platform=self.platform,
            event_id=str(payload.get("event_id") or payload.get("message_id") or f"{thread_id}:official"),
            event_type="message",
            thread_id=thread_id,
            occurred_at=parse_datetime(payload.get("occurred_at") or payload.get("sent_at")),
            text=_clean_text(payload.get("text")),
            user=user,
            raw_payload=payload,
            metadata={"placeholder": True},
        )

    def render_actions(
        self,
        event: CanonicalEvent,
        user: CanonicalUser,
        decision: CoreDecision,
    ) -> list[PlatformAction]:
        return [
            self._build_action(
                event=event,
                decision=decision,
                action_type="reply_suggestion",
                title=f"公众号回复草稿:{user.display_name or user.user_id}",
            )
        ]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
