from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


PAPER_SCENARIO: str = "age4_daily_exclude_volume_dry"
LEDGER_VERSION: str = "stock_range_reversion_liquid_q3_paper_ledger_v1"

V3_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
).expanduser().resolve()
V3_PREFIX: str = "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality"

LATEST_PACKET_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_latest_paper_packet_2018_2026"
).expanduser().resolve()
LATEST_PACKET_PREFIX: str = "stock_range_reversion_liquid_q3_latest_paper_packet_v1"

FALLBACK_AUDIT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_v3_fallback_audit_2018_2026"
).expanduser().resolve()
FALLBACK_AUDIT_PREFIX: str = "stock_range_reversion_liquid_q3_v3_fallback_audit_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_ledger_2018_2026"
).expanduser().resolve()

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    ("Zipline API / blotter and daily performance", "https://flounderteam.github.io/refs/zipline/appendix.html"),
    ("Zipline 3.0 API / SimulationBlotter", "https://zipline.ml4trading.io/api-reference.html"),
    ("Backtrader analyzers", "https://www.backtrader.com/docu/analyzers/analyzers/"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    if not text:
        return None
    return datetime.fromisoformat(text[:10]).date()


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def build_daily_ledger(daily: pl.DataFrame, latest_target_date: date | None) -> pl.DataFrame:
    latest_expr = pl.lit(False) if latest_target_date is None else pl.col("date") == pl.lit(latest_target_date)
    return (
        daily.sort("date")
        .with_columns(
            pl.lit(LEDGER_VERSION).alias("ledger_version"),
            pl.lit("backfilled_from_v3_paper_tracking").alias("ledger_source"),
            pl.when(pl.col("filled_abs_change") > 0)
            .then(pl.lit("rebalance"))
            .otherwise(pl.lit("hold"))
            .alias("paper_event_type"),
            latest_expr.alias("is_latest_target_date"),
            pl.col("strategy_equity").cum_max().alias("running_peak_equity"),
            pl.col("turnover_cost_ret").cum_sum().alias("cumulative_cost_drag"),
        )
        .with_columns(
            (pl.col("strategy_equity") / pl.col("running_peak_equity") - 1).alias("recomputed_drawdown")
        )
    )


def build_order_ledger(orders: pl.DataFrame) -> pl.DataFrame:
    return (
        orders.sort(["date", "symbol", "side"])
        .with_row_index("ledger_order_seq", offset=1)
        .with_columns(
            pl.lit(LEDGER_VERSION).alias("ledger_version"),
            pl.lit("backfilled_from_v3_paper_tracking").alias("ledger_source"),
        )
        .with_columns(
            pl.concat_str(
                [
                    pl.col("date").dt.strftime("%Y%m%d"),
                    pl.col("symbol").cast(pl.Utf8),
                    pl.col("side").cast(pl.Utf8),
                    pl.col("ledger_order_seq").cast(pl.Utf8),
                ],
                separator="-",
            ).alias("paper_order_id")
        )
        .select(
            [
                "ledger_version",
                "ledger_source",
                "ledger_order_seq",
                "paper_order_id",
                *orders.columns,
            ]
        )
    )


def summarize_period(daily_ledger: pl.DataFrame, period_name: str, period_expr: pl.Expr) -> pl.DataFrame:
    return (
        daily_ledger.with_columns(period_expr.alias(period_name))
        .group_by(period_name)
        .agg(
            pl.col("date").min().alias("start_date"),
            pl.col("date").max().alias("end_date"),
            pl.len().alias("trading_days"),
            ((pl.col("strategy_daily_ret") + 1).product() - 1).alias("period_return"),
            pl.col("strategy_equity").last().alias("end_equity"),
            pl.col("strategy_drawdown").min().alias("worst_drawdown_to_date"),
            pl.col("desired_abs_change").sum().alias("desired_abs_change_sum"),
            pl.col("filled_abs_change").sum().alias("filled_abs_change_sum"),
            pl.col("unfilled_abs_change").sum().alias("unfilled_abs_change_sum"),
            pl.col("blocked_order_count").sum().alias("blocked_order_count_sum"),
            pl.col("partial_order_count").sum().alias("partial_order_count_sum"),
            pl.col("turnover_cost_ret").sum().alias("cost_drag_sum"),
            (pl.col("strategy_daily_ret") > 0).mean().alias("daily_win_rate"),
        )
        .with_columns(
            pl.when(pl.col("desired_abs_change_sum") > 0)
            .then(pl.col("filled_abs_change_sum") / pl.col("desired_abs_change_sum"))
            .otherwise(None)
            .alias("period_fill_ratio")
        )
        .sort(period_name)
    )


def build_quality_checkpoints(
    v3_summary: dict[str, Any],
    latest_summary: dict[str, Any],
    fallback_summary: dict[str, Any] | None,
    daily_ledger: pl.DataFrame,
    order_ledger: pl.DataFrame,
) -> pl.DataFrame:
    latest_target_date = parse_date(v3_summary.get("latest_target_date"))
    latest_packet_target_date = parse_date(latest_summary.get("latest_target_date"))
    latest_signal_date = parse_date(latest_summary.get("latest_signal_date"))
    today = datetime.now().date()
    lag_days = (today - latest_target_date).days if latest_target_date else None
    rows: list[dict[str, Any]] = []

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
        "daily_row_count_matches_summary",
        "pass" if int(v3_summary.get("days", -1)) == daily_ledger.height else "fail",
        daily_ledger.height,
        v3_summary.get("days"),
        "日账本行数应等于v3 summary中的days。",
    )
    add(
        "order_row_count_matches_summary",
        "pass" if int(v3_summary.get("order_count", -1)) == order_ledger.height else "fail",
        order_ledger.height,
        v3_summary.get("order_count"),
        "订单账本行数应等于v3 summary中的order_count。",
    )
    add(
        "latest_target_date_matches_packet",
        "pass" if latest_target_date == latest_packet_target_date else "fail",
        latest_packet_target_date,
        latest_target_date,
        "latest packet和v3全历史账本应指向同一最新目标执行日。",
    )
    add(
        "latest_order_count_matches_packet",
        "pass" if int(latest_summary.get("latest_order_count", -1)) == int(v3_summary.get("latest_order_count", -2)) else "fail",
        latest_summary.get("latest_order_count"),
        v3_summary.get("latest_order_count"),
        "latest packet订单行数应等于v3 summary中的最新订单行数。",
    )
    add(
        "overall_fill_ratio_above_99pct",
        "pass" if float(v3_summary.get("overall_fill_ratio", 0.0)) >= 0.99 else "warn",
        v3_summary.get("overall_fill_ratio"),
        ">=0.99",
        "纸面成交填充率低于99%时，需要优先查容量和阻断原因。",
    )
    add(
        "latest_blocked_orders_zero",
        "pass" if int(latest_summary.get("latest_blocked_order_count", -1)) == 0 else "warn",
        latest_summary.get("latest_blocked_order_count"),
        0,
        "最新目标日若有阻断订单，需要进入人工执行检查。",
    )
    if fallback_summary is None:
        add(
            "fallback_audit_available",
            "warn",
            "missing",
            "available",
            "没有找到第256阶段fallback审计summary，ledger仍可生成但缺少一条防前视证据。",
        )
    else:
        add(
            "fallback_audit_pass_ratio_100pct",
            "pass" if float(fallback_summary.get("audit_pass_ratio", 0.0)) == 1.0 else "fail",
            fallback_summary.get("audit_pass_ratio"),
            1.0,
            "fallback订单全量复算应保持100%通过。",
        )
    if latest_signal_date and latest_target_date and latest_signal_date > latest_target_date:
        add(
            "latest_signal_after_target_warning",
            "warn",
            f"{latest_signal_date}>{latest_target_date}",
            "signal_date<=target_date",
            "尾部信号审计日晚于可执行目标日，执行以latest_target_date为准。",
        )
    else:
        add(
            "latest_signal_after_target_warning",
            "pass",
            f"{latest_signal_date}<={latest_target_date}",
            "signal_date<=target_date",
            "尾部信号和目标日没有倒挂。",
        )
    if lag_days is None:
        add("data_tail_calendar_lag", "warn", None, "<=7 calendar days", "无法识别最新目标执行日。")
    else:
        lag_status = "pass" if lag_days <= 7 else "warn" if lag_days <= 15 else "fail"
        add(
            "data_tail_calendar_lag",
            lag_status,
            lag_days,
            "<=7 calendar days preferred",
            "这是数据时效检查，不是策略优劣判断；超过7天应优先补数据再追加纸面记录。",
        )
    return pl.DataFrame(rows)


def build_latest_snapshot(
    v3_summary: dict[str, Any],
    latest_summary: dict[str, Any],
    quality_checkpoints: pl.DataFrame,
) -> pl.DataFrame:
    fail_count = quality_checkpoints.filter(pl.col("status") == "fail").height
    warn_count = quality_checkpoints.filter(pl.col("status") == "warn").height
    pass_count = quality_checkpoints.filter(pl.col("status") == "pass").height
    return pl.DataFrame(
        [
            {
                "ledger_version": LEDGER_VERSION,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "scenario": PAPER_SCENARIO,
                "latest_signal_date": latest_summary.get("latest_signal_date"),
                "latest_target_date": v3_summary.get("latest_target_date"),
                "final_equity": v3_summary.get("final_equity"),
                "total_return": v3_summary.get("total_return"),
                "max_drawdown": v3_summary.get("max_drawdown"),
                "sharpe": v3_summary.get("sharpe"),
                "overall_fill_ratio": v3_summary.get("overall_fill_ratio"),
                "order_count": v3_summary.get("order_count"),
                "blocked_order_count": v3_summary.get("blocked_order_count"),
                "latest_order_count": latest_summary.get("latest_order_count"),
                "latest_blocked_order_count": latest_summary.get("latest_blocked_order_count"),
                "latest_desired_abs_change": latest_summary.get("latest_desired_abs_change"),
                "latest_filled_abs_change": latest_summary.get("latest_filled_abs_change"),
                "quality_pass_count": pass_count,
                "quality_warn_count": warn_count,
                "quality_fail_count": fail_count,
            }
        ]
    )


def write_report(
    summary: dict[str, Any],
    latest_snapshot: pl.DataFrame,
    quality_checkpoints: pl.DataFrame,
    yearly_ledger: pl.DataFrame,
    monthly_ledger: pl.DataFrame,
    daily_ledger: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    latest = latest_snapshot.to_dicts()[0]
    failed = quality_checkpoints.filter(pl.col("status") == "fail")
    warned = quality_checkpoints.filter(pl.col("status") == "warn")
    recent_daily = daily_ledger.tail(15)
    recent_monthly = monthly_ledger.tail(12)
    lines = [
        "# 股票震荡liquid_q3 paper ledger v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把v3纸面订单、日汇总、latest packet和fallback审计整理成可复验账本；不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        f"- 最新信号日：`{latest['latest_signal_date']}`；最新目标执行日：`{latest['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Zipline/Backtrader类框架都把订单、成交、持仓、收益和分析器分层；纸面跟踪也应该先有账本，再谈策略升级。",
        "- 本阶段不复用外部框架，只吸收其账本思想：订单流水、日收益流水、周期汇总、质量检查点分开落盘。",
        "- 直觉判断：能穿越周期的系统，通常不是一条更漂亮的历史曲线，而是每次新数据进来都能留下无法抵赖的流水。",
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
            f"- 日账本`{summary['daily_rows']}`行，订单账本`{summary['order_rows']}`行。",
            f"- 期末权益`{latest['final_equity']:.4f}`，总收益`{pct(latest['total_return'])}`，最大回撤`{pct(latest['max_drawdown'])}`，Sharpe `{latest['sharpe']:.2f}`。",
            f"- 整体成交填充率`{pct(latest['overall_fill_ratio'])}`，全历史阻断订单`{latest['blocked_order_count']}`行。",
            f"- 最新目标日订单`{latest['latest_order_count']}`行，阻断`{latest['latest_blocked_order_count']}`行，计划换仓`{pct(latest['latest_desired_abs_change'])}`，可成交`{pct(latest['latest_filled_abs_change'])}`。",
            f"- 质量检查：通过`{latest['quality_pass_count']}`项，警告`{latest['quality_warn_count']}`项，失败`{latest['quality_fail_count']}`项。",
            "",
            "## 质量检查点",
            "",
            markdown_table(quality_checkpoints, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 年度账本",
            "",
            markdown_table(
                yearly_ledger,
                [
                    "year",
                    "start_date",
                    "end_date",
                    "trading_days",
                    "period_return",
                    "end_equity",
                    "worst_drawdown_to_date",
                    "desired_abs_change_sum",
                    "filled_abs_change_sum",
                    "period_fill_ratio",
                    "blocked_order_count_sum",
                    "cost_drag_sum",
                    "daily_win_rate",
                ],
                max_rows=20,
            ),
            "",
            "## 最近12个月账本",
            "",
            markdown_table(
                recent_monthly,
                [
                    "month",
                    "start_date",
                    "end_date",
                    "trading_days",
                    "period_return",
                    "end_equity",
                    "worst_drawdown_to_date",
                    "desired_abs_change_sum",
                    "filled_abs_change_sum",
                    "period_fill_ratio",
                    "blocked_order_count_sum",
                    "cost_drag_sum",
                    "daily_win_rate",
                ],
                max_rows=12,
            ),
            "",
            "## 最近15个交易日",
            "",
            markdown_table(
                recent_daily,
                [
                    "date",
                    "paper_event_type",
                    "target_symbol_count",
                    "actual_symbol_count",
                    "target_gross_weight",
                    "actual_gross_weight",
                    "desired_abs_change",
                    "filled_abs_change",
                    "fill_ratio",
                    "blocked_order_count",
                    "strategy_equity",
                    "strategy_drawdown",
                    "is_latest_target_date",
                ],
                max_rows=15,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只把既有v3纸面结果整理成账本，不新增预测变量、不调整过滤阈值、不选择更好收益窗口。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：ledger本身不能改善历史收益，只会暴露最新目标、订单阻断、数据尾部和审计状态。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：股票震荡候选已经进入纸面跟踪阶段，必须先建立可追加、可复验、可对账的流水。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：账本已把订单、日收益、月/年汇总和质量检查拆开，后续每次数据更新都能直接比较新增样本外表现。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- paper ledger作为后续股票震荡线新增数据后的固定记录入口。",
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
    v3_summary_path = V3_DIR / f"{V3_PREFIX}_summary.json"
    v3_daily_path = V3_DIR / f"{V3_PREFIX}_daily_summary.csv"
    v3_orders_path = V3_DIR / f"{V3_PREFIX}_paper_orders.csv"
    latest_summary_path = LATEST_PACKET_DIR / f"{LATEST_PACKET_PREFIX}_summary.json"
    fallback_summary_path = FALLBACK_AUDIT_DIR / f"{FALLBACK_AUDIT_PREFIX}_summary.json"

    v3_summary = load_json(v3_summary_path)
    latest_summary = load_json(latest_summary_path)
    fallback_summary = load_json(fallback_summary_path) if fallback_summary_path.exists() else None
    daily = pl.read_csv(v3_daily_path, try_parse_dates=True)
    orders = read_csv_with_symbol(v3_orders_path)

    latest_target_date = parse_date(v3_summary.get("latest_target_date"))
    daily_ledger = build_daily_ledger(daily, latest_target_date)
    order_ledger = build_order_ledger(orders)
    monthly_ledger = summarize_period(daily_ledger, "month", pl.col("date").dt.strftime("%Y-%m"))
    yearly_ledger = summarize_period(daily_ledger, "year", pl.col("date").dt.strftime("%Y"))
    quality_checkpoints = build_quality_checkpoints(
        v3_summary,
        latest_summary,
        fallback_summary,
        daily_ledger,
        order_ledger,
    )
    latest_snapshot = build_latest_snapshot(v3_summary, latest_summary, quality_checkpoints)
    summary = {
        "ledger_version": LEDGER_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "daily_rows": daily_ledger.height,
        "order_rows": order_ledger.height,
        "month_rows": monthly_ledger.height,
        "year_rows": yearly_ledger.height,
        "latest_target_date": v3_summary.get("latest_target_date"),
        "latest_signal_date": latest_summary.get("latest_signal_date"),
        "final_equity": v3_summary.get("final_equity"),
        "total_return": v3_summary.get("total_return"),
        "max_drawdown": v3_summary.get("max_drawdown"),
        "sharpe": v3_summary.get("sharpe"),
        "overall_fill_ratio": v3_summary.get("overall_fill_ratio"),
        "quality_pass_count": quality_checkpoints.filter(pl.col("status") == "pass").height,
        "quality_warn_count": quality_checkpoints.filter(pl.col("status") == "warn").height,
        "quality_fail_count": quality_checkpoints.filter(pl.col("status") == "fail").height,
    }
    paths = {
        "report": OUTPUT_DIR / f"{LEDGER_VERSION}_report.md",
        "summary": OUTPUT_DIR / f"{LEDGER_VERSION}_summary.json",
        "daily_ledger": OUTPUT_DIR / f"{LEDGER_VERSION}_daily_ledger.csv",
        "order_ledger": OUTPUT_DIR / f"{LEDGER_VERSION}_order_ledger.csv",
        "monthly_ledger": OUTPUT_DIR / f"{LEDGER_VERSION}_monthly_ledger.csv",
        "yearly_ledger": OUTPUT_DIR / f"{LEDGER_VERSION}_yearly_ledger.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{LEDGER_VERSION}_quality_checkpoints.csv",
        "latest_snapshot": OUTPUT_DIR / f"{LEDGER_VERSION}_latest_snapshot.csv",
        "meta": OUTPUT_DIR / f"{LEDGER_VERSION}_meta.json",
    }
    daily_ledger.write_csv(paths["daily_ledger"])
    order_ledger.write_csv(paths["order_ledger"])
    monthly_ledger.write_csv(paths["monthly_ledger"])
    yearly_ledger.write_csv(paths["yearly_ledger"])
    quality_checkpoints.write_csv(paths["quality_checkpoints"])
    latest_snapshot.write_csv(paths["latest_snapshot"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "ledger_version": LEDGER_VERSION,
            "paper_scenario": PAPER_SCENARIO,
            "source_v3_dir": str(V3_DIR),
            "source_latest_packet_dir": str(LATEST_PACKET_DIR),
            "source_fallback_audit_dir": str(FALLBACK_AUDIT_DIR),
            "research_sources": RESEARCH_SOURCES,
            "note": "Ledger only reorganizes existing v3 paper-tracking results. It does not change signals, parameters, or historical returns.",
        },
    )
    report_path = write_report(
        summary,
        latest_snapshot,
        quality_checkpoints,
        yearly_ledger,
        monthly_ledger,
        daily_ledger,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
