from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_creative_writing_service, get_optional_chat_gateway
from app.creative_writing.repository import FileCreativeWritingRepository
from app.creative_writing.service import CreativeWritingService
from app.llm.schemas import ChatResult
from app.main import app
from app.persona.models import EmotionIntensity, EmotionType
from app.persona.service import InMemoryPersonaRepository, PersonaService
from app.world.models import WorldState
from app.world.repository import InMemoryWorldRepository


def build_service(
    tmp_path: Path,
    *,
    persona_service: PersonaService | None = None,
    world_repository: InMemoryWorldRepository | None = None,
) -> CreativeWritingService:
    return CreativeWritingService(
        repository=FileCreativeWritingRepository(tmp_path / "novels"),
        persona_service=persona_service or PersonaService(repository=InMemoryPersonaRepository()),
        world_repository=world_repository,
    )


def test_creative_writing_project_creates_organized_folder(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/creative-writing/projects",
        json={
            "title": "雨夜灯塔",
            "premise": "小晏反复梦见一座只在雨夜出现的灯塔。",
            "characters": [{"name": "晏", "role": "记录梦的人", "desire": "找到灯塔"}],
            "outline": ["雨夜醒来", "灯塔第一次回望"],
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    project_dir = tmp_path / "novels" / project["folder_name"]
    assert project_dir.exists()
    assert (project_dir / "project.json").exists()
    assert (project_dir / "README.md").read_text(encoding="utf-8").startswith("# 雨夜灯塔")


def test_creative_writing_fragment_is_saved_under_chapter_folder(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "玻璃海", "premise": "一片记住所有声音的海。"},
    ).json()["project"]
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "海面像一张没有寄出的信。", "summary": "她第一次看见玻璃海。"},
    )

    assert response.status_code == 200
    fragment = response.json()["fragment"]
    fragment_path = tmp_path / "novels" / fragment["file_path"]
    assert fragment["chapter_index"] == 1
    assert fragment_path.read_text(encoding="utf-8") == "海面像一张没有寄出的信。"
    assert "chapter-001/fragments/fragment-001.md" in fragment["file_path"]


def test_creative_writing_can_generate_fragment_with_gateway(tmp_path: Path):
    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(output_text='{"summary":"地下花园发亮。","next_intention":"写她靠近花园。"}')
            assert "小说标题：地下花园" in messages[0].content
            assert "你正在写属于你自己的小说" in instructions
            return ChatResult(output_text="地下花园在凌晨三点轻轻发亮。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "地下花园", "premise": "城市地下藏着一座会呼吸的花园。"},
    ).json()["project"]
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"intention": "写她第一次听见花开。"},
    )

    assert response.status_code == 200
    fragment = response.json()["fragment"]
    fragment_path = tmp_path / "novels" / fragment["file_path"]
    assert fragment_path.read_text(encoding="utf-8") == "地下花园在凌晨三点轻轻发亮。"


def test_creative_writing_context_reads_recent_fragment_continuity(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "回声书店", "premise": "一家会替客人保存遗憾的书店。"},
    ).json()["project"]
    client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "她把伞靠在门边，听见书架深处有人叫她的小名。", "summary": "她第一次进入书店。"},
    )

    response = client.get(f"/creative-writing/projects/{project['id']}/context")

    assert response.status_code == 200
    context = response.json()["context"]
    assert context["recent_summaries"] == ["她第一次进入书店。"]
    assert "书架深处有人叫她的小名" in context["recent_excerpt"]


def test_creative_writing_generation_uses_recent_context(tmp_path: Path):
    captured: dict[str, str] = {}

    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(output_text='{"summary":"书店归还雨伞。","next_intention":"写她追问雨伞。"}')
            captured["prompt"] = messages[0].content
            return ChatResult(output_text="第二天，书店把那把伞还给了另一个人。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "回声书店", "premise": "一家会替客人保存遗憾的书店。"},
    ).json()["project"]
    client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "她把伞靠在门边。", "summary": "她第一次进入书店。"},
    )
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"intention": "写第二次回到书店。"},
    )

    assert response.status_code == 200
    assert "上一段连续性资料" in captured["prompt"]
    assert "她第一次进入书店。" in captured["prompt"]
    assert "她把伞靠在门边。" in captured["prompt"]


def test_creative_writing_habit_state_is_saved_on_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "停电地图", "premise": "城市停电后，墙上浮出另一张地图。"},
    ).json()["project"]
    response = client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={
            "attachment_reason": "她想知道那张地图是不是在等自己。",
            "last_pause": "停在地图第一次发光。",
            "next_intention": "写她伸手碰到地图边缘。",
            "cadence_note": "夜里适合慢慢写。",
        },
    )

    assert response.status_code == 200
    habit_state = response.json()["project"]["habit_state"]
    assert habit_state["attachment_reason"] == "她想知道那张地图是不是在等自己。"
    project_file = tmp_path / "novels" / project["folder_name"] / "project.json"
    assert "写她伸手碰到地图边缘。" in project_file.read_text(encoding="utf-8")


def test_creative_writing_generation_uses_habit_state(tmp_path: Path):
    captured: dict[str, str] = {}

    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(output_text='{"summary":"地图躲开了她。","next_intention":"写她追上地图。"}')
            captured["prompt"] = messages[0].content
            return ChatResult(output_text="她伸出手，地图像一尾鱼那样轻轻避开。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "停电地图", "premise": "城市停电后，墙上浮出另一张地图。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={
            "attachment_reason": "她想知道地图背后是不是有人。",
            "last_pause": "停在手指快碰到墙面。",
            "next_intention": "写地图躲开她。",
        },
    )
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={},
    )

    assert response.status_code == 200
    assert "创作牵挂：她想知道地图背后是不是有人。" in captured["prompt"]
    assert "上次停顿：停在手指快碰到墙面。" in captured["prompt"]
    assert "下次意向：写地图躲开她。" in captured["prompt"]


def test_creative_writing_auto_digests_generated_fragment(tmp_path: Path):
    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(
                    output_text=(
                        '{"summary":"她发现地图会避开触碰。",'
                        '"next_intention":"写她追着地图走进停电的楼道。",'
                        '"should_advance_chapter":true,'
                        '"chapter_closure_reason":"地图第一次回应了她，本章钩子已经成立。"}'
                    )
                )
            return ChatResult(output_text="她伸出手，地图像一尾鱼那样轻轻避开。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "停电地图", "premise": "城市停电后，墙上浮出另一张地图。"},
    ).json()["project"]
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"intention": "写地图第一次躲开她。"},
    )

    assert response.status_code == 200
    fragment = response.json()["fragment"]
    assert fragment["summary"] == "她发现地图会避开触碰。"
    assert fragment["digest"]["next_intention"] == "写她追着地图走进停电的楼道。"
    assert fragment["digest"]["should_advance_chapter"] is True

    project_response = client.get(f"/creative-writing/projects/{project['id']}").json()
    assert project_response["project"]["habit_state"]["next_intention"] == "写她追着地图走进停电的楼道。"
    fragment_file = tmp_path / "novels" / fragment["file_path"].replace(".md", ".json")
    assert "地图第一次回应了她" in fragment_file.read_text(encoding="utf-8")


def test_creative_writing_manual_summary_skips_auto_digest(tmp_path: Path):
    class FakeGateway:
        def create_response(self, messages, instructions=None):
            raise AssertionError("manual summary should not invoke the gateway")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "手写摘要", "premise": "她坚持给这一段自己命名。"},
    ).json()["project"]
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "她把这段亲手折起来。", "summary": "她手动收好这一段。"},
    )

    assert response.status_code == 200
    fragment = response.json()["fragment"]
    assert fragment["summary"] == "她手动收好这一段。"
    assert fragment["digest"] is None


def test_creative_writing_fragment_summary_does_not_overwrite_explicit_intention(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "旧电梯", "premise": "旧电梯只在没人按的时候抵达。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={"next_intention": "写她听见电梯里有人叫门。"},
    )
    client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "电梯停在了不存在的十三层。", "summary": "她看见十三层。"},
    )

    response = client.get(f"/creative-writing/projects/{project['id']}")

    assert response.status_code == 200
    assert response.json()["project"]["habit_state"]["next_intention"] == "写她听见电梯里有人叫门。"


def test_creative_writing_impulses_recommend_clear_next_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    quiet_project = client.post(
        "/creative-writing/projects",
        json={"title": "无声钟楼", "premise": "钟楼里所有钟都拒绝报时。"},
    ).json()["project"]
    vivid_project = client.post(
        "/creative-writing/projects",
        json={"title": "停电地图", "premise": "城市停电后，墙上浮出另一张地图。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{vivid_project['id']}/habit",
        json={
            "attachment_reason": "她想知道地图为什么只给她看。",
            "last_pause": "停在地图发出第一声呼吸。",
            "next_intention": "写她跟着地图走进楼梯间。",
        },
    )

    response = client.get("/creative-writing/impulses")

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_project_id"] == vivid_project["id"]
    assert body["impulses"][0]["project_id"] == vivid_project["id"]
    assert body["impulses"][0]["score"] > body["impulses"][1]["score"]
    assert quiet_project["id"] in {item["project_id"] for item in body["impulses"]}


def test_creative_writing_impulses_do_not_recommend_finished_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "完结之海", "premise": "一片终于学会安静的海。"},
    ).json()["project"]
    service.repository.save_project(
        service.get_project(project["id"]).model_copy(update={"status": "finished"})
    )

    response = client.get("/creative-writing/impulses")

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_project_id"] is None
    assert body["impulses"][0]["score"] == 0
    assert body["impulses"][0]["suggested_action"] == "回看或整理成稿"


def test_creative_writing_impulses_include_low_energy_context(tmp_path: Path):
    world_repository = InMemoryWorldRepository()
    world_repository.save_world_state(
        WorldState(
            time_of_day="night",
            energy="low",
            mood="tired",
            focus_tension="low",
        )
    )
    service = build_service(tmp_path, world_repository=world_repository)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    client.post(
        "/creative-writing/projects",
        json={"title": "夜航纸船", "premise": "一只纸船每晚都会回到窗台。"},
    )

    response = client.get("/creative-writing/impulses")

    assert response.status_code == 200
    impulse = response.json()["impulses"][0]
    assert impulse["score"] == 0
    assert "此刻能量偏低" in " ".join(impulse["reasons"])
    assert "世界状态偏疲惫" in " ".join(impulse["reasons"])
    assert response.json()["being_context"]["energy"] == "low"
    assert response.json()["being_context"]["mood"] == "tired"


def test_creative_writing_impulses_use_persona_engagement(tmp_path: Path):
    persona_service = PersonaService(repository=InMemoryPersonaRepository())
    persona_service.apply_emotion(
        EmotionType.ENGAGED,
        EmotionIntensity.MODERATE,
        reason="她刚整理出一个想写的场景。",
        source="creative_writing",
    )
    service = build_service(tmp_path, persona_service=persona_service)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    client.post(
        "/creative-writing/projects",
        json={"title": "回声邮局", "premise": "邮局只投递没有说出口的话。"},
    )

    response = client.get("/creative-writing/impulses")

    assert response.status_code == 200
    impulse = response.json()["impulses"][0]
    assert impulse["score"] > 10
    assert "当前情绪是 engaged" in " ".join(impulse["reasons"])
    assert response.json()["being_context"]["primary_emotion"] == "engaged"


def test_creative_writing_session_suggestion_prepares_confirmable_session(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "雨巷档案", "premise": "每场雨都会留下一个无人认领的档案袋。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={
            "attachment_reason": "她想知道档案袋为什么认识她。",
            "last_pause": "停在她拆开第一枚湿掉的封蜡。",
            "next_intention": "写档案袋里出现她童年的地址。",
        },
    )
    client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "雨水把档案袋的边角泡软了。", "summary": "她捡到第一个档案袋。"},
    )

    response = client.get("/creative-writing/session-suggestion")

    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["project_id"] == project["id"]
    assert suggestion["intention"] == "写档案袋里出现她童年的地址。"
    assert suggestion["suggested_action"] == "继续写一个短片段"
    assert "雨水把档案袋的边角泡软了。" in suggestion["context"]["recent_excerpt"]


def test_creative_writing_session_suggestion_is_empty_without_active_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "安静终章", "premise": "一个故事终于愿意停下来。"},
    ).json()["project"]
    service.repository.save_project(
        service.get_project(project["id"]).model_copy(update={"status": "finished"})
    )

    response = client.get("/creative-writing/session-suggestion")

    assert response.status_code == 200
    assert response.json()["suggestion"] is None


def test_creative_writing_can_create_pending_session_from_suggestion(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "雾中索引", "premise": "雾会替城市重新编排目录。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={
            "attachment_reason": "她想知道自己为什么被雾编进最后一页。",
            "next_intention": "写她翻到自己的名字。",
        },
    )

    response = client.post("/creative-writing/sessions")

    assert response.status_code == 200
    session = response.json()["session"]
    assert session["project_id"] == project["id"]
    assert session["status"] == "pending"
    assert session["intention"] == "写她翻到自己的名字。"
    session_path = tmp_path / "novels" / project["folder_name"] / "sessions" / f"session-{session['id']}.json"
    assert session_path.exists()


def test_creative_writing_session_list_can_filter_by_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    first = client.post(
        "/creative-writing/projects",
        json={"title": "纸桥", "premise": "桥只在纸上能通行。"},
    ).json()["project"]
    second = client.post(
        "/creative-writing/projects",
        json={"title": "月台", "premise": "末班车从不载活人。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{first['id']}/habit",
        json={"attachment_reason": "纸桥还没有走完。", "next_intention": "写她踏上桥。"},
    )
    client.post(f"/creative-writing/projects/{first['id']}/sessions")
    client.patch(
        f"/creative-writing/projects/{second['id']}/habit",
        json={"attachment_reason": "月台的灯还亮着。", "next_intention": "写她听见广播。"},
    )
    client.post(f"/creative-writing/projects/{second['id']}/sessions")

    response = client.get(f"/creative-writing/sessions?project_id={second['id']}")

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["project_id"] == second["id"]


def test_creative_writing_pending_session_is_empty_without_active_project(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "终止线", "premise": "故事停在一条看不见的线前。"},
    ).json()["project"]
    service.repository.save_project(
        service.get_project(project["id"]).model_copy(update={"status": "finished"})
    )

    response = client.post("/creative-writing/sessions")

    assert response.status_code == 200
    assert response.json()["session"] is None
    assert client.get("/creative-writing/sessions").json()["sessions"] == []


def test_creative_writing_can_execute_pending_session_with_manual_content(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "铁门之后", "premise": "一扇铁门每天凌晨都会换到不同街口。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={"attachment_reason": "她想知道门后是不是旧家。", "next_intention": "写她推开铁门。"},
    )
    session = client.post(f"/creative-writing/projects/{project['id']}/sessions").json()["session"]

    response = client.post(
        f"/creative-writing/sessions/{session['id']}/execute",
        json={"content": "铁门后面不是院子，是一整条下雨的走廊。", "summary": "她推开铁门。"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["status"] == "completed"
    assert body["session"]["completed_fragment_id"] == body["fragment"]["id"]
    fragment_path = tmp_path / "novels" / body["fragment"]["file_path"]
    assert fragment_path.read_text(encoding="utf-8") == "铁门后面不是院子，是一整条下雨的走廊。"


def test_creative_writing_can_execute_pending_session_with_gateway(tmp_path: Path):
    captured: dict[str, str] = {}

    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(output_text='{"summary":"铁门后有人留灯。","next_intention":"写她走向灯。"}')
            captured["prompt"] = messages[0].content
            return ChatResult(output_text="她推开铁门，看见门后有人替她留了一盏灯。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "铁门之后", "premise": "一扇铁门每天凌晨都会换到不同街口。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={"attachment_reason": "她想知道门后是不是旧家。", "next_intention": "写她推开铁门。"},
    )
    session = client.post(f"/creative-writing/projects/{project['id']}/sessions").json()["session"]
    response = client.post(f"/creative-writing/sessions/{session['id']}/execute", json={})

    assert response.status_code == 200
    assert "本次写作意图：写她推开铁门。" in captured["prompt"]
    assert response.json()["fragment"]["content"] == "她推开铁门，看见门后有人替她留了一盏灯。"


def test_creative_writing_rejects_completed_session_execution(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "重复之门", "premise": "同一扇门不能被同一个人推开两次。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={"attachment_reason": "门已经在等她。", "next_intention": "写第一次推门。"},
    )
    session = client.post(f"/creative-writing/projects/{project['id']}/sessions").json()["session"]
    client.post(
        f"/creative-writing/sessions/{session['id']}/execute",
        json={"content": "她推开门。"},
    )

    response = client.post(
        f"/creative-writing/sessions/{session['id']}/execute",
        json={"content": "她又推开门。"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "writing session is not pending"


def test_creative_writing_rejects_stale_session_context(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "换章之前", "premise": "每一章都会换一扇窗。"},
    ).json()["project"]
    client.patch(
        f"/creative-writing/projects/{project['id']}/habit",
        json={"attachment_reason": "她还没看窗外。", "next_intention": "写她走到窗边。"},
    )
    session = client.post(f"/creative-writing/projects/{project['id']}/sessions").json()["session"]
    client.post(
        f"/creative-writing/projects/{project['id']}/chapters/advance",
        json={"summary": "她还没有靠近窗。"},
    )

    response = client.post(
        f"/creative-writing/sessions/{session['id']}/execute",
        json={"content": "她走到窗边。"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "writing session context no longer matches the current chapter"


def test_creative_writing_can_advance_to_next_chapter(tmp_path: Path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "潮汐信箱", "premise": "海边有一只只在退潮时出现的信箱。"},
    ).json()["project"]
    response = client.post(
        f"/creative-writing/projects/{project['id']}/chapters/advance",
        json={"title": "退潮", "summary": "她第一次打开信箱，发现里面有一封未来寄来的信。"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["current_chapter_index"] == 2
    assert body["chapter_summary"]["chapter_index"] == 1
    summary_path = tmp_path / "novels" / body["chapter_summary"]["file_path"]
    assert summary_path.read_text(encoding="utf-8").startswith("# 退潮")


def test_new_chapter_context_uses_previous_summary_not_old_excerpt(tmp_path: Path):
    captured: dict[str, str] = {}

    class FakeGateway:
        def create_response(self, messages, instructions=None):
            if "创作消化器" in instructions:
                return ChatResult(output_text='{"summary":"海雾读完信。","next_intention":"写她听见回声。"}')
            captured["prompt"] = messages[0].content
            return ChatResult(output_text="第二章开始时，海雾先替她读完了那封信。")

    service = build_service(tmp_path)
    app.dependency_overrides[get_creative_writing_service] = lambda: service
    app.dependency_overrides[get_optional_chat_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    project = client.post(
        "/creative-writing/projects",
        json={"title": "潮汐信箱", "premise": "海边有一只只在退潮时出现的信箱。"},
    ).json()["project"]
    client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"content": "她把第一封信压在掌心。", "summary": "她发现未来的信。"},
    )
    client.post(
        f"/creative-writing/projects/{project['id']}/chapters/advance",
        json={"title": "退潮", "summary": "她发现信来自三年后的自己。"},
    )
    response = client.post(
        f"/creative-writing/projects/{project['id']}/fragments",
        json={"intention": "写第二章开头。"},
    )

    assert response.status_code == 200
    assert "第 1 章：退潮：她发现信来自三年后的自己。" in captured["prompt"]
    assert "她把第一封信压在掌心。" not in captured["prompt"]
    assert response.json()["fragment"]["chapter_index"] == 2
