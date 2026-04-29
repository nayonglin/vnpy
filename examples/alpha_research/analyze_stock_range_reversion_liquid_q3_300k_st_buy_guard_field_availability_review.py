from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_block_review_2018_2026"
).resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_block_review_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_field_availability_review_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_field_availability_review_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Lookahead-bias prevention notes emphasize explicit rolling lookback and warmup handling",
        "https://docs.clypt.ai/backtesting/lookahead-bias-prevention",
    ),
    (
        "A-share reversal examples commonly use 20-day average amount as liquidity filter",
        "https://www.pandaai.online/community/article/742",
    ),
)


def read_csv(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, try_parse_dates=True, infer_schema_length=10000, schema_overrides={"symbol": pl.Utf8})
    return df.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6)) if "symbol" in df.columns else df


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_recomputed_adv20() -> pl.DataFrame:
    stock_df, _ = load_panels()
    return (
        stock_df.select(["datetime", "symbol", "turnover"])
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .sort(["symbol", "date"])
        .with_columns(pl.col("turnover").rolling_mean(20).over("symbol").alias("recomputed_adv20_turnover"))
        .select(["date", "symbol", "recomputed_adv20_turnover"])
    )


def enrich_with_recomputed_adv20(blocks: pl.DataFrame, recomputed: pl.DataFrame) -> pl.DataFrame:
    return blocks.join(recomputed, on=["date", "symbol"], how="left").with_columns(
        pl.col("panel_adv20_turnover").is_null().alias("original_adv20_missing"),
        pl.col("recomputed_adv20_turnover").is_null().alias("recomputed_adv20_missing"),
        (pl.col("recomputed_adv20_turnover").fill_null(0.0) >= MIN_ADV20_TURNOVER).alias(
            "recomputed_adv20_pass_min"
        ),
        (
            (pl.col("primary_block_reason") == "adv20_turnover_lt_min")
            & pl.col("panel_adv20_turnover").is_null()
            & (pl.col("recomputed_adv20_turnover").fill_null(0.0) >= MIN_ADV20_TURNOVER)
        ).alias("likely_warmup_artifact_block"),
    )


def summarize_reason(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by("primary_block_reason")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("original_adv20_missing").sum().alias("original_adv20_missing_orders"),
            pl.col("recomputed_adv20_missing").sum().alias("recomputed_adv20_missing_orders"),
            pl.col("recomputed_adv20_pass_min").sum().alias("recomputed_adv20_pass_orders"),
            pl.col("likely_warmup_artifact_block").sum().alias("likely_warmup_artifact_orders"),
        )
        .sort("orders", descending=True)
    )


def summarize_warmup_artifacts(enriched: pl.DataFrame) -> pl.DataFrame:
    artifacts = enriched.filter(pl.col("likely_warmup_artifact_block"))
    if artifacts.is_empty():
        return pl.DataFrame()
    return (
        artifacts.with_columns(
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
        )
        .group_by(["year", "month"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("recomputed_adv20_turnover").mean().alias("avg_recomputed_adv20_turnover"),
        )
        .sort(["year", "month"])
    )


def summarize_top_artifact_symbols(enriched: pl.DataFrame) -> pl.DataFrame:
    artifacts = enriched.filter(pl.col("likely_warmup_artifact_block"))
    if artifacts.is_empty():
        return pl.DataFrame()
    return (
        artifacts.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("orders"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("recomputed_adv20_turnover").mean().alias("avg_recomputed_adv20_turnover"),
            pl.col("recomputed_adv20_turnover").min().alias("min_recomputed_adv20_turnover"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "adv20_missing_recomputed_reviewed",
            "status": "pass" if summary["adv20_reason_orders"] > 0 else "warn",
            "value": str(summary["adv20_reason_orders"]),
            "expected": ">0",
            "note": "本阶段必须复核ADV20字段缺失。",
        },
        {
            "checkpoint": "guard_as_is_not_ready",
            "status": "warn" if summary["likely_warmup_artifact_orders"] > 0 else "pass",
            "value": str(summary["likely_warmup_artifact_orders"]),
            "expected": "0 before direct integration",
            "note": "若大量阻断是暖机/字段缺失，不应原样接入守门。",
        },
        {
            "checkpoint": "latest_orders_not_impacted",
            "status": "pass" if summary["latest_st_or_ineligible_blocks"] == 0 else "warn",
            "value": str(summary["latest_st_or_ineligible_blocks"]),
            "expected": "0 for latest packet",
            "note": "最新目标日没有守门阻断，当前执行包未受影响。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "只审计字段可用性，不修改策略信号。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    reason_summary: pl.DataFrame,
    warmup_summary: pl.DataFrame,
    top_artifacts: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> None:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 ST守门ADV20字段可用性复核 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：复核第276阶段发现的ADV20阻断主因；不新增alpha信号、不调收益参数、不修改paper入口。",
        "- A/B判断：字段可用性审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 20日均成交额作为流动性过滤是常见做法，但任何滚动窗口都必须处理暖机期；缺失不能机械等同于流动性差。",
        "- 本阶段的关键不是优化收益，而是区分真实低流动性和数据窗口/字段缺失。",
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
            f"- 第276阶段`adv20_turnover_lt_min`阻断`{summary['adv20_reason_orders']}`笔。",
            f"- 这些阻断中原始`panel_adv20_turnover`缺失`{summary['adv20_original_missing_orders']}`笔。",
            f"- 用完整面板重新计算20日均成交额后，`{summary['adv20_recomputed_pass_orders']}`笔实际超过`{MIN_ADV20_TURNOVER:,.0f}`元阈值。",
            f"- 疑似暖机/字段缺失误阻断`{summary['likely_warmup_artifact_orders']}`笔，占全部守门阻断`{summary['likely_warmup_artifact_ratio']:.2%}`。",
            f"- 最新目标日`{summary['latest_date']}`守门阻断`{summary['latest_st_or_ineligible_blocks']}`笔，当前交易包不受影响。",
            f"- 历史样本中最新守门阻断日为`{summary['latest_block_date']}`。",
            "",
            "## 判断",
            "",
            "- 第275守门方向仍有价值，但不能原样接入paper入口。",
            "- 原因：最大阻断来源不是低流动性，而是原始ADV20字段缺失；完整历史重算后大多数通过流动性阈值。",
            "- 正确路径不是放弃守门，而是把守门拆成：真实ST禁止买入、非成分禁止新增、ADV20缺失时用可验证的前20日成交额重算或进入人工/保守降级。",
            "",
            "## 阻断原因复核",
            "",
            markdown_table(
                reason_summary,
                [
                    "primary_block_reason",
                    "orders",
                    "symbols",
                    "desired_amount_cny_sum",
                    "original_adv20_missing_orders",
                    "recomputed_adv20_missing_orders",
                    "recomputed_adv20_pass_orders",
                    "likely_warmup_artifact_orders",
                ],
                max_rows=50,
            ),
            "",
            "## 暖机疑似误阻断月度分布",
            "",
            "无数据"
            if warmup_summary.is_empty()
            else markdown_table(
                warmup_summary,
                ["year", "month", "orders", "symbols", "desired_amount_cny_sum", "avg_recomputed_adv20_turnover"],
                max_rows=100,
            ),
            "",
            "## 高频疑似误阻断个股",
            "",
            "无数据"
            if top_artifacts.is_empty()
            else markdown_table(
                top_artifacts,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "orders",
                    "first_date",
                    "last_date",
                    "desired_amount_cny_sum",
                    "avg_recomputed_adv20_turnover",
                    "min_recomputed_adv20_turnover",
                ],
                max_rows=80,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据"
            if failed.is_empty()
            else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据"
            if warned.is_empty()
            else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段检查字段可用性和滚动窗口暖机，不根据收益选择规则。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结论是否定原样接入守门，降低了因数据缺失误伤带来的拟合风险。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第276阶段显示ADV20是主要阻断原因，但其均值为空，必须拆清是低流动性还是字段缺失。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：发现关键数据边界问题，下一步应做修正版守门回放，而不是直接接入。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for key, path in paths.items():
        lines.append(f"- `{key}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = SOURCE_DIR / f"{SOURCE_PREFIX}_enriched_blocks.csv"
    source_summary_path = SOURCE_DIR / f"{SOURCE_PREFIX}_summary.json"
    blocks = read_csv(source_path)
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    recomputed = build_recomputed_adv20()
    enriched = enrich_with_recomputed_adv20(blocks, recomputed)
    reason_summary = summarize_reason(enriched)
    warmup_summary = summarize_warmup_artifacts(enriched)
    top_artifacts = summarize_top_artifact_symbols(enriched)

    adv_blocks = enriched.filter(pl.col("primary_block_reason") == "adv20_turnover_lt_min")
    likely_artifacts = enriched.filter(pl.col("likely_warmup_artifact_block"))
    latest_block_date = str(blocks["date"].max())
    adv_reason_orders = adv_blocks.height
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_enriched_blocks": str(source_path),
        "total_guard_blocks": enriched.height,
        "adv20_reason_orders": adv_reason_orders,
        "adv20_original_missing_orders": adv_blocks.filter(pl.col("original_adv20_missing")).height,
        "adv20_recomputed_missing_orders": adv_blocks.filter(pl.col("recomputed_adv20_missing")).height,
        "adv20_recomputed_pass_orders": adv_blocks.filter(pl.col("recomputed_adv20_pass_min")).height,
        "likely_warmup_artifact_orders": likely_artifacts.height,
        "likely_warmup_artifact_ratio": likely_artifacts.height / enriched.height if enriched.height else 0.0,
        "latest_block_date": latest_block_date,
        "latest_date": str(source_summary.get("latest_date", "")),
        "latest_st_or_ineligible_blocks": safe_int(source_summary.get("latest_st_or_ineligible_blocks", 0)),
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "enriched_blocks": OUTPUT_DIR / f"{PREFIX}_enriched_blocks.csv",
        "reason_summary": OUTPUT_DIR / f"{PREFIX}_reason_summary.csv",
        "warmup_artifact_monthly": OUTPUT_DIR / f"{PREFIX}_warmup_artifact_monthly.csv",
        "warmup_artifact_top_symbols": OUTPUT_DIR / f"{PREFIX}_warmup_artifact_top_symbols.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
    }
    enriched.write_csv(paths["enriched_blocks"])
    reason_summary.write_csv(paths["reason_summary"])
    warmup_summary.write_csv(paths["warmup_artifact_monthly"])
    top_artifacts.write_csv(paths["warmup_artifact_top_symbols"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, reason_summary, warmup_summary, top_artifacts, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()
