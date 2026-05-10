from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval

from build_qmt_roll_stage153_stage78_anti_fit_validation import NextOpenDelayedExecutionEngine
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import (
    SameDayCloseBacktestingEngine,
    build_roll_setting,
    build_summary_row,
    compute_round_trip_win_ratio,
)
from run_qmt_roll_monte_carlo import DAILY_BLOCK_SIZE, N_SIMULATIONS, RNG_SEED, TRADE_BLOCK_SIZE
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG: str = "stage217_stage78_50w_execution_slippage_mc_suite_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage217_stage78_50w_execution_slippage_mc_suite"
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _trades_to_frame(engine: SameDayCloseBacktestingEngine) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in sorted(engine.get_all_trades(), key=lambda item: (pd.Timestamp(item.datetime), item.vt_tradeid)):
        rows.append(
            {
                "datetime": pd.Timestamp(trade.datetime).isoformat(),
                "vt_tradeid": trade.vt_tradeid,
                "vt_orderid": trade.vt_orderid,
                "symbol": trade.symbol,
                "exchange": trade.exchange.value,
                "vt_symbol": trade.vt_symbol,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": float(trade.volume),
            }
        )
    return pd.DataFrame(rows)


def _daily_to_frame(daily_df: pd.DataFrame | None) -> pd.DataFrame:
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()
    frame = daily_df.copy()
    frame.insert(0, "date", pd.to_datetime(frame.index).date)
    return frame


def _run_variant(
    *,
    execution: str,
    engine_class: type[SameDayCloseBacktestingEngine],
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    assert_stage196_database_sentinels()
    overrides = build_official_stage78_overrides()
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    engine = engine_class()
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=analysis_end,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=OFFICIAL_STAGE78_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = OFFICIAL_STAGE78_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is not None:
        analysis_df = daily_df.copy()
        analysis_df = analysis_df.loc[
            (analysis_df.index >= analysis_start.date()) & (analysis_df.index <= analysis_end.date())
        ]
    else:
        analysis_df = pd.DataFrame()

    statistics: dict[str, Any] = engine.calculate_statistics(analysis_df)
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count
    summary = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        execution=execution,
        official_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        model_tag=MODEL_TAG,
        capital=OFFICIAL_STAGE78_CAPITAL,
        base_risk_ratio=BASE_RISK_RATIO,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        win_count=win_count,
        round_trip_count=round_trip_count,
    )
    return _daily_to_frame(analysis_df), _trades_to_frame(engine), summary


def _path_metrics_from_pnl(net_pnl: np.ndarray, initial_capital: float) -> dict[str, float]:
    if net_pnl.size == 0:
        return {
            "end_balance": initial_capital,
            "total_return_pct": 0.0,
            "max_drawdown": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    equity = initial_capital + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl, dtype=float), where=previous != 0)
    high = np.maximum.accumulate(np.insert(equity, 0, initial_capital))[1:]
    drawdown = equity - high
    drawdown_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown, dtype=float), where=high != 0) * 100.0
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(240.0)) if std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _build_slippage_stress(execution: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()
    net_pnl = pd.to_numeric(daily_df["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    slippage = pd.to_numeric(daily_df.get("slippage", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
        metrics = _path_metrics_from_pnl(stressed_net_pnl, OFFICIAL_STAGE78_CAPITAL)
        rows.append(
            {
                "execution": execution,
                "slippage_multiplier": multiplier,
                **metrics,
                "total_slippage": float(slippage.sum() * multiplier),
                "total_net_pnl": float(stressed_net_pnl.sum()),
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "model_tag": MODEL_TAG,
            }
        )
    return pd.DataFrame(rows)


def _build_round_trip_pnls(trades_df: pd.DataFrame, size_map: dict[str, float]) -> np.ndarray:
    if trades_df.empty:
        return np.array([], dtype=float)
    frame = trades_df.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame.sort_values(["datetime", "vt_tradeid"], inplace=True)
    open_queues: dict[tuple[str, str], list[dict[str, float]]] = {}
    realized: list[float] = []
    for row in frame.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        direction = str(row.direction)
        offset = str(row.offset)
        price = float(row.price)
        volume = float(row.volume)
        size = float(size_map.get(vt_symbol, 1.0))
        if offset == "Open":
            position_direction = "long" if direction == "Long" else "short"
            open_queues.setdefault((vt_symbol, position_direction), []).append({"price": price, "volume": volume})
            continue
        position_direction = "long" if direction == "Short" else "short"
        queue = open_queues.setdefault((vt_symbol, position_direction), [])
        remain = volume
        while remain > 1e-9 and queue:
            entry = queue[0]
            matched = min(remain, float(entry["volume"]))
            entry_price = float(entry["price"])
            pnl = (price - entry_price) * matched * size if position_direction == "long" else (entry_price - price) * matched * size
            realized.append(float(pnl))
            entry["volume"] = float(entry["volume"]) - matched
            remain -= matched
            if float(entry["volume"]) <= 1e-9:
                queue.pop(0)
    return np.array(realized, dtype=float)


def _calculate_path_metrics(values: np.ndarray, initial_capital: float) -> dict[str, float]:
    if values.size == 0:
        return {
            "end_balance": initial_capital,
            "total_return_pct": 0.0,
            "max_drawdown": 0.0,
            "max_dd_percent": 0.0,
            "min_balance": initial_capital,
        }
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_percent = np.divide(drawdown, high, out=np.zeros_like(drawdown, dtype=float), where=high != 0) * 100.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_percent.min()),
        "min_balance": float(values.min()),
    }


def _simulate_trade_bootstrap(round_trip_pnls: np.ndarray, rng: np.random.Generator, profile: str) -> pd.DataFrame:
    n = len(round_trip_pnls)
    if n == 0:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    blocks_per_path = int(np.ceil(n / TRADE_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            for offset in range(TRADE_BLOCK_SIZE):
                sampled.append(float(round_trip_pnls[(start_idx + offset) % n]))
        pnl_path = np.array(sampled[:n], dtype=float)
        equity_path = OFFICIAL_STAGE78_CAPITAL + np.cumsum(pnl_path)
        rows.append(
            {
                "profile": profile,
                "simulation": simulation,
                "method": "trade_block_bootstrap",
                **_calculate_path_metrics(equity_path, OFFICIAL_STAGE78_CAPITAL),
            }
        )
    return pd.DataFrame(rows)


def _simulate_daily_block_bootstrap(daily_returns: np.ndarray, rng: np.random.Generator, profile: str) -> pd.DataFrame:
    n = len(daily_returns)
    if n == 0:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    blocks_per_path = int(np.ceil(n / DAILY_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            for offset in range(DAILY_BLOCK_SIZE):
                sampled.append(float(daily_returns[(start_idx + offset) % n]))
        return_path = np.array(sampled[:n], dtype=float)
        equity_path = OFFICIAL_STAGE78_CAPITAL * np.cumprod(1.0 + return_path)
        rows.append(
            {
                "profile": profile,
                "simulation": simulation,
                "method": "daily_block_bootstrap",
                **_calculate_path_metrics(equity_path, OFFICIAL_STAGE78_CAPITAL),
            }
        )
    return pd.DataFrame(rows)


def _build_mc_summary(simulations: pd.DataFrame) -> pd.DataFrame:
    if simulations.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (profile, method), group in simulations.groupby(["profile", "method"], sort=True):
        end_balance = pd.to_numeric(group["end_balance"], errors="coerce")
        max_dd = pd.to_numeric(group["max_dd_percent"], errors="coerce")
        min_balance = pd.to_numeric(group["min_balance"], errors="coerce")
        total_return = pd.to_numeric(group["total_return_pct"], errors="coerce")
        rows.append(
            {
                "profile": profile,
                "method": method,
                "simulations": int(len(group)),
                "initial_capital": OFFICIAL_STAGE78_CAPITAL,
                "loss_probability_pct": float((end_balance < OFFICIAL_STAGE78_CAPITAL).mean() * 100.0),
                "ruin_probability_pct": float((min_balance <= 0.0).mean() * 100.0),
                "dd_over_20pct_probability_pct": float((max_dd <= -20.0).mean() * 100.0),
                "dd_over_30pct_probability_pct": float((max_dd <= -30.0).mean() * 100.0),
                "dd_over_40pct_probability_pct": float((max_dd <= -40.0).mean() * 100.0),
                "dd_over_50pct_probability_pct": float((max_dd <= -50.0).mean() * 100.0),
                "total_return_pct_q05": float(total_return.quantile(0.05)),
                "min_balance_q05": float(min_balance.quantile(0.05)),
                "max_dd_percent_q05": float(max_dd.quantile(0.05)),
                "total_return_pct_median": float(total_return.median()),
                "max_dd_percent_median": float(max_dd.median()),
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary_df: pd.DataFrame, slippage_df: pd.DataFrame, mc_summary_df: pd.DataFrame, paths: dict[str, str]) -> str:
    lines = [
        "# Stage217 第78 50万基准执行/滑点/蒙特卡洛三件套",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        f"- 基础风险：`{BASE_RISK_RATIO}`",
        f"- 样本：`{START_DT.date()}` 至 `{END_DT.date()}`",
        "- 口径：同日收盘撮合 vs T+1次日开盘代理撮合；滑点压力为 `1x/2x/3x/5x`；蒙特卡洛为 `1000` 次。",
        "",
        "## 执行延迟",
        "",
        summary_df.to_markdown(index=False),
        "",
        "## 滑点压力",
        "",
        slippage_df.to_markdown(index=False),
        "",
        "## 蒙特卡洛摘要",
        "",
        mc_summary_df.to_markdown(index=False),
        "",
        "## 输出文件",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in paths.items())
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = {
        "same_day_close": SameDayCloseBacktestingEngine,
        "t1_next_open": NextOpenDelayedExecutionEngine,
    }
    daily_by_execution: dict[str, pd.DataFrame] = {}
    trades_by_execution: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict[str, Any]] = []
    for execution, engine_class in variants.items():
        print(f"[stage217] run {execution}", flush=True)
        daily_df, trades_df, summary = _run_variant(execution=execution, engine_class=engine_class)
        daily_by_execution[execution] = daily_df
        trades_by_execution[execution] = trades_df
        summary_rows.append(summary)

    summary_df = pd.DataFrame(summary_rows)
    slippage_df = pd.concat(
        [_build_slippage_stress(execution, daily_df) for execution, daily_df in daily_by_execution.items()],
        ignore_index=True,
    )

    overrides = build_official_stage78_overrides()
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    size_map = {symbol: float(size) for symbol, size in metadata["sizes"].items()}
    rng = np.random.default_rng(RNG_SEED)
    mc_frames: list[pd.DataFrame] = []
    for execution, daily_df in daily_by_execution.items():
        trades_df = trades_by_execution[execution]
        if not daily_df.empty:
            daily_returns = pd.to_numeric(daily_df["return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            mc_frames.append(_simulate_daily_block_bootstrap(daily_returns, rng, execution))
        round_trip_pnls = _build_round_trip_pnls(trades_df, size_map)
        mc_frames.append(_simulate_trade_bootstrap(round_trip_pnls, rng, execution))
    mc_simulations_df = pd.concat([frame for frame in mc_frames if not frame.empty], ignore_index=True)
    mc_summary_df = _build_mc_summary(mc_simulations_df)

    paths = {
        "summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv").resolve()),
        "slippage_stress": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv").resolve()),
        "monte_carlo_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_summary_{MODEL_TAG}.csv").resolve()),
        "monte_carlo_simulations": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_simulations_{MODEL_TAG}.csv").resolve()),
        "same_day_daily": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_day_daily_{MODEL_TAG}.csv").resolve()),
        "t1_next_open_daily": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_t1_next_open_daily_{MODEL_TAG}.csv").resolve()),
        "same_day_trades": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_day_trades_{MODEL_TAG}.csv").resolve()),
        "t1_next_open_trades": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_t1_next_open_trades_{MODEL_TAG}.csv").resolve()),
        "report": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "manifest": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }

    summary_df.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    slippage_df.to_csv(paths["slippage_stress"], index=False, encoding="utf-8-sig")
    mc_summary_df.to_csv(paths["monte_carlo_summary"], index=False, encoding="utf-8-sig")
    mc_simulations_df.to_csv(paths["monte_carlo_simulations"], index=False, encoding="utf-8-sig")
    daily_by_execution["same_day_close"].to_csv(paths["same_day_daily"], index=False, encoding="utf-8-sig")
    daily_by_execution["t1_next_open"].to_csv(paths["t1_next_open_daily"], index=False, encoding="utf-8-sig")
    trades_by_execution["same_day_close"].to_csv(paths["same_day_trades"], index=False, encoding="utf-8-sig")
    trades_by_execution["t1_next_open"].to_csv(paths["t1_next_open_trades"], index=False, encoding="utf-8-sig")
    report = _write_report(summary_df, slippage_df, mc_summary_df, paths)
    Path(paths["report"]).write_text(report, encoding="utf-8")
    Path(paths["manifest"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "official_version": OFFICIAL_STAGE78_VERSION,
                "official_role": OFFICIAL_STAGE78_ROLE,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "base_risk_ratio": BASE_RISK_RATIO,
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report, flush=True)


if __name__ == "__main__":
    main()
