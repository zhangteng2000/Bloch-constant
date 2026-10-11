"""Inner-disk part of the finite Prym projection certificate.

Uses convergent analytic series and Cauchy tail bounds, including explicit
removal of the sole double pole. Needs the separate outer-area enclosure.
"""
from fractions import Fraction as Qr
import json
import math
from pathlib import Path
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'work'/'deps'))
from flint import arb,acb,acb_series,ctx

def B(a,b=None):
    a=Qr(a)
    if b is None:return arb(str(a))
    b=Qr(b)
    return arb(str((a+b)/2),arb(str((b-a)/2)).upper())
def S(x):return acb_series([x])
def txt(x):return x.str(50,more=True)
def pair(x):return [txt(x.real),txt(x.imag)]

class Geometry:
    def __init__(self):
        self.H=arb(3).sqrt()/2;self.rt3=2*self.H
        self.tau=acb(arb(1)/2,self.H);self.t1=self.tau/2
        self.p=acb(arb(3)/2,self.H/3);self.pp=1-self.p
        self.q=acb(arb(1)/2)
        self.phase=acb(-self.H,-arb(1)/2)
        sigma=1/(1+self.rt3).sqrt()
        self.k=sigma*B(Qr(2,3)).gamma()*B(Qr(11,12)).gamma()/(B(Qr(4,3)).gamma()*B(Qr(1,4)).gamma())
        self.c=B(Qr(2,3)).gamma()/(self.rt3*B(Qr(4,3)).gamma()*B(Qr(1,3)).gamma())
        self.wpQ=self.wp(self.q)
        self.vp=self.f(self.p).sqrt()
        old=ctx.cap;ctx.cap=2
        self.vpp=(acb_series([self.p/2-self.q/2,acb(1)/2]).elliptic_p(self.t1)/4)[1]/(2*self.vp)
        ctx.cap=old
    def wp(self,w):return (w/2).elliptic_p(self.t1)/4
    def zeta(self,w):return (w/2).elliptic_zeta(self.t1)/2
    def f(self,w):return self.wp(w-self.q)-self.wpQ


def hyper_monomial(a,b,c):
    vals=[acb(0) for _ in range(ctx.cap)]
    coef=acb(1);vals[0]=coef
    for n in range(1,(ctx.cap-1)//3+1):
        coef*=(a+n-1)*(b+n-1)/((c+n-1)*n)
        vals[3*n]=coef
    return acb_series(vals)

def zetaj(g,w):
    return S(g.zeta(w[0]))-(w.derivative()*(w/2).elliptic_p(g.t1)/4).integral()

def circle_bounds(g,col,radius):
    center=acb(B(Qr(2*col+1,2)),g.H/3)
    values=[arb(0) for _ in range(6)]
    stack=[(Qr(j,256),Qr(j+1,256),0) for j in range(256)]
    accepted=0;coverage=Qr(0)
    while stack:
        lo,hi,depth=stack.pop()
        xi=radius*(acb(0,2*arb.pi())*B(lo,hi)).exp()
        u=xi**3
        U=u.hypgeom_2f1(B(Qr(5,12)),B(Qr(1,12)),B(Qr(2,3)))
        V=u.hypgeom_2f1(B(Qr(3,4)),B(Qr(5,12)),B(Qr(4,3)))
        W=g.c*xi*u.hypgeom_2f1(B(Qr(1,3)),B(Qr(2,3)),B(Qr(4,3)))
        Z=g.k*xi*V/U
        Wp=g.c*(1-u)**(-acb(2)/3)
        Zp=g.k*(1-u)**(-acb(5)/6)/U**2
        w=center+g.phase*W
        f=g.f(w)
        Rpair=(g.vp*(g.wp(w-g.p)+g.wp(w-g.pp))
                +g.vpp*(g.zeta(w-g.p)-g.zeta(w-g.pp)))/2
        fb=abs(f).lower()
        if not fb>0 or not Rpair.is_finite() or not Zp.is_finite() or abs(Zp).contains(0):
            assert depth<20,("circle subdivision",lo,hi)
            mid=(lo+hi)/2
            stack.extend([(lo,mid,depth+1),(mid,hi,depth+1)])
            continue
        mb=(abs(Wp)**2/(fb.sqrt()*abs(Zp).lower())).upper()
        za=abs(Z).upper()
        ma=(abs(Rpair)*mb).upper()
        bounds=[mb,mb*za,mb*za**2,ma,ma*za,ma*za**2]
        if col==1:
            bounds[3]+=1/(2*g.k*radius**2)
            bounds[4]+=1/(2*radius)
        for j in range(6):
            values[j]=max(values[j],bounds[j].upper())
        coverage+=hi-lo;accepted+=1
    assert coverage==1
    return values,accepted

def inner(g,col,N=160):
    ctx.cap=N+6
    x=acb_series([0,1]);u=x**3
    U=hyper_monomial(acb(B(Qr(5,12))),acb(B(Qr(1,12))),acb(B(Qr(2,3))))
    V=hyper_monomial(acb(B(Qr(3,4))),acb(B(Qr(5,12))),acb(B(Qr(4,3))))
    W=g.c*x*hyper_monomial(acb(B(Qr(1,3))),acb(B(Qr(2,3))),acb(B(Qr(4,3))))
    Z=g.k*x*V/U
    Zp=g.k*(1-u)**(-acb(5)/6)/U**2
    wp=g.phase*g.c*(1-u)**(-acb(2)/3)
    center=acb(B(Qr(2*col+1,2)),g.H/3)
    w=center+g.phase*W
    fs=((w-g.q)/2).elliptic_p(g.t1)/4-g.wpQ
    vs=fs.sqrt()
    b=wp**2/(vs*Zp)
    b1=b*Z;b2=b1*Z
    if col==0:
        Rp=(g.vp*(((w-g.p)/2).elliptic_p(g.t1)+((w-g.pp)/2).elliptic_p(g.t1))/4
            +g.vpp*(zetaj(g,w-g.p)-zetaj(g,w-g.pp)))/2
        a0=Rp*b;a1=a0*Z;a2=a1*Z
    else:
        # Exact Laurent formula at the only double pole.
        assert abs(vs[0]-g.vp).upper()<B(Qr(1,10**25))
        uu=g.phase*W
        ux=acb_series([uu[j+1] for j in range(ctx.cap-1)])
        inv=1/ux
        inv2=inv**2
        g2,g3=g.t1.elliptic_invariants()
        g2/=16;g3/=64
        coeff={1:g2/20,2:g3/28}
        for n in range(3,(ctx.cap+1)//2+1):
            coeff[n]=6*sum((coeff[j]*coeff[n-1-j] for j in range(1,n-1)),acb(0))/((2*n)*(2*n-1)-12)
        preg=S(0);zreg=S(0)
        for n,c in coeff.items():
            preg+=c*uu**(2*n)
            zreg-=c*uu**(2*n+1)/(2*n+1)
        Rreg=(g.vp*(preg+((w-g.pp)/2).elliptic_p(g.t1)/4)
                +g.vpp*(zreg-zetaj(g,w-g.pp)))/2
        left=g.vp*inv2*b/2
        middle=g.vpp*inv*b/2
        regular=Rreg*b
        aa=[left[n+2]+middle[n+1]+regular[n] for n in range(N+3)]
        a0=acb_series(aa)
        alpha=1/(2*g.k)
        a1=a0*Z+acb_series([alpha*Z[n+2] for n in range(N+3)])
        ZZ=Z**2
        a2=a0*ZZ+acb_series([alpha*ZZ[n+2] for n in range(N+3)])
        # Known principal coefficients, checked before their exact removal.
        assert (left[0]-alpha).contains(0)
        assert (left[1]+middle[0]).contains(0)
    eta=B(Qr(3,4));rho=B(Qr(7,8))
    den=acb(0);num=acb(0)
    for n in range(N+1):
        factor=arb.pi()/4*eta**(2*n+2)/(n+1)
        den+=factor*(b[n]*b[n].conjugate()-2*b1[n]*b1[n].conjugate()+b2[n]*b2[n].conjugate())
        num+=factor*(a0[n]*b[n].conjugate()-2*a1[n]*b1[n].conjugate()+a2[n]*b2[n].conjugate())
    # Only point/ball function values are used for the Cauchy circle.
    old=ctx.cap;ctx.cap=1
    bounds,cells=circle_bounds(g,col,rho)
    ctx.cap=old
    b0,b1m,b2m,a0m,a1m,a2m=bounds
    tailfactor=arb.pi()/4*eta**2*(eta/rho)**(2*N+2)/((N+2)*(1-(eta/rho)**2))
    de=(tailfactor*(b0*b0+2*b1m*b1m+b2m*b2m)).upper()
    ne=(tailfactor*(a0m*b0+2*a1m*b1m+a2m*b2m)).upper()
    den+=acb(arb(0,de),arb(0,de))
    num+=acb(arb(0,ne),arb(0,ne))
    return 2*den,num,{"column":col,"order":N,"circle_cells":cells,
            "Cauchy_bounds":[txt(z) for z in bounds],
            "denominator_tail_before_pairing":txt(de),"numerator_tail":txt(ne),
            "denominator_paired":pair(2*den),"numerator_paired":pair(num)}

if __name__=="__main__":
    started=time.perf_counter();ctx.prec=256;ctx.cap=1
    g=Geometry()
    d=acb(0);n=acb(0);rows=[]
    for col in [0,1]:
        dd,nn,row=inner(g,col)
        d+=dd;n+=nn;rows.append(row)
        print(json.dumps(row),flush=True)
    report={"status":"Certified FOUR inner disks ONLY; outer annulus required",
            "inner_xi_radius":"3/4","Cauchy_xi_radius":"7/8",
            "denominator":pair(d),"numerator":pair(n),"details":rows,
            "seconds":time.perf_counter()-started}
    Path(__file__).with_name("bloch_shear_prym_inner_result.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps(report,indent=2))
