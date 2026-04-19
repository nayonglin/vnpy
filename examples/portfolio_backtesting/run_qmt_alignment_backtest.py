from __future__ import annotations

import json
from pathlib import Path
import re
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
MONTH_LABELS: list[str] = [f"{month}月" for month in range(1, 13)]


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


def _normalize_daily_df(daily_df: pd.DataFrame) -> pd.DataFrame:
    normalized: pd.DataFrame = daily_df.copy()
    normalized.index = pd.to_datetime(normalized.index)
    normalized.sort_index(inplace=True)
    return normalized


def _infer_product_symbol(vt_symbol: str) -> str:
    symbol, exchange = vt_symbol.split(".", 1)
    product: str = re.sub(r"\d+$", "", symbol)
    return f"{product}.{exchange}"


def _load_contract_product_map(mapping_csv_path: Path | None) -> dict[str, str]:
    if mapping_csv_path is None or not mapping_csv_path.exists():
        return {}

    mapping_df: pd.DataFrame = pd.read_csv(mapping_csv_path, usecols=["continuous_symbol_vt", "main_contract_vt"])
    mapping_df["main_contract_vt"] = mapping_df["main_contract_vt"].fillna("")
    mapping_df = mapping_df[mapping_df["main_contract_vt"] != ""].drop_duplicates(subset=["main_contract_vt"])
    return dict(zip(mapping_df["main_contract_vt"], mapping_df["continuous_symbol_vt"], strict=False))


def _build_product_pnl_curve_df(
    positions_df: pd.DataFrame,
    mapping_csv_path: Path | None = None,
) -> pd.DataFrame:
    if positions_df.empty:
        return pd.DataFrame()

    contract_product_map: dict[str, str] = _load_contract_product_map(mapping_csv_path)

    enriched_df: pd.DataFrame = positions_df.copy()
    enriched_df["date"] = pd.to_datetime(enriched_df["date"])
    enriched_df["product_symbol"] = enriched_df["vt_symbol"].map(contract_product_map)
    enriched_df["product_symbol"] = enriched_df["product_symbol"].fillna(
        enriched_df["vt_symbol"].map(_infer_product_symbol)
    )

    grouped_df: pd.DataFrame = (
        enriched_df.groupby(["date", "product_symbol"], as_index=False)["net_pnl"].sum()
    )
    product_curve_df: pd.DataFrame = grouped_df.pivot(
        index="date",
        columns="product_symbol",
        values="net_pnl",
    ).fillna(0.0)
    product_curve_df = product_curve_df.cumsum()

    ordered_columns: list[str] = product_curve_df.iloc[-1].abs().sort_values(ascending=False).index.tolist()
    return product_curve_df[ordered_columns]


def _build_monthly_return_matrix(daily_df: pd.DataFrame, capital: float) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()

    month_end_balance: pd.Series = daily_df["balance"].resample("ME").last()
    if month_end_balance.empty:
        return pd.DataFrame()

    monthly_returns: pd.Series = month_end_balance.pct_change()
    monthly_returns.iloc[0] = month_end_balance.iloc[0] / capital - 1 if capital else 0.0

    monthly_df: pd.DataFrame = monthly_returns.to_frame(name="monthly_return")
    monthly_df["year"] = monthly_df.index.year.astype(str)
    monthly_df["month"] = monthly_df.index.month

    matrix: pd.DataFrame = monthly_df.pivot(index="year", columns="month", values="monthly_return")
    return matrix.reindex(columns=range(1, 13))


def _build_roll_event_df(mapping_csv_path: Path | None = None) -> pd.DataFrame:
    if mapping_csv_path is None or not mapping_csv_path.exists():
        return pd.DataFrame()

    mapping_df: pd.DataFrame = pd.read_csv(
        mapping_csv_path,
        usecols=["date", "continuous_symbol_vt", "main_contract_vt"],
    )
    mapping_df["date"] = pd.to_datetime(mapping_df["date"])
    mapping_df["main_contract_vt"] = mapping_df["main_contract_vt"].fillna("")
    mapping_df.sort_values(["continuous_symbol_vt", "date"], inplace=True)

    mapping_df["prev_contract_vt"] = mapping_df.groupby("continuous_symbol_vt")["main_contract_vt"].shift(1).fillna("")
    roll_df: pd.DataFrame = mapping_df[
        (mapping_df["main_contract_vt"] != "")
        & (mapping_df["prev_contract_vt"] != "")
        & (mapping_df["main_contract_vt"] != mapping_df["prev_contract_vt"])
    ].copy()

    if roll_df.empty:
        return roll_df

    roll_df["roll_label"] = (
        roll_df["continuous_symbol_vt"]
        + "<br>"
        + roll_df["prev_contract_vt"]
        + " -> "
        + roll_df["main_contract_vt"]
    )
    return roll_df


def _build_roll_daily_marker_df(daily_df: pd.DataFrame, roll_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty or roll_df.empty:
        return pd.DataFrame()

    marker_df: pd.DataFrame = (
        roll_df.groupby("date", as_index=False)
        .agg(
            roll_count=("continuous_symbol_vt", "count"),
            roll_details=("roll_label", "<br>".join),
        )
    )

    balance_df: pd.DataFrame = daily_df[["balance"]].reset_index().rename(columns={"index": "date"})
    marker_df = marker_df.merge(balance_df, on="date", how="left")
    return marker_df.dropna(subset=["balance"])


def _create_classic_backtest_chart(daily_df: pd.DataFrame, chart_title: str) -> go.Figure:
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
    fig.update_layout(height=1000, width=1200, title=chart_title)
    return fig


def _create_professional_dashboard(
    daily_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    statistics: dict,
    dashboard_title: str,
    mapping_csv_path: Path | None = None,
) -> go.Figure:
    product_curve_df: pd.DataFrame = _build_product_pnl_curve_df(positions_df, mapping_csv_path)
    monthly_matrix: pd.DataFrame = _build_monthly_return_matrix(daily_df, float(statistics.get("capital", 0) or 0))
    roll_df: pd.DataFrame = _build_roll_event_df(mapping_csv_path)
    roll_marker_df: pd.DataFrame = _build_roll_daily_marker_df(daily_df, roll_df)

    fig = make_subplots(
        rows=5,
        cols=1,
        specs=[
            [{"type": "scatter"}],
            [{"type": "scatter"}],
            [{"type": "scatter"}],
            [{"type": "heatmap"}],
            [{"type": "scatter"}],
        ],
        subplot_titles=[
            "组合权益曲线",
            "组合回撤",
            "品种分组累计净盈亏",
            "月度收益热力图",
            "换月事件时间轴",
        ],
        row_heights=[0.22, 0.16, 0.24, 0.18, 0.20],
        vertical_spacing=0.05,
    )

    fig.add_trace(
        go.Scatter(
            x=daily_df.index,
            y=daily_df["balance"],
            mode="lines",
            name="组合权益",
            line={"color": "#2F5BEA", "width": 2},
        ),
        row=1,
        col=1,
    )

    if not roll_marker_df.empty:
        fig.add_trace(
            go.Scatter(
                x=roll_marker_df["date"],
                y=roll_marker_df["balance"],
                mode="markers",
                name="换月标记",
                marker={
                    "size": (roll_marker_df["roll_count"].clip(upper=6) * 2 + 6).tolist(),
                    "color": "#FF8C00",
                    "symbol": "diamond",
                    "line": {"width": 1, "color": "#C76A00"},
                },
                customdata=roll_marker_df[["roll_count", "roll_details"]].to_numpy(),
                hovertemplate=(
                    "日期: %{x|%Y-%m-%d}<br>"
                    "当日换月数: %{customdata[0]}<br>"
                    "%{customdata[1]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=daily_df.index,
            y=daily_df["drawdown"],
            fill="tozeroy",
            mode="lines",
            name="回撤",
            line={"color": "#D83A3A"},
            fillcolor="rgba(216,58,58,0.25)",
        ),
        row=2,
        col=1,
    )

    if not product_curve_df.empty:
        for product_symbol in product_curve_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=product_curve_df.index,
                    y=product_curve_df[product_symbol],
                    mode="lines",
                    name=product_symbol,
                    hovertemplate=(
                        "日期: %{x|%Y-%m-%d}<br>"
                        f"品种: {product_symbol}<br>"
                        "累计净盈亏: %{y:,.0f}<extra></extra>"
                    ),
                ),
                row=3,
                col=1,
            )

    if not monthly_matrix.empty:
        heatmap_text: pd.DataFrame = monthly_matrix.apply(
            lambda column: column.map(lambda value: "" if pd.isna(value) else f"{value:.1%}")
        )
        fig.add_trace(
            go.Heatmap(
                z=(monthly_matrix * 100).values,
                x=MONTH_LABELS,
                y=monthly_matrix.index.tolist(),
                text=heatmap_text.values,
                texttemplate="%{text}",
                colorscale="RdYlGn",
                colorbar={"title": "月收益(%)"},
                hovertemplate="年份: %{y}<br>月份: %{x}<br>月收益: %{z:.2f}%<extra></extra>",
            ),
            row=4,
            col=1,
        )

    if not roll_df.empty:
        fig.add_trace(
            go.Scatter(
                x=roll_df["date"],
                y=roll_df["continuous_symbol_vt"],
                mode="markers",
                name="换月事件",
                marker={"size": 9, "color": "#5B8FF9"},
                customdata=roll_df[["prev_contract_vt", "main_contract_vt"]].to_numpy(),
                hovertemplate=(
                    "日期: %{x|%Y-%m-%d}<br>"
                    "品种: %{y}<br>"
                    "旧主力: %{customdata[0]}<br>"
                    "新主力: %{customdata[1]}<extra></extra>"
                ),
            ),
            row=5,
            col=1,
        )

    fig.update_layout(
        title=dashboard_title,
        height=1800,
        width=1400,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(title_text="权益", row=1, col=1)
    fig.update_yaxes(title_text="回撤", row=2, col=1)
    fig.update_yaxes(title_text="累计净盈亏", row=3, col=1)
    fig.update_yaxes(title_text="品种", row=5, col=1)
    return fig


def save_backtest_artifacts(
    engine: BacktestingEngine,
    statistics: dict,
    *,
    file_prefix: str = "qmt_alignment",
    chart_title: str = "QMT Alignment Portfolio Backtest",
    mapping_csv_path: Path | None = None,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    positions_df: pd.DataFrame = build_positions_df(engine)
    trades_df: pd.DataFrame = build_trades_df(engine)

    daily_df = engine.daily_df
    if daily_df is not None:
        daily_df = _normalize_daily_df(daily_df)

        daily_path: Path = OUTPUT_DIR / f"{file_prefix}_daily.csv"
        daily_df.to_csv(daily_path, encoding="utf-8-sig")
        print(f"daily csv: {daily_path}")

        daily_equity_path: Path = OUTPUT_DIR / f"{file_prefix}_daily_equity.csv"
        daily_df.reset_index().to_csv(daily_equity_path, index=False, encoding="utf-8-sig")
        print(f"daily equity csv: {daily_equity_path}")

        classic_fig: go.Figure = _create_classic_backtest_chart(daily_df, chart_title)
        html_path: Path = OUTPUT_DIR / f"{file_prefix}_chart.html"
        classic_fig.write_html(str(html_path), include_plotlyjs="cdn", auto_open=OPEN_BROWSER_CHART)
        print(f"chart html: {html_path}")

        professional_fig: go.Figure = _create_professional_dashboard(
            daily_df=daily_df,
            positions_df=positions_df,
            statistics=statistics,
            dashboard_title=f"{chart_title} - Professional Dashboard",
            mapping_csv_path=mapping_csv_path,
        )
        dashboard_path: Path = OUTPUT_DIR / f"{file_prefix}_professional_dashboard.html"
        professional_fig.write_html(str(dashboard_path), include_plotlyjs="cdn", auto_open=False)
        print(f"professional dashboard html: {dashboard_path}")

    if not trades_df.empty:
        trades_path: Path = OUTPUT_DIR / f"{file_prefix}_trades_2020_2026_04.csv"
        trades_df.to_csv(trades_path, index=False, encoding="utf-8-sig")
        print(f"trades csv: {trades_path}")

    if not positions_df.empty:
        positions_path: Path = OUTPUT_DIR / f"{file_prefix}_position_changes_2020_2026_04.csv"
        positions_df.to_csv(positions_path, index=False, encoding="utf-8-sig")
        print(f"position changes csv: {positions_path}")

        pivot_df: pd.DataFrame = positions_df.pivot(index="date", columns="vt_symbol", values="end_pos").fillna(0)
        pivot_path: Path = OUTPUT_DIR / f"{file_prefix}_end_positions_wide_2020_2026_04.csv"
        pivot_df.to_csv(pivot_path, encoding="utf-8-sig")
        print(f"end positions wide csv: {pivot_path}")

    stats_path: Path = OUTPUT_DIR / f"{file_prefix}_statistics.json"
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
