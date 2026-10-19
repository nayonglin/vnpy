"""Causal, unadjusted product-main weekly closes for the long-entry gate.

The caller supplies an independent, complete session calendar.  Source truncation
never defines a week boundary.  Only the mapped contract's accepted clean EOW
close is eligible; invalid weeks remain in rolling windows.  This module neither
selects the main contract nor calculates financial performance.
"""
from bisect import bisect_left, bisect_right
from hashlib import sha256
import json
import math

import numpy as np
import pandas as pd

WINDOWS = (5, 10, 20, 40)
COLUMNS = ['product_vt_symbol', 'week_last_session', 'main_contract_vt',
           'observation_date', 'close', 'volume', 'valid', 'ma5', 'ma10',
           'ma20', 'ma40', 'history_weeks', 'valid_weeks', 'allowed', 'reason',
           'evidence_id']


def _date(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('invalid_date')
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
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(',', ':')).encode()).hexdigest()


class WeeklyMainTrend:
    """Frozen weekly evidence and phase-aware JSON-safe lookup.

    ``signal_close`` may observe an EOW session's close on that same date.
    ``open`` may observe only weeks whose last session is strictly earlier.
    Calendar-only future rows can be present as invalid evidence; lookup never
    returns them before their calendar completion date.
    """
    def __init__(self, market, mapping, calendar):
        required_market = {'date', 'vt_symbol', 'close', 'volume'}
        required_mapping = {'date', 'continuous_symbol_vt', 'main_contract_vt', 'observation_date'}
        if not required_market.issubset(market.columns):
            raise ValueError('missing_market_columns')
        if not required_mapping.issubset(mapping.columns):
            raise ValueError('missing_mapping_columns')
        cal = calendar['date'] if isinstance(calendar, pd.DataFrame) else calendar
        days = pd.DatetimeIndex([_date(d) for d in cal])
        if days.has_duplicates:
            raise ValueError('duplicate_calendar_session')
        days = days.sort_values()
        market = market.copy()
        mapping = mapping.copy()
        market['date'] = [_date(d) for d in market.date]
        mapping['date'] = [_date(d) for d in mapping.date]
        if market.duplicated(['date', 'vt_symbol']).any():
            raise ValueError('duplicate_daily_price')
        if mapping.duplicated(['date', 'continuous_symbol_vt']).any():
            raise ValueError('duplicate_main_mapping')
        products = sorted(str(p) for p in mapping.continuous_symbol_vt.dropna().unique() if str(p).strip())
        self._records = {}
        self._dates = {}
        if days.empty or not products:
            self.weekly = pd.DataFrame(columns=COLUMNS)
            return

        # Derive EOW from the full independent calendar BEFORE restricting output.
        # A source ending Wednesday still references its real future Friday EOW;
        # a broad vendor calendar must not add decades of price-less history.
        calendar_ends = pd.Series(days).groupby(days.to_period('W-SUN')).max()
        source_dates = pd.concat([market['date'], mapping['date']], ignore_index=True)
        first_week = source_dates.min().to_period('W-SUN')
        last_week = source_dates.max().to_period('W-SUN')
        ends = calendar_ends.loc[(calendar_ends.index >= first_week) &
                                 (calendar_ends.index <= last_week)].tolist()
        grid = pd.MultiIndex.from_product([products, ends], names=['continuous_symbol_vt', 'date']).to_frame(index=False)
        selected = grid.merge(mapping[list(required_mapping)], on=['continuous_symbol_vt', 'date'], how='left', validate='one_to_one')
        price_columns = ['date', 'vt_symbol', 'close', 'volume']
        price_columns += [c for c in ('execution_only', 'quote_class') if c in market]
        selected = selected.merge(market[price_columns], left_on=['date', 'main_contract_vt'],
                                  right_on=['date', 'vt_symbol'], how='left', validate='many_to_one')
        rows = []
        for product, group in selected.groupby('continuous_symbol_vt', sort=True):
            history = []
            evidence = []
            for row in group.sort_values('date').to_dict('records'):
                contract = _safe(row['main_contract_vt'])
                contract = contract.strip() if contract else None
                observation = pd.to_datetime(row['observation_date'], errors='coerce')
                if pd.notna(observation):
                    observation = _date(observation)
                close = pd.to_numeric(row['close'], errors='coerce')
                volume = pd.to_numeric(row['volume'], errors='coerce')
                quote_class = str(row.get('quote_class', '')).lower().replace('-', '_').replace(' ', '_')
                execution = row.get('execution_only', False)
                if not contract:
                    issue = 'missing_main_mapping'
                elif pd.isna(observation) or observation >= row['date']:
                    issue = 'noncausal_or_missing_observation'
                elif not isinstance(execution, (bool, np.bool_)) or bool(execution):
                    issue = 'execution_only_or_unknown_quote'
                elif 'execution_only' in quote_class or 'quote_only' in quote_class:
                    issue = 'execution_only_quote_class'
                elif not math.isfinite(close) or close <= 0:
                    issue = 'missing_or_nonpositive_selected_close'
                elif not math.isfinite(volume) or volume <= 0:
                    issue = 'nonpositive_selected_volume'
                else:
                    issue = None
                valid = issue is None
                item = dict(product_vt_symbol=product, week_last_session=row['date'].date().isoformat(),
                            main_contract_vt=contract, observation_date=_safe(observation),
                            close=float(close) if valid else float('nan'), volume=_safe(volume), valid=valid)
                history.append(item['close'])
                means = {f'ma{n}': float(np.mean(history[-n:])) if len(history) >= n else float('nan') for n in WINDOWS}
                valid_weeks = int(sum(math.isfinite(v) for v in history[-40:]))
                allowed = bool(len(history) >= 40 and valid_weeks == 40 and
                               means['ma5'] > means['ma10'] > means['ma20'] > means['ma40'])
                reason = issue or ('insufficient_history' if len(history) < 40 else
                                   'invalid_week_in_window' if valid_weeks < 40 else
                                   'strict_bullish' if allowed else 'not_strict_bullish')
                evidence.append(dict(week_last_session=item['week_last_session'], main_contract_vt=contract,
                                     observation_date=item['observation_date'], raw_close=_safe(close),
                                     volume=_safe(volume), quote_issue=issue))
                item.update(means, history_weeks=len(history), valid_weeks=valid_weeks,
                            allowed=allowed, reason=reason,
                            evidence_id=_hash(dict(policy='causal_main_completed_week_ma5_10_20_40_v1',
                                                   product_vt_symbol=product, window=evidence[-40:])))
                rows.append(item)
            records = [{k: _safe(v) for k, v in r.items()} for r in rows if r['product_vt_symbol'] == product]
            self._records[product] = records
            self._dates[product] = [r['week_last_session'] for r in records]
        self.weekly = pd.DataFrame(rows, columns=COLUMNS)

    def lookup(self, product, asof, phase='signal_close'):
        if phase not in ('signal_close', 'open'):
            raise ValueError('unknown_weekly_lookup_phase')
        date = _date(asof).date().isoformat()
        product = str(product)
        dates = self._dates.get(product, [])
        index = (bisect_right(dates, date) if phase == 'signal_close' else bisect_left(dates, date)) - 1
        if index >= 0:
            result = dict(self._records[product][index])
        else:
            result = dict(product_vt_symbol=product, week_last_session=None, main_contract_vt=None,
                          observation_date=None, close=None, volume=None, valid=False,
                          ma5=None, ma10=None, ma20=None, ma40=None, history_weeks=0,
                          valid_weeks=0, allowed=False,
                          reason='no_completed_week' if product in self._records else 'unknown_product',
                          evidence_id=_hash(dict(policy='causal_main_completed_week_ma5_10_20_40_v1',
                                                product_vt_symbol=product, window=[])))
        result.update(asof_date=date, phase=phase)
        return result
