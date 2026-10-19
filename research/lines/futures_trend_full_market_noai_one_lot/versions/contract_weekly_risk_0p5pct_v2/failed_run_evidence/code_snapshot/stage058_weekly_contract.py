"""Lazy exact-contract completed-week evidence; no continuous/main-contract splice.

Only a queried contract's own accepted-clean EOW close is eligible. Calendar
completion is independent of source coverage. Invalid weeks remain in windows;
listing-aware local ranges and lazy caching avoid a contract x global-time grid.
"""
from bisect import bisect_left, bisect_right
from hashlib import sha256
import json
import math

import numpy as np
import pandas as pd

POLICY = 'exact_contract_completed_week_ma5_10_20_40_v1'
EXPORT_SCOPE = 'queried_contracts_complete_local_weeks'
WINDOWS = (5, 10, 20, 40)
COLUMNS = ['product_vt_symbol', 'contract_vt_symbol', 'week_last_session',
           'close', 'volume', 'valid', 'ma5', 'ma10', 'ma20', 'ma40',
           'history_weeks', 'valid_weeks', 'allowed', 'reason', 'evidence_id',
           'export_scope']


def _date(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('invalid_weekly_date')
    return stamp.normalize().tz_localize(None)


def _safe(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return str(value)


def _hash(payload):
    return sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                             separators=(',', ':')).encode()).hexdigest()


class WeeklyContractTrend:
    """Phase-aware evidence for an exact real contract, cached on first query.

    ``weekly`` exports the full local history of queried contracts only, marked
    by ``export_scope`` both as a column and property. It is not the full metadata
    universe. Empty/unknown queried contracts have no fabricated weekly rows.
    The caller must supply a complete independent calendar and accepted-clean
    market data; when execution_only exists only explicit boolean False passes.
    """
    export_scope = EXPORT_SCOPE

    def __init__(self, market, contracts, calendar):
        if not {'date', 'vt_symbol', 'close', 'volume'}.issubset(market.columns):
            raise ValueError('missing_market_columns')
        if not {'vt_symbol', 'product_vt_symbol'}.issubset(contracts.columns):
            raise ValueError('missing_contract_identity_columns')
        if contracts.vt_symbol.duplicated().any():
            raise ValueError('duplicate_contract_metadata')
        if any(not isinstance(vt, str) or not vt.strip() for vt in contracts.vt_symbol):
            raise ValueError('invalid_contract_identity')
        self._metadata = contracts.set_index('vt_symbol').to_dict('index')
        columns = ['date', 'vt_symbol', 'close', 'volume']
        columns += [c for c in ('execution_only', 'quote_class', 'allow_new_open') if c in market]
        self._market = market[columns].copy()
        self._market['date'] = pd.to_datetime(self._market.date, errors='raise').dt.normalize().dt.tz_localize(None)
        if self._market.date.isna().any():
            raise ValueError('invalid_market_date')
        if self._market.duplicated(['date', 'vt_symbol']).any():
            raise ValueError('duplicate_exact_contract_daily_price')
        self._positions = self._market.groupby('vt_symbol', sort=False).indices
        cal = calendar['date'] if isinstance(calendar, pd.DataFrame) else calendar
        days = pd.DatetimeIndex([_date(d) for d in cal]).sort_values()
        if days.has_duplicates:
            raise ValueError('duplicate_calendar_session')
        self._calendar_ends = pd.Series(days).groupby(days.to_period('W-SUN')).max()
        self._calendar_dates = [d.date().isoformat() for d in self._calendar_ends]
        self._cache = {}
        self._dates = {}

    @property
    def queried_contracts(self):
        return sorted(self._cache)

    @property
    def weekly(self):
        rows = [r for vt in sorted(self._cache) for r in self._cache[vt]]
        frame = pd.DataFrame(rows, columns=COLUMNS)
        frame.attrs['export_scope'] = self.export_scope
        frame.attrs['queried_contracts'] = self.queried_contracts
        return frame

    def _empty(self, vt, reason, week=None):
        product = _safe(self._metadata.get(vt, {}).get('product_vt_symbol'))
        return dict(product_vt_symbol=product, contract_vt_symbol=vt,
                    week_last_session=week, close=None, volume=None, valid=False,
                    ma5=None, ma10=None, ma20=None, ma40=None, history_weeks=0,
                    valid_weeks=0, allowed=False, reason=reason,
                    evidence_id=_hash(dict(policy=POLICY, product_vt_symbol=product,
                                           contract_vt_symbol=vt, unavailable_week=week,
                                           reason=reason)), export_scope=self.export_scope)

    def _load(self, vt):
        if vt in self._cache:
            return
        self._cache[vt] = []
        self._dates[vt] = []
        meta = self._metadata.get(vt)
        if meta is None or not _safe(meta.get('product_vt_symbol')) or vt not in self._positions:
            return
        frame = self._market.iloc[self._positions[vt]].sort_values('date')
        listed = pd.to_datetime(meta.get('listed_date'), errors='coerce')
        start = _date(listed) if pd.notna(listed) else frame.date.min()
        end = frame.date.max()
        if start > end or self._calendar_ends.empty:
            return
        # Get each EOW from the full calendar first; only then limit local weeks.
        periods = self._calendar_ends.index
        ends = self._calendar_ends.loc[(periods >= start.to_period('W-SUN')) &
                                       (periods <= end.to_period('W-SUN'))]
        ends = ends[ends.ge(start)]
        selected = frame.set_index('date').reindex(pd.DatetimeIndex(ends))
        history = []
        evidence = []
        rows = []
        for row in selected.reset_index(names='date').to_dict('records'):
            close = pd.to_numeric(row['close'], errors='coerce')
            volume = pd.to_numeric(row['volume'], errors='coerce')
            execution = row.get('execution_only', False)
            quote_class = str(row.get('quote_class', '')).lower().replace('-', '_').replace(' ', '_')
            allow_open = row.get('allow_new_open', True)
            if not isinstance(execution, (bool, np.bool_)) or bool(execution):
                issue = 'execution_only_or_unknown_quote'
            elif any(label in quote_class for label in ('execution_only', 'quote_only', 'expiry_only')):
                issue = 'execution_only_quote_class'
            elif isinstance(allow_open, (bool, np.bool_)) and not bool(allow_open):
                issue = 'quote_disallows_new_open'
            elif not math.isfinite(close) or close <= 0:
                issue = 'missing_or_nonpositive_exact_contract_close'
            elif not math.isfinite(volume) or volume <= 0:
                issue = 'nonpositive_exact_contract_volume'
            else:
                issue = None
            valid = issue is None
            week = row['date'].date().isoformat()
            history.append(float(close) if valid else float('nan'))
            means = {f'ma{n}': float(np.mean(history[-n:])) if len(history) >= n else float('nan') for n in WINDOWS}
            valid_weeks = int(sum(math.isfinite(v) for v in history[-40:]))
            allowed = bool(len(history) >= 40 and valid_weeks == 40 and
                           means['ma5'] > means['ma10'] > means['ma20'] > means['ma40'])
            reason = issue or ('insufficient_exact_contract_history' if len(history) < 40 else
                               'invalid_week_in_window' if valid_weeks < 40 else
                               'strict_bullish' if allowed else 'not_strict_bullish')
            evidence.append(dict(week_last_session=week, raw_close=_safe(close),
                                 volume=_safe(volume), quote_issue=issue))
            rows.append(dict(product_vt_symbol=str(meta['product_vt_symbol']), contract_vt_symbol=vt,
                             week_last_session=week, close=history[-1], volume=_safe(volume),
                             valid=valid, **means, history_weeks=len(history), valid_weeks=valid_weeks,
                             allowed=allowed, reason=reason, export_scope=self.export_scope,
                             evidence_id=_hash(dict(policy=POLICY, product_vt_symbol=str(meta['product_vt_symbol']),
                                                    contract_vt_symbol=vt, window=evidence[-40:]))))
        self._cache[vt] = rows
        self._dates[vt] = [r['week_last_session'] for r in rows]

    def lookup(self, vt_symbol, asof, phase='signal_close'):
        if phase not in ('signal_close', 'open'):
            raise ValueError('unknown_weekly_lookup_phase')
        if not isinstance(vt_symbol, str):
            raise ValueError('contract_vt_symbol_must_be_string')
        date = _date(asof).date().isoformat()
        self._load(vt_symbol)
        bisect = bisect_right if phase == 'signal_close' else bisect_left
        index = bisect(self._dates[vt_symbol], date) - 1
        calendar_index = bisect(self._calendar_dates, date) - 1
        if vt_symbol not in self._metadata:
            result = self._empty(vt_symbol, 'unknown_exact_contract')
        elif index < 0:
            result = self._empty(vt_symbol, 'no_completed_exact_contract_week')
        elif calendar_index >= 0 and self._calendar_dates[calendar_index] > self._dates[vt_symbol][index]:
            # Do not extend expired local grids or reuse an older allowed week.
            result = self._empty(vt_symbol, 'missing_latest_completed_contract_week',
                                 self._calendar_dates[calendar_index])
        else:
            result = {k: _safe(v) for k, v in self._cache[vt_symbol][index].items()}
        result.update(asof_date=date, phase=phase)
        return result
