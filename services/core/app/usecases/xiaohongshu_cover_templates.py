from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XiaohongshuCoverTemplate:
    name: str
    decoration_mode: str
    decoration_variants: int
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
    # Title-length adaptive scaling (multipliers applied to font / card / spacing)
    title_short_scale: float
    title_long_scale: float


_TEMPLATES = {
    "warm_story": XiaohongshuCoverTemplate(
        name="warm_story",
        decoration_mode="warm_story",
        decoration_variants=3,
        bg_top=(255, 248, 242),
        bg_bottom=(253, 224, 210),
        card_fill=(255, 254, 250),
        card_outline=None,
        accent=(244, 108, 78),
        accent_soft=(254, 232, 224),
        title_color=(32, 28, 26),
        subtitle_color=(108, 88, 80),
        badge_fill=(244, 108, 78),
        badge_text=(255, 255, 255),
        footer_color=(120, 100, 90),
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
        title_short_scale=1.18,
        title_long_scale=0.82,
    ),
    "expert_clean": XiaohongshuCoverTemplate(
        name="expert_clean",
        decoration_mode="expert_clean",
        decoration_variants=3,
        bg_top=(248, 247, 243),
        bg_bottom=(230, 227, 219),
        card_fill=(255, 255, 253),
        card_outline=(222, 218, 209),
        accent=(54, 82, 108),
        accent_soft=(220, 228, 236),
        title_color=(24, 30, 36),
        subtitle_color=(88, 94, 100),
        badge_fill=(54, 82, 108),
        badge_text=(255, 255, 255),
        footer_color=(100, 104, 110),
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
        title_short_scale=1.16,
        title_long_scale=0.84,
    ),
    "bold_hook": XiaohongshuCoverTemplate(
        name="bold_hook",
        decoration_mode="bold_hook",
        decoration_variants=3,
        bg_top=(255, 243, 225),
        bg_bottom=(255, 210, 190),
        card_fill=(255, 250, 244),
        card_outline=None,
        accent=(232, 78, 42),
        accent_soft=(255, 227, 208),
        title_color=(36, 26, 22),
        subtitle_color=(112, 74, 62),
        badge_fill=(36, 26, 22),
        badge_text=(255, 246, 240),
        footer_color=(120, 80, 68),
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
        title_short_scale=1.2,
        title_long_scale=0.8,
    ),
    "minimal_clean": XiaohongshuCoverTemplate(
        name="minimal_clean",
        decoration_mode="minimal_clean",
        decoration_variants=3,
        bg_top=(250, 250, 248),
        bg_bottom=(242, 241, 238),
        card_fill=(255, 255, 255),
        card_outline=(228, 227, 224),
        accent=(140, 136, 128),
        accent_soft=(235, 233, 228),
        title_color=(32, 30, 28),
        subtitle_color=(120, 116, 110),
        badge_fill=(32, 30, 28),
        badge_text=(255, 255, 255),
        footer_color=(140, 134, 128),
        card_rect=(88, 260, 1154, 1440),
        card_radius=36,
        badge_origin=(120, 120),
        badge_height=72,
        badge_padding_x=22,
        badge_font_size=30,
        title_x=140,
        title_anchor_y=500,
        title_font_size=88,
        title_line_height=116,
        title_max_width=870,
        title_max_lines=3,
        subtitle_x=144,
        subtitle_gap=104,
        subtitle_font_size=38,
        subtitle_line_height=54,
        subtitle_max_width=820,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=26,
        footer_x=144,
        footer_y=1394,
        footer_font_size=28,
        footer_text="",
        title_short_scale=1.22,
        title_long_scale=0.84,
    ),
    "playful_pop": XiaohongshuCoverTemplate(
        name="playful_pop",
        decoration_mode="playful_pop",
        decoration_variants=3,
        bg_top=(255, 250, 240),
        bg_bottom=(255, 225, 200),
        card_fill=(255, 253, 248),
        card_outline=None,
        accent=(255, 140, 60),
        accent_soft=(254, 235, 210),
        title_color=(44, 32, 24),
        subtitle_color=(130, 90, 70),
        badge_fill=(255, 140, 60),
        badge_text=(255, 255, 255),
        footer_color=(140, 100, 80),
        card_rect=(60, 210, 1182, 1450),
        card_radius=56,
        badge_origin=(94, 104),
        badge_height=80,
        badge_padding_x=22,
        badge_font_size=32,
        title_x=108,
        title_anchor_y=490,
        title_font_size=108,
        title_line_height=136,
        title_max_width=935,
        title_max_lines=3,
        subtitle_x=114,
        subtitle_gap=84,
        subtitle_font_size=42,
        subtitle_line_height=60,
        subtitle_max_width=865,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=24,
        footer_x=114,
        footer_y=1398,
        footer_font_size=30,
        footer_text="",
        title_short_scale=1.18,
        title_long_scale=0.82,
    ),
    "dark_moody": XiaohongshuCoverTemplate(
        name="dark_moody",
        decoration_mode="dark_moody",
        decoration_variants=3,
        bg_top=(22, 24, 36),
        bg_bottom=(18, 16, 28),
        card_fill=(32, 34, 46),
        card_outline=(50, 52, 64),
        accent=(212, 175, 110),
        accent_soft=(60, 56, 72),
        title_color=(238, 234, 224),
        subtitle_color=(170, 164, 150),
        badge_fill=(212, 175, 110),
        badge_text=(24, 22, 18),
        footer_color=(130, 126, 118),
        card_rect=(80, 240, 1162, 1430),
        card_radius=50,
        badge_origin=(112, 114),
        badge_height=78,
        badge_padding_x=22,
        badge_font_size=32,
        title_x=130,
        title_anchor_y=480,
        title_font_size=100,
        title_line_height=128,
        title_max_width=900,
        title_max_lines=3,
        subtitle_x=134,
        subtitle_gap=90,
        subtitle_font_size=42,
        subtitle_line_height=60,
        subtitle_max_width=846,
        subtitle_max_lines=2,
        hide_subtitle_after_chars=26,
        footer_x=134,
        footer_y=1382,
        footer_font_size=30,
        footer_text="",
        title_short_scale=1.16,
        title_long_scale=0.84,
    ),
}


def list_xiaohongshu_cover_templates() -> list[str]:
    return list(_TEMPLATES.keys())


def get_xiaohongshu_cover_template(name: str) -> XiaohongshuCoverTemplate:
    template = _TEMPLATES.get(name)
    if template is None:
        raise ValueError(f"unknown xiaohongshu cover template: {name}")
    return template
