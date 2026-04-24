"""Export a VRM from an opened .blend template after applying a tiny spec subset.

Run with Blender:

/Applications/Blender.app/Contents/MacOS/Blender \
  --background services/core/.data/vrm_generation/templates/xiaoyan_base.blend \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/export_blend_vrm.py \
  -- \
  --spec services/core/scripts/vrm_generation/character_spec.example.json \
  --output /tmp/xiaoyan-from-template.vrm
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
    parser = argparse.ArgumentParser(description="Apply a character spec to the open .blend and export VRM.")
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
    spec_path = Path(args.spec).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    apply_spec(load_spec(spec_path))
    bpy.ops.export_scene.vrm(filepath=str(output_path))
    print(json.dumps({"output": str(output_path), "bytes": output_path.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
