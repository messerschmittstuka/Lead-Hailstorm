import bpy, bmesh, math, os
from mathutils import Vector

# ---- Bayonets, built in game units (1 unit = 1 m). Muzzle points +Y, up is +Z, bore axis at z=0.035. ----
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

WOOD  = wood_mat('arisaka_wood', (0.50, 0.23, 0.09), 47, 0.45)
WOOD2 = wood_mat('arisaka_dark', (0.36, 0.16, 0.06), 49, 0.5)
BLUED = mat('blued_steel', (0.075, 0.08, 0.09), 0.9, 0.4)
ARSENAL = mat('arsenal_steel', (0.30, 0.31, 0.33), 0.9, 0.4)
STEEL = mat('bright_steel', (0.46, 0.47, 0.5), 1.0, 0.28)
PARKER = mat('parkerised', (0.055, 0.06, 0.052), 0.7, 0.55)
BRASS = mat('brass', (0.55, 0.38, 0.1), 1.0, 0.3)

root = bpy.data.objects.new('Bayonets', None); bpy.context.collection.objects.link(root)

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


GRIPWOOD = mat('bayo_wood', (0.27, 0.13, 0.05), 0.0, 0.55)
BLACK = mat('bayo_black', (0.03, 0.03, 0.035), 0.1, 0.5)
# Every bayonet is built relative to the muzzle: origin = muzzle tip, +Y forward, bore axis at z=0, x to the right. Each type is an empty named bay_<type>.
groups = {}
def begin(): return set(bpy.data.objects)
def end(name, before):
    g = bpy.data.objects.new('bay_' + name, None); bpy.context.collection.objects.link(g); g.parent = root; groups[name] = g
    for o in set(bpy.data.objects) - before:
        if o is not g and o.parent is root: o.parent = g

def spike(name, L, r, cx, cz, y0=0.0):
    cyl_y(name, r, 0.0005, y0, L, cx, cz, STEEL, 4)

def knife(prefix, glen, grip_mat, blen, bh):
    cyl_y(prefix + '_ring', 0.0125, 0.0125, -0.004, 0.010, 0, 0, BLUED, 20)
    box(prefix + '_guard', 0.026, 0.006, 0.018, 0, 0.012, -0.0215, STEEL, 0.001)
    box(prefix + '_grip', 0.022, glen, 0.024, 0, 0.009 - glen / 2, -0.0225, grip_mat, 0.003)
    box(prefix + '_tang', 0.012, 0.014, 0.014, 0, -glen + 0.004, -0.0155, grip_mat, 0.001)
    zt = -0.0115; zb = zt - bh
    profile(prefix + '_blade', [(0.015, zb), (blen * 0.78, zb + 0.001), (blen, zb + bh * 0.55), (blen * 0.78, zt), (0.015, zt)], 0.0055, STEEL, 0.0008, 0)

def socket_spike(prefix, L, r):
    cyl_y(prefix + '_socket', 0.0118, 0.0118, -0.050, -0.002, 0, 0, STEEL, 20)
    box(prefix + '_arm', 0.016, 0.060, 0.008, 0.0125, -0.022, 0, BLUED, 0.001)
    spike(prefix + '_spike', L, r, 0.018, 0, -0.02)

b = begin(); socket_spike('mosin', 0.43, 0.0052); end('mosin', b)
b = begin(); knife('kar', 0.085, BLACK, 0.25, 0.022); end('kar98k', b)
b = begin(); knife('m03', 0.090, GRIPWOOD, 0.40, 0.024); end('m1903', b)
b = begin(); knife('svt', 0.085, GRIPWOOD, 0.23, 0.022); end('svt40', b)
b = begin(); knife('gar', 0.080, BLACK, 0.25, 0.022); end('garand', b)
b = begin()
box('mas_base', 0.014, 0.022, 0.012, 0, -0.006, -0.0195, BLUED, 0.001)
spike('mas_spike', 0.40, 0.0052, 0, -0.0195, -0.012)
end('mas36', b)
b = begin()
box('car_pivot', 0.014, 0.022, 0.012, 0, -0.004, -0.0205, BLUED, 0.001)
spike('car_spike', 0.18, 0.0046, 0, -0.0185, -0.008)
end('carcano', b)
b = begin(); socket_spike('rsc', 0.52, 0.0058); end('rsc17', b)
# Type 30 (Arisaka) with the hooked guard
b = begin()
box('ari_grip', 0.022, 0.080, 0.026, 0, -0.042, -0.0215, GRIPWOOD, 0.003)
box('ari_guard', 0.030, 0.008, 0.032, 0, 0.002, -0.0215, STEEL, 0.002)
box('ari_ring', 0.028, 0.012, 0.012, 0, -0.066, -0.0088, STEEL, 0.002)
rod('ari_hook1', (0.017, 0.004, -0.019), (0.017, 0.004, 0.013), 0.0026, STEEL)
rod('ari_hook2', (0.017, 0.004, 0.013), (0.017, -0.006, 0.023), 0.0026, STEEL)
rod('ari_hook3', (0.017, -0.006, 0.023), (0.017, -0.022, 0.022), 0.0026, STEEL)
profile('ari_blade', [(0.006, -0.0345), (0.34, -0.0315), (0.405, -0.0245), (0.35, -0.0135), (0.006, -0.0085)], 0.0062, STEEL, 0.0008, 0)
end('arisaka', b)

# ---------------- export + preview sheet ----------------
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('MESH', 'EMPTY'): ob.select_set(True)
glb = os.path.join(OUT, 'bayonets.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True)
for i, n in enumerate(groups):
    groups[n].location = (0, 0, -0.075 * i)
    rb = cyl_y('ref_' + n, 0.0088, 0.0088, -0.30, 0.0, 0, -0.075 * i, BLUED, 20)
    rb.parent = None
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
sc.render.resolution_x = 1800; sc.render.resolution_y = 1100
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.52, 0.58, 0.62)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.05
cam.location = (2.0, 0.12, -0.30); cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
sc.render.filepath = os.path.join(OUT, 'bayonets_sheet.png'); bpy.ops.render.render(write_still=True)
print('BAYONETS DONE', glb)
