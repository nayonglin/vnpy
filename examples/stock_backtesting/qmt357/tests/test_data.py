"""Snapshot contract tests using real local CSV/parquet files, never market APIs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "data.py"


@pytest.fixture
def data_module(tmp_path, monkeypatch):
    assert MODULE_PATH.exists(), "The isolated stock snapshot module is not implemented"
    spec = importlib.util.spec_from_file_location("qmt357_data_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATA_DIR", tmp_path / "snapshots")
    return module


def source_frame():
    return pd.DataFrame([
        dict(date="2026-01-06", vt_symbol="000001.SZ", open=10.0, high=12.0, low=9.0,
             close=11.0, volume=500, adj_factor=1.0, limit_up=12.1, limit_down=9.9,
             is_st="false", is_member="true"),
        dict(date="2026-01-05", vt_symbol="000300.SH", open=4000.0, high=4100.0, low=3900.0,
             close=4050.0, volume=100, adj_factor=1.0, limit_up=None, limit_down=None,
             is_st="false", is_member="false"),
        dict(date="2026-01-06", vt_symbol="000300.SH", open=4050.0, high=4150.0, low=4000.0,
             close=4100.0, volume=200, adj_factor=1.0, limit_up=None, limit_down=None,
             is_st="false", is_member="false"),
    ])


def write_source(tmp_path, frame=None, suffix=".parquet"):
    path = tmp_path / f"source{suffix}"
    frame = source_frame() if frame is None else frame
    if suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_parquet(path, index=False)
    return path


@pytest.mark.parametrize("suffix", [".csv", ".parquet"])
def test_snapshot_is_normalized_hashed_copy_independent_of_source(data_module, tmp_path, suffix):
    # Catches source mutation, missing hashes, missing defaults, and live source reads.
    source = write_source(tmp_path, suffix=suffix)
    original = source.read_bytes()
    snapshot = data_module.prepare_snapshot(source, "original")
    assert snapshot == data_module.DATA_DIR / "original"
    assert source.read_bytes() == original
    source.unlink()
    panel, manifest = data_module.load_snapshot(snapshot)
    assert panel["vt_symbol"].tolist() == ["000300.SSE", "000001.SZSE", "000300.SSE"]
    assert panel["date"].tolist() == list(pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-06"]))
    assert panel["is_member"].tolist() == [False, True, False]
    assert panel["cash_dividend"].tolist() == [0.0, 0.0, 0.0]
    assert panel["split_ratio"].tolist() == [1.0, 1.0, 1.0]
    assert manifest["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert manifest["panel_sha256"] == hashlib.sha256((snapshot / "panel.parquet").read_bytes()).hexdigest()
    assert manifest["rows"] == 3
    assert manifest["stock_symbols"] == 1
    assert manifest["insufficient_history"] is True
    assert manifest["historical_membership_verified"] is False


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape", "nested/name", ".", "", "bad\\name"])
def test_snapshot_name_cannot_escape_data_root(data_module, tmp_path, name):
    # Removing name/path validation must permit these forbidden targets and fail this test.
    source = write_source(tmp_path)
    with pytest.raises(ValueError):
        data_module.prepare_snapshot(source, name)
    assert not data_module.DATA_DIR.exists()


def test_existing_snapshot_is_not_overwritten(data_module, tmp_path):
    source = write_source(tmp_path)
    snapshot = data_module.prepare_snapshot(source, "fixed")
    original = (snapshot / "panel.parquet").read_bytes()
    with pytest.raises(FileExistsError):
        data_module.prepare_snapshot(source, "fixed")
    assert (snapshot / "panel.parquet").read_bytes() == original


def test_symlinked_data_root_cannot_write_elsewhere(data_module, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    data_module.DATA_DIR.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        data_module.prepare_snapshot(write_source(tmp_path), "escaped")
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("column,value", [
    ("date", "2026-01-06 14:50:00"), ("date", "bad date"),
    ("vt_symbol", "000001.CZCE"), ("open", -1), ("high", 10), ("low", 11),
    ("close", float("inf")), ("volume", -1), ("adj_factor", 0),
    ("limit_up", None), ("limit_down", 12.2),
    ("is_st", "unknown"), ("is_member", None), ("is_member", "2"),
    ("cash_dividend", -0.1), ("split_ratio", 0),
])
def test_invalid_stock_row_is_rejected(data_module, tmp_path, column, value):
    # Each row names a distinct unsafe market-data mutation that must fail closed.
    frame = source_frame()
    if column not in frame.columns:
        frame[column] = 0.0 if column == "cash_dividend" else 1.0
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = value
    source = write_source(tmp_path, frame, suffix=".csv")
    with pytest.raises(ValueError):
        data_module.prepare_snapshot(source, "bad")
    assert not (data_module.DATA_DIR / "bad").exists()


@pytest.mark.parametrize("case", ["missing_column", "duplicate", "missing_index", "outside_calendar", "index_member"])
def test_panel_level_contract_is_enforced(data_module, tmp_path, case):
    frame = source_frame()
    if case == "missing_column":
        frame = frame.drop(columns=["adj_factor"])
    elif case == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    elif case == "missing_index":
        frame = frame.iloc[[0]]
    elif case == "outside_calendar":
        frame.loc[0, "date"] = "2026-01-07"
    elif case == "index_member":
        frame.loc[1, "is_member"] = "true"
    with pytest.raises(ValueError):
        data_module.prepare_snapshot(write_source(tmp_path, frame), "bad")


def test_universe_mode_does_not_claim_verified_historical_membership(data_module, tmp_path):
    source = write_source(tmp_path)
    for mode in ["historical", "static_snapshot", "custom"]:
        _, manifest = data_module.load_snapshot(data_module.prepare_snapshot(source, mode, mode))
        assert manifest["universe_mode"] == mode
        assert manifest["historical_membership_verified"] is False
    with pytest.raises(ValueError):
        data_module.prepare_snapshot(source, "bad", "unrecognised")


def test_source_membership_declaration_remains_explicit(data_module, tmp_path):
    frame = source_frame()
    frame.attrs = {"historical_membership_verified": True, "membership_source": "test source declaration"}
    _, metadata = data_module.load_snapshot(data_module.prepare_snapshot(write_source(tmp_path, frame), "declared"))
    assert metadata["historical_membership_verified"] is True
    assert metadata["membership_verification_basis"] == "source_declaration"
    assert metadata["membership_source"] == "test source declaration"


def test_corporate_action_fields_are_retained_and_factor_gaps_disclosed(data_module, tmp_path):
    frame = source_frame()
    earlier = frame.iloc[[0]].copy()
    earlier["date"] = "2026-01-05"
    frame.loc[0, "adj_factor"] = 1.1
    frame = pd.concat([frame, earlier], ignore_index=True)
    source = write_source(tmp_path, frame)
    _, meta = data_module.load_snapshot(data_module.prepare_snapshot(source, "missing_actions"))
    assert meta["factor_changes_without_actions"] == 1
    assert meta["corporate_actions_required"] is True
    frame["cash_dividend"] = [0.1, 0.0, 0.0, 0.0]
    frame["split_ratio"] = [1.0, 1.0, 1.0, 1.0]
    _, meta = data_module.load_snapshot(data_module.prepare_snapshot(write_source(tmp_path, frame), "actions"))
    assert meta["factor_changes_without_actions"] == 0


def test_load_rejects_tampering_and_outside_paths(data_module, tmp_path):
    snapshot = data_module.prepare_snapshot(write_source(tmp_path), "valid")
    with pytest.raises(ValueError):
        data_module.load_snapshot(tmp_path)
    (snapshot / "panel.parquet").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash|SHA|checksum"):
        data_module.load_snapshot(snapshot)


def test_load_does_not_follow_panel_symlink(data_module, tmp_path):
    snapshot = data_module.prepare_snapshot(write_source(tmp_path), "valid")
    panel = snapshot / "panel.parquet"
    outside = tmp_path / "external.parquet"
    panel.rename(outside)
    panel.symlink_to(outside)
    with pytest.raises(ValueError):
        data_module.load_snapshot(snapshot)


def test_manifest_cannot_redirect_panel_load(data_module, tmp_path):
    snapshot = data_module.prepare_snapshot(write_source(tmp_path), "valid")
    manifest_path = snapshot / "manifest.json"
    metadata = json.loads(manifest_path.read_text())
    metadata["panel_file"] = "../external.parquet"
    manifest_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        data_module.load_snapshot(snapshot)


def test_snapshot_preserves_provider_limitations_and_execution_semantics(data_module, tmp_path):
    frame = source_frame()
    frame.attrs = {
        "provider": "baostock",
        "source": "historical stock API",
        "data_limitations": ["derived_limits", "cash_on_ex_date_before_tax"],
        "execution_semantics": {"limit_reference": "raw_preclose", "dividend_tax": "not_modeled"},
    }
    _, metadata = data_module.load_snapshot(data_module.prepare_snapshot(write_source(tmp_path, frame), "disclosed"))
    assert metadata["provider"] == "baostock"
    assert metadata["data_limitations"] == ["derived_limits", "cash_on_ex_date_before_tax"]
    assert metadata["execution_semantics"]["dividend_tax"] == "not_modeled"
    assert metadata["source_metadata"]["source"] == "historical stock API"
