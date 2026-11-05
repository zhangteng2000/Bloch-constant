import Mathlib.Analysis.Complex.Basic
import Mathlib.Analysis.SpecialFunctions.Gamma.Basic
import Mathlib.Data.ENNReal.Real
import Mathlib.Topology.UniformSpace.LocallyUniformConvergence
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

/-! Faithful definitions. Total functions are used with explicit open domains.
The radius lives in `ℝ≥0∞`, so an unbounded set of radii has supremum `∞`.
-/
noncomputable section
open Set Filter
open scoped Topology ENNReal

namespace AGStrip

def unitDisk : Set ℂ := Metric.ball 0 1

def HolomorphicOnDisk (f : ℂ → ℂ) : Prop := DifferentiableOn ℂ f unitDisk

def Normalized (f : ℂ → ℂ) : Prop :=
  HolomorphicOnDisk f ∧ f 0 = 0 ∧ deriv f 0 = 1

def IsInverseBranch (f ψ : ℂ → ℂ) (w : ℂ) (r : ℝ) : Prop :=
  DifferentiableOn ℂ ψ (Metric.ball w r) ∧
  MapsTo ψ (Metric.ball w r) unitDisk ∧
  ∀ ξ ∈ Metric.ball w r, f (ψ ξ) = ξ

def HasInverseDisk (f : ℂ → ℂ) (w : ℂ) (r : ℝ) : Prop :=
  0 < r ∧ ∃ ψ : ℂ → ℂ, IsInverseBranch f ψ w r

def admissibleRadii (f : ℂ → ℂ) : Set ℝ≥0∞ :=
  {ρ | ∃ r : ℝ, ρ = ENNReal.ofReal r ∧ ∃ w : ℂ, HasInverseDisk f w r}

def blochRadius (f : ℂ → ℂ) : ℝ≥0∞ := sSup (admissibleRadii f)

def blochConstant : ℝ≥0∞ := sInf {ρ | ∃ f : ℂ → ℂ, Normalized f ∧ ρ = blochRadius f}

def AG : ℝ :=
  Real.Gamma (1 / 3 : ℝ) * Real.Gamma (11 / 12 : ℝ) /
    (Real.sqrt (1 + Real.sqrt 3) * Real.Gamma (1 / 4 : ℝ))

def CompactConvergenceFromRight (f : ℝ → ℂ → ℂ) (g : ℂ → ℂ) : Prop :=
  ∀ K : Set ℂ, IsCompact K → K ⊆ unitDisk →
    TendstoUniformlyOn f g (𝓝[>] (0 : ℝ)) K

theorem inverseBranch_injective {f ψ : ℂ → ℂ} {w : ℂ} {r : ℝ}
    (h : IsInverseBranch f ψ w r) : InjOn ψ (Metric.ball w r) := by
  intro x hx y hy hxy
  calc
    x = f (ψ x) := (h.2.2 x hx).symm
    _ = f (ψ y) := congrArg f hxy
    _ = y := h.2.2 y hy

theorem inverseDisk_radius_le {f : ℂ → ℂ} {w : ℂ} {r : ℝ}
    (h : HasInverseDisk f w r) : ENNReal.ofReal r ≤ blochRadius f := by
  exact le_sSup ⟨r, rfl, w, h⟩

theorem blochRadius_le_iff (f : ℂ → ℂ) (R : ℝ≥0∞) :
    blochRadius f ≤ R ↔ ∀ w r, HasInverseDisk f w r → ENNReal.ofReal r ≤ R := by
  constructor
  · intro h w r hr
    exact (inverseDisk_radius_le hr).trans h
  · intro h
    apply sSup_le
    rintro ρ ⟨r, rfl, w, hr⟩
    exact h w r hr

theorem blochConstant_le {f : ℂ → ℂ} (h : Normalized f) :
    blochConstant ≤ blochRadius f := by
  exact sInf_le ⟨f, h, rfl⟩

theorem AG_denominator_pos :
    0 < Real.sqrt (1 + Real.sqrt 3) * Real.Gamma (1 / 4 : ℝ) := by
  have hg : 0 < Real.Gamma (1 / 4 : ℝ) := Real.Gamma_pos_of_pos (by norm_num)
  have hs : 0 < Real.sqrt (1 + Real.sqrt 3) := Real.sqrt_pos.2 (by positivity)
  exact mul_pos hs hg

theorem AG_denominator_ne_zero :
    Real.sqrt (1 + Real.sqrt 3) * Real.Gamma (1 / 4 : ℝ) ≠ 0 :=
  ne_of_gt AG_denominator_pos

theorem AG_pos : 0 < AG := by
  unfold AG
  exact div_pos (mul_pos (Real.Gamma_pos_of_pos (by norm_num))
    (Real.Gamma_pos_of_pos (by norm_num))) AG_denominator_pos

theorem normalized_id : Normalized (fun z : ℂ => z) := by
  refine ⟨?_, rfl, ?_⟩
  · exact differentiable_id.differentiableOn
  · simp

end AGStrip
