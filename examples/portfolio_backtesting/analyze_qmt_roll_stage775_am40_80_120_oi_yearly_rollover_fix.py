from __future__ import annotations

import json

import analyze_qmt_roll_stage773_am40_80_120_oi_yearly as base


MODEL_TAG = "stage775_am40_80_120_oi_yearly_rollover_fix_v1"
OUTPUT_PREFIX = "qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix"


def _configure_outputs() -> None:
    output_dir = base.OUTPUT_DIR
    base.MODEL_TAG = MODEL_TAG
    base.OUTPUT_PREFIX = OUTPUT_PREFIX
    base.SUMMARY_PATH = output_dir / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    base.COST_PATH = output_dir / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    base.CURVES_PATH = output_dir / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    base.PROFILE_AGG_PATH = output_dir / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
    base.COMPARISON_PATH = output_dir / f"{OUTPUT_PREFIX}_comparison_vs_am120_{MODEL_TAG}.csv"
    base.PHASE_PATH = output_dir / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
    base.DECISION_PATH = output_dir / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    base.REPORT_PATH = output_dir / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    base.RETURN_HEATMAP_PATH = output_dir / f"{OUTPUT_PREFIX}_return_heatmaps_{MODEL_TAG}.png"
    base.DD_HEATMAP_PATH = output_dir / f"{OUTPUT_PREFIX}_dd_heatmaps_{MODEL_TAG}.png"
    base.COMPARISON_CHART_PATH = output_dir / f"{OUTPUT_PREFIX}_comparison_chart_{MODEL_TAG}.png"


def main() -> None:
    _configure_outputs()
    base.main()
    report_text = base.REPORT_PATH.read_text(encoding="utf-8")
    report_text = report_text.replace("# Stage773 AM40/80/120 × OI 年度启动验证", "# Stage775 AM40/80/120 × OI 年度启动验证")
    base.REPORT_PATH.write_text(report_text, encoding="utf-8")
    decision = json.loads(base.DECISION_PATH.read_text(encoding="utf-8"))
    decision["stage"] = "Stage775"
    base.DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
