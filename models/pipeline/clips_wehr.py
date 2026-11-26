import math, bpy
from mathutils import Vector
import rig_lib, anim_lib
from anim_lib import Pose, two_bone, REST
FPS=30
def smooth(u): return u*u*(3-2*u)
def tri(x): return max(0.0,1.0-abs(x))
def foot_path(ph,sw,lift,fs):
    ph%=1.0
    if ph<fs: return sw*(1-2*ph/fs),0.0          # stance: foot slides back under the body (s>0 = forward)
    u=(ph-fs)/(1-fs); return -sw+2*sw*smooth(u), lift*math.sin(math.pi*u)
PARAMS={ # hips height, stride half-length, foot lift, stance fraction, lean, sway, twist, bob, arm swing, arm height
 'idle':(0.93,0.0,0.0,1.0,0.02,0.005,0.0,0.004,0.0,0.95),
 'walk':(0.905,0.22,0.09,0.62,0.03,0.012,0.09,0.010,0.13,0.93),
 'run':(0.83,0.40,0.22,0.38,0.18,0.015,0.14,0.035,0.26,1.07)}
def build(arm,ph,mode):
    P=Pose(); hz,sw,lift,fs,lean,sway,twist,bob,swing,ah=PARAMS[mode]; a=2*math.pi*ph
    if mode=='idle': dz=bob*math.sin(a); dx=sway*math.sin(a); roll=0.0
    elif mode=='walk': dz=bob*math.cos(4*math.pi*(ph-0.31)); dx=sway*math.cos(2*math.pi*(ph-0.31)); roll=-0.04*math.cos(2*math.pi*(ph-0.31))
    else: dz=-bob*math.cos(4*math.pi*(ph-0.19)); dx=sway*math.cos(2*math.pi*(ph-0.19)); roll=-0.05*math.cos(2*math.pi*(ph-0.19))
    P.hips_delta=Vector((dx,0,hz-0.93+dz))
    yaw=twist*math.cos(a)
    P.rotate('Hips',(lean*0.3,roll,-yaw*0.7))
    P.rotate('Spine',(lean*0.3,-roll*0.4,yaw*0.45)); P.rotate('Spine1',(lean*0.3,-roll*0.4,yaw*0.55))
    P.rotate('Spine2',(lean*0.15+(0.012*math.sin(a) if mode=='idle' else 0.0),-roll*0.3,yaw*0.6))
    P.rotate('Neck',(-lean*0.3,roll*0.5,-yaw*0.3)); P.rotate('Head',(-lean*0.2,roll*0.4,-yaw*0.35))
    fw={}   # how far forward each foot is, -1..1
    for sd,sg,off in (('Left',1,0.0),('Right',-1,0.5)):
        up,lg,ft=sd+'UpLeg',sd+'Leg',sd+'Foot'
        s,lf=foot_path(ph+off,sw,lift,fs) if mode!='idle' else (0.0,0.0)
        fw[sd]=(s/sw) if sw else 0.0
        T=Vector((sg*(0.14 if mode=='run' else 0.15),0.055-s,0.14+lf))
        two_bone(P,up,lg,T,(0,-1,0))
        td=0.0
        if mode!='idle':
            u=(ph+off)%1.0; um=u if u<0.5 else u-1.0
            td=0.45*tri((u-fs)/0.12)-0.22*tri(um/0.08)
        ang=0.32+td; P.aim(ft,(0,-math.cos(ang),-math.sin(ang)))
    Rs=REST['Spine2']; M=P.R['Spine2']@Rs['R'].inverted()
    def tw(T): return P.H['Spine2']+M@(T-Rs['H'])
    for sd,sg,other in (('Left',1,'Right'),('Right',-1,'Left')):
        sh,ar,fa,hd=sd+'Shoulder',sd+'Arm',sd+'ForeArm',sd+'Hand'
        P.keep(sh)
        f=fw[other] if mode!='idle' else 0.0      # arms swing against the legs
        y=0.045-swing*f*(1.0 if mode=='walk' else 1.35)
        z=ah+(0.05*max(0.0,f) if mode=='walk' else 0.07*f)
        x=sg*(0.235 if mode!='run' else 0.20)
        if mode=='idle': z+=0.004*math.sin(a)
        two_bone(P,ar,fa,tw(Vector((x,y,z))),(sg*0.4,0.9,-0.2))
        P.aim(hd,(P.tail(fa)-P.H[fa]).normalized()+Vector((0,-0.15,-0.25)))
    P.keep('Weapon')
    return P
def make_clip(arm,name,mode,frames):
    act=bpy.data.actions.new(name); arm.animation_data_create(); arm.animation_data.action=act
    for f in range(frames):
        anim_lib.write(arm,build(arm,f/frames,mode),f+1)
    return act
