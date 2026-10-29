"""Read-only verification of independent19 daily extension. No financial replay."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';OUT=LINE/'outputs/data_stage001_20261029';D=OUT/'data_approved';BASE=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage032_latest_data/data_approved')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def main():
 checks={};manifest=json.loads((D/'source_manifest.json').read_text())['files'];bad=[p for p,d in manifest.items() if sha(p)!=d];checks['source_manifest_hashes_unchanged']=not bad;checks['bound_files']=len(manifest)
 r=json.loads((D/'receipt.json').read_text());checks['completed_day']=r['date_end']=='2026-10-29' and r['latest_day_is_completed_week'] is False and r['next_trading_date']=='2026-10-30';checks['bounded_original19']=len(r['products'])==19 and r['historical_main_reconstruction_complete'] is False and r['units']=='single_sided_volume_close_oi'
 old=pd.read_csv(BASE/'physical_epoch_daily.csv',dtype=str).fillna('');new=pd.read_csv(D/'physical_epoch_daily.csv',dtype=str).fillna('');tail=new.iloc[len(old):];checks['old_physical_all_fields_exact']=new.iloc[:len(old)].reset_index(drop=True).equals(old.reset_index(drop=True));checks['old_physical_bytes_prefix']=(D/'physical_epoch_daily.csv').read_bytes().startswith((BASE/'physical_epoch_daily.csv').read_bytes());checks['new_28_only_20261029']=len(tail)==28 and set(tail.date)=={'2026-10-29'};checks['unique_physical_keys']=not new.duplicated(['vt_symbol','date']).any()
 for n in ['metadata.csv','physical_epochs.csv']:
  checks[n+'_bytes_unchanged']=sha(BASE/n)==sha(D/n)
 oldmap=pd.read_csv(BASE/'mapping.csv',dtype=str).fillna('');newmap=pd.read_csv(D/'mapping.csv',dtype=str).fillna('');checks['old_mapping_all_fields_exact']=newmap.iloc[:len(oldmap)].reset_index(drop=True).equals(oldmap.reset_index(drop=True));checks['old_mapping_bytes_prefix']=(D/'mapping.csv').read_bytes().startswith((BASE/'mapping.csv').read_bytes());m=newmap.iloc[len(oldmap):];checks['new_mapping_19_only_20261029']=len(m)==19 and set(m.date)=={'2026-10-29'} and set(m.continuous_symbol_vt)==set(r['products'])
 checks['inherited_mapping_universe_unchanged']=set(newmap.continuous_symbol_vt)==set(oldmap.continuous_symbol_vt);checks['active_append_original19_only']=set(m.continuous_symbol_vt)==set(r['products']);checks['no_future_approved_daily']=new.date.max()=='2026-10-29';checks['no_future_mapping']=newmap.date.max()=='2026-10-29'
 select=json.loads((OUT/'raw/selection.json').read_text());required={(s,'2026-10-29') for s in set(m.main_contract_vt)|set(select['frozen_held'])|set(select['frozen_pending'])};checks['required_keys_covered']=required<=set(zip(tail.vt_symbol,tail.date));checks['positive_real_OHLCV']=all(float(x)>0 for row in tail[['open','high','low','close','volume']].values for x in row)
 epochs=pd.read_csv(D/'physical_epochs.csv',dtype=str).fillna('');ep=epochs.set_index('contract_epoch_id');checks['new_epoch_identity']=all(ep.loc[row.contract_epoch_id,'vt_symbol']==row.vt_symbol and ep.loc[row.contract_epoch_id,'contract_yyyymm']==row.contract_yyyymm and (not ep.loc[row.contract_epoch_id,'listed_date'] or ep.loc[row.contract_epoch_id,'listed_date']<=row.date) and (not ep.loc[row.contract_epoch_id,'delisted_date'] or row.date<=ep.loc[row.contract_epoch_id,'delisted_date']) for row in tail.itertuples())
 rawrows=json.loads((OUT/'raw/new_rows.json').read_text());bykey={(x['vt_symbol'],x['date']):x for x in rawrows};checks['raw_rows_exact']=all(all(float(getattr(row,k))==float(bykey[(row.vt_symbol,row.date)][k]) for k in ['open','high','low','close','volume','close_oi']) for row in tail.itertuples())
 with sqlite3.connect(f'file:{D/"daily.sqlite"}?mode=ro',uri=True) as db:
  checks['sqlite_integrity']=db.execute('pragma integrity_check').fetchone()[0]=='ok';db.execute('attach database ? as frozen',(str(BASE/'daily.sqlite'),));missing=db.execute('select count(*) from (select * from frozen.dbbardata except select * from main.dbbardata)').fetchone()[0];counts=[db.execute('select count(*) from '+n+'.dbbardata').fetchone()[0] for n in ['frozen','main']];checks['old_sqlite_all_rows_exact']=missing==0 and counts[1]==counts[0]+28;checks['sqlite_rows_before_after']=counts
  dif=[]
  for x in tail.itertuples():
   code,ex=x.vt_symbol.split('.');v=db.execute("select open_price,high_price,low_price,close_price,volume,open_interest from main.dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,ex,x.date)).fetchall();expected=[tuple(float(getattr(x,k)) for k in ['open','high','low','close','volume','close_oi'])]
   if v!=expected:dif.append(x.vt_symbol)
  checks['new_sqlite_fields_exact']=not dif
 probe=json.loads((OUT/'probe_receipt.json').read_text());checks['no_order_or_CTP']=probe['ctp_connected'] is False and probe['order_api_calls']==0 and all(v==0 for v in probe['guards'].values())
 failures=[k for k,v in checks.items() if isinstance(v,bool) and not v];result={'status':'PASS_BOUNDED_DATA_ONLY' if not failures else 'FAIL','checks':checks,'failed_checks':failures,'source_mismatches':bad,'completed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'financial_replays':0,'review_scope':'Separate code recomputes preservation, raw numerical parity, mapping, physical epochs, all bound hashes; not independent-vendor truth or final post-backtest review.'}
 p=LINE/'stages/stage001_data_acceptance.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));return bool(failures)
if __name__=='__main__':raise SystemExit(main())
