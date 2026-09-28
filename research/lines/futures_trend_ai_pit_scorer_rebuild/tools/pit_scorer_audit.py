"""Core audits for rebuilding the formal AI scorer with point-in-time data."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
FUTURE_PNL_COLUMN = "future_net_pnl_60d"
TARGET_COLUMN = "target_future_top_half_60d"
PIT_TARGET_COLUMN = "pit_target_future_top_half_60d"


class PitScorerAuditError(RuntimeError):
    """Raised when a frozen PIT audit contract cannot be established."""


def _normalise_dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="raise").dt.tz_localize(None).dt.normalize()


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise PitScorerAuditError(f"{label}_columns_missing:{','.join(missing)}")


def recover_label_boundaries(
    daily: pd.DataFrame,
    samples: pd.DataFrame,
    *,
    horizon: int = 60,
) -> pd.DataFrame:
    """Recover the exact forward observations consumed by the legacy target."""
    if horizon <= 0:
        raise PitScorerAuditError("horizon_must_be_positive")
    _require_columns(daily, {"date", PRODUCT_COLUMN, "net_pnl"}, "daily")
    _require_columns(samples, {DATE_COLUMN, PRODUCT_COLUMN, FUTURE_PNL_COLUMN}, "samples")

    day = daily[["date", PRODUCT_COLUMN, "net_pnl"]].copy()
    day["date"] = _normalise_dates(day["date"])
    day[PRODUCT_COLUMN] = day[PRODUCT_COLUMN].astype(str)
    day["net_pnl"] = pd.to_numeric(day["net_pnl"], errors="raise").astype("float64")
    if day.duplicated(["date", PRODUCT_COLUMN]).any():
        raise PitScorerAuditError("daily_date_product_duplicate")

    sample = samples.copy()
    sample[DATE_COLUMN] = _normalise_dates(sample[DATE_COLUMN])
    sample[PRODUCT_COLUMN] = sample[PRODUCT_COLUMN].astype(str)
    sample[FUTURE_PNL_COLUMN] = pd.to_numeric(
        sample[FUTURE_PNL_COLUMN], errors="coerce"
    ).astype("float64")
    if sample.duplicated([DATE_COLUMN, PRODUCT_COLUMN]).any():
        raise PitScorerAuditError("sample_date_product_duplicate")

    calendars: dict[str, tuple[pd.DatetimeIndex, np.ndarray, dict[pd.Timestamp, int]]] = {}
    for product, group in day.groupby(PRODUCT_COLUMN, sort=False):
        ordered = group.sort_values("date", kind="mergesort")
        dates = pd.DatetimeIndex(ordered["date"])
        values = ordered["net_pnl"].to_numpy(dtype="float64")
        calendars[str(product)] = (
            dates,
            values,
            {pd.Timestamp(value): index for index, value in enumerate(dates)},
        )

    starts: list[pd.Timestamp | pd.NaT] = []
    ends: list[pd.Timestamp | pd.NaT] = []
    counts: list[int] = []
    sums: list[float] = []
    for row in sample.itertuples(index=False):
        product = str(getattr(row, PRODUCT_COLUMN))
        eval_date = pd.Timestamp(getattr(row, DATE_COLUMN))
        if product not in calendars:
            raise PitScorerAuditError(f"sample_product_missing_from_daily:{product}")
        dates, values, positions = calendars[product]
        if eval_date not in positions:
            raise PitScorerAuditError(
                f"sample_date_missing_from_daily:{product}:{eval_date.date().isoformat()}"
            )
        position = positions[eval_date]
        observation_count = min(horizon, max(0, len(dates) - position - 1))
        start_position = position + 1
        end_position = position + observation_count
        if observation_count:
            starts.append(pd.Timestamp(dates[start_position]))
            ends.append(pd.Timestamp(dates[end_position]))
            sums.append(float(np.sum(values[start_position : end_position + 1])))
        else:
            starts.append(pd.NaT)
            ends.append(pd.NaT)
            sums.append(float("nan"))
        counts.append(int(observation_count))

    sample["future_label_start_date"] = starts
    sample["future_label_end_date"] = ends
    sample["future_observation_count"] = counts
    sample["full_horizon_label"] = sample["future_observation_count"].eq(horizon)
    sample["recomputed_future_net_pnl"] = sums
    sample["legacy_future_net_pnl_abs_diff"] = (
        sample[FUTURE_PNL_COLUMN] - sample["recomputed_future_net_pnl"]
    ).abs()
    return sample


def audit_fold_label_overlap(
    samples: pd.DataFrame,
    windows: pd.DataFrame,
) -> pd.DataFrame:
    """Audit train labels against test starts using a strict non-overlap rule."""
    _require_columns(
        samples,
        {DATE_COLUMN, PRODUCT_COLUMN, "future_label_end_date"},
        "samples",
    )
    _require_columns(
        windows,
        {"window_id", "train_start", "train_end", "test_start", "test_end"},
        "windows",
    )
    panel = samples.copy()
    panel[DATE_COLUMN] = _normalise_dates(panel[DATE_COLUMN])
    panel["future_label_end_date"] = _normalise_dates(
        panel["future_label_end_date"]
    )
    folds = windows[
        ["window_id", "train_start", "train_end", "test_start", "test_end"]
    ].drop_duplicates().copy()
    for column in ("train_start", "train_end", "test_start", "test_end"):
        folds[column] = _normalise_dates(folds[column])
    if folds["window_id"].duplicated().any():
        raise PitScorerAuditError("window_id_duplicate_with_different_boundaries")

    rows: list[dict[str, Any]] = []
    for fold in folds.sort_values("window_id", kind="mergesort").itertuples(index=False):
        train = panel[
            panel[DATE_COLUMN].ge(fold.train_start)
            & panel[DATE_COLUMN].lt(fold.train_end)
        ].copy()
        test = panel[
            panel[DATE_COLUMN].ge(fold.test_start)
            & panel[DATE_COLUMN].lt(fold.test_end)
        ].copy()
        missing_end = train["future_label_end_date"].isna()
        overlap = train["future_label_end_date"].ge(fold.test_start)
        invalid = missing_end | overlap
        clean = train[~invalid]
        overlap_dates = sorted(train.loc[overlap, DATE_COLUMN].unique())
        rows.append(
            {
                "window_id": str(fold.window_id),
                "train_start": pd.Timestamp(fold.train_start),
                "train_end": pd.Timestamp(fold.train_end),
                "test_start": pd.Timestamp(fold.test_start),
                "test_end": pd.Timestamp(fold.test_end),
                "train_rows": int(len(train)),
                "train_months": int(train[DATE_COLUMN].nunique()),
                "test_rows": int(len(test)),
                "test_months": int(test[DATE_COLUMN].nunique()),
                "overlap_rows": int(overlap.sum()),
                "overlap_months": int(train.loc[overlap, DATE_COLUMN].nunique()),
                "overlap_eval_dates": ",".join(
                    pd.Timestamp(value).date().isoformat() for value in overlap_dates
                ),
                "missing_label_end_rows": int(missing_end.sum()),
                "strict_clean_train_rows": int(len(clean)),
                "strict_clean_train_months": int(clean[DATE_COLUMN].nunique()),
                "strict_train_label_end_max": (
                    pd.Timestamp(clean["future_label_end_date"].max())
                    if not clean.empty
                    else pd.NaT
                ),
                "strict_non_overlap_pass": bool(not invalid.any()),
            }
        )
    return pd.DataFrame(rows)


def build_effective_listing_dates(
    products: Sequence[str],
    official_listing_dates: Mapping[str, Any],
    first_valid_ohlc_dates: Mapping[str, Any],
) -> dict[str, pd.Timestamp]:
    """Use the later of the official listing date and first valid local bar."""
    result: dict[str, pd.Timestamp] = {}
    for product in map(str, products):
        if product not in first_valid_ohlc_dates:
            raise PitScorerAuditError(f"first_valid_ohlc_missing:{product}")
        candidates = [pd.Timestamp(first_valid_ohlc_dates[product]).normalize()]
        if product in official_listing_dates:
            candidates.append(pd.Timestamp(official_listing_dates[product]).normalize())
        if any(pd.isna(value) for value in candidates):
            raise PitScorerAuditError(f"listing_date_invalid:{product}")
        result[product] = max(candidates)
    return result


def apply_listing_filter_before_target(
    samples: pd.DataFrame,
    effective_listing_dates: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter unlisted products before rebuilding each monthly cross-section target."""
    _require_columns(
        samples,
        {DATE_COLUMN, PRODUCT_COLUMN, FUTURE_PNL_COLUMN},
        "samples",
    )
    frame = samples.copy()
    frame[DATE_COLUMN] = _normalise_dates(frame[DATE_COLUMN])
    frame[PRODUCT_COLUMN] = frame[PRODUCT_COLUMN].astype(str)
    availability = {
        str(product): pd.Timestamp(value).normalize()
        for product, value in effective_listing_dates.items()
    }
    unknown = sorted(set(frame[PRODUCT_COLUMN]) - set(availability))
    if unknown:
        raise PitScorerAuditError(f"listing_date_missing:{','.join(unknown)}")
    frame["pit_listing_date"] = frame[PRODUCT_COLUMN].map(availability)
    frame["pit_listing_eligible"] = frame[DATE_COLUMN].ge(frame["pit_listing_date"])

    audit_rows: list[dict[str, Any]] = []
    eligible_months: list[pd.DataFrame] = []
    for eval_date, month in frame.groupby(DATE_COLUMN, sort=True):
        kept = month[month["pit_listing_eligible"]].copy()
        removed = month[~month["pit_listing_eligible"]].copy()
        if kept.empty:
            raise PitScorerAuditError(
                f"eligible_cross_section_empty:{pd.Timestamp(eval_date).date().isoformat()}"
            )
        kept["pit_future_rank_pct_60d"] = kept[FUTURE_PNL_COLUMN].rank(
            method="average", pct=True
        )
        kept["pit_future_rank_centered_60d"] = (
            kept["pit_future_rank_pct_60d"] - 0.5
        )
        kept[PIT_TARGET_COLUMN] = (
            kept["pit_future_rank_centered_60d"] > 0.0
        ).astype("int64")
        changed = 0
        if TARGET_COLUMN in kept.columns:
            legacy = pd.to_numeric(kept[TARGET_COLUMN], errors="raise").astype("int64")
            changed = int(legacy.ne(kept[PIT_TARGET_COLUMN]).sum())
        audit_rows.append(
            {
                DATE_COLUMN: pd.Timestamp(eval_date),
                "legacy_cross_section_count": int(len(month)),
                "eligible_cross_section_count": int(len(kept)),
                "ineligible_sample_rows": int(len(removed)),
                "ineligible_products": ",".join(
                    sorted(removed[PRODUCT_COLUMN].astype(str).tolist())
                ),
                "eligible_target_changed_rows": changed,
            }
        )
        eligible_months.append(kept)
    eligible = pd.concat(eligible_months, ignore_index=True)
    eligible.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True, kind="mergesort")
    eligible.reset_index(drop=True, inplace=True)
    return eligible, pd.DataFrame(audit_rows)


def _contract_product(
    symbol: object,
    exchange: object,
    products: Sequence[str],
) -> str | None:
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", str(symbol))
    if match is None:
        return None
    code, delivery = match.groups()
    if len(set(delivery)) == 1 and delivery[0] in {"8", "9"}:
        return None
    if not 1 <= int(delivery[-2:]) <= 12:
        return None
    matches = [
        product
        for product in map(str, products)
        if product.partition(".")[2] == str(exchange)
        and product.partition(".")[0].lower() == code.lower()
    ]
    if len(matches) > 1:
        raise PitScorerAuditError(f"contract_product_ambiguous:{symbol}:{exchange}")
    return matches[0] if matches else None


def derive_first_valid_ohlc_dates(
    bars: pd.DataFrame,
    products: Sequence[str],
) -> dict[str, pd.Timestamp]:
    """Find the first ordinary-contract row with finite, strictly positive OHLC."""
    price_columns = ["open_price", "high_price", "low_price", "close_price"]
    _require_columns(
        bars,
        {"datetime", "symbol", "exchange", *price_columns},
        "bars",
    )
    frame = bars.copy()
    frame["date"] = _normalise_dates(frame["datetime"])
    frame[PRODUCT_COLUMN] = [
        _contract_product(symbol, exchange, products)
        for symbol, exchange in zip(
            frame["symbol"], frame["exchange"], strict=True
        )
    ]
    for column in price_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    finite_positive = np.isfinite(frame[price_columns]).all(axis=1) & frame[
        price_columns
    ].gt(0.0).all(axis=1)
    valid = frame[frame[PRODUCT_COLUMN].notna() & finite_positive].copy()
    if valid.empty:
        return {}
    first = valid.groupby(PRODUCT_COLUMN, sort=True)["date"].min()
    return {str(product): pd.Timestamp(value) for product, value in first.items()}


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    symbol, separator, exchange = raw.partition(".")
    if not separator:
        return raw
    match = re.match(r"^([A-Za-z]+)", symbol)
    code = match.group(1) if match else symbol
    return f"{code}.{exchange}"


def classify_universe_provenance(
    *,
    sample_products: set[str],
    current_products: set[str],
    observed_position_products: set[str],
    mapping_products: set[str],
    historical_approval_source: Path | str | None,
) -> dict[str, Any]:
    historical_source_exists = bool(
        historical_approval_source is not None
        and Path(historical_approval_source).is_file()
    )
    exact_current = sample_products == current_products
    exact_positions = sample_products == observed_position_products
    broader_mapping = bool(mapping_products - sample_products)
    if historical_source_exists:
        classification = "historical_asof_source_present_requires_content_validation"
    else:
        classification = "fixed_current_design_universe_only"
    return {
        "classification": classification,
        "historical_asof_universe_reconstructable": False,
        "historical_approval_source": (
            str(Path(historical_approval_source).resolve())
            if historical_source_exists
            else None
        ),
        "sample_matches_current_universe": exact_current,
        "sample_matches_observed_position_products": exact_positions,
        "mapping_has_broader_products": broader_mapping,
        "sample_product_count": len(sample_products),
        "current_product_count": len(current_products),
        "observed_position_product_count": len(observed_position_products),
        "mapping_product_count": len(mapping_products),
        "sample_products": sorted(sample_products),
        "current_only_products": sorted(current_products - sample_products),
        "sample_only_products": sorted(sample_products - current_products),
        "mapping_only_products": sorted(mapping_products - sample_products),
    }


def finite_max_abs(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if numeric.dropna().empty:
        return float("nan")
    result = float(numeric.abs().max())
    return result if math.isfinite(result) else float("nan")

