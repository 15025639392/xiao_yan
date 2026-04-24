"""Create an editable Blender template from an existing VRM file.

Run with Blender:

/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/prepare_blend_template.py \
  -- \
  --input apps/desktop/public/avatar/xiaoyan.vrm \
  --output services/core/.data/vrm_generation/templates/xiaoyan_base.blend
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Import a VRM and save it as an editable .blend template.")
    parser.add_argument("--input", required=True, help="Input .vrm path")
    parser.add_argument("--output", required=True, help="Output .blend path")
    return parser.parse_args(script_args)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.vrm(filepath=str(input_path))
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"saved_template={output_path}")


if __name__ == "__main__":
    main()
