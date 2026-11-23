import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'walls_1'
os.makedirs(OUT, exist_ok=True)

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
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

# =============================================================== ROCKS
# A rock's big shape is a low-frequency noise on a sphere (that is what COL_ follows); the visible mesh adds small bumps on top (+-2 cm).


# =============================================================== MODULAR BRICK WALL KIT  (3.0 m wide, 3.0 m high = one storey, 0.5 m thick)
# Origin = centre of the wall's foot, on the ground.  x = along the wall, y = thickness, z = up.  Pieces butt end to end on the 3 m grid
# (the game stretches/squeezes the width a little to fit a building's length) and stack every 3 m.
W_ = 3.0; H_ = 3.0; T_ = 0.5
M_BR = [mat('brick_a', (0.42, 0.20, 0.15), 0.95), mat('brick_b', (0.36, 0.17, 0.13), 0.95), mat('brick_c', (0.47, 0.25, 0.19), 0.95)]
M_CORE = mat('mortar', (0.40, 0.37, 0.33), 1.0)
M_STONE = mat('stone', (0.46, 0.45, 0.42), 0.9)
M_PLINTH = mat('plinth', (0.30, 0.28, 0.26), 1.0)
M_FRAME = mat('frame_wood', (0.16, 0.10, 0.06), 0.9)
MATS_W = M_BR + [M_CORE, M_STONE, M_PLINTH, M_FRAME]      # material slots: 0-2 bricks, 3 mortar core, 4 stone, 5 plinth, 6 frame
I_CORE, I_STONE, I_PLINTH, I_FRAME = 3, 4, 5, 6

def abox(bm, x0, x1, y0, y1, z0, z1, mi, skip_back=False):
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for k, f in enumerate(fs):
        if skip_back and k == 0: continue
        fc = bm.faces.new([v[i] for i in f]); fc.material_index = mi

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
        for z0, z1 in rr: abox(bm, x0, x1, -T_ / 2 + 0.045, T_ / 2 - 0.045, z0, z1 - 0.005, I_CORE)
    brick_faces(bm, pred, rnd, zmax)
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
    root = new_root(name); vis = to_obj(name, bm, MATS_W, False); col = to_obj('COL_' + name, cb, [M_CORE], False)
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
    return build_wall('wall_brick_ruined', pred, 24, H_, coping=False, extras=ex)

# ---------------------------------------------------------------- build the batch
wall_solid(); wall_window(); wall_door(); wall_ruined()
for i, r in enumerate(ROOTS): r.location = (i * 3.8, 0, 0)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True)
print('WALLS EXPORTED', os.path.getsize(glb), 'bytes')
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
cx = (len(ROOTS) - 1) * 3.8 / 2
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 19.0, 3.2, 16, 1.4)
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
shot(BATCH + '_col.png', cx, 19.0, 3.2, 16, 1.4)

# third preview: ONLY the collision shapes, solid red (shows exactly what bullets and feet will hit)
for ob in list(bpy.data.objects):
    if ob.name.startswith('cage_') or ob.name == gp.name: ob.hide_render = ob.name.startswith('cage_')
    elif ob.name.startswith('COL_'):
        ob.hide_render = False; ob.data.materials.clear(); ob.data.materials.append(wm)
    elif ob.type == 'MESH': ob.hide_render = True
shot(BATCH + '_colonly.png', cx, 19.0, 3.2, 16, 1.4)
print('WALLS DONE')
