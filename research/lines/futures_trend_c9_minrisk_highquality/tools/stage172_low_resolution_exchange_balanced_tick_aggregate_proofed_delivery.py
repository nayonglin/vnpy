from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage172"
MODEL_TAG = "stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery_v1"
OUTPUT_PREFIX = "qmt_roll_stage172_c9_minrisk_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery"
SELECTION_POLICY = "missing_stage153_ready_then_low_resolution_exchange_round_robin_not_trade_rule"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage172_low_resolution_exchange_balanced_tick_aggregate_proofed_delivery"


def _load_stage166_base():
    path = TOOLS_DIR / "stage166_gap_balanced_tick_aggregate_proofed_delivery.py"
    spec = importlib.util.spec_from_file_location("stage166_base_for_stage172", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage166 base from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_stage166_base()


def _set_stage172_globals() -> None:
    BASE.STAGE = STAGE
    BASE.MODEL_TAG = MODEL_TAG
    BASE.OUTPUT_PREFIX = OUTPUT_PREFIX
    BASE.SELECTION_POLICY = SELECTION_POLICY
    BASE.OUTPUT_DIR = OUTPUT_DIR
    BASE.REPORT_TITLE = "Stage172 Low-Resolution Exchange-Balanced Tick Aggregate Proofed Delivery"
    BASE.SCOPE_NOTE = "deterministic Stage152 low-resolution exchange-balanced coverage batch."
    BASE.SELECTION_NOTE = "low-resolution class is a manifest coverage obligation, not a trade filter."
    BASE.PATH_CHART_TITLE = "Official Path Unchanged; Stage172 Low-Resolution Exchange-Balanced Delivery"
    BASE.SELECTION_CHART_TITLE = "Stage172 Low-Resolution Exchange-Balanced Coverage Selection"
    BASE.DELIVERY_CHART_TITLE = "Stage172 Delivery Matrix"
    BASE.WINDOW_CHART_TITLE = "Stage172 Window Precheck"
    BASE.GATE_CHART_TITLE = "Stage172 Gate Status Matrix"
    BASE.DECISION_WRITTEN = "stage172_low_resolution_exchange_balanced_tick_aggregate_delivery_written_run_stage160_153_no_rule"
    BASE.DECISION_NONE_WRITTEN = "stage172_low_resolution_exchange_balanced_tick_aggregate_delivery_none_written_no_rule"

    BASE.MAX_REQUESTS = int(os.getenv("STAGE172_MAX_REQUESTS", "24"))
    BASE.WRITE_INCOMING = os.getenv("STAGE172_WRITE_INCOMING", "1").strip() != "0"
    BASE.OVERWRITE_EXISTING = os.getenv("STAGE172_OVERWRITE_EXISTING", "0").strip() == "1"
    BASE.MAX_SECONDS_TICK = int(os.getenv("STAGE172_MAX_SECONDS_TICK", "90"))
    BASE.TICK_DATA_LENGTH = int(os.getenv("STAGE172_TICK_DATA_LENGTH", "120000"))
    BASE.MIN_NORMALIZED_ROWS = int(os.getenv("STAGE172_MIN_NORMALIZED_ROWS", "10"))

    BASE.SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    BASE.SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
    BASE.REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
    BASE.DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
    BASE.WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
    BASE.GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
    BASE.REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    BASE.DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    BASE.PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_low_resolution_exchange_balanced_status_{MODEL_TAG}.png"
    BASE.SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_low_resolution_exchange_balanced_priority_{MODEL_TAG}.png"
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

    low_resolution = data[data["low_resolution_window_count"].gt(0)].copy()
    candidates = low_resolution if not low_resolution.empty else data
    candidates["manifest_coverage_gap_score"] = (
        candidates["low_resolution_window_count"] * 120
        + candidates["maxdd_window_count"] * 10
        + candidates["bottom_loss_window_count"] * 10
        + candidates["right_tail_window_count"] * 10
        + candidates["priority_score"]
    )
    sort_columns = [
        "low_resolution_window_count",
        "required_window_count",
        "estimated_required_1m_bars",
        "priority_score",
        "request_id",
    ]
    grouped: dict[str, list[pd.Series]] = {}
    for exchange, group in candidates.sort_values(
        sort_columns,
        ascending=[False, False, False, False, True],
    ).groupby("exchange", sort=False):
        grouped[str(exchange)] = [row for _, row in group.iterrows()]

    selected_rows: list[pd.Series] = []
    exchange_order = sorted(grouped, key=lambda item: (-len(grouped[item]), item))
    while len(selected_rows) < BASE.MAX_REQUESTS and any(grouped.values()):
        for exchange in exchange_order:
            if len(selected_rows) >= BASE.MAX_REQUESTS:
                break
            rows = grouped.get(exchange, [])
            if rows:
                selected_rows.append(rows.pop(0))

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    selected["batch_rank"] = np.arange(1, len(selected) + 1)
    selected["selection_policy"] = SELECTION_POLICY
    return selected


def main() -> None:
    _set_stage172_globals()
    BASE._select_batch = _select_batch
    BASE.main()


if __name__ == "__main__":
    main()
