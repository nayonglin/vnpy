from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import full_market_coverage as core  # noqa: E402


def _ranking(eval_date: str = "2024-01-04") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "eval_date": eval_date,
                "product_vt_symbol": "A.DCE",
                "score_rank": 1,
                "score_type": "formal",
            },
            {
                "eval_date": eval_date,
                "product_vt_symbol": "B.DCE",
                "score_rank": 2,
                "score_type": "formal",
            },
        ]
    )


def _mapping(products: list[str], eval_date: str = "2024-01-04") -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", eval_date, freq="D")
    rows: list[dict[str, object]] = []
    for product in products:
        code, exchange = product.split(".")
        for index, date in enumerate(dates, start=1):
            rows.append(
                {
                    "date": date,
                    "continuous_symbol_vt": product,
                    "main_contract_vt": f"{code}240{index}.{exchange}",
                    "exchange": exchange,
                }
            )
    return pd.DataFrame(rows)


def _bars(mapping: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in mapping.itertuples(index=False):
        symbol, exchange = str(item.main_contract_vt).split(".")
        rows.append(
            {
                "datetime": item.date,
                "symbol": symbol,
                "exchange": exchange,
                "interval": "d",
                "close_price": 100.0,
                "volume": 1000.0,
                "open_interest": 500.0,
            }
        )
    for product in sorted(mapping["continuous_symbol_vt"].unique()):
        code, exchange = product.split(".")
        rows.extend(
            [
                {
                    "datetime": pd.Timestamp("2024-01-04"),
                    "symbol": f"{code}2405",
                    "exchange": exchange,
                    "interval": "d",
                    "close_price": 101.0,
                    "volume": 1000.0,
                    "open_interest": 500.0,
                },
                {
                    "datetime": pd.Timestamp("2024-01-04"),
                    "symbol": f"{code}2409",
                    "exchange": exchange,
                    "interval": "d",
                    "close_price": 102.0,
                    "volume": 900.0,
                    "open_interest": 400.0,
                },
            ]
        )
    return pd.DataFrame(rows)


def _metadata(products: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vt_symbol": product,
                "symbol_kind": "product_cont",
                "price_tick": 1.0,
                "volume_multiple": 10.0,
            }
            for product in products
        ]
    )


def _config() -> core.CoverageConfig:
    return core.CoverageConfig(
        eval_start=pd.Timestamp("2024-01-04"),
        eval_end=pd.Timestamp("2024-01-04"),
        expected_months=1,
        expected_ranks_per_month=2,
        expected_static_products=2,
        replacement_rank=2,
        minimum_mapping_days=3,
        minimum_valid_close_days=3,
        activity_window_days=2,
        minimum_activity_ratio=1.0,
        minimum_curve_contracts=2,
        minimum_total_eligible=3,
        minimum_action_months=1,
        minimum_challengers=1,
        capital=1_000.0,
        conservative_margin_ratio=0.15,
    )


def test_build_coverage_enforces_pit_exchange_and_pool_boundaries() -> None:
    """Catches admitting CFFEX, future-only, or static-pool rows as challengers."""
    products = ["A.DCE", "B.DCE", "X.SHFE", "Y.CZCE", "IF.CFFEX"]
    mapping = _mapping(products)
    bars = _bars(mapping)

    y_mask = bars["symbol"].astype(str).str.startswith("Y")
    bars.loc[y_mask & pd.to_datetime(bars["datetime"]).lt("2024-01-04"), "close_price"] = pd.NA
    bars = pd.concat(
        [
            bars,
            pd.DataFrame(
                [
                    {
                        "datetime": "2024-01-05",
                        "symbol": "Y2403",
                        "exchange": "CZCE",
                        "interval": "d",
                        "close_price": 100.0,
                        "volume": 1000.0,
                        "open_interest": 500.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = core.build_coverage(
        _ranking(), mapping, bars, _metadata(products), _config()
    )
    rows = result.coverage.set_index("product_vt_symbol")

    assert bool(rows.loc["X.SHFE", "eligible"])
    assert bool(rows.loc["X.SHFE", "is_pool_outside_challenger"])
    assert not bool(rows.loc["A.DCE", "is_pool_outside_challenger"])
    assert not bool(rows.loc["B.DCE", "is_pool_outside_challenger"])
    assert not bool(rows.loc["Y.CZCE", "eligible"])
    assert rows.loc["Y.CZCE", "status"] == "valid_close_days_below_minimum"
    assert not bool(rows.loc["IF.CFFEX", "eligible"])
    assert rows.loc["IF.CFFEX", "status"] == "exchange_not_allowed"
    assert result.diagnostics["future_bar_rows_used"] == 0
    assert result.diagnostics["future_mapping_rows_used"] == 0


def test_baseline_rank_ineligible_keeps_month_non_actionable() -> None:
    """Catches replacing an invalid historical rank slot for a free backtest gain."""
    products = ["A.DCE", "B.DCE", "X.SHFE"]
    mapping = _mapping(products)
    bars = _bars(mapping)
    b_mask = bars["symbol"].astype(str).str.startswith("B")
    bars.loc[b_mask, "open_interest"] = 0.0

    result = core.build_coverage(
        _ranking(), mapping, bars, _metadata(products), _config()
    )
    month = result.monthly.iloc[0]

    assert month["formal_replacement_product"] == "B.DCE"
    assert not bool(month["formal_replacement_eligible"])
    assert not bool(month["action_ready"])


def test_one_lot_margin_is_a_hard_eligibility_gate() -> None:
    """Catches admitting a contract that the frozen 150k account cannot buy once."""
    products = ["A.DCE", "B.DCE", "X.SHFE"]
    metadata = _metadata(products)
    metadata.loc[metadata["vt_symbol"].eq("X.SHFE"), "volume_multiple"] = 100.0

    result = core.build_coverage(
        _ranking(), _mapping(products), _bars(_mapping(products)), metadata, _config()
    )
    row = result.coverage.set_index("product_vt_symbol").loc["X.SHFE"]

    assert not bool(row["eligible"])
    assert row["status"] == "one_lot_margin_above_capital"
    assert row["one_lot_margin"] == pytest.approx(1_500.0)


def test_assessment_fails_without_enough_pool_outside_challengers() -> None:
    """Catches lowering the challenger breadth gate after observing sparse coverage."""
    products = ["A.DCE", "B.DCE", "X.SHFE"]
    config = replace(_config(), minimum_challengers=2)
    result = core.build_coverage(
        _ranking(), _mapping(products), _bars(_mapping(products)), _metadata(products), config
    )
    summary = core.assess_coverage(result, config)

    assert not summary["all_gates_passed"]
    assert not summary["gates"]["challenger_breadth_on_each_eligible_baseline_month"]
    assert summary["decision"] == core.FAIL_DECISION


def test_ranking_requires_contiguous_unique_monthly_ranks() -> None:
    """Catches an ambiguous A-rank10 identity before any candidate audit."""
    ranking = _ranking()
    ranking.loc[1, "score_rank"] = 1

    with pytest.raises(core.CoverageError, match="formal_eval_rank_duplicate"):
        core.build_coverage(
            ranking,
            _mapping(["A.DCE", "B.DCE", "X.SHFE"]),
            _bars(_mapping(["A.DCE", "B.DCE", "X.SHFE"])),
            _metadata(["A.DCE", "B.DCE", "X.SHFE"]),
            _config(),
        )

