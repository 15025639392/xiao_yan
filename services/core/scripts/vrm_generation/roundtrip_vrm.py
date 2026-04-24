"""Minimal Blender-side VRM roundtrip prototype.

Run with Blender, not system Python:

/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/roundtrip_vrm.py \
  -- \
  --input apps/desktop/public/avatar/xiaoyan.vrm \
  --spec services/core/scripts/vrm_generation/character_spec.example.json \
  --output /tmp/xiaoyan-roundtrip.vrm
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import bpy

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def parse_args() -> argparse.Namespace:
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Import a VRM, apply a tiny spec subset, and export it again.")
    parser.add_argument("--input", required=True, help="Input .vrm path")
    parser.add_argument("--spec", required=True, help="character_spec.json path")
    parser.add_argument("--output", required=True, help="Output .vrm path")
    return parser.parse_args(script_args)


def load_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for section, key in (("hair", "color"), ("clothes", "primary_color"), ("clothes", "secondary_color")):
        value = spec.get(section, {}).get(key)
        if value is not None and not HEX_COLOR_RE.match(value):
            raise ValueError(f"{section}.{key} must be a #RRGGBB color")
    return spec


def hex_to_rgba(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    return (
        int(value[1:3], 16) / 255,
        int(value[3:5], 16) / 255,
        int(value[5:7], 16) / 255,
        alpha,
    )


def apply_spec(spec: dict[str, Any]) -> None:
    primary_color = spec.get("clothes", {}).get("primary_color")
    if not primary_color:
        return

    rgba = hex_to_rgba(primary_color)
    for material in bpy.data.materials:
        material.diffuse_color = rgba
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED" and "Base Color" in node.inputs:
                    node.inputs["Base Color"].default_value = rgba


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    spec_path = Path(args.spec).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)

    spec = load_spec(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.vrm(filepath=str(input_path))
    apply_spec(spec)
    bpy.ops.export_scene.vrm(filepath=str(output_path))
    print(json.dumps({"output": str(output_path), "bytes": output_path.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
