"""补全市场实际映射日线及月均价家族，原键不替换；真实缺失保留审计。"""
from stage005_prepare_data import *

def main():
 from tqsdk import TqApi,TqAuth,TqSim
 creds=json.loads((SOURCE/'.vntrader/vt_setting.json').read_text());out=OUT/'daily_download';out.mkdir(exist_ok=True)
 missing=pd.read_csv(OUT/'missing_daily.csv');symbols=set(missing.main_contract_vt)
 with sqlite3.connect(f'file:{CLEAN}?mode=ro',uri=True) as d:
  for product,exchange,yyyymm in d.execute("select distinct product,exchange,contract_yyyymm from daily_bars where product in ('L_F','PP_F','V_F')"):
   symbols.add(native(product,exchange,yyyymm)+'.'+exchange)
 api=None;stats=[]
 try:
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):api=TqApi(TqSim(),auth=TqAuth(creds['datafeed.username'],creds['datafeed.password']),disable_print=True)
  for symbol in sorted(symbols):
   target=out/(symbol+'.parquet');receipt=out/(symbol+'.json')
   if receipt.exists():stats.append(json.loads(receipt.read_text()));continue
   try:
    code,exchange=symbol.split('.')
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
     serial=api.get_kline_serial(exchange+'.'+code,86400,data_length=10000)
     deadline=time.time()+(6 if exchange=='CZCE' and re.match(r'(JR|LR|PM|RI|RS|WH|ZC)',code) else 45)
     while len(serial)==0 or serial.iloc[-1]['datetime']==0:
      if time.time()>deadline:raise TimeoutError('daily_serial_timeout')
      api.wait_update(deadline=deadline)
    raw=serial.copy();raw.to_parquet(target,index=False)
    raw=raw.loc[raw.datetime.gt(0)].copy();raw['date']=pd.to_datetime(raw.datetime,unit='ns',utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d')
    raw=raw.loc[(raw.date>='2019-01-01') & (raw.date<='2026-10-22')];accepted=raw.loc[raw[['open','high','low','close']].gt(0).all(axis=1)&raw.low.le(raw[['open','close']].min(axis=1))&raw.high.ge(raw[['open','close']].max(axis=1))&raw[['volume','close_oi']].ge(0).all(axis=1)]
    rows=[(code,exchange,r.date+' 00:00:00','d',r.volume,0.,r.close_oi,r.open,r.high,r.low,r.close) for r in accepted.itertuples()]
    with sqlite3.connect(OUT/'daily.sqlite') as db:
     before=db.execute('select count(*) from dbbardata').fetchone()[0]
     db.executemany('insert or ignore into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,?,?,?,?,?,?,?,?)',rows);db.commit();inserted=db.execute('select count(*) from dbbardata').fetchone()[0]-before
    row=dict(symbol=symbol,status='complete',raw_path=str(target),raw_sha256=sha(target),rows=len(raw),accepted_rows=len(accepted),inserted=inserted,invalid_rows=len(raw)-len(accepted),first=str(accepted.date.min()),last=str(accepted.date.max()),downloaded_at=pd.Timestamp.now(tz='Asia/Shanghai').isoformat(),kind='tqsdk_completed_daily_snapshot',only_missing_keys=True,order_api_calls=0)
   except Exception as e:
    row=dict(symbol=symbol,status='unavailable',error_type=type(e).__name__,order_api_calls=0);dump(receipt,row);stats.append(row);continue
   dump(receipt,row);stats.append(row)
   if len(stats)%10==0:print(json.dumps(dict(completed=len(stats),total=len(symbols),inserted=sum(x.get('inserted',0) for x in stats))),flush=True)
 finally:
  if api is not None:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):api.close()
  dump(OUT/'daily_download_progress.json',stats)
 # Supplier publishes no Tq main series for monthly-average F. Use fixed previous-observed-session OI maximum; no future data/tuning.
 mapping=pd.read_csv(OUT/'mapping.csv').fillna('');cal=sorted(mapping.date.unique());family_rows=[]
 mapping.loc[mapping.continuous_symbol_vt.isin(['l_F.DCE','pp_F.DCE','v_F.DCE']),['main_contract_vt','main_contract_tq']]=''
 with sqlite3.connect(f'file:{CLEAN}?mode=ro',uri=True) as source:
  expiries={native(p,e,y):d for p,e,y,d in source.execute("select product,exchange,contract_yyyymm,delisted_date from contracts where product in ('L_F','PP_F','V_F')")}
 with sqlite3.connect(OUT/'daily.sqlite') as db:
  for family in ['l','pp','v']:
   rows=pd.read_sql("select symbol,substr(datetime,1,10) date,volume,open_interest from dbbardata where exchange='DCE' and symbol glob ? and interval='d'",db,params=(family+'[0-9][0-9][0-9][0-9]F',))
   previous=None
   for day in cal:
    candidates=rows.loc[(rows.date==previous)&rows.volume.gt(0)&rows.open_interest.gt(0)] if previous else rows.iloc[:0]
    # Use contractual expiry snapshot, never future last-observed bar availability.
    candidates=candidates.loc[candidates.symbol.map(expiries).ge(day)]
    if len(candidates):
     chosen=candidates.sort_values(['open_interest','volume','symbol'],ascending=[False,False,True]).iloc[0];mask=(mapping.date==day)&mapping.continuous_symbol_vt.eq(family+'_F.DCE');mapping.loc[mask,'main_contract_vt']=chosen.symbol+'.DCE';mapping.loc[mask,'main_contract_tq']='DCE.'+chosen.symbol;family_rows.append(dict(date=day,family=family+'_F.DCE',selected=chosen.symbol+'.DCE',basis_date=previous,open_interest=chosen.open_interest))
    previous=day
 mapping.to_csv(OUT/'mapping.csv',index=False);pd.DataFrame(family_rows).to_csv(OUT/'F_mapping_evidence.csv',index=False)
 with sqlite3.connect(OUT/'daily.sqlite') as db:
  db.execute('delete from dbbaroverview');db.execute("insert into dbbaroverview(symbol,exchange,interval,count,start,end) select symbol,exchange,interval,count(*),min(datetime),max(datetime) from dbbardata group by symbol,exchange,interval");db.commit()
  daily=pd.read_sql("select symbol||'.'||exchange main_contract_vt,substr(datetime,1,10) date from dbbardata where interval='d'",db)
 target=mapping[(mapping.date>='2020-01-01') & mapping.main_contract_vt.ne('')].merge(daily,on=['date','main_contract_vt'],how='left',indicator=True);remaining=target.loc[target._merge=='left_only'];remaining.to_csv(OUT/'remaining_daily_gaps.csv',index=False)
 dump(OUT/'completed_manifest.json',dict(products=91,date_end='2026-10-22',mapping_policy='original Tq keys retained; published Tq fills missing keys; 3 unavailable F families previous-session observed OI max',remaining_mapping_daily_rows=len(remaining),remaining_mapping_daily_contracts=remaining.main_contract_vt.nunique(),downloads=len(stats),added_rows=sum(x.get('inserted',0) for x in stats),files={str(p):sha(p) for p in [OUT/'daily.sqlite',OUT/'mapping.csv',OUT/'metadata.csv',OUT/'universe.csv',OUT/'F_mapping_evidence.csv',OUT/'clean_overlay.json',OUT/'daily_download_progress.json']}))
 print(json.dumps(dict(status='data_complete_pending_review',downloads=len(stats),remaining_mapping_daily_rows=len(remaining),remaining_contracts=remaining.main_contract_vt.nunique())),flush=True)
if __name__=='__main__':main()
