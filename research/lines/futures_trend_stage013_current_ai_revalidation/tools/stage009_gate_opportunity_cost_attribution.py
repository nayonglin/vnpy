#!/usr/bin/env python3
"""Stage009: read-only multi-start attribution of Stage013 gate opportunity cost."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage007_stage006_reconciled_equity_halfyear as s7  # noqa: E402


LINE_ID = s7.LINE_ID
STAGE_ID = "stage009_gate_opportunity_cost_attribution"
STAGE_LABEL = "Stage009"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = s7.A_VERSION
C_VERSION = s7.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)
YEAR_2022_START = pd.Timestamp("2022-01-01")
YEAR_2022_END = pd.Timestamp("2022-12-31")

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
SOURCE_OUT = s7.OUT
OUT = LINE_DIR / "outputs" / STAGE_ID
EVENT_PATH = OUT / f"{OUTPUT_PREFIX}_event_attribution_{MODEL_TAG}.csv.gz"
COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_windows_{MODEL_TAG}.csv"
START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_{MODEL_TAG}.csv"
YEAR_PATH = OUT / f"{OUTPUT_PREFIX}_by_year_{MODEL_TAG}.csv"
FEATURE_PATH = OUT / f"{OUTPUT_PREFIX}_feature_attribution_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_opportunity_cost_{MODEL_TAG}.png"

EX_ANTE_COLUMNS = (
    "ai_product_pool_rank",
    "ai_product_pool_score",
    "ai_product_pool_top_n",
    "oi_price_confirm_risk_restore_applied",
    "oi_price_confirm_passed",
    "breakout",
    "rsi_value",
    "risk_multiplier",
    "recovery_sleeve_applied",
    "streak_entry_structure_risk_recovery_applied",
    "active_positions_before",
    "portfolio_drawdown_pct",
    "same_direction_correlation_max_corr",
    "bullish_alignment",
    "bearish_alignment",
    "stop_distance",
    "planned_entry_price",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_manifest(directory: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
    missing: list[str] = []
    size_mismatch: list[str] = []
    hash_mismatch: list[str] = []
    listed = set(manifest["file"].astype(str))
    for row in manifest.itertuples(index=False):
        path = directory / str(row.file)
        if not path.exists():
            missing.append(str(row.file))
            continue
        if int(path.stat().st_size) != int(row.bytes):
            size_mismatch.append(str(row.file))
        if _sha256(path) != str(row.sha256):
            hash_mismatch.append(str(row.file))
    extras = sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file()
        and path != manifest_path
        and path.name not in listed
    )
    return {
        "manifest_rows": int(len(manifest)),
        "missing_files": missing,
        "size_mismatch_files": size_mismatch,
        "hash_mismatch_files": hash_mismatch,
        "unlisted_files": extras,
        "pass": not (missing or size_mismatch or hash_mismatch or extras),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (str, bytes)) else False:
        return None
    return value


def _date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    return pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()


def _direction_series(frame: pd.DataFrame) -> pd.Series:
    if "direction" not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame["direction"].fillna("").astype(str).str.lower()


def _window_drawdown_metrics(
    daily: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, Any]:
    data = daily.copy()
    data["_date"] = _date_series(data, "date")
    data["_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data = (
        data.dropna(subset=["_date", "_equity"])
        .sort_values("_date")
        .drop_duplicates("_date", keep="last")
        .reset_index(drop=True)
    )
    start = pd.Timestamp(start).tz_localize(None).normalize()
    end = pd.Timestamp(end).tz_localize(None).normalize()
    part_mask = data["_date"].between(start, end)
    part = data.loc[part_mask].copy()
    if part.empty:
        return {
            "window_rows": 0,
            "actual_window_start": "",
            "actual_window_end": "",
            "historical_hwm_at_window_start": np.nan,
            "local_seed_equity": np.nan,
            "account_history_max_drawdown_pct": np.nan,
            "local_window_reset_max_drawdown_pct": np.nan,
        }

    prior = data[data["_date"] < start]
    if not prior.empty:
        local_seed = float(prior["_equity"].iloc[-1])
        historical_hwm = float(prior["_equity"].max())
    else:
        if "account_capital" in data.columns:
            capital = pd.to_numeric(data["account_capital"], errors="coerce").dropna()
            local_seed = float(capital.iloc[0]) if not capital.empty else float(part["_equity"].iloc[0])
        else:
            local_seed = float(part["_equity"].iloc[0])
        historical_hwm = local_seed

    full_hwm = data["_equity"].cummax()
    account_drawdown = (data["_equity"] / full_hwm - 1.0) * 100.0
    account_window_drawdown = account_drawdown.loc[part.index]

    local_equity = part["_equity"].reset_index(drop=True)
    local_hwm = (
        pd.concat([pd.Series([local_seed]), local_equity], ignore_index=True)
        .cummax()
        .iloc[1:]
        .reset_index(drop=True)
    )
    local_drawdown = (local_equity / local_hwm - 1.0) * 100.0
    return {
        "window_rows": int(len(part)),
        "actual_window_start": part["_date"].iloc[0].date().isoformat(),
        "actual_window_end": part["_date"].iloc[-1].date().isoformat(),
        "historical_hwm_at_window_start": historical_hwm,
        "local_seed_equity": local_seed,
        "account_history_max_drawdown_pct": float(account_window_drawdown.min()),
        "local_window_reset_max_drawdown_pct": float(local_drawdown.min()),
    }


def _candidate_matches(event: pd.Series, candidates: pd.DataFrame) -> pd.DataFrame:
    data = candidates.copy()
    if data.empty:
        return data
    event_date = pd.Timestamp(event.get("date")).tz_localize(None).normalize()
    event_symbol = str(event.get("vt_symbol") or event.get("contract_vt_symbol") or "")
    event_direction = str(event.get("direction") or "").lower()
    event_signal = str(event.get("signal") or "")
    signal = data["signal"].fillna("").astype(str) if "signal" in data.columns else pd.Series("", index=data.index)
    status = (
        data["candidate_status"].fillna("").astype(str).str.lower()
        if "candidate_status" in data.columns
        else pd.Series("", index=data.index)
    )
    symbol = (
        data["contract_vt_symbol"].fillna("").astype(str)
        if "contract_vt_symbol" in data.columns
        else pd.Series("", index=data.index)
    )
    mask = (
        _date_series(data, "date").eq(event_date)
        & symbol.eq(event_symbol)
        & _direction_series(data).eq(event_direction)
        & status.eq("opened")
    )
    if event_signal:
        mask &= signal.eq(event_signal)
    return data.loc[mask].copy()


def _map_event_to_arm(
    event: pd.Series,
    *,
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
    closed_lots: pd.DataFrame,
    arm_prefix: str,
    trading_dates: pd.Series | None = None,
) -> dict[str, Any]:
    prefix = str(arm_prefix)
    matches = _candidate_matches(event, candidates)
    if len(matches) > 1:
        raise ValueError(f"ambiguous opened candidate for {prefix}: {len(matches)} rows")
    if matches.empty:
        return {f"{prefix}_mapping_status": "missing_opened_candidate"}

    candidate = matches.iloc[0]
    event_date = pd.Timestamp(event.get("date")).tz_localize(None).normalize()
    event_symbol = str(event.get("vt_symbol") or event.get("contract_vt_symbol") or "")
    event_direction = str(event.get("direction") or "").lower()
    trade_data = trades.copy()
    if trade_data.empty:
        return {f"{prefix}_mapping_status": "missing_open_trade"}
    offset = (
        trade_data["offset"].fillna("").astype(str).str.lower()
        if "offset" in trade_data.columns
        else pd.Series("", index=trade_data.index)
    )
    symbol = (
        trade_data["vt_symbol"].fillna("").astype(str)
        if "vt_symbol" in trade_data.columns
        else pd.Series("", index=trade_data.index)
    )
    trade_data["_date"] = _date_series(trade_data, "date")
    trade_data["_direction"] = _direction_series(trade_data)
    opens = trade_data[
        offset.eq("open")
        & symbol.eq(event_symbol)
        & trade_data["_direction"].eq(event_direction)
        & trade_data["_date"].gt(event_date)
    ].copy()
    if opens.empty:
        return {f"{prefix}_mapping_status": "missing_open_trade"}
    entry_date = opens["_date"].min()
    if trading_dates is not None:
        calendar = pd.to_datetime(trading_dates, errors="coerce")
        if getattr(calendar.dt, "tz", None) is not None:
            calendar = calendar.dt.tz_localize(None)
        calendar = calendar.dt.normalize().dropna().drop_duplicates().sort_values()
        future_dates = calendar[calendar.gt(event_date)]
        if future_dates.empty:
            return {f"{prefix}_mapping_status": "missing_next_trading_day"}
        expected_entry_date = pd.Timestamp(future_dates.iloc[0])
        if entry_date != expected_entry_date:
            return {
                f"{prefix}_mapping_status": "open_not_next_trading_day",
                f"{prefix}_expected_entry_date": expected_entry_date.date().isoformat(),
                f"{prefix}_observed_entry_date": entry_date.date().isoformat(),
            }

    later_candidates = candidates.copy()
    if not later_candidates.empty:
        later_dates = _date_series(later_candidates, "date")
        later_symbol = later_candidates["contract_vt_symbol"].fillna("").astype(str)
        later_direction = _direction_series(later_candidates)
        intervening = later_candidates[
            later_dates.gt(event_date)
            & later_dates.lt(entry_date)
            & later_symbol.eq(event_symbol)
            & later_direction.eq(event_direction)
        ]
        if not intervening.empty:
            return {f"{prefix}_mapping_status": "intervening_candidate_before_open"}

    opens = opens[opens["_date"].eq(entry_date)].copy()
    if "trade_id" not in opens.columns:
        return {f"{prefix}_mapping_status": "missing_open_trade_id"}
    open_ids = set(opens["trade_id"].dropna().astype(str))
    lots = closed_lots.copy()
    if lots.empty or "open_trade_id" not in lots.columns:
        return {f"{prefix}_mapping_status": "missing_closed_lot"}
    lots = lots[lots["open_trade_id"].fillna("").astype(str).isin(open_ids)].copy()
    if len(lots) < len(open_ids):
        represented = set(lots["open_trade_id"].dropna().astype(str))
        if represented != open_ids:
            return {f"{prefix}_mapping_status": "missing_closed_lot"}

    if "signal" in lots.columns and str(event.get("signal") or ""):
        nonempty_signals = lots["signal"].dropna().astype(str)
        nonempty_signals = nonempty_signals[nonempty_signals.ne("")]
        if not nonempty_signals.eq(str(event.get("signal"))).all():
            return {f"{prefix}_mapping_status": "closed_lot_signal_mismatch"}
    open_volume_by_id = (
        opens.assign(_trade_id=opens["trade_id"].astype(str))
        .groupby("_trade_id")["volume"]
        .apply(lambda values: pd.to_numeric(values, errors="coerce").sum())
    )
    closed_volume_by_id = (
        lots.assign(_open_trade_id=lots["open_trade_id"].astype(str))
        .groupby("_open_trade_id")["volume"]
        .apply(lambda values: pd.to_numeric(values, errors="coerce").sum())
    )
    for trade_id, open_volume in open_volume_by_id.items():
        closed_volume = float(closed_volume_by_id.get(trade_id, np.nan))
        if not np.isfinite(closed_volume) or abs(float(open_volume) - closed_volume) > 1e-9:
            return {f"{prefix}_mapping_status": "closed_volume_mismatch"}

    pnl = pd.to_numeric(lots["realized_pnl"], errors="coerce")
    r_multiple = pd.to_numeric(lots.get("r_multiple", pd.Series(dtype=float)), errors="coerce")
    result: dict[str, Any] = {
        f"{prefix}_mapping_status": "mapped",
        f"{prefix}_candidate_rows": 1,
        f"{prefix}_planned_volume": float(pd.to_numeric(pd.Series([candidate.get("selected_volume")]), errors="coerce").iloc[0]),
        f"{prefix}_entry_date": entry_date.date().isoformat(),
        f"{prefix}_entry_lag_calendar_days": int((entry_date - event_date).days),
        f"{prefix}_open_trade_count": int(len(opens)),
        f"{prefix}_opened_volume_sum": float(pd.to_numeric(opens["volume"], errors="coerce").sum()),
        f"{prefix}_closed_lot_count": int(len(lots)),
        f"{prefix}_realized_pnl": float(pnl.sum()),
        f"{prefix}_mean_r_multiple": float(r_multiple.mean()) if not r_multiple.empty else np.nan,
        f"{prefix}_last_exit_date": _date_series(lots, "exit_date").max().date().isoformat(),
    }
    for column in EX_ANTE_COLUMNS:
        result[f"{prefix}_{column}"] = candidate.get(column, np.nan)
    return result


def _linear_counterfactual_fields(
    *,
    realized_pnl: float,
    selected_volume_before: float,
    selected_volume_after: float,
) -> dict[str, float]:
    pnl = float(realized_pnl)
    before = float(selected_volume_before)
    after = float(selected_volume_after)
    if not np.isfinite(after) or after <= 0.0:
        raise ValueError("selected_volume_after must be positive")
    scaled = pnl * before / after
    delta = scaled - pnl
    return {
        "same_path_linear_pnl_at_before": scaled,
        "same_path_linear_delta_vs_actual": delta,
        "suppressed_gain_same_path": max(0.0, delta) if pnl > 0.0 else 0.0,
        "avoided_loss_same_path": max(0.0, -delta) if pnl < 0.0 else 0.0,
    }


def _coverage(expected: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    result = expected[["requested_start_month", "rows"]].copy()
    result = result.rename(columns={"rows": "expected_event_count"})
    if events.empty:
        aggregate = pd.DataFrame(
            columns=[
                "requested_start_month",
                "actual_event_count",
                "c_mapped_count",
                "a_mapped_count",
                "mapping_error_count",
            ]
        )
    else:
        data = events.copy()
        data["_c_mapped"] = data["c_mapping_status"].astype(str).eq("mapped").astype(int)
        data["_a_mapped"] = data["a_mapping_status"].astype(str).eq("mapped").astype(int)
        data["_mapping_error"] = (
            data["c_mapping_status"].astype(str).ne("mapped")
            | data["a_mapping_status"].astype(str).ne("mapped")
        ).astype(int)
        aggregate = (
            data.groupby("requested_start_month", as_index=False)
            .agg(
                actual_event_count=("requested_start_month", "size"),
                c_mapped_count=("_c_mapped", "sum"),
                a_mapped_count=("_a_mapped", "sum"),
                mapping_error_count=("_mapping_error", "sum"),
            )
        )
    result = result.merge(aggregate, on="requested_start_month", how="left")
    numeric = (
        "expected_event_count",
        "actual_event_count",
        "c_mapped_count",
        "a_mapped_count",
        "mapping_error_count",
    )
    for column in numeric:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["count_match"] = result["actual_event_count"].eq(result["expected_event_count"]).astype(int)
    result["all_c_mapped"] = result["c_mapped_count"].eq(result["expected_event_count"]).astype(int)
    result["all_a_mapped"] = result["a_mapped_count"].eq(result["expected_event_count"]).astype(int)
    return result.sort_values("requested_start_month").reset_index(drop=True)


def _coverage_pass(frame: pd.DataFrame) -> bool:
    return bool(
        not frame.empty
        and frame["count_match"].eq(1).all()
        and frame["all_c_mapped"].eq(1).all()
        and frame["all_a_mapped"].eq(1).all()
        and frame["mapping_error_count"].eq(0).all()
    )


def _source_path(start: str, version: str, kind: str) -> Path:
    return SOURCE_OUT / (
        f"{s7.OUTPUT_PREFIX}_{start}_{version}_{kind}_{s7.MODEL_TAG}.csv.gz"
    )


def _load_source(start: str, version: str, kind: str) -> pd.DataFrame:
    path = _source_path(start, version, kind)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _event_base(event: pd.Series, start: str, event_index: int) -> dict[str, Any]:
    return {
        "requested_start_month": start,
        "event_index": int(event_index),
        "event_id": "|".join(
            [
                start,
                str(event.get("date") or ""),
                str(event.get("vt_symbol") or ""),
                str(event.get("direction") or ""),
                str(event.get("signal") or ""),
                str(event_index),
            ]
        ),
        "signal_date": pd.Timestamp(event.get("date")).date().isoformat(),
        "year": int(pd.Timestamp(event.get("date")).year),
        "vt_symbol": str(event.get("vt_symbol") or ""),
        "product_vt_symbol": str(event.get("product_vt_symbol") or ""),
        "direction": str(event.get("direction") or "").lower(),
        "signal": str(event.get("signal") or ""),
        "authoritative_equity": float(event.get("stage006_authoritative_equity")),
        "authoritative_high_water": float(event.get("stage006_authoritative_high_water")),
        "authoritative_drawdown_ratio": float(event.get("stage006_authoritative_drawdown_pct")),
        "selected_volume_before": float(event.get("stage013_pilot_gate_selected_volume_before")),
        "selected_volume_after": float(event.get("stage013_pilot_gate_selected_volume_after")),
        "active_positions_before": float(event.get("stage013_pilot_gate_active_positions_before")),
        "drawdown_trigger_ratio": float(event.get("stage013_pilot_gate_drawdown_trigger_pct")),
    }


def _attribute_events(expected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for audit in expected.itertuples(index=False):
        start = str(audit.requested_start_month)
        expected_count = int(audit.rows)
        if expected_count == 0:
            continue
        event_path = _source_path(start, C_VERSION, "pilot_gate_events")
        if not event_path.exists():
            rows.append(
                {
                    "requested_start_month": start,
                    "event_index": -1,
                    "event_id": f"{start}|missing-event-file",
                    "c_mapping_status": "missing_event_file",
                    "a_mapping_status": "missing_event_file",
                }
            )
            continue
        events = pd.read_csv(event_path, encoding="utf-8-sig", low_memory=False)
        arm_data = {
            version: {
                "candidates": _load_source(start, version, "entry_candidates"),
                "trades": _load_source(start, version, "trades"),
                "closed_lots": _load_source(start, version, "closed_lots"),
                "trading_dates": _load_source(start, version, "daily").get(
                    "date", pd.Series(dtype=str)
                ),
            }
            for version in VERSIONS
        }
        for event_index, event in events.reset_index(drop=True).iterrows():
            row = _event_base(event, start, int(event_index))
            try:
                row.update(
                    _map_event_to_arm(
                        event,
                        **arm_data[C_VERSION],
                        arm_prefix="c",
                    )
                )
                row.update(
                    _map_event_to_arm(
                        event,
                        **arm_data[A_VERSION],
                        arm_prefix="a",
                    )
                )
            except ValueError as exc:
                row.update(
                    {
                        "c_mapping_status": f"error:{exc}",
                        "a_mapping_status": f"error:{exc}",
                    }
                )
            if row.get("c_mapping_status") == "mapped":
                row.update(
                    _linear_counterfactual_fields(
                        realized_pnl=float(row["c_realized_pnl"]),
                        selected_volume_before=float(row["selected_volume_before"]),
                        selected_volume_after=float(row["selected_volume_after"]),
                    )
                )
                row["c_winner"] = int(float(row["c_realized_pnl"]) > 0.0)
            rows.append(row)
    return pd.DataFrame(rows)


def _drawdown_windows(expected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start in expected["requested_start_month"].astype(str):
        for version in VERSIONS:
            daily = _load_source(start, version, "daily")
            metrics = _window_drawdown_metrics(
                daily, start=YEAR_2022_START, end=YEAR_2022_END
            )
            rows.append(
                {
                    "requested_start_month": start,
                    "version": version,
                    **metrics,
                }
            )
    arm = pd.DataFrame(rows)
    pair_rows = []
    for start, group in arm.groupby("requested_start_month", sort=True):
        if set(group["version"]) != set(VERSIONS):
            continue
        a = group[group["version"].eq(A_VERSION)].iloc[0]
        c = group[group["version"].eq(C_VERSION)].iloc[0]
        pair_rows.append(
            {
                "requested_start_month": start,
                "window_rows": min(int(a["window_rows"]), int(c["window_rows"])),
                "a_account_history_max_drawdown_pct": a["account_history_max_drawdown_pct"],
                "c_account_history_max_drawdown_pct": c["account_history_max_drawdown_pct"],
                "account_history_drawdown_improvement_pp": (
                    float(c["account_history_max_drawdown_pct"] - a["account_history_max_drawdown_pct"])
                    if int(a["window_rows"]) and int(c["window_rows"])
                    else np.nan
                ),
                "a_local_window_reset_max_drawdown_pct": a["local_window_reset_max_drawdown_pct"],
                "c_local_window_reset_max_drawdown_pct": c["local_window_reset_max_drawdown_pct"],
                "local_window_reset_drawdown_improvement_pp": (
                    float(c["local_window_reset_max_drawdown_pct"] - a["local_window_reset_max_drawdown_pct"])
                    if int(a["window_rows"]) and int(c["window_rows"])
                    else np.nan
                ),
                "a_historical_hwm_at_window_start": a["historical_hwm_at_window_start"],
                "c_historical_hwm_at_window_start": c["historical_hwm_at_window_start"],
            }
        )
    return pd.DataFrame(pair_rows)


def _aggregate(events: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    mapped = events[
        events["c_mapping_status"].astype(str).eq("mapped")
        & events["a_mapping_status"].astype(str).eq("mapped")
    ].copy()
    return (
        mapped.groupby(keys, dropna=False, as_index=False)
        .agg(
            event_count=("event_id", "size"),
            distinct_start_count=("requested_start_month", "nunique"),
            c_winner_count=("c_winner", "sum"),
            c_realized_pnl=("c_realized_pnl", "sum"),
            a_realized_pnl=("a_realized_pnl", "sum"),
            same_path_linear_pnl_at_before=("same_path_linear_pnl_at_before", "sum"),
            same_path_linear_delta_vs_actual=("same_path_linear_delta_vs_actual", "sum"),
            suppressed_gain_same_path=("suppressed_gain_same_path", "sum"),
            avoided_loss_same_path=("avoided_loss_same_path", "sum"),
            selected_volume_before=("selected_volume_before", "sum"),
            selected_volume_after=("selected_volume_after", "sum"),
        )
        .sort_values(keys)
        .reset_index(drop=True)
    )


def _feature_buckets(events: pd.DataFrame) -> pd.DataFrame:
    data = events.copy()
    data["before_volume_bucket"] = pd.cut(
        pd.to_numeric(data["selected_volume_before"], errors="coerce"),
        bins=[-np.inf, 2, 4, 6, np.inf],
        labels=["le2", "3_4", "5_6", "ge7"],
    ).astype(str)
    dd = pd.to_numeric(data["authoritative_drawdown_ratio"], errors="coerce")
    data["drawdown_bucket"] = pd.cut(
        dd,
        bins=[-np.inf, 0.32, 0.35, np.inf],
        labels=["30_32pct", "32_35pct", "ge35pct"],
    ).astype(str)
    rank = pd.to_numeric(data.get("c_ai_product_pool_rank"), errors="coerce")
    data["ai_rank_bucket"] = pd.cut(
        rank,
        bins=[-np.inf, 3, 6, np.inf],
        labels=["rank1_3", "rank4_6", "rank7plus"],
    ).astype(str)
    data.loc[rank.isna(), "ai_rank_bucket"] = "missing"
    data["oi_confirm_bucket"] = np.where(
        pd.to_numeric(data.get("c_oi_price_confirm_risk_restore_applied"), errors="coerce").fillna(0).eq(1),
        "oi_confirmed",
        "not_confirmed",
    )
    data["active_bucket"] = (
        "active_" + pd.to_numeric(data["active_positions_before"], errors="coerce").fillna(-1).astype(int).astype(str)
    )
    parts = []
    for feature in (
        "before_volume_bucket",
        "drawdown_bucket",
        "ai_rank_bucket",
        "oi_confirm_bucket",
        "active_bucket",
        "direction",
    ):
        grouped = _aggregate(data.rename(columns={feature: "feature_value"}), ["feature_value"])
        grouped.insert(0, "feature", feature)
        parts.append(grouped)
    return pd.concat(parts, ignore_index=True, sort=False)


def _plot(by_start: pd.DataFrame, windows: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    active = by_start[by_start["event_count"].gt(0)].copy()
    x = np.arange(len(active))
    axes[0].bar(x - 0.2, active["suppressed_gain_same_path"], 0.4, label="suppressed gain", color="#0f766e")
    axes[0].bar(x + 0.2, active["avoided_loss_same_path"], 0.4, label="avoided loss", color="#b45309")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(active["requested_start_month"], rotation=45, ha="right")
    axes[0].set_title("Same-path linear attribution by start")
    axes[0].legend()
    visible = windows[windows["window_rows"].gt(0)].copy()
    x2 = np.arange(len(visible))
    axes[1].bar(x2 - 0.2, visible["account_history_drawdown_improvement_pp"], 0.4, label="account-history HWM", color="#2563eb")
    axes[1].bar(x2 + 0.2, visible["local_window_reset_drawdown_improvement_pp"], 0.4, label="local reset HWM", color="#94a3b8")
    axes[1].set_xticks(x2)
    axes[1].set_xticklabels(visible["requested_start_month"], rotation=45, ha="right")
    axes[1].set_title("2022 drawdown improvement: two definitions")
    axes[1].legend()
    for axis in axes:
        axis.axhline(0.0, color="#111827", linewidth=0.7)
        axis.grid(axis="y", alpha=0.22)
    fig.suptitle("Stage009 gate opportunity-cost attribution")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _lineage(source_manifest_audit: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "stage009_tool": Path(__file__).resolve(),
        "stage009_test": TOOLS_DIR / "test_stage009_gate_opportunity_cost_attribution.py",
        "stage007_tool": Path(s7.__file__).resolve(),
        "stage007_manifest": s7.MANIFEST_PATH,
        "stage007_decision": s7.DECISION_PATH,
        "stage007_pilot_audit": s7.PILOT_AUDIT_PATH,
    }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "inputs": {
            name: {
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
            for name, path in paths.items()
        },
        "source_stage007_manifest_audit": source_manifest_audit,
        "history_database_snapshot_complete": False,
    }


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path != MANIFEST_PATH:
            rows.append(
                {
                    "file": path.name,
                    "bytes": int(path.stat().st_size),
                    "sha256": _sha256(path),
                }
            )
    return pd.DataFrame(rows)


def _write_report(
    coverage: pd.DataFrame,
    windows: pd.DataFrame,
    by_start: pd.DataFrame,
    by_year: pd.DataFrame,
    features: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage009 全起点 gate 机会成本归因

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 策略改动：无；本阶段没有运行新策略回测。
- 映射覆盖：`{decision['coverage_pass']}`，事件 `{decision['event_count']}`。
- 边界：`same_path_linear_*` 仅按相同开平仓路径线性缩放手数，不包含权益、保证金、loss streak、后续仓位和信号反馈，不能作为候选绩效。
- 成本边界：closed-lot `realized_pnl` 是毛损益，未扣佣金和滑点；不得据此声称可执行净收益。
- 样本边界：`237` 是多起点路径事件，去重市场信号只有 `{decision['unique_market_signal_count']}` 个；特征分桶仅作探索标签，禁止据此挑 AI/OI 豁免。
- 回撤主口径：`account_history_hwm`；`local_window_reset_hwm` 只作局部归因。
- 独立 review：`P0=0/P1=1/P2=4`，数字/语义置信度 `99.5%/91%`；只允许一个低水位恢复进度真实引擎候选。

## 映射覆盖

{coverage.to_markdown(index=False)}

## 2022 回撤双口径

{windows.to_markdown(index=False)}

## 按起点

{by_start.to_markdown(index=False)}

## 按事件年份

{by_year.to_markdown(index=False)}

## 事前字段分桶

{features.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest_audit = _verify_manifest(SOURCE_OUT, s7.MANIFEST_PATH)
    if not source_manifest_audit["pass"]:
        raise RuntimeError(
            f"Stage007 source manifest verification failed: {source_manifest_audit}"
        )
    expected = pd.read_csv(s7.PILOT_AUDIT_PATH, encoding="utf-8-sig")
    expected = expected[["requested_start_month", "rows"]].copy()
    events = _attribute_events(expected)
    coverage = _coverage(expected, events)
    coverage_ok = _coverage_pass(coverage)
    windows = _drawdown_windows(expected)
    by_start = _aggregate(events, ["requested_start_month"])
    by_year = _aggregate(events, ["year"])
    features = _feature_buckets(events)

    mapped = events[
        events["c_mapping_status"].astype(str).eq("mapped")
        & events["a_mapping_status"].astype(str).eq("mapped")
    ]
    market_signal_keys = ["signal_date", "vt_symbol", "direction", "signal"]
    unique_market_signal_count = int(
        mapped[market_signal_keys].drop_duplicates().shape[0]
    )
    repeated_market_signal_count = int(
        mapped.groupby(market_signal_keys, dropna=False).size().gt(1).sum()
    )
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "strategy_changed": False,
        "new_backtest_run": False,
        "expected_event_count": int(pd.to_numeric(expected["rows"], errors="coerce").sum()),
        "event_count": int(len(events)),
        "mapped_event_count": int(len(mapped)),
        "coverage_pass": bool(coverage_ok),
        "source_stage007_manifest_pass": bool(source_manifest_audit["pass"]),
        "source_stage007_manifest_rows": int(source_manifest_audit["manifest_rows"]),
        "unique_market_signal_count": unique_market_signal_count,
        "repeated_market_signal_count": repeated_market_signal_count,
        "path_events_are_independent_samples": False,
        "feature_buckets_allowed_for_rule_selection": False,
        "closed_lot_realized_pnl_includes_costs": False,
        "same_path_linear_counterfactual_is_performance_claim": False,
        "primary_drawdown_definition": "account_history_hwm",
        "secondary_attribution_drawdown_definition": "local_window_reset_hwm",
        "final_2022_start_retention_goal_complete": False,
        "final_goal_residual": "Stage007 2022-01 independent-start retention remains 57.7149%; Stage009 is attribution only",
        "decision": (
            "stage009_attribution_complete_one_structural_test_allowed"
            if coverage_ok
            else "stage009_attribution_failed_mapping_incomplete"
        ),
        "overfit_before": "low: all 13 starts, no strategy parameter change",
        "overfit_after": "low for mapping; high if exploratory AI/OI buckets select a rule",
        "continue_value_before": "yes: separate avoided losses from suppressed recovery winners",
        "continue_value_after": "yes: one parameter-free low-water recovery-progress engine candidate",
    }

    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(START_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    LINEAGE_PATH.write_text(
        json.dumps(
            _json_safe(_lineage(source_manifest_audit)),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot(by_start, windows)
    _write_report(coverage, windows, by_start, by_year, features, decision)
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "events": events,
        "coverage": coverage,
        "windows": windows,
        "by_start": by_start,
        "by_year": by_year,
        "features": features,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["coverage"].to_string(index=False))
    print(result["windows"].to_string(index=False))
    print(result["by_start"].to_string(index=False))
    print(result["by_year"].to_string(index=False))
    print(json.dumps(_json_safe(result["decision"]), ensure_ascii=False, indent=2))
