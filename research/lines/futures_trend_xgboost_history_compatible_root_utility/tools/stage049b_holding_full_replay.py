from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = '69e4e9bd8dab96be26288ea51a76fca5cc834c773a92b0408dbf957b63b71a5a'
PRIOR_FREEZE = ROOT / 'stages/stage049_input_freeze.json'
CONTRACT = ROOT / 'stages/20260907_0551_stage049b_freeze_compatibility.md'
SCIENTIFIC_CONTRACT = ROOT / 'stages/20260906_1706_stage049_holding_full_path_contract.md'


def freeze_payload(manifest):
    payload = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
        'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
    payload['execution_authorized'] = True
    return payload


def adapted():
    spec = importlib.util.spec_from_file_location('compatible049b', ROOT / 'tools/stage049_holding_full_replay.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original_configured, original_inputs = module.configured, module.collect_inputs
    module.STAGE = 'stage049b_holding_full_replay'
    module.OUTPUT = ROOT / 'artifacts' / module.STAGE
    module.FREEZE = ROOT / 'stages/stage049b_input_freeze.json'
    module.__file__ = str(Path(__file__).resolve())

    def configured(input_count=None, summary_sha=None):
        if summary_sha != MODEL_SHA:
            raise RuntimeError('holding_fixed_training_summary_changed')
        if input_count is None:
            input_count = json.loads(module.FREEZE.read_text())['input_file_count']
        return original_configured(input_count, summary_sha)

    def collect_inputs(summary_sha):
        files = original_inputs(summary_sha)
        files.update(holding_freeze_compatibility_tool=Path(__file__).resolve(),
            holding_freeze_compatibility_test=ROOT / 'tests/test_stage049b_holding_full_replay.py',
            holding_freeze_compatibility_contract=CONTRACT, holding_failed_prior_freeze=PRIOR_FREEZE)
        return dict(sorted(files.items()))

    def freeze_inputs(summary_sha):
        files = module.collect_inputs(summary_sha)
        batch, _, runner = configured(len(files), summary_sha)
        manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
        batch.verify_baseline_inputs(manifest)
        payload = freeze_payload(manifest)
        batch.write_json(module.FREEZE, payload)
        runner.validate_frozen_input_contract(module.FREEZE, manifest)
        print(json.dumps(payload), flush=True)

    module.configured, module.collect_inputs, module.freeze_inputs = configured, collect_inputs, freeze_inputs
    return module


if __name__ == '__main__':
    adapted().main()
