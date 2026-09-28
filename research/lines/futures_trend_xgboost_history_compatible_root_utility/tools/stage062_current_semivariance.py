from __future__ import annotations

import copy
from datetime import date
from functools import lru_cache
import importlib.util
import io
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ('favorable_semivariance_5m', 'adverse_semivariance_5m')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('semivariance062_' + name, ROOT / 'tools' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


class SemivarianceSource(load('stage046_dynamic_exit_source').DynamicExitSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_records, self.references = [], {}
        self.feature_days = set(self.next_day) | set(self.next_day.values())

    def _frame(self, entry, path_key, sha_key):
        import pandas as pd

        path = self._path(entry[path_key]); raw = self._read(path, entry[sha_key])
        # Match the frozen training source's text-to-number conversion, including decimal prices.
        return pd.read_csv(io.BytesIO(raw), dtype=str, compression='gzip' if path.suffix == '.gz' else None)

    def features(self, row):
        day = row['date']; positions = row['actual_positions']
        if (not isinstance(day, str) or date.fromisoformat(day).isoformat() != day
                or day not in self.feature_days or len(positions) != 1):
            raise RuntimeError('semivariance_current_calendar_or_inventory')
        symbol = next(iter(positions))
        if symbol not in self.contracts:
            self._load_contract(symbol)
        frame, expected, parity = self.contracts[symbol]
        if not parity.get(day, False):
            raise RuntimeError('semivariance_current_source_daily_parity_failed')
        if symbol not in self.references:
            reference = self._frame(self.entries[symbol], 'daily_reference_path', 'daily_reference_sha256')
            if reference.bar_date.duplicated().any():
                raise RuntimeError('semivariance_current_duplicate_reference')
            self.references[symbol] = reference.set_index('bar_date').to_dict('index')
        values, _ = load('stage059_realized_semivariance_features').features_for_day(
            frame, expected, {'date': day, 'vt_symbol': symbol, 'snapshot': row},
            self.references[symbol].get(day), self.guards)
        self.feature_records.append({'date': day, 'vt_symbol': symbol, **values})
        return {key: values[key] for key in FEATURES}

    def receipt(self):
        return {**super().receipt(), 'feature_request_count': len(self.feature_records),
            'feature_records': copy.deepcopy(self.feature_records)}


def bind_policy(provider):
    spec = importlib.util.spec_from_file_location('semivariance062_bound_policy', ROOT / 'tools/stage047_current_holding_policy.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    panel = policy.load('stage040_holding_panel'); original = panel.visible_features

    def current_features(row, book, peak):
        values = original(row, book, peak); extra = provider.features(row)
        if set(extra) != set(FEATURES) or set(extra) & set(values):
            raise RuntimeError('semivariance_current_feature_inventory')
        return {**values, **extra}

    panel.visible_features = current_features
    return policy
