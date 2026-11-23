import bpy, sys, os, time, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/veg/'
def save(name, arr, srgb=True, jpg=None):
    jpg = (arr.shape[2] == 3) if jpg is None else jpg
    h, w = arr.shape[:2]
    if arr.shape[2] == 3: arr = np.concatenate([arr, np.ones((h, w, 1))], 2)
    img = bpy.data.images.new(name, w, h, alpha=True); img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    px = arr.copy()
    if srgb: px[..., :3] = to_srgb(px[..., :3])
    img.pixels.foreach_set(px.astype(np.float32).ravel()); img.filepath_raw = OUT + name + ('.jpg' if jpg else '.png'); img.file_format = 'JPEG' if jpg else 'PNG'
    if jpg: img.save(quality=90) if False else None
    img.save()
    bpy.data.images.remove(img)
t0 = time.time()
for kind in ('dead', 'charred', 'spruce'):
    c, h = bark(1024, {'dead': 11, 'charred': 21, 'spruce': 31}[kind], kind)
    save('bark_' + kind + '_c', c); save('bark_' + kind + '_n', normal_from_height(h, 4.0), False); print(kind, time.time() - t0)
c, h = wood_end(1024, 3, 32); save('endgrain_c', c); save('endgrain_n', normal_from_height(h, 3.0), False)
c, h = wood_end(1024, 8, 24, True, True); save('endgrain_charred_c', c); save('endgrain_charred_n', normal_from_height(h, 3.0), False)
c, h = wood_fibre(512); save('fibre_c', c); save('fibre_n', normal_from_height(h, 4.0), False); print('wood', time.time() - t0)
save('grass_a', grass_card(1024, 1024, 1, 70)); save('grass_b', grass_card(1024, 1024, 2, 45, 0.7, 1.0, 0.25, 6.0)); print('grass', time.time() - t0)
save('reed', reed_card()); print('reed', time.time() - t0)
save('spruce_branch', spruce_card(1024, 512, 2)); print('spruce', time.time() - t0)
print('DONE')
