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
DATA_ROOT = PROJECT_DIR / "downloaded_futures"

INPUT_PREFIX = "qmt_roll_stage565_stage526_liquidity_capacity_product_audit"
INPUT_TAG = "stage565_stage526_liquidity_capacity_product_audit_v1"
EVENT_IN = OUTPUT_DIR / f"{INPUT_PREFIX}_stage526_trade_liquidity_events_{INPUT_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{INPUT_PREFIX}_summary_{INPUT_TAG}.csv"

MODEL_TAG = "stage566_stage526_liquidity_gap_backfill_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage566_stage526_liquidity_gap_backfill_audit"

GAP_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_events_{MODEL_TAG}.csv"
BACKFILL_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_candidates_{MODEL_TAG}.csv"
RESOLVED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_resolved_events_{MODEL_TAG}.csv"
UNRESOLVED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unresolved_by_symbol_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_before_after_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SOFT_ORDER_VOLUME_PCT = 0.25
HARD_ORDER_VOLUME_PCT = 0.50
MAX_ORDER_VOLUME_PCT = 1.00
STRESS_POSITION_OI_PCT = 1.00
MIN_FULL_LIKE_MINUTE_BARS = 180


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


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol, exchange = _parse_vt_symbol(vt_symbol)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}" if exchange else product


def _candidate_file_names(symbol: str) -> set[str]:
    names = {symbol, symbol.lower(), symbol.upper()}
    names |= {f"{item}_minute_backtest" for item in list(names)}
    names |= {f"{item}_completed_minute_backtest" for item in list(names)}
    return {f"{name}.csv" for name in names}


def find_contract_files(vt_symbol: str) -> list[Path]:
    symbol, exchange = _parse_vt_symbol(vt_symbol)
    wanted = _candidate_file_names(symbol)
    files: list[Path] = []
    for path in DATA_ROOT.rglob("*.csv"):
        if path.name not in wanted:
            continue
        if exchange and path.parent.name.upper() != exchange.upper():
            continue
        files.append(path)
    return sorted(files, key=lambda item: (item.name.count("minute"), len(str(item)), str(item)))


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    parsed = pd.to_datetime(text, errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y%m%d", errors="coerce")
    return parsed.dt.normalize()


def _extract_daily_candidate(path: Path, event_date: pd.Timestamp) -> dict[str, Any] | None:
    try:
        frame = _read_csv(path)
    except Exception as exc:
        return {
            "source_path": str(path),
            "source_type": "daily_read_error",
            "source_note": str(exc),
            "candidate_volume": 0.0,
            "candidate_oi": 0.0,
            "candidate_close": 0.0,
            "minute_bar_count": 0,
            "accepted_quality": "unusable",
        }
    date_column = None
    for column in ["trade_date", "date", "datetime"]:
        if column in frame.columns:
            date_column = column
            break
    if date_column is None:
        return None
    dates = _normalize_trade_date(frame[date_column])
    row = frame.loc[dates.eq(event_date)].copy()
    if row.empty:
        return None
    record = row.iloc[-1]
    volume = 0.0
    for column in ["volume", "vol"]:
        if column in row.columns:
            volume = float(pd.to_numeric(record.get(column), errors="coerce") or 0.0)
            break
    oi = 0.0
    for column in ["close_oi", "open_interest", "oi", "open_oi"]:
        if column in row.columns:
            oi = float(pd.to_numeric(record.get(column), errors="coerce") or 0.0)
            break
    close = 0.0
    if "close" in row.columns:
        close = float(pd.to_numeric(record.get("close"), errors="coerce") or 0.0)
    quality = "daily_full" if volume > 0.0 and oi > 0.0 else "daily_incomplete"
    return {
        "source_path": str(path),
        "source_type": "daily",
        "source_note": "exact daily row",
        "candidate_volume": volume,
        "candidate_oi": oi,
        "candidate_close": close,
        "minute_bar_count": 0,
        "accepted_quality": quality,
    }


def _extract_minute_candidate(path: Path, event_date: pd.Timestamp) -> dict[str, Any] | None:
    try:
        frame = _read_csv(path)
    except Exception as exc:
        return {
            "source_path": str(path),
            "source_type": "minute_read_error",
            "source_note": str(exc),
            "candidate_volume": 0.0,
            "candidate_oi": 0.0,
            "candidate_close": 0.0,
            "minute_bar_count": 0,
            "accepted_quality": "unusable",
        }
    if "bar_datetime" not in frame.columns:
        return None
    dates = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.normalize()
    rows = frame.loc[dates.eq(event_date)].copy()
    if rows.empty:
        return None
    bar_count = int(len(rows))
    volume = float(_num(rows, "volume").sum())
    close_oi_series = _num(rows, "close_oi")
    positive_oi = close_oi_series[close_oi_series.gt(0.0)]
    oi = float(positive_oi.iloc[-1]) if not positive_oi.empty else 0.0
    close_series = _num(rows, "close")
    close = float(close_series.iloc[-1]) if not close_series.empty else 0.0
    if bar_count >= MIN_FULL_LIKE_MINUTE_BARS and volume > 0.0 and oi > 0.0:
        quality = "minute_full_like"
    elif volume > 0.0 or oi > 0.0:
        quality = "minute_partial_context"
    else:
        quality = "minute_empty_context"
    return {
        "source_path": str(path),
        "source_type": "minute",
        "source_note": "same-day minute aggregation",
        "candidate_volume": volume,
        "candidate_oi": oi,
        "candidate_close": close,
        "minute_bar_count": bar_count,
        "accepted_quality": quality,
    }


def collect_candidates(gap_events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, event in gap_events.iterrows():
        vt_symbol = str(event["vt_symbol"])
        event_date = pd.Timestamp(event["date"]).normalize()
        files = find_contract_files(vt_symbol)
        if not files:
            rows.append(
                {
                    "event_id": int(event["event_id"]),
                    "date": event_date,
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": event["product_vt_symbol"],
                    "order_volume": float(event["order_volume"]),
                    "source_path": "",
                    "source_type": "missing_file",
                    "source_note": "no local contract file found",
                    "candidate_volume": 0.0,
                    "candidate_oi": 0.0,
                    "candidate_close": 0.0,
                    "minute_bar_count": 0,
                    "accepted_quality": "unusable",
                }
            )
            continue
        for path in files:
            name = path.name.lower()
            if "minute_backtest" in name:
                candidate = _extract_minute_candidate(path, event_date)
            else:
                candidate = _extract_daily_candidate(path, event_date)
            if candidate is None:
                continue
            rows.append(
                {
                    "event_id": int(event["event_id"]),
                    "date": event_date,
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": event["product_vt_symbol"],
                    "order_volume": float(event["order_volume"]),
                    **candidate,
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["candidate_order_volume_to_day_volume_pct"] = np.where(
        out["candidate_volume"] > 0.0, out["order_volume"] / out["candidate_volume"] * 100.0, np.nan
    )
    out["candidate_order_volume_to_oi_pct"] = np.where(
        out["candidate_oi"] > 0.0, out["order_volume"] / out["candidate_oi"] * 100.0, np.nan
    )
    return out.sort_values(["event_id", "accepted_quality", "source_type", "source_path"]).reset_index(drop=True)


def choose_best_candidate(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    rank = {
        "daily_full": 0,
        "minute_full_like": 1,
        "daily_incomplete": 2,
        "minute_partial_context": 3,
        "minute_empty_context": 4,
        "unusable": 5,
    }
    work = candidates.copy()
    work["quality_rank"] = work["accepted_quality"].map(rank).fillna(9).astype(int)
    work["has_positive_volume_oi"] = (work["candidate_volume"].gt(0.0) & work["candidate_oi"].gt(0.0)).astype(int)
    work = work.sort_values(
        ["event_id", "quality_rank", "has_positive_volume_oi", "minute_bar_count", "candidate_volume"],
        ascending=[True, True, False, False, False],
    )
    return work.groupby("event_id", as_index=False).head(1).reset_index(drop=True)


def apply_backfill(events: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    out["event_id"] = out.index.astype(int)
    selected_cols = [
        "event_id",
        "source_path",
        "source_type",
        "accepted_quality",
        "candidate_volume",
        "candidate_oi",
        "candidate_close",
        "minute_bar_count",
    ]
    selected_view = selected[selected_cols].copy() if not selected.empty else pd.DataFrame(columns=selected_cols)
    merged = out.merge(selected_view, on="event_id", how="left")
    accepted = merged["accepted_quality"].isin(["daily_full", "minute_full_like"])
    merged["backfill_accepted"] = accepted.astype(int)
    merged["backfill_context_only"] = merged["accepted_quality"].isin(["daily_incomplete", "minute_partial_context"]).astype(int)
    merged["effective_daily_volume"] = np.where(
        accepted & merged["candidate_volume"].gt(0.0), merged["candidate_volume"], merged["daily_volume"]
    )
    merged["effective_daily_close_oi"] = np.where(
        accepted & merged["candidate_oi"].gt(0.0), merged["candidate_oi"], merged["daily_close_oi"]
    )
    merged["effective_daily_close"] = np.where(
        accepted & merged["candidate_close"].gt(0.0), merged["candidate_close"], merged["daily_close"]
    )
    merged["effective_volume_data_found"] = merged["effective_daily_volume"].gt(0.0).astype(int)
    merged["effective_oi_data_found"] = merged["effective_daily_close_oi"].gt(0.0).astype(int)
    merged["effective_volume_data_gap_event"] = merged["effective_volume_data_found"].eq(0).astype(int)
    merged["effective_oi_data_gap_event"] = merged["effective_oi_data_found"].eq(0).astype(int)
    merged["effective_order_volume_to_day_volume_pct"] = np.where(
        merged["effective_daily_volume"] > 0.0,
        merged["order_volume"] / merged["effective_daily_volume"] * 100.0,
        np.nan,
    )
    merged["effective_order_volume_to_oi_pct"] = np.where(
        merged["effective_daily_close_oi"] > 0.0,
        merged["order_volume"] / merged["effective_daily_close_oi"] * 100.0,
        np.nan,
    )
    merged["effective_peak_position_to_oi_pct"] = np.where(
        merged["effective_daily_close_oi"] > 0.0,
        merged["peak_abs_pos"] / merged["effective_daily_close_oi"] * 100.0,
        np.nan,
    )
    merged["effective_soft_volume_stress_event"] = (
        merged["effective_volume_data_found"].eq(1)
        & merged["effective_order_volume_to_day_volume_pct"].fillna(0.0).gt(SOFT_ORDER_VOLUME_PCT)
    ).astype(int)
    merged["effective_hard_volume_stress_event"] = (
        merged["effective_volume_data_found"].eq(1)
        & merged["effective_order_volume_to_day_volume_pct"].fillna(0.0).gt(HARD_ORDER_VOLUME_PCT)
    ).astype(int)
    merged["effective_position_oi_stress_event"] = (
        merged["effective_oi_data_found"].eq(1)
        & merged["effective_peak_position_to_oi_pct"].fillna(0.0).gt(STRESS_POSITION_OI_PCT)
    ).astype(int)
    return merged


def build_annual(before_after: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in before_after.groupby("year", sort=True):
        before_valid = group["order_volume_to_day_volume_pct"].dropna()
        after_valid = group["effective_order_volume_to_day_volume_pct"].dropna()
        rows.append(
            {
                "year": int(year),
                "event_count": int(len(group)),
                "original_volume_coverage_rate_pct": float(group["volume_data_found"].mean() * 100.0),
                "effective_volume_coverage_rate_pct": float(group["effective_volume_data_found"].mean() * 100.0),
                "original_oi_coverage_rate_pct": float(group["oi_data_found"].mean() * 100.0),
                "effective_oi_coverage_rate_pct": float(group["effective_oi_data_found"].mean() * 100.0),
                "accepted_backfill_events": int(group["backfill_accepted"].sum()),
                "context_only_events": int(group["backfill_context_only"].sum()),
                "unresolved_gap_events": int(
                    ((group["effective_volume_data_gap_event"] == 1) | (group["effective_oi_data_gap_event"] == 1)).sum()
                ),
                "original_p95_order_volume_to_day_volume_pct": float(before_valid.quantile(0.95)) if len(before_valid) else 0.0,
                "effective_p95_order_volume_to_day_volume_pct": float(after_valid.quantile(0.95)) if len(after_valid) else 0.0,
                "original_max_order_volume_to_day_volume_pct": float(before_valid.max()) if len(before_valid) else 0.0,
                "effective_max_order_volume_to_day_volume_pct": float(after_valid.max()) if len(after_valid) else 0.0,
                "effective_hard_volume_stress_events": int(group["effective_hard_volume_stress_event"].sum()),
                "effective_position_oi_stress_events": int(group["effective_position_oi_stress_event"].sum()),
            }
        )
    return pd.DataFrame(rows)


def build_unresolved(resolved: pd.DataFrame) -> pd.DataFrame:
    unresolved = resolved[
        (resolved["volume_data_gap_event"].eq(1) | resolved["oi_data_gap_event"].eq(1))
        & (resolved["backfill_accepted"].eq(0))
    ].copy()
    if unresolved.empty:
        return pd.DataFrame()
    grouped = (
        unresolved.groupby(["product_vt_symbol", "vt_symbol"], as_index=False)
        .agg(
            unresolved_events=("date", "count"),
            first_date=("date", "min"),
            last_date=("date", "max"),
            trade_day_net_pnl=("net_pnl", "sum"),
            slippage=("slippage", "sum"),
            best_context_quality=("accepted_quality", lambda s: ",".join(sorted(set(str(x) for x in s.dropna())))),
            max_minute_bar_count=("minute_bar_count", "max"),
        )
        .sort_values(["unresolved_events", "trade_day_net_pnl"], ascending=[False, True])
    )
    return grouped


def build_gates(resolved: pd.DataFrame, selected: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    event_count = int(len(resolved))
    gap_mask = resolved["volume_data_gap_event"].eq(1) | resolved["oi_data_gap_event"].eq(1)
    original_gap_events = int(gap_mask.sum())
    accepted = int(resolved.loc[gap_mask, "backfill_accepted"].sum())
    context_only = int(resolved.loc[gap_mask, "backfill_context_only"].sum())
    unresolved = int((gap_mask & resolved["backfill_accepted"].eq(0)).sum())
    original_volume_coverage = float(resolved["volume_data_found"].mean() * 100.0)
    effective_volume_coverage = float(resolved["effective_volume_data_found"].mean() * 100.0)
    original_oi_coverage = float(resolved["oi_data_found"].mean() * 100.0)
    effective_oi_coverage = float(resolved["effective_oi_data_found"].mean() * 100.0)
    p95 = (
        float(resolved["effective_order_volume_to_day_volume_pct"].dropna().quantile(0.95))
        if resolved["effective_order_volume_to_day_volume_pct"].dropna().size
        else 999.0
    )
    max_ratio = float(resolved["effective_order_volume_to_day_volume_pct"].max())
    hard_rate = float(resolved["effective_hard_volume_stress_event"].mean() * 100.0)
    position_oi_rate = float(resolved["effective_position_oi_stress_event"].mean() * 100.0)
    stress = resolved[resolved["effective_hard_volume_stress_event"].eq(1)]
    stress_pnl_share = (
        float(stress["net_pnl"].sum() / resolved["net_pnl"].abs().sum() * 100.0) if len(resolved) else 0.0
    )
    accepted_ratio = accepted / original_gap_events * 100.0 if original_gap_events else 100.0
    daily_full_count = int((selected["accepted_quality"].eq("daily_full")).sum()) if not selected.empty else 0
    minute_full_like_count = int((selected["accepted_quality"].eq("minute_full_like")).sum()) if not selected.empty else 0
    gate_rows = [
        {
            "gate": "accepted_gap_backfill_ge_80pct",
            "pass": int(accepted_ratio >= 80.0),
            "value": accepted_ratio,
            "threshold": 80.0,
            "note": "原始容量缺口中至少80%被完整日线或完整分钟近似补齐。",
        },
        {
            "gate": "effective_volume_coverage_ge_95pct",
            "pass": int(effective_volume_coverage >= 95.0),
            "value": effective_volume_coverage,
            "threshold": 95.0,
            "note": "回填后Stage526交易事件具备正成交量覆盖。",
        },
        {
            "gate": "effective_oi_coverage_ge_95pct",
            "pass": int(effective_oi_coverage >= 95.0),
            "value": effective_oi_coverage,
            "threshold": 95.0,
            "note": "回填后Stage526交易事件具备正持仓量覆盖。",
        },
        {
            "gate": "effective_p95_order_volume_le_0p25pct",
            "pass": int(p95 <= SOFT_ORDER_VOLUME_PCT),
            "value": p95,
            "threshold": SOFT_ORDER_VOLUME_PCT,
            "note": "回填后95分位订单量占日成交量不超过软容量线。",
        },
        {
            "gate": "effective_max_order_volume_le_1pct",
            "pass": int(max_ratio <= MAX_ORDER_VOLUME_PCT),
            "value": max_ratio,
            "threshold": MAX_ORDER_VOLUME_PCT,
            "note": "回填后单次订单量不超过日成交量1%。",
        },
        {
            "gate": "effective_hard_stress_event_rate_le_5pct",
            "pass": int(hard_rate <= 5.0),
            "value": hard_rate,
            "threshold": 5.0,
            "note": "回填后硬容量压力事件占比不超过5%。",
        },
        {
            "gate": "effective_position_oi_stress_event_rate_le_5pct",
            "pass": int(position_oi_rate <= 5.0),
            "value": position_oi_rate,
            "threshold": 5.0,
            "note": "回填后持仓/OI压力事件占比不超过5%。",
        },
        {
            "gate": "hard_liquidity_stress_not_main_loss_driver",
            "pass": int(abs(stress_pnl_share) <= 10.0),
            "value": stress_pnl_share,
            "threshold": 10.0,
            "note": "回填后硬容量压力事件不解释主要交易日损益。",
        },
    ]
    gates = pd.DataFrame(gate_rows)
    if effective_volume_coverage >= 95.0 and effective_oi_coverage >= 95.0 and max_ratio <= MAX_ORDER_VOLUME_PCT:
        decision_text = "liquidity_gap_closed_capacity_caution_selector_not_ready"
    elif accepted > 0:
        decision_text = "liquidity_gap_partially_backfilled_capacity_not_closed"
    else:
        decision_text = "liquidity_gap_not_backfilled_capacity_not_closed"
    decision = {
        "decision": decision_text,
        "passed_gates": int(gates["pass"].sum()),
        "total_gates": int(len(gates)),
        "stage526_event_count": event_count,
        "original_gap_events": original_gap_events,
        "accepted_backfill_events": accepted,
        "context_only_gap_events": context_only,
        "unresolved_gap_events": unresolved,
        "accepted_gap_backfill_rate_pct": accepted_ratio,
        "daily_full_backfill_events": daily_full_count,
        "minute_full_like_backfill_events": minute_full_like_count,
        "original_volume_data_coverage_rate_pct": original_volume_coverage,
        "effective_volume_data_coverage_rate_pct": effective_volume_coverage,
        "original_oi_data_coverage_rate_pct": original_oi_coverage,
        "effective_oi_data_coverage_rate_pct": effective_oi_coverage,
        "effective_p95_order_volume_to_day_volume_pct": p95,
        "effective_max_order_volume_to_day_volume_pct": max_ratio,
        "effective_hard_volume_stress_event_rate_pct": hard_rate,
        "effective_position_oi_stress_event_rate_pct": position_oi_rate,
        "hard_liquidity_stress_trade_day_pnl_share_of_abs_trade_day_pnl_pct": stress_pnl_share,
    }
    return gates, decision


def build_summary(decision: dict[str, Any]) -> pd.DataFrame:
    ref = {}
    if SUMMARY_IN.exists():
        old = _read_csv(SUMMARY_IN)
        if not old.empty:
            record = old.iloc[0]
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
                if column in old.columns:
                    ref[column] = float(pd.to_numeric(record.get(column), errors="coerce") or 0.0)
    return pd.DataFrame([{**ref, **decision}])


def write_report(
    gap_events: pd.DataFrame,
    candidates: pd.DataFrame,
    selected: pd.DataFrame,
    resolved: pd.DataFrame,
    unresolved: pd.DataFrame,
    annual: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    accepted_samples = selected[selected["accepted_quality"].isin(["daily_full", "minute_full_like"])].copy()
    accepted_samples = accepted_samples.sort_values(["event_id"]).head(20)
    stress_cols = [
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "order_volume",
        "effective_daily_volume",
        "effective_daily_close_oi",
        "effective_order_volume_to_day_volume_pct",
        "effective_peak_position_to_oi_pct",
        "net_pnl",
        "source_path",
        "accepted_quality",
    ]
    stress_top = resolved[resolved["effective_order_volume_to_day_volume_pct"].notna()].copy()
    stress_top = stress_top.sort_values("effective_order_volume_to_day_volume_pct", ascending=False)[stress_cols].head(12)
    lines = [
        "# Stage566 Stage526容量缺口本地回填审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        "- 阶段性质：只读容量数据覆盖审计；不改策略、不改参数、不生成交易候选。",
        "- 研究问题：Stage266 中 2020/2026 的日成交量/OI缺口，能否用仓库已有日线或完整分钟线补齐，从而让扩池容量判断更接近真实可成交约束。",
        "- 调研判断：TqSdk/vn.py历史K线可提供成交量与持仓量；成熟趋势组合框架会把品种分散、成本、容量和相关性单独建模。本阶段只补容量证据，不把数据补齐当作alpha。",
        "- 运行前过拟合反思：否。本阶段不根据收益结果调参数，只按预声明数据质量优先级补正容量字段。",
        "- 运行前继续价值反思：有。低单笔风险扩池如果要成立，必须先排除不可成交尾部和容量覆盖盲区。",
        "",
        "## 决策",
        "",
        f"- decision：`{decision['decision']}`",
        f"- gates：`{decision['passed_gates']}/{decision['total_gates']}`",
        f"- 原始缺口事件：`{decision['original_gap_events']}`",
        f"- 接受回填事件：`{decision['accepted_backfill_events']}`",
        f"- 仅上下文事件：`{decision['context_only_gap_events']}`",
        f"- 未解决缺口事件：`{decision['unresolved_gap_events']}`",
        f"- 回填后正成交量覆盖率：`{decision['effective_volume_data_coverage_rate_pct']:.4f}%`",
        f"- 回填后正持仓量覆盖率：`{decision['effective_oi_data_coverage_rate_pct']:.4f}%`",
        f"- 回填后p95订单量/日成交量：`{decision['effective_p95_order_volume_to_day_volume_pct']:.4f}%`",
        f"- 回填后max订单量/日成交量：`{decision['effective_max_order_volume_to_day_volume_pct']:.4f}%`",
        "",
        "## 闸门",
        "",
        _md_table(gates),
        "",
        "## 年度覆盖变化",
        "",
        _md_table(annual),
        "",
        "## 接受回填样本",
        "",
        _md_table(
            accepted_samples[
                [
                    "date",
                    "vt_symbol",
                    "product_vt_symbol",
                    "candidate_volume",
                    "candidate_oi",
                    "minute_bar_count",
                    "accepted_quality",
                    "source_path",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 回填后容量压力Top",
        "",
        _md_table(stress_top),
        "",
        "## 未解决缺口",
        "",
        _md_table(unresolved, max_rows=30),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表路径：`{CHART_PATH}`",
        "- 左上：按年度观察原始缺口、完整回填、仅上下文和未解决缺口，确认缺口是否仍集中在2020/2026。",
        "- 右上：观察回填来源结构，防止主要依赖不完整分钟片段。",
        "- 左下：看未解决缺口是否集中于少数合约/产品，决定是否需要外部补数据。",
        "- 右下：看年度覆盖率与最大订单占比是否因回填发生容量结论变化。",
        "",
        "## 结论",
        "",
        "- 完整日线/完整分钟近似才允许进入容量重算；成交窗口分钟片段只保留为上下文，不能用来当日成交量。",
        "- 如果回填后覆盖率仍低于95%，容量账仍不能关；后续应优先补真实日线成交量/OI，而不是据此扩池回测。",
        "- 如果覆盖率提升但 `fu2509.SHFE` 等边界事件仍存在，说明当前Stage526主风险不是容量缺口，而是少数大单和真实滑点倍率。",
        "",
        "## 后续规划",
        "",
        "- 若未解决缺口集中在少数合约，下一步用TqSdk日线补这些合约的完整成交量/OI。",
        "- 扩池方向继续保留容量闸门：候选品种必须先过正成交量/OI覆盖、订单量占比、持仓/OI，再谈选品收益。",
        "- 不继续扫低单笔风险、簇cap、相关阈值小数；后续重点转向point-in-time外生/舆情选品器和真实滑点采样账本。",
        "",
        "## 运行后反思",
        "",
        "- 过拟合：否。回填规则在运行前固定，且只影响容量审计字段，不影响交易信号或收益路径。",
        "- 继续价值：有。它把“扩池可成交性”从纸面直觉推进到可审计数据，但不能替代后续选品器和真实成交采样。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_chart(
    gap_events: pd.DataFrame,
    selected: pd.DataFrame,
    unresolved: pd.DataFrame,
    annual: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax = axes[0, 0]
    gap_by_year = gap_events.groupby("year").size().rename("original_gap")
    accepted_by_year = (
        selected[selected["accepted_quality"].isin(["daily_full", "minute_full_like"])]
        .assign(year=lambda x: pd.to_datetime(x["date"]).dt.year)
        .groupby("year")
        .size()
        .rename("accepted")
    )
    context_by_year = (
        selected[selected["accepted_quality"].isin(["daily_incomplete", "minute_partial_context"])]
        .assign(year=lambda x: pd.to_datetime(x["date"]).dt.year)
        .groupby("year")
        .size()
        .rename("context_only")
    )
    unresolved_by_year = (
        unresolved.assign(year=lambda x: pd.to_datetime(x["first_date"]).dt.year)
        .groupby("year")["unresolved_events"]
        .sum()
        .rename("unresolved")
        if not unresolved.empty
        else pd.Series(dtype=float, name="unresolved")
    )
    years = sorted(set(gap_by_year.index) | set(accepted_by_year.index) | set(context_by_year.index) | set(unresolved_by_year.index))
    year_frame = pd.DataFrame(index=years)
    for series in [gap_by_year, accepted_by_year, context_by_year, unresolved_by_year]:
        year_frame[series.name] = series
    year_frame = year_frame.fillna(0.0)
    year_frame[["original_gap", "accepted", "context_only", "unresolved"]].plot(kind="bar", ax=ax, width=0.78)
    ax.set_title("Stage526容量缺口年度分布与回填结果")
    ax.set_ylabel("事件数")
    ax.set_xlabel("年份")
    ax.tick_params(axis="x", rotation=0)

    ax = axes[0, 1]
    source_counts = selected["accepted_quality"].fillna("missing").value_counts().sort_index()
    colors = {
        "daily_full": "#2ca02c",
        "minute_full_like": "#1f77b4",
        "daily_incomplete": "#bcbd22",
        "minute_partial_context": "#ff7f0e",
        "minute_empty_context": "#7f7f7f",
        "unusable": "#d62728",
    }
    source_counts.plot(kind="bar", ax=ax, color=[colors.get(str(idx), "#999999") for idx in source_counts.index])
    ax.set_title("最优本地来源质量")
    ax.set_ylabel("事件数")
    ax.set_xlabel("来源质量")
    ax.tick_params(axis="x", rotation=35)

    ax = axes[1, 0]
    if unresolved.empty:
        ax.text(0.5, 0.5, "无未解决缺口", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        top_unresolved = (
            unresolved.groupby("product_vt_symbol")["unresolved_events"].sum().sort_values(ascending=True).tail(12)
        )
        top_unresolved.plot(kind="barh", ax=ax, color="#d62728")
        ax.set_title("未解决缺口产品Top")
        ax.set_xlabel("事件数")

    ax = axes[1, 1]
    plot_annual = annual.set_index("year")
    plot_annual[["original_volume_coverage_rate_pct", "effective_volume_coverage_rate_pct"]].plot(
        ax=ax, marker="o", color=["#9edae5", "#1f77b4"]
    )
    ax2 = ax.twinx()
    plot_annual[["original_max_order_volume_to_day_volume_pct", "effective_max_order_volume_to_day_volume_pct"]].plot(
        ax=ax2, marker="x", linestyle="--", color=["#ffbb78", "#d62728"]
    )
    ax.set_title("年度覆盖率与最大订单/成交量")
    ax.set_ylabel("覆盖率(%)")
    ax2.set_ylabel("最大订单/日成交量(%)")
    ax.set_xlabel("年份")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="best", fontsize=8)
    ax2.get_legend().remove()

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    events = _read_csv(EVENT_IN)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    if "event_id" in events.columns:
        events = events.drop(columns=["event_id"])
    events["product_vt_symbol"] = events["product_vt_symbol"].fillna(events["vt_symbol"].map(_product_from_vt_symbol))
    gap_mask = events["volume_data_gap_event"].eq(1) | events["oi_data_gap_event"].eq(1)
    gap_events = events[gap_mask].copy()
    gap_events.insert(0, "event_id", gap_events.index.astype(int))
    candidates = collect_candidates(gap_events)
    selected = choose_best_candidate(candidates)
    resolved = apply_backfill(events, selected)
    annual = build_annual(resolved)
    unresolved = build_unresolved(resolved)
    gates, decision = build_gates(resolved, selected)
    summary = build_summary(decision)

    gap_events.to_csv(GAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(BACKFILL_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    selected.to_csv(RESOLVED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    unresolved.to_csv(UNRESOLVED_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(gap_events, selected, unresolved, annual)
    write_report(gap_events, candidates, selected, resolved, unresolved, annual, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"chart={CHART_PATH}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
