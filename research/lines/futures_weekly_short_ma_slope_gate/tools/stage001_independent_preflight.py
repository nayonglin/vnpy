from pathlib import Path
import hashlib,json,sqlite3,math,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';D=LINE/'outputs/data_stage001_20261029/data_approved';B=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage032_latest_data/data_approved')
checks={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def check(k,v):
 checks[k]=bool(v)
 if not v:raise AssertionError(k)
def run():
 receipt=json.loads((D/'receipt.json').read_text());manifest=json.loads((D/'source_manifest.json').read_text())['files']
 check('all_78_source_bindings',all(Path(p).is_file() and sha(p)==h for p,h in manifest.items()))
 for n in ['metadata.csv','physical_epochs.csv']:check(n+'_unchanged',sha(D/n)==sha(B/n))
 for n in ['physical_epoch_daily.csv','mapping.csv']:check(n+'_byte_prefix',(D/n).read_bytes().startswith((B/n).read_bytes()))
 old=pd.read_csv(B/'physical_epoch_daily.csv',dtype=str).fillna('');new=pd.read_csv(D/'physical_epoch_daily.csv',dtype=str).fillna('');app=pd.read_csv(D/'admitted_20261029_daily.csv')
 check('accepted_old_fields_exact',old.equals(new.iloc[:len(old)].reset_index(drop=True)))
 check('accepted28_unique_only29',len(new)==len(old)+28 and len(app)==28 and not new.duplicated(['vt_symbol','date']).any() and set(app.date)=={'2026-10-29'})
 check('receipt_date_and_units',receipt['date_end']=='2026-10-29' and receipt['units']=='single_sided_volume_close_oi' and receipt['next_trading_date']=='2026-10-30' and receipt['latest_day_is_completed_week'] is False)
 with sqlite3.connect(f'file:{D/"daily.sqlite"}?mode=ro',uri=True) as db:
  db.execute('attach database ? as old',(str(B/'daily.sqlite'),))
  check('sqlite_integrity',db.execute('pragma integrity_check').fetchone()[0]=='ok')
  new_db_count=db.execute('select count(*) from dbbardata').fetchone()[0];b=db.execute('select count(*) from old.dbbardata').fetchone()[0]
  check('all_old_sqlite_fields',db.execute('select count(*) from (select * from old.dbbardata except select * from main.dbbardata)').fetchone()[0]==0 and new_db_count==b+28)
  for r in app.itertuples():
   check(r.vt_symbol+'_source_sha',sha(r.source_path)==r.source_sha256)
   raw=pd.read_csv(r.source_path);raw['date']=pd.to_datetime(raw.datetime,unit='ns',utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d');raw=raw.loc[raw.date.eq('2026-10-29')]
   check(r.vt_symbol+'_raw_daily',len(raw)==1 and int(raw.iloc[0].duration)==86400)
   code,exchange=r.vt_symbol.split('.');q=db.execute("select open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where symbol=? and exchange=? and substr(datetime,1,10)='2026-10-29' and interval='d'",(code,exchange)).fetchall();wanted=[getattr(r,k) for k in ['open','high','low','close','volume','close_oi']]
   check(r.vt_symbol+'_raw_fields',all(float(raw.iloc[0][k])==v for k,v in zip(['open','high','low','close','volume','close_oi'],wanted)))
   check(r.vt_symbol+'_db_fields',q==[tuple(wanted)] and min(wanted[:5])>0 and wanted[-1]>=0)
   ep=new.loc[new.vt_symbol.eq(r.vt_symbol)&new.date.eq(r.date)]
   check(r.vt_symbol+'_physical_epoch',len(ep)==1 and ep.iloc[0].contract_epoch_id==r.contract_epoch_id and str(ep.iloc[0].contract_yyyymm)==str(r.contract_yyyymm))
 m=pd.read_csv(D/'mapping.csv');a=pd.read_csv(D/'admitted_20261029_mapping.csv');check('mapping19_exact',len(a)==19 and set(a.continuous_symbol_vt)==set(receipt['products']) and len(receipt['products'])==19 and set(a.date)=={'2026-10-29'} and set(a.main_contract_vt)<=set(app.vt_symbol))
 # Existing completed-week semantics remain frozen; verify current 10/26--29 not a completed week.
 sys.path.insert(0,str(ROOT/'research/lines/futures_weekly_formal_no_half_r/tools'));from weekly_adapter import completed_weeks
 check('terminal_partial_week_excluded',(2026,44) not in completed_weeks(sorted(m.date.unique())))
 check('no44_inputs',not any('stage040' in p or 'weekly-boll-mid-short' in p for p in manifest))
 output={'status':'PASS_BOUNDED_PREFLIGHT','checks':checks,'check_count':len(checks),'failures':0,'old_sqlite_rows':b,'new_sqlite_rows':new_db_count,'new_daily_rows':28,'new_mapping_rows':19,'code_review':'OR strict positive completed-week SMA5/10; count-trimmed history; long/exits/rollover unchanged; unchanged full parent sizing then zero volume; final open guard; disabled A diagnostic only.','limitations':['Source consistency is not exchange truth or PIT proof.','Historical warmup/main/epoch limitations inherited.','Full accounting/fill review pending replay.']}
 (LINE/'stages/stage001_independent_preflight.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in output.items() if k!='checks'},ensure_ascii=False))
if __name__=='__main__':run()
