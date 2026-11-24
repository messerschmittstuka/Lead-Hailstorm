"""Standard multi-view renders for the asset feedback loop. Runs inside Blender (via the run.py watcher). Never writes outside the folder it is given."""
import bpy, math, os, time
from mathutils import Vector, Matrix

LENS = 70.0
SENSOR = 36.0
VIEWS = {                      # name: (azimuth deg around Z from the front, elevation deg)  az +90 = camera on the model's LEFT side
    'front': (0, 6), 'rear': (180, 6), 'left': (90, 6), 'right': (-90, 6), 'top': (0, 88),
    'q_front': (35, 24), 'q_rear': (215, 24),
}
PREFIX_HIDE = ('COL_', '_pl_', 'cage_')

def visible_meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith(PREFIX_HIDE) and not o.hide_render]

def collision_meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('COL_')]

def world_bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get(); lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        eo = o.evaluated_get(dg)
        for c in eo.bound_box:
            w = eo.matrix_world @ Vector(c)
            for i in range(3): lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return lo, hi

def _mat_grid(grid_m):
    m = bpy.data.materials.new('_pl_ground'); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    ck = nt.nodes.new('ShaderNodeTexChecker'); ck.inputs['Color1'].default_value = (0.34, 0.35, 0.37, 1); ck.inputs['Color2'].default_value = (0.27, 0.28, 0.30, 1)
    ck.inputs['Scale'].default_value = 1.0 / (2 * grid_m)
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], ck.inputs['Vector']); nt.links.new(ck.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.95
    return m

def _mat_clay():
    m = bpy.data.materials.new('_pl_clay'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.62, 0.62, 0.60, 1); b.inputs['Roughness'].default_value = 0.8; return m

class Rig:
    def __init__(self, lo, hi, grid_m, res):
        sc = bpy.context.scene; self.sc = sc; self.res = res
        self.center = (lo + hi) / 2; self.radius = max((hi - lo).length / 2, 0.05)
        try: sc.render.engine = 'BLENDER_EEVEE'
        except Exception: sc.render.engine = 'BLENDER_WORKBENCH'
        try: sc.eevee.taa_render_samples = 32
        except Exception: pass
        sc.render.film_transparent = False
        for vt in ('AgX', 'Filmic', 'Standard'):
            try: sc.view_settings.view_transform = vt; break
            except Exception: continue
        try: sc.view_settings.look = 'None'
        except Exception: pass
        sc.render.resolution_x = res; sc.render.resolution_y = res; sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
        w = bpy.data.worlds.new('_pl_w'); w.use_nodes = True; sc.world = w            # always a fresh, uniform world: the default sky texture lit every view differently
        nt = w.node_tree; nt.nodes.clear(); bg = nt.nodes.new('ShaderNodeBackground'); out = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        bg.inputs['Color'].default_value = (0.58, 0.62, 0.68, 1); bg.inputs['Strength'].default_value = 0.7
        cd = bpy.data.cameras.new('_pl_cam'); cd.lens = LENS; cd.sensor_width = SENSOR; cd.clip_start = 0.01; cd.clip_end = 500
        self.cam = bpy.data.objects.new('_pl_cam', cd); sc.collection.objects.link(self.cam); sc.camera = self.cam
        self.lights = []
        for nm, en, rot in (('_pl_key', 1.5, (-50, -30, 0)), ('_pl_fill', 0.35, (-12, 42, 0))):
            ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = en; ld.angle = 0.06
            lo_ = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo_); lo_.parent = self.cam
            lo_.rotation_euler = tuple(math.radians(a) for a in rot); self.lights.append(lo_)
        size = max(60 * self.radius, 4.0)
        bpy.ops.mesh.primitive_plane_add(size=size, location=(self.center.x, self.center.y, lo.z - 0.0008))
        self.ground = bpy.context.object; self.ground.name = '_pl_ground'; self.ground.data.materials.append(_mat_grid(grid_m))
        self.clay = _mat_clay()
        self.front = Vector((0, -1, 0))

    def set_front(self, axis):
        self.front = {'-Y': Vector((0, -1, 0)), '+Y': Vector((0, 1, 0)), '+X': Vector((1, 0, 0)), '-X': Vector((-1, 0, 0))}.get(axis, Vector((0, -1, 0)))

    def aim(self, az, el, target=None, dist=None):
        t = Vector(target) if target is not None else self.center
        d = dist if dist is not None else self.radius / math.sin(math.atan(SENSOR / 2 / LENS)) * 1.12
        f = Matrix.Rotation(math.radians(az), 3, 'Z') @ self.front
        e = math.radians(el); dirv = (f * math.cos(e) + Vector((0, 0, math.sin(e)))).normalized()
        self.cam.location = t + dirv * d
        self.cam.rotation_euler = (t - self.cam.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()

    def shot(self, path, mode='shaded'):
        """mode: shaded | clay (neutral grey material, shows form) | wire (clay + thin dark wireframe copies, shows topology)"""
        sc = self.sc; saved = []; dupes = []
        if mode in ('clay', 'wire'):
            for o in visible_meshes():                      # swap the materials on the real objects, restore afterwards
                saved.append((o, [m for m in o.data.materials])); n = len(o.data.materials)
                for i in range(max(n, 1)):
                    if n == 0: o.data.materials.append(self.clay)
                    else: o.data.materials[i] = self.clay
        if mode == 'wire':
            wm = bpy.data.materials.new('_pl_wire'); wm.use_nodes = True; wb = wm.node_tree.nodes['Principled BSDF']
            wb.inputs['Base Color'].default_value = (0.02, 0.04, 0.10, 1); wb.inputs['Roughness'].default_value = 1.0
            th = max(self.radius * 0.0045, 0.0004)
            for o, _ in saved:
                d = o.copy(); d.data = o.data.copy(); d.data.materials.clear(); d.data.materials.append(wm); d.name = '_pl_wire_' + o.name
                bpy.context.scene.collection.objects.link(d)
                md = d.modifiers.new('wf', 'WIREFRAME'); md.thickness = th; md.offset = 1.0; md.use_even_offset = True; md.use_replace = True; dupes.append(d)
        sc.render.filepath = path; bpy.ops.render.render(write_still=True)
        for d in dupes:
            me = d.data; bpy.data.objects.remove(d, do_unlink=True); bpy.data.meshes.remove(me)
        for o, mats in saved:
            for i, m in enumerate(mats):
                o.data.materials[i] = m
            while len(o.data.materials) > len(mats): o.data.materials.pop()

def render_all(outdir, spec, res=800):
    """shaded x7 standard views, clay x2, wire x1, plus the closeups named in spec['closeups']. returns the file list."""
    t0 = time.time(); os.makedirs(outdir, exist_ok=True)
    objs = visible_meshes(); lo, hi = world_bbox(objs)
    hidden = []
    for c in collision_meshes():                      # collision hulls are never part of the picture (they covered the model in the first renders)
        hidden.append((c, c.hide_render)); c.hide_render = True
    rig = Rig(lo, hi, spec.get('grid_m', 0.1), res); rig.set_front(spec.get('front_axis', '-Y')); files = []
    for name, (az, el) in VIEWS.items():
        rig.aim(az, el); p = os.path.join(outdir, name + '.png'); rig.shot(p); files.append(p)
    for name, (az, el) in (('clay_q_front', VIEWS['q_front']), ('clay_q_rear', VIEWS['q_rear'])):
        rig.aim(az, el); p = os.path.join(outdir, name + '.png'); rig.shot(p, 'clay'); files.append(p)
    rig.aim(*VIEWS['q_front']); p = os.path.join(outdir, 'wire_q_front.png'); rig.shot(p, 'wire'); files.append(p)
    for c in spec.get('closeups', []):
        rig.aim(c.get('az', 30), c.get('el', 20), c['target'], c.get('dist', 0.4)); p = os.path.join(outdir, 'close_' + c['name'] + '.png'); rig.shot(p); files.append(p)
    for o in (rig.cam, rig.ground, *rig.lights): bpy.data.objects.remove(o, do_unlink=True)
    for c, h in hidden: c.hide_render = h
    print('render_all: %d images in %.1fs' % (len(files), time.time() - t0))
    return files
