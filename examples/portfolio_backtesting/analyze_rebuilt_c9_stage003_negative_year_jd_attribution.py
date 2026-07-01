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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage003"
MODEL_TAG = "stage003_rebuilt_c9_negative_year_jd_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage003_negative_year_jd_attribution"

CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_entry_candidates_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
ANNUAL_RETURNS_PATH = (
    OUTPUT_DIR
    / "rebuilt_c9_stage002_goal_baseline_audit_annual_returns_"
    "stage002_rebuilt_c9_goal_baseline_audit_v1.csv"
)
PRODUCT_AUDIT_PATH = (
    OUTPUT_DIR
    / "rebuilt_c9_stage002_goal_baseline_audit_product_audit_"
    "stage002_rebuilt_c9_goal_baseline_audit_v1.csv"
)

NEGATIVE_YEAR_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_negative_year_attribution_{MODEL_TAG}.csv"
ANNUAL_CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_context_{MODEL_TAG}.csv"
NEGATIVE_VS_POSITIVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_negative_vs_positive_context_{MODEL_TAG}.csv"
SKIP_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_skip_reason_context_{MODEL_TAG}.csv"
PRODUCT_CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_context_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
NEGATIVE_BAR_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_negative_year_bar_{MODEL_TAG}.png"
CONTEXT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_context_scatter_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    curves = _read_csv(CURVES_PATH)
    entries = _read_csv(ENTRY_CANDIDATES_PATH)
    summary = _read_csv(SUMMARY_PATH)
    annual = _read_csv(ANNUAL_RETURNS_PATH)
    products = _read_csv(PRODUCT_AUDIT_PATH)
    return curves, entries, summary, annual, products


def _prep_curves(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["year"] = data["date"].dt.year.astype("Int64")
    numeric_cols = [
        "account_equity",
        "trade_count",
        "total_slippage",
        "net_pnl",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
        "drawdown_pct",
        "total_margin_exact",
    ]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna(subset=["date", "requested_start_month", "year"]).copy()


def _prep_entries(entries: pd.DataFrame) -> pd.DataFrame:
    data = entries.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["year"] = data["date"].dt.year.astype("Int64")
    numeric_cols = [
        "selected_volume",
        "ai_product_pool_allowed",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "active_positions_before",
        "remaining_position_slots",
        "portfolio_drawdown_pct",
        "projected_total_margin_after",
        "total_margin_in_use_before",
        "oi_price_confirm_risk_restore_applied",
        "risk_multiplier",
        "loss_streak",
        "recovery_sleeve_applied",
        "incremental_margin_budget_gate_passed",
        "incremental_margin_budget_gate_volume_reduced",
        "risk_cluster_heat_gate_selected_volume",
    ]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    data["product"] = data["product_vt_symbol"].astype(str).str.split(".").str[0]
    return data.dropna(subset=["date", "requested_start_month", "year"]).copy()


def _annual_curve_context(curves: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start_month, year), group in curves.groupby(["requested_start_month", "year"], sort=True):
        group = group.sort_values("date")
        if group.empty:
            continue
        account_equity = pd.to_numeric(group["account_equity"], errors="coerce")
        first_equity = float(account_equity.iloc[0])
        end_equity = float(account_equity.iloc[-1])
        min_equity = float(account_equity.min())
        max_equity = float(account_equity.max())
        running_peak = account_equity.cummax()
        intra_dd = (account_equity / running_peak - 1.0) * 100.0
        peak_to_end = (end_equity / max_equity - 1.0) * 100.0 if max_equity else np.nan
        rows.append(
            {
                "requested_start_month": str(start_month),
                "year": int(year),
                "year_start_date": group["date"].iloc[0].date().isoformat(),
                "year_end_date": group["date"].iloc[-1].date().isoformat(),
                "trading_days": int(len(group)),
                "start_equity_curve": first_equity,
                "end_equity_curve": end_equity,
                "min_equity_in_year": min_equity,
                "max_equity_in_year": max_equity,
                "intra_year_max_drawdown_pct": float(intra_dd.min()),
                "peak_to_end_giveback_pct": float(peak_to_end),
                "net_pnl_sum": float(pd.to_numeric(group["net_pnl"], errors="coerce").sum()),
                "trade_count_sum": int(pd.to_numeric(group["trade_count"], errors="coerce").sum()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").sum()),
                "broker10_margin_peak_pct": float(
                    pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()
                ),
                "broker10_margin_mean_pct": float(
                    pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").mean()
                ),
                "active_products_peak": int(pd.to_numeric(group["c3_active_products"], errors="coerce").max()),
                "active_contracts_peak": int(pd.to_numeric(group["c3_active_contracts"], errors="coerce").max()),
                "active_product_days": int((pd.to_numeric(group["c3_active_products"], errors="coerce") > 0).sum()),
            }
        )
    context = pd.DataFrame(rows)
    annual_cols = [
        "requested_start_month",
        "year",
        "annual_return_pct",
        "positive_year",
        "year_trading_days",
        "start_equity",
        "end_equity",
    ]
    annual_trim = annual[annual_cols].copy()
    annual_trim["year"] = annual_trim["year"].astype(int)
    merged = context.merge(annual_trim, on=["requested_start_month", "year"], how="left")
    return merged.sort_values(["requested_start_month", "year"]).reset_index(drop=True)


def _entry_context(entries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start_month, year), group in entries.groupby(["requested_start_month", "year"], sort=True):
        opened = group[group["candidate_status"].eq("opened")]
        skipped = group[group["candidate_status"].eq("skipped")]
        ai_blocked = group[group["skip_reason"].eq("ai_product_pool_blocked")]
        concurrent = group[group["skip_reason"].eq("concurrent_limit")]
        sizing_zero = group[group["skip_reason"].eq("sizing_zero_volume")]
        short_rejected = group[group["skip_reason"].eq("short_signal_rejected")]
        rows.append(
            {
                "requested_start_month": str(start_month),
                "year": int(year),
                "candidate_count": int(len(group)),
                "opened_count": int(len(opened)),
                "skipped_count": int(len(skipped)),
                "opened_rate_pct": float(len(opened) / len(group) * 100.0) if len(group) else np.nan,
                "ai_blocked_count": int(len(ai_blocked)),
                "ai_blocked_rate_pct": float(len(ai_blocked) / len(group) * 100.0) if len(group) else np.nan,
                "concurrent_limit_count": int(len(concurrent)),
                "sizing_zero_count": int(len(sizing_zero)),
                "short_signal_rejected_count": int(len(short_rejected)),
                "unique_candidate_products": int(group["product_vt_symbol"].nunique()),
                "unique_opened_products": int(opened["product_vt_symbol"].nunique()),
                "opened_selected_volume_sum": int(pd.to_numeric(opened["selected_volume"], errors="coerce").sum()),
                "opened_selected_volume_median": float(
                    pd.to_numeric(opened["selected_volume"], errors="coerce").median()
                )
                if len(opened)
                else 0.0,
                "opened_ai_rank_median": float(pd.to_numeric(opened["ai_product_pool_rank"], errors="coerce").median())
                if len(opened)
                else np.nan,
                "opened_risk_multiplier_mean": float(
                    pd.to_numeric(opened["risk_multiplier"], errors="coerce").mean()
                )
                if len(opened)
                else np.nan,
                "risk_restore_open_count": int(
                    pd.to_numeric(opened["oi_price_confirm_risk_restore_applied"], errors="coerce").fillna(0).sum()
                )
                if len(opened)
                else 0,
                "recovery_sleeve_open_count": int(
                    pd.to_numeric(opened["recovery_sleeve_applied"], errors="coerce").fillna(0).sum()
                )
                if len(opened)
                else 0,
                "loss_streak_max_at_candidate": int(pd.to_numeric(group["loss_streak"], errors="coerce").max())
                if len(group)
                else 0,
                "candidate_drawdown_median_pct": float(
                    pd.to_numeric(group["portfolio_drawdown_pct"], errors="coerce").median()
                )
                if len(group)
                else np.nan,
                "candidate_drawdown_worst_pct": float(
                    pd.to_numeric(group["portfolio_drawdown_pct"], errors="coerce").max()
                )
                if len(group)
                else np.nan,
                "remaining_slots_median": float(
                    pd.to_numeric(group["remaining_position_slots"], errors="coerce").median()
                )
                if len(group)
                else np.nan,
                "active_positions_before_median": float(
                    pd.to_numeric(group["active_positions_before"], errors="coerce").median()
                )
                if len(group)
                else np.nan,
                "incremental_margin_reduced_count": int(
                    pd.to_numeric(
                        group["incremental_margin_budget_gate_volume_reduced"], errors="coerce"
                    )
                    .fillna(0)
                    .sum()
                )
                if "incremental_margin_budget_gate_volume_reduced" in group.columns
                else 0,
            }
        )
    return pd.DataFrame(rows)


def _annual_context(curve_context: pd.DataFrame, entry_context: pd.DataFrame) -> pd.DataFrame:
    merged = curve_context.merge(entry_context, on=["requested_start_month", "year"], how="left")
    merged["annual_sign"] = np.where(
        pd.to_numeric(merged["annual_return_pct"], errors="coerce") > 0.0,
        "positive",
        "non_positive",
    )
    return merged.sort_values(["requested_start_month", "year"]).reset_index(drop=True)


def _negative_vs_positive(context: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [
        "annual_return_pct",
        "intra_year_max_drawdown_pct",
        "peak_to_end_giveback_pct",
        "trade_count_sum",
        "total_slippage_sum",
        "broker10_margin_peak_pct",
        "broker10_margin_mean_pct",
        "active_products_peak",
        "active_contracts_peak",
        "candidate_count",
        "opened_count",
        "opened_rate_pct",
        "ai_blocked_count",
        "ai_blocked_rate_pct",
        "concurrent_limit_count",
        "sizing_zero_count",
        "unique_candidate_products",
        "unique_opened_products",
        "opened_selected_volume_sum",
        "opened_risk_multiplier_mean",
        "risk_restore_open_count",
        "recovery_sleeve_open_count",
        "loss_streak_max_at_candidate",
        "candidate_drawdown_median_pct",
        "candidate_drawdown_worst_pct",
        "remaining_slots_median",
        "active_positions_before_median",
        "incremental_margin_reduced_count",
    ]
    rows: list[dict[str, Any]] = []
    for sign, group in context.groupby("annual_sign", sort=True):
        row: dict[str, Any] = {"annual_sign": sign, "row_count": int(len(group))}
        for col in metric_cols:
            values = pd.to_numeric(group[col], errors="coerce")
            row[f"{col}_median"] = float(values.median()) if values.notna().any() else np.nan
            row[f"{col}_mean"] = float(values.mean()) if values.notna().any() else np.nan
            row[f"{col}_min"] = float(values.min()) if values.notna().any() else np.nan
            row[f"{col}_max"] = float(values.max()) if values.notna().any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _skip_reason_context(entries: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    annual_sign = annual[["requested_start_month", "year", "annual_return_pct", "positive_year"]].copy()
    annual_sign["year"] = annual_sign["year"].astype(int)
    data = entries.copy()
    data["year"] = data["year"].astype(int)
    data["skip_reason_clean"] = data["skip_reason"].fillna("opened")
    merged = data.merge(annual_sign, on=["requested_start_month", "year"], how="left")
    merged["annual_sign"] = np.where(pd.to_numeric(merged["annual_return_pct"], errors="coerce") > 0.0, "positive", "non_positive")
    rows = (
        merged.groupby(["annual_sign", "skip_reason_clean"], dropna=False)
        .size()
        .reset_index(name="candidate_rows")
        .sort_values(["annual_sign", "candidate_rows"], ascending=[True, False])
    )
    totals = rows.groupby("annual_sign")["candidate_rows"].transform("sum")
    rows["share_pct"] = rows["candidate_rows"] / totals * 100.0
    return rows.reset_index(drop=True)


def _product_context(entries: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    annual_sign = annual[["requested_start_month", "year", "annual_return_pct"]].copy()
    annual_sign["year"] = annual_sign["year"].astype(int)
    data = entries.copy()
    data["year"] = data["year"].astype(int)
    merged = data.merge(annual_sign, on=["requested_start_month", "year"], how="left")
    merged["annual_sign"] = np.where(pd.to_numeric(merged["annual_return_pct"], errors="coerce") > 0.0, "positive", "non_positive")
    rows: list[dict[str, Any]] = []
    for (sign, product), group in merged.groupby(["annual_sign", "product_vt_symbol"], sort=True):
        opened = group[group["candidate_status"].eq("opened")]
        rows.append(
            {
                "annual_sign": sign,
                "product_vt_symbol": product,
                "candidate_count": int(len(group)),
                "opened_count": int(len(opened)),
                "opened_rate_pct": float(len(opened) / len(group) * 100.0) if len(group) else np.nan,
                "ai_blocked_count": int(group["skip_reason"].eq("ai_product_pool_blocked").sum()),
                "short_rejected_count": int(group["skip_reason"].eq("short_signal_rejected").sum()),
                "selected_volume_sum": int(pd.to_numeric(opened["selected_volume"], errors="coerce").sum())
                if len(opened)
                else 0,
                "median_ai_rank_opened": float(pd.to_numeric(opened["ai_product_pool_rank"], errors="coerce").median())
                if len(opened)
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["annual_sign", "opened_count", "candidate_count"], ascending=[True, False, False])


def _plot_negative_bars(negative: pd.DataFrame) -> None:
    data = negative.sort_values("annual_return_pct").copy()
    labels = data["requested_start_month"].astype(str) + " / " + data["year"].astype(str)
    fig, ax = plt.subplots(figsize=(16, 9), constrained_layout=True)
    ax.bar(np.arange(len(data)), data["annual_return_pct"], color="#b91c1c")
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_title("Stage003 Non-positive Annual Return Windows")
    ax.set_ylabel("annual return %")
    ax.set_xlabel("cold start / year")
    ax.set_xticks(np.arange(len(data)))
    ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=8)
    for index, value in enumerate(data["annual_return_pct"]):
        ax.text(index, value, f"{value:.1f}", ha="center", va="top", fontsize=7, color="#111827")
    fig.savefig(NEGATIVE_BAR_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_context(context: pd.DataFrame) -> None:
    data = context.copy()
    colors = np.where(data["annual_sign"].eq("positive"), "#047857", "#b91c1c")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    axes[0].scatter(
        data["broker10_margin_peak_pct"],
        data["annual_return_pct"],
        s=np.clip(pd.to_numeric(data["opened_count"], errors="coerce").fillna(1) * 8, 18, 180),
        c=colors,
        alpha=0.75,
    )
    axes[0].axhline(0, color="#111827", linewidth=1)
    axes[0].set_xlabel("broker10 peak margin/equity %")
    axes[0].set_ylabel("annual return %")
    axes[0].set_title("Return vs broker10 peak")
    axes[1].scatter(
        data["opened_rate_pct"],
        data["annual_return_pct"],
        s=np.clip(pd.to_numeric(data["ai_blocked_count"], errors="coerce").fillna(1) * 2, 18, 180),
        c=colors,
        alpha=0.75,
    )
    axes[1].axhline(0, color="#111827", linewidth=1)
    axes[1].set_xlabel("opened rate %")
    axes[1].set_ylabel("annual return %")
    axes[1].set_title("Return vs candidate opened rate")
    fig.savefig(CONTEXT_CHART_PATH, dpi=150)
    plt.close(fig)


def _decision(
    summary: pd.DataFrame,
    annual_context: pd.DataFrame,
    negative: pd.DataFrame,
    negative_vs_positive: pd.DataFrame,
    products: pd.DataFrame,
) -> dict[str, Any]:
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    jd_rows = products.set_index("item") if "item" in products.columns else pd.DataFrame()
    neg_year_counts = (
        negative.groupby("year")["requested_start_month"].count().sort_index().astype(int).to_dict()
        if not negative.empty
        else {}
    )
    worst = negative.sort_values("annual_return_pct").head(10).to_dict(orient="records")
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "summary": str(SUMMARY_PATH),
            "annual_returns": str(ANNUAL_RETURNS_PATH),
            "product_audit": str(PRODUCT_AUDIT_PATH),
        },
        "baseline_total_return": {
            "median_pct": float(returns.median()),
            "retention_80pct_floor": float(returns.median() * 0.8),
            "min_pct": float(returns.min()),
            "max_pct": float(returns.max()),
        },
        "negative_years": {
            "row_count": int(len(negative)),
            "year_counts": {str(k): int(v) for k, v in neg_year_counts.items()},
            "worst_rows": _json_safe(worst),
        },
        "context_summary": _json_safe(negative_vs_positive.to_dict(orient="records")),
        "jd_status": {
            "in_full_market_universe": _json_safe(jd_rows.loc["jd_in_full_market_universe"].to_dict())
            if not jd_rows.empty and "jd_in_full_market_universe" in jd_rows.index
            else None,
            "in_current_ai_pool": _json_safe(jd_rows.loc["jd_in_current_stage182_ai_pool"].to_dict())
            if not jd_rows.empty and "jd_in_current_stage182_ai_pool" in jd_rows.index
            else None,
            "in_stage167_candidates": _json_safe(jd_rows.loc["jd_in_stage167_entry_candidates"].to_dict())
            if not jd_rows.empty and "jd_in_stage167_entry_candidates" in jd_rows.index
            else None,
        },
        "judgment": {
            "overfit_risk_now": "low",
            "reason": "This stage only reads frozen Stage167 outputs and does not tune parameters or change trading rules.",
            "next_shape": (
                "Do not add jd into shared AI rerank yet. The next candidate should be a frozen, non-displacing "
                "sleeve or selector proxy, and high-quality signal risk increase must be gated by ex-ante labels "
                "visible at entry time."
            ),
        },
    }


def _write_report(
    annual_context: pd.DataFrame,
    negative: pd.DataFrame,
    negative_vs_positive: pd.DataFrame,
    skip_reason: pd.DataFrame,
    product_context: pd.DataFrame,
    summary: pd.DataFrame,
    products: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    baseline_median = float(returns.median())
    retention_floor = baseline_median * 0.8
    worst_negative = negative.sort_values("annual_return_pct").head(12)
    year_counts = (
        negative.groupby("year").agg(
            negative_rows=("requested_start_month", "count"),
            worst_return_pct=("annual_return_pct", "min"),
            median_return_pct=("annual_return_pct", "median"),
        )
        .reset_index()
        .sort_values("year")
    )
    top_negative_products = product_context[product_context["annual_sign"].eq("non_positive")].head(20)
    product_audit = products.copy()
    lines = [
        "# Stage003 重建版 C9/15w 负年度与鸡蛋接入归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{now}`",
        "- 阶段性质：只读归因，不改策略逻辑",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- Time-series momentum 的长期证据支持跨市场趋势跟随，但核心收益来自分散化和少数右尾；因此不能为了年度平滑随意砍核心右尾。",
        "- Deflated Sharpe、PBO、purged/CPCV 相关框架的共同提醒是：多参数、多候选、多窗口 winner-picking 会严重放大虚假发现。",
        "- Kelly/fractional Kelly 和期货 position sizing 资料的判断是：加大风险投入前，必须先有稳定、入场时可见的边际胜率或损益分布优势；否则只是放大估计误差。",
        "- 本阶段采纳：先用冻结 Stage167 输出做只读归因；否决：直接按 `2023/2026`、单品种或某个阈值扫参。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`examples/portfolio_backtesting/{Path(__file__).name}`",
        "- 修改策略脚本：无",
        "- 删除脚本：无",
        "- 新增参数：无策略参数；新增负年度归因口径。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 基准与目标",
        "",
        f"- 当前基准：Stage167 当前重建 C9/15w，多周期半年度冷启动，终点 `2026-06-30`。",
        f"- Stage167 中位总收益：`{baseline_median:.4f}%`。",
        f"- 80% 收益保留线：`{retention_floor:.4f}%`。",
        f"- 当前负年度行：`{len(negative)}`。",
        "- 注意：`2026` 年这里是截至 `2026-06-30` 的未完成年度/半年度路径，不等同完整自然年，但属于当前目标约束的实时缺口。",
        "",
        "## 年度负收益分布",
        "",
        _md_table(year_counts, max_rows=20),
        "",
        "## 最差年度窗口",
        "",
        _md_table(
            worst_negative[
                [
                    "requested_start_month",
                    "year",
                    "annual_return_pct",
                    "intra_year_max_drawdown_pct",
                    "peak_to_end_giveback_pct",
                    "broker10_margin_peak_pct",
                    "trade_count_sum",
                    "opened_count",
                    "ai_blocked_count",
                    "concurrent_limit_count",
                    "opened_rate_pct",
                    "unique_opened_products",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## 正负年度上下文对比",
        "",
        "- 注：`candidate_drawdown_*` 沿用源表原值，源表接近 0.50 时代表约 50% 组合回撤状态，不是 0.50 个百分点。",
        "",
        _md_table(negative_vs_positive, max_rows=10),
        "",
        "## Skip Reason 对比",
        "",
        _md_table(skip_reason, max_rows=20),
        "",
        "## 负年度候选品种上下文",
        "",
        _md_table(top_negative_products, max_rows=20),
        "",
        "## 鸡蛋状态",
        "",
        _md_table(product_audit, max_rows=20),
        "",
        "## 归因判断",
        "",
        "- 当前年度负收益不是因为 AI 没启用：Stage167 的 post-AI 审计已经 `FAIL=0`，负年度窗口里仍然有 AI allowed/blocked 元数据。",
        "- 正年度的 broker10 峰值和开仓广度反而更高，所以当前缺口不能用“简单加风险”解释或修复；负年度更像是有效趋势机会少、AI 拦截占比更高、开仓数和 opened products 更低，个别失败窗口仍有较高 broker10 压力但没有换来趋势收益。",
        "- 鸡蛋 `jd.DCE` 数据可用，但不在当前 AI 池和 Stage167 候选里。历史记录显示，共享 AI rerank/topN 加鸡蛋容易挤掉核心右尾品种，所以不能直接把鸡蛋塞进同一个共享池。",
        "- “超高质量信号加风险”下一步应该先定义入场时可见的质量标签，例如 AI rank/score、趋势广度、OI/价格一致、候选拥挤度、组合回撤状态、保证金压力和历史同类信号表现；不能使用未来 MFE/MAE 或最终盈亏。",
        "",
        "## 输出文件",
        "",
        f"- negative_year_attribution：`{NEGATIVE_YEAR_ATTRIBUTION_PATH}`",
        f"- annual_context：`{ANNUAL_CONTEXT_PATH}`",
        f"- negative_vs_positive：`{NEGATIVE_VS_POSITIVE_PATH}`",
        f"- skip_reason_context：`{SKIP_REASON_PATH}`",
        f"- product_context：`{PRODUCT_CONTEXT_PATH}`",
        f"- negative_bar_chart：`{NEGATIVE_BAR_CHART_PATH}`",
        f"- context_chart：`{CONTEXT_CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：当前重建版还没有达到新目标；失败集中在年度路径稳定性，而不是 AI 审计缺失。",
        "- 鸡蛋应走非挤占接入设计：独立 sleeve / 独立风险槽 / 账户级 selector，不能先进入共享 AI rerank 并挤占核心池。",
        "- 高质量信号加风险有继续价值，但必须先做冻结质量标签代理，再进入真实组合引擎 A/C 回测。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。只读归因冻结输出，不产生候选策略。",
        "- 运行后判断：否。没有根据某个失败年份改参数，也没有做 winner-picking。",
        "- 风险提醒：下一步如果直接按 `2023/2026` 或鸡蛋单品种表现调规则，就会进入过拟合高风险区。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。目标要求比当前基准更强，必须先定位失败形态。",
        "- 运行后判断：是。归因已经把下一步从“盲目加鸡蛋/加风险”收敛到“非挤占鸡蛋 sleeve + 入场可见质量标签”。",
        "- 后续规划：Stage004 先整理历史反证清单；Stage005 再写一个冻结的质量标签/鸡蛋非挤占代理，不直接上真实策略。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是。",
        "- 是否更新 `research/registry.md`：暂不需要；Stage003 不是正式候选。",
        "- 是否追加根目录 `memory.md/back_log.md`：否。本阶段未产生正式候选或重要突破。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    curves_raw, entries_raw, summary, annual, products = _load_inputs()
    curves = _prep_curves(curves_raw)
    entries = _prep_entries(entries_raw)
    annual["year"] = annual["year"].astype(int)
    annual["annual_return_pct"] = pd.to_numeric(annual["annual_return_pct"], errors="coerce")

    curve_context = _annual_curve_context(curves, annual)
    entry_context = _entry_context(entries)
    annual_context = _annual_context(curve_context, entry_context)
    negative = annual_context[pd.to_numeric(annual_context["annual_return_pct"], errors="coerce") <= 0.0].copy()
    negative_vs_positive = _negative_vs_positive(annual_context)
    skip_reason = _skip_reason_context(entries, annual)
    product_context = _product_context(entries, annual)

    annual_context.to_csv(ANNUAL_CONTEXT_PATH, index=False)
    negative.to_csv(NEGATIVE_YEAR_ATTRIBUTION_PATH, index=False)
    negative_vs_positive.to_csv(NEGATIVE_VS_POSITIVE_PATH, index=False)
    skip_reason.to_csv(SKIP_REASON_PATH, index=False)
    product_context.to_csv(PRODUCT_CONTEXT_PATH, index=False)

    _plot_negative_bars(negative)
    _plot_context(annual_context)

    decision = _decision(summary, annual_context, negative, negative_vs_positive, products)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(annual_context, negative, negative_vs_positive, skip_reason, product_context, summary, products, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
