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
STAGE = "Stage001"
MODEL_TAG = "stage001_c9_minrisk_baseline_visuals_v1"
OUTPUT_PREFIX = "qmt_roll_stage001_c9_minrisk_baseline_visuals"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
BT_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_baseline_visuals"

STAGE928_TAG = "stage928_c9_15w_halfyear_to_latest_v1"
STAGE928_PREFIX = "qmt_roll_stage928_c9_15w_halfyear_to_latest"
STAGE899_TAG = "stage899_c9_monthly_time_to_positive_v1"
STAGE899_PREFIX = "qmt_roll_stage899_c9_monthly_time_to_positive"
STAGE881_TAG = "stage881_stage863_progress_pyramid_proxy_audit_v1"
STAGE881_PREFIX = "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit"

HALFYEAR_SUMMARY_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_summary_{STAGE928_TAG}.csv"
HALFYEAR_CURVES_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_curves_{STAGE928_TAG}.csv"
HALFYEAR_AGG_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_aggregate_{STAGE928_TAG}.csv"
MONTHLY_SUMMARY_IN = BT_OUTPUT_DIR / f"{STAGE899_PREFIX}_summary_{STAGE899_TAG}.csv"
MONTHLY_CURVES_IN = BT_OUTPUT_DIR / f"{STAGE899_PREFIX}_curves_{STAGE899_TAG}.csv"
PROGRESS_FEATURES_IN = BT_OUTPUT_DIR / f"{STAGE881_PREFIX}_features_{STAGE881_TAG}.csv"

HALFYEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_halfyear_summary_{MODEL_TAG}.csv"
MONTHLY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_summary_{MODEL_TAG}.csv"
DELAYED_PROXY_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delayed_restore_proxy_features_{MODEL_TAG}.csv"
DELAYED_PROXY_YEARLY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delayed_restore_proxy_yearly_{MODEL_TAG}.csv"
VISUAL_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

HALFYEAR_NAV_CHART = OUTPUT_DIR / f"{OUTPUT_PREFIX}_halfyear_nav_grid_{MODEL_TAG}.png"
HALFYEAR_DD_CHART = OUTPUT_DIR / f"{OUTPUT_PREFIX}_halfyear_drawdown_grid_{MODEL_TAG}.png"
MONTHLY_RETURN_HEATMAP = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_return_heatmap_{MODEL_TAG}.png"
MONTHLY_DD_HEATMAP = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_drawdown_heatmap_{MODEL_TAG}.png"
MONTHLY_WAIT_HEATMAP = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_wait_heatmap_{MODEL_TAG}.png"
DELAYED_PROXY_CHART = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delayed_restore_proxy_yearly_{MODEL_TAG}.png"
DELAYED_PROXY_CURVE_CHART = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delayed_restore_proxy_closed_lot_curve_{MODEL_TAG}.png"

SCOUT_INITIAL_FRACTION = 0.50
CONFIRM_PROGRESS_R = 0.50


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _plot_halfyear_nav(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    windows = summary.sort_values("window_start")["window_id"].astype(str).tolist()
    fig, axes = plt.subplots(6, 3, figsize=(18, 22), constrained_layout=True)
    for ax, window_id in zip(axes.flatten(), windows, strict=False):
        row = summary[summary["window_id"].astype(str).eq(window_id)].iloc[0]
        data = curves[curves["window_id"].astype(str).eq(window_id)].copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data = data.sort_values("date")
        ax.plot(data["date"], pd.to_numeric(data["nav"], errors="coerce"), color="#2563eb", linewidth=1.0)
        ax.axhline(1.0, color="#94a3b8", linewidth=0.7, linestyle="--")
        ax.set_yscale("log")
        ax.set_title(
            f"{row['requested_start_month']} ret {row['total_return_pct']:.0f}% DD {row['max_dd_pct']:.1f}%",
            fontsize=9,
        )
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.35)
    for ax in axes.flatten()[len(windows) :]:
        ax.axis("off")
    fig.suptitle("Official C9/15w half-year cold-start NAV, log scale", fontsize=16)
    fig.savefig(HALFYEAR_NAV_CHART, dpi=170)
    plt.close(fig)


def _plot_halfyear_drawdown(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    windows = summary.sort_values("window_start")["window_id"].astype(str).tolist()
    fig, axes = plt.subplots(6, 3, figsize=(18, 22), constrained_layout=True)
    for ax, window_id in zip(axes.flatten(), windows, strict=False):
        row = summary[summary["window_id"].astype(str).eq(window_id)].iloc[0]
        data = curves[curves["window_id"].astype(str).eq(window_id)].copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data = data.sort_values("date")
        ax.fill_between(
            data["date"],
            pd.to_numeric(data["drawdown_pct"], errors="coerce"),
            0,
            color="#dc2626",
            alpha=0.28,
            linewidth=0,
        )
        ax.axhline(-30.0, color="#f59e0b", linewidth=0.8, linestyle="--")
        ax.axhline(-40.0, color="#dc2626", linewidth=0.8, linestyle="--")
        ax.set_ylim(min(-65, float(row["max_dd_pct"]) - 5), 2)
        ax.set_title(
            f"{row['requested_start_month']} DD {row['max_dd_pct']:.1f}% broker {row['max_broker10_margin_to_equity_pct']:.0f}%",
            fontsize=9,
        )
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.35)
    for ax in axes.flatten()[len(windows) :]:
        ax.axis("off")
    fig.suptitle("Official C9/15w half-year cold-start drawdown", fontsize=16)
    fig.savefig(HALFYEAR_DD_CHART, dpi=170)
    plt.close(fig)


def _annotated_heatmap(
    matrix: pd.DataFrame,
    *,
    title: str,
    path: Path,
    cmap: str,
    fmt: str,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 7.5), constrained_layout=True)
    arr = matrix.to_numpy(dtype=float)
    im = ax.imshow(arr, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(matrix.columns)), labels=[str(int(c)) for c in matrix.columns])
    ax.set_yticks(np.arange(len(matrix.index)), labels=[str(int(i)) for i in matrix.index])
    ax.set_xlabel("Start month")
    ax.set_ylabel("Start year")
    ax.set_title(title)
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            value = arr[y, x]
            if not np.isfinite(value):
                continue
            ax.text(x, y, format(value, fmt), ha="center", va="center", fontsize=7, color="#111827")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_monthly_heatmaps(monthly: pd.DataFrame) -> None:
    data = monthly.copy()
    data["start_year"] = pd.to_numeric(data["start_year"], errors="coerce").astype("Int64")
    data["start_month_num"] = pd.to_numeric(data["start_month_num"], errors="coerce").astype("Int64")
    ret = data.pivot(index="start_year", columns="start_month_num", values="rebased_total_return_pct").sort_index()
    dd = data.pivot(index="start_year", columns="start_month_num", values="rebased_max_dd_pct").sort_index()
    wait = data.pivot(
        index="start_year",
        columns="start_month_num",
        values="calendar_days_to_first_positive",
    ).sort_index()
    _annotated_heatmap(
        ret,
        title="C9 monthly cold-start latest return pct",
        path=MONTHLY_RETURN_HEATMAP,
        cmap="RdYlGn",
        fmt=".0f",
    )
    _annotated_heatmap(
        dd,
        title="C9 monthly cold-start max drawdown pct",
        path=MONTHLY_DD_HEATMAP,
        cmap="RdYlGn",
        fmt=".0f",
        vmin=-60.0,
        vmax=0.0,
    )
    _annotated_heatmap(
        wait,
        title="C9 monthly cold-start days to first positive NAV",
        path=MONTHLY_WAIT_HEATMAP,
        cmap="YlOrRd",
        fmt=".0f",
        vmin=0.0,
        vmax=160.0,
    )


def _build_delayed_restore_proxy(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    data = features.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data["entry_year"] = data["entry_date"].dt.year
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").fillna(0.0)
    data["pyramid_proxy_pnl"] = pd.to_numeric(data["pyramid_proxy_pnl"], errors="coerce").fillna(0.0)
    data["pyramid_candidate"] = pd.to_numeric(data["pyramid_candidate"], errors="coerce").fillna(0).astype(int)

    add_leg_pnl = data["pyramid_proxy_pnl"].where(data["pyramid_candidate"].eq(1), 0.0)
    data["delayed_restore_proxy_pnl"] = (
        SCOUT_INITIAL_FRACTION * data["realized_pnl"] + (1.0 - SCOUT_INITIAL_FRACTION) * add_leg_pnl
    )
    data["delayed_restore_proxy_delta_vs_original"] = data["delayed_restore_proxy_pnl"] - data["realized_pnl"]
    data["delayed_restore_candidate"] = data["pyramid_candidate"]
    data["delayed_restore_rule"] = f"initial_{SCOUT_INITIAL_FRACTION:.2f}_restore_after_{CONFIRM_PROGRESS_R:.2f}R"

    yearly = (
        data.groupby("entry_year", dropna=False)
        .agg(
            lots=("lot_id", "count"),
            candidate_lots=("delayed_restore_candidate", "sum"),
            original_pnl=("realized_pnl", "sum"),
            delayed_restore_proxy_pnl=("delayed_restore_proxy_pnl", "sum"),
            delta_vs_original=("delayed_restore_proxy_delta_vs_original", "sum"),
            big_winner_lots=("big_winner", "sum"),
        )
        .reset_index()
    )
    yearly["retention_pct"] = np.where(
        yearly["original_pnl"].abs() > 1e-9,
        yearly["delayed_restore_proxy_pnl"] / yearly["original_pnl"] * 100.0,
        np.nan,
    )
    original_total = float(data["realized_pnl"].sum())
    proxy_total = float(data["delayed_restore_proxy_pnl"].sum())
    stats = {
        "scout_initial_fraction": SCOUT_INITIAL_FRACTION,
        "confirm_progress_r": CONFIRM_PROGRESS_R,
        "closed_lot_count": int(len(data)),
        "candidate_lot_count": int(data["delayed_restore_candidate"].sum()),
        "candidate_lot_pct": float(data["delayed_restore_candidate"].mean() * 100.0),
        "original_closed_lot_pnl": original_total,
        "delayed_restore_proxy_pnl": proxy_total,
        "closed_lot_pnl_retention_pct": float(proxy_total / original_total * 100.0) if original_total else None,
        "proxy_delta_vs_original": float(proxy_total - original_total),
        "proxy_is_true_engine": False,
    }
    return data, yearly, stats


def _plot_delayed_restore_proxy(yearly: pd.DataFrame) -> None:
    fig, ax1 = plt.subplots(figsize=(13, 6.5), constrained_layout=True)
    x = np.arange(len(yearly))
    width = 0.38
    ax1.bar(x - width / 2, yearly["original_pnl"], width=width, color="#2563eb", label="Original closed-lot PnL")
    ax1.bar(
        x + width / 2,
        yearly["delayed_restore_proxy_pnl"],
        width=width,
        color="#16a34a",
        label="Delayed-restore proxy PnL",
    )
    ax1.axhline(0.0, color="#111827", linewidth=0.8)
    ax1.set_xticks(x, labels=[str(int(v)) for v in yearly["entry_year"]])
    ax1.set_ylabel("Closed-lot PnL proxy")
    ax1.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)
    ax2 = ax1.twinx()
    ax2.plot(x, yearly["retention_pct"], color="#dc2626", marker="o", label="Retention pct")
    ax2.axhline(80.0, color="#f59e0b", linewidth=0.9, linestyle="--")
    ax2.set_ylabel("Retention pct")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=False)
    fig.suptitle("Closed-lot proxy: initial 50% risk, restore after +0.5R progress", fontsize=15)
    fig.savefig(DELAYED_PROXY_CHART, dpi=170)
    plt.close(fig)


def _plot_proxy_closed_lot_curve(features: pd.DataFrame) -> None:
    data = features.dropna(subset=["exit_date"]).copy()
    daily = (
        data.groupby("exit_date", dropna=False)
        .agg(
            original_pnl=("realized_pnl", "sum"),
            delayed_restore_proxy_pnl=("delayed_restore_proxy_pnl", "sum"),
        )
        .sort_index()
        .reset_index()
    )
    daily["original_cum_pnl"] = daily["original_pnl"].cumsum()
    daily["delayed_restore_proxy_cum_pnl"] = daily["delayed_restore_proxy_pnl"].cumsum()
    fig, ax = plt.subplots(figsize=(14, 6.5), constrained_layout=True)
    ax.plot(daily["exit_date"], daily["original_cum_pnl"], color="#2563eb", linewidth=1.4, label="Original closed-lot cumulative PnL")
    ax.plot(
        daily["exit_date"],
        daily["delayed_restore_proxy_cum_pnl"],
        color="#16a34a",
        linewidth=1.4,
        label="Delayed-restore proxy cumulative PnL",
    )
    ax.axhline(0.0, color="#94a3b8", linewidth=0.8, linestyle="--")
    ax.set_title("Closed-lot proxy curve by exit date, not a portfolio equity backtest")
    ax.set_ylabel("Cumulative closed-lot PnL")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(DELAYED_PROXY_CURVE_CHART, dpi=170)
    plt.close(fig)


def _visual_manifest() -> pd.DataFrame:
    rows = [
        {"kind": "halfyear_nav_grid", "path": str(HALFYEAR_NAV_CHART), "interpretation": "log NAV shows right-tail compounding and cold-start dispersion"},
        {"kind": "halfyear_drawdown_grid", "path": str(HALFYEAR_DD_CHART), "interpretation": "drawdown grid shows DD40/DD50 tails are not one isolated trade"},
        {"kind": "monthly_return_heatmap", "path": str(MONTHLY_RETURN_HEATMAP), "interpretation": "monthly return heatmap shows broad profitability but recent weak starts"},
        {"kind": "monthly_drawdown_heatmap", "path": str(MONTHLY_DD_HEATMAP), "interpretation": "monthly drawdown heatmap locates 2020-2021 tail without turning it into a patch"},
        {"kind": "monthly_wait_heatmap", "path": str(MONTHLY_WAIT_HEATMAP), "interpretation": "wait heatmap measures cold-start pain before first positive NAV"},
        {"kind": "delayed_restore_proxy_yearly", "path": str(DELAYED_PROXY_CHART), "interpretation": "proxy checks whether risk-delay keeps 80pct closed-lot PnL"},
        {"kind": "delayed_restore_proxy_curve", "path": str(DELAYED_PROXY_CURVE_CHART), "interpretation": "proxy curve is a visual sanity check, not portfolio evidence"},
    ]
    return pd.DataFrame(rows)


def _summarize_stage928(agg: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    mature = agg[agg["scope"].astype(str).eq("mature_252d_plus")].iloc[0].to_dict()
    all_windows = agg[agg["scope"].astype(str).eq("all_windows")].iloc[0].to_dict()
    worst = summary.sort_values("max_dd_pct").head(5)[
        [
            "window_id",
            "window_start",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "deployable_pass",
        ]
    ].copy()
    return {
        "all_windows": all_windows,
        "mature_252d_plus": mature,
        "worst_halfyear_windows": worst.to_dict(orient="records"),
    }


def _summarize_monthly(monthly: pd.DataFrame) -> dict[str, Any]:
    mature = monthly[pd.to_numeric(monthly["complete_1y"], errors="coerce").fillna(0).eq(1)].copy()
    worst_dd = monthly.sort_values("rebased_max_dd_pct").head(8)[
        ["window_id", "window_start", "rebased_total_return_pct", "rebased_max_dd_pct", "calendar_days_to_first_positive"]
    ]
    unresolved = monthly[pd.to_numeric(monthly["ever_positive"], errors="coerce").fillna(0).eq(0)][
        ["window_id", "window_start", "rebased_total_return_pct", "rebased_max_dd_pct", "unresolved_elapsed_calendar_days"]
    ]
    return {
        "window_count": int(len(monthly)),
        "mature_1y_count": int(len(mature)),
        "mature_positive_count": int((pd.to_numeric(mature["rebased_total_return_pct"], errors="coerce") > 0).sum()),
        "worst_dd_pct": float(pd.to_numeric(monthly["rebased_max_dd_pct"], errors="coerce").min()),
        "median_return_pct": float(pd.to_numeric(monthly["rebased_total_return_pct"], errors="coerce").median()),
        "worst_monthly_windows": worst_dd.to_dict(orient="records"),
        "unresolved_windows": unresolved.to_dict(orient="records"),
    }


def _write_report(
    *,
    halfyear_agg: pd.DataFrame,
    halfyear_summary: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    proxy_stats: dict[str, Any],
    visual_manifest: pd.DataFrame,
) -> None:
    mature = halfyear_agg[halfyear_agg["scope"].astype(str).eq("mature_252d_plus")].iloc[0]
    worst_halfyear = halfyear_summary.sort_values("max_dd_pct").head(6)[
        ["window_id", "total_return_pct", "max_dd_pct", "sharpe", "max_broker10_margin_to_equity_pct"]
    ]
    worst_monthly = monthly_summary.sort_values("rebased_max_dd_pct").head(8)[
        ["window_id", "rebased_total_return_pct", "rebased_max_dd_pct", "calendar_days_to_first_positive"]
    ]
    text = f"""# Stage001 C9/15w最小风险高质量信号线基线视觉审计

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`
- 阶段性质：新研究线立线、正式 C9/15w 基线视觉审计、延迟恢复风险代理审计。
- 订单/CTP：不连接 CTP，不调用下单。

## 基线结论

- 当前正式 C9/15w 成熟半年度窗口 `positive={int(mature['positive_count'])}/{int(mature['window_count'])}`，中位收益 `{float(mature['median_return_pct']):.4f}%`，最差回撤 `{float(mature['worst_dd_pct']):.4f}%`。
- 成熟半年度窗口 DD40 失败 `{int(mature['dd40_fail_count'])}` 个，DD50 失败 `{int(mature['dd50_fail_count'])}` 个，broker100 失败 `{int(mature['broker100_fail_count'])}` 个。
- 视觉上不是单一窗口补丁问题：长起点的 NAV 右尾很强，但 2020/2021 周期的深回撤和 broker10 压力呈路径性出现。

## 最差半年度起点

{_md_table(worst_halfyear)}

## 月度起点风险图

{_md_table(worst_monthly)}

## 延迟恢复风险闭式代理

- 固定候选：先用原 C9 目标风险的 `{SCOUT_INITIAL_FRACTION:.0%}` 入场，入场日分钟 K 先触达 `+{CONFIRM_PROGRESS_R:.1f}R` 后才恢复剩余 `{1.0 - SCOUT_INITIAL_FRACTION:.0%}`；总风险不超过原 C9。
- 该代理来自 Stage881 closed-lot/minute features，只是判断是否值得写真实组合引擎，不是资金路径回测。
- 原 closed-lot PnL `{proxy_stats['original_closed_lot_pnl']:.4f}`，代理 PnL `{proxy_stats['delayed_restore_proxy_pnl']:.4f}`，closed-lot PnL 保留 `{proxy_stats['closed_lot_pnl_retention_pct']:.4f}%`。

{_md_table(proxy_yearly)}

## 视觉输出

{_md_table(visual_manifest)}

## 判断

- 当前阶段不宣称达成目标；只证明新线有明确基线、视觉产物和第一条非参数化候选方向。
- 下一步只允许把 `delayed_restore_50pct_after_0.5R_progress` 写成冻结真实引擎；不得扫初始比例、R倍数、月份、品种或方向。
"""
    REPORT_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    halfyear_summary = _read_csv(HALFYEAR_SUMMARY_IN)
    halfyear_curves = _read_csv(HALFYEAR_CURVES_IN)
    halfyear_agg = _read_csv(HALFYEAR_AGG_IN)
    monthly_summary = _read_csv(MONTHLY_SUMMARY_IN)
    progress_features = _read_csv(PROGRESS_FEATURES_IN)

    halfyear_summary.to_csv(HALFYEAR_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    monthly_summary.to_csv(MONTHLY_SUMMARY_OUT, index=False, encoding="utf-8-sig")

    _plot_halfyear_nav(halfyear_curves, halfyear_summary)
    _plot_halfyear_drawdown(halfyear_curves, halfyear_summary)
    _plot_monthly_heatmaps(monthly_summary)

    proxy_features, proxy_yearly, proxy_stats = _build_delayed_restore_proxy(progress_features)
    proxy_features.to_csv(DELAYED_PROXY_FEATURES_OUT, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(DELAYED_PROXY_YEARLY_OUT, index=False, encoding="utf-8-sig")
    _plot_delayed_restore_proxy(proxy_yearly)
    _plot_proxy_closed_lot_curve(proxy_features)

    visual_manifest = _visual_manifest()
    visual_manifest.to_csv(VISUAL_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    decision = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "baseline_visuals_ready_next_true_engine_delayed_restore",
        "official_live_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "inputs": {
            "halfyear_summary": str(HALFYEAR_SUMMARY_IN),
            "halfyear_curves": str(HALFYEAR_CURVES_IN),
            "monthly_summary": str(MONTHLY_SUMMARY_IN),
            "progress_features": str(PROGRESS_FEATURES_IN),
        },
        "halfyear": _summarize_stage928(halfyear_agg, halfyear_summary),
        "monthly": _summarize_monthly(monthly_summary),
        "delayed_restore_proxy": proxy_stats,
        "visuals": visual_manifest.to_dict(orient="records"),
        "overfit_judgment": {
            "stage001": "no",
            "reason": "baseline and one frozen first-principles proxy only; no parameter sweep or window-specific rule",
        },
        "next_step": "implement frozen true engine for delayed_restore_50pct_after_0.5R_progress",
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        halfyear_agg=halfyear_agg,
        halfyear_summary=halfyear_summary,
        monthly_summary=monthly_summary,
        proxy_yearly=proxy_yearly,
        proxy_stats=proxy_stats,
        visual_manifest=visual_manifest,
    )

    print(f"report={REPORT_OUT}")
    print(f"decision={DECISION_OUT}")
    print(f"visual_manifest={VISUAL_MANIFEST_OUT}")
    for path in visual_manifest["path"].tolist():
        print(f"visual={path}")


if __name__ == "__main__":
    main()
