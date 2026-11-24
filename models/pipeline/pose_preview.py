"""render posed frames of a rigged asset's actions (review aid only). usage from run.py: pose_preview.run('german_soldier','v3',[('walk',[0,8,15,23]),('run',[0,5,10,15]),('idle',[0,45])])"""
import bpy, os, math, json
from mathutils import Vector
import lib_loop, lib_render

def run(asset, version, plan, az=90, res=520):
    vdir = os.path.join(lib_loop.ROOT, asset, version); spec = json.load(open(os.path.join(lib_loop.ROOT, asset, 'spec.json')))
    lib_loop.clear_scene(); ns = {'__name__': 'build', 'ASSET': asset, 'VERSION': version, 'OUT': vdir, 'SPEC': spec}
    exec(compile(open(os.path.join(vdir, 'build.py')).read(), 'build.py', 'exec'), ns)
    ao = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]; rig = lib_render.Rig(Vector((-1, -1, 0)), Vector((1, 1, 1.8)), 0.1, res); rig.set_front('-Y')
    out = os.path.join(vdir, 'pose'); os.makedirs(out, exist_ok=True); files = []
    for act, frames in plan:
        ao.animation_data.action = bpy.data.actions[act]
        for f in frames:
            bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
            rig.aim(az, 5, (0, 0, 0.9), 4.2); p = os.path.join(out, '%s_%02d.png' % (act, f)); rig.shot(p); files.append(p)
    for o in (rig.cam, rig.ground, *rig.lights): bpy.data.objects.remove(o, do_unlink=True)
    print('POSE OK', len(files))
