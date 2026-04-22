from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XiaohongshuCoverTemplate:
    name: str
    decoration_mode: str
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    card_fill: tuple[int, int, int]
    card_outline: tuple[int, int, int] | None
    accent: tuple[int, int, int]
    accent_soft: tuple[int, int, int]
    title_color: tuple[int, int, int]
    subtitle_color: tuple[int, int, int]
    badge_fill: tuple[int, int, int]
    badge_text: tuple[int, int, int]
    footer_color: tuple[int, int, int]
    card_rect: tuple[int, int, int, int]
    card_radius: int
    badge_origin: tuple[int, int]
    badge_height: int
    badge_padding_x: int
    badge_font_size: int
    title_x: int
    title_anchor_y: int
    title_font_size: int
    title_line_height: int
    title_max_width: int
    title_max_lines: int
    subtitle_x: int
    subtitle_gap: int
    subtitle_font_size: int
    subtitle_line_height: int
    subtitle_max_width: int
    subtitle_max_lines: int
    hide_subtitle_after_chars: int
    footer_x: int
    footer_y: int
    footer_font_size: int
    footer_text: str


_TEMPLATES = {
    "warm_story": XiaohongshuCoverTemplate(
        name="warm_story",
        decoration_mode="warm_story",
        bg_top=(255, 249, 244),
        bg_bottom=(255, 212, 197),
        card_fill=(255, 253, 249),
        card_outline=None,
        accent=(255, 106, 77),
        accent_soft=(255, 230, 222),
        title_color=(28, 27, 26),
        subtitle_color=(89, 76, 72),
        badge_fill=(255, 106, 77),
        badge_text=(255, 255, 255),
        footer_color=(89, 76, 72),
        card_rect=(72, 248, 1170, 1428),
        card_radius=64,
        badge_origin=(102, 112),
        badge_height=86,
        badge_padding_x=20,
        badge_font_size=34,
        title_x=118,
        title_anchor_y=470,
        title_font_size=104,
        title_line_height=132,
        title_max_width=910,
        title_max_lines=3,
        subtitle_x=122,
        subtitle_gap=96,
        subtitle_font_size=44,
        subtitle_line_height=64,
        subtitle_max_width=860,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=28,
        footer_x=122,
        footer_y=1378,
        footer_font_size=34,
        footer_text="",
    ),
    "expert_clean": XiaohongshuCoverTemplate(
        name="expert_clean",
        decoration_mode="expert_clean",
        bg_top=(249, 247, 241),
        bg_bottom=(233, 229, 221),
        card_fill=(255, 255, 252),
        card_outline=(219, 215, 206),
        accent=(58, 88, 116),
        accent_soft=(218, 226, 233),
        title_color=(25, 31, 38),
        subtitle_color=(83, 91, 99),
        badge_fill=(58, 88, 116),
        badge_text=(255, 255, 255),
        footer_color=(83, 91, 99),
        card_rect=(84, 232, 1158, 1440),
        card_radius=48,
        badge_origin=(104, 110),
        badge_height=78,
        badge_padding_x=24,
        badge_font_size=30,
        title_x=136,
        title_anchor_y=474,
        title_font_size=96,
        title_line_height=122,
        title_max_width=884,
        title_max_lines=3,
        subtitle_x=140,
        subtitle_gap=88,
        subtitle_font_size=40,
        subtitle_line_height=58,
        subtitle_max_width=816,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=26,
        footer_x=140,
        footer_y=1386,
        footer_font_size=30,
        footer_text="",
    ),
    "bold_hook": XiaohongshuCoverTemplate(
        name="bold_hook",
        decoration_mode="bold_hook",
        bg_top=(255, 243, 214),
        bg_bottom=(255, 214, 197),
        card_fill=(255, 249, 242),
        card_outline=None,
        accent=(230, 86, 45),
        accent_soft=(255, 225, 204),
        title_color=(34, 24, 22),
        subtitle_color=(101, 68, 58),
        badge_fill=(34, 24, 22),
        badge_text=(255, 245, 238),
        footer_color=(101, 68, 58),
        card_rect=(60, 220, 1182, 1444),
        card_radius=52,
        badge_origin=(96, 108),
        badge_height=82,
        badge_padding_x=22,
        badge_font_size=32,
        title_x=110,
        title_anchor_y=500,
        title_font_size=112,
        title_line_height=140,
        title_max_width=930,
        title_max_lines=3,
        subtitle_x=116,
        subtitle_gap=78,
        subtitle_font_size=42,
        subtitle_line_height=60,
        subtitle_max_width=870,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=24,
        footer_x=116,
        footer_y=1392,
        footer_font_size=30,
        footer_text="",
    ),
}


def list_xiaohongshu_cover_templates() -> list[str]:
    return list(_TEMPLATES.keys())


def get_xiaohongshu_cover_template(name: str) -> XiaohongshuCoverTemplate:
    template = _TEMPLATES.get(name)
    if template is None:
        raise ValueError(f"unknown xiaohongshu cover template: {name}")
    return template
