import bpy, sys, os, time, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/'; OLD = OUT + '_old/'
def load_px(path):
    im = bpy.data.images.load(path); w, h = im.size; a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]; bpy.data.images.remove(im); return a
def save_rgb(path, arr, jpg=True):
    h, w = arr.shape[:2]; im = bpy.data.images.new('t', w, h, alpha=False); im.colorspace_settings.name = 'sRGB'
    a4 = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], 2).astype(np.float32); im.pixels.foreach_set(a4.ravel())
    im.filepath_raw = path; im.file_format = 'JPEG'; im.save(); bpy.data.images.remove(im)
def down(a, k): h, w = a.shape[:2]; return a.reshape(h // k, k, w // k, k, -1).mean((1, 3))
def seam(a):
    c = np.abs(a[:, 0] - a[:, -1]).mean(); r = np.abs(a[:, 5] - a[:, 6]).mean(); d = np.abs(a[0] - a[-1]).mean(); q = np.abs(a[5] - a[6]).mean()
    return c / (r + 1e-9), d / (q + 1e-9)
t0 = time.time(); tiles = {}
for name, fn in (('grass', ground_grass), ('trampled', ground_trampled), ('mud', ground_mud), ('dirt', ground_dirt), ('stone', ground_stone)):
    col, h = fn(1024)
    srgb = to_srgb(col)
    old = load_px(OLD + 'game_%s.jpg' % name); gain = np.clip(old.mean((0, 1)) / (srgb.mean((0, 1)) + 1e-6), 0.35, 1.6)      # keep the map's overall tone as it was
    srgb = np.clip(srgb * gain, 0, 1)
    nrm = normal_from_height((h - h.min()) / (h.max() - h.min() + 1e-9), 5.0)
    save_rgb(OUT + 'ground_%s.jpg' % name, srgb); save_rgb(OUT + 'ground_%s_n.jpg' % name, nrm); save_rgb(OUT + 'game_%s_512.jpg' % name, down(srgb, 2))
    tiles[name] = down(srgb, 4); print(name, 'gain', np.round(gain, 2), 'seam ratio (x,y) ~1 means invisible:', np.round(seam(srgb), 2), round(time.time() - t0, 1), 's')
sheet = np.zeros((512 * 2, 512 * 3, 3))
for i, (nm, t) in enumerate(tiles.items()):
    r, c = divmod(i, 3); sheet[r * 512:(r + 1) * 512, c * 512:(c + 1) * 512] = np.tile(t, (2, 2, 1))     # each texture repeated 2x2: any seam would show as a line
save_rgb(D + '/ground_tiles_preview.jpg', sheet[::-1])
print('DONE')
