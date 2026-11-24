import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'props_4'
os.makedirs(OUT, exist_ok=True)

for _ob in list(bpy.data.objects): bpy.data.objects.remove(_ob, do_unlink=True)
for _c in list(bpy.data.collections): bpy.data.collections.remove(_c)
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
    for b in list(blk):
        if b.users == 0: blk.remove(b)


TEX = OUT + '/textures/prop/'
def mat(name, rgb, rough=0.9, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1)
    return m

_IMG = {}
def img(name, srgb=True):
    if name not in _IMG:
        pth = TEX + name + ('.jpg' if os.path.exists(TEX + name + '.jpg') else '.png'); im = bpy.data.images.load(pth); im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'; _IMG[name] = im
    return _IMG[name]

def tmat(name, color, normal=None, rough=0.9, alpha=False, nstrength=1.0, spec=0.25):
    """image-textured PBR material: base colour map, optional tangent-space normal map, optional alpha-clip (cards)"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(color); t.interpolation = 'Linear'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    for k in ('Specular IOR Level', 'Specular'):
        if k in b.inputs: b.inputs[k].default_value = spec; break
    if normal:
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(normal, False)
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstrength
        nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if alpha:
        mth = nt.nodes.new('ShaderNodeMath'); mth.operation = 'GREATER_THAN'; mth.inputs[1].default_value = 0.5    # glTF exporter reads this as alphaMode MASK
        nt.links.new(t.outputs['Alpha'], mth.inputs[0]); nt.links.new(mth.outputs['Value'], b.inputs['Alpha'])
        m.use_backface_culling = False
        for k, v in (('blend_method', 'CLIP'), ('alpha_threshold', 0.5), ('surface_render_method', 'DITHERED')):
            try: setattr(m, k, v)
            except Exception as e: print('  (mat attr', k, 'unavailable)')
    m.diffuse_color = (0.3, 0.3, 0.3, 1)
    return m

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


from mathutils import Matrix

def frame(d):
    t = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(t).normalized(); w = d.cross(u).normalized(); return u, w

def ttube(bm, pts, radii, sides=6, cap_start=None, cap_end=None, lump=0.0, body_mat=0, tile=0.9):
    """a lumpy tapered bar swept along a polyline, UV-mapped for bark: u runs round the bar, v along it (square texture tiles).
    cap_*: material index of an end cap (None = open), caps get planar UVs for the cut-wood textures."""
    uvl = bm.loops.layers.uv.verify(); n = len(pts)
    C = 2 * math.pi * max(radii[0], 0.012); N = max(1, round(C / tile)); tl = max(C / N, 0.16)
    arc = [0.0]
    for i in range(1, n): arc.append(arc[-1] + (pts[i] - pts[i - 1]).length)
    rings = []; cs = {}
    for i, p in enumerate(pts):
        a = pts[i + 1] if i < n - 1 else p; b = pts[i - 1] if i > 0 else p
        d = (a - b).normalized(); u, w = frame(d); ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides; c, s = math.cos(ang), math.sin(ang); r = radii[i]
            if lump: r *= 1.0 + lump * noise.noise(p * 2.3 + Vector((c, s, 0.3 * k)) * (0.5 + 4 * radii[0]))
            v = bm.verts.new(p + (u * c + w * s) * r); cs[v] = (c, s); ring.append(v)
        rings.append(ring)
    for i in range(n - 1):
        A = rings[i]; B = rings[i + 1]
        for k in range(sides):
            j = (k + 1) % sides; f = bm.faces.new((A[k], A[j], B[j], B[k])); f.material_index = body_mat
            u0 = k / sides * N; u1 = (k + 1) / sides * N; va = arc[i] / tl; vb = arc[i + 1] / tl
            for lp, uv in zip(f.loops, ((u0, va), (u1, va), (u1, vb), (u0, vb))): lp[uvl].uv = uv
    for ring, idx, rev in ((rings[0], cap_start, True), (rings[-1], cap_end, False)):
        if idx is None: continue
        f = bm.faces.new(ring[::-1] if rev else ring); f.material_index = idx
        for lp in f.loops:
            c, s = cs[lp.vert]; lp[uvl].uv = (0.5 + 0.47 * c, 0.5 + 0.47 * s)
    return rings

from mathutils import Euler
def finish_soft(root, vis, name):
    vis.parent = root; STATS.append((name, len(vis.data.polygons), 0))

# materials (fixed slot order for every prop)
MATS = [tmat('brick', 'brick_c', 'brick_n', 0.92, nstrength=1.6), tmat('brick_solid', 'brick_solid_c', 'brick_solid_n', 0.9, nstrength=1.2),
        tmat('concrete', 'concrete_c', 'concrete_n', 0.95, nstrength=1.4), tmat('plaster', 'plaster_c', 'plaster_n', 0.95, nstrength=1.2),
        tmat('planks', 'planks_c', 'planks_n', 0.88, nstrength=1.5), tmat('planks_olive', 'planks_olive_c', 'planks_olive_n', 0.75, nstrength=1.4),
        tmat('metal_olive', 'metal_olive_c', 'metal_olive_n', 0.6, nstrength=0.6, spec=0.3), tmat('metal_grey', 'metal_grey_c', 'metal_grey_n', 0.55, nstrength=0.6, spec=0.3),
        tmat('burlap', 'burlap_c', 'burlap_n', 0.98, nstrength=0.8, spec=0.05)]
BR, BS, CO, PL, WD, WO, MO, MG, BU = range(9)
UVS = {BR: (1 / 1.075, 1 / 0.75), BS: (1 / 0.30, 1 / 0.30), CO: (1 / 1.2, 1 / 1.2), PL: (1 / 1.2, 1 / 1.2), WD: (1 / 0.8, 1 / 0.8), WO: (1 / 0.75, 1 / 0.75), MO: (1 / 1.0, 1 / 1.0), MG: (1 / 1.0, 1 / 1.0), BU: (1 / 0.55, 1 / 0.55)}

def add_chunk(bm, c, s, eul, mi, rnd, cuts=0, jit=0.0, clip=True, taper=0.0, rot_tex=False):
    """a (broken) block: subdivided cube, jittered, rotated, placed; faces get box-projected UVs in world metres so every texture keeps its real scale"""
    tmp = bmesh.new(); bmesh.ops.create_cube(tmp, size=1.0)
    if cuts: bmesh.ops.subdivide_edges(tmp, edges=list(tmp.edges), cuts=cuts, use_grid_fill=True)
    M = Euler(eul).to_matrix()
    for v in tmp.verts:
        p = v.co.copy()
        if taper: k = 1.0 - taper * (p.z + 0.5); p.x *= k; p.y *= k
        p = Vector((p.x * s[0], p.y * s[1], p.z * s[2]))
        if jit: p += Vector((rnd.uniform(-1, 1) * jit * s[0], rnd.uniform(-1, 1) * jit * s[1], rnd.uniform(-1, 1) * jit * s[2]))
        p = M @ p + Vector(c)
        if clip and p.z < 0: p.z = 0.0
        v.co = p
    tmp.normal_update(); uvl = bm.loops.layers.uv.verify(); sx, sy = UVS[mi]; o = (rnd.random(), rnd.random()); vm = {}; made = []
    for f in tmp.faces:
        if all(v.co.z < 1e-5 for v in f.verts) and f.normal.z > -0.5: continue
        vs = []
        for v in f.verts:
            if v not in vm: vm[v] = bm.verts.new(v.co)
            vs.append(vm[v])
        try: nf = bm.faces.new(vs)
        except ValueError: continue
        nf.material_index = mi; made.append(nf)
        n = f.normal
        if mi in (WD, WO):
            w_ = M @ Vector((0, 0, 1) if s[2] >= max(s[0], s[1]) else ((1, 0, 0) if s[0] >= s[1] else (0, 1, 0))); w_ = w_.normalized(); ac = n.cross(w_)
            ac = ac.normalized() if ac.length > 1e-4 else Vector((1, 0, 0))
            for lp, v in zip(nf.loops, f.verts): lp[uvl].uv = (v.co.dot(ac) * sx + o[0], v.co.dot(w_) * sy + o[1])
        else:
            ax = max(range(3), key=lambda i: abs(n[i])); a, b = [(1, 2), (0, 2), (0, 1)][ax]
            for lp, v in zip(nf.loops, f.verts): lp[uvl].uv = (v.co[a] * sx + o[0], v.co[b] * sy + o[1])
    tmp.free(); return vm.values()

def hull_col(name, pts):
    cb = bmesh.new()
    for p in pts: cb.verts.new(Vector((p.x, p.y, max(p.z, 0.0))))
    tri_hull(cb); return to_obj('COL_' + name, cb, [], False)

def jag_end(bm, verts, rnd, amt):
    for v in verts: v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * amt

# ---------------------------------------------------------------- rubble piles: broken wall fragments, concrete lumps, plaster, loose bricks, rebar and splintered timber, heaped in a cone
def rubble(name, seed, R, H, n_wall, n_conc, n_plas, n_brick, n_rebar, n_wood, lopsided=0.25):
    rnd = random.Random(seed); bm = bmesh.new(); hullp = []
    ax_, ay_ = rnd.uniform(0.85, 1.15), rnd.uniform(0.85, 1.15)
    def prof(r): return H * max(0.0, 1.0 - (r / R) ** 1.7)
    def spot(shrink=1.0):
        a = rnd.uniform(0, 6.283); r = R * shrink * math.sqrt(rnd.random()) ** 1.15; x = math.cos(a) * r * ax_; y = math.sin(a) * r * ay_
        rr = math.hypot(x / ax_, y / ay_); return x, y, prof(rr)
    def eul(): return (rnd.uniform(0, 6.283), rnd.uniform(0, 6.283), rnd.uniform(0, 6.283))
    for k in range(n_conc):
        x, y, z = spot(0.95); sz = rnd.uniform(0.22, 0.62) * (1.2 - 0.35 * (math.hypot(x, y) / R))
        hullp += [v.co.copy() for v in add_chunk(bm, (x, y, z * 0.75 + sz * 0.15), (sz, sz * rnd.uniform(0.6, 1.0), sz * rnd.uniform(0.5, 0.9)), eul(), CO, rnd, 2, 0.08)]
    for k in range(n_wall):
        x, y, z = spot(0.9); L = rnd.uniform(0.35, 0.85); w = rnd.uniform(0.2, 0.34); t = rnd.uniform(0.18, 0.4)
        hullp += [v.co.copy() for v in add_chunk(bm, (x, y, z * 0.7 + 0.1), (L, w, t), (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0, 6.283)), BR, rnd, 2, 0.06)]
    for k in range(n_plas):
        x, y, z = spot(); sz = rnd.uniform(0.12, 0.34)
        hullp += [v.co.copy() for v in add_chunk(bm, (x, y, z * 0.8 + sz * 0.15), (sz, sz * rnd.uniform(0.5, 1), sz * rnd.uniform(0.3, 0.6)), eul(), PL, rnd, 1, 0.1)]
    for k in range(n_brick):
        x, y, z = spot(1.12); z = max(prof(math.hypot(x, y)), 0) * 0.85
        hullp += [v.co.copy() for v in add_chunk(bm, (x, y, z + 0.03), (0.215, 0.10, 0.065), (rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(0, 6.283)), BS, rnd, 1, 0.04)]
    for k in range(n_wood):
        x, y, z = spot(0.8); L = rnd.uniform(0.5, 1.3); a = rnd.uniform(0, 6.283)
        vs = add_chunk(bm, (x, y, z + 0.12), (rnd.uniform(0.06, 0.1), rnd.uniform(0.09, 0.14), L), (rnd.uniform(0.9, 1.9), rnd.uniform(-0.3, 0.3), a), WD, rnd, 2, 0.06)
        jag_end(bm, [v for v in vs if v.co.z > 0.02 and rnd.random() < 0.5], rnd, 0.015); hullp += [v.co.copy() for v in vs]
    for k in range(n_rebar):                                          # bent rebar sticking out of the heap
        x, y, z = spot(0.7); d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.6, 1.4))).normalized(); L = rnd.uniform(0.35, 0.8)
        pts = [Vector((x, y, z + 0.1)) + d * L * t + Vector((0, 0, -0.55 * L * t * t)) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.015 * (1 if t > 0.5 else 0) for t in (0, 0.33, 0.66, 1.0)]
        ttube(bm, pts, [0.0135] * 4, 6, None, None, 0.0, MG, 0.5)
    bm.verts.ensure_lookup_table()
    root = new_root(name); vis = to_obj(name, bm, MATS, True)
    for p in vis.data.polygons: p.use_smooth = (vis.data.materials[p.material_index].name in ('plaster',))
    # collision: hull of the lumps only (rebar is thin enough to be ignored), squashed to the visible heap
    col = hull_col(name, [p for p in hullp if p.z > 0.0 or True]); finish(root, vis, col, name); return root

rubble('rubble_pile_a', 11, 1.0, 0.55, 5, 6, 5, 18, 3, 2)
rubble('rubble_pile_b', 23, 1.5, 0.8, 9, 10, 8, 26, 5, 3)
rubble('rubble_heap', 37, 2.3, 1.15, 18, 20, 14, 46, 9, 6)

# ---------------------------------------------------------------- loose debris (walk-through): bricks, broken bricks, plaster flakes, splinters scattered on the ground
def debris(name, seed, n_brick, n_half, n_flake, n_wood, R):
    rnd = random.Random(seed); bm = bmesh.new()
    def spot(): a = rnd.uniform(0, 6.283); r = R * math.sqrt(rnd.random()); return math.cos(a) * r, math.sin(a) * r
    for k in range(n_brick):
        x, y = spot(); tilt = rnd.random() < 0.3
        add_chunk(bm, (x, y, 0.032 if not tilt else 0.05), (0.215, 0.10, 0.065), ((rnd.uniform(-0.5, 0.5) if tilt else 0), (rnd.uniform(-0.5, 0.5) if tilt else 0), rnd.uniform(0, 6.283)), BS, rnd, 1, 0.03)
    for k in range(n_half):
        x, y = spot(); add_chunk(bm, (x, y, 0.03), (rnd.uniform(0.08, 0.15), 0.10, 0.065), (0, 0, rnd.uniform(0, 6.283)), BS, rnd, 1, 0.12)
    for k in range(n_flake):
        x, y = spot(); s = rnd.uniform(0.04, 0.12); add_chunk(bm, (x, y, s * 0.2), (s, s * rnd.uniform(0.5, 1), s * 0.45), (0, 0, rnd.uniform(0, 6.283)), PL if rnd.random() < 0.5 else CO, rnd, 1, 0.2)
    for k in range(n_wood):
        x, y = spot(); L = rnd.uniform(0.25, 0.7); add_chunk(bm, (x, y, 0.02), (0.035, 0.06, L), (math.pi / 2, 0, rnd.uniform(0, 6.283)), WD, rnd, 1, 0.08)
    root = new_root(name); vis = to_obj(name, bm, MATS, True); finish_soft(root, vis, name); return root
debris('debris_bricks_a', 51, 7, 5, 9, 2, 0.8)
debris('debris_bricks_b', 63, 12, 8, 14, 3, 1.2)

# ---------------------------------------------------------------- broken timber beams
def beams(name, seed):
    rnd = random.Random(seed); bm = bmesh.new(); hp = []
    spec = [((0, 0, 0.07), (0.10, 0.16, 1.9), (math.pi / 2, 0, 0.35)), ((0.15, 0.05, 0.2), (0.12, 0.14, 1.5), (math.pi / 2 + 0.12, 0.2, -0.5)),
            ((-0.25, -0.1, 0.12), (0.09, 0.12, 1.2), (math.pi / 2 - 0.08, 0.1, 1.2)), ((0.3, -0.25, 0.07), (0.07, 0.07, 0.9), (math.pi / 2, 0, -1.1))]
    for c, s, e in spec:
        vs = add_chunk(bm, c, s, e, WD, rnd, 3, 0.035)
        jag_end(bm, [v for v in vs if rnd.random() < 0.35 and (v.co - Vector(c)).length > s[2] * 0.4], rnd, 0.022); hp += [v.co.copy() for v in vs]
    for p in (Vector((0.1, 0.2, 0.01)), Vector((-0.2, 0.25, 0.01))):                   # a couple of nails / splinters on the ground
        add_chunk(bm, p, (0.03, 0.05, 0.35), (math.pi / 2, 0, rnd.uniform(0, 6)), WD, rnd, 1, 0.1)
    root = new_root(name); vis = to_obj(name, bm, MATS, True); finish(root, vis, hull_col(name, hp), name); return root
beams('beams_debris', 71)

# ---------------------------------------------------------------- wooden crate (0.8 x 0.5 x 0.53): boards on corner posts, battened lid, a cracked board
def crate_wood():
    rnd = random.Random(81); bm = bmesh.new(); X, Y, Z = 0.8, 0.5, 0.53; t = 0.018
    for sx in (-1, 1):
        for sy in (-1, 1): add_chunk(bm, (sx * (X / 2 - 0.03), sy * (Y / 2 - 0.03), Z / 2), (0.06, 0.06, Z), (0, 0, 0), WD, rnd, 0, 0.0, False)
    for sy in (-1, 1):
        for k in range(4):
            z = 0.05 + k * 0.125 + 0.0625 - 0.03; add_chunk(bm, (rnd.uniform(-0.004, 0.004), sy * (Y / 2 - t / 2), z), (X - 0.01, t, 0.115 + rnd.uniform(-0.006, 0.004)), (rnd.uniform(-0.01, 0.01), 0, 0), WD, rnd, 1, 0.01, False)
    for sx in (-1, 1):
        for k in range(4):
            z = 0.05 + k * 0.125 + 0.0625 - 0.03; add_chunk(bm, (sx * (X / 2 - t / 2), 0, z), (t, Y - 0.1, 0.115 + rnd.uniform(-0.006, 0.004)), (0, 0, 0), WD, rnd, 1, 0.01, False)
    for k in range(4): add_chunk(bm, (0, -Y / 2 + 0.0625 + k * 0.125, Z - 0.009), (X + 0.01, 0.118, 0.018), (0, rnd.uniform(-0.01, 0.01), 0), WD, rnd, 1, 0.01, False)
    for sx in (-0.28, 0.28): add_chunk(bm, (sx, 0, Z + 0.006), (0.06, Y - 0.02, 0.02), (0, 0, 0), WD, rnd, 0, 0, False)
    add_chunk(bm, (0, 0, 0.012), (X - 0.02, Y - 0.02, 0.024), (0, 0, 0), WD, rnd, 0, 0, False)           # floor
    root = new_root('crate_wood'); vis = to_obj('crate_wood', bm, MATS, False)
    zt = Z + 0.012; finish(root, vis, hull_col('crate_wood', [Vector((sx * X / 2, sy * Y / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, zt)]), 'crate_wood'); return root
crate_wood()

# ---------------------------------------------------------------- ammunition box (0.64 x 0.33 x 0.31): olive-painted boards, steel corner caps, latches, rope handles
def crate_ammo():
    rnd = random.Random(91); bm = bmesh.new(); X, Y, Z = 0.64, 0.33, 0.31
    add_chunk(bm, (0, 0, Z * 0.5), (X, Y, Z), (0, 0, 0), WO, rnd, 1, 0.0, False)
    add_chunk(bm, (0, 0, Z + 0.008), (X + 0.02, Y + 0.02, 0.016), (0, 0, 0), WO, rnd, 0, 0, False)              # overhanging lid
    for sx in (-1, 1):
        add_chunk(bm, (sx * (X / 2 - 0.045), 0, Z + 0.024), (0.05, Y + 0.02, 0.016), (0, 0, 0), WO, rnd, 0, 0, False)     # lid battens
        for sy in (-1, 1):
            add_chunk(bm, (sx * (X / 2 + 0.002), sy * (Y / 2 + 0.002), Z / 2), (0.022, 0.022, Z), (0, 0, 0), MG, rnd, 0, 0, False)  # steel corner strips
    for sy in (-1, 1):
        add_chunk(bm, (0, sy * (Y / 2 + 0.008), Z * 0.78), (0.07, 0.016, 0.075), (0, 0, 0), MG, rnd, 0, 0, False)   # hasp
        add_chunk(bm, (0, sy * (Y / 2 + 0.012), Z * 0.74), (0.025, 0.012, 0.03), (0, 0, 0), MG, rnd, 0, 0, False)
    for sx in (-1, 1):                                                  # rope handle loops on the short ends
        c = Vector((sx * (X / 2 + 0.012), 0, Z * 0.62)); pts = [c + Vector((0, y, z)) for y, z in ((-0.07, -0.02), (-0.06, 0.03), (-0.025, 0.055), (0.025, 0.055), (0.06, 0.03), (0.07, -0.02))]
        ttube(bm, pts, [0.009] * 6, 6, None, None, 0.0, BU, 0.3)
    root = new_root('crate_ammo'); vis = to_obj('crate_ammo', bm, MATS, False)
    zt = Z + 0.03; finish(root, vis, hull_col('crate_ammo', [Vector((sx * (X + 0.04) / 2, sy * (Y + 0.02) / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, zt)]), 'crate_ammo'); return root
crate_ammo()

# ---------------------------------------------------------------- steel drum (0.6 x 0.88): lathe profile with rolled hoops, chime rim, recessed head, two bungs
def barrel(name='barrel_oil', seed=7, sides=28):
    prof = [(0.0, 0.0), (0.262, 0.0), (0.286, 0.012), (0.292, 0.03), (0.288, 0.05), (0.292, 0.07)]
    for zc in (0.20, 0.44, 0.68):                                      # three rolled hoops
        prof += [(0.292, zc - 0.045), (0.2975, zc - 0.03), (0.306, zc - 0.012), (0.306, zc + 0.012), (0.2975, zc + 0.03), (0.292, zc + 0.045)]
    prof += [(0.292, 0.81), (0.289, 0.83), (0.292, 0.852), (0.297, 0.868), (0.30, 0.88), (0.282, 0.88), (0.272, 0.868), (0.27, 0.858), (0.0, 0.858)]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify(); rnd = random.Random(seed); rings = []
    for (r, z) in prof:
        ring = []
        for k in range(sides if r > 0 else 1):
            a = 2 * math.pi * k / sides; ring.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, z)))
        rings.append(ring)
    arc = [0.0]
    for i in range(1, len(prof)): arc.append(arc[-1] + math.hypot(prof[i][0] - prof[i - 1][0], prof[i][1] - prof[i - 1][1]))
    circ = 2 * math.pi * 0.3
    for i in range(len(prof) - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(sides):
            j = (k + 1) % sides
            if len(A) == 1: vs = (A[0], B[j], B[k])
            elif len(B) == 1: vs = (A[k], A[j], B[0])
            else: vs = (A[k], A[j], B[j], B[k])
            try: f = bm.faces.new(vs[::-1] if False else vs)
            except ValueError: continue
            f.material_index = MO
            for lp in f.loops:
                v = lp.vert; ang = math.atan2(v.co.y, v.co.x); idx = [i if v in rings[i] else i + 1][0]; lp[uvl].uv = ((ang / (2 * math.pi)) * circ + 0.25 * seed, arc[idx if v in rings[idx] else i] * 1.0)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for z, ang in ((0.858, 0.9), (0.858, -0.9)):                       # bungs: a threaded cap and a vent plug
        pass
    for (bx, by, rr) in ((0.12, 0.05, 0.034), (-0.12, -0.08, 0.026)):
        for r_, z_ in ((rr, 0.858), (rr, 0.872), (rr * 0.8, 0.874)):
            pass
        ring0 = [bm.verts.new((bx + math.cos(2 * math.pi * k / 12) * rr, by + math.sin(2 * math.pi * k / 12) * rr, 0.857)) for k in range(12)]
        ring1 = [bm.verts.new((bx + math.cos(2 * math.pi * k / 12) * rr, by + math.sin(2 * math.pi * k / 12) * rr, 0.874)) for k in range(12)]
        for k in range(12):
            j = (k + 1) % 12; f = bm.faces.new((ring0[k], ring0[j], ring1[j], ring1[k])); f.material_index = MG
            for lp in f.loops: lp[uvl].uv = (0.1 * lp.vert.co.x, 0.1 * lp.vert.co.y)
        f = bm.faces.new(ring1[::-1]); f.material_index = MG
        for lp in f.loops: lp[uvl].uv = (0.1 * lp.vert.co.x, 0.1 * lp.vert.co.y)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    root = new_root(name); vis = to_obj(name, bm, MATS, True)
    cb = bmesh.new()
    for z, r in ((0, 0.285), (0.2, 0.305), (0.44, 0.305), (0.68, 0.305), (0.88, 0.298)):
        for k in range(14): a = 2 * math.pi * k / 14; cb.verts.new((math.cos(a) * r, math.sin(a) * r, z))
    tri_hull(cb); finish(root, vis, to_obj('COL_' + name, cb, [], False), name); return root
barrel()

# ---------------------------------------------------------------- jerrycan (0.34 x 0.16 x 0.46): rounded body, embossed X ribs, triple-bar handle, spout and cap
def jerrycan():
    rnd = random.Random(101); bm = bmesh.new(); X, Y, Z = 0.34, 0.16, 0.42
    vs = add_chunk(bm, (0, 0, Z / 2), (X, Y, Z), (0, 0, 0), MO, rnd, 3, 0.0, False)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:                                                  # round every edge and dish the big faces slightly
        nx, ny, nz = v.co.x / (X / 2), v.co.y / (Y / 2), (v.co.z - Z / 2) / (Z / 2)
        if abs(nx) > 0.78: v.co.y *= 1 - 0.28 * (abs(nx) - 0.78) / 0.22
        if abs(nz) > 0.86: v.co.y *= 1 - 0.30 * (abs(nz) - 0.86) / 0.14
        v.co.z += 0.0; v.co.y += 0.0
    for sy in (-1, 1):                                                  # raised X on each broad face + two horizontal ribs
        for sgn in (-1, 1): add_chunk(bm, (0, sy * (Y / 2 + 0.002), Z * 0.45), (0.018, 0.006, 0.34), (0, sgn * 0.65, 0), MO, rnd, 0, 0, False)
        for zr in (0.12, 0.33): add_chunk(bm, (0, sy * (Y / 2 + 0.002), zr), (0.30, 0.006, 0.016), (0, 0, 0), MO, rnd, 0, 0, False)
    add_chunk(bm, (0, 0, Z + 0.025), (0.17, 0.035, 0.05), (0, 0, 0), MO, rnd, 0, 0, False)              # handle: top crossbar and two legs
    for sx in (-1, 1): add_chunk(bm, (sx * 0.075, 0, Z + 0.012), (0.03, 0.035, 0.05), (0, 0, 0), MO, rnd, 0, 0, False)
    add_chunk(bm, (0.1, 0, Z - 0.01), (0.04, 0.05, 0.03), (0, 0, 0), MG, rnd, 0, 0, False)
    sp = [bm.verts.new((0.12 + math.cos(2 * math.pi * k / 10) * 0.028, math.sin(2 * math.pi * k / 10) * 0.028, z)) for z in (Z + 0.0, Z + 0.07) for k in range(10)]
    uvl = bm.loops.layers.uv.verify()
    for k in range(10):
        j = (k + 1) % 10; f = bm.faces.new((sp[k], sp[j], sp[10 + j], sp[10 + k])); f.material_index = MG
        for lp in f.loops: lp[uvl].uv = (lp.vert.co.x * 2, lp.vert.co.z * 2)
    f = bm.faces.new(sp[10:][::-1]); f.material_index = MG
    for lp in f.loops: lp[uvl].uv = (lp.vert.co.x * 2, lp.vert.co.y * 2)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    root = new_root('jerrycan'); vis = to_obj('jerrycan', bm, MATS, False)
    hp = [Vector((sx * X / 2, sy * Y / 2 * 0.85, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, Z)] + [Vector((sx * 0.085, 0, Z + 0.05)) for sx in (-1, 1)] + [Vector((0.12 + 0.03 * math.cos(a), 0.03 * math.sin(a), Z + 0.07)) for a in (0, 1.6, 3.2, 4.8)]
    finish(root, vis, hull_col('jerrycan', hp), 'jerrycan'); return root
jerrycan()

# ---------------------------------------------------------------- sandbag wall (2.0 x 0.41 x 0.68): five staggered courses of lumpy filled bags with tied ends and creases
def sandbag(bm, c, yaw, rnd, size=(0.27, 0.19, 0.072)):
    a_, b_, c_ = size; uvl = bm.loops.layers.uv.verify(); tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=18, v_segments=10, radius=1.0)
    M = Euler((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.05, 0.05), yaw)).to_matrix(); vm = {}
    for v in tmp.verts:
        d = v.co.normalized(); e = 0.62
        p = Vector((a_ * math.copysign(abs(d.x) ** e, d.x), b_ * math.copysign(abs(d.y) ** e, d.y), c_ * math.copysign(abs(d.z) ** e, d.z)))
        pinch = abs(p.x) / a_; p.y *= 1 - 0.42 * pinch ** 3; p.z *= 1 - 0.35 * pinch ** 3        # gathered, tied ends
        p.z += 0.012 * math.sin(p.x * 22 + rnd.random()) * (1 - pinch)                           # soft creases
        p += Vector((noise.noise(p * 9 + Vector((c[0], c[1], 0))), noise.noise(p * 9 + Vector((7, c[1], c[0]))), noise.noise(p * 9 + Vector((3, 5, c[0]))))) * 0.012
        p = M @ p + Vector(c); p.z = max(p.z, 0.0); v.co = p
    o = (rnd.random(), rnd.random())
    for v in tmp.verts: vm[v] = bm.verts.new(v.co)
    out = []
    for f in tmp.faces:
        try: nf = bm.faces.new([vm[v] for v in f.verts])
        except ValueError: continue
        nf.material_index = BU; out.append(nf)
        for lp, v in zip(nf.loops, f.verts): lp[uvl].uv = (v.co.x * UVS[BU][0] * 0.8 + o[0], v.co.y * UVS[BU][1] * 0.8 + v.co.z * 1.4 + o[1])
    tmp.free(); return list(vm.values())
def sandbag_wall():
    rnd = random.Random(111); bm = bmesh.new(); hp = []
    for course in range(5):
        z = 0.067 + course * 0.128; n = 4 if course % 2 == 0 else 3; off = 0.0 if course % 2 == 0 else 0.25
        for k in range(n + (1 if course % 2 else 0)):
            x = -0.75 + k * 0.5 + off - (0.25 if course % 2 else 0.0) + rnd.uniform(-0.012, 0.012)
            if course % 2 and (k == 0 or k == n): x = -0.99 + 0.25 if k == 0 else 0.99 - 0.25
            vs = sandbag(bm, (x, rnd.uniform(-0.012, 0.012), z + rnd.uniform(-0.004, 0.004)), rnd.uniform(-0.07, 0.07), rnd); hp += [v.co.copy() for v in vs]
    root = new_root('sandbag_wall'); vis = to_obj('sandbag_wall', bm, MATS, True)
    ys = [p.y for p in hp]; hp2 = [Vector((max(min(p.x, 0.995), -0.995), p.y, p.z)) for p in hp]
    finish(root, vis, hull_col('sandbag_wall', hp2), 'sandbag_wall'); return root
sandbag_wall()

# layout: spread props by their real width so previews never overlap (the game ignores these positions)
def halfw(r):
    ob = [c for c in r.children if not c.name.startswith('COL_')][0]; xs_ = [v.co.x for v in ob.data.vertices]; ys_ = [v.co.y for v in ob.data.vertices]
    return max(abs(min(xs_)), abs(max(xs_)), abs(min(ys_)), abs(max(ys_)))
xs = 0.0; prev = 0.0
for r in ROOTS:
    hw = halfw(r); xs += (prev + hw + 1.2) if r is not ROOTS[0] else 0.0; r.location = (xs, 0, 0); prev = hw
bpy.context.view_layer.update()
# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True, export_image_format='AUTO')
print('VEG2 EXPORTED', os.path.getsize(glb), 'bytes')
for n, v, c in STATS: print('  %-18s visible %5d tris   collision %4d tris' % (n, v, c))

import json, struct
with open(glb, 'rb') as fh:
    fh.read(12); ln_, _t = struct.unpack('<II', fh.read(8)); J = json.loads(fh.read(ln_))
for m_ in J.get('materials', []): print('  glb material %-20s alpha=%s doubleSided=%s' % (m_.get('name'), m_.get('alphaMode', 'OPAQUE'), m_.get('doubleSided', False)))
print('  glb images:', len(J.get('images', [])))
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
try:
    sc.render.engine = 'BLENDER_EEVEE'
except Exception as e:
    print('eevee failed', e); sc.render.engine = 'BLENDER_WORKBENCH'
try: sc.eevee.taa_render_samples = 24
except Exception: pass
try: sc.view_settings.view_transform = 'Standard'
except Exception: pass
sunl = bpy.data.lights.new('sun', 'SUN'); sunl.energy = 4.0; sunl.angle = 0.05
sun = bpy.data.objects.new('sun', sunl); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(28))
sc.render.resolution_x = 1900; sc.render.resolution_y = 760
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.use_nodes = True; _bg = sc.world.node_tree.nodes['Background']; _bg.inputs['Color'].default_value = (0.50, 0.58, 0.68, 1); _bg.inputs['Strength'].default_value = 1.1
bpy.ops.mesh.primitive_plane_add(size=60, location=(5, 0, -0.001)); gp = bpy.context.object; gm = mat('ground', (0.20, 0.17, 0.12), 1.0); gn = gm.node_tree; _t = gn.nodes.new('ShaderNodeTexImage'); _t.image = bpy.data.images.load(OUT + '/textures/ground_dirt.jpg')
_tc = gn.nodes.new('ShaderNodeTexCoord'); _mp = gn.nodes.new('ShaderNodeMapping'); _mp.inputs['Scale'].default_value = (24, 24, 1)
gn.links.new(_tc.outputs['UV'], _mp.inputs['Vector']); gn.links.new(_mp.outputs['Vector'], _t.inputs['Vector']); gn.links.new(_t.outputs['Color'], gn.nodes['Principled BSDF'].inputs['Base Color'])
gp.data.materials.append(gm)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 38
def shot(fname, cx, dist, h, az, zt):
    a = math.radians(az); cam.location = (cx + math.sin(a) * dist, -math.cos(a) * dist, h)
    cam.rotation_euler = (Vector((cx, 0, zt)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, fname); bpy.ops.render.render(write_still=True)
XS = {r.name[5:]: r.location.x for r in ROOTS}
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
def mid(*ns): return sum(XS[n] for n in ns) / len(ns)
shot(BATCH + '_rubble.png', mid('rubble_pile_a', 'rubble_heap'), 17.0, 3.2, 12, 0.5)
shot(BATCH + '_heap.png', XS['rubble_heap'], 6.0, 2.2, 20, 0.5)
shot(BATCH + '_debris.png', mid('debris_bricks_a', 'beams_debris'), 7.0, 1.6, 12, 0.2)
shot(BATCH + '_kit.png', mid('crate_wood', 'sandbag_wall'), 9.0, 1.5, 10, 0.3)
shot(BATCH + '_crates.png', mid('crate_wood', 'crate_ammo', 'barrel_oil', 'jerrycan'), 4.2, 0.9, 12, 0.3)
shot(BATCH + '_sandbags.png', XS['sandbag_wall'], 3.2, 0.9, 14, 0.3)
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
shot(BATCH + '_col.png', mid('rubble_pile_a', 'rubble_heap'), 17.0, 3.2, 12, 0.5)
shot(BATCH + '_kit_col.png', mid('crate_wood', 'sandbag_wall'), 9.0, 1.5, 10, 0.3)
print('PROPS DONE')

# ---------------------------------------------------------------- game copy: same models, textures halved to 512 px (the dev page embeds this one)
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.size[0] <= 512: continue
    w, h = im.size; fp = (im.filepath or '').lower(); im.scale(512, max(1, int(h * 512 / w)))
    if fp.endswith('.jpg'): im.file_format = 'JPEG'
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.name.startswith(('prop_', 'COL_')) or (ob.parent is not None and ob.parent.name.startswith('prop_')): ob.select_set(True)
glb_g = os.path.join(OUT, BATCH + '_game.glb')
bpy.ops.export_scene.gltf(filepath=glb_g, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True, export_image_format='AUTO')
print('GAME GLB', os.path.getsize(glb_g), 'bytes')
