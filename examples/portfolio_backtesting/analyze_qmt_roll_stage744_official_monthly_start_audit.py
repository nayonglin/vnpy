from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage744_official_monthly_start_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage744_official_monthly_start_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ANALYSIS_END = pd.Timestamp("2026-04-30")
MONTH_STARTS = tuple(pd.date_range("2020-01-01", ANALYSIS_END.normalize(), freq="MS"))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
MATURITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_maturity_summary_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} 独立启动至 {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _add_month_fields(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_month"] = pd.to_datetime(frame["analysis_start"], errors="coerce").dt.to_period("M").astype(str)
    frame["start_year"] = pd.to_datetime(frame["analysis_start"], errors="coerce").dt.year
    frame["start_month_num"] = pd.to_datetime(frame["analysis_start"], errors="coerce").dt.month
    frame["positive_return"] = (pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce") > 0.0).astype(int)
    frame["short_sample_lt63"] = (pd.to_numeric(frame["trading_days"], errors="coerce") < 63).astype(int)
    frame["mature_63d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 63).astype(int)
    frame["mature_126d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 126).astype(int)
    frame["mature_252d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 252).astype(int)
    return frame


def _aggregate(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "bucket": label,
            "start_count": 0,
            "positive_count": 0,
            "positive_rate_pct": 0.0,
            "dd30_fail_count": 0,
            "dd40_fail_count": 0,
            "deployable_fail_count": 0,
            "median_return_pct": 0.0,
            "p10_return_pct": 0.0,
            "min_return_pct": 0.0,
            "median_dd_pct": 0.0,
            "worst_dd_pct": 0.0,
            "median_sharpe": 0.0,
            "worst_start_month_by_return": "",
            "worst_start_month_by_dd": "",
        }
    returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce").fillna(0.0)
    dd = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce").fillna(0.0)
    sharpe = pd.to_numeric(frame["rebased_sharpe"], errors="coerce").fillna(0.0)
    worst_return_idx = returns.idxmin()
    worst_dd_idx = dd.idxmin()
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "positive_count": int((returns > 0.0).sum()),
        "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
        "dd30_fail_count": int((dd < -30.0).sum()),
        "dd40_fail_count": int((dd < -40.0).sum()),
        "deployable_fail_count": int((pd.to_numeric(frame["deployable_pass"], errors="coerce").fillna(0) < 1).sum()),
        "median_return_pct": float(returns.median()),
        "p10_return_pct": float(returns.quantile(0.10)),
        "min_return_pct": float(returns.min()),
        "median_dd_pct": float(dd.median()),
        "worst_dd_pct": float(dd.min()),
        "median_sharpe": float(sharpe.median()),
        "worst_start_month_by_return": str(frame.loc[worst_return_idx, "start_month"]),
        "worst_start_month_by_dd": str(frame.loc[worst_dd_idx, "start_month"]),
    }


def _year_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in summary.groupby("start_year", sort=True):
        row = _aggregate(str(int(year)), group)
        row["start_year"] = int(year)
        rows.append(row)
    return pd.DataFrame(rows)


def _maturity_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _aggregate("all_monthly_starts", summary),
        _aggregate("mature_ge63_trading_days", summary[summary["mature_63d"].eq(1)]),
        _aggregate("mature_ge126_trading_days", summary[summary["mature_126d"].eq(1)]),
        _aggregate("mature_ge252_trading_days", summary[summary["mature_252d"].eq(1)]),
    ]
    return pd.DataFrame(rows)


def _checks(summary: pd.DataFrame, cost: pd.DataFrame, maturity: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    matured = summary[summary["mature_252d"].eq(1)].copy()
    mature126 = summary[summary["mature_126d"].eq(1)].copy()
    mature63 = summary[summary["mature_63d"].eq(1)].copy()
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].copy()
    cost2_mature252 = cost2[cost2["window_name"].isin(matured["window_name"].astype(str))].copy()

    add("monthly_start_count", "pass", float(len(summary)), ">= 70", "2020-01 至 2026-04 每月独立启动。")
    add(
        "mature252_start_count",
        "pass" if len(matured) >= 50 else "watch",
        float(len(matured)),
        ">= 50",
        "至少一年样本的月度起点数量。",
    )
    positive_252 = float(matured["positive_return"].mean() * 100.0) if not matured.empty else 0.0
    add(
        "mature252_positive_rate_ge80",
        "pass" if positive_252 >= 80.0 else "watch",
        positive_252,
        ">= 80%",
        "一年以上持有窗口最好大部分为正。",
    )
    dd40_fail_252 = float((pd.to_numeric(matured["rebased_max_dd_pct"], errors="coerce") < -40.0).sum())
    add(
        "mature252_dd40_fail_eq0",
        "pass" if dd40_fail_252 == 0.0 else "fail",
        dd40_fail_252,
        "= 0",
        "成熟样本不能打穿正式生存线。",
    )
    dd30_fail_252 = float((pd.to_numeric(matured["rebased_max_dd_pct"], errors="coerce") < -30.0).sum())
    add(
        "mature252_dd30_fail_watch",
        "pass" if dd30_fail_252 == 0.0 else "watch",
        dd30_fail_252,
        "= 0 preferred",
        "DD30 是本线目标，但正式版原本并未保证 DD30。",
    )
    min_return_252 = float(pd.to_numeric(matured["rebased_total_return_pct"], errors="coerce").min()) if not matured.empty else 0.0
    add(
        "mature252_min_return_positive",
        "pass" if min_return_252 > 0.0 else "fail",
        min_return_252,
        "> 0",
        "一年以上冷启动不应亏损。",
    )
    positive_126 = float(mature126["positive_return"].mean() * 100.0) if not mature126.empty else 0.0
    add(
        "mature126_positive_rate_ge70",
        "pass" if positive_126 >= 70.0 else "watch",
        positive_126,
        ">= 70%",
        "半年以上起点的可接受性。",
    )
    min_return_63 = float(pd.to_numeric(mature63["rebased_total_return_pct"], errors="coerce").min()) if not mature63.empty else 0.0
    add(
        "mature63_min_return_positive_watch",
        "pass" if min_return_63 > 0.0 else "watch",
        min_return_63,
        "> 0 preferred",
        "三个月以上短启动样本左尾，更多用于体验风险。",
    )
    if not cost2_mature252.empty:
        cost2_dd40_fail = float((pd.to_numeric(cost2_mature252["max_dd_pct"], errors="coerce") < -40.0).sum())
        add(
            "mature252_cost2_dd40_fail_eq0",
            "pass" if cost2_dd40_fail == 0.0 else "fail",
            cost2_dd40_fail,
            "= 0",
            "2x 成本成熟样本不能打穿 DD40。",
        )

    if not maturity.empty:
        all_row = maturity[maturity["bucket"].eq("all_monthly_starts")]
        if not all_row.empty:
            add(
                "all_monthly_worst_dd40_pass",
                "pass" if float(all_row["worst_dd_pct"].iloc[0]) >= -40.0 else "fail",
                float(all_row["worst_dd_pct"].iloc[0]),
                ">= -40%",
                "所有月起点最差回撤。",
            )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, year_summary: pd.DataFrame, maturity: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "official_monthly_start_audit_pass_with_watch" if not hard_fail else "official_monthly_start_audit_has_hard_fail"
    return {
        "stage": "Stage432",
        "script_stage": "Stage744",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "analysis_start_first": MONTH_STARTS[0].strftime("%Y-%m-%d"),
        "analysis_start_last": MONTH_STARTS[-1].strftime("%Y-%m-%d"),
        "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        "decision": label,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "monthly_independent_start_count": len(MONTH_STARTS),
            "note": "Each month is independently started with 200k capital and the current official Stage372 profile.",
        },
        "checks": checks.to_dict("records"),
        "maturity_summary": maturity.to_dict("records"),
        "year_summary": year_summary.to_dict("records"),
        "worst_by_return": summary.sort_values("rebased_total_return_pct").head(10).to_dict("records"),
        "worst_by_drawdown": summary.sort_values("rebased_max_dd_pct").head(10).to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "maturity_summary": str(MATURITY_SUMMARY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(summary: pd.DataFrame) -> None:
    data = summary.sort_values("analysis_start").copy()
    data["start_ts"] = pd.to_datetime(data["analysis_start"], errors="coerce")
    data["month_num"] = data["start_ts"].dt.month
    data["year"] = data["start_ts"].dt.year

    heat = data.pivot_table(
        index="year",
        columns="month_num",
        values="rebased_total_return_pct",
        aggfunc="first",
    ).reindex(columns=list(range(1, 13)))

    fig = plt.figure(figsize=(17, 12))
    grid = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.1])
    ax_ret = fig.add_subplot(grid[0, :])
    ax_dd = fig.add_subplot(grid[1, 0])
    ax_sharpe = fig.add_subplot(grid[1, 1])
    ax_heat = fig.add_subplot(grid[2, :])

    colors = np.where(data["rebased_total_return_pct"].astype(float) >= 0.0, "#2563eb", "#dc2626")
    ax_ret.bar(data["start_ts"], data["rebased_total_return_pct"], width=22, color=colors, alpha=0.85)
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_title("Official Stage372 monthly independent starts: total return to 2026-04-30")
    ax_ret.set_ylabel("Return %")
    ax_ret.grid(axis="y", alpha=0.25)

    ax_dd.plot(data["start_ts"], data["rebased_max_dd_pct"], color="#ea580c", linewidth=1.4)
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_title("Max drawdown by start month")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.grid(alpha=0.25)
    ax_dd.legend(loc="lower left")

    ax_sharpe.plot(data["start_ts"], data["rebased_sharpe"], color="#0f766e", linewidth=1.4)
    ax_sharpe.axhline(0.0, color="#111827", linewidth=0.8)
    ax_sharpe.set_title("Sharpe by start month")
    ax_sharpe.set_ylabel("Sharpe")
    ax_sharpe.grid(alpha=0.25)

    masked = np.ma.masked_invalid(heat.to_numpy(dtype=float))
    image = ax_heat.imshow(masked, aspect="auto", cmap="RdYlGn", vmin=-100, vmax=400)
    ax_heat.set_title("Return heatmap by start year/month")
    ax_heat.set_yticks(np.arange(len(heat.index)))
    ax_heat.set_yticklabels([str(int(item)) for item in heat.index])
    ax_heat.set_xticks(np.arange(12))
    ax_heat.set_xticklabels([str(i) for i in range(1, 13)])
    ax_heat.set_xlabel("Start month")
    ax_heat.set_ylabel("Start year")
    for y in range(masked.shape[0]):
        for x in range(masked.shape[1]):
            if masked.mask is not np.ma.nomask and masked.mask[y, x]:
                continue
            value = float(masked[y, x])
            text_color = "white" if value < -50 or value > 300 else "#111827"
            ax_heat.text(x, y, f"{value:.0f}", ha="center", va="center", fontsize=8, color=text_color)
    fig.colorbar(image, ax=ax_heat, fraction=0.018, pad=0.01, label="Return %")

    fig.suptitle(f"Stage432 / Script744 {OFFICIAL_LIVE_VERSION} monthly-start audit", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, year_summary: pd.DataFrame, maturity: pd.DataFrame, checks: pd.DataFrame, decision: dict[str, Any]) -> None:
    key_cols = [
        "start_month",
        "trading_days",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_cagr_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "days_over_100pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "deployable_pass",
        "short_sample_lt63",
    ]
    worst_return = summary.sort_values("rebased_total_return_pct").head(15)
    worst_dd = summary.sort_values("rebased_max_dd_pct").head(15)
    cost2_worst = cost[cost["cost_multiplier"].eq(2.0)].sort_values("max_dd_pct").head(15)
    lines = [
        "# Stage432 / Script744 当前正式版月度冷启动审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 官方实盘版本：`{OFFICIAL_LIVE_VERSION}`",
        f"- 策略体：`{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 账户口径：`{OFFICIAL_LIVE_CAPITAL:,.0f}`",
        f"- 起点范围：`2020-01` 至 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(MONTH_STARTS)}` 个逐月独立启动。",
        f"- 统一终点：`{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        "- 性质：只读鲁棒性审计；不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Walk-forward / rolling-window 资料和 GitHub 示例都强调：不能只看单条全周期曲线，需要从多个滚动起点观察参数和路径稳定性。",
        "- 本阶段不优化参数，不重新训练 AI，只把当前正式版从每个月独立启动，因此它是路径依赖审计，不是新策略优化。",
        "",
        "## 检查结论",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 成熟度聚合",
        "",
        _md_table(maturity, max_rows=20),
        "",
        "## 起始年份聚合",
        "",
        _md_table(year_summary, max_rows=20),
        "",
        "## 最差收益起点",
        "",
        _md_table(worst_return[key_cols], max_rows=15),
        "",
        "## 最差回撤起点",
        "",
        _md_table(worst_dd[key_cols], max_rows=15),
        "",
        "## 2x成本最差回撤起点",
        "",
        _md_table(cost2_worst, max_rows=15),
        "",
        "## 全部月起点明细",
        "",
        _md_table(summary[key_cols], max_rows=90),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    spec = s660._official_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for start in MONTH_STARTS:
        name = _window_name(start)
        print(f"[stage744] running {name} {OFFICIAL_LIVE_PROFILE_NAME}", flush=True)
        frame, forced_events = s660._run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=start,
            analysis_end=ANALYSIS_END,
        )
        summary, curve, costs = s660._window_metrics(
            frame,
            window_name=name,
            window_label=_window_label(start),
            group="monthly_start",
            source_name="official_monthly_independent_start",
            caveat="fresh independent monthly start; fixed official Stage372 profile; no parameter changes",
            forced_events=forced_events,
        )
        summary["requested_start_month"] = start.strftime("%Y-%m")
        summary_rows.append(summary)
        curve["requested_start_month"] = start.strftime("%Y-%m")
        curve_frames.append(curve)
        for row in costs:
            row["requested_start_month"] = start.strftime("%Y-%m")
            cost_rows.append(row)

    summary = _add_month_fields(pd.DataFrame(summary_rows))
    cost = pd.DataFrame(cost_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    year_summary = _year_summary(summary)
    maturity = _maturity_summary(summary)
    checks = _checks(summary, cost, maturity)
    decision = _decision(summary, cost, year_summary, maturity, checks)

    _plot(summary)
    _write_report(summary, cost, year_summary, maturity, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    maturity.to_csv(MATURITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
