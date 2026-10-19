from pathlib import Path
from collections import Counter,defaultdict
from bisect import bisect_right
import csv,json,hashlib,ast
P=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_risk025_contract_weekly_v1')
assert hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest()=='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35'
def rd(n):
 with (P/(n+'.csv')).open() as f:return list(csv.DictReader(f))
events=rd('pending_open_lifecycle_events');tr=rd('trades');aud=rd('open_budget_audit');cancels=rd('unfilled_intent_cancellations');calendar=[x['date'] for x in rd('trading_calendar')];nxt=dict(zip(calendar[:-1],calendar[1:]));bars={(x['date'],x['vt_symbol']):x for x in rd('market_daily')};mapping={(x['date'],x['continuous_symbol_vt']):x['main_contract_vt'] for x in rd('mapping')};accounts={x['date']:json.loads(x['positions']) for x in rd('account_snapshots')};errors=[]
check=lambda n,x,d=None:errors.append(dict(check=n,detail=d)) if not x else None
fills={json.loads(x['stage068_signal_snapshot'])['snapshot_id']:x for x in tr if x['offset']=='open'};rejects=defaultdict(list)
for x in aud:
 if x['signal_snapshot'] and x['filled'].lower()!='true':
  q=json.loads(x['signal_snapshot'])
  if q:rejects[q['snapshot_id']].append(dict(date=x['date'],reason=x['reason'],order=x['order_id']))
forced={}
for x in cancels:
 for q in json.loads(x['receipt_json']):
  if q:forced[q['snapshot_id']]=dict(date=x['date'],reason=x['reason'])
known={};rows=[];bindings={};pre_fill=[]
for i,x in enumerate(events):
 q=json.loads(x['receipt_json']) if x['receipt_json'] else None
 if isinstance(q,dict):items=[q]
 elif isinstance(q,list):items=[v for v in q if v]
 else:items=[]
 if x['event']=='preserve':bindings[(x['date'],x['vt_symbol'])]=items[0]
 if x['event']=='cached_order_dispatch':
  q=bindings.get((x['date'],x['vt_symbol']));check('cached_has_same_day_original_preserve',q is not None,i);items=[q] if q else []
 for q in items:
  sid=q['snapshot_id'];key=json.dumps(q,sort_keys=True,separators=(',',':'));check('unchanged_original_identity',sid not in known or known[sid]==key,sid);known[sid]=key
  trade=fills.get(sid);firstday=nxt[q['signal_datetime'][:10]];firstbar=bars.get((firstday,x['vt_symbol']));firstdeferral=firstbar is None or float(firstbar['volume'])<q['authorized_volume']
  if x['event']=='preserve':check('preserved_comes_after_real_low_volume_or_missing',firstdeferral,[sid,firstday,firstbar['volume'] if firstbar else None])
  if x['event']=='cached_order_dispatch':check('cached_not_real_execution_bar',(x['date'],x['vt_symbol']) not in bars,[x['date'],x['vt_symbol']])
  if x['event']=='cancel' and x['reason'].startswith('deferred_open_pre_fill'):
   bar=bars.get((x['date'],x['vt_symbol']));check('prefill_cancel_had_real_executable_qty',bar is not None and float(bar['volume'])>=q['authorized_volume'],sid);pre_fill.append(dict(date=x['date'],contract=x['vt_symbol'],receipt=sid,original_date=q['signal_datetime'][:10],qty=q['authorized_volume'],bar_volume=bar['volume'] if bar else None,mapping=mapping.get((x['date'],x['product_vt_symbol'])),reason=x['reason']))
  row=dict(event_index=i,event=x['event'],date=x['date'],contract=x['vt_symbol'],reason=x['reason'],snapshot_id=sid,receipt_sha256=hashlib.sha256(key.encode()).hexdigest(),signal_date=q['signal_datetime'][:10],authorized_volume=q['authorized_volume'],signal_budget=q['target_risk_amount'],first_next_session=firstday,first_next_volume=firstbar['volume'] if firstbar else '',first_real_deferral=firstdeferral,current_map=mapping.get((x['date'],x['product_vt_symbol']),''),actual_eod=accounts[x['date']].get(x['vt_symbol'],0),fill_trade_id=trade['trade_id'] if trade else '',fill_date=trade['date'] if trade else '',fill_qty=trade['volume'] if trade else '',risk_rejections=json.dumps(rejects.get(sid,[])),forced_cancellation=json.dumps(forced.get(sid,{})))
  rows.append(row)
first_mapflip=[]
for x in tr:
 if x['offset']!='open':continue
 q=json.loads(x['stage068_signal_snapshot']);day=q['signal_datetime'][:10]
 if x['date']==nxt[day] and mapping.get((x['date'],q['product_vt_symbol']),'')!=x['vt_symbol']:
  first_mapflip.append(dict(trade=x['trade_id'],contract=x['vt_symbol'],signal=day,fill=x['date'],current_mapping=mapping.get((x['date'],q['product_vt_symbol']),'')))
with Path('/private/tmp/stage101_actual_enabled_pending_trace.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
r=dict(source_manifest_sha256=hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest(),audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),events=len(events),evidence_rows=len(rows),unique_receipts=len(known),preserved_unique=len({x['snapshot_id'] for x in rows if x['event']=='preserve'}),first_next_open_mapping_flip_fills=first_mapflip,real_deferred_pre_fill_mapping_cancellations=pre_fill,outcomes={sid:dict(filled_trade=fills.get(sid,{}).get('trade_id'),rejections=rejects.get(sid,[]),forced_cancel=forced.get(sid)) for sid in known},errors=errors,error_count=len(errors))
Path('/private/tmp/stage101_actual_enabled_pending_trace.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
