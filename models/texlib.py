"""Procedural PBR texture generator (numpy only) for the Hailstorm Blender kit.
Every texture is tileable noise built from layered detail, saved as colour + normal map images.
Images are indexed bottom row first, like Blender (row 0 = bottom of the picture)."""
import numpy as np, math

def smooth(x, a, b):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1); return t * t * (3 - 2 * t)

def value_noise(h, w, cx, cy, rng):
    g = rng.random((cy, cx))
    ys = np.linspace(0, cy, h, endpoint=False); xs = np.linspace(0, cx, w, endpoint=False)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    fy = ys - y0; fx = xs - x0; fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    y1 = (y0 + 1) % cy; x1 = (x0 + 1) % cx
    a = g[np.ix_(y0, x0)]; b = g[np.ix_(y0, x1)]; c = g[np.ix_(y1, x0)]; d = g[np.ix_(y1, x1)]
    fxx = fx[None, :]; fyy = fy[:, None]
    return a * (1 - fxx) * (1 - fyy) + b * fxx * (1 - fyy) + c * (1 - fxx) * fyy + d * fxx * fyy

def fbm(n, seed, fx=4, fy=4, octaves=5, gain=0.5, lac=2.0, w=None):
    """tileable fractal noise scaled to 0..1. fx / fy = cycles across the picture at the first octave."""
    w = w or n; rng = np.random.default_rng(seed); out = np.zeros((n, w)); amp = 1.0
    for o in range(octaves):
        out += amp * value_noise(n, w, max(1, int(fx * lac ** o)), max(1, int(fy * lac ** o)), rng); amp *= gain
    out -= out.min(); return out / (out.max() + 1e-9)

def sample(img, X, Y):
    """bilinear lookup with wrap-around (X, Y are pixel coordinates)"""
    h, w = img.shape[:2]; X = X % w; Y = Y % h
    x0 = np.floor(X).astype(int); y0 = np.floor(Y).astype(int); fx = X - x0; fy = Y - y0
    x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    if img.ndim == 3: fx = fx[..., None]; fy = fy[..., None]
    return img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy

def warp(img, n, seed, amount=0.1, scale=3):
    X, Y = np.meshgrid(np.arange(img.shape[1], dtype=float), np.arange(img.shape[0], dtype=float))
    dx = (fbm(n, seed, scale, scale, 3) - 0.5) * n * amount; dy = (fbm(n, seed + 7, scale, scale, 3) - 0.5) * n * amount
    return sample(img, X + dx, Y + dy)

def ramp(t, stops):
    t = np.clip(t, 0, 1); pos = [s[0] for s in stops]
    return np.stack([np.interp(t, pos, [s[1][c] for s in stops]) for c in range(3)], -1)

def normal_from_height(h, strength=3.0):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5; gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx = -gx * strength * h.shape[1] / 64.0; ny = -gy * strength * h.shape[0] / 64.0; nz = np.ones_like(h)
    L = np.sqrt(nx * nx + ny * ny + nz * nz); return np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5

def to_srgb(c): return np.clip(c, 0, 1) ** (1 / 2.2)


def worley(n, seed, cx, cy, jitter=0.9):
    """tileable cellular noise; returns (F1, F2-F1, cell random id) in cell units. cx, cy = cells across / down."""
    rng = np.random.default_rng(seed)
    P = (rng.random((cy, cx, 2)) - 0.5) * jitter; ID = rng.random((cy, cx))
    ys = (np.arange(n) + 0.5) / n * cy; xs = (np.arange(n) + 0.5) / n * cx
    X, Y = np.meshgrid(xs, ys); ix = np.floor(X).astype(int); iy = np.floor(Y).astype(int)
    f1 = np.full(X.shape, 9.0); f2 = np.full(X.shape, 9.0); idv = np.zeros(X.shape)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            jx = (ix + dx) % cx; jy = (iy + dy) % cy
            px = ix + dx + 0.5 + P[jy, jx, 0]; py = iy + dy + 0.5 + P[jy, jx, 1]
            d = np.hypot(X - px, (Y - py) * (cx / cy) * 0.0 + (Y - py) * 1.0)
            new1 = d < f1; f2 = np.where(new1, f1, np.minimum(f2, d)); idv = np.where(new1, ID[jy, jx], idv); f1 = np.minimum(f1, d)
    return f1, f2 - f1, idv

def bark_height(n, seed, cols=18, rows=5, stretch=1.0):
    """tall bark plates. cells are tall because rows << cols; fissures where F2-F1 is small"""
    X, Y = np.meshgrid(np.arange(n, dtype=float), np.arange(n, dtype=float))
    dx = (fbm(n, seed + 40, 6, 3, 3) - 0.5) * n * 0.035; dy = (fbm(n, seed + 41, 3, 6, 3) - 0.5) * n * 0.05
    f1, edge, pid = worley_aniso(n, seed, cols, rows)
    return f1, edge, pid

def worley_aniso(n, seed, cx, cy):
    rng = np.random.default_rng(seed); P = (rng.random((cy, cx, 2)) - 0.5) * 0.85; ID = rng.random((cy, cx))
    ys = (np.arange(n) + 0.5) / n * cy; xs = (np.arange(n) + 0.5) / n * cx
    # wobble the lookup positions so edges are not straight
    X, Y = np.meshgrid(xs, ys)
    X = X + (fbm(n, seed + 50, 5, 5, 3) - 0.5) * 0.3; Y = Y + (fbm(n, seed + 51, 5, 5, 3) - 0.5) * 0.3
    ix = np.floor(X).astype(int); iy = np.floor(Y).astype(int); asp = cx / cy     # asp>1: cell is tall, so shrink vertical distance
    f1 = np.full(X.shape, 99.0); f2 = np.full(X.shape, 99.0); idv = np.zeros(X.shape)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            jx = (ix + dx) % cx; jy = (iy + dy) % cy
            px = ix + dx + 0.5 + P[jy, jx, 0]; py = iy + dy + 0.5 + P[jy, jx, 1]
            d = np.hypot(X - px, (Y - py) / asp * 1.0 * 2.2)
            new1 = d < f1; f2 = np.where(new1, f1, np.minimum(f2, d)); idv = np.where(new1, ID[jy, jx], idv); f1 = np.minimum(f1, d)
    return f1, f2 - f1, idv

# ------------------------------------------------------------------------------------------------ BARK
def bark(n=1024, seed=1, kind='dead'):
    """returns (colour rgb, height 0..1). kind: dead (weathered grey-brown, lichen), charred (black plates, ash), spruce (reddish scales)"""
    if kind == 'spruce':
        base = fbm(n, seed, 10, 7, 4, 0.55); base = warp(base, n, seed + 1, 0.10, 4)
        plates = 1 - np.abs(base * 2 - 1); h = smooth(plates, 0.15, 0.9) ** 1.3
        h = 0.8 * h + 0.2 * fbm(n, seed + 2, 40, 28, 3)
    else:
        f1, edge, pid = worley_aniso(n, seed, 15, 3)
        plate = smooth(edge, 0.02, 0.30)                                       # fissure between plates
        streak = fbm(n, seed + 2, 140, 5, 3, 0.6)                              # fine vertical fibres
        strand = fbm(n, seed + 7, 60, 2, 2, 0.5)
        h = plate * (0.55 + 0.25 * streak + 0.12 * strand + 0.2 * pid) + 0.0
        h = h * (0.85 + 0.15 * smooth(f1, 0.0, 0.8))
        if kind == 'charred':
            cr2 = fbm(n, seed + 4, 5, 12, 3); crack2 = 1 - np.clip(np.abs(cr2 - 0.5) / 0.03, 0, 1)
            h = h * (1 - 0.8 * crack2)
    h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    tone = fbm(n, seed + 5, 2, 3, 3); low = 0.8 + 0.4 * tone
    if kind == 'dead':
        col = ramp(h, [(0, (0.028, 0.022, 0.018)), (0.3, (0.085, 0.07, 0.056)), (0.65, (0.15, 0.13, 0.108)), (1, (0.25, 0.23, 0.20))])
        moss = smooth(fbm(n, seed + 6, 5, 3, 4), 0.58, 0.72) * smooth(h, 0.45, 0.8)
        col = col * (1 - 0.45 * moss[..., None]) + np.array([0.20, 0.23, 0.14]) * (0.45 * moss[..., None])
        lich = smooth(fbm(n, seed + 8, 14, 9, 3), 0.7, 0.78) * smooth(h, 0.5, 0.9)
        col = col * (1 - 0.6 * lich[..., None]) + np.array([0.46, 0.47, 0.40]) * (0.6 * lich[..., None])
    elif kind == 'charred':
        col = ramp(h, [(0, (0.006, 0.006, 0.006)), (0.4, (0.028, 0.026, 0.024)), (0.75, (0.075, 0.07, 0.065)), (1, (0.19, 0.18, 0.17))])
        ash = smooth(fbm(n, seed + 6, 6, 4, 4), 0.55, 0.75) * smooth(h, 0.55, 0.95)
        col = col * (1 - 0.7 * ash[..., None]) + np.array([0.30, 0.29, 0.28]) * (0.7 * ash[..., None])
        ember = smooth(fbm(n, seed + 9, 9, 7, 3), 0.8, 0.86) * (1 - smooth(h, 0.1, 0.35))
        col = col + np.array([0.05, 0.012, 0.0]) * ember[..., None]
    else:
        col = ramp(h, [(0, (0.028, 0.017, 0.012)), (0.35, (0.10, 0.052, 0.034)), (0.7, (0.22, 0.12, 0.075)), (1, (0.33, 0.20, 0.13))])
        lich = smooth(fbm(n, seed + 8, 10, 6, 3), 0.66, 0.78) * smooth(h, 0.5, 0.9)
        col = col * (1 - 0.4 * lich[..., None]) + np.array([0.30, 0.34, 0.22]) * (0.4 * lich[..., None])
    return col * low[..., None], h

# ------------------------------------------------------------------------------------------------ CUT WOOD (end grain)
def wood_end(n=1024, seed=3, rings=30, bark_edge=True, charred=False):
    Y, X = np.mgrid[0:n, 0:n].astype(float); cx = n / 2 + (np.random.default_rng(seed).random() - 0.5) * n * 0.05; cy = n / 2
    r = np.hypot((X - cx), (Y - cy)) / (n / 2)
    wob = (fbm(n, seed, 3, 3, 3) - 0.5) * 0.18 + (fbm(n, seed + 1, 12, 12, 3) - 0.5) * 0.03
    rr = np.clip(r + wob, 0, 2)
    phase = rr ** 0.92 * rings; ring = phase - np.floor(phase)
    late = smooth(ring, 0.55, 0.92) * (1 - smooth(ring, 0.94, 1.0))           # dark late wood band, sharp edge at the ring boundary
    pith = np.exp(-(rr / 0.05) ** 2)
    base = np.array([0.60, 0.46, 0.30]); dark = np.array([0.36, 0.23, 0.12])
    col = base * (1 - late[..., None]) + dark * late[..., None]
    col = col * (0.88 + 0.24 * fbm(n, seed + 2, 40, 40, 3)[..., None])
    col = col * (1 - 0.35 * pith[..., None])
    ang = np.arctan2(Y - cy, X - cx)                                           # radial drying cracks
    cn = fbm(n, seed + 4, 18, 1, 2, w=n); crk = np.zeros((n, n))
    for k in range(5):
        a0 = (np.random.default_rng(seed + 10 + k).random()) * 2 * math.pi; d = np.abs(((ang - a0 + math.pi) % (2 * math.pi)) - math.pi)
        crk = np.maximum(crk, (1 - smooth(d, 0.0, 0.035 * (0.4 + r))) * smooth(r, 0.05, 0.3) * (1 - smooth(r, 0.75, 0.95)))
    col = col * (1 - 0.8 * crk[..., None])
    weather = smooth(fbm(n, seed + 5, 5, 5, 4), 0.45, 0.8) * 0.55                # grey weathered surface
    col = col * (1 - weather[..., None]) + np.array([0.34, 0.32, 0.29]) * weather[..., None]
    if charred:
        ch = smooth(rr, 0.35, 0.9); col = col * (1 - ch[..., None] * 0.9) + np.array([0.02, 0.02, 0.02]) * ch[..., None] * 0.9
    if bark_edge:
        bk, bh = bark(512, seed + 20, 'dead'); bk = np.array(bk) * 0.55
        bi = np.clip(((np.arctan2(Y - cy, X - cx) / (2 * math.pi) + 0.5) * 511).astype(int), 0, 511); bj = np.clip((((r - 0.93) / 0.2) * 511).astype(int), 0, 511)
        bark_col = bk[bj, bi]; m = smooth(r, 0.925, 0.945)
        col = col * (1 - m[..., None]) + bark_col * m[..., None]
    h = 0.5 + 0.2 * late - 0.4 * crk + 0.1 * fbm(n, seed + 6, 30, 30, 3)
    return col, np.clip(h, 0, 1)

def wood_fibre(n=512, seed=5):
    """splintered, freshly broken wood: long pale fibres"""
    f = fbm(n, seed, 70, 3, 4, 0.55); f = warp(f, n, seed + 1, 0.08, 3)
    s = fbm(n, seed + 2, 12, 1.2, 3)
    h = 0.6 * f + 0.4 * s
    col = ramp(h, [(0, (0.30, 0.19, 0.10)), (0.5, (0.58, 0.44, 0.27)), (1, (0.80, 0.68, 0.48))])
    dirt = smooth(fbm(n, seed + 3, 6, 6, 4), 0.55, 0.8) * 0.5
    col = col * (1 - dirt[..., None]) + np.array([0.28, 0.25, 0.21]) * dirt[..., None]
    return col, h

# ------------------------------------------------------------------------------------------------ 2D painting (cards with alpha)
def new_card(w, h): return np.zeros((h, w, 4))

def seg(card, p0, p1, w0, w1, c0, c1, a=1.0):
    """anti-aliased tapered line segment composited over the card (pixel coords, row 0 at the bottom)"""
    h, w = card.shape[:2]; r = max(w0, w1) + 2
    x0 = int(max(0, min(p0[0], p1[0]) - r)); x1 = int(min(w, max(p0[0], p1[0]) + r + 1))
    y0 = int(max(0, min(p0[1], p1[1]) - r)); y1 = int(min(h, max(p0[1], p1[1]) + r + 1))
    if x1 <= x0 or y1 <= y0: return
    Y, X = np.mgrid[y0:y1, x0:x1].astype(float); d = np.array(p1) - np.array(p0); L2 = d @ d + 1e-9
    t = np.clip(((X - p0[0]) * d[0] + (Y - p0[1]) * d[1]) / L2, 0, 1)
    px = p0[0] + d[0] * t; py = p0[1] + d[1] * t; dist = np.hypot(X - px, Y - py)
    wd = w0 + (w1 - w0) * t; al = np.clip(wd - dist + 0.5, 0, 1) * a
    col = np.array(c0)[None, None, :] * (1 - t[..., None]) + np.array(c1)[None, None, :] * t[..., None]
    sub = card[y0:y1, x0:x1]; A = sub[..., 3:4]; al = al[..., None]
    out_a = al + A * (1 - al)
    sub[..., :3] = np.where(out_a > 1e-6, (col * al + sub[..., :3] * A * (1 - al)) / np.maximum(out_a, 1e-6), 0); sub[..., 3:4] = out_a

def bleed(card):
    """fill the colour of fully transparent pixels with the nearby average so mip-maps do not get dark fringes"""
    a = card[..., 3]; rgb = card[..., :3].copy(); m = a > 0.05
    avg = (rgb * m[..., None]).sum((0, 1)) / max(m.sum(), 1)
    for it in range(6):
        bl = (np.roll(rgb, 1, 0) + np.roll(rgb, -1, 0) + np.roll(rgb, 1, 1) + np.roll(rgb, -1, 1)) / 4
        rgb = np.where(m[..., None], rgb, bl * 0.9 + avg * 0.1 if it else avg)
    card[..., :3] = np.where(m[..., None], card[..., :3], rgb); return card

def blade(card, rng, x0, H, lean, w0, cols, rib=True, segs=14, curl=0.6):
    pts = []
    for i in range(segs + 1):
        t = i / segs; pts.append((x0 + lean * H * t ** 1.8 + curl * H * 0.1 * math.sin(t * 3 + x0), H * t))
    base, tip = cols
    for i in range(segs):
        t0 = i / segs; t1 = (i + 1) / segs
        wa = w0 * (1 - t0) ** 0.6 + 0.35; wb = w0 * (1 - t1) ** 0.6 + 0.35
        shade = 0.85 + 0.3 * rng.random() * 0
        seg(card, pts[i], pts[i + 1], wa, wb, np.array(base) * (1 - t0) + np.array(tip) * t0, np.array(base) * (1 - t1) + np.array(tip) * t1)
        if rib and wa > 2.2: seg(card, pts[i], pts[i + 1], wa * 0.22, wb * 0.22, np.array(base) * 0.55, np.array(base) * 0.55, 0.55)
    return pts

def grass_card(w=1024, h=1024, seed=1, count=70, hmin=0.45, hmax=0.95, spread=0.33, width=7.0, pal=None):
    rng = np.random.default_rng(seed); card = new_card(w, h)
    pal = pal or [((0.30, 0.22, 0.10), (0.62, 0.52, 0.30)), ((0.26, 0.19, 0.09), (0.52, 0.42, 0.24)), ((0.36, 0.30, 0.13), (0.70, 0.62, 0.38)), ((0.22, 0.24, 0.10), (0.46, 0.46, 0.22)), ((0.20, 0.14, 0.07), (0.40, 0.30, 0.17))]
    order = rng.permutation(count)
    for i in order:
        cx = w * (0.5 + (rng.random() - 0.5) * spread * 2); lean = (cx / w - 0.5) * 0.9 + (rng.random() - 0.5) * 0.35
        H = h * rng.uniform(hmin, hmax); wd = width * rng.uniform(0.7, 1.3)
        blade(card, rng, cx, H, lean, wd, pal[rng.integers(len(pal))])
    # a few seed stalks (thin, tall, with a dry head)
    for i in range(max(2, count // 14)):
        cx = w * (0.5 + (rng.random() - 0.5) * spread * 1.4); H = h * rng.uniform(0.7, 0.97); lean = (cx / w - 0.5) * 0.6
        pts = blade(card, rng, cx, H, lean, 2.2, ((0.30, 0.22, 0.12), (0.5, 0.4, 0.22)), False, 14, 0.2)
        tip = pts[-1]
        for k in range(14):
            a0 = (tip[0] - lean * 20 * (k / 14), tip[1] - 90 * (k / 14)); seg(card, a0, (a0[0], a0[1] - 14), 3.2 * (1 - abs(k - 7) / 9), 2.5, (0.34, 0.27, 0.15), (0.45, 0.37, 0.2))
    return bleed(card)

def reed_card(w=512, h=1536, seed=4):
    rng = np.random.default_rng(seed); card = new_card(w, h); tint = [((0.30, 0.25, 0.12), (0.62, 0.52, 0.28)), ((0.24, 0.20, 0.10), (0.50, 0.42, 0.22)), ((0.33, 0.30, 0.14), (0.58, 0.54, 0.30))]
    for i in range(16):                                                                         # long ribbon leaves
        cx = w * (0.5 + (rng.random() - 0.5) * 0.4); blade(card, rng, cx, h * rng.uniform(0.5, 0.88), (rng.random() - 0.5) * 0.9, 9.0, tint[rng.integers(3)], True, 16, 1.0)
    for i in range(9):                                                                          # stalks with cattail heads
        cx = w * (0.5 + (rng.random() - 0.5) * 0.34); H = h * rng.uniform(0.62, 0.95); lean = (cx / w - 0.5) * 0.45
        pts = blade(card, rng, cx, H, lean, 3.4, ((0.30, 0.26, 0.12), (0.52, 0.46, 0.24)), False, 16, 0.3)
        if i < 6:
            tp = pts[-4]; tq = pts[-1]
            for k in range(26):
                f = k / 25; x = tp[0] + (tq[0] - tp[0]) * f * 0.9; y = tp[1] + (tq[1] - tp[1]) * f * 0.9
                seg(card, (x, y), (x + (tq[0] - tp[0]) * 0.04, y + (tq[1] - tp[1]) * 0.04), 7.0 * math.sin(math.pi * min(1, f * 0.95 + 0.04)) + 1.5, 6.0, (0.14, 0.085, 0.05), (0.2, 0.12, 0.07))
            seg(card, pts[-1], (pts[-1][0] + lean * 20, pts[-1][1] + 70), 1.8, 0.5, (0.4, 0.32, 0.18), (0.5, 0.42, 0.24))
    return bleed(card)

def spruce_card(w=1024, h=512, seed=2, snow=0.0):
    """one horizontal spruce branch (trunk end on the left): twig, side twigs and hundreds of needles"""
    rng = np.random.default_rng(seed); card = new_card(w, h); cy = h * 0.5
    dk = np.array([0.035, 0.10, 0.06]); md = np.array([0.07, 0.19, 0.09]); lt = np.array([0.16, 0.30, 0.14]); brown = np.array([0.20, 0.12, 0.07])
    def needles(p0, p1, length, step=5.0):
        d = np.array(p1) - np.array(p0); L = np.hypot(*d); u = d / (L + 1e-9); nrm = np.array([-u[1], u[0]]); k = 0
        while k < L:
            base = np.array(p0) + u * k; for_side = (-1, 1)
            for sgn in for_side:
                ang = math.radians(rng.uniform(40, 75)); ln = length * rng.uniform(0.7, 1.15) * (0.55 + 0.45 * (1 - k / (L + 1)))
                dirn = u * math.cos(ang) + nrm * sgn * math.sin(ang) * rng.uniform(0.8, 1.2)
                c = md * rng.uniform(0.7, 1.25) if rng.random() > 0.15 else dk
                seg(card, tuple(base), tuple(base + dirn * ln), 1.4, 0.4, c, lt * rng.uniform(0.6, 1.1), 0.95)
            k += step
    # main twig
    pts = [(10 + i * (w - 40) / 20, cy + math.sin(i * 0.3) * 6 - i * 0.6) for i in range(21)]
    for i in range(20): seg(card, pts[i], pts[i + 1], 4.0 * (1 - i / 22) + 1.2, 4.0 * (1 - (i + 1) / 22) + 1.2, brown, brown * 1.2)
    for i in range(1, 20):                                                                         # side twigs both sides
        for sgn in (-1, 1):
            if rng.random() < 0.82:
                L = (h * 0.46) * (1 - i / 24) * rng.uniform(0.7, 1.0); a0 = math.radians(rng.uniform(45, 65))
                p0 = np.array(pts[i]); dd = np.array([math.cos(a0), sgn * math.sin(a0)]); p1 = p0 + dd * L
                seg(card, tuple(p0), tuple(p1), 1.8, 0.7, brown, brown * 1.1); needles(tuple(p0), tuple(p1), 26 * (1 - i / 40))
                for j in range(2):                                                                  # tiny sub twigs
                    f = rng.uniform(0.3, 0.8); q0 = p0 + (p1 - p0) * f; q1 = q0 + np.array([dd[0] * 0.6, dd[1] * 0.9]) * L * 0.35
                    seg(card, tuple(q0), tuple(q1), 1.0, 0.5, brown, brown); needles(tuple(q0), tuple(q1), 17)
    needles(pts[0], pts[-1], 24, 4.0)
    if snow > 0:                                                                                     # light dusting on the upper side of needles
        top = card[..., 3] > 0.3; hh = np.cumsum(top[::-1], 0)[::-1] <= 3
        m = top & hh & (np.random.default_rng(seed).random(top.shape) < snow)
        card[..., :3][m] = card[..., :3][m] * 0.2 + np.array([0.85, 0.88, 0.9]) * 0.8
    return bleed(card)

GREEN_PAL = [((0.05, 0.11, 0.03), (0.24, 0.40, 0.10)), ((0.07, 0.14, 0.04), (0.30, 0.46, 0.13)), ((0.04, 0.09, 0.03), (0.20, 0.34, 0.09)),
             ((0.09, 0.17, 0.05), (0.38, 0.50, 0.17)), ((0.12, 0.17, 0.05), (0.44, 0.50, 0.20)), ((0.22, 0.18, 0.07), (0.46, 0.40, 0.18))]

def leaf(card, base, ang, L, W, c0, c1, rib=True):
    """one pointed leaf: widens then narrows, with a lighter mid-rib"""
    d = np.array([math.cos(ang), math.sin(ang)]); p = np.array(base); n = 7
    for i in range(n):
        t0 = i / n; t1 = (i + 1) / n
        w0 = W * math.sin(math.pi * min(1, t0 * 0.95 + 0.02)) ** 0.8 + 0.4; w1 = W * math.sin(math.pi * min(1, t1 * 0.95 + 0.02)) ** 0.8 + 0.4
        seg(card, tuple(p + d * L * t0), tuple(p + d * L * t1), w0, w1, np.array(c0) * (1 - t0) + np.array(c1) * t0, np.array(c0) * (1 - t1) + np.array(c1) * t1)
    if rib: seg(card, tuple(p), tuple(p + d * L * 0.95), 0.9, 0.4, np.array(c1) * 1.25, np.array(c1) * 1.15, 0.8)

def leafy_card(w=1024, h=512, seed=6):
    """a leafy twig lying along the card (stem on the left), alternate leaves with varied colour"""
    rng = np.random.default_rng(seed); card = new_card(w, h); cy = h * 0.5; wood = np.array([0.15, 0.10, 0.06])
    pts = [(10 + i * (w - 60) / 16, cy + math.sin(i * 0.35) * 8 - i * 0.8) for i in range(17)]
    for i in range(16): seg(card, pts[i], pts[i + 1], 3.6 * (1 - i / 18) + 1.0, 3.6 * (1 - (i + 1) / 18) + 1.0, wood, wood * 1.2)
    greens = [((0.05, 0.14, 0.04), (0.20, 0.38, 0.08)), ((0.07, 0.17, 0.05), (0.26, 0.44, 0.11)), ((0.10, 0.18, 0.05), (0.34, 0.46, 0.13)), ((0.14, 0.18, 0.05), (0.42, 0.44, 0.12))]
    def side(p0, sgn, L, depth):
        a = math.radians(sgn * rng.uniform(40, 70)); q = np.array(p0) + np.array([math.cos(a), math.sin(a)]) * L
        seg(card, tuple(p0), tuple(q), 1.6, 0.8, wood, wood)
        for k in range(4):
            f = rng.uniform(0.2, 1.0); b = np.array(p0) + (q - np.array(p0)) * f
            g = greens[rng.integers(len(greens))]; la = a + sgn * math.radians(rng.uniform(15, 55)) * (1 if k % 2 else -1)
            leaf(card, b, la, rng.uniform(55, 85) * (1 - 0.3 * depth), rng.uniform(15, 24), g[0], g[1])
        g = greens[rng.integers(len(greens))]; leaf(card, q, a, 80, 20, g[0], g[1])
    for i in range(1, 16):
        for sgn in (-1, 1):
            if rng.random() < 0.8: side(pts[i], sgn, rng.uniform(70, 150) * (1 - i / 22), 0)
    for k in range(5): g = greens[rng.integers(len(greens))]; leaf(card, pts[-1], rng.uniform(-0.5, 0.5), 90, 22, g[0], g[1])
    return bleed(card)

def fern_card(w=1024, h=1024, seed=3):
    """arching fern fronds from the bottom centre: curved rachis, dense short pinnae that shorten toward the tip and curl down"""
    rng = np.random.default_rng(seed); card = new_card(w, h)
    cols = [((0.05, 0.13, 0.04), (0.20, 0.38, 0.09)), ((0.07, 0.16, 0.05), (0.26, 0.44, 0.12)), ((0.09, 0.15, 0.04), (0.32, 0.42, 0.11))]
    for f in range(8):
        a0 = math.pi / 2 + (f - 3.5) * 0.30 + rng.uniform(-0.08, 0.08); L = h * rng.uniform(0.62, 0.9); c = cols[rng.integers(3)]; side = 1 if f >= 4 else -1
        N = 44; ang = a0; p = np.array([w * 0.5 + (f - 3.5) * 7, 4.0]); pts = [p.copy()]
        for i in range(N):
            ang += side * 0.021 * (0.4 + i / N * 1.6); p = p + np.array([math.cos(ang), math.sin(ang)]) * L / N; pts.append(p.copy())
        for i in range(N): seg(card, pts[i], pts[i + 1], 2.4 * (1 - i / (N + 2)) + 0.7, 2.4 * (1 - (i + 1) / (N + 2)) + 0.7, (0.12, 0.2, 0.07), (0.2, 0.3, 0.1))
        for i in range(3, N):
            t = i / N; pl = L * 0.13 * math.sin(math.pi * min(1, t * 0.96 + 0.05)) ** 0.75 + 4
            d = pts[i + 1] - pts[i]; d = d / (np.hypot(*d) + 1e-9); nrm = np.array([-d[1], d[0]])
            for sg in (-1, 1):
                mid = pts[i] + (nrm * sg * 0.88 + d * 0.5) * pl * 0.6; tip = mid + (nrm * sg * 0.45 + d * 0.25 - np.array([0, 0.45])) * pl * 0.5
                cc0 = np.array(c[0]) * rng.uniform(0.85, 1.2); cc1 = np.array(c[1]) * rng.uniform(0.85, 1.15)
                seg(card, tuple(pts[i]), tuple(mid), 3.2, 3.0, cc0, cc1); seg(card, tuple(mid), tuple(tip), 3.0, 0.5, cc1, cc1 * 0.9)
    return bleed(card)

def meadow_card(w=1024, h=1024, seed=5):
    """short green grass with wildflowers (white daisies, yellow buttercups, purple vetch) on thin stems"""
    rng = np.random.default_rng(seed); card = grass_card(w, h, seed, 64, 0.30, 0.62, 0.38, 6.0, GREEN_PAL[:5])
    flowers = [((0.93, 0.92, 0.86), (0.95, 0.78, 0.15)), ((0.95, 0.80, 0.12), (0.85, 0.55, 0.05)), ((0.50, 0.30, 0.62), (0.80, 0.78, 0.40))]
    for i in range(14):
        cx = w * (0.5 + (rng.random() - 0.5) * 0.7); H = h * rng.uniform(0.45, 0.8); lean = (cx / w - 0.5) * 0.5
        top = (cx + lean * H, H); seg(card, (cx, 0), top, 2.2, 1.6, (0.09, 0.17, 0.05), (0.2, 0.32, 0.10))
        pc, cc = flowers[i % 3]; R = rng.uniform(15, 24)
        if i % 3 == 2:
            for k in range(5): seg(card, (top[0], top[1] - 12 + k * 6), (top[0] + rng.uniform(-6, 6), top[1] - 6 + k * 6), 5.5, 4.0, pc, pc)
        else:
            for k in range(9):
                a = 2 * math.pi * k / 9; seg(card, top, (top[0] + math.cos(a) * R, top[1] + math.sin(a) * R * 0.8), 5.0, 2.5, pc, np.array(pc) * 0.9)
            seg(card, top, (top[0] + 0.1, top[1] + 0.1), 6.0, 6.0, cc, cc)
    return bleed(card)

# ------------------------------------------------------------------------------------------------ SEAMLESS GROUND TEXTURES
WRAP = [False]
_seg0 = seg
def seg(card, p0, p1, w0, w1, c0, c1, a=1.0):
    """tileable when WRAP[0] is set: a stroke that crosses an edge is also drawn on the opposite side"""
    if not WRAP[0]: return _seg0(card, p0, p1, w0, w1, c0, c1, a)
    h, w = card.shape[:2]; r = max(w0, w1) + 2
    xs = [0]; ys = [0]
    if min(p0[0], p1[0]) - r < 0: xs.append(w)
    if max(p0[0], p1[0]) + r > w: xs.append(-w)
    if min(p0[1], p1[1]) - r < 0: ys.append(h)
    if max(p0[1], p1[1]) + r > h: ys.append(-h)
    for dx in xs:
        for dy in ys: _seg0(card, (p0[0] + dx, p0[1] + dy), (p1[0] + dx, p1[1] + dy), w0, w1, c0, c1, a)

def blur(a, r=2):
    """box blur with wrap-around (keeps tiles seamless)"""
    out = a.astype(float)
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for k in range(-r, r + 1): acc += np.roll(out, k, ax)
        out = acc / (2 * r + 1)
    return out

def over(base, card):
    a = card[..., 3:4]; return base * (1 - a) + card[..., :3] * a

def scatter_strokes(card, rng, n, count, lmin, lmax, wmin, wmax, pal, tone=None, ang=None, angjit=3.2):
    for i in range(count):
        x = rng.random() * n; y = rng.random() * n
        a = (ang[int(y) % n, int(x) % n] if ang is not None else rng.random() * 6.283) + (rng.random() - 0.5) * angjit
        L = rng.uniform(lmin, lmax); d = np.array([math.cos(a), math.sin(a)]); p0 = np.array([x, y]); p1 = p0 + d * L
        c0, c1 = pal[rng.integers(len(pal))]; t = 1.0 if tone is None else (0.75 + 0.5 * tone[int(y) % n, int(x) % n])
        w = rng.uniform(wmin, wmax); seg(card, tuple(p0), tuple(p1), w, w * 0.25, np.array(c0) * t, np.array(c1) * t)

def worley_iso(n, seed, c, jitter=0.9):
    return worley(n, seed, c, c, jitter)

def leaf_litter(card, rng, n, count, cols, Lr=(26, 50)):
    for i in range(count):
        x = rng.random() * n; y = rng.random() * n; L = rng.uniform(*Lr); c = cols[rng.integers(len(cols))]
        leaf(card, (x, y), rng.random() * 6.283, L, L * rng.uniform(0.22, 0.34), c[0], c[1], rib=rng.random() < 0.7)

def twigs(card, rng, n, count, col=(0.07, 0.05, 0.035)):
    for i in range(count):
        x = rng.random() * n; y = rng.random() * n; a = rng.random() * 6.283; L = rng.uniform(40, 130); d = np.array([math.cos(a), math.sin(a)])
        p = np.array([x, y]); q = p + d * L; seg(card, tuple(p), tuple(q), 2.0, 1.2, col, np.array(col) * 1.25)

def ground_grass(n=1024, seed=101):
    rng = np.random.default_rng(seed); tone = fbm(n, seed, 4, 4, 4)
    soil = ramp(fbm(n, seed + 1, 7, 7, 4), [(0, (0.022, 0.016, 0.010)), (1, (0.075, 0.054, 0.034))])
    WRAP[0] = True; card = new_card(n, n)
    greens = [((0.030, 0.075, 0.018), (0.16, 0.30, 0.06)), ((0.040, 0.095, 0.022), (0.20, 0.34, 0.07)), ((0.025, 0.06, 0.015), (0.13, 0.24, 0.05)), ((0.06, 0.10, 0.03), (0.26, 0.36, 0.09))]
    straw = [((0.12, 0.09, 0.04), (0.30, 0.24, 0.11)), ((0.09, 0.07, 0.035), (0.22, 0.17, 0.08))]
    scatter_strokes(card, rng, n, 5200, 16, 34, 1.4, 2.4, straw, tone)                        # dead thatch underneath
    scatter_strokes(card, rng, n, 26000, 10, 30, 1.0, 2.1, greens, tone)                       # the living grass mat
    scatter_strokes(card, rng, n, 3800, 12, 30, 1.0, 1.9, [straw[0], greens[3]], tone)
    leaf_litter(card, rng, n, 26, [((0.07, 0.04, 0.02), (0.20, 0.11, 0.04)), ((0.10, 0.07, 0.03), (0.26, 0.18, 0.07))], (18, 34))
    WRAP[0] = False
    col = over(soil, card)
    yellow = smooth(fbm(n, seed + 3, 3, 3, 4), 0.55, 0.8)[..., None] * 0.35; col = col * (1 - yellow) + col * np.array([1.5, 1.25, 0.6]) * yellow
    col = col * (0.82 + 0.36 * tone[..., None])
    lum = col @ np.array([0.3, 0.59, 0.11]); h = blur(lum / lum.max(), 1) * 0.7 + 0.3 * fbm(n, seed + 4, 60, 60, 3)
    return col, h

def ground_trampled(n=1024, seed=202):
    rng = np.random.default_rng(seed); tone = fbm(n, seed, 4, 4, 4); flow = fbm(n, seed + 1, 3, 3, 3) * 6.283 * 2
    mud = ramp(fbm(n, seed + 2, 8, 8, 5), [(0, (0.03, 0.021, 0.013)), (0.5, (0.075, 0.052, 0.032)), (1, (0.15, 0.108, 0.07))])
    f1, edge, pid = worley_iso(n, seed + 3, 9); dry = (1 - smooth(edge, 0.0, 0.06)) * smooth(fbm(n, seed + 4, 3, 3, 3), 0.45, 0.7)
    mud = mud * (1 - 0.55 * dry[..., None])
    WRAP[0] = True; card = new_card(n, n)
    straw = [((0.10, 0.075, 0.035), (0.28, 0.22, 0.10)), ((0.15, 0.115, 0.05), (0.36, 0.29, 0.14)), ((0.07, 0.055, 0.03), (0.2, 0.15, 0.07)), ((0.05, 0.09, 0.025), (0.17, 0.25, 0.06))]
    scatter_strokes(card, rng, n, 9000, 30, 80, 1.3, 2.8, straw, tone, flow, 1.0)                # flattened stems lying in swirling directions
    leaf_litter(card, rng, n, 30, [((0.06, 0.035, 0.018), (0.18, 0.10, 0.04)), ((0.09, 0.06, 0.025), (0.22, 0.15, 0.06))], (22, 42)); twigs(card, rng, n, 26)
    WRAP[0] = False
    col = over(mud, card) * (0.8 + 0.4 * tone[..., None])
    lum = col @ np.array([0.3, 0.59, 0.11]); h = 0.55 * blur(lum / lum.max(), 1) + 0.25 * fbm(n, seed + 5, 12, 12, 4) - 0.35 * dry
    return col, h

def ground_mud(n=1024, seed=303):
    rng = np.random.default_rng(seed)
    low = fbm(n, seed, 3, 3, 4); base = ramp(fbm(n, seed + 1, 6, 6, 5), [(0, (0.020, 0.013, 0.008)), (0.5, (0.056, 0.037, 0.023)), (1, (0.12, 0.082, 0.052))])
    rut = fbm(n, seed + 2, 2, 12, 3); ruts = 1 - np.abs(rut * 2 - 1); ruts = smooth(ruts, 0.55, 0.95)              # wheel ruts / churned ridges running one way
    churn = (fbm(n, seed + 3, 14, 14, 5) - 0.5)
    h = 0.55 * ruts + 0.45 * fbm(n, seed + 4, 9, 9, 5) + 0.15 * churn
    pud = smooth(fbm(n, seed + 5, 4, 4, 4), 0.70, 0.78)*0.8; h = h * (1 - pud) + 0.28 * pud                          # puddles are flat
    col = base * (0.75 + 0.5 * smooth(h, 0.2, 0.9)[..., None])
    wet = np.array([0.034, 0.030, 0.026]); col = col * (1 - 0.75 * pud[..., None]) + wet * 0.75 * pud[..., None]
    f1, edge, pid = worley_iso(n, seed + 6, 34, 0.95); pebble = (pid < 0.16) & (f1 < 0.30); dome = np.sqrt(np.clip(1 - (f1 / 0.30) ** 2, 0, 1)) * pebble
    pc = ramp(pid * 6, [(0, (0.10, 0.09, 0.08)), (0.5, (0.17, 0.15, 0.12)), (1, (0.12, 0.1, 0.07))]) * (1 - 0.5 * (pid * 6 % 1) * 0.3)[..., None]
    col = col * (1 - pebble[..., None] * 0.9) + pc * pebble[..., None] * 0.9; h = h + 0.45 * dome * (1 - pud)
    WRAP[0] = True; card = new_card(n, n)
    scatter_strokes(card, rng, n, 900, 25, 60, 1.2, 2.2, [((0.08, 0.06, 0.03), (0.2, 0.15, 0.07))], low); twigs(card, rng, n, 18, (0.06, 0.045, 0.03))
    WRAP[0] = False
    col = over(col, card); h = h + 0.12 * blur(card[..., 3], 1)
    return col, h

def ground_dirt(n=1024, seed=404):
    rng = np.random.default_rng(seed); tone = fbm(n, seed, 3, 3, 4)
    base = ramp(fbm(n, seed + 1, 8, 8, 5), [(0, (0.05, 0.036, 0.024)), (0.5, (0.11, 0.08, 0.052)), (1, (0.21, 0.16, 0.105))])
    grain = fbm(n, seed + 2, 120, 120, 3); base = base * (0.85 + 0.3 * grain[..., None])
    f1, edge, pid = worley_iso(n, seed + 3, 7); cr = (1 - smooth(edge, 0.0, 0.05)) * smooth(fbm(n, seed + 4, 3, 3, 3), 0.42, 0.65)
    base = base * (1 - 0.6 * cr[..., None])
    g1, e1, p1 = worley_iso(n, seed + 5, 30, 0.95); peb = (p1 < 0.4) & (g1 < 0.34); dome = np.sqrt(np.clip(1 - (g1 / 0.34) ** 2, 0, 1)) * peb
    pc = ramp(p1 * 2.5, [(0, (0.12, 0.10, 0.085)), (0.5, (0.22, 0.19, 0.15)), (1, (0.16, 0.12, 0.09))]) * (0.85 + 0.3 * grain[..., None])
    col = base * (1 - peb[..., None]) + pc * peb[..., None] * (0.55 + 0.45 * dome[..., None])
    WRAP[0] = True; card = new_card(n, n)
    leaf_litter(card, rng, n, 80, [((0.05, 0.03, 0.015), (0.16, 0.09, 0.03)), ((0.09, 0.06, 0.025), (0.24, 0.16, 0.06)), ((0.08, 0.05, 0.02), (0.20, 0.12, 0.05)), ((0.03, 0.025, 0.02), (0.10, 0.08, 0.06))])
    twigs(card, rng, n, 60); scatter_strokes(card, rng, n, 1400, 22, 55, 1.1, 2.0, [((0.12, 0.09, 0.04), (0.30, 0.24, 0.11)), ((0.06, 0.1, 0.03), (0.17, 0.24, 0.07))], tone)
    WRAP[0] = False
    col = over(col, card) * (0.85 + 0.3 * tone[..., None])
    h = 0.4 * fbm(n, seed + 6, 20, 20, 5) + 0.5 * dome + 0.25 * blur(card[..., 3], 1) - 0.3 * cr
    return col, h

def ground_stone(n=1024, seed=505):
    rng = np.random.default_rng(seed)
    f1, edge, pid = worley_iso(n, seed, 13, 0.95); gap = 1 - smooth(edge, 0.0, 0.10)
    dome = np.sqrt(np.clip(1 - (f1 / 0.66) ** 2, 0, 1)) * (0.7 + 0.3 * pid)
    stone = ramp(pid, [(0, (0.10, 0.095, 0.09)), (0.35, (0.2, 0.18, 0.15)), (0.7, (0.28, 0.25, 0.2)), (1, (0.17, 0.15, 0.12))])
    stone = stone * (0.8 + 0.4 * fbm(n, seed + 1, 90, 90, 4)[..., None]); stone = stone * (0.7 + 0.3 * smooth(dome, 0.0, 1.0)[..., None])
    spots = smooth(fbm(n, seed + 2, 24, 24, 3), 0.7, 0.78)[..., None]; stone = stone * (1 - 0.35 * spots) + np.array([0.3, 0.3, 0.24]) * 0.35 * spots
    soil = ramp(fbm(n, seed + 3, 30, 30, 4), [(0, (0.03, 0.022, 0.014)), (1, (0.09, 0.066, 0.042))])
    moss = smooth(fbm(n, seed + 4, 6, 6, 4), 0.5, 0.72)[..., None] * gap[..., None]; soil = soil * (1 - 0.7 * moss) + np.array([0.06, 0.10, 0.03]) * 0.7 * moss
    col = stone * (1 - gap[..., None]) + soil * gap[..., None]
    mossy = smooth(fbm(n, seed + 5, 5, 5, 4), 0.62, 0.8)[..., None] * smooth(1 - dome, 0.45, 0.9)[..., None] * (1 - gap[..., None])
    col = col * (1 - 0.5 * mossy) + np.array([0.07, 0.12, 0.035]) * 0.5 * mossy
    WRAP[0] = True; card = new_card(n, n)
    leaf_litter(card, rng, n, 20, [((0.07, 0.04, 0.02), (0.2, 0.11, 0.04))], (18, 32)); scatter_strokes(card, rng, n, 900, 14, 34, 1.1, 1.9, [((0.05, 0.09, 0.025), (0.15, 0.24, 0.06))], None)
    WRAP[0] = False
    col = over(col, card)
    h = 0.85 * dome * (1 - gap) + 0.1 * fbm(n, seed + 6, 50, 50, 3) + 0.1 * blur(card[..., 3], 1)
    return col, h

# ------------------------------------------------------------------------------------------------ WATER (seamless)
def water_height(n=512, seed=77):
    """waves from integer wave-vectors (so they tile exactly), mostly travelling along x, plus choppy ripples"""
    rng = np.random.default_rng(seed); Y, X = np.mgrid[0:n, 0:n].astype(float); h = np.zeros((n, n))
    for i in range(30):
        kx = int(rng.integers(2, 17)) * (1 if rng.random() < 0.85 else -1); ky = int(rng.integers(-9, 10))
        amp = 1.0 / (math.hypot(kx, ky) ** 1.15); ph = rng.random() * 6.283
        h += amp * np.sin(2 * math.pi * (kx * X + ky * Y) / n + ph)
    ch = 1 - np.abs(fbm(n, seed + 1, 14, 9, 4) * 2 - 1)              # choppy ridges
    h = h / np.abs(h).max() + 0.30 * ch + 0.10 * fbm(n, seed + 2, 24, 24, 3)
    return (h - h.min()) / (h.max() - h.min())

def water_colour(n, h, seed=78):
    """neutral light/dark map (the material colour tints it): silty patches, slow swirls and pale foam streaks on the crests"""
    silt = fbm(n, seed, 4, 3, 5); swirl = warp(fbm(n, seed + 1, 7, 4, 4), n, seed + 2, 0.14, 3)
    l = 0.62 + 0.22 * silt + 0.12 * (swirl - 0.5)
    crest = smooth(h, 0.62, 0.86) * smooth(fbm(n, seed + 3, 10, 40, 4), 0.50, 0.70)
    foam = np.clip(blur(crest, 3) * 0.9, 0, 0.55)
    col = np.stack([l * 1.00, l * 0.98, l * 0.90], -1)                 # faint warm silt
    col = col * (1 - foam[..., None]) + np.array([0.97, 0.98, 0.96]) * foam[..., None]
    return np.clip(col, 0, 1)
