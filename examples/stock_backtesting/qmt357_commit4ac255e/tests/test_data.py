"""Variant snapshots must be independent, immutable and hash-validated."""
import importlib
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / 'data.py'
    assert path.exists(), 'Independent variant snapshot storage is missing'
    return importlib.import_module('examples.stock_backtesting.qmt357_commit4ac255e.data')


def test_variant_snapshot_roundtrip_and_original_source_independence(tmp_path, monkeypatch):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    from examples.stock_backtesting.qmt357 import data as baseline
    data = module()
    original_root = baseline.DATA_DIR
    monkeypatch.setattr(data, 'DATA_DIR', tmp_path / 'variant/snapshots')
    frame, _ = fixture_panel()
    source = tmp_path / 'source.parquet'
    frame.to_parquet(source, index=False)
    path = data.prepare_snapshot(source, 'frozen', 'custom')
    source.unlink()  # Future replay depends only on the frozen bytes.
    restored, manifest = data.load_snapshot(path)
    assert len(restored) == len(frame)
    assert path.parent == tmp_path / 'variant/snapshots'
    assert baseline.DATA_DIR == original_root
    assert manifest['snapshot_name'] == 'frozen'
    assert manifest['factor_changes_without_actions'] == 0
    with pytest.raises(FileExistsError):
        data.prepare_snapshot(source, 'frozen', 'custom')
    (path / 'panel.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='SHA256'):
        data.load_snapshot(path)


@pytest.mark.parametrize('name', ['../baseline', '/tmp/escape', 'x/y', ''])
def test_snapshot_rejects_escape(tmp_path, monkeypatch, name):
    data = module()
    monkeypatch.setattr(data, 'DATA_DIR', tmp_path / 'snapshots')
    with pytest.raises(ValueError):
        data._snapshot_path(name)


def test_snapshot_rejects_symlinked_parent(tmp_path, monkeypatch):
    data = module()
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = tmp_path / 'data'
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(data, 'DATA_DIR', link / 'snapshots')
    with pytest.raises(ValueError, match='symlink'):
        data._snapshot_path('escape')


def test_snapshot_rejects_manifest_summary_tampering(tmp_path, monkeypatch):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    data = module()
    monkeypatch.setattr(data, 'DATA_DIR', tmp_path / 'snapshots')
    frame, _ = fixture_panel()
    source = tmp_path / 'source.parquet'
    frame.to_parquet(source, index=False)
    path = data.prepare_snapshot(source, 'frozen', 'custom')
    manifest = json.loads((path / 'manifest.json').read_text())
    manifest['rows'] += 1
    (path / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='summary'):
        data.load_snapshot(path)
