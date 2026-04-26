from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

import build_qmt_roll_ai_candidate_training_samples as candidate_samples
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import (
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_trades_df,
)
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage164_ai_path_damage_discount_avc_backtest import (
    PROFILE_C,
    _build_arms,
    _target_windows,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage165_ai_path_damage_runtime_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage165_ai_path_damage_runtime_attribution"

CANDIDATE_DETAIL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_detail_{MODEL_TAG}.csv"
ENTRY_RISK_DETAIL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_detail_{MODEL_TAG}.csv"
TRADES_DETAIL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_detail_{MODEL_TAG}.csv"
LABELED_SAMPLES_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_labeled_samples_{MODEL_TAG}.csv"
WINDOW_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
YEAR_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_attribution_{MODEL_TAG}.csv"
SEGMENT_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segment_attribution_{MODEL_TAG}.csv"
DISCOUNTED_CASES_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_discounted_cases_{MODEL_TAG}.csv"
RUN_LOG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_log_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _target_c_arm() -> dict[str, Any]:
    for arm in _build_arms():
        if arm.profile_name == PROFILE_C:
            return {
                "profile_name": arm.profile_name,
                "arm": arm.arm,
                "hypothesis": arm.hypothesis,
                "strategy_overrides": arm.strategy_overrides,
            }
    raise ValueError(f"missing arm {PROFILE_C}")


def _run_c_window(window: dict[str, Any], arm: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    window_name = str(window["window_name"])
    analysis_start: datetime = window["analysis_start"]
    analysis_end: datetime = window["analysis_end"]
    print(f"[stage165-runtime-attribution] {window_name} / {arm['profile_name']}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)

    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, _, _ = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=arm["strategy_overrides"],
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    candidates = build_entry_candidate_snapshots_df(engine)
    risks = build_entry_risk_diagnostics_df(engine)
    trades = build_trades_df(engine)
    for frame in (candidates, risks, trades):
        if not frame.empty:
            frame.insert(0, "window_name", window_name)
            frame.insert(1, "profile_name", str(arm["profile_name"]))
            frame.insert(2, "analysis_start", analysis_start.date().isoformat())
            frame.insert(3, "analysis_end", analysis_end.date().isoformat())

    run_log = pd.DataFrame(
        {
            "profile_name": [arm["profile_name"]],
            "window_name": [window_name],
            "log_line": ["\n".join(log_buffer.getvalue().splitlines()[-40:])],
        }
    )
    return candidates, risks, trades, run_log


def _build_labeled_samples_for_window(
    *,
    window_name: str,
    candidates: pd.DataFrame,
    risks: pd.DataFrame,
    trades: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    candidate_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{window_name}_candidate_snapshots_tmp_{MODEL_TAG}.csv"
    risk_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{window_name}_entry_risk_tmp_{MODEL_TAG}.csv"
    trades_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{window_name}_trades_tmp_{MODEL_TAG}.csv"
    candidates.to_csv(candidate_path, index=False, encoding="utf-8-sig")
    risks.to_csv(risk_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")

    original_paths = (
        candidate_samples.CANDIDATE_PATH,
        candidate_samples.ENTRY_RISK_PATH,
        candidate_samples.TRADES_PATH,
    )
    candidate_samples.CANDIDATE_PATH = candidate_path
    candidate_samples.ENTRY_RISK_PATH = risk_path
    candidate_samples.TRADES_PATH = trades_path
    try:
        samples, coverage = candidate_samples.build_training_samples()
    finally:
        (
            candidate_samples.CANDIDATE_PATH,
            candidate_samples.ENTRY_RISK_PATH,
            candidate_samples.TRADES_PATH,
        ) = original_paths

    if not samples.empty:
        samples.insert(0, "window_name", window_name)
    return samples, coverage


def _merge_discount_fields(samples: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    if samples.empty:
        return samples
    discount_columns = [
        "window_name",
        "candidate_index",
        "ai_path_damage_enabled",
        "ai_path_damage_model_tag",
        "ai_path_damage_probability",
        "ai_path_damage_discount_weight",
        "ai_path_damage_discount_applied",
        "ai_path_damage_feature_available",
        "ai_path_damage_selected_volume_before",
        "ai_path_damage_selected_volume_after",
    ]
    available = [column for column in discount_columns if column in candidates.columns]
    discount = candidates[available].copy()
    merged = samples.merge(discount, on=["window_name", "candidate_index"], how="left", suffixes=("", "_runtime"))
    for column in discount_columns:
        if column in {"window_name", "candidate_index"}:
            continue
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    return merged


def _add_counterfactual_columns(samples: pd.DataFrame) -> pd.DataFrame:
    frame = samples.copy()
    numeric_columns = [
        "label_is_selected",
        "label_realized_pnl_amount",
        "ai_path_damage_probability",
        "ai_path_damage_discount_weight",
        "ai_path_damage_discount_applied",
        "ai_path_damage_feature_available",
        "ai_path_damage_selected_volume_before",
        "ai_path_damage_selected_volume_after",
        "label_stage163_20d_mae_r",
        "label_stage163_40d_mae_r",
        "label_candidate_forward_20d_r_multiple",
    ]
    for column in numeric_columns:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    after_volume = frame["ai_path_damage_selected_volume_after"].astype("float64")
    before_volume = frame["ai_path_damage_selected_volume_before"].astype("float64")
    volume_weight = pd.Series(1.0, index=frame.index, dtype="float64")
    valid_volume_mask = before_volume > 0.0
    volume_weight.loc[valid_volume_mask] = (
        after_volume.loc[valid_volume_mask] / before_volume.loc[valid_volume_mask]
    )
    frame["stage165_runtime_volume_weight"] = volume_weight.replace([math.inf, -math.inf], 1.0).fillna(1.0)
    estimated_without_discount = frame["label_realized_pnl_amount"].astype("float64").copy()
    weight_mask = frame["stage165_runtime_volume_weight"].abs() > 1e-12
    estimated_without_discount.loc[weight_mask] = (
        frame.loc[weight_mask, "label_realized_pnl_amount"]
        / frame.loc[weight_mask, "stage165_runtime_volume_weight"]
    )
    frame["stage165_estimated_pnl_without_discount"] = estimated_without_discount.astype("float64").fillna(
        frame["label_realized_pnl_amount"]
    )
    frame["stage165_estimated_pnl_delta_from_discount"] = (
        frame["label_realized_pnl_amount"] - frame["stage165_estimated_pnl_without_discount"]
    )
    frame["stage165_discount_helped_loser"] = (
        (frame["ai_path_damage_discount_applied"] > 0)
        & (frame["stage165_estimated_pnl_without_discount"] < 0)
        & (frame["stage165_estimated_pnl_delta_from_discount"] > 0)
    ).astype("int64")
    frame["stage165_discount_hurt_winner"] = (
        (frame["ai_path_damage_discount_applied"] > 0)
        & (frame["stage165_estimated_pnl_without_discount"] > 0)
        & (frame["stage165_estimated_pnl_delta_from_discount"] < 0)
    ).astype("int64")
    frame["candidate_date"] = pd.to_datetime(frame["candidate_date"])
    frame["candidate_year"] = frame["candidate_date"].dt.year.astype("int64")
    frame["direction_signal"] = frame["direction"].astype(str) + "/" + frame["signal"].astype(str)
    return frame


def _summarize_group(group: pd.DataFrame, group_keys: dict[str, Any]) -> dict[str, Any]:
    selected = group[pd.to_numeric(group.get("label_is_selected", 0), errors="coerce").fillna(0.0) > 0].copy()
    discounted = selected[pd.to_numeric(selected.get("ai_path_damage_discount_applied", 0), errors="coerce").fillna(0.0) > 0].copy()
    row = dict(group_keys)
    row.update(
        {
            "selected_count": int(len(selected)),
            "discounted_selected_count": int(len(discounted)),
            "discounted_loser_count": int((discounted["stage165_estimated_pnl_without_discount"] < 0).sum()) if not discounted.empty else 0,
            "discounted_winner_count": int((discounted["stage165_estimated_pnl_without_discount"] > 0).sum()) if not discounted.empty else 0,
            "volume_before": int(_safe_float(discounted["ai_path_damage_selected_volume_before"].sum())) if not discounted.empty else 0,
            "volume_after": int(_safe_float(discounted["ai_path_damage_selected_volume_after"].sum())) if not discounted.empty else 0,
            "realized_pnl_with_discount": _safe_float(discounted["label_realized_pnl_amount"].sum()) if not discounted.empty else 0.0,
            "estimated_pnl_without_discount": _safe_float(discounted["stage165_estimated_pnl_without_discount"].sum()) if not discounted.empty else 0.0,
            "estimated_pnl_delta_from_discount": _safe_float(discounted["stage165_estimated_pnl_delta_from_discount"].sum()) if not discounted.empty else 0.0,
            "helped_loser_delta": _safe_float(
                discounted.loc[discounted["stage165_discount_helped_loser"] > 0, "stage165_estimated_pnl_delta_from_discount"].sum()
            )
            if not discounted.empty
            else 0.0,
            "hurt_winner_delta": _safe_float(
                discounted.loc[discounted["stage165_discount_hurt_winner"] > 0, "stage165_estimated_pnl_delta_from_discount"].sum()
            )
            if not discounted.empty
            else 0.0,
            "avg_probability": _safe_float(discounted["ai_path_damage_probability"].mean()) if not discounted.empty else 0.0,
            "avg_weight": _safe_float(discounted["ai_path_damage_discount_weight"].mean(), 1.0) if not discounted.empty else 1.0,
            "avg_20d_mae_r": _safe_float(discounted["label_stage163_20d_mae_r"].mean()) if "label_stage163_20d_mae_r" in discounted else 0.0,
            "avg_40d_mae_r": _safe_float(discounted["label_stage163_40d_mae_r"].mean()) if "label_stage163_40d_mae_r" in discounted else 0.0,
            "avg_20d_forward_r": _safe_float(discounted["label_candidate_forward_20d_r_multiple"].mean()) if not discounted.empty else 0.0,
        }
    )
    return row


def _build_window_attribution(samples: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window_name, group in samples.groupby("window_name", sort=False):
        rows.append(_summarize_group(group, {"window_name": window_name}))
    return pd.DataFrame(rows)


def _build_year_attribution(samples: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (window_name, year), group in samples.groupby(["window_name", "candidate_year"], sort=False):
        rows.append(_summarize_group(group, {"window_name": window_name, "candidate_year": int(year)}))
    return pd.DataFrame(rows)


def _build_segment_attribution(samples: pd.DataFrame) -> pd.DataFrame:
    rows = []
    filtered = samples[pd.to_numeric(samples.get("ai_path_damage_discount_applied", 0), errors="coerce").fillna(0.0) > 0].copy()
    if filtered.empty:
        return pd.DataFrame()
    for (window_name, direction_signal), group in filtered.groupby(["window_name", "direction_signal"], sort=False):
        rows.append(_summarize_group(group, {"window_name": window_name, "direction_signal": direction_signal}))
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["window_name", "estimated_pnl_delta_from_discount"], inplace=True)
    return result


def _build_discounted_cases(samples: pd.DataFrame) -> pd.DataFrame:
    cases = samples[
        (pd.to_numeric(samples.get("label_is_selected", 0), errors="coerce").fillna(0.0) > 0)
        & (pd.to_numeric(samples.get("ai_path_damage_discount_applied", 0), errors="coerce").fillna(0.0) > 0)
    ].copy()
    columns = [
        "window_name",
        "candidate_date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "ai_path_damage_probability",
        "ai_path_damage_discount_weight",
        "ai_path_damage_selected_volume_before",
        "ai_path_damage_selected_volume_after",
        "label_realized_pnl_amount",
        "stage165_estimated_pnl_without_discount",
        "stage165_estimated_pnl_delta_from_discount",
        "label_stage163_20d_mae_r",
        "label_stage163_40d_mae_r",
        "label_candidate_forward_20d_r_multiple",
    ]
    available = [column for column in columns if column in cases.columns]
    cases = cases[available].copy()
    if not cases.empty:
        cases.sort_values(["window_name", "stage165_estimated_pnl_delta_from_discount"], inplace=True)
    return cases


def _decision(window_attr: pd.DataFrame) -> str:
    if window_attr.empty:
        return "fail_no_attribution_rows"
    by_window = {str(row["window_name"]): row for row in window_attr.to_dict(orient="records")}
    full_delta = _safe_float(by_window.get("full_2020_2026", {}).get("estimated_pnl_delta_from_discount"))
    latest_delta = _safe_float(by_window.get("latest_2026", {}).get("estimated_pnl_delta_from_discount"))
    if latest_delta > 0 and full_delta < 0:
        return "state_conditioning_needed_not_always_on"
    if full_delta >= 0:
        return "discount_attribution_supports_further_validation"
    return "always_on_discount_hurts_selected_trade_pnl"


def _build_report(
    window_attr: pd.DataFrame,
    year_attr: pd.DataFrame,
    segment_attr: pd.DataFrame,
    discounted_cases: pd.DataFrame,
    decision: str,
) -> str:
    window_columns = [
        "window_name",
        "selected_count",
        "discounted_selected_count",
        "discounted_loser_count",
        "discounted_winner_count",
        "volume_before",
        "volume_after",
        "estimated_pnl_delta_from_discount",
        "helped_loser_delta",
        "hurt_winner_delta",
        "avg_probability",
        "avg_weight",
    ]
    year_columns = [
        "window_name",
        "candidate_year",
        "discounted_selected_count",
        "estimated_pnl_delta_from_discount",
        "helped_loser_delta",
        "hurt_winner_delta",
    ]
    segment_columns = [
        "window_name",
        "direction_signal",
        "discounted_selected_count",
        "estimated_pnl_delta_from_discount",
        "helped_loser_delta",
        "hurt_winner_delta",
    ]
    case_columns = [
        "window_name",
        "candidate_date",
        "product_vt_symbol",
        "direction",
        "signal",
        "ai_path_damage_probability",
        "ai_path_damage_selected_volume_before",
        "ai_path_damage_selected_volume_after",
        "label_realized_pnl_amount",
        "stage165_estimated_pnl_delta_from_discount",
    ]
    return "\n".join(
        [
            "# Stage165 AI Path-Damage Runtime Attribution",
            "",
            "## Boundary",
            "",
            "- This is attribution only, not a new trading version.",
            "- It reruns the frozen Stage164 C arm to export runtime candidate details.",
            "- The goal is to explain where the always-on discount helped or hurt.",
            "",
            "## Window Attribution",
            "",
            to_markdown_table(window_attr[[column for column in window_columns if column in window_attr.columns]]),
            "",
            "## Year Attribution",
            "",
            to_markdown_table(year_attr[[column for column in year_columns if column in year_attr.columns]].head(40))
            if not year_attr.empty
            else "_empty_",
            "",
            "## Worst/Best Segments",
            "",
            to_markdown_table(segment_attr[[column for column in segment_columns if column in segment_attr.columns]].head(30))
            if not segment_attr.empty
            else "_empty_",
            "",
            "## Discounted Cases",
            "",
            to_markdown_table(discounted_cases[[column for column in case_columns if column in discounted_cases.columns]].head(40))
            if not discounted_cases.empty
            else "_empty_",
            "",
            "## Decision",
            "",
            f"- `{decision}`",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    arm = _target_c_arm()
    windows = _target_windows()

    candidate_frames: list[pd.DataFrame] = []
    risk_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    sample_frames: list[pd.DataFrame] = []
    run_log_frames: list[pd.DataFrame] = []
    coverage_by_window: dict[str, Any] = {}

    for window in windows:
        window_name = str(window["window_name"])
        candidates, risks, trades, run_log = _run_c_window(window, arm)
        candidate_frames.append(candidates)
        risk_frames.append(risks)
        trade_frames.append(trades)
        run_log_frames.append(run_log)
        samples, coverage = _build_labeled_samples_for_window(
            window_name=window_name,
            candidates=candidates,
            risks=risks,
            trades=trades,
        )
        coverage_by_window[window_name] = coverage
        if not samples.empty:
            sample_frames.append(samples)

    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    risks_all = pd.concat(risk_frames, ignore_index=True, sort=False) if risk_frames else pd.DataFrame()
    trades_all = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    samples_all = pd.concat(sample_frames, ignore_index=True, sort=False) if sample_frames else pd.DataFrame()
    run_log_all = pd.concat(run_log_frames, ignore_index=True, sort=False) if run_log_frames else pd.DataFrame()

    samples_all = _merge_discount_fields(samples_all, candidates_all)
    samples_all = _add_counterfactual_columns(samples_all)
    window_attr = _build_window_attribution(samples_all)
    year_attr = _build_year_attribution(samples_all)
    segment_attr = _build_segment_attribution(samples_all)
    discounted_cases = _build_discounted_cases(samples_all)
    decision = _decision(window_attr)

    candidates_all.to_csv(CANDIDATE_DETAIL_PATH, index=False, encoding="utf-8-sig")
    risks_all.to_csv(ENTRY_RISK_DETAIL_PATH, index=False, encoding="utf-8-sig")
    trades_all.to_csv(TRADES_DETAIL_PATH, index=False, encoding="utf-8-sig")
    samples_all.to_csv(LABELED_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    window_attr.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    year_attr.to_csv(YEAR_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    segment_attr.to_csv(SEGMENT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    discounted_cases.to_csv(DISCOUNTED_CASES_PATH, index=False, encoding="utf-8-sig")
    run_log_all.to_csv(RUN_LOG_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        _build_report(window_attr, year_attr, segment_attr, discounted_cases, decision),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "analysis_type": "runtime_attribution_no_new_strategy_version",
                "profile_name": arm["profile_name"],
                "decision": decision,
                "coverage_by_window": coverage_by_window,
                "window_attribution": window_attr.to_dict(orient="records"),
                "year_attribution": year_attr.to_dict(orient="records"),
                "segment_attribution": segment_attr.to_dict(orient="records"),
                "discounted_cases": discounted_cases.head(80).to_dict(orient="records"),
                "output_paths": {
                    "candidate_detail": str(CANDIDATE_DETAIL_PATH),
                    "entry_risk_detail": str(ENTRY_RISK_DETAIL_PATH),
                    "trades_detail": str(TRADES_DETAIL_PATH),
                    "labeled_samples": str(LABELED_SAMPLES_PATH),
                    "window_attribution": str(WINDOW_ATTRIBUTION_PATH),
                    "year_attribution": str(YEAR_ATTRIBUTION_PATH),
                    "segment_attribution": str(SEGMENT_ATTRIBUTION_PATH),
                    "discounted_cases": str(DISCOUNTED_CASES_PATH),
                    "run_log": str(RUN_LOG_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage165-runtime-attribution] window attribution: {WINDOW_ATTRIBUTION_PATH}")
    print(f"[stage165-runtime-attribution] discounted cases: {DISCOUNTED_CASES_PATH}")
    print(f"[stage165-runtime-attribution] report: {REPORT_PATH}")
    print(f"[stage165-runtime-attribution] decision: {decision}")
    print(window_attr.to_string(index=False))
    if not segment_attr.empty:
        print(segment_attr.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
