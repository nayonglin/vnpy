"""Append independently reviewed reference evidence to the frozen source.
This wrapper changes no signal, fill, ledger, calendar, C2 or model rule.
"""
from datetime import datetime
import hashlib,json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage058_minute_evidence_adapter as adapter

LINE=Path(__file__).resolve().parents[1]
OLD=LINE/'outputs/stage056_uniform_minute_input_audit/run_20261020_222826_843552/qualified_inputs_manifest.json'
NEW=LINE/'outputs/stage067_followup_minute_input_audit/qualified_inputs_manifest.json'
OLD_REVIEW=LINE/'outputs/stage057_independent_minute_qualification_review/review.json'
UNION=LINE/'outputs/stage073_reviewed_evidence_union'
SOURCE=LINE/'outputs/stage073_union_augmented_source'
PREVIOUS=LINE/'outputs/stage058_minute_augmented_source/monthly_coldstart_coverage.csv'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def reviewed_union(a,b,ra,rb):
 groups=[];bindings=[];events=set()
 for manifest,review,flag in [(a,ra,'accepts_stage056_inputs'),(b,rb,'accepts_stage067_inputs')]:
  r=json.loads(Path(review).read_text());digest=sha(manifest)
  if r.get(flag) is not True or r.get('qualified_inputs_manifest_sha256')!=digest or any(r.get('unresolved_'+level)!=0 for level in ['P0','P1','P2']):raise ValueError('independent_exact_input_review_required:'+flag)
  rows=json.loads(Path(manifest).read_text())
  if not isinstance(rows,list) or not rows:raise ValueError('nonempty_manifest_required')
  # The two additions are different epoch-days from the old117. Nothing is replaced.
  own={item['requirement_id'] for item in rows}
  if own&events:raise ValueError('evidence_events_overlap_no_replacement_allowed')
  events|=own;groups.extend(rows);bindings.append(dict(manifest=str(Path(manifest).resolve()),manifest_sha256=digest,review=str(Path(review).resolve()),review_sha256=sha(review),accepted_items=len(rows),acceptance_field=flag))
 return groups,bindings

def assert_known_preserved(old,new,expected=4762):
 mask=old.asof_eligible&old.maturity_clock_reached&old.all_paths_value_known&old.cumulative_net_r.notna()
 if int(mask.sum())!=expected or len(old)!=len(new):raise ValueError('previous_row_or_known_count_changed')
 for col in ['cumulative_net_r','cumulative_gross_r','net_r_min','net_r_max']:
  if not np.array_equal(old.loc[mask,col].to_numpy(dtype='float64').view('uint64'),new.loc[mask,col].to_numpy(dtype='float64').view('uint64')):raise ValueError('known_float_bits_changed:'+col)
 for col in ['status','path_count','known_paths','all_paths_value_known','episodes']:
  if not old.loc[mask,col].equals(new.loc[mask,col]):raise ValueError('known_state_changed:'+col)
 return dict(old_known_preserved=expected,old_known_four_float64_bits_and_states_unchanged=True)

def run(new_review,workers=4):
 if UNION.exists() or SOURCE.exists():raise ValueError('immutable_output_exists')
 rows,reviews=reviewed_union(OLD,NEW,OLD_REVIEW,new_review)
 if len(rows)!=119 or reviews[0]['accepted_items']!=117 or reviews[1]['accepted_items']!=2:raise ValueError('frozen_119_scope_mismatch')
 # The unchanged index independently validates every snapshot, canonical grid,
 # OHLC, source membership and identity in the two accepted manifests.
 locked={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage073_reviewed_union_source.py'),OLD,NEW,OLD_REVIEW,Path(new_review),PREVIOUS,LINE/'tools/stage039_continuous_source.py',LINE/'tools/stage042_coldstart_coverage.py',LINE/'tools/stage055_minute_input_qualification.py',Path(adapter.__file__)]}
 started=now();UNION.mkdir(parents=True)
 manifest=UNION/'qualified_inputs_manifest.json';manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 digest=sha(manifest);receipt=UNION/'independent_parent_reviews.json'
 receipt.write_text(json.dumps(dict(issued_at=now(),qualified_inputs_manifest_sha256=digest,parents=reviews,reference_policy_grid_only=True,physical_session_verified=False,usable_for_trading=False),ensure_ascii=False,indent=2)+'\n')
 (UNION/'summary.json').write_text(json.dumps(dict(accepted_items=119,new_items=2,parent_reviews=reviews,source_policy_changed=False,physical_session_verified=False),ensure_ascii=False,indent=2)+'\n')
 def union_gate(path,actual_digest):
  if Path(path).resolve()!=receipt.resolve() or actual_digest!=digest or sha(manifest)!=digest:raise ValueError('union_identity_drift')
  checked,parents=reviewed_union(OLD,NEW,OLD_REVIEW,new_review)
  if checked!=rows or parents!=reviews or json.loads(receipt.read_text()).get('qualified_inputs_manifest_sha256')!=digest:raise ValueError('union_parent_review_drift')
  return json.loads(receipt.read_text())
 old_out=adapter.OUT;old_gate=adapter.validate_review_gate
 adapter.OUT=SOURCE;adapter.validate_review_gate=union_gate
 try:adapter.run(manifest,receipt,workers)
 finally:adapter.OUT=old_out;adapter.validate_review_gate=old_gate
 old=pd.read_csv(PREVIOUS,float_precision='round_trip');new=pd.read_csv(SOURCE/'monthly_coldstart_coverage.csv',float_precision='round_trip')
 proof=assert_known_preserved(old,new)
 mask=new.asof_eligible&new.maturity_clock_reached&new.all_paths_value_known&new.cumulative_net_r.notna()
 previous=old.asof_eligible&old.maturity_clock_reached&old.all_paths_value_known&old.cumulative_net_r.notna()
 changed=(old.status!=new.status)|(old.first_unknown_day.fillna('')!=new.first_unknown_day.fillna(''))|(old.first_unknown_reason.fillna('')!=new.first_unknown_reason.fillna(''))
 old.add_prefix('old_').join(new.add_prefix('new_')).loc[changed].to_csv(SOURCE/'changes_from058.csv',index=False)
 for path,digest0 in locked.items():
  if sha(path)!=digest0:raise ValueError('locked_input_changed:'+path)
 result=dict(started_at=started,completed_at=now(),**proof,all_rows=19698,mature_point_known=int(mask.sum()),new_mature_point_known=int((mask&~previous).sum()),changed_first_block_or_status=int(changed.sum()),mature_unknown=int((new.asof_eligible&new.maturity_clock_reached&~mask).sum()),new_manifest_sha256=sha(manifest),parent_reviews=reviews,locked_sha256=locked,model_fits=0,source_runs=1,production_changes=0,orders=0,physical_session_verified=False,usable_for_trading=False,source_policy_changed=False,independent_source_review_pending=True)
 (SOURCE/'append_evidence_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['locked_sha256','parent_reviews']},ensure_ascii=False),flush=True)
 return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--new-review',required=True);args=p.parse_args();run(Path(args.new_review))
