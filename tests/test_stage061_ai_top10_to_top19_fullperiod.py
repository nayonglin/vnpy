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
    return importlib.import_module("qmt_roll_candidate_stage061_ai_topn_width_config")


def _runner():
    return importlib.import_module("stage061_ai_top10_to_top19_fullperiod")


def _ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2026-07-31"] * 18,
            "product_vt_symbol": [f"p{rank}.TEST" for rank in range(1, 19)],
            "score": [float(100 - rank) for rank in range(1, 19)],
            "simple_trend_suitability_score": [0.0] * 18,
        }
    )


def test_stage061_freezes_all_requested_topn_arms_and_caps_only_top19() -> None:
    runner = _runner()

    assert runner.TOP_NS == tuple(range(10, 20))
    assert [arm["requested_top_n"] for arm in runner.ARMS] == list(range(10, 20))
    assert [arm["actual_ranked_count"] for arm in runner.ARMS] == [
        10, 11, 12, 13, 14, 15, 16, 17, 18, 18
    ]
    assert [arm["actual_total_count"] for arm in runner.ARMS] == [
        11, 12, 13, 14, 15, 16, 17, 18, 19, 19
    ]
    assert runner.START == pd.Timestamp("2018-01-01")
    assert runner.END == pd.Timestamp("2026-08-28")
    assert "OFFLINE" in runner.PLOT_TITLE


def test_stage061_selects_ranked_non_fu_and_fixed_fu_without_duplicates() -> None:
    runner = _runner()

    top10 = runner.select_topn_plus_fu(_ranking(), requested_top_n=10)
    top19 = runner.select_topn_plus_fu(_ranking(), requested_top_n=19)

    assert list(top10["product_vt_symbol"][:-1]) == [f"p{rank}.TEST" for rank in range(1, 11)]
    assert top10.iloc[-1]["product_vt_symbol"] == "fu.SHFE"
    assert top10["product_vt_symbol"].nunique() == 11
    assert top19["product_vt_symbol"].nunique() == 19
    assert set(top19["product_vt_symbol"]) == {
        *(f"p{rank}.TEST" for rank in range(1, 19)),
        "fu.SHFE",
    }


def test_stage061_candidate_config_keeps_ai_enabled_and_changes_only_membership() -> None:
    config = _config()
    candidate_path = ROOT / "tmp" / "top10.csv"
    overrides = config.build_candidate_overrides(10, candidate_path)
    diff = config.override_diff(10, candidate_path)

    assert overrides["enable_ai_product_pool_filter"] is True
    assert overrides["ai_product_pool_eligibility_path"] == str(candidate_path.resolve())
    assert overrides["ai_product_pool_strategy"] == "ai_top10_plus_fu_width_sweep"
    assert set(diff) == {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}
    assert config.build_candidate_overrides(19, candidate_path)[
        "ai_product_pool_strategy"
    ] == "ai_top19_plus_fu_width_sweep"


def test_stage061_reuses_top14_and_top19_duplicate_but_runs_other_arms() -> None:
    runner = _runner()

    assert runner.REUSED_TOP_NS == {14: "stage056_top14", 19: "stage061_top18_duplicate"}
    assert runner.ENGINE_RUN_TOP_NS == (10, 11, 12, 13, 15, 16, 17, 18)


def test_stage061_offline_identity_fails_closed_on_wrong_stage037() -> None:
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
    assert evidence["research_protocol"] == "explicit_stage037_ai_top10_to_top19_offline_width_sweep"
    assert evidence["formal_production_ac_compliant"] is False
    assert evidence["promotion_permitted"] is False

    with pytest.raises(RuntimeError, match="stage061_stage037_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity={**stage037, "ruleset_version": "wrong"},
            production_identity=production_q,
            remote_master=runner.BASE_MASTER_COMMIT,
        )


def test_stage061_full_period_gate_compares_every_arm_to_stage037() -> None:
    runner = _runner()
    passing = {
        "candidate_total_return_pct": 101.0,
        "baseline_total_return_pct": 100.0,
        "candidate_max_dd_pct": -42.0,
        "baseline_max_dd_pct": -40.0,
        "candidate_sharpe": 0.98,
        "baseline_sharpe": 1.0,
        "candidate_total_slippage": 105.0,
        "baseline_total_slippage": 100.0,
        "candidate_account_survival_pass": 1,
        "candidate_days_over_100pct": 0,
        "baseline_days_over_100pct": 0,
    }

    assert all(runner._full_period_gates(passing).values())
    assert runner._full_period_gates({**passing, "candidate_total_slippage": 105.001})[
        "slippage_le_105pct_of_stage037"
    ] is False
