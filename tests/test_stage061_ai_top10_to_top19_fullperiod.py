from __future__ import annotations

import importlib
import json
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


def test_stage061_preserves_reused_payload_and_detects_drift() -> None:
    runner = _runner()
    source = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "account_equity": [100.0, 101.0],
            "profile": ["source", "source"],
            "experiment_arm": ["C", "C"],
        }
    )
    target = source.copy()
    target["profile"] = "stage061_top14_plus_fu"
    target["experiment_arm"] = "T14"
    target["requested_top_n"] = 14

    runner._assert_relabel_preserves_payload(source, target, context="top14")
    with pytest.raises(RuntimeError, match="stage061_reuse_payload_drift"):
        runner._assert_relabel_preserves_payload(
            source,
            target.assign(account_equity=[100.0, 102.0]),
            context="top14",
        )
    with pytest.raises(RuntimeError, match="stage061_reuse_payload_columns_drift"):
        runner._assert_relabel_preserves_payload(
            source,
            target.drop(columns=["account_equity"]),
            context="top14",
        )


def test_stage061_cost_only_failures_keep_only_capacity_validation_value() -> None:
    runner = _runner()
    comparison = pd.DataFrame(
        {
            "requested_top_n": [10, 11, 12, 13],
            "all_full_period_gates_pass": [False, False, False, False],
            "gate_return_not_lower_than_stage037": [True, True, True, True],
            "gate_drawdown_worsening_le_2pp": [True, True, True, True],
            "gate_sharpe_not_lower_by_more_than_002": [True, True, True, True],
            "gate_slippage_le_105pct_of_stage037": [False, False, False, False],
            "gate_account_survival_pass": [True, True, True, True],
            "gate_broker10_days_over_100_not_worse": [True, True, True, False],
        }
    )

    cost_only = runner._cost_only_fail_top_ns(comparison)
    assessment = runner._continue_value_assessment(comparison)

    assert cost_only == [10, 11, 12]
    assert "容量/成本归一化" in assessment
    assert "继续扫TopN" in assessment
    assert "2019-12-31" in runner.PRE_AI_FU_BOUNDARY_NOTE


def test_stage061_published_reuse_and_decision_artifacts_are_closed() -> None:
    runner = _runner()
    output = runner.OUTPUT_DIR
    summary = pd.read_csv(output / runner.SUMMARY_NAME)
    curve = pd.read_csv(output / runner.CURVE_NAME)
    trades = pd.read_csv(output / runner.TRADES_NAME)
    source_summary = pd.read_csv(runner.STAGE056_DIR / runner.s56.SUMMARY_NAME)
    source_curve = pd.read_csv(runner.STAGE056_DIR / runner.s56.CURVE_NAME)
    source_trades = pd.read_csv(runner.STAGE056_DIR / runner.s56.TRADES_NAME)

    runner._assert_relabel_preserves_payload(
        source_summary[source_summary["experiment_arm"].astype(str).eq("C")],
        summary[summary["requested_top_n"].eq(14)],
        context="published_top14_summary",
    )
    runner._assert_relabel_preserves_payload(
        source_curve[source_curve["experiment_arm"].astype(str).eq("C")],
        curve[curve["requested_top_n"].eq(14)],
        context="published_top14_curve",
    )
    runner._assert_relabel_preserves_payload(
        source_trades[source_trades["experiment_arm"].astype(str).eq("C")],
        trades[trades["requested_top_n"].eq(14)],
        context="published_top14_trades",
    )
    for frame, name in ((summary, "summary"), (curve, "curve"), (trades, "trades")):
        runner._assert_relabel_preserves_payload(
            frame[frame["requested_top_n"].eq(18)],
            frame[frame["requested_top_n"].eq(19)],
            context=f"published_top19_{name}",
        )

    decision = json.loads((output / runner.DECISION_NAME).read_text(encoding="utf-8"))
    assert decision["cost_only_fail_top_ns"] == [10, 11, 12]
    assert "容量/成本归一化" in decision["continue_value_assessment"]
