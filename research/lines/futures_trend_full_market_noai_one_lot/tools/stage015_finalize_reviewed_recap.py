"""Bind independent review and residual quote dates to a new canonical-rendered page.
Reuses hash-bound serialized chart records; no strategy or market context rerun.
"""
from pathlib import Path
import json,shutil,sys
import pandas as pd
from stage001_frozen_recap import sha256,load_display_functions

def finalize(parent,report,output):
    if output.exists():raise FileExistsError(output)
    summary=json.loads((parent/'summary.json').read_text())
    for name,digest in summary['artifact_sha256'].items():
        if sha256(parent/name)!=digest:raise ValueError('parent_artifact_changed:'+name)
    source=Path(summary['source_directory'])
    if sha256(source/'manifest.json')!=summary['source_manifest_sha256']:raise ValueError('frozen_source_changed')
    page=(parent/'index.html').read_text()
    marker='const records=';start=page.index(marker)+len(marker)
    records,end=json.JSONDecoder().raw_decode(page[start:])
    if len(records)!=summary['chart_episodes']:raise ValueError('record_count_changed')
    market=pd.read_csv(source/'market_daily.csv',usecols=['vt_symbol','date'])
    residual=json.loads((source/'residual_open_positions.json').read_text())
    last=market.groupby('vt_symbol').date.max()
    detail='；'.join(f"{x['vt_symbol']}（{'多' if x['direction']=='long' else '空'}1手，最后报价{last[x['vt_symbol']] }）" for x in residual)
    meta=pd.read_csv(source/'contract_metadata.csv')
    trades=pd.read_csv(source/'trades.csv')
    exchanges=set(meta[meta.vt_symbol.isin(trades.vt_symbol)].exchange)
    summary['source_warning'] += ' 独立审查补充：四残仓及最后报价日：'+detail+'。全市场输入93品种/六所，实际67品种/五所成交，GFEX入池但0成交。'
    summary['independent_review']={'path':str(report),'sha256':sha256(report),'verdict':'diagnostic_delivery_only_performance_certification_FAIL'}
    summary['parent_render_summary_sha256']=sha256(parent/'summary.json')
    summary['review_finalizer_sha256']=sha256(Path(__file__))
    summary['serialized_records_reused']=True
    summary['canonical_renderer_sha256_before_finalization']=summary['canonical_renderer_sha256']
    renderer=load_display_functions({})
    if sha256(Path(summary['canonical_renderer']))!=summary['canonical_renderer_sha256']:raise ValueError('canonical_changed')
    available_ids={r['meta']['open_trade_id'] for r in records if len(r['intraday']['x'])>0}
    for r in records:r['meta']['draw_intraday']=int(r['meta']['open_trade_id'] in available_ids)
    summary['minute_availability_qualified_from_actual_bars']=True
    newpage=renderer._html(records,summary)
    output.mkdir(parents=True)
    for p in parent.iterdir():
        if p.name not in ('summary.json','index.html'):shutil.copy2(p,output/p.name)
    for name in ['chart_manifest.csv','all_trade_episodes.csv']:
        frame=pd.read_csv(output/name)
        frame['draw_intraday']=frame.open_trade_id.isin(available_ids).astype(int)
        frame.to_csv(output/name,index=False)
    shutil.copy2(report,output/'independent_review.md')
    shutil.copy2(report.with_suffix('.json'),output/'independent_review.json')
    (output/'index.html').write_text(newpage)
    summary['artifact_sha256']={p.name:sha256(p) for p in output.iterdir()}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({'episodes':len(records),'residuals':len(residual),'traded_exchanges':sorted(exchanges),'html_bytes':len(newpage.encode())},ensure_ascii=False))
if __name__=='__main__':finalize(*map(lambda x:Path(x).resolve(),sys.argv[1:]))
