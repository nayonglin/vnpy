from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_market_down_long_only import INITIAL_EQUITY, TRADING_DAYS, to_float
from backtest_stock_range_reversion_market_down_merged_portfolio import (
    BUCKET,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    OUTPUT_DIR as MERGED_OUTPUT_DIR,
    PREFIX as MERGED_PREFIX,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_beta_residual_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_beta_residual_v1"
INPUT_EQUITY_PATH: Path = MERGED_OUTPUT_DIR / f"{MERGED_PREFIX}_equity_curve.csv"

PATH_SPECS: tuple[tuple[str, str, str], ...] = (
    ("strategy_net", "strategy_daily_ret", "组合净收益"),
    ("same_exposure_benchmark", "benchmark_active_daily_ret", "同暴露中证1000"),
    ("active_excess_net", "active_excess_daily_ret", "组合净收益-同暴露中证1000"),
    ("beta_residual_net", "beta_residual_daily_ret", "组合净收益-beta拟合市场项"),
    ("strategy_gross", "strategy_gross_daily_ret", "组合毛收益"),
)


def product_return(values: list[float]) -> float:
    """Compound a list of daily returns."""
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def safe_mean(values: list[float]) -> float:
    """Return mean for non-empty values."""
    return sum(values) / len(values) if values else 0.0


def safe_std(values: list[float]) -> float:
    """Return sample std for values."""
    if len(values) <= 1:
        return 0.0
    mean = safe_mean(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def regression_metrics(rows: pl.DataFrame, y_col: str, x_col: str, *, active_only: bool) -> dict[str, float | int]:
    """Run a simple one-factor OLS regression y = alpha + beta * x."""
    work = rows.select(["return_gross_exposure", y_col, x_col]).filter(
        pl.col(y_col).is_not_null() & pl.col(x_col).is_not_null()
    )
    if active_only:
        work = work.filter(pl.col("return_gross_exposure") > 0)
    x_values = [to_float(value) for value in work[x_col].to_list()]
    y_values = [to_float(value) for value in work[y_col].to_list()]
    n = len(x_values)
    if n <= 2:
        return {
            "n": n,
            "alpha_daily": 0.0,
            "alpha_annualized_simple": 0.0,
            "beta": 0.0,
            "corr": 0.0,
            "r_squared": 0.0,
            "beta_t_stat": 0.0,
            "residual_std_daily": 0.0,
        }

    x_mean = safe_mean(x_values)
    y_mean = safe_mean(y_values)
    x_dev = [value - x_mean for value in x_values]
    y_dev = [value - y_mean for value in y_values]
    ssx = sum(value * value for value in x_dev)
    ssy = sum(value * value for value in y_dev)
    cov = sum(x_dev[index] * y_dev[index] for index in range(n))
    beta = cov / ssx if ssx else 0.0
    alpha = y_mean - beta * x_mean
    corr = cov / sqrt(ssx * ssy) if ssx and ssy else 0.0
    residuals = [y_values[index] - alpha - beta * x_values[index] for index in range(n)]
    residual_std = safe_std(residuals)
    sse = sum(value * value for value in residuals)
    residual_var = sse / (n - 2) if n > 2 else 0.0
    beta_se = sqrt(residual_var / ssx) if ssx and residual_var >= 0 else 0.0
    beta_t = beta / beta_se if beta_se else 0.0
    return {
        "n": n,
        "alpha_daily": alpha,
        "alpha_annualized_simple": alpha * TRADING_DAYS,
        "beta": beta,
        "corr": corr,
        "r_squared": corr * corr,
        "beta_t_stat": beta_t,
        "residual_std_daily": residual_std,
    }


def build_equity_and_drawdown(returns: list[float]) -> tuple[list[float], list[float]]:
    """Build compounded equity and drawdown arrays."""
    equity_values: list[float] = []
    drawdown_values: list[float] = []
    equity = INITIAL_EQUITY
    peak = INITIAL_EQUITY
    for daily_ret in returns:
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        equity_values.append(equity)
        drawdown_values.append(equity / peak - 1.0 if peak else 0.0)
    return equity_values, drawdown_values


def max_drawdown_window(dates: list[Any], equity_values: list[float]) -> dict[str, Any]:
    """Return peak, trough, and recovery for the max drawdown window."""
    if not dates or not equity_values:
        return {
            "peak_date": None,
            "trough_date": None,
            "recovery_date": None,
            "peak_equity": INITIAL_EQUITY,
            "trough_equity": INITIAL_EQUITY,
            "max_drawdown": 0.0,
            "drawdown_days": 0,
            "recovery_days": None,
        }

    peak_index = 0
    running_peak_index = 0
    running_peak_equity = equity_values[0]
    trough_index = 0
    max_dd = 0.0
    for index, equity in enumerate(equity_values):
        if equity > running_peak_equity:
            running_peak_equity = equity
            running_peak_index = index
        dd = equity / running_peak_equity - 1.0 if running_peak_equity else 0.0
        if dd < max_dd:
            max_dd = dd
            peak_index = running_peak_index
            trough_index = index

    recovery_index: int | None = None
    peak_equity = equity_values[peak_index]
    for index in range(trough_index + 1, len(equity_values)):
        if equity_values[index] >= peak_equity:
            recovery_index = index
            break

    return {
        "peak_date": dates[peak_index],
        "trough_date": dates[trough_index],
        "recovery_date": dates[recovery_index] if recovery_index is not None else None,
        "peak_equity": peak_equity,
        "trough_equity": equity_values[trough_index],
        "max_drawdown": max_dd,
        "drawdown_days": trough_index - peak_index,
        "recovery_days": recovery_index - trough_index if recovery_index is not None else None,
    }


def add_residual_paths(cost_df: pl.DataFrame, beta_to_active_benchmark: float) -> pl.DataFrame:
    """Add active excess, beta residual, and compounded path columns for one cost."""
    work = cost_df.sort("date").with_columns(
        (pl.col("strategy_daily_ret") - pl.col("benchmark_active_daily_ret")).alias("active_excess_daily_ret"),
        (
            pl.col("strategy_daily_ret")
            - beta_to_active_benchmark * pl.col("benchmark_active_daily_ret")
        ).alias("beta_residual_daily_ret"),
    )
    exprs: list[pl.Series] = []
    for path_name, ret_col, _label in PATH_SPECS:
        returns = [to_float(value) for value in work[ret_col].to_list()]
        equity_values, drawdown_values = build_equity_and_drawdown(returns)
        exprs.append(pl.Series(f"{path_name}_equity", equity_values))
        exprs.append(pl.Series(f"{path_name}_drawdown", drawdown_values))
    return work.with_columns(exprs)


def summarize_path(cost_df: pl.DataFrame, cost_bps: float, path_name: str, ret_col: str, label: str) -> dict[str, Any]:
    """Summarize one compounded return path."""
    days = cost_df.height
    returns = [to_float(value) for value in cost_df[ret_col].to_list()]
    equity_values = [to_float(value) for value in cost_df[f"{path_name}_equity"].to_list()]
    drawdowns = [to_float(value) for value in cost_df[f"{path_name}_drawdown"].to_list()]
    daily_mean = safe_mean(returns)
    daily_std = safe_std(returns)
    active_rows = cost_df.filter(pl.col("return_gross_exposure") > 0)
    active_returns = [to_float(value) for value in active_rows[ret_col].to_list()]
    total_return = equity_values[-1] / INITIAL_EQUITY - 1 if equity_values else 0.0
    return {
        "roundtrip_cost_bps": cost_bps,
        "path": path_name,
        "path_label": label,
        "days": days,
        "final_equity": equity_values[-1] if equity_values else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (TRADING_DAYS / days) - 1
        if days and total_return > -1
        else 0.0,
        "max_drawdown": min(drawdowns) if drawdowns else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "daily_mean": daily_mean,
        "daily_std": daily_std,
        "active_day_win_rate": safe_mean([1.0 if value > 0 else 0.0 for value in active_returns])
        if active_returns
        else 0.0,
        "avg_gross_exposure": to_float(cost_df["return_gross_exposure"].mean()) if days else 0.0,
    }


def build_path_summaries(curves: pl.DataFrame) -> pl.DataFrame:
    """Build path-level summary table."""
    rows: list[dict[str, Any]] = []
    for cost_bps in sorted(curves["roundtrip_cost_bps"].unique().to_list()):
        cost_df = curves.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        for path_name, ret_col, label in PATH_SPECS:
            rows.append(summarize_path(cost_df, cost_bps, path_name, ret_col, label))
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "path"])


def build_regression_summary(source: pl.DataFrame) -> tuple[pl.DataFrame, dict[float, float]]:
    """Build regression metrics and return beta against same-exposure benchmark by cost."""
    rows: list[dict[str, Any]] = []
    beta_by_cost: dict[float, float] = {}
    for cost_bps in sorted(source["roundtrip_cost_bps"].unique().to_list()):
        cost_df = source.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        specs = (
            ("strategy_vs_raw_benchmark_all_days", "strategy_daily_ret", "benchmark_daily_ret", False),
            ("strategy_vs_raw_benchmark_active_days", "strategy_daily_ret", "benchmark_daily_ret", True),
            (
                "strategy_vs_same_exposure_benchmark_all_days",
                "strategy_daily_ret",
                "benchmark_active_daily_ret",
                False,
            ),
            (
                "strategy_vs_same_exposure_benchmark_active_days",
                "strategy_daily_ret",
                "benchmark_active_daily_ret",
                True,
            ),
            (
                "gross_strategy_vs_same_exposure_benchmark_all_days",
                "strategy_gross_daily_ret",
                "benchmark_active_daily_ret",
                False,
            ),
        )
        for name, y_col, x_col, active_only in specs:
            metrics = regression_metrics(cost_df, y_col, x_col, active_only=active_only)
            rows.append(
                {
                    "roundtrip_cost_bps": cost_bps,
                    "regression": name,
                    "y_col": y_col,
                    "x_col": x_col,
                    "active_only": active_only,
                    **metrics,
                }
            )
            if name == "strategy_vs_same_exposure_benchmark_all_days":
                beta_by_cost[cost_bps] = to_float(metrics["beta"])
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "regression"]), beta_by_cost


def build_augmented_curves(source: pl.DataFrame, beta_by_cost: dict[float, float]) -> pl.DataFrame:
    """Add residual paths to every cost scenario."""
    frames: list[pl.DataFrame] = []
    for cost_bps in sorted(source["roundtrip_cost_bps"].unique().to_list()):
        cost_df = source.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        beta = beta_by_cost[cost_bps]
        frames.append(add_residual_paths(cost_df, beta).with_columns(pl.lit(beta).alias("beta_to_active_benchmark")))
    return pl.concat(frames, how="vertical").sort(["roundtrip_cost_bps", "date"])


def build_drawdown_windows(curves: pl.DataFrame) -> pl.DataFrame:
    """Build max drawdown windows and strategy-window decomposition."""
    rows: list[dict[str, Any]] = []
    for cost_bps in sorted(curves["roundtrip_cost_bps"].unique().to_list()):
        cost_df = curves.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        dates = cost_df["date"].to_list()
        for path_name, ret_col, label in PATH_SPECS:
            equity_values = [to_float(value) for value in cost_df[f"{path_name}_equity"].to_list()]
            window = max_drawdown_window(dates, equity_values)
            segment = cost_df.filter(
                (pl.col("date") > window["peak_date"]) & (pl.col("date") <= window["trough_date"])
            )
            rows.append(
                {
                    "roundtrip_cost_bps": cost_bps,
                    "path": path_name,
                    "path_label": label,
                    **window,
                    "window_strategy_return": product_return(
                        [to_float(value) for value in segment["strategy_daily_ret"].to_list()]
                    ),
                    "window_same_exposure_benchmark_return": product_return(
                        [to_float(value) for value in segment["benchmark_active_daily_ret"].to_list()]
                    ),
                    "window_active_excess_return": product_return(
                        [to_float(value) for value in segment["active_excess_daily_ret"].to_list()]
                    ),
                    "window_beta_residual_return": product_return(
                        [to_float(value) for value in segment["beta_residual_daily_ret"].to_list()]
                    ),
                    "window_raw_benchmark_return": product_return(
                        [to_float(value) for value in segment["benchmark_daily_ret"].to_list()]
                    ),
                    "window_avg_gross_exposure": to_float(segment["return_gross_exposure"].mean())
                    if segment.height
                    else 0.0,
                }
            )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "path"])


def build_year_summary(curves: pl.DataFrame) -> pl.DataFrame:
    """Summarize annual returns for every path."""
    rows: list[dict[str, Any]] = []
    for cost_bps in sorted(curves["roundtrip_cost_bps"].unique().to_list()):
        cost_df = curves.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        years = sorted(cost_df["date"].dt.year().unique().to_list())
        for year in years:
            year_df = cost_df.filter(pl.col("date").dt.year() == year)
            for path_name, ret_col, label in PATH_SPECS:
                returns = [to_float(value) for value in year_df[ret_col].to_list()]
                rows.append(
                    {
                        "roundtrip_cost_bps": cost_bps,
                        "year": year,
                        "path": path_name,
                        "path_label": label,
                        "year_return": product_return(returns),
                        "avg_gross_exposure": to_float(year_df["return_gross_exposure"].mean())
                        if year_df.height
                        else 0.0,
                    }
                )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "path", "year"])


def write_report(
    summary_df: pl.DataFrame,
    regression_df: pl.DataFrame,
    drawdown_df: pl.DataFrame,
    year_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese beta/residual attribution report."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down beta/residual归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略版本，也不是市场对冲策略；只把第218阶段合并持仓baseline拆成市场暴露、同暴露基准和残差alpha。",
        f"- 固定口径：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}`，top quintile，固定持有`{HORIZON}`日。",
        f"- 输入曲线：`{INPUT_EQUITY_PATH}`。",
        "- `active_excess_net`为组合净收益减同暴露中证1000收益；`beta_residual_net`为组合净收益减回归拟合的市场项，均为归因口径。",
        "",
        "## 路径摘要",
        "",
    ]
    for cost_bps in sorted(summary_df["roundtrip_cost_bps"].unique().to_list()):
        lines.append(f"### 成本`{cost_bps:.0f}bp`")
        for row in summary_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("path").iter_rows(named=True):
            lines.append(
                f"- `{row['path']}`：期末权益`{row['final_equity']:.4f}`，"
                f"总收益`{row['total_return']:.2%}`，最大回撤`{row['max_drawdown']:.2%}`，"
                f"Sharpe `{row['sharpe']:.2f}`，活跃日胜率`{row['active_day_win_rate']:.2%}`。"
            )

    lines.extend(["", "## 回归归因", ""])
    for row in regression_df.iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['regression']}`："
            f"n=`{row['n']}`，beta=`{row['beta']:.3f}`，corr=`{row['corr']:.3f}`，"
            f"R2=`{row['r_squared']:.2%}`，日alpha=`{row['alpha_daily']:.4%}`。"
        )

    lines.extend(["", "## 最大回撤窗口", ""])
    for row in drawdown_df.filter(pl.col("path") == "strategy_net").sort("roundtrip_cost_bps").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` 组合净值最大回撤："
            f"peak=`{row['peak_date']}`，trough=`{row['trough_date']}`，"
            f"maxDD=`{row['max_drawdown']:.2%}`，窗口组合`{row['window_strategy_return']:.2%}`，"
            f"同暴露基准`{row['window_same_exposure_benchmark_return']:.2%}`，"
            f"active_excess`{row['window_active_excess_return']:.2%}`，"
            f"beta_residual`{row['window_beta_residual_return']:.2%}`，"
            f"原始中证1000`{row['window_raw_benchmark_return']:.2%}`。"
        )

    lines.extend(["", "## 压力年份", ""])
    for row in year_df.filter(pl.col("year").is_in([2018, 2022, 2024])).sort(
        ["roundtrip_cost_bps", "path", "year"]
    ).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['path']}` `{row['year']}`："
            f"收益`{row['year_return']:.2%}`，平均暴露`{row['avg_gross_exposure']:.2%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果残差路径明显好于组合净值，说明主要风险是市场beta预算问题，不该继续改股票超跌信号。",
            "- 如果残差路径仍有深回撤，说明横截面alpha本身在压力段塌陷，股票震荡路线不应组合化。",
            "- 本阶段不触发第78 A/B，也不接入正式股票策略。",
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
    """Run beta/residual attribution for the merged market-down baseline."""
    if not INPUT_EQUITY_PATH.exists():
        raise FileNotFoundError(f"Missing merged equity curve: {INPUT_EQUITY_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = pl.read_csv(INPUT_EQUITY_PATH, try_parse_dates=True).sort(["roundtrip_cost_bps", "date"])
    regression_df, beta_by_cost = build_regression_summary(source)
    curves = build_augmented_curves(source, beta_by_cost)
    summary_df = build_path_summaries(curves)
    drawdown_df = build_drawdown_windows(curves)
    year_df = build_year_summary(curves)

    meta = {
        "feature": FEATURE,
        "bucket": BUCKET,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "input_equity_path": str(INPUT_EQUITY_PATH),
        "date_min": str(curves["date"].min()),
        "date_max": str(curves["date"].max()),
        "cost_bps": sorted(curves["roundtrip_cost_bps"].unique().to_list()),
        "path_specs": [{"path": name, "return_col": ret_col, "label": label} for name, ret_col, label in PATH_SPECS],
        "beta_by_cost": {str(key): value for key, value in beta_by_cost.items()},
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    regression_path = OUTPUT_DIR / f"{PREFIX}_regression_summary.csv"
    curves_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    drawdown_path = OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    regression_df.write_csv(regression_path)
    curves.write_csv(curves_path)
    drawdown_df.write_csv(drawdown_path)
    year_df.write_csv(year_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        regression_df,
        drawdown_df,
        year_df,
        meta,
        {
            "summary": summary_path,
            "regression_summary": regression_path,
            "equity_curve": curves_path,
            "drawdown_windows": drawdown_path,
            "year_summary": year_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(regression_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
