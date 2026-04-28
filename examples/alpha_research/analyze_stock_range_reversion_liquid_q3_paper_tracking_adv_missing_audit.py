from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    ACCOUNT_SIZE_CNY,
    MAX_PARTICIPATION_ADV20,
    OUTPUT_DIR as PAPER_OUTPUT_DIR,
    PAPER_SCENARIO,
    PREFIX as PAPER_PREFIX,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_tracking_adv_missing_audit_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_tracking_adv_missing_audit_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "ML4Trading data quality validation",
        "https://ml4trading.io/docs/data/tutorials/04_data_quality/",
    ),
    (
        "Backtesting data quality can your data provider be trusted",
        "https://concretumgroup.com/backtesting-data-quality-can-your-data-provider-be-trusted/",
    ),
    (
        "XTrade-AI liquidity filter example",
        "https://xtrade-ai-framework.readthedocs.io/en/latest/user-guide/backtesting.html",
    ),
)


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def read_orders() -> pl.DataFrame:
    path = PAPER_OUTPUT_DIR / f"{PAPER_PREFIX}_paper_orders.csv"
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def build_stock_liquidity_frame(stock_df: pl.DataFrame) -> pl.DataFrame:
    wanted = [
        "datetime",
        "symbol",
        "code_name",
        "listing_days",
        "is_suspended",
        "is_st",
        "is_stock_type",
        "is_listed_status",
        "eligible_research_row",
        "eligible_component_row",
        "is_index_component",
        "trade_open",
        "trade_close",
        "turnover",
        "volume",
        "adv20_turnover",
        "adv20_volume",
    ]
    cols = [col for col in wanted if col in stock_df.columns]
    return (
        stock_df.select(cols)
        .rename({"datetime": "date"})
        .sort(["symbol", "date"])
        .with_columns(
            (pl.col("turnover").is_not_null() & (pl.col("turnover") > 0)).alias("has_positive_turnover"),
            (pl.col("volume").is_not_null() & (pl.col("volume") > 0)).alias("has_positive_volume"),
        )
        .with_columns(
            pl.col("has_positive_turnover")
            .cast(pl.Int32)
            .rolling_sum(window_size=20, min_samples=1)
            .over("symbol")
            .alias("turnover_valid_count_20"),
            pl.col("has_positive_volume")
            .cast(pl.Int32)
            .rolling_sum(window_size=20, min_samples=1)
            .over("symbol")
            .alias("volume_valid_count_20"),
            pl.col("turnover").rolling_mean(window_size=20, min_samples=1).over("symbol").alias(
                "turnover_ma20_min1"
            ),
            pl.col("turnover").rolling_mean(window_size=10, min_samples=1).over("symbol").alias(
                "turnover_ma10_min1"
            ),
            pl.col("turnover").rolling_mean(window_size=5, min_samples=1).over("symbol").alias(
                "turnover_ma5_min1"
            ),
        )
        .with_columns(
            pl.when(pl.col("adv20_turnover").is_not_null() & (pl.col("adv20_turnover") > 0))
            .then(pl.col("adv20_turnover"))
            .when(pl.col("turnover_ma20_min1").is_not_null() & (pl.col("turnover_ma20_min1") > 0))
            .then(pl.col("turnover_ma20_min1"))
            .when(pl.col("turnover_ma10_min1").is_not_null() & (pl.col("turnover_ma10_min1") > 0))
            .then(pl.col("turnover_ma10_min1"))
            .when(pl.col("turnover_ma5_min1").is_not_null() & (pl.col("turnover_ma5_min1") > 0))
            .then(pl.col("turnover_ma5_min1"))
            .otherwise(None)
            .alias("fallback_adv_turnover")
        )
    )


def classify_missing_adv(joined: pl.DataFrame) -> pl.DataFrame:
    return joined.with_columns(
        pl.when(pl.col("row_found").not_())
        .then(pl.lit("stock_row_missing"))
        .when(
            pl.col("audit_is_suspended").fill_null(False)
            | pl.col("audit_trade_open").is_null()
            | (pl.col("audit_trade_open") <= 0)
        )
        .then(pl.lit("not_tradeable_bar"))
        .when(pl.col("audit_adv20_turnover").is_not_null() & (pl.col("audit_adv20_turnover") > 0))
        .then(pl.lit("paper_join_or_parse_mismatch"))
        .when((pl.col("turnover_valid_count_20") >= 20) & (pl.col("turnover_ma20_min1") > 0))
        .then(pl.lit("adv_field_missing_full_20d_history"))
        .when((pl.col("turnover_valid_count_20") >= 5) & (pl.col("turnover_ma20_min1") > 0))
        .then(pl.lit("adv_field_missing_partial_history"))
        .when(pl.col("turnover").is_not_null() & (pl.col("turnover") > 0))
        .then(pl.lit("current_turnover_only"))
        .when(pl.col("listing_days").is_not_null() & (pl.col("listing_days") < 20))
        .then(pl.lit("new_listing_insufficient_history"))
        .when(pl.col("turnover_valid_count_20").fill_null(0) == 0)
        .then(pl.lit("no_recent_turnover_history"))
        .otherwise(pl.lit("adv_missing_unclassified"))
        .alias("missing_adv_class")
    )


def build_missing_audit(orders: pl.DataFrame, stock_liquidity: pl.DataFrame) -> pl.DataFrame:
    missing_orders = orders.filter(pl.col("blocked_reason") == "missing_adv20_turnover")
    joined = missing_orders.join(stock_liquidity, on=["date", "symbol"], how="left", suffix="_stock")
    for col_name in ["code_name_stock", "industry_stock", "is_suspended_stock"]:
        if col_name not in joined.columns:
            joined = joined.with_columns(pl.lit(None).alias(col_name))
    joined = joined.with_columns(
        (
            pl.col("trade_close_stock").is_not_null()
            | pl.col("trade_open_stock").is_not_null()
            | pl.col("turnover").is_not_null()
        ).alias("row_found"),
        pl.coalesce([pl.col("code_name"), pl.col("code_name_stock")]).alias("audit_code_name"),
        pl.coalesce([pl.col("industry"), pl.col("industry_stock")]).alias("audit_industry"),
        pl.coalesce([pl.col("is_suspended_stock"), pl.col("is_suspended")]).alias("audit_is_suspended"),
        pl.coalesce([pl.col("trade_open_stock"), pl.col("trade_open")]).alias("audit_trade_open"),
        pl.coalesce([pl.col("trade_close_stock"), pl.col("trade_close")]).alias("audit_trade_close"),
        pl.coalesce([pl.col("adv20_turnover_stock"), pl.col("adv20_turnover")]).alias("audit_adv20_turnover"),
    )
    classified = classify_missing_adv(joined)
    return (
        classified.with_columns(
            (MAX_PARTICIPATION_ADV20 * pl.col("fallback_adv_turnover") / ACCOUNT_SIZE_CNY).alias(
                "fallback_cap_weight"
            )
        )
        .with_columns(
            pl.min_horizontal("desired_weight", "fallback_cap_weight").fill_null(0.0).alias(
                "fallback_filled_weight"
            )
        )
        .with_columns(
            (pl.col("desired_weight") - pl.col("fallback_filled_weight")).clip(0.0, None).alias(
                "fallback_unfilled_weight"
            )
        )
        .with_columns(
            (pl.col("fallback_filled_weight") * ACCOUNT_SIZE_CNY).alias("fallback_filled_amount_cny"),
            (pl.col("fallback_unfilled_weight") * ACCOUNT_SIZE_CNY).alias("fallback_unfilled_amount_cny"),
            (pl.col("fallback_filled_weight") > 0).alias("fallback_has_any_fill"),
            (pl.col("fallback_filled_weight") >= pl.col("desired_weight") - 1e-12).alias("fallback_full_fill"),
        )
        .select(
            "date",
            "symbol",
            pl.col("audit_code_name").alias("code_name"),
            pl.col("audit_industry").alias("industry"),
            "side",
            "desired_weight",
            "desired_amount_cny",
            "prev_actual_weight",
            "target_weight",
            "missing_adv_class",
            "row_found",
            "listing_days",
            "audit_is_suspended",
            "is_st",
            "is_stock_type",
            "is_listed_status",
            "eligible_research_row",
            "eligible_component_row",
            "is_index_component",
            "audit_trade_open",
            "audit_trade_close",
            "turnover",
            "volume",
            "audit_adv20_turnover",
            "adv20_volume",
            "turnover_valid_count_20",
            "volume_valid_count_20",
            "turnover_ma20_min1",
            "turnover_ma10_min1",
            "turnover_ma5_min1",
            "fallback_adv_turnover",
            "fallback_cap_weight",
            "fallback_filled_weight",
            "fallback_unfilled_weight",
            "fallback_filled_amount_cny",
            "fallback_unfilled_amount_cny",
            "fallback_has_any_fill",
            "fallback_full_fill",
        )
        .sort(["date", "symbol", "side"])
    )


def build_class_summary(audit: pl.DataFrame) -> pl.DataFrame:
    return (
        audit.group_by("missing_adv_class")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("fallback_filled_weight").sum().alias("fallback_filled_weight_sum"),
            pl.col("fallback_unfilled_weight").sum().alias("fallback_unfilled_weight_sum"),
            pl.col("fallback_has_any_fill").sum().alias("fallback_any_fill_orders"),
            pl.col("fallback_full_fill").sum().alias("fallback_full_fill_orders"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
        )
        .with_columns(
            (pl.col("fallback_filled_weight_sum") / pl.col("desired_weight_sum")).alias(
                "fallback_weight_recovery_ratio"
            ),
            (pl.col("fallback_any_fill_orders") / pl.col("orders")).alias("fallback_any_fill_order_ratio"),
            (pl.col("fallback_full_fill_orders") / pl.col("orders")).alias("fallback_full_fill_order_ratio"),
        )
        .sort("desired_weight_sum", descending=True)
    )


def build_date_summary(audit: pl.DataFrame) -> pl.DataFrame:
    return (
        audit.group_by("date")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("fallback_filled_weight").sum().alias("fallback_filled_weight_sum"),
            pl.col("fallback_unfilled_weight").sum().alias("fallback_unfilled_weight_sum"),
        )
        .with_columns(
            (pl.col("fallback_filled_weight_sum") / pl.col("desired_weight_sum")).alias(
                "fallback_weight_recovery_ratio"
            )
        )
        .sort("date")
    )


def build_symbol_summary(audit: pl.DataFrame) -> pl.DataFrame:
    return (
        audit.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("orders"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col("side").eq("buy").sum().alias("buy_orders"),
            pl.col("side").eq("sell").sum().alias("sell_orders"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("fallback_filled_weight").sum().alias("fallback_filled_weight_sum"),
            pl.col("fallback_unfilled_weight").sum().alias("fallback_unfilled_weight_sum"),
            pl.col("missing_adv_class").mode().first().alias("main_missing_adv_class"),
            pl.col("listing_days").median().alias("median_listing_days"),
        )
        .with_columns(
            (pl.col("fallback_filled_weight_sum") / pl.col("desired_weight_sum")).alias(
                "fallback_weight_recovery_ratio"
            )
        )
        .sort(["desired_weight_sum", "orders"], descending=[True, True])
    )


def summarize_audit(audit: pl.DataFrame, orders: pl.DataFrame) -> dict[str, Any]:
    missing_weight = float(audit["desired_weight"].sum() or 0.0)
    fallback_filled = float(audit["fallback_filled_weight"].sum() or 0.0)
    total_desired = float(orders["desired_weight"].sum() or 0.0)
    total_filled = float(orders["filled_weight"].sum() or 0.0)
    return {
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "total_orders": orders.height,
        "missing_adv_orders": audit.height,
        "missing_adv_symbols": audit["symbol"].n_unique(),
        "missing_adv_first_date": audit["date"].min(),
        "missing_adv_last_date": audit["date"].max(),
        "missing_adv_weight_sum": missing_weight,
        "fallback_filled_weight_sum": fallback_filled,
        "fallback_unfilled_weight_sum": float(audit["fallback_unfilled_weight"].sum() or 0.0),
        "fallback_weight_recovery_ratio": fallback_filled / missing_weight if missing_weight > 0 else 0.0,
        "fallback_any_fill_orders": int(audit["fallback_has_any_fill"].sum() or 0),
        "fallback_full_fill_orders": int(audit["fallback_full_fill"].sum() or 0),
        "original_total_desired_weight": total_desired,
        "original_total_filled_weight": total_filled,
        "original_fill_ratio": total_filled / total_desired if total_desired > 0 else 1.0,
        "fallback_adjusted_total_filled_weight": total_filled + fallback_filled,
        "fallback_adjusted_fill_ratio": (total_filled + fallback_filled) / total_desired
        if total_desired > 0
        else 1.0,
    }


def write_report(
    summary: dict[str, Any],
    class_summary: pl.DataFrame,
    symbol_summary: pl.DataFrame,
    date_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    fallback_ratio = summary["fallback_weight_recovery_ratio"]
    continue_judgment = "是" if summary["missing_adv_orders"] > 0 else "否"
    continue_reason = (
        "ADV缺失是纸面跟踪最大阻断来源，且存在可量化的fallback恢复空间，值得继续做数据前置检查。"
        if continue_judgment == "是"
        else "当前没有ADV缺失阻断，暂不需要继续这个审计分支。"
    )
    lines = [
        "# 股票震荡纸面跟踪ADV缺失审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第250阶段纸面跟踪后的数据/执行审计；不新增信号、不调参数。",
        f"- 审计对象：`{PAPER_SCENARIO}`纸面订单中的`missing_adv20_turnover`阻断。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 数据质量资料反复强调成交量/成交额缺失会直接扭曲流动性和可成交性判断。",
        "- 因此本阶段不把缺ADV简单当作策略失败，也不直接乐观补齐，而是先分解来源并估算fallback恢复空间。",
        "- 可用于正式纸面跟踪的规则必须是前置质量标签，而不是事后为了改善净值而补数据。",
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
            f"- 缺ADV阻断订单`{summary['missing_adv_orders']}`行，涉及股票`{summary['missing_adv_symbols']}`只，时间范围`{summary['missing_adv_first_date']}`到`{summary['missing_adv_last_date']}`。",
            f"- 缺ADV阻断权重合计`{summary['missing_adv_weight_sum']:.4f}`，约占全部目标换仓权重`{pct(summary['missing_adv_weight_sum'] / summary['original_total_desired_weight'])}`。",
            f"- 若只用同日可见成交额滚动均值作fallback，最多可恢复缺ADV阻断权重的`{pct(fallback_ratio)}`。",
            f"- 原纸面填充率`{pct(summary['original_fill_ratio'])}`；fallback理论填充率可提升到`{pct(summary['fallback_adjusted_fill_ratio'])}`。",
            "- 直觉判断：这更像数据字段口径/历史覆盖问题，而不是涨跌停或停牌造成的真实不可交易；但fallback不能直接进入正式口径，必须先变成预注册的数据质量规则。",
            "",
            "## 缺失分类汇总",
            "",
            markdown_table(
                class_summary,
                [
                    "missing_adv_class",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "fallback_filled_weight_sum",
                    "fallback_unfilled_weight_sum",
                    "fallback_weight_recovery_ratio",
                    "fallback_any_fill_order_ratio",
                    "fallback_full_fill_order_ratio",
                    "first_date",
                    "last_date",
                ],
            ),
            "",
            "## 权重最大的缺ADV股票",
            "",
            markdown_table(
                symbol_summary,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "orders",
                    "buy_orders",
                    "sell_orders",
                    "desired_weight_sum",
                    "fallback_filled_weight_sum",
                    "fallback_unfilled_weight_sum",
                    "fallback_weight_recovery_ratio",
                    "main_missing_adv_class",
                    "first_date",
                    "last_date",
                    "median_listing_days",
                ],
                max_rows=40,
            ),
            "",
            "## 权重最大的缺ADV日期",
            "",
            markdown_table(
                date_summary.sort("desired_weight_sum", descending=True),
                [
                    "date",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "fallback_filled_weight_sum",
                    "fallback_unfilled_weight_sum",
                    "fallback_weight_recovery_ratio",
                ],
                max_rows=40,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只审计纸面订单阻断来源，不新增预测变量、不调信号阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：fallback只用于测量数据缺失的影响边界，没有改写纸面跟踪结果，也没有选择更优参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第250阶段显示ADV缺失是最大阻断来源，必须判断它是真流动性问题还是数据口径问题。",
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
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步应把数据质量前置检查写入纸面跟踪入口，并整理候选版本说明。",
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
    orders = read_orders()
    stock_df, _benchmark_df = load_panels()
    stock_liquidity = build_stock_liquidity_frame(stock_df)
    audit = build_missing_audit(orders, stock_liquidity)
    class_summary = build_class_summary(audit)
    date_summary = build_date_summary(audit)
    symbol_summary = build_symbol_summary(audit)
    summary = summarize_audit(audit, orders)
    paths = {
        "missing_adv_orders_audit": OUTPUT_DIR / f"{PREFIX}_missing_adv_orders_audit.csv",
        "class_summary": OUTPUT_DIR / f"{PREFIX}_class_summary.csv",
        "date_summary": OUTPUT_DIR / f"{PREFIX}_date_summary.csv",
        "symbol_summary": OUTPUT_DIR / f"{PREFIX}_symbol_summary.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    audit.write_csv(paths["missing_adv_orders_audit"])
    class_summary.write_csv(paths["class_summary"])
    date_summary.write_csv(paths["date_summary"])
    symbol_summary.write_csv(paths["symbol_summary"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "source_paper_output_dir": str(PAPER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "note": "Fallback ADV is diagnostic only. It is not written back into paper tracking results.",
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, class_summary, symbol_summary, date_summary, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
