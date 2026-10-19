"""Append a current-trade Reset axes handler to a new readonly recap version.

No chart data, canonical source, finance or existing artifact is modified.
"""
import argparse,hashlib,json,shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_ID='stage067-current-trade-reset'
SCRIPT=r'''(() => {
  'use strict';
  document.addEventListener('click', function (event) {
    const target = event.target;
    const element = target && typeof target.closest === 'function' ? target : target && target.parentElement;
    const button = element && element.closest('[data-title="Reset axes"]');
    const chart = document.getElementById('chart');
    if (!button || !chart || !chart.contains(button)) return;
    if (typeof filtered === 'undefined' || !Array.isArray(filtered) || !filtered.length || typeof active === 'undefined') return;
    const record = filtered[active];
    const meta = record && record.meta;
    if (!meta || !Number.isFinite(meta.chart_x_start) || !Number.isFinite(meta.chart_x_end) || meta.chart_x_start >= meta.chart_x_end) return;
    if (typeof visiblePeriodOptions !== 'function' || typeof Plotly === 'undefined' || typeof Plotly.relayout !== 'function') return;
    const visible = visiblePeriodOptions(meta);
    if (!Array.isArray(visible) || !visible.length) return;
    const update = {};
    const axis = (prefix, index) => prefix + 'axis' + (index === 0 ? '' : String(index + 1));
    visible.forEach((option, index) => {
      update[axis('x', index) + '.range'] = [meta.chart_x_start, meta.chart_x_end];
      update[axis('x', index) + '.autorange'] = false;
      update[axis('y', index * 2) + '.autorange'] = true;
      update[axis('y', index * 2 + 1) + '.autorange'] = true;
    });
    event.preventDefault();
    event.stopImmediatePropagation();
    Plotly.relayout(chart, update);
  }, true);
})();'''


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def member(root,name):
    p=(root/name).resolve();require(p.is_relative_to(root) and p.is_file(),'unsafe_artifact_path:'+name);return p


def verify(root,entries):
    for name,digest in entries.items():require(sha(member(root,name))==digest,'parent_hash_mismatch:'+name)


def script_tag():return '<script id="'+SCRIPT_ID+'">\n'+SCRIPT+'\n</script>'


def patch_html(page):
    require(SCRIPT_ID not in page,'already_patched')
    require(page.count('</body>')==1,'expected_single_body_close')
    return page.replace('</body>',script_tag()+'</body>',1)


def records_from_html(page):
    marker='const records=';require(marker in page,'canonical_records_marker_missing')
    return json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):])[0]


def generate(parent,output):
    parent,output=(Path(p).resolve() for p in (parent,output))
    require(not(output.is_relative_to(parent) or parent.is_relative_to(output)),'output_overlaps_parent')
    if output.exists():raise FileExistsError(output)
    generator_hash=sha(Path(__file__));parent_hash=sha(parent/'summary.json');summary=json.loads((parent/'summary.json').read_text());artifacts=dict(summary['artifact_sha256'])
    for name in ('index.html','records.json','chart_manifest.csv'):require(name in artifacts,'parent_artifact_binding_missing:'+name)
    require('current_trade_reset_manifest.json' not in artifacts,'already_patched')
    verify(parent,artifacts);source_evidence={}
    if 'source_directory' in summary:
        source=Path(summary['source_directory']).resolve();identity=json.loads((source/'manifest.json').read_text())
        require(sha(source/'manifest.json')==summary['source_manifest_sha256'],'source_manifest_mismatch')
        verify(source,identity['hashes']);verify(source/'code_snapshot',identity.get('code_snapshot_hashes',{}))
        require(json.loads((source/'summary.json').read_text())==summary['backtest_metrics'],'source_metrics_mismatch')
        source_evidence=dict(manifest_sha256=summary['source_manifest_sha256'],hashes=identity['hashes'],code_snapshot_hashes=identity.get('code_snapshot_hashes',{}))
    original=(parent/'index.html').read_text();records=json.loads((parent/'records.json').read_text())
    require(records_from_html(original)==records,'parent_embedded_records_mismatch')
    page=patch_html(original);require(page.replace(script_tag(),'',1)==original,'html_not_append_only')
    require(records_from_html(page)==records,'patched_embedded_records_changed')
    provenance=dict(created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),generator_sha256=generator_hash,
        parent_directory=str(parent),parent_summary_sha256=parent_hash,parent_artifact_sha256=artifacts,
        source_evidence=source_evidence,original_html_sha256=artifacts['index.html'],script_sha256=hashlib.sha256(SCRIPT.encode()).hexdigest(),
        records_sha256=artifacts['records.json'],records_count=len(records),embedded_records_identical=True,
        other_artifacts_byte_identical=True,change='append_classic_capture_click_handler_for_current_trade_reset_axes_only',
        range_source='filtered[active].meta.chart_x_start/chart_x_end',period_source='visiblePeriodOptions(current_meta)',
        public_api='Plotly.relayout',private_plotly_state_access=False,financial_replays=0,market_downloads=0,production_access=False)
    output.mkdir(parents=True)
    for name in artifacts:
        if name!='index.html':
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(member(parent,name),target)
    (output/'index.html').write_text(page,encoding='utf-8');provenance['patched_html_sha256']=sha(output/'index.html')
    for name,digest in artifacts.items():
        if name!='index.html':require(sha(output/name)==digest,'copied_artifact_changed:'+name)
    verify(parent,artifacts);require(sha(parent/'summary.json')==parent_hash and sha(Path(__file__))==generator_hash,'parent_or_generator_changed')
    (output/'current_trade_reset_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    summary['ui_reset_fix']=provenance;summary['artifact_sha256']={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}
    if 'artifact_bytes' in summary:summary['artifact_bytes']={p.relative_to(output).as_posix():p.stat().st_size for p in output.rglob('*') if p.is_file()}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=generate(a.parent,a.output);print(json.dumps(r['ui_reset_fix'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
