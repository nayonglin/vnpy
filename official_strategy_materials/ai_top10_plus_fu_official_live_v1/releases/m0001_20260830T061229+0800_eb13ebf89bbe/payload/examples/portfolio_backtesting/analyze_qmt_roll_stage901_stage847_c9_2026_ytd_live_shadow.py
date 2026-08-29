from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

import pandas as pd

from qmt_roll_official_ai_pool_policy import (
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    official_ai_pool_snapshot_blockers,
)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage658_stage653_2026_ytd_shadow as s658
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
from main_contract_mapping import ALL_FUTURES_MAPPING_PATH
from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_pending_artifact import PENDING_ARTIFACT_SCHEMA_VERSION
from qmt_roll_official_live_execution_ledger import read_execution_ledger
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_PENDING_ORDERS_PATH,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_REPORT_PATH,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
    build_official_live_risk_snapshot,
)
from qmt_roll_official_live_phase_d_config import LIVE_EXECUTION_LEDGER_PATH


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage901_stage847_c9_2026_ytd_live_shadow_v1"
OUTPUT_PREFIX = "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
LINE_ID = "futures_trend_stage819_intraday_rules"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURRENT_POSITIONS_PATH = OFFICIAL_LIVE_CURRENT_POSITIONS_PATH
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
PENDING_ORDERS_PATH = OFFICIAL_LIVE_PENDING_ORDERS_PATH
SIGNAL_PLAN_PATH = OFFICIAL_LIVE_SIGNAL_PLAN_PATH
DECISION_PATH = OFFICIAL_LIVE_SUMMARY_PATH
REPORT_PATH = OFFICIAL_LIVE_REPORT_PATH
LIVE_STOP_ALIGNMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_stop_alignment_{MODEL_TAG}.csv"

_FULL_MINUTE_BY_SYMBOL_CACHE: dict[str, pd.DataFrame] | None = None
_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS: set[str] = set()
_LAST_MINUTE_AUDIT: dict[str, Any] = {}


def _official_live_identity() -> dict[str, Any]:
    if (
        OFFICIAL_LIVE_VERSION != C9_15W_PROFILE.official_version
        or OFFICIAL_LIVE_CAPITAL != C9_15W_PROFILE.capital
        or OFFICIAL_LIVE_CAPITAL_LABEL != C9_15W_PROFILE.capital_label
    ):
        raise ValueError("stage901_official_identity_config_mismatch")
    return {
        "execution_profile": C9_15W_PROFILE.profile_key,
        "official_live_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
    }


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _normal_direction(value: Any) -> str:
    text = _clean_text(value).lower()
    if text in {"long", "多", "direction.long", "buy"}:
        return "long"
    if text in {"short", "空", "direction.short", "sell"}:
        return "short"
    return text


def _normal_offset(value: Any) -> str:
    text = _clean_text(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {
        "close",
        "closetoday",
        "closeyesterday",
        "平",
        "平今",
        "平昨",
        "offset.close",
        "offset.closetoday",
        "offset.closeyesterday",
    }:
        return "close"
    return text


def _opposite_direction(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _ledger_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("intent_payload")
    return payload if isinstance(payload, dict) else {}


def _ledger_value(row: dict[str, Any], key: str) -> Any:
    payload = _ledger_payload(row)
    return row.get(key) if _clean_text(row.get(key)) else payload.get(key)


def _ledger_generated_date(row: dict[str, Any]) -> pd.Timestamp | None:
    generated = pd.to_datetime(_clean_text(row.get("generated_at")), errors="coerce")
    if pd.isna(generated):
        generated = pd.to_datetime(_clean_text(row.get("target_date")), errors="coerce")
    if pd.isna(generated):
        return None
    return pd.Timestamp(generated).normalize()


def _row_date_series(frame: pd.DataFrame) -> pd.Series:
    if "date" in frame.columns:
        source = frame["date"]
    elif "datetime" in frame.columns:
        source = frame["datetime"]
    elif "trading_day" in frame.columns:
        source = frame["trading_day"]
    else:
        return pd.Series(pd.NaT, index=frame.index)
    return pd.to_datetime(source, errors="coerce").dt.normalize()


def _latest_open_dates_by_key(trades: pd.DataFrame) -> dict[tuple[str, str], pd.Timestamp]:
    if trades.empty or "vt_symbol" not in trades.columns:
        return {}
    frame = trades.copy()
    frame["_date"] = _row_date_series(frame)
    frame["_direction"] = frame.get("direction", pd.Series("", index=frame.index)).map(_normal_direction)
    frame["_offset"] = frame.get("offset", pd.Series("", index=frame.index)).map(_normal_offset)
    frame["_vt_symbol"] = frame["vt_symbol"].fillna("").astype(str).str.strip()
    opens = frame[
        frame["_vt_symbol"].ne("")
        & frame["_direction"].isin(["long", "short"])
        & frame["_offset"].eq("open")
        & frame["_date"].notna()
    ].copy()
    if opens.empty:
        return {}
    grouped = opens.groupby(["_vt_symbol", "_direction"])["_date"].max()
    return {(str(vt_symbol), str(direction)): pd.Timestamp(date).normalize() for (vt_symbol, direction), date in grouped.items()}


def _live_stop_alignment_events(
    *,
    ledger_rows: list[dict[str, Any]],
    trades: pd.DataFrame,
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> pd.DataFrame:
    latest_open_dates = _latest_open_dates_by_key(trades)
    payload_by_fingerprint: dict[str, dict[str, Any]] = {}
    for ledger_row in ledger_rows:
        fingerprint = _clean_text(ledger_row.get("intent_fingerprint"))
        payload = _ledger_payload(ledger_row)
        if fingerprint and payload:
            payload_by_fingerprint[fingerprint] = payload
    rows: list[dict[str, Any]] = []
    for row in ledger_rows:
        if _clean_text(row.get("event_type")) != "filled_or_part_filled":
            continue
        linked_payload = payload_by_fingerprint.get(_clean_text(row.get("intent_fingerprint")), {})

        def event_value(key: str) -> Any:
            return row.get(key) if _clean_text(row.get(key)) else linked_payload.get(key)

        generated_date = _ledger_generated_date(row)
        if generated_date is None or generated_date < analysis_start or generated_date > analysis_end:
            continue
        vt_symbol = _clean_text(event_value("vt_symbol"))
        source = _clean_text(event_value("source"))
        source_reason = _clean_text(event_value("source_reason"))
        offset = _normal_offset(event_value("offset"))
        order_direction = _normal_direction(event_value("direction"))
        volume = _to_float(row.get("trade_volume_delta", row.get("volume")), 0.0)
        if not vt_symbol or volume <= 0:
            continue

        position_direction = ""
        position_delta_volume = 0.0
        stop_close_volume = 0.0
        retry_open_volume = 0.0
        suppress_signal_plan = 0
        alignment_note = ""
        if source == "stage904_c9_intraday_close" and offset == "close":
            position_direction = _opposite_direction(order_direction)
            if not position_direction:
                continue
            if "stage901_pending_open_after_stage904_stop_close_forced_close" in source_reason:
                alignment_note = "live_bug_repair_close_not_subtracted_from_shadow"
            else:
                position_delta_volume = -volume
                stop_close_volume = volume
                suppress_signal_plan = 1
                alignment_note = "stage904_realtime_stop_close_subtracted_from_shadow"
        elif source == "stage904_c9_intraday_retry_open" and offset == "open":
            position_direction = order_direction
            if not position_direction:
                continue
            position_delta_volume = volume
            retry_open_volume = volume
            suppress_signal_plan = 1
            alignment_note = "stage904_realtime_retry_open_offsets_stop_close"
        else:
            continue

        latest_open_date = latest_open_dates.get((vt_symbol, position_direction))
        if latest_open_date is not None and generated_date < latest_open_date:
            continue

        rows.append(
            {
                "generated_at": _clean_text(row.get("generated_at")),
                "generated_date": generated_date.date().isoformat(),
                "target_date": _clean_text(row.get("target_date")),
                "intent_id": _clean_text(row.get("intent_id")),
                "vt_orderid": _clean_text(row.get("vt_orderid")),
                "vt_symbol": vt_symbol,
                "position_direction": position_direction,
                "order_direction": order_direction,
                "offset": offset,
                "source": source,
                "source_reason": source_reason,
                "fill_price": _to_float(row.get("price"), 0.0),
                "fill_volume": volume,
                "position_delta_volume": position_delta_volume,
                "stop_close_volume": stop_close_volume,
                "retry_open_volume": retry_open_volume,
                "suppress_signal_plan": suppress_signal_plan,
                "latest_strategy_open_date": (
                    latest_open_date.date().isoformat() if latest_open_date is not None else ""
                ),
                "alignment_note": alignment_note,
            }
        )
    return pd.DataFrame(rows)


def _alignment_group(events: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "vt_symbol",
        "position_direction",
        "position_delta_volume",
        "stop_close_volume",
        "retry_open_volume",
        "suppress_signal_plan_volume",
    ]
    if events.empty:
        return pd.DataFrame(columns=columns)
    frame = events.copy()
    frame["suppress_signal_plan_volume"] = frame["fill_volume"].where(
        frame["suppress_signal_plan"].astype(int).eq(1), 0.0
    )
    grouped = (
        frame.groupby(["vt_symbol", "position_direction"], as_index=False)
        .agg(
            position_delta_volume=("position_delta_volume", "sum"),
            stop_close_volume=("stop_close_volume", "sum"),
            retry_open_volume=("retry_open_volume", "sum"),
            suppress_signal_plan_volume=("suppress_signal_plan_volume", "sum"),
        )
        .loc[:, columns]
    )
    grouped["net_stop_close_volume"] = (
        grouped["stop_close_volume"] - grouped["retry_open_volume"]
    ).clip(lower=0.0)
    return grouped


def _apply_live_stop_to_current_positions(
    current_positions: pd.DataFrame,
    grouped: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if current_positions.empty or grouped.empty:
        return current_positions.copy(), []
    deltas = {
        (_clean_text(row["vt_symbol"]), _clean_text(row["position_direction"])): min(
            0.0,
            _to_float(row.get("position_delta_volume"), 0.0),
        )
        for row in grouped.to_dict(orient="records")
    }
    frame = current_positions.copy()
    audit_rows: list[dict[str, Any]] = []
    keep_mask = pd.Series(True, index=frame.index)
    for idx, row in frame.iterrows():
        vt_symbol = _clean_text(row.get("vt_symbol"))
        direction = _normal_direction(row.get("direction"))
        delta = deltas.get((vt_symbol, direction), 0.0)
        if delta >= 0:
            continue
        original_signed = _to_float(row.get("end_pos", row.get("volume")), 0.0)
        original_volume = abs(original_signed)
        if original_volume <= 0:
            continue
        new_volume = max(0.0, original_volume + delta)
        applied_delta = new_volume - original_volume
        if abs(applied_delta) <= 1e-9:
            continue
        sign = -1.0 if direction == "short" else 1.0
        if "end_pos" in frame.columns:
            frame.at[idx, "end_pos"] = sign * new_volume
        if "margin_exact" in frame.columns:
            original_margin = _to_float(row.get("margin_exact"), 0.0)
            frame.at[idx, "margin_exact"] = original_margin * (new_volume / original_volume)
        if "live_stop_alignment_delta_volume" not in frame.columns:
            frame["live_stop_alignment_delta_volume"] = 0.0
        frame.at[idx, "live_stop_alignment_delta_volume"] = applied_delta
        if "live_stop_alignment_note" not in frame.columns:
            frame["live_stop_alignment_note"] = ""
        frame.at[idx, "live_stop_alignment_note"] = "aligned_with_stage904_realtime_stop_fill"
        if new_volume <= 1e-9:
            keep_mask.at[idx] = False
        audit_rows.append(
            {
                "vt_symbol": vt_symbol,
                "direction": direction,
                "original_volume": original_volume,
                "new_volume": new_volume,
                "applied_delta_volume": applied_delta,
                "row_removed": int(new_volume <= 1e-9),
            }
        )
    return frame.loc[keep_mask].reset_index(drop=True), audit_rows


def _suppress_stage901_open_rows(
    frame: pd.DataFrame,
    grouped: pd.DataFrame,
    *,
    source_name: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if frame.empty or grouped.empty:
        return frame.copy(), []
    suppress_keys = {
        (_clean_text(row["vt_symbol"]), _clean_text(row["position_direction"]))
        for row in grouped.to_dict(orient="records")
        if _to_float(row.get("suppress_signal_plan_volume"), 0.0) > 0
    }
    if not suppress_keys:
        return frame.copy(), []
    out = frame.copy()
    keep_mask = pd.Series(True, index=out.index)
    audit_rows: list[dict[str, Any]] = []
    for idx, row in out.iterrows():
        vt_symbol = _clean_text(row.get("vt_symbol"))
        direction = _normal_direction(row.get("direction"))
        offset = _normal_offset(row.get("offset"))
        if offset != "open" or (vt_symbol, direction) not in suppress_keys:
            continue
        keep_mask.at[idx] = False
        audit_rows.append(
            {
                "source": source_name,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "offset": offset,
                "volume": _to_float(row.get("volume", row.get("planned_volume")), 0.0),
                "suppress_reason": "stage901_open_already_touched_by_stage904_realtime_stop_logic",
            }
        )
    return out.loc[keep_mask].reset_index(drop=True), audit_rows


def _align_shadow_with_live_stop_fills(
    *,
    current_positions: pd.DataFrame,
    signal_plan: pd.DataFrame,
    pending_orders: pd.DataFrame,
    trades: pd.DataFrame,
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    ledger_rows = read_execution_ledger()
    events = _live_stop_alignment_events(
        ledger_rows=ledger_rows,
        trades=trades,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
    )
    grouped = _alignment_group(events)
    aligned_positions, position_adjustments = _apply_live_stop_to_current_positions(current_positions, grouped)
    aligned_signal_plan, suppressed_signals = _suppress_stage901_open_rows(
        signal_plan,
        grouped,
        source_name="signal_plan",
    )
    aligned_pending_orders, suppressed_pending = _suppress_stage901_open_rows(
        pending_orders,
        grouped,
        source_name="pending_orders",
    )
    live_stop_alignment = {
        "enabled": True,
        "ledger_path": str(LIVE_EXECUTION_LEDGER_PATH),
        "ledger_row_count": int(len(ledger_rows)),
        "event_count": int(len(events)),
        "stop_close_event_count": int((events.get("stop_close_volume", pd.Series(dtype=float)) > 0).sum()) if not events.empty else 0,
        "retry_open_event_count": int((events.get("retry_open_volume", pd.Series(dtype=float)) > 0).sum()) if not events.empty else 0,
        "position_adjustment_count": int(len(position_adjustments)),
        "position_removed_count": int(sum(row.get("row_removed", 0) for row in position_adjustments)),
        "signal_plan_suppressed_count": int(len(suppressed_signals)),
        "pending_order_suppressed_count": int(len(suppressed_pending)),
        "position_adjustments": position_adjustments,
        "suppressed_rows": suppressed_signals + suppressed_pending,
        "events": events.to_dict(orient="records"),
    }
    return aligned_positions, aligned_signal_plan, aligned_pending_orders, events, live_stop_alignment


def _known_trading_dates() -> pd.Series:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        return pd.Series(dtype="datetime64[ns]")
    frame = pd.read_csv(ALL_FUTURES_MAPPING_PATH, encoding="utf-8-sig")
    if frame.empty or "date" not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["date"], errors="coerce").dropna().drop_duplicates().sort_values().reset_index(drop=True)


def _required_ai_eval_dates(analysis_start: pd.Timestamp, analysis_end: pd.Timestamp) -> list[str]:
    dates = _known_trading_dates()
    if dates.empty:
        return []
    periods = pd.period_range(analysis_start.to_period("M"), analysis_end.to_period("M"), freq="M")
    required: list[str] = []
    for period in periods:
        month_start = pd.Timestamp(year=period.year, month=period.month, day=1)
        eligible = dates[dates < month_start]
        if eligible.empty:
            continue
        required.append(pd.Timestamp(eligible.iloc[-1]).date().isoformat())
    return sorted(set(required))


def _ai_pool_audit(path: Path, analysis_start: pd.Timestamp, analysis_end: pd.Timestamp) -> dict[str, Any]:
    required_eval_dates = _required_ai_eval_dates(analysis_start, analysis_end)
    calendar_blockers = [] if required_eval_dates else ["trading_calendar_unavailable"]
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "required_eval_dates": required_eval_dates,
            "missing_required_eval_dates": required_eval_dates,
            "contract_status": "invalid",
            "invalid_contract_eval_dates": required_eval_dates,
            "contract_blockers": [
                *calendar_blockers,
                "eligibility_file_missing",
                *[f"{date}:missing_eval_date" for date in required_eval_dates],
            ],
        }
    payload = path.read_bytes()
    eligibility_sha256 = hashlib.sha256(payload).hexdigest()
    frame = pd.read_csv(BytesIO(payload), encoding="utf-8-sig")
    required_columns = {
        "strategy",
        "score_type",
        "eval_date",
        "product_vt_symbol",
        "score_rank",
        "top_n",
    }
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        return {
            "path": str(path),
            "exists": True,
            "rows": int(len(frame)),
            "eligibility_sha256": eligibility_sha256,
            "required_eval_dates": required_eval_dates,
            "missing_required_eval_dates": required_eval_dates,
            "contract_status": "invalid",
            "invalid_contract_eval_dates": required_eval_dates,
            "contract_blockers": [
                *calendar_blockers,
                f"missing_columns:{','.join(missing_columns)}",
            ],
        }
    strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
    frame = frame[frame["strategy"].astype(str).eq(strategy)].copy()
    if frame.empty:
        return {
            "path": str(path),
            "exists": True,
            "rows": 0,
            "eligibility_sha256": eligibility_sha256,
            "required_eval_dates": required_eval_dates,
            "missing_required_eval_dates": required_eval_dates,
            "contract_status": "invalid",
            "invalid_contract_eval_dates": required_eval_dates,
            "contract_blockers": [
                *calendar_blockers,
                "official_strategy_rows_missing",
                *[f"{date}:missing_eval_date" for date in required_eval_dates],
            ],
        }
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    if frame["eval_date"].isna().any():
        return {
            "path": str(path),
            "exists": True,
            "rows": int(len(frame)),
            "eligibility_sha256": eligibility_sha256,
            "required_eval_dates": required_eval_dates,
            "missing_required_eval_dates": required_eval_dates,
            "contract_status": "invalid",
            "invalid_contract_eval_dates": required_eval_dates,
            "contract_blockers": [*calendar_blockers, "invalid_eval_date"],
        }
    latest_date = frame["eval_date"].max()
    latest = frame[frame["eval_date"].eq(latest_date)].sort_values(["score_rank", "product_vt_symbol"])
    available_eval_dates = {
        pd.Timestamp(value).date().isoformat()
        for value in frame["eval_date"].dropna().drop_duplicates().tolist()
    }
    contract_blockers: list[str] = list(calendar_blockers)
    invalid_contract_eval_dates: list[str] = []
    for required_date in required_eval_dates:
        snapshot = frame[
            frame["eval_date"].eq(pd.Timestamp(required_date))
        ].sort_values(["score_rank", "product_vt_symbol"])
        snapshot_blockers = official_ai_pool_snapshot_blockers(
            products=snapshot["product_vt_symbol"].tolist(),
            ranks=snapshot["score_rank"].tolist(),
            top_ns=snapshot["top_n"].tolist(),
            eval_date=required_date,
            score_types=snapshot["score_type"].tolist(),
        )
        if snapshot_blockers:
            invalid_contract_eval_dates.append(required_date)
            contract_blockers.extend(
                f"{required_date}:{blocker}" for blocker in snapshot_blockers
            )
    return {
        "path": str(path),
        "exists": True,
        "rows": int(len(frame)),
        "eligibility_sha256": eligibility_sha256,
        "min_eval_date": frame["eval_date"].min().date().isoformat(),
        "max_eval_date": latest_date.date().isoformat(),
        "unique_eval_dates": int(frame["eval_date"].nunique()),
        "latest_products": latest["product_vt_symbol"].astype(str).tolist(),
        "required_eval_dates": required_eval_dates,
        "missing_required_eval_dates": [
            date for date in required_eval_dates if date not in available_eval_dates
        ],
        "contract_status": "invalid" if contract_blockers else "valid",
        "invalid_contract_eval_dates": invalid_contract_eval_dates,
        "contract_blockers": contract_blockers,
    }


def _assert_ai_pool_contract_valid(audit: dict[str, Any]) -> None:
    if (
        audit.get("contract_status") == "valid"
        and not audit.get("missing_required_eval_dates")
    ):
        return
    blockers = [str(value) for value in audit.get("contract_blockers", [])]
    missing_dates = [
        str(value) for value in audit.get("missing_required_eval_dates", [])
    ]
    detail = ";".join([*blockers, *[f"missing_eval_date:{value}" for value in missing_dates]])
    raise RuntimeError(f"official_ai_pool_contract_invalid:{detail or 'unknown'}")


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_private_temp(*, parent: Path, destination_name: str, payload: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _publish_execution_artifact_cohort(
    *,
    decision: dict[str, Any],
    signal_plan: pd.DataFrame,
    current_positions: pd.DataFrame,
    pending_orders: pd.DataFrame,
    entry_risk: pd.DataFrame,
    profile=C9_15W_PROFILE,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    """Publish the executable Stage901 inputs with the audit seal last.

    Readers snapshot the audit before and after reading the other five files.
    Replacing the audit last means an interrupted publication can only yield a
    hash mismatch and fail closed; it cannot bless a mixed generation.
    """

    paths = {
        "official_summary": profile.summary_path,
        "signal_plan": profile.signal_plan_path,
        "current_positions": profile.current_positions_path,
        "pending_orders": profile.pending_orders_path,
        "entry_risk": profile.entry_risk_path,
        "audit": profile.pending_orders_audit_path,
    }
    if paths["entry_risk"] is None:
        raise ValueError("stage901_entry_risk_path_missing")
    parents = {path.parent.resolve(strict=True) for path in paths.values()}
    if len(parents) != 1:
        raise ValueError("stage901_artifact_cohort_parent_mismatch")
    parent = next(iter(parents))
    parent_metadata = parent.lstat()
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(parent_metadata.st_mode) & 0o022
    ):
        raise ValueError("stage901_artifact_cohort_parent_security_invalid")

    target_date = _clean_text(decision.get("analysis_end"))
    expected_identity = _official_live_identity()
    if not target_date or any(
        decision.get(key) != value for key, value in expected_identity.items()
    ):
        raise ValueError("stage901_artifact_cohort_identity_invalid")
    seed_pending = pending_orders.copy()
    seed_payloads = {
        "official_summary": _json_bytes(decision),
        "signal_plan": _csv_bytes(signal_plan),
        "current_positions": _csv_bytes(current_positions),
        "pending_orders": _csv_bytes(seed_pending),
        "entry_risk": _csv_bytes(entry_risk),
    }
    cohort_seed = {
        "target_date": target_date,
        **expected_identity,
        "generated_at": _clean_text(decision.get("generated_at")),
        "artifact_sha256s": {
            name: hashlib.sha256(payload).hexdigest()
            for name, payload in seed_payloads.items()
        },
    }
    cohort_id = hashlib.sha256(_json_bytes(cohort_seed)).hexdigest()

    published_pending = pending_orders.copy()
    row_identity = {
        "cohort_id": cohort_id,
        "target_date": target_date,
        **expected_identity,
    }
    for key, value in row_identity.items():
        published_pending[key] = value
    published_decision = {
        **decision,
        "cohort_id": cohort_id,
        "pending_order_count": int(len(published_pending)),
        "pending_orders": published_pending.to_dict(orient="records"),
    }
    artifact_payloads = {
        "official_summary": _json_bytes(published_decision),
        "signal_plan": _csv_bytes(signal_plan),
        "current_positions": _csv_bytes(current_positions),
        "pending_orders": _csv_bytes(published_pending),
        "entry_risk": _csv_bytes(entry_risk),
    }
    audit = {
        "schema_version": PENDING_ARTIFACT_SCHEMA_VERSION,
        "status": "ready",
        "cohort_id": cohort_id,
        "target_date": target_date,
        **expected_identity,
        **{
            f"{name}_sha256": hashlib.sha256(payload).hexdigest()
            for name, payload in artifact_payloads.items()
        },
        "pending_order_count": int(len(published_pending)),
        "order_api_called_count": 0,
        "publish_protocol": "five_artifacts_then_audit_generation_seal",
    }
    payloads = {**artifact_payloads, "audit": _json_bytes(audit)}
    temporary_paths: dict[str, Path] = {}
    try:
        for name, payload in payloads.items():
            temporary_paths[name] = _write_private_temp(
                parent=parent,
                destination_name=paths[name].name,
                payload=payload,
            )
        for name in (
            "official_summary",
            "signal_plan",
            "current_positions",
            "pending_orders",
            "entry_risk",
        ):
            os.replace(temporary_paths.pop(name), paths[name])
        parent_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
            os.replace(temporary_paths.pop("audit"), paths["audit"])
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        for temporary in temporary_paths.values():
            temporary.unlink(missing_ok=True)
    return published_decision, published_pending, audit


def _load_stage861_full_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    if s861.FULL_MINUTE_BARS_PATH.exists():
        data = pd.read_csv(s861.FULL_MINUTE_BARS_PATH, encoding="utf-8-sig")
    else:
        data = s861._load_full_minute_bars(vt_symbols)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" not in data.columns:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    else:
        data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).reset_index(drop=True)


def _ensure_c9_minute_bars(metadata: dict[str, Any]) -> dict[str, Any]:
    global _FULL_MINUTE_BY_SYMBOL_CACHE, _FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS, _LAST_MINUTE_AUDIT

    vt_symbols = set(str(item) for item in metadata.get("vt_symbols", []))
    if _FULL_MINUTE_BY_SYMBOL_CACHE is None or not vt_symbols.issubset(_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS):
        minute_bars = _load_stage861_full_minute_bars(vt_symbols)
        _FULL_MINUTE_BY_SYMBOL_CACHE = s847.s825._minute_groups(minute_bars)
        _FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = set(_FULL_MINUTE_BY_SYMBOL_CACHE.keys())

    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = _FULL_MINUTE_BY_SYMBOL_CACHE
    _LAST_MINUTE_AUDIT = {
        "source": str(s861.FULL_MINUTE_BARS_PATH),
        "source_exists": bool(s861.FULL_MINUTE_BARS_PATH.exists()),
        "requested_symbol_count": int(len(vt_symbols)),
        "loaded_symbol_count": int(len(_FULL_MINUTE_BY_SYMBOL_CACHE or {})),
        "missing_symbol_count": int(len(vt_symbols - _FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS)),
    }
    return dict(_LAST_MINUTE_AUDIT)


def _run_live_c9(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    minute_audit = _ensure_c9_minute_bars(metadata)
    try:
        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = s847._c9_profile(metadata)
        spec = profile["spec"]
        capital = replace(
            spec.capital,
            variant=OFFICIAL_LIVE_PROFILE_NAME,
            label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} live default",
            account_capital=OFFICIAL_LIVE_CAPITAL,
            c3_capital=OFFICIAL_LIVE_CAPITAL,
            note=(
                f"{spec.capital.note} | Stage901 official live default operator override. "
                "C9 is promoted to live default by explicit operator request; no parameter search."
            ),
        )
        live_profile = dict(profile)
        live_profile["profile"] = OFFICIAL_LIVE_PROFILE_NAME
        live_overrides = {**spec.overrides, **build_official_live_strategy_overrides()}
        live_profile["spec"] = replace(
            spec,
            capital=capital,
            overrides=live_overrides,
            profile=OFFICIAL_LIVE_PROFILE_NAME,
        )
        combined, frames = s847._run_profile(live_profile, metadata)
        live_spec = live_profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    combined["account_capital"] = live_spec.capital.account_capital
    combined["c3_capital"] = live_spec.capital.c3_capital
    combined["profile"] = live_spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = live_spec.capital.account_capital
        frame["c3_capital"] = live_spec.capital.c3_capital
        frame["profile"] = live_spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = 0
    combined["minute_source"] = minute_audit["source"]
    combined["minute_loaded_symbol_count"] = minute_audit["loaded_symbol_count"]
    return combined, frames, live_spec


def _signal_plan_from_trades(trades: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    columns = [
        "shadow_session_id",
        "trade_id",
        "vt_symbol",
        "direction",
        "offset",
        "volume",
        "theoretical_price",
        "real_t1_open_proxy_price",
        "day_session_open_proxy_price",
        "proxy_quality",
        "exit_reason",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].eq(target_date.normalize())].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)
    target = target_date.date().isoformat()
    frame["shadow_session_id"] = frame["trade_id"].astype(str).map(
        lambda value: f"C9LIVE-{target.replace('-', '')}-{value.replace('.', '-')}"
    )
    frame["theoretical_price"] = pd.to_numeric(frame.get("price", 0.0), errors="coerce").fillna(0.0)
    frame["real_t1_open_proxy_price"] = ""
    frame["day_session_open_proxy_price"] = ""
    frame["proxy_quality"] = "historical_shadow_trade_price_no_broker_submit"
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, columns].sort_values(["vt_symbol", "trade_id"]).reset_index(drop=True)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    monthly: pd.DataFrame,
    current_positions: pd.DataFrame,
    signal_plan: pd.DataFrame,
    pending_orders: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    live_stop_alignment = (
        decision.get("live_stop_alignment", {}) if isinstance(decision.get("live_stop_alignment"), dict) else {}
    )
    live_stop_events = pd.DataFrame(live_stop_alignment.get("events", []))
    if not live_stop_events.empty:
        live_stop_events = live_stop_events[
            [
                column
                for column in [
                    "generated_at",
                    "vt_symbol",
                    "position_direction",
                    "source",
                    "source_reason",
                    "fill_price",
                    "fill_volume",
                    "position_delta_volume",
                    "alignment_note",
                ]
                if column in live_stop_events.columns
            ]
        ]
    lines = [
        "# Stage901 C9 当前实盘默认影子盘",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘默认：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 统计区间：`{decision['analysis_start']}` 至 `{decision['analysis_end']}`。",
        "- 性质：只读影子盘绩效；不连接 CTP，不读取账户，不调用下单。",
        "- 统计起点由 `OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE` 或命令行 `--analysis-start` 决定。",
        "- 切换口径：operator override，把 C9 从 primary candidate 切为 live default。",
        f"- AI 池文件：`{decision['ai_pool_audit'].get('path', '')}`。",
        f"- AI 池最新 eval_date：`{decision['ai_pool_audit'].get('max_eval_date', '')}`。",
        f"- 本次回放需要 AI 池 eval_date：`{', '.join(decision['ai_pool_audit'].get('required_eval_dates', []))}`。",
        f"- 本次回放缺失 AI 池 eval_date：`{', '.join(decision['ai_pool_audit'].get('missing_required_eval_dates', [])) or '无'}`。",
        f"- AI 池正式合同：`{decision['ai_pool_audit'].get('contract_status', 'invalid')}`；异常月份：`{', '.join(decision['ai_pool_audit'].get('invalid_contract_eval_dates', [])) or '无'}`。",
        f"- AI 池最新品种：`{', '.join(decision['ai_pool_audit'].get('latest_products', []))}`。",
        f"- 实际 strategy override AI 池：`{decision['strategy_ai_product_pool_eligibility_path']}`。",
        f"- C9 分钟K源：`{decision['minute_audit'].get('source', '')}`，已加载合约数 `{decision['minute_audit'].get('loaded_symbol_count', '')}`。",
        "",
        "## 核心结果",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "end_equity",
                    "total_return_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ]
        ),
        "",
        "## 月度结果",
        "",
        _md_table(
            monthly[
                [
                    "variant",
                    "month",
                    "start_equity",
                    "end_equity",
                    "return_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "trade_count",
                    "slippage",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 当前持仓快照",
        "",
        _md_table(current_positions, max_rows=80),
        "",
        "## 目标日信号计划",
        "",
        _md_table(signal_plan, max_rows=80),
        "",
        "## 目标日后 Pending Orders",
        "",
        _md_table(pending_orders, max_rows=80),
        "",
        "## 实时止损对齐",
        "",
        f"- ledger 文件：`{live_stop_alignment.get('ledger_path', '')}`。",
        f"- ledger 行数：`{live_stop_alignment.get('ledger_row_count', 0)}`。",
        f"- 对齐事件数：`{live_stop_alignment.get('event_count', 0)}`。",
        f"- 持仓扣减行数：`{live_stop_alignment.get('position_adjustment_count', 0)}`。",
        f"- 移除持仓行数：`{live_stop_alignment.get('position_removed_count', 0)}`。",
        f"- signal_plan 抑制行数：`{live_stop_alignment.get('signal_plan_suppressed_count', 0)}`。",
        f"- pending_order 抑制行数：`{live_stop_alignment.get('pending_order_suppressed_count', 0)}`。",
        _md_table(live_stop_events, max_rows=40),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 判断",
        "",
        f"- 风险层级：`{decision['risk_snapshot']['risk_level']}`。",
        f"- 是否允许真实新开仓：`{decision['risk_snapshot']['allow_real_new_orders']}`。",
        f"- 目标日信号数：`{decision['target_signal_count']}`。",
        f"- 目标日后 pending order 数：`{decision['pending_order_count']}`。",
        f"- 实时止损对齐事件数：`{live_stop_alignment.get('event_count', 0)}`。",
        f"- 实时止损抑制理论开仓数：`{live_stop_alignment.get('signal_plan_suppressed_count', 0)}`。",
        "- 决策：`stage901_c9_live_default_shadow_measured_no_order_api`。",
        "- 后续真实执行仍需 fresh read-only、dry-run、broker-state reconciliation 和显式下单确认。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run C9 official live default shadow.")
    parser.add_argument("--analysis-start", default=OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE)
    parser.add_argument("--target-date", default="2026-06-12")
    args = parser.parse_args()

    analysis_start = pd.Timestamp(str(args.analysis_start)).normalize()
    analysis_end = pd.Timestamp(str(args.target_date)).normalize()

    ai_pool_audit = _ai_pool_audit(
        OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
        analysis_start,
        analysis_end,
    )
    _assert_ai_pool_contract_valid(ai_pool_audit)

    metadata = s513._metadata()
    combined, frames, spec = _run_live_c9(metadata, analysis_start, analysis_end)
    positions = frames.get("positions", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    pending_orders = frames.get("pending_orders", pd.DataFrame()).copy()

    if not positions.empty:
        _margin_daily, product_margin = s513._position_margin(positions, metadata)
    else:
        product_margin = pd.DataFrame()

    summary_rows = []
    cost_rows = []
    for cost_multiplier in s653.COST_MULTIPLIERS:
        row = s650._metrics(combined, spec.capital, cost_multiplier)
        row["profile"] = spec.profile
        row["official_live_version"] = OFFICIAL_LIVE_VERSION
        cost_rows.append(row)
        if cost_multiplier == 1.0:
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    monthly = s658._monthly_returns(combined)
    latest_date = pd.to_datetime(combined["date"], errors="coerce").max().normalize()
    current_positions = s658._current_positions(positions, metadata, latest_date)
    signal_plan = _signal_plan_from_trades(trades, analysis_end)
    current_positions, signal_plan, pending_orders, live_stop_events, live_stop_alignment = (
        _align_shadow_with_live_stop_fills(
            current_positions=current_positions,
            signal_plan=signal_plan,
            pending_orders=pending_orders,
            trades=trades,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
    )

    current_row = summary[summary["variant"].eq(OFFICIAL_LIVE_PROFILE_NAME)].to_dict(orient="records")
    decision = {
        "stage": "Stage901",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "latest_available_data_date": latest_date.date().isoformat(),
        **_official_live_identity(),
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "ai_pool_audit": ai_pool_audit,
        "minute_audit": dict(_LAST_MINUTE_AUDIT),
        "strategy_ai_product_pool_eligibility_path": str(spec.overrides.get("ai_product_pool_eligibility_path", "")),
        "live_stop_alignment": live_stop_alignment,
        "current_variant": current_row[0] if current_row else {},
        "risk_snapshot": {},
        "decision": "stage901_c9_live_default_shadow_measured_no_order_api",
        "execution_scope": "read-only backtest/shadow performance only; no CTP connection and no order API call",
        "shadow_replay_ai_pool_status": (
            "valid"
            if not ai_pool_audit.get("missing_required_eval_dates")
            and ai_pool_audit.get("contract_status") == "valid"
            else "invalid_ai_pool_contract"
        ),
        "target_signal_count": int(len(signal_plan)),
        "pending_order_count": int(len(pending_orders)),
        "pending_orders": pending_orders.to_dict(orient="records"),
        "current_position_count": int(len(current_positions)),
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    decision["risk_snapshot"] = build_official_live_risk_snapshot(decision)

    combined.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    live_stop_events.to_csv(LIVE_STOP_ALIGNMENT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    decision, pending_orders, _artifact_audit = _publish_execution_artifact_cohort(
        decision=decision,
        signal_plan=signal_plan,
        current_positions=current_positions,
        pending_orders=pending_orders,
        entry_risk=entry_risk,
    )
    _write_report(summary, cost, monthly, current_positions, signal_plan, pending_orders, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
