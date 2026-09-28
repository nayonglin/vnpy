from __future__ import annotations

from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = 'f8a8ba69f9c2a024c076db3ede01e081fd5f4c0126c25eeaf1a7e3db47705262'
CONTRACT = ROOT / 'stages/20260907_0952_stage061_063_semivariance_consumption_contract.md'


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('semivariance063_' + name, ROOT / 'tools' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def adapted():
    parent = load('stage056_late_session_full_replay')
    original_load = parent.load
    parent.MODEL_SHA, parent.CONTRACT, parent.__file__ = MODEL_SHA, CONTRACT, str(Path(__file__).resolve())

    def select(name):
        if name == 'stage054_late_session_consumption':
            return load('stage061_semivariance_consumption')
        if name == 'stage055_current_late_session':
            source = load('stage062_current_semivariance')
            return SimpleNamespace(LateSessionSource=source.SemivarianceSource, bind_policy=source.bind_policy)
        return original_load(name)

    # Reuse the frozen account/action audit with an isolated model and current source, in parent and worker.
    parent.load = select
    m = parent.adapted()
    m.STAGE = 'stage063_semivariance_full_replay'
    m.OUTPUT = ROOT / 'artifacts' / m.STAGE
    m.FREEZE = ROOT / 'stages/stage063_input_freeze.json'
    m.MODEL_OUTPUT = ROOT / 'artifacts/stage060_semivariance_training'
    original_inputs = m.collect_inputs

    def catalog(summary_sha):
        if summary_sha != MODEL_SHA:
            raise RuntimeError('semivariance_fixed_training_summary_changed')
        spec = json.loads((ROOT / 'artifacts/stage059_realized_semivariance_features/candidate_spec.json').read_text())
        jobs = json.loads((m.PANEL / 'jobs.json').read_text())['jobs']
        months = json.loads((m.PANEL / 'monthly_inventory.json').read_text())
        return load('stage061_semivariance_consumption').load_catalog(m.MODEL_OUTPUT, spec, summary_sha, jobs, months)

    def collect_inputs(summary_sha):
        files = original_inputs(summary_sha)
        files['semivariance_consumption_contract'] = CONTRACT
        for name in ('stage059_realized_semivariance_features', 'stage061_semivariance_consumption',
                'stage062_current_semivariance', 'stage063_semivariance_full_replay'):
            files['semivariance_tool/' + name] = ROOT / 'tools' / (name + '.py')
            files['semivariance_test/' + name] = ROOT / 'tests' / ('test_' + name + '.py')
        return dict(sorted(files.items()))

    m.catalog, m.collect_inputs = catalog, collect_inputs
    return m


if __name__ == '__main__':
    adapted().main()
