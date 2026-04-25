"""Inspect Tripo GLB material node tree for PBR textures."""
import sys, json, math
from pathlib import Path
import bpy

GLB_PATH = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/tripo_pbr_model_c50ca50e-e0c3-4df1-b2d3-b862d66e8cc1.glb"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
print(f"Mesh objects: {len(meshes)}")

for obj in meshes:
    print(f"\n=== {obj.name} ===")
    for slot in obj.material_slots:
        mat = slot.material
        if not mat:
            continue
        print(f"\nMaterial: {mat.name}")
        if not mat.node_tree:
            print("  No node tree")
            continue

        for node in mat.node_tree.nodes:
            print(f"  Node: {node.name} ({node.type})")
            if node.type == "TEX_IMAGE":
                img = node.image
                if img:
                    print(f"    Image: {img.name} size={img.size[0]}x{img.size[1]} filepath={img.filepath}")
                    # Check if packed
                    if img.packed_file:
                        print(f"    Packed: {img.packed_file.size} bytes")
            elif node.type == "BSDF_PRINCIPLED":
                for inp_name in ["Base Color", "Roughness", "Metallic", "Normal", "Alpha"]:
                    inp = node.inputs.get(inp_name)
                    if inp:
                        if inp.is_linked:
                            link = inp.links[0]
                            print(f"    {inp_name}: linked -> {link.from_node.name}.{link.from_socket.name}")
                        else:
                            val = inp.default_value
                            if hasattr(val, '__len__'):
                                val = [round(v, 4) for v in val]
                            else:
                                val = round(val, 4)
                            print(f"    {inp_name}: {val}")

# Also check for textures in bpy.data.images
print("\n\n=== All Images ===")
for img in bpy.data.images:
    print(f"{img.name}: size={img.size[0]}x{img.size[1]} filepath={img.filepath} packed={'yes' if img.packed_file else 'no'}")

print("\nDone.")
