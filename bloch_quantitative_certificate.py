"""Recombine fresh Arb certificates and verify an explicit CONDITIONAL gap.

Run the three quadrature programs first, then pass their directory with
--certificate-dir. No analytic identification of the finite expression
with the Bloch variation is certified by this arithmetic program.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work' / 'deps'))
from flint import arb, acb, ctx


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rat(x):
    return arb(x.numerator) / x.denominator


def complex_ball(pair):
    return acb(arb(pair[0]), arb(pair[1]))


def ball_text(x):
    return x.str(65, more=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--certificate-dir', type=Path,
                        default=Path(__file__).with_name('bloch_quantitative_certificates'))
    parser.add_argument('--out', type=Path,
                        default=Path(__file__).with_name('bloch_quantitative_certificate_result.json'))
    args = parser.parse_args()
    ctx.prec = 256
    certdir = args.certificate_dir.resolve()
    inputs = ['bloch_shear_prym_area_result.json',
              'bloch_shear_prym_inner_result.json',
              'bloch_shear_prym_period_result.json']
    outer, inner, period = [json.loads((certdir / name).read_text(encoding='utf-8'))
                            for name in inputs]
    assert outer['complete'] is True
    assert outer['covered_parameter_area'] == '2'
    assert outer['inner_xi_radius'] == inner['inner_xi_radius'] == '3/4'
    assert inner['Cauchy_xi_radius'] == '7/8'
    assert len(inner['details']) == 2
    assert all(row['order'] == 160 for row in inner['details'])
    for name, expected in outer['source_sha256'].items():
        assert digest(certdir / name) == expected, name
    assert period['precision_bits'] >= 128
    assert len(period['periods']) == 2
    assert period['strict_positive_real_square_root_segment_checks'] > 0
    assert period['two_point_gauss_cells_with_fourth_derivative_bounds'] > 0
    for row in period['periods']:
        assert complex_ball(row['root_closure']).contains(0)

    denominator = complex_ball(outer['denominator']) + complex_ball(inner['denominator'])
    numerator = complex_ball(outer['numerator']) + complex_ball(inner['numerator'])
    assert denominator.real > 0 and denominator.imag.contains(0)
    mean = numerator / denominator.real
    q = [arb(3).sqrt() / (4 * arb.pi()) *
         (complex_ball(row['alpha0']) - mean * complex_ball(row['eta'])).imag
         for row in period['periods']]
    assert q[0].overlaps(q[1])
    a = Fraction(337, 10**6)
    assert all(-arb(370) / 10**6 < value < -rat(a) for value in q)

    # This implication requires the two analytic hypotheses in the output.
    t = a / 20
    decrease = a*a / 40
    assert t == Fraction(337, 20_000_000)
    assert 0 < t < Fraction(1, 10000)
    assert -a*t + 10*t*t == -decrease
    assert decrease == Fraction(113569, 40_000_000_000_000)
    A = ((arb(1)/3).gamma() * (arb(11)/12).gamma() /
         ((1+arb(3).sqrt()).sqrt() * (arb(1)/4).gamma()))
    U = Fraction(471861652113, 10**12)
    gap = Fraction(13, 10**10)
    expression = A * (-rat(decrease)).exp()
    assert expression < rat(U) < A - rat(gap)
    assert arb('0.47186165345268178487') < A < arb('0.47186165345268178488')
    assert arb('0.47186165211296038375') < expression < arb('0.47186165211296038376')
    remainder = (arb(18)/5 + arb(1)/16 + arb(50).log()
                 + (arb(1)/2+arb(801)/1000)*arb(2).log())
    assert remainder < arb(8477)/1000 < 9

    sources = ['bloch_shear_prym_area_core.py', 'bloch_shear_prym_area_audit.py',
               'bloch_shear_prym_inner_audit.py', 'bloch_shear_prym_period_audit.py']
    result = {
        'status': 'PASS: finite-expression intervals and CONDITIONAL gap arithmetic',
        'not_an_unconditional_Bloch_counterexample_certificate': True,
        'required_analytic_hypotheses': [
            'The finite projection in (8.13) equals q_C for the compact-cylinder family.',
            'The normalized holomorphic family satisfies (8.9): '
            'log(b(f_t)/A_AG) <= t*q_C + 10*t^2 for 0 < t <= 1/10000.'
        ],
        'quadrature_inputs': 'Fresh full reruns on 2026-10-10; no resumed area checkpoint',
        'area_cover_complete': True,
        'area_accepted_rectangles': outer['accepted'],
        'area_attempts': outer['attempts'],
        'area_seconds': outer['seconds'],
        'inner_seconds': inner['seconds'],
        'period_seconds': period['seconds'],
        'precision_bits_recombination': ctx.prec,
        'denominator_real': ball_text(denominator.real),
        'numerator': [ball_text(numerator.real), ball_text(numerator.imag)],
        'projection_mean': [ball_text(mean.real), ball_text(mean.imag)],
        'q_projection_intervals': [ball_text(value) for value in q],
        'strict_q_bounds': ['-370/1000000', '-337/1000000'],
        'explicit_parameter': str(t),
        'strict_logarithmic_decrease': str(decrease),
        'analytic_remainder_constant_arithmetic': ball_text(remainder),
        'A_AG': ball_text(A),
        'conditional_upper_expression': ball_text(expression),
        'conditional_upper_rational': str(U),
        'conditional_upper_decimal': '0.471861652113',
        'conditional_gap_lower_bound': str(gap),
        'A_AG_minus_upper_expression': ball_text(A-expression),
        'A_AG_minus_upper_rational': ball_text(A-rat(U)),
        'input_sha256': {name: digest(certdir/name) for name in inputs},
        'source_sha256': {name: digest(certdir/name) for name in sources},
        'recombiner_sha256': digest(Path(__file__).resolve()),
    }
    args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
