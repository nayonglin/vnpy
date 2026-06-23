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
STAGE = "Stage240"
MODEL_TAG = "stage240_aligned_bar_return_counterexample_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage240_aligned_bar_return_counterexample_atlas"

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
STAGE239_SUMMARY_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_summary_{STAGE239_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_microstructure_audit_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_summary_{MODEL_TAG}.csv"
RULE_SKETCH_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_nonlabel_rule_sketch_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
QUINTILE_RATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aligned_bar_quintile_label_rates_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q1_q5_split_risk_heatmap_{MODEL_TAG}.png"
MICROSTRUCTURE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q1_q5_predecision_texture_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

ATLAS_LOOKBACK_BARS = 120
DIAGNOSTIC_LOOKBACKS = [5, 10, 30, 60]
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


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path, required=False)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if np.isnan(number) or np.isinf(number) else number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


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
    result["q1_flag"] = result["aligned_bar_quintile"].eq(1).astype(int)
    result["q5_flag"] = result["aligned_bar_quintile"].eq(5).astype(int)
    result["stage240_strategy_rule_allowed"] = 0
    result["stage240_true_engine_allowed"] = 0
    return result


def _load_event_bars(row: pd.Series, lookback: int = ATLAS_LOOKBACK_BARS) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    if not path.exists():
        raise RuntimeError(f"missing filtered source: {path}")
    bars = pd.read_parquet(path)
    bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
    decision_ts = pd.Timestamp(row["decision_ts"])
    bars = bars[bars["bar_end_ts"].notna() & bars["bar_end_ts"].le(decision_ts)].copy()
    bars = bars.sort_values("bar_end_ts").tail(lookback).reset_index(drop=True)
    return bars


def _event_texture(row: pd.Series) -> dict[str, Any]:
    bars = _load_event_bars(row, lookback=max(ATLAS_LOOKBACK_BARS, 61))
    sign = float(row["direction_sign"])
    close = pd.to_numeric(bars["close"], errors="coerce")
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    ret = close.pct_change() * sign
    record: dict[str, Any] = {
        "request_id": row["request_id"],
        "extension_window_id": row["extension_window_id"],
        "vt_symbol": row["vt_symbol"],
        "exchange": row["exchange"],
        "product": row["product"],
        "direction": row["direction"],
        "decision_ts": pd.Timestamp(row["decision_ts"]).strftime("%Y-%m-%d %H:%M:%S"),
        "priority_class": row["priority_class"],
        "aligned_bar_quintile": int(row["aligned_bar_quintile"]),
        "aligned_bar_value": float(row["aligned_bar_value"]),
        "risk_bad_label": int(row["risk_bad_label"]),
        "right_tail_label": int(row["right_tail_label"]),
        "ordinary_clean_label": int(row["ordinary_clean_label"]),
        "low_resolution_label": int(row["low_resolution_label"]),
        "predecision_bar_count": int(len(bars)),
        "last_bar_end_ts": "" if bars.empty else pd.Timestamp(bars["bar_end_ts"].iloc[-1]).strftime("%Y-%m-%d %H:%M:%S"),
        "last_bar_degenerate_ohlc": int((high.iloc[-1] == low.iloc[-1] == close.iloc[-1])) if len(bars) else 0,
        "stage240_strategy_rule_allowed": 0,
        "stage240_true_engine_allowed": 0,
    }
    for lookback in DIAGNOSTIC_LOOKBACKS:
        window = bars.tail(lookback + 1).copy()
        close_w = pd.to_numeric(window["close"], errors="coerce")
        volume_w = pd.to_numeric(window["volume"], errors="coerce")
        if len(close_w) >= 2 and close_w.iloc[0] != 0:
            directional_path = sign * (close_w / close_w.iloc[0] - 1.0) * 10000.0
            directional_ret = float(directional_path.iloc[-1])
            directional_mfe = float(directional_path.max())
            directional_mae = float(directional_path.min())
        else:
            directional_ret = np.nan
            directional_mfe = np.nan
            directional_mae = np.nan
        ret_w = (close_w.pct_change() * sign).dropna()
        record[f"directional_return_{lookback}bar_bps"] = directional_ret
        record[f"directional_mfe_{lookback}bar_bps"] = directional_mfe
        record[f"directional_mae_{lookback}bar_bps"] = directional_mae
        record[f"aligned_count_{lookback}bar"] = int((ret_w > 0).sum()) if len(ret_w) else 0
        record[f"positive_fraction_{lookback}bar"] = float((ret_w > 0).mean()) if len(ret_w) else np.nan
        vol_sum = float(volume_w.sum()) if volume_w.notna().any() else 0.0
        record[f"last_volume_share_{lookback}bar"] = float(volume_w.iloc[-1] / vol_sum) if vol_sum > 0 else np.nan
    return record


def _build_event_audit(joined: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in joined.iterrows():
        records.append(_event_texture(row))
    return pd.DataFrame(records)


def _rate(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _build_cohort_summary(joined: pd.DataFrame, event_audit: pd.DataFrame) -> pd.DataFrame:
    merged = joined.merge(
        event_audit[
            [
                "request_id",
                "directional_return_5bar_bps",
                "directional_return_30bar_bps",
                "directional_return_60bar_bps",
                "positive_fraction_5bar",
                "positive_fraction_30bar",
                "last_volume_share_30bar",
                "last_bar_degenerate_ohlc",
            ]
        ],
        on="request_id",
        how="left",
    )
    records: list[dict[str, Any]] = []
    for quintile in sorted(merged["aligned_bar_quintile"].dropna().unique()):
        group = merged[merged["aligned_bar_quintile"].eq(quintile)]
        records.append(
            {
                "cohort_id": f"q{int(quintile)}",
                "aligned_bar_quintile": int(quintile),
                "row_count": int(len(group)),
                "risk_bad_count": int(group["risk_bad_label"].sum()),
                "risk_bad_rate": _rate(group["risk_bad_label"]),
                "right_tail_count": int(group["right_tail_label"].sum()),
                "right_tail_rate": _rate(group["right_tail_label"]),
                "ordinary_clean_count": int(group["ordinary_clean_label"].sum()),
                "ordinary_clean_rate": _rate(group["ordinary_clean_label"]),
                "low_resolution_count": int(group["low_resolution_label"].sum()),
                "low_resolution_rate": _rate(group["low_resolution_label"]),
                "directional_return_5bar_bps_median": float(group["directional_return_5bar_bps"].median()),
                "directional_return_30bar_bps_median": float(group["directional_return_30bar_bps"].median()),
                "directional_return_60bar_bps_median": float(group["directional_return_60bar_bps"].median()),
                "positive_fraction_5bar_median": float(group["positive_fraction_5bar"].median()),
                "positive_fraction_30bar_median": float(group["positive_fraction_30bar"].median()),
                "last_volume_share_30bar_median": float(group["last_volume_share_30bar"].median()),
                "degenerate_last_bar_count": int(group["last_bar_degenerate_ohlc"].sum()),
                "stage240_strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _build_split_summary(joined: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in joined.groupby(split_column, dropna=False):
            q1 = split_group[split_group["q1_flag"].eq(1)]
            q5 = split_group[split_group["q5_flag"].eq(1)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "row_count": int(len(split_group)),
                    "q1_count": int(len(q1)),
                    "q5_count": int(len(q5)),
                    "q1_risk_bad_rate": _rate(q1["risk_bad_label"]),
                    "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
                    "q1_right_tail_rate": _rate(q1["right_tail_label"]),
                    "q5_right_tail_rate": _rate(q5["right_tail_label"]),
                    "valid_compare": int(len(q1) >= MIN_SPLIT_ROWS and len(q5) >= MIN_SPLIT_ROWS),
                    "q5_risk_better_than_q1": int(_rate(q5["risk_bad_label"]) <= _rate(q1["risk_bad_label"]))
                    if len(q1) and len(q5)
                    else np.nan,
                    "stage240_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _select_atlas(joined: pd.DataFrame) -> pd.DataFrame:
    selections: list[pd.DataFrame] = []
    cohort_specs = [
        ("q5_bad_counterexample", joined[joined["q5_flag"].eq(1) & joined["risk_bad_label"].eq(1)]),
        ("q5_right_tail_prototype", joined[joined["q5_flag"].eq(1) & joined["right_tail_label"].eq(1)]),
        ("q1_right_tail_miss", joined[joined["q1_flag"].eq(1) & joined["right_tail_label"].eq(1)]),
        ("q1_risk_bad_baseline", joined[joined["q1_flag"].eq(1) & joined["risk_bad_label"].eq(1)]),
        ("q5_ordinary_clean_reference", joined[joined["q5_flag"].eq(1) & joined["ordinary_clean_label"].eq(1)]),
    ]
    for category, frame in cohort_specs:
        if frame.empty:
            continue
        if category.startswith("q5"):
            picked = frame.sort_values("aligned_bar_value", ascending=False).head(6).copy()
        else:
            picked = frame.sort_values("aligned_bar_value", ascending=True).head(6).copy()
        picked["atlas_category"] = category
        selections.append(picked)
    if not selections:
        return pd.DataFrame()
    return pd.concat(selections, ignore_index=True)


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage240 is predecision atlas only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"q5_bad={summary['q5_risk_bad_count']} | q5_tail={summary['q5_right_tail_count']} | "
        f"q1_bad={summary['q1_risk_bad_count']} | atlas={summary['atlas_event_count']} | "
        f"true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_quintile_rates(cohort: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    x = np.arange(len(cohort))
    width = 0.26
    ax.bar(x - width, cohort["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, cohort["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, cohort["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
    ax.set_xticks(x)
    ax.set_xticklabels(cohort["cohort_id"])
    ax.set_ylim(0, max(0.6, float(cohort[["risk_bad_rate", "right_tail_rate", "ordinary_clean_rate"]].max().max()) + 0.08))
    ax.set_ylabel("rate")
    ax.set_title("Aligned bar return quintile label rates; descriptive only")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in cohort.iterrows():
        ax.text(idx, row["risk_bad_rate"] + 0.015, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(QUINTILE_RATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split_heatmap(split_summary: pd.DataFrame) -> None:
    subset = split_summary[split_summary["split_type"].isin(["year", "exchange"])].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    subset["risk_delta_q5_minus_q1"] = subset["q5_risk_bad_rate"] - subset["q1_risk_bad_rate"]
    pivot = subset.pivot_table(index="split_label", values="risk_delta_q5_minus_q1", aggfunc="first")
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted(
        [idx for idx in pivot.index if idx.startswith("exchange=")]
    )
    pivot = pivot.reindex(order)
    data = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(6.8, max(4.8, 0.36 * len(pivot.index))))
    masked = np.ma.masked_invalid(data)
    image = ax.imshow(masked, aspect="auto", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    ax.set_xticks([0])
    ax.set_xticklabels(["q5 risk rate - q1 risk rate"])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Split risk delta; blue means Q5 had lower risk-bad rate than Q1")
    for y in range(data.shape[0]):
        value = data[y, 0]
        if np.isfinite(value):
            ax.text(0, y, f"{value:+.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.04)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_microstructure(cohort: pd.DataFrame) -> None:
    plot = cohort[cohort["aligned_bar_quintile"].isin([1, 5])].copy()
    metrics = [
        "directional_return_5bar_bps_median",
        "directional_return_30bar_bps_median",
        "directional_return_60bar_bps_median",
        "positive_fraction_5bar_median",
        "positive_fraction_30bar_median",
        "last_volume_share_30bar_median",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, metric in zip(axes.flat, metrics):
        ax.bar(plot["cohort_id"], plot[metric], color=["#d62728" if item == "q1" else "#2ca02c" for item in plot["cohort_id"]])
        ax.set_title(metric.replace("_", " "), fontsize=9)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Predecision texture: Q1 vs Q5 aligned bar return")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(MICROSTRUCTURE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(selected: pd.DataFrame, event_audit: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if selected.empty:
        return [], pd.DataFrame()
    diagnostic_columns = [
        "request_id",
        "directional_return_30bar_bps",
        "positive_fraction_5bar",
        "last_volume_share_30bar",
    ]
    selected = selected.merge(event_audit[diagnostic_columns], on="request_id", how="left", validate="many_to_one")
    atlas_rows: list[dict[str, Any]] = []
    paths: list[Path] = []
    page = 1
    for category, group in selected.groupby("atlas_category", sort=False):
        rows = group.reset_index(drop=True)
        for start in range(0, len(rows), 6):
            page_rows = rows.iloc[start : start + 6].copy()
            fig, axes = plt.subplots(3, 2, figsize=(14, 10), sharex=False)
            axes_flat = axes.flat
            for ax in axes_flat:
                ax.axis("off")
            for panel_idx, (_, row) in enumerate(page_rows.iterrows()):
                ax = axes_flat[panel_idx]
                ax.axis("on")
                bars = _load_event_bars(row, lookback=ATLAS_LOOKBACK_BARS)
                sign = float(row["direction_sign"])
                close = pd.to_numeric(bars["close"], errors="coerce")
                if len(close) >= 2 and close.iloc[0] != 0:
                    y = sign * (close / close.iloc[0] - 1.0) * 10000.0
                else:
                    y = pd.Series([0.0] * len(close))
                x = np.arange(-len(y) + 1, 1)
                ax.plot(x, y, color="#1f77b4", linewidth=1.3)
                ax.axhline(0, color="#111111", linewidth=0.7, alpha=0.7)
                ax.axvline(0, color="#d62728", linewidth=0.8, alpha=0.8)
                ax.scatter([0], [float(y.iloc[-1]) if len(y) else 0.0], color="#d62728", s=22, zorder=3)
                title = (
                    f"{row['vt_symbol']} {row['direction']} Q{int(row['aligned_bar_quintile'])} "
                    f"{row['priority_class']} risk={int(row['risk_bad_label'])} tail={int(row['right_tail_label'])}"
                )
                ax.set_title(title, fontsize=8)
                ax.set_ylabel("dir bps", fontsize=8)
                ax.tick_params(axis="both", labelsize=7)
                ax.grid(alpha=0.2)
                subtitle = (
                    f"aligned1m={float(row['aligned_bar_value']):+.4f}; "
                    f"ret30={float(row.get('directional_return_30bar_bps', np.nan)):+.1f}bp; "
                    f"pos5={float(row.get('positive_fraction_5bar', np.nan)):.2f}; "
                    f"last_vol30={float(row.get('last_volume_share_30bar', np.nan)):.2f}"
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
                        "aligned_bar_value": float(row["aligned_bar_value"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "ordinary_clean_label": int(row["ordinary_clean_label"]),
                        "priority_class": row["priority_class"],
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page)).relative_to(REPO_DIR)),
                    }
                )
            fig.suptitle(f"Stage240 {category}: predecision minute paths only", fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(atlas_rows)


def _build_rule_sketch(summary: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule_sketch_id": "protect_official_risk_when_last_predecision_bar_aligned",
                "point_in_time_feature": "aligned_bar_return_1m",
                "allowed_action_if_ever_promoted": "only_veto_future_de_risk_or_delayed_restore; never_add_risk_or_filter_trades",
                "fixed_observation": "Q5 has lower risk_bad rate and higher right_tail rate than Q1 in Stage239/240 audit",
                "blocking_evidence": (
                    f"q5_bad_counterexample_count={summary['q5_risk_bad_count']}; "
                    f"q5_right_tail_coverage={summary['q5_right_tail_count']}/{summary['right_tail_label_count']}; "
                    "split reversals remain"
                ),
                "strategy_rule_allowed": 0,
                "true_engine_ready": 0,
                "ab_allowed": 0,
            }
        ]
    )


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage239_joined_exists", int(STAGE239_JOINED_IN.exists()), "Stage239 joined audit exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists"),
        ("minute_source_loaded_count_positive", int(summary["event_microstructure_row_count"] > 0), "filtered sources loaded"),
        ("q5_bad_counterexamples_present", int(summary["q5_risk_bad_count"] > 0), "Q5 still contains bad counterexamples"),
        ("label_only_rule_forbidden", 1, "Stage177 labels are not point-in-time trading rules"),
        ("strategy_rule_created", 0, "no strategy rule created"),
        ("true_engine_run", 0, "no true engine run"),
        ("ab_triggered", 0, "no A/B triggered"),
        ("official_config_changed", 0, "official config untouched"),
        ("order_api_called", 0, "no order API call"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": passed, "description": description} for gate_id, passed, description in rows])


def _write_report(
    summary: dict[str, Any],
    cohort: pd.DataFrame,
    split_summary: pd.DataFrame,
    rule_sketch: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    split_view = split_summary[
        split_summary["split_type"].isin(["year", "exchange"])
    ][
        [
            "split_type",
            "split_value",
            "row_count",
            "q1_count",
            "q5_count",
            "q1_risk_bad_rate",
            "q5_risk_bad_rate",
            "q1_right_tail_rate",
            "q5_right_tail_rate",
            "valid_compare",
        ]
    ]
    report = f"""# {STAGE} Aligned Bar Return Counterexample Atlas

## Decision

- decision: `{summary['decision']}`
- joined_row_count: `{summary['joined_row_count']}`
- q1_count: `{summary['q1_count']}`
- q5_count: `{summary['q5_count']}`
- q5_risk_bad_count: `{summary['q5_risk_bad_count']}`
- q5_right_tail_count: `{summary['q5_right_tail_count']}`
- q1_risk_bad_count: `{summary['q1_risk_bad_count']}`
- q1_right_tail_count: `{summary['q1_right_tail_count']}`
- atlas_event_count: `{summary['atlas_event_count']}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- 只使用 Stage239 joined audit 与 Stage180 cutoff-filtered predecision minute bars。
- atlas 图只画 `bar_end_ts <= decision_ts` 的分钟路径，横轴是决策前 bar 序号，不使用入场后的价格。
- `aligned_bar_return_1m` 仍只作为点时化视觉线索；Stage177 标签只用于反例分类，不生成交易条件。

## Cohort Summary

{_md_table(cohort, max_rows=None)}

## Split Summary

{_md_table(split_view, max_rows=20)}

## Rule Sketch

{_md_table(rule_sketch, max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Atlas Manifest Sample

{_md_table(atlas_manifest.head(12), max_rows=None)}

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{QUINTILE_RATE_CHART_OUT.relative_to(REPO_DIR)}`
- `{SPLIT_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{MICROSTRUCTURE_CHART_OUT.relative_to(REPO_DIR)}`
- atlas_pages: `{summary['atlas_page_count']}`
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    joined = _prepare_joined(_read_csv(STAGE239_JOINED_IN))
    stage239_summary = _row(STAGE239_SUMMARY_IN)

    event_audit = _build_event_audit(joined)
    cohort = _build_cohort_summary(joined, event_audit)
    split_summary = _build_split_summary(joined)
    selected = _select_atlas(joined)
    atlas_paths, atlas_manifest = _plot_atlas(selected, event_audit)

    q1 = joined[joined["q1_flag"].eq(1)]
    q5 = joined[joined["q5_flag"].eq(1)]
    q1_event = event_audit[event_audit["aligned_bar_quintile"].eq(1)]
    q5_event = event_audit[event_audit["aligned_bar_quintile"].eq(5)]
    right_tail_total = int(joined["right_tail_label"].sum())
    q5_tail_count = int(q5["right_tail_label"].sum())
    q5_bad_count = int(q5["risk_bad_label"].sum())
    q1_bad_count = int(q1["risk_bad_label"].sum())
    decision = "stage240_aligned_bar_return_visible_but_counterexamples_block_true_engine_no_rule"

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "joined_row_count": int(len(joined)),
        "q1_count": int(len(q1)),
        "q5_count": int(len(q5)),
        "q1_risk_bad_count": q1_bad_count,
        "q5_risk_bad_count": q5_bad_count,
        "q1_risk_bad_rate": _rate(q1["risk_bad_label"]),
        "q5_risk_bad_rate": _rate(q5["risk_bad_label"]),
        "q1_right_tail_count": int(q1["right_tail_label"].sum()),
        "q5_right_tail_count": q5_tail_count,
        "q1_right_tail_rate": _rate(q1["right_tail_label"]),
        "q5_right_tail_rate": _rate(q5["right_tail_label"]),
        "right_tail_label_count": right_tail_total,
        "q5_right_tail_coverage_rate": float(q5_tail_count / right_tail_total) if right_tail_total else np.nan,
        "q1_degenerate_last_bar_count": int(q1_event["last_bar_degenerate_ohlc"].sum()),
        "q5_degenerate_last_bar_count": int(q5_event["last_bar_degenerate_ohlc"].sum()),
        "q1_degenerate_last_bar_rate": _rate(q1_event["last_bar_degenerate_ohlc"]),
        "q5_degenerate_last_bar_rate": _rate(q5_event["last_bar_degenerate_ohlc"]),
        "event_microstructure_row_count": int(len(event_audit)),
        "atlas_event_count": int(len(atlas_manifest)),
        "atlas_page_count": int(len(atlas_paths)),
        "stage239_universal_structure_watch_only_count": _int(
            stage239_summary, "universal_structure_watch_only_count", 0
        ),
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
        "visual_file_count": 4 + int(len(atlas_paths)),
    }
    rule_sketch = _build_rule_sketch(summary)
    gate_status = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(event_audit, EVENT_AUDIT_OUT)
    _write_csv(cohort, COHORT_SUMMARY_OUT)
    _write_csv(split_summary, SPLIT_SUMMARY_OUT)
    _write_csv(rule_sketch, RULE_SKETCH_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, cohort, split_summary, rule_sketch, atlas_manifest, gate_status)

    _plot_official_path(curve, summary)
    _plot_quintile_rates(cohort)
    _plot_split_heatmap(split_summary)
    _plot_microstructure(cohort)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
