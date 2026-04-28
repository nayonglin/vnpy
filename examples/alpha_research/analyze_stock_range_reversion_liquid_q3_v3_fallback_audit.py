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
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality import (
    FALLBACK_MIN_VALID_TURNOVER_DAYS,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import (
    OUTPUT_DIR as V3_OUTPUT_DIR,
    PREFIX as V3_PREFIX,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_v3_fallback_audit_2018_2026"
).expanduser().resolve()
PREFIX = "stock_range_reversion_liquid_q3_v3_fallback_audit_v1"

SAMPLE_PER_QUALITY_FLAG = 12
RECOMPUTE_TOLERANCE = 1e-6

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    ("Look-Ahead Bias in Rolling Window Features", "https://www.mhtechin.com/support/look-ahead-bias-in-rolling-window-features/"),
    ("Analyzing Alpha look-ahead bias", "https://analyzingalpha.com/look-ahead-bias"),
    ("Backtesting pitfalls", "https://foxholm.com/q/concepts/backtesting-pitfalls/"),
)


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


def first_positive_expr(cols: list[str]) -> pl.Expr:
    expr: pl.Expr = pl.lit(None, dtype=pl.Float64)
    for col in reversed(cols):
        expr = pl.when(pl.col(col).is_not_null() & (pl.col(col) > 0)).then(pl.col(col)).otherwise(expr)
    return expr


def build_exante_liquidity(stock_df: pl.DataFrame) -> pl.DataFrame:
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "turnover",
        "adv20_turnover",
        "volume",
        "trade_open",
        "trade_close",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
    ]
    work = (
        stock_df.select([col for col in needed if col in stock_df.columns])
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("datetime").shift(1).over("symbol").alias("prev_trade_date"),
            pl.col("turnover").shift(1).over("symbol").alias("exante_turnover"),
            pl.col("volume").shift(1).over("symbol").alias("exante_volume"),
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
            .alias("recomputed_turnover_valid_count_20"),
            pl.col("exante_turnover").rolling_mean(window_size=20, min_samples=1).over("symbol").alias(
                "recomputed_exante_turnover_ma20_min1"
            ),
            pl.col("exante_turnover").rolling_mean(window_size=10, min_samples=1).over("symbol").alias(
                "recomputed_exante_turnover_ma10_min1"
            ),
            pl.col("exante_turnover").rolling_mean(window_size=5, min_samples=1).over("symbol").alias(
                "recomputed_exante_turnover_ma5_min1"
            ),
        )
        .with_columns(
            first_positive_expr(
                [
                    "recomputed_exante_turnover_ma20_min1",
                    "recomputed_exante_turnover_ma10_min1",
                    "recomputed_exante_turnover_ma5_min1",
                ]
            ).alias("recomputed_fallback_adv_turnover")
        )
    )
    return work.rename({"datetime": "date"})


def build_fallback_audit(orders: pl.DataFrame, exante: pl.DataFrame) -> pl.DataFrame:
    fallback = (
        orders.filter(pl.col("fallback_allowed"))
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6).alias("symbol_key"))
        .rename({"symbol": "order_symbol"})
    )
    joined = fallback.join(
        exante.rename({"symbol": "symbol_key"}),
        on=["date", "symbol_key"],
        how="left",
        suffix="_stock",
    )
    return (
        joined.with_columns(
            (pl.col("prev_trade_date").is_not_null() & (pl.col("prev_trade_date") < pl.col("date"))).alias(
                "prev_date_is_before_order_date"
            ),
            (pl.col("exante_native_adv20_turnover").is_null() | (pl.col("exante_native_adv20_turnover") <= 0)).alias(
                "native_adv_missing_as_expected"
            ),
            (
                (pl.col("fallback_adv_turnover") - pl.col("recomputed_fallback_adv_turnover")).abs()
                <= RECOMPUTE_TOLERANCE
            ).alias("fallback_matches_recomputed"),
            (pl.col("turnover_valid_count_20") == pl.col("recomputed_turnover_valid_count_20")).alias(
                "valid_count_matches_recomputed"
            ),
            (
                pl.col("fallback_adv_turnover").is_not_null()
                & pl.col("turnover").is_not_null()
                & ((pl.col("fallback_adv_turnover") - pl.col("turnover")).abs() <= RECOMPUTE_TOLERANCE)
                & (pl.col("exante_turnover").is_not_null())
                & ((pl.col("turnover") - pl.col("exante_turnover")).abs() > RECOMPUTE_TOLERANCE)
            ).alias("fallback_equals_current_turnover_only"),
        )
        .with_columns(
            (
                pl.col("prev_date_is_before_order_date")
                & pl.col("native_adv_missing_as_expected")
                & pl.col("fallback_matches_recomputed")
                & pl.col("valid_count_matches_recomputed")
                & (~pl.col("fallback_equals_current_turnover_only"))
            ).alias("audit_pass")
        )
        .sort(["date", "adv_quality_flag", "symbol_key", "side"])
    )


def build_class_summary(audit: pl.DataFrame) -> pl.DataFrame:
    if audit.is_empty():
        return pl.DataFrame()
    return (
        audit.group_by(["adv_quality_flag"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol_key").n_unique().alias("symbols"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("filled_weight").sum().alias("filled_weight_sum"),
            pl.col("unfilled_weight").sum().alias("unfilled_weight_sum"),
            pl.col("audit_pass").sum().alias("audit_pass_orders"),
            pl.col("fallback_matches_recomputed").sum().alias("fallback_match_orders"),
            pl.col("valid_count_matches_recomputed").sum().alias("valid_count_match_orders"),
            pl.col("prev_date_is_before_order_date").sum().alias("prev_date_before_orders"),
            pl.col("native_adv_missing_as_expected").sum().alias("native_adv_missing_orders"),
            pl.col("fallback_equals_current_turnover_only").sum().alias("current_turnover_exact_match_orders"),
        )
        .with_columns(
            (pl.col("audit_pass_orders") / pl.col("orders")).alias("audit_pass_ratio"),
            (pl.col("fallback_match_orders") / pl.col("orders")).alias("fallback_match_ratio"),
            (pl.col("valid_count_match_orders") / pl.col("orders")).alias("valid_count_match_ratio"),
        )
        .sort("orders", descending=True)
    )


def build_date_summary(audit: pl.DataFrame) -> pl.DataFrame:
    if audit.is_empty():
        return pl.DataFrame()
    return (
        audit.group_by("date")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol_key").n_unique().alias("symbols"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("audit_pass").sum().alias("audit_pass_orders"),
            (~pl.col("audit_pass")).sum().alias("audit_fail_orders"),
            pl.col("fallback_equals_current_turnover_only").sum().alias("current_turnover_exact_match_orders"),
        )
        .with_columns((pl.col("audit_pass_orders") / pl.col("orders")).alias("audit_pass_ratio"))
        .sort(["audit_fail_orders", "orders"], descending=[True, True])
    )


def build_sample(audit: pl.DataFrame) -> pl.DataFrame:
    if audit.is_empty():
        return pl.DataFrame()
    return (
        audit.with_columns(
            pl.col("desired_weight").rank("ordinal", descending=True).over("adv_quality_flag").alias("_sample_rank")
        )
        .filter(pl.col("_sample_rank") <= SAMPLE_PER_QUALITY_FLAG)
        .select(
            [
                "date",
                "prev_trade_date",
                "symbol_key",
                "code_name",
                "side",
                "status",
                "adv_quality_flag",
                "desired_weight",
                "filled_weight",
                "fallback_adv_turnover",
                "recomputed_fallback_adv_turnover",
                "turnover_valid_count_20",
                "recomputed_turnover_valid_count_20",
                "turnover",
                "exante_turnover",
                "exante_native_adv20_turnover",
                "prev_date_is_before_order_date",
                "native_adv_missing_as_expected",
                "fallback_matches_recomputed",
                "valid_count_matches_recomputed",
                "fallback_equals_current_turnover_only",
                "audit_pass",
            ]
        )
        .sort(["adv_quality_flag", "date", "symbol_key"])
    )


def summarize(audit: pl.DataFrame) -> dict[str, Any]:
    orders = audit.height
    if orders == 0:
        return {
            "scenario": PAPER_SCENARIO,
            "orders": 0,
            "audit_pass_ratio": 1.0,
            "audit_fail_orders": 0,
        }
    audit_pass_orders = int(audit["audit_pass"].sum() or 0)
    return {
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "orders": orders,
        "symbols": audit["symbol_key"].n_unique(),
        "date_count": audit["date"].n_unique(),
        "first_date": audit["date"].min(),
        "last_date": audit["date"].max(),
        "desired_weight_sum": float(audit["desired_weight"].sum() or 0.0),
        "filled_weight_sum": float(audit["filled_weight"].sum() or 0.0),
        "audit_pass_orders": audit_pass_orders,
        "audit_fail_orders": orders - audit_pass_orders,
        "audit_pass_ratio": audit_pass_orders / orders,
        "fallback_match_orders": int(audit["fallback_matches_recomputed"].sum() or 0),
        "valid_count_match_orders": int(audit["valid_count_matches_recomputed"].sum() or 0),
        "prev_date_before_orders": int(audit["prev_date_is_before_order_date"].sum() or 0),
        "native_adv_missing_orders": int(audit["native_adv_missing_as_expected"].sum() or 0),
        "current_turnover_exact_match_orders": int(audit["fallback_equals_current_turnover_only"].sum() or 0),
    }


def write_report(
    summary: dict[str, Any],
    class_summary: pl.DataFrame,
    date_summary: pl.DataFrame,
    sample: pl.DataFrame,
    fail_rows: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    continue_judgment = "是" if summary.get("audit_fail_orders", 0) == 0 else "否"
    continue_reason = (
        "v3 fallback全量复算通过，右移一日成交额口径暂未发现错位，适合继续做新增交易日纸面跟踪。"
        if continue_judgment == "是"
        else "存在fallback审计失败样本，应先定位成交额右移或交易日历错位，再继续推进纸面跟踪。"
    )
    lines = [
        "# 股票震荡liquid_q3 v3 fallback样本审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：审计v3 ex-ante ADV质量口径中的fallback样本；不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 滚动窗口特征若用于交易或执行约束，需要确认信息在交易点已经可知，常见做法是滞后一日。",
        "- 本阶段按全量fallback订单重新计算ex-ante成交额，重点查三件事：上一交易日早于订单日、原生ADV确实缺失、fallback与复算值一致。",
        "- 这不是收益优化，而是防止纸面跟踪在数据质量修复时引入隐性前视。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心结果",
            "",
            f"- fallback订单`{summary.get('orders', 0)}`行，涉及股票`{summary.get('symbols', 0)}`只，日期`{summary.get('first_date')}`到`{summary.get('last_date')}`。",
            f"- fallback目标权重合计`{summary.get('desired_weight_sum', 0):.4f}`，成交权重合计`{summary.get('filled_weight_sum', 0):.4f}`。",
            f"- 全量审计通过`{summary.get('audit_pass_orders', 0)}`行，失败`{summary.get('audit_fail_orders', 0)}`行，通过率`{pct(summary.get('audit_pass_ratio', 0))}`。",
            f"- fallback复算匹配`{summary.get('fallback_match_orders', 0)}`行；有效成交额天数匹配`{summary.get('valid_count_match_orders', 0)}`行。",
            f"- 上一交易日早于订单日`{summary.get('prev_date_before_orders', 0)}`行；原生ADV按预期缺失`{summary.get('native_adv_missing_orders', 0)}`行。",
            f"- fallback精确等于当日成交额且不等于上一交易日成交额的可疑样本`{summary.get('current_turnover_exact_match_orders', 0)}`行。",
            "- 直觉判断：这一步像检查纸面系统的钟表有没有慢一拍或快一拍；只要时间戳对齐干净，v3才值得作为默认入口。",
            "",
            "## 质量分类汇总",
            "",
            markdown_table(
                class_summary,
                [
                    "adv_quality_flag",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "audit_pass_orders",
                    "audit_pass_ratio",
                    "fallback_match_ratio",
                    "valid_count_match_ratio",
                    "current_turnover_exact_match_orders",
                ],
            ),
            "",
            "## 失败样本",
            "",
            markdown_table(
                fail_rows,
                [
                    "date",
                    "prev_trade_date",
                    "symbol_key",
                    "code_name",
                    "side",
                    "adv_quality_flag",
                    "fallback_adv_turnover",
                    "recomputed_fallback_adv_turnover",
                    "turnover_valid_count_20",
                    "recomputed_turnover_valid_count_20",
                    "prev_date_is_before_order_date",
                    "native_adv_missing_as_expected",
                    "fallback_matches_recomputed",
                    "valid_count_matches_recomputed",
                    "fallback_equals_current_turnover_only",
                    "audit_pass",
                ],
            ),
            "",
            "## 抽样样本",
            "",
            markdown_table(
                sample,
                [
                    "date",
                    "prev_trade_date",
                    "symbol_key",
                    "code_name",
                    "side",
                    "adv_quality_flag",
                    "desired_weight",
                    "filled_weight",
                    "fallback_adv_turnover",
                    "recomputed_fallback_adv_turnover",
                    "turnover_valid_count_20",
                    "recomputed_turnover_valid_count_20",
                    "turnover",
                    "exante_turnover",
                    "exante_native_adv20_turnover",
                    "audit_pass",
                ],
                max_rows=80,
            ),
            "",
            "## 日期汇总Top",
            "",
            markdown_table(
                date_summary,
                [
                    "date",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "audit_pass_orders",
                    "audit_fail_orders",
                    "audit_pass_ratio",
                    "current_turnover_exact_match_orders",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只审计执行数据口径，不新增交易信号、不调整收益参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：全量复算只是验证fallback来源是否ex-ante，不会提高历史收益。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：v3已作为最新纸面入口默认口径，必须确认fallback没有时间错位。",
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
            "- 若后续数据更新后fallback样本增加，应重新运行本审计。",
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
    orders = pl.read_csv(V3_OUTPUT_DIR / f"{V3_PREFIX}_paper_orders.csv", try_parse_dates=True)
    stock_df, _benchmark_df = load_panels()
    exante = build_exante_liquidity(stock_df)
    audit = build_fallback_audit(orders, exante)
    class_summary = build_class_summary(audit)
    date_summary = build_date_summary(audit)
    sample = build_sample(audit)
    fail_rows = audit.filter(~pl.col("audit_pass")) if not audit.is_empty() else pl.DataFrame()
    summary = summarize(audit)
    paths = {
        "audit": OUTPUT_DIR / f"{PREFIX}_audit.csv",
        "class_summary": OUTPUT_DIR / f"{PREFIX}_class_summary.csv",
        "date_summary": OUTPUT_DIR / f"{PREFIX}_date_summary.csv",
        "sample": OUTPUT_DIR / f"{PREFIX}_sample.csv",
        "fail_rows": OUTPUT_DIR / f"{PREFIX}_fail_rows.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    audit.write_csv(paths["audit"])
    class_summary.write_csv(paths["class_summary"])
    date_summary.write_csv(paths["date_summary"])
    sample.write_csv(paths["sample"])
    fail_rows.write_csv(paths["fail_rows"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "source_orders": str(V3_OUTPUT_DIR / f"{V3_PREFIX}_paper_orders.csv"),
        "recompute_tolerance": RECOMPUTE_TOLERANCE,
        "sample_per_quality_flag": SAMPLE_PER_QUALITY_FLAG,
        "research_sources": RESEARCH_SOURCES,
        "note": "Audits all v3 fallback orders by recomputing shifted turnover-based fallback ADV from the stock panel.",
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, class_summary, date_summary, sample, fail_rows, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
