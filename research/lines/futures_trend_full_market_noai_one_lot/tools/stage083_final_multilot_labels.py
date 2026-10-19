"""Restore final multi-lot labels after canonical review, without chart rerender.

Only two declared JS metric text expressions and one escaped plain-text note
change. Every other artifact, embedded record, array and coordinate stays exact.
Run after Stage020 review and before Stage067 current-trade reset.
"""
import argparse,html,json,math,shutil
from pathlib import Path
from stage001_frozen_recap import CANONICAL,sha256 as sha
from stage042_account_overview import verify_hashes,safe_member

NOTE_ID='stage083-multilot-display-note'
NOTE=('多手与分批平仓说明：毛/净盈亏分别为完整entry全部平仓段价差毛额、扣该entry分摊手续费和滑点后的净额；交易手数是原始开仓全部数量，不是平仓片段数。'
    '紫色最终退出点为最后一笔实际成交价，只在图中行情同源时显示；紫线为最终实际退出日期，不展示每个部分退出箭头。'
    '价格涨跌使用全部退出按数量计算的加权平均退出价，不代表最终退出日的真实成交均价；金额归因和最终日期以原始fills对账。')
REPLACEMENTS={"['净利润',pnlValue]":"['毛/净盈亏',pnlValue+'<span class=\"submetric\">净 '+fmt(m.net_pnl,2)+'；成本 '+fmt(m.cost,2)+'</span>']", "['平仓lot',m.lot_count]":"['交易手数',m.volume]"}

def check(ok,reason):
    if not ok:raise ValueError(reason)

def note_html():return '<div class="note" id="'+NOTE_ID+'">'+html.escape(NOTE)+'</div>'

def patch_html(page):
    check(NOTE_ID not in page,'already_patched')
    for old,new in REPLACEMENTS.items():check(page.count(old)==1 and new not in page,'label_contract_changed');page=page.replace(old,new,1)
    check(page.count('<div class="note">')==1,'plain_note_contract_changed')
    return page.replace('<div class="note">',note_html()+'<div class="note">',1)

def unpatch_html(page):
    check(page.count(note_html())==1,'disclosure_changed');page=page.replace(note_html(),'',1)
    for old,new in REPLACEMENTS.items():check(page.count(new)==1,'patched_label_contract_changed');page=page.replace(new,old,1)
    return page

def verify_exit_semantics(records):
    code=CANONICAL.read_text()
    for snippet in ('"exit_price": float(final["exit_price"])','"weighted_exit_price": weighted_exit_price','"exit_marker_price": float(row.exit_price) if exit_source == vt_symbol else None','y:[m.entry_marker_price,m.exit_marker_price]'):
        check(snippet in code,'canonical_exit_semantics_changed')
    differing=0;hidden=0
    for r in records:
        m=r['meta'];actual=m['exit_marker_price'];expected=m['exit_price'] if m['exit_source']==m['vt_symbol'] else None
        check(actual==expected,'actual_final_exit_marker_mismatch')
        hidden+=actual is None;differing+=not math.isclose(m['exit_price'],m['weighted_exit_price'],abs_tol=1e-10,rel_tol=1e-12)
        check(math.isclose(m['price_change_pct'],(m['weighted_exit_price']/m['entry_price']-1)*100,abs_tol=1e-9,rel_tol=1e-11),'weighted_price_change_mismatch')
    return dict(records_checked=len(records),marker_price_basis='last_actual_exit_fill',price_change_basis='all_exit_quantity_weighted_average',weighted_exit_differs_from_last_fill=differing,hidden_non_same_source_markers=hidden,all_partial_fill_arrows=False,canonical_sha256=sha(CANONICAL))

def embedded(page):
    marker='const records=';check(marker in page,'embedded_records_missing');return json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):])[0]

def generate(parent,output):
    parent,output=Path(parent).resolve(),Path(output).resolve();check(not(output.is_relative_to(parent) or parent.is_relative_to(output)),'output_overlaps_parent')
    if output.exists():raise FileExistsError(output)
    code_hash=sha(Path(__file__));parent_hash=sha(parent/'summary.json');summary=json.loads((parent/'summary.json').read_text());artifacts=dict(summary['artifact_sha256'])
    for name in ('records.json','index.html','chart_manifest.csv'):check(name in artifacts,'parent_binding_missing:'+name)
    for name,digest in artifacts.items():check(sha(safe_member(parent,name))==digest,'parent_hash_mismatch:'+name)
    source=Path(summary['source_directory']).resolve();check(not(output.is_relative_to(source) or source.is_relative_to(output)),'output_overlaps_source');identity=json.loads((source/'manifest.json').read_text());bound=verify_hashes(source,identity)
    check(sha(source/'manifest.json')==summary['source_manifest_sha256'] and json.loads((source/'summary.json').read_text())==summary['backtest_metrics'],'source_identity_mismatch')
    check(summary['canonical_renderer_sha256']==sha(CANONICAL),'canonical_hash_mismatch');records=json.loads((parent/'records.json').read_text());original=(parent/'index.html').read_text();check(embedded(original)==records,'parent_embedded_records_mismatch')
    marker_proof=verify_exit_semantics(records);page=patch_html(original);check(unpatch_html(page)==original and embedded(page)==records,'html_patch_exceeds_whitelist')
    proof=dict(generator_sha256=code_hash,parent_directory=str(parent),parent_summary_sha256=parent_hash,parent_artifact_sha256=artifacts,source_manifest_sha256=summary['source_manifest_sha256'],source_hashes=bound,
        canonical_sha256=sha(CANONICAL),literal_replacements=REPLACEMENTS,plain_text_disclosure=NOTE,original_html_sha256=sha(parent/'index.html'),records_sha256=artifacts['records.json'],records_count=len(records),
        embedded_records_identical=True,all_non_html_artifacts_byte_identical=True,html_patch_reverses_exactly=True,exit_semantics=marker_proof,financial_replays=0,market_downloads=0,production_access=False)
    output.mkdir(parents=True)
    for name,digest in artifacts.items():
        if name not in ('index.html','summary.json'):
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(safe_member(parent,name),target);check(sha(target)==digest,'copied_bytes_changed:'+name)
    (output/'index.html').write_text(page);proof['patched_html_sha256']=sha(output/'index.html')
    (output/'final_multilot_display_manifest.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');summary['final_multilot_display']=proof;summary['source_warning']+=' '+NOTE
    for name,digest in artifacts.items():check(sha(safe_member(parent,name))==digest,'parent_changed_during_render:'+name)
    check(sha(parent/'summary.json')==parent_hash and sha(Path(__file__))==code_hash and sha(source/'manifest.json')==proof['source_manifest_sha256'] and verify_hashes(source,identity)==bound,'inputs_changed_during_render')
    summary['artifact_sha256']={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file() and p.name!='summary.json'}
    if 'artifact_bytes' in summary:summary['artifact_bytes']={p.relative_to(output).as_posix():p.stat().st_size for p in output.rglob('*') if p.is_file() and p.name!='summary.json'}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=generate(a.parent,a.output);print(json.dumps(r['final_multilot_display'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
