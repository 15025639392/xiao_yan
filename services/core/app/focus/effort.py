from __future__ import annotations

from datetime import datetime

from app.focus.models import FocusEffort


def build_focus_effort(
    *,
    goal_id: str | None,
    goal_title: str,
    why_now: str,
    action_kind: str,
    did_what: str,
    effect: str | None = None,
    next_hint: str | None = None,
    now: datetime | None = None,
) -> FocusEffort:
    payload = {
        "goal_id": goal_id,
        "goal_title": goal_title,
        "why_now": why_now,
        "action_kind": action_kind,
        "did_what": did_what,
        "effect": effect,
        "next_hint": next_hint,
    }
    if now is not None:
        payload["created_at"] = now
    return FocusEffort(**payload)


def focus_adopted_effort(*, goal_id: str, goal_title: str, now: datetime) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="刚接住了用户这轮话题，先把它接成当前焦点。",
        action_kind="focus_adopted",
        did_what="把这轮用户话题转成了新的焦点目标。",
        effect="这条线现在正式进入持续跟进状态。",
        next_hint="接下来会围绕它继续形成计划或推进下一步。",
        now=now,
    )


def focus_resumed_effort(*, goal_id: str, goal_title: str, now: datetime) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="这条之前延后的线索到了重新转回来的时机。",
        action_kind="focus_resumed",
        did_what="把延后的用户话题重新提成了当前焦点。",
        effect="焦点重新回到这件事上了。",
        next_hint="接下来会继续围绕它推进。",
        now=now,
    )


def chain_advanced_effort(*, goal_id: str, goal_title: str, step: int, now: datetime) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="上一代目标刚收住，这条线自然接到了下一步。",
        action_kind="chain_advanced",
        did_what="把目标链推进到了下一代焦点。",
        effect=f"当前已经切到这条线的第{step}步。",
        next_hint="接下来会继续围绕这一代目标推进。",
        now=now,
    )


def command_effort(
    *,
    goal_id: str | None,
    goal_title: str,
    command: str,
    output: str,
    now: datetime,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="这个焦点目标里有一个可以直接落地的安全动作。",
        action_kind="command",
        did_what=f"执行了命令 `{command}`。",
        effect=f"拿到了结果：{output}",
        next_hint="接下来会根据这次执行结果决定下一步。",
        now=now,
    )


def focus_hold_effort(*, goal_id: str | None, goal_title: str, now: datetime) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="当前还有活跃焦点，但还没有进入可直接执行的动作分支。",
        action_kind="focus_hold",
        did_what="先把注意力重新对准当前焦点。",
        effect="这条线仍然被稳稳挂在眼前。",
        next_hint="接下来会继续判断是拆步、执行还是收束。",
        now=now,
    )


def consolidate_effort(*, goal_id: str | None, goal_title: str, now: datetime) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="这条焦点线已经进入后段，需要先收束而不是继续冒进。",
        action_kind="consolidate",
        did_what="先回看并整理这条线目前的推进位置。",
        effect="推进方式从直接往前做，切到了收束整理。",
        next_hint="接下来会决定是正式收住，还是再推进一小步。",
        now=now,
    )


def goal_completed_effort(
    *,
    goal_title: str,
    next_goal_id: str | None,
    next_goal_title: str | None,
    now: datetime,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=next_goal_id,
        goal_title=goal_title,
        why_now="当前焦点目标已经完成，需要确认这条线是收住还是续到下一步。",
        action_kind="goal_completed",
        did_what="先确认了当前焦点已经完成。",
        effect=(
            f"这条线已经接到“{next_goal_title}”。"
            if next_goal_title is not None
            else "这条线先被收住了。"
        ),
        next_hint=(
            f"接下来会围绕“{next_goal_title}”继续推进。"
            if next_goal_title is not None
            else "接下来会等待新的焦点重新形成。"
        ),
        now=now,
    )


def plan_action_effort(
    *,
    goal_id: str,
    goal_title: str,
    step_content: str,
    command: str,
    output: str,
    now: datetime,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="今天计划里明确排到了一个可执行动作。",
        action_kind="plan_action",
        did_what=f"按计划执行了这一步：{step_content}",
        effect=f"命令 `{command}` 已执行，结果是：{output}",
        next_hint="接下来会继续推进计划里的后续步骤。",
        now=now,
    )


def plan_step_effort(
    *,
    goal_id: str,
    goal_title: str,
    step_content: str,
    completed_steps: int,
    total_steps: int,
    plan_done: bool,
    now: datetime,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="今天计划已经排到这一步，需要先把当前小步走完。",
        action_kind="plan_step",
        did_what=f"推进了计划步骤：{step_content}",
        effect=f"今天计划已完成 {completed_steps}/{total_steps} 步。",
        next_hint="计划走完后会切回自主推进。" if plan_done else "接下来会继续走下一步。",
        now=now,
    )


def chat_reply_effort(*, goal_id: str | None, goal_title: str) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="刚围绕当前这条焦点线完成了一轮对话回应。",
        action_kind="chat_reply",
        did_what="先顺着当前焦点把这轮回复接住并说出来了。",
        effect="用户现在能更明确感到她为什么还在围绕这条线继续。",
        next_hint="接下来可以继续推进这条线，或根据用户回应调整焦点。",
    )


def manual_pause_effort(
    *,
    goal_title: str,
    next_goal_id: str | None,
    next_goal_title: str | None,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=next_goal_id,
        goal_title=goal_title,
        why_now="这条焦点线被手动暂停了，需要明确把重心从这里移开。",
        action_kind="manual_pause",
        did_what="先把这条目标暂停了。",
        effect=(
            f"当前重心转到了“{next_goal_title}”。"
            if next_goal_title is not None
            else "当前没有继续挂在眼前的焦点了。"
        ),
        next_hint=(
            f"接下来会围绕“{next_goal_title}”继续推进。"
            if next_goal_title is not None
            else "接下来会等待新的焦点重新形成。"
        ),
    )


def manual_abandon_effort(
    *,
    goal_title: str,
    next_goal_id: str | None,
    next_goal_title: str | None,
) -> FocusEffort:
    return build_focus_effort(
        goal_id=next_goal_id,
        goal_title=goal_title,
        why_now="这条焦点线被明确放下了，需要把当前主线重新收拢。",
        action_kind="manual_abandon",
        did_what="正式放下了这条目标。",
        effect=(
            f"当前重心转到了“{next_goal_title}”。"
            if next_goal_title is not None
            else "眼前这条线已经被清掉了。"
        ),
        next_hint=(
            f"接下来会围绕“{next_goal_title}”继续推进。"
            if next_goal_title is not None
            else "接下来会等待新的焦点重新形成。"
        ),
    )


def manual_focus_switch_effort(*, goal_id: str, goal_title: str) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="这条目标被重新提成了当前焦点。",
        action_kind="manual_focus_switch",
        did_what="把这条目标重新放回当前主线。",
        effect="它现在排到了最前面的焦点位置。",
        next_hint="接下来会重新围绕它生成计划并继续推进。",
    )


def manual_complete_effort(*, goal_id: str, goal_title: str) -> FocusEffort:
    return build_focus_effort(
        goal_id=goal_id,
        goal_title=goal_title,
        why_now="这条目标刚被手动标记完成，需要先保留这拍完成确认。",
        action_kind="manual_complete",
        did_what="先把这条目标标记成完成了。",
        effect="焦点会暂时留在这里，等待自主循环确认是否续到下一步。",
        next_hint="接下来会判断这条线是收住，还是继续接到下一代目标。",
    )
