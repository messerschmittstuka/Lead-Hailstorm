"""reed card texture (512 x 1536 RGBA): four straw culms, strap leaves arching from the nodes, feathery drooping plumes. Written for loop v2; PIL + numpy only."""
import random, math, sys
from PIL import Image, ImageDraw
W, H, S = 512, 1536, 2
img = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img); rnd = random.Random(11)
def quad(p0, p1, p2, n=36):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]
def blade(base, ctrl, tip, w0, col, rib):
    pts = quad(base, ctrl, tip); L = []; R = []; n = len(pts) - 1
    for i, (x, y) in enumerate(pts):
        a = pts[min(i + 1, n)]; b = pts[max(i - 1, 0)]; dx, dy = a[0] - b[0], a[1] - b[1]; ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln; t = i / n; w = w0 * (1 - t) ** 0.7 * (0.55 + 0.45 * min(1, t * 6))
        L.append((x + nx * w, y + ny * w)); R.append((x - nx * w, y - ny * w))
    d.polygon(L + R[::-1], fill=col); d.line(pts[:int(n * 0.9)], fill=rib, width=max(2, int(w0 * 0.16)))
culms = [(150, 118), (232, 70), (306, 150), (386, 104)]
for ci, (cx, top) in enumerate(culms):
    cx *= S; topy = top * S; bot = H * S
    sway = rnd.uniform(-26, 26) * S
    pts = quad((cx, bot), (cx + sway, (bot + topy) / 2), (cx + sway * 1.4, topy), 40)
    d.line(pts, fill=(182, 164, 108, 255), width=9 * S)
    for k in range(1, 6):                                                          # nodes
        y = bot - k * 250 * S; t = (bot - y) / (bot - topy)
        if t >= 0.96: continue
        px = cx + sway * 1.4 * t * t
        d.ellipse((px - 7 * S, y - 5 * S, px + 7 * S, y + 5 * S), fill=(150, 128, 80, 255))
        side = 1 if (k + ci) % 2 == 0 else -1
        tipx = px + side * rnd.uniform(170, 250) * S; tipy = y - rnd.uniform(60, 190) * S
        ctrl = (px + side * rnd.uniform(60, 120) * S, y - rnd.uniform(330, 470) * S)
        col = rnd.choice([(168, 152, 96, 255), (150, 142, 86, 255), (128, 132, 74, 255), (176, 158, 104, 255)])
        blade((px, y), ctrl, (tipx, tipy), rnd.uniform(26, 34) * S, col, (205, 190, 140, 255))
    tx, ty = pts[-1]                                                               # plume: many fine drooping strands
    for s in range(110):
        ang = math.radians(rnd.uniform(-78, 60)); L = rnd.uniform(110, 270) * S; dx = math.sin(ang) * L * 0.8; dy = abs(math.cos(ang)) * L
        p0 = (tx + rnd.uniform(-3, 3) * S, ty + rnd.uniform(0, 40) * S); p2 = (p0[0] + dx, p0[1] + dy)
        p1 = (p0[0] + dx * 0.15, p0[1] - rnd.uniform(0, 26) * S)
        c = rnd.choice([(118, 90, 96, 255), (140, 108, 104, 255), (170, 142, 118, 255), (190, 166, 132, 255)])
        d.line(quad(p0, p1, p2, 14), fill=c, width=rnd.choice([2, 3]) * S)
img = img.resize((W, H), Image.LANCZOS); img.save(sys.argv[1]); print('wrote', sys.argv[1], img.size)
