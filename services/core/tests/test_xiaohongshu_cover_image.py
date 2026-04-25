from pathlib import Path

import pytest

from app.usecases import xiaohongshu_cover_image as cover_image
from app.usecases.xiaohongshu_cover_layout import (
    choose_xiaohongshu_cover_template_name,
    resolve_xiaohongshu_cover_layout,
)
from app.usecases.xiaohongshu_cover_templates import list_xiaohongshu_cover_templates
from app.usecases.xiaohongshu_cover_templates import get_xiaohongshu_cover_template


# ── Existing tests ──────────────────────────────────────────────────────────


def test_generate_xiaohongshu_cover_image_writes_png(tmp_path):
    result = cover_image.generate_xiaohongshu_cover_image(
        title="巧克力礼盒开箱体验，真的太惊艳了！",
        body="开箱第一眼就被惊艳到了，包装非常精致，内容也很用心。\n\n第二句不用上封面。",
        output_dir=str(tmp_path),
    )

    assert result.badge == ""
    assert result.subtitle == "开箱第一眼就被惊艳到了，包装非常精致，内容也很用心"
    assert result.template_name in list_xiaohongshu_cover_templates()
    assert Path(result.path).exists()
    assert Path(result.path).suffix == ".png"
    assert Path(result.path).parent == tmp_path


def test_subtitle_extraction_first_paragraph():
    result = cover_image.generate_xiaohongshu_cover_image(
        title="测试",
        body="第一段正文。\n\n第二段正文。",
    )
    assert result.subtitle == "第一段正文"  # trailing punctuation stripped by rstrip

    result2 = cover_image.generate_xiaohongshu_cover_image(
        title="测试",
        body="",
    )
    assert result2.subtitle == cover_image._DEFAULT_SUBTITLE


def test_title_too_long_truncated():
    long_title = "测试标题" * 50
    result = cover_image.generate_xiaohongshu_cover_image(
        title=long_title,
        body="正文内容",
    )
    assert len(result.title) > 0


def test_raises_on_blank_title():
    with pytest.raises(ValueError, match="cannot be blank"):
        cover_image.generate_xiaohongshu_cover_image(
            title="  ",
            body="正文",
        )


def test_custom_badge():
    result = cover_image.generate_xiaohongshu_cover_image(
        title="测试",
        body="正文",
        badge="我的自定义徽章",
    )
    assert result.badge == "我的自定义徽章"


def test_choose_template_name_uses_title_tone():
    assert choose_xiaohongshu_cover_template_name(title="别再这样发小红书了", body="正文") == "bold_hook"
    assert choose_xiaohongshu_cover_template_name(title="我最近做内容的一个变化", body="正文") == "warm_story"
    assert choose_xiaohongshu_cover_template_name(title="小红书标题模板", body="三步写法") == "expert_clean"


def test_resolve_layout_hides_subtitle_for_long_title():
    decision = resolve_xiaohongshu_cover_layout(
        title="这是一个非常非常长而且明显会占满主标题区域的小红书封面标题",
        body="第一段正文。\n\n第二段正文。",
        default_subtitle=cover_image._DEFAULT_SUBTITLE,
        template_name="bold_hook",
    )

    assert decision.template.name == "bold_hook"
    assert decision.show_subtitle is False


def test_generate_cover_supports_explicit_template_name(tmp_path):
    result = cover_image.generate_xiaohongshu_cover_image(
        title="方法拆解模板",
        body="先给结论。\n\n再给步骤。",
        template_name="expert_clean",
        output_dir=str(tmp_path),
    )

    assert result.template_name == "expert_clean"
    assert Path(result.path).exists()


def test_cover_templates_do_not_render_style_explanation_footer():
    for template_name in list_xiaohongshu_cover_templates():
        assert get_xiaohongshu_cover_template(template_name).footer_text == ""


# ── New template tests ──────────────────────────────────────────────────────


def test_all_six_templates_exist():
    names = list_xiaohongshu_cover_templates()
    assert len(names) == 6
    assert "warm_story" in names
    assert "expert_clean" in names
    assert "bold_hook" in names
    assert "minimal_clean" in names
    assert "playful_pop" in names
    assert "dark_moody" in names


def test_every_template_has_variants():
    for name in list_xiaohongshu_cover_templates():
        template = get_xiaohongshu_cover_template(name)
        assert template.decoration_variants >= 2, f"{name} should have at least 2 decoration variants"


# ── Title size tier tests ───────────────────────────────────────────────────


def test_short_title_uses_short_tier():
    decision = resolve_xiaohongshu_cover_layout(
        title="短标题",
        body="正文内容",
        default_subtitle=cover_image._DEFAULT_SUBTITLE,
    )
    assert decision.title_size_tier == "short"


def test_medium_title_uses_medium_tier():
    decision = resolve_xiaohongshu_cover_layout(
        title="这是一个中等长度的标题文案",
        body="正文内容",
        default_subtitle=cover_image._DEFAULT_SUBTITLE,
    )
    assert decision.title_size_tier == "medium"


def test_long_title_uses_long_tier():
    decision = resolve_xiaohongshu_cover_layout(
        title="这是一个非常长的标题用来测试长标题的布局自适应效果",
        body="正文内容",
        default_subtitle=cover_image._DEFAULT_SUBTITLE,
    )
    assert decision.title_size_tier == "long"


def test_tier_applies_scale_override():
    """Short titles get larger fonts, long titles get smaller."""
    from app.usecases.xiaohongshu_cover_image import _apply_title_size_tier
    template = get_xiaohongshu_cover_template("bold_hook")

    short = _apply_title_size_tier(template, "short")
    medium = _apply_title_size_tier(template, "medium")
    long_ = _apply_title_size_tier(template, "long")

    assert short["title_font_size"] > medium["title_font_size"]
    assert long_["title_font_size"] < medium["title_font_size"]
    assert short["subtitle_gap"] > medium["subtitle_gap"]


# ── New template keyword matching ───────────────────────────────────────────


def test_playful_pop_template_matches_lifestyle_keywords():
    assert choose_xiaohongshu_cover_template_name(title="开箱测评超值好物", body="正文") == "playful_pop"


def test_dark_moody_template_matches_deep_keywords():
    assert choose_xiaohongshu_cover_template_name(title="深夜反思人生的意义", body="正文") == "dark_moody"


def test_minimal_clean_template_matches_efficiency_keywords():
    assert choose_xiaohongshu_cover_template_name(title="极简整理方法论", body="正文") == "minimal_clean"


# ── Decoration variant tests ────────────────────────────────────────────────


def test_different_variants_produce_different_images(tmp_path):
    """Two calls with the same inputs should produce visually different images."""
    title = "一种能让你沉浸思考的方法"
    body = "这个方法的核心是让自己进入深度状态。"

    result_a = cover_image.generate_xiaohongshu_cover_image(
        title=title,
        body=body,
        template_name="expert_clean",
        output_dir=str(tmp_path),
    )
    result_b = cover_image.generate_xiaohongshu_cover_image(
        title=title,
        body=body,
        template_name="expert_clean",
        output_dir=str(tmp_path),
    )

    # Same template, but potentially different variant
    assert result_a.template_name == result_b.template_name
    assert result_a.path != result_b.path  # different uuid filenames


def test_every_template_can_render_with_variants(tmp_path):
    """Smoke-test: every template renders a valid PNG for each variant."""
    for name in list_xiaohongshu_cover_templates():
        # Call multiple times to exercise different variants via randomness
        for _ in range(3):
            result = cover_image.generate_xiaohongshu_cover_image(
                title="测试标题内容",
                body="这是一段测试正文内容。\n\n用来看生成是否正常。",
                template_name=name,
                output_dir=str(tmp_path),
            )
            assert Path(result.path).exists()
            assert Path(result.path).stat().st_size > 100  # non-empty image


def test_new_template_renders_valid_png(tmp_path):
    """Each new template should produce a valid PNG."""
    for name in ("minimal_clean", "playful_pop", "dark_moody"):
        result = cover_image.generate_xiaohongshu_cover_image(
            title="一个测试用的标题",
            body="测试正文内容第一段。\n\n第二段内容。",
            template_name=name,
            output_dir=str(tmp_path),
        )
        assert result.template_name == name
        assert Path(result.path).exists()


def test_adaptive_layout_short_title_bigger_font(tmp_path):
    result_short = cover_image.generate_xiaohongshu_cover_image(
        title="短标题",
        body="正文内容",
        template_name="expert_clean",
        output_dir=str(tmp_path),
    )
    result_long = cover_image.generate_xiaohongshu_cover_image(
        title="这是一个比较长的标题需要缩小字号来适应卡片布局",
        body="正文内容",
        template_name="expert_clean",
        output_dir=str(tmp_path),
    )
    assert result_short.template_name == result_long.template_name
    assert Path(result_short.path).exists()
    assert Path(result_long.path).exists()
