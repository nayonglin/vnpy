"""Six Stage145 FX Ridge fits after a global zero-column equivalence preflight.

Reuse accepted130 identity/weights/common scalers and B outputs. No old fits,
SQL, native re-export, labels, cash, or global mutation of accepted modules.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util,json,time
from pathlib import Path
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
s=importlib.util.spec_from_file_location('fx147_projection146',TOOLS/'stage146_fx_projection.py');projection=importlib.util.module_from_spec(s);s.loader.exec_module(projection)
s=importlib.util.spec_from_file_location('fx147_accepted130',TOOLS/'stage130_contract_choice_fit.py');accepted=importlib.util.module_from_spec(s);s.loader.exec_module(accepted)
PROTOCOL=projection.PROTOCOL;PROTOCOL_SHA=projection.PROTOCOL_SHA
file_binding=projection.file_binding;read_bound=projection.read_bound;same_binding=projection.same_binding;write_json=projection.write_json;write_csv=projection.write_csv;write_npz=accepted.write_npz
SCOPES=accepted.SCOPES;CUTOFFS=accepted.CUTOFFS;END=accepted.END;PARAMETERS=accepted.PARAMETERS;ARMS=('CONTROL_REUSED','FX')
FEATURE_NAMES=accepted.FEATURE_NAMES+['fx_missing','fx_q_std']
INPUT_ROLES={'actions','common','mothers','dataset_manifest','dataset_terminal','accepted_fit_manifest','accepted_fit_records','accepted_child_scores','accepted_choices_main','accepted_choices_holdout','projection_manifest','projection'}
TRAIN_CHECK=['sequence_index','action_id','net_R_stress','entry_index','exit_index','label_known_date','u_date','family_id','u_action_eligible','label_state']
TRAIN_NUMERIC={'sequence_index','net_R_stress','entry_index','exit_index','u_action_eligible','sample_weight'}

def source_bundle():
 names=['stage146_fx_projection.py','test_stage146_fx_projection.py','stage147_fx_fit.py','test_stage147_fx_fit.py','stage130_contract_choice_fit.py','test_stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py']
 return sorted([file_binding(TOOLS/n) for n in names],key=lambda b:b['path'])

def check_zero_bridge(q,training_indices,forward_indices):
 """Checking the entire forward domain is essential for reused CONTROL scores."""
 q=np.asarray(q,float)
 for name,indices in [('mature_training',training_indices),('complete_forward',forward_indices)]:
  if not np.isfinite(q[np.asarray(indices,int)]).all():raise ValueError('zero-column bridge failed: FXmissing on '+name)
 return True

def scalar_stats(q,weights):
 q=np.asarray(q,float);weights=np.asarray(weights,float)
 if q.shape!=weights.shape or not len(q) or not np.isfinite(weights).all() or (weights<=0).any():raise ValueError('invalid FX scaler weights')
 stats=accepted.legacy.finite_stats(q,weights)
 if stats['finite_count']!=len(q) or not np.isfinite(stats['mean']) or not np.isfinite(stats['var']) or stats['var']<=0 or not np.isfinite(stats['scale']) or stats['scale']<=0:raise ValueError('FX weighted variance must be finite and positive in every fold')
 return stats

def preflight_scalar_cells(cells,on_fit=None):
 """No callback can run until every fold's train-only scalar passes."""
 stats=[scalar_stats(cell['q'],cell['weights']) for cell in cells]
 if on_fit is not None:
  for cell,stat in zip(cells,stats):on_fit(dict(cell,scalar=stat))
 return stats

def design(raw,q,scaler):
 common=accepted.design(raw,scaler);q=np.asarray(q,float);finite=np.isfinite(q)
 scalar=scaler['scalar'];z=np.where(finite,(q-scalar['mean'])/scalar['scale'],0.)
 x=np.column_stack([common,(~finite).astype(float),z])
 if x.shape!=(len(q),54) or not np.isfinite(x).all():raise ValueError('invalid54 FX design')
 return x

def fx_choices(mothers,actions,scores,scope,cutoff):
 # The accepted pure function also builds A as a temporary non-cash result.
 # Keep only B's full-domain selection and give the new model its own arm name.
 choices=accepted.make_choices(mothers,actions,scores,scope,cutoff)
 choices=choices.loc[choices.arm.eq('B')].copy();choices['arm']='FX'
 return choices.reset_index(drop=True)

def held_diagnostics(choices,actions):
 fields=['action_id','label_state','participation_state','net_R_stress','label_known_date']
 linked=choices.merge(actions[fields],left_on='chosen_action_id',right_on='action_id',how='left',validate='many_to_one')
 selected=linked.selected.eq(1);closed=linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)&linked.label_known_date.fillna('').ne('')&linked.label_known_date.fillna('').le(END)
 zero=~selected|linked.participation_state.eq('known_nonparticipation')
 linked['diagnostic_value_R']=np.where(zero,0.,np.where(closed,linked.net_R_stress,np.nan))
 groups={};daily=[];family_rows=[]
 for scope,part in linked.groupby('scope',sort=True):
  family=part.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['arm','family_id','u_index'])
  arms={arm:family.loc[family.arm.eq(arm)].set_index(['family_id','u_index']).sort_index() for arm in ARMS}
  control=arms['CONTROL_REUSED'];fx=arms['FX'].reindex(control.index)
  if len(control)!=len(fx) or fx.u_date.isna().any() or not control.u_date.eq(fx.u_date).all():raise ValueError('held full family-u population mismatch')
  same=control.chosen_action_id.eq(fx.chosen_action_id);known=np.isfinite(control.diagnostic_value_R)&np.isfinite(fx.diagnostic_value_R)
  delta=np.where(same,0.,np.where(known,fx.diagnostic_value_R-control.diagnostic_value_R,np.nan));unknown=~same&~known
  f=pd.DataFrame(dict(family_id=control.index.get_level_values('family_id'),u_index=control.index.get_level_values('u_index'),u_date=control.u_date.to_numpy(),control_chosen_action_id=control.chosen_action_id.to_numpy(),fx_chosen_action_id=fx.chosen_action_id.to_numpy(),control_value_R=control.diagnostic_value_R.to_numpy(),fx_value_R=fx.diagnostic_value_R.to_numpy(),same_action=same.to_numpy(),common_unresolved_same_action=(same&control.chosen_action_id.ne('')&~known).to_numpy(),delta_R=delta,known=np.isfinite(delta),unknown=unknown.to_numpy(),scope=scope))
  family_rows.append(f)
  days=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index();days['scope']=scope;daily.append(days)
  mean=float(days.delta_R.mean()) if days.delta_R.notna().any() else None;nunknown=int(unknown.sum())
  groups[scope]=dict(nominal_pass=mean is not None and mean>=0,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or nunknown else 'supported',known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=nunknown,common_unresolved_same_action=int((same&control.chosen_action_id.ne('')&~known).sum()),full_family_u=len(control),known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(days.delta_R.notna().sum()),selected_by_arm={arm:int(part.loc[part.arm.eq(arm),'selected'].sum()) for arm in ARMS},annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()) if v.delta_R.notna().any() else None,source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum())) for y,v in days.groupby(days.u_date.str[:4])],unknown_R_bounds=None)
 return dict(schema='stage147_fx_held_v1',groups=groups,contrast='FX_minus_CONTROL_REUSED',meaning='full prospective family-u, then equal-u; same unknown action incremental zero with common unresolved disclosure; distinct unknown never zero; not cash',full_policy_cash_qualified=False),pd.concat(daily,ignore_index=True),pd.concat(family_rows,ignore_index=True)

def bound_frame(binding,columns=None,numeric=()):
 if not same_binding(file_binding(binding['path']),binding):raise ValueError('bound frame changed '+binding['path'])
 frame=pd.read_csv(binding['path'],usecols=columns,dtype=str,keep_default_na=False,float_precision='round_trip')
 for col in numeric:
  if col in frame:frame[col]=pd.to_numeric(frame[col],errors='coerce')
 return frame

def load_inputs(inputs):
 fit=json.loads(read_bound(inputs['accepted_fit_manifest']));records=json.loads(read_bound(inputs['accepted_fit_records']))
 if fit.get('schema')!='stage130_contract_choice_fit_v1' or fit.get('status')!='completed' or fit.get('actual_fit_calls_completed')!=6 or fit.get('actual_fit_calls_attempted')!=6:raise ValueError('accepted130 incomplete')
 if fit.get('source_bundle')!=accepted.source_bundle():raise ValueError('accepted130 source identity changed')
 if not same_binding(fit['fit_records'],inputs['accepted_fit_records']):raise ValueError('accepted130 record binding mismatch')
 for role,old_role in [('accepted_child_scores','child_scores'),('accepted_choices_main','choices_main'),('accepted_choices_holdout','choices_holdout')]:
  if not same_binding(inputs[role],fit[old_role]):raise ValueError('accepted130 output reference mismatch '+role)
 for role in accepted.INPUT_ROLES:
  if not same_binding(inputs[role],fit['input_bindings'][role]):raise ValueError('accepted130 input bridge mismatch '+role)
 a,m,common=accepted.load_inputs({role:inputs[role] for role in accepted.INPUT_ROLES})
 if len(a)!=1552456:raise ValueError('full1552456 action domain required')
 pm=json.loads(read_bound(inputs['projection_manifest']))
 if pm.get('schema')!='stage146_fx_projection_v1' or pm.get('status')!='completed' or pm.get('protocol_sha256')!=PROTOCOL_SHA or pm.get('source_bundle')!=projection.source_bundle() or not same_binding(pm['projection'],inputs['projection']) or not same_binding(pm['input_bindings']['mothers'],inputs['mothers']):raise ValueError('projection146 binding mismatch')
 terminal=json.loads(read_bound(pm['terminal']))
 if terminal.get('status')!='completed' or terminal.get('actual_fit_calls_completed')!=0 or terminal.get('native_source_queries')!=0:raise ValueError('projection146 terminal mismatch')
 p=bound_frame(inputs['projection'],projection.IDENTITY+['q','fx_missing'],['sequence_index','u_index','q','fx_missing'])
 for col in projection.IDENTITY:
  if not np.array_equal(p[col].to_numpy(),m[col].to_numpy()):raise ValueError('projection mother identity mismatch '+col)
 missing=~np.isfinite(p.q.to_numpy(float))
 if not np.array_equal(p.fx_missing.to_numpy(),missing.astype(int)):raise ValueError('projection missing state mismatch')
 q=p.q.to_numpy(float)[a.mother_sequence_index.to_numpy(int)]
 return a,m,common,q,records

def prepare_folds(a,m,common,q,records):
 """Validate all six accepted identities and zero-column/scaler bridges first.

The accepted training files are immutable references. Do not reconstruct their
interval-union weights, repeat old fits, or materialize duplicate large X files.
"""
 expected={(scope,cutoff) for scope in SCOPES for cutoff in CUTOFFS}
 if len(records)!=6 or {(r['scope'],r['cutoff']) for r in records}!=expected:raise ValueError('exact six accepted folds required')
 by_key={(r['scope'],r['cutoff']):r for r in records};prepared=[];forward=np.flatnonzero(a.u_date.ge(CUTOFFS[0]).to_numpy())
 for scope in SCOPES:
  for j,cutoff in enumerate(CUTOFFS):
   record=by_key[(scope,cutoff)];next_cutoff=CUTOFFS[j+1] if j+1<len(CUTOFFS) else None
   train,pred,parent=accepted.fold_slices(a,m,cutoff,next_cutoff,scope);ti=train.sequence_index.to_numpy(int);pi=pred.sequence_index.to_numpy(int);mi=parent.sequence_index.to_numpy(int)
   if record['dimension']!=52 or record['training_rows']!=len(ti) or record['prediction_children']!=len(pi) or record['prediction_mothers']!=len(mi):raise ValueError('accepted fold dimensions differ')
   stored=bound_frame(record['training_identity_weights'],TRAIN_CHECK+['sample_weight'],TRAIN_NUMERIC)
   if len(stored)!=len(train):raise ValueError('accepted mature identity length differs')
   for col in TRAIN_CHECK:
    left=stored[col].to_numpy();right=train[col].to_numpy()
    # The target itself comes from the unchanged exact action source. The
    # accepted CSV target is only a serialization cross-check (not a new y).
    equal=np.allclose(left,right,rtol=1e-12,atol=1e-12,equal_nan=True) if col=='net_R_stress' else np.array_equal(left,right,equal_nan=True) if col in TRAIN_NUMERIC else np.array_equal(left,right)
    if not equal:raise ValueError('accepted mature identity/target differs '+col)
   weights=stored.sample_weight.to_numpy(float)
   if not np.isfinite(weights).all() or (weights<=0).any() or not np.isclose(weights.mean(),1.,rtol=1e-12,atol=1e-12):raise ValueError('accepted weights invalid')
   scaler=json.loads(read_bound(record['scaler']));portable=json.loads(read_bound(record['portable_model']))
   if scaler.get('scope')!=scope or scaler.get('cutoff')!=cutoff or scaler.get('feature_names')!=accepted.FEATURE_NAMES or scaler['common']['columns']!=accepted.COMMON:raise ValueError('accepted common scaler identity differs')
   for key in ['mean','var','scale','finite_count']:
    z=np.asarray(scaler['common'][key],float)
    if z.shape!=(26,) or not np.isfinite(z).all() or (key=='scale' and (z<=0).any()):raise ValueError('accepted common scaler malformed')
   if portable.get('parameters')!=PARAMETERS or portable.get('scope')!=scope or portable.get('cutoff')!=cutoff or portable.get('feature_names')!=accepted.FEATURE_NAMES or len(portable['coef'])!=52 or not np.isfinite(np.r_[portable['coef'],portable['intercept']]).all():raise ValueError('accepted portable model bridge differs')
   check_zero_bridge(q,ti,forward)
   prepared.append(dict(scope=scope,cutoff=cutoff,next_cutoff=next_cutoff,training_indices=ti,prediction_indices=pi,parent_indices=mi,weights=weights,common_scaler=scaler,accepted_record=record,q=q[ti]))
   del train,pred,parent,stored
 # Compute every q scaler before returning anything that can be fit.
 stats=preflight_scalar_cells(prepared)
 for cell,stat in zip(prepared,stats):
  cell['scaler']=dict(common=cell['common_scaler']['common'],scalar=stat,feature_names=FEATURE_NAMES,scope=cell['scope'],cutoff=cell['cutoff'],accepted_common_scaler=cell['accepted_record']['scaler'],missing='q nonfinite standardized0 and distinct missing flag; zero bridge demands no missing on mature/forward',weighting='exact accepted130 sample_weight',units='COMMON unchanged original2N; q log CNY_per_USD change')
  del cell['q'];del cell['common_scaler']
 report=dict(schema='stage147_control_zero_column_bridge_v1',status='passed',control_bridge_verified=True,all_six_preflight_before_first_fit=True,common26_binding_reused=True,original52_design='unchanged accepted130.design from exact bound common/scaler',accepted_training_identity_target_weights_reused=True,control_added_columns_identically_zero=True,complete_forward_actions=len(forward),complete_forward_fx_missing=0,control_new_fits=0,control_new_cash_replays=0,folds=[dict(scope=c['scope'],cutoff=c['cutoff'],training_rows=len(c['training_indices']),training_fx_missing=0,prediction_children=len(c['prediction_indices']),prediction_mothers=len(c['parent_indices']),q_scaler=c['scaler']['scalar'],training_identity_weights=c['accepted_record']['training_identity_weights'],common_scaler=c['accepted_record']['scaler'],portable_model=c['accepted_record']['portable_model']) for c in prepared])
 return prepared,report

def fit_cell(a,m,common,q,cell,directory,on_attempt,on_complete):
 scope=cell['scope'];cutoff=cell['cutoff'];ti=cell['training_indices'];pi=cell['prediction_indices'];mi=cell['parent_indices'];weights=cell['weights'];scaler=cell['scaler'];old=cell['accepted_record']
 directory.mkdir(parents=True,exist_ok=False);write_json(directory/'scaler.json',scaler)
 x=design(common[ti],q[ti],scaler);y=a.net_R_stress.to_numpy(float)[ti]
 estimator=accepted.legacy.Ridge(**PARAMETERS);on_attempt(scope,cutoff)
 with accepted.legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=weights)
 on_complete(scope,cutoff)
 z=np.column_stack([x,np.ones(len(x))]);lhs=z.T@(weights[:,None]*z);lhs[np.arange(54),np.arange(54)]+=PARAMETERS['alpha'];rhs=z.T@(weights*y);beta=np.r_[estimator.coef_,estimator.intercept_];residual=lhs@beta-rhs
 if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('FX Ridge sufficient normal equations mismatch')
 write_npz(directory/'normal_equations.npz',lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,weight_sum=np.array(weights.sum()))
 portable=dict(schema='stage147_portable_fx_ridge_v1',scope=scope,cutoff=cutoff,parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_))
 write_json(directory/'portable_model.json',portable)
 with (directory/'model.joblib').open('xb') as f:accepted.legacy.joblib.dump(estimator,f,compress=3)
 del x,z
 xp=design(common[pi],q[pi],scaler);scores=estimator.predict(xp)
 if not np.allclose(scores,xp@np.array(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):raise ValueError('FX portable score mismatch')
 pred=a.iloc[pi];parent=m.iloc[mi]
 child=pred[['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']].copy();child['score']=scores;child['scope']=scope;child['cutoff']=cutoff;child['arm']='FX'
 choices=fx_choices(parent,pred,scores,scope,cutoff)
 record=dict(scope=scope,cutoff=cutoff,training_rows=len(ti),prediction_children=len(pi),prediction_mothers=len(mi),dimension=54,training_identity_weights=old['training_identity_weights'],weight_groups=old['weight_groups'],accepted_common_scaler=old['scaler'],accepted_portable_model=old['portable_model'],accepted_fit_record=old,scaler=file_binding(directory/'scaler.json'),portable_model=file_binding(directory/'portable_model.json'),model=file_binding(directory/'model.joblib'),normal_equations=file_binding(directory/'normal_equations.npz'),normal_equation_max_abs_residual=float(np.max(np.abs(residual))),new_training_identity_copy=False)
 return child,choices,record

def reused_choices(inputs):
 frames=[]
 numeric=['sequence_index','u_index','proposed_score','chosen_action_sequence_index','score','selected']
 for role in ['accepted_choices_main','accepted_choices_holdout']:
  frame=bound_frame(inputs[role],numeric=numeric);frame=frame.loc[frame.arm.eq('B')].copy();frame['arm']='CONTROL_REUSED';frames.append(frame)
 return pd.concat(frames,ignore_index=True)

def verify_population(choices,children,a,m):
 expected=set(m.loc[m.u_date.ge(CUTOFFS[0]),'event_id']);forward=set(a.loc[a.u_date.ge(CUTOFFS[0]),'action_id'])
 main=choices.loc[choices.scope.eq('main')].copy();held=choices.loc[choices.scope.ne('main')].copy()
 for name,frame in [('main',main),('held_union',held)]:
  if len(frame)!=161014*2 or frame.duplicated(['event_id','arm']).any():raise ValueError('full parent forward coverage '+name)
  for arm in ARMS:
   if set(frame.loc[frame.arm.eq(arm),'event_id'])!=expected:raise ValueError('shrunk parent '+name+' '+arm)
 for frame in [children.loc[children.scope.eq('main')],children.loc[children.scope.ne('main')]]:
  if frame.action_id.duplicated().any() or set(frame.action_id)!=forward:raise ValueError('shrunk full prospective FX children')
 return main,held

def authorize(args):
 output=Path(args.output).resolve()
 if output.exists() or LINE/'outputs/stage147_fx_fit' not in output.parents:raise ValueError('fresh Stage147 output required')
 if args.protocol_sha256!=PROTOCOL_SHA or file_binding(args.protocol)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen145 mismatch')
 binding=file_binding(args.authorization)
 if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization hash mismatch')
 auth=json.loads(read_bound(binding));required=dict(schema='stage145_exact_root_authorization_v1',authorized_by='root',stage='fit',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
 if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle() or set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('exact root FX fit authorization mismatch')
 protocol=json.loads(read_bound(file_binding(PROTOCOL)))
 for role in INPUT_ROLES-{'projection_manifest','projection'}:
  if not same_binding(auth['input_bindings'][role],protocol['input_roles'][role]):raise ValueError('frozen fit input role mismatch '+role)
 return output,auth,binding

def run_actual(output,auth,binding):
 output.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();attempts=completed=0
 write_json(output/'actual_started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),authorization=binding,source_bundle=bundle,protocol=file_binding(PROTOCOL)))
 # Files exist even on an early failed bridge, so zero attempts are auditable.
 (output/'fit_attempts.jsonl').touch(exist_ok=False);(output/'fit_completed.jsonl').touch(exist_ok=False)
 def attempt(scope,cutoff):
  nonlocal attempts;attempts+=1
  with (output/'fit_attempts.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,attempt=attempts))+'\n');f.flush()
 def complete(scope,cutoff):
  nonlocal completed;completed+=1
  with (output/'fit_completed.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,completed=completed))+'\n');f.flush()
 try:
  a,m,common,q,old_records=load_inputs(auth['input_bindings'])
  cells,bridge=prepare_folds(a,m,common,q,old_records)
  controls=reused_choices(auth['input_bindings'])
  write_json(output/'bridge_preflight.json',bridge)
  children=[];choices=[controls];records=[]
  for cell in cells:
   child,choice,record=fit_cell(a,m,common,q,cell,output/'folds'/cell['scope']/cell['cutoff'],attempt,complete)
   children.append(child);choices.append(choice);records.append(record)
   print(json.dumps(dict(phase='fx_fit_cell_complete',scope=cell['scope'],cutoff=cell['cutoff'],completed=completed)),flush=True)
  choices=pd.concat(choices,ignore_index=True);children=pd.concat(children,ignore_index=True);main,held=verify_population(choices,children,a,m)
  if attempts!=6 or completed!=6:raise ValueError('exact six new FX fits required')
  held_report,held_daily,held_family_u=held_diagnostics(choices,a)
  bindings={name:write_csv(output/(name+'.csv.gz'),frame) for name,frame in [('choices_main',main),('choices_holdout',held),('child_scores',children),('held_daily',held_daily),('held_family_u',held_family_u)]}
  write_json(output/'held_diagnostic.json',held_report);bindings['held_diagnostic']=file_binding(output/'held_diagnostic.json')
  write_json(output/'fit_records.json',records)
  write_json(output/'summary.json',dict(status='completed',mother_rows=len(m),action_rows=len(a),new_fx_fit_calls_completed=completed,control_fit_calls=0,cash_replays=0,parent_rows_per_arm_main=161014,parent_rows_per_arm_held_union=161014,child_scores=len(children),selected=[dict(scope=scope,arm=arm,selected=int(f.selected.sum())) for (scope,arm),f in choices.groupby(['scope','arm'])],goal_complete=False,production_qualified=False,increased_betting_qualified=False,strict_pit_accepted=False))
  if bundle!=source_bundle():raise ValueError('source changed during FX fitting')
  write_json(output/'actual_terminal.json',dict(status='completed',mode='actual',exit_code=0,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,control_fit_calls=0,native_source_queries=0,cash_replays=0,new_cash_accounts=0,downloads=0,fixture=False,automatic_retry=False,elapsed_seconds=time.monotonic()-started))
  manifest=dict(schema='stage147_fx_fit_v1',status='completed',mode='actual',cash_eligible=True,protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=binding,input_bindings=auth['input_bindings'],projection_manifest=auth['input_bindings']['projection_manifest'],actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,control_fit_calls=0,prediction_mothers_per_arm=161014,prediction_children=len(children),native_source_queries=0,cash_replays=0,fit_records=file_binding(output/'fit_records.json'),bridge_preflight=file_binding(output/'bridge_preflight.json'),summary=file_binding(output/'summary.json'),terminal=file_binding(output/'actual_terminal.json'),reused_child_scores=auth['input_bindings']['accepted_child_scores'],goal_complete=False,production_qualified=False,**bindings)
  manifest['artifacts']={str(p.relative_to(output)):file_binding(p) for p in sorted(output.rglob('*')) if p.is_file()};write_json(output/'manifest.json',manifest);return manifest
 except BaseException as error:
  if not (output/'actual_terminal.json').exists():write_json(output/'actual_terminal.json',dict(status='failed',exit_code=1,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,control_fit_calls=0,native_source_queries=0,cash_replays=0,error_type=type(error).__name__,error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started))
  raise

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ['protocol','protocol-sha256','authorization','authorization-sha256','output']:parser.add_argument('--'+name,required=True)
 args=parser.parse_args(argv);output,auth,binding=authorize(args);result=run_actual(output,auth,binding)
 print(json.dumps(dict(status=result['status'],actual_fit_calls_completed=result['actual_fit_calls_completed'],output=str(output))),flush=True)
if __name__=='__main__':main()
