from __future__ import annotations

import os
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
_DEFAULT_BADGE = "小晏数字人全自动运营"
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


def _draw_decorations(draw: ImageDraw.Draw, template: XiaohongshuCoverTemplate) -> None:
    if template.decoration_mode == "warm_story":
        _rounded_rect(draw, (74, 76, 434, 224), 52, template.accent_soft)
        draw.ellipse([884, 118, 1104, 338], fill=(255, 255, 255))
        _rounded_rect(draw, (920, 1010, 1112, 1202), 54, template.accent_soft)
        draw.ellipse([900, 372, 1196, 668], fill=template.accent_soft)
        return
    if template.decoration_mode == "expert_clean":
        draw.line([(94, 146), (1148, 146)], fill=template.accent_soft, width=4)
        draw.line([(1120, 146), (1120, 300)], fill=template.accent, width=10)
        draw.line([(122, 380), (122, 1260)], fill=template.accent_soft, width=14)
        _rounded_rect(draw, (964, 1094, 1112, 1236), 34, template.accent_soft)
        return
    if template.decoration_mode == "bold_hook":
        draw.polygon([(0, 0), (410, 0), (220, 320), (0, 240)], fill=template.accent_soft)
        draw.polygon([(942, 0), (_CANVAS_WIDTH, 0), (_CANVAS_WIDTH, 420), (1038, 300)], fill=template.accent)
        draw.rounded_rectangle([86, 1240, 1158, 1296], radius=28, fill=template.accent_soft)
        draw.rounded_rectangle([86, 1308, 690, 1336], radius=14, fill=template.accent)


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
    target_dir = Path(output_dir.strip()) if output_dir and output_dir.strip() else _OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"xhs-cover-{uuid.uuid4().hex[:12]}.png"

    try:
        img = Image.new("RGB", (_CANVAS_WIDTH, _CANVAS_HEIGHT), layout.template.bg_top)
        draw = ImageDraw.Draw(img)
        _gradient_rect(draw, 0, 0, _CANVAS_WIDTH, _CANVAS_HEIGHT, layout.template.bg_top, layout.template.bg_bottom)
        _draw_decorations(draw, layout.template)
        _rounded_rect(
            draw,
            layout.template.card_rect,
            layout.template.card_radius,
            layout.template.card_fill,
            outline=layout.template.card_outline,
        )
        _draw_badge(draw, layout.template, normalized_badge)

        title_font = _load_font(layout.template.title_font_size)
        title_lines = _wrap_text(
            draw,
            normalized_title,
            title_font,
            layout.template.title_max_width,
            layout.template.title_max_lines,
        )
        title_height = max(1, len(title_lines)) * layout.template.title_line_height
        title_y = layout.template.title_anchor_y - title_height // 2
        for index, line in enumerate(title_lines):
            draw.text(
                (layout.template.title_x, title_y + index * layout.template.title_line_height),
                line,
                font=title_font,
                fill=layout.template.title_color,
            )

        if layout.show_subtitle:
            subtitle_font = _load_font(layout.template.subtitle_font_size)
            subtitle_lines = _wrap_text(
                draw,
                layout.subtitle,
                subtitle_font,
                layout.template.subtitle_max_width,
                layout.template.subtitle_max_lines,
            )
            subtitle_y = title_y + title_height + layout.template.subtitle_gap
            for index, line in enumerate(subtitle_lines):
                draw.text(
                    (layout.template.subtitle_x, subtitle_y + index * layout.template.subtitle_line_height),
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
