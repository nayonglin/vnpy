from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/stage002_event_feature_qualification.py"


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location("v4_event_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_keeps_protocol_and_targets_only_v4(module, tmp_path):
    runner = module.load_runner()
    assert runner.LINE_ID == ROOT.name
    assert runner.CLAIM_PATH.is_relative_to(ROOT)
    assert runner.FINAL_DIR.is_relative_to(ROOT)
    assert runner.FAILURE_DIR.is_relative_to(ROOT)
    assert runner.extract_formal_event_features is module.extract_formal_event_features
    paths = {key: tmp_path / key for key in ("profile", "worker_root", "runtime", "receipt", "feature")}
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    command = runner.worker_command(paths, "A1", manifest, tmp_path / "probe")
    assert command[7] == str(TOOL)
    assert command[4:7] == ["-I", "-S", "-B"]
    thresholds = runner.stage002_thresholds(runner.load_feature_module())
    assert (thresholds.min_events, thresholds.min_products) == (150, 15)
    assert thresholds.full_years == (2023, 2024, 2025)


@pytest.mark.parametrize("fail_replay", [False, True])
def test_redirect_survives_repeated_writes_and_restores_on_replay_failure(
    module, tmp_path, monkeypatch, fail_replay,
):
    support = module.load_runner().load_metadata_preflight_module()
    original = (tmp_path / "formal_universe.csv", tmp_path / "formal_eligibility.csv")
    original[0].write_bytes(b"u\n")
    original[1].write_bytes(b"e\n")
    before = [path.stat().st_mtime_ns for path in original]
    candidate_file = tmp_path / "candidate.py"
    candidate_file.touch()
    candidate = SimpleNamespace(
        __file__=str(candidate_file), UNIVERSE_PATH=original[0],
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=original[1],
    )
    monkeypatch.setitem(sys.modules, module.CANDIDATE_MODULE_NAME, candidate)
    calls = []

    def writes():
        assert candidate.UNIVERSE_PATH != original[0]
        candidate.UNIVERSE_PATH.write_bytes(b"u\n")
        candidate.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_bytes(b"e\n")

    def metadata():
        writes()
        return {"vt_symbols": ["a.DCE"], "product_symbols": ["a.DCE"], **{
            key: {"a.DCE": "static" if key == "metadata_sources" else 1}
            for key in ("rates", "slippages", "sizes", "priceticks", "margin_ratios",
                        "metadata_sources", "source_symbol_by_contract")
        }}

    def replay(*_args):
        calls.append("replay")
        writes()
        if fail_replay:
            raise RuntimeError("replay failed")
        return object(), {"entry_candidates": SimpleNamespace(copy=lambda: "candidates")}, SimpleNamespace(
            capital=SimpleNamespace(account_capital=150000), profile="formal",
        )

    context = {"s901": SimpleNamespace(
        s513=SimpleNamespace(_metadata=metadata),
        s847=SimpleNamespace(QmtRollPortfolioStrategyStage847C9StopRetry=object),
        _run_live_c9=replay,
    ), "live_config": SimpleNamespace(OFFICIAL_LIVE_PROFILE_NAME="formal")}
    v1 = SimpleNamespace(
        START="2020-01-02", END="2026-08-28", EXPECTED_CAPITAL=150000,
        _active_formal_identity=lambda: {"eligibility_path": "/frozen.csv"},
        _install_correlation_trace_instrumentation=lambda _cls: lambda: calls.append("restored"),
        pd=SimpleNamespace(read_csv=lambda _path: "eligibility"),
    )
    worker = tmp_path / "worker"
    worker.mkdir()
    kwargs = dict(
        worker_root=worker, expected_outputs=dict(universe=original[0], post_signal_eligibility=original[1]),
        expected_candidate_module_path=candidate_file, v1=v1,
        feature_module=SimpleNamespace(build_formal_root_event_features=lambda *_args: "features"),
        metadata_preflight=support,
    )
    if fail_replay:
        with pytest.raises(RuntimeError, match="replay failed"):
            module.extract_formal_event_features(context, **kwargs)
    else:
        features, _, evidence = module.extract_formal_event_features(context, **kwargs)
        assert features == "features"
        assert evidence["metadata_output_paths_restored"] is True
    assert calls == ["replay", "restored"]
    assert candidate.UNIVERSE_PATH is original[0]
    assert candidate.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH is original[1]
    assert [path.stat().st_mtime_ns for path in original] == before


def test_inventory_contains_profile_evidence_and_new_code(module):
    files = module.collect_input_files()
    assert len(files) == 1458
    assert files["v4_stage002_runner"] == TOOL
    assert files["v4_stage001_A1_receipt"].is_file()
    assert files["v4_stage001_A2_receipt"].is_file()
