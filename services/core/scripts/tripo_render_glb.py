"""Import Tripo GLB into Blender and render front views — fixed material/lighting."""
import sys, os, math
from pathlib import Path
import bpy
from mathutils import Vector

GLB_PATH = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/tripo_pbr_model_c50ca50e-e0c3-4df1-b2d3-b862d66e8cc1.glb"
OUTPUT_DIR = Path("/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output/renders")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_glb(path: str):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    print(f"Imported {len(meshes)} mesh objects, {sum(len(o.data.vertices) for o in meshes)} total verts")

    # Verify texture nodes are connected
    for obj in meshes:
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.node_tree:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                base_color = bsdf.inputs["Base Color"]
                print(f"  Material '{mat.name}': BaseColor linked={base_color.is_linked}")
    return meshes


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clear_scene()
    meshes = import_glb(GLB_PATH)
    if not meshes:
        print("No mesh objects imported")
        sys.exit(1)

    # Join all meshes
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object

    # Bounds
    bpy.context.view_layer.update()
    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
    min_x = min(v.x for v in bbox)
    max_x = max(v.x for v in bbox)
    min_y = min(v.y for v in bbox)
    max_y = max(v.y for v in bbox)
    min_z = min(v.z for v in bbox)
    max_z = max(v.z for v in bbox)
    cx, cy, cz = (min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2
    w, h, d = max_x-min_x, max_z-min_z, max_y-min_y
    print(f"Center: ({cx:.3f}, {cy:.3f}, {cz:.3f}) size: {w:.3f}x{h:.3f}x{d:.3f}")

    # Camera — front view
    cam_dist = max(w, h) * 2.5 + d
    bpy.ops.object.camera_add(location=(cx, cy - cam_dist, cz))
    camera = bpy.context.object
    bpy.context.scene.camera = camera
    camera.rotation_euler = (math.radians(90), 0, 0)

    # Render settings
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.film_transparent = False

    # World background — bright studio
    world = bpy.data.worlds.new("StudioWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes["Background"]
    bg_node.inputs["Color"].default_value = (0.85, 0.85, 0.85, 1.0)
    bg_node.inputs["Strength"].default_value = 2.0

    # Three-point lighting
    key_loc = (cx + 1.5, cy - 1.5, cz + 2.0)
    bpy.ops.object.light_add(type="AREA", location=key_loc)
    key = bpy.context.object
    key.data.energy = 2000
    key.data.size = 3

    fill_loc = (cx - 1.5, cy - 2.0, cz + 1.0)
    bpy.ops.object.light_add(type="AREA", location=fill_loc)
    fill = bpy.context.object
    fill.data.energy = 800
    fill.data.size = 3

    rim_loc = (cx, cy + 1.0, cz + 2.5)
    bpy.ops.object.light_add(type="AREA", location=rim_loc)
    rim = bpy.context.object
    rim.data.energy = 1000
    rim.data.size = 2

    # Front view
    bpy.context.scene.render.filepath = str(OUTPUT_DIR / "tripo_front.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered front: {bpy.context.scene.render.filepath}")

    # 3/4 view
    angle = math.radians(30)
    cam_x = cx + cam_dist * math.sin(angle) * 0.6
    cam_y = cy - cam_dist * math.cos(angle) * 0.7
    cam_z = cz + cam_dist * 0.25
    camera.location = (cam_x, cam_y, cam_z)
    # Look at center
    dir_vec = Vector((cx - cam_x, cy - cam_y, cz - cam_z))
    camera.rotation_euler = dir_vec.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.render.filepath = str(OUTPUT_DIR / "tripo_quarter.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered quarter: {bpy.context.scene.render.filepath}")

    print("Done.")


if __name__ == "__main__":
    main()
