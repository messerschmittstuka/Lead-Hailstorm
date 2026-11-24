"""Procedural textures for the German rifleman (veg-style loop asset german_soldier).
usage: python3 gen_soldier_tex.py <outdir>
Face texture is a cylindrical map of the head ellipsoid; features are placed in 3D (metres) so they line up with the sculpted head in build.py."""
import numpy as np, sys, os
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)
# head ellipsoid (must match build.py)
RX, RY, RZ, ZC = 0.078, 0.095, 0.115, 1.66


def lp(n, sigma, seed, sx=None, sy=None):
    """tileable low-pass noise, zero mean unit std; sigma in px (optionally anisotropic)"""
    r = np.random.default_rng(seed); a = r.standard_normal((n, n)); f = np.fft.fft2(a)
    fx = np.fft.fftfreq(n)[None, :]; fy = np.fft.fftfreq(n)[:, None]
    sx = sigma if sx is None else sx; sy = sigma if sy is None else sy
    g = np.exp(-((fx * 2 * np.pi * sx) ** 2 + (fy * 2 * np.pi * sy) ** 2) / 2)
    b = np.real(np.fft.ifft2(f * g)); return (b - b.mean()) / (b.std() + 1e-9)


def save(name, arr):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB').save(os.path.join(OUT, name + '.png')); print('wrote', name, arr.shape)


def col(c, n): return np.ones((n, n, 3)) * np.array(c, float)


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def wool(n=512):
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    img = col((86, 92, 77), n)
    tw = np.sin(2 * np.pi * (X + Y) / 6.0) * 0.5 + np.sin(2 * np.pi * (X - Y) / 12.0) * 0.25   # twill
    k = 1 + 0.08 * lp(n, 26, 1) + 0.06 * lp(n, 2, 2) + 0.035 * tw + 0.03 * lp(n, 1, 9)
    img = img * k[..., None]
    st = lp(n, 12, 3); img *= (1 - 0.16 * sstep(1.2, 2.2, st))[..., None]                         # stains
    gr = lp(n, 40, 4); img += np.array((10, 8, -2)) * sstep(0.9, 2.0, gr)[..., None]              # sun-faded patches
    save('wool', img)


def skin_body(n=512):
    img = col((212, 166, 140), n)
    img *= (1 + 0.05 * lp(n, 30, 11) + 0.025 * lp(n, 1.2, 12))[..., None]
    img += np.array((5, -2, -2)) * lp(n, 40, 13)[..., None] * 0.8
    d = sstep(0.6, 2.6, lp(n, 30, 14)); img = img * (1 - 0.2 * d[..., None]) + np.array((110, 84, 62)) * 0.2 * d[..., None]
    save('skin_body', img)


def leather(name, base, n=512, seed=20, scuff=(30, 26, 22)):
    img = col(base, n); g = lp(n, 1.8, seed); g2 = lp(n, 3.4, seed + 1)
    pebble = np.clip(g * 0.6 + g2 * 0.4, -2.5, 2.5)
    img *= (1 + 0.16 * pebble)[..., None]
    img *= (1 + 0.06 * lp(n, 30, seed + 2))[..., None]
    w = sstep(1.2, 2.2, lp(n, 18, seed + 3)); img = img * (1 - 0.5 * w[..., None]) + (np.array(base) + np.array(scuff)) * 0.5 * w[..., None]
    save(name, img)


def canvas(n=512):
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    img = col((148, 140, 110), n)
    warp = np.sin(2 * np.pi * X / 4.0); weft = np.sin(2 * np.pi * Y / 4.0); over = (((X // 4) + (Y // 4)) % 2)
    th = np.where(over == 1, warp, weft) * 0.5 + 0.3 * warp * weft
    img *= (1 + 0.07 * th + 0.07 * lp(n, 20, 31) + 0.04 * lp(n, 1.2, 32))[..., None]
    st = sstep(1.1, 2.1, lp(n, 10, 33)); img *= (1 - 0.2 * st[..., None])
    save('canvas', img)


def helmet(n=512):
    img = col((70, 76, 66), n); r = np.random.default_rng(41)
    img *= (1 + 0.07 * lp(n, 1.0, 40) + 0.05 * lp(n, 18, 42) + 0.03 * lp(n, 4, 43))[..., None]
    # worn paint: lighter steel showing through, rust spots, scratches
    wear = sstep(1.5, 2.4, lp(n, 6, 44)); img = img * (1 - 0.6 * wear[..., None]) + np.array((105, 104, 98)) * 0.6 * wear[..., None]
    rust = sstep(1.9, 2.8, lp(n, 3, 45)); img = img * (1 - 0.6 * rust[..., None]) + np.array((128, 78, 46)) * 0.6 * rust[..., None]
    from PIL import ImageDraw
    m = Image.new('L', (n, n), 0); d = ImageDraw.Draw(m)
    for _ in range(90):
        x0, y0 = r.integers(0, n, 2); a = r.uniform(0, 6.28); L = r.integers(6, 40)
        d.line([(x0, y0), (x0 + L * np.cos(a), y0 + L * np.sin(a))], fill=int(r.integers(60, 160)), width=1)
    mk = np.asarray(m, float) / 255; img = img * (1 - 0.5 * mk[..., None]) + np.array((130, 128, 120)) * 0.5 * mk[..., None]
    save('helmet', img)


def metal(n=512):
    img = col((120, 122, 117), n)
    img *= (1 + 0.10 * lp(n, 0.8, 51, sx=22, sy=0.8) + 0.05 * lp(n, 20, 52) + 0.03 * lp(n, 1, 53))[..., None]
    rust = sstep(1.7, 2.6, lp(n, 4, 54)); img = img * (1 - 0.5 * rust[..., None]) + np.array((120, 74, 44)) * 0.5 * rust[..., None]
    save('metal', img)


def face(name, seed=3, skin=(214, 168, 143), hair=(112, 90, 60), iris=(120, 150, 162), stub=0.04, N=1024):
    r = np.random.default_rng(seed)
    u = (np.arange(N) + 0.5) / N; v = 1 - (np.arange(N) + 0.5) / N
    U, V = np.meshgrid(u, v)
    th = (U - 0.5) * 2 * np.pi; cps = 2 * V - 1; z = ZC + RZ * cps; s = np.sqrt(np.clip(1 - cps ** 2, 0, 1))
    x = RX * s * np.sin(th); fr = np.cos(th); xa = np.abs(x)
    gate = sstep(0.05, 0.4, fr)

    def G(cx, cz, sx, sz, X=x): return np.exp(-0.5 * (((X - cx) / sx) ** 2 + ((z - cz) / sz) ** 2))
    img = col(skin, N)
    img *= (1 + 0.04 * lp(N, 40, seed + 1) + 0.02 * lp(N, 1.5, seed + 2))[..., None]
    ao = np.zeros((N, N))
    ao += 0.30 * G(0.034, 1.686, 0.018, 0.010, xa)           # eye sockets
    ao += 0.12 * G(0.020, 1.642, 0.008, 0.020, xa)           # beside the nose
    ao += 0.20 * G(0.0, 1.620, 0.016, 0.006)                 # under the nose
    ao += 0.16 * G(0.0, 1.577, 0.017, 0.005)                 # under the lower lip
    ao += 0.12 * G(0.0, 1.712, 0.040, 0.010)                 # under the helmet / brow
    ao += 0.22 * sstep(1.566, 1.545, z)                      # under the chin
    img *= (1 - ao * gate)[..., None]
    red = (G(0.050, 1.640, 0.022, 0.020, xa) * 0.9 + G(0.0, 1.631, 0.010, 0.008) * 0.8) * gate
    img += np.array((22, -9, -9)) * red[..., None]
    img += np.array((8, 4, 3)) * (G(0.0, 1.72, 0.05, 0.012) * gate)[..., None]
    # eyes
    for sg in (-1, 1):
        cx, cz = sg * 0.032, 1.686
        e = ((x - cx) / 0.0125) ** 2 + ((z - cz) / 0.0060) ** 2
        white = sstep(1.08, 0.92, e) * gate
        sc = np.array((228, 218, 206)) * (0.72 + 0.28 * np.clip((z - cz + 0.0072) / 0.0144, 0, 1))[..., None]
        sc += np.array((10, -12, -12)) * sstep(0.55, 1.0, e)[..., None]
        img = img * (1 - white[..., None]) + sc * white[..., None]
        d = np.sqrt((x - cx) ** 2 + ((z - cz) * 1.05) ** 2)
        ir = sstep(0.0058, 0.0050, d) * gate * (e < 1.0)
        ic = np.array(iris)[None, None, :] * (0.55 + 0.7 * sstep(0.0, 0.0054, d))[..., None] * (1 - 0.25 * sstep(0.0044, 0.0056, d))[..., None]
        img = img * (1 - ir[..., None]) + ic * ir[..., None]
        pu = sstep(0.0026, 0.0020, d) * gate; img = img * (1 - pu[..., None]) + 12 * pu[..., None]
        hl = sstep(0.0016, 0.0010, np.sqrt((x - cx + 0.0020) ** 2 + (z - cz - 0.0022) ** 2)) * gate; img = img * (1 - hl[..., None]) + 250 * hl[..., None]
        lid = sstep(0.35, 0.0, np.abs(e - 1.12)) * (z > cz - 0.002) * gate
        img = img * (1 - 0.8 * lid[..., None]) + np.array((58, 38, 32)) * 0.8 * lid[..., None]
        ll = sstep(0.25, 0.0, np.abs(e - 1.18)) * (z < cz - 0.002) * gate
        img = img * (1 - 0.25 * ll[..., None]) + np.array((120, 80, 70)) * 0.25 * ll[..., None]
        zb = 1.703 + 0.004 * np.sin(np.pi * np.clip((xa - 0.012) / 0.044, 0, 1)) - 0.001 * (sg < 0) * 0
        sx_ = x * sg
        brow = (np.abs(z - zb) < 0.0043) * (sx_ > 0.010) * (sx_ < 0.058) * gate
        strokes = 0.82 + 0.18 * lp(N, 2.2, seed + 7 + sg)
        brow = brow * np.clip(strokes, 0, 1) * (1 - 0.5 * sstep(0.04, 0.058, sx_))
        img = img * (1 - 0.7 * brow[..., None]) + np.array(hair) * 0.7 * 0.7 * brow[..., None]
    for sg in (-1, 1):
        cx, cz = sg * 0.032, 1.686
        e = ((x - cx) / 0.0125) ** 2 + ((z - cz) / 0.0060) ** 2
        crease = sstep(0.25, 0.0, np.abs(np.sqrt(((x - cx) / 0.0140) ** 2 + ((z - cz - 0.0075) / 0.0060) ** 2) - 1.0)) * (z > cz + 0.003) * gate
        img = img * (1 - 0.28 * crease[..., None]) + np.array((120, 80, 70)) * 0.28 * crease[..., None]
        lash = sstep(0.14, 0.0, np.abs(e - 1.0)) * (z > cz - 0.001) * gate; img = img * (1 - 0.85 * lash[..., None]) + np.array((44, 32, 26)) * 0.85 * lash[..., None]
        duct = G(cx - sg * 0.0112, cz - 0.0004, 0.0022, 0.0020) * gate; img = img * (1 - 0.6 * duct[..., None]) + np.array((196, 110, 104)) * 0.6 * duct[..., None]
        bag = G(cx, cz - 0.0125, 0.012, 0.004) * gate; img = img * (1 - 0.10 * bag[..., None]) + np.array((150, 120, 140)) * 0.10 * bag[..., None]
    pores = sstep(1.3, 3.2, lp(N, 0.8, seed + 40)) * gate; img *= (1 - 0.07 * pores)[..., None]
    nos = (G(0.0085, 1.626, 0.0045, 0.0028, xa)) * gate; img *= (1 - 0.65 * nos)[..., None]
    up = G(0.0, 1.601, 0.019, 0.0032) * gate; lo = G(0.0, 1.590, 0.017, 0.0044) * gate
    img = img * (1 - 0.9 * up[..., None]) + np.array((176, 108, 100)) * 0.8 * up[..., None]
    img = img * (1 - 0.9 * lo[..., None]) + np.array((184, 116, 106)) * 0.8 * lo[..., None]
    ml = (np.abs(z - (1.5945 + 0.0015 * (x / 0.02) ** 2)) < 0.0008) * (xa < 0.022) * gate
    img = img * (1 - 0.85 * ml[..., None]) + np.array((88, 48, 44)) * 0.85 * ml[..., None]
    # stubble
    jaw = sstep(1.622, 1.605, z) * sstep(0.064, 0.05, xa)
    cheek = sstep(0.026, 0.040, xa) * sstep(1.655, 1.640, z) * sstep(0.064, 0.052, xa)
    region = np.maximum(jaw, cheek) * gate * (1 - 0.85 * np.maximum(up, lo))
    region = np.maximum(region, 0.6 * sstep(1.585, 1.572, z) * sstep(1.552, 1.57, z) * gate)
    sp = (r.random((N, N)) < stub * region * 0.5)
    img = img * (1 - 0.4 * sp[..., None]) + np.array((50, 40, 34)) * 0.4 * sp[..., None]
    img *= (1 - 0.06 * stub * region)[..., None]
    # hair
    zh = 1.728 - 0.115 * sstep(1.0, 1.95, np.abs(th))
    hm = sstep(zh - 0.002, zh + 0.002, z)
    hc = np.array(hair)[None, None, :] * (0.75 + 0.35 * np.clip(0.5 + 0.5 * lp(N, 1.0, seed + 9), 0, 1))[..., None]
    img = img * (1 - hm[..., None]) + hc * hm[..., None]
    # dirt and sweat sheen
    dirt = sstep(1.0, 2.0, lp(N, 55, seed + 20)) * 0.30
    img = img * (1 - dirt[..., None]) + np.array((112, 86, 62)) * dirt[..., None]
    save(name, img)


def collar(n=512):
    X, Y = np.meshgrid(np.arange(n), np.arange(n)); img = col((44, 62, 48), n)
    tw = np.sin(2 * np.pi * (X + Y) / 6.0) * 0.5
    img *= (1 + 0.08 * lp(n, 26, 61) + 0.06 * lp(n, 2, 62) + 0.035 * tw)[..., None]; save('collar', img)


def litzen(n=256):
    img = col((40, 58, 44), n); img *= (1 + 0.06 * lp(n, 2, 71))[..., None]
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    for y0 in (n * 0.30, n * 0.70):                         # the two bars of the collar patch (field-grey on dark green)
        m = np.abs(Y - y0) < n * 0.07; edge = np.abs(Y - y0) > n * 0.045
        bar = np.where(m, np.where(edge, 150, 188), 0)[..., None] * np.ones(3) * np.array((0.92, 0.95, 0.9))
        img = np.where(m[..., None], bar * (1 + 0.05 * lp(n, 1.2, 72))[..., None], img)
    save('litzen', img)


if __name__ == '__main__':
    collar(); litzen()
    wool(); skin_body(); leather('leather_black', (30, 28, 27), seed=20); leather('leather_brown', (98, 64, 40), seed=24, scuff=(32, 26, 20))
    canvas(); helmet(); metal(); face('face_a')
