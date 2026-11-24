import bpy, os, bmesh
from mathutils import Vector
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
SRC = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models/_grass_src.blend')   # copy of the pack's .blend, so it never equals the file the watcher has open
PICK = ['tall_a_LOD1','tall_b_LOD1','tall_c_LOD1','mid_b_LOD2','mid_c_LOD2','small_b_LOD2']
# bring just the picked objects in from the pack (appending keeps this scene's context working for the exporter)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
with bpy.data.libraries.load(SRC, link=False) as (df, dt):
    dt.objects = ['grass_medium_01_'+p for p in PICK]
srcs = list(dt.objects)
for o in srcs: bpy.context.scene.collection.objects.link(o)
bpy.context.view_layer.update()
# new scene collection with only the picks, each normalised: centred in XY, base on z=0, 1 m tall (the game scales it per blade)
out = []
for p, o in zip(PICK, srcs):
    ob = bpy.data.objects.new('tuft_'+p.replace('_LOD',''), bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get())))
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = o.matrix_world.copy()
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world); ob.matrix_world.identity()
    vs = [v.co for v in ob.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    h = mx.z - mn.z; c = (mn + mx) * 0.5
    ob.data.transform(__import__('mathutils').Matrix.Translation((-c.x, -c.y, -mn.z)))
    ob.data.transform(__import__('mathutils').Matrix.Scale(1.0 / h, 4))
    ob.data.update()
    out.append(ob)
    print('TUFT', ob.name, len(ob.data.vertices), 'orig height', round(h,3), 'width', round((mx.x-mn.x)/h,2))
# drop everything else
for o in list(bpy.data.objects):
    if o not in out: bpy.data.objects.remove(o, do_unlink=True)
def make_mat(name, png):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(png); t.image.alpha_mode = 'STRAIGHT'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color']); nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.8
    try: m.blend_method = 'CLIP'
    except Exception: pass
    return m
G = make_mat('grass_green', OUT + '/textures/grass/grass_green_rgba.png')
for ob in out:
    ob.data.materials.clear(); ob.data.materials.append(G)
for ob in out: ob.select_set(True)
bpy.context.view_layer.objects.active = out[0]
bpy.ops.export_scene.gltf(filepath=OUT + '/grass_tufts.glb', export_format='GLB', use_selection=True, export_image_format='AUTO', export_yup=True, export_apply=True)
print('GRASS TUFTS DONE', os.path.getsize(OUT + '/grass_tufts.glb'))
