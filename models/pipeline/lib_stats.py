"""Numeric model inspection for the asset feedback loop (runs inside Blender): triangles, dimensions, materials, mesh hygiene, and pass/warn/fail checks against spec.json."""
import bpy, bmesh, math
from mathutils import Vector
import lib_render as R

def measure():
    dg = bpy.context.evaluated_depsgraph_get(); per = []; tot = 0; loose = 0; open_e = 0; zero = 0; no_uv = []
    mats = {}; imgs = {}
    for o in R.visible_meshes():
        eo = o.evaluated_get(dg); me = eo.to_mesh(); me.calc_loop_triangles(); n = len(me.loop_triangles); tot += n
        bm = bmesh.new(); bm.from_mesh(me)
        lv = sum(1 for v in bm.verts if not v.link_faces); oe = sum(1 for e in bm.edges if not e.is_manifold); zf = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
        bm.free(); loose += lv; open_e += oe; zero += zf
        if not me.uv_layers: no_uv.append(o.name)
        per.append({'object': o.name, 'tris': n, 'verts': len(me.vertices), 'materials': [m.name if m else None for m in o.data.materials]})
        eo.to_mesh_clear()
        for m in o.data.materials:
            if not m or m.name in mats: continue
            tex = []
            if m.use_nodes:
                for nd in m.node_tree.nodes:
                    if nd.type == 'TEX_IMAGE' and nd.image:
                        tex.append({'image': nd.image.name, 'size': list(nd.image.size)}); imgs[nd.image.name] = tuple(nd.image.size)
            mats[m.name] = {'textured': bool(tex), 'images': tex}
    lo, hi = R.world_bbox(R.visible_meshes()); size = hi - lo
    col = []
    for o in R.collision_meshes():
        eo = o.evaluated_get(dg); me = eo.to_mesh(); me.calc_loop_triangles(); bm = bmesh.new(); bm.from_mesh(me)
        col.append({'object': o.name, 'tris': len(me.loop_triangles), 'closed': all(e.is_manifold for e in bm.edges)}); bm.free(); eo.to_mesh_clear()
    mem = sum(w * h * 4 * 1.33 for (w, h) in imgs.values()) / 1048576.0
    return {'tris_total': tot, 'objects': per, 'dims_m': {'x': round(size.x, 4), 'y': round(size.y, 4), 'z': round(size.z, 4)},
            'bbox_min': [round(c, 4) for c in lo], 'bbox_max': [round(c, 4) for c in hi],
            'materials': mats, 'flat_materials': [k for k, v in mats.items() if not v['textured']], 'texture_mem_mb': round(mem, 2),
            'loose_verts': loose, 'open_edges': open_e, 'zero_area_faces': zero, 'objects_without_uv': no_uv, 'collision': col}

def evaluate(stats, spec):
    """returns a list of {name, status, detail}; status is pass | warn | fail"""
    out = []
    def add(n, s, d): out.append({'name': n, 'status': s, 'detail': d})
    b = spec.get('budget', {}); t = stats['tris_total']
    if b:
        lo, hi = b['target']; mx = b['max']
        add('triangle budget', 'fail' if t > mx else ('pass' if lo <= t <= hi else 'warn'),
            '%d tris (target %d-%d, max %d)%s' % (t, lo, hi, mx, '' if lo <= t <= hi or t > mx else ('  below target: fine only if the real object is simple' if t < lo else '  above target but under max: needs justification')))
    for ax in 'xyz':
        d = spec.get('dims_m', {}).get(ax)
        if d:
            v = stats['dims_m'][ax]; ok = abs(v - d[0]) <= d[1]
            add('dimension ' + ax, 'pass' if ok else ('warn' if abs(v - d[0]) <= 2 * d[1] else 'fail'), '%.3f m (spec %.3f +-%.3f m)' % (v, d[0], d[1]))
    if spec.get('require_textured_materials', True):
        fl = stats['flat_materials']; add('materials textured', 'pass' if not fl else 'fail', 'all materials use image textures' if not fl else 'flat-colour materials: ' + ', '.join(fl))
    add('uv maps', 'pass' if not stats['objects_without_uv'] else 'fail', 'all meshes have UVs' if not stats['objects_without_uv'] else 'no UVs: ' + ', '.join(stats['objects_without_uv']))
    add('loose geometry', 'pass' if stats['loose_verts'] == 0 else 'warn', '%d loose vertices' % stats['loose_verts'])
    add('zero-area faces', 'pass' if stats['zero_area_faces'] == 0 else 'warn', '%d' % stats['zero_area_faces'])
    if spec.get('require_closed_surface', False): add('closed surface', 'pass' if stats['open_edges'] == 0 else 'warn', '%d open/non-manifold edges' % stats['open_edges'])
    zmin = stats['bbox_min'][2]
    if spec.get('origin_at_bore'): add('origin', 'pass', 'weapon origin on the bore axis by game contract (lowest point z = %.3f m)' % zmin)
    else: add('sits on ground (z=0)', 'pass' if abs(zmin) <= 0.01 else 'warn', 'lowest point z = %.3f m' % zmin)
    if spec.get('require_collision', True):
        c = stats['collision']; bad = [x['object'] for x in c if not x['closed']]
        add('collision hull', 'fail' if not c else ('pass' if not bad else 'fail'), 'none found' if not c else ('closed, %d tris' % sum(x['tris'] for x in c) if not bad else 'open: ' + ', '.join(bad)))
    add('texture memory', 'pass' if stats['texture_mem_mb'] <= spec.get('texture_mem_mb_max', 16) else 'warn', '%.1f MB (mips included)' % stats['texture_mem_mb'])
    return out
