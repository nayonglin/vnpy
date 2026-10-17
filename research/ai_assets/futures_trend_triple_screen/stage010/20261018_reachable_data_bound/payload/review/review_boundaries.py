"""Four bounded mapping traces and saved-output checks; no closure rerun."""
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage010_reachable_demand'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    summary = json.loads((SOURCE / 'summary.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    assert all(sha(path) == digest for path, digest in inputs.items())
    assert all(sha(SOURCE / name) == digest for name, digest in summary['artifact_sha256'].items())
    demand = read(SOURCE / 'demand.csv')
    transitions = read(SOURCE / 'mandatory_transitions.csv')
    by_key = {(r['vt_symbol'], r['execution_trade_date']): r for r in demand}
    assert len(by_key) == len(demand) == summary['required_sessions'] == 28268
    assert len(transitions) == summary['diagnostics']['mandatory_close_states'] == 472
    assert sum(r['coverage_satisfied'] == 'False' for r in demand) == summary['gap_sessions'] == 23309
    assert sum(r['requirement_kind'] == 'full_session' and r['coverage_satisfied'] == 'False' for r in demand) == 771
    assert sum(r['requirement_kind'] == 'anchor' and r['coverage_satisfied'] == 'False' for r in demand) == 22538
    for row in demand:
        full = row['requirement_kind'] == 'full_session'
        assert (row['coverage_satisfied'] == 'True') == (row['complete' if full else 'anchor_present'] == 'True')
        assert int(row['required_minutes']) == (int(row['expected_minutes']) if full else 1)
        assert int(row['missing_required_minutes']) == (int(row['missing_minutes']) if full else int(row['anchor_present'] == 'False'))
    nonreal = [r for r in demand if r['real_daily_present'] == 'False']
    assert len(nonreal) == 16
    assert all(r['requirement_kind'] == 'anchor' and r['fill_bar_class'] == 'carry_or_missing_real_bar'
               and r['source_validation_required'] == 'True' for r in nonreal)

    signals = LINE / 'outputs/stage005_potential_signal_demand'
    calendar = [r['date'] for r in read(signals / 'global_engine_calendar.csv')]
    positions = {day: i for i, day in enumerate(calendar)}
    mapping = {}
    mapping_path = ROOT / 'examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
    wanted = {'cu.SHFE', 'fu.SHFE', 'SM.CZCE'}
    for row in read(mapping_path):
        if row['continuous_symbol_vt'] in wanted and row['date'] in positions:
            mapping[row['date'], row['continuous_symbol_vt']] = row['main_contract_vt']
    # Hand trace only these short real mapping windows. No implementation enumerate/advance call.
    examples = [('cu.SHFE', 'cu2003.SHFE', '2020-02-17', '2020-02-24', '2020-02-25'),
                ('fu.SHFE', 'fu2005.SHFE', '2020-04-07', '2020-04-14', '2020-04-15'),
                ('SM.CZCE', 'SM306.CZCE', '2023-05-16', '2023-05-25', '2023-05-26'),
                ('SM.CZCE', 'SM101.CZCE', '2020-12-17', '2020-12-24', '2020-12-25')]
    traces = []
    for product, held, first, due_day, fill in examples:
        target_before = None
        elapsed = 0
        trace = []
        for day in calendar[positions[first]:positions[due_day] + 1]:
            target = mapping[day, product]
            assert target and target != held
            elapsed = elapsed + 1 if target == target_before else 0
            trace.append(dict(date=day, target=target, elapsed=elapsed, due=elapsed >= 5))
            target_before = target
        assert not any(r['due'] for r in trace[:-1]) and trace[-1]['due']
        assert calendar[positions[due_day] + 1] == fill
        rows = [r for r in transitions if r['old_contract'] == held and r['signal_date'] == due_day]
        assert len(rows) == 1
        event = rows[0]
        assert event['execution_trade_date'] == fill and event['target_contract'] == trace[-1]['target']
        assert event['old_branch_removed_at_next_batch'] == 'True' and event['reopen_upper_bound'] == 'True'
        assert by_key[held, fill]['need_possible_close'] == 'True'
        new = by_key[event['target_contract'], fill]
        assert new['need_rollover_open'] == 'True' and new['requirement_kind'] == 'full_session'
        assert max(r['execution_trade_date'] for r in demand if r['vt_symbol'] == held) == fill
        traces.append(dict(product=product, held=held, trace=trace, transition=event,
            last_old_contract_demand=fill, next_batch_new_full=True))
    assert traces[1]['transition']['old_signal_real_bar'] == 'False'
    assert next(r for r in traces[2]['trace'] if r['date'] == '2023-05-18')['elapsed'] == 0
    seeds = read(signals / 'c0_potential_initial_events.csv')
    assert any(r['signal_date'] == '2020-12-16' and r['execution_trade_date'] == '2020-12-17'
               and r['vt_symbol'] == 'SM101.CZCE' for r in seeds)
    assert mapping['2020-12-17', 'SM.CZCE'] == 'SM105.CZCE'
    failures = []
    for day in ['2020-05-18', '2020-08-12']:
        row = by_key['rb2010.SHFE', day]
        assert row['need_possible_close'] == 'True' and row['requirement_kind'] == 'anchor'
        failures.append(dict(day=day, abstract_label='possible_close', actual_failed_order_offset='unknown_not_retained'))
    aug = by_key['rb2010.SHFE', '2020-08-12']
    assert aug['stage008_independently_qualified_candidate'] == 'True'
    assert aug['coverage_satisfied'] == 'False' and aug['available_minutes'] == '0'
    pending = read(SOURCE / 'terminal_pending.csv')
    assert len(pending) == 20 and all(r['execution_trade_date'] == '' for r in pending)
    assert sum(r['reason'] == 'initial_open' for r in pending) == 1
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_static_and_four_mapping_boundary_review_pass_conditional_overapproximation',
        p0_findings=0, p1_findings=0, network_calls=0, financial_replays=0, indicator_streams_repeated=0,
        full_state_closure_repeated=False, full_minute_or_account_audits_repeated=False,
        current_input_SHA_checked=len(inputs), source_summary_sha256=sha(SOURCE / 'summary.json'),
        source_input_manifest_sha256=sha(SOURCE / 'input_manifest.json'),
        saved_output_unique_demands=28268, saved_output_gaps=23309,
        initial_seeds_nonterminal=700, terminal_pending_demands=20,
        independent_short_mapping_traces=traces, reset_real_trace='SM306 May16 targetSM307, May18 targetSM309 resets elapsed0; dueMay25/fillMay26',
        return_to_held_clear_scope='static advance branch matches source; no separate real reversion sentinel claimed',
        no_real_fill_bar_constraints=16, no_real_rows_all_anchor_and_constraint_labeled=True,
        constraint_contracts=sorted({r['vt_symbol'] for r in nonreal}),
        known_failed_anchors_now_in_bound=failures, abstract_close_label_does_not_prove_failed_order_type=True,
        Stage008_candidate_annotation_only=True,
        source_scope='Stage005 frozen pure-alpha initial seeds plus current mapping and Stage004 real-bar flags; inherited earlier limited reviews',
        conditional_upper_bound='flat cold start; reverse/all three adds off; ignore optional exits, shape, funds and AI; old state removed next batch conditional on strict execution being possible',
        actual_trades_proven=False, all_prices_qualified=False, full_feasible_candidate_path_proven=False,
        download_authorized=False, C0_attempt3_authorized=False, production_qualified=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1, C0_alpha_verdict='not_evaluable',
        overfitting=False, continued_value=True)
    (DEST / 'boundary_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'saved_output_unique_demands', 'no_real_fill_bar_constraints',
        'current_input_SHA_checked', 'full_state_closure_repeated']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
