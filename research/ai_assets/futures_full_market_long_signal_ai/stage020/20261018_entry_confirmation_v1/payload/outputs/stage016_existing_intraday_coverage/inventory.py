"""One bounded inventory. No minute payload scan, provider, model, or qualification."""
import csv,hashlib,json,re,sqlite3,time
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
R=Path.cwd(); L=R/'research/lines/futures_full_market_long_signal_ai'; O=L/'outputs/stage016_existing_intraday_coverage'; T=R/'research/lines/futures_trend_triple_screen/outputs'; B=R/'examples/portfolio_backtesting/backtest_outputs'; D=R/'examples/portfolio_backtesting/downloaded_futures'
start=time.monotonic();now=datetime.now().astimezone().isoformat(); sources={}
def small(p):
 b=p.read_bytes();sources[str(p)]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};return b

def rows(p):return list(csv.DictReader(small(p).decode('utf-8-sig').splitlines()))
def js(p):return json.loads(small(p))
def write(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(name,rs):
 with (O/name).open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def prod(symbol):
 native,ex=symbol.rsplit('.',1);return ex+'.'+re.sub(r'\d+$','',native).upper()
allproducts=sorted({x['exchange']+'.'+x['product'] for x in rows(L/'outputs/stage002_full_market_input_inventory/coverage_by_product_year.csv')})
old19={prod(x['product_vt_symbol'])for x in rows(B/'qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv')}
pool_path=B/'qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv';pool=set();pool_exists=pool_path.exists()
if pool_exists: pool={prod(x['product_vt_symbol'])for x in rows(pool_path)if x['eligible']=='1'}
pre=js(T/'stage153_declared_delta_recorder_fix/prepare_retry/actual_preflight.json');bindings=pre['data_bindings']
files=[]; byproduct=defaultdict(list)
for p in sorted(D.rglob('*.csv')):
 m=re.fullmatch(r'([A-Za-z]+\d+)(?:_completed)?_minute_backtest.csv',p.name)
 if not m:continue
 vt=m.group(1)+'.'+p.parent.name; product=prod(vt);st=p.stat();f={'path':str(p),'product_id':product,'vt_symbol':vt,'family':p.relative_to(D).parts[0],'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'declared_sha256':bindings.get(str(p),{}).get('sha256',''),'actual_sha256':'','dates_verified':False,'completion_qualified':False};files.append(f);byproduct[product].append(f)
table('current_workspace_candidate_files.csv',files)
prior=rows(T/'stage004_minute_coverage/local_source_candidates.csv');roots=defaultdict(Counter)
for x in prior: roots[x['workspace_root']]['declared_paths']+=1; roots[x['workspace_root']]['currently_existing_paths']+=int(Path(x['path']).is_file())
qualified=defaultdict(set); summary=[]
for rel in ['stage002_local_minute_overlay/attempt2','stage011_needed_local_completed','stage015_daily_recovered_minute_delta','stage020_reviewed_provider_overlay']:
 p=T/rel; ss=rows(p/'session_manifest.csv'); accepted=[x for x in ss if x['status']=='accepted']; z=js(p/'summary.json'); ys=defaultdict(lambda:{'sessions':set(),'full':set()})
 for x in accepted:
  day=x.get('trading_date')or x.get('execution_trade_date'); k=(x['vt_symbol'],day); pr=prod(k[0]);full=x.get('requirement_kind','full_session')=='full_session';ys[(pr,day[:4])]['sessions'].add(k)
  if full:ys[(pr,day[:4])]['full'].add(k);qualified[pr].add(k)
 for (pr,yr),v in sorted(ys.items()):summary.append({'layer':rel,'product_id':pr,'year':yr,'accepted_session_keys':len(v['sessions']),'accepted_full_session_keys':len(v['full']),'first_day':min(k[1]for k in v['sessions']),'last_day':max(k[1]for k in v['sessions']),'scope':'inherited_layer_receipts_not_global_requalification'})
table('inherited_accepted_session_product_year.csv',summary)
# Only database metadata plus two index-backed two-row probes.
db=R/'.vntrader/database.db'
with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)as c:
 c.execute('pragma query_only=ON');c.row_factory=sqlite3.Row
 overview=[dict(x)for x in c.execute("select symbol,exchange,interval,count,start,end from dbbaroverview where interval='1m'")]
 schema=[dict(x)for x in c.execute('pragma table_info(dbbardata)')];indexes=[dict(x)for x in c.execute("select name,sql from sqlite_master where type='index' and tbl_name='dbbardata'")]
 probes=[]
 for sym,ex,day in [('CF005','CZCE','2020-03-06'),('fu2509','SHFE','2025-07-23')]:
  q="select symbol,exchange,interval,datetime,open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where symbol=? and exchange=? and interval='1m' and datetime>=? and datetime<? order by datetime limit 2";data=[dict(x)for x in c.execute(q,(sym,ex,day,day+'Z'))];probes.append({'query':q,'parameters':[sym,ex,day,day+'Z'],'rows':data})
write('database_metadata_and_probes.json',{'path':str(db),'bytes':db.stat().st_size,'mtime_ns':db.stat().st_mtime_ns,'inherited_binding':bindings.get(str(db)),'overview':overview,'schema':schema,'indexes':indexes,'bounded_probes':probes,'tick_overview_not_used':True})
# Six deterministic file endpoint samples: at most 4096 bytes from each end.
chosen=[]
for ex in sorted({f['product_id'].split('.')[0]for f in files}):chosen.append(next(f for f in files if f['product_id'].startswith(ex+'.')))
non19=[f for f in files if f['product_id']not in old19]
if non19: chosen.append(non19[0])
base=next(Path(k)for k in bindings if 'stage861_stage860_full_visual_atlas_full_minute_bars' in k)
paths=list(dict.fromkeys([Path(x['path'])for x in chosen]+[base]))[:6];samples=[]
for p in paths:
 with p.open('rb')as f:
  head=f.read(4096);f.seek(max(0,p.stat().st_size-4096));tail=f.read(4096)
 h=head.decode('utf-8-sig').splitlines();tt=tail.decode('utf-8').splitlines();samples.append({'path':str(p),'bytes':p.stat().st_size,'header':h[0],'first_data_row':h[1]if len(h)>1 else '', 'last_data_row':tt[-1]if tt else '', 'scope':'endpoints_only_not_continuous_date_coverage','inherited_binding':bindings.get(str(p))})
write('bounded_csv_endpoints.json',samples)
coverage=[]
for p in allproducts:
 ff=byproduct.get(p,[]);qq=qualified.get(p,set());ov=[x for x in overview if prod(x['symbol']+'.'+x['exchange'])==p];coverage.append({'product_id':p,'old19':p in old19,'legacy_eligible57':p in pool if pool_exists else 'unknown_missing_original_57_manifest','candidate_files':len(ff),'candidate_distinct_short_symbols':len({f['vt_symbol']for f in ff}),'minute_db_overview_rows':sum(x['count']for x in ov),'inherited_union_full_session_keys':len(qq),'first_inherited_full_day':min((x[1]for x in qq),default=''),'last_inherited_full_day':max((x[1]for x in qq),default=''),'full_market_day_coverage_verified':False})
table('product_scope_inventory.csv',coverage)
assets=[]
for k,v in bindings.items():
 if Path(k).name=='overlay.csv'or k==str(base):
  p=Path(k);s=p.stat()if p.exists()else None;assets.append({'path':k,'exists':bool(s),'actual_bytes':s.st_size if s else None,'actual_mtime_ns':s.st_mtime_ns if s else None,'inherited_sha256':v['sha256'],'inherited_bytes':v['bytes'],'actual_rehash':False})
late=[]
for rel in ['stage061_accepted_wait_delta/ccc4a13cbc8e4691af41a16916c659f2','stage135_accepted_off_wait_delta/81ffc8f704ce4c5eb701e97e0397b12a']:
 p=T/rel;d=js(p/'manifest.json');late.append({'path':str(p),'accepted_deliveries':d['accepted_deliveries'],'accepted_keys':d['accepted_keys'],'qualified_full_keys':d['qualified_full_keys'],'qualified_anchor_keys':d['qualified_anchor_keys'],'scope':d['qualification_scope'],'note':'key rights are not counts of complete sessions; acceptance inherited from later root receipt'})
result={'schema':'stage016_existing_intraday_inventory_v1','started_at':now,'elapsed_seconds':time.monotonic()-start,'all_market_products':len(allproducts),'old19_products':len(old19),'legacy_pool_products':len(pool)if pool_exists else None,'legacy_pool_expected_path':str(pool_path),'legacy_pool_path_exists':pool_exists,'current_workspace_candidate_files':len(files),'candidate_products':sorted(byproduct),'candidate_products_count':len(byproduct),'candidate_exchanges':sorted({p.split('.')[0]for p in byproduct}),'candidate_non19_products':sorted(set(byproduct)-old19),'legacy57_without_candidate_paths':sorted(pool-set(byproduct))if pool_exists else None,'all98_without_candidate_paths':sorted(set(allproducts)-set(byproduct)),'filename_symbols_are_not_contract_epochs':True,'source_roots_observed':{k:dict(v)for k,v in roots.items()},'db_overview_contracts':len(overview),'db_overview_minutes':sum(x['count']for x in overview),'db_overview_products':len({prod(x['symbol']+'.'+x['exchange'])for x in overview}),'db_overview_first':min(x['start']for x in overview),'db_overview_last':max(x['end']for x in overview),'bounded_payload_files':len(samples),'bounded_sql_payload_rows':sum(len(x['rows'])for x in probes),'bound_minute_assets':assets,'later_exact_key_deltas':late,'sources':sources,'financial_attempts':0,'model_fits':0,'downloads':0,'provider_connections':0,'large_payload_hashes':0,'qualification_granted':False,'source_or_strategy_writes':0}

other=[x for x in D.rglob('*minute*.csv')if not re.fullmatch(r'([A-Za-z]+\d+)(?:_completed)?_minute_backtest.csv',x.name)]
result['other_minute_named_paths']=[{'path':str(x),'bytes':x.stat().st_size,'mtime_ns':x.stat().st_mtime_ns,'payload_read':False}for x in other]
result['other_minute_named_path_count']=len(other)
result['other_minute_named_paths_scope']='Date-specific bundles, excluded from standard-symbol coverage and not newly qualified.'
write('input_inventory.json',result);print(json.dumps({k:v for k,v in result.items()if k in ['elapsed_seconds','all_market_products','old19_products','legacy_pool_products','current_workspace_candidate_files','candidate_products_count','candidate_exchanges','candidate_non19_products','db_overview_contracts','db_overview_minutes','bounded_payload_files','bounded_sql_payload_rows']},ensure_ascii=False))
write('actual_terminal.json',{'status':'completed','exit_code':0,'started_at':now,'finished_at':datetime.now().astimezone().isoformat(),'elapsed_seconds':time.monotonic()-start,'interpreter_requested':'.py311/bin/python','command':'.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage016_existing_intraday_coverage/inventory.py','financial_attempts':0,'model_fits':0,'downloads':0,'provider_connections':0})
