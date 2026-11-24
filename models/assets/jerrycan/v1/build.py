import bpy, bmesh, math, os, random
from mathutils import Vector, noise
# v1 = the jerrycan exactly as it currently exists in build_props4.py (game units: 1 unit = 1 m, Blender x east / y north / z up). Only the harness plumbing differs:
# no scene clearing, no export, no previews (lib_loop handles those); textures are read from models/textures/prop/ (read-only).
MODELS = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
TEX = MODELS + '/textures/prop/'
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
