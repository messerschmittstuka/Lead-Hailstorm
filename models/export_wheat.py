import bpy, os
bpy.ops.wm.open_mainfile(filepath='/Users/justinho/Documents/GitHub/Lead-Hailstorm/models/assets/veg_wheat/approved/model.blend')
print('OBJS', [(o.name, o.type, o.parent.name if o.parent else None) for o in bpy.data.objects if not o.name.startswith('wp_')][:20])
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.size[0] <= 512: continue
    w, h = im.size; im.scale(512, max(1, int(h * 512 / w)))
bpy.ops.object.select_all(action='DESELECT')
root = bpy.data.objects['wheat_clump']
sel = [root] + [c for c in root.children_recursive]
for o in sel: o.select_set(True)
bpy.context.view_layer.objects.active = root
root.location = (0, 0, 0); root.rotation_euler = (0, 0, 0); root.scale = (1, 1, 1)
win = bpy.context.window_manager.windows[0]
with bpy.context.temp_override(window=win, scene=bpy.context.scene, view_layer=bpy.context.view_layer, active_object=root, selected_objects=sel):
    bpy.ops.export_scene.gltf(filepath='/Users/justinho/Documents/GitHub/Lead-Hailstorm/models/wheat_game.glb', export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=False, export_image_format='AUTO', export_animations=False)
print('WHEAT GLB', os.path.getsize('/Users/justinho/Documents/GitHub/Lead-Hailstorm/models/wheat_game.glb'))
