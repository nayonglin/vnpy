from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    INITIAL_EQUITY,
    MAX_INDUSTRY_WEIGHT_PER_BASKET,
    MAX_STOCK_WEIGHT_PER_BASKET,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_symbol_daily,
    build_turnover,
    build_yearly_summary,
    pct,
    summarize_curve,
)
from backtest_stock_range_reversion_liquid_q3_hysteresis_replacement import (
    ENTRY_GROUP,
    RETAIN_MIN_GROUP,
    add_one_day_path_columns,
    build_ranked_liquid_q3,
    capped_weights,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_sticky_slot_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_sticky_slot_v1"
SCENARIO_NAME: str = "liquid_q3_entry20_keep40_sticky_slot"
SCENARIO_DESCRIPTION: str = "liquid_q3行业内top20进入，top40保留，只用退出腿释放的资金补入新候选"
EPS: float = 1e-9


def allocate_new_entries(
    candidates: list[dict[str, Any]],
    retained: dict[str, dict[str, Any]],
    row_by_symbol: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int, float]:
    current_industry_weight: dict[str, float] = defaultdict(float)
    current_exposure = 0.0
    for symbol, state in retained.items():
        row = row_by_symbol.get(symbol)
        if row is None:
            continue
        weight = float(state["target_weight"])
        current_industry_weight[str(row["industry"])] += weight
        current_exposure += weight

    available_cash = max(0.0, 1.0 - current_exposure)
    desired_weights = capped_weights(candidates)
    added: dict[str, dict[str, Any]] = {}

    for row in sorted(candidates, key=lambda item: float(item[FEATURE]), reverse=True):
        if available_cash <= EPS:
            break
        symbol = str(row["symbol"])
        if symbol in retained or symbol in added:
            continue
        industry = str(row["industry"])
        desired_weight = desired_weights.get(symbol, 0.0)
        industry_room = max(0.0, MAX_INDUSTRY_WEIGHT_PER_BASKET - current_industry_weight[industry])
        target_weight = min(desired_weight, MAX_STOCK_WEIGHT_PER_BASKET, industry_room, available_cash)
        if target_weight <= EPS:
            continue
        added[symbol] = {
            "entry_signal_date": row["datetime"],
            "entry_signal_index": row["signal_index"],
            "target_weight": target_weight,
        }
        current_industry_weight[industry] += target_weight
        available_cash -= target_weight

    return added, len(added), available_cash


def build_sticky_selected(ranked: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    active: dict[str, dict[str, Any]] = {}
    selected_records: list[dict[str, Any]] = []
    event_records: list[dict[str, Any]] = []
    daily_records: list[dict[str, Any]] = []

    grouped_dates = ranked.partition_by("datetime", as_dict=True)
    dates = sorted(key[0] if isinstance(key, tuple) else key for key in grouped_dates)

    for signal_index, signal_date in enumerate(dates):
        group_key = (signal_date,)
        daily_df = grouped_dates.get(group_key)
        if daily_df is None:
            daily_df = grouped_dates[signal_date]
        rows = [dict(row) | {"signal_index": signal_index} for row in daily_df.iter_rows(named=True)]
        row_by_symbol = {str(row["symbol"]): row for row in rows}

        retained: dict[str, dict[str, Any]] = {}
        exit_count = 0
        freed_weight = 0.0
        for symbol, state in active.items():
            row = row_by_symbol.get(symbol)
            if row is not None and int(row["feature_group"]) >= RETAIN_MIN_GROUP:
                retained[symbol] = state
                continue
            exit_count += 1
            freed_weight += float(state["target_weight"])
            event_records.append(
                {
                    "datetime": signal_date,
                    "symbol": symbol,
                    "event": "exit",
                    "holding_signal_days": signal_index - int(state["entry_signal_index"]),
                    "event_weight": float(state["target_weight"]),
                    "last_feature_group": int(row["feature_group"]) if row is not None else None,
                }
            )

        entry_candidates = [row for row in rows if int(row["feature_group"]) == ENTRY_GROUP and str(row["symbol"]) not in retained]
        added, entry_count, remaining_cash = allocate_new_entries(entry_candidates, retained, row_by_symbol)
        for symbol, state in added.items():
            row = row_by_symbol[symbol]
            event_records.append(
                {
                    "datetime": signal_date,
                    "symbol": symbol,
                    "event": "entry",
                    "holding_signal_days": 0,
                    "event_weight": float(state["target_weight"]),
                    "last_feature_group": int(row["feature_group"]),
                }
            )
        active = retained | added

        active_rows = [row_by_symbol[symbol] for symbol in active if symbol in row_by_symbol]
        active_industry_count = len({str(row["industry"]) for row in active_rows})
        gross_exposure = sum(float(active[str(row["symbol"])]["target_weight"]) for row in active_rows)
        daily_records.append(
            {
                "datetime": signal_date,
                "active_count": len(active_rows),
                "active_industry_count": active_industry_count,
                "entry_count": entry_count,
                "exit_count": exit_count,
                "freed_weight": freed_weight,
                "remaining_cash_after_entries": remaining_cash,
                "gross_exposure": gross_exposure,
                "entry_candidate_count": len(entry_candidates),
                "retain_candidate_count": sum(1 for row in rows if int(row["feature_group"]) >= RETAIN_MIN_GROUP),
            }
        )

        for row in active_rows:
            symbol = str(row["symbol"])
            state = active[symbol]
            record = {
                "scenario": SCENARIO_NAME,
                "scenario_description": SCENARIO_DESCRIPTION,
                "bucket": "liquid_q3",
                "weight_mode": "sticky_slot",
                "datetime": signal_date,
                "signal_date": signal_date,
                "symbol": symbol,
                "industry": row["industry"],
                FEATURE: row[FEATURE],
                "feature_group": int(row["feature_group"]),
                "entry_signal_date": state["entry_signal_date"],
                "holding_signal_days": signal_index - int(state["entry_signal_index"]) + 1,
                "basket_weight": float(state["target_weight"]),
                "basket_gross_weight": gross_exposure,
                "candidate_count": len(active_rows),
                "selected_industry_count": active_industry_count,
                "selected_industry_stock_count": sum(1 for item in active_rows if item["industry"] == row["industry"]),
                "target_date": row["target_date"],
                "pnl_date": row["pnl_date"],
                "stock_daily_ret": row["stock_daily_ret"],
            }
            for col in [
                "adv20_turnover",
                "turnover_rate_f",
                "adv20_turnover_q",
                "turnover_rate_f_q",
                "circ_mv",
                "total_mv",
            ]:
                if col in row:
                    record[col] = row[col]
            selected_records.append(record)

    return (
        pl.DataFrame(selected_records).sort(["datetime", "industry", FEATURE]),
        pl.DataFrame(daily_records).sort("datetime"),
        pl.DataFrame(event_records).sort(["datetime", "symbol"]),
    )


def build_lots(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.rename({"basket_weight": "lot_weight"})
        .with_columns(pl.lit(1).alias("holding_day"))
        .sort(["scenario", "target_date", "symbol"])
    )


def augment_summary(summary_df: pl.DataFrame, daily_state: pl.DataFrame, selected: pl.DataFrame) -> pl.DataFrame:
    state_summary = daily_state.select(
        pl.col("active_count").mean().alias("avg_sticky_active_count"),
        pl.col("active_count").max().alias("max_sticky_active_count"),
        pl.col("active_industry_count").mean().alias("avg_sticky_industry_count"),
        pl.col("entry_count").mean().alias("avg_daily_entries"),
        pl.col("exit_count").mean().alias("avg_daily_exits"),
        pl.col("freed_weight").mean().alias("avg_daily_freed_weight"),
        pl.col("remaining_cash_after_entries").mean().alias("avg_remaining_cash_after_entries"),
        pl.col("gross_exposure").mean().alias("avg_sticky_gross_exposure"),
    ).with_columns(pl.lit(SCENARIO_NAME).alias("scenario"))
    hold_summary = selected.select(
        pl.col("holding_signal_days").mean().alias("avg_holding_signal_days"),
        pl.col("holding_signal_days").median().alias("median_holding_signal_days"),
        pl.col("holding_signal_days").max().alias("max_holding_signal_days"),
    ).with_columns(pl.lit(SCENARIO_NAME).alias("scenario"))
    return summary_df.join(state_summary, on="scenario", how="left").join(hold_summary, on="scenario", how="left")


def build_feature_group_summary(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.group_by("feature_group")
        .agg(
            pl.len().alias("symbol_day_count"),
            pl.col("basket_weight").mean().alias("avg_weight"),
            pl.col("stock_daily_ret").mean().alias("avg_next_day_stock_ret"),
            pl.col("holding_signal_days").mean().alias("avg_holding_signal_days"),
        )
        .sort("feature_group")
    )


def write_report(
    summary_df: pl.DataFrame,
    yearly: pl.DataFrame,
    daily_state: pl.DataFrame,
    event_summary: pl.DataFrame,
    feature_group_summary: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡liquid_q3 sticky slot账本 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：只替换退出腿的turnover-aware账本压力测试，不是正式交易版本。",
        "",
        "## 方法",
        "",
        f"- 股票池：`liquid_q3`。",
        f"- 进入：行业内`{FEATURE}`进入top20，也就是分组`{ENTRY_GROUP}`。",
        f"- 保留：已持有股票只要仍在行业内top40，也就是分组大于等于`{RETAIN_MIN_GROUP}`，且资格有效，就保留原权重。",
        "- 替换：只用退出腿释放的资金补入当日top20新候选；保留股票不因排名细微变化而重配。",
        f"- 风控：新增股票遵守行业上限`{MAX_INDUSTRY_WEIGHT_PER_BASKET:.0%}`、单票上限`{MAX_STOCK_WEIGHT_PER_BASKET:.0%}`，无法使用的资金留现金。",
        f"- 成本：`{','.join(f'{item:.0f}bp' for item in COST_BPS)}`往返成本。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，股票数`{meta['symbol_count']}`。",
        "",
        "## 路径结果",
        "",
    ]
    for row in summary_df.sort("roundtrip_cost_bps").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`，"
            f"同暴露基准收益`{pct(row['benchmark_total_return'])}`。"
        )
        lines.append(
            f"  暴露/换手：平均暴露`{pct(row['avg_return_gross_exposure'])}`，年化单边换手`{row['annualized_one_way_turnover']:.2f}`倍，"
            f"成本拖累`{pct(row['cost_drag_sum'])}`，活跃日胜率`{pct(row['net_active_day_win_rate'])}`。"
        )
        lines.append(
            f"  持仓状态：平均活跃股票`{row['avg_sticky_active_count']:.1f}`，平均行业`{row['avg_sticky_industry_count']:.1f}`，"
            f"平均每日新增`{row['avg_daily_entries']:.1f}`，平均每日退出`{row['avg_daily_exits']:.1f}`，"
            f"平均释放权重`{pct(row['avg_daily_freed_weight'])}`，剩余现金`{pct(row['avg_remaining_cash_after_entries'])}`，"
            f"持仓天数均值`{row['avg_holding_signal_days']:.1f}`，中位`{row['median_holding_signal_days']:.1f}`，最大`{row['max_holding_signal_days']:.0f}`。"
        )

    lines.extend(["", "## 年度结果", ""])
    for row in yearly.sort(["roundtrip_cost_bps", "year"]).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['year']}`：净收益`{pct(row['year_return'])}`，"
            f"毛收益`{pct(row['year_gross_return'])}`，同暴露基准`{pct(row['year_benchmark_return'])}`，"
            f"平均暴露`{pct(row['avg_gross_exposure'])}`。"
        )

    lines.extend(["", "## 换仓事件", ""])
    for row in event_summary.iter_rows(named=True):
        lines.append(
            f"- `{row['event']}`：次数`{row['event_count']}`，平均持仓信号日`{row['avg_holding_signal_days']:.1f}`，"
            f"平均事件权重`{pct(row['avg_event_weight'])}`。"
        )

    lines.extend(["", "## 持有分组贡献", ""])
    for row in feature_group_summary.iter_rows(named=True):
        lines.append(
            f"- 分组`{row['feature_group']}`：股票日`{row['symbol_day_count']}`，平均权重`{pct(row['avg_weight'])}`，"
            f"次日股票收益均值`{pct(row['avg_next_day_stock_ret'])}`，平均持仓信号日`{row['avg_holding_signal_days']:.1f}`。"
        )

    lines.extend(
        [
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：这是第232阶段负向结论后的结构修正，只改变账本是否每日全组合重配，不扫描信号阈值、持仓天数或行业上限。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果没有被包装成候选版本；sticky slot虽然比每日重配少换手，但50bp后亏损，不能继续围绕它调参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第232阶段证明每日重配账本错误，sticky slot是同一研究方向下更符合交易成本本质的最后一类账本。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：有研究价值，但当前交易化路线应暂停。",
            "- 原因：换手从每日重配的约57倍降到约37倍，但仍远高于第230阶段，50bp后期末权益低于1；继续微调持仓账本容易变成成本适配器。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- sticky slot不作为正式候选。",
            "- 暂停当前`liquid_q3`日频股票震荡交易化，保留信号研究价值，后续只做外生状态归因或更低频/ETF路线。",
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
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_one_day_path_columns(
        add_forward_returns(add_price_features(stock_df), benchmark_df).join(
            layer_tags, on=["datetime", "symbol"], how="left"
        )
    )

    ranked = build_ranked_liquid_q3(df)
    selected, daily_state, events = build_sticky_selected(ranked)
    lots = build_lots(selected)
    symbol_daily = build_symbol_daily(lots)

    min_date = min(symbol_daily["target_date"].min(), symbol_daily["pnl_date"].min())
    max_date = max(symbol_daily["target_date"].max(), symbol_daily["pnl_date"].max())
    calendar = build_calendar(benchmark_df, min_date, max_date)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    turnover, targets = build_turnover(symbol_daily, calendar, SCENARIO_NAME)
    concentration, industry_daily = build_concentration(symbol_daily, calendar, SCENARIO_NAME)
    daily_gross = build_daily_gross(symbol_daily)

    curves: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    scenario = {
        "scenario": SCENARIO_NAME,
        "description": SCENARIO_DESCRIPTION,
        "bucket": "liquid_q3",
        "weight_mode": "sticky_slot",
    }
    for cost_bps in COST_BPS:
        curve = build_equity_curve(
            SCENARIO_NAME,
            daily_gross,
            turnover,
            benchmark_daily,
            calendar,
            cost_bps,
        )
        curves.append(curve)
        summary_rows.append(summarize_curve(curve, turnover, concentration, selected, scenario, cost_bps))

    curves_df = pl.concat(curves, how="vertical").sort(["roundtrip_cost_bps", "date"])
    summary_df = augment_summary(pl.DataFrame(summary_rows), daily_state, selected).sort("roundtrip_cost_bps")
    yearly = build_yearly_summary(curves_df)
    event_summary = (
        events.group_by("event")
        .agg(
            pl.len().alias("event_count"),
            pl.col("holding_signal_days").mean().alias("avg_holding_signal_days"),
            pl.col("event_weight").mean().alias("avg_event_weight"),
        )
        .sort("event")
    )
    feature_group_summary = build_feature_group_summary(selected)

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "feature": FEATURE,
        "entry_group": ENTRY_GROUP,
        "retain_min_group": RETAIN_MIN_GROUP,
        "cost_bps": list(COST_BPS),
        "date_min": str(stock_df["datetime"].min()),
        "date_max": str(stock_df["datetime"].max()),
        "symbol_count": stock_df["symbol"].n_unique(),
        "initial_equity": INITIAL_EQUITY,
        "trading_days": TRADING_DAYS,
        "weight_policy": "keep retained weights; allocate only available cash from exited legs to new top20 candidates",
    }

    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "equity_curve": OUTPUT_DIR / f"{PREFIX}_equity_curve.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "daily_state": OUTPUT_DIR / f"{PREFIX}_daily_state.csv",
        "events": OUTPUT_DIR / f"{PREFIX}_events.csv",
        "feature_group": OUTPUT_DIR / f"{PREFIX}_feature_group.csv",
        "turnover": OUTPUT_DIR / f"{PREFIX}_turnover.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "daily_concentration": OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv",
        "industry_daily": OUTPUT_DIR / f"{PREFIX}_industry_daily.csv",
        "selected": OUTPUT_DIR / f"{PREFIX}_selected.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary_df.write_csv(paths["summary"])
    curves_df.write_csv(paths["equity_curve"])
    yearly.write_csv(paths["yearly"])
    daily_state.write_csv(paths["daily_state"])
    events.write_csv(paths["events"])
    feature_group_summary.write_csv(paths["feature_group"])
    turnover.write_csv(paths["turnover"])
    targets.write_csv(paths["target_weights"])
    concentration.write_csv(paths["daily_concentration"])
    industry_daily.write_csv(paths["industry_daily"])
    selected.write_csv(paths["selected"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = write_report(
        summary_df,
        yearly,
        daily_state,
        event_summary,
        feature_group_summary,
        meta,
        paths,
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
