from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from qmt_universe import MARGIN_RATIOS, PRICETICKS, SIZES, SLIPPAGES, VT_SYMBOLS


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
PRODUCTS_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_products_2010_2026_04.csv"
METADATA_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_contract_metadata.csv"

MODEL_TAG: str = "full_market_tradable_universe_v1"
AUDIT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_full_market_tradable_universe_audit_{MODEL_TAG}.csv"
ELIGIBLE_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_full_market_tradable_universe_eligible_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_full_market_tradable_universe_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_roll_full_market_tradable_universe_report_{MODEL_TAG}.md"

ANALYSIS_START: pd.Timestamp = pd.Timestamp("2020-01-01")
ANALYSIS_END: pd.Timestamp = pd.Timestamp("2026-04-30")
RECENT_DAYS: int = 240
MIN_MAPPING_DAYS: int = 360
MIN_RECENT_MAPPING_DAYS: int = 120
MIN_RECENT_BAR_COVERAGE: float = 0.75
MIN_RECENT_NONZERO_VOLUME_RATIO: float = 0.60
MIN_RECENT_MEDIAN_VOLUME: float = 100.0
DEFAULT_MARGIN_RATIO: float = 0.15
CAPITAL: float = 200_000.0
MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO: float = 0.70


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    products = _read_csv(PRODUCTS_PATH)
    mapping = _read_csv(MAPPING_PATH)
    metadata = _read_csv(METADATA_PATH)

    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping["main_contract_tq"] = mapping["main_contract_tq"].fillna("").astype(str)
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[(mapping["date"] >= ANALYSIS_START) & (mapping["date"] <= ANALYSIS_END)].copy()

    for column in ("price_tick", "volume_multiple", "last_price", "reference_price"):
        if column in metadata.columns:
            metadata[column] = pd.to_numeric(metadata[column], errors="coerce")
    return products, mapping, metadata


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange] | None:
    if "." not in vt_symbol:
        return None
    symbol, exchange = vt_symbol.split(".", 1)
    try:
        return symbol, Exchange(exchange)
    except ValueError:
        return None


def _load_contract_bars(vt_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    database = get_database()
    rows: list[dict[str, Any]] = []
    start_dt = start.to_pydatetime()
    end_dt = end.to_pydatetime()

    for vt_symbol in sorted(set(vt_symbols)):
        parsed = _parse_vt_symbol(vt_symbol)
        if parsed is None:
            continue
        symbol, exchange = parsed
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "main_contract_vt": vt_symbol,
                    "close": float(bar.close_price),
                    "volume": float(getattr(bar, "volume", 0.0) or 0.0),
                    "open_interest": float(getattr(bar, "open_interest", 0.0) or 0.0),
                }
            )

    if not rows:
        return pd.DataFrame(columns=["date", "main_contract_vt", "close", "volume", "open_interest"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date", "main_contract_vt"]).sort_values(["main_contract_vt", "date"])


def _product_metadata(metadata: pd.DataFrame) -> dict[str, dict[str, float]]:
    product_rows = metadata[metadata.get("symbol_kind", "") == "product_cont"].copy()
    result: dict[str, dict[str, float]] = {}
    for row in product_rows.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        result[vt_symbol] = {
            "price_tick": _safe_float(getattr(row, "price_tick", 0.0)),
            "volume_multiple": _safe_float(getattr(row, "volume_multiple", 0.0)),
            "last_price": _safe_float(getattr(row, "last_price", 0.0)),
            "reference_price": _safe_float(getattr(row, "reference_price", 0.0)),
        }
    return result


def _latest_nonempty_date(product_mapping: pd.DataFrame) -> pd.Timestamp | None:
    nonempty = product_mapping[product_mapping["main_contract_tq"] != ""]
    if nonempty.empty:
        return None
    return pd.Timestamp(nonempty["date"].max()).normalize()


def _recent_market_metrics(product_mapping: pd.DataFrame) -> dict[str, float]:
    nonempty = product_mapping[product_mapping["main_contract_vt"] != ""].copy()
    if nonempty.empty:
        return {
            "recent_mapping_days": 0.0,
            "recent_bar_coverage_ratio": 0.0,
            "recent_nonzero_volume_ratio": 0.0,
            "recent_median_volume": 0.0,
            "recent_mean_volume": 0.0,
            "recent_median_close": 0.0,
            "recent_median_open_interest": 0.0,
        }

    recent_dates = sorted(nonempty["date"].unique())[-RECENT_DAYS:]
    recent_mapping = nonempty[nonempty["date"].isin(recent_dates)].copy()
    bar_df = _load_contract_bars(
        recent_mapping["main_contract_vt"].dropna().astype(str).unique().tolist(),
        pd.Timestamp(min(recent_dates)) - pd.Timedelta(days=5),
        pd.Timestamp(max(recent_dates)) + pd.Timedelta(days=5),
    )
    if bar_df.empty:
        return {
            "recent_mapping_days": float(recent_mapping["date"].nunique()),
            "recent_bar_coverage_ratio": 0.0,
            "recent_nonzero_volume_ratio": 0.0,
            "recent_median_volume": 0.0,
            "recent_mean_volume": 0.0,
            "recent_median_close": 0.0,
            "recent_median_open_interest": 0.0,
        }

    merged = recent_mapping[["date", "main_contract_vt"]].merge(
        bar_df,
        on=["date", "main_contract_vt"],
        how="left",
    )
    volume = pd.to_numeric(merged["volume"], errors="coerce").fillna(0.0)
    close = pd.to_numeric(merged["close"], errors="coerce").replace(0.0, np.nan)
    open_interest = pd.to_numeric(merged["open_interest"], errors="coerce").fillna(0.0)
    return {
        "recent_mapping_days": float(recent_mapping["date"].nunique()),
        "recent_bar_coverage_ratio": _safe_float(close.notna().mean()),
        "recent_nonzero_volume_ratio": _safe_float((volume > 0).mean()),
        "recent_median_volume": _safe_float(volume.median()),
        "recent_mean_volume": _safe_float(volume.mean()),
        "recent_median_close": _safe_float(close.median()),
        "recent_median_open_interest": _safe_float(open_interest.median()),
    }


def _exclude_reason(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    if not row["metadata_ok"]:
        reasons.append("metadata_missing")
    if row["mapping_days"] < MIN_MAPPING_DAYS:
        reasons.append("short_history")
    if not row["recently_active"]:
        reasons.append("inactive_recently")
    if row["recent_mapping_days"] < MIN_RECENT_MAPPING_DAYS:
        reasons.append("recent_mapping_insufficient")
    if row["recent_bar_coverage_ratio"] < MIN_RECENT_BAR_COVERAGE:
        reasons.append("recent_bar_incomplete")
    if row["recent_nonzero_volume_ratio"] < MIN_RECENT_NONZERO_VOLUME_RATIO:
        reasons.append("low_nonzero_volume_ratio")
    if row["recent_median_volume"] < MIN_RECENT_MEDIAN_VOLUME:
        reasons.append("low_median_volume")
    if row["estimated_margin_per_contract"] <= 0:
        reasons.append("invalid_margin")
    if row["estimated_margin_per_contract"] > CAPITAL * MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO:
        reasons.append("one_contract_margin_too_high")
    return ",".join(reasons) if reasons else ""


def build_universe() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    products, mapping, metadata = _load_inputs()
    metadata_by_product = _product_metadata(metadata)
    total_dates = int(mapping["date"].nunique())
    static_products = set(VT_SYMBOLS)
    rows: list[dict[str, Any]] = []

    for product_row in products.itertuples(index=False):
        product_vt = str(product_row.product_vt)
        product_mapping = mapping[mapping["continuous_symbol_vt"] == product_vt].copy()
        nonempty = product_mapping[product_mapping["main_contract_tq"] != ""]
        unique_main_contracts = sorted(nonempty["main_contract_tq"].dropna().astype(str).unique())
        latest_date = _latest_nonempty_date(product_mapping)
        market = _recent_market_metrics(product_mapping)
        meta = metadata_by_product.get(product_vt, {})

        price_tick = _safe_float(meta.get("price_tick", 0.0))
        volume_multiple = _safe_float(meta.get("volume_multiple", 0.0))
        metadata_price = _safe_float(meta.get("last_price", 0.0)) or _safe_float(meta.get("reference_price", 0.0))
        recent_close = _safe_float(market["recent_median_close"])
        effective_price = recent_close or metadata_price
        static_margin = _safe_float(MARGIN_RATIOS.get(product_vt, 0.0))
        margin_ratio = static_margin if static_margin > 0 else DEFAULT_MARGIN_RATIO
        static_slippage = _safe_float(SLIPPAGES.get(product_vt, 0.0))
        slippage = static_slippage if static_slippage > 0 else price_tick
        static_size = int(SIZES.get(product_vt, 0) or 0)
        size = static_size if static_size > 0 else int(round(volume_multiple)) if volume_multiple > 0 else 0
        static_pricetick = _safe_float(PRICETICKS.get(product_vt, 0.0))
        resolved_pricetick = static_pricetick if static_pricetick > 0 else price_tick
        notional = effective_price * size if effective_price > 0 and size > 0 else 0.0
        estimated_margin = notional * margin_ratio if notional > 0 and margin_ratio > 0 else 0.0
        recently_active = bool(latest_date is not None and latest_date >= ANALYSIS_END - pd.Timedelta(days=45))
        mapping_days = int(nonempty["date"].nunique())

        row: dict[str, Any] = {
            "product_vt_symbol": product_vt,
            "exchange": str(product_row.exchange),
            "product": str(product_row.product),
            "is_static_strategy_product": int(product_vt in static_products),
            "mapping_days": mapping_days,
            "mapping_coverage_ratio": mapping_days / total_dates if total_dates else 0.0,
            "latest_mapping_date": latest_date.date().isoformat() if latest_date is not None else "",
            "recently_active": int(recently_active),
            "main_contract_count": int(len(unique_main_contracts)),
            "price_tick": resolved_pricetick,
            "volume_multiple": size,
            "slippage": slippage,
            "margin_ratio": margin_ratio,
            "margin_ratio_source": "static" if static_margin > 0 else "default_conservative",
            "effective_price": effective_price,
            "notional_per_contract": notional,
            "estimated_margin_per_contract": estimated_margin,
            "metadata_ok": int(resolved_pricetick > 0 and size > 0),
            **market,
        }
        row["exclude_reason"] = _exclude_reason(row)
        row["eligible"] = int(row["exclude_reason"] == "")
        rows.append(row)

    audit = pd.DataFrame(rows).sort_values(
        ["eligible", "is_static_strategy_product", "recent_median_volume", "product_vt_symbol"],
        ascending=[False, False, False, True],
    )
    eligible = audit[audit["eligible"] == 1].copy()
    eligible.sort_values(["exchange", "product_vt_symbol"], inplace=True)

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "parameters": {
            "recent_days": RECENT_DAYS,
            "min_mapping_days": MIN_MAPPING_DAYS,
            "min_recent_mapping_days": MIN_RECENT_MAPPING_DAYS,
            "min_recent_bar_coverage": MIN_RECENT_BAR_COVERAGE,
            "min_recent_nonzero_volume_ratio": MIN_RECENT_NONZERO_VOLUME_RATIO,
            "min_recent_median_volume": MIN_RECENT_MEDIAN_VOLUME,
            "default_margin_ratio": DEFAULT_MARGIN_RATIO,
            "capital": CAPITAL,
            "max_single_trade_capital_usage_ratio": MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO,
        },
        "coverage": {
            "all_products": int(len(audit)),
            "eligible_products": int(len(eligible)),
            "static_strategy_products": int(audit["is_static_strategy_product"].sum()),
            "eligible_static_strategy_products": int(eligible["is_static_strategy_product"].sum()),
            "new_eligible_products": int((eligible["is_static_strategy_product"] == 0).sum()),
        },
        "eligible_products": eligible["product_vt_symbol"].astype(str).tolist(),
        "excluded_reason_counts": _reason_counts(audit),
        "artifacts": {
            "audit_csv": str(AUDIT_OUTPUT_PATH),
            "eligible_csv": str(ELIGIBLE_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
    }
    return audit, eligible, summary


def _reason_counts(audit: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in audit.loc[audit["eligible"] == 0, "exclude_reason"].fillna("").astype(str):
        for reason in value.split(","):
            if not reason:
                continue
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def build_report(audit: pd.DataFrame, eligible: pd.DataFrame, summary: dict[str, Any]) -> str:
    excluded = audit[audit["eligible"] == 0].copy()
    columns = [
        "product_vt_symbol",
        "exchange",
        "is_static_strategy_product",
        "mapping_days",
        "recent_bar_coverage_ratio",
        "recent_median_volume",
        "recent_nonzero_volume_ratio",
        "estimated_margin_per_contract",
        "exclude_reason",
    ]
    lines = [
        "# Full-Market Tradable Universe Audit",
        "",
        "## Judgement",
        "",
        "- This is a data-quality and executability filter, not a parameter optimization.",
        "- The eligible universe is intended for the next full-market strategy baseline run.",
        "- Non-static products use conservative margin assumptions because the current metadata lacks exchange margin ratios.",
        "",
        "## Coverage",
        "",
        f"- All continuous products: `{summary['coverage']['all_products']}`",
        f"- Eligible products: `{summary['coverage']['eligible_products']}`",
        f"- Static strategy products: `{summary['coverage']['static_strategy_products']}`",
        f"- Eligible static products: `{summary['coverage']['eligible_static_strategy_products']}`",
        f"- New eligible products: `{summary['coverage']['new_eligible_products']}`",
        "",
        "## Eligible Products",
        "",
        _table(
            eligible.sort_values(["is_static_strategy_product", "recent_median_volume"], ascending=[False, False]),
            [
                "product_vt_symbol",
                "exchange",
                "is_static_strategy_product",
                "mapping_days",
                "recent_median_volume",
                "estimated_margin_per_contract",
                "margin_ratio_source",
            ],
            max_rows=80,
        ),
        "",
        "## Excluded Reason Counts",
        "",
        json.dumps(summary["excluded_reason_counts"], ensure_ascii=False, indent=2),
        "",
        "## Excluded Sample",
        "",
        _table(excluded.sort_values(["exclude_reason", "product_vt_symbol"]), columns, max_rows=40),
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit, eligible, summary = build_universe()
    audit.to_csv(AUDIT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    eligible.to_csv(ELIGIBLE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(audit, eligible, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
