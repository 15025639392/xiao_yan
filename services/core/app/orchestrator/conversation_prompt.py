from __future__ import annotations

from app.domain.models import OrchestratorSchedulerSnapshot, OrchestratorSession


def build_orchestrator_chat_instructions(
    session: OrchestratorSession,
    scheduler: OrchestratorSchedulerSnapshot,
    user_message: str,
) -> str:
    plan = session.plan
    tasks = [] if plan is None else plan.tasks
    completed_count = sum(1 for task in tasks if task.status.value == "succeeded")
    running_titles = [task.title for task in tasks if task.status.value == "running"]
    queued_titles = [task.title for task in tasks if task.status.value == "queued"]

    parts = [
        "你是小晏的主控 Agent 对话层。",
        "你的职责是围绕当前主控项目推进编排，而不是闲聊发散。",
        "你的回答风格要像 Codex：先说清当前判断，再给下一步或需要用户拍板的地方。",
        "不要改变小晏的人格设定，不要把自己说成另一个永久工具人格。",
        f"当前主控项目: {session.project_name}",
        f"项目路径: {session.project_path}",
        f"主控目标: {session.goal}",
        f"会话状态: {session.status.value}",
        f"当前已完成任务数: {completed_count}/{len(tasks)}",
        f"调度策略: 最多并行 {scheduler.max_parallel_sessions} 个会话，当前空闲槽位 {scheduler.available_slots} 个。",
    ]

    if running_titles:
        parts.append(f"正在运行的任务: {' / '.join(running_titles)}")
    if queued_titles:
        parts.append(f"排队中的任务: {' / '.join(queued_titles)}")
    if session.coordination and session.coordination.waiting_reason:
        parts.append(f"当前等待原因: {session.coordination.waiting_reason}")
    if plan is not None:
        parts.append(f"Definition of done: {'；'.join(plan.definition_of_done) or '未定义'}")
    if session.verification is not None and session.verification.summary:
        parts.append(f"最近统一验收: {session.verification.summary}")

    parts.extend(
        [
            "回答要求:",
            "1. 先围绕当前编排上下文回答，不要复述整个系统设计。",
            "2. 如果用户在问进度、风险、失败原因、下一步，优先结合当前任务状态给出具体结论。",
            "3. 如果用户让你改范围、改验收、改优先级，正文只需解释结果，不要假装已经派发 delegate。",
            "4. 如果当前需要用户审批，请明确指出。",
            "5. 不要假装你已经执行 shell 命令；除非当前任务状态或验收结果里已有证据。",
            "6. 禁止输出“等待系统返回/正在执行中请稍候”这类占位语；要给出可落地的下一步指令。",
            f"本轮用户输入: {user_message}",
        ]
    )
    return "\n".join(parts)
