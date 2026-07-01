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

import stage006_current_quality_feature_binder as s006


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage009"
MODEL_TAG = "stage009_dense_start_goal_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage009_dense_start_goal_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_dense_start_goal_audit"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE008_OUTPUT_DIR = LINE_DIR / "outputs" / "stage008_high_quality_add_risk_proxy"

BASE_CURVES_PATH = (
    STAGE006_OUTPUT_DIR
    / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv"
)
PROXY_CURVES_PATH = (
    STAGE008_OUTPUT_DIR
    / "rebuilt_c9_stage008_high_quality_add_risk_proxy_curves_stage008_high_quality_add_risk_proxy_v1.csv"
)
STAGE008_SUMMARY_PATH = (
    STAGE008_OUTPUT_DIR
    / "rebuilt_c9_stage008_high_quality_add_risk_proxy_summary_stage008_high_quality_add_risk_proxy_v1.csv"
)

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
FIXED_HORIZON_DAYS = (366, 540, 730, 1095)
WORST_PER_START = 3
WORST_OUTPUT_ROWS = 1000

AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_to_final_windows_{MODEL_TAG}.csv"
FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixed_horizon_windows_{MODEL_TAG}.csv"
WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_cycle_retention_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _load_variant_curves() -> pd.DataFrame:
    base = pd.read_csv(BASE_CURVES_PATH, encoding="utf-8-sig")
    proxy = pd.read_csv(PROXY_CURVES_PATH, encoding="utf-8-sig")
    base = base[["requested_start_month", "date", "account_equity"]].copy()
    base.rename(columns={"account_equity": "equity"}, inplace=True)
    base["variant"] = "base_stage006"
    proxy = proxy[["requested_start_month", "date", "proxy_account_equity"]].copy()
    proxy.rename(columns={"proxy_account_equity": "equity"}, inplace=True)
    proxy["variant"] = "proxy_stage008"
    curves = pd.concat([base, proxy], ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    return curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])


def _ret_pct(start_equity: float, end_equity: float) -> float:
    return float((end_equity / start_equity - 1.0) * 100.0) if start_equity else np.nan


def _audit_group(variant: str, source_start: str, group: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = data["date"].to_numpy(dtype="datetime64[ns]")
    equity = data["equity"].to_numpy(dtype=float)
    objective_mask = (data["date"] >= OBJECTIVE_START_MIN) & (data["date"] <= OBJECTIVE_START_MAX)
    start_indices = np.flatnonzero(objective_mask.to_numpy())

    aggregate_rows: list[dict[str, Any]] = []
    to_final_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []

    all_count = 0
    all_negative = 0
    all_min = np.inf
    all_sum = 0.0
    all_positive = 0
    final_count = 0
    final_negative = 0
    final_min = np.inf
    final_sum = 0.0

    for idx in start_indices:
        start_date = pd.Timestamp(dates[idx])
        start_equity = float(equity[idx])
        min_end_date = start_date + pd.Timedelta(days=MIN_PERIOD_CALENDAR_DAYS)
        min_end_idx = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_idx >= len(dates):
            continue
        end_indices = np.arange(min_end_idx, len(dates), dtype=int)
        returns = (equity[end_indices] / start_equity - 1.0) * 100.0
        valid = np.isfinite(returns)
        returns = returns[valid]
        valid_end_indices = end_indices[valid]
        if len(returns) == 0:
            continue
        all_count += int(len(returns))
        neg = returns < 0.0
        all_negative += int(neg.sum())
        all_positive += int((returns > 0.0).sum())
        all_sum += float(returns.sum())
        all_min = min(all_min, float(returns.min()))

        k = min(WORST_PER_START, len(returns))
        candidate_indices = np.argpartition(returns, k - 1)[:k]
        for local_pos in candidate_indices:
            ret = float(returns[local_pos])
            if ret >= 0.0:
                continue
            end_idx = int(valid_end_indices[local_pos])
            worst_rows.append(
                {
                    "variant": variant,
                    "source_start_month": source_start,
                    "window_type": "all_gt_1y",
                    "start_date": start_date.date().isoformat(),
                    "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                    "period_calendar_days": int((pd.Timestamp(dates[end_idx]) - start_date).days),
                    "period_trading_days": int(end_idx - idx + 1),
                    "return_pct": ret,
                    "start_equity": start_equity,
                    "end_equity": float(equity[end_idx]),
                }
            )

        final_ret = _ret_pct(start_equity, float(equity[-1]))
        final_count += 1
        final_negative += int(final_ret < 0.0)
        final_sum += final_ret
        final_min = min(final_min, final_ret)
        to_final_rows.append(
            {
                "variant": variant,
                "source_start_month": source_start,
                "start_date": start_date.date().isoformat(),
                "end_date": pd.Timestamp(dates[-1]).date().isoformat(),
                "period_calendar_days": int((pd.Timestamp(dates[-1]) - start_date).days),
                "period_trading_days": int(len(dates) - idx),
                "return_pct": final_ret,
                "positive_return": int(final_ret > 0.0),
            }
        )

        for horizon in FIXED_HORIZON_DAYS:
            target_date = start_date + pd.Timedelta(days=horizon)
            end_idx = int(np.searchsorted(dates, np.datetime64(target_date), side="left"))
            if end_idx >= len(dates):
                continue
            ret = _ret_pct(start_equity, float(equity[end_idx]))
            fixed_rows.append(
                {
                    "variant": variant,
                    "source_start_month": source_start,
                    "horizon_days": horizon,
                    "start_date": start_date.date().isoformat(),
                    "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                    "actual_calendar_days": int((pd.Timestamp(dates[end_idx]) - start_date).days),
                    "period_trading_days": int(end_idx - idx + 1),
                    "return_pct": ret,
                    "positive_return": int(ret > 0.0),
                }
            )

    aggregate_rows.append(
        {
            "variant": variant,
            "source_start_month": source_start,
            "audit_scope": "all_trading_end_dates_gt_1y",
            "objective_start_min": OBJECTIVE_START_MIN.date().isoformat(),
            "objective_start_max": OBJECTIVE_START_MAX.date().isoformat(),
            "window_count": all_count,
            "positive_count": all_positive,
            "negative_count": all_negative,
            "negative_rate_pct": float(all_negative / all_count * 100.0) if all_count else np.nan,
            "min_return_pct": float(all_min) if np.isfinite(all_min) else np.nan,
            "mean_return_pct": float(all_sum / all_count) if all_count else np.nan,
            "is_independent_daily_cold_start": 0,
        }
    )
    aggregate_rows.append(
        {
            "variant": variant,
            "source_start_month": source_start,
            "audit_scope": "start_to_2026_06_30_only",
            "objective_start_min": OBJECTIVE_START_MIN.date().isoformat(),
            "objective_start_max": OBJECTIVE_START_MAX.date().isoformat(),
            "window_count": final_count,
            "positive_count": int(final_count - final_negative),
            "negative_count": final_negative,
            "negative_rate_pct": float(final_negative / final_count * 100.0) if final_count else np.nan,
            "min_return_pct": float(final_min) if np.isfinite(final_min) else np.nan,
            "mean_return_pct": float(final_sum / final_count) if final_count else np.nan,
            "is_independent_daily_cold_start": 0,
        }
    )
    return aggregate_rows, to_final_rows, fixed_rows, worst_rows


def _run_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    aggregate_rows: list[dict[str, Any]] = []
    to_final_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []
    for (variant, source_start), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        agg, final, fixed, worst = _audit_group(str(variant), str(source_start), group)
        aggregate_rows.extend(agg)
        to_final_rows.extend(final)
        fixed_rows.extend(fixed)
        worst_rows.extend(worst)

    aggregate = pd.DataFrame(aggregate_rows)
    to_final = pd.DataFrame(to_final_rows)
    fixed = pd.DataFrame(fixed_rows)
    worst = pd.DataFrame(worst_rows)
    if not worst.empty:
        worst = worst.sort_values("return_pct").head(WORST_OUTPUT_ROWS).reset_index(drop=True)
    return aggregate, to_final, fixed, worst


def _retention_summary() -> pd.DataFrame:
    summary = pd.read_csv(STAGE008_SUMMARY_PATH, encoding="utf-8-sig")
    rows = []
    for _, row in summary.iterrows():
        base = float(row["total_return_pct_base"])
        proxy = float(row["total_return_pct_proxy"])
        rows.append(
            {
                "requested_start_month": row["requested_start_month"],
                "base_total_return_pct": base,
                "proxy_total_return_pct": proxy,
                "proxy_vs_base_return_ratio": float(proxy / base) if base else np.nan,
                "passes_80pct_retention": int(proxy >= base * 0.8),
            }
        )
    return pd.DataFrame(rows)


def _plot(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    ax = axes[0, 0]
    scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    scope["label"] = scope["variant"] + "\n" + scope["source_start_month"]
    x = np.arange(len(scope))
    ax.bar(x, scope["negative_rate_pct"], color=np.where(scope["variant"].eq("proxy_stage008"), "#2563eb", "#f97316"))
    ax.set_xticks(x[::2])
    ax.set_xticklabels(scope["label"].iloc[::2], rotation=55, ha="right", fontsize=7)
    ax.set_title("Negative Rate: All Trading End Dates > 1Y")
    ax.set_ylabel("negative rate %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    final = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")].copy()
    final["label"] = final["variant"] + "\n" + final["source_start_month"]
    x = np.arange(len(final))
    ax.bar(x, final["negative_rate_pct"], color=np.where(final["variant"].eq("proxy_stage008"), "#2563eb", "#f97316"))
    ax.set_xticks(x[::2])
    ax.set_xticklabels(final["label"].iloc[::2], rotation=55, ha="right", fontsize=7)
    ax.set_title("Negative Rate: Start To 2026-06-30")
    ax.set_ylabel("negative rate %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not worst.empty:
        plot = worst.head(80).copy()
        ax.scatter(np.arange(len(plot)), plot["return_pct"], s=12, c=np.where(plot["variant"].eq("proxy_stage008"), "#2563eb", "#f97316"))
    ax.axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    ax.set_title("Worst Negative Windows")
    ax.set_ylabel("return %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    if not fixed.empty:
        fixed_summary = (
            fixed.groupby(["variant", "horizon_days"], as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values(["horizon_days", "variant"])
        )
        for variant, group in fixed_summary.groupby("variant"):
            ax.plot(group["horizon_days"], group["negative_rate_pct"], marker="o", label=variant)
    ax.set_title("Fixed Horizon Negative Rate")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("negative rate %")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], aggregate: pd.DataFrame, to_final: pd.DataFrame, fixed: pd.DataFrame, worst: pd.DataFrame, retention: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} 新目标任意日起点密集审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 目标起点范围：`{OBJECTIVE_START_MIN.date()}` 到 `{OBJECTIVE_START_MAX.date()}`",
        f"- 最短周期：`>{MIN_PERIOD_CALENDAR_DAYS - 1}` 个自然日",
        "- 阶段性质：只读运行曲线子周期审计；不是任意日独立冷启动回测，不改策略、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- PBO/CSCV 与 walk-forward 资料提示：密集滚动窗口能暴露少数半年起点看不出来的过拟合和左尾。",
        "- 本阶段不把现有运行曲线子周期审计冒充独立冷启动；若这里仍有负收益窗口，真实每日冷启动更不能直接假定达标。",
        "",
        "## 聚合结果",
        "",
        _md_table(aggregate, max_rows=40),
        "",
        "## To Final 窗口样例",
        "",
        _md_table(to_final.sort_values("return_pct").head(40), max_rows=40),
        "",
        "## 固定周期窗口样例",
        "",
        _md_table(fixed.sort_values("return_pct").head(40), max_rows=40),
        "",
        "## 最差窗口",
        "",
        _md_table(worst, max_rows=40),
        "",
        "## 全周期收益保留",
        "",
        _md_table(retention, max_rows=30),
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
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _load_variant_curves()
    aggregate, to_final, fixed, worst = _run_audit(curves)
    retention = _retention_summary()
    _plot(aggregate, worst, fixed)

    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    proxy_all = aggregate[
        aggregate["variant"].eq("proxy_stage008") & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    proxy_final = aggregate[
        aggregate["variant"].eq("proxy_stage008") & aggregate["audit_scope"].eq("start_to_2026_06_30_only")
    ]
    base_all = aggregate[
        aggregate["variant"].eq("base_stage006") & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "objective_start_min": OBJECTIVE_START_MIN.date().isoformat(),
        "objective_start_max": OBJECTIVE_START_MAX.date().isoformat(),
        "min_period_calendar_days": MIN_PERIOD_CALENDAR_DAYS,
        "is_independent_daily_cold_start": False,
        "source_curve_count": int(curves[["variant", "requested_start_month"]].drop_duplicates().shape[0]),
        "base_all_gt1y_window_count": int(base_all["window_count"].sum()) if not base_all.empty else 0,
        "base_all_gt1y_negative_count": int(base_all["negative_count"].sum()) if not base_all.empty else 0,
        "proxy_all_gt1y_window_count": int(proxy_all["window_count"].sum()) if not proxy_all.empty else 0,
        "proxy_all_gt1y_negative_count": int(proxy_all["negative_count"].sum()) if not proxy_all.empty else 0,
        "proxy_all_gt1y_min_return_pct": float(proxy_all["min_return_pct"].min()) if not proxy_all.empty else np.nan,
        "proxy_to_final_window_count": int(proxy_final["window_count"].sum()) if not proxy_final.empty else 0,
        "proxy_to_final_negative_count": int(proxy_final["negative_count"].sum()) if not proxy_final.empty else 0,
        "proxy_to_final_min_return_pct": float(proxy_final["min_return_pct"].min()) if not proxy_final.empty else np.nan,
        "retention_80pct_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "decision": "stage009_goal_not_met_dense_running_window_has_negative_gt1y_periods",
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Walk-forward/PBO references support dense start-date stress before promotion. "
            "This is a running-curve subperiod audit, not independent daily cold-start proof."
        ),
        "overfit_reflection_before": (
            "否。目标变更后先补审计口径，不改策略、不调参数，只测所有现有曲线子周期。"
        ),
        "continue_value_before": (
            "是。新目标要求任意日起点，半年起点结果不够，必须先定位密集区间缺口。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只读审计，发现负窗口后不反向调标签或比例。"
        ),
        "continue_value_after": (
            "有。Stage008 仍保留收益优势，但密集 >1 年子周期还有负收益，下一步要针对左尾目标重构真实引擎或账户层保护。"
        ),
        "outputs": {
            "aggregate": str(AGGREGATE_PATH),
            "to_final_windows": str(TO_FINAL_PATH),
            "fixed_horizon_windows": str(FIXED_HORIZON_PATH),
            "worst_windows": str(WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, aggregate, to_final, fixed, worst, retention)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    if not worst.empty:
        print("worst")
        print(worst.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
