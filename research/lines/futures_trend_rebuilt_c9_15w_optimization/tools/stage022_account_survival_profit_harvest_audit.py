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


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage009_dense_start_goal_audit as s009


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage022"
MODEL_TAG = "stage022_account_survival_profit_harvest_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage022_account_survival_profit_harvest_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage022_account_survival_profit_harvest_audit"
STAGE_RECORD_DIR = LINE_DIR / "stages"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE021_CURVES_PATH = STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_curves_{STAGE021_TAG}.csv"

CAPITAL = 150000.0
OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_DAYS = 365

HARVEST_POLICIES = [
    {
        "variant": "stage022_harvest_3x_lock50_primary",
        "threshold_mult": 3.0,
        "lock_fraction": 0.50,
        "role": "predeclared_primary",
    },
    {
        "variant": "stage022_harvest_2x_lock50_sensitivity",
        "threshold_mult": 2.0,
        "lock_fraction": 0.50,
        "role": "sensitivity_not_candidate",
    },
    {
        "variant": "stage022_harvest_1p5x_lock50_sensitivity",
        "threshold_mult": 1.5,
        "lock_fraction": 0.50,
        "role": "sensitivity_not_candidate",
    },
    {
        "variant": "stage022_harvest_3x_lock33_sensitivity",
        "threshold_mult": 3.0,
        "lock_fraction": 0.33,
        "role": "sensitivity_not_candidate",
    },
    {
        "variant": "stage022_harvest_3x_lock67_sensitivity",
        "threshold_mult": 3.0,
        "lock_fraction": 0.67,
        "role": "sensitivity_not_candidate",
    },
]

CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
DEFICIT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_deficit_summary_{MODEL_TAG}.csv"
DEFICIT_TOP_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_deficit_top_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
POLICY_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_policy_audit_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def _simulate_profit_harvest(group: pd.DataFrame, threshold_mult: float, lock_fraction: float) -> pd.DataFrame:
    data = group.sort_values("date").copy()
    raw = pd.to_numeric(data["stage021_combo_account_equity"], errors="coerce").to_numpy(dtype=float)
    returns = np.zeros(len(raw))
    if len(raw) > 1:
        returns[1:] = raw[1:] / np.where(raw[:-1] == 0.0, np.nan, raw[:-1]) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

    trading_bucket = CAPITAL
    locked_cash = 0.0
    high_watermark = CAPITAL
    threshold = threshold_mult * CAPITAL
    total_wealth: list[float] = []
    bucket_values: list[float] = []
    locked_values: list[float] = []
    harvest_values: list[float] = []

    for daily_return in returns:
        pre_bucket = trading_bucket * (1.0 + daily_return)
        pre_total = pre_bucket + locked_cash
        harvest = 0.0
        if pre_total > high_watermark and pre_total > threshold:
            base = max(high_watermark, threshold)
            harvest = max(0.0, (pre_total - base) * lock_fraction)
            harvest = min(harvest, pre_bucket)
            pre_bucket -= harvest
            locked_cash += harvest
            pre_total = pre_bucket + locked_cash
        high_watermark = max(high_watermark, pre_total)
        trading_bucket = pre_bucket
        total_wealth.append(float(pre_total))
        bucket_values.append(float(pre_bucket))
        locked_values.append(float(locked_cash))
        harvest_values.append(float(harvest))

    result = data[["requested_start_month", "date"]].copy()
    result["equity"] = total_wealth
    result["trading_bucket"] = bucket_values
    result["locked_cash"] = locked_values
    result["daily_harvest"] = harvest_values
    result["threshold_mult"] = threshold_mult
    result["lock_fraction"] = lock_fraction
    return result


def _build_curves(stage021_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    policy_rows: list[dict[str, Any]] = []
    base = stage021_curves[["requested_start_month", "date", "stage021_combo_account_equity"]].copy()
    base.rename(columns={"stage021_combo_account_equity": "equity"}, inplace=True)
    base["variant"] = "stage021_combo_stage020_plus_consensus"
    base["trading_bucket"] = base["equity"]
    base["locked_cash"] = 0.0
    base["daily_harvest"] = 0.0
    base["threshold_mult"] = np.nan
    base["lock_fraction"] = np.nan
    base["policy_role"] = "baseline"
    frames.append(base)

    for policy in HARVEST_POLICIES:
        variant_frames: list[pd.DataFrame] = []
        for _, group in stage021_curves.groupby("requested_start_month", sort=True):
            simulated = _simulate_profit_harvest(group, policy["threshold_mult"], policy["lock_fraction"])
            simulated["variant"] = policy["variant"]
            simulated["policy_role"] = policy["role"]
            variant_frames.append(simulated)
        policy_frame = pd.concat(variant_frames, ignore_index=True, sort=False)
        frames.append(policy_frame)
        policy_rows.append(
            {
                "variant": policy["variant"],
                "policy_role": policy["role"],
                "threshold_mult": policy["threshold_mult"],
                "lock_fraction": policy["lock_fraction"],
                "total_harvest": float(policy_frame["daily_harvest"].sum()),
                "median_final_locked_cash": float(policy_frame.groupby("requested_start_month")["locked_cash"].last().median()),
                "median_final_trading_bucket": float(
                    policy_frame.groupby("requested_start_month")["trading_bucket"].last().median()
                ),
            }
        )
    curves = pd.concat(frames, ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    return curves, pd.DataFrame(policy_rows)


def _summary(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (variant, start), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        g = group.sort_values("date")
        equity = pd.to_numeric(g["equity"], errors="coerce")
        rows.append(
            {
                "variant": variant,
                "requested_start_month": start,
                "actual_start": pd.Timestamp(g["date"].iloc[0]).date().isoformat(),
                "actual_end": pd.Timestamp(g["date"].iloc[-1]).date().isoformat(),
                "trading_days": int(len(g)),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(_drawdown_pct(equity).min()),
                "sharpe": _sharpe_from_equity(equity),
                "final_locked_cash": float(pd.to_numeric(g["locked_cash"], errors="coerce").iloc[-1]),
                "final_trading_bucket": float(pd.to_numeric(g["trading_bucket"], errors="coerce").iloc[-1]),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["variant", "requested_start_month", "date", "equity"]].copy()
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009._run_audit(audit_curves)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(BASE_STAGE006_SUMMARY_PATH, encoding="utf-8-sig")
    base = base[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    rows: list[pd.DataFrame] = []
    for variant, group in summary.groupby("variant"):
        merged = base.merge(group[["requested_start_month", "total_return_pct"]], on="requested_start_month", how="inner")
        merged["variant"] = variant
        merged["return_ratio_vs_base_stage006"] = (
            merged["total_return_pct"] / merged["total_return_pct_base_stage006"].replace(0.0, np.nan)
        )
        merged["passes_80pct_retention_vs_base_stage006"] = merged["return_ratio_vs_base_stage006"].ge(0.80).astype(
            "int64"
        )
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _deficit_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    top_rows: list[dict[str, Any]] = []
    for (variant, source), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        g = group.sort_values("date").reset_index(drop=True)
        dates = pd.to_datetime(g["date"], errors="coerce")
        equity = pd.to_numeric(g["equity"], errors="coerce").to_numpy(dtype=float)
        start_indices = np.flatnonzero((dates >= OBJECTIVE_START_MIN) & (dates <= OBJECTIVE_START_MAX))
        neg_count = 0
        max_deficit = 0.0
        max_deficit_pct = 0.0
        top: list[dict[str, Any]] = []
        for i in start_indices:
            min_end_date = dates.iloc[i] + pd.Timedelta(days=MIN_PERIOD_DAYS + 1)
            j0 = int(np.searchsorted(dates.to_numpy(dtype="datetime64[ns]"), np.datetime64(min_end_date), side="left"))
            if j0 >= len(g):
                continue
            end_values = equity[j0:]
            deficits = equity[i] - end_values
            negative_mask = deficits > 0.0
            if not bool(negative_mask.any()):
                continue
            count = int(negative_mask.sum())
            neg_count += count
            local_idx = int(np.nanargmax(np.where(negative_mask, deficits, np.nan)))
            deficit = float(deficits[local_idx])
            end_idx = j0 + local_idx
            deficit_pct = float(deficit / equity[i] * 100.0) if equity[i] else np.nan
            if deficit > max_deficit:
                max_deficit = deficit
                max_deficit_pct = deficit_pct
            top.append(
                {
                    "variant": variant,
                    "source_start_month": source,
                    "start_date": pd.Timestamp(dates.iloc[i]).date().isoformat(),
                    "end_date": pd.Timestamp(dates.iloc[end_idx]).date().isoformat(),
                    "start_equity": float(equity[i]),
                    "end_equity": float(equity[end_idx]),
                    "deficit": deficit,
                    "deficit_pct_of_start": deficit_pct,
                    "negative_end_count_from_start": count,
                }
            )
        top_sorted = sorted(top, key=lambda item: item["deficit"], reverse=True)[:20]
        top_rows.extend(top_sorted)
        summary_rows.append(
            {
                "variant": variant,
                "source_start_month": source,
                "negative_window_count": int(neg_count),
                "max_deficit": float(max_deficit),
                "max_deficit_pct_of_start": float(max_deficit_pct),
            }
        )
    summary = pd.DataFrame(summary_rows)
    total = (
        summary.groupby("variant", as_index=False)
        .agg(
            negative_window_count=("negative_window_count", "sum"),
            max_deficit=("max_deficit", "max"),
            max_deficit_pct_of_start=("max_deficit_pct_of_start", "max"),
        )
        .assign(source_start_month="ALL")
    )
    summary = pd.concat([total, summary], ignore_index=True, sort=False)
    top_df = pd.DataFrame(top_rows).sort_values(["variant", "deficit"], ascending=[True, False]).reset_index(drop=True)
    return summary, top_df


def _policy_audit(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    deficit_summary: pd.DataFrame,
    policy_table: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")].copy()
    for variant, group in summary.groupby("variant"):
        all_frame = all_scope[all_scope["variant"].eq(variant)]
        final_frame = final_scope[final_scope["variant"].eq(variant)]
        retention_frame = retention[retention["variant"].eq(variant)]
        deficit = deficit_summary[
            deficit_summary["variant"].eq(variant) & deficit_summary["source_start_month"].eq("ALL")
        ]
        policy = policy_table[policy_table["variant"].eq(variant)]
        rows.append(
            {
                "variant": variant,
                "policy_role": str(policy["policy_role"].iloc[0]) if not policy.empty else "baseline",
                "threshold_mult": float(policy["threshold_mult"].iloc[0]) if not policy.empty else np.nan,
                "lock_fraction": float(policy["lock_fraction"].iloc[0]) if not policy.empty else np.nan,
                "negative_window_count": int(all_frame["negative_count"].sum()) if not all_frame.empty else 0,
                "min_return_pct": float(all_frame["min_return_pct"].min()) if not all_frame.empty else np.nan,
                "to_final_negative_count": int(final_frame["negative_count"].sum()) if not final_frame.empty else 0,
                "to_final_min_return_pct": float(final_frame["min_return_pct"].min()) if not final_frame.empty else np.nan,
                "min_total_return_pct": float(group["total_return_pct"].min()),
                "median_total_return_pct": float(group["total_return_pct"].median()),
                "worst_max_dd_pct": float(group["max_dd_pct"].min()),
                "median_max_dd_pct": float(group["max_dd_pct"].median()),
                "retention_pass_count": int(retention_frame["passes_80pct_retention_vs_base_stage006"].sum()),
                "retention_rows": int(len(retention_frame)),
                "max_deficit": float(deficit["max_deficit"].iloc[0]) if not deficit.empty else np.nan,
                "max_deficit_pct_of_start": float(deficit["max_deficit_pct_of_start"].iloc[0])
                if not deficit.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("negative_window_count").reset_index(drop=True)


def _plot(policy_audit: pd.DataFrame, curves: pd.DataFrame, deficit_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    ax = axes[0, 0]
    plot = policy_audit.sort_values("negative_window_count")
    x = np.arange(len(plot))
    ax.bar(x, plot["negative_window_count"], color="#2563eb")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["variant"].tolist(), rotation=35, ha="right", fontsize=8)
    ax.set_title("Strict >1Y Negative Windows")
    ax.set_ylabel("negative windows")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    ax.bar(x, plot["max_deficit"], color="#dc2626")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["variant"].tolist(), rotation=35, ha="right", fontsize=8)
    ax.set_title("Max Absolute Deficit to Break Even")
    ax.set_ylabel("cash")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    show_variants = ["stage021_combo_stage020_plus_consensus", "stage022_harvest_3x_lock50_primary"]
    for variant in show_variants:
        frame = curves[curves["variant"].eq(variant)]
        for start, group in frame.groupby("requested_start_month"):
            group = group.sort_values("date")
            ax.plot(group["date"], group["equity"], linewidth=0.8, alpha=0.65, label=f"{variant}:{start}")
    ax.axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Baseline vs Primary Harvest Total Wealth")
    ax.set_ylabel("wealth")
    ax.grid(True, alpha=0.25)

    ax = axes[1, 1]
    all_deficit = deficit_summary[deficit_summary["source_start_month"].eq("ALL")].copy()
    ax.scatter(all_deficit["negative_window_count"], all_deficit["max_deficit_pct_of_start"], s=70, color="#7c3aed")
    for _, row in all_deficit.iterrows():
        ax.annotate(str(row["variant"]).replace("stage022_", "").replace("stage021_", ""), (row["negative_window_count"], row["max_deficit_pct_of_start"]), fontsize=7)
    ax.set_title("Deficit Severity vs Count")
    ax.set_xlabel("negative windows")
    ax.set_ylabel("max deficit % of start")
    ax.grid(True, alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(policy_audit: pd.DataFrame) -> dict[str, Any]:
    baseline = policy_audit[policy_audit["variant"].eq("stage021_combo_stage020_plus_consensus")]
    primary = policy_audit[policy_audit["variant"].eq("stage022_harvest_3x_lock50_primary")]
    best = policy_audit.sort_values("negative_window_count").iloc[0]
    baseline_negative = int(baseline["negative_window_count"].iloc[0]) if not baseline.empty else 0
    primary_negative = int(primary["negative_window_count"].iloc[0]) if not primary.empty else 0
    primary_retention_pass = (
        int(primary["retention_pass_count"].iloc[0]) == int(primary["retention_rows"].iloc[0]) if not primary.empty else False
    )
    if primary_negative == 0 and primary_retention_pass:
        decision = "stage022_primary_proxy_meets_goal_requires_true_engine"
    elif primary_negative < baseline_negative and primary_retention_pass:
        decision = "stage022_profit_harvest_reduces_negative_windows_but_not_goal"
    else:
        decision = "stage022_profit_harvest_not_enough"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "account_layer_daily_return_profit_harvest_proxy",
        "decision": decision,
        "baseline_negative_window_count": baseline_negative,
        "primary_negative_window_count": primary_negative,
        "primary_min_return_pct": float(primary["min_return_pct"].iloc[0]) if not primary.empty else np.nan,
        "primary_to_final_min_return_pct": float(primary["to_final_min_return_pct"].iloc[0]) if not primary.empty else np.nan,
        "primary_retention_pass_count": int(primary["retention_pass_count"].iloc[0]) if not primary.empty else 0,
        "primary_retention_rows": int(primary["retention_rows"].iloc[0]) if not primary.empty else 0,
        "best_variant": str(best["variant"]),
        "best_negative_window_count": int(best["negative_window_count"]),
        "best_min_return_pct": float(best["min_return_pct"]),
        "best_retention_pass_count": int(best["retention_pass_count"]),
        "best_retention_rows": int(best["retention_rows"]),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Volatility targeting, drawdown control, and dynamic lock-in are common CTA account-layer ideas, "
            "but literature and prior repo evidence both warn that protection usually trades away participation. "
            "Stage022 is therefore a feasibility audit, not a promoted trading rule."
        ),
        "overfit_reflection_before": (
            "否。Stage022 先审计账户层数学缺口和一组标记为 sensitivity 的锁盈代理，不把最优参数当候选。"
        ),
        "continue_value_before": (
            "有。剩余失败来自路径回撤和恢复时间，账户层生存线比继续调 AI topN/标签更贴近目标失败项。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有根据 sensitivity 最优项晋级；若挑最少负窗口的阈值直接上线会过拟合。"
        ),
        "continue_value_after": (
            "有，但利润锁定本身不足以达标。下一步应转向更早的风险前置信号、真实引擎级暂停/恢复机制或非价格外生信息。"
        ),
        "outputs": {
            "curves": str(CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "deficit_summary": str(DEFICIT_SUMMARY_PATH),
            "deficit_top_windows": str(DEFICIT_TOP_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "policy_audit": str(POLICY_AUDIT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    policy_audit: pd.DataFrame,
    deficit_summary: pd.DataFrame,
    top_deficits: pd.DataFrame,
    retention: pd.DataFrame,
) -> None:
    lines = [
        "# Stage022 账户层生存线与利润锁定可行性审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读账户层代理；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 波动目标、drawdown control、dynamic stop lock-in 都是 CTA/趋势策略常见账户层思路。",
        "- 这些方法通常在保护回撤和保留右尾之间交易，不应通过参数网格挑最好看的结果。",
        "- 本阶段把 `3x本金后锁定新增高水位利润50%` 作为 primary，只把其他阈值当 sensitivity。",
        "",
        "## 核心结果",
        "",
        f"- Stage021 baseline 严格负窗口：`{decision['baseline_negative_window_count']}`。",
        f"- primary harvest 严格负窗口：`{decision['primary_negative_window_count']}`；最差 `{decision['primary_min_return_pct']:.4f}%`。",
        f"- primary 到 `2026-06-30` 最差：`{decision['primary_to_final_min_return_pct']:.4f}%`。",
        f"- primary 收益保留：`{decision['primary_retention_pass_count']}/{decision['primary_retention_rows']}`。",
        f"- sensitivity 最少负窗口版本：`{decision['best_variant']}`，负窗口 `{decision['best_negative_window_count']}`，最差 `{decision['best_min_return_pct']:.4f}%`。",
        "",
        "## 策略审计表",
        "",
        _md_table(policy_audit, max_rows=20),
        "",
        "## 缺口汇总",
        "",
        _md_table(deficit_summary[deficit_summary["source_start_month"].eq("ALL")], max_rows=20),
        "",
        "## 最大缺口窗口",
        "",
        _md_table(top_deficits, max_rows=40),
        "",
        "## 收益保留样本",
        "",
        _md_table(retention.head(60), max_rows=60),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in decision["outputs"].items():
        lines.append(f"- {name}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], policy_audit: pd.DataFrame, deficit_summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage022_account_survival_profit_harvest_audit.md"
    lines = [
        "# Stage022 账户层生存线与利润锁定可行性审计",
        "",
        f"- 记录时间：`{timestamp:%Y-%m-%dT%H:%M}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        "- 新增参数：primary `profit_harvest_threshold=3x capital`、`lock_fraction=0.50`；另有 sensitivity 版本仅作可行性观察。",
        "- 修改参数：无，Stage021/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 本阶段只读账户层代理，不新增真实交易规则、不接实盘。",
        "",
        "## 调研和判断结论",
        "",
        "- 外部资料支持账户层波动目标、drawdown control、dynamic lock-in，但也提示保护会牺牲参与度。",
        "- 当前结果证明利润锁定能减少部分负窗口，但不能让所有 `>1` 年窗口转正。",
        "- sensitivity 最好项也未达标，因此不能把阈值/比例继续扫成候选。",
        "",
        "## 代理结果",
        "",
        f"- Stage021 baseline 严格负窗口：`{decision['baseline_negative_window_count']}`。",
        f"- primary 严格负窗口：`{decision['primary_negative_window_count']}`。",
        f"- primary 严格最差收益：`{decision['primary_min_return_pct']:.4f}%`。",
        f"- primary 到 `2026-06-30` 最差：`{decision['primary_to_final_min_return_pct']:.4f}%`。",
        f"- primary 收益保留：`{decision['primary_retention_pass_count']}/{decision['primary_retention_rows']}`。",
        f"- sensitivity 最少负窗口：`{decision['best_variant']}` = `{decision['best_negative_window_count']}`，最差 `{decision['best_min_return_pct']:.4f}%`。",
        "",
        "## 策略审计表",
        "",
        _md_table(policy_audit, max_rows=20),
        "",
        "## 缺口汇总",
        "",
        _md_table(deficit_summary[deficit_summary["source_start_month"].eq("ALL")], max_rows=20),
        "",
        "## 文件",
        "",
    ]
    for name, output_path in decision["outputs"].items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(
        [
            "",
            "## 后续规划和 TODO",
            "",
            "- 不继续扫利润锁定阈值/比例；下一步找更早的风险前置信号或真实引擎暂停/恢复机制。",
            "- 若继续账户层路线，需要验证真实成交、保证金、暂停后重启、右尾保留和实盘可执行边界。",
            "",
            "## 反思",
            "",
            f"- 过拟合反思：{decision['overfit_reflection_after']}",
            f"- 继续价值反思：{decision['continue_value_after']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stage021 = pd.read_csv(STAGE021_CURVES_PATH, encoding="utf-8-sig", parse_dates=["date"])
    stage021["requested_start_month"] = stage021["requested_start_month"].astype(str)
    curves, policy_table = _build_curves(stage021)
    summary = _summary(curves)
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention(summary)
    deficit_summary, top_deficits = _deficit_audit(curves)
    policy_audit = _policy_audit(summary, aggregate, retention, deficit_summary, policy_table)
    decision = _decision(policy_audit)
    _plot(policy_audit, curves, deficit_summary)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    deficit_summary.to_csv(DEFICIT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_deficits.to_csv(DEFICIT_TOP_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    policy_audit.to_csv(POLICY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, policy_audit, deficit_summary, top_deficits, retention)
    stage_record = _write_stage_record(decision, policy_audit, deficit_summary)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
