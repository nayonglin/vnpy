from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import re
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
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage451_true_path_1455_vwap_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage451_true_path_1455_vwap_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
TRUE_PATH_VARIANT = "stage079_true_path_1455_vwap"
RERUN_VARIANT = "stage079_rerun_same_day_close"

STAGE403_DAILY_PATH = s450.STAGE403_DAILY_PATH
STAGE149_DETAIL_PATH = s450.STAGE149_DETAIL_PATH

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
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _trade_ordinal(trade_id: Any) -> int:
    match = re.search(r"(\d+)$", str(trade_id))
    return int(match.group(1)) if match else 0


def _naive_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


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


def _direction_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _offset_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _load_stage079_baseline() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020") & frame["variant"].eq(BASELINE_VARIANT)].copy()
    for column in ["equity", "c3_net_pnl", "c3_slippage", "c3_trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _load_proxy_queues() -> dict[tuple[pd.Timestamp, str, str, str], deque[dict[str, Any]]]:
    detail = pd.read_csv(STAGE149_DETAIL_PATH, encoding="utf-8-sig")
    detail["date"] = pd.to_datetime(detail["date"], errors="coerce").dt.normalize()
    for column in ["same_last5_vwap", "theoretical_price", "volume", "size"]:
        detail[column] = pd.to_numeric(detail.get(column, np.nan), errors="coerce")
    detail = detail[
        detail["date"].notna()
        & detail["same_last5_vwap"].notna()
        & detail["theoretical_price"].notna()
        & detail["same_last5_vwap"].gt(0.0)
        & detail["theoretical_price"].gt(0.0)
    ].copy()
    detail["trade_ordinal"] = detail["trade_id"].map(_trade_ordinal)
    detail.sort_values(["date", "trade_ordinal", "trade_id"], inplace=True)

    queues: dict[tuple[pd.Timestamp, str, str, str], deque[dict[str, Any]]] = {}
    for row in detail.itertuples(index=False):
        key = (_naive_date(row.date), str(row.vt_symbol), str(row.direction), str(row.offset))
        queues.setdefault(key, deque()).append(
            {
                "source_trade_id": str(row.trade_id),
                "proxy_price": float(row.same_last5_vwap),
                "theoretical_price": float(row.theoretical_price),
                "source_volume": float(row.volume),
                "size": float(row.size),
                "product_vt_symbol": str(row.product_vt_symbol),
                "session_proxy_class": str(row.session_proxy_class),
            }
        )
    return queues


class TruePath1455VwapEngine(SameDayCloseBacktestingEngine):
    """Same-day close engine with per-trade 14:55 VWAP execution proxy."""

    def __init__(self, proxy_queues: dict[tuple[pd.Timestamp, str, str, str], deque[dict[str, Any]]]) -> None:
        super().__init__()
        self.proxy_queues = proxy_queues
        self.proxy_usage_rows: list[dict[str, Any]] = []

    def _resolve_trade_price(self, order: Any) -> float:
        fallback_price = float(order.price)
        key = (
            _naive_date(self.datetime),
            str(order.vt_symbol),
            _direction_text(order.direction),
            _offset_text(order.offset),
        )
        queue = self.proxy_queues.get(key)
        proxy_row: dict[str, Any] | None = queue.popleft() if queue else None
        if proxy_row is not None:
            trade_price = float(proxy_row["proxy_price"])
            source = "stage149_same_last5_vwap"
        else:
            trade_price = fallback_price
            source = "fallback_order_price"

        self.proxy_usage_rows.append(
            {
                "datetime": self.datetime,
                "date": _naive_date(self.datetime),
                "vt_symbol": str(order.vt_symbol),
                "direction": _direction_text(order.direction),
                "offset": _offset_text(order.offset),
                "orderid": str(order.orderid),
                "order_price": fallback_price,
                "trade_price": trade_price,
                "proxy_source": source,
                "proxy_source_trade_id": "" if proxy_row is None else str(proxy_row["source_trade_id"]),
                "proxy_theoretical_price": np.nan if proxy_row is None else float(proxy_row["theoretical_price"]),
                "proxy_source_volume": np.nan if proxy_row is None else float(proxy_row["source_volume"]),
                "order_volume": float(order.volume),
                "proxy_session_class": "" if proxy_row is None else str(proxy_row["session_proxy_class"]),
            }
        )
        return trade_price

    def cross_limit_order_on_close(self) -> None:
        for order in list(self.active_limit_orders.values()):
            bar: BarData = self.bars[order.vt_symbol]
            close_price = float(bar.close_price)
            if close_price <= 0:
                continue

            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self.strategy.update_order(order)

            if float(order.price) <= 0:
                continue

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
                price=self._resolve_trade_price(order),
                volume=order.volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )
            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade


def _run_c3_engine(*, true_path_proxy: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    proxy_queues = _load_proxy_queues() if true_path_proxy else {}
    engine = TruePath1455VwapEngine(proxy_queues) if true_path_proxy else SameDayCloseBacktestingEngine()
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
        raise RuntimeError("C3 true path replay produced empty daily result")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    usage = pd.DataFrame(getattr(engine, "proxy_usage_rows", []))
    if usage.empty:
        usage = pd.DataFrame(
            columns=[
                "date",
                "vt_symbol",
                "direction",
                "offset",
                "orderid",
                "order_price",
                "trade_price",
                "proxy_source",
                "proxy_source_trade_id",
                "order_volume",
            ]
        )
    return daily, usage


def _calendar_equity(daily: pd.DataFrame, equity_col: str) -> pd.Series:
    series = daily.sort_values("date").set_index("date")[equity_col].astype(float)
    calendar = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(calendar).ffill()


def _build_long_daily(
    baseline: pd.DataFrame,
    rerun_daily: pd.DataFrame,
    true_path_daily: pd.DataFrame,
) -> pd.DataFrame:
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
    rerun["label"] = "Stage079 same-day engine rerun"
    rows.append(rerun)

    true_path = true_path_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    true_path["variant"] = TRUE_PATH_VARIANT
    true_path["label"] = "Stage079 true path 14:55 VWAP fills"
    rows.append(true_path)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _cost_stress(long_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_by_multiplier: dict[float, float] = {}
    labels = long_daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for variant, frame in long_daily.groupby("variant", sort=False):
            ordered = frame.sort_values("date").copy()
            extra_cost = (multiplier - 1.0) * ordered["slippage"].astype(float).cumsum()
            equity = ordered["account_equity"].astype(float) - extra_cost
            calendar = pd.Series(equity.to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
            calendar = calendar.reindex(pd.date_range(calendar.index.min(), calendar.index.max(), freq="D")).ffill()
            nav = calendar / ACCOUNT_CAPITAL
            max_dd = s450._max_drawdown_pct(nav)
            if variant == BASELINE_VARIANT:
                baseline_by_multiplier[multiplier] = max_dd
            rows.append(
                {
                    "variant": variant,
                    "label": labels.get(variant, variant),
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_by_multiplier)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _evaluate(long_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    labels = long_daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant, frame in long_daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame, "account_equity")
        summary_rows.append(s450._summary_for(variant, labels.get(variant, variant), equity, ACCOUNT_CAPITAL))
        for horizon_days in (90, 180):
            horizon_rows.append(s450._horizon_for(variant, labels.get(variant, variant), equity, horizon_days))
    summary = pd.DataFrame(summary_rows)
    horizon = pd.DataFrame(horizon_rows)
    score = s450._score_horizons(horizon)
    cost = _cost_stress(long_daily)
    gate = s450._gate(summary, horizon, score, cost)
    return summary, horizon, score, cost, gate


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {
        BASELINE_VARIANT: "#4c78a8",
        RERUN_VARIANT: "#72b7b2",
        TRUE_PATH_VARIANT: "#e45756",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.2)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_title("Stage079 true path replay with 14:55 VWAP fills")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="#222222", linestyle="--", linewidth=1.0)
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
    gate_cols = [
        "variant",
        "hard_constraint_pass",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "improved_count_90d",
        "improved_count_180d",
        "promotion_gate_pass",
        "failed_hard_constraints",
    ]
    usage_view = usage.copy()
    if not usage_view.empty:
        usage_view["price_delta"] = usage_view["trade_price"].astype(float) - usage_view["order_price"].astype(float)
        usage_view = usage_view.reindex(usage_view["price_delta"].abs().sort_values(ascending=False).index).head(30)

    report = [
        "# Stage151 Stage079 14:55 VWAP真实路径回放审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行模型真实路径回放；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "- 方法：回测引擎仍按日线生成信号和订单，但在同日收盘撮合层优先用 Stage149 全量分钟账本的 `same_last5_vwap` 作为成交价。",
        "- 解释边界：这是固定 `14:55 VWAP` 执行口径，不是按收益调参；若真实路径产生新订单且无分钟代理价，则回退到原订单价并计数。",
        "",
        "## 外部调研判断",
        "",
        "- Implementation shortfall 要比较理论/决策价与实际执行价；本阶段把这个差异推进到逐笔成交和后续状态，而不是一阶加减权益。",
        "- Backtrader、NautilusTrader、vn.py 等回测资料都强调订单撮合时点和撮合价格必须有明确语义；因此真实路径回放比权益后处理更可信。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 硬约束通过项：`{decision['hard_constraint_pass_variants']}`。",
        f"- 晋级通过项：`{decision['promotion_gate_pass_variants']}`。",
        f"- 真实路径代理成交数：`{decision['proxy_matched_trade_count']}`。",
        f"- 回退原订单价成交数：`{decision['fallback_trade_count']}`。",
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
        "## 分数与门禁",
        "",
        _md_table(gate[gate_cols]),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## 最大成交价替换样本",
        "",
        _md_table(
            usage_view[
                [
                    "date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "order_price",
                    "trade_price",
                    "price_delta",
                    "order_volume",
                    "proxy_source",
                    "proxy_source_trade_id",
                ]
            ]
            if not usage_view.empty
            else usage_view,
            max_rows=30,
        ),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。固定使用 14:55 VWAP 执行代理，不筛日期、品种或坏窗口。",
        "- 运行后过拟合反思：否。结果只用于执行模型可信度裁决，不作为交易过滤规则。",
        "- 运行前继续价值反思：是。一阶重构不能证明后续止损、开仓和权益路径仍成立。",
        "- 运行后继续价值反思：若硬约束失败，应暂停优化并先修执行模型；若通过，再将同一回放口径扩展到 Stage103/xsmom。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    baseline = _load_stage079_baseline()
    rerun_daily, _ = _run_c3_engine(true_path_proxy=False)
    true_path_daily, usage = _run_c3_engine(true_path_proxy=True)
    long_daily = _build_long_daily(baseline, rerun_daily, true_path_daily)
    summary, horizon, score, cost, gate = _evaluate(long_daily)
    _plot(long_daily)

    stage403_end = float(summary[summary["variant"].eq(BASELINE_VARIANT)]["end_equity"].iloc[0])
    rerun_end = float(summary[summary["variant"].eq(RERUN_VARIANT)]["end_equity"].iloc[0])
    matched = int(usage["proxy_source"].eq("stage149_same_last5_vwap").sum()) if not usage.empty else 0
    fallback = int(usage["proxy_source"].eq("fallback_order_price").sum()) if not usage.empty else 0
    promotion = gate[gate["promotion_gate_pass"].eq(1)]["variant"].tolist()
    hard_pass = gate[gate["hard_constraint_pass"].eq(1)]["variant"].tolist()
    true_gate = gate[gate["variant"].eq(TRUE_PATH_VARIANT)].iloc[0]
    decision_label = (
        "true_path_1455_vwap_promote_candidate"
        if TRUE_PATH_VARIANT in promotion
        else (
            "true_path_1455_vwap_hard_pass_need_stage103_replay"
            if int(true_gate["hard_constraint_pass"]) == 1
            else "true_path_1455_vwap_hard_fail_pause_candidate_optimization"
        )
    )
    decision = {
        "stage": "Stage151",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "proxy_matched_trade_count": matched,
        "fallback_trade_count": fallback,
        "true_path_trade_count": int(len(usage)),
        "rerun_vs_stage403_end_equity_delta": rerun_end - stage403_end,
        "hard_constraint_pass_variants": hard_pass,
        "promotion_gate_pass_variants": promotion,
        "true_path_failed_hard_constraints": str(true_gate.get("failed_hard_constraints", "")),
        "true_path_score_90d": _safe_float(true_gate.get("score_90d")),
        "true_path_score_180d": _safe_float(true_gate.get("score_180d")),
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
        "next_step": "若Stage079真实路径仍通过硬约束，则用同一成交口径重算Stage103/xsmom；若失败，则暂停短持有优化并先修执行口径。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, usage, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
