"""Read-only source/epoch admission for Stage020; no renderer/engine/client import."""
from pathlib import Path
from collections import Counter
import ast,hashlib,json,sqlite3
import numpy as np
import pandas as pd
D=Path(__file__).resolve().parent;ROOT=D.parents[3];LINE=D.parent;OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian');OL=OLD/'research/lines/futures_weekly_short_ma_slope_gate';A=LINE/'artifacts/stage019_2026_ytd';DATA=OL/'outputs/data_stage014_20261030/data_approved';checks=0
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
def ok(v,l):
 global checks;checks+=1
 if not v:raise AssertionError(l)
def near(a,b,l):ok(np.allclose(a,b,rtol=0,atol=1e-7,equal_nan=False),l)
outer=load(A/'delivery_receipt.json');review=load(D/'Stage019_review_acceptance.json');raw=load(D/'Stage019_review_raw_result.json');RUN=Path(raw['source_run']);pins=raw['raw_files_sha256']
ok(outer['accepted']and outer['status']=='PASS_WITH_LIMITATIONS'and review['accepted'],'Stage019_acceptance')
ok(sha(outer['independent_review_path'])==outer['independent_review_sha256'],'Stage019_independent_receipt_binding')
for name,h in outer['delivery_files_sha256'].items():ok(sha(A/name)==h,'source019_delivery_pin:'+name)
for p,h in pins.items():ok(sha(p)==h,'original74_output_pin:'+Path(p).name)
fills=pd.read_csv(RUN/'trades.csv');rounds=pd.read_csv(D/'Stage019_review_closed_rounds.csv');eff=load(RUN/'effective_parameters.json');physical=pd.read_csv(DATA/'physical_epoch_daily.csv');mapping=pd.read_csv(DATA/'mapping.csv');physical['date']=physical.date.str[:10];mapping['date']=mapping.date.str[:10]
ok(len(fills)==36 and len(rounds)==18 and rounds.net_pnl.sum()==22380 and rounds.net_pnl.gt(0).sum()==8 and rounds.net_pnl.lt(0).sum()==10,'all18_36_net_outcomes')
used=[];out=[]
with sqlite3.connect(f'file:{DATA / "daily.sqlite"}?mode=ro',uri=True)as con:
 intervals=pd.read_sql_query('SELECT DISTINCT interval FROM dbbardata',con).iloc[:,0].tolist()
 for r in rounds.itertuples():
  ids=ast.literal_eval(r.trade_ids);part=fills.set_index('trade_id').loc[ids];ok(len(ids)==2 and part.offset.tolist()==['开','平'],'one_entry_one_exit');ok(part.vt_symbol.eq(r.vt_symbol).all(),'round_symbol');used.extend(ids);entry,exit_=part.iloc[0],part.iloc[-1];ok(entry.trading_date==r.opened_on and exit_.trading_date==r.closed_on,'true_trading_dates_not_natural_friday')
  size=float(eff['sizes'][r.vt_symbol]);slip=float(eff['slippages'][r.vt_symbol]);rate=float(eff['rates'][r.vt_symbol]);sgn=1 if entry.direction=='多'else-1;near(entry.volume,exit_.volume,'zero_residual_volume');gross=(exit_.price-entry.price)*entry.volume*size*sgn;cost=((entry.price+exit_.price)*rate+2*slip)*entry.volume*size;near(gross-cost,r.net_pnl,'independent_round_net')
  source=physical.loc[physical.vt_symbol.eq(r.vt_symbol)];epochs=source.loc[source.date.eq(r.opened_on),'contract_epoch_id'].unique();ok(len(epochs)==1,'unique_entry_epoch');epoch=source.loc[source.contract_epoch_id.eq(epochs[0])].sort_values('date');ok(epoch.date.is_unique and r.closed_on in set(epoch.date),'same_epoch_exit')
  sym,ex=r.vt_symbol.split('.');sql=pd.read_sql_query("SELECT datetime, open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<? ORDER BY datetime",con,params=[sym,ex,epoch.date.min(),str((pd.Timestamp(epoch.date.max())+pd.Timedelta(days=1)).date())]);sql['date']=sql.datetime.str[:10];ok(sql.date.is_unique and set(sql.date)==set(epoch.date),'sql_exact_epoch_dates');joined=epoch.merge(sql,on='date',validate='one_to_one',suffixes=('_physical','_sql'))
  for a,b in [('open','open_price'),('high','high_price'),('low','low_price'),('close','close_price'),('volume_physical','volume_sql'),('close_oi','open_interest')]:near(joined[a],joined[b],'epoch_OHLCVOI_parity:'+a)
  ok((epoch[['open','high','low','close']]>0).all().all()and (epoch.volume>0).all()and (epoch.close_oi>=0).all(),'usable_positive_exact_daily');ok((epoch.high>=epoch[['open','close','low']].max(axis=1)).all()and (epoch.low<=epoch[['open','close','high']].min(axis=1)).all(),'daily_OHLC_relationship')
  for f in [entry,exit_]:near(f.price,float(epoch.loc[epoch.date.eq(f.trading_date),'open'].iloc[0]),'source_marker_daily_open')
  prod=''.join(c for c in sym if c.isalpha());cal=mapping.loc[mapping['product'].str.lower().eq(prod.lower())&mapping.exchange.eq(ex),'date'].drop_duplicates();holding=set(cal.loc[cal.between(r.opened_on,r.closed_on)]);ok(holding<=set(epoch.date),'no_holding_date_gap')
  pre=int(epoch.date.lt(r.opened_on).sum());post=int(epoch.date.gt(r.closed_on).sum());out.append(dict(vt_symbol=r.vt_symbol,entry_trade_id=ids[0],exit_trade_id=ids[-1],entry_trading_date=r.opened_on,exit_trading_date=r.closed_on,entry_execution_datetime=entry.datetime,exit_execution_datetime=exit_.datetime,entry_price=float(entry.price),exit_price=float(exit_.price),direction='long'if sgn>0 else'short',volume=float(entry.volume),gross_pnl=float(gross),modeled_cost=float(cost),net_pnl=float(r.net_pnl),physical_epoch_id=str(epochs[0]),real_start=epoch.date.min(),real_end=epoch.date.max(),real_rows=len(epoch),pre_real_rows=pre,post_real_rows=post,pre300_truncated=pre<300,post50_truncated=post<50,holding_missing_dates=sorted(holding-set(epoch.date))))
ok(Counter(used)==Counter(fills.trade_id),'36_fills_used_exactly_once');near(sum(x['modeled_cost']for x in out),2930,'total_cost2930');near(sum(x['gross_pnl']for x in out),25310,'gross25310_not_net');ok(all(x['real_end']<='2026-10-30'for x in out),'completed_cutoff_no_future')
# Only known renderer cache paths and exact target files; never walk home or download.
cache_roots=[ROOT/'examples/portfolio_backtesting/downloaded_futures',OLD/'examples/portfolio_backtesting/downloaded_futures'];cache_candidates=[]
for root in cache_roots:
 for sym in sorted(set(fills.vt_symbol)):
  native,ex=sym.split('.');matches=list(root.glob(f'*/{ex}/{native}_completed_minute_backtest.csv'))if root.is_dir()else[]
  for p in matches:cache_candidates.append(dict(path=str(p),sha256=sha(p),target=sym))
known_bundles=['stage038_c9_15w_big_winner_multiscale_html/winner_bars_15m.csv','stage042_c9_15w_all_trade_multiscale_html/winner_bars_15m.csv','stage045_stage037c_all_trade_multiscale_html/bars_15m_not_used.csv','stage049_stage061_top10_fu_all_trade_multiscale_html/bars_15m_not_used.csv']
for root in [ROOT,OLD]:
 for name in known_bundles:
  p=root/'research/lines/futures_trend_winner_trade_forensics/outputs'/name
  if p.is_file():cache_candidates.append(dict(path=str(p),sha256=sha(p),target='bundle_needs_exact_symbol_epoch_validation'))
allpins={str(A/'delivery_receipt.json'):sha(A/'delivery_receipt.json'),str(D/'Stage019_review_acceptance.json'):sha(D/'Stage019_review_acceptance.json'),str(D/'Stage019_review_raw_result.json'):sha(D/'Stage019_review_raw_result.json'),str(D/'Stage019_review_closed_rounds.csv'):sha(D/'Stage019_review_closed_rounds.csv'),**pins,**{str(DATA/n):sha(DATA/n)for n in ['daily.sqlite','physical_epoch_daily.csv','mapping.csv','metadata.csv','receipt.json']}}
result=dict(schema='Stage020.independent-source-epoch-admission.v1',accepted=True,status='PASS_WITH_LIMITATIONS',failures=[],checks=checks,scope='All18closed/36fills from exact Stage019 reviewed original independent 2026 fresh window',summary={'closed_rounds':18,'fills':36,'wins':8,'losses':10,'flat':0,'gross_pnl':25310.,'slippage':2930.,'commission':0.,'net_pnl':22380.,'terminal_open_positions':0,'date_cutoff':'2026-10-30'},rounds=out,local_minute_search={'roots':[str(x)for x in cache_roots],'sqlite_intervals':intervals,'known_bundle_paths':known_bundles,'candidate_files':cache_candidates,'scope':'Only exact target-contract files under known renderer cache roots and explicit known bundle names; no global/home scan or fetch','qualification':'Any candidate requires symbol/epoch/date OHLC identity and trading-day checks before use. Daily-only page remains valid with absent-minute disclosure.'},input_files_sha256=allpins,required_display_conditions=['All18closed episodes; each36actualfill used exactly once','Net PnL22380 after2930slippage, gross25310 must not be labeled net','Use true trading_date for bar placement, retain natural execution datetime','Exact contract epoch only, prohibit decade alias mixing and undisclosed main-contract proxy','Truncated pre300/post50 and unavoidable MA warmup nulls must be shown','MA5/10/20/40 are chart reference, not regenerated strategy observations','R undefined when no exact frozen definition; no fabricated R','No financial rerun/download/CTP/production/HTTPserver'],financial_replays=0,market_downloads=0,production_accesses=0,production_qualified=False)
p=D/'Stage020_review_preflight.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(out).to_csv(D/'Stage020_review_expected_rounds.csv',index=False);print(json.dumps({'accepted':True,'checks':checks,'receipt_sha256':sha(p),'pre300_truncated':sum(x['pre300_truncated']for x in out),'post50_truncated':sum(x['post50_truncated']for x in out),'minute_candidates':len(cache_candidates),'sqlite_intervals':intervals}))
