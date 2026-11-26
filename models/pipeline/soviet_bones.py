# Soviet soldier: same skeleton as the Wehrmacht rig, arm/shoulder joints moved to fit this body (applied before building/reading the armature)
import rig_lib
def apply():
    A=rig_lib.add
    for sd,sg in (('Left',1),('Right',-1)):
        X=lambda v:(v[0]*sg,v[1],v[2])
        A(sd+'Shoulder','Spine2',X((0.05,0.03,1.45)),X((0.20,0.06,1.40)))
        A(sd+'Arm',sd+'Shoulder',X((0.20,0.06,1.40)),X((0.43,0.07,1.17)))
        A(sd+'ForeArm',sd+'Arm',X((0.43,0.07,1.17)),X((0.56,-0.01,1.08)))
        A(sd+'Hand',sd+'ForeArm',X((0.56,-0.01,1.08)),X((0.69,-0.05,0.99)))
