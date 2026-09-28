from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import roll_adjusted_trend_quality as core


def _bars(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "contract_vt_symbol", "close_price"])


def _legs(returns: list[float], *, product: str = "p.EX") -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2025-01-01", periods=len(returns) + 1)
    leg_rows: list[dict[str, object]] = []
    bar_rows: list[tuple[str, str, float]] = []
    price = 100.0
    for index, value in enumerate(returns, start=1):
        contract = "P2501.EX" if index <= 2 else "P2505.EX"
        previous = dates[index - 1]
        current = dates[index]
        if index == 3:
            price = 200.0
        next_price = price * math.exp(value)
        bar_rows.extend(
            [
                (str(previous.date()), contract, price),
                (str(current.date()), contract, next_price),
            ]
        )
        leg_rows.append(
            {
                "query_date": dates[0],
                "product_vt_symbol": product,
                "leg_index": index,
                "previous_date": previous,
                "return_date": current,
                "selected_contract_vt": contract,
                "leg_valid": True,
                "previous_bar_present": True,
                "return_bar_present": True,
                "roll_event": index == 3,
            }
        )
        price = next_price
    bars = pd.DataFrame(bar_rows, columns=["date", "contract_vt_symbol", "close_price"])
    bars = bars.drop_duplicates(["date", "contract_vt_symbol"], keep="last")
    return pd.DataFrame(leg_rows), bars


def test_roll_uses_two_same_contract_returns_without_cross_contract_jump() -> None:
    dates = pd.bdate_range("2025-01-01", periods=3)
    legs = pd.DataFrame(
        {
            "query_date": [dates[0], dates[0]],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "leg_index": [1, 2],
            "previous_date": [dates[0], dates[1]],
            "return_date": [dates[1], dates[2]],
            "selected_contract_vt": ["P2501.EX", "P2505.EX"],
            "leg_valid": [True, True],
            "previous_bar_present": [True, True],
            "return_bar_present": [True, True],
            "roll_event": [False, True],
        }
    )
    bars = _bars(
        [
            (str(dates[0].date()), "P2501.EX", 100.0),
            (str(dates[1].date()), "P2501.EX", 110.0),
            (str(dates[1].date()), "P2505.EX", 200.0),
            (str(dates[2].date()), "P2505.EX", 220.0),
        ]
    )

    result, audit = core.build_leg_returns(legs, bars)

    assert result["leg_log_return"].tolist() == pytest.approx([math.log(1.1), math.log(1.1)])
    assert result["price_contract_vt"].tolist() == ["P2501.EX", "P2505.EX"]
    assert audit["logical_close_reads"] == 4
    assert audit["cross_contract_price_comparisons"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "close_endpoint_missing"),
        ("zero", "close_nonpositive_or_nonfinite"),
        ("duplicate", "duplicate_contract_price"),
    ],
)
def test_invalid_close_source_fails_closed(mutation: str, message: str) -> None:
    legs, bars = _legs([0.01, 0.02])
    if mutation == "missing":
        bars = bars.iloc[1:].copy()
    elif mutation == "zero":
        bars.loc[bars.index[0], "close_price"] = 0.0
    else:
        bars = pd.concat([bars, bars.iloc[[0]]], ignore_index=True)

    with pytest.raises(core.TrendQualityError, match=message):
        core.build_leg_returns(legs, bars)


def test_positive_and_negative_mirror_have_same_trend_quality() -> None:
    positive_legs, positive_bars = _legs([0.10, -0.04, 0.05])
    negative_legs, negative_bars = _legs([-0.10, 0.04, -0.05], product="n.EX")
    legs = pd.concat([positive_legs, negative_legs], ignore_index=True)
    bars = pd.concat([positive_bars, negative_bars], ignore_index=True)
    negative_contracts = bars["contract_vt_symbol"].str.startswith("P") & bars.duplicated(
        ["date", "contract_vt_symbol"], keep="first"
    )
    bars.loc[negative_contracts, "contract_vt_symbol"] = (
        "N" + bars.loc[negative_contracts, "contract_vt_symbol"].str[1:]
    )
    negative_rows = legs["product_vt_symbol"].eq("n.EX")
    legs.loc[negative_rows, "selected_contract_vt"] = (
        "N" + legs.loc[negative_rows, "selected_contract_vt"].str[1:]
    )

    leg_returns, _ = core.build_leg_returns(legs, bars)
    labels = core.aggregate_path_labels(leg_returns, expected_leg_count=3)
    positive = labels.loc[labels["product_vt_symbol"].eq("p.EX")].iloc[0]
    negative = labels.loc[labels["product_vt_symbol"].eq("n.EX")].iloc[0]

    assert positive["path_log_return"] == pytest.approx(0.11)
    assert negative["path_log_return"] == pytest.approx(-0.11)
    for column in (
        "future_abs_log_return",
        "future_abs_variation",
        "future_trend_efficiency",
        "future_oriented_max_drawdown",
        "future_trend_capture_quality",
    ):
        assert positive[column] == pytest.approx(negative[column])
    assert positive["future_oriented_max_drawdown"] == pytest.approx(-0.04)
    assert positive["future_trend_capture_quality"] == pytest.approx(0.07)
    assert positive["future_trend_efficiency"] == pytest.approx(0.11 / 0.19)


def test_path_structure_must_have_exact_consecutive_legs() -> None:
    legs, bars = _legs([0.01, 0.02, 0.03])
    leg_returns, _ = core.build_leg_returns(legs, bars)
    leg_returns.loc[leg_returns.index[-1], "leg_index"] = 4

    with pytest.raises(core.TrendQualityError, match="path_leg_index_invalid"):
        core.aggregate_path_labels(leg_returns, expected_leg_count=3)


def test_relevance_is_five_level_and_preserves_ties() -> None:
    labels = pd.DataFrame(
        {
            "query_date": ["2025-01-31"] * 10,
            "product_vt_symbol": [f"p{i}.EX" for i in range(10)],
            "future_trend_capture_quality": [0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        }
    )

    ranked, diagnostics = core.add_cross_sectional_relevance(
        labels, levels=5, minimum_qid_width=5
    )

    assert ranked.loc[0, "trend_quality_relevance"] == ranked.loc[1, "trend_quality_relevance"]
    assert set(ranked["trend_quality_relevance"]) == {0, 1, 2, 3, 4}
    assert diagnostics.loc[0, "target_unique_count"] == 9
    assert diagnostics.loc[0, "relevance_level_count"] == 5


def test_relevance_rejects_narrow_or_degenerate_qid() -> None:
    narrow = pd.DataFrame(
        {
            "query_date": ["2025-01-31"] * 4,
            "product_vt_symbol": [f"p{i}.EX" for i in range(4)],
            "future_trend_capture_quality": np.arange(4, dtype=float),
        }
    )
    with pytest.raises(core.TrendQualityError, match="qid_width_below_minimum"):
        core.add_cross_sectional_relevance(narrow, levels=5, minimum_qid_width=5)

    degenerate = narrow.assign(
        query_date="2025-02-28",
        product_vt_symbol=[f"d{i}.EX" for i in range(4)],
        future_trend_capture_quality=1.0,
    )
    degenerate = pd.concat([degenerate, degenerate.iloc[[0]].assign(product_vt_symbol="d4.EX")])
    with pytest.raises(core.TrendQualityError, match="qid_target_unique_below_levels"):
        core.add_cross_sectional_relevance(degenerate, levels=5, minimum_qid_width=5)

