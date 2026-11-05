import AGStrip.Definitions
import AGStrip.Triangle

noncomputable section
open Set
open scoped ENNReal

namespace AGStrip

/-- Three unit directions, counterclockwise. -/
def triangleDirection : Fin 3 → ℂ :=
  ![1, ⟨-1 / 2, stripHeight⟩, ⟨-1 / 2, -stripHeight⟩]

/-- Disk-model vertex radius for the equilateral hyperbolic π/6 triangle.
The full hyperbolic-angle identification is an outstanding geometry obligation. -/
def hyperbolicVertexRadius : ℝ := 1 / Real.sqrt (1 + Real.sqrt 3)

def hyperbolicVertex (j : Fin 3) : ℂ :=
  (hyperbolicVertexRadius : ℂ) * triangleDirection j

/-- Center of the circle supporting the geodesic opposite vertex j. -/
def geodesicCircleCenter (j : Fin 3) : ℂ :=
  (-(hyperbolicVertexRadius + 1 / hyperbolicVertexRadius) : ℝ) * triangleDirection j

def canonicalHyperbolicTriangle : Set ℂ :=
  {z | z ∈ unitDisk ∧ ∀ j : Fin 3,
    Real.sqrt (‖geodesicCircleCenter j‖ ^ 2 - 1) < ‖z - geodesicCircleCenter j‖}

def euclideanVertex (j : Fin 3) : ℂ :=
  (1 / Real.sqrt 3 : ℝ) * triangleDirection j

def canonicalEuclideanTriangle : Set ℂ :=
  interior (convexHull ℝ (range euclideanVertex))

/-- A geometric/analytic specification of the AG function: a globally holomorphic
extension of the vertex-preserving conformal triangle map, normalized at its center,
with a source rotation allowed. No Bloch-radius equality occurs in this definition.
The correspondence with the Schwarz-reflection construction still needs proof.
-/
def IsAGFunction (g : ℂ → ℂ) : Prop :=
  Normalized g ∧ ∃ (F : ℂ → ℂ) (u : ℂ),
    HolomorphicOnDisk F ∧
    BijOn F canonicalHyperbolicTriangle canonicalEuclideanTriangle ∧
    (∀ j : Fin 3, F (hyperbolicVertex j) = euclideanVertex j) ∧
    F 0 = 0 ∧ deriv F 0 ≠ 0 ∧ ‖u‖ = 1 ∧
    ∀ z ∈ unitDisk, g z = F (u * z) / (u * deriv F 0)

/-- The target, not a proof: includes every positive sufficiently small parameter,
normalization, exact AG radius, and uniform convergence on every compact subset.
The explicit nonnegative factor prevents `ENNReal.ofReal` truncation from weakening
the intended real radius estimate. -/
def MainClaim : Prop :=
  ∃ (g : ℂ → ℂ) (δ c : ℝ) (f : ℝ → ℂ → ℂ),
    IsAGFunction g ∧ 0 < δ ∧ 0 < c ∧
    blochRadius g = ENNReal.ofReal AG ∧
    (∀ s, 0 < s → s < δ →
      Normalized (f s) ∧ 0 ≤ 1 - c * s ∧
      blochRadius (f s) ≤ ENNReal.ofReal (AG * (1 - c * s))) ∧
    CompactConvergenceFromRight f g

theorem hyperbolicVertexRadius_pos : 0 < hyperbolicVertexRadius := by
  unfold hyperbolicVertexRadius
  positivity

theorem hyperbolicVertexRadius_lt_one : hyperbolicVertexRadius < 1 := by
  unfold hyperbolicVertexRadius
  have h0 : 0 < Real.sqrt (1 + Real.sqrt 3) := by positivity
  have h1 := Real.sq_sqrt (show 0 ≤ 1 + Real.sqrt 3 by positivity)
  have h3 : 0 < Real.sqrt 3 := by positivity
  apply (div_lt_one h0).mpr
  nlinarith

/-- Only a logical consequence of the target specification. This is deliberately
not named `blochConstant_lt_AG`, since existence of the family remains unproved. -/
theorem blochConstant_lt_of_mainClaim (h : MainClaim) :
    blochConstant < ENNReal.ofReal AG := by
  obtain ⟨g, δ, c, f, _, hδ, hc, _, hf, _⟩ := h
  have hs : (0 : ℝ) < δ / 2 := by linarith
  obtain ⟨hnorm, _, hbound⟩ := hf (δ / 2) hs (by linarith)
  have hlt : AG * (1 - c * (δ / 2)) < AG := by
    nlinarith [mul_pos hc hs, mul_pos AG_pos (mul_pos hc hs)]
  exact lt_of_le_of_lt (blochConstant_le hnorm)
    (lt_of_le_of_lt hbound ((ENNReal.ofReal_lt_ofReal_iff AG_pos).mpr hlt))

end AGStrip
