"""Driver for one asset version. run.py just calls  lib_loop.run('<asset>', 'v<N>')  and the watcher executes it.
Contract for  assets/<asset>/<version>/build.py : build the model into the (empty) scene. Visible parts = any mesh not named COL_* ; collision hull = COL_* mesh(es).
The script is exec'd with  ASSET, VERSION, OUT (the version folder), SPEC (parsed spec.json). It must never write outside OUT."""
import bpy, os, sys, json, time, traceback, importlib, hashlib
D = os.path.expanduser('~/Documents/GitHub/Lead-Hailstorm/models'); P = D + '/pipeline'; ROOT = D + '/assets'
for p in (P, D):
    if p not in sys.path: sys.path.insert(0, p)
import lib_render, lib_stats
importlib.reload(lib_render); importlib.reload(lib_stats)

BUDGETS = {'rifle': ([3000, 6000], 10000), 'tank': ([15000, 30000], 45000), 'aircraft': ([20000, 40000], 60000),
           'small_prop': ([500, 2000], 3000), 'large_prop': ([2000, 6000], 10000)}

def _w(path, data):
    guard(path); open(path, 'w').write(data if isinstance(data, str) else json.dumps(data, indent=1))

def guard(path):
    """no write is ever allowed into an approved folder"""
    parts = os.path.realpath(path).split(os.sep)
    if 'assets' in parts and 'approved' in parts[parts.index('assets') + 1:]: raise PermissionError('refusing to write into an approved asset folder: ' + path)

def clear_scene():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights, bpy.data.cameras, bpy.data.curves):
        for b in list(blk):
            if b.users == 0: blk.remove(b)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)

def run(asset, version, res=800, render=True, force=False):
    vdir = os.path.join(ROOT, asset, version); adir = os.path.join(ROOT, asset)
    st = os.path.join(vdir, 'status.json'); t0 = time.time()
    sha = hashlib.sha256(open(os.path.join(vdir, 'build.py'), 'rb').read()).hexdigest()[:16]; prior = json.load(open(st)) if os.path.exists(st) else {}
    if prior.get('state') == 'done':
        if not force: raise RuntimeError('%s/%s already finished; versions are immutable - create the next one' % (asset, version))
        if prior.get('build_sha') not in (None, sha): raise RuntimeError('build.py changed since this version ran; make a new version instead')
        if os.path.isdir(vdir + '/renders'): os.rename(vdir + '/renders', vdir + '/renders_superseded_' + time.strftime('%H%M%S'))     # keep the old images; only the renderer was fixed
    spec = json.load(open(os.path.join(adir, 'spec.json')))
    _w(st, {'state': 'running', 'asset': asset, 'version': version, 'started': time.strftime('%Y-%m-%d %H:%M:%S')})
    try:
        clear_scene()
        ns = {'__name__': 'build', 'ASSET': asset, 'VERSION': version, 'OUT': vdir, 'SPEC': spec}
        src = open(os.path.join(vdir, 'build.py')).read(); exec(compile(src, os.path.join(vdir, 'build.py'), 'exec'), ns)
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(vdir, 'model.blend'), copy=True)
        stats = lib_stats.measure(); checks = lib_stats.evaluate(stats, spec)
        _w(os.path.join(vdir, 'stats.json'), {'stats': stats, 'checks': checks})
        files = lib_render.render_all(os.path.join(vdir, 'renders'), spec, res) if render else []
        for m in list(bpy.data.materials):
            if m.name.startswith('_pl_'): bpy.data.materials.remove(m)
        _w(st, {'state': 'done', 'asset': asset, 'version': version, 'build_sha': sha, 'rerendered_with_fixed_harness': bool(force), 'seconds': round(time.time() - t0, 1), 'tris': stats['tris_total'],
                'renders': [os.path.relpath(f, vdir) for f in files], 'checks': {s: sum(1 for c in checks if c['status'] == s) for s in ('pass', 'warn', 'fail')}})
        print('RUN OK %s/%s  %d tris  %d images  %.1fs' % (asset, version, stats['tris_total'], len(files), time.time() - t0))
        for c in checks: print('  [%s] %s: %s' % (c['status'].upper(), c['name'], c['detail']))
    except Exception:
        tb = traceback.format_exc(); _w(st, {'state': 'error', 'asset': asset, 'version': version, 'traceback': tb}); print('RUN FAILED\n' + tb)
