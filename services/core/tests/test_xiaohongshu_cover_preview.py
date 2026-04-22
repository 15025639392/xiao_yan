from app.usecases.xiaohongshu_cover_preview import preview_xiaohongshu_cover_image


def test_preview_xiaohongshu_cover_image_returns_data_url():
    result = preview_xiaohongshu_cover_image(
        title="测试封面",
        body="第一段正文。\n\n第二段正文。",
        template_name="expert_clean",
    )

    assert result.template_name == "expert_clean"
    assert "expert_clean" in result.available_templates
    assert result.image_path.endswith(".png")
    assert result.image_data_url.startswith("data:image/png;base64,")
