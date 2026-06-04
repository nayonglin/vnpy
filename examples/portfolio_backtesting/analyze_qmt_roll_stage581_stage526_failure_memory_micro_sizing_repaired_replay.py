from __future__ import annotations

from pathlib import Path

import analyze_qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay as s577


MODEL_TAG = "stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay"
OUTPUT_DIR = s577.OUTPUT_DIR


def _retarget_outputs() -> None:
    s577.MODEL_TAG = MODEL_TAG
    s577.OUTPUT_PREFIX = OUTPUT_PREFIX
    for name, suffix in {
        "SUMMARY_PATH": "summary",
        "COST_PATH": "cost_stress",
        "ROLLING_PATH": "rolling_holding",
        "WINDOW_PATH": "window_metrics",
        "MARGIN_DAILY_PATH": "margin_daily",
        "POSITIONS_PATH": "positions",
        "SNAPSHOT_PATH": "entry_candidate_snapshots",
        "MICRO_EVENTS_PATH": "micro_sizing_events",
        "PRODUCT_SUMMARY_PATH": "product_trigger_summary",
        "GATES_PATH": "gates",
        "DECISION_PATH": "decision",
        "REPORT_PATH": "report",
        "CHART_PATH": "chart",
    }.items():
        extension = ".json" if suffix == "decision" else ".png" if suffix == "chart" else ".md" if suffix == "report" else ".csv"
        setattr(s577, name, Path(OUTPUT_DIR) / f"{OUTPUT_PREFIX}_{suffix}_{MODEL_TAG}{extension}")


def main() -> None:
    _retarget_outputs()
    s577.main()
    report_path = s577.REPORT_PATH
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8")
        text = text.replace(
            "# Stage577 Stage526 failure-memory micro-sizing真实引擎回放",
            "# Stage581 Stage526 failure-memory micro-sizing修复后真实引擎回放",
            1,
        )
        report_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
