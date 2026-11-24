import bpy, sys, os, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/tank/'; os.makedirs(OUT, exist_ok=True)

def save_rgb(path, arr):
    h, w = arr.shape[:2]; im = bpy.data.images.new('t', w, h, alpha=False); im.colorspace_settings.name = 'sRGB'
    a4 = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], 2).astype(np.float32); im.pixels.foreach_set(a4.ravel())
    im.filepath_raw = path; im.file_format = 'JPEG'; im.save(); bpy.data.images.remove(im)

def seam(a): return round(float(np.abs(a[:, 0] - a[:, -1]).mean() / (np.abs(a[:, 5] - a[:, 6]).mean() + 1e-9)), 2), round(float(np.abs(a[0] - a[-1]).mean() / (np.abs(a[5] - a[6]).mean() + 1e-9)), 2)

def scratches(n, seed, count, lo=(0.30, 0.28, 0.25), hi=(0.46, 0.43, 0.38)):
    rng = np.random.default_rng(seed); card = new_card(n, n); WRAP[0] = True
    scatter_strokes(card, rng, n, count, 12, 70, 0.8, 1.4, [(lo, hi)], None); WRAP[0] = False
    return card

def tank_paint(n=1024, seed=801, base=(0.40, 0.28, 0.115)):
    """weathered tank paint: mottled, sun-faded, dusty, rain-streaked, chipped down to red-oxide primer and bare steel, scratched"""
    b = np.array(base)[None, None, :]
    col = b * (0.80 + 0.40 * fbm(n, seed, 5, 5, 5)[..., None]) * (0.93 + 0.14 * fbm(n, seed + 1, 140, 140, 2)[..., None])
    fade = smooth(fbm(n, seed + 2, 3, 3, 4), 0.45, 0.8) * 0.35
    col = col * (1 - fade[..., None]) + b * 1.25 * fade[..., None]
    dust = smooth(fbm(n, seed + 3, 4, 4, 5), 0.5, 0.85) * 0.42
    col = col * (1 - dust[..., None]) + np.array([0.34, 0.28, 0.19])[None, None, :] * dust[..., None]
    streak = smooth(fbm(n, seed + 4, 70, 3, 4), 0.55, 0.82) * smooth(fbm(n, seed + 5, 4, 3, 3), 0.35, 0.7)
    col = col * (1 - 0.32 * streak[..., None])
    chip = smooth(fbm(n, seed + 6, 9, 9, 5) + 0.5 * fbm(n, seed + 7, 90, 90, 3), 1.02, 1.14)
    prim = ramp(fbm(n, seed + 8, 30, 30, 4), [(0, (0.10, 0.035, 0.022)), (0.5, (0.20, 0.07, 0.04)), (1, (0.30, 0.12, 0.05))])
    steel = smooth(fbm(n, seed + 9, 50, 50, 3), 0.55, 0.8)
    under = prim * (1 - steel[..., None] * 0.7) + np.array([0.10, 0.10, 0.10])[None, None, :] * steel[..., None] * 0.7
    col = col * (1 - chip[..., None]) + under * chip[..., None]
    sc = scratches(n, seed + 10, 150)
    col = col * (1 - 0.40 * sc[..., 3:4]) + sc[..., :3] * 0.40 * sc[..., 3:4]
    grime = smooth(fbm(n, seed + 11, 3, 3, 5), 0.52, 0.88) * 0.30; col = col * (1 - grime[..., None])
    h = 0.62 + 0.04 * fbm(n, seed + 12, 120, 120, 2) - 0.20 * chip - 0.08 * sc[..., 3] + 0.03 * fbm(n, seed + 13, 20, 20, 3)
    return col, h

def tank_track(n=1024, seed=811):
    """dark manganese-steel track links: scuffed bright wear, rust and caked mud"""
    base = ramp(fbm(n, seed, 10, 10, 5), [(0, (0.035, 0.033, 0.03)), (0.6, (0.075, 0.07, 0.065)), (1, (0.12, 0.11, 0.10))])
    wear = smooth(fbm(n, seed + 1, 60, 60, 4), 0.55, 0.85)
    col = base * (1 - wear[..., None]) + np.array([0.20, 0.19, 0.18])[None, None, :] * wear[..., None]
    rustm = smooth(fbm(n, seed + 2, 9, 9, 5) + 0.3 * fbm(n, seed + 3, 50, 50, 3), 0.86, 1.02) * 0.55
    rust = ramp(fbm(n, seed + 4, 60, 60, 4), [(0, (0.07, 0.025, 0.012)), (0.5, (0.16, 0.06, 0.025)), (1, (0.26, 0.11, 0.04))])
    col = col * (1 - rustm[..., None]) + rust * rustm[..., None]
    mud = smooth(fbm(n, seed + 5, 5, 5, 5), 0.55, 0.8) * 0.85
    mc = np.array([0.13, 0.09, 0.055])[None, None, :] * (0.7 + 0.6 * fbm(n, seed + 6, 70, 70, 3)[..., None])
    col = col * (1 - mud[..., None]) + mc * mud[..., None]
    sc = scratches(n, seed + 7, 120, (0.25, 0.24, 0.22), (0.4, 0.38, 0.35))
    col = col * (1 - 0.3 * sc[..., 3:4]) + sc[..., :3] * 0.3 * sc[..., 3:4]
    h = 0.5 + 0.15 * wear * fbm(n, seed + 8, 80, 80, 2) + 0.25 * mud * fbm(n, seed + 9, 30, 30, 4) + 0.05 * fbm(n, seed + 10, 150, 150, 2)
    return col, h

def tank_steel(n=1024, seed=821):
    """gun / fittings steel: dark blued metal, oily smears, scratches, rust specks"""
    col = np.array([0.050, 0.052, 0.057])[None, None, :] * (0.75 + 0.5 * fbm(n, seed, 6, 6, 4)[..., None]) * (0.92 + 0.16 * fbm(n, seed + 1, 160, 160, 2)[..., None])
    oil = smooth(fbm(n, seed + 2, 4, 14, 4), 0.5, 0.8) * 0.5; col = col * (1 - 0.5 * oil[..., None])
    heat = smooth(fbm(n, seed + 3, 5, 5, 4), 0.62, 0.86) * 0.5
    col = col * (1 - heat[..., None]) + np.array([0.12, 0.085, 0.07])[None, None, :] * heat[..., None]
    rustm = smooth(fbm(n, seed + 4, 8, 8, 5) + 0.35 * fbm(n, seed + 5, 90, 90, 3), 0.9, 1.05) * 0.8
    rust = ramp(fbm(n, seed + 6, 60, 60, 4), [(0, (0.12, 0.04, 0.015)), (1, (0.38, 0.15, 0.05))])
    col = col * (1 - rustm[..., None]) + rust * rustm[..., None]
    sc = scratches(n, seed + 7, 220, (0.22, 0.22, 0.23), (0.42, 0.42, 0.43))
    col = col * (1 - 0.3 * sc[..., 3:4]) + sc[..., :3] * 0.3 * sc[..., 3:4]
    h = 0.55 + 0.05 * fbm(n, seed + 8, 140, 140, 3) + 0.15 * rustm - 0.08 * sc[..., 3]
    return col, h

def tank_rubber(n=1024, seed=831):
    """road-wheel tyres: sun-cracked black rubber under road dust"""
    col = np.array([0.032, 0.031, 0.030])[None, None, :] * (0.7 + 0.6 * fbm(n, seed, 8, 8, 4)[..., None])
    cr = scratches(n, seed + 1, 420, (0.0, 0.0, 0.0), (0.012, 0.012, 0.012)); crack = cr[..., 3] * smooth(fbm(n, seed + 2, 6, 6, 3), 0.3, 0.6)
    col = col * (1 - 0.8 * crack[..., None])
    dust = smooth(fbm(n, seed + 3, 9, 9, 5), 0.5, 0.88) * 0.45
    col = col * (1 - dust[..., None]) + np.array([0.30, 0.25, 0.17])[None, None, :] * 0.55 * dust[..., None]
    h = 0.55 - 0.25 * crack + 0.06 * fbm(n, seed + 4, 110, 110, 3)
    return col, h

if __name__ == '__main__' or True:
    SET = [('paint_dg', lambda: tank_paint(1024, 801, (0.40, 0.28, 0.115)), 2.0),
           ('paint_dg_dark', lambda: tank_paint(1024, 802, (0.26, 0.185, 0.08)), 2.0),
           ('track', lambda: tank_track(1024), 3.0), ('steel', lambda: tank_steel(1024), 2.0), ('rubber', lambda: tank_rubber(512), 2.0)]
    tiles = []
    for name, fn, st in SET:
        col, h = fn(); srgb = to_srgb(col); hn = (h - h.min()) / (h.max() - h.min() + 1e-9); nrm = normal_from_height(hn, st)
        save_rgb(OUT + name + '_c.jpg', srgb); save_rgb(OUT + name + '_n.jpg', nrm)
        k = srgb.shape[0] // 256; t = srgb.reshape(256, k, 256, k, 3).mean((1, 3)); tiles.append(np.tile(t, (2, 2, 1)))
        print(name, 'seam', seam(srgb), 'mean', np.round(srgb.mean((0, 1)), 2))
    tiles.append(tiles[0] * 0 + 0.5)
    rows = [np.concatenate(tiles[i:i + 3], 1) for i in range(0, 6, 3)]
    save_rgb(D + '/tank_tiles_preview.jpg', np.concatenate(rows, 0)[::-1])
    print('DONE')
