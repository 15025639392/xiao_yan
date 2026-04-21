from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)
from app.domain.models import XhsWorkDomainState, XhsWorkStatus
from app.memory.repository import MemoryRepository
from app.runtime import StateStore


@dataclass
class XhsWorkDomainAction:
    kind: str  # "scouting" | "drafting" | "publishing" | "idle"
    title: str
    data: dict


_CREATOR_HOME_URL = "https://creator.xiaohongshu.com/new/home"
_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image"
_CREATOR_HOME_SESSION_ID = "xhs-login"


class XhsWorkDomainEngine:
    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        gateway=None,  # ChatGateway, optional for now
    ):
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.gateway = gateway
        # In-memory cache of last scouting result (not persisted separately)
        self._last_scouting_data: dict | None = None
        # Skip timer on first tick to avoid triggering on service startup
        self._is_first_tick = True

    def tick(self) -> XhsWorkDomainAction | None:
        """检查定时器 + 驱动状态机一步。返回当前动作或 None。"""
        domain = self._get_or_init_domain()
        # Skip timer check on very first tick to avoid triggering on service startup
        if self._is_first_tick:
            self._is_first_tick = False
        else:
            self._check_and_fire_timer(domain)
        return self._step(domain)

    def _get_or_init_domain(self) -> XhsWorkDomainState:
        state = self.state_store.get()
        if state.xhs_work_domain is None:
            state.xhs_work_domain = XhsWorkDomainState()
            self.state_store.set(state)
        return state.xhs_work_domain

    def _check_and_fire_timer(self, domain: XhsWorkDomainState) -> None:
        """检查是否该开始新一轮侦察。"""
        if domain.state.status != XhsWorkStatus.IDLE:
            return  # 已经在流程中，不重复触发
        interval_hours = domain.profile.scouting_interval_hours
        last = domain.state.last_scouting_at
        now = datetime.now(timezone.utc)
        if last is None or (now - last).total_seconds() >= interval_hours * 3600:
            domain.state.status = XhsWorkStatus.SCOUTING
            self._save(domain)

    def _step(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        status = domain.state.status
        if status == XhsWorkStatus.SCOUTING:
            return self._do_scouting(domain)
        elif status == XhsWorkStatus.DRAFTING:
            return self._do_drafting(domain)
        elif status == XhsWorkStatus.PUBLISHING:
            return self._do_publishing(domain)
        elif status == XhsWorkStatus.BLOCKED:
            return None
        return None

    def _save(self, domain: XhsWorkDomainState) -> None:
        state = self.state_store.get()
        state.xhs_work_domain = domain
        self.state_store.set(state)

    def _do_scouting(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """browser organ 打开创作首页，提取话题和活动。"""
        try:
            open_result = call_browser_capability(
                "browser.open",
                {
                    "url": _CREATOR_HOME_URL,
                    "session_id": _CREATOR_HOME_SESSION_ID,
                    "headless": False,
                    "activate": False,
                },
                timeout_seconds=20.0,
            )
        except BrowserOrganUnavailable:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "浏览器器官不可用"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser organ unavailable"},
            )
        except BrowserCapabilityError:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser open failed"},
            )

        session_id = open_result.get("session_id")
        if not session_id:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "no session_id"},
            )

        try:
            snapshot = call_browser_capability(
                "browser.snapshot",
                {"session_id": session_id, "include_text": True},
                timeout_seconds=15.0,
            )
        except BrowserCapabilityError:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "页面快照失败"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "snapshot failed"},
            )
        finally:
            self._close_session(session_id)

        text_content = snapshot.get("text_content") or ""

        # Detect login page (check first 500 chars for login UI)
        login_indicators = ["登录", "login", "账号登录", "手机号登录", "密码登录", "验证码登录"]
        text_sample = text_content[:500].lower()
        if any(ind.lower() in text_sample for ind in login_indicators):
            # Further verify: if we can't find topic patterns, it's likely a login page
            if "#" not in text_content[:1000] and "话题" not in text_content[:500]:
                domain.state.status = XhsWorkStatus.BLOCKED
                domain.state.current_bottleneck = "需要登录小红书账号"
                self._save(domain)
                self._close_session(session_id)
                return XhsWorkDomainAction(
                    kind="scouting",
                    title="需要登录",
                    data={"error": "login required"},
                )

        # Use the proper extraction function
        from app.usecases.xiaohongshu_creator_home_capture import extract_creator_home_from_raw_text
        extracted = extract_creator_home_from_raw_text(text_content)

        topics_data = [
            {"topic": t.topic, "participation_count": t.participation_count, "view_count": t.view_count}
            for t in extracted.topics
        ]
        activities_data = [
            {"title": a.title, "date_range": a.date_range, "incentive_hint": a.incentive_hint}
            for a in extracted.activities
        ]

        # Cache in instance for drafting
        self._last_scouting_data = {
            "topics": topics_data,
            "activities": activities_data,
            "account_name": extracted.account_name,
            "raw_text": text_content,
        }

        topic_count = len(topics_data)
        activity_count = len(activities_data)

        # Persist account name to profile
        if extracted.account_name:
            domain.profile.account_name = extracted.account_name
        elif topic_count > 0 or activity_count > 0:
            # Scouting succeeded but account name not found in text
            # Mark as logged in with unknown account so login guidance clears
            if not domain.profile.account_name or domain.profile.account_name in ("", "当前账号"):
                domain.profile.account_name = "已登录账号"

        now = datetime.now(timezone.utc)
        domain.state.status = XhsWorkStatus.DRAFTING
        domain.state.last_scouting_at = now
        domain.state.current_focus = f"发现 {topic_count} 个话题、{activity_count} 个活动"
        domain.state.current_bottleneck = ""
        self._save(domain)

        return XhsWorkDomainAction(
            kind="scouting",
            title=f"侦察完成：{topic_count} 个话题",
            data={"topics": topics_data, "activities": activities_data},
        )

    def _do_drafting(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """基于侦察结果生成草稿，放入待发布队列。"""
        if not self._last_scouting_data:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "无侦察数据，跳过草稿生成"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无侦察数据", data={})

        topics = self._last_scouting_data.get("topics", [])
        activities = self._last_scouting_data.get("activities", [])
        account_name = self._last_scouting_data.get("account_name", "")

        # Build opportunity items from scouting data for LLM prompt
        opportunity_items = []
        for t in topics[:5]:
            opportunity_items.append({
                "source_kind": "topic",
                "title": t.get("topic", ""),
                "summary": f"参与人数: {t.get('participation_count', '未知')}",
            })
        for a in activities[:3]:
            opportunity_items.append({
                "source_kind": "activity",
                "title": a.get("title", ""),
                "summary": a.get("date_range", "") + " " + (a.get("incentive_hint") or ""),
            })

        if not opportunity_items:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "未发现话题或活动"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无机会内容", data={})

        # Use first opportunity for draft generation
        opportunity = opportunity_items[0]
        prompt = self._build_draft_prompt(opportunity)

        # Call LLM via gateway if available
        generated_title = ""
        generated_body = ""
        if self.gateway is not None:
            from app.llm.schemas import ChatMessage
            messages = [ChatMessage(role="user", content=prompt)]
            try:
                result = self.gateway.create_response(messages, instructions="你是一个小红书内容创作专家，直接输出标题和正文，不要其他解释。")
                output_text = result.output_text or ""
                # Parse title from output (expecting "标题：...正文：...")
                if "标题：" in output_text:
                    parts = output_text.split("标题：", 1)
                    if len(parts) > 1:
                        title_and_body = parts[1]
                        if "正文：" in title_and_body:
                            title_parts = title_and_body.split("正文：", 1)
                            generated_title = title_parts[0].strip()
                            generated_body = title_parts[1].strip()
                        else:
                            generated_title = title_and_body.strip()
                            generated_body = ""
                if not generated_title:
                    generated_title = f"探索 {opportunity['title'][:15]} 的创作灵感"
                    generated_body = output_text[:500] if output_text else f"根据最新侦察结果生成的内容草稿：{opportunity['title']}"
            except Exception as exc:
                # Fallback on LLM error
                generated_title = ""
                generated_body = ""

        # Fallback if no LLM result
        if not generated_title:
            generated_title = f"探索 {opportunity['title'][:20]} 的创作灵感"
            generated_body = f"根据最新侦察结果生成的内容草稿：{opportunity['title']}。{opportunity.get('summary', '')}"

        draft_id = str(uuid.uuid4())[:8]
        draft = {
            "draft_id": draft_id,
            "title": generated_title,
            "body": generated_body,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "source_kind": opportunity.get("source_kind", "topic"),
            "opportunity_title": opportunity.get("title", ""),
        }
        domain.state.pending_drafts = [draft]
        domain.state.status = XhsWorkStatus.PUBLISHING
        domain.state.backlog_count = 1
        self._save(domain)

        return XhsWorkDomainAction(
            kind="drafting",
            title=f"草稿生成：{generated_title[:20]}",
            data={"draft_id": draft_id, "title": generated_title},
        )

    def _do_publishing(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """从队列取草稿，通过 browser.publish 发布。"""
        drafts = domain.state.pending_drafts
        if not drafts:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "草稿队列为空"
            self._save(domain)
            return XhsWorkDomainAction(kind="idle", title="无草稿可发", data={})

        draft = drafts[0]
        selector = domain.profile.auto_publish_selector

        # 如果没有配置 selector，先尝试动态发现
        if not selector:
            selector = self._find_publish_button_sync()
            if not selector:
                domain.state.status = XhsWorkStatus.BLOCKED
                domain.state.current_bottleneck = "找不到发布按钮"
                self._save(domain)
                return XhsWorkDomainAction(
                    kind="publishing",
                    title="发布失败",
                    data={"error": "publish button not found"},
                )
            # Cache discovered selector for next time
            domain.profile.auto_publish_selector = selector
            self._save(domain)

        try:
            open_result = call_browser_capability(
                "browser.open",
                {"url": _PUBLISH_URL, "headless": False},
                timeout_seconds=20.0,
            )
        except BrowserOrganUnavailable:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "浏览器器官不可用"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title="发布失败",
                data={"error": "browser organ unavailable"},
            )

        session_id = open_result.get("session_id")
        if not session_id:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "无法打开发布页"
            self._save(domain)
            return XhsWorkDomainAction(kind="publishing", title="打开发布页失败", data={})

        try:
            publish_result = call_browser_capability(
                "browser.publish",
                {
                    "session_id": session_id,
                    "title": draft.get("title", ""),
                    "body": draft.get("body", ""),
                    "publish_selector": selector,
                },
                timeout_seconds=20.0,
            )
        except BrowserCapabilityError as exc:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = f"发布失败: {exc}"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title="发布失败",
                data={"error": str(exc)},
            )
        finally:
            self._close_session(session_id)

        publish_clicked = publish_result.get("publish_clicked", False)
        status = publish_result.get("status", "unknown")

        if publish_clicked:
            # 发布成功
            now = datetime.now(timezone.utc)
            published_entry = {
                "draft_id": draft.get("draft_id"),
                "title": draft.get("title"),
                "published_at": now.isoformat(),
                "post_url": _PUBLISH_URL,
            }
            domain.state.pending_drafts = drafts[1:]
            domain.state.last_published_at = now
            domain.state.backlog_count = max(0, domain.state.backlog_count - 1)
            domain.state.status = XhsWorkStatus.IDLE_REVIEWING
            domain.state.current_focus = "发布成功，等待补图"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title=f"发布成功：{draft.get('title', '')[:20]}",
                data={"published": published_entry},
            )
        else:
            # 表单填充了但没点到发布按钮（可能是 awaiting_image_upload 或找不到按钮）
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = f"无法点击发布按钮（status={status}）"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title="发布未完成",
                data={"status": status},
            )

    def _close_session(self, session_id: str) -> None:
        if session_id == _CREATOR_HOME_SESSION_ID:
            return
        try:
            call_browser_capability(
                "browser.close",
                {"session_id": session_id},
                timeout_seconds=5.0,
            )
        except Exception:
            pass

    def _find_publish_button_sync(self) -> str | None:
        """用 browser.find_publish_button capability 找到发布按钮 selector。"""
        try:
            open_result = call_browser_capability(
                "browser.open",
                {"url": _PUBLISH_URL, "headless": False},
                timeout_seconds=15.0,
            )
        except (BrowserOrganUnavailable, BrowserCapabilityError):
            return None

        session_id = open_result.get("session_id")
        if not session_id:
            return None

        try:
            result = call_browser_capability(
                "browser.find_publish_button",
                {"session_id": session_id},
                timeout_seconds=10.0,
            )
            if result.get("found"):
                return result.get("selector")
            return None
        except (BrowserCapabilityError, BrowserOrganUnavailable):
            return None
        finally:
            self._close_session(session_id)

    def _node_is_publish_button(self, node: dict) -> bool:
        role = node.get("role", "").lower()
        name = node.get("name", "")
        if role == "button" and name and ("发布" in name or "submit" in name.lower()):
            return True
        if role in ("button", "link") and name and "发布" in name:
            return True
        return False

    def _selector_for_node(self, node: dict) -> str:
        # 优先用 aria-label 或 name
        name = node.get("name", "")
        if name:
            return f"button:has-text('{name}')"
        # 降级到 tag + index（不太可靠）
        return "button[type='submit']"

    def _build_draft_prompt(self, opportunity: dict) -> str:
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        source_kind = opportunity.get("source_kind", "topic")
        return (
            "你现在不是在写运营建议，也不是在写方法论说明，而是在直接写一篇可以人工确认后发布的小红书图文稿。\n"
            "要求：\n"
            "1. 语言像真人发笔记，少抽象词，少空话。\n"
            "2. 必须写出一个明确场景、一个明确问题、一个明确动作。\n"
            '3. 禁止出现"最小闭环""验证反馈""轻量转化""先跑通"这类产品黑话。\n'
            "4. 不要写成课程大纲，不要写成写作指导。\n"
            "5. 输出必须严格使用下面格式。\n\n"
            f"机会来源：{source_kind}\n"
            f"机会标题：{title}\n"
            f"补充信息：{summary}\n\n"
            "请严格输出：\n"
            "标题：...\n\n正文：...\n"
        )

    def _extract_topics_and_activities(self, text: str) -> tuple[list[str], list[str]]:
        """从页面文本中提取话题和活动。简单实现。"""
        lines = text.split("\n")
        topics, activities = [], []
        current_section = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if "话题" in lower or "topic" in lower:
                current_section = "topics"
                continue
            if "活动" in lower or "campaign" in lower:
                current_section = "activities"
                continue
            if current_section == "topics" and len(stripped) < 100:
                topics.append(stripped)
            elif current_section == "activities" and len(stripped) < 200:
                activities.append(stripped)
        return topics[:10], activities[:5]
