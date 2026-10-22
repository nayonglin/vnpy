"""全市场固定研究数据准备：保留既有日线/映射，只补缺；不调用交易接口。"""
from pathlib import Path
import os,sys,json,time,sqlite3,hashlib,re,shutil,contextlib,io
from datetime import date
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs/stage005_data';SOURCE=Path('/Users/mac/Desktop/fian')
CLEAN=SOURCE/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite'
SNAPSHOT=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/inputs')
os.environ['TZ']='Asia/Shanghai';time.tzset()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def native(product,exchange,yyyymm):
 if product.upper().endswith('_F'):return product[:-2].lower()+yyyymm[-4:]+'F'
 return (product.upper() if exchange in {'CZCE','CFFEX'} else product.lower())+yyyymm[-3 if exchange=='CZCE' else -4:]
def main():
 OUT.mkdir(exist_ok=True)
 universe=pd.read_csv(SNAPSHOT/'product_universe.csv');universe=universe.loc[~universe['product'].isin(['ME','TC'])].copy();assert len(universe)==91
 universe['product']=[p.upper() if e in {'CZCE','CFFEX'} else p.lower().replace('_f','_F') for p,e in zip(universe['product'],universe.exchange)]
 universe['product_vt_symbol']=universe['product']+'.'+universe.exchange
 universe['eligibility_basis']='all_observed_futures_families_2020_onward_no_performance_screen';universe.to_csv(OUT/'universe.csv',index=False)
 credentials=json.loads((SOURCE/'.vntrader/vt_setting.json').read_text())
 from tqsdk import TqAuth
 from tqsdk.calendar import TqContCalendar
 if not (OUT/'mapping_raw.csv').exists():
  auth=TqAuth(credentials['datafeed.username'],credentials['datafeed.password'])
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
   auth.login();symbols=[f'KQ.m@{r.exchange}.{r.product}' for r in universe.itertuples()]
   cal=TqContCalendar(start_dt=date(2019,1,1),end_dt=date(2026,10,22),symbols=None,headers=auth._base_headers)
  cal.df.to_csv(OUT/'mapping_raw.csv',index=False)
 raw=pd.read_csv(OUT/'mapping_raw.csv');pieces=[]
 for r in universe.itertuples():
  key=f'KQ.m@{r.exchange}.{r.product}';available={k.lower():k for k in raw.columns};actual_key=available.get(key.lower());
  if actual_key is None and not r.product.endswith('_F'):raise ValueError('published_continuous_missing:'+key)
  series=raw[actual_key].fillna('') if actual_key else pd.Series('',index=raw.index)
  pieces.append(pd.DataFrame(dict(date=raw.date.astype(str).str[:10],product=r.product,exchange=r.exchange,continuous_symbol_tq=key,continuous_symbol_vt=r.product_vt_symbol,main_contract_tq=series,main_contract_vt=series.map(lambda s:s.split('.',1)[1]+'.'+s.split('.',1)[0] if s else ''))))
 fresh=pd.concat(pieces,ignore_index=True)
 base=pd.read_csv(LINE/'outputs/data/mapping.csv').fillna('');key=['date','continuous_symbol_vt']
 # Original mapping always has priority; fresh only fills keys absent from base, including newly listed families.
 merged=base.merge(fresh,on=key,suffixes=('','_fresh'))
 conflicts=merged.loc[merged.main_contract_vt!=merged.main_contract_vt_fresh]
 conflicts.to_csv(OUT/'mapping_overlap_conflicts.csv',index=False)
 existing=pd.MultiIndex.from_frame(base[key]);fresh=fresh.loc[~pd.MultiIndex.from_frame(fresh[key]).isin(existing)]
 mapping=pd.concat([base,fresh],ignore_index=True).sort_values(key);assert not mapping.duplicated(key).any();mapping.to_csv(OUT/'mapping.csv',index=False)
 # For five newly included families add only observed product-level multiplier/tick; preserve all old metadata.
 old=pd.read_csv(SOURCE/'examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_contract_metadata.csv')
 meta=pd.read_csv(SNAPSHOT/'contract_metadata.csv');meta['product_vt_symbol']=[p.upper() if p.endswith(('.CZCE','.CFFEX')) else p.split('.')[0].lower().replace('_f','_F')+'.'+p.split('.')[1] for p in meta.product_vt_symbol];extra=[]
 for r in universe.itertuples():
  if r.product_vt_symbol in set(old.vt_symbol):continue
  m=meta.loc[meta.product_vt_symbol==r.product_vt_symbol].sort_values('contract_yyyymm').iloc[-1]
  extra.append(dict(vt_symbol=r.product_vt_symbol,symbol_kind='product_cont',volume_multiple=m['size'],price_tick=m.pricetick,margin_ratio=0.15))
 metadata=pd.concat([old,pd.DataFrame(extra)],ignore_index=True);assert set(universe.product_vt_symbol)<=set(metadata.vt_symbol);metadata.to_csv(OUT/'metadata.csv',index=False)
 dbpath=OUT/'daily.sqlite'
 if not dbpath.exists():
  with sqlite3.connect(f'file:{LINE}/outputs/data/daily.sqlite?mode=ro',uri=True) as source,sqlite3.connect(dbpath) as dest:source.backup(dest)
 if not (OUT/'clean_overlay.json').exists():
  products=set(universe.product_vt_symbol);aliases=[];rows=[]
  with sqlite3.connect(f'file:{CLEAN}?mode=ro',uri=True) as clean:
   before=CLEAN.stat();columns=['contract_epoch_id','exchange','product','contract_yyyymm','trade_date','open','high','low','close','volume','close_oi']
   for values in clean.execute("select "+','.join(columns)+" from daily_bars where quality_status='accepted' and trade_date>='2019-01-01'"):
    epoch,exchange,product,yyyymm,day,op,hi,lo,cl,vol,oi=values
    p=product.upper() if exchange in {'CFFEX','CZCE'} else product.lower().replace('_f','_F')
    if p+'.'+exchange not in products:continue
    symbol=native(p,exchange,yyyymm)
    rows.append((symbol,exchange,day+' 00:00:00','d',vol,0.,oi,op,hi,lo,cl));aliases.append((epoch,symbol+'.'+exchange,day))
   assert (before.st_size,before.st_mtime_ns)==(CLEAN.stat().st_size,CLEAN.stat().st_mtime_ns)
  with sqlite3.connect(dbpath) as db:
   count=db.execute('select count(*) from dbbardata').fetchone()[0]
   db.executemany('insert or ignore into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,?,?,?,?,?,?,?,?)',rows);db.commit()
   after=db.execute('select count(*) from dbbardata').fetchone()[0]
  pd.DataFrame(aliases,columns=['epoch','native_vt_symbol','date']).to_csv(OUT/'clean_aliases.csv',index=False)
  dump(OUT/'clean_overlay.json',dict(source=str(CLEAN),source_stat=dict(bytes=before.st_size,mtime_ns=before.st_mtime_ns),manifest=str(CLEAN.parent/'dataset_manifest.json'),inserted=after-count,considered=len(rows),existing_keys_preserved=True,units='accepted_clean_single_sided_contracts',source_manifest_sha=sha(CLEAN.parent/'dataset_manifest.json')))
 with sqlite3.connect(dbpath) as db:daily=pd.read_sql("select symbol||'.'||exchange main_contract_vt,substr(datetime,1,10) date from dbbardata where interval='d'",db)
 target=mapping[(mapping.date>='2020-01-01') & mapping.main_contract_vt.ne('')].merge(daily,on=['date','main_contract_vt'],how='left',indicator=True)
 missing=target.loc[target._merge=='left_only'].drop(columns='_merge');missing.to_csv(OUT/'missing_daily.csv',index=False)
 dump(OUT/'prepare_manifest.json',dict(universe=91,mapping_rows=len(mapping),mapping_overlap_differences=len(conflicts),old_mapping_priority=True,missing_daily_rows=len(missing),missing_contracts=missing.main_contract_vt.nunique(),metadata_scope='original_86_snapshots_plus_5_observed_multiplier_tick; default_margin_0.15_when_not_defined; zero_commission',source_files={str(p):sha(p) for p in [LINE/'outputs/data/mapping.csv',SNAPSHOT/'product_universe.csv',SNAPSHOT/'contract_metadata.csv',OUT/'mapping_raw.csv',OUT/'universe.csv',OUT/'mapping.csv',OUT/'metadata.csv']}))
 print(json.dumps(dict(products=91,mapping_rows=len(mapping),missing_daily_rows=len(missing),missing_contracts=missing.main_contract_vt.nunique(),overlap_differences=len(conflicts))))
if __name__=='__main__':main()
