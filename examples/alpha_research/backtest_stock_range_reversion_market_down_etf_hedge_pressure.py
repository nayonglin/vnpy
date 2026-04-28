from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from audit_stock_range_reversion_hedge_data import STOCK_EQUITY_PATH, TRADING_DAYS, pct, safe_beta, safe_corr, to_float


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
ETF_DATA_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_csi1000_etf_data_2018_2026"
ETF_DAILY_PATH: Path = ETF_DATA_DIR / "stock_range_reversion_csi1000_etf_data_v1_selected_daily.csv"
ETF_SUMMARY_PATH: Path = ETF_DATA_DIR / "stock_range_reversion_csi1000_etf_data_v1_etf_summary.csv"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_etf_hedge_pressure_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_etf_hedge_pressure_v1"

ETF_CODES: tuple[str, ...] = ("512100.SH", "159845.SZ", "560010.SH", "159629.SZ", "159633.SZ")
CAPITAL_SCENARIOS_CNY: tuple[float, ...] = (200_000.0, 500_000.0, 1_000_000.0, 5_000_000.0)
AMOUNT_RAW_TO_CNY: float = 1000.0


@dataclass(frozen=True)
class HedgeScenario:
    name: str
    description: str
    hedge_ratio: float
    etf_one_way_cost_bps: float
    borrow_annual_rate: float
    tradability: str


SCENARIOS: tuple[HedgeScenario, ...] = (
    HedgeScenario(
        name="baseline_same_window",
        description="同ETF重合窗口股票震荡long-only baseline",
        hedge_ratio=0.0,
        etf_one_way_cost_bps=0.0,
        borrow_annual_rate=0.0,
        tradability="tradable_long_only_baseline",
    ),
    HedgeScenario(
        name="etf_short_50_cost5_noborrow",
        description="ETF 50%同暴露空头归因，单边5bp交易成本，不计融券成本",
        hedge_ratio=0.5,
        etf_one_way_cost_bps=5.0,
        borrow_annual_rate=0.0,
        tradability="attribution_requires_etf_short_or_lending",
    ),
    HedgeScenario(
        name="etf_short_100_cost5_noborrow",
        description="ETF 100%同暴露空头归因，单边5bp交易成本，不计融券成本",
        hedge_ratio=1.0,
        etf_one_way_cost_bps=5.0,
        borrow_annual_rate=0.0,
        tradability="attribution_requires_etf_short_or_lending",
    ),
    HedgeScenario(
        name="etf_short_100_cost10_borrow3",
        description="ETF 100%同暴露空头压力，单边10bp交易成本，年化3%融券/借券成本",
        hedge_ratio=1.0,
        etf_one_way_cost_bps=10.0,
        borrow_annual_rate=0.03,
        tradability="stress_requires_etf_short_or_lending",
    ),
)


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


def load_stock_equity() -> pd.DataFrame:
    frame = pd.read_csv(STOCK_EQUITY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame.sort_values(["roundtrip_cost_bps", "date"]).reset_index(drop=True)


def load_etf_daily() -> pd.DataFrame:
    if not ETF_DAILY_PATH.exists():
        raise FileNotFoundError(f"ETF daily data not found: {ETF_DAILY_PATH}")
    frame = pd.read_csv(ETF_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ("daily_ret", "close_pct_ret", "amount", "vol", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[frame["ts_code"].isin(ETF_CODES)].sort_values(["ts_code", "date"]).reset_index(drop=True)


def load_etf_names() -> dict[str, str]:
    if not ETF_SUMMARY_PATH.exists():
        return {code: code for code in ETF_CODES}
    frame = pd.read_csv(ETF_SUMMARY_PATH, encoding="utf-8-sig")
    return dict(zip(frame["ts_code"].astype(str), frame["name"].astype(str)))


def apply_scenario(stock: pd.DataFrame, etf: pd.DataFrame, scenario: HedgeScenario, etf_name: str) -> pd.DataFrame:
    work = stock.merge(etf[["date", "ts_code", "daily_ret", "amount", "vol", "close"]], on="date", how="inner")
    work = work.sort_values("date").reset_index(drop=True)
    work["etf_code"] = work["ts_code"]
    work["etf_name"] = etf_name
    work["hedge_notional"] = scenario.hedge_ratio * work["return_gross_exposure"].clip(lower=0.0)
    previous_notional = work["hedge_notional"].shift(1).fillna(0.0)
    work["etf_turnover_notional"] = (work["hedge_notional"] - previous_notional).abs()
    work["etf_trade_cost_ret"] = work["etf_turnover_notional"] * scenario.etf_one_way_cost_bps / 10_000.0
    work["borrow_cost_ret"] = work["hedge_notional"] * scenario.borrow_annual_rate / TRADING_DAYS
    work["hedge_daily_ret"] = -work["hedge_notional"] * work["daily_ret"]
    work["scenario_daily_ret"] = (
        work["strategy_daily_ret"] + work["hedge_daily_ret"] - work["etf_trade_cost_ret"] - work["borrow_cost_ret"]
    )
    equity, drawdown = equity_and_drawdown(work["scenario_daily_ret"])
    work["scenario_equity"] = equity
    work["scenario_drawdown"] = drawdown
    work["scenario"] = scenario.name
    work["scenario_description"] = scenario.description
    work["hedge_ratio"] = scenario.hedge_ratio
    work["etf_one_way_cost_bps"] = scenario.etf_one_way_cost_bps
    work["borrow_annual_rate"] = scenario.borrow_annual_rate
    work["tradability"] = scenario.tradability
    return work


def summarize_curve(curve: pd.DataFrame) -> dict[str, Any]:
    days = len(curve)
    returns = curve["scenario_daily_ret"].fillna(0.0)
    daily_mean = safe_mean(returns)
    daily_std = safe_std(returns)
    total_return = to_float(curve["scenario_equity"].iloc[-1] - 1.0) if days else 0.0
    active_returns = curve.loc[curve["return_gross_exposure"] > 0, "scenario_daily_ret"]
    return {
        "roundtrip_cost_bps": to_float(curve["roundtrip_cost_bps"].iloc[0]) if days else 0.0,
        "etf_code": str(curve["etf_code"].iloc[0]) if days else "",
        "etf_name": str(curve["etf_name"].iloc[0]) if days else "",
        "scenario": str(curve["scenario"].iloc[0]) if days else "",
        "tradability": str(curve["tradability"].iloc[0]) if days else "",
        "description": str(curve["scenario_description"].iloc[0]) if days else "",
        "hedge_ratio": to_float(curve["hedge_ratio"].iloc[0]) if days else 0.0,
        "etf_one_way_cost_bps": to_float(curve["etf_one_way_cost_bps"].iloc[0]) if days else 0.0,
        "borrow_annual_rate": to_float(curve["borrow_annual_rate"].iloc[0]) if days else 0.0,
        "days": days,
        "start_date": str(curve["date"].min()) if days else "",
        "end_date": str(curve["date"].max()) if days else "",
        "final_equity": to_float(curve["scenario_equity"].iloc[-1]) if days else 1.0,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (TRADING_DAYS / days) - 1
        if days and total_return > -1
        else 0.0,
        "max_drawdown": to_float(curve["scenario_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "active_day_win_rate": to_float((active_returns > 0).mean()) if len(active_returns) else 0.0,
        "avg_long_exposure": safe_mean(curve["return_gross_exposure"]),
        "max_long_exposure": to_float(curve["return_gross_exposure"].max()) if days else 0.0,
        "avg_hedge_notional": safe_mean(curve["hedge_notional"]),
        "max_hedge_notional": to_float(curve["hedge_notional"].max()) if days else 0.0,
        "annualized_etf_turnover": safe_mean(curve["etf_turnover_notional"]) * TRADING_DAYS,
        "total_etf_trade_cost_ret": to_float(curve["etf_trade_cost_ret"].sum()),
        "total_borrow_cost_ret": to_float(curve["borrow_cost_ret"].sum()),
        "corr_to_benchmark": safe_corr(curve["scenario_daily_ret"], curve["benchmark_daily_ret"]),
        "beta_to_benchmark": safe_beta(curve["scenario_daily_ret"], curve["benchmark_daily_ret"]),
        "etf_corr_to_benchmark": safe_corr(curve["daily_ret"], curve["benchmark_daily_ret"]),
        "etf_beta_to_benchmark": safe_beta(curve["daily_ret"], curve["benchmark_daily_ret"]),
        "median_etf_amount_raw": to_float(curve["amount"].median()),
        "p10_etf_amount_raw": to_float(curve["amount"].quantile(0.10)),
    }


def build_curves(stock: pd.DataFrame, etf_daily: pd.DataFrame, etf_names: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for cost_bps, cost_group in stock.groupby("roundtrip_cost_bps"):
        cost_group = cost_group.sort_values("date").reset_index(drop=True)
        for etf_code in ETF_CODES:
            etf = etf_daily[etf_daily["ts_code"] == etf_code].sort_values("date").reset_index(drop=True)
            if etf.empty:
                continue
            etf_name = etf_names.get(etf_code, etf_code)
            for scenario in SCENARIOS:
                curve = apply_scenario(cost_group, etf, scenario, etf_name)
                if curve.empty:
                    continue
                curves.append(curve)
                rows.append(summarize_curve(curve))
    all_curves = pd.concat(curves, ignore_index=True, sort=False)
    summary = pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "etf_code", "hedge_ratio", "scenario"])
    return summary, all_curves


def build_delta_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    keys = ["roundtrip_cost_bps", "etf_code"]
    for _, group in summary.groupby(keys):
        baseline = group[group["scenario"] == "baseline_same_window"]
        if baseline.empty:
            continue
        base = baseline.iloc[0]
        for row in group.itertuples(index=False):
            rows.append(
                {
                    "roundtrip_cost_bps": to_float(row.roundtrip_cost_bps),
                    "etf_code": str(row.etf_code),
                    "etf_name": str(row.etf_name),
                    "scenario": str(row.scenario),
                    "days": int(row.days),
                    "start_date": str(row.start_date),
                    "end_date": str(row.end_date),
                    "final_equity": to_float(row.final_equity),
                    "max_drawdown": to_float(row.max_drawdown),
                    "sharpe": to_float(row.sharpe),
                    "beta_to_benchmark": to_float(row.beta_to_benchmark),
                    "delta_final_equity": to_float(row.final_equity) - to_float(base["final_equity"]),
                    "delta_max_drawdown": to_float(row.max_drawdown) - to_float(base["max_drawdown"]),
                    "delta_sharpe": to_float(row.sharpe) - to_float(base["sharpe"]),
                    "delta_beta": to_float(row.beta_to_benchmark) - to_float(base["beta_to_benchmark"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "etf_code", "scenario"]).reset_index(drop=True)


def build_liquidity_pressure(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scenario_cols = [
        "roundtrip_cost_bps",
        "etf_code",
        "etf_name",
        "scenario",
        "hedge_ratio",
        "etf_one_way_cost_bps",
        "borrow_annual_rate",
    ]
    for keys, group in curves.groupby(scenario_cols):
        (
            roundtrip_cost_bps,
            etf_code,
            etf_name,
            scenario,
            hedge_ratio,
            etf_one_way_cost_bps,
            borrow_annual_rate,
        ) = keys
        if to_float(hedge_ratio) <= 0:
            continue
        active = group[group["etf_turnover_notional"] > 0].copy()
        if active.empty:
            continue
        amount_cny = active["amount"] * AMOUNT_RAW_TO_CNY
        for capital in CAPITAL_SCENARIOS_CNY:
            trade_cny = active["etf_turnover_notional"] * capital
            participation = trade_cny / amount_cny.replace(0, pd.NA)
            rows.append(
                {
                    "roundtrip_cost_bps": to_float(roundtrip_cost_bps),
                    "etf_code": str(etf_code),
                    "etf_name": str(etf_name),
                    "scenario": str(scenario),
                    "hedge_ratio": to_float(hedge_ratio),
                    "etf_one_way_cost_bps": to_float(etf_one_way_cost_bps),
                    "borrow_annual_rate": to_float(borrow_annual_rate),
                    "capital_cny": capital,
                    "trade_days": int(len(active)),
                    "median_trade_notional_cny": to_float(trade_cny.median()),
                    "p95_trade_notional_cny": to_float(trade_cny.quantile(0.95)),
                    "median_amount_cny_est": to_float(amount_cny.median()),
                    "p10_amount_cny_est": to_float(amount_cny.quantile(0.10)),
                    "median_participation": to_float(participation.median()),
                    "p95_participation": to_float(participation.quantile(0.95)),
                    "max_participation": to_float(participation.max()),
                    "pct_days_participation_gt_1pct": to_float((participation > 0.01).mean()),
                    "pct_days_participation_gt_5pct": to_float((participation > 0.05).mean()),
                    "pct_days_participation_gt_10pct": to_float((participation > 0.10).mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["roundtrip_cost_bps", "etf_code", "scenario", "capital_cny"]
    ).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 36) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(summary: pd.DataFrame, delta: pd.DataFrame, liquidity: pd.DataFrame) -> Path:
    full_512 = summary[
        (summary["roundtrip_cost_bps"] == 20.0)
        & (summary["etf_code"] == "512100.SH")
        & (summary["scenario"].isin(["baseline_same_window", "etf_short_50_cost5_noborrow", "etf_short_100_cost5_noborrow", "etf_short_100_cost10_borrow3"]))
    ].copy()
    post_liquid = summary[
        (summary["roundtrip_cost_bps"] == 20.0)
        & (summary["etf_code"].isin(["159845.SZ", "560010.SH", "159629.SZ"]))
        & (summary["scenario"].isin(["baseline_same_window", "etf_short_100_cost5_noborrow"]))
    ].copy()
    liq_focus = liquidity[
        (liquidity["roundtrip_cost_bps"] == 20.0)
        & (liquidity["scenario"] == "etf_short_100_cost5_noborrow")
        & (liquidity["capital_cny"].isin([200_000.0, 1_000_000.0, 5_000_000.0]))
        & (liquidity["etf_code"].isin(["512100.SH", "159845.SZ", "560010.SH", "159629.SZ"]))
    ].copy()

    baseline = full_512[full_512["scenario"] == "baseline_same_window"]
    hedge100 = full_512[full_512["scenario"] == "etf_short_100_cost5_noborrow"]
    baseline_final = to_float(baseline.iloc[0]["final_equity"]) if not baseline.empty else 0.0
    baseline_dd = to_float(baseline.iloc[0]["max_drawdown"]) if not baseline.empty else 0.0
    hedge_final = to_float(hedge100.iloc[0]["final_equity"]) if not hedge100.empty else 0.0
    hedge_dd = to_float(hedge100.iloc[0]["max_drawdown"]) if not hedge100.empty else 0.0

    report = f"""# 股票震荡 ETF 对冲压力测试 v1

- 记录时间：{datetime.now().strftime("%Y-%m-%d %H:%M CST")}
- 当前研究线：股票震荡 `market_down`，与第78趋势策略、期货震荡策略隔离。
- 本阶段性质：ETF空头腿归因/压力测试，不是正式策略版本。
- ETF日线输入：`{ETF_DAILY_PATH}`
- 股票路径输入：`{STOCK_EQUITY_PATH}`

## 关键边界

- A股普通账户不能天然做空ETF，本阶段`ETF short`只表示归因或需要融券/借券条件的压力测试。
- ETF成交额参与率按`amount * 1000`估算成交额人民币；最终实盘前必须再次核对Tushare金额单位、盘口深度和融券可得性。
- 不做ETF选择优化。`512100.SH`用于全历史覆盖观察；`159845.SZ`、`560010.SH`、`159629.SZ`用于2021/2022后流动性改善对照。

## 全样本512100结果

20bp股票成本下，`512100.SH`同窗口baseline期末权益`{baseline_final:.4f}`、最大回撤`{pct(baseline_dd)}`；100% ETF空头、单边5bp且不计融券成本后，期末权益`{hedge_final:.4f}`、最大回撤`{pct(hedge_dd)}`。

{markdown_table(full_512, ["roundtrip_cost_bps", "etf_code", "scenario", "final_equity", "total_return", "max_drawdown", "sharpe", "beta_to_benchmark", "total_etf_trade_cost_ret", "total_borrow_cost_ret", "tradability"])}

## 后半段高流动ETF对照

{markdown_table(post_liquid, ["roundtrip_cost_bps", "etf_code", "etf_name", "scenario", "days", "start_date", "final_equity", "max_drawdown", "sharpe", "beta_to_benchmark", "median_etf_amount_raw", "p10_etf_amount_raw"])}

## 相对同窗口baseline变化

{markdown_table(delta[(delta["roundtrip_cost_bps"] == 20.0) & (delta["scenario"] != "baseline_same_window")], ["etf_code", "scenario", "days", "delta_final_equity", "delta_max_drawdown", "delta_sharpe", "delta_beta"], max_rows=24)}

## ETF成交参与率压力

{markdown_table(liq_focus, ["etf_code", "scenario", "capital_cny", "trade_days", "median_trade_notional_cny", "p95_trade_notional_cny", "median_amount_cny_est", "p10_amount_cny_est", "p95_participation", "pct_days_participation_gt_1pct", "pct_days_participation_gt_5pct"])}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段使用第226阶段固定ETF候选，只测试`50%/100%`两个解释性对冲档和外生成本，没有按结果选择最优ETF或最优参数。

## 运行后过拟合反思

- 判断：否。
- 原因：报告同时保留收益被对冲吃掉、普通账户不可天然做空ETF、融券成本未确权、成交额参与率等反证。

## 运行前继续价值反思

- 判断：是。
- 原因：ETF能绕开IM一手合约颗粒度问题，是当前资金体量下更现实的beta工具候选。

## 运行后继续价值反思

- 判断：有，但方向应从“对冲”转成“beta预算/小仓位卫星”。
- 原因：ETF空头归因能降低回撤和beta，但收益同样被明显吃掉，且真实做空条件不稳定；普通账户更自然的落地形态仍是控制股票篮子仓位，而不是强行市场中性。

## 决策

- 不接入第78。
- 不进入正式股票策略。
- 不做第78 A/B/C。
- 不把ETF空头归因当成可交易结果。
- 暂不继续优化ETF对冲比例。
- 下一步应做股票震荡long-only的小仓位卫星版本边界：固定仓位上限、年度回撤贡献、与第78趋势策略相关性，而不是继续追求市场中性。

## 输出文件

- `{OUTPUT_DIR / f"{PREFIX}_summary.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_delta_vs_baseline.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_daily_curves.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_liquidity_pressure.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_metadata.json"}`
"""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock = load_stock_equity()
    etf_daily = load_etf_daily()
    etf_names = load_etf_names()

    summary, curves = build_curves(stock, etf_daily, etf_names)
    delta = build_delta_summary(summary)
    liquidity = build_liquidity_pressure(curves)

    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(OUTPUT_DIR / f"{PREFIX}_delta_vs_baseline.csv", index=False, encoding="utf-8-sig")
    curves.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_curves.csv", index=False, encoding="utf-8-sig")
    liquidity.to_csv(OUTPUT_DIR / f"{PREFIX}_liquidity_pressure.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stock_equity_path": str(STOCK_EQUITY_PATH),
        "etf_daily_path": str(ETF_DAILY_PATH),
        "etf_codes": ETF_CODES,
        "capital_scenarios_cny": CAPITAL_SCENARIOS_CNY,
        "amount_raw_to_cny": AMOUNT_RAW_TO_CNY,
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
    }
    (OUTPUT_DIR / f"{PREFIX}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = write_report(summary, delta, liquidity)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(summary.to_string(index=False))
    print(liquidity.to_string(index=False))


if __name__ == "__main__":
    main()
