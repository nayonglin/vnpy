"""Complete Stage157 report metadata only; never import or run a cash engine.

The original failed terminal, author sources, four actual books, saved metrics
and saved CI stay immutable. Root invokes this once with this exact source SHA.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

LINE=Path(__file__).resolve().parent.parent
PROTOCOL_SHA='7ec4f92b31b46b04e0a17812878acb7f6305c9c476f9350d84bb7d873fe11e47'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
LEDGERS=('fills','reservations','daily','positions','closed','open','capacity_audit','entry_execution_unknown','rejections')
JSON_NAMES={'largest_wins_losses','diagnostics','continuation_gate','signal_identification','budget_and_tick_disclosure','source_read_receipt'}
OUTPUT_NAMES=('comparisons','bootstrap_distributions','account_summaries','family_year_including_zero',
    'family_total_including_zero','annual_slices','capacity_summary','sector_variant_attribution',
    'sector_variant_year_including_zero',*sorted(JSON_NAMES))


def binding(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(b):
    path=Path(b['path']);raw=path.read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
        raise ValueError('immutable binding differs '+str(path))
    return json.loads(raw)


def write(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False);stream.write('\n')


def build_disclosure(protocol,execution):
    # Stage128 puts anchor_and_execution at top level, capacity inside cash.
    return dict(policy='NARROW',kernel='unchanged accepted131',budget=protocol['cash'],
        capacity=execution['cash']['capacity'],anchor=execution['anchor_and_execution'],
        bootstrap_indices=protocol['statistics']['indices'],bootstrap_indices_regenerated=False,
        fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,
        no_actual_orderbook_execution_proof=True,legal_clearance_proved=False,source_archive_is_final_reconstruction=True,
        voluntary_generic_kernel_reason='lifecycle_exit; see source/voluntary/effective sidecar',
        goal_complete=False,production_qualified=False,increased_betting_qualified=False,
        report_only_continuation=True,original_report_error="KeyError: 'anchor_and_execution'",
        financial_outputs_recomputed=False)


def execute(args):
    own=binding(__file__)
    if own['sha256']!=args.source_sha256:raise ValueError('exact finalizer source SHA required')
    out=Path(args.output).resolve()
    if LINE/'outputs/stage157_voluntary_cash' not in out.parents or not out.is_dir():
        raise ValueError('existing Stage157 actual output required')
    new_names=('budget_and_tick_disclosure.json','manifest.json','metadata_continuation_started.json','metadata_continuation_terminal.json')
    if any((out/n).exists() for n in new_names):raise FileExistsError('metadata continuation is once-only')
    started_binding=binding(out/'actual_started.json');started=read_bound(started_binding)
    original_terminal_binding=binding(out/'actual_terminal.json');original_terminal=read_bound(original_terminal_binding)
    if (original_terminal.get('status')!='failed' or original_terminal.get('exit_code')!=1
            or original_terminal.get('error')!="KeyError: 'anchor_and_execution'"
            or original_terminal.get('new_cash_accounts')!=4 or original_terminal.get('cash_accounts_started')!=4
            or original_terminal.get('native_source_queries')!=0 or original_terminal.get('actual_model_fit_calls')!=0):
        raise ValueError('only exact report-field failure after four completed accounts is eligible')
    auth=read_bound(started['authorization']);protocol=read_bound(started['protocol']);inputs=auth['input_bindings']
    if (started['protocol']['sha256']!=PROTOCOL_SHA or auth.get('output')!=str(out)
            or auth.get('authorized_by')!='root' or auth.get('stage')!='cash'
            or auth.get('source_bundle')!=started['source_bundle']):
        raise ValueError('original exact root authorization differs')
    for source in started['source_bundle']:
        if binding(source['path'])!=source:raise ValueError('original actual author/source changed')
    execution=read_bound(inputs['execution_protocol'])
    disclosure=build_disclosure(protocol,execution)
    baseline_books=read_bound(binding(out/'baseline_references.json'))
    if baseline_books!=protocol['cash']['read_only_control_books']:
        raise ValueError('saved read-only controls differ from frozen155')
    accounts=[]
    for window in WINDOWS:
        for cost in COSTS:
            name=f'NARROW_VOLUNTARY_RESELECT_{window}_{cost}';folder=out/name
            ledgers={role:binding(folder/(role+'.csv.gz')) for role in LEDGERS}
            sb=binding(folder/'summary.json');summary=read_bound(sb)
            if summary.get('account')!=name or summary.get('arm')!='VOLUNTARY_RESELECT' or summary.get('window')!=window or summary.get('cost')!=cost:
                raise ValueError('saved complete account identity differs '+name)
            accounts.append(dict(arm='VOLUNTARY_RESELECT',window=window,cost=cost,account_id=name,
                directory=str(folder),summary=sb,ledgers=ledgers))
    # Check required pre-existing outputs by identity only; do not parse/recompute
    # a ledger, equity curve, selection, outcome, bootstrap sample or CI.
    for name in OUTPUT_NAMES:
        if name=='budget_and_tick_disclosure':continue
        binding(out/(name+('.json' if name in JSON_NAMES else '.csv.gz')))
    for name in ('signals_VOLUNTARY_RESELECT.csv.gz','boundary_lineage.csv.gz'):
        binding(out/name)
    baseline_manifest=read_bound(inputs['accepted_cash_manifest'])
    old_fy=[a for a in baseline_manifest['artifacts'] if a.get('logical_name')=='family_year_including_zero.csv.gz']
    if len(old_fy)!=1:raise ValueError('accepted old family-year artifact missing')
    old_fy_binding={k:old_fy[0][k] for k in ('path','bytes','sha256')}
    preserved=[binding(p) for p in sorted(out.rglob('*')) if p.is_file()]
    began,clock=datetime.now(timezone.utc).isoformat(),time.monotonic()
    finalizer_sources=[own,binding(Path(__file__).with_name('test_stage157_voluntary_finalize.py'))]
    write(out/'metadata_continuation_started.json',dict(schema='stage157_metadata_continuation_started_v1',
        status='started',started_at=began,authorized_by='root_exact_source_invocation',
        original_actual_started=started_binding,original_actual_terminal=original_terminal_binding,
        source_bundle=finalizer_sources,all_original_artifact_bindings=preserved,
        new_cash_accounts=0,actual_model_fit_calls=0,native_source_queries=0,financial_recalculations=0))
    try:
        write(out/'budget_and_tick_disclosure.json',disclosure)
        for b in preserved:
            if binding(b['path'])!=b:raise ValueError('original output changed during metadata completion')
        write(out/'metadata_continuation_terminal.json',dict(schema='stage157_metadata_continuation_terminal_v1',
            status='completed',exit_code=0,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,new_cash_accounts=0,reused_completed_cash_accounts=4,
            actual_model_fit_calls=0,native_source_queries=0,financial_recalculations=0,bootstrap_recalculations=0,
            original_financial_outputs_unchanged=True,original_failed_terminal_preserved=True,
            original_actual_terminal=original_terminal_binding,original_artifact_count=len(preserved),
            exact_reporting_fix="execution['anchor_and_execution'] at top level",
            goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        artifacts=[dict(binding(p),logical_name=str(p.relative_to(out)),role='decision_asset',
            feature_schema='stage157_voluntary_cash_v1',raw_ohlc=False,reproducibility_required=True)
            for p in sorted(out.rglob('*')) if p.is_file()]
        terminal_binding=binding(out/'metadata_continuation_terminal.json')
        manifest=dict(schema='stage157_voluntary_cash_v1',status='completed_with_metadata_continuation',mode='actual',
            protocol=started['protocol'],protocol_sha256=PROTOCOL_SHA,authorization=started['authorization'],
            source_bundle=started['source_bundle'],input_bindings=inputs,terminal=terminal_binding,
            original_actual_terminal=original_terminal_binding,financial_actual_terminal=original_terminal_binding,
            metadata_continuation_started=binding(out/'metadata_continuation_started.json'),
            metadata_continuation_terminal=terminal_binding,metadata_continuation_source_bundle=finalizer_sources,
            artifacts=artifacts,accounts=accounts,signals=binding(out/'signals_VOLUNTARY_RESELECT.csv.gz'),
            boundary_lineage=binding(out/'boundary_lineage.csv.gz'),baseline_books=baseline_books,
            control_family_year_source=old_fy_binding,bootstrap_indices=protocol['statistics']['indices'],
            new_cash_accounts=4,native_source_queries=0,actual_model_fit_calls=0,new_labels=0,
            old_baseline_replays=0,old_control_cash_replays=0,metadata_continuation_new_cash_accounts=0,
            financial_recalculations=0,original_financial_outputs_unchanged=True,
            goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        for name in OUTPUT_NAMES:
            manifest[name]=binding(out/(name+('.json' if name in JSON_NAMES else '.csv.gz')))
        write(out/'manifest.json',manifest)
        return dict(status=manifest['status'],output=str(out),new_cash_accounts=0,reused_completed_cash_accounts=4,
            financial_recalculations=0,manifest=binding(out/'manifest.json'))
    except BaseException as exc:
        if not (out/'metadata_continuation_terminal.json').exists():
            write(out/'metadata_continuation_terminal.json',dict(status='failed',exit_code=1,
                error=f'{type(exc).__name__}: {exc}',new_cash_accounts=0,financial_recalculations=0,
                original_actual_terminal=original_terminal_binding))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--source-sha256',required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
