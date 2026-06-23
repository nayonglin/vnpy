from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage260"
MODEL_TAG = "stage260_execution_replay_source_inventory_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage260_execution_replay_source_inventory_audit"
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
LOG_DIR = REPO_DIR / "log"

STAGE111_DIR = LINE_DIR / "outputs" / "stage111_execution_replay_intake_acceptance"
STAGE112_DIR = LINE_DIR / "outputs" / "stage112_authorized_microstructure_data_drop_validator"
STAGE117_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"
STAGE136_DIR = LINE_DIR / "outputs" / "stage136_wave0_watch_inbox_arrival_monitor"
STAGE140_DIR = LINE_DIR / "outputs" / "stage140_wave0_unattended_watch_preinstall_status_panel"
STAGE141_DIR = LINE_DIR / "outputs" / "stage141_candidate_promotion_gate_contract"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE255_DIR = LINE_DIR / "outputs" / "stage255_microstructure_coverage_closure_audit"
STAGE259_DIR = LINE_DIR / "outputs" / "stage259_remaining_route_exhaustion_audit"

STAGE111_PREFIX = "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance"
STAGE112_PREFIX = "qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator"
STAGE117_PREFIX = "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier"
STAGE136_PREFIX = "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor"
STAGE140_PREFIX = "qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel"
STAGE141_PREFIX = "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE255_PREFIX = "qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit"
STAGE259_PREFIX = "qmt_roll_stage259_c9_minrisk_remaining_route_exhaustion_audit"

STAGE111_TAG = "stage111_execution_replay_intake_acceptance_v1"
STAGE112_TAG = "stage112_authorized_microstructure_data_drop_validator_v1"
STAGE117_TAG = "stage117_wave0_delivery_verifier_v1"
STAGE136_TAG = "stage136_wave0_watch_inbox_arrival_monitor_v1"
STAGE140_TAG = "stage140_wave0_unattended_watch_preinstall_status_panel_v1"
STAGE141_TAG = "stage141_candidate_promotion_gate_contract_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE255_TAG = "stage255_microstructure_coverage_closure_audit_v1"
STAGE259_TAG = "stage259_remaining_route_exhaustion_audit_v1"

STAGE111_SUMMARY_IN = STAGE111_DIR / f"{STAGE111_PREFIX}_summary_{STAGE111_TAG}.csv"
STAGE111_SMOKE_IN = STAGE111_DIR / f"{STAGE111_PREFIX}_stage932_smoke_audit_{STAGE111_TAG}.csv"
STAGE111_FIELD_IN = STAGE111_DIR / f"{STAGE111_PREFIX}_field_contract_{STAGE111_TAG}.csv"
STAGE112_SUMMARY_IN = STAGE112_DIR / f"{STAGE112_PREFIX}_summary_{STAGE112_TAG}.csv"
STAGE112_FILE_AUDIT_IN = STAGE112_DIR / f"{STAGE112_PREFIX}_file_audit_{STAGE112_TAG}.csv"
STAGE117_SUMMARY_IN = STAGE117_DIR / f"{STAGE117_PREFIX}_summary_{STAGE117_TAG}.csv"
STAGE136_SUMMARY_IN = STAGE136_DIR / f"{STAGE136_PREFIX}_summary_{STAGE136_TAG}.csv"
STAGE140_SUMMARY_IN = STAGE140_DIR / f"{STAGE140_PREFIX}_summary_{STAGE140_TAG}.csv"
STAGE141_SUMMARY_IN = STAGE141_DIR / f"{STAGE141_PREFIX}_summary_{STAGE141_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE255_SUMMARY_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_summary_{STAGE255_TAG}.csv"
STAGE255_COVERAGE_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_coverage_ledger_{STAGE255_TAG}.csv"
STAGE255_ROUTE_IN = STAGE255_DIR / f"{STAGE255_PREFIX}_route_status_{STAGE255_TAG}.csv"
STAGE259_SUMMARY_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_summary_{STAGE259_TAG}.csv"
STAGE259_ROUTE_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_route_ledger_{STAGE259_TAG}.csv"
STAGE259_NEXT_ACTION_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_next_action_queue_{STAGE259_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LOCAL_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_asset_inventory_{MODEL_TAG}.csv"
CANDIDATE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_file_audit_{MODEL_TAG}.csv"
FIELD_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_replay_field_contract_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_execution_replay_status_{MODEL_TAG}.png"
FIELD_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_contract_heatmap_{MODEL_TAG}.png"
INVENTORY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_inventory_chart_{MODEL_TAG}.png"
CANDIDATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_file_gate_heatmap_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_chart_{MODEL_TAG}.png"

FULL_ENTRY_DECISION_COUNT = 219
SCAN_EXTENSIONS = {".csv", ".json", ".ndjson", ".parquet", ".log", ".md"}
MAX_CSV_ROWS_TO_COUNT_BYTES = 80 * 1024 * 1024

SCAN_STAGE_DIRS = [
    LINE_DIR / "outputs" / "stage110_execution_replay_data_contract_audit",
    STAGE111_DIR,
    STAGE112_DIR,
    STAGE117_DIR,
    STAGE136_DIR,
    STAGE140_DIR,
    STAGE141_DIR,
    STAGE255_DIR,
    STAGE259_DIR,
]

SCAN_NAME_PATTERNS = [
    "official_live_phase_d_execution",
    "stage932",
    "stage587",
    "stage591",
    "stage605",
    "stage608",
    "stage615",
    "stage174",
    "stage916",
    "stage917",
    "stage931",
    "ctp",
    "simnow",
    "broker_replay",
    "broker_execution",
    "broker_order",
    "broker_trade",
    "production_replay",
    "production_execution",
    "live_tca",
    "read_only",
    "readonly",
    "smoke",
    "pending_orders",
    "execution",
    "order",
    "fill",
    "wave0",
    "w0",
    "microstructure",
]

FIELD_GROUPS: dict[str, list[str]] = {
    "bridge_signal_or_reference": [
        "bridge_signal_id",
        "signal_id",
        "order_reference",
        "reference",
        "clordid",
        "cl_ord_id",
        "origclordid",
    ],
    "returned_order_id": [
        "vt_orderid",
        "orderid",
        "order_id",
        "order number",
        "ordernumber",
        "orderidguid",
    ],
    "trade_or_execution_id": [
        "vt_tradeid",
        "tradeid",
        "trade_id",
        "execid",
        "exec_id",
        "execution_id",
        "fill_id",
    ],
    "instrument_identity": [
        "vt_symbol",
        "symbol",
        "instrument",
        "instrumentid",
        "securityid",
        "commodity",
    ],
    "exchange_identity": ["exchange", "exchangeid", "market", "venue"],
    "direction_or_side": ["direction", "side", "buy_sell", "buy/sell"],
    "offset_or_open_close": ["offset", "open_close", "comb_offset_flag", "position_effect"],
    "order_status_lifecycle": ["status", "order_status", "ordstatus", "exec_type", "exectype"],
    "order_timestamp": [
        "order_ts",
        "order_time",
        "submit_time",
        "insert_time",
        "send_time",
        "datetime",
    ],
    "trade_timestamp": ["trade_ts", "trade_time", "fill_ts", "fill_time", "transacttime", "datetime"],
    "order_or_fill_price": ["price", "order_price", "fill_price", "lastpx", "last_px", "avg_px"],
    "order_or_fill_volume": ["volume", "traded", "filled_volume", "lastshares", "cumqty", "order_qty"],
    "gateway_or_broker": ["gateway_name", "gateway", "broker", "broker_id"],
    "account_identity": ["account_id", "account", "investorid", "investor_id", "executing account"],
    "source_provenance_hash": ["raw_sha256", "raw_hash", "schema_hash", "file_sha256", "source_file"],
    "source_license_or_permission": ["source_license", "permission", "license", "source_permission"],
}

CORE_FIELD_GROUPS = [
    "bridge_signal_or_reference",
    "returned_order_id",
    "instrument_identity",
    "direction_or_side",
    "order_status_lifecycle",
    "order_timestamp",
    "order_or_fill_price",
    "order_or_fill_volume",
    "source_provenance_hash",
    "source_license_or_permission",
]

STRICT_FIELD_GROUPS = list(FIELD_GROUPS.keys())


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _clean_field(text: Any) -> str:
    value = str(text).strip().lower()
    return re.sub(r"[^a-z0-9_ /.-]+", "", value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_inputs() -> dict[str, Any]:
    return {
        "stage111_summary": _row(_read_csv(STAGE111_SUMMARY_IN)),
        "stage111_smoke": _read_csv(STAGE111_SMOKE_IN, required=False),
        "stage111_field": _read_csv(STAGE111_FIELD_IN, required=False),
        "stage112_summary": _row(_read_csv(STAGE112_SUMMARY_IN)),
        "stage112_file_audit": _read_csv(STAGE112_FILE_AUDIT_IN, required=False),
        "stage117_summary": _row(_read_csv(STAGE117_SUMMARY_IN)),
        "stage136_summary": _row(_read_csv(STAGE136_SUMMARY_IN)),
        "stage140_summary": _row(_read_csv(STAGE140_SUMMARY_IN)),
        "stage141_summary": _row(_read_csv(STAGE141_SUMMARY_IN)),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage255_summary": _row(_read_csv(STAGE255_SUMMARY_IN)),
        "stage255_coverage": _read_csv(STAGE255_COVERAGE_IN, required=False),
        "stage255_route": _read_csv(STAGE255_ROUTE_IN, required=False),
        "stage259_summary": _row(_read_csv(STAGE259_SUMMARY_IN)),
        "stage259_route": _read_csv(STAGE259_ROUTE_IN, required=False),
        "stage259_next_action": _read_csv(STAGE259_NEXT_ACTION_IN, required=False),
    }


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    arm = stage251_summary.get("arm", pd.Series(dtype=str)).astype(str)
    official = stage251_summary[arm.eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _load_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    arm = curve.get("arm", pd.Series(dtype=str)).astype(str)
    official = curve[arm.eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    for column in ["account_equity", "drawdown_pct"]:
        official[column] = pd.to_numeric(official[column], errors="coerce")
    return official[official["date"].notna()].sort_values("date").reset_index(drop=True)


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() not in SCAN_EXTENSIONS:
        return False
    name = path.name.lower()
    return any(pattern in name for pattern in SCAN_NAME_PATTERNS)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    if BACKTEST_OUTPUT_DIR.exists():
        files.extend(path for path in BACKTEST_OUTPUT_DIR.iterdir() if path.is_file() and _should_scan(path))
    if LOG_DIR.exists():
        files.extend(path for path in LOG_DIR.iterdir() if path.is_file() and _should_scan(path))
    for root in SCAN_STAGE_DIRS:
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file() and _should_scan(path))
    debug_file = REPO_DIR / "debug-simnow-snapshot-probe.md"
    if debug_file.exists():
        files.append(debug_file)
    return sorted(set(files), key=lambda item: str(item))


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR))
    except ValueError:
        return str(path)


def _sha256_sample(path: Path, limit: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read(limit))
    return digest.hexdigest()


def _read_schema(path: Path) -> tuple[list[str], int, str]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
            row_count = -1
            if path.stat().st_size <= MAX_CSV_ROWS_TO_COUNT_BYTES:
                with path.open("rb") as handle:
                    line_count = sum(1 for _ in handle)
                row_count = max(line_count - 1, 0)
            return list(frame.columns), row_count, "ok"
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
            if isinstance(payload, dict):
                return list(payload.keys()), 1, "ok"
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return list(payload[0].keys()), len(payload), "ok"
            return [], 0, "json_no_tabular_schema"
        if suffix == ".ndjson":
            row_count = 0
            first_keys: list[str] = []
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row_count += 1
                    if not first_keys:
                        try:
                            payload = json.loads(line)
                            if isinstance(payload, dict):
                                first_keys = list(payload.keys())
                        except json.JSONDecodeError:
                            pass
            return first_keys, row_count, "ok"
        if suffix == ".parquet":
            try:
                frame = pd.read_parquet(path, columns=[])
                return list(frame.columns), len(frame), "ok"
            except Exception:
                return [], -1, "parquet_schema_unreadable_without_engine"
        return [], -1, "schema_not_applicable"
    except Exception as exc:  # pragma: no cover - defensive inventory path
        return [], -1, f"schema_error:{type(exc).__name__}"


def _field_group_hits(columns: list[str]) -> dict[str, int]:
    cleaned = {_clean_field(column) for column in columns}
    hits: dict[str, int] = {}
    for group, synonyms in FIELD_GROUPS.items():
        group_hit = 0
        for synonym in synonyms:
            target = _clean_field(synonym)
            if target in cleaned or any(target and target in column for column in cleaned):
                group_hit = 1
                break
        hits[group] = group_hit
    return hits


def _classify_role(path: Path, columns: list[str]) -> str:
    name = path.name.lower()
    rel = _relative_path(path).lower()
    if "research/lines/" in rel:
        if "field_contract" in name or "gate" in name or "summary" in name or "report" in name or "decision" in name:
            return "research_audit_artifact"
        if "stage112" in rel or "wave0" in rel or "microstructure" in rel:
            return "data_drop_validator_artifact"
        return "research_line_artifact"
    if "stage932" in name or "smoke" in name:
        return "smoke_or_dry_run_sample"
    if "readonly" in name or "read_only" in name or "stage608" in name or "stage174" in name:
        return "readonly_snapshot_or_probe"
    if any(marker in name for marker in ["stage587", "stage591", "stage605", "stage615"]):
        return "adapter_or_contract_artifact"
    if "pending_orders" in name:
        return "official_shadow_pending_orders"
    if any(
        marker in name
        for marker in [
            "ctp",
            "simnow",
            "broker_replay",
            "broker_execution",
            "broker_order",
            "broker_trade",
            "production_replay",
            "production_execution",
            "live_tca",
            "official_live_phase_d_execution",
        ]
    ):
        return "live_or_broker_artifact"
    if "order" in name or "fill" in name or "execution" in name:
        return "generic_order_execution_artifact"
    if "trade" in name or "replay" in name:
        return "historical_backtest_trade_ledger"
    return "unknown"


def _candidate_file_audit() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in _iter_scan_files():
        columns, row_count, schema_status = _read_schema(path)
        hits = _field_group_hits(columns)
        role = _classify_role(path, columns)
        rel = _relative_path(path)
        is_research_artifact = int(rel.startswith("research/lines/"))
        hard_excluded = int(role in {"research_audit_artifact", "data_drop_validator_artifact", "research_line_artifact"})
        smoke_or_readonly = int(role in {"smoke_or_dry_run_sample", "readonly_snapshot_or_probe", "adapter_or_contract_artifact"})
        order_trade_like = int(
            hits["returned_order_id"]
            or hits["trade_or_execution_id"]
            or ("order" in path.name.lower() or "fill" in path.name.lower())
        )
        core_pass_count = int(sum(hits[group] for group in CORE_FIELD_GROUPS))
        strict_pass_count = int(sum(hits.values()))
        core_contract_pass = int(core_pass_count == len(CORE_FIELD_GROUPS))
        strict_contract_pass = int(strict_pass_count == len(STRICT_FIELD_GROUPS))
        source_candidate = int(not hard_excluded and order_trade_like and not is_research_artifact and not smoke_or_readonly)
        accepted_same_source_replay = int(source_candidate and strict_contract_pass and not smoke_or_readonly)
        blockers = []
        if hard_excluded:
            blockers.append("derived_research_artifact")
        if smoke_or_readonly:
            blockers.append(role)
        if not order_trade_like:
            blockers.append("not_order_trade_like")
        missing_core = [group for group in CORE_FIELD_GROUPS if not hits[group]]
        if missing_core:
            blockers.append("missing_core:" + ",".join(missing_core[:6]))
        if not hits["source_provenance_hash"] or not hits["source_license_or_permission"]:
            blockers.append("missing_raw_hash_or_license")
        rows.append(
            {
                "path": rel,
                "file_name": path.name,
                "file_role": role,
                "suffix": path.suffix.lower(),
                "bytes": path.stat().st_size,
                "row_count": row_count,
                "schema_status": schema_status,
                "column_count": len(columns),
                "columns_sample": ";".join(str(column) for column in columns[:24]),
                "schema_sample_sha256": _sha256_sample(path),
                "source_candidate": source_candidate,
                "order_trade_like": order_trade_like,
                "core_contract_pass_count": core_pass_count,
                "core_contract_total_count": len(CORE_FIELD_GROUPS),
                "strict_contract_pass_count": strict_pass_count,
                "strict_contract_total_count": len(STRICT_FIELD_GROUPS),
                "core_contract_pass": core_contract_pass,
                "strict_contract_pass": strict_contract_pass,
                "accepted_same_source_replay": accepted_same_source_replay,
                "blockers": ";".join(blockers),
                **{f"has_{group}": value for group, value in hits.items()},
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["accepted_same_source_replay", "source_candidate", "core_contract_pass_count", "strict_contract_pass_count", "bytes"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def _local_asset_inventory(candidate_audit: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    if candidate_audit.empty:
        role_counts = Counter()
    else:
        role_counts = Counter(candidate_audit["file_role"].astype(str))
    s111 = inputs["stage111_summary"]
    s112 = inputs["stage112_summary"]
    s255 = inputs["stage255_summary"]
    rows = [
        {
            "asset_id": "stage111_execution_replay_intake",
            "asset_family": "same_source_execution_replay",
            "status": "blocked_no_valid_research_sample",
            "file_count": 1,
            "row_or_order_count": _to_int(s111.get("stage932_total_snapshot_rows")),
            "ready_count": _to_int(s111.get("stage932_valid_research_sample_count")),
            "expected_count": _to_int(s111.get("stage932_session_count")),
            "coverage_pct": _safe_div(s111.get("stage932_valid_research_sample_count", 0), s111.get("stage932_session_count", 0)),
            "rule_ready": 0,
            "notes": "Stage932 snapshots exist but valid research samples are zero.",
        },
        {
            "asset_id": "stage112_authorized_microstructure_drop",
            "asset_family": "authorized_mbo_mbp10",
            "status": "absent_or_not_rule_ready",
            "file_count": _to_int(s112.get("file_audit_count", s112.get("data_file_count", 0))),
            "row_or_order_count": _to_int(s112.get("rule_ready_data_file_count")),
            "ready_count": _to_int(s112.get("rule_ready_data_file_count")),
            "expected_count": 1,
            "coverage_pct": _safe_div(s112.get("rule_ready_data_file_count", 0), 1),
            "rule_ready": 0,
            "notes": "No accepted MBO/L3 or MBP10/L2 rule-ready data drop.",
        },
        {
            "asset_id": "stage255_full_orderflow_or_execution_replay",
            "asset_family": "entry_decision_coverage",
            "status": "missing_for_all_entry_decisions",
            "file_count": 0,
            "row_or_order_count": _to_int(s255.get("full_orderflow_ready_order_count")),
            "ready_count": _to_int(s255.get("full_orderflow_ready_order_count")),
            "expected_count": _to_int(s255.get("full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT),
            "coverage_pct": _safe_div(s255.get("full_orderflow_ready_order_count", 0), s255.get("full_orderflow_expected_order_count", FULL_ENTRY_DECISION_COUNT)),
            "rule_ready": 0,
            "notes": "Orderflow/execution replay coverage remains zero.",
        },
        {
            "asset_id": "local_file_scan_source_candidates",
            "asset_family": "filesystem_inventory",
            "status": "no_accepted_same_source_replay_file",
            "file_count": int(candidate_audit["source_candidate"].sum()) if not candidate_audit.empty else 0,
            "row_or_order_count": int(candidate_audit["row_count"].clip(lower=0).sum()) if not candidate_audit.empty and "row_count" in candidate_audit else 0,
            "ready_count": int(candidate_audit["accepted_same_source_replay"].sum()) if not candidate_audit.empty else 0,
            "expected_count": FULL_ENTRY_DECISION_COUNT,
            "coverage_pct": 0.0,
            "rule_ready": 0,
            "notes": "Filesystem scan found artifacts, not a complete same-source replay contract.",
        },
    ]
    for role, count in sorted(role_counts.items()):
        rows.append(
            {
                "asset_id": f"scan_role_{role}",
                "asset_family": "filesystem_role_count",
                "status": "inventory_only",
                "file_count": int(count),
                "row_or_order_count": 0,
                "ready_count": 0,
                "expected_count": 0,
                "coverage_pct": np.nan,
                "rule_ready": 0,
                "notes": "Role count from local scan; not promoted by itself.",
            }
        )
    return pd.DataFrame(rows)


def _field_contract(candidate_audit: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group, synonyms in FIELD_GROUPS.items():
        file_hit_count = int(candidate_audit.get(f"has_{group}", pd.Series(dtype=int)).sum()) if not candidate_audit.empty else 0
        source_hit_count = (
            int(candidate_audit.loc[candidate_audit["source_candidate"].eq(1), f"has_{group}"].sum())
            if not candidate_audit.empty and f"has_{group}" in candidate_audit
            else 0
        )
        rows.append(
            {
                "field_group": group,
                "required_for": "same_source_execution_replay",
                "accepted_rule": "present in immutable source candidate and joined to all selected C9 entries",
                "local_file_hit_count": file_hit_count,
                "source_candidate_hit_count": source_hit_count,
                "accepted_replay_hit_count": 0,
                "pass_now": 0,
                "synonyms": ",".join(synonyms),
            }
        )
    rows.extend(
        [
            {
                "field_group": "full_entry_decision_coverage",
                "required_for": "anti_selection_and_tail_gate",
                "accepted_rule": "same-source replay covers 219/219 timestamp-ready entry decisions before rule design",
                "local_file_hit_count": _to_int(inputs["stage255_summary"].get("full_orderflow_ready_order_count")),
                "source_candidate_hit_count": 0,
                "accepted_replay_hit_count": 0,
                "pass_now": 0,
                "synonyms": "entry_decision_id,decision_ts,vt_symbol,side",
            },
            {
                "field_group": "right_tail_bottom_loss_visual_coverage",
                "required_for": "anti_overfit_promotion_gate",
                "accepted_rule": "covers all selected right-tail and bottom-loss windows with raw provenance",
                "local_file_hit_count": 0,
                "source_candidate_hit_count": 0,
                "accepted_replay_hit_count": 0,
                "pass_now": 0,
                "synonyms": "right_tail_sample,bottom_loss_sample,window_raw_hash",
            },
        ]
    )
    return pd.DataFrame(rows)


def _promotion_gate(candidate_audit: pd.DataFrame, field_contract: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    s111 = inputs["stage111_summary"]
    s112 = inputs["stage112_summary"]
    s255 = inputs["stage255_summary"]
    s259 = inputs["stage259_summary"]
    rows = [
        {
            "gate_id": "no_official_config_or_order_side_effect",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Stage260 is inventory-only; no CTP/SimNow/order API call.",
        },
        {
            "gate_id": "stage111_valid_research_sample",
            "required": _to_int(s111.get("stage932_session_count")),
            "observed": _to_int(s111.get("stage932_valid_research_sample_count")),
            "pass_now": 0,
            "reason": "Stage932 samples are dry-run/smoke/read-only or symbol/reference mismatched.",
        },
        {
            "gate_id": "stage112_authorized_microstructure_rule_ready_file",
            "required": 1,
            "observed": _to_int(s112.get("rule_ready_data_file_count")),
            "pass_now": 0,
            "reason": "No accepted authorized MBO/L3 or MBP10/L2 drop.",
        },
        {
            "gate_id": "full_orderflow_or_execution_replay_coverage",
            "required": _to_int(s255.get("full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT),
            "observed": _to_int(s255.get("full_orderflow_ready_order_count")),
            "pass_now": 0,
            "reason": "Same-source orderflow/execution replay is missing for all entry decisions.",
        },
        {
            "gate_id": "accepted_same_source_replay_file",
            "required": 1,
            "observed": int(candidate_audit["accepted_same_source_replay"].sum()) if not candidate_audit.empty else 0,
            "pass_now": 0,
            "reason": "Local scan found no immutable non-smoke replay file satisfying strict field contract.",
        },
        {
            "gate_id": "field_contract_all_pass",
            "required": len(field_contract),
            "observed": int(field_contract["pass_now"].sum()),
            "pass_now": 0,
            "reason": "Source hash/license and all-entry tail coverage are absent.",
        },
        {
            "gate_id": "stage259_route_reopened",
            "required": 1,
            "observed": _to_int(s259.get("strategy_rule_allowed_route_count")),
            "pass_now": 0,
            "reason": "Stage259 closed/blocked all local routes; import replay requires external state.",
        },
    ]
    return pd.DataFrame(rows)


def _next_action_queue(inputs: dict[str, Any], candidate_audit: pd.DataFrame) -> pd.DataFrame:
    stage259_next = inputs["stage259_next_action"].copy()
    rows: list[dict[str, Any]] = []
    if not stage259_next.empty:
        for _, row in stage259_next.iterrows():
            action_id = str(row.get("next_action_id", ""))
            rows.append(
                {
                    "rank": _to_int(row.get("rank"), len(rows) + 1),
                    "next_action_id": action_id,
                    "action_type": row.get("action_type", ""),
                    "can_start_without_external_state": _to_int(row.get("can_start_without_external_state")),
                    "actionable_now_after_stage260": int(action_id == "outside_account_capital_governance_only"),
                    "strategy_rule_allowed_now": 0,
                    "true_engine_allowed_now": 0,
                    "stage260_judgment": (
                        "requires_new_external_or_broker_data"
                        if action_id != "outside_account_capital_governance_only"
                        else "can_study_only_if_no_holding_path_change"
                    ),
                    "reason": row.get("reason", ""),
                }
            )
    if not rows:
        rows.append(
            {
                "rank": 1,
                "next_action_id": "import_broker_or_production_execution_replay",
                "action_type": "same_source_replay",
                "can_start_without_external_state": 0,
                "actionable_now_after_stage260": 0,
                "strategy_rule_allowed_now": 0,
                "true_engine_allowed_now": 0,
                "stage260_judgment": "requires_new_external_or_broker_data",
                "reason": "No accepted local replay file found.",
            }
        )
    rows.append(
        {
            "rank": max(row["rank"] for row in rows) + 1,
            "next_action_id": "do_not_mine_local_ohlcv_oi_thresholds",
            "action_type": "stop_condition",
            "can_start_without_external_state": 1,
            "actionable_now_after_stage260": 1,
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "stage260_judgment": "closed_to_avoid_overfit",
            "reason": "Stage260 found no same-source replay, so extra local threshold mining cannot answer execution-quality causality.",
        }
    )
    return pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)


def _summary(
    candidate_audit: pd.DataFrame,
    asset_inventory: pd.DataFrame,
    field_contract: pd.DataFrame,
    promotion_gate: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    official = _official_summary(inputs["stage251_summary"])
    s111 = inputs["stage111_summary"]
    s112 = inputs["stage112_summary"]
    s255 = inputs["stage255_summary"]
    source_candidates = int(candidate_audit["source_candidate"].sum()) if not candidate_audit.empty else 0
    order_like = int(candidate_audit["order_trade_like"].sum()) if not candidate_audit.empty else 0
    accepted_files = int(candidate_audit["accepted_same_source_replay"].sum()) if not candidate_audit.empty else 0
    full_expected = _to_int(s255.get("full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT)
    full_ready = _to_int(s255.get("full_orderflow_ready_order_count"))
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage260_execution_replay_local_inventory_missing_same_source_no_rule",
        "stage_nature": "read_only_execution_replay_source_inventory_audit",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "scanned_file_count": int(len(candidate_audit)),
        "source_candidate_file_count": source_candidates,
        "order_trade_like_file_count": order_like,
        "accepted_same_source_replay_file_count": accepted_files,
        "stage932_session_count": _to_int(s111.get("stage932_session_count")),
        "stage932_valid_research_sample_count": _to_int(s111.get("stage932_valid_research_sample_count")),
        "stage112_rule_ready_data_file_count": _to_int(s112.get("rule_ready_data_file_count")),
        "full_orderflow_expected_order_count": full_expected,
        "full_orderflow_ready_order_count": full_ready,
        "full_orderflow_missing_order_count": max(full_expected - full_ready, 0),
        "same_source_execution_replay_missing_order_count": _to_int(
            s255.get("same_source_execution_replay_missing_order_count"), FULL_ENTRY_DECISION_COUNT
        ),
        "field_contract_count": int(len(field_contract)),
        "field_contract_pass_count": int(field_contract["pass_now"].sum()),
        "promotion_gate_count": int(len(promotion_gate)),
        "promotion_gate_pass_count": int(promotion_gate["pass_now"].sum()),
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "official_end_equity": _to_float(official.get("end_equity")),
        "official_total_return_pct": _to_float(official.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official.get("max_dd_pct")),
        "official_sharpe": _to_float(official.get("sharpe")),
        "official_total_slippage": _to_float(official.get("total_slippage")),
        "official_total_trade_count": _to_float(official.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official.get("nonzero_daily_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(official.get("max_broker10_margin_to_equity_pct")),
        "visual_file_count": 5,
        "asset_inventory_row_count": int(len(asset_inventory)),
    }


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, ax1 = plt.subplots(figsize=(13, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#174a7c", linewidth=1.8, label="official equity")
    ax1.set_ylabel("Equity")
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#c44e52", alpha=0.18, label="drawdown")
    ax2.set_ylabel("Drawdown %")
    ax1.set_title("Stage260 official path vs execution replay coverage")
    text = (
        f"same-source replay ready: {summary['full_orderflow_ready_order_count']}/"
        f"{summary['full_orderflow_expected_order_count']} | "
        f"accepted files: {summary['accepted_same_source_replay_file_count']} | "
        f"no rule / no true engine"
    )
    ax1.text(
        0.01,
        0.96,
        text,
        transform=ax1.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#888888", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_field_heatmap(field_contract: pd.DataFrame) -> None:
    data = field_contract[["local_file_hit_count", "source_candidate_hit_count", "accepted_replay_hit_count", "pass_now"]].to_numpy(dtype=float)
    labels = field_contract["field_group"].astype(str).tolist()
    fig_height = max(6, len(labels) * 0.36)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu", vmin=0, vmax=max(1.0, float(np.nanmax(data)) if data.size else 1.0))
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(4))
    ax.set_xticklabels(["local hit", "source hit", "accepted hit", "pass"], rotation=20, ha="right")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, f"{int(data[y, x])}", ha="center", va="center", fontsize=8, color="#111111")
    ax.set_title("Stage260 execution replay field contract")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(FIELD_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_inventory(asset_inventory: pd.DataFrame, candidate_audit: pd.DataFrame) -> None:
    role_counts = (
        candidate_audit.groupby("file_role").size().sort_values(ascending=False).head(12)
        if not candidate_audit.empty
        else pd.Series(dtype=int)
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#4c78a8" if "smoke" not in role and "readonly" not in role else "#f58518" for role in role_counts.index]
    ax.barh(role_counts.index.astype(str), role_counts.values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("File count")
    ax.set_title("Stage260 local asset inventory by file role")
    for idx, value in enumerate(role_counts.values):
        ax.text(value + 0.2, idx, str(int(value)), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(INVENTORY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_candidate_heatmap(candidate_audit: pd.DataFrame) -> None:
    fields = [f"has_{group}" for group in FIELD_GROUPS]
    if candidate_audit.empty:
        data = np.zeros((1, len(fields)))
        labels = ["no_files"]
    else:
        top = candidate_audit.head(25).copy()
        data = top[fields].to_numpy(dtype=float)
        labels = top["file_name"].astype(str).str.slice(0, 70).tolist()
    fig_height = max(6, len(labels) * 0.35)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xticks(range(len(fields)))
    ax.set_xticklabels([field.replace("has_", "") for field in fields], rotation=45, ha="right", fontsize=7)
    ax.set_title("Stage260 top local files vs strict replay field groups")
    fig.tight_layout()
    fig.savefig(CANDIDATE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    data = next_action[["can_start_without_external_state", "actionable_now_after_stage260", "strategy_rule_allowed_now", "true_engine_allowed_now"]].to_numpy(dtype=float)
    labels = next_action["next_action_id"].astype(str).tolist()
    fig_height = max(5, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(4))
    ax.set_xticklabels(["no external", "actionable", "rule", "true engine"], rotation=25, ha="right")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage260 next action queue")
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: dict[str, Any],
    asset_inventory: pd.DataFrame,
    candidate_audit: pd.DataFrame,
    field_contract: pd.DataFrame,
    promotion_gate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    top_candidates = candidate_audit[
        [
            "file_name",
            "file_role",
            "source_candidate",
            "order_trade_like",
            "core_contract_pass_count",
            "strict_contract_pass_count",
            "accepted_same_source_replay",
            "blockers",
        ]
    ].head(15)
    report = f"""# Stage260 Execution Replay Source Inventory Audit

- line_id: `{LINE_ID}`
- created_at: `{summary['created_at']}`
- decision: `{summary['decision']}`
- nature: read-only inventory, no strategy rule, no true engine, no order API, no CTP/SimNow connection.

## Summary

- scanned files: `{summary['scanned_file_count']}`
- source candidate files: `{summary['source_candidate_file_count']}`
- order/trade-like files: `{summary['order_trade_like_file_count']}`
- accepted same-source replay files: `{summary['accepted_same_source_replay_file_count']}`
- Stage932 valid research samples: `{summary['stage932_valid_research_sample_count']}/{summary['stage932_session_count']}`
- Stage112 rule-ready data files: `{summary['stage112_rule_ready_data_file_count']}`
- full orderflow/execution replay coverage: `{summary['full_orderflow_ready_order_count']}/{summary['full_orderflow_expected_order_count']}`
- field contract pass: `{summary['field_contract_pass_count']}/{summary['field_contract_count']}`
- promotion gate pass: `{summary['promotion_gate_pass_count']}/{summary['promotion_gate_count']}`

## Judgment

Local files still do not provide a source contract that can join C9 signal -> submit reference -> exact returned order id -> order lifecycle -> trade/fill -> account/gateway -> raw hash/license across all selected entry decisions. The useful next step remains external/broker data import or forward capture. Local OHLCV/OI threshold mining stays closed because it cannot answer execution-quality causality.

## Asset Inventory

{_md_table(asset_inventory.head(20))}

## Top Candidate Files

{_md_table(top_candidates)}

## Field Contract

{_md_table(field_contract)}

## Promotion Gate

{_md_table(promotion_gate)}

## Next Action

{_md_table(next_action)}

## Files

- `{SUMMARY_OUT}`
- `{LOCAL_INVENTORY_OUT}`
- `{CANDIDATE_AUDIT_OUT}`
- `{FIELD_CONTRACT_OUT}`
- `{PROMOTION_GATE_OUT}`
- `{NEXT_ACTION_OUT}`
- `{PATH_CHART_OUT}`
- `{FIELD_HEATMAP_OUT}`
- `{INVENTORY_CHART_OUT}`
- `{CANDIDATE_HEATMAP_OUT}`
- `{NEXT_ACTION_CHART_OUT}`
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    candidate_audit = _candidate_file_audit()
    asset_inventory = _local_asset_inventory(candidate_audit, inputs)
    field_contract = _field_contract(candidate_audit, inputs)
    promotion_gate = _promotion_gate(candidate_audit, field_contract, inputs)
    next_action = _next_action_queue(inputs, candidate_audit)
    summary = _summary(candidate_audit, asset_inventory, field_contract, promotion_gate, inputs)
    curve = _load_curve(inputs["stage251_curve"])

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(asset_inventory, LOCAL_INVENTORY_OUT)
    _write_csv(candidate_audit, CANDIDATE_AUDIT_OUT)
    _write_csv(field_contract, FIELD_CONTRACT_OUT)
    _write_csv(promotion_gate, PROMOTION_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, asset_inventory, candidate_audit, field_contract, promotion_gate, next_action)

    _plot_official_path(curve, summary)
    _plot_field_heatmap(field_contract)
    _plot_inventory(asset_inventory, candidate_audit)
    _plot_candidate_heatmap(candidate_audit)
    _plot_next_action(next_action)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
