import bpy, math, os, random
from mathutils import Vector

# ---- Buildings built in game units (1 unit = 1 m). Blender x = east, y = north (game z = -y), z = up.
# Each building is a root empty named  bld_<kind>_w<W>_d<D>_f<floors>  centred on (0,0), ground at z=0.
# Visible parts are joined per material.  Solid parts also get an invisible  col_*  box: the game turns those into colliders
# (walls with window holes cut out, floors, stairs as stacked treads, rubble in steps), so you can walk in, up and out onto the roof.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
os.makedirs(OUT, exist_ok=True)

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
for blk in (bpy.data.meshes, bpy.data.materials):
    for b in list(blk):
        if b.users == 0: blk.remove(b)

TEX = OUT + '/textures/prop/'
_IMG = {}
def img(name, srgb=True):
    if name not in _IMG:
        im = bpy.data.images.load(TEX + name + '.jpg'); im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'; _IMG[name] = im
    return _IMG[name]
UVSC = {}
def tm(name, tex, scale, rough=0.92, ns=1.4, sx=None, sy=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex + '_c'); nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(tex + '_n', False); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = ns
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = rough
    for k in ('Specular IOR Level', 'Specular'):
        if k in bsdf.inputs: bsdf.inputs[k].default_value = 0.15; break
    m.diffuse_color = (0.4, 0.4, 0.4, 1); UVSC[name] = (sx or 1.0 / scale, sy or 1.0 / scale); return m

PLASTER = [tm('plaster_a', 'bplaster_a', 2.0), tm('plaster_b', 'bplaster_b', 2.0), tm('plaster_c', 'bplaster_c', 2.0)]
BRICK   = [tm('brick_a', 'bbrick_a', 1, sx=1 / 1.075, sy=1 / 0.75), tm('brick_b', 'bbrick_b', 1, sx=1 / 1.075, sy=1 / 0.75), tm('brick_c', 'bbrick_c', 1, sx=1 / 1.075, sy=1 / 0.75)]
STONE   = [tm('stone_a', 'bstone_a', 1.2), tm('stone_b', 'bstone_b', 1.2)]
PLINTH  = tm('plinth', 'bplinth', 1.2)
CAP     = tm('cap', 'bcap', 1.2)
ROOF    = tm('roof_tar', 'btar', 2.0, 0.85)
TILE    = tm('roof_tile', 'btile', 2.4, 0.8, 1.6)
WOOD    = tm('wood', 'bwood', 0.8, 0.88)
DWOOD   = tm('wood_dark', 'bdwood', 0.8, 0.9)
SHUT    = tm('shutter', 'bshut', 0.7, 0.8)
FLOOR   = tm('floor', 'bfloor', 1.6, 0.85)
CONC    = tm('concrete', 'bconc', 1.2, 0.95)
CHAR    = tm('char', 'bchar', 1.0, 0.95)
RUBM    = [tm('rub_a', 'brub_a', 0.7), tm('rub_b', 'brub_b', 0.7), tm('rub_c', 'brub_c', 0.4)]

def apply_uv(o, m):
    me = o.data; uvl = me.uv_layers.new(name='UV') if not me.uv_layers else me.uv_layers[0]; mw = o.matrix_world; sx, sy = UVSC[m.name]; m3 = mw.to_3x3()
    for poly in me.polygons:
        n = m3 @ poly.normal; ax = max(range(3), key=lambda i: abs(n[i])); a_, b_ = [(1, 2), (0, 2), (0, 1)][ax]
        for li in poly.loop_indices:
            w = mw @ me.vertices[me.loops[li].vertex_index].co; uvl.data[li].uv = (w[a_] * sx, w[b_] * sy)


FH = 3.2          # storey height
T = 0.4           # wall thickness

class B:
    def __init__(self, name, W, D, floors, ruin, seed):
        self.name = name; self.W = W; self.D = D; self.floors = floors; self.ruin = ruin
        self.rng = random.Random(seed)
        self.root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(self.root)
        self.vis = {}; self.ncol = 0; self.nobj = 0

    def _mesh(self, nm, x0, y0, z0, x1, y1, z1):
        vs = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        fs = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        me = bpy.data.meshes.new(nm); me.from_pydata(vs, [], fs); me.update()
        ob = bpy.data.objects.new(nm, me); bpy.context.collection.objects.link(ob); ob.parent = self.root
        return ob

    def deco(self, x0, y0, z0, x1, y1, z1, m, rot=None, pivot=None):
        x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1); z0, z1 = min(z0, z1), max(z0, z1)
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4: return None
        self.nobj += 1
        ob = self._mesh('v%d' % self.nobj, x0, y0, z0, x1, y1, z1)
        if rot:
            c = pivot or ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
            ob.location = c
            me = ob.data
            for v in me.vertices: v.co -= Vector(c)
            ob.rotation_euler = rot
        self.vis.setdefault(m.name, (m, []))[1].append(ob)
        return ob

    def solid(self, x0, y0, z0, x1, y1, z1, m, col=True):
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4: return
        self.deco(x0, y0, z0, x1, y1, z1, m)
        if col: self.colbox(x0, y0, z0, x1, y1, z1)

    def colbox(self, x0, y0, z0, x1, y1, z1):
        x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1); z0, z1 = min(z0, z1), max(z0, z1)
        self.ncol += 1                      # an empty (cube) whose location/scale is the box: the game reads it, nothing is drawn
        ob = bpy.data.objects.new('col_%d' % self.ncol, None); bpy.context.collection.objects.link(ob); ob.parent = self.root
        ob.empty_display_type = 'CUBE'; ob.empty_display_size = 1.0
        ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        ob.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)

    def pick(self, style):
        r = self.rng
        return r.choice(BRICK if style == 'brick' else PLASTER)

    def finish(self):
        bpy.context.view_layer.update()
        for nm, (m, obs) in self.vis.items():
            for o in obs:
                o.data.materials.clear(); o.data.materials.append(m); apply_uv(o, m)
        bpy.ops.object.select_all(action='DESELECT')
        for nm, (m, obs) in self.vis.items():
            bpy.ops.object.select_all(action='DESELECT')
            for o in obs: o.select_set(True)
            bpy.context.view_layer.objects.active = obs[0]
            if len(obs) > 1: bpy.ops.object.join()
            j = bpy.context.view_layer.objects.active
            j.name = 'vis_' + m.name
        return self.root

# ---------- a wall run with openings cut out; ruin walls get a ragged top ----------
def wall(b, alongX, t0, t1, u0, u1, openings, topfn, mfn, cell=None):
    """alongX: wall runs along x (t = y thickness range) else along y.  openings: (ua,ub,zb,zt)."""
    br = {u0, u1}
    for (ua, ub, zb, zt) in openings: br.add(max(u0, ua)); br.add(min(u1, ub))
    if cell:
        k = u0 + cell
        while k < u1 - 1e-6: br.add(k); k += cell
    br = sorted(br)
    for ua, ub in zip(br[:-1], br[1:]):
        if ub - ua < 1e-4: continue
        mid = (ua + ub) / 2; top = topfn(mid)
        cov = sorted([o for o in openings if o[0] <= ua + 1e-6 and o[1] >= ub - 1e-6], key=lambda o: o[2])
        z = 0.0; segs = []
        for (_, _, zb, zt) in cov:
            if zb > z: segs.append((z, min(zb, top)))
            z = max(z, zt)
        if top > z: segs.append((z, top))
        m = mfn(mid)
        for (za, zb2) in segs:
            if zb2 - za < 0.02: continue
            if alongX: b.solid(ua, t0, za, ub, t1, zb2, m)
            else:      b.solid(t0, ua, za, t1, ub, zb2, m)

def window_deco(b, alongX, tc, u0, u1, zb, zt, outward, shutters, frame=True):
    """frame, sill and shutters around a window opening centred in thickness tc, outward = +1/-1 normal."""
    f = 0.07; o0 = tc + outward * (T / 2); o1 = o0 + outward * 0.06
    def box(ua, ub, za, zb2, ta, tb):
        ta, tb = min(ta, tb), max(ta, tb)
        if alongX: b.deco(ua, ta, za, ub, tb, zb2, CAP if frame else DWOOD)
        else:      b.deco(ta, ua, za, tb, ub, zb2, CAP if frame else DWOOD)
    box(u0 - f, u0, zb - 0.06, zt + 0.06, o0, o1)
    box(u1, u1 + f, zb - 0.06, zt + 0.06, o0, o1)
    box(u0 - f, u1 + f, zt, zt + 0.12, o0 - outward * 0.02, o1 + outward * 0.04)       # lintel
    box(u0 - f, u1 + f, zb - 0.1, zb, o0 - outward * 0.02, o1 + outward * 0.10)        # sill
    if shutters:
        w = (u1 - u0) / 2
        for (ua, ub) in ((u0 - w - 0.03, u0 - 0.03), (u1 + 0.03, u1 + w + 0.03)):
            if alongX: b.deco(ua, o0, zb, ub, o0 + outward * 0.05, zt, SHUT)
            else:      b.deco(o0, ua, zb, o0 + outward * 0.05, ub, zt, SHUT)

def slab_with_hole(b, z, x0, x1, y0, y1, hole, mat_top, thick=0.3, clip=None):
    """a floor slab as boxes around a hole (hx0,hx1,hy0,hy1), optional clip rectangle for broken floors."""
    if clip:
        x0 = max(x0, clip[0]); x1 = min(x1, clip[1]); y0 = max(y0, clip[2]); y1 = min(y1, clip[3])
        if x1 - x0 < 0.2 or y1 - y0 < 0.2: return
    rects = []
    if hole:
        hx0 = max(hole[0], x0); hx1 = min(hole[1], x1); hy0 = max(hole[2], y0); hy1 = min(hole[3], y1)
        if hx1 > hx0 and hy1 > hy0:
            rects += [(x0, y0, hx0, y1), (hx1, y0, x1, y1), (hx0, y0, hx1, hy0), (hx0, hy1, hx1, y1)]
        else: rects = [(x0, y0, x1, y1)]
    else: rects = [(x0, y0, x1, y1)]
    for (a, c, d, e) in rects:
        if d - a < 0.01 or e - c < 0.01: continue
        b.solid(a, c, z - thick, d, e, z, CONC)
        b.deco(a, c, z, d, e, z + 0.02, mat_top)

def stairs(b, xA, xB, yS, n, run, dzs, upto, ruin_break=False):
    """switchback stairs: flight i climbs dzs[i]; even flights use column A going +y, odd flights column B going -y."""
    z0 = 0.0; holes = {}
    yL = yS + n * run
    for i in range(upto):
        dz = dzs[i]; rise = dz / n; top = z0 + dz
        for k in range(1, n + 1):
            if i % 2 == 0: ya, yb = yS + (k - 1) * run, yS + k * run; xs = xA
            else:          ya, yb = yL - k * run, yL - (k - 1) * run; xs = xB
            b.solid(xs[0], ya, z0, xs[1], yb, z0 + k * rise, WOOD)
        # landing where the next flight turns round (always built, it is part of the floor)
        if i < upto - 1 or True:
            if i % 2 == 0: b.solid(xB[0], yL, top - 0.3, xA[1], yL + 1.2, top, CONC)
            else:          b.solid(xB[0], yS - 1.2, top - 0.3, xA[1], yS, top, CONC)
        holes[i + 1] = (xA[0], xA[1], yS, yS + (n - 1) * run) if i % 2 == 0 else (xB[0], xB[1], yS + run, yL)
        z0 = top
    return holes

def openings_for(wall_len, n, wid, floors, level_z, door_u=None, door_w=1.3, extra_doors=(), win_zb=0.9, win_h=1.3, skip=()):
    ops = []; step = wall_len / n
    for i in range(n):
        uc = -wall_len / 2 + step * (i + 0.5)
        for f in range(floors):
            if (i, f) in skip: continue
            if f == 0 and door_u is not None and abs(uc - door_u) < 0.5: continue
            if f == 0 and any(abs(uc - d) < 0.5 for d in extra_doors): continue
            ops.append((uc - wid / 2, uc + wid / 2, f * FH + win_zb, f * FH + win_zb + win_h))
    return ops

def rubble(b, x, y, r, rng, solid=True):
    H = min(1.25, r * 0.72) if r >= 1.4 else r * 0.5
    for i in range(int(6 + r * 5)):
        a = rng.random() * 6.283; d = rng.random() * r; s = 0.25 + rng.random() * 0.6
        z = max(0, (1 - d / r) * H * 0.9 * rng.random())
        cx, cy = x + math.cos(a) * d, y + math.sin(a) * d
        b.deco(cx - s * 0.7, cy - s * 0.5, z, cx + s * 0.7, cy + s * 0.5, z + s * 0.6, rng.choice(RUBM),
               rot=(rng.random() * 0.6, rng.random() * 0.6, rng.random() * 3))
    b.deco(x - r * 0.8, y - r * 0.8, 0, x + r * 0.8, y + r * 0.8, H * 0.45, RUBM[0])
    if solid:
        b.colbox(x - r * 0.62, y - r * 0.62, 0, x + r * 0.62, y + r * 0.62, 0.4)
        if r >= 1.4: b.colbox(x - r * 0.42, y - r * 0.42, 0, x + r * 0.42, y + r * 0.42, max(0.9, H * 0.78))
        b.colbox(x - r * 0.27, y - r * 0.27, 0, x + r * 0.27, y + r * 0.27, max(0.6, H * 0.95))

# ============================== TOWNHOUSE ==============================
def townhouse(name, W, D, floors, ruin, seed, style='plaster'):
    b = B(name, W, D, floors, ruin, seed); rng = b.rng
    hw, hd = W / 2, D / 2
    Htop = floors * FH + (0.9 if not ruin else 0)
    n = 11 if False else 10; run = 0.42
    xA = (hw - T - 1.2, hw - T); xB = (hw - T - 2.4, hw - T - 1.2); yS = -3.0
    dzs = [FH] * floors
    stair_levels = floors if not ruin else min(floors, 1 + rng.randint(0, 1))
    holes = stairs(b, xA, xB, yS, n, run, dzs, stair_levels)

    # slabs
    slab_clip = {}
    for lv in range(1, floors + 1):
        if ruin and lv > stair_levels: continue
        clip = None
        if ruin:
            frac = 0.45 + rng.random() * 0.25; clip = (hw - T - (W - 2 * T) * frac, hw - T, -hd + T, hd - T)
        slab_with_hole(b, lv * FH, -hw + T, hw - T, -hd + T, hd - T, holes.get(lv), FLOOR if lv < floors or ruin else ROOF, clip=clip)
    # ground floor (visual only) and rubble/dark floor
    b.deco(-hw + T, -hd + T, 0.0, hw - T, hd - T, 0.03, FLOOR if not ruin else RUBM[0])

    # window / door layout
    nS = max(2, round(W / 3.4)); nE = max(2, round(D / 3.4))
    south = openings_for(W, nS, 1.2, floors, 0, door_u=0.0 if nS % 2 == 1 else None)
    south.append((-0.65, 0.65, 0.0, 2.3))
    north = openings_for(W, nS, 1.2, floors, 0, door_u=None, extra_doors=[-W / 2 + (W / nS) * 0.5])
    north.append((-W / 2 + (W / nS) * 0.5 - 0.65, -W / 2 + (W / nS) * 0.5 + 0.65, 0.0, 2.3))
    side = openings_for(D - 2 * T, nE, 1.2, floors, 0)
    sides_y = (D - 2 * T)

    def prof_factory():
        ph = rng.random() * 20
        cells = {}
        def f(u, Hm):
            return None
        return ph
    def topfn_factory(len_, Hm, ph):
        if not ruin: return lambda u: Htop
        def f(u):
            if u < -len_ / 2 + 1.2 or u > len_ / 2 - 1.2: return Hm * (0.78 + 0.2 * abs(math.sin(ph + u)))
            p = 0.55 + 0.45 * abs(math.sin((u + ph) * 0.35) * 0.7 + math.sin((u + ph) * 0.9 + 2) * 0.3)
            h = max(1.8, Hm * p)
            if abs(math.sin((u + ph) * 1.7)) > 0.985: h = 0.6 + rng.random() * 0.9       # a breach
            return h
        return f
    Hm = floors * FH
    def mfn(style_):
        if not ruin:
            m0 = b.pick(style_)
            return lambda u: m0
        m0 = b.pick(style_); m1 = b.pick(style_)
        return lambda u: m0 if rng.random() < 0.85 else m1
    cell = 1.3 if ruin else None
    # south, north (along x), west, east (along y, between them)
    tS = topfn_factory(W, Hm, rng.random() * 9); tN = topfn_factory(W, Hm, rng.random() * 9)
    tW = topfn_factory(D, Hm, rng.random() * 9); tE = topfn_factory(D, Hm, rng.random() * 9)
    wall(b, True, -hd, -hd + T, -hw, hw, south, tS, mfn(style), cell)
    wall(b, True, hd - T, hd, -hw, hw, north, tN, mfn(style), cell)
    wall(b, False, -hw, -hw + T, -hd + T, hd - T, side, tW, mfn(style), cell)
    wall(b, False, hw - T, hw, -hd + T, hd - T, side, tE, mfn(style), cell)

    # frames, sills and shutters; plinth; cornice
    def decorate(openings, alongX, tc, outward, tf=None):
        for (ua, ub, zb, zt) in openings:
            if zb < 0.5: continue
            if ruin and tf and min(tf(ua), tf((ua + ub) / 2), tf(ub)) < zt + 0.25: continue
            if ruin and rng.random() < 0.4: continue
            window_deco(b, alongX, tc, ua, ub, zb, zt, outward, shutters=(not ruin) and rng.random() < 0.7)
    decorate(south, True, -hd + T / 2, -1, tS); decorate(north, True, hd - T / 2, 1, tN)
    decorate(side, False, -hw + T / 2, -1, tW); decorate(side, False, hw - T / 2, 1, tE)
    # door leaves ajar (visual)
    b.deco(-0.65, -hd - 0.35, 0.0, -0.62, -hd - 0.05, 2.25, DWOOD, rot=(0, 0, 0.0))
    if not ruin:
        b.deco(-hw - 0.05, -hd - 0.05, 0.0, hw + 0.05, hd + 0.05, 0.6, PLINTH)
        z = floors * FH
        b.deco(-hw - 0.12, -hd - 0.12, z + 0.9, hw + 0.12, hd + 0.12, z + 1.02, CAP)
        for f in range(1, floors):
            b.deco(-hw - 0.05, -hd - 0.05, f * FH - 0.12, hw + 0.05, hd + 0.05, f * FH + 0.06, CAP)
        # chimney stacks and a roof hatch house on the roof, solid cover
        for cx, cy in ((-hw * 0.5, hd * 0.5), (-hw * 0.2, -hd * 0.45)):
            b.solid(cx - 0.45, cy - 0.45, z, cx + 0.45, cy + 0.45, z + 2.0, b.pick('brick'))
            b.deco(cx - 0.55, cy - 0.55, z + 2.0, cx + 0.55, cy + 0.55, z + 2.12, CAP)
        # interior: a partition wall with a doorway on every storey, a table and a wardrobe
        px = -1.2
        for f in range(floors):
            z0 = f * FH
            for (ya, yb) in ((-hd + T, -0.4), (0.7, hd - T)):
                b.solid(px, ya, z0, px + 0.2, yb, z0 + FH - 0.3 + (0.0), PLASTER[2])
            b.solid(px, -0.4, z0 + 2.3, px + 0.2, 0.7, z0 + FH - 0.3, PLASTER[2])
            b.solid(-hw + T + 0.1, hd - T - 0.7, z0, -hw + T + 1.5, hd - T - 0.1, z0 + 1.9, DWOOD)      # wardrobe
            b.solid(1.5, -1.0, z0, 2.7, 0.2, z0 + 0.04, DWOOD, col=False)
            b.solid(1.8, -0.8, z0 + 0.72, 2.5, 0.0, z0 + 0.78, WOOD, col=False)
            for lx, ly in ((1.85, -0.75), (2.45, -0.75), (1.85, -0.05), (2.45, -0.05)):
                b.deco(lx - 0.03, ly - 0.03, z0, lx + 0.03, ly + 0.03, z0 + 0.72, WOOD)
            b.colbox(1.75, -0.85, z0, 2.55, 0.05, z0 + 0.78)
    else:
        # ruined: rubble heaps in and around, a rubble ramp up to the broken first floor, charred beams
        for k in range(2 + floors // 2):
            rx = rng.uniform(-hw + 1.5, hw - 1.5); ry = rng.uniform(-hd + 1.5, hd - 1.5)
            if rx > hw - T - 2.6 and -3.5 < ry < 3.0: continue                  # keep the stairs clear
            rubble(b, rx, ry, rng.uniform(0.9, 2.0), rng)
        for k in range(2):
            side_ = rng.choice([-1, 1])
            rubble(b, side_ * (hw + 1.0), rng.uniform(-hd + 2, hd - 2), 1.7, rng)
        for k in range(4):
            bx_ = rng.uniform(-hw + 1.2, hw - 1.2); by_ = rng.uniform(-hd + 1.2, hd - 1.2)
            b.deco(bx_ - 0.1, by_ - 1.2, 0.0, bx_ + 0.1, by_ + 1.2, 0.2, CHAR, rot=(0, rng.uniform(-0.2, 0.2), rng.random() * 3))
        # a broken slab hanging down from the first floor edge (visual)
        if stair_levels >= 1:
            ex = hw - T - (W - 2 * T) * 0.6
            b.deco(ex - 2.4, -hd + 1.2, FH - 1.4, ex, hd - 1.2, FH - 1.1, CONC, rot=(0, 0.55, 0), pivot=(ex, 0, FH - 1.25))
        # chimney breast
        cx = rng.uniform(-hw + 2.5, 0.0)
        b.solid(cx - 0.55, hd - T - 0.72, 0, cx + 0.55, hd - T, Hm * 0.9, b.pick(style))
        b.deco(cx - 0.35, hd - T - 0.74, 0.05, cx + 0.35, hd - T - 0.66, 1.0, CHAR)
    return b

# ============================== CHURCH ==============================
def church(name, seed):
    W = 8.6; ND = 15.0; TW = 6.0; TD = 8.0
    # nave y in [0, ND], tower y in [-TD, 0]; centred later so the whole thing sits on the origin
    total = ND + TD; oy = -(ND - TD) / 2 * 0       # origin kept at the middle of the whole footprint
    b = B(name, W, total, 4, False, seed); rng = b.rng
    ys = -total / 2                                  # south end of tower
    ty0, ty1 = ys, ys + TD                          # tower y range
    ny0, ny1 = ty1, ty1 + ND                        # nave y range
    hw = W / 2; Tw = 0.6; Tt = 0.7
    stone = STONE; plaster = PLASTER[2]
    NH = 7.0                                        # nave wall height
    # ---- nave walls ----
    def pickst(_): return rng.choice(stone)
    wins = []
    cnt = 3
    for i in range(cnt):
        uc = ny0 + 2.8 + i * 4.5
        wins.append((uc - 0.65, uc + 0.65, 1.6, 5.0))
    wall(b, False, -hw, -hw + Tw, ny0, ny1, wins, lambda u: NH, lambda u: plaster)
    wall(b, False, hw - Tw, hw, ny0, ny1, wins, lambda u: NH, lambda u: plaster)
    # north end wall with a round window and a vestry door
    wall(b, True, ny1 - Tw, ny1, -hw + Tw, hw - Tw, [(-0.7, 0.7, 2.6, 5.4)], lambda u: NH + 2.4 * max(0, 1 - abs(u) / (hw - Tw)), lambda u: plaster)
    # gable of the north end (visual) is the topfn above. nave ceiling (solid, so bullets stop and nobody stands on a roof)
    b.solid(-hw + Tw, ny0, NH - 0.3, hw - Tw, ny1 - Tw, NH, CONC)
    # gabled roof (visual prism)
    def prism(x0, x1, y0, y1, z0, h, m):
        me = bpy.data.meshes.new('roof'); xm = (x0 + x1) / 2
        vs = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (xm, y0, z0 + h), (xm, y1, z0 + h)]
        fs = [(0, 3, 5, 4), (1, 4, 5, 2), (0, 4, 1), (3, 2, 5), (0, 1, 2, 3)]
        me.from_pydata(vs, [], fs); me.update()
        ob = bpy.data.objects.new('roof', me); bpy.context.collection.objects.link(ob); ob.parent = b.root
        b.vis.setdefault(m.name, (m, []))[1].append(ob)
    prism(-hw - 0.4, hw + 0.4, ny0 - 0.2, ny1 + 0.2, NH, 2.6, TILE)
    # buttresses
    for i in range(cnt + 1):
        uc = ny0 + 0.6 + i * 4.5
        for sx in (-1, 1):
            b.solid(sx * (hw + 0.2) - 0.35, uc - 0.3, 0, sx * (hw + 0.2) + 0.35, uc + 0.3, 4.4, STONE[1], col=False)
            b.deco(sx * (hw + 0.2) - 0.4, uc - 0.34, 4.4, sx * (hw + 0.2) + 0.4, uc + 0.34, 4.5, CAP)
    # window frames: pointed heads
    for (ua, ub, zb, zt) in wins:
        for sx in (-1, 1):
            tc = sx * (hw - Tw / 2)
            window_deco(b, False, tc, ua, ub, zb, zt, sx, False)
    # ---- tower ----
    tx0, tx1 = -TW / 2, TW / 2
    topz = 16.0; belfry = 12.0
    tdoor = [(-1.9, -0.5, 0.0, 3.3)]
    tslit = lambda yc: None
    ops_s = tdoor + [(-0.4, 0.4, 7.0, 8.6), (-0.4, 0.4, 3.0, 4.2)] + [(-1.0, 1.0, belfry + 0.9, belfry + 3.3)]
    ops_x = [(ty0 + 3.0, ty0 + 3.7, 3.0, 4.6), (ty0 + 3.0, ty0 + 3.7, 7.0, 8.6), (ty0 + 3.0 - 0.0, ty0 + 5.0, belfry + 0.9, belfry + 3.3)]
    ops_n = [(-1.9, -0.4, 0.0, 3.4)] + [(-1.0, 1.0, belfry + 0.9, belfry + 3.3)]
    crenel = lambda u: topz + 0.9
    wall(b, True, ty0, ty0 + Tt, tx0, tx1, ops_s, crenel, pickst)
    wall(b, True, ty1 - Tt, ty1, tx0, tx1, ops_n, crenel, pickst)
    wall(b, False, tx0, tx0 + Tt, ty0 + Tt, ty1 - Tt, ops_x, crenel, pickst)
    wall(b, False, tx1 - Tt, tx1, ty0 + Tt, ty1 - Tt, ops_x, crenel, pickst)
    # arched belfry heads, string courses, plinth, parapet cap and crenel gaps
    for z in (4.0, 8.0, 12.0, 16.0):
        b.deco(tx0 - 0.08, ty0 - 0.08, z - 0.08, tx1 + 0.08, ty1 + 0.08, z + 0.06, CAP)
    b.deco(tx0 - 0.1, ty0 - 0.1, 0, tx1 + 0.1, ty1 + 0.1, 0.7, PLINTH)
    b.deco(tx0 - 0.15, ty0 - 0.15, topz + 0.9, tx1 + 0.15, ty1 + 0.15, topz + 1.0, CAP)
    # tower floors and stairs (levels 4, 8, 12, 16)
    n = 11; run = 0.38
    xA = (tx1 - Tt - 1.2, tx1 - Tt); xB = (tx1 - Tt - 2.4, tx1 - Tt - 1.2)
    yS = ty0 + Tt + 1.3
    holes = stairs(b, xA, xB, yS, n, run, [4.0] * 4, 4)
    for lv in range(1, 5):
        slab_with_hole(b, lv * 4.0, tx0 + Tt, tx1 - Tt, ty0 + Tt, ty1 - Tt, holes.get(lv), FLOOR if lv < 4 else ROOF)
    # a nave doorway from the tower base (opening already cut) ; arched stone steps at the door
    b.deco(-2.1, ty0 - 0.7, 0, -0.3, ty0, 0.15, STONE[1])
    # ---- inside the nave: pews (cover), altar, pulpit ----
    for r in range(6):
        y = ny0 + 3.0 + r * 1.7
        for sx in (-1, 1):
            xa, xb = (sx * 0.5, sx * 3.0) if sx > 0 else (sx * 3.0, sx * 0.5)
            b.solid(xa, y, 0, xb, y + 0.5, 0.95, DWOOD)
    b.solid(-1.4, ny1 - 2.2, 0, 1.4, ny1 - 1.3, 1.0, STONE[1])                    # altar
    b.solid(hw - Tw - 1.1, ny0 + 5.0, 0, hw - Tw, ny0 + 6.2, 1.4, DWOOD)         # pulpit
    b.deco(-hw + Tw, ny0, 0.0, hw - Tw, ny1 - Tw, 0.03, FLOOR)
    return b

# ============================== build everything ==============================
VARIANTS = []
def place(bld, ox, oy):
    bld.root.location = (ox, oy, 0)
    VARIANTS.append(bld)
x = 0
specs = [('house_i2', 12, 10, 2, False, 11, 'plaster'),
         ('house_i3', 12, 10, 3, False, 12, 'brick'),
         ('ruin_f2', 14, 12, 2, True, 21, 'brick'),
         ('ruin_f3', 14, 12, 3, True, 22, 'plaster'),
         ('ruin_f4', 14, 12, 4, True, 23, 'brick'),
         ('ruin_f5', 14, 12, 5, True, 24, 'plaster')]
for (nm, W, D, fl, ru, sd, st) in specs:
    bl = townhouse('bld_%s_w%d_d%d_f%d' % (nm, W, D, fl), W, D, fl, ru, sd, st); bl.finish(); place(bl, x, 0); x += 26
ch = church('bld_church_w9_d23_f4', 5); ch.finish(); place(ch, x, 0)

# ---- export ----
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, 'buildings_hd.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True)
print('BUILDINGS EXPORTED', os.path.getsize(glb), 'bytes', [(v.name, v.ncol) for v in VARIANTS])

# ---- preview renders ----
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x = 1900; sc.render.resolution_y = 900
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.55, 0.62, 0.68)
for ob in bpy.data.objects:
    if ob.name.startswith('col_'): ob.hide_viewport = True; ob.hide_render = True
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 28
def shot(fname, cx, cy, dist, h, az, zt=4.0):
    a = math.radians(az)
    cam.location = (cx + math.sin(a) * dist, cy - math.cos(a) * dist, h)
    d = Vector((cx, cy, zt)) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, fname); bpy.ops.render.render(write_still=True)
shot('buildings2_a.png', 13, 0, 46, 22, 25, 4)      # intact 2f, intact 3f, ruin f2
shot('buildings2_b.png', 78, 0, 48, 24, 25, 5)      # ruins f3, f4, f5
shot('buildings2_c.png', 156, 0, 44, 22, 35, 7)     # the church
print('BUILDINGS DONE')
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.size[0] <= 512: continue
    w, h = im.size; im.scale(512, max(1, int(h * 512 / w))); im.file_format = 'JPEG'
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.name.startswith(('bld_', 'col_')) or (ob.parent is not None and ob.parent.name.startswith('bld_')): ob.select_set(True)
glb_g = os.path.join(OUT, 'buildings_game.glb')
bpy.ops.export_scene.gltf(filepath=glb_g, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_image_format='JPEG')
print('GAME GLB', os.path.getsize(glb_g), 'bytes')
