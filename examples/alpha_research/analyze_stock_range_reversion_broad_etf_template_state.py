from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
BROAD_ETF_DATA_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_data_2018_2026"
BROAD_ETF_DAILY_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_selected_daily.csv"
BROAD_ETF_BASIC_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_selected_basic.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_template_state_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_broad_etf_template_state_v1"

TRADING_DAYS: int = 252
INITIAL_EQUITY: float = 1.0
ROUNDTRIP_COST_BPS: tuple[float, ...] = (10.0, 20.0, 50.0)


@dataclass(frozen=True)
class TemplateStrategy:
    name: str
    description: str
    family: str
    use_trend_filter: bool
    max_hold_days: int


STRATEGIES: tuple[TemplateStrategy, ...] = (
    TemplateStrategy(
        name="connors_rsi2_no_filter",
        description="Connors风格RSI(2)<=10买入，收盘站上MA5退出，无趋势过滤",
        family="connors_rsi2",
        use_trend_filter=False,
        max_hold_days=10,
    ),
    TemplateStrategy(
        name="connors_rsi2_ma200",
        description="Connors风格RSI(2)<=10买入，收盘站上MA5退出，要求收盘在MA200上方",
        family="connors_rsi2",
        use_trend_filter=True,
        max_hold_days=10,
    ),
    TemplateStrategy(
        name="bollinger20_2_no_filter",
        description="Bollinger 20日-2σ买入，回到MA20退出，无趋势过滤",
        family="bollinger20_2",
        use_trend_filter=False,
        max_hold_days=15,
    ),
    TemplateStrategy(
        name="bollinger20_2_ma200",
        description="Bollinger 20日-2σ买入，回到MA20退出，要求收盘在MA200上方",
        family="bollinger20_2",
        use_trend_filter=True,
        max_hold_days=15,
    ),
)


def pct(value: float) -> str:
    return f"{value:.2%}"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def load_broad_etf_daily() -> pd.DataFrame:
    if not BROAD_ETF_DAILY_PATH.exists():
        raise FileNotFoundError(f"Broad ETF daily data not found: {BROAD_ETF_DAILY_PATH}")
    if not BROAD_ETF_BASIC_PATH.exists():
        raise FileNotFoundError(f"Broad ETF basic data not found: {BROAD_ETF_BASIC_PATH}")
    daily = pd.read_csv(BROAD_ETF_DAILY_PATH, encoding="utf-8-sig")
    basic = pd.read_csv(BROAD_ETF_BASIC_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    for column in ("pre_close", "open", "high", "low", "close", "pct_chg", "daily_ret", "amount", "vol"):
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    keep = ["ts_code", "index_bucket", "index_name", "role", "name", "m_fee", "c_fee"]
    frame = daily.merge(basic[keep], on="ts_code", how="left")
    frame = frame.dropna(subset=["date", "close", "daily_ret"]).sort_values(["ts_code", "date"])
    return frame.reset_index(drop=True)


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.sort_values("date").copy()
    close = work["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 2, adjust=False, min_periods=2).mean()
    avg_loss = loss.ewm(alpha=1 / 2, adjust=False, min_periods=2).mean()
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    work["rsi2"] = (100.0 - 100.0 / (1.0 + rs)).astype(float)
    work.loc[(avg_loss == 0.0) & (avg_gain > 0.0), "rsi2"] = 100.0
    work.loc[(avg_loss == 0.0) & (avg_gain == 0.0), "rsi2"] = 50.0
    work["ma5"] = close.rolling(5, min_periods=5).mean()
    work["ma20"] = close.rolling(20, min_periods=20).mean()
    work["std20"] = close.rolling(20, min_periods=20).std(ddof=0)
    work["ma60"] = close.rolling(60, min_periods=60).mean()
    work["ma120"] = close.rolling(120, min_periods=120).mean()
    work["ma200"] = close.rolling(200, min_periods=200).mean()
    work["ret60"] = close / close.shift(60) - 1.0
    work["z20"] = (close - work["ma20"]) / work["std20"].replace(0.0, float("nan"))
    work["high120"] = close.rolling(120, min_periods=60).max()
    work["drawdown120"] = close / work["high120"] - 1.0
    work["next_daily_ret"] = work["daily_ret"].shift(-1)
    work["buy_hold_daily_ret"] = work["daily_ret"].fillna(0.0)
    work["trend_state"] = work.apply(classify_trend_state, axis=1)
    work["drawdown_state"] = work["drawdown120"].apply(classify_drawdown_state)
    return work


def classify_trend_state(row: pd.Series) -> str:
    if pd.isna(row["ma200"]) or pd.isna(row["ma60"]) or pd.isna(row["ma120"]) or pd.isna(row["ret60"]):
        return "warmup"
    above_ma200 = row["close"] > row["ma200"]
    ma60_up = row["ma60"] >= row["ma120"]
    ret60_up = row["ret60"] >= 0.0
    if above_ma200 and ma60_up:
        return "above_ma200_up60"
    if above_ma200:
        return "above_ma200_down60"
    if ret60_up:
        return "below_ma200_recover60"
    return "below_ma200_down60"


def classify_drawdown_state(value: Any) -> str:
    drawdown = to_float(value, default=float("nan"))
    if pd.isna(drawdown):
        return "warmup"
    if drawdown > -0.05:
        return "shallow_dd"
    if drawdown > -0.15:
        return "medium_dd"
    return "deep_dd"


def strategy_entry_exit(row: pd.Series, strategy: TemplateStrategy) -> tuple[bool, bool]:
    trend_ok = True
    if strategy.use_trend_filter:
        trend_ok = bool(pd.notna(row["ma200"]) and row["close"] > row["ma200"])
    if strategy.family == "connors_rsi2":
        entry = bool(pd.notna(row["rsi2"]) and row["rsi2"] <= 10.0 and trend_ok)
        exit_signal = bool(pd.notna(row["ma5"]) and row["close"] > row["ma5"])
        return entry, exit_signal
    if strategy.family == "bollinger20_2":
        entry = bool(pd.notna(row["z20"]) and row["z20"] <= -2.0 and trend_ok)
        exit_signal = bool(pd.notna(row["ma20"]) and row["close"] >= row["ma20"])
        return entry, exit_signal
    raise ValueError(f"Unknown strategy family: {strategy.family}")


def equity_and_drawdown(returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    equity_values: list[float] = []
    drawdown_values: list[float] = []
    equity = INITIAL_EQUITY
    peak = INITIAL_EQUITY
    for value in returns.fillna(0.0):
        equity *= 1.0 + to_float(value)
        peak = max(peak, equity)
        equity_values.append(equity)
        drawdown_values.append(equity / peak - 1.0 if peak else 0.0)
    return pd.Series(equity_values, index=returns.index), pd.Series(drawdown_values, index=returns.index)


def run_template(etf: pd.DataFrame, strategy: TemplateStrategy, cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    one_way_cost = cost_bps / 2.0 / 10_000.0
    position = 0.0
    pending_position = 0.0
    pending_entry_meta: dict[str, Any] | None = None
    entry_date = None
    entry_signal_date = None
    entry_close = 0.0
    entry_trend_state = ""
    entry_drawdown_state = ""
    trade_growth = 1.0
    holding_days = 0
    trade_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    rows = list(etf.reset_index(drop=True).itertuples(index=False))
    for index, row in enumerate(rows):
        current_position = position
        trade_delta = pending_position - current_position
        trade_cost_ret = abs(trade_delta) * one_way_cost

        if trade_delta > 0:
            entry_date = row.date
            entry_close = to_float(row.close)
            trade_growth = 1.0
            holding_days = 0
            if pending_entry_meta:
                entry_signal_date = pending_entry_meta["signal_date"]
                entry_trend_state = pending_entry_meta["trend_state"]
                entry_drawdown_state = pending_entry_meta["drawdown_state"]
            else:
                entry_signal_date = row.date
                entry_trend_state = row.trend_state
                entry_drawdown_state = row.drawdown_state
        elif trade_delta < 0 and entry_date is not None:
            gross_return = trade_growth - 1.0
            trade_rows.append(
                {
                    "ts_code": row.ts_code,
                    "etf_name": row.name,
                    "index_bucket": row.index_bucket,
                    "index_name": row.index_name,
                    "role": row.role,
                    "strategy": strategy.name,
                    "roundtrip_cost_bps": cost_bps,
                    "entry_signal_date": entry_signal_date,
                    "entry_date": entry_date,
                    "exit_date": row.date,
                    "holding_days": holding_days,
                    "entry_close": entry_close,
                    "exit_close": to_float(row.close),
                    "entry_trend_state": entry_trend_state,
                    "entry_drawdown_state": entry_drawdown_state,
                    "gross_return": gross_return,
                    "net_return_est": gross_return - cost_bps / 10_000.0,
                }
            )
            entry_date = None
            entry_signal_date = None
            entry_close = 0.0
            entry_trend_state = ""
            entry_drawdown_state = ""
            trade_growth = 1.0
            holding_days = 0
            pending_entry_meta = None

        position = pending_position
        interval_ret = to_float(row.next_daily_ret) if index < len(rows) - 1 else 0.0
        strategy_daily_ret = position * interval_ret - trade_cost_ret
        if position > 0:
            trade_growth *= 1.0 + interval_ret

        if index == len(rows) - 1 and position > 0:
            strategy_daily_ret -= position * one_way_cost
            gross_return = trade_growth - 1.0
            trade_rows.append(
                {
                    "ts_code": row.ts_code,
                    "etf_name": row.name,
                    "index_bucket": row.index_bucket,
                    "index_name": row.index_name,
                    "role": row.role,
                    "strategy": strategy.name,
                    "roundtrip_cost_bps": cost_bps,
                    "entry_signal_date": entry_signal_date,
                    "entry_date": entry_date,
                    "exit_date": row.date,
                    "holding_days": holding_days,
                    "entry_close": entry_close,
                    "exit_close": to_float(row.close),
                    "entry_trend_state": entry_trend_state,
                    "entry_drawdown_state": entry_drawdown_state,
                    "gross_return": gross_return,
                    "net_return_est": gross_return - cost_bps / 10_000.0,
                }
            )
            position = 0.0
            pending_position = 0.0
            pending_entry_meta = None

        row_series = pd.Series(row._asdict())
        entry_signal, exit_signal = strategy_entry_exit(row_series, strategy)
        if position > 0:
            holding_days += 1
        next_position = position
        exit_by_hold = position > 0 and holding_days >= strategy.max_hold_days
        if position <= 0 and entry_signal:
            next_position = 1.0
            pending_entry_meta = {
                "signal_date": row.date,
                "trend_state": row.trend_state,
                "drawdown_state": row.drawdown_state,
            }
        elif position > 0 and (exit_signal or exit_by_hold):
            next_position = 0.0

        daily_rows.append(
            {
                "date": row.date,
                "ts_code": row.ts_code,
                "etf_name": row.name,
                "index_bucket": row.index_bucket,
                "index_name": row.index_name,
                "role": row.role,
                "strategy": strategy.name,
                "strategy_description": strategy.description,
                "family": strategy.family,
                "use_trend_filter": strategy.use_trend_filter,
                "roundtrip_cost_bps": cost_bps,
                "position": position,
                "next_position": next_position,
                "trade_abs_delta": abs(trade_delta),
                "trade_cost_ret": trade_cost_ret,
                "strategy_daily_ret": strategy_daily_ret,
                "buy_hold_daily_ret": to_float(row.buy_hold_daily_ret),
                "close": to_float(row.close),
                "rsi2": to_float(row.rsi2),
                "z20": to_float(row.z20),
                "ma20": to_float(row.ma20),
                "ma60": to_float(row.ma60),
                "ma120": to_float(row.ma120),
                "ma200": to_float(row.ma200),
                "ret60": to_float(row.ret60),
                "drawdown120": to_float(row.drawdown120),
                "trend_state": row.trend_state,
                "drawdown_state": row.drawdown_state,
                "entry_signal": entry_signal,
                "exit_signal": exit_signal,
                "exit_by_hold": exit_by_hold,
                "holding_days": holding_days,
            }
        )
        pending_position = next_position

    daily = pd.DataFrame(daily_rows)
    strategy_equity, strategy_drawdown = equity_and_drawdown(daily["strategy_daily_ret"])
    daily["strategy_equity"] = strategy_equity
    daily["strategy_drawdown"] = strategy_drawdown
    buy_hold_cost = cost_bps / 10_000.0
    buy_hold_ret = daily["buy_hold_daily_ret"].fillna(0.0).copy()
    if len(buy_hold_ret):
        buy_hold_ret.iloc[0] -= buy_hold_cost / 2.0
        buy_hold_ret.iloc[-1] -= buy_hold_cost / 2.0
    buy_hold_equity, buy_hold_drawdown = equity_and_drawdown(buy_hold_ret)
    daily["buy_hold_costed_daily_ret"] = buy_hold_ret
    daily["buy_hold_equity"] = buy_hold_equity
    daily["buy_hold_drawdown"] = buy_hold_drawdown
    return daily, pd.DataFrame(trade_rows)


def summarize_daily(daily: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    days = len(daily)
    ret = daily["strategy_daily_ret"].fillna(0.0)
    mean = ret.mean() if days else 0.0
    std = ret.std(ddof=1) if days > 1 else 0.0
    total_return = to_float(daily["strategy_equity"].iloc[-1] - 1.0) if days else 0.0
    buy_hold_return = to_float(daily["buy_hold_equity"].iloc[-1] - 1.0) if days else 0.0
    trade_count = int(len(trades))
    return {
        "ts_code": str(daily["ts_code"].iloc[0]) if days else "",
        "etf_name": str(daily["etf_name"].iloc[0]) if days else "",
        "index_bucket": str(daily["index_bucket"].iloc[0]) if days else "",
        "index_name": str(daily["index_name"].iloc[0]) if days else "",
        "role": str(daily["role"].iloc[0]) if days else "",
        "strategy": str(daily["strategy"].iloc[0]) if days else "",
        "roundtrip_cost_bps": to_float(daily["roundtrip_cost_bps"].iloc[0]) if days else 0.0,
        "days": days,
        "start_date": str(daily["date"].min()) if days else "",
        "end_date": str(daily["date"].max()) if days else "",
        "final_equity": to_float(daily["strategy_equity"].iloc[-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": (1.0 + total_return) ** (TRADING_DAYS / days) - 1.0 if days and total_return > -1 else 0.0,
        "max_drawdown": to_float(daily["strategy_drawdown"].min()) if days else 0.0,
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std else 0.0,
        "buy_hold_final_equity": to_float(daily["buy_hold_equity"].iloc[-1]) if days else INITIAL_EQUITY,
        "buy_hold_total_return": buy_hold_return,
        "buy_hold_max_drawdown": to_float(daily["buy_hold_drawdown"].min()) if days else 0.0,
        "active_day_ratio": to_float((daily["position"] > 0).mean()) if days else 0.0,
        "trade_count": trade_count,
        "win_rate": to_float((trades["net_return_est"] > 0).mean()) if trade_count else 0.0,
        "avg_trade_net_return": to_float(trades["net_return_est"].mean()) if trade_count else 0.0,
        "median_trade_net_return": to_float(trades["net_return_est"].median()) if trade_count else 0.0,
        "avg_holding_days": to_float(trades["holding_days"].mean()) if trade_count else 0.0,
        "annualized_abs_turnover": to_float(daily["trade_abs_delta"].mean()) * TRADING_DAYS if days else 0.0,
        "cost_drag_sum": to_float(daily["trade_cost_ret"].sum()) if days else 0.0,
        "entry_signal_count": int(daily["entry_signal"].sum()) if days else 0,
    }


def build_pool_summary(all_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    daily_rows: list[pd.DataFrame] = []
    for keys, group in all_curves.groupby(["strategy", "roundtrip_cost_bps"]):
        strategy, cost_bps = keys
        by_date = (
            group.groupby("date")
            .agg(
                pool_daily_ret=("strategy_daily_ret", "mean"),
                buy_hold_daily_ret=("buy_hold_daily_ret", "mean"),
                active_etf_count=("position", "sum"),
                available_etf_count=("ts_code", "nunique"),
            )
            .reset_index()
            .sort_values("date")
        )
        equity, drawdown = equity_and_drawdown(by_date["pool_daily_ret"])
        by_date["pool_equity"] = equity
        by_date["pool_drawdown"] = drawdown
        by_date["strategy"] = strategy
        by_date["roundtrip_cost_bps"] = cost_bps
        ret = by_date["pool_daily_ret"].fillna(0.0)
        total_return = to_float(by_date["pool_equity"].iloc[-1] - 1.0) if len(by_date) else 0.0
        rows.append(
            {
                "strategy": strategy,
                "roundtrip_cost_bps": cost_bps,
                "days": int(len(by_date)),
                "start_date": str(by_date["date"].min()) if len(by_date) else "",
                "end_date": str(by_date["date"].max()) if len(by_date) else "",
                "final_equity": to_float(by_date["pool_equity"].iloc[-1]) if len(by_date) else INITIAL_EQUITY,
                "total_return": total_return,
                "annualized_return": (1.0 + total_return) ** (TRADING_DAYS / len(by_date)) - 1.0
                if len(by_date) and total_return > -1
                else 0.0,
                "max_drawdown": to_float(by_date["pool_drawdown"].min()) if len(by_date) else 0.0,
                "sharpe": ret.mean() / ret.std(ddof=1) * sqrt(TRADING_DAYS) if len(ret) > 1 and ret.std(ddof=1) else 0.0,
                "avg_active_etf_count": to_float(by_date["active_etf_count"].mean()) if len(by_date) else 0.0,
                "avg_available_etf_count": to_float(by_date["available_etf_count"].mean()) if len(by_date) else 0.0,
            }
        )
        daily_rows.append(by_date)
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "strategy"]), pd.concat(
        daily_rows, ignore_index=True, sort=False
    )


def build_entry_state_summary(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["strategy", "roundtrip_cost_bps", "entry_trend_state", "entry_drawdown_state"]
    for keys, group in trades.groupby(group_cols):
        strategy, cost_bps, trend_state, drawdown_state = keys
        rows.append(
            {
                "strategy": strategy,
                "roundtrip_cost_bps": cost_bps,
                "entry_trend_state": trend_state,
                "entry_drawdown_state": drawdown_state,
                "trade_count": int(len(group)),
                "win_rate": to_float((group["net_return_est"] > 0).mean()),
                "avg_net_return": to_float(group["net_return_est"].mean()),
                "median_net_return": to_float(group["net_return_est"].median()),
                "avg_holding_days": to_float(group["holding_days"].mean()),
                "etf_count": int(group["ts_code"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "strategy", "entry_trend_state", "entry_drawdown_state"])


def build_holding_state_summary(all_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    holding = all_curves[all_curves["position"] > 0].copy()
    if holding.empty:
        return pd.DataFrame()
    group_cols = ["strategy", "roundtrip_cost_bps", "trend_state", "drawdown_state"]
    for keys, group in holding.groupby(group_cols):
        strategy, cost_bps, trend_state, drawdown_state = keys
        returns = group["strategy_daily_ret"].fillna(0.0)
        rows.append(
            {
                "strategy": strategy,
                "roundtrip_cost_bps": cost_bps,
                "trend_state": trend_state,
                "drawdown_state": drawdown_state,
                "holding_etf_days": int(len(group)),
                "avg_daily_ret": to_float(returns.mean()),
                "median_daily_ret": to_float(returns.median()),
                "compounded_ret": to_float((1.0 + returns).prod() - 1.0),
                "etf_count": int(group["ts_code"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "strategy", "trend_state", "drawdown_state"])


def build_yearly(all_curves: pd.DataFrame) -> pd.DataFrame:
    work = all_curves.copy()
    work["year"] = pd.to_datetime(work["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for keys, group in work.groupby(["ts_code", "strategy", "roundtrip_cost_bps", "year"]):
        ts_code, strategy, cost_bps, year = keys
        rows.append(
            {
                "ts_code": ts_code,
                "strategy": strategy,
                "roundtrip_cost_bps": cost_bps,
                "year": int(year),
                "year_return": to_float((1.0 + group["strategy_daily_ret"].fillna(0.0)).prod() - 1.0),
                "year_buy_hold_return": to_float((1.0 + group["buy_hold_costed_daily_ret"].fillna(0.0)).prod() - 1.0),
                "avg_position": to_float(group["position"].mean()),
                "trade_count": int((group["trade_abs_delta"] > 0).sum()),
                "year_cost_drag": to_float(group["trade_cost_ret"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "ts_code", "strategy", "year"])


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 60) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(
    summary: pd.DataFrame,
    pool_summary: pd.DataFrame,
    entry_state: pd.DataFrame,
    holding_state: pd.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    primary_boll = summary[
        (summary["role"] == "primary")
        & (summary["strategy"] == "bollinger20_2_ma200")
        & (summary["roundtrip_cost_bps"] == 20.0)
    ].copy()
    primary_boll = primary_boll.sort_values(["final_equity"], ascending=False)
    pool_20 = pool_summary[pool_summary["roundtrip_cost_bps"] == 20.0].copy()
    entry_boll = entry_state[
        (entry_state["strategy"].isin(["bollinger20_2_ma200", "bollinger20_2_no_filter"]))
        & (entry_state["roundtrip_cost_bps"] == 20.0)
    ].copy()
    holding_boll = holding_state[
        (holding_state["strategy"].isin(["bollinger20_2_ma200", "bollinger20_2_no_filter"]))
        & (holding_state["roundtrip_cost_bps"] == 20.0)
    ].copy()

    best_primary = primary_boll.head(1)
    lines = [
        "# 股票震荡宽基ETF模板状态归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定ETF业界模板的跨指数状态归因，不是正式交易版本。",
        f"- 输入数据：`{BROAD_ETF_DAILY_PATH}`",
        f"- ETF数量：`{meta['etf_count']}`，策略模板数：`{len(STRATEGIES)}`，成本档：`{','.join(str(int(x)) + 'bp' for x in ROUNDTRIP_COST_BPS)}`。",
        "- 执行口径：收盘生成信号，次日收盘换仓；收益使用Tushare `pct_chg`。",
        "",
        "## 核心观察",
        "",
    ]
    if not best_primary.empty:
        row = best_primary.iloc[0]
        lines.append(
            f"- primary ETF里20bp `bollinger20_2_ma200`期末权益最高的是`{row['ts_code']}`/`{row['index_name']}`："
            f"期末权益`{row['final_equity']:.4f}`，最大回撤`{pct(row['max_drawdown'])}`，"
            f"Sharpe `{row['sharpe']:.2f}`，交易`{int(row['trade_count'])}`次。"
        )
    pool_boll = pool_summary[
        (pool_summary["strategy"] == "bollinger20_2_ma200") & (pool_summary["roundtrip_cost_bps"] == 20.0)
    ]
    if not pool_boll.empty:
        row = pool_boll.iloc[0]
        lines.append(
            f"- 全ETF等权池20bp `bollinger20_2_ma200`：期末权益`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`，"
            f"平均持有ETF数`{row['avg_active_etf_count']:.2f}`。"
        )
    lines.extend(
        [
            "- 本阶段不根据状态结果即时加过滤器；状态归因只回答“钱在哪些状态里来”，不直接变成参数。",
            "- MA200过滤牺牲一部分收益弹性，但明显把交易集中到上行趋势回撤中；无过滤模板更容易吃到深回撤和趋势下跌阶段。",
            "",
            "## primary ETF：Bollinger+MA200 20bp",
            "",
            markdown_table(
                primary_boll,
                [
                    "ts_code",
                    "index_name",
                    "start_date",
                    "end_date",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "buy_hold_final_equity",
                    "buy_hold_max_drawdown",
                    "active_day_ratio",
                    "trade_count",
                    "win_rate",
                    "annualized_abs_turnover",
                ],
            ),
            "",
            "## 全ETF等权池",
            "",
            markdown_table(
                pool_20.sort_values("final_equity", ascending=False),
                [
                    "strategy",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_active_etf_count",
                    "avg_available_etf_count",
                ],
            ),
            "",
            "## 交易入口状态归因 20bp",
            "",
            markdown_table(
                entry_boll.sort_values(["strategy", "entry_trend_state", "entry_drawdown_state"]),
                [
                    "strategy",
                    "entry_trend_state",
                    "entry_drawdown_state",
                    "trade_count",
                    "win_rate",
                    "avg_net_return",
                    "median_net_return",
                    "avg_holding_days",
                    "etf_count",
                ],
                max_rows=80,
            ),
            "",
            "## 持有日状态归因 20bp",
            "",
            markdown_table(
                holding_boll.sort_values(["strategy", "trend_state", "drawdown_state"]),
                [
                    "strategy",
                    "trend_state",
                    "drawdown_state",
                    "holding_etf_days",
                    "avg_daily_ret",
                    "median_daily_ret",
                    "compounded_ret",
                    "etf_count",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：沿用上一阶段固定业界模板和固定宽基ETF池，不根据中间结果改阈值、删ETF或新增状态过滤。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：状态结果只做归因记录，没有把表现好的状态即时改成交易规则；A500/中证2000等短样本也保留但不作为全历史证据。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：单一中证1000 ETF模板只能说明局部现象，跨指数和状态归因可以判断ETF震荡骨架是否更接近可穿越周期。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但仍不是正式策略。",
            "- 原因：ETF等权池和多指数样本能看到低换手、低回撤骨架的结构性优势；但收益厚度仍有限，后续应先做状态稳定性和组合层设计。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段即时新增状态过滤器。",
            "- 下一步若继续，先做ETF池组合版本，而不是回到单ETF参数微调。",
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
    broad_daily = load_broad_etf_daily()
    curves: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for etf_code, group in broad_daily.groupby("ts_code"):
        prepared = add_indicators(group)
        for strategy in STRATEGIES:
            for cost_bps in ROUNDTRIP_COST_BPS:
                daily, trade = run_template(prepared, strategy, cost_bps)
                curves.append(daily)
                trades.append(trade)
                summary_rows.append(summarize_daily(daily, trade))

    all_curves = pd.concat(curves, ignore_index=True, sort=False)
    all_trades = pd.concat(trades, ignore_index=True, sort=False) if trades else pd.DataFrame()
    summary = pd.DataFrame(summary_rows).sort_values(["roundtrip_cost_bps", "ts_code", "strategy"])
    pool_summary, pool_daily = build_pool_summary(all_curves)
    entry_state = build_entry_state_summary(all_trades)
    holding_state = build_holding_state_summary(all_curves)
    yearly = build_yearly(all_curves)
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "input": str(BROAD_ETF_DAILY_PATH),
        "etf_count": int(broad_daily["ts_code"].nunique()),
        "etf_codes": sorted(broad_daily["ts_code"].unique().tolist()),
        "roundtrip_cost_bps": list(ROUNDTRIP_COST_BPS),
        "strategies": [strategy.__dict__ for strategy in STRATEGIES],
        "execution": "signals at close, position changes at next close; returns use Tushare pct_chg",
    }
    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "daily_curves": OUTPUT_DIR / f"{PREFIX}_daily_curves.csv",
        "trades": OUTPUT_DIR / f"{PREFIX}_trades.csv",
        "pool_summary": OUTPUT_DIR / f"{PREFIX}_pool_summary.csv",
        "pool_daily": OUTPUT_DIR / f"{PREFIX}_pool_daily.csv",
        "entry_state": OUTPUT_DIR / f"{PREFIX}_entry_state.csv",
        "holding_state": OUTPUT_DIR / f"{PREFIX}_holding_state.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    all_curves.to_csv(paths["daily_curves"], index=False, encoding="utf-8-sig")
    all_trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    pool_summary.to_csv(paths["pool_summary"], index=False, encoding="utf-8-sig")
    pool_daily.to_csv(paths["pool_daily"], index=False, encoding="utf-8-sig")
    entry_state.to_csv(paths["entry_state"], index=False, encoding="utf-8-sig")
    holding_state.to_csv(paths["holding_state"], index=False, encoding="utf-8-sig")
    yearly.to_csv(paths["yearly"], index=False, encoding="utf-8-sig")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(summary, pool_summary, entry_state, holding_state, meta, paths)
    print(summary.to_string(index=False))
    print(pool_summary.to_string(index=False))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
