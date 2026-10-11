"""Exact checks for the conditional finite-parameter energy bound (162).

The geometric construction, Green comparison, and integral identification
are mathematical arguments in the companion notes. This script checks
the new angular coefficient and explicit remainder arithmetic only.
"""
import hashlib
import json
from pathlib import Path
import sys

import sympy as s
try:
    from flint import arb,ctx
except ImportError:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'work'/'deps'))
    from flint import arb,ctx


def angular_average(expr,c,v):
    result=0
    for powers,coef in s.Poly(s.expand(expr),c,v).terms():
        n,m=powers
        if n%2 or m%2:continue
        a,b=n//2,m//2
        result+=coef*s.factorial(2*a)*s.factorial(2*b)/(4**(a+b)*s.factorial(a)*s.factorial(b)*s.factorial(a+b))
    return s.factor(result)


def main():
    c,v,k,d,t=s.symbols('c v k d t',real=True)
    e=s.Matrix([c,v])
    L=s.Matrix([[d*c*v,k+d*v*v],[0,0]])
    C=s.Matrix([[0,-1],[-1,0]])
    E=s.diag(1,0)
    A=d*c*v
    B=k+d*v*v
    bh1=s.Matrix([[-A,-B],[-B,A]])
    bh2=s.Matrix([[A*A+B*B,0],[0,0]])
    Jac=s.eye(2)+t*L
    bh=Jac.adjugate()*Jac.adjugate().T/Jac.det()
    assert (bh.diff(t).subs(t,0)-bh1)==s.zeros(2)
    assert s.simplify(bh.diff(t,2).subs(t,0)/2-bh2)==s.zeros(2)

    p0=-e
    p1=-L.T*e-k*v*s.Matrix([1,0])+2*k*c*v*e
    first=(p0.T*(C-bh1)*p0)[0]
    second=(p0.T*(E-bh2)*p0)[0]+2*(p1.T*(C-bh1)*p0)[0]
    assert angular_average(first,c,v)==0
    avg=angular_average(second,c,v)
    expected=(d*d+6*d*k-4*d+4*k*k-8*k+4)/8
    assert s.simplify(avg-expected)==0
    r=s.symbols('r',positive=True)
    annulus=s.simplify(s.integrate(avg.subs({k:2-r,d:-r})/r,(r,1,2)))
    assert annulus==s.Rational(1,16)+s.log(2)/2

    # Uniform bound for the rational integrand on the complex t-circle |t|=1/10.
    M=(s.Rational(143,89))**2*(s.Rational(111,100)+s.Rational(169,90))
    assert M<8
    assert s.Rational(8000)/(1-s.Rational(1,1000))<8010
    # Cauchy coefficient bound for F'/F'(0), at r<=b=1/50.
    assert s.Rational(12000)/(1-s.Rational(1,125))<12500
    # |Delta C|,|Delta E| <= 50000*r^3.
    angular_error=s.Rational(27)*50000*s.Rational(1,50)**3/3
    assert angular_error==s.Rational(18,5)
    ctx.prec=192
    coefficient=arb(18)/5+arb(1)/16+arb(50).log()+(arb(1)/2+arb(801)/1000)*arb(2).log()
    assert coefficient<9
    parameter=s.Rational(1,64000)
    bound=-parameter/3200+10*parameter**2
    assert bound==-s.Rational(1,409600000)
    assert bound<-s.Rational(2,10**9)
    assert parameter<s.Rational(1,10000)
    result={
        'reference_Dirichlet_first_and_second_coefficients':'PASS',
        'first_angular_average_zero':'PASS',
        'second_angular_average':str(avg),
        'annulus_second_coefficient':str(annulus),
        'complex_circle_integrand_bound_below_8':True,
        'cubic_remainder_constant':8010,
        'rotation_error_coefficient':str(angular_error),
        'total_remainder_coefficient':coefficient.str(50,more=True),
        'total_remainder_coefficient_below_9':True,
        'parameter_range':'|t| <= 1/10000',
        'conditional_parameter':str(parameter),
        'conditional_log_bound':str(bound),
        'conditional_log_bound_below_minus_2e_9':True,
        'scope':'Algebra and constants for (162); not a complete Bloch counterexample certificate',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    target=Path(__file__).with_name('bloch_shear_refined_energy_check_result.json')
    target.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
