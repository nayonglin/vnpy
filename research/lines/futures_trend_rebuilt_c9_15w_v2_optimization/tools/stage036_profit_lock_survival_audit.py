from __future__ import annotations

from dataclasses import asdict, dataclass
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
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage017_fixed_sleeve_blend_audit as s017


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage036"
MODEL_TAG = "stage036_profit_lock_survival_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage036_profit_lock_survival_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage036_profit_lock_survival_audit"
STAGES_DIR = LINE_DIR / "stages"

C9_CURVES_PATH = s017.C9_CURVES_PATH
PROFIT_LOCK_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_c9_{MODEL_TAG}.csv"
GOAL_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_table_{MODEL_TAG}.csv"
TRANSFER_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transfer_events_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ABSOLUTE_EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_curves_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

INITIAL_CAPITAL = 150_000.0
ANALYSIS_END = pd.Timestamp("2026-06-30")
START_MONTHS = s017.START_MONTHS
OBJECTIVE_START_MIN = s017.OBJECTIVE_START_MIN
OBJECTIVE_START_MAX = s017.OBJECTIVE_START_MAX
MIN_PERIOD_CALENDAR_DAYS = s017.MIN_PERIOD_CALENDAR_DAYS


@dataclass(frozen=True)
class ProfitLockPolicy:
    variant: str
    threshold_multiple: float
    transfer_fraction: float
    locked_fraction: float
    reserve_fraction: float
    note: str = ""


POLICIES: tuple[ProfitLockPolicy, ...] = (
    ProfitLockPolicy(
        variant="profit_tranche_norm6x",
        threshold_multiple=6.0,
        transfer_fraction=0.70,
        locked_fraction=0.70,
        reserve_fraction=0.30,
        note="Stage232 3m/500k threshold normalized to 6x for 150k; aggressive profit lock.",
    ),
    ProfitLockPolicy(
        variant="balanced_tranche_norm10x",
        threshold_multiple=10.0,
        transfer_fraction=0.50,
        locked_fraction=0.60,
        reserve_fraction=0.40,
        note="Stage232 5m/500k threshold normalized to 10x for 150k; balanced profit lock.",
    ),
)


def _json_safe(value: Any) -> Any:
    return s017._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s017._md_table(frame, max_rows=max_rows)


def _month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _load_c9_curves() -> pd.DataFrame:
    data = _read_csv(C9_CURVES_PATH)
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    wanted = {_month_text(start) for start in START_MONTHS}
    data = data[data["requested_start_month"].isin(wanted)].copy()
    return data[["requested_start_month", "date", "account_equity"]].reset_index(drop=True)


def _validate_policy(policy: ProfitLockPolicy) -> None:
    if policy.threshold_multiple <= 0.0:
        raise ValueError(f"threshold_multiple must be positive: {policy}")
    if not 0.0 <= policy.transfer_fraction <= 1.0:
        raise ValueError(f"transfer_fraction must be in [0, 1]: {policy}")
    if policy.locked_fraction < 0.0 or policy.reserve_fraction < 0.0:
        raise ValueError(f"bucket fractions must be non-negative: {policy}")
    if abs((policy.locked_fraction + policy.reserve_fraction) - 1.0) > 1e-9:
        raise ValueError(f"locked_fraction + reserve_fraction must equal 1: {policy}")


def _month_end_flags(dates: pd.Series) -> pd.Series:
    periods = pd.to_datetime(dates, errors="coerce").dt.to_period("M")
    next_periods = periods.shift(-1)
    return periods.ne(next_periods).fillna(True)


def apply_profit_lock_policy(curve: pd.DataFrame, policy: ProfitLockPolicy) -> pd.DataFrame:
    _validate_policy(policy)
    data = curve.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data = data.dropna(subset=["requested_start_month", "date", "account_equity"]).copy()

    rows: list[dict[str, Any]] = []
    for start_month, group in data.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        if g.empty:
            continue
        base_equity = pd.to_numeric(g["account_equity"], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(base_equity[0]) or base_equity[0] == 0.0:
            continue
        factors = np.ones(len(g), dtype=float)
        if len(g) > 1:
            previous = base_equity[:-1]
            current = base_equity[1:]
            raw = current / np.where(previous == 0.0, np.nan, previous)
            factors[1:] = np.where(np.isfinite(raw), raw, 1.0)

        month_ends = _month_end_flags(g["date"]).to_numpy(dtype=bool)
        source_initial = float(base_equity[0])
        threshold_equity = source_initial * float(policy.threshold_multiple)
        production_equity = source_initial
        locked_equity = 0.0
        reserve_equity = 0.0
        cumulative_transferred = 0.0

        for idx, item in g.iterrows():
            if idx > 0:
                production_equity *= float(factors[idx])

            transfer_amount = 0.0
            if bool(month_ends[idx]) and production_equity > threshold_equity:
                excess = production_equity - threshold_equity
                transfer_amount = excess * float(policy.transfer_fraction)
                production_equity -= transfer_amount
                locked_equity += transfer_amount * float(policy.locked_fraction)
                reserve_equity += transfer_amount * float(policy.reserve_fraction)
                cumulative_transferred += transfer_amount

            account_equity = production_equity + locked_equity + reserve_equity
            rows.append(
                {
                    "requested_start_month": str(start_month),
                    "date": pd.Timestamp(item["date"]),
                    "variant": policy.variant,
                    "base_account_equity": float(item["account_equity"]),
                    "base_nav": float(item["account_equity"]) / source_initial,
                    "account_equity": float(account_equity),
                    "nav": float(account_equity / source_initial),
                    "production_equity": float(production_equity),
                    "locked_equity": float(locked_equity),
                    "reserve_equity": float(reserve_equity),
                    "threshold_equity": float(threshold_equity),
                    "transfer_amount": float(transfer_amount),
                    "cumulative_transferred": float(cumulative_transferred),
                    "is_month_end": bool(month_ends[idx]),
                    "threshold_multiple": float(policy.threshold_multiple),
                    "transfer_fraction": float(policy.transfer_fraction),
                    "locked_fraction": float(policy.locked_fraction),
                    "reserve_fraction": float(policy.reserve_fraction),
                    "source_initial_equity": float(source_initial),
                    "stage": STAGE,
                    "model_tag": MODEL_TAG,
                    "line_id": LINE_ID,
                    "policy_note": policy.note,
                }
            )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month", "date"]).reset_index(drop=True)


def build_profit_lock_curves(
    base_curves: pd.DataFrame,
    policies: tuple[ProfitLockPolicy, ...] = POLICIES,
) -> pd.DataFrame:
    base = s017._normalize_curve(base_curves).copy()
    base["variant"] = "c9_100"
    base["base_account_equity"] = base["account_equity"]
    base["base_nav"] = base["nav"]
    base["production_equity"] = base["account_equity"]
    base["locked_equity"] = 0.0
    base["reserve_equity"] = 0.0
    base["threshold_equity"] = np.nan
    base["transfer_amount"] = 0.0
    base["cumulative_transferred"] = 0.0
    base["is_month_end"] = _month_end_flags(base["date"]).to_numpy(dtype=bool)
    base["threshold_multiple"] = np.nan
    base["transfer_fraction"] = 0.0
    base["locked_fraction"] = 0.0
    base["reserve_fraction"] = 0.0
    base["stage"] = STAGE
    base["model_tag"] = MODEL_TAG
    base["line_id"] = LINE_ID
    base["policy_note"] = "Baseline current rebuilt C9/15w Stage167 curve."

    parts = [base]
    for policy in policies:
        parts.append(apply_profit_lock_policy(base_curves, policy))
    return pd.concat(parts, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True)


def summarize_curve(curve: pd.DataFrame, *, variant: str, requested_start_month: str) -> dict[str, Any]:
    data = curve.sort_values("date").drop_duplicates("date").copy()
    equity = pd.to_numeric(data["account_equity"], errors="coerce")
    start_equity = float(equity.iloc[0])
    end_equity = float(equity.iloc[-1])
    dd = s017._drawdown_pct(equity)
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "variant": variant,
        "requested_start_month": requested_start_month,
        "start_date": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / start_equity - 1.0) * 100.0) if start_equity else np.nan,
        "max_drawdown_pct": float(dd.min()),
        "sharpe": s017._sharpe_from_equity(equity),
        "min_equity": float(equity.min()),
        "total_transferred": float(pd.to_numeric(data["transfer_amount"], errors="coerce").fillna(0.0).sum()),
        "ending_locked_equity": float(pd.to_numeric(data["locked_equity"], errors="coerce").fillna(0.0).iloc[-1]),
        "ending_reserve_equity": float(pd.to_numeric(data["reserve_equity"], errors="coerce").fillna(0.0).iloc[-1]),
    }


def _summarize_all(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (variant, start_month), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        rows.append(summarize_curve(group, variant=str(variant), requested_start_month=str(start_month)))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def build_goal_table(aggregate: pd.DataFrame, retention: pd.DataFrame) -> pd.DataFrame:
    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(
            all_gt1y_window_count=("window_count", "sum"),
            all_gt1y_negative_count=("negative_count", "sum"),
            all_gt1y_min_return_pct=("min_return_pct", "min"),
        )
    )
    final_scope = (
        aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        .groupby("variant", as_index=False)
        .agg(
            to_final_window_count=("window_count", "sum"),
            to_final_negative_count=("negative_count", "sum"),
            to_final_min_return_pct=("min_return_pct", "min"),
        )
    )
    ret_scope = retention.groupby("variant", as_index=False).agg(
        retention_80pct_pass_count=("passes_80pct_retention", "sum"),
        retention_rows=("passes_80pct_retention", "size"),
        min_retention=("return_retention_vs_c9", "min"),
    )
    goal = all_scope.merge(final_scope, on="variant", how="outer").merge(ret_scope, on="variant", how="outer")
    for column in [
        "all_gt1y_window_count",
        "all_gt1y_negative_count",
        "to_final_window_count",
        "to_final_negative_count",
        "retention_80pct_pass_count",
        "retention_rows",
    ]:
        goal[column] = pd.to_numeric(goal[column], errors="coerce").fillna(0).astype("int64")
    goal["min_retention"] = pd.to_numeric(goal["min_retention"], errors="coerce")
    goal["objective_pass"] = (
        goal["all_gt1y_window_count"].gt(0)
        & goal["all_gt1y_negative_count"].eq(0)
        & goal["to_final_window_count"].gt(0)
        & goal["to_final_negative_count"].eq(0)
        & goal["retention_rows"].gt(0)
        & goal["retention_80pct_pass_count"].eq(goal["retention_rows"])
        & goal["min_retention"].ge(0.80)
    )
    return goal.sort_values(
        ["objective_pass", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
        ascending=[False, True, False, False],
    ).reset_index(drop=True)


def make_profit_lock_decision(goal_table: pd.DataFrame) -> dict[str, Any]:
    goal = goal_table.copy()
    if goal.empty:
        raise ValueError("goal_table is empty")

    non_c9 = goal[~goal["variant"].astype(str).eq("c9_100")].copy()
    pass_rows = non_c9[non_c9["objective_pass"].astype(bool)].copy()
    if not pass_rows.empty:
        best = pass_rows.sort_values(
            ["all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
            ascending=[True, False, False],
        ).iloc[0].to_dict()
        decision = "stage036_profit_lock_survival_has_account_layer_candidate_needs_true_cash_ledger"
        reason = (
            "利润兑现资金层在曲线代理中通过目标门，但它只是账户现金账本候选，不能直接等同于策略信号或真实引擎。"
        )
        account_layer_candidate_allowed = True
    else:
        best = non_c9.sort_values(
            ["all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
            ascending=[True, False, False],
        ).iloc[0].to_dict()
        decision = "stage036_profit_lock_survival_not_goal_keep_readonly"
        reason = "预声明利润兑现资金层未能同时清零密集 >1 年负窗口并保留 C9 80% 收益。"
        account_layer_candidate_allowed = False

    c9_rows = goal[goal["variant"].astype(str).eq("c9_100")]
    c9_row = c9_rows.iloc[0].to_dict() if not c9_rows.empty else {}
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "decision_reason": reason,
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "start_months": [_month_text(item) for item in START_MONTHS],
        "objective_start_min": OBJECTIVE_START_MIN.date().isoformat(),
        "objective_start_max": OBJECTIVE_START_MAX.date().isoformat(),
        "min_period_calendar_days": MIN_PERIOD_CALENDAR_DAYS,
        "policies": [asdict(policy) for policy in POLICIES],
        "c9_all_gt1y_negative_count": int(c9_row.get("all_gt1y_negative_count", 0)),
        "c9_all_gt1y_min_return_pct": float(c9_row.get("all_gt1y_min_return_pct", np.nan)),
        "best_non_c9_variant": str(best["variant"]),
        "best_non_c9_all_gt1y_negative_count": int(best["all_gt1y_negative_count"]),
        "best_non_c9_all_gt1y_min_return_pct": float(best["all_gt1y_min_return_pct"]),
        "best_non_c9_min_retention": float(best["min_retention"]),
        "objective_pass_variant_count": int(goal["objective_pass"].astype(bool).sum()),
        "account_layer_candidate_allowed": bool(account_layer_candidate_allowed),
        "immediate_strategy_candidate_count": 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "formal_ab_triggered": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "is_independent_daily_cold_start": False,
        "external_research_judgment": (
            "趋势跟随的长期优势来自凸性右尾和分散化；资金层利润兑现可以保护已经兑现的高水位，"
            "但不能创造 alpha，也不能保护首次触发前的冷启动回撤。"
        ),
        "overfit_reflection_before": (
            "否。Stage036 只用旧 Stage232 资金分层思路按 15w 做倍数归一，不按具体坏窗口、品种、月份或方向扫参。"
        ),
        "overfit_reflection_after": (
            "若继续微调阈值倍数、转出比例或锁定/备用比例以刚好修复某些窗口，就是过拟合；本阶段只评价预声明形状。"
        ),
        "continue_value_before": (
            "有。当前没有新的 schema-ready PIT 数据时，账户外层是少数不改 AI/信号也能改善生存性的方向。"
        ),
        "continue_value_after": (
            "若未过目标门，继续扫资金层细参价值低；若过门，也必须先做真实现金账本和出入金约束，而不是改策略信号。"
        ),
        "variant_goal_table": goal.to_dict(orient="records"),
    }


def _extract_transfer_events(curves: pd.DataFrame) -> pd.DataFrame:
    events = curves[pd.to_numeric(curves["transfer_amount"], errors="coerce").fillna(0.0).gt(0.0)].copy()
    columns = [
        "variant",
        "requested_start_month",
        "date",
        "base_account_equity",
        "production_equity",
        "locked_equity",
        "reserve_equity",
        "threshold_equity",
        "transfer_amount",
        "cumulative_transferred",
    ]
    return events[columns].sort_values(["variant", "requested_start_month", "date"]).reset_index(drop=True)


def _plot_summary(summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    summary_agg = summary.groupby("variant", as_index=False).agg(
        median_return_pct=("total_return_pct", "median"),
        worst_dd_pct=("max_drawdown_pct", "min"),
        ending_locked_equity=("ending_locked_equity", "median"),
    )
    axes[0, 0].bar(summary_agg["variant"], summary_agg["median_return_pct"], color="#2563eb")
    axes[0, 0].set_title("Median start-to-final return")
    axes[0, 0].tick_params(axis="x", rotation=25)
    axes[0, 0].grid(True, axis="y", alpha=0.25)

    axes[0, 1].bar(summary_agg["variant"], summary_agg["worst_dd_pct"], color="#dc2626")
    axes[0, 1].set_title("Worst max drawdown")
    axes[0, 1].tick_params(axis="x", rotation=25)
    axes[0, 1].grid(True, axis="y", alpha=0.25)

    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(negative_count=("negative_count", "sum"), window_count=("window_count", "sum"))
    )
    all_scope["negative_rate_pct"] = all_scope["negative_count"] / all_scope["window_count"].replace(0, np.nan) * 100.0
    axes[1, 0].bar(all_scope["variant"], all_scope["negative_rate_pct"], color="#f97316")
    axes[1, 0].set_title("Dense >1Y negative window rate")
    axes[1, 0].tick_params(axis="x", rotation=25)
    axes[1, 0].grid(True, axis="y", alpha=0.25)

    ret = retention.groupby("variant", as_index=False).agg(
        pass_count=("passes_80pct_retention", "sum"),
        rows=("passes_80pct_retention", "size"),
    )
    ret["pass_rate_pct"] = ret["pass_count"] / ret["rows"].replace(0, np.nan) * 100.0
    axes[1, 1].bar(ret["variant"], ret["pass_rate_pct"], color="#16a34a")
    axes[1, 1].set_title("80% full-return retention pass rate vs C9")
    axes[1, 1].tick_params(axis="x", rotation=25)
    axes[1, 1].grid(True, axis="y", alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_absolute_equity_curves(curves: pd.DataFrame, decision: dict[str, Any]) -> None:
    best_variant = str(decision["best_non_c9_variant"])
    selected_variants = ["c9_100"] if best_variant == "c9_100" else ["c9_100", best_variant]
    start_months = [month for month in [_month_text(item) for item in START_MONTHS] if month.endswith("-01")]
    if not start_months:
        start_months = sorted(curves["requested_start_month"].dropna().astype(str).unique())[:6]

    fig, axes = plt.subplots(len(start_months), 1, figsize=(15, max(3.0 * len(start_months), 6.0)), sharex=False)
    if len(start_months) == 1:
        axes = [axes]
    colors = {"c9_100": "#111827", best_variant: "#2563eb"}
    for ax, start_month in zip(axes, start_months):
        subset = curves[
            curves["requested_start_month"].astype(str).eq(start_month)
            & curves["variant"].astype(str).isin(selected_variants)
        ].copy()
        for variant, group in subset.groupby("variant", sort=False):
            data = group.sort_values("date")
            ax.plot(
                pd.to_datetime(data["date"]),
                pd.to_numeric(data["account_equity"], errors="coerce"),
                label=str(variant),
                linewidth=1.7,
                color=colors.get(str(variant), "#6b7280"),
            )
        ax.set_title(f"Absolute account equity, source start {start_month}")
        ax.set_ylabel("CNY")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left")
    fig.suptitle("Stage036 absolute account equity curves", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(ABSOLUTE_EQUITY_CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
    goal_table: pd.DataFrame,
    transfer_events: pd.DataFrame,
) -> None:
    text = f"""# Stage036 利润兑现资金层生存线审计

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`
- 阶段性质：基于当前重建 C9/15w Stage167 曲线的账户外层只读审计；不改 AI、不改信号、不连接 CTP、不调用订单 API。

## 方法

- 基础输入：`{C9_CURVES_PATH}`
- 分析终点：`{decision["analysis_end"]}`，即当前 Stage167 曲线的已完成终点；不是 2026-07-02 盘中即时重跑。
- 生产桶每日承受 C9 曲线收益；月末若生产桶超过阈值，将超额的一部分转入锁定桶和备用桶。
- 锁定桶/备用桶不再承受 C9 日收益，因此只能保护已经兑现过的高水位，不能保护首次触发前的冷启动回撤。
- 目标门：`{OBJECTIVE_START_MIN.date()}` 到 `{OBJECTIVE_START_MAX.date()}` 任意曲线内交易日起点，所有大于一年窗口正收益，同时全周期收益保留 C9 的 80% 以上。

## 目标门汇总

{_md_table(goal_table, max_rows=20)}

## 多起点摘要

{_md_table(summary, max_rows=40)}

## 聚合窗口

{_md_table(aggregate, max_rows=60)}

## 80% 收益保留

{_md_table(retention, max_rows=60)}

## 转出事件样例

{_md_table(transfer_events.head(40), max_rows=40) if not transfer_events.empty else "_无转出事件_"}

## 最差窗口

{_md_table(worst, max_rows=40)}

## 图表

- 汇总图：`{SUMMARY_CHART_PATH}`
- 绝对资金曲线：`{ABSOLUTE_EQUITY_CHART_PATH}`

## 结论

- {decision["decision_reason"]}
- 本阶段不改变线上 C9、AI 池、开仓日 0.5R 实时止损重试逻辑、邮件或 CTP 执行链路。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
    goal_table: pd.DataFrame,
    transfer_events: pd.DataFrame,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage036_profit_lock_survival_audit.md"
    text = f"""# Stage036 利润兑现资金层生存线审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：当前重建 C9/15w 的账户外层只读审计；不是策略信号、不是 true engine、不是实盘执行改动
- 是否重要突破：{'是' if decision['account_layer_candidate_allowed'] else '否'}
- 是否触发A/B：否

## 外部调研与判断

- 参考 Rob Carver/pysystemtrade 对 capital correction、趋势跟随分散化与收益路径治理的讨论，以及 time-series momentum/managed futures 研究。
- 我的判断：利润兑现/资金分层符合“保住已赚到的右尾”的账户管理直觉，但不能创造信号质量；如果亏损发生在首次锁定前，它没有保护能力。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage036_profit_lock_survival_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage036_profit_lock_survival_audit.py`
- 新增参数：`POLICIES={json.dumps([asdict(policy) for policy in POLICIES], ensure_ascii=False)}`
- 修改参数：无正式策略参数修改
- 删除参数：无
- 新增图表：汇总图、绝对资金曲线图

## 结果

- C9 密集 >1 年负窗口数：`{decision["c9_all_gt1y_negative_count"]}`
- C9 密集 >1 年最差收益：`{decision["c9_all_gt1y_min_return_pct"]:.4f}%`
- 最优非 C9 资金层：`{decision["best_non_c9_variant"]}`
- 最优非 C9 密集 >1 年负窗口数：`{decision["best_non_c9_all_gt1y_negative_count"]}`
- 最优非 C9 密集 >1 年最差收益：`{decision["best_non_c9_all_gt1y_min_return_pct"]:.4f}%`
- 最优非 C9 最小收益保留：`{decision["best_non_c9_min_retention"]:.4f}`
- 目标通过 variant 数：`{decision["objective_pass_variant_count"]}`
- 转出事件数：`{len(transfer_events)}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## 目标门汇总

{_md_table(goal_table, max_rows=20)}

## 多起点摘要

{_md_table(summary, max_rows=40)}

## 聚合窗口

{_md_table(aggregate, max_rows=60)}

## 80% 收益保留

{_md_table(retention, max_rows=60)}

## 转出事件样例

{_md_table(transfer_events.head(40), max_rows=40) if not transfer_events.empty else "_无转出事件_"}

## 最差窗口

{_md_table(worst, max_rows=40)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- curves: `{PROFIT_LOCK_CURVES_PATH}`
- summary: `{SUMMARY_PATH}`
- aggregate: `{AGGREGATE_PATH}`
- to_final: `{TO_FINAL_PATH}`
- fixed_horizon: `{FIXED_HORIZON_PATH}`
- worst_windows: `{WORST_WINDOWS_PATH}`
- retention: `{RETENTION_PATH}`
- goal_table: `{GOAL_TABLE_PATH}`
- transfer_events: `{TRANSFER_EVENTS_PATH}`
- summary_chart: `{SUMMARY_CHART_PATH}`
- absolute_equity_chart: `{ABSOLUTE_EQUITY_CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c9_curves = _load_c9_curves()
    curves = build_profit_lock_curves(c9_curves, POLICIES)
    summary = _summarize_all(curves)
    aggregate, to_final, fixed, worst = s017.audit_goal_windows(curves)
    retention = s017.retention_vs_c9(summary)
    goal_table = build_goal_table(aggregate, retention)
    decision = make_profit_lock_decision(goal_table)
    transfer_events = _extract_transfer_events(curves)

    _plot_summary(summary, aggregate, retention)
    _plot_absolute_equity_curves(curves, decision)
    _write_report(decision, summary, aggregate, worst, retention, goal_table, transfer_events)
    stage_record = _write_stage_record(decision, summary, aggregate, worst, retention, goal_table, transfer_events)

    curves.to_csv(PROFIT_LOCK_CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    goal_table.to_csv(GOAL_TABLE_PATH, index=False, encoding="utf-8-sig")
    transfer_events.to_csv(TRANSFER_EVENTS_PATH, index=False, encoding="utf-8-sig")

    decision["outputs"] = {
        "curves": str(PROFIT_LOCK_CURVES_PATH),
        "summary": str(SUMMARY_PATH),
        "aggregate": str(AGGREGATE_PATH),
        "to_final": str(TO_FINAL_PATH),
        "fixed_horizon": str(FIXED_HORIZON_PATH),
        "worst_windows": str(WORST_WINDOWS_PATH),
        "retention": str(RETENTION_PATH),
        "goal_table": str(GOAL_TABLE_PATH),
        "transfer_events": str(TRANSFER_EVENTS_PATH),
        "summary_chart": str(SUMMARY_CHART_PATH),
        "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
