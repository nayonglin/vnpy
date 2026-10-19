"""Enrich a completed canonical recap with accepted actual-initial-risk gross R.

Chart arrays, coordinates, order and original tail/selection labels stay intact.
Only CSV risk_amount/r_multiple and records.meta equivalents gain risk evidence.
The source, parent recap, and canonical renderer are read-only hash-bound inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

import pandas as pd

from stage001_frozen_recap import CANONICAL,load_display_functions,sha256


def require(condition,message):
    if not condition:raise ValueError(message)


def non_r_payload_hash(records):
    """Hash every plot and metadata field other than the two authorized additions."""
    digest=hashlib.sha256();digest.update(b'[')
    for index,record in enumerate(records):
        if index:digest.update(b',')
        value={**record,'meta':{key:item for key,item in record['meta'].items() if key not in ('risk_amount','r_multiple')}}
        digest.update(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    digest.update(b']');return digest.hexdigest()


def finite_positive(value):
    try:return math.isfinite(float(value)) and float(value)>0
    except (ValueError,TypeError,OverflowError):return False


def equal_number(left,right,message):
    require(math.isclose(float(left),float(right),rel_tol=1e-10,abs_tol=1e-7),message)


def enrich_csv(parent,output,name,risk_by_id,r_by_id):
    """Preserve all non-R CSV cell strings exactly; avoid pandas float reformatting."""
    with (parent/name).open(newline='',encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle);fields=list(reader.fieldnames or []);rows=list(reader)
    require('open_trade_id' in fields,'parent_CSV_open_identity_missing:'+name)
    for field in ('risk_amount','r_multiple'):
        if field not in fields:fields.append(field)
    for row in rows:
        key=row['open_trade_id'];require(key in risk_by_id,'actual_open_risk_receipt_missing:'+key)
        row['risk_amount']=repr(float(risk_by_id[key]));row['r_multiple']=repr(float(r_by_id[key]))
    with (output/name).open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def enrich(source:Path,parent:Path,output:Path):
    source,parent,output=(Path(value).resolve() for value in (source,parent,output))
    for original in (source,parent):
        require(not(output==original or original in output.parents or output in original.parents),'output_must_be_isolated')
    if output.exists():raise FileExistsError(output)
    generator=Path(__file__).resolve();generator_hash=sha256(generator)
    identity=json.loads((source/'manifest.json').read_text())
    source_hash=sha256(source/'manifest.json')
    for name,digest in identity['hashes'].items():
        require(Path(name).name==name and (source/name).is_file() and sha256(source/name)==digest,'source_hash_mismatch:'+name)
    for name,digest in identity.get('code_snapshot_hashes',{}).items():
        require(Path(name).name==name and sha256(source/'code_snapshot'/name)==digest,'source_snapshot_hash_mismatch:'+name)
    summary=json.loads((parent/'summary.json').read_text())
    parent_summary_hash=sha256(parent/'summary.json')
    require(Path(summary['source_directory']).resolve()==source and summary['source_manifest_sha256']==source_hash,'parent_source_hash_identity_mismatch')
    require(summary['backtest_metrics']==json.loads((source/'summary.json').read_text()),'parent_source_metrics_changed')
    for required in ('records.json','closed_lots.csv','all_trade_episodes.csv','chart_manifest.csv','index.html'):
        require(required in summary['artifact_sha256'],'parent_hash_binding_missing:'+required)
    for name,digest in summary['artifact_sha256'].items():
        require(Path(name).name==name and (parent/name).is_file() and sha256(parent/name)==digest,'parent_hash_mismatch:'+name)
    require(Path(summary['canonical_renderer']).resolve()==CANONICAL and sha256(CANONICAL)==summary['canonical_renderer_sha256'],'canonical_hash_mismatch')
    records=json.loads((parent/'records.json').read_text())
    original_page=(parent/'index.html').read_text();marker='const records='
    embedded,_=json.JSONDecoder().raw_decode(original_page[original_page.index(marker)+len(marker):])
    require(embedded==records,'parent_embedded_records_changed')
    del embedded,original_page
    before_hash=non_r_payload_hash(records)
    trades=pd.read_csv(source/'trades.csv',float_precision='round_trip');require(not trades.trade_id.duplicated().any(),'actual_open_risk_trade_identity_duplicated')
    opens=trades[trades.offset.eq('open')].copy()
    require(not opens.empty and opens.volume.eq(1).all(),'actual_open_risk_requires_one_lot_receipts')
    require({'stage041_entry_risk','stage041_open_budget','stage041_signal_snapshot'}.issubset(opens.columns),'actual_open_risk_receipt_fields_missing')
    metadata=pd.read_csv(source/'contract_metadata.csv',float_precision='round_trip').set_index('vt_symbol')
    audit=pd.read_csv(source/'open_budget_audit.csv',float_precision='round_trip')
    accepted=audit[audit.filled.astype(str).str.lower().eq('true')]
    require(not accepted.trade_id.duplicated().any() and set(accepted.trade_id)==set(opens.trade_id),'actual_open_risk_accepted_audit_identity_mismatch')
    accepted=accepted.set_index('trade_id')
    for row in opens.itertuples(index=False):
        require(finite_positive(row.stage041_entry_risk),'actual_open_risk_missing_or_invalid:'+str(row.trade_id))
        require(finite_positive(row.stage041_open_budget) and row.stage041_entry_risk<=row.stage041_open_budget,'actual_open_risk_exceeds_accepted_budget:'+str(row.trade_id))
        receipt=json.loads(row.stage041_signal_snapshot);bound=accepted.loc[row.trade_id]
        require(receipt==json.loads(bound.signal_snapshot),'actual_open_risk_snapshot_audit_mismatch:'+str(row.trade_id))
        require(receipt.get('contract_vt_symbol')==row.vt_symbol and receipt.get('direction')==row.direction,'actual_open_risk_snapshot_identity_mismatch:'+str(row.trade_id))
        require(finite_positive(receipt.get('target_risk_amount')) and row.stage041_open_budget<=receipt['target_risk_amount'],'actual_open_risk_exceeds_signal_authorization:'+str(row.trade_id))
        stop=float(receipt['stop_price']);size=float(metadata.loc[row.vt_symbol,'size']);tick=float(metadata.loc[row.vt_symbol,'pricetick'])
        require(all(finite_positive(value) for value in (row.price,stop,size,tick)),'actual_open_risk_invalid_price_or_metadata')
        require(row.price>stop if row.direction=='long' else row.price<stop,'actual_open_risk_stop_already_crossed')
        reconstructed=max(abs(row.price-stop)*size,tick*size,1.)
        equal_number(row.stage041_entry_risk,reconstructed,'actual_open_risk_not_accepted_initial_stop_distance:'+str(row.trade_id))
        equal_number(row.stage041_entry_risk,bound.one_lot_risk,'actual_open_risk_audit_value_mismatch:'+str(row.trade_id))
        equal_number(row.stage041_open_budget,bound.opening_budget,'actual_open_risk_audit_budget_mismatch:'+str(row.trade_id))
    actual_risk=opens.set_index(opens.trade_id.astype(str))['stage041_entry_risk'].astype(float).to_dict()
    closed=pd.read_csv(parent/'closed_lots.csv',float_precision='round_trip')
    require(not closed.open_trade_id.duplicated().any() and closed.volume.eq(1).all(),'one_lot_closed_identity_ambiguous')
    require(set(closed.open_trade_id).issubset(actual_risk),'actual_open_risk_receipt_missing_for_closed_episode')
    closed['risk_amount']=closed.open_trade_id.map(actual_risk)
    closed['r_multiple']=closed.realized_pnl/closed.risk_amount
    renderer=load_display_functions({})
    canonical_episodes=renderer._all_trade_episodes(closed).set_index('open_trade_id')
    risk_by_id=canonical_episodes['risk_amount'].astype(float).to_dict()
    r_by_id=canonical_episodes['r_multiple'].astype(float).to_dict()
    ids=[str(record['meta']['open_trade_id']) for record in records]
    require(len(set(ids))==len(ids) and set(ids)==set(risk_by_id),'parent_chart_and_completed_risk_episode_identity_mismatch')
    for record in records:
        key=str(record['meta']['open_trade_id'])
        record['meta']['risk_amount']=risk_by_id[key]
        record['meta']['r_multiple']=r_by_id[key]
    after_hash=non_r_payload_hash(records)
    require(before_hash==after_hash,'plot_arrays_coordinates_or_non_R_metadata_changed')
    note=('R定义：每笔毛盈亏除以该笔原始开仓实际接受的初始止损风险（stage041_entry_risk，含原tick最小风险下限）；'
          '分母不是目标风险预算，分子不扣手续费/滑点。原记录顺序、盈亏排序与尾部标签保留，不重选；标签中的R缺失指父页生成时的筛选口径，新增R不追溯改变该口径。')
    summary['source_warning']=summary['source_warning'].replace('R不可获得时显示N/A。','').replace('R不可获得时显示N/A','')+' '+note
    provenance=dict(generator=str(generator),generator_sha256=generator_hash,source_manifest_sha256=source_hash,
        parent_directory=str(parent),parent_summary_sha256=parent_summary_hash,parent_artifact_sha256=dict(summary['artifact_sha256']),
        accepted_open_risk_receipts=len(opens),enriched_complete_episodes=len(records),
        denominator='accepted_actual_initial_stop_distance_risk_stage041_entry_risk',numerator='canonical_episode_gross_realized_pnl',
        selection_and_order_preserved=True,non_r_payload_sha256_before=before_hash,non_r_payload_sha256_after=after_hash,
        financial_replays=0,market_downloads=0,source_mutations=0)
    summary['risk_enrichment']=provenance
    summary['parent_render_summary_sha256']=parent_summary_hash
    # The pure canonical HTML implementation is reused without changing plotting code.
    page=renderer._html(records,summary)
    require(sha256(generator)==generator_hash and sha256(source/'manifest.json')==source_hash and sha256(parent/'summary.json')==parent_summary_hash,'inputs_or_generator_changed_during_enrichment')
    output.mkdir(parents=True)
    for name in summary['artifact_sha256']:
        if name not in ('index.html','records.json','closed_lots.csv','all_trade_episodes.csv','chart_manifest.csv','summary.json'):
            shutil.copy2(parent/name,output/name)
    for name in ('closed_lots.csv','all_trade_episodes.csv','chart_manifest.csv'):
        enrich_csv(parent,output,name,risk_by_id,r_by_id)
    (output/'records.json').write_text(json.dumps(renderer._json_safe(records),ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    (output/'index.html').write_text(page,encoding='utf-8')
    (output/'risk_enrichment_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary['artifact_sha256']={path.name:sha256(path) for path in output.iterdir() if path.name!='summary.json'}
    (output/'summary.json').write_text(json.dumps(renderer._json_safe(summary),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--parent',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=enrich(args.source,args.parent,args.output)
    print(json.dumps(result['risk_enrichment'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
