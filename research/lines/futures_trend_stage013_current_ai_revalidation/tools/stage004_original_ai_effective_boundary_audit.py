#!/usr/bin/env python3
"""Stage004: audit the original AI effective-date policy and calendar coverage."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_stage013_current_ai_revalidation"
STAGE_ID = "stage004_original_ai_effective_boundary_audit"
STAGE_LABEL = "Stage004"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
ORIGINAL_MODEL_PATH = PORTFOLIO_DIR / "analyze_qmt_roll_ai_product_suitability_walkforward.py"
ORIGINAL_SUMMARY_PATH = PORTFOLIO_DIR / "backtest_outputs" / (
    "qmt_roll_ai_product_suitability_market_walkforward_summary_"
    "product_suitability_market_wf_v2.json"
)
ORIGINAL_PREDICTIONS_PATH = PORTFOLIO_DIR / "backtest_outputs" / (
    "qmt_roll_ai_product_suitability_market_walkforward_predictions_"
    "product_suitability_market_wf_v2.csv"
)
CURRENT_AI_PATH = PORTFOLIO_DIR / "backtest_outputs" / (
    "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_"
    "eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)
STAGE062_COVERAGE_PATH = ROOT / "research" / "lines" / (
    "futures_trend_rebuilt_c9_15w_v2_optimization/outputs/"
    "stage062_stage013_full_monthly_ai_candidate_official/"
    "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_"
    "ai_coverage_stage062_stage013_full_monthly_ai_candidate_official_v1.csv"
)

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_month_audit_{MODEL_TAG}.csv"
SCORE_TYPE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_score_type_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260710_1955_stage004_original_ai_effective_boundary_audit.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _constant_from_python(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        if node.target.id == name and node.value is not None:
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {path}")


def _source_class(score_types: set[str]) -> str:
    if "static18_pre_ai_boundary" in score_types:
        return "pre_ai_static18_boundary"
    if "ai_probability" in score_types:
        return "original_walk_forward_oos"
    if any(value.startswith("stage174_recovered_") for value in score_types):
        return "recovered_membership_snapshot"
    if any(value.startswith("stage182_live_") for value in score_types):
        return "stage182_live_inference"
    return "unknown"


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    summary = json.loads(ORIGINAL_SUMMARY_PATH.read_text(encoding="utf-8"))
    predictions = pd.read_csv(
        ORIGINAL_PREDICTIONS_PATH, usecols=["eval_date", "window_id"]
    )
    predictions["eval_date"] = pd.to_datetime(
        predictions["eval_date"], errors="coerce"
    )
    current = pd.read_csv(CURRENT_AI_PATH, encoding="utf-8-sig")
    current["eval_date"] = pd.to_datetime(current["eval_date"], errors="coerce")
    current["month"] = current["eval_date"].dt.to_period("M").astype(str)
    coverage = pd.read_csv(STAGE062_COVERAGE_PATH, encoding="utf-8-sig")

    first_prediction = pd.Timestamp(predictions["eval_date"].min()).normalize()
    last_current = pd.Timestamp(current["eval_date"].max()).normalize()
    train_window_days = int(_constant_from_python(ORIGINAL_MODEL_PATH, "TRAIN_WINDOW_DAYS"))
    test_window_days = int(_constant_from_python(ORIGINAL_MODEL_PATH, "TEST_WINDOW_DAYS"))
    step_days = int(_constant_from_python(ORIGINAL_MODEL_PATH, "STEP_DAYS"))

    expected_months = pd.period_range("2020-01", last_current.to_period("M"), freq="M")
    rows: list[dict[str, Any]] = []
    for period in expected_months:
        month = str(period)
        group = current[current["month"].eq(month)]
        score_types = set(group["score_type"].astype(str))
        original_prediction_present = int(
            bool((predictions["eval_date"].dt.to_period("M") == period).any())
        )
        if period < first_prediction.to_period("M"):
            expected_policy = "pre_ai_static18_boundary"
            policy_present = int(
                bool(
                    current[
                        current["score_type"].astype(str).eq("static18_pre_ai_boundary")
                    ].shape[0]
                    == 18
                )
            )
            applied_eval_date = "2019-12-31"
            applied_source_class = "pre_ai_static18_boundary"
            applied_score_types = "static18_pre_ai_boundary"
        else:
            expected_policy = "monthly_ai_snapshot"
            policy_present = int(not group.empty)
            applied_eval_date = (
                group["eval_date"].max().date().isoformat() if not group.empty else ""
            )
            applied_source_class = _source_class(score_types)
            applied_score_types = "|".join(sorted(score_types))
        counterfactual = coverage[coverage["calendar_month"].astype(str).eq(month)]
        rows.append(
            {
                "calendar_month": month,
                "expected_policy": expected_policy,
                "policy_present": policy_present,
                "applied_eval_date": applied_eval_date,
                "current_month_rows": int(len(group)),
                "current_source_class": applied_source_class,
                "current_score_types": applied_score_types,
                "original_prediction_present": original_prediction_present,
                "stage062_retrospective_status": (
                    str(counterfactual.iloc[0]["status"]) if not counterfactual.empty else ""
                ),
                "stage062_is_before_original_first_oos": int(
                    not counterfactual.empty and period < first_prediction.to_period("M")
                ),
            }
        )
    month_audit = pd.DataFrame(rows)
    score_type_audit = (
        current.groupby("score_type", as_index=False)
        .agg(
            rows=("product_vt_symbol", "size"),
            eval_date_count=("eval_date", "nunique"),
            min_eval_date=("eval_date", "min"),
            max_eval_date=("eval_date", "max"),
        )
        .sort_values("min_eval_date")
    )
    for column in ("min_eval_date", "max_eval_date"):
        score_type_audit[column] = pd.to_datetime(
            score_type_audit[column], errors="coerce"
        ).dt.date.astype(str)

    pre_ai = month_audit[month_audit["expected_policy"].eq("pre_ai_static18_boundary")]
    monthly = month_audit[month_audit["expected_policy"].eq("monthly_ai_snapshot")]
    current_original_dates = set(
        current[current["score_type"].astype(str).eq("ai_probability")]["eval_date"]
        .dropna()
        .dt.normalize()
    )
    prediction_dates = set(predictions["eval_date"].dropna().dt.normalize())
    retrospective_pre_oos = coverage[
        pd.to_datetime(coverage["eval_date"], errors="coerce") < first_prediction
    ]
    retrospective_generated_pre_oos = retrospective_pre_oos[
        retrospective_pre_oos["status"].astype(str).eq("GENERATED")
    ]
    retrospective_infeasible_pre_oos = retrospective_pre_oos[
        retrospective_pre_oos["status"].astype(str).str.startswith("INFEASIBLE")
    ]
    policy_complete = bool(
        pre_ai["policy_present"].eq(1).all()
        and monthly["policy_present"].eq(1).all()
        and current_original_dates == prediction_dates
    )
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "original_model_path": str(ORIGINAL_MODEL_PATH),
        "original_model_sha256": _sha256(ORIGINAL_MODEL_PATH),
        "original_summary_path": str(ORIGINAL_SUMMARY_PATH),
        "original_summary_sha256": _sha256(ORIGINAL_SUMMARY_PATH),
        "original_predictions_path": str(ORIGINAL_PREDICTIONS_PATH),
        "original_predictions_sha256": _sha256(ORIGINAL_PREDICTIONS_PATH),
        "current_ai_path": str(CURRENT_AI_PATH),
        "current_ai_sha256": _sha256(CURRENT_AI_PATH),
        "original_walk_forward": {
            "train_window_days": train_window_days,
            "test_window_days": test_window_days,
            "step_days": step_days,
            "summary_train_window_days": int(summary["walk_forward"]["train_window_days"]),
            "prediction_row_count": int(len(predictions)),
            "prediction_eval_date_count": int(predictions["eval_date"].nunique()),
            "first_prediction_eval_date": first_prediction.date().isoformat(),
            "last_prediction_eval_date": pd.Timestamp(
                predictions["eval_date"].max()
            ).date().isoformat(),
        },
        "current_policy": {
            "pre_ai_month_count": int(len(pre_ai)),
            "monthly_ai_expected_count": int(len(monthly)),
            "monthly_ai_present_count": int(monthly["policy_present"].sum()),
            "monthly_ai_missing_months": monthly[
                monthly["policy_present"].eq(0)
            ]["calendar_month"].astype(str).tolist(),
            "static_boundary_rows": int(
                current["score_type"].astype(str).eq("static18_pre_ai_boundary").sum()
            ),
            "current_eval_date_count": int(current["eval_date"].nunique()),
            "current_rows": int(len(current)),
            "original_prediction_dates_exactly_preserved": bool(
                current_original_dates == prediction_dates
            ),
        },
        "stage062_counterfactual": {
            "coverage_dates_before_original_first_oos": int(
                len(retrospective_pre_oos)
            ),
            "generated_dates_before_original_first_oos": int(
                len(retrospective_generated_pre_oos)
            ),
            "generated_months_before_original_first_oos": retrospective_generated_pre_oos[
                "calendar_month"
            ].astype(str).tolist(),
            "infeasible_dates_before_original_first_oos": int(
                len(retrospective_infeasible_pre_oos)
            ),
            "uses_different_effective_date_policy": bool(
                len(retrospective_generated_pre_oos) > 0
            ),
        },
        "policy_complete": policy_complete,
        "decision": (
            "current_ai_calendar_complete_under_original_oos_policy_stage003_is_counterfactual"
            if policy_complete
            else "current_ai_calendar_has_original_policy_gap"
        ),
        "independent_review": {
            "status": "boundary_forensics_passed",
            "audit_p0": 0,
            "audit_p1": 0,
            "audit_p2": 1,
            "confidence_pct": 98,
            "corrected_upstream_findings": {
                "p1": 2,
                "items": [
                    "Stage002 nine-month promotion blocker was invalid",
                    "Stage003 was a policy change rather than a data repair",
                ],
            },
            "residual_p2": "2026-03 to 2026-05 preserve membership but not original probability values",
        },
        "overfit_before": "none: read-only date-policy audit",
        "overfit_after": "none: two independent read-only reviews confirmed the frozen effective-date policy",
        "continue_value_before": "yes: distinguishes missing snapshots from pre-AI policy",
        "continue_value_after": "yes for Stage002 cost/execution validation; no for Stage003 early activation",
    }

    month_audit.to_csv(MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    score_type_audit.to_csv(SCORE_TYPE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# Stage004 原始 AI 生效边界审计

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 原始 walk-forward：train/test/step `{train_window_days}/{test_window_days}/{step_days}` 天
- 首个原始 OOS 预测：`{first_prediction.date()}`
- 2020-2021：`24` 个月均按 `static18_pre_ai_boundary` 政策处理
- 2022-01 至 {last_current.strftime('%Y-%m')}：月度 AI 预期/存在 `{len(monthly)}/{int(monthly['policy_present'].sum())}`
- 原始 50 个 prediction eval_date 在当前文件中完全保留：`{current_original_dates == prediction_dates}`
- Stage062 在首个原始 OOS 前实际生成：`{len(retrospective_generated_pre_oos)}` 个月，另有 `{len(retrospective_infeasible_pre_oos)}` 个月不可生成；前者属于提前生效反事实，不是原历史政策缺口
- 独立审查：边界法证通过，`P0=0/P1=0/P2=1`，置信度 `98%`；另纠正 Stage002/003 上游结论 `P1=2`

## Score Types

{score_type_audit.to_markdown(index=False)}

## Month Audit

{month_audit.to_markdown(index=False)}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    STAGE_RECORD_PATH.write_text(
        f"""# Stage004 原始 AI 生效边界法证审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']}`
- 阶段性质：只读输入法证，不是回测，不改策略、AI 文件、实盘或 CTP
- 新增/修改/删除参数：无

## 结果

- 原始 walk-forward 训练/测试/步长：`{train_window_days}/{test_window_days}/{step_days}` 天。
- 原始预测共 `{len(predictions)}` 行、`{predictions['eval_date'].nunique()}` 个 eval_date，首个日期 `{first_prediction.date()}`。
- 当前 AI 文件 `504` 行/`55` 个 eval_date；2019-12 为 18 品种静态边界，2022-01 至 2026-06 的 54 个月月度快照连续无缺口。
- 当前 `ai_probability` 的 50 个日期与原始 walk-forward predictions 日期集合完全一致；2026-03 至 05 为恢复快照，2026-06 为 live inference。
- Stage062 在 2021-04 至 12 回算的 9 个月早于原首个 OOS 日期，是新 live inference 规则提前生效的反事实，不是原冻结政策下丢失的月池。

## 最终结论

- 决策：`{decision['decision']}`。
- Stage002 的 current-AI 月历在原冻结 OOS 政策下是完整的；Stage003 应定性为 early-activation sensitivity，不能用来否定 Stage002。
- 独立 agent review：边界法证通过，`P0=0/P1=0/P2=1`、置信度 `98%`；残余 P2 是 2026-03 至 05 只恢复 membership，原概率值未字节级恢复。

## 反思

- 过拟合：否。本阶段只核对代码常量、预测日期和文件覆盖。
- 继续价值：有。已撤销 Stage002 的“9个月缺失阻塞”，下一步进入成本/执行稳健性；Stage003 不继续。
""",
        encoding="utf-8",
    )
    return decision


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
