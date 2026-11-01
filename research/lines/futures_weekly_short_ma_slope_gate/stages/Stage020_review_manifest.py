"""Final002 source/delivery/table binding; no visualization or finance regeneration."""
from pathlib import Path
import hashlib,json,re
import numpy as np
import pandas as pd
D=Path(__file__).resolve().parent;LINE=D.parent;ROOT=LINE.parents[2];OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian');A=LINE/'artifacts/stage020_2026_ytd_recap_attempt002';checks=0
load=lambda p:json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ok(v,l):
 global checks;checks+=1
 if not v:raise AssertionError(l)
def near(a,b,l):ok(np.allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=0,atol=1e-6),l)
g=load(A/'generation_manifest.json');s=load(A/'summary.json');rs=load(A/'records.json');expected=load(D/'Stage020_review_preflight.json');nr=load(D/'Stage020_review_records_result_v3.json');js=load(D/'Stage020_review_javascript_result.json')
for p,h in g['source_files_sha256'].items():ok(sha(p)==h,'source_pin:'+Path(p).name)
for p,h in g['output_files_sha256'].items():ok(Path(p).name==p and sha(A/p)==h,'output_pin:'+p)
for p,h in expected['input_files_sha256'].items():
 if p in g['source_files_sha256']:ok(g['source_files_sha256'][p]==h,'expected_admitted_source:'+Path(p).name)
for p,h in load(D/'Stage019_review_raw_result.json')['raw_files_sha256'].items():ok(g['source_files_sha256'][p]==h,'all74_financial_sources_bound')
for relative in ['research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py','research/lines/futures_weekly_formal_no_half_r/tools/stage031_canonical_recap.py']:
 ok(sha(ROOT/relative)==sha(OLD/relative)==g['source_files_sha256'][str(ROOT/relative)],'old_canonical_library_same_bytes')
ok(s['frozen_backtest_metrics']==load(LINE/'artifacts/stage019_2026_ytd/summary.json'),'all_frozen_account_metrics_preserved')
ok((s['closed_rounds'],s['source_fills'],s['profits'],s['losses'],s['flat'],s['residual_positions'])==(18,36,8,10,0,0),'summary_counts');near([s['net_pnl'],s['gross_pnl'],s['cost']],[22380,25310,2930],'summary_net_after_cost')
ok(s['minute_episodes']==sum(r['meta']['draw_intraday']for r in rs)==8 and s['minute_available_complete_for_all']is False,'honest_partial_minute_scope')
for k in ['financial_replays','market_downloads','production_accesses']:ok(s[k]==g[k]==0,'zero_external_or_finance:'+k)
ok(s['ctp_connected']is False and s['http_service_started']is False,'no_CTP_or_HTTP')
chart=pd.read_csv(A/'chart_manifest.csv');closed=pd.read_csv(A/'closed_rounds.csv');by={r['meta']['open_trade_id']:r for r in rs};ok(len(chart)==len(closed)==18,'tables_all18');ok(set(chart.open_trade_id)==set(closed.entry_trade_id)==set(by),'table_record_identity')
for t in chart.itertuples():
 m=by[t.open_trade_id]['meta'];ok(t.vt_symbol==m['vt_symbol']and t.close_trade_id==m['close_trade_id']and t.entry_date==m['entry_date']and t.exit_date==m['exit_date']and t.physical_epoch_id==m['physical_epoch_id'],'manifest_endpoint_identity');near([t.entry_price,t.exit_price,t.volume,t.realized_pnl],[m['entry_price'],m['exit_price'],m['volume'],m['realized_pnl']],'manifest_net_and_fill');ok(json.loads(t.missing_15m_dates)==m['missing_15m_dates'],'manifest_missing_minutes')
 e=next(x for x in expected['rounds']if x['entry_trade_id']==t.open_trade_id);ok(t.exact_pre_bars==e['pre_real_rows']and t.exact_post_bars==e['post_real_rows'],'manifest_actual_listing_cutoff_counts')
for t in closed.itertuples():
 e=next(x for x in expected['rounds']if x['entry_trade_id']==t.entry_trade_id);near([t.net_pnl,t.gross_pnl,t.cost,t.opened_volume],[e['net_pnl'],e['gross_pnl'],e['modeled_cost'],e['volume']],'closed_export_independent_values');ok(t.entry_execution_datetime==e['entry_execution_datetime']and t.exit_execution_datetime==e['exit_execution_datetime'],'natural_execution_datetime_retained')
ok(nr['html_sha256']==js['html_sha256']==sha(A/'index.html'),'numeric_JS_same_final_HTML');ok(nr['records_sha256']==sha(A/'records.json'),'numeric_same_final_records');ok(nr['summary_sha256']==sha(A/'summary.json'),'numeric_same_final_summary');ok(nr['chart_manifest_sha256']==sha(A/'chart_manifest.csv'),'numeric_same_final_chartmanifest')
html=(A/'index.html').read_text();scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>',html)
for i,source in enumerate(scripts):ok((A/f'embedded_script_{i}.js').read_text()==source,'inline_script_export_identity')
ok(sha(A/'index.html')==sha(LINE/'artifacts/stage020_2026_ytd_recap/index.html'),'001_002_same_page_bytes_only_source_guards_changed')
out=dict(schema='Stage020.independent-final002-manifest-tables.v1',accepted=True,status='PASS_WITH_LIMITATIONS',failures=[],checks=checks,source_pins_verified=len(g['source_files_sha256']),output_pins_verified=len(g['output_files_sha256']),generation_manifest_sha256=sha(A/'generation_manifest.json'),source_files_sha256=g['source_files_sha256'],reviewed_outputs_sha256={str(p):sha(p)for p in sorted(A.iterdir())if p.is_file()},adapter_sha256=sha(LINE/'tools/Stage020_ytd_recap.py'),adapter_tests_sha256=sha(LINE/'tools/test_Stage020_ytd_recap.py'),browser_validation='blocked_by_file_protocol_policy',actual_browser_rendering=False,actual_pointer_zoom=False,source_qualified=False,production_qualified=False)
p=D/'Stage020_review_manifest_result.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'accepted':True,'checks':checks,'source_pins':out['source_pins_verified'],'output_pins':out['output_pins_verified'],'receipt_sha256':sha(p)}))
