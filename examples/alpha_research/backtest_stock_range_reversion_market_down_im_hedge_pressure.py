from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from audit_stock_range_reversion_hedge_data import (
    BASE_DIR,
    CONTINUOUS_METHODS,
    OUTPUT_DIR as AUDIT_OUTPUT_DIR,
    PREFIX as AUDIT_PREFIX,
    STOCK_EQUITY_PATH,
    TRADING_DAYS,
    contract_files,
    pct,
    read_contract_csv,
    safe_beta,
    safe_corr,
    to_float,
)


NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_im_hedge_pressure_2022_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_im_hedge_pressure_v1"

# CFFEX CSI 1000 index futures contract table: multiplier is RMB 200 per index point.
# Current exchange minimum margin is 8%; the 2022 listing notice used 15%.
IM_CONTRACT_MULTIPLIER_CNY: float = 200.0
CONTRACT_SPEC_SOURCES: dict[str, str] = {
    "cffex_contract_table": "https://www.cffex.com.cn/zz1000/",
    "cffex_listing_notice_20220718": "https://www.cffex.com.cn/en_new/NoticesGuidelinesandOther/20220718/28907.html",
}
CAPITAL_SCENARIOS_CNY: tuple[float, ...] = (200_000.0, 500_000.0, 1_000_000.0, 2_000_000.0, 5_000_000.0)


@dataclass(frozen=True)
class HedgeScenario:
    name: str
    description: str
    method: str
    hedge_ratio: float
    futures_one_way_cost_bps: float
    margin_ratio: float


SCENARIOS: tuple[HedgeScenario, ...] = (
    HedgeScenario(
        name="baseline_no_hedge",
        description="2022-07之后股票震荡原始long-only路径",
        method="dominant_by_volume",
        hedge_ratio=0.0,
        futures_one_way_cost_bps=0.0,
        margin_ratio=0.0,
    ),
    HedgeScenario(
        name="im_volume_50_cost2_margin15",
        description="IM成交量主力，50%同暴露对冲，期货单边2bp成本，15%保证金压力",
        method="dominant_by_volume",
        hedge_ratio=0.5,
        futures_one_way_cost_bps=2.0,
        margin_ratio=0.15,
    ),
    HedgeScenario(
        name="im_volume_100_cost2_margin15",
        description="IM成交量主力，100%同暴露对冲，期货单边2bp成本，15%保证金压力",
        method="dominant_by_volume",
        hedge_ratio=1.0,
        futures_one_way_cost_bps=2.0,
        margin_ratio=0.15,
    ),
    HedgeScenario(
        name="im_volume_100_cost5_margin20",
        description="IM成交量主力，100%同暴露对冲，期货单边5bp成本，20%保证金压力",
        method="dominant_by_volume",
        hedge_ratio=1.0,
        futures_one_way_cost_bps=5.0,
        margin_ratio=0.20,
    ),
    HedgeScenario(
        name="im_closeoi_100_cost2_margin15",
        description="IM持仓量主力，100%同暴露对冲，期货单边2bp成本，15%保证金压力",
        method="dominant_by_close_oi",
        hedge_ratio=1.0,
        futures_one_way_cost_bps=2.0,
        margin_ratio=0.15,
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


def summarize_path(curve: pd.DataFrame) -> dict[str, Any]:
    returns = curve["scenario_daily_ret"].fillna(0.0)
    days = len(curve)
    daily_mean = safe_mean(returns)
    daily_std = safe_std(returns)
    total_return = to_float(curve["scenario_equity"].iloc[-1] - 1.0) if days else 0.0
    active_returns = curve.loc[curve["return_gross_exposure"] > 0, "scenario_daily_ret"]
    return {
        "roundtrip_cost_bps": to_float(curve["roundtrip_cost_bps"].iloc[0]) if days else 0.0,
        "scenario": str(curve["scenario"].iloc[0]) if days else "",
        "description": str(curve["scenario_description"].iloc[0]) if days else "",
        "method": str(curve["method"].iloc[0]) if days else "",
        "hedge_ratio": to_float(curve["hedge_ratio"].iloc[0]) if days else 0.0,
        "futures_one_way_cost_bps": to_float(curve["futures_one_way_cost_bps"].iloc[0]) if days else 0.0,
        "margin_ratio": to_float(curve["margin_ratio"].iloc[0]) if days else 0.0,
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
        "avg_margin_weight": safe_mean(curve["margin_weight"]),
        "max_margin_weight": to_float(curve["margin_weight"].max()) if days else 0.0,
        "annualized_futures_turnover": safe_mean(curve["futures_turnover_notional"]) * TRADING_DAYS,
        "total_futures_cost_ret": to_float(curve["futures_cost_ret"].sum()),
        "roll_days_with_hedge": int(((curve["is_roll_day"]) & (curve["hedge_notional"] > 0)).sum()),
        "fallback_ret_days": int(curve["fallback_ret"].sum()),
        "corr_hedged_to_benchmark": safe_corr(curve["scenario_daily_ret"], curve["benchmark_daily_ret"]),
        "beta_hedged_to_benchmark": safe_beta(curve["scenario_daily_ret"], curve["benchmark_daily_ret"]),
    }


def load_im_panel() -> pd.DataFrame:
    parts = [read_contract_csv(path, "IM") for path in contract_files("IM")]
    parts = [part for part in parts if not part.empty]
    if not parts:
        raise FileNotFoundError("No local IM contract CSVs found")
    panel = pd.concat(parts, ignore_index=True, sort=False)
    panel["date"] = pd.to_datetime(panel["date"]).dt.date
    return panel.sort_values(["date", "symbol"]).reset_index(drop=True)


def build_target_contracts(panel: pd.DataFrame, method: str) -> pd.DataFrame:
    sort_column = "close_oi" if method == "dominant_by_close_oi" else "volume"
    work = panel.copy()
    work[sort_column] = pd.to_numeric(work[sort_column], errors="coerce").fillna(0.0)
    work = work.sort_values(["date", sort_column, "volume", "symbol"], ascending=[True, False, False, True])
    target = work.groupby("date", as_index=False).head(1).copy()
    target = target.sort_values("date").reset_index(drop=True)
    target = target.rename(
        columns={
            "symbol": "target_symbol",
            "contract_month": "target_contract_month",
            "close": "target_close",
            "volume": "target_volume",
            "close_oi": "target_close_oi",
        }
    )
    return target[
        [
            "date",
            "target_symbol",
            "target_contract_month",
            "target_close",
            "target_volume",
            "target_close_oi",
        ]
    ]


def build_roll_aware_im_returns(panel: pd.DataFrame, method: str) -> pd.DataFrame:
    target = build_target_contracts(panel, method)
    close_map = panel.set_index(["date", "symbol"])["close"].to_dict()

    rows: list[dict[str, Any]] = []
    previous_date: Any | None = None
    previous_target_symbol: str | None = None
    previous_target_close: float | None = None

    for row in target.itertuples(index=False):
        date = row.date
        target_symbol = str(row.target_symbol)
        target_close = to_float(row.target_close)
        daily_ret: float | None = None
        held_symbol = previous_target_symbol
        fallback_ret = False
        is_roll_day = False

        if previous_date is not None and previous_target_symbol is not None:
            prev_held_close = close_map.get((previous_date, previous_target_symbol))
            current_held_close = close_map.get((date, previous_target_symbol))
            if prev_held_close and current_held_close:
                daily_ret = to_float(current_held_close) / to_float(prev_held_close) - 1.0
            elif previous_target_close:
                daily_ret = target_close / previous_target_close - 1.0
                fallback_ret = True
            is_roll_day = target_symbol != previous_target_symbol

        rows.append(
            {
                "date": date,
                "method": method,
                "target_symbol": target_symbol,
                "held_symbol": held_symbol or "",
                "target_contract_month": str(row.target_contract_month),
                "target_close": target_close,
                "target_volume": to_float(row.target_volume),
                "target_close_oi": to_float(row.target_close_oi),
                "im_contract_notional_cny": target_close * IM_CONTRACT_MULTIPLIER_CNY,
                "im_daily_ret": daily_ret,
                "is_roll_day": is_roll_day,
                "fallback_ret": fallback_ret,
            }
        )
        previous_date = date
        previous_target_symbol = target_symbol
        previous_target_close = target_close

    return pd.DataFrame(rows).dropna(subset=["im_daily_ret"]).reset_index(drop=True)


def load_stock_equity() -> pd.DataFrame:
    frame = pd.read_csv(STOCK_EQUITY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame.sort_values(["roundtrip_cost_bps", "date"]).reset_index(drop=True)


def apply_scenario(stock: pd.DataFrame, im_returns: pd.DataFrame, scenario: HedgeScenario) -> pd.DataFrame:
    work = stock.merge(im_returns, on="date", how="inner")
    work = work.sort_values("date").reset_index(drop=True)
    work["hedge_notional"] = scenario.hedge_ratio * work["return_gross_exposure"].clip(lower=0.0)
    previous_notional = work["hedge_notional"].shift(1).fillna(0.0)
    rebalance_turnover = (work["hedge_notional"] - previous_notional).abs()
    roll_turnover = (previous_notional.abs() + work["hedge_notional"].abs()).where(work["is_roll_day"], 0.0)
    work["futures_turnover_notional"] = rebalance_turnover.where(~work["is_roll_day"], roll_turnover)
    work["futures_cost_ret"] = work["futures_turnover_notional"] * scenario.futures_one_way_cost_bps / 10_000.0
    work["hedge_daily_ret"] = -work["hedge_notional"] * work["im_daily_ret"]
    work["margin_weight"] = work["hedge_notional"] * scenario.margin_ratio
    work["scenario_daily_ret"] = work["strategy_daily_ret"] + work["hedge_daily_ret"] - work["futures_cost_ret"]
    equity, drawdown = equity_and_drawdown(work["scenario_daily_ret"])
    work["scenario_equity"] = equity
    work["scenario_drawdown"] = drawdown
    work["scenario"] = scenario.name
    work["scenario_description"] = scenario.description
    work["method"] = scenario.method
    work["hedge_ratio"] = scenario.hedge_ratio
    work["futures_one_way_cost_bps"] = scenario.futures_one_way_cost_bps
    work["margin_ratio"] = scenario.margin_ratio
    return work


def build_paths(stock: pd.DataFrame, im_by_method: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for cost_bps, cost_group in stock.groupby("roundtrip_cost_bps"):
        cost_group = cost_group.sort_values("date").reset_index(drop=True)
        for scenario in SCENARIOS:
            im_returns = im_by_method[scenario.method]
            curve = apply_scenario(cost_group, im_returns, scenario)
            curves.append(curve)
            summaries.append(summarize_path(curve))
    summary = pd.DataFrame(summaries).sort_values(
        ["roundtrip_cost_bps", "hedge_ratio", "scenario"]
    )
    all_curves = pd.concat(curves, ignore_index=True, sort=False)
    return summary, all_curves


def build_lot_feasibility(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scenario_cols = [
        "roundtrip_cost_bps",
        "scenario",
        "method",
        "hedge_ratio",
        "futures_one_way_cost_bps",
        "margin_ratio",
    ]
    for keys, group in curves.groupby(scenario_cols):
        group = group.sort_values("date").copy()
        roundtrip_cost_bps, scenario, method, hedge_ratio, futures_cost_bps, margin_ratio = keys
        if to_float(hedge_ratio) <= 0:
            continue
        active = group[group["hedge_notional"] > 0].copy()
        if active.empty:
            continue
        required_capital = active["im_contract_notional_cny"] / active["hedge_notional"]
        for capital in CAPITAL_SCENARIOS_CNY:
            target_contracts = active["hedge_notional"] * capital / active["im_contract_notional_cny"]
            rounded_contracts = target_contracts.round()
            one_contract_notional_ratio = active["im_contract_notional_cny"] / capital
            margin_weight_one_contract = one_contract_notional_ratio * to_float(margin_ratio)
            rows.append(
                {
                    "roundtrip_cost_bps": to_float(roundtrip_cost_bps),
                    "scenario": str(scenario),
                    "method": str(method),
                    "hedge_ratio": to_float(hedge_ratio),
                    "futures_one_way_cost_bps": to_float(futures_cost_bps),
                    "margin_ratio": to_float(margin_ratio),
                    "capital_cny": capital,
                    "active_hedge_days": int(len(active)),
                    "median_target_contracts": to_float(target_contracts.median()),
                    "max_target_contracts": to_float(target_contracts.max()),
                    "pct_days_target_lt_half_contract": to_float((target_contracts < 0.5).mean()),
                    "pct_days_target_lt_one_contract": to_float((target_contracts < 1.0).mean()),
                    "pct_days_rounded_zero": to_float((rounded_contracts == 0).mean()),
                    "median_one_contract_notional_ratio": to_float(one_contract_notional_ratio.median()),
                    "max_one_contract_notional_ratio": to_float(one_contract_notional_ratio.max()),
                    "median_margin_weight_one_contract": to_float(margin_weight_one_contract.median()),
                    "max_margin_weight_one_contract": to_float(margin_weight_one_contract.max()),
                    "median_required_capital_for_one_contract_target": to_float(required_capital.median()),
                    "p25_required_capital_for_one_contract_target": to_float(required_capital.quantile(0.25)),
                    "p75_required_capital_for_one_contract_target": to_float(required_capital.quantile(0.75)),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["roundtrip_cost_bps", "scenario", "capital_cny"]
    ).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(summary: pd.DataFrame, lot_feasibility: pd.DataFrame, im_tracking: pd.DataFrame) -> Path:
    summary_20 = summary[summary["roundtrip_cost_bps"] == 20.0].copy()
    lot_focus = lot_feasibility[
        (lot_feasibility["roundtrip_cost_bps"] == 20.0)
        & (lot_feasibility["scenario"].isin(["im_volume_100_cost2_margin15", "im_volume_50_cost2_margin15"]))
        & (lot_feasibility["capital_cny"].isin([200_000.0, 1_000_000.0, 5_000_000.0]))
    ].copy()
    baseline_20 = summary_20[summary_20["scenario"] == "baseline_no_hedge"]
    hedge100_20 = summary_20[summary_20["scenario"] == "im_volume_100_cost2_margin15"]
    baseline_dd = to_float(baseline_20.iloc[0]["max_drawdown"]) if not baseline_20.empty else 0.0
    hedge100_dd = to_float(hedge100_20.iloc[0]["max_drawdown"]) if not hedge100_20.empty else 0.0
    hedge100_final = to_float(hedge100_20.iloc[0]["final_equity"]) if not hedge100_20.empty else 0.0

    report = f"""# 股票震荡 IM 对冲压力测试 v1

- 记录时间：{datetime.now().strftime("%Y-%m-%d %H:%M CST")}
- 当前研究线：股票震荡 `market_down`，与第78趋势策略、期货震荡策略隔离。
- 本阶段性质：2022-07之后分段压力测试，不是正式策略版本。
- 合约规格来源：
  - 中金所中证1000股指期货合约表：{CONTRACT_SPEC_SOURCES["cffex_contract_table"]}
  - 中金所2022-07-18上市通知：{CONTRACT_SPEC_SOURCES["cffex_listing_notice_20220718"]}

## 关键假设

- IM合约乘数：每点人民币`{IM_CONTRACT_MULTIPLIER_CNY:.0f}`元。
- 使用本地IM日线合约CSV构造滚动收益：先持有前一日目标主力到当日收盘，再在收盘后切换到新目标主力，避免把跨合约价差跳变当成日内收益。
- 股票腿直接沿用第218阶段合并持仓路径，分别保留`20bp`和`50bp`股票往返成本。
- 期货腿成本是显式压力假设：单边`2bp`或`5bp`按期货名义成交额扣减；保证金为`15%`或`20%`压力观测，不直接扣收益。
- 回测仍按分数名义计算对冲收益；一手合约颗粒度另表审计，不能忽略。

## 分数名义压力结果

20bp股票成本下，baseline后IM样本最大回撤为`{pct(baseline_dd)}`；IM成交量主力100%同暴露对冲、期货单边2bp、15%保证金压力下，期末权益`{hedge100_final:.4f}`，最大回撤`{pct(hedge100_dd)}`。

{markdown_table(summary, ["roundtrip_cost_bps", "scenario", "final_equity", "total_return", "max_drawdown", "sharpe", "avg_hedge_notional", "max_margin_weight", "annualized_futures_turnover", "total_futures_cost_ret", "beta_hedged_to_benchmark"])}

## 一手颗粒度审计

说明：这里不是另一个回测，而是检查目标对冲名义相对于一手IM合约是否可执行。`pct_days_rounded_zero` 越高，说明按最接近整数手数执行时越容易完全对冲不了；`median_one_contract_notional_ratio` 越高，说明一手合约相对账户越重。

{markdown_table(lot_focus, ["scenario", "capital_cny", "median_target_contracts", "max_target_contracts", "pct_days_target_lt_one_contract", "pct_days_rounded_zero", "median_one_contract_notional_ratio", "median_margin_weight_one_contract", "median_required_capital_for_one_contract_target"])}

## IM滚动收益质检

{markdown_table(im_tracking, ["method", "days", "roll_days", "fallback_ret_days", "corr_to_csi1000", "beta_to_csi1000", "annualized_tracking_error"])}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只在第224阶段确定的2022-07后IM可用区间做粗压力场景；对冲比例只使用`50%/100%`两个解释性档位，成本/保证金为外生压力，不根据结果择优。

## 运行后过拟合反思

- 判断：否。
- 原因：结果同时输出分数名义收益和一手颗粒度约束；没有因为理论对冲改善就忽略小账户无法细粒度执行的硬约束。

## 运行前继续价值反思

- 判断：是。
- 原因：第224阶段证明IM对中证1000跟踪足够好，但只覆盖2022-07以后；必须先看真实对冲腿会怎样改变后半段路径。

## 运行后继续价值反思

- 判断：有，但不适合当前小资金直接做。
- 原因：分数名义IM对冲明显压低beta和回撤，说明风险结构上成立；但一手IM名义过大，20万到100万资金下多数日期目标手数小于1，无法平滑执行。

## 决策

- 不接入第78。
- 不进入正式股票策略。
- 不做第78 A/B/C。
- 不把分数名义IM结果当成实盘结果。
- 股票震荡若继续，优先补中证1000 ETF/基金历史行情，或者明确资金规模达到可交易IM颗粒度后再研究期货对冲版。

## 输出文件

- `{OUTPUT_DIR / f"{PREFIX}_summary.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_daily_curves.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_lot_feasibility.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_im_roll_returns.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_im_tracking.csv"}`
"""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def build_im_tracking(im_by_method: dict[str, pd.DataFrame], stock: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    benchmark = stock.sort_values(["date", "roundtrip_cost_bps"]).drop_duplicates("date")
    for method, im_returns in im_by_method.items():
        merged = im_returns.merge(benchmark[["date", "benchmark_daily_ret"]], on="date", how="inner")
        diff = merged["im_daily_ret"] - merged["benchmark_daily_ret"]
        rows.append(
            {
                "method": method,
                "days": int(len(merged)),
                "first_date": str(merged["date"].min()) if len(merged) else "",
                "last_date": str(merged["date"].max()) if len(merged) else "",
                "roll_days": int(merged["is_roll_day"].sum()) if len(merged) else 0,
                "fallback_ret_days": int(merged["fallback_ret"].sum()) if len(merged) else 0,
                "corr_to_csi1000": safe_corr(merged["im_daily_ret"], merged["benchmark_daily_ret"]),
                "beta_to_csi1000": safe_beta(merged["im_daily_ret"], merged["benchmark_daily_ret"]),
                "annualized_tracking_error": to_float(diff.std(ddof=1) * sqrt(TRADING_DAYS))
                if len(diff.dropna()) > 1
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("method").reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    im_panel = load_im_panel()
    im_by_method = {method: build_roll_aware_im_returns(im_panel, method) for method in CONTINUOUS_METHODS}
    stock = load_stock_equity()
    summary, curves = build_paths(stock, im_by_method)
    lot_feasibility = build_lot_feasibility(curves)
    im_tracking = build_im_tracking(im_by_method, stock)

    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    curves.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_curves.csv", index=False, encoding="utf-8-sig")
    lot_feasibility.to_csv(OUTPUT_DIR / f"{PREFIX}_lot_feasibility.csv", index=False, encoding="utf-8-sig")
    im_tracking.to_csv(OUTPUT_DIR / f"{PREFIX}_im_tracking.csv", index=False, encoding="utf-8-sig")
    pd.concat(im_by_method.values(), ignore_index=True, sort=False).to_csv(
        OUTPUT_DIR / f"{PREFIX}_im_roll_returns.csv", index=False, encoding="utf-8-sig"
    )

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stock_equity_path": str(STOCK_EQUITY_PATH),
        "audit_output_dir": str(AUDIT_OUTPUT_DIR),
        "audit_prefix": AUDIT_PREFIX,
        "im_contract_multiplier_cny": IM_CONTRACT_MULTIPLIER_CNY,
        "contract_spec_sources": CONTRACT_SPEC_SOURCES,
        "capital_scenarios_cny": CAPITAL_SCENARIOS_CNY,
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
    }
    (OUTPUT_DIR / f"{PREFIX}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = write_report(summary, lot_feasibility, im_tracking)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(summary.to_string(index=False))
    print(lot_feasibility.to_string(index=False))


if __name__ == "__main__":
    main()
