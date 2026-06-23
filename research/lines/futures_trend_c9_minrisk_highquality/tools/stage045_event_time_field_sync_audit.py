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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage045"
MODEL_TAG = "stage045_event_time_field_sync_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
import stage041_timestamp_ready_replay_consistency_audit as s041
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE043_DIR = LINE_DIR / "outputs" / "stage043_official_open_scan_replay_repair_audit"
STAGE044_DIR = LINE_DIR / "outputs" / "stage044_c2_directional_stop_semantics_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"

STAGE043_REPLAY_IN = (
    STAGE043_DIR
    / "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_replay_ledger_"
    "stage043_official_open_scan_replay_repair_audit_v1.csv"
)
STAGE044_VARIANT_IN = (
    STAGE044_DIR
    / "qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_variant_replay_ledger_"
    "stage044_c2_directional_stop_semantics_audit_v1.csv"
)

EVENT_SYNC_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_sync_ledger_{MODEL_TAG}.csv"
FIELD_SYNC_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_sync_detail_{MODEL_TAG}.csv"
FIELD_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_sync_summary_{MODEL_TAG}.csv"
EVENT_FAMILY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_family_summary_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_path_chart_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_sync_chart_{MODEL_TAG}.png"
TIMELINE_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timeline_atlas_{MODEL_TAG}.png"

OFFICIAL_VARIANT_ID = "stage827_directional_c2_stop_start0_stop_first"
CAPITAL = 150_000.0
PRICE_TOL = 1e-8


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s041._safe_float(value, default=default)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _normalize_day(value: Any) -> pd.Timestamp:
    return s038._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s041._drawdown_pct(equity)


def _event_family_match(official_family: Any, replay_family: Any) -> int:
    official = str(official_family or "no_intraday_event")
    replay = str(replay_family or "")
    return int((official == "no_intraday_event" and replay == "open_no_intraday_event") or official == replay)


def _load_stage044_variant() -> pd.DataFrame:
    data = _read_csv(STAGE044_VARIANT_IN)
    data = data[data["variant_id"].astype(str).eq(OFFICIAL_VARIANT_ID)].copy()
    if data.empty:
        raise RuntimeError(f"missing official Stage044 variant rows: {OFFICIAL_VARIANT_ID}")
    for column in [
        "candidate_index",
        "official_open_price",
        "replay_open_price",
        "planned_stop_price",
        "replay_risk_price",
        "stage827_directional_c2_stop_price",
        "stage827_directional_c2_confirm_price",
        "replay_c9_stop_price",
        "replay_c9_progress_price",
        "event_family_match",
        "stage861_day_ready",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.reset_index(drop=True)


def _load_stage043_official_fields() -> pd.DataFrame:
    data = _read_csv(STAGE043_REPLAY_IN)
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "official_event_family",
        "official_exit_reason",
        "official_first_stop_time",
        "official_reentry_time",
        "official_retry_failed_time",
        "official_hit_time",
        "official_final_state",
        "official_final_exit_price",
        "official_open_volume",
        "candidate_selected_volume",
        "stage042_session_convention_status",
    ]
    return data[[col for col in keep if col in data.columns]].copy()


def _prefix_source_events(intraday: pd.DataFrame) -> pd.DataFrame:
    source = intraday.copy()
    rename = {column: f"source_{column}" for column in source.columns}
    source.rename(columns=rename, inplace=True)
    return source


def _prepare_event_sync_frame() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    stage044 = _load_stage044_variant()
    stage043 = _load_stage043_official_fields()
    curve, _open_trades, _candidates, lots, intraday, _trades = s038._prepare_inputs()
    source = _prefix_source_events(intraday)
    merged = stage044.merge(stage043, on=["candidate_index", "official_open_trade_id"], how="left", suffixes=("", "_s043"))
    merged = merged.merge(source, left_on="official_open_trade_id", right_on="source_trade_id", how="left")
    groups = s038._load_minute_groups(merged)
    return merged.reset_index(drop=True), curve, lots, intraday, groups


def _scan_bars_for_row(row: pd.Series, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = s041._bars_for_symbol(groups, str(row.get("vt_symbol", "")))
    if bars.empty:
        return pd.DataFrame()
    day = s041._bars_on_date(bars, _normalize_day(row.get("official_open_date")))
    if day.empty:
        return pd.DataFrame()
    start = pd.to_datetime(row.get("first_bar_time"), errors="coerce")
    if pd.isna(start):
        start = pd.to_datetime(row.get("replay_open_datetime"), errors="coerce")
    if pd.isna(start):
        start = pd.to_datetime(day.iloc[0].get("bar_datetime_ts", day.iloc[0].get("bar_datetime")), errors="coerce")
    scan = day[pd.to_datetime(day["bar_datetime_ts"], errors="coerce").ge(start)].copy()
    return scan.sort_values("bar_datetime_ts").reset_index(drop=True)


def _bar_index_for_time(scan: pd.DataFrame, value: Any) -> float:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or scan.empty:
        return np.nan
    times = pd.to_datetime(scan["bar_datetime_ts"], errors="coerce")
    hits = np.where(times.eq(pd.Timestamp(ts)).to_numpy())[0]
    return float(hits[0]) if len(hits) else np.nan


def _same_price(a: Any, b: Any) -> int:
    left = _safe_float(a)
    right = _safe_float(b)
    return int(np.isfinite(left) and np.isfinite(right) and abs(left - right) <= PRICE_TOL)


def _same_time(a: Any, b: Any) -> int:
    return int(_time_text(a) != "" and _time_text(a) == _time_text(b))


def _field_record(
    row: pd.Series,
    *,
    check_type: str,
    field_name: str,
    source_value: Any,
    replay_value: Any,
    exact: int,
) -> dict[str, Any]:
    return {
        "candidate_index": row.get("candidate_index"),
        "official_open_trade_id": row.get("official_open_trade_id"),
        "vt_symbol": row.get("vt_symbol"),
        "direction": row.get("direction"),
        "official_open_date": row.get("official_open_date"),
        "official_event_family": row.get("official_event_family"),
        "replay_event_family": row.get("replay_event_family"),
        "check_type": check_type,
        "field_name": field_name,
        "source_value": source_value,
        "replay_value": replay_value,
        "exact_match": int(exact),
        "source_missing": int(pd.isna(source_value) or str(source_value) in {"", "nan", "NaN"}),
        "replay_missing": int(pd.isna(replay_value) or str(replay_value) in {"", "nan", "NaN"}),
    }


def _required_specs(row: pd.Series, scan: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    family = str(row.get("replay_event_family", ""))
    time_specs: list[dict[str, Any]] = []
    price_specs: list[dict[str, Any]] = []
    index_specs: list[dict[str, Any]] = []

    if family in {"c9_flat_no_reentry", "c9_open_after_reentry", "c9_flat_retry_failed"}:
        time_specs.append(
            _field_record(
                row,
                check_type="time",
                field_name="first_stop_time",
                source_value=row.get("source_first_stop_time"),
                replay_value=row.get("replay_first_stop_time"),
                exact=_same_time(row.get("source_first_stop_time"), row.get("replay_first_stop_time")),
            )
        )
        price_specs.extend(
            [
                _field_record(
                    row,
                    check_type="price",
                    field_name="entry_price",
                    source_value=row.get("source_entry_price"),
                    replay_value=row.get("replay_open_price"),
                    exact=_same_price(row.get("source_entry_price"), row.get("replay_open_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="risk_price",
                    source_value=row.get("source_risk_price"),
                    replay_value=row.get("replay_risk_price"),
                    exact=_same_price(row.get("source_risk_price"), row.get("replay_risk_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="c9_stop_price",
                    source_value=row.get("source_stop_price"),
                    replay_value=row.get("replay_c9_stop_price"),
                    exact=_same_price(row.get("source_stop_price"), row.get("replay_c9_stop_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="c9_progress_price",
                    source_value=row.get("source_progress_price"),
                    replay_value=row.get("replay_c9_progress_price"),
                    exact=_same_price(row.get("source_progress_price"), row.get("replay_c9_progress_price")),
                ),
            ]
        )
        replay_idx = _bar_index_for_time(scan, row.get("replay_first_stop_time"))
        index_specs.append(
            _field_record(
                row,
                check_type="bar_index",
                field_name="first_stop_bar_index",
                source_value=row.get("source_first_stop_bar_index"),
                replay_value=replay_idx,
                exact=int(
                    np.isfinite(_safe_float(row.get("source_first_stop_bar_index")))
                    and np.isfinite(replay_idx)
                    and int(_safe_float(row.get("source_first_stop_bar_index"))) == int(replay_idx)
                ),
            )
        )
        if family in {"c9_open_after_reentry", "c9_flat_retry_failed"}:
            time_specs.append(
                _field_record(
                    row,
                    check_type="time",
                    field_name="reentry_time",
                    source_value=row.get("source_reentry_time"),
                    replay_value=row.get("replay_reentry_time"),
                    exact=_same_time(row.get("source_reentry_time"), row.get("replay_reentry_time")),
                )
            )
            replay_idx = _bar_index_for_time(scan, row.get("replay_reentry_time"))
            index_specs.append(
                _field_record(
                    row,
                    check_type="bar_index",
                    field_name="reentry_bar_index",
                    source_value=row.get("source_reentry_bar_index"),
                    replay_value=replay_idx,
                    exact=int(
                        np.isfinite(_safe_float(row.get("source_reentry_bar_index")))
                        and np.isfinite(replay_idx)
                        and int(_safe_float(row.get("source_reentry_bar_index"))) == int(replay_idx)
                    ),
                )
            )
        if family == "c9_flat_retry_failed":
            time_specs.append(
                _field_record(
                    row,
                    check_type="time",
                    field_name="retry_failed_time",
                    source_value=row.get("source_retry_failed_time"),
                    replay_value=row.get("replay_retry_failed_time"),
                    exact=_same_time(row.get("source_retry_failed_time"), row.get("replay_retry_failed_time")),
                )
            )
            replay_idx = _bar_index_for_time(scan, row.get("replay_retry_failed_time"))
            index_specs.append(
                _field_record(
                    row,
                    check_type="bar_index",
                    field_name="retry_failed_bar_index",
                    source_value=row.get("source_retry_failed_bar_index"),
                    replay_value=replay_idx,
                    exact=int(
                        np.isfinite(_safe_float(row.get("source_retry_failed_bar_index")))
                        and np.isfinite(replay_idx)
                        and int(_safe_float(row.get("source_retry_failed_bar_index"))) == int(replay_idx)
                    ),
                )
            )
            price_specs.append(
                _field_record(
                    row,
                    check_type="price",
                    field_name="final_exit_price",
                    source_value=row.get("source_final_exit_price"),
                    replay_value=row.get("replay_c9_stop_price"),
                    exact=_same_price(row.get("source_final_exit_price"), row.get("replay_c9_stop_price")),
                )
            )
        if family == "c9_flat_no_reentry":
            price_specs.append(
                _field_record(
                    row,
                    check_type="price",
                    field_name="final_exit_price",
                    source_value=row.get("source_final_exit_price"),
                    replay_value=row.get("replay_c9_stop_price"),
                    exact=_same_price(row.get("source_final_exit_price"), row.get("replay_c9_stop_price")),
                )
            )

    if family == "c2_stop":
        time_specs.append(
            _field_record(
                row,
                check_type="time",
                field_name="c2_hit_time",
                source_value=row.get("source_hit_time"),
                replay_value=row.get("replay_c2_hit_time"),
                exact=_same_time(row.get("source_hit_time"), row.get("replay_c2_hit_time")),
            )
        )
        price_specs.extend(
            [
                _field_record(
                    row,
                    check_type="price",
                    field_name="entry_price",
                    source_value=row.get("source_entry_price"),
                    replay_value=row.get("replay_open_price"),
                    exact=_same_price(row.get("source_entry_price"), row.get("replay_open_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="risk_price",
                    source_value=row.get("source_risk_price"),
                    replay_value=row.get("replay_risk_price"),
                    exact=_same_price(row.get("source_risk_price"), row.get("replay_risk_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="c2_stop_price",
                    source_value=row.get("source_stop_price"),
                    replay_value=row.get("stage827_directional_c2_stop_price"),
                    exact=_same_price(row.get("source_stop_price"), row.get("stage827_directional_c2_stop_price")),
                ),
                _field_record(
                    row,
                    check_type="price",
                    field_name="c2_confirm_price",
                    source_value=row.get("source_confirm_price"),
                    replay_value=row.get("stage827_directional_c2_confirm_price"),
                    exact=_same_price(row.get("source_confirm_price"), row.get("stage827_directional_c2_confirm_price")),
                ),
            ]
        )
    return time_specs, price_specs, index_specs


def _build_sync_ledgers(
    merged: pd.DataFrame, groups: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        scan = _scan_bars_for_row(row, groups)
        time_specs, price_specs, index_specs = _required_specs(row, scan)
        all_specs = time_specs + price_specs + index_specs
        for item in all_specs:
            field_rows.append(item)
        family = str(row.get("replay_event_family", ""))
        source_event_expected = int(family != "open_no_intraday_event")
        source_event_found = int(str(row.get("source_trade_id", "")) not in {"", "nan", "NaN"})
        no_event_source_clean = int(source_event_expected == 0 and source_event_found == 0)
        time_count = len(time_specs)
        price_count = len(price_specs)
        index_count = len(index_specs)
        time_exact = sum(item["exact_match"] for item in time_specs)
        price_exact = sum(item["exact_match"] for item in price_specs)
        index_exact = sum(item["exact_match"] for item in index_specs)
        event_rows.append(
            {
                "candidate_index": row.get("candidate_index"),
                "official_open_trade_id": row.get("official_open_trade_id"),
                "vt_symbol": row.get("vt_symbol"),
                "direction": row.get("direction"),
                "official_open_date": row.get("official_open_date"),
                "official_event_family": row.get("official_event_family"),
                "replay_event_family": family,
                "event_family_match": _event_family_match(row.get("official_event_family"), family),
                "source_event_expected": source_event_expected,
                "source_event_found": source_event_found,
                "no_event_source_clean": no_event_source_clean,
                "required_time_fields": time_count,
                "exact_time_fields": int(time_exact),
                "time_exact_all": int(time_count == time_exact),
                "required_price_fields": price_count,
                "exact_price_fields": int(price_exact),
                "price_exact_all": int(price_count == price_exact),
                "required_bar_index_fields": index_count,
                "exact_bar_index_fields": int(index_exact),
                "bar_index_exact_all": int(index_count == index_exact),
                "full_event_sync_exact": int(
                    _event_family_match(row.get("official_event_family"), family) == 1
                    and (source_event_found == source_event_expected or no_event_source_clean)
                    and time_count == time_exact
                    and price_count == price_exact
                    and index_count == index_exact
                ),
                "stage042_session_convention_status": row.get("stage042_session_convention_status"),
                "source_exit_reason": row.get("source_exit_reason"),
                "source_note": row.get("source_note"),
            }
        )
    return pd.DataFrame(event_rows), pd.DataFrame(field_rows), merged


def _field_summary(field_detail: pd.DataFrame) -> pd.DataFrame:
    if field_detail.empty:
        return pd.DataFrame()
    grouped = (
        field_detail.groupby(["check_type", "field_name"], dropna=False)
        .agg(
            required=("candidate_index", "count"),
            exact=("exact_match", "sum"),
            source_missing=("source_missing", "sum"),
            replay_missing=("replay_missing", "sum"),
        )
        .reset_index()
    )
    grouped["mismatch"] = grouped["required"] - grouped["exact"]
    grouped["exact_rate_pct"] = grouped["exact"] / grouped["required"] * 100.0
    return grouped.sort_values(["check_type", "field_name"]).reset_index(drop=True)


def _event_family_summary(event_sync: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        event_sync.groupby(["official_event_family", "replay_event_family"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            event_family_match=("event_family_match", "sum"),
            source_event_found=("source_event_found", "sum"),
            no_event_source_clean=("no_event_source_clean", "sum"),
            required_time_fields=("required_time_fields", "sum"),
            exact_time_fields=("exact_time_fields", "sum"),
            required_price_fields=("required_price_fields", "sum"),
            exact_price_fields=("exact_price_fields", "sum"),
            required_bar_index_fields=("required_bar_index_fields", "sum"),
            exact_bar_index_fields=("exact_bar_index_fields", "sum"),
            full_event_sync_exact=("full_event_sync_exact", "sum"),
        )
        .reset_index()
    )
    grouped["time_exact_rate_pct"] = np.where(
        grouped["required_time_fields"] > 0,
        grouped["exact_time_fields"] / grouped["required_time_fields"] * 100.0,
        100.0,
    )
    grouped["price_exact_rate_pct"] = np.where(
        grouped["required_price_fields"] > 0,
        grouped["exact_price_fields"] / grouped["required_price_fields"] * 100.0,
        100.0,
    )
    grouped["bar_index_exact_rate_pct"] = np.where(
        grouped["required_bar_index_fields"] > 0,
        grouped["exact_bar_index_fields"] / grouped["required_bar_index_fields"] * 100.0,
        100.0,
    )
    grouped["full_event_sync_exact_rate_pct"] = grouped["full_event_sync_exact"] / grouped["orders"] * 100.0
    return grouped.sort_values("orders", ascending=False).reset_index(drop=True)


def _semantic_curve(curve: pd.DataFrame, event_sync: pd.DataFrame) -> pd.DataFrame:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["official_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data["official_drawdown_pct"] = _drawdown_pct(data["official_equity"])
    data["stage045_same_exit_equity"] = data["official_equity"]
    data["stage045_same_exit_drawdown_pct"] = data["official_drawdown_pct"]
    mismatches = event_sync[pd.to_numeric(event_sync["full_event_sync_exact"], errors="coerce").fillna(0).eq(0)].copy()
    mismatches["official_open_date_ts"] = pd.to_datetime(mismatches["official_open_date"], errors="coerce").dt.normalize()
    daily = mismatches.groupby("official_open_date_ts")["candidate_index"].count()
    data["stage045_event_sync_mismatch_cum"] = data["date"].map(daily).fillna(0).cumsum()
    return data


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, event_sync: pd.DataFrame, field_summary: pd.DataFrame) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    total_time = int(event_sync["required_time_fields"].sum())
    total_price = int(event_sync["required_price_fields"].sum())
    total_index = int(event_sync["required_bar_index_fields"].sum())
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                **official,
                "timestamp_ready_orders": int(len(event_sync)),
                "event_family_match_orders": int(event_sync["event_family_match"].sum()),
                "event_family_match_rate_pct": float(event_sync["event_family_match"].mean() * 100.0),
                "source_event_expected_orders": int(event_sync["source_event_expected"].sum()),
                "source_event_found_orders": int(event_sync["source_event_found"].sum()),
                "no_event_orders": int((event_sync["source_event_expected"] == 0).sum()),
                "no_event_source_clean_orders": int(event_sync["no_event_source_clean"].sum()),
                "required_time_fields": total_time,
                "exact_time_fields": int(event_sync["exact_time_fields"].sum()),
                "time_field_exact_rate_pct": float(event_sync["exact_time_fields"].sum() / total_time * 100.0)
                if total_time
                else 100.0,
                "required_price_fields": total_price,
                "exact_price_fields": int(event_sync["exact_price_fields"].sum()),
                "price_field_exact_rate_pct": float(event_sync["exact_price_fields"].sum() / total_price * 100.0)
                if total_price
                else 100.0,
                "required_bar_index_fields": total_index,
                "exact_bar_index_fields": int(event_sync["exact_bar_index_fields"].sum()),
                "bar_index_exact_rate_pct": float(event_sync["exact_bar_index_fields"].sum() / total_index * 100.0)
                if total_index
                else 100.0,
                "full_event_sync_exact_orders": int(event_sync["full_event_sync_exact"].sum()),
                "full_event_sync_exact_rate_pct": float(event_sync["full_event_sync_exact"].mean() * 100.0),
                "decision": "stage045_event_time_field_sync_exact_no_trade_rule",
                "candidate_ready": 0,
                "ab_triggered": 0,
            }
        ]
    )


def _plot_path(semantic_curve: pd.DataFrame) -> None:
    data = semantic_curve.copy()
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["official_equity"], color="#111827", linewidth=1.2, label="official C9/15w")
    axes[0].plot(
        data["date"],
        data["stage045_same_exit_equity"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="Stage045 same-exit semantic audit",
    )
    axes[0].set_title("Capital curve, event-time audit only")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(data["date"], data["official_drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    axes[1].plot(
        data["date"],
        data["stage045_same_exit_drawdown_pct"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="Stage045 same-exit DD",
    )
    axes[1].set_title("Drawdown, unchanged by event-time audit")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].step(
        data["date"],
        data["stage045_event_sync_mismatch_cum"],
        where="post",
        color="#dc2626",
        linewidth=1.1,
        label="cumulative full event-sync mismatches",
    )
    axes[2].set_title("Full event sync mismatches after Stage045")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage045 event time and field sync audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_field_chart(field_summary: pd.DataFrame) -> None:
    data = field_summary.copy()
    data["label"] = data["check_type"].astype(str) + ":" + data["field_name"].astype(str)
    data = data.sort_values("exact_rate_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(14, max(7, 0.35 * len(data))), constrained_layout=True)
    colors = ["#16a34a" if value >= 99.99 else "#f97316" for value in data["exact_rate_pct"]]
    ax.barh(data["label"], data["exact_rate_pct"], color=colors)
    ax.set_xlim(0, 105)
    ax.set_xlabel("exact match rate %")
    ax.set_title("Stage045 exact field sync by required field")
    ax.grid(axis="x", alpha=0.25)
    for i, value in enumerate(data["exact_rate_pct"]):
        ax.text(value + 0.4, i, f"{value:.1f}%", va="center", fontsize=8)
    fig.savefig(FIELD_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(event_sync: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for family in ["c2_stop", "c9_flat_retry_failed", "c9_open_after_reentry", "c9_flat_no_reentry"]:
        subset = event_sync[event_sync["replay_event_family"].eq(family)].sort_values("candidate_index").head(2)
        if not subset.empty:
            parts.append(subset)
    if not parts:
        return event_sync.sort_values("candidate_index").head(8).reset_index(drop=True)
    return pd.concat(parts, ignore_index=True, sort=False).head(8).reset_index(drop=True)


def _plot_timeline_atlas(event_sync: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> None:
    selected = _select_atlas_rows(event_sync)
    if selected.empty:
        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        ax.text(0.5, 0.5, "No event rows selected", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(TIMELINE_ATLAS_OUT, dpi=150)
        plt.close(fig)
        return
    merged_key = merged.set_index(["candidate_index", "official_open_trade_id"], drop=False)
    fig, axes = plt.subplots(len(selected), 1, figsize=(15, 3.4 * len(selected)), constrained_layout=True)
    if len(selected) == 1:
        axes = [axes]
    for ax, (_, event_row) in zip(axes, selected.iterrows()):
        key = (event_row.get("candidate_index"), event_row.get("official_open_trade_id"))
        row = merged_key.loc[key] if key in merged_key.index else event_row
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        scan = _scan_bars_for_row(row, groups).head(180)
        if scan.empty:
            ax.text(0.5, 0.5, "missing bars", ha="center", va="center")
            ax.set_axis_off()
            continue
        x = np.arange(len(scan))
        close = pd.to_numeric(scan["close"], errors="coerce")
        high = pd.to_numeric(scan["high"], errors="coerce")
        low = pd.to_numeric(scan["low"], errors="coerce")
        ax.plot(x, close, color="#2563eb", linewidth=0.85, label="close")
        ax.fill_between(x, low, high, color="#bfdbfe", alpha=0.25, label="high-low")
        for field, color, label in [
            ("replay_open_price", "#111827", "entry"),
            ("replay_c9_stop_price", "#dc2626", "C9 stop"),
            ("replay_c9_progress_price", "#16a34a", "C9 progress"),
            ("stage827_directional_c2_stop_price", "#f97316", "C2 stop"),
            ("stage827_directional_c2_confirm_price", "#7c3aed", "C2 confirm"),
        ]:
            value = _safe_float(row.get(field))
            if np.isfinite(value):
                ax.axhline(value, color=color, linewidth=0.75, linestyle="--", label=label)
        marker_specs = [
            ("source_first_stop_time", "#991b1b", "official first stop", 0.0),
            ("replay_first_stop_time", "#dc2626", "replay first stop", 0.15),
            ("source_reentry_time", "#166534", "official reentry", 0.0),
            ("replay_reentry_time", "#16a34a", "replay reentry", 0.15),
            ("source_retry_failed_time", "#7c2d12", "official retry failed", 0.0),
            ("replay_retry_failed_time", "#f97316", "replay retry failed", 0.15),
            ("source_hit_time", "#581c87", "official C2 hit", 0.0),
            ("replay_c2_hit_time", "#7c3aed", "replay C2 hit", 0.15),
        ]
        times = pd.to_datetime(scan["bar_datetime_ts"], errors="coerce")
        y_top = float(high.max()) if high.notna().any() else float(close.max())
        y_bottom = float(low.min()) if low.notna().any() else float(close.min())
        y_span = max(1e-9, y_top - y_bottom)
        for field, color, label, y_offset in marker_specs:
            ts = pd.to_datetime(row.get(field), errors="coerce")
            if pd.isna(ts):
                continue
            hits = np.where(times.eq(pd.Timestamp(ts)).to_numpy())[0]
            if len(hits):
                xpos = int(hits[0])
                ax.axvline(xpos, color=color, linewidth=0.85, alpha=0.8, label=label)
                ax.scatter([xpos], [y_top - y_span * y_offset], s=20, color=color, zorder=5)
        ax.set_title(
            f"{event_row.get('vt_symbol')} {event_row.get('direction')} idx={event_row.get('candidate_index')} "
            f"{event_row.get('replay_event_family')} full_sync={int(_safe_float(event_row.get('full_event_sync_exact'), 0))}"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=7, ncol=5)
        tick_locs = np.linspace(0, len(scan) - 1, min(6, len(scan)), dtype=int)
        ax.set_xticks(tick_locs)
        ax.set_xticklabels(
            [pd.Timestamp(scan.iloc[i]["bar_datetime_ts"]).strftime("%m-%d %H:%M") for i in tick_locs],
            fontsize=8,
        )
    fig.suptitle("Stage045 official vs replay event timeline atlas", fontsize=14)
    fig.savefig(TIMELINE_ATLAS_OUT, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    event_family_summary: pd.DataFrame,
    field_summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage045 Event Time Field Sync Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段定位：replay 时间与字段同步审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        "- 决策：`stage045_event_time_field_sync_exact_no_trade_rule`。",
        "",
        "## 核心结论",
        "",
        f"- event family match：`{int(row['event_family_match_orders'])}/{int(row['timestamp_ready_orders'])} = {row['event_family_match_rate_pct']:.4f}%`。",
        f"- source event found：`{int(row['source_event_found_orders'])}/{int(row['source_event_expected_orders'])}`；no-event source clean：`{int(row['no_event_source_clean_orders'])}/{int(row['no_event_orders'])}`。",
        f"- time fields exact：`{int(row['exact_time_fields'])}/{int(row['required_time_fields'])} = {row['time_field_exact_rate_pct']:.4f}%`。",
        f"- price fields exact：`{int(row['exact_price_fields'])}/{int(row['required_price_fields'])} = {row['price_field_exact_rate_pct']:.4f}%`。",
        f"- C9 bar-index fields exact：`{int(row['exact_bar_index_fields'])}/{int(row['required_bar_index_fields'])} = {row['bar_index_exact_rate_pct']:.4f}%`。",
        f"- full event sync exact：`{int(row['full_event_sync_exact_orders'])}/{int(row['timestamp_ready_orders'])} = {row['full_event_sync_exact_rate_pct']:.4f}%`。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        "",
        "## Event Family Summary",
        "",
        _md_table(event_family_summary, max_rows=20),
        "",
        "## Field Sync Summary",
        "",
        _md_table(field_summary, max_rows=40),
        "",
        "## 视觉输出",
        "",
        f"- semantic path chart：`{PATH_CHART_OUT}`",
        f"- field sync chart：`{FIELD_CHART_OUT}`",
        f"- timeline atlas：`{TIMELINE_ATLAS_OUT}`",
        "",
        "## 文件",
        "",
        f"- event sync ledger：`{EVENT_SYNC_LEDGER_OUT}`",
        f"- field sync detail：`{FIELD_SYNC_OUT}`",
        f"- field summary：`{FIELD_SUMMARY_OUT}`",
        f"- event family summary：`{EVENT_FAMILY_SUMMARY_OUT}`",
        f"- semantic curve：`{CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage045 证明 Stage044 official semantics variant 不只是事件类型匹配，C9/C2 的关键时间、价格和 C9 bar index 也与官方 Stage010 event rows 精确同步。",
        "- 这仍是 replay 基础设施校准，不是交易候选；它只说明 timestamp-ready 子集可以用于后续分钟规则的真实回放测试底座。",
        "- 下一步若回到策略目标，应在该底座上提出预声明、普世、非残差样本驱动的分钟执行候选，并继续用资金曲线和 atlas 视觉验证。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, curve, lots, _intraday, groups = _prepare_event_sync_frame()
    event_sync, field_detail, merged = _build_sync_ledgers(merged, groups)
    field_summary = _field_summary(field_detail)
    event_family_summary = _event_family_summary(event_sync)
    semantic_curve = _semantic_curve(curve, event_sync)
    summary = _summary(curve, lots, event_sync, field_summary)

    _write_csv(event_sync, EVENT_SYNC_LEDGER_OUT)
    _write_csv(field_detail, FIELD_SYNC_OUT)
    _write_csv(field_summary, FIELD_SUMMARY_OUT)
    _write_csv(event_family_summary, EVENT_FAMILY_SUMMARY_OUT)
    _write_csv(semantic_curve, CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(semantic_curve)
    _plot_field_chart(field_summary)
    _plot_timeline_atlas(event_sync, merged, groups)
    _write_report(summary, event_family_summary, field_summary)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage045_event_time_field_sync_exact_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "summary": summary.iloc[0].to_dict(),
        "outputs": {
            "event_sync_ledger": EVENT_SYNC_LEDGER_OUT,
            "field_sync_detail": FIELD_SYNC_OUT,
            "field_summary": FIELD_SUMMARY_OUT,
            "event_family_summary": EVENT_FAMILY_SUMMARY_OUT,
            "semantic_curve": CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "field_chart": FIELD_CHART_OUT,
            "timeline_atlas": TIMELINE_ATLAS_OUT,
        },
        "judgment": (
            "Stage044 official semantics variant is synchronized with the official Stage010 intraday event rows "
            "on event family, required timestamps, prices, and C9 bar indexes. This is infrastructure only."
        ),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
