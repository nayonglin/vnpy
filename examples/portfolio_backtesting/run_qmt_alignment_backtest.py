from __future__ import annotations

from datetime import timedelta
import html
import json
from pathlib import Path
import re
from typing import Any
from datetime import datetime

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from contract_metadata import build_resolved_metadata
from vnpy.trader.constant import Direction, Exchange, Interval
from vnpy.trader.database import get_database
from vnpy_portfoliostrategy import BacktestingEngine

from qmt_alignment_portfolio_strategy import QmtAlignmentPortfolioStrategy
from qmt_universe import END_DT, MARGIN_RATIOS, PRICETICKS, RATES, SIZES, SLIPPAGES, START_DT, VT_SYMBOLS

OUTPUT_DIR: Path = Path(__file__).resolve().parent / "backtest_outputs"
OPEN_BROWSER_CHART: bool = False
MONTH_LABELS: list[str] = [f"{month}月" for month in range(1, 13)]
TRADE_REVIEW_LOOKBACK_BARS: int = 30
TRADE_REVIEW_LOOKAHEAD_BARS: int = 30


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


def build_entry_risk_diagnostics_df(engine: BacktestingEngine) -> pd.DataFrame:
    strategy = getattr(engine, "strategy", None)
    rows: list[dict[str, Any]] = getattr(strategy, "entry_risk_diagnostics", []) if strategy else []
    if not rows:
        return pd.DataFrame()

    df: pd.DataFrame = pd.DataFrame(rows)
    sort_columns: list[str] = [column for column in ["entry_index", "datetime", "contract_vt_symbol"] if column in df.columns]
    if sort_columns:
        df.sort_values(sort_columns, inplace=True)
    return df


def _normalize_daily_df(daily_df: pd.DataFrame) -> pd.DataFrame:
    normalized: pd.DataFrame = daily_df.copy()
    normalized.index = pd.to_datetime(normalized.index)
    normalized.sort_index(inplace=True)
    return normalized


def _ensure_chart_columns(daily_df: pd.DataFrame, capital: float) -> pd.DataFrame:
    normalized: pd.DataFrame = daily_df.copy()

    if "balance" not in normalized.columns:
        net_pnl = pd.to_numeric(normalized.get("net_pnl", pd.Series(0.0, index=normalized.index)), errors="coerce").fillna(0.0)
        normalized["balance"] = float(capital) + net_pnl.cumsum()

    if "drawdown" not in normalized.columns:
        highlevel = normalized["balance"].cummax()
        normalized["highlevel"] = highlevel
        normalized["drawdown"] = normalized["balance"] - highlevel

    if "ddpercent" not in normalized.columns:
        highlevel = normalized.get("highlevel")
        if highlevel is None:
            highlevel = normalized["balance"].cummax()
            normalized["highlevel"] = highlevel
        safe_highlevel = highlevel.replace(0, pd.NA)
        normalized["ddpercent"] = (normalized["drawdown"] / safe_highlevel * 100).fillna(0.0)

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


def _build_daily_position_hover_df(positions_df: pd.DataFrame) -> pd.DataFrame:
    if positions_df.empty:
        return pd.DataFrame(columns=["date", "position_count", "position_details"])

    enriched_df: pd.DataFrame = positions_df.copy()
    enriched_df["date"] = pd.to_datetime(enriched_df["date"])
    enriched_df["end_pos"] = pd.to_numeric(enriched_df["end_pos"], errors="coerce").fillna(0.0)
    enriched_df = enriched_df[enriched_df["end_pos"] != 0].copy()

    if enriched_df.empty:
        return pd.DataFrame(columns=["date", "position_count", "position_details"])

    enriched_df["abs_end_pos"] = enriched_df["end_pos"].abs()

    enriched_df.sort_values(["date", "abs_end_pos", "vt_symbol"], ascending=[True, False, True], inplace=True)
    detail_df: pd.DataFrame = (
        enriched_df.assign(position_line=enriched_df.apply(lambda row: f"{row['vt_symbol']}: {row['end_pos']:,.0f}手", axis=1))
        .groupby("date", as_index=False)
        .agg(
            position_count=("vt_symbol", "size"),
            position_details=("position_line", "<br>".join),
        )
    )
    return detail_df


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
    position_hover_df: pd.DataFrame = _build_daily_position_hover_df(positions_df)
    monthly_matrix: pd.DataFrame = _build_monthly_return_matrix(daily_df, float(statistics.get("capital", 0) or 0))
    roll_df: pd.DataFrame = _build_roll_event_df(mapping_csv_path)
    roll_marker_df: pd.DataFrame = _build_roll_daily_marker_df(daily_df, roll_df)

    equity_df: pd.DataFrame = daily_df.reset_index().rename(columns={"index": "date"}).copy()
    equity_df["date"] = pd.to_datetime(equity_df["date"])
    equity_df["equity_text"] = equity_df["balance"].map(lambda value: f"{float(value) / 1_000_000:.6g}M")
    equity_df = equity_df.merge(position_hover_df, on="date", how="left")
    equity_df["position_count"] = equity_df["position_count"].fillna(0).astype(int)
    equity_df["position_details"] = equity_df["position_details"].fillna("无持仓")

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
            x=equity_df["date"],
            y=equity_df["balance"],
            mode="lines",
            name="组合权益",
            line={"color": "#2F5BEA", "width": 2},
            customdata=equity_df[["equity_text", "position_count", "position_details"]].to_numpy(),
            hovertemplate=(
                "日期: %{x|%Y-%m-%d}<br>"
                "组合权益: %{customdata[0]}<br>"
                "当日持仓数: %{customdata[1]}<br>"
                "持仓明细:<br>%{customdata[2]}<extra></extra>"
            ),
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


def _normalize_trade_review_input(df: pd.DataFrame, datetime_col: str) -> pd.DataFrame:
    normalized = df.copy()
    normalized[datetime_col] = pd.to_datetime(normalized[datetime_col]).dt.tz_localize(None)
    normalized["date"] = normalized[datetime_col].dt.normalize()
    return normalized


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def _load_trade_review_bars(trades_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if trades_df.empty:
        return {}

    database = get_database()
    bars_by_contract: dict[str, pd.DataFrame] = {}

    for vt_symbol, group_df in trades_df.groupby("vt_symbol"):
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        start_dt = group_df["datetime"].min().to_pydatetime() - timedelta(days=120)
        end_dt = group_df["datetime"].max().to_pydatetime() + timedelta(days=120)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)

        rows: list[dict[str, Any]] = []
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(bar.volume),
                }
            )

        if rows:
            contract_df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
            bars_by_contract[vt_symbol] = contract_df

    return bars_by_contract


def _match_entry_risk_to_trades(trades_df: pd.DataFrame, entry_risk_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if trades_df.empty or entry_risk_df.empty:
        return {}

    open_trades = trades_df[trades_df["offset"] == "Open"].copy()
    open_trades["direction_key"] = open_trades["direction"].str.lower()
    open_trades["volume_key"] = open_trades["volume"].round(8)
    open_trades.sort_values(["vt_symbol", "direction_key", "datetime", "trade_id"], inplace=True)

    risk_df = entry_risk_df.copy()
    risk_df["direction_key"] = risk_df["direction"].astype(str).str.lower()
    risk_df["volume_key"] = risk_df["volume"].astype(float).round(8)
    risk_df.sort_values(["contract_vt_symbol", "direction_key", "datetime", "entry_index"], inplace=True)

    matched: dict[str, dict[str, Any]] = {}

    grouped_risks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for risk_row in risk_df.to_dict("records"):
        key = (str(risk_row["contract_vt_symbol"]), str(risk_row["direction_key"]))
        grouped_risks.setdefault(key, []).append(risk_row)

    for trade_row in open_trades.to_dict("records"):
        key = (str(trade_row["vt_symbol"]), str(trade_row["direction_key"]))
        candidates = grouped_risks.get(key, [])

        selected_index: int | None = None
        for index, risk_row in enumerate(candidates):
            if float(risk_row["volume_key"]) != float(trade_row["volume_key"]):
                continue
            risk_dt = pd.Timestamp(risk_row["datetime"])
            trade_dt = pd.Timestamp(trade_row["datetime"])
            if risk_dt <= trade_dt <= risk_dt + pd.Timedelta(days=5):
                selected_index = index
                break

        if selected_index is None:
            continue

        matched[str(trade_row["trade_id"])] = candidates.pop(selected_index)

    return matched


def _marker_style(direction: str, offset: str, is_selected: bool = False) -> tuple[str, str]:
    if offset == "Open" and direction == "Long":
        return ("triangle-up", "#16A34A" if not is_selected else "#0F8A34")
    if offset == "Open" and direction == "Short":
        return ("triangle-down", "#DC2626" if not is_selected else "#B91C1C")
    if offset == "Close" and direction == "Short":
        return ("x", "#EF4444" if not is_selected else "#B91C1C")
    return ("x", "#2563EB" if not is_selected else "#1D4ED8")


def _build_trade_review_records(
    trades_df: pd.DataFrame,
    entry_risk_df: pd.DataFrame,
    mapping_csv_path: Path | None = None,
) -> list[dict[str, Any]]:
    if trades_df.empty:
        return []

    normalized_trades = _normalize_trade_review_input(trades_df, "datetime")
    normalized_risks = _normalize_trade_review_input(entry_risk_df, "datetime") if not entry_risk_df.empty else entry_risk_df
    bars_by_contract = _load_trade_review_bars(normalized_trades)
    risk_by_trade_id = _match_entry_risk_to_trades(normalized_trades, normalized_risks) if not entry_risk_df.empty else {}
    roll_df = _build_roll_event_df(mapping_csv_path)
    if not roll_df.empty:
        roll_df = roll_df.copy()
        roll_df["date"] = pd.to_datetime(roll_df["date"]).dt.normalize()

    contract_product_map = _load_contract_product_map(mapping_csv_path)
    records: list[dict[str, Any]] = []

    for display_index, trade_row in enumerate(normalized_trades.to_dict("records"), start=1):
        vt_symbol = str(trade_row["vt_symbol"])
        bars_df = bars_by_contract.get(vt_symbol)
        if bars_df is None or bars_df.empty:
            continue

        trade_date = pd.Timestamp(trade_row["date"])
        matching = bars_df.index[bars_df["date"] == trade_date].tolist()
        if matching:
            center_index = matching[0]
        else:
            center_index = int(bars_df["date"].searchsorted(trade_date, side="left"))
            center_index = min(max(center_index - 1, 0), len(bars_df) - 1)

        left = max(0, center_index - TRADE_REVIEW_LOOKBACK_BARS)
        right = min(len(bars_df), center_index + TRADE_REVIEW_LOOKAHEAD_BARS + 1)
        window_df = bars_df.iloc[left:right].copy()
        window_start = pd.Timestamp(window_df["date"].iloc[0])
        window_end = pd.Timestamp(window_df["date"].iloc[-1])

        window_trades = normalized_trades[
            (normalized_trades["vt_symbol"] == vt_symbol)
            & (normalized_trades["date"] >= window_start)
            & (normalized_trades["date"] <= window_end)
        ].copy()

        trade_markers: list[dict[str, Any]] = []
        for window_trade in window_trades.to_dict("records"):
            is_selected = str(window_trade["trade_id"]) == str(trade_row["trade_id"])
            symbol, color = _marker_style(str(window_trade["direction"]), str(window_trade["offset"]), is_selected)
            trade_markers.append(
                {
                    "x": pd.Timestamp(window_trade["date"]).strftime("%Y-%m-%d"),
                    "y": float(window_trade["price"]),
                    "text": (
                        f"{window_trade['trade_id']}<br>"
                        f"{window_trade['direction']} {window_trade['offset']}<br>"
                        f"价格: {float(window_trade['price']):,.2f}<br>"
                        f"手数: {float(window_trade['volume']):,.0f}"
                    ),
                    "symbol": symbol,
                    "color": color,
                    "size": 14 if is_selected else 10,
                    "selected": is_selected,
                }
            )

        roll_markers: list[dict[str, Any]] = []
        if not roll_df.empty:
            contract_roll_df = roll_df[
                (
                    (roll_df["prev_contract_vt"] == vt_symbol)
                    | (roll_df["main_contract_vt"] == vt_symbol)
                )
                & (roll_df["date"] >= window_start)
                & (roll_df["date"] <= window_end)
            ].copy()

            close_map = dict(zip(window_df["date"], window_df["close"], strict=False))
            for roll_row in contract_roll_df.to_dict("records"):
                y_value = close_map.get(roll_row["date"], float(window_df["close"].iloc[-1]))
                roll_markers.append(
                    {
                        "x": pd.Timestamp(roll_row["date"]).strftime("%Y-%m-%d"),
                        "y": float(y_value),
                        "text": str(roll_row["roll_label"]),
                    }
                )

        risk_row = risk_by_trade_id.get(str(trade_row["trade_id"]))
        risk_summary: dict[str, Any] | None = None
        stop_line: list[float] | None = None
        if risk_row:
            risk_summary = {
                "layer_kind": risk_row.get("layer_kind"),
                "risk_mode": risk_row.get("risk_mode"),
                "sizing_method": risk_row.get("sizing_method"),
                "estimated_equity": risk_row.get("estimated_equity"),
                "total_margin_in_use_before": risk_row.get("total_margin_in_use_before"),
                "limited_balance": risk_row.get("limited_balance"),
                "target_risk_amount": risk_row.get("target_risk_amount"),
                "actual_risk_amount": risk_row.get("actual_risk_amount"),
                "entry_price": risk_row.get("entry_price"),
                "stop_price": risk_row.get("stop_price"),
                "stop_distance": risk_row.get("stop_distance"),
                "risk_per_contract": risk_row.get("risk_per_contract"),
                "actual_margin_amount": risk_row.get("actual_margin_amount"),
                "contracts_by_risk": risk_row.get("contracts_by_risk"),
                "contracts_by_margin": risk_row.get("contracts_by_margin"),
                "selected_volume": risk_row.get("selected_volume"),
                "loss_streak": risk_row.get("loss_streak"),
            }
            if risk_row.get("stop_price") is not None:
                stop_line = [float(risk_row["stop_price"])] * len(window_df)

        product_symbol = contract_product_map.get(vt_symbol, _infer_product_symbol(vt_symbol))
        trade_date_text = pd.Timestamp(trade_row["datetime"]).strftime("%Y-%m-%d %H:%M:%S")
        label = (
            f"{display_index}. {trade_date_text} | {vt_symbol} | "
            f"{trade_row['direction']} {trade_row['offset']} | "
            f"@{float(trade_row['price']):,.2f} x {float(trade_row['volume']):,.0f}"
        )

        records.append(
            {
                "record_index": display_index,
                "label": label,
                "trade_id": str(trade_row["trade_id"]),
                "datetime": trade_date_text,
                "date": pd.Timestamp(trade_row["date"]).strftime("%Y-%m-%d"),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": product_symbol,
                "direction": str(trade_row["direction"]),
                "offset": str(trade_row["offset"]),
                "price": float(trade_row["price"]),
                "volume": float(trade_row["volume"]),
                "bars": {
                    "date": window_df["date"].dt.strftime("%Y-%m-%d").tolist(),
                    "open": window_df["open"].round(4).tolist(),
                    "high": window_df["high"].round(4).tolist(),
                    "low": window_df["low"].round(4).tolist(),
                    "close": window_df["close"].round(4).tolist(),
                    "volume": window_df["volume"].round(4).tolist(),
                },
                "trade_markers": trade_markers,
                "roll_markers": roll_markers,
                "risk": risk_summary,
                "stop_line": stop_line,
            }
        )

    return records


def _create_trade_review_html(
    trade_review_records: list[dict[str, Any]],
    html_title: str,
) -> str:
    payload: str = json.dumps(trade_review_records, ensure_ascii=False).replace("</", "<\\/")
    page_title = html.escape(html_title)
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f5f7fb; color: #1f2937; }
    .page { max-width: 1500px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0 0 16px; font-size: 28px; }
    .toolbar { display: grid; grid-template-columns: 220px 1fr auto auto; gap: 12px; align-items: center; margin-bottom: 16px; }
    select, input, button { height: 40px; border: 1px solid #d0d7e2; border-radius: 8px; padding: 0 12px; background: #fff; font-size: 14px; }
    button { cursor: pointer; }
    .meta { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .card { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }
    .card h3 { margin: 0 0 8px; font-size: 16px; }
    .kv { display: grid; grid-template-columns: 140px 1fr; row-gap: 6px; column-gap: 8px; font-size: 13px; }
    .kv div:nth-child(odd) { color: #64748b; }
    #trade-chart { background: #fff; border-radius: 12px; padding: 8px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }
    .footer { margin-top: 12px; font-size: 12px; color: #64748b; }
    @media (max-width: 1100px) {
      .toolbar { grid-template-columns: 1fr; }
      .meta { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>__TITLE__</h1>
    <div class="toolbar">
      <select id="contract-filter"></select>
      <select id="trade-select"></select>
      <button id="prev-btn">上一笔</button>
      <button id="next-btn">下一笔</button>
    </div>
    <div class="meta">
      <div class="card"><h3>成交信息</h3><div id="trade-summary" class="kv"></div></div>
      <div class="card"><h3>开仓风险快照</h3><div id="risk-summary" class="kv"></div></div>
      <div class="card"><h3>窗口信息</h3><div id="window-summary" class="kv"></div></div>
      <div class="card"><h3>说明</h3><div class="kv"><div>绿色三角</div><div>开多</div><div>红色三角</div><div>开空</div><div>红色叉号</div><div>平多</div><div>蓝色叉号</div><div>平空</div><div>橙色虚线</div><div>开仓止损线</div><div>紫色菱形</div><div>换月事件</div></div></div>
    </div>
    <div id="trade-chart"></div>
    <div class="footer">复盘页按每笔成交截取前后 30 根日线，叠加同窗口内全部成交点、换月事件和开仓风险快照。</div>
  </div>
  <script>
    const tradeRecords = __PAYLOAD__;
    const contractFilter = document.getElementById("contract-filter");
    const tradeSelect = document.getElementById("trade-select");
    const tradeSummary = document.getElementById("trade-summary");
    const riskSummary = document.getElementById("risk-summary");
    const windowSummary = document.getElementById("window-summary");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    let filteredIndices = [];
    let activePosition = 0;

    function formatNumber(value, digits = 2) {
      if (value === null || value === undefined || value === "") return "-";
      return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
    }

    function kvHtml(items) {
      return items.map(([k, v]) => `<div>${k}</div><div>${v ?? "-"}</div>`).join("");
    }

    function buildContractFilter() {
      const contracts = ["全部合约", ...new Set(tradeRecords.map(r => r.vt_symbol))];
      contractFilter.innerHTML = contracts.map(v => `<option value="${v}">${v}</option>`).join("");
    }

    function refreshTradeOptions() {
      const selectedContract = contractFilter.value;
      filteredIndices = tradeRecords
        .map((record, index) => ({ record, index }))
        .filter(item => selectedContract === "全部合约" || item.record.vt_symbol === selectedContract)
        .map(item => item.index);

      tradeSelect.innerHTML = filteredIndices
        .map((index, position) => `<option value="${position}">${tradeRecords[index].label}</option>`)
        .join("");

      activePosition = 0;
      renderTrade();
    }

    function renderTrade() {
      if (!filteredIndices.length) {
        tradeSummary.innerHTML = "";
        riskSummary.innerHTML = "";
        windowSummary.innerHTML = "";
        Plotly.newPlot("trade-chart", [], { title: "无可用交易" }, { responsive: true, displaylogo: false });
        return;
      }

      const record = tradeRecords[filteredIndices[activePosition]];
      tradeSelect.value = String(activePosition);

      tradeSummary.innerHTML = kvHtml([
        ["序号", `${record.record_index}`],
        ["成交时间", record.datetime],
        ["合约", record.vt_symbol],
        ["品种", record.product_vt_symbol],
        ["方向", `${record.direction} / ${record.offset}`],
        ["成交价", formatNumber(record.price)],
        ["手数", formatNumber(record.volume, 0)],
        ["成交编号", record.trade_id],
      ]);

      if (record.risk) {
        riskSummary.innerHTML = kvHtml([
          ["层级", record.risk.layer_kind],
          ["模式", `${record.risk.risk_mode} / ${record.risk.sizing_method}`],
          ["目标风险", formatNumber(record.risk.target_risk_amount)],
          ["实际风险", formatNumber(record.risk.actual_risk_amount)],
          ["保证金占用", formatNumber(record.risk.actual_margin_amount)],
          ["止损价", formatNumber(record.risk.stop_price)],
          ["单手风险", formatNumber(record.risk.risk_per_contract)],
          ["可用资金", formatNumber(record.risk.limited_balance)],
        ]);
      } else {
        riskSummary.innerHTML = kvHtml([
          ["说明", "该笔不是开仓，或未匹配到开仓风险快照"],
          ["目标风险", "-"],
          ["实际风险", "-"],
          ["保证金占用", "-"],
          ["止损价", "-"],
          ["单手风险", "-"],
          ["可用资金", "-"],
          ["手数限制", "-"],
        ]);
      }

      const barCount = record.bars.date.length;
      windowSummary.innerHTML = kvHtml([
        ["窗口起点", record.bars.date[0]],
        ["窗口终点", record.bars.date[barCount - 1]],
        ["K线数量", `${barCount}`],
        ["窗口内成交点", `${record.trade_markers.length}`],
        ["窗口内换月", `${record.roll_markers.length}`],
        ["当前筛选", `${activePosition + 1} / ${filteredIndices.length}`],
        ["前瞻根数", "30"],
        ["回看根数", "30"],
      ]);

      const traces = [
        {
          type: "candlestick",
          x: record.bars.date,
          open: record.bars.open,
          high: record.bars.high,
          low: record.bars.low,
          close: record.bars.close,
          name: "日线K线",
          increasing: { line: { color: "#ef4444" }, fillcolor: "#ef4444" },
          decreasing: { line: { color: "#16a34a" }, fillcolor: "#16a34a" },
        },
        {
          type: "scatter",
          mode: "markers",
          x: record.trade_markers.map(item => item.x),
          y: record.trade_markers.map(item => item.y),
          text: record.trade_markers.map(item => item.text),
          hovertemplate: "%{text}<extra></extra>",
          marker: {
            symbol: record.trade_markers.map(item => item.symbol),
            color: record.trade_markers.map(item => item.color),
            size: record.trade_markers.map(item => item.size),
            line: { width: 1, color: "#0f172a" },
          },
          name: "成交点",
        },
      ];

      if (record.stop_line) {
        traces.push({
          type: "scatter",
          mode: "lines",
          x: record.bars.date,
          y: record.stop_line,
          name: "开仓止损线",
          line: { color: "#f59e0b", width: 2, dash: "dash" },
          hovertemplate: "止损价: %{y:,.2f}<extra></extra>",
        });
      }

      if (record.roll_markers.length) {
        traces.push({
          type: "scatter",
          mode: "markers",
          x: record.roll_markers.map(item => item.x),
          y: record.roll_markers.map(item => item.y),
          text: record.roll_markers.map(item => item.text),
          hovertemplate: "%{text}<extra></extra>",
          marker: {
            symbol: "diamond",
            size: 11,
            color: "#7c3aed",
            line: { width: 1, color: "#5b21b6" },
          },
          name: "换月事件",
        });
      }

      const layout = {
        title: `${record.vt_symbol} | ${record.direction} ${record.offset} | ${record.datetime}`,
        height: 760,
        margin: { l: 40, r: 30, t: 60, b: 40 },
        xaxis: { rangeslider: { visible: false } },
        yaxis: { title: "价格" },
        hovermode: "x unified",
        legend: { orientation: "h", y: 1.02, x: 0 },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
      };

      Plotly.newPlot("trade-chart", traces, layout, { responsive: true, displaylogo: false });
    }

    contractFilter.addEventListener("change", refreshTradeOptions);
    tradeSelect.addEventListener("change", (event) => {
      activePosition = Number(event.target.value);
      renderTrade();
    });
    prevBtn.addEventListener("click", () => {
      if (!filteredIndices.length) return;
      activePosition = (activePosition - 1 + filteredIndices.length) % filteredIndices.length;
      renderTrade();
    });
    nextBtn.addEventListener("click", () => {
      if (!filteredIndices.length) return;
      activePosition = (activePosition + 1) % filteredIndices.length;
      renderTrade();
    });

    buildContractFilter();
    refreshTradeOptions();
  </script>
</body>
</html>
"""
    return template.replace("__TITLE__", page_title).replace("__PAYLOAD__", payload)


def save_backtest_artifacts(
    engine: BacktestingEngine,
    statistics: dict,
    *,
    file_prefix: str = "qmt_alignment",
    chart_title: str = "QMT Alignment Portfolio Backtest",
    mapping_csv_path: Path | None = None,
    analysis_start: datetime | None = None,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    positions_df: pd.DataFrame = build_positions_df(engine)
    trades_df: pd.DataFrame = build_trades_df(engine)
    entry_risk_df: pd.DataFrame = build_entry_risk_diagnostics_df(engine)

    daily_df = engine.daily_df
    if daily_df is not None:
        daily_df = _normalize_daily_df(daily_df)
        if analysis_start is not None:
            daily_df = daily_df[daily_df.index >= pd.Timestamp(analysis_start)]
        if not daily_df.empty:
            daily_df = _ensure_chart_columns(daily_df, float(statistics.get("capital", 0) or 0))

    if analysis_start is not None and not trades_df.empty:
        trade_dt = pd.to_datetime(trades_df["datetime"]).dt.tz_localize(None)
        trades_df = trades_df.loc[trade_dt >= pd.Timestamp(analysis_start)].copy()

    if analysis_start is not None and not positions_df.empty:
        pos_dt = pd.to_datetime(positions_df["date"])
        positions_df = positions_df.loc[pos_dt >= pd.Timestamp(analysis_start)].copy()

    if analysis_start is not None and not entry_risk_df.empty:
        risk_dt = pd.to_datetime(entry_risk_df["datetime"]).dt.tz_localize(None)
        entry_risk_df = entry_risk_df.loc[risk_dt >= pd.Timestamp(analysis_start)].copy()

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

    if not entry_risk_df.empty:
        entry_risk_path: Path = OUTPUT_DIR / f"{file_prefix}_entry_risk_diagnostics_2020_2026_04.csv"
        entry_risk_df.to_csv(entry_risk_path, index=False, encoding="utf-8-sig")
        print(f"entry risk diagnostics csv: {entry_risk_path}")

    if not trades_df.empty:
        trade_review_records = _build_trade_review_records(trades_df, entry_risk_df, mapping_csv_path)
        if trade_review_records:
            trade_review_html = _create_trade_review_html(
                trade_review_records,
                f"{chart_title} - Trade Review",
            )
            trade_review_path: Path = OUTPUT_DIR / f"{file_prefix}_trade_review.html"
            trade_review_path.write_text(trade_review_html, encoding="utf-8")
            print(f"trade review html: {trade_review_path}")

    stats_path: Path = OUTPUT_DIR / f"{file_prefix}_statistics.json"
    serializable_stats: dict[str, object] = {
        key: _to_builtin(value)
        for key, value in statistics.items()
    }
    stats_path.write_text(json.dumps(serializable_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"statistics json: {stats_path}")


def main() -> None:
    resolved = build_resolved_metadata(
        vt_symbols=VT_SYMBOLS,
        default_sizes=SIZES,
        default_priceticks=PRICETICKS,
        default_margin_ratios=MARGIN_RATIOS,
    )
    resolved_sizes: dict[str, int] = resolved["sizes"]
    resolved_priceticks: dict[str, float] = resolved["priceticks"]
    resolved_margin_ratios: dict[str, float] = resolved["margin_ratios"]

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbols=VT_SYMBOLS,
        interval=Interval.DAILY,
        start=START_DT,
        end=END_DT,
        rates=RATES,
        slippages=SLIPPAGES,
        sizes=resolved_sizes,
        priceticks=resolved_priceticks,
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
        "margin_ratio_overrides": ",".join(f"{symbol}={ratio}" for symbol, ratio in resolved_margin_ratios.items()),
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
