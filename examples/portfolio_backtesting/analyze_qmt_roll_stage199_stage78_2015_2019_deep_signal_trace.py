from __future__ import annotations

import contextlib
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage199_stage78_2015_2019_deep_signal_trace_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage199_stage78_2015_2019_deep_signal_trace"

ANALYSIS_START: datetime = datetime(2015, 1, 5)
ANALYSIS_END: datetime = datetime(2019, 12, 31)
PRELOAD_START: datetime = datetime(2014, 1, 5)
CAPITAL: float = 200_000.0

READINESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SIGNAL_TRACE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_trace_{MODEL_TAG}.csv"
CANDIDATES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def to_markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_无记录_"
    view = df.head(max_rows).copy()
    headers = list(view.columns)
    rows = [[str(row.get(col, "")) for col in headers] for _, row in view.iterrows()]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    if len(df) > max_rows:
        lines.append(f"\n_仅展示前{max_rows}行，共{len(df)}行。_")
    return "\n".join(lines)


def diagnose_entry_filter(strategy: QmtRollPortfolioStrategy, signal: str, history: pd.DataFrame) -> tuple[bool, str]:
    if not signal:
        return False, "empty_signal"

    is_long = signal.startswith("long")
    is_short = signal.startswith("short")

    if strategy.ma5_extreme_filter_enabled:
        mode = "max" if is_long else "min"
        ok, _, _ = strategy._is_latest_ma_extreme(
            history,
            period=strategy.ma_short,
            compare_days=strategy.ma5_extreme_compare_days,
            mode=mode,
        )
        if not ok:
            return False, "ma5_extreme_filter"

    if strategy.ma5_angle_reversal_filter_enabled:
        angle_filter = strategy._evaluate_ma5_angle_reversal_filter(
            history,
            period=strategy.ma_short,
            lookback_days=strategy.ma5_angle_reversal_lookback_days,
            angle_threshold_deg=strategy.ma5_angle_reversal_angle_threshold_deg,
        )
        if angle_filter.get("should_block"):
            return False, "ma5_angle_reversal_filter"

    if is_short and strategy.short_ma5_slope_filter_enabled:
        ma5_slope = strategy._get_ma_slope_direction(history, period=strategy.ma_short)
        if ma5_slope > 0:
            return False, "short_ma5_slope_filter"

    if strategy.wick_chop_filter_enabled:
        direction = "long" if is_long else "short"
        if not strategy._is_simple_ma_trend(history, direction, 3):
            ok, _, _ = strategy._wick_chop_filter_ok(
                history,
                strategy.wick_chop_filter_lookback,
                strategy.wick_chop_filter_max_days,
            )
            if not ok:
                return False, "wick_chop_filter"

    return True, ""


def install_signal_trace_patch() -> tuple[Any, Any]:
    original_on_bars = QmtRollPortfolioStrategy.on_bars
    original_generate_signal = QmtRollPortfolioStrategy._generate_signal

    def traced_on_bars(self: QmtRollPortfolioStrategy, bars: dict[str, Any]) -> None:
        if not hasattr(self, "stage199_readiness_rows"):
            self.stage199_readiness_rows = []
        if not hasattr(self, "stage199_signal_trace_rows"):
            self.stage199_signal_trace_rows = []

        current_date = next(iter(bars.values())).datetime.strftime("%Y-%m-%d") if bars else ""
        mapping_today = self.daily_mapping.get(current_date, {}) if current_date else {}
        self._stage199_current_date = current_date
        self._stage199_am_to_contract = {id(am): vt_symbol for vt_symbol, am in self.ams.items()}
        self._stage199_contract_to_product = {contract: product for product, contract in mapping_today.items()}

        original_on_bars(self, bars)

        for product_vt in self.product_symbols:
            target_contract = mapping_today.get(product_vt, "")
            target_bar = bars.get(target_contract) if target_contract else None
            am = self.ams.get(target_contract) if target_contract else None
            self.stage199_readiness_rows.append(
                {
                    "date": current_date,
                    "product_vt_symbol": product_vt,
                    "target_contract": target_contract,
                    "has_mapping": int(bool(target_contract)),
                    "has_target_bar": int(target_bar is not None),
                    "am_exists": int(am is not None),
                    "am_inited": int(bool(am is not None and am.inited)),
                }
            )

    def traced_generate_signal(
        self: QmtRollPortfolioStrategy,
        am: Any,
        history: pd.DataFrame,
    ) -> dict[str, Any]:
        if not hasattr(self, "stage199_signal_trace_rows"):
            self.stage199_signal_trace_rows = []

        close = pd.Series(am.close_array)
        ma_short = close.rolling(self.ma_short).mean()
        ma_mid = close.rolling(self.ma_mid).mean()
        ma_long = close.rolling(self.ma_long).mean()
        ma_extra_long = close.rolling(self.ma_extra_long).mean()
        rsi_value = float(am.rsi(self.rsi_length))
        dif, dea, hist = self._calculate_macd(close)

        required_values = [
            ma_short.iloc[-1],
            ma_mid.iloc[-1],
            ma_long.iloc[-1],
            ma_extra_long.iloc[-1],
            ma_short.iloc[-2],
            ma_mid.iloc[-2],
            ma_long.iloc[-2],
            ma_extra_long.iloc[-2],
            dif.iloc[-1],
            dif.iloc[-2],
            dea.iloc[-1],
            dea.iloc[-2],
            hist.iloc[-1],
        ]
        indicator_ready = not any(pd.isna(value) for value in required_values)

        contract = getattr(self, "_stage199_am_to_contract", {}).get(id(am), "")
        product = getattr(self, "_stage199_contract_to_product", {}).get(contract, "")
        date_text = str(getattr(self, "_stage199_current_date", ""))

        if not indicator_ready:
            self.stage199_signal_trace_rows.append(
                {
                    "date": date_text,
                    "product_vt_symbol": product,
                    "contract_vt_symbol": contract,
                    "stage": "indicator_not_ready",
                    "raw_signal": "",
                    "final_signal": "",
                    "filter_block_reason": "indicator_not_ready",
                    "history_len": int(len(history)),
                    "bullish_alignment": 0,
                    "bearish_alignment": 0,
                    "macd_hist": float("nan"),
                }
            )
            return self._signal_result(
                "", False, False, float("nan"), float("nan"), float("nan"), float("nan"), "regular", False
            )

        short_y, short_t = float(ma_short.iloc[-2]), float(ma_short.iloc[-1])
        mid_y, mid_t = float(ma_mid.iloc[-2]), float(ma_mid.iloc[-1])
        long_y, long_t = float(ma_long.iloc[-2]), float(ma_long.iloc[-1])
        extra_y, extra_t = float(ma_extra_long.iloc[-2]), float(ma_extra_long.iloc[-1])

        golden_5_10 = short_y <= mid_y and short_t > mid_t
        death_5_10 = short_y >= mid_y and short_t < mid_t
        golden_10_20 = mid_y <= long_y and mid_t > long_t
        death_10_20 = mid_y >= long_y and mid_t < long_t
        golden_20_40 = long_y <= extra_y and long_t > extra_t
        death_20_40 = long_y >= extra_y and long_t < extra_t
        bullish_alignment = short_t > mid_t > long_t > extra_t
        bearish_alignment = short_t < mid_t < long_t < extra_t

        macd_hist_t = float(hist.iloc[-1])
        macd_golden = float(dif.iloc[-2]) <= float(dea.iloc[-2]) and float(dif.iloc[-1]) > float(dea.iloc[-1])
        macd_death = float(dif.iloc[-2]) >= float(dea.iloc[-2]) and float(dif.iloc[-1]) < float(dea.iloc[-1])
        allow_long = macd_hist_t > 0
        allow_short = macd_hist_t < 0
        if self.enable_rsi_filter:
            allow_long = allow_long and rsi_value <= self.rsi_long_max
            allow_short = allow_short and rsi_value >= self.rsi_short_min

        raw_signal = ""
        pattern_case = ""
        if (golden_5_10 or death_5_10) and not (golden_10_20 or death_10_20 or golden_20_40 or death_20_40):
            if golden_5_10 and bullish_alignment and allow_long:
                raw_signal = "long_case1a"
                pattern_case = "ma5_10_cross"
            elif death_5_10 and bearish_alignment and allow_short:
                raw_signal = "short_case1a"
                pattern_case = "ma5_10_cross"
        elif golden_10_20 or death_10_20 or golden_20_40 or death_20_40:
            if (golden_10_20 or golden_20_40) and bullish_alignment and allow_long:
                raw_signal = "long_case2"
                pattern_case = "ma10_20_or_20_40_cross"
            elif (death_10_20 or death_20_40) and bearish_alignment and allow_short:
                raw_signal = "short_case2"
                pattern_case = "ma10_20_or_20_40_cross"
        else:
            if macd_golden and bullish_alignment and allow_long:
                raw_signal = "long_case3"
                pattern_case = "macd_cross"
            elif macd_death and bearish_alignment and allow_short:
                raw_signal = "short_case3"
                pattern_case = "macd_cross"

        filter_ok, filter_reason = diagnose_entry_filter(self, raw_signal, history)
        final_signal = raw_signal if filter_ok else ""
        result = original_generate_signal(self, am, history)

        self.stage199_signal_trace_rows.append(
            {
                "date": date_text,
                "product_vt_symbol": product,
                "contract_vt_symbol": contract,
                "stage": "signal_ready",
                "raw_signal": raw_signal,
                "final_signal": str(result.get("signal", "")),
                "local_final_signal": final_signal,
                "filter_block_reason": "" if filter_ok else filter_reason,
                "pattern_case": pattern_case,
                "history_len": int(len(history)),
                "bullish_alignment": int(bullish_alignment),
                "bearish_alignment": int(bearish_alignment),
                "golden_5_10": int(golden_5_10),
                "death_5_10": int(death_5_10),
                "golden_10_20": int(golden_10_20),
                "death_10_20": int(death_10_20),
                "golden_20_40": int(golden_20_40),
                "death_20_40": int(death_20_40),
                "macd_golden": int(macd_golden),
                "macd_death": int(macd_death),
                "macd_hist": macd_hist_t,
                "allow_long": int(allow_long),
                "allow_short": int(allow_short),
                "rsi_value": rsi_value,
            }
        )
        return result

    QmtRollPortfolioStrategy.on_bars = traced_on_bars
    QmtRollPortfolioStrategy._generate_signal = traced_generate_signal
    return original_on_bars, original_generate_signal


def restore_signal_trace_patch(original_on_bars: Any, original_generate_signal: Any) -> None:
    QmtRollPortfolioStrategy.on_bars = original_on_bars
    QmtRollPortfolioStrategy._generate_signal = original_generate_signal


def build_trades_df(engine: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in engine.get_all_trades():
        rows.append(
            {
                "datetime": trade.datetime,
                "date": trade.datetime.date().isoformat(),
                "year": trade.datetime.year,
                "vt_symbol": trade.vt_symbol,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": float(trade.volume),
                "vt_tradeid": trade.vt_tradeid,
            }
        )
    return pd.DataFrame(rows)


def normalize_candidates(candidate_df: pd.DataFrame) -> pd.DataFrame:
    if candidate_df.empty:
        return candidate_df
    df = candidate_df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
    df["date"] = df["datetime"].dt.date.astype(str)
    df["year"] = df["datetime"].dt.year
    return df


def build_summary(
    readiness_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in range(2015, 2020):
        readiness = readiness_df[readiness_df["year"] == year] if not readiness_df.empty else pd.DataFrame()
        trace = trace_df[trace_df["year"] == year] if not trace_df.empty else pd.DataFrame()
        candidates = candidate_df[candidate_df["year"] == year] if not candidate_df.empty else pd.DataFrame()
        trades = trades_df[trades_df["year"] == year] if not trades_df.empty else pd.DataFrame()
        raw_signal_rows = trace[trace["raw_signal"].astype(str) != ""] if not trace.empty else pd.DataFrame()
        final_signal_rows = trace[trace["final_signal"].astype(str) != ""] if not trace.empty else pd.DataFrame()
        blocked_rows = raw_signal_rows[raw_signal_rows["final_signal"].astype(str) == ""] if not raw_signal_rows.empty else pd.DataFrame()
        filter_counts = Counter(blocked_rows.get("filter_block_reason", pd.Series(dtype=str)).fillna("").astype(str))
        raw_signal_counts = Counter(raw_signal_rows.get("raw_signal", pd.Series(dtype=str)).fillna("").astype(str))
        rows.append(
            {
                "year": year,
                "mapped_product_days": int(readiness["has_mapping"].sum()) if not readiness.empty else 0,
                "target_bar_product_days": int(readiness["has_target_bar"].sum()) if not readiness.empty else 0,
                "am_inited_product_days": int(readiness["am_inited"].sum()) if not readiness.empty else 0,
                "signal_function_calls": int(len(trace)),
                "indicator_not_ready_count": int((trace["stage"].astype(str) == "indicator_not_ready").sum())
                if not trace.empty
                else 0,
                "raw_signal_count": int(len(raw_signal_rows)),
                "final_signal_count": int(len(final_signal_rows)),
                "filter_block_count": int(len(blocked_rows)),
                "candidate_count": int(len(candidates)),
                "opened_candidate_count": int((candidates["candidate_status"].astype(str) == "opened").sum())
                if not candidates.empty
                else 0,
                "trade_count": int(len(trades)),
                "open_trade_count": int((trades["offset"].astype(str) == "Open").sum()) if not trades.empty else 0,
                "raw_signal_mix": json.dumps(
                    {key: value for key, value in raw_signal_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "filter_block_reasons": json.dumps(
                    {key: value for key, value in filter_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    *,
    stats: dict[str, Any],
    summary_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> None:
    raw_signals = trace_df[trace_df["raw_signal"].astype(str) != ""].copy()
    blocked = raw_signals[raw_signals["final_signal"].astype(str) == ""].copy()
    candidate_view = candidate_df[
        ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal", "candidate_status", "skip_reason"]
    ].copy() if not candidate_df.empty else pd.DataFrame()
    trace_view = raw_signals[
        [
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "raw_signal",
            "final_signal",
            "filter_block_reason",
            "pattern_case",
            "bullish_alignment",
            "bearish_alignment",
        ]
    ].copy() if not raw_signals.empty else pd.DataFrame()
    blocked_view = blocked[
        ["date", "product_vt_symbol", "contract_vt_symbol", "raw_signal", "filter_block_reason", "pattern_case"]
    ].copy() if not blocked.empty else pd.DataFrame()

    report = f"""# Stage199 第78 2015-2019深度信号定位

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载：{PRELOAD_START.date()}
- 资金：{CAPITAL:,.0f}
- 方法：运行时临时埋点`_generate_signal`，拆分主力映射、bar可用、指标初始化、原始信号、过滤后信号、候选、成交。

## 回测结果

- 期末权益：{_fmt(stats.get("end_balance"), 2)}
- 总收益：{_fmt(stats.get("total_return"), 4)}%
- 最大回撤：{_fmt(stats.get("max_ddpercent"), 4)}%
- Sharpe：{_fmt(stats.get("sharpe_ratio"), 4)}
- 总滑点：{_fmt(stats.get("total_slippage"), 2)}
- 总交易次数：{_safe_int(stats.get("total_trade_count"))}

## 年度深度漏斗

{to_markdown_table(summary_df)}

## 原始信号明细

{to_markdown_table(trace_view, max_rows=80)}

## 被入场过滤器打掉的原始信号

{to_markdown_table(blocked_view, max_rows=80)}

## 候选记录

{to_markdown_table(candidate_view, max_rows=80)}

## 成交记录

{to_markdown_table(trades_df, max_rows=80)}

## 结论

1. 你说得对：不能说2015-2018“完全没信号”。更准确的说法是：正式入场候选很少，且早期原始信号大多在进入候选前或候选后被规则过滤。
2. 本报告区分了`raw_signal_count`和`candidate_count`。前者是策略形态层看到的原始信号，后者才是第78实际准备进入开仓计划的候选。
3. 若2015-2018存在较多`raw_signal_count`但`final_signal_count`低，说明问题在入场过滤器；若`signal_function_calls`本身低，说明问题更偏数据/主力映射/指标初始化。
4. 即使早期有原始信号，也不能直接放宽过滤器。下一步只能做只读A/B解释实验，不应直接合入第78正式版。

## 过拟合反思

- 本阶段只做埋点和归因，不改参数，不构成过拟合。
- 但如果下一步为了让2015多交易而放宽短空或过滤器，就会有明显过拟合风险，必须只读A/B。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    original_on_bars, original_generate_signal = install_signal_trace_patch()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine, _, stats = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_official_stage78_overrides(),
                analysis_start=ANALYSIS_START,
                analysis_end=ANALYSIS_END,
                preload_start=PRELOAD_START,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=OUTPUT_PREFIX,
                chart_title="Stage199 Stage78 2015-2019 Deep Signal Trace",
            )
    finally:
        restore_signal_trace_patch(original_on_bars, original_generate_signal)

    strategy = engine.strategy
    readiness_df = pd.DataFrame(getattr(strategy, "stage199_readiness_rows", []))
    trace_df = pd.DataFrame(getattr(strategy, "stage199_signal_trace_rows", []))
    candidate_df = normalize_candidates(build_entry_candidate_snapshots_df(engine))
    trades_df = build_trades_df(engine)

    if not readiness_df.empty:
        readiness_df["date"] = pd.to_datetime(readiness_df["date"])
        readiness_df["year"] = readiness_df["date"].dt.year
    if not trace_df.empty:
        trace_df["date"] = pd.to_datetime(trace_df["date"])
        trace_df["year"] = trace_df["date"].dt.year

    summary_df = build_summary(readiness_df, trace_df, candidate_df, trades_df)

    readiness_df.to_csv(READINESS_CSV_PATH, index=False, encoding="utf-8-sig")
    trace_df.to_csv(SIGNAL_TRACE_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_df.to_csv(CANDIDATES_CSV_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_CSV_PATH, index=False, encoding="utf-8-sig")
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    write_report(stats=stats, summary_df=summary_df, trace_df=trace_df, candidate_df=candidate_df, trades_df=trades_df)

    print(f"summary: {SUMMARY_CSV_PATH}")
    print(f"readiness: {READINESS_CSV_PATH}")
    print(f"signal_trace: {SIGNAL_TRACE_CSV_PATH}")
    print(f"candidates: {CANDIDATES_CSV_PATH}")
    print(f"trades: {TRADES_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
