"""Read-only sealed Stage014 crosscheck; never replay financial history."""
import ast,csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGE=LINE/'stages'
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate')
TARGET='2026-10-30'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report=json.loads((STAGE/'Stage018_signal_scope_20261030_result.json').read_text());products=report['products'];mains={r['vt_symbol']:r for r in products}
 out=dict(schema='Stage018.sealed-output-crosscheck.v1',target_date=TARGET,scope='read_only_existing_Stage014_outputs_not_actual_broker_or_new_replay',financial_replays=0,production_qualified=False,files={},paths=[])
 for arm in ['stage014_C_20150101_attempt001','stage014_C_20260601_attempt001']:
  root=OLD/'outputs'/arm;result=dict(path=str(root),simulated_start=arm.split('_')[2],rows={})
  for name in ['weekly_bars.csv','weekly_readiness.csv','entry_candidates.csv','pending_orders.csv','short_price_range_decisions.csv','positions.csv','reserve_daily.csv','actual_strategy_settings.json','preflight.json','input_manifest.json']:
   p=root/name;out['files'][str(p)]=dict(before_sha256=sha(p))
   if name.endswith('.json'):
    value=json.loads(p.read_text())
    if name=='input_manifest.json':
     result['approved_input_manifest_pins']={Path(key).name:val for key,val in value.items() if str(key).startswith(str(OLD/'outputs/data_stage014_20261030/data_approved'))}
    continue
   with p.open() as stream:
    reader=csv.DictReader(stream)
    rows=[r for r in reader if r.get('date',r.get('week_end',r.get('signal_date')))==TARGET]
   if name=='positions.csv':rows=[r for r in rows if float(r['end_pos'])!=0]
   if name=='weekly_bars.csv':rows=[r for r in rows if r['vt_symbol'] in mains and r['contract_epoch_id']==mains[r['vt_symbol']]['physical_epoch_id']]
   result['rows'][name]=rows
   if name=='weekly_bars.csv':
    assert len(rows)==19
    assert all(float(r['close'])==mains[r['vt_symbol']]['close'] and float(r['open_interest'])==mains[r['vt_symbol']]['close_oi'] for r in rows)
  for name in result['rows']:
   p=root/name;out['files'][str(p)]['after_sha256']=sha(p);assert out['files'][str(p)]['before_sha256']==out['files'][str(p)]['after_sha256']
  out['paths'].append(result)
 # Exact current completed-week OHLCVOI from the accepted physical source,
 # compared with sealed actual weekly adapter output, not daily-close proxies.
 p=OLD/'outputs/data_stage014_20261030/data_approved/physical_epoch_daily.csv';h=sha(p)
 bysymbol={s:[] for s in mains}
 with p.open() as f:
  for r in csv.DictReader(f):
   if r['vt_symbol'] in mains and '2026-10-26'<=r['date']<=TARGET and r['contract_epoch_id']==mains[r['vt_symbol']]['physical_epoch_id']:bysymbol[r['vt_symbol']].append(r)
 sealed={r['vt_symbol']:r for r in out['paths'][0]['rows']['weekly_bars.csv']}
 parity=[]
 for symbol,rows in sorted(bysymbol.items()):
  rows.sort(key=lambda r:r['date']);assert len(rows)==5
  values=dict(open=float(rows[0]['open']),high=max(float(r['high']) for r in rows),low=min(float(r['low']) for r in rows),close=float(rows[-1]['close']),volume=sum(float(r['volume']) for r in rows),open_interest=float(rows[-1]['close_oi']))
  assert all(abs(value-float(sealed[symbol][key]))<=1e-9 for key,value in values.items())
  assert [r['date'] for r in rows]==ast.literal_eval(sealed[symbol]['source_days'])
  parity.append(dict(vt_symbol=symbol,physical_epoch_id=mains[symbol]['physical_epoch_id'],source_days=[r['date'] for r in rows],**values))
 assert sha(p)==h
 out['source_weekly_OHLCVOI_parity']=parity;out['physical_source_sha256_before_after']=h;out['all_19_latest_weekly_source_values_equal']=True
 out['signals']=[r for r in products if r.get('signal_data',{}).get('signal')]
 out['native_signals']=report['native_signal_products'];out['conditional_intents']=report['decision']['intents']
 out['original_paths_are_distinct_and_not_adopted_as_actual_positions']=True
 (STAGE/'Stage018_signal_scope_crosscheck_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(signal_count=len(out['signals']),native_signal_count=len(out['native_signals']),intents=len(out['conditional_intents']),weekly_parity_contracts=len(parity),paths=[dict(name=Path(p['path']).name,entry_candidates=len(p['rows']['entry_candidates.csv']),pending_orders=len(p['rows']['pending_orders.csv']),simulated_positions=[(r['vt_symbol'],r['end_pos']) for r in p['rows']['positions.csv']]) for p in out['paths']]),ensure_ascii=False))
if __name__=='__main__':main()
