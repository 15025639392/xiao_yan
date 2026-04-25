"""Render Tripo GLB with Cycles for proper PBR texture handling."""
import sys, math
from pathlib import Path
import bpy
from mathutils import Vector

GLB_PATH = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/tripo_pbr_model_c50ca50e-e0c3-4df1-b2d3-b862d66e8cc1.glb"
OUTPUT_DIR = Path("/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/renders")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

bpy.ops.import_scene.gltf(filepath=GLB_PATH)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
print(f"Meshes: {len(meshes)}, verts: {sum(len(o.data.vertices) for o in meshes)}")

# Check UV maps
for obj in meshes:
    for uv in obj.data.uv_layers:
        print(f"UV layer: {uv.name}")

# Bounds
bbox = []
for o in meshes:
    for v in o.data.vertices:
        bbox.append(o.matrix_world @ v.co)
min_x = min(v.x for v in bbox)
max_x = max(v.x for v in bbox)
min_y = min(v.y for v in bbox)
max_y = max(v.y for v in bbox)
min_z = min(v.z for v in bbox)
max_z = max(v.z for v in bbox)
cx, cy, cz = (min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2
w, h, d = max_x-min_x, max_z-min_z, max_y-min_y
print(f"Center: ({cx:.2f},{cy:.2f},{cz:.2f}) size: {w:.2f}x{h:.2f}x{d:.2f}")

# Camera
cam_dist = max(w, h) * 2.5 + d
bpy.ops.object.camera_add(location=(cx, cy - cam_dist, cz))
camera = bpy.context.object
bpy.context.scene.camera = camera
camera.rotation_euler = (math.radians(90), 0, 0)

# Cycles settings
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "CPU"
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.image_settings.file_format = "PNG"

# World - studio lighting
world = bpy.data.worlds.new("Studio")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.9, 0.9, 0.9, 1)
bg.inputs["Strength"].default_value = 2.0

# Lighting
bpy.ops.object.light_add(type="AREA", location=(cx+1.5, cy-1.5, cz+2.0))
bpy.context.object.data.energy = 2000
bpy.ops.object.light_add(type="AREA", location=(cx-1.5, cy-2.0, cz+1.0))
bpy.context.object.data.energy = 800

bpy.context.scene.render.filepath = str(OUTPUT_DIR / "tripo_cycles_front.png")
bpy.context.scene.render.film_transparent = False
bpy.ops.render.render(write_still=True)
print(f"Rendered: {bpy.context.scene.render.filepath}")
