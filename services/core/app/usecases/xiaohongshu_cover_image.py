from __future__ import annotations

import os
import random
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.usecases.xiaohongshu_cover_layout import resolve_xiaohongshu_cover_layout
from app.usecases.xiaohongshu_cover_templates import XiaohongshuCoverTemplate

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # type: ignore


_CANVAS_WIDTH = 1242
_CANVAS_HEIGHT = 1660
_DEFAULT_BADGE = ""
_DEFAULT_SUBTITLE = "先发一条能接住咨询的内容。"
_OUTPUT_DIR = Path.home() / ".xiao_yan" / "xhs-covers"
_CHINESE_FONTS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


class XiaohongshuCoverImageError(Exception):
    """Base error for cover image generation."""


class XiaohongshuCoverImageUnavailableError(XiaohongshuCoverImageError):
    """Raised when cover generation is unavailable (PIL not installed)."""


class XiaohongshuCoverImageGenerationError(XiaohongshuCoverImageError):
    """Raised when cover image rendering fails."""


@dataclass(frozen=True)
class GeneratedXiaohongshuCoverImage:
    path: str
    title: str
    subtitle: str
    badge: str
    template_name: str


def _load_font(size: float) -> ImageFont.FreeTypeFont:
    for path in _CHINESE_FONTS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, int(size))
            except Exception:
                continue
    return ImageFont.load_default()


def _gradient_rect(draw: ImageDraw.Draw, x0: int, y0: int, x1: int, y1: int, color_top, color_bot) -> None:
    steps = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / steps
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(x0, y), (x1 - 1, y)], fill=(r, g, b))


def _rounded_rect(draw: ImageDraw.Draw, xy: tuple[int, int, int, int], radius: int, fill, outline=None) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=2 if outline else 0)


def _wrap_text(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        test = current + char
        if draw.textlength(test, font=font) <= max_width:
            current = test
            continue
        if current:
            lines.append(current)
            current = char
        else:
            lines.append(char)
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if lines and draw.textlength(lines[-1] + "…", font=font) > max_width:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip(" ，、。；")
        if lines[-1]:
            lines[-1] += "…"
    return lines


def _draw_card_shadow(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate) -> None:
    x0, y0, x1, y1 = template.card_rect
    cr, cg, cb = template.card_fill
    shadow_layers = [
        (6, 8, 0.82),
        (4, 5, 0.88),
        (2, 3, 0.94),
    ]
    for dx, dy, blend in shadow_layers:
        r = int(cr * blend)
        g = int(cg * blend)
        b = int(cb * blend)
        _rounded_rect(draw, (x0 + dx, y0 + dy, x1 + dx, y1 + dy), template.card_radius, (r, g, b))


# ── Decoration variant drawing ──────────────────────────────────────────────


def _draw_decorations(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    _DISPATCH = {
        "warm_story": _draw_warm_story,
        "expert_clean": _draw_expert_clean,
        "bold_hook": _draw_bold_hook,
        "minimal_clean": _draw_minimal_clean,
        "playful_pop": _draw_playful_pop,
        "dark_moody": _draw_dark_moody,
    }
    draw_fn = _DISPATCH.get(template.decoration_mode)
    if draw_fn is None:
        return
    draw_fn(draw, template, variant % template.decoration_variants)


def _draw_warm_story(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        _rounded_rect(draw, (74, 76, 434, 224), 52, template.accent_soft)
        draw.ellipse([884, 118, 1104, 338], fill=(255, 255, 255, 160))
        _rounded_rect(draw, (920, 1010, 1112, 1202), 54, template.accent_soft)
        draw.ellipse([900, 372, 1196, 668], fill=template.accent_soft)
        draw.ellipse([980, 430, 1110, 560], fill=template.accent)
    elif variant == 1:
        # Scattered small circles — firefly / dot constellation
        circles = [
            (104, 140, 26), (280, 90, 18), (180, 180, 22),
            (960, 160, 24), (1050, 260, 16), (100, 1050, 22),
            (220, 1120, 18), (960, 1060, 20), (1080, 1180, 16),
            (60, 960, 20), (140, 1200, 14),
        ]
        for cx, cy, r in circles:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=template.accent_soft)
        # Two accent circles
        draw.ellipse([900, 400, 1100, 600], fill=template.accent_soft)
        draw.ellipse([960, 440, 1050, 530], fill=template.accent)
    else:
        # Organic blobs — fewer, larger shapes
        draw.ellipse([40, 50, 500, 350], fill=template.accent_soft)
        draw.ellipse([860, 80, 1160, 380], fill=(255, 255, 255, 140))
        draw.ellipse([880, 360, 1200, 700], fill=template.accent_soft)
        draw.ellipse([960, 420, 1120, 580], fill=template.accent)
        _rounded_rect(draw, (70, 1000, 300, 1230), 60, template.accent_soft)


def _draw_expert_clean(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        draw.line([(94, 146), (1148, 146)], fill=template.accent_soft, width=4)
        draw.line([(1120, 146), (1120, 300)], fill=template.accent, width=10)
        draw.line([(122, 380), (122, 1260)], fill=template.accent_soft, width=14)
        _rounded_rect(draw, (964, 1094, 1112, 1236), 34, template.accent_soft)
        draw.line([(122, 440), (122, 520)], fill=template.accent, width=5)
    elif variant == 1:
        # Dual parallel lines + corner accents
        draw.line([(94, 140), (1148, 140)], fill=template.accent_soft, width=3)
        draw.line([(94, 152), (1148, 152)], fill=template.accent_soft, width=3)
        # Corner L-shapes
        draw.line([(94, 140), (94, 290)], fill=template.accent, width=8)
        draw.line([(94, 290), (240, 290)], fill=template.accent, width=8)
        draw.line([(1148, 140), (1148, 290)], fill=template.accent_soft, width=8)
        draw.line([(1002, 290), (1148, 290)], fill=template.accent_soft, width=8)
        # Thin vertical accent
        draw.line([(122, 360), (122, 1280)], fill=template.accent_soft, width=8)
    else:
        # Modular grid blocks
        rects = [(104, 130, 280, 170), (320, 130, 440, 170), (480, 130, 620, 170),
                 (104, 190, 220, 230), (240, 190, 380, 230)]
        for rx0, ry0, rx1, ry1 in rects:
            _rounded_rect(draw, (rx0, ry0, rx1, ry1), 6, template.accent_soft)
        draw.line([(1120, 130), (1120, 300)], fill=template.accent, width=10)
        draw.line([(122, 360), (122, 1280)], fill=template.accent_soft, width=8)
        _rounded_rect(draw, (990, 1080, 1128, 1240), 28, template.accent_soft)


def _draw_bold_hook(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        draw.polygon([(0, 0), (410, 0), (220, 320), (0, 240)], fill=template.accent_soft)
        draw.polygon([(942, 0), (_CANVAS_WIDTH, 0), (_CANVAS_WIDTH, 420), (1038, 300)], fill=template.accent)
        draw.polygon([(1038, 300), (_CANVAS_WIDTH, 420), (1100, 280)], fill=template.accent_soft)
        draw.rounded_rectangle([86, 1240, 1158, 1296], radius=28, fill=template.accent_soft)
        draw.rounded_rectangle([86, 1308, 690, 1336], radius=14, fill=template.accent)
    elif variant == 1:
        # Starburst — more aggressive polygons
        draw.polygon([(0, 0), (480, 0), (280, 360), (0, 280)], fill=template.accent_soft)
        draw.polygon([(260, 0), (620, 0), (380, 300), (200, 260)], fill=template.accent)
        draw.polygon([(900, 0), (_CANVAS_WIDTH, 0), (_CANVAS_WIDTH, 480), (1000, 320)], fill=template.accent)
        draw.polygon([(1000, 320), (_CANVAS_WIDTH, 480), (1120, 260)], fill=template.accent_soft)
        draw.rounded_rectangle([76, 1220, 1168, 1270], radius=24, fill=template.accent_soft)
        draw.rounded_rectangle([76, 1290, 700, 1330], radius=14, fill=template.accent)
        draw.rounded_rectangle([76, 1344, 400, 1368], radius=12, fill=template.accent_soft)
    else:
        # Bold horizontal strips
        draw.rectangle([(0, 60), (_CANVAS_WIDTH, 140)], fill=template.accent_soft)
        draw.rectangle([(0, 150), (_CANVAS_WIDTH, 175)], fill=template.accent)
        draw.rectangle([(0, 185), (800, 205)], fill=template.accent_soft)
        draw.polygon([(920, 0), (_CANVAS_WIDTH, 0), (_CANVAS_WIDTH, 440), (1000, 320)], fill=template.accent)
        draw.polygon([(1000, 320), (_CANVAS_WIDTH, 440), (1100, 290)], fill=template.accent_soft)
        draw.rounded_rectangle([80, 1220, 1162, 1270], radius=24, fill=template.accent_soft)
        draw.rounded_rectangle([80, 1290, 700, 1324], radius=14, fill=template.accent)


def _draw_minimal_clean(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        # Single thin line with a small accent dot
        draw.line([(94, 120), (1148, 120)], fill=template.accent_soft, width=1)
        draw.ellipse([1128, 116, 1144, 132], fill=template.accent)
        draw.line([(122, 350), (122, 400)], fill=template.accent, width=2)
    elif variant == 1:
        # Two subtle dots and a thin framing line
        draw.ellipse([126, 390, 140, 404], fill=template.accent)
        draw.ellipse([126, 430, 138, 442], fill=template.accent_soft)
        draw.line([(94, 110), (1148, 110)], fill=template.accent_soft, width=1)
        draw.line([(1140, 110), (1140, 180)], fill=template.accent_soft, width=1)
    else:
        # Minimal corner bracket + small circle
        draw.line([(90, 310), (90, 380)], fill=template.accent, width=2)
        draw.line([(90, 310), (160, 310)], fill=template.accent, width=2)
        draw.ellipse([1100, 1060, 1140, 1100], fill=template.accent_soft)
        draw.line([(88, 106), (1154, 106)], fill=template.accent_soft, width=1)


def _draw_playful_pop(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        # Overlapping colorful circles
        draw.ellipse([60, 60, 280, 280], fill=template.accent_soft)
        draw.ellipse([180, 120, 340, 280], fill=template.accent)
        draw.ellipse([960, 80, 1180, 300], fill=template.accent_soft)
        draw.ellipse([1020, 140, 1140, 260], fill=template.accent)
        _rounded_rect(draw, (80, 1050, 260, 1220), 40, template.accent_soft)
    elif variant == 1:
        # Scattered squircle shapes
        squiggles = [(80, 70, 50), (280, 110, 38), (160, 180, 44),
                     (980, 100, 46), (1080, 220, 36), (60, 1080, 42)]
        for cx, cy, s in squiggles:
            _rounded_rect(draw, (cx, cy, cx + s, cy + s), s // 2, template.accent_soft)
        draw.ellipse([900, 400, 1140, 640], fill=template.accent_soft)
        draw.ellipse([960, 460, 1090, 590], fill=template.accent)
    else:
        # Wavy dots + large playful circle
        for ix in range(5):
            x = 80 + ix * 50
            y = 110 + (20 if ix % 2 == 0 else -10)
            draw.ellipse([x, y, x + 20, y + 20], fill=template.accent_soft if ix % 3 == 0 else template.accent)
        draw.ellipse([920, 50, 1200, 330], fill=template.accent_soft)
        draw.ellipse([980, 120, 1130, 270], fill=template.accent)
        _rounded_rect(draw, (60, 1040, 240, 1220), 50, template.accent_soft)


def _draw_dark_moody(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, variant: int) -> None:
    if variant == 0:
        # Subtle glow orbs
        draw.ellipse([60, 40, 400, 380], fill=template.accent_soft)
        draw.ellipse([180, 120, 300, 240], fill=template.accent)
        draw.ellipse([900, 1000, 1200, 1300], fill=template.accent_soft)
        draw.ellipse([980, 1080, 1120, 1220], fill=template.accent)
    elif variant == 1:
        # Geometric line accents
        draw.line([(80, 100), (400, 100)], fill=template.accent, width=3)
        draw.line([(80, 100), (80, 340)], fill=template.accent_soft, width=3)
        draw.line([(1120, 1040), (1120, 1280)], fill=template.accent, width=3)
        draw.line([(960, 1280), (1120, 1280)], fill=template.accent_soft, width=3)
        draw.ellipse([900, 350, 1140, 590], fill=template.accent_soft)
        draw.ellipse([960, 410, 1090, 540], fill=template.accent)
    else:
        # Scattered rects + large subtle orb
        _rounded_rect(draw, (80, 80, 180, 160), 20, template.accent_soft)
        _rounded_rect(draw, (200, 100, 260, 140), 12, template.accent)
        draw.ellipse([860, 40, 1200, 380], fill=template.accent_soft)
        draw.ellipse([940, 120, 1120, 300], fill=template.accent)
        draw.ellipse([80, 1040, 400, 1280], fill=template.accent_soft)


# ── Adaptive layout helpers ────────────────────────────────────────────────


def _scale_param(value: int, scale: float) -> int:
    return max(1, int(value * scale))


def _apply_title_size_tier(
    template: XiaohongshuCoverTemplate,
    tier: str,
) -> dict:
    """Return layout overrides for the given title size tier."""
    if tier == "short":
        s = template.title_short_scale
        title_font = _scale_param(template.title_font_size, s)
        title_lh = _scale_param(template.title_line_height, s)
        card_x0, card_y0, card_x1, card_y1 = template.card_rect
        # Make card shorter vertically (title+subtitle area is compact)
        card_h = card_y1 - card_y0
        new_card_h = _scale_param(card_h, 0.88)
        return {
            "title_font_size": title_font,
            "title_line_height": title_lh,
            "title_anchor_y": _scale_param(template.title_anchor_y, 0.96),
            "subtitle_font_size": _scale_param(template.subtitle_font_size, s),
            "subtitle_line_height": _scale_param(template.subtitle_line_height, s),
            "subtitle_gap": _scale_param(template.subtitle_gap, 1.12),
            "card_rect": (card_x0, card_y0, card_x1, card_y0 + new_card_h),
        }
    elif tier == "long":
        s = template.title_long_scale
        title_font = _scale_param(template.title_font_size, s)
        title_lh = _scale_param(template.title_line_height, s)
        card_x0, card_y0, card_x1, card_y1 = template.card_rect
        return {
            "title_font_size": title_font,
            "title_line_height": title_lh,
            "title_anchor_y": template.title_anchor_y,
            "subtitle_font_size": _scale_param(template.subtitle_font_size, s),
            "subtitle_line_height": _scale_param(template.subtitle_line_height, s),
            "subtitle_gap": _scale_param(template.subtitle_gap, 0.82),
            "card_rect": template.card_rect,
        }
    else:
        # medium — use defaults
        return {
            "title_font_size": template.title_font_size,
            "title_line_height": template.title_line_height,
            "title_anchor_y": template.title_anchor_y,
            "subtitle_font_size": template.subtitle_font_size,
            "subtitle_line_height": template.subtitle_line_height,
            "subtitle_gap": template.subtitle_gap,
            "card_rect": template.card_rect,
        }


# ── Main generation ─────────────────────────────────────────────────────────


def _draw_badge(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate, badge: str) -> None:
    badge_font = _load_font(template.badge_font_size)
    badge_x0, badge_y0 = template.badge_origin
    badge_width = int(draw.textlength(badge, font=badge_font)) + template.badge_padding_x * 2
    _rounded_rect(
        draw,
        (badge_x0, badge_y0, badge_x0 + badge_width, badge_y0 + template.badge_height),
        template.badge_height // 2,
        template.badge_fill,
    )
    draw.text(
        (badge_x0 + template.badge_padding_x, badge_y0 + (template.badge_height - template.badge_font_size) // 2 - 2),
        badge,
        font=badge_font,
        fill=template.badge_text,
    )


def generate_xiaohongshu_cover_image(
    *,
    title: str,
    body: str,
    badge: str = _DEFAULT_BADGE,
    output_dir: str | None = None,
    template_name: str | None = None,
) -> GeneratedXiaohongshuCoverImage:
    if Image is None:
        raise XiaohongshuCoverImageUnavailableError("PIL is not installed. Install with: pip install Pillow")

    normalized_title = title.strip()
    normalized_badge = badge.strip() or _DEFAULT_BADGE
    if not normalized_title:
        raise ValueError("cover title cannot be blank")

    layout = resolve_xiaohongshu_cover_layout(
        title=normalized_title,
        body=body.strip(),
        default_subtitle=_DEFAULT_SUBTITLE,
        template_name=template_name,
    )
    layout_overrides = _apply_title_size_tier(layout.template, layout.title_size_tier)
    decoration_variant = random.randint(0, layout.template.decoration_variants - 1)

    target_dir = Path(output_dir.strip()) if output_dir and output_dir.strip() else _OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"xhs-cover-{uuid.uuid4().hex[:12]}.png"

    try:
        img = Image.new("RGB", (_CANVAS_WIDTH, _CANVAS_HEIGHT), layout.template.bg_top)
        draw = ImageDraw.Draw(img)
        _gradient_rect(draw, 0, 0, _CANVAS_WIDTH, _CANVAS_HEIGHT, layout.template.bg_top, layout.template.bg_bottom)
        _draw_decorations(draw, layout.template, decoration_variant)
        _draw_card_shadow(draw, layout.template)
        _rounded_rect(
            draw,
            layout_overrides["card_rect"],
            layout.template.card_radius,
            layout.template.card_fill,
            outline=layout.template.card_outline,
        )
        if normalized_badge:
            _draw_badge(draw, layout.template, normalized_badge)

        title_font = _load_font(layout_overrides["title_font_size"])
        title_lines = _wrap_text(
            draw,
            normalized_title,
            title_font,
            layout.template.title_max_width,
            layout.template.title_max_lines,
        )
        title_height = max(1, len(title_lines)) * layout_overrides["title_line_height"]
        title_y = layout_overrides["title_anchor_y"] - title_height // 2
        for index, line in enumerate(title_lines):
            draw.text(
                (layout.template.title_x, title_y + index * layout_overrides["title_line_height"]),
                line,
                font=title_font,
                fill=layout.template.title_color,
            )

        if layout.show_subtitle:
            subtitle_font = _load_font(layout_overrides["subtitle_font_size"])
            subtitle_lines = _wrap_text(
                draw,
                layout.subtitle,
                subtitle_font,
                layout.template.subtitle_max_width,
                layout.template.subtitle_max_lines,
            )
            subtitle_y = title_y + title_height + layout_overrides["subtitle_gap"]
            for index, line in enumerate(subtitle_lines):
                draw.text(
                    (layout.template.subtitle_x, subtitle_y + index * layout_overrides["subtitle_line_height"]),
                    line,
                    font=subtitle_font,
                    fill=layout.template.subtitle_color,
                )

        if layout.template.footer_text.strip():
            footer_font = _load_font(layout.template.footer_font_size)
            draw.text(
                (layout.template.footer_x, layout.template.footer_y),
                layout.template.footer_text,
                font=footer_font,
                fill=layout.template.footer_color,
            )

        img.save(output_path, "PNG")
        return GeneratedXiaohongshuCoverImage(
            path=str(output_path),
            title=normalized_title,
            subtitle=layout.subtitle,
            badge=normalized_badge,
            template_name=layout.template.name,
        )
    except XiaohongshuCoverImageUnavailableError:
        raise
    except Exception as exc:
        raise XiaohongshuCoverImageGenerationError(f"生成封面图失败：{exc}") from exc
