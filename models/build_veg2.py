import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'veg_2'
os.makedirs(OUT, exist_ok=True)

for _ob in list(bpy.data.objects): bpy.data.objects.remove(_ob, do_unlink=True)
for _c in list(bpy.data.collections): bpy.data.collections.remove(_c)
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
    for b in list(blk):
        if b.users == 0: blk.remove(b)


TEX = OUT + '/textures/veg/'
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

M_BARK = tmat('bark_dead', 'bark_dead_c', 'bark_dead_n', 0.96, nstrength=1.0)
M_CHAR = tmat('bark_charred', 'bark_charred_c', 'bark_charred_n', 0.92, nstrength=1.1)
M_SBARK = tmat('bark_spruce', 'bark_spruce_c', 'bark_spruce_n', 0.95, nstrength=1.4)
M_END = tmat('end_grain', 'endgrain_c', 'endgrain_n', 0.85, nstrength=1.0)
M_END_CH = tmat('end_grain_charred', 'endgrain_charred_c', 'endgrain_charred_n', 0.9)
M_FIBRE = tmat('wood_fibre', 'fibre_c', 'fibre_n', 0.9, nstrength=1.5)
M_GRASS = [tmat('grass_a', 'grass_a', None, 0.85, True), tmat('grass_b', 'grass_b', None, 0.85, True)]
M_REEDC = tmat('reed_card', 'reed', None, 0.8, True)
M_SPR = tmat('spruce_card', 'spruce_branch', None, 0.7, True)
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

def strip(bm, L, R, uvL, uvR, mi):
    """a ribbon of quads between two polylines (cards). uvL/uvR: (u,v) per point"""
    uvl = bm.loops.layers.uv.verify(); vl = [bm.verts.new(p) for p in L]; vr = [bm.verts.new(p) for p in R]
    for i in range(len(L) - 1):
        f = bm.faces.new((vl[i], vr[i], vr[i + 1], vl[i + 1])); f.material_index = mi
        for lp, uv in zip(f.loops, (uvL[i], uvR[i], uvR[i + 1], uvL[i + 1])): lp[uvl].uv = uv

def grow(bm, rnd, start, d, length, r0, depth, maxdepth, droop=0.0, sides=6, segs=5, taper=0.32, spread=(0.9, 1.7)):
    pts = [Vector(start)]; radii = [r0]; cur = d.normalized()
    for i in range(segs):
        wob = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.6) if depth == 0 else rnd.uniform(-1, 0.5)))
        cur = (cur + wob * 0.16 + Vector((0, 0, -droop))).normalized()
        pts.append(pts[-1] + cur * (length / segs)); radii.append(max(0.004, r0 * (1 - (1 - taper) * (i + 1) / segs)))
    ttube(bm, pts, radii, sides if depth < 2 else 4, None, 1 if r0 > 0.012 else None, 0.07 if depth < 2 else 0.0)
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
    radii = [r0 * (1.0 + 0.22 * max(0.0, 1 - i / 1.6)) + (r1 - r0) * (i / segs) ** 0.8 for i in range(segs + 1)]   # flared base
    return pts, radii

def roots(bm, rnd, r, n=6):
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.3, 0.3); d = Vector((math.cos(a), math.sin(a), 0))
        p = [d * r * 0.5 + Vector((0, 0, 0.30)), d * (r + 0.15) + Vector((0, 0, 0.12)), d * (r + 0.4) + Vector((0, 0, 0.03)), d * (r + 0.75) + Vector((0, 0, -0.05))]
        ttube(bm, p, [r * 0.38, r * 0.27, r * 0.16, r * 0.06], 6, None, None, 0.08)

def stubs(bm, rnd, pts, radii, n, lo, hi):
    """broken-off limb stubs on the trunk with splintered wood at the tips"""
    for k in range(n):
        t = rnd.uniform(lo, hi); i = min(len(pts) - 2, int(t * (len(pts) - 1))); f = t * (len(pts) - 1) - i
        p = pts[i] + (pts[i + 1] - pts[i]) * f; r = radii[i] * (1 - f) + radii[i + 1] * f; a = rnd.uniform(0, 6.28)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.1, 0.7))).normalized(); L = rnd.uniform(0.12, 0.35); rr = rnd.uniform(0.025, 0.05)
        ttube(bm, [p + d * r * 0.7, p + d * (r + L * 0.5), p + d * (r + L)], [rr * 1.4, rr, rr * 0.8], 6, None, 1, 0.05)

# ---------------------------------------------------------------- bare tree (7 m)
def dead_tree(name, seed, h, lean, charred=False):
    rnd = random.Random(seed); bm = bmesh.new(); bk = M_CHAR if charred else M_BARK
    pts, radii = trunk_path(rnd, h, lean, 8, 0.24, 0.06)
    ttube(bm, pts, radii, 14, None, 1, 0.06)
    roots(bm, rnd, 0.24, 6)
    stubs(bm, rnd, pts, radii, 6, 0.1, 0.75)
    for k in range(6 + (seed % 3)):
        i = 3 + int(k * 4.5 / 7); i = min(i, 7); a = 2.4 * k + rnd.uniform(0, 1)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.35, 0.9))).normalized()
        grow(bm, rnd, pts[i], d, h * rnd.uniform(0.28, 0.42) * (1.1 - 0.07 * k), radii[i] * 0.55, 1, 3, 0.03, 7, 5)
    grow(bm, rnd, pts[-1], pts[-1] - pts[-2], h * 0.22, radii[-1], 1, 2, 0.0, 6, 4)
    root = new_root(name); vis = to_obj(name, bm, [bk, M_FIBRE], True)
    col = to_obj('COL_' + name, trunk_hull(pts, radii, 0.55), [bk], False)
    finish(root, vis, col, name); return root

# ---------------------------------------------------------------- shell-snapped tree (3.4 m trunk, splinters, broken limbs)
def broken_tree(name, seed):
    rnd = random.Random(seed); bm = bmesh.new()
    pts, radii = trunk_path(rnd, 3.4, 0.22, 7, 0.26, 0.17, 0.1)
    ttube(bm, pts, radii, 14, None, 1, 0.07)
    roots(bm, rnd, 0.26, 6)
    stubs(bm, rnd, pts, radii, 3, 0.2, 0.7)
    top = pts[-1]
    for k in range(11):                                                     # splinters at different heights, pale fresh wood
        a = 2 * math.pi * k / 11 + rnd.uniform(-0.3, 0.3); r = rnd.uniform(0.02, 0.14); hgt = rnd.uniform(0.2, 1.1)
        base = top + Vector((math.cos(a) * r, math.sin(a) * r, -0.1)); tip = base + Vector((math.cos(a) * 0.05 * rnd.uniform(-1, 1) - 0.04, math.sin(a) * 0.05, hgt))
        ttube(bm, [base, base + (tip - base) * 0.5, base + (tip - base) * 0.85, tip], [0.05, 0.036, 0.02, 0.004], 5, None, None, 0.0, 1, 0.3)
    for (zi, a, L) in ((3, 0.6, 0.9), (4, 3.2, 0.6), (5, 5.1, 0.45)):
        d = Vector((math.cos(a), math.sin(a), 0.5)).normalized(); b = pts[zi]
        ttube(bm, [b, b + d * L * 0.5, b + d * L], [0.07, 0.055, 0.045], 6, None, 1, 0.05)
    root = new_root(name); vis = to_obj(name, bm, [M_CHAR, M_FIBRE], True)
    col = to_obj('COL_' + name, trunk_hull(pts, radii, 1.0), [M_BARK], False)
    finish(root, vis, col, name); return root

def stump():
    rnd = random.Random(11); bm = bmesh.new()
    pts = [Vector((0, 0, -0.04)), Vector((0.01, 0, 0.18)), Vector((0.012, 0.005, 0.38)), Vector((0.015, 0.01, 0.55))]
    ttube(bm, pts, [0.40, 0.31, 0.28, 0.27], 16, None, 1, 0.07)
    roots(bm, rnd, 0.33, 7)
    root = new_root('tree_stump'); vis = to_obj('tree_stump', bm, [M_BARK, M_END], True)
    cb = bmesh.new()
    for z, r in ((0.0, 0.40), (0.55, 0.27)):
        for k in range(10):
            a = 2 * math.pi * k / 10; cb.verts.new((math.cos(a) * (r + 0.01), math.sin(a) * (r + 0.01), z))
    tri_hull(cb); col = to_obj('COL_tree_stump', cb, [M_BARK], False)
    finish(root, vis, col, 'tree_stump'); return root

def fallen_log():
    rnd = random.Random(21); bm = bmesh.new(); L = 4.0
    pts = [Vector((-L / 2 + L * i / 8, 0.05 * math.sin(i * 0.7), 0.3 + 0.008 * i)) for i in range(9)]
    radii = [0.30 - 0.04 * i / 8 + rnd.uniform(-0.008, 0.008) for i in range(9)]
    ttube(bm, pts, radii, 16, 1, 1, 0.07)
    for (i, a, ln) in ((1, 1.2, 0.55), (3, 4.4, 0.4), (5, 0.4, 0.7), (6, 2.2, 0.35)):
        d = Vector((0.25, math.cos(a), 0.55 + 0.4 * math.sin(a))).normalized()
        grow(bm, rnd, pts[i], d, ln, 0.05, 2, 3, 0.03, 5, 3)
    root = new_root('fallen_log'); vis = to_obj('fallen_log', bm, [M_BARK, M_END], True)
    cb = bmesh.new()
    for i in (0, 8):
        for k in range(9):
            a = 2 * math.pi * k / 9; cb.verts.new(pts[i] + Vector((0, math.cos(a), math.sin(a))) * (radii[i] + 0.01))
    tri_hull(cb); col = to_obj('COL_fallen_log', cb, [M_BARK], False)
    finish(root, vis, col, 'fallen_log'); return root

def finish_soft(root, vis, name):
    vis.parent = root; STATS.append((name, len(vis.data.polygons), 0))

def shrub(name, seed, stems):
    rnd = random.Random(seed); bm = bmesh.new()
    for k in range(stems):
        a = 2 * math.pi * k / stems + rnd.uniform(-0.3, 0.3); d = Vector((math.cos(a) * rnd.uniform(0.25, 0.7), math.sin(a) * rnd.uniform(0.25, 0.7), 1.0))
        grow(bm, rnd, Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, 0)), d, rnd.uniform(0.9, 1.4), 0.016, 1, 3, 0.02, 5, 5)
    root = new_root(name); vis = to_obj(name, bm, [M_BARK, M_FIBRE], False)
    finish_soft(root, vis, name); return root

# ---------------------------------------------------------------- crossed alpha cards: grass tufts and reeds
def card_tuft(name, seed, cards, W, H, tex_list, bend=0.25, vseg=4):
    rnd = random.Random(seed); bm = bmesh.new()
    for c in range(cards):
        yaw = math.pi * (c / cards) + rnd.uniform(-0.25, 0.25); side = Vector((math.cos(yaw), math.sin(yaw), 0)); fwd = Vector((-side.y, side.x, 0))
        w = W * rnd.uniform(0.85, 1.1); h = H * rnd.uniform(0.85, 1.1); off = Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), 0)); lean = fwd * rnd.uniform(-bend, bend) * h
        L = []; R = []; uL = []; uR = []
        for i in range(vseg + 1):
            t = i / vseg; ctr = off + lean * t * t + Vector((0, 0, h * t - 0.01)); half = side * w / 2 * (1 - 0.0 * t)
            L.append(ctr - half); R.append(ctr + half); uL.append((0.0, t)); uR.append((1.0, t))
        strip(bm, L, R, uL, uR, rnd.randrange(len(tex_list)))
    root = new_root(name); vis = to_obj(name, bm, tex_list, False); finish_soft(root, vis, name); return root

# ---------------------------------------------------------------- young spruce (5 m): textured trunk, drooping needle-branch cards in whorls
def spruce():
    rnd = random.Random(7); bm = bmesh.new(); H = 5.0
    pts = [Vector((0.02 * math.sin(i), 0.02 * math.cos(i), H * i / 8)) for i in range(9)]
    ttube(bm, pts, [0.17 * (1 - 0.93 * (i / 8) ** 1.1) + 0.012 for i in range(9)], 10, None, 1, 0.03)
    for k in range(9):                                                       # dead brown stubs on the bare lower trunk
        z = rnd.uniform(0.35, 1.2); a = rnd.uniform(0, 6.28); d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.0, 0.35))).normalized()
        b = Vector((0, 0, z)); ttube(bm, [b + d * 0.1, b + d * 0.35, b + d * rnd.uniform(0.5, 0.8)], [0.022, 0.015, 0.006], 4, None, None, 0.0, 0, 0.3)
    z = 0.95; tiers = 0
    while z < H - 0.25:
        frac = (z - 0.95) / (H - 1.2); Lb = 1.55 * (1 - frac) ** 0.85 + 0.32; nb = 8 if frac < 0.6 else 6; rot = rnd.uniform(0, 6.28)
        for k in range(nb):
            a = rot + 2 * math.pi * k / nb + rnd.uniform(-0.2, 0.2); el = (-0.18 + 0.32 * frac) + rnd.uniform(-0.06, 0.1)
            d = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))); ln = Lb * rnd.uniform(0.82, 1.12); wd = ln * 0.58
            base = Vector((0, 0, z + rnd.uniform(-0.05, 0.05))) ; sd = Vector((-d.y, d.x, 0)).normalized()
            for tilt in (0.42, -0.42):
                sv = (sd + Vector((0, 0, tilt))).normalized(); L = []; R = []; uL = []; uR = []
                for i in range(7):
                    t = i / 6; c = base + d * ln * t + Vector((0, 0, -0.30 * ln * t * t + 0.05 * ln * math.sin(t * 3)))
                    hw = wd / 2
                    L.append(c - sv * hw); R.append(c + sv * hw); uL.append((t, 0.0)); uR.append((t, 1.0))
                strip(bm, L, R, uL, uR, 2)
        z += rnd.uniform(0.15, 0.21); tiers += 1
    root = new_root('spruce_young'); vis = to_obj('spruce_young', bm, [M_SBARK, M_END, M_SPR], True)
    cb = bmesh.new()
    for zz, r in ((0.0, 0.18), (2.4, 0.09)):
        for k in range(8):
            a = 2 * math.pi * k / 8; cb.verts.new((math.cos(a) * r, math.sin(a) * r, zz))
    tri_hull(cb); col = to_obj('COL_spruce_young', cb, [M_BARK], False)
    finish(root, vis, col, 'spruce_young'); return root

# ---------------------------------------------------------------- build the batch
dead_tree('dead_tree_a', 3, 7.0, 0.10); dead_tree('dead_tree_b', 8, 6.0, 0.22, True); broken_tree('broken_tree', 5); spruce(); stump(); fallen_log()
shrub('shrub_bare_a', 2, 10); shrub('shrub_bare_b', 6, 8)
card_tuft('grass_dry_short', 4, 6, 0.7, 0.52, M_GRASS); card_tuft('grass_dry_tall', 9, 5, 0.95, 0.95, [M_GRASS[1], M_GRASS[0]], 0.3); card_tuft('reed_clump', 33, 6, 0.75, 2.2, [M_REEDC], 0.22, 6)

xs = 0.0
for r in ROOTS:
    r.location = (xs, 0, 0); xs += 5.5 if r.name in ('prop_dead_tree_a', 'prop_dead_tree_b', 'prop_broken_tree', 'prop_spruce_young') else (3.0 if r.name in ('prop_fallen_log',) else 2.3)
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
sc.render.resolution_x = 1900; sc.render.resolution_y = 620
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
TREE_N = 4
XS = [r.location.x for r in ROOTS]
cx = (XS[0] + XS[TREE_N - 1]) / 2
cx2 = (XS[TREE_N] + XS[-1]) / 2
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 24.0, 5.0, 10, 3.2)
shot(BATCH + '_small.png', cx2, 16.0, 4.0, 10, 0.6); shot(BATCH + '_log.png', XS[5] if len(XS) > 5 else 0, 6.0, 1.6, 20, 0.3)
shot(BATCH + '_close.png', XS[0], 6.5, 2.4, 25, 2.2)
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
