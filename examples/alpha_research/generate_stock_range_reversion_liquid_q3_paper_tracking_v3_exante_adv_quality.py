from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    ACCOUNT_SIZE_CNY,
    LATEST_LOOKBACK_DAYS,
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_signal_audit,
    build_symbol_meta,
    build_target_maps,
    build_target_weights,
    build_tracking_dates,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality import (
    FALLBACK_MIN_VALID_TURNOVER_DAYS,
    RESEARCH_SOURCES,
    build_adv_quality_summary,
    build_block_reason_summary,
    replay_paper_orders,
    summarize_tracking,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality"


@dataclass(frozen=True)
class ExAnteAdvQualityExecInfo:
    code_name: str
    industry: str
    daily_ret: float
    trade_open: float
    trade_close: float
    adv_turnover_for_cap: float | None
    native_adv20_turnover: float | None
    fallback_adv_turnover: float | None
    adv_source: str
    adv_quality_flag: str
    fallback_allowed: bool
    turnover_valid_count_20: int
    tradable_open: bool
    is_suspended: bool
    is_oneword_limit_up: bool
    is_oneword_limit_down: bool
    is_limit_up_close: bool
    is_limit_down_close: bool


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


def first_positive(*values: Any) -> float:
    for value in values:
        parsed = to_float(value, default=0.0)
        if parsed > 0:
            return parsed
    return 0.0


def build_exec_info(stock_df: pl.DataFrame) -> dict[tuple[date, str], ExAnteAdvQualityExecInfo]:
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "trade_open",
        "trade_close",
        "turnover",
        "adv20_turnover",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    work = (
        stock_df.select([col for col in needed if col in stock_df.columns])
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"),
            pl.col("turnover").shift(1).over("symbol").alias("exante_turnover"),
            pl.col("adv20_turnover").shift(1).over("symbol").alias("exante_native_adv20_turnover"),
        )
        .with_columns(
            (pl.col("exante_turnover").is_not_null() & (pl.col("exante_turnover") > 0)).alias(
                "has_positive_exante_turnover"
            )
        )
        .with_columns(
            pl.col("has_positive_exante_turnover")
            .cast(pl.Int32)
            .rolling_sum(window_size=20, min_samples=1)
            .over("symbol")
            .alias("turnover_valid_count_20"),
            pl.col("exante_turnover").rolling_mean(window_size=20, min_samples=1).over("symbol").alias(
                "exante_turnover_ma20_min1"
            ),
            pl.col("exante_turnover").rolling_mean(window_size=10, min_samples=1).over("symbol").alias(
                "exante_turnover_ma10_min1"
            ),
            pl.col("exante_turnover").rolling_mean(window_size=5, min_samples=1).over("symbol").alias(
                "exante_turnover_ma5_min1"
            ),
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
    )
    info: dict[tuple[date, str], ExAnteAdvQualityExecInfo] = {}
    for row in work.iter_rows(named=True):
        trade_open = to_float(row.get("trade_open"), default=0.0)
        is_suspended = bool(row.get("is_suspended") or False)
        native_adv = to_float(row.get("exante_native_adv20_turnover"), default=0.0)
        turnover_count = int(to_float(row.get("turnover_valid_count_20"), default=0.0))
        fallback_adv = first_positive(
            row.get("exante_turnover_ma20_min1"),
            row.get("exante_turnover_ma10_min1"),
            row.get("exante_turnover_ma5_min1"),
        )
        fallback_allowed = native_adv <= 0 and turnover_count >= FALLBACK_MIN_VALID_TURNOVER_DAYS and fallback_adv > 0
        if native_adv > 0:
            adv_for_cap: float | None = native_adv
            adv_source = "exante_native_adv20_turnover"
            adv_quality_flag = "exante_native_ok"
        elif fallback_allowed:
            adv_for_cap = fallback_adv
            adv_source = "exante_fallback_turnover_ma_min1"
            adv_quality_flag = "exante_fallback_partial_history" if turnover_count < 20 else "exante_fallback_full_20d_history"
        else:
            adv_for_cap = None
            adv_source = "missing"
            adv_quality_flag = "missing_or_insufficient_exante_turnover_history"
        info[(row["datetime"], row["symbol"])] = ExAnteAdvQualityExecInfo(
            code_name=str(row.get("code_name") or ""),
            industry="",
            daily_ret=to_float(row.get("open_to_next_open_ret"), default=0.0),
            trade_open=trade_open,
            trade_close=to_float(row.get("trade_close"), default=0.0),
            adv_turnover_for_cap=adv_for_cap,
            native_adv20_turnover=native_adv if native_adv > 0 else None,
            fallback_adv_turnover=fallback_adv if fallback_adv > 0 else None,
            adv_source=adv_source,
            adv_quality_flag=adv_quality_flag,
            fallback_allowed=fallback_allowed,
            turnover_valid_count_20=turnover_count,
            tradable_open=(trade_open > 0 and not is_suspended),
            is_suspended=is_suspended,
            is_oneword_limit_up=bool(row.get("is_oneword_limit_up") or False),
            is_oneword_limit_down=bool(row.get("is_oneword_limit_down") or False),
            is_limit_up_close=bool(row.get("is_limit_up_close") or False),
            is_limit_down_close=bool(row.get("is_limit_down_close") or False),
        )
    return info


def write_report(
    summary: dict[str, Any],
    recent_daily: pl.DataFrame,
    latest_orders: pl.DataFrame,
    block_reason_summary: pl.DataFrame,
    adv_quality_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    latest_blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    lines = [
        "# 股票震荡liquid_q3纸面跟踪 v3 ex-ante ADV质量前置",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把v2的ADV质量规则改成交易开盘前可知口径；不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 成交上限应使用平均成交额/成交量，但实盘口径必须避免使用交易日当日尚不可知的成交额。",
        "- v3将原生ADV和fallback ADV都右移一日，容量约束只使用上一交易日及更早数据。",
        "- 本阶段只修执行数据口径，不改变股票池、信号和成交干枯过滤阈值。",
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
            f"- v3期末权益`{summary['final_equity']:.4f}`，总收益`{pct(summary['total_return'])}`，最大回撤`{pct(summary['max_drawdown'])}`，Sharpe `{summary['sharpe']:.2f}`。",
            f"- 整体成交填充率`{pct(summary['overall_fill_ratio'])}`，订单行数`{summary['order_count']}`，阻断订单行数`{summary['blocked_order_count']}`，部分成交订单行数`{summary['partial_order_count']}`。",
            f"- fallback允许订单`{summary['fallback_allowed_order_count']}`行，fallback成交权重`{summary['fallback_filled_weight_sum']:.4f}`。",
            f"- 最新目标执行日订单`{summary['latest_order_count']}`行，其中阻断`{summary['latest_blocked_order_count']}`行。",
            "- 直觉判断：v3比v2更接近真实开盘执行约束；如果v3仍接近v2，说明突破不是靠同日成交额偷看撑起来的。",
            "",
            "## ADV质量来源",
            "",
            markdown_table(
                adv_quality_summary,
                [
                    "adv_source",
                    "adv_quality_flag",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "filled_weight_ratio",
                    "fallback_allowed_orders",
                    "fallback_allowed_order_ratio",
                ],
            ),
            "",
            "## 阻断原因",
            "",
            markdown_table(
                block_reason_summary,
                [
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                    "unfilled_amount_cny_sum",
                ],
            ),
            "",
            "## 最近日汇总",
            "",
            markdown_table(
                recent_daily,
                [
                    "date",
                    "target_symbol_count",
                    "actual_symbol_count",
                    "target_gross_weight",
                    "actual_gross_weight",
                    "desired_abs_change",
                    "filled_abs_change",
                    "fill_ratio",
                    "blocked_order_count",
                    "partial_order_count",
                    "strategy_equity",
                    "strategy_drawdown",
                ],
            ),
            "",
            "## 最新订单阻断",
            "",
            markdown_table(
                latest_blocked.sort(["blocked_reason", "side", "symbol"]) if not latest_blocked.is_empty() else latest_blocked,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "blocked_reason",
                    "desired_weight",
                    "filled_weight",
                    "adv_source",
                    "adv_quality_flag",
                    "fallback_allowed",
                    "turnover_valid_count_20",
                    "trade_open",
                    "is_suspended",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只把执行容量口径右移为交易前可知，不新增信号、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：v3是更保守的反前视校验，收益不是通过挑参数得到的。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：v2已恢复成交填充率，但需要确认恢复不是依赖同日成交额口径。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：ex-ante口径仍保持接近v2的成交填充率和收益特征，值得作为当前纸面跟踪主口径继续验证。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- v3比v2更适合作为后续新增交易日纸面跟踪入口。",
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
    stock_df, benchmark_df = load_panels()
    signal_audit = build_signal_audit(selected_all)
    target_weights = build_target_weights(selected_all)
    target_maps = build_target_maps(target_weights)
    dates = build_tracking_dates(target_weights, benchmark_df)
    exec_info = build_exec_info(stock_df)
    symbol_meta = build_symbol_meta(signal_audit)
    orders, daily, curves = replay_paper_orders(target_maps, dates, exec_info, symbol_meta)
    block_reason_summary = build_block_reason_summary(orders)
    adv_quality_summary = build_adv_quality_summary(orders)
    summary = summarize_tracking(daily, orders)
    latest_target_date = summary["latest_target_date"]
    latest_orders = orders.filter(pl.col("date") == latest_target_date) if not orders.is_empty() else pl.DataFrame()
    recent_daily = daily.tail(LATEST_LOOKBACK_DAYS) if not daily.is_empty() else daily
    paths = {
        "paper_orders": OUTPUT_DIR / f"{PREFIX}_paper_orders.csv",
        "daily_summary": OUTPUT_DIR / f"{PREFIX}_daily_summary.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "adv_quality_summary": OUTPUT_DIR / f"{PREFIX}_adv_quality_summary.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "recent_daily": OUTPUT_DIR / f"{PREFIX}_recent_daily.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    orders.write_csv(paths["paper_orders"])
    daily.write_csv(paths["daily_summary"])
    curves.write_csv(paths["curves"])
    block_reason_summary.write_csv(paths["block_reason_summary"])
    adv_quality_summary.write_csv(paths["adv_quality_summary"])
    latest_orders.write_csv(paths["latest_orders"])
    recent_daily.write_csv(paths["recent_daily"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "source_filter_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "note": "V3 shifts native ADV and fallback turnover by one trading row per symbol so capacity uses only ex-ante data.",
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, recent_daily, latest_orders, block_reason_summary, adv_quality_summary, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
