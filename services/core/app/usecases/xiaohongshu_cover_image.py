from __future__ import annotations

import base64
import binascii
import json
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)

_CANVAS_WIDTH = 1242
_CANVAS_HEIGHT = 1660
_DEFAULT_BADGE = "小晏数字人全自动运营"
_DEFAULT_SUBTITLE = "先发一条能接住咨询的内容。"
_RENDER_PAGE_URL = "data:text/html;charset=utf-8," + quote(
    "<!doctype html><html><head><meta charset='utf-8'><title>xhs-cover</title></head><body></body></html>",
    safe=":/?&=,+-_.!~*'()#",
)


class XiaohongshuCoverImageError(Exception):
    """Base error for generated local Xiaohongshu cover images."""


class XiaohongshuCoverImageUnavailableError(XiaohongshuCoverImageError):
    """Raised when the browser organ is unavailable for local cover generation."""


class XiaohongshuCoverImageGenerationError(XiaohongshuCoverImageError):
    """Raised when the cover image could not be rendered or saved."""


@dataclass(frozen=True)
class GeneratedXiaohongshuCoverImage:
    path: str
    title: str
    subtitle: str
    badge: str


def generate_xiaohongshu_cover_image(
    *,
    title: str,
    body: str,
    badge: str = _DEFAULT_BADGE,
    output_dir: str | None = None,
) -> GeneratedXiaohongshuCoverImage:
    normalized_title = title.strip()
    normalized_body = body.strip()
    normalized_badge = badge.strip() or _DEFAULT_BADGE
    if not normalized_title:
        raise ValueError("cover title cannot be blank")

    subtitle = _derive_cover_subtitle(normalized_body)
    target_dir = _resolve_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    session_id = ""
    try:
        open_result = call_browser_capability(
            "browser.open",
            {"url": _RENDER_PAGE_URL, "headless": True, "activate": False},
            timeout_seconds=15.0,
        )
        session_id = str(open_result.get("session_id") or "")
        if not session_id:
            raise XiaohongshuCoverImageGenerationError("生成封面图失败：未拿到浏览器渲染会话。")

        render_result = call_browser_capability(
            "browser.evaluate",
            {
                "session_id": session_id,
                "script": _build_cover_render_script(
                    title=normalized_title,
                    subtitle=subtitle,
                    badge=normalized_badge,
                ),
            },
            timeout_seconds=15.0,
        )
        output_path = target_dir / f"xhs-cover-{uuid.uuid4().hex[:12]}.png"
        _write_png_data_url(output_path, render_result.get("result"))
        return GeneratedXiaohongshuCoverImage(
            path=str(output_path),
            title=normalized_title,
            subtitle=subtitle,
            badge=normalized_badge,
        )
    except BrowserOrganUnavailable as exc:
        raise XiaohongshuCoverImageUnavailableError("浏览器器官不可用，无法自动生成封面图。") from exc
    except BrowserCapabilityError as exc:
        raise XiaohongshuCoverImageGenerationError(f"生成封面图失败：{exc}") from exc
    finally:
        if session_id:
            try:
                call_browser_capability(
                    "browser.close",
                    {"session_id": session_id},
                    timeout_seconds=5.0,
                )
            except Exception:
                pass


def _resolve_output_dir(output_dir: str | None) -> Path:
    if output_dir and output_dir.strip():
        return Path(output_dir).expanduser().resolve()
    return Path(tempfile.gettempdir()).resolve() / "xiao_yan_xhs_covers"


def _derive_cover_subtitle(body: str) -> str:
    if not body:
        return _DEFAULT_SUBTITLE
    segments = [segment.strip() for segment in re.split(r"\n\s*\n|\n", body) if segment.strip()]
    candidate = segments[0] if segments else body.strip()
    normalized = re.sub(r"\s+", " ", candidate).strip("，。；,; ")
    if not normalized:
        return _DEFAULT_SUBTITLE
    if len(normalized) <= 28:
        return normalized
    return normalized[:27].rstrip("，。；,; ") + "..."


def _write_png_data_url(path: Path, raw_payload: object) -> None:
    if not isinstance(raw_payload, str) or not raw_payload.startswith("data:image/png;base64,"):
        raise XiaohongshuCoverImageGenerationError("生成封面图失败：浏览器没有返回 PNG 数据。")

    _, encoded = raw_payload.split(",", 1)
    try:
        path.write_bytes(base64.b64decode(encoded, validate=True))
    except (ValueError, binascii.Error) as exc:
        raise XiaohongshuCoverImageGenerationError("生成封面图失败：PNG 数据损坏。") from exc


def _build_cover_render_script(*, title: str, subtitle: str, badge: str) -> str:
    payload = json.dumps(
        {
            "width": _CANVAS_WIDTH,
            "height": _CANVAS_HEIGHT,
            "title": title,
            "subtitle": subtitle,
            "badge": badge,
        },
        ensure_ascii=False,
    )
    return f"""
(() => {{
  const payload = {payload};
  const canvas = document.createElement("canvas");
  canvas.width = payload.width;
  canvas.height = payload.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  const roundRect = (x, y, width, height, radius) => {{
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }};

  const fillRoundedRect = (x, y, width, height, radius, fillStyle) => {{
    ctx.save();
    ctx.fillStyle = fillStyle;
    roundRect(x, y, width, height, radius);
    ctx.fill();
    ctx.restore();
  }};

  const wrapText = (text, maxWidth, font, maxLines) => {{
    ctx.font = font;
    const chars = Array.from(text || "");
    const lines = [];
    let current = "";
    for (const char of chars) {{
      const candidate = current + char;
      if (!current || ctx.measureText(candidate).width <= maxWidth) {{
        current = candidate;
        continue;
      }}
      lines.push(current.trim());
      current = char;
      if (lines.length === maxLines) {{
        break;
      }}
    }}
    if (lines.length < maxLines && current) {{
      lines.push(current.trim());
    }}
    const usedChars = Array.from(lines.join("")).length;
    if (usedChars < chars.length && lines.length > 0) {{
      let last = lines[lines.length - 1];
      while (last && ctx.measureText(`${{last}}...`).width > maxWidth) {{
        last = last.slice(0, -1);
      }}
      lines[lines.length - 1] = `${{last}}...`;
    }}
    return lines;
  }};

  const gradient = ctx.createLinearGradient(0, 0, payload.width, payload.height);
  gradient.addColorStop(0, "#fff9f4");
  gradient.addColorStop(0.55, "#ffe9df");
  gradient.addColorStop(1, "#ffd4c5");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, payload.width, payload.height);

  fillRoundedRect(74, 76, 360, 148, 52, "rgba(255, 106, 77, 0.12)");
  fillRoundedRect(884, 118, 220, 220, 66, "rgba(255, 255, 255, 0.58)");
  fillRoundedRect(920, 1010, 192, 192, 54, "rgba(255, 111, 79, 0.12)");
  fillRoundedRect(72, 248, 1098, 1180, 64, "rgba(255, 253, 249, 0.96)");

  ctx.save();
  ctx.fillStyle = "rgba(255, 102, 72, 0.14)";
  ctx.beginPath();
  ctx.arc(1048, 520, 148, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  fillRoundedRect(102, 112, 432, 86, 42, "#ff5d45");
  ctx.fillStyle = "#ffffff";
  ctx.font = "600 34px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif";
  ctx.textBaseline = "middle";
  ctx.fillText(payload.badge, 136, 156);

  ctx.fillStyle = "#1c1b1a";
  ctx.textBaseline = "alphabetic";
  const titleLines = wrapText(
    payload.title,
    910,
    "700 104px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    3,
  );
  titleLines.forEach((line, index) => {{
    ctx.font = "700 104px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif";
    ctx.fillText(line, 118, 520 + index * 132);
  }});

  ctx.fillStyle = "#594c48";
  const subtitleLines = wrapText(
    payload.subtitle,
    860,
    "500 44px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    2,
  );
  subtitleLines.forEach((line, index) => {{
    ctx.font = "500 44px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif";
    ctx.fillText(line, 122, 1018 + index * 64);
  }});

  fillRoundedRect(122, 1174, 464, 12, 6, "#ff7b63");
  fillRoundedRect(122, 1220, 212, 12, 6, "rgba(255, 123, 99, 0.35)");

  ctx.fillStyle = "#8b5d54";
  ctx.font = "500 34px system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif";
  ctx.fillText("模板封面已自动生成，可直接作为小红书封面", 122, 1378);

  return canvas.toDataURL("image/png");
}})();
"""
