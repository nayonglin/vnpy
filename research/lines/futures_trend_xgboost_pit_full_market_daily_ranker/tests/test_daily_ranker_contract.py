from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import daily_ranker_contract as contract


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "datetime": [
                "2022-01-03",
                "2022-01-04",
                "2022-01-03",
                "2022-01-04",
            ],
            "symbol": ["A2205", "A2205", "A2209", "A2209"],
            "exchange": ["DCE", "DCE", "DCE", "DCE"],
            "interval": ["d", "d", "d", "d"],
            "close_price": [100.0, 110.0, 200.0, 220.0],
            "volume": [100.0, 120.0, 80.0, 90.0],
            "open_interest": [200.0, 210.0, 150.0, 160.0],
        }
    )


def test_mapped_return_uses_the_selected_contracts_own_prior_close() -> None:
    mapping = pd.DataFrame(
        {
            "date": ["2022-01-03", "2022-01-04"],
            "continuous_symbol_vt": ["a.DCE", "a.DCE"],
            "main_contract_vt": ["A2205.DCE", "A2209.DCE"],
        }
    )

    contract_bars = contract.build_contract_bar_table(_bars())
    history, diagnostics = contract.build_mapped_product_history(
        mapping,
        contract_bars,
    )

    switch_return = history.loc[
        history["date"].eq(pd.Timestamp("2022-01-04")), "same_contract_log_return"
    ].item()
    assert switch_return == pytest.approx(np.log(220.0 / 200.0))
    assert diagnostics == {
        "mapping_rows": 2,
        "resolved_mapping_rows": 2,
        "unresolved_mapping_rows": 0,
    }


def test_unresolved_mapping_is_counted_and_excluded() -> None:
    mapping = pd.DataFrame(
        {
            "date": ["2022-01-03", "2022-01-03"],
            "continuous_symbol_vt": ["a.DCE", "b.DCE"],
            "main_contract_vt": ["A2205.DCE", None],
        }
    )

    history, diagnostics = contract.build_mapped_product_history(
        mapping,
        contract.build_contract_bar_table(_bars()),
    )

    assert history["product_vt_symbol"].tolist() == ["a.DCE"]
    assert diagnostics["unresolved_mapping_rows"] == 1


def test_duplicate_resolved_mapping_key_is_rejected() -> None:
    mapping = pd.DataFrame(
        {
            "date": ["2022-01-03", "2022-01-03"],
            "continuous_symbol_vt": ["a.DCE", "a.DCE"],
            "main_contract_vt": ["A2205.DCE", "A2205.DCE"],
        }
    )

    with pytest.raises(contract.ContractError, match="duplicate_resolved_mapping"):
        contract.build_mapped_product_history(
            mapping,
            contract.build_contract_bar_table(_bars()),
        )


def _constant_history() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2021-01-04", periods=252)
    history = pd.DataFrame(
        {
            "date": dates,
            "product_vt_symbol": "a.DCE",
            "main_contract_vt": "A2205.DCE",
            "close_price": 100.0,
            "volume": 100.0,
            "open_interest": 200.0,
            "same_contract_log_return": 0.01,
        }
    )
    query = pd.DataFrame(
        {
            "query_date": [dates[-1]],
            "product_vt_symbol": ["a.DCE"],
            "main_contract_vt": ["A2205.DCE"],
        }
    )
    return history, query


def test_path_features_have_frozen_formulas() -> None:
    history, query = _constant_history()

    result = contract.compute_path_features(history, query).iloc[0]

    for window in (21, 63, 126, 252):
        assert result[f"momentum_{window}"] == pytest.approx(0.01 * window)
    for window in (21, 63, 126):
        assert result[f"trend_efficiency_{window}"] == pytest.approx(1.0)
    assert result["realized_vol_21"] == pytest.approx(0.0)
    assert result["realized_vol_63"] == pytest.approx(0.0)
    assert result["downside_vol_63"] == pytest.approx(0.0)
    assert result["max_drawdown_63"] == pytest.approx(0.0)
    assert result["volume_ratio_20_60"] == pytest.approx(0.0)
    assert result["open_interest_ratio_20_60"] == pytest.approx(0.0)
    assert result["maximum_path_source_date"] == query.iloc[0]["query_date"]


def test_path_features_keep_only_liquidity_ratios_missing() -> None:
    history, query = _constant_history()
    history.loc[history.index[-3:], "volume"] = 0.0
    history.loc[history.index[-11:], "open_interest"] = 0.0

    result = contract.compute_path_features(history, query).iloc[0]

    assert np.isnan(result["volume_ratio_20_60"])
    assert np.isnan(result["open_interest_ratio_20_60"])
    assert np.isfinite(result[list(contract.RAW_PATH_FEATURES[:-2])].to_numpy(float)).all()


def test_curve_features_match_front_slope_and_concentration() -> None:
    query_date = pd.Timestamp("2022-01-31")
    contract_bars = pd.DataFrame(
        {
            "date": [query_date] * 3,
            "contract_vt_symbol": ["A2203.DCE", "A2204.DCE", "A2205.DCE"],
            "close_price": [100.0, 95.0, 90.0],
            "volume": [100.0, 50.0, 50.0],
            "open_interest": [100.0, 100.0, 200.0],
            "same_contract_log_return": [0.0, 0.0, 0.0],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["A2203.DCE", "A2204.DCE", "A2205.DCE"],
            "product_vt_symbol": ["a.DCE"] * 3,
            "delivery_year": [2022] * 3,
            "delivery_month": [3, 4, 5],
        }
    )
    query = pd.DataFrame(
        {"query_date": [query_date], "product_vt_symbol": ["a.DCE"]}
    )

    result = contract.compute_curve_features(contract_bars, catalog, query).iloc[0]

    maturity = np.array([2022 * 12 + 3, 2022 * 12 + 4, 2022 * 12 + 5])
    assert result["front_next_basis_annualized"] == pytest.approx(
        np.log(100.0 / 95.0) * 12.0
    )
    assert result["full_curve_backwardation_slope"] == pytest.approx(
        -np.polyfit(maturity, np.log([100.0, 95.0, 90.0]), 1)[0] * 12.0
    )
    assert result["volume_hhi"] == pytest.approx(0.375)
    assert result["open_interest_hhi"] == pytest.approx(0.375)
    assert result["maximum_curve_source_date"] == query_date


def test_ranked_features_neutralize_liquidity_missing_without_dropping_rows() -> None:
    rows = []
    for index, product in enumerate(["a.DCE", "b.DCE", "c.DCE"], start=1):
        row = {
            "query_date": pd.Timestamp("2022-01-31"),
            "product_vt_symbol": product,
        }
        for feature in contract.RAW_FEATURES:
            row[feature] = float(index)
        rows.append(row)
    raw = pd.DataFrame(rows)
    raw.loc[1, "volume_ratio_20_60"] = np.nan
    raw.loc[2, "open_interest_ratio_20_60"] = np.nan

    result = contract.build_ranked_model_features(raw)

    assert len(result) == 3
    assert result.loc[1, "volume_ratio_20_60_rank"] == pytest.approx(0.5)
    assert result.loc[2, "open_interest_ratio_20_60_rank"] == pytest.approx(0.5)
    assert result["volume_ratio_missing"].tolist() == [0, 1, 0]
    assert result["open_interest_ratio_missing"].tolist() == [0, 0, 1]
    assert result.loc[0, "momentum_21_rank"] == pytest.approx(1.0 / 3.0)
    assert np.isfinite(result[list(contract.MODEL_FEATURES)].to_numpy(float)).all()


def test_base_query_panel_applies_history_curve_metadata_and_margin_gates() -> None:
    dates = pd.bdate_range("2021-01-04", periods=252)
    history = pd.DataFrame(
        {
            "date": dates,
            "product_vt_symbol": "a.DCE",
            "main_contract_vt": "A2205.DCE",
            "close_price": 100.0,
            "volume": 100.0,
            "open_interest": 200.0,
            "same_contract_log_return": [np.nan] + [0.001] * 251,
        }
    )
    contract_bars = pd.DataFrame(
        {
            "date": [dates[-1], dates[-1]],
            "contract_vt_symbol": ["A2205.DCE", "A2209.DCE"],
            "close_price": [100.0, 95.0],
            "volume": [100.0, 80.0],
            "open_interest": [200.0, 150.0],
            "same_contract_log_return": [0.001, 0.001],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["A2205.DCE", "A2209.DCE"],
            "product_vt_symbol": ["a.DCE", "a.DCE"],
            "delivery_year": [2022, 2022],
            "delivery_month": [5, 9],
        }
    )
    metadata = pd.DataFrame(
        {
            "vt_symbol": ["a.DCE"],
            "price_tick": [1.0],
            "volume_multiple": [10.0],
        }
    )

    result = contract.build_base_query_panel(
        history,
        contract_bars,
        catalog,
        metadata,
        start=dates[0],
        capital=150_000.0,
        margin_ratio=0.15,
    )

    assert result[["query_date", "product_vt_symbol"]].to_dict("records") == [
        {"query_date": dates[-1], "product_vt_symbol": "a.DCE"}
    ]
    assert result.iloc[0]["mapping_count_252"] == 252
    assert result.iloc[0]["valid_return_count_252"] == 251
    assert result.iloc[0]["valid_curve_contract_count"] == 2

    expensive = metadata.copy()
    expensive["volume_multiple"] = 20_000.0
    rejected = contract.build_base_query_panel(
        history,
        contract_bars,
        catalog,
        expensive,
        start=dates[0],
        capital=150_000.0,
        margin_ratio=0.15,
    )
    assert rejected.empty


def test_label_plan_uses_next_day_and_twenty_first_day_without_prices() -> None:
    dates = pd.bdate_range("2022-01-03", periods=25)
    base = pd.DataFrame(
        {
            "query_date": [dates[0], dates[0], dates[0], dates[0]],
            "product_vt_symbol": ["a.DCE", "b.DCE", "c.DCE", "d.DCE"],
            "main_contract_vt": [
                "A2205.DCE",
                "B2205.DCE",
                "C2205.DCE",
                "D2205.DCE",
            ],
        }
    )
    presence = pd.DataFrame(
        {
            "date": [dates[1], dates[21], dates[1], dates[1], dates[21]],
            "contract_vt_symbol": [
                "A2205.DCE",
                "A2205.DCE",
                "B2205.DCE",
                "C2205.DCE",
                "C2205.DCE",
            ],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": [
                "A2205.DCE",
                "B2205.DCE",
                "C2205.DCE",
                "D2205.DCE",
            ],
            "expire_date": [dates[22], dates[22], dates[20], dates[22]],
        }
    )

    accepted, rejected = contract.build_label_plan(
        base,
        presence,
        catalog,
        dates,
    )

    assert accepted["product_vt_symbol"].tolist() == ["a.DCE"]
    assert accepted.iloc[0]["entry_date"] == dates[1]
    assert accepted.iloc[0]["label_end"] == dates[21]
    assert bool(accepted.iloc[0]["label_value_read"]) is False
    assert set(rejected.set_index("product_vt_symbol")["rejection_reason"]) == {
        "exit_bar_missing",
        "contract_expiry_before_exit",
        "entry_bar_missing",
    }
    assert not any(
        token in column
        for column in accepted.columns
        for token in ("close", "return", "target", "relevance", "pnl", "score")
    )


def test_label_plan_rejects_bar_presence_with_price_columns() -> None:
    dates = pd.bdate_range("2022-01-03", periods=22)
    base = pd.DataFrame(
        {
            "query_date": [dates[0]],
            "product_vt_symbol": ["a.DCE"],
            "main_contract_vt": ["A2205.DCE"],
        }
    )
    presence = pd.DataFrame(
        {
            "date": [dates[1], dates[21]],
            "contract_vt_symbol": ["A2205.DCE", "A2205.DCE"],
            "close_price": [100.0, 101.0],
        }
    )
    catalog = pd.DataFrame(
        {"vt_symbol": ["A2205.DCE"], "expire_date": [dates[21]]}
    )

    with pytest.raises(contract.ContractError, match="bar_presence_columns_invalid"):
        contract.build_label_plan(base, presence, catalog, dates)


def test_formal_scoring_plan_keeps_one_anchor_and_disjoint_challengers() -> None:
    date = pd.Timestamp("2024-01-31")
    base = pd.DataFrame(
        {
            "query_date": [date, date, date],
            "product_vt_symbol": ["a.DCE", "b.DCE", "c.DCE"],
        }
    )
    coverage = pd.DataFrame(
        {
            "eval_date": [date, date, date],
            "product_vt_symbol": ["a.DCE", "b.DCE", "c.DCE"],
            "eligible": [True, True, True],
            "is_formal_replacement_product": [True, False, False],
            "is_pool_outside_challenger": [False, True, True],
        }
    )
    monthly = pd.DataFrame({"eval_date": [date], "action_ready": [True]})

    result = contract.build_formal_scoring_plan(base, coverage, monthly)

    assert result["role"].tolist() == ["formal_rank10", "challenger", "challenger"]
    assert result["formal_score_value_read"].sum() == 0

    overlap = coverage.copy()
    overlap.loc[0, "is_pool_outside_challenger"] = True
    with pytest.raises(contract.ContractError, match="formal_role_overlap"):
        contract.build_formal_scoring_plan(base, overlap, monthly)


def test_purged_fold_plan_uses_only_mature_qids_and_marks_inference() -> None:
    qids = pd.bdate_range("2022-01-03", periods=300)
    products = ["anchor.DCE", *(f"c{index}.DCE" for index in range(10))]
    label_plan = pd.DataFrame(
        {
            "query_date": np.repeat(qids, len(products)),
            "product_vt_symbol": products * len(qids),
            "main_contract_vt": [f"{product}.contract" for product in products]
            * len(qids),
            "entry_date": np.repeat(qids + pd.offsets.BDay(1), len(products)),
            "label_end": np.repeat(qids + pd.offsets.BDay(21), len(products)),
            "label_value_read": False,
        }
    )
    first_test = qids[273]
    inference_test = qids[-1] + pd.offsets.BDay(30)
    scoring_products = products * 2
    scoring = pd.DataFrame(
        {
            "test_eval_date": [first_test] * len(products)
            + [inference_test] * len(products),
            "product_vt_symbol": scoring_products,
            "role": (["formal_rank10"] + ["challenger"] * 10) * 2,
        }
    )

    result = contract.build_purged_fold_plan(
        label_plan,
        scoring,
        minimum_train_qids=252,
    )

    assert result.iloc[0]["train_qid_count"] == 252
    assert result.iloc[0]["maximum_train_label_end"] < first_test
    assert result.iloc[0]["effect_evaluable"] is True
    assert result.iloc[1]["inference_only"] is True
