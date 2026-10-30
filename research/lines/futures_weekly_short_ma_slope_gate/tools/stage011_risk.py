"""The only Stage011 alpha delta: three actual base risk ratios become .018.

The .4 capital multiplier is already reflected in these actual ratios.  This
module never changes signal labels, floors, multipliers or any sizing method.
"""
from copy import deepcopy
import math

OLD_RISK={'risk_ratio_volume_open_interest_surge':.06,'risk_ratio_open_interest_surge':.06,'risk_ratio_open_interest_decline':.025}
NEW_RISK={key:.018 for key in OLD_RISK}


def uniform_overrides(settings):
 result=deepcopy(settings)
 for key,old in OLD_RISK.items():
  if key in result and result[key] not in (old,NEW_RISK[key]):raise ValueError('stage011_unknown_original_risk:'+key)
  result[key]=NEW_RISK[key]
 return result


def restore_reference_risk(current,reference):
 """Undo only the declared delta for existing immutable reference audits."""
 result=deepcopy(current)
 for key,old in OLD_RISK.items():
  if result.get(key)!=NEW_RISK[key]:raise ValueError('stage011_actual_risk_not_uniform:'+key)
  if key in reference:
   if reference[key]!=old:raise ValueError('stage011_baseline_risk_changed:'+key)
   result[key]=reference[key]
  else:del result[key]
 return result


def accept_uniform_risk(current,baseline,effective,baseline_effective,entry_risk):
 if len(current)!=1 or len(baseline)!=1:raise ValueError('stage011_exactly_one_strategy_required')
 normalized=deepcopy(current)
 for field in ['setting','actual']:
  normalized[0][field]=restore_reference_risk(current[0][field],baseline[0][field])
 if normalized!=baseline:raise ValueError('stage011_nondeclared_settings_delta')
 actual=current[0]['actual']
 for key in ['risk_ratio_of_total_assets','risk_ratio_breakout','risk_ratio_ma_cross_breakout']:
  if actual.get(key)!=.018:raise ValueError('stage011_regular_risk_changed:'+key)
 preserved={'min_risk_per_trade':1000.,'oi_price_confirm_risk_restore_multiplier':2.,'directional_30d_risk_boost_multiplier':1.5,'directional_30d_low_volume_risk_multiplier':.5}
 if any(actual.get(key)!=value for key,value in preserved.items()):raise ValueError('stage011_preserved_risk_control_missing_or_changed')
 normalized_effective=deepcopy(effective)
 normalized_effective['spec']['overrides']=restore_reference_risk(effective['spec']['overrides'],baseline_effective['spec']['overrides'])
 if normalized_effective!=baseline_effective:raise ValueError('stage011_nondeclared_effective_delta')
 if 'risk_ratio' not in entry_risk:raise ValueError('stage011_entry_risk_ratio_missing')
 for value in entry_risk.risk_ratio:
  if not math.isfinite(float(value)) or not math.isclose(float(value),.018,rel_tol=0,abs_tol=1e-12):raise ValueError('stage011_entry_or_rollover_risk_not_uniform')
 return dict(schema='stage011_uniform_risk_acceptance_v1',accepted=True,actual_risk_overrides={key:actual[key] for key in NEW_RISK},baseline_risk=OLD_RISK,preserved_risk_controls=preserved,only_three_declared_risk_parameters_changed=True,all_other_actual_settings_unchanged=True,all_other_effective_parameters_unchanged=True,capital_risk_multiplier=effective['spec']['capital']['risk_multiplier'],second_risk_multiplier_applied=False,entry_risk_count=len(entry_risk),entry_context_counts={str(k):int(v) for k,v in entry_risk.entry_context.value_counts().items()} if 'entry_context' in entry_risk else {},all_entry_and_rollover_risk_ratios_uniform=True,production_qualified=False)
