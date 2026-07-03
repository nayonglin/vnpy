from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006
import stage024_causal_high_vol_pause_engine as s024

import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage027"
MODEL_TAG = "stage027_remaining_worst_window_position_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage027_remaining_worst_window_position_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage027_remaining_worst_window_position_attribution"
STAGE_RECORD_DIR = LINE_DIR / "stages"
STAGE024_OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_causal_high_vol_pause_engine"

STAGE024_PREFIX = "rebuilt_c9_stage024_causal_high_vol_pause_engine"
STAGE024_TAG = "stage024_causal_high_vol_pause_engine_v1"
STAGE024_CURVES_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_curves_{STAGE024_TAG}.csv"
STAGE024_WORST_WINDOWS_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_goal_worst_windows_{STAGE024_TAG}.csv"

TOP_WORST_ROWS = 1000
SELECTED_WINDOW_COUNT = 50
BROKER10_MULTIPLIER = 1.10

CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv.gz"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv.gz"
SELECTED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_windows_{MODEL_TAG}.csv"
WINDOW_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
WINDOW_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_bucket_detail_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
DAILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_summary_{MODEL_TAG}.csv"
VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _month_start(month: Any) -> pd.Timestamp:
    return pd.Timestamp(f"{str(month)[:7]}-01").normalize()


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def _direction_from_pos(start_pos: float, end_pos: float) -> str:
    position = start_pos if abs(start_pos) > 1e-9 else end_pos
    if position > 0:
        return "long"
    if position < 0:
        return "short"
    return "flat"


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _add_run_columns(frame: pd.DataFrame, source_start: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(_month_start(source_start))
    result["requested_start_month"] = source_start
    result["requested_end"] = _date_text(requested_end)
    return result


def _selected_windows() -> tuple[pd.DataFrame, list[str], pd.Timestamp]:
    worst = pd.read_csv(STAGE024_WORST_WINDOWS_PATH, encoding="utf-8-sig")
    worst["start_date"] = pd.to_datetime(worst["start_date"], errors="coerce").dt.normalize()
    worst["end_date"] = pd.to_datetime(worst["end_date"], errors="coerce").dt.normalize()
    worst["return_pct"] = pd.to_numeric(worst["return_pct"], errors="coerce")
    worst = worst.dropna(subset=["source_start_month", "start_date", "end_date", "return_pct"])
    top = worst.sort_values("return_pct").head(TOP_WORST_ROWS).copy()
    top["source_start_month"] = top["source_start_month"].astype(str)
    idx = top.groupby(["source_start_month", "start_date"])["return_pct"].idxmin()
    selected = top.loc[idx].sort_values("return_pct").head(SELECTED_WINDOW_COUNT).copy()
    selected.insert(0, "selected_rank", np.arange(1, len(selected) + 1))
    selected["start_date"] = pd.to_datetime(selected["start_date"], errors="coerce").dt.normalize()
    selected["end_date"] = pd.to_datetime(selected["end_date"], errors="coerce").dt.normalize()
    sources = sorted(top["source_start_month"].drop_duplicates().astype(str).tolist())
    requested_end = pd.Timestamp(top["end_date"].max()).normalize()
    return selected.reset_index(drop=True), sources, requested_end


def _prepare_curve(curve: pd.DataFrame, source: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    result = _add_run_columns(curve.copy(), source, requested_end)
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "trading_pnl",
        "holding_pnl",
        "total_pnl",
        "net_pnl",
        "account_equity",
        "c3_margin_exact",
        "c3_active_contracts",
        "c3_active_products",
        "broker10_margin_to_equity_pct",
    ]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    if "drawdown_pct" not in result.columns:
        result["drawdown_pct"] = _drawdown_pct(result["account_equity"])
    if "broker10_margin_to_equity_pct" not in result.columns:
        result["broker10_margin_to_equity_pct"] = 0.0
    return result


def _prepare_positions(positions: pd.DataFrame, source: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    result = _add_run_columns(positions.copy(), source, requested_end)
    if result.empty:
        return result
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values(["date", "vt_symbol"]).reset_index(drop=True)
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "pre_close",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "total_pnl",
        "net_pnl",
    ]:
        result[column] = pd.to_numeric(result.get(column, 0.0), errors="coerce").fillna(0.0)
    result["product"] = result["vt_symbol"].map(_product_from_vt_symbol)
    result["direction"] = result.apply(
        lambda row: _direction_from_pos(float(row["start_pos"]), float(row["end_pos"])), axis=1
    )
    return result


def _run_sources(sources: list[str], requested_end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s901.s513._metadata()
    curve_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []

    for index, source in enumerate(sources, start=1):
        start = _month_start(source)
        print(f"[stage027] running {index}/{len(sources)} source={source} end={_date_text(requested_end)}", flush=True)
        combined, frames, _spec = s024._run_live_stage024(metadata, start, requested_end)
        curve = _prepare_curve(combined, source, requested_end)
        positions = _prepare_positions(frames.get("positions", pd.DataFrame()), source, requested_end)
        curve_frames.append(curve)
        if not positions.empty:
            position_frames.append(positions)
            margin_daily, product_margin = s901.s513._position_margin(positions, metadata)
            margin_frames.append(_add_run_columns(margin_daily, source, requested_end))
            product_margin_frames.append(_add_run_columns(product_margin, source, requested_end))

    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    margin = pd.concat(margin_frames, ignore_index=True, sort=False) if margin_frames else pd.DataFrame()
    product_margin = pd.concat(product_margin_frames, ignore_index=True, sort=False) if product_margin_frames else pd.DataFrame()
    for frame in (margin, product_margin):
        if not frame.empty and "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return curves, positions, margin, product_margin


def _active_window_positions(
    positions: pd.DataFrame,
    source: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    source_positions = positions[positions["requested_start_month"].astype(str).eq(str(source))].copy()
    existing_contracts = set(
        source_positions[
            source_positions["date"].eq(start_date)
            & pd.to_numeric(source_positions["end_pos"], errors="coerce").abs().gt(1e-9)
        ]["vt_symbol"].astype(str)
    )
    window = source_positions[source_positions["date"].gt(start_date) & source_positions["date"].le(end_date)].copy()
    if window.empty:
        return window
    active = (
        window["start_pos"].abs() + window["end_pos"].abs() + window["pos_change"].abs() + window["trade_count"].abs()
    ) > 1e-9
    window = window[active].copy()
    window["source_bucket"] = np.where(
        window["vt_symbol"].astype(str).isin(existing_contracts),
        "existing_at_window_start",
        "opened_or_traded_after_window_start",
    )
    window["existing_contract_count_at_window_start"] = len(existing_contracts)
    return window


def _sum_rows(frame: pd.DataFrame, prefix: str) -> dict[str, float]:
    data = frame.copy()
    return {
        f"{prefix}_net_pnl": float(pd.to_numeric(data.get("net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()),
        f"{prefix}_holding_pnl": float(
            pd.to_numeric(data.get("holding_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()
        ),
        f"{prefix}_trading_pnl": float(
            pd.to_numeric(data.get("trading_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()
        ),
        f"{prefix}_slippage": float(
            pd.to_numeric(data.get("slippage", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()
        ),
        f"{prefix}_commission": float(
            pd.to_numeric(data.get("commission", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()
        ),
        f"{prefix}_trade_count": float(
            pd.to_numeric(data.get("trade_count", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()
        ),
    }


def _window_attribution(
    selected_windows: pd.DataFrame,
    curves: pd.DataFrame,
    positions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    bucket_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    daily_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, Any]] = []

    reference = pd.read_csv(STAGE024_CURVES_PATH, encoding="utf-8-sig")
    reference["date"] = pd.to_datetime(reference["date"], errors="coerce").dt.normalize()
    reference["account_equity"] = pd.to_numeric(reference["account_equity"], errors="coerce")

    for row in selected_windows.itertuples(index=False):
        source = str(row.source_start_month)
        start_date = pd.Timestamp(row.start_date).normalize()
        end_date = pd.Timestamp(row.end_date).normalize()
        curve = curves[curves["requested_start_month"].astype(str).eq(source)].sort_values("date").copy()
        ref = reference[reference["requested_start_month"].astype(str).eq(source)].copy()
        window_curve = curve[curve["date"].gt(start_date) & curve["date"].le(end_date)].copy()
        start_curve = curve[curve["date"].eq(start_date)]
        end_curve = curve[curve["date"].eq(end_date)]
        start_ref = ref[ref["date"].eq(start_date)]
        end_ref = ref[ref["date"].eq(end_date)]
        window_positions = _active_window_positions(positions, source, start_date, end_date)
        window_id = f"{int(row.selected_rank):03d}_{source}_{_date_text(start_date)}_{_date_text(end_date)}"
        if window_positions.empty:
            bucket = pd.DataFrame()
            product = pd.DataFrame()
            daily = pd.DataFrame()
        else:
            window_positions = window_positions.copy()
            window_positions["selected_rank"] = int(row.selected_rank)
            window_positions["window_id"] = window_id
            window_positions["window_start_date"] = start_date
            window_positions["window_end_date"] = end_date
            bucket = (
                window_positions.groupby("source_bucket", dropna=False)
                .agg(
                    net_pnl=("net_pnl", "sum"),
                    holding_pnl=("holding_pnl", "sum"),
                    trading_pnl=("trading_pnl", "sum"),
                    slippage=("slippage", "sum"),
                    commission=("commission", "sum"),
                    trade_count=("trade_count", "sum"),
                    active_days=("date", "nunique"),
                    contract_count=("vt_symbol", "nunique"),
                )
                .reset_index()
            )
            product = (
                window_positions.groupby(["product", "direction", "source_bucket"], dropna=False)
                .agg(
                    net_pnl=("net_pnl", "sum"),
                    holding_pnl=("holding_pnl", "sum"),
                    trading_pnl=("trading_pnl", "sum"),
                    slippage=("slippage", "sum"),
                    commission=("commission", "sum"),
                    trade_count=("trade_count", "sum"),
                    active_days=("date", "nunique"),
                    contract_count=("vt_symbol", "nunique"),
                    max_abs_end_pos=("end_pos", lambda s: float(pd.to_numeric(s, errors="coerce").abs().max())),
                )
                .reset_index()
            )
            daily = (
                window_positions.groupby("date", dropna=False)
                .agg(
                    net_pnl=("net_pnl", "sum"),
                    holding_pnl=("holding_pnl", "sum"),
                    trading_pnl=("trading_pnl", "sum"),
                    slippage=("slippage", "sum"),
                    commission=("commission", "sum"),
                    trade_count=("trade_count", "sum"),
                    active_contracts=("vt_symbol", "nunique"),
                )
                .reset_index()
            )
            for frame in (bucket, product, daily):
                frame["selected_rank"] = int(row.selected_rank)
                frame["window_id"] = window_id
                frame["source_start_month"] = source
                frame["window_start_date"] = start_date
                frame["window_end_date"] = end_date
            bucket_frames.append(bucket)
            product_frames.append(product)
            daily_frames.append(daily)

        curve_net = float(pd.to_numeric(window_curve.get("net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
        pos_net = float(pd.to_numeric(window_positions.get("net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
        start_equity = float(start_curve["account_equity"].iloc[0]) if not start_curve.empty else np.nan
        end_equity = float(end_curve["account_equity"].iloc[0]) if not end_curve.empty else np.nan
        reference_start_equity = float(start_ref["account_equity"].iloc[0]) if not start_ref.empty else np.nan
        reference_end_equity = float(end_ref["account_equity"].iloc[0]) if not end_ref.empty else np.nan
        equity_change = end_equity - start_equity

        validation_rows.extend(
            [
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "curve_vs_stage024_start_equity",
                    "actual": start_equity,
                    "reference": reference_start_equity,
                    "abs_diff": abs(start_equity - reference_start_equity),
                },
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "curve_vs_stage024_end_equity",
                    "actual": end_equity,
                    "reference": reference_end_equity,
                    "abs_diff": abs(end_equity - reference_end_equity),
                },
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "curve_net_pnl_vs_position_net_pnl",
                    "actual": curve_net,
                    "reference": pos_net,
                    "abs_diff": abs(curve_net - pos_net),
                },
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "equity_change_vs_curve_net_pnl",
                    "actual": equity_change,
                    "reference": curve_net,
                    "abs_diff": abs(equity_change - curve_net),
                },
            ]
        )

        existing = window_positions[window_positions["source_bucket"].eq("existing_at_window_start")]
        opened = window_positions[window_positions["source_bucket"].eq("opened_or_traded_after_window_start")]
        losses = {
            "existing": min(0.0, float(existing["net_pnl"].sum()) if not existing.empty else 0.0),
            "opened": min(0.0, float(opened["net_pnl"].sum()) if not opened.empty else 0.0),
        }
        total_loss_abs = abs(losses["existing"]) + abs(losses["opened"])
        worst_product = product.sort_values("net_pnl").iloc[0].to_dict() if not product.empty else {}
        worst_day = daily.sort_values("net_pnl").iloc[0].to_dict() if not daily.empty else {}
        start_state = start_curve.iloc[0].to_dict() if not start_curve.empty else {}
        rows.append(
            {
                "selected_rank": int(row.selected_rank),
                "window_id": window_id,
                "source_start_month": source,
                "window_start_date": start_date,
                "window_end_date": end_date,
                "period_calendar_days": int(row.period_calendar_days),
                "period_trading_days": int(row.period_trading_days),
                "stage024_return_pct": float(row.return_pct),
                "stage024_start_equity": float(row.start_equity),
                "stage024_end_equity": float(row.end_equity),
                "rerun_start_equity": start_equity,
                "rerun_end_equity": end_equity,
                "equity_change": equity_change,
                "curve_net_pnl": curve_net,
                "position_net_pnl": pos_net,
                "window_position_rows": int(len(window_positions)),
                "existing_contract_count_at_window_start": int(
                    window_positions["existing_contract_count_at_window_start"].max()
                    if not window_positions.empty
                    else 0
                ),
                **_sum_rows(window_positions, "all"),
                **_sum_rows(existing, "existing_at_start"),
                **_sum_rows(opened, "opened_after_start"),
                "existing_loss_abs": abs(losses["existing"]),
                "opened_after_start_loss_abs": abs(losses["opened"]),
                "existing_loss_share_pct": abs(losses["existing"]) / total_loss_abs * 100.0 if total_loss_abs else 0.0,
                "opened_after_start_loss_share_pct": abs(losses["opened"]) / total_loss_abs * 100.0 if total_loss_abs else 0.0,
                "start_drawdown_pct": float(start_state.get("drawdown_pct", np.nan)),
                "start_broker10_margin_to_equity_pct": float(start_state.get("broker10_margin_to_equity_pct", np.nan)),
                "start_active_products": float(start_state.get("c3_active_products", np.nan)),
                "start_active_contracts": float(start_state.get("c3_active_contracts", np.nan)),
                "window_min_equity": float(pd.to_numeric(window_curve.get("account_equity", pd.Series(dtype=float)), errors="coerce").min()),
                "window_min_drawdown_pct": float(pd.to_numeric(window_curve.get("drawdown_pct", pd.Series(dtype=float)), errors="coerce").min()),
                "window_max_broker10_margin_to_equity_pct": float(
                    pd.to_numeric(window_curve.get("broker10_margin_to_equity_pct", pd.Series(dtype=float)), errors="coerce").max()
                ),
                "worst_day": _json_safe(worst_day.get("date", "")),
                "worst_day_net_pnl": float(worst_day.get("net_pnl", np.nan)),
                "worst_product": str(worst_product.get("product", "")),
                "worst_product_direction": str(worst_product.get("direction", "")),
                "worst_product_bucket": str(worst_product.get("source_bucket", "")),
                "worst_product_net_pnl": float(worst_product.get("net_pnl", np.nan)),
            }
        )

    window_attribution = pd.DataFrame(rows)
    bucket_detail = pd.concat(bucket_frames, ignore_index=True, sort=False) if bucket_frames else pd.DataFrame()
    product_detail = pd.concat(product_frames, ignore_index=True, sort=False) if product_frames else pd.DataFrame()
    daily_detail = pd.concat(daily_frames, ignore_index=True, sort=False) if daily_frames else pd.DataFrame()
    validation = pd.DataFrame(validation_rows)
    return window_attribution, bucket_detail, product_detail, daily_detail, validation


def _summaries(
    window_attribution: pd.DataFrame,
    bucket_detail: pd.DataFrame,
    product_detail: pd.DataFrame,
    daily_detail: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_bucket = (
        bucket_detail.groupby("source_bucket", dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            window_count=("window_id", "nunique"),
            source_count=("source_start_month", "nunique"),
            active_days=("active_days", "sum"),
            contract_count=("contract_count", "sum"),
        )
        .reset_index()
        .sort_values("net_pnl")
        if not bucket_detail.empty
        else pd.DataFrame()
    )
    product = (
        product_detail.groupby(["product", "direction", "source_bucket"], dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            window_count=("window_id", "nunique"),
            source_count=("source_start_month", "nunique"),
            active_days=("active_days", "sum"),
            contract_count=("contract_count", "sum"),
            max_abs_end_pos=("max_abs_end_pos", "max"),
        )
        .reset_index()
        .sort_values("net_pnl")
        if not product_detail.empty
        else pd.DataFrame()
    )
    daily = (
        daily_detail.groupby("date", dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            window_count=("window_id", "nunique"),
            source_count=("source_start_month", "nunique"),
            active_contracts=("active_contracts", "sum"),
        )
        .reset_index()
        .sort_values("net_pnl")
        if not daily_detail.empty
        else pd.DataFrame()
    )
    for frame in (source_bucket, product, daily):
        if not frame.empty and "net_pnl" in frame.columns:
            frame["holding_share_of_net_pct"] = np.where(
                pd.to_numeric(frame["net_pnl"], errors="coerce").abs().gt(1e-9),
                pd.to_numeric(frame["holding_pnl"], errors="coerce") / pd.to_numeric(frame["net_pnl"], errors="coerce") * 100.0,
                np.nan,
            )
    return source_bucket, product, daily


def _plot(
    window_attribution: pd.DataFrame,
    source_bucket: pd.DataFrame,
    product: pd.DataFrame,
    daily: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    ax = axes[0, 0]
    if not window_attribution.empty:
        plot = window_attribution.sort_values("selected_rank")
        ax.bar(plot["selected_rank"], plot["stage024_return_pct"], color="#dc2626")
    ax.axhline(0, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Selected Stage024 Worst Windows")
    ax.set_xlabel("selected rank")
    ax.set_ylabel("return %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    if not source_bucket.empty:
        plot = source_bucket.sort_values("net_pnl")
        ax.barh(plot["source_bucket"], plot["net_pnl"], color=np.where(plot["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("Aggregated PnL By Position Source Bucket")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 0]
    if not product.empty:
        plot = product.head(16).copy()
        plot["label"] = plot["product"].astype(str) + " " + plot["direction"].astype(str) + "\n" + plot["source_bucket"].astype(str)
        ax.barh(plot["label"], plot["net_pnl"], color=np.where(plot["net_pnl"].ge(0), "#16a34a", "#dc2626"))
        ax.invert_yaxis()
    ax.set_title("Worst Product/Direction Contributions")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 1]
    if not validation.empty:
        check = validation.groupby("check_type", as_index=False).agg(max_abs_diff=("abs_diff", "max"))
        ax.barh(check["check_type"], check["max_abs_diff"], color="#7c3aed")
    ax.set_title("Validation Max Abs Diff")
    ax.set_xlabel("abs diff")
    ax.grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    validation: pd.DataFrame,
    window_attribution: pd.DataFrame,
    source_bucket: pd.DataFrame,
    product: pd.DataFrame,
    daily: pd.DataFrame,
) -> None:
    report = f"""# Stage027 Stage024 剩余 worst-window 持仓路径归因

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 阶段性质：只读归因；不改策略、不扫参数、不连接 CTP、不调用下单。
- 选择口径：Stage024 `goal_worst_windows` 前 `{TOP_WORST_ROWS}` 行，按 `source + start_date` 去重后取最差 `{SELECTED_WINDOW_COUNT}` 个代表窗口。

## 外部调研判断

- 趋势跟随研究强调右尾、分散化和波动/仓位控制，不能从单一失败窗口反推产品黑名单。
- PBO/回测过拟合框架提醒多次试参会制造虚假发现；本阶段只做路径归因，为后续预声明候选提供证据。

## 核心结果

- 代表窗口：`{decision['selected_window_count']}`
- 重放 source：`{decision['source_count']}`
- 最大一致性误差：`{decision['max_validation_abs_diff']:.6f}`
- 窗口聚合净 PnL：`{decision['selected_total_net_pnl']:,.2f}`
- 窗口聚合 holding PnL：`{decision['selected_total_holding_pnl']:,.2f}`
- 窗口聚合 trading PnL：`{decision['selected_total_trading_pnl']:,.2f}`
- 已有仓位亏损占比：`{decision['existing_loss_share_pct']:.2f}%`
- 窗口后新开/交易仓位亏损占比：`{decision['opened_after_start_loss_share_pct']:.2f}%`
- 决策：`{decision['decision']}`

## 一致性校验

{_md_table(validation.groupby("check_type", as_index=False).agg(max_abs_diff=("abs_diff", "max")), max_rows=20)}

## 代表窗口归因

{_md_table(window_attribution.head(30), max_rows=30)}

## 仓位来源分桶

{_md_table(source_bucket, max_rows=20)}

## 品种方向聚合

{_md_table(product.head(40), max_rows=40)}

## 最大亏损日聚合

{_md_table(daily.head(30), max_rows=30)}

## 判断

- 核心归因：{decision['core_attribution']}
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

"""
    for key, path in decision["outputs"].items():
        report += f"- {key}: `{path}`\n"
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage027_remaining_worst_window_position_attribution.md"
    content = f"""# Stage027 - Stage024 剩余 worst-window 持仓路径归因

## 变更时间

- {decision['generated_at']} CST

## 是否重要突破版本

- 否。只读归因，不是真实引擎候选，不改线上。

## 本次版本改动内容

- 新增工具：`research/lines/{LINE_ID}/tools/stage027_remaining_worst_window_position_attribution.py`
- 从 Stage024 top `{TOP_WORST_ROWS}` worst windows 中抽取 `{SELECTED_WINDOW_COUNT}` 个代表窗口。
- 用 Stage024 真实引擎重放相关 source 到 `{decision['requested_end']}`，输出 positions 并做窗口级 PnL 闭合校验。
- 将窗口损失拆成 `existing_at_window_start` 与 `opened_or_traded_after_window_start`。

## 新增参数

- `TOP_WORST_ROWS={TOP_WORST_ROWS}`
- `SELECTED_WINDOW_COUNT={SELECTED_WINDOW_COUNT}`

## 修改参数

- 无。

## 删除参数

- 无。

## 新增回测结果

- 代表窗口：`{decision['selected_window_count']}`
- 重放 source：`{decision['source_count']}`
- 最大一致性误差：`{decision['max_validation_abs_diff']:.6f}`
- 窗口聚合净 PnL：`{decision['selected_total_net_pnl']:,.2f}`
- 窗口聚合 holding PnL：`{decision['selected_total_holding_pnl']:,.2f}`
- 窗口聚合 trading PnL：`{decision['selected_total_trading_pnl']:,.2f}`
- 已有仓位亏损占比：`{decision['existing_loss_share_pct']:.2f}%`
- 窗口后新开/交易仓位亏损占比：`{decision['opened_after_start_loss_share_pct']:.2f}%`
- 决策：`{decision['decision']}`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 指标占位

- 期末权益：只读归因，不适用。
- 总收益：只读归因，不适用。
- 最大回撤：只读归因，不适用。
- Sharpe：只读归因，不适用。
- 总滑点：`{decision['selected_total_slippage']:,.2f}`
- 总交易次数：`{decision['selected_total_trade_count']:,.0f}`
- 胜率：不新增交易，不适用。

## 调研与判断结论

- 外部资料判断：趋势跟随左尾治理应优先看仓位路径、风险预算和分散化，不应从单窗口回测 winner-picking。
- 本阶段判断：`{decision['decision']}`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。本阶段只做 representative worst-window 路径归因，不写规则。
- 运行前是否有价值继续：有。Stage024 仍有 `298,012` 个严格负窗口，必须确认剩余损失来自已有仓位还是新增仓位。
- 运行后是否过拟合：{decision['overfit_reflection_after']}
- 运行后是否有价值继续：{decision['continue_value_after']}

## 后续规划和 TODO

- 若损失由窗口后新开/交易仓位主导，下一步应研究账户状态下的风险释放顺序，而不是 hard regime gate。
- 若损失由已有仓位主导，下一步应研究持仓期减风险或退出纪律，但必须避免切断趋势右尾。
- 不得把最差品种/方向直接做成黑名单。

## 输出文件

- `{REPORT_PATH}`
- `{DECISION_PATH}`
- `{CHART_PATH}`
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    selected_windows, sources, requested_end = _selected_windows()
    curves, positions, margin, product_margin = _run_sources(sources, requested_end)
    window_attribution, bucket_detail, product_detail, daily_detail, validation = _window_attribution(
        selected_windows, curves, positions
    )
    source_bucket, product_summary, daily_summary = _summaries(
        window_attribution, bucket_detail, product_detail, daily_detail
    )
    _plot(window_attribution, source_bucket, product_summary, daily_summary, validation)

    selected_windows.to_csv(SELECTED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    margin.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    window_attribution.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    bucket_detail.to_csv(WINDOW_BUCKET_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(DAILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")

    max_validation_diff = float(pd.to_numeric(validation["abs_diff"], errors="coerce").max()) if not validation.empty else np.nan
    selected_total_net = float(pd.to_numeric(window_attribution["all_net_pnl"], errors="coerce").sum())
    selected_total_holding = float(pd.to_numeric(window_attribution["all_holding_pnl"], errors="coerce").sum())
    selected_total_trading = float(pd.to_numeric(window_attribution["all_trading_pnl"], errors="coerce").sum())
    selected_total_slippage = float(pd.to_numeric(window_attribution["all_slippage"], errors="coerce").sum())
    selected_total_trade_count = float(pd.to_numeric(window_attribution["all_trade_count"], errors="coerce").sum())
    existing_loss = float(pd.to_numeric(window_attribution["existing_loss_abs"], errors="coerce").sum())
    opened_loss = float(pd.to_numeric(window_attribution["opened_after_start_loss_abs"], errors="coerce").sum())
    total_loss = existing_loss + opened_loss
    existing_share = existing_loss / total_loss * 100.0 if total_loss else 0.0
    opened_share = opened_loss / total_loss * 100.0 if total_loss else 0.0
    holding_share = selected_total_holding / selected_total_net * 100.0 if abs(selected_total_net) > 1e-9 else np.nan
    worst_product = product_summary.iloc[0].to_dict() if not product_summary.empty else {}
    worst_day = daily_summary.iloc[0].to_dict() if not daily_summary.empty else {}

    if max_validation_diff > 1e-6:
        decision_label = "stage027_validation_warning_do_not_use_for_strategy"
    elif opened_share >= 60.0:
        decision_label = "stage027_left_tail_dominated_by_new_or_traded_positions"
    elif existing_share >= 60.0:
        decision_label = "stage027_left_tail_dominated_by_existing_positions"
    else:
        decision_label = "stage027_left_tail_mixed_existing_and_new_positions"

    core_attribution = (
        f"代表窗口聚合净 PnL {selected_total_net:,.2f}，其中 holding PnL {selected_total_holding:,.2f} "
        f"({holding_share:.2f}% of net)，trading PnL {selected_total_trading:,.2f}；"
        f"已有仓位亏损占比 {existing_share:.2f}%，窗口后新开/交易仓位亏损占比 {opened_share:.2f}%。"
        f"最大品种方向拖累为 {worst_product.get('product', 'NA')} {worst_product.get('direction', 'NA')} "
        f"{worst_product.get('source_bucket', 'NA')}，net_pnl={float(worst_product.get('net_pnl', np.nan)):,.2f}；"
        f"最大聚合亏损日为 {worst_day.get('date', 'NA')}，net_pnl={float(worst_day.get('net_pnl', np.nan)):,.2f}。"
    )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage024_remaining_worst_window_position_path_attribution",
        "requested_end": _date_text(requested_end),
        "top_worst_rows": TOP_WORST_ROWS,
        "selected_window_count": int(len(selected_windows)),
        "source_count": int(len(sources)),
        "curve_rows": int(len(curves)),
        "position_rows": int(len(positions)),
        "max_validation_abs_diff": max_validation_diff,
        "selected_total_net_pnl": selected_total_net,
        "selected_total_holding_pnl": selected_total_holding,
        "selected_total_trading_pnl": selected_total_trading,
        "selected_total_slippage": selected_total_slippage,
        "selected_total_trade_count": selected_total_trade_count,
        "holding_share_of_net_pct": holding_share,
        "existing_loss_abs": existing_loss,
        "opened_after_start_loss_abs": opened_loss,
        "existing_loss_share_pct": existing_share,
        "opened_after_start_loss_share_pct": opened_share,
        "worst_product_direction": _json_safe(worst_product),
        "worst_day": _json_safe(worst_day),
        "decision": decision_label,
        "strategy_changed": False,
        "true_engine": False,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following and PBO references support path attribution before candidate design; "
            "this stage avoids product/date blacklists and parameter search."
        ),
        "overfit_reflection_before": (
            "否。Stage027 只抽取代表失败窗口并做持仓路径闭合，不写交易规则。"
        ),
        "continue_value_before": (
            "有。Stage024 仍未达到任意 >1 年正收益目标，需要定位剩余左尾来自已有仓位还是新增仓位。"
        ),
        "core_attribution": core_attribution,
        "overfit_reflection_after": (
            "否。本阶段没有按品种、方向、日期或阈值拟合规则；最差品种只作为归因证据。"
        ),
        "continue_value_after": (
            "有。归因可以把下一步从 hard regime gate 转向账户状态下的新开仓风险释放顺序；"
            "但真实候选仍必须预声明并做多起点严格窗口验证。"
        ),
        "outputs": {
            "selected_windows": str(SELECTED_WINDOWS_PATH),
            "curves": str(CURVES_PATH),
            "positions": str(POSITIONS_PATH),
            "margin_daily": str(MARGIN_DAILY_PATH),
            "product_margin": str(PRODUCT_MARGIN_PATH),
            "window_attribution": str(WINDOW_ATTRIBUTION_PATH),
            "window_bucket_detail": str(WINDOW_BUCKET_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "daily_summary": str(DAILY_SUMMARY_PATH),
            "validation": str(VALIDATION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, validation, window_attribution, source_bucket, product_summary, daily_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("source_bucket")
    print(source_bucket.to_string(index=False))
    print("product_direction")
    print(product_summary.head(30).to_string(index=False))
    print("daily")
    print(daily_summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
