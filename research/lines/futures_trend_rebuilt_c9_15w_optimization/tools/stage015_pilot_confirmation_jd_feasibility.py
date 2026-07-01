from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage015"
MODEL_TAG = "stage015_pilot_confirmation_jd_feasibility_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage015_pilot_confirmation_jd_feasibility"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage015_pilot_confirmation_jd_feasibility"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
BACKTEST_OUTPUT_DIR = PORTFOLIO_DIR / "backtest_outputs"

STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
TRADES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_trades_{STAGE013_TAG}.csv"
ENTRY_RISK_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_entry_risk_{STAGE013_TAG}.csv"
ENTRY_CANDIDATES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_entry_candidates_{STAGE013_TAG}.csv"
PILOT_EVENTS_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_pilot_gate_events_{STAGE013_TAG}.csv"

FULL_MARKET_PREDICTIONS_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)

CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PILOT_RISK_LINK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pilot_risk_link_{MODEL_TAG}.csv"
PILOT_LOT_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pilot_lot_detail_{MODEL_TAG}.csv"
CONFIRMATION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_confirmation_summary_{MODEL_TAG}.csv"
ENTRY_VISIBLE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_visible_summary_{MODEL_TAG}.csv"
JD_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_jd_month_audit_{MODEL_TAG}.csv"
JD_FEASIBILITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_jd_feasibility_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FOCUS_START = pd.Timestamp("2022-01-01")
FOCUS_END = pd.Timestamp("2023-12-31")
HORIZONS = (3, 5, 10)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if pd.isna(value) if not isinstance(value, (str, bytes)) else False:
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _read_stage013_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(TRADES_PATH, encoding="utf-8-sig")
    entry_risk = pd.read_csv(ENTRY_RISK_PATH, encoding="utf-8-sig")
    entry_candidates = pd.read_csv(ENTRY_CANDIDATES_PATH, encoding="utf-8-sig")
    pilot_events = pd.read_csv(PILOT_EVENTS_PATH, encoding="utf-8-sig")
    for frame in (trades, entry_risk, entry_candidates, pilot_events):
        for column in ("datetime", "date"):
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
        if "date" in frame.columns:
            frame["date"] = frame["date"].dt.normalize()
        if "requested_start_month" in frame.columns:
            frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    return trades, entry_risk, entry_candidates, pilot_events


def _build_closed_lots_by_source(
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    closed_rows: list[pd.DataFrame] = []
    risk_link_rows: list[pd.DataFrame] = []
    for source, source_trades in trades.groupby("requested_start_month", sort=True):
        source_text = str(source)
        source_risk = entry_risk[entry_risk["requested_start_month"].astype(str).eq(source_text)].copy()
        source_candidates = entry_candidates[
            entry_candidates["requested_start_month"].astype(str).eq(source_text)
        ].copy()
        closed = s719._build_closed_lots(source_trades.copy(), source_risk.copy(), source_candidates.copy(), metadata)
        if not closed.empty:
            closed["requested_start_month"] = source_text
            closed_rows.append(closed)

        matched = s719._match_entry_risk_to_trades(source_trades.copy(), source_risk.copy())
        if matched:
            link = pd.DataFrame([{**row, "open_trade_id": trade_id} for trade_id, row in matched.items()])
            link["requested_start_month"] = source_text
            risk_link_rows.append(link)

    closed_all = pd.concat(closed_rows, ignore_index=True, sort=False) if closed_rows else pd.DataFrame()
    if not closed_all.empty:
        for column in ("entry_date", "exit_date"):
            closed_all[column] = pd.to_datetime(closed_all[column], errors="coerce").dt.normalize()
        closed_all["open_trade_id"] = closed_all["open_trade_id"].astype(str)
        closed_all = s719._finalize_path_efficiency(closed_all)

    risk_link = pd.concat(risk_link_rows, ignore_index=True, sort=False) if risk_link_rows else pd.DataFrame()
    if not risk_link.empty:
        risk_link["entry_index"] = pd.to_numeric(risk_link["entry_index"], errors="coerce").astype("Int64")
        risk_link["open_trade_id"] = risk_link["open_trade_id"].astype(str)
        risk_link["date"] = pd.to_datetime(risk_link["date"], errors="coerce").dt.normalize()
    return closed_all, risk_link


def _pilot_risk_link(pilot_events: pd.DataFrame, entry_risk: pd.DataFrame, risk_link: pd.DataFrame) -> pd.DataFrame:
    events = pilot_events.reset_index(drop=True).copy()
    events.insert(0, "pilot_event_id", np.arange(1, len(events) + 1))
    key = ["requested_start_month", "date", "contract_vt_symbol", "product_vt_symbol", "direction"]
    risk_cols = key + [
        "entry_index",
        "datetime",
        "signal",
        "entry_context",
        "selected_volume",
        "volume",
        "planned_entry_price",
        "entry_price",
        "stop_price",
        "risk_per_contract",
        "actual_risk_amount",
        "oi_price_confirm_passed",
        "oi_price_confirm_price_aligned",
        "oi_price_confirm_recent_prior_oi_sum_ratio",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "loss_streak",
        "profit_recovery_streak",
        "ai_product_pool_score",
        "ai_product_pool_rank",
    ]
    available_risk_cols = [column for column in risk_cols if column in entry_risk.columns]
    risk = entry_risk[available_risk_cols].copy()
    risk["entry_index"] = pd.to_numeric(risk["entry_index"], errors="coerce").astype("Int64")
    pilot = events.merge(risk, on=key, how="left", suffixes=("_event", "_risk"), indicator="risk_merge")
    link_cols = ["requested_start_month", "entry_index", "open_trade_id"]
    pilot = pilot.merge(risk_link[link_cols], on=["requested_start_month", "entry_index"], how="left")
    pilot["planned_extra_volume"] = (
        pd.to_numeric(pilot.get("stage013_pilot_gate_selected_volume_before"), errors="coerce").fillna(0.0)
        - pd.to_numeric(pilot.get("stage013_pilot_gate_selected_volume_after"), errors="coerce").fillna(0.0)
    ).clip(lower=0.0)
    return pilot


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _horizon_metrics(row: pd.Series) -> dict[str, Any]:
    vt_symbol = row.get("vt_symbol")
    direction = str(row.get("direction") or "")
    raw_entry_date = pd.to_datetime(row.get("entry_date"), errors="coerce")
    raw_exit_date = pd.to_datetime(row.get("exit_date"), errors="coerce")
    if pd.isna(raw_entry_date) or pd.isna(raw_exit_date):
        return {
            **{f"alive_to_{horizon}d": False for horizon in HORIZONS},
            **{f"confirm_{horizon}d_close_positive": False for horizon in HORIZONS},
            **{f"confirm_{horizon}d_mfe_ge_0_5r": False for horizon in HORIZONS},
            **{f"confirm_{horizon}d_combo": False for horizon in HORIZONS},
        }
    entry_date = pd.Timestamp(raw_entry_date).normalize()
    exit_date = pd.Timestamp(raw_exit_date).normalize()
    entry_price = _safe_float(row.get("entry_price"))
    exit_price = _safe_float(row.get("exit_price"))
    size = int(_safe_float(row.get("size"), 1.0))
    volume = _safe_float(row.get("volume"), 1.0)
    risk_amount = _safe_float(row.get("risk_amount"))
    planned_extra_volume = _safe_float(row.get("planned_extra_volume"), 0.0)
    result: dict[str, Any] = {}
    if pd.isna(entry_date) or pd.isna(exit_date) or entry_price <= 0:
        return result

    bars = s719._read_contract_bars(vt_symbol)
    if bars.empty:
        for horizon in HORIZONS:
            result[f"alive_to_{horizon}d"] = False
            result[f"confirm_{horizon}d_close_positive"] = False
            result[f"confirm_{horizon}d_mfe_ge_0_5r"] = False
            result[f"confirm_{horizon}d_combo"] = False
        return result

    held = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if held.empty:
        for horizon in HORIZONS:
            result[f"alive_to_{horizon}d"] = False
            result[f"confirm_{horizon}d_close_positive"] = False
            result[f"confirm_{horizon}d_mfe_ge_0_5r"] = False
            result[f"confirm_{horizon}d_combo"] = False
        return result

    for horizon in HORIZONS:
        prefix = f"{horizon}d"
        alive = len(held) >= horizon
        result[f"alive_to_{prefix}"] = bool(alive)
        if not alive:
            result[f"dir_close_return_{prefix}"] = np.nan
            result[f"mfe_{prefix}_r"] = np.nan
            result[f"mae_{prefix}_r"] = np.nan
            result[f"confirm_close_price_{prefix}"] = np.nan
            result[f"post_confirm_extra_pnl_{prefix}"] = 0.0
            result[f"confirm_{prefix}_close_positive"] = False
            result[f"confirm_{prefix}_mfe_ge_0_5r"] = False
            result[f"confirm_{prefix}_combo"] = False
            continue

        window = held.iloc[:horizon].copy()
        close_price = float(window.iloc[-1]["close"])
        if direction == "long":
            close_return = (close_price - entry_price) / entry_price
            favorable_cash = (window["high"] - entry_price) * size * volume
            adverse_cash = (entry_price - window["low"]) * size * volume
            post_confirm_unit_pnl = (exit_price - close_price) * size
        else:
            close_return = (entry_price - close_price) / entry_price
            favorable_cash = (entry_price - window["low"]) * size * volume
            adverse_cash = (window["high"] - entry_price) * size * volume
            post_confirm_unit_pnl = (close_price - exit_price) * size

        mfe_cash = float(favorable_cash.max()) if favorable_cash.notna().any() else np.nan
        mae_cash = float(adverse_cash.max()) if adverse_cash.notna().any() else np.nan
        mfe_r = mfe_cash / risk_amount if risk_amount and not np.isnan(risk_amount) else np.nan
        mae_r = mae_cash / risk_amount if risk_amount and not np.isnan(risk_amount) else np.nan
        close_positive = bool(close_return > 0)
        mfe_confirmed = bool(mfe_r >= 0.5) if not np.isnan(mfe_r) else False
        combo = bool(close_positive and mfe_confirmed and (np.isnan(mae_r) or mae_r <= 1.0))
        result[f"dir_close_return_{prefix}"] = close_return
        result[f"mfe_{prefix}_r"] = mfe_r
        result[f"mae_{prefix}_r"] = mae_r
        result[f"confirm_close_price_{prefix}"] = close_price
        result[f"post_confirm_extra_pnl_{prefix}"] = post_confirm_unit_pnl * planned_extra_volume
        result[f"confirm_{prefix}_close_positive"] = close_positive
        result[f"confirm_{prefix}_mfe_ge_0_5r"] = mfe_confirmed
        result[f"confirm_{prefix}_combo"] = combo
    return result


def _attach_pilot_lots(pilot: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    keep_closed = closed_lots.copy()
    keep_closed["open_trade_id"] = keep_closed["open_trade_id"].astype(str)
    pilot["open_trade_id"] = pilot["open_trade_id"].astype(str)
    detail = pilot.merge(
        keep_closed,
        on=["requested_start_month", "open_trade_id"],
        how="left",
        suffixes=("_pilot", ""),
        indicator="closed_lot_merge",
    )
    detail["entry_date"] = pd.to_datetime(detail["entry_date"], errors="coerce").dt.normalize()
    detail["exit_date"] = pd.to_datetime(detail["exit_date"], errors="coerce").dt.normalize()
    detail["entry_year"] = detail["entry_date"].dt.year
    detail["focus_2022_2023"] = detail["entry_date"].between(FOCUS_START, FOCUS_END, inclusive="both")
    detail["realized_pnl"] = pd.to_numeric(detail.get("realized_pnl"), errors="coerce")
    detail["r_multiple"] = pd.to_numeric(detail.get("r_multiple"), errors="coerce")
    detail["winner"] = detail["realized_pnl"].gt(0.0).astype(int)
    detail["planned_extra_volume"] = pd.to_numeric(detail["planned_extra_volume"], errors="coerce").fillna(0.0)
    detail["pilot_upper_bound_extra_pnl_from_entry"] = np.where(
        pd.to_numeric(detail.get("volume"), errors="coerce").fillna(0.0).gt(0.0),
        detail["realized_pnl"]
        / pd.to_numeric(detail.get("volume"), errors="coerce").replace(0.0, np.nan)
        * detail["planned_extra_volume"],
        np.nan,
    )

    metrics = [_horizon_metrics(row) for _, row in detail.iterrows()]
    metrics_df = pd.DataFrame(metrics)
    if not metrics_df.empty:
        detail = pd.concat([detail.reset_index(drop=True), metrics_df.reset_index(drop=True)], axis=1)
    return detail


def _bucket_rank(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number) or number <= 0:
        return "missing"
    if number <= 3:
        return "rank_1_3"
    if number <= 6:
        return "rank_4_6"
    if number <= 9:
        return "rank_7_9"
    return "rank_gt9"


def _bucket_drawdown(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return "missing"
    if number < 0.35:
        return "dd_30_35"
    if number < 0.45:
        return "dd_35_45"
    return "dd_ge45"


def _bucket_corr(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return "missing"
    if number < 0.3:
        return "corr_lt0.3"
    if number < 0.6:
        return "corr_0.3_0.6"
    return "corr_ge0.6"


def _bucket_loss_streak(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return "missing"
    if number <= 0:
        return "loss_0"
    if number <= 2:
        return "loss_1_2"
    return "loss_ge3"


def _scope_frames(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    matched = detail[detail["closed_lot_merge"].astype(str).eq("both")].copy()
    return {
        "all_matched_pilot_lots": matched,
        "focus_2022_2023_pilot_lots": matched[matched["focus_2022_2023"].fillna(False)].copy(),
    }


def _summary_stats(group: pd.DataFrame) -> dict[str, Any]:
    if group.empty:
        return {
            "count": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "avg_r": np.nan,
            "median_r": np.nan,
            "p10_r": np.nan,
            "p90_r": np.nan,
            "planned_extra_volume": 0.0,
            "pilot_upper_bound_extra_pnl_from_entry": 0.0,
        }
    return {
        "count": int(len(group)),
        "win_rate_pct": float(group["winner"].mean() * 100.0),
        "total_pnl": float(group["realized_pnl"].sum()),
        "avg_r": float(group["r_multiple"].mean()),
        "median_r": float(group["r_multiple"].median()),
        "p10_r": float(group["r_multiple"].quantile(0.10)),
        "p90_r": float(group["r_multiple"].quantile(0.90)),
        "planned_extra_volume": float(group["planned_extra_volume"].sum()),
        "pilot_upper_bound_extra_pnl_from_entry": float(group["pilot_upper_bound_extra_pnl_from_entry"].sum()),
    }


def _confirmation_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    flag_to_extra = {}
    for horizon in HORIZONS:
        prefix = f"{horizon}d"
        for kind in ("close_positive", "mfe_ge_0_5r", "combo"):
            flag_to_extra[f"confirm_{prefix}_{kind}"] = f"post_confirm_extra_pnl_{prefix}"

    for scope, frame in _scope_frames(detail).items():
        rows.append({"scope": scope, "feature": "baseline", "feature_value": "all", **_summary_stats(frame)})
        for flag, extra_column in flag_to_extra.items():
            if flag not in frame.columns:
                continue
            for value, group in frame.groupby(frame[flag].fillna(False).astype(bool), dropna=False):
                stats = _summary_stats(group)
                stats["post_confirm_extra_pnl"] = (
                    float(group.loc[group[flag].fillna(False).astype(bool), extra_column].sum())
                    if extra_column in group.columns
                    else 0.0
                )
                rows.append(
                    {
                        "scope": scope,
                        "feature": flag,
                        "feature_value": bool(value),
                        **stats,
                    }
                )
    return pd.DataFrame(rows)


def _entry_visible_summary(detail: pd.DataFrame) -> pd.DataFrame:
    data = detail[detail["closed_lot_merge"].astype(str).eq("both")].copy()
    if data.empty:
        return pd.DataFrame()
    data["oi_passed_bucket"] = np.where(
        pd.to_numeric(data.get("oi_price_confirm_passed"), errors="coerce").fillna(0).gt(0),
        "oi_passed",
        "oi_failed",
    )
    data["oi_aligned_bucket"] = np.where(
        pd.to_numeric(data.get("oi_price_confirm_price_aligned"), errors="coerce").fillna(0).gt(0),
        "oi_price_aligned",
        "oi_price_not_aligned",
    )
    data["ai_rank_bucket"] = data.get("ai_product_pool_rank", np.nan).map(_bucket_rank)
    data["drawdown_bucket"] = data.get("portfolio_drawdown_pct", np.nan).map(_bucket_drawdown)
    data["corr_bucket"] = data.get("same_direction_correlation_max_corr", np.nan).map(_bucket_corr)
    data["loss_streak_bucket"] = data.get("loss_streak", np.nan).map(_bucket_loss_streak)
    features = [
        "direction",
        "product_vt_symbol",
        "oi_passed_bucket",
        "oi_aligned_bucket",
        "ai_rank_bucket",
        "drawdown_bucket",
        "corr_bucket",
        "loss_streak_bucket",
    ]
    rows: list[dict[str, Any]] = []
    for scope, frame in _scope_frames(data).items():
        for feature in features:
            if feature not in frame.columns:
                continue
            for value, group in frame.groupby(feature, dropna=False):
                if len(group) < 5 and feature == "product_vt_symbol":
                    continue
                rows.append({"scope": scope, "feature": feature, "feature_value": str(value), **_summary_stats(group)})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["scope", "feature", "total_pnl"], ascending=[True, True, False]).reset_index(drop=True)


def _jd_feasibility() -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "eval_date",
        "product_vt_symbol",
        "window_id",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "simple_trend_suitability_score_percentile",
        "future_net_pnl_60d",
        "future_rank_pct_60d",
        "target_future_top_half_60d",
        "market_ret_60d",
        "market_trend_efficiency_60d",
        "net_pnl_sum_60d",
        "opened_count_sum_60d",
        "candidate_count_sum_60d",
    ]
    data = pd.read_csv(
        FULL_MARKET_PREDICTIONS_PATH,
        encoding="utf-8-sig",
        usecols=lambda column: column in columns,
    )
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce").dt.normalize()
    data["ai_rank_desc"] = data.groupby("eval_date")["predicted_product_suitability_probability"].rank(
        ascending=False,
        method="min",
    )
    data["simple_rank_desc"] = data.groupby("eval_date")["simple_trend_suitability_score"].rank(
        ascending=False,
        method="min",
    )
    data["product_count"] = data.groupby("eval_date")["product_vt_symbol"].transform("count")
    data["ai_top8"] = data["ai_rank_desc"].le(8)
    data["simple_top8"] = data["simple_rank_desc"].le(8)
    data["future_top_half"] = pd.to_numeric(data["target_future_top_half_60d"], errors="coerce").fillna(0).gt(0)
    jd = data[data["product_vt_symbol"].astype(str).eq("jd.DCE")].copy()
    jd["period"] = np.select(
        [
            jd["eval_date"].between(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-06-30"), inclusive="both"),
            jd["eval_date"].between(pd.Timestamp("2022-07-01"), pd.Timestamp("2022-12-31"), inclusive="both"),
            jd["eval_date"].between(pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"), inclusive="both"),
            jd["eval_date"].between(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31"), inclusive="both"),
        ],
        ["2022_h1", "2022_h2", "2023", "2024_2025"],
        default="other",
    )
    rows: list[dict[str, Any]] = []
    for scope, frame in {
        "jd_all_available_months": jd,
        "jd_focus_2022_2023": jd[jd["eval_date"].between(FOCUS_START, FOCUS_END, inclusive="both")],
        "jd_2022_h1": jd[jd["period"].eq("2022_h1")],
        "jd_2022_h2": jd[jd["period"].eq("2022_h2")],
        "jd_2023": jd[jd["period"].eq("2023")],
        "jd_2024_2025": jd[jd["period"].eq("2024_2025")],
    }.items():
        if frame.empty:
            continue
        rows.append(
            {
                "scope": scope,
                "month_count": int(len(frame)),
                "ai_top8_count": int(frame["ai_top8"].sum()),
                "simple_top8_count": int(frame["simple_top8"].sum()),
                "future_top_half_count": int(frame["future_top_half"].sum()),
                "future_top_half_rate_pct": float(frame["future_top_half"].mean() * 100.0),
                "mean_future_net_pnl_60d": float(frame["future_net_pnl_60d"].mean()),
                "median_future_net_pnl_60d": float(frame["future_net_pnl_60d"].median()),
                "mean_ai_rank": float(frame["ai_rank_desc"].mean()),
                "median_ai_rank": float(frame["ai_rank_desc"].median()),
                "mean_simple_rank": float(frame["simple_rank_desc"].mean()),
                "median_simple_rank": float(frame["simple_rank_desc"].median()),
                "best_ai_rank": float(frame["ai_rank_desc"].min()),
                "best_simple_rank": float(frame["simple_rank_desc"].min()),
            }
        )
    summary = pd.DataFrame(rows)
    return jd.sort_values("eval_date").reset_index(drop=True), summary


def _plot(detail: pd.DataFrame, confirmation_summary: pd.DataFrame, jd_month: pd.DataFrame) -> None:
    matched = detail[detail["closed_lot_merge"].astype(str).eq("both")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_curve, ax_flags, ax_jd, ax_focus = axes.flatten()

    if not matched.empty:
        curve = matched.sort_values("entry_date").copy()
        curve["cum_pnl"] = curve["realized_pnl"].fillna(0.0).cumsum()
        ax_curve.plot(curve["entry_date"], curve["cum_pnl"], color="#2563eb", linewidth=1.4)
        ax_curve.axhline(0.0, color="#111827", linewidth=0.8)
        ax_curve.set_title("Stage013 pilot lots cumulative realized PnL")
        ax_curve.grid(alpha=0.25)

        yearly = matched.groupby("entry_year")["realized_pnl"].sum()
        colors = np.where(yearly.values >= 0, "#059669", "#dc2626")
        ax_focus.bar(yearly.index.astype(str), yearly.values, color=colors, alpha=0.85)
        ax_focus.axhline(0.0, color="#111827", linewidth=0.8)
        ax_focus.set_title("Pilot lots PnL by entry year")
        ax_focus.tick_params(axis="x", rotation=30)
        ax_focus.grid(axis="y", alpha=0.25)

    if not confirmation_summary.empty:
        focus = confirmation_summary[
            confirmation_summary["scope"].eq("focus_2022_2023_pilot_lots")
            & confirmation_summary["feature_value"].astype(str).eq("True")
            & confirmation_summary["feature"].str.contains("combo|close_positive", regex=True)
        ].copy()
        focus = focus.sort_values("post_confirm_extra_pnl", ascending=False).head(8)
        if not focus.empty:
            labels = focus["feature"].str.replace("confirm_", "", regex=False).str.replace("_", " ", regex=False)
            ax_flags.barh(labels.iloc[::-1], focus["post_confirm_extra_pnl"].iloc[::-1], color="#f97316", alpha=0.85)
            ax_flags.axvline(0.0, color="#111827", linewidth=0.8)
            ax_flags.set_title("Focus 2022-2023 post-confirm extra PnL proxy")
            ax_flags.grid(axis="x", alpha=0.25)

    if not jd_month.empty:
        ax_jd.plot(jd_month["eval_date"], jd_month["ai_rank_desc"], color="#7c3aed", marker="o", markersize=3, linewidth=1)
        ax_jd.axhline(8, color="#dc2626", linewidth=0.9, linestyle="--")
        ax_jd.invert_yaxis()
        ax_jd.set_title("jd.DCE full-market AI rank (lower is better)")
        ax_jd.grid(alpha=0.25)

    fig.suptitle("Stage015 Pilot Confirmation and jd.DCE Feasibility", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _decision(
    closed_lots: pd.DataFrame,
    pilot: pd.DataFrame,
    detail: pd.DataFrame,
    confirmation_summary: pd.DataFrame,
    jd_summary: pd.DataFrame,
) -> dict[str, Any]:
    matched = detail[detail["closed_lot_merge"].astype(str).eq("both")].copy()
    focus = matched[matched["focus_2022_2023"].fillna(False)].copy()
    baseline_focus_pnl = float(focus["realized_pnl"].sum()) if not focus.empty else 0.0
    focus_flags = confirmation_summary[
        confirmation_summary["scope"].eq("focus_2022_2023_pilot_lots")
        & confirmation_summary["feature_value"].astype(str).eq("True")
    ].copy()
    best_flag = (
        focus_flags.sort_values("post_confirm_extra_pnl", ascending=False).head(1).to_dict("records")[0]
        if not focus_flags.empty
        else {}
    )
    jd_focus = (
        jd_summary[jd_summary["scope"].eq("jd_focus_2022_2023")].to_dict("records")[0]
        if not jd_summary.empty and jd_summary["scope"].eq("jd_focus_2022_2023").any()
        else {}
    )
    jd_2023 = (
        jd_summary[jd_summary["scope"].eq("jd_2023")].to_dict("records")[0]
        if not jd_summary.empty and jd_summary["scope"].eq("jd_2023").any()
        else {}
    )
    verdict = "stage015_readonly_attribution_no_live_change"
    next_step = (
        "pilot_confirmation_has_candidate_shape_but_needs_true_engine"
        if best_flag and float(best_flag.get("post_confirm_extra_pnl") or 0.0) > 0.0
        else "pilot_confirmation_not_enough_skip_true_engine"
    )
    jd_next = (
        "jd_non_overlapping_small_budget_only_if_confirmed"
        if jd_focus and float(jd_focus.get("future_top_half_rate_pct") or 0.0) >= 50.0
        else "jd_direct_add_not_supported_by_full_market_evidence"
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage_nature": "readonly_attribution_no_strategy_change",
        "decision": verdict,
        "next_step": next_step,
        "jd_next_step": jd_next,
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "closed_lot_count": int(len(closed_lots)),
        "pilot_event_count": int(len(pilot)),
        "pilot_risk_matched_count": int(pilot["entry_index"].notna().sum()) if "entry_index" in pilot.columns else 0,
        "pilot_closed_lot_matched_count": int(len(matched)),
        "focus_2022_2023_pilot_lot_count": int(len(focus)),
        "focus_2022_2023_pilot_realized_pnl": baseline_focus_pnl,
        "best_focus_confirmation_flag": best_flag,
        "jd_focus_2022_2023_summary": jd_focus,
        "jd_2023_summary": jd_2023,
        "output_files": {
            "closed_lots": str(CLOSED_LOTS_PATH),
            "pilot_risk_link": str(PILOT_RISK_LINK_PATH),
            "pilot_lot_detail": str(PILOT_LOT_DETAIL_PATH),
            "confirmation_summary": str(CONFIRMATION_SUMMARY_PATH),
            "entry_visible_summary": str(ENTRY_VISIBLE_SUMMARY_PATH),
            "jd_month_audit": str(JD_MONTH_AUDIT_PATH),
            "jd_feasibility_summary": str(JD_FEASIBILITY_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    detail: pd.DataFrame,
    confirmation_summary: pd.DataFrame,
    entry_visible_summary: pd.DataFrame,
    jd_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_confirm = confirmation_summary[
        confirmation_summary["scope"].eq("focus_2022_2023_pilot_lots")
    ].copy()
    focus_confirm = focus_confirm.sort_values(
        ["post_confirm_extra_pnl", "total_pnl"],
        ascending=[False, False],
        na_position="last",
    )
    visible_focus = entry_visible_summary[
        entry_visible_summary["scope"].eq("focus_2022_2023_pilot_lots")
    ].copy()
    lines = [
        "# Stage015 Pilot Confirmation 与 jd.DCE 非挤占可行性",
        "",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读归因；不改策略、不连接 CTP、不调用下单 API。",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision['next_step']}`；jd：`{decision['jd_next_step']}`",
        "",
        "## 核心计数",
        "",
        f"- closed-lot 总数：`{decision['closed_lot_count']}`",
        f"- pilot 事件数：`{decision['pilot_event_count']}`",
        f"- pilot -> entry_risk 匹配数：`{decision['pilot_risk_matched_count']}`",
        f"- pilot -> closed-lot 匹配数：`{decision['pilot_closed_lot_matched_count']}`",
        f"- 2022-2023 focus pilot lot 数：`{decision['focus_2022_2023_pilot_lot_count']}`",
        f"- 2022-2023 focus pilot lot 原始 1 手实际 PnL：`{decision['focus_2022_2023_pilot_realized_pnl']:.2f}`",
        "",
        "## 触发后确认信号",
        "",
        _md_table(focus_confirm.head(16)),
        "",
        "## 入场可见维度",
        "",
        _md_table(visible_focus.head(16)),
        "",
        "## jd.DCE full-market 旧证据",
        "",
        _md_table(jd_summary),
        "",
        "## 输出",
        "",
    ]
    for key, path in decision["output_files"].items():
        lines.append(f"- `{key}`：`{path}`")
    lines.extend(
        [
            "",
            "## 反思",
            "",
            "- 过拟合反思：否。本阶段只做事件级归因和旧 full-market 证据审计，没有改规则、扫日期、扫品种或扫阈值。",
            "- 继续价值反思：是。pilot 触发后的确认信号如果能在真实引擎里改善 2022-2023 左尾，才值得进入下一阶段；jd 当前证据更适合小预算非挤占验证，不适合直接加入共享 AI topN。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trades, entry_risk, entry_candidates, pilot_events = _read_stage013_frames()
    closed_lots, risk_link = _build_closed_lots_by_source(trades, entry_risk, entry_candidates)
    pilot = _pilot_risk_link(pilot_events, entry_risk, risk_link)
    detail = _attach_pilot_lots(pilot, closed_lots)
    confirmation_summary = _confirmation_summary(detail)
    entry_visible_summary = _entry_visible_summary(detail)
    jd_month, jd_summary = _jd_feasibility()
    decision = _decision(closed_lots, pilot, detail, confirmation_summary, jd_summary)

    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_RISK_LINK_PATH, index=False, encoding="utf-8-sig")
    detail.to_csv(PILOT_LOT_DETAIL_PATH, index=False, encoding="utf-8-sig")
    confirmation_summary.to_csv(CONFIRMATION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_visible_summary.to_csv(ENTRY_VISIBLE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    jd_month.to_csv(JD_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    jd_summary.to_csv(JD_FEASIBILITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(detail, confirmation_summary, jd_month)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(detail, confirmation_summary, entry_visible_summary, jd_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
