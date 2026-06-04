from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage587_stage526_live_tca_bridge_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage587_stage526_live_tca_bridge_dry_run"

STAGE575_TAG = "stage575_stage526_live_execution_p0_watchlist_v1"
STAGE575_PREFIX = "qmt_roll_stage575_stage526_live_execution_p0_watchlist"
STAGE575_TEMPLATE = OUTPUT_DIR / f"{STAGE575_PREFIX}_live_p0_evidence_template_{STAGE575_TAG}.csv"

INTENT_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intent_ledger_{MODEL_TAG}.csv"
RAW_SOURCES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_event_sources_{MODEL_TAG}.csv"
ORDER_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_order_summary_{MODEL_TAG}.csv"
TRADE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_trade_summary_{MODEL_TAG}.csv"
MECHANICAL_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mechanical_non_p0_reducer_summary_{MODEL_TAG}.csv"
LIVE_TCA_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_tca_ledger_{MODEL_TAG}.csv"
JOIN_ATTEMPTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_join_attempts_{MODEL_TAG}.csv"
FIELD_COMPLETENESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_completeness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
BRIDGE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bridge_contract_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_SYMBOLS = {"fu2509.SHFE", "lc2505.GFEX", "AP505.CZCE"}
REQUIRED_VALID_SAMPLES_PER_P0 = 3
MAX_VWAP_COST_BPS = 50.0
MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0
MAX_PARTICIPATION_PCT = 25.0

REQUIRED_ACTUAL_FIELDS = [
    "signal_generated_at",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "order_type",
    "limit_price",
    "fill_first_at",
    "fill_last_at",
    "avg_fill_price",
    "filled_volume",
    "cancelled_volume",
    "unfilled_volume",
    "commission_cash",
    "actual_slippage_cash",
    "actual_implementation_shortfall_bps",
    "actual_vs_window_vwap_bps",
    "account_equity_before",
    "broker_margin_before",
]

STAGE526_REFERENCE = {
    "ending_equity": 23_369_505,
    "total_return_pct": 3699.9195,
    "max_drawdown_pct": -36.2670,
    "sharpe": 1.6385,
    "ulcer": 14.4691,
    "total_slippage": 1_342_190,
    "trade_count": 905,
    "win_rate_pct": 53.6330,
}


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _num_scalar(value: Any, default: float = 0.0) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed) or math.isinf(float(parsed)):
        return default
    return float(parsed)


def _present_scalar(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() != ""


def _first_present(series: pd.Series) -> Any:
    if series.empty:
        return ""
    values = series.dropna()
    values = values[values.astype(str).str.strip().ne("")]
    if values.empty:
        return ""
    return values.iloc[0]


def _last_present(series: pd.Series) -> Any:
    if series.empty:
        return ""
    values = series.dropna()
    values = values[values.astype(str).str.strip().ne("")]
    if values.empty:
        return ""
    return values.iloc[-1]


def _gate_row(gate: str, passed: bool, actual: str, required: str, severity: str, judgement: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": int(bool(passed)),
        "actual": actual,
        "required": required,
        "severity": severity,
        "judgement": judgement,
    }


def build_intent_ledger(template: pd.DataFrame) -> pd.DataFrame:
    intent = template.copy()
    for column in REQUIRED_ACTUAL_FIELDS:
        if column not in intent.columns:
            intent[column] = ""
    intent["bridge_signal_id"] = intent.apply(
        lambda row: (
            f"stage526_event_{int(_num_scalar(row.get('event_id'), 0))}_"
            f"{str(row.get('date', ''))}_{str(row.get('vt_symbol', ''))}_"
            f"{str(row.get('offset_type', ''))}_{str(row.get('execution_side', ''))}"
        ),
        axis=1,
    )
    intent["bridge_expected_join_key"] = "bridge_signal_id + vt_orderid"
    intent["bridge_vt_orderid"] = ""
    intent["bridge_status"] = "intent_loaded_waiting_for_live_submit_mapping"
    intent["bridge_note"] = "dry_run_only_no_ctp_connection_no_order_api_call"
    return intent


def _event_type_from_name(path: Path) -> str | None:
    lower = path.name.lower()
    if "orders" in lower:
        return "orders"
    if "trades" in lower:
        return "trades"
    if "ticks" in lower:
        return "ticks"
    if "accounts" in lower:
        return "accounts"
    if "positions" in lower:
        return "positions"
    return None


def _is_raw_ctp_candidate(path: Path) -> bool:
    lower = path.name.lower()
    if OUTPUT_PREFIX.lower() in lower:
        return False
    raw_keywords = ("simnow", "ctp", "open_close_proof", "smoke_order", "disconnect_proof")
    if not any(key in lower for key in raw_keywords):
        return False
    return _event_type_from_name(path) is not None


def discover_raw_sources() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    paths = sorted(path for path in OUTPUT_DIR.glob("*.csv") if _is_raw_ctp_candidate(path))
    frames: dict[str, list[pd.DataFrame]] = {key: [] for key in ["orders", "trades", "ticks", "accounts", "positions"]}
    rows: list[dict[str, Any]] = []
    for path in paths:
        event_type = _event_type_from_name(path)
        if event_type is None:
            continue
        try:
            frame = _read_csv(path)
            status = "ok"
            error = ""
        except Exception as exc:  # noqa: BLE001
            frame = pd.DataFrame()
            status = "read_error"
            error = f"{type(exc).__name__}: {exc}"
        if not frame.empty:
            frame = frame.copy()
            frame["source_file"] = _relative(path)
            frames[event_type].append(frame)
        vt_symbol_count = int(frame["vt_symbol"].dropna().astype(str).nunique()) if "vt_symbol" in frame.columns else 0
        p0_row_count = int(frame["vt_symbol"].fillna("").astype(str).isin(P0_SYMBOLS).sum()) if "vt_symbol" in frame.columns else 0
        rows.append(
            {
                "source_file": _relative(path),
                "event_type": event_type,
                "status": status,
                "error": error,
                "row_count": int(len(frame)),
                "column_count": int(len(frame.columns)),
                "vt_symbol_count": vt_symbol_count,
                "p0_row_count": p0_row_count,
                "columns": ",".join(map(str, frame.columns[:40])),
            }
        )
    combined = {key: (pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame()) for key, value in frames.items()}
    return pd.DataFrame(rows), combined


def summarize_orders(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty or "vt_orderid" not in orders.columns:
        return pd.DataFrame()
    frame = orders.copy()
    frame["vt_orderid"] = frame["vt_orderid"].fillna("").astype(str)
    frame = frame[frame["vt_orderid"].str.strip().ne("")].copy()
    if frame.empty:
        return pd.DataFrame()
    dedupe_cols = [col for col in ["vt_orderid", "status", "price", "volume", "traded", "datetime", "vt_symbol"] if col in frame.columns]
    if dedupe_cols:
        frame = frame.drop_duplicates(subset=dedupe_cols).copy()
    frame["_datetime_sort"] = pd.to_datetime(frame.get("datetime", pd.Series("", index=frame.index)), errors="coerce")
    status_text = frame.get("status", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    frame["_status_rank"] = np.select(
        [
            status_text.str.contains("all traded|全部成交"),
            status_text.str.contains("part traded|部分成交"),
            status_text.str.contains("cancel|撤"),
            status_text.str.contains("reject|拒"),
            status_text.str.contains("not traded|未成交"),
            status_text.str.contains("submitting|提交"),
        ],
        [6, 5, 4, 4, 2, 1],
        default=0,
    )
    frame = frame.sort_values(["vt_orderid", "_datetime_sort"], kind="mergesort")
    rows: list[dict[str, Any]] = []
    for vt_orderid, group in frame.groupby("vt_orderid", sort=False):
        terminal = group.sort_values(["_datetime_sort", "_status_rank"], kind="mergesort").iloc[-1]
        volume = float(pd.to_numeric(group.get("volume", pd.Series(index=group.index, dtype=float)), errors="coerce").fillna(0.0).max())
        traded = float(pd.to_numeric(group.get("traded", pd.Series(index=group.index, dtype=float)), errors="coerce").fillna(0.0).max())
        status = str(terminal.get("status", ""))
        if volume > 0 and traded >= volume and not (
            "traded" in status.lower() or "成交" in status or "cancel" in status.lower() or "撤" in status or "reject" in status.lower() or "拒" in status
        ):
            status = f"{status}|filled_inferred_from_order_traded"
        cancelled = max(volume - traded, 0.0) if "cancel" in status.lower() else 0.0
        rows.append(
            {
                "vt_orderid": vt_orderid,
                "vt_symbol": str(terminal.get("vt_symbol", _last_present(group.get("vt_symbol", pd.Series(index=group.index, dtype=object))))),
                "order_submit_at": str(_first_present(group.get("datetime", pd.Series(index=group.index, dtype=object)))),
                "order_submit_price": _num_scalar(_first_present(group.get("price", pd.Series(index=group.index, dtype=object)))),
                "order_type": str(_first_present(group.get("type", pd.Series(index=group.index, dtype=object)))),
                "limit_price": _num_scalar(_first_present(group.get("price", pd.Series(index=group.index, dtype=object)))),
                "order_volume": volume,
                "order_traded_latest": traded,
                "order_status_latest": status,
                "cancelled_volume_inferred": cancelled,
                "unfilled_volume_inferred": max(volume - traded, 0.0),
                "direction": str(_last_present(group.get("direction", pd.Series(index=group.index, dtype=object)))),
                "offset": str(_last_present(group.get("offset", pd.Series(index=group.index, dtype=object)))),
                "row_count": int(len(group)),
                "source_files": ";".join(sorted(set(group["source_file"].dropna().astype(str)))) if "source_file" in group.columns else "",
            }
        )
    return pd.DataFrame(rows)


def summarize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    if "vt_orderid" not in frame.columns:
        if {"gateway_name", "orderid"}.issubset(frame.columns):
            frame["vt_orderid"] = frame["gateway_name"].fillna("").astype(str) + "." + frame["orderid"].fillna("").astype(str)
        elif "orderid" in frame.columns:
            frame["vt_orderid"] = frame["orderid"].fillna("").astype(str)
        else:
            return pd.DataFrame()
    frame["vt_orderid"] = frame["vt_orderid"].fillna("").astype(str)
    frame = frame[frame["vt_orderid"].str.strip().ne("")].copy()
    if frame.empty:
        return pd.DataFrame()
    dedupe_cols = [col for col in ["vt_orderid", "tradeid", "price", "volume", "datetime", "vt_symbol"] if col in frame.columns]
    if dedupe_cols:
        frame = frame.drop_duplicates(subset=dedupe_cols).copy()
    frame["_datetime_sort"] = pd.to_datetime(frame.get("datetime", pd.Series("", index=frame.index)), errors="coerce")
    frame = frame.sort_values(["vt_orderid", "_datetime_sort"], kind="mergesort")
    rows: list[dict[str, Any]] = []
    for vt_orderid, group in frame.groupby("vt_orderid", sort=False):
        prices = pd.to_numeric(group.get("price", pd.Series(index=group.index, dtype=float)), errors="coerce")
        volumes = pd.to_numeric(group.get("volume", pd.Series(index=group.index, dtype=float)), errors="coerce").fillna(0.0)
        valid = prices.notna() & volumes.gt(0)
        filled_volume = float(volumes[valid].sum()) if valid.any() else 0.0
        avg_fill_price = float((prices[valid] * volumes[valid]).sum() / filled_volume) if filled_volume > 0 else np.nan
        rows.append(
            {
                "vt_orderid": vt_orderid,
                "vt_symbol": str(_last_present(group.get("vt_symbol", pd.Series(index=group.index, dtype=object)))),
                "fill_first_at": str(_first_present(group.get("datetime", pd.Series(index=group.index, dtype=object)))),
                "fill_last_at": str(_last_present(group.get("datetime", pd.Series(index=group.index, dtype=object)))),
                "avg_fill_price": avg_fill_price,
                "filled_volume": filled_volume,
                "trade_count": int(len(group)),
                "trade_ids": ";".join(map(str, group.get("tradeid", pd.Series(index=group.index, dtype=object)).dropna().astype(str).tolist())),
                "source_files": ";".join(sorted(set(group["source_file"].dropna().astype(str)))) if "source_file" in group.columns else "",
            }
        )
    return pd.DataFrame(rows)


def build_mechanical_non_p0_summary(order_summary: pd.DataFrame, trade_summary: pd.DataFrame) -> pd.DataFrame:
    if order_summary.empty or trade_summary.empty:
        return pd.DataFrame()
    joined = order_summary.merge(trade_summary, on="vt_orderid", how="inner", suffixes=("_order", "_trade"))
    if joined.empty:
        return joined
    joined["is_stage526_p0_symbol"] = joined["vt_symbol_order"].fillna("").astype(str).isin(P0_SYMBOLS).astype(int)
    joined["filled_volume_ok"] = (pd.to_numeric(joined["filled_volume"], errors="coerce").fillna(0.0) > 0.0).astype(int)
    joined["unfilled_volume"] = pd.to_numeric(joined["unfilled_volume_inferred"], errors="coerce").fillna(0.0)
    joined["cancelled_volume"] = pd.to_numeric(joined["cancelled_volume_inferred"], errors="coerce").fillna(0.0)
    joined["mechanical_reducer_status"] = np.where(
        joined["is_stage526_p0_symbol"].astype(bool),
        "raw_p0_symbol_candidate_not_intent_joined",
        "non_p0_mechanical_reducer_ok_not_stage526_evidence",
    )
    columns = [
        "vt_orderid",
        "vt_symbol_order",
        "order_submit_at",
        "order_submit_price",
        "order_type",
        "limit_price",
        "order_volume",
        "order_traded_latest",
        "order_status_latest",
        "fill_first_at",
        "fill_last_at",
        "avg_fill_price",
        "filled_volume",
        "unfilled_volume",
        "cancelled_volume",
        "trade_count",
        "is_stage526_p0_symbol",
        "mechanical_reducer_status",
    ]
    return joined[[col for col in columns if col in joined.columns]].copy()


def build_live_tca_ledger(intent: pd.DataFrame, order_summary: pd.DataFrame, trade_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    order_by_id = order_summary.set_index("vt_orderid") if not order_summary.empty and "vt_orderid" in order_summary.columns else pd.DataFrame()
    trade_by_id = trade_summary.set_index("vt_orderid") if not trade_summary.empty and "vt_orderid" in trade_summary.columns else pd.DataFrame()

    for _, intent_row in intent.iterrows():
        row = intent_row.to_dict()
        explicit_vt_orderid = str(row.get("bridge_vt_orderid") or row.get("vt_orderid") or "").strip()
        matched_order = explicit_vt_orderid and not order_by_id.empty and explicit_vt_orderid in order_by_id.index
        matched_trade = explicit_vt_orderid and not trade_by_id.empty and explicit_vt_orderid in trade_by_id.index
        blockers: list[str] = []
        if not explicit_vt_orderid:
            blockers.append("missing_explicit_vt_orderid_mapping")
        if explicit_vt_orderid and not matched_order:
            blockers.append("mapped_vt_orderid_not_found_in_raw_orders")
        if explicit_vt_orderid and not matched_trade:
            blockers.append("mapped_vt_orderid_not_found_in_raw_trades")

        if matched_order:
            order_match = order_by_id.loc[explicit_vt_orderid]
            if isinstance(order_match, pd.DataFrame):
                order_match = order_match.iloc[-1]
            row["order_submit_at"] = order_match.get("order_submit_at", row.get("order_submit_at", ""))
            row["order_submit_price"] = order_match.get("order_submit_price", row.get("order_submit_price", ""))
            row["order_type"] = order_match.get("order_type", row.get("order_type", ""))
            row["limit_price"] = order_match.get("limit_price", row.get("limit_price", ""))
            row["cancelled_volume"] = order_match.get("cancelled_volume_inferred", row.get("cancelled_volume", ""))
            row["unfilled_volume"] = order_match.get("unfilled_volume_inferred", row.get("unfilled_volume", ""))
        if matched_trade:
            trade_match = trade_by_id.loc[explicit_vt_orderid]
            if isinstance(trade_match, pd.DataFrame):
                trade_match = trade_match.iloc[-1]
            row["fill_first_at"] = trade_match.get("fill_first_at", row.get("fill_first_at", ""))
            row["fill_last_at"] = trade_match.get("fill_last_at", row.get("fill_last_at", ""))
            row["avg_fill_price"] = trade_match.get("avg_fill_price", row.get("avg_fill_price", ""))
            row["filled_volume"] = trade_match.get("filled_volume", row.get("filled_volume", ""))

        for field in REQUIRED_ACTUAL_FIELDS:
            if not _present_scalar(row.get(field)):
                blockers.append(f"missing_{field}")

        filled = _num_scalar(row.get("filled_volume"), default=np.nan)
        order_volume = _num_scalar(row.get("order_volume"), default=0.0)
        unfilled = _num_scalar(row.get("unfilled_volume"), default=np.nan)
        avg_fill = _num_scalar(row.get("avg_fill_price"), default=np.nan)
        vwap_bps = _num_scalar(row.get("actual_vs_window_vwap_bps"), default=np.nan)
        shortfall_bps = _num_scalar(row.get("actual_implementation_shortfall_bps"), default=np.nan)
        target_window_volume = _num_scalar(row.get("target_close_window_volume"), default=0.0)
        participation = (filled / target_window_volume * 100.0) if target_window_volume > 0.0 and not math.isnan(filled) else np.nan

        if math.isnan(avg_fill) or avg_fill <= 0:
            blockers.append("avg_fill_price_not_positive")
        if math.isnan(filled) or filled <= 0:
            blockers.append("filled_volume_not_positive")
        elif order_volume > 0 and filled < order_volume:
            blockers.append("filled_less_than_order_volume")
        if math.isnan(unfilled) or unfilled != 0:
            blockers.append("unfilled_volume_not_zero")
        if math.isnan(vwap_bps) or vwap_bps > MAX_VWAP_COST_BPS:
            blockers.append("actual_vs_window_vwap_bps_missing_or_gt50")
        if math.isnan(shortfall_bps) or shortfall_bps > MAX_IMPLEMENTATION_SHORTFALL_BPS:
            blockers.append("actual_implementation_shortfall_missing_or_gt75")
        if math.isnan(participation) or participation > MAX_PARTICIPATION_PCT:
            blockers.append("participation_missing_or_gt25pct")

        row["actual_participation_pct"] = "" if math.isnan(participation) else participation
        row["bridge_join_status"] = "joined_order_trade" if matched_order and matched_trade else "not_joined"
        row["valid_live_tca_sample"] = 0 if blockers else 1
        row["bridge_blockers"] = ";".join(sorted(set(blockers)))
        rows.append(row)
        attempts.append(
            {
                "event_id": row.get("event_id"),
                "date": row.get("date"),
                "vt_symbol": row.get("vt_symbol"),
                "watch_priority": row.get("watch_priority"),
                "bridge_signal_id": row.get("bridge_signal_id"),
                "explicit_vt_orderid": explicit_vt_orderid,
                "matched_order": int(bool(matched_order)),
                "matched_trade": int(bool(matched_trade)),
                "valid_live_tca_sample": int(row["valid_live_tca_sample"]),
                "blockers": row["bridge_blockers"],
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(attempts)


def build_field_completeness(ledger: pd.DataFrame) -> pd.DataFrame:
    p0_mask = ledger["watch_priority"].fillna("").astype(str).str.startswith("P0") if "watch_priority" in ledger.columns else pd.Series(False, index=ledger.index)
    rows = []
    for field in REQUIRED_ACTUAL_FIELDS + ["actual_participation_pct", "bridge_vt_orderid"]:
        all_count = int(ledger[field].apply(_present_scalar).sum()) if field in ledger.columns else 0
        p0_count = int(ledger.loc[p0_mask, field].apply(_present_scalar).sum()) if field in ledger.columns else 0
        rows.append(
            {
                "field": field,
                "all_nonempty": all_count,
                "all_total": int(len(ledger)),
                "p0_nonempty": p0_count,
                "p0_total": int(p0_mask.sum()),
                "all_fill_rate_pct": round(all_count / len(ledger) * 100, 4) if len(ledger) else 0.0,
                "p0_fill_rate_pct": round(p0_count / int(p0_mask.sum()) * 100, 4) if int(p0_mask.sum()) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_gates(
    intent: pd.DataFrame,
    raw_sources: pd.DataFrame,
    mechanical: pd.DataFrame,
    ledger: pd.DataFrame,
    field_completeness: pd.DataFrame,
) -> pd.DataFrame:
    p0_mask = ledger["watch_priority"].fillna("").astype(str).str.startswith("P0")
    p0_valid = int(pd.to_numeric(ledger.loc[p0_mask, "valid_live_tca_sample"], errors="coerce").fillna(0).sum())
    p0_total_required = len(P0_SYMBOLS) * REQUIRED_VALID_SAMPLES_PER_P0
    explicit_map_count = int(ledger["bridge_vt_orderid"].apply(_present_scalar).sum()) if "bridge_vt_orderid" in ledger.columns else 0
    p0_joined = int(ledger.loc[p0_mask, "bridge_join_status"].fillna("").astype(str).eq("joined_order_trade").sum())
    p0_actual_fields_complete = int((field_completeness["p0_nonempty"] >= field_completeness["p0_total"]).sum())
    raw_rows = int(pd.to_numeric(raw_sources.get("row_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not raw_sources.empty else 0
    mechanical_joined = int(len(mechanical))
    return pd.DataFrame(
        [
            _gate_row("dry_run_no_ctp_connection", True, "true", "true", "hard", "script only reads local files"),
            _gate_row("send_order_api_called_count_zero", True, "0", "0", "hard", "no broker API path in script"),
            _gate_row("stage575_intent_loaded", len(intent) > 0, str(len(intent)), ">0", "hard", "intent ledger exists"),
            _gate_row("p0_intents_loaded", int(p0_mask.sum()) >= len(P0_SYMBOLS), str(int(p0_mask.sum())), f">={len(P0_SYMBOLS)}", "hard", "P0 rows exist"),
            _gate_row("raw_ctp_event_sources_scanned", raw_rows > 0, f"{len(raw_sources)} files / {raw_rows} rows", ">0 rows", "hard", "raw local CTP/SimNow files found"),
            _gate_row("mechanical_non_p0_order_trade_reducer_ok", mechanical_joined > 0, str(mechanical_joined), ">0 joined orders", "medium", "reducer can join existing non-P0 test orders/trades"),
            _gate_row("explicit_stage526_vt_orderid_mapping_present", explicit_map_count > 0, str(explicit_map_count), ">0", "hard", "submit bridge not yet wired"),
            _gate_row("p0_order_trade_joined", p0_joined > 0, str(p0_joined), ">0", "hard", "no P0 order/trade join yet"),
            _gate_row("p0_actual_tca_fields_complete", p0_actual_fields_complete >= len(REQUIRED_ACTUAL_FIELDS), f"{p0_actual_fields_complete}/{len(REQUIRED_ACTUAL_FIELDS) + 2}", "all required fields", "hard", "P0 actual fields remain blank"),
            _gate_row("p0_valid_live_samples_complete", p0_valid >= p0_total_required, f"{p0_valid}/{p0_total_required}", f">={p0_total_required}", "hard", "P0 sample gate remains open"),
            _gate_row("zero_execution_bias_claim_allowed", False, "not allowed", "allowed only after P0 sample gate", "hard", "Stage526 remains normal-cost candidate"),
        ]
    )


def write_bridge_contract() -> None:
    text = f"""# Stage587 Dry-run Live TCA Bridge Contract

## Scope

This contract is for a dry-run ledger bridge. It does not connect to CTP and does not call `send_order`.

## Required input streams

1. Intent rows from Stage575 live template:
   - `event_id`, `date`, `vt_symbol`, `product_vt_symbol`, `offset_type`, `execution_side`, `order_volume`, `backtest_fill_price`, `minute_last15_vwap`.
2. Submit bridge row, written only by a future dry-run/pre-submit adapter:
   - `bridge_signal_id`, `vt_orderid`, `order_submit_at`, `order_submit_price`, `order_type`, `limit_price`, `account_equity_before`, `broker_margin_before`.
3. vn.py events:
   - `EVENT_ORDER`: latest status, volume, traded, cancelled/rejected state.
   - `EVENT_TRADE`: fill timestamps, fill price, fill volume, trade id.
   - `EVENT_TICK` or independent minute bars: benchmark VWAP and participation denominator.

## Non-negotiable rule

No `vt_orderid`, no join. The bridge must not infer Stage526 P0 evidence from same-symbol or same-day rows alone.

## P0 close criteria

Each of `fu2509.SHFE`, `lc2505.GFEX`, and `AP505.CZCE` needs `{REQUIRED_VALID_SAMPLES_PER_P0}` valid samples:

- filled/order volume = 100%
- unfilled = 0
- actual vs window VWAP <= {MAX_VWAP_COST_BPS:.0f} bps
- implementation shortfall <= {MAX_IMPLEMENTATION_SHORTFALL_BPS:.0f} bps
- participation <= {MAX_PARTICIPATION_PCT:.0f}%
- no broker reject/filter
"""
    BRIDGE_CONTRACT_PATH.write_text(text, encoding="utf-8")


def write_chart(
    gates: pd.DataFrame,
    raw_sources: pd.DataFrame,
    join_attempts: pd.DataFrame,
    field_completeness: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    ax = axes[0, 0]
    colors = ["#2e7d32" if bool(x) else "#c62828" for x in gates["passed"]]
    ypos = np.arange(len(gates))
    ax.barh(ypos, np.ones(len(gates)), color=colors)
    ax.set_yticks(ypos)
    ax.set_yticklabels(gates["gate"], fontsize=8)
    ax.set_xticks([])
    ax.set_xlim(0, 1)
    ax.set_title("Dry-run bridge gates")
    for idx, row in gates.iterrows():
        ax.text(0.5, idx, "PASS" if row["passed"] else "FAIL", ha="center", va="center", color="white", fontweight="bold", fontsize=9)
    ax.invert_yaxis()

    ax = axes[0, 1]
    if raw_sources.empty:
        counts = pd.Series(dtype=float)
        p0_counts = pd.Series(dtype=float)
    else:
        counts = raw_sources.groupby("event_type")["row_count"].sum().sort_index()
        p0_counts = raw_sources.groupby("event_type")["p0_row_count"].sum().reindex(counts.index).fillna(0)
    x = np.arange(len(counts))
    ax.bar(x, counts.values, color="#4e79a7", label="all raw rows")
    ax.bar(x, p0_counts.values, color="#c62828", label="P0 rows")
    ax.set_xticks(x)
    ax.set_xticklabels(counts.index.tolist(), rotation=30, ha="right")
    ax.set_title("Local raw CTP/SimNow event rows")
    ax.set_ylabel("rows")
    ax.legend()
    for idx, value in enumerate(counts.values):
        ax.text(idx, value, f"{int(value)}", ha="center", va="bottom", fontsize=9)

    ax = axes[1, 0]
    p0 = join_attempts[join_attempts["watch_priority"].fillna("").astype(str).str.startswith("P0")].copy() if not join_attempts.empty else pd.DataFrame()
    if not p0.empty:
        labels = p0["vt_symbol"].astype(str).tolist()
        matched_order = p0["matched_order"].astype(float).to_numpy()
        matched_trade = p0["matched_trade"].astype(float).to_numpy()
        valid = p0["valid_live_tca_sample"].astype(float).to_numpy()
        x = np.arange(len(labels))
        width = 0.25
        ax.bar(x - width, matched_order, width, label="order joined", color="#59a14f")
        ax.bar(x, matched_trade, width, label="trade joined", color="#edc948")
        ax.bar(x + width, valid, width, label="valid sample", color="#e15759")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.set_ylim(0, 1.1)
        ax.set_title("P0 explicit join status")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No P0 join attempts", ha="center", va="center")
        ax.set_axis_off()

    ax = axes[1, 1]
    fc = field_completeness.copy()
    view = fc.set_index("field")[["all_fill_rate_pct", "p0_fill_rate_pct"]] if not fc.empty else pd.DataFrame()
    heat = view.to_numpy(dtype=float) / 100.0 if not view.empty else np.zeros((1, 2))
    ax.imshow(heat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(view)))
    ax.set_yticklabels(view.index.tolist(), fontsize=7)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["all\nfill rate", "P0\nfill rate"], fontsize=8)
    ax.set_title("Live ledger actual field completeness")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat[i, j] * 100:.0f}%", ha="center", va="center", fontsize=7)

    fig.suptitle("Stage587 dry-run live TCA bridge: contract works, P0 evidence still absent", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    intent: pd.DataFrame,
    raw_sources: pd.DataFrame,
    mechanical: pd.DataFrame,
    ledger: pd.DataFrame,
    join_attempts: pd.DataFrame,
    field_completeness: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    p0_join = join_attempts[join_attempts["watch_priority"].fillna("").astype(str).str.startswith("P0")].copy()
    pass_count = int(gates["passed"].sum())
    raw_rows = int(pd.to_numeric(raw_sources.get("row_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not raw_sources.empty else 0
    text = f"""# Stage587 Stage526 Live TCA Bridge Dry-run

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- phase type: dry-run bridge implementation; no CTP connection; no order API call; no strategy change; no return backtest.

## External Research Judgment

- vn.py order/trade events are the correct raw execution lifecycle hooks.
- TCA should be order-level and fill-weighted. Implementation shortfall compares executed average price with arrival/signal price; VWAP comparison benchmarks execution against the intended market window.
- Therefore this stage implements the strict join contract. It does not infer P0 evidence by same symbol/date alone.

References: vn.py GitHub/EventEngine docs, tcapy open-source TCA, QuestDB order-level implementation shortfall example, CME TCA material.

## Decision

- Decision: `dry_run_live_tca_bridge_created_no_valid_p0_samples`
- Interpretation: the bridge contract and reducer now exist. Existing local SimNow/CTP raw files prove the reducer can join non-P0 test order/trade rows, but Stage526 P0 has no explicit `event_id/signal_id -> vt_orderid` mapping and no valid live TCA sample.
- Stage526 status: normal-cost candidate only; zero execution-bias claim remains not allowed.

## Stage526 Reference

| metric | value |
| --- | ---: |
| ending_equity | {STAGE526_REFERENCE['ending_equity']} |
| total_return_pct | {STAGE526_REFERENCE['total_return_pct']:.4f} |
| max_drawdown_pct | {STAGE526_REFERENCE['max_drawdown_pct']:.4f} |
| sharpe | {STAGE526_REFERENCE['sharpe']:.4f} |
| ulcer | {STAGE526_REFERENCE['ulcer']:.4f} |
| total_slippage | {STAGE526_REFERENCE['total_slippage']} |
| trade_count | {STAGE526_REFERENCE['trade_count']} |
| win_rate_pct | {STAGE526_REFERENCE['win_rate_pct']:.4f} |

## Key Results

- gates: `{pass_count}/{len(gates)}`
- intent rows loaded: `{len(intent)}`
- P0 intent rows: `{int(ledger['watch_priority'].fillna('').astype(str).str.startswith('P0').sum())}`
- raw CTP/SimNow source files: `{len(raw_sources)}`
- raw CTP/SimNow rows scanned: `{raw_rows}`
- mechanical non-P0 order/trade joins: `{len(mechanical)}`
- P0 valid live TCA samples: `{int(pd.to_numeric(ledger.loc[ledger['watch_priority'].fillna('').astype(str).str.startswith('P0'), 'valid_live_tca_sample'], errors='coerce').fillna(0).sum())}/9`

## Gates

{_md_table(gates)}

## P0 Join Attempts

{_md_table(p0_join, max_rows=10)}

## Mechanical Non-P0 Reducer Check

These rows are only a reducer mechanics check. They are not Stage526 P0 evidence.

{_md_table(mechanical, max_rows=20)}

## Raw Source Summary

{_md_table(raw_sources[['source_file', 'event_type', 'status', 'row_count', 'vt_symbol_count', 'p0_row_count']], max_rows=40) if not raw_sources.empty else '_empty_'}

## Field Completeness

{_md_table(field_completeness, max_rows=40)}

## Visual Read

- Top-left gate chart should show the first bridge/safety gates green and the actual P0 evidence gates red.
- Top-right raw source chart should show local SimNow/CTP rows exist, but P0 row count remains zero.
- Bottom-left P0 join chart should be all zero because no explicit `vt_orderid` mapping exists for Stage526 P0.
- Bottom-right field heatmap should show template/intent metadata exists but live actual execution fields remain empty for P0.

## Next Step

Wire the dry-run bridge into the pre-submit path:

1. Before any submit-capable run, create a `bridge_signal_id` for each intended Stage526/Stage575 row.
2. When a future dry-run/pre-submit adapter receives or would receive `vt_orderid`, write a submit mapping row.
3. Feed raw `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` CSVs into this script.
4. Only after real mapped P0 fills exist should the P0 close gates be re-evaluated.

## Overfitting Reflection

- Before run: no. This is execution ledger plumbing, not alpha tuning.
- After run: no. The bridge refuses same-symbol/date inference and keeps all P0 evidence gates red.

## Continued Value Reflection

- Before run: yes. Stage526 cannot close execution-bias risk without this bridge.
- After run: yes. We now have an executable bridge contract and reducer; the next blocker is collecting real mapped P0 fills.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template = _read_csv(STAGE575_TEMPLATE)
    intent = build_intent_ledger(template)
    raw_sources, raw_frames = discover_raw_sources()
    order_summary = summarize_orders(raw_frames["orders"])
    trade_summary = summarize_trades(raw_frames["trades"])
    mechanical = build_mechanical_non_p0_summary(order_summary, trade_summary)
    ledger, join_attempts = build_live_tca_ledger(intent, order_summary, trade_summary)
    field_completeness = build_field_completeness(ledger)
    gates = build_gates(intent, raw_sources, mechanical, ledger, field_completeness)
    write_bridge_contract()

    intent.to_csv(INTENT_LEDGER_PATH, index=False, encoding="utf-8-sig")
    raw_sources.to_csv(RAW_SOURCES_PATH, index=False, encoding="utf-8-sig")
    order_summary.to_csv(ORDER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    trade_summary.to_csv(TRADE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    mechanical.to_csv(MECHANICAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ledger.to_csv(LIVE_TCA_LEDGER_PATH, index=False, encoding="utf-8-sig")
    join_attempts.to_csv(JOIN_ATTEMPTS_PATH, index=False, encoding="utf-8-sig")
    field_completeness.to_csv(FIELD_COMPLETENESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    write_chart(gates, raw_sources, join_attempts, field_completeness)
    write_report(intent, raw_sources, mechanical, ledger, join_attempts, field_completeness, gates)

    p0_mask = ledger["watch_priority"].fillna("").astype(str).str.startswith("P0")
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "dry_run_live_tca_bridge_created_no_valid_p0_samples",
        "stage526_reference": STAGE526_REFERENCE,
        "send_order_api_called_count": 0,
        "ctp_connection_attempted": False,
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_total": int(len(gates)),
        "intent_rows": int(len(intent)),
        "p0_intent_rows": int(p0_mask.sum()),
        "raw_source_files": int(len(raw_sources)),
        "raw_source_rows": int(pd.to_numeric(raw_sources.get("row_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not raw_sources.empty else 0,
        "mechanical_non_p0_joined_orders": int(len(mechanical)),
        "explicit_stage526_vt_orderid_mappings": int(ledger["bridge_vt_orderid"].apply(_present_scalar).sum()) if "bridge_vt_orderid" in ledger.columns else 0,
        "p0_joined_order_trade_rows": int(ledger.loc[p0_mask, "bridge_join_status"].fillna("").astype(str).eq("joined_order_trade").sum()),
        "p0_valid_live_tca_samples": int(pd.to_numeric(ledger.loc[p0_mask, "valid_live_tca_sample"], errors="coerce").fillna(0).sum()),
        "p0_required_live_tca_samples": int(len(P0_SYMBOLS) * REQUIRED_VALID_SAMPLES_PER_P0),
        "zero_execution_bias_claim_allowed": False,
        "next_required_action": "wire bridge_signal_id/vt_orderid mapping into future dry-run/pre-submit adapter and collect mapped P0 EVENT_ORDER/EVENT_TRADE/TICK rows",
        "outputs": {
            "intent_ledger": str(INTENT_LEDGER_PATH),
            "raw_sources": str(RAW_SOURCES_PATH),
            "order_summary": str(ORDER_SUMMARY_PATH),
            "trade_summary": str(TRADE_SUMMARY_PATH),
            "mechanical_summary": str(MECHANICAL_SUMMARY_PATH),
            "live_tca_ledger": str(LIVE_TCA_LEDGER_PATH),
            "join_attempts": str(JOIN_ATTEMPTS_PATH),
            "field_completeness": str(FIELD_COMPLETENESS_PATH),
            "gates": str(GATES_PATH),
            "bridge_contract": str(BRIDGE_CONTRACT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
