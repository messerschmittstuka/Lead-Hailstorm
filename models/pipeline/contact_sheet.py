#!/usr/bin/env python3
"""Make labelled contact sheets from a version's renders so Claude can look at them with the Read tool (runs on the Claude side after the PNGs are staged).
usage: contact_sheet.py <renders_dir> <out_prefix> [cell_px]   ->  <out_prefix>_views.png (7 shaded views), <out_prefix>_forms.png (clay+wire), <out_prefix>_close.png (closeups, if any)"""
import sys, os, glob
from PIL import Image, ImageDraw
d, out = sys.argv[1], sys.argv[2]; cell = int(sys.argv[3]) if len(sys.argv) > 3 else 640
def sheet(names, path, cols):
    ims = [(n, os.path.join(d, n + '.png')) for n in names if os.path.exists(os.path.join(d, n + '.png'))]
    if not ims: return
    rows = (len(ims) + cols - 1) // cols; S = Image.new('RGB', (cols * cell, rows * cell), (20, 20, 20))
    for i, (n, p) in enumerate(ims):
        im = Image.open(p).convert('RGB').resize((cell, cell), Image.LANCZOS); dr = ImageDraw.Draw(im); dr.rectangle((0, 0, 150, 20), fill=(0, 0, 0)); dr.text((5, 4), n, fill=(255, 255, 255)); S.paste(im, ((i % cols) * cell, (i // cols) * cell))
    S.save(path); print('wrote', path, S.size)
sheet(['front', 'rear', 'left', 'right', 'top', 'q_front', 'q_rear'], out + '_views.png', 4)
sheet(['clay_q_front', 'clay_q_rear', 'wire_q_front'], out + '_forms.png', 3)
sheet([os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(d, 'close_*.png')))], out + '_close.png', 2)
