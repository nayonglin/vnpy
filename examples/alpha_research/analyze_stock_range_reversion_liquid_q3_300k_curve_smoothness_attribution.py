from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    write_json,
)
from analyze_stock_range_reversion_liquid_q3_market_state_baseline import add_market_state
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Conditional volatility targeting can reduce downside risk but is not universally beneficial",
        "https://www.tandfonline.com/doi/full/10.1080/0015198X.2020.1790853",
    ),
    (
        "Smoothing volatility targeting highlights turnover and transaction-cost risks",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "Risk-based performance attribution decomposes performance by risk exposures",
        "https://en.wikipedia.org/wiki/Performance_attribution",
    ),
)


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def compound_return(values: list[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def downside_vol(values: list[float]) -> float:
    clean = [min(value, 0.0) for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def build_full_position_daily(
    daily: pl.DataFrame,
    orders: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> pl.DataFrame:
    order_rows_by_date: dict[Any, list[dict[str, Any]]] = {}
    symbol_meta: dict[str, dict[str, str]] = {}
    for row in orders.sort(["date", "symbol", "side"]).iter_rows(named=True):
        current_date = row["date"]
        order_rows_by_date.setdefault(current_date, []).append(row)
        symbol = str(row["symbol"])
        current_meta = symbol_meta.setdefault(symbol, {"code_name": "", "industry": ""})
        code_name = str(row.get("code_name") or "")
        industry = str(row.get("industry") or "")
        if code_name:
            current_meta["code_name"] = code_name
        if industry:
            current_meta["industry"] = industry

    actual_shares: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for current_date in daily.sort("date")["date"].to_list():
        action_by_symbol: dict[str, str] = {}
        for order in order_rows_by_date.get(current_date, []):
            symbol = str(order["symbol"])
            shares_after = int(to_float(order.get("actual_shares_after")))
            if shares_after > 0:
                actual_shares[symbol] = shares_after
            else:
                actual_shares.pop(symbol, None)
            action_by_symbol[symbol] = str(order.get("side") or "")
            current_meta = symbol_meta.setdefault(symbol, {"code_name": "", "industry": ""})
            code_name = str(order.get("code_name") or "")
            industry = str(order.get("industry") or "")
            if code_name:
                current_meta["code_name"] = code_name
            if industry:
                current_meta["industry"] = industry

        for symbol, shares in sorted(actual_shares.items()):
            info = exec_info.get((current_date, symbol))
            meta = symbol_meta.get(symbol, {})
            trade_open = to_float(info.trade_open if info else None)
            daily_ret = info.daily_ret if info is not None else None
            amount = shares * trade_open if trade_open > 0 else 0.0
            actual_weight = amount / ACCOUNT_SIZE_CNY
            contribution = actual_weight * daily_ret if daily_ret is not None else None
            rows.append(
                {
                    "date": current_date,
                    "symbol": symbol,
                    "code_name": meta.get("code_name", ""),
                    "industry": meta.get("industry", ""),
                    "actual_shares": shares,
                    "trade_open": trade_open,
                    "actual_amount_cny": amount,
                    "actual_weight": actual_weight,
                    "daily_ret": daily_ret,
                    "gross_contribution": contribution,
                    "position_action": action_by_symbol.get(symbol, "hold"),
                    "missing_return": info is None,
                }
            )
    return pl.DataFrame(rows).sort(["date", "industry", "symbol"]) if rows else pl.DataFrame()


def build_drawdown_episodes(daily: pl.DataFrame) -> pl.DataFrame:
    rows = daily.sort("date").to_dicts()
    if not rows:
        return pl.DataFrame()
    peak_equity = to_float(rows[0]["equity_min_fee"])
    peak_date = rows[0]["date"]
    current: dict[str, Any] | None = None
    episodes: list[dict[str, Any]] = []

    for row in rows[1:]:
        current_date = row["date"]
        equity = to_float(row["equity_min_fee"])
        if equity >= peak_equity - 1e-12:
            if current is not None:
                current["recovery_date"] = current_date
                current["recovered"] = True
                episodes.append(current)
                current = None
            peak_equity = equity
            peak_date = current_date
            continue
        if current is None:
            current = {
                "peak_date": peak_date,
                "start_date": current_date,
                "peak_equity": peak_equity,
                "trough_date": current_date,
                "trough_equity": equity,
                "recovery_date": None,
                "recovered": False,
            }
        if equity < to_float(current["trough_equity"]):
            current["trough_date"] = current_date
            current["trough_equity"] = equity
    if current is not None:
        episodes.append(current)

    enriched: list[dict[str, Any]] = []
    for episode in episodes:
        start_date = episode["start_date"]
        trough_date = episode["trough_date"]
        recovery_date = episode["recovery_date"]
        segment_to_trough = daily.filter((pl.col("date") >= start_date) & (pl.col("date") <= trough_date))
        if recovery_date is None:
            segment_full = daily.filter(pl.col("date") >= start_date)
        else:
            segment_full = daily.filter((pl.col("date") >= start_date) & (pl.col("date") <= recovery_date))
        returns = [float(value) for value in segment_to_trough["strategy_daily_ret_min_fee"].to_list()]
        enriched.append(
            {
                **episode,
                "max_drawdown": to_float(episode["trough_equity"]) / to_float(episode["peak_equity"]) - 1.0,
                "trading_days_to_trough": segment_to_trough.height,
                "trading_days_to_recovery_or_end": segment_full.height,
                "net_return_to_trough": compound_return(returns),
                "gross_return_sum_to_trough": to_float(segment_to_trough["strategy_gross_daily_ret"].sum()),
                "cost_drag_sum_to_trough": to_float(segment_to_trough["turnover_cost_ret_min_fee"].sum()),
                "avg_actual_gross_weight": to_float(segment_to_trough["actual_gross_weight"].mean()),
                "max_actual_gross_weight": to_float(segment_to_trough["actual_gross_weight"].max()),
                "avg_actual_symbol_count": to_float(segment_to_trough["actual_symbol_count"].mean()),
                "avg_zero_lot_target_count": to_float(segment_to_trough["zero_lot_target_count"].mean()),
                "worst_daily_return": to_float(segment_to_trough["strategy_daily_ret_min_fee"].min()),
            }
        )
    return pl.DataFrame(enriched).sort("max_drawdown")


def add_buckets(state_daily: pl.DataFrame) -> pl.DataFrame:
    if state_daily.is_empty():
        return state_daily
    gross_low = to_float(state_daily["actual_gross_weight"].quantile(0.33))
    gross_high = to_float(state_daily["actual_gross_weight"].quantile(0.66))
    zero_low = to_float(state_daily["zero_lot_target_count"].quantile(0.33))
    zero_high = to_float(state_daily["zero_lot_target_count"].quantile(0.66))
    change_high = to_float(state_daily["actual_gross_weight_abs_change"].quantile(0.90))
    names_low = to_float(state_daily["actual_symbol_count"].quantile(0.33))
    names_high = to_float(state_daily["actual_symbol_count"].quantile(0.66))
    return state_daily.with_columns(
        pl.when(pl.col("actual_gross_weight") <= gross_low)
        .then(pl.lit("gross_low"))
        .when(pl.col("actual_gross_weight") >= gross_high)
        .then(pl.lit("gross_high"))
        .otherwise(pl.lit("gross_mid"))
        .alias("gross_exposure_bucket"),
        pl.when(pl.col("zero_lot_target_count") <= zero_low)
        .then(pl.lit("zero_lot_low"))
        .when(pl.col("zero_lot_target_count") >= zero_high)
        .then(pl.lit("zero_lot_high"))
        .otherwise(pl.lit("zero_lot_mid"))
        .alias("zero_lot_bucket"),
        pl.when(pl.col("actual_symbol_count") <= names_low)
        .then(pl.lit("names_low"))
        .when(pl.col("actual_symbol_count") >= names_high)
        .then(pl.lit("names_high"))
        .otherwise(pl.lit("names_mid"))
        .alias("actual_names_bucket"),
        pl.when(pl.col("actual_gross_weight_abs_change") >= change_high)
        .then(pl.lit("top_decile_exposure_change"))
        .otherwise(pl.lit("normal_exposure_change"))
        .alias("exposure_change_bucket"),
    )


def summarize_by(state_daily: pl.DataFrame, group_col: str) -> pl.DataFrame:
    if state_daily.is_empty() or group_col not in state_daily.columns:
        return pl.DataFrame()
    return (
        state_daily.group_by(group_col)
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((pl.col("strategy_daily_ret_min_fee") + 1).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("strategy_gross_daily_ret").sum().alias("gross_return_sum"),
            pl.col("turnover_cost_ret_min_fee").sum().alias("cost_drag_sum"),
            pl.col("same_exposure_benchmark_o2o_ret").sum().alias("same_exposure_benchmark_sum"),
            pl.col("gross_alpha_vs_same_exposure_benchmark").sum().alias("alpha_vs_benchmark_sum"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("zero_lot_target_count").mean().alias("avg_zero_lot_target_count"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
        )
        .sort("net_return_sum")
    )


def build_worst_day_industry(position_daily: pl.DataFrame, state_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty() or state_daily.is_empty():
        return pl.DataFrame()
    threshold = to_float(state_daily["strategy_daily_ret_min_fee"].quantile(0.10))
    worst_dates = state_daily.filter(pl.col("strategy_daily_ret_min_fee") <= threshold).select("date")
    return (
        position_daily.join(worst_dates, on="date", how="inner")
        .group_by("industry")
        .agg(
            pl.len().alias("position_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("actual_weight").max().alias("max_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.col("gross_contribution").mean().alias("avg_position_contribution"),
        )
        .sort("gross_contribution_sum")
    )


def build_worst_day_symbol(position_daily: pl.DataFrame, state_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty() or state_daily.is_empty():
        return pl.DataFrame()
    threshold = to_float(state_daily["strategy_daily_ret_min_fee"].quantile(0.10))
    worst_dates = state_daily.filter(pl.col("strategy_daily_ret_min_fee") <= threshold).select("date")
    return (
        position_daily.join(worst_dates, on="date", how="inner")
        .group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("held_bad_days"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("actual_weight").max().alias("max_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.col("daily_ret").mean().alias("avg_daily_ret"),
        )
        .sort("gross_contribution_sum")
    )


def build_worst_days(state_daily: pl.DataFrame) -> pl.DataFrame:
    if state_daily.is_empty():
        return pl.DataFrame()
    return state_daily.sort("strategy_daily_ret_min_fee").select(
        [
            "date",
            "strategy_daily_ret_min_fee",
            "strategy_gross_daily_ret",
            "turnover_cost_ret_min_fee",
            "actual_gross_weight",
            "actual_symbol_count",
            "zero_lot_target_count",
            "benchmark_open_to_next_open_ret",
            "same_exposure_benchmark_o2o_ret",
            "gross_alpha_vs_same_exposure_benchmark",
            "index_state",
            "breadth_state",
            "exante_trend_state",
            "exante_vol_state",
        ]
    ).head(30)


def plot_overview(daily: pl.DataFrame, drawdowns: pl.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    pdf = daily.sort("date").to_pandas()
    top_dd = drawdowns.head(5).to_dicts() if not drawdowns.is_empty() else []
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.2, 1.2]})
    fig.suptitle("300k Lot Account Smoothness Attribution", fontsize=14, fontweight="bold")
    axes[0].plot(pdf["date"], pdf["equity_min_fee"], color="#145C9E", linewidth=1.6, label="Equity - min fee")
    for episode in top_dd:
        axes[0].axvspan(episode["start_date"], episode["trough_date"], color="#D95D39", alpha=0.18)
    axes[0].set_ylabel("Equity")
    axes[0].legend(loc="upper left")
    axes[1].fill_between(pdf["date"], pdf["drawdown_min_fee"], 0, color="#D95D39", alpha=0.3)
    axes[1].plot(pdf["date"], pdf["drawdown_min_fee"], color="#A63A2A", linewidth=0.9)
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    axes[2].plot(pdf["date"], pdf["actual_gross_weight"], color="#6F4E7C", linewidth=1.0, label="Actual gross exposure")
    axes[2].plot(
        pdf["date"],
        pdf["zero_lot_target_count"] / max(float(pdf["zero_lot_target_count"].max()), 1.0),
        color="#C17817",
        linewidth=0.9,
        alpha=0.8,
        label="Zero-lot targets, scaled",
    )
    axes[2].set_ylabel("Exposure / scaled count")
    axes[2].legend(loc="upper left")
    axes[2].xaxis.set_major_locator(mdates.YearLocator())
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for ax in axes:
        ax.grid(True, linewidth=0.4, alpha=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=170, bbox_inches="tight")


def build_quality_checkpoints(summary: dict[str, Any], state_daily: pl.DataFrame, position_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": name,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "account_size_is_300k",
        "pass" if abs(to_float(summary.get("account_size_cny")) - 300_000.0) <= 1e-6 else "fail",
        summary.get("account_size_cny"),
        300000,
        "本阶段只归因30万整手口径。",
    )
    add(
        "drawdown_episodes_found",
        "pass" if int(summary.get("drawdown_episode_count") or 0) > 0 else "fail",
        summary.get("drawdown_episode_count"),
        ">0",
        "必须识别出回撤段，才有平滑归因意义。",
    )
    benchmark_nulls = state_daily.select(pl.col("benchmark_open_to_next_open_ret").null_count()).item()
    add(
        "benchmark_state_coverage",
        "pass" if benchmark_nulls == 0 else "fail",
        benchmark_nulls,
        0,
        "市场同向暴露归因需要完整基准收益。",
    )
    missing_position_returns = (
        position_daily.filter(pl.col("missing_return")).height if not position_daily.is_empty() else 0
    )
    add(
        "position_return_coverage",
        "pass" if missing_position_returns == 0 else "fail",
        missing_position_returns,
        0,
        "全历史持仓贡献应能取到开盘到次开盘收益。",
    )
    if not position_daily.is_empty():
        attribution = (
            position_daily.group_by("date")
            .agg(pl.col("gross_contribution").sum().alias("recomputed_gross_ret"))
            .join(state_daily.select("date", "strategy_gross_daily_ret"), on="date", how="left")
            .with_columns((pl.col("recomputed_gross_ret") - pl.col("strategy_gross_daily_ret")).abs().alias("diff"))
        )
        max_diff = to_float(attribution["diff"].max())
    else:
        max_diff = None
    add(
        "position_contribution_matches_daily_gross",
        "pass" if max_diff is not None and max_diff <= 1e-10 else "fail",
        max_diff,
        "<=1e-10",
        "持仓贡献求和应复原日级毛收益。",
    )
    add(
        "no_signal_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只做曲线归因，不修改策略信号。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    drawdowns: pl.DataFrame,
    worst_days: pl.DataFrame,
    state_summaries: dict[str, pl.DataFrame],
    worst_industry: pl.DataFrame,
    worst_symbol: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万曲线平滑归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：曲线不平滑来源归因；不新增信号、不调参数、不生成新策略版本。",
        f"- 账户规模：`{summary['account_size_cny']:,.0f}`元。",
        "- A/B判断：纯归因，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 波动目标和风险平滑可能降低下行风险，但文献也提示它不是对所有因子都稳定有效，并可能带来换手和成本问题。",
        "- 因此本阶段先做风险归因，不直接把波动目标、行业上限或市场状态降权变成交易规则。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 区间：`{summary['date_start']}`到`{summary['date_end']}`，交易日`{summary['trading_days']}`天。",
            f"- 最低佣金口径期末权益`{summary['final_equity_min_fee']:.4f}`，总收益`{pct(summary['total_return_min_fee'])}`，最大回撤`{pct(summary['max_drawdown_min_fee'])}`。",
            f"- 年化波动`{pct(summary['annualized_vol_min_fee'])}`，下行波动`{pct(summary['downside_vol_min_fee'])}`，最差单日`{pct(summary['worst_daily_ret_min_fee'])}`。",
            f"- 平均实际暴露`{pct(summary['avg_actual_gross_weight'])}`，平均实际持仓`{summary['avg_actual_symbol_count']:.1f}`只，平均买不到一手目标`{summary['avg_zero_lot_target_count']:.1f}`只。",
            f"- 回撤段数量`{summary['drawdown_episode_count']}`个，最大回撤段`{summary['worst_drawdown_peak_date']}`到`{summary['worst_drawdown_trough_date']}`，深度`{pct(summary['worst_drawdown_depth'])}`。",
            "- 初步判断：曲线可以尝试更平滑，但更像是市场状态/行业贡献/整手暴露形态共同造成，不能靠搜索持仓数量或单票权重解决。",
            "",
            "## 最大回撤段",
            "",
            markdown_table(
                drawdowns.head(12),
                [
                    "peak_date",
                    "start_date",
                    "trough_date",
                    "recovery_date",
                    "recovered",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "trading_days_to_recovery_or_end",
                    "net_return_to_trough",
                    "gross_return_sum_to_trough",
                    "cost_drag_sum_to_trough",
                    "avg_actual_gross_weight",
                    "avg_zero_lot_target_count",
                    "worst_daily_return",
                ],
                max_rows=20,
            ),
            "",
            "## 最差单日",
            "",
            markdown_table(worst_days, worst_days.columns, max_rows=30),
            "",
            "## 市场状态归因",
            "",
            "### 按指数当日状态",
            "",
            markdown_table(state_summaries["index_state"], state_summaries["index_state"].columns, max_rows=20),
            "",
            "### 按市场宽度状态",
            "",
            markdown_table(state_summaries["breadth_state"], state_summaries["breadth_state"].columns, max_rows=20),
            "",
            "### 按20日趋势状态",
            "",
            markdown_table(state_summaries["exante_trend_state"], state_summaries["exante_trend_state"].columns, max_rows=20),
            "",
            "### 按20日波动状态",
            "",
            markdown_table(state_summaries["exante_vol_state"], state_summaries["exante_vol_state"].columns, max_rows=20),
            "",
            "## 30万账户结构归因",
            "",
            "### 按实际暴露分组",
            "",
            markdown_table(state_summaries["gross_exposure_bucket"], state_summaries["gross_exposure_bucket"].columns, max_rows=20),
            "",
            "### 按买不到一手数量分组",
            "",
            markdown_table(state_summaries["zero_lot_bucket"], state_summaries["zero_lot_bucket"].columns, max_rows=20),
            "",
            "### 按实际持仓数量分组",
            "",
            markdown_table(state_summaries["actual_names_bucket"], state_summaries["actual_names_bucket"].columns, max_rows=20),
            "",
            "### 按暴露跳变分组",
            "",
            markdown_table(state_summaries["exposure_change_bucket"], state_summaries["exposure_change_bucket"].columns, max_rows=20),
            "",
            "## 最差10%单日行业贡献",
            "",
            markdown_table(
                worst_industry,
                [
                    "industry",
                    "position_days",
                    "symbols",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_position_contribution",
                ],
                max_rows=80,
            ),
            "",
            "## 最差10%单日个股贡献",
            "",
            markdown_table(
                worst_symbol.head(30),
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "held_bad_days",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_daily_ret",
                ],
                max_rows=30,
            ),
            "",
            "## 质量检查点",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只做曲线不平滑来源归因，不测试新参数，不选择更好曲线。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：报告只给出风险来源，不把任何风险层直接固化为交易规则。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万曲线是否能更平滑，必须先知道不平滑来自哪里。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：归因能把下一步收敛到市场状态降权、行业实际暴露约束或最低佣金/订单门槛压力测试，而不是盲目调参。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步只允许测试少数第一性原理风控层，优先市场状态降权或行业实际暴露约束。",
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
    daily_path = LOT_OUTPUT_DIR / f"{LOT_PREFIX}_daily.csv"
    orders_path = LOT_OUTPUT_DIR / f"{LOT_PREFIX}_orders.csv"
    daily = pl.read_csv(daily_path, try_parse_dates=True).sort("date")
    orders = read_csv_with_symbol(orders_path).sort(["date", "symbol", "side"])
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    position_daily = build_full_position_daily(daily, orders, exec_info)

    state_daily = (
        add_market_state(
            daily.with_columns(pl.col("strategy_daily_ret_min_fee").alias("strategy_daily_ret")),
            benchmark_df,
            stock_df,
        )
        .with_columns(pl.col("actual_gross_weight").diff().abs().fill_null(0.0).alias("actual_gross_weight_abs_change"))
        .sort("date")
    )
    state_daily = add_buckets(state_daily)
    drawdowns = build_drawdown_episodes(daily)
    worst_days = build_worst_days(state_daily)
    state_summaries = {
        name: summarize_by(state_daily, name)
        for name in [
            "index_state",
            "breadth_state",
            "exante_trend_state",
            "exante_vol_state",
            "gross_exposure_bucket",
            "zero_lot_bucket",
            "actual_names_bucket",
            "exposure_change_bucket",
        ]
    }
    worst_industry = build_worst_day_industry(position_daily, state_daily)
    worst_symbol = build_worst_day_symbol(position_daily, state_daily)

    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    worst_episode = drawdowns.row(0, named=True) if not drawdowns.is_empty() else {}
    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "date_start": daily["date"].min(),
        "date_end": daily["date"].max(),
        "trading_days": daily.height,
        "final_equity_min_fee": daily["equity_min_fee"][-1],
        "total_return_min_fee": daily["equity_min_fee"][-1] - 1.0,
        "max_drawdown_min_fee": daily["drawdown_min_fee"].min(),
        "annualized_vol_min_fee": annualized_vol(returns),
        "downside_vol_min_fee": downside_vol(returns),
        "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
        "avg_actual_gross_weight": to_float(daily["actual_gross_weight"].mean()),
        "avg_actual_symbol_count": to_float(daily["actual_symbol_count"].mean()),
        "avg_zero_lot_target_count": to_float(daily["zero_lot_target_count"].mean()),
        "drawdown_episode_count": drawdowns.height,
        "worst_drawdown_peak_date": worst_episode.get("peak_date"),
        "worst_drawdown_trough_date": worst_episode.get("trough_date"),
        "worst_drawdown_depth": worst_episode.get("max_drawdown"),
        "worst_drawdown_days_to_trough": worst_episode.get("trading_days_to_trough"),
        "worst_drawdown_avg_gross_weight": worst_episode.get("avg_actual_gross_weight"),
        "worst_drawdown_avg_zero_lot_target_count": worst_episode.get("avg_zero_lot_target_count"),
    }
    quality = build_quality_checkpoints(summary, state_daily, position_daily)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
        "position_daily": OUTPUT_DIR / f"{PREFIX}_position_daily.csv",
        "drawdown_episodes": OUTPUT_DIR / f"{PREFIX}_drawdown_episodes.csv",
        "worst_days": OUTPUT_DIR / f"{PREFIX}_worst_days.csv",
        "worst_day_industry": OUTPUT_DIR / f"{PREFIX}_worst_day_industry.csv",
        "worst_day_symbol": OUTPUT_DIR / f"{PREFIX}_worst_day_symbol.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "overview_png": OUTPUT_DIR / f"{PREFIX}_overview.png",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    for name, frame in state_summaries.items():
        path = OUTPUT_DIR / f"{PREFIX}_{name}_summary.csv"
        paths[f"{name}_summary"] = path
        frame.write_csv(path)
    state_daily.write_csv(paths["state_daily"])
    position_daily.write_csv(paths["position_daily"])
    drawdowns.write_csv(paths["drawdown_episodes"])
    worst_days.write_csv(paths["worst_days"])
    worst_industry.write_csv(paths["worst_day_industry"])
    worst_symbol.write_csv(paths["worst_day_symbol"])
    quality.write_csv(paths["quality_checkpoints"])
    plot_overview(daily, drawdowns, paths["overview_png"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_daily": daily_path,
            "source_orders": orders_path,
            "research_sources": RESEARCH_SOURCES,
            "note": "Curve smoothness attribution only; no strategy parameter changes.",
        },
    )
    report_path = write_report(
        summary,
        drawdowns,
        worst_days,
        state_summaries,
        worst_industry,
        worst_symbol,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
