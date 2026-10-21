"""Stage110 NFC category experiment: eight fresh main-scope NARROW cash accounts.

Only supplied main scores enter accepted070's original reserve/quote/ledger
implementation. Imports and synthetic tests do not read native data, fit a
model, create labels, or replay an actual account. Exact root authorization and
a fresh output directory are required for the single shared native read.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '80b9eb2f8e959fb61218b92c3c35049a3f5084817d784c211ece2fc5970a81bc'
DEPENDENCIES = {
    'stage070_narrow_policy_cash.py': '5ed1461fb137854f5a6d7c20d1f3ea25306cd3fc9b8b1646fbc767e786387ecb',
    'stage070_policy_kernel.py': 'ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe',
    'stage042_cross_session_experiment.py': 'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d',
    'stage054_maturity_cash_compare.py': 'f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd',
}
for _name, _sha in DEPENDENCIES.items():
    if hashlib.sha256((TOOLS/_name).read_bytes()).hexdigest() != _sha:
        raise ValueError('accepted pure dependency changed '+_name)
_spec = importlib.util.spec_from_file_location('stage113_accepted070', TOOLS/'stage070_narrow_policy_cash.py')
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)
kernel, ref, diagnostics = helpers.kernel, helpers.ref, helpers.diagnostics
ARMS = ('CONTROL', 'NFC')
WINDOWS = ('primary_2020', 'cold_2023')
COSTS = ('base', 'stress')


FIXED_INPUTS = {
    'market_protocol': dict(path=str(LINE/'outputs/stage052_maturity_information_cash_protocol/protocol.json'), bytes=11987,
        sha256='968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c'),
    'narrow_labels': dict(path=str(LINE/'outputs/stage070_narrow_policy_cash/labels/labels_narrow.csv.gz'), bytes=61463237,
        sha256='26dda06208f49c4e4d04eb3e9b06379406338c7bc264906ec5ad160f6d0dbca3'),
    'narrow_manifest': dict(path=str(LINE/'outputs/stage070_narrow_policy_cash/labels/manifest.json'), bytes=5279,
        sha256='23fcf336abc9b9a2a405f5372333264bb82c03e8e82409310c66ed7c423f748a'),
}
BOOTSTRAP_INDICES = {
    'primary_2020': dict(path=str(LINE/'outputs/stage070_narrow_policy_cash/cash/primary_2020_bootstrap_indices.npy'), bytes=13144128,
        sha256='1991a9ba4cb6d71c17e08a639bf3e38c49d8c317e035b49c7ca9359ee0467ea3'),
    'cold_2023': dict(path=str(LINE/'outputs/stage070_narrow_policy_cash/cash/cold_2023_bootstrap_indices.npy'), bytes=7320128,
        sha256='957dd6dc9cedc126fe8d517daf698aae68876721c725ce6c338f36433157c9fc'),
}


def make_signals(labels, predictions, arm):
    """external missing and future label states never become an execution gate."""
    if arm not in ARMS or set(predictions.scope) != {'main'}:
        raise ValueError('only main CONTROL/NFC predictions may enter cash')
    if set(predictions.policy) != {'NARROW'} or not set(predictions.arm).issubset(ARMS):
        raise ValueError('fixed NARROW CONTROL/NFC predictions required')
    chosen = predictions.loc[predictions.arm.eq(arm)]
    if not chosen.external_missing.isin([0, 1]).all():
        raise ValueError('binary external missing required')
    result = helpers.make_signals(labels, predictions, 'NARROW', arm)
    result = result.merge(chosen[['event_id', 'external_missing']], on='event_id', how='left', validate='one_to_one')
    result['arm'], result['policy'] = arm, 'NARROW'
    return result


def validate_shared_missing(predictions):
    if set(predictions.arm) != set(ARMS) or predictions.duplicated(['arm', 'event_id']).any():
        raise ValueError('both unique main arms required for shared external missing')
    values = predictions.pivot(index='event_id', columns='arm', values='external_missing')
    if not values.isin([0, 1]).all().all() or not values.NFC.eq(values.CONTROL).all():
        raise ValueError('shared external missing differs across arms')


def paired_statistics(active, control, indices):
    """Use the prebound source-calendar index matrix; never regenerate it."""
    index = np.asarray(indices)
    if (index.ndim != 2 or index.shape[0] == 0 or index.shape[1] != len(active)
            or index.dtype.kind not in 'iu' or index.min() < 0 or index.max() >= len(active)):
        raise ValueError('bootstrap index shape/type/range differs from paired source calendar')
    return helpers.paired_statistics(active, control, index)


def continuation_gate(points, held, any_stale, *, wealth_positive, signal_unknown_main=False):
    """Frozen cash nominal conditions and separate signal identification limits."""
    lookup = {(p['window'], p['cost']): p for p in points}
    if len(points) != 4 or set(lookup) != {(w, c) for w in WINDOWS for c in COSTS}:
        raise ValueError('all four fixed cash comparisons required')
    groups = held.get('groups', {})
    if set(groups) != {'holdout_0', 'holdout_1'}:
        raise ValueError('both held diagnostics required; held models never enter cash')
    returns = (lookup[('primary_2020', 'stress')]['return_percentage_point_difference'] > 0 and
               all(p['return_percentage_point_difference'] >= 0 for k, p in lookup.items()
                   if k != ('primary_2020', 'stress')))
    dds = [p['drawdown_percentage_point_difference'] for p in points]
    dd_known = all(v is not None and np.isfinite(v) for v in dds)
    dd_no_deeper = all(v >= 0 for v in dds if v is not None and np.isfinite(v))
    primary = lookup[('primary_2020', 'stress')]
    ci = primary.get('ci95_low')
    ci_pass = ci is not None and np.isfinite(ci) and ci > 0
    own_returns = all(p.get('active_total_return_pct') is not None and np.isfinite(p['active_total_return_pct'])
                      and p['active_total_return_pct'] > 0 for p in points)
    cash_nominal = bool(returns and dd_known and dd_no_deeper and ci_pass and own_returns and wealth_positive)
    held_nominal = all(g.get('nominal_pass') is True for g in groups.values())
    held_unknown = any(g.get('unknown_differential_selected_events', 0) > 0 or g.get('status') == 'unknown'
                       for g in groups.values())
    if all(p['identification'] == 'all_empty_unidentified' for p in points):
        status = 'all_empty_unidentified'
    elif not (returns and dd_no_deeper and ci_pass and held_nominal and own_returns and wealth_positive):
        status = 'unsupported'
    elif not dd_known:
        status = 'unknown_empty_reference_DD'
    elif any_stale:
        status = 'unknown_historical_stale'
    elif held_unknown:
        status = 'unknown_differential_held_outcome'
    else:
        status = 'supported_research_model_only'
    return dict(status=status, cash_nominal_pass=cash_nominal, held_known_nominal_pass=bool(held_nominal),
                NFC_own_returns_positive_in_all_four=bool(own_returns), actual_wealth_positive=bool(wealth_positive),
                nominal_pass=bool(cash_nominal and held_nominal), financial_unknown=bool(any_stale or not dd_known),
                signal_unknown_main=bool(signal_unknown_main), held_signal_unknown=bool(held_unknown),
                signal_label_uncertainty_is_not_cash_exposure=True, goal_complete=False,
                production_qualified=False, increased_betting_qualified=False,
                independent_actual_review_required=True, no_automatic_promotion=True)


def source_bundle():
    names = list(DEPENDENCIES)+['stage113_member_category_cash.py', 'test_stage113_member_category_cash.py']
    return sorted([ref.file_binding(TOOLS/name) for name in names], key=lambda b: b['path'])


def same_binding(actual, expected, role):
    if not isinstance(actual, dict) or any(actual.get(k) != expected.get(k) for k in ('path', 'bytes', 'sha256')):
        raise ValueError('binding differs '+role)


def authorize(args):
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError('fresh output required; failure is retained, no automatic retry '+str(output))
    protocol_binding = ref.file_binding(args.protocol)
    if args.protocol_sha256 != PROTOCOL_SHA or protocol_binding['sha256'] != PROTOCOL_SHA:
        raise ValueError('exact Stage110 protocol SHA required')
    protocol = json.loads(ref.read_bound(protocol_binding))
    if (protocol.get('stage') != 110 or protocol.get('line_id') != LINE.name
            or protocol.get('kind') != 'fixed_information_increment_experiment'):
        raise ValueError('Stage110 protocol identity differs')
    authorization_binding = ref.file_binding(args.authorization)
    authorization = json.loads(ref.read_bound(authorization_binding))
    required = dict(schema='stage110_exact_root_authorization_v1', authorized_by='root', stage='cash',
                    exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, output=str(output))
    if any(authorization.get(k) != v for k, v in required.items()):
        raise ValueError('exact root source/protocol/fresh output authorization required')
    if sorted(authorization.get('source_bundle', []), key=lambda b: b['path']) != source_bundle():
        raise ValueError('root authorized source bundle differs from current source/tests')
    inputs = authorization.get('input_bindings', {})
    if set(inputs) != {'market_protocol', 'narrow_labels', 'narrow_manifest', 'fit_manifest', 'predictions_main', 'held_diagnostic'}:
        raise ValueError('cash requires exactly market, narrow, completed112 main and held diagnostic bindings')
    for role, binding in FIXED_INPUTS.items():
        same_binding(inputs[role], binding, role)
    if (protocol['cash']['initial_equity'], protocol['cash']['single_family_risk'], protocol['cash']['total_planned_risk'],
        protocol['cash']['buffered_margin_cap'], protocol['cash']['margin_buffer']) != (
            ref.INITIAL, ref.SINGLE_RISK, ref.TOTAL_RISK, ref.MARGIN_CAP, ref.MARGIN_BUFFER):
        raise ValueError('accepted070 cash constants differ')
    market = json.loads(ref.read_bound(inputs['market_protocol']))
    ref.assert_db_binding(market['database'])
    return protocol, protocol_binding, authorization, authorization_binding


def validate_cash_manifests(narrow, fit, inputs):
    if (narrow.get('schema') != 'stage070_narrow_labels_v1' or narrow.get('status') != 'completed'
            or narrow.get('mode') != 'actual' or narrow.get('mother_rows') != 399252
            or narrow.get('protocol', {}).get('sha256') != kernel.PROTOCOL_SHA):
        raise ValueError('accepted070 complete narrow label manifest required')
    same_binding(narrow['labels_narrow'], inputs['narrow_labels'], 'narrow manifest labels')
    same_binding(narrow['input_bindings']['market_protocol'], inputs['market_protocol'], 'narrow market bridge')
    if (fit.get('schema') != 'stage112_member_category_fit_v1' or fit.get('status') != 'completed' or fit.get('mode') != 'actual'
            or fit.get('protocol', {}).get('sha256') != PROTOCOL_SHA or fit.get('protocol_sha256') != PROTOCOL_SHA
            or fit.get('actual_fit_calls_completed') != 12 or fit.get('native_source_queries') != 0
            or fit.get('cash_replays') != 0 or fit.get('prediction_rows') != 644056
            or fit.get('cash_eligible') is not True):
        raise ValueError('completed actual112 12fit/zero native/zero cash manifest required')
    for role in ('predictions_main', 'held_diagnostic'):
        same_binding(fit[role], inputs[role], '112 '+role)
    for role in ('narrow_labels', 'narrow_manifest'):
        same_binding(fit['input_bindings'][role], inputs[role], '112 '+role)
    terminal = json.loads(ref.read_bound(fit['terminal']))
    if (terminal.get('status') != 'completed' or terminal.get('exit_code') != 0
            or terminal.get('actual_fit_calls_attempted') != 12 or terminal.get('actual_fit_calls_completed') != 12
            or terminal.get('native_source_queries') != 0
            or terminal.get('cash_replays') != 0):
        raise ValueError('112 actual terminal incomplete or budget differs')
    terminal = json.loads(ref.read_bound(narrow['terminal']))
    if (terminal.get('status') != 'completed' or terminal.get('exit_code') != 0
            or terminal.get('completed_label_rows') != 399252 or terminal.get('native_source_queries') != 1
            or terminal.get('new_cash_accounts') != 0):
        raise ValueError('accepted070 label terminal incomplete')


def main_signal_diagnostics(labels, predictions, end):
    columns = ['event_id', 'family_id', 'u_date', 'label_state', 'label_known_date', 'net_R_stress']
    full = labels[columns].merge(predictions.pivot(index='event_id', columns='arm', values='selected'),
                                 on='event_id', validate='one_to_one', how='inner')
    full['actions_differ'] = full.NFC.ne(full.CONTROL)
    full['closed_known'] = (full.label_state.eq('closed_complete_bar_model') & np.isfinite(full.net_R_stress)
                            & full.label_known_date.fillna('').ne('') & full.label_known_date.fillna('').le(end))
    full['known_nonparticipation'] = full.label_state.eq('known_nonparticipation')
    full['year'] = full.u_date.str[:4]
    states = full.groupby(['year', 'label_state'], dropna=False).agg(
        rows=('event_id', 'size'), action_disagreements=('actions_differ', 'sum'),
        CONTROL_selected=('CONTROL', 'sum'), NFC_selected=('NFC', 'sum'), closed_known=('closed_known', 'sum')).reset_index()
    return dict(main_prediction_rows_per_arm=len(full), full_mother_rows=len(labels),
                full_mother_label_states={str(k): int(v) for k, v in labels.label_state.value_counts(dropna=False).items()},
                unknown_differential_selected_events=int((full.actions_differ & ~full.closed_known & ~full.known_nonparticipation).sum()),
                known_nonparticipation_differential_selected_events=int((full.actions_differ & full.known_nonparticipation).sum()),
                unfilled_signal_label_uncertainty_is_not_cash_exposure=True), states


def comparisons(summaries, daily, indices):
    points, distributions = [], {}
    for window in WINDOWS:
        for cost in COSTS:
            active, control = ('NFC', window, cost), ('CONTROL', window, cost)
            point = helpers.compare_points(summaries[active], summaries[control])
            statistics, dist = paired_statistics(daily[active], daily[control], indices[window])
            name = window+'_'+cost+'_NFC_minus_CONTROL'
            points.append(dict(window=window, cost=cost, contrast='NFC_minus_CONTROL',
                               active_total_return_pct=summaries[active]['total_return_pct'],
                               reference_total_return_pct=summaries[control]['total_return_pct'],
                               **point, **statistics))
            distributions[name] = dist
    return points, distributions


def add_family_costs(family_year, book):
    family_year = family_year.copy()
    fills = pd.DataFrame(book['fills'])
    if len(fills):
        fills['year'] = fills.date.str[:4]
        costs = fills.groupby(['family_id', 'year']).agg(slippage=('slippage', 'sum'),
                    fill_count=('qty', 'size'), filled_qty=('qty', 'sum')).reset_index()
        family_year = family_year.merge(costs, on=['family_id', 'year'], how='left', validate='one_to_one')
    else:
        family_year['slippage'], family_year['fill_count'], family_year['filled_qty'] = 0., 0, 0
    return family_year.fillna({'slippage': 0., 'fill_count': 0, 'filled_qty': 0})


def select_native_cases(selections, book, account, arm):
    roots = {r['root_id']: r for r in book['closed_episodes']+book['open_episodes']}
    for fill in book['fills']:
        if fill['side'] != 'SELL':
            continue
        root = roots[fill['root_id']]
        reason = fill['reason']
        kind = ('entry_day_stop' if reason in ('stop_boundary', 'gap_stop') and fill['date'] == root['entry_date']
                else 'later_boundary' if reason == 'stop_boundary' else 'gap_stop' if reason == 'gap_stop'
                else 'old_epoch_exit' if reason == 'liquidity_reference_changed'
                else 'lifecycle_exit' if reason == 'lifecycle_exit'
                else 'deferred_exit' if reason == 'research_deferred_liquidation' else None)
        if kind is not None:
            selections.setdefault((arm, kind), dict(kind=kind, policy='NARROW', arm=arm,
                  event_id=fill['event_id'], date=fill['date'], account=account, fill=fill))
    for position in book['position_days']:
        if position['mark_state'] == 'stale':
            selections.setdefault((arm, 'missing'), dict(kind='missing', policy='NARROW', arm=arm,
                 event_id=position['event_id'], date=position['date'], account=account, position=position))


def execute(args):
    protocol, protocol_binding, authorization, authorization_binding = authorize(args)
    inputs = authorization['input_bindings']
    narrow = json.loads(ref.read_bound(inputs['narrow_manifest']))
    fit = json.loads(ref.read_bound(inputs['fit_manifest']))
    validate_cash_manifests(narrow, fit, inputs)
    labels, predictions = (helpers.read_table(inputs[role]) for role in ('narrow_labels', 'predictions_main'))
    held = json.loads(ref.read_bound(inputs['held_diagnostic']))
    if len(labels) != 399252 or labels.product_id.nunique() != 98 or labels.family_id.nunique() != 95:
        raise ValueError('complete399252 mother/98 products/95 families required')
    if len(predictions) != 322028 or set(predictions.scope) != {'main'}:
        raise ValueError('two main arms of161014 complete forward predictions required')
    validate_shared_missing(predictions)
    signals = {arm: make_signals(labels, predictions, arm) for arm in ARMS}
    signal_report, signal_states = main_signal_diagnostics(labels, predictions, '2026-10-16')
    indices = {w: np.load(io.BytesIO(ref.read_bound(BOOTSTRAP_INDICES[w])), allow_pickle=False) for w in WINDOWS}
    if any(a.ndim != 2 or a.shape[0] != 2000 for a in indices.values()):
        raise ValueError('prebound2000 bootstrap index rows required')
    if ref.NATIVE_QUERIES:
        raise ValueError('native input already consumed in this process')
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    began, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    source_before = source_bundle()
    status, error, started, completed = 'failed', None, 0, 0
    ref.write_json(out/'actual_started.json', dict(status='started', stage='cash', started_at=began,
           source_bundle=source_before, authorization=authorization_binding, protocol=protocol_binding,
           authorized_new_cash_accounts=8, authorized_native_queries=1, fixture=False))
    try:
        panel, market, dates, economics, _, receipt, market_protocol = kernel.load_market_bridge(authorization)
        ref.write_json(out/'source_read_receipt.json', receipt)
        summaries, daily, reports, family_tables, all_budgets, native_selections = {}, {}, {}, [], [], {}
        families = sorted(panel.product_id.map(ref.family).unique())
        for arm in ARMS:
            sig = signals[arm]
            prepared = ref.organize(sig)
            for window_id, bounds in protocol['cash']['windows'].items():
                start, end = (int(np.searchsorted(dates, value)) for value in bounds)
                if end >= len(dates) or dates[end] != bounds[1] or start >= len(dates):
                    raise ValueError('fixed window source calendar absent')
                if indices[window_id].shape != (2000, end-start+1):
                    raise ValueError('prebound bootstrap index calendar width differs')
                for cost in COSTS:
                    name = f"NARROW_{arm}_{window_id}_{cost}"
                    started += 1
                    book = kernel.run_cash_account(sig, market, dates, economics, cost, name, start, end,
                                                   prepared=prepared, policy='NARROW')
                    completed += 1
                    account_dir = out/name
                    account_dir.mkdir()
                    for file, key in [('fills', 'fills'), ('reservations', 'budgets'), ('daily', 'daily'),
                                      ('positions', 'position_days'), ('closed', 'closed_episodes'), ('open', 'open_episodes')]:
                        ref.write_table(account_dir/(file+'.csv.gz'), book[key], helpers.EMPTY_COLUMNS.get(key, []))
                    ref.write_table(account_dir/'rejections.csv.gz', [r for r in book['budgets'] if r.get('D_qty', 0) == 0], helpers.EMPTY_COLUMNS['budgets'])
                    summary, report, family_year = helpers.cash_report(book, families, ref.INITIAL)
                    key = (arm, window_id, cost)
                    summaries[key], daily[key], reports[name] = summary, pd.DataFrame(book['daily']), report
                    family_year = add_family_costs(family_year, book)
                    family_tables.append(family_year.assign(arm=arm, window=window_id, cost=cost))
                    all_budgets.extend(book['budgets'])
                    select_native_cases(native_selections, book, name, arm)
                    ref.write_json(account_dir/'summary.json', kernel.safe(summary))
                    print(json.dumps(dict(phase='account_complete', account=name, completed=completed,
                                          elapsed_seconds=time.monotonic()-clock)), flush=True)
        if started != 8 or completed != 8 or ref.NATIVE_QUERIES != 1:
            raise AssertionError('finite8 cash/one native budget differs')
        points, distributions = comparisons(summaries, daily, indices)
        ref.write_table(out/'comparisons.csv.gz', points, [])
        ref.write_table(out/'bootstrap_distributions.csv.gz', pd.DataFrame(distributions), [])
        family_year = pd.concat(family_tables, ignore_index=True)
        ref.write_table(out/'family_year_including_zero.csv.gz', family_year, [])
        ref.write_table(out/'family_total_including_zero.csv.gz', family_year.groupby(
            ['arm', 'window', 'cost', 'family_id'])[['net_equity_contribution', 'fee', 'slippage', 'fill_count', 'filled_qty']].sum().reset_index(), [])
        ref.write_table(out/'annual_slices.csv.gz', [dict(account=a, **r) for a, report in reports.items() for r in report['annual_slices']], [])
        ref.write_table(out/'account_summaries.csv.gz', [dict(arm=k[0], window=k[1], cost=k[2], **v) for k, v in summaries.items()], [])
        ref.write_json(out/'diagnostics.json', kernel.safe(reports))
        ref.write_json(out/'signal_identification.json', kernel.safe(dict(main=signal_report, held_binding=inputs['held_diagnostic'],
                       held_groups=held['groups'], label_unknown_not_a_cash_gate=True)))
        ref.write_table(out/'main_signal_states.csv.gz', signal_states, [])
        kernel.export_native_cases(out/'finite_native_cases.json.gz', list(native_selections.values()),
                                   {'NARROW': labels}, panel, market, dates, economics)
        stale = any(report['stale_days'] > 0 for report in reports.values())
        wealth_positive = all(np.isfinite(frame.equity).all() and frame.equity.gt(0).all()
                              and not frame.ever_insolvent.any() for frame in daily.values())
        gate = continuation_gate(points, held, stale, wealth_positive=wealth_positive,
                    signal_unknown_main=signal_report['unknown_differential_selected_events'] > 0)
        ref.write_json(out/'continuation_gate.json', kernel.safe(dict(gate, any_historical_stale=stale)))
        ready = labels.label_history_ready20.eq(1)
        ref.write_json(out/'budget_and_tick_disclosure.json', kernel.safe(dict(
            policy='NARROW', ready_rows=int(ready.sum()), known_tick_rows=int((ready & labels.tick_size.gt(0)).sum()),
            stop_distance_below_tick=int((ready & labels.R0_points.lt(labels.tick_size)).sum()),
            risk_unit='0.25*N*M+roundtrip_fee+two_adverse_slippages; frozen actual D risk while held',
            budget_rules='accepted070 original u joint fractional reserve/floor; D own cap reduce only; no reallocation or same-day sale funding',
            reservation_records=len(all_budgets), continuous_boundary_not_necessarily_tick_order=True,
            no_gap_loss_cap=True, normal_open_close_mark_is_frozen_research_valuation=True,
            zero_price_scenarios_are_not_universal_loss_bounds=True,
            bootstrap_indices=BOOTSTRAP_INDICES, bootstrap_indices_regenerated=False,
            normal_open_not_automatically_financial_unknown=True)))
        ref.assert_db_binding(market_protocol['database'])
        if source_bundle() != source_before:
            raise ValueError('source changed during113 actual')
        status = 'completed'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        ref.write_json(out/'actual_terminal.json', dict(status=status, stage='cash', started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status == 'completed' else 1, error=error, native_source_queries=ref.NATIVE_QUERIES,
            cash_accounts_started=started, new_cash_accounts=completed, actual_model_fit_calls=0,
            downloads=0, new_labels=0, whole_database_hashes=0, old_baseline_replays=0, fixture=False, python=sys.executable))
    artifacts = [dict(ref.file_binding(p), logical_name=str(p.relative_to(out)),
                     role='qualification_evidence' if p.name == 'finite_native_cases.json.gz' else 'decision_asset',
                     feature_schema='stage113_member_category_cash_v1', raw_ohlc=p.name == 'finite_native_cases.json.gz',
                     reproducibility_required=p.name != 'finite_native_cases.json.gz') for p in sorted(out.rglob('*')) if p.is_file()]
    ref.write_json(out/'manifest.json', dict(schema='stage113_member_category_cash_v1', status=status, mode='actual',
        protocol=protocol_binding, authorization=authorization_binding,
        input_bindings=inputs, source_bundle=source_before, bootstrap_indices=BOOTSTRAP_INDICES,
        terminal=ref.file_binding(out/'actual_terminal.json'), artifacts=artifacts,
        new_cash_accounts=completed, native_source_queries=ref.NATIVE_QUERIES, actual_model_fit_calls=0,
        new_labels=0, old_baseline_replays=0, goal_complete=False, production_qualified=False))
    return dict(status=status, output=str(out), native_source_queries=ref.NATIVE_QUERIES, new_cash_accounts=completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'protocol-sha256', 'authorization', 'output'):
        parser.add_argument('--'+name, required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
