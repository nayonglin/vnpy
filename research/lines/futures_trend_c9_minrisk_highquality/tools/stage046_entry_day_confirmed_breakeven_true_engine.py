from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage046"
MODEL_TAG = "stage046_entry_day_confirmed_breakeven_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage008_no_follow_reduce_true_engine as s008
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"
STAGE010_OFFICIAL_CLOSED_LOTS_IN = (
    LINE_DIR
    / "outputs"
    / "stage010_authoritative_minute_coverage_audit"
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage046_entry_day_confirmed_breakeven"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
COST_STRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
TRADES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
BREAKEVEN_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_breakeven_events_{MODEL_TAG}.csv"
OFFICIAL_EVENT_MATCH_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_event_match_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s008._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s008._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s008._safe_float(value, default=default)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s008._drawdown_pct(equity)


def _read_required_csv(path: Path) -> pd.DataFrame:
    return s008._read_required_csv(path)


def _to_naive_ts(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    return s008._index_for_time(day, value)


class QmtRollPortfolioStrategyStage046ConfirmedBreakeven(s008.s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage046_entry_day_confirmed_breakeven: bool = False

    parameters = s008.s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage046_entry_day_confirmed_breakeven",
    ]
    variables = s008.s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage046_breakeven_exit_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage046_breakeven_events: list[dict[str, Any]] = []
        self.stage046_breakeven_exit_count: int = 0
        self.stage002_restore_events = self.stage046_breakeven_events
        self.stage002_open_adjustments: list[dict[str, Any]] = []

    def stage827_intraday_exit_after_open_trade(self, trade: s008.s827.TradeData) -> dict[str, Any] | None:
        if self.enable_stage847_half_r_stop_retry:
            event = self._stage847_stop_retry_event_after_open_trade(trade)
            if event:
                return event
        if self.enable_stage046_entry_day_confirmed_breakeven:
            event = self._stage046_entry_day_confirmed_breakeven_after_open_trade(trade)
            if event:
                return event
        return super(s008.s847.QmtRollPortfolioStrategyStage847C9StopRetry, self).stage827_intraday_exit_after_open_trade(trade)

    def _stage046_entry_day_confirmed_breakeven_after_open_trade(
        self,
        trade: s008.s827.TradeData,
    ) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s008.s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        trade_date = s008.s827._normalize_date(trade.datetime)
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        if bars.empty:
            return None
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        if entry_day.empty:
            return None

        entry_price = float(trade.price)
        if entry_price <= 0:
            return None

        candidate_indexes: list[int] = []
        risk_prices: list[float] = []
        for index, layer in enumerate(state.layers):
            if layer.direction != position_direction:
                continue
            candidate_indexes.append(index)
            risk_prices.append(abs(entry_price - float(layer.stop_price)))
        if not candidate_indexes:
            return None

        risk_price = max(risk_prices) if risk_prices else 0.0
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = s008.s827._direction_sign(position_direction)
        c2_stop_price = entry_price - sign * float(self.stage827_intraday_c2_stop_r) * risk_price
        c2_confirm_price = entry_price + sign * float(self.stage827_intraday_c2_confirm_r) * risk_price

        confirm_idx = -1
        confirm_time = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            high = float(item.high)
            low = float(item.low)
            if position_direction == "long":
                stop_hit = low <= c2_stop_price
                confirm_hit = high >= c2_confirm_price
            else:
                stop_hit = high >= c2_stop_price
                confirm_hit = low <= c2_confirm_price
            if stop_hit:
                return None
            if confirm_hit:
                confirm_idx = idx
                confirm_time = pd.Timestamp(item.bar_datetime).isoformat()
                break
        if confirm_idx < 0:
            return None

        breakeven_idx = -1
        breakeven_time = ""
        for idx in range(confirm_idx + 1, len(entry_day)):
            item = entry_day.iloc[idx]
            high = float(item["high"])
            low = float(item["low"])
            if position_direction == "long":
                breakeven_hit = low <= entry_price
            else:
                breakeven_hit = high >= entry_price
            if breakeven_hit:
                breakeven_idx = idx
                breakeven_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                break
        if breakeven_idx < 0:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = int(sum(state.layers[index].volume for index in candidate_indexes))
        if close_volume <= 0:
            return None

        exit_price = entry_price
        exit_reason = "stage046_entry_day_confirmed_breakeven_exit"
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        if len(candidate_indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state,
                exit_price,
                execution_price_override=exit_price,
                exit_reason=exit_reason,
            )
        else:
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason=exit_reason,
                volume=close_volume,
                price=exit_price,
            )
            self._close_layers(state, candidate_indexes, exit_price, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=exit_price)

        self.stage046_breakeven_exit_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "risk_price": risk_price,
            "c2_stop_price": c2_stop_price,
            "c2_confirm_price": c2_confirm_price,
            "exit_price": exit_price,
            "stop_price": exit_price,
            "volume": close_volume,
            "confirm_time": confirm_time,
            "confirm_bar_index": confirm_idx,
            "breakeven_time": breakeven_time,
            "breakeven_bar_index": breakeven_idx,
            "bars_after_confirm_to_breakeven": breakeven_idx - confirm_idx,
            "estimated_exit_pnl": 0.0,
            "exit_reason": exit_reason,
            "final_state": "closed_at_breakeven_after_1r_confirm",
            "note": (
                "After official C9 0.5R stop/retry stays inactive, require the official C2 +1R confirm to occur "
                "before the C2 -1R stop. Only from the next minute after confirm, close at original entry if "
                "price returns to breakeven. Same-bar confirm/breakeven ambiguity keeps the official path."
            ),
            "synthetic_trades": [
                {
                    "action": "close",
                    "source": exit_reason,
                    "price": exit_price,
                    "volume": close_volume,
                    "time": breakeven_time,
                }
            ],
        }
        self.stage046_breakeven_events.append(event)
        return event


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s008.s928._with_legacy_stage372_spec()
    try:
        profile = s008.s928._c9_15w_profile(metadata, window)
    finally:
        s008.s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C_ARM}_2018_01",
        label="Stage046 entry-day confirmed breakeven official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage046 frozen confirmed-breakeven guard. "
            "Official C9 opens normally and official 0.5R stop/retry keeps priority. If the entry-day path first "
            "reaches the existing C2 +1R confirm before the C2 -1R stop, then any later same-day return to the "
            "original entry price closes active same-direction layers at breakeven. Missing minute bars, invalid risk, "
            "C2 stop-first, no confirm, no retrace, and same-bar ambiguity keep the official path. No product, direction, "
            "year, month, R, window, or threshold scan."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage046_entry_day_confirmed_breakeven": True,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage046ConfirmedBreakeven
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s008.s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    breakeven_events = frames.get("restore_events", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum())
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm": C_ARM,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "window_id": FULL_WINDOW_ID,
            "window_start": START.date().isoformat(),
            "window_end": END.date().isoformat(),
            "actual_start": pd.to_datetime(combined["date"], errors="coerce").min().date().isoformat(),
            "actual_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
            "trading_days": int(len(combined)),
            "stop_retry_event_count": int(len(stop_retry_events)),
            "breakeven_exit_event_count": int(len(breakeven_events)),
            "breakeven_exit_volume": float(pd.to_numeric(breakeven_events.get("volume", 0), errors="coerce").fillna(0).sum())
            if not breakeven_events.empty
            else 0.0,
            "broker10_cap_event_count": broker10_cap_event_count,
            "closed_trade_rows": int(len(trades)),
        }
    )
    return row


def _candidate_curve(combined: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    curve = combined.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["arm"] = C_ARM
    curve["window_id"] = FULL_WINDOW_ID
    curve["window_start"] = START.date().isoformat()
    curve["window_end"] = END.date().isoformat()
    curve["account_capital"] = CAPITAL
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    curve["variant"] = profile["spec"].capital.variant
    return curve


def _load_baseline() -> tuple[pd.Series, pd.DataFrame]:
    summary = _read_required_csv(s008.s002.BASELINE_SUMMARY_IN)
    curves = _read_required_csv(s008.s002.BASELINE_CURVES_IN)
    base_summary = summary[summary["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_summary.empty:
        raise RuntimeError(f"missing baseline full window: {FULL_WINDOW_ID}")
    base_curve = curves[curves["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_curve.empty:
        raise RuntimeError(f"missing baseline curve full window: {FULL_WINDOW_ID}")
    row = base_summary.iloc[0].copy()
    row["stage"] = STAGE
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["arm"] = A_ARM
    row["official_live_version"] = OFFICIAL_LIVE_VERSION
    row["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    row["breakeven_exit_event_count"] = 0
    row["breakeven_exit_volume"] = 0.0
    base_curve["arm"] = A_ARM
    base_curve["stage"] = STAGE
    base_curve["model_tag"] = MODEL_TAG
    return row, base_curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["arm"].eq(A_ARM)].iloc[0]
    c = summary[summary["arm"].eq(C_ARM)].iloc[0]
    return_retention = float(c["total_return_pct"]) / float(a["total_return_pct"]) * 100.0 if float(a["total_return_pct"]) else np.nan
    equity_retention = (float(c["end_equity"]) - CAPITAL) / (float(a["end_equity"]) - CAPITAL) * 100.0
    row = {
        "A_arm": A_ARM,
        "C_arm": C_ARM,
        "A_end_equity": float(a["end_equity"]),
        "C_end_equity": float(c["end_equity"]),
        "end_equity_delta": float(c["end_equity"]) - float(a["end_equity"]),
        "A_total_return_pct": float(a["total_return_pct"]),
        "C_total_return_pct": float(c["total_return_pct"]),
        "return_retention_pct": return_retention,
        "equity_gain_retention_pct": equity_retention,
        "A_max_dd_pct": float(a["max_dd_pct"]),
        "C_max_dd_pct": float(c["max_dd_pct"]),
        "dd_improvement_pp": float(c["max_dd_pct"]) - float(a["max_dd_pct"]),
        "A_sharpe": float(a["sharpe"]),
        "C_sharpe": float(c["sharpe"]),
        "sharpe_delta": float(c["sharpe"]) - float(a["sharpe"]),
        "A_total_slippage": float(a["total_slippage"]),
        "C_total_slippage": float(c["total_slippage"]),
        "A_total_trade_count": float(a["total_trade_count"]),
        "C_total_trade_count": float(c["total_trade_count"]),
        "A_win_rate_pct": float(a["nonzero_daily_win_rate_pct"]),
        "C_win_rate_pct": float(c["nonzero_daily_win_rate_pct"]),
        "A_max_broker10_pct": float(a["max_broker10_margin_to_equity_pct"]),
        "C_max_broker10_pct": float(c["max_broker10_margin_to_equity_pct"]),
        "broker10_improvement_pp": float(a["max_broker10_margin_to_equity_pct"]) - float(c["max_broker10_margin_to_equity_pct"]),
        "A_days_over_100pct": int(a.get("days_over_100pct", 0)),
        "C_days_over_100pct": int(c.get("days_over_100pct", 0)),
        "C_breakeven_exit_event_count": int(c.get("breakeven_exit_event_count", 0)),
        "C_breakeven_exit_volume": float(c.get("breakeven_exit_volume", 0.0)),
    }
    return pd.DataFrame([row])


def _cost_stress(profile: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in [1.0, 2.0, 3.0]:
        row = s008.s650._metrics(combined, profile["spec"].capital, cost_multiplier=multiplier)
        row.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm": C_ARM,
                "cost_multiplier": multiplier,
                "window_id": FULL_WINDOW_ID,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        trough = group.loc[group["drawdown_pct"].idxmin()]
        before = group[group["date"].le(trough["date"])]
        peak = before.loc[before["account_equity"].idxmax()]
        rows.append(
            {
                "arm": arm,
                "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
                "peak_equity": float(peak["account_equity"]),
                "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
                "trough_equity": float(trough["account_equity"]),
                "trough_dd_pct": float(trough["drawdown_pct"]),
                "max_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()),
                "p95_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {A_ARM: "#2563eb", C_ARM: "#9333ea"}
    labels = {
        A_ARM: "A official C9/15w",
        C_ARM: "C confirmed breakeven",
    }
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct"],
            label=labels.get(arm, arm),
            color=colors.get(arm),
        )
    axes[0].set_title("Stage046 full-path equity")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.7)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in ["volume", "risk_price", "bars_after_confirm_to_breakeven"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby("year", dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            exit_volume=("volume", "sum"),
            median_risk_price=("risk_price", "median"),
            median_bars_after_confirm_to_breakeven=("bars_after_confirm_to_breakeven", "median"),
            max_bars_after_confirm_to_breakeven=("bars_after_confirm_to_breakeven", "max"),
        )
        .reset_index()
        .sort_values("year")
    )


def _official_event_match(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty or not STAGE010_OFFICIAL_CLOSED_LOTS_IN.exists():
        return pd.DataFrame(), pd.DataFrame()
    official = _read_required_csv(STAGE010_OFFICIAL_CLOSED_LOTS_IN)
    matched = events.merge(
        official,
        left_on="trade_id",
        right_on="open_trade_id",
        how="left",
        suffixes=("_event", "_official"),
    )
    pnl = pd.to_numeric(matched.get("realized_pnl"), errors="coerce")
    matched["official_realized_pnl_num"] = pnl
    matched["event_year"] = pd.to_datetime(matched.get("datetime"), errors="coerce").dt.year
    summary = pd.DataFrame(
        [
            {
                "event_count": int(len(events)),
                "matched_closed_lot_rows": int(pnl.notna().sum()),
                "official_realized_pnl_sum": float(pnl.sum()),
                "official_positive_pnl_sum": float(pnl[pnl > 0].sum()),
                "official_negative_pnl_sum": float(pnl[pnl < 0].sum()),
                "official_winner_rows": int((pnl > 0).sum()),
                "official_loser_rows": int((pnl < 0).sum()),
            }
        ]
    )
    return matched, summary


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["volume_num"] = pd.to_numeric(data.get("volume"), errors="coerce").fillna(0.0)
    data["bars_after_confirm_num"] = pd.to_numeric(data.get("bars_after_confirm_to_breakeven"), errors="coerce").fillna(0.0)
    selected = [
        data.sort_values("volume_num", ascending=False).head(8),
        data.sort_values("bars_after_confirm_num", ascending=False).head(8),
    ]
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "datetime", "direction", "breakeven_time"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s008.s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = s008.s827._normalize_date(row["datetime"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s008.s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "entry / breakeven"),
                    ("c2_stop_price", "#dc2626", "--", "C2 -1R stop"),
                    ("c2_confirm_price", "#16a34a", "--", "C2 +1R confirm"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("confirm_time", "#16a34a", "confirm"),
                    ("breakeven_time", "#9333ea", "breakeven exit"),
                ]:
                    idx = _index_for_time(day, row.get(time_col))
                    if idx >= 0:
                        ax.axvline(idx, color=color, linewidth=1.0, alpha=0.85, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{vt_symbol} {row.get('direction')} {entry_date:%Y-%m-%d} "
                    f"vol={int(_safe_float(row.get('volume'), 0))} "
                    f"confirm_idx={int(_safe_float(row.get('confirm_bar_index'), -1))} "
                    f"be_idx={int(_safe_float(row.get('breakeven_bar_index'), -1))}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": row.get("direction", ""),
                    "volume": _safe_float(row.get("volume")),
                    "confirm_time": row.get("confirm_time", ""),
                    "breakeven_time": row.get("breakeven_time", ""),
                    "entry_price": _safe_float(row.get("entry_price")),
                    "c2_stop_price": _safe_float(row.get("c2_stop_price")),
                    "c2_confirm_price": _safe_float(row.get("c2_confirm_price")),
                    "bars_after_confirm_to_breakeven": _safe_float(row.get("bars_after_confirm_to_breakeven")),
                }
            )
        fig.suptitle("Stage046 confirmed-breakeven minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(comparison: pd.DataFrame, cost_stress: pd.DataFrame) -> dict[str, Any]:
    row = comparison.iloc[0]
    cost_3x = cost_stress[cost_stress["cost_multiplier"].eq(3.0)].iloc[0].to_dict()
    retention_pass = float(row["return_retention_pct"]) >= 80.0
    dd_pass = float(row["dd_improvement_pp"]) > 0.0
    broker_pass = float(row["C_max_broker10_pct"]) <= float(row["A_max_broker10_pct"]) + 1e-9
    sharpe_pass = float(row["sharpe_delta"]) >= -0.10
    if retention_pass and dd_pass and broker_pass and sharpe_pass:
        label = "stage046_full_period_pass_next_multistart"
    elif not retention_pass:
        label = "stage046_failed_return_retention_no_param_rescue"
    elif not dd_pass:
        label = "stage046_failed_drawdown_no_param_rescue"
    else:
        label = "stage046_mixed_no_promotion"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "baseline_arm": A_ARM,
        "candidate_arm": C_ARM,
        "candidate_hypothesis": (
            "Keep the official C9 entry path and only after the existing C2 +1R confirmation move the entry-day "
            "risk to breakeven. This is meant to remove residual same-day risk after price has proven direction, "
            "without reducing initial right-tail participation."
        ),
        "predeclared_metrics": [
            "full-period end_equity/return/max_drawdown/Sharpe/slippage/trades/win_rate",
            "return retention >= 80%",
            "max drawdown improves versus A",
            "broker10 peak and days_over_100pct do not worsen",
            "2x/3x cost stress does not create a hidden failure",
            "visual path chart and minute-K atlas must support the metric story",
        ],
        "decision": label,
        "pass_flags": {
            "return_retention_80pct": bool(retention_pass),
            "drawdown_improved": bool(dd_pass),
            "broker10_not_worse": bool(broker_pass),
            "sharpe_not_materially_worse": bool(sharpe_pass),
        },
        "comparison": comparison.to_dict(orient="records"),
        "cost_3x_candidate": cost_3x,
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "summary": str(SUMMARY_OUT),
            "comparison": str(COMPARISON_OUT),
            "curve": str(CURVE_OUT),
            "cost_stress": str(COST_STRESS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "breakeven_events": str(BREAKEVEN_EVENTS_OUT),
            "official_event_match": str(OFFICIAL_EVENT_MATCH_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "Backtrader stop/trailing examples and NautilusTrader backtesting docs both imply that stop-based logic must "
            "be represented as explicit event-order semantics. vn.py BarGenerator confirms minute bars are the execution "
            "state unit in this stack. Therefore Stage046 freezes one universal order-state rule and rejects any same-bar "
            "confirm/breakeven optimism."
        ),
        "overfit_reflection_before": (
            "No: the rule uses the existing official C2 +1R confirmation and original entry price breakeven. It does not "
            "branch by product, year, direction, month, final PnL, residual replay samples, or tuned decimals."
        ),
        "continue_value_before": (
            "Yes: previous default-small-risk and no-follow-reduce shapes cut right-tail exposure. Stage046 leaves the "
            "initial official exposure untouched and only removes same-day residual risk after direction is confirmed."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
    }


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    event_summary: pd.DataFrame,
    official_match_summary: pd.DataFrame,
    cost_stress: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    view_cols = [
        "arm",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "stop_retry_event_count",
        "breakeven_exit_event_count",
    ]
    lines = [
        "# Stage046 confirmed-breakeven 真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- A：当前官方 C9/15w 全路径。",
        "- C：C9/15w + `entry_day_confirmed_breakeven`。",
        "- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- Backtrader stop/trailing stop 示例强调止损与保护利润必须通过明确订单/事件状态表达。",
        "- NautilusTrader backtesting 文档强调 backtest engine 处理历史事件流，策略、portfolio 和 execution semantics 要一致。",
        "- vn.py BarGenerator 源码说明分钟 bar 是本栈生成/更新日内状态的基础单元。",
        "- 我的判断：Stage046 只能做成明确事件顺序规则；同一根分钟K里既确认又回踩保本的情况保持官方路径，避免乐观 intrabar 排序。",
        "",
        "## 预声明规则",
        "",
        "- 官方 C9 正常开仓，保留原 C2 stop、broker10 cap、`0.5R` stop/retry-once 语义。",
        "- 若 C9 自身 `0.5R` stop/retry 已触发，则优先执行 C9，不叠加 Stage046。",
        "- 若入场日先触发 C2 `-1R` stop，保持官方 C2 路径。",
        "- 若入场日先触发 C2 `+1R` confirm，则从下一根分钟K开始把剩余 entry-day 风险移动到原始入场价。",
        "- confirm 后若同日价格回踩原始入场价，则按入场价退出同方向 active layers。",
        "- 同根 confirm+breakeven、缺分钟K、无效风险、无 confirm 或无回踩均保持官方路径。",
        "- 不扫 R 倍数、窗口、保本价、品种、方向、年份或月份。",
        "",
        "## Summary",
        "",
        _md_table(summary[view_cols], max_rows=10),
        "",
        "## A/C Comparison",
        "",
        _md_table(comparison, max_rows=5),
        "",
        "## Cost Stress Candidate",
        "",
        _md_table(cost_stress[["cost_multiplier", "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]], max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Breakeven Events By Year",
        "",
        _md_table(event_summary, max_rows=30),
        "",
        "## Official Path Attribution For Triggered Events",
        "",
        _md_table(official_match_summary, max_rows=10) if not official_match_summary.empty else "(no official match table)",
        "",
        "## Visual Outputs",
        "",
        f"- path chart：`{PATH_CHART_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage046] loading metadata and full minute bars", flush=True)
    metadata = s008.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s008.s928._load_stage861_full_minute_bars(vt_symbols)
    s008.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s008.s825._minute_groups(minute_bars)

    print("[stage046] running candidate true engine", flush=True)
    profile = _candidate_profile(metadata)
    combined, frames = s008.s002._run_candidate(profile, metadata)
    c_summary = _candidate_summary(profile, combined, frames)
    c_curve = _candidate_curve(combined, profile)
    a_summary, a_curve = _load_baseline()

    summary = pd.DataFrame([a_summary.to_dict(), c_summary])
    curve = pd.concat([a_curve, c_curve], ignore_index=True, sort=False)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    comparison = _comparison(summary)
    cost_stress = _cost_stress(profile, combined)
    path_diag = _path_diagnostics(curve)
    breakeven_events = frames.get("restore_events", pd.DataFrame()).copy()
    event_summary = _event_summary(breakeven_events)
    official_event_match, official_match_summary = _official_event_match(breakeven_events)
    atlas_paths, atlas_manifest = _plot_atlas(breakeven_events, minute_bars)
    closed_lots = s008.s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    decision = _decision(comparison, cost_stress)
    if decision["decision"] == "stage046_full_period_pass_next_multistart":
        decision["overfit_reflection_after"] = (
            "No immediate full-period overfit signal: the single frozen C2-confirmed breakeven rule retained 80%+ return, "
            "improved drawdown and did not worsen broker10. It still needs half-year/monthly cold-start validation."
        )
        decision["continue_value_after"] = (
            "Yes: escalate unchanged to predeclared half-year/monthly starts and visual stress pages; do not tune confirm R or breakeven timing."
        )
    elif decision["decision"] == "stage046_failed_return_retention_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No new overfit was introduced, but changing confirm R, same-bar handling, or breakeven trigger after seeing this result would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape if return retention is below 80%; keep the atlas as failure evidence and switch idea."
        )
    elif decision["decision"] == "stage046_failed_drawdown_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No parameter search occurred; the rule failed the primary drawdown objective. Tuning around the failure would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape as a drawdown reducer unless visual evidence reveals an implementation bug, not a parameter issue."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No parameter search occurred, but the mixed result is not enough for promotion. Further tuning the same shape would be overfitting."
        )
        decision["continue_value_after"] = (
            "Limited: inspect the visual failure mode once; only proceed unchanged if multi-start validation is justified."
        )

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    cost_stress.to_csv(COST_STRESS_OUT, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_risk", pd.DataFrame()).to_csv(ENTRY_RISK_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_OUT, index=False, encoding="utf-8-sig")
    frames.get("trade_events", pd.DataFrame()).to_csv(TRADE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("intraday_events", pd.DataFrame()).to_csv(INTRADAY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("stop_retry_events", pd.DataFrame()).to_csv(STOP_RETRY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    breakeven_events.to_csv(BREAKEVEN_EVENTS_OUT, index=False, encoding="utf-8-sig")
    official_event_match.to_csv(OFFICIAL_EVENT_MATCH_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(summary, comparison, path_diag, event_summary, official_match_summary, cost_stress, atlas_paths, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage046] decision={decision['decision']}", flush=True)
    print(f"[stage046] comparison={COMPARISON_OUT}", flush=True)
    print(f"[stage046] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
