# pure-python FK/IK for the Wehrmacht rig: computes every bone's pose from joint targets, then writes quaternions (no depsgraph reads)
import bpy, math
from mathutils import Vector, Matrix, Quaternion, Euler
import rig_lib
BONES=rig_lib.BONES
ORDER=list(BONES.keys())   # parents always precede children
REST={}
def init_rest(arm):
    for n,(p,h,t) in BONES.items():
        b=arm.data.bones[n]; REST[n]={'R':b.matrix_local.to_3x3().copy(),'H':b.head_local.copy(),'T':b.tail_local.copy(),'len':(b.tail_local-b.head_local).length,'p':p}
class Pose:
    def __init__(s): s.R={}; s.H={}; s.hips_delta=Vector((0,0,0))
    def frame(s,n):   # the bone's frame before its own pose, inherited from its parent
        r=REST[n]; p=r['p']
        if p is None: return REST[n]['R'].copy(), REST[n]['H']+s.hips_delta
        rp=REST[p]; M=s.R[p]@rp['R'].inverted()
        return M@r['R'], s.H[p]+M@(r['H']-rp['H'])
    def rotate(s,n,euler):     # euler (x,y,z) in armature axes, relative to the parent frame
        r=REST[n]; p=r['p']; Rpf,H=s.frame(n)
        # Rpf = Rp_final Rp_rest^-1 Rrest ; rotation in armature axes acts on the left of Rpf
        s.R[n]=Euler(euler,'XYZ').to_matrix()@Rpf; s.H[n]=H
    def aim(s,n,d,roll_up=None):   # point the bone's Y axis along armature-space direction d
        Rpf,H=s.frame(n); cur=(Rpf@Vector((0,1,0))).normalized(); d=Vector(d).normalized()
        s.R[n]=cur.rotation_difference(d).to_matrix()@Rpf; s.H[n]=H
    def keep(s,n):
        Rpf,H=s.frame(n); s.R[n]=Rpf; s.H[n]=H
    def tail(s,n): return s.H[n]+s.R[n]@Vector((0,REST[n]['len'],0))
def two_bone(pose,a,b,target,pole,end_dir=None,c=None):
    """bones a (upper) and b (lower): reach 'target' with the middle joint pushed toward 'pole'"""
    pose.keep(a); Ha=pose.H[a]; l1=REST[a]['len']; l2=REST[b]['len']
    v=Vector(target)-Ha; d=v.length; d=max(abs(l1-l2)+1e-3,min(l1+l2-1e-3,d)); u=v.normalized()
    pl=Vector(pole); pl=(pl-u*pl.dot(u)); pl=pl.normalized() if pl.length>1e-6 else Vector((0,0,1))
    x=(l1*l1-l2*l2+d*d)/(2*d); h=math.sqrt(max(0.0,l1*l1-x*x)); E=Ha+u*x+pl*h
    pose.aim(a,E-Ha); pose.aim(b,(Ha+u*d)-E)
    if c: pose.aim(c,end_dir if end_dir is not None else (Ha+u*d)-E)
def write(arm,pose,frame,hips_loc=True):
    for n in ORDER:
        r=REST[n]; p=r['p']; pb=arm.pose.bones[n]
        Rpf,H=pose.frame(n)
        q=(Rpf.inverted()@pose.R[n]).to_quaternion()
        pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=q; pb.keyframe_insert('rotation_quaternion',frame=frame)
    pb=arm.pose.bones['Hips']; pb.location=REST['Hips']['R'].inverted()@pose.hips_delta; pb.keyframe_insert('location',frame=frame)
