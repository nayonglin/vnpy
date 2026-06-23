from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage112"
MODEL_TAG = "stage112_authorized_microstructure_data_drop_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage112_authorized_microstructure_data_drop_validator"
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE108_RISK_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE110_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage110_execution_replay_data_contract_audit"
    / "qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_summary_"
    "stage110_execution_replay_data_contract_audit_v1.csv"
)
STAGE111_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage111_execution_replay_intake_acceptance"
    / "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_summary_"
    "stage111_execution_replay_intake_acceptance_v1.csv"
)
STAGE111_GATE_IN = (
    LINE_DIR
    / "outputs"
    / "stage111_execution_replay_intake_acceptance"
    / "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_intake_gate_matrix_"
    "stage111_execution_replay_intake_acceptance_v1.csv"
)
STAGE111_STAGE932_IN = (
    LINE_DIR
    / "outputs"
    / "stage111_execution_replay_intake_acceptance"
    / "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_stage932_smoke_audit_"
    "stage111_execution_replay_intake_acceptance_v1.csv"
)

INTAKE_ROOTS = [
    LINE_DIR / "data" / "authorized_microstructure_intake",
    LINE_DIR / "inputs" / "authorized_microstructure_intake",
]
MANIFEST_NAMES = {"manifest.csv", "manifest.json", "manifest.jsonl", "manifest.ndjson", "manifest.parquet"}
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}
OLD_SOURCE_MARKERS = (
    "stage932",
    "stage608",
    "tqsdk",
    "tq_",
    "dry-run",
    "dry_run",
    "smoke",
    "synthetic",
    "stage131",
    "positive_drop",
    "contract_positive",
    "local_contract_positive",
)

COMMON_REQUIRED_COLUMNS = [
    "vt_symbol",
    "exchange",
    "symbol",
    "trading_day",
    "session_id",
    "ts_event",
    "ts_recv",
    "action",
    "side",
    "price",
    "size",
    "raw_file",
    "raw_sha256",
    "schema_hash",
    "source_license",
]
MBO_REQUIRED_COLUMNS = COMMON_REQUIRED_COLUMNS + ["order_id", "sequence"]
MBP10_REQUIRED_COLUMNS = (
    COMMON_REQUIRED_COLUMNS
    + ["depth"]
    + [f"bid_px_{idx:02d}" for idx in range(10)]
    + [f"ask_px_{idx:02d}" for idx in range(10)]
    + [f"bid_sz_{idx:02d}" for idx in range(10)]
    + [f"ask_sz_{idx:02d}" for idx in range(10)]
    + [f"bid_ct_{idx:02d}" for idx in range(10)]
    + [f"ask_ct_{idx:02d}" for idx in range(10)]
)
L1_TICK_COLUMNS = [
    "vt_symbol",
    "datetime",
    "last_price",
    "bid_price_1",
    "ask_price_1",
    "bid_volume_1",
    "ask_volume_1",
]

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_drop_inventory_{MODEL_TAG}.csv"
FILE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_audit_{MODEL_TAG}.csv"
SCHEMA_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_schema_contract_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_acceptance_gate_{MODEL_TAG}.csv"
COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_requirements_{MODEL_TAG}.csv"
NEGATIVE_EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_negative_evidence_{MODEL_TAG}.csv"
MANIFEST_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample_manifest_template_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_data_drop_gate_{MODEL_TAG}.png"
INVENTORY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_chart_{MODEL_TAG}.png"
SCHEMA_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_gate_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_requirement_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _normalize_columns(columns: list[Any]) -> set[str]:
    return {_clean(column).lower() for column in columns if _clean(column)}


def _schema_match(columns: list[Any]) -> tuple[str, int, int, str]:
    normalized = _normalize_columns(columns)
    mbo_missing = [column for column in MBO_REQUIRED_COLUMNS if column.lower() not in normalized]
    mbp_missing = [column for column in MBP10_REQUIRED_COLUMNS if column.lower() not in normalized]
    l1_missing = [column for column in L1_TICK_COLUMNS if column.lower() not in normalized]
    mbo_present = len(MBO_REQUIRED_COLUMNS) - len(mbo_missing)
    mbp_present = len(MBP10_REQUIRED_COLUMNS) - len(mbp_missing)
    l1_present = len(L1_TICK_COLUMNS) - len(l1_missing)
    if not mbo_missing:
        return "authorized_mbo_l3", 1, mbo_present, ""
    if not mbp_missing:
        return "authorized_mbp10_l2", 1, mbp_present, ""
    if not l1_missing:
        return "l1_tick_forward_watch_only", 0, l1_present, "l1_tick_has_no_l3_queue_or_l2_10_depth"
    if mbo_present >= mbp_present:
        return "partial_mbo_like", 0, mbo_present, ";".join(mbo_missing[:12])
    return "partial_mbp10_like", 0, mbp_present, ";".join(mbp_missing[:12])


def _read_json_rows(path: Path, max_rows: int = 200) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        for line in text.splitlines()[:max_rows]:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data[:max_rows] if isinstance(item, dict)]
    if isinstance(data, dict):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [item for item in rows[:max_rows] if isinstance(item, dict)]
        return [data]
    return []


def _read_manifest(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return pd.DataFrame(_read_json_rows(path, max_rows=10000))
    if suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _inspect_file_schema(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    columns: list[Any] = []
    row_sample_count = 0
    read_error = ""
    parquet_num_rows: int | None = None
    try:
        if suffix == ".csv":
            sample = pd.read_csv(path, nrows=200, encoding="utf-8-sig")
            columns = list(sample.columns)
            row_sample_count = len(sample)
        elif suffix in {".json", ".jsonl", ".ndjson"}:
            rows = _read_json_rows(path, max_rows=200)
            columns = list(pd.DataFrame(rows).columns)
            row_sample_count = len(rows)
        elif suffix == ".parquet":
            try:
                import pyarrow.parquet as pq  # type: ignore

                parquet_file = pq.ParquetFile(path)
                columns = list(parquet_file.schema_arrow.names)
                parquet_num_rows = int(parquet_file.metadata.num_rows) if parquet_file.metadata else None
                row_sample_count = min(parquet_num_rows or 0, 200)
            except Exception as exc:
                read_error = f"parquet_metadata_error:{exc.__class__.__name__}"
    except Exception as exc:
        read_error = f"read_error:{exc.__class__.__name__}"
    schema_type, schema_ready, required_present_count, missing_required = _schema_match(columns)
    return {
        "file_path": str(path),
        "file_suffix": suffix,
        "file_exists": int(path.exists()),
        "file_bytes": int(path.stat().st_size) if path.exists() else 0,
        "row_sample_count": row_sample_count,
        "parquet_num_rows": parquet_num_rows if parquet_num_rows is not None else "",
        "column_count": len(columns),
        "columns": ";".join(str(column) for column in columns[:80]),
        "detected_schema_type": schema_type,
        "schema_ready": schema_ready,
        "required_present_count": required_present_count,
        "missing_required_sample": missing_required,
        "read_error": read_error,
    }


def _manifest_file_path(root: Path, value: Any) -> Path | None:
    text = _clean(value)
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else root / path


def _first_nonempty(row: pd.Series, names: list[str]) -> str:
    lower = {str(column).lower(): column for column in row.index}
    for name in names:
        column = lower.get(name.lower())
        if column is None:
            continue
        value = _clean(row.get(column))
        if value:
            return value
    return ""


def _truthy_source_permission(value: str) -> int:
    text = value.lower()
    if not text:
        return 0
    blocked = ("unknown", "demo", "dry", "smoke", "synthetic", "personal_test", "research_sample_only")
    return int(not any(marker in text for marker in blocked))


def _old_source_marker(values: list[str]) -> str:
    joined = " ".join(value.lower() for value in values if value)
    for marker in OLD_SOURCE_MARKERS:
        if marker in joined:
            return marker
    return ""


def _scan_intake_roots(risk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    right_tail_required = int(pd.to_numeric(risk.get("right_tail_visual", 0), errors="coerce").fillna(0).sum())
    bottom_loss_required = int(pd.to_numeric(risk.get("bottom_loss_visual", 0), errors="coerce").fillna(0).sum())
    timestamp_required = len(risk)

    for root in INTAKE_ROOTS:
        root_exists = int(root.exists())
        all_files = sorted([path for path in root.rglob("*") if path.is_file()]) if root.exists() else []
        manifest_files = [path for path in all_files if path.name.lower() in MANIFEST_NAMES]
        data_files = [path for path in all_files if path.suffix.lower() in DATA_SUFFIXES and path.name.lower() not in MANIFEST_NAMES]
        manifest_row_count = 0
        manifest_data_file_count = 0
        manifest_data_file_existing_count = 0
        manifest_schema_ready_count = 0
        manifest_basic_pass_count = 0
        manifest_rule_ready_count = 0
        manifest_license_clear_count = 0
        manifest_old_source_marker_count = 0
        max_timestamp_coverage_pct = 0.0
        max_right_tail_covered_count = 0
        max_bottom_loss_covered_count = 0
        vendors: set[str] = set()

        for manifest_path in manifest_files:
            manifest = _read_manifest(manifest_path)
            manifest_row_count += len(manifest)
            for index, row in manifest.iterrows():
                data_value = _first_nonempty(row, ["data_file", "data_path", "file", "path", "relative_path"])
                raw_value = _first_nonempty(row, ["raw_file", "raw_path", "source_raw_file"])
                data_path = _manifest_file_path(root, data_value)
                raw_path = _manifest_file_path(root, raw_value)
                manifest_data_file_count += int(data_path is not None)
                data_file_exists = int(data_path.exists()) if data_path is not None else 0
                raw_file_exists = int(raw_path.exists()) if raw_path is not None else 0
                manifest_data_file_existing_count += data_file_exists

                row_schema_declared = _first_nonempty(row, ["schema_type", "data_schema", "schema", "schema_name"])
                row_schema_detected = "not_inspected"
                schema_ready = 0
                required_present_count = 0
                missing_required_sample = ""
                inspect: dict[str, Any] = {}
                if data_path is not None and data_path.exists():
                    inspect = _inspect_file_schema(data_path)
                    row_schema_detected = str(inspect["detected_schema_type"])
                    schema_ready = int(inspect["schema_ready"])
                    required_present_count = int(inspect["required_present_count"])
                    missing_required_sample = str(inspect["missing_required_sample"])
                declared_lower = row_schema_declared.lower()
                declared_ready = int("mbo" in declared_lower or "mbp" in declared_lower or "depth" in declared_lower)
                schema_ready = int(schema_ready or declared_ready)
                manifest_schema_ready_count += schema_ready

                raw_sha256 = _first_nonempty(row, ["raw_sha256", "sha256", "raw_hash", "file_sha256"])
                schema_hash = _first_nonempty(row, ["schema_hash", "schema_sha256"])
                source_license = _first_nonempty(row, ["source_license", "license", "permission", "source_permission"])
                vendor = _first_nonempty(row, ["source_vendor", "vendor", "source", "provider"])
                if vendor:
                    vendors.add(vendor)
                license_clear = _truthy_source_permission(source_license)
                manifest_license_clear_count += license_clear
                marker = _old_source_marker(
                    [
                        str(manifest_path),
                        data_value,
                        raw_value,
                        row_schema_declared,
                        source_license,
                        vendor,
                        _first_nonempty(row, ["dataset_id", "dataset", "data_set"]),
                        _first_nonempty(row, ["notes", "comment", "description"]),
                        _first_nonempty(row, ["proof_file", "proof_path"]),
                    ]
                )
                manifest_old_source_marker_count += int(bool(marker))

                timestamp_coverage_pct = float(
                    pd.to_numeric(_first_nonempty(row, ["timestamp_ready_order_coverage_pct", "coverage_pct"]), errors="coerce")
                    if _first_nonempty(row, ["timestamp_ready_order_coverage_pct", "coverage_pct"])
                    else 0
                )
                right_tail_covered_count = int(
                    pd.to_numeric(_first_nonempty(row, ["right_tail_covered_count", "right_tail_visual_covered_count"]), errors="coerce")
                    if _first_nonempty(row, ["right_tail_covered_count", "right_tail_visual_covered_count"])
                    else 0
                )
                bottom_loss_covered_count = int(
                    pd.to_numeric(_first_nonempty(row, ["bottom_loss_covered_count", "bottom_loss_visual_covered_count"]), errors="coerce")
                    if _first_nonempty(row, ["bottom_loss_covered_count", "bottom_loss_visual_covered_count"])
                    else 0
                )
                max_timestamp_coverage_pct = max(max_timestamp_coverage_pct, timestamp_coverage_pct)
                max_right_tail_covered_count = max(max_right_tail_covered_count, right_tail_covered_count)
                max_bottom_loss_covered_count = max(max_bottom_loss_covered_count, bottom_loss_covered_count)

                raw_hash_schema_hash_present = int(bool(raw_sha256 and schema_hash and raw_value))
                basic_pass = int(
                    data_file_exists == 1
                    and schema_ready == 1
                    and raw_hash_schema_hash_present == 1
                    and license_clear == 1
                    and not marker
                )
                coverage_pass = int(
                    timestamp_coverage_pct >= 95.0
                    and right_tail_covered_count >= right_tail_required
                    and bottom_loss_covered_count >= bottom_loss_required
                    and timestamp_required > 0
                )
                rule_ready = int(basic_pass and coverage_pass)
                manifest_basic_pass_count += basic_pass
                manifest_rule_ready_count += rule_ready

                file_rows.append(
                    {
                        "root_path": str(root),
                        "manifest_path": str(manifest_path),
                        "manifest_row_index": int(index),
                        "data_file": str(data_path) if data_path is not None else "",
                        "raw_file": str(raw_path) if raw_path is not None else "",
                        "data_file_exists": data_file_exists,
                        "raw_file_exists": raw_file_exists,
                        "declared_schema_type": row_schema_declared,
                        "detected_schema_type": row_schema_detected,
                        "schema_ready": schema_ready,
                        "required_present_count": required_present_count,
                        "missing_required_sample": missing_required_sample,
                        "raw_sha256_present": int(bool(raw_sha256)),
                        "schema_hash_present": int(bool(schema_hash)),
                        "source_license": source_license,
                        "source_license_clear": license_clear,
                        "source_vendor": vendor,
                        "old_source_marker": marker,
                        "timestamp_ready_order_coverage_pct": timestamp_coverage_pct,
                        "right_tail_covered_count": right_tail_covered_count,
                        "bottom_loss_covered_count": bottom_loss_covered_count,
                        "basic_intake_pass": basic_pass,
                        "rule_research_ready": rule_ready,
                        "read_error": str(inspect.get("read_error", "")),
                    }
                )

        inventory_rows.append(
            {
                "root_path": str(root),
                "root_exists": root_exists,
                "file_count": len(all_files),
                "manifest_file_count": len(manifest_files),
                "manifest_row_count": manifest_row_count,
                "data_file_count": len(data_files),
                "manifest_data_file_count": manifest_data_file_count,
                "manifest_data_file_existing_count": manifest_data_file_existing_count,
                "manifest_schema_ready_count": manifest_schema_ready_count,
                "manifest_license_clear_count": manifest_license_clear_count,
                "manifest_old_source_marker_count": manifest_old_source_marker_count,
                "basic_intake_pass_count": manifest_basic_pass_count,
                "rule_research_ready_count": manifest_rule_ready_count,
                "max_timestamp_ready_order_coverage_pct": max_timestamp_coverage_pct,
                "max_right_tail_covered_count": max_right_tail_covered_count,
                "max_bottom_loss_covered_count": max_bottom_loss_covered_count,
                "source_vendor_count": len(vendors),
                "source_vendors": ";".join(sorted(vendors)[:20]),
            }
        )

        orphan_data_files = [path for path in data_files if not manifest_files]
        for path in orphan_data_files[:200]:
            inspect = _inspect_file_schema(path)
            file_rows.append(
                {
                    "root_path": str(root),
                    "manifest_path": "",
                    "manifest_row_index": "",
                    "data_file": str(path),
                    "raw_file": "",
                    "data_file_exists": 1,
                    "raw_file_exists": 0,
                    "declared_schema_type": "",
                    "detected_schema_type": inspect["detected_schema_type"],
                    "schema_ready": int(inspect["schema_ready"]),
                    "required_present_count": int(inspect["required_present_count"]),
                    "missing_required_sample": str(inspect["missing_required_sample"]),
                    "raw_sha256_present": 0,
                    "schema_hash_present": 0,
                    "source_license": "",
                    "source_license_clear": 0,
                    "source_vendor": "",
                    "old_source_marker": _old_source_marker([str(path)]),
                    "timestamp_ready_order_coverage_pct": 0.0,
                    "right_tail_covered_count": 0,
                    "bottom_loss_covered_count": 0,
                    "basic_intake_pass": 0,
                    "rule_research_ready": 0,
                    "read_error": str(inspect["read_error"]),
                }
            )

    return pd.DataFrame(inventory_rows), pd.DataFrame(file_rows)


def _schema_contract() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for route, columns, rule_ready, note in [
        ("authorized_mbo_l3", MBO_REQUIRED_COLUMNS, 1, "order-id keyed order book events; queue-position capable"),
        ("authorized_mbp10_l2", MBP10_REQUIRED_COLUMNS, 1, "price-level top-10 depth events with bid/ask sizes and counts"),
        ("vnpy_l1_tick_forward_watch_only", L1_TICK_COLUMNS, 0, "usable only for forward watch/TCA; insufficient for queue/orderflow rules"),
    ]:
        for column in columns:
            rows.append(
                {
                    "route_schema": route,
                    "required_column": column,
                    "rule_ready_route": rule_ready,
                    "contract_note": note,
                }
            )
    return pd.DataFrame(rows)


def _coverage_requirements(risk: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    timestamp_required = len(risk)
    right_tail_required = int(pd.to_numeric(risk.get("right_tail_visual", 0), errors="coerce").fillna(0).sum())
    bottom_loss_required = int(pd.to_numeric(risk.get("bottom_loss_visual", 0), errors="coerce").fillna(0).sum())
    maxdd_required = int(pd.to_numeric(risk.get("maxdd_context", 0), errors="coerce").fillna(0).sum())
    accepted_timestamp_pct = (
        float(pd.to_numeric(inventory["max_timestamp_ready_order_coverage_pct"], errors="coerce").fillna(0).max())
        if not inventory.empty
        else 0.0
    )
    accepted_right_tail = (
        int(pd.to_numeric(inventory["max_right_tail_covered_count"], errors="coerce").fillna(0).max()) if not inventory.empty else 0
    )
    accepted_bottom_loss = (
        int(pd.to_numeric(inventory["max_bottom_loss_covered_count"], errors="coerce").fillna(0).max()) if not inventory.empty else 0
    )
    rows = [
        {
            "coverage_gate": "timestamp_ready_order_windows",
            "required_count": timestamp_required,
            "required_pct": 95.0,
            "accepted_count_or_pct": accepted_timestamp_pct,
            "pass_now": int(accepted_timestamp_pct >= 95.0 and timestamp_required > 0),
            "why": "C9 timestamp-ready order windows need enough historical microstructure coverage to avoid cherry-picking.",
        },
        {
            "coverage_gate": "right_tail_visual_orders",
            "required_count": right_tail_required,
            "required_pct": 100.0,
            "accepted_count_or_pct": accepted_right_tail,
            "pass_now": int(right_tail_required > 0 and accepted_right_tail >= right_tail_required),
            "why": "All right-tail visual samples must be covered before any intrabar risk-release rule can be trusted.",
        },
        {
            "coverage_gate": "bottom_loss_visual_orders",
            "required_count": bottom_loss_required,
            "required_pct": 100.0,
            "accepted_count_or_pct": accepted_bottom_loss,
            "pass_now": int(bottom_loss_required > 0 and accepted_bottom_loss >= bottom_loss_required),
            "why": "All bottom-loss samples must be covered to avoid hiding drawdown failures in missing data.",
        },
        {
            "coverage_gate": "maxdd_context_orders",
            "required_count": maxdd_required,
            "required_pct": 100.0,
            "accepted_count_or_pct": 0,
            "pass_now": 0,
            "why": "MaxDD context requires a visual pack from the accepted same-source data, not local Tq/smoke rows.",
        },
    ]
    return pd.DataFrame(rows)


def _negative_evidence() -> pd.DataFrame:
    stage110 = _read_csv(STAGE110_SUMMARY_IN)
    stage111 = _read_csv(STAGE111_SUMMARY_IN)
    stage111_stage932 = _read_csv(STAGE111_STAGE932_IN)

    current_line_tick_files = 0
    for pattern in ["*tick*", "*quote*", "*depth*", "*orderbook*", "*mbo*", "*mbp*"]:
        current_line_tick_files += len(list((LINE_DIR / "outputs").glob(f"**/{pattern}")))
    stage932_tick_files = len(
        list(BACKTEST_OUTPUT_DIR.glob("qmt_roll_stage932_official_live_ctp_smoke_order_ticks_*_stage932_official_live_ctp_smoke_order_v1.csv"))
    )
    stage608_tick_files = len(
        list(BACKTEST_OUTPUT_DIR.glob("qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_*_stage608_readonly_tick_snapshot_probe_v1.csv"))
    )
    rows = [
        {
            "evidence_id": "current_line_tick_named_outputs",
            "observed_count": current_line_tick_files,
            "accepted_for_rule": 0,
            "reason": "historical line artifacts are Tq/downloader/smoke/proxy outputs already downgraded by Stage033/078/079/080/110.",
        },
        {
            "evidence_id": "stage932_ctp_smoke_ticks",
            "observed_count": stage932_tick_files,
            "accepted_for_rule": 0,
            "reason": "Stage111 found existing Stage932 rows are dry-run/read-only or symbol/reference mismatched; format sample only.",
        },
        {
            "evidence_id": "stage608_readonly_tick_probe",
            "observed_count": stage608_tick_files,
            "accepted_for_rule": 0,
            "reason": "read-only forward probe is not authorized historical depth/orderflow and has no C9 signal->order replay join.",
        },
        {
            "evidence_id": "stage110_rule_usable_assets",
            "observed_count": int(stage110.iloc[0].get("rule_usable_asset_count", 0)) if not stage110.empty else 0,
            "accepted_for_rule": 0,
            "reason": "Stage110 already found zero rule-usable local data assets.",
        },
        {
            "evidence_id": "stage111_valid_research_samples",
            "observed_count": int(stage111.iloc[0].get("stage932_valid_research_sample_count", 0)) if not stage111.empty else 0,
            "accepted_for_rule": 0,
            "reason": "Stage111 found zero linked Stage932 research samples.",
        },
        {
            "evidence_id": "stage111_smoke_audit_sessions",
            "observed_count": len(stage111_stage932),
            "accepted_for_rule": 0,
            "reason": "smoke sessions are useful for schema inspection only, not for rule binding.",
        },
    ]
    return pd.DataFrame(rows)


def _acceptance_gate(inventory: pd.DataFrame, files: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    manifest_rows = int(pd.to_numeric(inventory.get("manifest_row_count", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0
    existing_roots = int(pd.to_numeric(inventory.get("root_exists", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0
    basic_pass = int(pd.to_numeric(files.get("basic_intake_pass", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    rule_ready = int(pd.to_numeric(files.get("rule_research_ready", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    schema_ready = int(pd.to_numeric(files.get("schema_ready", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    raw_hash_schema_ready = (
        int(((pd.to_numeric(files.get("raw_sha256_present", 0), errors="coerce").fillna(0) == 1)
            & (pd.to_numeric(files.get("schema_hash_present", 0), errors="coerce").fillna(0) == 1)).sum())
        if not files.empty
        else 0
    )
    license_clear = int(pd.to_numeric(files.get("source_license_clear", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    old_source_count = int(files.get("old_source_marker", pd.Series(dtype=str)).map(_clean).ne("").sum()) if not files.empty else 0
    vendor_count = int(pd.to_numeric(inventory.get("source_vendor_count", 0), errors="coerce").fillna(0).max()) if not inventory.empty else 0
    coverage_pass_count = int(pd.to_numeric(coverage.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not coverage.empty else 0
    rows = [
        {
            "gate_id": "authorized_intake_root_present",
            "observed": str(existing_roots),
            "required": ">=1 root with data drop",
            "pass_now": int(existing_roots > 0 and manifest_rows > 0),
            "severity": "hard",
        },
        {
            "gate_id": "manifest_present",
            "observed": str(manifest_rows),
            "required": ">=1 manifest row",
            "pass_now": int(manifest_rows > 0),
            "severity": "hard",
        },
        {
            "gate_id": "raw_hash_schema_hash_present",
            "observed": str(raw_hash_schema_ready),
            "required": "all accepted rows include raw_file/raw_sha256/schema_hash",
            "pass_now": int(basic_pass > 0 and raw_hash_schema_ready >= basic_pass),
            "severity": "hard",
        },
        {
            "gate_id": "schema_mbo_or_mbp10",
            "observed": str(schema_ready),
            "required": "MBO/L3 or MBP-10/L2 depth schema",
            "pass_now": int(schema_ready > 0 and basic_pass > 0),
            "severity": "hard",
        },
        {
            "gate_id": "source_license_permission_clear",
            "observed": str(license_clear),
            "required": "non-demo, non-smoke, authorized research permission",
            "pass_now": int(license_clear > 0 and license_clear >= basic_pass and basic_pass > 0),
            "severity": "hard",
        },
        {
            "gate_id": "same_source_no_mixed_vendor",
            "observed": str(vendor_count),
            "required": "one declared vendor/source family for a package, or explicit normalized source map",
            "pass_now": int(vendor_count == 1 and basic_pass > 0),
            "severity": "hard",
        },
        {
            "gate_id": "not_tq_smoke_stage932_downgrade",
            "observed": str(old_source_count),
            "required": "0 old Tq/smoke/synthetic markers in accepted package",
            "pass_now": int(basic_pass > 0 and old_source_count == 0),
            "severity": "hard",
        },
        {
            "gate_id": "timestamp_and_tail_coverage",
            "observed": f"{coverage_pass_count}/{len(coverage)}",
            "required": f"{len(coverage)}/{len(coverage)} coverage gates",
            "pass_now": int(len(coverage) > 0 and coverage_pass_count == len(coverage) and basic_pass > 0),
            "severity": "hard",
        },
        {
            "gate_id": "rule_research_ready",
            "observed": str(rule_ready),
            "required": ">=1 data file passes metadata, schema, permission and coverage gates",
            "pass_now": int(rule_ready > 0),
            "severity": "hard",
        },
    ]
    return pd.DataFrame(rows)


def _manifest_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "example_only": 1,
                "dataset_id": "vendor_or_exchange_mbp10_YYYYMMDD_YYYYMMDD",
                "schema_type": "authorized_mbp10_l2",
                "source_vendor": "authorized_vendor_or_exchange",
                "source_license": "research_allowed_contract_id",
                "exchange": "SHFE",
                "symbol": "rb",
                "vt_symbol": "rb2601.SHFE",
                "start_ts": "2026-01-01 21:00:00+08:00",
                "end_ts": "2026-01-02 15:00:00+08:00",
                "timezone": "Asia/Shanghai",
                "calendar_version": "vnpy_cffex_shfe_dce_czce_gfex_YYYYMMDD",
                "data_file": "data/rb2601_mbp10.parquet",
                "raw_file": "raw/rb2601_source.bin",
                "raw_sha256": "required_raw_sha256_hex",
                "schema_hash": "required_schema_hash_hex",
                "query_params": "required_original_query_or_contract",
                "timestamp_ready_order_coverage_pct": 95.0,
                "right_tail_covered_count": "must_equal_stage112_requirement",
                "bottom_loss_covered_count": "must_equal_stage112_requirement",
                "notes": "Do not use Tq smoke, Stage932 smoke, synthetic rows, or unlicensed samples.",
            }
        ]
    )


def _summary(inventory: pd.DataFrame, files: pd.DataFrame, gate: pd.DataFrame, coverage: pd.DataFrame, negative: pd.DataFrame) -> pd.DataFrame:
    stage111 = _read_csv(STAGE111_SUMMARY_IN).iloc[0]
    manifest_rows = int(pd.to_numeric(inventory.get("manifest_row_count", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0
    data_files = int(pd.to_numeric(inventory.get("data_file_count", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0
    basic_pass = int(pd.to_numeric(files.get("basic_intake_pass", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    rule_ready = int(pd.to_numeric(files.get("rule_research_ready", 0), errors="coerce").fillna(0).sum()) if not files.empty else 0
    detected_mbo = int(files.get("detected_schema_type", pd.Series(dtype=str)).map(_clean).eq("authorized_mbo_l3").sum()) if not files.empty else 0
    detected_mbp10 = int(files.get("detected_schema_type", pd.Series(dtype=str)).map(_clean).eq("authorized_mbp10_l2").sum()) if not files.empty else 0
    coverage_pass = int(pd.to_numeric(coverage.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not coverage.empty else 0
    gate_pass = int(pd.to_numeric(gate.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not gate.empty else 0
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage112_authorized_microstructure_data_drop_validator_built_no_data_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "candidate_intake_root_count": len(INTAKE_ROOTS),
                "existing_candidate_intake_root_count": int(pd.to_numeric(inventory.get("root_exists", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0,
                "manifest_file_count": int(pd.to_numeric(inventory.get("manifest_file_count", 0), errors="coerce").fillna(0).sum()) if not inventory.empty else 0,
                "manifest_row_count": manifest_rows,
                "data_file_count": data_files,
                "basic_intake_pass_file_count": basic_pass,
                "rule_ready_data_file_count": rule_ready,
                "accepted_mbo_file_count": detected_mbo,
                "accepted_mbp10_file_count": detected_mbp10,
                "acceptance_gate_count": len(gate),
                "acceptance_gate_pass_count": gate_pass,
                "coverage_gate_count": len(coverage),
                "coverage_gate_pass_count": coverage_pass,
                "negative_evidence_count": len(negative),
                "next_recommended_route": "drop_authorized_mbo_or_mbp10_package_with_manifest_then_rerun_stage112_and_stage111",
                "true_engine_allowed": 0,
                "strategy_feature_usable": int(rule_ready > 0 and gate_pass == len(gate)),
                "end_equity": float(stage111["end_equity"]),
                "total_return_pct": float(stage111["total_return_pct"]),
                "max_drawdown_pct": float(stage111["max_drawdown_pct"]),
                "sharpe": float(stage111["sharpe"]),
                "total_slippage": float(stage111["total_slippage"]),
                "total_trade_count": float(stage111["total_trade_count"]),
                "closed_lot_win_rate_pct": float(stage111["closed_lot_win_rate_pct"]),
                "max_broker10_margin_to_equity_pct": float(stage111["max_broker10_margin_to_equity_pct"]),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, risk: pd.DataFrame) -> None:
    risk = risk.copy()
    risk["official_open_date"] = pd.to_datetime(risk["official_open_date"], errors="coerce").dt.normalize()
    risk = risk.drop(
        columns=[
            column
            for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]
            if column in risk.columns
        ]
    )
    points = _nearest_curve_points(curve, risk["official_open_date"]).reset_index(drop=True)
    risk = risk.sort_values("official_open_date").reset_index(drop=True)
    if len(risk) == len(points):
        risk = pd.concat(
            [risk, points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]],
            axis=1,
        )
    selected = risk[risk["bottom_loss_visual"].eq(1) | risk["right_tail_visual"].eq(1) | risk["maxdd_context"].eq(1)]
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    if not selected.empty:
        for label, group in selected.groupby("risk_route_label"):
            color = "#dc2626" if "blocked" in str(label) else "#0f766e"
            size = np.where(group["bottom_loss_visual"].eq(1), 82, 42)
            edge = np.where(group["right_tail_visual"].eq(1), "#111827", "white")
            for ax, column, scale in [
                (axes[0], "account_equity", 1_000_000),
                (axes[1], "drawdown_pct", 1),
                (axes[2], "broker10_margin_to_equity_pct", 1),
            ]:
                ax.scatter(
                    group["official_open_date"],
                    group[column] / scale,
                    s=size,
                    c=color,
                    edgecolors=edge,
                    linewidths=0.6,
                    alpha=0.82,
                    label=label if ax is axes[0] else None,
                )
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_title("Stage112 official path: authorized microstructure data drop gate remains blocked")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_inventory(inventory: pd.DataFrame) -> None:
    data = inventory.copy()
    labels = data["root_path"].map(lambda value: Path(str(value)).name + "\n" + Path(str(value)).parent.name)
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(12, 5.5))
    width = 0.22
    ax.bar(x - width, data["root_exists"], width=width, color="#64748b", label="root exists")
    ax.bar(x, data["manifest_row_count"], width=width, color="#0369a1", label="manifest rows")
    ax.bar(x + width, data["basic_intake_pass_count"], width=width, color="#16a34a", label="basic pass")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel("count")
    ax.set_title("Stage112 intake roots: no accepted authorized data drop yet")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    if data[["root_exists", "manifest_row_count", "basic_intake_pass_count"]].to_numpy().max() == 0:
        ax.set_ylim(0, 1)
        for idx in x:
            ax.text(idx, 0.08, "missing", ha="center", va="bottom", color="#dc2626", fontsize=9)
    fig.tight_layout()
    fig.savefig(INVENTORY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_gate(gate: pd.DataFrame) -> None:
    data = gate.copy()
    data["blocked"] = 1 - pd.to_numeric(data["pass_now"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.45 * len(data))))
    colors = np.where(data["blocked"].eq(1), "#dc2626", "#16a34a")
    ax.barh(data["gate_id"], data["blocked"], color=colors, alpha=0.88)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("blocked now")
    ax.set_title("Stage112 hard acceptance gates before microstructure rule research")
    for y, row in enumerate(data.itertuples(index=False)):
        ax.text(0.03, y, str(row.observed), color="white", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(SCHEMA_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage(coverage: pd.DataFrame) -> None:
    data = coverage.copy()
    x = np.arange(len(data))
    required = pd.to_numeric(data["required_count"], errors="coerce").fillna(0)
    accepted = pd.to_numeric(data["accepted_count_or_pct"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(x - 0.18, required, width=0.36, color="#64748b", label="required count")
    ax.bar(x + 0.18, accepted, width=0.36, color="#dc2626", label="accepted count/pct")
    ax.set_xticks(x)
    ax.set_xticklabels(data["coverage_gate"], rotation=22, ha="right")
    ax.set_title("Stage112 coverage gates: accepted authorized package coverage remains zero")
    ax.set_ylabel("count or pct")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    inventory: pd.DataFrame,
    files: pd.DataFrame,
    schema: pd.DataFrame,
    gate: pd.DataFrame,
    coverage: pd.DataFrame,
    negative: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage112 authorized microstructure data drop validator",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only intake validator; no strategy rule, no true engine, no A/B, no CTP connection, no order API.",
        "- question: can a new authorized quote/depth/orderflow package be accepted for the current C9 min-risk line?",
        "",
        "## Baseline Path",
        "",
        f"- end equity: `{row['end_equity']:,.2f}`",
        f"- total return: `{row['total_return_pct']:.4f}%`",
        f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe: `{row['sharpe']:.4f}`",
        f"- total slippage: `{row['total_slippage']:,.0f}`",
        f"- total trade count: `{row['total_trade_count']:.0f}`",
        f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## Key Metrics",
        "",
        _md_table(summary),
        "",
        "## Intake Inventory",
        "",
        _md_table(inventory, max_rows=20),
        "",
        "## File Audit",
        "",
        _md_table(files, max_rows=30),
        "",
        "## Required Schema Contract",
        "",
        _md_table(schema.groupby("route_schema", as_index=False).agg(required_column_count=("required_column", "count"), rule_ready_route=("rule_ready_route", "max")), max_rows=20),
        "",
        "## Acceptance Gates",
        "",
        _md_table(gate, max_rows=30),
        "",
        "## Coverage Requirements",
        "",
        _md_table(coverage, max_rows=10),
        "",
        "## Negative Evidence",
        "",
        _md_table(negative, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- official path data-drop gate: `{PATH_CHART_OUT}`",
        f"- inventory chart: `{INVENTORY_CHART_OUT}`",
        f"- schema gate chart: `{SCHEMA_GATE_CHART_OUT}`",
        f"- coverage requirement chart: `{COVERAGE_CHART_OUT}`",
        "",
        "## External Research Judgment",
        "",
        (
            "The accepted intake shape is MBO/L3 or MBP-10/L2 depth with raw provenance. MBO is preferred when queue "
            "position or order-id event reconstruction is required; MBP-10 can support top-of-book/depth imbalance and "
            "impact replay but not full queue identity. Parquet metadata is enough for fast schema validation, but raw "
            "hash and source permission must still be preserved outside the derived files."
        ),
        "",
        "## Judgment",
        "",
        (
            "No authorized package is present under the fixed intake roots. Existing Tq, Stage608 and Stage932 artifacts "
            "remain negative evidence, not strategy data. The line should continue through data drop/import acceptance "
            "only until Stage112 and Stage111 both pass; writing a minute rule before that would be data mining on known "
            "low-resolution or unlinked artifacts."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    risk = _read_csv(STAGE108_RISK_IN)
    inventory, files = _scan_intake_roots(risk)
    schema = _schema_contract()
    coverage = _coverage_requirements(risk, inventory)
    negative = _negative_evidence()
    gate = _acceptance_gate(inventory, files, coverage)
    summary = _summary(inventory, files, gate, coverage, negative)
    manifest_template = _manifest_template()

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(inventory, INVENTORY_OUT)
    _write_csv(files, FILE_AUDIT_OUT)
    _write_csv(schema, SCHEMA_CONTRACT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(coverage, COVERAGE_OUT)
    _write_csv(negative, NEGATIVE_EVIDENCE_OUT)
    _write_csv(manifest_template, MANIFEST_TEMPLATE_OUT)

    _plot_path(curve, risk)
    _plot_inventory(inventory)
    _plot_schema_gate(gate)
    _plot_coverage(coverage)
    _write_report(summary, inventory, files, schema, gate, coverage, negative)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "data_drop_inventory_path": str(INVENTORY_OUT),
        "file_audit_path": str(FILE_AUDIT_OUT),
        "required_schema_contract_path": str(SCHEMA_CONTRACT_OUT),
        "acceptance_gate_path": str(GATE_OUT),
        "coverage_requirements_path": str(COVERAGE_OUT),
        "negative_evidence_path": str(NEGATIVE_EVIDENCE_OUT),
        "sample_manifest_template_path": str(MANIFEST_TEMPLATE_OUT),
        "charts": [str(PATH_CHART_OUT), str(INVENTORY_CHART_OUT), str(SCHEMA_GATE_CHART_OUT), str(COVERAGE_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": int(summary.iloc[0]["strategy_feature_usable"]),
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
