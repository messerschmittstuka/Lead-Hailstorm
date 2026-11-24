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
def dark(fn, k):
    def g():
        c, h = fn(); return c * k, h
    return g
SET = [('bplaster_a', lambda: plaster_wall(1024, 701, (0.40, 0.34, 0.25), 601, 0.16), 3.0), ('bplaster_b', lambda: plaster_wall(1024, 702, (0.33, 0.29, 0.21), 602, 0.12), 3.0),
       ('bplaster_c', lambda: plaster_wall(1024, 703, (0.45, 0.41, 0.32), 603, 0.22), 3.0),
       ('bbrick_a', lambda: brick_wall(1024, 601), 4.0), ('bbrick_b', lambda: brick_wall(1024, 611), 4.0), ('bbrick_c', lambda: brick_wall(1024, 621), 4.0),
       ('bstone_a', lambda: concrete(1024, 631, (0.22, 0.21, 0.19)), 3.5), ('bstone_b', lambda: concrete(1024, 641, (0.17, 0.165, 0.15)), 3.5),
       ('bplinth', lambda: concrete(1024, 651, (0.10, 0.095, 0.09)), 3.5), ('bcap', lambda: concrete(1024, 661, (0.26, 0.25, 0.23)), 3.0),
       ('bconc', lambda: concrete(1024, 621), 3.5), ('btile', lambda: roof_tile(1024, 711), 4.0), ('btar', lambda: roof_tar(1024, 721), 3.0),
       ('bchar', lambda: concrete(1024, 671, (0.025, 0.023, 0.022)), 3.5), ('bfloor', dark(lambda: planks(1024, 681, 8), 0.6), 3.5),
       ('bshut', lambda: planks(1024, 691, 4, (0.045, 0.085, 0.055)), 3.5), ('bwood', lambda: planks(1024, 631), 4.0), ('bdwood', dark(lambda: planks(1024, 641, 5), 0.45), 4.0),
       ('brub_a', lambda: concrete(1024, 731, (0.14, 0.135, 0.125)), 4.0), ('brub_b', lambda: plaster_wall(1024, 732, (0.36, 0.31, 0.23), 604, 0.4), 4.0), ('brub_c', lambda: brick_solid(1024, 733), 3.0)]
tiles = []
for name, fn, st in SET:
    col, h = fn(); srgb = to_srgb(col); hn = (h - h.min()) / (h.max() - h.min() + 1e-9); nrm = normal_from_height(hn, st)
    save_rgb(OUT + name + '_c.jpg', srgb); save_rgb(OUT + name + '_n.jpg', nrm)
    k = srgb.shape[0] // 128; t = srgb.reshape(128, k, 128, k, 3).mean((1, 3)); tiles.append(np.tile(t, (2, 2, 1)) if False else t)
    print(name, np.round(srgb.mean((0, 1)), 2))
while len(tiles) % 7: tiles.append(np.zeros((128, 128, 3)))
rows = [np.concatenate(tiles[i:i + 7], 1) for i in range(0, len(tiles), 7)]
save_rgb(D + '/bld_tiles_preview.jpg', np.concatenate(rows, 0)[::-1])
print('DONE')
