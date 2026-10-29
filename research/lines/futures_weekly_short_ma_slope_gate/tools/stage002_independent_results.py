"""Independent Stage002 financial/weekly audit plus mirrored long-entry checks."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
from stage001_independent_results import audit
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
checks=0

def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-10),label)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='001');args=ap.parse_args();p=L/'outputs'/f'stage002_C_attempt{args.attempt}';result=audit(p);before={str(f):sha(f) for f in p.iterdir() if f.is_file()}
 pre=json.loads((p/'preflight.json').read_text());ok(pre['short_ma_slope_gate_enabled'] is True and pre['long_ma_slope_gate_enabled'] is True,'both_actual_preflight_gates')
 acceptance=json.loads((p/'long_ma_slope_acceptance.json').read_text());ok(acceptance['accepted'] is True and acceptance['enabled'] is True and set(acceptance['signals'])=={'long_case1a','long_case2'} and acceptance['operator']=='OR','long_gate_contract')
 weekly=pd.read_csv(p/'weekly_bars.csv');weeks={(r.vt_symbol,r.week_end):r for r in weekly.itertuples()};long=json.loads((p/'long_ma_slope_decisions.json').read_text());short=json.loads((p/'short_ma_slope_decisions.json').read_text());can=pd.read_csv(p/'entry_candidates.csv');signal_counts={};blocks={};would={}
 for r in long:
  vals,ds=r['source_week_closes'],r['source_week_ends'];ok(r['signal'] in {'long_case1a','long_case2'} and r['direction']=='long','long_signal_class');ok(len(vals)==len(ds)==11 and ds[-1]==r['signal_date'],'long_fresh_source');epochs=set()
  for day,value in zip(ds,vals):
   w=weeks[(r['vt_symbol'],day)];near(w.close,value,'long_source_close');epochs.add(w.contract_epoch_id)
  ok(len(epochs)==1,'long_single_epoch');g=weekly.loc[weekly.vt_symbol.eq(r['vt_symbol'])&weekly.contract_epoch_id.eq(next(iter(epochs)))&weekly.week_end.le(r['signal_date'])].sort_values('week_end').tail(11);ok(g.week_end.tolist()==ds,'long_latest11_not_arbitrary')
  m5=sum(vals[-5:])/5;p5=sum(vals[-6:-1])/5;m10=sum(vals[-10:])/10;p10=sum(vals[-11:-1])/10
  for k,v in [('ma5_current',m5),('ma5_previous',p5),('ma10_current',m10),('ma10_previous',p10),('ma5_delta',m5-p5),('ma10_delta',m10-p10)]:near(r[k],v,'independent_long_MA:'+k)
  expected=m5<p5 or m10<p10;ok(r['would_block']==expected and r['enabled'] is True,'strict_negative_OR');applied=expected and r['selected_volume_before']>0;ok(r['applied_block']==applied,'long_applied_positive_size');near(r['selected_volume_after'],0 if applied else r['selected_volume_before'],'long_volume_zero_only_if_blocked');signal_counts[r['signal']]=signal_counts.get(r['signal'],0)+1;would[r['signal']]=would.get(r['signal'],0)+int(expected);blocks[r['signal']]=blocks.get(r['signal'],0)+int(applied)
  rows=can.loc[can.date.astype(str).str[:10].eq(r['signal_date'])&can.contract_vt_symbol.eq(r['vt_symbol'])&can.direction.eq('long')&can.signal.eq(r['signal'])]
  ok(len(rows)>=1,'long_decision_candidate_exists')
  if applied:ok(rows.selected_volume.eq(0).all() and rows.candidate_status.ne('opened').all(),'blocked_long_no_candidate_open')
 # Every native long candidate and actual long-open fill must be covered, including long_case2.
 all_native=can.loc[can.direction.eq('long')&can.signal.isin(['long_case1a','long_case2'])]
 for r in all_native.itertuples():
  proof=[v for v in long if v['vt_symbol']==r.contract_vt_symbol and v['signal_date']==str(r.date)[:10] and v['signal']==r.signal];ok(bool(proof),'every_long_candidate_covered')
  if r.candidate_status=='opened':ok(not any(v['would_block'] for v in proof),'opened_long_nonnegative')
 fills=pd.read_csv(p/'trades.csv');anchors=pd.read_csv(p/'execution_anchor_requests.csv');roll=pd.read_csv(p/'rollover_shape_same_volume.csv');contexts={}
 for direction,name,decisions in [('多','long',long),('空','short',short)]:
  cnt={'native':0,'rollover':0};signals={}
  for t in fills.loc[fills.direction.eq(direction)&fills.offset.eq('开')].itertuples():
   a=anchors.loc[anchors.order_id.astype(str).eq(str(t.order_id))];ok(len(a)==1,'actual_open_unique_anchor');day=str(a.iloc[0].signal_date)[:10];native=can.loc[can.date.astype(str).str[:10].eq(day)&can.contract_vt_symbol.eq(t.vt_symbol)&can.direction.eq(name)&can.candidate_status.eq('opened')];rr=roll.loc[roll.date.astype(str).str[:10].eq(day)&roll.target_contract_vt_symbol.eq(t.vt_symbol)&roll.direction.eq(name)&roll.status.eq('targeted')&roll.final_volume.gt(0)]
   ok((len(native)>0)!=(len(rr)>0),'unique_native_or_roll_context')
   if len(native):
    cnt['native']+=1;ds=[r for r in decisions if r['signal_date']==day and r['vt_symbol']==t.vt_symbol];ok(bool(ds) and not any(r['would_block'] or r['applied_block'] for r in ds),'actual_native_passes_gate')
    for value in native.signal.unique():signals[value]=signals.get(value,0)+1
   else:cnt['rollover']+=1
  contexts[name]={**cnt,'native_signal_counts':signals}
 # Fill-derived required-held-day completeness, independent of source position row presence.
 dates=pd.read_csv(p/'daily.csv',usecols=['date']).date.astype(str).str[:10].tolist();presence={}
 for c in pd.read_csv(p/'positions.csv',usecols=['date','vt_symbol','start_pos','end_pos','trade_count'],chunksize=100000):
  active=c.loc[c[['start_pos','end_pos','trade_count']].abs().sum(axis=1).ne(0)]
  for day,g in active.groupby('date'):presence.setdefault(str(day)[:10],set()).update(g.vt_symbol)
 groups={day:g for day,g in fills.groupby('trading_date')};held={}
 for day in dates:
  g=groups.get(day,fills.iloc[:0]);required={s for s,q in held.items() if q!=0}|set(g.vt_symbol);ok(required<=presence.get(day,set()),'required_financial_day_present')
  for t in g.itertuples():held[t.vt_symbol]=held.get(t.vt_symbol,0)+(1 if t.direction=='多' else -1)*t.volume
 # Reused controls are full accepted ledgers with unchanged data/settings; absence of longflag means false.
 current_settings=json.loads((p/'actual_strategy_settings.json').read_text());current_effective=json.loads((p/'effective_parameters.json').read_text());controls={}
 for label,arm in [('original','A'),('short_only','C')]:
  control=L/'outputs'/f'stage001_{arm}_attempt003';cp=json.loads((control/'preflight.json').read_text());ok(cp['data_identity']==pre['data_identity'],'same_data_identity:'+label);ok(json.loads((control/'actual_strategy_settings.json').read_text())==current_settings,'same_settings:'+label);ok(json.loads((control/'effective_parameters.json').read_text())==current_effective,'same_effective:'+label);ok(cp.get('long_ma_slope_gate_enabled',False) is False,'old_control_long_off:'+label);controls[label]=dict(path=str(control),long_enabled=False,short_enabled=cp['short_ma_slope_gate_enabled'])
 old=json.loads((L/'stages/stage001_delivery_manifest.json').read_text());bad=[q for q,h in old['files_sha256'].items() if not Path(q).is_file() or sha(q)!=h];ok(not bad,'all_stage001_delivery_3105_unchanged')
 ok(before=={str(f):sha(f) for f in p.iterdir() if f.is_file()},'new_attempt_unchanged_during_review')
 result.update(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,long_decision_count=len(long),long_signal_decision_counts=signal_counts,long_would_block_counts=would,long_applied_block_counts=blocks,actual_open_context_counts=contexts,additional_checks=checks,reused_controls=controls,old_delivery_mismatches=bad,production_qualified=False,financial_replays=0)
 (L/'stages/stage002_independent_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_files_sha256'},ensure_ascii=False,default=str))
if __name__=='__main__':main()
