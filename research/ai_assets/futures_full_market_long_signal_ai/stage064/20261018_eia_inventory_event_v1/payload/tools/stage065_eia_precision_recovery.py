"""One offline correction for independent rounding in already downloaded EIA stocks.

No downloads or fits. Keep Stage060 and all published stock/Difference values intact.
The unchanged Stage060 calendar/availability/ordinal52/sham logic is reused verbatim.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage065_eia_precision_recovery'
FROZEN060='f40f1b07007d283b950187d05f144ec9954c125433eb130165285e1bac07d45e'
SOURCE060=Path(__file__).with_name('stage060_eia_report_import.py')
spec=importlib.util.spec_from_file_location('frozen_stage060_precision_semantics',SOURCE060)
m060=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m060)
LABELS=m060.LABELS
ROUNDING_SOURCE='https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf'
ROUNDING_NOTE='Differences and percent changes are calculated using unrounded numbers'


def parse_rounded_table1(content: bytes, report: dict):
    """Validate displayed value intervals; never replace published Difference."""
    rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig',errors='replace').replace('\x1a',''))))
    if not rows or len(rows[0])<4 or rows[0][0]!='STUB_1' or rows[0][3]!='Difference':
        raise ValueError('Table1 stock header not recognized')
    ending=m060._table_date(rows[0][1]); prior_ending=m060._table_date(rows[0][2])
    if ending!=report['data_ending_expected']:
        raise ValueError('data-ending differs from official calendar; not a rounding repair')
    found={}; audit={}
    for rownum,row in enumerate(rows[1:],2):
        if row and row[0]=='STUB_1':break
        if not row or row[0] not in LABELS:continue
        if row[0] in found or len(row)<4:raise ValueError('duplicate or short stock component')
        try:
            current,prior,delta=[Decimal(s.replace(',','').strip()) for s in row[1:4]]
        except InvalidOperation as exc:
            raise ValueError('stock has nonnumeric value') from exc
        nums=(current,prior,delta)
        if not all(x.is_finite() for x in nums) or current<=0 or prior<=0:
            raise ValueError('nonfinite or nonpositive stock level')
        qc,qp,qd=[Decimal(10)**x.as_tuple().exponent for x in nums]
        residual=current-prior-delta
        bound=(qc+qp+qd)/2
        compatible=abs(residual)<=bound
        audit[row[0]]=dict(scope='cell',report_id=report['report_id'],series_label=row[0],source_row_number=rownum,
                          raw_current=str(current),raw_prior_inline=str(prior),raw_difference=str(delta),
                          current_quantum_native=str(qc),prior_quantum_native=str(qp),difference_quantum_native=str(qd),
                          residual_native=str(residual),rounding_bound_native=str(bound),rounding_compatible=compatible,
                          residual_thousand_barrels=float(residual*1000),rounding_bound_thousand_barrels=float(bound*1000),
                          interval_rule='abs(current-prior_inline-published_difference)<=half(sum of three printed quanta)',
                          published_difference_unchanged=True,unit='million_barrels',rounding_evidence_url=ROUNDING_SOURCE)
        found[row[0]]=dict(report_id=report['report_id'],series_label=row[0],data_ending=ending,prior_data_ending=prior_ending,
                          native_unit='million_barrels',normalized_unit='thousand_barrels',unit_conversion_factor=1000,
                          unit_evidence_url=ROUNDING_SOURCE,current=float(current*1000),prior_inline=float(prior*1000),delta=float(delta*1000),
                          raw_current=str(current),raw_prior_inline=str(prior),raw_delta=str(delta),
                          arithmetic_residual_thousand_barrels=float(residual*1000),precision_rounding_bound_thousand_barrels=float(bound*1000),
                          precision_rounding_compatible=compatible,normalization_stage='stage065',source_row_number=rownum,
                          value_status='known_precision_recovered',source_sha256=hashlib.sha256(content).hexdigest(),
                          source_url=report['table1_url'])
    if set(found)!=set(LABELS):raise ValueError('three exact stock labels not present before flow header')
    if not all(x['rounding_compatible'] for x in audit.values()):
        exc=ValueError('at least one stock outside independent printed rounding intervals')
        exc.precision_audit=[audit[k] for k in LABELS]
        raise exc
    return [found[k] for k in LABELS],[audit[k] for k in LABELS]


def recover_normalized_stocks(calendar_reports,original_rows,source_records):
    """Only restore original arithmetic-rejected reports; retain all other identities."""
    output={(r['report_id'],r['series_label']):dict(r) for r in original_rows}
    sources={r['report_id']:r for r in source_records}; audit=[]
    for r in calendar_reports:
        rid=r['report_id']; rec=sources[rid]
        if rec.get('source_status')=='known':continue
        common=dict(scope='report',report_id=rid,original_source_status=rec.get('source_status'),original_parse_error=rec.get('parse_error'))
        eligible=(rec.get('status')==200 and rec.get('source_status')=='unknown_parse_failed' and
                  rec.get('parse_error','').startswith('current-prior does not equal reported Difference:'))
        if not eligible:
            audit.append(dict(common,recovery_status='not_eligible_original_reason'))
            continue
        p=Path(rec['raw_path'])
        if m060.sha(p)!=rec['sha256']:raise ValueError('raw source SHA drift before precision recovery')
        try:
            values,cells=parse_rounded_table1(p.read_bytes(),r)
        except ValueError as exc:
            audit.append(dict(common,recovery_status='retained_unknown_outside_precision_contract',recovery_error=str(exc)))
            audit.extend(dict(x,original_parse_error=rec['parse_error'],recovery_status='retained_unknown_outside_precision_contract') for x in getattr(exc,'precision_audit',[]))
            continue
        for v in values:output[(rid,v['series_label'])]=v
        audit.append(dict(common,recovery_status='recovered',all_three_components_rounding_compatible=True,
                          source_sha256=rec['sha256'],published_values_and_difference_unchanged=True))
        audit.extend(dict(x,original_parse_error=rec['parse_error'],recovery_status='recovered') for x in cells)
    result=[output[(r['report_id'],k)] for r in calendar_reports for k in LABELS]
    return result,audit


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-manifest',required=True,type=Path)
    ap.add_argument('--expected-source-manifest-sha',required=True)
    args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    terminal=OUT/'actual_terminal.json'
    if terminal.exists():raise RuntimeError('Stage065 offline normalization was already attempted')
    state=dict(schema='stage065_offline_precision_terminal_v1',status='running',started_at=datetime.now(timezone.utc).isoformat(),
               normalization_actual_startups=1,offline_normalization_actual_startups=1,new_http_requests=0,source_actual_startups=0,model_fits=0,cash_accounts=0,sql_queries=0,
               original_stage060_unchanged=True,goal_complete=False)
    m060.write_json(terminal,state); start=time.monotonic()
    try:
        if m060.sha(SOURCE060)!=FROZEN060:raise ValueError('frozen060 implementation drifted')
        if m060.sha(args.source_manifest)!=args.expected_source_manifest_sha:raise ValueError('060 manifest binding changed')
        amendment=LINE/'outputs/stage059_eia_full_market_protocol/precision_input_amendment.json'
        if m060.sha(amendment)!='46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729':raise ValueError('precision amendment binding changed')
        source=json.loads(args.source_manifest.read_text())
        if source['status']!='completed':raise ValueError('060 not completed')
        for b in source['artifacts'].values():
            if m060.sha(b['path'])!=b['sha256'] or Path(b['path']).stat().st_size!=b['bytes']:
                raise ValueError('060 artifact binding changed: '+b['path'])
        old_terminal=json.loads(Path(source['artifacts']['actual_terminal']['path']).read_text())
        if old_terminal['status']!='completed' or old_terminal['source_actual_startups']!=1:raise ValueError('060 actual did not finish exactly once')
        state['original060_source_actual_startups']=old_terminal['source_actual_startups']
        reports=pd.read_csv(source['artifacts']['calendar']['path']).to_dict('records')
        original=pd.read_csv(source['artifacts']['normalized_stocks']['path'],dtype={'raw_current':'str','raw_prior_inline':'str','raw_delta':'str'}).to_dict('records')
        src=json.loads(Path(source['artifacts']['source_bindings']['path']).read_text())
        recovered,audit=recover_normalized_stocks(reports,original,src['reports'])
        report_audit=[r for r in audit if r['scope']=='report']
        recovered_ids={r['report_id'] for r in report_audit if r['recovery_status']=='recovered'}
        src65=[]
        for old in src['reports']:
            rec=dict(old,original_source_status=old['source_status'],original_parse_status=old.get('parse_status'),normalization_layer='stage065')
            if old['report_id'] in recovered_ids:
                rec.update(source_status='known_precision_recovered',parse_status='all_three_stocks_compatible_with_independent_rounding')
            src65.append(rec)
        shutil.copyfile(source['artifacts']['calendar']['path'],OUT/'calendar.csv')
        pd.DataFrame(recovered).to_csv(OUT/'normalized_stocks.csv',index=False)
        cal=source['input_bindings']['accepted_china_calendar']
        if m060.sha(cal['path'])!=cal['sha256']:raise ValueError('accepted China calendar changed')
        days=[datetime.strptime(str(int(x)),'%Y%m%d').date().isoformat() for x in np.load(cal['path'],allow_pickle=False)]
        features=m060.make_report_signals(reports,recovered,days)
        events=m060.make_event_map(features)
        features.to_csv(OUT/'report_features.csv',index=False);events.to_csv(OUT/'event_map.csv',index=False)
        pd.DataFrame(audit).to_csv(OUT/'recovery_audit.csv',index=False)
        m060.write_json(OUT/'source_bindings.json',dict(schema='stage065_two_layer_source_bindings_v1',archive=src['archive'],reports=src65,
                                                       original_stage060_manifest=m060.binding(args.source_manifest,'immutable_original_source_actual_manifest')))
        year=features.assign(year=features.release_date.str[:4]).groupby('year').agg(reports=('report_id','size'),stock_missing=('stock_missing','sum'),external_missing=('external_missing','sum')).reset_index()
        year['precision_recovered_reports']=year.year.map(Counter(next(r['release_date'][:4] for r in reports if r['report_id']==rid) for rid in recovered_ids)).fillna(0).astype(int)
        year.to_csv(OUT/'coverage_by_year.csv',index=False)
        known=sum(r['source_status'] in ('known','known_precision_recovered') for r in src65)
        coverage=dict(schema='stage065_offline_precision_coverage_v1',calendar_reports=len(reports),calendar_first=reports[0]['release_date'],calendar_last=reports[-1]['release_date'],
                      original_known_reports=old_terminal['known_reports'],original_unknown_reports=old_terminal['unknown_reports'],precision_recovered_reports=len(recovered_ids),
                      known_reports=known,unknown_reports=len(reports)-known,normalized_stock_rows=len(recovered),
                      scalar_known=int(features.s.notna().sum()),shared_information_known=int(features.external_missing.eq(0).sum()),
                      decision_events=len(events),decision_events_2020plus=int(events.u_date.ge('2020-01-01').sum()),
                      decision_events_shared_known_2020plus=int((events.u_date.ge('2020-01-01') & events.external_missing.eq(0)).sum()),
                      superseded_reports=int(features.superseded_before_first_decision.sum()),pending_after_source_end=int(events.execution_state.eq('pending_after_source_end').sum()),
                      source_failures=[{k:v for k,v in rec.items() if k in ('report_id','status','source_status','parse_error','error','stderr')} for rec in src65 if rec['source_status'] not in ('known','known_precision_recovered')],
                      new_http_requests=0,existing_raw_sources_only=True,all_family_eligibility_unchanged=True,raw_sources_in_git=False,
                      rounding_evidence=dict(url=ROUNDING_SOURCE,note=ROUNDING_NOTE,rule='per-cell Decimal printed quantum; abs residual<=half(sum quanta); preserve published Difference'),
                      calendar_clock_ordinal52_sham_implementation_sha=FROZEN060)
        m060.write_json(OUT/'coverage.json',coverage)
        state.update(status='completed',finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,
                     calendar_reports=len(reports),precision_recovered_reports=len(recovered_ids),known_reports=known,unknown_reports=len(reports)-known)
        m060.write_json(terminal,state)
        files={'calendar':('calendar.csv','unchanged_official_release_calendar'), 'normalized_stocks':('normalized_stocks.csv','normalized_three_inventory_components_with_precision_recovery'),
               'report_features':('report_features.csv','causal_full_calendar_scalar_and_past_sham'), 'event_map':('event_map.csv','unique_decision_date_causal_external_input_all_families'),
               'coverage':('coverage.json','two_layer_source_coverage'), 'coverage_by_year':('coverage_by_year.csv','source_annual_coverage_and_precision_recovery'),
               'source_bindings':('source_bindings.json','two_layer_public_source_status_and_hash_bindings'), 'recovery_audit':('recovery_audit.csv','report_and_cell_printed_precision_residual_bound_and_original_rejection_audit'),
               'actual_terminal':('actual_terminal.json','offline_normalization_actual_terminal'), 'tests_red':('tests_red.log','new_behavior_red_evidence'), 'tests_green':('tests_green.log','new_behavior_green_evidence')}
        manifest=dict(schema='stage060_eia_import_manifest_v1',producer='stage065_eia_precision_recovery',normalization_stage='stage065',status='completed',artifacts={k:m060.binding(OUT/name,role) for k,(name,role) in files.items()},
                      input_bindings=dict(precision_input_amendment=m060.binding(amendment,'frozen_precision_input_correction_contract'),original_stage060_manifest=m060.binding(args.source_manifest,'immutable_original_source_actual_manifest'),
                                          original_stage060_actual=source['artifacts']['actual_terminal'],original_stage060_source_bindings=source['artifacts']['source_bindings'],
                                          original_stage060_implementation=source['input_bindings']['implementation'],original_stage060_tests=source['input_bindings']['tests'],
                                          archive_acquisition=source['input_bindings']['archive_acquisition'],accepted_china_calendar=cal,
                                          protocol=source['input_bindings']['protocol'],frozen_stage060_implementation=m060.binding(SOURCE060,'unchanged_calendar_clock_ordinal52_sham_semantics'),
                                          implementation=m060.binding(__file__,'precision_correction_implementation'),tests=m060.binding(Path(__file__).with_name('test_stage065_eia_precision_recovery.py'),'precision_correction_new_behavior_tests')),
                      source_end=m060.SOURCE_END,new_http_requests=0,all_families_same_event_eligibility=True,
                      raw_source_handling='original Stage060 excluded_raw_sources only; no raw copies or registrations',goal_complete=False)
        m060.write_json(OUT/'manifest.json',manifest)
        print(json.dumps(dict(status='completed',coverage=coverage),ensure_ascii=False))
    except Exception as exc:
        state.update(status='failed',error=repr(exc),finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start)
        m060.write_json(terminal,state)
        raise


if __name__=='__main__':main()
