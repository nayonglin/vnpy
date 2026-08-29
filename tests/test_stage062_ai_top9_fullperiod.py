from __future__ import annotations

import importlib
import json
import math
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


def _runner():
    try:
        return importlib.import_module("stage062_ai_top9_fullperiod")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stage062 runner is not implemented: {exc}")


def _config():
    try:
        return importlib.import_module("qmt_roll_candidate_stage062_ai_top9_config")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stage062 config is not implemented: {exc}")


def _ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2026-07-31"] * 18,
            "product_vt_symbol": [f"p{rank}.TEST" for rank in range(1, 19)],
            "score": [float(100 - rank) for rank in range(1, 19)],
            "simple_trend_suitability_score": [0.0] * 18,
        }
    )


def test_stage062_freezes_top9_as_only_new_engine_arm() -> None:
    runner = _runner()

    assert runner.STAGE == "Stage062"
    assert runner.TOP_N == 9
    assert runner.NEW_ENGINE_TOP_NS == (9,)
    assert runner.REUSED_STAGE061_TOP_NS == tuple(range(10, 20))
    assert runner.START == pd.Timestamp("2018-01-01")
    assert runner.END == pd.Timestamp("2026-08-28")
    assert runner.TOP9_ARM == {
        "arm": "T9",
        "requested_top_n": 9,
        "actual_ranked_count": 9,
        "actual_total_count": 10,
        "profile": "stage062_top9_plus_fu",
        "label": "Top9+fu（实际10品种）",
        "plot_label": "Top9",
    }


def test_stage062_selects_exact_top9_non_fu_plus_fixed_fu() -> None:
    runner = _runner()

    selected = runner.select_top9_plus_fu(_ranking())

    assert list(selected["product_vt_symbol"][:-1]) == [
        f"p{rank}.TEST" for rank in range(1, 10)
    ]
    assert selected.iloc[-1]["product_vt_symbol"] == "fu.SHFE"
    assert selected["product_vt_symbol"].nunique() == 10
    assert selected["top_n"].astype(int).eq(10).all()


def test_stage062_config_keeps_ai_enabled_and_changes_only_membership() -> None:
    config = _config()
    candidate_path = ROOT / "tmp" / "stage062_top9.csv"

    overrides = config.build_candidate_overrides(candidate_path)
    diff = config.override_diff(candidate_path)

    assert overrides["enable_ai_product_pool_filter"] is True
    assert overrides["ai_product_pool_eligibility_path"] == str(candidate_path.resolve())
    assert overrides["ai_product_pool_strategy"] == "ai_top9_plus_fu_boundary_check"
    assert set(diff) == {
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }


def test_stage062_offline_identity_keeps_stage037_and_stage061_frozen() -> None:
    runner = _runner()
    stage037 = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": runner.BASE_RULESET_VERSION,
        "material_release_id": runner.BASE_RELEASE_ID,
        "source_commit": runner.BASE_SOURCE_COMMIT,
    }

    evidence = runner._assert_offline_identity_contract(
        checkout_identity=stage037,
        production_identity={**stage037, "ruleset_version": "stage021_q_rollover_volume_atr_v1"},
        remote_master=runner.BASE_MASTER_COMMIT,
    )

    assert evidence["research_protocol"] == "explicit_stage037_ai_top9_offline_boundary_check"
    assert evidence["stage061_source_commit"] == runner.BASE_STAGE061_COMMIT
    assert evidence["formal_production_ac_compliant"] is False
    assert evidence["promotion_permitted"] is False

    with pytest.raises(RuntimeError, match="stage062_stage037_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity={**stage037, "source_commit": "wrong"},
            production_identity=stage037,
            remote_master=runner.BASE_MASTER_COMMIT,
        )


def test_stage062_full_period_gate_is_unchanged_from_stage061() -> None:
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
    assert runner._full_period_gates(
        {**passing, "candidate_total_slippage": 105.001}
    )["slippage_le_105pct_of_stage037"] is False


def test_stage062_reuses_stage061_reference_and_top10_to_top19_exactly() -> None:
    runner = _runner()

    summaries, curves, trades = runner._load_stage061_artifacts()

    assert set(summaries) == {"REF", *range(10, 20)}
    assert set(curves) == {"REF", *range(10, 20)}
    assert set(trades) == set(range(10, 20))
    assert len(curves["REF"]) == 2101
    assert all(len(curves[top_n]) == 2101 for top_n in range(10, 20))


def test_stage062_published_artifacts_include_top9_and_preserve_stage061() -> None:
    runner = _runner()
    output = runner.OUTPUT_DIR
    summary = pd.read_csv(output / runner.SUMMARY_NAME)
    curve = pd.read_csv(output / runner.CURVE_NAME)
    trades = pd.read_csv(output / runner.TRADES_NAME)
    source_summary = pd.read_csv(runner.STAGE061_DIR / runner.s61.SUMMARY_NAME)
    source_curve = pd.read_csv(runner.STAGE061_DIR / runner.s61.CURVE_NAME)
    source_trades = pd.read_csv(runner.STAGE061_DIR / runner.s61.TRADES_NAME)
    eligibility = pd.read_csv(output / runner.ELIGIBILITY_NAME)
    membership = pd.read_csv(output / runner.MEMBERSHIP_AUDIT_NAME)
    ranking_audit = pd.read_csv(output / runner.RANKING_AUDIT_NAME)

    assert set(summary["experiment_arm"].astype(str)) == {
        "REF", "T9", *(f"T{top_n}" for top_n in range(10, 20))
    }
    assert len(curve[curve["experiment_arm"].astype(str).eq("T9")]) == 2101
    for source, target in (
        (source_summary, summary[~summary["experiment_arm"].astype(str).eq("T9")]),
        (source_curve, curve[~curve["experiment_arm"].astype(str).eq("T9")]),
        (source_trades, trades[~trades["experiment_arm"].astype(str).eq("T9")]),
    ):
        pd.testing.assert_frame_equal(
            source.reset_index(drop=True),
            target[source.columns].reset_index(drop=True),
            check_dtype=False,
        )

    decision = json.loads((output / runner.DECISION_NAME).read_text(encoding="utf-8"))
    assert decision["frozen_scope"]["new_engine_top_ns"] == [9]
    assert decision["frozen_scope"]["reused_stage061_top_ns"] == list(range(10, 20))
    assert decision["order_api_called_count"] == 0
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False

    assert len(membership) == 55
    assert membership["actual_ranked_count"].astype(int).eq(9).all()
    assert membership["actual_total_count"].astype(int).eq(10).all()
    assert membership["formal_top8_preserved"].astype(bool).all()
    assert membership["fixed_fu_present"].astype(bool).all()
    mismatches = membership[~membership["strict_model_top9_match"].astype(bool)]
    assert mismatches["eval_date"].astype(str).tolist() == ["2026-03-31", "2026-05-29"]
    assert mismatches["added_vs_strict_top9"].tolist() == [
        "lh.DCE,sp.SHFE",
        "rb.SHFE",
    ]
    assert mismatches["excluded_vs_strict_top9"].tolist() == [
        "au.SHFE,si.GFEX",
        "ru.SHFE",
    ]
    assert set(membership["membership_policy"].astype(str)) == {
        "strict_model_top9_plus_fixed_fu",
        "formal_top8_locked_then_same_month_model_fill_to_9_plus_fixed_fu",
    }
    pre_ai = eligibility[eligibility["eval_date"].astype(str).eq("2019-12-31")]
    assert len(pre_ai) == 18
    assert "fu.SHFE" not in set(pre_ai["product_vt_symbol"].astype(str))
    assert len(ranking_audit) == 990
    assert ranking_audit["eval_date"].nunique() == 55
    assert set(ranking_audit["ranking_provenance"].astype(str)) == {
        "frozen_market_walkforward_v2",
        "stage189_rerun_membership_locked_fill",
        "stage182_point_in_time_replay",
        "formal_m0016_latest_pool",
    }

    top9_summary = summary[summary["experiment_arm"].astype(str).eq("T9")].iloc[0]
    top9_curve = curve[curve["experiment_arm"].astype(str).eq("T9")].copy().sort_values("date")
    equity = pd.to_numeric(top9_curve["account_equity"], errors="raise")
    recomputed_dd = float((equity / equity.cummax() - 1.0).min() * 100.0)
    daily_returns = equity.ffill().pct_change().replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    recomputed_sharpe = float(
        daily_returns.mean() / daily_returns.std(ddof=1) * math.sqrt(252.0)
    )
    recomputed_slippage = float(
        pd.to_numeric(top9_curve["total_slippage"], errors="raise").sum()
    )
    recomputed_trade_count = int(
        pd.to_numeric(top9_curve["trade_count"], errors="raise").sum()
    )
    net_pnl = pd.to_numeric(top9_curve["net_pnl"], errors="raise")
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]
    recomputed_win_rate = float(nonzero_pnl.gt(0.0).mean() * 100.0)
    assert float(top9_summary["end_equity"]) == pytest.approx(16_871_625.40)
    assert float(top9_summary["total_return_pct"]) == pytest.approx(11_147.7502666667)
    assert float(top9_summary["max_dd_pct"]) == pytest.approx(recomputed_dd)
    assert float(top9_summary["sharpe"]) == pytest.approx(recomputed_sharpe)
    assert float(top9_summary["total_slippage"]) == pytest.approx(recomputed_slippage)
    assert int(top9_summary["total_trade_count"]) == recomputed_trade_count
    assert float(top9_summary["nonzero_daily_win_rate_pct"]) == pytest.approx(
        recomputed_win_rate
    )
    top9_comparison = pd.read_csv(output / runner.COMPARISON_NAME).query(
        "requested_top_n == 9"
    ).iloc[0]
    failed_gate_columns = {
        column
        for column in top9_comparison.index
        if column.startswith("gate_") and not bool(top9_comparison[column])
    }
    assert failed_gate_columns == {
        "gate_sharpe_not_lower_by_more_than_002",
        "gate_slippage_le_105pct_of_stage037",
    }

    reference_summary = summary[summary["experiment_arm"].astype(str).eq("REF")].iloc[0]
    reference_curve = curve[
        curve["experiment_arm"].astype(str).eq("REF")
    ].copy().sort_values("date")
    reference_equity = pd.to_numeric(reference_curve["account_equity"], errors="raise")
    reference_returns = (
        reference_equity.ffill()
        .pct_change()
        .replace([float("inf"), float("-inf")], pd.NA)
        .fillna(0.0)
    )
    reference_sharpe = float(
        reference_returns.mean()
        / reference_returns.std(ddof=1)
        * math.sqrt(252.0)
    )
    independently_recomputed_gates = runner._full_period_gates(
        {
            "candidate_total_return_pct": float(
                (equity.iloc[-1] / float(top9_curve["account_capital"].iloc[0]) - 1.0)
                * 100.0
            ),
            "baseline_total_return_pct": float(
                (
                    reference_equity.iloc[-1]
                    / float(reference_curve["account_capital"].iloc[0])
                    - 1.0
                )
                * 100.0
            ),
            "candidate_max_dd_pct": recomputed_dd,
            "baseline_max_dd_pct": float(
                (reference_equity / reference_equity.cummax() - 1.0).min() * 100.0
            ),
            "candidate_sharpe": recomputed_sharpe,
            "baseline_sharpe": reference_sharpe,
            "candidate_total_slippage": recomputed_slippage,
            "baseline_total_slippage": float(
                pd.to_numeric(reference_curve["total_slippage"], errors="raise").sum()
            ),
            "candidate_account_survival_pass": int(equity.min() > 0.0),
            "candidate_days_over_100pct": int(
                pd.to_numeric(
                    top9_curve["broker10_margin_to_equity_pct"], errors="raise"
                ).gt(100.0 + 1e-9).sum()
            ),
            "baseline_days_over_100pct": int(
                pd.to_numeric(
                    reference_curve["broker10_margin_to_equity_pct"], errors="raise"
                ).gt(100.0 + 1e-9).sum()
            ),
        }
    )
    assert {key for key, value in independently_recomputed_gates.items() if not value} == {
        "sharpe_not_lower_by_more_than_002",
        "slippage_le_105pct_of_stage037",
    }
    assert float(reference_summary["sharpe"]) == pytest.approx(reference_sharpe)

    source_identity = decision["source_identity"]
    assert source_identity["candidate_eligibility_sha256"] == runner._file_sha256(
        runner.ELIGIBILITY_PATH
    )
    assert source_identity["formal_eligibility_sha256"] == runner._file_sha256(
        runner.s61.s56.FORMAL_ELIGIBILITY_PATH
    )
    assert source_identity["ranking_audit_sha256"] == runner._file_sha256(
        runner.RANKING_AUDIT_PATH
    )
    assert source_identity["ranking_provenance_counts"] == {
        "frozen_market_walkforward_v2": 900,
        "stage189_rerun_membership_locked_fill": 54,
        "stage182_point_in_time_replay": 18,
        "formal_m0016_latest_pool": 18,
    }
    assert decision["frozen_scope"]["strict_model_top9_match_month_count"] == 53
    assert decision["frozen_scope"]["strict_model_top9_mismatch_dates"] == [
        "2026-03-31",
        "2026-05-29",
    ]

    formal = pd.read_csv(runner.s61.s56.FORMAL_ELIGIBILITY_PATH)
    formal["eval_date"] = pd.to_datetime(formal["eval_date"]).dt.date.astype(str)
    candidate = eligibility.copy()
    candidate["eval_date"] = pd.to_datetime(candidate["eval_date"]).dt.date.astype(str)
    ranking = ranking_audit.copy()
    ranking["eval_date"] = pd.to_datetime(ranking["eval_date"]).dt.date.astype(str)
    independently_found_mismatches: dict[str, tuple[set[str], set[str]]] = {}
    for eval_date in sorted(ranking["eval_date"].unique()):
        ranked_month = ranking[ranking["eval_date"].eq(eval_date)].sort_values(
            "source_rank"
        )
        strict_top9 = set(
            ranked_month.head(9)["product_vt_symbol"].astype(str)
        )
        candidate_month = candidate[candidate["eval_date"].eq(eval_date)]
        candidate_non_fu = candidate_month[
            ~candidate_month["product_vt_symbol"].astype(str).eq("fu.SHFE")
        ]
        candidate_products = set(candidate_non_fu["product_vt_symbol"].astype(str))
        formal_month = formal[formal["eval_date"].eq(eval_date)]
        formal_top8 = set(
            formal_month.loc[
                ~formal_month["product_vt_symbol"].astype(str).eq("fu.SHFE"),
                "product_vt_symbol",
            ].astype(str)
        )
        assert len(candidate_products) == 9
        assert formal_top8.issubset(candidate_products)
        ranking_scores = ranked_month.set_index("product_vt_symbol")["score"]
        for row in candidate_non_fu.itertuples(index=False):
            assert float(row.score) == pytest.approx(
                float(ranking_scores.loc[str(row.product_vt_symbol)])
            )
        added = candidate_products - strict_top9
        excluded = strict_top9 - candidate_products
        if added or excluded:
            independently_found_mismatches[eval_date] = (added, excluded)
    assert independently_found_mismatches == {
        "2026-03-31": (
            {"lh.DCE", "sp.SHFE"},
            {"au.SHFE", "si.GFEX"},
        ),
        "2026-05-29": ({"rb.SHFE"}, {"ru.SHFE"}),
    }
