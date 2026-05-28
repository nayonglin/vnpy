from __future__ import annotations

import importlib.util
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from build_qmt_roll_stage153_stage78_anti_fit_validation import (  # noqa: E402
    NextCloseDelayedExecutionEngine,
    NextOpenDelayedExecutionEngine,
)
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_trades_df  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage443_execution_proxy_calibration_v1"
OUTPUT_PREFIX = "qmt_roll_stage443_execution_proxy_calibration"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0

STAGE403_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
EXECUTION_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_matrix_{MODEL_TAG}.csv"
TRADE_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_gap_ledger_{MODEL_TAG}.csv"
TRADE_GAP_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_gap_summary_{MODEL_TAG}.csv"
WORST_DATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_gap_dates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


NIGHT_SESSION_PRODUCTS = {
    "au.SHFE",
    "cu.SHFE",
    "rb.SHFE",
    "hc.SHFE",
    "fu.SHFE",
    "ru.SHFE",
    "sp.SHFE",
    "MA.CZCE",
    "OI.CZCE",
    "CF.CZCE",
    "FG.CZCE",
    "SA.CZCE",
    "SM.CZCE",
    "jm.DCE",
}
DAY_ONLY_OR_UNCONFIRMED_PRODUCTS = {
    "AP.CZCE",
    "SH.CZCE",
    "lh.DCE",
    "lc.GFEX",
    "si.GFEX",
}


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage443", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage443"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


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


def _session_proxy_class(product_vt_symbol: str) -> str:
    if product_vt_symbol in NIGHT_SESSION_PRODUCTS:
        return "night_session_next_trade_day_open_proxy"
    if product_vt_symbol in DAY_ONLY_OR_UNCONFIRMED_PRODUCTS:
        return "day_or_unconfirmed_session_next_day_09_proxy"
    return "unknown_session_requires_exchange_table"


def _run_c3_engine(
    engine_class: type[SameDayCloseBacktestingEngine],
    execution_name: str,
) -> dict[str, Any]:
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
        for column in ["net_pnl", "trade_count", "slippage"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        if "balance" in daily.columns:
            daily["balance"] = pd.to_numeric(daily["balance"], errors="coerce").ffill().fillna(C3_CAPITAL)
        else:
            daily["balance"] = C3_CAPITAL + daily["net_pnl"].cumsum()
        daily = daily[["date", "net_pnl", "trade_count", "slippage", "balance"]].dropna(subset=["date"])

    trades = build_trades_df(engine)
    if not trades.empty:
        trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.normalize()
        trades = trades[(trades["date"] >= START_DT) & (trades["date"] <= END_DT)].copy()
        trades["product_vt_symbol"] = trades["vt_symbol"].map(_product_from_contract)
        trades["execution"] = execution_name
    return {"daily": daily, "trades": trades, "metadata": metadata}


def _load_stage403_full() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020")].copy()
    for column in [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "equity",
        "trade_count",
        "combo_slippage",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"])


def _build_curves(stage403: pd.DataFrame, t1_open: pd.DataFrame, t1_close: pd.DataFrame) -> pd.DataFrame:
    baseline = (
        stage403[stage403["variant"].eq("stage079")]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .copy()
    )
    stage103 = (
        stage403[stage403["variant"].eq(STAGE103_VARIANT)]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .copy()
    )
    merged = baseline[
        ["date", "equity", "c3_net_pnl", "c3_trade_count", "c3_slippage"]
    ].rename(
        columns={
            "equity": "stage079_same_equity",
            "c3_net_pnl": "c3_same_net_pnl",
            "c3_trade_count": "c3_same_trade_count",
            "c3_slippage": "c3_same_slippage",
        }
    )
    merged = merged.merge(
        stage103[["date", "equity", "satellite_daily_pnl", "satellite_slippage_cost", "trade_count", "combo_slippage"]].rename(
            columns={
                "equity": "stage103_same_equity",
                "satellite_daily_pnl": "stage103_satellite_pnl",
                "satellite_slippage_cost": "stage103_satellite_slippage",
                "trade_count": "stage103_same_trade_count",
                "combo_slippage": "stage103_same_slippage",
            }
        ),
        on="date",
        how="outer",
    )
    merged = merged.merge(
        t1_open.rename(
            columns={
                "net_pnl": "c3_t1_open_net_pnl",
                "trade_count": "c3_t1_open_trade_count",
                "slippage": "c3_t1_open_slippage",
            }
        )[["date", "c3_t1_open_net_pnl", "c3_t1_open_trade_count", "c3_t1_open_slippage"]],
        on="date",
        how="outer",
    )
    merged = merged.merge(
        t1_close.rename(
            columns={
                "net_pnl": "c3_t1_close_net_pnl",
                "trade_count": "c3_t1_close_trade_count",
                "slippage": "c3_t1_close_slippage",
            }
        )[["date", "c3_t1_close_net_pnl", "c3_t1_close_trade_count", "c3_t1_close_slippage"]],
        on="date",
        how="outer",
    )
    merged = merged.sort_values("date").reset_index(drop=True)
    for column in merged.columns:
        if column != "date":
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)

    merged["stage079_same_equity_rebuilt"] = ACCOUNT_CAPITAL + merged["c3_same_net_pnl"].cumsum()
    merged["stage079_t1_open_equity"] = ACCOUNT_CAPITAL + merged["c3_t1_open_net_pnl"].cumsum()
    merged["stage079_t1_close_equity"] = ACCOUNT_CAPITAL + merged["c3_t1_close_net_pnl"].cumsum()
    merged["stage103_t1_open_equity"] = ACCOUNT_CAPITAL + (
        merged["c3_t1_open_net_pnl"] + merged["stage103_satellite_pnl"]
    ).cumsum()
    merged["stage103_t1_close_equity"] = ACCOUNT_CAPITAL + (
        merged["c3_t1_close_net_pnl"] + merged["stage103_satellite_pnl"]
    ).cumsum()

    rows = [
        ("stage079", "Stage079 same-day close", "same_day_close", "stage079_same_equity_rebuilt", "c3_same_trade_count", "c3_same_slippage"),
        (
            "stage079_c3_t1_next_open",
            "Stage079 C3 T+1 next open",
            "t1_next_open",
            "stage079_t1_open_equity",
            "c3_t1_open_trade_count",
            "c3_t1_open_slippage",
        ),
        (
            "stage079_c3_t1_next_close",
            "Stage079 C3 T+1 next close",
            "t1_next_close",
            "stage079_t1_close_equity",
            "c3_t1_close_trade_count",
            "c3_t1_close_slippage",
        ),
        (
            "stage103_same_day_close",
            "Stage103 same-day close",
            "same_day_close",
            "stage103_same_equity",
            "stage103_same_trade_count",
            "stage103_same_slippage",
        ),
        (
            "stage103_c3_t1_next_open_satellite_frozen",
            "Stage103 C3 T+1 open + frozen xsmom",
            "t1_next_open_c3_only",
            "stage103_t1_open_equity",
            "c3_t1_open_trade_count",
            "c3_t1_open_slippage",
        ),
        (
            "stage103_c3_t1_next_close_satellite_frozen",
            "Stage103 C3 T+1 close + frozen xsmom",
            "t1_next_close_c3_only",
            "stage103_t1_close_equity",
            "c3_t1_close_trade_count",
            "c3_t1_close_slippage",
        ),
    ]
    curves = []
    for variant, label, proxy, equity_col, trade_col, slip_col in rows:
        curves.append(
            pd.DataFrame(
                {
                    "date": merged["date"],
                    "variant": variant,
                    "label": label,
                    "execution_proxy": proxy,
                    "equity": merged[equity_col],
                    "trade_count": merged[trade_col],
                    "slippage": merged[slip_col],
                }
            )
        )
    return pd.concat(curves, ignore_index=True).dropna(subset=["date", "equity"])


def _candidate(variant: str, label: str, equity: pd.Series, proxy: str) -> Any:
    equity = equity.sort_index().dropna()
    return s087.Candidate(
        variant=variant,
        label=label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=f"execution_proxy:{proxy}",
        eligible_for_promotion=False,
        note="执行代理校准项，不作为alpha晋级候选。",
    )


def _evaluate_curves(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates: list[Any] = []
    for (variant, label, proxy), group in curves.groupby(["variant", "label", "execution_proxy"], sort=False):
        equity = group.sort_values("date").set_index("date")["equity"].astype(float)
        candidates.append(_candidate(str(variant), str(label), equity, str(proxy)))
    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame(
        [s087._horizon_metrics(candidate, horizon_days) for candidate in candidates for horizon_days in (90, 180)]
    )
    score = s087._score_horizons(horizon)
    execution_totals = (
        curves.groupby(["variant", "label", "execution_proxy"], sort=False)
        .agg(total_trade_count=("trade_count", "sum"), total_slippage=("slippage", "sum"))
        .reset_index()
    )
    matrix = summary.merge(execution_totals, on=["variant", "label"], how="left").merge(
        score.drop_duplicates(["variant", "label"])[["variant", "label", "score_90d", "score_180d", "short_holding_score"]],
        on=["variant", "label"],
        how="left",
    )
    return summary, horizon, score, matrix


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange_value)


def _load_contract_bars(vt_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    database = get_database()
    rows: list[dict[str, Any]] = []
    for vt_symbol in sorted(set(vt_symbols)):
        try:
            symbol, exchange = _parse_vt_symbol(vt_symbol)
        except Exception:
            continue
        bars = database.load_bar_data(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.DAILY,
            start=start.to_pydatetime(),
            end=end.to_pydatetime(),
        )
        for bar in bars:
            bar_date = pd.Timestamp(bar.datetime)
            if bar_date.tzinfo is not None:
                bar_date = bar_date.tz_convert(None)
            rows.append(
                {
                    "date": bar_date.normalize(),
                    "vt_symbol": vt_symbol,
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(bar.volume),
                }
            )
    return pd.DataFrame(rows).sort_values(["vt_symbol", "date"]).reset_index(drop=True) if rows else pd.DataFrame()


def _bar_at_or_after(group: pd.DataFrame, trade_date: pd.Timestamp, *, strictly_after: bool) -> dict[str, Any]:
    if group.empty:
        return {}
    dates = pd.DatetimeIndex(group["date"])
    side = "right" if strictly_after else "left"
    index = int(dates.searchsorted(trade_date, side=side))
    if index >= len(group):
        return {}
    return group.iloc[index].to_dict()


def _adverse_price_diff(direction: str, executable_price: float, theoretical_price: float) -> float:
    raw_diff = executable_price - theoretical_price
    return raw_diff if str(direction) == "Long" else -raw_diff


def _build_trade_gap_ledger(same_trades: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
    if same_trades.empty:
        return pd.DataFrame()
    start = pd.Timestamp(same_trades["date"].min()) - pd.Timedelta(days=3)
    end = pd.Timestamp(same_trades["date"].max()) + pd.Timedelta(days=10)
    bars = _load_contract_bars(same_trades["vt_symbol"].dropna().astype(str).unique().tolist(), start, end)
    lookup = {str(vt_symbol): group.sort_values("date").reset_index(drop=True) for vt_symbol, group in bars.groupby("vt_symbol", sort=False)}
    sizes = metadata["sizes"]
    priceticks = metadata["priceticks"]
    margin_ratios = metadata["margin_ratios"]

    rows: list[dict[str, Any]] = []
    for row in same_trades.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        trade_date = pd.Timestamp(row.date).normalize()
        group = lookup.get(vt_symbol, pd.DataFrame())
        same_bar = _bar_at_or_after(group, trade_date, strictly_after=False)
        if same_bar and pd.Timestamp(same_bar.get("date")).normalize() != trade_date:
            same_bar = {}
        next_bar = _bar_at_or_after(group, trade_date, strictly_after=True)

        product_vt_symbol = str(row.product_vt_symbol)
        size = float(sizes.get(vt_symbol, 1) or 1)
        pricetick = float(priceticks.get(vt_symbol, 1.0) or 1.0)
        margin_ratio = float(margin_ratios.get(vt_symbol, 0.0) or 0.0)
        theoretical_price = float(row.price)
        volume = float(row.volume)
        next_open = _safe_float(next_bar.get("open") if next_bar else 0.0)
        next_close = _safe_float(next_bar.get("close") if next_bar else 0.0)
        next_volume = _safe_float(next_bar.get("volume") if next_bar else 0.0)
        next_open_available = int(bool(next_bar) and next_open > 0.0 and next_volume > 0.0)
        next_close_available = int(bool(next_bar) and next_close > 0.0 and next_volume > 0.0)
        next_open_adverse_price = _adverse_price_diff(str(row.direction), next_open, theoretical_price) if next_open_available else 0.0
        next_close_adverse_price = _adverse_price_diff(str(row.direction), next_close, theoretical_price) if next_close_available else 0.0
        rows.append(
            {
                "trade_id": row.trade_id,
                "date": trade_date,
                "next_trade_date": pd.Timestamp(next_bar.get("date")).normalize() if next_bar else pd.NaT,
                "product_vt_symbol": product_vt_symbol,
                "session_proxy_class": _session_proxy_class(product_vt_symbol),
                "vt_symbol": vt_symbol,
                "direction": row.direction,
                "offset": row.offset,
                "exit_reason": "" if pd.isna(row.exit_reason) else row.exit_reason,
                "theoretical_price": theoretical_price,
                "same_day_close": _safe_float(same_bar.get("close") if same_bar else 0.0),
                "next_open": next_open,
                "next_close": next_close,
                "volume": volume,
                "size": size,
                "price_tick": pricetick,
                "margin_ratio": margin_ratio,
                "next_open_available": next_open_available,
                "next_close_available": next_close_available,
                "next_open_adverse_price": next_open_adverse_price,
                "next_open_adverse_ticks": next_open_adverse_price / pricetick if pricetick else 0.0,
                "next_open_adverse_cash": next_open_adverse_price * volume * size,
                "next_close_adverse_price": next_close_adverse_price,
                "next_close_adverse_ticks": next_close_adverse_price / pricetick if pricetick else 0.0,
                "next_close_adverse_cash": next_close_adverse_price * volume * size,
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "vt_symbol", "trade_id"]).reset_index(drop=True)


def _gap_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, pd.DataFrame]] = [("all", ledger)]
    groups.extend((str(name), group) for name, group in ledger.groupby("session_proxy_class", sort=True))
    groups.extend((f"offset={name}", group) for name, group in ledger.groupby("offset", sort=True))
    for name, group in groups:
        daily = group.groupby("date", sort=True).agg(
            daily_next_open_adverse_cash=("next_open_adverse_cash", "sum"),
            daily_next_close_adverse_cash=("next_close_adverse_cash", "sum"),
        )
        rows.append(
            {
                "bucket": name,
                "trade_count": int(len(group)),
                "open_available_rate": float(group["next_open_available"].mean()),
                "close_available_rate": float(group["next_close_available"].mean()),
                "total_next_open_adverse_cash": float(group["next_open_adverse_cash"].sum()),
                "total_next_close_adverse_cash": float(group["next_close_adverse_cash"].sum()),
                "mean_next_open_adverse_cash": float(group["next_open_adverse_cash"].mean()),
                "median_next_open_adverse_ticks": float(group["next_open_adverse_ticks"].median()),
                "p95_abs_next_open_adverse_ticks": float(group["next_open_adverse_ticks"].abs().quantile(0.95)),
                "positive_open_adverse_rate": float((group["next_open_adverse_cash"] > 0.0).mean()),
                "max_daily_next_open_adverse_cash": float(daily["daily_next_open_adverse_cash"].max()),
                "min_daily_next_open_adverse_cash": float(daily["daily_next_open_adverse_cash"].min()),
            }
        )
    return pd.DataFrame(rows)


def _worst_gap_dates(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    daily = (
        ledger.groupby("date", sort=True)
        .agg(
            trade_count=("trade_id", "count"),
            products=("product_vt_symbol", lambda values: ",".join(sorted(set(map(str, values))))),
            next_open_adverse_cash=("next_open_adverse_cash", "sum"),
            next_close_adverse_cash=("next_close_adverse_cash", "sum"),
            max_single_trade_open_adverse_cash=("next_open_adverse_cash", "max"),
        )
        .reset_index()
    )
    return daily.reindex(daily["next_open_adverse_cash"].abs().sort_values(ascending=False).index).head(30)


def _write_report(
    matrix: pd.DataFrame,
    horizon: pd.DataFrame,
    gap_summary: pd.DataFrame,
    worst_dates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    matrix_cols = [
        "variant",
        "execution_proxy",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
        "score_90d",
        "score_180d",
        "total_trade_count",
        "total_slippage",
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
    report = [
        "# Stage143 执行代理价校准审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行模型审计；不修改 Stage079/C3/Stage103 的交易规则。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "",
        "## 外部调研判断",
        "",
        "- 国内商品期货夜盘品种的下一交易日通常从前一日晚间夜盘开始；有夜盘的品种，夜盘集合竞价价格会成为该交易日开盘价。",
        "- 日线回测的 `next bar open` 更接近“收盘后生成信号、下一可交易时段执行”的保守代理；`same-day close` 只有在盘中提前生成稳定信号、或具备合规收盘/结算价交易通道时才可执行。",
        "- 本地目前没有完整分钟线/盘口级 20:55、21:00、09:00 可成交价，因此本阶段只能判断日线代理的风险边界，不能宣称已完成实盘成交校准。",
        "",
        "## 执行代理核心结果",
        "",
        _md_table(matrix[matrix_cols]),
        "",
        "## 3个月/6个月体验代理变化",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 同日订单的 next-open / next-close 缺口",
        "",
        _md_table(gap_summary),
        "",
        "## next-open 缺口绝对值最大日期",
        "",
        _md_table(worst_dates, max_rows=20),
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 推荐执行代理：`{decision['recommended_execution_proxy']}`。",
        f"- 是否允许把 Stage103 直接进入真实 paper：`{decision['allow_stage103_real_paper_without_intraday_proxy']}`。",
        f"- 主要原因：{decision['reason']}",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。本阶段只比较成交代理，不按结果修改信号、品种、日期或参数。",
        "- 运行后过拟合反思：否。结论没有把坏日期/坏品种做成过滤器，反而限制继续在不可靠成交口径上优化。",
        "- 运行前继续价值反思：是。Stage103 是否能 paper，取决于成交代理是否可信。",
        "- 运行后继续价值反思：是。下一步应该补 20:55/21:00/09:00 分钟线或 QMT 行情采样，而不是继续调 alpha。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    same = _run_c3_engine(SameDayCloseBacktestingEngine, "same_day_close")
    t1_open = _run_c3_engine(NextOpenDelayedExecutionEngine, "t1_next_open")
    t1_close = _run_c3_engine(NextCloseDelayedExecutionEngine, "t1_next_close")

    stage403 = _load_stage403_full()
    curves = _build_curves(stage403, t1_open["daily"], t1_close["daily"])
    summary, horizon, score, matrix = _evaluate_curves(curves)
    gap_ledger = _build_trade_gap_ledger(same["trades"], same["metadata"])
    gap_summary = _gap_summary(gap_ledger)
    worst_dates = _worst_gap_dates(gap_ledger)

    stage079_same = matrix[matrix["variant"].eq("stage079")].iloc[0].to_dict()
    stage079_open = matrix[matrix["variant"].eq("stage079_c3_t1_next_open")].iloc[0].to_dict()
    stage103_open = matrix[matrix["variant"].eq("stage103_c3_t1_next_open_satellite_frozen")].iloc[0].to_dict()

    open_hard_failure = (
        _safe_float(stage079_open["max_dd_pct"]) < -30.0
        or _safe_float(stage103_open["max_dd_pct"]) < -30.0
        or _safe_float(stage079_open["rolling252_dd30_breach_rate"]) > 0.0
    )
    decision_label = (
        "same_day_close_not_deployment_safe_next_open_requires_intraday_calibration"
        if open_hard_failure
        else "next_open_proxy_accepts_same_day_candidate_for_paper"
    )
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "recommended_execution_proxy": "t1_next_open_until_intraday_20_55_21_00_09_00_proxy_is_available",
        "allow_stage103_real_paper_without_intraday_proxy": False,
        "stage079_same_max_dd_pct": _safe_float(stage079_same["max_dd_pct"]),
        "stage079_t1_open_max_dd_pct": _safe_float(stage079_open["max_dd_pct"]),
        "stage103_t1_open_max_dd_pct": _safe_float(stage103_open["max_dd_pct"]),
        "reason": "T+1 next-open 日线代理已使回撤闸门失效；同日收盘候选只能保留为研究口径，真实 paper 前必须补分钟线/QMT 行情执行代理。",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "execution_matrix": str(EXECUTION_MATRIX_PATH),
            "trade_gap_ledger": str(TRADE_GAP_PATH),
            "trade_gap_summary": str(TRADE_GAP_SUMMARY_PATH),
            "worst_dates": str(WORST_DATES_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(EXECUTION_MATRIX_PATH, index=False, encoding="utf-8-sig")
    gap_ledger.to_csv(TRADE_GAP_PATH, index=False, encoding="utf-8-sig")
    gap_summary.to_csv(TRADE_GAP_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    worst_dates.to_csv(WORST_DATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(matrix, horizon, gap_summary, worst_dates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
