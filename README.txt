Bloch-constant: computational verification materials

These files support the quantitative section of the manuscript
"Bloch's constant conjecture is false" by Teng Zhang (October 10, 2026).
The original numerical programs, results, and run logs are preserved
byte for byte from bloch_quantitative_revision_20261010.zip.

Material-to-manuscript map (LaTeX labels identify the exact statements)

1. Proposition prop:explicitremainder: angular averages and remainder constants
   bloch_quantitative_certificates/bloch_shear_refined_energy_check.py
   bloch_quantitative_certificates/bloch_shear_refined_energy_check_result.json
   The script also records the older parameter 1/64000. That parameter is
   not the paper's t_*=337/20000000; the latter is checked by item 5.

2. Outer annulus: metricweight and gausserror
   bloch_quantitative_certificates/bloch_shear_prym_area_core.py
   bloch_quantitative_certificates/bloch_shear_prym_area_audit.py
   bloch_quantitative_certificates/bloch_shear_prym_area_result.json
   bloch_quantitative_certificates/outer_run.log
   Required completion fields: complete=true and covered_parameter_area="2".

3. Inner disks: innertail and the complete Cauchy circles
   bloch_quantitative_certificates/bloch_shear_prym_inner_audit.py
   bloch_quantitative_certificates/bloch_shear_prym_inner_result.json
   bloch_quantitative_certificates/inner_run.log
   Inner radius 3/4, Cauchy radius 7/8, truncation degree 160.

4. Period integrals and square-root continuation: finiteprojection
   bloch_quantitative_certificates/bloch_shear_prym_period_audit.py
   bloch_quantitative_certificates/bloch_shear_prym_period_result.json
   bloch_quantitative_certificates/period_run.log
   Independent paths at heights h/2 and 7h/10.

5. Combined intervals, Lemma lem:intervalresult, and scalar comparisons
   in Proposition prop:quantitative (certifiedq and quantmain)
   bloch_quantitative_certificate.py
   bloch_quantitative_certificate_result.json
   Includes input/source hashes, D_m, D_m M_*, the two q_C intervals,
   t_*=337/20000000, d_*=113569/40000000000000, Gamma and exponential bounds.

Reproduction

Use Python 3 with python-flint 0.9.0 and SymPy (for the energy algebra).
Install in a virtual environment, for example:

  python -m pip install python-flint==0.9.0 sympy

Run the following commands separately from this repository's root:

  python bloch_quantitative_certificates/bloch_shear_prym_area_audit.py --workers 3 --seconds-limit 7200
  python bloch_quantitative_certificates/bloch_shear_prym_inner_audit.py
  python bloch_quantitative_certificates/bloch_shear_prym_period_audit.py
  python bloch_quantitative_certificates/bloch_shear_refined_energy_check.py
  python bloch_quantitative_certificate.py --certificate-dir bloch_quantitative_certificates

These commands write result JSON files. Run them in a separate checkout
to preserve the recorded results. The outer program must finish with
complete=true and covered_parameter_area="2". An incomplete checkpoint
is not a completed enclosure. Timing and interval midpoints can vary.

Scope and provenance

The programs check the finite-expression interval enclosures and scalar
arithmetic. The geometric construction, analytic identification with q_C,
and the Green-function comparison are arguments in the manuscript.
Historical equation numbers in the unmodified scripts refer to an earlier
draft; use the statement map above for the current manuscript.

This repository omits the archive's old PDF/TeX, old-draft structural checks,
and revision audit. It contains no Lean development. The new manuscript PDF
is supplied separately in the repository; the TeX source is delivered to
the author separately.

SHA256SUMS.txt covers this README and the 14 original verification files.
It excludes itself and the separately supplied manuscript PDF.
The links in the manuscript pin the verification files to their Git commit
so subsequent repository updates cannot silently change the cited evidence.
