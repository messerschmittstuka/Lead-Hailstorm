#!/usr/bin/env python3
"""Control script for the asset feedback loop (plain python3, no Blender needed).
  loopctl.py new <asset> <class> [front_axis]   create models/assets/<asset>/ with spec templates
  loopctl.py next <asset>                       create the next version folder (copies the previous build.py)
  loopctl.py status <asset>                     versions, run states, triangle counts, open defects
  loopctl.py check <asset>                      stop rules: should another improvement cycle run?
  loopctl.py revisions <asset>                  regenerate revisions.md from every version's changes.md / review.json / stats.json
  loopctl.py report <asset>                     write report.md (final quality report)
  loopctl.py approve <asset> <version>          ONLY after the user approves: copy that version to approved/ and make it read-only
An approved asset is never modified: 'next' and 'approve' refuse once approved/ exists.  Max 5 improvement cycles (v1 + v2..v6)."""
import sys, os, json, shutil, stat, time, re, glob
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets'); ROOT = os.path.abspath(ROOT)
BUDGETS = {'rifle': ([3000, 6000], 10000), 'tank': ([15000, 30000], 45000), 'aircraft': ([20000, 40000], 60000), 'small_prop': ([500, 2000], 3000), 'large_prop': ([2000, 6000], 10000)}
MAX_CYCLES = 5

def adir(a): return os.path.join(ROOT, a)
def versions(a): return sorted([d for d in os.listdir(adir(a)) if re.fullmatch(r'v\d+', d)], key=lambda x: int(x[1:]))
def jl(p, default=None):
    return json.load(open(p)) if os.path.exists(p) else default
def approved(a): return os.path.exists(os.path.join(adir(a), 'approved', 'APPROVED'))

def new(a, cls, front='-Y'):
    if os.path.exists(adir(a)): sys.exit('asset already exists: ' + a)
    if cls not in BUDGETS: sys.exit('class must be one of ' + ', '.join(BUDGETS))
    t, m = BUDGETS[cls]; os.makedirs(os.path.join(adir(a), 'v1'))
    json.dump({'asset': a, 'class': cls, 'front_axis': front, 'grid_m': 0.1, 'budget': {'target': t, 'max': m}, 'budget_exception': None,
               'dims_m': {}, 'closeups': [], 'require_textured_materials': True, 'require_collision': True}, open(os.path.join(adir(a), 'spec.json'), 'w'), indent=1)
    open(os.path.join(adir(a), 'spec.md'), 'w').write('# %s - reference specification\n\nClass: %s. Budget %d-%d tris (max %d).\n\n## Sources\n\n## Dimensions\n\n## Features that must be present\n\n## Materials and finish\n\n## Deliberately omitted (not worth the triangles)\n\n## Proposed budget exceptions (need approval)\nnone\n' % (a, cls, t[0], t[1], m))
    print('created', adir(a))

def nxt(a):
    if approved(a): sys.exit('%s is approved; approved assets are never modified' % a)
    vs = versions(a); n = len(vs)
    if n >= MAX_CYCLES + 1: sys.exit('limit reached: %d improvement cycles already done' % MAX_CYCLES)
    last = vs[-1]; st = jl(os.path.join(adir(a), last, 'status.json'), {})
    if st.get('state') != 'done': sys.exit('%s has not finished a successful run yet' % last)
    d = os.path.join(adir(a), 'v%d' % (n + 1)); os.makedirs(d); shutil.copy(os.path.join(adir(a), last, 'build.py'), os.path.join(d, 'build.py'))
    open(os.path.join(d, 'changes.md'), 'w').write('# %s changes (from %s)\n\nDefects addressed: \n\n' % ('v%d' % (n + 1), last))
    print('created', d)

def defects(a, v):
    r = jl(os.path.join(adir(a), v, 'review.json'));
    return {d['id']: d for d in r['defects']} if r else None

def history(a):
    h = []
    for v in versions(a):
        st = jl(os.path.join(adir(a), v, 'stats.json'), {}); rv = defects(a, v); h.append({'v': v, 'tris': st.get('stats', {}).get('tris_total'), 'checks': st.get('checks', []), 'defects': rv})
    return h

def check(a):
    h = history(a); n = len(h) - 1; res = {'versions': len(h), 'improvement_cycles_done': n}
    cur = h[-1]
    if cur['defects'] is None: res.update(cont=None, reason='latest version %s has not been reviewed yet (needs review.json)' % cur['v']); return res
    open_now = [d for d in cur['defects'].values() if d.get('status', 'open') == 'open']; major = [d for d in open_now if d['severity'] == 'major']
    fails = [c for c in cur['checks'] if c['status'] == 'fail']
    flow = []
    for i in range(1, len(h)):
        if h[i]['defects'] is None or h[i - 1]['defects'] is None: continue
        p, c = set(h[i - 1]['defects']), set(h[i]['defects']); flow.append({'v': h[i]['v'], 'resolved': len(p - c), 'new': len(c - p), 'open': len(c)})
    res['flow'] = flow; res['open'] = len(open_now); res['open_major'] = len(major); res['failed_checks'] = len(fails)
    if not open_now and not fails: res.update(cont=False, reason='no open defects and no failed checks - ready for the user to review'); return res
    if n >= MAX_CYCLES: res.update(cont=False, reason='maximum of %d improvement cycles reached' % MAX_CYCLES); return res
    if len(flow) >= 2 and flow[-1]['resolved'] <= 1 and flow[-2]['resolved'] <= 1 and flow[-1]['open'] >= flow[-2]['open']:
        res.update(cont=False, reason='diminishing returns: the last two cycles resolved <=1 defect each and the open count did not fall'); return res
    if cur['tris'] and cur['tris'] > BUDGETS[jl(os.path.join(adir(a), 'spec.json'))['class']][1]: res.update(cont=False, reason='over the hard triangle limit - needs a budget decision'); return res
    res.update(cont=True, reason='%d open defects (%d major), %d failed checks' % (len(open_now), len(major), len(fails))); return res

def revisions(a):
    spec = jl(os.path.join(adir(a), 'spec.json')); out = ['# %s - revision history\n' % a, 'Generated by loopctl.py from each version folder. Versions are immutable once run.\n']
    prev = None
    for v in versions(a):
        d = os.path.join(adir(a), v); st = jl(d + '/status.json', {}); s = jl(d + '/stats.json', {}); rv = jl(d + '/review.json')
        out.append('\n## %s  (%s)\n' % (v, st.get('state', 'not run')))
        if s:
            t = s['stats']['tris_total']; dm = s['stats']['dims_m']
            out.append('- Triangles: %d%s;  size %.3f x %.3f x %.3f m;  collision %s tris;  texture memory %s MB' % (t, ('  (%+d vs %s)' % (t - prev, 'previous')) if prev is not None else '', dm['x'], dm['y'], dm['z'], sum(c['tris'] for c in s['stats']['collision']), s['stats']['texture_mem_mb']))
            cc = {k: sum(1 for c in s['checks'] if c['status'] == k) for k in ('pass', 'warn', 'fail')}; out.append('- Numeric checks: %d pass, %d warn, %d fail' % (cc['pass'], cc['warn'], cc['fail'])); prev = t
        if os.path.exists(d + '/changes.md'): out.append('\n**What changed and why**\n\n' + open(d + '/changes.md').read().split('\n', 1)[1].strip())
        if rv:
            out.append('\n**Review of this version** (verdict: %s)\n' % rv.get('verdict'))
            for x in rv['defects']: out.append('- %s [%s/%s] %s%s' % (x['id'], x['severity'], x['category'], x['text'], ('  -> fix: ' + x['fix']) if x.get('fix') else ''))
            if not rv['defects']: out.append('- no defects found')
    open(os.path.join(adir(a), 'revisions.md'), 'w').write('\n'.join(out) + '\n'); print('wrote revisions.md')

def report(a):
    revisions(a); spec = jl(os.path.join(adir(a), 'spec.json')); h = history(a); c = check(a); last = h[-1]
    out = ['# %s - final quality report\n' % a, 'Status: **awaiting user approval** (nothing exported, nothing integrated).\n', '- Versions built: %d (improvement cycles used: %d of %d)' % (len(h), len(h) - 1, MAX_CYCLES), '- Loop verdict: %s' % c.get('reason'),
           '- Final triangles: %s (budget %s-%s, max %s)' % (last['tris'], spec['budget']['target'][0], spec['budget']['target'][1], spec['budget']['max'])]
    out.append('\n## Triangle count by version\n'); out += ['- %s: %s' % (x['v'], x['tris']) for x in h]
    out.append('\n## Numeric checks (latest version)\n'); out += ['- [%s] %s: %s' % (x['status'].upper(), x['name'], x['detail']) for x in last['checks']]
    out.append('\n## Defect flow\n'); out += ['- %s: %d resolved, %d new, %d open' % (f['v'], f['resolved'], f['new'], f['open']) for f in c.get('flow', [])]
    if last['defects']:
        out.append('\n## Remaining open defects\n'); r = [d for d in last['defects'].values() if d.get('status', 'open') == 'open']; out += ['- %s [%s/%s] %s' % (d['id'], d['severity'], d['category'], d['text']) for d in r] or ['- none']
    open(os.path.join(adir(a), 'report.md'), 'w').write('\n'.join(out) + '\n'); print('wrote report.md')

def approve(a, v):
    if approved(a): sys.exit('already approved')
    src = os.path.join(adir(a), v); st = jl(src + '/status.json', {})
    if st.get('state') != 'done': sys.exit('version has not run successfully')
    dst = os.path.join(adir(a), 'approved'); shutil.copytree(src, dst)
    open(os.path.join(dst, 'APPROVED'), 'w').write('approved version %s at %s\n' % (v, time.strftime('%Y-%m-%d %H:%M:%S')))
    for r, ds, fs in os.walk(dst, topdown=False):
        for f in fs: os.chmod(os.path.join(r, f), stat.S_IREAD)
        for d in ds: os.chmod(os.path.join(r, d), stat.S_IREAD | stat.S_IEXEC)
    os.chmod(dst, stat.S_IREAD | stat.S_IEXEC); print('approved', a, v, '(read-only copy in approved/; nothing exported or integrated)')

def status(a):
    for x in history(a):
        st = jl(os.path.join(adir(a), x['v'], 'status.json'), {}); od = [d for d in (x['defects'] or {}).values() if d.get('status', 'open') == 'open']
        print('%-4s state=%-8s tris=%-6s defects_open=%s' % (x['v'], st.get('state', '-'), x['tris'], len(od) if x['defects'] is not None else 'not reviewed'))
    print('approved:', approved(a))

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit()
    c = a[0]
    {'new': lambda: new(a[1], a[2], *(a[3:4])), 'next': lambda: nxt(a[1]), 'status': lambda: status(a[1]), 'check': lambda: print(json.dumps(check(a[1]), indent=1)),
     'revisions': lambda: revisions(a[1]), 'report': lambda: report(a[1]), 'approve': lambda: approve(a[1], a[2])}[c]()
