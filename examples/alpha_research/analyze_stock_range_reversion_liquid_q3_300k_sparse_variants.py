from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    build_tracking_dates,
    build_target_maps,
    floor_to_lot_shares,
    replay_lot_account,
    summarize_orders,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    PAPER_SCENARIO,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import (
    build_exec_info,
    to_float,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_sparse_variants_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_sparse_variants_v1"

VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "variant": "sparse_14_w4pct_ind4",
        "max_names": 14,
        "per_name_weight": 0.04,
        "max_names_per_industry": 4,
        "description": "30万账户偏集中版：最多14只，单票目标4%，同业最多4只。",
    },
    {
        "variant": "sparse_18_w3pct_ind4",
        "max_names": 18,
        "per_name_weight": 0.03,
        "max_names_per_industry": 4,
        "description": "30万账户均衡版：最多18只，单票目标3%，同业最多4只。",
    },
    {
        "variant": "sparse_22_w2_5pct_ind5",
        "max_names": 22,
        "per_name_weight": 0.025,
        "max_names_per_industry": 5,
        "description": "30万账户偏分散版：最多22只，单票目标2.5%，同业最多5只。",
    },
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE trading rules: buy orders must be in a board lot of 100 shares",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
)


def one_lot_amount(row: dict[str, Any], exec_info: dict[tuple[date, str], Any]) -> float:
    info = exec_info.get((row["target_date"], row["symbol"]))
    trade_open = to_float(info.trade_open if info else None)
    return trade_open * BOARD_LOT_SHARES


def choose_sparse_targets_for_day(
    rows: list[dict[str, Any]],
    exec_info: dict[tuple[date, str], Any],
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    max_names = int(variant["max_names"])
    per_name_weight = float(variant["per_name_weight"])
    max_names_per_industry = int(variant["max_names_per_industry"])
    original_gross = sum(to_float(row.get("target_weight")) for row in rows)
    selected: list[dict[str, Any]] = []
    industry_counts: dict[str, int] = {}

    for row in sorted(rows, key=lambda item: (-to_float(item.get("target_weight")), str(item.get("symbol")))):
        if len(selected) >= max_names:
            break
        industry = str(row.get("industry") or "")
        if industry_counts.get(industry, 0) >= max_names_per_industry:
            continue
        lot_amount = one_lot_amount(row, exec_info)
        if lot_amount <= 0:
            continue
        if lot_amount > per_name_weight * ACCOUNT_SIZE_CNY:
            continue
        selected.append({**row, "_one_lot_amount_cny": lot_amount})
        industry_counts[industry] = industry_counts.get(industry, 0) + 1

    # If original gross exposure is low, scale down rather than manufacturing extra exposure.
    while selected:
        final_weight = min(per_name_weight, original_gross / len(selected))
        affordable = [row for row in selected if row["_one_lot_amount_cny"] <= final_weight * ACCOUNT_SIZE_CNY]
        if len(affordable) == len(selected):
            break
        selected = affordable

    if not selected:
        return []
    final_weight = min(per_name_weight, original_gross / len(selected))
    output: list[dict[str, Any]] = []
    for row in selected:
        clean = {key: value for key, value in row.items() if not key.startswith("_")}
        clean["target_weight"] = final_weight
        clean["target_amount_cny"] = final_weight * ACCOUNT_SIZE_CNY
        clean["account_size_cny"] = ACCOUNT_SIZE_CNY
        clean["variant"] = variant["variant"]
        clean["variant_description"] = variant["description"]
        output.append(clean)
    return output


def build_sparse_target_weights(
    original_targets: pl.DataFrame,
    exec_info: dict[tuple[date, str], Any],
    variant: dict[str, Any],
) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for (_target_date,), group in original_targets.group_by("target_date", maintain_order=True):
        rows.extend(choose_sparse_targets_for_day(list(group.iter_rows(named=True)), exec_info, variant))
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).sort(["target_date", "industry", "symbol"])


def add_variant(frame: pl.DataFrame, variant: str) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    return frame.with_columns(pl.lit(variant).alias("variant"))


def summarize_target_shape(target_weights: pl.DataFrame, exec_info: dict[tuple[date, str], Any]) -> dict[str, Any]:
    if target_weights.is_empty():
        return {}
    zero_lot = 0
    total = 0
    one_lot_amounts: list[float] = []
    for row in target_weights.iter_rows(named=True):
        info = exec_info.get((row["target_date"], row["symbol"]))
        trade_open = to_float(info.trade_open if info else None)
        target_amount = to_float(row.get("target_weight")) * ACCOUNT_SIZE_CNY
        target_shares = floor_to_lot_shares(target_amount, trade_open)
        total += 1
        if target_shares <= 0:
            zero_lot += 1
        if trade_open > 0:
            one_lot_amounts.append(trade_open * BOARD_LOT_SHARES)
    daily = target_weights.group_by("target_date").agg(
        pl.len().alias("target_names"),
        pl.col("target_weight").sum().alias("target_gross"),
        pl.col("industry").n_unique().alias("industry_count"),
    )
    return {
        "target_rows": total,
        "zero_lot_target_rows": zero_lot,
        "zero_lot_target_ratio": zero_lot / total if total else 0.0,
        "avg_target_names": to_float(daily["target_names"].mean()),
        "avg_target_gross": to_float(daily["target_gross"].mean()),
        "avg_industry_count": to_float(daily["industry_count"].mean()),
        "median_one_lot_amount_cny": sorted(one_lot_amounts)[len(one_lot_amounts) // 2] if one_lot_amounts else 0.0,
    }


def build_report(
    variant_summary: pl.DataFrame,
    baseline_summary: dict[str, Any],
    latest_targets: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万账户稀疏组合构造 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：30万账户组合构造影子回放；不改选股信号，不调`volume_ratio_20 <= 0.70`。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；买入颗粒度：`{BOARD_LOT_SHARES}`股整数手；最低佣金压力：`{MIN_COMMISSION_CNY}`元/笔。",
        "- 设计原则：先让组合在30万账户上真实买得动，再讨论收益；不按回测收益倒推参数。",
        "",
        "## 外部调研判断",
        "",
        "- 上交所说明主板股票买入委托为100股整数倍；深交所互联互通规则也列明买入为100股或其整数倍。",
        "- 因此30万账户的核心约束是单票目标金额太小会被整手吞掉，必须减少持仓数量或提高单票金额。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 原始30万整手回放基准",
            "",
            f"- 原始目标股票被一手取整为0比例：`{baseline_summary['zero_lot_target_ratio']:.2%}`。",
            f"- 最新目标日：目标`{baseline_summary['latest_target_symbol_count']}`只，实际`{baseline_summary['latest_actual_symbol_count']}`只，目标取整为0的股票`{baseline_summary['latest_zero_lot_target_count']}`只。",
            f"- 最低佣金压力口径：期末权益`{baseline_summary['final_equity_min_fee']:.4f}`，总收益`{pct(baseline_summary['total_return_min_fee'])}`，最大回撤`{pct(baseline_summary['max_drawdown_min_fee'])}`，Sharpe `{baseline_summary['sharpe_min_fee']:.2f}`。",
            "",
            "## 稀疏组合结果",
            "",
            markdown_table(
                variant_summary,
                [
                    "variant",
                    "max_names",
                    "per_name_weight",
                    "max_names_per_industry",
                    "zero_lot_target_ratio",
                    "avg_target_names",
                    "avg_target_gross",
                    "latest_actual_symbol_count",
                    "latest_actual_gross_weight",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "filled_order_rows",
                    "blocked_order_rows",
                ],
                max_rows=20,
            ),
            "",
            "## 最新目标样例",
            "",
            markdown_table(
                latest_targets,
                [
                    "variant",
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "target_weight",
                    "target_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段不是改信号，而是把30万账户必然面对的持仓数量和单票金额约束显性化。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：暂时否，但需要警惕。",
            "- 原因：本次只跑3个由交易颗粒度推导出的稀疏构造，没有按结果继续搜索；后续不能用收益最高者直接定版。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：原始30万回放已有35.01%的目标买不到一手，必须验证专用组合构造。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：若稀疏构造能大幅降低一手失真，下一步才有资格做OOS和纸面监控；若收益形态恶化，也能及时否决30万股票震荡实盘路线。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 暂不做第78 A/B/C。",
            "- 下一步看OOS稳定性和最新纸面订单，而不是只看全历史收益。",
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
    exec_info = build_exec_info(stock_df)
    original_targets = build_target_weights(selected_all)
    dates = build_tracking_dates(original_targets, benchmark_df)

    baseline_summary_path = (
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_300k_lot_feasibility_2018_2026"
        / "stock_range_reversion_liquid_q3_300k_lot_feasibility_v1_summary.json"
    )
    baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))

    summaries: list[dict[str, Any]] = []
    all_orders: list[pl.DataFrame] = []
    all_daily: list[pl.DataFrame] = []
    all_targets: list[pl.DataFrame] = []

    for variant in VARIANTS:
        variant_name = str(variant["variant"])
        target_weights = build_sparse_target_weights(original_targets, exec_info, variant)
        target_maps = build_target_maps(target_weights)
        orders, daily, _curves = replay_lot_account(target_maps, dates, exec_info)
        summary = summarize_orders(orders, daily)
        shape = summarize_target_shape(target_weights, exec_info)
        summary.update(shape)
        summary.update(
            {
                "variant": variant_name,
                "description": variant["description"],
                "max_names": variant["max_names"],
                "per_name_weight": variant["per_name_weight"],
                "max_names_per_industry": variant["max_names_per_industry"],
            }
        )
        summaries.append(summary)
        all_orders.append(add_variant(orders, variant_name))
        all_daily.append(add_variant(daily, variant_name))
        all_targets.append(target_weights)

    variant_summary = pl.DataFrame(summaries).sort("variant")
    orders_all = pl.concat(all_orders, how="vertical") if all_orders else pl.DataFrame()
    daily_all = pl.concat(all_daily, how="vertical") if all_daily else pl.DataFrame()
    targets_all = pl.concat(all_targets, how="vertical") if all_targets else pl.DataFrame()
    latest_date = targets_all["target_date"].max() if not targets_all.is_empty() else None
    latest_targets = (
        targets_all.filter(pl.col("target_date") == latest_date).sort(["variant", "industry", "symbol"])
        if latest_date is not None
        else pl.DataFrame()
    )

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "summary_json": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "targets": OUTPUT_DIR / f"{PREFIX}_targets.csv",
        "latest_targets": OUTPUT_DIR / f"{PREFIX}_latest_targets.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    variant_summary.write_csv(paths["summary"])
    daily_all.write_csv(paths["daily"])
    orders_all.write_csv(paths["orders"])
    targets_all.write_csv(paths["targets"])
    latest_targets.write_csv(paths["latest_targets"])
    write_json(paths["summary_json"], {"summaries": summaries})
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "board_lot_shares": BOARD_LOT_SHARES,
            "variants": VARIANTS,
            "baseline_summary_path": baseline_summary_path,
            "research_sources": RESEARCH_SOURCES,
            "note": "Sparse construction variants for 300k account only; no signal or threshold optimization.",
        },
    )
    report_path = build_report(variant_summary, baseline_summary, latest_targets, paths)
    print(variant_summary)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
