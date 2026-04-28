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
BROAD_ETF_SUMMARY_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_summary.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_signal_sleeve_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_broad_etf_signal_sleeve_v1"

TRADING_DAYS: int = 252
INITIAL_EQUITY: float = 1.0
ROUNDTRIP_COST_BPS: tuple[float, ...] = (10.0, 20.0, 50.0)
SLEEVE_WEIGHTS: tuple[float, ...] = (0.05, 0.10)
TOTAL_EXPOSURE_CAPS: tuple[float, ...] = (0.30, 0.50)


@dataclass(frozen=True)
class TemplateStrategy:
    name: str
    description: str
    family: str
    max_hold_days: int


STRATEGIES: tuple[TemplateStrategy, ...] = (
    TemplateStrategy(
        name="bollinger20_2_ma200",
        description="Bollinger 20日-2σ买入，回到MA20退出，要求收盘在MA200上方",
        family="bollinger20_2",
        max_hold_days=15,
    ),
    TemplateStrategy(
        name="connors_rsi2_ma200",
        description="Connors风格RSI(2)<=10买入，收盘站上MA5退出，要求收盘在MA200上方",
        family="connors_rsi2",
        max_hold_days=10,
    ),
)


@dataclass(frozen=True)
class UniverseConfig:
    name: str
    description: str
    min_years: float
    min_p10_amount_raw: float


UNIVERSES: tuple[UniverseConfig, ...] = (
    UniverseConfig(
        name="primary_long_all",
        description="primary且样本不少于5年，不按流动性再过滤",
        min_years=5.0,
        min_p10_amount_raw=0.0,
    ),
    UniverseConfig(
        name="primary_tradable_p10_2000",
        description="primary且样本不少于5年，p10成交额原始口径不少于2000",
        min_years=5.0,
        min_p10_amount_raw=2000.0,
    ),
    UniverseConfig(
        name="primary_core_liquid_p10_50000",
        description="primary且样本不少于5年，p10成交额原始口径不少于50000",
        min_years=5.0,
        min_p10_amount_raw=50_000.0,
    ),
)


@dataclass(frozen=True)
class SleeveConfig:
    universe: UniverseConfig
    strategy: TemplateStrategy
    sleeve_weight: float
    total_exposure_cap: float
    roundtrip_cost_bps: float

    @property
    def name(self) -> str:
        sleeve = int(round(self.sleeve_weight * 100))
        cap = int(round(self.total_exposure_cap * 100))
        cost = int(self.roundtrip_cost_bps)
        return f"{self.universe.name}__{self.strategy.name}__sleeve{sleeve}__cap{cap}__cost{cost}bp"


def pct(value: float) -> str:
    return f"{value:.2%}"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BROAD_ETF_DAILY_PATH.exists():
        raise FileNotFoundError(f"Broad ETF daily data not found: {BROAD_ETF_DAILY_PATH}")
    if not BROAD_ETF_BASIC_PATH.exists():
        raise FileNotFoundError(f"Broad ETF basic data not found: {BROAD_ETF_BASIC_PATH}")
    if not BROAD_ETF_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Broad ETF summary data not found: {BROAD_ETF_SUMMARY_PATH}")

    daily = pd.read_csv(BROAD_ETF_DAILY_PATH, encoding="utf-8-sig")
    basic = pd.read_csv(BROAD_ETF_BASIC_PATH, encoding="utf-8-sig")
    summary = pd.read_csv(BROAD_ETF_SUMMARY_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    for column in ("pre_close", "open", "high", "low", "close", "pct_chg", "daily_ret", "amount", "vol"):
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    for column in ("years", "median_amount_raw", "p10_amount_raw"):
        summary[column] = pd.to_numeric(summary[column], errors="coerce")

    keep = ["ts_code", "index_bucket", "index_name", "role", "name", "m_fee", "c_fee"]
    frame = daily.merge(basic[keep], on="ts_code", how="left")
    frame = frame.dropna(subset=["date", "close", "daily_ret"]).sort_values(["ts_code", "date"])
    return frame.reset_index(drop=True), summary


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


def strategy_entry_exit(row: dict[str, Any], strategy: TemplateStrategy) -> tuple[bool, bool]:
    trend_ok = bool(pd.notna(row.get("ma200")) and to_float(row.get("close")) > to_float(row.get("ma200")))
    if strategy.family == "connors_rsi2":
        rsi2 = to_float(row.get("rsi2"), default=100.0)
        entry = bool(rsi2 <= 10.0 and trend_ok)
        exit_signal = bool(pd.notna(row.get("ma5")) and to_float(row.get("close")) > to_float(row.get("ma5")))
        return entry, exit_signal
    if strategy.family == "bollinger20_2":
        z20 = to_float(row.get("z20"), default=0.0)
        entry = bool(pd.notna(row.get("z20")) and z20 <= -2.0 and trend_ok)
        exit_signal = bool(pd.notna(row.get("ma20")) and to_float(row.get("close")) >= to_float(row.get("ma20")))
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


def select_universe(summary: pd.DataFrame, universe: UniverseConfig) -> pd.DataFrame:
    selected = summary[
        (summary["role"] == "primary")
        & (summary["years"] >= universe.min_years)
        & (summary["p10_amount_raw"] >= universe.min_p10_amount_raw)
    ].copy()
    return selected.sort_values(["index_bucket", "index_name", "ts_code"]).reset_index(drop=True)


def build_records(prepared: pd.DataFrame, codes: set[str]) -> dict[Any, dict[str, dict[str, Any]]]:
    records: dict[Any, dict[str, dict[str, Any]]] = {}
    for record in prepared[prepared["ts_code"].isin(codes)].to_dict("records"):
        records.setdefault(record["date"], {})[str(record["ts_code"])] = record
    return records


def close_trade(
    trades: list[dict[str, Any]],
    open_trades: dict[str, dict[str, Any]],
    code: str,
    row: dict[str, Any],
    date: Any,
    cost_bps: float,
    exit_reason: str,
) -> None:
    meta = open_trades.pop(code, None)
    if not meta:
        return
    gross_return = to_float(meta.get("growth"), default=1.0) - 1.0
    trades.append(
        {
            "ts_code": code,
            "etf_name": row.get("name", ""),
            "index_bucket": row.get("index_bucket", ""),
            "index_name": row.get("index_name", ""),
            "entry_signal_date": meta.get("entry_signal_date"),
            "entry_date": meta.get("entry_date"),
            "exit_date": date,
            "holding_days": int(meta.get("holding_days", 0)),
            "entry_close": meta.get("entry_close", 0.0),
            "exit_close": to_float(row.get("close")),
            "entry_trend_state": meta.get("entry_trend_state", ""),
            "entry_drawdown_state": meta.get("entry_drawdown_state", ""),
            "gross_return": gross_return,
            "net_return_est": gross_return - cost_bps / 10_000.0,
            "exit_reason": exit_reason,
        }
    )


def equal_weight(active_codes: set[str], sleeve_weight: float, total_cap: float) -> dict[str, float]:
    if not active_codes:
        return {}
    raw_total = len(active_codes) * sleeve_weight
    scale = min(1.0, total_cap / raw_total) if raw_total > 0 else 0.0
    return {code: sleeve_weight * scale for code in sorted(active_codes)}


def run_sleeve(
    prepared: pd.DataFrame,
    eligible: pd.DataFrame,
    config: SleeveConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    codes = set(eligible["ts_code"].astype(str))
    records = build_records(prepared, codes)
    dates = sorted(records)
    one_way_cost = config.roundtrip_cost_bps / 2.0 / 10_000.0
    active_codes: set[str] = set()
    current_weights: dict[str, float] = {}
    pending_weights: dict[str, float] = {}
    pending_active_codes: set[str] = set()
    pending_entry_meta: dict[str, dict[str, Any]] = {}
    open_trades: dict[str, dict[str, Any]] = {}
    daily_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for date_index, date in enumerate(dates):
        day_records = records.get(date, {})
        is_last = date_index == len(dates) - 1
        trade_codes = set(current_weights) | set(pending_weights)
        turnover = sum(abs(pending_weights.get(code, 0.0) - current_weights.get(code, 0.0)) for code in trade_codes)

        for code in sorted(trade_codes):
            before = current_weights.get(code, 0.0)
            after = pending_weights.get(code, 0.0)
            row = day_records.get(code)
            if after > 0 and before <= 0 and row is not None:
                meta = pending_entry_meta.get(code, {})
                open_trades[code] = {
                    "entry_signal_date": meta.get("entry_signal_date", row.get("date")),
                    "entry_date": date,
                    "entry_close": to_float(row.get("close")),
                    "entry_trend_state": meta.get("entry_trend_state", row.get("trend_state", "")),
                    "entry_drawdown_state": meta.get("entry_drawdown_state", row.get("drawdown_state", "")),
                    "growth": 1.0,
                    "holding_days": 0,
                }
            elif after <= 0 and before > 0:
                close_row = row or {"close": 0.0, "name": "", "index_bucket": "", "index_name": ""}
                close_trade(trade_rows, open_trades, code, close_row, date, config.roundtrip_cost_bps, "signal_exit")

        active_codes = set(pending_active_codes)
        current_weights = {code: weight for code, weight in pending_weights.items() if weight > 0}
        pending_entry_meta = {}

        interval_ret = 0.0
        available_next_returns: list[float] = []
        for code, row in day_records.items():
            next_ret = to_float(row.get("next_daily_ret"), default=0.0)
            if pd.notna(row.get("next_daily_ret")):
                available_next_returns.append(next_ret)
            weight = current_weights.get(code, 0.0)
            if weight > 0:
                interval_ret += weight * next_ret
                if code in open_trades:
                    open_trades[code]["growth"] = to_float(open_trades[code].get("growth"), default=1.0) * (1.0 + next_ret)
                    open_trades[code]["holding_days"] = int(open_trades[code].get("holding_days", 0)) + 1

        strategy_daily_ret = interval_ret - turnover * one_way_cost
        final_close_cost = 0.0
        if is_last and current_weights:
            final_close_turnover = sum(abs(weight) for weight in current_weights.values())
            final_close_cost = final_close_turnover * one_way_cost
            strategy_daily_ret -= final_close_cost
            for code in sorted(current_weights):
                row = day_records.get(code, {"close": 0.0, "name": "", "index_bucket": "", "index_name": ""})
                close_trade(trade_rows, open_trades, code, row, date, config.roundtrip_cost_bps, "final_close")
            active_codes = set()
            current_weights = {}
            pending_active_codes = set()
            pending_weights = {}

        equal_universe_ret = sum(available_next_returns) / len(available_next_returns) if available_next_returns else 0.0
        signal_count = 0
        if not is_last:
            next_active_codes: set[str] = set()
            next_entry_meta: dict[str, dict[str, Any]] = {}
            for code in sorted(codes):
                row = day_records.get(code)
                if row is None:
                    continue
                entry_signal, exit_signal = strategy_entry_exit(row, config.strategy)
                is_active = code in active_codes
                hold_days = int(open_trades.get(code, {}).get("holding_days", 0))
                exit_by_hold = is_active and hold_days >= config.strategy.max_hold_days
                if is_active and not exit_signal and not exit_by_hold:
                    next_active_codes.add(code)
                elif not is_active and entry_signal:
                    signal_count += 1
                    next_active_codes.add(code)
                    next_entry_meta[code] = {
                        "entry_signal_date": date,
                        "entry_trend_state": row.get("trend_state", ""),
                        "entry_drawdown_state": row.get("drawdown_state", ""),
                    }
            pending_active_codes = next_active_codes
            pending_weights = equal_weight(pending_active_codes, config.sleeve_weight, config.total_exposure_cap)
            pending_entry_meta = next_entry_meta
            for code, weight in pending_weights.items():
                row = day_records.get(code, {})
                target_rows.append(
                    {
                        "date": date,
                        "portfolio": config.name,
                        "universe": config.universe.name,
                        "strategy": config.strategy.name,
                        "sleeve_weight": config.sleeve_weight,
                        "total_exposure_cap": config.total_exposure_cap,
                        "roundtrip_cost_bps": config.roundtrip_cost_bps,
                        "ts_code": code,
                        "index_name": row.get("index_name", ""),
                        "target_weight": weight,
                        "trend_state": row.get("trend_state", ""),
                        "drawdown_state": row.get("drawdown_state", ""),
                    }
                )

        daily_rows.append(
            {
                "date": date,
                "portfolio": config.name,
                "universe": config.universe.name,
                "strategy": config.strategy.name,
                "sleeve_weight": config.sleeve_weight,
                "total_exposure_cap": config.total_exposure_cap,
                "roundtrip_cost_bps": config.roundtrip_cost_bps,
                "eligible_etf_count": len(codes),
                "active_etf_count": len(current_weights),
                "gross_exposure": sum(current_weights.values()),
                "turnover": turnover,
                "trade_cost_ret": turnover * one_way_cost + final_close_cost,
                "strategy_daily_ret": strategy_daily_ret,
                "equal_universe_daily_ret": equal_universe_ret,
                "new_signal_count": signal_count,
                "held_codes": ",".join(sorted(current_weights)),
            }
        )

    daily = pd.DataFrame(daily_rows)
    trades = pd.DataFrame(trade_rows)
    targets = pd.DataFrame(target_rows)
    if not daily.empty:
        equity, drawdown = equity_and_drawdown(daily["strategy_daily_ret"])
        daily["strategy_equity"] = equity
        daily["strategy_drawdown"] = drawdown
        baseline_equity, baseline_drawdown = equity_and_drawdown(daily["equal_universe_daily_ret"])
        daily["equal_universe_equity"] = baseline_equity
        daily["equal_universe_drawdown"] = baseline_drawdown
    return daily, trades, targets


def summarize_portfolio(daily: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {}
    ret = daily["strategy_daily_ret"].fillna(0.0)
    mean = ret.mean()
    std = ret.std(ddof=1)
    total_return = to_float(daily["strategy_equity"].iloc[-1] - 1.0)
    baseline_return = to_float(daily["equal_universe_equity"].iloc[-1] - 1.0)
    trade_count = int(len(trades))
    return {
        "portfolio": str(daily["portfolio"].iloc[0]),
        "universe": str(daily["universe"].iloc[0]),
        "strategy": str(daily["strategy"].iloc[0]),
        "sleeve_weight": to_float(daily["sleeve_weight"].iloc[0]),
        "total_exposure_cap": to_float(daily["total_exposure_cap"].iloc[0]),
        "roundtrip_cost_bps": to_float(daily["roundtrip_cost_bps"].iloc[0]),
        "eligible_etf_count": int(daily["eligible_etf_count"].iloc[0]),
        "days": int(len(daily)),
        "start_date": str(daily["date"].min()),
        "end_date": str(daily["date"].max()),
        "final_equity": to_float(daily["strategy_equity"].iloc[-1]),
        "total_return": total_return,
        "annualized_return": (1.0 + total_return) ** (TRADING_DAYS / len(daily)) - 1.0
        if len(daily) and total_return > -1
        else 0.0,
        "max_drawdown": to_float(daily["strategy_drawdown"].min()),
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std else 0.0,
        "baseline_equal_final_equity": to_float(daily["equal_universe_equity"].iloc[-1]),
        "baseline_equal_total_return": baseline_return,
        "baseline_equal_max_drawdown": to_float(daily["equal_universe_drawdown"].min()),
        "avg_active_etf_count": to_float(daily["active_etf_count"].mean()),
        "avg_gross_exposure": to_float(daily["gross_exposure"].mean()),
        "max_gross_exposure": to_float(daily["gross_exposure"].max()),
        "annualized_turnover": to_float(daily["turnover"].mean()) * TRADING_DAYS,
        "cost_drag_sum": to_float(daily["trade_cost_ret"].sum()),
        "entry_count": trade_count,
        "win_rate": to_float((trades["net_return_est"] > 0).mean()) if trade_count else 0.0,
        "avg_trade_net_return": to_float(trades["net_return_est"].mean()) if trade_count else 0.0,
        "median_trade_net_return": to_float(trades["net_return_est"].median()) if trade_count else 0.0,
        "avg_holding_days": to_float(trades["holding_days"].mean()) if trade_count else 0.0,
        "signal_days": int((daily["new_signal_count"] > 0).sum()),
    }


def build_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    work = daily.copy()
    work["year"] = pd.to_datetime(work["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for keys, group in work.groupby(["portfolio", "year"]):
        portfolio, year = keys
        rows.append(
            {
                "portfolio": portfolio,
                "year": int(year),
                "year_return": to_float((1.0 + group["strategy_daily_ret"].fillna(0.0)).prod() - 1.0),
                "baseline_year_return": to_float((1.0 + group["equal_universe_daily_ret"].fillna(0.0)).prod() - 1.0),
                "avg_active_etf_count": to_float(group["active_etf_count"].mean()),
                "avg_gross_exposure": to_float(group["gross_exposure"].mean()),
                "year_turnover": to_float(group["turnover"].sum()),
                "year_cost_drag": to_float(group["trade_cost_ret"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["portfolio", "year"])


def build_index_contribution(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for keys, group in trades.groupby(["portfolio", "index_name"]):
        portfolio, index_name = keys
        rows.append(
            {
                "portfolio": portfolio,
                "index_name": index_name,
                "trade_count": int(len(group)),
                "win_rate": to_float((group["net_return_est"] > 0).mean()),
                "avg_net_return": to_float(group["net_return_est"].mean()),
                "median_net_return": to_float(group["net_return_est"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["portfolio", "avg_net_return"])


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    index_contribution: pd.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    focus = summary[
        (summary["strategy"] == "bollinger20_2_ma200")
        & (summary["universe"].isin(["primary_tradable_p10_2000", "primary_core_liquid_p10_50000"]))
    ].copy()
    focus_20 = focus[focus["roundtrip_cost_bps"] == 20.0].sort_values(
        ["max_drawdown", "final_equity"], ascending=[False, False]
    )
    focus_50 = focus[focus["roundtrip_cost_bps"] == 50.0].sort_values(
        ["max_drawdown", "final_equity"], ascending=[False, False]
    )
    all_20 = summary[summary["roundtrip_cost_bps"] == 20.0].sort_values("final_equity", ascending=False)
    best_boll_20 = focus_20.sort_values(["final_equity", "max_drawdown"], ascending=[False, False]).head(1)
    best_boll_50 = focus_50.sort_values(["final_equity", "max_drawdown"], ascending=[False, False]).head(1)
    lines = [
        "# 股票震荡宽基ETF小权重全信号袖珍仓 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：ETF池小权重全信号分散账本，不是正式交易版本。",
        f"- 输入数据：`{BROAD_ETF_DAILY_PATH}`",
        f"- 宇宙数量：`{len(UNIVERSES)}`，策略模板数：`{len(STRATEGIES)}`，袖珍仓权重：`{','.join(pct(x) for x in SLEEVE_WEIGHTS)}`，总暴露上限：`{','.join(pct(x) for x in TOTAL_EXPOSURE_CAPS)}`，成本档：`{','.join(str(int(x)) + 'bp' for x in ROUNDTRIP_COST_BPS)}`。",
        "- 执行口径：收盘生成信号，次日收盘换仓；收益使用Tushare `pct_chg`。",
        "- 组合规则：每个ETF信号独立获得固定小权重，不按超跌程度排名；若总权重超过暴露上限，则所有活跃信号等比例缩放。",
        "",
        "## 核心观察",
        "",
    ]
    if not best_boll_20.empty:
        row = best_boll_20.iloc[0]
        lines.append(
            f"- 20bp下`Bollinger+MA200`焦点池里期末权益较高的是`{row['portfolio']}`："
            f"期末权益`{row['final_equity']:.4f}`，最大回撤`{pct(row['max_drawdown'])}`，"
            f"Sharpe `{row['sharpe']:.2f}`，平均暴露`{pct(row['avg_gross_exposure'])}`。"
        )
    if not best_boll_50.empty:
        row = best_boll_50.iloc[0]
        lines.append(
            f"- 50bp压力下同类焦点池最佳期末权益为`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`，说明成本压力仍然是真边界。"
        )
    lines.extend(
        [
            "- 与topN组合不同，小权重全信号不让指数之间抢仓位，能检验低回撤是否来自分散账本。",
            "- 如果该账本仍不能明显改善回撤/收益比，就说明ETF路线更适合单指数袖珍仓或观察工具，而非主动轮动组合。",
            "- 本阶段不根据指数贡献删ETF，也不新增状态过滤器。",
            "",
            "## 20bp综合结果",
            "",
            markdown_table(
                all_20,
                [
                    "universe",
                    "strategy",
                    "sleeve_weight",
                    "total_exposure_cap",
                    "eligible_etf_count",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_active_etf_count",
                    "avg_gross_exposure",
                    "max_gross_exposure",
                    "annualized_turnover",
                    "entry_count",
                ],
                max_rows=100,
            ),
            "",
            "## Bollinger+MA200 焦点池 20bp",
            "",
            markdown_table(
                focus_20,
                [
                    "universe",
                    "sleeve_weight",
                    "total_exposure_cap",
                    "eligible_etf_count",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_active_etf_count",
                    "avg_gross_exposure",
                    "max_gross_exposure",
                    "annualized_turnover",
                    "cost_drag_sum",
                    "entry_count",
                    "win_rate",
                ],
                max_rows=80,
            ),
            "",
            "## Bollinger+MA200 焦点池 50bp",
            "",
            markdown_table(
                focus_50,
                [
                    "universe",
                    "sleeve_weight",
                    "total_exposure_cap",
                    "eligible_etf_count",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_active_etf_count",
                    "avg_gross_exposure",
                    "max_gross_exposure",
                    "annualized_turnover",
                    "cost_drag_sum",
                    "entry_count",
                    "win_rate",
                ],
                max_rows=80,
            ),
            "",
            "## 年度样本：tradable Bollinger 5% cap30 20bp",
            "",
            markdown_table(
                yearly[
                    yearly["portfolio"]
                    == "primary_tradable_p10_2000__bollinger20_2_ma200__sleeve5__cap30__cost20bp"
                ],
                [
                    "year",
                    "year_return",
                    "baseline_year_return",
                    "avg_active_etf_count",
                    "avg_gross_exposure",
                    "year_turnover",
                    "year_cost_drag",
                ],
            ),
            "",
            "## 指数贡献：tradable Bollinger 5% cap30 20bp",
            "",
            markdown_table(
                index_contribution[
                    index_contribution["portfolio"]
                    == "primary_tradable_p10_2000__bollinger20_2_ma200__sleeve5__cap30__cost20bp"
                ],
                ["index_name", "trade_count", "win_rate", "avg_net_return", "median_net_return"],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段使用事先固定的primary宇宙、固定袖珍仓权重、固定总暴露上限和固定MA200模板，不按结果做排名筛选。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：输出保留全部宇宙、全部权重档、全部暴露上限和10/20/50bp成本；结论不选择单一组合正式化。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：topN组合已经证明指数间竞争有害，小权重全信号能检验是否可以用分散账本保留单ETF低回撤特征。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：有研究价值，但不适合作为正式策略候选继续参数化。",
            "- 原因：小权重全信号显著压低了topN账本的回撤，说明指数间不抢仓位是对的；但收益厚度很薄，50bp压力下只剩微弱正收益，年度收益也更像观察仓而不是主策略。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 不继续围绕ETF池权重、暴露上限或成本档调参。",
            "- 下一步应回到固定指数袖珍仓/指数画像，确认哪些指数天然适合震荡接刀；若仍无收益厚度，再转向行业内残差/个股横截面路线。",
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
    broad_daily, broad_summary = load_inputs()
    prepared = pd.concat([add_indicators(group) for _, group in broad_daily.groupby("ts_code")], ignore_index=True)
    configs = [
        SleeveConfig(
            universe=universe,
            strategy=strategy,
            sleeve_weight=sleeve_weight,
            total_exposure_cap=total_cap,
            roundtrip_cost_bps=cost_bps,
        )
        for universe in UNIVERSES
        for strategy in STRATEGIES
        for sleeve_weight in SLEEVE_WEIGHTS
        for total_cap in TOTAL_EXPOSURE_CAPS
        for cost_bps in ROUNDTRIP_COST_BPS
    ]

    all_daily: list[pd.DataFrame] = []
    all_trades: list[pd.DataFrame] = []
    all_targets: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for config in configs:
        eligible = select_universe(broad_summary, config.universe)
        daily, trades, targets = run_sleeve(prepared, eligible, config)
        if not trades.empty:
            trades.insert(0, "portfolio", config.name)
            trades.insert(1, "universe", config.universe.name)
            trades.insert(2, "strategy", config.strategy.name)
            trades.insert(3, "sleeve_weight", config.sleeve_weight)
            trades.insert(4, "total_exposure_cap", config.total_exposure_cap)
            trades.insert(5, "roundtrip_cost_bps", config.roundtrip_cost_bps)
        all_daily.append(daily)
        all_trades.append(trades)
        all_targets.append(targets)
        summary_rows.append(summarize_portfolio(daily, trades))

    combined_daily = pd.concat(all_daily, ignore_index=True, sort=False)
    combined_trades = pd.concat([frame for frame in all_trades if not frame.empty], ignore_index=True, sort=False)
    combined_targets = pd.concat([frame for frame in all_targets if not frame.empty], ignore_index=True, sort=False)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["roundtrip_cost_bps", "universe", "strategy", "sleeve_weight", "total_exposure_cap"]
    )
    yearly = build_yearly(combined_daily)
    index_contribution = build_index_contribution(combined_trades)
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "input": str(BROAD_ETF_DAILY_PATH),
        "universes": [universe.__dict__ for universe in UNIVERSES],
        "strategies": [strategy.__dict__ for strategy in STRATEGIES],
        "sleeve_weights": list(SLEEVE_WEIGHTS),
        "total_exposure_caps": list(TOTAL_EXPOSURE_CAPS),
        "roundtrip_cost_bps": list(ROUNDTRIP_COST_BPS),
        "execution": "signals at close, position changes at next close; returns use Tushare pct_chg",
    }
    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "trades": OUTPUT_DIR / f"{PREFIX}_trades.csv",
        "targets": OUTPUT_DIR / f"{PREFIX}_targets.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "index_contribution": OUTPUT_DIR / f"{PREFIX}_index_contribution.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    combined_daily.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    combined_trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    combined_targets.to_csv(paths["targets"], index=False, encoding="utf-8-sig")
    yearly.to_csv(paths["yearly"], index=False, encoding="utf-8-sig")
    index_contribution.to_csv(paths["index_contribution"], index=False, encoding="utf-8-sig")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(summary, yearly, index_contribution, meta, paths)
    print(summary.to_string(index=False))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
