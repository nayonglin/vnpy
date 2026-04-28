from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from audit_stock_range_reversion_hedge_data import STOCK_EQUITY_PATH, TRADING_DAYS, pct, safe_corr, to_float


BASE_DIR: Path = Path(__file__).resolve().parent
PROJECT_DIR: Path = BASE_DIR.parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
PORTFOLIO_OUTPUT_DIR: Path = PROJECT_DIR / "portfolio_backtesting" / "backtest_outputs"
STAGE78_DAILY_PATH: Path = PORTFOLIO_OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_daily_equity.csv"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_long_only_satellite_boundary_2020_2026"
).resolve()
PREFIX: str = "stock_range_reversion_long_only_satellite_boundary_v1"

STAGE78_INITIAL_CAPITAL: float = 200_000.0
STOCK_COST_BPS_LIST: tuple[float, ...] = (20.0, 50.0)
SATELLITE_WEIGHTS: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15, 0.20)


def safe_mean(values: pd.Series) -> float:
    clean = values.dropna()
    return to_float(clean.mean()) if len(clean) else 0.0


def safe_std(values: pd.Series) -> float:
    clean = values.dropna()
    return to_float(clean.std(ddof=1)) if len(clean) > 1 else 0.0


def equity_and_drawdown(returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    equity_values: list[float] = []
    drawdown_values: list[float] = []
    equity = 1.0
    peak = 1.0
    for value in returns.fillna(0.0):
        equity *= 1.0 + to_float(value)
        peak = max(peak, equity)
        equity_values.append(equity)
        drawdown_values.append(equity / peak - 1.0 if peak else 0.0)
    return pd.Series(equity_values, index=returns.index), pd.Series(drawdown_values, index=returns.index)


def max_drawdown_window(curve: pd.DataFrame, equity_col: str) -> dict[str, Any]:
    if curve.empty:
        return {
            "peak_date": "",
            "trough_date": "",
            "max_drawdown": 0.0,
            "drawdown_days": 0,
        }
    peak_index = 0
    running_peak_index = 0
    running_peak = to_float(curve[equity_col].iloc[0])
    trough_index = 0
    max_dd = 0.0
    for index, value in enumerate(curve[equity_col]):
        equity = to_float(value)
        if equity > running_peak:
            running_peak = equity
            running_peak_index = index
        dd = equity / running_peak - 1.0 if running_peak else 0.0
        if dd < max_dd:
            max_dd = dd
            peak_index = running_peak_index
            trough_index = index
    return {
        "peak_date": str(curve["date"].iloc[peak_index]),
        "trough_date": str(curve["date"].iloc[trough_index]),
        "max_drawdown": max_dd,
        "drawdown_days": trough_index - peak_index,
    }


def load_stage78_returns() -> pd.DataFrame:
    if not STAGE78_DAILY_PATH.exists():
        raise FileNotFoundError(f"Stage78 daily equity not found: {STAGE78_DAILY_PATH}")
    frame = pd.read_csv(STAGE78_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.sort_values("date").reset_index(drop=True)
    previous_balance = frame["balance"].shift(1)
    previous_balance.iloc[0] = STAGE78_INITIAL_CAPITAL
    frame["stage78_daily_ret"] = frame["balance"] / previous_balance - 1.0
    frame["stage78_equity_norm"] = frame["balance"] / STAGE78_INITIAL_CAPITAL
    return frame[["date", "stage78_daily_ret", "stage78_equity_norm", "balance", "drawdown", "ddpercent"]]


def load_stock_returns(cost_bps: float) -> pd.DataFrame:
    frame = pd.read_csv(STOCK_EQUITY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[frame["roundtrip_cost_bps"] == cost_bps].copy()
    if frame.empty:
        raise ValueError(f"No stock curve for roundtrip_cost_bps={cost_bps}")
    return frame[
        [
            "date",
            "strategy_daily_ret",
            "strategy_equity",
            "benchmark_daily_ret",
            "return_gross_exposure",
            "one_way_turnover",
        ]
    ].rename(columns={"strategy_daily_ret": "stock_daily_ret", "strategy_equity": "stock_equity_norm"})


def build_base_frame(stage78: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    work = stage78.merge(stock, on="date", how="left")
    work["stock_daily_ret"] = work["stock_daily_ret"].fillna(0.0)
    work["benchmark_daily_ret"] = work["benchmark_daily_ret"].fillna(0.0)
    work["return_gross_exposure"] = work["return_gross_exposure"].fillna(0.0)
    work["one_way_turnover"] = work["one_way_turnover"].fillna(0.0)
    return work.sort_values("date").reset_index(drop=True)


def summarize_curve(curve: pd.DataFrame, cost_bps: float, weight: float) -> dict[str, Any]:
    returns = curve["portfolio_daily_ret"].fillna(0.0)
    days = len(curve)
    daily_mean = safe_mean(returns)
    daily_std = safe_std(returns)
    total_return = to_float(curve["portfolio_equity"].iloc[-1] - 1.0) if days else 0.0
    dd_window = max_drawdown_window(curve, "portfolio_equity")
    stage78_return = to_float((1.0 + curve["stage78_daily_ret"]).prod() - 1.0) if days else 0.0
    stock_component_simple = to_float((curve["stock_daily_ret"] * weight).sum()) if days else 0.0
    return {
        "roundtrip_cost_bps": cost_bps,
        "satellite_weight": weight,
        "days": days,
        "start_date": str(curve["date"].min()) if days else "",
        "end_date": str(curve["date"].max()) if days else "",
        "final_equity": to_float(curve["portfolio_equity"].iloc[-1]) if days else 1.0,
        "total_return": total_return,
        "annualized_return": (1.0 + total_return) ** (TRADING_DAYS / days) - 1.0
        if days and total_return > -1.0
        else 0.0,
        "max_drawdown": to_float(curve["portfolio_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "daily_std": daily_std,
        "corr_to_stage78": safe_corr(curve["portfolio_daily_ret"], curve["stage78_daily_ret"]),
        "stock_corr_to_stage78": safe_corr(curve["stock_daily_ret"], curve["stage78_daily_ret"]),
        "stock_corr_to_benchmark": safe_corr(curve["stock_daily_ret"], curve["benchmark_daily_ret"]),
        "avg_stock_gross_exposure": safe_mean(curve["return_gross_exposure"]) * weight,
        "max_stock_gross_exposure": to_float(curve["return_gross_exposure"].max()) * weight if days else 0.0,
        "annualized_stock_one_way_turnover": safe_mean(curve["one_way_turnover"]) * weight * TRADING_DAYS,
        "stage78_total_return_same_window": stage78_return,
        "stock_component_simple_sum": stock_component_simple,
        "peak_date": dd_window["peak_date"],
        "trough_date": dd_window["trough_date"],
        "drawdown_days": dd_window["drawdown_days"],
    }


def build_satellite_curves(stage78: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    curve_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    drawdown_rows: list[dict[str, Any]] = []

    for cost_bps in STOCK_COST_BPS_LIST:
        stock = load_stock_returns(cost_bps)
        base = build_base_frame(stage78, stock)
        for weight in SATELLITE_WEIGHTS:
            curve = base.copy()
            curve["roundtrip_cost_bps"] = cost_bps
            curve["satellite_weight"] = weight
            curve["portfolio_daily_ret"] = (1.0 - weight) * curve["stage78_daily_ret"] + weight * curve["stock_daily_ret"]
            equity, drawdown = equity_and_drawdown(curve["portfolio_daily_ret"])
            curve["portfolio_equity"] = equity
            curve["portfolio_drawdown"] = drawdown
            curve["stage78_alloc_ret"] = (1.0 - weight) * curve["stage78_daily_ret"]
            curve["stock_alloc_ret"] = weight * curve["stock_daily_ret"]
            curve_parts.append(curve)
            summary_rows.append(summarize_curve(curve, cost_bps, weight))

            curve["year"] = pd.to_datetime(curve["date"]).dt.year
            for year, year_group in curve.groupby("year"):
                stage78_year = to_float((1.0 + year_group["stage78_daily_ret"]).prod() - 1.0)
                stock_year = to_float((1.0 + year_group["stock_daily_ret"]).prod() - 1.0)
                portfolio_year = to_float((1.0 + year_group["portfolio_daily_ret"]).prod() - 1.0)
                yearly_rows.append(
                    {
                        "roundtrip_cost_bps": cost_bps,
                        "satellite_weight": weight,
                        "year": int(year),
                        "days": int(len(year_group)),
                        "stage78_year_return": stage78_year,
                        "stock_year_return": stock_year,
                        "portfolio_year_return": portfolio_year,
                        "delta_vs_stage78_year_return": portfolio_year - stage78_year,
                        "stock_alloc_simple_sum": to_float(year_group["stock_alloc_ret"].sum()),
                    }
                )

            dd_window = max_drawdown_window(curve, "portfolio_equity")
            peak_date = pd.to_datetime(dd_window["peak_date"]).date() if dd_window["peak_date"] else None
            trough_date = pd.to_datetime(dd_window["trough_date"]).date() if dd_window["trough_date"] else None
            if peak_date is not None and trough_date is not None:
                dd_slice = curve[(curve["date"] >= peak_date) & (curve["date"] <= trough_date)]
                drawdown_rows.append(
                    {
                        "roundtrip_cost_bps": cost_bps,
                        "satellite_weight": weight,
                        "peak_date": str(peak_date),
                        "trough_date": str(trough_date),
                        "drawdown_days": int(len(dd_slice)),
                        "portfolio_drawdown": to_float(dd_window["max_drawdown"]),
                        "stage78_alloc_return_sum": to_float(dd_slice["stage78_alloc_ret"].sum()),
                        "stock_alloc_return_sum": to_float(dd_slice["stock_alloc_ret"].sum()),
                        "stock_raw_return_compound": to_float((1.0 + dd_slice["stock_daily_ret"]).prod() - 1.0),
                        "stage78_raw_return_compound": to_float((1.0 + dd_slice["stage78_daily_ret"]).prod() - 1.0),
                    }
                )

    curves = pd.concat(curve_parts, ignore_index=True, sort=False)
    summary = pd.DataFrame(summary_rows).sort_values(["roundtrip_cost_bps", "satellite_weight"])
    yearly = pd.DataFrame(yearly_rows).sort_values(["roundtrip_cost_bps", "satellite_weight", "year"])
    drawdowns = pd.DataFrame(drawdown_rows).sort_values(["roundtrip_cost_bps", "satellite_weight"])
    return summary, curves, yearly, drawdowns


def build_delta_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cost_bps, group in summary.groupby("roundtrip_cost_bps"):
        base = group[group["satellite_weight"] == 0.0].iloc[0]
        for row in group.itertuples(index=False):
            rows.append(
                {
                    "roundtrip_cost_bps": to_float(cost_bps),
                    "satellite_weight": to_float(row.satellite_weight),
                    "final_equity": to_float(row.final_equity),
                    "total_return": to_float(row.total_return),
                    "max_drawdown": to_float(row.max_drawdown),
                    "sharpe": to_float(row.sharpe),
                    "delta_final_equity": to_float(row.final_equity) - to_float(base["final_equity"]),
                    "delta_total_return": to_float(row.total_return) - to_float(base["total_return"]),
                    "delta_max_drawdown": to_float(row.max_drawdown) - to_float(base["max_drawdown"]),
                    "delta_sharpe": to_float(row.sharpe) - to_float(base["sharpe"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "satellite_weight"])


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(summary: pd.DataFrame, delta: pd.DataFrame, yearly: pd.DataFrame, drawdowns: pd.DataFrame) -> Path:
    summary_20 = summary[summary["roundtrip_cost_bps"] == 20.0]
    delta_20 = delta[delta["roundtrip_cost_bps"] == 20.0]
    yearly_10 = yearly[(yearly["roundtrip_cost_bps"] == 20.0) & (yearly["satellite_weight"] == 0.10)]
    dd_20 = drawdowns[drawdowns["roundtrip_cost_bps"] == 20.0]
    corr_value = to_float(summary_20.iloc[0]["stock_corr_to_stage78"]) if not summary_20.empty else 0.0
    stock_benchmark_corr = to_float(summary_20.iloc[0]["stock_corr_to_benchmark"]) if not summary_20.empty else 0.0
    weight_10 = summary_20[summary_20["satellite_weight"] == 0.10]
    weight_10_final = to_float(weight_10.iloc[0]["final_equity"]) if not weight_10.empty else 0.0
    weight_10_dd = to_float(weight_10.iloc[0]["max_drawdown"]) if not weight_10.empty else 0.0
    weight_0 = summary_20[summary_20["satellite_weight"] == 0.0]
    base_final = to_float(weight_0.iloc[0]["final_equity"]) if not weight_0.empty else 0.0
    base_dd = to_float(weight_0.iloc[0]["max_drawdown"]) if not weight_0.empty else 0.0
    delta_10 = delta_20[delta_20["satellite_weight"] == 0.10]
    delta_10_final = to_float(delta_10.iloc[0]["delta_final_equity"]) if not delta_10.empty else 0.0
    delta_10_dd = to_float(delta_10.iloc[0]["delta_max_drawdown"]) if not delta_10.empty else 0.0
    delta_10_sharpe = to_float(delta_10.iloc[0]["delta_sharpe"]) if not delta_10.empty else 0.0

    report = f"""# 股票震荡 long-only 小仓位卫星边界 v1

- 记录时间：{datetime.now().strftime("%Y-%m-%d %H:%M CST")}
- 当前研究线：股票震荡 `market_down`，与第78趋势策略、期货震荡策略隔离。
- 本阶段性质：固定仓位边界归因，不是正式A/B版本。
- 第78输入：`{STAGE78_DAILY_PATH}`
- 股票震荡输入：`{STOCK_EQUITY_PATH}`

## 方法

- 只读取第78正式冻结日度权益，不重跑、不修改第78。
- 股票震荡使用第218阶段合并持仓long-only路径。
- 组合日收益按固定资金权重每日再平衡：`(1-w) * 第78日收益 + w * 股票震荡日收益`。
- 权重固定为`0%/5%/10%/15%/20%`，不按结果择优。

## 核心观察

- 股票震荡与第78日收益相关约 `{corr_value:.3f}`，与中证1000 benchmark 相关约 `{stock_benchmark_corr:.3f}`。
- 20bp股票成本、10%卫星下，组合期末权益`{weight_10_final:.4f}`，第78同窗口`{base_final:.4f}`；组合最大回撤`{pct(weight_10_dd)}`，第78同窗口`{pct(base_dd)}`。
- 10%卫星相对第78同窗口：期末权益变化`{delta_10_final:.4f}`，最大回撤改善`{pct(delta_10_dd)}`，Sharpe变化`{delta_10_sharpe:.4f}`。
- 固定小仓位卫星不是为了抬高绝对收益上限，而是检查是否用可承受的beta暴露换取股票震荡alpha。

## 20bp股票成本摘要

{markdown_table(summary_20, ["satellite_weight", "final_equity", "total_return", "max_drawdown", "sharpe", "stock_corr_to_stage78", "avg_stock_gross_exposure", "annualized_stock_one_way_turnover"])}

## 相对第78同窗口变化

{markdown_table(delta_20, ["satellite_weight", "delta_final_equity", "delta_total_return", "delta_max_drawdown", "delta_sharpe"])}

## 10%卫星年度贡献

{markdown_table(yearly_10, ["year", "stage78_year_return", "stock_year_return", "portfolio_year_return", "delta_vs_stage78_year_return", "stock_alloc_simple_sum"])}

## 最大回撤窗口贡献

{markdown_table(dd_20, ["satellite_weight", "peak_date", "trough_date", "portfolio_drawdown", "stage78_alloc_return_sum", "stock_alloc_return_sum", "stock_raw_return_compound", "stage78_raw_return_compound"])}

## 运行前过拟合反思

- 判断：否。
- 原因：只测试固定小仓位比例，不扫描最优权重，也不改股票信号和第78配置。

## 运行后过拟合反思

- 判断：否。
- 原因：输出保留不同权重的线性边界和年度/回撤贡献，没有选择某个权重作为正式参数。

## 运行前继续价值反思

- 判断：是。
- 原因：ETF/IM市场中性化都遇到现实约束，股票震荡更自然的候选形态是小仓位long-only卫星。

## 运行后继续价值反思

- 判断：有，但不适合作为占用第78资金的正式卫星。
- 原因：股票震荡与第78相关性很低，能线性降低组合最大回撤并略微抬高Sharpe；但第78本身收益厚度远高于当前股票震荡路径，固定资金替换会明显牺牲期末权益。下一步若继续，应研究股票震荡作为独立小资金/闲置资金策略的状态过滤，而不是进入第78 A/B。

## 决策

- 不接入第78。
- 不进入正式股票策略。
- 不做第78 A/B/C。
- 不在本阶段选择正式卫星权重。

## 输出文件

- `{OUTPUT_DIR / f"{PREFIX}_summary.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_delta_vs_stage78.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_daily_curves.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_yearly.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_metadata.json"}`
"""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage78 = load_stage78_returns()
    summary, curves, yearly, drawdowns = build_satellite_curves(stage78)
    delta = build_delta_summary(summary)

    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(OUTPUT_DIR / f"{PREFIX}_delta_vs_stage78.csv", index=False, encoding="utf-8-sig")
    curves.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_curves.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly.csv", index=False, encoding="utf-8-sig")
    drawdowns.to_csv(OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stage78_daily_path": str(STAGE78_DAILY_PATH),
        "stock_equity_path": str(STOCK_EQUITY_PATH),
        "stage78_initial_capital": STAGE78_INITIAL_CAPITAL,
        "stock_cost_bps_list": STOCK_COST_BPS_LIST,
        "satellite_weights": SATELLITE_WEIGHTS,
        "method": "daily_rebalanced_fixed_weight_mix",
    }
    (OUTPUT_DIR / f"{PREFIX}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = write_report(summary, delta, yearly, drawdowns)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(summary.to_string(index=False))
    print(delta.to_string(index=False))


if __name__ == "__main__":
    main()
