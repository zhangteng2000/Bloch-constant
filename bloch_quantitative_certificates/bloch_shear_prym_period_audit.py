"""Finite elliptic periods with Arb, including analytic square-root checks.

This certifies only the period factors in formula (165), not its area
projection and not the global Bloch claim.
"""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'work'/'deps'))
from flint import arb, acb, acb_series, ctx

ctx.prec=160
ctx.cap=5
H=arb(3).sqrt()/2
tau=acb(arb(1)/2,H)
tau1=tau/2
p=acb(arb(3)/2,H/3)
Q=acb(arb(1)/2)

def wp(w):
    return (w/2).elliptic_p(tau1)/4

def zeta(w):
    return (w/2).elliptic_zeta(tau1)/2

def wp_prime(w):
    return (acb_series([w/2,acb(1)/2]).elliptic_p(tau1)/4)[1]

wpQ=wp(Q)
def square(w):
    return wp(w-Q)-wpQ

vp=square(p).sqrt()
vpp=wp_prime(p-Q)/(2*vp)
def R(w):
    return (vp*wp(w-p)+vpp*(zeta(w-p)-zeta(w-Q)))/2

def text(x):
    return x.str(50,more=True)

def pair(z):
    return [text(z.real),text(z.imag)]

def segment_ball(a,b):
    return acb((a.real+b.real)/2, (a.imag+b.imag)/2)+acb(
        arb(0,abs(a.real-b.real).upper()/2),
        arb(0,abs(a.imag-b.imag).upper()/2))

checks=[]
cells=0
def move(a,b,v,depth=0):
    fa=square(a)
    ratio=square(segment_ball(a,b))/fa
    if not ratio.real>0:
        assert depth<20, ("branch enclosure failed",pair(a),pair(b),pair(ratio))
        mid=(a+b)/2
        return move(mid,b,move(a,mid,v,depth+1),depth+1)
    checks.append(text(ratio.real))
    return v*(square(b)/fa).sqrt(analytic=True)

def wpj(w):
    return (w/2).elliptic_p(tau1)/4

def zetaj(w):
    return acb_series([zeta(w[0])])-(w.derivative()*wpj(w)).integral()

def rj(w):
    return (vp*wpj(w-p)+vpp*(zetaj(w-p)-zetaj(w-Q)))/2

def gauss_period(a,b,v,depth=0):
    global cells
    mid=(a+b)/2
    fm=square(mid)
    vm=move(a,mid,v)
    wj=acb_series([segment_ball(a,b),1])
    ratio=(wpj(wj-Q)-wpQ)/fm
    if not ratio[0].real>0:
        assert depth<22
        e0,a0,v0=gauss_period(a,mid,v,depth+1)
        e1,a1,v1=gauss_period(mid,b,v0,depth+1)
        return e0+e1,a0+a1,v1
    root=ratio.sqrt()
    if not root[0].is_finite() or (vm*root[0]).contains(0):
        assert depth<22, (str(vm),str(ratio),str(root))
        e0,a0,v0=gauss_period(a,mid,v,depth+1)
        e1,a1,v1=gauss_period(mid,b,v0,depth+1)
        return e0+e1,a0+a1,v1
    ej=1/(vm*root)
    aj=rj(wj)*ej
    length=(b-a).real
    error_e=length**5*abs(ej[4]).upper()/180
    error_a=length**5*abs(aj[4]).upper()/180
    if (not error_e.is_finite() or not error_a.is_finite()
        or error_e>length*arb("1e-11") or error_a>length*arb("1e-11")):
        assert depth<22
        e0,a0,v0=gauss_period(a,mid,v,depth+1)
        e1,a1,v1=gauss_period(mid,b,v0,depth+1)
        return e0+e1,a0+a1,v1
    delta=length/(2*arb(3).sqrt())
    es=acb(0)
    als=acb(0)
    for sign in [-1,1]:
        w=mid+sign*delta
        e=1/(vm*(square(w)/fm).sqrt(analytic=True))
        es+=e
        als+=R(w)*e
    eb=arb(0,error_e.upper())
    ab=arb(0,error_a.upper())
    cells+=1
    return length*es/2+acb(eb,eb),length*als/2+acb(ab,ab),move(mid,b,vm)

def periods(height):
    a=p
    v=vp
    start=acb(arb(3)/2,height*H)
    for j in range(1,17):
        b=p+(start-p)*j/16
        v=move(a,b,v)
        a=b
    start_v=v
    eta=acb(0)
    alpha=acb(0)
    for j in range(32):
        a=start+arb(j)/16
        b=start+arb(j+1)/16
        ep,ap,next_v=gauss_period(a,b,v)
        assert ep.is_finite() and ap.is_finite()
        eta+=ep
        alpha+=ap
        v=next_v
    assert (v/start_v).real>0
    assert abs(v-start_v).upper()<arb("1e-20")
    return {"height_over_H":text(height),"eta":pair(eta),"alpha0":pair(alpha),
            "root_closure":pair(v-start_v)}

if __name__=="__main__":
    started=time.perf_counter()
    result={
        "status":"Certified finite elliptic period factors ONLY",
        "precision_bits":ctx.prec,
        "normalization":"wp_Lambda(w)=wp(w/2,tau/2)/4; zeta_Lambda(w)=zeta(w/2,tau/2)/2",
        "v_at_p":pair(vp),"v_prime_at_p":pair(vpp),
        "periods":[periods(arb(1)/2),periods(arb(7)/10)],
        "strict_positive_real_square_root_segment_checks":len(checks),
        "two_point_gauss_cells_with_fourth_derivative_bounds":cells,
        "limitations":["Area projection M_R is not certified here.",
                       "This output does not certify a Bloch counterexample."],
        "seconds":time.perf_counter()-started}
    path=Path(__file__).with_name("bloch_shear_prym_period_result.json")
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
