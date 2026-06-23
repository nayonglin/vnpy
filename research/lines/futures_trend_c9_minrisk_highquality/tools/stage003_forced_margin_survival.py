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
STAGE = "Stage003"
MODEL_TAG = "stage003_forced_margin_survival_v1"
OUTPUT_PREFIX = "qmt_roll_stage003_c9_minrisk_forced_margin_survival"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage928_c9_15w_halfyear_to_latest as s928
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage003_forced_margin_survival"
BT_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage003_forced95_to80_largest_margin"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
FORCED_TRIGGER_RATIO = 0.95
FORCED_TARGET_RATIO = 0.80
FORCED_BROKER_MULTIPLIER = 1.65
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
FORCED_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
POSITIONS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
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
        label="Stage003 forced margin survival official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage003 frozen account survival layer. "
            "After daily mark-to-market, if runtime broker10 margin/equity exceeds 95%, "
            "reduce largest-margin positions toward 80%. This is a single coarse survival "
            "test inherited from prior Stage653 evidence; no threshold, product, direction, "
            "year or month scan is allowed."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_forced_margin_deleverage": True,
        "forced_margin_deleverage_trigger_ratio": FORCED_TRIGGER_RATIO,
        "forced_margin_deleverage_target_ratio": FORCED_TARGET_RATIO,
        "forced_margin_deleverage_broker_multiplier": FORCED_BROKER_MULTIPLIER,
        "forced_margin_deleverage_priority": "largest_margin",
        "forced_margin_deleverage_max_reductions_per_day": 100,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _run_candidate(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s847.START
    original_end = s847.END
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        s847.START = START
        s847.END = END
        combined, frames = _run_profile_with_stage003_frames(profile, metadata)
    finally:
        s847.START = original_start
        s847.END = original_end
        s928._restore_legacy_state(legacy_state)
    return combined, frames


def _run_profile_with_stage003_frames(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s827.s778.s653.s517.START_DT
    original_end = s827.s778.s653.s517.END_DT
    original_preload = s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s827.s778.s653.s517.START_DT = START.to_pydatetime()
        s827.s778.s653.s517.END_DT = END.to_pydatetime()
        s827.s778.s653.s517.PRELOAD_START_DT = s827.s772._preload_for_start(START).to_pydatetime()
        s827.s778.s653.s517.assert_stage196_database_sentinels()
        s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s827.s778.s653.s517.PRELOAD_START_DT,
            s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s847.Stage847StopRetryEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s827.Interval.DAILY,
            start=preload_start,
            end=s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s513._c3_overrides(START.to_pydatetime())),
            start=START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START.date()) & (daily.index <= END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s827.s772._combine_daily(daily, margin_daily, spec)

        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "forced_events": forced_events,
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["window_id"] = FULL_WINDOW_ID
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s827.s778.s653.s517.START_DT = original_start
        s827.s778.s653.s517.END_DT = original_end
        s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    forced_events = frames.get("forced_events", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum())
    forced_closed_volume = (
        float(pd.to_numeric(forced_events.get("reduce_volume", 0), errors="coerce").fillna(0.0).sum())
        if not forced_events.empty
        else 0.0
    )
    max_forced_ratio_before = (
        float(pd.to_numeric(forced_events.get("ratio_before", 0), errors="coerce").fillna(0.0).max() * 100.0)
        if not forced_events.empty
        else 0.0
    )
    max_forced_ratio_after = (
        float(pd.to_numeric(forced_events.get("ratio_after", 0), errors="coerce").fillna(0.0).max() * 100.0)
        if not forced_events.empty
        else 0.0
    )
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
            "forced_event_count": int(len(forced_events)),
            "forced_closed_volume": forced_closed_volume,
            "forced_max_ratio_before_pct": max_forced_ratio_before,
            "forced_max_ratio_after_pct": max_forced_ratio_after,
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
        "C_forced_event_count": int(c.get("forced_event_count", 0)),
        "C_forced_closed_volume": float(c.get("forced_closed_volume", 0.0)),
        "C_forced_max_ratio_before_pct": float(c.get("forced_max_ratio_before_pct", 0.0)),
        "C_forced_max_ratio_after_pct": float(c.get("forced_max_ratio_after_pct", 0.0)),
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
                "days_over_100pct": int((pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce") > 100.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {A_ARM: "#2563eb", C_ARM: "#b45309"}
    labels = {
        A_ARM: "A official C9/15w",
        C_ARM: "C forced95->80 largest margin",
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
    axes[0].set_title("Stage003 full-path equity")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.7)
    axes[2].axhline(95.0, color="#f59e0b", linestyle=":", linewidth=0.9, alpha=0.7)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _forced_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in ["reduce_volume", "volume_before", "volume_after", "ratio_before", "ratio_after", "margin_before", "margin_after"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["year", "product_vt_symbol", "direction"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            contracts=("vt_symbol", "nunique"),
            reduce_volume=("reduce_volume", "sum"),
            max_ratio_before_pct=("ratio_before", lambda values: float(np.max(values) * 100.0)),
            max_ratio_after_pct=("ratio_after", lambda values: float(np.max(values) * 100.0)),
            first_datetime=("datetime", "min"),
            last_datetime=("datetime", "max"),
        )
        .reset_index()
        .sort_values(["year", "reduce_volume"], ascending=[True, False])
    )


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["ratio_before_num"] = pd.to_numeric(data.get("ratio_before"), errors="coerce").fillna(0.0)
    data["reduce_volume_num"] = pd.to_numeric(data.get("reduce_volume"), errors="coerce").fillna(0.0)
    selected = data.sort_values(["ratio_before_num", "reduce_volume_num"], ascending=False).head(MAX_ATLAS_ROWS)
    return selected.drop_duplicates(["vt_symbol", "datetime", "direction"]).head(MAX_ATLAS_ROWS)


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
            event_date = s827._normalize_date(row["datetime"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(event_date)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {event_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                price = _safe_float(row.get("price"))
                if np.isfinite(price):
                    ax.axhline(price, color="#dc2626", linestyle="--", linewidth=1.0, label="forced reduce price")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                ax.grid(True, alpha=0.18)
                ax.legend(loc="best", fontsize=7)
            ratio_before = _safe_float(row.get("ratio_before"), 0.0) * 100.0
            ratio_after = _safe_float(row.get("ratio_after"), 0.0) * 100.0
            ax.set_title(
                (
                    f"{vt_symbol} {row.get('direction')} {event_date:%Y-%m-%d} "
                    f"reduce={int(_safe_float(row.get('reduce_volume'), 0))} "
                    f"vol={int(_safe_float(row.get('volume_before'), 0))}->{int(_safe_float(row.get('volume_after'), 0))} "
                    f"ratio={ratio_before:.1f}%->{ratio_after:.1f}%"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "date": event_date.date().isoformat(),
                    "direction": row.get("direction"),
                    "reduce_volume": _safe_float(row.get("reduce_volume"), 0),
                    "ratio_before_pct": ratio_before,
                    "ratio_after_pct": ratio_after,
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
        "stage003_forced_margin_survival_promote_to_multistart_validation"
        if pass_return and pass_dd and pass_broker and pass_cost
        else "stage003_forced_margin_survival_not_promoted_no_threshold_rescue"
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
            "enable_forced_margin_deleverage": True,
            "forced_margin_deleverage_trigger_ratio": FORCED_TRIGGER_RATIO,
            "forced_margin_deleverage_target_ratio": FORCED_TARGET_RATIO,
            "forced_margin_deleverage_broker_multiplier": FORCED_BROKER_MULTIPLIER,
            "forced_margin_deleverage_priority": "largest_margin",
            "forced_margin_deleverage_max_reductions_per_day": 100,
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
            "forced_events": str(FORCED_EVENTS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
        },
        "next_step": (
            "If promoted, validate halfyear/monthly starts without tuning. "
            "If not promoted, stop this global forced-margin shape and move back to data/visual coverage or a new first principle."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    forced_summary: pd.DataFrame,
    cost_stress: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        f"# {STAGE} C9/15w forced margin survival",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- A: `{A_ARM}`",
        f"- C: `{C_ARM}`",
        f"- frozen rule: broker10 runtime ratio `95% -> 80%`, priority `largest_margin`, multiplier `{FORCED_BROKER_MULTIPLIER}`",
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
                    "forced_event_count",
                    "forced_closed_volume",
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
        "## Forced Event Summary",
        "",
        _md_table(forced_summary, max_rows=20) if not forced_summary.empty else "No forced events.",
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
        "- This is a coarse account-survival test, not a new alpha rule.",
        "- No threshold rescue is allowed if the curve or return-retention evidence fails.",
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
    forced_events = frames.get("forced_events", pd.DataFrame()).copy()
    forced_summary = _forced_event_summary(forced_events)
    _plot_path(curve)
    atlas_paths, atlas_manifest = _plot_atlas(forced_events, minute_bars)
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
        ("forced_events", FORCED_EVENTS_OUT),
        ("positions", POSITIONS_OUT),
    ]:
        frames.get(key, pd.DataFrame()).to_csv(path, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    _write_report(summary, comparison, path_diag, forced_summary, cost_stress, atlas_paths, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
