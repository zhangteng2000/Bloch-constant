import AGStrip.SurfaceCenterGamma

/-! The actual normalized deformation decreases from the explicit AG
constant. Its identification as an IsAGFunction is a separate obligation. -/
noncomputable section
open Set Filter Complex Topology
open scoped ENNReal
namespace AGStrip

theorem strip_actual_AG_radius_decrease :
    ∃ p ∈ stripDiskCenters, p ∈ stripLowerComplement ∪ stripUpperComplement ∧
      ∃ δ c : ℝ, ∃ f : ℝ → ℂ → ℂ,
      Normalized (normalizeAt stripTranslatedFunction p) ∧ 0 < δ ∧ 0 < c ∧
      blochRadius (normalizeAt stripTranslatedFunction p) = ENNReal.ofReal AG ∧
      (∀ s, 0 < s → s < δ → Normalized (f s) ∧ 0 ≤ 1-c*s ∧
        blochRadius (f s) ≤ ENNReal.ofReal (AG * (1-c*s))) ∧
      CompactConvergenceFromRight f (normalizeAt stripTranslatedFunction p) := by
  obtain ⟨p,hp,hΩ,δ,c,f,hn,_,hδ,hc,hR,hfam,hconv⟩ := strip_actual_strict_radius_decrease
  rw [stripCenterRadius_eq_AG hp] at hR hfam
  exact ⟨p,hp,hΩ,δ,c,f,hn,hδ,hc,hR,hfam,hconv⟩

theorem blochConstant_lt_AG : blochConstant < ENNReal.ofReal AG := by
  obtain ⟨p,hp,hΩ,δ,c,f,hn,hδ,hc,hR,hfam,hconv⟩ := strip_actual_AG_radius_decrease
  have hs : (0 : ℝ) < δ/2 := by linarith
  obtain ⟨hN,_,hb⟩ := hfam (δ/2) hs (by linarith)
  have hlt : AG*(1-c*(δ/2)) < AG := by
    nlinarith [mul_pos hc hs,mul_pos AG_pos (mul_pos hc hs)]
  exact lt_of_le_of_lt (blochConstant_le hN)
    (lt_of_le_of_lt hb ((ENNReal.ofReal_lt_ofReal_iff AG_pos).mpr hlt))

end AGStrip
