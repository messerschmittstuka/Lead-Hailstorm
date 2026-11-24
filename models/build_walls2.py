import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'walls_2'
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


W_ = 3.0; H_ = 3.0; T_ = 0.5
MATS_W = MATS
I_CORE, I_STONE, I_PLINTH, I_FRAME = BR, CO, CO, WD

def abox(bm, x0, x1, y0, y1, z0, z1, mi, skip_back=False):
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for k, f in enumerate(fs):
        if skip_back and k == 0: continue
        fc = bm.faces.new([v[i] for i in f]); fc.material_index = mi
        uvl = bm.loops.layers.uv.verify(); fc.normal_update(); n = fc.normal; ax = max(range(3), key=lambda i: abs(n[i])); a_, b_ = [(1, 2), (0, 2), (0, 1)][ax]; sx, sy = UVS[mi]
        for lp in fc.loops: lp[uvl].uv = (lp.vert.co[a_] * sx, lp.vert.co[b_] * sy)

def runs(pred, x, step=0.01, zmax=H_):
    out = []; z = 0.0; cur = None
    n = int(round(zmax / step))
    for k in range(n):
        zm = (k + 0.5) * step
        if pred(x, zm):
            if cur is None: cur = k * step
        else:
            if cur is not None: out.append((cur, k * step)); cur = None
    if cur is not None: out.append((cur, n * step))
    return out

def merged_columns(pred, step=0.05, zmax=H_):
    """left to right, merge neighbouring columns whose solid z-runs are identical -> list of (x0, x1, [(z0, z1)...])"""
    cols = []; n = int(round(W_ / step))
    for i in range(n):
        xm = -W_ / 2 + (i + 0.5) * step; r = [(round(a, 2), round(b, 2)) for a, b in runs(pred, xm, 0.01, zmax)]
        if cols and cols[-1][2] == r: cols[-1][1] = -W_ / 2 + (i + 1) * step
        else: cols.append([-W_ / 2 + i * step, -W_ / 2 + (i + 1) * step, r])
    return cols

def brick_faces(bm, pred, rnd, zmax):
    CH = 0.12                                                                                  # course height (brick + joint)
    for k in range(int(zmax / CH + 1e-6)):
        z0 = k * CH + 0.008; z1 = k * CH + CH - 0.008; zm = (z0 + z1) / 2
        x = -W_ / 2 - (k % 2) * 0.26 - rnd.random() * 0.04
        while x < W_ / 2:
            ln = rnd.choice((0.50, 0.50, 0.75, 0.25)); a = max(x + 0.008, -W_ / 2); b = min(x + ln - 0.008, W_ / 2); x += ln
            if b - a < 0.06: continue
            # trim the brick to the part of it that is actually wall (openings, broken top)
            s = 0.025; pieces = []; cur = None
            for q in range(int(round((b - a) / s))):
                xm = a + (q + 0.5) * s; ok = pred(xm, zm)
                if ok and cur is None: cur = a + q * s
                if not ok and cur is not None: pieces.append((cur, a + q * s)); cur = None
            if cur is not None: pieces.append((cur, b))
            mi = rnd.choices((0, 1, 2), (4, 3, 3))[0]
            for p0, p1 in pieces:
                if p1 - p0 < 0.05: continue
                d = 0.017 + rnd.random() * 0.012
                abox(bm, p0, p1, T_ / 2 - 0.045, T_ / 2 - 0.045 + d + 0.03, z0, z1, mi, skip_back=True)       # outer face courses
                abox(bm, p0, p1, -T_ / 2 + 0.045 - d - 0.03, -T_ / 2 + 0.045, z0, z1, mi, skip_back=False)    # inner face courses

def build_wall(name, pred, seed, zmax=H_, plinth=True, coping=True, extras=None):
    rnd = random.Random(seed); bm = bmesh.new()
    for x0, x1, rr in merged_columns(pred, 0.05, zmax):                                          # mortar core (follows openings and the broken top)
        for z0, z1 in rr: abox(bm, x0, x1, -T_ / 2, T_ / 2, z0, z1 - 0.005, I_CORE)
    if plinth:                                                                                   # darker stone foot, like the game's plinth
        for x0, x1, rr in merged_columns(pred, 0.05, 0.36):
            for z0, z1 in rr:
                if z0 < 0.01: abox(bm, x0, x1, -T_ / 2 - 0.02, T_ / 2 + 0.02, 0.0, min(z1, 0.36), I_PLINTH)
    if coping: abox(bm, -W_ / 2 - 0.02, W_ / 2 + 0.02, -T_ / 2 - 0.03, T_ / 2 + 0.03, zmax, zmax + 0.08, I_STONE)
    if extras: extras(bm, rnd)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    cb = bmesh.new()                                                                              # collision: solid blocks following the real silhouette
    for x0, x1, rr in merged_columns(pred, 0.05, zmax):
        for z0, z1 in rr: abox(cb, x0, x1, -T_ / 2, T_ / 2, z0, z1 + (0.08 if coping and abs(z1 - zmax) < 0.011 else 0), 0)
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    root = new_root(name); vis = to_obj(name, bm, MATS_W, False); col = to_obj('COL_' + name, cb, [], False)
    finish(root, vis, col, name); return root

ZC = H_ - 0.08                                                                                   # intact walls: courses end under the stone coping
def frame_box(bm, x0, x1, z0, z1): abox(bm, x0, x1, -0.14, 0.14, z0, z1, I_FRAME)

def wall_solid(): return build_wall('wall_brick_solid', lambda x, z: z < ZC, 21, ZC)

def wall_window():
    def pred(x, z): return z < ZC and not (abs(x) < 0.6 and 1.0 < z < 2.2)
    def ex(bm, rnd):
        abox(bm, -0.74, 0.74, -T_ / 2 - 0.05, T_ / 2 + 0.05, 0.94, 1.0, I_STONE)                  # stone sill
        abox(bm, -0.76, 0.76, -T_ / 2 - 0.02, T_ / 2 + 0.02, 2.2, 2.38, I_STONE)                   # stone lintel
        for x0, x1 in ((-0.6, -0.54), (0.54, 0.6)): frame_box(bm, x0, x1, 1.0, 2.2)               # window frame, with a mullion and a transom
        frame_box(bm, -0.6, 0.6, 1.0, 1.05); frame_box(bm, -0.6, 0.6, 2.15, 2.2); frame_box(bm, -0.025, 0.025, 1.05, 2.15); frame_box(bm, -0.54, 0.54, 1.6, 1.64)
    return build_wall('wall_brick_window', pred, 22, ZC, extras=ex)

def wall_door():
    def pred(x, z): return z < ZC and not (abs(x) < 0.55 and z < 2.5)
    def ex(bm, rnd):
        abox(bm, -0.72, 0.72, -T_ / 2 - 0.02, T_ / 2 + 0.02, 2.5, 2.68, I_STONE)                  # stone lintel
        for x0, x1 in ((-0.56, -0.5), (0.5, 0.56)): frame_box(bm, x0, x1, 0.0, 2.5)               # door frame
        frame_box(bm, -0.56, 0.56, 2.44, 2.5)
        abox(bm, -0.58, 0.58, -T_ / 2 - 0.03, T_ / 2 + 0.03, 0.0, 0.04, I_STONE)                  # worn stone threshold
    return build_wall('wall_brick_door', pred, 23, ZC, extras=ex)

def wall_ruined():
    rr_ = random.Random(77); hts = {}
    def hf(x):
        c = int(math.floor((x + W_ / 2) / 0.25))
        if c not in hts:
            h = 2.25 + 0.5 * math.sin(c * 0.55 + 0.7) + 0.3 * math.sin(c * 1.4 + 1.9) + (rr_.random() - 0.5) * 0.35
            if 4 <= c <= 7: h = 0.55 + rr_.random() * 0.45            # a breach blown through the wall
            if c <= 1: h = 2.9 - rr_.random() * 0.2                   # the corner stays standing tall
            hts[c] = max(0.4, min(2.95, round(h / 0.12) * 0.12))
        return hts[c]
    def pred(x, z):
        if abs(x + 0.9) < 0.5 and 1.0 < z < 2.2: return False        # the remains of a window
        return z < hf(x)
    def ex(bm, rnd):
        abox(bm, -1.44, -0.36, -T_ / 2 - 0.05, T_ / 2 + 0.05, 0.94, 1.0, I_STONE)                  # sill survived
        frame_box(bm, -1.4, -1.34, 1.0, 2.2)                                                      # one splintered frame post
        rr2 = random.Random(5)
        for k in range(16):
            x = rr2.uniform(-1.0, 1.1); y = rr2.choice((-1, 1)) * rr2.uniform(0.35, 0.95)
            add_chunk(bm, (x, y, 0.03), (0.215, 0.10, 0.065), (rr2.uniform(-0.5, 0.5), rr2.uniform(-0.5, 0.5), rr2.uniform(0, 6.28)), BS, rr2, 1, 0.04)
        for k in range(5):
            x = rr2.uniform(-0.8, 0.9); y = rr2.choice((-1, 1)) * rr2.uniform(0.4, 0.9); L_ = rr2.uniform(0.3, 0.6)
            add_chunk(bm, (x, y, 0.1), (L_, rr2.uniform(0.2, 0.3), rr2.uniform(0.15, 0.3)), (rr2.uniform(-0.3, 0.3), rr2.uniform(-0.3, 0.3), rr2.uniform(0, 6.28)), BR, rr2, 2, 0.05)
        for k in range(3):
            x = rr2.uniform(-0.8, 0.9); y = rr2.choice((-1, 1)) * rr2.uniform(0.4, 0.9); s_ = rr2.uniform(0.2, 0.4)
            add_chunk(bm, (x, y, 0.05), (s_, s_ * 0.8, s_ * 0.6), (rr2.uniform(0, 6.28),) * 3, CO, rr2, 2, 0.08)
    return build_wall('wall_brick_ruined', pred, 24, H_, coping=False, extras=ex)


wall_solid(); wall_window(); wall_door(); wall_ruined()
# layout: spread props by their real width so previews never overlap (the game ignores these positions)
def halfw(r):
    ob = [c for c in r.children if not c.name.startswith('COL_')][0]; xs_ = [v.co.x for v in ob.data.vertices]; ys_ = [v.co.y for v in ob.data.vertices]
    return max(abs(min(xs_)), abs(max(xs_)), abs(min(ys_)), abs(max(ys_)))
xs = 0.0; prev = 0.0
for r in ROOTS:
    hw = halfw(r); xs += (prev + hw + 0.6) if r is not ROOTS[0] else 0.0; r.location = (xs, 0, 0); prev = hw
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
mid_ = sum(XS.values()) / len(XS)
shot(BATCH + '_view.png', mid_, 13.0, 2.6, 18, 1.5)
shot(BATCH + '_back.png', mid_, 13.0, 2.6, 160, 1.5)
shot(BATCH + '_ruin.png', XS['wall_brick_ruined'], 6.5, 1.8, 22, 1.3)
shot(BATCH + '_win.png', XS['wall_brick_window'], 5.0, 1.6, 16, 1.5)
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
shot(BATCH + '_col.png', mid_, 13.0, 2.6, 18, 1.5)
print('WALLS DONE')

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
