import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'veg_1'
os.makedirs(OUT, exist_ok=True)

for _ob in list(bpy.data.objects): bpy.data.objects.remove(_ob, do_unlink=True)
for _c in list(bpy.data.collections): bpy.data.collections.remove(_c)
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

# =============================================================== VEGETATION (winter, 1942: bare, burnt and broken trees, scrub, dry grass, reeds, one young spruce)
from mathutils import Matrix
M_BARK = mat('bark', (0.17, 0.135, 0.105), 1.0)
M_CHAR = mat('bark_charred', (0.06, 0.052, 0.047), 1.0)
M_SPLIT = mat('wood_split', (0.46, 0.37, 0.26), 0.95)
M_TWIG = mat('twig', (0.21, 0.165, 0.12), 1.0)
M_STRAW = [mat('straw_a', (0.55, 0.46, 0.27), 1.0), mat('straw_b', (0.42, 0.34, 0.20), 1.0), mat('straw_c', (0.60, 0.53, 0.34), 1.0)]
M_REED = [mat('reed_a', (0.50, 0.41, 0.23), 1.0), mat('reed_b', (0.38, 0.31, 0.18), 1.0)]
M_HEAD = mat('seed_head', (0.22, 0.14, 0.08), 0.9)
M_NEEDLE = mat('needles', (0.06, 0.15, 0.085), 1.0)

def frame(d):
    t = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(t).normalized(); w = d.cross(u).normalized(); return u, w

def ttube(bm, pts, radii, sides=6, cap_start=None, cap_end=None):
    """a round bar swept along a polyline with a radius per point. cap_*: material index of an end cap (None = open)."""
    rings = []; n = len(pts)
    for i, p in enumerate(pts):
        a = pts[i + 1] if i < n - 1 else p; b = pts[i - 1] if i > 0 else p
        d = (a - b).normalized(); u, w = frame(d)
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * radii[i]) for k in range(sides)])
    for i in range(n - 1):
        A = rings[i]; B = rings[i + 1]
        for k in range(sides):
            j = (k + 1) % sides; bm.faces.new((A[k], A[j], B[j], B[k]))
    if cap_start is not None:
        f = bm.faces.new(rings[0][::-1]); f.material_index = cap_start
    if cap_end is not None:
        f = bm.faces.new(rings[-1]); f.material_index = cap_end
    return rings

def grow(bm, rnd, start, d, length, r0, depth, maxdepth, droop=0.0, sides=5, segs=5, taper=0.32, spread=(0.9, 1.7)):
    """a branch that curves a little, tapers, and sprouts smaller branches until maxdepth"""
    pts = [Vector(start)]; radii = [r0]; cur = d.normalized()
    for i in range(segs):
        wob = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.6) if depth == 0 else rnd.uniform(-1, 0.5)))
        cur = (cur + wob * 0.16 + Vector((0, 0, -droop))).normalized()
        pts.append(pts[-1] + cur * (length / segs)); radii.append(max(0.004, r0 * (1 - (1 - taper) * (i + 1) / segs)))
    ttube(bm, pts, radii, sides if depth < 2 else 3)
    if depth < maxdepth:
        nkids = 3 if depth == 0 else 2
        for k in range(nkids + (1 if depth == 0 else 0)):
            t = rnd.uniform(*spread) / 2.0 if depth == 0 else rnd.uniform(0.4, 0.9)
            idx = min(segs - 1, int(t * segs)); p = pts[idx]; dd = (pts[idx + 1] - pts[idx]).normalized()
            ax = dd.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0, 1)))).normalized()
            if ax.length < 1e-6: ax = Vector((0, 0, 1))
            nd = (Matrix.Rotation(math.radians(rnd.uniform(30, 60)), 3, ax) @ dd)
            if depth == 0: nd.z = abs(nd.z) * 0.6 + 0.35
            grow(bm, rnd, p, nd, length * rnd.uniform(0.45, 0.65), radii[idx] * 0.6, depth + 1, maxdepth, droop + 0.02, sides, max(3, segs - 1), taper)
    return pts

def trunk_hull(pts, radii, upto, sides=8):
    """closed low-poly collision for a trunk: convex hull of rings at the base and at 'upto' of its height"""
    cb = bmesh.new(); n = len(pts)
    for i in sorted(set([0, int(upto * (n - 1))])):
        d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized(); u, w = frame(d)
        for k in range(sides):
            a = 2 * math.pi * k / sides; cb.verts.new(pts[i] + (u * math.cos(a) + w * math.sin(a)) * (radii[i] + 0.015))
    tri_hull(cb); return cb

def trunk_path(rnd, h, lean, segs=8, r0=0.22, r1=0.07, bend=0.12):
    d = Vector((lean * rnd.uniform(0.6, 1.0), lean * rnd.uniform(-0.6, 0.6), 1.0)).normalized(); pts = [Vector((0, 0, 0))]; cur = d
    for i in range(segs):
        cur = (cur + Vector((rnd.uniform(-bend, bend), rnd.uniform(-bend, bend), 0))).normalized()
        pts.append(pts[-1] + cur * (h / segs))
    radii = [r0 + (r1 - r0) * (i / segs) ** 0.8 for i in range(segs + 1)]
    return pts, radii

def roots(bm, rnd, r, n=5, mat_idx=None):
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.3, 0.3); d = Vector((math.cos(a), math.sin(a), 0))
        p0 = d * r * 0.6 + Vector((0, 0, 0.18)); p1 = d * (r + 0.35) + Vector((0, 0, 0.03)); p2 = d * (r + 0.7) + Vector((0, 0, -0.04))
        ttube(bm, [p0, p1, p2], [r * 0.32, r * 0.2, r * 0.08], 4)

# ---------------------------------------------------------------- bare tree (7 m)
def dead_tree(name, seed, h, lean, charred=False):
    rnd = random.Random(seed); bm = bmesh.new()
    pts, radii = trunk_path(rnd, h, lean, 8, 0.24, 0.06)
    ttube(bm, pts, radii, 8, None, 0)
    roots(bm, rnd, 0.24, 5)
    for k in range(6 + (seed % 3)):                                         # main limbs spiral up the upper two thirds of the trunk
        i = 3 + int(k * 4.5 / 7); i = min(i, 7); a = 2.4 * k + rnd.uniform(0, 1)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.35, 0.9))).normalized()
        grow(bm, rnd, pts[i], d, h * rnd.uniform(0.28, 0.42) * (1.1 - 0.07 * k), radii[i] * 0.55, 1, 3, 0.03, 5, 5)
    grow(bm, rnd, pts[-1], pts[-1] - pts[-2], h * 0.22, radii[-1], 1, 2, 0.0, 4, 4)   # the leader
    root = new_root(name); vis = to_obj(name, bm, [M_CHAR if charred else M_BARK, M_SPLIT], True)
    col = to_obj('COL_' + name, trunk_hull(pts, radii, 0.55), [M_BARK], False)
    finish(root, vis, col, name); return root

# ---------------------------------------------------------------- shell-snapped tree (3.4 m trunk, splinters at the top, a few broken limbs)
def broken_tree(name, seed):
    rnd = random.Random(seed); bm = bmesh.new()
    pts, radii = trunk_path(rnd, 3.4, 0.22, 7, 0.26, 0.17, 0.1)
    ttube(bm, pts, radii, 8, None, 1)
    roots(bm, rnd, 0.26, 5)
    top = pts[-1]
    for k in range(7):                                                      # splinters: thin wedges standing out of the break at different heights
        a = 2 * math.pi * k / 7 + rnd.uniform(-0.3, 0.3); r = rnd.uniform(0.04, 0.13); hgt = rnd.uniform(0.25, 0.95)
        base = top + Vector((math.cos(a) * r, math.sin(a) * r, -0.05)); tip = base + Vector((math.cos(a) * 0.05 * rnd.uniform(-1, 1) - 0.04, math.sin(a) * 0.05, hgt))
        ttube(bm, [base, base + (tip - base) * 0.6, tip], [0.045, 0.028, 0.004], 4, None, None)
    for (zi, a, L) in ((3, 0.6, 0.9), (4, 3.2, 0.6), (5, 5.1, 0.45)):    # snapped-off limb stubs
        d = Vector((math.cos(a), math.sin(a), 0.5)).normalized(); b = pts[zi]
        ttube(bm, [b, b + d * L * 0.5, b + d * L], [0.06, 0.05, 0.04], 5, None, 1)
    root = new_root(name); vis = to_obj(name, bm, [M_CHAR, M_SPLIT], True)
    col = to_obj('COL_' + name, trunk_hull(pts, radii, 1.0), [M_BARK], False)
    finish(root, vis, col, name); return root

# ---------------------------------------------------------------- stump (0.55 m, cut top, flared roots)
def stump():
    rnd = random.Random(11); bm = bmesh.new()
    pts = [Vector((0, 0, -0.04)), Vector((0.01, 0, 0.25)), Vector((0.015, 0.01, 0.55))]
    ttube(bm, pts, [0.36, 0.30, 0.27], 10, None, 1)
    roots(bm, rnd, 0.33, 6)
    root = new_root('tree_stump'); vis = to_obj('tree_stump', bm, [M_BARK, M_SPLIT], True)
    cb = bmesh.new()
    for z, r in ((0.0, 0.36), (0.55, 0.27)):
        for k in range(10):
            a = 2 * math.pi * k / 10; cb.verts.new((math.cos(a) * (r + 0.01), math.sin(a) * (r + 0.01), z))
    tri_hull(cb); col = to_obj('COL_tree_stump', cb, [M_BARK], False)
    finish(root, vis, col, 'tree_stump'); return root

# ---------------------------------------------------------------- fallen log (4 m long, lying along x)
def fallen_log():
    rnd = random.Random(21); bm = bmesh.new(); L = 4.0
    pts = [Vector((-L / 2 + L * i / 6, 0.05 * math.sin(i * 0.9), 0.3 + 0.01 * i)) for i in range(7)]
    radii = [0.30 - 0.04 * i / 6 + rnd.uniform(-0.008, 0.008) for i in range(7)]
    ttube(bm, pts, radii, 9, 1, 1)
    for (i, a, ln) in ((1, 1.2, 0.55), (3, 4.4, 0.4), (4, 0.4, 0.7), (5, 2.2, 0.35)):
        d = Vector((0.25, math.cos(a), 0.55 + 0.4 * math.sin(a))).normalized()
        grow(bm, rnd, pts[i], d, ln, 0.045, 2, 3, 0.03, 4, 3)
    root = new_root('fallen_log'); vis = to_obj('fallen_log', bm, [M_BARK, M_SPLIT], True)
    cb = bmesh.new()
    for i in (0, 6):
        for k in range(9):
            a = 2 * math.pi * k / 9; cb.verts.new(pts[i] + Vector((0, math.cos(a), math.sin(a))) * (radii[i] + 0.01))
    tri_hull(cb); col = to_obj('COL_fallen_log', cb, [M_BARK], False)
    finish(root, vis, col, 'fallen_log'); return root

# ---------------------------------------------------------------- bare scrub bush (1.3 m, walk-through: no collision)
def finish_soft(root, vis, name):
    vis.parent = root; STATS.append((name, len(vis.data.polygons), 0))

def shrub(name, seed, stems):
    rnd = random.Random(seed); bm = bmesh.new()
    for k in range(stems):
        a = 2 * math.pi * k / stems + rnd.uniform(-0.3, 0.3); d = Vector((math.cos(a) * rnd.uniform(0.25, 0.7), math.sin(a) * rnd.uniform(0.25, 0.7), 1.0))
        grow(bm, rnd, Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, 0)), d, rnd.uniform(0.9, 1.4), 0.014, 1, 3, 0.02, 3, 4)
    root = new_root(name); vis = to_obj(name, bm, [M_TWIG], False)
    finish_soft(root, vis, name); return root

# ---------------------------------------------------------------- dry grass tuft (blades are flat strips; draw them double-sided)
def grass(name, seed, count, height, spread):
    rnd = random.Random(seed); bm = bmesh.new()
    for b in range(count):
        a = rnd.uniform(0, 2 * math.pi); r = spread * math.sqrt(rnd.random()); base = Vector((math.cos(a) * r, math.sin(a) * r, -0.02))
        lean = Vector((math.cos(a) * 0.25 + rnd.uniform(-0.2, 0.2), math.sin(a) * 0.25 + rnd.uniform(-0.2, 0.2), 0)); H = height * rnd.uniform(0.55, 1.0)
        side = Vector((-math.sin(rnd.uniform(0, 6.28)), math.cos(rnd.uniform(0, 6.28)), 0)).normalized()
        w = 0.011; levels = [(0.0, w), (0.5, w * 0.8), (0.85, w * 0.45)]
        vs = []
        for t, ww in levels:
            c = base + lean * (t ** 1.7) * H + Vector((0, 0, t * H)); vs.append((bm.verts.new(c - side * ww), bm.verts.new(c + side * ww)))
        tip = bm.verts.new(base + lean * H * 1.05 + Vector((0, 0, H)))
        mi = rnd.randrange(3)
        for i in range(2):
            f = bm.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0])); f.material_index = mi
        f = bm.faces.new((vs[2][0], vs[2][1], tip)); f.material_index = mi
    root = new_root(name); vis = to_obj(name, bm, M_STRAW, False)
    finish_soft(root, vis, name); return root

# ---------------------------------------------------------------- reed clump (1.4 - 2.1 m stalks, cattail heads on some)
def reeds():
    rnd = random.Random(33); bm = bmesh.new(); heads = bmesh.new()
    for k in range(26):
        a = rnd.uniform(0, 2 * math.pi); r = 0.38 * math.sqrt(rnd.random()); H = rnd.uniform(1.3, 2.1)
        base = Vector((math.cos(a) * r, math.sin(a) * r, 0)); lean = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.05, 0.3)
        pts = [base + lean * (t ** 2) * H + Vector((0, 0, t * H)) for t in (0, 0.33, 0.66, 1.0)]
        ttube(bm, pts, [0.009, 0.0075, 0.006, 0.004], 3)
        if rnd.random() < 0.45:
            d = (pts[3] - pts[2]).normalized(); ttube(heads, [pts[3] - d * 0.22, pts[3] + d * 0.02], [0.022, 0.018], 5, None, 0)
        if rnd.random() < 0.7:                                              # long drooping leaf blade
            b2 = pts[1]; d = Vector((math.cos(a + 1.2), math.sin(a + 1.2), 0.6)).normalized()
            ttube(bm, [b2, b2 + d * 0.5, b2 + d * 0.8 + Vector((0, 0, -0.25))], [0.007, 0.006, 0.002], 3)
    for f in heads.faces: f.material_index = 1
    tmp = bpy.data.meshes.new('h'); heads.to_mesh(tmp); heads.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    root = new_root('reed_clump'); vis = to_obj('reed_clump', bm, [M_REED[0], M_HEAD], False)
    finish_soft(root, vis, 'reed_clump'); return root

# ---------------------------------------------------------------- young spruce (5 m; the only green thing)
def spruce():
    rnd = random.Random(7); bm = bmesh.new(); needles = bmesh.new(); H = 5.0
    pts = [Vector((0.02 * math.sin(i), 0.02 * math.cos(i), H * i / 6)) for i in range(7)]
    ttube(bm, pts, [0.16, 0.13, 0.105, 0.08, 0.06, 0.04, 0.012], 7, None, 0)
    tiers = 9
    for i in range(tiers):
        z = 0.9 + (H - 1.3) * i / (tiers - 1); R = 1.45 * (1 - i / (tiers - 0.4)) + 0.12; rot = rnd.uniform(0, 6.28); n = 11
        apex = needles.verts.new((0, 0, z + 0.55 + 0.15 * R))
        rim = []
        for k in range(n):
            a = rot + 2 * math.pi * k / n; rr = R * rnd.uniform(0.8, 1.15)
            rim.append(needles.verts.new((math.cos(a) * rr, math.sin(a) * rr, z - 0.28 * rr + rnd.uniform(-0.05, 0.05))))
        for k in range(n):
            needles.faces.new((apex, rim[(k + 1) % n], rim[k]))
    tmp = bpy.data.meshes.new('n'); needles.to_mesh(tmp); needles.free()
    nb = bmesh.new(); nb.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    for f in nb.faces: f.material_index = 1
    tmp2 = bpy.data.meshes.new('nn'); nb.to_mesh(tmp2); nb.free(); bm.from_mesh(tmp2); bpy.data.meshes.remove(tmp2)
    root = new_root('spruce_young'); vis = to_obj('spruce_young', bm, [M_BARK, M_NEEDLE], True)
    cb = bmesh.new()
    for z, r in ((0.0, 0.17), (2.4, 0.09)):
        for k in range(8):
            a = 2 * math.pi * k / 8; cb.verts.new((math.cos(a) * r, math.sin(a) * r, z))
    tri_hull(cb); col = to_obj('COL_spruce_young', cb, [M_BARK], False)
    finish(root, vis, col, 'spruce_young'); return root

# ---------------------------------------------------------------- build the batch
dead_tree('dead_tree_a', 3, 7.0, 0.10); dead_tree('dead_tree_b', 8, 6.0, 0.22, True); broken_tree('broken_tree', 5); spruce(); stump(); fallen_log()
shrub('shrub_bare_a', 2, 9); shrub('shrub_bare_b', 6, 7)
grass('grass_dry_short', 4, 46, 0.38, 0.22); grass('grass_dry_tall', 9, 34, 0.85, 0.26); reeds()

# lay them out in a row (for the preview and so the file is readable); the game ignores the position and re-centres each prop
xs = 0.0
for r in ROOTS:
    r.location = (xs, 0, 0); xs += 5.5 if r.name in ('prop_dead_tree_a', 'prop_dead_tree_b', 'prop_broken_tree', 'prop_spruce_young') else (3.0 if r.name in ('prop_fallen_log',) else 2.3)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True)
print('VEGETATION EXPORTED', os.path.getsize(glb), 'bytes')
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
TREE_N = 4
XS = [r.location.x for r in ROOTS]
cx = (XS[0] + XS[TREE_N - 1]) / 2
cx2 = (XS[TREE_N] + XS[-1]) / 2
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 24.0, 5.0, 10, 3.2)
shot(BATCH + '_small.png', cx2, 16.0, 4.0, 10, 0.6)
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
shot(BATCH + '_col.png', cx, 24.0, 5.0, 10, 3.2)
shot(BATCH + '_small_col.png', cx2, 16.0, 4.0, 10, 0.6)
print('VEG DONE')
