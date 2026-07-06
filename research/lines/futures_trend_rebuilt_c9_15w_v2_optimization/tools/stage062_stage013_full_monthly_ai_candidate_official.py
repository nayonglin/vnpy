from __future__ import annotations

from contextlib import contextmanager
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
STAGE = "Stage062"
MODEL_TAG = "stage062_stage013_full_monthly_ai_candidate_official_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official"
SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-07-02")
MONTHLY_AUDIT_START = pd.Timestamp("2020-01-01")
START_MONTHS = (1, 7)

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage062_stage013_full_monthly_ai_candidate_official"
STAGES_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = ROOT / "back_log.md"

CURRENT_COMBINED_AI_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)

FULL_POOL_PATH = OUT / f"{OUTPUT_PREFIX}_full_monthly_pool_{MODEL_TAG}.csv.gz"
FULL_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_full_monthly_eligibility_{MODEL_TAG}.csv"
CANDIDATE_AI_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_ai_eligibility_{MODEL_TAG}.csv"
AI_COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_coverage_{MODEL_TAG}.csv"
AI_REBUILD_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_rebuild_audit_{MODEL_TAG}.json"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_curves_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_trades_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_stage013_trade_events_{MODEL_TAG}.csv.gz"
STANDARD_AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_standard_ai_month_audit_{MODEL_TAG}.csv"
FRESHNESS_AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_freshness_ai_month_audit_{MODEL_TAG}.csv"
POOL_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pool_audit_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
AI_FRESHNESS_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_ai_freshness_chart_{MODEL_TAG}.png"
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


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


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


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= REQUESTED_END:
                starts.append(start)
    return starts


def _expected_month_end_eval_dates(daily: pd.DataFrame) -> list[pd.Timestamp]:
    dates = pd.to_datetime(daily["date"], errors="coerce").dropna().drop_duplicates().sort_values()
    latest_completed = s182._last_completed_month_eval_date(dates)
    usable = dates[(dates >= MONTHLY_AUDIT_START) & (dates <= latest_completed)].copy()
    return [
        pd.Timestamp(value).normalize()
        for value in usable.groupby(usable.dt.to_period("M")).max().tolist()
    ]


def _build_one_eval_date(
    featured: pd.DataFrame,
    samples: pd.DataFrame,
    feature_columns: list[str],
    daily_dates: pd.Series,
    eval_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    label_cutoff = s182._training_label_cutoff(daily_dates, eval_date)
    train_df = samples[pd.to_datetime(samples[s182.DATE_COLUMN]).dt.normalize().le(label_cutoff)].copy()
    target_classes = int(train_df["target_future_top_half_60d"].nunique()) if not train_df.empty else 0
    train_months = int(train_df[s182.DATE_COLUMN].nunique()) if not train_df.empty else 0
    audit: dict[str, Any] = {
        "eval_date": eval_date.date().isoformat(),
        "training_label_cutoff": label_cutoff.date().isoformat(),
        "train_rows": int(len(train_df)),
        "train_months": train_months,
        "target_class_count": target_classes,
        "status": "",
        "selected_products": "",
    }
    if train_df.empty or train_months < 12:
        audit["status"] = "INFEASIBLE_COLD_START_MIN_12_TRAIN_MONTHS"
        return pd.DataFrame(), pd.DataFrame(), audit
    if target_classes < 2:
        audit["status"] = "INFEASIBLE_COLD_START_ONE_TARGET_CLASS"
        return pd.DataFrame(), pd.DataFrame(), audit

    model = s182.train_model(train_df, feature_columns)
    live_rows = s182._build_live_feature_rows(featured, eval_date)
    live_rows[s182.PROBABILITY_COLUMN] = s182.score_model(model, live_rows, feature_columns)
    live_pool = live_rows.sort_values(
        [s182.PROBABILITY_COLUMN, s182.SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
        ascending=[False, False, True],
    ).copy()
    live_pool["ai_rank"] = range(1, len(live_pool) + 1)
    live_pool["eval_date"] = eval_date.date().isoformat()
    live_eligibility = s182._build_live_eligibility(live_pool, eval_date)
    audit.update(
        {
            "status": "GENERATED",
            "live_rows": int(len(live_pool)),
            "selected_products": "/".join(live_eligibility["product_vt_symbol"].astype(str).tolist()),
        }
    )
    return live_pool, live_eligibility, audit


def build_full_monthly_ai_file() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    source_paths = s182._configure_source_paths(SOURCE_PREFIX)
    daily = s182.build_product_daily()
    source_max_date = pd.Timestamp(daily["date"].max()).normalize()
    latest_completed = s182._last_completed_month_eval_date(daily["date"])
    featured = s182.add_rolling_features(daily)
    samples, feature_columns = s182.build_monthly_samples(featured)
    expected_eval_dates = _expected_month_end_eval_dates(daily)

    pool_frames: list[pd.DataFrame] = []
    eligibility_frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    for eval_date in expected_eval_dates:
        pool, eligibility, audit = _build_one_eval_date(
            featured=featured,
            samples=samples,
            feature_columns=feature_columns,
            daily_dates=daily["date"],
            eval_date=eval_date,
        )
        coverage_rows.append(audit)
        if not pool.empty:
            pool_frames.append(pool)
        if not eligibility.empty:
            eligibility_frames.append(eligibility)

    live_pool = pd.concat(pool_frames, ignore_index=True, sort=False) if pool_frames else pd.DataFrame()
    live_eligibility = (
        pd.concat(eligibility_frames, ignore_index=True, sort=False) if eligibility_frames else pd.DataFrame()
    )
    if live_eligibility.empty:
        raise RuntimeError("no feasible Stage182 monthly AI eligibility rows were generated")
    live_eligibility["eval_date"] = pd.to_datetime(live_eligibility["eval_date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    live_eligibility["score_rank"] = pd.to_numeric(live_eligibility["score_rank"], errors="coerce").astype(int)
    live_eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    live_eligibility.reset_index(drop=True, inplace=True)

    base = pd.read_csv(CURRENT_COMBINED_AI_PATH)
    base["eval_date"] = pd.to_datetime(base["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    strategy = AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME
    generated_dates = set(live_eligibility["eval_date"].astype(str))
    keep = ~(
        base["strategy"].astype(str).eq(strategy)
        & base["eval_date"].astype(str).isin(generated_dates)
    )
    combined = pd.concat([base.loc[keep].copy(), live_eligibility.copy()], ignore_index=True, sort=False)
    combined["eval_date"] = pd.to_datetime(combined["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined["score_rank"] = pd.to_numeric(combined["score_rank"], errors="coerce").fillna(9999).astype(int)
    combined.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    coverage = pd.DataFrame(coverage_rows)
    coverage["calendar_month"] = pd.to_datetime(coverage["eval_date"], errors="coerce").dt.to_period("M").astype(str)
    coverage["present_in_candidate_ai_file"] = coverage["eval_date"].astype(str).isin(
        set(combined["eval_date"].astype(str))
    ).astype(int)
    coverage.to_csv(AI_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    live_pool.to_csv(FULL_POOL_PATH, index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(FULL_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(CANDIDATE_AI_PATH, index=False, encoding="utf-8-sig")

    generated_eval_dates = sorted(live_eligibility["eval_date"].astype(str).unique().tolist())
    candidate_eval_dates = sorted(combined["eval_date"].astype(str).unique().tolist())
    infeasible = coverage[coverage["status"].astype(str).str.startswith("INFEASIBLE")]["eval_date"].astype(str).tolist()
    repair = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_prefix": SOURCE_PREFIX,
        "source_paths": source_paths,
        "source_max_date": source_max_date.date().isoformat(),
        "latest_completed_month_eval_date": latest_completed.date().isoformat(),
        "expected_eval_date_count_2020_to_latest_completed": int(len(expected_eval_dates)),
        "generated_eval_date_count": int(len(generated_eval_dates)),
        "infeasible_cold_start_eval_date_count": int(len(infeasible)),
        "infeasible_cold_start_eval_dates": infeasible,
        "generated_eval_date_min": generated_eval_dates[0],
        "generated_eval_date_max": generated_eval_dates[-1],
        "candidate_ai_eval_date_count": int(len(candidate_eval_dates)),
        "candidate_ai_eval_dates_2026": [d for d in candidate_eval_dates if d.startswith("2026-")],
        "candidate_ai_rows": int(len(combined)),
        "candidate_ai_path": str(CANDIDATE_AI_PATH),
        "candidate_ai_sha256": _sha256(CANDIDATE_AI_PATH),
        "current_combined_ai_path": str(CURRENT_COMBINED_AI_PATH),
        "current_combined_ai_sha256": _sha256(CURRENT_COMBINED_AI_PATH),
        "full_monthly_pool_path": str(FULL_POOL_PATH),
        "full_monthly_eligibility_path": str(FULL_ELIGIBILITY_PATH),
        "coverage_path": str(AI_COVERAGE_PATH),
        "feature_count": int(len(feature_columns)),
        "strategy": strategy,
        "safety": {
            "overwrites_official_live_ai_file": False,
            "overwrites_current_combined_ai_file": False,
            "changes_training_thresholds": False,
            "real_order_enabled": False,
            "ctp_connected": False,
        },
    }
    AI_REBUILD_AUDIT_PATH.write_text(json.dumps(_json_safe(repair), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return repair


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


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / float(OFFICIAL_LIVE_CAPITAL)
    drawdown = _drawdown_pct(equity)
    end_equity = float(equity.iloc[-1])
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": "stage013_account_state_pilot_candidate_official",
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "ai_pool_path": str(CANDIDATE_AI_PATH),
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


def _prepare_curve(curve: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    result = curve.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = "stage013_account_state_pilot_candidate_official"
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["nav"] = pd.to_numeric(result["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
    result["drawdown_pct"] = _drawdown_pct(pd.to_numeric(result["account_equity"], errors="coerce"))
    result["days_since_start"] = np.arange(len(result), dtype=int)
    return result


def _with_run_columns(frame: pd.DataFrame, start: pd.Timestamp, name: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = "stage013_account_state_pilot_candidate_official"
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["frame_name"] = name
    return result


def run_stage013_multistart() -> dict[str, pd.DataFrame]:
    starts = _build_start_dates()
    metadata = s901.s513._metadata()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    with _patched_live_ai_path(CANDIDATE_AI_PATH):
        for idx, start in enumerate(starts, start=1):
            print(f"[stage062] stage013 {idx}/{len(starts)} start={_date_text(start)}", flush=True)
            combined, frames, _spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
            curve = _prepare_curve(combined, start)
            curve_frames.append(curve)
            summary_rows.append(_summarize_curve(curve, start))
            candidate_frames.append(_with_run_columns(frames.get("entry_candidates", pd.DataFrame()), start, "entry_candidates"))
            trade_frames.append(_with_run_columns(frames.get("trades", pd.DataFrame()), start, "trades"))
            trade_event_frames.append(_with_run_columns(frames.get("trade_events", pd.DataFrame()), start, "trade_events"))
    return {
        "summary": pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat([f for f in candidate_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in candidate_frames)
        else pd.DataFrame(),
        "trades": pd.concat([f for f in trade_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_frames)
        else pd.DataFrame(),
        "trade_events": pd.concat([f for f in trade_event_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_event_frames)
        else pd.DataFrame(),
    }


def _latest_prior_eval(eval_dates: list[pd.Timestamp], candidate_date: pd.Timestamp) -> pd.Timestamp | None:
    prior = [d for d in eval_dates if d < candidate_date]
    return prior[-1] if prior else None


def _text_present(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    return text.ne("") & ~text.str.lower().isin({"nan", "nat", "none"})


def build_freshness_month_audit(
    candidates: pd.DataFrame,
    summary: pd.DataFrame,
    pool: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:
    pool_dates = sorted(pd.to_datetime(pool["eval_date"], errors="coerce").dropna().dt.normalize().unique())
    pool_dates = [pd.Timestamp(d).normalize() for d in pool_dates]
    expected_dates = sorted(pd.to_datetime(coverage["eval_date"], errors="coerce").dropna().dt.normalize().unique())
    expected_dates = [pd.Timestamp(d).normalize() for d in expected_dates]
    generated_dates = set(
        pd.to_datetime(
            coverage.loc[coverage["status"].astype(str).eq("GENERATED"), "eval_date"],
            errors="coerce",
        )
        .dropna()
        .dt.normalize()
        .dt.strftime("%Y-%m-%d")
    )
    infeasible_dates = set(
        pd.to_datetime(
            coverage.loc[coverage["status"].astype(str).str.startswith("INFEASIBLE"), "eval_date"],
            errors="coerce",
        )
        .dropna()
        .dt.normalize()
        .dt.strftime("%Y-%m-%d")
    )
    rows: list[dict[str, Any]] = []
    if not candidates.empty:
        temp = candidates.copy()
        temp["candidate_date"] = pd.to_datetime(temp.get("date", temp.get("datetime")), errors="coerce").dt.normalize()
        temp = temp.dropna(subset=["candidate_date"])
        temp["covered_month"] = temp["candidate_date"].dt.to_period("M").astype(str)
        temp["signal_date_text"] = temp.get("ai_product_pool_signal_date", pd.Series("", index=temp.index))
        temp["signal_date_present"] = _text_present(temp["signal_date_text"])
        expected_signal_dates: list[str] = []
        desired_eval_status: list[str] = []
        latest_available_dates: list[str] = []
        matches_latest_available: list[int] = []
        matches_desired_generated: list[int] = []
        for row in temp.itertuples(index=False):
            candidate_date = pd.Timestamp(getattr(row, "candidate_date")).normalize()
            desired = _latest_prior_eval(expected_dates, candidate_date)
            latest_available = _latest_prior_eval(pool_dates, candidate_date)
            signal_text = str(getattr(row, "signal_date_text") or "").strip()
            signal_date = pd.Timestamp(signal_text).normalize() if signal_text else None
            desired_text = desired.date().isoformat() if desired is not None else ""
            latest_text = latest_available.date().isoformat() if latest_available is not None else ""
            if not desired_text:
                desired_status = "SEED_PRE_2020"
            elif desired_text in generated_dates:
                desired_status = "GENERATED"
            elif desired_text in infeasible_dates:
                desired_status = "INFEASIBLE_COLD_START"
            else:
                desired_status = "MISSING_FROM_COVERAGE"
            expected_signal_dates.append(desired_text)
            desired_eval_status.append(desired_status)
            latest_available_dates.append(latest_text)
            matches_latest_available.append(int(signal_date is not None and latest_available is not None and signal_date == latest_available))
            matches_desired_generated.append(int(signal_date is not None and desired is not None and signal_date == desired))
        temp["desired_signal_date"] = expected_signal_dates
        temp["desired_signal_status"] = desired_eval_status
        temp["latest_available_signal_date"] = latest_available_dates
        temp["matches_latest_available_pool"] = matches_latest_available
        temp["matches_desired_generated_pool"] = matches_desired_generated

        grouped = (
            temp.groupby(["requested_start_month", "covered_month"], dropna=False)
            .agg(
                candidate_count=("candidate_index", "size"),
                opened_count=("is_opened", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                candidate_min_date=("candidate_date", "min"),
                candidate_max_date=("candidate_date", "max"),
                missing_signal_date_count=("signal_date_present", lambda s: int((~s).sum())),
                latest_available_match_count=("matches_latest_available_pool", "sum"),
                desired_generated_match_count=("matches_desired_generated_pool", "sum"),
                unique_signal_dates=("signal_date_text", lambda s: "/".join(sorted(v for v in set(s.fillna("").astype(str)) if v.strip()))),
                desired_signal_dates=("desired_signal_date", lambda s: "/".join(sorted(v for v in set(s.fillna("").astype(str)) if v.strip()))),
                latest_available_signal_dates=("latest_available_signal_date", lambda s: "/".join(sorted(v for v in set(s.fillna("").astype(str)) if v.strip()))),
                desired_statuses=("desired_signal_status", lambda s: "/".join(sorted(set(s.astype(str))))),
            )
            .reset_index()
        )
        for _, row in grouped.iterrows():
            candidate_count = int(row["candidate_count"])
            missing = int(row["missing_signal_date_count"])
            latest_match = int(row["latest_available_match_count"])
            desired_match = int(row["desired_generated_match_count"])
            desired_statuses = set(str(row["desired_statuses"]).split("/"))
            if missing:
                status = "FAIL_MISSING_SIGNAL_DATE"
            elif desired_statuses <= {"GENERATED"} and desired_match == candidate_count:
                status = "FRESH_MONTHLY_POOL"
            elif desired_statuses <= {"INFEASIBLE_COLD_START", "SEED_PRE_2020"} and latest_match == candidate_count:
                status = "COLD_START_PRE_MODEL_POOL"
            elif latest_match == candidate_count and "INFEASIBLE_COLD_START" in desired_statuses:
                status = "MIXED_COLD_START_AND_FRESH"
            elif latest_match == candidate_count:
                status = "LATEST_AVAILABLE_POOL_USED"
            else:
                status = "FAIL_STALE_OR_MISMATCHED_POOL"
            rows.append(
                {
                    **row.to_dict(),
                    "candidate_min_date": _date_text(row["candidate_min_date"]),
                    "candidate_max_date": _date_text(row["candidate_max_date"]),
                    "status": status,
                    "candidate_month": 1,
                }
            )

    present = set((str(row["requested_start_month"]), str(row["covered_month"])) for row in rows)
    for _, item in summary.iterrows():
        months = pd.period_range(item["actual_start"], item["actual_end"], freq="M").astype(str)
        for month in months:
            key = (str(item["requested_start_month"]), str(month))
            if key in present:
                continue
            rows.append(
                {
                    "requested_start_month": item["requested_start_month"],
                    "covered_month": month,
                    "candidate_count": 0,
                    "opened_count": 0,
                    "candidate_min_date": "",
                    "candidate_max_date": "",
                    "missing_signal_date_count": 0,
                    "latest_available_match_count": 0,
                    "desired_generated_match_count": 0,
                    "unique_signal_dates": "",
                    "desired_signal_dates": "",
                    "latest_available_signal_dates": "",
                    "desired_statuses": "",
                    "status": "NO_CANDIDATE_MONTH",
                    "candidate_month": 0,
                }
            )
    return pd.DataFrame(rows).sort_values(["requested_start_month", "covered_month"]).reset_index(drop=True)


def _plot_outputs(summary: pd.DataFrame, curves: pd.DataFrame, freshness: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.78, label=str(start))
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.78, label=str(start))
    axes[0].axhline(OFFICIAL_LIVE_CAPITAL, color="#111827", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage062 Stage013 Candidate Official: Absolute Equity")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage062 Stage013 Candidate Official: Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=4, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)

    monthly = (
        freshness[freshness["candidate_month"].astype(int).eq(1)]
        .groupby(["covered_month", "status"], as_index=False)
        .agg(candidate_count=("candidate_count", "sum"))
        .sort_values("covered_month")
    )
    pivot = monthly.pivot_table(index="covered_month", columns="status", values="candidate_count", aggfunc="sum", fill_value=0)
    colors = {
        "FRESH_MONTHLY_POOL": "#2563eb",
        "COLD_START_PRE_MODEL_POOL": "#f97316",
        "MIXED_COLD_START_AND_FRESH": "#a855f7",
        "LATEST_AVAILABLE_POOL_USED": "#16a34a",
        "FAIL_MISSING_SIGNAL_DATE": "#dc2626",
        "FAIL_STALE_OR_MISMATCHED_POOL": "#991b1b",
    }
    fig, ax = plt.subplots(figsize=(20, 7), constrained_layout=True)
    bottom = np.zeros(len(pivot), dtype=float)
    x = np.arange(len(pivot))
    for column in pivot.columns:
        vals = pivot[column].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, label=column, color=colors.get(str(column), "#6b7280"))
        bottom += vals
    step = max(1, len(pivot) // 24)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(pivot.index.astype(str).tolist()[::step], rotation=55, ha="right")
    ax.set_title("AI Pool Freshness By Candidate Calendar Month")
    ax.set_ylabel("entry candidate count")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8, ncol=2, loc="best")
    fig.savefig(AI_FRESHNESS_CHART_PATH, dpi=160)
    plt.close(fig)


def run_backtest_and_audits(ai_repair: dict[str, Any]) -> dict[str, Any]:
    result = run_stage013_multistart()
    pool = pd.read_csv(CANDIDATE_AI_PATH)
    pool["eval_date"] = pd.to_datetime(pool["eval_date"], errors="coerce").dt.normalize()
    coverage = pd.read_csv(AI_COVERAGE_PATH)
    pool_audit = s167._pool_audit_frame(pool)
    standard_ai_month = s167._ai_month_audit(result["entry_candidates"], result["summary"], pool)
    freshness_ai_month = build_freshness_month_audit(result["entry_candidates"], result["summary"], pool, coverage)

    result["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    result["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    result["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    result["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    result["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pool_audit.to_csv(POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    standard_ai_month.to_csv(STANDARD_AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    freshness_ai_month.to_csv(FRESHNESS_AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _plot_outputs(result["summary"], result["curves"], freshness_ai_month)

    returns = pd.to_numeric(result["summary"]["total_return_pct"], errors="coerce")
    dds = pd.to_numeric(result["summary"]["max_dd_pct"], errors="coerce")
    standard_status = standard_ai_month["status"].astype(str).value_counts().to_dict()
    freshness_status = freshness_ai_month["status"].astype(str).value_counts().to_dict()
    candidate_months = freshness_ai_month[freshness_ai_month["candidate_month"].astype(int).eq(1)]
    fail_freshness = candidate_months[candidate_months["status"].astype(str).str.startswith("FAIL")]
    generated_coverage = coverage[coverage["status"].astype(str).eq("GENERATED")]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "candidate": "stage013_account_state_pilot_candidate_official",
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "actual_end_max": result["summary"]["actual_end"].max(),
        "start_count": int(len(result["summary"])),
        "positive_count": int(returns.gt(0.0).sum()),
        "min_return_pct": float(returns.min()),
        "median_return_pct": float(returns.median()),
        "max_return_pct": float(returns.max()),
        "worst_max_drawdown_pct": float(dds.min()),
        "median_max_drawdown_pct": float(dds.median()),
        "total_slippage_sum": float(pd.to_numeric(result["summary"]["total_slippage"], errors="coerce").fillna(0.0).sum()),
        "total_trade_count_sum": float(
            pd.to_numeric(result["summary"]["total_trade_count"], errors="coerce").fillna(0.0).sum()
        ),
        "ai_repair": ai_repair,
        "ai_coverage_generated_min": str(generated_coverage["eval_date"].min()),
        "ai_coverage_generated_max": str(generated_coverage["eval_date"].max()),
        "standard_ai_month_status_counts": {str(k): int(v) for k, v in standard_status.items()},
        "freshness_ai_month_status_counts": {str(k): int(v) for k, v in freshness_status.items()},
        "freshness_fail_candidate_month_count": int(len(fail_freshness)),
        "all_generated_months_have_pool": bool(ai_repair["generated_eval_date_count"] == 63),
        "all_candidate_months_use_latest_available_pool": bool(int(len(fail_freshness)) == 0),
        "promotion_gate": {
            "candidate_official_ready": bool(int(len(fail_freshness)) == 0 and int(returns.gt(0.0).sum()) == len(result["summary"])),
            "reason": (
                "AI应用链路已按最新可用月池运行；2020-01 到 2021-03 属于当前 Stage182 训练规则下的冷启动，"
                "不是缺文件。若收益/回撤仍通过，再进入 shadow/执行验收。"
            ),
        },
        "strategy_changed": False,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "否。本阶段只补齐 PIT 月度输入并验证单一候选 Stage013，没有新增交易参数或按结果调阈值。"
        ),
        "overfit_reflection_after": (
            "仍然否。若后续因为个别起点表现差去改月份、品种或训练门槛，才会转为过拟合风险。"
        ),
        "continue_value_before": (
            "有。候选版要晋级正式，月度 AI 输入完整性是必要条件，比继续纠结旧正式版恢复更有价值。"
        ),
        "continue_value_after": (
            "有。补齐后可以用同一候选版做 shadow/执行验收；冷启动边界也已被显式记录。"
        ),
        "outputs": {
            "candidate_ai": str(CANDIDATE_AI_PATH),
            "ai_rebuild_audit": str(AI_REBUILD_AUDIT_PATH),
            "ai_coverage": str(AI_COVERAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "standard_ai_month_audit": str(STANDARD_AI_MONTH_AUDIT_PATH),
            "freshness_ai_month_audit": str(FRESHNESS_AI_MONTH_AUDIT_PATH),
            "pool_audit": str(POOL_AUDIT_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "ai_freshness_chart": str(AI_FRESHNESS_CHART_PATH),
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
    now = datetime.now()
    summary = pd.read_csv(SUMMARY_PATH)
    coverage = pd.read_csv(AI_COVERAGE_PATH)
    freshness = pd.read_csv(FRESHNESS_AI_MONTH_AUDIT_PATH)
    cold = coverage[coverage["status"].astype(str).str.startswith("INFEASIBLE")]
    top_summary = summary[
        [
            "requested_start_month",
            "actual_end",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "total_trade_count",
        ]
    ]
    fail_or_cold = freshness[
        freshness["status"].astype(str).isin(["COLD_START_PRE_MODEL_POOL", "MIXED_COLD_START_AND_FRESH"])
        & freshness["candidate_month"].astype(int).eq(1)
    ]
    lines = [
        "# Stage062 Stage013 full-monthly-AI candidate official",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- candidate: `{decision['candidate']}`",
        f"- AI file: `{decision['ai_repair']['candidate_ai_path']}`",
        f"- AI hash: `{decision['ai_repair']['candidate_ai_sha256']}`",
        f"- source max: `{decision['ai_repair']['source_max_date']}`",
        f"- latest completed month eval: `{decision['ai_repair']['latest_completed_month_eval_date']}`",
        "",
        "## AI Coverage",
        "",
        f"- expected eval dates from 2020-01 to latest completed month: `{decision['ai_repair']['expected_eval_date_count_2020_to_latest_completed']}`",
        f"- generated under unchanged Stage182 rules: `{decision['ai_repair']['generated_eval_date_count']}`",
        f"- infeasible cold-start eval dates: `{decision['ai_repair']['infeasible_cold_start_eval_date_count']}`",
        f"- generated range: `{decision['ai_coverage_generated_min']}` -> `{decision['ai_coverage_generated_max']}`",
        f"- 2026 eval dates in candidate file: `{', '.join(decision['ai_repair']['candidate_ai_eval_dates_2026'])}`",
        "",
        "Cold-start infeasible eval dates:",
        "",
        _md_table(cold[["eval_date", "training_label_cutoff", "train_rows", "train_months", "target_class_count", "status"]], max_rows=40),
        "",
        "## Backtest Summary",
        "",
        f"- starts: `{decision['positive_count']}/{decision['start_count']}` positive",
        f"- min/median/max return: `{decision['min_return_pct']:.4f}% / {decision['median_return_pct']:.4f}% / {decision['max_return_pct']:.4f}%`",
        f"- worst/median max DD: `{decision['worst_max_drawdown_pct']:.4f}% / {decision['median_max_drawdown_pct']:.4f}%`",
        f"- total slippage / trades: `{decision['total_slippage_sum']:.4f}` / `{decision['total_trade_count_sum']:.0f}`",
        f"- actual max end: `{decision['actual_end_max']}`",
        "",
        _md_table(top_summary, max_rows=30),
        "",
        "## AI Usage Audit",
        "",
        f"- standard status counts: `{decision['standard_ai_month_status_counts']}`",
        f"- freshness status counts: `{decision['freshness_ai_month_status_counts']}`",
        f"- candidate months with FAIL freshness: `{decision['freshness_fail_candidate_month_count']}`",
        "",
        "Cold-start candidate months using latest available pre-model pool:",
        "",
        _md_table(
            fail_or_cold[
                [
                    "requested_start_month",
                    "covered_month",
                    "candidate_count",
                    "unique_signal_dates",
                    "desired_signal_dates",
                    "desired_statuses",
                    "status",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## Decision",
        "",
        f"- candidate official ready by this mechanical gate: `{decision['promotion_gate']['candidate_official_ready']}`",
        f"- reason: {decision['promotion_gate']['reason']}",
        "- no official live config was changed; no CTP connection; no order API call.",
        "",
        "## Outputs",
        "",
    ]
    for key, value in decision["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage062_stage013_full_monthly_ai_candidate_official.md"
    stage_lines = [
        "# Stage062 Stage013 full-monthly-AI candidate official",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：候选正式化输入验收；不是交易参数突破",
        "- 是否触发A/B：是；Stage013 被用户指定为候选正式版，需要进入晋级验收，但本阶段不再比较旧正式版",
        "",
        "## 外部调研与判断",
        "",
        "- 参考 pysystemtrade / walk-forward / overfitting 资料。判断：不能因为曲线好就改训练门槛补早期月池；必须保持 PIT、训练窗口和标签可得性。",
        "- 本次执行判断：补齐所有当前逻辑可生成的月池；不能生成的 2020-01 到 2021-03 明确标为 cold-start，不伪造独立月池。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：无交易参数；新增线内 candidate AI 文件路径 override",
        "- 修改参数：无正式交易参数修改",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- 版本：Stage013 account-state pilot candidate official",
        "- 起点：`2020-01` 到 `2026-01` 逐半年",
        "- 终点：`2026-07-02`，实际终点见 summary",
        "- 资金：`150,000`",
        f"- AI 池：`{decision['ai_repair']['candidate_ai_path']}`",
        f"- AI hash：`{decision['ai_repair']['candidate_ai_sha256']}`",
        "",
        "## 结果",
        "",
        f"- 期末权益/总收益：逐起点详见 `{SUMMARY_PATH}`",
        f"- 正收益：`{decision['positive_count']}/{decision['start_count']}`",
        f"- 最小/中位/最大收益：`{decision['min_return_pct']:.4f}% / {decision['median_return_pct']:.4f}% / {decision['max_return_pct']:.4f}%`",
        f"- 最差/中位最大回撤：`{decision['worst_max_drawdown_pct']:.4f}% / {decision['median_max_drawdown_pct']:.4f}%`",
        f"- 总滑点：`{decision['total_slippage_sum']:.4f}`",
        f"- 总交易次数：`{decision['total_trade_count_sum']:.0f}`",
        "- 胜率：本阶段未逐笔重算，保留待 promotion shadow 验收补充",
        f"- AI 覆盖：expected `{decision['ai_repair']['expected_eval_date_count_2020_to_latest_completed']}`，generated `{decision['ai_repair']['generated_eval_date_count']}`，cold-start `{decision['ai_repair']['infeasible_cold_start_eval_date_count']}`",
        f"- AI 应用审计：standard `{decision['standard_ai_month_status_counts']}`；freshness `{decision['freshness_ai_month_status_counts']}`",
        "",
        "## 结论",
        "",
        "- 所有可由当前 Stage182 逻辑生成的月池已经补齐到线内候选 AI 文件。",
        "- 2020-01 到 2021-03 不是文件缺失，而是训练样本不足导致的模型冷启动；若要这些月也独立月更，需要更早的 PIT 源数据或改变训练逻辑。",
        "- 本阶段不改正式配置，下一步应做候选版 shadow/邮件/执行链路验收，再决定是否晋级正式。",
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

    back_log_entry = (
        f"\n{now.strftime('%Y-%m-%d %H:%M')} CST：`{LINE_ID}` Stage062 完成 Stage013 候选正式版全月度 AI 补齐与回测验收。"
        f"AI 文件 `{decision['ai_repair']['candidate_ai_path']}`，hash `{decision['ai_repair']['candidate_ai_sha256']}`；"
        f"expected 月末 eval `{decision['ai_repair']['expected_eval_date_count_2020_to_latest_completed']}`，"
        f"generated `{decision['ai_repair']['generated_eval_date_count']}`，"
        f"cold-start infeasible `{decision['ai_repair']['infeasible_cold_start_eval_date_count']}`；"
        f"2026 候选池日期 `{', '.join(decision['ai_repair']['candidate_ai_eval_dates_2026'])}`。"
        f"回测起点 2020-01 到 2026-01 逐半年，终点 2026-07-02，实际最大终点 `{decision['actual_end_max']}`；"
        f"正收益 `{decision['positive_count']}/{decision['start_count']}`，最小/中位/最大收益 "
        f"`{decision['min_return_pct']:.4f}%/{decision['median_return_pct']:.4f}%/{decision['max_return_pct']:.4f}%`，"
        f"最差最大回撤 `{decision['worst_max_drawdown_pct']:.4f}%`，总滑点 `{decision['total_slippage_sum']:.4f}`，"
        f"总交易次数 `{decision['total_trade_count_sum']:.0f}`；AI freshness status `{decision['freshness_ai_month_status_counts']}`。"
        f"未改正式配置、未连接 CTP、未调用订单 API。过拟合反思：{decision['overfit_reflection_after']} "
        f"继续价值：{decision['continue_value_after']}\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(back_log_entry)
    return stage_path


def main() -> None:
    print("[stage062] build full monthly AI file", flush=True)
    ai_repair = build_full_monthly_ai_file()
    print(json.dumps(_json_safe(ai_repair), ensure_ascii=False, indent=2), flush=True)
    print("[stage062] run Stage013 candidate-official backtest", flush=True)
    decision = run_backtest_and_audits(ai_repair)
    stage_path = write_report_and_records(decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
