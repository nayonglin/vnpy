from __future__ import annotations

import importlib.util
import math
from datetime import date
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('inference045_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def holding_guard_class(preflight, baseline):
    models = load('stage044_holding_models')
    base = models.load('stage006_monthly_models')

    def predict(bundle, day, product, event, spec):
        return models.predict_decision(bundle, day, product, {key: event[key] for key in spec['features']}, spec)

    monthly = SimpleNamespace(validate_cutoff=base.validate_cutoff, digest=models.digest,
        load_bundle=models.load_bundle, predict_decision=predict)
    parent = load('stage008_frozen_inference').frozen_guard_class(preflight, baseline, monthly)
    forbidden = tuple(ROOT / 'artifacts' / name for name in ('stage040_holding_panel', 'stage041_holding_labels',
        'stage041b_holding_labels', 'stage042_holding_labels', 'stage041c_label_collection',
        'stage043_label_collection', 'stage044_holding_training/baseline_observation_predictions.csv'))

    class HoldingInferenceGuard(parent):
        def _check_open(self, file, mode):
            path = self._resolve_path(file)
            if path is not None and not any(token in str(mode) for token in ('w', 'a', 'x', '+')):
                if any(root == path or root in path.parents for root in forbidden):
                    self._block('label_value_read_count', 'holding_label_or_baseline_prediction_read_forbidden')
            super()._check_open(file, mode)

        def _profile(self, frame, event, argument):
            if (event == 'call' and not self._blocking and frame.f_code.co_name == 'fit_month'
                    and Path(frame.f_code.co_filename).resolve() == ROOT / 'tools/stage044_holding_models.py'):
                self._block('model_fit_count', 'holding_month_training_forbidden')
            super()._profile(frame, event, argument)

        def predict_event(self, event):
            if set(event) != {*self.spec['features'], 'decision_date', 'product_vt_symbol'}:
                raise RuntimeError('holding_current_feature_inventory')
            day, product = event['decision_date'], event['product_vt_symbol']
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                raise RuntimeError('holding_decision_date_invalid')
            if not isinstance(product, str) or not product:
                raise RuntimeError('holding_decision_product_invalid')
            if any(not isinstance(event[key], (int, float)) or not math.isfinite(event[key]) for key in self.spec['features']):
                raise RuntimeError('holding_current_feature_nonfinite')
            return super().predict_event(event)

        def predict_holding(self, decision_date, product, current_features):
            if set(current_features) != set(self.spec['features']):
                raise RuntimeError('holding_current_feature_inventory')
            return self.predict_event({**current_features, 'decision_date': decision_date, 'product_vt_symbol': product})

    return HoldingInferenceGuard
