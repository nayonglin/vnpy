"""Explicit research corrections, never an automatic anomaly suppression rule.

Callers freeze and verify the original source and each cited evidence artifact.
Factors affect indicator continuity only; no cash or shares are inferred from
them. Every action replacement requires a separate issuer-backed operation.
"""
import math
import pandas as pd


def _positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Factor and ratio must be finite positive values')
    return value


def apply_repairs(panel, operations):
    if panel.duplicated(['date', 'vt_symbol']).any() or not panel.index.is_unique:
        raise ValueError('Repair input must have unique symbol/date and row index')
    result = panel.copy(deep=True)
    seen = set()
    writes = []
    for op in operations:
        if not op.get('evidence') or not op.get('reason'):
            raise ValueError('Every correction requires frozen evidence and a reason')
        identity = (op['vt_symbol'], op['kind'], op.get('date', op.get('before')), op.get('field'))
        if identity in seen:
            raise ValueError('Duplicate correction')
        seen.add(identity)
        stock = panel.loc[panel.vt_symbol.eq(op['vt_symbol'])].sort_values('date')
        if stock.empty:
            raise ValueError('Repair symbol missing from original panel')
        kind = op['kind']
        if kind in {'factor_step', 'factor_move'}:
            date = pd.Timestamp(op['date'])
            at = stock.loc[stock.date.eq(date)]
            prev = stock.loc[stock.date.lt(date)]
            if len(at) != 1 or prev.empty:
                raise ValueError('Factor step lacks exact current and prior rows')
            old_previous = _positive(op['previous_factor'])
            old_current = _positive(op['current_factor'])
            if (not math.isclose(prev.adj_factor.iloc[-1], old_previous, rel_tol=1e-12)
                    or not math.isclose(at.adj_factor.iloc[0], old_current, rel_tol=1e-12)):
                raise ValueError('Original factor anchors do not match correction')
            if kind == 'factor_step':
                multiplier = _positive(op['desired_ratio']) / (old_current / old_previous)
                indices = stock.loc[stock.date.ge(date)].index
            else:
                actual = pd.Timestamp(op['actual_date'])
                if actual >= date or not stock.date.eq(actual).any():
                    raise ValueError('Moved factor must have an earlier observed effective date')
                indices = stock.loc[stock.date.ge(actual) & stock.date.lt(date)].index
                if not stock.loc[indices, 'adj_factor'].eq(old_previous).all():
                    raise ValueError('Cannot move across another factor event')
                multiplier = old_current / old_previous
            affected = set(indices)
            if any(prefix and affected.intersection(prior) for prior, prefix in writes):
                raise ValueError('Factor operation overlaps a legacy prefix')
            writes.append((affected, False))
            result.loc[indices, 'adj_factor'] *= multiplier
        elif kind == 'action':
            column = op['field']
            if column not in {'cash_dividend', 'split_ratio'}:
                raise ValueError('Only separately evidenced cash/split fields are allowed')
            indices = stock.loc[stock.date.eq(pd.Timestamp(op['date']))].index
            new = float(op['new'])
            if (len(indices) != 1 or not stock.loc[indices, column].eq(op['old']).all()
                    or not math.isfinite(new) or new < 0 or (column == 'split_ratio' and new == 0)):
                raise ValueError('Invalid or stale action correction')
            result.loc[indices, column] = new
        elif kind == 'factor_prefix':
            cutoff = pd.Timestamp(op['before'])
            indices = stock.loc[stock.date.lt(cutoff)].index
            after = stock.loc[stock.date.ge(cutoff)]
            factors = pd.DataFrame(op['factors'], columns=['date', 'factor'])
            factors['date'] = pd.to_datetime(factors.date)
            factors['factor'] = factors.factor.map(_positive)
            if (not len(indices) or after.empty or factors.empty or factors.date.duplicated().any()
                    or factors.date.ge(cutoff).any()
                    or not stock.loc[indices, 'adj_factor'].eq(op['expected_old']).all()
                    or not math.isclose(after.adj_factor.iloc[0], _positive(op['bridge_factor']), rel_tol=1e-12)
                    or not math.isclose(factors.sort_values('date').factor.iloc[-1], op['bridge_factor'], rel_tol=1e-12)):
                raise ValueError('Legacy prefix identity/bridge anchors do not match')
            mapped = pd.merge_asof(stock.loc[indices, ['date']], factors.sort_values('date'),
                                   on='date', direction='backward')
            if mapped.factor.isna().any():
                raise ValueError('Legacy factor coverage is incomplete; no future backward fill')
            affected = set(indices)
            if any(affected.intersection(prior) for prior, _ in writes):
                raise ValueError('Legacy prefix overlaps another factor operation')
            writes.append((affected, True))
            result.loc[indices, 'adj_factor'] = mapped.factor.to_numpy()
        else:
            raise ValueError(f'Unsupported correction kind: {kind}')
    if not result.adj_factor.map(lambda x: math.isfinite(x) and x > 0).all():
        raise ValueError('Corrected factors must be finite and positive')
    changes = []
    for column in ['adj_factor', 'cash_dividend', 'split_ratio']:
        for index in panel.index[panel[column].ne(result[column])]:
            changes.append(dict(date=str(panel.loc[index, 'date'].date()),
                vt_symbol=panel.loc[index, 'vt_symbol'], field=column,
                old=float(panel.loc[index, column]), new=float(result.loc[index, column])))
    return result, changes
