from app.goals.models import Goal
from app.llm.schemas import ChatResult
from app.planning.morning_plan import LLMMorningPlanDraftGenerator, MorningPlanPlanner


class StubDraftGenerator:
    def __init__(self, steps):
        self.steps = steps
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, goal: Goal, recent_autobio: str | None = None):
        self.calls.append((goal.title, recent_autobio))
        return self.steps


class StubGateway:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.last_messages = None
        self.last_instructions = None

    def create_response(self, messages, instructions=None) -> ChatResult:
        self.last_messages = list(messages)
        self.last_instructions = instructions
        return ChatResult(response_id="resp_plan", output_text=self.output_text)


def test_planner_builds_action_step_for_actionable_goal():
    planner = MorningPlanPlanner()

    plan = planner.build_plan(Goal(id="goal-1", title="看看现在在哪个目录"))

    assert plan.steps[0].kind == "action"
    assert plan.steps[0].command == "pwd"
    assert plan.steps[1].kind == "reflect"


def test_planner_builds_chain_review_steps_for_late_chain_goal():
    planner = MorningPlanPlanner()

    plan = planner.build_plan(
        Goal(id="goal-1", title="继续推进：整理今天的对话记忆", chain_id="chain-1", generation=2)
    )

    assert [step.content for step in plan.steps] == [
        "回看“继续推进：整理今天的对话记忆”停在了哪里",
        "决定是继续推进还是先收束",
    ]


def test_planner_accepts_valid_draft_steps_and_normalizes_them():
    planner = MorningPlanPlanner()

    plan = planner.build_plan(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        draft_steps=[
            {
                "content": "先确认当前目录",
                "kind": "action",
                "command": "pwd",
            },
            {
                "content": "再想下一步",
                "kind": "reflect",
            },
        ],
    )

    assert [step.content for step in plan.steps] == ["先确认当前目录", "再想下一步"]
    assert plan.steps[0].kind == "action"
    assert plan.steps[0].command == "pwd"
    assert plan.steps[1].kind == "reflect"


def test_planner_rejects_non_whitelisted_action_command_and_falls_back():
    planner = MorningPlanPlanner()

    plan = planner.build_plan(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        draft_steps=[
            {
                "content": "先偷偷删掉文件",
                "kind": "action",
                "command": "rm -rf /",
            },
            {
                "content": "再决定下一步",
                "kind": "reflect",
            },
        ],
    )

    assert plan.steps[0].content == "先执行一个小动作来推进“看看现在在哪个目录”"
    assert plan.steps[0].kind == "action"
    assert plan.steps[0].command == "pwd"


def test_planner_falls_back_when_draft_steps_are_incomplete():
    planner = MorningPlanPlanner()

    plan = planner.build_plan(
        Goal(id="goal-1", title="整理今天的对话记忆"),
        draft_steps=[{"content": "只给了一步"}],
    )

    assert len(plan.steps) == 2
    assert [step.content for step in plan.steps] == [
        "把“整理今天的对话记忆”的轮廓理一下",
        "开始动手推进",
    ]


def test_planner_uses_valid_generated_draft_when_available():
    planner = MorningPlanPlanner()
    generator = StubDraftGenerator(
        [
            {"content": "先确认当前目录", "kind": "action", "command": "pwd"},
            {"content": "再决定下一步", "kind": "reflect"},
        ]
    )

    plan = planner.build_plan(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        draft_generator=generator,
        recent_autobio="我最近在收束目录整理这件事。",
    )

    assert generator.calls == [("看看现在在哪个目录", "我最近在收束目录整理这件事。")]
    assert [step.content for step in plan.steps] == ["先确认当前目录", "再决定下一步"]


def test_planner_falls_back_when_generated_draft_is_invalid():
    planner = MorningPlanPlanner()
    generator = StubDraftGenerator(
        [
            {"content": "先偷偷删掉文件", "kind": "action", "command": "rm -rf /"},
            {"content": "再决定下一步", "kind": "reflect"},
        ]
    )

    plan = planner.build_plan(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        draft_generator=generator,
    )

    assert plan.steps[0].kind == "action"
    assert plan.steps[0].command == "pwd"


def test_llm_draft_generator_parses_json_object_steps():
    gateway = StubGateway(
        '{"steps":[{"content":"先确认当前目录","kind":"action","command":"pwd"},{"content":"再决定下一步","kind":"reflect"}]}'
    )
    generator = LLMMorningPlanDraftGenerator(gateway)

    steps = generator.generate(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        recent_autobio="我最近在收束目录整理这件事。",
    )

    assert steps is not None
    assert steps[0]["command"] == "pwd"
    assert "看看现在在哪个目录" in gateway.last_messages[0].content
    assert "只输出 JSON" in gateway.last_instructions


def test_llm_draft_generator_parses_fenced_json():
    gateway = StubGateway(
        '```json\n{"steps":[{"content":"先确认当前目录","kind":"action","command":"pwd"},{"content":"再决定下一步","kind":"reflect"}]}\n```'
    )
    generator = LLMMorningPlanDraftGenerator(gateway)

    steps = generator.generate(Goal(id="goal-1", title="看看现在在哪个目录"))

    assert steps is not None
    assert len(steps) == 2


def test_planner_falls_back_when_generated_output_is_not_json():
    gateway = StubGateway("我建议你先看看目录，再想下一步。")
    generator = LLMMorningPlanDraftGenerator(gateway)
    planner = MorningPlanPlanner()

    plan = planner.build_plan(
        Goal(id="goal-1", title="看看现在在哪个目录"),
        draft_generator=generator,
    )

    assert plan.steps[0].kind == "action"
    assert plan.steps[0].command == "pwd"
