import bpy, bmesh, math, os, sys, importlib
import numpy as np
from mathutils import Vector, noise
D = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models'); sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import fbm, smooth as tsmooth

# ---- T-34/76, realistic version. Same geometry and 4-part structure as build_tanks.py (the game looks the parts up by name),
#      but every material is a real weathered PBR texture, every face gets world-metre box-projected UVs, mud and dust are baked into vertex colours,
#      and the national markings are worn.
src = open(D + '/build_tanks.py').read()
src = src[:src.index('\nclear()\nbuild_pz4()')]
ns = {'__name__': 'tanks'}; exec(compile(src, 'build_tanks.py', 'exec'), ns)
TEX = D + '/textures/tank/'; PTEX = D + '/textures/prop/'
_IMG = {}
def img(path, srgb=True):
    if path not in _IMG:
        im = bpy.data.images.load(path); im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'; _IMG[path] = im
    return _IMG[path]

def tmat(name, col, nrm, rough, metal, nstr=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(col)
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
    nt.links.new(t.outputs['Color'], mx.inputs[6]); nt.links.new(vc.outputs['Color'], mx.inputs[7]); nt.links.new(mx.outputs[2], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(nrm, False)
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (0.3, 0.3, 0.3, 1)
    return m

SPEC = {'paint': (TEX + 'paint_olive', 2.0, 0.82, 0.05), 'track': (TEX + 'track', 0.5, 0.78, 0.35), 'steel': (TEX + 'steel', 1.0, 0.55, 0.55),
        'rubber': (TEX + 'rubber', 0.5, 0.9, 0.0), 'wood': (PTEX + 'planks', 1.0, 0.9, 0.0), 'paintdark': (TEX + 'paint_olive_dark', 2.0, 0.85, 0.05)}
TILE = {}
def mat(name, rgb, metal=0.0, rough=0.7):
    key = name.split('_', 1)[1]; p, tile, ro, me = SPEC[key]
    m = tmat(name, p + '_c.jpg', p + '_n.jpg', ro, me); TILE[name] = tile; return m

def rgba_image(name, arr):
    """worn markings: paint rubbed through and dust over the top"""
    H, W, _ = arr.shape; N = max(H, W); a = arr.copy()
    f = fbm(N, 91, 5, 5, 4)[:H, :W]; f2 = fbm(N, 92, 30, 30, 3)[:H, :W]
    hole = tsmooth(f * 0.65 + f2 * 0.55, 0.68, 0.95)
    a[..., 3] *= (1 - 0.85 * hole)
    dust = (0.15 + 0.35 * tsmooth(f, 0.4, 0.8))[..., None]
    a[..., :3] = a[..., :3] * (1 - dust) + np.array([0.30, 0.25, 0.17])[None, None, :] * dust * 0.8
    return ns['rgba_image'].__wrapped__(name, a) if hasattr(ns['rgba_image'], '__wrapped__') else _orig_rgba(name, a)
_orig_rgba = ns['rgba_image']
ns['mat'] = mat; ns['rgba_image'] = rgba_image

_orig_finish = ns['finish']
MUD = np.array([0.30, 0.205, 0.125])
def finish(bm, name, mats, loc=(0, 0, 0), skip=()):
    ob = _orig_finish(bm, name, mats, loc, skip); me = ob.data; L = Vector(loc)
    uvl = me.uv_layers.active or me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        mn = me.materials[poly.material_index].name
        if 'decal' in mn: continue
        T = TILE.get(mn, 1.0); n = poly.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co + L
            u, v = ((p.y, p.z) if ax == 0 else (p.x, p.z) if ax == 1 else (p.x, p.y))
            uvl.data[li].uv = (u / T, v / T)
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    for poly in me.polygons:
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co + L
            nz = noise.noise(Vector((p.x * 1.6, p.y * 1.6, p.z * 2.2))) * 0.5 + 0.5          # 0..1
            nf = noise.noise(Vector((p.x * 7.0, p.y * 7.0, p.z * 7.0))) * 0.5 + 0.5
            low = max(0.0, min(1.0, (1.40 - p.z) / 0.95))                                      # splash: heavier near the ground
            m = max(0.0, min(1.0, low * low * (0.7 + 1.1 * nz) + 0.3 * (nf - 0.5) * low))
            dust = 0.10 + 0.14 * nz                                                            # a film of dust everywhere
            c = (1 - m) * (1 - dust * (1 - np.array([0.86, 0.80, 0.68]))) + m * MUD
            ca.data[li].color = (float(c[0]), float(c[1]), float(c[2]), 1.0)
    return ob
ns['finish'] = finish

ns['clear']()
hull, tur, gun, bar = ns['build_t34']()

# ---------------------------------------------------------------- extra stowage, joined into the hull
box, cyl, tube, sphere = ns['box'], ns['cyl'], ns['tube'], ns['sphere']; Matrix = ns['Matrix']
bm = bmesh.new()
cyl(bm, (-0.55, -2.55, 1.50), (0.55, -2.55, 1.50), 0.14, 0.14, 14, 5)                  # rolled tarpaulin on the rear deck
for xx in (-0.4, 0.0, 0.4): cyl(bm, (xx - 0.015, -2.55, 1.50), (xx + 0.015, -2.55, 1.50), 0.148, 0.148, 14, 4)
for yy in (0.35, 0.56):                                                                 # jerrycans on the left fender
    box(bm, (-1.3, yy, 1.30), (0.34, 0.15, 0.40), None, 5)
    box(bm, (-1.3, yy, 1.51), (0.14, 0.12, 0.04), None, 2)
for sd in (-1, 1):                                                                      # spare track links on the glacis
    for i in range(4): box(bm, (sd * (0.55 + i * 0.0) , 2.2 + 0.0, 1.30 + i * 0.0), (0.0, 0.0, 0.0), None, 1) if False else None
for i in range(5): box(bm, (-0.95 + i * 0.12, 1.78, 1.56), (0.1, 0.05, 0.22), None, 1)  # track links stacked on the hull roof, front
mats = list(hull.data.materials)[:6]
ex = ns['finish'](bm, 't34_hull_stow', mats)
bpy.ops.object.select_all(action='DESELECT'); ex.select_set(True); hull.select_set(True); bpy.context.view_layer.objects.active = hull
bpy.ops.object.join()
OBJS = [o for o in bpy.data.objects if o.name.startswith('t34_')]
for o in OBJS:
    for p in o.data.polygons: p.use_smooth = False

# ---------------------------------------------------------------- previews (EEVEE, sun + sky, dirt ground)
sc = bpy.context.scene
try: sc.render.engine = 'BLENDER_EEVEE'
except Exception as e: print('eevee failed', e); sc.render.engine = 'BLENDER_WORKBENCH'
try: sc.eevee.taa_render_samples = 24
except Exception: pass
try: sc.view_settings.view_transform = 'Standard'
except Exception: pass
sunl = bpy.data.lights.new('sun', 'SUN'); sunl.energy = 4.0; sunl.angle = 0.05
sun = bpy.data.objects.new('sun', sunl); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(28))
sc.render.resolution_x = 1500; sc.render.resolution_y = 850
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.use_nodes = True; _bg = sc.world.node_tree.nodes['Background']; _bg.inputs['Color'].default_value = (0.50, 0.58, 0.68, 1); _bg.inputs['Strength'].default_value = 1.1
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.002)); gp = bpy.context.object
gm = bpy.data.materials.new('ground'); gm.use_nodes = True; gn = gm.node_tree; _t = gn.nodes.new('ShaderNodeTexImage'); _t.image = bpy.data.images.load(D + '/textures/ground_dirt.jpg')
_tc = gn.nodes.new('ShaderNodeTexCoord'); _mp = gn.nodes.new('ShaderNodeMapping'); _mp.inputs['Scale'].default_value = (30, 30, 1)
gn.links.new(_tc.outputs['UV'], _mp.inputs['Vector']); gn.links.new(_mp.outputs['Vector'], _t.inputs['Vector']); gn.links.new(_t.outputs['Color'], gn.nodes['Principled BSDF'].inputs['Base Color'])
gp.data.materials.append(gm); gp.name = 'preview_ground'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
def shot(fname, loc, tgt, lens=38):
    cam.data.lens = lens; cam.location = Vector(loc)
    cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(D, fname); bpy.ops.render.render(write_still=True)
shot('t34v2_a.png', (9.0, 8.0, 3.4), (0, 0.3, 1.1))
shot('t34v2_b.png', (-9.0, -7.5, 3.4), (0, 0.2, 1.1))
shot('t34v2_c.png', (12.5, 0.3, 1.9), (0, 0.3, 1.2), 42)
shot('t34v2_d.png', (4.2, 4.6, 2.6), (0, 1.0, 1.3), 50)
shot('t34v2_e.png', (3.4, -1.8, 1.0), (1.2, -0.3, 0.5), 50)
print('PREVIEWS DONE')

# ---------------------------------------------------------------- export: full-size and the 512 px game copy
bpy.data.objects.remove(gp, do_unlink=True); bpy.data.objects.remove(sun, do_unlink=True); bpy.data.objects.remove(cam, do_unlink=True)
def export(fn):
    bpy.ops.object.select_all(action='DESELECT')
    for o in OBJS: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(D, fn), export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True, export_image_format='AUTO')
    print(fn, os.path.getsize(os.path.join(D, fn)), 'bytes')
export('t34.glb')
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.size[0] <= 512: continue
    w, h = im.size; fp = (im.filepath or '').lower(); im.scale(512, max(1, int(h * 512 / w)))
    if fp.endswith('.jpg'): im.file_format = 'JPEG'
export('t34_game.glb')
print('T34 DONE', sum(len(o.data.polygons) for o in OBJS), 'faces')
