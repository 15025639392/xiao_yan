"""Render the Tripo Color texture on a flat plane to verify texture data."""
import sys
from pathlib import Path
import bpy
import math

GLB_PATH = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/tripo_pbr_model_c50ca50e-e0c3-4df1-b2d3-b862d66e8cc1.glb"
OUTPUT_DIR = Path("/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/renders")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

# Import GLB to get the texture
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

# Find the mesh and its texture
mesh = None
for o in bpy.context.scene.objects:
    if o.type == "MESH":
        mesh = o
        break

if not mesh:
    print("No mesh found")
    sys.exit(1)

mat = mesh.data.materials[0]
tex_node = None
for node in mat.node_tree.nodes:
    if node.type == "TEX_IMAGE" and node.image and "Color" in (node.image.name or ""):
        tex_node = node
        break

if not tex_node:
    # Fallback: just get any TEX_IMAGE node linked to Base Color
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf and bsdf.inputs["Base Color"].is_linked:
        link = bsdf.inputs["Base Color"].links[0]
        if link.from_node.type == "TEX_IMAGE":
            tex_node = link.from_node

if not tex_node:
    print("No Color texture node found")
    sys.exit(1)

print(f"Texture: {tex_node.image.name} size={tex_node.image.size[0]}x{tex_node.image.size[1]}")

# Delete imported mesh, create a plane with the texture
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

# Create plane
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
plane = bpy.context.object
plane.name = "TexturePlane"

# Create material with the extracted texture
plane_mat = bpy.data.materials.new("PlaneMat")
plane_mat.use_nodes = True
nodes = plane_mat.node_tree.nodes
nodes.clear()
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
output = nodes.new("ShaderNodeOutputMaterial")
tex = nodes.new("ShaderNodeTexImage")
tex.image = tex_node.image
nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
plane_mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
plane_mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
plane.data.materials.append(plane_mat)

# Camera
bpy.ops.object.camera_add(location=(0, -2.5, 0))
camera = bpy.context.object
bpy.context.scene.camera = camera
camera.rotation_euler = (math.radians(90), 0, 0)

# World
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)

# Render
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.render.resolution_x = 2048
bpy.context.scene.render.resolution_y = 2048
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.render.filepath = str(OUTPUT_DIR / "tripo_texture_plane.png")
bpy.ops.render.render(write_still=True)
print(f"Rendered texture plane: {bpy.context.scene.render.filepath}")
