import bpy, bmesh, math, os
from mathutils import Vector

# ---- Karabiner 98k, built in game units (1 unit = 1 m). Muzzle points +Y, up is +Z, bore axis at z=0.035. ----
MODELS = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')   # v1 = the Kar98k exactly as in build_kar98k2.py; no scene clearing, export or previews (lib_loop does that)

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

TEX = MODELS + '/textures/gun/'
_IMG = {}
def img(name, srgb=True):
    if name not in _IMG:
        im = bpy.data.images.load(TEX + name + '.jpg'); im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'; _IMG[name] = im
    return _IMG[name]
TILE = {}
def tmat(name, tex, rough, metal, nstr=1.0, tile=0.16):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex + '_c'); nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(tex + '_n', False)
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (0.3, 0.3, 0.3, 1); TILE[name] = tile
    return m
def mat(name, rgb, metal=0.0, rough=0.5):                     # fall-backs for anything still asking for a flat material
    return tmat(name, {'blued_steel': 'blued', 'bright_steel': 'steel', 'parkerised': 'parker', 'brass': 'steel'}.get(name, 'steel'), rough, metal)
WOOD  = tmat('walnut', 'walnut', 0.45, 0.0, 0.3)
WOOD2 = WOOD
BLUED = tmat('blued_steel', 'blued', 0.5, 0.55, 0.15)
STEEL = tmat('bright_steel', 'steel', 0.5, 0.55, 0.25)
PARKER = tmat('parkerised', 'parker', 0.6, 0.45, 0.25)
BRASS = tmat('brass', 'steel', 0.3, 0.9, 0.4)

root = bpy.data.objects.new('Kar98k', None); bpy.context.collection.objects.link(root)

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

BZ = 0.035            # bore height
# ---------------- stock + forend: one outline, side view (y along the gun, z up) ----------------
# game z -> -y here. Butt at -0.375, forend tip at +0.60.
stock_pts = [
    # top line: forend flush with the barrel, shoulder round the receiver, dipping wrist, low comb, heel
    (0.575, 0.050), (0.46, 0.052), (0.30, 0.052), (0.154, 0.052), (0.10, 0.047), (0.0, 0.045), (-0.068, 0.0352),
    (-0.094, 0.0306), (-0.125, 0.0238), (-0.165, 0.0124), (-0.222, 0.010), (-0.273, 0.0044), (-0.324, -0.0035), (-0.372, -0.0103),
    # butt face to toe
    (-0.378, -0.060), (-0.373, -0.1266),
    # underside: sweeping toe line, pistol-grip swell, rise to the trigger guard, forend underside
    (-0.324, -0.1095), (-0.273, -0.081), (-0.222, -0.0639), (-0.165, -0.0582), (-0.125, -0.0559), (-0.102, -0.0468), (-0.085, -0.033),
    (-0.068, -0.0296), (-0.017, -0.0296), (0.020, -0.026), (0.063, -0.0148), (0.154, 0.0044), (0.29, 0.0193), (0.461, 0.0204), (0.575, 0.019)
]
def loft_stock():
    """round-section walnut stock lofted along its length from the side outline: rounded top, full cheeks, narrow wrist, belly swell"""
    top = sorted(stock_pts[0:14], key=lambda p: p[0]); bot = sorted(stock_pts[15:], key=lambda p: p[0])
    ty = [p[0] for p in top]; tz = [p[1] for p in top]; by = [p[0] for p in bot]; bz = [p[1] for p in bot]
    wy = [-0.374, -0.30, -0.22, -0.15, -0.10, -0.04, 0.05, 0.16, 0.35, 0.50, 0.575]; ww = [0.044, 0.042, 0.038, 0.034, 0.035, 0.040, 0.041, 0.040, 0.034, 0.031, 0.030]
    N = 32; S = 120; ys = [-0.374 + (0.575 + 0.374) * i / (S - 1) for i in range(S)]
    me = bpy.data.meshes.new('stock'); ob = bpy.data.objects.new('stock', me); bpy.context.collection.objects.link(ob)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify(); rings = []
    for y in ys:
        zt = float(np.interp(y, ty, tz)); zb = float(np.interp(y, by, bz)); hw = float(np.interp(y, wy, ww)) / 2
        zc = (zt + zb) / 2; hh = (zt - zb) / 2; p = 3.0 if y < 0.15 else 2.6
        ring = []
        for k in range(N):
            a = 2 * math.pi * k / N; c = math.cos(a); sn = math.sin(a)
            x = hw * math.copysign(abs(c) ** (2 / p), c)
            z = zc + hh * math.copysign(abs(sn) ** (2 / p), sn) * (0.96 if sn < 0 else 1.0)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for i in range(S - 1):
        for k in range(N):
            k2 = (k + 1) % N
            f = bm.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][k2], rings[i][k2])); f.smooth = True
            u0 = i / (S - 1); u1 = (i + 1) / (S - 1); v0 = k / N; v1 = (k + 1) / N
            for l, uv in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))): l[uvl].uv = uv
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(ring[::-1] if flip else ring); f.smooth = False
        for l in f.loops: l[uvl].uv = (0.0 if flip else 1.0, 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.materials.append(WOOD); ob.parent = root
    for pl in me.polygons: pl.use_smooth = True
    return ob
loft_stock()

# butt plate and its toe, sling disc, grip cap
profile('butt_plate', [(-0.366, -0.008), (-0.380, -0.060), (-0.377, -0.130), (-0.369, -0.129), (-0.372, -0.060), (-0.358, -0.010)], 0.043, BLUED, 0.0015, 1)
box('butt_screw_t', 0.007, 0.004, 0.007, 0, -0.381, -0.030, STEEL, 0.0006)
box('butt_screw_b', 0.007, 0.004, 0.007, 0, -0.378, -0.105, STEEL, 0.0006)
cyl_x('sling_disc_L', 0.0165, -0.0225, -0.0185, -0.262, -0.040, STEEL)
cyl_x('sling_disc_R', 0.0165, 0.0185, 0.0225, -0.262, -0.040, STEEL)
box('grip_cap', 0.030, 0.030, 0.011, 0, -0.118, -0.0585, BLUED, 0.002)

# ---------------- barrel, tapered, with muzzle crown ----------------
cyl_y('barrel', 0.0148, 0.0102, 0.12, 0.73, 0, BZ, BLUED)
torus_y('muzzle_crown', 0.0108, 0.0016, 0.730, 0, BZ, STEEL)
# chamber / receiver ring and receiver body
cyl_y('receiver_ring', 0.0185, 0.0185, 0.075, 0.135, 0, BZ, BLUED)
cyl_y('receiver', 0.0185, 0.0185, -0.085, 0.080, 0, BZ, BLUED, 30)
box('receiver_floor', 0.032, 0.17, 0.020, 0, -0.005, 0.016, BLUED)
box('receiver_bridge', 0.022, 0.030, 0.012, 0, 0.03, 0.057, BLUED)          # rear bridge over the bolt way
box('clip_guide', 0.016, 0.07, 0.004, 0, 0.012, 0.0605, BLUED)             # stripper clip guide
box('safety_wing', 0.006, 0.022, 0.010, 0, -0.105, 0.034, BLUED)           # wing safety on the cocking piece

box('rear_tang', 0.018, 0.060, 0.012, 0, -0.112, 0.0455, BLUED, 0.0035)                 # receiver tang behind the bolt
for i, y in enumerate((-0.058, -0.040, -0.022)):
    torus_y('bolt_ring_%d' % i, 0.0112, 0.0012, y, 0, BZ + 0.0035, STEEL)                  # grooves on the bolt body
box('bolt_stop', 0.007, 0.020, 0.008, -0.0215, 0.040, 0.026, BLUED, 0.0006)              # bolt stop on the left
# removed (read as floating specks from behind): cyl_x('stock_screw_a', 0.0042, 0.0170, 0.0215, 0.020, 0.036, STEEL, 12)                   # action screws through the stock
# removed (read as floating specks from behind): cyl_x('stock_screw_b', 0.0042, 0.0190, 0.0235, -0.075, 0.020, STEEL, 12)
# ---------------- bolt ----------------
cyl_y('bolt_body', 0.0108, 0.0108, -0.075, 0.020, 0, BZ + 0.0035, STEEL)
cyl_y('cocking_piece', 0.0080, 0.0100, -0.125, -0.080, 0, BZ + 0.0035, STEEL)
rod('bolt_arm', (0.008, -0.012, BZ + 0.004), (0.048, -0.020, 0.018), 0.0052, STEEL)
rod('bolt_arm_2', (0.048, -0.020, 0.018), (0.060, -0.030, 0.004), 0.0052, STEEL)
ball('bolt_knob', 0.0118, (0.0625, -0.032, 0.0), STEEL)

# ---------------- trigger guard, floor plate, trigger ----------------
box('floor_plate', 0.034, 0.075, 0.008, 0, -0.003, -0.0285, PARKER, 0.0015)

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
curve_tube('trigger_guard', [(-0.082, -0.028), (-0.072, -0.056), (-0.040, -0.067), (-0.005, -0.060), (0.016, -0.024)], 0.0036, PARKER)
box('trigger', 0.006, 0.006, 0.030, 0, -0.040, -0.044, STEEL, 0.0008)

# ---------------- barrel band, nose cap, bayonet lug, cleaning rod tip ----------------
cyl_y('band', 0.0182, 0.0182, 0.455, 0.468, 0, 0.0355, STEEL, 32, 0.0012)
cyl_y('nose_cap', 0.0190, 0.0172, 0.557, 0.592, 0, 0.0335, STEEL, 32, 0.0015)
box('bayonet_lug', 0.016, 0.022, 0.010, 0, 0.5745, 0.058, STEEL, 0.001)
rod('cleaning_rod_tip', (0, 0.560, 0.0125), (0, 0.610, 0.0125), 0.0045, STEEL)

# ---------------- front sight: base on the barrel, post, hood (tip of the post at z = 0.088) ----------------
box('fs_base', 0.018, 0.032, 0.012, 0, 0.700, 0.0462, BLUED, 0.001)
box('fs_post', 0.0034, 0.004, 0.040, 0, 0.700, 0.0685, BLUED, 0.0004)
for sx in (-1, 1):
    box('fs_hood_leg', 0.0036, 0.016, 0.020, sx * 0.0100, 0.700, 0.0605, BLUED, 0.0006)
torus_y('fs_hood_f', 0.0108, 0.0020, 0.7085, 0, 0.0765, BLUED)
torus_y('fs_hood_b', 0.0108, 0.0020, 0.6915, 0, 0.0765, BLUED)
box('fs_hood_top', 0.0044, 0.019, 0.0036, 0, 0.700, 0.0878, BLUED, 0.0005)

# ---------------- rear sight: base on the handguard + tangent leaf with a V notch (centre of the notch at z = 0.088) ----------------
box('rs_base', 0.034, 0.075, 0.012, 0, 0.275, 0.058, BLUED, 0.0012)
box('rs_slider', 0.024, 0.014, 0.014, 0, 0.275, 0.071, STEEL, 0.001)
def poly_xz(name, pts, thick, y, m):
    """flat plate cut from an outline in the x-z plane (front view), thickness along y"""
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    bm = bmesh.new(); vs = [bm.verts.new((x, y - thick / 2, z)) for x, z in pts]; f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f]); vv = [v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, thick, 0), verts=vv); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free(); me.materials.append(m); ob.parent = root
    md = ob.modifiers.new('bev', 'BEVEL'); md.width = 0.0004; md.segments = 1; md.limit_method = 'ANGLE'
    return ob
# tangent leaf: one plate with the real V notch, apex on the line of sight (z = 0.088), top edge a little above it
poly_xz('rs_leaf', [(-0.0135, 0.0585), (0.0135, 0.0585), (0.0135, 0.0935), (0.0058, 0.0935), (0.0, 0.0880), (-0.0058, 0.0935), (-0.0135, 0.0935)], 0.004, 0.272, BLUED)
box('rs_leaf_ramp', 0.026, 0.010, 0.006, 0, 0.268, 0.0612, BLUED, 0.0008)          # the leaf's hinge block on the ramp
for i, dz in enumerate((0.066, 0.072, 0.078)):                                      # range graduations along the leaf's back edge
    box('rs_tick_%d' % i, 0.004, 0.0012, 0.0010, 0.0105, 0.2695, dz, STEEL, 0)

# ---------------- screws, swivel, small details ----------------
for x in (-0.0195, 0.0195):
    for y in (-0.05, 0.05):
        cyl_x('screw', 0.0038, x, x + (0.003 if x > 0 else -0.003), y, 0.0, STEEL, 12)
box('sling_swivel', 0.016, 0.008, 0.014, 0, 0.485, 0.014, STEEL, 0.0006)


# ---------------- rig: functional groups with proper pivots (for reload / bolt / sight animation) ----------------
def group(name, pivot, members):
    g = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(g)
    g.parent = root; g.location = pivot
    bpy.context.view_layer.update()
    for n in members:
        for ob in [o for o in bpy.data.objects if o.type == 'MESH' and (o.name == n or o.name.startswith(n + '.'))]:
            ob.parent = g; ob.matrix_parent_inverse = g.matrix_world.inverted()
    return g
# Bolt pivot sits on the bore axis: slide along Y to cycle, rotate about Y to lift the handle
group('Bolt', (0, 0, BZ + 0.0035), ['bolt_body', 'bolt_ring_0', 'bolt_ring_1', 'bolt_ring_2', 'cocking_piece', 'bolt_arm', 'bolt_arm_2', 'bolt_knob', 'safety_wing'])
group('Trigger', (0, -0.040, -0.030), ['trigger'])
group('RearSight', (0, 0.275, 0.058), ['rs_slider', 'rs_leaf', 'rs_leaf_ramp', 'rs_tick_0', 'rs_tick_1', 'rs_tick_2'])
group('FloorPlate', (0, -0.040, -0.0285), ['floor_plate', 'trigger_guard'])

# ---------------- UVs: metal parts get box-projected world-metre UVs (the stock has its own, lofted) ----------------
bpy.context.view_layer.update()
for ob in bpy.data.objects:
    if ob.type != 'MESH' or ob.name == 'stock': continue
    me = ob.data; mn = me.materials[0].name if me.materials else ''
    T = TILE.get(mn, 0.16); uvl = me.uv_layers.active or me.uv_layers.new(name='UVMap'); M = ob.matrix_world; R = M.to_3x3()
    for poly in me.polygons:
        n = R @ poly.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            p = M @ me.vertices[me.loops[li].vertex_index].co
            u, v = ((p.y, p.z) if ax == 0 else (p.x, p.z) if ax == 1 else (p.x, p.y))
            uvl.data[li].uv = (u / T, v / T)

