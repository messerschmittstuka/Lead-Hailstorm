# shared by the Wehrmacht soldier rig/anim/export scripts (runs inside Blender via watch.py)
import bpy, bmesh, math, mathutils
from mathutils import Vector, Matrix, Quaternion, Euler
# bones: name -> (parent, head, tail). Armature space: Z up, soldier faces -Y, his left is +X
def L(v): return (v[0],v[1],v[2])
def mirror(v): return (-v[0],v[1],v[2])
BONES={}
def add(n,p,h,t): BONES[n]=(p,h,t)
add('Hips',None,(0,0.02,0.93),(0,0.02,1.03))
add('Spine','Hips',(0,0.02,1.03),(0,0.02,1.19))
add('Spine1','Spine',(0,0.02,1.19),(0,0.02,1.34))
add('Spine2','Spine1',(0,0.02,1.34),(0,0.02,1.47))
add('Neck','Spine2',(0,0.02,1.47),(0,0.01,1.56))
add('Head','Neck',(0,0.01,1.56),(0,0.01,1.80))
for sd,sg in (('Left',1),('Right',-1)):
    X=lambda v:(v[0]*sg,v[1],v[2])
    add(sd+'Shoulder','Spine2',X((0.05,0.03,1.45)),X((0.20,0.055,1.38)))
    add(sd+'Arm',sd+'Shoulder',X((0.20,0.055,1.38)),X((0.385,0.07,1.155)))
    add(sd+'ForeArm',sd+'Arm',X((0.385,0.07,1.155)),X((0.52,-0.04,1.03)))
    add(sd+'Hand',sd+'ForeArm',X((0.52,-0.04,1.03)),X((0.66,-0.08,0.87)))
    add(sd+'UpLeg','Hips',X((0.115,0.0,0.93)),X((0.14,-0.015,0.545)))
    add(sd+'Leg',sd+'UpLeg',X((0.14,-0.015,0.545)),X((0.16,0.055,0.14)))
    add(sd+'Foot',sd+'Leg',X((0.16,0.055,0.14)),X((0.16,-0.19,0.05)))
add('Weapon','Spine2',(0.0,-0.20,1.22),(0.0,-0.45,1.26))
SIDE={n:(1 if n.startswith('Left') else -1 if n.startswith('Right') else 0) for n in BONES}
def build_armature(sc):
    ad=bpy.data.armatures.new('Armature'); ob=bpy.data.objects.new('Armature',ad); sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active=ob
    with bpy.context.temp_override(active_object=ob,object=ob):
        bpy.ops.object.mode_set(mode='EDIT')
        eb=ad.edit_bones
        for n,(p,h,t) in BONES.items():
            b=eb.new(n); b.head=Vector(h); b.tail=Vector(t); b.roll=0
        for n,(p,h,t) in BONES.items():
            if p: eb[n].parent=eb[p]
        bpy.ops.object.mode_set(mode='OBJECT')
    return ob
def seg_dist(p,a,b):
    ab=b-a; t=max(0.0,min(1.0,(p-a).dot(ab)/max(ab.length_squared,1e-9))); return (p-(a+ab*t)).length
def weight_mesh(o,arm):
    for n in BONES:
        if n!='Weapon' and n not in o.vertex_groups: o.vertex_groups.new(name=n)
    segs={n:(Vector(h),Vector(t)) for n,(p,h,t) in BONES.items() if n!='Weapon'}
    for v in o.data.vertices:
        p=o.matrix_world@v.co; c=[]
        for n,(a,b) in segs.items():
            s=SIDE[n]
            if s==1 and p.x<-0.03: continue
            if s==-1 and p.x>0.03: continue
            d=seg_dist(p,a,b)
            c.append((d,n))
        c.sort(); c=c[:3]
        ws=[(1.0/(d+0.02))**3 for d,n in c]; tot=sum(ws)
        for (d,n),w in zip(c,ws):
            if w/tot>0.04: o.vertex_groups[n].add([v.index],w/tot,'REPLACE')
def rest3(arm,name):
    b=arm.data.bones[name]; return b.matrix_local.to_3x3()
def set_rot(arm,name,euler_xyz):
    """rotate bone 'name' by an Euler (X,Y,Z radians, armature axes, applied X then Y then Z) relative to its parent frame"""
    pb=arm.pose.bones[name]; B=rest3(arm,name); R=Euler(euler_xyz,'XYZ').to_matrix()
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=(B.inverted()@R@B).to_quaternion()
def set_loc(arm,name,vec):
    pb=arm.pose.bones[name]; B=rest3(arm,name); pb.location=B.inverted()@Vector(vec)
