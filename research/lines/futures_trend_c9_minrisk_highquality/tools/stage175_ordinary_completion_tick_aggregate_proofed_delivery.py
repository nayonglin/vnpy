from __future__ import annotations

import importlib.util
import os
from pathlib import Path


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage175"
MODEL_TAG = "stage175_ordinary_completion_tick_aggregate_proofed_delivery_v1"
OUTPUT_PREFIX = "qmt_roll_stage175_c9_minrisk_ordinary_completion_tick_aggregate_proofed_delivery"
SELECTION_POLICY = "missing_stage153_ready_then_complete_remaining_ordinary_not_trade_rule"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage175_ordinary_completion_tick_aggregate_proofed_delivery"


def _load_stage172_base():
    path = TOOLS_DIR / "stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery.py"
    spec = importlib.util.spec_from_file_location("stage172_base_for_stage175", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage172 base from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE172 = _load_stage172_base()
BASE = BASE172.BASE


def _set_stage175_globals() -> None:
    BASE172.STAGE = STAGE
    BASE172.MODEL_TAG = MODEL_TAG
    BASE172.OUTPUT_PREFIX = OUTPUT_PREFIX
    BASE172.SELECTION_POLICY = SELECTION_POLICY
    BASE172.OUTPUT_DIR = OUTPUT_DIR

    BASE.STAGE = STAGE
    BASE.MODEL_TAG = MODEL_TAG
    BASE.OUTPUT_PREFIX = OUTPUT_PREFIX
    BASE.SELECTION_POLICY = SELECTION_POLICY
    BASE.OUTPUT_DIR = OUTPUT_DIR
    BASE.REPORT_TITLE = "Stage175 Ordinary Completion Tick Aggregate Proofed Delivery"
    BASE.SCOPE_NOTE = "deterministic Stage152 ordinary-window completion batch."
    BASE.SELECTION_NOTE = "ordinary windows are a manifest coverage obligation, not a trade filter."
    BASE.PATH_CHART_TITLE = "Official Path Unchanged; Stage175 Ordinary Completion Delivery"
    BASE.SELECTION_CHART_TITLE = "Stage175 Ordinary Completion Coverage Selection"
    BASE.DELIVERY_CHART_TITLE = "Stage175 Delivery Matrix"
    BASE.WINDOW_CHART_TITLE = "Stage175 Window Precheck"
    BASE.GATE_CHART_TITLE = "Stage175 Gate Status Matrix"
    BASE.DECISION_WRITTEN = "stage175_ordinary_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule"
    BASE.DECISION_NONE_WRITTEN = "stage175_ordinary_completion_tick_aggregate_delivery_none_written_no_rule"

    BASE.MAX_REQUESTS = int(os.getenv("STAGE175_MAX_REQUESTS", "128"))
    BASE.WRITE_INCOMING = os.getenv("STAGE175_WRITE_INCOMING", "1").strip() != "0"
    BASE.OVERWRITE_EXISTING = os.getenv("STAGE175_OVERWRITE_EXISTING", "0").strip() == "1"
    BASE.MAX_SECONDS_TICK = int(os.getenv("STAGE175_MAX_SECONDS_TICK", "90"))
    BASE.TICK_DATA_LENGTH = int(os.getenv("STAGE175_TICK_DATA_LENGTH", "120000"))
    BASE.MIN_NORMALIZED_ROWS = int(os.getenv("STAGE175_MIN_NORMALIZED_ROWS", "10"))

    BASE.SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    BASE.SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
    BASE.REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
    BASE.DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
    BASE.WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
    BASE.GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
    BASE.REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    BASE.DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    BASE.PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_ordinary_completion_status_{MODEL_TAG}.png"
    BASE.SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_ordinary_completion_priority_{MODEL_TAG}.png"
    BASE.DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
    BASE.WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_matrix_{MODEL_TAG}.png"
    BASE.GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


def main() -> None:
    _set_stage175_globals()
    BASE._select_batch = BASE172._select_batch
    BASE.main()


if __name__ == "__main__":
    main()
