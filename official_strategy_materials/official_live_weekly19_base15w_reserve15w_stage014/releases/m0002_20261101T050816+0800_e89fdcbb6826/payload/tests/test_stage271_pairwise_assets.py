"""Fail-closed immutable pairwise binding and actual frozen-model inference."""
from dataclasses import dataclass, replace
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'examples/portfolio_backtesting'
sys.path.insert(0, str(PROJECT))
from qmt_roll_official_strategy_material_resolver import ActiveMaterialRelease

MODEL_SHA = 'ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66'
SUMMARY_SHA = 'c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86'
MODEL_LOGICAL = 'ai/stage182/pairwise/model.joblib'
SUMMARY_LOGICAL = 'ai/stage182/pairwise/summary.json'
STRATEGY = 'ai_top10_plus_fu_official_live_v1'


def assets_module():
    assert (PROJECT / 'qmt_roll_official_live_pairwise_assets.py').is_file(), 'pairwise strict resolver missing'
    return importlib.import_module('qmt_roll_official_live_pairwise_assets')


def active_fixture(tmp_path, source_pair=None):
    release_id = 'mtest_pairwise'
    release_root = tmp_path / 'official_strategy_materials' / STRATEGY / 'releases' / release_id
    release_root.mkdir(parents=True)
    rows = []
    if source_pair:
        for source, logical, role in zip(source_pair, [MODEL_LOGICAL, SUMMARY_LOGICAL], ['model_artifact', 'feature_contract']):
            target = release_root / 'payload' / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            rows.append({'logical_path': logical, 'payload_path': 'payload/' + logical,
                         'role': role, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                         'size_bytes': target.stat().st_size})
    manifest = {'release_id': release_id, 'strategy_version': STRATEGY,
                'material_version': 'mtest', 'manifest_sha256': 'a' * 64, 'files': rows}
    manifest_path = release_root / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    return ActiveMaterialRelease(tmp_path, tmp_path/'official_strategy_materials/CURRENT.json',
                                 'active', release_id, 'b'*40, STRATEGY, 'mtest', manifest_path, manifest)


def real_pair():
    # Qualification requires actual repository payloads, with no skip,
    # machine-local data fallback or mocked estimator.
    for manifest_path in sorted((ROOT/'official_strategy_materials').glob('*/releases/*/manifest.json'), reverse=True):
        manifest = json.loads(manifest_path.read_text())
        rows = {r['logical_path']: r for r in manifest.get('files', [])}
        if MODEL_LOGICAL in rows and SUMMARY_LOGICAL in rows:
            pair = tuple(manifest_path.parent/rows[k]['payload_path'] for k in [MODEL_LOGICAL, SUMMARY_LOGICAL])
            if all(p.is_file() and not p.is_symlink() for p in pair):
                return pair
    pytest.fail('real immutable pairwise model and summary must be frozen in repository release payload')


def test_missing_assets_refuse_matching_backtest_outputs_fallback(tmp_path):
    module = assets_module()
    active = active_fixture(tmp_path)
    fallback = tmp_path/'examples/portfolio_backtesting/backtest_outputs'
    fallback.mkdir(parents=True)
    for source in real_pair():
        shutil.copy2(source, fallback/source.name)
    with pytest.raises(RuntimeError, match='pairwise_asset_missing'):
        module.resolve_official_pairwise_assets(active, expected_release_id=active.release_id)


def test_release_identity_mismatch_fails_before_loading_asset(tmp_path):
    module = assets_module()
    active = active_fixture(tmp_path)
    with pytest.raises(RuntimeError, match='pairwise_release_identity_mismatch'):
        module.resolve_official_pairwise_assets(active, expected_release_id='other_release')
    altered = replace(active, manifest={**active.manifest, 'release_id': 'other_release'})
    with pytest.raises(RuntimeError, match='pairwise_release_identity_mismatch'):
        module.resolve_official_pairwise_assets(altered, expected_release_id=active.release_id)


def test_known_hash_is_required_even_when_inventory_accepts_different_bytes(tmp_path):
    module = assets_module()
    paths = []
    for name in ['different.joblib', 'different.json']:
        path = tmp_path/name; path.write_bytes(b'wrong but inventory-consistent bytes'); paths.append(path)
    active = active_fixture(tmp_path, paths)
    with pytest.raises(RuntimeError, match='pairwise_known_sha256_mismatch'):
        module.resolve_official_pairwise_assets(active, expected_release_id=active.release_id)


def test_exact_runtime_version_drift_is_rejected(monkeypatch):
    module = assets_module()
    original = module.metadata.version
    monkeypatch.setattr(module.metadata, 'version', lambda package: '0.0' if package == 'scikit-learn' else original(package))
    with pytest.raises(RuntimeError, match='pairwise_runtime_version_mismatch:scikit-learn'):
        module.assert_pairwise_runtime_versions()


def test_valid_binding_uses_same_release_payload_and_known_sha(tmp_path):
    module = assets_module()
    active = active_fixture(tmp_path, real_pair())
    overrides, audit = module.resolve_official_pairwise_assets(active, expected_release_id=active.release_id)
    for parameter, logical, expected in [('selection_pairwise_model_path', MODEL_LOGICAL, MODEL_SHA),
                                         ('selection_pairwise_summary_path', SUMMARY_LOGICAL, SUMMARY_SHA)]:
        path = Path(overrides[parameter])
        assert path == (active.manifest_path.parent/'payload'/logical).resolve(strict=True)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    assert audit['material_release_id'] == active.release_id
    assert audit['model_sha256'] == MODEL_SHA
    assert audit['summary_sha256'] == SUMMARY_SHA
    assert audit['status'] == 'valid'


def test_stage901_enforces_payload_paths_after_all_other_overrides(tmp_path, monkeypatch):
    module = assets_module()
    active = active_fixture(tmp_path, real_pair())
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901
    @dataclass(frozen=True)
    class Capital:
        variant: str = 'fixture'
        label: str = 'fixture'
        note: str = 'fixture'
        account_capital: float = 150000
        c3_capital: float = 150000
    @dataclass(frozen=True)
    class Spec:
        capital: Capital
        overrides: dict
        profile: str = 'fixture'
    original = {'stage847_stop_retry_r': 0.5, 'selection_pairwise_model_path': '/bad/old.joblib'}
    monkeypatch.setattr(stage901, 'OFFICIAL_LIVE_MATERIAL_RELEASE', active)
    monkeypatch.setattr(stage901, '_ensure_c9_minute_bars', lambda _: {'source':'fixture', 'loaded_symbol_count':0})
    monkeypatch.setattr(stage901.s847, '_c9_profile', lambda _: {'spec':Spec(Capital(), original)})
    monkeypatch.setattr(stage901, 'build_official_live_strategy_overrides', lambda: {'selection_pairwise_model_path':'/bad/last.joblib'})
    monkeypatch.setattr(stage901.s847, '_run_profile', lambda profile, _: (pd.DataFrame({'date':['2026-10-19']}), {}))
    _, _, spec = stage901._run_live_c9({}, pd.Timestamp('2026-07-23'), pd.Timestamp('2026-10-19'))
    assert Path(spec.overrides['selection_pairwise_model_path']) == (active.manifest_path.parent/'payload'/MODEL_LOGICAL).resolve()
    assert Path(spec.overrides['selection_pairwise_summary_path']) == (active.manifest_path.parent/'payload'/SUMMARY_LOGICAL).resolve()
    assert spec.overrides['stage847_stop_retry_r'] == 0.5
    assert stage901._LAST_PAIRWISE_AUDIT['material_release_id'] == active.release_id


def predict_two_real_rows(active):
    module = assets_module()
    overrides, _ = module.resolve_official_pairwise_assets(active, expected_release_id=active.release_id)
    import joblib
    summary = json.loads(Path(overrides['selection_pairwise_summary_path']).read_text())
    columns = summary['model_metadata']['feature_columns']
    model = joblib.load(overrides['selection_pairwise_model_path'])
    x = pd.DataFrame(np.vstack([np.zeros(len(columns)), np.ones(len(columns))*0.25]), columns=columns)
    probabilities = model.predict_proba(x)
    assert probabilities.shape == (2, 2)
    assert np.isfinite(probabilities).all()
    assert np.allclose(probabilities[:,1], [0.2607274555068904, 9.726442794585814e-08], atol=1e-12)
    assert np.allclose(probabilities.sum(axis=1), 1)


def test_portable_release_payload_predicts_two_actual_candidate_rows(tmp_path):
    pair = real_pair()
    manifest_path = pair[0].parents[4]/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    release_commit = subprocess.check_output(
        ['git', '-C', str(ROOT), 'log', '-1', '--format=%H', '--', str(manifest_path.relative_to(ROOT))],
        text=True,
    ).strip()
    assert len(release_commit) == 40, 'qualification payload must be committed'
    active = ActiveMaterialRelease(ROOT, ROOT/'official_strategy_materials/CURRENT.json',
                                   'active', manifest['release_id'], release_commit,
                                   manifest['strategy_version'], manifest['material_version'],
                                   manifest_path, manifest)
    predict_two_real_rows(active)
