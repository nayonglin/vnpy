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

import stage245_realized_volatility_counterexample_audit as shared


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage246"
MODEL_TAG = "stage246_turnover_vwap_gap_counterexample_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage246_turnover_vwap_gap_counterexample_audit"

CURVE_IN = shared.CURVE_IN
STAGE239_JOINED_IN = shared.STAGE239_JOINED_IN
STAGE239_FEATURE_SUMMARY_IN = shared.STAGE239_FEATURE_SUMMARY_IN
STAGE241_EVENT_IN = shared.STAGE241_EVENT_IN

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_vwap_gap_audit_{MODEL_TAG}.csv"
QUINTILE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quintile_summary_{MODEL_TAG}.csv"
GROUP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_summary_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q3_q5_vs_extreme_split_summary_{MODEL_TAG}.csv"
JOINT_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_vwap_volume_joint_matrix_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
QUINTILE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aligned_vwap_gap_quintile_label_rates_{MODEL_TAG}.png"
GROUP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixed_vwap_gap_group_label_rates_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q2_q4_q5_minus_q3_split_delta_{MODEL_TAG}.png"
JOINT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_vwap_gap_volume_joint_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_vwap_gap_context_scatter_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

ATLAS_LOOKBACK_BARS = 120
MIN_SPLIT_ROWS = 4


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    return shared._read_csv(path, required=required)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    shared._write_csv(frame, path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    shared._write_json(path, payload)


def _json_safe(value: Any) -> Any:
    return shared._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return shared._md_table(frame, max_rows=max_rows)


def _rate(series: pd.Series) -> float:
    return shared._rate(series)


def _median(series: pd.Series) -> float:
    return shared._median(series)


def _load_curve() -> pd.DataFrame:
    return shared._load_curve()


def _turnover_multiplier_proxy(bars: pd.DataFrame) -> float:
    denom = pd.to_numeric(bars["close"], errors="coerce") * pd.to_numeric(bars["volume"], errors="coerce")
    ratio = pd.to_numeric(bars["turnover"], errors="coerce") / denom.replace(0, np.nan)
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    ratio = ratio[ratio > 0]
    return np.nan if ratio.empty else float(ratio.median())


def _prepare_event(joined: pd.DataFrame, artifact: pd.DataFrame) -> pd.DataFrame:
    required = [
        "request_id",
        "exchange",
        "vt_symbol",
        "decision_ts",
        "direction",
        "filtered_source_file",
        "candidate_turnover_vwap_gap_30m",
        "audit_value_aligned_turnover_vwap_gap_30m",
        "quality_value_aligned_turnover_vwap_gap_30m",
        "quality_quintile_aligned_turnover_vwap_gap_30m",
        "candidate_volume_zscore_60m",
        "audit_value_volume_zscore_60m",
        "quality_quintile_volume_zscore_60m",
        "quality_quintile_directional_efficiency_30m",
        "quality_value_directional_efficiency_30m",
        "risk_bad_label",
        "right_tail_label",
        "ordinary_clean_label",
        "low_resolution_label",
        "event_time_missing_label",
    ]
    missing = [column for column in required if column not in joined.columns]
    if missing:
        raise RuntimeError(f"missing Stage239 columns: {missing}")
    artifact_cols = [
        "request_id",
        "last_bar_degenerate_ohlc",
        "last_bar_single_tick",
        "degenerate_nonzero_gap_flag",
        "last_bar_open_clock_flag",
        "last_bar_volume_share_30bar",
        "last_bar_directional_return_bps",
        "without_last_return_30bar_bps",
    ]
    missing_artifact = [column for column in artifact_cols if column not in artifact.columns]
    if missing_artifact:
        raise RuntimeError(f"missing Stage241 artifact columns: {missing_artifact}")
    event = joined[required].merge(artifact[artifact_cols], on="request_id", how="left", validate="one_to_one")
    event["decision_ts"] = pd.to_datetime(event["decision_ts"], errors="coerce")
    event["decision_year"] = event["decision_ts"].dt.year.astype("Int64")
    numeric_cols = [
        "candidate_turnover_vwap_gap_30m",
        "audit_value_aligned_turnover_vwap_gap_30m",
        "quality_value_aligned_turnover_vwap_gap_30m",
        "candidate_volume_zscore_60m",
        "audit_value_volume_zscore_60m",
        "quality_value_directional_efficiency_30m",
        "last_bar_volume_share_30bar",
        "last_bar_directional_return_bps",
        "without_last_return_30bar_bps",
    ]
    for column in numeric_cols:
        event[column] = pd.to_numeric(event[column], errors="coerce")
    int_cols = [
        "quality_quintile_aligned_turnover_vwap_gap_30m",
        "quality_quintile_volume_zscore_60m",
        "quality_quintile_directional_efficiency_30m",
        "risk_bad_label",
        "right_tail_label",
        "ordinary_clean_label",
        "low_resolution_label",
        "event_time_missing_label",
        "last_bar_degenerate_ohlc",
        "last_bar_single_tick",
        "degenerate_nonzero_gap_flag",
        "last_bar_open_clock_flag",
    ]
    for column in int_cols:
        event[column] = pd.to_numeric(event[column], errors="coerce").fillna(0).astype(int)
    event["aligned_vwap_gap_quintile"] = event["quality_quintile_aligned_turnover_vwap_gap_30m"].astype(int)
    event["volume_zscore_quintile"] = event["quality_quintile_volume_zscore_60m"].astype(int)
    event["efficiency_quintile"] = event["quality_quintile_directional_efficiency_30m"].astype(int)
    event["favorable_gap_q4q5_flag"] = event["aligned_vwap_gap_quintile"].ge(4).astype(int)
    event["adverse_gap_q1q2_flag"] = event["aligned_vwap_gap_quintile"].le(2).astype(int)
    event["neutral_gap_q3_flag"] = event["aligned_vwap_gap_quintile"].eq(3).astype(int)
    event["artifact_context_flag"] = (
        event["low_resolution_label"].eq(1)
        | event["event_time_missing_label"].eq(1)
        | event["last_bar_degenerate_ohlc"].eq(1)
        | event["last_bar_single_tick"].eq(1)
        | event["degenerate_nonzero_gap_flag"].eq(1)
        | event["last_bar_open_clock_flag"].eq(1)
    ).astype(int)
    event["clean_context_flag"] = event["artifact_context_flag"].eq(0).astype(int)
    event["stage246_strategy_rule_allowed"] = 0
    event["stage246_true_engine_allowed"] = 0
    return event


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
        "low_resolution_count": int(pd.to_numeric(frame["low_resolution_label"], errors="coerce").fillna(0).sum()),
        "low_resolution_rate": _rate(frame["low_resolution_label"]),
        "event_time_missing_rate": _rate(frame["event_time_missing_label"]),
        "artifact_context_rate": _rate(frame["artifact_context_flag"]),
        "clean_context_count": int(pd.to_numeric(frame["clean_context_flag"], errors="coerce").fillna(0).sum()),
        "aligned_turnover_vwap_gap_30m_median": _median(frame["audit_value_aligned_turnover_vwap_gap_30m"]),
        "raw_turnover_vwap_gap_30m_median": _median(frame["candidate_turnover_vwap_gap_30m"]),
        "volume_zscore_60m_median": _median(frame["audit_value_volume_zscore_60m"]),
        "directional_efficiency_30m_median": _median(frame["quality_value_directional_efficiency_30m"]),
        "stage246_strategy_rule_allowed": 0,
    }


def _build_quintile_summary(event: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for q in range(1, 6):
        group = event[event["aligned_vwap_gap_quintile"].eq(q)]
        row = _summarize_group(f"aligned_vwap_gap_q{q}", group)
        row["aligned_vwap_gap_quintile"] = q
        rows.append(row)
    return pd.DataFrame(rows)


def _build_group_summary(event: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("q1_strong_adverse_gap", event[event["aligned_vwap_gap_quintile"].eq(1)]),
        ("q2_mild_adverse_gap", event[event["aligned_vwap_gap_quintile"].eq(2)]),
        ("q3_neutral_gap", event[event["aligned_vwap_gap_quintile"].eq(3)]),
        ("q4_mild_favorable_gap", event[event["aligned_vwap_gap_quintile"].eq(4)]),
        ("q5_strong_favorable_gap", event[event["aligned_vwap_gap_quintile"].eq(5)]),
        ("favorable_gap_q4q5", event[event["favorable_gap_q4q5_flag"].eq(1)]),
        ("adverse_gap_q1q2", event[event["adverse_gap_q1q2_flag"].eq(1)]),
        ("q2_bad", event[event["aligned_vwap_gap_quintile"].eq(2) & event["risk_bad_label"].eq(1)]),
        ("q3_tail", event[event["aligned_vwap_gap_quintile"].eq(3) & event["right_tail_label"].eq(1)]),
        ("q4_bad", event[event["aligned_vwap_gap_quintile"].eq(4) & event["risk_bad_label"].eq(1)]),
        ("q5_bad", event[event["aligned_vwap_gap_quintile"].eq(5) & event["risk_bad_label"].eq(1)]),
        ("favorable_gap_bad", event[event["favorable_gap_q4q5_flag"].eq(1) & event["risk_bad_label"].eq(1)]),
    ]
    return pd.DataFrame([_summarize_group(group_id, frame) for group_id, frame in specs])


def _build_split_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in event.groupby(split_column, dropna=False):
            q2 = split_group[split_group["aligned_vwap_gap_quintile"].eq(2)]
            q3 = split_group[split_group["aligned_vwap_gap_quintile"].eq(3)]
            q4 = split_group[split_group["aligned_vwap_gap_quintile"].eq(4)]
            q5 = split_group[split_group["aligned_vwap_gap_quintile"].eq(5)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "row_count": int(len(split_group)),
                    "q2_count": int(len(q2)),
                    "q3_count": int(len(q3)),
                    "q4_count": int(len(q4)),
                    "q5_count": int(len(q5)),
                    "q2_risk_bad_rate": _rate(q2["risk_bad_label"]),
                    "q3_risk_bad_rate": _rate(q3["risk_bad_label"]),
                    "q4_risk_bad_rate": _rate(q4["risk_bad_label"]),
                    "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
                    "q2_right_tail_rate": _rate(q2["right_tail_label"]),
                    "q3_right_tail_rate": _rate(q3["right_tail_label"]),
                    "q4_right_tail_rate": _rate(q4["right_tail_label"]),
                    "q5_right_tail_rate": _rate(q5["right_tail_label"]),
                    "q2_minus_q3_risk_bad_rate": _rate(q2["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
                    "q4_minus_q3_risk_bad_rate": _rate(q4["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
                    "q5_minus_q3_risk_bad_rate": _rate(q5["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
                    "q5_minus_q3_right_tail_rate": _rate(q5["right_tail_label"]) - _rate(q3["right_tail_label"]),
                    "q5_minus_q3_artifact_context_rate": _rate(q5["artifact_context_flag"]) - _rate(q3["artifact_context_flag"]),
                    "valid_q3_q5_compare": int(len(q3) >= MIN_SPLIT_ROWS and len(q5) >= MIN_SPLIT_ROWS),
                    "stage246_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_joint_matrix(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for qg in range(1, 6):
        for qv in range(1, 6):
            group = event[event["aligned_vwap_gap_quintile"].eq(qg) & event["volume_zscore_quintile"].eq(qv)]
            records.append(
                {
                    "aligned_vwap_gap_quintile": qg,
                    "volume_zscore_quintile": qv,
                    "row_count": int(len(group)),
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "right_tail_rate": _rate(group["right_tail_label"]),
                    "artifact_context_rate": _rate(group["artifact_context_flag"]),
                    "stage246_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _load_bars(row: pd.Series) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    bars = pd.read_parquet(path)
    bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
    decision_ts = pd.Timestamp(row["decision_ts"])
    bars = bars[bars["bar_end_ts"].notna() & bars["bar_end_ts"].le(decision_ts)].sort_values("bar_end_ts").reset_index(drop=True)
    multiplier = _turnover_multiplier_proxy(bars)
    close = pd.to_numeric(bars["close"], errors="coerce")
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    turnover = pd.to_numeric(bars["turnover"], errors="coerce")
    denom = volume.rolling(30, min_periods=30).sum() * multiplier
    vwap = turnover.rolling(30, min_periods=30).sum() / denom.replace(0, np.nan)
    raw_gap = close / vwap.replace(0, np.nan) - 1.0
    sign = 1.0 if str(row["direction"]).lower() != "short" else -1.0
    bars["stage246_aligned_vwap_gap_path"] = sign * raw_gap
    return bars.tail(ATLAS_LOOKBACK_BARS).reset_index(drop=True)


def _select_atlas(event: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("q3_tail", event.query("aligned_vwap_gap_quintile == 3 and right_tail_label == 1")),
        ("q2_bad", event.query("aligned_vwap_gap_quintile == 2 and risk_bad_label == 1")),
        ("q4_bad", event.query("aligned_vwap_gap_quintile == 4 and risk_bad_label == 1")),
        ("q5_bad", event.query("aligned_vwap_gap_quintile == 5 and risk_bad_label == 1")),
        ("favorable_gap_bad", event.query("aligned_vwap_gap_quintile >= 4 and risk_bad_label == 1")),
    ]
    frames: list[pd.DataFrame] = []
    for category, frame in specs:
        if frame.empty:
            continue
        if "bad" in category:
            picked = frame.sort_values("audit_value_aligned_turnover_vwap_gap_30m", ascending=False).head(6).copy()
        else:
            picked = frame.sort_values("audit_value_aligned_turnover_vwap_gap_30m", ascending=True).head(6).copy()
        picked["atlas_category"] = category
        frames.append(picked)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage246 audits turnover_vwap_gap_30m only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"Q3 neutral risk={summary['q3_risk_bad_rate']:.3f} tail={summary['q3_right_tail_rate']:.3f} | "
        f"Q4 risk={summary['q4_risk_bad_rate']:.3f} | Q5 tail={summary['q5_right_tail_rate']:.3f} | true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_quintile_rates(quintile_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.8, 5.5))
    x = np.arange(len(quintile_summary))
    width = 0.22
    ax.bar(x - 1.5 * width, quintile_summary["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x - 0.5 * width, quintile_summary["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + 0.5 * width, quintile_summary["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
    ax.bar(x + 1.5 * width, quintile_summary["low_resolution_rate"], width, label="low_resolution", color="#ff7f0e")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{int(q)}" for q in quintile_summary["aligned_vwap_gap_quintile"]])
    ax.set_ylabel("rate")
    ax.set_title("aligned_turnover_vwap_gap_30m quintile label rates; Q5 strongest favorable gap")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in quintile_summary.reset_index(drop=True).iterrows():
        ymax = max(row["risk_bad_rate"], row["right_tail_rate"], row["ordinary_clean_rate"], row["low_resolution_rate"])
        ax.text(idx, ymax + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(QUINTILE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_group_rates(group_summary: pd.DataFrame) -> None:
    plot_groups = group_summary[group_summary["group_id"].isin(
        [
            "q1_strong_adverse_gap",
            "q2_mild_adverse_gap",
            "q3_neutral_gap",
            "q4_mild_favorable_gap",
            "q5_strong_favorable_gap",
            "favorable_gap_q4q5",
            "adverse_gap_q1q2",
        ]
    )].copy()
    fig, ax = plt.subplots(figsize=(12, 5.4))
    x = np.arange(len(plot_groups))
    width = 0.24
    ax.bar(x - width, plot_groups["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, plot_groups["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, plot_groups["artifact_context_rate"], width, label="artifact_context", color="#ff7f0e")
    ax.set_xticks(x)
    ax.set_xticklabels(plot_groups["group_id"], rotation=22, ha="right", fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Fixed VWAP-gap groups; favorable price acceptance is not monotonic")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in plot_groups.reset_index(drop=True).iterrows():
        ymax = max(row["risk_bad_rate"], row["right_tail_rate"], row["artifact_context_rate"])
        ax.text(idx, ymax + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GROUP_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split_delta(split_summary: pd.DataFrame) -> None:
    subset = split_summary[split_summary["split_type"].isin(["year", "exchange"])].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    pivot = subset.set_index("split_label")[
        [
            "q2_minus_q3_risk_bad_rate",
            "q4_minus_q3_risk_bad_rate",
            "q5_minus_q3_risk_bad_rate",
            "q5_minus_q3_right_tail_rate",
            "q5_minus_q3_artifact_context_rate",
        ]
    ]
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted(
        [idx for idx in pivot.index if idx.startswith("exchange=")]
    )
    pivot = pivot.reindex(order)
    fig, ax = plt.subplots(figsize=(9.5, max(4.8, 0.38 * len(pivot))))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdBu_r", vmin=-0.6, vmax=0.6)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(["risk Q2-Q3", "risk Q4-Q3", "risk Q5-Q3", "tail Q5-Q3", "artifact Q5-Q3"], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Extreme VWAP-gap buckets minus neutral Q3 by split")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:+.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_joint_heatmap(joint: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, value_col, title, cmap in [
        (axes[0], "risk_bad_rate", "risk_bad by VWAP-gap Q / volume-z Q", "Reds"),
        (axes[1], "right_tail_rate", "right_tail by VWAP-gap Q / volume-z Q", "Greens"),
    ]:
        pivot = joint.pivot(index="volume_zscore_quintile", columns="aligned_vwap_gap_quintile", values=value_col)
        count = joint.pivot(index="volume_zscore_quintile", columns="aligned_vwap_gap_quintile", values="row_count")
        data = pivot.to_numpy(dtype=float)
        vmax = max(0.35, np.nanmax(data) if np.isfinite(data).any() else 0.35)
        image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([f"GQ{col}" for col in pivot.columns])
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels([f"VQ{idx}" for idx in pivot.index])
        ax.set_xlabel("aligned_turnover_vwap_gap_30m quintile")
        ax.set_ylabel("volume_zscore_60m quintile")
        ax.set_title(title)
        for y in range(data.shape[0]):
            for x in range(data.shape[1]):
                value = data[y, x]
                n = int(count.to_numpy()[y, x])
                if np.isfinite(value):
                    ax.text(x, y, f"{value:.2f}\nn={n}", ha="center", va="center", fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(JOINT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(event: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharex=True)
    colors = np.where(event["risk_bad_label"].eq(1), "#d62728", np.where(event["right_tail_label"].eq(1), "#2ca02c", "#1f77b4"))
    sizes = np.where(event["right_tail_label"].eq(1), 58, 24)
    markers = {2: "o", 3: "s", 4: "D", 5: "^"}
    for q, marker in markers.items():
        mask = event["aligned_vwap_gap_quintile"].eq(q)
        for ax, ycol in [(axes[0], "audit_value_volume_zscore_60m"), (axes[1], "quality_value_directional_efficiency_30m")]:
            ax.scatter(
                event.loc[mask, "audit_value_aligned_turnover_vwap_gap_30m"],
                event.loc[mask, ycol],
                c=colors[mask.to_numpy()],
                s=sizes[mask.to_numpy()],
                marker=marker,
                alpha=0.78,
                edgecolor="white",
                linewidth=0.4,
                label=f"GQ{q}" if ycol == "audit_value_volume_zscore_60m" else None,
            )
    axes[0].set_ylabel("volume_zscore_60m")
    axes[0].set_title("VWAP gap vs volume surprise")
    axes[1].set_ylabel("directional_efficiency_30m")
    axes[1].set_title("VWAP gap vs directional efficiency")
    for ax in axes:
        ax.axvline(0, color="#111111", linewidth=0.7, alpha=0.7)
        ax.set_xlabel("aligned_turnover_vwap_gap_30m")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle("Stage246 scatter; red=risk_bad, green=right_tail; marker highlights GQ2/GQ3/GQ4/GQ5", fontsize=12)
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
                close = pd.to_numeric(bars["close"], errors="coerce")
                valid_close = close.dropna()
                if valid_close.empty or float(valid_close.iloc[0]) == 0:
                    y = pd.Series([0.0] * len(close))
                else:
                    sign = 1.0 if str(row["direction"]).lower() != "short" else -1.0
                    y = sign * (close / float(valid_close.iloc[0]) - 1.0) * 10000.0
                x = np.arange(-len(y) + 1, 1)
                ax.plot(x, y, color="#1f77b4", linewidth=1.15)
                ax.axhline(0, color="#111111", linewidth=0.7, alpha=0.7)
                ax.axvline(0, color="#d62728", linewidth=0.8, alpha=0.8)
                ax.grid(alpha=0.2)
                ax.set_title(
                    f"{row['vt_symbol']} {row['direction']} GQ{int(row['aligned_vwap_gap_quintile'])} "
                    f"risk={int(row['risk_bad_label'])} tail={int(row['right_tail_label'])}",
                    fontsize=8,
                )
                ax.tick_params(axis="both", labelsize=7)
                ax2 = ax.twinx()
                gap = pd.to_numeric(bars["stage246_aligned_vwap_gap_path"], errors="coerce")
                ax2.plot(x, gap, color="#ff7f0e", linewidth=0.9, alpha=0.85)
                ax2.axhline(0, color="#ff7f0e", linewidth=0.6, alpha=0.45)
                ax2.tick_params(axis="y", labelsize=6, colors="#ff7f0e")
                ax2.set_ylabel("aligned gap", fontsize=6, color="#ff7f0e")
                subtitle = (
                    f"gap={float(row['audit_value_aligned_turnover_vwap_gap_30m']):+.4f}; "
                    f"volQ={int(row['volume_zscore_quintile'])}; art={int(row['artifact_context_flag'])}"
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
                        "aligned_vwap_gap_quintile": int(row["aligned_vwap_gap_quintile"]),
                        "audit_value_aligned_turnover_vwap_gap_30m": float(row["audit_value_aligned_turnover_vwap_gap_30m"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "artifact_context_flag": int(row["artifact_context_flag"]),
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                    }
                )
            fig.suptitle(
                f"Stage246 {category}: blue=directional price path, orange=aligned VWAP-gap path",
                fontsize=12,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(rows_out)


def _build_gate_status(summary: dict[str, Any], atlas_pages: list[Path]) -> pd.DataFrame:
    gates = [
        ("stage239_joined_exists", STAGE239_JOINED_IN.exists(), "Stage239 joined signal-label audit exists"),
        ("stage241_event_exists", STAGE241_EVENT_IN.exists(), "Stage241 artifact audit exists"),
        ("curve_exists", CURVE_IN.exists(), "official curve exists"),
        ("event_row_count_219", summary["event_vwap_gap_row_count"] == 219, "219 VWAP-gap rows"),
        ("q3_neutral_is_best_risk_bucket", summary["q3_risk_bad_rate"] < summary["q2_risk_bad_rate"] and summary["q3_risk_bad_rate"] < summary["q4_risk_bad_rate"], "neutral Q3 is the tempting risk bucket"),
        ("favorable_q4q5_not_better_than_q3", summary["favorable_gap_q4q5_risk_bad_rate"] > summary["q3_risk_bad_rate"], "favorable VWAP-gap aggregate does not beat Q3"),
        ("q5_has_bad_cases", summary["q5_risk_bad_count"] > 0, "strong favorable bucket still has bad cases"),
        ("q3_tail_not_enough", summary["q3_right_tail_rate"] < summary["q2_right_tail_rate"], "neutral Q3 does not dominate right tails"),
        ("strategy_rule_created", False, "no strategy rule created"),
        ("true_engine_run", False, "no true engine run"),
        ("ab_triggered", False, "no A/B triggered"),
        ("official_config_changed", False, "official config untouched"),
        ("order_api_called", False, "no order API call"),
        ("visual_files_nonempty", len(atlas_pages) > 0, "atlas pages generated"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": int(bool(passed)), "description": description} for gate_id, passed, description in gates])


def _write_report(
    summary: dict[str, Any],
    quintile_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    joint: pd.DataFrame,
    gate_status: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    lines = [
        "# Stage246 Turnover VWAP-Gap Counterexample Audit",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        f"- event_vwap_gap_row_count: `{summary['event_vwap_gap_row_count']}`",
        f"- q3_risk_bad_rate: `{summary['q3_risk_bad_rate']:.6f}`",
        f"- q2_risk_bad_rate: `{summary['q2_risk_bad_rate']:.6f}`",
        f"- q4_risk_bad_rate: `{summary['q4_risk_bad_rate']:.6f}`",
        f"- q5_risk_bad_rate: `{summary['q5_risk_bad_rate']:.6f}`",
        f"- favorable_gap_q4q5_risk_bad_rate: `{summary['favorable_gap_q4q5_risk_bad_rate']:.6f}`",
        "- strategy_rule_created: `0`",
        "- true_engine_run: `0`",
        "- ab_triggered: `0`",
        "",
        "## Method",
        "",
        "- Use Stage239 joined signal-label audit and Stage241 artifact audit.",
        "- Fixed quality quintile for `aligned_turnover_vwap_gap_30m`; Q5 means strongest favorable close-vs-VWAP gap in trade direction.",
        "- This stage checks whether price acceptance versus turnover VWAP is a universal low-risk/high-tail context.",
        "- No threshold scan, no Q3 or Q5 promotion, no true engine, no A/B.",
        "",
        "## Quintile Summary",
        "",
        _md_table(quintile_summary),
        "",
        "## Group Summary",
        "",
        _md_table(group_summary),
        "",
        "## Split Summary",
        "",
        _md_table(split_summary, max_rows=18),
        "",
        "## Joint Matrix Sample",
        "",
        _md_table(joint, max_rows=25),
        "",
        "## Gate Status",
        "",
        _md_table(gate_status),
        "",
        "## Atlas Manifest Sample",
        "",
        _md_table(atlas_manifest, max_rows=12),
        "",
        "## Visuals",
        "",
        f"- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- `{QUINTILE_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- `{GROUP_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- `{SPLIT_HEATMAP_OUT.relative_to(REPO_DIR)}`",
        f"- `{JOINT_HEATMAP_OUT.relative_to(REPO_DIR)}`",
        f"- `{SCATTER_OUT.relative_to(REPO_DIR)}`",
        f"- atlas_pages: `{summary['atlas_page_count']}`",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joined = _read_csv(STAGE239_JOINED_IN)
    artifact = _read_csv(STAGE241_EVENT_IN)
    curve = _load_curve()
    feature_summary = _read_csv(STAGE239_FEATURE_SUMMARY_IN, required=False)
    event = _prepare_event(joined, artifact)

    quintile_summary = _build_quintile_summary(event)
    group_summary = _build_group_summary(event)
    split_summary = _build_split_summary(event)
    joint = _build_joint_matrix(event)

    q2 = event[event["aligned_vwap_gap_quintile"].eq(2)]
    q3 = event[event["aligned_vwap_gap_quintile"].eq(3)]
    q4 = event[event["aligned_vwap_gap_quintile"].eq(4)]
    q5 = event[event["aligned_vwap_gap_quintile"].eq(5)]
    favorable = event[event["favorable_gap_q4q5_flag"].eq(1)]
    adverse = event[event["adverse_gap_q1q2_flag"].eq(1)]

    feature_row = feature_summary[feature_summary["audit_feature_id"].eq("aligned_turnover_vwap_gap_30m")]
    stage239_watch = int(feature_row["universal_structure_watch_only"].iloc[0]) if not feature_row.empty else 0

    selected = _select_atlas(event)
    atlas_pages, atlas_manifest = _plot_atlas(selected)
    visual_files = [PATH_CHART_OUT, QUINTILE_CHART_OUT, GROUP_CHART_OUT, SPLIT_HEATMAP_OUT, JOINT_HEATMAP_OUT, SCATTER_OUT] + atlas_pages

    decision = "stage246_aligned_turnover_vwap_gap_nonmonotonic_neutral_bucket_blocks_true_engine_no_rule"
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "event_vwap_gap_row_count": int(len(event)),
        "stage239_universal_structure_watch_only": stage239_watch,
        "q2_count": int(len(q2)),
        "q2_risk_bad_count": int(q2["risk_bad_label"].sum()),
        "q2_risk_bad_rate": _rate(q2["risk_bad_label"]),
        "q2_right_tail_count": int(q2["right_tail_label"].sum()),
        "q2_right_tail_rate": _rate(q2["right_tail_label"]),
        "q3_count": int(len(q3)),
        "q3_risk_bad_count": int(q3["risk_bad_label"].sum()),
        "q3_risk_bad_rate": _rate(q3["risk_bad_label"]),
        "q3_right_tail_count": int(q3["right_tail_label"].sum()),
        "q3_right_tail_rate": _rate(q3["right_tail_label"]),
        "q4_count": int(len(q4)),
        "q4_risk_bad_count": int(q4["risk_bad_label"].sum()),
        "q4_risk_bad_rate": _rate(q4["risk_bad_label"]),
        "q4_right_tail_count": int(q4["right_tail_label"].sum()),
        "q4_right_tail_rate": _rate(q4["right_tail_label"]),
        "q5_count": int(len(q5)),
        "q5_risk_bad_count": int(q5["risk_bad_label"].sum()),
        "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
        "q5_right_tail_count": int(q5["right_tail_label"].sum()),
        "q5_right_tail_rate": _rate(q5["right_tail_label"]),
        "favorable_gap_q4q5_count": int(len(favorable)),
        "favorable_gap_q4q5_risk_bad_count": int(favorable["risk_bad_label"].sum()),
        "favorable_gap_q4q5_risk_bad_rate": _rate(favorable["risk_bad_label"]),
        "favorable_gap_q4q5_right_tail_count": int(favorable["right_tail_label"].sum()),
        "favorable_gap_q4q5_right_tail_rate": _rate(favorable["right_tail_label"]),
        "adverse_gap_q1q2_count": int(len(adverse)),
        "adverse_gap_q1q2_risk_bad_rate": _rate(adverse["risk_bad_label"]),
        "adverse_gap_q1q2_right_tail_rate": _rate(adverse["right_tail_label"]),
        "q2_minus_q3_risk_bad_rate": _rate(q2["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
        "q4_minus_q3_risk_bad_rate": _rate(q4["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
        "q5_minus_q3_risk_bad_rate": _rate(q5["risk_bad_label"]) - _rate(q3["risk_bad_label"]),
        "q5_minus_q3_right_tail_rate": _rate(q5["right_tail_label"]) - _rate(q3["right_tail_label"]),
        "atlas_event_count": int(len(selected)),
        "atlas_page_count": int(len(atlas_pages)),
        "visual_file_count": int(len(visual_files)),
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
    }

    _plot_official_path(curve, summary)
    _plot_quintile_rates(quintile_summary)
    _plot_group_rates(group_summary)
    _plot_split_delta(split_summary)
    _plot_joint_heatmap(joint)
    _plot_scatter(event)

    gate_status = _build_gate_status(summary, atlas_pages)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_json(DECISION_OUT, summary)
    _write_csv(event, EVENT_OUT)
    _write_csv(quintile_summary, QUINTILE_SUMMARY_OUT)
    _write_csv(group_summary, GROUP_SUMMARY_OUT)
    _write_csv(split_summary, SPLIT_SUMMARY_OUT)
    _write_csv(joint, JOINT_MATRIX_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_report(summary, quintile_summary, group_summary, split_summary, joint, gate_status, atlas_manifest)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
