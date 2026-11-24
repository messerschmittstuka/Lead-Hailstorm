import random, math
from PIL import Image, ImageDraw, ImageFilter
W,H=768,1536; S=2  # supersample
img=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); d=ImageDraw.Draw(img)
def c(col,j=10,r=random): return tuple(max(0,min(255,v+r.randint(-j,j))) for v in col)+(255,)
def line(p,w,col): d.line([(x*S,y*S) for x,y in p],fill=col,width=max(1,int(w*S)),joint='curve')
def bez(p0,p1,p2,n=24):
    return [((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0],(1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1]) for t in [i/n for i in range(n+1)]]
def culm(r,x0,tone):
    base=(196,170,98) if tone==0 else ((186,176,104) if tone==1 else (170,168,100))
    ytop=r.randint(300,420); xtop=x0+r.randint(-40,40)
    pts=bez((x0,H-4),(x0+r.randint(-25,25),(H+ytop)//2),(xtop,ytop),40)
    # leaves (flag leaf + one lower), dried yellow-green, arching
    for k,(t,sgn) in enumerate(((0.45,r.choice((-1,1))),(0.7,r.choice((-1,1))))):
        sx,sy=pts[int(t*40)]; L=r.randint(160,230)
        ex=sx+sgn*L*0.8; ey=sy-L*0.25+r.randint(-30,30)
        leaf=bez((sx,sy),(sx+sgn*L*0.5,sy-L*0.55),(ex,ey+L*0.25),20)
        lc=c((158,152,84),12,r)
        for i in range(len(leaf)-1):
            w=max(1,int(11*(1-i/20)**0.7*(1 if i>1 else 0.5)))
            d.line([(leaf[i][0]*S,leaf[i][1]*S),(leaf[i+1][0]*S,leaf[i+1][1]*S)],fill=lc,width=w*S)
    # stem
    for i in range(len(pts)-1): d.line([(pts[i][0]*S,pts[i][1]*S),(pts[i+1][0]*S,pts[i+1][1]*S)],fill=c(base,8,r),width=int(6*S))
    # leaf sheath (paler) on lower half
    for i in range(0,26): d.line([(pts[i][0]*S,pts[i][1]*S),(pts[i+1][0]*S,pts[i+1][1]*S)],fill=c((214,196,130),6,r),width=int(8*S))
    for t in (0.22,0.42,0.62):   # nodes
        x,y=pts[int(t*40)]; d.ellipse([(x-5)*S,(y-4)*S,(x+5)*S,(y+4)*S],fill=(120,100,52,255))
    # ear: drooping
    ex,ey=pts[-1]; ang=r.uniform(-0.35,0.35)+ (0.25 if r.random()<0.5 else -0.25)  # lean from vertical
    EL=138; dx,dy=math.sin(ang),-math.cos(ang)
    spk=(212,170,72)
    for i in range(11):
        t=i/10; px=ex+dx*EL*t*0.98+ (t*t*28*(1 if ang>0 else -1)); py=ey+dy*EL*t
        nx,ny=-dy,dx; wd=11*(0.55+0.45*math.sin(math.pi*min(1,t*0.95+0.05)))
        for sgn in (-1,1):
            cx=px+nx*wd*0.7*sgn; cy=py+ny*wd*0.7*sgn+ sgn*2
            d.ellipse([(cx-wd*0.8)*S,(cy-7)*S,(cx+wd*0.8)*S,(cy+7)*S],fill=c(spk,14,r))
            # awn from each spikelet
            ax=cx+ (dx*1.0+nx*sgn*0.35)*r.randint(95,135); ay=cy+(dy*1.0)*r.randint(95,135)
            d.line([(cx*S,cy*S),(ax*S,ay*S)],fill=c((228,204,128),12,r),width=int(1.6*S))
    d.ellipse([(ex+dx*EL-5)*S,(ey+dy*EL-6)*S,(ex+dx*EL+5)*S,(ey+dy*EL+6)*S],fill=c(spk,10,r))
r=random.Random(11)
for k,x0 in enumerate([110,250,390,530,670]):
    culm(r,x0+r.randint(-25,25),[0,0,1,0,2][k])
img=img.resize((W,H),Image.LANCZOS)
# bleed straw colour into transparent texels (avoid dark halo)
a=img.split()[3]; bg=Image.new('RGBA',img.size,(205,180,100,0)); bg.alpha_composite(img); out=Image.merge('RGBA',(*bg.split()[:3],a))
out.save('wheat.png'); print(out.size)
