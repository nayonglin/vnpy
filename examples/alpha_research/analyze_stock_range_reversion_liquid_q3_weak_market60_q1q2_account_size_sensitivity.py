from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    HORIZON,
    NATIVE_RESULTS_DIR,
    build_lots,
    build_symbol_daily,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_weak_market60_q1q2_account_size_sensitivity_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_weak_market60_q1q2_account_size_sensitivity_v1"

PRIMARY_SCENARIO: str = "weak_market60_q1q2_diagnostic"
REALLOCATED_SCENARIO: str = "weak_market60_q1q2_reallocated"
CANDIDATE_SCENARIOS: tuple[str, ...] = (PRIMARY_SCENARIO, REALLOCATED_SCENARIO)
ACCOUNT_SIZES_CNY: tuple[float, ...] = tuple(
    float(item)
    for item in os.getenv("ACCOUNT_SIZES_CNY", "300000,500000,1000000,2000000,3000000,5000000").split(",")
    if item.strip()
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE board lot rules",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
    (
        "Backtesting Engine position sizing notes",
        "https://backtestingengine.com/getting-started/first-strategy",
    ),
)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_selected() -> pl.DataFrame:
    return pl.read_csv(
        SOURCE_DIR / f"{SOURCE_PREFIX}_selected_variants.csv",
        try_parse_dates=True,
        schema_overrides={
            "symbol": pl.Utf8,
            "vt_symbol": pl.Utf8,
            "bs_code": pl.Utf8,
            "code": pl.Utf8,
        },
    ).filter(pl.col("scenario").is_in(CANDIDATE_SCENARIOS))


def build_candidate_target_weights(selected: pl.DataFrame) -> pl.DataFrame:
    lots = build_lots(selected)
    symbol_daily = build_symbol_daily(lots)
    keep_cols = [
        col
        for col in [
            "scenario",
            "target_date",
            "symbol",
            "target_weight",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "circ_mv",
            "total_mv",
        ]
        if col in symbol_daily.columns
    ]
    return symbol_daily.select(keep_cols).unique(subset=["scenario", "target_date", "symbol"]).sort(
        ["scenario", "target_date", "symbol"]
    )


def replay_with_account_size(
    scenario: str,
    account_size_cny: float,
    target_weights: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    original_size = lot.ACCOUNT_SIZE_CNY
    lot.ACCOUNT_SIZE_CNY = account_size_cny
    try:
        scenario_targets = target_weights.filter(pl.col("scenario") == scenario).drop("scenario")
        target_maps = lot.build_target_maps(scenario_targets)
        dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
        orders, daily, curve = lot.replay_lot_account(target_maps, dates, exec_info)
        summary = lot.summarize_orders(orders, daily)
    finally:
        lot.ACCOUNT_SIZE_CNY = original_size

    if not orders.is_empty():
        orders = orders.with_columns(
            pl.lit(scenario).alias("scenario"),
            pl.lit(account_size_cny).alias("account_size_cny"),
        )
    if not daily.is_empty():
        daily = daily.with_columns(
            pl.lit(scenario).alias("scenario"),
            pl.lit(account_size_cny).alias("account_size_cny"),
        )
    summary["scenario"] = scenario
    summary["account_size_cny"] = account_size_cny
    summary["target_weight_mode"] = (
        "original_weight_no_realloc" if scenario == PRIMARY_SCENARIO else "reallocated_capped"
    )
    summary["min_fee_equity_gap"] = to_float(summary.get("final_equity_bps_only")) - to_float(
        summary.get("final_equity_min_fee")
    )
    summary["latest_exposure_capture_ratio"] = (
        to_float(summary.get("latest_rounded_target_amount_sum_cny"))
        / to_float(summary.get("latest_target_amount_sum_cny"))
        if to_float(summary.get("latest_target_amount_sum_cny")) > 0
        else 0.0
    )
    return summary, orders, daily, curve


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        size = row["account_size_cny"]
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        min_fee_gap = to_float(row.get("min_fee_equity_gap"))
        rows.append(
            {
                "scenario": scenario,
                "account_size_cny": size,
                "checkpoint": "zero_lot_target_ratio",
                "status": "fail" if zero_ratio > 0.30 else "warn" if zero_ratio > 0.10 else "pass",
                "value": f"{zero_ratio:.2%}",
                "expected": "<=10% preferred, <=30% hard",
                "note": "整手取整为0比例过高时，账户规模不足以承载分散组合。",
            }
        )
        rows.append(
            {
                "scenario": scenario,
                "account_size_cny": size,
                "checkpoint": "latest_exposure_capture_ratio",
                "status": "fail" if latest_capture < 0.50 else "warn" if latest_capture < 0.70 else "pass",
                "value": f"{latest_capture:.2%}",
                "expected": ">=70% preferred, >=50% hard",
                "note": "最新目标日取整后市值相对目标市值的捕获率。",
            }
        )
        rows.append(
            {
                "scenario": scenario,
                "account_size_cny": size,
                "checkpoint": "min_fee_equity_gap",
                "status": "warn" if min_fee_gap > 0.10 else "pass",
                "value": f"{min_fee_gap:.4f}",
                "expected": "<=0.10 equity gap",
                "note": "最低佣金相对bps成本的额外权益拖累。",
            }
        )
    return pl.DataFrame(rows).sort(["scenario", "account_size_cny", "checkpoint"])


def write_report(summary: pl.DataFrame, quality: pl.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best_primary = summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("account_size_cny")
    best_reallocated = summary.filter(pl.col("scenario") == REALLOCATED_SCENARIO).sort("account_size_cny")
    primary_latest = best_primary.tail(1).row(0, named=True)
    reallocated_latest = best_reallocated.tail(1).row(0, named=True)

    def first_all_pass_row(scenario: str) -> dict[str, Any] | None:
        scenario_summary = summary.filter(pl.col("scenario") == scenario).sort("account_size_cny")
        scenario_quality = quality.filter(pl.col("scenario") == scenario)
        for row in scenario_summary.iter_rows(named=True):
            account_size = row["account_size_cny"]
            checks = scenario_quality.filter(pl.col("account_size_cny") == account_size)
            if checks.filter(pl.col("status") != "pass").is_empty():
                return row
        return None

    primary_first_pass = first_all_pass_row(PRIMARY_SCENARIO)
    reallocated_first_pass = first_all_pass_row(REALLOCATED_SCENARIO)

    def account_threshold_text(row: dict[str, Any] | None) -> str:
        if row is None:
            return "本轮未出现全部质量项通过的账户规模"
        return (
            f"首次全部质量项通过为`{row['account_size_cny']:,.0f}`元，"
            f"zero-lot `{pct(row['zero_lot_target_ratio'])}`，"
            f"最新暴露捕获`{pct(row['latest_exposure_capture_ratio'])}`，"
            f"最低佣金权益差`{row['min_fee_equity_gap']:.4f}`"
        )

    lines = [
        "# 股票震荡liquid_q3 weak_market60_q1q2 资金规模敏感性审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定候选信号，仅改变账户规模，审计整手损失、最低佣金拖累和暴露捕获。",
        f"- 账户规模：`{', '.join(f'{size:,.0f}' for size in ACCOUNT_SIZES_CNY)}`元。",
        "- A/B判断：资金规模硬约束审计，不接入正式版本，不触发第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- A股100股整手会让小账户的目标权重被价格离散化。",
        "- 仓位百分比策略必须和账户规模一起复放，否则小资金下的组合形状会偏离研究信号。",
        "- 本阶段只改变账户规模，不改变信号和权重规则。",
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
            f"- 诊断组最高审计资金`{primary_latest['account_size_cny']:,.0f}`元：zero-lot `{pct(primary_latest['zero_lot_target_ratio'])}`，最新暴露捕获`{pct(primary_latest['latest_exposure_capture_ratio'])}`，最低佣金权益差`{primary_latest['min_fee_equity_gap']:.4f}`。",
            f"- 重分配组最高审计资金`{reallocated_latest['account_size_cny']:,.0f}`元：zero-lot `{pct(reallocated_latest['zero_lot_target_ratio'])}`，最新暴露捕获`{pct(reallocated_latest['latest_exposure_capture_ratio'])}`，最低佣金权益差`{reallocated_latest['min_fee_equity_gap']:.4f}`。",
            f"- 诊断组承载阈值：{account_threshold_text(primary_first_pass)}。",
            f"- 重分配组承载阈值：{account_threshold_text(reallocated_first_pass)}。",
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 判断：资金规模越大，整手损失和最低佣金拖累下降；30万/50万不适合直接实盘复刻当前组合形状，承载阈值只能用于判断可交易性，不能反向调alpha。",
            "",
            "## 规模汇总",
            "",
            markdown_table(
                summary,
                [
                    "scenario",
                    "target_weight_mode",
                    "account_size_cny",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "zero_lot_target_ratio",
                    "min_fee_equity_gap",
                    "latest_target_symbol_count",
                    "latest_actual_symbol_count",
                    "latest_zero_lot_target_count",
                    "latest_target_amount_sum_cny",
                    "latest_rounded_target_amount_sum_cny",
                    "latest_exposure_capture_ratio",
                    "latest_actual_gross_weight",
                ],
                max_rows=40,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["scenario", "account_size_cny", "checkpoint", "status", "value", "expected", "note"], max_rows=120),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["scenario", "account_size_cny", "checkpoint", "status", "value", "expected", "note"], max_rows=120),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["scenario", "account_size_cny", "checkpoint", "status", "value", "expected", "note"], max_rows=120),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只改变账户规模，测试A股整手和最低佣金硬约束，不改变alpha信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：资金规模敏感性是执行约束审计；不能用结果反向选择账户规模来美化策略，只能判断可承载性。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万候选整手复放显示zero-lot很重，需要知道资金规模到哪里才缓解。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：视资金规模而定。",
            "- 原因：若50万/100万明显缓解，可继续候选paper；若仍严重，则应暂停实盘链路，回到资金/组合形状约束。",
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
    selected = read_selected()
    target_weights = build_candidate_target_weights(selected)
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    summaries: list[dict[str, Any]] = []
    order_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    for account_size in ACCOUNT_SIZES_CNY:
        for scenario in CANDIDATE_SCENARIOS:
            summary, orders, daily, _curve = replay_with_account_size(
                scenario,
                account_size,
                target_weights,
                benchmark_df,
                exec_info,
            )
            summaries.append(summary)
            order_frames.append(orders)
            daily_frames.append(daily)

    summary = pl.DataFrame(summaries).sort(["scenario", "account_size_cny"])
    quality = build_quality(summary)
    orders = pl.concat([frame for frame in order_frames if not frame.is_empty()], how="vertical")
    daily = pl.concat([frame for frame in daily_frames if not frame.is_empty()], how="vertical")

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    quality.write_csv(paths["quality_checkpoints"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "candidate_scenarios": CANDIDATE_SCENARIOS,
            "account_sizes_cny": ACCOUNT_SIZES_CNY,
            "board_lot_shares": lot.BOARD_LOT_SHARES,
            "min_commission_cny": lot.MIN_COMMISSION_CNY,
            "horizon": HORIZON,
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(summary, quality, paths)
    print(f"report={report_path}")
    print(summary)
    print(quality)


if __name__ == "__main__":
    main()
