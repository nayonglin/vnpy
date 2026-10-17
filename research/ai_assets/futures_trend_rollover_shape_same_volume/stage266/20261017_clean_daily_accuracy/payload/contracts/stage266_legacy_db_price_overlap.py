"""Bounded read-only OHLC audit of final clean daily vs untouched legacy vn.py DB."""
from collections import Counter,defaultdict
from datetime import datetime
import csv,hashlib,json,math,sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage266_clean_daily'
CLEAN=OUT/'clean_daily.sqlite'
LEGACY=ROOT/'.vntrader/database.db'
EXPECTED='4191dc61218b8f4cc804f239f46f099769bd34beddff74929e284a51dc1bd598'
def sha(p):
 d=hashlib.sha256()
 with p.open('rb')as f:
  for x in iter(lambda:f.read(1024*1024),b''):d.update(x)
 return d.hexdigest()
def main():
 before={str(p):{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}for p in [CLEAN,LEGACY]}
 digest=sha(CLEAN)
 if digest!=EXPECTED:raise RuntimeError('final_clean_snapshot_sha_changed:'+digest)
 connection=sqlite3.connect(CLEAN.resolve().as_uri()+'?mode=ro',uri=True)
 connection.execute('PRAGMA query_only=ON')
 connection.execute('ATTACH DATABASE ? AS legacy',(LEGACY.resolve().as_uri()+'?mode=ro',))
 times=connection.execute("SELECT substr(datetime,11),count(*) FROM legacy.dbbardata WHERE interval='d' GROUP BY substr(datetime,11)").fetchall()
 if any(time!=' 00:00:00'for time,n in times):raise RuntimeError('nonmidnight_legacy_daily_timestamp:'+repr(times))
 old_symbol="CASE WHEN c.exchange='CZCE' THEN c.product||substr(c.contract_yyyymm,-3) WHEN c.exchange='CFFEX' THEN c.product||substr(c.contract_yyyymm,-4) ELSE lower(CASE WHEN substr(c.product,-2)='_F' THEN substr(c.product,1,length(c.product)-2) ELSE c.product END)||substr(c.contract_yyyymm,-4)||CASE WHEN substr(c.product,-2)='_F' THEN 'F' ELSE '' END END"
 query=f'''SELECT c.contract_epoch_id,c.exchange,c.product,c.contract_yyyymm,c.trade_date,c.source_id,
 c.open,c.high,c.low,c.close,c.source_locator,b.id,b.symbol,b.datetime,b.open_price,b.high_price,b.low_price,b.close_price,b.volume
 FROM daily_bars c JOIN legacy.dbbardata b INDEXED BY dbbardata_symbol_exchange_interval_datetime
 ON b.symbol=({old_symbol}) AND b.exchange=c.exchange AND b.interval='d' AND b.datetime=c.trade_date||' 00:00:00'
 ORDER BY c.contract_epoch_id,c.trade_date'''
 totals=Counter();year=defaultdict(Counter);exchange=defaultdict(Counter);source=defaultdict(Counter);family=defaultdict(Counter);exchange_year=defaultdict(Counter)
 differences=[];legacy_ids=set();epochs=set();fields=('open','high','low','close');pricekeys=set()
 for values in connection.execute(query):
  identity,ex,product,month,day,src,*rest=values
  cv=rest[:4];locator,legacy_id,legacy_symbol,legacy_dt=rest[4:8];lv=rest[8:12];legacy_volume=rest[12]
  if legacy_id in legacy_ids:raise RuntimeError('one_legacy_bar_mapped_to_multiple_full_YYYYMM:'+str(legacy_id))
  legacy_ids.add(legacy_id);epochs.add(identity)
  mismatch=[name for name,a,b in zip(fields,cv,lv)if a!=b]
  near=all(math.isclose(a,b,rel_tol=0,abs_tol=1e-8)for a,b in zip(cv,lv))
  tags=['overlap_keys','ohlc_exact_equal'if not mismatch else 'ohlc_exact_different','ohlc_equal_with_abs_1e_8'if near else 'ohlc_different_above_abs_1e_8']
  if legacy_volume<=0:tags.append('legacy_zero_volume_but_clean_real_trade')
  for counter in [totals,year[day[:4]],exchange[ex],source[src],family[src.split(':')[0]],exchange_year[ex+'|'+day[:4]]]:counter.update(tags)
  if mismatch:
   row={'contract_epoch_id':identity,'trade_date':day,'exchange':ex,'product':product,'contract_yyyymm':month,'selected_source_id':src,
       'legacy_symbol':legacy_symbol,'legacy_row_id':legacy_id,'legacy_datetime':legacy_dt,'different_fields':','.join(mismatch),
       **{'clean_'+name:value for name,value in zip(fields,cv)},**{'legacy_'+name:value for name,value in zip(fields,lv)},
       'max_absolute_difference':max(abs(a-b)for a,b in zip(cv,lv)),'equal_with_abs_1e_8':near,'legacy_volume':legacy_volume,
       'clean_source_locator':locator,'review_action':'price_disagreement_evidence_only_no_data_modified'}
   differences.append(row);pricekeys.add((identity,day))
 total_clean=connection.execute('SELECT count(*) FROM daily_bars').fetchone()[0]
 connection.close()
 after={str(p):{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}for p in [CLEAN,LEGACY]}
 if before!=after:raise RuntimeError('input_size_or_mtime_changed_during_read_only_audit')
 fields_out=['contract_epoch_id','trade_date','exchange','product','contract_yyyymm','selected_source_id','legacy_symbol','legacy_row_id','legacy_datetime','different_fields',*[prefix+name for prefix in ['clean_','legacy_']for name in fields],'max_absolute_difference','equal_with_abs_1e_8','legacy_volume','clean_source_locator','review_action']
 diffpath=OUT/'stage266_legacy_db_price_overlap_differences.csv'
 with diffpath.open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=fields_out,lineterminator='\n');w.writeheader();w.writerows(differences)
 report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'scope':'Full exact contract-date overlap, 2010+ final clean vs legacy daily only; no old open_interest comparison',
    'status':'PASS_READ_ONLY_PRICE_COMPARISON','clean_path':str(CLEAN),'clean_sha256':digest,'clean_expected_sha256':EXPECTED,'legacy_path':str(LEGACY),
    'script_sha256':sha(Path(__file__)),'inputs_before':before,'inputs_after':after,'input_size_mtime_unchanged':before==after,
    'clean_total_rows':total_clean,'clean_without_legacy_exact_key':total_clean-totals['overlap_keys'],'overlap_contract_epochs':len(epochs),'totals':dict(totals),
    'by_year':{k:dict(v)for k,v in sorted(year.items())},'by_exchange':{k:dict(v)for k,v in sorted(exchange.items())},
    'by_source_family':{k:dict(v)for k,v in sorted(family.items())},'by_selected_source_id':{k:dict(v)for k,v in sorted(source.items())},
    'by_exchange_year':{k:dict(v)for k,v in sorted(exchange_year.items())},
    'join_contract':{'CZCE':'uppercase PRODUCT+last3(YYYYMM), exact same trade_date; full epoch retained','CFFEX':'uppercase PRODUCT+last4(YYYYMM), exact same trade_date',
    'others':'lowercase PRODUCT+last4(YYYYMM), F suffix preserved','legacy_interval':'d','legacy_datetime':'trade_date + 00:00:00',
    'all_legacy_daily_timestamp_groups':times,'legacy_daily_unique_index_used':True,'duplicate_legacy_row_id_across_epochs':0,'continuous_contracts_joined':False},
    'differences':{'path':str(diffpath),'sha256':sha(diffpath),'rows':len(differences),'unique_contract_date_keys':len(pricekeys),'sample':differences[:20]},
    'interpretation':'Exact floating-point OHLC equality reported separately from abs1e-8. A price mismatch is retained evidence; no source declared correct from legacy alone.',
    'old_open_interest_not_read_or_compared':True,'source_writes':0,'main_database_writes':0,'data_corrections':0,'backtests':0,'training_runs':0}
 output=OUT/'stage266_legacy_db_price_overlap.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:report[k]for k in ['clean_sha256','clean_total_rows','overlap_contract_epochs','totals','by_source_family','by_year','by_exchange','differences']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
