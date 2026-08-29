from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage450_minute_execution_equity_rebuild as s450  # noqa: E402
import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage502_confirmed_daily_next_real_open_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage502_confirmed_daily_next_real_open_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RERUN_VARIANT = "stage079_rerun_same_day_close"
NEXT_REAL_VARIANT = "stage079_confirmed_daily_all_orders_next_real_open"

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


class ConfirmedDailyNextRealOpenEngine(SameDayCloseBacktestingEngine):
    """Use completed daily signals; execute every order at the next real session-open proxy."""

    def __init__(self, open_proxy_map: dict[tuple[pd.Timestamp, pd.Timestamp, str], dict[str, Any]]) -> None:
        super().__init__()
        self.open_proxy_map = open_proxy_map
        self.trade_usage_rows: list[dict[str, Any]] = []
        self.source_counter: Counter[str] = Counter()

    def new_bars(self, dt) -> None:
        self.datetime = dt

        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            bar: BarData | None = self.history_data.get((dt, vt_symbol), None)
            if bar:
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar
            elif vt_symbol in self.bars:
                old_bar: BarData = self.bars[vt_symbol]
                bar = BarData(
                    symbol=old_bar.symbol,
                    exchange=old_bar.exchange,
                    datetime=dt,
                    open_price=old_bar.close_price,
                    high_price=old_bar.close_price,
                    low_price=old_bar.close_price,
                    close_price=old_bar.close_price,
                    gateway_name=old_bar.gateway_name,
                )
                self.bars[vt_symbol] = bar

        self.cross_delayed_orders()
        self.strategy.on_bars(bars)

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def _resolve_trade_price(self, order: Any, bar: BarData) -> tuple[float, str, dict[str, Any]]:
        vt_symbol = str(order.vt_symbol)
        signal_date = s501._naive_date(order.datetime)
        fill_date = s501._naive_date(self.datetime)
        proxy = self.open_proxy_map.get((signal_date, fill_date, vt_symbol))
        if proxy is None:
            proxy = s501._next_real_open_proxy_from_raw(vt_symbol, signal_date, fill_date)
        if proxy is not None and _safe_float(proxy.get("proxy_price"), 0.0) > 0:
            return float(proxy["proxy_price"]), str(proxy["price_source"]), proxy
        fallback = float(bar.open_price or 0.0) or float(order.price)
        return fallback, "fallback_daily_next_open", {}

    def _fill_order(self, order: Any, bar: BarData) -> None:
        trade_price, price_source, proxy = self._resolve_trade_price(order, bar)
        if trade_price <= 0 or float(order.price) <= 0:
            return
        if order.status == Status.SUBMITTING:
            order.status = Status.NOTTRADED
            self.strategy.update_order(order)

        order.traded = order.volume
        order.status = Status.ALLTRADED
        self.strategy.update_order(order)

        if order.vt_orderid in self.active_limit_orders:
            self.active_limit_orders.pop(order.vt_orderid)

        self.trade_count += 1
        trade = TradeData(
            symbol=order.symbol,
            exchange=order.exchange,
            orderid=order.orderid,
            tradeid=str(self.trade_count),
            direction=order.direction,
            offset=order.offset,
            price=trade_price,
            volume=order.volume,
            datetime=self.datetime,
            gateway_name=self.gateway_name,
        )
        self.strategy.update_trade(trade)
        self.trades[trade.vt_tradeid] = trade
        self.source_counter[price_source] += 1
        self.trade_usage_rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "orderid": str(order.orderid),
                "signal_date": s501._naive_date(order.datetime),
                "fill_date": s501._naive_date(self.datetime),
                "vt_symbol": str(order.vt_symbol),
                "direction": s501._direction_text(order.direction),
                "offset": s501._offset_text(order.offset),
                "order_price": float(order.price),
                "trade_price": float(trade_price),
                "price_delta": float(trade_price) - float(order.price),
                "order_volume": float(order.volume),
                "price_source": price_source,
                "proxy_bar_count": proxy.get("proxy_bar_count", np.nan),
                "proxy_first_time": proxy.get("proxy_first_time", ""),
                "proxy_last_time": proxy.get("proxy_last_time", ""),
            }
        )

    def cross_delayed_orders(self) -> None:
        for order in list(self.active_limit_orders.values()):
            bar: BarData | None = self.bars.get(order.vt_symbol)
            if bar is None:
                continue
            self._fill_order(order, bar)


def _load_stage079_baseline() -> pd.DataFrame:
    frame = pd.read_csv(s450.STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020") & frame["variant"].eq(BASELINE_VARIANT)].copy()
    for column in ["equity", "c3_net_pnl", "c3_slippage", "c3_trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _make_engine(next_real: bool) -> SameDayCloseBacktestingEngine:
    if not next_real:
        return SameDayCloseBacktestingEngine()
    _, open_map = s501._seed_proxy_maps()
    return ConfirmedDailyNextRealOpenEngine(open_map)


def _run_c3_engine(*, next_real: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    engine = _make_engine(next_real)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(metadata["margin_ratios"], risk_ratio=BASE_RISK_RATIO, strategy_overrides=overrides)
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError("C3 engine produced empty daily result")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    source_counts = pd.DataFrame(
        [{"price_source": key, "trade_count": int(value)} for key, value in getattr(engine, "source_counter", Counter()).items()]
    )
    return daily, usage, source_counts


def _build_long_daily(baseline: pd.DataFrame, rerun_daily: pd.DataFrame, next_real_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base = baseline[["date", "equity", "c3_slippage", "c3_trade_count", "c3_net_pnl"]].copy()
    base.rename(
        columns={
            "equity": "account_equity",
            "c3_slippage": "slippage",
            "c3_trade_count": "trade_count",
            "c3_net_pnl": "net_pnl",
        },
        inplace=True,
    )
    base["variant"] = BASELINE_VARIANT
    base["label"] = "Stage079 baseline from Stage403"
    rows.append(base)

    rerun = rerun_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    rerun["variant"] = RERUN_VARIANT
    rerun["label"] = "Stage079 same-day close rerun"
    rows.append(rerun)

    next_real = next_real_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    next_real["variant"] = NEXT_REAL_VARIANT
    next_real["label"] = "Stage079 completed daily signal, all orders next real open"
    rows.append(next_real)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {
        BASELINE_VARIANT: "#4c78a8",
        RERUN_VARIANT: "#72b7b2",
        NEXT_REAL_VARIANT: "#e45756",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.2)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_title("Stage079 confirmed daily signal + next real open execution")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    usage: pd.DataFrame,
    source_counts: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    usage_view = usage.copy()
    if not usage_view.empty:
        usage_view = usage_view.reindex(usage_view["price_delta"].abs().sort_values(ascending=False).index).head(30)
    report = [
        "# Stage202 完整日K确认后下一真实窗口回放",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：真实可成交日线基准；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 口径：所有订单都由已完成日K信号产生，并在下一真实可交易窗口代理价成交。",
        "- 判定目标：全周期最大回撤是否在 `40%` 内，并尽量保留 Stage079 大部分收益。",
        "",
        "## 外部调研判断",
        "",
        "- Backtrader 的市价单默认在下一根bar open成交，理由是当前bar逻辑结束后，下一个价格点是下一bar open。",
        "- NautilusTrader 强调事件时间顺序和bar完成时刻，以避免 look-ahead bias。",
        "- QuantConnect/LEAN 采用事件驱动时间推进，只让算法看到当前和过去的数据。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 下一真实窗口成交数：`{decision['next_real_trade_count']}`。",
        f"- fallback成交数：`{decision['fallback_trade_count']}`。",
        f"- 相对 Stage079 收益保留：`{decision['return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 原始重跑与Stage403期末权益差：`{decision['rerun_vs_stage403_end_equity_delta']:.2f}`。",
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## 成交价格来源",
        "",
        _md_table(source_counts.sort_values("trade_count", ascending=False) if not source_counts.empty else source_counts),
        "",
        "## 最大成交价替换样本",
        "",
        _md_table(
            usage_view[
                [
                    "signal_date",
                    "fill_date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "order_price",
                    "trade_price",
                    "price_delta",
                    "order_volume",
                    "price_source",
                ]
            ]
            if not usage_view.empty
            else usage_view,
            max_rows=30,
        ),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。该阶段只建立无偏执行基准，不调策略参数。",
        "- 运行后过拟合反思：以门禁结果为准；若失败，不能按坏窗口补丁救。",
        "- 运行前继续价值反思：是。新目标需要先知道日线确认信号的真实可成交边界。",
        "- 运行后继续价值反思：若40%回撤失败，下一步应优先低自由度风险预算/波动目标结构，而不是回到同bar执行。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    baseline = _load_stage079_baseline()
    rerun_daily, _, _ = _run_c3_engine(next_real=False)
    next_real_daily, usage, source_counts = _run_c3_engine(next_real=True)
    long_daily = _build_long_daily(baseline, rerun_daily, next_real_daily)
    summary, horizon, score, cost, gate = s451._evaluate(long_daily)
    _plot(long_daily)

    stage079 = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    rerun = summary[summary["variant"].eq(RERUN_VARIANT)].iloc[0]
    candidate = summary[summary["variant"].eq(NEXT_REAL_VARIANT)].iloc[0]
    fallback_count = int(usage["price_source"].astype(str).str.startswith("fallback").sum()) if not usage.empty else 0
    return_retention = (
        _safe_float(candidate["total_return_pct"]) / _safe_float(stage079["total_return_pct"]) * 100.0
        if _safe_float(stage079["total_return_pct"]) > 0
        else 0.0
    )
    max_dd_ok_40 = _safe_float(candidate["max_dd_pct"]) >= -40.0
    retain_most = return_retention >= 65.0
    decision_label = (
        "confirmed_daily_next_real_open_candidate_pass_dd40_return65"
        if max_dd_ok_40 and retain_most and fallback_count == 0
        else "confirmed_daily_next_real_open_baseline_fails_need_risk_structure"
    )
    decision = {
        "stage": "Stage202",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "next_real_trade_count": int(len(usage)),
        "fallback_trade_count": fallback_count,
        "return_retention_vs_stage079_pct": float(return_retention),
        "max_dd_ok_40": bool(max_dd_ok_40),
        "return_retention_ge_65": bool(retain_most),
        "rerun_vs_stage403_end_equity_delta": _safe_float(rerun["end_equity"]) - _safe_float(stage079["end_equity"]),
        "candidate_end_equity": _safe_float(candidate["end_equity"]),
        "candidate_total_return_pct": _safe_float(candidate["total_return_pct"]),
        "candidate_max_dd_pct": _safe_float(candidate["max_dd_pct"]),
        "candidate_sharpe": _safe_float(candidate["sharpe"]),
        "candidate_ulcer_pct": _safe_float(candidate["ulcer_pct"]),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若该无偏基准未满足DD40/收益保留，下一步在同一执行口径上测试低自由度风险预算或波动目标结构。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, usage, source_counts, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
