import bpy, bmesh, math, os, random
from mathutils import Vector, noise

# ---- Environment props, built in game units (1 unit = 1 m). Blender x = east, y = north, z = up (glTF export flips to Y-up).
# Every prop is a root empty  prop_<name>  (origin on the ground, centred) holding:
#   <name>        the visible mesh (one or more materials)
#   COL_<name>    the collision mesh: closed, low-poly, hugging the real silhouette (never a bounding box unless the prop IS a box).
#                 One COL_ mesh per prop, closed triangles, so the game can raycast it (bullets) and test movement against it.
# The game hides every COL_* mesh and uses it only for collision.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
BATCH = 'props_2'
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
def rock(name, seed, size, squash, mat_main, sub_vis=4, sub_col=2):
    sx, sy, sz = size
    def shape(p, fine):
        n = noise.noise(p * 1.25 + Vector((seed, seed * 0.7, seed * 1.3)))
        r = 1.0 + 0.32 * n
        if fine: r += 0.035 * noise.noise(p * 7.0 + Vector((seed * 2.1, 3.3, seed)))
        q = p * r; q.x *= sx; q.y *= sy; q.z *= sz * squash
        return q
    def build(sub, fine):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        for v in bm.verts: v.co = shape(v.co.normalized(), fine)
        zmin = -0.38 * sz * squash                                  # flat bottom: the rock sits in the ground
        for v in bm.verts:
            if v.co.z < zmin: v.co.z = zmin
        for v in bm.verts: v.co.z -= zmin
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        return bm
    root = new_root(name)
    vis = to_obj(name, build(sub_vis, True), [mat_main], True)
    colbm = build(sub_col, False)
    col = to_obj('COL_' + name, colbm, [M_ROCK], False)
    finish(root, vis, col, name); return root

# =============================================================== RUBBLE PILE (bricks + concrete chunks heaped into a mound, ~2 m across)
M_BRICK = mat('brick_rubble', (0.34, 0.16, 0.11), 0.95)
M_CONC = mat('concrete_rubble', (0.38, 0.37, 0.35), 0.95)
def chunk(bm, c, size, eul, jit, rnd):
    r = bmesh.ops.create_cube(bm, size=1.0); vs = r['verts']
    for v in vs: v.co = Vector((v.co.x * size[0] * (1 + (rnd.random() - 0.5) * jit), v.co.y * size[1] * (1 + (rnd.random() - 0.5) * jit), v.co.z * size[2] * (1 + (rnd.random() - 0.5) * jit)))
    from mathutils import Euler
    m = Euler(eul).to_matrix()
    for v in vs: v.co = m @ v.co + Vector(c)
    return vs
M_DUST = mat('rubble_dust', (0.27, 0.25, 0.22), 1.0)
def rubble_pile(name, seed, R, H, n):
    """a mound of packed rubble (the core) with bricks and concrete chunks sitting on and in it; the collision hull follows the mound + the chunks that stick out"""
    rnd = random.Random(seed); bm = bmesh.new(); hull = bmesh.new(); pts = []
    core = bmesh.new(); bmesh.ops.create_icosphere(core, subdivisions=3, radius=1.0)
    for v in core.verts:
        p = v.co.normalized(); k = 1 + 0.10 * noise.noise(p * 2.1 + Vector((seed, 1.3, 0.4))) + 0.03 * noise.noise(p * 7.0 + Vector((0.5, seed, 2.0)))
        v.co = Vector((p.x * R * k, p.y * R * k, max(0.0, p.z * H * k)))
    bmesh.ops.recalc_face_normals(core, faces=list(core.faces))
    for v in core.verts: pts.append(v.co.copy())
    for i in range(n):
        ang = rnd.random() * 6.283; rr = R * 0.93 * math.sqrt(rnd.random())
        top = H * math.sqrt(max(0.0, 1 - (rr / R) ** 2))
        sz = (0.14 + rnd.random() * 0.20, 0.08 + rnd.random() * 0.12, 0.07 + rnd.random() * 0.10)
        c = (math.cos(ang) * rr, math.sin(ang) * rr, max(sz[2] * 0.5, top - sz[2] * (0.1 + rnd.random() * 0.3)))
        eul = ((rnd.random() - 0.5) * 0.9, (rnd.random() - 0.5) * 0.9, rnd.random() * 6.283)
        vs = chunk(bm, c, sz, eul, 0.18, rnd); k = rnd.randrange(2); vset = set(vs)
        for f in bm.faces:
            if all(v in vset for v in f.verts): f.material_index = k
        for v in vs: pts.append(Vector((v.co.x, v.co.y, max(0.0, v.co.z))))
    for p in pts: hull.verts.new(p)
    tri_hull(hull)
    root = new_root(name)
    vc = to_obj(name + '_core', core, [M_DUST], True); vb = to_obj(name, bm, [M_BRICK, M_CONC], False)
    bpy.ops.object.select_all(action='DESELECT'); vb.select_set(True); vc.select_set(True); bpy.context.view_layer.objects.active = vb
    vb.data.materials.append(M_DUST)
    for p in vc.data.polygons: p.material_index = 2
    bpy.ops.object.join(); vis = bpy.context.view_layer.objects.active; vis.name = name
    col = to_obj('COL_' + name, hull, [M_CONC], False)
    finish(root, vis, col, name); return root

# =============================================================== OIL DRUM (0.58 m across, 0.88 m tall, two rolling hoops)
def lathe(bm, prof, seg):
    rings = []
    for (r, z) in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg; bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
def barrel():
    R = 0.29; Hh = 0.88
    prof = [(R - 0.03, 0.0), (R, 0.015), (R, 0.20), (R + 0.012, 0.215), (R + 0.012, 0.245), (R, 0.26), (R, 0.62), (R + 0.012, 0.635), (R + 0.012, 0.665), (R, 0.68), (R, Hh - 0.03), (R - 0.025, Hh - 0.015), (R - 0.05, Hh - 0.03), (R - 0.05, Hh - 0.045), (R - 0.2, Hh - 0.05), (R - 0.2, Hh - 0.045)]
    bm = bmesh.new(); lathe(bm, prof, 28); bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    root = new_root('barrel_oil'); vis = to_obj('barrel_oil', bm, [M_DRUM], True)
    cb = bmesh.new(); lathe(cb, [(R + 0.012, 0.0), (R + 0.012, Hh)], 12)
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    col = to_obj('COL_barrel_oil', cb, [M_DRUM], False)
    finish(root, vis, col, 'barrel_oil'); return root
M_DRUM = mat('drum', (0.17, 0.22, 0.14), 0.55, 0.45)

# =============================================================== AMMO CRATE (0.60 x 0.32 x 0.30, olive wood, metal handles and clasps)
M_AMMO = mat('ammo_wood', (0.22, 0.25, 0.14), 0.9)
def ammo_crate():
    W, D, H = 0.60, 0.32, 0.30
    bw = bmesh.new(); bmm = bmesh.new()
    box_geo(bw, (0, 0, H * 0.5 - 0.01), (W, D, H - 0.02))                                   # body
    box_geo(bw, (0, 0, H - 0.012), (W + 0.012, D + 0.012, 0.024))                          # lid
    for sx in (-1, 1): box_geo(bw, (sx * (W / 2 - 0.05), 0, H + 0.004), (0.04, D + 0.012, 0.018))   # lid battens
    for sx in (-1, 1): box_geo(bw, (sx * (W / 2 - 0.05), 0, 0.012), (0.04, D + 0.012, 0.024))       # foot battens
    for sx in (-1, 1):
        for sy in (-1, 1): pass
    for sx in (-1, 1): box_geo(bmm, (sx * (W / 2 + 0.008), 0, H * 0.62), (0.014, 0.12, 0.012)); box_geo(bmm, (sx * (W / 2 + 0.014), 0, H * 0.62 - 0.03), (0.01, 0.12, 0.012))   # rope handle bars on the ends
    for sy in (-1, 1): box_geo(bmm, (0.0, sy * (D / 2 + 0.005), H - 0.04), (0.06, 0.01, 0.05))   # lid clasp
    root = new_root('crate_ammo')
    vw = to_obj('crate_ammo', bw, [M_AMMO], False); vm = to_obj('crate_ammo_metal', bmm, [M_METAL], False)
    bpy.ops.object.select_all(action='DESELECT'); vw.select_set(True); vm.select_set(True); bpy.context.view_layer.objects.active = vw
    vw.data.materials.append(M_METAL)
    for p in vm.data.polygons: p.material_index = 1
    bpy.ops.object.join(); vis = bpy.context.view_layer.objects.active; vis.name = 'crate_ammo'
    cb = bmesh.new(); box_geo(cb, (0, 0, (H + 0.014) / 2), (W + 0.04, D + 0.014, H + 0.014))
    bmesh.ops.triangulate(cb, faces=list(cb.faces)); bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    col = to_obj('COL_crate_ammo', cb, [M_AMMO], False)
    finish(root, vis, col, 'crate_ammo'); return root

# ---------------------------------------------------------------- build the batch
rock('rock_slab', 9.3, (0.75, 0.55, 0.26), 1.0, M_ROCK)
rubble_pile('rubble_pile_a', 3, 1.0, 0.5, 55)
barrel()
ammo_crate()

# lay them out in a row (for the preview and so the file is readable); the game ignores the position and re-centres each prop
for i, r in enumerate(ROOTS): r.location = (i * 3.2, 0, 0)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export (visible + COL_ meshes, parented under each prop_ root)
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects: ob.select_set(True)
glb = os.path.join(OUT, BATCH + '.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_apply=True, export_yup=True)
print('PROPS EXPORTED', os.path.getsize(glb), 'bytes')
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
cx = (len(ROOTS) - 1) * 3.2 / 2
for ob in bpy.data.objects:
    if ob.name.startswith('COL_'): ob.hide_render = True
shot(BATCH + '_view.png', cx, 17.0, 6.0, 14, 0.4)
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
shot(BATCH + '_col.png', cx, 17.0, 6.0, 14, 0.4)
print('PROPS DONE')
