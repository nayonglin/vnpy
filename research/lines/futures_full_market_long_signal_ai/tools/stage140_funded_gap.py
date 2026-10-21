"""One exact existing-ledger CNY bridge; no strategies, fits, SQL or new paths."""
from __future__ import annotations
import argparse,hashlib,io,json,math,time,traceback
from pathlib import Path
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL_SHA='7d07e65db4dd4287b0245b535c19af76d6a23ffc9e9896defab7f1b278b2057d'
CONTROLS=['MAX_VOLUME_POS']+[f'RANDOM_POS_{i:02d}' for i in range(20)]
SIGNED=['positive_delta_CNY','negative_delta_CNY']
MEASURES=['delta_CNY','risk_component','unit_component','participation_component','gross_realized_difference','negative_fee_difference','unrealized_difference']
MAX_ERROR=0.
def binding(p):
 p=Path(p).resolve();v=p.read_bytes();return dict(path=str(p),bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
def bound(item):
 v=Path(item['path']).read_bytes()
 if len(v)!=item['bytes'] or hashlib.sha256(v).hexdigest()!=item['sha256']:raise ValueError('binding changed '+item['path'])
 return v
def table(item):return pd.read_csv(io.BytesIO(bound(item)),compression='gzip',keep_default_na=False)
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
def source_bundle():return sorted([binding(TOOLS/n) for n in ['stage140_funded_gap.py','test_stage140_funded_gap.py']],key=lambda v:v['path'])
def flag(v):
 if isinstance(v,(bool,np.bool_)):return bool(v)
 if str(v).lower() in ('true','1'):return True
 if str(v).lower() in ('false','0',''):return False
 raise ValueError('invalid boolean '+str(v))
def num(v):return float(v)
def close(a,b):
 global MAX_ERROR
 a,b=np.asarray(a,float),np.asarray(b,float)
 if not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('nonfinite amount')
 MAX_ERROR=max(MAX_ERROR,float(np.max(np.abs(a-b))) if a.size else 0.)
 if not np.allclose(a,b,rtol=1e-10,atol=1e-6):raise ValueError('accounting not reconciled')
def root_contribution(r,closed):
 value=num(r['realized_gross'])-num(r['entry_fees'])-num(r['exit_fees'])+(0. if closed else num(r['unrealized']))
 if closed:close(value,num(r['net_pnl']))
 return value

def decompose(ca,cb,fa,fb,ea,eb):
 for c in (ca,cb):
  if not np.isfinite(c):raise ValueError('nonfinite contribution')
 for e,f in [(ea,fa),(eb,fb)]:
  if e and (f is None or not np.isfinite(f) or f<=0):raise ValueError('positive initial funded risk required')
 ya=ca/fa if ea else None;yb=cb/fb if eb else None
 risk=(fa-fb)*(ya+yb)/2 if ea and eb else 0.
 unit=(ya-yb)*(fa+fb)/2 if ea and eb else 0.
 participation=ca if ea and not eb else -cb if eb and not ea else 0.
 if not ea:close(ca,0.)
 if not eb:close(cb,0.)
 close(risk+unit+participation,ca-cb)
 return dict(delta_CNY=ca-cb,risk_component=risk,unit_component=unit,participation_component=participation,AI_unit_return=ya,control_unit_return=yb)

def calendar_dates(values):
 if values.dtype.kind in 'iu':
  return [str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in values]
 return values.astype('datetime64[D]').astype(str).tolist()

def window_opportunity(u,start,end):return start-1<=u<=end-1

def artifact(m,name):
 found=[v for v in m['artifacts'] if v.get('logical_name')==name]
 if len(found)!=1:raise ValueError('unique accepted artifact required '+name)
 return {k:found[0][k] for k in ['path','bytes','sha256']}

def path_signature(root,fills):
 q=num(root['initial_qty']);items=[]
 for f in fills.to_dict('records'):
  items.append([str(f[k]) for k in ['date','side','reason']]+[round(num(f[k]),12) for k in ['reference_price','fill_price']]+[round(num(f[k])/q,12) for k in ['qty','fee','slippage','realized_gross']])
 meta={k:str(root.get(k,'')) for k in ['exit_date','exit_reason','anchor_request_date','anchor_request_reason','state']}
 meta.update({k:flag(root.get(k,'')) for k in ['stale','ever_stale','deferred','execution_capacity_unknown']});meta.update(remaining_fraction=round(num(root['qty'])/q,12),last_mark=round(num(root['last_mark']),12))
 return hashlib.sha256(json.dumps(dict(fills=items,terminal=meta),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def source_choices(protocol,controls):
 choices=table(protocol['inputs']['choices_main']);base=choices[choices.arm.eq('B')&choices.scope.eq('main')&choices.selected.eq(1)].copy().reset_index(drop=True)
 if len(base)!=4917 or base.event_id.duplicated().any():raise ValueError('source B parent domain differs')
 parents=base[['event_id','product_id','family_id','u_date','u_index','chosen_action_id','chosen_epoch']].rename(columns={'event_id':'mother_event_id'})
 maps={'AI':parents.copy()}
 for control in CONTROLS:
  sig=table(controls['signals'][control]);z=sig[['mother_event_id','event_id','reference_epoch']].rename(columns={'event_id':'chosen_action_id','reference_epoch':'chosen_epoch'})
  if z.mother_event_id.duplicated().any() or set(z.mother_event_id)!=set(parents.mother_event_id):raise ValueError('control changed parent domain')
  z=parents.drop(columns=['chosen_action_id','chosen_epoch']).merge(z,on='mother_event_id',validate='one_to_one',sort=False)
  maps[control]=z
 return parents,maps

def book_rows(account,choice,dates,window):
 name=account['account_id'];summary=json.loads(bound(account['summary']));ledger=account['ledgers']
 closed,opened,fills,budgets,entry_unknown=(table(ledger[k]) for k in ['closed','open','fills','reservations','entry_execution_unknown'])
 roots=pd.concat([closed.assign(terminal_closed=True),opened.assign(terminal_closed=False)],ignore_index=True)
 if roots.root_id.duplicated().any() or roots.event_id.duplicated().any():raise ValueError('unique root/action needed')
 start=int(np.searchsorted(dates,window[0]));end=int(np.searchsorted(dates,window[1]));mapping=choice.set_index('chosen_action_id',drop=False,verify_integrity=True)
 entry=budgets.loc[budgets.get('budget_kind',pd.Series('',index=budgets.index)).ne('existing_position_reduction')].copy()
 if entry.event_id.duplicated().any():raise ValueError('duplicate entry decision')
 expect=set(choice.loc[choice.u_index.map(lambda v:window_opportunity(int(v),start,end)),'chosen_action_id'])
 if set(entry.event_id)!=expect:raise ValueError('full native decision window differs '+name)
 decisions=entry.set_index('event_id');unknown=set(entry_unknown.event_id) if 'event_id' in entry_unknown else set()
 root_map=roots.set_index('event_id');fillgroups={k:g for k,g in fills.groupby('event_id',sort=False)}
 if set(fillgroups)!=set(roots.event_id):raise ValueError('fill/root domain mismatch')
 rows=[]
 for c in choice.to_dict('records'):
  action=c['chosen_action_id'];entered=action in root_map.index;opportunity=action in expect;r=root_map.loc[action].to_dict() if entered else None
  row=dict(account_id=name,control_id=account['control_id'],window=account['window'],cost=account['cost'],**c,cohort_year=str(c['u_date'])[:4],opportunity=opportunity,entered=entered,entry_execution_unknown=action in unknown,entry_state=str(decisions.loc[action,'D_state']) if opportunity else 'outside_account_decision_window')
  if entered:
   g=fillgroups[action];buy=g[g.side.eq('BUY')]
   if len(buy)!=1 or str(r['mother_event_id'])!=c['mother_event_id'] or str(r['epoch'])!=c['chosen_epoch']:raise ValueError('root/choice identity differs')
   buy=buy.iloc[0];q=num(r['initial_qty']);risk=num(r['risk_per_lot']);close([buy['qty'],buy['risk_per_lot'],buy['fee']],[q,risk,num(r['entry_fees'])]);close(q-g.loc[g.side.eq('SELL'),'qty'].astype(float).sum(),num(r['qty']))
   contribution=root_contribution(r,flag(r['terminal_closed']));close(contribution,g.realized_gross.astype(float).sum()-g.fee.astype(float).sum()+(0 if flag(r['terminal_closed']) else num(r['unrealized'])))
   row.update(root_id=r['root_id'],initial_qty=q,risk_per_lot=risk,funded_initial_risk_CNY=q*risk,net_contribution=contribution,realized_gross=num(r['realized_gross']),fees=num(r['entry_fees'])+num(r['exit_fees']),unrealized=0. if flag(r['terminal_closed']) else num(r['unrealized']),terminal_open=not flag(r['terminal_closed']),ever_stale=flag(r['ever_stale']),terminal_stale=flag(r['stale']),capacity_unknown=flag(r['execution_capacity_unknown']),observed_path_signature=path_signature(r,g))
   if q<=0 or risk<=0 or not np.isfinite(q*risk):raise ValueError('invalid funded initial risk')
  else:row.update(root_id='',initial_qty=None,risk_per_lot=None,funded_initial_risk_CNY=None,net_contribution=0.,realized_gross=0.,fees=0.,unrealized=0.,terminal_open=False,ever_stale=False,terminal_stale=False,capacity_unknown=False,observed_path_signature='')
  row['affected']=bool(row['entry_execution_unknown'] or row['terminal_open'] or row['ever_stale'] or row['capacity_unknown']);rows.append(row)
 z=pd.DataFrame(rows);growth=num(summary['ending_equity'])-1000000.;close(math.fsum(z.net_contribution),growth);close(math.fsum(z.net_contribution),fills.realized_gross.astype(float).sum()-fills.fee.astype(float).sum()+opened.unrealized.astype(float).sum())
 return z,dict(account_id=name,control_id=account['control_id'],window=account['window'],cost=account['cost'],parent_rows=len(z),entered=int(z.entered.sum()),opportunity=int(z.opportunity.sum()),growth_CNY=growth,root_sum_CNY=math.fsum(z.net_contribution),ending_equity=num(summary['ending_equity']),capacity_unknown_roots=int(z.capacity_unknown.sum()),ever_stale_roots=int(z.ever_stale.sum()),terminal_open_roots=int(z.terminal_open.sum()),entry_execution_unknown=int(z.entry_execution_unknown.sum()))

def pair_rows(ai,peer):
 if ai.mother_event_id.tolist()!=peer.mother_event_id.tolist():raise ValueError('parent order mismatch')
 rows=[]
 for a,b in zip(ai.to_dict('records'),peer.to_dict('records')):
  ea,eb=bool(a['entered']),bool(b['entered']);same=a['chosen_action_id']==b['chosen_action_id']
  category='both_entered_same_action' if ea and eb and same else 'both_entered_different_action' if ea and eb else 'AI_only_entered' if ea else 'control_only_entered' if eb else 'neither_entered'
  path='same_observed_fractional_path' if ea and eb and same and a['observed_path_signature']==b['observed_path_signature'] else 'different_observed_fractional_path' if ea and eb and same else 'different_action_not_compared' if ea and eb else 'not_both_entered'
  row={k:a[k] for k in ['mother_event_id','product_id','family_id','u_date','u_index','cohort_year','window','cost']};row.update(control_id=b['control_id'],category=category,path_diagnostic=path,same_chosen_action=same,AI_entered=ea,control_entered=eb,AI_action_id=a['chosen_action_id'],control_action_id=b['chosen_action_id'],AI_initial_risk_CNY=a['funded_initial_risk_CNY'],control_initial_risk_CNY=b['funded_initial_risk_CNY'],AI_net_CNY=a['net_contribution'],control_net_CNY=b['net_contribution'],AI_entry_state=a['entry_state'],control_entry_state=b['entry_state'],affected=bool(a['affected'] or b['affected']))
  row.update(decompose(a['net_contribution'],b['net_contribution'],a['funded_initial_risk_CNY'],b['funded_initial_risk_CNY'],ea,eb))
  row.update(gross_realized_difference=a['realized_gross']-b['realized_gross'],negative_fee_difference=b['fees']-a['fees'],unrealized_difference=a['unrealized']-b['unrealized'])
  for f in ['capacity_unknown','ever_stale','terminal_open','terminal_stale','entry_execution_unknown']:row['either_'+f]=bool(a[f] or b[f])
  close(row['delta_CNY'],row['gross_realized_difference']+row['negative_fee_difference']+row['unrealized_difference']);rows.append(row)
 return pd.DataFrame(rows)

def group_table(frame,dimension):
 keys=['control_id','window','cost']+dimension
 frame=frame.assign(positive_delta_CNY=frame.delta_CNY.clip(lower=0),negative_delta_CNY=frame.delta_CNY.clip(upper=0))
 out=frame.groupby(keys,dropna=False,sort=True)[MEASURES+SIGNED].sum().reset_index();counts=frame.groupby(keys,dropna=False,sort=True).size().rename('parent_rows').reset_index();return out.merge(counts,on=keys,validate='one_to_one')

def execute(args):
 pb=binding(args.protocol)
 if pb['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('exact139 required')
 p=json.loads(bound(pb));ab=binding(args.authorization)
 if ab['sha256']!=args.authorization_sha256:raise ValueError('exact auth hash required')
 auth=json.loads(bound(ab));out=Path(args.output).resolve()
 required=dict(schema='stage139_exact_root_authorization_v1',authorized_by='root',stage='attribution',protocol_sha256=PROTOCOL_SHA,output=str(out),exact_source_authorized=True)
 if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle() or auth.get('input_bindings')!=p['inputs']:raise ValueError('root source/input auth differs')
 out.mkdir(parents=True,exist_ok=False);started=time.monotonic();terminal=out/'actual_terminal.json'
 try:
  c=json.loads(bound(p['inputs']['control_cash_manifest']));old=json.loads(bound(p['inputs']['AI_cash_manifest']));review=json.loads(bound(p['inputs']['accepted_review']));rt=json.loads(bound(p['inputs']['accepted_review_terminal']));assert review['counts']==dict(Critical=0,Important=0,Minor=0) and rt['exit_code']==0;assert review['exact_inputs']['cash']==p['inputs']['control_cash_manifest'];assert c['input_bindings']['baseline_cash_manifest']==p['inputs']['AI_cash_manifest'];assert c['input_bindings']['choices_main']==p['inputs']['choices_main']
  dates=calendar_dates(np.load(io.BytesIO(bound(p['inputs']['calendar'])),allow_pickle=False));assert len(dates)==5587
  parents,maps=source_choices(p,c);accounts=list(c['accounts'])
  for window in p['scope']['windows']:
   for cost in p['scope']['costs']:
    name=f'NARROW_B_{window}_{cost}';accounts.append(dict(control_id='AI',window=window,cost=cost,account_id=name,summary=artifact(old,name+'/summary.json'),ledgers={r:artifact(old,name+'/'+r+'.csv.gz') for r in ['closed','open','fills','reservations','entry_execution_unknown']}))
  books={};rec=[]
  for account in accounts:
   key=(account['control_id'],account['window'],account['cost']);z,r=book_rows(account,maps[account['control_id']],dates,p['scope']['windows'][account['window']]);books[key]=z;rec.append(r)
  pairs=[]
  for control in CONTROLS:
   for window in p['scope']['windows']:
    for cost in p['scope']['costs']:
     z=pair_rows(books[('AI',window,cost)],books[(control,window,cost)]);close(z.delta_CNY.sum(),books[('AI',window,cost)].net_contribution.sum()-books[(control,window,cost)].net_contribution.sum());pairs.append(z)
  book=pd.concat(books.values(),ignore_index=True);pair=pd.concat(pairs,ignore_index=True);assert len(book)==432696 and len(pair)==413028
  summaries=group_table(pair,[]);aggregates=[]
  for (window,cost),g in summaries.groupby(['window','cost'],sort=False):
   for contrast,part in [('AI_minus_MAX_VOLUME_POS',g[g.control_id.eq('MAX_VOLUME_POS')]),('AI_minus_RANDOM_POS_mean20',g[g.control_id.str.startswith('RANDOM')])]:
    expected=1 if 'MAX_VOLUME' in contrast else 20;assert len(part)==expected;row=dict(window=window,cost=cost,contrast=contrast,control_count=expected,**{k:float(part[k].mean()) for k in MEASURES+SIGNED});close(row['delta_CNY'],row['risk_component']+row['unit_component']+row['participation_component']);aggregates.append(row)
  outputs=dict(book_parent_contributions=book,pair_parent_decomposition=pair,account_reconciliation=pd.DataFrame(rec),pair_summaries=summaries,aggregate_summaries=pd.DataFrame(aggregates))
  for name,dim in [('category_components',['category']),('family_components',['family_id']),('cohort_components',['cohort_year']),('affected_components',['affected']),('path_components',['path_diagnostic'])]:outputs[name]=group_table(pair,dim)
  top=[]
  for (window,cost),g in pair.groupby(['window','cost'],sort=False):
   for contrast,sub in [('AI_minus_MAX_VOLUME_POS',g[g.control_id.eq('MAX_VOLUME_POS')]),('AI_minus_RANDOM_POS_mean20',g[g.control_id.str.startswith('RANDOM')])]:
    mean=sub.groupby(['mother_event_id','family_id','u_date'],sort=False).delta_CNY.mean().reset_index()
    for side,part in [('positive',mean[mean.delta_CNY.gt(0)].nlargest(5,'delta_CNY')),('negative',mean[mean.delta_CNY.lt(0)].nsmallest(5,'delta_CNY'))]:
     for rank,r in enumerate(part.to_dict('records'),1):top.append(dict(window=window,cost=cost,contrast=contrast,side=side,rank=rank,**r))
  outputs['top_parent_contributions']=pd.DataFrame(top)
  bindings={}
  for name,frame in outputs.items():
   path=out/(name+'.csv.gz');frame.to_csv(path,index=False,compression=dict(method='gzip',mtime=0));bindings[name]=binding(path)
  diag=dict(schema='stage140_funded_gap_diagnostics_v1',account_count=len(books),pair_count=84,book_parent_rows=len(book),pair_parent_rows=len(pair),accounting_max_absolute_error_CNY=MAX_ERROR,all_roots_and_growth_reconciled=True,initial_funded_risk_not_loss_bound=True,unentered_Y_is_null=True,all20_seeds_preserved=True,new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0,causal_AI_or_sizing_effect_identified=False,original138_verdict_unchanged=True,goal_complete=False,increased_betting_qualified=False,production_qualified=False)
  write(out/'diagnostics.json',diag);bindings['diagnostics']=binding(out/'diagnostics.json');write(terminal,dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-started,new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0))
  manifest=dict(schema='stage140_funded_gap_v1',status='completed',mode='actual',protocol=pb,authorization=ab,source_bundle=source_bundle(),input_bindings=p['inputs'],terminal=binding(terminal),**bindings)
  write(out/'manifest.json',manifest);print(json.dumps(dict(status='completed',elapsed_seconds=time.monotonic()-started,counts=diag)))
 except BaseException:
  write(terminal,dict(status='failed',exit_code=1,error=traceback.format_exc(),elapsed_seconds=time.monotonic()-started,new_SQL=0,new_fits=0,new_cash=0));raise
if __name__=='__main__':
 a=argparse.ArgumentParser()
 for n in ['protocol','protocol-sha256','authorization','authorization-sha256','output']:a.add_argument('--'+n,required=True)
 execute(a.parse_args())
