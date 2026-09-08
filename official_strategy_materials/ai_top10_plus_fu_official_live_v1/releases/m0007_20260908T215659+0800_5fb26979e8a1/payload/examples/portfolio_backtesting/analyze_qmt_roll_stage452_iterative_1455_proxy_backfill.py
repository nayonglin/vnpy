from __future__ import annotations

from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo
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


MODEL_TAG = "stage452_iterative_1455_proxy_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage452_iterative_1455_proxy_backfill"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RERUN_VARIANT = "stage079_rerun_same_day_close"
TRUE_PATH_VARIANT = "stage079_true_path_1455_vwap_symbol_date_backfilled"

RAW_ROOTS = [
    PROJECT_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
    PROJECT_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
]
WRITE_RAW_ROOT = RAW_ROOTS[0]
CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_ITERATIONS = 4
MAX_SECONDS_PER_SYMBOL = 180

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
PROXY_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_map_{MODEL_TAG}.csv"
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
        return {str(k): _json_safe(v) for k, v in value.items()}
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


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _raw_path(root: Path, vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return root / exchange / f"{symbol}_minute_backtest.csv"


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _load_raw_bars(vt_symbol: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for root in RAW_ROOTS:
        path = _raw_path(root, vt_symbol)
        if not path.exists():
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
        frame["vt_symbol"] = vt_symbol
        frames.append(frame.dropna(subset=["bar_datetime"]))
    if not frames:
        return pd.DataFrame(columns=["vt_symbol", "bar_datetime", "open", "close", "volume"])
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
    return bars.sort_values("bar_datetime").reset_index(drop=True)


def _proxy_from_bars(vt_symbol: str, date: pd.Timestamp) -> dict[str, Any] | None:
    bars = _load_raw_bars(vt_symbol)
    if bars.empty:
        return None
    start = pd.Timestamp(date).normalize() + pd.Timedelta(hours=14, minutes=55)
    end = pd.Timestamp(date).normalize() + pd.Timedelta(hours=15)
    window = bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].copy()
    if window.empty:
        return None
    volume = pd.to_numeric(window["volume"], errors="coerce").fillna(0.0)
    close = pd.to_numeric(window["close"], errors="coerce")
    volume_sum = float(volume.sum())
    price = float((close * volume).sum() / volume_sum) if volume_sum > 0 else float(close.mean())
    return {
        "date": pd.Timestamp(date).normalize(),
        "vt_symbol": vt_symbol,
        "proxy_price": price,
        "proxy_source": "raw_1455_vwap",
        "proxy_bar_count": int(len(window)),
        "proxy_first_time": window["bar_datetime"].iloc[0],
        "proxy_last_time": window["bar_datetime"].iloc[-1],
    }


def _seed_proxy_map_from_stage149() -> dict[tuple[pd.Timestamp, str], dict[str, Any]]:
    detail = pd.read_csv(s451.STAGE149_DETAIL_PATH, encoding="utf-8-sig")
    detail["date"] = pd.to_datetime(detail["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    detail["same_last5_vwap"] = pd.to_numeric(detail.get("same_last5_vwap", np.nan), errors="coerce")
    detail = detail[detail["date"].notna() & detail["same_last5_vwap"].gt(0.0)].copy()
    proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]] = {}
    for row in detail.sort_values(["date", "vt_symbol", "trade_id"]).itertuples(index=False):
        key = (pd.Timestamp(row.date).normalize(), str(row.vt_symbol))
        proxy_map.setdefault(
            key,
            {
                "date": key[0],
                "vt_symbol": key[1],
                "proxy_price": float(row.same_last5_vwap),
                "proxy_source": "stage149_same_last5_vwap_symbol_date",
                "proxy_bar_count": np.nan,
                "proxy_first_time": "",
                "proxy_last_time": "",
            },
        )
    return proxy_map


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _extract_symbol_windows(vt_symbol: str, dates: list[pd.Timestamp]) -> dict[str, Any]:
    unique_dates = sorted({pd.Timestamp(date).normalize() for date in dates})
    if not unique_dates:
        return {"vt_symbol": vt_symbol, "status": "no_dates", "rows": 0, "target_dates": 0}

    username, password = _require_credentials()
    tq_symbol = _to_tqsdk_symbol(vt_symbol)
    start_dt = unique_dates[0] + pd.Timedelta(hours=14, minutes=45)
    end_dt = unique_dates[-1] + pd.Timedelta(hours=15, minutes=10)
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "extract_start": start_dt,
        "extract_end": end_dt,
        "target_dates": int(len(unique_dates)),
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    started = time.time()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            bar = klines.iloc[-1].to_dict()
            bar_id = int(bar.get("id", -1))
            if bar_id in seen:
                continue
            seen.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    bars = pd.DataFrame(rows)
    if not bars.empty:
        write_path = _raw_path(WRITE_RAW_ROOT, vt_symbol)
        write_path.parent.mkdir(parents=True, exist_ok=True)
        if write_path.exists():
            old = pd.read_csv(write_path, encoding="utf-8-sig")
            if not old.empty:
                old["bar_datetime"] = pd.to_datetime(old["bar_datetime"], errors="coerce").dt.tz_localize(None)
                bars = pd.concat([old, bars], ignore_index=True)
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last").sort_values(["vt_symbol", "bar_datetime"])
        bars.to_csv(write_path, index=False, encoding="utf-8-sig")

    if status["status"] == "unknown":
        status["status"] = "extracted" if len(bars) else "empty"
    status["rows"] = int(len(bars))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status


class DateSymbolProxyEngine(SameDayCloseBacktestingEngine):
    """Same-day engine that fills every order at the fixed date/symbol proxy price."""

    def __init__(self, proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]]) -> None:
        super().__init__()
        self.proxy_map = proxy_map
        self.proxy_usage_rows: list[dict[str, Any]] = []

    def _resolve_trade_price(self, order: Any) -> float:
        date = s451._naive_date(self.datetime)
        key = (date, str(order.vt_symbol))
        proxy = self.proxy_map.get(key)
        fallback = float(order.price)
        if proxy is not None and float(proxy["proxy_price"]) > 0:
            price = float(proxy["proxy_price"])
            source = str(proxy["proxy_source"])
        else:
            price = fallback
            source = "fallback_order_price"
        self.proxy_usage_rows.append(
            {
                "datetime": self.datetime,
                "date": date,
                "vt_symbol": str(order.vt_symbol),
                "direction": s451._direction_text(order.direction),
                "offset": s451._offset_text(order.offset),
                "orderid": str(order.orderid),
                "order_price": fallback,
                "trade_price": price,
                "price_delta": price - fallback,
                "order_volume": float(order.volume),
                "proxy_source": source,
                "proxy_bar_count": np.nan if proxy is None else proxy.get("proxy_bar_count", np.nan),
                "proxy_first_time": "" if proxy is None else proxy.get("proxy_first_time", ""),
                "proxy_last_time": "" if proxy is None else proxy.get("proxy_last_time", ""),
            }
        )
        return price

    def cross_limit_order_on_close(self) -> None:
        for order in list(self.active_limit_orders.values()):
            bar: BarData = self.bars[order.vt_symbol]
            if float(bar.close_price) <= 0:
                continue
            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self.strategy.update_order(order)
            if float(order.price) <= 0:
                continue
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
                price=self._resolve_trade_price(order),
                volume=order.volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )
            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade


def _run_engine(proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]] | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    engine = DateSymbolProxyEngine(proxy_map) if proxy_map is not None else SameDayCloseBacktestingEngine()
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
        raise RuntimeError("engine produced empty daily result")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    usage = pd.DataFrame(getattr(engine, "proxy_usage_rows", []))
    return daily, usage


def _fallback_targets(usage: pd.DataFrame) -> pd.DataFrame:
    if usage.empty or "proxy_source" not in usage.columns:
        return pd.DataFrame(columns=["vt_symbol", "date"])
    fallback = usage[usage["proxy_source"].eq("fallback_order_price")].copy()
    if fallback.empty:
        return pd.DataFrame(columns=["vt_symbol", "date"])
    fallback["date"] = pd.to_datetime(fallback["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    return fallback.dropna(subset=["date", "vt_symbol"])[["vt_symbol", "date"]].drop_duplicates()


def _fill_proxy_map_for_targets(
    proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]],
    targets: pd.DataFrame,
    *,
    allow_fetch: bool,
) -> list[dict[str, Any]]:
    status_rows: list[dict[str, Any]] = []
    if targets.empty:
        return status_rows
    unresolved: dict[str, list[pd.Timestamp]] = {}
    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        date = pd.Timestamp(row.date).normalize()
        key = (date, vt_symbol)
        if key in proxy_map:
            continue
        proxy = _proxy_from_bars(vt_symbol, date)
        if proxy is not None:
            proxy["proxy_source"] = "cached_raw_1455_vwap"
            proxy_map[key] = proxy
            status_rows.append({"vt_symbol": vt_symbol, "date": date, "status": "cached_raw", "message": ""})
        else:
            unresolved.setdefault(vt_symbol, []).append(date)

    if not allow_fetch:
        for vt_symbol, dates in unresolved.items():
            for date in sorted(set(dates)):
                status_rows.append({"vt_symbol": vt_symbol, "date": date, "status": "missing_not_fetched", "message": ""})
        return status_rows

    for vt_symbol, dates in sorted(unresolved.items()):
        status = _extract_symbol_windows(vt_symbol, dates)
        for date in sorted(set(dates)):
            proxy = _proxy_from_bars(vt_symbol, date)
            if proxy is not None:
                proxy["proxy_source"] = "stage452_backfilled_1455_vwap"
                proxy_map[(date, vt_symbol)] = proxy
                row_status = "backfilled"
                message = str(status.get("status", ""))
            else:
                row_status = "still_missing"
                message = str(status.get("message", status.get("status", "")))
            status_rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "date": date,
                    "status": row_status,
                    "message": message,
                    "extract_status": status.get("status", ""),
                    "extract_rows": status.get("rows", 0),
                    "extract_elapsed_seconds": status.get("elapsed_seconds", 0.0),
                }
            )
    return status_rows


def _build_long_daily(baseline: pd.DataFrame, rerun_daily: pd.DataFrame, true_daily: pd.DataFrame) -> pd.DataFrame:
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
    rerun["label"] = "Stage079 same-day engine rerun"
    rows.append(rerun)
    true_path = true_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    true_path["variant"] = TRUE_PATH_VARIANT
    true_path["label"] = "Stage079 14:55 VWAP symbol-date backfilled"
    rows.append(true_path)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _calendar_equity(daily: pd.DataFrame, equity_col: str) -> pd.Series:
    series = daily.sort_values("date").set_index("date")[equity_col].astype(float)
    calendar = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(calendar).ffill()


def _evaluate(long_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    labels = long_daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant, frame in long_daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame, "account_equity")
        summary_rows.append(s450._summary_for(variant, labels.get(variant, variant), equity, ACCOUNT_CAPITAL))
        for horizon_days in (90, 180):
            horizon_rows.append(s450._horizon_for(variant, labels.get(variant, variant), equity, horizon_days))
    summary = pd.DataFrame(summary_rows)
    horizon = pd.DataFrame(horizon_rows)
    score = s450._score_horizons(horizon)
    cost = s451._cost_stress(long_daily)
    gate = s450._gate(summary, horizon, score, cost)
    return summary, horizon, score, cost, gate


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {BASELINE_VARIANT: "#4c78a8", RERUN_VARIANT: "#72b7b2", TRUE_PATH_VARIANT: "#e45756"}
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.2)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_title("Stage079 iterative 14:55 VWAP proxy backfill")
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
    usage: pd.DataFrame,
    backfill_status: pd.DataFrame,
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
    report = [
        "# Stage152 Stage079 14:55 VWAP fallback补齐迭代回放",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行代理覆盖补齐与路径稳定性审计；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 方法：按 `(日期, 合约)` 固定 14:55 VWAP 成交价，不再依赖原订单方向/开平队列；对 fallback 交易先查缓存，再用 TqBacktest 窄窗口补抽取。",
        "- 外部调研判断：事件驱动回测要让成交价进入后续仓位状态；混合真实成交与理论价回退会污染路径结论，因此需要迭代补齐。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最终 fallback 数：`{decision['final_fallback_trade_count']}`。",
        f"- 最终代理成交数：`{decision['final_proxy_matched_trade_count']}`。",
        f"- 迭代次数：`{decision['iterations']}`。",
        f"- 新增/补齐代理键数：`{decision['backfilled_proxy_key_count']}`。",
        f"- 硬约束通过项：`{decision['hard_constraint_pass_variants']}`。",
        f"- 晋级通过项：`{decision['promotion_gate_pass_variants']}`。",
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
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## 补齐状态",
        "",
        _md_table(backfill_status.groupby("status", dropna=False).size().reset_index(name="count")),
        "",
        "## 剩余fallback样本",
        "",
        _md_table(
            usage[usage["proxy_source"].eq("fallback_order_price")][
                ["date", "vt_symbol", "direction", "offset", "order_price", "trade_price", "order_volume"]
            ].head(50)
        ),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。补的是固定执行价格数据，不按收益或坏窗口筛选。",
        "- 运行后过拟合反思：否。没有把补齐结果转成交易规则，仍只作为执行模型审计。",
        "- 运行前继续价值反思：是。Stage151 的 fallback 会造成混合成交价，需要清理。",
        "- 运行后继续价值反思：若补齐后仍硬失败，14:55 VWAP 可部署成交语义应被否决；若恢复硬约束，才允许扩展到 Stage103/xsmom。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    baseline = s451._load_stage079_baseline()
    rerun_daily, _ = _run_engine(None)
    proxy_map = _seed_proxy_map_from_stage149()
    backfill_rows: list[dict[str, Any]] = []
    usage = pd.DataFrame()
    true_daily = pd.DataFrame()
    initial_proxy_key_count = len(proxy_map)

    for iteration in range(1, MAX_ITERATIONS + 1):
        true_daily, usage = _run_engine(proxy_map)
        fallback = _fallback_targets(usage)
        fallback_count = int(len(usage[usage["proxy_source"].eq("fallback_order_price")])) if not usage.empty else 0
        backfill_rows.append(
            {
                "iteration": iteration,
                "vt_symbol": "__iteration__",
                "date": "",
                "status": "iteration_summary",
                "message": f"fallback_trade_count={fallback_count};fallback_key_count={len(fallback)}",
            }
        )
        if fallback.empty:
            break
        before = len(proxy_map)
        rows = _fill_proxy_map_for_targets(proxy_map, fallback, allow_fetch=True)
        for row in rows:
            row["iteration"] = iteration
        backfill_rows.extend(rows)
        if len(proxy_map) == before:
            break

    long_daily = _build_long_daily(baseline, rerun_daily, true_daily)
    summary, horizon, score, cost, gate = _evaluate(long_daily)
    _plot(long_daily)
    backfill_status = pd.DataFrame(backfill_rows)
    proxy_map_frame = pd.DataFrame(list(proxy_map.values()))
    final_fallback = int(usage["proxy_source"].eq("fallback_order_price").sum()) if not usage.empty else 0
    final_proxy = int(len(usage) - final_fallback) if not usage.empty else 0
    hard_pass = gate[gate["hard_constraint_pass"].eq(1)]["variant"].tolist()
    promotion = gate[gate["promotion_gate_pass"].eq(1)]["variant"].tolist()
    true_gate = gate[gate["variant"].eq(TRUE_PATH_VARIANT)].iloc[0]
    decision_label = (
        "iterative_1455_backfill_promote_candidate"
        if TRUE_PATH_VARIANT in promotion
        else (
            "iterative_1455_backfill_hard_pass_need_stage103_replay"
            if int(true_gate["hard_constraint_pass"]) == 1
            else "iterative_1455_backfill_hard_fail_reject_1455_execution"
        )
    )
    decision = {
        "stage": "Stage152",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "iterations": int(
            backfill_status[backfill_status["status"].eq("iteration_summary")]["iteration"].max()
            if not backfill_status.empty
            else 0
        ),
        "initial_proxy_key_count": int(initial_proxy_key_count),
        "final_proxy_key_count": int(len(proxy_map)),
        "backfilled_proxy_key_count": int(len(proxy_map) - initial_proxy_key_count),
        "final_proxy_matched_trade_count": final_proxy,
        "final_fallback_trade_count": final_fallback,
        "true_path_trade_count": int(len(usage)),
        "hard_constraint_pass_variants": hard_pass,
        "promotion_gate_pass_variants": promotion,
        "true_path_failed_hard_constraints": str(true_gate.get("failed_hard_constraints", "")),
        "true_path_score_90d": s451._safe_float(true_gate.get("score_90d")),
        "true_path_score_180d": s451._safe_float(true_gate.get("score_180d")),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "proxy_map": str(PROXY_MAP_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若补齐后仍硬失败，否决14:55 VWAP执行口径；只保留其它预先定义成交语义的审计，不做alpha补丁。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    backfill_status.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    proxy_map_frame.to_csv(PROXY_MAP_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, usage, backfill_status, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
