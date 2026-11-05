module
public import AGStripModuleLeaves.BudgetedFinal
import AGStripModuleCore.AuditSupport

set_option maxHeartbeats 100000000
set_option maxRecDepth 1000000

namespace AGStrip

public theorem original_quantitative_bloch_bound :
    blochConstant < ENNReal.ofReal (AG - (13 : ℝ) / 10^10) :=
  BudgetedOuterFinalCertificate.original_quantitative_bloch_bound

end AGStrip

#check @AGStrip.original_quantitative_bloch_bound
#print axioms AGStrip.original_quantitative_bloch_bound
#print AGStrip.Normalized
#print AGStrip.IsInverseBranch
#print AGStrip.blochRadius
#print AGStrip.blochConstant
#print AGStrip.AG
#agstrip_current_module_audit
#agstrip_module_closure_audit
