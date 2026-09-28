"""Pure label-free transformations for the full-market daily ranker contract."""

from __future__ import annotations

from math import ceil, sqrt
from typing import Iterable

import numpy as np
import pandas as pd


class ContractError(RuntimeError):
    pass


RAW_PATH_FEATURES = [
    "momentum_21",
    "momentum_63",
    "momentum_126",
    "momentum_252",
    "trend_efficiency_21",
    "trend_efficiency_63",
    "trend_efficiency_126",
    "realized_vol_21",
    "realized_vol_63",
    "downside_vol_63",
    "max_drawdown_63",
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
MODEL_FEATURES = [
    *(f"{feature}_rank" for feature in RAW_FEATURES),
    "volume_ratio_missing",
    "open_interest_ratio_missing",
]
LIQUIDITY_FEATURES = {
    "volume_ratio_20_60": "volume_ratio_missing",
    "open_interest_ratio_20_60": "open_interest_ratio_missing",
}
MINIMUM_VALID_RATIO = 0.90


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ContractError(f"missing_columns:{name}:{','.join(missing)}")


def _normalise_date(series: pd.Series) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce").dt.normalize()
    if result.isna().any():
        raise ContractError("invalid_date")
    return result


def build_contract_bar_table(bars: pd.DataFrame) -> pd.DataFrame:
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
    result = bars.copy()
    if "interval" in result.columns:
        result = result[result["interval"].astype(str).eq("d")].copy()
    result["date"] = _normalise_date(result["datetime"])
    result["contract_vt_symbol"] = (
        result["symbol"].astype(str).str.strip()
        + "."
        + result["exchange"].astype(str).str.strip()
    )
    for column in ("close_price", "volume", "open_interest"):
        result[column] = pd.to_numeric(result[column], errors="coerce").astype(float)
    result = result.sort_values(
        ["contract_vt_symbol", "date"], kind="mergesort"
    ).reset_index(drop=True)
    if result.duplicated(["contract_vt_symbol", "date"]).any():
        raise ContractError("duplicate_contract_bar")
    prior_close = result.groupby("contract_vt_symbol", sort=False)[
        "close_price"
    ].shift(1)
    valid = (
        np.isfinite(result["close_price"])
        & np.isfinite(prior_close)
        & result["close_price"].gt(0)
        & prior_close.gt(0)
    )
    result["same_contract_log_return"] = np.nan
    result.loc[valid, "same_contract_log_return"] = np.log(
        result.loc[valid, "close_price"] / prior_close.loc[valid]
    )
    return result[
        [
            "date",
            "contract_vt_symbol",
            "close_price",
            "volume",
            "open_interest",
            "same_contract_log_return",
        ]
    ]


def build_mapped_product_history(
    mapping: pd.DataFrame,
    contract_bars: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    _require_columns(
        mapping,
        ["date", "continuous_symbol_vt", "main_contract_vt"],
        "mapping",
    )
    _require_columns(
        contract_bars,
        [
            "date",
            "contract_vt_symbol",
            "close_price",
            "volume",
            "open_interest",
            "same_contract_log_return",
        ],
        "contract_bars",
    )
    clean = mapping[
        ["date", "continuous_symbol_vt", "main_contract_vt"]
    ].copy()
    clean["date"] = _normalise_date(clean["date"])
    for column in ("continuous_symbol_vt", "main_contract_vt"):
        clean[column] = clean[column].astype("string").str.strip()
    resolved = (
        clean["continuous_symbol_vt"].notna()
        & clean["continuous_symbol_vt"].ne("")
        & clean["main_contract_vt"].notna()
        & clean["main_contract_vt"].ne("")
    )
    diagnostics = {
        "mapping_rows": int(len(clean)),
        "resolved_mapping_rows": int(resolved.sum()),
        "unresolved_mapping_rows": int((~resolved).sum()),
    }
    clean = clean[resolved].copy()
    clean["continuous_symbol_vt"] = clean["continuous_symbol_vt"].astype(str)
    clean["main_contract_vt"] = clean["main_contract_vt"].astype(str)
    if clean.duplicated(["date", "continuous_symbol_vt"]).any() or clean.duplicated(
        ["date", "main_contract_vt"]
    ).any():
        raise ContractError("duplicate_resolved_mapping")
    history = clean.merge(
        contract_bars,
        how="left",
        left_on=["date", "main_contract_vt"],
        right_on=["date", "contract_vt_symbol"],
        validate="one_to_one",
    ).rename(columns={"continuous_symbol_vt": "product_vt_symbol"})
    history = history[
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "close_price",
            "volume",
            "open_interest",
            "same_contract_log_return",
        ]
    ].sort_values(["product_vt_symbol", "date"], kind="mergesort")
    return history.reset_index(drop=True), diagnostics


def build_base_query_panel(
    history: pd.DataFrame,
    contract_bars: pd.DataFrame,
    catalog: pd.DataFrame,
    metadata: pd.DataFrame,
    *,
    start: pd.Timestamp,
    capital: float,
    margin_ratio: float,
) -> pd.DataFrame:
    if capital <= 0 or not 0 < margin_ratio <= 1:
        raise ContractError("invalid_capital_or_margin_ratio")
    _require_columns(
        history,
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "close_price",
            "same_contract_log_return",
        ],
        "history",
    )
    _require_columns(
        contract_bars,
        ["date", "contract_vt_symbol", "close_price", "volume", "open_interest"],
        "contract_bars",
    )
    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"],
        "catalog",
    )
    _require_columns(
        metadata,
        ["vt_symbol", "price_tick", "volume_multiple"],
        "metadata",
    )
    panel = history.copy()
    panel["date"] = _normalise_date(panel["date"])
    panel["product_vt_symbol"] = panel["product_vt_symbol"].astype(str)
    panel = panel.sort_values(
        ["product_vt_symbol", "date"], kind="mergesort"
    ).reset_index(drop=True)
    if panel.duplicated(["date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_product_history")
    grouped = panel.groupby("product_vt_symbol", sort=False)
    panel["mapping_count_252"] = (
        grouped["main_contract_vt"]
        .rolling(252, min_periods=1)
        .count()
        .reset_index(level=0, drop=True)
    )
    panel["valid_return_count_252"] = (
        grouped["same_contract_log_return"]
        .rolling(252, min_periods=1)
        .count()
        .reset_index(level=0, drop=True)
    )

    bars = contract_bars.copy()
    bars["date"] = _normalise_date(bars["date"])
    clean_catalog = catalog[
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"]
    ].copy()
    if clean_catalog.duplicated("vt_symbol").any():
        raise ContractError("duplicate_catalog_contract")
    curve = bars.merge(
        clean_catalog,
        how="inner",
        left_on="contract_vt_symbol",
        right_on="vt_symbol",
        validate="many_to_one",
    )
    curve["maturity_month_index"] = (
        pd.to_numeric(curve["delivery_year"], errors="coerce") * 12
        + pd.to_numeric(curve["delivery_month"], errors="coerce")
    )
    curve["query_month_index"] = curve["date"].dt.year * 12 + curve["date"].dt.month
    valid_curve = (
        (curve["maturity_month_index"] - curve["query_month_index"]).between(0, 48)
        & pd.to_numeric(curve["close_price"], errors="coerce").gt(0)
        & pd.to_numeric(curve["volume"], errors="coerce").gt(0)
        & pd.to_numeric(curve["open_interest"], errors="coerce").gt(0)
    )
    curve_counts = (
        curve[valid_curve]
        .groupby(["date", "product_vt_symbol"], sort=False)
        .size()
        .rename("valid_curve_contract_count")
        .reset_index()
    )
    panel = panel.merge(
        curve_counts,
        on=["date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
    )
    panel["valid_curve_contract_count"] = panel[
        "valid_curve_contract_count"
    ].fillna(0).astype(int)
    clean_metadata = metadata.rename(
        columns={"vt_symbol": "product_vt_symbol"}
    )[["product_vt_symbol", "price_tick", "volume_multiple"]].copy()
    if clean_metadata.duplicated("product_vt_symbol").any():
        raise ContractError("duplicate_product_metadata")
    panel = panel.merge(
        clean_metadata,
        on="product_vt_symbol",
        how="left",
        validate="many_to_one",
    )
    for column in ("close_price", "price_tick", "volume_multiple"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce").astype(float)
    panel["one_lot_margin"] = (
        panel["close_price"] * panel["volume_multiple"] * margin_ratio
    )
    start_date = pd.Timestamp(start).normalize()
    eligible = (
        panel["date"].ge(start_date)
        & panel["mapping_count_252"].eq(252)
        & panel["valid_return_count_252"].ge(241)
        & panel["close_price"].gt(0)
        & panel["price_tick"].gt(0)
        & panel["volume_multiple"].gt(0)
        & panel["one_lot_margin"].le(capital)
        & panel["valid_curve_contract_count"].ge(2)
        & ~panel["product_vt_symbol"].str.endswith(".CFFEX")
    )
    result = panel[eligible].copy().rename(columns={"date": "query_date"})
    result["maximum_identity_source_date"] = result["query_date"]
    result["future_identity_rows_used"] = 0
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _finite_window(values: pd.Series, window: int) -> np.ndarray:
    tail = pd.to_numeric(values.tail(window), errors="coerce").to_numpy(float)
    valid = np.isfinite(tail)
    required = ceil(window * MINIMUM_VALID_RATIO)
    if len(tail) < window or int(valid.sum()) < required:
        raise ContractError(
            f"return_window_coverage_below_minimum:{window}:{int(valid.sum())}:{required}"
        )
    return tail[valid]


def _positive_window_or_none(values: pd.Series, window: int) -> np.ndarray | None:
    tail = pd.to_numeric(values.tail(window), errors="coerce").to_numpy(float)
    valid = np.isfinite(tail) & (tail > 0)
    required = ceil(window * MINIMUM_VALID_RATIO)
    if len(tail) < window or int(valid.sum()) < required:
        return None
    return tail[valid]


def _zero_origin_max_drawdown(returns: np.ndarray) -> float:
    cumulative = np.cumsum(np.asarray(returns, dtype="float64"))
    equity = np.concatenate(([0.0], cumulative))
    drawdown = equity - np.maximum.accumulate(equity)
    return float(drawdown.min())


def compute_path_features(
    history: pd.DataFrame,
    query_rows: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(
        history,
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "volume",
            "open_interest",
            "same_contract_log_return",
        ],
        "history",
    )
    _require_columns(
        query_rows,
        ["query_date", "product_vt_symbol", "main_contract_vt"],
        "query_rows",
    )
    clean_history = history.copy()
    clean_history["date"] = _normalise_date(clean_history["date"])
    clean_history["product_vt_symbol"] = clean_history[
        "product_vt_symbol"
    ].astype(str)
    clean_history = clean_history.sort_values(
        ["product_vt_symbol", "date"], kind="mergesort"
    )
    if clean_history.duplicated(["date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_product_history")
    grouped = {
        product: group.reset_index(drop=True)
        for product, group in clean_history.groupby(
            "product_vt_symbol", sort=False
        )
    }
    queries = query_rows[
        ["query_date", "product_vt_symbol", "main_contract_vt"]
    ].copy()
    queries["query_date"] = _normalise_date(queries["query_date"])
    queries["product_vt_symbol"] = queries["product_vt_symbol"].astype(str)
    if queries.duplicated(["query_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_query_row")

    rows: list[dict[str, object]] = []
    for query in queries.itertuples(index=False):
        product_history = grouped.get(query.product_vt_symbol)
        if product_history is None:
            raise ContractError(f"missing_product_history:{query.product_vt_symbol}")
        usable = product_history[product_history["date"].le(query.query_date)]
        if usable.empty:
            raise ContractError(f"empty_history_at_query:{query.product_vt_symbol}")
        returns = {
            window: _finite_window(usable["same_contract_log_return"], window)
            for window in (21, 63, 126, 252)
        }
        row: dict[str, object] = {
            "query_date": query.query_date,
            "product_vt_symbol": query.product_vt_symbol,
            "main_contract_vt": query.main_contract_vt,
        }
        for window, values in returns.items():
            row[f"momentum_{window}"] = float(values.sum() * window / len(values))
        for window in (21, 63, 126):
            values = returns[window]
            absolute_sum = float(np.abs(values).sum())
            row[f"trend_efficiency_{window}"] = (
                float(abs(values.sum()) / absolute_sum) if absolute_sum > 0 else 0.0
            )
        for window in (21, 63):
            values = returns[window]
            row[f"realized_vol_{window}"] = float(
                np.std(values, ddof=1) * sqrt(252)
            )
        negative = returns[63][returns[63] < 0]
        row["downside_vol_63"] = (
            float(np.sqrt(np.mean(np.square(negative))) * sqrt(252))
            if len(negative)
            else 0.0
        )
        row["max_drawdown_63"] = _zero_origin_max_drawdown(returns[63])
        for source in ("volume", "open_interest"):
            short = _positive_window_or_none(usable[source], 20)
            long = _positive_window_or_none(usable[source], 60)
            name = f"{source}_ratio_20_60"
            row[name] = (
                float(np.log(short.mean() / long.mean()))
                if short is not None and long is not None
                else np.nan
            )
        row["maximum_path_source_date"] = usable["date"].max()
        row["future_path_rows_used"] = 0
        rows.append(row)
    result = pd.DataFrame(rows)
    non_liquidity = [
        feature for feature in RAW_PATH_FEATURES if feature not in LIQUIDITY_FEATURES
    ]
    if not np.isfinite(result[non_liquidity].to_numpy(float)).all():
        raise ContractError("nonfinite_path_feature")
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def compute_curve_features(
    contract_bars: pd.DataFrame,
    catalog: pd.DataFrame,
    query_rows: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(
        contract_bars,
        ["date", "contract_vt_symbol", "close_price", "volume", "open_interest"],
        "contract_bars",
    )
    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"],
        "catalog",
    )
    _require_columns(query_rows, ["query_date", "product_vt_symbol"], "query_rows")
    bars = contract_bars.copy()
    bars["date"] = _normalise_date(bars["date"])
    for column in ("close_price", "volume", "open_interest"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce").astype(float)
    clean_catalog = catalog[
        ["vt_symbol", "product_vt_symbol", "delivery_year", "delivery_month"]
    ].copy()
    if clean_catalog.duplicated("vt_symbol").any():
        raise ContractError("duplicate_catalog_contract")
    curve = bars.merge(
        clean_catalog,
        how="inner",
        left_on="contract_vt_symbol",
        right_on="vt_symbol",
        validate="many_to_one",
    )
    curve_groups = {
        (date, product): group
        for (date, product), group in curve.groupby(
            ["date", "product_vt_symbol"], sort=False
        )
    }
    queries = query_rows[["query_date", "product_vt_symbol"]].copy()
    queries["query_date"] = _normalise_date(queries["query_date"])
    queries["product_vt_symbol"] = queries["product_vt_symbol"].astype(str)
    if queries.duplicated().any():
        raise ContractError("duplicate_query_row")
    rows: list[dict[str, object]] = []
    for query in queries.itertuples(index=False):
        selected = curve_groups.get((query.query_date, query.product_vt_symbol))
        if selected is None:
            raise ContractError(
                f"missing_curve:{query.query_date.date()}:{query.product_vt_symbol}"
            )
        selected = selected.copy()
        selected["maturity_month_index"] = (
            pd.to_numeric(selected["delivery_year"], errors="coerce") * 12
            + pd.to_numeric(selected["delivery_month"], errors="coerce")
        )
        query_month = query.query_date.year * 12 + query.query_date.month
        selected["months_to_delivery"] = (
            selected["maturity_month_index"] - query_month
        )
        valid = (
            selected["months_to_delivery"].between(0, 48)
            & selected["close_price"].gt(0)
            & selected["volume"].gt(0)
            & selected["open_interest"].gt(0)
            & np.isfinite(selected["close_price"])
            & np.isfinite(selected["volume"])
            & np.isfinite(selected["open_interest"])
        )
        selected = selected[valid].sort_values(
            ["maturity_month_index", "contract_vt_symbol"], kind="mergesort"
        )
        if len(selected) < 2:
            raise ContractError(
                f"curve_contract_count_below_minimum:{query.query_date.date()}:{query.product_vt_symbol}"
            )
        if selected.duplicated("maturity_month_index").any():
            raise ContractError("duplicate_curve_maturity")
        maturity = selected["maturity_month_index"].to_numpy(float)
        log_price = np.log(selected["close_price"].to_numpy(float))
        maturity_gap = maturity[1] - maturity[0]
        volume = selected["volume"].to_numpy(float)
        open_interest = selected["open_interest"].to_numpy(float)
        rows.append(
            {
                "query_date": query.query_date,
                "product_vt_symbol": query.product_vt_symbol,
                "front_next_basis_annualized": float(
                    (log_price[0] - log_price[1]) * 12.0 / maturity_gap
                ),
                "full_curve_backwardation_slope": float(
                    -np.polyfit(maturity, log_price, 1)[0] * 12.0
                ),
                "volume_hhi": float(np.square(volume / volume.sum()).sum()),
                "open_interest_hhi": float(
                    np.square(open_interest / open_interest.sum()).sum()
                ),
                "maximum_curve_source_date": selected["date"].max(),
                "future_curve_rows_used": 0,
            }
        )
    result = pd.DataFrame(rows)
    if not np.isfinite(result[RAW_CURVE_FEATURES].to_numpy(float)).all():
        raise ContractError("nonfinite_curve_feature")
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def compute_raw_features(
    base_panel: pd.DataFrame,
    history: pd.DataFrame,
    contract_bars: pd.DataFrame,
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    path = compute_path_features(history, base_panel)
    curve = compute_curve_features(contract_bars, catalog, base_panel)
    result = path.merge(
        curve,
        on=["query_date", "product_vt_symbol"],
        how="inner",
        validate="one_to_one",
    )
    if len(result) != len(base_panel):
        raise ContractError("raw_feature_row_count_changed")
    return result


def build_ranked_model_features(raw_features: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        raw_features,
        ["query_date", "product_vt_symbol", *RAW_FEATURES],
        "raw_features",
    )
    result = raw_features.copy()
    result["query_date"] = _normalise_date(result["query_date"])
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    if result.duplicated(["query_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_raw_feature_row")
    non_liquidity = [
        feature for feature in RAW_FEATURES if feature not in LIQUIDITY_FEATURES
    ]
    if not np.isfinite(result[non_liquidity].to_numpy(float)).all():
        raise ContractError("unexpected_nonfinite_raw_feature")
    for feature, missing_flag in LIQUIDITY_FEATURES.items():
        values = pd.to_numeric(result[feature], errors="coerce").astype(float)
        invalid = ~np.isfinite(values)
        result[missing_flag] = invalid.astype(int)
        result[feature] = values.where(~invalid, np.nan)
    for feature in RAW_FEATURES:
        ranked = result.groupby("query_date", sort=False)[feature].rank(
            method="average", pct=True
        )
        if feature in LIQUIDITY_FEATURES:
            ranked = ranked.fillna(0.5)
        result[f"{feature}_rank"] = ranked
    if not np.isfinite(result[MODEL_FEATURES].to_numpy(float)).all():
        raise ContractError("nonfinite_model_feature")
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_label_plan(
    base_panel: pd.DataFrame,
    bar_presence: pd.DataFrame,
    catalog: pd.DataFrame,
    global_dates: Iterable[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Plan fixed-contract label windows without exposing any price values."""
    _require_columns(
        base_panel,
        ["query_date", "product_vt_symbol", "main_contract_vt"],
        "base_panel",
    )
    if set(bar_presence.columns) != {"date", "contract_vt_symbol"}:
        raise ContractError("bar_presence_columns_invalid")
    _require_columns(catalog, ["vt_symbol", "expire_date"], "catalog")

    base = base_panel[
        ["query_date", "product_vt_symbol", "main_contract_vt"]
    ].copy()
    base["query_date"] = _normalise_date(base["query_date"])
    for column in ("product_vt_symbol", "main_contract_vt"):
        base[column] = base[column].astype(str)
    if base.duplicated(["query_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_base_query_row")

    presence = bar_presence.copy()
    presence["date"] = _normalise_date(presence["date"])
    presence["contract_vt_symbol"] = presence["contract_vt_symbol"].astype(str)
    if presence.duplicated(["date", "contract_vt_symbol"]).any():
        raise ContractError("duplicate_bar_presence")
    presence_keys = set(
        presence[["date", "contract_vt_symbol"]].itertuples(index=False, name=None)
    )

    clean_catalog = catalog[["vt_symbol", "expire_date"]].copy()
    clean_catalog["vt_symbol"] = clean_catalog["vt_symbol"].astype(str)
    clean_catalog["expire_date"] = _normalise_date(clean_catalog["expire_date"])
    if clean_catalog.duplicated("vt_symbol").any():
        raise ContractError("duplicate_catalog_contract")
    expiry_by_contract = clean_catalog.set_index("vt_symbol")["expire_date"].to_dict()

    calendar = pd.DatetimeIndex(pd.to_datetime(list(global_dates))).normalize()
    calendar = calendar[~calendar.isna()].unique().sort_values()
    if calendar.empty:
        raise ContractError("empty_global_calendar")
    calendar_positions = {date: index for index, date in enumerate(calendar)}

    accepted_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    for row in base.itertuples(index=False):
        position = calendar_positions.get(row.query_date)
        entry_date = (
            calendar[position + 1]
            if position is not None and position + 1 < len(calendar)
            else pd.NaT
        )
        label_end = (
            calendar[position + 21]
            if position is not None and position + 21 < len(calendar)
            else pd.NaT
        )
        identity = {
            "query_date": row.query_date,
            "product_vt_symbol": row.product_vt_symbol,
            "main_contract_vt": row.main_contract_vt,
            "entry_date": entry_date,
            "label_end": label_end,
        }
        if position is None:
            rejection_reason = "query_date_outside_calendar"
        elif pd.isna(entry_date) or pd.isna(label_end):
            rejection_reason = "exit_date_outside_cutoff"
        elif (entry_date, row.main_contract_vt) not in presence_keys:
            rejection_reason = "entry_bar_missing"
        elif (label_end, row.main_contract_vt) not in presence_keys:
            rejection_reason = "exit_bar_missing"
        elif row.main_contract_vt not in expiry_by_contract:
            rejection_reason = "catalog_contract_missing"
        elif expiry_by_contract[row.main_contract_vt] < label_end:
            rejection_reason = "contract_expiry_before_exit"
        else:
            accepted_rows.append(
                {
                    **identity,
                    "label_value_read": False,
                    "future_value_rows_used": 0,
                }
            )
            continue
        rejected_rows.append({**identity, "rejection_reason": rejection_reason})

    accepted_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "label_value_read",
        "future_value_rows_used",
    ]
    rejected_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "rejection_reason",
    ]
    accepted = pd.DataFrame(accepted_rows, columns=accepted_columns)
    rejected = pd.DataFrame(rejected_rows, columns=rejected_columns)
    sort_columns = ["query_date", "product_vt_symbol"]
    return (
        accepted.sort_values(sort_columns, kind="mergesort").reset_index(drop=True),
        rejected.sort_values(sort_columns, kind="mergesort").reset_index(drop=True),
    )


def build_formal_scoring_plan(
    base_panel: pd.DataFrame,
    coverage: pd.DataFrame,
    monthly_status: pd.DataFrame,
) -> pd.DataFrame:
    """Bind formal rank-10 anchors and outside-pool challengers to query rows."""
    _require_columns(
        base_panel,
        ["query_date", "product_vt_symbol"],
        "base_panel",
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
    _require_columns(monthly_status, ["eval_date", "action_ready"], "monthly_status")

    base = base_panel[["query_date", "product_vt_symbol"]].copy()
    base["query_date"] = _normalise_date(base["query_date"])
    base["product_vt_symbol"] = base["product_vt_symbol"].astype(str)
    if base.duplicated().any():
        raise ContractError("duplicate_base_query_row")

    clean_coverage = coverage.copy()
    clean_coverage["eval_date"] = _normalise_date(clean_coverage["eval_date"])
    clean_coverage["product_vt_symbol"] = clean_coverage[
        "product_vt_symbol"
    ].astype(str)
    if clean_coverage.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_coverage_row")
    formal = clean_coverage["is_formal_replacement_product"].fillna(False).astype(bool)
    challenger = clean_coverage["is_pool_outside_challenger"].fillna(False).astype(bool)
    if (formal & challenger).any():
        raise ContractError("formal_role_overlap")

    monthly = monthly_status[["eval_date", "action_ready"]].copy()
    monthly["eval_date"] = _normalise_date(monthly["eval_date"])
    if monthly.duplicated("eval_date").any():
        raise ContractError("duplicate_monthly_status")
    ready_dates = set(monthly.loc[monthly["action_ready"].astype(bool), "eval_date"])

    selected = clean_coverage[
        clean_coverage["eligible"].fillna(False).astype(bool)
        & clean_coverage["eval_date"].isin(ready_dates)
        & (formal | challenger)
    ].copy()
    selected["role"] = np.where(
        selected["is_formal_replacement_product"].astype(bool),
        "formal_rank10",
        "challenger",
    )
    selected = selected.merge(
        base,
        how="inner",
        left_on=["eval_date", "product_vt_symbol"],
        right_on=["query_date", "product_vt_symbol"],
        validate="one_to_one",
    )
    if selected.empty:
        raise ContractError("empty_formal_scoring_plan")
    formal_count = selected["role"].eq("formal_rank10").groupby(
        selected["eval_date"]
    ).sum()
    if not formal_count.eq(1).all():
        raise ContractError("formal_anchor_count_invalid")
    selected["formal_score_value_read"] = False
    selected["_role_order"] = selected["role"].map(
        {"formal_rank10": 0, "challenger": 1}
    )
    result = selected.rename(columns={"eval_date": "test_eval_date"})
    result = result.sort_values(
        ["test_eval_date", "_role_order", "product_vt_symbol"], kind="mergesort"
    )
    return result[
        [
            "test_eval_date",
            "product_vt_symbol",
            "role",
            "formal_score_value_read",
        ]
    ].reset_index(drop=True)


def build_purged_fold_plan(
    label_plan: pd.DataFrame,
    scoring_plan: pd.DataFrame,
    *,
    minimum_train_qids: int = 252,
) -> pd.DataFrame:
    """Plan expanding folds whose training labels have matured before test time."""
    if minimum_train_qids <= 0:
        raise ContractError("invalid_minimum_train_qids")
    _require_columns(
        label_plan,
        ["query_date", "product_vt_symbol", "label_end"],
        "label_plan",
    )
    _require_columns(
        scoring_plan,
        ["test_eval_date", "product_vt_symbol", "role"],
        "scoring_plan",
    )
    labels = label_plan[["query_date", "product_vt_symbol", "label_end"]].copy()
    labels["query_date"] = _normalise_date(labels["query_date"])
    labels["label_end"] = _normalise_date(labels["label_end"])
    labels["product_vt_symbol"] = labels["product_vt_symbol"].astype(str)
    if labels.duplicated(["query_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_label_plan_row")
    qid_label_ends = labels.groupby("query_date", sort=True)["label_end"].nunique()
    if not qid_label_ends.eq(1).all():
        raise ContractError("qid_label_end_not_unique")
    qids = (
        labels.groupby("query_date", sort=True)["label_end"]
        .first()
        .rename("label_end")
        .reset_index()
    )

    scoring = scoring_plan[["test_eval_date", "product_vt_symbol", "role"]].copy()
    scoring["test_eval_date"] = _normalise_date(scoring["test_eval_date"])
    scoring["product_vt_symbol"] = scoring["product_vt_symbol"].astype(str)
    if scoring.duplicated(["test_eval_date", "product_vt_symbol"]).any():
        raise ContractError("duplicate_scoring_plan_row")
    if not set(scoring["role"]).issubset({"formal_rank10", "challenger"}):
        raise ContractError("invalid_scoring_role")

    label_membership = set(
        labels[["query_date", "product_vt_symbol"]].itertuples(index=False, name=None)
    )
    rows: list[dict[str, object]] = []
    for test_date, group in scoring.groupby("test_eval_date", sort=True):
        mature = qids[qids["label_end"].lt(test_date)]
        if len(mature) < minimum_train_qids:
            continue
        formal_products = group.loc[
            group["role"].eq("formal_rank10"), "product_vt_symbol"
        ].tolist()
        challenger_products = group.loc[
            group["role"].eq("challenger"), "product_vt_symbol"
        ].tolist()
        formal_present = len(formal_products) == 1 and (
            test_date,
            formal_products[0],
        ) in label_membership
        challenger_present = sum(
            (test_date, product) in label_membership
            for product in challenger_products
        )
        effect_evaluable = formal_present and challenger_present >= 10
        rows.append(
            {
                "test_eval_date": test_date,
                "train_qid_count": int(len(mature)),
                "minimum_train_query_date": mature["query_date"].min(),
                "maximum_train_query_date": mature["query_date"].max(),
                "maximum_train_label_end": mature["label_end"].max(),
                "effect_evaluable": effect_evaluable,
                "inference_only": not effect_evaluable,
                "future_label_rows_used": 0,
                "sealed_holdout_rows": 0,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        raise ContractError("no_fold_meets_minimum_train_qids")
    for column in ("effect_evaluable", "inference_only"):
        result[column] = result[column].astype(object)
    return result.reset_index(drop=True)
