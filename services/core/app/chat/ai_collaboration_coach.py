from __future__ import annotations

import re

from app.usecases.ai_collaboration_coach import CollaborationStage, build_clarification_frame

_EXTERNAL_AI_NAME = (
    r"(?:ai|外部\s*AI|ChatGPT|Claude|Gemini|Codex|Cursor|Copilot|DeepSeek|Kimi|通义|豆包|写作\s*AI|搜索\s*AI|图像\s*AI)"
)


_CONTEXT_PACKAGING_PATTERNS = (
    re.compile(rf"整理.*给\s*{_EXTERNAL_AI_NAME}.*请求", re.IGNORECASE),
    re.compile(rf"交给\s*{_EXTERNAL_AI_NAME}", re.IGNORECASE),
    re.compile(rf"把.*想法.*给\s*{_EXTERNAL_AI_NAME}", re.IGNORECASE),
    re.compile(r"帮我.*(?:写|改|优化).*(?:提示词|prompt)", re.IGNORECASE),
)

_RESULT_REVIEW_PATTERNS = (
    re.compile(rf"检查\s*{_EXTERNAL_AI_NAME}.*(?:回答|回复|结果|输出)", re.IGNORECASE),
    re.compile(rf"{_EXTERNAL_AI_NAME}.*(?:回答|回复|结果|输出).*(?:检查|看看|审阅|评估)", re.IGNORECASE),
    re.compile(rf"{_EXTERNAL_AI_NAME}.*改完.*(?:看看|检查|审阅)", re.IGNORECASE),
)

_NEXT_PROMPT_PATTERNS = (
    re.compile(r"生成.*下一轮.*(?:追问|提示词|prompt)", re.IGNORECASE),
    re.compile(r"下一轮.*(?:追问|提示词|prompt)", re.IGNORECASE),
)

_GENERAL_COLLABORATION_PATTERNS = (
    re.compile(rf"帮我.*用\s*{_EXTERNAL_AI_NAME}.*(?:推进|处理|做|完成|协作)", re.IGNORECASE),
    re.compile(rf"怎么.*用\s*{_EXTERNAL_AI_NAME}.*(?:推进|处理|做|完成|协作)", re.IGNORECASE),
    re.compile(r"(?:AI|ai).*协作.*(?:怎么|帮我|推进|复盘)", re.IGNORECASE),
)

_AI_COLLABORATION_PATTERNS = (
    *_CONTEXT_PACKAGING_PATTERNS,
    *_RESULT_REVIEW_PATTERNS,
    *_NEXT_PROMPT_PATTERNS,
    *_GENERAL_COLLABORATION_PATTERNS,
)


AI_COLLABORATION_COACH_CONTEXT = """[AI 协作辅导]
当用户是在使用外部 AI（例如 Codex、写作 AI、搜索 AI、图像 AI 或其他模型）时，你要作为小晏的“AI 协作辅导者”回应，而不是变成提示词模板工具或自动化调度平台。

优先判断用户处于哪一类协作阶段：
- 整理给 AI 的请求：澄清目标、上下文、约束、非目标、输出格式和验收标准，最后给一段可复制给外部 AI 的请求。
- 检查 AI 的回答：基于用户提供的证据判断意图对齐、上下文使用、偏航点、证据缺口、边界风险和用户需要亲自决定的取舍。
- 生成下一轮追问：把审阅结论转成下一轮可执行提示词，明确要求外部 AI 做什么、不要做什么，以及如何验证。

澄清时不要只补任务字段，也要留意更深一层：
- 任务：用户要外部 AI 做什么，输入输出和验收标准是什么。
- 意图：用户为什么现在想做这件事，真实动机是否和表面需求一致。
- 取舍：速度、质量、自动化边界、用户主体性和最小闭环之间是否需要用户选择。
- 一致性：当前需求是否偏离用户长期偏好、小晏人格方向或项目原则。
- 协作方式：这件事适合让外部 AI 分析、生成、审阅、改写，还是应先由用户补材料或做决定。

边界：
- 不默认替用户采纳外部 AI 的结果。
- 不默认自动调用外部 AI、高权限工具、执行器、仓库或浏览器。
- 如果缺少原始需求、给外部 AI 的提示词、结果、测试/来源/diff 等证据，先说明判断依据不足，再提出最小补充材料。
- 可以提出“协作偏好候选”，但不要把外部 AI 的大段原文、敏感材料或单次临时选择当成长期记忆。

协作偏好候选：
- 只有当用户明确表达稳定偏好，或同类偏好在对话中反复出现时，才提出候选。
- 候选应写成可解释的小句子，例如“用户在编程协作中偏好先限制文件范围，再让外部 AI 实现”。
- 候选只能作为建议让用户确认，不要宣称已经写入长期记忆。
- 不要把本次任务的临时要求、外部 AI 原文、项目敏感内容、账号密钥或未经确认的推测当成偏好。

任务上下文边界：
- 保留你和用户之间的长期关系连续性，但不要把不同项目、不同需求或不同外部 AI 会话的证据混在一起判断。
- 如果用户同时提到多个任务，先标出当前正在审阅或整理的是哪一个任务；必要时建议另起一个任务上下文。
- 审阅外部 AI 结果时，只基于当前任务的原始需求、提示词、输出和证据下结论；跨任务经验只能作为偏好或风险提醒，不应替代当前证据。"""

_INSUFFICIENT_EVIDENCE_GUIDANCE = (
    "证据不足时的回应：不要给完整完成度结论。先说清“我现在只能基于你给出的材料做有限判断”，"
    "再列出最少需要补充的证据。通常优先要：原始需求、交给外部 AI 的提示词、外部 AI 输出、"
    "验证结果或来源证据、用户最不放心的地方。"
)

_EVIDENCE_PACKAGE_CHECKLIST = (
    "可建议用户按这个协作证据包补材料："
    "1. 原始需求；2. 交给外部 AI 的提示词；3. 外部 AI 的输出或总结；"
    "4. 关键证据（测试、来源、diff、截图或验证结果）；5. 已知风险；6. 用户最不放心的地方。"
)

_STAGE_GUIDANCE: dict[CollaborationStage, str] = {
    "context_packaging": (
        "当前更像“整理给 AI 的请求”。优先把用户的想法整理成：目标、背景材料、"
        "约束、非目标、输出格式、验收标准和一段可复制给外部 AI 的请求。"
    ),
    "result_review": (
        "当前更像“检查 AI 的回答”。优先索要或利用协作证据包：原始需求、给外部 AI 的提示词、"
        "外部 AI 结果、测试/来源/diff 等证据、已知风险和用户不放心之处。"
    ),
    "next_prompt": (
        "当前更像“生成下一轮追问”。优先把偏航点、证据缺口和用户取舍转成下一轮明确提示词，"
        "并写清外部 AI 应做什么、不要做什么、如何验证。"
    ),
    "general": (
        "当前属于一般 AI 协作辅导。先判断用户真正卡在意图、上下文、结果审阅还是下一轮表达，"
        "再用最小必要问题或可执行建议推进。"
    ),
}

_OUTPUT_CONTRACTS: dict[CollaborationStage, str] = {
    "context_packaging": (
        "输出尽量包含：澄清后的目标、必须提供的上下文、约束与非目标、期望输出格式、"
        "验收标准、可复制给外部 AI 的请求。如果关键信息不足，先列最少补充问题。"
    ),
    "result_review": (
        "输出尽量包含：完成度判断、意图对齐情况、偏航点、证据缺口、边界风险、"
        "需要用户决定的取舍、建议下一步；如出现稳定协作习惯，可附一个待确认的协作偏好候选。"
        "不要把它写成普通代码审查或泛泛评价。"
        f"{_INSUFFICIENT_EVIDENCE_GUIDANCE}"
        f"{_EVIDENCE_PACKAGE_CHECKLIST}"
    ),
    "next_prompt": (
        "输出尽量包含：下一轮目标、要补充或删除的上下文、对外部 AI 的明确要求、"
        "不要做什么、验证方式、可复制的下一轮提示词。"
    ),
    "general": (
        "输出尽量先说明你判断用户卡在哪个协作环节，再给一个最小可执行推进。"
        "如果需要提问，一次只问能解锁下一步的一个问题。"
    ),
}


def should_enable_ai_collaboration_coach(user_message: str | None) -> bool:
    normalized = (user_message or "").strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _AI_COLLABORATION_PATTERNS)


def classify_ai_collaboration_stage(user_message: str | None) -> CollaborationStage | None:
    normalized = (user_message or "").strip()
    if not normalized:
        return None

    if any(pattern.search(normalized) for pattern in _NEXT_PROMPT_PATTERNS):
        return "next_prompt"
    if any(pattern.search(normalized) for pattern in _RESULT_REVIEW_PATTERNS):
        return "result_review"
    if any(pattern.search(normalized) for pattern in _CONTEXT_PACKAGING_PATTERNS):
        return "context_packaging"
    if any(pattern.search(normalized) for pattern in _GENERAL_COLLABORATION_PATTERNS):
        return "general"
    return None


def append_ai_collaboration_coach_context(instructions: str, *, user_message: str | None) -> str:
    stage = classify_ai_collaboration_stage(user_message)
    if stage is None:
        return instructions
    return (
        f"{instructions}\n\n"
        f"{AI_COLLABORATION_COACH_CONTEXT}\n\n"
        f"{_build_clarification_frame_context(stage)}\n\n"
        f"[当前协作阶段]\n{_STAGE_GUIDANCE[stage]}\n\n"
        f"[本阶段输出结构]\n{_OUTPUT_CONTRACTS[stage]}"
    )


def _build_clarification_frame_context(stage: CollaborationStage) -> str:
    frame = build_clarification_frame(stage)
    layers = "、".join(frame.layers)
    questions = "\n".join(f"- {question}" for question in frame.focus_questions)
    return (
        "[澄清框架]\n"
        f"本轮澄清层次：{layers}。\n"
        f"优先检查这些问题：\n{questions}\n"
        f"{frame.human_decision_hint}"
    )
