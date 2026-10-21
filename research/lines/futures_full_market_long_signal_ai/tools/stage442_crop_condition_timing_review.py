#!/usr/bin/env python3
"""Independent bounded Stage441 numerical audit, using emitted facts and two calendar columns."""
import bisect
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, date, time as dt_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

BASE=Path('/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai')
SRC=BASE/'outputs/stage441_crop_condition_timing/actual_run1'
OUT=BASE/'outputs/stage442_crop_condition_timing_review/actual_run2'
CAL=BASE/'outputs/stage427_product_material_timing/actual_run1/source_day_features.csv.gz'
NY=ZoneInfo('America/New_York'); SH=ZoneInfo('Asia/Shanghai')
FIELDS=['q','own_u','gap','after_open','total']
PRIMARY=['after_open_partial_correlation','after_open_worsening_minus_nonworsening_mean']
STAT=[f+s for f in ['gap','after_open','total'] for s in ['_correlation','_partial_correlation']]+['q_own_u_correlation',PRIMARY[1]]
checks=0; failures=[]; largest_difference=0.; bindings=[]

def check(ok,label):
 global checks
 checks+=1
 if not ok: failures.append(label)

def compare(a,b,label,tol=2e-12):
 global largest_difference
 if a is None or b is None: check(a is None and b is None,label); return
 delta=abs(float(a)-float(b));largest_difference=max(largest_difference,delta)
 check(math.isfinite(delta) and delta<=tol,label)

def binding(path,blob):
 return {'path':str(path),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}

def load(path,kind='json'):
 blob=path.read_bytes();bindings.append(binding(path,blob))
 if kind=='bytes':return blob
 if kind=='jsonl':return [json.loads(x) for x in blob.decode().splitlines()]
 return json.loads(blob)

def pearson(x,y):
 if len(x)<3:return None
 a=x-x.mean();b=y-y.mean();den=float(np.sqrt(np.dot(a,a)*np.dot(b,b)))
 return float(np.dot(a,b)/den) if den>0 else None

def partial(x,y,z):
 # Algebraic residual correlation, independent of the author's numeric helpers.
 xy=pearson(x,y);xz=pearson(x,z);yz=pearson(y,z)
 if any(v is None for v in [xy,xz,yz]):return None
 den=(1-xz*xz)*(1-yz*yz)
 return float((xy-xz*yz)/np.sqrt(den)) if den>0 else None

def stats(matrix):
 a=matrix[np.isfinite(matrix).all(axis=1)]
 result={'joint_count':len(a),'nonjoint_calendar_dates':len(matrix)-len(a),
         'q_worsening_joint':int(np.sum(a[:,0]>0)),'q_nonworsening_joint':int(np.sum(a[:,0]<=0))}
 for j,name in enumerate(['gap','after_open','total'],2):
  result[name+'_correlation']=pearson(a[:,0],a[:,j])
  result[name+'_partial_correlation']=partial(a[:,0],a[:,j],a[:,1])
 result['q_own_u_correlation']=pearson(a[:,0],a[:,1])
 w=a[:,0]>0;other=a[:,0]<=0
 result[PRIMARY[1]]=float(a[w,3].mean()-a[other,3].mean()) if w.any() and other.any() else None
 return result

def main():
 started=datetime.now(timezone.utc).isoformat();t0=time.monotonic();OUT.mkdir(parents=True,exist_ok=False)
 try:
  names=['manifest.json','receipt.json','results.json','event_facts.json','bootstrap_replicates.json','terminal.json','started.json','source_qualification.json']
  docs={name:load(SRC/name) for name in names}
  manifest=docs['manifest.json'];receipt=docs['receipt.json'];results=docs['results.json'];facts=docs['event_facts.json']['events'];oldrep=docs['bootstrap_replicates.json']
  raw=load(BASE/'outputs/stage438_crop_condition_extract/actual_run1/crop_rows.jsonl','jsonl')
  protocol=load(BASE/'outputs/stage440_crop_condition_timing_protocol/protocol.json')
  code=load(BASE/'tools/stage441_crop_condition_timing.py','bytes')
  identity_by_path={x['path']:x for x in bindings}
  for name,record in manifest['artifacts'].items():check(identity_by_path[str(SRC/name)]==record,'manifest:'+name)
  check(hashlib.sha256(code).hexdigest()=='1673348e01ce772dc7d9faedad9ff531c2bbe404a0f48a95bc16347eec061a01','frozen author code SHA')
  for key in ['implementation','protocol','source_crop_rows']:
   check(receipt[key]==identity_by_path[receipt[key]['path']],'receipt input binding:'+key)
  check(receipt['protocol']['sha256']=='8ef8794e51f857aa77cbc34dda4c6bef51b9ef1b94e30c59e04a2dd8d1a45c52','frozen protocol SHA')
  check(receipt['source_review']['sha256']=='eb4adb14a65157901716b24f22340294a5927a718b24508ea1a1c2e18f1140e4','root-accepted source review binding')
  for k in ['authorization','execution_inputs','implementation','protocol']:
   check(docs['started.json'][k]==receipt[k],'started receipt binding:'+k)
  terminal=docs['terminal.json'];check(terminal['status']==receipt['status']==manifest['status']=='completed' and terminal['exit_code']==0 and receipt['failure'] is None,'single completed terminal')
  check(terminal['operations']==receipt['operations'] and receipt['operations']['actual_starts']==receipt['operations']['actual_terminals']==1,'operation receipt coherence')
  op=receipt['operations'];check(op['mother_full_read']==op['native_npz_open']==op['source_crop_rows_full_read']==op['source_review_json_read']==1 and all(x==1 for x in op['npz_members'].values()),'bounded author reads')
  check(all(op[k]==0 for k in ['source_raw_TXT_reads','API','downloads','SQL','fits','cash','forward_D','account_mutations','large_input_hashes_recomputed','Y_score_reads']),'forbidden author operations zero')
  check(receipt['inputs_before']==receipt['inputs_after'] and receipt['price_inputstat_unchanged'],'author price input stat unchanged')
  for name in ['mothers','cache']:
   for key in ['path','bytes','mtime_ns']:check(receipt['inputs_before'][name][key]==protocol['inputs'][name][key],'protocol price stat:'+name+key)
  # Only the two authorized logical calendar columns; no q or price column is accessed.
  calendar=pd.read_csv(CAL,usecols=['u_index','u_date']).sort_values('u_index').reset_index(drop=True)
  check(CAL.stat().st_size==153748 and list(calendar.columns)==['u_index','u_date'],'accepted calendar usecols/size')
  indices=calendar.u_index.to_numpy(dtype=np.int64);dates=calendar.u_date.tolist()
  check(len(indices)==4074 and np.all(np.diff(indices)==1) and len(set(dates))==4074 and dates==sorted(dates),'full consecutive unique calendar')
  closes=[datetime.combine(date.fromisoformat(x),dt_time(15),SH) for x in dates]
  position={int(u):i for i,u in enumerate(indices)}
  soy=[x for x in raw if x['crop']=='Soybeans'];by_release={x['metadata_release_date']:x for x in soy}
  check(len(raw)==618 and len(soy)==len(facts)==len(by_release)==309,'complete source population')
  actual={x['event_key']:x for x in facts};expected=[];groups=defaultdict(list);source_counts=Counter()
  for source in soy:
   day=source['metadata_release_date'];key='Soybeans:'+day+':'+source['source']['sha256'];event=actual[key]
   check(event['source_evidence']==source,'exact source evidence:'+day)
   known=all(source[k]['status']=='known' for k in ['body_release','current','adjacent_change'])
   q=None
   if known:
    previous=by_release[source['adjacent_change']['previous_metadata_release_date']]
    q=float(previous['current']['good_plus_excellent']-source['current']['good_plus_excellent']);source_counts[int(day[:4])]+=1
    check(q==-source['adjacent_change']['value_pp'],'q original adjacent direction:'+day)
   compare(event['q'],q,'q:'+day)
   reasons=[label+':'+reason for label in ['body_release','current','adjacent_change'] if source[label]['status']!='known' for reason in source[label].get('unknown_reasons',[source[label]['status']])]
   state='known' if known else 'unknown:'+';'.join(reasons or ['source_not_known'])
   check(event['source_state']==state and event['historical_first_seen']=='unknown','source state:'+day)
   body=source['body_release']['body_release_date'] if source['body_release']['status']=='known' else None
   x={'event_key':key,'q':q,'source_state':state,'body_release_date':body,'u_index':None,'u_date':None,'D_index':None,'D_date':None,
      'release_year':None,'reference_year':int(source['reference_week_date'][:4]) if source['reference_week_date'] else None,
      'availability_new_york':None,'availability_shanghai':None,'D_open_lower_bound_shanghai':None,
      'availability_before_D_open_lower_bound':None,'exact_session_time_unknown':True,'superseded_by':None,'projection_state':'missing_release'}
   if body:
    ny=datetime.combine(date.fromisoformat(body)+timedelta(days=1),dt_time(0),NY);available=ny.astimezone(SH)
    x.update(release_year=int(body[:4]),availability_new_york=ny.isoformat(),availability_shanghai=available.isoformat())
    p=bisect.bisect_left(closes,available)
    if p==len(dates):x['projection_state']='censored_no_u'
    else:
     x.update(u_index=int(indices[p]),u_date=dates[p],projection_state='censored_no_D')
     if p+1<len(dates):
      lower=datetime.combine(date.fromisoformat(dates[p]),dt_time(21),SH)
      check(lower>available,'execution lower bound after availability:'+day)
      x.update(D_index=int(indices[p+1]),D_date=dates[p+1],D_open_lower_bound_shanghai=lower.isoformat(),availability_before_D_open_lower_bound=True,projection_state='active')
     groups[x['u_index']].append(x)
   expected.append(x)
  for group in groups.values():
   ordered=sorted(group,key=lambda x:x['availability_shanghai']);winner=ordered[-1]
   check(len(ordered)==1 or ordered[-2]['availability_shanghai']!=winner['availability_shanghai'],'unique latest same-u release')
   for x in ordered[:-1]:x.update(projection_state='superseded',superseded_by=winner['event_key'])
  max_log_error=0.;max_decomp_error=0.
  for x in expected:
   e=actual[x['event_key']]
   for key,value in x.items():
    if key!='q':check(e[key]==value,'projection:'+x['event_key']+':'+key)
   check(e['crop']=='Soybeans' and e['metadata_release_date']==x['event_key'].split(':')[1],'fixed crop event identity')
   if e['projection_state']=='active':
    check(e['epoch'] is None or e['epoch'].startswith('DCE.M.'),'only M same-epoch fact identity')
    check('mother_sequence_index' in e and 'mother_event_id' in e,'emitted representative identity exists')
   else:check(all(e[k] is None for k in ['epoch','previous_close','u_close','D_open','D_close','own_u','gap','after_open','total']),'inactive is never priced')
   if e['timing_state']=='known':
    check(all(e[k] is not None and math.isfinite(e[k]) and e[k]>0 for k in ['previous_close','u_close','D_open','D_close'])
          and all(e[k] is not None for k in FIELDS[1:]),'known exact tuple is complete')
   if e['timing_state']=='missing_exact_day':
    check(any(e[k] is None for k in ['previous_close','u_close','D_open','D_close'])
          and all(e[k] is None for k in ['gap','after_open','total']),'missing exact tuple keeps D-return group null')
   for name,numerator,denominator in [('own_u','u_close','previous_close'),('gap','D_open','u_close'),('after_open','D_close','D_open'),('total','D_close','u_close')]:
    a,b=e[numerator],e[denominator]
    value=math.log(a/b) if a is not None and b is not None and a>0 and b>0 else None
    if e[name] is None:
     # The accepted pricing helper fails closed on a missing member of the
     # exact three-date tuple. Do not backfill component returns from partial prices.
     check(e['timing_state']!='known','known timing cannot omit '+name+':'+e['event_key'])
    else:
     compare(e[name],value,'log '+name+':'+e['event_key'])
     if value is not None:max_log_error=max(max_log_error,abs(e[name]-value))
   joint=all(e[k] is not None and math.isfinite(e[k]) for k in FIELDS)
   check(e['joint']==joint,'joint support:'+e['event_key'])
   reasons=[] if joint else [reason for reason,bad in [(x['source_state'],x['q'] is None),(x['projection_state'],x['projection_state']!='active'),(e['timing_state'],any(e[k] is None for k in FIELDS[1:]))] if bad]
   check(e['nonjoint_reasons']==reasons,'nonjoint reasons:'+e['event_key'])
   if joint:max_decomp_error=max(max_decomp_error,abs(e['total']-e['gap']-e['after_open']))
  compare(max_decomp_error,results['return_decomposition_max_abs_error'],'reported decomposition error')
  check(max_decomp_error<=1e-12,'decomposition tolerance')
  qualification={'known_adjacent_changes_by_release_year':{str(y):source_counts[y] for y in sorted(source_counts)},
                 'development_2017_2022':sum(source_counts[y] for y in range(2017,2023)),
                 'later_2023_2025':sum(source_counts[y] for y in range(2023,2026)),
                 'minimums':{'development':50,'later':30,'each_2023_2024_2025':10},'source_review_remaining_core_problems':0,'passed_before_price_reads':True}
  check(qualification==results['source_qualification']==docs['source_qualification.json'],'source-year qualification')
  check(results['all_source_event_count']==309 and results['era_assignment']=='decision_u_date','event total and era assignment')
  check(results['event_projection_states']==dict(Counter(x['projection_state'] for x in expected)),'projection state counts')
  check(results['source_states_all_events']==dict(Counter(x['source_state'] for x in expected)),'source state counts')
  retained=[actual[x['event_key']] for x in expected if x['projection_state'] in ['active','censored_no_D']]
  check(len({e['u_index'] for e in retained})==len(retained),'latest observations incl unknown one per u')
  full=np.full((len(calendar),5),np.nan)
  for e in retained:full[position[e['u_index']]]=[np.nan if e[k] is None else e[k] for k in FIELDS]
  def evaluate(mask,reported,label):
   data=full[mask];u_set=set(indices[mask]);events=[e for e in retained if e['u_index'] in u_set];s=stats(data)
   counts={'calendar_dates':len(data),'retained_events':len(events),'no_event_dates':len(data)-len(events),
           'q_known':sum(e['q'] is not None for e in events),'q_missing':sum(e['q'] is None for e in events),
           'q_worsening':sum(e['q'] is not None and e['q']>0 for e in events),'q_nonworsening':sum(e['q'] is not None and e['q']<=0 for e in events),
           'source_states':dict(Counter(e['source_state'] for e in events)),'timing_states':dict(Counter(e['timing_state'] for e in events)),
           'joint_events':s['joint_count'],'nonjoint_events':len(events)-s['joint_count']}
   check(counts==reported['counts'],label+':all counts')
   for k,v in s.items():compare(v,reported['statistics'][k],label+':'+k)
   return data,s
  era_points={};year_points={};bootstrap_audit={}
  for era,(begin,end) in protocol['eras'].items():
   mask=np.array([begin<=d<=end for d in dates]);report=results['eras'][era];data,s=evaluate(mask,report,era);era_points[era]=s
   n=len(data);blocks=math.ceil(n/252);rng=np.random.default_rng(20261020)
   starts=rng.integers(0,n-252+1,size=(2000,blocks))
   ix=(starts[:,:,None]+np.arange(252)[None,None,:]).reshape(2000,-1)[:,:n]
   ihash=hashlib.sha256(ix.astype('<i8').tobytes()).hexdigest();b=report['bootstrap']
   check(ihash==b['indices_sha256'] and b['same_indices_all_statistics'] is True,era+':shared complete-calendar block indices')
   check(b['resamples']==2000 and b['block_global_trade_dates']==252 and b['seed']==20261020 and b['calendar_date_count']==n,era+':bootstrap parameters')
   reconstructed={k:[] for k in STAT}
   for j,index in enumerate(ix):
    point=stats(data[index])
    for k in STAT:
     reconstructed[k].append(point[k]);compare(point[k],oldrep[era][k][j],era+':replicate:'+k+':'+str(j),2e-11)
   for k,values in reconstructed.items():
    finite=np.array([v for v in values if v is not None],float);br=b['statistics'][k]
    check(br['defined']==len(finite) and br['undefined']==2000-len(finite),era+':bootstrap defined count:'+k)
    compare(float(np.percentile(finite,2.5)) if len(finite) else None,br['lower_2_5'],era+':CI lower:'+k)
    compare(float(np.percentile(finite,97.5)) if len(finite) else None,br['upper_97_5'],era+':CI upper:'+k)
   bootstrap_audit[era]={'calendar_dates':n,'indices_sha256':ihash,'replicates_per_stat':2000,'statistics':8,'all_shared_indices':True,
                         'defined_by_stat':{k:sum(x is not None for x in reconstructed[k]) for k in STAT}}
  for year in range(2017,2026):
   _,s=evaluate(np.array([d.startswith(str(year)) for d in dates]),results['all_years'][str(year)],str(year));year_points[str(year)]=s
  positive=lambda x:x is not None and math.isfinite(x) and x>0
  points=all(positive(v[k]) for v in era_points.values() for k in PRIMARY)
  intervals=all(positive(results['eras']['later_2023_2025']['bootstrap']['statistics'][k]['lower_2_5']) for k in PRIMARY)
  years=[str(y) for y in [2023,2024,2025] if all(positive(year_points[str(y)][k]) for k in PRIMARY)]
  gate={'both_eras_two_primary_points_positive':points,'later_both_primary_CI_lower_positive':intervals,
        'later_years_both_primary_positive':years,'at_least_two_of_three_later_years':len(years)>=2,
        'independent_price_review_complete':False,'numeric_eligible_pending_review':points and intervals and len(years)>=2,
        'financial_authorized':False,'adding_exposure_authorized':False}
  check(gate==results['gate'],'all gates rebuilt')
  domain=results['domain'];check(domain['mothers']==98*len(calendar)==399252 and domain['global_trade_dates']==len(calendar) and domain['other_97_structural_mother_rows']==97*len(calendar),'98 product preserved arithmetic')
  check(domain['applicable_product']=='DCE.M' and len(domain['per_product'])==98 and sum(x['structurally_not_applicable'] for x in domain['per_product'])==97,'fixed structural applicability')
  map_u={e['u_index']:e for e in retained};states=Counter('no_new_release' if u not in map_u else ('known_event' if map_u[u]['q'] is not None else 'source_missing') for u in indices)
  check(domain['M_calendar_projection_states']==dict(states),'full M no-carry projection counts')
  check(len({e['epoch'] for e in facts if e['epoch']})==results['retained_M_cache_epochs']==results['required_M_cache_epochs']==26,'emitted M epoch count')
  output={'schema':'stage442_crop_condition_timing_independent_review_v1','started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),
          'status':'arithmetic_accepted' if not failures else 'rejected','remaining_core_problems':len(failures),'core_problems':failures,'checks':checks,
          'reviewer_code':binding(Path(__file__).resolve(),Path(__file__).read_bytes()),'input_bindings':bindings,
          'calendar':{'path':str(CAL),'bytes':CAL.stat().st_size,'logical_columns_read':['u_index','u_date'],'rows':len(calendar),'full_calendar_q_or_price_columns_read':False},
          'scope':{'all_new_actual_files_read':names,'extra_small_metadata_read': ['started.json','source_qualification.json'],
                   'extra_metadata_scope_root_accepted':True,'source_soy_events':309,'all_crop_rows':618,
                   'source_q_clock_latest_unknown_joint_prices_decomposition_rebuilt':True,'two_eras_and_nine_year_statistics_rebuilt':True,
                   'bootstrap_numeric_values_compared':32000,'author_numeric_imports':0,'author_reruns':0,
                   'root_authorization_execution_inputs':'bindings cross-checked within accepted started/receipt; original authorization/input files not reopened',
                   'quote_truth':'emitted M facts only; accepted original mother/cache identities not independently reread or repriced'},
          'largest_numeric_abs_difference':largest_difference,'max_rebuilt_log_error':max_log_error,'decomposition_max_error':max_decomp_error,
          'reconstructed_era_primary':{k:{x:v[x] for x in PRIMARY+['joint_count']} for k,v in era_points.items()},
          'reconstructed_year_primary':{k:{x:v[x] for x in PRIMARY+['joint_count']} for k,v in year_points.items()},
          'bootstrap_audit':bootstrap_audit,'gate':gate,'decision':'stop_fixed_soy_deterioration_M_delayed_open_no_sign_window_or_year_rescue',
          'limitations':['Unknown historical first-seen/first-release bytes; fixed NY next-day midnight is an assumption.',
                        'u21 is only earliest D-open lower bound; exact historical night/day session time is unverified.',
                        'Three later crop years make percentile CI conditional and fragile, not calibrated independent-week evidence.',
                        'No independent price-vendor truth, original quote source replay, costed net return, account or causal proof.'],
          'prior_failed_review':{'path':str(BASE/'outputs/stage442_crop_condition_timing_review/actual_run1/failure.json'),
                                 'reason':'reviewer incorrectly tried to fill unreported component returns from an incomplete exact-date price tuple; fixed reviewer only'},
          'operations':{'this_review_actual_runs':1,'cumulative_review_starts':2,'calendar_two_column_read':1,'source_raw_TXT_reads':0,'old_mother_reads':0,'old_cache_opens':0,
                        'author_numeric_imports':0,'author_reruns':0,'API':0,'downloads':0,'SQL':0,'fits':0,'cash':0,'forward_D':0,'account_mutations':0},
          'financial_authorized':False,'adding_exposure_authorized':False,'elapsed_seconds':time.monotonic()-t0}
  path=OUT/'review_receipt.json';path.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
  print(json.dumps({'status':output['status'],'checks':checks,'remaining_core_problems':len(failures),'max_abs_difference':largest_difference,
                    'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'gate':gate,'failures_first5':failures[:5]}))
 except Exception as exc:
  (OUT/'failure.json').write_text(json.dumps({'error':str(exc),'type':type(exc).__name__,'checks':checks,'failures':failures},ensure_ascii=False,indent=2)+'\n');raise

if __name__=='__main__':main()
