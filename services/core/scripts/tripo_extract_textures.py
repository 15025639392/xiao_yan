"""Extract packed textures from Tripo GLB and save them as PNG files."""
import sys, os
from pathlib import Path
import bpy

GLB_PATH = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/tripo_pbr_model_c50ca50e-e0c3-4df1-b2d3-b862d66e8cc1.glb"
OUTPUT_DIR = Path("/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/textures")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for img in bpy.data.images:
    if img.packed_file and img.size[0] > 0:
        out_path = OUTPUT_DIR / f"{img.name}.png"
        # Set file format and save
        img.filepath_raw = str(out_path)
        img.file_format = "PNG"
        img.save()
        size_kb = out_path.stat().st_size / 1024
        print(f"Saved: {out_path} ({size_kb:.0f} KB)")

print("Done.")
