"""v2 textures for veg_broadleaf (PIL): lobed English-oak leaf card, ovate serrated silver-birch leaf card, lighter fissured oak bark.
Run: python3 gen_broadleaf.py <src_dir_with_bark_oak_c.jpg> <out_dir>"""
import sys, math, random, numpy as np
from PIL import Image, ImageDraw, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
rnd = random.Random(5)

def bleed(img, rad=6):
    a = np.asarray(img).astype(np.float32); al = a[..., 3:4] / 255
    pm = Image.fromarray((a[..., :3] * al).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad))
    am = Image.fromarray((al[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad))
    p = np.asarray(pm).astype(np.float32); m = np.asarray(am).astype(np.float32)[..., None] / 255
    fill = np.clip(p / np.maximum(m, 1e-3), 0, 255)
    rgb = np.where(a[..., 3:4] > 0, a[..., :3], fill)
    return Image.fromarray(np.concatenate([rgb, a[..., 3:4]], -1).astype(np.uint8), 'RGBA')

def jit(c, k=0.14):
    f = 1 + rnd.uniform(-k, k); return tuple(max(0, min(255, int(v * f))) for v in c)

def leaf_poly(x, y, ang, L, Wd, kind):
    """polygon of one leaf from its base (x,y) pointing at angle ang"""
    pts = []; n = 26
    def half(t):
        if kind == 'oak':   # obovate with 4-5 rounded lobes per side, narrow base
            env = math.sin(math.pi * min(1, t ** 0.75)) ; lob = 1 + 0.38 * math.sin(2 * math.pi * (4.5 * t) + 0.6)
            return Wd * 0.5 * env * lob * (0.35 + 0.65 * t ** 0.5)
        else:               # birch: ovate, widest near the base, pointed tip, toothed edge
            env = (1 - t) ** 0.8 * math.sin(math.pi * min(1, t * 0.55 + 0.02) * 1.0) ** 0.7 * 1.9
            tooth = 1 + 0.12 * (1 if int(t * 14) % 2 == 0 else -1)
            return Wd * 0.5 * min(1.0, env) * tooth
    for sgn in (1, -1):
        rng_t = range(n + 1) if sgn == 1 else range(n, -1, -1)
        for i in rng_t:
            t = i / n; px = L * t; py = sgn * half(t)
            pts.append((x + px * math.cos(ang) - py * math.sin(ang), y + px * math.sin(ang) + py * math.cos(ang)))
    return pts

def draw_leaf(d, x, y, ang, L, Wd, kind, base, vein, edge, S):
    pts = leaf_poly(x, y, ang, L, Wd, kind); d.polygon(pts, fill=jit(base) + (255,))
    d.line(pts + [pts[0]], fill=edge + (255,), width=max(1, int(1.6 * S)))
    x2, y2 = x + L * 0.9 * math.cos(ang), y + L * 0.9 * math.sin(ang); d.line([(x, y), (x2, y2)], fill=vein + (255,), width=max(1, int(1.3 * S)))
    for k in range(1, 6):   # side veins
        t = k / 6.0; vx, vy = x + L * t * math.cos(ang), y + L * t * math.sin(ang)
        for sgn in (1, -1):
            a2 = ang + sgn * 0.9; hl = Wd * 0.28
            d.line([(vx, vy), (vx + hl * math.cos(a2), vy + hl * math.sin(a2))], fill=vein + (255,), width=max(1, int(0.9 * S)))

def card(kind, W=1024, H=512, S=2):
    w, h = W * S, H * S; im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cy = h * 0.5
    if kind == 'oak':
        greens = [(46, 86, 34), (58, 102, 40), (74, 120, 46), (38, 74, 30)]; vein = (112, 140, 70); edge = (26, 52, 22); LL, WW = 74 * S, 52 * S
    else:
        greens = [(96, 142, 54), (118, 160, 62), (84, 126, 48), (134, 168, 70)]; vein = (170, 190, 100); edge = (52, 84, 30); LL, WW = 46 * S, 34 * S
    twig = (84, 60, 40, 255)
    pts = [(10 * S + i * (w - 40 * S) / 24, cy + math.sin(i * 0.4) * 6 * S) for i in range(25)]
    for i in range(24): d.line([pts[i], pts[i + 1]], fill=twig, width=max(2, int((6 * (1 - i / 30) + 2) * S)))
    def cluster(px, py, ang, n, spread):
        for _ in range(n):
            a = ang + rnd.uniform(-spread, spread); k = rnd.uniform(0.8, 1.15)
            draw_leaf(d, px, py, a, LL * k, WW * k, kind, rnd.choice(greens), vein, edge, S)
    for i in range(1, 24):
        for sgn in (-1, 1):
            if rnd.random() < 0.85:
                Ls = (h * 0.34) * (1 - i / 30) * rnd.uniform(0.6, 1.0); a0 = math.radians(rnd.uniform(40, 70)) * (1 if kind == 'oak' else 1.15)
                p0 = pts[i]; dd = (math.cos(a0), sgn * math.sin(a0)); p1 = (p0[0] + dd[0] * Ls, p0[1] + dd[1] * Ls)
                d.line([p0, p1], fill=twig, width=max(2, int(3 * S)))
                ang = math.atan2(dd[1], dd[0])
                cluster(p1[0], p1[1], ang, 5 if kind == 'oak' else 4, 0.8)
                mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2); cluster(mid[0], mid[1], ang + sgn * 0.5, 2, 0.5)
    cluster(pts[-1][0], pts[-1][1], 0.0, 7, 0.9)
    im = im.resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32); a[..., 3] = np.where(a[..., 3] > 90, 255, 0)
    return bleed(Image.fromarray(a.astype(np.uint8), 'RGBA'))

def oak_bark():
    src = np.asarray(Image.open(SRC + '/bark_oak_c.jpg').convert('RGB')).astype(np.float32) / 255
    lum = src.mean(-1, keepdims=True)
    lum = np.clip((lum - lum.min()) / (lum.max() - lum.min() + 1e-6), 0, 1) ** 0.8
    col = np.concatenate([lum * 0.50 + 0.10, lum * 0.43 + 0.085, lum * 0.34 + 0.065], -1)
    return Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), 'RGB')

card('oak').save(OUT + '/oak_v5.png'); card('birch').save(OUT + '/birch_v5.png'); oak_bark().save(OUT + '/bark_oak_light_c.jpg', quality=92)
print('ok')
