from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660  # noqa: E402
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage124_full_market_single_product_c9_replay"
MODEL_TAG = f"{STAGE_ID}_v1"

ANALYSIS_START = pd.Timestamp("2020-01-01")
ANALYSIS_END = pd.Timestamp("2026-06-30")
LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
FULL_2022_START = pd.Timestamp("2022-01-01")
FULL_2022_END = pd.Timestamp("2022-12-31")
CAPITAL = float(OFFICIAL_LIVE_CAPITAL)

FULL_MARKET_ELIGIBLE_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)

OUT = ROOT / "research" / "lines" / LINE_ID / "outputs" / STAGE_ID
UNIVERSE_DIR = OUT / "single_product_universes"
DAILY_DIR = OUT / "daily_by_product"
FRAMES_DIR = OUT / "frames_by_product"
STAGES_DIR = ROOT / "research" / "lines" / LINE_ID / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1426_stage124_full_market_single_product_c9_replay.md"

SUMMARY_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_product_summary_{MODEL_TAG}.csv"
PERIOD_SUMMARY_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_product_period_summary_{MODEL_TAG}.csv"
ANNUAL_SUMMARY_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_annual_summary_{MODEL_TAG}.csv"
RUN_STATUS_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_run_status_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_closed_lots_{MODEL_TAG}.csv.gz"
REPORT_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_decision_{MODEL_TAG}.json"
LOSS_WINDOW_CHART_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_loss_window_daily_pnl_bar_{MODEL_TAG}.png"
FULL_SAMPLE_CHART_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_full_sample_daily_pnl_bar_{MODEL_TAG}.png"
SCATTER_PATH = OUT / f"rebuilt_c9_v2_{STAGE_ID}_loss_window_vs_full_sample_scatter_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False, floatfmt=".4f")


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _product_filename(product_vt_symbol: str) -> str:
    return product_vt_symbol.replace(".", "_").replace("/", "_")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _safe_max(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.max()) if len(values) else 0.0


def _load_universe(limit: int | None = None) -> pd.DataFrame:
    if not FULL_MARKET_ELIGIBLE_PATH.exists():
        raise FileNotFoundError(FULL_MARKET_ELIGIBLE_PATH)
    frame = pd.read_csv(FULL_MARKET_ELIGIBLE_PATH)
    frame["eligible"] = pd.to_numeric(frame.get("eligible", 0), errors="coerce").fillna(0).astype(int)
    frame = frame[frame["eligible"].eq(1)].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["is_static_strategy_product"] = (
        pd.to_numeric(frame.get("is_static_strategy_product", 0), errors="coerce").fillna(0).astype(int)
    )
    frame = frame.sort_values(["exchange", "product_vt_symbol"]).reset_index(drop=True)
    if limit is not None:
        frame = frame.head(int(limit)).copy()
    return frame


def _write_single_universe(row: pd.Series, universe: pd.DataFrame) -> Path:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    product = str(row["product_vt_symbol"])
    path = UNIVERSE_DIR / f"{_product_filename(product)}.csv"
    single = universe[universe["product_vt_symbol"].astype(str).eq(product)].copy()
    single.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _metadata(universe_path: Path) -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(universe_path))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _with_legacy_stage372_state() -> dict[str, Any]:
    state = {
        "OFFICIAL_LIVE_PROFILE_NAME": s660.OFFICIAL_LIVE_PROFILE_NAME,
        "OFFICIAL_LIVE_BASE_PROFILE_NAME": s660.OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "OFFICIAL_LIVE_ALIAS": s660.OFFICIAL_LIVE_ALIAS,
        "OFFICIAL_LIVE_CAPITAL": s660.OFFICIAL_LIVE_CAPITAL,
        "OFFICIAL_LIVE_STRATEGY_OVERRIDES": s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    }
    s660.OFFICIAL_LIVE_PROFILE_NAME = s847.LEGACY_STAGE372_PROFILE_NAME
    s660.OFFICIAL_LIVE_BASE_PROFILE_NAME = s847.LEGACY_STAGE372_BASE_PROFILE_NAME
    s660.OFFICIAL_LIVE_ALIAS = "Stage372-20w"
    s660.OFFICIAL_LIVE_CAPITAL = 200_000.0
    s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES = dict(s847.LEGACY_STAGE372_STRATEGY_OVERRIDES)
    return state


def _restore_legacy_state(state: dict[str, Any]) -> None:
    for key, value in state.items():
        setattr(s660, key, value)


def _single_product_profile(metadata: dict[str, Any], product: str, universe_path: Path) -> dict[str, Any]:
    state = _with_legacy_stage372_state()
    try:
        profile = s847._c9_profile(metadata)
    finally:
        _restore_legacy_state(state)
    spec = profile["spec"]
    profile_name = f"stage124_c9_15w_single_{_product_filename(product)}"
    live_overrides = dict(build_official_live_strategy_overrides())
    overrides = {
        **spec.overrides,
        **live_overrides,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": False,
        "ai_product_pool_eligibility_path": "",
        "account_capital": CAPITAL,
        "c3_capital": CAPITAL,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "enable_stage847_half_r_stop_retry": True,
        "stage847_stop_retry_r": s847.STOP_RETRY_R,
        "stage847_max_retries": s847.MAX_RETRIES,
    }
    capital = replace(
        spec.capital,
        variant=profile_name,
        label=f"Stage124 C9/15w single product {product}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage124 full-market single-product replay. "
            "AI product pool filter is disabled and the universe contains exactly one product; "
            "C9 entry/exit/sizing/cost/stop-retry rules are otherwise preserved."
        ),
    )
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_product(row: pd.Series, universe: pd.DataFrame, *, force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    product = str(row["product_vt_symbol"])
    slug = _product_filename(product)
    daily_path = DAILY_DIR / f"{slug}_daily.csv.gz"
    closed_path = FRAMES_DIR / f"{slug}_closed_lots.csv.gz"
    status_path = FRAMES_DIR / f"{slug}_status.json"
    if not force and daily_path.exists() and status_path.exists():
        daily = pd.read_csv(daily_path, encoding="utf-8-sig")
        closed = pd.read_csv(closed_path, encoding="utf-8-sig") if closed_path.exists() else pd.DataFrame()
        status = json.loads(status_path.read_text(encoding="utf-8"))
        return daily, closed, status

    universe_path = _write_single_universe(row, universe)
    metadata = _metadata(universe_path)
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    status: dict[str, Any] = {
        "product_vt_symbol": product,
        "exchange": str(row.get("exchange", "")),
        "product": str(row.get("product", "")),
        "universe_path": str(universe_path),
        "status": "ok",
        "error": "",
    }
    try:
        minute_audit = s901._ensure_c9_minute_bars(metadata)
        status.update({f"minute_{k}": v for k, v in minute_audit.items()})
        s847.START = ANALYSIS_START.normalize()
        s847.END = ANALYSIS_END.normalize()
        profile = _single_product_profile(metadata, product, universe_path)
        combined, frames = s847._run_profile(profile, metadata)
        combined = combined.copy()
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
        combined = combined.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        combined["product_vt_symbol"] = product
        combined["exchange"] = str(row.get("exchange", ""))
        combined["product"] = str(row.get("product", ""))
        combined["is_static_strategy_product"] = int(row.get("is_static_strategy_product", 0))
        combined["profile"] = profile["profile"]
        combined["official_live_version"] = OFFICIAL_LIVE_VERSION
        combined["stage"] = STAGE_ID
        combined["model_tag"] = MODEL_TAG

        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
        if not closed.empty:
            closed["product_vt_symbol"] = product
            closed["exchange"] = str(row.get("exchange", ""))
            closed["product"] = str(row.get("product", ""))
            closed["is_static_strategy_product"] = int(row.get("is_static_strategy_product", 0))
            closed["profile"] = profile["profile"]
            for column in ("entry_date", "exit_date"):
                if column in closed.columns:
                    closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
        status["daily_rows"] = int(len(combined))
        status["closed_lots"] = int(len(closed))
        status["trade_rows"] = int(len(trades))
        combined.to_csv(daily_path, index=False, encoding="utf-8-sig")
        closed.to_csv(closed_path, index=False, encoding="utf-8-sig")
        status_path.write_text(json.dumps(_json_safe(status), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return combined, closed, status
    except Exception as exc:
        status["status"] = "error"
        status["error"] = repr(exc)
        status_path.write_text(json.dumps(_json_safe(status), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        daily = pd.DataFrame(
            [
                {
                    "date": ANALYSIS_END,
                    "product_vt_symbol": product,
                    "exchange": str(row.get("exchange", "")),
                    "product": str(row.get("product", "")),
                    "is_static_strategy_product": int(row.get("is_static_strategy_product", 0)),
                    "account_equity": CAPITAL,
                    "net_pnl": 0.0,
                    "trade_count": 0.0,
                    "slippage": 0.0,
                    "commission": 0.0,
                    "stage124_error": repr(exc),
                }
            ]
        )
        daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
        return daily, pd.DataFrame(), status
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol


def _period_metrics(daily: pd.DataFrame, closed: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, period: str) -> dict[str, Any]:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    span = frame[frame["date"].between(start, end)].copy()
    closed_span = pd.DataFrame()
    if not closed.empty and "exit_date" in closed.columns:
        c = closed.copy()
        c["exit_date"] = pd.to_datetime(c["exit_date"], errors="coerce").dt.normalize()
        closed_span = c[c["exit_date"].between(start, end)].copy()
    return {
        "period": period,
        "period_start": _date_text(start),
        "period_end": _date_text(end),
        "daily_net_pnl": _safe_sum(span, "net_pnl"),
        "daily_trade_count": _safe_sum(span, "trade_count"),
        "daily_slippage": _safe_sum(span, "slippage"),
        "daily_commission": _safe_sum(span, "commission"),
        "active_days": int((pd.to_numeric(span.get("net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).abs() > 1e-12).sum()),
        "closed_lot_count": int(len(closed_span)),
        "closed_lot_realized_pnl": _safe_sum(closed_span, "realized_pnl") if not closed_span.empty else 0.0,
    }


def _summaries(
    daily_frames: list[pd.DataFrame],
    closed_frames: list[pd.DataFrame],
    statuses: list[dict[str, Any]],
    universe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    closed_by_product = {
        str(frame["product_vt_symbol"].iloc[0]): frame.copy()
        for frame in closed_frames
        if not frame.empty and "product_vt_symbol" in frame.columns
    }
    annual_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    for frame in daily_frames:
        if frame.empty or "product_vt_symbol" not in frame.columns:
            continue
        data = frame.copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
        data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        product = str(data["product_vt_symbol"].iloc[0])
        closed = closed_by_product.get(product, pd.DataFrame())
        equity = pd.to_numeric(data.get("account_equity", CAPITAL), errors="coerce").ffill()
        net_pnl = pd.to_numeric(data.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
        dd = _drawdown_pct(equity)
        meta = universe[universe["product_vt_symbol"].astype(str).eq(product)].iloc[0].to_dict()
        year_frame = data.copy()
        year_frame["year"] = year_frame["date"].dt.year
        active_years = 0
        positive_years = 0
        for year, group in year_frame.groupby("year", sort=True):
            year_pnl = _safe_sum(group, "net_pnl")
            trade_count = _safe_sum(group, "trade_count")
            annual_rows.append(
                {
                    "product_vt_symbol": product,
                    "year": int(year),
                    "net_pnl": year_pnl,
                    "trade_count": trade_count,
                    "active_days": int((pd.to_numeric(group.get("net_pnl", 0.0), errors="coerce").fillna(0.0).abs() > 1e-12).sum()),
                }
            )
            if trade_count > 0 or abs(year_pnl) > 1e-9:
                active_years += 1
                positive_years += int(year_pnl > 0.0)
        periods = [
            (LOSS_WINDOW_START, LOSS_WINDOW_END, "loss_window_20220309_20220629"),
            (FULL_2022_START, FULL_2022_END, "full_2022"),
            (ANALYSIS_START, ANALYSIS_END, "full_sample_20200101_20260630"),
        ]
        period_values: dict[str, dict[str, Any]] = {}
        for start, end, period in periods:
            row = _period_metrics(data, closed, start, end, period)
            row.update(
                {
                    "product_vt_symbol": product,
                    "exchange": str(meta.get("exchange", "")),
                    "product": str(meta.get("product", "")),
                    "is_static_strategy_product": int(meta.get("is_static_strategy_product", 0)),
                }
            )
            period_rows.append(row)
            period_values[period] = row
        summary_rows.append(
            {
                "product_vt_symbol": product,
                "exchange": str(meta.get("exchange", "")),
                "product": str(meta.get("product", "")),
                "is_static_strategy_product": int(meta.get("is_static_strategy_product", 0)),
                "status": str(data.get("stage124_error", pd.Series(["ok"])).iloc[0]) if "stage124_error" in data.columns else "ok",
                "actual_start": _date_text(data["date"].iloc[0]) if len(data) else "",
                "actual_end": _date_text(data["date"].iloc[-1]) if len(data) else "",
                "trading_days": int(len(data)),
                "end_equity": float(equity.iloc[-1]) if len(equity) else CAPITAL,
                "total_net_pnl": float(net_pnl.sum()),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0) if len(equity) else 0.0,
                "max_drawdown_pct": float(dd.min()) if len(dd) else 0.0,
                "sharpe": _daily_sharpe(equity),
                "total_trade_count": _safe_sum(data, "trade_count"),
                "total_slippage": _safe_sum(data, "slippage"),
                "total_commission": _safe_sum(data, "commission"),
                "nonzero_pnl_days": int((net_pnl.abs() > 1e-12).sum()),
                "active_year_count": active_years,
                "positive_active_years": positive_years,
                "positive_active_year_rate_pct": positive_years / active_years * 100.0 if active_years else 0.0,
                "max_broker10_margin_to_equity_pct": _safe_max(data, "broker10_margin_to_equity_pct"),
                "loss_window_daily_net_pnl": float(period_values["loss_window_20220309_20220629"]["daily_net_pnl"]),
                "loss_window_closed_lot_realized_pnl": float(period_values["loss_window_20220309_20220629"]["closed_lot_realized_pnl"]),
                "full_2022_daily_net_pnl": float(period_values["full_2022"]["daily_net_pnl"]),
                "full_2022_closed_lot_realized_pnl": float(period_values["full_2022"]["closed_lot_realized_pnl"]),
                "recent_median_volume": float(pd.to_numeric(meta.get("recent_median_volume", 0.0), errors="coerce") or 0.0),
                "recent_bar_coverage_ratio": float(pd.to_numeric(meta.get("recent_bar_coverage_ratio", 0.0), errors="coerce") or 0.0),
                "estimated_margin_per_contract": float(pd.to_numeric(meta.get("estimated_margin_per_contract", 0.0), errors="coerce") or 0.0),
            }
        )
    summary = pd.DataFrame(summary_rows)
    annual = pd.DataFrame(annual_rows)
    period = pd.DataFrame(period_rows)
    run_status = pd.DataFrame(statuses)
    closed_all = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    if not summary.empty:
        summary["full_sample_profitable"] = summary["total_net_pnl"].gt(0.0).astype(int)
        summary["loss_window_profitable"] = summary["loss_window_daily_net_pnl"].gt(0.0).astype(int)
        summary["full_2022_profitable"] = summary["full_2022_daily_net_pnl"].gt(0.0).astype(int)
        summary["material_profitable"] = (
            summary["total_net_pnl"].gt(CAPITAL * 0.10)
            & summary["total_trade_count"].ge(3)
            & summary["positive_active_years"].ge(2)
        ).astype(int)
        summary.sort_values(["full_sample_profitable", "total_net_pnl"], ascending=[False, False], inplace=True)
    if not period.empty:
        period.sort_values(["period", "daily_net_pnl"], ascending=[True, False], inplace=True)
    return summary, period, annual, run_status, closed_all


def _plot_bar(summary: pd.DataFrame, column: str, path: Path, title: str) -> None:
    if summary.empty or column not in summary.columns:
        return
    data = summary[["product_vt_symbol", column]].copy()
    data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    top = data.sort_values(column, ascending=False).head(15)
    bottom = data.sort_values(column, ascending=True).head(15)
    view = pd.concat([top, bottom], ignore_index=True).drop_duplicates("product_vt_symbol")
    view = view.sort_values(column, ascending=True)
    fig, ax = plt.subplots(figsize=(13, max(7, len(view) * 0.32)))
    colors = ["#16a34a" if value > 0 else "#dc2626" for value in view[column]]
    ax.barh(view["product_vt_symbol"], view[column], color=colors)
    ax.axvline(0, color="#111827", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("net pnl")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_scatter(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    data = summary.copy()
    x = pd.to_numeric(data["loss_window_daily_net_pnl"], errors="coerce").fillna(0.0)
    y = pd.to_numeric(data["total_net_pnl"], errors="coerce").fillna(0.0)
    static = pd.to_numeric(data["is_static_strategy_product"], errors="coerce").fillna(0).astype(int)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(x[static.eq(0)], y[static.eq(0)], c="#64748b", alpha=0.72, label="non-static full-market")
    ax.scatter(x[static.eq(1)], y[static.eq(1)], c="#2563eb", alpha=0.86, label="static strategy pool")
    ax.axhline(0, color="#111827", linewidth=1)
    ax.axvline(0, color="#111827", linewidth=1)
    for _, row in data.sort_values("total_net_pnl", ascending=False).head(8).iterrows():
        ax.annotate(str(row["product_vt_symbol"]), (row["loss_window_daily_net_pnl"], row["total_net_pnl"]), fontsize=8)
    for _, row in data.sort_values("loss_window_daily_net_pnl", ascending=True).head(6).iterrows():
        ax.annotate(str(row["product_vt_symbol"]), (row["loss_window_daily_net_pnl"], row["total_net_pnl"]), fontsize=8)
    ax.set_title("Stage124 single-product C9: 2022 loss-window PnL vs full-sample PnL")
    ax.set_xlabel("2022-03-09..2022-06-29 daily net pnl")
    ax.set_ylabel("2020..2026-06-30 daily net pnl")
    ax.legend(loc="best")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCATTER_PATH, dpi=160)
    plt.close(fig)


def _decision(summary: pd.DataFrame, run_status: pd.DataFrame) -> dict[str, Any]:
    ok = run_status[run_status["status"].astype(str).eq("ok")] if not run_status.empty and "status" in run_status.columns else pd.DataFrame()
    loss_profit = summary[summary["loss_window_daily_net_pnl"].gt(0.0)].copy() if not summary.empty else pd.DataFrame()
    full_profit = summary[summary["total_net_pnl"].gt(0.0)].copy() if not summary.empty else pd.DataFrame()
    material = summary[summary["material_profitable"].eq(1)].copy() if not summary.empty else pd.DataFrame()
    return {
        "stage": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "full_market_single_product_replay_completed",
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": CAPITAL,
        "scope": "57 eligible full-market products, each replayed as a standalone one-product universe with current C9/15w stop-retry engine; AI product pool filter disabled for this diagnostic.",
        "anti_overfit_before": "No parameter is tuned. This is a fixed-diagnostic replay to answer product-level strategy fit, not a new selection rule.",
        "continue_value_before": "Yes. It distinguishes products with actual strategy PnL from products that merely trend.",
        "coverage": {
            "requested_products": int(len(run_status)),
            "ok_products": int(len(ok)),
            "error_products": int(len(run_status) - len(ok)) if not run_status.empty else 0,
            "full_sample_profitable_products": int(len(full_profit)),
            "loss_window_profitable_products": int(len(loss_profit)),
            "material_profitable_products": int(len(material)),
        },
        "top_full_sample_products": full_profit.head(15)["product_vt_symbol"].astype(str).tolist(),
        "top_loss_window_products": loss_profit.sort_values("loss_window_daily_net_pnl", ascending=False).head(15)["product_vt_symbol"].astype(str).tolist(),
        "worst_full_sample_products": summary.sort_values("total_net_pnl", ascending=True).head(12)["product_vt_symbol"].astype(str).tolist() if not summary.empty else [],
        "worst_loss_window_products": summary.sort_values("loss_window_daily_net_pnl", ascending=True).head(12)["product_vt_symbol"].astype(str).tolist() if not summary.empty else [],
        "next_step": (
            "Use this only as a candidate inventory. Before any universe expansion, run multi-product portfolio true-engine A/B "
            "with predeclared selection logic, liquidity/margin gates, and out-of-sample validation."
        ),
    }


def _write_report(summary: pd.DataFrame, period: pd.DataFrame, run_status: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_full = summary.sort_values("total_net_pnl", ascending=False).head(20)
    worst_full = summary.sort_values("total_net_pnl", ascending=True).head(15)
    top_loss = summary.sort_values("loss_window_daily_net_pnl", ascending=False).head(20)
    worst_loss = summary.sort_values("loss_window_daily_net_pnl", ascending=True).head(15)
    cols = [
        "product_vt_symbol",
        "exchange",
        "is_static_strategy_product",
        "total_net_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "total_trade_count",
        "positive_active_years",
        "active_year_count",
        "loss_window_daily_net_pnl",
        "full_2022_daily_net_pnl",
        "max_broker10_margin_to_equity_pct",
        "material_profitable",
    ]
    period_totals = (
        period.groupby("period", as_index=False)
        .agg(
            product_count=("product_vt_symbol", "nunique"),
            profitable_count=("daily_net_pnl", lambda s: int(pd.to_numeric(s, errors="coerce").gt(0).sum())),
            total_daily_net_pnl=("daily_net_pnl", "sum"),
            total_closed_lot_realized_pnl=("closed_lot_realized_pnl", "sum"),
            total_daily_trade_count=("daily_trade_count", "sum"),
        )
        if not period.empty
        else pd.DataFrame()
    )
    status_view = run_status.copy()
    for column in ["product_vt_symbol", "status", "error", "minute_missing_symbol_count", "daily_rows", "closed_lots"]:
        if column not in status_view.columns:
            status_view[column] = "" if column in {"product_vt_symbol", "status", "error"} else 0
    lines = [
        "# Stage124 全品种单品种 C9 盈利能力 replay",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 当前实盘口径：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}` / 资金 `{CAPITAL:,.0f}`",
        f"- 回放区间：`{ANALYSIS_START.date()}` 到 `{ANALYSIS_END.date()}`；重点窗口 `{LOSS_WINDOW_START.date()} -> {LOSS_WINDOW_END.date()}`。",
        "- 口径：每个 full-market eligible 产品单独作为 universe 跑当前 C9/15w 真引擎；关闭 AI 产品池过滤；保留 C9 入场、出场、成本、保证金、broker10 cap、开仓日 0.5R stop/retry 逻辑。",
        "- 注意：这是产品适配度库存，不是直接扩池方案；组合后会有资金竞争、相关性、保证金和 AI 选择变化。",
        "",
        "## Period Totals",
        "",
        _md_table(period_totals, max_rows=10),
        "",
        "## Full Sample Top",
        "",
        _md_table(top_full[cols], max_rows=20),
        "",
        "## Full Sample Worst",
        "",
        _md_table(worst_full[cols], max_rows=15),
        "",
        "## 2022 Loss Window Top",
        "",
        _md_table(top_loss[cols], max_rows=20),
        "",
        "## 2022 Loss Window Worst",
        "",
        _md_table(worst_loss[cols], max_rows=15),
        "",
        "## Run Status",
        "",
        _md_table(status_view[["product_vt_symbol", "status", "error", "minute_missing_symbol_count", "daily_rows", "closed_lots"]] if not status_view.empty else pd.DataFrame(), max_rows=80),
        "",
        "## Charts",
        "",
        f"- loss-window bar：`{LOSS_WINDOW_CHART_PATH}`",
        f"- full-sample bar：`{FULL_SAMPLE_CHART_PATH}`",
        f"- scatter：`{SCATTER_PATH}`",
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(summary: pd.DataFrame, period: pd.DataFrame, run_status: pd.DataFrame, decision: dict[str, Any]) -> None:
    ok_count = int(run_status["status"].astype(str).eq("ok").sum()) if not run_status.empty else 0
    error_count = int(len(run_status) - ok_count) if not run_status.empty else 0
    full_profit = int(summary["total_net_pnl"].gt(0.0).sum()) if not summary.empty else 0
    loss_profit = int(summary["loss_window_daily_net_pnl"].gt(0.0).sum()) if not summary.empty else 0
    best_full = summary.sort_values("total_net_pnl", ascending=False).head(10) if not summary.empty else pd.DataFrame()
    best_loss = summary.sort_values("loss_window_daily_net_pnl", ascending=False).head(10) if not summary.empty else pd.DataFrame()
    worst_loss = summary.sort_values("loss_window_daily_net_pnl", ascending=True).head(10) if not summary.empty else pd.DataFrame()
    lines = [
        "# Stage124 全品种单品种 C9 盈利能力 replay",
        "",
        f"- 时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 是否重要突破版本：否。本阶段是全品种产品适配度库存，不是策略晋级。",
        f"- 阶段性质：诊断/库存；每个产品单独跑当前 C9/15w 真引擎，AI 产品池过滤关闭。",
        f"- 回放区间：`{ANALYSIS_START.date()}` 到 `{ANALYSIS_END.date()}`；重点窗口 `{LOSS_WINDOW_START.date()} -> {LOSS_WINDOW_END.date()}`。",
        f"- 覆盖：请求 `{len(run_status)}` 个 full-market eligible 产品，成功 `{ok_count}`，失败 `{error_count}`。",
        "",
        "## 本次版本变更",
        "",
        "- 新增参数：`enable_ai_product_pool_filter=False` 仅用于单品种诊断；`product_universe_csv_path` 每次替换为单品种 universe。",
        "- 修改参数：仅账户资金固定为当前 official live `150,000`，单品种 universe 替换；C9 核心入场/出场/成本/stop-retry 参数不改。",
        "- 删除参数：无。",
        "- 策略/实盘入口：未修改。",
        "",
        "## 结果摘要",
        "",
        f"- 全样本盈利产品数：`{full_profit}`。",
        f"- 2022 亏损窗口盈利产品数：`{loss_profit}`。",
        "",
        "### 全样本 Top10",
        "",
        _md_table(
            best_full[
                [
                    "product_vt_symbol",
                    "total_net_pnl",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "total_trade_count",
                    "loss_window_daily_net_pnl",
                    "full_2022_daily_net_pnl",
                ]
            ]
            if not best_full.empty
            else pd.DataFrame(),
            max_rows=10,
        ),
        "",
        "### 2022 亏损窗口 Top10",
        "",
        _md_table(
            best_loss[
                [
                    "product_vt_symbol",
                    "loss_window_daily_net_pnl",
                    "total_net_pnl",
                    "full_2022_daily_net_pnl",
                    "total_trade_count",
                ]
            ]
            if not best_loss.empty
            else pd.DataFrame(),
            max_rows=10,
        ),
        "",
        "### 2022 亏损窗口 Worst10",
        "",
        _md_table(
            worst_loss[
                [
                    "product_vt_symbol",
                    "loss_window_daily_net_pnl",
                    "total_net_pnl",
                    "full_2022_daily_net_pnl",
                    "total_trade_count",
                ]
            ]
            if not worst_loss.empty
            else pd.DataFrame(),
            max_rows=10,
        ),
        "",
        "## 关键指标",
        "",
        "- 期末权益：见 `product_summary`，本阶段不是单一组合权益。",
        "- 总收益：见各产品 `total_return_pct`。",
        "- 最大回撤：见各产品 `max_drawdown_pct`。",
        "- Sharpe：见各产品 `sharpe`。",
        "- 总滑点：见各产品 `total_slippage`。",
        "- 总交易次数：见各产品 `total_trade_count`。",
        "- 胜率：本阶段未以日胜率作为选品依据；后续若进入组合 A/B 再补。",
        "",
        "## 反过拟合与继续价值",
        "",
        "- 是否过拟合：否。未按结果新增阈值、黑名单或参数，只是固定口径全市场 replay。",
        "- 是否还有价值继续：有。下一步可以用这个库存提出预声明候选池，再做组合级真实引擎 A/B；不能直接按历史 PnL 排名上线。",
        "",
        "## 输出",
        "",
        f"- summary：`{SUMMARY_PATH}`",
        f"- period_summary：`{PERIOD_SUMMARY_PATH}`",
        f"- annual_summary：`{ANNUAL_SUMMARY_PATH}`",
        f"- closed_lots：`{CLOSED_LOTS_PATH}`",
        f"- report：`{REPORT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(limit: int | None = None, force: bool = False) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    universe = _load_universe(limit=limit)
    daily_frames: list[pd.DataFrame] = []
    closed_frames: list[pd.DataFrame] = []
    statuses: list[dict[str, Any]] = []
    for index, row in enumerate(universe.itertuples(index=False), start=1):
        series = pd.Series(row._asdict())
        product = str(series["product_vt_symbol"])
        print(f"[stage124] {index:02d}/{len(universe)} {product}", flush=True)
        daily, closed, status = _run_product(series, universe, force=force)
        daily_frames.append(daily)
        if not closed.empty:
            closed_frames.append(closed)
        statuses.append(status)
    summary, period, annual, run_status, closed_all = _summaries(daily_frames, closed_frames, statuses, universe)
    decision = _decision(summary, run_status)
    _plot_bar(summary, "loss_window_daily_net_pnl", LOSS_WINDOW_CHART_PATH, "Stage124 full-market single-product C9: 2022 loss window daily PnL")
    _plot_bar(summary, "total_net_pnl", FULL_SAMPLE_CHART_PATH, "Stage124 full-market single-product C9: full-sample daily PnL")
    _plot_scatter(summary)
    _write_report(summary, period, run_status, decision)
    _write_stage_record(summary, period, run_status, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    period.to_csv(PERIOD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    run_status.to_csv(RUN_STATUS_PATH, index=False, encoding="utf-8-sig")
    closed_all.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage124 full-market single-product C9/15w replay")
    parser.add_argument("--limit", type=int, default=None, help="limit product count for smoke test")
    parser.add_argument("--force", action="store_true", help="rerun existing per-product outputs")
    args = parser.parse_args()
    decision = run(limit=args.limit, force=bool(args.force))
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
