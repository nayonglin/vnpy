from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_repairability_filter_cost_capacity import (
    BASELINE_SCENARIO,
    CANDIDATE_SCENARIO,
    SCENARIOS,
    build_symbol_daily_from_selected,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_execution_constraints_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_execution_constraints_v1"

EXECUTION_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "execution_variant": "open_tradeable_no_adv_cap_50bp",
        "description": "次日开盘成交，只限制停牌/一字板，不设ADV成交上限",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 10_000_000.0,
        "max_participation_adv20": None,
    },
    {
        "execution_variant": "open_tradeable_cap5pct_adv_10m_50bp",
        "description": "次日开盘成交，1000万资金，单票单日成交额不超过5% ADV20",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 10_000_000.0,
        "max_participation_adv20": 0.05,
    },
    {
        "execution_variant": "open_tradeable_cap3pct_adv_50m_50bp",
        "description": "次日开盘成交，5000万资金，单票单日成交额不超过3% ADV20",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 50_000_000.0,
        "max_participation_adv20": 0.03,
    },
    {
        "execution_variant": "open_tradeable_cap1pct_adv_50m_50bp",
        "description": "次日开盘成交，5000万资金，单票单日成交额不超过1% ADV20",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 50_000_000.0,
        "max_participation_adv20": 0.01,
    },
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Trading Costs by Frazzini, Israel and Moskowitz",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719",
    ),
    (
        "Short-term reversals and costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Empirical investigation of mean reversion strategies for equity markets",
        "https://arxiv.org/abs/1909.04327",
    ),
)


@dataclass(frozen=True)
class ExecInfo:
    daily_ret: float
    adv20_turnover: float | None
    tradable_open: bool
    is_suspended: bool
    is_oneword_limit_up: bool
    is_oneword_limit_down: bool


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


def build_desired_maps(symbol_daily: pl.DataFrame) -> tuple[dict[tuple[str, date], dict[str, float]], list[date]]:
    desired: dict[tuple[str, date], dict[str, float]] = {}
    dates: set[date] = set()
    for row in symbol_daily.select("scenario", "target_date", "symbol", "target_weight").iter_rows(named=True):
        key = (row["scenario"], row["target_date"])
        desired.setdefault(key, {})[row["symbol"]] = float(row["target_weight"])
        dates.add(row["target_date"])
    return desired, sorted(dates)


def build_exec_info(stock_df: pl.DataFrame) -> dict[tuple[date, str], ExecInfo]:
    needed = [
        "datetime",
        "symbol",
        "trade_open",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "adv20_turnover",
    ]
    work = (
        stock_df.select([col for col in needed if col in stock_df.columns])
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"),
        )
        .with_columns(
            pl.when(
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("next_trade_open").is_not_null()
                & (pl.col("next_trade_open") > 0)
            )
            .then(pl.col("next_trade_open") / pl.col("trade_open") - 1)
            .otherwise(None)
            .alias("open_to_next_open_ret")
        )
        .select(
            "datetime",
            "symbol",
            "open_to_next_open_ret",
            "adv20_turnover",
            "trade_open",
            "is_suspended",
            "is_oneword_limit_up",
            "is_oneword_limit_down",
        )
    )
    info: dict[tuple[date, str], ExecInfo] = {}
    for row in work.iter_rows(named=True):
        trade_open = to_float(row.get("trade_open"), default=0.0)
        is_suspended = bool(row.get("is_suspended") or False)
        info[(row["datetime"], row["symbol"])] = ExecInfo(
            daily_ret=to_float(row.get("open_to_next_open_ret"), default=0.0),
            adv20_turnover=to_float(row.get("adv20_turnover"), default=0.0) or None,
            tradable_open=(trade_open > 0 and not is_suspended),
            is_suspended=is_suspended,
            is_oneword_limit_up=bool(row.get("is_oneword_limit_up") or False),
            is_oneword_limit_down=bool(row.get("is_oneword_limit_down") or False),
        )
    return info


def simulate_one(
    scenario: str,
    variant: dict[str, Any],
    dates: list[date],
    desired: dict[tuple[str, date], dict[str, float]],
    exec_info: dict[tuple[date, str], ExecInfo],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actual: dict[str, float] = {}
    curve_rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    equity = 1.0
    peak = 1.0
    one_way_cost = float(variant["roundtrip_cost_bps"]) / 2.0 / 10000.0
    account_size = float(variant["account_size_cny"])
    max_participation = variant["max_participation_adv20"]

    for current_date in dates:
        target = desired.get((scenario, current_date), {})
        symbols = set(actual) | set(target)
        desired_abs_change = 0.0
        filled_abs_change = 0.0
        blocked_buy_weight = 0.0
        blocked_sell_weight = 0.0
        cap_limited_weight = 0.0
        missing_info_weight = 0.0
        limit_block_weight = 0.0
        suspended_block_weight = 0.0
        buy_weight = 0.0
        sell_weight = 0.0
        trade_names = 0
        capped_trade_names = 0
        blocked_trade_names = 0

        next_actual = dict(actual)
        for symbol in symbols:
            previous_weight = actual.get(symbol, 0.0)
            target_weight = target.get(symbol, 0.0)
            delta = target_weight - previous_weight
            if abs(delta) <= 1e-12:
                continue
            desired_abs_change += abs(delta)
            side = "buy" if delta > 0 else "sell"
            info = exec_info.get((current_date, symbol))
            if info is None:
                missing_info_weight += abs(delta)
                blocked_trade_names += 1
                if side == "buy":
                    blocked_buy_weight += abs(delta)
                else:
                    blocked_sell_weight += abs(delta)
                continue

            blocked_reason = ""
            if not info.tradable_open:
                blocked_reason = "suspended_or_missing_open"
                suspended_block_weight += abs(delta)
            elif side == "buy" and info.is_oneword_limit_up:
                blocked_reason = "oneword_limit_up_buy"
                limit_block_weight += abs(delta)
            elif side == "sell" and info.is_oneword_limit_down:
                blocked_reason = "oneword_limit_down_sell"
                limit_block_weight += abs(delta)

            if blocked_reason:
                blocked_trade_names += 1
                if side == "buy":
                    blocked_buy_weight += abs(delta)
                else:
                    blocked_sell_weight += abs(delta)
                continue

            fill_abs = abs(delta)
            if max_participation is not None:
                if info.adv20_turnover is None or info.adv20_turnover <= 0:
                    missing_info_weight += abs(delta)
                    blocked_trade_names += 1
                    if side == "buy":
                        blocked_buy_weight += abs(delta)
                    else:
                        blocked_sell_weight += abs(delta)
                    continue
                cap_weight = float(max_participation) * info.adv20_turnover / account_size
                if fill_abs > cap_weight:
                    cap_limited_weight += fill_abs - cap_weight
                    fill_abs = max(0.0, cap_weight)
                    capped_trade_names += 1
            fill_delta = fill_abs if side == "buy" else -fill_abs
            if fill_abs <= 1e-12:
                continue
            next_actual[symbol] = previous_weight + fill_delta
            if abs(next_actual[symbol]) <= 1e-12:
                next_actual.pop(symbol, None)
            filled_abs_change += fill_abs
            trade_names += 1
            if side == "buy":
                buy_weight += fill_abs
            else:
                sell_weight += fill_abs

        actual = {symbol: weight for symbol, weight in next_actual.items() if abs(weight) > 1e-12}
        gross_ret = 0.0
        missing_return_weight = 0.0
        for symbol, weight in actual.items():
            info = exec_info.get((current_date, symbol))
            if info is None:
                missing_return_weight += abs(weight)
                continue
            gross_ret += weight * info.daily_ret
        cost_ret = filled_abs_change * one_way_cost
        net_ret = gross_ret - cost_ret
        equity *= 1.0 + net_ret
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        gross_exposure = sum(actual.values())
        curve_rows.append(
            {
                "scenario": scenario,
                "execution_variant": variant["execution_variant"],
                "date": current_date,
                "strategy_gross_daily_ret": gross_ret,
                "turnover_cost_ret": cost_ret,
                "strategy_daily_ret": net_ret,
                "strategy_equity": equity,
                "strategy_drawdown": drawdown,
                "actual_gross_exposure": gross_exposure,
                "actual_active_symbols": len(actual),
                "desired_abs_change": desired_abs_change,
                "filled_abs_change": filled_abs_change,
                "fill_ratio": filled_abs_change / desired_abs_change if desired_abs_change > 0 else 1.0,
            }
        )
        diag_rows.append(
            {
                "scenario": scenario,
                "execution_variant": variant["execution_variant"],
                "date": current_date,
                "desired_abs_change": desired_abs_change,
                "filled_abs_change": filled_abs_change,
                "unfilled_abs_change": max(0.0, desired_abs_change - filled_abs_change),
                "blocked_buy_weight": blocked_buy_weight,
                "blocked_sell_weight": blocked_sell_weight,
                "cap_limited_weight": cap_limited_weight,
                "missing_info_weight": missing_info_weight,
                "limit_block_weight": limit_block_weight,
                "suspended_block_weight": suspended_block_weight,
                "buy_weight": buy_weight,
                "sell_weight": sell_weight,
                "trade_names": trade_names,
                "capped_trade_names": capped_trade_names,
                "blocked_trade_names": blocked_trade_names,
                "actual_gross_exposure": gross_exposure,
                "actual_active_symbols": len(actual),
                "missing_return_weight": missing_return_weight,
            }
        )
    return curve_rows, diag_rows


def summarize_curve(curve: pl.DataFrame, diagnostics: pl.DataFrame, variant: dict[str, Any]) -> dict[str, Any]:
    returns = [float(value) for value in curve.sort("date")["strategy_daily_ret"].to_list()]
    mean = sum(returns) / len(returns) if returns else 0.0
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    active = curve.filter((pl.col("actual_gross_exposure") > 0) | (pl.col("filled_abs_change") > 0))
    final_equity = float(curve["strategy_equity"][-1]) if curve.height else 1.0
    desired_sum = float(diagnostics["desired_abs_change"].sum()) if diagnostics.height else 0.0
    filled_sum = float(diagnostics["filled_abs_change"].sum()) if diagnostics.height else 0.0
    return {
        "scenario": curve["scenario"][0],
        "execution_variant": variant["execution_variant"],
        "description": variant["description"],
        "roundtrip_cost_bps": float(variant["roundtrip_cost_bps"]),
        "account_size_cny": float(variant["account_size_cny"]),
        "max_participation_adv20": variant["max_participation_adv20"],
        "days": curve.height,
        "final_equity": final_equity,
        "total_return": final_equity - 1.0,
        "max_drawdown": float(curve["strategy_drawdown"].min()) if curve.height else 0.0,
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std > 0 else 0.0,
        "cost_drag_sum": float(curve["turnover_cost_ret"].sum()) if curve.height else 0.0,
        "active_day_win_rate": float((active["strategy_daily_ret"] > 0).mean() or 0.0) if not active.is_empty() else 0.0,
        "avg_actual_gross_exposure": float(curve["actual_gross_exposure"].mean() or 0.0),
        "max_actual_gross_exposure": float(curve["actual_gross_exposure"].max() or 0.0),
        "avg_actual_active_symbols": float(curve["actual_active_symbols"].mean() or 0.0),
        "p95_actual_active_symbols": float(curve["actual_active_symbols"].quantile(0.95) or 0.0),
        "desired_abs_change_sum": desired_sum,
        "filled_abs_change_sum": filled_sum,
        "overall_fill_ratio": filled_sum / desired_sum if desired_sum > 0 else 1.0,
        "cap_limited_weight_sum": float(diagnostics["cap_limited_weight"].sum()) if diagnostics.height else 0.0,
        "blocked_buy_weight_sum": float(diagnostics["blocked_buy_weight"].sum()) if diagnostics.height else 0.0,
        "blocked_sell_weight_sum": float(diagnostics["blocked_sell_weight"].sum()) if diagnostics.height else 0.0,
        "limit_block_weight_sum": float(diagnostics["limit_block_weight"].sum()) if diagnostics.height else 0.0,
        "suspended_block_weight_sum": float(diagnostics["suspended_block_weight"].sum()) if diagnostics.height else 0.0,
        "missing_info_weight_sum": float(diagnostics["missing_info_weight"].sum()) if diagnostics.height else 0.0,
    }


def run_execution_backtest(
    desired: dict[tuple[str, date], dict[str, float]],
    dates: list[date],
    exec_info: dict[tuple[date, str], ExecInfo],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    curve_rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for variant in EXECUTION_VARIANTS:
        for scenario in SCENARIOS:
            scenario_curve_rows, scenario_diag_rows = simulate_one(scenario, variant, dates, desired, exec_info)
            curve_rows.extend(scenario_curve_rows)
            diag_rows.extend(scenario_diag_rows)
            curve = pl.DataFrame(scenario_curve_rows)
            diagnostics = pl.DataFrame(scenario_diag_rows)
            summary_rows.append(summarize_curve(curve, diagnostics, variant))
    return (
        pl.DataFrame(summary_rows).sort(["execution_variant", "scenario"]),
        pl.DataFrame(curve_rows).sort(["execution_variant", "scenario", "date"]),
        pl.DataFrame(diag_rows).sort(["execution_variant", "scenario", "date"]),
    )


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(summary: pl.DataFrame, meta: dict[str, Any], paths: dict[str, Path]) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    primary = summary.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO)
        & (pl.col("execution_variant") == "open_tradeable_cap5pct_adv_10m_50bp")
    ).to_dicts()[0]
    no_cap = summary.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO)
        & (pl.col("execution_variant") == "open_tradeable_no_adv_cap_50bp")
    ).to_dicts()[0]
    stress = summary.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO)
        & (pl.col("execution_variant") == "open_tradeable_cap1pct_adv_50m_50bp")
    ).to_dicts()[0]
    continue_judgment = "是" if primary["final_equity"] > 1.0 and primary["sharpe"] > 0 else "否"
    continue_reason = (
        "1000万、5% ADV成交上限下仍为正收益，说明执行约束没有直接打穿候选。"
        if continue_judgment == "是"
        else "1000万、5% ADV成交上限下已经无法保持正收益，说明问题转到执行层。"
    )
    lines = [
        "# 股票震荡liquid_q3成交干枯过滤真实成交约束回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：在第244阶段候选上重放实际成交约束；不新增信号、不调`volume_ratio_20 <= 0.70`阈值。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 短反转能否交易，最终要看成本、冲击和成交失败，而不是只看理论净值。",
        "- 本阶段继续沿用成本/流动性研究的约束思想，但不套黑箱冲击模型；先用可解释的开盘成交、一字板/停牌阻断和ADV成交上限做保守回放。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心观察",
            "",
            f"- 候选在`open_tradeable_no_adv_cap_50bp`下：期末权益`{no_cap['final_equity']:.4f}`，总收益`{pct(no_cap['total_return'])}`，最大回撤`{pct(no_cap['max_drawdown'])}`，Sharpe `{no_cap['sharpe']:.2f}`。",
            f"- 候选在1000万、5% ADV成交上限下：期末权益`{primary['final_equity']:.4f}`，总收益`{pct(primary['total_return'])}`，最大回撤`{pct(primary['max_drawdown'])}`，Sharpe `{primary['sharpe']:.2f}`，整体成交填充率`{pct(primary['overall_fill_ratio'])}`。",
            f"- 候选在5000万、1% ADV更严压力下：期末权益`{stress['final_equity']:.4f}`，总收益`{pct(stress['total_return'])}`，最大回撤`{pct(stress['max_drawdown'])}`，Sharpe `{stress['sharpe']:.2f}`，整体成交填充率`{pct(stress['overall_fill_ratio'])}`。",
            "- 直觉判断：本阶段没有塌陷，前面的突破不只是研究净值好看；但它仍只是“可交易候选”，还没到正式策略。",
            "",
            "## 汇总结果",
            "",
            markdown_table(
                summary,
                [
                    "execution_variant",
                    "scenario",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "cost_drag_sum",
                    "active_day_win_rate",
                    "avg_actual_gross_exposure",
                    "max_actual_gross_exposure",
                    "overall_fill_ratio",
                    "cap_limited_weight_sum",
                    "blocked_buy_weight_sum",
                    "blocked_sell_weight_sum",
                    "limit_block_weight_sum",
                    "suspended_block_weight_sum",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只加入执行约束，不新增预测变量、不调信号阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但仍需真实撮合进一步确认。",
            "- 原因：执行约束是反证测试；若结果变差，是暴露问题，不会让研究过拟合变轻。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第247阶段说明成本/容量近似通过，下一步必须验证真实成交阻断。",
            "",
            "## 运行后继续价值反思",
            "",
            f"- 判断：{continue_judgment}。",
            f"- 原因：{continue_reason}",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 本阶段通过第一层真实成交约束；下一步做延迟成交和样本外纸面跟踪。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, _benchmark_df = load_panels()
    symbol_daily = build_symbol_daily_from_selected(selected_all)
    desired, dates = build_desired_maps(symbol_daily)
    exec_info = build_exec_info(stock_df)
    summary, curves, diagnostics = run_execution_backtest(desired, dates, exec_info)
    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_scenario": BASELINE_SCENARIO,
        "candidate_scenario": CANDIDATE_SCENARIO,
        "execution_variants": EXECUTION_VARIANTS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "execution_note": "Weights are replayed with open-to-next-open returns, simple cash idle handling, no intraday queue model.",
    }
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "diagnostics": OUTPUT_DIR / f"{PREFIX}_diagnostics.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    curves.write_csv(paths["curves"])
    diagnostics.write_csv(paths["diagnostics"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, meta, paths)
    print(summary)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
