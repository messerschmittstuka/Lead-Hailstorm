import bpy, os, math
import numpy as np

# ---- Ground textures: grass, trampled grass, mud, dirt, stone. Seamless 1024x1024, realistic but restrained (low contrast, no loud detail).
# Built from tileable filtered noise (FFT), so every edge wraps. Each one is saved as an albedo JPEG plus a normal-map JPEG
# into  models/textures/ , then laid out tiled 3x3 on a Blender sheet so the repeat is visible.
OUT = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models')
TEX = os.path.join(OUT, 'textures'); os.makedirs(TEX, exist_ok=True)
N = 1024

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
    for b in list(blk):
        if b.users == 0: blk.remove(b)

_fx = np.fft.fftfreq(N)[None, :]; _fy = np.fft.fftfreq(N)[:, None]
def fnoise(beta, seed, ax=1.0, ay=1.0, lo=0.0, hi=None):
    """tileable noise, zero mean, unit std. beta = how fast detail falls off (0 white .. 3 very smooth). ax/ay stretch it along x or y."""
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.standard_normal((N, N)))
    f = np.sqrt((_fx * ax) ** 2 + (_fy * ay) ** 2); f[0, 0] = 1.0
    F *= f ** (-beta / 2.0)
    if lo: F *= (f > lo)
    if hi: F *= (f < hi)
    a = np.real(np.fft.ifft2(F)); a -= a.mean()
    return (a / (a.std() + 1e-9)).astype(np.float32)

def smooth(a, k):
    """tileable box-ish blur by low-pass in frequency"""
    F = np.fft.fft2(a); f = np.sqrt(_fx ** 2 + _fy ** 2)
    return np.real(np.fft.ifft2(F * np.exp(-(f / (0.5 / k)) ** 2))).astype(np.float32)

def sstep(a, e0, e1):
    t = np.clip((a - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def lerp3(a, b, t):
    return a[None, None, :] + (b - a)[None, None, :] * t[:, :, None]

def col(r, g, b): return np.array([r, g, b], dtype=np.float32)

def blobs(seed, density, size):
    """sparse little bumps (pebbles / clods): a smoothed noise thresholded high, values 0..1"""
    n = smooth(fnoise(0.0, seed), size); n = (n - n.mean()) / (n.std() + 1e-9)
    return sstep(n, density, density + 0.9)

def finish(name, rgb, height, nstrength=2.5):
    rgb = np.clip(rgb, 0, 1)
    # normal map from the height (wrapping differences keep it seamless)
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5
    nx, ny, nz = -dx * nstrength, dy * nstrength, np.ones_like(height)
    L = np.sqrt(nx * nx + ny * ny + nz * nz); nrm = np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    out = {}
    for tag, arr, cs in (('', rgb, 'sRGB'), ('_n', nrm, 'Non-Color')):
        img = bpy.data.images.new(name + tag, N, N, alpha=False)
        px = np.ones((N, N, 4), dtype=np.float32); px[:, :, :3] = arr
        img.pixels = px.ravel().tolist(); img.update(); img.pack()
        img.colorspace_settings.name = cs
        img.filepath_raw = os.path.join(TEX, name + tag + '.jpg'); img.file_format = 'JPEG'
        img.save_render(os.path.join(TEX, name + tag + '.jpg'), scene=sc)
        out[tag] = img
    return out

# ---------------- grass: short, mixed green with a few dry blades ----------------
def grass():
    blade = fnoise(0.7, 11, 1.0, 0.16)                     # fine vertical streaks
    blade2 = fnoise(0.9, 12, 0.5, 0.5)
    clump = fnoise(2.3, 13)
    dry = sstep(fnoise(2.8, 14), 0.7, 1.7)
    v = 0.5 + 0.16 * blade + 0.07 * blade2 + 0.17 * clump
    dark, mid, light = col(0.085, 0.135, 0.045), col(0.17, 0.25, 0.075), col(0.29, 0.37, 0.11)
    t = np.clip(v, 0, 1)
    rgb = np.where((t < 0.5)[:, :, None], lerp3(dark, mid, t * 2), lerp3(mid, light, (t - 0.5) * 2))
    rgb = rgb * (1 - 0.30 * dry[:, :, None]) + col(0.33, 0.30, 0.15)[None, None, :] * (0.30 * dry[:, :, None])      # sun-dried patches
    soil = blobs(15, 2.6, 1.2); rgb = rgb * (1 - 0.35 * soil[:, :, None]) + col(0.16, 0.115, 0.07) * (0.35 * soil[:, :, None])   # specks of earth
    return finish('ground_grass', rgb, 0.5 * blade + 0.25 * blade2 + 0.5 * clump, 1.6)

# ---------------- trampled grass: flattened, straw coloured, earth showing through ----------------
def trampled():
    a = fnoise(0.8, 21, 1.0, 0.2); b = fnoise(0.8, 22, 0.2, 1.0)         # blades lying both ways
    clump = fnoise(2.6, 23); wear = fnoise(2.7, 24)
    v = 0.5 + 0.10 * a + 0.09 * b + 0.14 * clump
    dark, mid, light = col(0.12, 0.14, 0.055), col(0.23, 0.26, 0.095), col(0.36, 0.35, 0.16)
    t = np.clip(v, 0, 1)
    rgb = np.where((t < 0.5)[:, :, None], lerp3(dark, mid, t * 2), lerp3(mid, light, (t - 0.5) * 2))
    straw = sstep(fnoise(2.4, 25), 0.2, 1.4)
    rgb = rgb * (1 - 0.35 * straw[:, :, None]) + col(0.40, 0.35, 0.18)[None, None, :] * (0.35 * straw[:, :, None])
    bare = sstep(smooth(wear, 2.0), 0.35, 1.5)                                         # worn through to earth
    earth = lerp3(col(0.20, 0.15, 0.09), col(0.34, 0.26, 0.15), np.clip(0.5 + 0.2 * fnoise(0.9, 26) + 0.1 * fnoise(0.4, 27), 0, 1))
    rgb = rgb * (1 - 0.8 * bare[:, :, None]) + earth * (0.8 * bare[:, :, None])
    return finish('ground_trampled', rgb, 0.35 * a + 0.3 * b + 0.5 * clump - 0.4 * bare, 1.5)

# ---------------- mud: dark, lumpy, wet sheen areas, a few stones ----------------
def mud():
    lump = fnoise(2.4, 31); clod = fnoise(1.5, 32); fine = fnoise(0.8, 33)
    wet = sstep(-fnoise(2.9, 34), 0.45, 1.3)                               # smoother, darker, puddled
    v = 0.5 + 0.20 * lump + 0.14 * clod + 0.07 * fine
    v = v * (1 - 0.45 * wet) + 0.45 * wet * 0.55
    dark, light = col(0.10, 0.07, 0.045), col(0.31, 0.22, 0.135)
    rgb = lerp3(dark, light, np.clip(v, 0, 1))
    rgb = rgb * (1 - 0.35 * wet[:, :, None]) + col(0.085, 0.075, 0.07)[None, None, :] * (0.35 * wet[:, :, None])
    st = blobs(35, 2.7, 1.8); rgb = rgb * (1 - 0.5 * st[:, :, None]) + col(0.27, 0.235, 0.20) * (0.5 * st[:, :, None])
    return finish('ground_mud', rgb, 0.7 * lump + 0.4 * clod + 0.1 * fine - 0.9 * wet, 2.6)

# ---------------- dirt: dry tan earth, fine grain, a few pebbles, hairline cracks ----------------
def dirt():
    grain = fnoise(0.3, 41); mid = fnoise(1.1, 42); big = fnoise(2.6, 43)
    v = 0.5 + 0.11 * grain + 0.12 * mid + 0.12 * big
    dark, light = col(0.20, 0.145, 0.09), col(0.50, 0.40, 0.27)
    rgb = lerp3(dark, light, np.clip(v, 0, 1))
    crack = 1.0 - sstep(np.abs(fnoise(2.5, 44)), 0.0, 0.07)               # thin dark hairlines
    crack *= sstep(fnoise(2.8, 45), -0.3, 0.8)                             # only in some areas
    rgb = rgb * (1 - 0.45 * crack[:, :, None])
    peb = blobs(46, 2.1, 1.4); rgb = rgb * (1 - 0.5 * peb[:, :, None]) + col(0.52, 0.47, 0.39) * (0.5 * peb[:, :, None])
    return finish('ground_dirt', rgb, 0.25 * grain + 0.4 * mid + 0.5 * big - 0.8 * crack + 0.8 * peb, 2.0)

# ---------------- stone: weathered grey rock, blocky facets, strata, a little lichen ----------------
def stone():
    rng = np.random.default_rng(51); P = 46
    pts = rng.random((P, 2)) * N
    d1 = np.full((N, N), 1e9, np.float32); d2 = np.full((N, N), 1e9, np.float32); cid = np.zeros((N, N), np.int32)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    xx = xx + 12 * fnoise(2.2, 57); yy = yy + 12 * fnoise(2.2, 58)      # warp the cells so they are rock, not paving
    for i, (px, py) in enumerate(pts):
        dx = np.abs(xx - px); dx = np.minimum(dx, N - dx); dy = np.abs(yy - py); dy = np.minimum(dy, N - dy)
        d = np.sqrt(dx * dx + dy * dy)
        m1 = d < d1; d2 = np.where(m1, d1, np.minimum(d2, d)); cid = np.where(m1, i, cid); d1 = np.where(m1, d, d1)
    edge = (d2 - d1)
    tone = rng.random(P).astype(np.float32); warm = rng.random(P).astype(np.float32)
    base = 0.34 + 0.13 * tone[cid]
    strata = fnoise(1.8, 52, 0.12, 1.0)                                    # horizontal banding
    grain = fnoise(0.7, 53); mottle = fnoise(2.4, 54)
    v = base + 0.04 * strata + 0.04 * grain + 0.06 * mottle
    rgb = np.stack([v * (1.0 + 0.06 * warm[cid]), v * 0.98, v * (1.0 - 0.06 * warm[cid])], -1)
    seam = 1.0 - sstep(edge, 0.0, 11.0)                                     # dark joints between facets
    rgb = rgb * (1 - 0.46 * seam[:, :, None])
    lich = sstep(fnoise(2.6, 55), 1.1, 1.9) * sstep(fnoise(0.9, 56), -0.2, 1.0)
    rgb = rgb * (1 - 0.5 * lich[:, :, None]) + col(0.36, 0.40, 0.22) * (0.5 * lich[:, :, None])
    h = sstep(edge, 0.0, 14.0) * 0.9 + 0.12 * grain + 0.1 * strata + 0.1 * mottle
    return finish('ground_stone', rgb, h, 3.0)

imgs = {}
for nm, fn in (('grass', grass), ('trampled', trampled), ('mud', mud), ('dirt', dirt), ('stone', stone)):
    imgs[nm] = fn(); print('built', nm)

# ---------------- contact sheet: each texture tiled 3x3 on its own plane, top-down ----------------
sc = bpy.context.scene
for i, nm in enumerate(imgs):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(i * 1.06, 0, 0))
    pl = bpy.context.active_object; pl.name = 'p_' + nm
    m = bpy.data.materials.new('m_' + nm); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (3, 3, 3)
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = imgs[nm]['']; tx.interpolation = 'Linear'; tx.extension = 'REPEAT'
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
    nt.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
    m.diffuse_color = (0.3, 0.3, 0.3, 1); pl.data.materials.append(m)
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x = 2400; sc.render.resolution_y = 520
sc.render.image_settings.file_format = 'PNG'
sc.world = sc.world or bpy.data.worlds.new('w'); sc.world.color = (0.1, 0.1, 0.1)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 5.45; cam.location = (2.12, 0, 5); cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, 'ground_textures_sheet.png'); bpy.ops.render.render(write_still=True)
print('GROUND TEXTURES DONE')
