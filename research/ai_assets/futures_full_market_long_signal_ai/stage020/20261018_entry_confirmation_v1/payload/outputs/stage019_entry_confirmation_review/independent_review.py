"""Independent Stage019 numerical review; never imports/calls Stage018 implementation."""
import csv,hashlib,io,json,math,time,traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
R=Path.cwd();L=R/'research/lines/futures_full_market_long_signal_ai';O=L/'outputs/stage019_entry_confirmation_review';P=L/'outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes'
started=datetime.now().astimezone().isoformat();clock=time.monotonic();checks={};bound={};cache={}
def dump(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def verify(b):
 p=Path(b['path']);raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest==b['sha256'],str(p)
 if 'bytes'in b:assert len(raw)==b['bytes']
 bound[str(p)]={'sha256':digest,'bytes':len(raw)};return raw

def compare(label,a,b,tol=2e-10):
 aa=np.asarray(a,dtype=float);bb=np.asarray(b,dtype=float);assert aa.shape==bb.shape,(label,aa.shape,bb.shape)
 assert np.array_equal(np.isnan(aa),np.isnan(bb)),label+' missingness'
 good=np.isfinite(aa);assert np.isfinite(bb[good]).all(),label+' finite'
 error=float(np.max(np.abs(aa[good]-bb[good])))if good.any()else 0.
 assert error<=tol,(label,error);checks[label]={'values':int(good.sum()),'max_abs_error':error}

def mean(a):
 v=np.asarray(a,float);v=v[np.isfinite(v)];return float(v.mean())if len(v)else None

def nested(label,a,b):
 if isinstance(a,dict):
  assert set(a)<=set(b),(label,set(a)-set(b))
  for k,v in a.items():nested(label+'.'+k,v,b[k])
 elif isinstance(a,(float,np.floating)):
  assert b is not None and abs(float(a)-float(b))<=2e-10,(label,a,b)
 else:assert a==b,(label,a,b)

def readcsv(binding,cols=None):return pd.read_csv(io.BytesIO(verify(binding)),compression='gzip',dtype=str,keep_default_na=False,usecols=cols)

try:
 expected={'manifest.json':'0d0bce1477ca430f85f1720005715f73318e6199a152bcfbad61d1847e018b8f','metrics.json':'5f51593ccfc539131003453fc62196cbe51ec60e79cb0798162fc8f994c1d9d6','actual_terminal.json':'417e5a1b4f2f78bc39f7dc7756dc977b22a0fc5a2146bb676503b1aa5a7562ec'}
 docs={n:json.loads(verify({'path':str(P/n),'sha256':s}))for n,s in expected.items()};m=docs['manifest.json'];reported=docs['metrics.json'];terminal=docs['actual_terminal.json']
 assert terminal['status']=='completed'and terminal['exit_code']==0 and terminal['attempts']==3 and terminal['completed_full_experiment']==1
 for k in ['model_fits','SQL_queries','financial_runs','network_calls','downloads']:assert terminal[k]==m[k]==0
 for b in [m['source'],m['test'],m['protocol'],*m['test_compile_evidence'],*m['prior_failed_attempt_evidence']]:verify(b)
 assert m['source']['sha256']=='e50126b4833b21005b775e41209c89e9a762b705159762f3b8bd2233c37aacb2'
 assert m['test']['sha256']=='dfb0b92833bbd37097458ef0ec9f17fffe58c98532c9c21e9d1fdf0c025cfd6c'
 for b in m['artifacts']:
  if Path(b['path']).name not in expected and Path(b['path']).name!='event_intervals.csv.gz':verify(b)
 e=readcsv(m['event_intervals']);assert len(e)==399252 and not e.event_id.duplicated().any()and not e.duplicated(['product_id','u_date']).any()
 ids=['event_id','product_id','product','exchange','u_date','reference_epoch','planned_execution_date','status','direction']
 caches=m['source_bindings']['original_caches'];x=readcsv(caches[0],ids+['high']);f=readcsv(caches[1],ids+['family_id','feature_ready','history_state','label_identified','label_state','label_known_date','atr20','gross_lower','gross_upper','proxy_lower','proxy_upper']);a=readcsv(caches[2],['event_id','u_date','reference_epoch','planned_execution_date','ideal_entry_F','risk_distance','D_high','D_low','D_close'])
 assert len(x)==len(f)==len(e)
 for key in ids:assert e[key].equals(x[key])and e[key].equals(f[key]),key
 for key in ['family_id','feature_ready','history_state','label_identified','label_state','label_known_date']:assert e[key].equals(f[key]),key
 assert e.direction.eq('long').all()and (e.exchange+'.'+e['product']).equals(e.product_id)
 assert e.family_id.equals(e.product_id.str.removesuffix('_F'))
 assert e.feature_ready.isin(['0','1']).all()and e.label_identified.isin(['0','1']).all()
 dates=json.loads((P/'source_calendar_dates.json').read_text())['dates'];full=np.load(io.BytesIO(verify(caches[3])),allow_pickle=False);full=[str(z)[:4]+'-'+str(z)[4:6]+'-'+str(z)[6:]for z in full]
 assert len(dates)==4074 and dates==[z for z in full if '2010-01-01'<=z<='2026-10-16']
 successors=dict(zip(full[:-1],full[1:]));assert e.planned_execution_date.equals(e.u_date.map(successors).fillna(''))
 assert set(e.u_date)==set(dates)and len(set(e.product_id))==98
 known=e.label_identified.eq('1');ready=e.feature_ready.eq('1');assert (ready|~known).all();assert known.sum()==194168 and ready.sum()==194709
 assert e.loc[known,'label_known_date'].equals(e.loc[known,'planned_execution_date'])and e.loc[~known,'label_known_date'].eq('').all()
 label_numeric=[c for c in e if c not in ids+['family_id','history_state','feature_ready','label_identified','label_state','label_known_date','evaluation_state','trigger_state','family_group']]
 assert e.loc[~known,label_numeric].eq('').all().all();assert e.loc[~known,'trigger_state'].eq('unknown').all()
 assert set(label_numeric)<=set(m['label_only_columns']) and m['all_D_coordinates_and_outcomes_are_label_only']is True
 assert not set(e)&{'open','high','low','close','D_high','D_low','D_close','ideal_entry_F','risk_distance','atr20'}
 assert not a.event_id.duplicated().any();assert set(a.event_id)<=set(e.event_id);a=a.set_index('event_id').loc[e.loc[known,'event_id']]
 for key in ['u_date','reference_epoch','planned_execution_date']:assert np.array_equal(a[key],e.loc[known,key]),key
 k=e.loc[known].copy();numeric=k[label_numeric].astype(float);k[label_numeric]=numeric
 for key in ['feature_ready','label_identified','family_group']:e[key]=e[key].astype(int);k[key]=k[key].astype(int)
 F=a.ideal_entry_F.astype(float).to_numpy();H=a.D_high.astype(float).to_numpy();LL=a.D_low.astype(float).to_numpy();C=a.D_close.astype(float).to_numpy();r=a.risk_distance.astype(float).to_numpy();B=x.loc[known,'high'].astype(float).to_numpy()
 assert np.isfinite(np.column_stack([F,H,LL,C,r,B])).all()and (r>0).all()and(F-r>0).all()
 compare('r_equals_u_quarter_ATR',r,.25*f.loc[known,'atr20'].astype(float).to_numpy())
 coords=np.column_stack([(B-F)/r,(H-F)/r,(LL-F)/r,(C-F)/r]);compare('all_normalized_coordinates',coords,numeric[['b','h','l','c']])
 entry=np.maximum(F,B);gap=F>=B;fill=H>=B;intraday=fill&~gap;stop=LL<=entry-r;profit=H>=entry+4*r;close_stop=C<=entry-r;cr=(C-entry)/r
 bits={'raw_gap_open':gap,'raw_trigger_reached':fill,'raw_low_le_confirm_stop':stop,'raw_high_ge_confirm_profit':profit,'raw_close_le_confirm_stop':close_stop,'raw_open_stop_touch':LL<=F-r,'raw_open_profit_touch':H>=F+4*r,'confirm_day_close_r':cr}
 for key,value in bits.items():compare('raw_price_'+key,value,numeric[key],0 if key!='confirm_day_close_r'else 2e-10)
 alo=np.where(LL<=F-r,-1,np.where(H>=F+4*r,4,(C-F)/r));ahi=np.where(H>=F+4*r,4,np.where(LL<=F-r,-1,(C-F)/r))
 compare('OPEN_raw_price_recompute_009_lower',alo,f.loc[known,'gross_lower'].astype(float));compare('OPEN_raw_price_recompute_009_upper',ahi,f.loc[known,'gross_upper'].astype(float))
 compare('OPEN_inherited_gross',np.column_stack([alo,ahi]),numeric[['open_gross_lower','open_gross_upper']])
 klo=np.where(~fill,0,np.where(gap,alo,np.where(stop,-1,np.where(profit,4,cr))))
 khi=np.where(~fill,0,np.where(gap,ahi,np.where(profit,4,np.where(stop&close_stop,-1,cr))))
 states=np.where(gap,'gap_open',np.where(fill,'intraday_trigger','not_filled'));assert np.array_equal(states,k.trigger_state);compare('fill',fill,numeric.confirm_fill,0)
 vals={}
 for prefix,fee in [('',.2),('stress_',1.)]:
  al,au=alo-fee,ahi-fee;kl,ku=klo-fee*fill,khi-fee*fill
  vals.update({prefix+'open_lower':al,prefix+'open_upper':au,prefix+'confirm_lower':kl,prefix+'confirm_upper':ku,prefix+'paired_lower':np.where(gap,0,kl-au),prefix+'paired_upper':np.where(gap,0,ku-al)})
 for key,v in vals.items():compare('event_'+key,v,numeric[key]);k[key]=v
 for name in ['open','confirm','paired']:
  v=vals[name+'_upper']-vals[name+'_lower'];compare(name+'_width',v,numeric[name+'_width']);k[name+'_width']=v
 groups=e.family_id.map(lambda z:int(hashlib.sha256(z.encode()).hexdigest(),16)%2);assert np.array_equal(e.family_group,groups)
 correct_state=np.where(e.feature_ready.eq(0),'not_feature_ready',np.where(known,'identified',e.label_state));assert np.array_equal(e.evaluation_state,correct_state)
 norm_stop=coords[:,2]<=-1;norm_profit=coords[:,1]>=4
 boundary_rows=int(((norm_stop!=(LL<=F-r))|(norm_profit!=(H>=F+4*r))).sum())
 checks['all_identity_and_state_counts']={'outer':len(e),'ready':int(ready.sum()),'known':int(known.sum()),'unknown_ready':int((ready&~known).sum()),'raw_vs_normalized_OPEN_touch_rows':boundary_rows,'raw_bits_checked':len(k)*7,'label_only':True}
 print(json.dumps({'progress':'all_rows_identity_raw_prices_and_intervals_verified','known':len(k),'raw_normalized_touch_disagreements':boundary_rows}),flush=True)
 def count(frame):
  z=frame.loc[frame.label_identified.eq(1)];rr=frame.feature_ready.eq(1);un=frame.loc[rr&frame.label_identified.eq(0)];yes=z.loc[z.confirm_fill.eq(1)];no=z.loc[z.confirm_fill.eq(0)]
  return dict(all_outer_rows=len(frame),feature_ready_rows=int(rr.sum()),identified_rows=len(z),ready_unknown_rows=len(un),unknown_label_states=dict(Counter(un.label_state)),evaluation_states=dict(Counter(frame.evaluation_state)),trigger_states=dict(Counter(frame.trigger_state)),confirm_fill_rows=len(yes),confirm_fill_dates=yes.u_date.nunique(),confirm_fill_families=yes.family_id.nunique(),not_fill_rows=len(no),not_fill_dates=no.u_date.nunique(),not_fill_families=no.family_id.nunique(),open_ambiguous_rows=int(z.open_width.gt(0).sum()),confirm_ambiguous_rows=int(z.confirm_width.gt(0).sum()),paired_outer_nonsingleton_rows=int(z.paired_width.gt(0).sum()),no_fill_conditional_positive_open_lower=mean(np.maximum(no.open_lower,0)),no_fill_conditional_positive_open_upper=mean(np.maximum(no.open_upper,0)))
 # Replace actual numeric values by independently derived values, retaining unknowns as NaN.
 for col in label_numeric:e[col]=pd.to_numeric(e[col],errors='coerce')
 for col in [*vals,'open_width','confirm_width','paired_width']:e.loc[known,col]=k[col].to_numpy()
 nested('all_counts',count(e),reported['all_outer_counts']);nested('manifest_counts',count(e),m['counts'])
 reconstructed={};cimax=0.;bootstrap_hashes={}
 for scope in ['main','family_0','family_1']:
  outer=e if scope=='main'else e.loc[e.family_group.eq(int(scope[-1]))];q=outer.loc[outer.label_identified.eq(1)].copy();size=q.groupby('u_date').size();p=q.groupby('u_date').confirm_fill.sum()/size;pr=q.u_date.map(p).to_numpy();g=q.trigger_state.eq('gap_open').to_numpy();nf=q.confirm_fill.eq(0).to_numpy()
  for prefix in ['', 'stress_']:
   al=q[prefix+'open_lower'].to_numpy();au=q[prefix+'open_upper'].to_numpy();kl=q[prefix+'confirm_lower'].to_numpy();ku=q[prefix+'confirm_upper'].to_numpy()
   q[prefix+'participation_lower']=np.where(g,(1-pr)*al,kl-pr*au);q[prefix+'participation_upper']=np.where(g,(1-pr)*au,ku-pr*al)
  if scope=='main':
   compare('event_day_p',pr,numeric.day_p)
   for col in ['participation_lower','participation_upper','stress_participation_lower','stress_participation_upper']:compare('event_'+col,q[col],numeric[col])
  for side in ['lower','upper']:
   positive=np.maximum(q['open_'+side].to_numpy(),0);q['unfilled_right_tail_'+side]=np.where(nf,positive,0);q['filled_open_positive_'+side]=np.where(nf,0,positive)
   if scope=='main':compare('event_unfilled_right_tail_'+side,q['unfilled_right_tail_'+side],numeric['unfilled_right_tail_'+side])
  q['fill_rate']=q.confirm_fill;q['gap_rate']=g.astype(float);q['intraday_trigger_rate']=q.trigger_state.eq('intraday_trigger').astype(float);q['not_fill_rate']=nf.astype(float);q['participation_cost_residual']=.2*(pr-q.confirm_fill);q['participation_stress_cost_residual']=pr-q.confirm_fill
  numbers=[*vals,'participation_lower','participation_upper','stress_participation_lower','stress_participation_upper','fill_rate','gap_rate','intraday_trigger_rate','not_fill_rate','participation_cost_residual','participation_stress_cost_residual','unfilled_right_tail_lower','unfilled_right_tail_upper','filled_open_positive_lower','filled_open_positive_upper','open_width','confirm_width','paired_width']
  daily=q.groupby('u_date')[numbers].sum().div(size,axis=0);daily['identified_rows']=size;daily=daily.reindex(dates)
  compare(scope+'_cost_cancel_lower',daily.participation_lower,daily.stress_participation_lower,2e-12);compare(scope+'_cost_cancel_upper',daily.participation_upper,daily.stress_participation_upper,2e-12)
  reconstructed[scope]={}
  for period,start in [('all_2010','2010-01-01'),('primary_2020','2020-01-01')]:
   dd=daily.loc[daily.index>=start];ff=outer.loc[outer.u_date>=start];saved=pd.read_csv(P/f'daily_{scope}_{period}.csv',dtype={'u_date':str},float_precision='round_trip').set_index('u_date');assert list(dd.index)==list(saved.index)
   compare(scope+'_'+period+'_daily',dd[saved.columns],saved)
   result={'cohort':count(ff),'date_equal_means':{c:mean(dd[c])for c in dd},'source_grid_days':len(dd),'no_identified_days':int(dd.identified_rows.isna().sum())};nested(scope+period,result,reported['scopes'][scope][period]);reconstructed[scope][period]=result
   if scope=='main':
    saved_ci=reported['scopes'][scope][period]['bootstrap'];cols=list(saved_ci['metrics']);values=dd[cols].to_numpy(float);finite=np.isfinite(values);prefix=np.vstack([np.zeros(len(cols)),np.cumsum(np.where(finite,values,0),axis=0)]);counts=np.vstack([np.zeros(len(cols),dtype=int),np.cumsum(finite,axis=0)]);n=len(dd);block=60;blocks=(n+block-1)//block;lengths=np.full(blocks,block);lengths[-1]=n-block*(blocks-1);rng=np.random.default_rng(20261018);ih=hashlib.sha256();samples=[]
    for repeat in range(2000):
     begin=rng.integers(0,n-block+1,size=blocks);ix=(begin[:,None]+np.arange(block)).ravel()[:n];ih.update(ix.astype('<i8').tobytes());end=begin+lengths;v=(prefix[end]-prefix[begin]).sum(axis=0);den=(counts[end]-counts[begin]).sum(axis=0);samples.append(np.divide(v,den,out=np.full(len(cols),np.nan),where=den>0))
    assert ih.hexdigest()==saved_ci['common_indices_sha256'];bootstrap_hashes[period]=ih.hexdigest();samples=np.array(samples)
    for j,col in enumerate(cols):
     samp=samples[:,j];samp=samp[np.isfinite(samp)];ci=np.quantile(samp,[.025,.975]);actual={'mean':mean(values[:,j]),'ci95_lower':float(ci[0]),'ci95_upper':float(ci[1]),'finite_source_days':int(finite[:,j].sum()),'finite_bootstrap_replicates':len(samp)};nested(period+'CI'+col,actual,saved_ci['metrics'][col]);cimax=max(cimax,abs(actual['ci95_lower']-saved_ci['metrics'][col]['ci95_lower']),abs(actual['ci95_upper']-saved_ci['metrics'][col]['ci95_upper']))
    reconstructed[scope][period]['bootstrap']=saved_ci
  annual={}
  for y in range(2010,2027):
   yy=str(y);dd=daily.loc[daily.index.str.startswith(yy)];ff=outer.loc[outer.u_date.str.startswith(yy)];rr={'cohort':count(ff),'date_equal_means':{c:mean(dd[c])for c in dd},'source_grid_days':len(dd),'no_identified_days':int(dd.identified_rows.isna().sum())};nested(scope+yy,rr,reported['scopes'][scope]['annual'][yy]);annual[yy]=rr
  reconstructed[scope]['annual']=annual
  print(json.dumps({'progress':'scope_all_daily_annual_period_counts_verified','scope':scope}),flush=True)
 main=reconstructed['main'];prim=main['primary_2020'];whole=main['all_2010'];cis=prim['bootstrap']['metrics'];pos=lambda v:v is not None and v>0
 gates={'primary_fill_dates_at_least_60':prim['cohort']['confirm_fill_dates']>=60,'primary_fill_families_at_least_8':prim['cohort']['confirm_fill_families']>=8,'primary_confirm_lower_ci_positive':pos(cis['confirm_lower']['ci95_lower']),'primary_paired_lower_ci_positive':pos(cis['paired_lower']['ci95_lower']),'primary_participation_lower_ci_positive':pos(cis['participation_lower']['ci95_lower']),'all_2010_confirm_lower_positive':pos(whole['date_equal_means']['confirm_lower']),'all_2010_paired_lower_positive':pos(whole['date_equal_means']['paired_lower']),'all_2010_participation_lower_positive':pos(whole['date_equal_means']['participation_lower']),'same_mask_cost_1R_primary_confirm_lower_positive':pos(prim['date_equal_means']['stress_confirm_lower']),'four_complete_years_paired_lower_positive':sum(pos(main['annual'][str(y)]['date_equal_means']['paired_lower'])for y in range(2020,2026))>=4,'partial_2026_confirm_lower_positive':pos(main['annual']['2026']['date_equal_means']['confirm_lower'])}
 for group in [0,1]:
  for metric in ['confirm_lower','paired_lower']:gates[f'family_{group}_primary_{metric}_positive']=pos(reconstructed[f'family_{group}']['primary_2020']['date_equal_means'][metric])
 assert gates==reported['gates']and len(gates)==15;assert reported['quality_screen_pass']==m['quality_screen_pass']==all(gates.values());assert reported['entry_increment_detected']==m['entry_increment_detected']==gates['primary_paired_lower_ci_positive']
 for key in ['real_economic_labels_ready','financial_ready','production_qualified']:assert m[key]is False and reported[key]is False
 receipt={'schema':'stage019_entry_confirmation_review_v1','status':'accepted_calculation_rejected_quality_screen','reviewer':'ema_financial_overall_review','Critical':0,'Important':0,'Minor':0,'qualified_for_fixed_proxy_experiment':True,'experiment_manifest':bound[str(P/'manifest.json')]|{'path':str(P/'manifest.json')},'source':m['source'],'test':m['test'],'protocol':m['protocol'],'counts':reported['all_outer_counts'],'checks':checks,'ci_max_absolute_error':cimax,'bootstrap_index_sha256':bootstrap_hashes,'gates':gates,'gates_true':sum(gates.values()),'gates_false':len(gates)-sum(gates.values()),'quality_screen_pass':False,'entry_increment_detected':False,'source_bindings_verified':bound,'scope':'all399252 identities; all194168 raw price predicates and intervals; all six daily outputs; 3 scopes x 17 years; two common-bootstrap grids, all 15 gates; no source experiment import/replay','declined_to_judge':['actual futures execution, price jumps, tick, capacity or economic PnL','global sharpness of paired outer bounds or proof confirmation is truly worse','future generalization, new setup or all AI alpha','independent requalification of original daily database or inherited009 data contract'],'real_economic_labels_ready':False,'financial_ready':False,'production_qualified':False,'model_fits':0,'financial_runs':0,'SQL_queries':0,'downloads':0,'overfitting_added':False,'continued_value':'accept arithmetic and stop this fixed screening package; retain unidentified execution boundary'}
 dump('review_receipt.json',receipt);dump('actual_terminal.json',{'status':'completed','exit_code':0,'started_at':started,'finished_at':datetime.now().astimezone().isoformat(),'elapsed_seconds':time.monotonic()-clock,'command':'.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage019_entry_confirmation_review/independent_review.py','model_fits':0,'financial_runs':0,'SQL_queries':0,'author_entrypoint_calls':0});print(json.dumps({'status':receipt['status'],'C_I_M':[0,0,0],'outer':len(e),'known':len(k),'gates_true':sum(gates.values()),'ci_max_abs_error':cimax,'elapsed_seconds':time.monotonic()-clock}),flush=True)
except BaseException as exc:
 dump('actual_terminal.json',{'status':'failed','exit_code':1,'started_at':started,'finished_at':datetime.now().astimezone().isoformat(),'elapsed_seconds':time.monotonic()-clock,'error':type(exc).__name__+': '+str(exc),'checks_before_failure':checks});raise
