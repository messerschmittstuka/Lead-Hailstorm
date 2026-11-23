import bpy, sys, os, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
def save_rgb(path, arr):
    h, w = arr.shape[:2]; im = bpy.data.images.new('t', w, h, alpha=False); im.colorspace_settings.name = 'sRGB'
    a4 = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], 2).astype(np.float32); im.pixels.foreach_set(a4.ravel())
    im.filepath_raw = path; im.file_format = 'JPEG'; im.save(); bpy.data.images.remove(im)
n = 512; h = water_height(n); nrm = normal_from_height(h, 2.2); col = water_colour(n, h)
save_rgb(D + '/textures/water_n.jpg', nrm); save_rgb(D + '/textures/water_c.jpg', col)
def seam(a): return round(float(np.abs(a[:, 0] - a[:, -1]).mean() / (np.abs(a[:, 5] - a[:, 6]).mean() + 1e-9)), 2), round(float(np.abs(a[0] - a[-1]).mean() / (np.abs(a[5] - a[6]).mean() + 1e-9)), 2)
print('seam ratios normal', seam(nrm), 'colour', seam(col))
# preview: colour and a fake-lit normal map, each tiled 2x2 so seams would show
nv = nrm * 2 - 1; L = np.array([0.4, 0.3, 0.86]); L /= np.linalg.norm(L)
shade = np.clip(0.55 + 0.9 * (nv @ L - L[2]) + 0.35, 0.15, 1.3)[..., None]
lit = shade * np.array([0.30, 0.38, 0.33]) * 1.6 * col * 1.2
sheet = np.concatenate([np.tile(col, (2, 2, 1)), np.tile(np.clip(lit, 0, 1), (2, 2, 1))], 1)
save_rgb(D + '/water_tiles_preview.jpg', sheet[::-1][::2, ::2] if False else sheet[::-1])
print('DONE')
