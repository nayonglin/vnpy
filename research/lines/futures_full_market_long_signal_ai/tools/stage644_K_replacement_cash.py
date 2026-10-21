"""Frozen643 thin four-C runner; imports and fixtures never consume payloads.

Original157 A books are references only. Every authorized payload is opened,
hashed and parsed once; actually queried literals support independent645 review.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd
import stage644_K_replacement_kernel as kernel
import stage157_voluntary_cash as reuse

TOOLS = Path(__file__).resolve().parent
PROTOCOL_SHA = 'b017e3480dafd4eff14f318c78551a658383c07cc22283f6839919597e56ea32'
ARM = 'SLOT_K_REPLACEMENT'
NEW_FILES = ('stage644_K_replacement_cash.py', 'stage644_K_replacement_kernel.py',
             'test_stage644_K_replacement_cash.py')
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']


def binding(path, raw=None):
    p = Path(path).resolve()
    raw = p.read_bytes() if raw is None else raw
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def read_bound(bound):
    raw = Path(bound['path']).read_bytes()
    if binding(bound['path'], raw) != {k: bound[k] for k in ('path', 'bytes', 'sha256')}:
        raise ValueError('bound asset changed ' + str(bound['path']))
    return raw


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(kernel.original.safe(value), f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def source_bundle():
    return [binding(TOOLS / name) for name in NEW_FILES]


def boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if str(value).lower() in ('true', '1'):
        return True
    if str(value).lower() in ('false', '0'):
        return False
    raise ValueError('unknown boolean ' + repr(value))


def calendar_values(array):
    if array.dtype.kind in 'iu':
        result = [f'{int(d):08d}' for d in array]
        result = [d[:4] + '-' + d[4:6] + '-' + d[6:] for d in result]
    else:
        result = array.astype('datetime64[D]').astype(str).tolist()
    if len(result) != 5587 or result != sorted(set(result)):
        raise ValueError('original5587 source calendar required')
    return result


def metadata_frame(signals, dates):
    if (len(signals) != 4365 or signals.event_id.duplicated().any()
            or signals.duplicated(['family_id', 'u_index']).any()
            or not all(signals.policy == 'NARROW')
            or not all(signals.arm == 'VOLUNTARY_RESELECT')):
        raise ValueError('original4365 main m1 identity differs')
    if not np.isfinite(signals[['u_close', 'N_u', 'low20_u', 'score']].to_numpy(float)).all():
        raise ValueError('nonfinite original causal signal')
    if not all(signals.score > 0) or not all(signals.D_index == signals.u_index + 1):
        raise ValueError('original positive/D predicate differs')
    for r in signals.to_dict('records'):
        u = int(r['u_index'])
        if not 0 <= u < len(dates) or dates[u] != r['u_date']:
            raise ValueError('signal/source calendar differs')
        cutoff = '2020-01-01' if r['u_date'] < '2023-01-01' else '2023-01-01'
        if r['cutoff'] != cutoff or r['reference_epoch'].rsplit('.', 1)[0] != r['product_id']:
            raise ValueError('causal cutoff or actual epoch differs')


class RecordingMarket:
    def __init__(self, market):
        self.market = market
        self.series, self.dates = market.series, market.dates
        self.bars, self.indicators = {}, {}
        self.account = None

    def _record(self, cache, epoch, k, value):
        key = (epoch, int(k))
        if key not in cache:
            cache[key] = dict(epoch=epoch, index=int(k),
                              date=self.dates[k] if 0 <= k < len(self.dates) else None,
                              missing=value is None, value=value, accounts=set())
        cache[key]['accounts'].add(self.account)

    def bar(self, epoch, k):
        value = self.market.bar(epoch, k)
        self._record(self.bars, epoch, k, value)
        return value

    def indicator(self, epoch, k):
        value = self.market.indicator(epoch, k)
        self._record(self.indicators, epoch, k, value)
        return value


class RecordingEconomics(Mapping):
    def __init__(self, values):
        self.raw_values, self.queried, self.account = values, {}, None

    def __iter__(self):
        return iter(self.raw_values)

    def __len__(self):
        return len(self.raw_values)

    def __getitem__(self, epoch):
        value = self.raw_values[epoch]
        self._record(epoch, value, True)
        return value

    def _record(self, epoch, value, present):
        r = self.queried.setdefault(epoch, dict(epoch=epoch, present=present, value=value, accounts=set()))
        r['accounts'].add(self.account)

    def get(self, epoch, default=None):
        present = epoch in self.raw_values
        value = self.raw_values.get(epoch, default)
        self._record(epoch, value, present)
        return value


class _ReferenceRow(Mapping):
    def __init__(self, parent, u, values):
        self.parent, self.u, self.raw_values = parent, u, values

    def __iter__(self):
        return iter(self.raw_values)

    def __len__(self):
        return len(self.raw_values)

    def __getitem__(self, product):
        value = self.raw_values[product]
        self.parent.record(self.u, product, value, True)
        return value

    def get(self, product, default=None):
        value = self.raw_values.get(product, default)
        self.parent.record(self.u, product, value, product in self.raw_values)
        return value


class RecordingReferences(Mapping):
    def __init__(self, values):
        self.raw_values, self.queried, self.account = values, {}, None

    def __iter__(self):
        return iter(self.raw_values)

    def __len__(self):
        return len(self.raw_values)

    def __getitem__(self, u):
        return _ReferenceRow(self, u, self.raw_values[u])

    def get(self, u, default=None):
        if u not in self.raw_values and not isinstance(default, Mapping):
            self.record(u, '', default, False)
            return default
        return _ReferenceRow(self, u, self.raw_values.get(u, {}))

    def record(self, u, product, value, present):
        key = (int(u), product)
        r = self.queried.setdefault(key, dict(u_index=int(u), product_id=product,
                                             reference_epoch=value, present=present, accounts=set()))
        r['accounts'].add(self.account)


def recording_rows(values):
    return [dict(r, accounts=sorted(r['accounts'])) for _, r in sorted(values.items())]


def fixed_gate(points, summaries, reports, baseline_unknown, wealth_positive):
    if len(points) != 4:
        raise ValueError('four frozen C-A comparisons required')
    finite = lambda x: x is not None and bool(np.isfinite(x))
    conditions = dict(
        C_own_total_return_positive_all4=all(finite(p['active_total_return_pct']) and p['active_total_return_pct'] > 0 for p in points),
        C_return_gt_A_all4=all(finite(p['return_percentage_point_difference']) and p['return_percentage_point_difference'] > 0 for p in points),
        C_drawdown_nondegrade_all4=all(finite(p['drawdown_percentage_point_difference']) and p['drawdown_percentage_point_difference'] >= -1e-8 for p in points),
        C_paired_daily_log_lower_positive_all4=all(finite(p.get('ci95_low')) and p['ci95_low'] > 0 for p in points),
        model_execution_known_all4=all(not s['execution_unknown'] and not s['replacement_unknown']
                                     and reports[s['account']]['stale_days'] == 0
                                     and s['terminal_unresolved_open'] == 0
                                     for s in summaries),
        actual_wealth_positive_all4=bool(wealth_positive))
    nominal = all(conditions.values())
    c_unknown = bool(not conditions['model_execution_known_all4'] or not wealth_positive)
    return dict(conditions, cash_nominal_pass=nominal,
                nominal_pass=bool(nominal and not c_unknown),
                status='promising_research_only' if nominal and not c_unknown else 'close_exact_policy',
                financial_unknown=bool(c_unknown or baseline_unknown), C_financial_unknown=c_unknown,
                baseline_execution_unknown=bool(baseline_unknown), baseline_unknown_is_not_new_veto=True,
                promising_is_conditional_historical_research_only=True,
                goal_complete=False, production_qualified=False, increased_betting_qualified=False,
                no_parameter_rescue=True)


def annual_slices(frame, account, arm, window, cost):
    result, previous = [], 1_000_000.
    groups = {str(y): g for y, g in frame.groupby(frame.date.str[:4], sort=True)}
    for year in map(str, range(2020, 2027)):
        group = groups.get(year)
        row = dict(account=account, arm=arm, window=window, cost=cost, year=year,
                   partial=year == '2026', continuous_account_slice=True, independent_cold_start=False)
        if group is None:
            row.update(in_account_window=False, source_days=0)
        else:
            path = np.r_[previous, group.equity.to_numpy(float)]
            row.update(in_account_window=True, source_days=len(group), starting_equity=previous,
                       ending_equity=float(path[-1]), cash_growth=float(path[-1] - previous),
                       return_pct=(float(path[-1]) / previous - 1) * 100 if previous > 0 else None,
                       max_drawdown_pct=float((path / np.maximum.accumulate(path) - 1).min() * 100))
            previous = float(path[-1])
        result.append(row)
    return result


def load_inputs(protocol, out):
    """One read/hash/parse for each frozen payload, with exact review copies."""
    inputs, data, receipts = protocol['inputs'], {}, {}
    if len(inputs) != 20:
        raise ValueError('frozen twenty inputs required')
    mirror = out / 'reused_inputs'
    mirror.mkdir()
    for role, bound in inputs.items():
        raw = read_bound(bound)
        receipts[role] = dict(bound, source_opens=1, hash_and_parse_same_buffer=True)
        copy = (role in ('signals', 'source_calendar', 'family_inventory')
                or role.endswith('_indices') or '/' in role)
        if copy:
            target = mirror / (role.replace('/', '__') + Path(bound['path']).name)
            target.write_bytes(raw)
            receipts[role]['local_copy'] = binding(target, raw)
        if role == 'native_cache':
            data[role] = raw
        elif role.endswith('_indices') or role == 'source_calendar':
            data[role] = np.load(io.BytesIO(raw), allow_pickle=False)
        elif role in ('signals', 'mother_identity') or role.endswith('/daily'):
            kwargs = dict(compression='gzip', keep_default_na=False, float_precision='round_trip')
            if role == 'mother_identity':
                kwargs.update(dtype=str, usecols=IDENTITY)
            data[role] = pd.read_csv(io.BytesIO(raw), **kwargs)
            receipts[role]['rows'] = len(data[role])
        else:
            data[role] = json.loads(raw)
    return data, receipts


def restore_store(data, inputs):
    """Exact132 recovery body; no hidden calendar/protocol/cache rereads."""
    meta = data['native_cache_manifest']
    if (meta['schema'] != 'stage132_native_store_recovery_cache_v1'
            or meta['native_rows'] != 1552456 or meta['native_epochs'] != 9520
            or meta['file'] != inputs['native_cache']):
        raise ValueError('original native cache metadata differs')
    before = reuse.cache_source.database_state(meta['database']['path'])
    if any(meta['database'][k] != v for k, v in before.items()):
        raise ValueError('cached native database stat differs')
    dates = calendar_values(data['source_calendar'])
    store = reuse.cache_source.NativeBars(dates)
    with np.load(io.BytesIO(data.pop('native_cache')), allow_pickle=False) as z:
        epochs, offsets = z['epochs'].tolist(), z['offsets']
        flat = {k: z[k] for k in ('days', 'values', 'accepted', 'valid', 'N', 'low20', 'run')}
        if len(epochs) != 9520 or offsets[0] != 0 or offsets[-1] != 1552456:
            raise ValueError('original native dimensions differ')
        for i, epoch in enumerate(epochs):
            store.series[epoch] = {k: a[int(offsets[i]):int(offsets[i + 1])] for k, a in flat.items()}
    after = reuse.cache_source.database_state(meta['database']['path'])
    if before != after:
        raise ValueError('native database stat changed during recovery')
    return store, dict(native_source_queries=0, native_contract_days=1552456, native_epochs=9520,
                       database_before=before, database_after=after, database_rehashed=False,
                       cache=inputs['native_cache_manifest'], cache_file=inputs['native_cache'],
                       restored_from_exact_cache=True, original_restore_hidden_reads=0)


def build_prepared(signals, mothers, dates):
    if (len(mothers) != 399252 or mothers.event_id.duplicated().any()
            or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95):
        raise ValueError('complete399252/98/95 mother identities required')
    if len(mothers.loc[mothers.u_date.between('2020-01-01', '2026-10-16')]) != 161014:
        raise ValueError('complete161014 forward mothers required')
    if mothers.duplicated(['product_id', 'u_date']).any():
        raise ValueError('duplicate canonical product/u')
    lookup = {d: i for i, d in enumerate(dates)}
    for d, u in zip(mothers.u_date, mothers.u_index):
        if d not in lookup or int(u) != lookup[d]:
            raise ValueError('canonical/source calendar mismatch')
    potential, references = reuse.author.organize(signals, mothers, dates)
    return potential, RecordingReferences(references)


def run(protocol_path, ready_path, out):
    raw = protocol_path.read_bytes()
    pb, protocol = binding(protocol_path, raw), json.loads(raw)
    if pb['sha256'] != PROTOCOL_SHA or protocol['schema'] != 'stage643_single_old_slot_K_replacement_cash_protocol_v1':
        raise ValueError('frozen643 protocol changed')
    ready = json.loads(ready_path.read_bytes())
    sources = source_bundle()
    if not ready.get('source_ready') or ready['protocol'] != pb or ready['source_bundle'] != sources:
        raise ValueError('source-ready binding differs')
    fb = ready['fixture_receipt'].get('binding', ready['fixture_receipt'])
    fixture = json.loads(read_bound(fb))
    if fixture.get('exit_code') != 0 or fixture.get('source_bundle') != sources:
        raise ValueError('passed new-fixture receipt required')
    for bound in protocol['accepted_sources']:
        read_bound(bound)
    out.mkdir(parents=True, exist_ok=False)
    started = completed = 0
    status, error, accounts = 'failed', None, []
    began = time.monotonic()
    write_json(out / 'actual_started.json', dict(protocol=pb, source_ready=binding(ready_path),
               source_bundle=sources, started_at=datetime.now(timezone.utc).isoformat(), max_new_cash=4))
    try:
        data, receipts = load_inputs(protocol, out)
        manifest = data['accepted157_manifest']
        if (manifest['schema'] != 'stage157_voluntary_cash_v1'
                or manifest['status'] not in ('completed', 'completed_with_metadata_continuation')
                or manifest['new_cash_accounts'] != 4 or manifest['signals'] != protocol['inputs']['signals']):
            raise ValueError('accepted157 four OWN accounts/signals required')
        if data['market_protocol']['economic_projection'] != protocol['inputs']['economic_projection']:
            raise ValueError('economic projection lineage differs')
        store, native = restore_store(data, protocol['inputs'])
        dates, signals = store.calendar, data.pop('signals')
        metadata_frame(signals, dates)
        market = RecordingMarket(reuse.CachedMarket(store))
        econ_values = data.pop('economic_projection')['instruments']
        if set(econ_values) != set(store.series):
            raise ValueError('exact9520 economic epochs differ')
        economics = RecordingEconomics(econ_values)
        prepared = build_prepared(signals, data.pop('mother_identity'), dates)
        references = prepared[1]
        families = data['family_inventory']['families_by_scope']['main']
        if len(families) != 95 or len(set(families)) != 95:
            raise ValueError('complete95 family inventory required')
        write_json(out / 'source_read_receipt.json', dict(native, input_receipts=receipts,
                   mother_rows=399252, forward_rows=161014, products=98, families=95, selected_signals=4365,
                   input_payload_opens=20, A_replay=0, fit=0, labels=0, SQL=0, GET=0))
        metrics, comparisons, fy_parts, annual, audits, distributions = [], [], [], [], [], {}
        reports, control, daily_a, daily_c = {}, {}, {}, {}
        unknown_a = False
        for window, bounds in protocol['windows'].items():
            if data['execution_protocol']['cash']['windows'][window] != bounds:
                raise ValueError('unchanged original execution window required')
            start, end = [int(np.searchsorted(dates, d)) for d in bounds]
            idx = data[window + '_indices']
            if end >= len(dates) or dates[end] != bounds[1] or idx.shape != (2000, end - start + 1):
                raise ValueError('fixed source-calendar/bootstrap width differs')
            for cost in protocol['costs']:
                old = f'NARROW_VOLUNTARY_RESELECT_{window}_{cost}'
                own = next(a for a in manifest['accounts'] if a['account_id'] == old)
                if (own['summary'] != protocol['inputs'][old + '/summary']
                        or own['ledgers']['daily'] != protocol['inputs'][old + '/daily']):
                    raise ValueError('OWN A account lineage differs')
                key = (window, cost)
                control[key], daily_a[key] = data[old + '/summary'], data[old + '/daily']
                sa, da = control[key], daily_a[key]
                if da.date.tolist() != dates[start:end + 1]:
                    raise ValueError('full A source-calendar dates differ')
                unknown_a |= bool(sa.get('execution_unknown', False) or np.any(da.stale_positions > 0))
                metrics.append(dict(sa, account=old, arm='A_REUSED', window=window, cost=cost,
                                    source_only=True, replayed=False))
                annual.extend(annual_slices(da, old, 'A_REUSED', window, cost))
                name = f'NARROW_{ARM}_{window}_{cost}'
                for obj in (market, economics, references):
                    obj.account = name
                started += 1
                if started > 4:
                    raise ValueError('four-new-cash budget exhausted')
                write_json(out / f'cash_progress_{started:02d}.json', dict(started=started, completed=completed, account=name))
                book = kernel.run_cash_account(signals, market, dates, economics, cost, name, start, end, prepared=prepared)
                completed += 1
                folder = out / name
                ledgers = reuse.write_ledgers(folder, book)
                audit = [dict(r, account=name, window=window, cost=cost) for r in book['replacement_audit']]
                audits.extend(audit)
                reuse.ref.write_table(folder / 'replacement_audit.csv.gz', audit, ['account', 'D_state', 'unknown'])
                write_json(folder / 'replacement_root_ids.json', book['replacement_root_ids'])
                summary, report, fy = reuse.helpers.cash_report(book, families, float(protocol['initial']))
                replacement_unknown = bool(book['replacement_unknown'])
                summary.update(account=name, arm='C', window=window, cost=cost,
                               execution_unknown=bool(book['execution_unknown'] or replacement_unknown),
                               replacement_unknown=replacement_unknown,
                               entry_execution_unknown=len(book['entry_execution_unknown']),
                               capacity_unknown_roots=len(book['capacity_unknown_roots']),
                               any_historical_stale=report['stale_days'] > 0,
                               terminal_unresolved_open=sum(p.get('state') == 'stale_open_unresolved' for p in book['open_episodes']),
                               replacement_attempts=len(audit),
                               replacement_reserved=sum(kernel.positive(r.get('qty_cap')) for r in audit),
                               replacement_old_confirmed=sum(r.get('old_confirmed') is True for r in audit),
                               replacement_entered_roots=len(book['replacement_root_ids']),
                               replacement_unknown_rows=sum(bool(r.get('unknown', False)) for r in audit),
                               replacement_blocked=sum(not r.get('unknown', False) and r.get('D_qty') == 0 for r in audit))
                report.update(account=name, replacement_unknown=replacement_unknown,
                              replacement_reason_counts=pd.Series([r.get('D_state', 'unspecified') for r in audit], dtype=str).value_counts().to_dict())
                summaries_key = summary
                daily_c[key], reports[name] = pd.DataFrame(book['daily']), report
                metrics.append(summary)
                annual.extend(annual_slices(daily_c[key], name, 'C', window, cost))
                fy = reuse.report_helpers.add_family_costs(fy, book)
                full = pd.MultiIndex.from_product([sorted(families), [str(y) for y in range(2020, 2027)]], names=['family_id', 'year']).to_frame(index=False)
                fy['year'] = fy.year.astype(str)
                full = full.merge(fy, on=['family_id', 'year'], how='left', validate='one_to_one')
                measures = [c for c in ['net_equity_contribution', 'fee', 'slippage', 'fill_count', 'filled_qty'] if c in full]
                full[measures] = full[measures].fillna(0)
                full['in_account_window'] = full.year >= bounds[0][:4]
                fy_parts.append(full.assign(account=name, arm='C', window=window, cost=cost))
                write_json(folder / 'summary.json', summary)
                stat, dist = reuse.paired_statistics(daily_c[key], da, idx)
                distributions[window + '_' + cost] = dist
                comparisons.append(dict(window=window, cost=cost, contrast='C_minus_A157_OWN',
                                        active_total_return_pct=summaries_key['total_return_pct'],
                                        reference_total_return_pct=sa['total_return_pct'],
                                        **reuse.helpers.compare_points(summary, sa), **stat))
                accounts.append(dict(account_id=name, window=window, cost=cost, directory=str(folder),
                                     summary=binding(folder / 'summary.json'), ledgers=ledgers,
                                     replacement_audit=binding(folder / 'replacement_audit.csv.gz'),
                                     replacement_root_ids=binding(folder / 'replacement_root_ids.json')))
                print(json.dumps(dict(phase='account_complete', account=name, completed=completed,
                                      replacement_entered_roots=summary['replacement_entered_roots'])), flush=True)
        wealth = all(reuse.reuse._log_path(d)[0] is not None for d in list(daily_a.values()) + list(daily_c.values()))
        cmetrics = [m for m in metrics if m['arm'] == 'C']
        gate = fixed_gate(comparisons, cmetrics, reports, unknown_a, wealth)
        reuse.ref.write_table(out / 'account_summaries.csv.gz', metrics, [])
        reuse.ref.write_table(out / 'comparisons.csv.gz', comparisons, [])
        reuse.ref.write_table(out / 'bootstrap_distributions.csv.gz', pd.DataFrame(distributions), [])
        reuse.ref.write_table(out / 'replacement_audit.csv.gz', audits, ['account', 'D_state', 'unknown'])
        reuse.ref.write_table(out / 'family_year_including_zero.csv.gz', pd.concat(fy_parts, ignore_index=True), [])
        reuse.ref.write_table(out / 'annual_slices.csv.gz', annual, [])
        evidence = out / 'execution_literals'
        write_json(evidence / 'market_bars.json', recording_rows(market.bars))
        write_json(evidence / 'market_indicators.json', recording_rows(market.indicators))
        write_json(evidence / 'economic_epochs.json', recording_rows(economics.queried))
        write_json(evidence / 'canonical_references.json', recording_rows(references.queried))
        write_json(out / 'diagnostics.json', reports)
        write_json(out / 'continuation_gate.json', gate)
        if completed != 4 or reuse.ref.NATIVE_QUERIES:
            raise ValueError('exact4 C/zero SQL required')
        after = reuse.cache_source.database_state(data['native_cache_manifest']['database']['path'])
        if after != native['database_after']:
            raise ValueError('database stat changed')
        status = 'completed'
    except Exception:
        error = traceback.format_exc()
        write_json(out / 'failure.json', dict(error=error, started=started, completed=completed))
    terminal = dict(status=status, exit_code=0 if status == 'completed' else 1,
                    elapsed_seconds=time.monotonic() - began, cash_accounts_started=started,
                    new_cash_accounts=completed, actual_model_fit_calls=0, new_labels=0,
                    SQL=0, GET=0, old_A_replay=0, goal_complete=False)
    write_json(out / 'actual_terminal.json', terminal)
    artifacts = {str(p.relative_to(out)): binding(p) for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    write_json(out / 'manifest.json', dict(schema='stage644_K_replacement_cash_v1', status=status,
               protocol=pb, source_ready=binding(ready_path), source_bundle=sources,
               inputs=protocol['inputs'], accounts=accounts, artifacts=artifacts,
               terminal=binding(out / 'actual_terminal.json'), new_cash_accounts=completed,
               actual_model_fit_calls=0, new_labels=0, SQL=0, GET=0, old_A_replay=0,
               source_scope='399252/161014 mothers,98 products/95 families,original4365main m1',
               goal_complete=False, production_qualified=False, increased_betting_qualified=False))
    print(json.dumps(terminal), flush=True)
    if status != 'completed':
        raise RuntimeError(error)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--source-ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.protocol, args.source_ready, args.output)
