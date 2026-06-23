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
STAGE = "Stage004"
MODEL_TAG = "stage004_cap_only_delayed_restore_v1"
OUTPUT_PREFIX = "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage928_c9_15w_halfyear_to_latest as s928
import stage002_delayed_restore_true_engine as s002
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage004_cap_only_delayed_restore"
BT_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage004_cap_only_delayed_restore"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
INITIAL_FRACTION = 0.50
PROGRESS_R = 0.50
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

STAGE928_TAG = "stage928_c9_15w_halfyear_to_latest_v1"
STAGE928_PREFIX = "qmt_roll_stage928_c9_15w_halfyear_to_latest"
BASELINE_SUMMARY_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_summary_{STAGE928_TAG}.csv"
BASELINE_CURVES_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_curves_{STAGE928_TAG}.csv"

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
RESTORE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_events_{MODEL_TAG}.csv"
OPEN_ADJUSTMENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_adjustments_{MODEL_TAG}.csv"
CAP_DELAY_ELIGIBLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cap_delay_eligible_events_{MODEL_TAG}.csv"
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


class QmtRollPortfolioStrategyStage004CapOnlyDelayedRestore(s002.QmtRollPortfolioStrategyStage002DelayedRestore):
    enable_stage004_cap_only_delayed_restore: bool = False

    parameters = s002.QmtRollPortfolioStrategyStage002DelayedRestore.parameters + [
        "enable_stage004_cap_only_delayed_restore",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage004_cap_delay_eligible_events: list[dict[str, Any]] = []

    def _open_position(
        self,
        state: Any,
        contract_vt_symbol: str,
        direction: str,
        volume: int,
        bar: Any,
        signal: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        sizing_snapshot: dict[str, Any] | None = None,
    ) -> None:
        sizing = dict(sizing_snapshot or {})
        cap_applied = int(sizing.get("stage830_broker10_margin_cap_applied") or 0) == 1
        selected_before = int(sizing.get("stage830_margin_cap_selected_volume_before") or volume or 0)
        selected_after = int(sizing.get("stage830_margin_cap_selected_volume_after") or volume or 0)
        eligible = bool(self.enable_stage004_cap_only_delayed_restore) and cap_applied

        if eligible:
            self.stage004_cap_delay_eligible_events.append(
                {
                    "datetime": bar.datetime,
                    "product_vt_symbol": state.product_vt_symbol,
                    "vt_symbol": contract_vt_symbol,
                    "direction": direction,
                    "signal": signal,
                    "selected_volume_before_cap": selected_before,
                    "selected_volume_after_cap": selected_after,
                    "cap_reduced_volume": max(0, selected_before - selected_after),
                    "stage830_projected_broker10_margin_to_equity_before": sizing.get(
                        "stage830_projected_broker10_margin_to_equity_before"
                    ),
                    "stage830_projected_broker10_margin_to_equity_after": sizing.get(
                        "stage830_projected_broker10_margin_to_equity_after"
                    ),
                    "note": "Stage004 delayed restore applies only after existing Stage830 broker10 cap reduced this flat entry",
                }
            )
            sizing["stage004_cap_only_delayed_restore_eligible"] = 1
            sizing["stage004_cap_selected_volume_before"] = selected_before
            sizing["stage004_cap_selected_volume_after"] = selected_after
            return super()._open_position(
                state,
                contract_vt_symbol,
                direction,
                volume,
                bar,
                signal,
                history,
                signal_data,
                sizing_snapshot=sizing,
            )

        previous = bool(self.enable_stage002_delayed_restore)
        self.enable_stage002_delayed_restore = False
        try:
            sizing["stage004_cap_only_delayed_restore_eligible"] = 0
            return super()._open_position(
                state,
                contract_vt_symbol,
                direction,
                volume,
                bar,
                signal,
                history,
                signal_data,
                sizing_snapshot=sizing,
            )
        finally:
            self.enable_stage002_delayed_restore = previous


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
        label="Stage004 cap-only delayed restore official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage004 frozen cap-only delayed restore. "
            "Use the Stage002 scout+restore mechanism only when the existing Stage830 broker10 cap "
            "has already reduced a flat entry. This reorders risk release inside an official account-pressure "
            "case; it does not add size, new margin thresholds, products, directions, years or months."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage002_delayed_restore": True,
        "stage002_initial_fraction": INITIAL_FRACTION,
        "stage002_progress_r": PROGRESS_R,
        "enable_stage004_cap_only_delayed_restore": True,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage004CapOnlyDelayedRestore
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _run_candidate(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s002.s847.START
    original_end = s002.s847.END
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        s002.s847.START = START
        s002.s847.END = END
        combined, frames = s002._run_profile_with_stage002_frames(profile, metadata)
        strategy = None
        cap_events = pd.DataFrame()
        # The runner does not expose the strategy object directly, so recover the explicit eligibility
        # from entry diagnostics and open adjustments below.
        frames["cap_delay_eligible_events"] = cap_events
    finally:
        s002.s847.START = original_start
        s002.s847.END = original_end
        s928._restore_legacy_state(legacy_state)
    return combined, _add_stage004_eligibility_frame(frames)


def _add_stage004_eligibility_frame(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    open_adjustments = frames.get("open_adjustments", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()

    open_keys: set[tuple[str, str, str]] = set()
    if not open_adjustments.empty:
        open_keys = set(
            zip(
                pd.to_datetime(open_adjustments["datetime"], errors="coerce").dt.normalize().dt.strftime("%Y-%m-%d"),
                open_adjustments["vt_symbol"].astype(str),
                open_adjustments["direction"].astype(str),
            )
        )

    if not trade_events.empty and "reason" in trade_events.columns:
        cap_events = trade_events[
            trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False)
        ].copy()
        if not cap_events.empty:
            cap_events["stage004_actual_split"] = [
                int(
                    (
                        pd.Timestamp(row["datetime"]).normalize().strftime("%Y-%m-%d"),
                        str(row["vt_symbol"]),
                        str(row["direction"]),
                    )
                    in open_keys
                )
                for _, row in cap_events.iterrows()
            ]
            frames["cap_delay_eligible_events"] = cap_events
            return frames

    if entry_risk.empty:
        actual = open_adjustments.copy()
        if not actual.empty:
            actual["stage004_actual_split"] = 1
        frames["cap_delay_eligible_events"] = actual
        return frames

    data = entry_risk.copy()
    def numeric_column(name: str, default: float = 0.0) -> pd.Series:
        if name in data.columns:
            return pd.to_numeric(data[name], errors="coerce").fillna(default)
        return pd.Series(default, index=data.index)

    def string_column(name: str, default: str = "") -> pd.Series:
        if name in data.columns:
            return data[name].astype(str)
        return pd.Series(default, index=data.index)

    for col in [
        "stage830_broker10_margin_cap_applied",
        "stage830_margin_cap_selected_volume_before",
        "stage830_margin_cap_selected_volume_after",
        "selected_volume",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)
    selected_after = (
        numeric_column("stage830_margin_cap_selected_volume_after")
        if "stage830_margin_cap_selected_volume_after" in data.columns
        else numeric_column("selected_volume")
    )
    eligible = data[
        numeric_column("stage830_broker10_margin_cap_applied").eq(1.0)
        & selected_after.ge(2.0)
        & string_column("signal").ne("rollover_reopen")
    ].copy()
    if not eligible.empty and open_keys:
        eligible["stage004_actual_split"] = [
            int(
                (
                    pd.Timestamp(row["datetime"]).normalize().strftime("%Y-%m-%d"),
                    str(row["contract_vt_symbol"]),
                    str(row["direction"]),
                )
                in open_keys
            )
            for _, row in eligible.iterrows()
        ]
    elif not eligible.empty:
        eligible["stage004_actual_split"] = 0
    elif eligible.empty and not open_adjustments.empty:
        eligible = open_adjustments.copy()
        eligible["stage004_actual_split"] = 1
    else:
        frames["cap_delay_eligible_events"] = pd.DataFrame()
        return frames
    frames["cap_delay_eligible_events"] = eligible
    return frames


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    restore_events = frames.get("restore_events", pd.DataFrame())
    open_adjustments = frames.get("open_adjustments", pd.DataFrame())
    cap_delay = frames.get("cap_delay_eligible_events", pd.DataFrame())
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
            "restore_event_count": int(len(restore_events)),
            "restore_stop_count": int(
                restore_events["final_state"].astype(str).eq("restore_stopped").sum() if not restore_events.empty else 0
            ),
            "open_adjustment_count": int(len(open_adjustments)),
            "cap_delay_eligible_count": int(len(cap_delay)),
            "cap_delay_actual_split_count": int(cap_delay.get("stage004_actual_split", pd.Series(dtype=int)).sum())
            if not cap_delay.empty
            else 0,
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
    summary = _read_required_csv(BASELINE_SUMMARY_IN)
    curves = _read_required_csv(BASELINE_CURVES_IN)
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
    base_curve["arm"] = A_ARM
    base_curve["stage"] = STAGE
    base_curve["model_tag"] = MODEL_TAG
    return row, base_curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["arm"].eq(A_ARM)].iloc[0]
    c = summary[summary["arm"].eq(C_ARM)].iloc[0]
    return_retention = float(c["total_return_pct"]) / float(a["total_return_pct"]) * 100.0 if float(a["total_return_pct"]) else np.nan
    equity_retention = (float(c["end_equity"]) - CAPITAL) / (float(a["end_equity"]) - CAPITAL) * 100.0
    return pd.DataFrame(
        [
            {
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
                "broker10_improvement_pp": float(a["max_broker10_margin_to_equity_pct"])
                - float(c["max_broker10_margin_to_equity_pct"]),
                "A_days_over_100pct": int(a.get("days_over_100pct", 0)),
                "C_days_over_100pct": int(c.get("days_over_100pct", 0)),
                "C_open_adjustment_count": int(c.get("open_adjustment_count", 0)),
                "C_restore_event_count": int(c.get("restore_event_count", 0)),
                "C_restore_stop_count": int(c.get("restore_stop_count", 0)),
                "C_cap_delay_eligible_count": int(c.get("cap_delay_eligible_count", 0)),
            }
        ]
    )


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
                "max_broker10_margin_to_equity_pct": float(
                    pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()
                ),
                "p95_broker10_margin_to_equity_pct": float(
                    pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").quantile(0.95)
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {A_ARM: "#2563eb", C_ARM: "#7c3aed"}
    labels = {A_ARM: "A official C9/15w", C_ARM: "C cap-only delayed restore"}
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=labels.get(arm, arm), color=colors.get(arm))
    axes[0].set_title("Stage004 full-path equity")
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
    for column in ["restore_volume", "original_volume", "scout_volume", "deferred_volume", "estimated_restore_pnl"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["year", "final_state", "restore_stop_state"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            original_volume=("original_volume", "sum"),
            scout_volume=("scout_volume", "sum"),
            restore_volume=("restore_volume", "sum"),
            estimated_restore_pnl=("estimated_restore_pnl", "sum"),
            median_progress_bar=("progress_bar_index", "median"),
            median_stop_bar=("stop_bar_index", "median"),
        )
        .reset_index()
        .sort_values(["year", "final_state", "restore_stop_state"])
    )


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["restore_volume_num"] = pd.to_numeric(data.get("restore_volume"), errors="coerce").fillna(0.0)
    data["estimated_restore_pnl_num"] = pd.to_numeric(data.get("estimated_restore_pnl"), errors="coerce").fillna(0.0)
    selected: list[pd.DataFrame] = []
    opened = data[data["final_state"].astype(str).eq("restore_open")].copy()
    stopped = data[data["final_state"].astype(str).eq("restore_stopped")].copy()
    if not opened.empty:
        selected.append(opened.sort_values("restore_volume_num", ascending=False).head(8))
    if not stopped.empty:
        selected.append(stopped.sort_values("estimated_restore_pnl_num").head(8))
    if not selected:
        selected.append(data.sort_values("restore_volume_num", ascending=False).head(8))
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "datetime", "direction", "progress_time"])
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
                    ("entry_price", "#2563eb", "-", "scout entry"),
                    ("progress_price", "#16a34a", "--", "+0.5R restore"),
                    ("adverse_price", "#7c2d12", ":", "-0.5R adverse"),
                    ("restore_stop_price", "#dc2626", "-.", "restore stop at entry"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("progress_time", "#16a34a", "restore"),
                    ("stop_time", "#dc2626", "restore stop"),
                ]:
                    idx = _index_for_time(day, row.get(time_col))
                    if idx >= 0:
                        ax.axvline(idx, color=color, linewidth=1.0, alpha=0.9, label=label)
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
                    f"state={row.get('final_state')} stop_state={row.get('restore_stop_state')} "
                    f"orig/scout/restore={int(_safe_float(row.get('original_volume'), 0))}/"
                    f"{int(_safe_float(row.get('scout_volume'), 0))}/"
                    f"{int(_safe_float(row.get('restore_volume'), 0))}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "date": entry_date.date().isoformat(),
                    "direction": row.get("direction"),
                    "final_state": row.get("final_state"),
                    "restore_stop_state": row.get("restore_stop_state"),
                    "restore_volume": _safe_float(row.get("restore_volume"), 0),
                    "png": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                }
            )
        path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(comparison: pd.DataFrame, cost_stress: pd.DataFrame) -> dict[str, Any]:
    row = comparison.iloc[0].to_dict()
    cost_3x = cost_stress[cost_stress["cost_multiplier"].eq(3.0)].iloc[0].to_dict()
    pass_return = float(row["return_retention_pct"]) >= 80.0
    pass_dd = float(row["dd_improvement_pp"]) > 2.0
    pass_broker = float(row["C_max_broker10_pct"]) <= float(row["A_max_broker10_pct"]) and int(row["C_days_over_100pct"]) <= int(row["A_days_over_100pct"])
    pass_cost = float(cost_3x["max_dd_pct"]) > -55.0 and float(cost_3x["end_equity"]) > CAPITAL
    decision = (
        "stage004_cap_only_delayed_restore_promote_to_multistart_validation"
        if pass_return and pass_dd and pass_broker and pass_cost
        else "stage004_cap_only_delayed_restore_not_promoted_no_param_rescue"
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "A_arm": A_ARM,
        "C_arm": C_ARM,
        "candidate": {
            "trigger": "stage830_broker10_margin_cap_applied == 1",
            "initial_fraction": INITIAL_FRACTION,
            "progress_r": PROGRESS_R,
            "restore_stop": "original_entry_price",
            "no_new_margin_threshold": True,
        },
        "pass_return_retention_80": pass_return,
        "pass_dd_improvement_2pp": pass_dd,
        "pass_broker10_not_worse": pass_broker,
        "pass_3x_cost_survival": pass_cost,
        "comparison": {key: _json_safe(value) for key, value in row.items()},
        "cost_3x_candidate": {key: _json_safe(value) for key, value in cost_3x.items()},
        "decision": decision,
        "paths": {
            "summary": str(SUMMARY_OUT),
            "comparison": str(COMPARISON_OUT),
            "curve": str(CURVE_OUT),
            "cost_stress": str(COST_STRESS_OUT),
            "restore_events": str(RESTORE_EVENTS_OUT),
            "open_adjustments": str(OPEN_ADJUSTMENTS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
        },
        "next_step": "If not promoted, stop cap-only delayed restore and use the visual evidence to choose a new first principle.",
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
    lines = [
        f"# {STAGE} C9/15w cap-only delayed restore",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- A: `{A_ARM}`",
        f"- C: `{C_ARM}`",
        "- frozen rule: only entries already reduced by Stage830 broker10 cap use Stage002 scout+restore.",
        f"- decision: `{decision['decision']}`",
        "",
        "## Summary",
        "",
        _md_table(
            summary[
                [
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
                    "cap_delay_eligible_count",
                    "cap_delay_actual_split_count",
                    "broker10_cap_event_count",
                    "open_adjustment_count",
                    "restore_event_count",
                    "restore_stop_count",
                ]
            ].fillna(0),
            max_rows=20,
        ),
        "",
        "## A vs C",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Restore Event Summary",
        "",
        _md_table(event_summary, max_rows=20) if not event_summary.empty else "No restore events.",
        "",
        "## Cost Stress",
        "",
        _md_table(
            cost_stress[
                [
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "total_slippage",
                    "total_trade_count",
                ]
            ],
            max_rows=10,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- atlas pages: `{len(atlas_paths)}`",
        "",
        "## Judgment",
        "",
        "- This is a narrow account-pressure execution test, not a new alpha source.",
        "- No cap threshold, fraction, R, product, direction, year or month rescue is allowed if it fails.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _candidate_profile(metadata)
    combined, frames = _run_candidate(profile, metadata)
    candidate_summary = _candidate_summary(profile, combined, frames)
    candidate_curve = _candidate_curve(combined, profile)
    baseline_row, baseline_curve = _load_baseline()

    summary = pd.DataFrame([baseline_row.to_dict(), candidate_summary])
    curve = pd.concat([baseline_curve, candidate_curve], ignore_index=True, sort=False)
    if "drawdown_pct" not in curve.columns:
        curve["drawdown_pct"] = curve.groupby("arm")["account_equity"].transform(_drawdown_pct)
    comparison = _comparison(summary)
    cost_stress = _cost_stress(profile, combined)
    path_diag = _path_diagnostics(curve)
    restore_events = frames.get("restore_events", pd.DataFrame()).copy()
    event_summary = _event_summary(restore_events)
    _plot_path(curve)
    atlas_paths, atlas_manifest = _plot_atlas(restore_events, minute_bars)
    decision = _decision(comparison, cost_stress)

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    cost_stress.to_csv(COST_STRESS_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    for key, path in [
        ("trades", TRADES_OUT),
        ("entry_risk", ENTRY_RISK_OUT),
        ("entry_candidates", ENTRY_CANDIDATES_OUT),
        ("trade_events", TRADE_EVENTS_OUT),
        ("intraday_events", INTRADAY_EVENTS_OUT),
        ("stop_retry_events", STOP_RETRY_EVENTS_OUT),
        ("restore_events", RESTORE_EVENTS_OUT),
        ("open_adjustments", OPEN_ADJUSTMENTS_OUT),
        ("cap_delay_eligible_events", CAP_DELAY_ELIGIBLE_OUT),
    ]:
        frames.get(key, pd.DataFrame()).to_csv(path, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    _write_report(summary, comparison, path_diag, event_summary, cost_stress, atlas_paths, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
