"""Pure PIT coverage logic for the full-market one-slot research line."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage001_full_market_coverage_pass_allow_feature_preregistration_only"
FAIL_DECISION = "stage001_full_market_coverage_fail_close_shape_no_labels"


class CoverageError(RuntimeError):
    """Raised when the frozen coverage contract cannot be evaluated exactly."""


@dataclass(frozen=True)
class CoverageConfig:
    eval_start: pd.Timestamp
    eval_end: pd.Timestamp
    expected_months: int
    expected_ranks_per_month: int
    expected_static_products: int
    replacement_rank: int
    minimum_mapping_days: int
    minimum_valid_close_days: int
    activity_window_days: int
    minimum_activity_ratio: float
    minimum_curve_contracts: int
    minimum_total_eligible: int
    minimum_action_months: int
    minimum_challengers: int
    capital: float
    conservative_margin_ratio: float
    allowed_exchanges: tuple[str, ...] = ("CZCE", "DCE", "GFEX", "INE", "SHFE")
    fixed_satellite: str = "fu.SHFE"

    def __post_init__(self) -> None:
        if pd.Timestamp(self.eval_start) > pd.Timestamp(self.eval_end):
            raise CoverageError("eval_range_invalid")
        positive_ints = (
            self.expected_months,
            self.expected_ranks_per_month,
            self.expected_static_products,
            self.replacement_rank,
            self.minimum_mapping_days,
            self.minimum_valid_close_days,
            self.activity_window_days,
            self.minimum_curve_contracts,
            self.minimum_total_eligible,
            self.minimum_action_months,
            self.minimum_challengers,
        )
        if any(int(value) <= 0 for value in positive_ints):
            raise CoverageError("positive_integer_config_invalid")
        if self.replacement_rank > self.expected_ranks_per_month:
            raise CoverageError("replacement_rank_out_of_bounds")
        if self.minimum_valid_close_days > self.minimum_mapping_days:
            raise CoverageError("valid_close_gate_exceeds_mapping_window")
        if self.activity_window_days > self.minimum_mapping_days:
            raise CoverageError("activity_window_exceeds_mapping_window")
        if not 0.0 < float(self.minimum_activity_ratio) <= 1.0:
            raise CoverageError("activity_ratio_invalid")
        if float(self.capital) <= 0.0 or not 0.0 < float(self.conservative_margin_ratio) <= 1.0:
            raise CoverageError("capital_or_margin_invalid")


@dataclass(frozen=True)
class CoverageResult:
    coverage: pd.DataFrame
    monthly: pd.DataFrame
    rejected: pd.DataFrame
    diagnostics: dict[str, Any]


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    if missing := sorted(required - set(frame.columns)):
        raise CoverageError(f"{name}_columns_missing:{','.join(missing)}")


def _normalise_formal_ranking(
    ranking: pd.DataFrame, config: CoverageConfig
) -> tuple[pd.DataFrame, set[str]]:
    required = {"eval_date", "product_vt_symbol", "score_rank", "score_type"}
    _require_columns(ranking, required, "formal")
    frame = ranking.loc[:, sorted(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame = frame[
        frame["eval_date"].between(
            pd.Timestamp(config.eval_start).normalize(),
            pd.Timestamp(config.eval_end).normalize(),
        )
    ].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str).str.strip()
    frame["score_type"] = frame["score_type"].astype(str).str.strip()
    frame["score_rank"] = pd.to_numeric(frame["score_rank"], errors="raise").astype(int)
    if frame.empty:
        raise CoverageError("formal_period_empty")
    if frame["product_vt_symbol"].eq("").any() or frame["score_type"].eq("").any():
        raise CoverageError("formal_identity_empty")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise CoverageError("formal_eval_product_duplicate")
    if frame.duplicated(["eval_date", "score_rank"]).any():
        raise CoverageError("formal_eval_rank_duplicate")

    eval_dates = pd.DatetimeIndex(sorted(frame["eval_date"].unique()))
    if len(eval_dates) != int(config.expected_months):
        raise CoverageError("formal_month_count_mismatch")
    expected_ranks = list(range(1, int(config.expected_ranks_per_month) + 1))
    for _, month in frame.groupby("eval_date", sort=True):
        if sorted(month["score_rank"].tolist()) != expected_ranks:
            raise CoverageError("formal_rank_not_contiguous")
    static_products = set(frame["product_vt_symbol"].unique())
    if len(static_products) != int(config.expected_static_products):
        raise CoverageError("formal_static_product_count_mismatch")
    return (
        frame.sort_values(["eval_date", "score_rank"], kind="mergesort").reset_index(drop=True),
        static_products,
    )


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    product, separator, exchange = str(vt_symbol).partition(".")
    if not separator or not product or not exchange:
        raise CoverageError(f"vt_symbol_invalid:{vt_symbol}")
    return product, exchange.upper()


def _normalise_mapping(
    mapping: pd.DataFrame, max_eval_date: pd.Timestamp
) -> tuple[pd.DataFrame, int]:
    required = {"date", "continuous_symbol_vt", "main_contract_vt", "exchange"}
    _require_columns(mapping, required, "mapping")
    frame = mapping.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["continuous_symbol_vt"] = frame["continuous_symbol_vt"].astype(str).str.strip()
    frame["main_contract_vt"] = frame["main_contract_vt"].fillna("").astype(str).str.strip()
    frame["exchange"] = frame["exchange"].astype(str).str.strip().str.upper()
    future_rows_seen = int(frame["date"].gt(max_eval_date).sum())
    frame = frame[frame["date"].le(max_eval_date)].copy()
    if frame.duplicated(["date", "continuous_symbol_vt"]).any():
        raise CoverageError("mapping_eval_product_duplicate")
    for item in frame.itertuples(index=False):
        _, suffix_exchange = _split_vt_symbol(item.continuous_symbol_vt)
        if suffix_exchange != item.exchange:
            raise CoverageError("mapping_exchange_suffix_mismatch")
    return frame, future_rows_seen


def _normalise_bars(
    bars: pd.DataFrame, max_eval_date: pd.Timestamp
) -> tuple[pd.DataFrame, int]:
    required = {
        "datetime",
        "symbol",
        "exchange",
        "interval",
        "close_price",
        "volume",
        "open_interest",
    }
    _require_columns(bars, required, "bars")
    frame = bars.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame.pop("datetime"), errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["exchange"] = frame["exchange"].astype(str).str.strip().str.upper()
    frame["interval"] = frame["interval"].astype(str).str.strip()
    frame = frame[frame["interval"].eq("d")].copy()
    future_rows_seen = int(frame["date"].gt(max_eval_date).sum())
    frame = frame[frame["date"].le(max_eval_date)].copy()
    for column in ("close_price", "volume", "open_interest"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["contract_vt_symbol"] = frame["symbol"] + "." + frame["exchange"]
    if frame.duplicated(["date", "contract_vt_symbol"]).any():
        raise CoverageError("daily_contract_duplicate")
    return frame, future_rows_seen


def _normalise_metadata(metadata: pd.DataFrame) -> pd.DataFrame:
    required = {"vt_symbol", "symbol_kind", "price_tick", "volume_multiple"}
    _require_columns(metadata, required, "metadata")
    frame = metadata.loc[:, sorted(required)].copy()
    frame["vt_symbol"] = frame["vt_symbol"].astype(str).str.strip()
    frame["symbol_kind"] = frame["symbol_kind"].astype(str).str.strip()
    frame = frame[frame["symbol_kind"].eq("product_cont")].copy()
    frame["price_tick"] = pd.to_numeric(frame["price_tick"], errors="coerce")
    frame["volume_multiple"] = pd.to_numeric(frame["volume_multiple"], errors="coerce")
    if frame.duplicated("vt_symbol").any():
        raise CoverageError("metadata_product_duplicate")
    return frame.set_index("vt_symbol", drop=False)


def _month_serial(value: pd.Timestamp) -> int:
    return int(value.year * 12 + value.month)


def infer_delivery_month(symbol: Any, exchange: Any, eval_date: Any) -> pd.Timestamp | pd.NaT:
    text = str(symbol).strip()
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", text)
    if match is None:
        return pd.NaT
    digits = match.group(2)
    if len(set(digits)) == 1 and digits[0] in {"8", "9"}:
        return pd.NaT
    month = int(digits[-2:])
    if not 1 <= month <= 12:
        return pd.NaT

    eval_ts = pd.Timestamp(eval_date).normalize()
    eval_month = pd.Timestamp(eval_ts.year, eval_ts.month, 1)
    if len(digits) == 4:
        maturity = pd.Timestamp(2000 + int(digits[:2]), month, 1)
        distance = _month_serial(maturity) - _month_serial(eval_month)
        return maturity if 0 <= distance <= 48 else pd.NaT
    if str(exchange).strip().upper() != "CZCE":
        return pd.NaT
    year_digit = int(digits[0])
    candidates = [pd.Timestamp(year, month, 1) for year in range(2000 + year_digit, 2050, 10)]
    plausible = [
        value
        for value in candidates
        if 0 <= _month_serial(value) - _month_serial(eval_month) <= 48
    ]
    return plausible[0] if len(plausible) == 1 else pd.NaT


def _attach_product_to_bars(bars: pd.DataFrame, products: set[str]) -> pd.DataFrame:
    lookup: dict[tuple[str, str], str] = {}
    for vt_symbol in sorted(products):
        product, exchange = _split_vt_symbol(vt_symbol)
        key = (product.lower(), exchange)
        if key in lookup and lookup[key] != vt_symbol:
            raise CoverageError("product_lookup_ambiguous")
        lookup[key] = vt_symbol

    product_values: list[str | None] = []
    maturities: list[pd.Timestamp | pd.NaT] = []
    for item in bars.itertuples(index=False):
        match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", str(item.symbol))
        product = lookup.get((match.group(1).lower(), item.exchange)) if match else None
        product_values.append(product)
        maturities.append(
            infer_delivery_month(item.symbol, item.exchange, item.date)
            if product is not None
            else pd.NaT
        )
    frame = bars.copy()
    frame["product_vt_symbol"] = product_values
    frame["contract_maturity"] = maturities
    return frame


def _valid_number(value: Any) -> bool:
    return bool(pd.notna(value) and np.isfinite(float(value)) and float(value) > 0.0)


def build_coverage(
    ranking: pd.DataFrame,
    mapping: pd.DataFrame,
    bars: pd.DataFrame,
    metadata: pd.DataFrame,
    config: CoverageConfig,
) -> CoverageResult:
    formal, static_products = _normalise_formal_ranking(ranking, config)
    eval_dates = pd.DatetimeIndex(sorted(formal["eval_date"].unique()))
    max_eval_date = pd.Timestamp(eval_dates.max()).normalize()
    mapped, future_mapping_seen = _normalise_mapping(mapping, max_eval_date)
    daily, future_bar_seen = _normalise_bars(bars, max_eval_date)
    product_metadata = _normalise_metadata(metadata)
    all_products = set(mapped["continuous_symbol_vt"].unique()) | static_products
    daily = _attach_product_to_bars(daily, all_products)

    bar_lookup = daily.set_index(["date", "contract_vt_symbol"], drop=False)
    mapping_by_product = {
        str(product): group.sort_values("date", kind="mergesort").reset_index(drop=True)
        for product, group in mapped.groupby("continuous_symbol_vt", sort=False)
    }
    exact_mapping_by_date = {
        pd.Timestamp(date): group[group["main_contract_vt"].ne("")]
        .sort_values("continuous_symbol_vt", kind="mergesort")
        .reset_index(drop=True)
        for date, group in mapped.groupby("date", sort=False)
    }
    curve_by_eval_product = {
        (pd.Timestamp(date), str(product)): group
        for (date, product), group in daily[
            daily["date"].isin(eval_dates) & daily["product_vt_symbol"].notna()
        ].groupby(["date", "product_vt_symbol"], sort=False)
    }
    replacement_by_date = (
        formal[formal["score_rank"].eq(config.replacement_rank)]
        .set_index("eval_date")["product_vt_symbol"]
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    for eval_date in eval_dates:
        exact_mapping = exact_mapping_by_date.get(pd.Timestamp(eval_date), mapped.iloc[0:0])
        for exact in exact_mapping.itertuples(index=False):
            product = str(exact.continuous_symbol_vt)
            _, exchange = _split_vt_symbol(product)
            product_mapping = mapping_by_product[product]
            history = product_mapping[
                product_mapping["date"].le(eval_date)
                & product_mapping["main_contract_vt"].ne("")
            ]
            mapping_days = int(len(history))
            lookback = history.tail(config.minimum_mapping_days)

            stitched_rows: list[dict[str, Any]] = []
            for mapping_row in lookback.itertuples(index=False):
                key = (pd.Timestamp(mapping_row.date), str(mapping_row.main_contract_vt))
                if key not in bar_lookup.index:
                    stitched_rows.append(
                        {
                            "date": pd.Timestamp(mapping_row.date),
                            "close_price": np.nan,
                            "volume": np.nan,
                            "open_interest": np.nan,
                        }
                    )
                    continue
                bar = bar_lookup.loc[key]
                if isinstance(bar, pd.DataFrame):
                    raise CoverageError("daily_contract_lookup_not_unique")
                stitched_rows.append(
                    {
                        "date": pd.Timestamp(mapping_row.date),
                        "close_price": bar["close_price"],
                        "volume": bar["volume"],
                        "open_interest": bar["open_interest"],
                    }
                )
            stitched = pd.DataFrame(stitched_rows)
            valid_close_days = int(stitched.get("close_price", pd.Series(dtype=float)).map(_valid_number).sum())
            if stitched.empty:
                activity_ratio = 0.0
                latest_close = np.nan
                exact_close_valid = False
            else:
                activity = stitched.tail(config.activity_window_days)
                activity_valid = (
                    activity["close_price"].map(_valid_number)
                    & activity["volume"].map(_valid_number)
                    & activity["open_interest"].map(_valid_number)
                )
                activity_ratio = float(activity_valid.mean()) if len(activity) else 0.0
                latest = stitched[stitched["date"].eq(eval_date)]
                latest_close = float(latest.iloc[-1]["close_price"]) if len(latest) else np.nan
                exact_close_valid = _valid_number(latest_close)

            curve_source = curve_by_eval_product.get(
                (pd.Timestamp(eval_date), product), daily.iloc[0:0]
            )
            curve = curve_source[
                curve_source["contract_maturity"].notna()
                & curve_source["close_price"].map(_valid_number)
                & curve_source["volume"].map(_valid_number)
                & curve_source["open_interest"].map(_valid_number)
            ].sort_values(["contract_maturity", "contract_vt_symbol"], kind="mergesort")
            curve = curve.drop_duplicates("contract_maturity", keep="first")
            curve_contract_count = int(len(curve))
            curve_strictly_increasing = bool(
                curve_contract_count >= config.minimum_curve_contracts
                and pd.DatetimeIndex(curve["contract_maturity"]).is_monotonic_increasing
                and not curve["contract_maturity"].duplicated().any()
            )

            metadata_ready = product in product_metadata.index
            price_tick = (
                float(product_metadata.loc[product, "price_tick"])
                if metadata_ready and _valid_number(product_metadata.loc[product, "price_tick"])
                else np.nan
            )
            volume_multiple = (
                float(product_metadata.loc[product, "volume_multiple"])
                if metadata_ready and _valid_number(product_metadata.loc[product, "volume_multiple"])
                else np.nan
            )
            metadata_ready = bool(_valid_number(price_tick) and _valid_number(volume_multiple))
            one_lot_margin = (
                float(latest_close * volume_multiple * config.conservative_margin_ratio)
                if exact_close_valid and metadata_ready
                else np.nan
            )

            if exchange not in set(config.allowed_exchanges):
                status = "exchange_not_allowed"
            elif mapping_days < config.minimum_mapping_days:
                status = "mapping_days_below_minimum"
            elif valid_close_days < config.minimum_valid_close_days:
                status = "valid_close_days_below_minimum"
            elif not exact_close_valid:
                status = "eval_date_close_missing"
            elif activity_ratio < config.minimum_activity_ratio:
                status = "activity_ratio_below_minimum"
            elif curve_contract_count < config.minimum_curve_contracts:
                status = "curve_contract_count_below_minimum"
            elif not curve_strictly_increasing:
                status = "curve_maturity_order_invalid"
            elif not metadata_ready:
                status = "metadata_invalid"
            elif one_lot_margin > config.capital:
                status = "one_lot_margin_above_capital"
            else:
                status = "ok"
            eligible = status == "ok"
            is_static = product in static_products
            is_challenger = bool(
                eligible and not is_static and product != config.fixed_satellite
            )
            row = {
                "eval_date": pd.Timestamp(eval_date),
                "product_vt_symbol": product,
                "exchange": exchange,
                "main_contract_vt": str(exact.main_contract_vt),
                "mapping_days": mapping_days,
                "valid_close_days": valid_close_days,
                "activity_ratio": activity_ratio,
                "curve_contract_count": curve_contract_count,
                "curve_strictly_increasing": curve_strictly_increasing,
                "metadata_ready": metadata_ready,
                "price_tick": price_tick,
                "volume_multiple": volume_multiple,
                "latest_close": latest_close,
                "one_lot_margin": one_lot_margin,
                "is_static_product": is_static,
                "is_formal_replacement_product": product == replacement_by_date[pd.Timestamp(eval_date)],
                "eligible": eligible,
                "is_pool_outside_challenger": is_challenger,
                "status": status,
                "fallback_used": False,
                "future_mapping_rows_used": 0,
                "future_bar_rows_used": 0,
                "label_rows_read": 0,
            }
            rows.append(row)
            if not eligible:
                rejected_rows.append(
                    {
                        "eval_date": pd.Timestamp(eval_date),
                        "product_vt_symbol": product,
                        "status": status,
                    }
                )

    coverage = pd.DataFrame(rows).sort_values(
        ["eval_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    if coverage.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise CoverageError("coverage_eval_product_duplicate")

    monthly_rows: list[dict[str, Any]] = []
    for eval_date in eval_dates:
        month = coverage[coverage["eval_date"].eq(eval_date)]
        replacement_product = str(replacement_by_date[pd.Timestamp(eval_date)])
        replacement = month[month["product_vt_symbol"].eq(replacement_product)]
        replacement_eligible = bool(len(replacement) == 1 and replacement.iloc[0]["eligible"])
        challenger_count = int(month["is_pool_outside_challenger"].sum())
        monthly_rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "formal_replacement_product": replacement_product,
                "formal_replacement_eligible": replacement_eligible,
                "eligible_product_count": int(month["eligible"].sum()),
                "challenger_count": challenger_count,
                "action_ready": bool(
                    replacement_eligible and challenger_count >= config.minimum_challengers
                ),
            }
        )
    monthly = pd.DataFrame(monthly_rows)
    rejected = pd.DataFrame(
        rejected_rows, columns=["eval_date", "product_vt_symbol", "status"]
    ).sort_values(["eval_date", "product_vt_symbol"], kind="mergesort").reset_index(drop=True)
    diagnostics = {
        "future_mapping_rows_seen_in_source": future_mapping_seen,
        "future_bar_rows_seen_in_source": future_bar_seen,
        "future_mapping_rows_used": 0,
        "future_bar_rows_used": 0,
        "fallback_rows": int(coverage["fallback_used"].sum()),
        "label_rows_read": int(coverage["label_rows_read"].sum()),
        "static_products": sorted(static_products),
        "eval_dates": [pd.Timestamp(value).date().isoformat() for value in eval_dates],
    }
    return CoverageResult(
        coverage=coverage,
        monthly=monthly,
        rejected=rejected,
        diagnostics=diagnostics,
    )


def assess_coverage(result: CoverageResult, config: CoverageConfig) -> dict[str, Any]:
    monthly = result.monthly
    baseline_eligible = monthly["formal_replacement_eligible"].astype(bool)
    challenger_gate = bool(
        monthly.loc[baseline_eligible, "challenger_count"].ge(config.minimum_challengers).all()
    )
    gates = {
        "monthly_row_count_exact": len(monthly) == config.expected_months,
        "eligible_breadth_each_month": bool(
            monthly["eligible_product_count"].ge(config.minimum_total_eligible).all()
        ),
        "formal_replacement_eligible_months": int(baseline_eligible.sum())
        >= config.minimum_action_months,
        "challenger_breadth_on_each_eligible_baseline_month": challenger_gate,
        "cxffex_eligible_rows_zero": int(
            (
                result.coverage["eligible"].astype(bool)
                & result.coverage["exchange"].eq("CFFEX")
            ).sum()
        )
        == 0,
        "coverage_duplicates_zero": not result.coverage.duplicated(
            ["eval_date", "product_vt_symbol"]
        ).any(),
        "future_mapping_rows_used_zero": result.diagnostics["future_mapping_rows_used"] == 0,
        "future_bar_rows_used_zero": result.diagnostics["future_bar_rows_used"] == 0,
        "fallback_rows_zero": result.diagnostics["fallback_rows"] == 0,
        "label_rows_read_zero": result.diagnostics["label_rows_read"] == 0,
    }
    passed = bool(all(gates.values()))
    return {
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": passed,
        "gates": gates,
        "eval_months": int(len(monthly)),
        "coverage_rows": int(len(result.coverage)),
        "eligible_rows": int(result.coverage["eligible"].sum()),
        "challenger_rows": int(result.coverage["is_pool_outside_challenger"].sum()),
        "minimum_eligible_products": int(monthly["eligible_product_count"].min()),
        "median_eligible_products": float(monthly["eligible_product_count"].median()),
        "maximum_eligible_products": int(monthly["eligible_product_count"].max()),
        "formal_replacement_eligible_months": int(baseline_eligible.sum()),
        "minimum_challengers_on_eligible_baseline_month": int(
            monthly.loc[baseline_eligible, "challenger_count"].min()
        )
        if baseline_eligible.any()
        else 0,
        "action_ready_months": int(monthly["action_ready"].sum()),
        "rejected_rows": int(len(result.rejected)),
        "rejection_counts": {
            str(key): int(value)
            for key, value in result.rejected["status"].value_counts().sort_index().items()
        },
    }
