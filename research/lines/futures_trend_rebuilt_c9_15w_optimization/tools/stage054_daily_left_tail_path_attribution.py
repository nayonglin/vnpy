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

import stage013_account_state_pilot_gate_engine as s013
import stage041_selected_daily_cold_start_probe as s041
import stage053_contract_oi_share_daily_probe as s053

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage054"
MODEL_TAG = "stage054_daily_left_tail_path_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage054_daily_left_tail_path_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage054_daily_left_tail_path_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE053_OUTPUT_DIR = LINE_DIR / "outputs" / "stage053_contract_oi_share_daily_probe"
STAGE053_PREFIX = "rebuilt_c9_stage053_contract_oi_share_daily_probe"
STAGE053_TAG = "stage053_contract_oi_share_daily_probe_v1"
STAGE053_SUMMARY_PATH = STAGE053_OUTPUT_DIR / f"{STAGE053_PREFIX}_summary_{STAGE053_TAG}.csv"
STAGE053_CURVES_PATH = STAGE053_OUTPUT_DIR / f"{STAGE053_PREFIX}_curves_{STAGE053_TAG}.csv"

TOP_N_PER_VARIANT = 8

SELECTED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_windows_{MODEL_TAG}.csv"
RERUN_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rerun_curves_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv.gz"
CURVE_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_window_attribution_{MODEL_TAG}.csv"
BUCKET_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_detail_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
DAILY_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_detail_{MODEL_TAG}.csv"
VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

VARIANT_CONFIG = {
    "stage013_daily_cold_start_engine": {
        "label": "Stage013 base",
        "equity_column": "account_equity",
        "drawdown_column": "drawdown_pct",
        "delta_column": None,
    },
    "stage053_daily_cold_start_contract_oi_share_proxy": {
        "label": "Stage053 contract OI share proxy",
        "equity_column": "stage053_account_equity",
        "drawdown_column": "stage053_drawdown_pct",
        "delta_column": "stage053_daily_delta",
    },
}


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _date_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _to_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


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


def select_worst_windows_from_stage053_summary(
    summary: pd.DataFrame,
    top_n_per_variant: int = TOP_N_PER_VARIANT,
) -> pd.DataFrame:
    data = summary.copy()
    for column in ["requested_start", "actual_start", "worst_end_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    data["min_return_pct"] = pd.to_numeric(data["min_return_pct"], errors="coerce")
    data["to_final_return_pct"] = pd.to_numeric(data.get("to_final_return_pct"), errors="coerce")
    data = data.dropna(subset=["requested_start", "actual_start", "worst_end_date", "min_return_pct"])

    rows: list[pd.DataFrame] = []
    for variant in VARIANT_CONFIG:
        selected = data[data["variant"].eq(variant)].sort_values("min_return_pct").head(int(top_n_per_variant)).copy()
        if selected.empty:
            continue
        selected["selected_rank_in_variant"] = np.arange(1, len(selected) + 1)
        rows.append(selected)
    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True, sort=False)
    result.insert(0, "selected_rank", np.arange(1, len(result) + 1))
    result["requested_start"] = result["requested_start"].map(_date_key)
    result["window_start_date"] = pd.to_datetime(result["actual_start"], errors="coerce").dt.normalize()
    result["window_end_date"] = pd.to_datetime(result["worst_end_date"], errors="coerce").dt.normalize()
    result["window_return_pct"] = pd.to_numeric(result["min_return_pct"], errors="coerce")
    result["period_calendar_days"] = (result["window_end_date"] - result["window_start_date"]).dt.days
    keep = [
        "selected_rank",
        "selected_rank_in_variant",
        "requested_start",
        "variant",
        "window_start_date",
        "window_end_date",
        "period_calendar_days",
        "window_return_pct",
        "to_final_return_pct",
        "probe_bucket",
        "source_variant",
        "source_start_month",
        "source_return_pct",
    ]
    return result[[column for column in keep if column in result.columns]].reset_index(drop=True)


def _filter_source_frame(frame: pd.DataFrame, requested_start: str) -> pd.DataFrame:
    data = frame.copy()
    if "date" in data.columns:
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    source_key = str(requested_start)
    masks: list[pd.Series] = []
    for column in ["requested_start", "requested_start_month"]:
        if column in data.columns:
            masks.append(data[column].astype(str).eq(source_key))
    if not masks:
        return data.iloc[0:0].copy()
    mask = masks[0]
    for extra in masks[1:]:
        mask = mask | extra
    return data[mask].copy()


def summarize_curve_window(
    curves: pd.DataFrame,
    *,
    requested_start: str,
    variant: str,
    window_start_date: pd.Timestamp,
    window_end_date: pd.Timestamp,
) -> dict[str, Any]:
    config = VARIANT_CONFIG[variant]
    equity_column = str(config["equity_column"])
    drawdown_column = str(config["drawdown_column"])
    delta_column = config["delta_column"]

    source_curve = _filter_source_frame(curves, requested_start).sort_values("date").copy()
    start_date = pd.Timestamp(window_start_date).normalize()
    end_date = pd.Timestamp(window_end_date).normalize()
    window = source_curve[source_curve["date"].gt(start_date) & source_curve["date"].le(end_date)].copy()
    start_row = source_curve[source_curve["date"].eq(start_date)]
    end_row = source_curve[source_curve["date"].eq(end_date)]

    for column in [
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "trade_count",
        "turnover",
        "broker10_margin_to_equity_pct",
        equity_column,
        drawdown_column,
    ]:
        if column in source_curve.columns:
            source_curve[column] = pd.to_numeric(source_curve[column], errors="coerce")
        if column in window.columns:
            window[column] = pd.to_numeric(window[column], errors="coerce")

    if delta_column:
        stage053_delta = float(_to_numeric(window, str(delta_column), 0.0).sum())
    else:
        stage053_delta = 0.0
    window_effect = _to_numeric(window, "net_pnl", 0.0) + (
        _to_numeric(window, str(delta_column), 0.0) if delta_column else 0.0
    )
    worst_day = ""
    worst_day_effect = np.nan
    if len(window_effect) > 0:
        idx = window_effect.idxmin()
        worst_day = _date_key(window.loc[idx, "date"])
        worst_day_effect = float(window_effect.loc[idx])

    start_equity = float(pd.to_numeric(start_row[equity_column], errors="coerce").iloc[0]) if not start_row.empty else np.nan
    end_equity = float(pd.to_numeric(end_row[equity_column], errors="coerce").iloc[0]) if not end_row.empty else np.nan
    curve_net = float(_to_numeric(window, "net_pnl", 0.0).sum())
    curve_effect = curve_net + stage053_delta
    equity_change = end_equity - start_equity if pd.notna(start_equity) and pd.notna(end_equity) else np.nan

    return {
        "requested_start": str(requested_start),
        "variant": variant,
        "variant_label": config["label"],
        "window_start_date": start_date,
        "window_end_date": end_date,
        "period_calendar_days": int((end_date - start_date).days),
        "period_trading_days": int(len(window)),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "equity_change": equity_change,
        "curve_net_pnl": curve_net,
        "curve_holding_pnl": float(_to_numeric(window, "holding_pnl", 0.0).sum()),
        "curve_trading_pnl": float(_to_numeric(window, "trading_pnl", 0.0).sum()),
        "curve_commission": float(_to_numeric(window, "commission", 0.0).sum()),
        "curve_slippage": float(_to_numeric(window, "slippage", 0.0).sum()),
        "curve_trade_count": float(_to_numeric(window, "trade_count", 0.0).sum()),
        "stage053_delta_pnl": stage053_delta,
        "curve_net_plus_stage053_delta": curve_effect,
        "equity_change_vs_curve_effect_abs_diff": abs(equity_change - curve_effect)
        if pd.notna(equity_change)
        else np.nan,
        "window_min_equity": float(_to_numeric(window, equity_column, np.nan).min()) if not window.empty else np.nan,
        "window_min_drawdown_pct": float(_to_numeric(window, drawdown_column, np.nan).min()) if not window.empty else np.nan,
        "window_max_broker10_margin_to_equity_pct": float(
            _to_numeric(window, "broker10_margin_to_equity_pct", np.nan).max()
        )
        if not window.empty
        else np.nan,
        "worst_day": worst_day,
        "worst_day_effect_pnl": worst_day_effect,
    }


def _prepare_curve(curve: pd.DataFrame, requested_start: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    result = curve.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = str(requested_start)
    result["requested_start_month"] = str(requested_start)
    result["requested_end"] = _date_key(requested_end)
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
    if "drawdown_pct" not in result.columns and "account_equity" in result.columns:
        result["drawdown_pct"] = _drawdown_pct(result["account_equity"])
    if "broker10_margin_to_equity_pct" not in result.columns:
        result["broker10_margin_to_equity_pct"] = 0.0
    return result


def _prepare_positions(positions: pd.DataFrame, requested_start: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    result = positions.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = str(requested_start)
    result["requested_start_month"] = str(requested_start)
    result["requested_end"] = _date_key(requested_end)
    if result.empty:
        return result
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values(["date", "vt_symbol"]).reset_index(drop=True)
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
        "total_pnl",
        "net_pnl",
    ]:
        result[column] = pd.to_numeric(result.get(column, 0.0), errors="coerce").fillna(0.0)
    result["product"] = result["vt_symbol"].map(_product_from_vt_symbol)
    result["direction"] = result.apply(
        lambda row: _direction_from_pos(float(row["start_pos"]), float(row["end_pos"])), axis=1
    )
    return result


def classify_window_positions(
    positions: pd.DataFrame,
    *,
    requested_start: str,
    window_start_date: pd.Timestamp,
    window_end_date: pd.Timestamp,
) -> pd.DataFrame:
    source_positions = _filter_source_frame(positions, requested_start).copy()
    if source_positions.empty:
        return source_positions
    source_positions["date"] = pd.to_datetime(source_positions["date"], errors="coerce").dt.normalize()
    start_date = pd.Timestamp(window_start_date).normalize()
    end_date = pd.Timestamp(window_end_date).normalize()
    for column in ["start_pos", "end_pos", "pos_change", "trade_count"]:
        source_positions[column] = pd.to_numeric(source_positions.get(column, 0.0), errors="coerce").fillna(0.0)
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
    if "product" not in window.columns:
        window["product"] = window["vt_symbol"].map(_product_from_vt_symbol)
    if "direction" not in window.columns:
        window["direction"] = window.apply(
            lambda row: _direction_from_pos(float(row["start_pos"]), float(row["end_pos"])), axis=1
        )
    return window


def _sum_rows(frame: pd.DataFrame, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_net_pnl": float(_to_numeric(frame, "net_pnl", 0.0).sum()),
        f"{prefix}_holding_pnl": float(_to_numeric(frame, "holding_pnl", 0.0).sum()),
        f"{prefix}_trading_pnl": float(_to_numeric(frame, "trading_pnl", 0.0).sum()),
        f"{prefix}_slippage": float(_to_numeric(frame, "slippage", 0.0).sum()),
        f"{prefix}_commission": float(_to_numeric(frame, "commission", 0.0).sum()),
        f"{prefix}_trade_count": float(_to_numeric(frame, "trade_count", 0.0).sum()),
    }


def _run_position_sources(selected_windows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s013.s901.s513._metadata()
    requested_end_by_start = (
        selected_windows.groupby("requested_start", dropna=False)["window_end_date"].max().sort_index().to_dict()
    )
    curve_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for index, (requested_start, requested_end) in enumerate(requested_end_by_start.items(), start=1):
        start = pd.Timestamp(requested_start).normalize()
        end = pd.Timestamp(requested_end).normalize()
        print(
            f"[stage054] rerun Stage013 positions {index}/{len(requested_end_by_start)} "
            f"start={_date_key(start)} end={_date_key(end)}",
            flush=True,
        )
        combined, frames, _spec = s013._run_live_stage013(metadata, start, end)
        curve_frames.append(_prepare_curve(combined, _date_key(start), end))
        positions = _prepare_positions(frames.get("positions", pd.DataFrame()), _date_key(start), end)
        if not positions.empty:
            position_frames.append(positions)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    return curves, positions


def _build_attribution(
    selected_windows: pd.DataFrame,
    stage053_curves: pd.DataFrame,
    rerun_curves: pd.DataFrame,
    positions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    curve_rows: list[dict[str, Any]] = []
    bucket_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    daily_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, Any]] = []

    for row in selected_windows.itertuples(index=False):
        requested_start = str(row.requested_start)
        variant = str(row.variant)
        start_date = pd.Timestamp(row.window_start_date).normalize()
        end_date = pd.Timestamp(row.window_end_date).normalize()
        window_id = f"{int(row.selected_rank):03d}_{variant}_{requested_start}_{_date_key(end_date)}"

        curve_row = summarize_curve_window(
            stage053_curves,
            requested_start=requested_start,
            variant=variant,
            window_start_date=start_date,
            window_end_date=end_date,
        )
        curve_row.update(
            {
                "selected_rank": int(row.selected_rank),
                "selected_rank_in_variant": int(row.selected_rank_in_variant),
                "window_id": window_id,
                "stage053_summary_return_pct": float(row.window_return_pct),
            }
        )

        base_curve_row = summarize_curve_window(
            stage053_curves,
            requested_start=requested_start,
            variant="stage013_daily_cold_start_engine",
            window_start_date=start_date,
            window_end_date=end_date,
        )
        rerun_base_curve_row = summarize_curve_window(
            rerun_curves,
            requested_start=requested_start,
            variant="stage013_daily_cold_start_engine",
            window_start_date=start_date,
            window_end_date=end_date,
        )
        validation_rows.extend(
            [
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "stage053_summary_return_vs_curve_return",
                    "actual": (curve_row["equity_change"] / curve_row["start_equity"] * 100.0)
                    if curve_row["start_equity"]
                    else np.nan,
                    "reference": float(row.window_return_pct),
                    "abs_diff": abs(
                        (curve_row["equity_change"] / curve_row["start_equity"] * 100.0) - float(row.window_return_pct)
                    )
                    if curve_row["start_equity"]
                    else np.nan,
                },
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "stage013_original_curve_vs_rerun_end_equity",
                    "actual": rerun_base_curve_row["end_equity"],
                    "reference": base_curve_row["end_equity"],
                    "abs_diff": abs(rerun_base_curve_row["end_equity"] - base_curve_row["end_equity"]),
                },
                {
                    "selected_rank": int(row.selected_rank),
                    "window_id": window_id,
                    "check_type": "stage013_original_curve_vs_rerun_curve_net_pnl",
                    "actual": rerun_base_curve_row["curve_net_pnl"],
                    "reference": base_curve_row["curve_net_pnl"],
                    "abs_diff": abs(rerun_base_curve_row["curve_net_pnl"] - base_curve_row["curve_net_pnl"]),
                },
            ]
        )

        window_positions = classify_window_positions(
            positions,
            requested_start=requested_start,
            window_start_date=start_date,
            window_end_date=end_date,
        )
        if not window_positions.empty:
            window_positions = window_positions.copy()
            window_positions["selected_rank"] = int(row.selected_rank)
            window_positions["window_id"] = window_id
            window_positions["variant"] = variant
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
                frame["variant"] = variant
                frame["requested_start"] = requested_start
                frame["window_start_date"] = start_date
                frame["window_end_date"] = end_date
            bucket_frames.append(bucket)
            product_frames.append(product)
            daily_frames.append(daily)

        existing = window_positions[window_positions["source_bucket"].eq("existing_at_window_start")]
        opened = window_positions[window_positions["source_bucket"].eq("opened_or_traded_after_window_start")]
        existing_loss = abs(min(0.0, float(_to_numeric(existing, "net_pnl", 0.0).sum())))
        opened_loss = abs(min(0.0, float(_to_numeric(opened, "net_pnl", 0.0).sum())))
        total_loss = existing_loss + opened_loss
        pos_net = float(_to_numeric(window_positions, "net_pnl", 0.0).sum())
        curve_row.update(
            {
                "position_net_pnl": pos_net,
                "position_vs_stage013_curve_net_pnl_abs_diff": abs(pos_net - base_curve_row["curve_net_pnl"]),
                "position_rows": int(len(window_positions)),
                "existing_contract_count_at_window_start": int(
                    window_positions["existing_contract_count_at_window_start"].max()
                    if not window_positions.empty
                    else 0
                ),
                **_sum_rows(window_positions, "all_positions"),
                **_sum_rows(existing, "existing_at_start"),
                **_sum_rows(opened, "opened_after_start"),
                "existing_loss_abs": existing_loss,
                "opened_after_start_loss_abs": opened_loss,
                "existing_loss_share_pct": existing_loss / total_loss * 100.0 if total_loss else 0.0,
                "opened_after_start_loss_share_pct": opened_loss / total_loss * 100.0 if total_loss else 0.0,
            }
        )
        curve_rows.append(curve_row)

    curve_attribution = pd.DataFrame(curve_rows)
    bucket_detail = pd.concat(bucket_frames, ignore_index=True, sort=False) if bucket_frames else pd.DataFrame()
    product_detail = pd.concat(product_frames, ignore_index=True, sort=False) if product_frames else pd.DataFrame()
    daily_detail = pd.concat(daily_frames, ignore_index=True, sort=False) if daily_frames else pd.DataFrame()
    validation = pd.DataFrame(validation_rows)
    return curve_attribution, bucket_detail, product_detail, daily_detail, validation


def _summaries(
    bucket_detail: pd.DataFrame,
    product_detail: pd.DataFrame,
    daily_detail: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bucket = (
        bucket_detail.groupby(["variant", "source_bucket"], dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            window_count=("window_id", "nunique"),
            source_count=("requested_start", "nunique"),
            active_days=("active_days", "sum"),
            contract_count=("contract_count", "sum"),
        )
        .reset_index()
        .sort_values(["variant", "net_pnl"])
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
            source_count=("requested_start", "nunique"),
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
            source_count=("requested_start", "nunique"),
            active_contracts=("active_contracts", "sum"),
        )
        .reset_index()
        .sort_values("net_pnl")
        if not daily_detail.empty
        else pd.DataFrame()
    )
    return bucket, product, daily


def _plot(curve_attribution: pd.DataFrame, bucket: pd.DataFrame, product: pd.DataFrame, daily: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    ax = axes[0, 0]
    if not curve_attribution.empty:
        plot = curve_attribution.sort_values(["variant", "selected_rank_in_variant"])
        colors = np.where(
            plot["variant"].eq("stage053_daily_cold_start_contract_oi_share_proxy"),
            "#c2410c",
            "#2563eb",
        )
        ax.bar(range(len(plot)), plot["equity_change"], color=colors)
        ax.set_xticks(range(len(plot)))
        ax.set_xticklabels(plot["requested_start"].astype(str), rotation=75, ha="right")
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_title("Selected worst windows equity change")
    ax.set_ylabel("PnL")

    ax = axes[0, 1]
    if not curve_attribution.empty:
        plot = curve_attribution.sort_values("opened_after_start_loss_share_pct", ascending=False)
        ax.bar(
            range(len(plot)),
            plot["opened_after_start_loss_share_pct"],
            color="#dc2626",
            label="opened after start",
        )
        ax.bar(
            range(len(plot)),
            plot["existing_loss_share_pct"],
            bottom=plot["opened_after_start_loss_share_pct"],
            color="#64748b",
            label="existing at start",
        )
        ax.set_xticks(range(len(plot)))
        ax.set_xticklabels(plot["requested_start"].astype(str), rotation=75, ha="right")
        ax.legend()
    ax.set_title("Loss attribution share")
    ax.set_ylabel("% of negative position PnL")

    ax = axes[1, 0]
    if not product.empty:
        plot = product.sort_values("net_pnl").head(15)
        labels = plot["product"].astype(str) + " " + plot["direction"].astype(str) + " " + plot["source_bucket"].astype(str)
        ax.barh(range(len(plot)), plot["net_pnl"], color="#9333ea")
        ax.set_yticks(range(len(plot)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
    ax.set_title("Worst product / direction buckets")
    ax.set_xlabel("PnL")

    ax = axes[1, 1]
    if not daily.empty:
        plot = daily.sort_values("net_pnl").head(30).sort_values("date")
        ax.plot(pd.to_datetime(plot["date"]), plot["net_pnl"], marker="o", color="#0f766e")
        ax.tick_params(axis="x", rotation=45)
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_title("Worst daily position PnL dates")
    ax.set_ylabel("PnL")

    fig.suptitle("Stage054 daily left-tail path attribution", fontsize=16)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _decision(
    selected_windows: pd.DataFrame,
    curve_attribution: pd.DataFrame,
    bucket: pd.DataFrame,
    product: pd.DataFrame,
    validation: pd.DataFrame,
) -> dict[str, Any]:
    opened_loss = float(pd.to_numeric(curve_attribution.get("opened_after_start_loss_abs"), errors="coerce").sum())
    existing_loss = float(pd.to_numeric(curve_attribution.get("existing_loss_abs"), errors="coerce").sum())
    total_loss = opened_loss + existing_loss
    opened_share = opened_loss / total_loss * 100.0 if total_loss else 0.0
    existing_share = existing_loss / total_loss * 100.0 if total_loss else 0.0
    worst_product = product.sort_values("net_pnl").head(1).to_dict("records")[0] if not product.empty else {}
    max_validation_abs_diff = (
        float(pd.to_numeric(validation.get("abs_diff"), errors="coerce").fillna(0.0).max()) if not validation.empty else 0.0
    )
    if opened_share >= 60.0:
        decision = "stage054_left_tail_mainly_opened_after_start_risk_budget_problem"
        continue_after = (
            "有。左尾更像窗口后新增风险暴露问题，下一步应做因果风险预算/信号质量过滤，而不是调已有持仓的止损。"
        )
    elif existing_share >= 60.0:
        decision = "stage054_left_tail_mainly_existing_position_carry_problem"
        continue_after = "有。左尾更像窗口起点已有仓位承压，下一步应审计入场前状态、持仓迁移和账户层降风险。"
    else:
        decision = "stage054_left_tail_mixed_path_need_deeper_trade_lot_attribution"
        continue_after = "有但需继续拆 lot。新增仓与既有仓都贡献亏损，下一步应按真实开仓事件和月度 AI 池切片。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "read_only_daily_left_tail_path_attribution_from_stage053_worst_windows",
        "selected_window_count": int(len(selected_windows)),
        "top_n_per_variant": TOP_N_PER_VARIANT,
        "opened_after_start_loss_abs": opened_loss,
        "existing_loss_abs": existing_loss,
        "opened_after_start_loss_share_pct": opened_share,
        "existing_loss_share_pct": existing_share,
        "worst_product_direction_bucket": _json_safe(worst_product),
        "max_validation_abs_diff": max_validation_abs_diff,
        "strategy_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Man Group 关于趋势跟踪回撤的讨论、CFA/FAJ managed futures 研究和 pysystemtrade 的公开实现都支持："
            "先把 alpha 信号与组合风险预算/持仓路径分开归因，再决定是否改风险投入。Stage054 因此只做路径归因，"
            "不把某个亏损日期、品种或阈值直接改成交易规则。参考："
            "https://www.man.com/insights/is-this-time-different ; "
            "https://rpc.cfainstitute.org/research/financial-analysts-journal/2015/trend-following-with-managed-futures ; "
            "https://github.com/pst-group/pysystemtrade"
        ),
        "overfit_reflection_before": (
            "否。本阶段只读 Stage053 已经固定的最差窗口，按资金曲线和 positions 拆来源，不新增交易参数。"
        ),
        "overfit_reflection_after": (
            "否。若后续直接按本阶段最差品种、日期、方向设硬规则才会过拟合；本阶段只用于归因和下一步方向选择。"
        ),
        "continue_value_before": "有。Stage053 已反证 OI 份额救左尾，需要知道左尾是新开风险还是老仓 carry。",
        "continue_value_after": continue_after,
        "outputs": {
            "selected_windows": str(SELECTED_WINDOWS_PATH),
            "rerun_curves": str(RERUN_CURVES_PATH),
            "positions": str(POSITIONS_PATH),
            "curve_attribution": str(CURVE_ATTRIBUTION_PATH),
            "bucket_detail": str(BUCKET_DETAIL_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_PATH),
            "daily_detail": str(DAILY_DETAIL_PATH),
            "validation": str(VALIDATION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    selected_windows: pd.DataFrame,
    curve_attribution: pd.DataFrame,
    bucket: pd.DataFrame,
    product: pd.DataFrame,
    daily: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    lines = [
        "# Stage054 - 日级左尾路径归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；复用 Stage053 最差窗口，重跑 Stage013 仅为拿 positions；不改策略、不连接 CTP、不调用下单。",
        f"- 选中窗口数：`{decision['selected_window_count']}`；每个 variant topN `{decision['top_n_per_variant']}`。",
        "",
        "## 核心结论",
        "",
        f"- opened_after_start 亏损占比：`{decision['opened_after_start_loss_share_pct']:.2f}%`，亏损额 `{decision['opened_after_start_loss_abs']:,.2f}`。",
        f"- existing_at_window_start 亏损占比：`{decision['existing_loss_share_pct']:.2f}%`，亏损额 `{decision['existing_loss_abs']:,.2f}`。",
        f"- 最大校验差异：`{decision['max_validation_abs_diff']:,.6f}`。",
        f"- 最差产品/方向/bucket：`{decision['worst_product_direction_bucket']}`。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 选中窗口",
        "",
        _md_table(selected_windows, max_rows=40),
        "",
        "## 曲线窗口归因",
        "",
        _md_table(
            curve_attribution[
                [
                    column
                    for column in [
                        "selected_rank",
                        "variant",
                        "requested_start",
                        "window_end_date",
                        "equity_change",
                        "curve_net_pnl",
                        "stage053_delta_pnl",
                        "position_net_pnl",
                        "opened_after_start_loss_share_pct",
                        "existing_loss_share_pct",
                        "worst_day",
                        "worst_day_effect_pnl",
                    ]
                    if column in curve_attribution.columns
                ]
            ],
            max_rows=40,
        ),
        "",
        "## source bucket 汇总",
        "",
        _md_table(bucket, max_rows=20),
        "",
        "## 最差产品方向",
        "",
        _md_table(product.head(30), max_rows=30),
        "",
        "## 最差日期",
        "",
        _md_table(daily.head(30), max_rows=30),
        "",
        "## 校验",
        "",
        _md_table(validation, max_rows=60),
        "",
        "## 输出",
        "",
        f"- selected_windows：`{SELECTED_WINDOWS_PATH}`",
        f"- rerun_curves：`{RERUN_CURVES_PATH}`",
        f"- positions：`{POSITIONS_PATH}`",
        f"- curve_attribution：`{CURVE_ATTRIBUTION_PATH}`",
        f"- bucket_detail：`{BUCKET_DETAIL_PATH}`",
        f"- product_direction_summary：`{PRODUCT_DIRECTION_PATH}`",
        f"- daily_detail：`{DAILY_DETAIL_PATH}`",
        f"- validation：`{VALIDATION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    selected_windows: pd.DataFrame,
    curve_attribution: pd.DataFrame,
    bucket: pd.DataFrame,
    product: pd.DataFrame,
    validation: pd.DataFrame,
) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage054_daily_left_tail_path_attribution.md"
    lines = [
        "# Stage054 - 日级左尾路径归因",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage054_daily_left_tail_path_attribution.py`",
        "- 新增测试：`tests/test_rebuilt_c9_stage054_daily_left_tail_path_attribution.py`",
        "- 新增参数：`TOP_N_PER_VARIANT=8`，只用于选取 Stage053/Stage013 各自最差窗口做归因。",
        "- 修改参数：无；Stage013、Stage053、当前官方 C9 配置均未改。",
        "- 删除参数：无。",
        "- 新增回测结果：Stage053 最差日级窗口的资金曲线、positions、bucket、产品方向、日级 PnL 归因。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 选中窗口数：`{decision['selected_window_count']}`。",
        f"- opened_after_start 亏损占比：`{decision['opened_after_start_loss_share_pct']:.2f}%`。",
        f"- existing_at_window_start 亏损占比：`{decision['existing_loss_share_pct']:.2f}%`。",
        f"- opened_after_start 亏损额：`{decision['opened_after_start_loss_abs']:,.2f}`。",
        f"- existing_at_window_start 亏损额：`{decision['existing_loss_abs']:,.2f}`。",
        f"- 最大校验差异：`{decision['max_validation_abs_diff']:,.6f}`。",
        "",
        "## 选中窗口",
        "",
        _md_table(selected_windows, max_rows=40),
        "",
        "## 曲线窗口归因",
        "",
        _md_table(curve_attribution, max_rows=40),
        "",
        "## bucket 汇总",
        "",
        _md_table(bucket, max_rows=20),
        "",
        "## 最差产品方向",
        "",
        _md_table(product.head(30), max_rows=30),
        "",
        "## 校验",
        "",
        _md_table(validation, max_rows=60),
        "",
        "## 输出",
        "",
        f"- selected_windows：`{SELECTED_WINDOWS_PATH}`",
        f"- rerun_curves：`{RERUN_CURVES_PATH}`",
        f"- positions：`{POSITIONS_PATH}`",
        f"- curve_attribution：`{CURVE_ATTRIBUTION_PATH}`",
        f"- bucket_detail：`{BUCKET_DETAIL_PATH}`",
        f"- product_direction_summary：`{PRODUCT_DIRECTION_PATH}`",
        f"- daily_detail：`{DAILY_DETAIL_PATH}`",
        f"- validation：`{VALIDATION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    stage053_summary = pd.read_csv(STAGE053_SUMMARY_PATH, encoding="utf-8-sig")
    stage053_curves = pd.read_csv(STAGE053_CURVES_PATH, encoding="utf-8-sig")
    selected_windows = select_worst_windows_from_stage053_summary(stage053_summary, TOP_N_PER_VARIANT)
    if selected_windows.empty:
        raise ValueError("no Stage053 worst windows selected")

    rerun_curves, positions = _run_position_sources(selected_windows)
    curve_attribution, bucket_detail, product_detail, daily_detail, validation = _build_attribution(
        selected_windows,
        stage053_curves,
        rerun_curves,
        positions,
    )
    bucket, product, daily = _summaries(bucket_detail, product_detail, daily_detail)
    decision = _decision(selected_windows, curve_attribution, bucket, product, validation)

    selected_windows.to_csv(SELECTED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    rerun_curves.to_csv(RERUN_CURVES_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    curve_attribution.to_csv(CURVE_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_DETAIL_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_DETAIL_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    _plot(curve_attribution, bucket, product, daily)
    _write_report(decision, selected_windows, curve_attribution, bucket, product, daily, validation)
    stage_record = _write_stage_record(decision, selected_windows, curve_attribution, bucket, product, validation)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
