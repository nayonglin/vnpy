from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage077"
MODEL_TAG = "stage077_raw_authority_provenance_tick_backfill_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage077_raw_authority_provenance_tick_backfill_feasibility"

STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE074_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"
STAGE076_DIR = LINE_DIR / "outputs" / "stage076_data_exit_route_scorecard_audit"

STAGE045_CURVE_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE074_AUDIT_IN = (
    STAGE074_DIR
    / "qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_decision_audit_"
    "stage074_initial_entry_authoritative_source_decision_audit_v1.csv"
)
STAGE076_SUMMARY_IN = (
    STAGE076_DIR
    / "qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_summary_"
    "stage076_data_exit_route_scorecard_audit_v1.csv"
)

STAGE448_SCRIPT = EXAMPLE_DIR / "analyze_qmt_roll_stage448_minute_session_rebuild_batch.py"
STAGE452_SCRIPT = EXAMPLE_DIR / "analyze_qmt_roll_stage452_iterative_1455_proxy_backfill.py"
STAGE501_SCRIPT = EXAMPLE_DIR / "analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py"
STAGE502_SCRIPT = EXAMPLE_DIR / "analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py"

STAGE449_STATUS_IN = (
    EXAMPLE_DIR
    / "backtest_outputs"
    / "qmt_roll_stage449_minute_session_rebuild_full_extract_status_stage449_minute_session_rebuild_full_v1.csv"
)
STAGE449_BARS_IN = (
    EXAMPLE_DIR
    / "backtest_outputs"
    / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv"
)
STAGE449_DETAIL_IN = (
    EXAMPLE_DIR
    / "backtest_outputs"
    / "qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv"
)

RAW_AUTHORITY_ROOTS = [
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
]

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
SOURCE_LINEAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_lineage_{MODEL_TAG}.csv"
ACTION_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_scorecard_{MODEL_TAG}.csv"
BAR_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bar_quality_summary_{MODEL_TAG}.csv"
ANCHOR_YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_year_matrix_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_provenance_chart_{MODEL_TAG}.png"
READINESS_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_provenance_readiness_atlas_{MODEL_TAG}.png"
BAR_QUALITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bar_quality_chart_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(col) for col in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in display.columns) + " |")
    return "\n".join(lines)


def _count_files(root: Path, patterns: list[str]) -> int:
    if not root.exists():
        return 0
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in root.rglob(pattern) if path.is_file())
    return len(files)


def _script_contains(path: Path, text: str) -> int:
    if not path.exists():
        return 0
    return int(text in path.read_text(encoding="utf-8", errors="ignore"))


def _prepare_audit(stage074: pd.DataFrame) -> pd.DataFrame:
    audit = stage074.copy()
    audit["official_open_date"] = pd.to_datetime(audit["official_open_date"], errors="coerce")
    audit["realized_pnl"] = _safe_num(audit.get("realized_pnl", pd.Series(np.nan, index=audit.index))).fillna(0.0)
    for col in [
        "timestamp_ready",
        "raw_anchor_ready",
        "raw_anchor_exact_official",
        "raw_anchor_zero_volume",
        "raw_anchor_degenerate_ohlc",
        "stage449_anchor_ready",
        "stage449_anchor_exact_official",
        "stage449_anchor_zero_volume",
        "stage449_anchor_degenerate_ohlc",
        "tq_proxy_anchor_ready",
        "tq_price_exact_any",
    ]:
        audit[col] = _safe_num(audit.get(col, pd.Series(0, index=audit.index))).fillna(0).astype(int)
    audit["open_year"] = _safe_num(audit.get("official_open_year", audit["official_open_date"].dt.year)).fillna(0).astype(int)
    audit["route_class"] = np.select(
        [
            audit["timestamp_ready"].eq(0),
            audit["source_decision_class"].astype(str).str.contains("stage452", na=False),
            audit["stage449_anchor_ready"].eq(1),
        ],
        ["fallback_no_proxy_gap", "stage452_raw_fallback_gap", "stage449_raw_price_boundary"],
        default="raw_price_boundary_other",
    )
    return audit


def _stage449_bar_quality() -> pd.DataFrame:
    if not STAGE449_BARS_IN.exists():
        return pd.DataFrame(
            [
                {
                    "artifact": "stage449_minute_bars",
                    "exists": 0,
                    "total_rows": 0,
                    "unique_symbols": 0,
                    "zero_volume_rows": 0,
                    "degenerate_ohlc_rows": 0,
                    "zero_and_degenerate_rows": 0,
                    "positive_volume_non_degenerate_rows": 0,
                    "has_bid_ask_columns": 0,
                    "has_last_price_column": 0,
                }
            ]
        )
    header = pd.read_csv(STAGE449_BARS_IN, nrows=0, encoding="utf-8-sig")
    columns = set(header.columns)
    has_bid_ask = int(bool(columns & {"bid_price1", "ask_price1", "bid1", "ask1", "bid_price_1", "ask_price_1"}))
    has_last = int("last_price" in columns)
    usecols = [col for col in ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"] if col in columns]
    total = 0
    zero = 0
    degenerate = 0
    both = 0
    positive_non_degenerate = 0
    symbols: set[str] = set()
    year_rows: dict[int, dict[str, int]] = {}
    for chunk in pd.read_csv(STAGE449_BARS_IN, usecols=usecols, chunksize=250_000, encoding="utf-8-sig"):
        total += len(chunk)
        if "vt_symbol" in chunk.columns:
            symbols.update(chunk["vt_symbol"].dropna().astype(str).unique())
        open_ = _safe_num(chunk.get("open", pd.Series(np.nan, index=chunk.index)))
        high = _safe_num(chunk.get("high", pd.Series(np.nan, index=chunk.index)))
        low = _safe_num(chunk.get("low", pd.Series(np.nan, index=chunk.index)))
        close = _safe_num(chunk.get("close", pd.Series(np.nan, index=chunk.index)))
        volume = _safe_num(chunk.get("volume", pd.Series(np.nan, index=chunk.index))).fillna(0.0)
        zero_mask = volume.le(0.0)
        deg_mask = open_.eq(high) & open_.eq(low) & open_.eq(close)
        zero += int(zero_mask.sum())
        degenerate += int(deg_mask.sum())
        both += int((zero_mask & deg_mask).sum())
        positive_non_degenerate += int((volume.gt(0.0) & ~deg_mask).sum())
        if "bar_datetime" in chunk.columns:
            years = pd.to_datetime(chunk["bar_datetime"], errors="coerce").dt.year
            for year, part_index in years.dropna().astype(int).groupby(years.dropna().astype(int)).groups.items():
                idx = list(part_index)
                info = year_rows.setdefault(
                    int(year),
                    {"year": int(year), "rows": 0, "zero_volume_rows": 0, "degenerate_ohlc_rows": 0},
                )
                info["rows"] += len(idx)
                info["zero_volume_rows"] += int(zero_mask.loc[idx].sum())
                info["degenerate_ohlc_rows"] += int(deg_mask.loc[idx].sum())
    quality = pd.DataFrame(
        [
            {
                "artifact": "stage449_minute_bars",
                "exists": 1,
                "total_rows": int(total),
                "unique_symbols": int(len(symbols)),
                "zero_volume_rows": int(zero),
                "zero_volume_rate": float(zero / total) if total else 0.0,
                "degenerate_ohlc_rows": int(degenerate),
                "degenerate_ohlc_rate": float(degenerate / total) if total else 0.0,
                "zero_and_degenerate_rows": int(both),
                "zero_and_degenerate_rate": float(both / total) if total else 0.0,
                "positive_volume_non_degenerate_rows": int(positive_non_degenerate),
                "positive_volume_non_degenerate_rate": float(positive_non_degenerate / total) if total else 0.0,
                "has_bid_ask_columns": has_bid_ask,
                "has_last_price_column": has_last,
            }
        ]
    )
    year_quality = pd.DataFrame(year_rows.values()).sort_values("year") if year_rows else pd.DataFrame()
    if not year_quality.empty:
        year_quality["zero_volume_rate"] = year_quality["zero_volume_rows"] / year_quality["rows"]
        year_quality["degenerate_ohlc_rate"] = year_quality["degenerate_ohlc_rows"] / year_quality["rows"]
    quality.attrs["year_quality"] = year_quality
    return quality


def _anchor_year_matrix(audit: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if audit.empty:
        return pd.DataFrame(rows)
    for year, group in audit.groupby("open_year", sort=True):
        if int(year) <= 0:
            continue
        rows.append(
            {
                "year": int(year),
                "initial_opens": int(len(group)),
                "timestamp_ready": int(group["timestamp_ready"].sum()),
                "fallback_no_proxy": int(group["timestamp_ready"].eq(0).sum()),
                "raw_exact": int(group["raw_anchor_exact_official"].sum()),
                "raw_zero_degenerate": int(
                    (group["raw_anchor_zero_volume"].eq(1) & group["raw_anchor_degenerate_ohlc"].eq(1)).sum()
                ),
                "stage449_exact": int(group["stage449_anchor_exact_official"].sum()),
                "stage449_zero_degenerate": int(
                    (group["stage449_anchor_zero_volume"].eq(1) & group["stage449_anchor_degenerate_ohlc"].eq(1)).sum()
                ),
                "tq_proxy_ready": int(group["tq_proxy_anchor_ready"].sum()),
                "tq_exact": int(group["tq_price_exact_any"].sum()),
                "realized_pnl": float(group["realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _source_lineage(
    audit: pd.DataFrame,
    bar_quality: pd.DataFrame,
    stage449_status: pd.DataFrame,
) -> pd.DataFrame:
    raw_minute_files = sum(_count_files(root, ["*_minute_backtest.csv"]) for root in RAW_AUTHORITY_ROOTS)
    raw_tick_files = sum(
        _count_files(root, ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"])
        for root in RAW_AUTHORITY_ROOTS
    )
    stage449_rows = int(_safe_num(stage449_status.get("rows", pd.Series(dtype=float))).fillna(0).sum())
    total_bars = int(bar_quality["total_rows"].iloc[0]) if not bar_quality.empty else 0
    stage449_anchor_ready = int(audit["stage449_anchor_ready"].sum()) if not audit.empty else 0
    stage449_anchor_exact = int(audit["stage449_anchor_exact_official"].sum()) if not audit.empty else 0
    stage449_zero_degenerate = (
        int((audit["stage449_anchor_zero_volume"].eq(1) & audit["stage449_anchor_degenerate_ohlc"].eq(1)).sum())
        if not audit.empty
        else 0
    )
    raw_ready = int(audit["raw_anchor_ready"].sum()) if not audit.empty else 0
    raw_exact = int(audit["raw_anchor_exact_official"].sum()) if not audit.empty else 0
    tq_ready = int(audit["tq_proxy_anchor_ready"].sum()) if not audit.empty else 0
    tq_exact = int(audit["tq_price_exact_any"].sum()) if not audit.empty else 0
    rows = [
        {
            "artifact_id": "S1_stage448_449_tqsdk_backtest_60s_minute",
            "artifact_name": "Stage448/449 TqSdk backtest minute bars",
            "local_evidence_count": stage449_anchor_ready,
            "file_or_row_count": total_bars,
            "method_detected": "TqBacktest + get_kline_serial(duration_seconds=60)",
            "script_has_tqbacktest": _script_contains(STAGE448_SCRIPT, "TqBacktest"),
            "script_has_60s_kline": _script_contains(STAGE448_SCRIPT, "duration_seconds=60"),
            "script_has_tick_api": _script_contains(STAGE448_SCRIPT, "get_tick_serial"),
            "historical_2018_2026": 1,
            "same_source_price_authority": int(stage449_anchor_exact > 0),
            "anchor_exact_count": stage449_anchor_exact,
            "anchor_zero_degenerate_count": stage449_zero_degenerate,
            "nondegenerate_anchor_ready": 0,
            "tick_orderbook_ready": 0,
            "same_transform_verified": 1,
            "rule_candidate_allowed": 0,
            "decision": "price_authority_only_not_microstructure",
        },
        {
            "artifact_id": "S2_raw_authority_roots_minute_files",
            "artifact_name": "Stage452/448 raw minute roots",
            "local_evidence_count": raw_ready,
            "file_or_row_count": raw_minute_files,
            "method_detected": "cached TqSdk 60s minute CSV roots",
            "script_has_tqbacktest": 1,
            "script_has_60s_kline": 1,
            "script_has_tick_api": 0,
            "historical_2018_2026": 1,
            "same_source_price_authority": int(raw_exact > 0),
            "anchor_exact_count": raw_exact,
            "anchor_zero_degenerate_count": int(
                (audit["raw_anchor_zero_volume"].eq(1) & audit["raw_anchor_degenerate_ohlc"].eq(1)).sum()
            )
            if not audit.empty
            else 0,
            "nondegenerate_anchor_ready": 0,
            "tick_orderbook_ready": 0,
            "same_transform_verified": 1,
            "rule_candidate_allowed": 0,
            "decision": "ledger_boundary_only",
        },
        {
            "artifact_id": "S3_stage452_1455_proxy_backfill",
            "artifact_name": "Stage452 14:55 proxy backfill",
            "local_evidence_count": int(audit["route_class"].eq("stage452_raw_fallback_gap").sum()) if not audit.empty else 0,
            "file_or_row_count": raw_minute_files,
            "method_detected": "TqBacktest 60s minute + raw 14:55 VWAP fallback",
            "script_has_tqbacktest": _script_contains(STAGE452_SCRIPT, "TqBacktest"),
            "script_has_60s_kline": _script_contains(STAGE452_SCRIPT, "duration_seconds=60"),
            "script_has_tick_api": _script_contains(STAGE452_SCRIPT, "get_tick_serial"),
            "historical_2018_2026": 1,
            "same_source_price_authority": 1,
            "anchor_exact_count": int(audit["route_class"].eq("stage452_raw_fallback_gap").sum()) if not audit.empty else 0,
            "anchor_zero_degenerate_count": int(audit["route_class"].eq("stage452_raw_fallback_gap").sum())
            if not audit.empty
            else 0,
            "nondegenerate_anchor_ready": 0,
            "tick_orderbook_ready": 0,
            "same_transform_verified": 1,
            "rule_candidate_allowed": 0,
            "decision": "coverage_patch_not_alpha",
        },
        {
            "artifact_id": "S4_existing_tq_tick_batch",
            "artifact_name": "Existing Tq tick/proxy batch from Stage070-074",
            "local_evidence_count": tq_ready,
            "file_or_row_count": tq_ready,
            "method_detected": "Tq tick/top-book audit batch",
            "script_has_tqbacktest": 0,
            "script_has_60s_kline": 0,
            "script_has_tick_api": 1,
            "historical_2018_2026": 0,
            "same_source_price_authority": 0,
            "anchor_exact_count": tq_exact,
            "anchor_zero_degenerate_count": 0,
            "nondegenerate_anchor_ready": 1,
            "tick_orderbook_ready": int(tq_ready > 0),
            "same_transform_verified": 0,
            "rule_candidate_allowed": 0,
            "decision": "same_vendor_possible_but_transform_not_verified_tca_only",
        },
        {
            "artifact_id": "S5_same_source_tick_orderbook",
            "artifact_name": "Same-source tick/orderbook explaining Stage449/raw open",
            "local_evidence_count": 0,
            "file_or_row_count": raw_tick_files,
            "method_detected": "not present locally",
            "script_has_tqbacktest": 0,
            "script_has_60s_kline": 0,
            "script_has_tick_api": 0,
            "historical_2018_2026": 0,
            "same_source_price_authority": 0,
            "anchor_exact_count": 0,
            "anchor_zero_degenerate_count": 0,
            "nondegenerate_anchor_ready": 0,
            "tick_orderbook_ready": 0,
            "same_transform_verified": 0,
            "rule_candidate_allowed": 0,
            "decision": "required_but_absent",
        },
        {
            "artifact_id": "S6_fallback_no_proxy_gap",
            "artifact_name": "Fallback no-proxy initial opens",
            "local_evidence_count": int(audit["timestamp_ready"].eq(0).sum()) if not audit.empty else 0,
            "file_or_row_count": 0,
            "method_detected": "daily next open fallback without raw timestamp",
            "script_has_tqbacktest": 0,
            "script_has_60s_kline": 0,
            "script_has_tick_api": 0,
            "historical_2018_2026": 1,
            "same_source_price_authority": 0,
            "anchor_exact_count": 0,
            "anchor_zero_degenerate_count": 0,
            "nondegenerate_anchor_ready": 0,
            "tick_orderbook_ready": 0,
            "same_transform_verified": 0,
            "rule_candidate_allowed": 0,
            "decision": "coverage_gap_refill_only",
        },
    ]
    return pd.DataFrame(rows)


def _action_scorecard(source_lineage: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "action_id": "A1_tqsdk_dur0_same_vendor_tick_rebuild",
            "priority": 1,
            "action": "Use TqSdk DataDownloader dur_sec=0 or equivalent tick export for the exact Stage449 anchor windows",
            "current_local_evidence": int(
                source_lineage.loc[source_lineage["artifact_id"].eq("S4_existing_tq_tick_batch"), "local_evidence_count"].sum()
            ),
            "blocking_condition": "Stage073/074 already found Tq top-book mismatch for part of the batch; same vendor is not enough",
            "completion_gate": "aggregate tick/orderbook to the Stage449 60s transform and prove anchor exact across timestamp-ready opens",
            "can_write_rule_now": 0,
        },
        {
            "action_id": "A2_authorized_vendor_or_raw_exchange_history",
            "priority": 2,
            "action": "Acquire authorized historical tick/quote/depth data with stable symbology and exact timestamp coverage",
            "current_local_evidence": 0,
            "blocking_condition": "no local authorized tick/orderbook archive that explains Stage449/raw open",
            "completion_gate": "point-time catalog + exact replay against official open before feature extraction",
            "can_write_rule_now": 0,
        },
        {
            "action_id": "A3_no_proxy_refill",
            "priority": 3,
            "action": "Refill the 105 no-proxy initial opens with raw authority timestamps",
            "current_local_evidence": int(
                source_lineage.loc[source_lineage["artifact_id"].eq("S6_fallback_no_proxy_gap"), "local_evidence_count"].sum()
            ),
            "blocking_condition": "coverage gap; not an alpha signal",
            "completion_gate": "raw timestamp/price authority for the missing opens, still no rule based on missing/ready status",
            "can_write_rule_now": 0,
        },
        {
            "action_id": "A4_external_preentry_source",
            "priority": 4,
            "action": "Switch to external pre-entry source only if it is point-time, complete, and not final-PnL-derived",
            "current_local_evidence": 0,
            "blocking_condition": "no current source catalog proving complete point-time coverage",
            "completion_gate": "coverage and release-time audit before any strategy hypothesis",
            "can_write_rule_now": 0,
        },
    ]
    return pd.DataFrame(rows)


def _official_metrics(summary: pd.DataFrame, curve: pd.DataFrame) -> dict[str, float]:
    if not summary.empty:
        row = summary.iloc[0]
        return {
            "end_equity": _safe_float(row.get("end_equity"), np.nan),
            "total_return_pct": _safe_float(row.get("total_return_pct"), np.nan),
            "max_drawdown_pct": _safe_float(row.get("max_drawdown_pct"), np.nan),
            "sharpe": _safe_float(row.get("sharpe"), np.nan),
            "total_slippage": _safe_float(row.get("total_slippage"), np.nan),
            "total_trade_count": _safe_float(row.get("total_trade_count"), np.nan),
            "closed_lot_win_rate_pct": _safe_float(row.get("closed_lot_win_rate_pct"), np.nan),
            "max_broker10_margin_to_equity_pct": _safe_float(row.get("max_broker10_margin_to_equity_pct"), np.nan),
        }
    curve = curve.copy()
    curve["official_equity"] = _safe_num(curve.get("official_equity", curve.get("account_equity", pd.Series(dtype=float))))
    end_equity = float(curve["official_equity"].dropna().iloc[-1]) if curve["official_equity"].notna().any() else np.nan
    total_return_pct = (end_equity / INITIAL_CAPITAL - 1.0) * 100 if np.isfinite(end_equity) else np.nan
    dd = _safe_num(curve.get("official_drawdown_pct", curve.get("drawdown_pct", pd.Series(dtype=float))))
    return {
        "end_equity": end_equity,
        "total_return_pct": float(total_return_pct),
        "max_drawdown_pct": float(dd.min()) if dd.notna().any() else np.nan,
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": np.nan,
    }


def _plot_official_path(curve: pd.DataFrame, audit: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve["official_equity"] = _safe_num(curve.get("official_equity", curve.get("account_equity", pd.Series(dtype=float))))
    curve["official_drawdown_pct"] = _safe_num(
        curve.get("official_drawdown_pct", curve.get("drawdown_pct", pd.Series(dtype=float)))
    )
    audit = audit.dropna(subset=["official_open_date"]).sort_values(["official_open_date", "official_open_trade_id"]).copy()
    classes = [
        "stage449_raw_price_boundary",
        "stage452_raw_fallback_gap",
        "fallback_no_proxy_gap",
        "raw_price_boundary_other",
    ]
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=False)
    axes[0].plot(curve["date"], curve["official_equity"], color="#1f77b4", linewidth=1.6, label="official equity")
    axes[0].set_title("Stage077 official equity baseline")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left")

    axes[1].plot(curve["date"], curve["official_drawdown_pct"], color="#b22222", linewidth=1.2, label="official DD")
    axes[1].axhline(-40, color="#666666", linestyle="--", linewidth=0.8)
    axes[1].set_title("official drawdown")
    axes[1].set_ylabel("DD %")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="lower left")

    for cls in classes:
        part = audit[audit["route_class"].eq(cls)].copy()
        if part.empty:
            continue
        daily = part.groupby("official_open_date", sort=True)["realized_pnl"].sum().cumsum()
        axes[2].plot(daily.index, daily.values, linewidth=1.3, label=cls)
    axes[2].axhline(0, color="#333333", linewidth=0.8)
    axes[2].set_title("initial-open realized PnL contribution by provenance class")
    axes[2].set_ylabel("cum PnL")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_readiness_atlas(source_lineage: pd.DataFrame) -> None:
    cols = [
        "historical_2018_2026",
        "same_source_price_authority",
        "nondegenerate_anchor_ready",
        "tick_orderbook_ready",
        "same_transform_verified",
        "rule_candidate_allowed",
    ]
    mat = source_lineage.set_index("artifact_id")[cols].astype(float)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    im = ax.imshow(mat.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(mat.index)))
    ax.set_yticklabels(mat.index)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{int(mat.iloc[i, j])}", ha="center", va="center", color="black", fontsize=9)
    ax.set_title("Stage077 provenance readiness atlas")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_ATLAS_OUT, dpi=160)
    plt.close(fig)


def _plot_bar_quality(bar_quality: pd.DataFrame, audit: pd.DataFrame, action_scorecard: pd.DataFrame) -> None:
    q = bar_quality.iloc[0].to_dict() if not bar_quality.empty else {}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    event_labels = [
        "initial opens",
        "timestamp ready",
        "raw exact",
        "raw zero+deg",
        "stage449 exact",
        "stage449 zero+deg",
        "no proxy",
        "same-source tick files",
    ]
    event_values = [
        len(audit),
        int(audit["timestamp_ready"].sum()),
        int(audit["raw_anchor_exact_official"].sum()),
        int((audit["raw_anchor_zero_volume"].eq(1) & audit["raw_anchor_degenerate_ohlc"].eq(1)).sum()),
        int(audit["stage449_anchor_exact_official"].sum()),
        int((audit["stage449_anchor_zero_volume"].eq(1) & audit["stage449_anchor_degenerate_ohlc"].eq(1)).sum()),
        int(audit["timestamp_ready"].eq(0).sum()),
        sum(
            _count_files(root, ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"])
            for root in RAW_AUTHORITY_ROOTS
        ),
    ]
    axes[0].barh(event_labels, event_values, color="#4c78a8")
    axes[0].set_title("anchor evidence counts")
    axes[0].grid(axis="x", alpha=0.25)

    quality_labels = ["zero volume", "degenerate OHLC", "zero+deg", "pos vol nondeg"]
    quality_values = [
        q.get("zero_volume_rate", 0.0),
        q.get("degenerate_ohlc_rate", 0.0),
        q.get("zero_and_degenerate_rate", 0.0),
        q.get("positive_volume_non_degenerate_rate", 0.0),
    ]
    axes[1].bar(quality_labels, quality_values, color=["#e45756", "#f58518", "#b279a2", "#54a24b"])
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Stage449 all-bar quality rates")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].grid(axis="y", alpha=0.25)

    actions = action_scorecard.sort_values("priority")
    axes[2].barh(actions["action_id"], actions["can_write_rule_now"], color="#54a24b")
    axes[2].set_xlim(0, 1)
    axes[2].set_title("rule permission by next action")
    axes[2].grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BAR_QUALITY_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_lineage: pd.DataFrame,
    action_scorecard: pd.DataFrame,
    bar_quality: pd.DataFrame,
    anchor_year: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage077 raw authority provenance / tick backfill feasibility",
        "",
        f"- decision: `{decision['decision']}`",
        f"- next_step: `{decision['next_step']}`",
        f"- official_live_version: `{OFFICIAL_LIVE_VERSION}`",
        "",
        "## summary",
        "",
        _md_table(summary),
        "",
        "## source lineage",
        "",
        _md_table(
            source_lineage[
                [
                    "artifact_id",
                    "local_evidence_count",
                    "file_or_row_count",
                    "same_source_price_authority",
                    "nondegenerate_anchor_ready",
                    "tick_orderbook_ready",
                    "same_transform_verified",
                    "rule_candidate_allowed",
                    "decision",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## action scorecard",
        "",
        _md_table(action_scorecard, max_rows=20),
        "",
        "## bar quality",
        "",
        _md_table(bar_quality),
        "",
        "## year anchor matrix",
        "",
        _md_table(anchor_year, max_rows=20),
        "",
        "## conclusion",
        "",
        "- Stage448/449 的 raw authority 来源链是 TqSdk backtest 60s K 线缓存，不是本地 tick/orderbook 历史库。",
        "- Stage449 能解释官方 open price，但 initial-open anchor 全部是 zero-volume/OHLC-flat price proxy，不能支持 body/range/volume/spread/depth/imbalance 规则。",
        "- 现有 Tq tick 批次只能证明同 vendor 的另一种数据形态可用于 TCA；Stage073/074 已显示部分 top-book 与 official/raw open 不一致，不能直接交易化。",
        "- 下一步只能获取同源 tick/orderbook 并复验 Stage449 60s transform exact，或转向完整点时化外生入场前源。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _read_csv(STAGE045_CURVE_IN)
    stage074 = _read_csv(STAGE074_AUDIT_IN)
    stage076_summary = _read_csv(STAGE076_SUMMARY_IN)
    stage449_status = _read_csv(STAGE449_STATUS_IN)
    if not STAGE449_DETAIL_IN.exists():
        raise RuntimeError(f"missing required input: {STAGE449_DETAIL_IN}")

    audit = _prepare_audit(stage074)
    bar_quality = _stage449_bar_quality()
    anchor_year = _anchor_year_matrix(audit)
    source_lineage = _source_lineage(audit, bar_quality, stage449_status)
    action_scorecard = _action_scorecard(source_lineage)
    metrics = _official_metrics(stage076_summary, curve)

    raw_tick_files = int(
        sum(
            _count_files(root, ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"])
            for root in RAW_AUTHORITY_ROOTS
        )
    )
    same_source_tick_ready = int(
        source_lineage.loc[source_lineage["artifact_id"].eq("S5_same_source_tick_orderbook"), "tick_orderbook_ready"].sum()
    )
    rule_allowed = int(source_lineage["rule_candidate_allowed"].sum())
    tq_ready = int(audit["tq_proxy_anchor_ready"].sum())
    tq_exact = int(audit["tq_price_exact_any"].sum())
    tq_mismatch = int(tq_ready - tq_exact)
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "decision": "stage077_r2_requires_same_source_tick_transform_no_rule",
                "next_step": "acquire_same_source_tick_or_authorized_external_preentry_source_before_rules",
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
                "initial_opens": int(len(audit)),
                "timestamp_ready": int(audit["timestamp_ready"].sum()),
                "fallback_no_proxy": int(audit["timestamp_ready"].eq(0).sum()),
                "stage449_anchor_exact": int(audit["stage449_anchor_exact_official"].sum()),
                "stage449_anchor_zero_degenerate": int(
                    (audit["stage449_anchor_zero_volume"].eq(1) & audit["stage449_anchor_degenerate_ohlc"].eq(1)).sum()
                ),
                "raw_anchor_exact": int(audit["raw_anchor_exact_official"].sum()),
                "raw_anchor_zero_degenerate": int(
                    (audit["raw_anchor_zero_volume"].eq(1) & audit["raw_anchor_degenerate_ohlc"].eq(1)).sum()
                ),
                "raw_authority_tick_file_count": raw_tick_files,
                "same_source_tick_orderbook_ready": same_source_tick_ready,
                "tq_proxy_ready": tq_ready,
                "tq_proxy_exact": tq_exact,
                "tq_proxy_mismatch": tq_mismatch,
                "rule_candidate_allowed_source_count": rule_allowed,
                "stage449_total_bar_rows": int(bar_quality["total_rows"].iloc[0]),
                "stage449_zero_volume_rate": float(bar_quality["zero_volume_rate"].iloc[0]),
                "stage449_degenerate_ohlc_rate": float(bar_quality["degenerate_ohlc_rate"].iloc[0]),
                "end_equity": metrics["end_equity"],
                "total_return_pct": metrics["total_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "sharpe": metrics["sharpe"],
                "total_slippage": metrics["total_slippage"],
                "total_trade_count": metrics["total_trade_count"],
                "closed_lot_win_rate_pct": metrics["closed_lot_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": metrics["max_broker10_margin_to_equity_pct"],
            }
        ]
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage077_r2_requires_same_source_tick_transform_no_rule",
        "next_step": "acquire_same_source_tick_or_authorized_external_preentry_source_before_rules",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "initial_opens": int(summary["initial_opens"].iloc[0]),
        "timestamp_ready": int(summary["timestamp_ready"].iloc[0]),
        "fallback_no_proxy": int(summary["fallback_no_proxy"].iloc[0]),
        "stage449_anchor_exact": int(summary["stage449_anchor_exact"].iloc[0]),
        "stage449_anchor_zero_degenerate": int(summary["stage449_anchor_zero_degenerate"].iloc[0]),
        "raw_authority_tick_file_count": raw_tick_files,
        "same_source_tick_orderbook_ready": same_source_tick_ready,
        "tq_proxy_ready": tq_ready,
        "tq_proxy_mismatch": tq_mismatch,
        "rule_candidate_allowed_source_count": rule_allowed,
        "outputs": {
            "summary": SUMMARY_OUT,
            "decision": DECISION_OUT,
            "source_lineage": SOURCE_LINEAGE_OUT,
            "action_scorecard": ACTION_SCORECARD_OUT,
            "bar_quality": BAR_QUALITY_OUT,
            "anchor_year_matrix": ANCHOR_YEAR_MATRIX_OUT,
            "official_path_chart": OFFICIAL_PATH_CHART_OUT,
            "readiness_atlas": READINESS_ATLAS_OUT,
            "bar_quality_chart": BAR_QUALITY_CHART_OUT,
            "report": REPORT_OUT,
        },
    }

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(source_lineage, SOURCE_LINEAGE_OUT)
    _write_csv(action_scorecard, ACTION_SCORECARD_OUT)
    _write_csv(bar_quality, BAR_QUALITY_OUT)
    _write_csv(anchor_year, ANCHOR_YEAR_MATRIX_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_official_path(curve, audit)
    _plot_readiness_atlas(source_lineage)
    _plot_bar_quality(bar_quality, audit, action_scorecard)
    _write_report(summary, source_lineage, action_scorecard, bar_quality, anchor_year, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
