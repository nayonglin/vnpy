"""Explicitly disable both monthly pool and inherited pairwise AI selection."""
import pandas as pd
AI_FLAGS=['enable_ai_product_pool_filter','enable_selection_pairwise_v2','enable_selection_pairwise_v2_catastrophic_veto','enable_selection_pairwise_v2_catastrophic_hard_filter','enable_selection_pairwise_v2_volume_tilt']
AI_FIELDS=['selection_pairwise_score','selection_pairwise_rank','selection_pairwise_enabled','selection_pairwise_veto_flag','selection_pairwise_volume_tilt_applied']
def disable_ai_selection(settings):return {**settings,**{key:False for key in AI_FLAGS}}
def audit_ai_selection_off(strategy,frames,model_load_attempts):
 flags={key:getattr(strategy,key,None) for key in AI_FLAGS}
 runtime_loaded=getattr(strategy,'selection_pairwise_runtime',None) is not None
 monthly_status=getattr(strategy,'ai_product_pool_load_status',None)
 monthly_dates=list(getattr(strategy,'ai_product_pool_eval_dates',[]))
 nonzero=0;by_frame={}
 for name,frame in frames.items():
  hits={col:int((pd.to_numeric(frame[col],errors='coerce').fillna(0).abs()>1e-12).sum()) for col in AI_FIELDS if col in frame}
  if 'selection_pairwise_model_tag' in frame:hits['selection_pairwise_model_tag']=int(frame.selection_pairwise_model_tag.fillna('').astype(str).str.strip().ne('').sum())
  by_frame[name]=hits;nonzero+=sum(hits.values())
 accepted=all(value is False for value in flags.values()) and not runtime_loaded and monthly_status=='disabled' and not monthly_dates and int(model_load_attempts)==0 and nonzero==0
 return dict(schema='stage012_ai_selection_off_v1',accepted=accepted,verdict='PASS_ALL_AI_SELECTION_DISABLED' if accepted else 'REJECT_AI_SELECTION_NOT_DISABLED',flags=flags,model_load_attempts=int(model_load_attempts),runtime_loaded=runtime_loaded,monthly_load_status=monthly_status,monthly_eval_dates=monthly_dates,nonzero_ai_candidate_fields=nonzero,field_counts=by_frame)
