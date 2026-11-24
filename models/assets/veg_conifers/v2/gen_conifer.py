"""v2 textures for veg_conifers (PIL): dense Scots pine needle card, heavy-snow spruce card, grey and orange pine bark. Run: python3 gen_conifer.py <src_dir> <out_dir>"""
import sys, math, random, numpy as np
from PIL import Image, ImageDraw, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
rnd = random.Random(11); rng = np.random.default_rng(11)

def noise(h, w, sig, seed):
    r = np.random.default_rng(seed).random((h, w)).astype(np.float32)
    im = Image.fromarray((r * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(sig))
    a = np.asarray(im).astype(np.float32); a = (a - a.min()) / (a.max() - a.min() + 1e-6); return a

# ---------- pine needle card: twig along u, shoots both sides, each shoot ends in a dense brush of paired needles
def pine_card(W=1024, H=512, S=2):
    w, h = W * S, H * S; im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cy = h * 0.5
    def line(p0, p1, wd, col): d.line([p0, p1], fill=col, width=max(1, int(wd)))
    twig = (92, 58, 34, 255)
    pts = [(10 * S + i * (w - 40 * S) / 24, cy + math.sin(i * 0.35) * 5 * S) for i in range(25)]
    for i in range(24): line(pts[i], pts[i + 1], (5.5 * (1 - i / 30) + 1.5) * S, twig)
    greens = [(38, 78, 52), (46, 92, 60), (58, 108, 66), (30, 64, 46), (70, 118, 74)]
    def brush(p, ang, ln, n):
        for _ in range(n):
            a = ang + rnd.uniform(-0.9, 0.9); l2 = ln * rnd.uniform(0.6, 1.05); curl = rnd.uniform(-0.25, 0.25)
            g = rnd.choice(greens); g = tuple(int(c * rnd.uniform(0.85, 1.15)) for c in g) + (255,)
            x0, y0 = p; x1 = x0 + math.cos(a) * l2 * 0.5; y1 = y0 + math.sin(a) * l2 * 0.5
            x2 = x1 + math.cos(a + curl) * l2 * 0.5; y2 = y1 + math.sin(a + curl) * l2 * 0.5
            d.line([(x0, y0), (x1, y1), (x2, y2)], fill=g, width=max(2, int(2.6 * S)))
            if rnd.random() < 0.5:   # twin needle of the pair, slightly splayed
                d.line([(x0, y0), (x1 + 3 * S, y1 - 3 * S), (x2 + 5 * S, y2 - 4 * S)], fill=g, width=max(2, int(2.4 * S)))
    for i in range(2, 24):
        for sgn in (-1, 1):
            if rnd.random() < 0.9:
                L = (h * 0.40) * (1 - i / 30) * rnd.uniform(0.6, 1.0); a0 = math.radians(rnd.uniform(35, 65))
                p0 = pts[i]; dd = (math.cos(a0), sgn * math.sin(a0)); p1 = (p0[0] + dd[0] * L, p0[1] + dd[1] * L)
                line(p0, p1, 2.6 * S, twig)
                ang = math.atan2(dd[1], dd[0]); ln = 60 * S * (1 - i / 45)
                brush(p1, ang, ln, 30)
                for f in (0.45, 0.75): brush((p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f), ang, ln * 0.8, 14)
    brush(pts[-1], 0.0, 100 * S, 42)
    im = im.resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32); a[..., 3] = np.where(a[..., 3] > 90, 255, 0)   # hard alpha-clip friendly
    n = noise(H, W, 5, 3); a[..., :3] *= (0.85 + 0.3 * n[..., None]); a = np.clip(a, 0, 255)
    return Image.fromarray(a.astype(np.uint8), 'RGBA')

# ---------- snow spruce card: spruce card with heavy clumped snow on the needles, thickened silhouette
def snow_card():
    src = Image.open(SRC + '/spruce_v4.png').convert('RGBA'); a = np.asarray(src).astype(np.float32) / 255
    al = a[..., 3]; h, w = al.shape
    big = noise(h, w, 14, 21); small = noise(h, w, 3, 22); sn = 0.65 * big + 0.35 * small
    # heavier snow toward the upper half of the card (v>0.5) and along the twig, patchy elsewhere
    vv = np.linspace(0, 1, h)[:, None]; bias = 0.12 * (np.abs(vv - 0.5) * 2)
    mask = (al > 0.35) & (sn > 0.515)
    # snow caps grow a little beyond the needles
    m_img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    m = np.asarray(m_img).astype(np.float32) / 255
    shade = 0.84 + 0.16 * noise(h, w, 4, 23)
    snow = np.stack([0.95 * shade, 0.97 * shade, 1.0 * shade], -1)
    k = (m > 0.45)[..., None].astype(np.float32)
    out = a.copy(); out[..., :3] = a[..., :3] * (1 - k) + snow * k
    out[..., 3] = np.maximum(al, (m > 0.45).astype(np.float32))
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGBA')

# ---------- pine bark: grey-brown plates low on the trunk, orange flaking above
def bark_variants():
    src = np.asarray(Image.open(SRC + '/bark_pine_c.jpg').convert('RGB')).astype(np.float32) / 255
    lum = src.mean(-1, keepdims=True)
    grey = np.concatenate([lum * 0.95 + 0.02, lum * 0.88 + 0.015, lum * 0.80 + 0.012], -1) * 0.95
    n = noise(src.shape[0], src.shape[1], 18, 31)[..., None]
    grey = grey * (0.85 + 0.3 * n)
    orange = np.concatenate([lum * 1.15 + 0.03, lum * 0.66 + 0.012, lum * 0.30 + 0.006], -1)
    flake = (noise(src.shape[0], src.shape[1], 6, 32)[..., None] > 0.58).astype(np.float32)   # paler papery flakes
    orange = orange * (1 - 0.35 * flake) + np.array([0.62, 0.36, 0.18]) * 0.35 * flake * (0.6 + lum)
    f = lambda x: Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8), 'RGB')
    return f(grey), f(orange)

pine_card().save(OUT + '/pine_v5.png')
snow_card().save(OUT + '/spruce_snow_v5.png')
g, o = bark_variants(); g.save(OUT + '/bark_pine_low_c.jpg', quality=92); o.save(OUT + '/bark_pine_up_c.jpg', quality=92)
print('ok')
