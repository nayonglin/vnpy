"""Pure builders for roll-adjusted, direction-neutral trend-quality labels."""

from __future__ import annotations

from collections.abc import Iterable
from math import ceil

import numpy as np
import pandas as pd


class TrendQualityError(RuntimeError):
    pass


PATH_KEYS = ["query_date", "product_vt_symbol"]
LEG_KEYS = [*PATH_KEYS, "leg_index"]


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise TrendQualityError(f"missing_columns:{name}:{','.join(missing)}")


def _normalise_dates(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if result[column].isna().any():
            raise TrendQualityError(f"invalid_date:{name}:{column}")
    return result


def normalise_contract_prices(bars: pd.DataFrame) -> pd.DataFrame:
    """Return one close observation per date and actual futures contract."""
    if {"date", "contract_vt_symbol", "close_price"}.issubset(bars.columns):
        result = bars[["date", "contract_vt_symbol", "close_price"]].copy()
    else:
        _require_columns(
            bars,
            ["datetime", "symbol", "exchange", "close_price"],
            "bars",
        )
        result = bars.copy()
        if "interval" in result.columns:
            result = result[result["interval"].astype(str).eq("d")].copy()
        result["date"] = result["datetime"]
        result["contract_vt_symbol"] = (
            result["symbol"].astype(str).str.strip()
            + "."
            + result["exchange"].astype(str).str.strip()
        )
        result = result[["date", "contract_vt_symbol", "close_price"]]
    result = _normalise_dates(result, ["date"], "bars")
    result["contract_vt_symbol"] = (
        result["contract_vt_symbol"].astype(str).str.strip()
    )
    if result["contract_vt_symbol"].eq("").any():
        raise TrendQualityError("empty_contract_price_identity")
    result["close_price"] = pd.to_numeric(
        result["close_price"], errors="coerce"
    ).astype(float)
    result = result.sort_values(
        ["date", "contract_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    if result.duplicated(["date", "contract_vt_symbol"]).any():
        raise TrendQualityError("duplicate_contract_price")
    return result


def build_leg_returns(
    legs: pd.DataFrame,
    contract_prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Compute every return from two closes of the same actual contract."""
    required = [
        *LEG_KEYS,
        "previous_date",
        "return_date",
        "selected_contract_vt",
        "leg_valid",
        "previous_bar_present",
        "return_bar_present",
        "roll_event",
    ]
    _require_columns(legs, required, "legs")
    clean = _normalise_dates(
        legs, ["query_date", "previous_date", "return_date"], "legs"
    )
    clean["product_vt_symbol"] = clean["product_vt_symbol"].astype(str)
    clean["selected_contract_vt"] = (
        clean["selected_contract_vt"].astype(str).str.strip()
    )
    clean["leg_index"] = pd.to_numeric(
        clean["leg_index"], errors="coerce"
    )
    if clean["leg_index"].isna().any():
        raise TrendQualityError("invalid_leg_index")
    clean["leg_index"] = clean["leg_index"].astype(int)
    if clean.duplicated(LEG_KEYS).any():
        raise TrendQualityError("duplicate_leg_identity")
    if clean["selected_contract_vt"].eq("").any():
        raise TrendQualityError("empty_selected_contract")
    if not clean["leg_valid"].fillna(False).astype(bool).all():
        raise TrendQualityError("upstream_leg_invalid")
    if not clean["previous_bar_present"].fillna(False).astype(bool).all():
        raise TrendQualityError("upstream_previous_bar_absent")
    if not clean["return_bar_present"].fillna(False).astype(bool).all():
        raise TrendQualityError("upstream_return_bar_absent")
    if clean["previous_date"].ge(clean["return_date"]).any():
        raise TrendQualityError("leg_date_order_invalid")

    prices = normalise_contract_prices(contract_prices)
    previous = prices.rename(
        columns={
            "date": "previous_date",
            "contract_vt_symbol": "selected_contract_vt",
            "close_price": "previous_close",
        }
    )
    current = prices.rename(
        columns={
            "date": "return_date",
            "contract_vt_symbol": "selected_contract_vt",
            "close_price": "return_close",
        }
    )
    result = clean.merge(
        previous,
        how="left",
        on=["previous_date", "selected_contract_vt"],
        validate="many_to_one",
    ).merge(
        current,
        how="left",
        on=["return_date", "selected_contract_vt"],
        validate="many_to_one",
    )
    missing_count = int(
        result[["previous_close", "return_close"]].isna().any(axis=1).sum()
    )
    if missing_count:
        raise TrendQualityError(f"close_endpoint_missing:{missing_count}")
    valid = (
        np.isfinite(result["previous_close"])
        & np.isfinite(result["return_close"])
        & result["previous_close"].gt(0)
        & result["return_close"].gt(0)
    )
    invalid_count = int((~valid).sum())
    if invalid_count:
        raise TrendQualityError(
            f"close_nonpositive_or_nonfinite:{invalid_count}"
        )
    result["price_contract_vt"] = result["selected_contract_vt"]
    result["comparison_contract_match"] = True
    result["leg_log_return"] = np.log(
        result["return_close"] / result["previous_close"]
    )
    if not np.isfinite(result["leg_log_return"]).all():
        raise TrendQualityError("leg_log_return_nonfinite")
    result["logical_close_reads"] = 2
    result["cross_contract_price_comparisons"] = 0
    result = result.sort_values(LEG_KEYS, kind="mergesort").reset_index(
        drop=True
    )
    audit = {
        "leg_rows": int(len(result)),
        "logical_close_reads": int(len(result) * 2),
        "missing_endpoint_legs": 0,
        "invalid_close_legs": 0,
        "cross_contract_price_comparisons": 0,
    }
    return result, audit


def _oriented_max_drawdown(returns: np.ndarray, direction: int) -> float:
    oriented = np.asarray(returns, dtype="float64") * float(direction)
    cumulative = np.concatenate(([0.0], np.cumsum(oriented)))
    drawdown = cumulative - np.maximum.accumulate(cumulative)
    return float(drawdown.min())


def aggregate_path_labels(
    leg_returns: pd.DataFrame,
    *,
    expected_leg_count: int = 20,
) -> pd.DataFrame:
    """Aggregate same-contract legs into one direction-neutral path label."""
    _require_columns(
        leg_returns,
        [
            *LEG_KEYS,
            "leg_log_return",
            "selected_contract_vt",
            "comparison_contract_match",
            "cross_contract_price_comparisons",
            "roll_event",
        ],
        "leg_returns",
    )
    if expected_leg_count <= 0:
        raise TrendQualityError("expected_leg_count_invalid")
    clean = _normalise_dates(leg_returns, ["query_date"], "leg_returns")
    clean["leg_index"] = pd.to_numeric(
        clean["leg_index"], errors="coerce"
    )
    clean["leg_log_return"] = pd.to_numeric(
        clean["leg_log_return"], errors="coerce"
    ).astype(float)
    if clean[["leg_index", "leg_log_return"]].isna().any().any():
        raise TrendQualityError("invalid_leg_value")
    clean["leg_index"] = clean["leg_index"].astype(int)
    if clean.duplicated(LEG_KEYS).any():
        raise TrendQualityError("duplicate_leg_identity")
    if not np.isfinite(clean["leg_log_return"]).all():
        raise TrendQualityError("leg_log_return_nonfinite")
    if not clean["comparison_contract_match"].fillna(False).astype(bool).all():
        raise TrendQualityError("cross_contract_comparison_detected")
    if int(clean["cross_contract_price_comparisons"].sum()) != 0:
        raise TrendQualityError("cross_contract_comparison_detected")

    rows: list[dict[str, object]] = []
    expected_indexes = list(range(1, expected_leg_count + 1))
    for identity, group in clean.groupby(PATH_KEYS, sort=False):
        ordered = group.sort_values("leg_index", kind="mergesort")
        if len(ordered) != expected_leg_count:
            raise TrendQualityError(
                f"path_leg_count_invalid:{identity[0]}:{identity[1]}:{len(ordered)}"
            )
        if ordered["leg_index"].tolist() != expected_indexes:
            raise TrendQualityError(
                f"path_leg_index_invalid:{identity[0]}:{identity[1]}"
            )
        returns = ordered["leg_log_return"].to_numpy(dtype="float64")
        path_return = float(np.sum(returns))
        absolute_return = abs(path_return)
        direction = int(np.sign(path_return))
        max_drawdown = _oriented_max_drawdown(returns, direction)
        absolute_variation = float(np.abs(returns).sum())
        efficiency = (
            float(absolute_return / absolute_variation)
            if absolute_variation > 0.0
            else 0.0
        )
        capture_quality = float(absolute_return + max_drawdown)
        rows.append(
            {
                "query_date": identity[0],
                "product_vt_symbol": identity[1],
                "leg_count": int(len(ordered)),
                "roll_count": int(ordered["roll_event"].astype(bool).sum()),
                "contract_count": int(ordered["selected_contract_vt"].nunique()),
                "path_log_return": path_return,
                "future_abs_log_return": absolute_return,
                "future_trend_sign": direction,
                "future_abs_variation": absolute_variation,
                "future_trend_efficiency": efficiency,
                "future_oriented_max_drawdown": max_drawdown,
                "future_trend_capture_quality": capture_quality,
                "logical_close_reads": int(len(ordered) * 2),
                "cross_contract_price_comparisons": 0,
                "return_sum_error": abs(path_return - float(returns.sum())),
                "efficiency_formula_error": abs(
                    efficiency
                    - (
                        absolute_return / absolute_variation
                        if absolute_variation > 0.0
                        else 0.0
                    )
                ),
                "drawdown_formula_error": abs(
                    max_drawdown
                    - _oriented_max_drawdown(returns, direction)
                ),
                "capture_quality_formula_error": abs(
                    capture_quality - (absolute_return + max_drawdown)
                ),
            }
        )
    result = pd.DataFrame(rows).sort_values(
        PATH_KEYS, kind="mergesort"
    ).reset_index(drop=True)
    numeric = [
        "path_log_return",
        "future_abs_log_return",
        "future_abs_variation",
        "future_trend_efficiency",
        "future_oriented_max_drawdown",
        "future_trend_capture_quality",
    ]
    if not np.isfinite(result[numeric].to_numpy(dtype="float64")).all():
        raise TrendQualityError("path_label_nonfinite")
    tolerance = 1e-12
    if result["future_trend_efficiency"].lt(-tolerance).any() or result[
        "future_trend_efficiency"
    ].gt(1.0 + tolerance).any():
        raise TrendQualityError("trend_efficiency_out_of_bounds")
    if result["future_oriented_max_drawdown"].gt(tolerance).any():
        raise TrendQualityError("oriented_drawdown_positive")
    if (
        result["future_trend_capture_quality"]
        > result["future_abs_log_return"] + tolerance
    ).any():
        raise TrendQualityError("capture_quality_exceeds_absolute_return")
    return result


def add_cross_sectional_relevance(
    path_labels: pd.DataFrame,
    *,
    levels: int = 5,
    minimum_qid_width: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create tie-preserving relevance levels within each query-date qid."""
    _require_columns(
        path_labels,
        [*PATH_KEYS, "future_trend_capture_quality"],
        "path_labels",
    )
    if levels < 2:
        raise TrendQualityError("relevance_levels_invalid")
    if minimum_qid_width < levels:
        raise TrendQualityError("minimum_qid_width_below_levels")
    result = _normalise_dates(path_labels, ["query_date"], "path_labels")
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result["future_trend_capture_quality"] = pd.to_numeric(
        result["future_trend_capture_quality"], errors="coerce"
    ).astype(float)
    if result.duplicated(PATH_KEYS).any():
        raise TrendQualityError("duplicate_path_identity")
    if not np.isfinite(result["future_trend_capture_quality"]).all():
        raise TrendQualityError("path_target_nonfinite")
    grouped = result.groupby("query_date", sort=False)
    widths = grouped["product_vt_symbol"].size()
    if widths.lt(minimum_qid_width).any():
        first = widths[widths.lt(minimum_qid_width)].index[0]
        raise TrendQualityError(f"qid_width_below_minimum:{first.date()}")
    unique_counts = grouped["future_trend_capture_quality"].nunique(
        dropna=False
    )
    if unique_counts.lt(levels).any():
        first = unique_counts[unique_counts.lt(levels)].index[0]
        raise TrendQualityError(
            f"qid_target_unique_below_levels:{first.date()}"
        )
    percentile = grouped["future_trend_capture_quality"].rank(
        method="average", pct=True
    )
    result["trend_quality_relevance"] = (
        np.ceil(percentile * levels)
        .sub(1)
        .clip(lower=0, upper=levels - 1)
        .astype(int)
    )
    diagnostics = result.groupby("query_date", sort=False).agg(
        qid_width=("product_vt_symbol", "size"),
        target_unique_count=("future_trend_capture_quality", "nunique"),
        relevance_level_count=("trend_quality_relevance", "nunique"),
        target_min=("future_trend_capture_quality", "min"),
        target_median=("future_trend_capture_quality", "median"),
        target_max=("future_trend_capture_quality", "max"),
        target_std=("future_trend_capture_quality", "std"),
    ).reset_index()
    if diagnostics["relevance_level_count"].lt(levels).any():
        first = diagnostics.loc[
            diagnostics["relevance_level_count"].lt(levels), "query_date"
        ].iloc[0]
        raise TrendQualityError(
            f"qid_relevance_levels_incomplete:{first.date()}"
        )
    if not np.isfinite(diagnostics["target_std"]).all() or diagnostics[
        "target_std"
    ].le(0.0).any():
        raise TrendQualityError("qid_target_degenerate")
    return (
        result.sort_values(PATH_KEYS, kind="mergesort").reset_index(drop=True),
        diagnostics.sort_values("query_date", kind="mergesort").reset_index(
            drop=True
        ),
    )

