import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Quaternion
V = Vector
TEX = os.path.join(OUT, 'textures')
# ============================================================ German rifleman, 1943, rigged (Mixamo-style bone names so the game's bone lookups work)
# Blender axes: +Z up, character faces -Y, his left side is +X. Height to top of helmet about 1.80 m.

# ---------------------------------------------------------------- materials
_IMG = {}; MATS = []; MIDX = {}
def tmat(name, rough=0.85):
    if name not in _IMG: _IMG[name] = bpy.data.images.load(os.path.join(TEX, name + '.png'))
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = _IMG[name]; nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    MIDX[name] = len(MATS); MATS.append(m); return MIDX[name]
M_WOOL = tmat('wool', 0.95); M_SKIN = tmat('skin_body', 0.6); M_FACE = tmat('face_a', 0.55); M_LB = tmat('leather_black', 0.55); M_LR = tmat('leather_brown', 0.6)
M_COL = tmat('collar', 0.95); M_LIT = tmat('litzen', 0.9); M_CAN = tmat('canvas', 0.95); M_HELM = tmat('helmet', 0.7); M_MET = tmat('metal', 0.45)

# ---------------------------------------------------------------- skeleton (name, parent, head, tail)
def mir(p, s): return (p[0] * s, p[1], p[2])
BONES = [('Hips', None, (0, 0, 0.93), (0, 0, 1.03)), ('Spine', 'Hips', (0, 0, 1.03), (0, 0, 1.16)), ('Spine1', 'Spine', (0, 0, 1.16), (0, 0, 1.30)),
         ('Spine2', 'Spine1', (0, 0, 1.30), (0, 0, 1.43)), ('Neck', 'Spine2', (0, 0, 1.43), (0, 0, 1.55)), ('Head', 'Neck', (0, 0, 1.55), (0, 0, 1.78))]
for nm, s in (('Left', 1), ('Right', -1)):
    BONES += [(nm + 'Shoulder', 'Spine2', mir((0.03, 0, 1.40), s), mir((0.19, 0, 1.42), s)), (nm + 'Arm', nm + 'Shoulder', mir((0.19, 0, 1.42), s), mir((0.34, 0, 1.16), s)),
              (nm + 'ForeArm', nm + 'Arm', mir((0.34, 0, 1.16), s), mir((0.47, 0, 0.935), s)), (nm + 'Hand', nm + 'ForeArm', mir((0.47, 0, 0.935), s), mir((0.56, 0, 0.78), s)),
              (nm + 'UpLeg', 'Hips', mir((0.09, 0, 0.93), s), mir((0.095, 0, 0.50), s)), (nm + 'Leg', nm + 'UpLeg', mir((0.095, 0, 0.50), s), mir((0.10, 0, 0.09), s)),
              (nm + 'Foot', nm + 'Leg', mir((0.10, 0, 0.09), s), mir((0.105, -0.13, 0.045), s)), (nm + 'ToeBase', nm + 'Foot', mir((0.105, -0.13, 0.045), s), mir((0.105, -0.20, 0.03), s))]
BP = {n: (V(h), V(t)) for n, p, h, t in BONES}

def seg_dist(p, a, b):
    ab = b - a; t = max(0.0, min(1.0, (p - a).dot(ab) / ab.dot(ab))); return (p - (a + ab * t)).length

# ---------------------------------------------------------------- geometry accumulation (one merged mesh, one material slot per texture)
bm = bmesh.new(); UVL = bm.loops.layers.uv.new('UVMap'); VINFO = []

def addv(p, cand, sig):
    v = bm.verts.new(p); VINFO.append((v, cand, sig)); return v

def addf(vs, uvs, mat, flip=False):
    if flip: vs = vs[::-1]; uvs = uvs[::-1]
    try: f = bm.faces.new(vs)
    except ValueError: return None
    for l, uv in zip(f.loops, uvs): l[UVL].uv = uv
    f.material_index = mat; return f

def loft(rings, nseg, mat, tile, cand, sig=0.06, closed=False, caps=(True, True), front=(0, -1, 0), e=1.0):
    """rings = [(center, a, b[, front])]; a/b semi-axes along the two ring axes; e<1 squares the section"""
    n = len(rings); cs = [V(r[0]) for r in rings]; fr0 = V(front); P = []; dist = [0.0]
    for i in range(1, n): dist.append(dist[-1] + (cs[i] - cs[i - 1]).length)
    if closed: total = dist[-1] + (cs[0] - cs[-1]).length
    for i, r in enumerate(rings):
        t = (cs[(i + 1) % n] - cs[(i - 1) % n]) if closed else (cs[min(i + 1, n - 1)] - cs[max(i - 1, 0)])
        t = t.normalized(); fr = V(r[3]) if len(r) > 3 else fr0
        vv = fr - t * fr.dot(t)
        if vv.length < 1e-4: vv = V((1, 0, 0)) - t * t.x
        vv.normalize(); uu = t.cross(vv).normalized(); ring = []
        for k in range(nseg):
            ph = 2 * math.pi * k / nseg; c_, s_ = math.cos(ph), math.sin(ph)
            c_ = math.copysign(abs(c_) ** e, c_); s_ = math.copysign(abs(s_) ** e, s_)
            ring.append(addv(cs[i] + uu * (c_ * r[1]) + vv * (s_ * r[2]), cand, sig))
        P.append((ring, 2 * math.pi * math.sqrt((r[1] ** 2 + r[2] ** 2) / 2)))
    cnt = n if closed else n - 1
    flip = None
    for i in range(cnt):
        j = (i + 1) % n
        for k in range(nseg):
            k2 = (k + 1) % nseg
            vs = [P[i][0][k], P[i][0][k2], P[j][0][k2], P[j][0][k]]
            di = dist[i]; dj = dist[j] if j > i else total
            uvs = [(k / nseg * P[i][1] / tile, di / tile), ((k + 1) / nseg * P[i][1] / tile, di / tile), ((k + 1) / nseg * P[j][1] / tile, dj / tile), (k / nseg * P[j][1] / tile, dj / tile)]
            if flip is None:
                ctr = (vs[0].co + vs[1].co + vs[2].co + vs[3].co) / 4; nrm = (vs[1].co - vs[0].co).cross(vs[3].co - vs[0].co)
                flip = nrm.dot(ctr - cs[i]) < 0
            addf(vs, uvs, mat, flip)
    if not closed:
        for idx, ring_i, other in ((0, 0, 1), (1, n - 1, n - 2)):
            if not caps[idx]: continue
            ctr = addv(cs[ring_i], cand, sig); ring = P[ring_i][0]; away = (cs[ring_i] - cs[other]).normalized(); rad = rings[ring_i][1] / tile
            for k in range(nseg):
                k2 = (k + 1) % nseg
                vs = [ring[k], ring[k2], ctr]; nrm = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
                ph1, ph2 = 2 * math.pi * k / nseg, 2 * math.pi * (k + 1) / nseg
                uvs = [(0.5 + math.cos(ph1) * 0.25, 0.5 + math.sin(ph1) * 0.25), (0.5 + math.cos(ph2) * 0.25, 0.5 + math.sin(ph2) * 0.25), (0.5, 0.5)]
                addf(vs, uvs, mat, nrm.dot(away) < 0)

def catmull(pts, per=4):
    P = [V(p) for p in pts]; out = []
    for i in range(len(P) - 1):
        p0 = P[max(i - 1, 0)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(i + 2, len(P) - 1)]
        for s in range(per):
            t = s / per; t2 = t * t; t3 = t2 * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1]); return out

# ---------------------------------------------------------------- torso surface (tunic) as a function of height
TORSO = [(0.82, 0.180, 0.125), (0.90, 0.178, 0.122), (1.00, 0.165, 0.112), (1.08, 0.152, 0.105), (1.20, 0.165, 0.112), (1.30, 0.185, 0.124), (1.38, 0.200, 0.118), (1.43, 0.192, 0.105), (1.452, 0.150, 0.092), (1.475, 0.095, 0.075), (1.50, 0.068, 0.068)]
def torso_rad(z):
    if z <= TORSO[0][0]: return TORSO[0][1], TORSO[0][2]
    for (z0, a0, b0), (z1, a1, b1) in zip(TORSO, TORSO[1:]):
        if z <= z1: t = (z - z0) / (z1 - z0); return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
    return TORSO[-1][1], TORSO[-1][2]
def surf(z, phi_deg, off=0.0):
    rx, ry = torso_rad(z); ph = math.radians(phi_deg); return V((rx * math.sin(ph) * (1 + off), -ry * math.cos(ph) * (1 + off), z))
def nrm_at(z, phi_deg):
    rx, ry = torso_rad(z); ph = math.radians(phi_deg); return V((math.sin(ph) / rx, -math.cos(ph) / ry, 0)).normalized()

TC = ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'LeftShoulder', 'RightShoulder')
# tunic (field blouse) body
zs = [0.82, 0.86, 0.90, 0.96, 1.02, 1.08, 1.14, 1.20, 1.26, 1.32, 1.38, 1.42, 1.45, 1.465, 1.48, 1.495]
loft([(V((0, 0, z)), torso_rad(z)[0], torso_rad(z)[1]) for z in zs], 24, M_WOOL, 0.45, TC, 0.08)
# stand-and-fall collar
loft([(V((0, 0.004, 1.462)), 0.078, 0.074), (V((0, 0.004, 1.510)), 0.068, 0.066), (V((0, 0.004, 1.552)), 0.064, 0.062)], 20, M_COL, 0.3, ('Neck', 'Spine2'), 0.05, caps=(False, False))
# neck
loft([(V((0, 0.004, 1.43)), 0.058, 0.060), (V((0, 0.006, 1.50)), 0.054, 0.056), (V((0, 0.012, 1.560)), 0.046, 0.050), (V((0, 0.016, 1.600)), 0.038, 0.044)], 14, M_SKIN, 0.3, ('Neck', 'Head', 'Spine2'), 0.04, caps=(False, False))

# patch pockets, shoulder straps, buttons
def pbox(c, w, h, d, mat, tile, cand, sig=0.05, e=0.35, nseg=12):
    """flat patch/box on the front (-Y) with centre c, width w (x), height h (z), depth d (y)"""
    loft([(V((c[0], c[1] + d / 2, c[2])), w / 2, h / 2), (V((c[0], c[1] - d / 2, c[2])), w / 2, h / 2)], nseg, mat, tile, cand, sig, front=(0, 0, 1), e=e)
for sx in (1, -1):
    for (z, w, h) in ((1.25, 0.105, 0.115), (0.96, 0.125, 0.15)):
        x = 0.088 * sx; rx, ry = torso_rad(z); y = -ry * math.sqrt(max(0.0, 1 - (x / rx) ** 2)) - 0.004
        pbox((x, y, z), w, h, 0.014, M_WOOL, 0.3, TC, 0.06)
        if z > 1.0:
            pbox((x, y - 0.005, z + h / 2 - 0.018), w + 0.008, 0.046, 0.008, M_WOOL, 0.3, TC, 0.06, e=0.75)        # scalloped flap
            loft([(V((x, y - 0.010, z + h / 2 - 0.025)), 0.0075, 0.0075), (V((x, y - 0.016, z + h / 2 - 0.025)), 0.0075, 0.0075)], 8, M_MET, 0.05, TC, 0.06, front=(1, 0, 0))   # flap button
    loft([(V((0.105 * sx, 0.0, 1.450)), 0.021, 0.004), (V((0.175 * sx, 0.0, 1.425)), 0.021, 0.004)], 8, M_WOOL, 0.3, ('Spine2', 'LeftShoulder', 'RightShoulder'), 0.06, front=(0, 0, 1), e=0.4)   # shoulder strap
for z in (1.38, 1.30, 1.22, 1.14, 1.06, 0.98):                       # front button placket
    rx, ry = torso_rad(z); loft([(V((0, -ry - 0.002, z)), 0.007, 0.007), (V((0, -ry - 0.007, z)), 0.007, 0.007)], 8, M_MET, 0.05, TC, 0.06, front=(1, 0, 0))

for sx in (1, -1):    # two-bar collar patches
    for dz in (0.0,):
        pts = []
        for ang in (22, 34, 46, 58):
            a_ = math.radians(ang); pts.append((V((0.0715 * math.sin(a_) * sx, 0.004 - 0.0695 * math.cos(a_), 1.500)), 0.011, 0.0016, V((math.sin(a_) * sx / 0.069, -math.cos(a_) / 0.067, 0)).normalized()))
        loft(pts, 8, M_LIT, 0.04, ('Neck', 'Spine2'), 0.05, e=0.6)
# ---------------------------------------------------------------- arms (sleeve + bare hand)
for sx in (1, -1):
    nm = 'Left' if sx > 0 else 'Right'; ac = ('Spine2', nm + 'Shoulder', nm + 'Arm', nm + 'ForeArm'); sh = V(mir((0.19, 0, 1.42), sx)); el = V(mir((0.34, 0, 1.16), sx)); wr = V(mir((0.47, 0, 0.935), sx))
    d1 = (el - sh).normalized(); d2 = (wr - el).normalized()
    rings = [(sh - d1 * 0.012, 0.026, 0.028), (sh + d1 * 0.012, 0.050, 0.052), (sh + d1 * 0.05, 0.059, 0.060), (sh + d1 * 0.20, 0.056, 0.056), (el, 0.052, 0.052), (el + d2 * 0.09, 0.047, 0.047), (el + d2 * 0.19, 0.043, 0.043), (wr + d2 * 0.005, 0.045, 0.045)]
    loft(rings, 16, M_WOOL, 0.4, ac, 0.055, caps=(True, True))
    # hand: palm facing the thigh, thickness along the arm's side axis
    hd = (V(mir((0.56, 0, 0.78), sx)) - wr).normalized(); hc = ('LeftHand' if sx > 0 else 'RightHand', nm + 'ForeArm')
    loft([(wr - hd * 0.004, 0.022, 0.034), (wr + hd * 0.05, 0.020, 0.040), (wr + hd * 0.098, 0.016, 0.037)], 12, M_SKIN, 0.3, hc, 0.04)
    for fy, fl in ((-0.027, 0.070), (-0.009, 0.080), (0.009, 0.074), (0.027, 0.058)):
        b0 = wr + hd * 0.095 + V((0, fy, 0))
        loft([(b0, 0.0068, 0.0068), (b0 + hd * fl * 0.5 + V((-0.003 * sx, 0, 0)), 0.0058, 0.0058), (b0 + hd * fl + V((-0.011 * sx, 0, 0)), 0.0044, 0.0044)], 8, M_SKIN, 0.2, hc, 0.04)
    th = (wr + hd * 0.035 + V((-0.025 * sx, -0.025, 0))); loft([(wr + hd * 0.03 + V((-0.018 * sx, -0.030, 0)), 0.011, 0.011), (wr + hd * 0.075 + V((-0.022 * sx, -0.043, 0)), 0.009, 0.009), (wr + hd * 0.105 + V((-0.020 * sx, -0.052, 0)), 0.007, 0.007)], 8, M_SKIN, 0.3, hc, 0.04)   # thumb

# ---------------------------------------------------------------- legs, trousers, boots
for sx in (1, -1):
    nm = 'Left' if sx > 0 else 'Right'; lc = ('Hips', nm + 'UpLeg', nm + 'Leg', nm + 'Foot')
    X = 0.09 * sx
    loft([(V((X, 0.0, 0.985)), 0.105, 0.118), (V((X, 0, 0.90)), 0.098, 0.108), (V((X + 0.004 * sx, 0, 0.74)), 0.083, 0.088), (V((X + 0.006 * sx, 0, 0.60)), 0.071, 0.075), (V((X + 0.008 * sx, 0, 0.50)), 0.066, 0.070),
          (V((X + 0.010 * sx, 0, 0.40)), 0.060, 0.063), (V((X + 0.010 * sx, 0, 0.30)), 0.056, 0.058), (V((X + 0.010 * sx, 0, 0.23)), 0.068, 0.072), (V((X + 0.010 * sx, 0.004, 0.19)), 0.076, 0.080), (V((X + 0.010 * sx, 0.004, 0.15)), 0.070, 0.074)], 18, M_WOOL, 0.4, lc, 0.07, caps=(False, False))
    # ankle boot: shaft + foot
    BX = 0.10 * sx
    loft([(V((BX, 0.002, 0.205)), 0.060, 0.064), (V((BX, 0.004, 0.16)), 0.062, 0.066), (V((BX, 0.006, 0.10)), 0.060, 0.066), (V((BX, 0.012, 0.06)), 0.056, 0.060)], 16, M_LB, 0.25, (nm + 'Leg', nm + 'Foot'), 0.04, caps=(False, False))
    loft([(V((BX, 0.088, 0.050)), 0.040, 0.050), (V((BX, 0.045, 0.054)), 0.048, 0.054), (V((BX, -0.015, 0.044)), 0.052, 0.044), (V((BX, -0.085, 0.036)), 0.055, 0.036), (V((BX, -0.155, 0.031)), 0.048, 0.031), (V((BX, -0.190, 0.029)), 0.038, 0.029), (V((BX, -0.212, 0.025)), 0.024, 0.024), (V((BX, -0.222, 0.020)), 0.010, 0.016)],
         14, M_LB, 0.25, (nm + 'Leg', nm + 'Foot', nm + 'ToeBase'), 0.04, front=(0, 0, 1))
    tp = [(-0.075, 0.073), (-0.066, 0.095), (-0.063, 0.125), (-0.062, 0.160), (-0.062, 0.195)]
    loft([(V((BX, y - 0.003, z)), 0.022, 0.0025, (0, -1, 0.5)) for y, z in tp], 8, M_LR, 0.2, (nm + 'Leg', nm + 'Foot'), 0.04, e=0.5)      # tongue
    for y, z in tp[:-1]:   # cross laces
        loft([(V((BX - 0.020, y - 0.006, z + 0.006)), 0.0035, 0.0022, (0, -1, 0.5)), (V((BX + 0.020, y - 0.006, z - 0.002)), 0.0035, 0.0022, (0, -1, 0.5))], 6, M_LB, 0.1, (nm + 'Leg', nm + 'Foot'), 0.04, e=0.6)
    loft([(V((BX, 0.090, 0.012)), 0.043, 0.012), (V((BX, -0.010, 0.012)), 0.055, 0.012), (V((BX, -0.150, 0.012)), 0.050, 0.012), (V((BX, -0.200, 0.012)), 0.038, 0.012), (V((BX, -0.226, 0.012)), 0.014, 0.012)], 10, M_LB, 0.25, (nm + 'Foot', nm + 'ToeBase'), 0.04, front=(0, 0, 1), e=0.6)   # sole

# ---------------------------------------------------------------- head: sculpted ellipsoid, UVs are a cylindrical map of the BASE ellipsoid (the face texture is painted in the same 3D coordinates)
RX, RY = 0.072, 0.095; RZ, ZC = 0.1012, 1.668; RZO, ZCO = 0.115, 1.66
def gauss(x, z, cx, cz, sx, sz): return math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((z - cz) / sz) ** 2))
def head_disp(x, z, fr):
    h = 0.0; xa = abs(x)
    h += 0.014 * gauss(xa, z, 0.0, 1.640, 0.0105, 0.012)                                 # nose body and tip
    h += 0.005 * gauss(xa, z, 0.0, 1.680, 0.010, 0.013)                                  # nose bridge
    h += 0.012 * gauss(xa, z, 0.0140, 1.631, 0.0065, 0.0055)                              # nostril wings
    h += 0.012 * gauss(xa, z, 0.0, 1.700, 0.042, 0.009)                                  # brow ridge
    h -= 0.010 * gauss(xa, z, 0.031, 1.685, 0.018, 0.010)
    h += 0.004 * gauss(xa, z, 0.031, 1.695, 0.016, 0.004)                                # upper lid fold
    h -= 0.004 * gauss(xa, z, 0.003, 1.613, 0.005, 0.006)
    h -= 0.004 * gauss(xa, z, 0.030, 1.620, 0.006, 0.020)                                # nasolabial fold                                # philtrum groove                               # eye sockets
    h += 0.010 * gauss(xa, z, 0.054, 1.650, 0.016, 0.014)
    h += 0.008 * gauss(xa, z, 0.054, 1.598, 0.014, 0.018)                                # jaw angle                                # cheekbones
    h += 0.011 * gauss(xa, z, 0.0, 1.600, 0.025, 0.008)                                 # lips
    h -= 0.005 * gauss(xa, z, 0.0, 1.5935, 0.026, 0.0025)                               # mouth line
    h += 0.009 * gauss(xa, z, 0.0, 1.563, 0.016, 0.012)                                  # chin
    return h * fr
NT, NL = 44, 30
HC = ('Head', 'Neck'); hv = []
for j in range(NL + 1):
    psi = math.pi * j / NL; z0 = ZC + RZ * math.cos(psi); zo = ZCO + RZO * math.cos(psi); s = math.sin(psi); row = []; zc_ = z0 if z0 >= ZC else ZC + (z0 - ZC) * 0.86
    for k in range(NT if 0 < j < NL else 1):
        th = -math.pi + 2 * math.pi * k / NT if 0 < j < NL else 0.0
        x = RX * s * math.sin(th); y = -RY * s * math.cos(th); fr = max(0.0, math.cos(th)) ** 0.6 if (0 < j < NL) else 0.0
        p = V((x, y, zc_)); n = V((x / RX ** 2, y / RY ** 2, (z0 - ZC) / RZ ** 2)); n.normalize() if n.length > 0 else None
        jaw = max(0.0, min(1.0, (ZCO - 0.04 - zo) / 0.07))
        p.x *= 1 - 0.09 * jaw * jaw; p.y += -0.008 * jaw if fr > 0 else 0.0
        if 0 < j < NL and n.length > 0: p = p + n * head_disp(x, zo, fr)
        row.append(addv(p, HC, 0.05))
    hv.append(row)
def uvh(j, k):
    psi = math.pi * j / NL; return (k / NT, (1 + math.cos(psi)) / 2)
for j in range(NL):
    for k in range(NT):
        k2 = (k + 1) % NT
        if j == 0:
            vs = [hv[0][0], hv[1][k], hv[1][k2]]; uvs = [(( k + 0.5) / NT, 1.0), uvh(1, k), (( k + 1) / NT, uvh(1, 0)[1])]
        elif j == NL - 1:
            vs = [hv[j][k], hv[NL][0], hv[j][k2]]; uvs = [uvh(j, k), ((k + 0.5) / NT, 0.0), ((k + 1) / NT, uvh(j, 0)[1])]
        else:
            vs = [hv[j][k], hv[j + 1][k], hv[j + 1][k2], hv[j][k2]]; uvs = [uvh(j, k), uvh(j + 1, k), ((k + 1) / NT, uvh(j + 1, 0)[1]), ((k + 1) / NT, uvh(j, 0)[1])]
        # outward = away from head centre
        c = sum((v.co for v in vs), V()) / len(vs); nr = (vs[1].co - vs[0].co).cross(vs[-1].co - vs[0].co)
        addf(vs, uvs, M_FACE, nr.dot(c - V((0, 0, ZC))) < 0)
# ears
for sx in (1, -1):
    loft([(V((0.064 * sx, 0.008, 1.668)), 0.011, 0.024), (V((0.074 * sx, 0.010, 1.668)), 0.015, 0.031), (V((0.084 * sx, 0.012, 1.670)), 0.011, 0.026)], 10, M_SKIN, 0.1, ('Head',), 0.03, front=(0, 0, 1))

# ---------------------------------------------------------------- Stahlhelm M40 (open shell, front brow at 1.70, flares over the ears and the neck)
NHT, NHS = 32, 11
def zb(th): c = math.cos(th); return 1.668 + (0.074 * max(0.0, c) ** 1.4) - (0.063 * max(0.0, -c))
rings = []
for j in range(NHS + 1):
    s = max(0.03, j / NHS) if j < NHS else 1.0; row = []
    for k in range(NHT):
        th = -math.pi + 2 * math.pi * k / NHT; zbt = zb(th)
        z = zbt + (1.800 - zbt) * math.cos(s * math.pi / 2); rho = math.sin(s * math.pi / 2); rho = rho * (1 + 0.05 * max(0.0, s - 0.85) / 0.15)
        row.append(addv(V((0.102 * rho * math.sin(th), 0.014 - 0.136 * rho * math.cos(th), z)), ('Head',), 0.02))
    rings.append(row)
extra = []
for dz, dr in ((-0.007, 1.075), (0.004, 1.045)):
    row = []
    for k in range(NHT):
        th = -math.pi + 2 * math.pi * k / NHT; zbt = zb(th)
        row.append(addv(V((0.102 * dr * math.sin(th), 0.014 - 0.136 * dr * math.cos(th), zbt + dz)), ('Head',), 0.02))
    extra.append(row)
rings += extra; NR = len(rings)
def uvhm(j, k): return (k / NHT * 0.75 / 0.5, j / (NR - 1) * 0.24 / 0.5)
for j in range(NR - 1):
    for k in range(NHT):
        k2 = (k + 1) % NHT; vs = [rings[j][k], rings[j][k2], rings[j + 1][k2], rings[j + 1][k]]
        uvs = [uvhm(j, k), uvhm(j, k + 1), uvhm(j + 1, k + 1), uvhm(j + 1, k)]
        c = sum((v.co for v in vs), V()) / 4; nr = (vs[1].co - vs[0].co).cross(vs[3].co - vs[0].co)
        addf(vs, uvs, M_HELM, nr.dot(c - V((0, 0, 1.70))) < 0)
# crown
top = addv(V((0, 0.014, 1.801)), ('Head',), 0.02)
for k in range(NHT):
    k2 = (k + 1) % NHT; vs = [rings[0][k], rings[0][k2], top]; c = sum((v.co for v in vs), V()) / 3; nr = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
    addf(vs, [(0.4 + 0.05 * math.cos(k), 0.4), (0.4, 0.4), (0.4, 0.45)], M_HELM, nr.dot(c - V((0, 0, 1.70))) < 0)
for sx in (1, -1):    # ventilation rivets
    loft([(V((0.096 * sx, 0.014, 1.715)), 0.0055, 0.0055), (V((0.106 * sx, 0.014, 1.715)), 0.0055, 0.0055)], 8, M_MET, 0.05, ('Head',), 0.02, front=(0, 1, 0))
# wool neck scarf pulled up over the mouth and chin: folded layers, rolled rim and a hanging knot tail
_zs = [1.525, 1.548, 1.570, 1.592, 1.610, 1.624]
_rg = []
for i, zz in enumerate(_zs):
    f = 1 + 0.045 * math.sin(i * 2.4 + 0.7)
    t = (zz - 1.525) / 0.099
    _rg.append((V((0, 0.010 - 0.006 * t, zz)), (0.068 + 0.004 * math.sin(math.pi * t)) * f * (1 - 0.04 * t * t), (0.082 + 0.048 * min(1.0, t * 2.2)) * f))
loft(_rg, 28, M_WOOL, 0.18, ('Head', 'Neck'), 0.04, caps=(False, False))
for _z, _s in ((1.553, 1.0), (1.585, 1.0)):      # fold ridges wrapping the scarf
    loft([(V((0, 0.006, _z + 0.5 * 0.008 * k)), (0.072 + 0.002 * (k % 2)) * _s, 0.126 * _s + 0.002 * (k % 2)) for k in range(3)], 28, M_WOOL, 0.15, ('Head', 'Neck'), 0.04, caps=(False, False))
_rim = []
for i in range(28):
    ph = 2 * math.pi * i / 28
    _rim.append((V((0.062 * math.sin(ph) * 1.02, 0.004 - 0.124 * math.cos(ph), 1.606)), 0.011, 0.011))
loft(_rim, 8, M_WOOL, 0.1, ('Head', 'Neck'), 0.04, closed=True, front=(0, 0, 1))
_tail = catmull([V((0.040, -0.126, 1.580)), V((0.050, -0.130, 1.552)), V((0.046, -0.128, 1.528)), V((0.052, -0.122, 1.506))], 4)
loft([(p_, 0.008 - 0.0015 * (k / len(_tail)), 0.0035) for k, p_ in enumerate(_tail)], 8, M_WOOL, 0.15, ('Neck', 'Spine2', 'Head'), 0.05, front=(0, -1, 0), e=0.7)
# chin strap: from each side of the shell, under the chin
half = [(0.098, 0.005, 1.672), (0.092, -0.030, 1.622), (0.080, -0.070, 1.600), (0.050, -0.124, 1.585), (0.0, -0.134, 1.578)]
path = [V(p) for p in half] + [V((-p[0], p[1], p[2])) for p in half[::-1][1:]]
loft([(p, 0.009, 0.0022) for p in catmull(path, 4)], 6, M_LB, 0.2, ('Head',), 0.02, front=(0, 0, 1), e=0.5)

# ---------------------------------------------------------------- field gear
GC = ('Hips', 'Spine', 'Spine1')
rx, ry = torso_rad(1.0); belt = []
for i in range(28):
    ph = 2 * math.pi * i / 28; belt.append((V((rx * 1.03 * math.sin(ph), -ry * 1.03 * math.cos(ph), 1.0)), 0.0055, 0.022))
loft(belt, 8, M_LB, 0.25, GC, 0.05, closed=True, front=(0, 0, 1), e=0.45)
loft([(V((0, -ry * 1.03 - 0.004, 1.0)), 0.034, 0.024), (V((0, -ry * 1.03 - 0.012, 1.0)), 0.034, 0.024)], 12, M_MET, 0.1, GC, 0.04, front=(0, 0, 1), e=0.7)     # buckle
for sx in (1, -1):    # triple ammunition pouches either side of the buckle
    x = 0.088 * sx; y = -ry * math.sqrt(1 - (x / rx) ** 2) * 1.03
    pbox((x * 1.0, y - 0.028, 1.045), 0.108, 0.088, 0.050, M_LB, 0.25, GC, 0.05, e=0.3)
    pbox((x * 1.0, y - 0.056, 1.052), 0.100, 0.052, 0.006, M_LB, 0.25, GC, 0.05, e=0.3)   # flap
# Y-straps
for sx in (1, -1):
    pts = [surf(1.00, 30, 0.03), surf(1.12, 29, 0.03), surf(1.26, 30, 0.03), surf(1.40, 40, 0.03), V((0.140, -0.010, 1.452)), surf(1.40, 140, 0.03), surf(1.26, 150, 0.03), surf(1.14, 158, 0.03), surf(1.04, 170, 0.03), V((0.0, ry * 1.03, 1.02))]
    pts = [V((p.x * sx, p.y, p.z)) for p in pts]; sm = catmull(pts, 4); rg = []
    for p in sm:
        nvec = V((p.x / max(0.001, torso_rad(min(1.47, max(0.82, p.z)))[0] ** 2), p.y / max(0.001, torso_rad(min(1.47, max(0.82, p.z)))[1] ** 2), 0.12)).normalized()
        rg.append((p, 0.016, 0.0035, nvec))
    loft(rg, 8, M_LR, 0.25, ('Spine', 'Spine1', 'Spine2', 'LeftShoulder', 'RightShoulder'), 0.07, e=0.5)
loft([(V((0.150, -0.062, 0.975)), 0.020, 0.009), (V((0.151, -0.066, 0.935)), 0.020, 0.009)], 10, M_LB, 0.2, GC, 0.05, front=(0, -1, 0), e=0.5)           # bayonet frog
loft([(V((0.151, -0.068, 0.955)), 0.012, 0.0055), (V((0.153, -0.074, 0.80)), 0.011, 0.0050), (V((0.154, -0.077, 0.75)), 0.006, 0.004)], 8, M_MET, 0.15, GC, 0.05, front=(0, -1, 0), e=0.5)  # scabbard
# bread bag + canteen + gas-mask canister on the back and hips
def bag(c, w, h, d, mat, cand, e=0.3): loft([(V((c[0], c[1] - d / 2, c[2])), w / 2, h / 2), (V((c[0], c[1] + d / 2, c[2])), w / 2, h / 2)], 12, mat, 0.3, cand, 0.05, front=(0, 0, 1), e=e)
bag((0.150, 0.100, 0.850), 0.200, 0.190, 0.075, M_CAN, GC)                                   # bread bag, left rear hip
bag((0.150, 0.100, 0.935), 0.205, 0.030, 0.085, M_LB, GC)                                    # its leather flap strap
loft([(V((0.04, 0.140, 0.77)), 0.050, 0.038), (V((0.04, 0.140, 0.99)), 0.050, 0.038)], 14, M_CAN, 0.3, GC, 0.05, front=(0, 1, 0), e=0.7)   # canteen in its felt cover
loft([(V((0.04, 0.140, 0.775)), 0.040, 0.030), (V((0.04, 0.140, 0.77)), 0.040, 0.030)], 10, M_MET, 0.1, GC, 0.05, front=(0, 1, 0))
loft([(V((-0.115, 0.145, 0.78)), 0.056, 0.056), (V((-0.115, 0.145, 1.04)), 0.056, 0.056)], 14, M_MET, 0.15, GC, 0.05, front=(0, 1, 0))      # gas-mask canister
for z in (0.82, 0.88, 0.94, 1.0):    # ribs on the canister
    loft([(V((-0.115, 0.145, z)), 0.060, 0.060), (V((-0.115, 0.145, z + 0.012)), 0.060, 0.060)], 14, M_MET, 0.15, GC, 0.05, front=(0, 1, 0))

# ---------------------------------------------------------------- finish mesh, shading, vertex weights
bm.verts.index_update(); bm.normal_update()
me = bpy.data.meshes.new('german_soldier'); bm.to_mesh(me)
for m in MATS: me.materials.append(m)
try:
    me.shade_smooth()
except Exception:
    for p in me.polygons: p.use_smooth = True
obj = bpy.data.objects.new('german_soldier', me); bpy.context.scene.collection.objects.link(obj)

arm = bpy.data.armatures.new('german_rig'); ao = bpy.data.objects.new('german_rig', arm); bpy.context.scene.collection.objects.link(ao)
bpy.context.view_layer.objects.active = ao; ao.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
for n, par, h, t in BONES:
    b = arm.edit_bones.new(n); b.head = V(h); b.tail = V(t)
    if par: b.parent = arm.edit_bones[par]
bpy.ops.object.mode_set(mode='OBJECT')
obj.parent = ao; md = obj.modifiers.new('Armature', 'ARMATURE'); md.object = ao
vg = {n: obj.vertex_groups.new(name=n) for n, *_ in BONES}
for v, cand, sig in VINFO:
    ws = []
    for bn in cand:
        a, b = BP[bn]; d = seg_dist(v.co, a, b); ws.append((math.exp(-(d / sig) ** 2), bn))
    ws.sort(reverse=True); ws = ws[:4]; tot = sum(w for w, _ in ws)
    if tot < 1e-6:
        bn = min(cand, key=lambda b: seg_dist(v.co, *BP[b])); ws = [(1.0, bn)]; tot = 1.0
    for w, bn in ws: vg[bn].add([v.index], w / tot, 'REPLACE')

# ---------------------------------------------------------------- animation (hierarchical deltas in armature axes; see rot())
bpy.context.view_layer.objects.active = ao; bpy.ops.object.mode_set(mode='POSE')
PB = ao.pose.bones
for pb in PB: pb.rotation_mode = 'QUATERNION'
REST = {b.name: b.matrix_local.to_3x3().to_quaternion() for b in arm.bones}
AX = {'x': V((1, 0, 0)), 'y': V((0, 1, 0)), 'z': V((0, 0, 1))}
def Q(ax, deg): return Quaternion(AX[ax], math.radians(deg))
def setrot(bn, *rots):
    q = Quaternion((1, 0, 0, 0))
    for ax, deg in rots: q = q @ Q(ax, deg)
    r = REST[bn]; PB[bn].rotation_quaternion = r.inverted() @ q @ r
def setloc(bn, dx, dy, dz):
    PB[bn].location = REST[bn].inverted() @ V((dx, dy, dz))
def key(f):
    for pb in PB:
        pb.keyframe_insert('rotation_quaternion', frame=f)
        if pb.name == 'Hips': pb.keyframe_insert('location', frame=f)
def reset():
    for pb in PB: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
ARMIN = 18      # arms hang closer to the body than the A-pose
def new_action(name):
    ao.animation_data_create(); a = bpy.data.actions.new(name); a.use_fake_user = True; ao.animation_data.action = a; return a
def cycle(name, N, f):
    new_action(name)
    for fr in range(N + 1):
        reset(); f(2 * math.pi * fr / N); key(fr)
def gait(ph, A_t, K, k0, A_a, E0, E1, T, lean, bob, sway, armin):
    for nm, sg, p in (('Left', 1, 0.0), ('Right', -1, math.pi)):
        s_ = math.sin(ph + p); c_ = math.cos(ph + p)
        th = -A_t * s_; kn = k0 + K * max(0.0, c_) ** 1.3
        setrot(nm + 'UpLeg', ('x', th)); setrot(nm + 'Leg', ('x', kn)); setrot(nm + 'Foot', ('x', -(th + kn) * 0.55 + 6 * max(0.0, s_) ** 2)); setrot(nm + 'ToeBase', ('x', -8 * max(0.0, s_)))
        setrot(nm + 'Arm', ('x', A_a * s_), ('y', sg * armin)); setrot(nm + 'ForeArm', ('x', -(E0 + E1 * max(0.0, -s_))))
    setrot('Spine', ('z', T * math.sin(ph)), ('x', lean * 0.5)); setrot('Spine1', ('z', T * 0.6 * math.sin(ph)), ('x', lean * 0.3)); setrot('Spine2', ('z', T * 0.4 * math.sin(ph)), ('x', lean * 0.2)); setrot('Neck', ('x', -lean * 0.4)); setrot('Head', ('z', -T * 1.0 * math.sin(ph)), ('x', -lean * 0.3))
    setloc('Hips', sway * math.sin(ph), 0.0, bob * math.cos(2 * ph)); PB['Hips'].rotation_quaternion = REST['Hips'].inverted() @ Q('z', -T * 0.9 * math.sin(ph)) @ REST['Hips']
def walk(ph): gait(ph, 26, 38, 6, 20, 14, 14, 4, 4, 0.014, 0.012, ARMIN)
def run(ph): gait(ph, 44, 85, 10, 50, 75, 15, 7, 12, 0.04, 0.02, 22)
def idle(ph):
    br = math.sin(ph)
    for nm, sg in (('Left', 1), ('Right', -1)):
        setrot(nm + 'Arm', ('x', -3 + 0.6 * br), ('y', sg * ARMIN)); setrot(nm + 'ForeArm', ('x', -12 - 1.0 * br)); setrot(nm + 'Shoulder', ('z', sg * 0.7 * br))
    setrot('Spine1', ('x', 0.6 * br)); setrot('Spine2', ('x', 1.0 * br)); setrot('Neck', ('x', -0.5 * br)); setrot('Head', ('z', 2.0 * math.sin(ph / 3 + 0.5)), ('x', -0.6 * math.sin(ph + 0.6)))
    setloc('Hips', 0.008 * math.sin(ph / 3), 0.0, -0.002 * br)
cycle('idle', 90, idle); cycle('walk', 30, walk); cycle('run', 20, run)
ao.animation_data.action = bpy.data.actions['idle']; reset()
for pb in PB: pb.keyframe_insert('rotation_quaternion', frame=0) if False else None
bpy.ops.object.mode_set(mode='OBJECT'); bpy.context.scene.frame_set(0)
# rest pose for the renders: arms down a little, like the game's idle
bpy.context.view_layer.update()
