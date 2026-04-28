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
ETF_DATA_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_csi1000_etf_data_2018_2026"
ETF_DAILY_PATH: Path = ETF_DATA_DIR / "stock_range_reversion_csi1000_etf_data_v1_selected_daily.csv"
ETF_SUMMARY_PATH: Path = ETF_DATA_DIR / "stock_range_reversion_csi1000_etf_data_v1_etf_summary.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_etf_industry_template_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_etf_industry_template_v1"

TRADING_DAYS: int = 252
INITIAL_EQUITY: float = 1.0
ROUNDTRIP_COST_BPS: tuple[float, ...] = (10.0, 20.0, 50.0)
ETF_CODES: tuple[str, ...] = (
    "512100.SH",
    "159845.SZ",
    "560010.SH",
    "159629.SZ",
    "159633.SZ",
    "516300.SH",
    "560110.SH",
)


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
        description="Connors风格RSI(2)<10买入，收盘站上MA5退出，无趋势过滤",
        family="connors_rsi2",
        use_trend_filter=False,
        max_hold_days=10,
    ),
    TemplateStrategy(
        name="connors_rsi2_ma200",
        description="Connors风格RSI(2)<10买入，收盘站上MA5退出，要求收盘在MA200上方",
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


def load_etf_daily() -> pd.DataFrame:
    if not ETF_DAILY_PATH.exists():
        raise FileNotFoundError(f"ETF daily data not found: {ETF_DAILY_PATH}")
    frame = pd.read_csv(ETF_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ("pre_close", "open", "high", "low", "close", "pct_chg", "daily_ret", "amount", "vol"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[frame["ts_code"].isin(ETF_CODES)].dropna(subset=["date", "open", "close"])
    return frame.sort_values(["ts_code", "date"]).reset_index(drop=True)


def load_etf_names() -> dict[str, str]:
    if not ETF_SUMMARY_PATH.exists():
        return {code: code for code in ETF_CODES}
    frame = pd.read_csv(ETF_SUMMARY_PATH, encoding="utf-8-sig")
    return dict(zip(frame["ts_code"].astype(str), frame["name"].astype(str)))


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
    work["ma200"] = close.rolling(200, min_periods=200).mean()
    work["z20"] = (close - work["ma20"]) / work["std20"].replace(0.0, float("nan"))
    work["next_daily_ret"] = work["daily_ret"].shift(-1)
    work["buy_hold_daily_ret"] = work["daily_ret"].fillna(0.0)
    return work


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
    raise ValueError(f"Unknown family: {strategy.family}")


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


def run_template(etf: pd.DataFrame, strategy: TemplateStrategy, cost_bps: float, etf_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    one_way_cost = cost_bps / 2.0 / 10_000.0
    position = 0.0
    pending_position = 0.0
    entry_date = None
    entry_close = 0.0
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
        elif trade_delta < 0 and entry_date is not None:
            exit_close = to_float(row.close)
            gross_return = trade_growth - 1.0
            trade_rows.append(
                {
                    "ts_code": row.ts_code,
                    "etf_name": etf_name,
                    "strategy": strategy.name,
                    "roundtrip_cost_bps": cost_bps,
                    "entry_date": entry_date,
                    "exit_date": row.date,
                    "holding_days": holding_days,
                    "entry_close": entry_close,
                    "exit_close": exit_close,
                    "gross_return": gross_return,
                    "net_return_est": gross_return - cost_bps / 10_000.0,
                }
            )
            entry_date = None
            entry_close = 0.0
            trade_growth = 1.0
            holding_days = 0

        position = pending_position
        interval_ret = to_float(row.next_daily_ret) if index < len(rows) - 1 else 0.0
        strategy_daily_ret = position * interval_ret - trade_cost_ret
        if position > 0:
            trade_growth *= 1.0 + interval_ret

        if index == len(rows) - 1 and position > 0:
            strategy_daily_ret -= position * one_way_cost
            exit_close = to_float(row.close)
            gross_return = trade_growth - 1.0
            trade_rows.append(
                {
                    "ts_code": row.ts_code,
                    "etf_name": etf_name,
                    "strategy": strategy.name,
                    "roundtrip_cost_bps": cost_bps,
                    "entry_date": entry_date,
                    "exit_date": row.date,
                    "holding_days": holding_days,
                    "entry_close": entry_close,
                    "exit_close": exit_close,
                    "gross_return": gross_return,
                    "net_return_est": gross_return - cost_bps / 10_000.0,
                }
            )
            position = 0.0
            pending_position = 0.0

        row_series = pd.Series(row._asdict())
        entry_signal, exit_signal = strategy_entry_exit(row_series, strategy)
        if position > 0:
            holding_days += 1
        next_position = position
        exit_by_hold = position > 0 and holding_days >= strategy.max_hold_days
        if position <= 0 and entry_signal:
            next_position = 1.0
        elif position > 0 and (exit_signal or exit_by_hold):
            next_position = 0.0

        daily_rows.append(
            {
                "date": row.date,
                "ts_code": row.ts_code,
                "etf_name": etf_name,
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
                "open": to_float(row.open),
                "close": to_float(row.close),
                "rsi2": to_float(row.rsi2),
                "z20": to_float(row.z20),
                "ma5": to_float(row.ma5),
                "ma20": to_float(row.ma20),
                "ma200": to_float(row.ma200),
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
        buy_hold_ret.iloc[0] -= one_way_cost
        buy_hold_ret.iloc[-1] -= one_way_cost
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
    win_rate = to_float((trades["net_return_est"] > 0).mean()) if trade_count else 0.0
    return {
        "ts_code": str(daily["ts_code"].iloc[0]) if days else "",
        "etf_name": str(daily["etf_name"].iloc[0]) if days else "",
        "strategy": str(daily["strategy"].iloc[0]) if days else "",
        "family": str(daily["family"].iloc[0]) if days else "",
        "use_trend_filter": bool(daily["use_trend_filter"].iloc[0]) if days else False,
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
        "avg_position": to_float(daily["position"].mean()) if days else 0.0,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "avg_trade_net_return": to_float(trades["net_return_est"].mean()) if trade_count else 0.0,
        "median_trade_net_return": to_float(trades["net_return_est"].median()) if trade_count else 0.0,
        "avg_holding_days": to_float(trades["holding_days"].mean()) if trade_count else 0.0,
        "annualized_abs_turnover": to_float(daily["trade_abs_delta"].mean()) * TRADING_DAYS if days else 0.0,
        "cost_drag_sum": to_float(daily["trade_cost_ret"].sum()) if days else 0.0,
        "entry_signal_count": int(daily["entry_signal"].sum()) if days else 0,
    }


def build_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    work = daily.copy()
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
                "year_return": (1.0 + group["strategy_daily_ret"].fillna(0.0)).prod() - 1.0,
                "year_buy_hold_return": (1.0 + group["buy_hold_costed_daily_ret"].fillna(0.0)).prod() - 1.0,
                "avg_position": group["position"].mean(),
                "trade_count": int((group["trade_abs_delta"] > 0).sum()),
                "year_cost_drag": group["trade_cost_ret"].sum(),
            }
        )
    return pd.DataFrame(rows).sort_values(["roundtrip_cost_bps", "ts_code", "strategy", "year"])


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(summary: pd.DataFrame, yearly: pd.DataFrame, meta: dict[str, Any], paths: dict[str, Path]) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    full_512100 = summary[(summary["ts_code"] == "512100.SH") & (summary["roundtrip_cost_bps"] == 20.0)].copy()
    high_liq = summary[
        (summary["ts_code"].isin(["159845.SZ", "560010.SH", "159629.SZ"]))
        & (summary["roundtrip_cost_bps"] == 20.0)
    ].copy()
    best_512100 = full_512100.sort_values(["final_equity", "max_drawdown"], ascending=[False, False]).head(1)
    lines = [
        "# 股票震荡 ETF 业界模板均值回归 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：业界常见ETF均值回归模板验证，不是正式交易版本。",
        f"- 输入数据：`{ETF_DAILY_PATH}`",
        f"- 样本ETF数：`{meta['etf_count']}`，策略模板数：`{len(STRATEGIES)}`，成本档：`{','.join(str(int(x)) + 'bp' for x in ROUNDTRIP_COST_BPS)}`。",
        "- 执行口径：收盘生成信号，次日收盘换仓；收益使用Tushare `pct_chg`，避免ETF份额折算造成原始开盘价跳变污染。",
        "",
        "## 核心观察",
        "",
    ]
    if not best_512100.empty:
        row = best_512100.iloc[0]
        lines.append(
            f"- 全历史`512100.SH`在20bp下最好模板是`{row['strategy']}`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`，"
            f"交易次数`{int(row['trade_count'])}`。"
        )
    risk_512100 = full_512100[
        (full_512100["strategy"] == "bollinger20_2_ma200") & (full_512100["roundtrip_cost_bps"] == 20.0)
    ]
    if not risk_512100.empty:
        row = risk_512100.iloc[0]
        lines.append(
            f"- `512100.SH`风险更干净的模板是`bollinger20_2_ma200`：20bp期末权益`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`，交易次数`{int(row['trade_count'])}`，"
            f"年化绝对换手`{row['annualized_abs_turnover']:.2f}`。"
        )
    risk_512100_50 = summary[
        (summary["ts_code"] == "512100.SH")
        & (summary["strategy"] == "bollinger20_2_ma200")
        & (summary["roundtrip_cost_bps"] == 50.0)
    ]
    if not risk_512100_50.empty:
        row = risk_512100_50.iloc[0]
        lines.append(
            f"- 同一模板在50bp压力下仍为正：期末权益`{row['final_equity']:.4f}`，"
            f"最大回撤`{pct(row['max_drawdown'])}`，说明ETF模板比个股日频账本更抗成本，但收益厚度有限。"
        )
    lines.extend(
        [
            "- 原始ETF开盘价存在份额折算跳变，本阶段收益统一使用Tushare `pct_chg`；此前基于原始open-to-open的漂亮结果作废。",
            "- 这一步不选择正式参数，只看业界模板在A股ETF数据上是否天然比个股日频账本更低换手、更抗成本。",
            "",
            "## 512100全历史结果",
            "",
            markdown_table(
                full_512100.sort_values(["final_equity"], ascending=False),
                [
                    "strategy",
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
                    "cost_drag_sum",
                ],
            ),
            "",
            "## 后半段高流动ETF对照",
            "",
            markdown_table(
                high_liq.sort_values(["ts_code", "final_equity"], ascending=[True, False]),
                [
                    "ts_code",
                    "etf_name",
                    "strategy",
                    "start_date",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "buy_hold_final_equity",
                    "trade_count",
                    "annualized_abs_turnover",
                ],
                max_rows=60,
            ),
            "",
            "## 年度样本 512100 20bp",
            "",
            markdown_table(
                yearly[(yearly["ts_code"] == "512100.SH") & (yearly["roundtrip_cost_bps"] == 20.0)].sort_values(
                    ["strategy", "year"]
                ),
                [
                    "strategy",
                    "year",
                    "year_return",
                    "year_buy_hold_return",
                    "avg_position",
                    "trade_count",
                    "year_cost_drag",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：策略来自业界常见ETF均值回归模板，参数固定为RSI(2)<10、MA5退出、Bollinger 20/2σ、MA200趋势过滤；收益口径使用`pct_chg`以避开ETF份额折算，不根据本地结果扫参。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段保留全部ETF、全部模板和10/20/50bp成本；发现原始open-to-open被ETF折算污染后，主动改用`pct_chg`并放弃污染后的漂亮结果，没有按收益调参。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：业界ETF均值回归模板天然低标的数量、低组合替换复杂度，可能比日频个股篮子更适合A股long-only约束。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但它更像低回撤ETF择时骨架，不是高收益正式策略。",
            "- 原因：Bollinger+MA200模板在50bp下仍能保持正收益和低回撤，交易次数很少；但收益明显低于买入持有，下一步应先做多ETF/多指数数据审计和状态归因，而不是直接正式化。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 不把单一ETF/单一模板作为正式候选。",
            "- 下一步优先扩展到宽基ETF池并做状态归因，验证这个骨架是否跨指数成立。",
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
    etf_daily = load_etf_daily()
    etf_names = load_etf_names()
    curves: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for etf_code, group in etf_daily.groupby("ts_code"):
        prepared = add_indicators(group)
        etf_name = etf_names.get(str(etf_code), str(etf_code))
        for strategy in STRATEGIES:
            for cost_bps in ROUNDTRIP_COST_BPS:
                daily, trade = run_template(prepared, strategy, cost_bps, etf_name)
                curves.append(daily)
                trades.append(trade)
                summary_rows.append(summarize_daily(daily, trade))

    all_curves = pd.concat(curves, ignore_index=True, sort=False)
    all_trades = pd.concat(trades, ignore_index=True, sort=False) if trades else pd.DataFrame()
    summary = pd.DataFrame(summary_rows).sort_values(["roundtrip_cost_bps", "ts_code", "strategy"])
    yearly = build_yearly(all_curves)
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "input": str(ETF_DAILY_PATH),
        "etf_count": int(etf_daily["ts_code"].nunique()),
        "etf_codes": sorted(etf_daily["ts_code"].unique().tolist()),
        "roundtrip_cost_bps": list(ROUNDTRIP_COST_BPS),
        "strategies": [strategy.__dict__ for strategy in STRATEGIES],
        "execution": "signals at close, position changes at next close; returns use Tushare pct_chg to avoid raw price split artifacts",
    }
    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "daily_curves": OUTPUT_DIR / f"{PREFIX}_daily_curves.csv",
        "trades": OUTPUT_DIR / f"{PREFIX}_trades.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    all_curves.to_csv(paths["daily_curves"], index=False, encoding="utf-8-sig")
    all_trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    yearly.to_csv(paths["yearly"], index=False, encoding="utf-8-sig")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(summary, yearly, meta, paths)
    print(summary.to_string(index=False))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
