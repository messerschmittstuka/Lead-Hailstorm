import bpy, sys, os, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/prop/'; os.makedirs(OUT, exist_ok=True)
def save_rgb(path, arr):
    h, w = arr.shape[:2]; im = bpy.data.images.new('t', w, h, alpha=False); im.colorspace_settings.name = 'sRGB'
    a4 = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], 2).astype(np.float32); im.pixels.foreach_set(a4.ravel())
    im.filepath_raw = path; im.file_format = 'JPEG'; im.save(); bpy.data.images.remove(im)
def seam(a): return round(float(np.abs(a[:, 0] - a[:, -1]).mean() / (np.abs(a[:, 5] - a[:, 6]).mean() + 1e-9)), 2), round(float(np.abs(a[0] - a[-1]).mean() / (np.abs(a[5] - a[6]).mean() + 1e-9)), 2)
SET = [('brick', lambda: brick_wall(1024), 4.0), ('brick_solid', lambda: brick_solid(512), 3.0), ('concrete', lambda: concrete(1024), 4.0),
       ('plaster', lambda: concrete(1024, 622, (0.34, 0.31, 0.26)), 3.0), ('planks', lambda: planks(1024), 4.0),
       ('planks_olive', lambda: planks(1024, 632, 5, (0.13, 0.15, 0.07)), 4.0), ('metal_olive', lambda: metal_paint(1024, 641, (0.055, 0.066, 0.03)), 1.5),
       ('metal_grey', lambda: metal_paint(1024, 642, (0.07, 0.075, 0.08)), 1.5), ('burlap', lambda: burlap(1024), 2.0)]
tiles = []
for name, fn, st in SET:
    col, h = fn(); srgb = to_srgb(col); hn = (h - h.min()) / (h.max() - h.min() + 1e-9); nrm = normal_from_height(hn, st)
    save_rgb(OUT + name + '_c.jpg', srgb); save_rgb(OUT + name + '_n.jpg', nrm)
    k = srgb.shape[0] // 256; t = srgb.reshape(256, k, 256, k, 3).mean((1, 3)); tiles.append(np.tile(t, (2, 2, 1)))
    print(name, 'seam', seam(srgb), 'mean', np.round(srgb.mean((0, 1)), 2))
rows = [np.concatenate(tiles[i:i + 3], 1) for i in range(0, 9, 3)]
save_rgb(D + '/prop_tiles_preview.jpg', np.concatenate(rows, 0)[::-1])
print('DONE')
