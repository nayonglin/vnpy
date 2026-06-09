from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage661_stage653_min_one_throttle_multiperiod as s661
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage663_stage372_30w_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage663_stage372_30w_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CAPITAL_30W = 300_000.0
VARIANT_30W = "stage526_300k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().fillna(CAPITAL_30W)
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").ffill().pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _cagr_pct(equity: pd.Series, dates: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    days = max((pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days, 1)
    return float((end / start) ** (365.25 / days) - 1.0) * 100.0


def _spec_30w(metadata: dict[str, Any]) -> s653.ForcedVariant:
    spec = s660._official_spec(metadata)
    capital = replace(
        spec.capital,
        variant=VARIANT_30W,
        label="30w Stage372 recovery sleeve",
        account_capital=CAPITAL_30W,
        c3_capital=CAPITAL_30W,
        note=(
            "Stage374 research: Stage372 official logic with 300k starting capital. "
            "No alpha/entry/AI/threshold changes."
        ),
    )
    return replace(spec, capital=capital, profile="forced_margin_95_to_80_recovery_sleeve_30w")


def _run_window(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return s660._run_independent_window(
        spec=spec,
        metadata=metadata,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
    )


def _run_latest_ytd(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime("2026-06-04", "%Y-%m-%d"),
        s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    forced_events = forced_events.copy()
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile
    return combined, forced_events


def _window_metrics(
    frame: pd.DataFrame,
    *,
    window_name: str,
    window_label: str,
    group: str,
    source_name: str,
    caveat: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    if frame.empty:
        raise ValueError(f"empty window frame: {window_name}")

    ordered = frame.sort_values("date").reset_index(drop=True)
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    net_pnl = ordered["net_pnl"].astype(float)
    equity = ordered["account_equity"].astype(float)
    dates = ordered["date"]
    dd = _drawdown_pct(equity)
    margin = ordered["broker10_total_margin_exact"].astype(float) / equity.replace(0.0, np.nan) * 100.0
    margin = margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]

    start_date = pd.Timestamp(dates.iloc[0]).date().isoformat()
    end_date = pd.Timestamp(dates.iloc[-1]).date().isoformat()
    event_count = 0
    event_volume = 0.0
    if not forced_events.empty:
        events = forced_events.copy()
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
        events = events[
            events["variant"].astype(str).eq(VARIANT_30W)
            & events["date"].ge(pd.Timestamp(start_date))
            & events["date"].le(pd.Timestamp(end_date))
        ]
        event_count = int(len(events))
        event_volume = float(pd.to_numeric(events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    summary = {
        "variant": VARIANT_30W,
        "window_name": window_name,
        "window_label": window_label,
        "window_group": group,
        "source_name": source_name,
        "analysis_start": start_date,
        "analysis_end": end_date,
        "trading_days": int(len(ordered)),
        "start_equity_path": float(equity.iloc[0]),
        "end_equity_path": float(equity.iloc[-1]),
        "path_return_pct": float((equity.iloc[-1] / CAPITAL_30W - 1.0) * 100.0),
        "rebased_end_equity": float(equity.iloc[-1]),
        "rebased_total_return_pct": float((equity.iloc[-1] / CAPITAL_30W - 1.0) * 100.0),
        "rebased_cagr_pct": _cagr_pct(equity, dates),
        "rebased_max_dd_pct": float(dd.min()),
        "rebased_sharpe": _sharpe(equity),
        "rebased_min_equity": float(equity.min()),
        "max_broker10_margin_to_rebased_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_rebased_equity_pct": float(margin.quantile(0.95)),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
        "broker10_90_watch_pass": int(margin.max() < 90.0),
        "account_survival_pass": int(equity.min() > 0.0),
        "deployable_pass": int(float(dd.min()) >= -40.0 and margin.max() <= 100.0 + 1e-9 and equity.min() > 0.0),
        "caveat": caveat,
    }

    curve = pd.DataFrame(
        {
            "date": dates,
            "variant": VARIANT_30W,
            "window_name": window_name,
            "window_label": window_label,
            "window_group": group,
            "source_name": source_name,
            "rebased_equity": equity,
            "rebased_nav": equity / CAPITAL_30W,
            "drawdown_pct": dd,
            "broker10_margin_to_rebased_equity_pct": margin,
            "net_pnl": net_pnl,
            "trade_count": ordered["trade_count"].astype(float),
            "total_slippage": ordered["total_slippage"].astype(float),
        }
    )

    cost_rows: list[dict[str, Any]] = []
    cumulative_slippage = ordered["total_slippage"].astype(float).cumsum()
    for multiplier in (1.0, 2.0, 3.0):
        stressed = equity - cumulative_slippage * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = ordered["broker10_total_margin_exact"].astype(float) / stressed.replace(0.0, np.nan) * 100.0
        stressed_margin = stressed_margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cost_rows.append(
            {
                "variant": VARIANT_30W,
                "window_name": window_name,
                "window_label": window_label,
                "cost_multiplier": multiplier,
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / CAPITAL_30W - 1.0) * 100.0),
                "max_dd_pct": float(stressed_dd.min()),
                "sharpe": _sharpe(stressed),
                "max_broker10_margin_to_equity_pct": float(stressed_margin.max()),
                "days_over_100pct": int(stressed_margin.gt(100.0 + 1e-9).sum()),
                "account_survival_pass": int(stressed.min() > 0.0),
                "deployable_pass": int(
                    stressed_dd.min() >= -40.0
                    and stressed_margin.max() <= 100.0 + 1e-9
                    and stressed.min() > 0.0
                ),
            }
        )
    return summary, curve, cost_rows


def _period_metrics(group: pd.DataFrame, *, name: str, label: str, period_group: str, source_name: str) -> dict[str, Any]:
    ordered = group.sort_values("date").reset_index(drop=True)
    dates = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    net_pnl = ordered["net_pnl"].astype(float)
    end_equity = ordered["account_equity"].astype(float)
    start_equity = float(end_equity.iloc[0] - net_pnl.iloc[0])
    path = pd.Series([start_equity] + end_equity.tolist())
    dd = _drawdown_pct(path)
    margin = ordered["broker10_total_margin_exact"].astype(float) / end_equity.replace(0.0, np.nan) * 100.0
    margin = margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]
    return {
        "window_name": name,
        "window_label": label,
        "window_group": period_group,
        "source_name": source_name,
        "analysis_start": pd.Timestamp(dates.iloc[0]).date().isoformat(),
        "analysis_end": pd.Timestamp(dates.iloc[-1]).date().isoformat(),
        "trading_days": int(len(ordered)),
        "period_start_equity": start_equity,
        "period_end_equity": float(end_equity.iloc[-1]),
        "period_pnl": float(net_pnl.sum()),
        "period_pnl_on_30w_pct": float(net_pnl.sum() / CAPITAL_30W * 100.0),
        "period_return_pct": float((end_equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
        "period_max_dd_pct": float(dd.min()),
        "period_sharpe": _sharpe(path),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
    }


def _annual_monthly(frame: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("date").copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    ordered["year"] = ordered["date"].dt.year.astype(str)
    ordered["month"] = ordered["date"].dt.to_period("M").astype(str)
    annual = [
        _period_metrics(group, name=f"year_{year}", label=f"{year}年度", period_group="calendar_year", source_name=source_name)
        for year, group in ordered.groupby("year", sort=True)
    ]
    monthly = [
        _period_metrics(group, name=f"month_{month}", label=f"{month}月度", period_group="calendar_month", source_name=source_name)
        for month, group in ordered.groupby("month", sort=True)
    ]
    return pd.DataFrame(annual), pd.DataFrame(monthly)


def _check_rows(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full = summary[summary["window_name"].eq("full_2020_20260430")]
    if not full.empty:
        row = full.iloc[0]
        rows.extend(
            [
                {
                    "check_name": "full_dd40",
                    "status": "pass" if float(row["rebased_max_dd_pct"]) >= -40.0 else "fail",
                    "value": float(row["rebased_max_dd_pct"]),
                    "threshold": ">= -40",
                    "comment": "30万全周期正常成本最大回撤。",
                },
                {
                    "check_name": "full_margin100",
                    "status": "pass" if int(row["days_over_100pct"]) == 0 else "fail",
                    "value": int(row["days_over_100pct"]),
                    "threshold": "0 days",
                    "comment": "30万全周期 broker10 保证金不穿100%。",
                },
            ]
        )
    cost2 = cost[(cost["window_name"].eq("full_2020_20260430")) & (cost["cost_multiplier"].eq(2.0))]
    if not cost2.empty:
        row = cost2.iloc[0]
        rows.append(
            {
                "check_name": "full_2x_cost_dd40",
                "status": "pass" if float(row["max_dd_pct"]) >= -40.0 else "fail",
                "value": float(row["max_dd_pct"]),
                "threshold": ">= -40",
                "comment": "30万全周期2x成本压力最大回撤。",
            }
        )
    if not rolling.empty:
        focus = rolling[rolling["holding_days"].isin([63, 126, 252])].copy()
        if not focus.empty:
            rows.append(
                {
                    "check_name": "rolling_p05_return_min",
                    "status": "watch" if float(focus["p05_return_pct"].min()) < 0.0 else "pass",
                    "value": float(focus["p05_return_pct"].min()),
                    "threshold": ">= 0 preferred",
                    "comment": "30万短周期左尾。",
                }
            )
    return pd.DataFrame(rows)


def _plot_report(summary: pd.DataFrame, curves: pd.DataFrame, annual: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_equity, ax_multi, ax_annual, ax_margin = axes.flatten()

    full_curve = curves[curves["window_name"].eq("full_2020_20260430")].sort_values("date")
    ax_equity.plot(pd.to_datetime(full_curve["date"]), full_curve["rebased_nav"], color="#2563eb", linewidth=1.2)
    ax_equity_2 = ax_equity.twinx()
    ax_equity_2.plot(pd.to_datetime(full_curve["date"]), full_curve["drawdown_pct"], color="#dc2626", linewidth=0.9)
    ax_equity_2.axhline(-40.0, color="#111827", linestyle="--", linewidth=0.8)
    ax_equity.set_title("Stage372 30w full-period NAV and drawdown")
    ax_equity.grid(alpha=0.25)

    for name in ["since_2021", "since_2022", "since_2023", "since_2024", "since_2025", "ytd_2026_latest_ai"]:
        frame = curves[curves["window_name"].eq(name)].sort_values("date")
        if frame.empty:
            continue
        ax_multi.plot(np.arange(len(frame)), frame["rebased_nav"], linewidth=1.0, label=str(frame["window_label"].iloc[0]))
    ax_multi.set_title("Start-window rebased NAV curves")
    ax_multi.grid(alpha=0.25)
    ax_multi.legend(fontsize=7)

    annual_view = annual[annual["source_name"].eq("stage372_30w_full_path")].copy()
    annual_view["year"] = annual_view["window_name"].str.replace("year_", "", regex=False)
    ax_annual.bar(annual_view["year"], annual_view["period_pnl_on_30w_pct"], color="#059669")
    ax_annual.axhline(0.0, color="#111827", linewidth=0.8)
    ax_annual.set_title("Calendar-year PnL / 300k capital")
    ax_annual.tick_params(axis="x", rotation=30)
    ax_annual.grid(axis="y", alpha=0.25)

    ax_margin.plot(pd.to_datetime(full_curve["date"]), full_curve["broker10_margin_to_rebased_equity_pct"], color="#7c3aed")
    ax_margin.axhline(100.0, color="#111827", linestyle="--", linewidth=0.9)
    ax_margin.axhline(90.0, color="#64748b", linestyle=":", linewidth=0.9)
    ax_margin.set_title("Broker10 margin / equity")
    ax_margin.grid(alpha=0.25)

    fig.suptitle("Stage374 Stage372 30w multiperiod audit", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    rolling: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage374 Stage372 30万启动资金多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 基准官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 本阶段候选：`{VARIANT_30W}`",
        "- 性质：只读研究回测；不修改官方实盘配置，不连接 CTP，不调用下单。",
        "- 变量：只把启动资金和 C3 资金从 `200000` 改为 `300000`；不改 alpha、AI池、入场、恢复仓阈值、强制减仓阈值。",
        "",
        "## 检查结论",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期窗口",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## 年度拆分",
        "",
        _md_table(annual, max_rows=20),
        "",
        "## 月度拆分",
        "",
        _md_table(monthly, max_rows=120),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 63/126/252 日任意启动体验",
        "",
        _md_table(rolling, max_rows=20),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    spec = _spec_30w(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    annual_source_daily: pd.DataFrame | None = None

    for window_name, window_label, group, start, end in s660.WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage663] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, forced_events = _run_window(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        if window_name == "full_2020_20260430":
            annual_source_daily = frame.copy()
        row, curve, costs = _window_metrics(
            frame,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name="stage372_30w_independent_window",
            caveat="历史窗口独立重跑，30万 fresh capital，预热期只初始化指标。",
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    ytd_frame, ytd_forced = _run_latest_ytd(spec=spec, metadata=metadata)
    ytd_row, ytd_curve, ytd_costs = _window_metrics(
        ytd_frame,
        window_name="ytd_2026_latest_ai",
        window_label="2026年初至2026-06-04最新AI池",
        group="latest_ytd",
        source_name="stage372_30w_latest_ai_ytd",
        caveat="最新 AI 池独立年初至今影子盘。",
        forced_events=ytd_forced,
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    if annual_source_daily is None:
        raise RuntimeError("full window daily not generated")
    annual, monthly = _annual_monthly(annual_source_daily, "stage372_30w_full_path")
    ytd_annual, ytd_monthly = _annual_monthly(ytd_frame, "stage372_30w_latest_ai_ytd")
    annual = pd.concat([annual, ytd_annual], ignore_index=True, sort=False)
    monthly = pd.concat([monthly, ytd_monthly], ignore_index=True, sort=False)
    rolling = s661._rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    checks = _check_rows(summary, cost, rolling)
    hard_fail_checks = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch_checks = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_label = (
        "stage372_30w_multiperiod_watch_pass"
        if not hard_fail_checks
        else "stage372_30w_multiperiod_has_hard_fail"
    )
    decision = {
        "stage": "Stage374",
        "script_stage": "Stage663",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_live_version": OFFICIAL_LIVE_VERSION,
        "candidate_variant": VARIANT_30W,
        "capital": CAPITAL_30W,
        "decision": decision_label,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "outputs": {
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "rolling": str(ROLLING_PATH),
            "checks": str(CHECKS_PATH),
            "decision": str(DECISION_PATH),
        },
        "execution_scope": "read-only backtest only; no CTP connection and no order API call",
    }

    _plot_report(summary, curves, annual)
    _write_report(summary, cost, annual, monthly, rolling, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
