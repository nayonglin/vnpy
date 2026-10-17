"""Bounded original-method/SQL-window review. Never enumerate the account stream."""
from pathlib import Path
from datetime import datetime
import ast
import csv
import gzip
import hashlib
import inspect
import json
import os
import sqlite3
import sys
import textwrap

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage005_potential_signal_demand'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'
sys.path.insert(0, str(LINE / 'tools'))
import stage005_potential_signal_demand as implementation


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pure_method_closure(base):
    names, queue = set(), ['_generate_signal', '_build_history_df']
    while queue:
        name = queue.pop()
        if name in names:
            continue
        names.add(name)
        tree = ast.parse(textwrap.dedent(inspect.getsource(getattr(base, name))))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self'
                    and hasattr(base, node.func.attr)):
                queue.append(node.func.attr)
    return sorted(names)


def main():
    runtime = implementation.load_runtime()
    pd = runtime['pd']
    base = runtime['Strategy']
    # Import class definitions only; never initialize a strategy or engine.
    os.environ['MPLCONFIGDIR'] = '/private/tmp/stage005-independent-mpl'
    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as c9module
    from main_contract_mapping import build_daily_mapping, load_product_universe_symbols
    from stage001_run_first_screen import build_research_strategy, WeeklyLookup
    c9 = c9module.QmtRollPortfolioStrategyStage847C9StopRetry
    wrapper = build_research_strategy(c9, WeeklyLookup([]), 'A0')
    pure_methods = pure_method_closure(base)
    identities = {name: dict(c9_same=getattr(c9, name) is getattr(base, name),
                            research_wrapper_same=getattr(wrapper, name) is getattr(base, name))
                  for name in pure_methods}
    assert len(identities) == 12 and all(all(v.values()) for v in identities.values())
    assert c9module.s827.s772._preload_for_start(pd.Timestamp('2020-01-01')) == pd.Timestamp('2019-06-01')

    summary = json.loads((SOURCE / 'summary.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    assert all(sha(SOURCE / name) == value for name, value in summary['artifacts'].items())
    # Reuse accepted large-source bindings. Do not rehash/re-audit old minute payloads or weekly data.
    checked_paths = [implementation.PROTOCOL, Path(implementation.__file__),
                     Path(implementation.__file__).with_name('test_stage005_potential_signal_demand.py'),
                     A0 / 'actual_strategy_settings.json', A0 / 'effective_parameters.json',
                     implementation.PROJECT / 'qmt_roll_portfolio_strategy.py',
                     implementation.COVERAGE / 'input_manifest.json',
                     implementation.COVERAGE / 'summary.json', implementation.REVIEW]
    assert all(sha(path) == inputs[str(path)] for path in checked_paths)
    assert summary['all_inputs_unchanged'] and not summary['production_qualified']
    for name in ('financial_attempts', 'downloads', 'model_fits', 'strategy_initializations',
                 'account_engines', 'order_api_calls', 'cancel_api_calls', 'outcome_fields_read', 'source_writes'):
        assert summary[name] == 0

    actual = json.loads((A0 / 'actual_strategy_settings.json').read_text())[0]['actual']
    # A separate uninitialized method container, with the recorded actual settings.
    strategy = base.__new__(base)
    for name, value in actual.items():
        setattr(strategy, name, value)
    assert not hasattr(strategy, 'strategy_engine') and not hasattr(strategy, 'states')
    mapping = build_daily_mapping(actual['mapping_csv_path'],
        supported_symbols=load_product_universe_symbols(actual['product_universe_csv_path']))
    metadata = sorted(json.loads((A0 / 'effective_parameters.json').read_text())['contract_sizes'])
    events = pd.read_csv(SOURCE / 'potential_initial_events.csv').fillna('')
    demand = pd.read_csv(SOURCE / 'initial_session_demand.csv').fillna('')
    c0_events = pd.read_csv(SOURCE / 'c0_potential_initial_events.csv').fillna('')
    assert len(events) == summary['raw_events'] == 900
    assert len(c0_events) == summary['c0_allowed_events'] == 701
    pd.testing.assert_frame_equal(events.loc[events.c0_allowed].reset_index(drop=True), c0_events)
    assert (~events.weekly_ready).sum() == summary['weekly_unknown_events'] == 143
    assert events.loc[~events.weekly_ready, 'c0_allowed'].all()
    # Independent finite output-table arithmetic, not a re-run of the indicator stream.
    direction = events.signal.str.startswith('long').map({True: 1, False: -1})
    assert events.c0_allowed.eq(~events.weekly_ready | events.weekly_direction.eq(direction)).all()
    assert len(demand) == 899 and demand.complete.sum() == 416
    assert demand.missing_minutes.gt(0).sum() == 483 and demand.missing_minutes.sum() == 156831
    assert demand.c0_events.gt(0).sum() == 700
    assert (demand.c0_events.gt(0) & demand.missing_minutes.gt(0)).sum() == 378
    assert demand.loc[demand.c0_events.gt(0), 'missing_minutes'].sum() == 124772
    identity_cols = ['signal_date', 'product_vt_symbol', 'vt_symbol', 'signal']
    assert not events.duplicated(identity_cols).any()
    known = pd.read_csv(A0 / 'entry_candidates.csv',
        usecols=['date', 'product_vt_symbol', 'contract_vt_symbol', 'signal']).fillna('')
    observed = set(events[identity_cols].itertuples(index=False, name=None))
    assert len(known) == 886
    assert all(row in observed for row in known[['date', 'product_vt_symbol', 'contract_vt_symbol', 'signal']]
               .itertuples(index=False, name=None))

    cross_roll = []
    for row in events.itertuples(index=False):
        assert mapping[row.signal_date][row.product_vt_symbol] == row.vt_symbol
        next_main = mapping.get(row.execution_trade_date, {}).get(row.product_vt_symbol, '')
        if row.execution_trade_date and next_main != row.vt_symbol:
            cross_roll.append(dict(signal_date=row.signal_date, execution_trade_date=row.execution_trade_date,
                signal_contract=row.vt_symbol, next_mapping_contract=next_main))
    assert len(cross_roll) == 17

    positive_keys = [('2020-01-08', 'rb2005.SHFE'), ('2020-01-09', 'AP005.CZCE'),
                     ('2020-01-10', 'ru2005.SHFE'), ('2020-09-01', 'hc2010.SHFE'),
                     ('2021-09-23', 'CF201.CZCE'), ('2026-10-14', 'sp2701.SHFE')]
    negative_keys = [('2020-01-07', 'rb.SHFE'), ('2020-01-08', 'AP.CZCE')]
    window_checks = []
    real_bar_rows_read = 0
    database = ROOT / '.vntrader/database.db'
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA query_only=ON')

        def window(symbol, day):
            nonlocal real_bar_rows_read
            native, exchange = symbol.rsplit('.', 1)
            params = [native, exchange, '2019-06-01 00:00:00', day + ' 00:00:00']
            rows = db.execute("SELECT datetime,open_price,high_price,low_price,close_price,volume,turnover,open_interest "
                "FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<=? "
                "ORDER BY datetime DESC LIMIT 41", params).fetchall()[::-1]
            total = db.execute("SELECT count(*) FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' "
                "AND datetime>=? AND datetime<=?", params).fetchone()[0]
            real_bar_rows_read += len(rows)
            assert rows and rows[-1][0][:10] == day
            assert len(set(row[0] for row in rows)) == len(rows)
            am = runtime['ArrayManager'](41)
            for row in rows:
                am.update_bar(runtime['BarData'](symbol=native, exchange=runtime['Exchange'](exchange),
                    datetime=datetime.fromisoformat(row[0]), interval=runtime['Interval'].DAILY,
                    gateway_name='INDEPENDENT_READONLY_SQL', open_price=row[1], high_price=row[2],
                    low_price=row[3], close_price=row[4], volume=row[5], turnover=row[6], open_interest=row[7]))
            return am, rows, total

        for day, symbol in positive_keys:
            source_event = events.loc[events.signal_date.eq(day) & events.vt_symbol.eq(symbol)]
            assert len(source_event) == 1
            source_event = source_event.iloc[0]
            am, rows, total = window(symbol, day)
            assert am.inited and total == int(source_event.am_count)
            history = base._build_history_df(strategy, am)
            generated = base._generate_signal(strategy, am, history)
            assert generated['signal'] == source_event.signal and generated['risk_mode'] == source_event.risk_mode
            assert float(rows[0][4]) == source_event.history_first_close
            assert float(rows[-1][4]) == source_event.history_last_close
            # Independently establish the next global engine date from metadata keys only.
            next_dt = db.execute("SELECT min(datetime) FROM dbbardata WHERE interval='d' "
                "AND datetime>? AND datetime<='2026-10-14 00:00:00' AND symbol||'.'||exchange IN ("
                + ','.join('?' for _ in metadata) + ')', [day + ' 00:00:00', *metadata]).fetchone()[0]
            next_day = next_dt[:10] if next_dt else ''
            assert next_day == source_event.execution_trade_date
            window_checks.append(dict(kind='positive', date=day, contract=symbol,
                signal=generated['signal'], risk_mode=generated['risk_mode'], observations_in_SQL=total,
                SQL_window_rows=len(rows), first_window_date=rows[0][0][:10], last_window_date=rows[-1][0][:10],
                history_first_close=rows[0][4], history_last_close=rows[-1][4], next_global_day=next_day,
                weekly_ready=bool(source_event.weekly_ready), weekly_direction=int(source_event.weekly_direction),
                c0_allowed=bool(source_event.c0_allowed), matches=True))
        for day, product in negative_keys:
            symbol = mapping[day][product]
            am, rows, total = window(symbol, day)
            assert am.inited
            generated = base._generate_signal(strategy, am, base._build_history_df(strategy, am))
            assert generated['signal'] == ''
            assert not (events.signal_date.eq(day) & events.product_vt_symbol.eq(product)).any()
            window_checks.append(dict(kind='no_alpha', date=day, product=product, contract=symbol,
                observations_in_SQL=total, SQL_window_rows=len(rows), signal='', matches=True))
        # One actual new-listing warmup boundary, without replaying other contracts/dates.
        warm_day = next(day for day in sorted(mapping) if day >= '2020-01-01' and mapping[day].get('lc.GFEX'))
        warm_symbol = mapping[warm_day]['lc.GFEX']
        am, rows, total = window(warm_symbol, warm_day)
        assert 0 < total < 41 and not am.inited
        assert not (events.signal_date.eq(warm_day) & events.product_vt_symbol.eq('lc.GFEX')).any()
        window_checks.append(dict(kind='not_warmed', date=warm_day, contract=warm_symbol,
            observations_in_SQL=total, SQL_window_rows=len(rows), inited=False, matches=True))

    # Extract only six frozen weekly records. No weekly recomputation.
    weekly_keys = {(day, symbol.rsplit('.', 1)[1] + '.' + ''.join(c for c in symbol.split('.')[0] if not c.isdigit()).upper())
                   for day, symbol in positive_keys}
    weekly_sample = {}
    with implementation.WEEKLY.open(newline='') as f:
        for row in csv.DictReader(f):
            key = row['date'], row['product_id']
            if key in weekly_keys:
                weekly_sample[key] = row
    assert len(weekly_sample) == 6
    for check in window_checks[:6]:
        code, exchange = check['contract'].rsplit('.', 1)
        product = exchange + '.' + ''.join(c for c in code if not c.isdigit()).upper()
        row = weekly_sample[check['date'], product]
        assert (row['weekly_ready'] == 'True') == check['weekly_ready']
        assert int(row['weekly_direction']) == check['weekly_direction']

    # Six exact-key cache joins, no count/grid rerun of the Stage004 table.
    sample_demand = demand.loc[(demand.vt_symbol.eq('rb2005.SHFE') & demand.execution_trade_date.eq('2020-01-09'))
        | (demand.vt_symbol.eq('AP005.CZCE') & demand.execution_trade_date.eq('2020-01-10'))
        | (demand.vt_symbol.eq('ru2005.SHFE') & demand.execution_trade_date.eq('2020-01-13'))
        | (demand.vt_symbol.eq('hc2010.SHFE') & demand.execution_trade_date.eq('2020-09-02'))
        | (demand.vt_symbol.eq('CF201.CZCE') & demand.execution_trade_date.eq('2021-09-24'))]
    assert len(sample_demand) == 5
    requested = {(r.vt_symbol, r.execution_trade_date) for r in sample_demand.itertuples(index=False)}
    cached = {}
    with gzip.open(implementation.COVERAGE / 'session_coverage.csv.gz', 'rt', newline='') as f:
        for row in csv.DictReader(f):
            key = row['vt_symbol'], row['date']
            if key in requested:
                cached[key] = row
                if len(cached) == len(requested):
                    break
    calendar = pd.DatetimeIndex(sorted(pd.Timestamp(day) for day in mapping))
    joined_checks = []
    for row in sample_demand.itertuples(index=False):
        cache = cached[row.vt_symbol, row.execution_trade_date]
        for key in ('expected_minutes', 'available_minutes', 'missing_minutes', 'local_candidate_paths'):
            assert int(cache[key]) == int(getattr(row, key))
        for key in ('anchor_present', 'complete'):
            assert (cache[key] == 'True') == bool(getattr(row, key))
        grid = runtime['session_minutes'](row.vt_symbol, row.execution_trade_date, calendar)
        assert len(grid) == int(row.expected_minutes)
        assert grid[0].isoformat() == row.session_start
        assert (grid[-1] + pd.Timedelta(minutes=1)).isoformat() == row.session_end_exclusive
        joined_checks.append(dict(contract=row.vt_symbol, execution_date=row.execution_trade_date,
            expected=int(row.expected_minutes), available=int(row.available_minutes), missing=int(row.missing_minutes),
            physical_start=row.session_start, full_cache_count_and_helper_identity_match=True))

    missing_known_paths = []
    for attempt, day in [('C0', '2020-05-18'), ('C0_attempt2', '2020-08-12')]:
        path = LINE / 'outputs/stage001_first_screen' / attempt
        failure = json.loads((path / 'run_failure.json').read_text())
        assert not (demand.vt_symbol.eq('rb2010.SHFE') & demand.execution_trade_date.eq(day)).any()
        assert f'intraday_open_anchor_missing:rb2010.SHFE:{day}:' in failure['error']
        assert (path / 'engine.log').stat().st_size == 0
        assert not failure['minute_requests']
        missing_known_paths.append(dict(attempt=attempt, contract='rb2010.SHFE', execution_date=day,
            in_immediate_initial_demand=False, preserved_error=failure['error'],
            preserved_bar_failures=failure['captured_bar_failures'], engine_log_bytes=0,
            offset='unknown_not_retained', origin='not_proven_from_retained_failure'))

    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_original_signal_and_initial_demand_semantic_review_pass', p0_findings=0, p1_findings=0,
        financial_replays=0, full_indicator_stream_repeated=False, account_or_weekly_recalculations=0,
        base_C9_research_wrapper_method_identity=identities,
        MRO=[dict(name=cls.__name__, path=inspect.getfile(cls)) for cls in c9.__mro__[:-1]],
        source_preload='2019-06-01', source_array_manager_size=41,
        positive_SQL_windows=6, no_alpha_SQL_windows=2, warmup_SQL_windows=1,
        real_daily_price_rows_read=real_bar_rows_read, SQL_window_checks=window_checks,
        actual_count_separately_queried=True,
        window_equivalence='last41 real observations exactly determine arrays, RSI and all original signal helpers; total historical AM count is separately checked for positive rows',
        pure_alpha_events_from_existing_table=900, c0_permitted_events=701, weekly_unknown_preserve_baseline=143,
        terminal_pending_excluded_sessions=1, known_A0_four_identity_columns_matched=886,
        cross_mapping_boundary_events=17, cross_mapping_examples=cross_roll[:3],
        sample_cached_session_joins=joined_checks, frozen_weekly_records_only=6,
        raw_initial_sessions=899, raw_missing_sessions=483, raw_missing_minutes=156831,
        c0_initial_sessions=700, c0_missing_sessions=378, c0_missing_minutes=124772,
        known_failed_sessions_outside_immediate_initial_set=missing_known_paths,
        old_minute_payloads_reopened=False, full_cached_coverage_counts_recomputed=False,
        checked_small_input_fingerprints={str(p): sha(p) for p in checked_paths},
        inherited_DB_weekly_minute_bindings='reuse Stage005 input manifest and prior accepted Stage001/002/004 reviews; no repeated full old-data validation',
        source_summary_sha256=sha(SOURCE / 'summary.json'), source_input_manifest_sha256=sha(SOURCE / 'input_manifest.json'),
        production_qualified=False, C0_attempt3_authorized=False, fallback_authorized=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict='not_evaluable',
        scope='exact original pure-alpha initial-event interface under frozen settings, not actual entry orders, deferred initial demand, fills, exits, adds, rollover reopens, full account paths, or independent B signals',
        uncertainty='two prior failed anchors are absent from immediate initial demand; retained receipts do not identify their offset or origin',
        overfitting=False, overfitting_reason='fixed-source identity/time/data-demand verification; no parameter or outcome selection; historical strategy-selection risk remains',
        continued_value=True, continued_value_reason='bounded initial-demand table informs source validation, but full path closure is still required before any account run')
    (DEST / 'signal_sentinel_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'positive_SQL_windows', 'no_alpha_SQL_windows',
        'warmup_SQL_windows', 'real_daily_price_rows_read', 'cross_mapping_boundary_events', 'C0_attempt3_authorized')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
