from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import hashlib
import json
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
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
for candidate in (str(PORTFOLIO_DIR), str(UPSTREAM_TOOLS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import build_qmt_roll_stage182_ai_product_pool_live_inference_runner as s182
import stage013_account_state_pilot_gate_engine as s013
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage061"
MODEL_TAG = "stage061_stage013_frozen_ai_promotion_ab_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage061_stage013_frozen_ai_promotion_ab"
REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
TARGET_EVAL_DATE = pd.Timestamp("2026-05-29")
SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage061_stage013_frozen_ai_promotion_ab"
STAGES_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = ROOT / "back_log.md"

CURRENT_COMBINED_AI_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)
STAGE013_SAVED_AI_AUDIT_PATH = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "outputs"
    / "stage013_account_state_pilot_gate_engine"
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_ai_pool_audit_stage013_account_state_pilot_gate_engine_v1.csv"
)

GENERATED_LIVE_POOL_PATH = OUT / f"{OUTPUT_PREFIX}_generated_live_pool_20260529_{MODEL_TAG}.csv"
GENERATED_LIVE_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_generated_live_eligibility_20260529_{MODEL_TAG}.csv"
FROZEN_AI_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_frozen_ai_eligibility_{MODEL_TAG}.csv"
AI_REPAIR_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_repair_audit_{MODEL_TAG}.json"

OFFICIAL_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_official_summary_{MODEL_TAG}.csv"
STAGE013_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_summary_{MODEL_TAG}.csv"
PAIR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUT / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
OFFICIAL_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_official_curves_{MODEL_TAG}.csv.gz"
STAGE013_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_curves_{MODEL_TAG}.csv.gz"
PAIR_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_pair_curves_{MODEL_TAG}.csv.gz"
OFFICIAL_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_official_entry_candidates_{MODEL_TAG}.csv.gz"
STAGE013_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_entry_candidates_{MODEL_TAG}.csv.gz"
OFFICIAL_AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_official_ai_month_audit_{MODEL_TAG}.csv"
STAGE013_AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_ai_month_audit_{MODEL_TAG}.csv"
POOL_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_frozen_ai_pool_audit_{MODEL_TAG}.csv"
ABSOLUTE_EQUITY_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_absolute_equity_grid_{MODEL_TAG}.png"
RELATIVE_GAP_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_relative_gap_grid_{MODEL_TAG}.png"
SUMMARY_BAR_PATH = OUT / f"{OUTPUT_PREFIX}_summary_bar_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
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


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp, prefix: str) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / float(OFFICIAL_LIVE_CAPITAL)
    drawdown = _drawdown_pct(equity)
    end_equity = float(equity.iloc[-1])
    return {
        "version": prefix,
        "requested_start": _date_text(requested_start),
        "requested_start_month": _start_month_text(requested_start),
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "account_capital": float(OFFICIAL_LIVE_CAPITAL),
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / float(OFFICIAL_LIVE_CAPITAL) - 1.0) * 100.0),
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else 0.0,
        "sharpe": _daily_sharpe(nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "final_nav": float(nav.iloc[-1]),
    }


def _products_for_eval(frame: pd.DataFrame, eval_date: pd.Timestamp) -> list[str]:
    selected = frame[pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize().eq(eval_date)].copy()
    if selected.empty:
        return []
    selected["score_rank"] = pd.to_numeric(selected["score_rank"], errors="coerce").fillna(9999)
    return selected.sort_values(["score_rank", "product_vt_symbol"])["product_vt_symbol"].astype(str).tolist()


def _saved_products_for_eval(path: Path, eval_date: pd.Timestamp) -> list[str]:
    if not path.exists():
        return []
    audit = pd.read_csv(path)
    rows = audit[pd.to_datetime(audit["eval_date"], errors="coerce").dt.normalize().eq(eval_date)]
    if rows.empty:
        return []
    text = str(rows.iloc[0].get("products", "") or "")
    return [item for item in text.split("/") if item]


def _generate_target_live_pool() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    source_paths = s182._configure_source_paths(SOURCE_PREFIX)
    daily = s182.build_product_daily()
    eval_date = s182._resolve_eval_date(daily, TARGET_EVAL_DATE.date().isoformat(), False)
    if eval_date != TARGET_EVAL_DATE:
        raise RuntimeError(f"resolved eval date {eval_date.date()} != target {TARGET_EVAL_DATE.date()}")
    label_cutoff = s182._training_label_cutoff(daily["date"], eval_date)
    featured = s182.add_rolling_features(daily)
    samples, feature_columns = s182.build_monthly_samples(featured)
    train_df = samples[pd.to_datetime(samples[s182.DATE_COLUMN]).dt.normalize().le(label_cutoff)].copy()
    if train_df.empty or train_df[s182.DATE_COLUMN].nunique() < 12:
        raise RuntimeError("insufficient Stage182 training rows for 2026-05-29")
    if train_df["target_future_top_half_60d"].nunique() < 2:
        raise RuntimeError("Stage182 training target has fewer than two classes")

    model = s182.train_model(train_df, feature_columns)
    live_rows = s182._build_live_feature_rows(featured, eval_date)
    live_rows[s182.PROBABILITY_COLUMN] = s182.score_model(model, live_rows, feature_columns)
    live_pool = live_rows.sort_values(
        [s182.PROBABILITY_COLUMN, s182.SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
        ascending=[False, False, True],
    ).copy()
    live_pool["ai_rank"] = range(1, len(live_pool) + 1)
    live_eligibility = s182._build_live_eligibility(live_pool, eval_date)
    info = {
        "source_prefix": SOURCE_PREFIX,
        "source_paths": source_paths,
        "eval_date": eval_date.date().isoformat(),
        "source_max_date": _date_text(pd.to_datetime(daily["date"]).max()),
        "training_label_cutoff": label_cutoff.date().isoformat(),
        "train_rows": int(len(train_df)),
        "train_months": int(train_df[s182.DATE_COLUMN].nunique()),
        "feature_count": int(len(feature_columns)),
        "live_rows": int(len(live_pool)),
    }
    return live_pool, live_eligibility, info


def build_frozen_ai_file() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    live_pool, live_eligibility, info = _generate_target_live_pool()
    base = pd.read_csv(CURRENT_COMBINED_AI_PATH)
    base["eval_date"] = pd.to_datetime(base["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    strategy = AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME
    drop_mask = base["strategy"].astype(str).eq(strategy) & base["eval_date"].isin(
        [TARGET_EVAL_DATE.date().isoformat(), "2026-06-30"]
    )
    combined = pd.concat([base.loc[~drop_mask].copy(), live_eligibility.copy()], ignore_index=True, sort=False)
    combined["eval_date"] = pd.to_datetime(combined["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined["score_rank"] = pd.to_numeric(combined["score_rank"], errors="coerce").fillna(9999).astype(int)
    combined.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    live_pool.to_csv(GENERATED_LIVE_POOL_PATH, index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(GENERATED_LIVE_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(FROZEN_AI_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")

    saved_products = _saved_products_for_eval(STAGE013_SAVED_AI_AUDIT_PATH, TARGET_EVAL_DATE)
    generated_products = _products_for_eval(live_eligibility, TARGET_EVAL_DATE)
    frozen_dates = sorted(pd.to_datetime(combined["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d").dropna().unique())
    audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_combined_ai_path": str(CURRENT_COMBINED_AI_PATH),
        "current_combined_sha256": _sha256(CURRENT_COMBINED_AI_PATH),
        "stage013_saved_ai_audit_path": str(STAGE013_SAVED_AI_AUDIT_PATH),
        "target_eval_date": TARGET_EVAL_DATE.date().isoformat(),
        "dropped_current_rows": int(drop_mask.sum()),
        "generated_live_eligibility_rows": int(len(live_eligibility)),
        "frozen_rows": int(len(combined)),
        "frozen_eval_date_count": int(len(frozen_dates)),
        "frozen_eval_dates_2026": [d for d in frozen_dates if d.startswith("2026-")],
        "generated_products": generated_products,
        "saved_stage013_products": saved_products,
        "matches_saved_stage013_products": generated_products == saved_products,
        "frozen_ai_path": str(FROZEN_AI_ELIGIBILITY_PATH),
        "frozen_ai_sha256": _sha256(FROZEN_AI_ELIGIBILITY_PATH),
        "generated_live_eligibility_path": str(GENERATED_LIVE_ELIGIBILITY_PATH),
        "generated_live_pool_path": str(GENERATED_LIVE_POOL_PATH),
        "stage182_info": info,
        "safety": {
            "overwrites_official_live_ai_file": False,
            "overwrites_official_stage78_eligibility": False,
            "real_order_enabled": False,
            "ctp_connected": False,
        },
    }
    AI_REPAIR_AUDIT_PATH.write_text(json.dumps(_json_safe(audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not audit["matches_saved_stage013_products"]:
        raise RuntimeError(
            "generated 2026-05-29 pool does not match saved Stage013 product audit; stop before promotion A/B"
        )
    return audit


@contextmanager
def _patched_live_ai_path(ai_path: Path):
    original_s901_builder = s901.build_official_live_strategy_overrides
    original_s013_builder = s013.build_official_live_strategy_overrides
    original_s167_path = s167.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    original_s901_path = s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    original_s013_path = s013.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH

    def build_overrides() -> dict[str, Any]:
        overrides = dict(original_s901_builder())
        overrides["ai_product_pool_eligibility_path"] = str(ai_path)
        return overrides

    try:
        s901.build_official_live_strategy_overrides = build_overrides
        s013.build_official_live_strategy_overrides = build_overrides
        s167.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = ai_path
        s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = ai_path
        s013.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = ai_path
        yield
    finally:
        s901.build_official_live_strategy_overrides = original_s901_builder
        s013.build_official_live_strategy_overrides = original_s013_builder
        s167.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = original_s167_path
        s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = original_s901_path
        s013.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = original_s013_path


def _prepare_curve(curve: pd.DataFrame, start: pd.Timestamp, version: str) -> pd.DataFrame:
    result = curve.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = version
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["nav"] = pd.to_numeric(result["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
    result["drawdown_pct"] = _drawdown_pct(pd.to_numeric(result["account_equity"], errors="coerce"))
    result["days_since_start"] = np.arange(len(result), dtype=int)
    return result


def _with_run_columns(frame: pd.DataFrame, start: pd.Timestamp, version: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = version
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    return result


def run_version(version: str, metadata: dict[str, Any], starts: list[pd.Timestamp]) -> dict[str, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for idx, start in enumerate(starts, start=1):
        print(f"[stage061] {version} {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        if version == "official_c9_15w_stage847":
            combined, frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)
        elif version == "stage013_account_state_pilot":
            combined, frames, _spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        else:
            raise ValueError(version)
        curve = _prepare_curve(combined, start, version)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start, version))
        candidates = _with_run_columns(frames.get("entry_candidates", pd.DataFrame()), start, version)
        if not candidates.empty:
            candidate_frames.append(candidates)
    return {
        "summary": pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
    }


def build_pair(official_curves: pd.DataFrame, stage013_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    official = official_curves[
        [
            "requested_start_month",
            "date",
            "account_equity",
            "nav",
            "drawdown_pct",
            "slippage",
            "trade_count",
        ]
    ].rename(
        columns={
            "account_equity": "official_equity",
            "nav": "official_nav",
            "drawdown_pct": "official_drawdown_pct",
            "slippage": "official_slippage",
            "trade_count": "official_trade_count",
        }
    )
    candidate = stage013_curves[
        [
            "requested_start_month",
            "date",
            "account_equity",
            "nav",
            "drawdown_pct",
            "slippage",
            "trade_count",
        ]
    ].rename(
        columns={
            "account_equity": "stage013_equity",
            "nav": "stage013_nav",
            "drawdown_pct": "stage013_drawdown_pct",
            "slippage": "stage013_slippage",
            "trade_count": "stage013_trade_count",
        }
    )
    pair = official.merge(candidate, on=["requested_start_month", "date"], how="inner")
    pair["stage013_vs_official_nav_gap_pct"] = (pair["stage013_nav"] / pair["official_nav"] - 1.0) * 100.0
    pair["stage013_lags_official"] = pair["stage013_vs_official_nav_gap_pct"].lt(0.0)
    rows: list[dict[str, Any]] = []
    for start, group in pair.groupby("requested_start_month", sort=True):
        group = group.sort_values("date")
        final = group.iloc[-1]
        worst_gap = group.loc[group["stage013_vs_official_nav_gap_pct"].idxmin()]
        official_return = (float(final["official_nav"]) - 1.0) * 100.0
        stage013_return = (float(final["stage013_nav"]) - 1.0) * 100.0
        official_dd = float(group["official_drawdown_pct"].min())
        stage013_dd = float(group["stage013_drawdown_pct"].min())
        rows.append(
            {
                "requested_start_month": start,
                "start_date": _date_text(group["date"].iloc[0]),
                "end_date": _date_text(group["date"].iloc[-1]),
                "trading_days": int(len(group)),
                "official_end_equity": float(final["official_equity"]),
                "stage013_end_equity": float(final["stage013_equity"]),
                "official_total_return_pct": official_return,
                "stage013_total_return_pct": stage013_return,
                "return_diff_pp": stage013_return - official_return,
                "official_max_drawdown_pct": official_dd,
                "stage013_max_drawdown_pct": stage013_dd,
                "drawdown_improvement_pp": stage013_dd - official_dd,
                "official_sharpe": _daily_sharpe(group["official_nav"]),
                "stage013_sharpe": _daily_sharpe(group["stage013_nav"]),
                "final_nav_ratio_vs_official": float(final["stage013_nav"] / final["official_nav"]),
                "worst_stage013_vs_official_gap_pct": float(worst_gap["stage013_vs_official_nav_gap_pct"]),
                "worst_gap_date": _date_text(worst_gap["date"]),
                "stage013_lag_day_ratio_pct": float(group["stage013_lags_official"].mean() * 100.0),
                "official_total_slippage": _safe_sum(group, "official_slippage"),
                "stage013_total_slippage": _safe_sum(group, "stage013_slippage"),
                "official_total_trade_count": _safe_sum(group, "official_trade_count"),
                "stage013_total_trade_count": _safe_sum(group, "stage013_trade_count"),
            }
        )
    summary = pd.DataFrame(rows)
    aggregate = pd.DataFrame(
        [
            {
                "start_count": int(len(summary)),
                "official_positive_count": int(summary["official_total_return_pct"].gt(0.0).sum()),
                "stage013_positive_count": int(summary["stage013_total_return_pct"].gt(0.0).sum()),
                "stage013_return_win_count": int(summary["return_diff_pp"].gt(0.0).sum()),
                "stage013_drawdown_improve_count": int(summary["drawdown_improvement_pp"].gt(0.0).sum()),
                "stage013_both_return_and_drawdown_win_count": int(
                    (summary["return_diff_pp"].gt(0.0) & summary["drawdown_improvement_pp"].gt(0.0)).sum()
                ),
                "official_min_return_pct": float(summary["official_total_return_pct"].min()),
                "stage013_min_return_pct": float(summary["stage013_total_return_pct"].min()),
                "official_median_return_pct": float(summary["official_total_return_pct"].median()),
                "stage013_median_return_pct": float(summary["stage013_total_return_pct"].median()),
                "official_worst_max_drawdown_pct": float(summary["official_max_drawdown_pct"].min()),
                "stage013_worst_max_drawdown_pct": float(summary["stage013_max_drawdown_pct"].min()),
                "min_final_nav_ratio_vs_official": float(summary["final_nav_ratio_vs_official"].min()),
                "median_final_nav_ratio_vs_official": float(summary["final_nav_ratio_vs_official"].median()),
                "worst_relative_gap_pct": float(summary["worst_stage013_vs_official_gap_pct"].min()),
            }
        ]
    )
    return pair, summary, aggregate


def _plot_pair(pair: pd.DataFrame, summary: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        ax.plot(group["date"], group["official_equity"], color="#111827", linewidth=1.0, label="Official")
        ax.plot(group["date"], group["stage013_equity"], color="#2563eb", linewidth=1.0, label="Stage013")
        ax.set_title(start, fontsize=9)
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        if start == starts[0]:
            ax.legend(fontsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Stage061 Official vs Stage013: Absolute Equity, Frozen 2026-05-29 AI", fontsize=15)
    fig.savefig(ABSOLUTE_EQUITY_GRID_PATH, dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), sharey=True, constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        row = summary[summary["requested_start_month"].eq(start)].iloc[0]
        y = group["stage013_vs_official_nav_gap_pct"]
        ax.plot(group["date"], y, color="#2563eb", linewidth=1.0)
        ax.fill_between(group["date"], y, 0, where=y.ge(0), color="#16a34a", alpha=0.18, interpolate=True)
        ax.fill_between(group["date"], y, 0, where=y.lt(0), color="#dc2626", alpha=0.22, interpolate=True)
        ax.axhline(0, color="#111827", linewidth=0.8)
        ax.set_title(
            f"{start} final {row['final_nav_ratio_vs_official'] - 1:+.1%} worst {row['worst_stage013_vs_official_gap_pct']:+.1f}%",
            fontsize=9,
        )
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Stage013 Relative NAV Gap vs Official, Frozen 2026-05-29 AI", fontsize=15)
    fig.savefig(RELATIVE_GAP_GRID_PATH, dpi=170)
    plt.close(fig)

    frame = summary.sort_values("requested_start_month")
    x = np.arange(len(frame))
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    axes[0].bar(x, frame["return_diff_pp"], color=np.where(frame["return_diff_pp"].ge(0), "#2563eb", "#dc2626"))
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage013 final return minus Official")
    axes[0].set_ylabel("percentage points")
    axes[0].grid(True, axis="y", alpha=0.22)
    axes[1].bar(x, frame["drawdown_improvement_pp"], color=np.where(frame["drawdown_improvement_pp"].ge(0), "#16a34a", "#dc2626"))
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Stage013 max drawdown improvement")
    axes[1].set_ylabel("percentage points")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(frame["requested_start_month"], rotation=35, ha="right")
    axes[1].grid(True, axis="y", alpha=0.22)
    fig.savefig(SUMMARY_BAR_PATH, dpi=170)
    plt.close(fig)


def _ai_month_audit(candidates: pd.DataFrame, summary: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    return s167._ai_month_audit(candidates, summary, pool)


def run_ab(ai_audit: dict[str, Any]) -> dict[str, Any]:
    starts = s167._build_start_dates()
    metadata = s901.s513._metadata()
    with _patched_live_ai_path(FROZEN_AI_ELIGIBILITY_PATH):
        official = run_version("official_c9_15w_stage847", metadata, starts)
        stage013 = run_version("stage013_account_state_pilot", metadata, starts)

    pool = pd.read_csv(FROZEN_AI_ELIGIBILITY_PATH)
    pool["eval_date"] = pd.to_datetime(pool["eval_date"], errors="coerce").dt.normalize()
    pool_audit = s167._pool_audit_frame(pool)
    official_ai_month = _ai_month_audit(official["entry_candidates"], official["summary"], pool)
    stage013_ai_month = _ai_month_audit(stage013["entry_candidates"], stage013["summary"], pool)

    pair, pair_summary, aggregate = build_pair(official["curves"], stage013["curves"])
    _plot_pair(pair, pair_summary)

    official["summary"].to_csv(OFFICIAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stage013["summary"].to_csv(STAGE013_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pair_summary.to_csv(PAIR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    official["curves"].to_csv(OFFICIAL_CURVES_PATH, index=False, encoding="utf-8-sig")
    stage013["curves"].to_csv(STAGE013_CURVES_PATH, index=False, encoding="utf-8-sig")
    pair.to_csv(PAIR_CURVES_PATH, index=False, encoding="utf-8-sig")
    official["entry_candidates"].to_csv(OFFICIAL_ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    stage013["entry_candidates"].to_csv(STAGE013_ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    pool_audit.to_csv(POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    official_ai_month.to_csv(OFFICIAL_AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    stage013_ai_month.to_csv(STAGE013_AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")

    agg = aggregate.iloc[0].to_dict()
    official_ai_status = official_ai_month.groupby("status").size().to_dict() if not official_ai_month.empty else {}
    stage013_ai_status = stage013_ai_month.groupby("status").size().to_dict() if not stage013_ai_month.empty else {}
    promotion_gate = {
        "candidate": "stage013_account_state_pilot",
        "direct_promotion_recommended": False,
        "next_validation_recommended": True,
        "reason": (
            "Stage013 improves most return/drawdown paths under a frozen PIT AI file, but it still has "
            "known underperforming starts and must pass live-shadow/account reconciliation before formal promotion."
        ),
    }
    if (
        int(agg["stage013_return_win_count"]) >= 14
        and int(agg["stage013_drawdown_improve_count"]) >= 14
        and float(agg["stage013_min_return_pct"]) > 0
        and float(agg["stage013_worst_max_drawdown_pct"]) > float(agg["official_worst_max_drawdown_pct"])
    ):
        promotion_gate["next_validation_recommended"] = True
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "arms": {
            "A": "official_c9_15w_stage847",
            "C": "stage013_account_state_pilot",
            "B": "not_applicable_account_state_layer",
        },
        "ai_repair_audit": ai_audit,
        "aggregate": agg,
        "official_ai_month_status": {str(k): int(v) for k, v in official_ai_status.items()},
        "stage013_ai_month_status": {str(k): int(v) for k, v in stage013_ai_status.items()},
        "promotion_gate": promotion_gate,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "有选择偏差风险，因为研究线已经看过多条候选；本阶段只锁定一个结构候选 Stage013，并先冻结 AI 输入。"
        ),
        "overfit_reflection_after": (
            "未新增调参。若失败后继续按输的起点改日期、品种、阈值，就是过拟合；当前只允许进入下一层执行验证。"
        ),
        "continue_value_before": "有。Stage013 是账户状态层，不是新增预测因子，具备穿越周期的结构理由。",
        "continue_value_after": (
            "有，但价值在于进入更严格 shadow/执行验证，不是今天直接替换正式版。"
        ),
        "outputs": {
            "frozen_ai_eligibility": str(FROZEN_AI_ELIGIBILITY_PATH),
            "ai_repair_audit": str(AI_REPAIR_AUDIT_PATH),
            "official_summary": str(OFFICIAL_SUMMARY_PATH),
            "stage013_summary": str(STAGE013_SUMMARY_PATH),
            "pair_summary": str(PAIR_SUMMARY_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "official_curves": str(OFFICIAL_CURVES_PATH),
            "stage013_curves": str(STAGE013_CURVES_PATH),
            "pair_curves": str(PAIR_CURVES_PATH),
            "official_ai_month_audit": str(OFFICIAL_AI_MONTH_AUDIT_PATH),
            "stage013_ai_month_audit": str(STAGE013_AI_MONTH_AUDIT_PATH),
            "pool_audit": str(POOL_AUDIT_PATH),
            "absolute_equity_grid": str(ABSOLUTE_EQUITY_GRID_PATH),
            "relative_gap_grid": str(RELATIVE_GAP_GRID_PATH),
            "summary_bar": str(SUMMARY_BAR_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def write_report_and_records(decision: dict[str, Any]) -> Path:
    agg = decision["aggregate"]
    pair_summary = pd.read_csv(PAIR_SUMMARY_PATH)
    underperform = pair_summary[pair_summary["return_diff_pp"].lt(0)].sort_values("return_diff_pp")
    dd_worse = pair_summary[pair_summary["drawdown_improvement_pp"].lt(0)].sort_values("drawdown_improvement_pp")
    now = datetime.now()
    lines = [
        "# Stage061 Stage013 frozen-AI promotion A/C",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- A: `{decision['arms']['A']}`",
        f"- C: `{decision['arms']['C']}`",
        f"- frozen AI: `{decision['ai_repair_audit']['frozen_ai_path']}`",
        f"- frozen AI sha256: `{decision['ai_repair_audit']['frozen_ai_sha256']}`",
        f"- 2026 eval_dates: `{', '.join(decision['ai_repair_audit']['frozen_eval_dates_2026'])}`",
        f"- 2026-05-29 products: `{', '.join(decision['ai_repair_audit']['generated_products'])}`",
        "",
        "## Result",
        "",
        f"- starts: `{int(agg['start_count'])}`",
        f"- Stage013 positive: `{int(agg['stage013_positive_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 return wins: `{int(agg['stage013_return_win_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 drawdown improves: `{int(agg['stage013_drawdown_improve_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 both return and drawdown wins: `{int(agg['stage013_both_return_and_drawdown_win_count'])}/{int(agg['start_count'])}`",
        f"- official min/median return: `{agg['official_min_return_pct']:.4f}% / {agg['official_median_return_pct']:.4f}%`",
        f"- Stage013 min/median return: `{agg['stage013_min_return_pct']:.4f}% / {agg['stage013_median_return_pct']:.4f}%`",
        f"- official worst max DD: `{agg['official_worst_max_drawdown_pct']:.4f}%`",
        f"- Stage013 worst max DD: `{agg['stage013_worst_max_drawdown_pct']:.4f}%`",
        f"- Stage013 min/median NAV ratio vs official: `{agg['min_final_nav_ratio_vs_official']:.4f} / {agg['median_final_nav_ratio_vs_official']:.4f}`",
        "",
        "## Underperforming Starts",
        "",
        _md_table(
            underperform[
                [
                    "requested_start_month",
                    "official_total_return_pct",
                    "stage013_total_return_pct",
                    "return_diff_pp",
                    "official_max_drawdown_pct",
                    "stage013_max_drawdown_pct",
                    "drawdown_improvement_pp",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## DD Worse Starts",
        "",
        _md_table(
            dd_worse[
                [
                    "requested_start_month",
                    "official_max_drawdown_pct",
                    "stage013_max_drawdown_pct",
                    "drawdown_improvement_pp",
                    "return_diff_pp",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Decision",
        "",
        f"- direct promotion recommended: `{decision['promotion_gate']['direct_promotion_recommended']}`",
        f"- next validation recommended: `{decision['promotion_gate']['next_validation_recommended']}`",
        f"- reason: {decision['promotion_gate']['reason']}",
        "- overfitting: run did not add parameters; picking Stage013 still carries candidate-selection risk, so next step is shadow/execution validation.",
        "- continued value: yes, but only as a staged formal candidate, not as an immediate live replacement.",
        "",
        "## Outputs",
        "",
    ]
    for key, value in decision["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage061_stage013_frozen_ai_promotion_ab.md"
    stage_lines = [
        "# Stage061 Stage013 frozen-AI promotion A/C",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否；Stage013 进入下一层验证，但不直接晋升正式版",
        "- 是否触发A/B：是；A=Official C9/15w Stage847，C=Stage013 account-state pilot",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：Bailey/PBO、pysystemtrade 和 walk-forward validation。结论是不能从多候选里挑最优曲线直接上线，必须先锁候选、锁输入、再做 A/C。",
        "- 我的判断：Stage013 是账户状态风控层，结构上比 Stage010/014 proxy 更适合作为 formal candidate；但当前还只能进入 shadow/执行验证。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：无交易参数；新增研究进程内 frozen AI path override",
        "- 修改参数：无正式参数修改",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- A：Official C9/15w Stage847",
        "- C：Stage013 account-state pilot",
        "- 起点：`2018-01` 到 `2026-01` 逐半年",
        "- 终点：`2026-06-30`",
        "- 资金：`150,000`",
        f"- AI 池：`{decision['ai_repair_audit']['frozen_ai_path']}`",
        f"- AI hash：`{decision['ai_repair_audit']['frozen_ai_sha256']}`",
        "",
        "## 结果",
        "",
        f"- 期末权益/总收益：详见 `{PAIR_SUMMARY_PATH}`",
        f"- Stage013 正收益：`{int(agg['stage013_positive_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 收益胜正式：`{int(agg['stage013_return_win_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 回撤改善：`{int(agg['stage013_drawdown_improve_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 最小/中位收益：`{agg['stage013_min_return_pct']:.4f}% / {agg['stage013_median_return_pct']:.4f}%`",
        f"- Stage013 最差最大回撤：`{agg['stage013_worst_max_drawdown_pct']:.4f}%`",
        f"- 总滑点/总交易次数：详见 A/C summary 文件；本阶段未重新逐笔计算胜率",
        f"- AI 审计：official `{decision['official_ai_month_status']}`；Stage013 `{decision['stage013_ai_month_status']}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：Stage013 可以作为唯一 formal candidate 继续验证；不建议今天直接替换正式版。",
        "- 下一步：用同一 frozen AI 跑 latest shadow / 当前持仓对账 / 执行链路 dry-run，再由用户显式确认是否 staged promotion。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")

    back_log_entry = "\n".join(
        [
            "",
            f"{now.strftime('%Y-%m-%d %H:%M')} CST：`{LINE_ID}` Stage061 完成 Stage013 frozen-AI promotion A/C，决策 `stage013_next_validation_not_direct_promotion`。A=`official_c9_15w_stage847`，C=`stage013_account_state_pilot`；本阶段先生成线内 frozen AI 文件，删除当前错误用于本回测的 `2026-06-30` 池并重建 `2026-05-29` 池，AI hash `{decision['ai_repair_audit']['frozen_ai_sha256']}`，不覆盖正式 live AI 文件、不连接 CTP、不调用订单 API。结果：Stage013 正收益 `{int(agg['stage013_positive_count'])}/{int(agg['start_count'])}`，收益胜正式 `{int(agg['stage013_return_win_count'])}/{int(agg['start_count'])}`，回撤改善 `{int(agg['stage013_drawdown_improve_count'])}/{int(agg['start_count'])}`，最小/中位收益 `{agg['stage013_min_return_pct']:.4f}%/{agg['stage013_median_return_pct']:.4f}%`，最差最大回撤 `{agg['stage013_worst_max_drawdown_pct']:.4f}%`，正式版最差最大回撤 `{agg['official_worst_max_drawdown_pct']:.4f}%`；总滑点和交易次数见 `{PAIR_SUMMARY_PATH}`。运行前过拟合反思：{decision['overfit_reflection_before']} 运行后过拟合反思：{decision['overfit_reflection_after']} 运行前继续价值反思：{decision['continue_value_before']} 运行后继续价值反思：{decision['continue_value_after']} 后续：只进入 shadow/执行验证和用户显式晋升确认，不直接改正式版。",
        ]
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(back_log_entry + "\n")
    return stage_path


def main() -> None:
    print("[stage061] build frozen AI file", flush=True)
    ai_audit = build_frozen_ai_file()
    print(json.dumps(_json_safe(ai_audit), ensure_ascii=False, indent=2), flush=True)
    print("[stage061] run A/C backtest", flush=True)
    decision = run_ab(ai_audit)
    stage_path = write_report_and_records(decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
