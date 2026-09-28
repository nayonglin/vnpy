from __future__ import annotations

from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'stages/20260906_1120_stage041b_numeric_inventory_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('numeric041b_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def numeric_inventory(book):
    result = {}
    for symbol, item in book.items():
        if set(item) != {'quantity', 'average_entry_price', 'source_trade_ids'}:
            raise ValueError('holding_inventory_fields')
        quantity, price = Decimal(item['quantity']), Decimal(item['average_entry_price'])
        if (not quantity.is_finite() or not price.is_finite() or quantity == 0 or price <= 0
                or quantity != quantity.to_integral_value()):
            raise ValueError('holding_inventory_numeric_domain')
        result[symbol] = {'quantity': quantity, 'average_entry_price': price, 'source_trade_ids': item['source_trade_ids']}
    return result


def check_observation(job, row, book, peak):
    if row != job['snapshot'] or peak != job['equity_peak'] or numeric_inventory(book) != numeric_inventory(job['inventory']):
        raise ValueError('holding_label_current_state_changed')
    values = load('stage040_holding_panel').visible_features(row, book, peak)
    if values != job['features']:
        raise ValueError('holding_label_current_features_changed')
    return values


def adapted():
    module = load('stage041_holding_labels')
    original_collect, original_configured = module.collect_inputs, module.configured
    failed = module.OUTPUT
    module.__file__ = str(Path(__file__).resolve())
    module.STAGE = 'stage041b_holding_labels'
    module.OUTPUT = ROOT / 'artifacts' / module.STAGE
    module.FREEZE = ROOT / 'stages/stage041b_input_freeze.json'
    module.check_observation = check_observation

    def collect():
        files = original_collect()
        files.update(numeric_inventory_adapter=Path(__file__).resolve(), numeric_inventory_contract=CONTRACT,
            numeric_inventory_tests=ROOT / 'tests/test_stage041b_numeric_inventory_labels.py',
            original_stage041_runner=ROOT / 'tools/stage041_holding_labels.py',
            stage041_failed_manifest=failed / 'input_manifest.json', stage041_failed_freeze=ROOT / 'stages/stage041_input_freeze.json')
        for path in sorted(failed.rglob('*')):
            if path.is_file():
                files['stage041_failure/' + str(path.relative_to(failed))] = path
        return dict(sorted(files.items()))

    def configured(job=None, audit_ref=None):
        base, runner = original_configured(job, audit_ref)
        if audit_ref is not None:
            original_load = runner.load_v1_runner

            def local_v1():
                v1 = original_load(); install = v1._install_correlation_trace_instrumentation

                def instrument(cls):
                    restore = install(cls); original = cls.on_bars

                    def observed(strategy, bars):
                        try:
                            return original(strategy, bars)
                        except Exception as exc:
                            audit_ref['callback_failure'] = {'error': str(exc), 'traceback': traceback.format_exc(),
                                'date': str(strategy.strategy_engine.datetime)}
                            raise
                    cls.on_bars = observed

                    def undo():
                        cls.on_bars = original
                        restore()
                    return undo

                v1._install_correlation_trace_instrumentation = instrument
                return v1
            runner.load_v1_runner = local_v1
        return base, runner

    module.collect_inputs = collect
    module.configured = configured
    return module


def main():
    if '--worker' not in sys.argv:
        prior = load('stage041_holding_labels'); _, runner = prior.configured()
        manifest = json.loads((prior.OUTPUT / 'input_manifest.json').read_text())
        runner.validate_frozen_input_contract(prior.FREEZE, manifest)
        runner.validate_current_input_manifest(manifest)
    adapted().main()


if __name__ == '__main__':
    main()
