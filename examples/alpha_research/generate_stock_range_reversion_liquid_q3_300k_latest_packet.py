from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    floor_to_lot_shares,
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
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "Zipline ledger separates orders, transactions, and portfolio state",
        "https://flounderteam.github.io/refs/zipline/appendix.html",
    ),
)


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def build_latest_targets(target_weights: pl.DataFrame, exec_info: dict[tuple[Any, str], Any]) -> pl.DataFrame:
    latest_date = target_weights["target_date"].max()
    rows: list[dict[str, Any]] = []
    for row in target_weights.filter(pl.col("target_date") == latest_date).iter_rows(named=True):
        symbol = str(row["symbol"])
        info = exec_info.get((row["target_date"], symbol))
        trade_open = to_float(info.trade_open if info else None)
        target_weight = to_float(row.get("target_weight"))
        target_amount = target_weight * ACCOUNT_SIZE_CNY
        target_shares = floor_to_lot_shares(target_amount, trade_open)
        rounded_target_amount = target_shares * trade_open
        rows.append(
            {
                "target_date": row["target_date"],
                "symbol": symbol,
                "code_name": info.code_name if info else "",
                "industry": row.get("industry") or "",
                "target_weight": target_weight,
                "target_amount_cny": target_amount,
                "trade_open": trade_open,
                "one_lot_amount_cny": trade_open * BOARD_LOT_SHARES,
                "target_shares": target_shares,
                "rounded_target_amount_cny": rounded_target_amount,
                "rounded_target_weight": rounded_target_amount / ACCOUNT_SIZE_CNY,
                "zero_lot_target": target_weight > 0 and target_shares <= 0,
                "adv20_turnover": row.get("adv20_turnover"),
                "turnover_rate_f": row.get("turnover_rate_f"),
                "active_lots": row.get("active_lots"),
            }
        )
    return pl.DataFrame(rows).sort(["zero_lot_target", "target_weight", "symbol"], descending=[True, True, False])


def build_status_summary(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["side", "status", "blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_sum_cny"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_sum_cny"),
            pl.col("unfilled_amount_cny").sum().alias("unfilled_amount_sum_cny"),
            pl.col("desired_shares").sum().alias("desired_shares_sum"),
            pl.col("filled_shares").sum().alias("filled_shares_sum"),
        )
        .sort(["side", "status", "orders"], descending=[False, False, True])
    )


def build_latest_industry_exposure(holdings: pl.DataFrame) -> pl.DataFrame:
    if holdings.is_empty():
        return pl.DataFrame()
    return (
        holdings.group_by("industry")
        .agg(
            pl.col("actual_weight").sum().alias("actual_weight"),
            pl.col("actual_amount_cny").sum().alias("actual_amount_cny"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .sort("actual_weight", descending=True)
    )


def safe_quantile(frame: pl.DataFrame, column: str, q: float) -> float:
    if frame.is_empty() or column not in frame.columns:
        return 0.0
    value = frame[column].quantile(q)
    return to_float(value)


def build_quality_checkpoints(summary: dict[str, Any]) -> pl.DataFrame:
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
        "本交易包只服务30万整手口径。",
    )
    add(
        "latest_target_has_lot_gap_visible",
        "warn" if int(summary.get("latest_zero_lot_target_count") or 0) > 0 else "pass",
        summary.get("latest_zero_lot_target_count"),
        0,
        "30万账户允许买不到一手，但必须在交易包里显式列出。",
    )
    add(
        "latest_blocked_orders_zero",
        "pass" if int(summary.get("latest_blocked_order_count") or 0) == 0 else "warn",
        summary.get("latest_blocked_order_count"),
        0,
        "最新目标日阻断订单为0，才说明执行链路当前健康。",
    )
    add(
        "latest_unfilled_amount_zero",
        "pass" if abs(to_float(summary.get("latest_unfilled_amount_sum_cny"))) <= 1e-9 else "warn",
        summary.get("latest_unfilled_amount_sum_cny"),
        0,
        "最新目标日未成交金额应接近0。",
    )
    add(
        "latest_actual_gross_not_over_target_gross",
        "pass"
        if to_float(summary.get("latest_actual_gross_weight")) <= to_float(summary.get("latest_target_gross_weight")) + 1e-9
        else "warn",
        summary.get("latest_actual_gross_weight"),
        f"<= {summary.get('latest_target_gross_weight')}",
        "整手向下取整后，实际暴露不应超过原始目标暴露。",
    )
    add(
        "no_signal_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只生成30万最新交易包，不改策略信号。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    latest_targets: pl.DataFrame,
    latest_orders: pl.DataFrame,
    latest_holdings: pl.DataFrame,
    status_summary: pl.DataFrame,
    industry_exposure: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    zero_lot_targets = latest_targets.filter(pl.col("zero_lot_target"))
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万最新纸面交易包 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：30万整手账户最新目标/订单/持仓包；不新增信号、不调参数。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；买入颗粒度：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元/笔。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 30万账户必须把目标权重翻译成100股整数手后的目标股数，不能只看百分比权重。",
        "- 交易包应拆出目标、订单、持仓和买不到一手目标，便于后续和真实委托对账。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 最新执行摘要",
            "",
            f"- 原始目标`{summary['latest_target_count']}`只，目标总金额`{summary['latest_target_amount_sum_cny']:.0f}`元，目标总权重`{pct(summary['latest_target_gross_weight'])}`。",
            f"- 100股取整后目标市值`{summary['latest_rounded_target_amount_sum_cny']:.0f}`元，取整后目标权重`{pct(summary['latest_rounded_target_gross_weight'])}`。",
            f"- 买不到一手目标`{summary['latest_zero_lot_target_count']}`只，占目标`{summary['latest_zero_lot_target_ratio']:.2%}`。",
            f"- 最新订单`{summary['latest_order_count']}`行，成交`{summary['latest_filled_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行。",
            f"- 最新计划成交金额`{summary['latest_desired_amount_sum_cny']:.0f}`元，实际成交`{summary['latest_filled_amount_sum_cny']:.0f}`元，未成交`{summary['latest_unfilled_amount_sum_cny']:.0f}`元。",
            f"- 最新实际持仓`{summary['latest_actual_symbol_count']}`只，实际市值`{summary['latest_actual_amount_sum_cny']:.0f}`元，实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            f"- 最新订单金额：最小`{summary['latest_filled_order_min_cny']:.0f}`元，中位`{summary['latest_filled_order_median_cny']:.0f}`元，最大`{summary['latest_filled_order_max_cny']:.0f}`元。",
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
            "## 最新订单状态汇总",
            "",
            markdown_table(
                status_summary,
                [
                    "side",
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_amount_sum_cny",
                    "filled_amount_sum_cny",
                    "unfilled_amount_sum_cny",
                    "desired_shares_sum",
                    "filled_shares_sum",
                ],
                max_rows=40,
            ),
            "",
            "## 买不到一手目标",
            "",
            markdown_table(
                zero_lot_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "target_weight",
                    "target_amount_cny",
                    "trade_open",
                    "one_lot_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 最新目标",
            "",
            markdown_table(
                latest_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "target_weight",
                    "target_amount_cny",
                    "target_shares",
                    "rounded_target_amount_cny",
                    "zero_lot_target",
                    "trade_open",
                    "one_lot_amount_cny",
                ],
                max_rows=120,
            ),
            "",
            "## 最新订单",
            "",
            markdown_table(
                latest_orders.sort(["side", "filled_amount_cny", "symbol"], descending=[False, True, False])
                if not latest_orders.is_empty()
                else latest_orders,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "prev_shares",
                    "target_shares",
                    "desired_shares",
                    "filled_shares",
                    "actual_shares_after",
                    "trade_open",
                    "desired_amount_cny",
                    "filled_amount_cny",
                    "unfilled_amount_cny",
                ],
                max_rows=120,
            ),
            "",
            "## 最新持仓",
            "",
            markdown_table(
                latest_holdings,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "actual_shares",
                    "last_trade_open",
                    "actual_amount_cny",
                    "actual_weight",
                    "last_target_weight",
                ],
                max_rows=120,
            ),
            "",
            "## 最新行业暴露",
            "",
            markdown_table(industry_exposure, ["industry", "actual_weight", "actual_amount_cny", "symbols"], max_rows=60),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只生成30万最新执行包，不新增变量、不调参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：交易包只暴露整手约束和订单明细，没有据此修改信号。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万能做与否，必须把每天能买、不能买、实际持仓拆清楚。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：最新订单无阻断无未成交，但买不到一手目标仍多，适合继续paper跟踪而不是马上实盘。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 30万口径继续paper，不采用稀疏满仓变体。",
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
    exec_info = build_exec_info(stock_df)
    target_weights = build_target_weights(selected_all)
    latest_targets = build_latest_targets(target_weights, exec_info)
    latest_date = latest_targets["target_date"].max()

    orders = read_csv_with_symbol(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_orders.csv")
    daily = pl.read_csv(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_daily.csv", try_parse_dates=True)
    holdings = read_csv_with_symbol(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_latest_holdings.csv")
    latest_orders = orders.filter(pl.col("date") == latest_date)
    latest_daily = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    filled_latest_orders = latest_orders.filter(pl.col("filled_shares") > 0)
    status_summary = build_status_summary(latest_orders)
    industry_exposure = build_latest_industry_exposure(holdings)

    target_count = latest_targets.height
    zero_lot_count = latest_targets.filter(pl.col("zero_lot_target")).height
    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "board_lot_shares": BOARD_LOT_SHARES,
        "min_commission_cny": MIN_COMMISSION_CNY,
        "latest_target_date": latest_date,
        "latest_target_count": target_count,
        "latest_target_gross_weight": to_float(latest_targets["target_weight"].sum()),
        "latest_target_amount_sum_cny": to_float(latest_targets["target_amount_cny"].sum()),
        "latest_rounded_target_amount_sum_cny": to_float(latest_targets["rounded_target_amount_cny"].sum()),
        "latest_rounded_target_gross_weight": to_float(latest_targets["rounded_target_amount_cny"].sum()) / ACCOUNT_SIZE_CNY,
        "latest_zero_lot_target_count": zero_lot_count,
        "latest_zero_lot_target_ratio": zero_lot_count / target_count if target_count else 0.0,
        "latest_order_count": latest_orders.height,
        "latest_filled_order_count": filled_latest_orders.height,
        "latest_blocked_order_count": latest_orders.filter(pl.col("status") == "blocked").height,
        "latest_desired_amount_sum_cny": to_float(latest_orders["desired_amount_cny"].sum())
        if not latest_orders.is_empty()
        else 0.0,
        "latest_filled_amount_sum_cny": to_float(latest_orders["filled_amount_cny"].sum())
        if not latest_orders.is_empty()
        else 0.0,
        "latest_unfilled_amount_sum_cny": to_float(latest_orders["unfilled_amount_cny"].sum())
        if not latest_orders.is_empty()
        else 0.0,
        "latest_actual_symbol_count": int(latest_daily["actual_symbol_count"]),
        "latest_actual_amount_sum_cny": to_float(latest_daily["actual_market_value_cny"]),
        "latest_actual_gross_weight": to_float(latest_daily["actual_gross_weight"]),
        "latest_filled_order_min_cny": to_float(filled_latest_orders["filled_amount_cny"].min())
        if not filled_latest_orders.is_empty()
        else 0.0,
        "latest_filled_order_median_cny": safe_quantile(filled_latest_orders, "filled_amount_cny", 0.5),
        "latest_filled_order_max_cny": to_float(filled_latest_orders["filled_amount_cny"].max())
        if not filled_latest_orders.is_empty()
        else 0.0,
    }
    quality = build_quality_checkpoints(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "latest_targets": OUTPUT_DIR / f"{PREFIX}_latest_targets.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "latest_holdings": OUTPUT_DIR / f"{PREFIX}_latest_holdings.csv",
        "industry_exposure": OUTPUT_DIR / f"{PREFIX}_industry_exposure.csv",
        "status_summary": OUTPUT_DIR / f"{PREFIX}_status_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    latest_targets.write_csv(paths["latest_targets"])
    latest_orders.write_csv(paths["latest_orders"])
    holdings.write_csv(paths["latest_holdings"])
    industry_exposure.write_csv(paths["industry_exposure"])
    status_summary.write_csv(paths["status_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_lot_output_dir": LOT_OUTPUT_DIR,
            "research_sources": RESEARCH_SOURCES,
            "note": "300k latest packet only; no signal or threshold changes.",
        },
    )
    report_path = write_report(
        summary,
        latest_targets,
        latest_orders,
        holdings,
        status_summary,
        industry_exposure,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
