"""Arb evaluator for the finite Prym projection's outer annulus.

Use bloch_shear_prym_area_audit.py for the complete parallel cover.
This is an arithmetic component; the geometric interpretation is a separate
mathematical argument in bloch_research_notes.tex.
"""
import argparse
from fractions import Fraction as Qr
import json
import math
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'work'/'deps'))
from flint import arb,acb,acb_series,ctx

def B(a,b=None):
    a=Qr(a)
    if b is None:return arb(str(a))
    b=Qr(b)
    return arb(str((a+b)/2),arb(str((b-a)/2)).upper())
def S(x):return acb_series([x])
def cj(x):return acb_series([x[i].conjugate() for i in range(ctx.cap)])
def abs2j(x):
    re=acb_series([acb(x[i].real) for i in range(ctx.cap)])
    im=acb_series([acb(x[i].imag) for i in range(ctx.cap)])
    out=re**2+im**2
    # The constant is a modulus square, so use the rectangle-distance bound
    # instead of independent products of repeated uncertain real parts.
    modulus=abs(x[0])
    lo=max(arb(0),modulus.lower())**2
    hi=modulus.upper()**2
    square=arb((lo+hi)/2,((hi-lo)/2).upper())
    return acb_series([acb(square)]+[out[i] for i in range(1,ctx.cap)])
def positive_power_jet(x,p):
    assert x[0].imag.is_zero()
    lo=x[0].real.lower();hi=x[0].real.upper()
    if not lo>0:raise ValueError("positive scalar power needs subdivision")
    delta=acb_series([0]+[x[j] for j in range(1,ctx.cap)])
    ans=S(0);power=S(1);binom=arb(1)
    for j in range(ctx.cap):
        exponent=p-j
        aa=lo**exponent;bb=hi**exponent
        low=min(aa.lower(),bb.lower());high=max(aa.upper(),bb.upper())
        coeff=arb((low+high)/2,((high-low)/2).upper())
        ans+=binom*coeff*power
        binom*= (p-j)/(j+1)
        power*=delta
    return ans
def absj(x):return positive_power_jet(abs2j(x),arb(1)/2)
def invabsj(x):return positive_power_jet(abs2j(x),-arb(1)/2)
def hyp(a,b,c,z):
    a,b,c=acb(a),acb(b),acb(c)
    if abs(z[0]-acb(z[0].real.mid(),z[0].imag.mid())).upper()>B(Qr(1,10**20)):
        return hyp_euler(a,b,c,z)
    dz=acb_series([0]+[z[k] for k in range(1,ctx.cap)])
    ans=S(z[0].hypgeom_2f1(a,b,c))
    power=S(1);coef=acb(1)
    for k in range(1,ctx.cap):
        coef*=(a+k-1)*(b+k-1)/((c+k-1)*k)
        power*=dz
        ans+=coef*z[0].hypgeom_2f1(a+k,b+k,c+k)*power
    return ans
def hyp_euler(a,b,c,z):
    """Local Taylor enclosure from the ODE and Euler's beta integral."""
    assert a.imag.is_zero() and b.imag.is_zero() and c.imag.is_zero()
    assert a.real>0 and b.real>0 and c.real>b.real
    zm=acb(z[0].real.mid(),z[0].imag.mid())
    d=(1-max(arb(0),zm.real.upper())).lower()
    radius=abs(z[0]-zm).upper()
    if not d>0 or not radius/d<arb(1)/4:
        raise ValueError("hypergeometric Taylor box needs subdivision")
    ratio=radius/d;M=22
    yy=[zm.hypgeom_2f1(a,b,c),a*b/c*zm.hypgeom_2f1(a+1,b+1,c+1)]
    if abs(zm)<B(Qr(1,100)):
        for n in range(2,M+1):
            coef=acb(1)
            for j in range(n):coef*=(a+j)*(b+j)/((c+j)*(j+1))
            yy.append(coef*zm.hypgeom_2f1(a+n,b+n,c+n))
    else:
        A0=zm*(1-zm);A1=1-2*zm;B0=c-(a+b+1)*zm
        for n in range(M-1):
            yy.append((-(n+1)*(A1*n+B0)*yy[n+1]
                       +(n*(n-1)+(a+b+1)*n+a*b)*yy[n])/(A0*(n+2)*(n+1)))
    zz=z-zm
    out=S(yy[-1])
    for v in reversed(yy[:-1]):out=out*zz+v
    # Bound derivatives of the omitted tail at every point of z[0].
    dz=acb_series([0]+[z[j] for j in range(1,ctx.cap)])
    power=S(1);pref=arb(1)
    for j in range(ctx.cap):
        if j:pref*=a.real+j-1
        N=M+1-j
        first=arb(1)
        for k in range(N):first*=(a.real+j+k)*ratio/(k+1)
        tailratio=ratio*max(arb(1),(a.real+j+N)/(N+1))
        error=(pref*d**(-a.real-j)*first/(1-tailratio)).upper()
        out+=acb(arb(0,error),arb(0,error))*power/math.factorial(j)
        power*=dz
    return out
def hyp0(c,z):
    c=acb(c)
    dz=acb_series([0]+[z[k] for k in range(1,ctx.cap)])
    ans=S(z[0].hypgeom_0f1(c))
    power=S(1);coef=acb(1)
    for k in range(1,ctx.cap):
        coef/=(c+k-1)*k;power*=dz
        ans+=coef*z[0].hypgeom_0f1(c+k)*power
    return ans
def hyp1(a,c,z):
    a,c=acb(a),acb(c)
    dz=acb_series([0]+[z[k] for k in range(1,ctx.cap)])
    ans=S(z[0].hypgeom_1f1(a,c))
    power=S(1);coef=acb(1)
    for k in range(1,ctx.cap):
        coef*=(a+k-1)/((c+k-1)*k);power*=dz
        ans+=coef*z[0].hypgeom_1f1(a+k,c+k)*power
    return ans
def txt(x):return x.str(50,more=True)
def pair(x):return [txt(x.real),txt(x.imag)]

class Geometry:
    def __init__(self):
        self.H=arb(3).sqrt()/2;self.rt3=2*self.H
        self.tau=acb(arb(1)/2,self.H);self.t1=self.tau/2
        self.p=acb(arb(3)/2,self.H/3);self.pp=1-self.p
        self.q=acb(arb(1)/2);self.K=arb.pi()/2
        self.phase=acb(-self.H,-arb(1)/2)
        self.omega=acb(-arb(1)/2,self.H)
        self.sigma=1/(1+self.rt3).sqrt()
        self.k=self.sigma*B(Qr(2,3)).gamma()*B(Qr(11,12)).gamma()/(B(Qr(4,3)).gamma()*B(Qr(1,4)).gamma())
        self.c=B(Qr(2,3)).gamma()/(self.rt3*B(Qr(4,3)).gamma()*B(Qr(1,3)).gamma())
        self.r=1/self.rt3
        self.wpQ=self.wp(self.q)
        self.vp=self.f(self.p).sqrt()
        old=ctx.cap;ctx.cap=2
        self.vpp=(acb_series([self.p/2-self.q/2,acb(1)/2]).elliptic_p(self.t1)/4)[1]/(2*self.vp)
        ctx.cap=old
        self.eta1=self.zeta(acb(1))
        self.eta2=self.zeta(self.tau/2)
        self.theta_coeff=[]
        for n in range(18):
            self.theta_coeff.append(2*(-1)**n*(acb(0,arb.pi())*self.t1*(B(Qr(2*n+1,2))**2)).exp())
        self.tail=B(Qr(1,10**100))
        # Derivative tails through order eight, uniformly |Im w| <= 2.
        self.tail_checks=[]
        for j in range(13):
            n=18
            first=2*(self.K*(2*n+1))**j*(-arb.pi()*self.H/2*B(Qr(2*n+1,2))**2+2*self.K*(2*n+1)).exp()
            ratio=B(Qr(2*n+3,2*n+1))**j*(-arb.pi()*self.H*(n+1)+4*self.K).exp()
            bound=first/(1-ratio)
            assert ratio<arb(1)/2 and bound<self.tail
            self.tail_checks.append(txt(bound))
        self.thetaQ=self.theta(S(self.q))[0][0]
        self.theta0prime=self.theta(S(0))[1][0]
        self.tfactor=abs(self.thetaQ)**2/abs(self.theta0prime)**2
        self.ca0=B(Qr(2,3)).gamma()*B(Qr(1,6)).gamma()/(B(Qr(1,4)).gamma()*B(Qr(7,12)).gamma())
        self.cb0=B(Qr(2,3)).gamma()*B(Qr(-1,6)).gamma()/(B(Qr(5,12)).gamma()*B(Qr(1,12)).gamma())
        self.ca1=B(Qr(4,3)).gamma()*B(Qr(1,6)).gamma()/(B(Qr(7,12)).gamma()*B(Qr(11,12)).gamma())
        self.cb1=B(Qr(4,3)).gamma()*B(Qr(-1,6)).gamma()/(B(Qr(3,4)).gamma()*B(Qr(5,12)).gamma())
    def wp(self,w):return (w/2).elliptic_p(self.t1)/4
    def zeta(self,w):return (w/2).elliptic_zeta(self.t1)/2
    def f(self,w):return self.wp(w-self.q)-self.wpQ
    def R(self,w):return (self.vp*self.wp(w-self.p)+self.vpp*(self.zeta(w-self.p)-self.zeta(w-self.q)))/2
    def theta_error(self,w):
        dz=acb_series([0]+[w[i] for i in range(1,ctx.cap)])
        power=S(1);out=S(0)
        e=acb(arb(0,self.tail),arb(0,self.tail))
        for i in range(ctx.cap):
            out+=e*power/math.factorial(i)
            power*=dz
        return out
    def theta(self,w):
        assert abs(w[0].imag).upper()<2
        ts=[S(0),S(0),S(0)]
        for n,coeff in enumerate(self.theta_coeff):
            freq=self.K*(2*n+1);arg=freq*w
            sn=arg.sin();co=arg.cos()
            ts[0]+=coeff*sn
            ts[1]+=coeff*freq*co
            ts[2]-=coeff*freq**2*sn
        e=self.theta_error(w)
        return [v+e for v in ts]
    def theta_div(self,w):
        if abs(w[0]).lower()>B(Qr(1,100)):
            return self.theta(w)[0]/w
        ans=S(0)
        for n,coeff in enumerate(self.theta_coeff):
            freq=self.K*(2*n+1)
            ans+=coeff*freq*hyp0(B(Qr(3,2)),-(freq*w)**2/4)
        return ans+self.theta_error(w)
    def Rpair(self,w):
        def elliptic(arg):
            # Any chosen integers give an exact period identity.
            nn=int(round(float(arg[0].imag.mid()/self.H)))
            mm=int(round(float((arg[0]-nn*self.tau).real.mid()/2)))
            red=arg-nn*self.tau-2*mm
            t=self.theta(red)
            wp=-(t[2]/t[0]-(t[1]/t[0])**2)-self.eta1
            ze=self.eta1*red+t[1]/t[0]+2*nn*self.eta2+2*mm*self.eta1
            return wp,ze
        wp1,z1=elliptic(w-self.p);wp2,z2=elliptic(w-self.pp)
        return (self.vp*(wp1+wp2)+self.vpp*(z1-z2))/2
    def base(self,s,t,mode,inner):
        rad=s**6
        aa,bb=(S(1),t) if mode==0 else (t,S(1))
        aa*=1-inner
        x=aa*rad
        xi=(1-x)*(acb(0,arb.pi()/3)*bb*rad).exp()
        h=acb(0,arb.pi())*bb*rad
        D=3*aa-3*aa**2*rad+aa**3*rad**2-acb(0,arb.pi())*bb*(1-x)**3*hyp1(1,2,h)
        delta=rad*D
        if abs(delta[0]).upper()<arb(3)/4:
            sixth=s*D**(acb(1)/6)
            U=self.ca0*hyp(B(Qr(5,12)),B(Qr(1,12)),B(Qr(5,6)),delta)+self.cb0*sixth*hyp(B(Qr(1,4)),B(Qr(7,12)),B(Qr(7,6)),delta)
            V=self.ca1*hyp(B(Qr(3,4)),B(Qr(5,12)),B(Qr(5,6)),delta)+self.cb1*sixth*hyp(B(Qr(7,12)),B(Qr(11,12)),B(Qr(7,6)),delta)
            L=-self.c*xi*D**(acb(1)/3)*hyp(1,B(Qr(2,3)),B(Qr(4,3)),delta)
        else:
            U=hyp(B(Qr(5,12)),B(Qr(1,12)),B(Qr(2,3)),xi**3)
            V=hyp(B(Qr(3,4)),B(Qr(5,12)),B(Qr(4,3)),xi**3)
            W=self.c*xi*hyp(B(Qr(1,3)),B(Qr(2,3)),B(Qr(4,3)),xi**3)
            L=(W-self.r)/s**2
        Z=self.k*xi*V/U
        # Jacobian includes the radial annulus scale (1-inner).
        dens=arb.pi()*self.c**4/(2*self.k**2)*s**3*(1-inner)*(1-x)*(1-abs2j(Z))**2*abs2j(U)**2*invabsj(D)
        return Z,L,dens
    def integrand(self,sb,tb,mode,direction,inner):
        s=acb_series([sb,int(direction==0)])
        t=acb_series([tb,int(direction==1)])
        Z,L,dens=self.base(s,t,mode,inner)
        den=S(0);num=S(0)
        for reflect in [False,True]:
            LL=cj(L) if reflect else L
            for j in range(3):
                dL=self.phase*self.omega**j*LL
                d=s**2*dL
                edge=self.theta(d+1)[0]
                if abs(d[0]).lower()>B(Qr(1,100)):
                    common=self.tfactor*s**2*invabsj(self.theta(d)[0])*invabsj(edge)
                else:
                    td=self.theta_div(d)
                    common=self.tfactor*invabsj(td)*invabsj(dL)*invabsj(edge)
                for parity in [0,1]:
                    w=parity+d
                    tq=self.theta(w-self.q)[0]
                    weight=common*abs2j(tq)
                    den+=2*weight
                    num+=weight*self.Rpair(w)
        return [dens*den,dens*num]
    def cell(self,sl,sh,tl,th,mode,inner):
        hs=B(sh-sl);ht=B(th-tl);sm=B((sl+sh)/2);tm=B((tl+th)/2)
        root=arb(30).sqrt()
        nodes=[]
        for sign in [-1,1]:
            for branch in [-1,1]:
                node=sign*((3+branch*2*(arb(6)/5).sqrt())/7).sqrt()/2
                weight=(18-branch*root)/72
                nodes.append((node,weight))
        values=[acb(0),acb(0)]
        old=ctx.cap
        self.last_direction=None
        try:
            ctx.cap=1
            for si,sw in nodes:
                for ti,tw in nodes:
                    vv=self.integrand(sm+si*hs,tm+ti*ht,mode,-1,inner)
                    for k in range(2):values[k]+=sw*tw*vv[k][0]
            ctx.cap=9
            js=self.integrand(B(sl,sh),B(tl,th),mode,0,inner)
            jt=self.integrand(B(sl,sh),B(tl,th),mode,1,inner)
            es=[hs**8*abs(js[k][8]).upper()/44100 for k in range(2)]
            et=[ht**8*abs(jt[k][8]).upper()/44100 for k in range(2)]
            errors=[a+b for a,b in zip(es,et)]
            if not all(v.is_finite() for v in values+errors):return None
            self.last_direction=0 if max(es)>max(et) else 1
            return [hs*ht*(values[k]+acb(arb(0,errors[k].upper()),arb(0,errors[k].upper()))) for k in range(2)]
        except (ValueError,ZeroDivisionError,AssertionError):
            return None
        finally:ctx.cap=old

def outside(args):
    ctx.prec=args.prec;ctx.cap=1
    geo=Geometry();started=time.perf_counter()
    inner=B(Qr(3,4));tol=B(Qr(1,20000))
    stack=[(Qr(0),Qr(1),Qr(0),Qr(1),m,0) for m in [0,1]]
    total=[acb(0),acb(0)];area=Qr(0);accepted=attempts=0
    while stack:
        sl,sh,tl,th,mode,depth=stack.pop();attempts+=1
        val=geo.cell(sl,sh,tl,th,mode,inner)
        ar=(sh-sl)*(th-tl)
        if val is not None and all(max(x.real.rad(),x.imag.rad())<=tol*B(ar) for x in val):
            total=[a+b for a,b in zip(total,val)]
            area+=ar;accepted+=1
        else:
            if depth>=args.max_depth:raise RuntimeError(("depth",sl,sh,tl,th,mode))
            if (geo.last_direction==0 or (geo.last_direction is None and sh-sl>=th-tl)):
                mid=(sl+sh)/2
                stack.extend([(sl,mid,tl,th,mode,depth+1),(mid,sh,tl,th,mode,depth+1)])
            else:
                mid=(tl+th)/2
                stack.extend([(sl,sh,tl,mid,mode,depth+1),(sl,sh,mid,th,mode,depth+1)])
        if attempts%100==0:
            print("attempts",attempts,"accepted",accepted,"area",float(area),"pending",len(stack),"seconds",time.perf_counter()-started,flush=True)
            checkpoint={"status":"INCOMPLETE live quadrature checkpoint",
                        "area":str(area),"accepted":accepted,"attempts":attempts,
                        "totals":[pair(x) for x in total],
                        "stack":[[str(x) for x in row[:4]]+list(row[4:]) for row in stack]}
            Path(args.out).with_suffix(".checkpoint.json").write_text(json.dumps(checkpoint,indent=2),encoding="utf8")
        if attempts>=args.limit or time.perf_counter()-started>=args.seconds_limit:
            print("STOPPED: incomplete cover",flush=True);break
    result={"status":"OUTSIDE annulus only; inner disks still required",
            "complete":not stack,"covered_parameter_area":str(area),
            "inner_xi_radius":"3/4","denominator":pair(total[0]),"numerator":pair(total[1]),
            "theta_derivative_tails":geo.tail_checks,
            "accepted":accepted,"attempts":attempts,"seconds":time.perf_counter()-started}
    Path(args.out).write_text(json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--prec",type=int,default=128)
    parser.add_argument("--limit",type=int,default=200000)
    parser.add_argument("--max-depth",type=int,default=40)
    parser.add_argument("--out",default=str(Path(__file__).with_name("prym_area_outside.json")))
    parser.add_argument("--seconds-limit",type=float,default=3000)
    args=parser.parse_args()
    outside(args)
