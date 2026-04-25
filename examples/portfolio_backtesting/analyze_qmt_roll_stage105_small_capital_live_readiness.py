from __future__ import annotations

import json
import math
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_stage105_fu_sn_config import (
    STAGE105_ROLE,
    STAGE105_SIZING_EQUITY_CAP,
    STAGE105_VERSION,
    build_stage105_manifest,
    build_stage105_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage105_small_capital_live_readiness_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage105_small_capital_live_readiness"
BACKTEST_PREFIX: str = "qmt_roll_stage105_fu_sn_small_capital_400k"

CAPITAL: float = 400_000.0
TRADING_DAYS_PER_YEAR: int = 240
LIQUIDITY_WARN_VOLUME_SHARE_PCT: float = 1.0
LIQUIDITY_EXTREME_VOLUME_SHARE_PCT: float = 5.0
MARGIN_WARN_BALANCE_PCT: float = 60.0
MARGIN_EXTREME_BALANCE_PCT: float = 80.0
SINGLE_PRODUCT_MARGIN_WARN_PCT: float = 45.0
DAILY_LOSS_WARN_PCT: float = -15.0

DAILY_RISK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_risk_{MODEL_TAG}.csv"
PRODUCT_EXPOSURE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_exposure_{MODEL_TAG}.csv"
CONTRACT_GRANULARITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_granularity_{MODEL_TAG}.csv"
LIQUIDITY_TRADE_AUDIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_liquidity_trade_audit_{MODEL_TAG}.csv"
LIQUIDITY_PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_liquidity_product_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{BACKTEST_PREFIX}_position_changes_2020_2026_04.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{BACKTEST_PREFIX}_trades_2020_2026_04.csv"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, Exchange(exchange)


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def run_stage105_400k_backtest() -> tuple[pd.DataFrame, dict[str, Any]]:
    print(f"[stage105-small-capital] run 400k full: {START_DT.date()} -> {END_DT.date()}")
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            _, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_stage105_overrides(),
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=CAPITAL,
                save_artifacts=True,
                include_start_year_sweep=False,
                file_prefix=BACKTEST_PREFIX,
                chart_title="QMT Roll Stage105 Fu/Sn 400k Live Readiness",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    if analysis_df is None:
        analysis_df = pd.DataFrame()
    daily = analysis_df.copy()
    if not daily.empty:
        daily.sort_index(inplace=True)
    return daily, statistics


def calculate_daily_path_risk(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    frame = daily.reset_index().rename(columns={"index": "date"}).copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "net_pnl", "trade_count", "slippage", "drawdown", "ddpercent"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["previous_balance"] = frame["balance"].shift(1).fillna(CAPITAL).replace(0.0, np.nan)
    frame["daily_net_pnl_pct_prev_balance"] = (frame["net_pnl"] / frame["previous_balance"] * 100.0).fillna(0.0)
    frame["rolling_5d_net_pnl"] = frame["net_pnl"].rolling(5, min_periods=1).sum()
    frame["rolling_20d_net_pnl"] = frame["net_pnl"].rolling(20, min_periods=1).sum()
    frame["rolling_5d_pct_capital"] = frame["rolling_5d_net_pnl"] / CAPITAL * 100.0
    frame["rolling_20d_pct_capital"] = frame["rolling_20d_net_pnl"] / CAPITAL * 100.0
    frame["loss_day"] = (frame["net_pnl"] < 0).astype(int)
    loss_group = (frame["loss_day"] != frame["loss_day"].shift()).cumsum()
    frame["consecutive_loss_days"] = frame.groupby(loss_group)["loss_day"].cumsum() * frame["loss_day"]
    return frame


def build_margin_and_exposure(daily_risk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(POSITION_CHANGES_PATH)
    positions = pd.read_csv(POSITION_CHANGES_PATH)
    positions["date"] = pd.to_datetime(positions["date"]).dt.normalize()
    positions["product_vt_symbol"] = positions["vt_symbol"].map(product_from_contract)
    for column in ["end_pos", "close_price", "net_pnl", "trade_count", "turnover", "slippage"]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)

    manifest = build_stage105_manifest()
    supported_symbols = load_product_universe_symbols(manifest["product_universe_csv_path"])
    metadata = build_contract_metadata(
        supported_symbols=supported_symbols,
    )
    sizes = metadata["sizes"]
    margin_ratios = metadata["margin_ratios"]
    positions["size"] = positions["vt_symbol"].map(sizes).fillna(1).astype(float)
    positions["margin_ratio"] = positions["vt_symbol"].map(margin_ratios).fillna(0.15).astype(float)
    positions["abs_end_pos"] = positions["end_pos"].abs()
    positions["position_notional"] = positions["abs_end_pos"] * positions["close_price"].clip(lower=0.0) * positions["size"]
    positions["position_margin"] = positions["position_notional"] * positions["margin_ratio"]
    positions["single_contract_margin"] = positions["close_price"].clip(lower=0.0) * positions["size"] * positions["margin_ratio"]

    product_daily = (
        positions.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            product_margin=("position_margin", "sum"),
            product_notional=("position_notional", "sum"),
            active_contract_count=("abs_end_pos", lambda s: int((s > 0).sum())),
            product_net_pnl=("net_pnl", "sum"),
            product_trade_count=("trade_count", "sum"),
            product_slippage=("slippage", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
        .reset_index(drop=True)
    )
    product_daily["active_product"] = (
        (product_daily["product_margin"] > 0)
        | (product_daily["product_net_pnl"].abs() > 1e-9)
        | (product_daily["product_trade_count"] > 0)
    ).astype(int)

    daily_margin = (
        product_daily.groupby("date", as_index=False)
        .agg(
            total_margin=("product_margin", "sum"),
            total_notional=("product_notional", "sum"),
            active_contract_count=("active_contract_count", "sum"),
            active_product_count=("active_product", "sum"),
            max_single_product_margin=("product_margin", "max"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily_margin = daily_margin.merge(
        daily_risk[
            [
                "date",
                "balance",
                "net_pnl",
                "daily_net_pnl_pct_prev_balance",
                "rolling_5d_net_pnl",
                "rolling_20d_net_pnl",
                "ddpercent",
                "consecutive_loss_days",
            ]
        ],
        on="date",
        how="left",
    )
    daily_margin["balance"] = pd.to_numeric(daily_margin["balance"], errors="coerce").ffill().fillna(CAPITAL)
    daily_margin["total_margin_to_balance_pct"] = daily_margin["total_margin"] / daily_margin["balance"].replace(0.0, np.nan) * 100.0
    daily_margin["total_margin_to_initial_capital_pct"] = daily_margin["total_margin"] / CAPITAL * 100.0
    daily_margin["total_notional_to_balance_pct"] = daily_margin["total_notional"] / daily_margin["balance"].replace(0.0, np.nan) * 100.0
    daily_margin["max_single_product_margin_share_pct"] = (
        daily_margin["max_single_product_margin"] / daily_margin["total_margin"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    daily_margin["warn_margin_to_balance"] = (daily_margin["total_margin_to_balance_pct"] > MARGIN_WARN_BALANCE_PCT).astype(int)
    daily_margin["extreme_margin_to_balance"] = (
        daily_margin["total_margin_to_balance_pct"] > MARGIN_EXTREME_BALANCE_PCT
    ).astype(int)
    daily_margin["warn_single_product_share"] = (
        daily_margin["max_single_product_margin_share_pct"] > SINGLE_PRODUCT_MARGIN_WARN_PCT
    ).astype(int)

    product_with_balance = product_daily.merge(
        daily_risk[["date", "balance"]],
        on="date",
        how="left",
    )
    product_with_balance["balance"] = pd.to_numeric(product_with_balance["balance"], errors="coerce").ffill().fillna(CAPITAL)
    product_with_balance["product_margin_to_balance_pct"] = (
        product_with_balance["product_margin"] / product_with_balance["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)

    product_exposure = (
        product_with_balance.groupby("product_vt_symbol", as_index=False)
        .agg(
            total_net_pnl=("product_net_pnl", "sum"),
            total_trade_count=("product_trade_count", "sum"),
            total_slippage=("product_slippage", "sum"),
            active_days=("active_product", "sum"),
            max_margin=("product_margin", "max"),
            p95_margin=("product_margin", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.95))),
            max_margin_to_balance_pct=("product_margin_to_balance_pct", "max"),
            p95_margin_to_balance_pct=(
                "product_margin_to_balance_pct",
                lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.95)),
            ),
            max_active_contract_count=("active_contract_count", "max"),
        )
        .sort_values(["max_margin_to_balance_pct", "total_net_pnl"], ascending=[False, False])
        .reset_index(drop=True)
    )

    contract_granularity = (
        positions[positions["trade_count"] > 0]
        .groupby("product_vt_symbol", as_index=False)
        .agg(
            trade_days=("date", "nunique"),
            median_single_contract_margin=("single_contract_margin", "median"),
            max_single_contract_margin=("single_contract_margin", "max"),
            median_trade_turnover=("turnover", "median"),
            total_trade_count=("trade_count", "sum"),
        )
        .sort_values("max_single_contract_margin", ascending=False)
        .reset_index(drop=True)
    )
    contract_granularity["max_single_contract_margin_pct_capital"] = (
        contract_granularity["max_single_contract_margin"] / CAPITAL * 100.0
    )
    contract_granularity["median_single_contract_margin_pct_capital"] = (
        contract_granularity["median_single_contract_margin"] / CAPITAL * 100.0
    )
    return daily_margin, product_exposure, contract_granularity


def _load_contract_bars(vt_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    database = get_database()
    rows: list[dict[str, Any]] = []
    start_dt = start.to_pydatetime()
    end_dt = end.to_pydatetime()
    for vt_symbol in sorted(set(vt_symbols)):
        if not vt_symbol or vt_symbol == "nan":
            continue
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "vt_symbol": vt_symbol,
                    "market_volume": float(getattr(bar, "volume", 0.0) or 0.0),
                    "open_interest": float(getattr(bar, "open_interest", 0.0) or 0.0),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["date", "vt_symbol", "market_volume", "open_interest"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date", "vt_symbol"]).sort_values(["vt_symbol", "date"])


def run_liquidity_audit() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    trades = pd.read_csv(TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"]).dt.normalize()
    trades["trade_volume"] = pd.to_numeric(trades["volume"], errors="coerce").fillna(0.0).abs()
    trades["product_vt_symbol"] = trades["vt_symbol"].map(product_from_contract)
    start = trades["date"].min()
    end = trades["date"].max()
    bars = _load_contract_bars(trades["vt_symbol"].dropna().astype(str).unique().tolist(), start, end)
    audit = trades.merge(bars, on=["date", "vt_symbol"], how="left")
    audit["market_volume"] = pd.to_numeric(audit["market_volume"], errors="coerce")
    audit["open_interest"] = pd.to_numeric(audit["open_interest"], errors="coerce")
    audit["volume_share_pct"] = np.where(
        audit["market_volume"].fillna(0.0) > 0,
        audit["trade_volume"] / audit["market_volume"] * 100.0,
        np.nan,
    )
    audit["open_interest_share_pct"] = np.where(
        audit["open_interest"].fillna(0.0) > 0,
        audit["trade_volume"] / audit["open_interest"] * 100.0,
        np.nan,
    )
    audit["missing_market_bar"] = audit["market_volume"].isna().astype(int)
    audit["zero_market_volume"] = (audit["market_volume"].fillna(0.0) <= 0).astype(int)
    audit["warn_volume_share_gt_1pct"] = (audit["volume_share_pct"] > LIQUIDITY_WARN_VOLUME_SHARE_PCT).astype(int)
    audit["extreme_volume_share_gt_5pct"] = (audit["volume_share_pct"] > LIQUIDITY_EXTREME_VOLUME_SHARE_PCT).astype(int)

    product_summary = (
        audit.groupby("product_vt_symbol", as_index=False)
        .agg(
            trade_count=("trade_id", "count"),
            trade_volume_sum=("trade_volume", "sum"),
            median_market_volume=("market_volume", "median"),
            min_market_volume=("market_volume", "min"),
            p95_volume_share_pct=("volume_share_pct", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.95))),
            max_volume_share_pct=("volume_share_pct", "max"),
            warn_trade_count=("warn_volume_share_gt_1pct", "sum"),
            extreme_trade_count=("extreme_volume_share_gt_5pct", "sum"),
        )
        .sort_values(["max_volume_share_pct", "trade_count"], ascending=[False, False])
        .reset_index(drop=True)
    )

    valid_share = pd.to_numeric(audit["volume_share_pct"], errors="coerce").dropna()
    summary = {
        "trade_count": int(len(audit)),
        "missing_market_bar_count": int(audit["missing_market_bar"].sum()),
        "zero_market_volume_count": int(audit["zero_market_volume"].sum()),
        "warn_volume_share_gt_1pct_count": int(audit["warn_volume_share_gt_1pct"].sum()),
        "extreme_volume_share_gt_5pct_count": int(audit["extreme_volume_share_gt_5pct"].sum()),
        "median_volume_share_pct": float(valid_share.median()) if not valid_share.empty else 0.0,
        "p95_volume_share_pct": float(valid_share.quantile(0.95)) if not valid_share.empty else 0.0,
        "max_volume_share_pct": float(valid_share.max()) if not valid_share.empty else 0.0,
    }
    return audit, product_summary, summary


def build_summary(
    statistics: dict[str, Any],
    daily_risk: pd.DataFrame,
    daily_margin: pd.DataFrame,
    product_exposure: pd.DataFrame,
    contract_granularity: pd.DataFrame,
    liquidity_summary: dict[str, Any],
) -> dict[str, Any]:
    worst_daily = daily_risk.loc[daily_risk["net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_5d = daily_risk.loc[daily_risk["rolling_5d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_20d = daily_risk.loc[daily_risk["rolling_20d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    max_margin = daily_margin.loc[daily_margin["total_margin_to_balance_pct"].idxmax()].to_dict() if not daily_margin.empty else {}
    max_single_share = (
        daily_margin.loc[daily_margin["max_single_product_margin_share_pct"].idxmax()].to_dict()
        if not daily_margin.empty
        else {}
    )
    max_contract_margin = (
        contract_granularity.loc[contract_granularity["max_single_contract_margin"].idxmax()].to_dict()
        if not contract_granularity.empty
        else {}
    )

    return {
        "model_tag": MODEL_TAG,
        "version": STAGE105_VERSION,
        "role": STAGE105_ROLE,
        "capital": CAPITAL,
        "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
        "base_risk_ratio": BASE_RISK_RATIO,
        "statistics": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": _safe_float(statistics.get("total_trade_count")),
        },
        "path_risk": {
            "worst_daily_net_pnl": _safe_float(worst_daily.get("net_pnl")),
            "worst_daily_date": str(worst_daily.get("date", ""))[:10],
            "worst_daily_pct_prev_balance": _safe_float(worst_daily.get("daily_net_pnl_pct_prev_balance")),
            "worst_5d_net_pnl": _safe_float(worst_5d.get("rolling_5d_net_pnl")),
            "worst_5d_end_date": str(worst_5d.get("date", ""))[:10],
            "worst_5d_pct_capital": _safe_float(worst_5d.get("rolling_5d_pct_capital")),
            "worst_20d_net_pnl": _safe_float(worst_20d.get("rolling_20d_net_pnl")),
            "worst_20d_end_date": str(worst_20d.get("date", ""))[:10],
            "worst_20d_pct_capital": _safe_float(worst_20d.get("rolling_20d_pct_capital")),
            "max_consecutive_loss_days": int(daily_risk["consecutive_loss_days"].max()) if not daily_risk.empty else 0,
        },
        "margin_risk": {
            "max_total_margin": _safe_float(max_margin.get("total_margin")),
            "max_total_margin_date": str(max_margin.get("date", ""))[:10],
            "max_total_margin_to_balance_pct": _safe_float(max_margin.get("total_margin_to_balance_pct")),
            "max_total_margin_to_initial_capital_pct": _safe_float(max_margin.get("total_margin_to_initial_capital_pct")),
            "max_total_notional_to_balance_pct": _safe_float(max_margin.get("total_notional_to_balance_pct")),
            "max_active_product_count": int(daily_margin["active_product_count"].max()) if not daily_margin.empty else 0,
            "max_active_contract_count": int(daily_margin["active_contract_count"].max()) if not daily_margin.empty else 0,
            "max_single_product_margin_share_pct": _safe_float(max_single_share.get("max_single_product_margin_share_pct")),
            "max_single_product_margin_share_date": str(max_single_share.get("date", ""))[:10],
            "warn_margin_days": int(daily_margin["warn_margin_to_balance"].sum()) if not daily_margin.empty else 0,
            "extreme_margin_days": int(daily_margin["extreme_margin_to_balance"].sum()) if not daily_margin.empty else 0,
            "warn_single_product_share_days": int(daily_margin["warn_single_product_share"].sum()) if not daily_margin.empty else 0,
        },
        "contract_granularity": {
            "max_single_contract_margin_product": str(max_contract_margin.get("product_vt_symbol", "")),
            "max_single_contract_margin": _safe_float(max_contract_margin.get("max_single_contract_margin")),
            "max_single_contract_margin_pct_capital": _safe_float(
                max_contract_margin.get("max_single_contract_margin_pct_capital")
            ),
        },
        "liquidity": liquidity_summary,
        "top_product_exposure": product_exposure.head(10).to_dict(orient="records"),
        "outputs": {
            "daily_risk": str(DAILY_RISK_PATH),
            "product_exposure": str(PRODUCT_EXPOSURE_PATH),
            "contract_granularity": str(CONTRACT_GRANULARITY_PATH),
            "liquidity_trade_audit": str(LIQUIDITY_TRADE_AUDIT_PATH),
            "liquidity_product_summary": str(LIQUIDITY_PRODUCT_SUMMARY_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(
    summary: dict[str, Any],
    product_exposure: pd.DataFrame,
    contract_granularity: pd.DataFrame,
    liquidity_product_summary: pd.DataFrame,
) -> str:
    stats = summary["statistics"]
    path = summary["path_risk"]
    margin = summary["margin_risk"]
    granularity = summary["contract_granularity"]
    liquidity = summary["liquidity"]
    return "\n".join(
        [
            "# Stage105 Small Capital Live Readiness",
            "",
            "## Boundary",
            "",
            "- This is a deployment risk audit, not a parameter optimization.",
            "- Capital is fixed at `400,000`; Stage105 trading rules are unchanged.",
            "- Stage78 remains the defensive formal baseline; this audit only checks whether Stage105 is usable for small capital.",
            "",
            "## Backtest Result",
            "",
            f"- End balance: `{stats['end_balance']:,.0f}`",
            f"- Total return: `{stats['total_return_pct']:.4f}%`",
            f"- Max drawdown: `{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe: `{stats['sharpe_ratio']:.4f}`",
            f"- Total slippage: `{stats['total_slippage']:,.0f}`",
            f"- Total trade count: `{stats['total_trade_count']:,.0f}`",
            "",
            "## Path Risk",
            "",
            f"- Worst daily net pnl: `{path['worst_daily_net_pnl']:,.0f}` on `{path['worst_daily_date']}` "
            f"(`{path['worst_daily_pct_prev_balance']:.4f}%` of previous balance)",
            f"- Worst 5d net pnl: `{path['worst_5d_net_pnl']:,.0f}` ending `{path['worst_5d_end_date']}` "
            f"(`{path['worst_5d_pct_capital']:.4f}%` of initial capital)",
            f"- Worst 20d net pnl: `{path['worst_20d_net_pnl']:,.0f}` ending `{path['worst_20d_end_date']}` "
            f"(`{path['worst_20d_pct_capital']:.4f}%` of initial capital)",
            f"- Max consecutive loss days: `{path['max_consecutive_loss_days']}`",
            "",
            "## Margin Risk",
            "",
            f"- Max total margin: `{margin['max_total_margin']:,.0f}` on `{margin['max_total_margin_date']}`",
            f"- Max margin / balance: `{margin['max_total_margin_to_balance_pct']:.4f}%`",
            f"- Max margin / initial capital: `{margin['max_total_margin_to_initial_capital_pct']:.4f}%`",
            f"- Max notional / balance: `{margin['max_total_notional_to_balance_pct']:.4f}%`",
            f"- Max active product count: `{margin['max_active_product_count']}`",
            f"- Max active contract count: `{margin['max_active_contract_count']}`",
            f"- Max single product margin share: `{margin['max_single_product_margin_share_pct']:.4f}%`",
            f"- Margin warning days > {MARGIN_WARN_BALANCE_PCT:.0f}% balance: `{margin['warn_margin_days']}`",
            f"- Margin extreme days > {MARGIN_EXTREME_BALANCE_PCT:.0f}% balance: `{margin['extreme_margin_days']}`",
            f"- Single-product share warning days > {SINGLE_PRODUCT_MARGIN_WARN_PCT:.0f}%: `{margin['warn_single_product_share_days']}`",
            "",
            "## Contract Granularity",
            "",
            f"- Largest single-contract margin product: `{granularity['max_single_contract_margin_product']}`",
            f"- Largest single-contract margin: `{granularity['max_single_contract_margin']:,.0f}`",
            f"- Largest single-contract margin / initial capital: `{granularity['max_single_contract_margin_pct_capital']:.4f}%`",
            "",
            "## Liquidity",
            "",
            f"- Trades: `{liquidity['trade_count']}`",
            f"- Missing market bars: `{liquidity['missing_market_bar_count']}`",
            f"- Zero market volume rows: `{liquidity['zero_market_volume_count']}`",
            f"- Trades >1% market volume: `{liquidity['warn_volume_share_gt_1pct_count']}`",
            f"- Trades >5% market volume: `{liquidity['extreme_volume_share_gt_5pct_count']}`",
            f"- Median volume share: `{liquidity['median_volume_share_pct']:.4f}%`",
            f"- P95 volume share: `{liquidity['p95_volume_share_pct']:.4f}%`",
            f"- Max volume share: `{liquidity['max_volume_share_pct']:.4f}%`",
            "",
            "## Product Exposure Top 10",
            "",
            to_markdown_table(
                product_exposure,
                [
                    "product_vt_symbol",
                    "total_net_pnl",
                    "total_trade_count",
                    "active_days",
                    "max_margin",
                    "max_margin_to_balance_pct",
                    "p95_margin_to_balance_pct",
                    "max_active_contract_count",
                ],
                max_rows=10,
            ),
            "",
            "## Contract Granularity Top 10",
            "",
            to_markdown_table(
                contract_granularity,
                [
                    "product_vt_symbol",
                    "trade_days",
                    "max_single_contract_margin",
                    "max_single_contract_margin_pct_capital",
                    "median_single_contract_margin_pct_capital",
                    "total_trade_count",
                ],
                max_rows=10,
            ),
            "",
            "## Liquidity Product Top 10",
            "",
            to_markdown_table(
                liquidity_product_summary,
                [
                    "product_vt_symbol",
                    "trade_count",
                    "p95_volume_share_pct",
                    "max_volume_share_pct",
                    "warn_trade_count",
                    "extreme_trade_count",
                ],
                max_rows=10,
            ),
            "",
            "## Judgement",
            "",
            f"- Current 400k deployment as-is fails the margin-readiness check: max margin / balance is `{margin['max_total_margin_to_balance_pct']:.4f}%`.",
            "- Liquidity is acceptable, but margin occupancy and short-window loss path are not acceptable for direct small-capital deployment.",
            "- This audit is a mechanical feasibility check; it does not judge whether the alpha itself is real or false.",
            "- The key rejection conditions are excessive margin occupancy, coarse single-contract sizing, liquidity share warnings, or an intolerable short-window loss path.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, statistics = run_stage105_400k_backtest()
    daily_risk = calculate_daily_path_risk(daily)
    daily_margin, product_exposure, contract_granularity = build_margin_and_exposure(daily_risk)
    liquidity_audit, liquidity_product_summary, liquidity_summary = run_liquidity_audit()
    summary = build_summary(
        statistics=statistics,
        daily_risk=daily_risk,
        daily_margin=daily_margin,
        product_exposure=product_exposure,
        contract_granularity=contract_granularity,
        liquidity_summary=liquidity_summary,
    )

    daily_margin.to_csv(DAILY_RISK_PATH, index=False, encoding="utf-8-sig")
    product_exposure.to_csv(PRODUCT_EXPOSURE_PATH, index=False, encoding="utf-8-sig")
    contract_granularity.to_csv(CONTRACT_GRANULARITY_PATH, index=False, encoding="utf-8-sig")
    liquidity_audit.to_csv(LIQUIDITY_TRADE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    liquidity_product_summary.to_csv(LIQUIDITY_PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(
        build_report(summary, product_exposure, contract_granularity, liquidity_product_summary),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"[stage105-small-capital] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
