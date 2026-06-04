from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DAILY_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

MODEL_TAG = "stage565_stage526_liquidity_capacity_product_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage565_stage526_liquidity_capacity_product_audit"

STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_VARIANT = "r080_pc25_maxpos4"
STAGE526_POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE526_SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"

STAGE541_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
STAGE541_TAG = "stage541_single_product_opportunity_map_v1"
STAGE541_SUMMARY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_summary_{STAGE541_TAG}.csv"
STAGE541_POSITIONS_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_positions_{STAGE541_TAG}.csv"

STAGE557_PRODUCT_IN = (
    OUTPUT_DIR
    / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_product_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv"
)

EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage526_trade_liquidity_events_{MODEL_TAG}.csv"
STAGE526_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage526_product_liquidity_{MODEL_TAG}.csv"
SINGLE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_single_product_liquidity_{MODEL_TAG}.csv"
COMBINED_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_product_capacity_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_liquidity_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BAD_START = pd.Timestamp("2022-03-09")
BAD_END = pd.Timestamp("2022-12-07")
STRESS_ORDER_VOLUME_PCT = 0.50
SOFT_ORDER_VOLUME_PCT = 0.25
STRESS_POSITION_OI_PCT = 1.00


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _contract_path(vt_symbol: object) -> Path | None:
    raw = str(vt_symbol)
    if "." not in raw:
        return None
    symbol, exchange = raw.split(".", 1)
    directory = DAILY_ROOT / exchange
    candidates = [symbol, symbol.lower(), symbol.upper()]
    for candidate in candidates:
        path = directory / f"{candidate}.csv"
        if path.exists():
            return path
    return None


_DAILY_CACHE: dict[str, pd.DataFrame] = {}


def _contract_daily(vt_symbol: object) -> pd.DataFrame:
    raw = str(vt_symbol)
    if raw in _DAILY_CACHE:
        return _DAILY_CACHE[raw]
    path = _contract_path(raw)
    if path is None:
        frame = pd.DataFrame(columns=["date", "daily_volume", "daily_open_oi", "daily_close_oi", "daily_close"])
        _DAILY_CACHE[raw] = frame
        return frame
    frame = _read_csv(path)
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    out = pd.DataFrame(
        {
            "date": frame["date"],
            "daily_volume": _num(frame, "volume"),
            "daily_open_oi": _num(frame, "open_oi"),
            "daily_close_oi": _num(frame, "close_oi"),
            "daily_close": _num(frame, "close"),
        }
    ).dropna(subset=["date"])
    _DAILY_CACHE[raw] = out
    return out


def _attach_liquidity(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    parts: list[pd.DataFrame] = []
    for vt_symbol, group in events.groupby("vt_symbol", sort=False):
        daily = _contract_daily(vt_symbol)
        merged = group.merge(daily, on="date", how="left")
        parts.append(merged)
    out = pd.concat(parts, ignore_index=True)
    out["liquidity_data_found"] = out["daily_volume"].notna().astype(int)
    out[["daily_volume", "daily_open_oi", "daily_close_oi", "daily_close"]] = out[
        ["daily_volume", "daily_open_oi", "daily_close_oi", "daily_close"]
    ].fillna(0.0)
    out["volume_data_found"] = (out["liquidity_data_found"].eq(1) & out["daily_volume"].gt(0.0)).astype(int)
    out["oi_data_found"] = (out["liquidity_data_found"].eq(1) & out["daily_close_oi"].gt(0.0)).astype(int)
    out["volume_data_gap_event"] = out["volume_data_found"].eq(0).astype(int)
    out["oi_data_gap_event"] = out["oi_data_found"].eq(0).astype(int)
    out["order_volume_to_day_volume_pct"] = np.where(
        out["daily_volume"] > 0.0, out["order_volume"] / out["daily_volume"] * 100.0, np.nan
    )
    out["order_volume_to_oi_pct"] = np.where(
        out["daily_close_oi"] > 0.0, out["order_volume"] / out["daily_close_oi"] * 100.0, np.nan
    )
    out["end_position_to_oi_pct"] = np.where(
        out["daily_close_oi"] > 0.0, out["end_abs_pos"] / out["daily_close_oi"] * 100.0, np.nan
    )
    out["peak_position_to_oi_pct"] = np.where(
        out["daily_close_oi"] > 0.0, out["peak_abs_pos"] / out["daily_close_oi"] * 100.0, np.nan
    )
    out["soft_volume_stress_event"] = (
        out["volume_data_found"].eq(1) & out["order_volume_to_day_volume_pct"].fillna(0.0).gt(SOFT_ORDER_VOLUME_PCT)
    ).astype(int)
    out["hard_volume_stress_event"] = (
        out["volume_data_found"].eq(1) & out["order_volume_to_day_volume_pct"].fillna(0.0).gt(STRESS_ORDER_VOLUME_PCT)
    ).astype(int)
    out["position_oi_stress_event"] = (
        out["oi_data_found"].eq(1) & out["peak_position_to_oi_pct"].fillna(0.0).gt(STRESS_POSITION_OI_PCT)
    ).astype(int)
    out["liquidity_bucket"] = pd.cut(
        out["order_volume_to_day_volume_pct"].fillna(999.0),
        bins=[-0.001, 0.05, 0.10, 0.25, 0.50, 1.00, 5.00, 1_000.0],
        labels=["<=0.05%", "0.05-0.10%", "0.10-0.25%", "0.25-0.50%", "0.50-1.00%", "1-5%", ">5%/missing"],
        include_lowest=True,
    ).astype(str)
    return out


def _events_from_positions(path: Path, variant: str | None = None, usecols: list[str] | None = None) -> pd.DataFrame:
    frame = _read_csv(path, usecols=usecols)
    if variant is not None and "variant" in frame.columns:
        frame = frame[frame["variant"].eq(variant)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "close_price",
    ]:
        frame[column] = _num(frame, column)
    event = frame[(frame["pos_change"].abs() > 0.0) | (frame["trade_count"] > 0.0)].copy()
    event["product_vt_symbol"] = event["vt_symbol"].map(_product_from_contract)
    event["order_volume"] = event["pos_change"].abs()
    event["start_abs_pos"] = event["start_pos"].abs()
    event["end_abs_pos"] = event["end_pos"].abs()
    event["peak_abs_pos"] = event[["start_abs_pos", "end_abs_pos"]].max(axis=1)
    event["offset_type"] = np.select(
        [
            event["start_abs_pos"].eq(0.0) & event["end_abs_pos"].gt(0.0),
            event["start_abs_pos"].gt(0.0) & event["end_abs_pos"].eq(0.0),
            event["start_pos"].mul(event["end_pos"]).lt(0.0),
            event["end_abs_pos"].gt(event["start_abs_pos"]),
            event["end_abs_pos"].lt(event["start_abs_pos"]),
        ],
        ["open", "close", "reverse", "add", "reduce"],
        default="adjust",
    )
    event["direction_after"] = np.select(
        [event["end_pos"].gt(0.0), event["end_pos"].lt(0.0)], ["long", "short"], default="flat"
    )
    event["year"] = event["date"].dt.year.astype(int)
    event["bad_window_overlap"] = event["date"].between(BAD_START, BAD_END).astype(int)
    return event.sort_values(["date", "vt_symbol"]).reset_index(drop=True)


def load_stage526_events() -> pd.DataFrame:
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    events = _events_from_positions(STAGE526_POSITIONS_IN, variant=STAGE526_VARIANT, usecols=usecols)
    events.insert(0, "source", "stage526")
    return _attach_liquidity(events)


def load_single_product_events() -> pd.DataFrame:
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "product_vt_symbol",
        "is_core_product",
        "exchange",
        "product",
        "variant",
    ]
    events = _events_from_positions(STAGE541_POSITIONS_IN, usecols=usecols)
    events.insert(0, "source", "stage541_single_product")
    return _attach_liquidity(events)


def summarize_events(events: pd.DataFrame, source: str) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    grouped = (
        events.groupby("product_vt_symbol", as_index=False)
        .agg(
            event_count=("vt_symbol", "count"),
            contract_count=("vt_symbol", "nunique"),
            matched_liquidity_events=("liquidity_data_found", "sum"),
            volume_data_gap_events=("volume_data_gap_event", "sum"),
            oi_data_gap_events=("oi_data_gap_event", "sum"),
            soft_volume_stress_events=("soft_volume_stress_event", "sum"),
            hard_volume_stress_events=("hard_volume_stress_event", "sum"),
            position_oi_stress_events=("position_oi_stress_event", "sum"),
            total_order_volume=("order_volume", "sum"),
            max_order_volume=("order_volume", "max"),
            p50_order_volume_to_day_volume_pct=("order_volume_to_day_volume_pct", "median"),
            p90_order_volume_to_day_volume_pct=("order_volume_to_day_volume_pct", lambda s: float(s.dropna().quantile(0.90)) if s.dropna().size else np.nan),
            p95_order_volume_to_day_volume_pct=("order_volume_to_day_volume_pct", lambda s: float(s.dropna().quantile(0.95)) if s.dropna().size else np.nan),
            max_order_volume_to_day_volume_pct=("order_volume_to_day_volume_pct", "max"),
            p95_peak_position_to_oi_pct=("peak_position_to_oi_pct", lambda s: float(s.dropna().quantile(0.95)) if s.dropna().size else np.nan),
            max_peak_position_to_oi_pct=("peak_position_to_oi_pct", "max"),
            total_net_pnl_on_trade_days=("net_pnl", "sum"),
            total_slippage_on_trade_days=("slippage", "sum"),
            bad_window_trade_net_pnl=("net_pnl", lambda s: float(s[events.loc[s.index, "bad_window_overlap"].eq(1)].sum())),
        )
        .sort_values(["hard_volume_stress_events", "max_order_volume_to_day_volume_pct"], ascending=[False, False])
    )
    grouped.insert(0, "source", source)
    grouped["liquidity_match_rate_pct"] = grouped["matched_liquidity_events"] / grouped["event_count"].replace(0, np.nan) * 100.0
    grouped["volume_data_coverage_rate_pct"] = (
        (grouped["event_count"] - grouped["volume_data_gap_events"]) / grouped["event_count"].replace(0, np.nan) * 100.0
    )
    grouped["oi_data_coverage_rate_pct"] = (
        (grouped["event_count"] - grouped["oi_data_gap_events"]) / grouped["event_count"].replace(0, np.nan) * 100.0
    )
    grouped["hard_volume_stress_event_rate_pct"] = (
        grouped["hard_volume_stress_events"] / grouped["event_count"].replace(0, np.nan) * 100.0
    )
    grouped["soft_volume_stress_event_rate_pct"] = (
        grouped["soft_volume_stress_events"] / grouped["event_count"].replace(0, np.nan) * 100.0
    )
    grouped["position_oi_stress_event_rate_pct"] = (
        grouped["position_oi_stress_events"] / grouped["event_count"].replace(0, np.nan) * 100.0
    )
    return grouped.fillna(0.0)


def build_annual(stage526_events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in stage526_events.groupby("year"):
        rows.append(
            {
                "year": int(year),
                "event_count": int(len(group)),
                "product_count": int(group["product_vt_symbol"].nunique()),
                "liquidity_match_rate_pct": float(group["liquidity_data_found"].mean() * 100.0),
                "volume_data_coverage_rate_pct": float(group["volume_data_found"].mean() * 100.0),
                "oi_data_coverage_rate_pct": float(group["oi_data_found"].mean() * 100.0),
                "p95_order_volume_to_day_volume_pct": float(group["order_volume_to_day_volume_pct"].dropna().quantile(0.95))
                if group["order_volume_to_day_volume_pct"].dropna().size
                else 0.0,
                "max_order_volume_to_day_volume_pct": float(group["order_volume_to_day_volume_pct"].max()),
                "hard_volume_stress_events": int(group["hard_volume_stress_event"].sum()),
                "hard_volume_stress_event_rate_pct": float(group["hard_volume_stress_event"].mean() * 100.0),
                "position_oi_stress_events": int(group["position_oi_stress_event"].sum()),
                "trade_day_net_pnl": float(group["net_pnl"].sum()),
                "trade_day_slippage": float(group["slippage"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def build_combined_product(stage526_summary: pd.DataFrame, single_summary: pd.DataFrame) -> pd.DataFrame:
    product_summary = _read_csv(STAGE541_SUMMARY_IN)
    product_summary = product_summary.rename(
        columns={
            "total_pnl": "single_product_total_pnl",
            "total_return_pct": "single_product_total_return_pct",
            "max_dd_pct": "single_product_max_dd_pct",
            "sharpe": "single_product_sharpe",
            "trade_count": "single_product_trade_count",
            "slippage": "single_product_slippage",
        }
    )
    for column in [
        "single_product_total_pnl",
        "single_product_total_return_pct",
        "single_product_max_dd_pct",
        "single_product_sharpe",
        "single_product_trade_count",
        "single_product_slippage",
        "recent_median_volume",
        "core_daily_pnl_corr",
        "max_broker10_margin_to_sleeve_equity_pct",
        "candidate_materiality_pass",
        "is_core_product",
    ]:
        product_summary[column] = _num(product_summary, column)
    keep = [
        "product_vt_symbol",
        "exchange",
        "product",
        "is_core_product",
        "single_product_total_pnl",
        "single_product_total_return_pct",
        "single_product_max_dd_pct",
        "single_product_sharpe",
        "single_product_trade_count",
        "single_product_slippage",
        "recent_median_volume",
        "core_daily_pnl_corr",
        "max_broker10_margin_to_sleeve_equity_pct",
        "candidate_materiality_pass",
        "opportunity_score",
    ]
    keep = [column for column in keep if column in product_summary.columns]
    out = product_summary[keep].copy()
    single_liq = single_summary.drop(columns=["source"], errors="ignore").add_prefix("single_")
    single_liq = single_liq.rename(columns={"single_product_vt_symbol": "product_vt_symbol"})
    out = out.merge(single_liq, on="product_vt_symbol", how="left")
    stage526_liq = stage526_summary.drop(columns=["source"], errors="ignore").add_prefix("stage526_")
    stage526_liq = stage526_liq.rename(columns={"stage526_product_vt_symbol": "product_vt_symbol"})
    out = out.merge(stage526_liq, on="product_vt_symbol", how="left")
    if STAGE557_PRODUCT_IN.exists():
        harvest = _read_csv(STAGE557_PRODUCT_IN)
        harvest = harvest[harvest["variant"].eq("breadth_all_noncore_r020_famcap20_corr5075_maxpos8")].copy()
        harvest["satellite_product_net_pnl"] = _num(harvest, "satellite_product_net_pnl")
        sleeve = (
            harvest.groupby("product_vt_symbol", as_index=False)
            .agg(
                breadth_all_noncore_sleeve_pnl=("satellite_product_net_pnl", "sum"),
                breadth_all_noncore_active_days=("active_days", "sum"),
                breadth_all_noncore_max_margin=("max_margin", "max"),
            )
            .copy()
        )
        out = out.merge(sleeve, on="product_vt_symbol", how="left")
    for column in out.columns:
        if column not in {"product_vt_symbol", "exchange", "product"}:
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    out["capacity_quality_flag"] = np.select(
        [
            out["single_hard_volume_stress_event_rate_pct"].gt(10.0)
            | out["single_max_order_volume_to_day_volume_pct"].gt(1.0)
            | out["single_position_oi_stress_event_rate_pct"].gt(10.0),
            out["single_volume_data_coverage_rate_pct"].lt(95.0)
            | out["single_oi_data_coverage_rate_pct"].lt(95.0)
            | out["single_p95_order_volume_to_day_volume_pct"].gt(0.50)
            | out["single_p95_peak_position_to_oi_pct"].gt(1.00),
        ],
        ["red", "yellow"],
        default="green",
    )
    out["material_and_capacity_ok"] = (
        out["candidate_materiality_pass"].eq(1)
        & out["capacity_quality_flag"].eq("green")
        & out["single_product_total_pnl"].gt(0.0)
    ).astype(int)
    return out.sort_values(
        ["material_and_capacity_ok", "candidate_materiality_pass", "single_product_total_pnl"],
        ascending=[False, False, False],
    )


def build_gates(stage526_events: pd.DataFrame, combined: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    material = combined[combined["candidate_materiality_pass"].eq(1)].copy()
    stage526_match = float(stage526_events["liquidity_data_found"].mean() * 100.0) if len(stage526_events) else 0.0
    stage526_volume_coverage = float(stage526_events["volume_data_found"].mean() * 100.0) if len(stage526_events) else 0.0
    stage526_oi_coverage = float(stage526_events["oi_data_found"].mean() * 100.0) if len(stage526_events) else 0.0
    stage526_p95 = (
        float(stage526_events["order_volume_to_day_volume_pct"].dropna().quantile(0.95))
        if stage526_events["order_volume_to_day_volume_pct"].dropna().size
        else 999.0
    )
    stage526_max = float(stage526_events["order_volume_to_day_volume_pct"].max())
    stage526_hard_rate = float(stage526_events["hard_volume_stress_event"].mean() * 100.0) if len(stage526_events) else 100.0
    stage526_position_oi_rate = (
        float(stage526_events["position_oi_stress_event"].mean() * 100.0) if len(stage526_events) else 100.0
    )
    stress = stage526_events[stage526_events["hard_volume_stress_event"].eq(1)]
    stress_pnl_share = float(stress["net_pnl"].sum() / stage526_events["net_pnl"].abs().sum() * 100.0) if len(stage526_events) else 0.0
    material_ok_count = int(material["material_and_capacity_ok"].sum()) if not material.empty else 0
    material_red_count = int(material["capacity_quality_flag"].eq("red").sum()) if not material.empty else 0
    material_count = int(len(material))
    gate_rows = [
        {
            "gate": "stage526_volume_coverage_ge_95pct",
            "pass": int(stage526_volume_coverage >= 95.0),
            "value": stage526_volume_coverage,
            "threshold": 95.0,
            "note": "Stage526交易事件能匹配TqSdk正成交量。",
        },
        {
            "gate": "stage526_oi_coverage_ge_95pct",
            "pass": int(stage526_oi_coverage >= 95.0),
            "value": stage526_oi_coverage,
            "threshold": 95.0,
            "note": "Stage526交易事件能匹配TqSdk正持仓量。",
        },
        {
            "gate": "stage526_p95_order_volume_le_0p25pct",
            "pass": int(stage526_p95 <= SOFT_ORDER_VOLUME_PCT),
            "value": stage526_p95,
            "threshold": SOFT_ORDER_VOLUME_PCT,
            "note": "95分位订单量占日成交量不超过软容量线。",
        },
        {
            "gate": "stage526_max_order_volume_le_1pct",
            "pass": int(stage526_max <= 1.0),
            "value": stage526_max,
            "threshold": 1.0,
            "note": "单次订单量不应超过日成交量1%。",
        },
        {
            "gate": "stage526_hard_stress_event_rate_le_5pct",
            "pass": int(stage526_hard_rate <= 5.0),
            "value": stage526_hard_rate,
            "threshold": 5.0,
            "note": "硬容量压力事件占比不超过5%。",
        },
        {
            "gate": "stage526_position_oi_stress_event_rate_le_5pct",
            "pass": int(stage526_position_oi_rate <= 5.0),
            "value": stage526_position_oi_rate,
            "threshold": 5.0,
            "note": "持仓占合约持仓量压力事件占比不超过5%。",
        },
        {
            "gate": "stage526_liquidity_stress_not_main_loss_driver",
            "pass": int(abs(stress_pnl_share) <= 10.0),
            "value": stress_pnl_share,
            "threshold": 10.0,
            "note": "硬容量压力事件的交易日PnL不应解释主要亏损。",
        },
        {
            "gate": "material_noncore_capacity_ok_ge_4",
            "pass": int(material_ok_count >= 4),
            "value": float(material_ok_count),
            "threshold": 4.0,
            "note": "Stage541材料性非核心候选中至少4个同时通过容量绿灯。",
        },
        {
            "gate": "material_noncore_red_capacity_eq_0",
            "pass": int(material_red_count == 0),
            "value": float(material_red_count),
            "threshold": 0.0,
            "note": "材料性非核心候选不能存在容量红灯。",
        },
    ]
    gates = pd.DataFrame(gate_rows)
    pass_count = int(gates["pass"].sum())
    coverage_pass = stage526_volume_coverage >= 95.0 and stage526_oi_coverage >= 95.0
    actual_capacity_pass = (
        stage526_p95 <= SOFT_ORDER_VOLUME_PCT
        and stage526_max <= 1.0
        and stage526_hard_rate <= 5.0
        and stage526_position_oi_rate <= 5.0
        and abs(stress_pnl_share) <= 10.0
    )
    if actual_capacity_pass and material_ok_count >= 4 and not coverage_pass:
        decision_text = "capacity_ok_with_data_gaps_selector_still_needed"
    elif actual_capacity_pass and material_ok_count >= 4:
        decision_text = "capacity_ok_but_selector_still_needed"
    else:
        decision_text = "liquidity_capacity_caution_selector_not_ready"
    decision = {
        "decision": decision_text,
        "passed_gates": pass_count,
        "total_gates": int(len(gates)),
        "stage526_event_count": int(len(stage526_events)),
        "stage526_liquidity_match_rate_pct": stage526_match,
        "stage526_volume_data_coverage_rate_pct": stage526_volume_coverage,
        "stage526_oi_data_coverage_rate_pct": stage526_oi_coverage,
        "stage526_p95_order_volume_to_day_volume_pct": stage526_p95,
        "stage526_max_order_volume_to_day_volume_pct": stage526_max,
        "stage526_hard_volume_stress_event_rate_pct": stage526_hard_rate,
        "stage526_position_oi_stress_event_rate_pct": stage526_position_oi_rate,
        "hard_liquidity_stress_trade_day_pnl_share_of_abs_trade_day_pnl_pct": stress_pnl_share,
        "material_noncore_count": material_count,
        "material_noncore_capacity_green_count": material_ok_count,
        "material_noncore_capacity_red_count": material_red_count,
        "material_noncore_capacity_green_products": material.loc[
            material["material_and_capacity_ok"].eq(1), "product_vt_symbol"
        ].astype(str).tolist(),
        "material_noncore_capacity_red_products": material.loc[
            material["capacity_quality_flag"].eq("red"), "product_vt_symbol"
        ].astype(str).tolist(),
    }
    return gates, decision


def build_summary(decision: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    stage526_summary = _read_csv(STAGE526_SUMMARY_IN)
    row = stage526_summary[stage526_summary["variant"].eq(STAGE526_VARIANT)]
    ref: dict[str, Any] = {}
    if not row.empty:
        record = row.iloc[0]
        for column in [
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
        ]:
            ref[column] = float(record.get(column, 0.0))
    material = combined[combined["candidate_materiality_pass"].eq(1)].copy()
    return pd.DataFrame(
        [
            {
                **ref,
                **decision,
                "material_noncore_avg_recent_median_volume": float(material["recent_median_volume"].mean())
                if not material.empty
                else 0.0,
                "material_noncore_min_recent_median_volume": float(material["recent_median_volume"].min())
                if not material.empty
                else 0.0,
                "material_noncore_avg_single_p95_order_volume_to_day_volume_pct": float(
                    material["single_p95_order_volume_to_day_volume_pct"].mean()
                )
                if not material.empty
                else 0.0,
            }
        ]
    )


def plot_outputs(stage526_events: pd.DataFrame, combined: pd.DataFrame, annual: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_event, ax_scatter, ax_product, ax_annual = axes.flatten()

    event_plot = stage526_events.copy()
    matched_event_plot = event_plot[event_plot["volume_data_found"].eq(1)].copy()
    gap_event_plot = event_plot[event_plot["volume_data_found"].eq(0)].copy()
    matched_event_plot["order_volume_to_day_volume_pct_plot"] = matched_event_plot[
        "order_volume_to_day_volume_pct"
    ].clip(upper=2.0)
    colors = np.where(matched_event_plot["hard_volume_stress_event"].eq(1), "#dc2626", "#2563eb")
    ax_event.scatter(
        matched_event_plot["date"],
        matched_event_plot["order_volume_to_day_volume_pct_plot"],
        s=np.maximum(matched_event_plot["order_volume"], 1.0) * 4.0,
        c=colors,
        alpha=0.65,
        edgecolors="none",
        label="matched event",
    )
    if not gap_event_plot.empty:
        ax_event.scatter(
            gap_event_plot["date"],
            np.full(len(gap_event_plot), 1.20),
            s=28,
            c="#64748b",
            marker="x",
            alpha=0.75,
            label="volume data gap",
        )
    ax_event.axhline(SOFT_ORDER_VOLUME_PCT, color="#f59e0b", linestyle="--", linewidth=1)
    ax_event.axhline(STRESS_ORDER_VOLUME_PCT, color="#dc2626", linestyle="--", linewidth=1)
    ax_event.set_title("Stage526交易事件容量压力")
    ax_event.set_ylabel("订单量/当日日成交量%")
    ax_event.grid(alpha=0.25)
    ax_event.legend(fontsize=8)

    scatter = combined.copy()
    scatter["abs_corr"] = scatter["core_daily_pnl_corr"].abs()
    color_map = {"green": "#16a34a", "yellow": "#f59e0b", "red": "#dc2626"}
    ax_scatter.scatter(
        scatter["single_p95_order_volume_to_day_volume_pct"].clip(upper=2.0),
        scatter["single_product_total_pnl"],
        c=[color_map.get(x, "#64748b") for x in scatter["capacity_quality_flag"]],
        s=np.where(scatter["candidate_materiality_pass"].eq(1), 90, 35),
        alpha=0.75,
    )
    material = scatter[scatter["candidate_materiality_pass"].eq(1)]
    for row in material.itertuples(index=False):
        ax_scatter.annotate(str(row.product_vt_symbol), (row.single_p95_order_volume_to_day_volume_pct, row.single_product_total_pnl), fontsize=8)
    ax_scatter.axvline(SOFT_ORDER_VOLUME_PCT, color="#f59e0b", linestyle="--", linewidth=1)
    ax_scatter.axvline(STRESS_ORDER_VOLUME_PCT, color="#dc2626", linestyle="--", linewidth=1)
    ax_scatter.axhline(0.0, color="#111827", linewidth=0.8)
    ax_scatter.set_title("单品种机会收益 vs 容量压力")
    ax_scatter.set_xlabel("单品种事件 p95 订单量/日成交量%")
    ax_scatter.set_ylabel("单品种总PnL")
    ax_scatter.grid(alpha=0.25)

    top = combined.sort_values("single_max_order_volume_to_day_volume_pct", ascending=False).head(12).copy()
    ax_product.barh(top["product_vt_symbol"], top["single_max_order_volume_to_day_volume_pct"], color="#7c3aed")
    ax_product.axvline(STRESS_ORDER_VOLUME_PCT, color="#dc2626", linestyle="--", linewidth=1)
    ax_product.invert_yaxis()
    ax_product.set_title("扩池单品种最大容量压力 Top12")
    ax_product.set_xlabel("最大订单量/日成交量%")
    ax_product.grid(axis="x", alpha=0.25)

    ax_annual.plot(annual["year"], annual["p95_order_volume_to_day_volume_pct"], marker="o", label="p95 order/day volume", color="#2563eb")
    ax_annual.bar(annual["year"], annual["hard_volume_stress_event_rate_pct"], alpha=0.35, label="hard stress event rate%", color="#dc2626")
    ax_annual.axhline(STRESS_ORDER_VOLUME_PCT, color="#dc2626", linestyle="--", linewidth=1)
    ax_annual.set_title("Stage526年度容量压力")
    ax_annual.set_ylabel("%")
    ax_annual.grid(alpha=0.25)
    ax_coverage = ax_annual.twinx()
    ax_coverage.plot(
        annual["year"],
        annual["volume_data_coverage_rate_pct"],
        marker="s",
        color="#64748b",
        label="volume coverage%",
        linewidth=1.0,
    )
    ax_coverage.set_ylim(0, 105)
    ax_coverage.set_ylabel("coverage%")
    lines, labels = ax_annual.get_legend_handles_labels()
    lines2, labels2 = ax_coverage.get_legend_handles_labels()
    ax_annual.legend(lines + lines2, labels + labels2, fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    stage526_events: pd.DataFrame,
    stage526_product: pd.DataFrame,
    combined: pd.DataFrame,
    annual: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    material = combined[combined["candidate_materiality_pass"].eq(1)].copy()
    material_view = material[
        [
            "product_vt_symbol",
            "single_product_total_pnl",
            "single_product_max_dd_pct",
            "recent_median_volume",
            "single_volume_data_coverage_rate_pct",
            "single_p95_order_volume_to_day_volume_pct",
            "single_max_order_volume_to_day_volume_pct",
            "single_p95_peak_position_to_oi_pct",
            "capacity_quality_flag",
            "material_and_capacity_ok",
        ]
    ].sort_values("single_product_total_pnl", ascending=False)
    stage526_stress = stage526_events[
        stage526_events["hard_volume_stress_event"].eq(1) | stage526_events["position_oi_stress_event"].eq(1)
    ][
        [
            "date",
            "vt_symbol",
            "product_vt_symbol",
            "offset_type",
            "order_volume",
            "daily_volume",
            "daily_close_oi",
            "order_volume_to_day_volume_pct",
            "peak_position_to_oi_pct",
            "net_pnl",
            "slippage",
        ]
    ].sort_values(["order_volume_to_day_volume_pct", "peak_position_to_oi_pct"], ascending=False)
    data_gap = (
        stage526_events[stage526_events["volume_data_gap_event"].eq(1)]
        .groupby("product_vt_symbol", as_index=False)
        .agg(
            gap_events=("vt_symbol", "count"),
            first_gap_date=("date", "min"),
            last_gap_date=("date", "max"),
            trade_day_net_pnl=("net_pnl", "sum"),
            trade_day_slippage=("slippage", "sum"),
        )
        .sort_values("gap_events", ascending=False)
    )
    lines = [
        f"# Stage565 Stage526流动性/容量/扩池品种可承载性审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        "- 阶段性质：只读容量审计；不改策略、不改参数、不生成交易候选。",
        "- 研究问题：Stage526 在真实成交上是否有容量压力；Stage541 里看似能扩池的材料性候选，是否同时具备可承载成交量。",
        "- 调研判断：成熟趋势跟随研究通常把分散、成本、换手和流动性分开建模；本阶段采用保守的成交量/持仓量占比闸门，只作为实盘可承载性审计，不作为 alpha。",
        "- 运行前过拟合反思：否。本阶段不根据结果调参数，只检查既有候选在当时合约成交量/持仓量下是否可执行。",
        "- 运行前继续价值反思：有。若低风险扩池要成立，必须先证明候选品种不会把纸面收益建立在低流动性成交上。",
        "",
        "## 决策",
        "",
        f"- decision：`{decision['decision']}`",
        f"- gates：`{decision['passed_gates']}/{decision['total_gates']}`",
        f"- Stage526事件数：`{decision['stage526_event_count']}`",
        f"- Stage526流动性匹配率：`{decision['stage526_liquidity_match_rate_pct']:.4f}%`",
        f"- Stage526正成交量覆盖率：`{decision['stage526_volume_data_coverage_rate_pct']:.4f}%`",
        f"- Stage526正持仓量覆盖率：`{decision['stage526_oi_data_coverage_rate_pct']:.4f}%`",
        f"- Stage526 p95订单量/日成交量：`{decision['stage526_p95_order_volume_to_day_volume_pct']:.4f}%`",
        f"- Stage526 max订单量/日成交量：`{decision['stage526_max_order_volume_to_day_volume_pct']:.4f}%`",
        f"- Stage526硬容量压力事件占比：`{decision['stage526_hard_volume_stress_event_rate_pct']:.4f}%`",
        f"- Stage526持仓/OI压力事件占比：`{decision['stage526_position_oi_stress_event_rate_pct']:.4f}%`",
        f"- 材料性非核心容量绿灯：`{decision['material_noncore_capacity_green_count']}/{decision['material_noncore_count']}`",
        f"- 材料性非核心容量红灯：`{decision['material_noncore_capacity_red_count']}`",
        "",
        "## 闸门",
        "",
        _md_table(gates),
        "",
        "## Stage526产品容量压力 Top",
        "",
        _md_table(
            stage526_product[
                [
                    "product_vt_symbol",
                    "event_count",
                    "p95_order_volume_to_day_volume_pct",
                    "max_order_volume_to_day_volume_pct",
                    "p95_peak_position_to_oi_pct",
                    "hard_volume_stress_event_rate_pct",
                    "total_net_pnl_on_trade_days",
                ]
            ].sort_values("max_order_volume_to_day_volume_pct", ascending=False),
            max_rows=12,
        ),
        "",
        "## Stage526压力事件样本",
        "",
        _md_table(stage526_stress, max_rows=20),
        "",
        "## Stage526成交量/OI数据缺口",
        "",
        _md_table(data_gap, max_rows=20),
        "",
        "## 材料性扩池候选容量表",
        "",
        _md_table(material_view, max_rows=20),
        "",
        "## 年度容量",
        "",
        _md_table(annual),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表路径：`{CHART_PATH}`",
        "- 左上图用于看 Stage526 的交易事件容量压力是否集中在少数日期/品种。",
        "- 右上图用于看扩池候选是否同时满足正收益和低容量压力；被标注的是材料性非核心候选。",
        "- 左下图用于暴露扩池单品种里最可能出现纸面成交风险的产品。",
        "- 右下图用于检查容量压力是否随年份恶化，尤其是否与 2022 弱窗口重叠。",
        "",
        "## 结论",
        "",
        "- 如果 Stage526 的容量压力闸门通过，则它的主要实盘风险仍是 Stage265 的真实滑点倍率监控，而不是订单量吃掉日成交量。",
        "- 如果扩池材料性候选多数为绿灯，说明“扩大品种池”不是被流动性直接否决；真正瓶颈仍是 Stage264/263 指出的选品器和 forward 外生数据。",
        "- 若出现容量红灯候选，该产品不得因历史收益好直接晋级，只能进入观察或降风险纸面池。",
        "",
        "## 后续规划",
        "",
        "- 下一步不继续扫扩池小数。若本阶段容量可接受，应转向真实成交滑点采样账本：记录信号价、提交价、成交价、窗口VWAP、实际滑点与订单量/当时盘口容量。",
        "- 品种选择路线仍需按 Stage261/263 累计 `20` 个合格 forward 外生样本和真实舆情/新闻账本，未达标前禁止选品收益回测。",
        "",
        "## 运行后反思",
        "",
        "- 过拟合：否。审计只读取既有回测事件和独立TqSdk日成交量/持仓量，没有用结果筛参数。",
        "- 继续价值：有。容量审计能把“收益好但不可成交”的候选提前剔除；但它不能替代选品器，也不能证明未来收益。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage526_events = load_stage526_events()
    single_events = load_single_product_events()
    stage526_product = summarize_events(stage526_events, "stage526")
    single_product = summarize_events(single_events, "stage541_single_product")
    combined = build_combined_product(stage526_product, single_product)
    annual = build_annual(stage526_events)
    gates, decision = build_gates(stage526_events, combined)
    summary = build_summary(decision, combined)

    stage526_events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    stage526_product.to_csv(STAGE526_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    single_product.to_csv(SINGLE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(COMBINED_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_outputs(stage526_events, combined, annual)
    write_report(stage526_events, stage526_product, combined, annual, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(REPORT_PATH)
    print(CHART_PATH)


if __name__ == "__main__":
    main()
