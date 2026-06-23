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
STAGE = "Stage242"
MODEL_TAG = "stage242_without_last_multibar_persistence_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage242_without_last_multibar_persistence_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE241_DIR = LINE_DIR / "outputs" / "stage241_aligned_bar_return_artifact_peel_audit"
STAGE241_PREFIX = "qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit"
STAGE241_TAG = "stage241_aligned_bar_return_artifact_peel_audit_v1"
STAGE241_EVENT_IN = STAGE241_DIR / f"{STAGE241_PREFIX}_event_artifact_audit_{STAGE241_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_persistence_audit_{MODEL_TAG}.csv"
QUINTILE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quintile_summary_{MODEL_TAG}.csv"
COMBO_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_summary_{MODEL_TAG}.csv"
SPLIT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_summary_{MODEL_TAG}.csv"
MATRIX_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q30_q60_matrix_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
QUINTILE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q30_q60_label_rates_{MODEL_TAG}.png"
COMBO_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_label_rates_{MODEL_TAG}.png"
MATRIX_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_q30_q60_matrix_heatmap_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_both_high_vs_low_split_delta_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return30_vs_return60_scatter_{MODEL_TAG}.png"
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


def _rank_corr(left: pd.Series, right: pd.Series) -> float:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    mask = left_num.notna() & right_num.notna()
    if int(mask.sum()) < 3:
        return np.nan
    if left_num[mask].nunique(dropna=True) < 2 or right_num[mask].nunique(dropna=True) < 2:
        return np.nan
    return float(left_num[mask].rank(method="average").corr(right_num[mask].rank(method="average"), method="pearson"))


def _combo(row: pd.Series) -> str:
    q30 = int(row["without_last_30bar_quintile"])
    q60 = int(row["without_last_60bar_quintile"])
    if q30 >= 4 and q60 >= 4:
        return "both_high_q4q5"
    if q30 <= 2 and q60 <= 2:
        return "both_low_q1q2"
    if q30 >= 4 and q60 <= 3:
        return "thirty_high_only"
    if q60 >= 4 and q30 <= 3:
        return "sixty_high_only"
    return "mixed_middle"


def _build_event(event: pd.DataFrame) -> pd.DataFrame:
    data = event.copy()
    data["without_last_return_30bar_bps"] = pd.to_numeric(data["without_last_return_30bar_bps"], errors="coerce")
    data["without_last_return_60bar_bps"] = pd.to_numeric(data["without_last_return_60bar_bps"], errors="coerce")
    data["without_last_30bar_quintile"] = _quality_quintile(data["without_last_return_30bar_bps"]).round().astype("Int64")
    data["without_last_60bar_quintile"] = _quality_quintile(data["without_last_return_60bar_bps"]).round().astype("Int64")
    data["persistence_combo"] = data.apply(_combo, axis=1)
    data["both_high_q4q5_flag"] = data["persistence_combo"].eq("both_high_q4q5").astype(int)
    data["both_low_q1q2_flag"] = data["persistence_combo"].eq("both_low_q1q2").astype(int)
    data["sixty_high_only_flag"] = data["persistence_combo"].eq("sixty_high_only").astype(int)
    data["thirty_high_only_flag"] = data["persistence_combo"].eq("thirty_high_only").astype(int)
    data["stage242_strategy_rule_allowed"] = 0
    data["stage242_true_engine_allowed"] = 0
    return data


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
        "degenerate_last_bar_rate": _rate(frame["last_bar_degenerate_ohlc"]),
        "return30_bps_median": float(pd.to_numeric(frame["without_last_return_30bar_bps"], errors="coerce").median()) if len(frame) else np.nan,
        "return60_bps_median": float(pd.to_numeric(frame["without_last_return_60bar_bps"], errors="coerce").median()) if len(frame) else np.nan,
        "stage242_strategy_rule_allowed": 0,
    }


def _build_quintile_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for horizon, q_col in [("30bar", "without_last_30bar_quintile"), ("60bar", "without_last_60bar_quintile")]:
        for quintile in range(1, 6):
            group = event[event[q_col].eq(quintile)]
            row = _summarize_group(f"{horizon}_q{quintile}", group)
            row["horizon"] = horizon
            row["quintile"] = quintile
            records.append(row)
    return pd.DataFrame(records)


def _build_combo_summary(event: pd.DataFrame) -> pd.DataFrame:
    order = ["both_high_q4q5", "sixty_high_only", "thirty_high_only", "mixed_middle", "both_low_q1q2"]
    records = []
    for combo in order:
        records.append(_summarize_group(combo, event[event["persistence_combo"].eq(combo)]))
    return pd.DataFrame(records)


def _build_matrix_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for q30 in range(1, 6):
        for q60 in range(1, 6):
            group = event[event["without_last_30bar_quintile"].eq(q30) & event["without_last_60bar_quintile"].eq(q60)]
            records.append(
                {
                    "q30": q30,
                    "q60": q60,
                    "row_count": int(len(group)),
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "right_tail_rate": _rate(group["right_tail_label"]),
                    "ordinary_clean_rate": _rate(group["ordinary_clean_label"]),
                    "stage242_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_split_summary(event: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, split_column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, split_group in event.groupby(split_column, dropna=False):
            high = split_group[split_group["both_high_q4q5_flag"].eq(1)]
            low = split_group[split_group["both_low_q1q2_flag"].eq(1)]
            records.append(
                {
                    "split_type": split_type,
                    "split_value": "" if pd.isna(split_value) else str(split_value),
                    "row_count": int(len(split_group)),
                    "both_high_count": int(len(high)),
                    "both_low_count": int(len(low)),
                    "both_high_risk_bad_rate": _rate(high["risk_bad_label"]),
                    "both_low_risk_bad_rate": _rate(low["risk_bad_label"]),
                    "both_high_right_tail_rate": _rate(high["right_tail_label"]),
                    "both_low_right_tail_rate": _rate(low["right_tail_label"]),
                    "valid_compare": int(len(high) >= MIN_SPLIT_ROWS and len(low) >= MIN_SPLIT_ROWS),
                    "stage242_strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _load_bars(row: pd.Series) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    bars = pd.read_parquet(path)
    bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
    decision_ts = pd.Timestamp(row["decision_ts"])
    return bars[bars["bar_end_ts"].notna() & bars["bar_end_ts"].le(decision_ts)].sort_values("bar_end_ts").tail(ATLAS_LOOKBACK_BARS).reset_index(drop=True)


def _select_atlas(event: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("both_high_bad", event.query("persistence_combo == 'both_high_q4q5' and risk_bad_label == 1")),
        ("both_high_tail", event.query("persistence_combo == 'both_high_q4q5' and right_tail_label == 1")),
        ("both_low_tail_miss", event.query("persistence_combo == 'both_low_q1q2' and right_tail_label == 1")),
        ("sixty_high_only_tail", event.query("persistence_combo == 'sixty_high_only' and right_tail_label == 1")),
        ("thirty_high_only_bad", event.query("persistence_combo == 'thirty_high_only' and risk_bad_label == 1")),
    ]
    frames: list[pd.DataFrame] = []
    for category, frame in specs:
        if frame.empty:
            continue
        picked = frame.sort_values(["without_last_return_60bar_bps", "without_last_return_30bar_bps"], ascending=False).head(6).copy()
        picked["atlas_category"] = category
        frames.append(picked)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage242 audits without-last 30/60bar persistence only")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"both_high={summary['both_high_count']} risk={summary['both_high_risk_bad_rate']:.3f} "
        f"tail={summary['both_high_right_tail_rate']:.3f} | "
        f"both_low={summary['both_low_count']} risk={summary['both_low_risk_bad_rate']:.3f} | true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_quintile_rates(quintile_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), sharey=True)
    for ax, horizon in zip(axes, ["30bar", "60bar"]):
        plot = quintile_summary[quintile_summary["horizon"].eq(horizon)].sort_values("quintile")
        x = np.arange(len(plot))
        width = 0.26
        ax.bar(x - width, plot["risk_bad_rate"], width, label="risk_bad", color="#d62728")
        ax.bar(x, plot["right_tail_rate"], width, label="right_tail", color="#2ca02c")
        ax.bar(x + width, plot["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
        ax.set_xticks(x)
        ax.set_xticklabels([f"Q{int(q)}" for q in plot["quintile"]])
        ax.set_title(f"without-last {horizon} return quintile")
        ax.grid(axis="y", alpha=0.25)
        for idx, row in plot.reset_index(drop=True).iterrows():
            ax.text(idx, max(row["risk_bad_rate"], row["right_tail_rate"], row["ordinary_clean_rate"]) + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    axes[0].set_ylabel("rate")
    axes[1].legend(loc="best")
    fig.tight_layout()
    fig.savefig(QUINTILE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_combo_rates(combo_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.2))
    x = np.arange(len(combo_summary))
    width = 0.26
    ax.bar(x - width, combo_summary["risk_bad_rate"], width, label="risk_bad", color="#d62728")
    ax.bar(x, combo_summary["right_tail_rate"], width, label="right_tail", color="#2ca02c")
    ax.bar(x + width, combo_summary["ordinary_clean_rate"], width, label="ordinary_clean", color="#1f77b4")
    ax.set_xticks(x)
    ax.set_xticklabels(combo_summary["group_id"], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("rate")
    ax.set_title("Without-last 30/60bar persistence combo label rates")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    for idx, row in combo_summary.reset_index(drop=True).iterrows():
        ax.text(idx, max(row["risk_bad_rate"], row["right_tail_rate"], row["ordinary_clean_rate"]) + 0.02, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(COMBO_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_matrix(matrix: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, value_col, title, cmap in [
        (axes[0], "risk_bad_rate", "risk_bad rate by Q30/Q60", "Reds"),
        (axes[1], "right_tail_rate", "right_tail rate by Q30/Q60", "Greens"),
    ]:
        pivot = matrix.pivot(index="q60", columns="q30", values=value_col)
        count = matrix.pivot(index="q60", columns="q30", values="row_count")
        data = pivot.to_numpy(dtype=float)
        image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=0, vmax=max(0.35, np.nanmax(data) if np.isfinite(data).any() else 0.35))
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([f"Q{col}" for col in pivot.columns])
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels([f"Q{idx}" for idx in pivot.index])
        ax.set_xlabel("30bar quintile")
        ax.set_ylabel("60bar quintile")
        ax.set_title(title)
        for y in range(data.shape[0]):
            for x in range(data.shape[1]):
                value = data[y, x]
                n = int(count.to_numpy()[y, x])
                if np.isfinite(value):
                    ax.text(x, y, f"{value:.2f}\nn={n}", ha="center", va="center", fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(MATRIX_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_split_delta(split_summary: pd.DataFrame) -> None:
    subset = split_summary[split_summary["split_type"].isin(["year", "exchange"])].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    subset["risk_delta_high_minus_low"] = subset["both_high_risk_bad_rate"] - subset["both_low_risk_bad_rate"]
    subset["tail_delta_high_minus_low"] = subset["both_high_right_tail_rate"] - subset["both_low_right_tail_rate"]
    pivot = subset.set_index("split_label")[["risk_delta_high_minus_low", "tail_delta_high_minus_low"]]
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted([idx for idx in pivot.index if idx.startswith("exchange=")])
    pivot = pivot.reindex(order)
    fig, ax = plt.subplots(figsize=(7.5, max(4.8, 0.36 * len(pivot))))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(["risk high-low", "tail high-low"], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Both-high minus both-low by split; blue risk is better, red tail is better")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:+.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.04)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(event: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    colors = np.where(event["risk_bad_label"].eq(1), "#d62728", np.where(event["right_tail_label"].eq(1), "#2ca02c", "#1f77b4"))
    sizes = np.where(event["right_tail_label"].eq(1), 55, 24)
    ax.scatter(event["without_last_return_30bar_bps"], event["without_last_return_60bar_bps"], c=colors, s=sizes, alpha=0.75, edgecolor="white", linewidth=0.4)
    ax.axhline(0, color="#111111", linewidth=0.8)
    ax.axvline(0, color="#111111", linewidth=0.8)
    ax.set_xlabel("without-last 30bar directional return bps")
    ax.set_ylabel("without-last 60bar directional return bps")
    ax.set_title("Multibar persistence scatter; red=risk_bad, green=right_tail")
    ax.grid(alpha=0.25)
    fig.tight_layout()
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
                ax.axvspan(-60, -1, color="#2ca02c", alpha=0.08)
                ax.axvspan(-30, -1, color="#1f77b4", alpha=0.08)
                ax.plot(x[:-1], y.iloc[:-1], color="#1f77b4", linewidth=1.2)
                ax.plot(x[-2:], y.iloc[-2:], color="#d62728", linewidth=1.4)
                ax.axhline(0, color="#111111", linewidth=0.7, alpha=0.7)
                ax.axvline(0, color="#d62728", linewidth=0.8, alpha=0.8)
                ax.set_title(
                    f"{row['vt_symbol']} {row['direction']} {row['persistence_combo']} "
                    f"risk={int(row['risk_bad_label'])} tail={int(row['right_tail_label'])}",
                    fontsize=8,
                )
                ax.tick_params(axis="both", labelsize=7)
                ax.grid(alpha=0.2)
                subtitle = (
                    f"ret30={float(row['without_last_return_30bar_bps']):+.1f}bp Q{int(row['without_last_30bar_quintile'])}; "
                    f"ret60={float(row['without_last_return_60bar_bps']):+.1f}bp Q{int(row['without_last_60bar_quintile'])}; "
                    f"deg={int(row['last_bar_degenerate_ohlc'])}"
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
                        "persistence_combo": row["persistence_combo"],
                        "without_last_30bar_quintile": int(row["without_last_30bar_quintile"]),
                        "without_last_60bar_quintile": int(row["without_last_60bar_quintile"]),
                        "risk_bad_label": int(row["risk_bad_label"]),
                        "right_tail_label": int(row["right_tail_label"]),
                        "chart_file": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page)).relative_to(REPO_DIR)),
                    }
                )
            fig.suptitle(f"Stage242 {category}: 60bar green band, 30bar blue band, final bar red", fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
            path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
            fig.savefig(path, dpi=160)
            plt.close(fig)
            paths.append(path)
            page += 1
    return paths, pd.DataFrame(rows_out)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage241_event_exists", int(STAGE241_EVENT_IN.exists()), "Stage241 event artifact audit exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists"),
        ("event_row_count_219", int(summary["event_persistence_row_count"] == 219), "219 persistence rows"),
        ("both_high_has_counterexamples", int(summary["both_high_risk_bad_count"] > 0), "both-high still has bad examples"),
        ("both_high_tail_not_dominant", int(summary["both_high_right_tail_coverage_rate"] < 0.5), "both-high does not cover most right tail"),
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
    combo_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    matrix_summary: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    split_view = split_summary[
        [
            "split_type",
            "split_value",
            "both_high_count",
            "both_low_count",
            "both_high_risk_bad_rate",
            "both_low_risk_bad_rate",
            "both_high_right_tail_rate",
            "both_low_right_tail_rate",
            "valid_compare",
        ]
    ].head(16)
    report = f"""# {STAGE} Without-last Multibar Persistence Audit

## Decision

- decision: `{summary['decision']}`
- event_persistence_row_count: `{summary['event_persistence_row_count']}`
- both_high_count: `{summary['both_high_count']}`
- both_high_risk_bad_rate: `{summary['both_high_risk_bad_rate']:.6f}`
- both_high_right_tail_rate: `{summary['both_high_right_tail_rate']:.6f}`
- both_high_right_tail_coverage_rate: `{summary['both_high_right_tail_coverage_rate']:.6f}`
- both_low_count: `{summary['both_low_count']}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- 输入来自 Stage241 event artifact audit。
- 去掉最后一根 bar 后，固定计算 30bar 与 60bar 方向收益的 rank quintile。
- 固定结构组：`both_high_q4q5`、`both_low_q1q2`、`thirty_high_only`、`sixty_high_only`、`mixed_middle`。
- 不扫 bps 阈值、不按年份/交易所/方向补丁化。

## Quintile Summary

{_md_table(quintile_summary, max_rows=None)}

## Combo Summary

{_md_table(combo_summary, max_rows=None)}

## Split Summary

{_md_table(split_view, max_rows=None)}

## Matrix Sample

{_md_table(matrix_summary.head(15), max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Atlas Manifest Sample

{_md_table(atlas_manifest.head(12), max_rows=None)}

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{QUINTILE_CHART_OUT.relative_to(REPO_DIR)}`
- `{COMBO_CHART_OUT.relative_to(REPO_DIR)}`
- `{MATRIX_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{SPLIT_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{SCATTER_OUT.relative_to(REPO_DIR)}`
- atlas_pages: `{summary['atlas_page_count']}`
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    event = _build_event(_read_csv(STAGE241_EVENT_IN))
    quintile_summary = _build_quintile_summary(event)
    combo_summary = _build_combo_summary(event)
    matrix_summary = _build_matrix_summary(event)
    split_summary = _build_split_summary(event)
    atlas_selected = _select_atlas(event)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_selected)

    both_high = event[event["both_high_q4q5_flag"].eq(1)]
    both_low = event[event["both_low_q1q2_flag"].eq(1)]
    tail_total = int(event["right_tail_label"].sum())
    decision = "stage242_without_last_multibar_persistence_no_true_engine_no_rule"
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_persistence_row_count": int(len(event)),
        "both_high_count": int(len(both_high)),
        "both_high_risk_bad_count": int(both_high["risk_bad_label"].sum()),
        "both_high_risk_bad_rate": _rate(both_high["risk_bad_label"]),
        "both_high_right_tail_count": int(both_high["right_tail_label"].sum()),
        "both_high_right_tail_rate": _rate(both_high["right_tail_label"]),
        "both_high_right_tail_coverage_rate": float(both_high["right_tail_label"].sum() / tail_total) if tail_total else np.nan,
        "both_high_ordinary_clean_rate": _rate(both_high["ordinary_clean_label"]),
        "both_low_count": int(len(both_low)),
        "both_low_risk_bad_count": int(both_low["risk_bad_label"].sum()),
        "both_low_risk_bad_rate": _rate(both_low["risk_bad_label"]),
        "both_low_right_tail_count": int(both_low["right_tail_label"].sum()),
        "both_low_right_tail_rate": _rate(both_low["right_tail_label"]),
        "rank_corr_30_vs_risk_bad": _rank_corr(event["without_last_return_30bar_bps"], event["risk_bad_label"]),
        "rank_corr_30_vs_right_tail": _rank_corr(event["without_last_return_30bar_bps"], event["right_tail_label"]),
        "rank_corr_60_vs_risk_bad": _rank_corr(event["without_last_return_60bar_bps"], event["risk_bad_label"]),
        "rank_corr_60_vs_right_tail": _rank_corr(event["without_last_return_60bar_bps"], event["right_tail_label"]),
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
    _write_csv(combo_summary, COMBO_SUMMARY_OUT)
    _write_csv(split_summary, SPLIT_SUMMARY_OUT)
    _write_csv(matrix_summary, MATRIX_SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, quintile_summary, combo_summary, split_summary, matrix_summary, atlas_manifest, gate_status)

    _plot_official_path(curve, summary)
    _plot_quintile_rates(quintile_summary)
    _plot_combo_rates(combo_summary)
    _plot_matrix(matrix_summary)
    _plot_split_delta(split_summary)
    _plot_scatter(event)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
