"""Read-only Stage011 admission review; no financial engine or market access."""
from pathlib import Path
import hashlib, importlib, json, os, sqlite3, sys, time
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
STAGES=LINE/'stages'
EXPECTED={
 'stage009_freeze.json':'d53d36fc21b8308b220cd69484697ae3d1b29074abd23311f28f58feec4e406a',
 'stage009_delivery_manifest.json':'b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424',
 'stage010_delivery_manifest.json':'8660d87b44df4cc306b99e42df3f2c197a79760a5cc7950aae9b232397967371'}
checks=0
def ok(v,label):
 global checks
 checks+=1
 if not v: raise AssertionError(label)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
 return h.hexdigest()
def fingerprint(path):
 s=Path(path).stat()
 return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def load(path): return json.loads(Path(path).read_text())
def main():
 out=STAGES/'stage011_independent_data_review.json'
 cacheout=STAGES/'stage011_independent_hash_cache.json'
 if out.exists() or cacheout.exists(): raise ValueError('immutable_admission_review_exists')
 for name,want in EXPECTED.items(): ok(sha(STAGES/name)==want,'frozen_baseline:'+name)
 frozen=load(STAGES/'stage009_freeze.json');regpath=LINE/'outputs/stage009_multistart/registry.json';reg=load(regpath)
 expected=[f'{y}-{m:02d}-01' for y in range(2015,2027) for m in [1,6] if (y,m)<=(2026,1)]
 ok(reg['starts']==frozen['starts']==expected and reg['arms']==['A','C'] and reg['cutoff']=='2026-10-29','exact23starts_twoarms_cutoff')
 ok(len(reg['jobs'])==46 and reg['financial_replays_started']==46 and reg['financial_engine_batch_complete'] is True,'old46_completed_reserve_replays')
 ok(reg['engine_initial_capital']==reg['reserve_initial_capital']==150000 and reg['total_initial_capital']==300000,'old_reserve_not_idle_control')
 oldmanifest=load(STAGES/'stage009_delivery_manifest.json')
 ok(oldmanifest['accepted'] and oldmanifest['promotion_decision']=='NO_PROMOTION' and oldmanifest['files_sha256'][str(regpath)]==sha(regpath),'accepted_old_registry_binding')
 data=Path(frozen['data_directory']);receipt=load(data/'receipt.json')
 paths={'daily_sqlite_sha256':'daily.sqlite','mapping_sha256':'mapping.csv','physical_epoch_daily_sha256':'physical_epoch_daily.csv','receipt_sha256':'receipt.json'}
 graph={str(data/v):frozen['data_identity'][k] for k,v in paths.items()}
 graph.update({str(STAGES/k):v for k,v in EXPECTED.items()});graph[str(regpath)]=sha(regpath)
 for name,want in frozen['source_files_sha256'].items(): graph[str(Path(name) if Path(name).is_absolute() else ROOT/name)]=want
 # The already accepted input graph is identical across old runs apart from
 # source identities. Hash each distinct path once, retaining its stat identity.
 for job in reg['jobs'].values():
  p=Path(job['path']);pre=load(p/'preflight.json')
  ok(pre['reserve_topup_enabled'] is True and pre['data_identity']==frozen['data_identity'],'old_job_same_reserve_data')
  for f in ['daily.csv','reserve_daily.csv','trades.csv','entry_risk.csv','actual_strategy_settings.json','effective_parameters.json','input_manifest.json','preflight.json','terminal.json','reserve_total_metrics.json']:
   q=str(p/f);ok(q in job['files_sha256'],'old_selected_output_manifest:'+f);graph[q]=job['files_sha256'][q]
  for q,h in load(p/'input_manifest.json').items():
   ok(q not in graph or graph[q]==h,'input_graph_consensus');graph[q]=h
 for number in ['001','002','003','004','005','006','007']:
  names=[f'stage{number}_delivery_manifest.json']
  if number=='004': names+=['stage004_delivery_manifest_v2.json']
  for name in names:
   q=STAGES/name;graph[str(q)]=sha(q)
   for p,h in load(q)['files_sha256'].items():
    ok(p not in graph or graph[p]==h,'old_delivery_consensus');graph[p]=h
 cache={};total=0;started=time.monotonic()
 for path,want in sorted(graph.items()):
  q=Path(path);before=fingerprint(q);actual=sha(q);ok(actual==want,'source_graph_hash:'+path);ok(fingerprint(q)==before,'source_graph_stable:'+path)
  cache[path]={'sha256':actual,'stat':before};total+=q.stat().st_size
 mapping=pd.read_csv(data/'mapping.csv',dtype=str);source=pd.read_csv(data/'physical_epoch_daily.csv',dtype={'date':str,'vt_symbol':str,'contract_epoch_id':str})
 ok(not mapping.duplicated(['date','product','exchange']).any(),'mapping_unique')
 last=mapping.loc[mapping.date.eq('2026-10-29')];ok(len(last)==19 and set(last.continuous_symbol_vt)==set(receipt['products']),'original19_mapping_complete_cutoff')
 ok(mapping.date.max()=='2026-10-29' and source.date.max()=='2026-10-29','exclude_forming1030')
 index=source.set_index(['date','vt_symbol']);latest=[]
 for r in last.itertuples():
  ok((r.date,r.main_contract_vt) in index.index,'cutoff_mapping_has_real_daily');s=index.loc[(r.date,r.main_contract_vt)]
  ok(float(s.volume)>0 and all(pd.notna(s[x]) for x in ['open','high','low','close','close_oi']),'cutoff_positive_real_bar');latest.append(r.main_contract_vt)
 db=sqlite3.connect('file:'+str(data/'daily.sqlite')+'?mode=ro',uri=True)
 ok(db.execute('pragma quick_check').fetchone()[0]=='ok','sqlite_integrity')
 count=db.execute('select count(*) from dbbardata').fetchone()[0];cols=[x[1] for x in db.execute('pragma table_info(dbbardata)')];db.close()
 ok(receipt['data_ready'] is True and receipt['data_ready_for_bounded_replay'] is True and receipt['main_missing_2015_onward']==0 and receipt['historical_main_reconstruction_complete'] is False,'honest_bounded_data_readiness')
 os.environ['MPLCONFIGDIR']='/private/tmp/stage011-independent-mpl'
 vendor=Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
 sys.path[:0]=[str(ROOT),str(vendor),str(ROOT/'examples/portfolio_backtesting')]
 modules={}
 for name in ['vnpy.trader.object','vnpy_sqlite.sqlite_database','vnpy_portfoliostrategy','pandas','numpy','matplotlib','talib']:
  m=importlib.import_module(name);modules[name]={'file':getattr(m,'__file__',None),'version':getattr(m,'__version__',None)}
 payload=dict(schema='stage011_independent_hash_cache_v1',scope='Each deduplicated old bound input, selected old financial output and legacy delivery hashed once; cache hits require identical device/inode/size/mtime/ctime. New run outputs independently hashed and financially reconstructed.',files=cache,files_count=len(cache),bytes_verified=total)
 cacheout.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 report=dict(schema='stage011_independent_data_review_v1',status='PASS_DATA_BASELINE_RUNTIME_WITH_LIMITATIONS',P0=0,P1=0,P2=0,checks=checks,baseline_sha256=EXPECTED,baseline_registry_sha256=sha(regpath),data_identity=frozen['data_identity'],starts=expected,cutoff='2026-10-29',old_reserve_runs=46,cutoff_mapping_products=19,cutoff_daily_symbols=latest,sqlite_rows=count,sqlite_columns=cols,runtime={'python':sys.version,'executable':sys.executable,'modules':modules},hash_cache=str(cacheout),hash_cache_sha256=sha(cacheout),deduplicated_files=len(cache),deduplicated_bytes=total,hash_seconds=time.monotonic()-started,financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',limitations=load(STAGES/'stage009_data_preflight.json')['limitations'],source_code_admission='Pending Stage011 runner/contract freeze; this receipt alone does not permit financial execution',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['runtime','limitations','sqlite_columns','cutoff_daily_symbols']},ensure_ascii=False))
if __name__=='__main__': main()
