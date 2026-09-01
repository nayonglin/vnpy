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
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_BASE_PROFILE_NAME,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_STAGE659_MODEL_TAG,
    OFFICIAL_LIVE_STAGE659_PREFIX,
    OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    OFFICIAL_LIVE_VERSION,
    build_official_live_manifest,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage660_stage653_multiperiod_live_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage660_stage653_multiperiod_live_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE653_MODEL_TAG = "stage653_stage526_200k_forced_margin_deleverage_v1"
STAGE653_PREFIX = "qmt_roll_stage653_stage526_200k_forced_margin_deleverage"
STAGE659_MODEL_TAG = OFFICIAL_LIVE_STAGE659_MODEL_TAG
STAGE659_PREFIX = OFFICIAL_LIVE_STAGE659_PREFIX

STAGE653_DAILY_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_daily_{STAGE653_MODEL_TAG}.csv"
STAGE653_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_summary_{STAGE653_MODEL_TAG}.csv"
STAGE653_COST_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_cost_stress_{STAGE653_MODEL_TAG}.csv"
STAGE653_ROLLING_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_rolling_holding_{STAGE653_MODEL_TAG}.csv"
STAGE653_FORCED_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_forced_events_{STAGE653_MODEL_TAG}.csv"
STAGE653_EVENT_PATH = OUTPUT_DIR / f"{STAGE653_PREFIX}_event_days_{STAGE653_MODEL_TAG}.csv"

STAGE659_DAILY_PATH = OUTPUT_DIR / f"{STAGE659_PREFIX}_daily_{STAGE659_MODEL_TAG}.csv"
STAGE659_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE659_PREFIX}_summary_{STAGE659_MODEL_TAG}.csv"
STAGE659_MONTHLY_PATH = OUTPUT_DIR / f"{STAGE659_PREFIX}_monthly_{STAGE659_MODEL_TAG}.csv"
STAGE659_CURRENT_POSITIONS_PATH = OUTPUT_DIR / f"{STAGE659_PREFIX}_current_positions_{STAGE659_MODEL_TAG}.csv"
STAGE659_DECISION_PATH = OUTPUT_DIR / f"{STAGE659_PREFIX}_decision_{STAGE659_MODEL_TAG}.json"

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

WINDOWS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("full_2020_20260430", "2020-2026Q2历史全周期", "historical_full", "2020-01-01", "2026-04-30"),
    ("since_2021", "2021起点至历史最新", "start_year", "2021-01-01", None),
    ("since_2022", "2022起点至历史最新", "start_year", "2022-01-01", None),
    ("since_2023", "2023起点至历史最新", "start_year", "2023-01-01", None),
    ("since_2024", "2024起点至历史最新", "start_year", "2024-01-01", None),
    ("since_2025", "2025起点至历史最新", "start_year", "2025-01-01", None),
    ("since_2026_hist", "2026起点至历史最新", "start_year", "2026-01-01", None),
    ("phase_2020_2021", "2020-2021独立阶段", "market_phase", "2020-01-01", "2021-12-31"),
    ("phase_2022_2023", "2022-2023独立阶段", "market_phase", "2022-01-01", "2023-12-31"),
    ("phase_2024_2025", "2024-2025独立阶段", "market_phase", "2024-01-01", "2025-12-31"),
    ("weak_2021_drawdown", "2021核心回撤窗口", "stress_window", "2021-05-01", "2021-07-31"),
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")


def _load_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_daily(path: Path, source_name: str) -> pd.DataFrame:
    frame = _load_csv(path)
    frame = frame[frame["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    if frame.empty:
        raise ValueError(f"official live profile not found in {path}: {OFFICIAL_LIVE_PROFILE_NAME}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "net_pnl",
        "account_equity",
        "total_net_pnl",
        "total_slippage",
        "trade_count",
        "slippage",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["source_name"] = source_name
    return frame.sort_values("date").reset_index(drop=True)


def _official_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    specs = s653._variants(identity_map)
    for spec in specs:
        if spec.capital.variant == OFFICIAL_LIVE_PROFILE_NAME:
            return spec
    for spec in specs:
        if spec.capital.variant == OFFICIAL_LIVE_BASE_PROFILE_NAME:
            capital = replace(
                spec.capital,
                variant=OFFICIAL_LIVE_PROFILE_NAME,
                label=f"20w {OFFICIAL_LIVE_ALIAS} recovery sleeve",
                note=(
                    "Stage372 official live: force95->80 base plus one-lot recovery sleeve only for clean "
                    "long_case1a/short_case1a structure recovery at the 0.1 risk floor."
                ),
            )
            overrides = {**spec.overrides, **OFFICIAL_LIVE_STRATEGY_OVERRIDES}
            return replace(spec, capital=capital, overrides=overrides, profile="forced_margin_95_to_80_recovery_sleeve")
    raise ValueError(f"official spec/base profile not found: {OFFICIAL_LIVE_PROFILE_NAME}")


def _run_independent_window(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start.to_pydatetime()
        s653.s517.END_DT = analysis_end.to_pydatetime()
        daily, positions, _usage, forced_events = s653._run_variant(replace(spec), metadata)
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end

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
    net_pnl = ordered["net_pnl"].astype(float)
    rebased = ordered["account_equity"].astype(float)
    dates = ordered["date"]
    dd = _drawdown_pct(rebased)
    margin = ordered["broker10_total_margin_exact"].astype(float) / rebased.replace(0.0, np.nan) * 100.0
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
            events["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)
            & events["date"].ge(pd.Timestamp(start_date))
            & events["date"].le(pd.Timestamp(end_date))
        ]
        event_count = int(len(events))
        event_volume = float(pd.to_numeric(events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    summary = {
        "window_name": window_name,
        "window_label": window_label,
        "window_group": group,
        "source_name": source_name,
        "analysis_start": start_date,
        "analysis_end": end_date,
        "trading_days": int(len(ordered)),
        "start_equity_path": float(ordered["account_equity"].iloc[0]),
        "end_equity_path": float(ordered["account_equity"].iloc[-1]),
        "path_return_pct": float((ordered["account_equity"].iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "rebased_end_equity": float(rebased.iloc[-1]),
        "rebased_total_return_pct": float((rebased.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "rebased_cagr_pct": _cagr_pct(rebased, dates),
        "rebased_max_dd_pct": float(dd.min()),
        "rebased_sharpe": _sharpe(rebased),
        "rebased_min_equity": float(rebased.min()),
        "max_broker10_margin_to_rebased_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_rebased_equity_pct": float(margin.quantile(0.95)),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "nonzero_daily_win_rate_pct": float((nonzero_pnl.gt(0.0)).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
        "broker10_90_watch_pass": int(margin.max() < 90.0),
        "account_survival_pass": int(rebased.min() > 0.0),
        "deployable_pass": int(float(dd.min()) >= -40.0 and margin.max() <= 100.0 + 1e-9 and rebased.min() > 0.0),
        "caveat": caveat,
    }

    curve = pd.DataFrame(
        {
            "date": dates,
            "window_name": window_name,
            "window_label": window_label,
            "window_group": group,
            "source_name": source_name,
            "rebased_equity": rebased,
            "rebased_nav": rebased / OFFICIAL_LIVE_CAPITAL,
            "drawdown_pct": dd,
            "broker10_margin_to_rebased_equity_pct": margin,
            "net_pnl": net_pnl,
            "trade_count": ordered["trade_count"].astype(float),
            "total_slippage": ordered["total_slippage"].astype(float),
        }
    )

    cost_rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0):
        stressed = rebased - ordered["total_slippage"].astype(float).cumsum() * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = ordered["broker10_total_margin_exact"].astype(float) / stressed.replace(0.0, np.nan) * 100.0
        stressed_margin = stressed_margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cost_rows.append(
            {
                "window_name": window_name,
                "window_label": window_label,
                "cost_multiplier": multiplier,
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(stressed_dd.min()),
                "sharpe": _sharpe(stressed),
                "max_broker10_margin_to_equity_pct": float(stressed_margin.max()),
                "days_over_100pct": int(stressed_margin.gt(100.0 + 1e-9).sum()),
                "account_survival_pass": int(stressed.min() > 0.0),
                "deployable_pass": int(stressed_dd.min() >= -40.0 and stressed_margin.max() <= 100.0 + 1e-9 and stressed.min() > 0.0),
            }
        )
    return summary, curve, cost_rows


def _period_metrics(group: pd.DataFrame, *, name: str, label: str, period_group: str, source_name: str) -> dict[str, Any]:
    ordered = group.sort_values("date").reset_index(drop=True)
    if ordered.empty:
        raise ValueError(f"empty period: {name}")
    dates = ordered["date"]
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
        "period_pnl_on_200k_pct": float(net_pnl.sum() / OFFICIAL_LIVE_CAPITAL * 100.0),
        "period_return_pct": float((end_equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
        "period_max_dd_pct": float(dd.min()),
        "period_sharpe": _sharpe(pd.Series(path)),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "nonzero_daily_win_rate_pct": float((nonzero_pnl.gt(0.0)).mean() * 100.0) if len(nonzero_pnl) else 0.0,
    }


def _annual_monthly(frame: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("date").copy()
    ordered["year"] = ordered["date"].dt.year.astype(str)
    ordered["month"] = ordered["date"].dt.to_period("M").astype(str)

    annual_rows: list[dict[str, Any]] = []
    for year, group in ordered.groupby("year", sort=True):
        annual_rows.append(
            _period_metrics(
                group,
                name=f"year_{year}",
                label=f"{year}年度",
                period_group="calendar_year",
                source_name=source_name,
            )
        )

    monthly_rows: list[dict[str, Any]] = []
    for month, group in ordered.groupby("month", sort=True):
        monthly_rows.append(
            _period_metrics(
                group,
                name=f"month_{month}",
                label=f"{month}月度",
                period_group="calendar_month",
                source_name=source_name,
            )
        )
    return pd.DataFrame(annual_rows), pd.DataFrame(monthly_rows)


def _check_rows(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, ytd_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    full = summary[summary["window_name"].eq("full_2020_20260430")]
    ytd = summary[summary["window_name"].eq("ytd_2026_latest_ai")]
    if not full.empty:
        row = full.iloc[0]
        rows.extend(
            [
                {
                    "check_name": "full_dd40",
                    "status": "pass" if float(row["rebased_max_dd_pct"]) >= -40.0 else "fail",
                    "value": float(row["rebased_max_dd_pct"]),
                    "threshold": ">= -40",
                    "comment": "全周期正常成本最大回撤。",
                },
                {
                    "check_name": "full_margin100",
                    "status": "pass" if int(row["days_over_100pct"]) == 0 else "fail",
                    "value": int(row["days_over_100pct"]),
                    "threshold": "0 days",
                    "comment": "全周期 broker10 保证金不穿100%。",
                },
                {
                    "check_name": "full_margin90_watch",
                    "status": "pass" if int(row["days_over_90pct"]) == 0 else "watch",
                    "value": int(row["days_over_90pct"]),
                    "threshold": "0 days",
                    "comment": "实盘观察线；当前官方版本全周期低于90%。",
                },
            ]
        )
    if not ytd.empty:
        row = ytd.iloc[0]
        rows.append(
            {
                "check_name": "latest_ytd_no_signal_risk",
                "status": "pass" if float(row["max_broker10_margin_to_rebased_equity_pct"]) < 90.0 and float(row["rebased_min_equity"]) > 0 else "watch",
                "value": float(row["rebased_total_return_pct"]),
                "threshold": "margin < 90 and equity > 0",
                "comment": "最新 AI 池年初至今口径。",
            }
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
                "comment": "全周期2x成本压力最大回撤。",
            }
        )
    if not rolling.empty:
        focus = rolling[rolling["holding_days"].isin([63, 126, 252])].copy()
        if not focus.empty:
            rows.append(
                {
                    "check_name": "rolling_positive_rate_min",
                    "status": "pass" if float(focus["positive_rate_pct"].min()) >= 50.0 else "watch",
                    "value": float(focus["positive_rate_pct"].min()),
                    "threshold": ">= 50%",
                    "comment": "63/126/252日任意启动正收益率下界。",
                }
            )
            rows.append(
                {
                    "check_name": "rolling_p05_return_min",
                    "status": "watch" if float(focus["p05_return_pct"].min()) < 0.0 else "pass",
                    "value": float(focus["p05_return_pct"].min()),
                    "threshold": ">= 0 preferred",
                    "comment": "短周期左尾仍为负，属于体验风险。",
                }
            )
    if not ytd_summary.empty:
        ytd_row = ytd_summary.iloc[0].to_dict()
        rows.append(
            {
                "check_name": "stage659_latest_report_exists",
                "status": "pass",
                "value": float(ytd_row.get("total_return_pct", 0.0) or 0.0),
                "threshold": "generated",
                "comment": "Stage659 当前官方实盘最新影子盘已纳入本报告。",
            }
        )
    return pd.DataFrame(rows)


def _plot_report(summary: pd.DataFrame, curves: pd.DataFrame, annual: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_equity, ax_multi, ax_annual, ax_margin = axes.flatten()

    full_curve = curves[curves["window_name"].eq("full_2020_20260430")].sort_values("date")
    if not full_curve.empty:
        ax_equity.plot(pd.to_datetime(full_curve["date"]), full_curve["rebased_nav"], color="#2563eb", linewidth=1.2, label="NAV")
        ax_equity_2 = ax_equity.twinx()
        ax_equity_2.plot(pd.to_datetime(full_curve["date"]), full_curve["drawdown_pct"], color="#dc2626", linewidth=0.9, alpha=0.75, label="DD")
        ax_equity_2.set_ylabel("Drawdown %")
        ax_equity_2.axhline(-40.0, color="#111827", linestyle="--", linewidth=0.8)
    ax_equity.set_title("Official live full-period NAV and drawdown")
    ax_equity.set_ylabel("NAV")
    ax_equity.grid(alpha=0.25)

    multi_names = [
        "since_2021",
        "since_2022",
        "since_2023",
        "since_2024",
        "since_2025",
        "ytd_2026_latest_ai",
    ]
    for name in multi_names:
        frame = curves[curves["window_name"].eq(name)].sort_values("date")
        if frame.empty:
            continue
        x = np.arange(len(frame))
        ax_multi.plot(x, frame["rebased_nav"], linewidth=1.0, label=str(frame["window_label"].iloc[0]))
    ax_multi.set_title("Start-window rebased NAV curves")
    ax_multi.set_xlabel("Trading days since window start")
    ax_multi.set_ylabel("NAV")
    ax_multi.grid(alpha=0.25)
    ax_multi.legend(fontsize=7)

    annual_view = annual[annual["source_name"].eq("official_live_independent_full_path")].copy()
    annual_view["year"] = annual_view["window_name"].str.replace("year_", "", regex=False)
    ax_annual.bar(annual_view["year"], annual_view["period_pnl_on_200k_pct"], color="#059669")
    ax_annual.axhline(0.0, color="#111827", linewidth=0.8)
    ax_annual.set_title("Calendar-year PnL / 200k capital")
    ax_annual.set_ylabel("Return %")
    ax_annual.tick_params(axis="x", rotation=30)
    ax_annual.grid(axis="y", alpha=0.25)

    if not full_curve.empty:
        ax_margin.plot(
            pd.to_datetime(full_curve["date"]),
            full_curve["broker10_margin_to_rebased_equity_pct"],
            color="#7c3aed",
            linewidth=1.0,
        )
    ax_margin.axhline(100.0, color="#111827", linestyle="--", linewidth=0.9)
    ax_margin.axhline(90.0, color="#64748b", linestyle=":", linewidth=0.9)
    ax_margin.set_title("Broker10 margin / rebased equity")
    ax_margin.set_ylabel("Margin %")
    ax_margin.grid(alpha=0.25)

    fig.suptitle(f"{OFFICIAL_LIVE_VERSION} multiperiod live audit", fontsize=14)
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
    stage653_summary: pd.DataFrame,
    stage653_cost: pd.DataFrame,
    stage659_summary: pd.DataFrame,
    stage659_monthly: pd.DataFrame,
    stage659_current_positions: pd.DataFrame,
    stage653_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    full_cols = [
        "window_name",
        "window_label",
        "analysis_start",
        "analysis_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_cagr_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "days_over_100pct",
        "days_over_90pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "deployable_pass",
    ]
    annual_cols = [
        "window_name",
        "analysis_start",
        "analysis_end",
        "period_start_equity",
        "period_end_equity",
        "period_pnl_on_200k_pct",
        "period_return_pct",
        "period_max_dd_pct",
        "period_sharpe",
        "max_broker10_margin_to_equity_pct",
        "total_trade_count",
    ]
    lines = [
        "# Stage660 当前官方实盘多周期检查报告",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 官方实盘版本：`{OFFICIAL_LIVE_VERSION}`",
        f"- 策略体：`{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 账户口径：`{OFFICIAL_LIVE_CAPITAL:,.0f}`",
        "- 性质：只读多周期审计；不改策略参数，不连接 CTP，不调用下单。",
        "- 历史全周期输入：当前官方版本逐窗口独立重跑，至 `2026-04-30`。",
        "- 历史多窗口输入：当前官方版本逐窗口独立重跑，至 `2026-04-30`。",
        "- 最新年初至今输入：Stage659 当前官方版本最新 AI 池影子盘，至 `2026-06-04`。",
        "- 注意：历史窗口只重新设定起点和终点，不重新训练、不重新调参；预热期只用于指标初始化。",
        "",
        "## 外部调研判断",
        "",
        "- 公开回测实践通常要求 out-of-sample / walk-forward / rolling windows，而不是只看单条全周期曲线。",
        "- 本阶段不重新优化参数，只做固定线上版本的多窗口稳健性、成本压力和保证金压力审计。",
        "",
        "## 检查结论",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期窗口",
        "",
        _md_table(summary[full_cols], max_rows=80),
        "",
        "## 年度拆分",
        "",
        _md_table(annual[annual_cols], max_rows=20),
        "",
        "## 最新 YTD 月度",
        "",
        _md_table(stage659_monthly, max_rows=80),
        "",
        "## 63/126/252 日任意启动体验",
        "",
        _md_table(
            rolling[
                [
                    "holding_days",
                    "sample_count",
                    "min_return_pct",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "window_name",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 历史基准全周期参考",
        "",
        _md_table(stage653_summary, max_rows=20),
        "",
        "## 历史基准成本压力参考",
        "",
        _md_table(stage653_cost, max_rows=20),
        "",
        "## Stage653 关键风险日",
        "",
        _md_table(stage653_events, max_rows=30),
        "",
        "## Stage659 最新影子盘参考",
        "",
        _md_table(stage659_summary, max_rows=20),
        "",
        "## 当前持仓",
        "",
        _md_table(stage659_current_positions, max_rows=80),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- cost：`{COST_PATH}`",
        f"- annual：`{ANNUAL_PATH}`",
        f"- monthly：`{MONTHLY_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- checks：`{CHECKS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) if decision['hard_fail_checks'] else '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) if decision['watch_checks'] else '无'}`。",
        "- 结论：当前版本可以继续作为官方实盘观察/测试版本，但不是扩大手数的充分理由；短周期左尾和 2x/3x 成本压力仍需要真实 TCA 继续校准。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    manifest = build_official_live_manifest()
    if manifest["profile_name"] != OFFICIAL_LIVE_PROFILE_NAME:
        raise RuntimeError("official live manifest/profile mismatch")

    _require(STAGE653_DAILY_PATH)
    metadata = s513._metadata()
    spec = _official_spec(metadata)
    latest_daily = _prepare_daily(STAGE659_DAILY_PATH, "stage659_latest_ai_ytd")

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    annual_source_daily: pd.DataFrame | None = None
    all_forced_events: list[pd.DataFrame] = []
    for window_name, window_label, group, start, end in WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage660] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, forced_events = _run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        if window_name == "full_2020_20260430":
            annual_source_daily = frame.copy()
        if not forced_events.empty:
            forced_events["window_name"] = window_name
            all_forced_events.append(forced_events)
        row, curve, costs = _window_metrics(
            frame,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name="official_live_independent_window",
            caveat="历史窗口独立重跑，20万 fresh capital，预热期只初始化指标。",
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    ytd_row, ytd_curve, ytd_costs = _window_metrics(
        latest_daily,
        window_name="ytd_2026_latest_ai",
        window_label="2026年初至2026-06-04最新AI池",
        group="latest_ytd",
        source_name="stage659_latest_ai_ytd",
        caveat="最新 AI 池独立年初至今影子盘。",
        forced_events=pd.DataFrame(),
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    if annual_source_daily is None:
        raise RuntimeError("full window daily not generated")
    annual, monthly = _annual_monthly(annual_source_daily, "official_live_independent_full_path")
    ytd_annual, ytd_monthly = _annual_monthly(latest_daily, "stage659_latest_ai_ytd")
    annual = pd.concat([annual, ytd_annual], ignore_index=True, sort=False)
    monthly = pd.concat([monthly, ytd_monthly], ignore_index=True, sort=False)

    rolling = _load_csv(STAGE653_ROLLING_PATH)
    rolling = rolling[rolling["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    for column in ["holding_days", "sample_count", "min_return_pct", "p05_return_pct", "median_return_pct", "positive_rate_pct", "min_window_dd_pct"]:
        rolling[column] = pd.to_numeric(rolling.get(column, 0.0), errors="coerce").fillna(0.0)

    stage653_summary = _load_csv(STAGE653_SUMMARY_PATH)
    stage653_summary = stage653_summary[stage653_summary["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    stage653_cost = _load_csv(STAGE653_COST_PATH)
    stage653_cost = stage653_cost[stage653_cost["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    stage653_events = _load_csv(STAGE653_EVENT_PATH)
    stage653_events = stage653_events[stage653_events["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    stage659_summary = _load_csv(STAGE659_SUMMARY_PATH)
    stage659_summary = stage659_summary[stage659_summary["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    stage659_monthly = _load_csv(STAGE659_MONTHLY_PATH)
    if "variant" in stage659_monthly.columns:
        stage659_monthly = stage659_monthly[stage659_monthly["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    stage659_current_positions = _load_csv(STAGE659_CURRENT_POSITIONS_PATH)
    stage659_decision = _load_json(STAGE659_DECISION_PATH)

    checks = _check_rows(summary, cost, rolling, stage659_summary)
    hard_fail_checks = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch_checks = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_label = (
        "official_live_multiperiod_audit_live_watch_pass_with_cost_tail_risk"
        if not hard_fail_checks
        else "official_live_multiperiod_audit_has_hard_fail"
    )
    decision = {
        "stage": "Stage370",
        "script_stage": "Stage660",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "decision": decision_label,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "stage659_decision": stage659_decision.get("decision", ""),
        "inputs": {
            "stage653_daily": str(STAGE653_DAILY_PATH),
            "stage659_daily": str(STAGE659_DAILY_PATH),
        },
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
    }

    _plot_report(summary, curves, annual)
    _write_report(
        summary,
        cost,
        annual,
        monthly,
        rolling,
        checks,
        stage653_summary,
        stage653_cost,
        stage659_summary,
        stage659_monthly,
        stage659_current_positions,
        stage653_events,
        decision,
    )

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
