from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from analyze_qmt_roll_stage346_xsmom_integer_feasibility import _build_price_frame  # noqa: E402
from build_qmt_roll_stage153_stage78_anti_fit_validation import NextOpenDelayedExecutionEngine  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df, build_trades_df  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage442_t1_execution_gap_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage442_t1_execution_gap_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_attribution_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_attribution_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_date_delta_{MODEL_TAG}.csv"
DRAWDOWN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_periods_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return f"{letters or symbol}.{exchange}"


def _path_stats(equity: pd.Series) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").dropna().astype(float)
    if equity.empty:
        return {
            "end_equity": ACCOUNT_CAPITAL,
            "total_return_pct": 0.0,
            "max_dd_pct": 0.0,
            "sharpe": 0.0,
            "ulcer_pct": 0.0,
        }
    nav = equity / ACCOUNT_CAPITAL
    dd = nav / nav.cummax() - 1.0
    ret = nav.pct_change().dropna()
    std = float(ret.std(ddof=1)) if len(ret) > 1 else 0.0
    sharpe = float(ret.mean() / std * math.sqrt(252.0)) if std > 0 else 0.0
    ulcer = float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float) * 100.0, 0.0)))))
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_pct": float(dd.min() * 100.0),
        "sharpe": sharpe,
        "ulcer_pct": ulcer,
    }


def _run_c3_engine(engine_class: type[SameDayCloseBacktestingEngine], execution_name: str) -> dict[str, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    engine = engine_class()
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
    if daily_df is None:
        daily = pd.DataFrame(columns=["date", "net_pnl", "trade_count", "slippage", "balance"])
    else:
        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())]
        daily = daily.reset_index().rename(columns={"index": "date"})
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        daily["net_pnl"] = pd.to_numeric(daily.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
        daily["trade_count"] = pd.to_numeric(daily.get("trade_count", 0.0), errors="coerce").fillna(0.0)
        daily["slippage"] = pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0)
        if "balance" in daily.columns:
            daily["balance"] = pd.to_numeric(daily["balance"], errors="coerce").ffill().fillna(C3_CAPITAL)
        else:
            daily["balance"] = C3_CAPITAL + daily["net_pnl"].cumsum()
        daily = daily[["date", "net_pnl", "trade_count", "slippage", "balance"]].dropna(subset=["date"])

    positions = build_positions_df(engine)
    if not positions.empty:
        positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
        positions = positions[(positions["date"] >= START_DT) & (positions["date"] <= END_DT)].copy()
        positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_contract)
        positions["execution"] = execution_name
        for column in ["start_pos", "end_pos", "pos_change", "close_price", "net_pnl", "holding_pnl", "trading_pnl", "trade_count"]:
            positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)

    trades = build_trades_df(engine)
    if not trades.empty:
        trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.normalize()
        trades = trades[(trades["date"] >= START_DT) & (trades["date"] <= END_DT)].copy()
        trades["product_vt_symbol"] = trades["vt_symbol"].map(_product_from_contract)
        trades["execution"] = execution_name
    return {"daily": daily, "positions": positions, "trades": trades, "metadata": metadata}


def _active_roll_days(positions: pd.DataFrame, execution: str) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["date", f"{execution}_active_roll_products", f"{execution}_active_roll_count"])
    active = positions[positions["end_pos"].abs().gt(1e-9)].copy()
    if active.empty:
        return pd.DataFrame(columns=["date", f"{execution}_active_roll_products", f"{execution}_active_roll_count"])
    active_strings = (
        active.groupby(["product_vt_symbol", "date"])["vt_symbol"]
        .apply(lambda values: ",".join(sorted(set(map(str, values)))))
        .reset_index(name="active_contracts")
        .sort_values(["product_vt_symbol", "date"])
    )
    active_strings["prev_active_contracts"] = active_strings.groupby("product_vt_symbol")["active_contracts"].shift(1)
    changed = active_strings[
        active_strings["prev_active_contracts"].notna()
        & active_strings["active_contracts"].ne(active_strings["prev_active_contracts"])
    ].copy()
    if changed.empty:
        return pd.DataFrame(columns=["date", f"{execution}_active_roll_products", f"{execution}_active_roll_count"])
    result = (
        changed.groupby("date")["product_vt_symbol"]
        .apply(lambda values: ",".join(sorted(set(map(str, values)))))
        .reset_index(name=f"{execution}_active_roll_products")
    )
    result[f"{execution}_active_roll_count"] = result[f"{execution}_active_roll_products"].map(
        lambda text: 0 if not text else len(str(text).split(","))
    )
    return result


def _universe_roll_calendar() -> pd.DataFrame:
    prices = _build_price_frame()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices = prices.sort_values(["product_vt_symbol", "date"])
    prices["prev_contract"] = prices.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    rolls = prices[
        prices["prev_contract"].notna()
        & prices["main_contract_vt"].notna()
        & prices["main_contract_vt"].ne(prices["prev_contract"])
    ].copy()
    if rolls.empty:
        return pd.DataFrame(columns=["date", "universe_roll_products", "universe_roll_count"])
    result = (
        rolls.groupby("date")["product_vt_symbol"]
        .apply(lambda values: ",".join(sorted(set(map(str, values)))))
        .reset_index(name="universe_roll_products")
    )
    result["universe_roll_count"] = result["universe_roll_products"].map(lambda text: len(str(text).split(",")))
    return result


def _contract_delta(same_pos: pd.DataFrame, t1_pos: pd.DataFrame) -> pd.DataFrame:
    columns = ["date", "vt_symbol", "product_vt_symbol", "net_pnl", "holding_pnl", "trading_pnl", "trade_count", "start_pos", "end_pos"]
    same = same_pos[columns].copy() if not same_pos.empty else pd.DataFrame(columns=columns)
    t1 = t1_pos[columns].copy() if not t1_pos.empty else pd.DataFrame(columns=columns)
    same = same.rename(
        columns={
            "net_pnl": "same_net_pnl",
            "holding_pnl": "same_holding_pnl",
            "trading_pnl": "same_trading_pnl",
            "trade_count": "same_contract_trade_count",
            "start_pos": "same_start_pos",
            "end_pos": "same_end_pos",
        }
    )
    t1 = t1.rename(
        columns={
            "net_pnl": "t1_net_pnl",
            "holding_pnl": "t1_holding_pnl",
            "trading_pnl": "t1_trading_pnl",
            "trade_count": "t1_contract_trade_count",
            "start_pos": "t1_start_pos",
            "end_pos": "t1_end_pos",
        }
    )
    merged = same.merge(t1, on=["date", "vt_symbol", "product_vt_symbol"], how="outer")
    for column in merged.columns:
        if column not in {"date", "vt_symbol", "product_vt_symbol"}:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["net_pnl_delta"] = merged["t1_net_pnl"] - merged["same_net_pnl"]
    merged["holding_pnl_delta"] = merged["t1_holding_pnl"] - merged["same_holding_pnl"]
    merged["trading_pnl_delta"] = merged["t1_trading_pnl"] - merged["same_trading_pnl"]
    merged["abs_net_pnl_delta"] = merged["net_pnl_delta"].abs()
    return merged.sort_values(["date", "vt_symbol"])


def _build_daily_attribution(
    same_daily: pd.DataFrame,
    t1_daily: pd.DataFrame,
    same_pos: pd.DataFrame,
    t1_pos: pd.DataFrame,
    same_trades: pd.DataFrame,
    t1_trades: pd.DataFrame,
    contract_delta: pd.DataFrame,
) -> pd.DataFrame:
    daily = same_daily.rename(
        columns={"net_pnl": "same_net_pnl", "trade_count": "same_trade_count", "slippage": "same_slippage", "balance": "same_c3_balance"}
    ).merge(
        t1_daily.rename(
            columns={"net_pnl": "t1_net_pnl", "trade_count": "t1_trade_count", "slippage": "t1_slippage", "balance": "t1_c3_balance"}
        ),
        on="date",
        how="outer",
    )
    for column in ["same_net_pnl", "same_trade_count", "same_slippage", "t1_net_pnl", "t1_trade_count", "t1_slippage"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["same_stage079_equity"] = ACCOUNT_CAPITAL + daily["same_net_pnl"].cumsum()
    daily["t1_stage079_equity"] = ACCOUNT_CAPITAL + daily["t1_net_pnl"].cumsum()
    daily["net_pnl_delta"] = daily["t1_net_pnl"] - daily["same_net_pnl"]
    daily["equity_delta"] = daily["t1_stage079_equity"] - daily["same_stage079_equity"]

    for prefix, pos in [("same", same_pos), ("t1", t1_pos)]:
        if pos.empty:
            agg = pd.DataFrame(columns=["date", f"{prefix}_active_contract_count", f"{prefix}_active_product_count", f"{prefix}_abs_end_pos_sum"])
        else:
            active = pos[pos["end_pos"].abs().gt(1e-9)].copy()
            agg = (
                active.groupby("date")
                .agg(
                    **{
                        f"{prefix}_active_contract_count": ("vt_symbol", "nunique"),
                        f"{prefix}_active_product_count": ("product_vt_symbol", "nunique"),
                        f"{prefix}_abs_end_pos_sum": ("end_pos", lambda values: float(np.abs(values).sum())),
                    }
                )
                .reset_index()
            )
        daily = daily.merge(agg, on="date", how="left")

    for prefix, trades in [("same", same_trades), ("t1", t1_trades)]:
        if trades.empty:
            agg = pd.DataFrame(columns=["date", f"{prefix}_actual_trade_rows", f"{prefix}_actual_trade_volume"])
        else:
            agg = (
                trades.groupby("date")
                .agg(
                    **{
                        f"{prefix}_actual_trade_rows": ("trade_id", "count"),
                        f"{prefix}_actual_trade_volume": ("volume", "sum"),
                    }
                )
                .reset_index()
            )
        daily = daily.merge(agg, on="date", how="left")

    if contract_delta.empty:
        contract_agg = pd.DataFrame(columns=["date", "contract_abs_delta_sum", "contract_negative_delta_sum", "contract_positive_delta_sum"])
    else:
        contract_agg = (
            contract_delta.groupby("date")
            .agg(
                contract_abs_delta_sum=("abs_net_pnl_delta", "sum"),
                contract_negative_delta_sum=("net_pnl_delta", lambda values: float(values[values < 0].sum())),
                contract_positive_delta_sum=("net_pnl_delta", lambda values: float(values[values > 0].sum())),
            )
            .reset_index()
        )
    daily = daily.merge(contract_agg, on="date", how="left")
    daily = daily.merge(_universe_roll_calendar(), on="date", how="left")
    daily = daily.merge(_active_roll_days(same_pos, "same"), on="date", how="left")
    daily = daily.merge(_active_roll_days(t1_pos, "t1"), on="date", how="left")

    for column in daily.columns:
        if column.endswith("_count") or column.endswith("_sum") or column.endswith("_rows") or column.endswith("_volume"):
            daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0.0)
    for column in ["universe_roll_products", "same_active_roll_products", "t1_active_roll_products"]:
        if column in daily.columns:
            daily[column] = daily[column].fillna("").astype(str)
    daily["any_universe_roll"] = daily.get("universe_roll_count", 0.0).gt(0).astype(int)
    daily["any_active_roll"] = (
        daily.get("same_active_roll_count", 0.0).gt(0) | daily.get("t1_active_roll_count", 0.0).gt(0)
    ).astype(int)
    daily["any_trade_day"] = (
        daily.get("same_actual_trade_rows", 0.0).gt(0) | daily.get("t1_actual_trade_rows", 0.0).gt(0)
    ).astype(int)
    daily["negative_delta_day"] = daily["net_pnl_delta"].lt(0).astype(int)
    return daily.sort_values("date")


def _bucket_rows(daily: pd.DataFrame) -> pd.DataFrame:
    buckets: list[tuple[str, pd.Series]] = [
        ("all_days", pd.Series(True, index=daily.index)),
        ("negative_delta_days", daily["net_pnl_delta"].lt(0)),
        ("positive_delta_days", daily["net_pnl_delta"].gt(0)),
        ("universe_roll_days", daily["any_universe_roll"].eq(1)),
        ("non_universe_roll_days", daily["any_universe_roll"].eq(0)),
        ("active_roll_days", daily["any_active_roll"].eq(1)),
        ("non_active_roll_days", daily["any_active_roll"].eq(0)),
        ("trade_days", daily["any_trade_day"].eq(1)),
        ("non_trade_days", daily["any_trade_day"].eq(0)),
    ]
    rows: list[dict[str, Any]] = []
    for name, mask in buckets:
        frame = daily[mask].copy()
        if frame.empty:
            rows.append({"bucket": name, "days": 0})
            continue
        rows.append(
            {
                "bucket": name,
                "days": int(len(frame)),
                "delta_sum": float(frame["net_pnl_delta"].sum()),
                "negative_delta_sum": float(frame.loc[frame["net_pnl_delta"].lt(0), "net_pnl_delta"].sum()),
                "positive_delta_sum": float(frame.loc[frame["net_pnl_delta"].gt(0), "net_pnl_delta"].sum()),
                "delta_mean": float(frame["net_pnl_delta"].mean()),
                "delta_min": float(frame["net_pnl_delta"].min()),
                "delta_max": float(frame["net_pnl_delta"].max()),
                "negative_day_count": int(frame["net_pnl_delta"].lt(0).sum()),
                "dd30_day_count_t1_equity": int(((frame["t1_stage079_equity"] / frame["t1_stage079_equity"].cummax()) - 1.0).lt(-0.30).sum()),
            }
        )
    return pd.DataFrame(rows)


def _drawdown_period(equity: pd.Series) -> dict[str, Any]:
    equity = equity.dropna().astype(float)
    high = equity.cummax()
    dd = equity / high - 1.0
    trough = dd.idxmin()
    peak = equity.loc[:trough].idxmax()
    after = equity.loc[trough:]
    recovered = after[after >= equity.loc[peak]]
    recovery = recovered.index[0] if not recovered.empty else pd.NaT
    return {
        "peak_date": pd.Timestamp(peak),
        "trough_date": pd.Timestamp(trough),
        "recovery_date": recovery,
        "peak_equity": float(equity.loc[peak]),
        "trough_equity": float(equity.loc[trough]),
        "max_dd_pct": float(dd.loc[trough] * 100.0),
        "duration_days": int((pd.Timestamp(trough) - pd.Timestamp(peak)).days),
        "recovered": int(not pd.isna(recovery)),
    }


def _product_delta(contract_delta: pd.DataFrame, daily: pd.DataFrame, dd_period: dict[str, Any]) -> pd.DataFrame:
    if contract_delta.empty:
        return pd.DataFrame()
    peak = pd.Timestamp(dd_period["peak_date"])
    trough = pd.Timestamp(dd_period["trough_date"])
    frame = contract_delta.copy()
    frame["in_t1_max_dd_window"] = frame["date"].between(peak, trough).astype(int)
    grouped = (
        frame.groupby("product_vt_symbol")
        .agg(
            total_delta=("net_pnl_delta", "sum"),
            negative_delta_sum=("net_pnl_delta", lambda values: float(values[values < 0].sum())),
            positive_delta_sum=("net_pnl_delta", lambda values: float(values[values > 0].sum())),
            abs_delta_sum=("abs_net_pnl_delta", "sum"),
            max_single_day_loss=("net_pnl_delta", "min"),
            trade_delta_sum=("trading_pnl_delta", "sum"),
            holding_delta_sum=("holding_pnl_delta", "sum"),
            dd_window_delta=("net_pnl_delta", lambda values: float(values[frame.loc[values.index, "in_t1_max_dd_window"].eq(1)].sum())),
            active_days=("date", "nunique"),
        )
        .reset_index()
    )
    grouped["negative_share_of_all_negative_delta"] = grouped["negative_delta_sum"] / abs(
        float(daily.loc[daily["net_pnl_delta"].lt(0), "net_pnl_delta"].sum()) or np.nan
    )
    return grouped.sort_values("negative_delta_sum")


def _summary(same_daily: pd.DataFrame, t1_daily: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    same_equity = pd.Series(ACCOUNT_CAPITAL + same_daily["net_pnl"].cumsum().to_numpy(dtype=float), index=same_daily["date"])
    t1_equity = pd.Series(ACCOUNT_CAPITAL + t1_daily["net_pnl"].cumsum().to_numpy(dtype=float), index=t1_daily["date"])
    rows = []
    for execution, equity, source in [
        ("same_day_close", same_equity, same_daily),
        ("t1_next_open", t1_equity, t1_daily),
    ]:
        stats = _path_stats(equity)
        rows.append(
            {
                "execution": execution,
                **stats,
                "total_net_pnl": float(source["net_pnl"].sum()),
                "total_trade_count": float(source["trade_count"].sum()),
                "total_slippage": float(source["slippage"].sum()),
            }
        )
    rows.append(
        {
            "execution": "t1_minus_same",
            "end_equity": float(t1_equity.iloc[-1] - same_equity.iloc[-1]),
            "total_return_pct": float((t1_equity.iloc[-1] - same_equity.iloc[-1]) / ACCOUNT_CAPITAL * 100.0),
            "max_dd_pct": float(_path_stats(t1_equity)["max_dd_pct"] - _path_stats(same_equity)["max_dd_pct"]),
            "sharpe": float(_path_stats(t1_equity)["sharpe"] - _path_stats(same_equity)["sharpe"]),
            "ulcer_pct": float(_path_stats(t1_equity)["ulcer_pct"] - _path_stats(same_equity)["ulcer_pct"]),
            "total_net_pnl": float(daily["net_pnl_delta"].sum()),
            "total_trade_count": float(t1_daily["trade_count"].sum() - same_daily["trade_count"].sum()),
            "total_slippage": float(t1_daily["slippage"].sum() - same_daily["slippage"].sum()),
        }
    )
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    buckets: pd.DataFrame,
    products: pd.DataFrame,
    contracts: pd.DataFrame,
    drawdowns: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage142 T+1执行缺口归因",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读执行归因；不新增策略规则，不调参数。",
        "- 归因对象：Stage079/C3 同日收盘成交 vs C3 T+1 next open。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 总体差异",
        "",
        _md_table(summary),
        "",
        "## T+1最大回撤区间",
        "",
        _md_table(drawdowns),
        "",
        "## 日期桶归因",
        "",
        _md_table(buckets),
        "",
        "## 负向产品贡献 Top15",
        "",
        _md_table(products.head(15)),
        "",
        "## 负向合约日 Top20",
        "",
        _md_table(contracts.nsmallest(20, "net_pnl_delta")[
            ["date", "vt_symbol", "product_vt_symbol", "same_net_pnl", "t1_net_pnl", "net_pnl_delta", "same_end_pos", "t1_end_pos", "same_contract_trade_count", "t1_contract_trade_count"]
        ]),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只解释 Stage141 的执行差异，不根据最差日筛品种、日期或阈值。",
        "- 若后续要形成交易规则，必须先证明规则来自真实可执行时段或数据工程修正，而不是历史坏窗口补丁。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    same = _run_c3_engine(SameDayCloseBacktestingEngine, "same_day_close")
    t1 = _run_c3_engine(NextOpenDelayedExecutionEngine, "t1_next_open")
    contract_delta = _contract_delta(same["positions"], t1["positions"])
    daily = _build_daily_attribution(
        same["daily"],
        t1["daily"],
        same["positions"],
        t1["positions"],
        same["trades"],
        t1["trades"],
        contract_delta,
    )
    buckets = _bucket_rows(daily)
    t1_equity = pd.Series(daily["t1_stage079_equity"].to_numpy(dtype=float), index=daily["date"])
    same_equity = pd.Series(daily["same_stage079_equity"].to_numpy(dtype=float), index=daily["date"])
    t1_dd = _drawdown_period(t1_equity)
    same_dd = _drawdown_period(same_equity)
    drawdowns = pd.DataFrame(
        [
            {"execution": "same_day_close", **same_dd},
            {"execution": "t1_next_open", **t1_dd},
        ]
    )
    products = _product_delta(contract_delta, daily, t1_dd)
    summary = _summary(same["daily"], t1["daily"], daily)

    trades = pd.concat([same["trades"], t1["trades"]], ignore_index=True) if not same["trades"].empty or not t1["trades"].empty else pd.DataFrame()
    same_roll_delta = float(buckets.loc[buckets["bucket"].eq("active_roll_days"), "delta_sum"].iloc[0]) if "active_roll_days" in set(buckets["bucket"]) else 0.0
    non_roll_delta = float(buckets.loc[buckets["bucket"].eq("non_active_roll_days"), "delta_sum"].iloc[0]) if "non_active_roll_days" in set(buckets["bucket"]) else 0.0
    trade_day_delta = float(buckets.loc[buckets["bucket"].eq("trade_days"), "delta_sum"].iloc[0]) if "trade_days" in set(buckets["bucket"]) else 0.0
    non_trade_day_delta = float(buckets.loc[buckets["bucket"].eq("non_trade_days"), "delta_sum"].iloc[0]) if "non_trade_days" in set(buckets["bucket"]) else 0.0
    top_negative = products.head(5)[["product_vt_symbol", "negative_delta_sum", "dd_window_delta"]].to_dict("records") if not products.empty else []
    decision = {
        "stage": "Stage142",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "t1_gap_is_path_timing_and_position_divergence_not_simple_roll_day_only",
        "t1_max_dd_pct": _safe_float(t1_dd["max_dd_pct"]),
        "t1_max_dd_peak": str(pd.Timestamp(t1_dd["peak_date"]).date()),
        "t1_max_dd_trough": str(pd.Timestamp(t1_dd["trough_date"]).date()),
        "total_t1_minus_same_net_pnl": float(daily["net_pnl_delta"].sum()),
        "active_roll_day_delta_sum": same_roll_delta,
        "non_active_roll_day_delta_sum": non_roll_delta,
        "trade_day_delta_sum": trade_day_delta,
        "non_trade_day_delta_sum": non_trade_day_delta,
        "top_negative_products": top_negative,
        "judgement": "T+1开盘口径不是单纯换月日问题；净收益更高但路径回撤显著恶化，说明延迟成交改变了持仓路径和缺口暴露。下一步应验证更贴近真实夜盘/提交时点的成交代理，而不是按坏日期过滤。",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "daily": str(DAILY_PATH),
            "bucket": str(BUCKET_PATH),
            "product": str(PRODUCT_PATH),
            "contract": str(CONTRACT_PATH),
            "drawdown": str(DRAWDOWN_PATH),
            "trades": str(TRADES_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    buckets.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    products.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    contract_delta.to_csv(CONTRACT_PATH, index=False, encoding="utf-8-sig")
    drawdowns.to_csv(DRAWDOWN_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, buckets, products, contract_delta, drawdowns, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
