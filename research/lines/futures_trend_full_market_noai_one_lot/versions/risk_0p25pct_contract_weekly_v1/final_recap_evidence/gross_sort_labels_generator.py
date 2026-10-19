"""End-only public text correction. Original chart algorithms and all data bytes stay fixed."""
from pathlib import Path
import json,hashlib,shutil
line=Path.cwd()/'research/lines/futures_trend_full_market_noai_one_lot';parent=line/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v2';output=line/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary=json.loads((parent/'summary.json').read_text());original=(parent/'index.html').read_text()
assert sha(parent/'index.html')=='b0eca000d4af4b1af0f7868127da7c46bd267cec2b4e6a9136088c6990b74a48'
assert all(sha(parent/n)==h for n,h in summary['artifact_sha256'].items()) and not output.exists()
replacements={'净利润绝对值从大到小':'毛盈亏绝对值从大到小','净利润绝对值从小到大':'毛盈亏绝对值从小到大'}
note_text='排序与筛选口径：本页盈亏金额排序、盈利/亏损筛选及R的分子均使用毛价差盈亏；净盈亏在卡片单列，包含分摊手续费和滑点。账户总览中的胜率和盈亏比按完整原始开仓的净盈亏统计；部分平仓或每手不另计胜负样本。'
note='<div id="stage106-gross-sort-note" class="note">'+note_text+'</div>'
page=original
for old,new in replacements.items():assert page.count(old)==1 and new not in page;page=page.replace(old,new,1)
anchor='<div class="note" id="stage083-multilot-display-note"';assert page.count(anchor)==1 and note not in page;page=page.replace(anchor,note+anchor,1)
restored=page.replace(note,'',1)
for old,new in replacements.items():assert restored.count(new)==1;restored=restored.replace(new,old,1)
assert restored==original
output.mkdir()
for n in summary['artifact_sha256']:
 if n!='index.html':shutil.copy2(parent/n,output/n)
(output/'index.html').write_text(page)
proof=dict(scope='two_sort_option_labels_and_plain_static_disclosure_only',parent_directory=str(parent),parent_summary_sha256=sha(parent/'summary.json'),parent_html_sha256=sha(parent/'index.html'),generator_sha256=sha(Path(__file__)),replacement_map=replacements,note_id='stage106-gross-sort-note',note_text=note_text,reverse_html_byte_equivalence=True,chart_algorithm_changed=False,records_changed=False,financial_replays=0,non_html_hashes={n:h for n,h in summary['artifact_sha256'].items() if n!='index.html'})
for n,h in proof['non_html_hashes'].items():assert sha(output/n)==h
(output/'gross_sort_labels_manifest.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,output/'gross_sort_labels_generator.py')
summary['gross_sort_labels_patch']=proof;summary['source_warning']+=' '+note_text;summary['artifact_sha256']={p.name:sha(p) for p in output.iterdir() if p.name!='summary.json'}
(output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
assert all(sha(parent/n)==h for n,h in json.loads((parent/'summary.json').read_text())['artifact_sha256'].items())
print(json.dumps({'output':str(output),'html_sha256':sha(output/'index.html'),'records_sha256':sha(output/'records.json'),'non_html_unchanged':len(proof['non_html_hashes'])},ensure_ascii=False))
