"""Point-in-time listing eligibility for the frozen formal futures ranking."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


ELIGIBILITY_COLUMNS = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]
RANKING_COLUMNS = [
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "score_type",
]
CANDIDATE_SCORE_TYPE = "pit_listing_eligible_formal_rank_top10_plus_fixed_fu"


class ListingEligibilityError(RuntimeError):
    """Raised when the frozen PIT listing contract is violated."""


def match_contract_to_product(
    symbol: object,
    exchange: object,
    formal_products: Sequence[str],
) -> str | None:
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", str(symbol))
    if match is None:
        return None
    code, delivery = match.groups()
    if len(set(delivery)) == 1 and delivery[0] in {"8", "9"}:
        return None
    if not 1 <= int(delivery[-2:]) <= 12:
        return None

    exchange_text = str(exchange)
    matches = []
    for product in map(str, formal_products):
        product_code, separator, product_exchange = product.partition(".")
        if (
            separator
            and product_exchange == exchange_text
            and product_code.lower() == code.lower()
        ):
            matches.append(product)
    if len(matches) > 1:
        raise ListingEligibilityError("contract_product_match_ambiguous")
    return matches[0] if matches else None


def derive_first_available_dates(
    bars: pd.DataFrame,
    formal_products: Sequence[str],
) -> dict[str, pd.Timestamp]:
    required = {"datetime", "symbol", "exchange"}
    if missing := sorted(required - set(bars.columns)):
        raise ListingEligibilityError(f"bar_columns_missing:{','.join(missing)}")
    products = [str(product) for product in formal_products]
    if not products or len(products) != len(set(products)):
        raise ListingEligibilityError("formal_products_invalid")

    frame = bars.loc[:, ["datetime", "symbol", "exchange"]].copy()
    frame["date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = [
        match_contract_to_product(symbol, exchange, products)
        for symbol, exchange in zip(frame["symbol"], frame["exchange"], strict=True)
    ]
    frame = frame[frame["product_vt_symbol"].notna()].copy()
    if frame.empty:
        return {}
    first = frame.groupby("product_vt_symbol", sort=True)["date"].min()
    return {str(product): pd.Timestamp(value) for product, value in first.items()}


def _canonical_date_strings(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="raise").dt.strftime("%Y-%m-%d")


def _normalise_first_available(
    first_available: Mapping[str, Any],
) -> dict[str, pd.Timestamp]:
    result: dict[str, pd.Timestamp] = {}
    for product, value in first_available.items():
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ListingEligibilityError(f"first_available_date_invalid:{product}")
        result[str(product)] = timestamp.normalize()
    return result


def _validate_formal_and_ranking(
    formal_eligibility: pd.DataFrame,
    formal_ranking: pd.DataFrame,
    first_available: Mapping[str, pd.Timestamp],
    *,
    expected_ranked_products: int,
    top_n: int,
    fixed_product: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    if missing := sorted(set(ELIGIBILITY_COLUMNS) - set(formal_eligibility.columns)):
        raise ListingEligibilityError(f"formal_columns_missing:{','.join(missing)}")
    if missing := sorted(set(RANKING_COLUMNS) - set(formal_ranking.columns)):
        raise ListingEligibilityError(f"ranking_columns_missing:{','.join(missing)}")
    if expected_ranked_products < top_n:
        raise ListingEligibilityError("expected_ranked_products_below_topn")

    formal = formal_eligibility.loc[:, ELIGIBILITY_COLUMNS].copy()
    ranking = formal_ranking.loc[:, RANKING_COLUMNS].copy()
    formal["eval_date"] = _canonical_date_strings(formal["eval_date"])
    ranking["eval_date"] = _canonical_date_strings(ranking["eval_date"])
    formal["score_rank"] = pd.to_numeric(formal["score_rank"], errors="raise").astype(int)
    ranking["score_rank"] = pd.to_numeric(ranking["score_rank"], errors="raise").astype(int)
    formal["top_n"] = pd.to_numeric(formal["top_n"], errors="raise").astype(int)
    formal["score"] = pd.to_numeric(formal["score"], errors="raise").astype(float)
    ranking["score"] = pd.to_numeric(ranking["score"], errors="raise").astype(float)

    if formal.duplicated(["eval_date", "score_rank"]).any():
        raise ListingEligibilityError("formal_date_rank_duplicate")
    if ranking.duplicated(["eval_date", "score_rank"]).any():
        raise ListingEligibilityError("ranking_date_rank_duplicate")
    if ranking.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise ListingEligibilityError("ranking_date_product_duplicate")

    products = sorted(ranking["product_vt_symbol"].astype(str).unique())
    if len(products) != expected_ranked_products:
        raise ListingEligibilityError(f"ranked_product_count:{len(products)}")
    if set(products) != set(first_available):
        raise ListingEligibilityError("first_available_products_mismatch")

    ranking_dates = sorted(ranking["eval_date"].unique())
    if not set(ranking_dates).issubset(set(formal["eval_date"])):
        raise ListingEligibilityError("ranking_date_missing_from_formal")
    for eval_date, month in ranking.groupby("eval_date", sort=True):
        ordered = month.sort_values("score_rank", kind="mergesort")
        if len(ordered) != expected_ranked_products:
            raise ListingEligibilityError(f"ranking_month_product_count:{eval_date}:{len(ordered)}")
        if ordered["score_rank"].tolist() != list(range(1, expected_ranked_products + 1)):
            raise ListingEligibilityError(f"ranking_month_rank_not_contiguous:{eval_date}")

        formal_month = formal[formal["eval_date"].eq(eval_date)].sort_values(
            "score_rank", kind="mergesort"
        )
        fixed = formal_month[formal_month["product_vt_symbol"].eq(fixed_product)]
        model = formal_month[formal_month["product_vt_symbol"].ne(fixed_product)]
        if len(fixed) != 1 or len(model) != top_n:
            raise ListingEligibilityError(f"formal_month_shape:{eval_date}")
        if int(fixed.iloc[0]["score_rank"]) != top_n + 1:
            raise ListingEligibilityError(f"fixed_product_rank_drift:{eval_date}")
        if model["product_vt_symbol"].astype(str).tolist() != ordered.head(top_n)[
            "product_vt_symbol"
        ].astype(str).tolist():
            raise ListingEligibilityError(f"formal_ranking_membership_mismatch:{eval_date}")
    return formal, ranking, ranking_dates


def build_pit_listing_candidate(
    formal_eligibility: pd.DataFrame,
    formal_ranking: pd.DataFrame,
    first_available: Mapping[str, Any],
    *,
    expected_ranked_products: int = 18,
    top_n: int = 10,
    fixed_product: str = "fu.SHFE",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    availability = _normalise_first_available(first_available)
    formal, ranking, ranking_dates = _validate_formal_and_ranking(
        formal_eligibility,
        formal_ranking,
        availability,
        expected_ranked_products=expected_ranked_products,
        top_n=top_n,
        fixed_product=fixed_product,
    )

    candidate_months: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []
    ranking_date_set = set(ranking_dates)
    for eval_date, formal_month in formal.groupby("eval_date", sort=True):
        formal_month = formal_month.sort_values("score_rank", kind="mergesort").copy()
        if eval_date not in ranking_date_set:
            candidate_months.append(formal_month)
            continue

        eval_timestamp = pd.Timestamp(eval_date)
        ordered = ranking[ranking["eval_date"].eq(eval_date)].sort_values(
            "score_rank", kind="mergesort"
        )
        formal_top = formal_month[
            formal_month["product_vt_symbol"].ne(fixed_product)
        ]["product_vt_symbol"].astype(str).tolist()
        unavailable_formal = [
            product for product in formal_top if availability[product] > eval_timestamp
        ]
        available = ordered[
            ordered["product_vt_symbol"].map(availability).le(eval_timestamp)
        ].copy()
        if len(available) < top_n:
            raise ListingEligibilityError(
                f"eligible_product_count_below_topn:{eval_date}:{len(available)}"
            )
        selected = available.head(top_n).copy()
        candidate_top = selected["product_vt_symbol"].astype(str).tolist()
        changed = formal_top != candidate_top

        if not unavailable_formal:
            if changed:
                raise ListingEligibilityError(
                    f"membership_changed_without_unavailable_formal_top10:{eval_date}"
                )
            candidate_month = formal_month
        else:
            fixed = formal_month[
                formal_month["product_vt_symbol"].eq(fixed_product)
            ].copy()
            strategy_values = formal_month["strategy"].astype(str).unique().tolist()
            top_n_values = formal_month["top_n"].astype(int).unique().tolist()
            if len(strategy_values) != 1 or top_n_values != [top_n + 1]:
                raise ListingEligibilityError(f"formal_month_metadata_drift:{eval_date}")
            rebuilt = pd.DataFrame(
                {
                    "strategy": strategy_values[0],
                    "score_type": CANDIDATE_SCORE_TYPE,
                    "eval_date": eval_date,
                    "product_vt_symbol": candidate_top,
                    "score": selected["score"].astype(float).tolist(),
                    "score_rank": list(range(1, top_n + 1)),
                    "top_n": top_n + 1,
                }
            )
            candidate_month = pd.concat([rebuilt, fixed], ignore_index=True)
            candidate_month = candidate_month.loc[:, ELIGIBILITY_COLUMNS]

        promoted = [product for product in candidate_top if product not in formal_top]
        removed = [product for product in formal_top if product not in candidate_top]
        audit_rows.append(
            {
                "eval_date": eval_date,
                "ranked_product_count": int(len(ordered)),
                "available_ranked_product_count": int(len(available)),
                "formal_top10_products": ",".join(formal_top),
                "candidate_top10_products": ",".join(candidate_top),
                "formal_unavailable_top10_count": int(len(unavailable_formal)),
                "formal_unavailable_top10_products": ",".join(unavailable_formal),
                "removed_unavailable_products": ",".join(removed),
                "promoted_products": ",".join(promoted),
                "changed_member_count": int(len(set(formal_top) ^ set(candidate_top))),
                "membership_changed": bool(changed),
                "future_rows_used": 0,
            }
        )
        candidate_months.append(candidate_month)

    candidate = pd.concat(candidate_months, ignore_index=True)
    candidate.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    candidate.reset_index(drop=True, inplace=True)
    audit = pd.DataFrame(audit_rows).sort_values("eval_date", kind="mergesort").reset_index(drop=True)
    return candidate, audit


def validate_membership_contract(
    formal_eligibility: pd.DataFrame,
    candidate_eligibility: pd.DataFrame,
    audit: pd.DataFrame,
    first_available: Mapping[str, Any],
    *,
    unchanged_from: pd.Timestamp,
    top_n: int = 10,
    fixed_product: str = "fu.SHFE",
) -> dict[str, Any]:
    formal = formal_eligibility.loc[:, ELIGIBILITY_COLUMNS].copy()
    candidate = candidate_eligibility.loc[:, ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = _canonical_date_strings(formal["eval_date"])
    candidate["eval_date"] = _canonical_date_strings(candidate["eval_date"])
    audit_frame = audit.copy()
    audit_frame["eval_date"] = _canonical_date_strings(audit_frame["eval_date"])
    availability = _normalise_first_available(first_available)
    boundary = pd.Timestamp(unchanged_from).normalize()

    changed_after_boundary = audit_frame[
        pd.to_datetime(audit_frame["eval_date"]).ge(boundary)
        & audit_frame["membership_changed"].astype(bool)
    ]
    if not changed_after_boundary.empty:
        raise ListingEligibilityError("post_boundary_membership_changed")

    candidate_unavailable: list[tuple[str, str]] = []
    changed_without_reason: list[str] = []
    for row in audit_frame.itertuples(index=False):
        eval_date = str(row.eval_date)
        eval_timestamp = pd.Timestamp(eval_date)
        formal_month = formal[formal["eval_date"].eq(eval_date)]
        candidate_month = candidate[candidate["eval_date"].eq(eval_date)]
        formal_top = formal_month[
            formal_month["product_vt_symbol"].ne(fixed_product)
        ].sort_values("score_rank")["product_vt_symbol"].astype(str).tolist()
        candidate_top = candidate_month[
            candidate_month["product_vt_symbol"].ne(fixed_product)
        ].sort_values("score_rank")["product_vt_symbol"].astype(str).tolist()
        if len(candidate_top) != top_n or len(set(candidate_top)) != top_n:
            raise ListingEligibilityError(f"candidate_month_topn_shape:{eval_date}")
        fixed = candidate_month[candidate_month["product_vt_symbol"].eq(fixed_product)]
        if len(fixed) != 1 or int(fixed.iloc[0]["score_rank"]) != top_n + 1:
            raise ListingEligibilityError(f"candidate_fixed_product_shape:{eval_date}")
        for product in candidate_top:
            if product not in availability or availability[product] > eval_timestamp:
                candidate_unavailable.append((eval_date, product))
        membership_changed = set(formal_top) != set(candidate_top)
        if membership_changed and int(row.formal_unavailable_top10_count) <= 0:
            changed_without_reason.append(eval_date)
        if not membership_changed and bool(row.membership_changed):
            raise ListingEligibilityError(f"audit_membership_change_mismatch:{eval_date}")
    if candidate_unavailable:
        raise ListingEligibilityError(f"candidate_contains_unavailable:{candidate_unavailable}")
    if changed_without_reason:
        raise ListingEligibilityError(f"membership_changed_without_reason:{changed_without_reason}")
    return {
        "ranking_months": int(len(audit_frame)),
        "changed_months": int(audit_frame["membership_changed"].astype(bool).sum()),
        "unavailable_candidate_count": 0,
        "post_boundary_changed_months": 0,
        "future_rows_used": int(audit_frame.get("future_rows_used", 0).sum()),
    }
