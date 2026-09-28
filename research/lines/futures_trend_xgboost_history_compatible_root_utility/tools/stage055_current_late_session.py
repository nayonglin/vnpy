from __future__ import annotations

import copy
from datetime import date
from functools import lru_cache
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('late055_' + name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class LateSessionSource(load('stage046_dynamic_exit_source').DynamicExitSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_records, self.references = [], {}
        self.feature_days = set(self.next_day) | set(self.next_day.values())

    def features(self, row):
        day = row['date']; positions = row['actual_positions']
        if (not isinstance(day, str) or date.fromisoformat(day).isoformat() != day
                or day not in self.feature_days or len(positions) != 1):
            raise RuntimeError('late_current_calendar_or_inventory')
        symbol = next(iter(positions))
        if symbol not in self.contracts:
            self._load_contract(symbol)
        frame, expected, parity = self.contracts[symbol]
        if not parity.get(day, False):
            raise RuntimeError('late_current_source_daily_parity_failed')
        if symbol not in self.references:
            reference = self._frame(self.entries[symbol], 'daily_reference_path', 'daily_reference_sha256')
            if reference.bar_date.duplicated().any():
                raise RuntimeError('late_current_duplicate_reference')
            self.references[symbol] = reference.set_index('bar_date').to_dict('index')
        late = load('stage052_late_session_features')
        values = late.features_for_day(frame, expected, {'date': day, 'vt_symbol': symbol, 'snapshot': row},
                                       self.references[symbol].get(day), self.guards)
        self.feature_records.append({'date': day, 'vt_symbol': symbol, **values})
        return {key: values[key] for key in late.FEATURES}

    def receipt(self):
        return {**super().receipt(), 'feature_request_count': len(self.feature_records),
                'feature_records': copy.deepcopy(self.feature_records)}


def bind_policy(provider):
    # A fresh module keeps each worker/parent's feature source isolated without changing frozen Stage047.
    spec = importlib.util.spec_from_file_location('late055_bound_policy', ROOT / 'tools/stage047_current_holding_policy.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    panel = policy.load('stage040_holding_panel'); original = panel.visible_features

    def current_features(row, book, peak):
        features = original(row, book, peak)
        extra = provider.features(row)
        if set(extra) != {'directional_late_return_30m', 'late_volume_fraction_30m'} or set(extra) & set(features):
            raise RuntimeError('late_current_feature_inventory')
        return {**features, **extra}

    panel.visible_features = current_features
    return policy
