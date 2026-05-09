from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database

from main_contract_mapping import load_mapping_df, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage194_stage78_2015_multicycle_viability_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage194_stage78_2015_multicycle_viability"

COVERAGE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
YEAR_COVERAGE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_coverage_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_RETURNS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
EQUITY_CURVES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.csv"
EQUITY_CURVES_HTML_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.html"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

COVERAGE_PASS_THRESHOLD: float = 0.95
REQUESTED_START: datetime = datetime(2015, 1, 5)
TRADING_DAYS_PER_YEAR: int = 240
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def latest_database_date() -> datetime:
    overview = get_database().get_bar_overview()
    ends = [item.end for item in overview if getattr(item, "end", None)]
    if not ends:
        raise RuntimeError("No bar data found in vn.py database.")
    return max(ends)


def exchange_by_value() -> dict[str, Any]:
    overview = get_database().get_bar_overview()
    return {item.exchange.value: item.exchange for item in overview}


def load_contract_date_sets(contract_symbols: set[str], start: datetime, end: datetime) -> dict[str, set[str]]:
    database = get_database()
    exchanges = exchange_by_value()
    result: dict[str, set[str]] = {}
    for vt_symbol in sorted(contract_symbols):
        if "." not in vt_symbol:
            result[vt_symbol] = set()
            continue
        symbol, exchange_value = vt_symbol.split(".", 1)
        exchange = exchanges.get(exchange_value)
        if exchange is None:
            result[vt_symbol] = set()
            continue
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start, end)
        result[vt_symbol] = {bar.datetime.date().isoformat() for bar in bars}
    return result


def build_windows(analysis_end: datetime) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = [
        {
            "window_name": "requested_since_2015",
            "display_label": "2015起点请求窗口",
            "analysis_start": REQUESTED_START,
            "analysis_end": analysis_end,
            "kind": "coverage_request",
            "run_backtest": True,
        },
        {
            "window_name": "early_data_2015_2017",
            "display_label": "2015-2017早期数据段",
            "analysis_start": datetime(2015, 1, 5),
            "analysis_end": datetime(2017, 12, 29),
            "kind": "coverage_request",
            "run_backtest": True,
        },
        {
            "window_name": "transition_2018_2019",
            "display_label": "2018-2019过渡数据段",
            "analysis_start": datetime(2018, 1, 2),
            "analysis_end": datetime(2019, 12, 31),
            "kind": "coverage_request",
            "run_backtest": True,
        },
        {
            "window_name": "full_2020_2026",
            "display_label": "2020-2026正式可信窗口",
            "analysis_start": datetime(2020, 1, 1),
            "analysis_end": analysis_end,
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
        {
            "window_name": "pre_ai_2020_2021",
            "display_label": "2020-2021 AI前窗口",
            "analysis_start": datetime(2020, 1, 1),
            "analysis_end": datetime(2021, 12, 31),
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
        {
            "window_name": "post_signal_2022_2026",
            "display_label": "2022-2026 AI后窗口",
            "analysis_start": datetime(2022, 2, 7),
            "analysis_end": analysis_end,
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
        {
            "window_name": "early_ai_2022_2023",
            "display_label": "2022-2023 AI早期窗口",
            "analysis_start": datetime(2022, 2, 7),
            "analysis_end": datetime(2023, 12, 31),
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
        {
            "window_name": "trend_rich_2024_2025",
            "display_label": "2024-2025趋势富集窗口",
            "analysis_start": datetime(2024, 1, 1),
            "analysis_end": datetime(2025, 12, 31),
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
        {
            "window_name": "latest_2026",
            "display_label": "2026最新窗口",
            "analysis_start": datetime(2026, 1, 1),
            "analysis_end": analysis_end,
            "kind": "trusted_multicycle",
            "run_backtest": True,
        },
    ]

    for year in range(2016, 2026):
        start = datetime(year, 1, 1)
        if start >= analysis_end:
            continue
        windows.append(
            {
                "window_name": f"since_{year}",
                "display_label": f"{year}起点冷启动",
                "analysis_start": start,
                "analysis_end": analysis_end,
                "kind": "start_year",
                "run_backtest": True,
            }
        )
    return windows


def build_year_windows(analysis_end: datetime) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for year in range(2015, analysis_end.year + 1):
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        if year == 2015:
            start = REQUESTED_START
        if start > analysis_end:
            continue
        windows.append(
            {
                "window_name": f"year_{year}",
                "display_label": str(year),
                "analysis_start": start,
                "analysis_end": min(end, analysis_end),
                "kind": "year_coverage",
                "run_backtest": False,
            }
        )
    return windows


def build_coverage_table(
    mapping_df: pd.DataFrame,
    product_symbols: list[str],
    windows: list[dict[str, Any]],
    contract_date_sets: dict[str, set[str]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    product_set = set(product_symbols)
    df = mapping_df[mapping_df["continuous_symbol_vt"].isin(product_set)].copy()
    df = df[df["main_contract_vt"].fillna("") != ""].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)

    for window in windows:
        start_date = window["analysis_start"].date().isoformat()
        end_date = window["analysis_end"].date().isoformat()
        window_df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
        total_mapped_days = 0
        total_present_days = 0

        for product in product_symbols:
            product_df = window_df[window_df["continuous_symbol_vt"] == product].copy()
            mapped_days = len(product_df)
            present_days = 0
            missing_contracts: set[str] = set()
            for row in product_df.itertuples(index=False):
                date_text = str(row.date)
                contract = str(row.main_contract_vt)
                if date_text in contract_date_sets.get(contract, set()):
                    present_days += 1
                else:
                    missing_contracts.add(contract)
            total_mapped_days += mapped_days
            total_present_days += present_days
            rows.append(
                {
                    "window_name": window["window_name"],
                    "display_label": window["display_label"],
                    "kind": window["kind"],
                    "analysis_start": start_date,
                    "analysis_end": end_date,
                    "product_vt_symbol": product,
                    "mapped_days": mapped_days,
                    "present_days": present_days,
                    "missing_days": mapped_days - present_days,
                    "coverage_ratio": present_days / mapped_days if mapped_days else 1.0,
                    "missing_contract_count": len(missing_contracts),
                    "missing_contract_examples": ",".join(sorted(missing_contracts)[:8]),
                }
            )

        rows.append(
            {
                "window_name": window["window_name"],
                "display_label": window["display_label"],
                "kind": window["kind"],
                "analysis_start": start_date,
                "analysis_end": end_date,
                "product_vt_symbol": "__TOTAL__",
                "mapped_days": total_mapped_days,
                "present_days": total_present_days,
                "missing_days": total_mapped_days - total_present_days,
                "coverage_ratio": total_present_days / total_mapped_days if total_mapped_days else 1.0,
                "missing_contract_count": 0,
                "missing_contract_examples": "",
            }
        )

    return pd.DataFrame(rows)


def run_valid_backtests(
    windows: list[dict[str, Any]],
    coverage_table: pd.DataFrame,
    strategy_overrides: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    daily_by_window: dict[str, pd.DataFrame] = {}
    total_rows = coverage_table[coverage_table["product_vt_symbol"] == "__TOTAL__"].copy()
    coverage_by_window = {
        str(row.window_name): float(row.coverage_ratio) for row in total_rows.itertuples(index=False)
    }

    seen: set[tuple[str, str]] = set()
    for window in windows:
        if not bool(window["run_backtest"]):
            continue
        window_name = str(window["window_name"])
        coverage_ratio = coverage_by_window.get(window_name, 0.0)
        if coverage_ratio < COVERAGE_PASS_THRESHOLD:
            continue
        analysis_start: datetime = window["analysis_start"]
        analysis_end: datetime = window["analysis_end"]
        dedupe_key = (analysis_start.date().isoformat(), analysis_end.date().isoformat())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        print(f"[stage194] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        _, analysis_df, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            preload_start=analysis_start - timedelta(days=365),
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{window_name}",
            chart_title=f"Stage194 {OFFICIAL_STAGE78_VERSION} {window_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                model_tag=MODEL_TAG,
                window_name=window_name,
                display_label=str(window["display_label"]),
                kind=str(window["kind"]),
                capital=OFFICIAL_STAGE78_CAPITAL,
                base_risk_ratio=BASE_RISK_RATIO,
                coverage_ratio=coverage_ratio,
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
        if analysis_df is not None and not analysis_df.empty:
            daily_by_window[window_name] = analysis_df.copy()

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary.sort_values(["analysis_start", "analysis_end", "window_name"], inplace=True)
        summary.reset_index(drop=True, inplace=True)
    return summary, daily_by_window


def annual_returns(full_daily: pd.DataFrame) -> pd.DataFrame:
    if full_daily.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    df = full_daily.reset_index().rename(columns={"index": "date"}).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    previous_balance = OFFICIAL_STAGE78_CAPITAL
    for year, group in df.groupby(df["date"].dt.year, sort=True):
        group = group.sort_values("date")
        start_balance = float(previous_balance)
        end_balance = float(group["balance"].iloc[-1])
        min_balance = float(group["balance"].min())
        year_pnl = end_balance - start_balance
        rows.append(
            {
                "year": int(year),
                "start_balance": start_balance,
                "end_balance": end_balance,
                "year_pnl": year_pnl,
                "year_return_pct": year_pnl / start_balance * 100.0 if start_balance else 0.0,
                "min_balance_in_year": min_balance,
            }
        )
        previous_balance = end_balance
    return pd.DataFrame(rows)


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray) -> dict[str, float]:
    if len(net_pnl) == 0:
        return {"end_balance": 0.0, "total_return_pct": 0.0, "max_dd_percent": 0.0, "sharpe_ratio": 0.0}
    equity = OFFICIAL_STAGE78_CAPITAL + np.cumsum(net_pnl.astype(float))
    previous_equity = np.concatenate([[OFFICIAL_STAGE78_CAPITAL], equity[:-1]])
    returns = np.divide(net_pnl, previous_equity, out=np.zeros_like(net_pnl, dtype=float), where=previous_equity != 0)
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(
        equity - high_water,
        high_water,
        out=np.zeros_like(equity, dtype=float),
        where=high_water != 0,
    ) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / OFFICIAL_STAGE78_CAPITAL - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe,
    }


def slippage_stress(full_daily: pd.DataFrame) -> pd.DataFrame:
    if full_daily.empty:
        return pd.DataFrame()
    frame = full_daily.reset_index().rename(columns={"index": "date"}).copy()
    net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    slippage = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    trade_count = int(pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0).sum())
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
        rows.append(
            {
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                "total_trade_count": trade_count,
                **calculate_metrics_from_net_pnl(stressed_net_pnl),
            }
        )
    return pd.DataFrame(rows)


def build_equity_curves(daily_by_window: dict[str, pd.DataFrame], summary: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if summary.empty:
        return pd.DataFrame()
    labels = {
        str(row.window_name): str(row.display_label)
        for row in summary[["window_name", "display_label"]].itertuples(index=False)
    }
    for window_name, daily in daily_by_window.items():
        if daily.empty:
            continue
        df = daily.reset_index().rename(columns={"index": "date"})[["date", "balance"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        first_balance = float(df["balance"].iloc[0] or OFFICIAL_STAGE78_CAPITAL)
        if abs(first_balance) < 1e-9:
            first_balance = OFFICIAL_STAGE78_CAPITAL
        df["normalized_nav"] = df["balance"] / first_balance
        df["window_name"] = window_name
        df["display_label"] = labels.get(window_name, window_name)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    curves = pd.concat(frames, ignore_index=True).sort_values(["window_name", "date"])
    curves.to_csv(EQUITY_CURVES_CSV_PATH, index=False, encoding="utf-8-sig")
    return curves


def write_equity_html(curves: pd.DataFrame) -> None:
    if curves.empty:
        EQUITY_CURVES_HTML_PATH.write_text("<html><body><h1>No equity curves</h1></body></html>", encoding="utf-8")
        return
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for window_name, group in curves.groupby("window_name", sort=False):
            name = str(group["display_label"].iloc[0])
            fig.add_trace(
                go.Scatter(
                    x=group["date"],
                    y=group["normalized_nav"],
                    mode="lines",
                    name=name,
                    visible=True
                    if window_name in {
                        "requested_since_2015",
                        "full_2020_2026",
                        "since_2022",
                        "since_2025",
                        "latest_2026",
                    }
                    else "legendonly",
                )
            )
        fig.update_layout(
            title="Stage194 Stage78 Multi-cycle Normalized NAV",
            xaxis_title="Date",
            yaxis_title="Normalized NAV",
            hovermode="x unified",
            template="plotly_white",
            width=1280,
            height=760,
        )
        fig.write_html(EQUITY_CURVES_HTML_PATH, include_plotlyjs="cdn")
    except Exception as exc:
        EQUITY_CURVES_HTML_PATH.write_text(
            f"<html><body><h1>Stage194 Equity Curves</h1><p>Plotly failed: {exc}</p></body></html>",
            encoding="utf-8",
        )


def coverage_total_view(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()
    view = coverage[coverage["product_vt_symbol"] == "__TOTAL__"].copy()
    view["coverage_ratio_pct"] = view["coverage_ratio"] * 100.0
    view["gate_result"] = np.where(view["coverage_ratio"] >= COVERAGE_PASS_THRESHOLD, "PASS", "FAIL")
    return view[
        [
            "window_name",
            "display_label",
            "kind",
            "analysis_start",
            "analysis_end",
            "mapped_days",
            "present_days",
            "missing_days",
            "coverage_ratio_pct",
            "gate_result",
        ]
    ].reset_index(drop=True)


def worst_product_coverage(coverage: pd.DataFrame, window_name: str, limit: int = 10) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()
    view = coverage[
        (coverage["window_name"] == window_name) & (coverage["product_vt_symbol"] != "__TOTAL__")
    ].copy()
    if view.empty:
        return pd.DataFrame()
    view["coverage_ratio_pct"] = view["coverage_ratio"] * 100.0
    return view.sort_values(["coverage_ratio", "missing_days"], ascending=[True, False])[
        [
            "product_vt_symbol",
            "mapped_days",
            "present_days",
            "missing_days",
            "coverage_ratio_pct",
            "missing_contract_examples",
        ]
    ].head(limit)


def build_report(
    *,
    analysis_end: datetime,
    latest_date: datetime,
    coverage: pd.DataFrame,
    year_coverage: pd.DataFrame,
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    stress: pd.DataFrame,
) -> str:
    coverage_view = coverage_total_view(coverage)
    year_view = coverage_total_view(year_coverage)
    summary_view = summary[
        [
            "window_name",
            "display_label",
            "kind",
            "analysis_start",
            "analysis_end",
            "coverage_ratio",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_slippage",
            "total_trade_count",
            "win_ratio_pct",
        ]
    ].copy() if not summary.empty else pd.DataFrame()
    requested_total = coverage[
        (coverage["window_name"] == "requested_since_2015") & (coverage["product_vt_symbol"] == "__TOTAL__")
    ]
    requested_coverage = _safe_float(requested_total["coverage_ratio"].iloc[0]) if not requested_total.empty else 0.0
    early_total = coverage[
        (coverage["window_name"] == "early_data_2015_2017") & (coverage["product_vt_symbol"] == "__TOTAL__")
    ]
    early_coverage = _safe_float(early_total["coverage_ratio"].iloc[0]) if not early_total.empty else 0.0
    early_pass = early_coverage >= COVERAGE_PASS_THRESHOLD
    full_rows = summary[summary["window_name"] == "full_2020_2026"] if not summary.empty else pd.DataFrame()
    latest_rows = summary[summary["window_name"] == "latest_2026"] if not summary.empty else pd.DataFrame()
    full = full_rows.iloc[0] if not full_rows.empty else None
    latest = latest_rows.iloc[0] if not latest_rows.empty else None
    full_pass = bool(
        full is not None
        and _safe_float(full["total_return_pct"]) > 0
        and _safe_float(full["sharpe_ratio"]) > 1.0
        and _safe_float(full["max_dd_percent"]) >= -40.0
    )
    latest_positive = bool(latest is not None and _safe_float(latest["total_return_pct"]) > 0)
    decision = "yellow_keep_stage78_validate_live"
    if requested_coverage >= COVERAGE_PASS_THRESHOLD and early_pass and full_pass and latest_positive:
        decision = "green_long_sample_supported"
    elif requested_coverage >= COVERAGE_PASS_THRESHOLD and full_pass and latest_positive:
        decision = "yellow_long_sample_supported_early_segment_gap"
    elif not full_pass:
        decision = "red_research_not_live_ready"

    lines = [
        "# Stage194 Stage78 2015起点多周期可行性审计",
        "",
        "## 结论先行",
        "",
        f"- 决策标签：`{decision}`。",
        f"- 2015起点覆盖率：`{requested_coverage * 100:.2f}%`，门禁阈值：`{COVERAGE_PASS_THRESHOLD * 100:.0f}%`。",
        f"- 2015-2017早期子段覆盖率：`{early_coverage * 100:.2f}%`，门禁阈值：`{COVERAGE_PASS_THRESHOLD * 100:.0f}%`。",
        "- 如果2015起点覆盖率不达标，本报告不会把2015曲线当作可信回测结果；如果早期子段不达标，则只把2015总窗口当作长样本参考，不单独确认2015-2017周期表现。",
        "- 可信可回测主样本仍以覆盖通过窗口为准；当前重点看2020以后第78正式口径，并把早期残缺品种继续列为数据风险。",
        "",
        "## 调研判断",
        "",
        "- 外部趋势跟踪研究支持用长样本、分段、交易成本和敏感性分析检验趋势策略；长样本有效性不能建立在缺失数据上。",
        "- 本轮不修改第78，不新增参数，不为了让2015窗口通过而降低覆盖门槛。",
        "",
        "## 参数",
        "",
        f"- 正式版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        f"- 本金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        f"- 基础 risk ratio：`{BASE_RISK_RATIO}`",
        f"- 请求起点：`{REQUESTED_START.date().isoformat()}`",
        f"- 回测终点：`{analysis_end.date().isoformat()}`",
        f"- 数据库最新K线日期：`{latest_date.date().isoformat()}`",
        f"- 覆盖率通过阈值：`{COVERAGE_PASS_THRESHOLD:.0%}`",
        "",
        "## 数据覆盖门禁",
        "",
        to_markdown_table(coverage_view),
        "",
        "## 年度覆盖率",
        "",
        to_markdown_table(
            year_view[
                [
                    "window_name",
                    "analysis_start",
                    "analysis_end",
                    "mapped_days",
                    "present_days",
                    "missing_days",
                    "coverage_ratio_pct",
                    "gate_result",
                ]
            ]
        ),
        "",
        "## 2015起点缺失最严重品种",
        "",
        to_markdown_table(worst_product_coverage(coverage, "requested_since_2015")),
        "",
        "## 覆盖通过窗口回测结果",
        "",
        to_markdown_table(summary_view) if not summary_view.empty else "_empty_",
        "",
        "## 年度收益拆分",
        "",
        to_markdown_table(annual) if not annual.empty else "_empty_",
        "",
        "## 全样本滑点压力",
        "",
        to_markdown_table(stress) if not stress.empty else "_empty_",
        "",
        "## 可行性判断",
        "",
    ]

    if full is not None:
        lines.extend(
            [
                (
                    f"- 2020-2026可信主样本：期末权益 `{_fmt(full['end_balance'], 0)}`，"
                    f"总收益 `{_fmt(full['total_return_pct'])}%`，"
                    f"最大回撤 `{_fmt(full['max_dd_percent'])}%`，"
                    f"Sharpe `{_fmt(full['sharpe_ratio'])}`，"
                    f"总滑点 `{_fmt(full['total_slippage'], 0)}`，"
                    f"交易 `{_fmt(full['total_trade_count'], 0)}`。"
                )
            ]
        )
    if latest is not None:
        lines.append(
            (
                f"- 2026最新窗口：总收益 `{_fmt(latest['total_return_pct'])}%`，"
                f"最大回撤 `{_fmt(latest['max_dd_percent'])}%`，"
                f"Sharpe `{_fmt(latest['sharpe_ratio'])}`。"
            )
        )

    lines.extend(
        [
            "- 2015起点是否可直接确认：2015总窗口通过时可作为长样本参考；但2015-2017早期子段若低于门槛，不能单独确认早期周期表现。",
            "- 策略是否可继续实盘前验证：如果2020以后主样本、分周期、起始年份和滑点压力仍稳定，则有价值继续进入影子盘和T+1执行审计。",
            "",
            "## 过拟合反思",
            "",
            "- 运行前：否，本轮是固定第78做验证，不调参；风险在于如果强行使用低覆盖2015数据，会形成数据缺失型假结论。",
            "- 运行后：以覆盖通过窗口为准的结果不过拟合；但若把长窗口通过直接等同于2015-2017子段完全可信，则属于数据覆盖外推。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前：有价值，因为它回答第78是否能经受更长样本审计，以及当前数据是否支持2015回测。",
            "- 运行后：有价值；下一步应追补早期残缺品种并推进T+1执行审计，而不是在缺数据窗口上调参。",
            "",
            "## 输出文件",
            "",
            f"- 覆盖率：`{COVERAGE_CSV_PATH}`",
            f"- 年度覆盖率：`{YEAR_COVERAGE_CSV_PATH}`",
            f"- 汇总：`{SUMMARY_CSV_PATH}`",
            f"- 年度收益：`{ANNUAL_RETURNS_CSV_PATH}`",
            f"- 滑点压力：`{SLIPPAGE_STRESS_CSV_PATH}`",
            f"- 资金曲线CSV：`{EQUITY_CURVES_CSV_PATH}`",
            f"- 资金曲线HTML：`{EQUITY_CURVES_HTML_PATH}`",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_date = latest_database_date()
    analysis_end = min(END_DT, latest_date)
    strategy_overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(strategy_overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    windows = build_windows(analysis_end)
    year_windows = build_year_windows(analysis_end)
    all_windows = windows + year_windows
    mapping_df = load_mapping_df()
    window_start = min(window["analysis_start"] for window in all_windows)
    window_end = max(window["analysis_end"] for window in all_windows)
    mapped_contracts = set(
        mapping_df[
            mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
            & (mapping_df["main_contract_vt"].fillna("") != "")
        ]["main_contract_vt"].astype(str)
    )
    contract_date_sets = load_contract_date_sets(mapped_contracts, window_start, window_end)
    coverage = build_coverage_table(mapping_df, product_symbols, windows, contract_date_sets)
    year_coverage = build_coverage_table(mapping_df, product_symbols, year_windows, contract_date_sets)
    summary, daily_by_window = run_valid_backtests(windows, coverage, strategy_overrides)

    full_daily = daily_by_window.get("full_2020_2026", pd.DataFrame())
    annual = annual_returns(full_daily)
    stress = slippage_stress(full_daily)
    curves = build_equity_curves(daily_by_window, summary)
    write_equity_html(curves)

    coverage.to_csv(COVERAGE_CSV_PATH, index=False, encoding="utf-8-sig")
    year_coverage.to_csv(YEAR_COVERAGE_CSV_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_RETURNS_CSV_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(SLIPPAGE_STRESS_CSV_PATH, index=False, encoding="utf-8-sig")

    report = build_report(
        analysis_end=analysis_end,
        latest_date=latest_date,
        coverage=coverage,
        year_coverage=year_coverage,
        summary=summary,
        annual=annual,
        stress=stress,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "requested_start": REQUESTED_START.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "latest_database_date": latest_date.date().isoformat(),
        "coverage_pass_threshold": COVERAGE_PASS_THRESHOLD,
        "paths": {
            "coverage": str(COVERAGE_CSV_PATH),
            "year_coverage": str(YEAR_COVERAGE_CSV_PATH),
            "summary": str(SUMMARY_CSV_PATH),
            "annual_returns": str(ANNUAL_RETURNS_CSV_PATH),
            "slippage_stress": str(SLIPPAGE_STRESS_CSV_PATH),
            "equity_curves_csv": str(EQUITY_CURVES_CSV_PATH),
            "equity_curves_html": str(EQUITY_CURVES_HTML_PATH),
            "report": str(REPORT_PATH),
        },
        "coverage_total": coverage_total_view(coverage).to_dict(orient="records"),
        "year_coverage_total": coverage_total_view(year_coverage).to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
        "annual_returns": annual.to_dict(orient="records"),
        "slippage_stress": stress.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(coverage_total_view(coverage).to_string(index=False))
    if not summary.empty:
        print(summary[["window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "win_ratio_pct"]].to_string(index=False))
    print(f"[stage194] report: {REPORT_PATH}")
    print(f"[stage194] equity html: {EQUITY_CURVES_HTML_PATH}")


if __name__ == "__main__":
    main()
