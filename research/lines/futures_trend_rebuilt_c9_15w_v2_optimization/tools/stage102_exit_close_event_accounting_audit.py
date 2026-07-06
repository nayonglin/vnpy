from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage102"
MODEL_TAG = "stage102_exit_close_event_accounting_audit_v2_reviewed_all"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage102_exit_close_event_accounting_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage102_exit_close_event_accounting_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE099_OUT = LINE_DIR / "outputs" / "stage099_held_trend_deterioration_audit"
STAGE099_PREFIX = "rebuilt_c9_v2_stage099_held_trend_deterioration_audit"
STAGE099_TAG = "stage099_held_trend_deterioration_audit_v1"
HELD_PANEL_PATH = STAGE099_OUT / f"{STAGE099_PREFIX}_held_panel_{STAGE099_TAG}.csv.gz"
STAGE099_DECISION_PATH = STAGE099_OUT / f"{STAGE099_PREFIX}_decision_{STAGE099_TAG}.json"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

STAGE098_OUT = LINE_DIR / "outputs" / "stage098_carryover_component_decomposition_audit"
STAGE098_PREFIX = "rebuilt_c9_v2_stage098_carryover_component_decomposition_audit"
STAGE098_TAG = "stage098_carryover_component_decomposition_audit_v1"
STAGE098_DECISION_PATH = STAGE098_OUT / f"{STAGE098_PREFIX}_decision_{STAGE098_TAG}.json"

ACTION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_action_summary_{MODEL_TAG}.csv"
EXIT_REASON_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_exit_reason_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
CLOSE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_close_events_{MODEL_TAG}.csv.gz"
TOP_CLOSE_LOSS_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_top_close_loss_events_{MODEL_TAG}.csv"
ACCOUNTING_OFFSET_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_accounting_offset_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")
EPS = 1e-9

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Backtests should separate accounting, position sizing and trading-cost effects before changing system rules.",
    },
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Dynamic stops and volatility controls change skew/Sharpe trade-offs; exit changes need path attribution first.",
    },
    {
        "source": "Research Affiliates stop-loss paper",
        "url": "https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1099-stop-the-losses.pdf",
        "finding": "Stop-loss protections may improve drawdowns but often drag expected or risk-adjusted returns, so candidates need broad evidence.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    held = pd.read_csv(HELD_PANEL_PATH, encoding="utf-8-sig")
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    stage098_decision = json.loads(STAGE098_DECISION_PATH.read_text(encoding="utf-8"))
    stage099_decision = json.loads(STAGE099_DECISION_PATH.read_text(encoding="utf-8"))
    if stage098_decision.get("decision") != "stage098_no_component_condition_candidate_carryover_holding_dominates_bad_window":
        raise ValueError(f"Unexpected Stage098 decision: {stage098_decision.get('decision')}")
    if stage099_decision.get("decision") != "stage099_no_held_trend_deterioration_candidate":
        raise ValueError(f"Unexpected Stage099 decision: {stage099_decision.get('decision')}")
    for column in ["date", "next_date"]:
        held[column] = pd.to_datetime(held[column], errors="coerce").dt.normalize()
    for column in ["entry_date", "exit_date"]:
        lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    held["requested_start_month"] = held["requested_start_month"].astype(str)
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    for column in [
        "end_pos",
        "end_pos_next",
        "pos_change",
        "trade_count",
        "drawdown_depth_pct",
        "next_holding_pnl",
        "next_same_symbol_rebalance_net_pnl",
        "next_same_symbol_net_pnl",
    ]:
        held[column] = _numeric(held, column)
    for column in ["realized_pnl", "volume", "r_multiple"]:
        lots[column] = _numeric(lots, column)
    return held.dropna(subset=["date", "next_date"]).copy(), lots.dropna(subset=["exit_date"]).copy(), stage098_decision, stage099_decision


def classify_actions(held: pd.DataFrame) -> pd.DataFrame:
    data = held.copy()
    prev = data["end_pos"]
    nxt = data["end_pos_next"]
    nonheld_rows = int(prev.abs().le(EPS).sum())
    if nonheld_rows:
        raise ValueError(f"Held panel includes non-held rows: {nonheld_rows}")
    traded = data["trade_count"].gt(0) | data["pos_change"].abs().gt(EPS)
    prev_sign = np.sign(prev)
    next_sign = np.sign(nxt)
    action = np.full(len(data), "no_trade", dtype=object)
    action[traded & prev.abs().gt(EPS) & nxt.abs().le(EPS)] = "close"
    action[traded & nxt.abs().gt(EPS) & (prev_sign != next_sign)] = "flip"
    same_sign = traded & nxt.abs().gt(EPS) & (prev_sign == next_sign)
    action[same_sign & nxt.abs().lt(prev.abs() - EPS)] = "reduce"
    action[same_sign & nxt.abs().gt(prev.abs() + EPS)] = "add"
    action[same_sign & (nxt.abs().sub(prev.abs()).abs().le(EPS))] = "same_size_churn"
    data["action"] = action
    data["close_day_net_pnl"] = data["next_same_symbol_net_pnl"]
    data["close_day_holding_pnl"] = data["next_holding_pnl"]
    data["close_day_rebalance_net_pnl"] = data["next_same_symbol_rebalance_net_pnl"]
    data["in_bad_window_by_next_date"] = data["next_date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
    data["dd30_before_next_date"] = data["drawdown_depth_pct"].ge(30.0)
    return data


def build_exit_reason_map(lots: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["requested_start_month", "vt_symbol", "exit_date"]
    rows: list[dict[str, Any]] = []
    for key, group in lots.groupby(key_cols, dropna=False, sort=True):
        reason_pnl = group.groupby("exit_reason", dropna=False)["realized_pnl"].sum().reset_index()
        reason_abs = reason_pnl.assign(abs_pnl=reason_pnl["realized_pnl"].abs()).sort_values(
            ["abs_pnl", "realized_pnl"], ascending=[False, True]
        )
        primary_reason = str(reason_abs.iloc[0]["exit_reason"]) if not reason_abs.empty else ""
        reasons = ",".join(str(item) for item in sorted(group["exit_reason"].dropna().astype(str).unique()))
        rows.append(
            {
                "requested_start_month": key[0],
                "vt_symbol": key[1],
                "next_date": key[2],
                "matched_lot_count": int(len(group)),
                "matched_lot_pnl_sum": float(group["realized_pnl"].sum()),
                "matched_lot_positive_pnl_sum": float(group.loc[group["realized_pnl"].gt(0), "realized_pnl"].sum()),
                "matched_lot_negative_pnl_abs_sum": float(-group.loc[group["realized_pnl"].lt(0), "realized_pnl"].sum()),
                "matched_lot_volume_sum": float(group["volume"].sum()),
                "primary_exit_reason": primary_reason,
                "exit_reason_list": reasons,
            }
        )
    return pd.DataFrame(rows)


def attach_exit_reasons(actions: pd.DataFrame, lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_events = actions[actions["action"].eq("close")].copy()
    reason_map = build_exit_reason_map(lots)
    if reason_map.duplicated(["requested_start_month", "vt_symbol", "next_date"]).any():
        raise ValueError("Exit reason map has duplicate keys after grouping")
    close_events = close_events.merge(
        reason_map,
        on=["requested_start_month", "vt_symbol", "next_date"],
        how="left",
        validate="many_to_one",
    )
    unmatched = int(close_events["primary_exit_reason"].isna().sum())
    if unmatched:
        raise ValueError(f"Close events without closed-lot exit reason match: {unmatched}")
    close_events["primary_exit_reason"] = close_events["primary_exit_reason"].astype(str)
    close_events["exit_reason_list"] = close_events["exit_reason_list"].fillna("").astype(str)
    return actions, close_events


def _pnl_stats(frame: pd.DataFrame, value_col: str) -> dict[str, Any]:
    values = pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0)
    by_start = frame.groupby("requested_start_month")[value_col].sum() if not frame.empty else pd.Series(dtype=float)
    by_date = frame.groupby("next_date")[value_col].sum() if not frame.empty else pd.Series(dtype=float)
    return {
        f"{value_col}_sum": float(values.sum()) if not values.empty else 0.0,
        f"{value_col}_positive_sum": float(values[values.gt(0)].sum()) if not values.empty else 0.0,
        f"{value_col}_negative_abs_sum": float(-values[values.lt(0)].sum()) if not values.empty else 0.0,
        f"{value_col}_loss_rate": float(values.lt(0).mean()) if not values.empty else np.nan,
        f"{value_col}_negative_start_count": int(by_start.lt(0).sum()) if len(by_start) else 0,
        f"{value_col}_negative_start_rate": _safe_div(float(by_start.lt(0).sum()), float(len(by_start))),
        f"{value_col}_negative_date_count": int(by_date.lt(0).sum()) if len(by_date) else 0,
        f"{value_col}_negative_date_rate": _safe_div(float(by_date.lt(0).sum()), float(len(by_date))),
        f"{value_col}_start_pnl_min": float(by_start.min()) if len(by_start) else np.nan,
        f"{value_col}_start_pnl_median": float(by_start.median()) if len(by_start) else np.nan,
        f"{value_col}_start_pnl_max": float(by_start.max()) if len(by_start) else np.nan,
    }


def _base_summary(frame: pd.DataFrame, scope: str, action: str = "") -> dict[str, Any]:
    row = {
        "scope": scope,
        "action": action,
        "rows": int(len(frame)),
        "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
        "date_count": int(frame["next_date"].nunique()) if not frame.empty else 0,
        "symbol_count": int(frame["vt_symbol"].nunique()) if not frame.empty else 0,
        "trade_count_sum": float(frame["trade_count"].sum()) if "trade_count" in frame.columns and not frame.empty else 0.0,
    }
    for col in ["next_holding_pnl", "next_same_symbol_rebalance_net_pnl", "next_same_symbol_net_pnl"]:
        if col in frame.columns:
            row.update(_pnl_stats(frame, col))
    return row


def build_action_summary(actions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scopes = {
        "all": actions,
        "bad_window": actions[actions["in_bad_window_by_next_date"]],
        "dd30": actions[actions["dd30_before_next_date"]],
    }
    for scope, scope_frame in scopes.items():
        rows.append(_base_summary(scope_frame, scope, "all_actions"))
        for action, group in scope_frame.groupby("action", sort=True):
            rows.append(_base_summary(group.copy(), scope, str(action)))
    return pd.DataFrame(rows).sort_values(["scope", "action"]).reset_index(drop=True)


def _exit_reason_row(frame: pd.DataFrame, scope: str, reason: str, condition_name: str) -> dict[str, Any]:
    row = {
        "scope": scope,
        "condition_name": condition_name,
        "primary_exit_reason": reason,
        "rows": int(len(frame)),
        "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
        "date_count": int(frame["next_date"].nunique()) if not frame.empty else 0,
        "symbol_count": int(frame["vt_symbol"].nunique()) if not frame.empty else 0,
        "matched_lot_count_sum": int(frame["matched_lot_count"].sum()) if not frame.empty else 0,
        "matched_lot_pnl_sum": float(frame["matched_lot_pnl_sum"].sum()) if not frame.empty else 0.0,
        "matched_lot_negative_pnl_abs_sum": float(frame["matched_lot_negative_pnl_abs_sum"].sum()) if not frame.empty else 0.0,
        "matched_lot_positive_pnl_sum": float(frame["matched_lot_positive_pnl_sum"].sum()) if not frame.empty else 0.0,
        "close_day_holding_pnl_sum": float(frame["close_day_holding_pnl"].sum()) if not frame.empty else 0.0,
        "close_day_rebalance_net_pnl_sum": float(frame["close_day_rebalance_net_pnl"].sum()) if not frame.empty else 0.0,
        "close_day_net_pnl_sum": float(frame["close_day_net_pnl"].sum()) if not frame.empty else 0.0,
        "close_day_net_pnl_positive_sum": float(frame.loc[frame["close_day_net_pnl"].gt(0), "close_day_net_pnl"].sum())
        if not frame.empty
        else 0.0,
        "close_day_net_pnl_negative_abs_sum": float(-frame.loc[frame["close_day_net_pnl"].lt(0), "close_day_net_pnl"].sum())
        if not frame.empty
        else 0.0,
        "close_day_net_loss_rate": float(frame["close_day_net_pnl"].lt(0).mean()) if not frame.empty else np.nan,
    }
    by_start = frame.groupby("requested_start_month")["close_day_net_pnl"].sum() if not frame.empty else pd.Series(dtype=float)
    by_date = frame.groupby("next_date")["close_day_net_pnl"].sum() if not frame.empty else pd.Series(dtype=float)
    row["negative_start_count"] = int(by_start.lt(0).sum()) if len(by_start) else 0
    row["negative_start_rate"] = _safe_div(float(by_start.lt(0).sum()), float(len(by_start)))
    row["negative_date_count"] = int(by_date.lt(0).sum()) if len(by_date) else 0
    row["negative_date_rate"] = _safe_div(float(by_date.lt(0).sum()), float(len(by_date)))
    row["start_net_pnl_min"] = float(by_start.min()) if len(by_start) else np.nan
    row["start_net_pnl_median"] = float(by_start.median()) if len(by_start) else np.nan
    row["start_net_pnl_max"] = float(by_start.max()) if len(by_start) else np.nan
    row["rebalance_abs_offset_ratio"] = _safe_div(abs(row["close_day_rebalance_net_pnl_sum"]), abs(row["close_day_net_pnl_sum"]))
    return row


def build_exit_reason_summary(close_events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scopes = {
        "all_close_events": close_events,
        "bad_window_close_events": close_events[close_events["in_bad_window_by_next_date"]],
        "dd30_close_events": close_events[close_events["dd30_before_next_date"]],
    }
    for scope, scope_frame in scopes.items():
        rows.append(_exit_reason_row(scope_frame, scope, "ALL", scope))
        for reason, group in scope_frame.groupby("primary_exit_reason", sort=True):
            rows.append(_exit_reason_row(group.copy(), scope, str(reason), f"{scope}::{reason}"))
    return (
        pd.DataFrame(rows)
        .sort_values(["scope", "close_day_net_pnl_sum", "rows"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def build_candidate_summary(exit_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in exit_summary.iterrows():
        reason = str(row["primary_exit_reason"])
        scope = str(row["scope"])
        is_all = scope == "all_close_events"
        is_dd30 = scope == "dd30_close_events"
        live_rule_shape = is_all or is_dd30
        aggregate_close_shape = reason == "ALL"
        min_rows = 50 if is_all else 30
        min_starts = 8 if is_all else 6
        min_dates = 25 if is_all else 12
        min_symbols = 4 if is_all else 3
        broad_enough = bool(
            int(row["rows"]) >= min_rows
            and int(row["start_count"]) >= min_starts
            and int(row["date_count"]) >= min_dates
            and int(row["symbol_count"]) >= min_symbols
        )
        net_loss_large = float(row["close_day_net_pnl_sum"]) <= -500_000.0
        matched_lot_materially_losing = float(row["matched_lot_pnl_sum"]) <= -250_000.0
        stable_negative = bool(
            pd.notna(row["negative_start_rate"])
            and pd.notna(row["negative_date_rate"])
            and float(row["negative_start_rate"]) >= 0.65
            and float(row["negative_date_rate"]) >= 0.55
        )
        candidate_for_followup = bool(
            live_rule_shape and broad_enough and net_loss_large and matched_lot_materially_losing and stable_negative
        )
        rows.append(
            {
                "condition_name": row["condition_name"],
                "scope": scope,
                "primary_exit_reason": reason,
                "aggregate_close_shape": aggregate_close_shape,
                "live_rule_shape": live_rule_shape,
                "broad_enough": broad_enough,
                "net_loss_large": net_loss_large,
                "matched_lot_materially_losing": matched_lot_materially_losing,
                "stable_negative": stable_negative,
                "candidate_for_followup": candidate_for_followup,
                "rows": int(row["rows"]),
                "start_count": int(row["start_count"]),
                "date_count": int(row["date_count"]),
                "symbol_count": int(row["symbol_count"]),
                "close_day_net_pnl_sum": float(row["close_day_net_pnl_sum"]),
                "matched_lot_pnl_sum": float(row["matched_lot_pnl_sum"]),
                "negative_start_rate": float(row["negative_start_rate"]) if pd.notna(row["negative_start_rate"]) else np.nan,
                "negative_date_rate": float(row["negative_date_rate"]) if pd.notna(row["negative_date_rate"]) else np.nan,
                "rejection_reason": _candidate_rejection_reason(
                    live_rule_shape, broad_enough, net_loss_large, matched_lot_materially_losing, stable_negative
                ),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["candidate_for_followup", "close_day_net_pnl_sum"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _candidate_rejection_reason(
    live_rule_shape: bool,
    broad_enough: bool,
    net_loss_large: bool,
    matched_lot_materially_losing: bool,
    stable_negative: bool,
) -> str:
    reasons: list[str] = []
    if not live_rule_shape:
        reasons.append("not_live_rule_shape")
    if not broad_enough:
        reasons.append("sample_not_broad")
    if not net_loss_large:
        reasons.append("close_day_net_loss_not_large")
    if not matched_lot_materially_losing:
        reasons.append("matched_lot_not_materially_losing")
    if not stable_negative:
        reasons.append("not_stably_negative")
    return ",".join(reasons) if reasons else ""


def build_accounting_offset_summary(action_summary: pd.DataFrame, exit_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in ["all", "bad_window", "dd30"]:
        action_row = action_summary[(action_summary["scope"].eq(scope)) & (action_summary["action"].eq("close"))]
        if action_row.empty:
            continue
        row = action_row.iloc[0].to_dict()
        holding = float(row.get("next_holding_pnl_sum", 0.0) or 0.0)
        rebalance = float(row.get("next_same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0)
        net = float(row.get("next_same_symbol_net_pnl_sum", 0.0) or 0.0)
        rows.append(
            {
                "scope": scope,
                "close_rows": int(row.get("rows", 0) or 0),
                "close_holding_pnl": holding,
                "close_rebalance_net_pnl": rebalance,
                "close_day_net_pnl": net,
                "rebalance_abs_to_net_abs": _safe_div(abs(rebalance), abs(net)),
                "holding_plus_rebalance_minus_net": float(holding + rebalance - net),
                "interpretation": (
                    "rebalance_loss_partially_offset_by_holding"
                    if rebalance < 0 and holding > 0 and net > rebalance
                    else "net_loss_after_offset"
                ),
            }
        )
    all_exit = exit_summary[
        exit_summary["scope"].eq("all_close_events") & ~exit_summary["primary_exit_reason"].eq("ALL")
    ].copy()
    if not all_exit.empty:
        worst = all_exit.sort_values("close_day_net_pnl_sum").iloc[0]
        rows.append(
            {
                "scope": "worst_all_exit_reason",
                "close_rows": int(worst["rows"]),
                "close_holding_pnl": float(worst["close_day_holding_pnl_sum"]),
                "close_rebalance_net_pnl": float(worst["close_day_rebalance_net_pnl_sum"]),
                "close_day_net_pnl": float(worst["close_day_net_pnl_sum"]),
                "rebalance_abs_to_net_abs": float(worst["rebalance_abs_offset_ratio"])
                if pd.notna(worst["rebalance_abs_offset_ratio"])
                else np.nan,
                "holding_plus_rebalance_minus_net": float(
                    worst["close_day_holding_pnl_sum"] + worst["close_day_rebalance_net_pnl_sum"] - worst["close_day_net_pnl_sum"]
                ),
                "interpretation": f"worst_reason={worst['primary_exit_reason']}",
            }
        )
    return pd.DataFrame(rows)


def build_top_close_loss_events(close_events: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "requested_start_month",
        "date",
        "next_date",
        "vt_symbol",
        "end_pos",
        "end_pos_next",
        "drawdown_depth_pct",
        "in_bad_window_by_next_date",
        "dd30_before_next_date",
        "primary_exit_reason",
        "exit_reason_list",
        "close_day_holding_pnl",
        "close_day_rebalance_net_pnl",
        "close_day_net_pnl",
        "matched_lot_count",
        "matched_lot_pnl_sum",
        "matched_lot_negative_pnl_abs_sum",
        "matched_lot_positive_pnl_sum",
    ]
    return close_events.sort_values("close_day_net_pnl").loc[:, [col for col in cols if col in close_events.columns]].head(100)


def make_decision(
    action_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    close_events: pd.DataFrame,
    stage098_decision: dict[str, Any],
    stage099_decision: dict[str, Any],
) -> dict[str, Any]:
    candidates = candidate_summary[candidate_summary["candidate_for_followup"].astype(bool)].copy()
    close_all = action_summary[(action_summary["scope"].eq("all")) & (action_summary["action"].eq("close"))]
    close_bad = action_summary[(action_summary["scope"].eq("bad_window")) & (action_summary["action"].eq("close"))]
    close_dd30 = action_summary[(action_summary["scope"].eq("dd30")) & (action_summary["action"].eq("close"))]
    close_all_row = close_all.iloc[0].to_dict() if not close_all.empty else {}
    close_bad_row = close_bad.iloc[0].to_dict() if not close_bad.empty else {}
    close_dd30_row = close_dd30.iloc[0].to_dict() if not close_dd30.empty else {}
    if candidates.empty:
        decision = "stage102_no_exit_or_aggregate_accounting_followup_candidate"
        best_candidate = ""
        promote_to_followup = False
        next_step = (
            "不进入退出规则 proxy/true engine；Stage098 的 rebalance 账面损失主要应按 close-day net 解释，"
            "当前 exit_reason/DD30 聚合组合没有宽样本、稳定负贡献、且 matched lot 也显著亏损的候选。"
            "下一步应转向 post-exit continuation 或真实分钟路径滑点/止损穿价审计，但不能从本阶段直接改退出。"
        )
        continue_after = "有但需换问题"
        continue_reason = "本阶段排除了把 rebalance accounting 当成独立损失的误读；继续价值在 post-exit 行为或分钟执行路径，而不是按 exit_reason 直接扫参。"
        overfit_after = (
            "否。只读核算固定 close/reduce/add/hold 动作与既有 exit_reason；没有按品种、方向、月份或亏损事件调参。"
        )
    else:
        best = candidates.sort_values("close_day_net_pnl_sum").iloc[0]
        decision = "stage102_close_accounting_candidate_for_post_exit_audit"
        best_candidate = str(best["condition_name"])
        promote_to_followup = True
        next_step = (
            f"只允许围绕 `{best_candidate}` 做一次 post-exit continuation 审计，确认延迟/替代退出是否真实保留收益；"
            "不得扩展成 exit_reason、DD 阈值、产品、方向或日期扫描。"
        )
        continue_after = "有"
        continue_reason = "存在宽样本且稳定负贡献的退出事件形状，但只能作为后续归因，不是策略候选。"
        overfit_after = (
            "否，但下一步风险升高。本阶段候选来自固定 exit_reason 和 DD30 状态，后续必须冻结一次验证。"
        )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "candidate_summary_scope": "specific_exit_reason_and_ALL_aggregate_close_shapes",
        "promote_to_followup_audit": promote_to_followup,
        "promote_to_proxy": False,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "held_panel_rows": int(action_summary[action_summary["scope"].eq("all") & action_summary["action"].eq("all_actions")]["rows"].iloc[0])
        if not action_summary.empty
        else 0,
        "close_event_rows": int(len(close_events)),
        "close_events_matched_lot_count": int(close_events["matched_lot_count"].notna().sum()),
        "close_all_net_pnl": float(close_all_row.get("next_same_symbol_net_pnl_sum", 0.0) or 0.0),
        "close_all_holding_pnl": float(close_all_row.get("next_holding_pnl_sum", 0.0) or 0.0),
        "close_all_rebalance_net_pnl": float(close_all_row.get("next_same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0),
        "close_bad_window_net_pnl": float(close_bad_row.get("next_same_symbol_net_pnl_sum", 0.0) or 0.0),
        "close_bad_window_holding_pnl": float(close_bad_row.get("next_holding_pnl_sum", 0.0) or 0.0),
        "close_bad_window_rebalance_net_pnl": float(close_bad_row.get("next_same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0),
        "close_dd30_net_pnl": float(close_dd30_row.get("next_same_symbol_net_pnl_sum", 0.0) or 0.0),
        "close_dd30_holding_pnl": float(close_dd30_row.get("next_holding_pnl_sum", 0.0) or 0.0),
        "close_dd30_rebalance_net_pnl": float(close_dd30_row.get("next_same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0),
        "stage098_bad_window_same_symbol_rebalance_net_pnl": float(
            stage098_decision.get("bad_window_active_same_symbol_rebalance_net_pnl", 0.0) or 0.0
        ),
        "stage098_bad_window_same_symbol_holding_pnl": float(
            stage098_decision.get("bad_window_active_same_symbol_holding_pnl", 0.0) or 0.0
        ),
        "stage099_bad_window_same_symbol_net_pnl": float(
            stage099_decision.get("bad_window_next_same_symbol_net_pnl_sum", 0.0) or 0.0
        ),
        "main_accounting_judgement": (
            "rebalance component is not independently actionable; close-day net must combine holding and rebalance/cost"
        ),
        "independent_review_resolution": (
            "v2 includes ALL aggregate close shapes in candidate_summary after v1 reviewer found DD30 ALL was silently skipped"
        ),
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    action_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    offset_summary: pd.DataFrame,
    top_close_loss_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Exit Close Event Accounting Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：趋势系统的退出规则不能只看平仓成交项或止损项；必须把 close-day holding PnL、rebalance/trading PnL、成本和 closed-lot exit reason 合并核算，避免把会计分解误当成可交易 alpha。

## Action Summary

{_md_table(action_summary, 80)}

## Accounting Offset Summary

{_md_table(offset_summary, 40)}

## Exit Reason Summary

{_md_table(exit_summary, 120)}

## Candidate Summary

{_md_table(candidate_summary, 120)}

## Top Close Loss Events

{_md_table(top_close_loss_events, 100)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- 输入：Stage099 held panel 与 Stage094 closed lots；Stage098/099 decision 只用于确认上游口径。
- 主口径：`close_day_net_pnl = next_same_symbol_net_pnl`，不单独把 `next_same_symbol_rebalance_net_pnl` 当成损失规则。
- `close` 定义：上一日持仓非零，下一交易日同合约持仓归零，且存在 trade/pos_change。
- exit reason 映射：`requested_start_month + vt_symbol + next_date==exit_date` 聚合；若 close event 无 closed-lot 匹配则直接报错。
- 候选闸门：只允许 all-close 或 DD30-close 的 exit_reason 形状进入后续审计；bad-window 只做解释，不作为交易条件。

## 过拟合反思

- 运行前：否。当前实验是会计核算和路径归因，不是新参数搜索。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage098/099 暴露了 same-symbol close/rebalance 的坏窗口损失，必须先辨认是不是可交易问题。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- close_events：`{CLOSE_EVENTS_PATH}`
- action_summary：`{ACTION_SUMMARY_PATH}`
- exit_reason_summary：`{EXIT_REASON_SUMMARY_PATH}`
- candidate_summary：`{CANDIDATE_SUMMARY_PATH}`
- accounting_offset_summary：`{ACCOUNTING_OFFSET_SUMMARY_PATH}`
- top_close_loss_events：`{TOP_CLOSE_LOSS_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    action_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    offset_summary: pd.DataFrame,
    top_close_loss_events: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage102_exit_close_event_accounting_audit.md"
    text = f"""# Stage102 出场平仓日会计核算审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读 close-event / exit-reason 会计归因；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不产生可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、Rob Carver dynamic trend following、Research Affiliates stop-loss paper。
- 我的判断：退出/止损类规则存在“改善回撤但损伤右尾”的天然张力；本阶段先检查 Stage098 的 rebalance 损失是不是独立可交易损失，而不是直接调退出规则。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage102_exit_close_event_accounting_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：无正式交易参数；只新增审计口径 `action=close/reduce/add/flip/no_trade` 和固定 DD30 诊断。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage099 held panel、Stage094 closed lots、Stage098/099 decision。
- 数据区间：Stage099 的 `2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：沿用 Stage167/Stage099 `150,000`；本阶段不重算账户曲线。
- 成本口径：Stage099 `next_same_symbol_net_pnl` 已包含 same-symbol holding/trading/cost；Stage094 `realized_pnl` 用于 exit_reason 匹配解释。
- 样本过滤：上一日有同合约持仓的 held panel；close event 需下一交易日同合约持仓归零。
- 策略/归因口径：只读 close-day net 归因；不按产品、方向、日期或坏窗口黑名单改规则。

## Action Summary

{_md_table(action_summary, 80)}

## Accounting Offset Summary

{_md_table(offset_summary, 40)}

## Exit Reason Summary

{_md_table(exit_summary, 120)}

## Candidate Summary

{_md_table(candidate_summary, 120)}

## Top Close Loss Events

{_md_table(top_close_loss_events, 100)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- held panel rows：`{decision['held_panel_rows']}`。
- close event rows：`{decision['close_event_rows']}`。
- close all net PnL：`{decision['close_all_net_pnl']:.4f}`。
- close all holding PnL：`{decision['close_all_holding_pnl']:.4f}`。
- close all rebalance net PnL：`{decision['close_all_rebalance_net_pnl']:.4f}`。
- bad-window close net PnL：`{decision['close_bad_window_net_pnl']:.4f}`。
- DD30 close net PnL：`{decision['close_dd30_net_pnl']:.4f}`。
- 是否进入 proxy：`{decision['promote_to_proxy']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。
- 总滑点：沿用 Stage099 component 内置成本，不新增汇总。
- 总交易次数：close event rows `{decision['close_event_rows']}` 仅为审计事件数，不是新策略交易次数。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}
- 原因：本阶段只解释既有会计分量和 exit_reason，不搜索阈值或局部历史伤口。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等独立 agent 审查。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    held, lots, stage098_decision, stage099_decision = load_inputs()
    input_audit = _input_audit([HELD_PANEL_PATH, CLOSED_LOTS_PATH, STAGE098_DECISION_PATH, STAGE099_DECISION_PATH])
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")

    actions = classify_actions(held)
    actions, close_events = attach_exit_reasons(actions, lots)
    if int(close_events["matched_lot_count"].notna().sum()) != len(close_events):
        raise ValueError("Not all close events have matched lot metadata")

    action_summary = build_action_summary(actions)
    exit_summary = build_exit_reason_summary(close_events)
    candidate_summary = build_candidate_summary(exit_summary)
    offset_summary = build_accounting_offset_summary(action_summary, exit_summary)
    top_close_loss_events = build_top_close_loss_events(close_events)
    decision = make_decision(action_summary, exit_summary, candidate_summary, close_events, stage098_decision, stage099_decision)

    close_events.to_csv(CLOSE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    action_summary.to_csv(ACTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    exit_summary.to_csv(EXIT_REASON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    offset_summary.to_csv(ACCOUNTING_OFFSET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_close_loss_events.to_csv(TOP_CLOSE_LOSS_EVENTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(action_summary, exit_summary, candidate_summary, offset_summary, top_close_loss_events, decision)
    stage_path = write_stage_record(action_summary, exit_summary, candidate_summary, offset_summary, top_close_loss_events, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
