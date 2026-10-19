"""Read only one-complete/one-failed status overview; no producer/finance imports."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re,subprocess,tempfile,math,base64
import numpy as np,pandas as pd
ROOT=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian');L=ROOT/'research/lines/futures_trend_full_market_noai_one_lot';P=L/'outputs/run_20261020_risk025_contract_weekly_v1';O=L/'outputs/overview_20261020_risk025_v1_status_v2';F=L/'outputs/run_20261020_risk025_no_weekly_v1';RECAP=L/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v3';REVIEW=L/'stages/20261020_0203_stage101_risk025_weekly_enabled_actual_review.json';NODE=Path('/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert (O/'summary.json').exists() and sha(P/'manifest.json')=='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35'
errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
def js(p):return json.loads(Path(p).read_text())
def near(a,b,tol=1e-7):return abs(float(a)-float(b))<=tol
proof=js(O/'summary.json');source=js(P/'summary.json');manifest=js(P/'manifest.json');page=(O/'index.html').read_text();fig=js(O/'figure.json');export=pd.read_csv(O/'equity_drawdown.csv',float_precision='round_trip');d=pd.read_csv(P/'daily.csv',float_precision='round_trip');review=js(REVIEW);final=js(RECAP/'summary.json')
ck('one_complete_one_failed',proof['status']=='ONE_COMPLETE_ONE_FAILED_NO_PAIRED_RANKING' and proof['failed_full_period_metrics_valid'] is False)
ck('proposal_only',proof['proposal_only'] is True and proof['financial_replays']==0)
ck('own_review_bound',final['independent_review']['metadata']['source_manifest_sha256']==sha(P/'manifest.json') and review['source_manifest_sha256']==sha(P/'manifest.json') and review['status']=='PASS_WITH_LIMITS')
ck('review_json_original_bytes',sha(REVIEW)=='3a0ba1efa4d54e887dc7862ee4be48baab0dfafd3b38952ceb0b2de29f7f950e')
for name,digest in proof['artifact_sha256'].items():ck('artifact_'+name,sha(O/name)==digest)
for path,digest in proof['input_bindings'].items():ck('input_'+path,sha(path)==digest)
ck('off_no_manifest',not (F/'manifest.json').exists());failed=js(O/'failed_review.json');ck('off_fail_not_performance',failed['status']=='FAIL_INCOMPLETE_LIFECYCLE' and failed['performance_valid'] is False and failed['full_period_statistics'] is None)
ck('failed_copy_bound',sha(O/'failed_review.json')==proof['failed_review_sha256'])
ck('failed_source_protocol',sha(F/'protocol.json')==proof['failed_protocol_sha256']);ck('failed_source_snapshot',sha(F/'failure_snapshot.json')==proof['failed_snapshot_sha256'])
ck('same_original_parameters',js(F/'protocol.json')['parameters']==manifest['parameters'])
ck('single_arm_source',proof['enabled']['source_manifest_sha256']==sha(P/'manifest.json') and proof['enabled']['metrics']==source)
ck('source_recap_bound',proof['enabled']['parent_summary_sha256']==sha(RECAP/'summary.json'))
for name,digest in proof['enabled']['parent_artifact_sha256'].items():ck('final_recap_artifact_'+name,sha(RECAP/name)==digest)
capital=1e6;eq=capital+d.net_pnl.cumsum();peak=eq.cummax().clip(lower=capital);dd=(eq/peak-1)*100;trough=int(dd.idxmin());peakidx=int(eq.loc[:trough].idxmax())
ck('daily2862',len(d)==len(export)==proof['points']==2862 and d.date.iloc[0]=='2015-01-05' and d.date.iloc[-1]=='2026-10-16');ck('csv_dates',export.date.tolist()==d.date.tolist())
for n,v in [('equity',eq),('peak',peak),('drawdown_pct',dd)]:ck('csv_'+n,np.allclose(export[n],v,rtol=0,atol=1e-6))
for n,v in [('equity',eq),('balance',eq),('highlevel',peak),('ddpercent',dd),('drawdown',eq-peak)]:ck('native_daily_'+n,np.allclose(d[n],v,rtol=0,atol=1e-6))
def arr(x):
 if isinstance(x,dict) and 'bdata' in x:return np.frombuffer(base64.b64decode(x['bdata']),dtype=np.dtype(x['dtype']))
 return np.array(x)
ck('only_four_source_traces',len(fig['data'])==proof['trace_count']==4)
for i,v in enumerate((eq/10000,peak/10000,dd)):
 trace=fig['data'][i];ck('trace_dates_'+str(i),list(trace['x'])==d.date.tolist());ck('trace_values_'+str(i),np.allclose(arr(trace['y']).astype(float),v,atol=1e-9,rtol=1e-12))
trace=fig['data'][3];ck('max_dd_marker',list(trace['x'])==[d.date.iloc[trough]] and len(arr(trace['y']))==1 and near(arr(trace['y'])[0],dd.iloc[trough]))
layout=fig['layout'];ck('linked_date_axes',layout.get('xaxis',{}).get('matches')=='x2' or layout.get('xaxis2',{}).get('matches')=='x');ck('equity_unit_10k','万元' in layout['yaxis']['title']['text']);ck('dd_unit_pct','%' in layout['yaxis2']['title']['text'])
ck('no_other_curve_names',not any(s in str([x.get('name') for x in fig['data']]) for s in ('关闭','基线','0.5%')))
# Exact embedded chart data/layout must equal figure.json, not a stale screenshot.
m=re.search(r'Plotly\.newPlot\(\s*"(?:account-overview|[a-f0-9-]{36})"\s*,\s*',page);ck('embedded_plot_found',m is not None)
if m:
 decoder=json.JSONDecoder();data,n=decoder.raw_decode(page[m.end():]);remaining=page[m.end()+n:].lstrip();ck('embedded_data',data==fig['data']);remaining=remaining[1:].lstrip();lay,n=decoder.raw_decode(remaining);ck('embedded_layout',lay==fig['layout'])
class Rows(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.cur=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.cur=[]
  if tag=='td':self.cell=[]
 def handle_data(self,data):
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag=='td':self.cur.append(''.join(self.cell));self.cell=None
  if tag=='tr' and self.cur:self.rows.append(self.cur);self.cur=None
parser=Rows();parser.feed(page);keys=['initial_capital','end_balance','total_return','max_ddpercent','sharpe_ratio','payoff_ratio','profit_factor','win_rate_pct','completed_episodes','completed_contracts','total_trade_count','total_commission','total_slippage'];ck('table13',len(parser.rows)==len(keys))
for row,key in zip(parser.rows,keys):
 val=float(re.sub(r'[^0-9.eE+\-]','',row[1].replace(',','')));ck('metric_'+key,abs(val-float(source[key]))<=.000051,[val,source[key]]);ck('off_table_NA_'+key,'未完成' in row[2] and not re.search(r'\d',row[2]))
ck('honest_failure_disclosure',all(x in page for x in ('无法形成完整双版绩效比较','2019-06-27','JR201907','前缀不能','没有关闭版或旧版本替代曲线','尚未') ) if '尚未' in page else all(x in page for x in ('无法形成完整双版绩效比较','2019-06-27','JR201907','前缀不能','没有关闭版或旧版本替代曲线','不认领')))
trades=pd.read_csv(P/'trades.csv',float_precision='round_trip');cashcost=float(trades.commission.sum()+trades.slippage.sum());net=float(d.net_pnl.sum());gross=net+cashcost
ck('html_gross_cost_net',all(f'{v:,.2f}' in page for v in (gross,cashcost,net)))
OLD_O=L/'outputs/overview_20261020_risk025_v1_status'
ck('v3_html_bound',sha(RECAP/'index.html')=='382abac2b94232f0b485da6c4246ff9f3d1a6b36b081a64573da919c4571edee')
for file in ('figure.json','equity_drawdown.csv','equity_drawdown.png'):
 ck('original_status_bytes_'+file,(O/file).read_bytes()==(OLD_O/file).read_bytes())
oldpage=(OLD_O/'index.html').read_text();ck('status_html_only_recap_link_changed',oldpage.replace('recap_20261020_risk025_contract_weekly_v1_reviewed_v2/index.html','recap_20261020_risk025_contract_weekly_v1_reviewed_v3/index.html')==page)
js_count=0
with tempfile.TemporaryDirectory(prefix='stage105-status-js-') as tmp:
 for i,(attrs,body) in enumerate(re.findall(r'<script\b([^>]*)>(.*?)</script>',page,re.S|re.I)):
  if not body.strip() or 'application/json' in attrs:continue
  path=Path(tmp)/f'{i}.js';path.write_text(body);result=subprocess.run([str(NODE),'--check',str(path)],capture_output=True,text=True);ck('js_syntax_'+str(i),result.returncode==0,result.stderr);js_count+=1
import struct,zlib
png=(O/'equity_drawdown.png').read_bytes();ck('png_signature',png[:8]==b'\x89PNG\r\n\x1a\n');width,height=struct.unpack('>II',png[16:24]);ck('png_dimensions',width>=1600 and height>=800);offset=8;chunks=[]
while offset<len(png):
 size=struct.unpack('>I',png[offset:offset+4])[0];kind=png[offset+4:offset+8];data=png[offset+8:offset+8+size];crc=struct.unpack('>I',png[offset+8+size:offset+12+size])[0];ck('png_crc_'+kind.decode('ascii'),zlib.crc32(kind+data)&0xffffffff==crc);chunks.append(kind.decode('ascii'));offset+=12+size
ck('png_complete',offset==len(png) and chunks[-1]=='IEND' and 'IDAT' in chunks)
r=dict(status='PASS_STATIC_DISPLAY_ONLY' if not errors else 'FAIL_STATIC_DISPLAY',source_manifest_sha256=sha(P/'manifest.json'),audit_script_sha256=sha(__file__),overview_summary_sha256=sha(O/'summary.json'),final_recap_summary_sha256=sha(RECAP/'summary.json'),actual_review_json_sha256=sha(REVIEW),source_financial_replays=0,points=len(d),traces=len(fig['data']),ending_equity=float(eq.iloc[-1]),max_dd_pct=float(dd.min()),max_dd_peak_date=d.date.iloc[peakidx],max_dd_trough_date=d.date.iloc[trough],ending_dd_pct=float(dd.iloc[-1]),javascript_blocks=js_count,png_size=[width,height],png_visual_check='separate_view_image_required',browser_check='root_responsibility_not_claimed',failed_full_period_performance='N/A_no_complete_manifest',artifact_sha256={p.name:sha(p) for p in O.iterdir() if p.is_file()},errors=errors,error_count=len(errors))
Path('/private/tmp/stage105_status_v2_independent_audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
