import AGStrip.SurfaceAGIdentification
import AGStrip.SurfaceAGRadiusDescent

/-! The actual deformation family satisfies the original MainClaim.
No geometric identification or numerical estimate is added as a hypothesis. -/
noncomputable section
namespace AGStrip

theorem main : MainClaim := by
  obtain ⟨p,hp,hΩ,δ,c,f,hn,hδ,hc,hR,hfam,hconv⟩ := strip_actual_AG_radius_decrease
  exact ⟨normalizeAt stripTranslatedFunction p,δ,c,f,
    stripCenter_isAGFunction hp,hδ,hc,hR,hfam,hconv⟩

end AGStrip
