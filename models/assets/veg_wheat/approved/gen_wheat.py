import random, math, sys
SEED=int(sys.argv[1]) if len(sys.argv)>1 else 11
OUTN=sys.argv[2] if len(sys.argv)>2 else 'wheat.png'
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
    # ear: compact, slightly drooping near the tip
    ex,ey=pts[-1]; side=1 if r.random()<0.5 else -1; ang=r.uniform(0.05,0.3)*side
    EL=r.randint(120,140); dx,dy=math.sin(ang),-math.cos(ang)
    def ep(t):
        droop=(t**2.2)*34*side
        return ex+dx*EL*t+droop, ey+dy*EL*t+ (t**2.2)*14
    # rachis/body underlay so the ear reads as a solid mass
    for i in range(0,20):
        t=i/19; px,py=ep(t); wd=8*(0.6+0.4*math.sin(math.pi*min(1,t*0.9+0.08)))
        d.ellipse([(px-wd)*S,(py-9)*S,(px+wd)*S,(py+9)*S],fill=c((190,150,62),8,r))
    for i in range(14):
        t=i/13; px,py=ep(t); nx,ny=-dy,dx; wd=12*(0.55+0.45*math.sin(math.pi*min(1,t*0.92+0.06)))
        for sgn in (-1,1):
            cx=px+nx*wd*0.62*sgn; cy=py+ny*wd*0.62*sgn+(0 if sgn<0 else 4)
            tone=c((226,192,102),14,r)
            d.ellipse([(cx-wd*0.55)*S,(cy-11)*S,(cx+wd*0.55)*S,(cy+11)*S],fill=tone)
            d.line([(cx*S,(cy-9)*S),(cx*S,(cy+9)*S)],fill=c((170,130,56),8,r),width=S)     # glume keel
            L=r.randint(90,135); aa=r.uniform(-0.12,0.12)
            ax=cx+(dx+nx*sgn*0.3)*L*0.9+aa*40; ay=cy+dy*L
            d.line([(cx*S,(cy-6)*S),(ax*S,ay*S)],fill=c((232,212,140),10,r),width=int(1.5*S))
    px,py=ep(1.0); d.ellipse([(px-6)*S,(py-8)*S,(px+6)*S,(py+8)*S],fill=c((220,184,96),8,r))
r=random.Random(SEED)
for k,x0 in enumerate([110,250,390,530,670]):
    culm(r,x0+r.randint(-25,25),[0,0,1,0,2][k])
img=img.resize((W,H),Image.LANCZOS)
# bleed straw colour into transparent texels (avoid dark halo)
a=img.split()[3]; bg=Image.new('RGBA',img.size,(205,180,100,0)); bg.alpha_composite(img); out=Image.merge('RGBA',(*bg.split()[:3],a))
out.save(OUTN); print(out.size)
