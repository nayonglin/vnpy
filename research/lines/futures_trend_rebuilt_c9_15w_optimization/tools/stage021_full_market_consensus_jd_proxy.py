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

import stage009_dense_start_goal_audit as s009


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage021"
MODEL_TAG = "stage021_full_market_consensus_jd_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"
STAGE_RECORD_DIR = LINE_DIR / "stages"
BACKTEST_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE020_OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_stage013_high_quality_add_risk_proxy"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE020_PREFIX = "rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy"
STAGE020_TAG = "stage020_stage013_high_quality_add_risk_proxy_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE013_CLOSED_LOTS_PATH = STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
STAGE020_CURVES_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_curves_{STAGE020_TAG}.csv"
STAGE020_SUMMARY_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_summary_{STAGE020_TAG}.csv"

FULL_MARKET_PREDICTIONS_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)

ADD_RISK_FRACTION = 0.25
AI_TOP_N = 8
SIMPLE_TOP_N = 8
CAPITAL = 150000.0
EPS = 1e-9
FOCUS_START = pd.Timestamp("2022-01-01")
FOCUS_END = pd.Timestamp("2023-12-31")

PREDICTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_market_predictions_ranked_{MODEL_TAG}.csv"
LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTOR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selector_summary_{MODEL_TAG}.csv"
JD_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_jd_month_audit_{MODEL_TAG}.csv"
JD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_jd_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _product_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _closed_lot_product_key(product: Any, vt_symbol: Any) -> str:
    product_text = str(product or "").strip()
    if "." in product_text:
        return product_text.lower()
    vt_text = str(vt_symbol or "").strip()
    if "." not in vt_text or not product_text:
        return product_text.lower()
    exchange = vt_text.rsplit(".", 1)[-1]
    return f"{product_text}.{exchange}".lower()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def _read_predictions() -> pd.DataFrame:
    usecols = [
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
        "market_realized_vol_60d",
        "market_ma20_over_ma60_60d",
        "candidate_count_sum_60d",
        "opened_count_sum_60d",
        "net_pnl_sum_60d",
    ]
    data = pd.read_csv(FULL_MARKET_PREDICTIONS_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["eval_date"])
    data["eval_date"] = data["eval_date"].dt.normalize()
    data["product_key"] = data["product_vt_symbol"].map(_product_key)
    for column in usecols:
        if column not in {"eval_date", "product_vt_symbol", "window_id"}:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["ai_rank_desc"] = (
        data.groupby("eval_date")["predicted_product_suitability_probability"]
        .rank(method="first", ascending=False)
        .astype("int64")
    )
    data["simple_rank_desc"] = (
        data.groupby("eval_date")["simple_trend_suitability_score"].rank(method="first", ascending=False).astype("int64")
    )
    data["product_count"] = data.groupby("eval_date")["product_vt_symbol"].transform("nunique").astype("int64")
    data["stage021_ai_top8"] = data["ai_rank_desc"].le(AI_TOP_N)
    data["stage021_simple_top8"] = data["simple_rank_desc"].le(SIMPLE_TOP_N)
    data["stage021_consensus_top8"] = data["stage021_ai_top8"] & data["stage021_simple_top8"]
    data["stage021_consensus_top8_jd"] = data["stage021_consensus_top8"] & data["product_key"].eq("jd.dce")
    return data.sort_values(["product_key", "eval_date"]).reset_index(drop=True)


def _selector_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    selectors = {
        "ai_top8": predictions["stage021_ai_top8"],
        "simple_top8": predictions["stage021_simple_top8"],
        "consensus_top8": predictions["stage021_consensus_top8"],
        "non_consensus": ~predictions["stage021_consensus_top8"],
    }
    for name, mask in selectors.items():
        frame = predictions[mask].copy()
        rows.append(
            {
                "selector": name,
                "row_count": int(len(frame)),
                "month_count": int(frame["eval_date"].nunique()),
                "product_count": int(frame["product_vt_symbol"].nunique()),
                "future_top_half_rate_pct": float(frame["target_future_top_half_60d"].mean() * 100.0)
                if len(frame)
                else np.nan,
                "mean_future_net_pnl_60d": float(frame["future_net_pnl_60d"].mean()) if len(frame) else np.nan,
                "median_future_net_pnl_60d": float(frame["future_net_pnl_60d"].median()) if len(frame) else np.nan,
                "mean_future_rank_pct_60d": float(frame["future_rank_pct_60d"].mean()) if len(frame) else np.nan,
                "mean_ai_rank": float(frame["ai_rank_desc"].mean()) if len(frame) else np.nan,
                "mean_simple_rank": float(frame["simple_rank_desc"].mean()) if len(frame) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _jd_audit(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    jd = predictions[predictions["product_key"].eq("jd.dce")].copy()
    jd["period"] = "other"
    jd.loc[jd["eval_date"].between("2022-01-01", "2022-06-30"), "period"] = "jd_2022_h1"
    jd.loc[jd["eval_date"].between("2022-07-01", "2022-12-31"), "period"] = "jd_2022_h2"
    jd.loc[jd["eval_date"].between("2023-01-01", "2023-12-31"), "period"] = "jd_2023"
    jd.loc[jd["eval_date"].between("2024-01-01", "2025-12-31"), "period"] = "jd_2024_2025"
    scopes = {
        "jd_all_available_months": jd.index == jd.index,
        "jd_focus_2022_2023": jd["eval_date"].between(FOCUS_START, FOCUS_END),
        "jd_2022_h1": jd["period"].eq("jd_2022_h1"),
        "jd_2022_h2": jd["period"].eq("jd_2022_h2"),
        "jd_2023": jd["period"].eq("jd_2023"),
        "jd_2024_2025": jd["period"].eq("jd_2024_2025"),
    }
    rows: list[dict[str, Any]] = []
    for scope, mask in scopes.items():
        frame = jd[mask].copy()
        rows.append(
            {
                "scope": scope,
                "month_count": int(len(frame)),
                "ai_top8_count": int(frame["stage021_ai_top8"].sum()),
                "simple_top8_count": int(frame["stage021_simple_top8"].sum()),
                "consensus_top8_count": int(frame["stage021_consensus_top8"].sum()),
                "future_top_half_count": int(frame["target_future_top_half_60d"].eq(1).sum()),
                "future_top_half_rate_pct": float(frame["target_future_top_half_60d"].mean() * 100.0)
                if len(frame)
                else np.nan,
                "mean_future_net_pnl_60d": float(frame["future_net_pnl_60d"].mean()) if len(frame) else np.nan,
                "median_future_net_pnl_60d": float(frame["future_net_pnl_60d"].median()) if len(frame) else np.nan,
                "mean_ai_rank": float(frame["ai_rank_desc"].mean()) if len(frame) else np.nan,
                "median_ai_rank": float(frame["ai_rank_desc"].median()) if len(frame) else np.nan,
                "mean_simple_rank": float(frame["simple_rank_desc"].mean()) if len(frame) else np.nan,
                "median_simple_rank": float(frame["simple_rank_desc"].median()) if len(frame) else np.nan,
            }
        )
    keep = [
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "future_net_pnl_60d",
        "future_rank_pct_60d",
        "target_future_top_half_60d",
        "ai_rank_desc",
        "simple_rank_desc",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "market_trend_efficiency_60d",
        "market_realized_vol_60d",
        "market_ma20_over_ma60_60d",
        "period",
    ]
    return jd[keep].sort_values("eval_date").reset_index(drop=True), pd.DataFrame(rows)


def _build_lot_deltas(predictions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = pd.read_csv(STAGE013_CLOSED_LOTS_PATH, encoding="utf-8-sig", parse_dates=["entry_date", "exit_date"])
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["product_key"] = [
        _closed_lot_product_key(product, vt_symbol)
        for product, vt_symbol in zip(closed["product"], closed["vt_symbol"], strict=False)
    ]
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)
    preds = predictions.sort_values(["product_key", "eval_date"]).copy()
    lots = closed.sort_values(["product_key", "entry_date"]).copy()
    prediction_columns = [column for column in preds.columns if column != "product_key"]
    merged_frames: list[pd.DataFrame] = []
    for product_key, lot_group in lots.groupby("product_key", sort=False):
        left = lot_group.sort_values("entry_date").copy()
        right = preds[preds["product_key"].eq(product_key)].sort_values("eval_date").drop(columns=["product_key"])
        if right.empty:
            out = left.copy()
            for column in prediction_columns:
                if column not in out.columns:
                    out[column] = np.nan
        else:
            out = pd.merge_asof(
                left,
                right,
                left_on="entry_date",
                right_on="eval_date",
                direction="backward",
                allow_exact_matches=True,
            )
        merged_frames.append(out)
    merged = pd.concat(merged_frames, ignore_index=True, sort=False) if merged_frames else pd.DataFrame()
    merged["stage021_prediction_matched"] = merged["eval_date"].notna()
    bool_cols = ["stage021_ai_top8", "stage021_simple_top8", "stage021_consensus_top8"]
    for column in bool_cols:
        merged[column] = merged[column].eq(True)
    merged["stage021_selected_for_consensus_proxy"] = merged["stage021_consensus_top8"]
    merged["stage021_add_risk_fraction"] = ADD_RISK_FRACTION
    merged["stage021_proxy_delta_pnl"] = np.where(
        merged["stage021_selected_for_consensus_proxy"],
        merged["realized_pnl"] * ADD_RISK_FRACTION,
        0.0,
    )
    selected = merged[merged["stage021_selected_for_consensus_proxy"]].copy()
    focus = selected[selected["entry_date"].between(FOCUS_START, FOCUS_END)].copy()
    keep = [
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "volume",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "eval_date",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "ai_rank_desc",
        "simple_rank_desc",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "stage021_prediction_matched",
        "stage021_add_risk_fraction",
        "stage021_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "prediction_matched_lot_count": int(merged["stage021_prediction_matched"].sum()),
        "prediction_match_rate_pct": float(merged["stage021_prediction_matched"].mean() * 100.0) if len(merged) else np.nan,
        "selected_lots": int(len(selected)),
        "selected_realized_pnl": float(selected["realized_pnl"].sum()) if len(selected) else 0.0,
        "total_proxy_delta_pnl": float(selected["stage021_proxy_delta_pnl"].sum()) if len(selected) else 0.0,
        "focus_selected_lots": int(len(focus)),
        "focus_selected_realized_pnl": float(focus["realized_pnl"].sum()) if len(focus) else 0.0,
        "focus_total_proxy_delta_pnl": float(focus["stage021_proxy_delta_pnl"].sum()) if len(focus) else 0.0,
    }
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True), audit


def _build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    for column in ["account_equity", "stage020_account_equity"]:
        curves[column] = pd.to_numeric(curves[column], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage021_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage021_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage021_proxy_delta_pnl": "stage021_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage021_daily_delta"] = pd.to_numeric(merged["stage021_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage021_cum_delta"] = g["stage021_daily_delta"].cumsum()
        g["stage021_consensus_account_equity"] = g["account_equity"] + g["stage021_cum_delta"]
        g["stage021_combo_account_equity"] = g["stage020_account_equity"] + g["stage021_cum_delta"]
        g["stage021_consensus_nav"] = g["stage021_consensus_account_equity"] / CAPITAL
        g["stage021_combo_nav"] = g["stage021_combo_account_equity"] / CAPITAL
        g["stage021_consensus_drawdown_pct"] = _drawdown_pct(g["stage021_consensus_account_equity"])
        g["stage021_combo_drawdown_pct"] = _drawdown_pct(g["stage021_combo_account_equity"])
        frames.append(g)
    proxy = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _summarize_curve(curve: pd.DataFrame, equity_column: str, variant: str) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data[equity_column], errors="coerce")
    return {
        "variant": variant,
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _summary(proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    variants = [
        ("stage013_engine", "account_equity"),
        ("stage020_high_quality_proxy", "stage020_account_equity"),
        ("stage021_consensus_proxy", "stage021_consensus_account_equity"),
        ("stage021_combo_stage020_plus_consensus", "stage021_combo_account_equity"),
    ]
    for start, group in proxy_curves.groupby("requested_start_month"):
        for variant, column in variants:
            rows.append(_summarize_curve(group, column, variant))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    wide["combo_return_delta_pp_vs_stage020"] = (
        wide["total_return_pct_stage021_combo_stage020_plus_consensus"]
        - wide["total_return_pct_stage020_high_quality_proxy"]
    )
    wide["combo_maxdd_delta_pp_vs_stage020"] = (
        wide["max_dd_pct_stage021_combo_stage020_plus_consensus"] - wide["max_dd_pct_stage020_high_quality_proxy"]
    )
    wide["consensus_return_delta_pp_vs_stage013"] = (
        wide["total_return_pct_stage021_consensus_proxy"] - wide["total_return_pct_stage013_engine"]
    )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    mapping = {
        "stage013_engine": "account_equity",
        "stage020_high_quality_proxy": "stage020_account_equity",
        "stage021_consensus_proxy": "stage021_consensus_account_equity",
        "stage021_combo_stage020_plus_consensus": "stage021_combo_account_equity",
    }
    for variant, column in mapping.items():
        frame = proxy_curves[["requested_start_month", "date", column]].copy()
        frame.rename(columns={column: "equity"}, inplace=True)
        frame["variant"] = variant
        parts.append(frame)
    curves = pd.concat(parts, ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009._run_audit(curves)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(BASE_STAGE006_SUMMARY_PATH, encoding="utf-8-sig")
    base = base[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    wide = _wide_summary(summary)
    merged = base.merge(wide, on="requested_start_month", how="inner")
    for variant in [
        "stage021_consensus_proxy",
        "stage021_combo_stage020_plus_consensus",
    ]:
        merged[f"{variant}_vs_base_stage006_return_ratio"] = (
            merged[f"total_return_pct_{variant}"]
            / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
        )
        merged[f"{variant}_vs_stage013_return_ratio"] = (
            merged[f"total_return_pct_{variant}"]
            / pd.to_numeric(merged["total_return_pct_stage013_engine"], errors="coerce").replace(0.0, np.nan)
        )
        merged[f"{variant}_passes_80pct_retention_vs_base_stage006"] = (
            merged[f"{variant}_vs_base_stage006_return_ratio"].ge(0.80).astype("int64")
        )
        merged[f"{variant}_passes_80pct_retention_vs_stage013"] = (
            merged[f"{variant}_vs_stage013_return_ratio"].ge(0.80).astype("int64")
        )
    return merged


def _strict_metrics(aggregate: pd.DataFrame, variant: str) -> dict[str, Any]:
    frame = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    return {
        f"{variant}_all_gt1y_window_count": int(frame["window_count"].sum()) if not frame.empty else 0,
        f"{variant}_all_gt1y_negative_count": int(frame["negative_count"].sum()) if not frame.empty else 0,
        f"{variant}_all_gt1y_min_return_pct": float(frame["min_return_pct"].min()) if not frame.empty else np.nan,
        f"{variant}_to_final_negative_count": int(final["negative_count"].sum()) if not final.empty else 0,
        f"{variant}_to_final_min_return_pct": float(final["min_return_pct"].min()) if not final.empty else np.nan,
    }


def _plot(wide: pd.DataFrame, aggregate: pd.DataFrame, proxy_curves: pd.DataFrame, jd_month: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    x = np.arange(len(wide))
    labels = wide["requested_start_month"].astype(str).tolist()

    ax = axes[0, 0]
    ax.bar(
        x,
        wide["combo_return_delta_pp_vs_stage020"],
        color=np.where(wide["combo_return_delta_pp_vs_stage020"].ge(0), "#16a34a", "#dc2626"),
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right")
    ax.set_title("Stage021 Combo Return Delta vs Stage020")
    ax.set_ylabel("return delta pp")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    variants = [
        "stage020_high_quality_proxy",
        "stage021_consensus_proxy",
        "stage021_combo_stage020_plus_consensus",
    ]
    summary = (
        all_scope[all_scope["variant"].isin(variants)]
        .groupby("variant", as_index=False)
        .agg(negative_count=("negative_count", "sum"), min_return_pct=("min_return_pct", "min"))
    )
    x2 = np.arange(len(summary))
    ax.bar(x2, summary["negative_count"], color=["#64748b", "#2563eb", "#dc2626"][: len(summary)])
    ax.set_xticks(x2)
    ax.set_xticklabels(summary["variant"].tolist(), rotation=20, ha="right", fontsize=8)
    ax.set_title("Strict >1Y Negative Windows")
    ax.set_ylabel("negative windows")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    for start, group in proxy_curves.groupby("requested_start_month"):
        g = group.sort_values("date")
        ax.plot(g["date"], g["stage021_combo_account_equity"], linewidth=0.9, alpha=0.72, label=str(start))
    ax.axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Stage021 Combo Absolute Equity")
    ax.set_ylabel("account equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=6, ncol=3, loc="best")

    ax = axes[1, 1]
    if not jd_month.empty:
        colors = np.where(jd_month["stage021_consensus_top8"], "#16a34a", "#94a3b8")
        ax.bar(pd.to_datetime(jd_month["eval_date"]), jd_month["future_net_pnl_60d"], width=20, color=colors)
    ax.axhline(0, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("jd.DCE Future 60D PnL; green=AI+simple consensus top8")
    ax.set_ylabel("future_net_pnl_60d")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    lot_audit: dict[str, Any],
    jd_summary: pd.DataFrame,
    selector_summary: pd.DataFrame,
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    wide = _wide_summary(summary)
    result: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selector": f"full_market_ai_top{AI_TOP_N}_and_simple_top{SIMPLE_TOP_N}",
        "add_risk_fraction": ADD_RISK_FRACTION,
        "audit_type": "stage013_closed_lot_read_only_full_market_consensus_add_risk_proxy",
        "stage013_closed_lot_count": lot_audit["stage013_closed_lot_count"],
        "prediction_match_rate_pct": lot_audit["prediction_match_rate_pct"],
        "selected_lots": lot_audit["selected_lots"],
        "selected_realized_pnl": lot_audit["selected_realized_pnl"],
        "total_proxy_delta_pnl": lot_audit["total_proxy_delta_pnl"],
        "focus_selected_lots": lot_audit["focus_selected_lots"],
        "focus_selected_realized_pnl": lot_audit["focus_selected_realized_pnl"],
        "focus_total_proxy_delta_pnl": lot_audit["focus_total_proxy_delta_pnl"],
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(summary["requested_start_month"].nunique()),
        "combo_min_return_pct": float(wide["total_return_pct_stage021_combo_stage020_plus_consensus"].min()),
        "combo_median_return_pct": float(wide["total_return_pct_stage021_combo_stage020_plus_consensus"].median()),
        "combo_worst_max_dd_pct": float(wide["max_dd_pct_stage021_combo_stage020_plus_consensus"].min()),
        "combo_median_max_dd_pct": float(wide["max_dd_pct_stage021_combo_stage020_plus_consensus"].median()),
        "combo_return_improved_count_vs_stage020": int(wide["combo_return_delta_pp_vs_stage020"].gt(EPS).sum()),
        "combo_return_unchanged_count_vs_stage020": int(wide["combo_return_delta_pp_vs_stage020"].abs().le(EPS).sum()),
        "combo_return_worse_count_vs_stage020": int(wide["combo_return_delta_pp_vs_stage020"].lt(-EPS).sum()),
        "combo_maxdd_improved_count_vs_stage020": int(wide["combo_maxdd_delta_pp_vs_stage020"].gt(EPS).sum()),
        "combo_maxdd_unchanged_count_vs_stage020": int(wide["combo_maxdd_delta_pp_vs_stage020"].abs().le(EPS).sum()),
        "combo_maxdd_worse_count_vs_stage020": int(wide["combo_maxdd_delta_pp_vs_stage020"].lt(-EPS).sum()),
        "combo_retention_vs_base_stage006_pass_count": int(
            retention["stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_base_stage006"].sum()
        ),
        "combo_retention_vs_stage013_pass_count": int(
            retention["stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_stage013"].sum()
        ),
        "retention_rows": int(len(retention)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following literature supports diversification, volatility-aware sizing, and breadth filters, "
            "but warns that sizing improvements are metric-dependent. Stage021 therefore uses one fixed consensus "
            "selector from existing full-market AI probability and simple trend rank, plus one fixed add-risk fraction."
        ),
        "overfit_reflection_before": (
            "否。Stage021 不按最差窗口、品种方向或年度调参，只固定 full-market AI top8 与 simple trend top8 共识。"
        ),
        "continue_value_before": (
            "有。Stage020 证明高质量标签加风险不够，需要验证 full-market 选择器和 jd 非挤占候选是否能补剩余恢复段。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只读归因，不根据结果改 topN、比例或过滤条件；若用 2022H1/2023 事后分段写规则会过拟合。"
        ),
        "outputs": {
            "predictions": str(PREDICTIONS_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
            "curves": str(CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "selector_summary": str(SELECTOR_SUMMARY_PATH),
            "jd_month_audit": str(JD_MONTH_AUDIT_PATH),
            "jd_summary": str(JD_SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    for variant in [
        "stage013_engine",
        "stage020_high_quality_proxy",
        "stage021_consensus_proxy",
        "stage021_combo_stage020_plus_consensus",
    ]:
        result.update(_strict_metrics(aggregate, variant))

    combo_negative = result["stage021_combo_stage020_plus_consensus_all_gt1y_negative_count"]
    stage020_negative = result["stage020_high_quality_proxy_all_gt1y_negative_count"]
    retention_pass = result["combo_retention_vs_base_stage006_pass_count"] == result["retention_rows"]
    if combo_negative == 0 and retention_pass:
        decision = "stage021_proxy_meets_goal_requires_true_engine"
    elif combo_negative < stage020_negative and retention_pass:
        decision = "stage021_proxy_improves_but_goal_not_met"
    else:
        decision = "stage021_consensus_proxy_not_enough"
    result["decision"] = decision
    jd_all = jd_summary[jd_summary["scope"].eq("jd_all_available_months")]
    jd_focus = jd_summary[jd_summary["scope"].eq("jd_focus_2022_2023")]
    result["jd_all_consensus_count"] = int(jd_all["consensus_top8_count"].iloc[0]) if not jd_all.empty else 0
    result["jd_focus_consensus_count"] = int(jd_focus["consensus_top8_count"].iloc[0]) if not jd_focus.empty else 0
    consensus = selector_summary[selector_summary["selector"].eq("consensus_top8")]
    result["consensus_future_top_half_rate_pct"] = (
        float(consensus["future_top_half_rate_pct"].iloc[0]) if not consensus.empty else np.nan
    )
    result["consensus_mean_future_net_pnl_60d"] = (
        float(consensus["mean_future_net_pnl_60d"].iloc[0]) if not consensus.empty else np.nan
    )
    if decision == "stage021_proxy_improves_but_goal_not_met":
        result["continue_value_after"] = (
            "有，但只能作为新信息源候选。full-market 共识若降低负窗口但未达标，应转真实引擎小预算验证或继续找非价格信息。"
        )
    else:
        result["continue_value_after"] = (
            "有，但不应继续调 topN 或比例。若共识不能改善 Stage020，应把 jd 保留为非挤占观察，转向账户生存线或外生信息。"
        )
    return result


def _write_report(
    decision: dict[str, Any],
    wide: pd.DataFrame,
    selector_summary: pd.DataFrame,
    jd_summary: pd.DataFrame,
    jd_month: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> None:
    strict = aggregate[
        aggregate["variant"].isin(
            [
                "stage020_high_quality_proxy",
                "stage021_consensus_proxy",
                "stage021_combo_stage020_plus_consensus",
            ]
        )
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    lines = [
        "# Stage021 full-market 共识选择器与 jd 非挤占只读代理",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读代理；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- 选择器：`AI top{AI_TOP_N} AND simple trend top{SIMPLE_TOP_N}`。",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随资料支持分散化、目标波动和市场广度思路，但也强调不同 sizing 指标会给出不同赢家。",
        "- 本阶段不扫 topN、不扫倍率，只用一个 full-market AI 与简单趋势共识选择器做只读验证。",
        "- jd 只按非挤占候选审计；不得直接塞入共享 AI topN。",
        "",
        "## 核心结果",
        "",
        f"- selected lots：`{decision['selected_lots']}`；Stage013 realized PnL `{decision['selected_realized_pnl']:,.2f}`；代理增量 `{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- focus 2022-2023 selected lots：`{decision['focus_selected_lots']}`；realized PnL `{decision['focus_selected_realized_pnl']:,.2f}`。",
        f"- Stage020 严格负窗口：`{decision['stage020_high_quality_proxy_all_gt1y_negative_count']}`；Stage021 combo 严格负窗口：`{decision['stage021_combo_stage020_plus_consensus_all_gt1y_negative_count']}`。",
        f"- Stage021 combo 最差严格收益：`{decision['stage021_combo_stage020_plus_consensus_all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage021_combo_stage020_plus_consensus_to_final_negative_count']}`；最差 `{decision['stage021_combo_stage020_plus_consensus_to_final_min_return_pct']:.4f}%`。",
        f"- combo 收益改善/不变/变差 vs Stage020：`{decision['combo_return_improved_count_vs_stage020']}/{decision['combo_return_unchanged_count_vs_stage020']}/{decision['combo_return_worse_count_vs_stage020']}`。",
        f"- combo 回撤改善/不变/变差 vs Stage020：`{decision['combo_maxdd_improved_count_vs_stage020']}/{decision['combo_maxdd_unchanged_count_vs_stage020']}/{decision['combo_maxdd_worse_count_vs_stage020']}`。",
        f"- combo 80% 收益保留 vs Stage006：`{decision['combo_retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`。",
        "",
        "## 选择器统计",
        "",
        _md_table(selector_summary, max_rows=20),
        "",
        "## jd 审计",
        "",
        _md_table(jd_summary, max_rows=20),
        "",
        "## jd 月度明细",
        "",
        _md_table(
            jd_month[
                [
                    "eval_date",
                    "future_net_pnl_60d",
                    "future_rank_pct_60d",
                    "ai_rank_desc",
                    "simple_rank_desc",
                    "stage021_ai_top8",
                    "stage021_simple_top8",
                    "stage021_consensus_top8",
                    "period",
                ]
            ],
            max_rows=60,
        ),
        "",
        "## 多起点摘要",
        "",
        _md_table(
            wide[
                [
                    "requested_start_month",
                    "total_return_pct_stage020_high_quality_proxy",
                    "total_return_pct_stage021_combo_stage020_plus_consensus",
                    "combo_return_delta_pp_vs_stage020",
                    "max_dd_pct_stage020_high_quality_proxy",
                    "max_dd_pct_stage021_combo_stage020_plus_consensus",
                    "combo_maxdd_delta_pp_vs_stage020",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 密集目标审计",
        "",
        _md_table(strict, max_rows=60),
        "",
        "## 收益保留",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage021_combo_stage020_plus_consensus_vs_base_stage006_return_ratio",
                    "stage021_combo_stage020_plus_consensus_vs_stage013_return_ratio",
                    "stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_base_stage006",
                    "stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 增量 lot 样本",
        "",
        _md_table(lot_deltas, max_rows=30),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in decision["outputs"].items():
        lines.append(f"- {name}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    wide: pd.DataFrame,
    selector_summary: pd.DataFrame,
    jd_summary: pd.DataFrame,
    retention: pd.DataFrame,
) -> Path:
    timestamp = datetime.now()
    path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage021_full_market_consensus_jd_proxy.md"
    lines = [
        "# Stage021 full-market 共识选择器与 jd 非挤占只读代理",
        "",
        f"- 记录时间：`{timestamp:%Y-%m-%dT%H:%M}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增参数：`selector=AI top{AI_TOP_N} AND simple trend top{SIMPLE_TOP_N}`、`stage021_add_risk_fraction=0.25`。",
        "- 修改参数：无，Stage013/Stage020/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 本阶段只读代理，不新增真实交易规则、不接实盘。",
        "",
        "## 调研和判断结论",
        "",
        "- 外部趋势跟随资料支持分散化、目标波动和市场广度，但 sizing 没有普适免费午餐。",
        "- 本阶段只跑一个 full-market AI 与 simple trend 共识选择器，不扫 topN、倍率、品种或日期。",
        "- jd 只能先按非挤占候选审计，不能直接塞入共享 AI topN。",
        "",
        "## 代理结果",
        "",
        f"- selected lots：`{decision['selected_lots']}`。",
        f"- Stage013 realized PnL：`{decision['selected_realized_pnl']:,.2f}`。",
        f"- 代理增量 PnL：`{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- focus 2022-2023 selected realized PnL：`{decision['focus_selected_realized_pnl']:,.2f}`。",
        f"- 严格任意结束日 `>1` 年负窗口：Stage020 `{decision['stage020_high_quality_proxy_all_gt1y_negative_count']}` -> Stage021 combo `{decision['stage021_combo_stage020_plus_consensus_all_gt1y_negative_count']}`。",
        f"- Stage021 combo 严格最差收益：`{decision['stage021_combo_stage020_plus_consensus_all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage021_combo_stage020_plus_consensus_to_final_negative_count']}`，最差 `{decision['stage021_combo_stage020_plus_consensus_to_final_min_return_pct']:.4f}%`。",
        f"- 收益保留 vs Stage006：`{decision['combo_retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage020：`{decision['combo_return_improved_count_vs_stage020']}/{decision['combo_return_unchanged_count_vs_stage020']}/{decision['combo_return_worse_count_vs_stage020']}`。",
        f"- 回撤改善/不变/变差 vs Stage020：`{decision['combo_maxdd_improved_count_vs_stage020']}/{decision['combo_maxdd_unchanged_count_vs_stage020']}/{decision['combo_maxdd_worse_count_vs_stage020']}`。",
        "",
        "## 选择器统计",
        "",
        _md_table(selector_summary, max_rows=20),
        "",
        "## jd 摘要",
        "",
        _md_table(jd_summary, max_rows=20),
        "",
        "## 多起点摘要",
        "",
        _md_table(
            wide[
                [
                    "requested_start_month",
                    "total_return_pct_stage020_high_quality_proxy",
                    "total_return_pct_stage021_combo_stage020_plus_consensus",
                    "combo_return_delta_pp_vs_stage020",
                    "max_dd_pct_stage020_high_quality_proxy",
                    "max_dd_pct_stage021_combo_stage020_plus_consensus",
                    "combo_maxdd_delta_pp_vs_stage020",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 收益保留摘要",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage021_combo_stage020_plus_consensus_vs_base_stage006_return_ratio",
                    "stage021_combo_stage020_plus_consensus_vs_stage013_return_ratio",
                    "stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_base_stage006",
                    "stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 文件",
        "",
    ]
    for name, output_path in decision["outputs"].items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(
        [
            "",
            "## 后续规划和 TODO",
            "",
            "- 若严格负窗口仍未清零，不继续调 topN 或加风险比例；转真实引擎前置生存约束或新外生信息源。",
            "- 若 jd 共识月份仍不稳定，jd 只保留为非挤占观察，不直接加入共享 AI topN。",
            "",
            "## 反思",
            "",
            f"- 过拟合反思：{decision['overfit_reflection_after']}",
            f"- 继续价值反思：{decision['continue_value_after']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    predictions = _read_predictions()
    selector_summary = _selector_summary(predictions)
    jd_month, jd_summary = _jd_audit(predictions)
    lot_deltas, lot_audit = _build_lot_deltas(predictions)
    base_curves = pd.read_csv(STAGE020_CURVES_PATH, encoding="utf-8-sig", parse_dates=["date"])
    proxy_curves, unmatched_delta_dates = _build_proxy_curves(base_curves, lot_deltas)
    summary = _summary(proxy_curves)
    wide = _wide_summary(summary)
    aggregate, to_final, fixed, worst = _goal_audit(proxy_curves)
    retention = _retention(summary)
    decision = _decision(
        summary,
        aggregate,
        retention,
        lot_audit,
        jd_summary,
        selector_summary,
        unmatched_delta_dates,
    )
    _plot(wide, aggregate, proxy_curves, jd_month)

    predictions.to_csv(PREDICTIONS_PATH, index=False, encoding="utf-8-sig")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    proxy_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    selector_summary.to_csv(SELECTOR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    jd_month.to_csv(JD_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    jd_summary.to_csv(JD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, wide, selector_summary, jd_summary, jd_month, aggregate, retention, lot_deltas)
    stage_record = _write_stage_record(decision, wide, selector_summary, jd_summary, retention)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
