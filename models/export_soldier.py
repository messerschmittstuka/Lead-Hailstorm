import bpy, os
SRC = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models/assets/german_soldier_e/approved/model.blend'
bpy.ops.wm.open_mainfile(filepath=SRC)
print('OPENED', SRC, [a.name for a in bpy.data.actions], [o.name for o in bpy.data.objects if o.type == 'ARMATURE'])
for ob in bpy.data.objects:
    ad = ob.animation_data
    print('ANIM', ob.name, ob.type, ad.action.name if ad and ad.action else None, len(ad.nla_tracks) if ad else 0)
    if ob.type != 'ARMATURE' and ad: ob.animation_data_clear()
arm0 = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
for a in bpy.data.actions:
    print('ACT', a.name, 'slots', len(a.slots), 'fcurves', sum(len(l.strips[0].channelbags[0].fcurves) if l.strips and l.strips[0].channelbags else 0 for l in a.layers), 'range', tuple(a.frame_range))
arm0.animation_data_create(); arm0.animation_data.action = None
for tr in list(arm0.animation_data.nla_tracks): arm0.animation_data.nla_tracks.remove(tr)
for a in bpy.data.actions:
    if a.name.split('.')[0] not in ('idle', 'walk', 'run'): continue
    if '.' in a.name: continue
    tr = arm0.animation_data.nla_tracks.new(); tr.name = a.name
    st = tr.strips.new(a.name, int(a.frame_range[0]), a); st.name = a.name
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.size[0] <= 512: continue
    w, h = im.size; im.scale(512, max(1, int(h * 512 / w)))
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('MESH', 'ARMATURE'): ob.select_set(True)
out = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models/german_soldier_game.glb'
win = bpy.context.window_manager.windows[0]
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
bpy.context.view_layer.objects.active = arm
with bpy.context.temp_override(window=win, scene=bpy.context.scene, view_layer=bpy.context.view_layer, active_object=arm, selected_objects=[o for o in bpy.data.objects if o.select_get()]):
  bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_apply=False, export_yup=True, export_animations=True, export_animation_mode='NLA_TRACKS', export_image_format='AUTO')
print('SOLDIER GLB', os.path.getsize(out))
