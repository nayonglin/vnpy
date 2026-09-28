import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location('post_training_' + path.stem, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_original_pretraining_assertion_with_isolated_missing_directory(tmp_path, monkeypatch):
    original = load(ROOT / 'tests/test_stage045_holding_catalog.py')
    monkeypatch.setattr(original, 'ROOT', tmp_path)
    original.test_no_historical_catalog_exists_until_training_is_complete()


def test_existing_historical_campaign_rejects_wrong_summary_identity():
    campaign = ROOT / 'artifacts/stage044_holding_training'
    assert (campaign / 'summary.json').is_file(), 'this check belongs to the completed-training phase'
    catalog = load(ROOT / 'tools/stage045_holding_catalog.py')
    with pytest.raises(RuntimeError, match='holding_catalog_file_changed'):
        catalog.load_catalog(campaign, {}, '0' * 64, [], [])
