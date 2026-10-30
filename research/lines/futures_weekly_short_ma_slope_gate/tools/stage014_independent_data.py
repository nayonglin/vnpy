"""Independent Stage014 additive data/native mapping/warmup admission. No download or finance."""
from pathlib import Path
from datetime import date,timedelta
from collections import Counter
import ast,hashlib,json,sqlite3,time
import numpy as np
import pandas as pd
from stage014_independent_scope import canonical_starts,mature,completed_weeks,DEFAULT_MONTHS
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=L/'stages';BASE=L/'outputs/data_stage001_20261029/data_approved';OUT=L/'outputs/data_stage014_20261030';DATA=OUT/'data_approved';TARGET='2026-10-30';OLD='2026-10-29';FIELDS=['open','high','low','close','volume','close_oi'];checks=0;cache={}
def ok(value,label):
 global checks
 checks+=1
 if not value:raise AssertionError(label)
def near(a,b,label):ok(np.allclose(a,b,rtol=1e-10,atol=1e-7,equal_nan=False),label)
def sha(p):
 q=str(Path(p).resolve());s=Path(q).stat();stat=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
 if q in cache and cache[q]['stat']==stat:return cache[q]['sha256']
 h=hashlib.sha256()
 with Path(q).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 ok(Path(q).stat().st_mtime_ns==s.st_mtime_ns,'stable_hash_read:'+q);digest=h.hexdigest();cache[q]={'sha256':digest,'stat':stat};return digest
load=lambda p:json.loads(Path(p).read_text())
def prefix_equal(old,new):
 with Path(old).open('rb') as a,Path(new).open('rb') as b:
  while True:
   x=a.read(8*1024*1024)
   if not x:break
   ok(b.read(len(x))==x,'byte_prefix:'+Path(old).name)
 return True

def main():
 started=time.monotonic();output=S/'stage014_independent_data_admission.json';ok(not output.exists(),'immutable_data_admission');receipt=load(DATA/'receipt.json');source=load(DATA/'source_manifest.json')
 ok(receipt['date_end']==TARGET and receipt['next_trading_date']=='2026-11-02' and receipt['data_ready'] and receipt['data_ready_for_bounded_replay'],'real_completed_cutoff');ok(not receipt['historical_main_reconstruction_complete'] and receipt['units']=='single_sided_volume_close_oi','bounded_original_units');ok(len(receipt['products'])==19 and len(set(receipt['products']))==19,'original19')
 for p,h in source['files'].items():ok(sha(p)==h,'bound_data_source:'+p)
 for name in ['metadata.csv','physical_epochs.csv']:ok(sha(BASE/name)==sha(DATA/name),'unchanged_asset:'+name)
 for name in ['physical_epoch_daily.csv','mapping.csv']:prefix_equal(BASE/name,DATA/name)
 old=pd.read_csv(BASE/'physical_epoch_daily.csv',dtype=str).fillna('');physical=pd.read_csv(DATA/'physical_epoch_daily.csv',dtype=str).fillna('');mapping=pd.read_csv(DATA/'mapping.csv',dtype=str).fillna('');oldmap=pd.read_csv(BASE/'mapping.csv',dtype=str).fillna('');epochs=pd.read_csv(DATA/'physical_epochs.csv',dtype=str).fillna('')
 ok(physical.iloc[:len(old)].reset_index(drop=True).equals(old),'all_old_physical_fields_exact');ok(mapping.iloc[:len(oldmap)].reset_index(drop=True).equals(oldmap),'all_old_mapping_fields_exact');new=physical.iloc[len(old):];newmap=mapping.iloc[len(oldmap):];ok(len(new)==185 and new.date.eq(TARGET).all() and not physical.duplicated(['vt_symbol','date']).any(),'exact185_new_unique_bars');ok(len(newmap)==19 and newmap.date.eq(TARGET).all() and set(newmap.continuous_symbol_vt)==set(receipt['products']),'exact19_new_mapping');ok(physical.date.max()==mapping.date.max()==TARGET,'no_future_bars_or_mapping')
 # Full historical SQL row identity, including primary keys and all metadata columns.
 olddb=sqlite3.connect('file:'+str(BASE/'daily.sqlite')+'?mode=ro',uri=True);newdb=sqlite3.connect('file:'+str(DATA/'daily.sqlite')+'?mode=ro',uri=True);ok(newdb.execute('pragma integrity_check').fetchone()==('ok',),'sqlite_integrity')
 ok(olddb.execute('pragma table_info(dbbardata)').fetchall()==newdb.execute('pragma table_info(dbbardata)').fetchall(),'identical_daily_schema');cols=[x[1] for x in olddb.execute('pragma table_info(dbbardata)')];query='select '+','.join('"'+c+'"' for c in cols)+' from dbbardata order by id';a=olddb.execute(query);b=newdb.execute(query+ ' limit '+str(olddb.execute('select count(*) from dbbardata').fetchone()[0]));sqlcount=0;sqlhash=hashlib.sha256()
 while True:
  x=a.fetchmany(10000);y=b.fetchmany(10000)
  if not x:ok(not y,'no_extra_old_sql_rows');break
  ok(x==y,'old_sql_all_column_row_prefix');sqlhash.update(json.dumps(x,separators=(',',':')).encode());sqlcount+=len(x)
 ok(sqlcount==1345757 and newdb.execute('select count(*) from dbbardata').fetchone()[0]==sqlcount+185,'sql_old_plus185');ok(newdb.execute("select count(*) from dbbardata where substr(datetime,1,10)>?",(TARGET,)).fetchone()[0]==0,'no_forming_SQL')
 for row in new.to_dict('records'):
  code,exchange=row['vt_symbol'].split('.');q=newdb.execute("select open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,exchange,TARGET)).fetchall();ok(len(q)==1,'new_SQL_key_unique');near(q[0],[float(row[k]) for k in FIELDS],'new_SQL_OHLCV_closeOI')
 olddb.close();newdb.close()
 selection=load(OUT/'raw/selection.json');wanted=set(selection['wanted']);active=set()
 for e in epochs.to_dict('records'):
  if e['product_vt_symbol'] not in receipt['products']:continue
  if e['listed_date'] and e['listed_date']>TARGET:continue
  if e['delisted_date'] and e['delisted_date']<TARGET:continue
  if e['contract_yyyymm']<'202610':continue
  active.add(e['vt_symbol'])
 recent=set(old.loc[old.date.eq(OLD),'vt_symbol']);required=set(newmap.main_contract_vt)|set(selection['frozen_held'])|set(selection['frozen_pending']);ok(wanted==active|recent|required and len(wanted)==189,'all_active_epochs_tails_and_required_union_not_only23_positions');ok(set(selection['active_epoch_candidates'])==active,'independent_lifecycle_selection')
 status={r['vt_symbol']:r for r in load(OUT/'raw/contract_statuses.json')};coverage={r['vt_symbol']:r for r in load(OUT/'raw/contract_coverage.json')};ok(set(status)==set(coverage)==wanted,'complete_contract_classification');accepted={r['vt_symbol']:r for r in new.to_dict('records')};excluded=0;invalid={}
 for sym in sorted(wanted):
  p=OUT/'raw/raw_daily'/(sym+'.csv');raw=pd.read_csv(p,float_precision='round_trip');ok(sha(p)==status[sym]['raw_sha256'],'raw_contract_hash');valid=raw.loc[pd.to_numeric(raw.datetime).gt(0)&pd.to_numeric(raw.id).ge(0)].copy();valid['day']=pd.to_datetime(valid.datetime,unit='ns',utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d');ok(not valid.day.duplicated().any(),'unique_raw_day');target=valid.loc[valid.day.eq(TARGET)];ok(len(target)==status[sym]['target_rows']==1,'observed_target_for_every_candidate');future=int(valid.day.gt(TARGET).sum());ok(future==status[sym]['excluded_forming_or_future_rows'],'exact_future_exclusion');excluded+=future;t=target.iloc[0];ok(int(t.duration)==86400,'true_daily_duration');v=np.array([t[k] for k in FIELDS],float);clean=bool(np.isfinite(v).all() and (v[:4]>0).all() and v[4]>0 and v[5]>=0 and v[2]<=min(v[0],v[3])<=max(v[0],v[3])<=v[1])
  if clean:
   ok(sym in accepted,'all_clean_raw_targets_admitted');near(v,[float(accepted[sym][k]) for k in FIELDS],'raw_to_physical_same_day_OHLCV_closeOI');ok(accepted[sym]['source_sha256']==sha(p),'physical_raw_binding');match=epochs.loc[epochs.vt_symbol.eq(sym)&epochs.contract_epoch_id.eq(accepted[sym]['contract_epoch_id'])];ok(len(match)==1,'unique_physical_epoch');e=match.iloc[0];ok((not e.listed_date or e.listed_date<=TARGET) and (not e.delisted_date or TARGET<=e.delisted_date),'known_epoch_lifecycle')
  else:
   ok(sym not in accepted and sym not in required,'invalid_observation_never_mark_or_required_bar');invalid[sym]={'raw_values':dict(zip(FIELDS,v.tolist())),'historical_accepted_bars':int(old.vt_symbol.eq(sym).sum()),'all_mapping_occurrences':int(mapping.main_contract_vt.eq(sym).sum())};ok(invalid[sym]['all_mapping_occurrences']==0,'invalid_symbol_unreachable_from_any_main_history')
 ok(set(invalid)=={'SM704.CZCE','SM706.CZCE','SM707.CZCE','SM708.CZCE'} and excluded==143 and required<=set(accepted),'classified4_not_missing_required_and143_forming_excluded')
 fresh=pd.read_csv(OUT/'raw/fresh_calendar.csv',dtype=str).fillna('')
 for r in newmap.itertuples():
  g=fresh.loc[fresh.date.str[:10].eq(TARGET)];ok(len(g)==1 and g.iloc[0][r.continuous_symbol_tq]==r.main_contract_tq,'fresh_mapping_raw_same_day')
 lookup={(r.vt_symbol,r.date):r.contract_epoch_id for r in physical.itertuples()};known=set();classification_counts={}
 for filename,count in [('known_no_trade_main.csv',573),('structural_unavailable_main.csv',18)]:
  q=pd.read_csv(DATA/filename,dtype=str);ok(len(q)==count and sha(BASE/filename)==sha(DATA/filename),'inherited_exact_classification:'+filename);known.update(zip(q.vt_symbol,q.date));classification_counts[filename]=count
 financialmap=mapping.loc[mapping.continuous_symbol_vt.isin(receipt['products'])&mapping.date.ge('2015-01-01')&mapping.main_contract_vt.ne('')];missing={(r.main_contract_vt,r.date) for r in financialmap.itertuples() if (r.main_contract_vt,r.date)not in lookup};ok(missing==known,'all591_absent_financial_main_keys_exactly_prior_classification_no_new_unknown');ok(all((sym,TARGET)in lookup for sym in newmap.main_contract_vt),'new19main_all_positive_real_bars')
 calendar=sorted(mapping.date.unique());weeks=completed_weeks(calendar);ok(any(days[-1]==TARGET for days in weeks.values()) and all(max(ds)<=TARGET for ds in weeks.values()),'Friday_completed_without_future_Monday');datesbyepoch={(sym,ep):set(g.date) for (sym,ep),g in physical.groupby(['vt_symbol','contract_epoch_id'])};warmups=[]
 for start in canonical_starts():
  first=next(day for day in calendar if day>=start);warm=(date.fromisoformat(start)-timedelta(days=365)).isoformat();rows=mapping.loc[mapping.date.eq(first)&mapping.continuous_symbol_vt.isin(receipt['products'])];detail=[]
  for row in rows.itertuples():
   sym=row.main_contract_vt
   if not sym:detail.append(dict(product=row.continuous_symbol_vt,main='',pre_first_complete_epoch_weeks=0));continue
   ep=lookup.get((sym,first))
   if ep is None:
    ok((sym,first)in known,'first_target_gap_is_known_classification');detail.append(dict(product=row.continuous_symbol_vt,main=sym,pre_first_complete_epoch_weeks=0,first_day_classified_nonbar=True));continue
   available=datesbyepoch[(sym,ep)];n=sum(warm<=ds[0] and ds[-1]<first and set(ds)<=available for ds in weeks.values());detail.append(dict(product=row.continuous_symbol_vt,main=sym,contract_epoch_id=ep,pre_first_complete_epoch_weeks=n))
  warmups.append(dict(start=start,actual_first=first,raw_load_from=warm,financial_days=sum(start<=d<=TARGET for d in calendar),mature=mature(start),mapped_on_first=sum(bool(x['main']) for x in detail),targets_with21_pre_first_complete_weeks=sum(x['pre_first_complete_epoch_weeks']>=21 for x in detail),per_target=detail,readiness_note='Data-only pre-first upper bound; runtime21ready/41store and first-day state/queue independently audited per run. Insufficient or prelisting history is retained, never forced ready.'))
 ok(len(warmups)==59 and sum(x['mature'] for x in warmups)==54,'frozen_default59_54_5')
 portfolio=ROOT/'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py';native_opens=[]
 for fn in ast.walk(ast.parse(portfolio.read_text())):
  if isinstance(fn,ast.FunctionDef):
   for call in ast.walk(fn):
    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='_open_position':
     ok(fn.name in ['on_bars','_handle_rollover'] and isinstance(call.args[1],ast.Name) and call.args[1].id=='target_contract','all_base_open_call_targets_are_mapping_or_inherited_owned_target');native_opens.append(dict(method=fn.name,line=call.lineno,expression=ast.unparse(call)))
 ok(len(native_opens)==4,'complete_four_base_open_routes');safety=ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage022_historical_safety.py'
 for t in ['mapping_today: dict[str, str] = self.daily_mapping.get(current_date, {})','target_contract: str = mapping_today.get(product_vt, "")','self._handle_rollover(state, target_contract, bars)']:ok(t in portfolio.read_text(),'native_mapping_source_identity')
 cachep=S/'stage014_independent_hash_cache.json';ok(not cachep.exists(),'immutable_new_cache');cachep.write_text(json.dumps({'files':cache},indent=2)+'\n');identity={k:sha(DATA/n) for k,n in [('daily_sqlite_sha256','daily.sqlite'),('mapping_sha256','mapping.csv'),('physical_epoch_daily_sha256','physical_epoch_daily.csv'),('receipt_sha256','receipt.json')]}
 result=dict(schema='stage014_independent_additive_data_admission_v1',accepted=True,status='PASS_DATA_FOR_FROZEN_59_CANARY_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=[],checks=checks,data_directory=str(DATA),data_identity=identity,source_manifest_sha256=sha(DATA/'source_manifest.json'),old_SQL_rows_exact=sqlcount,old_SQL_all_columns_digest=sqlhash.hexdigest(),old_physical_rows_exact=len(old),new_physical_rows=len(new),new_mapping_rows=len(newmap),requested_contracts=len(wanted),observed_target_contracts=len(status),accepted_positive_targets=len(accepted),forming_rows_excluded=excluded,invalid_targets=invalid,invalid_targets_reachability_proof='Four native symbols never appear in any frozen main mapping, including old reused CZCE epochs. Original cold starts have zero positions/orders, native entry target comes only from mapping_today and rollover target uses that same mapping; actual-position resolver only discovers existing inventory. AI/addon disabled. By induction none can be opened or held in any of59 cold starts. No zero observation is turned into a bar. Every actual held/traded key is independently gated per run.',native_open_routes=native_opens,reachability_source_files_sha256={str(p):sha(p) for p in [portfolio,safety]},start_months=list(DEFAULT_MONTHS),starts=canonical_starts(),cutoff=TARGET,mature_windows=54,observation_windows=5,warmup_windows=warmups,new19_main_keys_positive_present=True,all_unclassified_financial_main_keys_present=True,inherited_nonbar_main_classifications=classification_counts,latest_day_completed_week=True,no_future_rows_in_approved_data=True,source_consensus_claim=False,limitations=['Fresh Tq 10/30 after market close, not exchange-final arbitration; 143 forming/future observations excluded.','Frozen <=29 contains inherited historical/PIT/lifecycle gaps. Warmup is bounded same-epoch available history; not all mapped targets are forcibly21ready.','Four genuine zero/invalid SM observations classified, not priced; source/mapping induction plus actual held-key runtime gates required.','Zero fees, static metadata/margin and capacity limits inherited. Repeated overlapping history is not independent OOS.'],source_hash_cache=str(cachep),source_hash_cache_sha256=sha(cachep),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(output),'sha256':sha(output),'checks':checks,'seconds':result['seconds']},ensure_ascii=False))
if __name__=='__main__':main()
