from app.usecases.xiaohongshu_generate_publish_draft import parse_xiaohongshu_publish_draft


def test_parse_xiaohongshu_publish_draft_collapses_body_into_three_part_structure():
    draft = parse_xiaohongshu_publish_draft(
        output_text=(
            "【标题】\n"
            "你不是不难过\n"
            "【开头】\n"
            "你回消息的时候总说没事。\n"
            "其实心里已经很累了。\n"
            "【正文】\n"
            "- 你不是不委屈，你只是太习惯先安顿别人。\n"
            "- 等你终于停下来，那些情绪才会一起上来。\n"
            "【结尾】\n"
            "先别急着怪自己慢半拍。\n"
            "【首评】\n"
            "如果你愿意，小晏可以继续陪你慢慢看这件事。\n"
        ),
        source_title="#情绪总是晚到一步",
    )

    assert draft.opening == "你回消息的时候总说没事。\n\n其实心里已经很累了。"
    assert draft.body_sections == [
        "你不是不委屈，你只是太习惯先安顿别人。\n\n等你终于停下来，那些情绪才会一起上来。"
    ]
    assert draft.closing_cta == "先别急着怪自己慢半拍。"
