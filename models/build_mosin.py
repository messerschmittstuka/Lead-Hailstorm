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

WOOD  = wood_mat('birch', (0.80, 0.40, 0.15), 11, 0.42)
WOOD2 = wood_mat('birch_dark', (0.52, 0.24, 0.09), 13, 0.5)
BLUED = mat('blued_steel', (0.075, 0.08, 0.09), 0.9, 0.4)
ARSENAL = mat('arsenal_steel', (0.30, 0.31, 0.33), 0.9, 0.4)
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

BZ = 0.035            # bore height. Outline traced from the user's photo (scale: butt y=-0.41, muzzle y=+0.88)
top = [(0.78, 0.048), (0.749, 0.049), (0.663, 0.049), (0.513, 0.049), (0.385, 0.048), (0.342, 0.048), (0.299, 0.046), (0.23, 0.042), (0.17, 0.044), (0.107, 0.042),
       (0.04, 0.036), (0.0, 0.041), (-0.049, 0.039), (-0.066, 0.036), (-0.083, 0.026), (-0.1, 0.014), (-0.117, 0.008), (-0.135, 0.001), (-0.17, -0.003),
       (-0.203, 0.002), (-0.254, 0.001), (-0.289, 0.001), (-0.323, -0.004), (-0.357, -0.006), (-0.39, -0.011), (-0.405, -0.008)]
under = [(-0.409, -0.115), (-0.357, -0.121), (-0.323, -0.106), (-0.289, -0.098), (-0.254, -0.086), (-0.22, -0.075), (-0.186, -0.062), (-0.152, -0.052), (-0.117, -0.043),
         (-0.083, -0.031), (-0.049, -0.019), (0.0, -0.012), (0.064, -0.011), (0.149, -0.015), (0.192, -0.011), (0.256, -0.004), (0.299, -0.001), (0.321, 0.008),
         (0.385, 0.009), (0.47, 0.009), (0.513, 0.014), (0.599, 0.014), (0.663, 0.015), (0.749, 0.018), (0.78, 0.024)]
stock_pts = top + under
st = profile('stock', stock_pts, 0.042, WOOD, 0.003, 1, taper=lambda y: 1.0 if y < 0.28 else max(0.78, 1.0 - 0.22 * min(1.0, (y - 0.28) / 0.5)))

def cut_slot(target, name, cy, cz, L, Hh):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, cy, cz))
    c = bpy.context.active_object; c.name = 'cutter_' + name; c.scale = (0.12, L, Hh)
    bpy.ops.object.transform_apply(scale=True)
    bv = c.modifiers.new('r', 'BEVEL'); bv.width = Hh * 0.45; bv.segments = 6; bv.limit_method = 'NONE'
    c.display_type = 'WIRE'; c.hide_render = True
    md = target.modifiers.new('cut_' + name, 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = c; md.solver = 'EXACT'
cut_slot(st, 'butt', -0.24, -0.045, 0.040, 0.013)       # sling slot through the butt
cut_slot(st, 'fore', 0.575, 0.029, 0.040, 0.013)        # sling slot through the forend

profile('butt_plate', [(-0.4055, -0.0075), (-0.4105, -0.060), (-0.4100, -0.1155), (-0.4075, -0.1155), (-0.4080, -0.060), (-0.4035, -0.0075)], 0.041, BLUED, 0.0008, 0)

# barrel, receiver, tang
cyl_y('barrel', 0.0148, 0.0092, 0.12, 0.88, 0, BZ, BLUED)
torus_y('muzzle_crown', 0.0094, 0.0014, 0.88, 0, BZ, ARSENAL)
cyl_y('receiver_ring', 0.0148, 0.0148, 0.075, 0.20, 0, BZ, ARSENAL)
cyl_y('receiver', 0.0135, 0.0135, -0.060, 0.080, 0, BZ, ARSENAL, 30)
box('receiver_floor', 0.030, 0.16, 0.016, 0, -0.005, 0.018, ARSENAL)
box('clip_guide', 0.026, 0.07, 0.005, 0, 0.0, 0.0495, ARSENAL)
for x in (-0.0185, 0.0185):
    for y in (-0.03, 0.12):
        cyl_x('screw', 0.0036, x, x + (0.0025 if x > 0 else -0.0025), y, 0.0, ARSENAL, 12)

# bolt: bright steel body, cocking-piece knob rising behind the receiver, handle swept out and down with a ball knob
cyl_y('bolt_body', 0.0105, 0.0105, -0.058, 0.045, 0, BZ + 0.0035, STEEL)
cyl_y('cocking_piece', 0.0092, 0.0082, -0.075, -0.05, 0, BZ + 0.0035, STEEL)
rod('cocking_stem', (0, 0.014, BZ + 0.004), (0, 0.014, 0.056), 0.0048, STEEL)
ball('cocking_knob', 0.0078, (0, 0.014, 0.0615), STEEL)
rod('bolt_arm', (0.008, -0.010, BZ + 0.0035), (0.052, -0.018, 0.030), 0.0050, STEEL)
rod('bolt_arm_2', (0.052, -0.018, 0.030), (0.062, -0.028, 0.012), 0.0050, STEEL)
ball('bolt_knob', 0.0112, (0.0635, -0.030, 0.004), STEEL)
kn = bpy.data.objects.new('Knob', None); bpy.context.collection.objects.link(kn); kn.parent = root; kn.location = (0.0635, -0.030, 0.004)

# floor plate flush under the stock, guard bow behind it, trigger
box('floor_plate', 0.030, 0.145, 0.024, 0, 0.058, -0.0235, STEEL, 0.0012)      # the magazine box and floor plate, silver like the photo
box('guard_strap', 0.012, 0.17, 0.004, 0, 0.215, -0.0045, STEEL, 0.0005)
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
curve_tube('trigger_guard', [(-0.072, -0.016), (-0.066, -0.040), (-0.045, -0.054), (-0.026, -0.044), (-0.014, -0.018)], 0.0032, STEEL)
box('trigger', 0.005, 0.005, 0.026, 0, -0.040, -0.034, STEEL, 0.0006)

# bands, nose cap, muzzle collar
for i, y in enumerate((0.32, 0.685)):
    box('band_%d' % i, 0.043 if i == 0 else 0.040, 0.008, 0.044, 0, y, 0.0285, BLUED, 0.001)
    box('swivel_%d' % i, 0.006, 0.010, 0.012, 0.0215 if i == 0 else 0.0195, y, 0.022, STEEL, 0.0005)
box('nose_cap', 0.033, 0.018, 0.036, 0, 0.775, 0.0345, BLUED, 0.001)
cyl_y('muzzle_collar', 0.0108, 0.0108, 0.835, 0.855, 0, BZ, BLUED)

# rig: bolt, trigger, floor plate groups with pivots
def group(name, pivot, members):
    g = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(g)
    g.parent = root; g.location = pivot
    bpy.context.view_layer.update()
    for n in members:
        for ob in [o for o in bpy.data.objects if o.type == 'MESH' and (o.name == n or o.name.startswith(n + '.'))]:
            ob.parent = g; ob.matrix_parent_inverse = g.matrix_world.inverted()
    return g
group('Bolt', (0, 0, BZ + 0.0035), ['bolt_body', 'cocking_piece', 'cocking_stem', 'cocking_knob', 'bolt_arm', 'bolt_arm_2', 'bolt_knob'])
group('Trigger', (0, -0.040, -0.030), ['trigger'])
group('FloorPlate', (0, -0.040, -0.0285), ['floor_plate', 'trigger_guard'])

# ---------------- export + preview renders ----------------
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('MESH', 'EMPTY') and not ob.name.startswith('cutter'): ob.select_set(True)
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
