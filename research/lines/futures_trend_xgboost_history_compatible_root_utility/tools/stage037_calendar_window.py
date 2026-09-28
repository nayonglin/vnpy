from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage037_calendar_window'
OUTPUT = ROOT / 'artifacts' / STAGE
CONTRACT = ROOT / 'stages/20260906_0931_stage037_calendar_window_contract.md'
FREEZE = ROOT / 'stages/stage037_input_freeze.json'
SOURCE_OUTPUT = ROOT / 'artifacts/stage036_full_minute_source'
EVIDENCE = ROOT / 'artifacts/stage037_exchange_clock_evidence'
SPEC = importlib.util.spec_from_file_location('calendar_source036', ROOT / 'tools/stage036_full_minute_source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
ORIGINAL_QUALIFY = SOURCE.qualify
ORIGINAL_INPUTS = SOURCE.collect_inputs


def qualify_from_clock(bars, expected, day, next_day, quantity, parity, guards):
    future = expected[expected.bar_date.eq(next_day)
                      & expected.bar_datetime.gt(pd.Timestamp(day) + pd.Timedelta(hours=15))]
    if future.empty:
        result = ORIGINAL_QUALIFY(bars, expected, day, next_day, False, quantity, parity, guards)
        result['status'] = 'expected_next_window_missing'
        return result
    first = future.bar_datetime.min()
    night = first == pd.Timestamp(day) + pd.Timedelta(hours=21)
    daytime = first == pd.Timestamp(next_day) + pd.Timedelta(hours=9)
    result = ORIGINAL_QUALIFY(bars, expected, day, next_day, night, quantity, parity, guards)
    if not night and not daytime:
        result['status'] = 'unsupported_expected_anchor'
    return result


def calendar_hook(bars, expected, day, next_day, legacy_night, quantity, parity, guards):
    return qualify_from_clock(bars, expected, day, next_day, quantity, parity, guards)


def collect_inputs():
    files = ORIGINAL_INPUTS()
    files.update(calendar_runner=Path(__file__).resolve(), calendar_contract=CONTRACT,
                 calendar_tests=ROOT / 'tests/test_stage037_calendar_window.py',
                 source036_freeze=ROOT / 'stages/stage036_input_freeze.json',
                 source036_manifest=SOURCE_OUTPUT / 'input_manifest.json',
                 source036_summary=SOURCE_OUTPUT / 'summary.json',
                 exchange_gazette=EVIDENCE / 'czce_2023_09_gazette.pdf',
                 exchange_download_receipt=EVIDENCE / 'receipt.json')
    for name in ('windows', 'daily_comparison', 'contracts'):
        files['source036_output_' + name] = SOURCE_OUTPUT / (name + '.csv')
    return dict(sorted(files.items()))


def configured():
    SOURCE.STAGE = STAGE
    SOURCE.OUTPUT = OUTPUT
    SOURCE.FREEZE = FREEZE
    SOURCE.collect_inputs = collect_inputs
    SOURCE.qualify = calendar_hook
    return SOURCE.configured()


def verify_parent():
    runner = SOURCE.WINDOW.configured()
    runner.STAGE = 'stage036_full_minute_source'
    runner.collect_input_files = ORIGINAL_INPUTS
    runner.EXPECTED_INPUT_FILE_COUNT = len(ORIGINAL_INPUTS())
    manifest = json.loads((SOURCE_OUTPUT / 'input_manifest.json').read_text())
    runner.validate_frozen_input_contract(ROOT / 'stages/stage036_input_freeze.json', manifest)
    runner.validate_current_input_manifest(manifest)
    result = json.loads((SOURCE_OUTPUT / 'summary.json').read_text())
    for item in result['outputs'].values():
        if runner._file_identity(Path(item['path'])) != item:
            raise ValueError('calendar_parent_output_changed')


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--run', action='store_true')
    args = parser.parse_args()
    verify_parent()
    runner = configured()
    if args.freeze:
        manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
        value = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
                 'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        value['execution_authorized'] = True
        SOURCE.WINDOW.inventory_tool().load('stage004_label_batch').write_json(FREEZE, value)
        print(json.dumps(value), flush=True)
    else:
        SOURCE.run()


if __name__ == '__main__':
    main()
