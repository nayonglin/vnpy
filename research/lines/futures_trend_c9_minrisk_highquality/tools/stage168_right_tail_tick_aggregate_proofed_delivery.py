from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage168"
MODEL_TAG = "stage168_right_tail_tick_aggregate_proofed_delivery_v1"
OUTPUT_PREFIX = "qmt_roll_stage168_c9_minrisk_right_tail_tick_aggregate_proofed_delivery"
SELECTION_POLICY = "missing_stage153_ready_then_manifest_coverage_gap_right_tail_bottom_loss_maxdd_request_id_not_trade_rule"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage168_right_tail_tick_aggregate_proofed_delivery"


def _load_stage166_base():
    path = TOOLS_DIR / "stage166_gap_balanced_tick_aggregate_proofed_delivery.py"
    spec = importlib.util.spec_from_file_location("stage166_base_for_stage168", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage166 base from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_stage166_base()


def _set_stage168_globals() -> None:
    BASE.STAGE = STAGE
    BASE.MODEL_TAG = MODEL_TAG
    BASE.OUTPUT_PREFIX = OUTPUT_PREFIX
    BASE.SELECTION_POLICY = SELECTION_POLICY
    BASE.OUTPUT_DIR = OUTPUT_DIR
    BASE.REPORT_TITLE = "Stage168 Right-Tail Tick Aggregate Proofed Delivery"
    BASE.SCOPE_NOTE = "deterministic Stage152 right-tail coverage-gap batch expansion."
    BASE.SELECTION_NOTE = "right-tail/bottom-loss/maxDD classes are manifest coverage obligations, not trade filters."
    BASE.PATH_CHART_TITLE = "Official Path Unchanged; Stage168 Right-Tail Delivery"
    BASE.SELECTION_CHART_TITLE = "Stage168 Manifest Right-Tail Coverage Selection"
    BASE.DELIVERY_CHART_TITLE = "Stage168 Delivery Matrix"
    BASE.WINDOW_CHART_TITLE = "Stage168 Window Precheck"
    BASE.GATE_CHART_TITLE = "Stage168 Gate Status Matrix"
    BASE.DECISION_WRITTEN = "stage168_right_tail_tick_aggregate_delivery_written_run_stage160_153_no_rule"
    BASE.DECISION_NONE_WRITTEN = "stage168_right_tail_tick_aggregate_delivery_none_written_no_rule"

    BASE.MAX_REQUESTS = int(os.getenv("STAGE168_MAX_REQUESTS", "8"))
    BASE.WRITE_INCOMING = os.getenv("STAGE168_WRITE_INCOMING", "1").strip() != "0"
    BASE.OVERWRITE_EXISTING = os.getenv("STAGE168_OVERWRITE_EXISTING", "0").strip() == "1"
    BASE.MAX_SECONDS_TICK = int(os.getenv("STAGE168_MAX_SECONDS_TICK", "90"))
    BASE.TICK_DATA_LENGTH = int(os.getenv("STAGE168_TICK_DATA_LENGTH", "120000"))
    BASE.MIN_NORMALIZED_ROWS = int(os.getenv("STAGE168_MIN_NORMALIZED_ROWS", "10"))

    BASE.SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    BASE.SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
    BASE.REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
    BASE.DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
    BASE.WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
    BASE.GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
    BASE.REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    BASE.DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    BASE.PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_right_tail_status_{MODEL_TAG}.png"
    BASE.SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_right_tail_priority_{MODEL_TAG}.png"
    BASE.DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
    BASE.WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_matrix_{MODEL_TAG}.png"
    BASE.GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


def _select_batch(manifest: pd.DataFrame, ready_ids: set[str]) -> pd.DataFrame:
    data = manifest[~manifest["request_id"].astype(str).isin(ready_ids)].copy()
    numeric_columns = [
        "priority_score",
        "right_tail_window_count",
        "bottom_loss_window_count",
        "maxdd_window_count",
        "low_resolution_window_count",
        "required_window_count",
        "estimated_required_1m_bars",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
    data["manifest_coverage_gap_score"] = (
        data["right_tail_window_count"] * 100
        + data["bottom_loss_window_count"] * 40
        + data["maxdd_window_count"] * 20
        + data["low_resolution_window_count"] * 5
        + data["priority_score"]
    )
    selected = data.sort_values(
        [
            "right_tail_window_count",
            "bottom_loss_window_count",
            "maxdd_window_count",
            "low_resolution_window_count",
            "priority_score",
            "request_id",
        ],
        ascending=[False, False, False, False, False, True],
    ).head(BASE.MAX_REQUESTS)
    selected = selected.reset_index(drop=True)
    selected["batch_rank"] = np.arange(1, len(selected) + 1)
    selected["selection_policy"] = SELECTION_POLICY
    return selected


def main() -> None:
    _set_stage168_globals()
    BASE._select_batch = _select_batch
    BASE.main()


if __name__ == "__main__":
    main()
