from __future__ import annotations

from collections import Counter
from copy import copy
from datetime import datetime, timedelta
import json
import math
import os
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
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


STAGE = os.getenv("STAGE497_STAGE", "Stage197")
MODEL_TAG = os.getenv("STAGE497_MODEL_TAG", "stage497_consistent_preclose_full_bar_replay_v1")
OUTPUT_PREFIX = os.getenv("STAGE497_OUTPUT_PREFIX", "qmt_roll_stage497_consistent_preclose_full_bar_replay")
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RERUN_VARIANT = "stage079_rerun_same_day_close"
PRECLOSE_VARIANT = os.getenv(
    "STAGE497_PRECLOSE_VARIANT",
    "stage079_consistent_preclose_full_bar_fill_first_open",
)
PRECLOSE_LABEL = os.getenv(
    "STAGE497_PRECLOSE_LABEL",
    "Stage079 consistent preclose full bar + first fill",
)

SYNTH_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_synthetic_stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv"
)
EXTRA_SYNTH_PATHS = [
    Path(item.strip())
    for item in os.getenv("STAGE497_EXTRA_SYNTHETIC_PATHS", "").split(",")
    if item.strip()
]

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
BAR_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bar_usage_{MODEL_TAG}.csv"
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
        return {str(k): _json_safe(item) for k, item in value.items()}
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


def _naive_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _direction_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _offset_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _load_preclose_maps() -> tuple[dict[tuple[pd.Timestamp, str], dict[str, float]], pd.DataFrame]:
    frames = [pd.read_csv(SYNTH_PATH, encoding="utf-8-sig")]
    for path in EXTRA_SYNTH_PATHS:
        resolved = path if path.is_absolute() else OUTPUT_DIR / path
        if not resolved.exists():
            raise FileNotFoundError(resolved)
        frames.append(pd.read_csv(resolved, encoding="utf-8-sig"))
    synth = pd.concat(frames, ignore_index=True)
    synth["date"] = pd.to_datetime(synth["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in [
        "synthetic_open",
        "synthetic_high",
        "synthetic_low",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "fill_first_open",
        "fill_last_close",
        "fill_volume",
        "strict_full_preclose_ready",
    ]:
        synth[column] = pd.to_numeric(synth.get(column, np.nan), errors="coerce")
    synth = synth.drop_duplicates(["date", "vt_symbol"], keep="last").reset_index(drop=True)
    ready = synth[
        synth["date"].notna()
        & synth["vt_symbol"].notna()
        & synth["strict_full_preclose_ready"].eq(1)
    ].copy()
    if len(ready) != len(synth):
        raise RuntimeError(f"Stage196 synthetic is not fully ready: {len(ready)}/{len(synth)}")

    mapping: dict[tuple[pd.Timestamp, str], dict[str, float]] = {}
    for row in ready.itertuples(index=False):
        key = (_naive_date(row.date), str(row.vt_symbol))
        mapping[key] = {
            "open": float(row.synthetic_open),
            "high": float(row.synthetic_high),
            "low": float(row.synthetic_low),
            "close": float(row.synthetic_close),
            "volume": float(row.synthetic_volume),
            "open_interest": float(row.synthetic_open_interest),
            "fill_first_open": float(row.fill_first_open),
            "fill_last_close": float(row.fill_last_close),
            "fill_volume": float(row.fill_volume),
        }
    return mapping, ready


class ConsistentPrecloseEngine(SameDayCloseBacktestingEngine):
    """Use frozen preclose OHLCVOI as strategy input and the same fill window for execution."""

    def __init__(self, preclose_map: dict[tuple[pd.Timestamp, str], dict[str, float]]) -> None:
        super().__init__()
        self.preclose_map = preclose_map
        self.synthetic_bar_keys_used: set[tuple[pd.Timestamp, str]] = set()
        self.bar_usage_counter: Counter[str] = Counter()
        self.trade_usage_rows: list[dict[str, Any]] = []

    def _replace_bar(self, dt: Any, vt_symbol: str, bar: BarData) -> BarData:
        key = (_naive_date(dt), str(vt_symbol))
        row = self.preclose_map.get(key)
        if row is None:
            self.bar_usage_counter["original_bar_no_synthetic"] += 1
            return bar
        replaced = copy(bar)
        replaced.open_price = float(row["open"])
        replaced.high_price = float(row["high"])
        replaced.low_price = float(row["low"])
        replaced.close_price = float(row["close"])
        replaced.volume = float(row["volume"])
        replaced.open_interest = float(row["open_interest"])
        self.synthetic_bar_keys_used.add(key)
        self.bar_usage_counter["synthetic_preclose_bar"] += 1
        return replaced

    def new_bars(self, dt) -> None:
        self.datetime = dt

        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            bar: BarData | None = self.history_data.get((dt, vt_symbol), None)

            if bar:
                bar = self._replace_bar(dt, vt_symbol, bar)
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
                bar = self._replace_bar(dt, vt_symbol, bar)
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar

        self.strategy.on_bars(bars)
        self.cross_limit_order_on_close()

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def _resolve_trade_price(self, order: Any) -> tuple[float, str, float]:
        fallback_price = float(order.price)
        key = (_naive_date(self.datetime), str(order.vt_symbol))
        row = self.preclose_map.get(key)
        fill = _safe_float(row.get("fill_first_open") if row else np.nan, np.nan)
        if row is not None and pd.notna(fill) and fill > 0.0:
            return fill, "stage196_fill_first_open", _safe_float(row.get("fill_volume"), np.nan)
        return fallback_price, "fallback_order_price_no_stage196_fill", np.nan

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

            trade_price, fill_source, fill_volume = self._resolve_trade_price(order)
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
            self.trade_usage_rows.append(
                {
                    "date": _naive_date(self.datetime),
                    "vt_symbol": str(order.vt_symbol),
                    "direction": _direction_text(order.direction),
                    "offset": _offset_text(order.offset),
                    "orderid": str(order.orderid),
                    "order_price": float(order.price),
                    "trade_price": float(trade_price),
                    "fill_source": fill_source,
                    "fill_volume": fill_volume,
                    "order_volume": float(order.volume),
                    "bar_close_price": close_price,
                }
            )


def _make_engine(preclose_map: dict[tuple[pd.Timestamp, str], dict[str, float]] | None) -> SameDayCloseBacktestingEngine:
    return ConsistentPrecloseEngine(preclose_map) if preclose_map is not None else SameDayCloseBacktestingEngine()


def _run_c3_engine(
    *,
    preclose_map: dict[tuple[pd.Timestamp, str], dict[str, float]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    engine = _make_engine(preclose_map)
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
        raise RuntimeError("C3 replay produced empty daily result")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()

    trade_usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    bar_usage = pd.DataFrame(
        [
            {
                "metric": "bar_usage_counter",
                "key": key,
                "value": int(value),
            }
            for key, value in getattr(engine, "bar_usage_counter", Counter()).items()
        ]
    )
    if isinstance(engine, ConsistentPrecloseEngine):
        expected_keys = set(preclose_map or {})
        used_keys = set(engine.synthetic_bar_keys_used)
        bar_usage = pd.concat(
            [
                bar_usage,
                pd.DataFrame(
                    [
                        {"metric": "synthetic_key_coverage", "key": "expected_stage196_keys", "value": len(expected_keys)},
                        {"metric": "synthetic_key_coverage", "key": "used_stage196_keys", "value": len(used_keys)},
                        {"metric": "synthetic_key_coverage", "key": "unused_stage196_keys", "value": len(expected_keys - used_keys)},
                    ]
                ),
            ],
            ignore_index=True,
        )
    return daily, trade_usage, bar_usage


def _build_long_daily(
    baseline: pd.DataFrame,
    rerun_daily: pd.DataFrame,
    preclose_daily: pd.DataFrame,
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
    rerun["label"] = "Stage079 same-day close rerun"
    rows.append(rerun)

    preclose = preclose_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    preclose["variant"] = PRECLOSE_VARIANT
    preclose["label"] = PRECLOSE_LABEL
    rows.append(preclose)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _evaluate(long_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return s451._evaluate(long_daily)


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {
        BASELINE_VARIANT: "#4c78a8",
        RERUN_VARIANT: "#72b7b2",
        PRECLOSE_VARIANT: "#e45756",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.2)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_title("Stage079 consistent preclose full-bar replay")
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
    bar_usage: pd.DataFrame,
    trade_usage: pd.DataFrame,
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
    fallback_trades = (
        trade_usage[trade_usage["fill_source"].astype(str).ne("stage196_fill_first_open")].copy()
        if not trade_usage.empty and "fill_source" in trade_usage.columns
        else pd.DataFrame()
    )
    report = [
        f"# {STAGE} 一致预收盘完整bar真实回放",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行语义真实回放；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "- 方法：策略输入bar优先替换为 Stage196 冻结前 synthetic OHLCVOI；同日订单用同一 `14:55-15:00` 窗口 `fill_first_open` 成交。",
        "- 解释边界：若存在成交价 fallback，不能作为晋级候选，只能作为缺口归因。",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk/TqBacktest 的 K 线随时间推进更新，不能把最终日K当作冻结时点可见数据。",
        "- 通用回测原则要求决策时点与成交时点明确，否则 same-bar close 信号/成交容易产生未来函数。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 硬约束通过项：`{decision['hard_constraint_pass_variants']}`。",
        f"- 晋级通过项：`{decision['promotion_gate_pass_variants']}`。",
        f"- Stage196 synthetic key使用数：`{decision['used_stage196_keys']}/{decision['expected_stage196_keys']}`。",
        f"- 成交 fallback 数：`{decision['fallback_trade_count']}`。",
        f"- 额外合成bar输入数：`{decision['extra_synthetic_path_count']}`。",
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
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ]
        ),
        "",
        "## Bar使用审计",
        "",
        _md_table(bar_usage),
        "",
        "## 成交fallback样本",
        "",
        _md_table(fallback_trades.head(40)),
        "",
        "## 输出图",
        "",
        f"- `{CHART_PATH}`",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。本阶段只改变执行语义为预声明冻结时点，不调策略参数。",
        "- 运行后过拟合反思：见结果；若失败，不做小数补丁，先归因执行缺口。",
        "- 运行前继续价值反思：是。Stage196 已满足数据前置，需要真实回放判定 Stage079 是否仍能作为优化baseline。",
        "- 运行后继续价值反思：见决策；若硬约束失败，必须重新定义可执行baseline或数据覆盖。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preclose_map, synth = _load_preclose_maps()
    baseline = s451._load_stage079_baseline()
    rerun_daily, _, _ = _run_c3_engine(preclose_map=None)
    preclose_daily, trade_usage, bar_usage = _run_c3_engine(preclose_map=preclose_map)
    long_daily = _build_long_daily(baseline, rerun_daily, preclose_daily)
    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    trade_usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    bar_usage.to_csv(BAR_USAGE_PATH, index=False, encoding="utf-8-sig")

    summary, horizon, score, cost, gate = _evaluate(long_daily)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    _plot(long_daily)

    hard_pass = gate[gate["hard_constraint_pass"].eq(1)]["variant"].astype(str).tolist()
    promotion_pass = gate[gate["promotion_gate_pass"].eq(1)]["variant"].astype(str).tolist()
    bar_usage_map = bar_usage.set_index("key")["value"].to_dict() if not bar_usage.empty else {}
    expected_keys = int(bar_usage_map.get("expected_stage196_keys", len(preclose_map)))
    used_keys = int(bar_usage_map.get("used_stage196_keys", 0))
    fallback_trade_count = (
        int(trade_usage["fill_source"].astype(str).ne("stage196_fill_first_open").sum())
        if not trade_usage.empty and "fill_source" in trade_usage.columns
        else 0
    )
    stage403_end = float(baseline["equity"].iloc[-1])
    rerun_end = float(rerun_daily["account_equity"].iloc[-1])
    preclose_gate_pass = PRECLOSE_VARIANT in promotion_pass and fallback_trade_count == 0
    if preclose_gate_pass:
        decision_label = "consistent_preclose_full_bar_replay_promotion_candidate"
    elif PRECLOSE_VARIANT in hard_pass:
        decision_label = "consistent_preclose_full_bar_hard_pass_but_no_promotion"
    else:
        decision_label = "consistent_preclose_full_bar_replay_failed_hard_constraints"
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": PRECLOSE_VARIANT if preclose_gate_pass else "none",
        "hard_constraint_pass_variants": hard_pass,
        "promotion_gate_pass_variants": promotion_pass,
        "expected_stage196_keys": expected_keys,
        "used_stage196_keys": used_keys,
        "unused_stage196_keys": int(expected_keys - used_keys),
        "stage196_synthetic_rows": int(len(synth)),
        "extra_synthetic_path_count": int(len(EXTRA_SYNTH_PATHS)),
        "preclose_map_rows": int(len(preclose_map)),
        "trade_count": int(len(trade_usage)),
        "fallback_trade_count": fallback_trade_count,
        "rerun_vs_stage403_end_equity_delta": float(rerun_end - stage403_end),
        "outputs": {
            "daily": str(DAILY_PATH),
            "bar_usage": str(BAR_USAGE_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": (
            "若一致预收盘回放过硬约束且无fallback，再恢复3/6个月体验优化；否则先归因失败项，不做参数救援。"
        ),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, bar_usage, trade_usage, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
