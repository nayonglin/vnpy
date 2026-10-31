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
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage707_recovery_all_cases_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage707_recovery_all_cases_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_stage707"
RECOVERY_SIGNALS = "long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

WINDOWS: tuple[tuple[str, str, str, str, str], ...] = (
    ("full_2020_20260430", "2020起点至2026-04-30", "full", "2020-01-01", "2026-04-30"),
    ("since_2021", "2021起点至2026-04-30", "start_year", "2021-01-01", "2026-04-30"),
    ("since_2022", "2022起点至2026-04-30", "start_year", "2022-01-01", "2026-04-30"),
    ("since_2023", "2023起点至2026-04-30", "start_year", "2023-01-01", "2026-04-30"),
    ("since_2024", "2024起点至2026-04-30", "start_year", "2024-01-01", "2026-04-30"),
    ("since_2025", "2025起点至2026-04-30", "start_year", "2025-01-01", "2026-04-30"),
    ("since_2026", "2026起点至2026-04-30", "start_year", "2026-01-01", "2026-04-30"),
    ("phase_2020_2021", "2020-2021独立启动", "phase", "2020-01-01", "2021-12-31"),
    ("phase_2022_2023", "2022-2023独立启动", "phase", "2022-01-01", "2023-12-31"),
    ("phase_2024_2025", "2024-2025独立启动", "phase", "2024-01-01", "2025-12-31"),
    ("phase_2026_latest", "2026独立启动至2026-04-30", "phase", "2026-01-01", "2026-04-30"),
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
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


def _candidate_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage707 recovery all native entry cases",
        note=(
            "Official Stage372 unchanged except the existing clean-book 0.1-floor recovery lift is allowed "
            "for all native trend entry cases instead of only case1a."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": RECOVERY_SIGNALS,
        "streak_entry_structure_recovery_min_multiplier": 1.0,
        "streak_entry_structure_recovery_require_flat_portfolio": True,
        "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
        "streak_entry_structure_recovery_require_rsi_confirmation": False,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_recovery_all_cases_stage707")


def _metric_row(
    frame: pd.DataFrame,
    *,
    spec: s653.ForcedVariant,
    window_name: str,
    window_label: str,
    window_group: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    ordered = frame.sort_values("date").reset_index(drop=True)
    if ordered.empty:
        raise ValueError(f"empty window frame: {window_name} {spec.capital.variant}")

    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    net_pnl = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
    slippage = pd.to_numeric(ordered.get("total_slippage", ordered.get("slippage", 0.0)), errors="coerce").fillna(0.0)
    margin_exact = pd.to_numeric(ordered.get("broker10_total_margin_exact", 0.0), errors="coerce").fillna(0.0)
    margin = (margin_exact / equity.replace(0.0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    dd = _drawdown_pct(equity)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]

    events = forced_events.copy()
    event_count = 0
    event_volume = 0.0
    if not events.empty:
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
        events = events[
            events["variant"].astype(str).eq(spec.capital.variant)
            & events["date"].ge(ordered["date"].min())
            & events["date"].le(ordered["date"].max())
        ]
        event_count = int(len(events))
        event_volume = float(pd.to_numeric(events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    row = {
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "profile": spec.profile,
        "window_name": window_name,
        "window_label": window_label,
        "window_group": window_group,
        "analysis_start": pd.Timestamp(ordered["date"].iloc[0]).date().isoformat(),
        "analysis_end": pd.Timestamp(ordered["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(ordered)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "cagr_pct": _cagr_pct(equity, ordered["date"]),
        "max_dd_pct": float(dd.min()),
        "ulcer_pct": float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0))))),
        "sharpe": _sharpe(equity),
        "min_equity": float(equity.min()),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_equity_pct": float(margin.quantile(0.95)),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "days_equity_below_zero": int(equity.le(0.0).sum()),
        "total_slippage": float(slippage.sum()),
        "total_trade_count": float(pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd30_pass": int(float(dd.min()) >= -30.0),
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
        "account_survival_pass": int(equity.min() > 0.0),
        "deployable_pass": int(float(dd.min()) >= -40.0 and margin.max() <= 100.0 + 1e-9 and equity.min() > 0.0),
    }

    curve = pd.DataFrame(
        {
            "date": ordered["date"],
            "variant": spec.capital.variant,
            "label": spec.capital.label,
            "window_name": window_name,
            "window_label": window_label,
            "window_group": window_group,
            "account_equity": equity,
            "drawdown_pct": dd,
            "broker10_margin_to_equity_pct": margin,
            "net_pnl": net_pnl,
            "trade_count": pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0),
            "total_slippage": slippage,
        }
    )

    cost_rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0):
        stressed = equity - slippage.cumsum() * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = (margin_exact / stressed.replace(0.0, np.nan) * 100.0).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(0.0)
        cost_rows.append(
            {
                "variant": spec.capital.variant,
                "label": spec.capital.label,
                "window_name": window_name,
                "cost_multiplier": multiplier,
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
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
    return row, curve, cost_rows


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fields = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_closed_volume",
    ]
    for window_name, group in summary.groupby("window_name", sort=False):
        base = group[group["variant"].eq(BASE_VARIANT)]
        candidate = group[group["variant"].eq(CANDIDATE_VARIANT)]
        if base.empty or candidate.empty:
            continue
        b = base.iloc[0]
        c = candidate.iloc[0]
        base_ret = float(b["total_return_pct"])
        cand_ret = float(c["total_return_pct"])
        row = {
            "window_name": window_name,
            "window_group": str(c["window_group"]),
            "base_return_pct": base_ret,
            "candidate_return_pct": cand_ret,
            "return_retention_pct": cand_ret / base_ret * 100.0 if base_ret > 0 else 0.0,
        }
        for field in fields:
            row[f"base_{field}"] = float(b.get(field, 0.0) or 0.0)
            row[f"candidate_{field}"] = float(c.get(field, 0.0) or 0.0)
            row[f"delta_{field}"] = row[f"candidate_{field}"] - row[f"base_{field}"]
        for multiplier in (2.0, 3.0):
            bcost = cost[
                cost["variant"].eq(BASE_VARIANT)
                & cost["window_name"].eq(window_name)
                & cost["cost_multiplier"].eq(multiplier)
            ]
            ccost = cost[
                cost["variant"].eq(CANDIDATE_VARIANT)
                & cost["window_name"].eq(window_name)
                & cost["cost_multiplier"].eq(multiplier)
            ]
            if not bcost.empty and not ccost.empty:
                row[f"base_{multiplier:.0f}x_max_dd_pct"] = float(bcost["max_dd_pct"].iloc[0])
                row[f"candidate_{multiplier:.0f}x_max_dd_pct"] = float(ccost["max_dd_pct"].iloc[0])
                row[f"delta_{multiplier:.0f}x_max_dd_pct"] = (
                    float(ccost["max_dd_pct"].iloc[0]) - float(bcost["max_dd_pct"].iloc[0])
                )
                row[f"candidate_{multiplier:.0f}x_deployable_pass"] = int(ccost["deployable_pass"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def _annual_monthly(full_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = full_curves[full_curves["window_name"].eq("full_2020_20260430")].copy()
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["year"] = data["date"].dt.year
    data["month"] = data["date"].dt.strftime("%Y-%m")
    rows_annual: list[dict[str, Any]] = []
    rows_monthly: list[dict[str, Any]] = []
    for (variant, year), group in data.groupby(["variant", "year"], sort=True):
        rows_annual.append(_period_row(group, variant=variant, key_name="year", key_value=year))
    for (variant, month), group in data.groupby(["variant", "month"], sort=True):
        rows_monthly.append(_period_row(group, variant=variant, key_name="month", key_value=month))
    return pd.DataFrame(rows_annual), pd.DataFrame(rows_monthly)


def _period_row(group: pd.DataFrame, *, variant: str, key_name: str, key_value: Any) -> dict[str, Any]:
    ordered = group.sort_values("date")
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
    start_equity = float(equity.iloc[0] - pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0).iloc[0])
    path = pd.Series([start_equity] + equity.tolist())
    dd = _drawdown_pct(path)
    return {
        "variant": variant,
        key_name: key_value,
        "period_start_equity": start_equity,
        "period_end_equity": float(equity.iloc[-1]),
        "period_pnl": float(pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0).sum()),
        "period_return_pct": float((equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
        "period_max_dd_pct": float(dd.min()),
        "total_trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
        "total_slippage": float(pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).sum()),
    }


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    start_years = comparison[comparison["window_group"].eq("start_year")].copy()
    phases = comparison[comparison["window_group"].eq("phase")].copy()
    cand_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    cand_cost2 = cost[(cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()

    add(
        "full_return_retention_ge80",
        "pass" if float(full["return_retention_pct"]) >= 80.0 else "fail",
        float(full["return_retention_pct"]),
        ">= 80%",
        "全周期收益保留必须足够高，否则只是降风险壳。",
    )
    add(
        "full_dd30_pass",
        "pass" if float(full["candidate_max_dd_pct"]) >= -30.0 else "fail",
        float(full["candidate_max_dd_pct"]),
        ">= -30%",
        "本线核心目标是回撤压到30以内。",
    )
    add(
        "full_sharpe_not_lower",
        "pass" if float(full["delta_sharpe"]) >= 0.0 else "watch",
        float(full["delta_sharpe"]),
        ">= 0",
        "收益降低时 Sharpe 至少要补偿。",
    )
    add(
        "full_broker10_100_pass",
        "pass" if int(cand_summary[cand_summary["window_name"].eq("full_2020_20260430")]["broker10_100_pass"].iloc[0]) == 1 else "fail",
        float(full["candidate_max_broker10_margin_to_equity_pct"]),
        "<= 100%",
        "不能用更危险的保证金路径换取回撤改善。",
    )
    add(
        "cost2_full_dd40_pass",
        "pass"
        if int(
            cand_cost2[cand_cost2["window_name"].eq("full_2020_20260430")]["deployable_pass"].iloc[0]
        )
        == 1
        else "fail",
        float(cand_cost2[cand_cost2["window_name"].eq("full_2020_20260430")]["max_dd_pct"].iloc[0]),
        "2x cost deployable",
        "2x成本压力下不能穿 DD40 或 broker100。",
    )
    add(
        "start_years_min_retention_ge70",
        "pass" if float(start_years["return_retention_pct"].min()) >= 70.0 else "fail",
        float(start_years["return_retention_pct"].min()),
        ">= 70%",
        "起始年份不能只在2020全周期好看。",
    )
    add(
        "start_years_dd_not_worse_by_3pp",
        "pass" if float(start_years["delta_max_dd_pct"].min()) >= -3.0 else "fail",
        float(start_years["delta_max_dd_pct"].min()),
        ">= -3pp",
        "任一起点不能显著加深回撤。",
    )
    add(
        "start_years_dd40_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("start_year")]["dd40_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("start_year")]["max_dd_pct"].min()),
        "all start-year DD >= -40%",
        "冷启动生存边界必须全部过。",
    )
    add(
        "phase_min_retention_ge65",
        "pass" if float(phases["return_retention_pct"].min()) >= 65.0 else "watch",
        float(phases["return_retention_pct"].min()),
        ">= 65%",
        "分段窗口用于观察是否只有单一周期胜出。",
    )
    add(
        "phase_dd40_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("phase")]["dd40_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("phase")]["max_dd_pct"].min()),
        "all phase DD >= -40%",
        "分段独立启动不能破坏生存边界。",
    )
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = (
        "recovery_all_cases_next_quarterly_validation"
        if not hard_fail
        else "recovery_all_cases_multiperiod_not_promoted"
    )
    return {
        "stage": "Stage421",
        "script_stage": "Stage707",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": label,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "streak_risk_multipliers_before": "1.0,1.0,1.0,0.1",
            "streak_risk_multipliers_after": "1.0,1.0,1.0,0.1",
            "recovery_signals_before": "long_case1a,short_case1a",
            "recovery_signals_after": RECOVERY_SIGNALS,
            "recovery_requires_flat_portfolio": True,
            "recovery_max_same_direction_corr": 0.30,
        },
        "checks": checks.to_dict("records"),
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    plot_data = curves[curves["window_name"].isin(["full_2020_20260430", "since_2022", "phase_2024_2025"])].copy()
    labels = {
        BASE_VARIANT: "A official",
        CANDIDATE_VARIANT: "C recovery all cases",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#2563eb",
    }
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    for ax, (window_name, group) in zip(axes, plot_data.groupby("window_name", sort=False)):
        for variant, series in group.sort_values("date").groupby("variant", sort=False):
            ax.plot(
                series["date"],
                series["account_equity"],
                label=labels.get(variant, variant),
                linewidth=1.5,
                color=colors.get(variant),
            )
        ax.axhline(OFFICIAL_LIVE_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax.set_title(window_name)
        ax.set_ylabel("equity")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "window_name",
        "return_retention_pct",
        "base_total_return_pct",
        "candidate_total_return_pct",
        "base_max_dd_pct",
        "candidate_max_dd_pct",
        "delta_max_dd_pct",
        "base_sharpe",
        "candidate_sharpe",
        "delta_sharpe",
    ]
    lines = [
        "# Stage421 / Script707 Recovery All Cases Multiperiod Validation",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，`case1a` 恢复规则。",
        "- C：保持 `streak_risk_multipliers=1,1,1,0.1`，仅把既有 clean-book recovery lift 从 `case1a` 扩到所有原生趋势入场 case。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Checks",
        "",
        _md_table(checks),
        "",
        "## Comparison",
        "",
        _md_table(comparison[key_cols], max_rows=40),
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## Annual Full Path",
        "",
        _md_table(annual, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    base_spec = s660._official_spec(metadata)
    candidate_spec = _candidate_spec(metadata)
    specs = [base_spec, candidate_spec]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    forced_frames: list[pd.DataFrame] = []
    for window_name, window_label, window_group, start, end in WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage707] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events = s660._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            if not forced_events.empty:
                forced_events["window_name"] = window_name
                forced_frames.append(forced_events)
            row, curve, costs = _metric_row(
                frame,
                spec=spec,
                window_name=window_name,
                window_label=window_label,
                window_group=window_group,
                forced_events=forced_events,
            )
            summary_rows.append(row)
            curve_frames.append(curve)
            cost_rows.extend(costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison(summary, cost)
    annual, monthly = _annual_monthly(curves)
    checks = _check_rows(summary, comparison, cost)
    decision = _decision(summary, comparison, cost, checks)

    _plot(curves)
    _write_report(summary, comparison, cost, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
