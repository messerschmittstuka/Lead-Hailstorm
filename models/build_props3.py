import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'props_3'
os.makedirs(OUT, exist_ok=True)

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
    for b in list(blk):
        if b.users == 0: blk.remove(b)

def mat(name, rgb, rough=0.9, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1)
    return m

M_ROCK = mat('rock', (0.30, 0.28, 0.25), 0.95)
M_ROCK2 = mat('rock_dark', (0.20, 0.19, 0.18), 0.95)
M_BAG = [mat('bag_a', (0.43, 0.37, 0.26), 1.0), mat('bag_b', (0.36, 0.31, 0.22), 1.0), mat('bag_c', (0.48, 0.42, 0.30), 1.0)]
M_WOOD = mat('wood', (0.32, 0.20, 0.10), 0.85)
M_WOOD_D = mat('wood_dark', (0.14, 0.09, 0.05), 0.9)
M_METAL = mat('metal', (0.12, 0.12, 0.11), 0.6, 0.6)

ROOTS = []; STATS = []

def to_obj(name, bm, mats, smooth):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    if smooth: me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob

def new_root(name):
    r = bpy.data.objects.new('prop_' + name, None); bpy.context.scene.collection.objects.link(r)
    r.empty_display_type = 'PLAIN_AXES'; ROOTS.append(r); return r

def finish(root, vis, col, name):
    vis.parent = root; col.parent = root
    STATS.append((name, len(vis.data.polygons), len(col.data.polygons)))

def tri_hull(bm):
    """closed triangle convex hull of every vertex in bm (collision for convex-ish shapes)"""
    r = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    bmesh.ops.delete(bm, geom=list(set(r['geom_interior']) | set(r['geom_unused'])), context='VERTS')
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

def box_geo(bm, c, s, rot=0.0, bevel=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=Vector(s), verts=vs)
    if rot: bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=__import__('mathutils').Matrix.Rotation(rot, 3, 'Z'), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(c), verts=vs)
    return vs

# =============================================================== ROCKS
# A rock's big shape is a low-frequency noise on a sphere (that is what COL_ follows); the visible mesh adds small bumps on top (+-2 cm).
def rock(name, seed, size, squash, mat_main, sub_vis=4, sub_col=2):
    sx, sy, sz = size
    def shape(p, fine):
        n = noise.noise(p * 1.25 + Vector((seed, seed * 0.7, seed * 1.3)))
        r = 1.0 + 0.32 * n
        if fine: r += 0.035 * noise.noise(p * 7.0 + Vector((seed * 2.1, 3.3, seed)))
        q = p * r; q.x *= sx; q.y *= sy; q.z *= sz * squash
        return q
    def build(sub, fine):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        for v in bm.verts: v.co = shape(v.co.normalized(), fine)
        zmin = -0.38 * sz * squash                                  # flat bottom: the rock sits in the ground
        for v in bm.verts:
            if v.co.z < zmin: v.co.z = zmin
        for v in bm.verts: v.co.z -= zmin
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        return bm
    root = new_root(name)
    vis = to_obj(name, build(sub_vis, True), [mat_main], True)
    colbm = build(sub_col, False)
    col = to_obj('COL_' + name, colbm, [M_ROCK], False)
    finish(root, vis, col, name); return root

from mathutils import Matrix
M_STEEL = mat('rusty_steel', (0.20, 0.12, 0.08), 0.7, 0.5)
M_WIREM = mat('wire', (0.10, 0.09, 0.08), 0.5, 0.8)
M_CONCRETE = mat('concrete', (0.42, 0.41, 0.39), 0.95)
M_PLANK = mat('plank', (0.36, 0.27, 0.17), 0.9)
M_PLANK_D = mat('plank_dark', (0.22, 0.16, 0.10), 0.9)

def tube(bm, pts, r, sides=6, closed=False):
    """a thin round bar swept along a polyline"""
    rings = []; n = len(pts)
    for i, p in enumerate(pts):
        a = pts[(i + 1) % n] if (closed or i < n - 1) else p; b = pts[(i - 1) % n] if (closed or i > 0) else p
        d = (a - b).normalized(); t = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(t).normalized(); w = d.cross(u).normalized()
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)])
    for i in range(n - (0 if closed else 1)):
        A = rings[i]; B = rings[(i + 1) % n]
        for k in range(sides):
            j = (k + 1) % sides; bm.faces.new((A[k], A[j], B[j], B[k]))

def closed_box(bm, c, s, m=None):
    vs = box_geo(bm, c, s)
    if m is not None:
        for v in vs: v.co = m @ v.co
    return vs

# =============================================================== BARBED WIRE COIL (concertina, 3 m long, 0.9 m across, lying on the ground)
def wire_coil():
    L = 3.0; R = 0.45; rings = 11; bm = bmesh.new(); rnd = random.Random(4)
    for i in range(rings):
        x = -L / 2 + L * i / (rings - 1); sq = 1 + (rnd.random() - 0.5) * 0.05
        pts = [Vector((x + 0.03 * math.sin(a * 2), math.cos(a) * R * sq, R + math.sin(a) * R * sq)) for a in [2 * math.pi * k / 20 for k in range(20)]]
        tube(bm, pts, 0.007, 5, True)
    for k in range(5):                                                     # long wires running down the coil
        a = 2 * math.pi * k / 5 + 0.3
        tube(bm, [Vector((-L / 2 + L * i / 40, math.cos(a + i * 0.02) * R * 0.97, R + math.sin(a + i * 0.02) * R * 0.97)) for i in range(41)], 0.005, 4, False)
    for i in range(rings):                                                 # barbs: tiny crossed spikes on the rings
        x = -L / 2 + L * i / (rings - 1)
        for k in range(6):
            a = 2 * math.pi * k / 6 + i * 0.6; p = Vector((x, math.cos(a) * R, R + math.sin(a) * R)); o = Vector((0, -math.sin(a), math.cos(a)))
            tube(bm, [p - o * 0.03, p + o * 0.03], 0.003, 3, False); tube(bm, [p - Vector((1, 0, 0)) * 0.03, p + Vector((1, 0, 0)) * 0.03], 0.003, 3, False)
    root = new_root('wire_coil'); vis = to_obj('wire_coil', bm, [M_WIREM], False)
    cb = bmesh.new()                                                       # the coil is round: a 10-sided prism (touches the real wire on every ring)
    for i in (0, 1):
        x = -L / 2 + L * i
        ring = [cb.verts.new((x, math.cos(2 * math.pi * k / 10) * (R + 0.01), R + math.sin(2 * math.pi * k / 10) * (R + 0.01))) for k in range(10)]
        if i == 0: r0 = ring
        else: r1 = ring
    for k in range(10):
        j = (k + 1) % 10; cb.faces.new((r0[k], r0[j], r1[j], r1[k]))
    cb.faces.new(r0[::-1]); cb.faces.new(r1)
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    col = to_obj('COL_wire_coil', cb, [M_WIREM], False); col['bullet_pass'] = 1     # wire stops people, not bullets
    finish(root, vis, col, 'wire_coil'); return root

# =============================================================== CZECH HEDGEHOG (three 1.5 m steel beams crossed at right angles, resting on three tips)
def hedgehog():
    L = 1.5; B = 0.10
    m = Vector((1, 1, 1)).rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
    zc = L / (2 * math.sqrt(3)) + 0.0
    bm = bmesh.new(); cb = bmesh.new()
    lift = Matrix.Translation((0, 0, zc + 0.0)) @ m
    for ax in range(3):
        s = [B, B, B]; s[ax] = L
        for tgt, inset in ((bm, 0.0), (cb, 0.0)):
            vs = box_geo(tgt, (0, 0, 0), s)
            for v in vs: v.co = lift @ v.co
    # drop so the lowest corner sits exactly on z=0
    for tgt in (bm, cb):
        zm = min(v.co.z for v in tgt.verts)
        for v in tgt.verts: v.co.z -= zm
    for f in bm.faces: pass
    # angle-iron look: a shallow groove cut along each beam is skipped on purpose (the collision follows the real beam)
    for tgt in (bm, cb):
        bmesh.ops.recalc_face_normals(tgt, faces=list(tgt.faces))
    bmesh.ops.triangulate(cb, faces=list(cb.faces))
    root = new_root('hedgehog'); vis = to_obj('hedgehog', bm, [M_STEEL], False)
    col = to_obj('COL_hedgehog', cb, [M_STEEL], False)
    finish(root, vis, col, 'hedgehog'); return root

# =============================================================== WOODEN FENCE SECTION (2.4 m, three posts, two rails, pickets)
def fence():
    Lx = 2.4; bm = bmesh.new(); bmd = bmesh.new(); rnd = random.Random(11)
    for x in (-Lx / 2, 0.0, Lx / 2): box_geo(bm, (x, 0, 0.58), (0.10, 0.10, 1.16))              # posts
    for z in (0.35, 0.80): box_geo(bm, (0, 0.0, z), (Lx, 0.04, 0.06))                         # rails
    n = 11
    for i in range(n):                                                                         # pickets, a little uneven, slightly gapped
        x = -Lx / 2 + 0.12 + i * (Lx - 0.24) / (n - 1); h = 0.95 + (rnd.random() - 0.5) * 0.06
        box_geo(bmd, (x, 0.04, h / 2 + 0.05), (0.095, 0.02, h))
    root = new_root('fence_wood'); vp = to_obj('fence_wood', bm, [M_PLANK_D], False); vq = to_obj('fence_wood_pickets', bmd, [M_PLANK], False)
    bpy.ops.object.select_all(action='DESELECT'); vp.select_set(True); vq.select_set(True); bpy.context.view_layer.objects.active = vp
    vp.data.materials.append(M_PLANK)
    for p in vq.data.polygons: p.material_index = 1
    bpy.ops.object.join(); vis = bpy.context.view_layer.objects.active; vis.name = 'fence_wood'
    cb = bmesh.new()
    for x in (-Lx / 2, 0.0, Lx / 2): box_geo(cb, (x, 0, 0.58), (0.10, 0.10, 1.16))
    box_geo(cb, (0, 0.025, 0.52), (Lx - 0.10, 0.07, 0.94))                                    # the picket panel between the posts (gaps between pickets ignored)
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    col = to_obj('COL_fence_wood', cb, [M_PLANK], False)
    finish(root, vis, col, 'fence_wood'); return root

# =============================================================== DRAGON'S TOOTH (concrete tank trap, 0.9 base, 0.35 top, 0.85 high)
def dragons_tooth():
    rnd = random.Random(5); bm = bmesh.new()
    def frus(tgt, jit):
        bs = 0.45; ts = 0.17; H = 0.85
        base = [tgt.verts.new((sx * bs, sy * bs, 0.0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        top = [tgt.verts.new((sx * ts + (0.03 if jit else 0), sy * ts, H - (rnd.random() * 0.03 if jit else 0))) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for i in range(4):
            j = (i + 1) % 4; tgt.faces.new((base[i], base[j], top[j], top[i]))
        tgt.faces.new(base[::-1]); tgt.faces.new(top)
        bmesh.ops.recalc_face_normals(tgt, faces=list(tgt.faces))
    frus(bm, False)
    cb = bmesh.new(); frus(cb, False); bmesh.ops.triangulate(cb, faces=list(cb.faces))
    root = new_root('dragons_tooth'); vis = to_obj('dragons_tooth', bm, [M_CONCRETE], False)
    col = to_obj('COL_dragons_tooth', cb, [M_CONCRETE], False)
    finish(root, vis, col, 'dragons_tooth'); return root

# ---------------------------------------------------------------- build the batch
wire_coil(); hedgehog(); fence(); dragons_tooth()

# lay them out in a row (for the preview and so the file is readable); the game ignores the position and re-centres each prop
for i, r in enumerate(ROOTS): r.location = (i * 3.2, 0, 0)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True)
print('PROPS EXPORTED', os.path.getsize(glb), 'bytes')
for n, v, c in STATS: print('  %-18s visible %5d tris   collision %4d tris' % (n, v, c))

# ---------------------------------------------------------------- verify every collision mesh: closed (no open edges), within its prop's bounds
def verify():
    for r in ROOTS:
        for ch in r.children:
            if not ch.name.startswith('COL_'): continue
            bm = bmesh.new(); bm.from_mesh(ch.data)
            open_e = sum(1 for e in bm.edges if not e.is_manifold)
            xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
            print('  %-22s closed=%s  size %.2f x %.2f x %.2f  zmin %.3f' % (ch.name, open_e == 0, max(xs) - min(xs), max(ys) - min(ys), max(zs), min(zs)))
            bm.free()
verify()

# ---------------------------------------------------------------- previews: solid, and with the collision meshes drawn as red wire cages
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
sc.render.resolution_x = 1900; sc.render.resolution_y = 620
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.55, 0.62, 0.68)
bpy.ops.mesh.primitive_plane_add(size=60, location=(5, 0, -0.001)); gp = bpy.context.object; gp.data.materials.append(mat('ground', (0.22, 0.26, 0.15), 1.0))
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 38
def shot(fname, cx, dist, h, az, zt):
    a = math.radians(az); cam.location = (cx + math.sin(a) * dist, -math.cos(a) * dist, h)
    cam.rotation_euler = (Vector((cx, 0, zt)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, fname); bpy.ops.render.render(write_still=True)
cx = (len(ROOTS) - 1) * 3.2 / 2
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 17.0, 6.0, 14, 0.4)
wm = mat('colred', (1.0, 0.08, 0.08), 0.5)
def cage(src):
    """collision mesh drawn as thin red bars along every edge (robust, unlike the wireframe modifier on sliver triangles)"""
    bm = bmesh.new(); bm.from_mesh(src.data); mw = src.matrix_world
    out = bmesh.new(); R = 0.009
    for e in bm.edges:
        a_ = mw @ e.verts[0].co; b_ = mw @ e.verts[1].co; d = b_ - a_
        if d.length < 1e-5: continue
        z = d.normalized(); t = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
        x = z.cross(t).normalized() * R; y = z.cross(x).normalized() * R
        vs = [out.verts.new(p + o) for p in (a_, b_) for o in (x + y, x - y, -x - y, -x + y)]
        for i in range(4):
            j = (i + 1) % 4; out.faces.new((vs[i], vs[j], vs[4 + j], vs[4 + i]))
    bm.free(); ob = to_obj('cage_' + src.name, out, [wm], False); return ob
cages = [cage(ob) for ob in list(bpy.data.objects) if ob.name.startswith('COL_')]
shot(BATCH + '_col.png', cx, 17.0, 6.0, 14, 0.4)
print('PROPS DONE')
