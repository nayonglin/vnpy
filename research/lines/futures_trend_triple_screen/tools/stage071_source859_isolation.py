"""Isolate unproved source859 physical rows; never grant minute-use rights.

The caller must verify and fingerprint the permitted completion-proof sources
before supplying their exact keys. Install this context outside Stage061 so its
equal-only merge runs first. Numeric imports require Stage022's frozen runtime.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys

SOURCE859 = 'stage859_tqsdk_backtest'
POLICY_SCHEMA = 'stage071_source859_preload_isolation_v1'
CACHE_NAMES = ('_FULL_MINUTE_BY_SYMBOL_CACHE', '_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS', '_LAST_MINUTE_AUDIT')


def _numerical():
    import stage022_run_c0_qualified_wait as runtime
    for name in ('numpy', 'pandas'):
        module = sys.modules.get(name)
        if module is not None and not Path(module.__file__).resolve().is_relative_to(runtime.FROZEN_SITE):
            raise RuntimeError(f'numerical_package_imported_before_frozen_runtime:{name}')
    if str(runtime.FROZEN_SITE) not in sys.path:
        raise RuntimeError('configure_stage022_frozen_runtime_first')
    import pandas as pd
    import stage002_local_minute_overlay as old
    return pd, old


def _completed_index(keys, pd):
    normalized = []
    for key in keys:
        if not isinstance(key, (tuple, list)) or len(key) != 2:
            raise ValueError('source859_invalid_completed_value_key')
        symbol, stamp = key
        if not isinstance(symbol, str) or not symbol or symbol.strip() != symbol:
            raise ValueError('source859_invalid_completed_value_symbol')
        stamp = pd.Timestamp(stamp)
        if pd.isna(stamp):
            raise ValueError('source859_invalid_completed_value_timestamp')
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert('Asia/Shanghai').tz_localize(None)
        normalized.append((symbol, stamp))
    if not normalized:
        return pd.MultiIndex.from_arrays([[], pd.DatetimeIndex([])], names=['vt_symbol', 'bar_datetime'])
    return pd.MultiIndex.from_tuples(normalized, names=['vt_symbol', 'bar_datetime']).unique()


def _isolate(frame, completed_index, pd, old):
    required = {'vt_symbol', 'bar_datetime', 'minute_source', *old.VALUES}
    if not required.issubset(frame.columns):
        raise ValueError('source859_required_columns_missing')
    normalized = old.normal_times(frame)
    symbols = normalized.vt_symbol
    if (symbols.isna().any() or not symbols.map(
            lambda value: isinstance(value, str) and bool(value) and value.strip() == value).all()
            or normalized.bar_datetime.isna().any()):
        raise ValueError('source859_invalid_physical_key')
    physical_index = old.minute_keys(normalized)
    if physical_index.has_duplicates:
        raise ValueError('source859_duplicate_physical_key')
    source859 = normalized.minute_source.eq(SOURCE859)
    retained859 = source859 & physical_index.isin(completed_index)
    removed859 = source859 & ~retained859
    result = normalized.loc[~removed859].copy()
    counts = pd.DataFrame(dict(vt_symbol=symbols, input_rows=1,
        source859_rows=source859.astype(int), retained_source859_rows=retained859.astype(int),
        removed_source859_rows=removed859.astype(int), retained_non859_rows=(~source859).astype(int)))
    by_symbol = {str(symbol): {name: int(value) for name, value in row.items()}
        for symbol, row in counts.groupby('vt_symbol', sort=False).sum().iterrows()}
    audit = dict(schema=POLICY_SCHEMA, policy_source=SOURCE859,
        policy='remove_only_source859_without_exact_completed_value_proof',
        qualification_rights_granted=False, input_rows=len(normalized), output_rows=len(result),
        source859_rows=int(source859.sum()), retained_source859_rows=int(retained859.sum()),
        removed_source859_rows=int(removed859.sum()), retained_non859_rows=int((~source859).sum()),
        completed_value_proof_keys=len(completed_index), by_symbol=by_symbol)
    return result, audit


def isolate_unqualified_source859(frame, completed_value_keys):
    """Return a fresh normalized frame and compact audit; do not mutate or qualify.

    Proof keys are normalized once. Physical-key membership stays vectorized;
    removed keys are neither materialized as a Python set nor emitted to JSON.
    """
    pd, old = _numerical()
    completed_index = _completed_index(completed_value_keys, pd)
    return _isolate(frame, completed_index, pd, old)


@contextmanager
def temporary_source859_isolation(s901, completed_value_keys, audit):
    """Wrap the outermost loader and restore all original cache object identities.

    A failed loader call restores its cache references and emits no filter audit.
    An exceptional context exit rolls back this scope's audits as well. Inputs,
    the original cache objects and all qualification predicates remain untouched.
    """
    pd, old = _numerical()
    completed_index = _completed_index(completed_value_keys, pd)
    if not isinstance(audit, list):
        raise TypeError('source859_audit_must_be_list')
    original = s901._load_stage861_full_minute_bars
    saved = {name: getattr(s901, name) for name in CACHE_NAMES}
    audit_start = len(audit)

    def loader(symbols):
        before = {name: getattr(s901, name) for name in CACHE_NAMES}
        try:
            result, summary = _isolate(original(symbols), completed_index, pd, old)
        except BaseException:
            for name, value in before.items():
                setattr(s901, name, value)
            raise
        audit.append(summary)
        return result

    s901._load_stage861_full_minute_bars = loader
    s901._FULL_MINUTE_BY_SYMBOL_CACHE = None
    s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = set()
    s901._LAST_MINUTE_AUDIT = {}
    try:
        yield
    except BaseException:
        del audit[audit_start:]
        raise
    finally:
        s901._load_stage861_full_minute_bars = original
        for name, value in saved.items():
            setattr(s901, name, value)
