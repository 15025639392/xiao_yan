from __future__ import annotations

import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # type: ignore


_CANVAS_WIDTH = 1242
_CANVAS_HEIGHT = 1660
_DEFAULT_BADGE = "小晏数字人全自动运营"
_DEFAULT_SUBTITLE = "先发一条能接住咨询的内容。"
_OUTPUT_DIR = Path.home() / ".xiao_yan" / "xhs-covers"

# Palette — mirrors the JS canvas version
_COLOR_BG_TOP = (255, 249, 244)       # #fff9f4
_COLOR_BG_MID = (255, 233, 223)       # #ffe9df
_COLOR_BG_BOT = (255, 212, 197)       # #ffd4c5
_COLOR_CARD = (255, 253, 249, 246)    # rgba(255,253,249,0.96)
_COLOR_ACCENT = (255, 106, 77)        # #ff6a4d
_COLOR_BADGE_BG = (255, 106, 77, 30)  # rgba(255,106,77,0.12)
_COLOR_CIRCLE_BG = (255, 102, 72, 36) # rgba(255,102,72,0.14)
_COLOR_BADGE_TINT = (255, 123, 99, 28) # rgba(255,123,99,0.35)
_COLOR_TEXT_DARK = (28, 27, 26)       # #1c1b1a
_COLOR_TEXT_MUTED = (89, 76, 72)      # #594c48
_COLOR_BADGE_TEXT = (255, 255, 255)   # white

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


def _load_font(size: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the best available Chinese-compatible font at the given size."""
    candidates = _CHINESE_FONTS
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, int(size))
            except Exception:
                continue
    return ImageFont.load_default()


def _gradient_rect(draw: ImageDraw.Draw, x0: int, y0: int, x1: int, y1: int, color_top, color_bot) -> None:
    """Draw a vertical gradient rectangle."""
    steps = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / steps
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(x0, y), (x1 - 1, y)], fill=(r, g, b))


def _rounded_rect(draw: ImageDraw.Draw, xy: tuple, radius: int, fill, outline=None) -> None:
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * radius, y0 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * radius, y0, x1, y0 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * radius, x0 + 2 * radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * radius, y1 - 2 * radius, x1, y1], 0, 90, fill=fill)
    if outline is not None:
        draw.rectangle([x0 + radius, y0, x1 - radius, y0 + 1], fill=outline)
        draw.rectangle([x0 + radius, y1 - 1, x1 - radius, y1], fill=outline)
        draw.rectangle([x0, y0 + radius, x0 + 1, y1 - radius], fill=outline)
        draw.rectangle([x1 - 1, y0 + radius, x1, y1 - radius], fill=outline)


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    """Wrap text into lines that fit within max_width."""
    if not text:
        return []
    chars = list(text)
    lines = []
    current = ""
    for char in chars:
        test = current + char
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
                current = char
            else:
                lines.append(char)
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    # Truncate last line if too long
    if lines and draw.textlength(lines[-1] + "...", font=font) > max_width:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip(" ，、。；")
        if lines[-1]:
            lines[-1] += "…"
    return lines


def _derive_subtitle(body: str) -> str:
    """Extract first non-empty paragraph as subtitle."""
    if not body:
        return _DEFAULT_SUBTITLE
    import re
    segments = [s.strip() for s in re.split(r"\n\s*\n|\n", body) if s.strip()]
    candidate = segments[0] if segments else body.strip()
    normalized = re.sub(r"\s+", " ", candidate).strip(" ，、。；…")
    if not normalized:
        return _DEFAULT_SUBTITLE
    if len(normalized) <= 28:
        return normalized
    return normalized[:27].rstrip(" ，、。；") + "…"


def generate_xiaohongshu_cover_image(
    *,
    title: str,
    body: str,
    badge: str = _DEFAULT_BADGE,
    output_dir: str | None = None,
) -> GeneratedXiaohongshuCoverImage:
    """Generate a Xiaohongshu cover image locally using PIL.

    No browser dependency. Draws a peach-gradient card with title,
    subtitle, badge, and decorative elements.
    """
    if Image is None:
        raise XiaohongshuCoverImageUnavailableError(
            "PIL is not installed. Install with: pip install Pillow"
        )

    normalized_title = title.strip()
    normalized_badge = badge.strip() or _DEFAULT_BADGE
    if not normalized_title:
        raise ValueError("cover title cannot be blank")

    subtitle = _derive_subtitle(body.strip())

    target_dir = Path(output_dir.strip()) if output_dir and output_dir.strip() else _OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"xhs-cover-{uuid.uuid4().hex[:12]}.png"

    try:
        # ── Canvas ──────────────────────────────────────────────────────────
        img = Image.new("RGB", (_CANVAS_WIDTH, _CANVAS_HEIGHT), _COLOR_BG_TOP)
        draw = ImageDraw.Draw(img)

        # Gradient background
        _gradient_rect(draw, 0, 0, _CANVAS_WIDTH, _CANVAS_HEIGHT, _COLOR_BG_TOP, _COLOR_BG_BOT)

        # ── Decorative shapes ──────────────────────────────────────────────
        # Top-left blob
        _rounded_rect(draw, (74, 76, 434, 224), 52, _COLOR_BADGE_BG)
        # Top-right circle
        draw.ellipse([884, 118, 1104, 338], fill=(255, 255, 255, 88))  # semi-transparent white
        # Bottom-right blob
        _rounded_rect(draw, (920, 1010, 1112, 1202), 54, _COLOR_BADGE_BG)
        # Main card
        _rounded_rect(draw, (72, 248, 1170, 1428), 64, _COLOR_CARD)
        # Accent circle (top right, inside card area)
        draw.ellipse([900, 372, 1196, 668], fill=_COLOR_CIRCLE_BG)

        # ── Badge ───────────────────────────────────────────────────────────
        badge_font = _load_font(34, bold=True)
        badge_w = int(draw.textlength(normalized_badge, font=badge_font)) + 40
        badge_h = 86
        badge_x0 = 102
        badge_y0 = 112
        _rounded_rect(draw, (badge_x0, badge_y0, badge_x0 + badge_w, badge_y0 + badge_h), 42, _COLOR_ACCENT)
        draw.text(
            (badge_x0 + 20, badge_y0 + 23),
            normalized_badge,
            font=badge_font,
            fill=_COLOR_BADGE_TEXT,
        )

        # ── Title ──────────────────────────────────────────────────────────
        title_font = _load_font(104, bold=True)
        title_lines = _wrap_text(draw, normalized_title, title_font, 910, 3)
        y = 340
        for line in title_lines:
            draw.text((118, y), line, font=title_font, fill=_COLOR_TEXT_DARK)
            y += 132

        # ── Subtitle ───────────────────────────────────────────────────────
        subtitle_font = _load_font(44, bold=False)
        subtitle_lines = _wrap_text(draw, subtitle, subtitle_font, 860, 2)
        y = 870
        for line in subtitle_lines:
            draw.text((122, y), line, font=subtitle_font, fill=_COLOR_TEXT_MUTED)
            y += 64

        # ── Bottom accent bars ─────────────────────────────────────────────
        draw.rounded_rectangle([122, 1174, 586, 1186], radius=6, fill=_COLOR_ACCENT)
        draw.rounded_rectangle([122, 1220, 334, 1232], radius=6, fill=_COLOR_BADGE_TINT)

        # ── Footer note ────────────────────────────────────────────────────
        note_font = _load_font(34, bold=False)
        draw.text((122, 1378), "模板封面已自动生成，可直接作为小红书封面", font=note_font, fill=_COLOR_TEXT_MUTED)

        img.save(output_path, "PNG")
        return GeneratedXiaohongshuCoverImage(
            path=str(output_path),
            title=normalized_title,
            subtitle=subtitle,
            badge=normalized_badge,
        )

    except XiaohongshuCoverImageUnavailableError:
        raise
    except Exception as exc:
        raise XiaohongshuCoverImageGenerationError(f"生成封面图失败：{exc}") from exc
