from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage786_current_ai_oos_2018_2019 as s786


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage787_stage777_source_ai_oos_2018_2019_v1"
OUTPUT_PREFIX = "qmt_roll_stage787_stage777_source_ai_oos_2018_2019"
LINE_ID = "futures_trend_2019_data_extension"

SOURCE_PREFIX = "qmt_roll_stage786_probe_stage777_family_source_2015_2019"

AI_ON_VARIANT = "stage787_stage777_source_ai_pit_2018_2019"
AI_OFF_VARIANT = "stage787_stage777_source_ai_off_2018_2019"
AI_ON_PROFILE = "stage787_stage777_source_ai_pit"
AI_OFF_PROFILE = "stage787_stage777_source_ai_off"

SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.json"
PRODUCT_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_{MODEL_TAG}.csv"
MARKET_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
FEATURED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_featured_daily_{MODEL_TAG}.csv"
SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
AI_POOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pit_ai_pool_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_training_audit_{MODEL_TAG}.csv"
SELECTED_PRODUCTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_products_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _configure_stage786_helpers() -> None:
    s786.MODEL_TAG = MODEL_TAG
    s786.OUTPUT_PREFIX = OUTPUT_PREFIX
    s786.SOURCE_PREFIX = SOURCE_PREFIX
    s786.AI_ON_VARIANT = AI_ON_VARIANT
    s786.AI_OFF_VARIANT = AI_OFF_VARIANT
    s786.AI_ON_PROFILE = AI_ON_PROFILE
    s786.AI_OFF_PROFILE = AI_OFF_PROFILE
    s786.SOURCE_SUMMARY_PATH = SOURCE_SUMMARY_PATH
    s786.PRODUCT_DAILY_PATH = PRODUCT_DAILY_PATH
    s786.MARKET_DAILY_PATH = MARKET_DAILY_PATH
    s786.FEATURED_DAILY_PATH = FEATURED_DAILY_PATH
    s786.SAMPLES_PATH = SAMPLES_PATH
    s786.AI_POOL_PATH = AI_POOL_PATH
    s786.ELIGIBILITY_PATH = ELIGIBILITY_PATH
    s786.AI_AUDIT_PATH = AI_AUDIT_PATH
    s786.SELECTED_PRODUCTS_PATH = SELECTED_PRODUCTS_PATH
    s786.SUMMARY_PATH = SUMMARY_PATH
    s786.COST_PATH = COST_PATH
    s786.CURVES_PATH = CURVES_PATH
    s786.COMPARISON_PATH = COMPARISON_PATH
    s786.DECISION_PATH = DECISION_PATH
    s786.REPORT_PATH = REPORT_PATH
    s786.CHART_PATH = CHART_PATH


def _source_summary(source_paths: dict[str, Path]) -> dict[str, Any]:
    position_min, position_max, position_rows = s786._csv_date_range(source_paths["position_changes"], ("date", "datetime"))
    candidate_min, candidate_max, candidate_rows = s786._csv_date_range(source_paths["entry_candidate_snapshots"], ("datetime", "date"))
    stats_path = source_paths["statistics"]
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
    summary = {
        "source_prefix": SOURCE_PREFIX,
        "source_kind": "Stage777-family no-AI target-strategy attribution source",
        "position_min_date": position_min,
        "position_max_date": position_max,
        "position_rows": position_rows,
        "candidate_min_date": candidate_min,
        "candidate_max_date": candidate_max,
        "candidate_rows": candidate_rows,
        "statistics": stats,
        "outputs": {key: str(path) for key, path in source_paths.items()},
    }
    SOURCE_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _decision(source_summary: dict[str, Any], pool: pd.DataFrame, eligibility: pd.DataFrame, audit: pd.DataFrame, summary: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    comp = comparison.iloc[0].to_dict()
    scored = audit[audit["status"].astype(str).eq("scored")].copy()
    return {
        "stage": "Stage787",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "research_boundary": (
            "This is not the frozen official AI pool. It keeps the current AI model form but rebuilds labels from "
            "a Stage777-family no-AI source so 2018-2019 can be tested point-in-time."
        ),
        "source_summary": source_summary,
        "ai_coverage": {
            "scored_eval_months": int(scored["eval_date"].nunique()),
            "first_scored_eval_date": str(scored["eval_date"].min()) if not scored.empty else "",
            "last_scored_eval_date": str(scored["eval_date"].max()) if not scored.empty else "",
            "pool_rows": int(len(pool)),
            "eligibility_rows": int(len(eligibility)),
            "selected_products_unique": sorted(eligibility["product_vt_symbol"].astype(str).unique().tolist()),
        },
        "summary": {
            "ai_on": _json_safe(summary[summary["ai_product_pool_enabled"].eq(1)].iloc[0].to_dict()),
            "ai_off": _json_safe(summary[summary["ai_product_pool_enabled"].eq(0)].iloc[0].to_dict()),
            "comparison": _json_safe(comp),
        },
        "judgement": {
            "overfit_risk": "medium",
            "why": (
                "The model form and top8 rule are unchanged and 2018-2019 is not used for tuning, but the label source "
                "has been changed from the frozen official AI source to the target strategy family."
            ),
            "continue_value": "High as a method feasibility test; low as direct proof that the current official AI pool worked in 2018-2019.",
        },
        "outputs": {
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "ai_pool": str(AI_POOL_PATH),
            "eligibility": str(ELIGIBILITY_PATH),
            "ai_training_audit": str(AI_AUDIT_PATH),
            "selected_products": str(SELECTED_PRODUCTS_PATH),
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _build_report(decision: dict[str, Any], selected: pd.DataFrame, summary: pd.DataFrame, comparison: pd.DataFrame, audit: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage787 Stage777标签源 + 当前AI方法 2018-2019 时点外验证",
            "",
            "## 边界",
            "",
            "- 这不是当前正式AI池的历史证明；Stage786已经证明正式AI源在18-19之前标签不足。",
            "- 这次只验证：同样的AI模型形态，如果标签源换成Stage777同族无AI策略，能否在2018-2019形成有效过滤。",
            "",
            "## 月度选品",
            "",
            _md_table(selected, max_rows=40),
            "",
            "## 回测摘要",
            "",
            _md_table(
                summary[
                    [
                        "variant",
                        "ai_product_pool_enabled",
                        "end_equity",
                        "rebased_total_return_pct",
                        "rebased_max_dd_pct",
                        "rebased_sharpe",
                        "total_trade_count",
                        "total_slippage",
                    ]
                ],
                max_rows=10,
            ),
            "",
            "## A/B差值",
            "",
            _md_table(comparison, max_rows=5),
            "",
            "## 训练覆盖",
            "",
            _md_table(audit[["eval_date", "train_start", "training_label_cutoff", "train_rows", "train_months", "status", "skip_reason"]], max_rows=40),
            "",
            "## 图",
            "",
            f"![Stage787 equity curve]({CHART_PATH})",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _configure_stage786_helpers()
    source_paths = s786._artifact_paths(SOURCE_PREFIX)
    missing = [str(path) for path in source_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Stage777-family source artifacts: {missing}")
    source_summary = _source_summary(source_paths)
    pool, eligibility, audit = s786.build_point_in_time_ai_pool(source_paths)
    summary, cost, curves = s786._run_backtest_ab()
    comparison = s786._comparison(summary)
    selected = pd.read_csv(SELECTED_PRODUCTS_PATH)
    decision = _decision(source_summary, pool, eligibility, audit, summary, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    s786._plot(curves)
    REPORT_PATH.write_text(_build_report(decision, selected, summary, comparison, audit), encoding="utf-8")

    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))
    print(f"chart: {CHART_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
