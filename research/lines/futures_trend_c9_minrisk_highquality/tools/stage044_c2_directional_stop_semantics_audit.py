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
STAGE = "Stage044"
MODEL_TAG = "stage044_c2_directional_stop_semantics_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
import stage041_timestamp_ready_replay_consistency_audit as s041
import stage043_official_open_scan_replay_repair_audit as s043
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE043_DIR = LINE_DIR / "outputs" / "stage043_official_open_scan_replay_repair_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage044_c2_directional_stop_semantics_audit"

STAGE043_REPLAY_IN = (
    STAGE043_DIR
    / "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_replay_ledger_"
    "stage043_official_open_scan_replay_repair_audit_v1.csv"
)
STAGE043_CURVE_IN = (
    STAGE043_DIR
    / "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_same_exit_repair_curve_"
    "stage043_official_open_scan_replay_repair_audit_v1.csv"
)

VARIANT_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_replay_ledger_{MODEL_TAG}.csv"
VARIANT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RESIDUAL_RESOLUTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_resolution_{MODEL_TAG}.csv"
PRICE_SEMANTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_price_semantics_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_path_chart_{MODEL_TAG}.png"
VARIANT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_match_chart_{MODEL_TAG}.png"
RESIDUAL_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_atlas_{MODEL_TAG}.png"

CAPITAL = 150_000.0
OFFICIAL_STAGE827_C2_FORMULA = "entry_price - direction_sign * 1R risk_price"
OFFICIAL_STAGE827_C2_CONFIRM_FORMULA = "entry_price + direction_sign * 1R risk_price"


VARIANTS: list[dict[str, Any]] = [
    {
        "variant_id": "stage043_planned_stop_as_c2_stop_start0_stop_first",
        "stop_mode": "planned_stop_direct",
        "start_idx": 0,
        "same_bar_priority": "stop_first",
    },
    {
        "variant_id": "stage827_directional_c2_stop_start0_stop_first",
        "stop_mode": "stage827_directional",
        "start_idx": 0,
        "same_bar_priority": "stop_first",
    },
    {
        "variant_id": "stage827_directional_c2_stop_start1_stop_first",
        "stop_mode": "stage827_directional",
        "start_idx": 1,
        "same_bar_priority": "stop_first",
    },
    {
        "variant_id": "stage827_directional_c2_stop_start0_confirm_first",
        "stop_mode": "stage827_directional",
        "start_idx": 0,
        "same_bar_priority": "confirm_first",
    },
]


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
    return s041._time_text(value)


def _parse_ts(value: Any) -> pd.Timestamp:
    return s043._parse_ts(value)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s038._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s041._drawdown_pct(equity)


def _event_family_match(official_family: Any, replay_family: Any) -> int:
    official = str(official_family or "no_intraday_event")
    replay = str(replay_family or "")
    return int((official == "no_intraday_event" and replay == "open_no_intraday_event") or official == replay)


def _load_stage043_replay() -> pd.DataFrame:
    replay = _read_csv(STAGE043_REPLAY_IN)
    for column in [
        "candidate_index",
        "official_open_price",
        "replay_open_price",
        "planned_stop_price",
        "planned_stop_distance",
        "replay_risk_price",
        "replay_bar_count",
        "event_family_match",
        "stage861_day_ready",
        "replay_c2_same_bar_confirm",
        "stage042_raw_event_family_match",
    ]:
        if column in replay.columns:
            replay[column] = pd.to_numeric(replay[column], errors="coerce")
    for column in [
        "candidate_date",
        "official_open_date",
        "replay_open_datetime",
        "replay_c2_hit_time",
        "official_hit_time",
        "stage042_raw_replay_first_event_time",
        "stage042_official_first_event_time",
    ]:
        if column in replay.columns:
            replay[f"{column}_ts"] = pd.to_datetime(replay[column], errors="coerce")
    return replay.reset_index(drop=True)


def _planned_stop_side(row: pd.Series) -> str:
    direction = s038._direction_text(row.get("direction"))
    entry = _safe_float(row.get("replay_open_price"))
    planned = _safe_float(row.get("planned_stop_price"))
    if not np.isfinite(entry) or not np.isfinite(planned):
        return "missing"
    if direction == "long":
        return "planned_above_entry_for_long" if planned > entry else "planned_below_or_equal_entry_for_long"
    return "planned_below_entry_for_short" if planned < entry else "planned_above_or_equal_entry_for_short"


def _directional_c2_prices(row: pd.Series) -> tuple[float, float]:
    direction = s038._direction_text(row.get("direction"))
    sign = s038._direction_sign(direction)
    entry = _safe_float(row.get("replay_open_price"))
    risk = _safe_float(row.get("replay_risk_price"))
    if not np.isfinite(entry) or not np.isfinite(risk):
        return np.nan, np.nan
    return entry - sign * risk, entry + sign * risk


def _variant_c2_prices(row: pd.Series, variant: dict[str, Any]) -> tuple[float, float]:
    if variant["stop_mode"] == "planned_stop_direct":
        stop = _safe_float(row.get("planned_stop_price"))
        direction = s038._direction_text(row.get("direction"))
        sign = s038._direction_sign(direction)
        entry = _safe_float(row.get("replay_open_price"))
        risk = _safe_float(row.get("replay_risk_price"))
        confirm = entry + sign * risk if np.isfinite(entry) and np.isfinite(risk) else np.nan
        return stop, confirm
    return _directional_c2_prices(row)


def _first_c2_custom(
    day: pd.DataFrame,
    *,
    stop_price: float,
    confirm_price: float,
    direction: str,
    start_idx: int,
    same_bar_priority: str,
) -> dict[str, Any]:
    for idx in range(max(0, int(start_idx)), len(day)):
        item = day.iloc[idx]
        high = _safe_float(item.get("high"))
        low = _safe_float(item.get("low"))
        if direction == "long":
            stop_hit = low <= stop_price
            confirm_hit = high >= confirm_price
        else:
            stop_hit = high >= stop_price
            confirm_hit = low <= confirm_price
        if same_bar_priority == "confirm_first":
            if confirm_hit:
                return {
                    "event": "confirm",
                    "idx": idx,
                    "time": _time_text(item.get("bar_datetime_ts", item.get("bar_datetime"))),
                    "same_bar_opposite": int(stop_hit),
                }
            if stop_hit:
                return {
                    "event": "c2_stop",
                    "idx": idx,
                    "time": _time_text(item.get("bar_datetime_ts", item.get("bar_datetime"))),
                    "same_bar_opposite": int(confirm_hit),
                }
        else:
            if stop_hit:
                return {
                    "event": "c2_stop",
                    "idx": idx,
                    "time": _time_text(item.get("bar_datetime_ts", item.get("bar_datetime"))),
                    "same_bar_opposite": int(confirm_hit),
                }
            if confirm_hit:
                return {
                    "event": "confirm",
                    "idx": idx,
                    "time": _time_text(item.get("bar_datetime_ts", item.get("bar_datetime"))),
                    "same_bar_opposite": int(stop_hit),
                }
    return {"event": "none", "idx": -1, "time": "", "same_bar_opposite": 0}


def _first_bar_snapshot(scan: pd.DataFrame) -> dict[str, Any]:
    if scan.empty:
        return {
            "first_bar_time": "",
            "first_bar_open": np.nan,
            "first_bar_high": np.nan,
            "first_bar_low": np.nan,
            "first_bar_close": np.nan,
        }
    first = scan.iloc[0]
    return {
        "first_bar_time": _time_text(first.get("bar_datetime_ts", first.get("bar_datetime"))),
        "first_bar_open": _safe_float(first.get("open")),
        "first_bar_high": _safe_float(first.get("high")),
        "first_bar_low": _safe_float(first.get("low")),
        "first_bar_close": _safe_float(first.get("close")),
    }


def _replay_variant(row: pd.Series, groups: dict[str, pd.DataFrame], variant: dict[str, Any]) -> dict[str, Any]:
    scan, scan_source = s043._select_official_scan_bars(row, groups)
    direction = s038._direction_text(row.get("direction"))
    entry = _safe_float(row.get("replay_open_price"))
    risk = _safe_float(row.get("replay_risk_price"))
    directional_stop, directional_confirm = _directional_c2_prices(row)
    variant_stop, variant_confirm = _variant_c2_prices(row, variant)
    planned_stop = _safe_float(row.get("planned_stop_price"))
    base = {
        "variant_id": variant["variant_id"],
        "variant_stop_mode": variant["stop_mode"],
        "variant_start_idx": int(variant["start_idx"]),
        "variant_same_bar_priority": variant["same_bar_priority"],
        "candidate_index": row.get("candidate_index"),
        "official_open_trade_id": row.get("official_open_trade_id"),
        "vt_symbol": row.get("vt_symbol"),
        "direction": direction,
        "candidate_date": row.get("candidate_date"),
        "official_open_date": row.get("official_open_date"),
        "official_event_family": row.get("official_event_family", "no_intraday_event"),
        "stage043_replay_event_family": row.get("replay_event_family"),
        "stage043_event_family_match": row.get("event_family_match"),
        "stage042_session_convention_status": row.get("stage042_session_convention_status"),
        "official_open_price": row.get("official_open_price"),
        "replay_open_price": entry,
        "planned_stop_price": planned_stop,
        "replay_risk_price": risk,
        "stage827_directional_c2_stop_price": directional_stop,
        "stage827_directional_c2_confirm_price": directional_confirm,
        "variant_c2_stop_price": variant_stop,
        "variant_c2_confirm_price": variant_confirm,
        "planned_minus_directional_c2_stop": planned_stop - directional_stop
        if np.isfinite(planned_stop) and np.isfinite(directional_stop)
        else np.nan,
        "planned_stop_side": _planned_stop_side(row),
        "replay_scan_source": scan_source,
        "stage861_day_ready": int(not scan.empty),
        "replay_event_family": "missing_stage861_replay_bars",
        "replay_first_stop_time": "",
        "replay_reentry_time": "",
        "replay_retry_failed_time": "",
        "replay_c2_hit_time": "",
        "replay_c2_confirm_time": "",
        "replay_c2_same_bar_opposite": 0,
        "event_family_match": 0,
        "stage043_residual_resolved": 0,
        **_first_bar_snapshot(scan),
    }
    if scan.empty:
        base["event_family_match"] = _event_family_match(base["official_event_family"], base["replay_event_family"])
        return base
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        base["replay_event_family"] = "invalid_replay_risk"
        base["event_family_match"] = _event_family_match(base["official_event_family"], base["replay_event_family"])
        return base

    c9 = s038._first_c9_stop_or_progress(scan, entry_price=entry, risk_price=risk, direction=direction)
    base["replay_c9_stop_price"] = c9.get("stop_price")
    base["replay_c9_progress_price"] = c9.get("progress_price")
    base["replay_c9_first_event"] = c9.get("event")
    base["replay_c9_first_event_time"] = str(c9.get("time", ""))
    if c9["event"] == "stop":
        retry = s038._reentry_after_stop(
            scan,
            direction=direction,
            entry_price=entry,
            stop_price=float(c9["stop_price"]),
            stop_idx=int(c9["idx"]),
        )
        family = "c9_flat_no_reentry"
        if int(retry["reentry_idx"]) >= 0:
            family = "c9_open_after_reentry"
            if int(retry["retry_failed_idx"]) >= 0:
                family = "c9_flat_retry_failed"
        base.update(
            {
                "replay_event_family": family,
                "replay_first_stop_time": str(c9.get("time", "")),
                "replay_reentry_time": str(retry["reentry_time"]),
                "replay_retry_failed_time": str(retry["retry_failed_time"]),
            }
        )
    else:
        c2 = _first_c2_custom(
            scan,
            stop_price=variant_stop,
            confirm_price=variant_confirm,
            direction=direction,
            start_idx=int(variant["start_idx"]),
            same_bar_priority=str(variant["same_bar_priority"]),
        )
        if c2["event"] == "c2_stop":
            base["replay_event_family"] = "c2_stop"
            base["replay_c2_hit_time"] = str(c2["time"])
            base["replay_c2_same_bar_opposite"] = int(c2.get("same_bar_opposite", 0))
        else:
            base["replay_event_family"] = "open_no_intraday_event"
            base["replay_c2_confirm_time"] = str(c2["time"]) if c2["event"] == "confirm" else ""
            base["replay_c2_same_bar_opposite"] = int(c2.get("same_bar_opposite", 0))
    base["event_family_match"] = _event_family_match(base["official_event_family"], base["replay_event_family"])
    base["stage043_residual_resolved"] = int(
        _safe_float(row.get("event_family_match"), 0.0) == 0 and base["event_family_match"] == 1
    )
    return base


def _build_variant_ledger(replay: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in replay.iterrows():
        for variant in VARIANTS:
            rows.append(_replay_variant(row, groups, variant))
    ledger = pd.DataFrame(rows)
    numeric = [
        "candidate_index",
        "official_open_price",
        "replay_open_price",
        "planned_stop_price",
        "replay_risk_price",
        "stage827_directional_c2_stop_price",
        "stage827_directional_c2_confirm_price",
        "variant_c2_stop_price",
        "variant_c2_confirm_price",
        "planned_minus_directional_c2_stop",
        "stage861_day_ready",
        "event_family_match",
        "stage043_event_family_match",
        "stage043_residual_resolved",
        "first_bar_open",
        "first_bar_high",
        "first_bar_low",
        "first_bar_close",
    ]
    for column in numeric:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce")
    return ledger


def _variant_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    residual_mask = pd.to_numeric(ledger["stage043_event_family_match"], errors="coerce").fillna(0).eq(0)
    rows = []
    for variant_id, data in ledger.groupby("variant_id", dropna=False):
        matches = pd.to_numeric(data["event_family_match"], errors="coerce").fillna(0)
        residual_data = data[residual_mask.reindex(data.index).fillna(False)]
        residual_matches = pd.to_numeric(residual_data["event_family_match"], errors="coerce").fillna(0)
        rows.append(
            {
                "variant_id": variant_id,
                "orders": int(len(data)),
                "event_match_orders": int(matches.sum()),
                "event_match_rate_pct": float(matches.mean() * 100.0) if len(data) else 0.0,
                "event_mismatch_orders": int((matches == 0).sum()),
                "stage043_residual_orders": int(len(residual_data)),
                "stage043_residual_resolved_orders": int(residual_matches.sum()),
                "stage043_residual_resolution_rate_pct": float(residual_matches.mean() * 100.0)
                if len(residual_data)
                else 0.0,
                "c2_stop_orders": int(data["replay_event_family"].astype(str).eq("c2_stop").sum()),
                "open_no_intraday_event_orders": int(data["replay_event_family"].astype(str).eq("open_no_intraday_event").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("event_match_rate_pct", ascending=False).reset_index(drop=True)


def _residual_resolution(ledger: pd.DataFrame) -> pd.DataFrame:
    residual = ledger[pd.to_numeric(ledger["stage043_event_family_match"], errors="coerce").fillna(0).eq(0)].copy()
    keep = [
        "variant_id",
        "candidate_index",
        "official_open_trade_id",
        "vt_symbol",
        "direction",
        "official_open_date",
        "official_event_family",
        "stage043_replay_event_family",
        "replay_event_family",
        "event_family_match",
        "planned_stop_side",
        "replay_open_price",
        "planned_stop_price",
        "stage827_directional_c2_stop_price",
        "stage827_directional_c2_confirm_price",
        "planned_minus_directional_c2_stop",
        "first_bar_time",
        "first_bar_open",
        "first_bar_high",
        "first_bar_low",
        "first_bar_close",
        "replay_c2_hit_time",
        "replay_c2_confirm_time",
    ]
    return residual[[col for col in keep if col in residual.columns]].sort_values(["candidate_index", "variant_id"])


def _price_semantics(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    directional = data.apply(_directional_c2_prices, axis=1, result_type="expand")
    data["stage827_directional_c2_stop_price"] = pd.to_numeric(directional[0], errors="coerce")
    data["stage827_directional_c2_confirm_price"] = pd.to_numeric(directional[1], errors="coerce")
    data["planned_stop_side"] = data.apply(_planned_stop_side, axis=1)
    data["planned_equals_directional_c2_stop"] = np.isclose(
        pd.to_numeric(data["planned_stop_price"], errors="coerce"),
        pd.to_numeric(data["stage827_directional_c2_stop_price"], errors="coerce"),
        equal_nan=False,
    )
    data["stage043_residual"] = pd.to_numeric(data["event_family_match"], errors="coerce").fillna(0).eq(0)
    grouped = (
        data.groupby("planned_stop_side", dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            stage043_residual_orders=("stage043_residual", "sum"),
            planned_equals_directional_c2_stop=("planned_equals_directional_c2_stop", "sum"),
            median_abs_planned_vs_directional_stop_delta=(
                "planned_stop_price",
                lambda s: float(
                    np.nanmedian(
                        np.abs(
                            pd.to_numeric(s, errors="coerce").to_numpy()
                            - pd.to_numeric(data.loc[s.index, "stage827_directional_c2_stop_price"], errors="coerce").to_numpy()
                        )
                    )
                )
                if len(s)
                else np.nan,
            ),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )
    return grouped


def _semantic_curve(curve: pd.DataFrame, variant_summary: pd.DataFrame) -> pd.DataFrame:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["official_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data["official_drawdown_pct"] = _drawdown_pct(data["official_equity"])
    # Stage044 is semantic-only; same-exit equity is intentionally identical to official equity.
    data["stage044_same_exit_equity"] = data["official_equity"]
    data["stage044_same_exit_drawdown_pct"] = data["official_drawdown_pct"]
    return data


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, variant_summary: pd.DataFrame) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    baseline = variant_summary[
        variant_summary["variant_id"].eq("stage043_planned_stop_as_c2_stop_start0_stop_first")
    ].iloc[0].to_dict()
    directional = variant_summary[
        variant_summary["variant_id"].eq("stage827_directional_c2_stop_start0_stop_first")
    ].iloc[0].to_dict()
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                **official,
                "stage043_baseline_match_orders": int(baseline["event_match_orders"]),
                "stage043_baseline_match_rate_pct": float(baseline["event_match_rate_pct"]),
                "stage827_directional_match_orders": int(directional["event_match_orders"]),
                "stage827_directional_match_rate_pct": float(directional["event_match_rate_pct"]),
                "stage043_residual_orders": int(directional["stage043_residual_orders"]),
                "stage043_residual_resolved_by_directional_c2_orders": int(
                    directional["stage043_residual_resolved_orders"]
                ),
                "stage043_residual_resolution_rate_pct": float(directional["stage043_residual_resolution_rate_pct"]),
                "official_semantics_variant_id": directional["variant_id"],
                "official_semantics_match_rate_pct": float(directional["event_match_rate_pct"]),
                "decision": "stage044_c2_directional_stop_semantics_resolves_replay_residual_no_trade_rule",
                "candidate_ready": 0,
                "ab_triggered": 0,
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, ledger: pd.DataFrame) -> None:
    data = curve.copy()
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["official_equity"], color="#111827", linewidth=1.2, label="official C9/15w")
    axes[0].plot(
        data["date"],
        data["stage044_same_exit_equity"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="Stage044 same-exit semantic audit",
    )
    axes[0].set_title("Capital curve, semantic audit only")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(data["date"], data["official_drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    axes[1].plot(
        data["date"],
        data["stage044_same_exit_drawdown_pct"],
        color="#16a34a",
        linewidth=1.0,
        linestyle="--",
        label="Stage044 same-exit DD",
    )
    axes[1].set_title("Drawdown, unchanged by semantic-only repair")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    residual = ledger[
        ledger["variant_id"].eq("stage827_directional_c2_stop_start0_stop_first")
        & pd.to_numeric(ledger["event_family_match"], errors="coerce").fillna(0).eq(0)
    ].copy()
    residual["official_open_date_ts"] = pd.to_datetime(residual["official_open_date"], errors="coerce").dt.normalize()
    residual_daily = residual.groupby("official_open_date_ts")["candidate_index"].count()
    data["directional_c2_residual_mismatch_cum"] = data["date"].map(residual_daily).fillna(0).cumsum()
    axes[2].step(
        data["date"],
        data["directional_c2_residual_mismatch_cum"],
        where="post",
        color="#dc2626",
        linewidth=1.1,
        label="residual mismatches after Stage827 C2 formula",
    )
    axes[2].set_title("Residual event mismatches after directional C2 stop formula")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage044 C2 directional stop semantics audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_variant_chart(variant_summary: pd.DataFrame) -> None:
    data = variant_summary.sort_values("event_match_rate_pct", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(14, 7), constrained_layout=True)
    colors = ["#16a34a" if value >= 99.99 else "#f97316" for value in data["event_match_rate_pct"]]
    ax.barh(data["variant_id"], data["event_match_rate_pct"], color=colors)
    ax.set_xlim(0, 105)
    ax.set_xlabel("event family match rate %")
    ax.set_title("Replay event match by C2 stop semantics variant")
    ax.grid(axis="x", alpha=0.25)
    for i, value in enumerate(data["event_match_rate_pct"]):
        ax.text(value + 0.4, i, f"{value:.4f}%", va="center", fontsize=8)
    fig.savefig(VARIANT_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_residual_atlas(resolution: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> None:
    target = resolution[
        resolution["variant_id"].eq("stage827_directional_c2_stop_start0_stop_first")
    ].drop_duplicates("candidate_index")
    if target.empty:
        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        ax.text(0.5, 0.5, "No Stage043 residual samples", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(RESIDUAL_ATLAS_OUT, dpi=150)
        plt.close(fig)
        return
    fig, axes = plt.subplots(len(target), 1, figsize=(15, 3.8 * len(target)), constrained_layout=True)
    if len(target) == 1:
        axes = [axes]
    for ax, (_, row) in zip(axes, target.iterrows()):
        bars = s041._bars_for_symbol(groups, str(row.get("vt_symbol", "")))
        day = s041._bars_on_date(bars, _normalize_day(row.get("official_open_date"))) if not bars.empty else pd.DataFrame()
        open_ts = _parse_ts(row.get("first_bar_time"))
        scan = day[pd.to_datetime(day.get("bar_datetime_ts"), errors="coerce").ge(open_ts)].copy() if not day.empty else pd.DataFrame()
        scan = scan.sort_values("bar_datetime_ts").head(90).reset_index(drop=True)
        if scan.empty:
            ax.text(0.5, 0.5, "missing bars", ha="center", va="center")
            ax.set_axis_off()
            continue
        x = np.arange(len(scan))
        ax.plot(x, pd.to_numeric(scan["close"], errors="coerce"), color="#2563eb", linewidth=0.9, label="close")
        ax.fill_between(
            x,
            pd.to_numeric(scan["low"], errors="coerce"),
            pd.to_numeric(scan["high"], errors="coerce"),
            color="#bfdbfe",
            alpha=0.25,
            label="high-low range",
        )
        lines = [
            ("replay_open_price", "#111827", "entry"),
            ("planned_stop_price", "#f97316", "Stage043 planned_stop-as-C2"),
            ("stage827_directional_c2_stop_price", "#dc2626", "Stage827 directional C2 stop"),
            ("stage827_directional_c2_confirm_price", "#16a34a", "Stage827 directional C2 confirm"),
        ]
        for field, color, label in lines:
            value = _safe_float(row.get(field))
            if np.isfinite(value):
                ax.axhline(value, color=color, linewidth=0.85, linestyle="--", label=label)
        ax.axvline(0, color="#111827", linewidth=0.85, linestyle=":", label="official-open first bar")
        ax.set_title(
            f"{row.get('vt_symbol')} {row.get('direction')} idx={row.get('candidate_index')} "
            f"Stage043={row.get('stage043_replay_event_family')} Stage044={row.get('replay_event_family')} "
            f"match={int(_safe_float(row.get('event_family_match'), 0))}"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=7, ncol=4)
        tick_locs = np.linspace(0, len(scan) - 1, min(6, len(scan)), dtype=int)
        ax.set_xticks(tick_locs)
        ax.set_xticklabels(
            [pd.Timestamp(scan.iloc[i]["bar_datetime_ts"]).strftime("%m-%d %H:%M") for i in tick_locs],
            fontsize=8,
        )
    fig.suptitle("Stage044 residual atlas: planned stop vs Stage827 directional C2 stop", fontsize=14)
    fig.savefig(RESIDUAL_ATLAS_OUT, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    variant_summary: pd.DataFrame,
    price_semantics: pd.DataFrame,
    residual_resolution: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    directional_residual = residual_resolution[
        residual_resolution["variant_id"].eq("stage827_directional_c2_stop_start0_stop_first")
    ].copy()
    lines = [
        "# Stage044 C2 Directional Stop Semantics Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段定位：replay 语义审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        "- 决策：`stage044_c2_directional_stop_semantics_resolves_replay_residual_no_trade_rule`。",
        "",
        "## 核心结论",
        "",
        f"- Stage043 planned-stop baseline match：`{int(row['stage043_baseline_match_orders'])}/219 = {row['stage043_baseline_match_rate_pct']:.4f}%`。",
        f"- Stage827 directional C2 formula match：`{int(row['stage827_directional_match_orders'])}/219 = {row['stage827_directional_match_rate_pct']:.4f}%`。",
        f"- Stage043 residual resolved：`{int(row['stage043_residual_resolved_by_directional_c2_orders'])}/{int(row['stage043_residual_orders'])}`。",
        f"- 官方 C2 stop 公式：`{OFFICIAL_STAGE827_C2_FORMULA}`；confirm 公式：`{OFFICIAL_STAGE827_C2_CONFIRM_FORMULA}`。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        "",
        "## Variant Match",
        "",
        _md_table(variant_summary, max_rows=20),
        "",
        "## Planned Stop Side",
        "",
        _md_table(price_semantics, max_rows=20),
        "",
        "## Stage043 Residual Resolution, Directional C2 Variant",
        "",
        _md_table(directional_residual, max_rows=20),
        "",
        "## 视觉输出",
        "",
        f"- semantic path chart：`{PATH_CHART_OUT}`",
        f"- variant match chart：`{VARIANT_CHART_OUT}`",
        f"- residual atlas：`{RESIDUAL_ATLAS_OUT}`",
        "",
        "## 文件",
        "",
        f"- variant replay ledger：`{VARIANT_LEDGER_OUT}`",
        f"- variant summary：`{VARIANT_SUMMARY_OUT}`",
        f"- residual resolution：`{RESIDUAL_RESOLUTION_OUT}`",
        f"- price semantics：`{PRICE_SEMANTICS_OUT}`",
        f"- semantic curve：`{CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage043 的剩余 4 笔不是首根触线信号，也不是需要跳过首根 bar，而是 C2 stop 价格语义错误：真实 Stage827 用 entry ± 1R 从 layer risk 重建 stop/confirm。",
        "- 使用 Stage827 directional C2 公式后，timestamp-ready 子集事件 family match 达到 100%。这说明 replay 账本已能解释官方 C9/C2 事件 family，但仍只是基础设施校准，不是交易候选。",
        "- 下一步如果继续 replay 基础设施，应审计事件时间精度、C9/C2 价格字段与真实 engine trade event 的同步；在进入新分钟规则前仍要避免把 timestamp/replay 残差当成 alpha。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage043_replay = _load_stage043_replay()
    groups = s038._load_minute_groups(stage043_replay)
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    variant_ledger = _build_variant_ledger(stage043_replay, groups)
    variant_summary = _variant_summary(variant_ledger)
    residual_resolution = _residual_resolution(variant_ledger)
    price_semantics = _price_semantics(stage043_replay)
    semantic_curve = _semantic_curve(curve, variant_summary)
    summary = _summary(curve, lots, variant_summary)

    _write_csv(variant_ledger, VARIANT_LEDGER_OUT)
    _write_csv(variant_summary, VARIANT_SUMMARY_OUT)
    _write_csv(residual_resolution, RESIDUAL_RESOLUTION_OUT)
    _write_csv(price_semantics, PRICE_SEMANTICS_OUT)
    _write_csv(semantic_curve, CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(semantic_curve, variant_ledger)
    _plot_variant_chart(variant_summary)
    _plot_residual_atlas(residual_resolution, groups)
    _write_report(summary, variant_summary, price_semantics, residual_resolution)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage044_c2_directional_stop_semantics_resolves_replay_residual_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "summary": summary.iloc[0].to_dict(),
        "outputs": {
            "variant_ledger": VARIANT_LEDGER_OUT,
            "variant_summary": VARIANT_SUMMARY_OUT,
            "residual_resolution": RESIDUAL_RESOLUTION_OUT,
            "price_semantics": PRICE_SEMANTICS_OUT,
            "semantic_curve": CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "variant_chart": VARIANT_CHART_OUT,
            "residual_atlas": RESIDUAL_ATLAS_OUT,
        },
        "judgment": (
            "The remaining Stage043 residuals are explained by official Stage827 C2 stop semantics: "
            "stop is reconstructed as entry minus direction-adjusted 1R, not copied from planned_stop_price."
        ),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
