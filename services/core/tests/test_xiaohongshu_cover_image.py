from pathlib import Path

import pytest

from app.usecases import xiaohongshu_cover_image as cover_image


def test_generate_xiaohongshu_cover_image_writes_png(tmp_path):
    result = cover_image.generate_xiaohongshu_cover_image(
        title="巧克力礼盒开箱体验，真的太惊艳了！",
        body="开箱第一眼就被惊艳到了，包装非常精致，内容也很用心。\n\n第二句不用上封面。",
        output_dir=str(tmp_path),
    )

    assert result.badge == "小晏数字人全自动运营"
    assert result.subtitle == "开箱第一眼就被惊艳到了，包装非常精致，内容也很用心"
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
