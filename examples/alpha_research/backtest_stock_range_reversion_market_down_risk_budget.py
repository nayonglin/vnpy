from __future__ import annotations

import json
import os
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_market_down_long_only import (
    COST_BPS,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    PREFIX as BASE_PREFIX,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
BASE_BACKTEST_DIR: Path = Path(
    os.getenv(
        "BASE_BACKTEST_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_long_only_2018_2026"),
    )
).expanduser().resolve()
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_risk_budget_2018_2026"),
    )
).expanduser().resolve()

PREFIX: str = "stock_range_reversion_market_down_risk_budget_v1"
INITIAL_EQUITY: float = float(os.getenv("INITIAL_EQUITY", "1.0") or 1.0)
TRADING_DAYS: int = int(os.getenv("TRADING_DAYS", "252") or 252)


@dataclass(frozen=True)
class RiskScenario:
    name: str
    description: str
    max_active_sleeves: int | None = None
    cooldown_trading_days: int = 0


SCENARIOS: tuple[RiskScenario, ...] = (
    RiskScenario("baseline", "第214阶段原始路径：不限制重叠篮子"),
    RiskScenario("max_sleeves_5", "最多5个重叠篮子，约半仓风险预算", max_active_sleeves=5),
    RiskScenario("max_sleeves_3", "最多3个重叠篮子，保守风险预算", max_active_sleeves=3),
    RiskScenario("cooldown_2d", "接受一个信号篮子后，至少间隔2个交易日再接受新篮子", cooldown_trading_days=2),
    RiskScenario(
        "max_sleeves_5_cooldown_2d",
        "最多5个重叠篮子，且信号篮子之间至少间隔2个交易日",
        max_active_sleeves=5,
        cooldown_trading_days=2,
    ),
)


def require_path(path: Path) -> Path:
    """Return an existing path or raise a clear error."""
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def load_base_outputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load basket-level outputs from the fixed market-down path backtest."""
    basket_daily = pl.read_csv(require_path(BASE_BACKTEST_DIR / f"{BASE_PREFIX}_basket_daily.csv"), try_parse_dates=True)
    basket_horizon = pl.read_csv(
        require_path(BASE_BACKTEST_DIR / f"{BASE_PREFIX}_basket_horizon.csv"), try_parse_dates=True
    )
    return basket_daily, basket_horizon


def build_trading_index(benchmark_df: pl.DataFrame) -> dict[Any, int]:
    """Map each benchmark trading date to an ordinal index."""
    dates = benchmark_df.sort("datetime")["datetime"].to_list()
    return {date: index for index, date in enumerate(dates)}


def select_signal_dates(
    signal_dates: list[Any],
    trading_index: dict[Any, int],
    scenario: RiskScenario,
) -> tuple[list[Any], pl.DataFrame]:
    """Select accepted signal dates under one mechanical risk-budget scenario."""
    accepted: list[Any] = []
    decision_rows: list[dict[str, Any]] = []
    for signal_date in signal_dates:
        signal_index = trading_index[signal_date]
        active_before = sum(1 for accepted_date in accepted if 0 < signal_index - trading_index[accepted_date] < HORIZON)
        days_since_last = signal_index - trading_index[accepted[-1]] if accepted else None

        reject_reasons: list[str] = []
        if scenario.max_active_sleeves is not None and active_before >= scenario.max_active_sleeves:
            reject_reasons.append("max_active_sleeves")
        if days_since_last is not None and days_since_last <= scenario.cooldown_trading_days:
            reject_reasons.append("cooldown")

        accepted_flag = not reject_reasons
        if accepted_flag:
            accepted.append(signal_date)

        decision_rows.append(
            {
                "scenario": scenario.name,
                "signal_date": signal_date,
                "accepted": accepted_flag,
                "active_sleeves_before": active_before,
                "days_since_last_accepted": days_since_last,
                "reject_reason": ",".join(reject_reasons) if reject_reasons else "",
            }
        )
    return accepted, pl.DataFrame(decision_rows)


def build_equity_curve(
    basket_daily: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    accepted_dates: list[Any],
    cost_bps: float,
    scenario: RiskScenario,
    full_start: Any,
    full_end: Any,
) -> pl.DataFrame:
    """Build an overlapping-sleeve equity curve for accepted signal dates."""
    sleeve_weight = 1.0 / HORIZON
    daily_cost = (cost_bps / 10000.0) / HORIZON
    accepted_series = pl.Series("signal_date", accepted_dates).implode()
    accepted_daily = basket_daily.filter(pl.col("signal_date").is_in(accepted_series))
    if accepted_daily.is_empty():
        daily = pl.DataFrame(
            {
                "pnl_date": [],
                "strategy_daily_ret": [],
                "benchmark_daily_ret_active": [],
                "gross_exposure": [],
                "active_sleeves": [],
                "active_stock_positions": [],
            },
            schema={
                "pnl_date": pl.Date,
                "strategy_daily_ret": pl.Float64,
                "benchmark_daily_ret_active": pl.Float64,
                "gross_exposure": pl.Float64,
                "active_sleeves": pl.Int64,
                "active_stock_positions": pl.Int64,
            },
        )
    else:
        components = accepted_daily.with_columns(
            ((pl.col("basket_stock_daily_ret") - daily_cost) * sleeve_weight).alias("strategy_component_ret"),
            (pl.col("benchmark_daily_ret") * sleeve_weight).alias("benchmark_component_ret"),
            pl.lit(sleeve_weight).alias("exposure_component"),
        )
        daily = (
            components.group_by("pnl_date")
            .agg(
                pl.col("strategy_component_ret").sum().alias("strategy_daily_ret"),
                pl.col("benchmark_component_ret").sum().alias("benchmark_daily_ret_active"),
                pl.col("exposure_component").sum().alias("gross_exposure"),
                pl.col("signal_date").n_unique().alias("active_sleeves"),
                pl.col("stock_count").sum().alias("active_stock_positions"),
            )
            .sort("pnl_date")
        )

    all_dates = benchmark_df.select(pl.col("datetime").alias("pnl_date")).filter(
        (pl.col("pnl_date") >= full_start) & (pl.col("pnl_date") <= full_end)
    )
    return (
        all_dates.join(daily, on="pnl_date", how="left")
        .with_columns(
            pl.col("strategy_daily_ret").fill_null(0.0),
            pl.col("benchmark_daily_ret_active").fill_null(0.0),
            pl.col("gross_exposure").fill_null(0.0),
            pl.col("active_sleeves").fill_null(0),
            pl.col("active_stock_positions").fill_null(0),
        )
        .with_columns(
            (INITIAL_EQUITY * (1 + pl.col("strategy_daily_ret")).cum_prod()).alias("strategy_equity"),
            (INITIAL_EQUITY * (1 + pl.col("benchmark_daily_ret_active")).cum_prod()).alias("benchmark_equity"),
        )
        .with_columns(
            (pl.col("strategy_equity") / pl.col("strategy_equity").cum_max() - 1).alias("strategy_drawdown"),
            (pl.col("benchmark_equity") / pl.col("benchmark_equity").cum_max() - 1).alias("benchmark_drawdown"),
            pl.lit(cost_bps).alias("roundtrip_cost_bps"),
            pl.lit(scenario.name).alias("scenario"),
            pl.lit(scenario.description).alias("scenario_description"),
        )
    )


def summarize_curve(
    curve: pl.DataFrame,
    basket_horizon: pl.DataFrame,
    accepted_dates: list[Any],
    scenario: RiskScenario,
    cost_bps: float,
) -> dict[str, Any]:
    """Summarize one risk-budget curve."""
    accepted_series = pl.Series("signal_date", accepted_dates).implode()
    accepted_baskets = basket_horizon.filter(pl.col("signal_date").is_in(accepted_series))
    cost_return = cost_bps / 10000.0
    accepted_net = accepted_baskets.with_columns(
        (pl.col("gross_basket_ret") - cost_return).alias("net_basket_ret"),
        (pl.col("gross_basket_excess_ret") - cost_return).alias("net_basket_excess_ret"),
    )
    days = curve.height
    total_return = to_float(curve["strategy_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    benchmark_total_return = to_float(curve["benchmark_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    daily_mean = to_float(curve["strategy_daily_ret"].mean()) if days else 0.0
    daily_std = to_float(curve["strategy_daily_ret"].std()) if days else 0.0
    annualized_return = (1 + total_return) ** (TRADING_DAYS / days) - 1 if days and total_return > -1 else 0.0
    benchmark_annualized_return = (
        (1 + benchmark_total_return) ** (TRADING_DAYS / days) - 1
        if days and benchmark_total_return > -1
        else 0.0
    )
    return {
        "scenario": scenario.name,
        "scenario_description": scenario.description,
        "roundtrip_cost_bps": cost_bps,
        "feature": FEATURE,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "days": days,
        "accepted_signal_baskets": len(accepted_dates),
        "acceptance_ratio": len(accepted_dates) / basket_horizon.height if basket_horizon.height else 0.0,
        "final_equity": to_float(curve["strategy_equity"][-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": to_float(curve["strategy_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "calmar": annualized_return / abs(to_float(curve["strategy_drawdown"].min())) if days and curve["strategy_drawdown"].min() < 0 else 0.0,
        "benchmark_final_equity": to_float(curve["benchmark_equity"][-1]) if days else INITIAL_EQUITY,
        "benchmark_total_return": benchmark_total_return,
        "benchmark_annualized_return": benchmark_annualized_return,
        "benchmark_max_drawdown": to_float(curve["benchmark_drawdown"].min()) if days else 0.0,
        "active_day_ratio": to_float((curve["gross_exposure"] > 0).mean()) if days else 0.0,
        "avg_gross_exposure": to_float(curve["gross_exposure"].mean()) if days else 0.0,
        "max_gross_exposure": to_float(curve["gross_exposure"].max()) if days else 0.0,
        "max_active_sleeves": int(curve["active_sleeves"].max()) if days else 0,
        "avg_active_stock_positions": to_float(curve["active_stock_positions"].mean()) if days else 0.0,
        "net_basket_ret_mean": to_float(accepted_net["net_basket_ret"].mean()) if accepted_net.height else 0.0,
        "net_basket_excess_ret_mean": to_float(accepted_net["net_basket_excess_ret"].mean()) if accepted_net.height else 0.0,
        "net_basket_win_rate": to_float((accepted_net["net_basket_ret"] > 0).mean()) if accepted_net.height else 0.0,
        "net_basket_excess_win_rate": to_float((accepted_net["net_basket_excess_ret"] > 0).mean()) if accepted_net.height else 0.0,
    }


def build_year_summary(equity_df: pl.DataFrame, decisions_df: pl.DataFrame) -> pl.DataFrame:
    """Summarize year-level path return and accepted signal counts."""
    year_path = (
        equity_df.with_columns(pl.col("pnl_date").dt.year().alias("year"))
        .group_by(["scenario", "roundtrip_cost_bps", "year"])
        .agg(
            (pl.col("strategy_equity").last() / pl.col("strategy_equity").first() - 1).alias(
                "simple_year_path_return"
            ),
            pl.col("strategy_drawdown").min().alias("min_drawdown_seen"),
            pl.col("gross_exposure").mean().alias("avg_exposure"),
            pl.col("active_sleeves").max().alias("max_active_sleeves"),
        )
    )
    year_decisions = (
        decisions_df.with_columns(pl.col("signal_date").dt.year().alias("year"))
        .group_by(["scenario", "year"])
        .agg(
            pl.len().alias("signal_baskets"),
            pl.col("accepted").sum().alias("accepted_signal_baskets"),
            (pl.col("accepted").sum() / pl.len()).alias("acceptance_ratio"),
        )
    )
    return year_path.join(year_decisions, on=["scenario", "year"], how="left").sort(
        ["roundtrip_cost_bps", "scenario", "year"]
    )


def write_report(
    summary_df: pl.DataFrame,
    year_df: pl.DataFrame,
    decisions_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for risk-budget pressure tests."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 风险预算压力测试 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略版本，也不是参数优化；只把第214阶段固定信号路径放进少数机械风控约束，观察回撤和收益如何变化。",
        f"- 原始口径：`{MARKET_STATE}`、`{FEATURE}`、固定持有`{HORIZON}`日；成本情景：`{', '.join(str(x) for x in COST_BPS)}bp`。",
        "- 风控约束只看重叠篮子上限和信号间隔，不使用行业收益、未来收益或回撤段信息生成规则。",
        "",
        "## 总体结果",
        "",
    ]

    for cost_bps in sorted(summary_df["roundtrip_cost_bps"].unique().to_list()):
        lines.append(f"### 成本`{cost_bps:.0f}bp`")
        focus = summary_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("scenario")
        for row in focus.iter_rows(named=True):
            lines.append(
                f"- `{row['scenario']}`：接受篮子`{row['accepted_signal_baskets']}`个，"
                f"接受率`{row['acceptance_ratio']:.2%}`，期末权益`{row['final_equity']:.4f}`，"
                f"总收益`{row['total_return']:.2%}`，最大回撤`{row['max_drawdown']:.2%}`，"
                f"Sharpe `{row['sharpe']:.2f}`，平均暴露`{row['avg_gross_exposure']:.2%}`。"
            )

    lines.extend(["", "## 2018/2022压力年份", ""])
    stress_years = year_df.filter(pl.col("year").is_in([2018, 2022])).sort(
        ["roundtrip_cost_bps", "scenario", "year"]
    )
    for row in stress_years.iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}` `{row['year']}`："
            f"路径收益`{row['simple_year_path_return']:.2%}`，年内最低回撤`{row['min_drawdown_seen']:.2%}`，"
            f"平均暴露`{row['avg_exposure']:.2%}`，接受篮子`{row['accepted_signal_baskets']}`。"
        )

    lines.extend(["", "## 信号拒绝原因", ""])
    rejection = (
        decisions_df.filter(~pl.col("accepted"))
        .group_by(["scenario", "reject_reason"])
        .agg(pl.len().alias("rejected_count"))
        .sort(["scenario", "reject_reason"])
    )
    for row in rejection.iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` `{row['reject_reason']}`：拒绝`{row['rejected_count']}`个信号篮子。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果重叠上限能显著降低回撤但同步砍掉大部分收益，说明这条线的收益和风险来自同一类暴露，不能靠简单减仓变成优质策略。",
            "- 如果冷却机制改善有限，说明风险不是信号太密本身，而是下跌状态持续时的市场beta暴露。",
            "- 这一步仍不触发第78 A/B，也不接入正式股票策略。",
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
    """Run mechanical risk-budget pressure tests on the fixed market-down path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _stock_df, benchmark_df = load_panels()
    basket_daily, basket_horizon = load_base_outputs()
    signal_dates = basket_horizon.sort("signal_date")["signal_date"].to_list()
    trading_index = build_trading_index(benchmark_df)
    full_start = basket_daily["pnl_date"].min()
    full_end = basket_daily["pnl_date"].max()

    decision_frames: list[pl.DataFrame] = []
    equity_frames: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        accepted_dates, decisions = select_signal_dates(signal_dates, trading_index, scenario)
        decision_frames.append(decisions)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(
                basket_daily,
                benchmark_df,
                accepted_dates,
                cost_bps,
                scenario,
                full_start,
                full_end,
            )
            equity_frames.append(curve)
            summary_rows.append(summarize_curve(curve, basket_horizon, accepted_dates, scenario, cost_bps))

    decisions_df = pl.concat(decision_frames, how="vertical").sort(["scenario", "signal_date"])
    equity_df = pl.concat(equity_frames, how="vertical").sort(["roundtrip_cost_bps", "scenario", "pnl_date"])
    summary_df = pl.DataFrame(summary_rows).sort(["roundtrip_cost_bps", "scenario"])
    year_df = build_year_summary(equity_df, decisions_df)
    meta: dict[str, Any] = {
        "source_backtest_dir": str(BASE_BACKTEST_DIR),
        "feature": FEATURE,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "scenario_count": len(SCENARIOS),
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        "signal_basket_count": len(signal_dates),
        "full_start": str(full_start),
        "full_end": str(full_end),
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    decisions_path = OUTPUT_DIR / f"{PREFIX}_signal_decisions.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    equity_df.write_csv(equity_path)
    decisions_df.write_csv(decisions_path)
    year_df.write_csv(year_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        year_df,
        decisions_df,
        meta,
        {
            "summary": summary_path,
            "equity_curve": equity_path,
            "signal_decisions": decisions_path,
            "year_summary": year_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
