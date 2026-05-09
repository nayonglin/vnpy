from __future__ import annotations

import contextlib
import io
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from vnpy.trader.utility import ArrayManager

from analyze_qmt_roll_stage199_stage78_2015_2019_deep_signal_trace import (
    build_summary,
    build_trades_df,
    install_signal_trace_patch,
    normalize_candidates,
    restore_signal_trace_patch,
    to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage201_stage78_continuous_indicator_validation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage201_stage78_continuous_indicator_validation"

ANALYSIS_START: datetime = datetime(2015, 1, 5)
ANALYSIS_END: datetime = datetime(2019, 12, 31)
PRELOAD_START: datetime = datetime(2014, 1, 5)
CAPITAL: float = 200_000.0

STATS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
YEARLY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_summary_{MODEL_TAG}.csv"
SIGNAL_MIX_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_mix_{MODEL_TAG}.csv"
TRADES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def install_continuous_indicator_on_bars(original_on_bars: Any) -> Any:
    def continuous_indicator_on_bars(self: QmtRollPortfolioStrategy, bars: dict[str, Any]) -> None:
        if not hasattr(self, "stage199_readiness_rows"):
            self.stage199_readiness_rows = []
        if not hasattr(self, "stage199_signal_trace_rows"):
            self.stage199_signal_trace_rows = []
        if not hasattr(self, "stage201_product_ams"):
            am_size_floor = max(int(self.array_manager_size_floor or 140), 1)
            am_size = max(int(self.ma_extra_long) + int(self.donchian_entry_period) + 20, am_size_floor)
            self.stage201_product_ams = {
                product_vt: ArrayManager(am_size) for product_vt in self.product_symbols
            }

        if not bars:
            return original_on_bars(self, bars)

        current_date = next(iter(bars.values())).datetime.strftime("%Y-%m-%d")
        mapping_today = self.daily_mapping.get(current_date, {})

        replacements: dict[str, Any] = {}
        trace_am_to_contract: dict[int, str] = {}
        trace_contract_to_product: dict[str, str] = {}
        for product_vt, target_contract in mapping_today.items():
            if not target_contract or target_contract not in bars:
                continue
            product_am = self.stage201_product_ams.get(product_vt)
            if product_am is None:
                continue
            replacements[target_contract] = self.ams.get(target_contract)
            self.ams[target_contract] = product_am
            trace_am_to_contract[id(product_am)] = target_contract
            trace_contract_to_product[target_contract] = product_vt

        self._stage199_current_date = current_date
        self._stage199_am_to_contract = trace_am_to_contract
        self._stage199_contract_to_product = trace_contract_to_product

        try:
            original_on_bars(self, bars)
        finally:
            for vt_symbol, original_am in replacements.items():
                if original_am is not None:
                    self.ams[vt_symbol] = original_am

        for product_vt in self.product_symbols:
            target_contract = mapping_today.get(product_vt, "")
            target_bar = bars.get(target_contract) if target_contract else None
            product_am = self.stage201_product_ams.get(product_vt)
            self.stage199_readiness_rows.append(
                {
                    "date": current_date,
                    "product_vt_symbol": product_vt,
                    "target_contract": target_contract,
                    "has_mapping": int(bool(target_contract)),
                    "has_target_bar": int(target_bar is not None),
                    "am_exists": int(product_am is not None),
                    "am_inited": int(bool(product_am is not None and product_am.inited)),
                }
            )

    QmtRollPortfolioStrategy.on_bars = continuous_indicator_on_bars
    return continuous_indicator_on_bars


def build_signal_mix(case_name: str, trace_df: pd.DataFrame) -> pd.DataFrame:
    if trace_df.empty:
        return pd.DataFrame(columns=["case_name", "year", "raw_signal", "count"])
    raw = trace_df[trace_df["raw_signal"].fillna("").astype(str) != ""].copy()
    if raw.empty:
        return pd.DataFrame(columns=["case_name", "year", "raw_signal", "count"])
    mix = raw.groupby(["year", "raw_signal"]).size().reset_index(name="count")
    mix.insert(0, "case_name", case_name)
    return mix.sort_values(["case_name", "year", "raw_signal"])


def run_case(case_name: str, continuous_indicator: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    original_on_bars, original_generate_signal = install_signal_trace_patch()
    if continuous_indicator:
        install_continuous_indicator_on_bars(original_on_bars)
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
                file_prefix=f"{OUTPUT_PREFIX}_{case_name}",
                chart_title=f"Stage201 {case_name}",
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
    if not trades_df.empty:
        trades_df.insert(0, "case_name", case_name)

    yearly = build_summary(readiness_df, trace_df, candidate_df, trades_df.drop(columns=["case_name"], errors="ignore"))
    yearly.insert(0, "case_name", case_name)
    signal_mix = build_signal_mix(case_name, trace_df)

    stats_row = {
        "case_name": case_name,
        "continuous_indicator": int(continuous_indicator),
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_ddpercent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_trade_count": _safe_int(stats.get("total_trade_count")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "total_commission": _safe_float(stats.get("total_commission")),
        "raw_signal_count": int(yearly["raw_signal_count"].sum()),
        "final_signal_count": int(yearly["final_signal_count"].sum()),
        "candidate_count": int(yearly["candidate_count"].sum()),
        "opened_candidate_count": int(yearly["opened_candidate_count"].sum()),
        "am_inited_product_days": int(yearly["am_inited_product_days"].sum()),
        "signal_function_calls": int(yearly["signal_function_calls"].sum()),
    }
    return yearly, signal_mix, trades_df, stats_row


def write_report(stats_df: pd.DataFrame, yearly_df: pd.DataFrame, signal_mix_df: pd.DataFrame) -> None:
    compact_stats = stats_df[
        [
            "case_name",
            "continuous_indicator",
            "end_balance",
            "total_return_pct",
            "max_ddpercent",
            "sharpe_ratio",
            "total_trade_count",
            "raw_signal_count",
            "candidate_count",
            "opened_candidate_count",
            "am_inited_product_days",
        ]
    ].copy()
    compact_stats["end_balance"] = compact_stats["end_balance"].map(lambda value: _fmt(value, 2))
    for column in ["total_return_pct", "max_ddpercent", "sharpe_ratio"]:
        compact_stats[column] = compact_stats[column].map(lambda value: _fmt(value, 4))

    yearly_view = yearly_df[
        [
            "case_name",
            "year",
            "am_inited_product_days",
            "signal_function_calls",
            "raw_signal_count",
            "final_signal_count",
            "candidate_count",
            "opened_candidate_count",
            "trade_count",
            "open_trade_count",
            "raw_signal_mix",
            "filter_block_reasons",
        ]
    ].copy()

    report = f"""# Stage201 第78 连续主力指标只读验证

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载：{PRELOAD_START.date()}
- 资金：{CAPITAL:,.0f}
- baseline：第78正式合约级AM，信号和执行都使用当日真实主力合约自己的AM。
- continuous_indicator_raw：按品种维护连续主力AM，信号用连续主力AM，执行仍使用当日真实主力合约。
- 注意：本阶段连续序列是未复权的主力拼接，先用于验证“换月导致指标历史断裂”的方向，不作为正式交易口径。

## 总体结果

{to_markdown_table(compact_stats, max_rows=20)}

## 年度漏斗

{to_markdown_table(yearly_view, max_rows=80)}

## 原始信号分布

{to_markdown_table(signal_mix_df, max_rows=120)}

## 结论

1. 如果`continuous_indicator_raw`相对baseline显著增加2015-2018的AM初始化天数和原始信号，说明早期无信号主要来自换月后合约级AM历史断裂。
2. 这个方案比直接把AM长度从120降到90更接近问题本质，因为它不缩短指标窗口，而是把同一品种主力历史串起来。
3. 但当前连续序列还没有做复权/价差修正，换月跳价可能污染均线/MACD，所以只能作为只读验证，不能直接合入正式第78。
4. 后续如果继续，应做“后复权/比值复权连续主力指标”并和未复权拼接对照。

## 过拟合反思

- 本阶段不选参数，不改正式第78，只验证工程口径，因此不是正式过拟合。
- 若后续按2015-2019收益选择某种复权方式或窗口长度，则会有过拟合风险，必须用2020后正式样本和影子盘约束反证。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yearly_frames: list[pd.DataFrame] = []
    signal_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    stats_rows: list[dict[str, Any]] = []

    for case_name, continuous_indicator in [
        ("baseline_contract_am", False),
        ("continuous_indicator_raw", True),
    ]:
        print(f"[stage201] run {case_name}")
        yearly, signal_mix, trades, stats_row = run_case(case_name, continuous_indicator)
        yearly_frames.append(yearly)
        signal_frames.append(signal_mix)
        trade_frames.append(trades)
        stats_rows.append(stats_row)

    yearly_df = pd.concat(yearly_frames, ignore_index=True)
    signal_mix_df = pd.concat(signal_frames, ignore_index=True)
    trades_df = pd.concat(trade_frames, ignore_index=True)
    stats_df = pd.DataFrame(stats_rows)

    stats_df.to_csv(STATS_CSV_PATH, index=False, encoding="utf-8-sig")
    yearly_df.to_csv(YEARLY_CSV_PATH, index=False, encoding="utf-8-sig")
    signal_mix_df.to_csv(SIGNAL_MIX_CSV_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_CSV_PATH, index=False, encoding="utf-8-sig")
    write_report(stats_df, yearly_df, signal_mix_df)

    print(f"stats: {STATS_CSV_PATH}")
    print(f"yearly: {YEARLY_CSV_PATH}")
    print(f"signal_mix: {SIGNAL_MIX_CSV_PATH}")
    print(f"trades: {TRADES_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
