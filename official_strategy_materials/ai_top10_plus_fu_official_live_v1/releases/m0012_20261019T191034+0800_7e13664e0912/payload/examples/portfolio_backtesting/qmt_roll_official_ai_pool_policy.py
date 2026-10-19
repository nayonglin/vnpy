from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


OFFICIAL_AI_RANKED_PRODUCT_COUNT: int = 10
OFFICIAL_AI_FIXED_PRODUCT: str = "fu.SHFE"
OFFICIAL_AI_TOTAL_PRODUCT_COUNT: int = OFFICIAL_AI_RANKED_PRODUCT_COUNT + 1
OFFICIAL_AI_PRODUCT_POOL_STRATEGY: str = "ai_top10_plus_fu_official_live_v1"
OFFICIAL_AI_PRE_AI_EVAL_DATE: str = "2019-12-31"
OFFICIAL_AI_PRE_AI_PRODUCT_COUNT: int = 18
OFFICIAL_AI_PRE_AI_SCORE_TYPE: str = "static18_pre_ai_boundary"


def _exact_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    return int(number)


def _canonical_eval_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def official_ai_pool_snapshot_blockers(
    *,
    products: Sequence[Any],
    ranks: Sequence[Any],
    top_ns: Sequence[Any],
    eval_date: Any | None = None,
    score_types: Sequence[Any] | None = None,
) -> list[str]:
    """Validate the fixed pre-AI boundary or one Top10-ranked plus fu month."""
    normalized_products: list[str] = []
    invalid_product_value = False
    for value in products:
        if value is None:
            invalid_product_value = True
            normalized_products.append("")
            continue
        try:
            if value != value:
                invalid_product_value = True
                normalized_products.append("")
                continue
        except (TypeError, ValueError):
            invalid_product_value = True
            normalized_products.append("")
            continue
        normalized = str(value).strip()
        if not normalized or normalized.casefold() in {"nan", "none", "<na>"}:
            invalid_product_value = True
        normalized_products.append(normalized)
    normalized_ranks: list[int | None] = []
    normalized_top_ns: list[int | None] = []
    for value in ranks:
        normalized_ranks.append(_exact_integer(value))
    for value in top_ns:
        normalized_top_ns.append(_exact_integer(value))

    canonical_eval_date = _canonical_eval_date(eval_date)
    normalized_score_types: list[str] = []
    invalid_score_type = score_types is None or len(score_types) != len(products)
    score_type_values = () if score_types is None else score_types
    for value in score_type_values:
        if value is None:
            invalid_score_type = True
            normalized_score_types.append("")
            continue
        try:
            if value != value:
                invalid_score_type = True
                normalized_score_types.append("")
                continue
        except (TypeError, ValueError):
            invalid_score_type = True
            normalized_score_types.append("")
            continue
        normalized = str(value).strip()
        if not normalized or normalized.casefold() in {"nan", "none", "<na>"}:
            invalid_score_type = True
        normalized_score_types.append(normalized)

    blockers: list[str] = []
    if invalid_product_value:
        blockers.append("product_value")
    if eval_date is not None and canonical_eval_date is None:
        blockers.append("eval_date")

    if canonical_eval_date == OFFICIAL_AI_PRE_AI_EVAL_DATE:
        if len(normalized_products) != OFFICIAL_AI_PRE_AI_PRODUCT_COUNT:
            blockers.append("pre_ai_row_count")
        if len(set(normalized_products)) != OFFICIAL_AI_PRE_AI_PRODUCT_COUNT:
            blockers.append("pre_ai_unique_product_count")
        if OFFICIAL_AI_FIXED_PRODUCT in normalized_products:
            blockers.append("pre_ai_contains_fixed_product")
        expected_ranks = list(range(1, OFFICIAL_AI_PRE_AI_PRODUCT_COUNT + 1))
        if sorted(
            normalized_ranks,
            key=lambda value: value if value is not None else -1,
        ) != expected_ranks:
            blockers.append("pre_ai_rank_range")
        if set(normalized_top_ns) != {OFFICIAL_AI_PRE_AI_PRODUCT_COUNT}:
            blockers.append("pre_ai_top_n")
        if (
            invalid_score_type
            or len(normalized_score_types) != OFFICIAL_AI_PRE_AI_PRODUCT_COUNT
            or any(
                not value.endswith(OFFICIAL_AI_PRE_AI_SCORE_TYPE)
                for value in normalized_score_types
            )
        ):
            blockers.append("pre_ai_score_type")
        return blockers

    if invalid_score_type:
        blockers.append("score_type")
    if any(
        value.endswith(OFFICIAL_AI_PRE_AI_SCORE_TYPE)
        for value in normalized_score_types
    ):
        blockers.append("pre_ai_score_type_date")
    if len(normalized_products) != OFFICIAL_AI_TOTAL_PRODUCT_COUNT:
        blockers.append("row_count")
    if len(set(normalized_products)) != OFFICIAL_AI_TOTAL_PRODUCT_COUNT:
        blockers.append("unique_product_count")
    if normalized_products.count(OFFICIAL_AI_FIXED_PRODUCT) != 1:
        blockers.append("missing_fixed_product")
    non_fixed = [
        product
        for product in normalized_products
        if product != OFFICIAL_AI_FIXED_PRODUCT
    ]
    if len(non_fixed) != OFFICIAL_AI_RANKED_PRODUCT_COUNT:
        blockers.append("ranked_product_count")
    expected_ranks = list(range(1, OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1))
    if sorted(normalized_ranks, key=lambda value: value if value is not None else -1) != expected_ranks:
        blockers.append("rank_range")
    if set(normalized_top_ns) != {OFFICIAL_AI_TOTAL_PRODUCT_COUNT}:
        blockers.append("top_n")
    fixed_ranks = [
        rank
        for product, rank in zip(normalized_products, normalized_ranks, strict=False)
        if product == OFFICIAL_AI_FIXED_PRODUCT
    ]
    if fixed_ranks != [OFFICIAL_AI_TOTAL_PRODUCT_COUNT]:
        blockers.append("fixed_product_rank")
    return blockers
