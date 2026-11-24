import bpy, bmesh, math, os, random
from mathutils import Vector, noise
# v2: jerrycan rebuilt from the v1 review (D1-D9). Game units: 1 unit = 1 m, Blender x east / y north / z up, broad face toward -Y.
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

# ---- materials: only what the can uses (v1 attached nine slots, 87.8 MB of textures)
MATS = [tmat('paint_olive', 'metal_olive_c', 'metal_olive_n', 0.62, nstrength=0.7, spec=0.3), tmat('steel_grey', 'metal_grey_c', 'metal_grey_n', 0.5, nstrength=0.6, spec=0.35)]
PAINT, STEEL = 0, 1
from mathutils import Euler

X, Y, ZB, ZT = 0.345, 0.156, 0.40, 0.46          # width, depth, body height, overall height (handle top)
R_EDGE = 0.02                                     # pressed-steel edge radius

def uv_box(bm, scale=1 / 0.45):
    """per-face box projection in metres (dominant normal axis), so the paint texture keeps its real scale on every face"""
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i])); a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops: lp[uvl].uv = (lp.vert.co[a] * scale, lp.vert.co[b] * scale)

def body(bm):
    """rounded box: subdivided cube pushed onto a rounded-box surface (flat top, small fillets), recessed seam round the middle of the narrow faces (y = 0)"""
    tmp = bmesh.new(); bmesh.ops.create_cube(tmp, size=1.0); bmesh.ops.subdivide_edges(tmp, edges=list(tmp.edges), cuts=7, use_grid_fill=True)
    for yy in (-0.0055 / Y, 0.0055 / Y):                                                  # extra loops either side of y = 0 so the seam groove is a continuous V
        bmesh.ops.bisect_plane(tmp, geom=list(tmp.verts) + list(tmp.edges) + list(tmp.faces), plane_co=(0, yy, 0), plane_no=(0, 1, 0))
    h = Vector((X / 2, Y / 2, ZB / 2)); r = R_EDGE
    for v in tmp.verts:
        p = Vector((v.co.x * X, v.co.y * Y, v.co.z * ZB))
        inner = Vector((max(-(h.x - r), min(h.x - r, p.x)), max(-(h.y - r), min(h.y - r, p.y)), max(-(h.z - r), min(h.z - r, p.z))))
        d = p - inner
        if d.length > 1e-9: p = inner + d.normalized() * r
        if abs(p.y) < 0.0056 and (abs(p.x) > h.x - 1e-4 or abs(p.z) > h.z - 1e-4):            # recessed seam groove
            k = 1.0 - abs(p.y) / 0.0056; p.x -= math.copysign(0.0045 * k, p.x) if abs(p.x) > h.x - 1e-4 else 0; p.z -= math.copysign(0.0045 * k, p.z) if abs(p.z) > h.z - 1e-4 else 0
        v.co = p + Vector((0, 0, ZB / 2))
    tmp.normal_update(); vm = {}
    for f in tmp.faces:
        if all(v.co.z < 1e-4 for v in f.verts): continue                          # bottom face is never seen
        vs = []
        for v in f.verts:
            if v not in vm: vm[v] = bm.verts.new(v.co)
            vs.append(vm[v])
        nf = bm.faces.new(vs); nf.material_index = PAINT; nf.smooth = True
    tmp.free()

def prism(bm, p0, p1, w0, w1, h0, h1, mi, sink=0.003):
    """a low trapezoid rib from p0 to p1 lying on a face whose outward normal is +/-Y (sign taken from p0.y): base width w0, top width w1, height h0 above the surface, sunk 'sink' into it"""
    sgn = 1 if p0.y >= 0 else -1; d = (p1 - p0); ln = d.length; u = d.normalized(); n = Vector((0, sgn, 0)); s = u.cross(n).normalized()
    def ring(p, hgt):
        base = p - n * sink
        return [base - s * w0 / 2, base + s * w0 / 2, base + n * (hgt + sink) + s * w1 / 2, base + n * (hgt + sink) - s * w1 / 2]
    a = [bm.verts.new(v) for v in ring(p0, h0)]; b = [bm.verts.new(v) for v in ring(p1, h1)]
    for i in range(4):
        j = (i + 1) % 4; f = bm.faces.new((a[i], a[j], b[j], b[i]) if sgn > 0 else (a[j], a[i], b[i], b[j])); f.material_index = PAINT
    for q in (a, b[::-1]):
        pass
    f = bm.faces.new(a[::-1] if sgn > 0 else a); f.material_index = PAINT
    f = bm.faces.new(b if sgn > 0 else b[::-1]); f.material_index = PAINT

def box(bm, c, s, mi, rot_z=0.0):
    tmp = bmesh.new(); bmesh.ops.create_cube(tmp, size=1.0)
    for v in tmp.verts:
        p = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
        if rot_z: p = Euler((0, 0, rot_z)).to_matrix() @ p
        v.co = p + Vector(c)
    vm = {}
    for f in tmp.faces:
        vs = []
        for v in f.verts:
            if v not in vm: vm[v] = bm.verts.new(v.co)
            vs.append(vm[v])
        nf = bm.faces.new(vs); nf.material_index = mi
    tmp.free()

def cyl(bm, c, r, z0, z1, mi, sides=12, cap_top=True, r_top=None):
    r_top = r if r_top is None else r_top
    lo = [bm.verts.new((c[0] + math.cos(2 * math.pi * k / sides) * r, c[1] + math.sin(2 * math.pi * k / sides) * r, z0)) for k in range(sides)]
    hi = [bm.verts.new((c[0] + math.cos(2 * math.pi * k / sides) * r_top, c[1] + math.sin(2 * math.pi * k / sides) * r_top, z1)) for k in range(sides)]
    for k in range(sides):
        j = (k + 1) % sides; f = bm.faces.new((lo[k], lo[j], hi[j], hi[k])); f.material_index = mi; f.smooth = True
    if cap_top: f = bm.faces.new(hi[::-1]); f.material_index = mi

def jerrycan():
    bm = bmesh.new(); body(bm)
    yf = Y / 2                                                                      # broad-face plane
    for sy in (-1, 1):                                                              # pressed ribs: X and two rails, on both broad faces
        y = sy * yf
        x0, x1, z0, z1 = -0.125, 0.125, 0.075, 0.325
        prism(bm, Vector((x0, y, z0)), Vector((x1, y, z1)), 0.022, 0.012, 0.0045, 0.0045, PAINT)
        prism(bm, Vector((x0, y, z1)), Vector((x1, y, z0)), 0.022, 0.012, 0.0045, 0.0045, PAINT)
        for z in (0.05, 0.35): prism(bm, Vector((-0.15, y, z)), Vector((0.15, y, z)), 0.020, 0.012, 0.0045, 0.0045, PAINT)
        for x in (-0.15, 0.15): prism(bm, Vector((x, y, 0.05)), Vector((x, y, 0.35)), 0.020, 0.012, 0.0045, 0.0045, PAINT)
    # three-bar handle: four posts, three grip openings, a top bar
    xs = [-0.165, -0.0917, -0.0183, 0.055]
    for x in xs: box(bm, (x, 0, ZB + 0.029), (0.014, 0.030, 0.058), PAINT)
    box(bm, ((xs[0] + xs[-1]) / 2, 0, ZB + 0.0545), (xs[-1] - xs[0] + 0.014, 0.030, 0.010), PAINT)
    box(bm, ((xs[0] + xs[-1]) / 2, 0, ZB + 0.004), (xs[-1] - xs[0] + 0.026, 0.040, 0.012), PAINT)               # pressed base block under the handle
    # spout with flange, flip cap, cam lever and retainer ring
    sx = 0.12
    cyl(bm, (sx, 0), 0.040, ZB - 0.004, ZB + 0.008, STEEL, 14, True)
    cyl(bm, (sx, 0), 0.030, ZB + 0.008, ZB + 0.036, STEEL, 14, False)
    cyl(bm, (sx, 0), 0.034, ZB + 0.036, ZB + 0.052, STEEL, 14, True, 0.032)
    box(bm, (sx, 0, ZB + 0.058), (0.062, 0.012, 0.010), STEEL)
    box(bm, (sx + 0.0, 0.0, ZB + 0.045), (0.010, 0.074, 0.006), STEEL)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); uv_box(bm)
    root = new_root('jerrycan'); vis = to_obj('jerrycan', bm, MATS, False)
    hp = [Vector((sx_ * X / 2, sy_ * Y / 2 * 0.9, z)) for sx_ in (-1, 1) for sy_ in (-1, 1) for z in (0, ZB)] + [Vector((sx_ * 0.17, 0, ZB + 0.058)) for sx_ in (-1, 1)] + [Vector((sx + 0.034 * math.cos(a), 0.034 * math.sin(a), ZB + 0.062)) for a in (0, 1.6, 3.2, 4.8)]
    finish(root, vis, hull_col('jerrycan', hp), 'jerrycan'); return root

def hull_col(name, pts):
    cb = bmesh.new()
    for p in pts: cb.verts.new(Vector((p.x, p.y, max(p.z, 0.0))))
    tri_hull(cb); return to_obj('COL_' + name, cb, [], False)
jerrycan()
