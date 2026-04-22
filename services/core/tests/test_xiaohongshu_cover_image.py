from pathlib import Path

import pytest

from app.usecases import xiaohongshu_cover_image as cover_image
from app.usecases.xiaohongshu_cover_layout import (
    choose_xiaohongshu_cover_template_name,
    resolve_xiaohongshu_cover_layout,
)
from app.usecases.xiaohongshu_cover_templates import list_xiaohongshu_cover_templates
from app.usecases.xiaohongshu_cover_templates import get_xiaohongshu_cover_template


def test_generate_xiaohongshu_cover_image_writes_png(tmp_path):
    result = cover_image.generate_xiaohongshu_cover_image(
        title="巧克力礼盒开箱体验，真的太惊艳了！",
        body="开箱第一眼就被惊艳到了，包装非常精致，内容也很用心。\n\n第二句不用上封面。",
        output_dir=str(tmp_path),
    )

    assert result.badge == "小晏数字人全自动运营"
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
