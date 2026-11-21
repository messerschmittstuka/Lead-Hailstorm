import bpy, bmesh, math, os
from mathutils import Vector

# ---- Karabiner 98k, built in game units (1 unit = 1 m). Muzzle points +Y, up is +Z, bore axis at z=0.035. ----
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
os.makedirs(OUT, exist_ok=True)

# clean scene
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
for blk in (bpy.data.meshes, bpy.data.materials):
    for b in list(blk):
        if b.users == 0: blk.remove(b)

def mat(name, rgb, metal=0.0, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1)
    return m

import numpy as np
def blur(a, kx, ky=1):
    out = a
    for ax, k in ((1, kx), (0, ky)):
        if k <= 1: continue
        pad = [(0, 0), (0, 0)]; pad[ax] = (k, 0)
        c = np.cumsum(np.pad(out, pad, mode='wrap'), axis=ax)
        out = (c[:, k:] - c[:, :-k]) / k if ax == 1 else (c[k:, :] - c[:-k, :]) / k
    return out

def norm(a):
    return (a - a.mean()) / (a.std() + 1e-6)

def wood_image(name, base, seed, W=2048, H=512):
    rng = np.random.default_rng(seed)
    r = lambda: rng.random((H, W)).astype(np.float32)
    streak = norm(blur(blur(r(), 220, 2), 90, 1))            # long fibres
    warp   = norm(blur(blur(r(), 700, 40), 300, 10))         # slow waviness of the rings
    fine   = norm(blur(r(), 24, 1))                          # short flecks
    yy = (np.arange(H, dtype=np.float32) / H)[:, None]
    ph = yy * 11.0 + warp * 0.55 + streak * 0.18             # ring coordinate: a few wide rings across the stock
    rings = 0.5 + 0.5 * np.sin(2 * np.pi * ph)
    rings = np.clip(rings, 0, 1) ** 1.6                      # thin dark late-wood lines
    pores = (blur((r() > 0.9965).astype(np.float32), 14, 1) * 6.0).clip(0, 1)   # little dark pores, stretched along the grain
    v = 0.60 - 0.34 * rings + 0.10 * np.clip(streak * 0.35, -1, 1) + 0.12 * np.clip(warp * 0.4, -1, 1) + 0.05 * fine - 0.30 * pores
    v = np.clip(v, 0.05, 1.0)
    base = np.array(base, dtype=np.float32)
    dark = base * np.array([0.38, 0.34, 0.30], dtype=np.float32)
    light = base * np.array([1.30, 1.30, 1.15], dtype=np.float32)
    tint = (0.5 + 0.5 * np.clip(streak * 0.3, -1, 1))[:, :, None] * np.array([0.10, 0.02, -0.02], dtype=np.float32)   # warmer red in the dark streaks
    rgb = dark[None, None, :] + (light - dark)[None, None, :] * v[:, :, None] + tint * 0.4 * base[None, None, :]
    img = bpy.data.images.new(name, W, H)
    px = np.ones((H, W, 4), dtype=np.float32); px[:, :, :3] = np.clip(rgb, 0, 1)
    img.pixels = px.ravel().tolist(); img.pack()
    return img

def wood_mat(name, base, seed, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = wood_image(name + '_tex', base, seed)
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = 0.0
    m.diffuse_color = (base[0], base[1], base[2], 1)
    return m

WOOD  = wood_mat('birch', (0.66, 0.40, 0.18), 11, 0.42)
WOOD2 = wood_mat('birch_dark', (0.42, 0.22, 0.09), 13, 0.5)
BLUED = mat('blued_steel', (0.03, 0.033, 0.04), 0.9, 0.36)
STEEL = mat('bright_steel', (0.46, 0.47, 0.5), 1.0, 0.28)
PARKER = mat('parkerised', (0.055, 0.06, 0.052), 0.7, 0.55)
BRASS = mat('brass', (0.55, 0.38, 0.1), 1.0, 0.3)

root = bpy.data.objects.new('Mosin', None); bpy.context.collection.objects.link(root)

def finish(ob, m, smooth=True, bevel=0.0012):
    ob.data.materials.append(m)
    ob.parent = root
    if bevel:
        md = ob.modifiers.new('bev', 'BEVEL'); md.width = bevel; md.segments = 2; md.limit_method = 'ANGLE'
    if smooth:
        for p in ob.data.polygons: p.use_smooth = True
    return ob

def box(name, sx, sy, sz, cx, cy, cz, m, bevel=0.0012):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, cz))
    ob = bpy.context.active_object; ob.name = name; ob.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    return finish(ob, m, True, bevel)

def cyl_y(name, r1, r2, y0, y1, cx, cz, m, verts=28, bevel=0.0008):
    L = y1 - y0
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=L, location=(cx, (y0 + y1) / 2, cz), rotation=(-math.pi / 2, 0, 0))
    ob = bpy.context.active_object; ob.name = name
    return finish(ob, m, True, bevel)

def cyl_x(name, r, x0, x1, cy, cz, m, verts=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=abs(x1 - x0), location=((x0 + x1) / 2, cy, cz), rotation=(0, math.pi / 2, 0))
    ob = bpy.context.active_object; ob.name = name
    return finish(ob, m, True, 0)

def rod(name, p1, p2, r, m, verts=14):
    a = Vector(p1); b = Vector(p2); d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(a + b) / 2)
    ob = bpy.context.active_object; ob.name = name
    ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return finish(ob, m, True, 0)

def ball(name, r, loc, m):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=24, ring_count=14, location=loc)
    ob = bpy.context.active_object; ob.name = name
    return finish(ob, m, True, 0)

def torus_y(name, R, r, y, cx, cz, m):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=28, minor_segments=10, location=(cx, y, cz), rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.active_object; ob.name = name
    return finish(ob, m, True, 0)

def planar_uv(ob, k=3.0):
    me = ob.data; uv = me.uv_layers.new(name='UVMap') if not me.uv_layers else me.uv_layers[0]
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            if abs(n.x) >= abs(n.z) * 0.8 and abs(n.x) >= abs(n.y):
                uv.data[li].uv = (v.y * k, v.z * k * 1.2 + 0.5)
            else:
                uv.data[li].uv = (v.y * k, v.x * k * 1.2 + 0.5)

def profile(name, pts, width, m, bevel=0.003, subd=1, taper=None):
    """extrude a side outline [(y,z),...] to a given width (x), smoothed."""
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    vs = [bm.verts.new((-width / 2, y, z)) for y, z in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    vv = [v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(width, 0, 0), verts=vv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    if taper:
        for v in me.vertices: v.co.x *= taper(v.co.y)
    planar_uv(ob)
    bpy.context.view_layer.objects.active = ob
    ob.data.materials.append(m); ob.parent = root
    md = ob.modifiers.new('bev', 'BEVEL'); md.width = bevel; md.segments = 3; md.limit_method = 'ANGLE'
    if subd:
        ss = ob.modifiers.new('sub', 'SUBSURF'); ss.levels = 1; ss.render_levels = 1
    for p in ob.data.polygons: p.use_smooth = True
    return ob

BZ = 0.035            # bore height. Game units: muzzle at y=+0.88, butt plate at y=-0.41 (the game's z axis is -y here)
stock_pts = [
    (0.72, 0.047), (0.55, 0.049), (0.35, 0.050), (0.16, 0.048), (0.0, 0.045), (-0.06, 0.042), (-0.11, 0.036), (-0.17, 0.031),
    (-0.25, 0.027), (-0.33, 0.022), (-0.40, 0.016),
    (-0.412, -0.05), (-0.405, -0.118),
    (-0.33, -0.100), (-0.25, -0.080), (-0.17, -0.062), (-0.12, -0.052), (-0.095, -0.040), (-0.07, -0.031),
    (-0.01, -0.030), (0.04, -0.026), (0.12, -0.012), (0.22, 0.0), (0.45, 0.012), (0.72, 0.014)
]
profile('stock', stock_pts, 0.044, WOOD, 0.004, 2, taper=lambda y: 1.0 if y < 0.16 else max(0.72, 1.0 - 0.28 * min(1.0, (y - 0.16) / 0.5)))
profile('handguard', [(0.27, 0.046), (0.27, 0.0625), (0.31, 0.0645), (0.47, 0.0645), (0.51, 0.0605), (0.51, 0.046)], 0.032, WOOD2, 0.003, 1)
profile('butt_plate', [(-0.402, 0.016), (-0.419, -0.05), (-0.416, -0.124), (-0.406, -0.122), (-0.409, -0.05), (-0.394, 0.012)], 0.045, BLUED, 0.0015, 1)
box('butt_screw_t', 0.007, 0.004, 0.007, 0, -0.4165, -0.025, STEEL, 0.0006)
box('butt_screw_b', 0.007, 0.004, 0.007, 0, -0.4145, -0.100, STEEL, 0.0006)

# barrel, receiver
cyl_y('barrel', 0.0148, 0.0105, 0.12, 0.88, 0, BZ, BLUED)
torus_y('muzzle_crown', 0.0108, 0.0016, 0.88, 0, BZ, STEEL)
cyl_y('receiver_ring', 0.0195, 0.0195, 0.075, 0.19, 0, BZ, BLUED)
cyl_y('receiver', 0.0185, 0.0185, -0.095, 0.080, 0, BZ, BLUED, 30)
box('receiver_floor', 0.032, 0.18, 0.020, 0, -0.005, 0.016, BLUED)
box('clip_guide', 0.030, 0.075, 0.006, 0, 0.02, 0.061, PARKER)
for x in (-0.0195, 0.0195):
    for y in (-0.05, 0.05):
        cyl_x('screw', 0.0038, x, x + (0.003 if x > 0 else -0.003), y, 0.0, STEEL, 12)

# bolt: straight body, big cocking piece, handle swept out and down, ball knob
cyl_y('bolt_body', 0.0108, 0.0108, -0.085, 0.04, 0, BZ + 0.0035, STEEL)
cyl_y('cocking_piece', 0.0098, 0.0085, -0.145, -0.085, 0, BZ + 0.0035, STEEL)
ball('bolt_safety', 0.0105, (0, -0.148, BZ + 0.0035), STEEL)
rod('bolt_arm', (0.008, -0.010, BZ + 0.0035), (0.052, -0.018, 0.030), 0.0052, STEEL)
rod('bolt_arm_2', (0.052, -0.018, 0.030), (0.062, -0.028, 0.012), 0.0052, STEEL)
ball('bolt_knob', 0.0115, (0.0635, -0.030, 0.004), STEEL)
kn = bpy.data.objects.new('Knob', None); bpy.context.collection.objects.link(kn); kn.parent = root; kn.location = (0.0635, -0.030, 0.004)

# trigger guard, floor plate, trigger
box('floor_plate', 0.034, 0.075, 0.008, 0, -0.010, -0.0295, PARKER, 0.0015)
def curve_tube(name, pts, r, m):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 4; cu.resolution_u = 14
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for p, (y, z) in zip(sp.bezier_points, pts):
        p.co = (0, y, z); p.handle_left_type = 'AUTO'; p.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.convert(target='MESH'); ob = bpy.context.active_object
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.materials.append(m); ob.parent = root
    return ob
curve_tube('trigger_guard', [(-0.085, -0.028), (-0.075, -0.056), (-0.045, -0.067), (-0.008, -0.060), (0.012, -0.026)], 0.0036, PARKER)
box('trigger', 0.006, 0.006, 0.030, 0, -0.040, -0.044, STEEL, 0.0008)

# barrel bands, nose cap, bayonet lug
for i, y in enumerate((0.28, 0.50, 0.665)):
    box('band_%d' % i, 0.047, 0.011, 0.056 if i == 0 else 0.046, 0, y, 0.037 if i == 0 else 0.031, STEEL, 0.0015)
box('nose_cap', 0.040, 0.030, 0.044, 0, 0.705, 0.030, STEEL, 0.002)
box('bayonet_lug', 0.012, 0.030, 0.014, 0, 0.835, 0.0155, STEEL, 0.001)
box('muzzle_collar', 0.026, 0.020, 0.026, 0, 0.855, BZ, BLUED, 0.001)

# rig: bolt, trigger, floor plate groups with pivots
def group(name, pivot, members):
    g = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(g)
    g.parent = root; g.location = pivot
    bpy.context.view_layer.update()
    for n in members:
        for ob in [o for o in bpy.data.objects if o.type == 'MESH' and (o.name == n or o.name.startswith(n + '.'))]:
            ob.parent = g; ob.matrix_parent_inverse = g.matrix_world.inverted()
    return g
group('Bolt', (0, 0, BZ + 0.0035), ['bolt_body', 'cocking_piece', 'bolt_safety', 'bolt_arm', 'bolt_arm_2', 'bolt_knob'])
group('Trigger', (0, -0.040, -0.030), ['trigger'])
group('FloorPlate', (0, -0.040, -0.0285), ['floor_plate', 'trigger_guard'])

# ---------------- export + preview renders ----------------
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('MESH', 'EMPTY'): ob.select_set(True)
glb = os.path.join(OUT, 'mosin.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x = 1800; sc.render.resolution_y = 500
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.52, 0.58, 0.62)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.75
cam.location = (2.0, 0.24, -0.02); cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
sc.render.filepath = os.path.join(OUT, 'mosin_side.png'); bpy.ops.render.render(write_still=True)
sc.render.resolution_x = 1200; sc.render.resolution_y = 700; cam.data.ortho_scale = 1.15
cam.location = (1.2, -1.3, 0.55); cam.rotation_euler = (math.radians(72), 0, math.radians(42))
sc.render.filepath = os.path.join(OUT, 'mosin_view.png'); bpy.ops.render.render(write_still=True)
print('MOSIN DONE', glb)
