import bpy, os, sys, importlib
sys.path.insert(0,os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models/pipeline'))
import rig_lib, anim_lib, clips_wehr
for m in (rig_lib,anim_lib,clips_wehr): importlib.reload(m)
A=os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models/assets/soviet_game')
bpy.ops.wm.open_mainfile(filepath=os.path.join(A,'rig.blend'))
sc=bpy.context.scene; arm=[o for o in sc.objects if o.type=='ARMATURE'][0]
anim_lib.init_rest(arm); sc.render.fps=30
acts={}
for name,mode,fr in (('idle','idle',30),('walk','walk',19),('run','run',15)): acts[name]=clips_wehr.make_clip(arm,name,mode,fr)
arm.animation_data.action=None
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
for name,a in acts.items():
    tr=arm.animation_data.nla_tracks.new(); tr.name=name; st=tr.strips.new(name,1,a); st.name=name
base=set()
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image and any(l.to_socket.name=='Base Color' for o in n.outputs for l in o.links): base.add(n.image.name)
for im in bpy.data.images:
    if im.type!='IMAGE' or im.size[0]==0: continue
    t=1024 if im.name in base else 512
    if im.size[0]>t: im.scale(t,t)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('MESH','ARMATURE'): ob.select_set(True)
out=os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models/soviet_game.glb')
win=bpy.context.window_manager.windows[0]; bpy.context.view_layer.objects.active=arm
with bpy.context.temp_override(window=win,scene=sc,view_layer=bpy.context.view_layer,active_object=arm,selected_objects=[o for o in bpy.data.objects if o.select_get()]):
    bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',use_selection=True,export_apply=False,export_yup=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_image_format='JPEG')
print('GLB',os.path.getsize(out))
