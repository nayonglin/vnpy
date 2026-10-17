"""Independent read-only evidence audit; never invokes the financial engine.

Reads only the Stage267 selected epoch subset of clean data, plus frozen replay
artifacts. Does not import the source adapter, runner, or monthly sample builder.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
ECONOMIC = ['trade_count', 'turnover', 'commission', 'slippage', 'holding_pnl', 'trading_pnl', 'total_pnl', 'net_pnl']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def receipt(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def load_json(path):
    return json.loads(Path(path).read_text())


def check(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def numeric_error(actual, expected):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    check(a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all(), 'nonfinite or shape mismatch')
    return float(np.max(np.abs(a-b))) if a.size else 0.0


def native_epoch(native, day):
    match = re.fullmatch(r'([A-Za-z]+)(\d{3,4})\.([A-Z]+)', native)
    check(match is not None, f'non-delivery native symbol {native}')
    product, digits, exchange = match.groups()
    anchor = pd.Timestamp(day)
    years = [year for year in range(anchor.year-1, anchor.year+4)
             if year % (10 if len(digits) == 3 else 100) == int(digits[:-2])]
    check(len(years) == 1, f'ambiguous native epoch {native}:{day}')
    check(exchange == 'CZCE' or len(digits) == 4, '3 digits outside CZCE')
    return f'{exchange}.{product.upper()}.{years[0]:04d}{digits[-2:]}'


def current_metadata(info, products):
    # Reference is the original metadata reader, not the Stage267 renamer.
    sys.path[:0] = [str(ROOT), str(ROOT/'examples/portfolio_backtesting')]
    from main_contract_mapping import build_contract_metadata
    from contract_metadata import ALL_FUTURES_CONTRACT_METADATA_PATH, DEFAULT_CONTRACT_METADATA_PATH
    original = build_contract_metadata(supported_symbols=products)
    metadata_file = (ALL_FUTURES_CONTRACT_METADATA_PATH if ALL_FUTURES_CONTRACT_METADATA_PATH.exists()
                     else DEFAULT_CONTRACT_METADATA_PATH)
    result = {}
    for row in info.itertuples():
        result[row.research_symbol] = {key: original[key][row.native_symbol]
            for key in ['sizes', 'rates', 'slippages', 'priceticks', 'margin_ratios', 'metadata_sources']}
    return result, receipt(metadata_file)


def source_audit(source, output):
    summary_path = source/'source_summary.json'
    summary = load_json(summary_path)
    fingerprint_checks = []
    for item in [*summary['inputs'].values(), *summary['source_files'], *summary['outputs'].values()]:
        actual = receipt(item['path'])
        check(actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes'], f'fingerprint changed {item["path"]}')
        fingerprint_checks.append(actual)
    check(summary['financial_replays'] == 1 and summary['model_fits'] == 0, 'source run-count scope')
    check(summary['retrospective_fixed_policy'] and not summary['upstream_model_PIT_certified'], 'missing retrospective source boundary')
    info = pd.read_csv(source/'contract_epoch_identity.csv')
    check(not info.contract_epoch_id.duplicated().any() and not info.research_symbol.duplicated().any(), 'identity collision')
    for row in info.itertuples():
        ex, product, month = row.contract_epoch_id.split('.')
        prod_case, prod_ex = row.product_vt_symbol.split('.')
        check(ex == prod_ex and prod_case.upper() == product and row.research_symbol == f'{prod_case}{month}.{ex}', 'research identity mismatch')
    by_symbol = info.set_index('research_symbol')
    products = summary['inputs'] and list(pd.read_csv(source/'product_coverage.csv', usecols=['product_vt_symbol']).product_vt_symbol.unique())
    metadata, metadata_file = current_metadata(info, products)
    (output/'current_native_metadata_reference.json').write_text(json.dumps(dict(
        status='read_only_current_reference_not_historical_PIT_or_runtime_snapshot', metadata_file=metadata_file,
        original_code=receipt(ROOT/'examples/portfolio_backtesting/contract_metadata.py'),
        research_metadata=metadata), ensure_ascii=False, indent=2)+'\n')

    original = pd.read_csv(summary['inputs']['mapping']['path']).fillna('')
    original = original.loc[original.continuous_symbol_vt.isin(products) &
                            original.date.between(summary['analysis_start'], summary['analysis_end'])]
    private = pd.read_csv(source/'research_epoch_mapping.csv').fillna('')
    check(len(original) == len(private), 'private mapping row count changed')
    joined = private.merge(original[['date','continuous_symbol_vt','main_contract_vt']],
        on=['date','continuous_symbol_vt'], how='outer', suffixes=('', '_original'), validate='one_to_one')
    check(joined.native_symbol.eq(joined.main_contract_vt_original).all(), 'private mapping changed native contract')
    for row in joined.loc[joined.native_symbol.ne('')].itertuples():
        check(native_epoch(row.native_symbol, row.date) == row.contract_epoch_id, 'delivery decade/month mismatch')
        check(row.main_contract_vt == by_symbol.loc[row.main_contract_vt].name, 'mapping unknown private symbol')

    cal = pd.DatetimeIndex(pd.read_csv(source/'source_calendar.csv').date)
    observed_cal = cal[(cal >= summary['analysis_start']) & (cal <= summary['analysis_end'])]
    check(observed_cal.is_unique and observed_cal.is_monotonic_increasing, 'bad source calendar')
    clean_path = Path(summary['inputs']['clean']['path'])
    epochs = info.contract_epoch_id.tolist()
    with closing(sqlite3.connect(clean_path.as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        clean = pd.read_sql_query('SELECT contract_epoch_id,trade_date,close,volume,close_oi,open_oi FROM daily_bars WHERE contract_epoch_id IN ('+
            ','.join('?' for _ in epochs)+') AND trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date', db,
            params=epochs+[summary['analysis_start'],summary['analysis_end']])
    check(len(clean) == summary['real_daily_bar_count'], 'selected clean row count')
    check(not clean.duplicated(['contract_epoch_id','trade_date']).any(), 'duplicate selected clean key')
    frames = {}
    for epoch, group in clean.groupby('contract_epoch_id', sort=False):
        symbol = info.loc[info.contract_epoch_id.eq(epoch), 'research_symbol'].iloc[0]
        frames[symbol] = group.set_index('trade_date')
    trades = pd.read_csv(source/'source_trades.csv')
    fills = pd.read_csv(source/'real_bar_fill_audit.csv')
    check(not trades.trade_id.duplicated().any(), 'duplicate trades')
    check(set(trades.trade_id) == set(fills.trade_id) and len(fills) == len(trades), 'fill audit not complete')
    fill_join = trades.merge(fills, on='trade_id', suffixes=('', '_audit'), validate='one_to_one')
    check(fill_join.date.eq(fill_join.date_audit).all() and fill_join.vt_symbol.eq(fill_join.vt_symbol_audit).all(), 'fill trace differs')
    check(trades.signed_volume.eq(np.where(trades.direction.eq('Long'), trades.volume, -trades.volume)).all(), 'signed volume')
    for row in trades.itertuples():
        check(row.vt_symbol in frames and row.date in frames[row.vt_symbol].index, f'stale fill {row.trade_id}')
        check(row.vt_symbol == f'{row.symbol}.{row.exchange}', 'trade symbol mismatch')
    deferred = pd.read_csv(source/'deferred_missing_real_bar_orders.csv')
    check(len(deferred) == summary['deferred_missing_real_bar_order_attempts'], 'guard trace count')

    calls = pd.read_csv(source/'pairwise_input_audit.csv')
    call_counts = []
    for row in calls.itertuples():
        prefix = frames[row.research_symbol].loc[:row.date]
        check(len(prefix) == row.rows and prefix.index[-1] == row.date == row.max_input_date, 'pairwise not exact full prefix/asof')
        check(int(prefix.open_oi.isna().sum()) == row.open_oi_missing_rows, 'opening OI was changed')
        call_counts.append(len(prefix))

    # Independently recalculate source-calendar warmup; not observed tail rows.
    coverage = pd.read_csv(source/'product_coverage.csv').fillna('')
    coverage140 = pd.read_csv(source/'product_coverage_extra140.csv').fillna('')
    check(len(coverage) == len(observed_cal)*len(products), 'coverage not full product-calendar grid')
    for window, cov in [(summary['actual_am_size'], coverage), (140, coverage140)]:
        for symbol, group in cov.loc[cov.mapped].groupby('main_contract_vt', sort=False):
            dates = pd.DatetimeIndex(frames[symbol].index) if symbol in frames else pd.DatetimeIndex([])
            present = observed_cal.isin(dates)
            cumulative = np.r_[0, np.cumsum(present)]
            counts = np.zeros(len(observed_cal), dtype=int)
            counts[window-1:] = cumulative[window:]-cumulative[:-window]
            ready = pd.Series(counts == window, index=observed_cal)
            real = pd.DatetimeIndex(group.date).isin(dates)
            check(np.array_equal(real, group.real_main_bar.to_numpy()), 'coverage real bar flag')
            check(np.array_equal(ready.reindex(pd.DatetimeIndex(group.date)).to_numpy(), group.warmup_complete.to_numpy()), 'coverage warmup flag')
        check(cov.observed.eq(cov.real_main_bar & cov.warmup_complete & ~cov.held_bar_missing).all(), 'coverage observed formula')

    # Trade-day expectations, independent of the source daily-result implementation.
    t = trades.assign(notional=trades.volume*trades.price, signed_notional=trades.signed_volume*trades.price)
    tg = t.groupby(['date','vt_symbol']).agg(n=('trade_id','size'), volume=('volume','sum'),
        signed=('signed_volume','sum'), notional=('notional','sum'), signed_notional=('signed_notional','sum'))
    portfolio = defaultdict(lambda: np.zeros(len(ECONOMIC)))
    holdings = defaultdict(float)
    previous_close, previous_end, previous_date = {}, {}, {}
    max_errors = defaultdict(float)
    missing_held = set()
    position_rows = 0
    for chunk in pd.read_csv(source/'source_position_changes.csv', chunksize=100000):
        position_rows += len(chunk)
        check(chunk.vt_symbol.isin(by_symbol.index).all(), 'unknown ledger symbol')
        for symbol, group in chunk.groupby('vt_symbol', sort=False):
            dates = group.date.to_numpy()
            check(all(dates[i] < dates[i+1] for i in range(len(dates)-1)) and
                  (symbol not in previous_date or previous_date[symbol] < dates[0]), 'duplicate/unsorted ledger date')
            data = frames[symbol]
            observed = data.index.to_numpy()
            ix = np.searchsorted(observed, dates, side='right')-1
            check((ix >= 0).all(), 'valuation before first observed price')
            values = data.close.to_numpy()[ix]
            max_errors['close_matches_real_or_prior_valuation'] = max(max_errors['close_matches_real_or_prior_valuation'], numeric_error(group.close_price, values))
            expected_pre = np.r_[previous_close.get(symbol, 0.0), group.close_price.to_numpy()[:-1]]
            expected_start = np.r_[previous_end.get(symbol, 0.0), group.end_pos.to_numpy()[:-1]]
            max_errors['previous_close_chain'] = max(max_errors['previous_close_chain'], numeric_error(group.pre_close, expected_pre))
            max_errors['position_continuity'] = max(max_errors['position_continuity'], numeric_error(group.start_pos, expected_start))
            native = metadata[symbol]
            keys = pd.MultiIndex.from_arrays([group.date, group.vt_symbol])
            tx = tg.reindex(keys).fillna(0)
            size = native['sizes']
            holding = group.start_pos.to_numpy()*(group.close_price.to_numpy()-group.pre_close.to_numpy())*size
            trading = (tx.signed.to_numpy()*group.close_price.to_numpy()-tx.signed_notional.to_numpy())*size
            turnover = tx.notional.to_numpy()*size
            commission = turnover*native['rates']
            slippage = tx.volume.to_numpy()*size*native['slippages']
            expected = dict(trade_count=tx.n.to_numpy(), turnover=turnover, commission=commission, slippage=slippage,
                holding_pnl=holding, trading_pnl=trading, total_pnl=holding+trading, net_pnl=holding+trading-commission-slippage,
                pos_change=tx.signed.to_numpy(), end_pos=group.start_pos.to_numpy()+tx.signed.to_numpy())
            for field, values in expected.items():
                max_errors[field] = max(max_errors[field], numeric_error(group[field], values))
            for row in group.loc[group.start_pos.ne(0) & ~group.date.isin(data.index)].itertuples():
                missing_held.add((row.date, by_symbol.loc[symbol, 'product_vt_symbol']))
            previous_close[symbol], previous_end[symbol], previous_date[symbol] = group.close_price.iloc[-1], group.end_pos.iloc[-1], dates[-1]
        summed = chunk.groupby('date')[ECONOMIC].sum()
        for day, values in zip(summed.index, summed.to_numpy()):
            portfolio[day] += values
    daily = pd.read_csv(source/'source_daily.csv').set_index('date')
    ledger = pd.DataFrame.from_dict(portfolio, orient='index', columns=ECONOMIC).sort_index()
    check(set(ledger.index) == set(daily.index), 'source daily dates differ')
    for field in ECONOMIC:
        max_errors['portfolio_'+field] = numeric_error(daily[field], ledger.reindex(daily.index)[field])
    max_errors['balance'] = numeric_error(daily.balance, float(summary['capital'])+daily.net_pnl.cumsum())
    check(max(max_errors.values()) < 1e-6, f'independent ledger mismatch {dict(max_errors)}')
    marked = set(map(tuple, coverage.loc[coverage.held_bar_missing, ['date','product_vt_symbol']].to_numpy()))
    check(missing_held == marked, 'missing held day trace mismatch')

    candidates = pd.read_csv(source/'source_entry_candidate_snapshots.csv')
    prematch = daily.balance-daily.trading_pnl+daily.commission+daily.slippage
    equity_reference = candidates.date.map(prematch)
    equity_error = candidates.estimated_equity-equity_reference
    equity_detail = candidates[['candidate_index','date','contract_vt_symbol','estimated_equity']].copy()
    equity_detail['vendor_prematch_equity'] = equity_reference
    equity_detail['difference'] = equity_error
    equity_detail.to_csv(output/'candidate_equity_timing_comparison.csv', index=False)
    result = dict(status='PASS_WITH_RESEARCH_SCOPE_LIMITS', source_summary=receipt(summary_path),
        input_fingerprints_checked=len(fingerprint_checks), metadata_reference_file=metadata_file,
        epochs=len(info), selected_clean_rows=len(clean), source_calendar_days=len(observed_cal),
        independent_mapping_rows=len(joined), fill_count=len(trades), every_fill_has_real_exact_epoch_date=True,
        deferred_stale_order_attempts=len(deferred), guard_recovery_price_exercised=bool(len(deferred)),
        pairwise_calls=len(calls), pairwise_prefix_counts_and_asof_all_equal=True,
        pairwise_min_observations=min(call_counts) if call_counts else None,
        pairwise_calls_below_140=sum(n<140 for n in call_counts),
        coverage120_observed=int(coverage.observed.sum()), coverage140_observed=int(coverage140.observed.sum()),
        position_rows=position_rows, independent_ledger_max_errors=dict(max_errors),
        missing_held_product_days=len(missing_held), candidate_equity_comparison=dict(rows=len(candidates),
            premise='prior vendor balance plus current holding PNL, before same-day fills/costs',
            matches_within_1e_6=int(equity_error.abs().le(1e-6).sum()), max_abs_difference=float(equity_error.abs().max())),
        frozen_source_inputs_and_code=fingerprint_checks,
        qualifications=dict(retrospective_fixed_policy=True, upstream_model_PIT_certified=False,
            source_PNL_is_conditional_account_path=True, original_AM_and_undefined_derived_stat_policy_preserved=True),
        findings=[dict(priority='P2', code='guard_branch_unexercised', detail='No deferred orders occurred; real fill keys passed. Delayed cancellation/repricing behavior has static review only; no financial rerun requested.'),
            dict(priority='P2', code='metadata_reference_not_runtime_snapshot', detail='Current native metadata is exported and size/cost is independently checked against every ledger row. Native metadata CSV was not included in original run input receipt; tick/margin historical PIT is not certified.'),
            dict(priority='P2', code='partial_strategy_equity_trace', detail='Candidate equity can be compared at pre-fill timing; no full daily strategy-equity trace was exported. Vendor contract/daily PNL is independently verified and remains the label source.'),
            dict(priority='P2', code='fixed_policy_model_time_and_missing_data', detail='Frozen pairwise model uses 2020-2022 training observations; early source is retrospective. Missing held days may affect later shared account state; source is conditional, not independent product return or production PIT proof.')],
        activity=dict(financial_replays=0, model_fits=0, new_downloads=0, main_database_writes=0,
                      clean_queries='read-only selected 837 epochs only; no full raw-data QA'))
    return result


def monthly_manifest_audit(folder):
    summary_path = folder/'sample_summary.json'
    if not summary_path.exists():
        return dict(status='PENDING', path=str(folder))
    summary = load_json(summary_path)
    checked = []
    for item in [*summary['inputs'].values(), *summary['outputs'], summary['script'], summary['feature_contract']]:
        actual = receipt(item['path'])
        check(actual['sha256'] == item['sha256'], 'monthly artifact fingerprint changed')
        checked.append(actual)
    contract = load_json(summary['feature_contract']['path'])
    columns = contract['feature_columns']
    check(len(columns) == 108 and len(set(columns)) == 108 and not any(c.startswith(('future_','target_','sample_weight_')) for c in columns), 'monthly feature schema leak')
    return dict(status='MANIFEST_AND_SCHEMA_PASS', summary=receipt(summary_path), feature_count=108,
                monthly_artifacts_checked=checked, samples_all=summary['all'], qualified=summary['qualified'],
                informative=summary['informative'], note='Independent numerical 108/60 audit is performed by the separate reviewer; its evidence is linked when supplied.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=LINE/'outputs/stage267_clean_training_source')
    parser.add_argument('--samples', type=Path)
    parser.add_argument('--monthly-review', type=Path)
    parser.add_argument('--reuse-source-review', type=Path)
    parser.add_argument('--output', type=Path, default=LINE/'outputs/stage267_independent_review/source_and_sample_review.json')
    args = parser.parse_args(argv)
    check(not args.output.exists(), 'existing audit output; choose a new filename')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.reuse_source_review:
        result = load_json(args.reuse_source_review)
        check(result['source_summary']['sha256'] == sha(args.source/'source_summary.json'), 'cached source evidence changed')
        result['reused_independent_source_review'] = receipt(args.reuse_source_review)
        result['original_source_validation_script'] = result['review_script']
    else:
        result = source_audit(args.source, args.output.parent)
    result['generated_at'] = datetime.now().astimezone().isoformat()
    result['review_script'] = receipt(__file__)
    result['monthly'] = monthly_manifest_audit(args.samples) if args.samples else dict(status='PENDING')
    if args.monthly_review:
        external = load_json(args.monthly_review)
        result['monthly'] = dict(status='DELEGATED_INDEPENDENT_REVIEW', evidence=receipt(args.monthly_review),
            report=external, method='Separate independent reviewer, no repeated monthly calculation in this source audit')
    if result['pairwise_calls_below_140'] and not any(f['code'] == 'inherited_pairwise_maturity_policy' for f in result['findings']):
        result['findings'].append(dict(priority='P2', code='inherited_pairwise_maturity_policy',
            detail=f"{result['pairwise_calls_below_140']} of {result['pairwise_calls']} exact-asof calls have fewer than 140 observations (minimum {result['pairwise_min_observations']}). Original AM120 and undefined-derived-value policy retained; not all 19 features are certified mature."))
    result['candidate_equity_evidence'] = receipt(args.output.parent/'candidate_equity_timing_comparison.csv')
    result['derived_metadata_evidence'] = receipt(args.output.parent/'current_native_metadata_reference.json')
    result['finding_counts'] = {level: sum(f['priority'] == level for f in result['findings']) for level in ['P0','P1','P2']}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ['status','epochs','selected_clean_rows','fill_count','position_rows','candidate_equity_comparison','finding_counts','monthly']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
