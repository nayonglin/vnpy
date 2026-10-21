"""128 frozen shared six-Ridge initial contract action selection. No SQL or old models.

Both arms share prospective action scores. Only exact-product month choice differs;
ordinary/F family priority, u eligibility and training are identical.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage128_contract_choice_protocol/protocol.json'
PROTOCOL_SHA='bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0'
s=importlib.util.spec_from_file_location('fit130_accepted071',TOOLS/'stage071_settlement_narrow_fit.py')
legacy=importlib.util.module_from_spec(s);s.loader.exec_module(legacy)
COMMON=legacy.COMMON;IDENTITY=legacy.IDENTITY
FEATURE_NAMES=COMMON+[c+'_missing' for c in COMMON]
SCOPES=('main','holdout_0','holdout_1');ARMS=('A','B');CUTOFFS=('2020-01-01','2023-01-01');END='2026-10-16'
PARAMETERS=dict(alpha=1.,fit_intercept=True,solver='cholesky')
file_binding=legacy.file_binding;read_bound=legacy.read_bound;write_json=legacy.write_json;write_csv=legacy.write_csv;write_npz=legacy.write_npz
ACTION_COLUMNS=list(dict.fromkeys(legacy.LABEL_COLUMNS+['action_sequence_index','action_id','actual_epoch','mother_sequence_index','mother_event_id','anchor_epoch','u_action_eligible','entry_capacity_qty','participation_state']))
NUMERIC=['sequence_index','action_sequence_index','mother_sequence_index','u_index','entry_index','exit_index','net_R_stress','label_history_ready20','u_action_eligible','entry_capacity_qty']
INPUT_ROLES={'dataset_manifest','actions','common','mothers','dataset_terminal'}
def family_group(v):return int(hashlib.sha256(str(v).encode()).hexdigest(),16)%2
def source_bundle():return sorted([file_binding(TOOLS/n) for n in ['stage130_contract_choice_fit.py','test_stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py']],key=lambda b:b['path'])
def union_intervals(intervals):
 result=[]
 for s,e in sorted(intervals):
  if s<0 or e<s:raise ValueError('invalid mature interval')
  if result and s<=result[-1][1]+1:result[-1][1]=int(max(result[-1][1],e))
  else:result.append([int(s),int(e)])
 return result

def training_weights(train):
 """Each family-u interval union counts once, then split group mass over months."""
 f=train.reset_index(drop=True);group_ids=np.empty(len(f),np.int64);records=[]
 for gid,((family,u),idx) in enumerate(f.groupby(['family_id','u_date'],sort=True,observed=True).indices.items()):
  ii=np.asarray(idx,int);starts=f.entry_index.to_numpy()[ii];ends=f.exit_index.to_numpy()[ii]
  if not np.isfinite(starts).all() or not np.isfinite(ends).all() or not np.equal(starts,np.floor(starts)).all() or not np.equal(ends,np.floor(ends)).all():raise ValueError('noninteger mature interval')
  merged=union_intervals(zip(starts.astype(int),ends.astype(int)));group_ids[ii]=gid
  records.append(dict(group_id=gid,family_id=family,u_date=u,member_count=len(ii),union_intervals=merged,union_length=sum(e-s+1 for s,e in merged)))
 if not records:raise ValueError('empty mature training')
 by_family={}
 for r in records:by_family.setdefault(r['family_id'],[]).append(r)
 for rs in by_family.values():
  last=max(e for r in rs for _,e in r['union_intervals']);delta=np.zeros(last+2,dtype=np.int64)
  for r in rs:
   for s,e in r['union_intervals']:delta[s]+=1;delta[e+1]-=1
  concurrency=np.cumsum(delta[:-1]);inv=np.zeros(len(concurrency));np.divide(1.,concurrency,out=inv,where=concurrency>0);prefix=np.r_[0.,np.cumsum(inv)]
  for r in rs:r['uniqueness']=float(sum(prefix[e+1]-prefix[s] for s,e in r['union_intervals'])/r['union_length'])
 g=pd.DataFrame(records);count=g.member_count.to_numpy()[group_ids];uniq=g.uniqueness.to_numpy()[group_ids];base=uniq/count
 totals=pd.Series(base).groupby(f.u_date,sort=False).transform('sum').to_numpy();p=base/totals;w=p/p.mean()
 if not np.isfinite(w).all() or (w<=0).any():raise ValueError('invalid union weights')
 out=pd.DataFrame(dict(group_id=group_ids,group_member_count=count,group_union_length=g.union_length.to_numpy()[group_ids],group_uniqueness=uniq,base_weight=base,day_weight_total=totals,sample_weight=w))
 g['union_intervals']=g.union_intervals.map(lambda v:json.dumps(v,separators=(',',':')))
 return out,g

def fold_slices(frame,mothers,cutoff,next_cutoff,scope):
 train=frame.loc[frame.u_action_eligible.eq(1)&frame.label_state.eq('closed_complete_bar_model')&frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)&np.isfinite(frame.net_R_stress)].copy()
 pred=frame.loc[frame.u_date.ge(cutoff)&(frame.u_date.lt(next_cutoff) if next_cutoff else True)].copy()
 parent=mothers.loc[mothers.u_date.ge(cutoff)&(mothers.u_date.lt(next_cutoff) if next_cutoff else True)].copy()
 if scope!='main':
  group=int(scope[-1]);train=train.loc[train.family_id.map(family_group).ne(group)].copy();pred=pred.loc[pred.family_id.map(family_group).eq(group)].copy();parent=parent.loc[parent.family_id.map(family_group).eq(group)].copy()
 if train.empty or pred.empty or parent.empty:raise ValueError('empty fixed fold')
 return train,pred,parent

def design(raw,scaler):
 x=np.asarray(raw,float);mu=np.array(scaler['common']['mean']);sd=np.array(scaler['common']['scale']);finite=np.isfinite(x)
 z=np.column_stack([np.where(finite,(x-mu)/sd,0.),(~finite).astype(float)])
 if z.shape!=(len(x),52) or not np.isfinite(z).all():raise ValueError('invalid52 design')
 return z

def make_choices(mothers,actions,scores,scope,cutoff):
 if len(actions)!=len(scores) or not np.isfinite(scores).all():raise ValueError('score identity/finite mismatch')
 a=actions.copy();a['score']=scores
 results=[]
 for arm in ARMS:
  eligible=a.u_action_eligible.eq(1)&a.score.gt(0)
  if arm=='A':eligible &= a.reference_epoch.eq(a.anchor_epoch)
  candidates=a.loc[eligible].sort_values(['mother_sequence_index','score','reference_epoch','action_id'],ascending=[True,False,True,True],kind='stable').drop_duplicates('mother_sequence_index')
  candidates['is_F']=candidates.product_id.str.endswith('_F').astype(int)
  winners=candidates.sort_values(['u_index','family_id','is_F','product_id','reference_epoch','action_id'],kind='stable').drop_duplicates(['family_id','u_index'])
  out=mothers.copy();idx=out.sequence_index
  proposed=candidates.set_index('mother_sequence_index');win=winners.set_index('mother_sequence_index')
  out['proposed_action_id']=idx.map(proposed.action_id).fillna('');out['proposed_epoch']=idx.map(proposed.reference_epoch).fillna('');out['proposed_score']=idx.map(proposed.score)
  out['chosen_action_id']=idx.map(win.action_id).fillna('');out['chosen_action_sequence_index']=idx.map(win.action_sequence_index).fillna(-1).astype(np.int64)
  out['chosen_epoch']=idx.map(win.reference_epoch).fillna('');out['anchor_epoch']=out.reference_epoch
  out['score']=idx.map(win.score);out['selected']=out.chosen_action_id.ne('').astype(np.int8)
  observed=set(a.mother_sequence_index)
  out['selection_state']=np.select([out.selected.eq(1),out.proposed_action_id.ne(''),~idx.isin(observed)],['selected','family_priority_suppressed','no_observed_children'],default='no_eligible_positive_action')
  out['scope']=scope;out['cutoff']=cutoff;out['arm']=arm;out['policy']='NARROW'
  if out.loc[out.selected.eq(1)].duplicated(['family_id','u_index']).any():raise ValueError('multiple family actions')
  results.append(out)
 return pd.concat(results,ignore_index=True)

def held_diagnostics(choices,actions):
 fields=['action_id','label_state','participation_state','net_R_stress','label_known_date']
 linked=choices.merge(actions[fields],left_on='chosen_action_id',right_on='action_id',how='left',validate='many_to_one')
 selected=linked.selected.eq(1);closed=linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)&linked.label_known_date.fillna('').ne('')&linked.label_known_date.fillna('').le(END)
 zero=~selected|linked.participation_state.eq('known_nonparticipation')
 linked['diagnostic_value_R']=np.where(zero,0.,np.where(closed,linked.net_R_stress,np.nan))
 groups={};daily=[]
 for scope,part in linked.groupby('scope',sort=True):
  # Collapse ordinary/F duplicate mothers using precisely the prospective family winner.
  family=part.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['arm','family_id','u_index'])
  arms={arm:family.loc[family.arm.eq(arm)].set_index(['family_id','u_index']).sort_index() for arm in ARMS};aa=arms['A'];bb=arms['B'].reindex(aa.index)
  if len(aa)!=len(bb) or bb.u_date.isna().any() or not aa.u_date.eq(bb.u_date).all():raise ValueError('held family population mismatch')
  same=aa.chosen_action_id.eq(bb.chosen_action_id);known=np.isfinite(aa.diagnostic_value_R)&np.isfinite(bb.diagnostic_value_R)
  delta=np.where(same,0.,np.where(known,bb.diagnostic_value_R-aa.diagnostic_value_R,np.nan));unknown=~same&~known
  f=pd.DataFrame(dict(u_date=aa.u_date.to_numpy(),delta_R=delta,known=np.isfinite(delta),unknown=unknown.to_numpy()))
  days=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index();days['scope']=scope;daily.append(days)
  mean=float(days.delta_R.mean()) if days.delta_R.notna().any() else None;nunknown=int(unknown.sum())
  groups[scope]=dict(nominal_pass=mean is not None and mean>=0,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or nunknown else 'supported',known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=nunknown,common_unresolved_same_action=int((same&aa.chosen_action_id.ne('')&~known).sum()),full_family_u=len(aa),known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(days.delta_R.notna().sum()),
   selected_by_arm={a:int(part.loc[part.arm.eq(a),'selected'].sum()) for a in ARMS},annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()) if v.delta_R.notna().any() else None,source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum())) for y,v in days.groupby(days.u_date.str[:4])],unknown_R_bounds=None)
 return dict(schema='stage130_prospective_choice_held_v1',groups=groups,contrast='B_minus_A',meaning='actual pre-outcome chosen action; same action incremental zero with unresolved disclosure; distinct unknown never zero; family-u then equal-u; not cash',full_policy_cash_qualified=False),pd.concat(daily,ignore_index=True),linked

def read_csv(binding,columns,numeric=()):
 if not legacy.same_binding(file_binding(binding['path']),binding):raise ValueError('input binding changed '+binding['path'])
 frame=pd.read_csv(binding['path'],usecols=columns,dtype=str,keep_default_na=False,float_precision='round_trip')
 for c in numeric:frame[c]=pd.to_numeric(frame[c],errors='coerce')
 return frame

def load_inputs(inputs):
 manifest=json.loads(read_bound(inputs['dataset_manifest']));terminal=json.loads(read_bound(inputs['dataset_terminal']))
 if manifest.get('schema')!='stage129_contract_choice_dataset_v1' or manifest.get('status')!='completed' or terminal.get('status')!='completed':raise ValueError('dataset not complete')
 for role in ['actions','common','mothers']:
  if not legacy.same_binding(manifest.get(role,{}),inputs[role]):raise ValueError('dataset role mismatch '+role)
 a=read_csv(inputs['actions'],ACTION_COLUMNS,NUMERIC);m=read_csv(inputs['mothers'],IDENTITY,['sequence_index','u_index'])
 if len(m)!=399252 or m.event_id.duplicated().any() or not np.array_equal(m.sequence_index,np.arange(len(m))):raise ValueError('full mother identity mismatch')
 if a.action_id.duplicated().any() or not np.array_equal(a.sequence_index,np.arange(len(a))) or not a.sequence_index.eq(a.action_sequence_index).all() or not a.event_id.eq(a.action_id).all() or not a.reference_epoch.eq(a.actual_epoch).all():raise ValueError('action alias identity mismatch')
 if not a.u_action_eligible.isin([0,1]).all():raise ValueError('bad action eligibility')
 idx=a.mother_sequence_index.to_numpy(np.int64)
 if (idx<0).any() or (idx>=len(m)).any() or not np.array_equal(a.mother_event_id.to_numpy(),m.event_id.to_numpy()[idx]):raise ValueError('parent-action mismatch')
 for c in ['product_id','family_id','u_date','u_index']:
  if not np.array_equal(a[c].to_numpy(),m[c].to_numpy()[idx]):raise ValueError('parent-action '+c+' mismatch')
 if not legacy.same_binding(file_binding(inputs['common']['path']),inputs['common']):raise ValueError('common changed')
 with np.load(inputs['common']['path'],allow_pickle=False) as data:
  if data['columns'].tolist()!=COMMON or data['common'].shape!=(len(a),26):raise ValueError('common shape/names mismatch')
  common=data['common'].astype(float)
 return a,m,common

def fit_cell(a,m,common,scope,cutoff,next_cutoff,directory,on_attempt,on_complete):
 train,pred,parent=fold_slices(a,m,cutoff,next_cutoff,scope);ti=train.sequence_index.to_numpy(int);pi=pred.sequence_index.to_numpy(int)
 w,g=training_weights(train);weights=w.sample_weight.to_numpy(float);y=train.net_R_stress.to_numpy(float)
 stats=[legacy.finite_stats(common[ti,j],weights) for j in range(26)]
 scaler=dict(common=dict(columns=COMMON,**{key:[s[key] for s in stats] for key in ['mean','var','scale','finite_count']}),feature_names=FEATURE_NAMES,scope=scope,cutoff=cutoff,weighting='family_u_interval_union_then_divide_actions_then_equal_u',missing='raw nonfinite standardized0 plus missing flag',units='COMMON unchanged original2N')
 directory.mkdir(parents=True,exist_ok=False);write_json(directory/'scaler.json',scaler)
 train_out=train.copy().reset_index(drop=True)
 for c in w:train_out[c]=w[c].to_numpy()
 training_binding=write_csv(directory/'training_identity_weights.csv.gz',train_out);groups_binding=write_csv(directory/'weight_groups.csv.gz',g)
 x=design(common[ti],scaler);estimator=legacy.Ridge(**PARAMETERS);on_attempt(scope,cutoff)
 with legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=weights)
 on_complete(scope,cutoff)
 # Store small sufficient equations instead of duplicate huge normalized matrices.
 z=np.column_stack([x,np.ones(len(x))]);lhs=z.T@(weights[:,None]*z);lhs[np.arange(52),np.arange(52)]+=1.;rhs=z.T@(weights*y);beta=np.r_[estimator.coef_,estimator.intercept_]
 residual=lhs@beta-rhs
 if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('Ridge normal equations mismatch')
 write_npz(directory/'normal_equations.npz',lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,weight_sum=np.array(weights.sum()))
 portable=dict(schema='stage130_shared_portable_ridge_v1',scope=scope,cutoff=cutoff,parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_))
 write_json(directory/'portable_model.json',portable)
 with (directory/'model.joblib').open('xb') as stream:legacy.joblib.dump(estimator,stream,compress=3)
 del x,z
 xp=design(common[pi],scaler);scores=estimator.predict(xp)
 if not np.allclose(scores,xp@np.array(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):raise ValueError('portable score mismatch')
 child=pred[['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']].copy();child['score']=scores;child['scope']=scope;child['cutoff']=cutoff
 choices=make_choices(parent,pred,scores,scope,cutoff)
 record=dict(scope=scope,cutoff=cutoff,training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),training_groups=len(g),prediction_children=len(pred),prediction_mothers=len(parent),max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),dimension=52,training_identity_weights=training_binding,weight_groups=groups_binding,scaler=file_binding(directory/'scaler.json'),portable_model=file_binding(directory/'portable_model.json'),model=file_binding(directory/'model.joblib'),normal_equations=file_binding(directory/'normal_equations.npz'),normal_equation_max_abs_residual=float(np.max(np.abs(residual))))
 return child,choices,record

def authorize(args):
 output=Path(args.output).resolve()
 if output.exists() or LINE/'outputs/stage130_contract_choice_fit' not in output.parents:raise ValueError('fresh Stage130 output required')
 if args.protocol_sha256!=PROTOCOL_SHA or file_binding(args.protocol)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen128 mismatch')
 binding=file_binding(args.authorization)
 if binding['sha256']!=args.authorization_sha256:raise ValueError('auth hash mismatch')
 auth=json.loads(read_bound(binding));required=dict(schema='stage128_exact_root_authorization_v1',authorized_by='root',stage='fit',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
 if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle() or set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('exact root fit auth mismatch')
 return output,auth,binding

def run_actual(output,auth,binding):
 output.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();attempts=completed=0
 write_json(output/'actual_started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),authorization=binding,source_bundle=bundle,protocol=file_binding(PROTOCOL)))
 def attempt(scope,cutoff):
  nonlocal attempts;attempts+=1
  with (output/'fit_attempts.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,attempt=attempts))+'\n');f.flush()
 def complete(scope,cutoff):
  nonlocal completed;completed+=1
  with (output/'fit_completed.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,completed=completed))+'\n');f.flush()
 try:
  a,m,common=load_inputs(auth['input_bindings']);children=[];choices=[];records=[]
  for scope in SCOPES:
   for j,cutoff in enumerate(CUTOFFS):
    child,choice,record=fit_cell(a,m,common,scope,cutoff,CUTOFFS[j+1] if j+1<len(CUTOFFS) else None,output/'folds'/scope/cutoff,attempt,complete)
    children.append(child);choices.append(choice);records.append(record)
    print(json.dumps(dict(phase='shared_fit_cell_complete',scope=scope,cutoff=cutoff,completed=completed)),flush=True)
  choices=pd.concat(choices,ignore_index=True);children=pd.concat(children,ignore_index=True);main=choices.loc[choices.scope.eq('main')].copy();held=choices.loc[choices.scope.ne('main')].copy()
  expected=set(m.loc[m.u_date.ge(CUTOFFS[0]),'event_id'])
  for name,frame in [('main',main),('held_union',held)]:
   if len(frame)!=161014*2 or frame.duplicated(['event_id','arm']).any():raise ValueError('full parent forward coverage '+name)
   for arm in ARMS:
    if set(frame.loc[frame.arm.eq(arm),'event_id'])!=expected:raise ValueError('shrunk parent '+name)
  forward=set(a.loc[a.u_date.ge(CUTOFFS[0]),'action_id'])
  for part in [children.loc[children.scope.eq('main')],children.loc[children.scope.ne('main')]]:
   if part.action_id.duplicated().any() or set(part.action_id)!=forward:raise ValueError('shrunk child forward coverage')
  if attempts!=6 or completed!=6:raise ValueError('six shared fits required')
  held_report,held_daily,linked=held_diagnostics(choices,a)
  bindings={name:write_csv(output/(name+'.csv.gz'),frame) for name,frame in [('choices_main',main),('choices_holdout',held),('child_scores',children),('held_daily',held_daily)]}
  write_json(output/'held_diagnostic.json',held_report);bindings['held_diagnostic']=file_binding(output/'held_diagnostic.json')
  write_json(output/'fit_records.json',records)
  write_json(output/'summary.json',dict(status='completed',mother_rows=len(m),action_rows=len(a),shared_fit_calls_completed=completed,parent_rows_per_arm_main=161014,parent_rows_per_arm_held_union=161014,child_scores=len(children),selected=choices.groupby(['scope','arm'],sort=True).selected.sum().astype(int).to_dict() if False else [dict(scope=s,arm=arm,selected=int(f.selected.sum())) for (s,arm),f in choices.groupby(['scope','arm'])],goal_complete=False,production_qualified=False))
  if bundle!=source_bundle():raise ValueError('source changed during fit')
  write_json(output/'actual_terminal.json',dict(status='completed',mode='actual',exit_code=0,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,downloads=0,fixture=False,elapsed_seconds=time.monotonic()-started))
  bindings['terminal']=file_binding(output/'actual_terminal.json')
  manifest=dict(schema='stage130_contract_choice_fit_v1',status='completed',mode='actual',cash_eligible=True,protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=binding,input_bindings=auth['input_bindings'],actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,prediction_mothers_per_arm=161014,prediction_children=len(children),native_source_queries=0,cash_replays=0,fit_records=file_binding(output/'fit_records.json'),goal_complete=False,production_qualified=False,**bindings)
  manifest['artifacts']={str(p.relative_to(output)):file_binding(p) for p in sorted(output.rglob('*')) if p.is_file()};write_json(output/'manifest.json',manifest)
  return manifest
 except BaseException as error:
  if not (output/'actual_terminal.json').exists():write_json(output/'actual_terminal.json',dict(status='failed',exit_code=1,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,error_type=type(error).__name__,error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started))
  raise

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ['protocol','protocol-sha256','authorization','authorization-sha256','output']:parser.add_argument('--'+name,required=True)
 args=parser.parse_args(argv);output,auth,binding=authorize(args);result=run_actual(output,auth,binding)
 print(json.dumps(dict(status=result['status'],actual_fit_calls_completed=result['actual_fit_calls_completed'],output=str(output))),flush=True)
if __name__=='__main__':main()
