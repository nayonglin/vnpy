from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage024"
MODEL_TAG = "stage024_preentry_risk_granularity_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE023_DIR = LINE_DIR / "outputs" / "stage023_active2_stress_loss_decomposition"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_preentry_risk_granularity_forensics"

FEATURES_IN = (
    STAGE023_DIR
    / "qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_features_"
    "stage023_active2_stress_loss_decomposition_v1.csv"
)
DAILY_STATE_IN = (
    LINE_DIR
    / "outputs"
    / "stage022_path_risk_state_forensics"
    / "qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_"
    "stage022_path_risk_state_forensics_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
RISK_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_granularity_scatter_{MODEL_TAG}.png"
VOLUME_STOP_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volume_stop_heatmap_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    column_keys = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in column_keys) + " |")
    return "\n".join(lines)


def _bucket_numeric(series: pd.Series, bins: list[float], labels: list[str], missing_label: str) -> pd.Series:
    bucket = pd.cut(series, bins=bins, labels=labels, include_lowest=True)
    out = bucket.astype(object)
    out[series.isna()] = missing_label
    return out.astype(str)


def _prepare_features() -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    numeric_columns = [
        "realized_pnl",
        "risk_amount",
        "target_risk_amount",
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "entry_risk_distance_pct",
        "prev_drawdown_pct",
        "prev_broker10_margin_to_equity_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        else:
            data[column] = np.nan

    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce")
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["exit_day"] = data["exit_date"].dt.normalize()
    data["product_key"] = data.get("product_key", data.get("product", "missing")).fillna("missing").astype(str)

    data["risk_to_target_ratio"] = (data["risk_amount"] / data["target_risk_amount"]).replace(
        [np.inf, -np.inf], np.nan
    )
    data["volume_to_risk_contract_ratio"] = (data["selected_volume"] / data["contracts_by_risk"]).replace(
        [np.inf, -np.inf], np.nan
    )
    data["margin_to_risk_contract_ratio"] = (data["contracts_by_margin"] / data["contracts_by_risk"]).replace(
        [np.inf, -np.inf], np.nan
    )
    data["entry_risk_distance_display_pct"] = data["entry_risk_distance_pct"] * 100.0

    data["selected_volume_bucket_stage024"] = _bucket_numeric(
        data["selected_volume"],
        [-0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 1_000_000.0],
        ["vol_1", "vol_2_10", "vol_11_50", "vol_51_100", "vol_101_500", "vol_gt500"],
        "missing",
    )
    data["contracts_by_risk_bucket_stage024"] = _bucket_numeric(
        data["contracts_by_risk"],
        [-0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 2000.0, 1_000_000_000.0],
        [
            "riskctr_1",
            "riskctr_2_10",
            "riskctr_11_50",
            "riskctr_51_100",
            "riskctr_101_500",
            "riskctr_501_2000",
            "riskctr_gt2000",
        ],
        "missing",
    )
    data["risk_cash_bucket_stage024"] = _bucket_numeric(
        data["risk_amount"],
        [-0.1, 2000.0, 10_000.0, 50_000.0, 200_000.0, 500_000.0, 1_000_000_000.0],
        [
            "riskcash_le2k",
            "riskcash_2_10k",
            "riskcash_10_50k",
            "riskcash_50_200k",
            "riskcash_200_500k",
            "riskcash_gt500k",
        ],
        "missing",
    )
    data["risk_to_target_bucket_stage024"] = _bucket_numeric(
        data["risk_to_target_ratio"],
        [-0.1, 0.25, 0.50, 0.75, 0.95, 1.05, 1_000_000.0],
        ["rtt_le25", "rtt_25_50", "rtt_50_75", "rtt_75_95", "rtt_95_105", "rtt_gt105"],
        "missing",
    )
    data["margin_to_risk_contract_bucket_stage024"] = _bucket_numeric(
        data["margin_to_risk_contract_ratio"],
        [-0.1, 1.0, 2.0, 5.0, 10.0, 1_000_000.0],
        ["marginctr_le1", "marginctr_1_2", "marginctr_2_5", "marginctr_5_10", "marginctr_gt10"],
        "missing",
    )
    data["margin_cap_binding_flag_stage024"] = (
        data["contracts_by_margin"].notna()
        & data["contracts_by_risk"].notna()
        & (data["contracts_by_margin"] < data["contracts_by_risk"])
    )
    data["sizing_missing_flag_stage024"] = data["selected_volume"].isna() | data["risk_amount"].isna()
    return data


def _prepare_daily() -> pd.DataFrame:
    data = _read_csv(DAILY_STATE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    return data


def _bucket_summary(data: pd.DataFrame) -> pd.DataFrame:
    families = {
        "stop_distance": "stop_distance_bucket",
        "selected_volume": "selected_volume_bucket_stage024",
        "contracts_by_risk": "contracts_by_risk_bucket_stage024",
        "risk_cash": "risk_cash_bucket_stage024",
        "risk_to_target": "risk_to_target_bucket_stage024",
        "margin_to_risk_contract": "margin_to_risk_contract_bucket_stage024",
    }
    total_positive = float(data.loc[data["realized_pnl"] > 0.0, "realized_pnl"].sum())
    total_negative_abs = float((-data.loc[data["realized_pnl"] < 0.0, "realized_pnl"]).sum())
    rows: list[dict[str, Any]] = []
    for family, column in families.items():
        for bucket, group in data.groupby(column, dropna=False):
            if group.empty:
                continue
            positive = float(group.loc[group["realized_pnl"] > 0.0, "realized_pnl"].sum())
            negative_abs = float((-group.loc[group["realized_pnl"] < 0.0, "realized_pnl"]).sum())
            yearly = group.groupby("entry_year")["realized_pnl"].sum().dropna()
            rows.append(
                {
                    "bucket_family": family,
                    "bucket": str(bucket),
                    "lot_count": int(len(group)),
                    "product_count": int(group["product_key"].nunique()),
                    "year_count": int(group["entry_year"].nunique()),
                    "net_pnl": float(group["realized_pnl"].sum()),
                    "positive_pnl": positive,
                    "negative_pnl_abs": negative_abs,
                    "positive_coverage_pct": positive / total_positive * 100.0 if total_positive else 0.0,
                    "negative_coverage_pct": negative_abs / total_negative_abs * 100.0
                    if total_negative_abs
                    else 0.0,
                    "positive_year_count": int((yearly > 0.0).sum()),
                    "negative_year_count": int((yearly < 0.0).sum()),
                    "mean_selected_volume": float(group["selected_volume"].mean()),
                    "mean_entry_risk_distance_pct": float(group["entry_risk_distance_display_pct"].mean()),
                    "mean_risk_to_target_ratio": float(group["risk_to_target_ratio"].mean()),
                    "margin_cap_binding_count": int(group["margin_cap_binding_flag_stage024"].sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["bucket_family", "net_pnl"]).reset_index(drop=True)


def _bucket_year_matrix(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for family, column in {
        "stop_distance": "stop_distance_bucket",
        "selected_volume": "selected_volume_bucket_stage024",
        "contracts_by_risk": "contracts_by_risk_bucket_stage024",
        "risk_cash": "risk_cash_bucket_stage024",
        "risk_to_target": "risk_to_target_bucket_stage024",
        "margin_to_risk_contract": "margin_to_risk_contract_bucket_stage024",
    }.items():
        item = data.groupby([column, "entry_year"])["realized_pnl"].sum().reset_index()
        item = item.rename(columns={column: "bucket"})
        item.insert(0, "bucket_family", family)
        rows.append(item)
    return pd.concat(rows, ignore_index=True)


def _cohort_masks(data: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "all_lots": pd.Series(True, index=data.index),
        "margin_cap_binding": data["margin_cap_binding_flag_stage024"],
        "sizing_missing": data["sizing_missing_flag_stage024"],
        "riskcash_le2k": data["risk_cash_bucket_stage024"].eq("riskcash_le2k"),
        "risk_to_target_le25": data["risk_to_target_bucket_stage024"].eq("rtt_le25"),
        "risk_to_target_50_75": data["risk_to_target_bucket_stage024"].eq("rtt_50_75"),
        "selected_volume_101_500": data["selected_volume_bucket_stage024"].eq("vol_101_500"),
        "selected_volume_gt500": data["selected_volume_bucket_stage024"].eq("vol_gt500"),
        "stop_le1pct": data["stop_distance_bucket"].astype(str).eq("stop_le1pct"),
        "stop_2_4pct": data["stop_distance_bucket"].astype(str).eq("stop_2_4pct"),
    }


def _cohort_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cohort, mask in _cohort_masks(data).items():
        group = data[mask.fillna(False)].copy()
        yearly = group.groupby("entry_year")["realized_pnl"].sum().dropna()
        rows.append(
            {
                "cohort": cohort,
                "lot_count": int(len(group)),
                "product_count": int(group["product_key"].nunique()) if len(group) else 0,
                "year_count": int(group["entry_year"].nunique()) if len(group) else 0,
                "net_pnl": float(group["realized_pnl"].sum()) if len(group) else 0.0,
                "positive_year_count": int((yearly > 0.0).sum()),
                "negative_year_count": int((yearly < 0.0).sum()),
                "mean_selected_volume": float(group["selected_volume"].mean()) if len(group) else 0.0,
                "mean_entry_risk_distance_pct": float(group["entry_risk_distance_display_pct"].mean())
                if len(group)
                else 0.0,
                "mean_risk_to_target_ratio": float(group["risk_to_target_ratio"].mean()) if len(group) else 0.0,
                "mean_prev_drawdown_pct": float(group["prev_drawdown_pct"].mean()) if len(group) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _cumulative_by_exit(data: pd.DataFrame, daily: pd.DataFrame, mask: pd.Series) -> pd.Series:
    group = data[mask.fillna(False) & data["exit_day"].notna()].copy()
    pnl_by_day = group.groupby("exit_day")["realized_pnl"].sum()
    index = pd.DatetimeIndex(daily["date"].dt.normalize())
    series = pnl_by_day.reindex(index, fill_value=0.0).cumsum()
    series.index = daily["date"].values
    return series


def _plot_path(data: pd.DataFrame, daily: pd.DataFrame) -> None:
    masks = _cohort_masks(data)
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1.2, 1]})
    axes[0].plot(daily["date"], daily["account_equity"], color="#2563eb", linewidth=1.5, label="official equity")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.25)
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    colors = {
        "margin_cap_binding": "#16a34a",
        "riskcash_le2k": "#dc2626",
        "risk_to_target_le25": "#0f766e",
        "risk_to_target_50_75": "#f97316",
        "selected_volume_101_500": "#9333ea",
        "stop_2_4pct": "#64748b",
    }
    for cohort, color in colors.items():
        series = _cumulative_by_exit(data, daily, masks[cohort])
        axes[1].plot(series.index, series.values, label=cohort, linewidth=1.2, color=color)
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].grid(True, alpha=0.25)
    axes[1].set_ylabel("closed-lot cumulative pnl")
    axes[1].legend(loc="upper left", ncol=2, fontsize=8)

    axes[2].plot(daily["date"], daily["drawdown_pct"], color="#334155", linewidth=1.1, label="drawdown")
    axes[2].plot(
        daily["date"],
        daily["broker10_margin_to_equity_pct"],
        color="#a855f7",
        linewidth=0.9,
        label="broker10 pct",
    )
    axes[2].axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[2].axhline(100.0, color="#a855f7", linestyle="--", linewidth=0.8)
    axes[2].grid(True, alpha=0.25)
    axes[2].set_ylabel("pct")
    axes[2].legend(loc="lower left", ncol=2, fontsize=8)
    fig.suptitle("Stage024 official path and pre-entry risk granularity cohorts")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_year_heatmap(bucket_year: pd.DataFrame) -> None:
    focus = bucket_year[
        bucket_year["bucket_family"].isin(["risk_cash", "risk_to_target", "selected_volume", "stop_distance"])
    ].copy()
    focus["row"] = focus["bucket_family"] + ":" + focus["bucket"].astype(str)
    order = (
        focus.groupby("row")["realized_pnl"].sum().abs().sort_values(ascending=False).head(24).index.tolist()
    )
    pivot = focus[focus["row"].isin(order)].pivot_table(
        index="row", columns="entry_year", values="realized_pnl", aggfunc="sum", fill_value=0.0
    )
    pivot = pivot.reindex(order)
    values = pivot.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(13, 9))
    image = ax.imshow(values, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(column)) for column in pivot.columns], fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            if abs(values[y, x]) >= vmax * 0.08:
                ax.text(x, y, f"{values[y, x] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Stage024 fixed risk granularity bucket-year net pnl")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_risk_scatter(data: pd.DataFrame) -> None:
    plot = data[data["risk_to_target_ratio"].notna()].copy()
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = np.where(plot["realized_pnl"] < 0.0, "#dc2626", "#2563eb")
    sizes = np.clip(plot["selected_volume"].fillna(1.0) / 3.0, 10.0, 260.0)
    ax.scatter(
        plot["risk_to_target_ratio"],
        plot["entry_risk_distance_display_pct"],
        s=sizes,
        c=colors,
        alpha=0.55,
        edgecolor="white",
        linewidth=0.35,
    )
    ax.axvline(0.25, color="#64748b", linestyle="--", linewidth=0.8)
    ax.axvline(0.75, color="#64748b", linestyle="--", linewidth=0.8)
    ax.axvline(1.0, color="#111827", linestyle=":", linewidth=0.8)
    ax.axhline(1.0, color="#16a34a", linestyle="--", linewidth=0.8)
    ax.axhline(2.0, color="#16a34a", linestyle=":", linewidth=0.8)
    ax.set_xlabel("actual risk / target risk")
    ax.set_ylabel("entry risk distance pct")
    ax.set_title("Stage024 entry risk distance vs actual risk utilization; size = selected volume")
    ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2563eb", markersize=8, label="winning lot"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=8, label="losing lot"),
    ]
    ax.legend(handles=handles, loc="upper right")
    fig.tight_layout()
    fig.savefig(RISK_SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_volume_stop_heatmap(data: pd.DataFrame) -> None:
    pivot = data.pivot_table(
        index="selected_volume_bucket_stage024",
        columns="stop_distance_bucket",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    row_order = ["missing", "vol_1", "vol_2_10", "vol_11_50", "vol_51_100", "vol_101_500", "vol_gt500"]
    col_order = ["missing", "stop_le1pct", "stop_1_2pct", "stop_2_4pct", "stop_gt4pct"]
    pivot = pivot.reindex([r for r in row_order if r in pivot.index])
    pivot = pivot[[c for c in col_order if c in pivot.columns]]
    values = pivot.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(10, 6))
    image = ax.imshow(values, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            if abs(values[y, x]) >= vmax * 0.08:
                ax.text(x, y, f"{values[y, x] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Stage024 selected volume x stop distance net pnl")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(VOLUME_STOP_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    data: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    cohort_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    weakest = bucket_summary.sort_values("net_pnl").head(15)
    strongest = bucket_summary.sort_values("net_pnl", ascending=False).head(15)
    focus_cohorts = cohort_summary[
        cohort_summary["cohort"].isin(
            [
                "margin_cap_binding",
                "riskcash_le2k",
                "risk_to_target_le25",
                "risk_to_target_50_75",
                "selected_volume_101_500",
                "stop_2_4pct",
            ]
        )
    ]
    rtt_year = bucket_year[bucket_year["bucket_family"].eq("risk_to_target")].pivot_table(
        index="bucket", columns="entry_year", values="realized_pnl", aggfunc="sum", fill_value=0.0
    )
    lines = [
        f"# {STAGE} pre-entry risk granularity / risk distance 只读归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- 阶段性质：只读法证；所有分桶均为入场前可见的 sizing/risk ledger 字段，不使用未来结果生成条件。",
        "- 候选状态：`candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- `margin_cap_binding` 净 PnL `{decision['margin_cap_binding_net_pnl']:.2f}`，说明保证金 cap binding 不是坏信号。",
        f"- `selected_volume_101_500` 净 PnL `{decision['selected_volume_101_500_net_pnl']:.2f}`，大手数不是坏信号充分条件。",
        f"- `risk_to_target_50_75` 净 PnL `{decision['risk_to_target_50_75_net_pnl']:.2f}`，但相邻桶 `rtt_le25/rtt_75_95/rtt_95_105` 为正，关系非单调。",
        f"- `riskcash_le2k` 净 PnL `{decision['riskcash_le2k_net_pnl']:.2f}`，样本只有 `{decision['riskcash_le2k_lot_count']}` 笔且年份少，不足以交易化。",
        "",
        "## 重点 cohort 摘要",
        "",
        _md_table(focus_cohorts),
        "",
        "## 最弱固定分桶",
        "",
        _md_table(weakest),
        "",
        "## 最强固定分桶",
        "",
        _md_table(strongest),
        "",
        "## risk_to_target 年度矩阵",
        "",
        _md_table(rtt_year.reset_index()),
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_OUT}`",
        f"- bucket summary：`{BUCKET_SUMMARY_OUT}`",
        f"- bucket year matrix：`{BUCKET_YEAR_OUT}`",
        f"- cohort summary：`{COHORT_SUMMARY_OUT}`",
        f"- path chart：`{PATH_CHART_OUT}`",
        f"- bucket-year heatmap：`{BUCKET_YEAR_HEATMAP_OUT}`",
        f"- risk scatter：`{RISK_SCATTER_OUT}`",
        f"- volume-stop heatmap：`{VOLUME_STOP_HEATMAP_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉判断",
        "",
        "- path chart 显示 `margin_cap_binding` 和 `selected_volume_101_500` 随官方右尾台阶上行，不是应削风险的状态。",
        "- bucket-year heatmap 显示负贡献不是沿风险粒度单调增加，而是分散在局部桶和局部年份。",
        "- risk scatter 显示亏损点与盈利点在 risk utilization / stop distance 空间混杂；没有一个入场前可见的干净边界。",
        "- volume-stop heatmap 显示窄止损 + 大手数反而是官方右尾核心区域之一，不能用“手数大/止损窄”机械最小风险。",
        "",
        "## 后续边界",
        "",
        "- 停止把 selected volume、contracts_by_risk、stop distance、risk_to_target 单桶写成交易规则。",
        "- 若继续该目标，需要寻找更外生的信息，或只做 forward watch；不得继续扫风险粒度阈值。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _prepare_features()
    daily = _prepare_daily()
    bucket_summary = _bucket_summary(data)
    bucket_year = _bucket_year_matrix(data)
    cohort_summary = _cohort_summary(data)

    def cohort_value(cohort: str, column: str) -> float:
        row = cohort_summary[cohort_summary["cohort"].eq(cohort)]
        if row.empty:
            return 0.0
        return float(row.iloc[0][column])

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "decision": "stage024_preentry_risk_granularity_no_candidate_nonmonotonic_right_tail_dominant",
        "reason": [
            "Margin cap binding and large selected-volume cohorts are strongly positive, so they are not bad-signal states.",
            "Risk-to-target utilization has a weak negative middle bucket, but the relationship is non-monotonic and adjacent buckets are positive.",
            "Very small actual risk cash is weakly negative, but sample breadth is too small and mostly reflects low participation rather than drawdown control.",
            "Stop distance buckets do not produce a universal monotonic risk source; narrow stops are a core right-tail contributor.",
        ],
        "margin_cap_binding_net_pnl": cohort_value("margin_cap_binding", "net_pnl"),
        "selected_volume_101_500_net_pnl": cohort_value("selected_volume_101_500", "net_pnl"),
        "risk_to_target_50_75_net_pnl": cohort_value("risk_to_target_50_75", "net_pnl"),
        "riskcash_le2k_net_pnl": cohort_value("riskcash_le2k", "net_pnl"),
        "riskcash_le2k_lot_count": int(cohort_value("riskcash_le2k", "lot_count")),
        "output_files": {
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "bucket_year_matrix": BUCKET_YEAR_OUT,
            "cohort_summary": COHORT_SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "risk_scatter": RISK_SCATTER_OUT,
            "volume_stop_heatmap": VOLUME_STOP_HEATMAP_OUT,
        },
    }

    data.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    cohort_summary.to_csv(COHORT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path(data, daily)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_risk_scatter(data)
    _plot_volume_stop_heatmap(data)
    _write_report(data, bucket_summary, bucket_year, cohort_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
