"""Increment only281's eleven CSVs; reuse accepted275 projections, zero finance.

Never open273's original47 payloads. Accepted subset/report rows are copied;
only281's eleven standalone CSVs pass through the accepted275 pure parser.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time

LINE=Path(__file__).resolve().parents[1]
OUTPUT=LINE/'outputs/stage282_wasde_incremental_projection/actual_run1'
CORE=Path(__file__).with_name('stage275_wasde_corn_projection.py')
CORE_SHA='4467590ea3f5f8d1bfbccc051698e4075d650e632c46e1dbb951d8802b6a9fda'


def combine_reports(old,new):
    rows=[dict(r,projection_origin_stage='275',acquisition_stage='273') for r in old]
    rows.extend(dict(r,projection_origin_stage='282',acquisition_stage='281') for r in new)
    identities=[(r['WasdeNumber'],r['release_date']) for r in rows]
    if len(identities)!=len(set(identities)):raise ValueError('increment_overlaps_accepted_report')
    return sorted(rows,key=lambda r:(r['release_date'],r['WasdeNumber']))


def remaining_gaps(old_unknown,attempted278,successful281):
    filled={r['filename'] for r in successful281 if r['status']=='body_retained_unparsed'}
    tried={r['filename']:r for r in attempted278};result=[]
    for prior in old_unknown:
        if prior['filename'] in filled:continue
        row=dict(prior,release_date=None)
        if prior['filename'] in tried:
            request=tried[prior['filename']]
            row.update(acquisition_stage='278',reason=request['status'],error=request.get('error'))
        elif prior['reason']=='failed':row['acquisition_stage']='273'
        else:row.update(acquisition_stage='278',reason='unattempted_CDN')
        result.append(row)
    return result


def binding(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_json(path):
    raw=Path(path).read_bytes();return json.loads(raw),binding(path,raw)


def accepted_csv(ref):
    raw=Path(ref['path']).read_bytes();got=binding(ref['path'],raw)
    if any(got[k]!=ref[k] for k in ('bytes','sha256')):raise ValueError('accepted275_output_changed')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as z,io.TextIOWrapper(z,encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    return fields,rows,got


def run_actual():
    core_ref=binding(CORE)
    if core_ref['sha256']!=CORE_SHA:raise ValueError('accepted275_pure_source_changed')
    spec=importlib.util.spec_from_file_location('accepted275',CORE);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    review,review_ref=read_json(LINE/'outputs/stage276_wasde_projection_review/receipt.json')
    if review['status']!='completed' or review['core_blockers']!=0:raise ValueError('276_not_accepted')
    old_manifest,old_manifest_ref=read_json(LINE/'outputs/stage275_wasde_corn_projection/actual_run1/manifest.json')
    new_manifest,new_manifest_ref=read_json(LINE/'outputs/stage281_original_host_wasde_source/actual_run1/manifest.json')
    prior_manifest,prior_manifest_ref=read_json(LINE/'outputs/stage278_remaining_wasde_source/actual_run1/manifest.json')
    successful=[r for r in new_manifest['requests'] if r['status']=='body_retained_unparsed']
    if (new_manifest['terminal']['status']!='completed' or len(successful)!=11
            or sum(r['bytes'] for r in successful)!=10849860 or any(r['kind']!='csv' for r in successful)):
        raise ValueError('281_completed_eleven_source_contract')
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic();status='failed';failure=None
    inputs=dict(accepted276=review_ref,accepted275_manifest=old_manifest_ref,source281_manifest=new_manifest_ref,
        prior278_manifest=prior_manifest_ref,accepted275_pure_source=core_ref)
    old_rows=[];old_reports=[];new_rows=[];new_reports=[];merged=[];gaps=[];inventory=[];streams=0
    ledger={k:Counter() for k in ('MarketYear','ForecastYear','Unit','ProjEstFlag','AnnualQuarterFlag','ReportDate')};ledger['all_source_rows']=0
    try:
        fields,old_rows,ref=accepted_csv(old_manifest['artifacts']['corn_world_rows']);inputs['accepted275_Corn_subset']=ref
        projection_fields,old_reports,ref=accepted_csv(old_manifest['artifacts']['report_projection']);inputs['accepted275_report_projection']=ref
        old_inventory,ref=read_json(old_manifest['artifacts']['source_inventory']['path']);inputs['accepted275_inventory']=ref
        if any(ref[k]!=old_manifest['artifacts']['source_inventory'][k] for k in ('bytes','sha256')):raise ValueError('275_inventory_changed')
        if len(old_rows)!=3612 or len(old_reports)!=172:raise ValueError('accepted275_row_identity')
        for request in successful:
            path=Path(request['path']);entry=dict(filename=request['filename'],month=request['month'],visible_version_suffix=request.get('visible_version_suffix'),
                inherited_body_binding={k:request[k] for k in ('path','bytes','sha256')},integrity_rehash=False)
            inventory.append(entry)
            if path.stat().st_size!=request['bytes']:raise ValueError('new281_source_size_changed')
            streams+=1
            rows,info=p.consume_csv(path.open('rb'),request,'',ledger);entry['stream']=info;new_rows.extend(rows)
        grouped=defaultdict(list)
        for row in new_rows:grouped[row['WasdeNumber'] or 'unknown::'+row['source_filename']].append(row)
        new_reports=[p.project_report(rows) for rows in grouped.values()]
        merged=combine_reports(old_reports,new_reports)
        gaps=remaining_gaps(old_inventory['source_unknown_months'],prior_manifest['requests'],successful)
        observed={r['release_month'] for r in old_reports if r['release_month']}
        absent=[f'{year:04d}-{month:02d}' for year in range(2010,2021) for month in range(1,13)
            if (year,month)>=(2010,4) and f'{year:04d}-{month:02d}' not in observed]
        p.write_csv(OUTPUT/'corn_world_rows.csv.gz',fields,old_rows+new_rows)
        p.write_csv(OUTPUT/'report_projection.csv.gz',projection_fields+['projection_origin_stage','acquisition_stage'],merged)
        p.save_json(OUTPUT/'source_inventory.json',dict(schema='stage282_incremental_source_inventory_v1',new_sources=inventory,
            accepted_old_source_inventory=inputs['accepted275_inventory'],source_unknown_months=gaps,
            unlisted_calendar_months=old_inventory['unlisted_calendar_months'],archive_nominal_months_without_observed_report=absent,
            no_missing_month_release_dates_invented=True,no_carry=True,new_source_ledger=ledger,
            new_report_unknowns=[{k:r[k] for k in ('WasdeNumber','release_date','unknown_reason')} for r in new_reports if not r['feature_eligible']]))
        status='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    eligible=lambda r:r['feature_eligible'] is True or r['feature_eligible']=='True'
    receipt=dict(schema='stage282_wasde_incremental_projection_receipt_v1',status=status,inputs=inputs,source=binding(__file__),
        source281_actual_session=95256,source281_actual_exit_code=0,source281_bodies=11,source281_body_bytes=10849860,
        source281_CSV_streams=streams,source273_old_original_reads=0,source278_original_reads=0,original_integrity_rehashes=0,
        accepted_old_subset_rows=len(old_rows),accepted_old_report_rows=len(old_reports),new_all_source_rows=ledger['all_source_rows'],
        new_Corn_World_rows=len(new_rows),merged_Corn_World_rows=len(old_rows)+len(new_rows),new_report_rows=len(new_reports),merged_report_rows=len(merged),
        new_feature_eligible=sum(eligible(r) for r in new_reports),merged_feature_eligible=sum(eligible(r) for r in merged),
        new_unknown_reasons=dict(Counter(r['unknown_reason'] for r in new_reports if r['unknown_reason'])),
        source_unknown_months=gaps,source_gap_counts=dict(Counter(r['acquisition_stage']+':'+r['reason'] for r in gaps)),
        visible_V2='raw quantity retained; feature_eligible false; correction_known_at unknown',
        source_time='ReleaseDate literal and parsed date; ReleaseTime literal; candidate release+2 NewYork00 UTC inherited275, not proven known_at',
        offset_join_not_run=True,network=0,SQL=0,native_price_reads=0,labels=0,new_fit=0,new_cash=0,cumulative_fit=439,cumulative_cash=238,
        automatic_retry=False,goal_complete=False,failure=failure,completed_at=p.now(),elapsed_seconds=time.monotonic()-began)
    p.save_json(OUTPUT/'receipt.json',receipt)
    p.save_json(OUTPUT/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
    roles={k:k+suffix for k,suffix in [('corn_world_rows','.csv.gz'),('report_projection','.csv.gz'),('source_inventory','.json'),('receipt','.json'),('terminal','.json')]}
    p.save_json(OUTPUT/'manifest.json',dict(schema='stage282_wasde_incremental_projection_manifest_v1',status=status,
        source=receipt['source'],inputs=inputs,artifacts={k:binding(OUTPUT/v) for k,v in roles.items() if (OUTPUT/v).is_file()},new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',required=True);parser.parse_args(argv)
    r=run_actual()
    print(json.dumps({k:r[k] for k in ['status','source281_CSV_streams','new_Corn_World_rows','merged_Corn_World_rows',
        'new_report_rows','merged_report_rows','new_feature_eligible','merged_feature_eligible','new_unknown_reasons','source_gap_counts','elapsed_seconds']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
