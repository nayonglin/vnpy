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


def _ranking(eval_date: str = "2026-07-31") -> pd.DataFrame:
    products = [
        "fu.SHFE",
        "jm.DCE",
        "si.GFEX",
        "SA.CZCE",
        "au.SHFE",
        "lc.GFEX",
        "cu.SHFE",
        "SM.CZCE",
        "lh.DCE",
        "AP.CZCE",
        "CF.CZCE",
        "FG.CZCE",
        "MA.CZCE",
        "OI.CZCE",
        "SH.CZCE",
        "hc.SHFE",
        "rb.SHFE",
        "ru.SHFE",
        "sp.SHFE",
    ]
    return pd.DataFrame(
        {
            "eval_date": eval_date,
            "product_vt_symbol": products,
            "score": [1.0 - index / 100 for index in range(len(products))],
        }
    )


def test_stage056_selects_exactly_top14_non_fu_plus_fixed_fu() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")

    selected = runner.select_top14_plus_fu(_ranking())

    assert len(selected) == 15
    assert selected["product_vt_symbol"].nunique() == 15
    assert selected["product_vt_symbol"].eq("fu.SHFE").sum() == 1
    assert selected.loc[selected["product_vt_symbol"].eq("fu.SHFE"), "score_rank"].item() == 15
    assert selected["top_n"].eq(15).all()
    assert selected.loc[~selected["product_vt_symbol"].eq("fu.SHFE"), "product_vt_symbol"].tolist() == [
        "jm.DCE",
        "si.GFEX",
        "SA.CZCE",
        "au.SHFE",
        "lc.GFEX",
        "cu.SHFE",
        "SM.CZCE",
        "lh.DCE",
        "AP.CZCE",
        "CF.CZCE",
        "FG.CZCE",
        "MA.CZCE",
        "OI.CZCE",
        "SH.CZCE",
    ]


def test_stage056_membership_only_month_locks_formal_top8_then_fills_six() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")
    formal_top8 = (
        "SH.CZCE",
        "jm.DCE",
        "cu.SHFE",
        "FG.CZCE",
        "SA.CZCE",
        "sp.SHFE",
        "ru.SHFE",
        "lh.DCE",
    )

    selected = runner.select_top14_plus_fu(
        _ranking("2026-03-31"),
        locked_non_fu=formal_top8,
        provenance="membership_locked_score_fill",
    )

    selected_non_fu = set(
        selected.loc[
            ~selected["product_vt_symbol"].eq("fu.SHFE"), "product_vt_symbol"
        ].astype(str)
    )
    assert set(formal_top8).issubset(selected_non_fu)
    assert len(selected_non_fu - set(formal_top8)) == 6
    assert selected["score_type"].eq("membership_locked_score_fill").all()


def test_stage056_preserves_static18_pre_ai_boundary() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")
    formal = pd.DataFrame(
        {
            "strategy": ["old"] * 18,
            "score_type": ["static18_pre_ai_boundary"] * 18,
            "eval_date": ["2019-12-31"] * 18,
            "product_vt_symbol": [f"p{index}" for index in range(18)],
            "score": [0.0] * 18,
            "score_rank": list(range(1, 19)),
            "top_n": [18] * 18,
        }
    )

    preserved = runner.preserve_pre_ai_boundary(formal)

    assert preserved["product_vt_symbol"].tolist() == formal["product_vt_symbol"].tolist()
    assert preserved["score_rank"].tolist() == list(range(1, 19))
    assert preserved["top_n"].eq(18).all()
    assert preserved["strategy"].eq(runner.CANDIDATE_AI_STRATEGY).all()


def test_stage056_missing_or_duplicate_rankings_fail_closed() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")

    with pytest.raises(RuntimeError, match="ranking_has_fewer_than_14_non_fu"):
        runner.select_top14_plus_fu(_ranking().head(10))

    duplicated = pd.concat([_ranking(), _ranking().iloc[[1]]], ignore_index=True)
    with pytest.raises(RuntimeError, match="duplicate_ranking_product"):
        runner.select_top14_plus_fu(duplicated)


def test_stage056_candidate_changes_only_ai_pool_path_and_strategy() -> None:
    config = importlib.import_module(
        "qmt_roll_candidate_stage056_stage037_ai_top14_plus_fu_config"
    )

    assert set(config.override_diff()) == {
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }
    overrides = config.build_candidate_overrides()
    assert overrides["ai_product_pool_strategy"] == config.CANDIDATE_AI_STRATEGY
    assert Path(overrides["ai_product_pool_eligibility_path"]) == config.CANDIDATE_ELIGIBILITY_PATH
    assert config.BASE_RULESET_VERSION == "stage037_stage034_long_short_mirror_hard_block_v1"


def test_stage056_identity_parity_fails_closed_on_production_drift() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")
    identity = {"ruleset_version": "stage037", "material_release_id": "m0016"}

    runner._assert_identity_parity(
        identity,
        identity.copy(),
        checkout_head="same",
        production_head="same",
        remote_master="same",
    )
    with pytest.raises(RuntimeError, match="formal_identity_mismatch_stop"):
        runner._assert_identity_parity(
            identity,
            {"ruleset_version": "stage021", "material_release_id": "m0015"},
            checkout_head="new",
            production_head="old",
            remote_master="new",
        )


def test_stage056_published_artifacts_close_selection_and_risk_contracts() -> None:
    runner = importlib.import_module("stage056_stage037_ai_top14_plus_fu_ac")
    artifact = (
        ROOT
        / "research"
        / "lines"
        / "futures_trend_rollover_shape_same_volume"
        / "artifacts"
        / "stage056_stage037_ai_top14_plus_fu"
    )
    eligibility = pd.read_csv(artifact / "stage056_candidate_eligibility.csv")
    decision = json.loads((artifact / "stage056_decision.json").read_text(encoding="utf-8"))
    summary = pd.read_csv(artifact / "stage056_summary.csv").set_index("experiment_arm")
    formal = pd.read_csv(runner.FORMAL_ELIGIBILITY_PATH)

    post_ai = eligibility[eligibility["eval_date"].astype(str).ne("2019-12-31")]
    assert post_ai.groupby("eval_date")["product_vt_symbol"].nunique().eq(15).all()
    assert post_ai.groupby("eval_date")["product_vt_symbol"].apply(
        lambda products: products.astype(str).eq("fu.SHFE").sum()
    ).eq(1).all()
    for eval_date, formal_month in formal.groupby(formal["eval_date"].astype(str)):
        candidate_products = set(
            eligibility.loc[
                eligibility["eval_date"].astype(str).eq(eval_date), "product_vt_symbol"
            ].astype(str)
        )
        assert set(formal_month["product_vt_symbol"].astype(str)).issubset(candidate_products)
    assert decision["gates"]["selector_contract_pass"] is True
    assert decision["gates"]["only_ai_pool_path_and_strategy_changed"] is True
    assert decision["gates"]["candidate_max_drawdown_not_worse"] is False
    assert decision["gates"]["candidate_sharpe_not_lower_than_formal"] is False
    assert decision["gates"]["candidate_broker10_100_pass"] is False
    assert decision["gates"]["formal_identity_parity_pass"] is False
    assert decision["identity_gate"]["pass"] is False
    assert decision["post_review_annotation"]["numerical_results_changed_by_review"] is False
    assert decision["post_review_annotation"]["governance_fields_added_after_independent_review"] is True
    assert decision["decision"] == (
        "protocol_invalid_production_identity_drift_keep_offline_diagnostic_only_do_not_promote"
    )
    assert decision["source_identity"]["database_latest_daily_date"] == "2026-08-28"
    assert decision["source_identity"]["database_sha256"]
    assert decision["source_identity"]["stage183_position_changes_sha256"]
    assert decision["source_identity"]["stage183_entry_snapshots_sha256"]
    assert decision["promote_to_official"] is False
    assert decision["order_api_called_count"] == 0
    assert summary.loc["A", "profile"] == "stage056_A_master_m0016_stage037_top8_plus_fu"
    assert "离线基线" in summary.loc["A", "label"]
    assert summary.loc["C", "analysis_end"] == "2026-08-28"
