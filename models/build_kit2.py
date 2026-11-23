import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'kit_2'
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

# =============================================================== STRUCTURAL KIT: floor slabs, stairs, chimney  (same conventions as the walls: 1 unit = 1 m, 3 m grid)
M_BR = [mat('brick_a', (0.42, 0.20, 0.15), 0.95), mat('brick_b', (0.36, 0.17, 0.13), 0.95), mat('brick_c', (0.47, 0.25, 0.19), 0.95)]
M_CORE = mat('mortar', (0.40, 0.37, 0.33), 1.0)
M_STONE = mat('stone', (0.46, 0.45, 0.42), 0.9)
M_CONC = mat('concrete', (0.42, 0.41, 0.39), 0.95)
M_BOARD = mat('floorboard', (0.30, 0.20, 0.12), 0.9)
M_REBAR = mat('rebar', (0.28, 0.13, 0.07), 0.7, 0.4)
M_SOOT = mat('soot', (0.05, 0.05, 0.05), 1.0)
M_TIMBER = mat('timber', (0.24, 0.15, 0.08), 0.9)
MK = M_BR + [M_CORE, M_STONE, M_CONC, M_BOARD, M_REBAR, M_SOOT, M_TIMBER]     # slots: 0-2 brick, 3 mortar, 4 stone, 5 concrete, 6 board, 7 rebar, 8 soot, 9 timber
I_CORE, I_STONE, I_CONC, I_BOARD, I_REBAR, I_SOOT, I_TIMBER = 3, 4, 5, 6, 7, 8, 9

def abox(bm, x0, x1, y0, y1, z0, z1, mi):
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        fc = bm.faces.new([v[i] for i in f]); fc.material_index = mi

def prism_x(bm, prof, x0, x1, mi):
    """extrude a convex (y,z) profile along x from x0 to x1"""
    a = [bm.verts.new((x0, y, z)) for y, z in prof]; b = [bm.verts.new((x1, y, z)) for y, z in prof]
    for f in (a[::-1], b):
        fc = bm.faces.new(f); fc.material_index = mi
    for i in range(len(prof)):
        j = (i + 1) % len(prof); fc = bm.faces.new((a[i], a[j], b[j], b[i])); fc.material_index = mi

def finish_kit(name, bm, cb, pivot_note=''):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    root = new_root(name); vis = to_obj(name, bm, MK, False); col = to_obj('COL_' + name, cb, [M_CORE], False)
    finish(root, vis, col, name); return root

# ---------------------------------------------------------------- FLOOR SLAB  (3 x 3 m, origin = centre of the WALKING surface; the slab hangs 0.3 m below)
def floor_slab():
    bm = bmesh.new(); cb = bmesh.new(); rnd = random.Random(31)
    abox(bm, -1.5, 1.5, -1.5, 1.5, -0.30, -0.03, I_CONC)
    for i in range(12):                                                                       # floorboards, a little uneven
        y0 = -1.5 + i * 0.25; x_split = rnd.uniform(-0.8, 0.8)
        for xa, xb in ((-1.5, x_split - 0.006), (x_split + 0.006, 1.5)):
            abox(bm, xa, xb, y0 + 0.006, y0 + 0.244, -0.032 + rnd.random() * 0.004, 0.0, I_BOARD)
    for x in (-1.0, 0.0, 1.0): abox(bm, x - 0.06, x + 0.06, -1.5, 1.5, -0.42, -0.30, I_CONC)   # concrete ribs under the slab
    abox(cb, -1.5, 1.5, -1.5, 1.5, -0.30, 0.0, 0)
    for x in (-1.0, 0.0, 1.0): abox(cb, x - 0.06, x + 0.06, -1.5, 1.5, -0.42, -0.30, 0)
    return finish_kit('floor_slab', bm, cb)

def floor_slab_broken():
    bm = bmesh.new(); cb = bmesh.new(); rnd = random.Random(32); N = 12; C = 0.25
    def solid(i, j):
        cx = -1.5 + (i + 0.5) * C; cy = -1.5 + (j + 0.5) * C
        a = math.atan2(cy + 0.15, cx - 0.35); r = math.hypot(cx - 0.35, cy + 0.15)
        if r < 0.95 + 0.22 * math.sin(a * 3 + 1.0) + 0.12 * math.sin(a * 7): return False      # the hole, ragged
        if i >= N - 2 and j >= N - 2 and (i + j) % 2 == 0: return False                       # a chipped corner
        return True
    for j in range(N):
        i = 0
        while i < N:
            if not solid(i, j): i += 1; continue
            k = i
            while k < N and solid(k, j): k += 1
            x0 = -1.5 + i * C; x1 = -1.5 + k * C; y0 = -1.5 + j * C; y1 = y0 + C
            abox(bm, x0, x1, y0, y1, -0.30, -0.03, I_CONC)
            abox(bm, x0, x1, y0 + 0.006, y1 - 0.006, -0.032, 0.0, I_BOARD)
            abox(cb, x0, x1, y0, y1, -0.30, 0.0, 0)
            i = k
    for (x, y, d) in ((0.05, -0.55, 'x'), (0.35, 0.40, 'y'), (-0.05, -0.1, 'x'), (0.85, -0.55, 'y'), (0.75, 0.2, 'x')):     # rebar poking into the hole
        L = 0.45
        if d == 'x': abox(bm, x - L / 2, x + L / 2, y - 0.012, y + 0.012, -0.17, -0.14, I_REBAR)
        else: abox(bm, x - 0.012, x + 0.012, y - L / 2, y + L / 2, -0.17, -0.14, I_REBAR)
    return finish_kit('floor_slab_broken', bm, cb)

# ---------------------------------------------------------------- WOODEN STAIRS  (17 steps, 1.2 m wide, climbs 3.0 m over 4.25 m; origin = bottom front centre, climbs toward +y)
def stairs_wood():
    bm = bmesh.new(); cb = bmesh.new(); N = 17; RISE = 3.0 / N; RUN = 0.25; W = 1.2
    for i in range(N):
        top = (i + 1) * RISE; y0 = i * RUN
        abox(bm, -W / 2, W / 2, y0 - 0.02, y0 + RUN, top - 0.04, top, I_TIMBER)               # tread with a nosing
        abox(bm, -W / 2, W / 2, y0 - 0.02, y0, top - RISE, top - 0.04, I_BOARD)                # riser
        abox(cb, -W / 2, W / 2, y0, y0 + RUN, 0.0, top, 0)                                      # collision: solid under each step
    slope = (3.0 - RISE) / ((N - 1) * RUN)
    for x0, x1 in ((-W / 2 - 0.05, -W / 2), (W / 2, W / 2 + 0.05)):                           # side stringers
        prism_x(bm, [(0.0, 0.0), (N * RUN, 3.0 - 0.42), (N * RUN, 3.0 - 0.04), (0.0, RISE - 0.04)], x0, x1, I_TIMBER)
    for k in (0, 8, 16):                                                                       # newel posts + handrail on the +x side
        y = k * RUN + 0.1; z0 = (k + 1) * RISE
        abox(bm, W / 2 - 0.03, W / 2 + 0.05, y - 0.04, y + 0.04, z0, z0 + 0.98, I_TIMBER)
    z_a = RISE + 0.98; z_b = 3.0 - RISE + 0.98 - 0.12
    prism_x(bm, [(0.1, z_a - 0.04), (16 * RUN + 0.1, z_b - 0.04), (16 * RUN + 0.1, z_b + 0.04), (0.1, z_a + 0.04)], W / 2 - 0.01, W / 2 + 0.05, I_TIMBER)
    return finish_kit('stairs_wood', bm, cb)

# ---------------------------------------------------------------- BRICK CHIMNEY BREAST with fireplace  (1.2 x 0.72, stack to 4.2 m; origin = centre of the foot; fireplace faces +y)
CH = 0.12
def brick_side(bm, nsign, axis, HU, HN, z0, z1, rnd, pred=lambda u, z: True):
    for k in range(int(round((z1 - z0) / CH))):
        za = z0 + k * CH + 0.008; zb = z0 + k * CH + CH - 0.008; zm = (za + zb) / 2
        u = -HU - (k % 2) * 0.26 - rnd.random() * 0.04
        while u < HU:
            ln = rnd.choice((0.50, 0.50, 0.75, 0.25)); a = max(u + 0.008, -HU); b = min(u + ln - 0.008, HU); u += ln
            if b - a < 0.06: continue
            s = 0.025; pcs = []; cur = None
            for q in range(int(round((b - a) / s))):
                um = a + (q + 0.5) * s; ok = pred(um, zm)
                if ok and cur is None: cur = a + q * s
                if not ok and cur is not None: pcs.append((cur, a + q * s)); cur = None
            if cur is not None: pcs.append((cur, b))
            mi = rnd.choices((0, 1, 2), (4, 3, 3))[0]
            for p0, p1 in pcs:
                if p1 - p0 < 0.05: continue
                d = 0.017 + rnd.random() * 0.012
                n0, n1 = (HN - 0.045, HN - 0.045 + d + 0.03) if nsign > 0 else (-(HN - 0.045 + d + 0.03), -(HN - 0.045))
                if axis == 'y': abox(bm, p0, p1, n0, n1, za, zb, mi)         # faces looking along +-y (u runs along x)
                else: abox(bm, n0, n1, p0, p1, za, zb, mi)                   # faces looking along +-x (u runs along y)

def chimney_brick():
    bm = bmesh.new(); cb = bmesh.new(); rnd = random.Random(41)
    HX, HY, HB, HSX, HSY = 0.60, 0.36, 3.0, 0.45, 0.30
    # mortar core of the breast, with the fireplace recess (0.72 wide, 0.95 high, 0.36 deep) cut into the front
    abox(bm, -HX + 0.045, HX - 0.045, -HY + 0.045, 0.0, 0.0, HB, I_CORE)
    abox(bm, -HX + 0.045, -0.36, 0.0, HY - 0.045, 0.0, HB, I_CORE); abox(bm, 0.36, HX - 0.045, 0.0, HY - 0.045, 0.0, HB, I_CORE)
    abox(bm, -0.36, 0.36, 0.0, HY - 0.045, 0.95, HB, I_CORE)
    abox(bm, -0.36, 0.36, 0.0, 0.012, 0.0, 0.95, I_SOOT)                                       # soot-black back of the firebox
    for nsign, axis, HU, HN, pr in ((1, 'y', HX, HY, lambda u, z: not (abs(u) < 0.36 and z < 0.95)), (-1, 'y', HX, HY, lambda u, z: True),
                                    (1, 'x', HY, HX, lambda u, z: True), (-1, 'x', HY, HX, lambda u, z: True)):
        brick_side(bm, nsign, axis, HU, HN, 0.0, HB, rnd, pr)
    abox(bm, -0.52, 0.52, -0.33, 0.33, HB, HB + 0.15, I_STONE)                                  # corbel where the breast narrows
    abox(bm, -HSX + 0.045, HSX - 0.045, -HSY + 0.045, HSY - 0.045, HB + 0.15, 4.2, I_CORE)      # the stack
    for nsign, axis, HU, HN in ((1, 'y', HSX, HSY), (-1, 'y', HSX, HSY), (1, 'x', HSY, HSX), (-1, 'x', HSY, HSX)):
        brick_side(bm, nsign, axis, HU, HN, HB + 0.15, 4.2, rnd)
    abox(bm, -0.52, 0.52, -0.36, 0.36, 4.2, 4.3, I_STONE)                                       # cap stone
    abox(bm, -0.5, 0.5, HY - 0.05, HY + 0.19, 0.0, 0.06, I_STONE)                               # hearth slab
    abox(bm, -0.66, 0.66, HY - 0.05, HY + 0.1, 1.05, 1.14, I_TIMBER)                            # wooden mantel
    for x in (-0.4, 0.4): abox(bm, x - 0.03, x + 0.03, HY - 0.05, HY + 0.07, 0.95, 1.05, I_TIMBER)   # mantel brackets
    # collision: the breast around the recess, the stack, the cap, the hearth
    abox(cb, -HX, HX, -HY, 0.0, 0.0, HB, 0)
    abox(cb, -HX, -0.36, 0.0, HY, 0.0, HB, 0); abox(cb, 0.36, HX, 0.0, HY, 0.0, HB, 0)
    abox(cb, -0.36, 0.36, 0.0, HY, 0.95, HB, 0)
    abox(cb, -HSX, HSX, -HSY, HSY, HB, 4.2, 0); abox(cb, -0.52, 0.52, -0.36, 0.36, 4.2, 4.3, 0)
    abox(cb, -0.5, 0.5, HY, HY + 0.19, 0.0, 0.06, 0)
    return finish_kit('chimney_brick', bm, cb)

# ---------------------------------------------------------------- build the batch
floor_slab(); floor_slab_broken(); stairs_wood(); chimney_brick()
for r, (x, z, rz) in zip(ROOTS, ((0.0, 0.45, 0), (3.6, 0.45, 0), (8.2, 0, 90), (12.2, 0, 0))):
    r.location = (x, 0, z); r.rotation_euler = (0, 0, math.radians(rz))
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_extras=True)
print('KIT EXPORTED', os.path.getsize(glb), 'bytes')
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
cx = 5.9
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 23.0, 5.5, 16, 1.4)
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
shot(BATCH + '_col.png', cx, 23.0, 5.5, 16, 1.4)

for ob in list(bpy.data.objects):
    if ob.name.startswith('cage_'): ob.hide_render = True
    elif ob.name.startswith('COL_'): ob.hide_render = False; ob.data.materials.clear(); ob.data.materials.append(wm)
    elif ob.type == 'MESH' and ob.name != gp.name: ob.hide_render = True
shot(BATCH + '_colonly.png', cx, 23.0, 5.5, 16, 1.4)
for ob in list(bpy.data.objects):
    if ob.name.startswith('COL_') or ob.name.startswith('cage_'): ob.hide_render = True
    elif ob.type == 'MESH': ob.hide_render = False
sc.render.resolution_x = 1100; sc.render.resolution_y = 900
shot(BATCH + '_chimney.png', 12.2, 7.5, 1.9, 196, 1.9)
print('KIT DONE')
