from pathlib import Path
import json,hashlib,re,subprocess,tempfile
L=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot');OLD=L/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v2';NEW=L/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v3';SOURCE=L/'outputs/run_20261020_risk025_contract_weekly_v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
assert sha(OLD/'index.html')=='b0eca000d4af4b1af0f7868127da7c46bd267cec2b4e6a9136088c6990b74a48' and sha(NEW/'index.html')=='382abac2b94232f0b485da6c4246ff9f3d1a6b36b081a64573da919c4571edee'
a=(OLD/'index.html').read_text();b=(NEW/'index.html').read_text();restored=b
for old,new in [('净利润绝对值从大到小','毛盈亏绝对值从大到小'),('净利润绝对值从小到大','毛盈亏绝对值从小到大')]:
 ck('one_new_label_'+new,b.count(new)==1 and b.count(old)==0 and a.count(old)==1);restored=restored.replace(new,old)
NOTE='排序与筛选口径：本页盈亏金额排序、盈利/亏损筛选及R的分子均使用毛价差盈亏；净盈亏在卡片单列，包含分摊手续费和滑点。账户总览中的胜率和盈亏比按完整原始开仓的净盈亏统计；部分平仓或每手不另计胜负样本。'
tag='<div id="stage106-gross-sort-note" class="note">'+NOTE+'</div>';ck('one_declared_plain_note',restored.count(tag)==1);restored=restored.replace(tag,'',1);ck('independent_inverse_exact_bytes',restored.encode()==(OLD/'index.html').read_bytes())
old_summary=json.loads((OLD/'summary.json').read_text());new_summary=json.loads((NEW/'summary.json').read_text());nonhtml={n:d for n,d in old_summary['artifact_sha256'].items() if n!='index.html'}
for n,d in nonhtml.items():ck('non_html_original_'+n,sha(OLD/n)==sha(NEW/n)==d)
ck('records_bytes',sha(NEW/'records.json')=='99a5aaac295e92fc226cd466e724fbd581b6bf13884c71a4d8a3be16a94d992b')
for n,d in new_summary['artifact_sha256'].items():ck('new_artifact_'+n,sha(NEW/n)==d)
ck('metrics_and_source_unchanged',new_summary['source_manifest_sha256']==old_summary['source_manifest_sha256']==sha(SOURCE/'manifest.json') and new_summary['backtest_metrics']==old_summary['backtest_metrics'])
old_scripts=re.findall(r'<script\b([^>]*)>(.*?)</script>',a,re.S|re.I);new_scripts=re.findall(r'<script\b([^>]*)>(.*?)</script>',b,re.S|re.I);ck('all_js_text_byte_identical',old_scripts==new_scripts)
node='/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node';count=0
with tempfile.TemporaryDirectory(prefix='stage105-final-v3-js-') as tmp:
 for i,(attrs,body) in enumerate(new_scripts):
  if not body.strip() or 'application/json' in attrs:continue
  p=Path(tmp)/f'{i}.js';p.write_text(body);r=subprocess.run([node,'--check',str(p)],capture_output=True,text=True);ck('v3_js_syntax_'+str(i),r.returncode==0,r.stderr);count+=1
r=dict(source_manifest_sha256=sha(SOURCE/'manifest.json'),audit_script_sha256=sha(__file__),parent_html_sha256=sha(OLD/'index.html'),final_html_sha256=sha(NEW/'index.html'),parent_summary_sha256=sha(OLD/'summary.json'),final_summary_sha256=sha(NEW/'summary.json'),inverse_html_sha256=hashlib.sha256(restored.encode()).hexdigest(),non_html_original_artifacts=len(nonhtml),all_javascript_identical=old_scripts==new_scripts,javascript_blocks=count,final_records_sha256=sha(NEW/'records.json'),financial_replays=0,artifact_sha256={n:sha(NEW/n) for n in new_summary['artifact_sha256']},errors=errors,error_count=len(errors));Path('/private/tmp/stage105_final_text_patch_independent_audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
