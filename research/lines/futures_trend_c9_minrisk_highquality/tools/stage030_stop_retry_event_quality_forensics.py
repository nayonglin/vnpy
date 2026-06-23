from __future__ import annotations

from datetime import datetime
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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage030"
MODEL_TAG = "stage030_stop_retry_event_quality_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
FIRST_STOP_EARLY_BAR = 30
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE019_DIR = LINE_DIR / "outputs" / "stage019_no_follow_light_shave_true_engine"
STAGE028_DIR = LINE_DIR / "outputs" / "stage028_member_rank_position_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage030_stop_retry_event_quality_forensics"

FEATURES_IN = (
    STAGE028_DIR
    / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_features_"
    "stage028_member_rank_position_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)
STOP_RETRY_EVENTS_IN = (
    STAGE019_DIR
    / "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_stop_retry_events_"
    "stage019_no_follow_light_shave_true_engine_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
EVENT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
LOT_STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_state_summary_{MODEL_TAG}.csv"
STATE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_year_matrix_{MODEL_TAG}.csv"
STATE_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_product_matrix_{MODEL_TAG}.csv"
FIRST_STOP_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_first_stop_bucket_summary_{MODEL_TAG}.csv"
QUALITY_CROSSTAB_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_crosstab_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_stop_retry_state_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_contribution_chart_{MODEL_TAG}.png"
STATE_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_year_heatmap_{MODEL_TAG}.png"
PRODUCT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_state_heatmap_{MODEL_TAG}.png"
FIRST_STOP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_first_stop_timing_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


STATE_ORDER = ["no_event", "flat_no_reentry", "flat_retry_failed", "open_after_reentry"]
STATE_COLORS = {
    "no_event": "#1f77b4",
    "flat_no_reentry": "#ff7f0e",
    "flat_retry_failed": "#d62728",
    "open_after_reentry": "#2ca02c",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _event_key(vt_symbol: Any, direction: Any, date_value: Any) -> str:
    date = pd.to_datetime(date_value, errors="coerce")
    date_text = "" if pd.isna(date) else pd.Timestamp(date).strftime("%Y-%m-%d")
    return f"{vt_symbol}|{direction}|{date_text}"


def _load_features() -> pd.DataFrame:
    frame = _read_csv(FEATURES_IN)
    for column in ["entry_date", "exit_date", "prev_state_date"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    frame["entry_year"] = pd.to_numeric(frame["entry_year"], errors="coerce").astype("Int64")
    for column in [
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "risk_amount",
        "risk_price",
        "entry_price",
        "exit_price",
        "first_30m_directional_r",
        "first_30m_mae_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "stage861_entry_day_minute_bars",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["vt_symbol"] = frame["vt_symbol"].astype(str)
    frame["direction"] = frame["direction"].astype(str)
    frame["product"] = frame["product"].astype(str)
    frame["event_key"] = [
        _event_key(vt_symbol, direction, entry_date)
        for vt_symbol, direction, entry_date in zip(frame["vt_symbol"], frame["direction"], frame["entry_date"], strict=False)
    ]
    return frame


def _load_events() -> pd.DataFrame:
    events = _read_csv(STOP_RETRY_EVENTS_IN)
    events["event_entry_date"] = pd.to_datetime(events["datetime"], errors="coerce").dt.normalize()
    for column in ["first_stop_time", "reentry_time", "retry_failed_time"]:
        events[column] = pd.to_datetime(events[column], errors="coerce")
        events[column] = events[column].dt.tz_localize(None) if getattr(events[column].dt, "tz", None) is not None else events[column]
    for column in [
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "volume",
        "first_stop_bar_index",
        "reentry_bar_index",
        "retry_failed_bar_index",
        "retry_reentered",
        "retry_failed",
    ]:
        events[column] = pd.to_numeric(events[column], errors="coerce")
    for column in ["reentry_bar_index", "retry_failed_bar_index"]:
        events.loc[events[column] < 0, column] = np.nan
    events["event_key"] = [
        _event_key(vt_symbol, direction, event_date)
        for vt_symbol, direction, event_date in zip(
            events["vt_symbol"], events["direction"], events["event_entry_date"], strict=False
        )
    ]
    events["first_stop_bucket"] = events["first_stop_bar_index"].map(_first_stop_bucket)
    events["reentry_latency_bars"] = events["reentry_bar_index"] - events["first_stop_bar_index"]
    events.loc[~np.isfinite(events["reentry_latency_bars"]), "reentry_latency_bars"] = np.nan
    return events


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _first_stop_bucket(value: Any) -> str:
    bar = _safe_float(value)
    if not np.isfinite(bar):
        return "no_first_stop"
    if bar < 5:
        return "first_stop_0_4"
    if bar < 15:
        return "first_stop_5_14"
    if bar < FIRST_STOP_EARLY_BAR:
        return "first_stop_15_29"
    if bar < 120:
        return "first_stop_30_119"
    return "first_stop_120_plus"


def _entry_quality_label(row: pd.Series) -> str:
    if int(_safe_float(row.get("stage861_covered"), 0.0)) != 1:
        return "missing_stage861"
    if int(_safe_float(row.get("risk_valid"), 0.0)) != 1:
        return "risk_invalid"
    directional = _safe_float(row.get("first_30m_directional_r"))
    mae = _safe_float(row.get("first_30m_mae_r"))
    if not np.isfinite(directional) or not np.isfinite(mae):
        return "feature_invalid"
    if directional <= 0:
        return "no_follow_30m"
    if mae > 0.5:
        return "adverse_heat_30m"
    return "clean_continuation_30m"


def _bind_events(features: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    event_cols = [
        "event_key",
        "trade_id",
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "first_stop_time",
        "first_stop_bar_index",
        "first_stop_bucket",
        "reentry_time",
        "reentry_bar_index",
        "reentry_latency_bars",
        "retry_failed_time",
        "retry_failed_bar_index",
        "retry_reentered",
        "retry_failed",
        "final_state",
        "final_exit_price",
    ]
    event_unique = events[event_cols].drop_duplicates("event_key").copy()
    merged = features.merge(event_unique, on="event_key", how="left", suffixes=("", "_event"))
    merged["stop_retry_event_matched"] = merged["final_state"].notna()
    merged["stop_retry_state"] = merged["final_state"].fillna("no_event")
    merged["stop_retry_state"] = pd.Categorical(merged["stop_retry_state"], categories=STATE_ORDER, ordered=True)
    merged["entry_quality_label_stage030"] = merged.apply(_entry_quality_label, axis=1)
    merged["first_stop_bucket"] = merged["first_stop_bucket"].fillna("no_first_stop")
    return merged.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _official_metrics(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    start = float(curve["account_equity"].iloc[0]) if not curve.empty else ACCOUNT_CAPITAL
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0),
        "closed_lot_count": float(len(features)),
    }


def _lot_state_summary(features: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).sum())
    total_pos = float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).clip(lower=0.0).sum())
    total_neg_abs = abs(float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).clip(upper=0.0).sum()))
    rows: list[dict[str, Any]] = []
    for state in STATE_ORDER:
        group = features[features["stop_retry_state"].astype(str).eq(state)].copy()
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        pos = float(pnl.clip(lower=0.0).sum())
        neg = float(pnl.clip(upper=0.0).sum())
        rows.append(
            {
                "stop_retry_state": state,
                "lot_count": int(len(group)),
                "event_key_count": int(group["event_key"].nunique()),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": float(pnl.sum()),
                "positive_pnl": pos,
                "negative_pnl": neg,
                "net_pnl_share_pct": float(pnl.sum() / total_pnl * 100.0) if total_pnl else np.nan,
                "positive_coverage_pct": float(pos / total_pos * 100.0) if total_pos else np.nan,
                "negative_abs_coverage_pct": float(abs(neg) / total_neg_abs * 100.0) if total_neg_abs else np.nan,
                "win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else np.nan,
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()) if len(group) else np.nan,
                "avg_first_stop_bar": float(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").mean()) if len(group) else np.nan,
                "avg_reentry_latency_bars": float(pd.to_numeric(group["reentry_latency_bars"], errors="coerce").mean()) if len(group) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for state, group in events.groupby("final_state", dropna=False, sort=False):
        rows.append(
            {
                "final_state": str(state),
                "event_count": int(len(group)),
                "product_count": int(group["product_vt_symbol"].nunique()),
                "year_count": int(group["event_entry_date"].dt.year.nunique()),
                "retry_reentered": int(pd.to_numeric(group["retry_reentered"], errors="coerce").fillna(0).sum()),
                "retry_failed": int(pd.to_numeric(group["retry_failed"], errors="coerce").fillna(0).sum()),
                "median_first_stop_bar": float(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").median()),
                "median_reentry_latency_bars": float(pd.to_numeric(group["reentry_latency_bars"], errors="coerce").median()),
                "early_first_stop_lt30_count": int(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").lt(FIRST_STOP_EARLY_BAR).sum()),
            }
        )
    order = {state: idx for idx, state in enumerate(STATE_ORDER)}
    return pd.DataFrame(rows).sort_values("final_state", key=lambda s: s.map(order).fillna(99)).reset_index(drop=True)


def _state_year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = features.pivot_table(
        index="stop_retry_state",
        columns="entry_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    matrix = matrix.reindex(STATE_ORDER).fillna(0.0)
    matrix.columns = [str(int(column)) for column in matrix.columns]
    return matrix.reset_index()


def _state_product_matrix(features: pd.DataFrame) -> pd.DataFrame:
    data = features[features["stop_retry_state"].astype(str).ne("no_event")].copy()
    matrix = data.pivot_table(
        index="product",
        columns="stop_retry_state",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    for state in STATE_ORDER:
        if state not in matrix.columns:
            matrix[state] = 0.0
    matrix["event_net_pnl"] = matrix[[state for state in STATE_ORDER if state != "no_event"]].sum(axis=1)
    matrix["event_lot_count"] = data.groupby("product").size()
    matrix = matrix.sort_values("event_lot_count", ascending=False)
    return matrix.reset_index()


def _first_stop_bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    data = features[features["stop_retry_state"].astype(str).ne("no_event")].copy()
    rows: list[dict[str, Any]] = []
    for (bucket, state), group in data.groupby(["first_stop_bucket", "stop_retry_state"], dropna=False, observed=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "first_stop_bucket": str(bucket),
                "stop_retry_state": str(state),
                "lot_count": int(len(group)),
                "net_pnl": float(pnl.sum()),
                "win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else np.nan,
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["first_stop_bucket", "stop_retry_state"]).reset_index(drop=True)


def _quality_crosstab(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    matrix = data.pivot_table(
        index="entry_quality_label_stage030",
        columns="stop_retry_state",
        values="realized_pnl",
        aggfunc=["count", "sum"],
        fill_value=0.0,
        observed=False,
    )
    matrix.columns = [f"{agg}_{state}" for agg, state in matrix.columns]
    return matrix.reset_index()


def _contribution_curve(features: pd.DataFrame) -> pd.DataFrame:
    start = features["exit_date"].min()
    end = features["exit_date"].max()
    calendar = pd.date_range(start, end, freq="D")
    out = pd.DataFrame({"date": calendar})
    for state in STATE_ORDER:
        sub = features[features["stop_retry_state"].astype(str).eq(state)].copy()
        daily = sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
        out[f"cum_pnl_{state}"] = daily.to_numpy(dtype=float)
    event_daily = features[features["stop_retry_state"].astype(str).ne("no_event")].groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    out["cum_pnl_any_stop_retry_event"] = event_daily.to_numpy(dtype=float)
    return out


def _build_summary(metrics: dict[str, float], lot_summary: pd.DataFrame, event_summary: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    event_lots = features[features["stop_retry_state"].astype(str).ne("no_event")]
    open_after = lot_summary[lot_summary["stop_retry_state"].eq("open_after_reentry")]
    flat_failed = lot_summary[lot_summary["stop_retry_state"].eq("flat_retry_failed")]
    flat_no = lot_summary[lot_summary["stop_retry_state"].eq("flat_no_reentry")]
    return pd.DataFrame(
        [
            {
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": metrics["end_equity"],
                "total_return_pct": metrics["total_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "sharpe": metrics["sharpe"],
                "closed_lot_count": int(len(features)),
                "event_lot_count": int(len(event_lots)),
                "event_key_count": int(event_lots["event_key"].nunique()),
                "event_net_pnl": float(event_lots["realized_pnl"].sum()),
                "flat_no_reentry_net_pnl": float(flat_no["net_pnl"].iloc[0]) if not flat_no.empty else 0.0,
                "flat_retry_failed_net_pnl": float(flat_failed["net_pnl"].iloc[0]) if not flat_failed.empty else 0.0,
                "open_after_reentry_net_pnl": float(open_after["net_pnl"].iloc[0]) if not open_after.empty else 0.0,
                "stop_retry_event_count": int(event_summary["event_count"].sum()) if not event_summary.empty else 0,
            }
        ]
    )


def _build_decision(
    metrics: dict[str, float],
    lot_summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    first_stop_summary: pd.DataFrame,
    quality_crosstab: pd.DataFrame,
    features: pd.DataFrame,
) -> dict[str, Any]:
    event_lots = features[features["stop_retry_state"].astype(str).ne("no_event")]
    open_after = lot_summary[lot_summary["stop_retry_state"].eq("open_after_reentry")]
    flat_failed = lot_summary[lot_summary["stop_retry_state"].eq("flat_retry_failed")]
    flat_no = lot_summary[lot_summary["stop_retry_state"].eq("flat_no_reentry")]
    event_net = float(event_lots["realized_pnl"].sum()) if not event_lots.empty else 0.0
    open_after_net = float(open_after["net_pnl"].iloc[0]) if not open_after.empty else 0.0
    flat_net = float(flat_failed["net_pnl"].iloc[0] + flat_no["net_pnl"].iloc[0]) if not flat_failed.empty and not flat_no.empty else 0.0
    if event_net < 0 and open_after_net > 0:
        decision = "stage030_stop_retry_forensics_no_candidate_future_state_not_tradable"
        reason = (
            "Stop/retry event lots are net negative in official C9/15w attribution, while open-after-reentry "
            "lots are positive; however open_after_reentry is a future state, not an entry-time tradable rule."
        )
    else:
        decision = "stage030_stop_retry_forensics_no_candidate_no_stable_edge"
        reason = "Stop/retry attribution does not expose a stable broad tradable subset without future labels."
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": reason,
        "official_metrics": metrics,
        "event_lot_count": int(len(event_lots)),
        "event_key_count": int(event_lots["event_key"].nunique()) if not event_lots.empty else 0,
        "event_net_pnl": event_net,
        "flat_stop_net_pnl": flat_net,
        "open_after_reentry_net_pnl": open_after_net,
        "lot_state_summary": lot_summary.to_dict(orient="records"),
        "event_summary": event_summary.to_dict(orient="records"),
        "first_stop_summary": first_stop_summary.to_dict(orient="records"),
        "quality_crosstab": quality_crosstab.to_dict(orient="records"),
        "guardrails": {
            "no_trade_rule": True,
            "no_parameter_sweep": True,
            "no_ctp_or_order_api": True,
            "final_state_is_future_label_not_tradable": True,
            "official_pnl_source": str(FEATURES_IN),
            "event_timing_source": str(STOP_RETRY_EVENTS_IN),
            "event_binding_key": "vt_symbol|direction|entry_date",
        },
        "outputs": {
            "features": str(FEATURES_OUT),
            "event_summary": str(EVENT_SUMMARY_OUT),
            "lot_state_summary": str(LOT_STATE_SUMMARY_OUT),
            "state_year_matrix": str(STATE_YEAR_OUT),
            "state_product_matrix": str(STATE_PRODUCT_OUT),
            "first_stop_bucket_summary": str(FIRST_STOP_BUCKET_OUT),
            "quality_crosstab": str(QUALITY_CROSSTAB_OUT),
            "contribution_curve": str(CONTRIB_CURVE_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "summary": str(SUMMARY_OUT),
            "decision": str(DECISION_OUT),
            "report": str(REPORT_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "state_year_heatmap": str(STATE_YEAR_HEATMAP_OUT),
            "product_heatmap": str(PRODUCT_HEATMAP_OUT),
            "first_stop_chart": str(FIRST_STOP_CHART_OUT),
        },
    }


def _plot_path(curve: pd.DataFrame, contribution: pd.DataFrame) -> None:
    merged = curve.merge(contribution, left_on="date", right_on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].set_title("Official drawdown pct")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(merged["date"], merged["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.1)
    axes[2].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin pressure")
    axes[2].grid(True, alpha=0.25)
    axes[3].plot(merged["date"], merged["cum_pnl_any_stop_retry_event"], color="#111111", linewidth=1.4, label="any stop/retry event")
    axes[3].plot(merged["date"], merged["cum_pnl_open_after_reentry"], color=STATE_COLORS["open_after_reentry"], linewidth=1.0, label="open_after_reentry")
    axes[3].plot(merged["date"], merged["cum_pnl_flat_retry_failed"], color=STATE_COLORS["flat_retry_failed"], linewidth=1.0, label="flat_retry_failed")
    axes[3].plot(merged["date"], merged["cum_pnl_flat_no_reentry"], color=STATE_COLORS["flat_no_reentry"], linewidth=1.0, label="flat_no_reentry")
    axes[3].axhline(0.0, color="#555555", linewidth=0.8)
    axes[3].set_title("Stop/retry state realized PnL contribution")
    axes[3].legend(loc="upper left", ncol=2, fontsize=8)
    axes[3].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(contribution: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(15, 7))
    for state in STATE_ORDER:
        column = f"cum_pnl_{state}"
        if column not in contribution:
            continue
        ax.plot(contribution["date"], contribution[column], linewidth=1.2, label=state, color=STATE_COLORS[state])
    ax.plot(contribution["date"], contribution["cum_pnl_any_stop_retry_event"], linewidth=1.7, color="#111111", label="any_stop_retry_event")
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Closed-lot realized PnL by stop/retry state")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", ncol=3)
    fig.tight_layout()
    fig.savefig(CONTRIB_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_year_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("stop_retry_state")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13, max(4, 0.55 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=45, ha="right")
    ax.set_title("Stop/retry state by entry year net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(STATE_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    cols = [state for state in STATE_ORDER if state in matrix.columns and state != "no_event"]
    data = matrix.set_index("product")[cols].head(24)
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8, max(6, 0.35 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=35, ha="right")
    ax.set_title("Product x stop/retry state net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_first_stop_timing(features: pd.DataFrame, first_stop_summary: pd.DataFrame) -> None:
    events = features[features["stop_retry_state"].astype(str).ne("no_event")].copy()
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    for state in ["flat_no_reentry", "flat_retry_failed", "open_after_reentry"]:
        sub = events[events["stop_retry_state"].astype(str).eq(state)]
        if sub.empty:
            continue
        axes[0].hist(
            pd.to_numeric(sub["first_stop_bar_index"], errors="coerce").dropna(),
            bins=[0, 5, 15, 30, 60, 120, 240, 480, 900],
            alpha=0.45,
            label=state,
            color=STATE_COLORS[state],
        )
    axes[0].set_title("First 0.5R stop bar index distribution")
    axes[0].set_xlabel("entry-day minute bar index")
    axes[0].set_ylabel("lot count")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper right")
    pivot = first_stop_summary.pivot_table(
        index="first_stop_bucket",
        columns="stop_retry_state",
        values="net_pnl",
        aggfunc="sum",
        fill_value=0.0,
        observed=False,
    )
    for state in ["flat_no_reentry", "flat_retry_failed", "open_after_reentry"]:
        if state not in pivot:
            pivot[state] = 0.0
    pivot = pivot[["flat_no_reentry", "flat_retry_failed", "open_after_reentry"]]
    x = np.arange(len(pivot.index))
    width = 0.25
    for offset, state in zip([-width, 0.0, width], pivot.columns, strict=False):
        axes[1].bar(x + offset, pivot[state] / 10000.0, width=width, label=state, color=STATE_COLORS[state])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(pivot.index, rotation=25, ha="right")
    axes[1].axhline(0.0, color="#555555", linewidth=0.8)
    axes[1].set_title("Net PnL by first-stop timing bucket")
    axes[1].set_ylabel("net PnL, 10k CNY")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIRST_STOP_CHART_OUT, dpi=160)
    plt.close(fig)


def _load_minute_groups(features: pd.DataFrame) -> dict[str, pd.DataFrame]:
    selected_symbols = set(features["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(selected_symbols)
    return s010.s008.s825._minute_groups(minute_bars)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    specs = [
        ("flat_retry_failed", True, 8),
        ("flat_no_reentry", True, 6),
        ("open_after_reentry", False, 8),
        ("open_after_reentry", True, 2),
    ]
    for state, ascending, count in specs:
        sub = features[features["stop_retry_state"].astype(str).eq(state)].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("realized_pnl", ascending=ascending)
        sub["atlas_reason"] = f"{state}_{'worst' if ascending else 'best'}"
        selected.append(sub.head(count))
    if not selected:
        return pd.DataFrame()
    out = pd.concat(selected, ignore_index=True, sort=False)
    out = out.drop_duplicates(["event_key", "stop_retry_state"]).head(MAX_ATLAS_ROWS)
    return out


def _plot_atlas(features: pd.DataFrame) -> pd.DataFrame:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return pd.DataFrame()
    groups = _load_minute_groups(selected)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = s010._normalize_day(row.get("entry_date"))
            day = s010._day_for_symbol(groups, vt_symbol, entry_day)
            day = day.head(420).copy() if not day.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_day:%Y-%m-%d}", ha="center", va="center")
            else:
                s010.s008.s825._plot_candles(ax, day)
                entry_price = _safe_float(row.get("entry_price_event"), _safe_float(row.get("entry_price")))
                stop_price = _safe_float(row.get("stop_price"))
                progress_price = _safe_float(row.get("progress_price"))
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.95, label="entry/reentry")
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linestyle="--", linewidth=0.9, label="0.5R stop")
                if np.isfinite(progress_price):
                    ax.axhline(progress_price, color="#16a34a", linestyle="--", linewidth=0.85, label="0.5R progress")
                for marker_col, color, label in [
                    ("first_stop_time", "#dc2626", "first stop"),
                    ("reentry_time", "#2563eb", "reentry"),
                    ("retry_failed_time", "#7c2d12", "retry failed"),
                ]:
                    ts = pd.to_datetime(row.get(marker_col), errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.9, alpha=0.8, label=label)
                if len(day) >= FIRST_STOP_EARLY_BAR:
                    ax.axvspan(0, FIRST_STOP_EARLY_BAR - 1, color="#fef3c7", alpha=0.18)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.iloc[pos]["bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{row.get('atlas_reason', '')} | {vt_symbol} {row.get('direction', '')} {entry_day:%Y-%m-%d} "
                f"state={row.get('stop_retry_state', '')} pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"R={_safe_float(row.get('r_multiple')):.2f} first_stop_bar={_safe_float(row.get('first_stop_bar_index')):.0f} "
                f"quality={row.get('entry_quality_label_stage030', '')}"
            )
            ax.set_title(title, fontsize=8.1, loc="left")
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.strftime("%Y-%m-%d") if not pd.isna(entry_day) else "",
                    "direction": row.get("direction", ""),
                    "stop_retry_state": str(row.get("stop_retry_state", "")),
                    "atlas_reason": row.get("atlas_reason", ""),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "first_stop_time": row.get("first_stop_time", ""),
                    "reentry_time": row.get("reentry_time", ""),
                    "retry_failed_time": row.get("retry_failed_time", ""),
                    "entry_quality_label_stage030": row.get("entry_quality_label_stage030", ""),
                }
            )
        fig.suptitle("Stage030 C9 stop/retry minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
    return pd.DataFrame(manifest)


def _write_report(
    metrics: dict[str, float],
    summary: pd.DataFrame,
    decision: dict[str, Any],
    lot_summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    state_year: pd.DataFrame,
    state_product: pd.DataFrame,
    first_stop_summary: pd.DataFrame,
    quality_crosstab: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    report = f"""# {STAGE} C9 stop/retry 事件质量只读法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：官方 C9/15w stop/retry 事件归因与分钟图谱；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- Robert Carver / systematic trend-following 资料强调趋势系统应保持简单、连续和稳健，显式 exit/re-entry 规则很容易过拟合；但初始紧止损和 whipsaw 归因是合理的风控研究对象。
- 趋势/突破资料普遍承认 false breakout 与 whipsaw 是趋势系统的主要摩擦，通常通过固定风险、止损、再入场纪律和仓位控制处理，而不是按历史坏样本补丁化。
- 我的判断：C9 的 `0.5R stop/retry once` 是当前正式版已经接入的分钟级执行纪律。继续优化前，必须先看它在官方 C9/15w 中到底是右尾保护、左尾来源，还是二者混合；本阶段只读，不把 `open_after_reentry` 这类未来状态当交易规则。

## 官方基准指标

- 期末权益：`{metrics['end_equity']:,.2f}`
- 总收益：`{metrics['total_return_pct']:.4f}%`
- 最大回撤：`{metrics['max_drawdown_pct']:.4f}%`
- Sharpe：`{metrics['sharpe']:.4f}`
- 总滑点：`{metrics['total_slippage']:,.0f}`
- 总交易次数：`{metrics['total_trade_count']:,.0f}`
- closed-lot 胜率：`{metrics['closed_lot_win_rate_pct']:.4f}%`

## Summary

{_md_table(summary)}

## Lot State Summary

{_md_table(lot_summary)}

## Event Timing Summary

{_md_table(event_summary)}

## State-Year Matrix

{_md_table(state_year)}

## Product-State Matrix

{_md_table(state_product, max_rows=30)}

## First Stop Bucket

{_md_table(first_stop_summary)}

## Quality Crosstab

{_md_table(quality_crosstab)}

## Atlas Manifest

{_md_table(atlas_manifest, max_rows=40)}

## 视觉观察

- path chart：`{PATH_CHART_OUT}`
  - 同时查看官方权益、回撤、broker10 和 stop/retry state 累计贡献。
- contribution chart：`{CONTRIB_CHART_OUT}`
  - 观察 `open_after_reentry` 是否能覆盖 `flat_no_reentry/flat_retry_failed` 的损失。
- state-year heatmap：`{STATE_YEAR_HEATMAP_OUT}`
  - 判断 stop/retry state 是否跨年稳定，避免只凭单年窗口。
- product heatmap：`{PRODUCT_HEATMAP_OUT}`
  - 判断贡献是否被少数产品块主导，避免产品补丁。
- first-stop timing chart：`{FIRST_STOP_CHART_OUT}`
  - 检查第一次 `0.5R` stop 的 bar index 是否能稳定区分成功/失败重试。
- minute atlas：`{OUTPUT_DIR}`
  - 对最差 retry_failed、最差 no_reentry、最佳 open_after_reentry 画 entry-day 分钟 K，标记 entry、0.5R stop、0.5R progress、first stop、reentry、retry failed。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：否。只读归因 C9 已有 stop/retry 事件，不新增参数、不按年份/品种/方向筛选。
- 运行后判断：否。`final_state` 明确标注为未来标签，只能解释，不可交易化；若下一步直接用 `open_after_reentry` 或单个 timing bucket 写规则就是过拟合。

## 继续价值反思

- 运行前判断：有价值。当前目标核心就是分钟级最小风险参与，而 stop/retry 是正式版已经存在的分钟级风控核心。
- 运行后判断：以决策为准；若 stop/retry 事件净负但成功重试有右尾，下一步只允许寻找 reentry 当刻可见、跨年跨品种稳定的结构，不允许用未来成功/失败标签。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_features = _load_features()
    events = _load_events()
    curve = _load_curve()
    features = _bind_events(raw_features, events)
    metrics = _official_metrics(curve, features)

    lot_summary = _lot_state_summary(features)
    event_summary = _event_summary(events)
    state_year = _state_year_matrix(features)
    state_product = _state_product_matrix(features)
    first_stop_summary = _first_stop_bucket_summary(features)
    quality_crosstab = _quality_crosstab(features)
    contribution = _contribution_curve(features)
    summary = _build_summary(metrics, lot_summary, event_summary, features)
    decision = _build_decision(metrics, lot_summary, event_summary, first_stop_summary, quality_crosstab, features)
    atlas_manifest = _plot_atlas(features)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    lot_summary.to_csv(LOT_STATE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    state_year.to_csv(STATE_YEAR_OUT, index=False, encoding="utf-8-sig")
    state_product.to_csv(STATE_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    first_stop_summary.to_csv(FIRST_STOP_BUCKET_OUT, index=False, encoding="utf-8-sig")
    quality_crosstab.to_csv(QUALITY_CROSSTAB_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(curve, contribution)
    _plot_contribution(contribution)
    _plot_state_year_heatmap(state_year)
    _plot_product_heatmap(state_product)
    _plot_first_stop_timing(features, first_stop_summary)
    _write_report(metrics, summary, decision, lot_summary, event_summary, state_year, state_product, first_stop_summary, quality_crosstab, atlas_manifest)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
