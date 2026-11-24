import bpy, sys, os, time, math, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/veg4/'
os.makedirs(OUT, exist_ok=True)
def save(name, arr, srgb=True, jpg=None):
    jpg = (arr.shape[2] == 3) if jpg is None else jpg
    h, w = arr.shape[:2]
    if arr.shape[2] == 3: arr = np.concatenate([arr, np.ones((h, w, 1))], 2)
    img = bpy.data.images.new(name, w, h, alpha=True); img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    px = arr.copy()
    if srgb: px[..., :3] = to_srgb(px[..., :3])
    img.pixels.foreach_set(px.astype(np.float32).ravel()); img.filepath_raw = OUT + name + ('.jpg' if jpg else '.png'); img.file_format = 'JPEG' if jpg else 'PNG'
    img.save(); bpy.data.images.remove(img)

def bark_pine(n=1024, seed=41):
    _, h = bark(n, seed, 'dead')
    tone = fbm(n, seed + 3, 2, 6, 3)
    col = ramp(h, [(0, (0.03, 0.02, 0.016)), (0.35, (0.12, 0.062, 0.036)), (0.7, (0.24, 0.115, 0.06)), (1, (0.36, 0.19, 0.095))])
    grey = ramp(h, [(0, (0.03, 0.026, 0.022)), (0.5, (0.12, 0.09, 0.07)), (1, (0.26, 0.20, 0.15))])
    m = smooth(tone, 0.3, 0.6)[..., None]
    col = col * (1 - 0.6 * m) + grey * 0.6 * m
    lich = smooth(fbm(n, seed + 8, 12, 8, 3), 0.7, 0.78) * smooth(h, 0.5, 0.9)
    col = col * (1 - 0.35 * lich[..., None]) + np.array([0.30, 0.34, 0.20]) * 0.35 * lich[..., None]
    return col * (0.8 + 0.4 * fbm(n, seed + 5, 2, 4, 3))[..., None], h

def bark_oak(n=1024, seed=51):
    _, h = bark(n, seed, 'dead')
    col = ramp(h, [(0, (0.016, 0.014, 0.012)), (0.3, (0.052, 0.046, 0.04)), (0.65, (0.115, 0.10, 0.085)), (1, (0.21, 0.19, 0.165))])
    moss = smooth(fbm(n, seed + 6, 4, 3, 4), 0.55, 0.72) * smooth(h, 0.3, 0.8)
    col = col * (1 - 0.5 * moss[..., None]) + np.array([0.10, 0.17, 0.06]) * (0.5 * moss[..., None])
    return col * (0.8 + 0.4 * fbm(n, seed + 5, 2, 3, 3))[..., None], h

def bark_birch(n=1024, seed=61):
    rng = np.random.default_rng(seed)
    base = 0.55 + 0.25 * fbm(n, seed, 3, 14, 4)
    streak = fbm(n, seed + 1, 2, 60, 3)
    col = np.stack([base * 0.92, base * 0.90, base * 0.84], -1) * (0.85 + 0.3 * streak[..., None])
    col = np.clip(col, 0, 1) * 0.62
    h = 0.5 + 0.2 * streak
    for _ in range(95):
        y = rng.integers(0, n); x = rng.integers(0, n); w = rng.integers(18, 110); t = rng.integers(2, 6)
        xs = (np.arange(x, x + w) % n); ys = np.clip(y + np.round(np.sin(np.linspace(0, 3.1, w)) * 1.5).astype(int), 0, n - t - 1)
        fall = np.sin(np.linspace(0, math.pi, w)) ** 0.5
        for k in range(t):
            r = (ys + k) % n
            col[r, xs] = col[r, xs] * (1 - 0.9 * fall[:, None]) + np.array([0.012, 0.011, 0.01]) * 0.9 * fall[:, None]
            h[r, xs] -= 0.25 * fall
    peel = smooth(fbm(n, seed + 4, 3, 22, 3), 0.7, 0.8)
    col = col * (1 - 0.25 * peel[..., None]) + np.array([0.13, 0.10, 0.07]) * 0.25 * peel[..., None]
    mm = smooth(fbm(n, seed + 9, 5, 4, 3), 0.65, 0.8)[..., None]
    col = col * (1 - 0.2 * mm) + np.array([0.12, 0.2, 0.08]) * 0.2 * mm
    return col, np.clip(h, 0, 1)

def conifer_card(w=1024, h=512, seed=2, snow=0.0, pine=False):
    rng = np.random.default_rng(seed); card = new_card(w, h); cy = h * 0.5
    if pine:
        dk = np.array([0.05, 0.095, 0.05]); md = np.array([0.10, 0.18, 0.085]); lt = np.array([0.21, 0.30, 0.13]); brown = np.array([0.20, 0.10, 0.055])
    else:
        dk = np.array([0.018, 0.05, 0.03]); md = np.array([0.035, 0.105, 0.05]); lt = np.array([0.09, 0.19, 0.08]); brown = np.array([0.16, 0.085, 0.05])
    def needles(p0, p1, length, step):
        d = np.array(p1) - np.array(p0); L = np.hypot(*d); u = d / (L + 1e-9); nrm = np.array([-u[1], u[0]]); k = 0.0
        while k < L:
            base = np.array(p0) + u * k
            for sgn in (-1, 1):
                ang = math.radians(rng.uniform(35, 70)); ln = length * rng.uniform(0.7, 1.2) * (0.6 + 0.4 * (1 - k / (L + 1)))
                dirn = u * math.cos(ang) + nrm * sgn * math.sin(ang) * rng.uniform(0.8, 1.2)
                c = md * rng.uniform(0.7, 1.3) if rng.random() > 0.2 else dk
                seg(card, tuple(base), tuple(base + dirn * ln), 1.5, 0.35, c, lt * rng.uniform(0.6, 1.1), 0.95)
            k += step
    def tuft(p, ang, ln):
        for _ in range(46):
            a = ang + rng.uniform(-0.75, 0.75); l2 = ln * rng.uniform(0.6, 1.1); d = np.array([math.cos(a), math.sin(a)])
            c = md * rng.uniform(0.75, 1.3) if rng.random() > 0.2 else dk
            seg(card, tuple(p), tuple(np.array(p) + d * l2), 1.5, 0.35, c, lt * rng.uniform(0.7, 1.1), 0.95)
    pts = [(10 + i * (w - 40) / 20, cy + math.sin(i * 0.3) * 6 - i * 0.6) for i in range(21)]
    for i in range(20): seg(card, pts[i], pts[i + 1], 4.2 * (1 - i / 22) + 1.2, 4.2 * (1 - (i + 1) / 22) + 1.2, brown, brown * 1.2)
    for i in range(1, 20):
        for sgn in (-1, 1):
            if rng.random() < (0.95 if pine else 0.85):
                L = (h * 0.45) * (1 - i / 24) * rng.uniform(0.7, 1.0); a0 = math.radians(rng.uniform(42, 66))
                p0 = np.array(pts[i]); dd = np.array([math.cos(a0), sgn * math.sin(a0)]); p1 = p0 + dd * L
                seg(card, tuple(p0), tuple(p1), 1.9, 0.7, brown, brown * 1.1)
                if pine:
                    tuft(p1, math.atan2(dd[1], dd[0]), 52 * (1 - i / 40))
                    for j in range(2): tuft(p0 + (p1 - p0) * (0.4 + 0.3 * j), math.atan2(dd[1], dd[0]), 42 * (1 - i / 40))
                else:
                    needles(tuple(p0), tuple(p1), 27 * (1 - i / 40), 4.5)
                    for j in range(2):
                        f = rng.uniform(0.3, 0.8); q0 = p0 + (p1 - p0) * f; q1 = q0 + np.array([dd[0] * 0.6, dd[1] * 0.9]) * L * 0.35
                        seg(card, tuple(q0), tuple(q1), 1.0, 0.5, brown, brown); needles(tuple(q0), tuple(q1), 17, 4.5)
    if pine: tuft(pts[-1], 0.0, 80)
    else: needles(pts[0], pts[-1], 25, 4.0)
    if snow > 0:
        top = card[..., 3] > 0.3; hh = np.cumsum(top[::-1], 0)[::-1] <= 4
        m = top & hh & (np.random.default_rng(seed).random(top.shape) < snow)
        card[..., :3][m] = card[..., :3][m] * 0.2 + np.array([0.82, 0.86, 0.9]) * 0.8
    return bleed(card)

def broadleaf_card(w=1024, h=512, seed=6, greens=None, size=(55, 85), width=(15, 24), nside=4):
    rng = np.random.default_rng(seed); card = new_card(w, h); cy = h * 0.5; wood = np.array([0.12, 0.085, 0.05])
    pts = [(10 + i * (w - 60) / 16, cy + math.sin(i * 0.35) * 8 - i * 0.8) for i in range(17)]
    for i in range(16): seg(card, pts[i], pts[i + 1], 3.6 * (1 - i / 18) + 1.0, 3.6 * (1 - (i + 1) / 18) + 1.0, wood, wood * 1.2)
    def side(p0, sgn, L):
        a = math.radians(sgn * rng.uniform(40, 70)); q = np.array(p0) + np.array([math.cos(a), math.sin(a)]) * L
        seg(card, tuple(p0), tuple(q), 1.6, 0.8, wood, wood)
        for k in range(nside):
            f = rng.uniform(0.2, 1.0); b = np.array(p0) + (q - np.array(p0)) * f
            g = greens[rng.integers(len(greens))]; la = a + sgn * math.radians(rng.uniform(15, 55)) * (1 if k % 2 else -1)
            leaf(card, b, la, rng.uniform(*size), rng.uniform(*width), g[0], g[1])
        g = greens[rng.integers(len(greens))]; leaf(card, q, a, size[1], width[1], g[0], g[1])
    for i in range(1, 16):
        for sgn in (-1, 1):
            if rng.random() < 0.8: side(pts[i], sgn, rng.uniform(70, 150) * (1 - i / 22))
    for k in range(5): g = greens[rng.integers(len(greens))]; leaf(card, pts[-1], rng.uniform(-0.5, 0.5), size[1], width[1], g[0], g[1])
    return bleed(card)

OAK_G = [((0.03, 0.075, 0.02), (0.11, 0.22, 0.045)), ((0.04, 0.09, 0.025), (0.15, 0.27, 0.06)), ((0.05, 0.10, 0.03), (0.19, 0.30, 0.07)), ((0.07, 0.11, 0.03), (0.24, 0.30, 0.08))]
BIRCH_G = [((0.07, 0.14, 0.03), (0.28, 0.42, 0.09)), ((0.09, 0.17, 0.04), (0.35, 0.48, 0.11)), ((0.11, 0.18, 0.04), (0.40, 0.48, 0.12)), ((0.15, 0.19, 0.05), (0.48, 0.46, 0.12))]

t0 = time.time()
for nm, fn, sd in (('pine', bark_pine, 41), ('oak', bark_oak, 51), ('birch', bark_birch, 61)):
    c, h = fn(1024, sd); save('bark_%s_c' % nm, c); save('bark_%s_n' % nm, normal_from_height(h, 4.0), False); print(nm, time.time() - t0)
save('spruce_v4', conifer_card(1024, 512, 12)); print('spruce', time.time() - t0)
save('spruce_snow_v4', conifer_card(1024, 512, 12, snow=0.55)); print('snow', time.time() - t0)
save('pine_v4', conifer_card(1024, 512, 14, pine=True)); print('pine', time.time() - t0)
save('oak_v4', broadleaf_card(1024, 512, 16, OAK_G, size=(38, 62), width=(13, 20), nside=6)); print('oak', time.time() - t0)
save('birch_v4', broadleaf_card(1024, 512, 18, BIRCH_G, size=(42, 62), width=(14, 20), nside=5)); print('birch', time.time() - t0)
print('DONE')
