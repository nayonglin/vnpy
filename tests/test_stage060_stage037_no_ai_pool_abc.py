from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "examples" / "portfolio_backtesting"
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
for path in (PORTFOLIO, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _config():
    return importlib.import_module("qmt_roll_candidate_stage060_stage037_no_ai_config")


def _runner():
    return importlib.import_module("stage060_stage037_no_ai_pool_abc")


def test_stage060_changes_only_ai_filter_switch_and_keeps_19_product_universe() -> None:
    config = _config()
    from main_contract_mapping import load_product_universe_symbols

    assert config.override_diff() == {"enable_ai_product_pool_filter": (True, False)}
    formal = config.live_cfg.build_official_live_strategy_overrides()
    candidate = config.build_candidate_overrides()
    assert candidate["enable_ai_product_pool_filter"] is False
    assert candidate["product_universe_csv_path"] == formal["product_universe_csv_path"]
    assert candidate["ai_product_pool_eligibility_path"] == formal["ai_product_pool_eligibility_path"]
    assert candidate["ai_product_pool_strategy"] == formal["ai_product_pool_strategy"]
    products = load_product_universe_symbols(candidate["product_universe_csv_path"])
    assert len(products) == 19
    assert len(set(products)) == 19
    assert "fu.SHFE" in products


def test_stage060_freezes_stage037_stage056_and_no_ai_arms() -> None:
    runner = _runner()

    assert [arm["arm"] for arm in runner.ARMS] == ["A", "B", "C"]
    assert runner.ARMS[0]["profile"] == "stage060_A_stage037_top8_plus_fu"
    assert runner.ARMS[1]["profile"] == "stage060_B_stage056_top14_plus_fu"
    assert runner.ARMS[2]["profile"] == "stage060_C_stage037_no_ai_static18_plus_fu"
    assert runner.TOTAL_PRODUCT_COUNT == 19
    assert runner.START == pd.Timestamp("2018-01-01")
    assert runner.END == pd.Timestamp("2026-08-28")


def test_stage060_offline_identity_is_explicit_and_fails_on_wrong_stage037() -> None:
    runner = _runner()
    stage037 = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": runner.BASE_RULESET_VERSION,
        "material_release_id": runner.BASE_RELEASE_ID,
        "source_commit": runner.BASE_SOURCE_COMMIT,
    }
    production_q = {**stage037, "ruleset_version": "stage021_q_rollover_volume_atr_v1"}

    evidence = runner._assert_offline_identity_contract(
        checkout_identity=stage037,
        production_identity=production_q,
        remote_master=runner.BASE_MASTER_COMMIT,
    )
    assert evidence["research_protocol"] == "explicit_stage037_stage056_no_ai_offline_ablation"
    assert evidence["production_identity_matches_stage037"] is False
    assert evidence["formal_production_ac_compliant"] is False
    assert evidence["promotion_permitted"] is False

    with pytest.raises(RuntimeError, match="stage060_stage037_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity={**stage037, "ruleset_version": "wrong"},
            production_identity=production_q,
            remote_master=runner.BASE_MASTER_COMMIT,
        )


def test_stage060_reuses_stage056_ab_metrics_without_relabeling_drift() -> None:
    runner = _runner()
    summary, curve = runner._load_reused_ab()
    source_summary = pd.read_csv(runner.STAGE056_DIR / runner.s56.SUMMARY_NAME).set_index(
        "experiment_arm"
    )
    by_arm = summary.set_index("experiment_arm")

    assert set(by_arm.index) == {"A", "B"}
    assert by_arm.loc["A", "profile"] == runner.ARMS[0]["profile"]
    assert by_arm.loc["B", "profile"] == runner.ARMS[1]["profile"]
    assert by_arm.loc["A", "end_equity"] == source_summary.loc["A", "end_equity"]
    assert by_arm.loc["B", "end_equity"] == source_summary.loc["C", "end_equity"]
    assert set(curve["experiment_arm"].astype(str)) == {"A", "B"}

    source_curve = pd.read_csv(runner.STAGE056_DIR / runner.s56.CURVE_NAME)
    for target, source in (("A", "A"), ("B", "C")):
        target_row = by_arm.loc[target]
        source_row = source_summary.loc[source]
        numeric = [
            column
            for column in source_summary.columns
            if pd.api.types.is_numeric_dtype(source_summary[column])
        ]
        for column in numeric:
            assert target_row[column] == pytest.approx(source_row[column], nan_ok=True)
        target_equity = curve.loc[
            curve["experiment_arm"].astype(str).eq(target), "account_equity"
        ].reset_index(drop=True)
        source_equity = source_curve.loc[
            source_curve["experiment_arm"].astype(str).eq(source), "account_equity"
        ].reset_index(drop=True)
        pd.testing.assert_series_equal(target_equity, source_equity, check_names=False)


def test_stage060_candidate_frames_are_never_labeled_as_live() -> None:
    runner = _runner()
    source = pd.DataFrame(
        {
            "profile": ["stage847_c9_15w_stage819_05r_stop_retry_live"],
            "variant": ["stage847_c9_15w_stage819_05r_stop_retry_live"],
            "arm": ["stage847_c9_15w_stage819_05r_stop_retry_live"],
            "label": ["live"],
        }
    )

    labeled = runner._label_candidate_frame(source)

    assert set(labeled["experiment_arm"]) == {"C"}
    for column in ("profile", "variant", "arm"):
        assert set(labeled[column]) == {runner.ARMS[2]["profile"]}
    assert set(labeled["label"]) == {runner.ARMS[2]["label"]}
    assert "OFFLINE" in runner.PLOT_TITLE
    assert "离线研究" in runner.REPORT_BANNER


def test_stage060_full_period_gate_requires_risk_cost_and_capacity_noninferiority() -> None:
    runner = _runner()
    passing = {
        "C_total_return_pct": 101.0,
        "A_total_return_pct": 100.0,
        "C_max_dd_pct": -42.0,
        "A_max_dd_pct": -40.0,
        "C_sharpe": 0.98,
        "A_sharpe": 1.0,
        "C_total_slippage": 105.0,
        "A_total_slippage": 100.0,
        "C_account_survival_pass": 1,
        "C_days_over_100pct": 0,
        "A_days_over_100pct": 0,
    }

    assert all(runner._full_period_gates(passing).values())
    assert runner._full_period_gates({**passing, "C_total_slippage": 105.001})[
        "slippage_le_105pct_of_stage037"
    ] is False
