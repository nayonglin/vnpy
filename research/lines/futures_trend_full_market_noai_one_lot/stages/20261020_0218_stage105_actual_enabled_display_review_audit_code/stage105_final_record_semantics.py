from pathlib import Path
import json,hashlib,math
import pandas as pd
L=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot');P=L/'outputs/run_20261020_risk025_contract_weekly_v1';F=L/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v2';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(P/'manifest.json')=='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35' and sha(F/'index.html')=='b0eca000d4af4b1af0f7868127da7c46bd267cec2b4e6a9136088c6990b74a48'
records=json.loads((F/'records.json').read_text());summary=json.loads((F/'summary.json').read_text());closed=pd.read_csv(P/'closed_episodes.csv',float_precision='round_trip').set_index('open_trade_id');fills=pd.read_csv(P/'trades.csv',float_precision='round_trip').set_index('trade_id');manifest=pd.read_csv(F/'chart_manifest.csv',float_precision='round_trip').set_index('open_trade_id');errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
def near(a,b):return math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-11)
counts={'profit':0,'loss':0,'flat':0};diffweighted=hiddenmarkers=partialentries=0
for row in records:
 m=row['meta'];key=m['open_trade_id'];e=closed.loc[key];entry=fills.loc[key];ids=json.loads(e.close_trade_ids);final=fills.loc[ids[-1]]
 classification='profit' if e.gross_pnl>0 else 'loss' if e.gross_pnl<0 else 'flat';counts[classification]+=1;ck('gross_filter_type',m['result_type']==classification,key)
 partialentries+=len(ids)>1;diffweighted+=not near(m['weighted_exit_price'],final.price)
 ck('last_actual_exit',m['exit_date']==final.date and near(m['exit_price'],final.price),key)
 expected=final.price if m['exit_source']==m['vt_symbol'] else None
 ck('conditional_final_marker',(m['exit_marker_price'] is None) if expected is None else near(m['exit_marker_price'],expected),key);hiddenmarkers+=expected is None
 ck('raw_weighted_price_move',near(m['price_change_pct'],(e.exit_price/entry.price-1)*100),key)
 ck('R_uses_actual_total_initial_risk',near(m['initial_risk_total'],entry.stage068_entry_risk) and near(m['risk_amount'],entry.stage068_entry_risk) and near(m['r_multiple'],e.gross_pnl/entry.stage068_entry_risk),key)
 ck('whole_entry_quantity',near(m['volume'],entry.volume),key)
 c=manifest.loc[key]
 for field in ['volume','risk_amount','initial_risk_total','cost','net_pnl','r_multiple','exit_marker_price']:
  if field=='exit_marker_price' and expected is None:ck('manifest_hidden_marker',pd.isna(c[field]),key)
  else:ck('manifest_'+field,near(c[field],m[field]),key)
for group,n in counts.items():ck('summary_gross_count_'+group,summary['chart_'+group+'_episodes']==n)
ck('net_win_count',int((closed.net_pnl>0).sum())==418)
review=summary['independent_review'];ck('actual_review_MD_bytes',sha(review['path'])==review['sha256']);ck('actual_review_JSON_bytes',sha(review['metadata_path'])==review['metadata_sha256']=='3a0ba1efa4d54e887dc7862ee4be48baab0dfafd3b38952ceb0b2de29f7f950e')
page=(F/'index.html').read_text();ck('final_labels_whole_qty',"['交易手数',m.volume]" in page and "['毛/净盈亏'" in page and "['平仓lot',m.lot_count]" not in page);ck('partial_final_exit_disclosure','最后一笔实际成交价' in page and '加权平均退出价' in page)
r=dict(source_manifest_sha256=sha(P/'manifest.json'),final_html_sha256=sha(F/'index.html'),audit_script_sha256=sha(__file__),records=len(records),gross_filter_counts=counts,net_winners=418,net_losers=893,partial_complete_entries=partialentries,weighted_exit_differs_from_last_fill=diffweighted,hidden_non_same_source_exit_markers=hiddenmarkers,financial_replays=0,errors=errors,error_count=len(errors));Path('/private/tmp/stage105_final_record_semantics.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
