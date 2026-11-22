import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'props_1'
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
    bmesh.ops.delete(bm, geom=r['geom_interior'] + r['geom_unused'], context='VERTS')
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

# =============================================================== SANDBAG WALL (2.0 m long, 3 rows, ~0.5 m thick, ~0.76 m high)
def bag_geo(bm, c, rx, ry, rz, yaw, sub, matidx, fine, seed):
    r = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    vs = r['verts']; cy, sy_ = math.cos(yaw), math.sin(yaw)
    for v in vs:
        p = v.co.normalized()
        q = Vector((math.copysign(abs(p.x) ** 0.78, p.x), math.copysign(abs(p.y) ** 0.78, p.y), math.copysign(abs(p.z) ** 0.9, p.z)))   # squarer, pillow-like
        tip = max(0.0, abs(q.x) - 0.62)                                                      # the choked ends of the bag taper down
        q.z *= 1.0 - 1.3 * tip; q.y *= 1.0 - 0.45 * tip
        if q.z > 0: q.z *= 0.92                                                              # sagging top
        if fine: q *= 1.0 + 0.04 * noise.noise(p * 5.0 + Vector((seed, 0.2, 0.7)))
        x, y, z = q.x * rx, q.y * ry, q.z * rz
        v.co = Vector((c[0] + x * cy - y * sy_, c[1] + x * sy_ + y * cy, c[2] + z))
    vset = set(vs)
    for f in bm.faces:
        if all(v in vset for v in f.verts): f.material_index = matidx
    return vs

def sandbag_wall():
    rnd = random.Random(7)
    L = 2.0; RX, RY, RZ = 0.26, 0.205, 0.125
    plan = []                                                    # (x centre, row, half?)
    for row in range(3):
        if row % 2 == 0: xs = [-0.75, -0.25, 0.25, 0.75]; halves = []
        else: xs = [-0.5, 0.0, 0.5]; halves = [-0.875, 0.875]
        for x in xs: plan.append((x, row, False))
        for x in halves: plan.append((x, row, True))
    bmv = bmesh.new(); rows_hulls = [bmesh.new() for _ in range(3)]
    seed = 1.0
    for (x, row, half) in plan:
        seed += 1.7
        rx = RX * (0.5 if half else 1.0) * (1 + (rnd.random() - 0.5) * 0.08)
        rz = RZ * (1 - 0.05 * row); z0 = 0.125 * (1 - 0.05 * row) + sum(0.25 * (1 - 0.05 * k) for k in range(row)) * 0.96
        c = (x + (rnd.random() - 0.5) * 0.03, (rnd.random() - 0.5) * 0.05, z0)
        yaw = (rnd.random() - 0.5) * 0.22
        bag_geo(bmv, c, rx, RY, rz, yaw, 3, rnd.randrange(3), True, seed)
        bag_geo(rows_hulls[row], c, rx, RY, rz, yaw, 1, 0, False, seed)       # coarse copy of the same bag for the collision hull
    root = new_root('sandbag_wall')
    vis = to_obj('sandbag_wall', bmv, M_BAG, True)
    colbm = bmesh.new()
    for rh in rows_hulls:                                                       # one convex hull per row -> three stacked closed hulls
        tri_hull(rh); me = bpy.data.meshes.new('t'); rh.to_mesh(me); rh.free(); colbm.from_mesh(me); bpy.data.meshes.remove(me)
    col = to_obj('COL_sandbag_wall', colbm, [M_BAG[0]], False)
    finish(root, vis, col, 'sandbag_wall'); return root

# =============================================================== WOODEN CRATE (0.8 x 0.5 x 0.5)
def crate():
    W, D, H = 0.80, 0.50, 0.50
    bm = bmesh.new(); bmd = bmesh.new()
    box_geo(bmd, (0, 0, H / 2), (W - 0.03, D - 0.03, H - 0.03))                              # dark core seen through the gaps
    P = 0.055                                                                                # corner posts
    for sx in (-1, 1):
        for sy in (-1, 1): box_geo(bm, (sx * (W / 2 - P / 2), sy * (D / 2 - P / 2), H / 2), (P, P, H))
    T = 0.022; n = 4; bh = (H - 2 * 0.03) / n
    for k in range(n):                                                                       # horizontal slats on the four sides
        z = 0.03 + bh * (k + 0.5); h = bh - 0.012
        for sy in (-1, 1): box_geo(bm, (0, sy * (D / 2 - T / 2), z), (W - 2 * P + 0.004, T, h))
        for sx in (-1, 1): box_geo(bm, (sx * (W / 2 - T / 2), 0, z), (T, D - 2 * P + 0.004, h))
    for k in range(4):                                                                       # lid planks
        y = -D / 2 + 0.07 + k * (D - 0.14) / 3
        box_geo(bm, (0, y, H - 0.012), (W - 0.02, (D - 0.14) / 3 - 0.012 + 0.07 * 0.0 + 0.012, 0.024))
    for sx in (-1, 1): box_geo(bm, (sx * (W / 2 - 0.09), 0, H + 0.006), (0.07, D - 0.04, 0.022))      # end battens on the lid
    root = new_root('crate_wood')
    vis_w = to_obj('crate_wood', bm, [M_WOOD], False)
    vis_d = to_obj('crate_wood_core', bmd, [M_WOOD_D], False)
    # join core into the visible mesh (two materials)
    bpy.ops.object.select_all(action='DESELECT'); vis_w.select_set(True); vis_d.select_set(True); bpy.context.view_layer.objects.active = vis_w
    vis_w.data.materials.append(M_WOOD_D)
    for p in vis_d.data.polygons: p.material_index = 1
    bpy.ops.object.join(); vis = bpy.context.view_layer.objects.active; vis.name = 'crate_wood'
    cb = bmesh.new(); box_geo(cb, (0, 0, (H + 0.028) / 2), (W, D, H + 0.028))
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    col = to_obj('COL_crate_wood', cb, [M_WOOD], False)
    finish(root, vis, col, 'crate_wood'); return root

# ---------------------------------------------------------------- build the batch
rock('rock_boulder_a', 1.3, (0.95, 0.80, 0.70), 1.0, M_ROCK)
rock('rock_boulder_b', 5.7, (0.60, 0.55, 0.50), 1.0, M_ROCK2)
sandbag_wall()
crate()

# lay them out in a row (for the preview and so the file is readable); the game ignores the position and re-centres each prop
for i, r in enumerate(ROOTS): r.location = (i * 3.2, 0, 0)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True)
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
