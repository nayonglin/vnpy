from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/pit_listing_eligibility.py"
SPEC = importlib.util.spec_from_file_location("pit_listing_eligibility", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _ranking(eval_date: str, products: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": [eval_date] * len(products),
            "product_vt_symbol": products,
            "score": [1.0 - 0.01 * index for index in range(len(products))],
            "score_rank": list(range(1, len(products) + 1)),
            "score_type": ["formal_full_rank"] * len(products),
        }
    )


def _formal(eval_date: str, products: list[str]) -> pd.DataFrame:
    rows = [
        {
            "strategy": "formal",
            "score_type": "formal_top10",
            "eval_date": eval_date,
            "product_vt_symbol": product,
            "score": 1.0 - 0.01 * index,
            "score_rank": index + 1,
            "top_n": 11,
        }
        for index, product in enumerate(products[:10])
    ]
    rows.append(
        {
            "strategy": "formal",
            "score_type": "fixed_fu",
            "eval_date": eval_date,
            "product_vt_symbol": "fu.SHFE",
            "score": 0.5,
            "score_rank": 11,
            "top_n": 11,
        }
    )
    return pd.DataFrame(rows)


def test_contract_matching_excludes_continuous_options_and_bad_months() -> None:
    products = ["SH.CZCE"]
    assert MODULE.match_contract_to_product("SH409", "CZCE", products) == "SH.CZCE"
    assert MODULE.match_contract_to_product("SH2409", "CZCE", products) == "SH.CZCE"
    assert MODULE.match_contract_to_product("SH8888", "CZCE", products) is None
    assert MODULE.match_contract_to_product("SH99", "CZCE", products) is None
    assert MODULE.match_contract_to_product("SH409C3000", "CZCE", products) is None
    assert MODULE.match_contract_to_product("SH413", "CZCE", products) is None


def test_first_available_date_uses_only_regular_contract_bars() -> None:
    bars = pd.DataFrame(
        {
            "datetime": ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"],
            "symbol": ["AA8888", "AA2201C10", "AA2213", "AA2205"],
            "exchange": ["DCE"] * 4,
        }
    )
    observed = MODULE.derive_first_available_dates(bars, ["AA.DCE"])
    assert observed == {"AA.DCE": pd.Timestamp("2022-01-04")}


def test_candidate_filters_unlisted_and_promotes_next_formal_ranks() -> None:
    products = [f"P{index}.DCE" for index in range(1, 13)]
    ranking = _ranking("2022-07-29", products)
    formal = _formal("2022-07-29", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products}
    first_available["P3.DCE"] = pd.Timestamp("2022-08-01")
    first_available["P7.DCE"] = pd.Timestamp("2022-08-01")

    candidate, audit = MODULE.build_pit_listing_candidate(
        formal,
        ranking,
        first_available,
        expected_ranked_products=12,
    )

    month = candidate[candidate["eval_date"].eq("2022-07-29")]
    model = month[month["product_vt_symbol"].ne("fu.SHFE")]
    assert model["product_vt_symbol"].tolist() == [
        "P1.DCE",
        "P2.DCE",
        "P4.DCE",
        "P5.DCE",
        "P6.DCE",
        "P8.DCE",
        "P9.DCE",
        "P10.DCE",
        "P11.DCE",
        "P12.DCE",
    ]
    assert model["score_rank"].tolist() == list(range(1, 11))
    assert month.iloc[-1]["product_vt_symbol"] == "fu.SHFE"
    assert int(month.iloc[-1]["score_rank"]) == 11
    assert audit.iloc[0]["removed_unavailable_products"] == "P3.DCE,P7.DCE"
    assert audit.iloc[0]["promoted_products"] == "P11.DCE,P12.DCE"


def test_unchanged_month_is_byte_semantically_preserved() -> None:
    products = [f"P{index}.DCE" for index in range(1, 13)]
    ranking = _ranking("2024-01-31", products)
    formal = _formal("2024-01-31", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products}

    candidate, audit = MODULE.build_pit_listing_candidate(
        formal,
        ranking,
        first_available,
        expected_ranked_products=12,
    )

    pd.testing.assert_frame_equal(candidate.reset_index(drop=True), formal.reset_index(drop=True))
    assert bool(audit.iloc[0]["membership_changed"]) is False


def test_future_first_bar_does_not_make_product_eligible() -> None:
    products = [f"P{index}.DCE" for index in range(1, 12)]
    ranking = _ranking("2022-07-29", products)
    formal = _formal("2022-07-29", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products}
    first_available["P1.DCE"] = pd.Timestamp("2022-07-30")

    candidate, _ = MODULE.build_pit_listing_candidate(
        formal,
        ranking,
        first_available,
        expected_ranked_products=11,
    )

    assert "P1.DCE" not in set(candidate["product_vt_symbol"])
    assert "P11.DCE" in set(candidate["product_vt_symbol"])


def test_candidate_fails_when_fewer_than_topn_products_are_available() -> None:
    products = [f"P{index}.DCE" for index in range(1, 11)]
    ranking = _ranking("2022-07-29", products)
    formal = _formal("2022-07-29", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products}
    first_available["P10.DCE"] = pd.Timestamp("2022-08-01")

    with pytest.raises(MODULE.ListingEligibilityError, match="eligible_product_count_below_topn"):
        MODULE.build_pit_listing_candidate(
            formal,
            ranking,
            first_available,
            expected_ranked_products=10,
        )


def test_missing_first_available_date_fails_closed() -> None:
    products = [f"P{index}.DCE" for index in range(1, 12)]
    ranking = _ranking("2022-07-29", products)
    formal = _formal("2022-07-29", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products[:-1]}

    with pytest.raises(MODULE.ListingEligibilityError, match="first_available_products_mismatch"):
        MODULE.build_pit_listing_candidate(
            formal,
            ranking,
            first_available,
            expected_ranked_products=11,
        )


def test_only_months_with_unavailable_formal_top10_can_change() -> None:
    first_products = [f"P{index}.DCE" for index in range(1, 12)]
    second_products = list(reversed(first_products))
    ranking = pd.concat(
        [_ranking("2022-07-29", first_products), _ranking("2023-09-28", second_products)],
        ignore_index=True,
    )
    formal = pd.concat(
        [_formal("2022-07-29", first_products), _formal("2023-09-28", second_products)],
        ignore_index=True,
    )
    first_available = {product: pd.Timestamp("2020-01-01") for product in first_products}
    first_available["P2.DCE"] = pd.Timestamp("2022-08-01")

    candidate, audit = MODULE.build_pit_listing_candidate(
        formal,
        ranking,
        first_available,
        expected_ranked_products=11,
    )

    MODULE.validate_membership_contract(
        formal,
        candidate,
        audit,
        first_available,
        unchanged_from=pd.Timestamp("2023-09-28"),
    )


def test_contract_rejects_post_boundary_membership_change() -> None:
    products = [f"P{index}.DCE" for index in range(1, 12)]
    ranking = _ranking("2023-09-28", products)
    formal = _formal("2023-09-28", products)
    first_available = {product: pd.Timestamp("2020-01-01") for product in products}
    candidate = formal.copy()
    candidate.loc[candidate["score_rank"].eq(10), "product_vt_symbol"] = "P11.DCE"
    audit = pd.DataFrame(
        [{
            "eval_date": "2023-09-28",
            "membership_changed": True,
            "formal_unavailable_top10_count": 0,
        }]
    )

    with pytest.raises(MODULE.ListingEligibilityError, match="post_boundary_membership_changed"):
        MODULE.validate_membership_contract(
            formal,
            candidate,
            audit,
            first_available,
            unchanged_from=pd.Timestamp("2023-09-28"),
        )
