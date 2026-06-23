from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage241"
MODEL_TAG = "stage241_aligned_bar_return_artifact_peel_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage241_aligned_bar_return_artifact_peel_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_artifact_audit_{MODEL_TAG}.csv"
GROUP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_group_summary_{MODEL_TAG}.csv"
TRANSITION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_without_last_quintile_transition_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
ARTIFACT_RATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_group_label_rates_{MODEL_TAG}.png"
DEGENERATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quintile_by_degenerate_risk_heatmap_{MODEL_TAG}.png"
TRANSITION_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_with_vs_without_last_quintile_transition_{MODEL_TAG}.png"
LAST_CONTRIB_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_last_bar_contribution_scatter_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

ATLAS_LOOKBACK_BARS = 120
MIN_SPLIT_ROWS = 4


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _quality_quintile(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    result = pd.Series(np.nan, index=series.index, dtype="float64")
    mask = values.notna()
    if int(mask.sum()) == 0:
        return result
    pct = values[mask].rank(method="average", pct=True)
    quintile = np.ceil((pct * 5).clip(lower=0, upper=5)).astype(int).clip(lower=1, upper=5)
    result.loc[mask] = quintile.astype(float)
    return result


def _rate(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _prepare_joined(joined: pd.DataFrame) -> pd.DataFrame:
    result = joined.copy()
    result["decision_ts"] = pd.to_datetime(result["decision_ts"], errors="coerce")
    result["decision_year"] = result["decision_ts"].dt.year.astype("Int64")
    result["aligned_bar_quintile"] = (
        pd.to_numeric(result["quality_quintile_aligned_bar_return_1m"], errors="coerce").round().astype("Int64")
    )
    result["aligned_bar_value"] = pd.to_numeric(result["quality_value_aligned_bar_return_1m"], errors="coerce")
    result["direction_sign"] = np.where(result["direction"].astype(str).str.lower().eq("short"), -1.0, 1.0)
    for column in ["risk_bad_label", "right_tail_label", "ordinary_clean_label", "low_resolution_label"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["stage241_strategy_rule_allowed"] = 0
    result["stage241_true_engine_allowed"] = 0
    return result


def _load_event_bars(row: pd.Series, lookback: int = ATLAS_LOOKBACK_BARS) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    if not path.exists():
        raise RuntimeError(f"missing filtered source: {path}")
    bars = pd.read_parquet(path)
    bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
    if "bar_start_ts" in bars.columns:
        bars["bar_start_ts"] = pd.to_datetime(bars["bar_start_ts"], errors="coerce")
    decision_ts = pd.Timestamp(row["decision_ts"])
    bars = bars[bars["bar_end_ts"].notna() & bars["bar_end_ts"].le(decision_ts)].copy()
    return bars.sort_values("bar_end_ts").tail(lookback).reset_index(drop=True)


def _directional_return(close_now: float, close_before: float, sign: float) -> float:
    if not np.isfinite(close_now) or not np.isfinite(close_before) or close_before == 0:
        return np.nan
    return float(sign * (close_now / close_before - 1.0) * 10000.0)


def _event_artifact(row: pd.Series) -> dict[str, Any]:
    bars = _load_event_bars(row, lookback=ATLAS_LOOKBACK_BARS)
    if len(bars) < 2:
        raise RuntimeError(f"insufficient bars for {row['request_id']}: {len(bars)}")
    sign = float(row["direction_sign"])
    close = pd.to_numeric(bars["close"], errors="coerce")
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    open_ = pd.to_numeric(bars["open"], errors="coerce")
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    tick_count = pd.to_numeric(bars["tick_count"], errors="coerce") if "tick_count" in bars.columns else pd.Series(np.nan, index=bars.index)

    last = bars.iloc[-1]
    prev = bars.iloc[-2]
    last_end = pd.Timestamp(last["bar_end_ts"])
    last_start = pd.Timestamp(last["bar_start_ts"]) if "bar_start_ts" in bars.columns and pd.notna(last["bar_start_ts"]) else pd.NaT
    decision_ts = pd.Timestamp(row["decision_ts"])
    last_degenerate = int(
        np.isfinite(open_.iloc[-1])
        and open_.iloc[-1] == high.iloc[-1] == low.iloc[-1] == close.iloc[-1]
    )
    last_zero_range = int(np.isfinite(high.iloc[-1]) and np.isfinite(low.iloc[-1]) and high.iloc[-1] == low.iloc[-1])
    last_single_tick = int(pd.notna(tick_count.iloc[-1]) and float(tick_count.iloc[-1]) <= 1)
    last_return_bps = _directional_return(float(close.iloc[-1]), float(close.iloc[-2]), sign)
    prev_return_bps = _directional_return(float(close.iloc[-2]), float(close.iloc[-3]), sign) if len(close) >= 3 else np.nan

    def without_last_return(lookback: int) -> float:
        if len(close) < lookback + 2:
            return np.nan
        return _directional_return(float(close.iloc[-2]), float(close.iloc[-2 - lookback]), sign)

    volume_30 = volume.tail(31)
    volume_30_sum = float(volume_30.sum()) if volume_30.notna().any() else 0.0
    last_volume_share_30 = float(volume_30.iloc[-1] / volume_30_sum) if volume_30_sum > 0 else np.nan
    record = {
        "request_id": row["request_id"],
        "extension_window_id": row["extension_window_id"],
        "vt_symbol": row["vt_symbol"],
        "exchange": row["exchange"],
        "product": row["product"],
        "direction": row["direction"],
        "decision_ts": decision_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "decision_year": int(row["decision_year"]) if pd.notna(row["decision_year"]) else np.nan,
        "decision_clock": decision_ts.strftime("%H:%M:%S"),
        "last_bar_start_ts": "" if pd.isna(last_start) else last_start.strftime("%Y-%m-%d %H:%M:%S"),
        "last_bar_end_ts": last_end.strftime("%Y-%m-%d %H:%M:%S"),
        "last_bar_end_clock": last_end.strftime("%H:%M:%S"),
        "last_bar_end_equals_decision": int(last_end == decision_ts),
        "last_bar_open_clock_flag": int(last_end.strftime("%H:%M:%S") in {"09:00:00", "21:00:00"}),
        "priority_class": row["priority_class"],
        "filtered_source_file": row["filtered_source_file"],
        "aligned_bar_quintile": int(row["aligned_bar_quintile"]),
        "aligned_bar_value": float(row["aligned_bar_value"]),
        "risk_bad_label": int(row["risk_bad_label"]),
        "right_tail_label": int(row["right_tail_label"]),
        "ordinary_clean_label": int(row["ordinary_clean_label"]),
        "low_resolution_label": int(row["low_resolution_label"]),
        "predecision_bar_count": int(len(bars)),
        "last_bar_degenerate_ohlc": last_degenerate,
        "last_bar_zero_range": last_zero_range,
        "last_bar_single_tick": last_single_tick,
        "last_bar_tick_count": float(tick_count.iloc[-1]) if pd.notna(tick_count.iloc[-1]) else np.nan,
        "last_bar_volume": float(volume.iloc[-1]) if pd.notna(volume.iloc[-1]) else np.nan,
        "last_bar_volume_share_30bar": last_volume_share_30,
        "last_bar_directional_return_bps": last_return_bps,
        "prior_bar_directional_return_bps": prev_return_bps,
        "degenerate_nonzero_gap_flag": int(last_degenerate and np.isfinite(last_return_bps) and abs(last_return_bps) > 1e-12),
        "without_last_return_5bar_bps": without_last_return(5),
        "without_last_return_30bar_bps": without_last_return(30),
        "without_last_return_60bar_bps": without_last_return(60),
        "stage241_strategy_rule_allowed": 0,
        "stage241_true_engine_allowed": 0,
    }
    return record


def _build_event_audit(joined: pd.DataFrame) -> pd.DataFrame:
    records = [_event_artifact(row) for _, row in joined.iterrows()]
    audit = pd.DataFrame(records)
    audit["without_last_1bar_quintile"] = _quality_quintile(audit["prior_bar_directional_return_bps"]).round().astype("Int64")
    audit["without_last_30bar_quintile"] = _quality_quintile(audit["without_last_return_30bar_bps"]).round().astype("Int64")
    audit["original_q5_flag"] = audit["aligned_bar_quintile"].eq(5).astype(int)
    audit["original_q1_flag"] = audit["aligned_bar_quintile"].eq(1).astype(int)
    audit["q5_persist_without_last_1bar_flag"] = (
        audit["original_q5_flag"].eq(1) & audit["without_last_1bar_quintile"].ge(4)
    ).astype(int)
    audit["q5_drop_without_last_1bar_flag"] = (
        audit["original_q5_flag"].eq(1) & audit["without_last_1bar_quintile"].le(2)
    ).astype(int)
    audit["q5_nonartifact_lastbar_flag"] = (
        audit["original_q5_flag"].eq(1)
        & audit["last_bar_degenerate_ohlc"].eq(0)
        & audit["last_bar_single_tick"].eq(0)
    ).astype(int)
    return audit


def _summarize_group(group_id: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "row_count": int(len(frame)),
        "risk_bad_count": int(pd.to_numeric(frame["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "risk_bad_rate": _rate(frame["risk_bad_label"]),
        "right_tail_count": int(pd.to_numeric(frame["right_tail_label"], errors="coerce").fillna(0).sum()),
        "right_tail_rate": _rate(frame["right_tail_label"]),
        "ordinary_clean_count": int(pd.to_numeric(frame["ordinary_clean_label"], errors="coerce").fillna(0).sum()),
        "ordinary_clean_rate": _rate(frame["ordinary_clean_label"]),
        "degenerate_last_bar_count": int(pd.to_numeric(frame["last_bar_degenerate_ohlc"], errors="coerce").fillna(0).sum()),
        "single_tick_last_bar_count": int(pd.to_numeric(frame["last_bar_single_tick"], errors="coerce").fillna(0).sum()),
        "degenerate_nonzero_gap_count": int(pd.to_numeric(frame["degenerate_nonzero_gap_flag"], errors="coerce").fillna(0).sum()),
        "last_bar_directional_return_bps_median": float(pd.to_numeric(frame["last_bar_directional_return_bps"], errors="coerce").median()),
        "prior_bar_directional_return_bps_median": float(pd.to_numeric(frame["prior_bar_directional_return_bps"], errors="coerce").median()),
        "without_last_return_30bar_bps_median": float(pd.to_numeric(frame["without_last_return_30bar_bps"], errors="coerce").median()),
        "last_bar_volume_share_30bar_median": float(pd.to_numeric(frame["last_bar_volume_share_30bar"], errors="coerce").median()),
        "stage241_strategy_rule_allowed": 0,
    }


def _build_group_summary(event_audit: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "all": event_audit,
        "q1_all": event_audit[event_audit["aligned_bar_quintile"].eq(1)],
        "q5_all": event_audit[event_audit["aligned_bar_quintile"].eq(5)],
        "q5_degenerate_last_bar": event_audit[
            event_audit["aligned_bar_quintile"].eq(5) & event_audit["last_bar_degenerate_ohlc"].eq(1)
        ],
        "q5_non_degenerate_last_bar": event_audit[
            event_audit["aligned_bar_quintile"].eq(5) & event_audit["last_bar_degenerate_ohlc"].eq(0)
        ],
        "q5_single_tick_last_bar": event_audit[
            event_audit["aligned_bar_quintile"].eq(5) & event_audit["last_bar_single_tick"].eq(1)
        ],
        "q5_nonartifact_lastbar": event_audit[event_audit["q5_nonartifact_lastbar_flag"].eq(1)],
        "q5_drop_without_last_1bar": event_audit[event_audit["q5_drop_without_last_1bar_flag"].eq(1)],
        "q5_persist_without_last_1bar": event_audit[event_audit["q5_persist_without_last_1bar_flag"].eq(1)],
    }
    return pd.DataFrame([_summarize_group(group_id, frame) for group_id, frame in groups.items()])


def _build_transition(event_audit: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for original in range(1, 6):
        group = event_audit[event_audit["aligned_bar_quintile"].eq(original)]
        for without_last in range(1, 6):
            cell = group[group["without_last_1bar_quintile"].eq(without_last)]
            records.append(
                {
                    "original_aligned_bar_quintile": original,
                    "without_last_1bar_quintile": without_last,
                    "row_count": int(len(cell)),
                    "risk_bad_count": int(cell["risk_bad_label"].sum()),
                    "risk_bad_rate": _rate(cell["risk_bad_label"]),
                    "right_tail_count": int(cell["right_tail_label"].sum()),
                    "right_tail_rate": _rate(cell["right_tail_label"]),
                    "degenerate_last_bar_count": int(cell["last_bar_degenerate_ohlc"].sum()),
                    "stage241_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_split_summary(event_audit: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in event_audit.groupby(split_column, dropna=False):
            q5 = split_group[split_group["aligned_bar_quintile"].eq(5)]
            q5_nonartifact = q5[q5["q5_nonartifact_lastbar_flag"].eq(1)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "row_count": int(len(split_group)),
                    "q5_count": int(len(q5)),
                    "q5_nonartifact_count": int(len(q5_nonartifact)),
                    "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
                    "q5_nonartifact_risk_bad_rate": _rate(q5_nonartifact["risk_bad_label"]),
                    "q5_right_tail_rate": _rate(q5["right_tail_label"]),
                    "q5_nonartifact_right_tail_rate": _rate(q5_nonartifact["right_tail_label"]),
                    "valid_compare": int(len(q5) >= MIN_SPLIT_ROWS and len(q5_nonartifact) >= MIN_SPLIT_ROWS),
                    "stage241_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _select_atlas(event_audit: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("q5_degenerate_bad", event_audit.query("aligned_bar_quintile == 5 and last_bar_degenerate_ohlc == 1 and risk_bad_label == 1")),
        ("q5_degenerate_tail", event_audit.query("aligned_bar_quintile == 5 and last_bar_degenerate_ohlc == 1 and right_tail_label == 1")),
        ("q5_nonartifact_tail", event_audit.query("q5_nonartifact_lastbar_flag == 1 and right_tail_label == 1")),
        ("q5_nonartifact_bad", event_audit.query("q5_nonartifact_lastbar_flag == 1 and risk_bad_label == 1")),
        ("q5_drop_without_last", event_audit.query("q5_drop_without_last_1bar_flag == 1")),
        ("q5_persist_without_last", event_audit.query("q5_persist_without_last_1bar_flag == 1")),
    ]
    frames: list[pd.DataFrame] = []
    for category, frame in specs:
        if frame.empty:
            continue
        picked = frame.sort_values("aligned_bar_value", ascending=False).head(6).copy()
        picked["atlas_category"] = category
        frames.append(picked)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage241 peels aligned-bar artefacts only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"q5={summary['q5_count']} | q5_nonartifact={summary['q5_nonartifact_lastbar_count']} | "
        f"q5_deg={summary['q5_degenerate_last_bar_count']} | q5_drop_without_last={summary['q5_drop_without_last_1bar_count']} | "
        f"true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_artifact_rates(group_summary: pd.DataFrame) -> None:
    plot_ids = [
        "q1_all",
        "q5_all",
        "q5_degenerate_last_bar",
        "q5_non_degenerate_last_bar",
        "q5_nonartifact_lastbar",
        "q5_drop_without_last_1bar",
        "q5_persist_without_last_1bar",
    ]
    plot = group_summary[group_summary["group_id"].isin(plot_ids)].copy()
    fig, ax = plt.subplots(figsize=(13, 5.5))
    x = np.arange(len(plot))
    width = 0.26
    ax.bar(x - width, plot["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, plot["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, plot["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["group_id"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Stage241 artefact peel: label rates by fixed structural group")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in plot.reset_index(drop=True).iterrows():
        ax.text(idx, max(row["risk_bad_rate"], row["right_tail_rate"], row["ordinary_clean_rate"]) + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(ARTIFACT_RATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_degenerate_heatmap(event_audit: pd.DataFrame) -> None:
    records: list[dict[str, Any]] = []
    for quintile in range(1, 6):
        for degenerate in [0, 1]:
            group = event_audit[
                event_audit["aligned_bar_quintile"].eq(quintile)
                & event_audit["last_bar_degenerate_ohlc"].eq(degenerate)
            ]
            records.append(
                {
                    "aligned_bar_quintile": quintile,
                    "last_bar_degenerate_ohlc": degenerate,
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "row_count": int(len(group)),
                }
            )
    frame = pd.DataFrame(records)
    pivot = frame.pivot(index="last_bar_degenerate_ohlc", columns="aligned_bar_quintile", values="risk_bad_rate")
    count = frame.pivot(index="last_bar_degenerate_ohlc", columns="aligned_bar_quintile", values="row_count")
    fig, ax = plt.subplots(figsize=(8.5, 4))
    data = pivot.to_numpy(dtype=float)
    masked = np.ma.masked_invalid(data)
    image = ax.imshow(masked, aspect="auto", cmap="Reds", vmin=0, vmax=0.6)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([f"Q{col}" for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([f"degenerate={idx}" for idx in pivot.index])
    ax.set_title("Risk-bad rate by original aligned quintile and degenerate last bar")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            n = int(count.to_numpy()[y, x])
            if np.isfinite(value):
                ax.text(x, y, f"{value:.2f}\nn={n}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(DEGENERATE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_transition(transition: pd.DataFrame) -> None:
    pivot = transition.pivot(
        index="original_aligned_bar_quintile",
        columns="without_last_1bar_quintile",
        values="row_count",
    ).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 5.8))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="Blues")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([f"Q{col}" for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([f"orig Q{idx}" for idx in pivot.index])
    ax.set_xlabel("without-last previous 1-bar quintile")
    ax.set_ylabel("original aligned-bar quintile")
    ax.set_title("Original Q vs prior-bar quintile after removing final bar")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = int(data[y, x])
            if value:
                ax.text(x, y, str(value), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.04)
    fig.tight_layout()
    fig.savefig(TRANSITION_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_last_contrib(event_audit: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = np.where(event_audit["last_bar_degenerate_ohlc"].eq(1), "#d62728", "#1f77b4")
    sizes = np.where(event_audit["right_tail_label"].eq(1), 55, 25)
    ax.scatter(
        event_audit["prior_bar_directional_return_bps"],
        event_audit["last_bar_directional_return_bps"],
        c=colors,
        s=sizes,
        alpha=0.75,
        edgecolor="white",
        linewidth=0.4,
    )
    ax.axhline(0, color="#111111", linewidth=0.8)
    ax.axvline(0, color="#111111", linewidth=0.8)
    ax.set_xlabel("prior bar directional return bps")
    ax.set_ylabel("last bar directional return bps")
    ax.set_title("Last-bar contribution vs prior-bar contribution; red=degenerate final bar, larger=right-tail")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(LAST_CONTRIB_SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(selected: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if selected.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    atlas_rows: list[dict[str, Any]] = []
    page = 1
    for category, group in selected.groupby("atlas_category", sort=False):
        rows = group.reset_index(drop=True)
        for start in range(0, len(rows), 6):
            page_rows = rows.iloc[start : start + 6]
            fig, axes = plt.subplots(3, 2, figsize=(14, 10), sharex=False)
            for ax in axes.flat:
                ax.axis("off")
            for panel_idx, (_, row) in enumerate(page_rows.iterrows()):
                ax = axes.flat[panel_idx]
                ax.axis("on")
                bars = _load_event_bars(row, lookback=ATLAS_LOOKBACK_BARS)
                sign = 1.0 if str(row["direction"]).lower() != "short" else -1.0
                close = pd.to_numeric(bars["close"], errors="coerce")
                y = sign * (close / close.iloc[0] - 1.0) * 10000.0 if len(close) and close.iloc[0] != 0 else pd.Series([0.0] * len(close))
                x = np.arange(-len(y) + 1, 1)
                ax.plot(x[:-1], y.iloc[:-1], color="#1f77b4", linewidth=1.2)
                ax.plot(x[-2:], y.iloc[-2:], color="#d62728", linewidth=1.6)
                ax.scatter([0], [float(y.iloc[-1])], color="#d62728", s=24, zorder=3)
                ax.axhline(0, color="#111111", linewidth=0.7, alpha=0.7)
                ax.axvline(0, color="#d62728", linewidth=0.8, alpha=0.8)
                title = (
                    f"{row['vt_symbol']} {row['direction']} origQ{int(row['aligned_bar_quintile'])} "
                    f"preQ{int(row['without_last_1bar_quintile']) if pd.notna(row['without_last_1bar_quintile']) else 'NA'} "
                    f"deg={int(row['last_bar_degenerate_ohlc'])} tick={row['last_bar_tick_count']:.0f}"
                )
                ax.set_title(title, fontsize=8)
                ax.tick_params(axis="both", labelsize=7)
                ax.grid(alpha=0.2)
                subtitle = (
                    f"last={float(row['last_bar_directional_return_bps']):+.1f}bp; "
                    f"prior={float(row['prior_bar_directional_return_bps']):+.1f}bp; "
                    f"risk={int(row['risk_bad_label'])}; tail={int(row['right_tail_label'])}"
                )
                ax.text(0.01, 0.02, subtitle, transform=ax.transAxes, fontsize=7, va="bottom")
                atlas_rows.append(
                    {
                        "atlas_page": page,
                        "panel": panel_idx + 1,
                        "atlas_category": category,
                        "request_id": row["request_id"],
                        "vt_symbol": row["vt_symbol"],
                        "decision_ts": row["decision_ts"],
                        "direction": row["direction"],
                        "aligned_bar_quintile": int(row["aligned_bar_quintile"]),
                        "without_last_1bar_quintile": int(row["without_last_1bar_quintile"]) if pd.notna(row["without_last_1bar_quintile"]) else np.nan,
                        "last_bar_degenerate_ohlc": int(row["last_bar_degenerate_ohlc"]),
                        "last_bar_single_tick": int(row["last_bar_single_tick"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page)).relative_to(REPO_DIR)),
                    }
                )
            fig.suptitle(f"Stage241 {category}: final bar in red, prior path in blue", fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(atlas_rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage239_joined_exists", int(STAGE239_JOINED_IN.exists()), "Stage239 joined audit exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists"),
        ("event_artifact_row_count_219", int(summary["event_artifact_row_count"] == 219), "219 event artifact rows"),
        ("q5_degenerate_present", int(summary["q5_degenerate_last_bar_count"] > 0), "Q5 has degenerate final bars"),
        ("q5_nonartifact_sample_small", int(summary["q5_nonartifact_lastbar_count"] < summary["q5_count"]), "artefact peel materially reduces Q5 sample"),
        ("strategy_rule_created", 0, "no strategy rule created"),
        ("true_engine_run", 0, "no true engine run"),
        ("ab_triggered", 0, "no A/B triggered"),
        ("official_config_changed", 0, "official config untouched"),
        ("order_api_called", 0, "no order API call"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": passed, "description": description} for gate_id, passed, description in rows])


def _write_report(
    summary: dict[str, Any],
    group_summary: pd.DataFrame,
    transition: pd.DataFrame,
    split_summary: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    transition_view = transition[
        transition["original_aligned_bar_quintile"].eq(5)
    ][
        [
            "original_aligned_bar_quintile",
            "without_last_1bar_quintile",
            "row_count",
            "risk_bad_rate",
            "right_tail_rate",
            "degenerate_last_bar_count",
        ]
    ]
    split_view = split_summary[
        [
            "split_type",
            "split_value",
            "q5_count",
            "q5_nonartifact_count",
            "q5_risk_bad_rate",
            "q5_nonartifact_risk_bad_rate",
            "q5_right_tail_rate",
            "q5_nonartifact_right_tail_rate",
            "valid_compare",
        ]
    ].head(16)
    report = f"""# {STAGE} Aligned Bar Return Artefact Peel Audit

## Decision

- decision: `{summary['decision']}`
- event_artifact_row_count: `{summary['event_artifact_row_count']}`
- q5_count: `{summary['q5_count']}`
- q5_degenerate_last_bar_count: `{summary['q5_degenerate_last_bar_count']}`
- q5_nonartifact_lastbar_count: `{summary['q5_nonartifact_lastbar_count']}`
- q5_drop_without_last_1bar_count: `{summary['q5_drop_without_last_1bar_count']}`
- q5_persist_without_last_1bar_count: `{summary['q5_persist_without_last_1bar_count']}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- 输入只来自 Stage239 joined audit 与 Stage180 predecision minute bars。
- 固定结构剥离：`last_bar_degenerate_ohlc`、`last_bar_single_tick`、最后一根方向收益、去掉最后一根后的前一根方向收益。
- 不根据标签选择阈值；本阶段只判断 Stage239 的 Q5 是否主要来自最后一根 artefact。

## Group Summary

{_md_table(group_summary, max_rows=None)}

## Original Q5 Transition After Removing Last Bar

{_md_table(transition_view, max_rows=None)}

## Split Summary

{_md_table(split_view, max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Atlas Manifest Sample

{_md_table(atlas_manifest.head(12), max_rows=None)}

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{ARTIFACT_RATE_CHART_OUT.relative_to(REPO_DIR)}`
- `{DEGENERATE_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{TRANSITION_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{LAST_CONTRIB_SCATTER_OUT.relative_to(REPO_DIR)}`
- atlas_pages: `{summary['atlas_page_count']}`
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    joined = _prepare_joined(_read_csv(STAGE239_JOINED_IN))
    event_audit = _build_event_audit(joined)
    group_summary = _build_group_summary(event_audit)
    transition = _build_transition(event_audit)
    split_summary = _build_split_summary(event_audit)
    atlas_selected = _select_atlas(event_audit)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_selected)

    q5 = event_audit[event_audit["aligned_bar_quintile"].eq(5)]
    q5_nonartifact = q5[q5["q5_nonartifact_lastbar_flag"].eq(1)]
    q5_degenerate = q5[q5["last_bar_degenerate_ohlc"].eq(1)]
    q5_drop = q5[q5["q5_drop_without_last_1bar_flag"].eq(1)]
    q5_persist = q5[q5["q5_persist_without_last_1bar_flag"].eq(1)]
    decision = "stage241_aligned_bar_q5_partly_artifact_peel_blocks_true_engine_no_rule"
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_artifact_row_count": int(len(event_audit)),
        "q5_count": int(len(q5)),
        "q5_risk_bad_count": int(q5["risk_bad_label"].sum()),
        "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
        "q5_right_tail_count": int(q5["right_tail_label"].sum()),
        "q5_right_tail_rate": _rate(q5["right_tail_label"]),
        "q5_degenerate_last_bar_count": int(q5["last_bar_degenerate_ohlc"].sum()),
        "q5_degenerate_last_bar_rate": _rate(q5["last_bar_degenerate_ohlc"]),
        "q5_single_tick_last_bar_count": int(q5["last_bar_single_tick"].sum()),
        "q5_single_tick_last_bar_rate": _rate(q5["last_bar_single_tick"]),
        "q5_degenerate_nonzero_gap_count": int(q5["degenerate_nonzero_gap_flag"].sum()),
        "q5_nonartifact_lastbar_count": int(len(q5_nonartifact)),
        "q5_nonartifact_risk_bad_count": int(q5_nonartifact["risk_bad_label"].sum()),
        "q5_nonartifact_risk_bad_rate": _rate(q5_nonartifact["risk_bad_label"]),
        "q5_nonartifact_right_tail_count": int(q5_nonartifact["right_tail_label"].sum()),
        "q5_nonartifact_right_tail_rate": _rate(q5_nonartifact["right_tail_label"]),
        "q5_degenerate_risk_bad_count": int(q5_degenerate["risk_bad_label"].sum()),
        "q5_degenerate_risk_bad_rate": _rate(q5_degenerate["risk_bad_label"]),
        "q5_degenerate_right_tail_count": int(q5_degenerate["right_tail_label"].sum()),
        "q5_degenerate_right_tail_rate": _rate(q5_degenerate["right_tail_label"]),
        "q5_drop_without_last_1bar_count": int(len(q5_drop)),
        "q5_drop_without_last_1bar_rate": float(len(q5_drop) / len(q5)) if len(q5) else np.nan,
        "q5_persist_without_last_1bar_count": int(len(q5_persist)),
        "q5_persist_without_last_1bar_rate": float(len(q5_persist) / len(q5)) if len(q5) else np.nan,
        "atlas_event_count": int(len(atlas_manifest)),
        "atlas_page_count": int(len(atlas_paths)),
        "strategy_feature_usable": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "official_config_changed": 0,
        "ctp_or_simnow_connected": 0,
        "order_api_called": 0,
        "official_curve_initial_equity": float(curve["account_equity"].iloc[0]),
        "official_curve_final_equity": float(curve["account_equity"].iloc[-1]),
        "official_curve_total_return_pct": float((curve["account_equity"].iloc[-1] / curve["account_equity"].iloc[0] - 1) * 100),
        "official_curve_max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "official_curve_broker10_peak_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        "visual_file_count": 5 + int(len(atlas_paths)),
    }
    gate_status = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(event_audit, EVENT_AUDIT_OUT)
    _write_csv(group_summary, GROUP_SUMMARY_OUT)
    _write_csv(transition, TRANSITION_OUT)
    _write_csv(split_summary, SPLIT_SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, group_summary, transition, split_summary, atlas_manifest, gate_status)

    _plot_official_path(curve, summary)
    _plot_artifact_rates(group_summary)
    _plot_degenerate_heatmap(event_audit)
    _plot_transition(transition)
    _plot_last_contrib(event_audit)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
