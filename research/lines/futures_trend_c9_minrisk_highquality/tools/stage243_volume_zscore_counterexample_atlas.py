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
STAGE = "Stage243"
MODEL_TAG = "stage243_volume_zscore_counterexample_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage243_volume_zscore_counterexample_atlas"

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
STAGE239_FEATURE_SUMMARY_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_feature_rank_correlation_audit_{STAGE239_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_volume_zscore_audit_{MODEL_TAG}.csv"
QUINTILE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quintile_summary_{MODEL_TAG}.csv"
GROUP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_summary_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_summary_{MODEL_TAG}.csv"
JOINT_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_efficiency_joint_matrix_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
QUINTILE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_quintile_label_rates_{MODEL_TAG}.png"
GROUP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_group_label_rates_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_high_low_split_delta_{MODEL_TAG}.png"
JOINT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_efficiency_joint_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_vs_price_context_scatter_{MODEL_TAG}.png"
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


def _rank_corr(left: pd.Series, right: pd.Series) -> float:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    mask = left_num.notna() & right_num.notna()
    if int(mask.sum()) < 3:
        return np.nan
    if left_num[mask].nunique(dropna=True) < 2 or right_num[mask].nunique(dropna=True) < 2:
        return np.nan
    return float(left_num[mask].rank(method="average").corr(right_num[mask].rank(method="average"), method="pearson"))


def _prepare_event(joined: pd.DataFrame) -> pd.DataFrame:
    event = joined.copy()
    required = [
        "audit_value_volume_zscore_60m",
        "quality_value_volume_zscore_60m",
        "quality_quintile_volume_zscore_60m",
        "quality_quintile_directional_efficiency_30m",
        "quality_value_aligned_bar_return_1m",
        "quality_value_directional_efficiency_30m",
        "risk_bad_label",
        "right_tail_label",
        "ordinary_clean_label",
        "low_resolution_label",
        "decision_ts",
        "direction",
        "filtered_source_file",
    ]
    missing = [column for column in required if column not in event.columns]
    if missing:
        raise RuntimeError(f"missing Stage239 columns: {missing}")
    event["decision_ts"] = pd.to_datetime(event["decision_ts"], errors="coerce")
    event["decision_year"] = event["decision_ts"].dt.year.astype("Int64")
    for column in [
        "audit_value_volume_zscore_60m",
        "quality_value_volume_zscore_60m",
        "quality_value_aligned_bar_return_1m",
        "quality_value_directional_efficiency_30m",
    ]:
        event[column] = pd.to_numeric(event[column], errors="coerce")
    for column in [
        "quality_quintile_volume_zscore_60m",
        "quality_quintile_directional_efficiency_30m",
        "risk_bad_label",
        "right_tail_label",
        "ordinary_clean_label",
        "low_resolution_label",
    ]:
        event[column] = pd.to_numeric(event[column], errors="coerce").astype("Int64")
    event["volume_zscore_quintile"] = event["quality_quintile_volume_zscore_60m"].astype("Int64")
    event["efficiency_quintile"] = event["quality_quintile_directional_efficiency_30m"].astype("Int64")
    event["high_volume_q4q5_flag"] = event["volume_zscore_quintile"].ge(4).fillna(False).astype(int)
    event["low_volume_q1q2_flag"] = event["volume_zscore_quintile"].le(2).fillna(False).astype(int)
    event["volume_group"] = np.select(
        [
            event["volume_zscore_quintile"].ge(4),
            event["volume_zscore_quintile"].le(2),
            event["volume_zscore_quintile"].eq(3),
        ],
        ["high_volume_q4q5", "low_volume_q1q2", "mid_volume_q3"],
        default="missing",
    )
    event["stage243_strategy_rule_allowed"] = 0
    event["stage243_true_engine_allowed"] = 0
    return event


def _summarize_group(group_id: str, frame: pd.DataFrame) -> dict[str, Any]:
    volume = pd.to_numeric(frame["audit_value_volume_zscore_60m"], errors="coerce")
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
        "volume_zscore_mean": float(volume.mean()) if volume.notna().any() else np.nan,
        "volume_zscore_median": float(volume.median()) if volume.notna().any() else np.nan,
        "stage243_strategy_rule_allowed": 0,
    }


def _build_quintile_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for quintile in range(1, 6):
        group = event[event["volume_zscore_quintile"].eq(quintile)]
        row = _summarize_group(f"volume_q{quintile}", group)
        row["quality_quintile"] = quintile
        records.append(row)
    return pd.DataFrame(records)


def _build_group_summary(event: pd.DataFrame) -> pd.DataFrame:
    order = [
        ("high_volume_q4q5", event[event["high_volume_q4q5_flag"].eq(1)]),
        ("low_volume_q1q2", event[event["low_volume_q1q2_flag"].eq(1)]),
        ("mid_volume_q3", event[event["volume_zscore_quintile"].eq(3)]),
        ("volume_q4", event[event["volume_zscore_quintile"].eq(4)]),
        ("volume_q5", event[event["volume_zscore_quintile"].eq(5)]),
    ]
    return pd.DataFrame([_summarize_group(group_id, frame) for group_id, frame in order])


def _build_split_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in event.groupby(split_column, dropna=False):
            high = split_group[split_group["high_volume_q4q5_flag"].eq(1)]
            low = split_group[split_group["low_volume_q1q2_flag"].eq(1)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "row_count": int(len(split_group)),
                    "high_count": int(len(high)),
                    "low_count": int(len(low)),
                    "high_risk_bad_rate": _rate(high["risk_bad_label"]),
                    "low_risk_bad_rate": _rate(low["risk_bad_label"]),
                    "high_right_tail_rate": _rate(high["right_tail_label"]),
                    "low_right_tail_rate": _rate(low["right_tail_label"]),
                    "high_low_resolution_rate": _rate(high["low_resolution_label"]),
                    "low_low_resolution_rate": _rate(low["low_resolution_label"]),
                    "valid_compare": int(len(high) >= MIN_SPLIT_ROWS and len(low) >= MIN_SPLIT_ROWS),
                    "stage243_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_joint_matrix(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for qv in range(1, 6):
        for qe in range(1, 6):
            group = event[event["volume_zscore_quintile"].eq(qv) & event["efficiency_quintile"].eq(qe)]
            records.append(
                {
                    "volume_quintile": qv,
                    "efficiency_quintile": qe,
                    "row_count": int(len(group)),
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "right_tail_rate": _rate(group["right_tail_label"]),
                    "ordinary_clean_rate": _rate(group["ordinary_clean_label"]),
                    "stage243_strategy_rule_allowed": 0,
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
    bars["stage243_volume_zscore_path"] = np.where(std60.eq(0), 0.0, (mean30 - mean60) / std60)
    return bars.tail(ATLAS_LOOKBACK_BARS).reset_index(drop=True)


def _select_atlas(event: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("q5_bad", event.query("volume_zscore_quintile == 5 and risk_bad_label == 1")),
        ("q5_tail", event.query("volume_zscore_quintile == 5 and right_tail_label == 1")),
        ("q4_tail", event.query("volume_zscore_quintile == 4 and right_tail_label == 1")),
        ("low_volume_tail_miss", event.query("volume_zscore_quintile <= 2 and right_tail_label == 1")),
        ("high_volume_low_resolution", event.query("volume_zscore_quintile >= 4 and low_resolution_label == 1")),
    ]
    frames: list[pd.DataFrame] = []
    for category, frame in specs:
        if frame.empty:
            continue
        if category == "low_volume_tail_miss":
            picked = frame.sort_values("audit_value_volume_zscore_60m", ascending=True).head(6).copy()
        else:
            picked = frame.sort_values("audit_value_volume_zscore_60m", ascending=False).head(6).copy()
        picked["atlas_category"] = category
        frames.append(picked)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage243 audits volume_zscore_60m only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"high_q4q5={summary['high_volume_count']} risk={summary['high_volume_risk_bad_rate']:.3f} "
        f"tail={summary['high_volume_right_tail_rate']:.3f} | "
        f"q5 risk={summary['q5_risk_bad_rate']:.3f} | true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_quintile_rates(quintile_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    x = np.arange(len(quintile_summary))
    width = 0.22
    ax.bar(x - 1.5 * width, quintile_summary["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x - 0.5 * width, quintile_summary["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + 0.5 * width, quintile_summary["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
    ax.bar(x + 1.5 * width, quintile_summary["low_resolution_rate"], width, label="low_resolution", color="#ff7f0e")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{int(q)}" for q in quintile_summary["quality_quintile"]])
    ax.set_ylabel("rate")
    ax.set_title("volume_zscore_60m quality quintile label rates")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in quintile_summary.reset_index(drop=True).iterrows():
        ymax = max(row["risk_bad_rate"], row["right_tail_rate"], row["ordinary_clean_rate"], row["low_resolution_rate"])
        ax.text(idx, ymax + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(QUINTILE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_group_rates(group_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.2))
    x = np.arange(len(group_summary))
    width = 0.24
    ax.bar(x - width, group_summary["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, group_summary["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, group_summary["low_resolution_rate"], width, label="low_resolution", color="#ff7f0e")
    ax.set_xticks(x)
    ax.set_xticklabels(group_summary["group_id"], rotation=22, ha="right", fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Fixed volume-zscore groups; Q4 and Q5 shown separately to expose non-monotonicity")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in group_summary.reset_index(drop=True).iterrows():
        ymax = max(row["risk_bad_rate"], row["right_tail_rate"], row["low_resolution_rate"])
        ax.text(idx, ymax + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GROUP_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split_delta(split_summary: pd.DataFrame) -> None:
    subset = split_summary[split_summary["split_type"].isin(["year", "exchange"])].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    subset["risk_delta_high_minus_low"] = subset["high_risk_bad_rate"] - subset["low_risk_bad_rate"]
    subset["tail_delta_high_minus_low"] = subset["high_right_tail_rate"] - subset["low_right_tail_rate"]
    subset["lowres_delta_high_minus_low"] = subset["high_low_resolution_rate"] - subset["low_low_resolution_rate"]
    pivot = subset.set_index("split_label")[
        ["risk_delta_high_minus_low", "tail_delta_high_minus_low", "lowres_delta_high_minus_low"]
    ]
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted(
        [idx for idx in pivot.index if idx.startswith("exchange=")]
    )
    pivot = pivot.reindex(order)
    fig, ax = plt.subplots(figsize=(8.4, max(4.8, 0.38 * len(pivot))))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(["risk high-low", "tail high-low", "lowres high-low"], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("High-volume minus low-volume by split; blue risk/lowres is better, red tail is better")
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
        (axes[0], "risk_bad_rate", "risk_bad by volume Q / efficiency Q", "Reds"),
        (axes[1], "right_tail_rate", "right_tail by volume Q / efficiency Q", "Greens"),
    ]:
        pivot = joint.pivot(index="efficiency_quintile", columns="volume_quintile", values=value_col)
        count = joint.pivot(index="efficiency_quintile", columns="volume_quintile", values="row_count")
        data = pivot.to_numpy(dtype=float)
        image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=0, vmax=max(0.35, np.nanmax(data) if np.isfinite(data).any() else 0.35))
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([f"VQ{col}" for col in pivot.columns])
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels([f"EQ{idx}" for idx in pivot.index])
        ax.set_xlabel("volume_zscore_60m quintile")
        ax.set_ylabel("directional_efficiency_30m quintile")
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
    x = event["audit_value_volume_zscore_60m"]
    axes[0].scatter(x, event["quality_value_aligned_bar_return_1m"], c=colors, s=sizes, alpha=0.75, edgecolor="white", linewidth=0.4)
    axes[0].axhline(0, color="#111111", linewidth=0.8)
    axes[0].axvline(0, color="#111111", linewidth=0.8)
    axes[0].set_ylabel("aligned_bar_return_1m quality value")
    axes[0].set_title("Volume surprise vs last-bar direction context")
    axes[1].scatter(x, event["quality_value_directional_efficiency_30m"], c=colors, s=sizes, alpha=0.75, edgecolor="white", linewidth=0.4)
    axes[1].axhline(0, color="#111111", linewidth=0.8)
    axes[1].axvline(0, color="#111111", linewidth=0.8)
    axes[1].set_ylabel("directional_efficiency_30m")
    axes[1].set_title("Volume surprise vs 30m efficiency context")
    for ax in axes:
        ax.set_xlabel("volume_zscore_60m")
        ax.grid(alpha=0.25)
    fig.suptitle("Stage243 scatter; red=risk_bad, green=right_tail, blue=other", fontsize=12)
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
                    f"risk={int(row['risk_bad_label'])} tail={int(row['right_tail_label'])}",
                    fontsize=8,
                )
                ax.tick_params(axis="both", labelsize=7)
                ax2 = ax.twinx()
                z = pd.to_numeric(bars["stage243_volume_zscore_path"], errors="coerce")
                ax2.plot(x, z, color="#ff7f0e", linewidth=0.9, alpha=0.85)
                ax2.axhline(0, color="#ff7f0e", linewidth=0.6, alpha=0.45)
                ax2.tick_params(axis="y", labelsize=6, colors="#ff7f0e")
                ax2.set_ylabel("vol z", fontsize=6, color="#ff7f0e")
                subtitle = (
                    f"vol_z={float(row['audit_value_volume_zscore_60m']):+.3f}; "
                    f"effQ={int(row['efficiency_quintile'])}; "
                    f"lowres={int(row['low_resolution_label'])}"
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
                        "efficiency_quintile": int(row["efficiency_quintile"]),
                        "volume_zscore_60m": float(row["audit_value_volume_zscore_60m"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "low_resolution_label": int(row["low_resolution_label"]),
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page)).relative_to(REPO_DIR)),
                    }
                )
            fig.suptitle(f"Stage243 {category}: blue=directional price path, orange=rolling volume z-score path", fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(rows_out)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage239_joined_exists", int(STAGE239_JOINED_IN.exists()), "Stage239 joined signal-label audit exists"),
        ("stage239_feature_summary_exists", int(STAGE239_FEATURE_SUMMARY_IN.exists()), "Stage239 feature summary exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists"),
        ("event_row_count_219", int(summary["event_volume_row_count"] == 219), "219 volume audit rows"),
        ("q5_has_bad_counterexamples", int(summary["q5_risk_bad_count"] > 0), "Q5 volume still has bad examples"),
        ("q5_not_clean_monotonic", int(summary["q5_risk_bad_rate"] >= summary["q4_risk_bad_rate"]), "Q5 risk is not better than Q4"),
        ("high_volume_tail_coverage_above_half", int(summary["high_volume_right_tail_coverage_rate"] >= 0.5), "High-volume covers a bit more than half of right tail, descriptive only"),
        ("strategy_rule_created", 0, "no strategy rule created"),
        ("true_engine_run", 0, "no true engine run"),
        ("ab_triggered", 0, "no A/B triggered"),
        ("official_config_changed", 0, "official config untouched"),
        ("order_api_called", 0, "no order API call"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": passed, "description": description} for gate_id, passed, description in rows])


def _write_report(
    summary: dict[str, Any],
    quintile_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    joint_matrix: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    split_view = split_summary[
        [
            "split_type",
            "split_value",
            "high_count",
            "low_count",
            "high_risk_bad_rate",
            "low_risk_bad_rate",
            "high_right_tail_rate",
            "low_right_tail_rate",
            "valid_compare",
        ]
    ].head(16)
    report = f"""# {STAGE} Volume Z-score Counterexample Atlas

## Decision

- decision: `{summary['decision']}`
- event_volume_row_count: `{summary['event_volume_row_count']}`
- high_volume_count: `{summary['high_volume_count']}`
- high_volume_risk_bad_rate: `{summary['high_volume_risk_bad_rate']:.6f}`
- high_volume_right_tail_rate: `{summary['high_volume_right_tail_rate']:.6f}`
- high_volume_right_tail_coverage_rate: `{summary['high_volume_right_tail_coverage_rate']:.6f}`
- q4_risk_bad_rate: `{summary['q4_risk_bad_rate']:.6f}`
- q5_risk_bad_rate: `{summary['q5_risk_bad_rate']:.6f}`
- q5_risk_bad_count: `{summary['q5_risk_bad_count']}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- Input comes from Stage239 joined signal-label audit.
- `volume_zscore_60m` is treated as a descriptive volume surprise feature, not as a return-direction signal.
- Fixed groups only: `high_volume_q4q5`, `low_volume_q1q2`, `mid_volume_q3`, plus separate Q4/Q5 diagnostics.
- No threshold scan, no product/year/exchange/direction patch, no true engine.

## Quintile Summary

{_md_table(quintile_summary, max_rows=None)}

## Group Summary

{_md_table(group_summary, max_rows=None)}

## Split Summary

{_md_table(split_view, max_rows=None)}

## Joint Matrix Sample

{_md_table(joint_matrix.head(15), max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Atlas Manifest Sample

{_md_table(atlas_manifest.head(12), max_rows=None)}

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{QUINTILE_CHART_OUT.relative_to(REPO_DIR)}`
- `{GROUP_CHART_OUT.relative_to(REPO_DIR)}`
- `{SPLIT_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{JOINT_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{SCATTER_OUT.relative_to(REPO_DIR)}`
- atlas_pages: `{summary['atlas_page_count']}`
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    event = _prepare_event(_read_csv(STAGE239_JOINED_IN))
    stage239_feature_summary = _read_csv(STAGE239_FEATURE_SUMMARY_IN)
    volume_feature = stage239_feature_summary[
        stage239_feature_summary["audit_feature_id"].astype(str).eq("volume_zscore_60m")
    ]
    if volume_feature.empty:
        raise RuntimeError("Stage239 volume_zscore_60m summary is missing")

    quintile_summary = _build_quintile_summary(event)
    group_summary = _build_group_summary(event)
    split_summary = _build_split_summary(event)
    joint_matrix = _build_joint_matrix(event)
    atlas_selected = _select_atlas(event)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_selected)

    high = event[event["high_volume_q4q5_flag"].eq(1)]
    low = event[event["low_volume_q1q2_flag"].eq(1)]
    q4 = event[event["volume_zscore_quintile"].eq(4)]
    q5 = event[event["volume_zscore_quintile"].eq(5)]
    tail_total = int(pd.to_numeric(event["right_tail_label"], errors="coerce").fillna(0).sum())
    q5_risk_rate = _rate(q5["risk_bad_label"])
    q4_risk_rate = _rate(q4["risk_bad_label"])
    high_tail_coverage = float(pd.to_numeric(high["right_tail_label"], errors="coerce").fillna(0).sum() / tail_total) if tail_total else np.nan
    non_monotonic_block = int(q5_risk_rate >= q4_risk_rate)
    coverage_block = int(high_tail_coverage < 0.5)
    decision = (
        "stage243_volume_zscore_weak_high_volume_structure_but_q5_counterexamples_block_true_engine_no_rule"
        if non_monotonic_block or coverage_block
        else "stage243_volume_zscore_watch_only_needs_true_engine_design_no_rule"
    )

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_volume_row_count": int(len(event)),
        "stage239_universal_structure_watch_only": int(volume_feature.iloc[0]["universal_structure_watch_only"]),
        "stage239_quality_rank_corr_vs_risk_bad": float(volume_feature.iloc[0]["quality_rank_corr_vs_risk_bad"]),
        "stage239_quality_rank_corr_vs_right_tail": float(volume_feature.iloc[0]["quality_rank_corr_vs_right_tail"]),
        "high_volume_count": int(len(high)),
        "high_volume_risk_bad_count": int(pd.to_numeric(high["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "high_volume_risk_bad_rate": _rate(high["risk_bad_label"]),
        "high_volume_right_tail_count": int(pd.to_numeric(high["right_tail_label"], errors="coerce").fillna(0).sum()),
        "high_volume_right_tail_rate": _rate(high["right_tail_label"]),
        "high_volume_right_tail_coverage_rate": high_tail_coverage,
        "high_volume_low_resolution_rate": _rate(high["low_resolution_label"]),
        "low_volume_count": int(len(low)),
        "low_volume_risk_bad_count": int(pd.to_numeric(low["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "low_volume_risk_bad_rate": _rate(low["risk_bad_label"]),
        "low_volume_right_tail_count": int(pd.to_numeric(low["right_tail_label"], errors="coerce").fillna(0).sum()),
        "low_volume_right_tail_rate": _rate(low["right_tail_label"]),
        "low_volume_low_resolution_rate": _rate(low["low_resolution_label"]),
        "q4_count": int(len(q4)),
        "q4_risk_bad_count": int(pd.to_numeric(q4["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "q4_risk_bad_rate": q4_risk_rate,
        "q4_right_tail_count": int(pd.to_numeric(q4["right_tail_label"], errors="coerce").fillna(0).sum()),
        "q4_right_tail_rate": _rate(q4["right_tail_label"]),
        "q5_count": int(len(q5)),
        "q5_risk_bad_count": int(pd.to_numeric(q5["risk_bad_label"], errors="coerce").fillna(0).sum()),
        "q5_risk_bad_rate": q5_risk_rate,
        "q5_right_tail_count": int(pd.to_numeric(q5["right_tail_label"], errors="coerce").fillna(0).sum()),
        "q5_right_tail_rate": _rate(q5["right_tail_label"]),
        "rank_corr_volume_vs_risk_bad": _rank_corr(event["audit_value_volume_zscore_60m"], event["risk_bad_label"]),
        "rank_corr_volume_vs_right_tail": _rank_corr(event["audit_value_volume_zscore_60m"], event["right_tail_label"]),
        "rank_corr_volume_vs_low_resolution": _rank_corr(event["audit_value_volume_zscore_60m"], event["low_resolution_label"]),
        "q5_not_better_than_q4_risk_block": non_monotonic_block,
        "high_volume_tail_coverage_block": coverage_block,
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
    _write_csv(quintile_summary, QUINTILE_SUMMARY_OUT)
    _write_csv(group_summary, GROUP_SUMMARY_OUT)
    _write_csv(split_summary, SPLIT_SUMMARY_OUT)
    _write_csv(joint_matrix, JOINT_MATRIX_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)

    _plot_official_path(curve, summary)
    _plot_quintile_rates(quintile_summary)
    _plot_group_rates(group_summary)
    _plot_split_delta(split_summary)
    _plot_joint_heatmap(joint_matrix)
    _plot_scatter(event)
    _write_report(summary, quintile_summary, group_summary, split_summary, joint_matrix, atlas_manifest, gate_status)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
