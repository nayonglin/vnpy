"""Read-only source reachability evidence for four zero-volume non-main contracts."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';BASE=LINE/'outputs/data_stage001_20261029/data_approved';OUT=LINE/'outputs/data_stage014_20261030';D=OUT/'data_approved'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 output=LINE/'stages/stage014_zero_daily_reachability.json'
 if output.exists():raise ValueError('immutable_reachability_evidence_exists')
 mapping=pd.read_csv(BASE/'mapping.csv',dtype=str);newmap=pd.read_csv(D/'admitted_20261030_mapping.csv',dtype=str)
 daily=pd.read_csv(BASE/'physical_epoch_daily.csv',dtype={'vt_symbol':str,'date':str,'contract_yyyymm':str})
 raw={r['vt_symbol']:r for r in json.loads((OUT/'raw/new_rows.json').read_text())};coverage=json.loads((OUT/'raw/contract_coverage.json').read_text())
 symbols=sorted(r['vt_symbol']for r in coverage if r['classification']!='accepted_positive_real_daily');rows=[]
 with sqlite3.connect(f'file:{BASE/"daily.sqlite"}?mode=ro',uri=True)as db:
  for symbol in symbols:
   x=daily[daily.vt_symbol.str.casefold().eq(symbol.casefold())].copy();epoch='2027'+symbol[3:5];e=x[x.contract_yyyymm.eq(epoch)]
   positive=x[(x[['open','high','low','close','volume']]>0).all(axis=1)].sort_values('date');last=positive.tail(1)
   code,ex=symbol.split('.');sql=db.execute("select count(*),min(datetime),max(datetime)from dbbardata where symbol=?and exchange=?and interval='d'",(code,ex)).fetchone()
   rows.append(dict(vt_symbol=symbol,physical_epoch='CZCE.SM.'+epoch,mapping_all_history_count=int(mapping.main_contract_vt.eq(symbol).sum()),mapping_all_history_casefold_count=int(mapping.main_contract_vt.str.casefold().eq(symbol.casefold()).sum()),new_target_main_count=int(newmap.main_contract_vt.str.casefold().eq(symbol.casefold()).sum()),physical_prior_alias_rows=len(x),physical_prior_current_epoch_rows=len(e),sqlite_prior_alias_rows=sql[0],sqlite_first=sql[1],sqlite_last=sql[2],latest_prior_positive=last[['date','open','high','low','close','volume','close_oi','contract_epoch_id']].to_dict('records'),raw_target_fields={k:raw[symbol][k]for k in ['date','open','high','low','close','volume','close_oi','duration']},data_only_conclusion='Never a main contract in any frozen historical mapping or target30; existing physical data does not imply strategy reachability. Independent code audit must confirm all position-creation paths require mapped main and fresh initial positions are zero.'))
 assert len(rows)==4 and all(r['mapping_all_history_casefold_count']==r['new_target_main_count']==0 for r in rows)
 sources={str(p):sha(p)for p in [BASE/'mapping.csv',BASE/'physical_epoch_daily.csv',BASE/'daily.sqlite',D/'admitted_20261030_mapping.csv',OUT/'raw/new_rows.json',OUT/'raw/contract_coverage.json',Path(__file__)]}
 result=dict(schema='stage014_zero_daily_never_main_evidence_v1',status='PASS_DATA_EVIDENCE_PENDING_INDEPENDENT_CODE_REACHABILITY',created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),contracts=rows,source_files_sha256=sources,financial_replays=0,market_downloads=0,production_accesses=0,claim='No synthetic bar inserted; zero/invalid four are classified and cannot be silently treated as prices. Code reachability proof is separate and required before finance.')
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'contracts':len(rows),'sha256':sha(output)}))
if __name__=='__main__':main()
