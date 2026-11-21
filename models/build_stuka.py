import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix

# ---- Junkers Ju 87 B/R Stuka, game units (1 unit = 1 m). Nose is +Y, up is +Z, wings along X. Origin on the fuselage axis, ~5 m behind the nose tip. ----
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
os.makedirs(OUT, exist_ok=True)

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
    for b in list(blk):
        if b.users == 0: blk.remove(b)

V = Vector

# ------------------------------------------------------------------ materials
def mat(name, rgb, metal=0.0, rough=0.6, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1)
    if alpha is not None:
        b.inputs['Alpha'].default_value = alpha; m.diffuse_color = (rgb[0], rgb[1], rgb[2], alpha)
        try: m.blend_method = 'BLEND'
        except Exception: pass
        try: m.surface_render_method = 'BLENDED'
        except Exception: pass
        m.use_backface_culling = False
    return m

def tex_mat(name, img, rough=0.62):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = 0.0
    m.diffuse_color = (0.3, 0.35, 0.25, 1)
    return m

# ------------------------------------------------------------------ texture painting (numpy)
def rs(g, H, W):
    h, w = g.shape
    xi = np.linspace(0, w - 1, W); x0 = np.floor(xi).astype(int); x1 = np.minimum(x0 + 1, w - 1); fx = (xi - x0)[None, :]
    a = g[:, x0] * (1 - fx) + g[:, x1] * fx
    yi = np.linspace(0, h - 1, H); y0 = np.floor(yi).astype(int); y1 = np.minimum(y0 + 1, h - 1); fy = (yi - y0)[:, None]
    return a[y0, :] * (1 - fy) + a[y1, :] * fy

def vnoise(W, H, sx, sy, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((max(2, int(H / sy) + 2), max(2, int(W / sx) + 2))).astype(np.float32) * 2 - 1
    return rs(g, H, W)

def fbm(W, H, sx, sy, seed, oct=3):
    out = np.zeros((H, W), np.float32); a = 1.0; tot = 0
    for o in range(oct):
        out += a * vnoise(W, H, max(1, sx / (2 ** o)), max(1, sy / (2 ** o)), seed + o * 13); tot += a; a *= 0.5
    return out / tot

def camo_field(W, H, seed, cell, ncols):
    rng = np.random.default_rng(seed)
    n = int(W * H / (cell[0] * cell[1]))
    sx = rng.random(n).astype(np.float32) * W; sy = rng.random(n).astype(np.float32) * H
    col = rng.integers(0, ncols, n)
    out = np.zeros((H, W), np.int8)
    X = np.arange(W, dtype=np.float32)[None, :, None]
    warp = (fbm(W, H, 90, 40, seed + 5, 2) * 18).astype(np.float32)
    for r0 in range(0, H, 32):
        r1 = min(H, r0 + 32)
        Y = (np.arange(r0, r1, dtype=np.float32)[:, None, None])
        Xw = X + warp[r0:r1, :, None]
        d = ((Xw - sx) / cell[0]) ** 2 + ((Y - sy) / cell[1]) ** 2
        out[r0:r1] = col[np.argmin(d, axis=2)]
    return out

PAL = np.array([(74, 88, 62), (104, 118, 78), (126, 134, 104)], np.float32) / 255.0    # RLM 70, 71, 02
BLUE = np.array([138, 160, 176], np.float32) / 255.0                                  # RLM 65 light blue
YEL = np.array([222, 184, 30], np.float32) / 255.0
BLACK = np.array([22, 22, 20], np.float32) / 255.0
WHITE = np.array([232, 230, 220], np.float32) / 255.0

GLYPH = {
    'S': [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    '2': [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    '+': ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    'A': [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'M': ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
}

def fill(img, r0, r1, c0, c1, col, a=1.0):
    H, W, _ = img.shape
    r0 = max(0, int(r0)); r1 = min(H, int(r1)); c0 = max(0, int(c0)); c1 = min(W, int(c1))
    if r1 <= r0 or c1 <= c0: return
    img[r0:r1, c0:c1] = img[r0:r1, c0:c1] * (1 - a) + np.array(col, np.float32) * a

def cross(img, rc, cc, sx, sy, flip_r=False):
    """Balkenkreuz: sx, sy = half size in px (columns, rows)"""
    for (hw, col) in ((0.30, WHITE), (0.19, BLACK)):
        L = 1.0 if col is WHITE else 0.86
        fill(img, rc - sy * L, rc + sy * L, cc - sx * hw, cc + sx * hw, col)
        fill(img, rc - sy * hw, rc + sy * hw, cc - sx * L, cc + sx * L, col)

def text(img, s, rc, cc, cw, ch, mirror_c=False, mirror_r=False, col=BLACK):
    """stencil-block letters; cw, ch = cell size of one glyph pixel in px (cols, rows). mirror flags flip the whole string"""
    n = len(s); gw = 5 * cw; gap = cw * 2; total = n * gw + (n - 1) * gap
    c_start = cc - total / 2
    for i, chr_ in enumerate(s):
        g = GLYPH[chr_]
        for r in range(7):
            for c in range(5):
                if g[r][c] != '#': continue
                cx = c_start + i * (gw + gap) + c * cw
                rr = (6 - r) if True else r             # glyph row 0 is the top, image row 0 is the bottom
                cxx = cx; rrr = rc - 3.5 * ch + rr * ch
                if mirror_c: cxx = 2 * cc - cx - cw
                if mirror_r: rrr = 2 * rc - rrr - ch
                fill(img, rrr, rrr + ch, cxx, cxx + cw, col)

def paint_fuselage():
    W, H = 2048, 512
    cm = camo_field(W, H, 11, (170, 70), 3)
    img = PAL[cm].copy()
    v = ((np.arange(H) + 0.5) / H)[:, None]
    db = np.minimum(v, 1 - v) + np.zeros((1, W), np.float32)
    mot = fbm(W, H, 26, 10, 21, 3)
    edge = db + 0.05 * fbm(W, H, 70, 30, 31, 2)
    blue = (edge + 0.07 * mot) < 0.205                                    # light blue belly, mottled up the sides
    img = np.where(blue[:, :, None], BLUE, img)
    # splinter patches on the blue sides too (a few darker blobs of green dropping into the belly)
    # bands and noses
    ux = lambda y: (5.45 - y) / 10.4 * W
    # yellow Eastern Front fuselage band (behind the cross) and a yellow cowl ring
    c0, c1 = ux(-2.0), ux(-2.5)
    fill(img, 0, H, c0, c1, YEL)
    # weathering: soot behind the exhausts, oil streaks, grime
    for side in (0.25, 0.75):
        for k in range(6):
            cc = ux(5.0 - k * 0.3); rr = (side + (-0.012 if side < 0.5 else 0.012) + 0.01 * k * (1 if side < 0.5 else -1)) * H
            L = 150 + 40 * k
            xs = np.arange(int(cc), int(min(W, cc + L)))
            fall = 1 - (xs - cc) / L
            for dr in range(-5, 6):
                rr2 = int(rr + dr)
                if 0 <= rr2 < H:
                    img[rr2, xs] *= (1 - 0.55 * fall * (1 - abs(dr) / 6))[:, None]
    # panel lines (black, thin) – transverse rings and the long seam
    for y in (4.6, 3.3, 2.95, 0.3, -0.6, -1.1, -2.0, -3.0, -4.0):
        c = int(ux(y)); img[:, max(0, c - 1):c + 1] *= 0.62
    for vv in (0.215, 0.785, 0.34, 0.66):
        r = int(vv * H); img[r - 1:r + 1, int(ux(5.0)):int(ux(-4.8))] *= 0.7
    # cowl flaps & the engine cowl joint
    for k in range(7):
        c = int(ux(5.2 - k * 0.22)); img[int(0.10 * H):int(0.40 * H), c:c + 1] *= 0.72; img[int(0.60 * H):int(0.90 * H), c:c + 1] *= 0.72
    # markings: Balkenkreuz and the unit code on both sides
    ppm_u = W / 10.4; ppm_v = 155.0
    for side in (0.25, 0.75):
        rc = (side + (0.0 if side < 0.5 else 0.0)) * H
        cross(img, rc + (0.0), ux(-1.6), 0.33 * ppm_u, 0.29 * ppm_v)
    # codes: S2+ in front of the cross, AM behind; starboard (v~0.25) reads mirrored in u, port is mirrored in v
    cw = 0.035 * ppm_u; ch = 0.043 * ppm_v
    rc_s = 0.30 * H; rc_p = 0.70 * H
    text(img, 'S2+', rc_s, ux(-0.75), cw, ch, mirror_c=True)
    text(img, 'AM', rc_s, ux(-0.02), cw, ch, mirror_c=True)
    text(img, 'S2+', rc_p, ux(-0.02), cw, ch, mirror_r=True)
    text(img, 'AM', rc_p, ux(-0.75), cw, ch, mirror_r=True)
    # grime and wear
    gr = fbm(W, H, 60, 20, 41, 3)
    img *= (0.93 + 0.07 * gr)[:, :, None]
    img *= (0.96 + 0.04 * vnoise(W, H, 3, 3, 53))[:, :, None]
    # chipped paint along the canopy base and spine
    chips = (vnoise(W, H, 5, 3, 61) > 0.82) & (np.abs(db - 0.5) < 0.12)
    img = np.where(chips[:, :, None], img * 0.55 + 0.25, img)
    return np.clip(img, 0, 1)

WING_X0, WING_X1 = 0.3, 6.95
def paint_wing(vtab):
    W, H = 1024, 512
    cm = camo_field(W, H, 17, (110, 66), 3)
    img = PAL[cm].copy()
    vv = ((np.arange(H) + 0.5) / H)[:, None] + np.zeros((1, W), np.float32)
    top = vv > 0.5
    img = np.where(top[:, :, None], img, BLUE + np.zeros_like(img))
    ux = lambda x: (x - WING_X0) / (WING_X1 - WING_X0) * W
    vt = lambda xc: np.interp(xc, vtab['top_x'], vtab['top_v']) * H
    vb = lambda xc: np.interp(xc, vtab['bot_x'], vtab['bot_v']) * H
    # yellow undersides of the wing tips
    fill(img, 0, H * 0.5, ux(5.95), W, YEL)
    # panel lines on both surfaces: hinge lines, aileron/flap breaks, gun panels
    for xc in (0.28, 0.72, 0.84):
        for rr in (vt(xc), vb(xc)):
            r = int(rr); img[r - 1:r + 1, int(ux(0.5)):int(ux(6.7))] *= 0.62
    for x in (1.5, 3.4, 4.7, 5.95):
        c = int(ux(x)); img[:, c - 1:c + 1] *= 0.65
    # walkway at the root, top
    fill(img, vt(0.35), vt(0.62), ux(0.4), ux(1.35), BLACK, 0.55)
    # crosses, top and bottom of the outer panel
    sx = 0.62 * (W / (WING_X1 - WING_X0)); sy_top = 0.62 * 111.0; sy_bot = 0.62 * 111.0
    cross(img, vt(0.52), ux(4.95), sx, sy_top)
    cross(img, vb(0.52), ux(4.75), sx, sy_bot)
    # leading-edge wear and soot, rivet rows
    for rr in (vt(0.02), vb(0.02)):
        r = int(rr)
        for dr in range(-3, 4):
            wear = vnoise(W, 1, 3, 1, 70 + dr)[0] > 0.45
            img[r + dr, wear] = img[r + dr, wear] * 0.5 + 0.35
    gr = fbm(W, H, 50, 20, 43, 3)
    img *= (0.92 + 0.08 * gr)[:, :, None]
    img *= (0.96 + 0.04 * vnoise(W, H, 3, 3, 59))[:, :, None]
    return np.clip(img, 0, 1)

def to_image(name, arr):
    H, W, _ = arr.shape
    img = bpy.data.images.new(name, W, H)
    px = np.ones((H, W, 4), np.float32); px[:, :, :3] = arr
    img.pixels = px.ravel().tolist(); img.pack()
    img.file_format = 'JPEG'
    return img

# ------------------------------------------------------------------ geometry helpers
def loft_bm(bm, rings, us, vs, closed=True, caps=(True, True), mi=0):
    uvl = bm.loops.layers.uv.verify()
    R = len(rings); N = len(rings[0])
    Vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    nk = N if closed else N - 1
    faces = []
    for i in range(R - 1):
        for k in range(nk):
            k2 = (k + 1) % N
            try: f = bm.faces.new((Vs[i][k], Vs[i][k2], Vs[i + 1][k2], Vs[i + 1][k]))
            except ValueError: continue
            f.smooth = True; f.material_index = mi; faces.append(f)
            v2 = vs[k + 1] if k + 1 < N else 1.0
            for l, c in zip(f.loops, ((us[i], vs[k]), (us[i], v2), (us[i + 1], v2), (us[i + 1], vs[k]))): l[uvl].uv = c
    for ci, flag in ((0, caps[0]), (R - 1, caps[1])):
        if flag and closed:
            try: f = bm.faces.new(Vs[ci])
            except ValueError: continue
            f.smooth = True; f.material_index = mi; faces.append(f)
            for l, vtx in zip(f.loops, range(N)): l[uvl].uv = (us[ci], vs[vtx])
    return faces

def finish(bm, name, mats, loc=(0, 0, 0), recalc=True):
    if recalc: bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    for p in me.polygons: pass
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); ob.location = loc
    return ob

def box(bm, c, s, rot=None, mi=0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    M = Matrix.Translation(V(c)) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4)) @ Matrix.Diagonal((s[0], s[1], s[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=r['verts'])
    for f in set(f for v in r['verts'] for f in v.link_faces): f.material_index = mi

def cyl(bm, p0, p1, r0, r1=None, seg=10, mi=0):
    p0 = V(p0); p1 = V(p1); d = p1 - p0; L = d.length
    if L < 1e-5: return
    if r1 is None: r1 = r0
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=L)
    q = V((0, 0, 1)).rotation_difference(d.normalized())
    M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=r['verts'])
    for f in set(f for v in r['verts'] for f in v.link_faces): f.material_index = mi

def tube(bm, pts, r, seg=5, mi=0):
    for a, b in zip(pts[:-1], pts[1:]): cyl(bm, a, b, r, r, seg, mi)

def sphere(bm, c, r, mi=0, sc=(1, 1, 1)):
    rr = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=r)
    M = Matrix.Translation(V(c)) @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=rr['verts'])
    for f in set(f for v in rr['verts'] for f in v.link_faces): f.material_index = mi

def smooth_arr(a, passes=2):
    k = np.array([1, 2, 3, 2, 1], np.float32); k /= k.sum()
    out = a.copy()
    for _ in range(passes):
        p = np.pad(out, 2, mode='edge'); out = np.convolve(p, k, mode='valid')
    out[0] = a[0]; out[-1] = a[-1]
    return out

def thick(xc, t):
    return 5 * t * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1015 * xc ** 4) + 0.0035

# unit profile ring (bottom TE -> LE -> top TE) and its arc-length v parameter
M_AF = 12
XC_BOT = 0.5 * (1 + np.cos(np.pi * np.arange(M_AF + 1) / M_AF))            # 1 .. 0
XC_TOP = 0.5 * (1 - np.cos(np.pi * np.arange(1, M_AF + 1) / M_AF))         # >0 .. 1
AF_XC = np.concatenate([XC_BOT, XC_TOP]); AF_SG = np.concatenate([-np.ones(M_AF + 1), np.ones(M_AF)])
_pts = np.stack([AF_XC, AF_SG * thick(AF_XC, 0.12)], 1)
_arc = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(_pts, axis=0).T))])
AF_V = (_arc / _arc[-1]).tolist()
VTAB = {'bot_x': XC_BOT[::-1], 'bot_v': np.array(AF_V[:M_AF + 1])[::-1], 'top_x': XC_TOP, 'top_v': np.array(AF_V[M_AF + 1:])}

def af_ring(P, C, T, t):
    """P = leading-edge point, C = chord vector (to the trailing edge), T = unit thickness direction"""
    L = C.length
    return [P + C * float(xc) + T * float(sg * thick(xc, t) * L) for xc, sg in zip(AF_XC, AF_SG)]

# ------------------------------------------------------------------ build
img_f = to_image('stuka_fuselage_tex', paint_fuselage())
img_w = to_image('stuka_wing_tex', paint_wing(VTAB))
M_FUS = tex_mat('stuka_fuselage', img_f)
M_WING = tex_mat('stuka_wing', img_w)
M_G70 = mat('rlm70_green', (0.062, 0.078, 0.047), 0.0, 0.7)
M_DARK = mat('dark_metal', (0.05, 0.052, 0.05), 0.5, 0.5)
M_METAL = mat('steel', (0.34, 0.35, 0.35), 0.8, 0.4)
M_YEL = mat('yellow', (0.62, 0.45, 0.02), 0.0, 0.6)
M_TYRE = mat('tyre', (0.035, 0.035, 0.035), 0.0, 0.9)
M_GLASS = mat('glass', (0.62, 0.75, 0.80), 0.0, 0.1, alpha=0.32)
M_LEATH = mat('leather', (0.28, 0.2, 0.14), 0.0, 0.8)
M_BOMB = mat('bomb_grey', (0.2, 0.22, 0.19), 0.2, 0.55)
M_WHITE = mat('white', (0.75, 0.74, 0.68), 0.0, 0.6)

# ---- fuselage
ST = np.array([  # y, half-width, top, bottom depth
    (5.45, .50, .24, .66), (4.9, .56, .30, .72), (4.0, .60, .36, .76), (3.3, .62, .46, .74), (2.4, .60, .46, .72),
    (1.4, .56, .40, .72), (0.3, .50, .34, .66), (-0.6, .44, .22, .62), (-1.5, .38, .20, .56), (-2.4, .32, .19, .50),
    (-3.3, .24, .18, .42), (-4.1, .16, .24, .30), (-4.95, .07, .22, .12)], np.float32)
ys = np.arange(5.45, -4.96, -0.17); ys[-1] = -4.95
ySt = ST[::-1, 0]
cols = [smooth_arr(np.interp(ys[::-1], ySt, ST[::-1, k])[::-1]) for k in (1, 2, 3)]
NR = 28
def fus_ring(y, w, zt, zb, n=3.1):
    out = []
    for k in range(NR):
        th = 2 * math.pi * k / NR; s = math.sin(th); c = math.cos(th)
        x = w * math.copysign(abs(s) ** (2 / n), s)
        z = -zb * abs(c) ** (2 / n) if c > 0 else zt * abs(c) ** (2 / n)
        out.append(V((x, float(y), z)))
    return out
rings = [fus_ring(y, cols[0][i], cols[1][i], cols[2][i]) for i, y in enumerate(ys)]
us = [(5.45 - y) / 10.4 for y in ys]
vs = [k / NR for k in range(NR)]
bm = bmesh.new()
loft_bm(bm, rings, us, vs, True, (True, True))
body = finish(bm, 'stuka_body', [M_FUS])

# ---- wings
WK = dict(x=[0.3, 1.5, 4.0, 6.45], le=[3.2, 3.2, 3.15, 3.05], ch=[3.1, 2.85, 2.09, 1.35], zc=[-0.5, -0.95, -0.72, -0.45], th=[.17, .15, .12, .10])
def wk(key, x): return float(np.interp(x, WK['x'], WK[key]))
def wing_secs():
    xs = list(np.arange(0.3, 6.45, 0.35)) + [6.45]
    out = [(x, 1.0) for x in xs]
    for ph in (0.3, 0.6, 0.9, 1.15, 1.35, 1.5): out.append((6.45 + 0.5 * math.sin(ph), math.cos(ph)))
    return out
def wing_rings(sd):
    rings, us_ = [], []
    for x, f in wing_secs():
        le = wk('le', x); ch = wk('ch', x); zc = wk('zc', x); th = wk('th', x)
        le2 = le - 0.3 * ch + 0.3 * ch * f; ch2 = ch * f
        P = V((sd * x, le2, zc)); C = V((0, -ch2, 0)); T = V((0, 0, 1))
        rings.append(af_ring(P, C, T, th)); us_.append((x - WING_X0) / (WING_X1 - WING_X0))
    return rings, us_
for sd, nm in ((1, 'R'), (-1, 'L')):
    rg, uu = wing_rings(sd)
    bm = bmesh.new(); loft_bm(bm, rg, uu, AF_V, True, (True, True))
    finish(bm, 'stuka_wing_' + nm, [M_WING])

# ---- tail: fin and tailplane use the wing's paint (top colours only on the fin)
fin = [(0.2, -3.05, 1.95), (0.9, -3.35, 1.65), (1.4, -3.6, 1.35)]
rings, uu = [], []
secs = [(z, le, ch, 1.0) for z, le, ch in fin]
for ph in (0.3, 0.6, 0.9, 1.15, 1.35, 1.5):
    z = 1.4 + 0.3 * math.sin(ph); f = math.cos(ph)
    le = -3.6 - 0.12 * math.sin(ph); ch = 1.35
    secs.append((z, le - 0.3 * ch + 0.3 * ch * f, ch * f, f))
for z, le, ch, f in secs:
    ch2 = ch if f == 1.0 else ch
    rings.append(af_ring(V((0, le, z)), V((0, -ch2, 0)), V((1, 0, 0)), 0.095)); uu.append((z - 0.2) / 1.8 * 0.5)
bm = bmesh.new(); loft_bm(bm, rings, uu, [0.55 + 0.4 * v for v in AF_V], True, (True, True))
finish(bm, 'stuka_fin', [M_WING])
for sd, nm in ((1, 'R'), (-1, 'L')):
    rings, uu = [], []
    xs = [(0.1, -3.25, 1.0), (1.0, -3.25, 1.0), (2.0, -3.25, 1.0), (2.3, -3.25, 1.0)]
    secs = [(x, le, ch, 1.0) for x, le, ch in xs]
    for ph in (0.5, 1.0, 1.3):
        x = 2.3 + 0.22 * math.sin(ph); f = max(0.35, math.cos(ph))
        le = -3.25; ch = 1.0
        secs.append((x, le - 0.3 * ch + 0.3 * ch * f, ch * f, f))
    for x, le, ch, f in secs:
        rings.append(af_ring(V((sd * x, le, 0.30)), V((0, -ch, 0)), V((0, 0, 1)), 0.09)); uu.append(x / 2.6 * 0.5)
    bm = bmesh.new(); loft_bm(bm, rings, uu, AF_V, True, (True, True))
    finish(bm, 'stuka_stab_' + nm, [M_WING])

# ---- glasshouse (open shell, double sided) and frames
GS = [(2.95, .50, .30), (2.6, .78, .36), (2.0, .86, .40), (1.2, .88, .40), (0.7, .80, .40), (0.4, .72, .36), (0.25, .55, .26)]
BELT = 0.33
def glass_ring(y, top, w, N=11, grow=1.0):
    out = []
    for k in range(N):
        ph = math.pi * k / (N - 1)
        c = math.cos(ph); s = math.sin(ph)
        x = w * grow * math.copysign(abs(c) ** (2 / 2.6), c); z = BELT + (top - BELT) * grow * (abs(s) ** (2 / 2.6)) - (grow - 1) * 0
        out.append(V((x, y, z)))
    return out
bm = bmesh.new()
loft_bm(bm, [glass_ring(y, t, w) for y, t, w in GS], [i / (len(GS) - 1) for i in range(len(GS))], [k / 10 for k in range(11)], False, (False, False))
finish(bm, 'stuka_glass', [M_GLASS], recalc=False)

det_dark = bmesh.new(); det_metal = bmesh.new(); det_g70 = bmesh.new(); det_yel = bmesh.new(); det_leath = bmesh.new(); det_tyre = bmesh.new(); det_white = bmesh.new()
for y, t, w in GS[1:-1]:
    ring = glass_ring(y, t, w, 13, 1.012)
    tube(det_dark, ring, 0.016, 4)
tube(det_dark, [glass_ring(y, t, w, 13, 1.012)[6] for y, t, w in GS], 0.016, 4)               # spine
for kk in (2, 10): tube(det_dark, [glass_ring(y, t, w, 13, 1.012)[kk] for y, t, w in GS], 0.014, 4)
for sd in (-1, 1): tube(det_dark, [V((sd * (w * 1.01), y, BELT)) for y, t, w in GS], 0.016, 4)     # belt rails
# seats, crew and the rear gun
for (y, sd_) in ((1.8, 1), (0.62, -1)):
    box(det_leath, (0, y - 0.1 * sd_, 0.42), (0.36, 0.1, 0.45)); box(det_leath, (0, y, 0.18), (0.36, 0.36, 0.1))
    sphere(det_leath, (0, y + 0.05 * sd_, 0.66), 0.115, 0, (1, 1.05, 1.0)); box(det_dark, (0, y + 0.02 * sd_, 0.74), (0.26, 0.28, 0.04))
box(det_dark, (0, 2.75, 0.42), (0.6, 0.3, 0.16))                                                      # instrument coaming
cyl(det_metal, (0, -0.05, 0.3), (0, -0.05, 0.5), 0.03, 0.03, 6)
for sx in (-0.07, 0.07): cyl(det_dark, (sx, -0.1, 0.52), (sx, -1.0, 0.54), 0.017, 0.017, 6)       # twin MG 81Z
tube(det_metal, [V((-0.2, -0.05, 0.34)), V((-0.2, -0.05, 0.6)), V((0.2, -0.05, 0.6)), V((0.2, -0.05, 0.34))], 0.012, 4)
# ---- engine details: exhaust stacks, intake, cowl lip, chin radiator
for sd in (-1, 1):
    for k in range(6):
        y = 5.0 - k * 0.28
        p0 = V((sd * 0.58, y, -0.25)); cyl(det_dark, p0, p0 + V((sd * 0.07, -0.06, -0.02)), 0.035, 0.04, 6)
box(det_dark, (0, 4.1, 0.4), (0.35, 0.5, 0.14))
for sx in (-0.2, 0.2): cyl(det_dark, (sx, 5.0, 0.27), (sx, 5.4, 0.27), 0.018, 0.018, 6)             # MG 17 troughs (muzzle blast tubes)
cir = [V((math.sin(2 * math.pi * k / 20) * 0.5, 5.44, -0.22 + math.cos(2 * math.pi * k / 20) * 0.45)) for k in range(21)]; tube(det_metal, cir, 0.022, 4)
rings = []
for y, h, w in ((4.75, .06, .28), (4.5, .38, .32), (3.9, .38, .32), (3.7, .06, .26)):
    rr = []
    for k in range(14):
        th = 2 * math.pi * k / 14
        rr.append(V((w * math.sin(th) * 0.9, y, -0.80 + 0.5 * h * math.cos(th))))
    rings.append(rr)
bm = bmesh.new(); loft_bm(bm, rings, [i / 3 for i in range(4)], [k / 14 for k in range(14)], True, (True, True))
finish(bm, 'stuka_chin', [M_DARK])
# ---- landing gear: big spats, wheels, siren mounts, tail wheel
def spat_rings():
    out = []
    for z, ax, ayf, ayb, cy in ((-0.95, .18, .5, .55, 3.15), (-1.4, .24, .75, .9, 3.0), (-1.8, .26, .8, .9, 3.0), (-2.1, .2, .55, .5, 3.3), (-2.2, .1, .3, .3, 3.3)):
        rr = []
        for k in range(16):
            th = 2 * math.pi * k / 16; cth = math.cos(th)
            rr.append(V((ax * math.sin(th), cy + (ayf if cth > 0 else ayb) * cth, z)))
        out.append(rr)
    return out
for sd, nm in ((1, 'R'), (-1, 'L')):
    gx = sd * 1.45
    rg = [[V((gx + p.x, p.y, p.z)) for p in ring] for ring in spat_rings()]
    bm = bmesh.new(); loft_bm(bm, rg, [i / 4 for i in range(5)], [k / 16 for k in range(16)], True, (True, True))
    finish(bm, 'stuka_spat_' + nm, [M_G70])
    cyl(det_tyre, (gx - 0.14, 3.3, -2.1), (gx + 0.14, 3.3, -2.1), 0.5, 0.5, 20)
    cyl(det_metal, (gx - 0.16, 3.3, -2.1), (gx + 0.16, 3.3, -2.1), 0.22, 0.22, 14)
    cyl(det_metal, (gx, 3.75, -1.45), (gx, 4.0, -1.45), 0.04, 0.04, 6)                                  # siren mount
    cyl(det_metal, (gx - sd * 0.15, 2.9, -0.95), (gx - sd * 0.15, 2.9, -1.8), 0.04, 0.04, 6)    # struts peeking out
    # wing guns, dive-brake plates, pitot
    gxm = sd * 3.5; cyl(det_dark, (gxm, wk('le', 3.5) - 0.2, wk('zc', 3.5) - 0.03), (gxm, wk('le', 3.5) + 0.55, wk('zc', 3.5) - 0.03), 0.022, 0.022, 6)
    if sd < 0: cyl(det_metal, (-6.0, wk('le', 6.0) + 0.1, wk('zc', 6.0) + 0.05), (-6.0, wk('le', 6.0) + 0.95, wk('zc', 6.0) + 0.05), 0.012, 0.012, 5)
    # light-bomb racks
    for i in range(4):
        x = 3.4 + i * 0.5
        zb = wk('zc', x) - wk('th', x) * wk('ch', x) * 0.55
        box(det_metal, (sd * x, wk('le', x) - 1.0, zb - 0.04), (0.05, 0.5, 0.1))
# trapeze arms for the big bomb
for sd in (-1, 1):
    cyl(det_metal, (sd * 0.1, 2.5, -0.7), (sd * 0.33, 2.4, -1.2), 0.025, 0.025, 6); cyl(det_metal, (sd * 0.1, 1.5, -0.7), (sd * 0.33, 1.6, -1.2), 0.025, 0.025, 6)
# tail wheel, struts, antenna, aerial
cyl(det_metal, (0, -4.4, -0.3), (0, -4.5, -0.75), 0.04, 0.04, 6); cyl(det_tyre, (-0.07, -4.5, -0.92), (0.07, -4.5, -0.92), 0.17, 0.17, 12)
for sd in (-1, 1): cyl(det_metal, (sd * 0.1, -3.9, -0.25), (sd * 1.4, -3.8, 0.28), 0.025, 0.025, 6)
cyl(det_dark, (0, 0.75, 0.0), (0, 0.75, 0), 0.01, 0.01, 4)
cyl(det_dark, (0, 1.1, 0.85), (0, 1.1, 1.6), 0.012, 0.012, 4); cyl(det_dark, (0, 1.1, 1.6), (0, -3.9, 1.62), 0.004, 0.004, 3)
for nm, bmx, mm in (('stuka_d_dark', det_dark, M_DARK), ('stuka_d_metal', det_metal, M_METAL), ('stuka_d_leather', det_leath, M_LEATH),
                    ('stuka_d_tyre', det_tyre, M_TYRE), ('stuka_d_yellow', det_yel, M_YEL)):
    finish(bmx, nm, [mm], recalc=False)
det_g70.free(); det_white.free()

# ---- propeller (VDM three-blade) with spinner. Object origin = hub centre so the game can spin it about its own nose axis.
HUB = V((0, 5.45, -0.2))
bm = bmesh.new()
sp_rings, sp_us = [], []
for k, yy in enumerate(np.linspace(0, 0.75, 8)):
    r = 0.32 * math.sqrt(max(0.0, 1 - (yy / 0.8) ** 2)) + 0.012
    sp_rings.append([V((r * math.sin(2 * math.pi * j / 14), yy, r * math.cos(2 * math.pi * j / 14))) for j in range(14)]); sp_us.append(k / 7)
loft_bm(bm, sp_rings, sp_us, [j / 14 for j in range(14)], True, (True, True), 0)
for a in range(3):
    al = a * 2 * math.pi / 3 + 0.4
    R = V((math.sin(al), 0, math.cos(al))); Tn = V((math.cos(al), 0, -math.sin(al)))
    pit = math.radians(28); wv = V((0, 1, 0)) * math.cos(pit) + Tn * math.sin(pit); nv = R.cross(wv).normalized()
    rr_ = [(0.3, 0.09), (0.55, 0.16), (0.9, 0.22), (1.2, 0.21), (1.4, 0.16), (1.55, 0.08)]
    ringsb = [[V((0, 0.22, 0)) + R * r + wv * (w / 2) * sx + nv * 0.022 * sy for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))] for r, w in rr_]
    loft_bm(bm, ringsb[:4], [0, 0.3, 0.6, 1.0], [0, 0.25, 0.5, 0.75], True, (True, False), 0)
    loft_bm(bm, ringsb[3:], [0, 0.5, 1.0], [0, 0.25, 0.5, 0.75], True, (False, True), 1)     # yellow tips
    cyl(bm, V((0, 0.22, 0)) + R * 0.08, V((0, 0.22, 0)) + R * 0.32, 0.06, 0.05, 8, 0)
for ob_f in bm.faces: ob_f.smooth = True
prop = finish(bm, 'prop', [M_DARK, M_YEL], loc=tuple(HUB))

# ---- siren propellers (Jericho trumpets) on the spat fronts: origin at the pivot, spun about the nose axis
for sd, nm in ((1, 'siren_R'), (-1, 'siren_L')):
    bm = bmesh.new()
    box(bm, (0, 0, 0), (0.95, 0.025, 0.07)); box(bm, (0, 0, 0), (0.07, 0.025, 0.95)); cyl(bm, (0, -0.05, 0), (0, 0.06, 0), 0.07, 0.04, 8)
    finish(bm, nm, [M_DARK], loc=(sd * 1.45, 4.02, -1.45), recalc=False)

# ---- bombs: SC 500 on the trapeze, eight SC 50 under the outer wings
def bomb(name, L, R, loc, band=True, fins=0.45):
    bm = bmesh.new(); rings = []; us_ = []
    prof = [(-0.5 * L, 0.35), (-0.4 * L, 0.7), (-0.15 * L, 0.97), (0.15 * L, 1.0), (0.32 * L, 0.93), (0.43 * L, 0.7), (0.49 * L, 0.32), (0.5 * L, 0.05)]
    for i, (yy, f) in enumerate(prof):
        rings.append([V((R * f * math.sin(2 * math.pi * j / 12), yy, R * f * math.cos(2 * math.pi * j / 12))) for j in range(12)]); us_.append(i / 7)
    loft_bm(bm, rings, us_, [j / 12 for j in range(12)], True, (True, True), 0)
    if band: cyl(bm, (0, 0.2 * L, 0), (0, 0.27 * L, 0), R * 1.01, R * 1.01, 12, 1)
    for k in range(4):
        a = k * math.pi / 2; d = V((math.sin(a), 0, math.cos(a)))
        box(bm, d * R * 1.1 + V((0, -0.42 * L, 0)), (0.02, 0.24 * L, R * 1.0), Matrix.Rotation(a, 3, 'Y'), 0)
    return finish(bm, name, [M_BOMB, M_YEL], loc=loc)
bomb('bomb_heavy', 1.75, 0.235, (0, 2.0, -1.38))
k = 0
for sd in (-1, 1):
    for i in range(4):
        x = 3.4 + i * 0.5
        zb = wk('zc', x) - wk('th', x) * wk('ch', x) * 0.55
        bomb('bomb_l%d' % k, 1.0, 0.1, (sd * x, wk('le', x) - 1.0, zb - 0.2), False, 0.4); k += 1

# ------------------------------------------------------------------ export + previews
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        for p in ob.data.polygons: p.use_smooth = p.use_smooth
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, 'stuka.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_image_format='JPEG', export_jpeg_quality=85)
print('STUKA EXPORTED', os.path.getsize(glb), 'bytes', len(bpy.data.objects), 'objects')

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x = 1600; sc.render.resolution_y = 800
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.55, 0.62, 0.7)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 35
def shot(fname, loc, tgt=(0, 0, -0.3)):
    cam.location = V(loc); d = V(tgt) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, fname); bpy.ops.render.render(write_still=True)
shot('stuka_a.png', (17, 14, 4.5))          # front three-quarter, starboard
shot('stuka_b.png', (-16, -13, 5))          # rear three-quarter, port
shot('stuka_c.png', (24, 0.5, 0.0), (0, 0, 0))       # starboard side
shot('stuka_d.png', (0.2, 0.2, 26), (0, 0, 0))       # from above
shot('stuka_e.png', (9, 14, -7), (0, 0, -0.5))       # from below
print('STUKA DONE')
