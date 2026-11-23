import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix

# ---- Panzer IV Ausf. G/H and T-34/76 for the tank mode. Game units (1 unit = 1 m). Nose is +Y, up is +Z, ground is Z=0, hull centred on the origin.
# Each tank exports 4 objects with separate origins so the game can move them independently:
#   <t>_hull    origin (0,0,0)                       hull, tracks, wheels, fenders, stowage
#   <t>_turret  origin on the turret ring            turret body (+ skirts/hatches), sits where the game's turret group is
#   <t>_gun     origin on the gun trunnion           mantlet + recoil housing, pitches with the gun
#   <t>_barrel  origin on the gun trunnion           barrel (+ muzzle brake), so the game can hide it when the tank is wrecked
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
os.makedirs(OUT, exist_ok=True)
V = Vector

def clear():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for b in list(blk):
            if b.users == 0: blk.remove(b)

# ------------------------------------------------------------------ materials / images
def lin(r, g, b): return tuple((c / 255.0) ** 2.2 for c in (r, g, b))

def mat(name, rgb, metal=0.0, rough=0.7):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1)
    return m

def decal_mat(name, img):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.9
    try: m.blend_method = 'BLEND'
    except Exception: pass
    try: m.surface_render_method = 'BLENDED'
    except Exception: pass
    m.use_backface_culling = False
    return m

def rgba_image(name, arr):
    """arr: HxWx4 float, row 0 = TOP"""
    a = np.ascontiguousarray(arr[::-1]).astype(np.float32)
    H, W, _ = a.shape
    img = bpy.data.images.new(name, W, H, alpha=True)
    img.pixels = a.ravel().tolist(); img.pack(); img.file_format = 'PNG'
    return img

BLK = (0.07, 0.07, 0.06); WHT = (0.92, 0.90, 0.84); RED = (0.72, 0.09, 0.07)
GLYPH = {
    '0': [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    '1': ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    '3': [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    '4': ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
}

def paint(im, r0, r1, c0, c1, col):
    H, W, _ = im.shape
    r0 = max(0, int(r0)); r1 = min(H, int(r1)); c0 = max(0, int(c0)); c1 = min(W, int(c1))
    if r1 <= r0 or c1 <= c0: return
    im[r0:r1, c0:c1, :3] = col; im[r0:r1, c0:c1, 3] = 1.0

def cross_img(S=256):
    im = np.zeros((S, S, 4), np.float32); c = S / 2
    for hw, L, col in ((0.30, 1.0, WHT), (0.19, 0.86, BLK)):
        paint(im, c - c * L, c + c * L, c - c * hw, c + c * hw, col)
        paint(im, c - c * hw, c + c * hw, c - c * L, c + c * L, col)
    return im

def star_img(S=256):
    im = np.zeros((S, S, 4), np.float32); yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    def poly(R, r, col):
        pts = [((S / 2) + (R if i % 2 == 0 else r) * math.cos(-math.pi / 2 + i * math.pi / 5),
                (S / 2) + (R if i % 2 == 0 else r) * math.sin(-math.pi / 2 + i * math.pi / 5)) for i in range(10)]
        ins = np.zeros((S, S), bool)
        for i in range(10):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % 10]
            cond = ((y1 > yy) != (y2 > yy)) & (xx < (x2 - x1) * (yy - y1) / (y2 - y1 + 1e-9) + x1)
            ins ^= cond
        im[ins, :3] = col; im[ins, 3] = 1.0
    poly(S * 0.50, S * 0.20, WHT); poly(S * 0.42, S * 0.165, RED)
    return im

def num_img(s, cell, col, outline=None, pad=0):
    n = len(s); gw = 5 * cell; gap = cell
    W = n * gw + (n - 1) * gap + 2 * pad; H = 7 * cell + 2 * pad
    m = np.zeros((H, W), bool)
    for i, ch in enumerate(s):
        g = GLYPH[ch]
        for r in range(7):
            for c in range(5):
                if g[r][c] == '#':
                    x0 = pad + i * (gw + gap) + c * cell; y0 = pad + r * cell
                    m[y0:y0 + cell, x0:x0 + cell] = True
    im = np.zeros((H, W, 4), np.float32)
    if outline is not None and pad > 0:
        d = m.copy()
        for dy in range(-pad, pad + 1):
            for dx in range(-pad, pad + 1):
                if dx * dx + dy * dy <= pad * pad: d |= np.roll(np.roll(m, dy, 0), dx, 1)
        im[d, :3] = outline; im[d, 3] = 1.0
    im[m, :3] = col; im[m, 3] = 1.0
    return im

# ------------------------------------------------------------------ geometry helpers
def loft_bm(bm, rings, closed=True, caps=(True, True), mi=0, smooth=False):
    uvl = bm.loops.layers.uv.verify()
    R = len(rings); N = len(rings[0])
    Vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    us = [i / max(1, R - 1) for i in range(R)]; vs = [j / N for j in range(N)]
    for i in range(R - 1):
        for k in range(N):
            k2 = (k + 1) % N
            try: f = bm.faces.new((Vs[i][k], Vs[i][k2], Vs[i + 1][k2], Vs[i + 1][k]))
            except ValueError: continue
            f.smooth = smooth; f.material_index = mi
            v2 = vs[k] + 1.0 / N
            for l, c in zip(f.loops, ((us[i], vs[k]), (us[i], v2), (us[i + 1], v2), (us[i + 1], vs[k]))): l[uvl].uv = c
    for ci, flag in ((0, caps[0]), (R - 1, caps[1])):
        if flag:
            try: f = bm.faces.new(Vs[ci])
            except ValueError: continue
            f.smooth = False; f.material_index = mi
            for l, vtx in zip(f.loops, range(N)): l[uvl].uv = (us[ci], vs[vtx])

def stations(bm, sts, mi=0, smooth=False):
    loft_bm(bm, [[V((x, y, z)) for (x, z) in pts] for y, pts in sts], True, (True, True), mi, smooth)

def ring6(wb, zb, ws, zs, wt, zt):
    return [(-wb, zb), (wb, zb), (ws, zs), (wt, zt), (-wt, zt), (-ws, zs)]

def ring8(wb, wm1, z1, wm2, z2, wt, zt):
    return [(-wb, 0), (wb, 0), (wm1, z1), (wm2, z2), (wt, zt), (-wt, zt), (-wm2, z2), (-wm1, z1)]

def finish(bm, name, mats, loc=(0, 0, 0), skip=()):
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index not in skip])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); ob.location = loc
    return ob

def box(bm, c, s, rot=None, mi=0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    M = Matrix.Translation(V(c)) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4)) @ Matrix.Diagonal((s[0], s[1], s[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=r['verts'])
    for f in set(f for v in r['verts'] for f in v.link_faces): f.material_index = mi

def cyl(bm, p0, p1, r0, r1=None, seg=12, mi=0):
    p0 = V(p0); p1 = V(p1); d = p1 - p0; L = d.length
    if L < 1e-5: return
    if r1 is None: r1 = r0
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=L)
    q = V((0, 0, 1)).rotation_difference(d.normalized())
    M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=r['verts'])
    for f in set(f for v in r['verts'] for f in v.link_faces): f.material_index = mi

def sphere(bm, c, r, mi=0, sc=(1, 1, 1), seg=10):
    rr = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(5, seg // 2 + 1), radius=r)
    M = Matrix.Translation(V(c)) @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1))
    bmesh.ops.transform(bm, matrix=M, verts=rr['verts'])
    for f in set(f for v in rr['verts'] for f in v.link_faces): f.material_index = mi

def tube(bm, pts, r, seg=6, mi=0):
    for a, b in zip(pts[:-1], pts[1:]): cyl(bm, a, b, r, r, seg, mi)

def xcyl(bm, cx, cy, cz, r, w, mi=0, seg=14):
    cyl(bm, (cx - w / 2, cy, cz), (cx + w / 2, cy, cz), r, r, seg, mi)

def dquad(bm, c, right, up, w, h, mi):
    uv = bm.loops.layers.uv.verify()
    c = V(c); r = V(right).normalized() * (w / 2); u = V(up).normalized() * (h / 2)
    f = bm.faces.new([bm.verts.new(c - r - u), bm.verts.new(c + r - u), bm.verts.new(c + r + u), bm.verts.new(c - r + u)])
    f.material_index = mi; f.smooth = False
    for l, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): l[uv].uv = t

# ------------------------------------------------------------------ tracks
def hull2d(circles, n=16):
    pts = set()
    for cy, cz, r in circles:
        for k in range(n * 2):
            a = 2 * math.pi * k / (n * 2); pts.add((round(cy + r * math.cos(a), 5), round(cz + r * math.sin(a), 5)))
    pts = sorted(pts)
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]        # counter-clockwise in the (y,z) plane

def resample(poly, ds):
    n = len(poly); segs = []; tot = 0.0
    for i in range(n):
        a = poly[i]; b = poly[(i + 1) % n]; L = math.hypot(b[0] - a[0], b[1] - a[1]); segs.append((a, b, L, tot)); tot += L
    cnt = max(8, int(round(tot / ds))); out = []
    for k in range(cnt):
        s = tot * k / cnt
        for a, b, L, s0 in segs:
            if s0 <= s < s0 + L + 1e-9:
                t = (s - s0) / max(L, 1e-9); tx = (b[0] - a[0]) / max(L, 1e-9); tz = (b[1] - a[1]) / max(L, 1e-9)
                out.append(((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), (tx, tz))); break
    return out

def track(bm, xc, w, circles, thick=0.055, link=0.19, mi_belt=1, mi_link=1, mi_pad=3):
    pts = resample(hull2d(circles), 0.14)
    x0 = xc - w / 2; x1 = xc + w / 2; rows = []
    for (py, pz), (ty, tz) in pts:
        ny, nz = tz, -ty
        rows.append((V((x0, py, pz)), V((x1, py, pz)), V((x1, py + ny * thick, pz + nz * thick)), V((x0, py + ny * thick, pz + nz * thick))))
    vv = [[bm.verts.new(p) for p in r] for r in rows]; n = len(vv)
    for i in range(n):
        j = (i + 1) % n
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
            try:
                f = bm.faces.new((vv[i][a], vv[i][b], vv[j][b], vv[j][a])); f.material_index = mi_belt
            except ValueError: pass
    for (py, pz), (ty, tz) in resample(hull2d(circles), link):
        ny, nz = tz, -ty; phi = math.atan2(tz, ty)
        c = V((xc, py + ny * (thick + 0.013), pz + nz * (thick + 0.013)))
        box(bm, c, (w - 0.05, link * 0.52, 0.028), Matrix.Rotation(phi, 3, 'X'), mi_link)
    return pts

def wheel(bm, cx, cy, cz, r, w, mi_tire, mi_disc, seg=14):
    xcyl(bm, cx, cy, cz, r, w, mi_tire, seg)
    xcyl(bm, cx, cy, cz, r * 0.72, w * 1.12, mi_disc, seg)
    xcyl(bm, cx, cy, cz, r * 0.3, w * 1.3, mi_disc, 8)

def sprocket(bm, cx, cy, cz, r, w, sd, mi, mi_dark, teeth=12, spokes=8):
    xcyl(bm, cx, cy, cz, r * 0.95, w * 0.5, mi_dark, 16)
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        p0 = (cx + sd * w * 0.18, cy + 0.12 * math.cos(a), cz + 0.12 * math.sin(a)); p1 = (cx + sd * w * 0.18, cy + r * 0.92 * math.cos(a), cz + r * 0.92 * math.sin(a))
        cyl(bm, p0, p1, 0.028, 0.028, 5, mi)
    for k in range(teeth):
        a = 2 * math.pi * k / teeth
        box(bm, (cx, cy + r * 0.98 * math.cos(a), cz + r * 0.98 * math.sin(a)), (w * 0.34, 0.07, 0.07), Matrix.Rotation(a - math.pi / 2, 3, 'X'), mi)
    xcyl(bm, cx + sd * w * 0.15, cy, cz, r * 0.28, w * 0.5, mi, 10)

# ------------------------------------------------------------------ scene preview + export
def preview_and_export(prefix, title, shots):
    objs = [o for o in bpy.data.objects if o.name.startswith(prefix + '_')]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    glb = os.path.join(OUT, prefix + '.glb')
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_image_format='AUTO')
    tris = sum(len(o.data.polygons) for o in objs)
    print(title, 'EXPORTED', os.path.getsize(glb), 'bytes', len(objs), 'objects', tris, 'faces')
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.render.resolution_x = 1400; sc.render.resolution_y = 760
    sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.55, 0.6, 0.66)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 40
    for fname, loc, tgt in shots:
        cam.location = V(loc); d = V(tgt) - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, prefix + '_' + fname + '.png'); bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)

SHOTS = [('a', (10.5, 9.5, 5.2), (0, 0.3, 1.3)), ('b', (-10.5, -9.5, 5.2), (0, 0.3, 1.3)), ('c', (15.5, 0.3, 1.8), (0, 0.3, 1.4)), ('d', (0.1, 0.4, 15), (0, 0.4, 1.2)), ('e', (0.2, 13.5, 2.2), (0, 0, 1.4))]

# ====================================================================================================================
#  PANZER IV  Ausf. G/H
# ====================================================================================================================
def build_pz4():
    P = mat('pz4_paint', lin(172, 150, 98), 0.1, 0.85)
    DK = mat('pz4_track', lin(48, 45, 40), 0.35, 0.8)
    ST = mat('pz4_steel', lin(82, 78, 72), 0.45, 0.65)
    RB = mat('pz4_rubber', lin(30, 30, 28), 0.0, 0.9)
    WD = mat('pz4_wood', lin(120, 86, 52), 0.0, 0.9)
    PD = mat('pz4_paintdark', lin(118, 102, 66), 0.1, 0.9)
    D_X = decal_mat('pz4_decal_cross', rgba_image('pz4_cross', cross_img(256)))
    D_N = decal_mat('pz4_decal_num', rgba_image('pz4_num', num_img('413', 24, BLK, WHT, 5)))
    # materials: hull 0 paint,1 track,2 steel,3 rubber,4 wood,5 darkpaint,6 cross | turret 0 paint,1 track,2 steel,3 num,4 cross,5 darkpaint
    ring_y, ring_z = 0.2, 1.62

    # ---------------- hull
    bm = bmesh.new()
    stations(bm, [(-2.95, [(-.80, .50), (.80, .50), (.98, .62), (.98, 1.10), (-.98, 1.10), (-.98, .62)]),
                  (-2.88, ring6(.95, .38, 1.0, .5, 1.0, 1.12)), (2.55, ring6(.95, .38, 1.0, .5, 1.0, 1.12)),
                  (2.95, ring6(.82, .78, .98, .85, .98, 1.02))], 0)
    # superstructure: sloped front plate, vertical sides, fighting compartment roof
    stations(bm, [(2.42, ring6(1.18, 1.02, 1.18, 1.10, 1.0, 1.18)), (2.14, ring6(1.2, 1.02, 1.2, 1.46, 1.12, 1.62)),
                  (-0.78, ring6(1.2, 1.02, 1.2, 1.46, 1.12, 1.62)), (-0.9, ring6(1.14, 1.02, 1.14, 1.34, 1.06, 1.46))], 0)
    # engine deck + rear plate
    stations(bm, [(-0.9, ring6(1.1, 1.0, 1.1, 1.3, 1.04, 1.45)), (-2.85, ring6(1.06, 1.0, 1.06, 1.2, 1.0, 1.36)), (-2.97, ring6(.95, .8, .95, 1.0, .9, 1.14))], 0)
    for sd in (-1, 1):
        box(bm, (sd * 1.22, 0.1, 1.02), (0.5, 5.5, 0.05), None, 0)                         # fender shelf
        box(bm, (sd * 1.45, 0.1, 1.07), (0.04, 5.5, 0.08), None, 5)                        # fender lip
        box(bm, (sd * 1.22, 3.02, 1.12), (0.5, 0.42, 0.05), Matrix.Rotation(-0.35, 3, 'X'), 0)   # raised front mudguard
        box(bm, (sd * 1.22, -2.92, 1.0), (0.5, 0.38, 0.05), Matrix.Rotation(0.12, 3, 'X'), 0)
        box(bm, (sd * 1.3, -1.9, 1.2), (0.42, 0.95, 0.26), None, 5)                        # stowage / tool box
        box(bm, (sd * 1.3, -1.9, 1.34), (0.46, 1.0, 0.03), None, 0)
        box(bm, (sd * 1.3, 0.2, 1.08), (0.1, 1.0, 0.05), None, 4)                          # shovel
        box(bm, (sd * 1.33, 1.5, 1.09), (0.08, 0.55, 0.07), None, 2)                       # jack
        tube(bm, [(sd * 1.38, -2.3, 1.1), (sd * 1.38, 2.4, 1.1)], 0.022, 6, 1)             # tow cable
        for yy in (-2.3, 2.4): sphere(bm, (sd * 1.38, yy, 1.1), 0.05, 1, (1, 1, 1), 6)
        box(bm, (sd * 0.62, 1.4, 1.64), (0.46, 0.42, 0.05), None, 5)                       # driver / radio hatches
        box(bm, (sd * 0.62, 1.4, 1.68), (0.34, 0.3, 0.03), None, 0)
        cyl(bm, (sd * 0.62, -1.9, 1.34), (sd * 0.62, -1.9, 1.48), 0.2, 0.2, 14, 5)         # filler caps on the engine deck
    # driver's visor, bow MG, spare track links on the nose, towing eyes, headlight
    box(bm, (-0.62, 2.27, 1.36), (0.3, 0.1, 0.13), Matrix.Rotation(0.2, 3, 'X'), 5)
    sphere(bm, (0.62, 2.3, 1.34), 0.11, 2, (1, 0.9, 1), 8); cyl(bm, (0.62, 2.32, 1.34), (0.62, 2.65, 1.34), 0.02, 0.02, 6, 2)
    for i in range(6): box(bm, (-0.75 + i * 0.3, 2.66, 0.92), (0.26, 0.08, 0.12), Matrix.Rotation(-0.55, 3, 'X'), 1)
    for sd in (-1, 1):
        for k in (0, 1): cyl(bm, (sd * 0.82, 2.96, 0.72), (sd * 0.82, 3.1, 0.72), 0.05 - k * 0.025, 0.05 - k * 0.025, 8, 2)
    cyl(bm, (-0.92, 2.68, 1.12), (-0.92, 2.78, 1.12), 0.09, 0.09, 12, 2)
    box(bm, (-0.92, 2.64, 1.05), (0.1, 0.18, 0.04), None, 2)
    # engine deck louvres + rear details + muffler
    for i in range(7): box(bm, (-0.45, -1.2 - i * 0.25, 1.455 - i * 0.012), (0.8, 0.14, 0.03), None, 5)
    box(bm, (0.5, -1.95, 1.44), (0.55, 0.9, 0.03), None, 5)
    cyl(bm, (-0.55, -2.55, 1.2), (-0.55, -3.4, 1.2), 0.17, 0.17, 14, 2); cyl(bm, (-0.55, -3.4, 1.2), (-0.55, -3.46, 1.2), 0.1, 0.1, 10, 1)
    cyl(bm, (0.55, -2.6, 1.14), (0.55, -3.1, 1.14), 0.05, 0.05, 8, 2)
    for sd in (-1, 1): box(bm, (sd * 0.85, -3.0, 0.78), (0.2, 0.08, 0.18), None, 2)
    # superstructure side details: vision ports, hull cross
    for sd in (-1, 1):
        box(bm, (sd * 1.21, 1.9, 1.35), (0.03, 0.22, 0.12), None, 1)
        box(bm, (sd * 1.21, 0.3, 1.38), (0.03, 0.5, 0.3), None, 5)
        dquad(bm, (sd * 1.222, 1.25, 1.3), (0, sd, 0), (0, 0, 1), 0.46, 0.46, 6)
    # ---- tracks and running gear
    xc = 1.24; w = 0.40
    WY = [-1.915, -1.385, -0.815, -0.285, 0.285, 0.815, 1.385, 1.915]; WR = 0.235; WZ = 0.06 + WR
    SPY, SPR, IDY, IDR = 2.55, 0.43, -2.55, 0.36
    circ = [(SPY, 0.055 + SPR, SPR), (IDY, 0.055 + IDR, IDR)] + [(y, WZ, WR) for y in (WY[0], WY[-1])]
    for sd in (-1, 1):
        track(bm, sd * xc, w, circ, 0.055, 0.19, 1, 1, 3)
        for y in WY:
            wheel(bm, sd * (xc - 0.03), y, WZ, WR, 0.12, 3, 2)
            xcyl(bm, sd * (xc - 0.1), y, WZ, WR * 0.4, 0.1, 2, 8)
        for y in (-1.7, -0.55, 0.6, 1.75):
            zin = 0.775 + (y + 2.55) / 5.1 * 0.14
            xcyl(bm, sd * xc, y, zin - 0.1, 0.095, 0.12, 3, 10)
        sprocket(bm, sd * (xc + 0.02), SPY, 0.055 + SPR, SPR, 0.2, sd, 2, 1)
        wheel(bm, sd * (xc + 0.02), IDY, 0.055 + IDR, IDR, 0.16, 3, 2, 14)
        for k in range(8):                                                                  # idler spokes
            a = 2 * math.pi * k / 8; zc = 0.055 + IDR
            cyl(bm, (sd * (xc + 0.1), IDY, zc), (sd * (xc + 0.1), IDY + IDR * 0.78 * math.cos(a), zc + IDR * 0.78 * math.sin(a)), 0.02, 0.02, 5, 2)
        for k in range(4):                                                                  # bogie springs
            y = (-1.65, -0.55, 0.55, 1.65)[k]
            box(bm, (sd * 1.0, y, 0.46), (0.12, 1.1, 0.05), None, 2)
    hull = finish(bm, 'pz4_hull', [P, DK, ST, RB, WD, PD, D_X], skip=(6,))

    # ---------------- turret (local origin = ring centre)
    bm = bmesh.new()
    stations(bm, [(-1.25, ring6(.8, 0, .9, .4, .8, .78)), (-1.05, ring6(.92, 0, .95, .5, .9, .85)), (0.8, ring6(.95, 0, .95, .55, .9, .85)),
                  (1.12, ring6(.9, 0, .9, .55, .72, .76)), (1.25, ring6(.8, 0, .8, .46, .6, .7))], 0)
    box(bm, (0, -1.42, 0.45), (1.5, 0.36, 0.6), None, 0)                                  # rear stowage bin
    box(bm, (0, -1.62, 0.45), (1.56, 0.04, 0.64), None, 5)
    for i in range(5): box(bm, (-0.6 + i * 0.3, -1.64, 0.45), (0.02, 0.03, 0.6), None, 2)
    cyl(bm, (0, -0.75, 0.83), (0, -0.75, 1.07), 0.34, 0.31, 14, 0)                          # cupola
    cyl(bm, (0, -0.75, 1.07), (0, -0.75, 1.12), 0.36, 0.33, 14, 5)
    for k in range(5):                                                                      # vision blocks
        a = math.radians(-100 + k * 50)
        box(bm, (0.33 * math.sin(a), -0.75 + 0.33 * math.cos(a) * -1 * -1, 0.97), (0.12, 0.05, 0.1), Matrix.Rotation(-a, 3, 'Z'), 1)
    cyl(bm, (0, -0.75, 1.12), (0, -0.75, 1.2), 0.24, 0.24, 14, 0)
    box(bm, (0.5, 0.25, 0.855), (0.46, 0.42, 0.04), None, 5)                                # loader hatch
    box(bm, (-0.5, 0.2, 0.855), (0.46, 0.42, 0.04), None, 5)
    for sd in (-1, 1):
        box(bm, (sd * 0.955, 0.1, 0.45), (0.03, 0.48, 0.5), None, 5)                        # side hatch doors
        box(bm, (sd * 0.972, 0.1, 0.62), (0.02, 0.2, 0.07), None, 1)
        box(bm, (sd * 0.96, 0.82, 0.55), (0.03, 0.12, 0.08), None, 1)                       # vision slit
        box(bm, (sd * 1.235, 0.0, 0.5), (0.03, 2.3, 0.62), None, 0)                         # Schuerzen skirt plate
        for yy in (-0.95, -0.2, 0.55): box(bm, (sd * 1.1, yy, 0.78), (0.28, 0.05, 0.05), None, 2)
        for yy in (-0.95, 0.9): box(bm, (sd * 1.235, yy, 0.82), (0.05, 0.12, 0.06), None, 2)
        dquad(bm, (sd * 1.253, -0.55, 0.5), (0, sd, 0), (0, 0, 1), 0.86, 0.33, 3)           # number 413
        dquad(bm, (sd * 1.253, 0.65, 0.5), (0, sd, 0), (0, 0, 1), 0.42, 0.42, 4)             # balkenkreuz
    tur = finish(bm, 'pz4_turret', [P, DK, ST, D_N, D_X, PD], loc=(0, ring_y, ring_z), skip=(3, 4))

    # ---------------- gun (origin at trunnion = turret front face, centre height)
    bm = bmesh.new()
    box(bm, (0, 0.05, 0), (0.75, 0.36, 0.5), None, 0)
    box(bm, (0, 0.2, 0.02), (0.6, 0.12, 0.4), None, 5)
    cyl(bm, (0, 0.05, 0.28), (0, 1.0, 0.28), 0.055, 0.045, 10, 2)                           # recoil / recuperator housing
    box(bm, (0, 0.05, 0.28), (0.1, 0.3, 0.05), None, 0)
    cyl(bm, (0.22, 0.2, 0.0), (0.22, 0.42, 0.0), 0.04, 0.04, 8, 2)                          # coaxial MG
    cyl(bm, (0, 0.05, 0), (0, 0.4, 0), 0.17, 0.15, 12, 5)
    gun = finish(bm, 'pz4_gun', [P, DK, ST, RB, WD, PD], loc=(0, ring_y + 1.25, ring_z + 0.425))
    bm = bmesh.new()
    cyl(bm, (0, 0.2, 0), (0, 3.5, 0), 0.078, 0.052, 12, 0)
    cyl(bm, (0, 3.47, 0), (0, 3.85, 0), 0.07, 0.07, 10, 1)
    for y0 in (3.5, 3.66): cyl(bm, (0, y0, 0), (0, y0 + 0.1, 0), 0.125, 0.125, 12, 1)
    cyl(bm, (0, 3.78, 0), (0, 3.85, 0), 0.1, 0.1, 12, 1)
    bar = finish(bm, 'pz4_barrel', [DK, ST], loc=(0, ring_y + 1.25, ring_z + 0.425))
    # the barrel colour is steel-dark: re-assign slot 0 to the paint-dark steel look
    return hull, tur, gun, bar

# ====================================================================================================================
#  T-34/76
# ====================================================================================================================
def build_t34():
    P = mat('t34_paint', lin(76, 88, 52), 0.1, 0.85)
    DK = mat('t34_track', lin(52, 46, 40), 0.35, 0.8)
    ST = mat('t34_steel', lin(80, 76, 70), 0.45, 0.65)
    RB = mat('t34_rubber', lin(30, 30, 28), 0.0, 0.9)
    WD = mat('t34_wood', lin(116, 84, 50), 0.0, 0.9)
    PD = mat('t34_paintdark', lin(54, 64, 38), 0.1, 0.9)
    D_S = decal_mat('t34_decal_star', rgba_image('t34_star', star_img(256)))
    D_N = decal_mat('t34_decal_num', rgba_image('t34_num', num_img('101', 24, WHT, None, 0)))
    ring_y, ring_z = 0.5, 1.62

    # ---------------- hull
    bm = bmesh.new()
    stations(bm, [(-3.0, ring6(.55, .62, .85, .85, .85, 1.05)), (-2.8, ring6(.8, .42, 1.18, 1.0, 1.18, 1.42)),
                  (1.7, ring6(.8, .42, 1.18, 1.0, 1.18, 1.50)), (2.0, ring6(.8, .42, 1.18, 1.0, 1.15, 1.52)),
                  (2.75, ring6(.75, .45, 1.1, .9, 1.05, 1.12)), (3.02, ring6(.7, .62, .95, .8, .9, .88))], 0)
    cyl(bm, (0, ring_y, 1.38), (0, ring_y, 1.66), 0.92, 0.92, 20, 0)                       # turret ring collar
    for sd in (-1, 1):
        box(bm, (sd * 1.3, -0.1, 1.15), (0.44, 5.4, 0.05), None, 0)                        # fenders
        box(bm, (sd * 1.5, -0.1, 1.2), (0.04, 5.4, 0.1), None, 5)
        box(bm, (sd * 1.3, 2.95, 1.2), (0.46, 0.55, 0.05), Matrix.Rotation(-0.3, 3, 'X'), 0)    # front mudguards
        box(bm, (sd * 1.3, -3.0, 1.1), (0.46, 0.4, 0.05), Matrix.Rotation(0.12, 3, 'X'), 0)
        cyl(bm, (sd * 1.33, -2.5, 1.36), (sd * 1.33, -0.9, 1.36), 0.15, 0.15, 14, 5)       # external fuel drums
        for yy in (-2.45, -0.95): box(bm, (sd * 1.33, yy, 1.24), (0.1, 0.05, 0.14), None, 2)
        box(bm, (sd * 1.33, -0.55, 1.27), (0.3, 0.8, 0.22), None, 5)                       # tool / stowage box
        box(bm, (sd * 1.31, 1.4, 1.19), (0.09, 0.9, 0.04), None, 4)                        # log / shovel
        tube(bm, [(sd * 1.0, 2.3, 1.55), (sd * 0.78, 2.9, 1.0)], 0.02, 6, 1)               # tow cable
        cyl(bm, (sd * 0.55, 3.0, 0.78), (sd * 0.55, 3.14, 0.78), 0.05, 0.05, 8, 2)         # towing eyes
        cyl(bm, (sd * 0.7, -3.0, 0.78), (sd * 0.7, -3.12, 0.78), 0.05, 0.05, 8, 2)
        cyl(bm, (sd * 0.95, -2.9, 1.4), (sd * 0.95, -3.1, 1.12), 0.1, 0.12, 10, 2)         # exhaust covers
        box(bm, (sd * 1.3, 2.45, 1.19), (0.46, 0.1, 0.04), None, 5)
    # glacis details: driver's hatch, bow MG, headlight
    cyl(bm, (-0.42, 2.18, 1.58), (-0.42, 2.14, 1.64), 0.22, 0.2, 14, 5); cyl(bm, (-0.42, 2.1, 1.62), (-0.42, 2.12, 1.68), 0.15, 0.15, 12, 0)
    box(bm, (-0.42, 2.34, 1.5), (0.22, 0.06, 0.05), Matrix.Rotation(-0.8, 3, 'X'), 1)
    sphere(bm, (0.58, 2.3, 1.36), 0.12, 2, (1, 0.9, 1), 10); cyl(bm, (0.58, 2.35, 1.36), (0.58, 2.85, 1.3), 0.025, 0.025, 6, 2)
    cyl(bm, (-0.78, 2.55, 1.25), (-0.78, 2.62, 1.25), 0.1, 0.1, 12, 2)
    # engine deck: louvres and hatches, rear plate
    for i in range(8): box(bm, (0, -1.0 - i * 0.2, 1.43 + 0.0 - i * 0.004), (1.5, 0.12, 0.03), None, 5)
    box(bm, (0, -2.7, 1.38), (1.2, 0.36, 0.04), None, 5)
    for sd in (-1, 1): box(bm, (sd * 0.8, -1.9, 1.405), (0.4, 0.8, 0.03), None, 5)
    box(bm, (0, -3.02, 0.84), (0.8, 0.05, 0.4), None, 5)
    # ---- tracks and wheels
    xc = 1.2; w = 0.5
    WY = [1.7, 0.85, 0.0, -0.85, -1.7]; WR = 0.41; WZ = 0.06 + WR
    IDY, IDR, SPY, SPR = 2.62, 0.38, -2.6, 0.34
    circ = [(IDY, 0.055 + IDR, IDR), (SPY, 0.055 + SPR, SPR)] + [(y, WZ, WR + 0.0) for y in WY]
    for sd in (-1, 1):
        track(bm, sd * xc, w, circ, 0.055, 0.2, 1, 1, 3)
        for y in WY:
            wheel(bm, sd * (xc - 0.02), y, WZ, WR, 0.13, 3, 2, 16)
            for k in range(6):                                                                # lightening holes (dark spokes)
                a = 2 * math.pi * k / 6
                xcyl(bm, sd * (xc + 0.045), y + 0.2 * math.cos(a), WZ + 0.2 * math.sin(a), 0.06, 0.05, 1, 8)
        wheel(bm, sd * (xc + 0.02), IDY, 0.055 + IDR, IDR, 0.16, 3, 2, 14)                    # idler
        sprocket(bm, sd * (xc + 0.02), SPY, 0.055 + SPR, SPR, 0.22, sd, 2, 1)                  # sprocket
        box(bm, (sd * 1.0, 0.0, 0.9), (0.1, 4.0, 0.05), None, 2)                              # suspension cover rail
    hull = finish(bm, 't34_hull', [P, DK, ST, RB, WD, PD], skip=())

    # ---------------- turret
    bm = bmesh.new()
    TS = [(-1.15, ring8(.6, .62, .2, .55, .45, .35, .62)), (-0.95, ring8(.85, .95, .2, .9, .5, .55, .72)), (-0.2, ring8(1.0, 1.05, .2, 1.0, .5, .7, .82)),
          (0.5, ring8(.95, 1.0, .2, .9, .5, .6, .78)), (0.95, ring8(.65, .7, .2, .62, .45, .42, .68)), (1.15, ring8(.45, .5, .2, .45, .4, .3, .58))]
    stations(bm, TS, 0, smooth=True)
    for k, (hx, hy, r_) in enumerate(((-0.42, -0.3, 0.27), (0.42, -0.2, 0.25))):             # two round hatches
        cyl(bm, (hx, hy, 0.74), (hx, hy, 0.82), r_ * 1.12, r_ * 1.0, 16, 5)
        cyl(bm, (hx, hy, 0.82), (hx, hy, 0.86), r_ * 0.95, r_ * 0.95, 16, 0)
        box(bm, (hx, hy + r_ * 0.4, 0.89), (0.12, 0.04, 0.03), None, 2)
    for sd in (-1, 1):
        box(bm, (sd * 0.2, -0.95, 0.77), (0.1, 0.07, 0.07), None, 1)                         # periscope
    cyl(bm, (-0.6, 0.3, 0.8), (-0.6, 0.3, 0.86), 0.06, 0.06, 8, 2)
    # decals follow the turret surface
    def side_x(y, z, sd):
        ys = [s[0] for s in TS]; y = min(max(y, ys[0]), ys[-1])
        for i in range(len(TS) - 1):
            if ys[i] <= y <= ys[i + 1]:
                t = (y - ys[i]) / (ys[i + 1] - ys[i])
                pa, pb = TS[i][1], TS[i + 1][1]
                prof = [(pa[k][0] * (1 - t) + pb[k][0] * t, pa[k][1] * (1 - t) + pb[k][1] * t) for k in (1, 2, 3, 4)]
                prof = [(0.0 + p[0], p[1]) for p in prof]
                for j in range(len(prof) - 1):
                    if prof[j][1] <= z <= prof[j + 1][1]:
                        u = (z - prof[j][1]) / max(1e-6, prof[j + 1][1] - prof[j][1])
                        return prof[j][0] + (prof[j + 1][0] - prof[j][0]) * u, prof[j + 1][0] - prof[j][0], prof[j + 1][1] - prof[j][1]
                return prof[-1][0], 0.0, 1.0
        return 0.9, 0.0, 1.0
    for sd in (-1, 1):
        for (dy, dz, w_, h_, mi_) in ((0.5, 0.4, 0.62, 0.62, 3), (-0.3, 0.42, 0.58, 0.24, 4)):
            x, dx, dzz = side_x(dy, dz, sd); n = math.hypot(dx, dzz) or 1.0
            nrm = V((sd * dzz / n, 0, -dx / n)); up = V((sd * dx / n, 0, dzz / n))
            dquad(bm, V((sd * x, dy, dz)) + nrm * 0.02, (0, sd, 0), up, w_, h_, mi_)
    tur = finish(bm, 't34_turret', [P, DK, ST, D_S, D_N, PD], loc=(0, ring_y, ring_z), skip=(3, 4))

    # ---------------- gun
    bm = bmesh.new()
    sphere(bm, (0, 0.12, 0), 0.34, 0, (1.15, 0.8, 0.95), 14)
    box(bm, (0.0, 0.0, 0.0), (0.7, 0.3, 0.5), None, 0)
    cyl(bm, (0, 0.2, 0), (0, 0.5, 0), 0.19, 0.15, 14, 5)
    sphere(bm, (0.34, 0.28, 0.0), 0.075, 2, (1, 1, 1), 8); cyl(bm, (0.34, 0.3, 0), (0.34, 0.65, 0), 0.02, 0.02, 6, 2)   # coax MG
    gun = finish(bm, 't34_gun', [P, DK, ST, RB, WD, PD], loc=(0, ring_y + 1.15, ring_z + 0.425))
    bm = bmesh.new()
    cyl(bm, (0, 0.3, 0), (0, 3.45, 0), 0.098, 0.062, 14, 0)
    cyl(bm, (0, 3.35, 0), (0, 3.45, 0), 0.07, 0.075, 12, 1)
    bar = finish(bm, 't34_barrel', [PD, ST], loc=(0, ring_y + 1.15, ring_z + 0.425))
    return hull, tur, gun, bar

clear()
build_pz4()
preview_and_export('pz4', 'PANZER IV', SHOTS)
clear()
build_t34()
preview_and_export('t34', 'T-34', SHOTS)
print('TANKS DONE')
