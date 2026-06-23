from __future__ import annotations

import importlib.util
import os
from pathlib import Path


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage191"
MODEL_TAG = "stage191_predecision_lookback_tick_aggregate_delivery_batch_v1"
OUTPUT_PREFIX = "qmt_roll_stage191_c9_minrisk_predecision_lookback_tick_aggregate_delivery_batch"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE178_PATH = LINE_DIR / "tools" / "stage178_predecision_lookback_tick_aggregate_delivery_batch.py"


def _load_stage178_module():
    spec = importlib.util.spec_from_file_location("stage178_base_for_stage191", STAGE178_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage178 base from {STAGE178_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure(module) -> None:
    output_dir = LINE_DIR / "outputs" / "stage191_predecision_lookback_tick_aggregate_delivery_batch"
    module.STAGE = STAGE
    module.MODEL_TAG = MODEL_TAG
    module.OUTPUT_PREFIX = OUTPUT_PREFIX
    module.SELECTION_POLICY = "stage177_remaining_highest_priority_exchange_round_robin_stage191_no_pnl_no_rule"
    module.REPORT_TITLE = "Stage191 Predecision Lookback Tick Aggregate Delivery Batch"
    module.SCOPE_NOTE = "Stage177 predecision lookback raw/normalized/proof delivery expansion batch."
    module.SELECTION_NOTE = "priority classes are Stage177 coverage obligations only, not trade filters; Stage191 continues from existing triplets."
    module.SUCCESS_DECISION = "stage191_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule"
    module.FAIL_DECISION = "stage191_predecision_lookback_tick_aggregate_delivery_none_written_need_source_route_repair_no_rule"
    module.SUCCESS_NEXT_ACTION = "refresh_stage179_180_181_for_all_delivered_predecision_requests"
    module.FAIL_NEXT_ACTION = "repair_stage191_source_or_reduce_batch_before_validator_refresh"
    module.OUTPUT_DIR = output_dir
    module.SUMMARY_OUT = output_dir / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    module.SELECTED_OUT = output_dir / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
    module.REQUEST_STATUS_OUT = output_dir / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
    module.DELIVERY_AUDIT_OUT = output_dir / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
    module.WINDOW_PRECHECK_OUT = output_dir / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
    module.GATE_OUT = output_dir / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
    module.REPORT_OUT = output_dir / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    module.DECISION_OUT = output_dir / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    module.PATH_CHART_OUT = output_dir / f"{OUTPUT_PREFIX}_official_path_delivery_status_{MODEL_TAG}.png"
    module.SELECTION_CHART_OUT = output_dir / f"{OUTPUT_PREFIX}_selected_exchange_priority_{MODEL_TAG}.png"
    module.DELIVERY_CHART_OUT = output_dir / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
    module.WINDOW_CHART_OUT = output_dir / f"{OUTPUT_PREFIX}_predecision_window_precheck_{MODEL_TAG}.png"
    module.GATE_CHART_OUT = output_dir / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"
    module.MAX_REQUESTS = int(os.getenv("STAGE191_MAX_REQUESTS", "4"))
    module.WRITE_INCOMING = os.getenv("STAGE191_WRITE_INCOMING", "1").strip() != "0"
    module.OVERWRITE_EXISTING = os.getenv("STAGE191_OVERWRITE_EXISTING", "0").strip() == "1"
    module.MAX_SECONDS_TICK = int(os.getenv("STAGE191_MAX_SECONDS_TICK", "240"))
    module.TICK_DATA_LENGTH = int(os.getenv("STAGE191_TICK_DATA_LENGTH", "10000"))
    module.MIN_NORMALIZED_ROWS = int(os.getenv("STAGE191_MIN_NORMALIZED_ROWS", "61"))
    module.MIN_POSITIVE_VOLUME_BARS = int(os.getenv("STAGE191_MIN_POSITIVE_VOLUME_BARS", "60"))


def main() -> None:
    module = _load_stage178_module()
    _configure(module)
    module.main()


if __name__ == "__main__":
    main()
