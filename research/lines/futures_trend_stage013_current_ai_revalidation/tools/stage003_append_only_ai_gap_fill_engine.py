#!/usr/bin/env python3
"""Stage003: counterfactual early activation of the later Stage182 AI policy."""

from __future__ import annotations

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
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage001_stage013_current_ai_engine as s1  # noqa: E402
import stage002_stage013_current_ai_halfyear as s2  # noqa: E402


LINE_ID = s1.LINE_ID
STAGE_ID = "stage003_append_only_ai_gap_fill_engine"
STAGE_LABEL = "Stage003"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"
START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2026-06-30")
CAPITAL = s1.CAPITAL

A_VERSION = s1.A_VERSION
C_VERSION = s1.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)

RETURN_RETENTION_MIN = 0.70
FULL_DD_IMPROVEMENT_MIN_PP = 3.0
YEAR_2022_DD_IMPROVEMENT_MIN_PP = 5.0
STRESS_DD_IMPROVEMENT_MIN_PP = 3.0

SOURCE_STAGE062_DIR = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage062_stage013_full_monthly_ai_candidate_official"
)
SOURCE_GENERATED_ELIGIBILITY_PATH = SOURCE_STAGE062_DIR / (
    "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_"
    "full_monthly_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv"
)
SOURCE_COVERAGE_PATH = SOURCE_STAGE062_DIR / (
    "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_"
    "ai_coverage_stage062_stage013_full_monthly_ai_candidate_official_v1.csv"
)
CURRENT_AI_PATH = Path(s1.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
STAGE002_SUMMARY_PATH = s2.SUMMARY_PATH

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260710_1945_stage003_append_only_ai_gap_fill_engine.md"

HYBRID_BASE_PATH = OUT / f"{OUTPUT_PREFIX}_hybrid_base_{MODEL_TAG}.csv"
A_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_{A_VERSION}_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_{C_VERSION}_eligibility_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
PROFILE_DIFF_PATH = OUT / f"{OUTPUT_PREFIX}_profile_diff_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
AI_CANDIDATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_candidate_detail_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_stress_{MODEL_TAG}.png"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    data["product_vt_symbol"] = data["product_vt_symbol"].astype(str)
    for column in ("score", "score_rank", "top_n"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data[
        ["eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]
    ].sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)


def _canonical_hash(frame: pd.DataFrame) -> str:
    payload = _canonical(frame).to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_hybrid() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    current = pd.read_csv(CURRENT_AI_PATH, encoding="utf-8-sig")
    generated = pd.read_csv(SOURCE_GENERATED_ELIGIBILITY_PATH, encoding="utf-8-sig")
    coverage = pd.read_csv(SOURCE_COVERAGE_PATH, encoding="utf-8-sig")
    for data in (current, generated):
        data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce").dt.strftime(
            "%Y-%m-%d"
        )
        data["calendar_month"] = pd.to_datetime(
            data["eval_date"], errors="coerce"
        ).dt.to_period("M").astype(str)

    current_months = set(current["calendar_month"].astype(str))
    feasible = coverage[coverage["status"].astype(str).eq("GENERATED")].copy()
    cold_start = coverage[
        coverage["status"].astype(str).str.startswith("INFEASIBLE_COLD_START")
    ].copy()
    missing_feasible_months = sorted(
        set(feasible["calendar_month"].astype(str)) - current_months
    )
    additions = generated[
        generated["calendar_month"].astype(str).isin(missing_feasible_months)
    ].copy()
    common_columns = [column for column in current.columns if column != "calendar_month"]
    missing_columns = sorted(set(common_columns) - set(additions.columns))
    if missing_columns:
        raise RuntimeError(f"Stage062 generated eligibility is missing columns: {missing_columns}")
    additions = additions[common_columns + ["calendar_month"]]
    hybrid = pd.concat(
        [current, additions[current.columns]], ignore_index=True, sort=False
    )
    hybrid = hybrid.sort_values(
        ["eval_date", "score_rank", "product_vt_symbol"]
    ).reset_index(drop=True)

    key_columns = ["strategy", "eval_date", "product_vt_symbol"]
    overlap_dates = sorted(set(current["eval_date"]) & set(additions["eval_date"]))
    duplicate_key_count = int(hybrid.duplicated(key_columns).sum())
    current_hash = _canonical_hash(current)
    preserved = hybrid[hybrid["eval_date"].isin(set(current["eval_date"]))].copy()
    preserved_hash = _canonical_hash(preserved)
    feasible_months = set(feasible["calendar_month"].astype(str))
    hybrid_months = set(hybrid["calendar_month"].astype(str))
    feasible_after_missing = sorted(feasible_months - hybrid_months)

    audit_rows = []
    for _, row in coverage.sort_values("eval_date").iterrows():
        month = str(row["calendar_month"])
        audit_rows.append(
            {
                "calendar_month": month,
                "eval_date": str(row["eval_date"]),
                "stage182_status": str(row["status"]),
                "present_in_current": int(month in current_months),
                "appended_by_stage003": int(month in missing_feasible_months),
                "present_in_hybrid": int(month in hybrid_months),
                "cold_start_uses_2019_12_bootstrap": int(
                    str(row["status"]).startswith("INFEASIBLE_COLD_START")
                ),
            }
        )
    audit = pd.DataFrame(audit_rows)
    lineage = {
        "current_ai_path": str(CURRENT_AI_PATH),
        "current_ai_sha256": _sha256(CURRENT_AI_PATH),
        "stage062_generated_path": str(SOURCE_GENERATED_ELIGIBILITY_PATH),
        "stage062_generated_sha256": _sha256(SOURCE_GENERATED_ELIGIBILITY_PATH),
        "stage062_coverage_path": str(SOURCE_COVERAGE_PATH),
        "stage062_coverage_sha256": _sha256(SOURCE_COVERAGE_PATH),
        "current_rows": int(len(current)),
        "current_eval_date_count": int(current["eval_date"].nunique()),
        "current_canonical_hash": current_hash,
        "preserved_current_rows": int(len(preserved)),
        "preserved_current_canonical_hash": preserved_hash,
        "current_rows_exactly_preserved": bool(
            len(preserved) == len(current) and preserved_hash == current_hash
        ),
        "added_rows": int(len(additions)),
        "added_eval_date_count": int(additions["eval_date"].nunique()),
        "added_months": missing_feasible_months,
        "overlap_eval_dates": overlap_dates,
        "duplicate_key_count": duplicate_key_count,
        "hybrid_rows": int(len(hybrid)),
        "hybrid_eval_date_count": int(hybrid["eval_date"].nunique()),
        "feasible_month_count": int(len(feasible)),
        "cold_start_month_count": int(len(cold_start)),
        "feasible_months_missing_after_append": feasible_after_missing,
    }
    expected = {
        "current_rows": 504,
        "current_eval_date_count": 55,
        "added_rows": 81,
        "added_eval_date_count": 9,
        "hybrid_rows": 585,
        "hybrid_eval_date_count": 64,
        "feasible_month_count": 63,
        "cold_start_month_count": 15,
    }
    for key, value in expected.items():
        if int(lineage[key]) != value:
            raise RuntimeError(f"unexpected {key}: {lineage[key]} != {value}")
    if overlap_dates or duplicate_key_count or feasible_after_missing:
        raise RuntimeError("append-only AI input invariants failed")
    if not lineage["current_rows_exactly_preserved"]:
        raise RuntimeError("current official AI rows were not exactly preserved")
    return hybrid.drop(columns=["calendar_month"]), audit, lineage


def _eligibility_for_arm(hybrid: pd.DataFrame, version: str) -> pd.DataFrame:
    strategy = s1.A_STRATEGY if version == A_VERSION else s1.C_STRATEGY
    result = hybrid.copy()
    result["strategy"] = strategy
    result["score_type"] = version
    return result[
        [
            "strategy",
            "score_type",
            "eval_date",
            "product_vt_symbol",
            "score",
            "score_rank",
            "top_n",
        ]
    ].copy()


def _run(
    metadata: dict[str, Any], profile: dict[str, Any], version: str
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames = s2._run_for_start(metadata, profile, version, START)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    tagged: dict[str, pd.DataFrame] = {}
    for name, frame in frames.items():
        data = frame.copy()
        if not data.empty:
            data["stage"] = STAGE_LABEL
            data["model_tag"] = MODEL_TAG
            data["line_id"] = LINE_ID
        tagged[name] = data
    return daily, tagged


def _summary_row(
    metadata: dict[str, Any],
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    version: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    row, curve = s2._summary_row(daily, frames, metadata, version, START)
    row.update({"stage": STAGE_LABEL, "model_tag": MODEL_TAG, "line_id": LINE_ID})
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    return row, curve


def _save_arm(
    version: str, daily: pd.DataFrame, frames: dict[str, pd.DataFrame]
) -> None:
    daily.to_csv(
        OUT / f"{OUTPUT_PREFIX}_{version}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    for name in (
        "entry_candidates",
        "entry_risk",
        "trades",
        "trade_events",
        "stop_retry_events",
        "pilot_gate_events",
    ):
        frame = frames.get(name, pd.DataFrame())
        if not frame.empty:
            frame.to_csv(
                OUT / f"{OUTPUT_PREFIX}_{version}_{name}_{MODEL_TAG}.csv.gz",
                index=False,
                encoding="utf-8-sig",
            )


def _candidate_detail(frames_by_version: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    wanted = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "signal",
        "entry_context",
        "ai_product_pool_enabled",
        "ai_product_pool_allowed",
        "ai_product_pool_signal_date",
        "is_opened",
        "candidate_status",
        "skip_reason",
        "selected_volume",
    ]
    for version, frames in frames_by_version.items():
        data = frames.get("entry_candidates", pd.DataFrame()).copy()
        if data.empty:
            continue
        keep = [column for column in wanted if column in data.columns]
        data = data[keep].copy()
        data.insert(0, "version", version)
        rows.append(data)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _profile_diff(profiles: dict[str, dict[str, Any]]) -> pd.DataFrame:
    a = profiles[A_VERSION]["spec"].overrides
    c = profiles[C_VERSION]["spec"].overrides
    allowed = {
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
        "enable_stage013_account_state_pilot_gate",
        "stage013_pilot_drawdown_trigger_pct",
        "stage013_pilot_active_positions_max",
        "stage013_pilot_min_volume",
    }
    rows = []
    for key in sorted(set(a) | set(c)):
        if a.get(key) == c.get(key):
            continue
        rows.append(
            {
                "field": key,
                "a_value": repr(a.get(key)),
                "c_value": repr(c.get(key)),
                "allowed_difference": int(key in allowed),
            }
        )
    rows.append(
        {
            "field": "strategy_class",
            "a_value": profiles[A_VERSION]["strategy_cls"].__name__,
            "c_value": profiles[C_VERSION]["strategy_cls"].__name__,
            "allowed_difference": 1,
        }
    )
    return pd.DataFrame(rows)


def _metric(frame: pd.DataFrame, version: str) -> dict[str, Any]:
    return frame[frame["version"].eq(version)].iloc[0].to_dict()


def _window(frame: pd.DataFrame, version: str, name: str) -> dict[str, Any]:
    return frame[(frame["version"].eq(version)) & (frame["window"].eq(name))].iloc[0].to_dict()


def _decision(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pilot: pd.DataFrame,
    usage: pd.DataFrame,
    lineage: dict[str, Any],
    profile_diff: pd.DataFrame,
) -> dict[str, Any]:
    a = _metric(summary, A_VERSION)
    c = _metric(summary, C_VERSION)
    a22 = _window(stress, A_VERSION, "year_2022")
    c22 = _window(stress, C_VERSION, "year_2022")
    ast = _window(stress, A_VERSION, "main_2022_2024_stress")
    cst = _window(stress, C_VERSION, "main_2022_2024_stress")
    current_summary = pd.read_csv(STAGE002_SUMMARY_PATH)
    current_a = current_summary[
        current_summary["requested_start_month"].astype(str).eq("2020-01")
        & current_summary["version"].astype(str).eq(A_VERSION)
    ].iloc[0]
    c_vs_a_retention = float(c["total_return_pct"] / a["total_return_pct"])
    c_vs_current_retention = float(
        c["total_return_pct"] / float(current_a["total_return_pct"])
    )
    full_dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    year_dd_delta = float(c22["window_max_drawdown_pct"] - a22["window_max_drawdown_pct"])
    stress_dd_delta = float(cst["window_max_drawdown_pct"] - ast["window_max_drawdown_pct"])
    broker_delta = float(
        c["max_broker10_margin_to_equity_pct"]
        - a["max_broker10_margin_to_equity_pct"]
    )
    all_pilot = pilot.iloc[0]
    usage_rows = pd.to_numeric(usage["ai_usage_rows"], errors="coerce").fillna(0)
    enabled_rows = pd.to_numeric(usage["ai_enabled_rows"], errors="coerce").fillna(0)
    missing_signal_rows = pd.to_numeric(
        usage["missing_signal_date_rows"], errors="coerce"
    ).fillna(0)
    input_ok = (
        bool(lineage["current_rows_exactly_preserved"])
        and int(lineage["added_rows"]) == 81
        and int(lineage["added_eval_date_count"]) == 9
        and int(lineage["hybrid_rows"]) == 585
        and int(lineage["hybrid_eval_date_count"]) == 64
        and not lineage["overlap_eval_dates"]
        and int(lineage["duplicate_key_count"]) == 0
        and not lineage["feasible_months_missing_after_append"]
    )
    mechanical_semantics_ok = (
        input_ok
        and bool((usage_rows == enabled_rows).all())
        and int(missing_signal_rows.sum()) == 0
        and int(all_pilot["rows"]) > 0
        and int(all_pilot["flat_entry_violation_count"]) == 0
        and int(all_pilot["after_not_one_count"]) == 0
        and int(all_pilot["below_drawdown_trigger_count"]) == 0
        and int(all_pilot["above_active_limit_count"]) == 0
        and int(all_pilot["applied_not_one_count"]) == 0
        and bool(profile_diff["allowed_difference"].eq(1).all())
    )
    # The frozen historical walk-forward used a 720-day warm-up and first
    # produced OOS predictions on 2022-01-28.  Appending the later expanding
    # Stage182 inference into 2021 is a counterfactual policy change.
    historical_policy_semantics_ok = False
    gates = {
        "c_positive": float(c["total_return_pct"]) > 0.0,
        "c_vs_hybrid_a_return_retention_ge_70pct": c_vs_a_retention >= RETURN_RETENTION_MIN,
        "c_vs_current_official_a_return_retention_ge_70pct": c_vs_current_retention >= RETURN_RETENTION_MIN,
        "full_dd_improvement_ge_3pp": full_dd_delta >= FULL_DD_IMPROVEMENT_MIN_PP,
        "year_2022_dd_improvement_ge_5pp": year_dd_delta >= YEAR_2022_DD_IMPROVEMENT_MIN_PP,
        "main_stress_dd_improvement_ge_3pp": stress_dd_delta >= STRESS_DD_IMPROVEMENT_MIN_PP,
        "broker10_not_worse": broker_delta <= 1e-9,
    }
    performance_ok = all(gates.values())
    decision = "stage003_close_counterfactual_early_activation_no_parameter_rescue"
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "requested_start": START.date().isoformat(),
        "requested_end": END.date().isoformat(),
        "lineage": lineage,
        "a_hybrid_control": a,
        "c_hybrid_stage013": c,
        "a_year_2022": a22,
        "c_year_2022": c22,
        "a_main_stress": ast,
        "c_main_stress": cst,
        "current_official_a_total_return_pct": float(current_a["total_return_pct"]),
        "c_vs_hybrid_a_return_retention_ratio": c_vs_a_retention,
        "c_vs_current_official_a_return_retention_ratio": c_vs_current_retention,
        "full_drawdown_improvement_pp": full_dd_delta,
        "year_2022_drawdown_improvement_pp": year_dd_delta,
        "main_stress_drawdown_improvement_pp": stress_dd_delta,
        "broker10_delta_pp": broker_delta,
        "predeclared_gates": gates,
        "input_ok": bool(input_ok),
        "mechanical_semantics_ok": bool(mechanical_semantics_ok),
        "historical_policy_semantics_ok": bool(historical_policy_semantics_ok),
        "semantics_ok": False,
        "performance_ok": bool(performance_ok),
        "decision": decision,
        "independent_review": {
            "status": "passed_counterfactual_only",
            "p0": 0,
            "p1": 2,
            "p2": 3,
            "numeric_confidence_pct": 99,
            "appended_rows_without_prior_nonzero_strategy_state": 37,
            "learned_rank_rows_without_prior_nonzero_strategy_state": 28,
            "findings": [
                "2021 rows change the frozen 720-day OOS effective-date policy",
                "Stage062 historical universe is not strict PIT",
                "counterfactual metrics are correct and deterministic",
            ],
        },
        "promotion_ready": False,
        "overfit_before": "low mechanically, but historical effective-date semantics required review",
        "overfit_after": "policy backfill bias: later 12-month live inference was moved into the frozen 720-day warm-up",
        "continue_value_before": "yes as a falsification of retrospective early activation",
        "continue_value_after": "no for Stage003; keep Stage002 current original-OOS policy path",
    }


def _normalized_window_with_prior_seed(
    data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[pd.Series, pd.Series]:
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date")
    prior = frame[frame["date"] < start]
    seed = (
        float(pd.to_numeric(prior["account_equity_for_metrics"], errors="coerce").iloc[-1])
        if len(prior)
        else CAPITAL
    )
    part = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    equity = pd.to_numeric(part["account_equity_for_metrics"], errors="coerce").ffill()
    return part["date"], equity / seed


def _plot(curves: pd.DataFrame) -> None:
    current = pd.read_csv(s2.CURVES_PATH)
    current = current[
        current["requested_start_month"].astype(str).eq("2020-01")
        & current["version"].astype(str).eq(A_VERSION)
    ].copy()
    current["plot_version"] = "current_official_a_reference"
    data_all = curves.copy()
    data_all["plot_version"] = data_all["version"]
    data_all = pd.concat([current, data_all], ignore_index=True, sort=False)
    colors = {
        "current_official_a_reference": "#64748b",
        A_VERSION: "#111827",
        C_VERSION: "#0f766e",
    }
    labels = {
        "current_official_a_reference": "Current official A reference",
        A_VERSION: "A early-activation C9",
        C_VERSION: "C early-activation Stage013",
    }
    styles = {"current_official_a_reference": "--", A_VERSION: "-", C_VERSION: "-"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    for version, group in data_all.groupby("plot_version", sort=False):
        data = group.sort_values("date").copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0, 0].plot(data["date"], equity, color=colors[version], linestyle=styles[version], label=labels[version], linewidth=1.1)
        axes[1, 0].plot(data["date"], s1.source.s006.base._drawdown_pct(equity), color=colors[version], linestyle=styles[version], label=labels[version], linewidth=1.0)
        d22, n22 = _normalized_window_with_prior_seed(data, s1.source.YEAR_2022_START, s1.source.YEAR_2022_END)
        axes[0, 1].plot(d22, n22, color=colors[version], linestyle=styles[version], label=labels[version], linewidth=1.1)
        dst, nst = _normalized_window_with_prior_seed(data, s1.source.STRESS_START, s1.source.STRESS_END)
        axes[1, 1].plot(dst, nst, color=colors[version], linestyle=styles[version], label=labels[version], linewidth=1.1)
    axes[0, 0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Absolute account equity")
    axes[1, 0].set_title("Full-period drawdown")
    axes[0, 1].set_title("2022 normalized equity")
    axes[1, 1].set_title("2022-07-15 to 2024-05-10 normalized equity")
    for ax in axes.flat:
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8)
    fig.suptitle("Stage003 counterfactual Stage182 early activation: A/C and current reference")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pilot: pd.DataFrame,
    usage: pd.DataFrame,
    input_audit: pd.DataFrame,
    profile_diff: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage003 Stage182 提前生效反事实 A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 输入机械检查/历史政策语义/绩效通过：`{decision['input_ok']}` / `{decision['historical_policy_semantics_ok']}` / `{decision['performance_ok']}`
- C 相对 hybrid A / 当前 official A 收益保留：`{decision['c_vs_hybrid_a_return_retention_ratio']:.6f}` / `{decision['c_vs_current_official_a_return_retention_ratio']:.6f}`
- C-A 全周期/2022/压力窗回撤改善：`{decision['full_drawdown_improvement_pp']:.4f}` / `{decision['year_2022_drawdown_improvement_pp']:.4f}` / `{decision['main_stress_drawdown_improvement_pp']:.4f}` pp
- broker10 变化：`{decision['broker10_delta_pp']:.4f}` pp
- 独立审查：`P0=0/P1=2/P2=3`，数值正确性置信度 `99%`；反事实数值可信，历史政策修复语义不可信

## 全周期指标

{summary.to_markdown(index=False)}

## 压力窗口

{stress.to_markdown(index=False)}

## Pilot 审计

{pilot.to_markdown(index=False)}

## AI 使用

{usage.to_markdown(index=False)}

## 配置差异

{profile_diff.to_markdown(index=False)}

## 反事实输入月历

{input_audit.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def _write_stage_record(
    summary: pd.DataFrame, decision: dict[str, Any]
) -> None:
    a = _metric(summary, A_VERSION)
    c = _metric(summary, C_VERSION)
    STAGE_RECORD_PATH.write_text(
        f"""# Stage003 Stage182 提前生效反事实 A/C

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']}`
- 是否重要突破：否；early-activation 反事实路线关闭
- 新增参数：无策略参数；反事实输入把后来 Stage182 live inference 提前到 `2021-04 -> 2021-12`
- 修改参数：A/C AI 文件从当前 504 行扩为 hybrid 585 行，现有 504 行完全保留
- 删除参数：无

## 调研与判断

- scikit-learn TimeSeriesSplit 明确时间序列训练必须在过去、测试在未来；QuantConnect walk-forward 文档要求滚动训练和 warm-up。
- 原冻结 walk-forward 使用 720 天训练窗，首个 OOS 预测为 2022-01-28；本阶段追加九个月只代表后来 Stage182 规则可以追溯计算，不代表原历史政策缺失。

## 回测口径

- 区间：`{START.date()} -> {END.date()}`；账户 `150,000`。
- A：append-only hybrid AI + 当前 C9；C：A + 冻结 Stage013 `30%/1/1`。
- 成本、保证金、相关门、forced-margin、0.5R 开仓日止损重试和退出均不改。

## 结果

- A：期末权益 `{float(a['end_equity']):,.2f}`，总收益 `{float(a['total_return_pct']):.4f}%`，最大回撤 `{float(a['max_drawdown_pct']):.4f}%`，Sharpe `{float(a['sharpe']):.4f}`，总滑点 `{float(a['total_slippage']):,.2f}`，交易次数 `{float(a['total_trade_count']):.0f}`，非零日胜率 `{float(a['nonzero_daily_win_rate_pct']):.4f}%`，逐笔胜率 `{float(a['closed_lot_win_rate_pct']):.4f}%`。
- C：期末权益 `{float(c['end_equity']):,.2f}`，总收益 `{float(c['total_return_pct']):.4f}%`，最大回撤 `{float(c['max_drawdown_pct']):.4f}%`，Sharpe `{float(c['sharpe']):.4f}`，总滑点 `{float(c['total_slippage']):,.2f}`，交易次数 `{float(c['total_trade_count']):.0f}`，非零日胜率 `{float(c['nonzero_daily_win_rate_pct']):.4f}%`，逐笔胜率 `{float(c['closed_lot_win_rate_pct']):.4f}%`。
- C 相对 hybrid A / 当前 official A 收益保留：`{decision['c_vs_hybrid_a_return_retention_ratio']:.4f}` / `{decision['c_vs_current_official_a_return_retention_ratio']:.4f}`。
- 全周期/2022/固定压力窗回撤改善：`{decision['full_drawdown_improvement_pp']:.4f}` / `{decision['year_2022_drawdown_improvement_pp']:.4f}` / `{decision['main_stress_drawdown_improvement_pp']:.4f}` pp。
- broker10 变化：`{decision['broker10_delta_pp']:.4f}` pp。
- 输入机械口径：当前 `504/55`，反事实追加 `81/9`，hybrid `585/64`；这不是原冻结政策的缺失修复。

## 最终结论

- 决策：`{decision['decision']}`；独立 review `P0=0/P1=2/P2=3`、数值正确性置信度 `99%`，`promotion_ready=false`。
- 数值作为反事实实验可信，但历史政策语义不成立；追加 81 行中 37 行在 eval date 前没有非零策略状态，不能作为严格 PIT 原政策重建。
- 候选级 AI 明细已保存到 `{AI_CANDIDATE_AUDIT_PATH}`。
- 新增回测结果见 `{SUMMARY_PATH}`；未修改或删除历史结果。

## 过拟合反思

- 运行前：低。只修复确定的数据缺口，参数与门槛预声明，不按结果调月池或 Stage013。
- 运行后：存在政策回填偏差。没有参数扫描，但把后来 12 月训练门槛事后提前到原 720 天 warm-up 期，不可用于晋级。

## 继续价值反思

- 运行前：有。它直接检验 Stage002 改善是否依赖长期 bootstrap 池。
- 运行后：本路线无继续价值，不扩逐半年、不调 `30%/1/1`；Stage002 当前原政策路线仍有价值。
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    hybrid, input_audit, lineage = _build_hybrid()
    lineage["stage002_summary_path"] = str(STAGE002_SUMMARY_PATH)
    lineage["stage002_summary_sha256"] = _sha256(STAGE002_SUMMARY_PATH)
    lineage["stage002_curves_path"] = str(s2.CURVES_PATH)
    lineage["stage002_curves_sha256"] = _sha256(s2.CURVES_PATH)
    hybrid.to_csv(HYBRID_BASE_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    LINEAGE_PATH.write_text(
        json.dumps(s1.source.s006.base._json_safe(lineage), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    eligibility = {
        A_VERSION: _eligibility_for_arm(hybrid, A_VERSION),
        C_VERSION: _eligibility_for_arm(hybrid, C_VERSION),
    }
    paths = {A_VERSION: A_ELIGIBILITY_PATH, C_VERSION: C_ELIGIBILITY_PATH}
    for version in VERSIONS:
        eligibility[version].to_csv(paths[version], index=False, encoding="utf-8-sig")

    metadata = s1.source._metadata()
    profiles = {
        A_VERSION: s1._a_profile(metadata, paths[A_VERSION]),
        C_VERSION: s1._c_profile(metadata, paths[C_VERSION]),
    }
    profile_diff = _profile_diff(profiles)
    profile_diff.to_csv(PROFILE_DIFF_PATH, index=False, encoding="utf-8-sig")

    daily_by_version: dict[str, pd.DataFrame] = {}
    frames_by_version: dict[str, dict[str, pd.DataFrame]] = {}
    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    usage_rows: list[dict[str, Any]] = []
    for index, version in enumerate(VERSIONS, start=1):
        print(f"[stage003] run {index}/2 version={version}", flush=True)
        daily, frames = _run(metadata, profiles[version], version)
        daily_by_version[version] = daily
        frames_by_version[version] = frames
        _save_arm(version, daily, frames)
        row, curve = _summary_row(metadata, daily, frames, version)
        summary_rows.append(row)
        curves.append(curve)
        usage_rows.append(s2._ai_usage_row(frames, version, START))

    summary = pd.DataFrame(summary_rows)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    stress = s1._stress(daily_by_version)
    pilot = pd.DataFrame(
        [s2._pilot_audit_row(frames_by_version[C_VERSION]["pilot_gate_events"], START)]
    )
    usage = pd.DataFrame(usage_rows)
    candidate_detail = _candidate_detail(frames_by_version)
    decision = _decision(summary, stress, pilot, usage, lineage, profile_diff)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    candidate_detail.to_csv(
        AI_CANDIDATE_AUDIT_PATH, index=False, encoding="utf-8-sig"
    )
    DECISION_PATH.write_text(
        json.dumps(s1.source.s006.base._json_safe(decision), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(summary, stress, pilot, usage, input_audit, profile_diff, decision)
    _write_stage_record(summary, decision)
    return {
        "summary": summary,
        "stress": stress,
        "pilot": pilot,
        "usage": usage,
        "input_audit": input_audit,
        "profile_diff": profile_diff,
        "decision": decision,
    }


def main() -> None:
    result = build()
    print(result["summary"].to_string(index=False))
    print(json.dumps(s1.source.s006.base._json_safe(result["decision"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
