import bpy, sys, os, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/gun/'; os.makedirs(OUT, exist_ok=True)

def save_rgb(path, arr):
    h, w = arr.shape[:2]; im = bpy.data.images.new('t', w, h, alpha=False); im.colorspace_settings.name = 'sRGB'
    a4 = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], 2).astype(np.float32); im.pixels.foreach_set(a4.ravel())
    im.filepath_raw = path; im.file_format = 'JPEG'; im.save(); bpy.data.images.remove(im)

def seam(a): return round(float(np.abs(a[:, 0] - a[:, -1]).mean() / (np.abs(a[:, 5] - a[:, 6]).mean() + 1e-9)), 2), round(float(np.abs(a[0] - a[-1]).mean() / (np.abs(a[5] - a[6]).mean() + 1e-9)), 2)

def scratches(n, seed, count, lo, hi, lmin=10, lmax=80, wmin=0.7, wmax=1.3):
    rng = np.random.default_rng(seed); card = new_card(n, n); WRAP[0] = True
    scatter_strokes(card, rng, n, count, lmin, lmax, wmin, wmax, [(lo, hi)], None); WRAP[0] = False
    return card

def box_blur(a, k, axis):
    """cheap wrap-around box blur along one axis"""
    out = np.zeros_like(a)
    for s in range(-(k // 2), k - k // 2): out += np.roll(a, s, axis)
    return out / k

def walnut(W=2048, H=512, seed=5, base=(0.30, 0.145, 0.06)):
    """oiled walnut stock: ring figure, long fibres, pores, hand-oil darkening, dings and scratches. rows = round the stock, columns = along it"""
    rng = np.random.default_rng(seed)
    r = lambda: rng.random((H, W)).astype(np.float32)
    nrm_ = lambda a: (a - a.mean()) / (a.std() + 1e-6)
    streak = nrm_(box_blur(box_blur(r(), 220, 1), 2, 0)); warp = nrm_(box_blur(box_blur(r(), 700, 1), 40, 0)); fine = nrm_(box_blur(r(), 24, 1))
    yy = (np.arange(H, dtype=np.float32) / H)[:, None]
    ph = yy * 11.0 + warp * 0.55 + streak * 0.18
    rings = np.clip(0.5 + 0.5 * np.sin(2 * np.pi * ph), 0, 1) ** 1.6
    pores = np.clip(box_blur((r() > 0.9965).astype(np.float32), 14, 1) * 6.0, 0, 1)
    v = 0.60 - 0.34 * rings + 0.10 * np.clip(streak * 0.35, -1, 1) + 0.12 * np.clip(warp * 0.4, -1, 1) + 0.05 * fine - 0.30 * pores
    v = np.clip(v, 0.05, 1.0); b = np.array(base, np.float32)
    dark = b * np.array([0.38, 0.34, 0.30], np.float32); light = b * np.array([1.30, 1.30, 1.15], np.float32)
    tint = (0.5 + 0.5 * np.clip(streak * 0.3, -1, 1))[:, :, None] * np.array([0.10, 0.02, -0.02], np.float32)
    rgb = dark[None, None, :] + (light - dark)[None, None, :] * v[:, :, None] + tint * 0.4 * b[None, None, :]
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    oil = np.clip(nrm_(box_blur(box_blur(r(), 400, 1), 60, 0)) * 0.5 + 0.5, 0, 1)                   # hand oil / grime darkening in long patches
    rgb = rgb * (1 - 0.30 * oil[..., None] * np.array([0.9, 1.0, 1.1], np.float32)[None, None, :])
    h = 0.5 + 0.04 * rings + 0.03 * streak - 0.35 * pores + 0.01 * fine
    for _ in range(46):                                                                              # dings and dents
        cx = rng.random() * W; cy = rng.random() * H; rr = 2 + rng.random() * 7
        d = np.exp(-(((X - cx + W / 2) % W - W / 2) ** 2 + ((Y - cy + H / 2) % H - H / 2) ** 2) / (2 * rr * rr))
        h -= d * (0.25 + 0.5 * rng.random()); rgb = rgb * (1 - 0.35 * d[..., None])
    for _ in range(260):                                                                             # fine scratches
        x0 = rng.random() * W; y0 = rng.random() * H; L = 20 + rng.random() * 120; a = rng.normal(0, 0.35)
        t = np.linspace(0, 1, int(L)); xs = ((x0 + t * L * np.cos(a)) % W).astype(int); ys = ((y0 + t * L * np.sin(a)) % H).astype(int)
        h[ys, xs] -= 0.10; rgb[ys, xs] = rgb[ys, xs] * 0.8 + np.array([0.36, 0.25, 0.14], np.float32) * 0.2
    return np.clip(rgb, 0, 1), h

def blued(n=1024, seed=901):
    """blued steel: blue-black with plum patina, brushed along the barrel, oil sheen, silvery wear flecks and scratches"""
    t = fbm(n, seed, 3, 60, 4)
    col = ramp(0.55 * t + 0.45 * fbm(n, seed + 1, 6, 6, 4), [(0, (0.012, 0.014, 0.021)), (0.6, (0.028, 0.032, 0.045)), (1, (0.055, 0.060, 0.075))])
    pat = smooth(fbm(n, seed + 2, 5, 5, 5), 0.55, 0.82) * 0.55
    col = col * (1 - pat[..., None]) + np.array([0.085, 0.060, 0.055])[None, None, :] * pat[..., None]
    wear = smooth(fbm(n, seed + 3, 14, 14, 5) + 0.5 * fbm(n, seed + 4, 90, 90, 3), 1.05, 1.22)
    col = col * (1 - wear[..., None]) + np.array([0.30, 0.31, 0.33])[None, None, :] * (0.6 + 0.4 * fbm(n, seed + 5, 60, 60, 3))[..., None] * wear[..., None]
    sc = scratches(n, seed + 6, 240, (0.20, 0.21, 0.23), (0.36, 0.37, 0.40))
    col = col * (1 - 0.55 * sc[..., 3:4]) + sc[..., :3] * 0.55 * sc[..., 3:4]
    oil = smooth(fbm(n, seed + 7, 4, 4, 4), 0.6, 0.85) * 0.25; col = col * (1 - oil[..., None])
    h = 0.55 + 0.04 * t + 0.03 * fbm(n, seed + 8, 140, 140, 2) - 0.06 * sc[..., 3] - 0.05 * wear
    return col, h

def parker(n=1024, seed=911):
    """manganese phosphate (parkerised) finish: grey-green granular, worn lighter on the high points"""
    g = fbm(n, seed, 220, 220, 3)
    col = ramp(0.6 * g + 0.4 * fbm(n, seed + 1, 7, 7, 4), [(0, (0.040, 0.046, 0.040)), (0.6, (0.070, 0.076, 0.066)), (1, (0.105, 0.110, 0.095))])
    wear = smooth(fbm(n, seed + 2, 12, 12, 5) + 0.5 * fbm(n, seed + 3, 80, 80, 3), 1.0, 1.2)
    col = col * (1 - wear[..., None]) + np.array([0.20, 0.20, 0.19])[None, None, :] * wear[..., None]
    sc = scratches(n, seed + 4, 160, (0.18, 0.18, 0.17), (0.32, 0.32, 0.30))
    col = col * (1 - 0.45 * sc[..., 3:4]) + sc[..., :3] * 0.45 * sc[..., 3:4]
    rust = smooth(fbm(n, seed + 5, 9, 9, 5) + 0.3 * fbm(n, seed + 6, 60, 60, 3), 0.98, 1.15) * 0.6
    col = col * (1 - rust[..., None]) + np.array([0.20, 0.08, 0.03])[None, None, :] * rust[..., None]
    h = 0.55 + 0.10 * g - 0.05 * sc[..., 3]
    return col, h

def steel(n=1024, seed=921):
    """bright, much-handled steel: brushed, scratched, dull grey with oily dark patches"""
    t = fbm(n, seed, 2, 70, 4)
    col = ramp(0.6 * t + 0.4 * fbm(n, seed + 1, 5, 5, 4), [(0, (0.10, 0.105, 0.11)), (0.6, (0.18, 0.185, 0.195)), (1, (0.28, 0.285, 0.295))])
    oil = smooth(fbm(n, seed + 2, 4, 4, 5), 0.5, 0.8) * 0.5; col = col * (1 - 0.5 * oil[..., None])
    sc = scratches(n, seed + 3, 300, (0.40, 0.40, 0.41), (0.62, 0.62, 0.63))
    col = col * (1 - 0.5 * sc[..., 3:4]) + sc[..., :3] * 0.5 * sc[..., 3:4]
    rust = smooth(fbm(n, seed + 4, 8, 8, 5) + 0.4 * fbm(n, seed + 5, 80, 80, 3), 1.0, 1.18) * 0.7
    col = col * (1 - rust[..., None]) + np.array([0.26, 0.10, 0.04])[None, None, :] * rust[..., None]
    h = 0.55 + 0.05 * t - 0.08 * sc[..., 3] + 0.1 * rust
    return col, h

for name, fn, st, size in (('blued', lambda: blued(1024), 2.0, 1024), ('parker', lambda: parker(1024), 2.0, 1024), ('steel', lambda: steel(1024), 2.0, 1024)):
    col, h = fn(); srgb = to_srgb(col); hn = (h - h.min()) / (h.max() - h.min() + 1e-9)
    save_rgb(OUT + name + '_c.jpg', srgb); save_rgb(OUT + name + '_n.jpg', normal_from_height(hn, st))
    print(name, 'seam', seam(srgb), 'mean', np.round(srgb.mean((0, 1)), 3))
rgb, h = walnut(2048, 512, 5)
hn = (h - h.min()) / (h.max() - h.min() + 1e-9)
save_rgb(OUT + 'walnut_c.jpg', np.clip(rgb, 0, 1) ** (1 / 2.2) if False else rgb)
save_rgb(OUT + 'walnut_n.jpg', normal_from_height(hn, 2.5))
print('walnut mean', np.round(rgb.mean((0, 1)), 3))
# preview montage: metals tiled 2x2 plus the wood strip
t = [np.tile(to_srgb(f()[0])[::4, ::4], (2, 2, 1)) for f in (lambda: blued(1024), lambda: parker(1024), lambda: steel(1024))]
top = np.concatenate(t, 1)
wd = np.repeat(np.repeat(rgb[::4, ::4], 1, 0), 1, 1); wd = np.pad(wd, ((0, 0), (0, max(0, top.shape[1] - wd.shape[1])), (0, 0)))[:, :top.shape[1]]
save_rgb(D + '/gun_tiles_preview.jpg', np.concatenate([top, wd], 0)[::-1])
print('DONE')
