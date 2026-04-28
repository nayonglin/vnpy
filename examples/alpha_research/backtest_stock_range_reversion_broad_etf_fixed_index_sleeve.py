from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

from backtest_stock_range_reversion_broad_etf_signal_sleeve import (
    BROAD_ETF_BASIC_PATH,
    BROAD_ETF_DAILY_PATH,
    BROAD_ETF_SUMMARY_PATH,
    INITIAL_EQUITY,
    NATIVE_RESULTS_DIR,
    ROUNDTRIP_COST_BPS,
    STRATEGIES,
    TRADING_DAYS,
    add_indicators,
    equity_and_drawdown,
    pct,
    strategy_entry_exit,
    to_float,
)


OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_fixed_index_sleeve_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_broad_etf_fixed_index_sleeve_v1"

SLEEVE_WEIGHTS: tuple[float, ...] = (0.05, 0.10)
MIN_YEARS: float = 5.0
MIN_P10_AMOUNT_RAW: float = 2_000.0


def load_primary_etf_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BROAD_ETF_DAILY_PATH.exists():
        raise FileNotFoundError(f"Broad ETF daily data not found: {BROAD_ETF_DAILY_PATH}")
    if not BROAD_ETF_BASIC_PATH.exists():
        raise FileNotFoundError(f"Broad ETF basic data not found: {BROAD_ETF_BASIC_PATH}")
    if not BROAD_ETF_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Broad ETF summary data not found: {BROAD_ETF_SUMMARY_PATH}")

    daily = pd.read_csv(BROAD_ETF_DAILY_PATH, encoding="utf-8-sig")
    basic = pd.read_csv(BROAD_ETF_BASIC_PATH, encoding="utf-8-sig")
    summary = pd.read_csv(BROAD_ETF_SUMMARY_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    for column in ("pre_close", "open", "high", "low", "close", "pct_chg", "daily_ret", "amount", "vol"):
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    for column in ("years", "median_amount_raw", "p10_amount_raw"):
        summary[column] = pd.to_numeric(summary[column], errors="coerce")

    keep = ["ts_code", "index_bucket", "index_name", "role", "name", "m_fee", "c_fee"]
    frame = daily.merge(basic[keep], on="ts_code", how="left")
    selected = summary[
        (summary["role"] == "primary")
        & (summary["years"] >= MIN_YEARS)
        & (summary["p10_amount_raw"] >= MIN_P10_AMOUNT_RAW)
    ].copy()
    codes = set(selected["ts_code"].astype(str))
    frame = frame[frame["ts_code"].isin(codes)].dropna(subset=["date", "close", "daily_ret"])
    frame = frame.sort_values(["ts_code", "date"]).reset_index(drop=True)
    selected = selected.sort_values(["index_bucket", "index_name", "ts_code"]).reset_index(drop=True)
    return frame, selected


def close_trade(
    trades: list[dict[str, Any]],
    open_trade: dict[str, Any] | None,
    row: dict[str, Any],
    date: Any,
    cost_bps: float,
    exit_reason: str,
) -> None:
    if not open_trade:
        return
    gross_return = to_float(open_trade.get("growth"), default=1.0) - 1.0
    trades.append(
        {
            "entry_signal_date": open_trade.get("entry_signal_date"),
            "entry_date": open_trade.get("entry_date"),
            "exit_date": date,
            "holding_days": int(open_trade.get("holding_days", 0)),
            "entry_close": open_trade.get("entry_close", 0.0),
            "exit_close": to_float(row.get("close")),
            "entry_trend_state": open_trade.get("entry_trend_state", ""),
            "entry_drawdown_state": open_trade.get("entry_drawdown_state", ""),
            "gross_return": gross_return,
            "net_return_est": gross_return - cost_bps / 10_000.0,
            "exit_reason": exit_reason,
        }
    )


def run_single_index(
    frame: pd.DataFrame,
    strategy: Any,
    sleeve_weight: float,
    roundtrip_cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = add_indicators(frame).sort_values("date").reset_index(drop=True)
    one_way_cost = roundtrip_cost_bps / 2.0 / 10_000.0
    active = False
    pending_active = False
    pending_entry_meta: dict[str, Any] | None = None
    open_trade: dict[str, Any] | None = None
    daily_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for idx, row_obj in work.iterrows():
        row = row_obj.to_dict()
        date = row["date"]
        is_last = idx == len(work) - 1
        previous_weight = sleeve_weight if active else 0.0
        current_weight = sleeve_weight if pending_active else 0.0
        turnover = abs(current_weight - previous_weight)

        if current_weight > 0.0 and previous_weight <= 0.0:
            meta = pending_entry_meta or {}
            open_trade = {
                "entry_signal_date": meta.get("entry_signal_date", date),
                "entry_date": date,
                "entry_close": to_float(row.get("close")),
                "entry_trend_state": meta.get("entry_trend_state", row.get("trend_state", "")),
                "entry_drawdown_state": meta.get("entry_drawdown_state", row.get("drawdown_state", "")),
                "growth": 1.0,
                "holding_days": 0,
            }
        elif current_weight <= 0.0 and previous_weight > 0.0:
            close_trade(trade_rows, open_trade, row, date, roundtrip_cost_bps, "signal_exit")
            open_trade = None

        active = pending_active
        pending_entry_meta = None
        next_ret = to_float(row.get("next_daily_ret"), default=0.0)
        strategy_daily_ret = current_weight * next_ret - turnover * one_way_cost
        baseline_daily_ret = sleeve_weight * next_ret

        if active and open_trade is not None:
            open_trade["growth"] = to_float(open_trade.get("growth"), default=1.0) * (1.0 + next_ret)
            open_trade["holding_days"] = int(open_trade.get("holding_days", 0)) + 1

        final_close_cost = 0.0
        if is_last and active:
            final_close_cost = sleeve_weight * one_way_cost
            strategy_daily_ret -= final_close_cost
            close_trade(trade_rows, open_trade, row, date, roundtrip_cost_bps, "final_close")
            open_trade = None
            active = False
            pending_active = False

        new_signal = False
        if not is_last:
            entry_signal, exit_signal = strategy_entry_exit(row, strategy)
            hold_days = int(open_trade.get("holding_days", 0)) if open_trade else 0
            exit_by_hold = active and hold_days >= strategy.max_hold_days
            next_active = active and not exit_signal and not exit_by_hold
            if not active and entry_signal:
                next_active = True
                new_signal = True
                pending_entry_meta = {
                    "entry_signal_date": date,
                    "entry_trend_state": row.get("trend_state", ""),
                    "entry_drawdown_state": row.get("drawdown_state", ""),
                }
            pending_active = next_active

        daily_rows.append(
            {
                "date": date,
                "ts_code": row.get("ts_code"),
                "etf_name": row.get("name", ""),
                "index_bucket": row.get("index_bucket", ""),
                "index_name": row.get("index_name", ""),
                "strategy": strategy.name,
                "sleeve_weight": sleeve_weight,
                "roundtrip_cost_bps": roundtrip_cost_bps,
                "active": int(current_weight > 0.0),
                "gross_exposure": current_weight,
                "turnover": turnover,
                "trade_cost_ret": turnover * one_way_cost + final_close_cost,
                "strategy_daily_ret": strategy_daily_ret,
                "baseline_sleeve_daily_ret": baseline_daily_ret,
                "new_signal": int(new_signal),
                "trend_state": row.get("trend_state", ""),
                "drawdown_state": row.get("drawdown_state", ""),
            }
        )

    daily = pd.DataFrame(daily_rows)
    trades = pd.DataFrame(trade_rows)
    if not daily.empty:
        equity, drawdown = equity_and_drawdown(daily["strategy_daily_ret"])
        baseline_equity, baseline_drawdown = equity_and_drawdown(daily["baseline_sleeve_daily_ret"])
        daily["strategy_equity"] = equity
        daily["strategy_drawdown"] = drawdown
        daily["baseline_sleeve_equity"] = baseline_equity
        daily["baseline_sleeve_drawdown"] = baseline_drawdown
    return daily, trades


def summarize(daily: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    ret = daily["strategy_daily_ret"].fillna(0.0)
    mean = ret.mean()
    std = ret.std(ddof=1)
    total_return = to_float(daily["strategy_equity"].iloc[-1] - INITIAL_EQUITY)
    baseline_return = to_float(daily["baseline_sleeve_equity"].iloc[-1] - INITIAL_EQUITY)
    trade_count = int(len(trades))
    return {
        "ts_code": str(daily["ts_code"].iloc[0]),
        "etf_name": str(daily["etf_name"].iloc[0]),
        "index_bucket": str(daily["index_bucket"].iloc[0]),
        "index_name": str(daily["index_name"].iloc[0]),
        "strategy": str(daily["strategy"].iloc[0]),
        "sleeve_weight": to_float(daily["sleeve_weight"].iloc[0]),
        "roundtrip_cost_bps": to_float(daily["roundtrip_cost_bps"].iloc[0]),
        "days": int(len(daily)),
        "start_date": str(daily["date"].min()),
        "end_date": str(daily["date"].max()),
        "final_equity": to_float(daily["strategy_equity"].iloc[-1]),
        "total_return": total_return,
        "annualized_return": (1.0 + total_return) ** (TRADING_DAYS / len(daily)) - 1.0
        if len(daily) and total_return > -1.0
        else 0.0,
        "max_drawdown": to_float(daily["strategy_drawdown"].min()),
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std else 0.0,
        "baseline_sleeve_final_equity": to_float(daily["baseline_sleeve_equity"].iloc[-1]),
        "baseline_sleeve_total_return": baseline_return,
        "baseline_sleeve_max_drawdown": to_float(daily["baseline_sleeve_drawdown"].min()),
        "active_day_ratio": to_float(daily["active"].mean()),
        "avg_gross_exposure": to_float(daily["gross_exposure"].mean()),
        "annualized_turnover": to_float(daily["turnover"].mean()) * TRADING_DAYS,
        "cost_drag_sum": to_float(daily["trade_cost_ret"].sum()),
        "entry_count": trade_count,
        "win_rate": to_float((trades["net_return_est"] > 0.0).mean()) if trade_count else 0.0,
        "avg_trade_net_return": to_float(trades["net_return_est"].mean()) if trade_count else 0.0,
        "median_trade_net_return": to_float(trades["net_return_est"].median()) if trade_count else 0.0,
        "avg_holding_days": to_float(trades["holding_days"].mean()) if trade_count else 0.0,
        "signal_days": int(daily["new_signal"].sum()),
    }


def build_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    work = daily.copy()
    work["year"] = pd.to_datetime(work["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for keys, group in work.groupby(["ts_code", "index_name", "strategy", "sleeve_weight", "roundtrip_cost_bps", "year"]):
        ts_code, index_name, strategy, sleeve_weight, cost_bps, year = keys
        rows.append(
            {
                "ts_code": ts_code,
                "index_name": index_name,
                "strategy": strategy,
                "sleeve_weight": sleeve_weight,
                "roundtrip_cost_bps": cost_bps,
                "year": int(year),
                "year_return": to_float((1.0 + group["strategy_daily_ret"].fillna(0.0)).prod() - 1.0),
                "baseline_year_return": to_float((1.0 + group["baseline_sleeve_daily_ret"].fillna(0.0)).prod() - 1.0),
                "active_day_ratio": to_float(group["active"].mean()),
                "year_turnover": to_float(group["turnover"].sum()),
                "year_cost_drag": to_float(group["trade_cost_ret"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["strategy", "roundtrip_cost_bps", "sleeve_weight", "ts_code", "year"]
    )


def build_state_summary(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    keys = [
        "ts_code",
        "index_name",
        "strategy",
        "sleeve_weight",
        "roundtrip_cost_bps",
        "entry_trend_state",
        "entry_drawdown_state",
    ]
    for group_keys, group in trades.groupby(keys):
        record = dict(zip(keys, group_keys))
        record.update(
            {
                "trade_count": int(len(group)),
                "win_rate": to_float((group["net_return_est"] > 0.0).mean()),
                "avg_net_return": to_float(group["net_return_est"].mean()),
                "median_net_return": to_float(group["net_return_est"].median()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows).sort_values(
        ["strategy", "roundtrip_cost_bps", "sleeve_weight", "ts_code", "avg_net_return"]
    )


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    state_summary: pd.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    focus_boll_20 = summary[
        (summary["strategy"] == "bollinger20_2_ma200")
        & (summary["sleeve_weight"] == 0.10)
        & (summary["roundtrip_cost_bps"] == 20.0)
    ].sort_values(["final_equity", "max_drawdown"], ascending=[False, False])
    focus_boll_50 = summary[
        (summary["strategy"] == "bollinger20_2_ma200")
        & (summary["sleeve_weight"] == 0.10)
        & (summary["roundtrip_cost_bps"] == 50.0)
    ].sort_values(["final_equity", "max_drawdown"], ascending=[False, False])
    focus_connors_20 = summary[
        (summary["strategy"] == "connors_rsi2_ma200")
        & (summary["sleeve_weight"] == 0.10)
        & (summary["roundtrip_cost_bps"] == 20.0)
    ].sort_values(["final_equity", "max_drawdown"], ascending=[False, False])
    best_boll = focus_boll_20.head(1)
    weak_boll = focus_boll_20.tail(3)
    lines = [
        "# 股票震荡宽基ETF固定指数袖珍仓画像 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定指数袖珍仓画像，不是正式交易版本。",
        f"- 输入数据：`{BROAD_ETF_DAILY_PATH}`",
        f"- 样本口径：primary ETF，样本不少于`{MIN_YEARS:.0f}`年，p10成交额原始口径不少于`{MIN_P10_AMOUNT_RAW:.0f}`。",
        f"- 袖珍仓权重：`{','.join(pct(x) for x in SLEEVE_WEIGHTS)}`；成本档：`{','.join(str(int(x)) + 'bp' for x in ROUNDTRIP_COST_BPS)}`。",
        "- 执行口径：收盘生成信号，次日收盘换仓；收益使用Tushare `pct_chg`。",
        "",
        "## 核心观察",
        "",
    ]
    if not best_boll.empty:
        row = best_boll.iloc[0]
        lines.append(
            f"- 10%袖珍仓、20bp下Bollinger+MA200最强指数是`{row['index_name']}` `{row['ts_code']}`："
            f"期末权益`{row['final_equity']:.4f}`，最大回撤`{pct(row['max_drawdown'])}`，"
            f"Sharpe `{row['sharpe']:.2f}`，交易`{int(row['entry_count'])}`次。"
        )
    if not focus_boll_50.empty:
        row = focus_boll_50.iloc[0]
        lines.append(
            f"- 50bp压力下Bollinger+MA200最佳仍为`{row['index_name']}`，期末权益`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`。"
        )
    if not focus_connors_20.empty:
        row = focus_connors_20.iloc[0]
        lines.append(
            f"- Connors 20bp最佳为`{row['index_name']}`，期末权益`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`，但需要继续看50bp压力。"
        )
    lines.extend(
        [
            "- 固定指数画像的目的不是挑收益最高指数上线，而是确认哪些指数在同一模板下天然更干净，哪些指数会系统性拖累。",
            "- 本阶段仍不删除弱指数，不新增状态过滤器。",
            "",
            "## Bollinger+MA200 10%袖珍仓 20bp",
            "",
            markdown_table(
                focus_boll_20,
                [
                    "ts_code",
                    "index_name",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "baseline_sleeve_total_return",
                    "active_day_ratio",
                    "annualized_turnover",
                    "entry_count",
                    "win_rate",
                    "avg_trade_net_return",
                ],
                max_rows=80,
            ),
            "",
            "## Bollinger+MA200 10%袖珍仓 50bp",
            "",
            markdown_table(
                focus_boll_50,
                [
                    "ts_code",
                    "index_name",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "active_day_ratio",
                    "annualized_turnover",
                    "entry_count",
                    "win_rate",
                    "avg_trade_net_return",
                ],
                max_rows=80,
            ),
            "",
            "## Connors RSI2+MA200 10%袖珍仓 20bp",
            "",
            markdown_table(
                focus_connors_20,
                [
                    "ts_code",
                    "index_name",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "active_day_ratio",
                    "annualized_turnover",
                    "entry_count",
                    "win_rate",
                    "avg_trade_net_return",
                ],
                max_rows=80,
            ),
            "",
            "## 弱Bollinger指数年度摘录",
            "",
            markdown_table(
                yearly[
                    yearly["ts_code"].isin(set(weak_boll["ts_code"].astype(str)))
                    & (yearly["strategy"] == "bollinger20_2_ma200")
                    & (yearly["sleeve_weight"] == 0.10)
                    & (yearly["roundtrip_cost_bps"] == 20.0)
                ],
                ["ts_code", "index_name", "year", "year_return", "baseline_year_return", "active_day_ratio"],
                max_rows=80,
            ),
            "",
            "## 状态归因摘录：Bollinger 10% 20bp",
            "",
            markdown_table(
                state_summary[
                    (state_summary["strategy"] == "bollinger20_2_ma200")
                    & (state_summary["sleeve_weight"] == 0.10)
                    & (state_summary["roundtrip_cost_bps"] == 20.0)
                ].sort_values(["avg_net_return"], ascending=False),
                [
                    "index_name",
                    "entry_trend_state",
                    "entry_drawdown_state",
                    "trade_count",
                    "win_rate",
                    "avg_net_return",
                    "median_net_return",
                ],
                max_rows=60,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段是固定指数画像，使用同一模板、同一成本档和同一袖珍仓权重，不按结果删指数或新增过滤器。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：画像保留全部长样本primary ETF和全部成本档，结论只用于路线判断，不把最优指数包装成正式参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：小权重全信号证明不抢仓位可以压回撤，但需要知道低回撤来自哪些指数的天然结构。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：有研究价值，但ETF路线暂不适合作为正式策略主线继续参数化。",
            "- 原因：沪深300/中证800等大宽基在Bollinger+MA200下表现干净，50bp后仍保持低回撤小正收益；但10%袖珍仓收益厚度只有几个百分点，更像状态观察/防守小模块，不像独立收益引擎。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- ETF路线保留为固定指数监控画像，不继续围绕ETF池、权重、暴露上限或指数剔除调参。",
            "- 下一步应切回行业内残差/个股横截面震荡路线，寻找比ETF更厚的横截面均值回归收益。",
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
    broad_daily, selected = load_primary_etf_data()
    all_daily: list[pd.DataFrame] = []
    all_trades: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for code in selected["ts_code"].astype(str):
        frame = broad_daily[broad_daily["ts_code"] == code].copy()
        for strategy in STRATEGIES:
            for sleeve_weight in SLEEVE_WEIGHTS:
                for cost_bps in ROUNDTRIP_COST_BPS:
                    daily, trades = run_single_index(frame, strategy, sleeve_weight, cost_bps)
                    if not trades.empty:
                        meta_cols = {
                            "ts_code": str(daily["ts_code"].iloc[0]),
                            "etf_name": str(daily["etf_name"].iloc[0]),
                            "index_bucket": str(daily["index_bucket"].iloc[0]),
                            "index_name": str(daily["index_name"].iloc[0]),
                            "strategy": strategy.name,
                            "sleeve_weight": sleeve_weight,
                            "roundtrip_cost_bps": cost_bps,
                        }
                        for insert_at, (column, value) in enumerate(meta_cols.items()):
                            trades.insert(insert_at, column, value)
                    all_daily.append(daily)
                    all_trades.append(trades)
                    summary_rows.append(summarize(daily, trades))

    combined_daily = pd.concat(all_daily, ignore_index=True, sort=False)
    combined_trades = pd.concat([frame for frame in all_trades if not frame.empty], ignore_index=True, sort=False)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["strategy", "roundtrip_cost_bps", "sleeve_weight", "final_equity"],
        ascending=[True, True, True, False],
    )
    yearly = build_yearly(combined_daily)
    state_summary = build_state_summary(combined_trades)
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "input": str(BROAD_ETF_DAILY_PATH),
        "basic": str(BROAD_ETF_BASIC_PATH),
        "summary": str(BROAD_ETF_SUMMARY_PATH),
        "min_years": MIN_YEARS,
        "min_p10_amount_raw": MIN_P10_AMOUNT_RAW,
        "selected_etfs": selected.to_dict("records"),
        "strategies": [asdict(strategy) for strategy in STRATEGIES],
        "sleeve_weights": list(SLEEVE_WEIGHTS),
        "roundtrip_cost_bps": list(ROUNDTRIP_COST_BPS),
        "execution": "signals at close, position changes at next close; returns use Tushare pct_chg",
    }
    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "trades": OUTPUT_DIR / f"{PREFIX}_trades.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    combined_daily.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    combined_trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    yearly.to_csv(paths["yearly"], index=False, encoding="utf-8-sig")
    state_summary.to_csv(paths["state_summary"], index=False, encoding="utf-8-sig")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(summary, yearly, state_summary, paths)
    print(summary.to_string(index=False))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
