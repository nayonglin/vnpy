"""Frozen conditional month-ranking attribution; no fitting, SQL or cash replay."""
from __future__ import annotations
import argparse,hashlib,json,time,traceback
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent
PROTOCOL_SHA='25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62'
POLICIES=['AI','UNIFORM_S','UNIFORM_E','MAX_VOLUME_POS','K']
CONTRASTS=[('AI','UNIFORM_S'),('UNIFORM_S','UNIFORM_E'),('AI','MAX_VOLUME_POS'),('UNIFORM_E','K'),('AI','K')]
CONTROLS=['MAX_VOLUME_POS']+[f'RANDOM_POS_{s:02d}' for s in range(20)]
ACTION_COLS=['action_id','action_sequence_index','mother_event_id','actual_epoch','u_volume','label_state','net_R_stress','label_known_date']
def binding(path):
 p=Path(path).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def read_bound(b):
 if binding(b['path'])!=b:raise ValueError('binding changed '+b['path'])
 return Path(b['path']).read_bytes()
def dump(path,obj):
 Path(path).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
def source_bundle():
 return sorted([binding(TOOLS/n) for n in ['stage135_month_ranking_choices.py','test_stage135_month_ranking_choices.py']],key=lambda b:b['path'])
def random_key(seed,product_id,u_date,actual_epoch):
 obj=dict(version='stage134_positive_month_rank_v1',seed=int(seed),product_id=str(product_id),u_date=str(u_date),actual_epoch=str(actual_epoch))
 return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def volume_choice(g):
 return g.sort_values(['u_volume','actual_epoch','action_id'],ascending=[False,True,True],kind='stable').iloc[0]
def outcome(a,end):
 if a['label_state']=='known_nonparticipation':return 0.
 value=pd.to_numeric(a['net_R_stress'],errors='coerce')
 if a['label_state']=='closed_complete_bar_model' and np.isfinite(value) and a['label_known_date'] and a['label_known_date']<=end:return float(value)
 return None
def linear_expectation(left,right,values):
 c={}
 for sign,weights in [(1,left),(-1,right)]:
  for k,w in weights.items():c[k]=c.get(k,Fraction(0))+sign*Fraction(w)
 c={k:v for k,v in c.items() if v}
 unknown={k:w for k,w in c.items() if values.get(k) is None}
 return dict(value=None if unknown else float(sum(float(w)*values[k] for k,w in c.items())),known=not unknown,
  unknown_positive_mass=float(sum(w for w in unknown.values() if w>0)),unknown_negative_mass=float(-sum(w for w in unknown.values() if w<0)))
def materialize(base,overrides,control_id):
 """All original B parents in order; unselected source proposals stay diagnostic."""
 z=base.copy();o=overrides.loc[overrides.control_id.eq(control_id)].copy()
 key=['scope','event_id'];o=o.rename(columns={'mother_event_id':'event_id'})
 if o.duplicated(key).any():raise ValueError('duplicate override')
 want=set(map(tuple,z.loc[z.selected.eq(1),key].to_numpy()));have=set(map(tuple,o[key].to_numpy()))
 if want!=have:raise ValueError('selected-parent override population differs')
 oi=o.set_index(key)
 for ix,r in z.loc[z.selected.eq(1)].iterrows():
  a=oi.loc[(r.scope,r.event_id)]
  for c in ['chosen_action_id','chosen_action_sequence_index','chosen_epoch','score']:z.at[ix,c]=a[c]
  for dst,src in [('proposed_action_id','chosen_action_id'),('proposed_epoch','chosen_epoch'),('proposed_score','score')]:z.at[ix,dst]=a[src]
 return z

def authorize(args):
 pb=binding(args.protocol)
 if pb['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('frozen134 required')
 protocol=json.loads(read_bound(pb));ab=binding(args.authorization)
 if ab['sha256']!=args.authorization_sha256:raise ValueError('auth hash differs')
 auth=json.loads(read_bound(ab));out=Path(args.output).resolve()
 req=dict(schema='stage134_exact_root_authorization_v1',authorized_by='root',stage='choices',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
 if any(auth.get(k)!=v for k,v in req.items()):raise ValueError('exact root choices auth required')
 if auth.get('source_bundle')!=source_bundle():raise ValueError('source auth differs')
 if auth.get('input_bindings')!=protocol['inputs']:raise ValueError('fixed input roles differ')
 if out.exists():raise FileExistsError('fresh output required')
 return protocol,pb,auth,ab,out

def aggregate(d):
 result=[]
 metrics=POLICIES+[a+'_minus_'+b for a,b in CONTRASTS]
 for scope,g in d.groupby('scope',sort=True):
  for population,sub in [('full',g),('admitted',g[g.admitted.eq(1)]),('multiple',g[g.admitted.eq(1)&g.positive_month_count.gt(1)])]:
   periods=[('all',sub)]+[(str(y),part) for y,part in sub.groupby(sub.u_date.str[:4])]
   for period,part in periods:
    for name in metrics:
     ok=part[name+'_known'].astype(bool);v=part[name+'_value'];known=part.loc[ok,['u_date']].assign(value=v[ok].astype(float))
     means=known.groupby('u_date').value.mean()
     result.append(dict(scope=scope,population=population,period=period,contrast=name,family_u_rows=len(part),u_days=int(part.u_date.nunique()),known_increment_rows=int(ok.sum()),unknown_increment_rows=int((~ok).sum()),mean_equal_u_known_only=float(means.mean()) if len(means) else None,all_identified_mean_equal_u=float(means.mean()) if len(part) and ok.all() else None,unknown_positive_mass=float(part[name+'_unknown_positive_mass'].sum()),unknown_negative_mass=float(part[name+'_unknown_negative_mass'].sum())))
 return result

def execute(args):
 p,pb,auth,ab,out=authorize(args);out.mkdir(parents=True);started=time.monotonic()
 terminal=out/'actual_terminal.json'
 try:
  inp=p['inputs']
  # Read only immutable accepted action identifiers/labels and existing source scores.
  actions=pd.read_csv(inp['actions']['path'],usecols=ACTION_COLS,keep_default_na=False)
  if binding(inp['actions']['path'])!=inp['actions']:raise ValueError('actions binding differs')
  scores=pd.read_csv(inp['child_scores']['path'],keep_default_na=False)
  if binding(inp['child_scores']['path'])!=inp['child_scores']:raise ValueError('scores binding differs')
  bases=[]
  for role in ['choices_main','choices_holdout']:
   b=pd.read_csv(inp[role]['path'],keep_default_na=False);b=b[b.arm.eq('B')].copy();bases.append(b)
   if binding(inp[role]['path'])!=inp[role]:raise ValueError('base choices binding differs')
  base=pd.concat(bases,ignore_index=True)
  for c in ['score','u_action_eligible']:scores[c]=pd.to_numeric(scores[c],errors='coerce')
  eligible=scores.u_action_eligible.eq(1)&np.isfinite(scores.score)
  positive=eligible&scores.score.gt(0)
  # Pre-family all-negative counts are descriptive only.
  pre=scores.assign(eligible_count=eligible.astype(int),positive_count=positive.astype(int)).groupby(['scope','mother_event_id'],sort=False)[['eligible_count','positive_count']].sum()
  pre_summary=[]
  for scope,g in pre.groupby(level=0):pre_summary.append(dict(scope=scope,parent_rows=len(g),E_nonempty_S_empty=int((g.eligible_count.gt(0)&g.positive_count.eq(0)).sum()),E_nonempty=int(g.eligible_count.gt(0).sum())))
  selected=base[base.selected.eq(1)].copy()
  wanted=set(zip(selected.scope,selected.event_id))
  mask=np.fromiter(((s,m) in wanted for s,m in zip(scores.scope,scores.mother_event_id)),dtype=bool,count=len(scores))
  pool=scores[mask&eligible].copy()
  a=actions.set_index('action_id',verify_integrity=True)
  extra=a.loc[pool.action_id,['action_sequence_index','actual_epoch','u_volume','label_state','net_R_stress','label_known_date']].reset_index(drop=True)
  pool=pool.reset_index(drop=True)
  for c in extra:pool[c]=extra[c]
  pool['u_volume']=pd.to_numeric(pool.u_volume,errors='raise')
  groups={(s,m):g for (s,m),g in pool.groupby(['scope','mother_event_id'],sort=False)}
  overrides=[];diags={}
  for c in selected.to_dict('records'):
   e=groups[(c['scope'],c['event_id'])];s=e[e.score.gt(0)];ai=str(c['chosen_action_id'])
   if s.empty or ai not in set(s.action_id):raise ValueError('sourceB choice not in S')
   if s.product_id.nunique()!=1 or s.product_id.iloc[0]!=c['product_id']:raise ValueError('winning product differs')
   volume=volume_choice(s)
   choices={'MAX_VOLUME_POS':(volume,'max_original_u_volume')}
   for seed in range(20):
    ranks=[(random_key(seed,c['product_id'],c['u_date'],r['actual_epoch']),r['actual_epoch'],r['action_id'],r) for r in s.to_dict('records')]
    chosen=min(ranks,key=lambda v:v[:3]);choices[f'RANDOM_POS_{seed:02d}']=(chosen[3],chosen[0])
   for control,(r,key) in choices.items():
    overrides.append(dict(control_id=control,scope=c['scope'],cutoff=c['cutoff'],mother_sequence_index=int(c['sequence_index']),mother_event_id=c['event_id'],product_id=c['product_id'],family_id=c['family_id'],u_date=c['u_date'],u_index=int(c['u_index']),chosen_action_id=r['action_id'],chosen_action_sequence_index=int(r['action_sequence_index']),chosen_epoch=r['actual_epoch'],anchor_epoch=c['anchor_epoch'],score=float(r['score']),u_volume=float(r['u_volume']),rule_key=key))
   values={r['action_id']:outcome(r,p['scope']['end']) for r in e.to_dict('records')}
   canonical=s.loc[s.actual_epoch.eq(c['anchor_epoch']),'action_id'].tolist()
   if len(canonical)>1:raise ValueError('multiple canonical epochs')
   weights=dict(AI={ai:Fraction(1)},UNIFORM_S={v:Fraction(1,len(s)) for v in s.action_id},UNIFORM_E={v:Fraction(1,len(e)) for v in e.action_id},MAX_VOLUME_POS={volume.action_id:Fraction(1)},K={canonical[0]:Fraction(1)} if canonical else {})
   row=dict(scope=c['scope'],cutoff=c['cutoff'],u_date=c['u_date'],u_index=int(c['u_index']),family_id=c['family_id'],admitted=1,positive_month_count=len(s),eligible_month_count=len(e),winning_product_id=c['product_id'],mother_event_id=c['event_id'],chosen_ai_action_id=ai,chosen_volume_action_id=volume.action_id,canonical_action_id=canonical[0] if canonical else '',common_unresolved_count=sum(values[v] is None for v in s.action_id))
   for name,w in weights.items():
    for k,v in linear_expectation(w,{},values).items():row[name+'_'+k]=v
   for left,right in CONTRASTS:
    for k,v in linear_expectation(weights[left],weights[right],values).items():row[left+'_minus_'+right+'_'+k]=v
   diags[(c['scope'],c['family_id'],c['u_date'])]=row
  # Complete original family-u population, including no-intent states.
  rows=[]
  for (scope,fam,date),g in base.groupby(['scope','family_id','u_date'],sort=True):
   key=(scope,fam,date)
   if key in diags:row=diags[key]
   else:
    c=g.iloc[0];row=dict(scope=scope,cutoff=c.cutoff,u_date=date,u_index=int(c.u_index),family_id=fam,admitted=0,positive_month_count=0,eligible_month_count=0,winning_product_id='',mother_event_id='',chosen_ai_action_id='',chosen_volume_action_id='',canonical_action_id='',common_unresolved_count=0)
    for name in POLICIES+[x+'_minus_'+y for x,y in CONTRASTS]:
     for k,v in dict(value=0.,known=True,unknown_positive_mass=0.,unknown_negative_mass=0.).items():row[name+'_'+k]=v
   rows.append(row)
  overrides=pd.DataFrame(overrides);diag=pd.DataFrame(rows)
  if len(overrides)!=len(selected)*21:raise ValueError('override count differs')
  op=out/'choice_overrides.csv.gz';dp=out/'diagnostic_family_u.csv.gz'
  overrides.to_csv(op,index=False,compression=dict(method='gzip',mtime=0));diag.to_csv(dp,index=False,compression=dict(method='gzip',mtime=0))
  summary=dict(schema='stage135_label_attribution_summary_v1',unit='own_policy_net_R_stress_not_funded_portfolio',pre_family=pre_summary,aggregates=aggregate(diag),unknown='Exact coefficients cancel; nonzero unknown coefficients unidentified; known-only means are conditional observed domains, not whole-policy values.',new_SQL=0,new_fits=0,new_cash=0,new_labels=0)
  sp=out/'diagnostic_summary.json';dump(sp,summary)
  dump(terminal,dict(status='completed',exit_code=0,native_source_queries=0,actual_fit_calls_completed=0,new_cash_accounts=0,new_labels=0,elapsed_seconds=time.monotonic()-started))
  manifest=dict(schema='stage135_month_ranking_attribution_v1',status='completed',mode='actual',protocol=pb,authorization=ab,source_bundle=source_bundle(),input_bindings=inp,overrides=binding(op),diagnostic_family_u=binding(dp),diagnostic_summary=binding(sp),terminal=binding(terminal),full_base_references={r:inp[r] for r in ['choices_main','choices_holdout']},counts=dict(original_B_parent_rows=len(base),selected_parent_rows=len(selected),override_rows=len(overrides),family_u_rows=len(diag),new_cash=0,new_SQL=0,new_fits=0,new_labels=0),population='Full original B parent bases plus compact selected overrides; no retrospective filled-trade filter; no future-filtered selection.')
  dump(out/'manifest.json',manifest)
  print(json.dumps(dict(status='completed',counts=manifest['counts'],elapsed_seconds=time.monotonic()-started)))
 except Exception:
  dump(terminal,dict(status='failed',exit_code=1,native_source_queries=0,actual_fit_calls_completed=0,new_cash_accounts=0,new_labels=0,error=traceback.format_exc(),elapsed_seconds=time.monotonic()-started));raise

def main():
 a=argparse.ArgumentParser()
 for n in ['protocol','protocol-sha256','authorization','authorization-sha256','output']:a.add_argument('--'+n,required=True)
 execute(a.parse_args())
if __name__=='__main__':main()
