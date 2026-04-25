from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_EXPERIMENT_TAG,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "quarterly_wf_liquidity_v1"
OUTPUT_PREFIX: str = f"{OFFICIAL_STAGE78_EXPERIMENT_TAG}_quarterly_walkforward_liquidity"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
LIQUIDITY_TRADE_AUDIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_liquidity_trade_audit_{MODEL_TAG}.csv"
LIQUIDITY_PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_liquidity_product_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE78_FORMAL_TRADES_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_trades_2020_2026_04.csv"
)

TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)
LIQUIDITY_WARN_VOLUME_SHARE_PCT: float = 1.0
LIQUIDITY_EXTREME_VOLUME_SHARE_PCT: float = 5.0


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


def quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if not starts.empty and starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= END_DT]


def summarize_daily_slice(df: pd.DataFrame, *, capital: float) -> dict[str, float]:
    if df.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
        }

    balance = pd.to_numeric(df["balance"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(df.get("net_pnl", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
    daily_return = net_pnl / balance.shift(1).fillna(capital).replace(0.0, np.nan)
    daily_return = daily_return.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    return {
        "end_balance": float(balance.iloc[-1]),
        "total_return_pct": (float(balance.iloc[-1]) - capital) / capital * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(df.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(df.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(df)),
    }


def run_quarterly_walkforward() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strategy_overrides = build_official_stage78_overrides()
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []

    for analysis_start in quarter_starts():
        window_name = f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"
        print(f"[stage78-quarterly] {window_name}: {analysis_start.date()} -> {END_DT.date()}")
        _, analysis_df, _ = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
        )
        if analysis_df is None:
            analysis_df = pd.DataFrame()
        analysis_df = analysis_df.copy()
        if not analysis_df.empty:
            analysis_df.sort_index(inplace=True)

        to_end = summarize_daily_slice(analysis_df, capital=OFFICIAL_STAGE78_CAPITAL)
        quarter_rows.append(
            {
                "window_name": window_name,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
                "horizon": "to_end",
                **to_end,
            }
        )

        for horizon_days in HORIZON_DAYS:
            horizon_df = analysis_df.iloc[:horizon_days].copy()
            horizon = summarize_daily_slice(horizon_df, capital=OFFICIAL_STAGE78_CAPITAL)
            horizon_rows.append(
                {
                    "window_name": window_name,
                    "analysis_start": analysis_start.date().isoformat(),
                    "analysis_end": END_DT.date().isoformat(),
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(horizon["day_count"] >= horizon_days),
                    **horizon,
                }
            )

    quarter_df = pd.DataFrame(quarter_rows)
    horizon_df = pd.DataFrame(horizon_rows)
    complete_mask = horizon_df["complete_horizon"].astype(bool) if "complete_horizon" in horizon_df else pd.Series(False, index=horizon_df.index)
    complete_horizon_df = horizon_df[complete_mask].copy()
    if complete_horizon_df.empty:
        aggregate_df = pd.DataFrame()
    else:
        aggregate_df = (
            complete_horizon_df.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                positive_return_count=("total_return_pct", lambda s: int((s > 0).sum())),
                non_positive_return_count=("total_return_pct", lambda s: int((s <= 0).sum())),
                median_return_pct=("total_return_pct", "median"),
                worst_return_pct=("total_return_pct", "min"),
                best_return_pct=("total_return_pct", "max"),
                median_max_dd_percent=("max_dd_percent", "median"),
                worst_max_dd_percent=("max_dd_percent", "min"),
                median_sharpe=("sharpe_ratio", "median"),
                worst_sharpe=("sharpe_ratio", "min"),
                median_trade_count=("total_trade_count", "median"),
                median_slippage=("total_slippage", "median"),
            )
            .sort_values("horizon")
            .reset_index(drop=True)
        )
        aggregate_df["positive_return_rate_pct"] = (
            aggregate_df["positive_return_count"] / aggregate_df["window_count"].replace(0, np.nan) * 100.0
        ).fillna(0.0)
    return quarter_df, horizon_df, aggregate_df


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
    if not STAGE78_FORMAL_TRADES_PATH.exists():
        raise FileNotFoundError(STAGE78_FORMAL_TRADES_PATH)

    trades = pd.read_csv(STAGE78_FORMAL_TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"]).dt.normalize()
    trades["trade_volume"] = pd.to_numeric(trades["volume"], errors="coerce").fillna(0.0).abs()
    trades["product_vt_symbol"] = trades["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)")[0] + "." + trades["exchange"].astype(str)
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
            max_trade_volume=("trade_volume", "max"),
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


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
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


def build_report(
    quarter_df: pd.DataFrame,
    horizon_df: pd.DataFrame,
    aggregate_df: pd.DataFrame,
    product_summary: pd.DataFrame,
    liquidity_summary: dict[str, Any],
) -> str:
    complete_mask = horizon_df["complete_horizon"].astype(bool) if "complete_horizon" in horizon_df else pd.Series(False, index=horizon_df.index)
    complete_horizon_df = horizon_df[complete_mask].copy()
    weak_horizons = (
        complete_horizon_df.sort_values("total_return_pct").head(12)
        if not complete_horizon_df.empty
        else pd.DataFrame()
    )
    incomplete_horizon_count = int((~complete_mask).sum()) if not horizon_df.empty else 0
    lines = [
        f"# {OFFICIAL_STAGE78_VERSION} Quarterly Walk-Forward + Liquidity Audit",
        "",
        "## Purpose",
        "",
        "- Validate the frozen defensive formal profile under quarterly cold starts.",
        "- Keep liquidity as an audit, not as a new trading filter.",
        "",
        "## Frozen Reference",
        "",
        (
            f"- Full cycle reference: end balance "
            f"`{OFFICIAL_STAGE78_REFERENCE_METRICS['full_2020_2026']['end_balance']:,.0f}`, "
            f"return `{OFFICIAL_STAGE78_REFERENCE_METRICS['full_2020_2026']['total_return_pct']:.4f}%`, "
            f"max drawdown `{OFFICIAL_STAGE78_REFERENCE_METRICS['full_2020_2026']['max_dd_percent']:.4f}%`, "
            f"Sharpe `{OFFICIAL_STAGE78_REFERENCE_METRICS['full_2020_2026']['sharpe_ratio']:.4f}`."
        ),
        "",
        "## Horizon Aggregate",
        "",
        "- Aggregate rows only include complete horizon windows; incomplete late-start windows remain in the detail CSV.",
        f"- Incomplete horizon rows excluded from aggregate: `{incomplete_horizon_count}`",
        "",
        to_markdown_table(
            aggregate_df,
            [
                "horizon",
                "window_count",
                "positive_return_count",
                "positive_return_rate_pct",
                "median_return_pct",
                "worst_return_pct",
                "median_max_dd_percent",
                "worst_max_dd_percent",
                "median_sharpe",
                "worst_sharpe",
            ],
        ),
        "",
        "## Weakest Horizon Starts",
        "",
        to_markdown_table(
            weak_horizons,
            [
                "window_name",
                "analysis_start",
                "horizon",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "total_trade_count",
            ],
            max_rows=12,
        ),
        "",
        "## Liquidity Audit",
        "",
        f"- Trade count: `{liquidity_summary['trade_count']:,}`",
        f"- Missing market bar count: `{liquidity_summary['missing_market_bar_count']:,}`",
        f"- Zero market volume count: `{liquidity_summary['zero_market_volume_count']:,}`",
        f"- Trades above 1% of daily market volume: `{liquidity_summary['warn_volume_share_gt_1pct_count']:,}`",
        f"- Trades above 5% of daily market volume: `{liquidity_summary['extreme_volume_share_gt_5pct_count']:,}`",
        f"- Median volume share: `{liquidity_summary['median_volume_share_pct']:.4f}%`",
        f"- P95 volume share: `{liquidity_summary['p95_volume_share_pct']:.4f}%`",
        f"- Max volume share: `{liquidity_summary['max_volume_share_pct']:.4f}%`",
        "",
        "## Product Liquidity Tail",
        "",
        to_markdown_table(
            product_summary,
            [
                "product_vt_symbol",
                "trade_count",
                "median_market_volume",
                "min_market_volume",
                "p95_volume_share_pct",
                "max_volume_share_pct",
                "warn_trade_count",
                "extreme_trade_count",
            ],
            max_rows=15,
        ),
        "",
        "## Judgement",
        "",
        "- Small capital does not need a full capacity curve yet, but it still needs liquidity sanity checks.",
        "- Quarterly cold-start failures matter more than theoretical capacity at the current capital scale.",
        "- Liquidity should remain an audit layer unless repeated violations concentrate in specific products.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_df, horizon_df, aggregate_df = run_quarterly_walkforward()
    audit_df, product_summary, liquidity_summary = run_liquidity_audit()

    quarter_df.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_df.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate_df.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    audit_df.to_csv(LIQUIDITY_TRADE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(LIQUIDITY_PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "quarter_window_count": int(len(quarter_df)),
        "horizon_row_count": int(len(horizon_df)),
        "horizon_aggregate": aggregate_df.to_dict(orient="records"),
        "liquidity_summary": liquidity_summary,
        "outputs": {
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "horizon_summary": str(HORIZON_SUMMARY_PATH),
            "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
            "liquidity_trade_audit": str(LIQUIDITY_TRADE_AUDIT_PATH),
            "liquidity_product_summary": str(LIQUIDITY_PRODUCT_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        build_report(quarter_df, horizon_df, aggregate_df, product_summary, liquidity_summary),
        encoding="utf-8",
    )
    print(json.dumps({"quarter_windows": len(quarter_df), "horizon_rows": len(horizon_df), **liquidity_summary}, ensure_ascii=False, indent=2))
    print(f"[stage78-quarterly] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
