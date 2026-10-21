"""Read-only past-feature construction; no labels, target data, fit or source generator."""
import ast,hashlib,json,math,sqlite3,statistics,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import talib
from stage044_asof_features import compute_features,FEATURE_NAMES
LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage044_asof_features'
DB=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite'
PANEL=LINE/'outputs/stage040_daily_source_panel/daily_source_panel.sqlite'
CAL=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/trading_dates.npy'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def readonly(path):
 c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);c.execute('PRAGMA query_only=ON');return c


def old18_binding():
 pointer=json.loads((ROOT/'official_strategy_materials/CURRENT.json').read_text())
 release=ROOT/'official_strategy_materials'/pointer['strategy_version']/'releases'/pointer['release_id']
 logical='examples/portfolio_backtesting/qmt_universe.py';path=release/'payload'/logical
 manifest=json.loads((release/'manifest.json').read_text());expected=next(r['sha256'] for r in manifest['files'] if r['logical_path']==logical)
 if sha(path)!=expected:raise ValueError('frozen_universe_manifest_mismatch')
 node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='PRODUCT_SPECS')
 products=[str(n.args[0].value)+'.'+n.args[1].attr for n in node.value.elts]
 if len(products)!=18 or len(set(products))!=18 or 'fu.SHFE' in products:raise ValueError('old18_source_contract_changed')
 return dict(release_id=pointer['release_id'],logical_path=logical,path=str(path),sha256=expected,ast_lines=[node.lineno,node.end_lineno],products=products,count=18,fixed_fu_excluded=True,extraction='AST literal ProductSpec calls only; no import or generator execution')


def oracle(rows):
 c=[float(r['close']) for r in rows];h=[float(r['high']) for r in rows];l=[float(r['low']) for r in rows]
 v=[float(r['volume']) for r in rows];oi=[float(r['close_oi']) for r in rows]
 log=[math.log(c[i]/c[i-1]) for i in range(1,41)];tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,41)]
 atr=sum(tr[:14])/14
 for t in tr[14:]:atr=(13*atr+t)/14
 change=[c[i]-c[i-1] for i in range(1,41)];gain=sum(max(x,0) for x in change[:6])/6;loss=sum(max(-x,0) for x in change[:6])/6
 for delta in change[6:]:gain=(5*gain+max(delta,0))/6;loss=(5*loss+max(-delta,0))/6
 rsi=100*gain/(gain+loss) if gain+loss else 0
 div=lambda n,d:0. if d==0 else n/d
 mean=lambda a:sum(a)/len(a)
 vals=[div(abs(sum(log[-20:])),math.sqrt(sum(x*x for x in log[-20:]))),div(abs(sum(log)),math.sqrt(sum(x*x for x in log))),
       div(abs(sum(log[-20:])),sum(abs(x) for x in log[-20:])),div(abs(sum(log)),sum(abs(x) for x in log)),
       statistics.pstdev(log[-20:]),div(statistics.pstdev(log[-5:]),statistics.pstdev(log[-20:])),
       div(abs(mean(c[-5:])-mean(c[-20:])),atr),div(abs(mean(c[-20:])-mean(c[-40:])),atr),div(atr,c[-1]),abs(rsi-50)/50,
       div(mean(v[-5:]),mean(v[-20:])),div(oi[-1]-oi[-21],oi[-1]+oi[-21])]
 return dict(zip(FEATURE_NAMES,vals))


def run():
 output=OUT/'monthly_asof_features.csv'
 if output.exists():raise ValueError('immutable_feature_output_exists')
 started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();timer=time.perf_counter();binding=old18_binding();old=set(binding['products'])
 (OUT/'old18_binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
 stamps={str(p):(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino) for p in (DB,PANEL)}
 calendar=pd.to_datetime(np.load(CAL,allow_pickle=False).astype(str),format='%Y%m%d')
 calendar=[str(d.date()) for d in calendar if pd.Timestamp('2010-01-01')<=d<=pd.Timestamp('2026-10-16')]
 index={d:i for i,d in enumerate(calendar)}
 dates=sorted(pd.read_csv(LINE/'outputs/stage008_monthly_raw_matrix/monthly_raw_signal_matrix.csv',usecols=['eval_date']).eval_date.unique())
 selected=['exchange','product','product_vt_symbol','eval_date','monthly_average_F','reference_epoch','input_ready','input_status','source_id','feature_start','open','high','low','close','volume','close_oi','rsi6']
 columns='exchange,product,contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,source_id'
 with readonly(PANEL) as panel,readonly(DB) as source:
  frame=pd.read_sql_query('SELECT '+','.join(selected)+' FROM panel WHERE eval_date IN ('+','.join('?' for d in dates)+') ORDER BY exchange,product,eval_date',panel,params=dates)
  if len(frame)!=98*len(dates):raise ValueError('candidate_calendar_rows_not_preserved')
  frame['domain_role']=np.where(frame.product_vt_symbol.eq('fu.SHFE'),'fixed_fu',np.where(frame.monthly_average_F.eq(1),'monthly_average_F',np.where(frame.product_vt_symbol.isin(old),'old18','expanded')))
  ready=frame.loc[frame.input_ready.eq(1)]
  sample=pd.concat([ready.iloc[np.linspace(0,len(ready)-1,60,dtype=int)],ready.groupby(['exchange','domain_role'],sort=True).head(1),frame.groupby('input_status',sort=True).head(1)]).drop_duplicates(['product_vt_symbol','eval_date'])
  samplekeys=set(zip(sample.product_vt_symbol,sample.eval_date));audit=[];results=[];read_bars=0;checks=0
  for r in frame.to_dict('records'):
   row={k:r[k] for k in ('exchange','product','product_vt_symbol','eval_date','monthly_average_F','reference_epoch','input_ready','input_status','source_id','feature_start','domain_role')}
   row.update({k:None for k in FEATURE_NAMES});row['asof_feature_status']='unknown_input:'+r['input_status']
   if r['input_ready']==1:
    end=index[r['eval_date']];expected=calendar[end-40:end+1]
    records=pd.read_sql_query('SELECT '+columns+' FROM daily_bars WHERE contract_epoch_id=? AND trade_date>=? AND trade_date<=? ORDER BY trade_date',source,params=[r['reference_epoch'],expected[0],r['eval_date']]).to_dict('records');read_bars+=len(records)
    if [x['trade_date'] for x in records]!=expected or any(x['exchange']!=r['exchange'] or x['product']!=r['product'] for x in records):raise ValueError('same_epoch_exact_calendar_identity_mismatch')
    if r['feature_start']!=expected[0]:raise ValueError('panel_feature_start_mismatch')
    if any(float(records[-1][k])!=float(r[k]) for k in ('open','high','low','close','volume','close_oi')) or records[-1]['source_id']!=r['source_id']:raise ValueError('panel_current_source_fields_mismatch')
    if any(not math.isfinite(float(x['volume'])) or float(x['volume'])<=0 or not math.isfinite(float(x['close_oi'])) or float(x['close_oi'])<0 for x in records):raise ValueError('panel_strict_volume_oi_mismatch')
    row.update(compute_features(records));row['asof_feature_status']='known_fixed12_asof_only'
    if (r['product_vt_symbol'],r['eval_date']) in samplekeys:
     representative=source.execute('SELECT contract_epoch_id FROM daily_bars WHERE exchange=? AND product=? AND trade_date=? AND volume>0 ORDER BY volume DESC,close_oi DESC,contract_epoch_id ASC LIMIT 1',(r['exchange'],r['product'],r['eval_date'])).fetchone()
     if representative is None or representative[0]!=r['reference_epoch']:raise ValueError('asof_representative_mismatch')
     literal=oracle(records);diff={k:abs(row[k]-literal[k]) for k in FEATURE_NAMES}
     if any(not math.isclose(row[k],literal[k],rel_tol=1e-9,abs_tol=1e-10) for k in FEATURE_NAMES):raise ValueError('independent_feature_oracle_mismatch:'+str((r['product_vt_symbol'],r['eval_date'],diff)))
     if not math.isclose(talib.RSI(np.array([x['close'] for x in records]),timeperiod=6)[-1],r['rsi6'],abs_tol=1e-10):raise ValueError('panel_RSI_mismatch')
     checks+=16;audit.append(dict(product=r['product_vt_symbol'],eval_date=r['eval_date'],role=r['domain_role'],epoch=r['reference_epoch'],status='ready_source_and_oracle_match',max_feature_abs_diff=max(diff.values())))
   elif (r['product_vt_symbol'],r['eval_date']) in samplekeys:
    checks+=1;audit.append(dict(product=r['product_vt_symbol'],eval_date=r['eval_date'],role=r['domain_role'],epoch=r['reference_epoch'],status='unknown_row_preserved:'+r['input_status']))
   results.append(row)
 result=pd.DataFrame(results);result.to_csv(output,index=False)
 with sqlite3.connect(OUT/'monthly_asof_features.sqlite') as destination:
  result.to_sql('features',destination,index=False,if_exists='fail');destination.execute('CREATE UNIQUE INDEX feature_product_month ON features(product_vt_symbol,eval_date)')
 pd.DataFrame(audit).to_csv(OUT/'fixed_stratified_audit.csv',index=False)
 counts=result.groupby(['domain_role','asof_feature_status'],dropna=False).size().reset_index(name='rows');counts.to_csv(OUT/'status_counts.csv',index=False)
 for p in (DB,PANEL):
  if stamps[str(p)]!=(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino):raise ValueError('input_database_modified')
 dependency=[Path(__file__),LINE/'tools/stage044_asof_features.py',LINE/'tools/test_stage044_asof_features.py',OUT/'contract.md',OUT/'old18_binding.json',output,OUT/'monthly_asof_features.sqlite',OUT/'fixed_stratified_audit.csv']
 summary=dict(started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),elapsed_seconds=time.perf_counter()-timer,
              rows=len(result),months=len(dates),domains=result.product_vt_symbol.nunique(),feature_count=12,known_features=int(result.input_ready.eq(1).sum()),
              unknown_features=int(result.input_ready.ne(1).sum()),past_bars_projected=read_bars,audit_rows=len(audit),audit_checks=checks,audit_failures=0,
              asof_candidate_rows_dropped=0,future_labels_read=0,model_fits=0,financial_backtests=0,orders=0,downloads=0,formal_AC_runs=0,
              formal_source_qualified=False,training_eligible=False,old18=binding['products'],TA_Lib_version=talib.__version__,
              input_db_unchanged=True,input_db_stats=stamps,panel_source_sha256=sha(PANEL),calendar_sha256=sha(CAL),
              input_scope='only asof panel fields plus exact clean epoch <=eval past41; no target source, no future label read',
              bindings={str(p.relative_to(LINE)):sha(p) for p in dependency})
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ('bindings','old18','input_db_stats')},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
