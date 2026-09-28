from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import Iterable

import numpy as np
import pandas as pd


RAW_PATH_FEATURES = [
    "momentum_21",
    "momentum_63",
    "momentum_126",
    "momentum_252",
    "trend_efficiency_63",
    "trend_efficiency_126",
    "realized_vol_21",
    "realized_vol_63",
    "volume_ratio_20_60",
    "open_interest_ratio_20_60",
]
RAW_CURVE_FEATURES = [
    "front_next_basis_annualized",
    "full_curve_backwardation_slope",
    "volume_hhi",
    "open_interest_hhi",
]
RAW_FEATURES = [*RAW_PATH_FEATURES, *RAW_CURVE_FEATURES]
PAIRWISE_FEATURES = [f"{feature}_pct_delta_vs_rank10" for feature in RAW_FEATURES]
CONTEXT_FEATURES = [
    "market_median_abs_momentum_126",
    "market_median_realized_vol_63",
]
MODEL_FEATURES = [*PAIRWISE_FEATURES, *CONTEXT_FEATURES]


class FeatureError(RuntimeError):
    pass


@dataclass(frozen=True)
class FeatureConfig:
    return_windows: tuple[int, ...] = (21, 63, 126, 252)
    efficiency_windows: tuple[int, ...] = (63, 126)
    volatility_windows: tuple[int, ...] = (21, 63)
    short_liquidity_window: int = 20
    long_liquidity_window: int = 60
    minimum_valid_ratio: float = 0.90
    minimum_nonzero_months: int = 44
    minimum_train_months: int = 24

    def __post_init__(self) -> None:
        if self.return_windows != (21, 63, 126, 252):
            raise ValueError("return_windows_must_match_frozen_contract")
        if self.efficiency_windows != (63, 126):
            raise ValueError("efficiency_windows_must_match_frozen_contract")
        if self.volatility_windows != (21, 63):
            raise ValueError("volatility_windows_must_match_frozen_contract")
        if self.short_liquidity_window != 20 or self.long_liquidity_window != 60:
            raise ValueError("liquidity_windows_must_match_frozen_contract")
        if not 0 < self.minimum_valid_ratio <= 1:
            raise ValueError("minimum_valid_ratio_out_of_range")
        if self.minimum_nonzero_months < 1 or self.minimum_train_months < 1:
            raise ValueError("minimum_counts_must_be_positive")


@dataclass(frozen=True)
class FeatureBundle:
    raw_features: pd.DataFrame
    model_features: pd.DataFrame
    label_plan: pd.DataFrame
    fold_plan: pd.DataFrame
    diagnostics: pd.DataFrame


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise FeatureError(f"missing_columns:{name}:{','.join(missing)}")


def _normalise_date(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce").dt.normalize()
    if values.isna().any():
        raise FeatureError("invalid_date_value")
    return values


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def build_product_return_history(
    mapping: pd.DataFrame,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    """Splice product history from returns computed inside each concrete contract."""
    _require_columns(
        mapping,
        ["date", "continuous_symbol_vt", "main_contract_vt"],
        "mapping",
    )
    _require_columns(
        bars,
        [
            "datetime",
            "symbol",
            "exchange",
            "close_price",
            "volume",
            "open_interest",
        ],
        "bars",
    )

    clean_mapping = mapping[
        ["date", "continuous_symbol_vt", "main_contract_vt"]
    ].copy()
    clean_mapping["date"] = _normalise_date(clean_mapping["date"])
    for column in ["continuous_symbol_vt", "main_contract_vt"]:
        clean_mapping[column] = clean_mapping[column].astype("string").str.strip()
    resolved = (
        clean_mapping["continuous_symbol_vt"].notna()
        & clean_mapping["continuous_symbol_vt"].ne("")
        & clean_mapping["main_contract_vt"].notna()
        & clean_mapping["main_contract_vt"].ne("")
    )
    clean_mapping = clean_mapping[resolved].copy()
    clean_mapping["continuous_symbol_vt"] = clean_mapping[
        "continuous_symbol_vt"
    ].astype(str)
    clean_mapping["main_contract_vt"] = clean_mapping["main_contract_vt"].astype(str)
    if clean_mapping.duplicated(["date", "continuous_symbol_vt"]).any():
        raise FeatureError("duplicate_product_mapping")

    clean_bars = bars.copy()
    if "interval" in clean_bars.columns:
        clean_bars = clean_bars[clean_bars["interval"].astype(str).eq("d")].copy()
    clean_bars["date"] = _normalise_date(clean_bars["datetime"])
    clean_bars["contract_vt_symbol"] = (
        clean_bars["symbol"].astype(str) + "." + clean_bars["exchange"].astype(str)
    )
    for column in ["close_price", "volume", "open_interest"]:
        clean_bars[column] = _numeric(clean_bars[column])
    clean_bars = clean_bars.sort_values(
        ["contract_vt_symbol", "date"], kind="mergesort"
    )
    if clean_bars.duplicated(["contract_vt_symbol", "date"]).any():
        raise FeatureError("duplicate_contract_daily_bar")

    prior_close = clean_bars.groupby("contract_vt_symbol", sort=False)[
        "close_price"
    ].shift(1)
    valid_return = (
        np.isfinite(clean_bars["close_price"])
        & np.isfinite(prior_close)
        & clean_bars["close_price"].gt(0)
        & prior_close.gt(0)
    )
    clean_bars["log_return"] = np.nan
    clean_bars.loc[valid_return, "log_return"] = np.log(
        clean_bars.loc[valid_return, "close_price"] / prior_close.loc[valid_return]
    )

    selected = clean_mapping.merge(
        clean_bars[
            [
                "date",
                "contract_vt_symbol",
                "close_price",
                "volume",
                "open_interest",
                "log_return",
            ]
        ],
        how="left",
        left_on=["date", "main_contract_vt"],
        right_on=["date", "contract_vt_symbol"],
        validate="one_to_one",
    )
    selected = selected.rename(columns={"continuous_symbol_vt": "product_vt_symbol"})
    result = selected[
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "close_price",
            "volume",
            "open_interest",
            "log_return",
        ]
    ].sort_values(["product_vt_symbol", "date"], kind="mergesort")
    return result.reset_index(drop=True)


def _finite_values_with_coverage(
    values: pd.Series,
    window: int,
    minimum_valid_ratio: float,
    error_prefix: str,
) -> np.ndarray:
    tail = _numeric(values.tail(window))
    finite = np.isfinite(tail.to_numpy(float))
    required = ceil(window * minimum_valid_ratio)
    if len(tail) < window or int(finite.sum()) < required:
        raise FeatureError(
            f"{error_prefix}:window={window}:valid={int(finite.sum())}:required={required}"
        )
    return tail.to_numpy(float)[finite]


def _positive_values_with_coverage(
    values: pd.Series,
    window: int,
    minimum_valid_ratio: float,
    error_prefix: str,
) -> np.ndarray:
    tail = _numeric(values.tail(window)).to_numpy(float)
    valid = np.isfinite(tail) & (tail > 0)
    required = ceil(window * minimum_valid_ratio)
    if len(tail) < window or int(valid.sum()) < required:
        raise FeatureError(
            f"{error_prefix}:window={window}:valid={int(valid.sum())}:required={required}"
        )
    return tail[valid]


def audit_trailing_coverage(
    history: pd.DataFrame,
    action_rows: pd.DataFrame,
    *,
    config: FeatureConfig,
) -> pd.DataFrame:
    _require_columns(
        history,
        ["date", "product_vt_symbol", "log_return", "volume", "open_interest"],
        "history",
    )
    _require_columns(action_rows, ["eval_date", "product_vt_symbol"], "action_rows")
    clean_history = history.copy()
    clean_history["date"] = _normalise_date(clean_history["date"])
    clean_history["product_vt_symbol"] = clean_history["product_vt_symbol"].astype(
        str
    )
    clean_history = clean_history.sort_values(
        ["product_vt_symbol", "date"], kind="mergesort"
    )
    if clean_history.duplicated(["date", "product_vt_symbol"]).any():
        raise FeatureError("duplicate_product_history_row")

    actions = action_rows[["eval_date", "product_vt_symbol"]].copy()
    actions["eval_date"] = _normalise_date(actions["eval_date"])
    actions["product_vt_symbol"] = actions["product_vt_symbol"].astype(str)
    if actions.duplicated().any():
        raise FeatureError("duplicate_action_row")
    grouped = {
        product: group.reset_index(drop=True)
        for product, group in clean_history.groupby("product_vt_symbol", sort=False)
    }

    failures: list[dict[str, object]] = []
    checks = [
        (
            "log_return",
            config.return_windows,
            False,
            "return_window_coverage_below_minimum",
        ),
        (
            "volume",
            (config.short_liquidity_window, config.long_liquidity_window),
            True,
            "volume_window_coverage_below_minimum",
        ),
        (
            "open_interest",
            (config.short_liquidity_window, config.long_liquidity_window),
            True,
            "open_interest_window_coverage_below_minimum",
        ),
    ]
    for action in actions.itertuples(index=False):
        product_history = grouped.get(action.product_vt_symbol)
        if product_history is None:
            failures.append(
                {
                    "eval_date": action.eval_date,
                    "product_vt_symbol": action.product_vt_symbol,
                    "issue": "missing_product_history",
                    "source_column": "",
                    "window": 0,
                    "available_count": 0,
                    "valid_count": 0,
                    "required_count": 1,
                }
            )
            continue
        usable = product_history[product_history["date"].le(action.eval_date)]
        for column, windows, positive_required, issue in checks:
            for window in windows:
                values = _numeric(usable[column].tail(window)).to_numpy(float)
                valid = np.isfinite(values)
                if positive_required:
                    valid &= values > 0
                required = ceil(window * config.minimum_valid_ratio)
                if len(values) < window or int(valid.sum()) < required:
                    failures.append(
                        {
                            "eval_date": action.eval_date,
                            "product_vt_symbol": action.product_vt_symbol,
                            "issue": issue,
                            "source_column": column,
                            "window": int(window),
                            "available_count": int(len(values)),
                            "valid_count": int(valid.sum()),
                            "required_count": int(required),
                        }
                    )
    columns = [
        "eval_date",
        "product_vt_symbol",
        "issue",
        "source_column",
        "window",
        "available_count",
        "valid_count",
        "required_count",
    ]
    return pd.DataFrame(failures, columns=columns).sort_values(
        ["eval_date", "product_vt_symbol", "source_column", "window"],
        kind="mergesort",
    ).reset_index(drop=True)


def compute_trailing_features(
    history: pd.DataFrame,
    action_rows: pd.DataFrame,
    *,
    config: FeatureConfig,
) -> pd.DataFrame:
    _require_columns(
        history,
        [
            "date",
            "product_vt_symbol",
            "log_return",
            "volume",
            "open_interest",
        ],
        "history",
    )
    _require_columns(action_rows, ["eval_date", "product_vt_symbol"], "action_rows")

    clean_history = history.copy()
    clean_history["date"] = _normalise_date(clean_history["date"])
    clean_history["product_vt_symbol"] = clean_history["product_vt_symbol"].astype(
        str
    )
    clean_history = clean_history.sort_values(
        ["product_vt_symbol", "date"], kind="mergesort"
    )
    if clean_history.duplicated(["date", "product_vt_symbol"]).any():
        raise FeatureError("duplicate_product_history_row")

    actions = action_rows[["eval_date", "product_vt_symbol"]].copy()
    actions["eval_date"] = _normalise_date(actions["eval_date"])
    actions["product_vt_symbol"] = actions["product_vt_symbol"].astype(str)
    if actions.duplicated().any():
        raise FeatureError("duplicate_action_row")

    rows: list[dict[str, object]] = []
    grouped = {
        product: group.reset_index(drop=True)
        for product, group in clean_history.groupby("product_vt_symbol", sort=False)
    }
    for action in actions.itertuples(index=False):
        product_history = grouped.get(action.product_vt_symbol)
        if product_history is None:
            raise FeatureError(f"missing_product_history:{action.product_vt_symbol}")
        usable = product_history[product_history["date"].le(action.eval_date)]
        if usable.empty:
            raise FeatureError(
                f"no_history_at_or_before_eval:{action.eval_date.date()}:{action.product_vt_symbol}"
            )

        returns: dict[int, np.ndarray] = {}
        for window in config.return_windows:
            returns[window] = _finite_values_with_coverage(
                usable["log_return"],
                window,
                config.minimum_valid_ratio,
                "return_window_coverage_below_minimum",
            )

        row: dict[str, object] = {
            "eval_date": action.eval_date,
            "product_vt_symbol": action.product_vt_symbol,
        }
        for window in config.return_windows:
            values = returns[window]
            row[f"momentum_{window}"] = float(values.sum() * window / len(values))
        for window in config.efficiency_windows:
            values = returns[window]
            absolute_sum = float(np.abs(values).sum())
            row[f"trend_efficiency_{window}"] = (
                float(abs(values.sum()) / absolute_sum) if absolute_sum > 0 else 0.0
            )
        for window in config.volatility_windows:
            values = returns[window]
            row[f"realized_vol_{window}"] = float(
                np.std(values, ddof=1) * sqrt(252)
            )

        short_volume = _positive_values_with_coverage(
            usable["volume"],
            config.short_liquidity_window,
            config.minimum_valid_ratio,
            "volume_window_coverage_below_minimum",
        )
        long_volume = _positive_values_with_coverage(
            usable["volume"],
            config.long_liquidity_window,
            config.minimum_valid_ratio,
            "volume_window_coverage_below_minimum",
        )
        short_open_interest = _positive_values_with_coverage(
            usable["open_interest"],
            config.short_liquidity_window,
            config.minimum_valid_ratio,
            "open_interest_window_coverage_below_minimum",
        )
        long_open_interest = _positive_values_with_coverage(
            usable["open_interest"],
            config.long_liquidity_window,
            config.minimum_valid_ratio,
            "open_interest_window_coverage_below_minimum",
        )
        row["volume_ratio_20_60"] = float(
            np.log(short_volume.mean() / long_volume.mean())
        )
        row["open_interest_ratio_20_60"] = float(
            np.log(short_open_interest.mean() / long_open_interest.mean())
        )
        row["maximum_source_date_used"] = usable["date"].max()
        row["future_bar_rows_used"] = 0
        rows.append(row)

    result = pd.DataFrame(rows)
    if not np.isfinite(result[RAW_PATH_FEATURES].to_numpy(float)).all():
        raise FeatureError("nonfinite_trailing_feature")
    return result.sort_values(
        ["eval_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def compute_curve_features(
    bars: pd.DataFrame,
    catalog: pd.DataFrame,
    action_rows: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(
        bars,
        [
            "datetime",
            "symbol",
            "exchange",
            "close_price",
            "volume",
            "open_interest",
        ],
        "bars",
    )
    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"],
        "catalog",
    )
    _require_columns(action_rows, ["eval_date", "product_vt_symbol"], "action_rows")

    clean_bars = bars.copy()
    if "interval" in clean_bars.columns:
        clean_bars = clean_bars[clean_bars["interval"].astype(str).eq("d")].copy()
    clean_bars["date"] = _normalise_date(clean_bars["datetime"])
    clean_bars["vt_symbol"] = (
        clean_bars["symbol"].astype(str) + "." + clean_bars["exchange"].astype(str)
    )
    for column in ["close_price", "volume", "open_interest"]:
        clean_bars[column] = _numeric(clean_bars[column])
    if clean_bars.duplicated(["date", "vt_symbol"]).any():
        raise FeatureError("duplicate_curve_daily_bar")

    clean_catalog = catalog[
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"]
    ].copy()
    clean_catalog["vt_symbol"] = clean_catalog["vt_symbol"].astype(str)
    clean_catalog["product_vt_symbol"] = clean_catalog["product_vt_symbol"].astype(
        str
    )
    clean_catalog["delivery_year"] = pd.to_numeric(
        clean_catalog["delivery_year"], errors="coerce"
    )
    clean_catalog["delivery_month"] = pd.to_numeric(
        clean_catalog["delivery_month"], errors="coerce"
    )
    if clean_catalog.duplicated("vt_symbol").any():
        raise FeatureError("duplicate_catalog_contract")

    curve = clean_bars.merge(
        clean_catalog, on="vt_symbol", how="inner", validate="many_to_one"
    )
    curve_groups = {
        (date, product): group
        for (date, product), group in curve.groupby(
            ["date", "product_vt_symbol"], sort=False
        )
    }
    actions = action_rows[["eval_date", "product_vt_symbol"]].copy()
    actions["eval_date"] = _normalise_date(actions["eval_date"])
    actions["product_vt_symbol"] = actions["product_vt_symbol"].astype(str)
    if actions.duplicated().any():
        raise FeatureError("duplicate_action_row")

    rows: list[dict[str, object]] = []
    for action in actions.itertuples(index=False):
        selected = curve_groups.get((action.eval_date, action.product_vt_symbol))
        selected = curve.iloc[0:0].copy() if selected is None else selected.copy()
        eval_month_index = action.eval_date.year * 12 + action.eval_date.month
        selected["maturity_month_index"] = (
            selected["delivery_year"] * 12 + selected["delivery_month"]
        )
        selected["months_to_delivery"] = (
            selected["maturity_month_index"] - eval_month_index
        )
        valid = (
            selected["delivery_year"].notna()
            & selected["delivery_month"].between(1, 12)
            & selected["months_to_delivery"].between(0, 48)
            & np.isfinite(selected["close_price"])
            & selected["close_price"].gt(0)
            & np.isfinite(selected["volume"])
            & selected["volume"].gt(0)
            & np.isfinite(selected["open_interest"])
            & selected["open_interest"].gt(0)
        )
        selected = selected[valid].sort_values(
            ["maturity_month_index", "vt_symbol"], kind="mergesort"
        )
        if len(selected) < 2:
            raise FeatureError(
                f"curve_contract_count_below_minimum:{action.eval_date.date()}:{action.product_vt_symbol}"
            )
        if selected.duplicated("maturity_month_index").any():
            raise FeatureError(
                f"duplicate_curve_maturity:{action.eval_date.date()}:{action.product_vt_symbol}"
            )

        maturity = selected["maturity_month_index"].to_numpy(float)
        log_price = np.log(selected["close_price"].to_numpy(float))
        front_gap = maturity[1] - maturity[0]
        basis = (log_price[0] - log_price[1]) * 12.0 / front_gap
        slope = np.polyfit(maturity, log_price, 1)[0]
        volume = selected["volume"].to_numpy(float)
        open_interest = selected["open_interest"].to_numpy(float)
        rows.append(
            {
                "eval_date": action.eval_date,
                "product_vt_symbol": action.product_vt_symbol,
                "front_next_basis_annualized": float(basis),
                "full_curve_backwardation_slope": float(-slope * 12.0),
                "volume_hhi": float(np.square(volume / volume.sum()).sum()),
                "open_interest_hhi": float(
                    np.square(open_interest / open_interest.sum()).sum()
                ),
                "curve_contract_count": int(len(selected)),
                "maximum_curve_source_date_used": selected["date"].max(),
                "future_curve_rows_used": 0,
            }
        )

    result = pd.DataFrame(rows)
    if not np.isfinite(result[RAW_CURVE_FEATURES].to_numpy(float)).all():
        raise FeatureError("nonfinite_curve_feature")
    return result.sort_values(
        ["eval_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_pairwise_features(
    raw_features: pd.DataFrame,
    coverage: pd.DataFrame,
    monthly: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(
        raw_features,
        ["eval_date", "product_vt_symbol", *RAW_FEATURES],
        "raw_features",
    )
    _require_columns(
        coverage,
        [
            "eval_date",
            "product_vt_symbol",
            "eligible",
            "is_formal_replacement_product",
            "is_pool_outside_challenger",
        ],
        "coverage",
    )
    _require_columns(monthly, ["eval_date", "action_ready"], "monthly")

    clean_raw = raw_features.copy()
    clean_raw["eval_date"] = _normalise_date(clean_raw["eval_date"])
    clean_raw["product_vt_symbol"] = clean_raw["product_vt_symbol"].astype(str)
    if clean_raw.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise FeatureError("duplicate_raw_feature_row")

    action_months = monthly.loc[monthly["action_ready"].astype(bool), ["eval_date"]].copy()
    action_months["eval_date"] = _normalise_date(action_months["eval_date"])
    if action_months.duplicated().any():
        raise FeatureError("duplicate_monthly_action_row")

    action_set = coverage.copy()
    action_set["eval_date"] = _normalise_date(action_set["eval_date"])
    action_set["product_vt_symbol"] = action_set["product_vt_symbol"].astype(str)
    action_set = action_set.merge(action_months, on="eval_date", how="inner")
    selected = action_set["eligible"].astype(bool) & (
        action_set["is_formal_replacement_product"].astype(bool)
        | action_set["is_pool_outside_challenger"].astype(bool)
    )
    action_set = action_set[selected].copy()
    if action_set.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise FeatureError("duplicate_action_set_row")

    anchor_counts = action_set.groupby("eval_date")[
        "is_formal_replacement_product"
    ].sum()
    if not anchor_counts.eq(1).all():
        raise FeatureError("formal_rank10_anchor_count_not_one")
    if (
        action_set["is_formal_replacement_product"].astype(bool)
        & action_set["is_pool_outside_challenger"].astype(bool)
    ).any():
        raise FeatureError("action_role_overlap")

    result = action_set[
        [
            "eval_date",
            "product_vt_symbol",
            "is_formal_replacement_product",
            "is_pool_outside_challenger",
        ]
    ].merge(
        clean_raw,
        on=["eval_date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
    )
    if result[RAW_FEATURES].isna().any().any():
        raise FeatureError("missing_raw_feature_for_action_row")
    if not np.isfinite(result[RAW_FEATURES].to_numpy(float)).all():
        raise FeatureError("nonfinite_raw_feature_for_action_row")
    result["role"] = np.where(
        result["is_formal_replacement_product"].astype(bool),
        "formal_rank10",
        "challenger",
    )

    for raw_feature, pairwise_feature in zip(
        RAW_FEATURES, PAIRWISE_FEATURES, strict=True
    ):
        percentile = result.groupby("eval_date", sort=False)[raw_feature].rank(
            method="average", pct=True
        )
        anchor_percentile = pd.Series(
            np.where(result["role"].eq("formal_rank10"), percentile, np.nan),
            index=result.index,
        ).groupby(result["eval_date"]).transform("max")
        result[pairwise_feature] = percentile - anchor_percentile
        result.loc[result["role"].eq("formal_rank10"), pairwise_feature] = 0.0

    result["market_median_abs_momentum_126"] = result.groupby(
        "eval_date", sort=False
    )["momentum_126"].transform(lambda values: values.abs().median())
    result["market_median_realized_vol_63"] = result.groupby(
        "eval_date", sort=False
    )["realized_vol_63"].transform("median")
    if not np.isfinite(result[MODEL_FEATURES].to_numpy(float)).all():
        raise FeatureError("nonfinite_model_feature")

    columns = [
        "eval_date",
        "product_vt_symbol",
        "role",
        "is_formal_replacement_product",
        "is_pool_outside_challenger",
        *RAW_FEATURES,
        *MODEL_FEATURES,
    ]
    return result[columns].sort_values(
        ["eval_date", "role", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_label_plan(
    model_features: pd.DataFrame,
    all_eval_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    _require_columns(
        model_features,
        ["eval_date", "product_vt_symbol", "role"],
        "model_features",
    )
    dates = pd.DatetimeIndex(pd.to_datetime(all_eval_dates, errors="coerce")).normalize()
    if dates.isna().any() or dates.duplicated().any():
        raise FeatureError("invalid_or_duplicate_eval_dates")
    dates = dates.sort_values()
    next_dates = dict(zip(dates[:-1], dates[1:], strict=True))

    features = model_features[["eval_date", "product_vt_symbol", "role"]].copy()
    features["eval_date"] = _normalise_date(features["eval_date"])
    features["product_vt_symbol"] = features["product_vt_symbol"].astype(str)
    if features.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise FeatureError("duplicate_model_feature_row")
    if not set(features["eval_date"]).issubset(set(dates)):
        raise FeatureError("model_eval_date_outside_calendar")

    anchors = (
        features[features["role"].eq("formal_rank10")]
        .set_index("eval_date")["product_vt_symbol"]
        .to_dict()
    )
    if len(anchors) != features["eval_date"].nunique():
        raise FeatureError("formal_rank10_anchor_count_not_one")
    plan = features[features["role"].eq("challenger")].copy()
    plan["next_eval_date"] = plan["eval_date"].map(next_dates)
    plan = plan[plan["next_eval_date"].notna()].copy()
    plan["formal_replacement_product"] = plan["eval_date"].map(anchors)
    plan["label_values_read"] = False
    return plan[
        [
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "formal_replacement_product",
            "role",
            "label_values_read",
        ]
    ].sort_values(
        ["eval_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_fold_plan(
    model_features: pd.DataFrame,
    label_plan: pd.DataFrame,
    *,
    minimum_train_months: int,
) -> pd.DataFrame:
    if minimum_train_months < 1:
        raise FeatureError("minimum_train_months_must_be_positive")
    _require_columns(model_features, ["eval_date"], "model_features")
    _require_columns(
        label_plan,
        ["eval_date", "next_eval_date", "product_vt_symbol"],
        "label_plan",
    )

    test_dates = _normalise_date(model_features["eval_date"]).drop_duplicates().sort_values()
    labels = label_plan.copy()
    labels["eval_date"] = _normalise_date(labels["eval_date"])
    labels["next_eval_date"] = _normalise_date(labels["next_eval_date"])
    label_months = (
        labels[["eval_date", "next_eval_date"]]
        .drop_duplicates()
        .sort_values("eval_date", kind="mergesort")
    )
    if label_months.duplicated("eval_date").any():
        raise FeatureError("multiple_label_end_dates_for_month")
    effect_dates = set(label_months["eval_date"])

    rows: list[dict[str, object]] = []
    for test_date in test_dates:
        training = label_months[label_months["next_eval_date"].lt(test_date)]
        if len(training) < minimum_train_months:
            continue
        train_eval_dates = set(training["eval_date"])
        train_task_count = int(labels["eval_date"].isin(train_eval_dates).sum())
        effect_evaluable = test_date in effect_dates
        rows.append(
            {
                "test_eval_date": test_date,
                "train_month_count": int(len(training)),
                "train_task_count": train_task_count,
                "minimum_train_eval_date": training["eval_date"].min(),
                "maximum_train_eval_date": training["eval_date"].max(),
                "minimum_train_label_end": training["next_eval_date"].min(),
                "maximum_train_label_end": training["next_eval_date"].max(),
                "effect_evaluable": bool(effect_evaluable),
                "inference_only": bool(not effect_evaluable),
                "future_label_rows_used": 0,
                "sealed_holdout_rows": 0,
            }
        )
    return pd.DataFrame(rows)


def build_feature_bundle(
    coverage: pd.DataFrame,
    monthly: pd.DataFrame,
    mapping: pd.DataFrame,
    bars: pd.DataFrame,
    catalog: pd.DataFrame,
    *,
    config: FeatureConfig = FeatureConfig(),
) -> FeatureBundle:
    action_months = monthly.loc[monthly["action_ready"].astype(bool), ["eval_date"]].copy()
    action_months["eval_date"] = _normalise_date(action_months["eval_date"])
    action_coverage = coverage.copy()
    action_coverage["eval_date"] = _normalise_date(action_coverage["eval_date"])
    action_coverage = action_coverage.merge(action_months, on="eval_date", how="inner")
    selected = action_coverage["eligible"].astype(bool) & (
        action_coverage["is_formal_replacement_product"].astype(bool)
        | action_coverage["is_pool_outside_challenger"].astype(bool)
    )
    action_rows = action_coverage.loc[
        selected, ["eval_date", "product_vt_symbol"]
    ].drop_duplicates()

    history = build_product_return_history(mapping, bars)
    trailing = compute_trailing_features(history, action_rows, config=config)
    curve = compute_curve_features(bars, catalog, action_rows)
    raw = trailing.merge(
        curve,
        on=["eval_date", "product_vt_symbol"],
        how="inner",
        validate="one_to_one",
    )
    if len(raw) != len(action_rows):
        raise FeatureError("raw_feature_row_count_mismatch")
    model = build_pairwise_features(raw, coverage, monthly)
    all_eval_dates = sorted(action_months["eval_date"].unique())
    labels = build_label_plan(model, list(all_eval_dates))
    folds = build_fold_plan(
        model,
        labels,
        minimum_train_months=config.minimum_train_months,
    )

    diagnostics_rows: list[dict[str, object]] = []
    challengers = model[model["role"].eq("challenger")]
    for feature in PAIRWISE_FEATURES:
        monthly_std = challengers.groupby("eval_date")[feature].std(ddof=0)
        diagnostics_rows.append(
            {
                "feature": feature,
                "month_count": int(len(monthly_std)),
                "nonzero_cross_section_months": int(monthly_std.fillna(0).gt(0).sum()),
                "minimum_required_nonzero_months": config.minimum_nonzero_months,
            }
        )
    diagnostics = pd.DataFrame(diagnostics_rows)
    return FeatureBundle(
        raw_features=raw.sort_values(
            ["eval_date", "product_vt_symbol"], kind="mergesort"
        ).reset_index(drop=True),
        model_features=model,
        label_plan=labels,
        fold_plan=folds,
        diagnostics=diagnostics,
    )
