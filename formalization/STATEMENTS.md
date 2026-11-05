# Paper-to-Lean statement map

The entry-point files linked below are unchanged copies of the accepted source. They are provided for inspection; use the complete release project to resolve imports and build.

## Theorem 1.1

```lean
AGStrip.main : AGStrip.MainClaim
```

The proof is in [AGStrip/Main.lean](entry/AGStrip/Main.lean). The exact proposition is defined in [AGStrip/MainStatement.lean](entry/AGStrip/MainStatement.lean). It asserts the existence of a normalized Ahlfors–Grunsky function and positive constants together with a normalized holomorphic perturbation family, a strict linear improvement of its Bloch-radius bound, and convergence on compact subsets as the parameter tends to zero from the right. In particular, `blochRadius g = ENNReal.ofReal AG` and, for every `0 < s < δ`, the family satisfies `0 ≤ 1 - c * s` and `blochRadius (f s) ≤ ENNReal.ofReal (AG * (1 - c * s))`. The final declaration has no additional hypotheses.

## Corollary 1.2

```lean
AGStrip.blochConstant_lt_AG :
  AGStrip.blochConstant < ENNReal.ofReal AGStrip.AG
```

The proof is in [AGStrip/SurfaceAGRadiusDescent.lean](entry/AGStrip/SurfaceAGRadiusDescent.lean). It applies the radius-decreasing family to obtain the strict inequality for the Bloch constant.

## Theorem 1.3

```lean
AGStrip.original_quantitative_bloch_bound :
  AGStrip.blochConstant < ENNReal.ofReal (AGStrip.AG - (13 : ℝ) / 10^10)
```

The final entry point is [AGStripQuantitative.lean](entry/AGStripQuantitative.lean). The proved decrement is exactly the paper's rational number `13 / 10^10`, and the final theorem has no additional hypotheses.

## Definitions and trust assumptions

[AGStrip/Definitions.lean](entry/AGStrip/Definitions.lean) defines normalization by holomorphicity on the unit disk, `f 0 = 0`, and `deriv f 0 = 1`. The Bloch radius is the supremum of radii of disks admitting a holomorphic inverse branch into the unit disk. The Bloch constant is the infimum of these radii over normalized functions. These radii use `ENNReal`, so unbounded suprema are represented.

The constant `AG` is

```lean
Real.Gamma (1 / 3 : ℝ) * Real.Gamma (11 / 12 : ℝ) /
  (Real.sqrt (1 + Real.sqrt 3) * Real.Gamma (1 / 4 : ℝ))
```

The recorded type and axiom audits report exactly the standard axiom dependencies `propext`, `Classical.choice`, and `Quot.sound` for all three final declarations. See [verification evidence](VERIFICATION.md) for original commands and logs.

Some comments in the unchanged specification files describe obligations at the time those definitions were introduced. The completed theorem proofs and their acceptance records are indexed above.
