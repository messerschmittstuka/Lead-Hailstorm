import bpy, sys, os, time, numpy as np, importlib
D = '/Users/justinho/Documents/GitHub/Lead-Hailstorm/models'
sys.path.insert(0, D)
import texlib; importlib.reload(texlib)
from texlib import *
OUT = D + '/textures/veg/'
def save(name, arr):
    h, w = arr.shape[:2]; img = bpy.data.images.new(name, w, h, alpha=True); img.colorspace_settings.name = 'sRGB'
    px = arr.copy(); px[..., :3] = to_srgb(px[..., :3]); img.pixels.foreach_set(px.astype(np.float32).ravel())
    img.filepath_raw = OUT + name + '.png'; img.file_format = 'PNG'; img.save(); bpy.data.images.remove(img)
t0 = time.time()
save('grass_green_a', grass_card(1024, 1024, 11, 80, 0.45, 0.95, 0.33, 7.0, GREEN_PAL)); save('grass_green_b', grass_card(1024, 1024, 12, 55, 0.7, 1.0, 0.26, 6.0, GREEN_PAL[:5]))
print('grass', time.time() - t0)
save('meadow', meadow_card()); print('meadow', time.time() - t0)
save('fern', fern_card()); print('fern', time.time() - t0)
save('leafy_a', leafy_card(1024, 512, 6)); save('leafy_b', leafy_card(1024, 512, 9)); print('leafy', time.time() - t0)
print('DONE')
