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
STAGE = "Stage019"
MODEL_TAG = "stage019_no_follow_light_shave_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage928_c9_15w_halfyear_to_latest as s928
import stage002_delayed_restore_true_engine as s002
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_no_follow_light_shave_true_engine"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage019_no_follow_30m_reduce_to_80"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
WINDOW_MINUTES = 30
REDUCE_FRACTION = 0.80
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
NO_FOLLOW_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_no_follow_light_shave_events_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    times = pd.to_datetime(day["bar_datetime"], errors="coerce")
    matches = day.index[times.eq(ts)]
    if len(matches):
        return int(matches[0])
    diffs = (times - ts).abs()
    if diffs.empty:
        return -1
    pos = int(diffs.idxmin())
    return pos if diffs.loc[pos] <= pd.Timedelta(minutes=1) else -1


class QmtRollPortfolioStrategyStage019NoFollowLightShave(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage019_no_follow_reduce: bool = False
    stage019_reduce_fraction: float = REDUCE_FRACTION
    stage019_window_minutes: int = WINDOW_MINUTES

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage019_no_follow_reduce",
        "stage019_reduce_fraction",
        "stage019_window_minutes",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage019_no_follow_light_shave_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage019_no_follow_light_shave_events: list[dict[str, Any]] = []
        self.stage019_no_follow_light_shave_count: int = 0
        # Reuse the Stage002 frame collector without inheriting its trading logic.
        self.stage002_restore_events = self.stage019_no_follow_light_shave_events
        self.stage002_open_adjustments: list[dict[str, Any]] = []

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        if self.enable_stage847_half_r_stop_retry:
            event = self._stage847_stop_retry_event_after_open_trade(trade)
            if event:
                return event
        if self.enable_stage019_no_follow_reduce:
            event = self._stage019_no_follow_reduce_after_open_trade(trade)
            if event:
                return event
        return super(s847.QmtRollPortfolioStrategyStage847C9StopRetry, self).stage827_intraday_exit_after_open_trade(trade)

    def _stage019_no_follow_reduce_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        trade_date = s827._normalize_date(trade.datetime)
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

        window_minutes = max(1, int(self.stage019_window_minutes))
        window = entry_day.head(window_minutes).copy()
        if window.empty:
            return None

        reduce_time = pd.Timestamp(window.iloc[-1]["bar_datetime"]).isoformat()
        reduce_price = float(window.iloc[-1]["close"])
        if reduce_price <= 0:
            return None

        if position_direction == "short":
            first_directional_r = (entry_price - reduce_price) / risk_price
            first_mfe_r = (entry_price - pd.to_numeric(window["low"], errors="coerce").min()) / risk_price
            first_mae_r = (pd.to_numeric(window["high"], errors="coerce").max() - entry_price) / risk_price
            progress_price = entry_price - 0.5 * risk_price
            adverse_price = entry_price + 0.5 * risk_price
        else:
            first_directional_r = (reduce_price - entry_price) / risk_price
            first_mfe_r = (pd.to_numeric(window["high"], errors="coerce").max() - entry_price) / risk_price
            first_mae_r = (entry_price - pd.to_numeric(window["low"], errors="coerce").min()) / risk_price
            progress_price = entry_price + 0.5 * risk_price
            adverse_price = entry_price - 0.5 * risk_price

        first_mfe_r = max(0.0, first_mfe_r) if np.isfinite(first_mfe_r) else np.nan
        first_mae_r = max(0.0, first_mae_r) if np.isfinite(first_mae_r) else np.nan
        if not np.isfinite(first_directional_r) or first_directional_r > 0:
            return None

        current_volume = int(state.active_volume())
        target_volume = max(1, int(math.floor(current_volume * float(self.stage019_reduce_fraction))))
        target_volume = min(target_volume, current_volume)
        reduce_volume = current_volume - target_volume
        if reduce_volume <= 0:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        size = self.get_size(contract_vt_symbol)
        sign = s827._direction_sign(position_direction)
        estimated_reduce_pnl = sign * (reduce_price - entry_price) * size * reduce_volume

        self._record_trade_event(
            bar=event_bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=position_direction,
            offset="Close",
            reason="stage019_no_follow_30m_reduce_to_80",
            volume=reduce_volume,
            price=reduce_price,
        )
        self._reduce_position_to_target(state, target_volume, reduce_price)
        self._apply_state_target(state, execution_price_override=reduce_price)

        self.stage019_no_follow_light_shave_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "risk_price": risk_price,
            "progress_price": progress_price,
            "adverse_price": adverse_price,
            "reduce_price": reduce_price,
            "reduce_time": reduce_time,
            "window_minutes": window_minutes,
            "window_bars": int(len(window)),
            "first_30m_directional_r": first_directional_r,
            "first_30m_mfe_r": first_mfe_r,
            "first_30m_mae_r": first_mae_r,
            "original_active_volume": current_volume,
            "target_volume": target_volume,
            "reduce_volume": reduce_volume,
            "estimated_reduce_pnl": estimated_reduce_pnl,
            "final_state": "reduced_to_80pct",
            "exit_reason": "stage019_no_follow_30m_reduce_to_80",
            "note": "first 30 minute close did not follow trade direction; reduce to floor(80%) min one lot, no hard deletion",
            "synthetic_trades": [
                {
                    "action": "close",
                    "source": "stage019_no_follow_30m_reduce_to_80",
                    "price": reduce_price,
                    "volume": reduce_volume,
                    "time": reduce_time,
                }
            ],
        }
        self.stage019_no_follow_light_shave_events.append(event)
        return event


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        profile = s928._c9_15w_profile(metadata, window)
    finally:
        s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C_ARM}_2018_01",
        label="Stage019 no-follow 30m light-shave official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage019 frozen no-follow light risk shave. "
            "Official C9 opens normally. If the first 30 entry-day minute bars close with non-positive "
            "directional progress, reduce active volume to floor(80%) with a one-lot minimum. Missing "
            "entry-day minute bars are left unchanged. No parameter, product, direction, year or month scan."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage019_no_follow_reduce": True,
        "stage019_reduce_fraction": REDUCE_FRACTION,
        "stage019_window_minutes": WINDOW_MINUTES,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage019NoFollowLightShave
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    no_follow_events = frames.get("restore_events", pd.DataFrame())
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
            "no_follow_light_shave_event_count": int(len(no_follow_events)),
            "no_follow_light_shave_volume": float(pd.to_numeric(no_follow_events.get("reduce_volume", 0), errors="coerce").fillna(0).sum())
            if not no_follow_events.empty
            else 0.0,
            "open_adjustment_count": 0,
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
    summary = _read_required_csv(s002.BASELINE_SUMMARY_IN)
    curves = _read_required_csv(s002.BASELINE_CURVES_IN)
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
    row["no_follow_light_shave_event_count"] = 0
    row["no_follow_light_shave_volume"] = 0.0
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
        "C_no_follow_light_shave_event_count": int(c.get("no_follow_light_shave_event_count", 0)),
        "C_no_follow_light_shave_volume": float(c.get("no_follow_light_shave_volume", 0.0)),
    }
    return pd.DataFrame([row])


def _cost_stress(profile: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in [1.0, 2.0, 3.0]:
        row = s650._metrics(combined, profile["spec"].capital, cost_multiplier=multiplier)
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
    colors = {A_ARM: "#2563eb", C_ARM: "#0f766e"}
    labels = {
        A_ARM: "A official C9/15w",
        C_ARM: "C no-follow 30m light-shave-to-80",
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
    axes[0].set_title("Stage019 full-path equity")
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
    for column in ["original_active_volume", "target_volume", "reduce_volume", "estimated_reduce_pnl", "first_30m_directional_r", "first_30m_mae_r"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby("year", dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            original_active_volume=("original_active_volume", "sum"),
            reduce_volume=("reduce_volume", "sum"),
            estimated_reduce_pnl=("estimated_reduce_pnl", "sum"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
            median_first_30m_mae_r=("first_30m_mae_r", "median"),
        )
        .reset_index()
        .sort_values("year")
    )


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["reduce_volume_num"] = pd.to_numeric(data.get("reduce_volume"), errors="coerce").fillna(0.0)
    data["estimated_reduce_pnl_num"] = pd.to_numeric(data.get("estimated_reduce_pnl"), errors="coerce").fillna(0.0)
    selected = [
        data.sort_values("estimated_reduce_pnl_num").head(8),
        data.sort_values("reduce_volume_num", ascending=False).head(8),
    ]
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "datetime", "direction", "reduce_time"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = s827._normalize_date(row["datetime"])
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
                s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "entry"),
                    ("progress_price", "#16a34a", "--", "+0.5R progress"),
                    ("adverse_price", "#dc2626", ":", "-0.5R adverse"),
                    ("reduce_price", "#7c3aed", "-.", "30m reduce price"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                idx = _index_for_time(day, row.get("reduce_time"))
                if idx >= 0:
                    ax.axvline(idx, color="#7c3aed", linewidth=1.1, alpha=0.9, label="reduce time")
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
                    f"orig/target/reduce={int(_safe_float(row.get('original_active_volume'), 0))}/"
                    f"{int(_safe_float(row.get('target_volume'), 0))}/"
                    f"{int(_safe_float(row.get('reduce_volume'), 0))} "
                    f"dir30={_safe_float(row.get('first_30m_directional_r'), 0):.2f}"
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
                    "original_active_volume": _safe_float(row.get("original_active_volume")),
                    "target_volume": _safe_float(row.get("target_volume")),
                    "reduce_volume": _safe_float(row.get("reduce_volume")),
                    "reduce_time": row.get("reduce_time", ""),
                    "first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                    "estimated_reduce_pnl": _safe_float(row.get("estimated_reduce_pnl")),
                }
            )
        fig.suptitle("Stage019 no-follow 30m light-shave true-engine entry-day minute-K atlas", fontsize=12)
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
    meaningful_dd5_pass = float(row["dd_improvement_pp"]) >= 5.0
    broker_pass = float(row["C_max_broker10_pct"]) <= float(row["A_max_broker10_pct"]) + 1e-9
    sharpe_pass = float(row["sharpe_delta"]) >= -0.10
    if retention_pass and dd_pass and meaningful_dd5_pass and broker_pass and sharpe_pass:
        label = "stage019_full_period_pass_next_multistart"
    elif not retention_pass:
        label = "stage019_failed_return_retention_no_param_rescue"
    elif not dd_pass:
        label = "stage019_failed_drawdown_no_param_rescue"
    else:
        label = "stage019_mixed_no_promotion"
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
            "Keep the official C9 entry path, but if the first 30 entry-day minute bars do not close in the trade "
            "direction, reduce active exposure to a one-lot-minimum 80pct position. This tests no-follow as a negative "
            "risk-restoration signal without hard-deleting the right tail."
        ),
        "predeclared_metrics": [
            "full-period end_equity/return/max_drawdown/Sharpe/slippage/trades/win_rate",
            "return retention >= 80%",
            "max drawdown improves versus A",
            "prefer meaningful drawdown improvement >= 5pp before any promotion path",
            "broker10 peak and days_over_100pct do not worsen",
            "2x/3x cost stress does not create a hidden failure",
            "visual path chart and minute-K atlas must support the metric story",
        ],
        "decision": label,
        "pass_flags": {
            "return_retention_80pct": bool(retention_pass),
            "drawdown_improved": bool(dd_pass),
            "meaningful_drawdown_5pp": bool(meaningful_dd5_pass),
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
            "no_follow_events": str(NO_FOLLOW_EVENTS_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "Trend-following position-sizing references support changing risk exposure while keeping alpha fixed, "
            "but they also warn that drawdown reducers can destroy positive skew. Stage019 is therefore a one-shot "
            "true-engine falsification of Stage018's fixed 80% light-shave proxy, not a sizing sweep."
        ),
        "overfit_reflection_before": (
            "Controlled risk, not zero risk: changing Stage008's failed half-risk shape to 80% could become parameter "
            "rescue if repeated. This run is acceptable only because 80% was frozen before the true engine, comes from "
            "Stage018's light-shave proxy, and does not branch by product, year, direction, month, or final PnL."
        ),
        "continue_value_before": (
            "Yes for exactly one run: Stage018 is proxy-only, so a true path engine is needed to see whether a light "
            "no-follow risk shave preserves the official C9 right tail. If it fails, stop this fraction/window route."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
    }


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    event_summary: pd.DataFrame,
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
        "no_follow_light_shave_event_count",
    ]
    lines = [
        "# Stage019 no-follow 30m 降风险真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- A：当前官方 C9/15w 全路径。",
        "- C：C9/15w + `no_follow_30m_reduce_to_80`。",
        "- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- CTA / trend-following 资料支持随趋势确认逐步建立或降低风险，但核心仍是保留右尾和正偏。",
        "- 日内动量资料支持前 30 分钟有信息含量；数据质量资料要求缺失 entry-day 分钟K不能插值或用未来K线替代。",
        "- 本阶段只测试一个负向规则：不跟随时降风险，不删除，不按样本补丁化。",
        "",
        "## 预声明规则",
        "",
        "- 官方 C9 正常开仓，保留原 C2 stop、broker10 cap、`0.5R` stop/retry-once 语义。",
        "- 若 C9 自身 `0.5R` stop/retry 已触发，则优先执行 C9，不再叠加 Stage019。",
        "- 若入场日已有分钟K且前 `30` 根分钟K收盘相对入场价的方向性 R `<=0`，把 active volume 降到 `floor(80%)`，最低保留 `1` 手。",
        "- 若缺失 entry-day 分钟K、风险距离无效或原仓位只有 `1` 手，则保持官方路径。",
        "- 不做恢复、不做二次判断、不做产品/方向/年份/月度分支。",
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
        "## No-Follow Light-Shave Events By Year",
        "",
        _md_table(event_summary, max_rows=30),
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
    print("[stage019] loading metadata and minute bars", flush=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s928._load_stage861_full_minute_bars(vt_symbols)
    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    print("[stage019] running candidate true engine", flush=True)
    profile = _candidate_profile(metadata)
    combined, frames = s002._run_candidate(profile, metadata)
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
    no_follow_events = frames.get("restore_events", pd.DataFrame()).copy()
    event_summary = _event_summary(no_follow_events)
    atlas_paths, atlas_manifest = _plot_atlas(no_follow_events, minute_bars)
    closed_lots = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    decision = _decision(comparison, cost_stress)
    if decision["decision"] == "stage019_full_period_pass_next_multistart":
        decision["overfit_reflection_after"] = (
            "No immediate full-period overfit signal: the frozen C rule retained 80%+ return and improved path risk, "
            "but completion still requires half-year/monthly cold-start visual verification before any promotion."
        )
        decision["continue_value_after"] = (
            "Yes: escalate to predeclared half-year and monthly starts, plus cost-pressure visuals; do not tune the rule."
        )
    elif decision["decision"] == "stage019_failed_return_retention_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No new overfit was introduced, but trying to rescue the shape by changing 30 minutes or 80% after seeing "
            "this result would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape if full-period return retention is below 80%; switch to a different first-principles "
            "execution idea instead of parameter rescue."
        )
    elif decision["decision"] == "stage019_failed_drawdown_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No parameter search occurred; the rule simply failed the drawdown objective. Tuning the window/fraction "
            "around the failure would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape as a drawdown reducer; only keep the event ledger for later attribution."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No parameter search occurred, but the mixed result is insufficient for promotion; further tuning around this "
            "same shape would be overfitting."
        )
        decision["continue_value_after"] = (
            "Limited: inspect the visual failure mode once, then either run fixed multi-start if evidence is strong enough "
            "or stop the shape."
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
    no_follow_events.to_csv(NO_FOLLOW_EVENTS_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(summary, comparison, path_diag, event_summary, cost_stress, atlas_paths, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage019] decision={decision['decision']}", flush=True)
    print(f"[stage019] comparison={COMPARISON_OUT}", flush=True)
    print(f"[stage019] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
