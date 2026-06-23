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
STAGE = "Stage244"
MODEL_TAG = "stage244_volume_q4_q5_mechanism_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage244_volume_q4_q5_mechanism_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE243_DIR = LINE_DIR / "outputs" / "stage243_volume_zscore_counterexample_atlas"
STAGE243_PREFIX = "qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas"
STAGE243_TAG = "stage243_volume_zscore_counterexample_atlas_v1"
STAGE243_EVENT_IN = STAGE243_DIR / f"{STAGE243_PREFIX}_event_volume_zscore_audit_{STAGE243_TAG}.csv"

STAGE241_DIR = LINE_DIR / "outputs" / "stage241_aligned_bar_return_artifact_peel_audit"
STAGE241_PREFIX = "qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit"
STAGE241_TAG = "stage241_aligned_bar_return_artifact_peel_audit_v1"
STAGE241_EVENT_IN = STAGE241_DIR / f"{STAGE241_PREFIX}_event_artifact_audit_{STAGE241_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_mechanism_audit_{MODEL_TAG}.csv"
MECHANISM_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mechanism_summary_{MODEL_TAG}.csv"
ARTIFACT_LABEL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_label_summary_{MODEL_TAG}.csv"
SHAPE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_shape_summary_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q5_minus_q4_split_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
FLAG_RATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q4_q5_mechanism_flag_rates_{MODEL_TAG}.png"
ARTIFACT_LABEL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_clean_label_rates_{MODEL_TAG}.png"
SHAPE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q4_q5_path_shape_medians_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q5_minus_q4_split_delta_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_artifact_price_scatter_{MODEL_TAG}.png"
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


def _rate(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.median()) if values.notna().any() else np.nan


def _prepare_event(stage243: pd.DataFrame, stage241: pd.DataFrame) -> pd.DataFrame:
    artifact_cols = [
        "request_id",
        "last_bar_degenerate_ohlc",
        "last_bar_zero_range",
        "last_bar_single_tick",
        "last_bar_tick_count",
        "last_bar_volume",
        "last_bar_volume_share_30bar",
        "last_bar_directional_return_bps",
        "prior_bar_directional_return_bps",
        "degenerate_nonzero_gap_flag",
        "last_bar_open_clock_flag",
        "without_last_return_5bar_bps",
        "without_last_return_30bar_bps",
        "without_last_return_60bar_bps",
    ]
    missing = [column for column in artifact_cols if column not in stage241.columns]
    if missing:
        raise RuntimeError(f"missing Stage241 artifact columns: {missing}")
    event = stage243.merge(stage241[artifact_cols], on="request_id", how="left", validate="one_to_one")
    for column in [
        "risk_bad_label",
        "right_tail_label",
        "ordinary_clean_label",
        "low_resolution_label",
        "event_time_missing_label",
        "runway_ready_label",
        "volume_zscore_quintile",
        "efficiency_quintile",
        "last_bar_degenerate_ohlc",
        "last_bar_zero_range",
        "last_bar_single_tick",
        "degenerate_nonzero_gap_flag",
        "last_bar_open_clock_flag",
    ]:
        event[column] = pd.to_numeric(event[column], errors="coerce").fillna(0).astype(int)
    for column in [
        "audit_value_volume_zscore_60m",
        "quality_value_directional_efficiency_30m",
        "quality_value_aligned_bar_return_1m",
        "last_bar_tick_count",
        "last_bar_volume",
        "last_bar_volume_share_30bar",
        "last_bar_directional_return_bps",
        "prior_bar_directional_return_bps",
        "without_last_return_5bar_bps",
        "without_last_return_30bar_bps",
        "without_last_return_60bar_bps",
    ]:
        event[column] = pd.to_numeric(event[column], errors="coerce")
    event["decision_ts"] = pd.to_datetime(event["decision_ts"], errors="coerce")
    event["decision_year"] = event["decision_ts"].dt.year.astype("Int64")
    event["volume_q4_flag"] = event["volume_zscore_quintile"].eq(4).astype(int)
    event["volume_q5_flag"] = event["volume_zscore_quintile"].eq(5).astype(int)
    event["artifact_context_flag"] = (
        event["low_resolution_label"].eq(1)
        | event["event_time_missing_label"].eq(1)
        | event["last_bar_degenerate_ohlc"].eq(1)
        | event["last_bar_single_tick"].eq(1)
        | event["degenerate_nonzero_gap_flag"].eq(1)
        | event["last_bar_open_clock_flag"].eq(1)
    ).astype(int)
    event["clean_context_flag"] = event["artifact_context_flag"].eq(0).astype(int)
    event["stage244_strategy_rule_allowed"] = 0
    event["stage244_true_engine_allowed"] = 0
    return event


def _group_frame(event: pd.DataFrame, group_id: str) -> pd.DataFrame:
    if group_id == "volume_q4":
        return event[event["volume_q4_flag"].eq(1)]
    if group_id == "volume_q5":
        return event[event["volume_q5_flag"].eq(1)]
    if group_id == "q4_bad":
        return event[event["volume_q4_flag"].eq(1) & event["risk_bad_label"].eq(1)]
    if group_id == "q5_bad":
        return event[event["volume_q5_flag"].eq(1) & event["risk_bad_label"].eq(1)]
    if group_id == "q4_tail":
        return event[event["volume_q4_flag"].eq(1) & event["right_tail_label"].eq(1)]
    if group_id == "q5_tail":
        return event[event["volume_q5_flag"].eq(1) & event["right_tail_label"].eq(1)]
    if group_id == "q5_clean_bad":
        return event[event["volume_q5_flag"].eq(1) & event["risk_bad_label"].eq(1) & event["artifact_context_flag"].eq(0)]
    if group_id == "q5_artifact_bad":
        return event[event["volume_q5_flag"].eq(1) & event["risk_bad_label"].eq(1) & event["artifact_context_flag"].eq(1)]
    raise ValueError(group_id)


def _summarize_mechanism(group_id: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "row_count": int(len(frame)),
        "risk_bad_count": int(pd.to_numeric(frame["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "risk_bad_rate": _rate(frame["risk_bad_label"]),
        "right_tail_count": int(pd.to_numeric(frame["right_tail_label"], errors="coerce").fillna(0).sum()),
        "right_tail_rate": _rate(frame["right_tail_label"]),
        "low_resolution_rate": _rate(frame["low_resolution_label"]),
        "event_time_missing_rate": _rate(frame["event_time_missing_label"]),
        "last_bar_degenerate_rate": _rate(frame["last_bar_degenerate_ohlc"]),
        "last_bar_single_tick_rate": _rate(frame["last_bar_single_tick"]),
        "degenerate_nonzero_gap_rate": _rate(frame["degenerate_nonzero_gap_flag"]),
        "last_bar_open_clock_rate": _rate(frame["last_bar_open_clock_flag"]),
        "artifact_context_rate": _rate(frame["artifact_context_flag"]),
        "clean_context_count": int(pd.to_numeric(frame["clean_context_flag"], errors="coerce").fillna(0).sum()),
        "stage244_strategy_rule_allowed": 0,
    }


def _build_mechanism_summary(event: pd.DataFrame) -> pd.DataFrame:
    group_ids = [
        "volume_q4",
        "volume_q5",
        "q4_bad",
        "q5_bad",
        "q4_tail",
        "q5_tail",
        "q5_clean_bad",
        "q5_artifact_bad",
    ]
    return pd.DataFrame([_summarize_mechanism(group_id, _group_frame(event, group_id)) for group_id in group_ids])


def _build_artifact_label_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    subset = event[event["volume_zscore_quintile"].isin([4, 5])].copy()
    for q, q_group in subset.groupby("volume_zscore_quintile", sort=True):
        for artifact_value, group in q_group.groupby("artifact_context_flag", sort=True):
            records.append(
                {
                    "group_id": f"volume_q{int(q)}_{'artifact' if artifact_value else 'clean'}",
                    "volume_quintile": int(q),
                    "artifact_context_flag": int(artifact_value),
                    "row_count": int(len(group)),
                    "risk_bad_count": int(group["risk_bad_label"].sum()),
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "right_tail_count": int(group["right_tail_label"].sum()),
                    "right_tail_rate": _rate(group["right_tail_label"]),
                    "low_resolution_rate": _rate(group["low_resolution_label"]),
                    "stage244_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_shape_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for group_id in ["volume_q4", "volume_q5", "q4_bad", "q5_bad", "q4_tail", "q5_tail", "q5_clean_bad"]:
        frame = _group_frame(event, group_id)
        records.append(
            {
                "group_id": group_id,
                "row_count": int(len(frame)),
                "volume_zscore_median": _median(frame["audit_value_volume_zscore_60m"]),
                "last_bar_volume_share_30bar_median": _median(frame["last_bar_volume_share_30bar"]),
                "last_bar_directional_return_bps_median": _median(frame["last_bar_directional_return_bps"]),
                "without_last_return_30bar_bps_median": _median(frame["without_last_return_30bar_bps"]),
                "directional_efficiency_30m_median": _median(frame["quality_value_directional_efficiency_30m"]),
                "aligned_bar_return_1m_median": _median(frame["quality_value_aligned_bar_return_1m"]),
                "stage244_strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _build_split_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in event.groupby(split_column, dropna=False):
            q4 = split_group[split_group["volume_q4_flag"].eq(1)]
            q5 = split_group[split_group["volume_q5_flag"].eq(1)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "q4_count": int(len(q4)),
                    "q5_count": int(len(q5)),
                    "q4_risk_bad_rate": _rate(q4["risk_bad_label"]),
                    "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
                    "q5_minus_q4_risk_bad_rate": _rate(q5["risk_bad_label"]) - _rate(q4["risk_bad_label"]),
                    "q4_right_tail_rate": _rate(q4["right_tail_label"]),
                    "q5_right_tail_rate": _rate(q5["right_tail_label"]),
                    "q5_minus_q4_right_tail_rate": _rate(q5["right_tail_label"]) - _rate(q4["right_tail_label"]),
                    "q4_artifact_context_rate": _rate(q4["artifact_context_flag"]),
                    "q5_artifact_context_rate": _rate(q5["artifact_context_flag"]),
                    "q5_minus_q4_artifact_context_rate": _rate(q5["artifact_context_flag"]) - _rate(q4["artifact_context_flag"]),
                    "valid_compare": int(len(q4) >= MIN_SPLIT_ROWS and len(q5) >= MIN_SPLIT_ROWS),
                    "stage244_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _load_bars(row: pd.Series) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    bars = pd.read_parquet(path)
    bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
    decision_ts = pd.Timestamp(row["decision_ts"])
    bars = bars[bars["bar_end_ts"].notna() & bars["bar_end_ts"].le(decision_ts)].sort_values("bar_end_ts").reset_index(drop=True)
    volume = pd.to_numeric(bars["volume"], errors="coerce").fillna(0.0)
    mean30 = volume.rolling(30, min_periods=30).mean()
    mean60 = volume.rolling(60, min_periods=60).mean()
    std60 = volume.rolling(60, min_periods=60).std(ddof=1)
    bars["stage244_volume_zscore_path"] = np.where(std60.eq(0), 0.0, (mean30 - mean60) / std60)
    return bars.tail(ATLAS_LOOKBACK_BARS).reset_index(drop=True)


def _select_atlas(event: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("q5_clean_bad", _group_frame(event, "q5_clean_bad")),
        ("q5_artifact_bad", _group_frame(event, "q5_artifact_bad")),
        ("q4_bad", _group_frame(event, "q4_bad")),
        ("q4_tail", _group_frame(event, "q4_tail")),
        ("q5_tail", _group_frame(event, "q5_tail")),
    ]
    frames: list[pd.DataFrame] = []
    for category, frame in specs:
        if frame.empty:
            continue
        picked = frame.sort_values("audit_value_volume_zscore_60m", ascending=False).head(6).copy()
        picked["atlas_category"] = category
        frames.append(picked)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage244 audits Q4 vs Q5 volume mechanism only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"Q4 bad={summary['q4_bad_count']}/{summary['q4_count']} artifact_bad={summary['q4_bad_artifact_context_rate']:.2f} | "
        f"Q5 bad={summary['q5_bad_count']}/{summary['q5_count']} clean_bad={summary['q5_clean_bad_count']} | true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_flag_rates(mechanism: pd.DataFrame) -> None:
    plot = mechanism[mechanism["group_id"].isin(["volume_q4", "volume_q5"])].set_index("group_id")
    cols = [
        "low_resolution_rate",
        "event_time_missing_rate",
        "last_bar_degenerate_rate",
        "last_bar_single_tick_rate",
        "degenerate_nonzero_gap_rate",
        "last_bar_open_clock_rate",
        "artifact_context_rate",
    ]
    fig, ax = plt.subplots(figsize=(12, 5.8))
    x = np.arange(len(cols))
    width = 0.35
    ax.bar(x - width / 2, plot.loc["volume_q4", cols], width, label="volume_q4", color="#1f77b4")
    ax.bar(x + width / 2, plot.loc["volume_q5", cols], width, label="volume_q5", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels([col.replace("_rate", "").replace("_", "\n") for col in cols], fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Q4 vs Q5 mechanism flags; descriptive only")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(FLAG_RATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_artifact_label_rates(artifact_label: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    x = np.arange(len(artifact_label))
    width = 0.26
    ax.bar(x - width, artifact_label["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, artifact_label["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, artifact_label["low_resolution_rate"], width, label="low_resolution", color="#ff7f0e")
    ax.set_xticks(x)
    ax.set_xticklabels(artifact_label["group_id"], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Q4/Q5 clean-vs-artifact label rates")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in artifact_label.reset_index(drop=True).iterrows():
        ymax = max(row["risk_bad_rate"], row["right_tail_rate"], row["low_resolution_rate"])
        ax.text(idx, ymax + 0.025, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(ARTIFACT_LABEL_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_shape_medians(shape: pd.DataFrame) -> None:
    cols = [
        "last_bar_volume_share_30bar_median",
        "last_bar_directional_return_bps_median",
        "without_last_return_30bar_bps_median",
        "directional_efficiency_30m_median",
    ]
    titles = [
        "last bar volume share",
        "last bar directional return bps",
        "without-last 30bar return bps",
        "directional efficiency 30m",
    ]
    plot = shape[shape["group_id"].isin(["volume_q4", "volume_q5", "q4_bad", "q5_bad", "q4_tail", "q5_tail"])].copy()
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5))
    for ax, col, title in zip(axes.flat, cols, titles):
        ax.bar(plot["group_id"], plot[col], color="#1f77b4")
        ax.axhline(0, color="#111111", linewidth=0.8)
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Q4/Q5 path-shape medians; not a threshold scan", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(SHAPE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split_delta(split: pd.DataFrame) -> None:
    subset = split[split["split_type"].isin(["year", "exchange"])].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    pivot = subset.set_index("split_label")[
        ["q5_minus_q4_risk_bad_rate", "q5_minus_q4_right_tail_rate", "q5_minus_q4_artifact_context_rate"]
    ]
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted(
        [idx for idx in pivot.index if idx.startswith("exchange=")]
    )
    pivot = pivot.reindex(order)
    fig, ax = plt.subplots(figsize=(8.5, max(4.8, 0.38 * len(pivot))))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdBu_r", vmin=-0.6, vmax=0.6)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(["risk Q5-Q4", "tail Q5-Q4", "artifact Q5-Q4"], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Q5 minus Q4 by split; red risk/artifact worse, red tail better")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:+.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(event: pd.DataFrame) -> None:
    subset = event[event["volume_zscore_quintile"].isin([4, 5])].copy()
    colors = np.where(subset["risk_bad_label"].eq(1), "#d62728", np.where(subset["right_tail_label"].eq(1), "#2ca02c", "#1f77b4"))
    markers = np.where(subset["volume_zscore_quintile"].eq(5), "Q5", "Q4")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharex=True)
    for q, marker in [(4, "o"), (5, "^")]:
        mask = subset["volume_zscore_quintile"].eq(q)
        axes[0].scatter(
            subset.loc[mask, "audit_value_volume_zscore_60m"],
            subset.loc[mask, "last_bar_volume_share_30bar"],
            c=colors[mask.to_numpy()],
            s=55,
            marker=marker,
            alpha=0.78,
            edgecolor="white",
            linewidth=0.4,
            label=f"Q{q}",
        )
        axes[1].scatter(
            subset.loc[mask, "audit_value_volume_zscore_60m"],
            subset.loc[mask, "last_bar_directional_return_bps"],
            c=colors[mask.to_numpy()],
            s=55,
            marker=marker,
            alpha=0.78,
            edgecolor="white",
            linewidth=0.4,
            label=f"Q{q}",
        )
    axes[0].set_ylabel("last_bar_volume_share_30bar")
    axes[0].set_title("Volume z-score vs terminal volume concentration")
    axes[1].set_ylabel("last_bar_directional_return_bps")
    axes[1].set_title("Volume z-score vs terminal price jump")
    for ax in axes:
        ax.axhline(0, color="#111111", linewidth=0.8)
        ax.grid(alpha=0.25)
        ax.set_xlabel("volume_zscore_60m")
        ax.legend(loc="best", fontsize=8)
    fig.suptitle("Stage244 scatter; red=risk_bad, green=right_tail, marker=Q4/Q5", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(selected: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if selected.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    rows_out: list[dict[str, Any]] = []
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
                bars = _load_bars(row)
                sign = 1.0 if str(row["direction"]).lower() != "short" else -1.0
                close = pd.to_numeric(bars["close"], errors="coerce")
                y = sign * (close / close.iloc[0] - 1.0) * 10000.0 if len(close) and close.iloc[0] != 0 else pd.Series([0.0] * len(close))
                x = np.arange(-len(y) + 1, 1)
                ax.plot(x, y, color="#1f77b4", linewidth=1.15)
                ax.axhline(0, color="#111111", linewidth=0.7, alpha=0.7)
                ax.axvline(0, color="#d62728", linewidth=0.8, alpha=0.8)
                ax.grid(alpha=0.2)
                ax.set_title(
                    f"{row['vt_symbol']} {row['direction']} VQ{int(row['volume_zscore_quintile'])} "
                    f"art={int(row['artifact_context_flag'])} risk={int(row['risk_bad_label'])} tail={int(row['right_tail_label'])}",
                    fontsize=8,
                )
                ax.tick_params(axis="both", labelsize=7)
                ax2 = ax.twinx()
                z = pd.to_numeric(bars["stage244_volume_zscore_path"], errors="coerce")
                ax2.plot(x, z, color="#ff7f0e", linewidth=0.9, alpha=0.85)
                ax2.axhline(0, color="#ff7f0e", linewidth=0.6, alpha=0.45)
                ax2.tick_params(axis="y", labelsize=6, colors="#ff7f0e")
                ax2.set_ylabel("vol z", fontsize=6, color="#ff7f0e")
                subtitle = (
                    f"z={float(row['audit_value_volume_zscore_60m']):+.3f}; "
                    f"lastRet={float(row['last_bar_directional_return_bps']):+.1f}bp; "
                    f"volShare={float(row['last_bar_volume_share_30bar']):.3f}"
                )
                ax.text(0.01, 0.02, subtitle, transform=ax.transAxes, fontsize=7, va="bottom")
                rows_out.append(
                    {
                        "atlas_page": page,
                        "panel": panel_idx + 1,
                        "atlas_category": category,
                        "request_id": row["request_id"],
                        "vt_symbol": row["vt_symbol"],
                        "decision_ts": row["decision_ts"],
                        "direction": row["direction"],
                        "volume_zscore_quintile": int(row["volume_zscore_quintile"]),
                        "artifact_context_flag": int(row["artifact_context_flag"]),
                        "volume_zscore_60m": float(row["audit_value_volume_zscore_60m"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "last_bar_volume_share_30bar": float(row["last_bar_volume_share_30bar"]),
                        "last_bar_directional_return_bps": float(row["last_bar_directional_return_bps"]),
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page)).relative_to(REPO_DIR)),
                    }
                )
            fig.suptitle(f"Stage244 {category}: blue=directional price path, orange=rolling volume z-score path", fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(rows_out)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage243_event_exists", int(STAGE243_EVENT_IN.exists()), "Stage243 event volume audit exists"),
        ("stage241_event_exists", int(STAGE241_EVENT_IN.exists()), "Stage241 artifact audit exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists"),
        ("event_row_count_219", int(summary["event_mechanism_row_count"] == 219), "219 mechanism rows"),
        ("q4_bad_all_artifact", int(summary["q4_clean_bad_count"] == 0 and summary["q4_bad_count"] > 0), "Q4 bad cases are artifact-context only"),
        ("q5_has_clean_bad", int(summary["q5_clean_bad_count"] > 0), "Q5 has clean-context bad cases"),
        ("q5_bad_not_explained_by_artifact_only", int(summary["q5_bad_artifact_context_rate"] < 1.0), "Q5 bad is not fully explained by artifact context"),
        ("strategy_rule_created", 0, "no strategy rule created"),
        ("true_engine_run", 0, "no true engine run"),
        ("ab_triggered", 0, "no A/B triggered"),
        ("official_config_changed", 0, "official config untouched"),
        ("order_api_called", 0, "no order API call"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": passed, "description": description} for gate_id, passed, description in rows])


def _write_report(
    summary: dict[str, Any],
    mechanism: pd.DataFrame,
    artifact_label: pd.DataFrame,
    shape: pd.DataFrame,
    split: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    split_view = split[
        [
            "split_type",
            "split_value",
            "q4_count",
            "q5_count",
            "q5_minus_q4_risk_bad_rate",
            "q5_minus_q4_right_tail_rate",
            "q5_minus_q4_artifact_context_rate",
            "valid_compare",
        ]
    ].head(16)
    report = f"""# {STAGE} Volume Q4-vs-Q5 Mechanism Audit

## Decision

- decision: `{summary['decision']}`
- event_mechanism_row_count: `{summary['event_mechanism_row_count']}`
- q4_bad_count: `{summary['q4_bad_count']}`
- q4_clean_bad_count: `{summary['q4_clean_bad_count']}`
- q4_bad_artifact_context_rate: `{summary['q4_bad_artifact_context_rate']:.6f}`
- q5_bad_count: `{summary['q5_bad_count']}`
- q5_clean_bad_count: `{summary['q5_clean_bad_count']}`
- q5_bad_artifact_context_rate: `{summary['q5_bad_artifact_context_rate']:.6f}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- Merge Stage243 volume audit with Stage241 last-bar artifact audit by `request_id`.
- Fixed comparison only: `volume_q4` vs `volume_q5`; no threshold scan and no Q4 promotion.
- Artifact context is descriptive: low resolution, event-time missing, degenerate/single-tick last bar, degenerate nonzero gap, or open-clock last bar.
- This stage checks whether Q5 risk rebound is merely an artifact.

## Mechanism Summary

{_md_table(mechanism, max_rows=None)}

## Artifact Label Summary

{_md_table(artifact_label, max_rows=None)}

## Path Shape Summary

{_md_table(shape, max_rows=None)}

## Split Summary

{_md_table(split_view, max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Atlas Manifest Sample

{_md_table(atlas_manifest.head(12), max_rows=None)}

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{FLAG_RATE_CHART_OUT.relative_to(REPO_DIR)}`
- `{ARTIFACT_LABEL_CHART_OUT.relative_to(REPO_DIR)}`
- `{SHAPE_CHART_OUT.relative_to(REPO_DIR)}`
- `{SPLIT_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{SCATTER_OUT.relative_to(REPO_DIR)}`
- atlas_pages: `{summary['atlas_page_count']}`
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    event = _prepare_event(_read_csv(STAGE243_EVENT_IN), _read_csv(STAGE241_EVENT_IN))
    mechanism = _build_mechanism_summary(event)
    artifact_label = _build_artifact_label_summary(event)
    shape = _build_shape_summary(event)
    split = _build_split_summary(event)
    atlas_selected = _select_atlas(event)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_selected)

    q4 = _group_frame(event, "volume_q4")
    q5 = _group_frame(event, "volume_q5")
    q4_bad = _group_frame(event, "q4_bad")
    q5_bad = _group_frame(event, "q5_bad")
    q4_tail = _group_frame(event, "q4_tail")
    q5_tail = _group_frame(event, "q5_tail")
    q4_clean_bad_count = int(q4_bad["clean_context_flag"].sum())
    q5_clean_bad_count = int(q5_bad["clean_context_flag"].sum())
    decision = (
        "stage244_volume_q5_risk_rebound_not_artifact_only_blocks_q4_or_q5_rule_no_true_engine"
        if q5_clean_bad_count > 0
        else "stage244_volume_q5_risk_rebound_artifact_explained_watch_only_no_true_engine"
    )

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_mechanism_row_count": int(len(event)),
        "q4_count": int(len(q4)),
        "q4_risk_bad_rate": _rate(q4["risk_bad_label"]),
        "q4_bad_count": int(q4["risk_bad_label"].sum()),
        "q4_tail_count": int(q4["right_tail_label"].sum()),
        "q4_tail_rate": _rate(q4["right_tail_label"]),
        "q4_artifact_context_rate": _rate(q4["artifact_context_flag"]),
        "q4_bad_artifact_context_rate": _rate(q4_bad["artifact_context_flag"]),
        "q4_clean_count": int(q4["clean_context_flag"].sum()),
        "q4_clean_bad_count": q4_clean_bad_count,
        "q4_clean_bad_rate": _rate(q4[q4["clean_context_flag"].eq(1)]["risk_bad_label"]),
        "q4_tail_artifact_context_rate": _rate(q4_tail["artifact_context_flag"]),
        "q5_count": int(len(q5)),
        "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
        "q5_bad_count": int(q5["risk_bad_label"].sum()),
        "q5_tail_count": int(q5["right_tail_label"].sum()),
        "q5_tail_rate": _rate(q5["right_tail_label"]),
        "q5_artifact_context_rate": _rate(q5["artifact_context_flag"]),
        "q5_bad_artifact_context_rate": _rate(q5_bad["artifact_context_flag"]),
        "q5_clean_count": int(q5["clean_context_flag"].sum()),
        "q5_clean_bad_count": q5_clean_bad_count,
        "q5_clean_bad_rate": _rate(q5[q5["clean_context_flag"].eq(1)]["risk_bad_label"]),
        "q5_tail_artifact_context_rate": _rate(q5_tail["artifact_context_flag"]),
        "q5_minus_q4_risk_bad_rate": _rate(q5["risk_bad_label"]) - _rate(q4["risk_bad_label"]),
        "q5_minus_q4_tail_rate": _rate(q5["right_tail_label"]) - _rate(q4["right_tail_label"]),
        "q5_minus_q4_artifact_context_rate": _rate(q5["artifact_context_flag"]) - _rate(q4["artifact_context_flag"]),
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
        "visual_file_count": 6 + int(len(atlas_paths)),
    }
    gate_status = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(event, EVENT_OUT)
    _write_csv(mechanism, MECHANISM_SUMMARY_OUT)
    _write_csv(artifact_label, ARTIFACT_LABEL_OUT)
    _write_csv(shape, SHAPE_SUMMARY_OUT)
    _write_csv(split, SPLIT_SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)

    _plot_official_path(curve, summary)
    _plot_flag_rates(mechanism)
    _plot_artifact_label_rates(artifact_label)
    _plot_shape_medians(shape)
    _plot_split_delta(split)
    _plot_scatter(event)
    _write_report(summary, mechanism, artifact_label, shape, split, atlas_manifest, gate_status)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
