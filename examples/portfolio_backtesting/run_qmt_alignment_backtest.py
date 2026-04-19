from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from vnpy.trader.constant import Direction, Interval
from vnpy_portfoliostrategy import BacktestingEngine

from qmt_alignment_portfolio_strategy import QmtAlignmentPortfolioStrategy
from qmt_universe import END_DT, MARGIN_RATIOS, PRICETICKS, RATES, SIZES, SLIPPAGES, START_DT, VT_SYMBOLS

OUTPUT_DIR: Path = Path(__file__).resolve().parent / "backtest_outputs"
OPEN_BROWSER_CHART: bool = False


def _to_builtin(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def build_trades_df(engine: BacktestingEngine) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in engine.get_all_trades():
        signed_volume: float = float(trade.volume) if trade.direction == Direction.LONG else -float(trade.volume)
        rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "order_id": trade.vt_orderid,
                "datetime": trade.datetime,
                "date": trade.datetime.date(),
                "time": trade.datetime.strftime("%H:%M:%S"),
                "vt_symbol": trade.vt_symbol,
                "symbol": trade.symbol,
                "exchange": trade.exchange.value,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": float(trade.volume),
                "signed_volume": signed_volume,
                "gateway_name": trade.gateway_name,
            }
        )

    if not rows:
        return pd.DataFrame()

    df: pd.DataFrame = pd.DataFrame(rows)
    df.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)
    return df


def build_positions_df(engine: BacktestingEngine) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for daily_result in engine.get_all_daily_results():
        result_date = daily_result.date
        for vt_symbol, contract_result in daily_result.contract_results.items():
            close_price: float = float(contract_result.close_price)
            pre_close: float = float(contract_result.pre_close)
            rows.append(
                {
                    "date": result_date,
                    "vt_symbol": vt_symbol,
                    "start_pos": float(contract_result.start_pos),
                    "end_pos": float(contract_result.end_pos),
                    "pos_change": float(contract_result.end_pos) - float(contract_result.start_pos),
                    "close_price": close_price,
                    "pre_close": pre_close,
                    "trade_count": int(contract_result.trade_count),
                    "turnover": float(contract_result.turnover),
                    "commission": float(contract_result.commission),
                    "slippage": float(contract_result.slippage),
                    "holding_pnl": float(contract_result.holding_pnl),
                    "trading_pnl": float(contract_result.trading_pnl),
                    "total_pnl": float(contract_result.total_pnl),
                    "net_pnl": float(contract_result.net_pnl),
                }
            )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.sort_values(["date", "vt_symbol"], inplace=True)
    return df


def save_backtest_artifacts(engine: BacktestingEngine, statistics: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily_df = engine.daily_df
    if daily_df is not None:
        daily_path: Path = OUTPUT_DIR / "qmt_alignment_daily.csv"
        daily_df.to_csv(daily_path, encoding="utf-8-sig")
        print(f"daily csv: {daily_path}")

        daily_equity_path: Path = OUTPUT_DIR / "qmt_alignment_daily_equity.csv"
        daily_df.reset_index().to_csv(daily_equity_path, index=False, encoding="utf-8-sig")
        print(f"daily equity csv: {daily_equity_path}")

        fig = make_subplots(
            rows=4,
            cols=1,
            subplot_titles=["Balance", "Drawdown", "Daily Pnl", "Pnl Distribution"],
            vertical_spacing=0.06,
        )
        fig.add_trace(
            go.Scatter(x=daily_df.index, y=daily_df["balance"], mode="lines", name="Balance"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=daily_df.index,
                y=daily_df["drawdown"],
                fillcolor="red",
                fill="tozeroy",
                mode="lines",
                name="Drawdown",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(go.Bar(x=daily_df.index, y=daily_df["net_pnl"], name="Daily Pnl"), row=3, col=1)
        fig.add_trace(go.Histogram(x=daily_df["net_pnl"], nbinsx=100, name="Days"), row=4, col=1)
        fig.update_layout(height=1000, width=1200, title="QMT Alignment Portfolio Backtest")

        html_path: Path = OUTPUT_DIR / "qmt_alignment_chart.html"
        fig.write_html(str(html_path), include_plotlyjs="cdn", auto_open=OPEN_BROWSER_CHART)
        print(f"chart html: {html_path}")

    trades_df: pd.DataFrame = build_trades_df(engine)
    if not trades_df.empty:
        trades_path: Path = OUTPUT_DIR / "qmt_alignment_trades_2020_2026_04.csv"
        trades_df.to_csv(trades_path, index=False, encoding="utf-8-sig")
        print(f"trades csv: {trades_path}")

    positions_df: pd.DataFrame = build_positions_df(engine)
    if not positions_df.empty:
        positions_path: Path = OUTPUT_DIR / "qmt_alignment_position_changes_2020_2026_04.csv"
        positions_df.to_csv(positions_path, index=False, encoding="utf-8-sig")
        print(f"position changes csv: {positions_path}")

        pivot_df: pd.DataFrame = positions_df.pivot(index="date", columns="vt_symbol", values="end_pos").fillna(0)
        pivot_path: Path = OUTPUT_DIR / "qmt_alignment_end_positions_wide_2020_2026_04.csv"
        pivot_df.to_csv(pivot_path, encoding="utf-8-sig")
        print(f"end positions wide csv: {pivot_path}")

    stats_path: Path = OUTPUT_DIR / "qmt_alignment_statistics.json"
    serializable_stats: dict[str, object] = {
        key: _to_builtin(value)
        for key, value in statistics.items()
    }
    stats_path.write_text(json.dumps(serializable_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"statistics json: {stats_path}")


def main() -> None:
    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbols=VT_SYMBOLS,
        interval=Interval.DAILY,
        start=START_DT,
        end=END_DT,
        rates=RATES,
        slippages=SLIPPAGES,
        sizes=SIZES,
        priceticks=PRICETICKS,
        capital=1_000_000,
    )

    setting: dict[str, object] = {
        "ma_short": 5,
        "ma_mid": 10,
        "ma_long": 20,
        "ma_extra_long": 40,
        "rsi_length": 6,
        "enable_rsi_filter": False,
        "capital_base": 1_000_000,
        "fixed_size": 0,
        "min_position_size": 1,
        "max_position_size": 500,
        "max_concurrent_positions": 4,
        "long_entry_enabled": True,
        "short_entry_enabled": False,
        "max_capital_usage_ratio": 0.9,
        "risk_ratio_of_total_assets": 0.01,
        "risk_ratio_breakout": 0.01,
        "risk_ratio_ma_cross_breakout": 0.01,
        "min_risk_per_trade": 1000.0,
        "max_risk_per_trade": 50_000_000.0,
        "margin_ratio_overrides": ",".join(f"{symbol}={ratio}" for symbol, ratio in MARGIN_RATIOS.items()),
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
        "stop_loss_pct": 0.02,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 0.0,
        "add_position_min_profit": 0.001,
        "atr_2x_mid_stop_enabled": True,
        "exit_on_alignment_break": True,
        "enable_ma_trend_stop": True,
        "enable_add_position": True,
        "add_position_threshold": 0.01,
        "second_add_position_threshold": 0.01,
        "max_add_layers": 1,
        "regular_add_volume_multiplier": 0.5,
        "regular_add_use_day_extreme_stop": True,
        "restrict_regular_add_to_first": True,
        "require_reversal_for_add": True,
        "wick_chop_filter_enabled": False,
        "wick_chop_filter_lookback": 10,
        "wick_chop_filter_max_days": 4,
        "enable_donchian_add_position": True,
        "donchian_entry_period": 20,
        "donchian_add_period": 20,
        "donchian_add_max_layers": 2,
        "donchian_add_volume_multipliers": "2.0,1.0",
        "case2_requires_breakout": True,
        "tick_add": 1,
        "warmup_days": 90,
    }
    engine.add_strategy(QmtAlignmentPortfolioStrategy, setting)

    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()

    statistics: dict = engine.calculate_statistics()
    print(statistics)
    save_backtest_artifacts(engine, statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
