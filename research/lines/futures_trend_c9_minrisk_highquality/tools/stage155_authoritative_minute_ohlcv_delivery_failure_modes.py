from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from jsonschema import Draft202012Validator
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage155"
MODEL_TAG = "stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1"
OUTPUT_PREFIX = "qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage155_authoritative_minute_ohlcv_delivery_failure_modes"
NEGATIVE_DIR = OUTPUT_DIR / "negative_drops"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"

STAGE154_DIR = LINE_DIR / "outputs" / "stage154_authoritative_minute_ohlcv_proof_schema_pack"
STAGE154_PREFIX = "qmt_roll_stage154_c9_minrisk_authoritative_minute_ohlcv_proof_schema_pack"
STAGE154_TAG = "stage154_authoritative_minute_ohlcv_proof_schema_pack_v1"
STAGE154_SUMMARY_IN = STAGE154_DIR / f"{STAGE154_PREFIX}_summary_{STAGE154_TAG}.csv"
STAGE154_PROOF_SCHEMA_IN = STAGE154_DIR / f"{STAGE154_PREFIX}_proof_schema_{STAGE154_TAG}.json"
STAGE154_TEMPLATE_INDEX_IN = STAGE154_DIR / f"{STAGE154_PREFIX}_proof_template_index_{STAGE154_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
REQUEST_CASE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_case_audit_{MODEL_TAG}.csv"
FAILURE_REASON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_reason_matrix_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_failure_mode_status_{MODEL_TAG}.png"
CASE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_blocked_bar_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_role_presence_heatmap_{MODEL_TAG}.png"
REASON_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_reason_heatmap_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

STAGE153_PROOF_REQUIRED_FIELDS = [
    "request_id",
    "vendor_name",
    "vendor_license",
    "dataset_id",
    "query_params",
    "raw_file",
    "raw_sha256",
    "schema_hash",
    "exchange",
    "vt_symbol",
    "request_start_ts",
    "request_end_ts",
    "timezone",
    "session_calendar",
    "no_trade_bar_policy",
    "synthetic_or_adjusted_flag",
]
NORMALIZED_REQUIRED_COLUMNS = [
    "exchange",
    "vt_symbol",
    "bar_start_ts",
    "bar_end_ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
]
FORBIDDEN_PROVENANCE_MARKERS = [
    "synthetic",
    "smoke",
    "fixture",
    "stage131",
    "positive_drop",
    "template_only",
    "<",
]
CASE_SPECS = [
    {
        "case_id": "template_proof_only_all_requests",
        "description": "Copy Stage154 proof templates as if they were delivered proof files; no raw or parquet files.",
        "request_scope": "all",
        "expected_ready_count": 0,
    },
    {
        "case_id": "schema_valid_proof_only_no_files",
        "description": "Provide schema-valid proof JSON only; raw and normalized files are absent.",
        "request_scope": "all",
        "expected_ready_count": 0,
    },
    {
        "case_id": "raw_present_hash_mismatch",
        "description": "Provide raw files and schema-valid proof JSON, but proof raw_sha256 is wrong.",
        "request_scope": "all",
        "expected_ready_count": 0,
    },
    {
        "case_id": "raw_hash_match_invalid_parquet",
        "description": "Raw hash matches proof but normalized file is invalid parquet bytes.",
        "request_scope": "all",
        "expected_ready_count": 0,
    },
    {
        "case_id": "raw_hash_match_zero_row_parquet",
        "description": "Raw hash matches proof and parquet is readable, but row_count is zero.",
        "request_scope": "all",
        "expected_ready_count": 0,
    },
    {
        "case_id": "local_positive_shape_forbidden_marker",
        "description": "One complete local positive-shaped fixture has raw, proof and one-row parquet, but provenance markers must block it.",
        "request_scope": "one",
        "expected_ready_count": 0,
    },
]


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|"))
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_path(case_id: str, expected_path: str) -> Path:
    rel = Path(expected_path)
    if rel.parts and rel.parts[0] == "incoming":
        rel = Path(*rel.parts[1:])
    return NEGATIVE_DIR / case_id / rel


def _valid_proof(row: pd.Series, raw_sha256: str, normalized_sha256: str = "b" * 64, marker_text: str = "") -> dict[str, Any]:
    proof = {
        "request_id": row["request_id"],
        "vendor_name": "authorized_vendor" + marker_text,
        "vendor_license": "license_research_use_20260621",
        "dataset_id": "authoritative_1m_ohlcv",
        "query_params": {
            "symbols": [row["vt_symbol"]],
            "interval": "1m",
            "start_ts": row["request_start_ts"],
            "end_ts": row["request_end_ts"],
            "timezone": "Asia/Shanghai",
            "adjustment": "none",
            "source_endpoint": "vendor_historical_ohlcv_endpoint",
        },
        "raw_file": row["expected_raw_file"],
        "raw_file_size_bytes": 1,
        "raw_sha256": raw_sha256,
        "normalized_file": row["expected_normalized_file"],
        "normalized_sha256": normalized_sha256,
        "schema_hash": "c" * 64,
        "exchange": row["exchange"],
        "vt_symbol": row["vt_symbol"],
        "request_start_ts": row["request_start_ts"],
        "request_end_ts": row["request_end_ts"],
        "timezone": "Asia/Shanghai",
        "session_calendar": {
            "calendar_id": "domestic_futures_v1",
            "trading_day_convention": "night_session_stitched_to_trading_day",
            "night_session_policy": "vendor_declared_and_preserved",
        },
        "no_trade_bar_policy": {
            "policy": "sparse_trade_bars_only",
            "meaning": "absent minute means no trade according to vendor policy",
            "sequence_gap_interpretation": "gaps are audited separately and not treated as alpha",
        },
        "coverage_claims": {
            "required_window_count": int(row["required_window_count"]),
            "right_tail_window_coverage": 1.0,
            "bottom_loss_window_coverage": 1.0,
            "maxdd_window_coverage": 1.0,
            "sequence_gap_count": 0,
            "duplicate_bar_count": 0,
        },
        "synthetic_or_adjusted_flag": False,
        "template_only_not_real_proof": False,
        "operator_notes": "negative case only" + marker_text,
    }
    return proof


def _write_zero_row_parquet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "exchange": pa.array([], type=pa.string()),
            "vt_symbol": pa.array([], type=pa.string()),
            "bar_start_ts": pa.array([], type=pa.string()),
            "bar_end_ts": pa.array([], type=pa.string()),
            "open": pa.array([], type=pa.float64()),
            "high": pa.array([], type=pa.float64()),
            "low": pa.array([], type=pa.float64()),
            "close": pa.array([], type=pa.float64()),
            "volume": pa.array([], type=pa.float64()),
        }
    )
    pq.write_table(table, path)


def _write_one_row_parquet(path: Path, row: pd.Series) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "exchange": pa.array([row["exchange"]], type=pa.string()),
            "vt_symbol": pa.array([row["vt_symbol"]], type=pa.string()),
            "bar_start_ts": pa.array([row["request_start_ts"]], type=pa.string()),
            "bar_end_ts": pa.array([row["request_start_ts"]], type=pa.string()),
            "open": pa.array([1.0], type=pa.float64()),
            "high": pa.array([1.0], type=pa.float64()),
            "low": pa.array([1.0], type=pa.float64()),
            "close": pa.array([1.0], type=pa.float64()),
            "volume": pa.array([1.0], type=pa.float64()),
        }
    )
    pq.write_table(table, path)


def _build_negative_drops(requests: pd.DataFrame, template_index: pd.DataFrame, schema: dict[str, Any]) -> None:
    if NEGATIVE_DIR.exists():
        shutil.rmtree(NEGATIVE_DIR)
    template_path_by_request = template_index.set_index("request_id")["template_path"].to_dict()
    validator = Draft202012Validator(schema)
    for _, case in enumerate(CASE_SPECS):
        case_id = case["case_id"]
        case_requests = requests.head(1) if case["request_scope"] == "one" else requests
        for _, row in case_requests.iterrows():
            raw_path = _case_path(case_id, row["expected_raw_file"])
            norm_path = _case_path(case_id, row["expected_normalized_file"])
            proof_path = _case_path(case_id, row["expected_proof_file"])
            if case_id == "template_proof_only_all_requests":
                payload = _load_json(Path(template_path_by_request[row["request_id"]]))
                _write_json(proof_path, payload)
                continue
            raw_payload = f"{case_id}:{row['request_id']}".encode("utf-8")
            raw_sha = hashlib.sha256(raw_payload).hexdigest()
            if case_id != "schema_valid_proof_only_no_files":
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw_payload)
            if case_id == "raw_present_hash_mismatch":
                proof = _valid_proof(row, "a" * 64)
            elif case_id == "local_positive_shape_forbidden_marker":
                _write_one_row_parquet(norm_path, row)
                norm_sha = _sha256(norm_path)
                proof = _valid_proof(row, raw_sha, norm_sha, marker_text="_fixture")
            else:
                if case_id == "raw_hash_match_invalid_parquet":
                    norm_path.parent.mkdir(parents=True, exist_ok=True)
                    norm_path.write_bytes(b"not a parquet file")
                elif case_id == "raw_hash_match_zero_row_parquet":
                    _write_zero_row_parquet(norm_path)
                proof = _valid_proof(row, raw_sha)
            # Keep this as an internal assertion so broken selftests fail loudly.
            if case_id in {"schema_valid_proof_only_no_files", "raw_present_hash_mismatch", "raw_hash_match_invalid_parquet", "raw_hash_match_zero_row_parquet", "local_positive_shape_forbidden_marker"}:
                errors = sorted(validator.iter_errors(proof), key=lambda error: list(error.path))
                if errors:
                    raise RuntimeError(f"{case_id} generated invalid proof for {row['request_id']}: {errors[0].message}")
            _write_json(proof_path, proof)


def _string_values(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        values: list[str] = []
        for item in payload.values():
            values.extend(_string_values(item))
        return values
    if isinstance(payload, list):
        values = []
        for item in payload:
            values.extend(_string_values(item))
        return values
    return [payload] if isinstance(payload, str) else []


def _forbidden_marker_count(payload: dict[str, Any], paths: list[Path]) -> tuple[int, str]:
    text = " ".join(_string_values(payload)).lower()
    text += " " + " ".join(str(path).lower() for path in paths)
    hits = [marker for marker in FORBIDDEN_PROVENANCE_MARKERS if marker in text]
    return len(hits), ",".join(hits)


def _audit_one_request(case_id: str, row: pd.Series, schema: dict[str, Any]) -> dict[str, Any]:
    raw_path = _case_path(case_id, row["expected_raw_file"])
    norm_path = _case_path(case_id, row["expected_normalized_file"])
    proof_path = _case_path(case_id, row["expected_proof_file"])
    proof_payload: dict[str, Any] = {}
    proof_json_valid = 0
    if proof_path.exists():
        try:
            proof_payload = _load_json(proof_path)
            proof_json_valid = int(isinstance(proof_payload, dict))
        except Exception:
            proof_payload = {}
            proof_json_valid = 0
    validator = Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(proof_payload), key=lambda error: list(error.path)) if proof_json_valid else []
    proof_schema_valid = int(proof_json_valid == 1 and len(schema_errors) == 0)
    present_fields = [field for field in STAGE153_PROOF_REQUIRED_FIELDS if proof_payload.get(field) not in (None, "", [])]
    missing_fields = [field for field in STAGE153_PROOF_REQUIRED_FIELDS if field not in present_fields]
    raw_sha = _sha256(raw_path) if raw_path.exists() else ""
    start = pd.to_datetime(proof_payload.get("request_start_ts"), errors="coerce")
    end = pd.to_datetime(proof_payload.get("request_end_ts"), errors="coerce")
    expected_start = pd.to_datetime(row.get("request_start_ts"), errors="coerce")
    expected_end = pd.to_datetime(row.get("request_end_ts"), errors="coerce")
    marker_count, markers = _forbidden_marker_count(proof_payload, [raw_path, norm_path, proof_path])
    synthetic_flag = proof_payload.get("synthetic_or_adjusted_flag")
    synthetic_clean = int(str(synthetic_flag).strip().lower() in {"0", "false", "no", "clean"})
    parquet_readable = 0
    row_count = 0
    missing_columns = NORMALIZED_REQUIRED_COLUMNS.copy()
    normalized_schema_pass = 0
    if norm_path.exists():
        try:
            parquet_file = pq.ParquetFile(norm_path)
            columns = list(parquet_file.schema.names)
            row_count = int(parquet_file.metadata.num_rows)
            parquet_readable = 1
            missing_columns = [column for column in NORMALIZED_REQUIRED_COLUMNS if column not in columns]
            normalized_schema_pass = int(len(missing_columns) == 0 and row_count > 0)
        except Exception:
            parquet_readable = 0
    stage153_ready = int(
        raw_path.exists()
        and proof_json_valid == 1
        and len(present_fields) == len(STAGE153_PROOF_REQUIRED_FIELDS)
        and str(proof_payload.get("request_id", "")) == str(row["request_id"])
        and str(proof_payload.get("exchange", "")) == str(row["exchange"])
        and str(proof_payload.get("vt_symbol", "")) == str(row["vt_symbol"])
        and pd.notna(start)
        and pd.notna(end)
        and start <= expected_start
        and end >= expected_end
        and bool(raw_sha)
        and str(proof_payload.get("raw_sha256", "")).lower() == raw_sha
        and bool(str(proof_payload.get("no_trade_bar_policy", "")).strip())
        and synthetic_clean == 1
        and marker_count == 0
        and normalized_schema_pass == 1
    )
    return {
        "case_id": case_id,
        "request_id": row["request_id"],
        "exchange": row["exchange"],
        "product": row["product"],
        "vt_symbol": row["vt_symbol"],
        "raw_file_present": int(raw_path.exists()),
        "proof_file_present": int(proof_path.exists()),
        "normalized_file_present": int(norm_path.exists()),
        "proof_json_valid": proof_json_valid,
        "proof_schema_valid": proof_schema_valid,
        "proof_schema_error_count": len(schema_errors),
        "stage153_required_field_present_count": len(present_fields),
        "stage153_missing_fields": ",".join(missing_fields),
        "identity_match": int(
            str(proof_payload.get("request_id", "")) == str(row["request_id"])
            and str(proof_payload.get("exchange", "")) == str(row["exchange"])
            and str(proof_payload.get("vt_symbol", "")) == str(row["vt_symbol"])
        ),
        "time_span_cover_request": int(
            pd.notna(start)
            and pd.notna(end)
            and pd.notna(expected_start)
            and pd.notna(expected_end)
            and start <= expected_start
            and end >= expected_end
        ),
        "raw_sha256_match": int(bool(raw_sha) and str(proof_payload.get("raw_sha256", "")).lower() == raw_sha),
        "no_trade_policy_declared": int(bool(str(proof_payload.get("no_trade_bar_policy", "")).strip())),
        "synthetic_or_adjusted_flag_clean": synthetic_clean,
        "forbidden_marker_count": marker_count,
        "forbidden_markers": markers,
        "parquet_readable": parquet_readable,
        "parquet_row_count": row_count,
        "normalized_required_column_missing_count": len(missing_columns),
        "normalized_schema_pass": normalized_schema_pass,
        "stage153_request_ready": stage153_ready,
        "strategy_rule_allowed": 0,
    }


def _audit_negative_drops(requests: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for case in CASE_SPECS:
        case_requests = requests.head(1) if case["request_scope"] == "one" else requests
        for _, row in case_requests.iterrows():
            records.append(_audit_one_request(case["case_id"], row, schema))
    return pd.DataFrame(records)


def _case_summary(audit: pd.DataFrame) -> pd.DataFrame:
    case_meta = pd.DataFrame(CASE_SPECS)
    grouped = (
        audit.groupby("case_id", dropna=False)
        .agg(
            audited_request_count=("request_id", "count"),
            raw_file_present_count=("raw_file_present", "sum"),
            proof_file_present_count=("proof_file_present", "sum"),
            normalized_file_present_count=("normalized_file_present", "sum"),
            proof_schema_valid_count=("proof_schema_valid", "sum"),
            raw_sha256_match_count=("raw_sha256_match", "sum"),
            parquet_readable_count=("parquet_readable", "sum"),
            normalized_schema_pass_count=("normalized_schema_pass", "sum"),
            forbidden_marker_request_count=("forbidden_marker_count", lambda s: int((s > 0).sum())),
            stage153_request_ready_count=("stage153_request_ready", "sum"),
            strategy_rule_allowed_count=("strategy_rule_allowed", "sum"),
        )
        .reset_index()
    )
    result = case_meta.merge(grouped, on="case_id", how="left")
    result["observed_blocked_count"] = result["audited_request_count"] - result["stage153_request_ready_count"]
    result["expected_ready_count"] = pd.to_numeric(result["expected_ready_count"], errors="coerce").fillna(0).astype(int)
    result["expectation_pass"] = result["stage153_request_ready_count"].eq(result["expected_ready_count"]).astype(int)
    return result


def _failure_reason_matrix(audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    reason_map = {
        "missing_raw": audit["raw_file_present"].eq(0),
        "missing_proof": audit["proof_file_present"].eq(0),
        "missing_normalized": audit["normalized_file_present"].eq(0),
        "proof_schema_invalid": audit["proof_schema_valid"].eq(0),
        "raw_sha_mismatch": audit["raw_sha256_match"].eq(0),
        "parquet_unreadable": audit["normalized_file_present"].eq(1) & audit["parquet_readable"].eq(0),
        "zero_or_bad_parquet_schema": audit["normalized_file_present"].eq(1) & audit["normalized_schema_pass"].eq(0),
        "forbidden_marker": audit["forbidden_marker_count"].gt(0),
        "stage153_ready_unexpected": audit["stage153_request_ready"].eq(1),
    }
    for case_id, case_frame in audit.groupby("case_id", dropna=False):
        for reason, mask in reason_map.items():
            rows.append(
                {
                    "case_id": case_id,
                    "reason": reason,
                    "request_count": int(len(case_frame)),
                    "hit_count": int(mask.loc[case_frame.index].sum()),
                    "hit_ratio": float(mask.loc[case_frame.index].mean()) if len(case_frame) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("negative_case_count", summary["case_count"], len(CASE_SPECS), "selftest_hard"),
        ("case_expectation_pass_count", summary["case_expectation_pass_count"], summary["case_count"], "selftest_hard"),
        ("unexpected_ready_count", summary["unexpected_ready_count"], 0, "intake_hard"),
        ("strategy_rule_allowed_count", summary["strategy_rule_allowed_count"], 0, "strategy_hard"),
        ("stage153_feature_build_allowed", summary["stage153_feature_build_allowed"], 0, "downstream_hard"),
        ("fixture_written_under_incoming", summary["negative_drop_written_under_incoming"], 0, "filesystem_hard"),
        ("official_config_changed", summary["official_config_changed"], 0, "execution_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("side_effect_count", summary["side_effect_count"], 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    cases: pd.DataFrame,
    failure_reasons: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 权威分钟 OHLCV 交付负例审计",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只构造隔离负例审计到货闸门，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- JSON Schema 能校验结构，但不能证明数据真实；因此 schema-valid proof-only 仍必须被 raw/parquet/hash/coverage gate 阻断。",
        "- Apache Parquet metadata 可读和 row count 可作为验收输入；可读但零行的 parquet 不是可研究分钟数据。",
        "- NIST FIPS 180-4 说明 SHA-256 可用于检测文件是否变化；hash 匹配只证明文件一致，不证明 vendor provenance 或 no-trade policy。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Case Summary",
        "",
        _md_table(cases),
        "",
        "## Failure Reason Matrix",
        "",
        _md_table(failure_reasons),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CASE_CHART_OUT.name}`",
        f"- `{ROLE_CHART_OUT.name}`",
        f"- `{REASON_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage155 delivery failure modes on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["cases", "audits", "unexpected_ready", "expect_pass", "rule", "engine"]
    values = [
        row["case_count"],
        row["request_case_audit_count"],
        row["unexpected_ready_count"],
        row["case_expectation_pass_count"],
        row["strategy_rule_created"],
        row["true_engine_run"],
    ]
    colors = ["#3657D6", "#0F766E", "#B91C1C", "#0F766E", "#111827", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("All negative delivery shapes remain blocked")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_blocked(cases: pd.DataFrame) -> None:
    data = cases.sort_values("audited_request_count", ascending=True)
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.barh(data["case_id"], data["observed_blocked_count"], color="#0F766E", label="blocked")
    ax.barh(data["case_id"], data["stage153_request_ready_count"], color="#B91C1C", label="unexpected ready")
    ax.set_title("Stage155 negative cases: blocked vs unexpected ready")
    ax.set_xlabel("request count")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    for i, (_, row) in enumerate(data.iterrows()):
        ax.text(row["observed_blocked_count"] + 0.5, i, f"{int(row['observed_blocked_count'])}/{int(row['audited_request_count'])}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(CASE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_role_heatmap(cases: pd.DataFrame) -> None:
    cols = [
        "raw_file_present_count",
        "proof_file_present_count",
        "normalized_file_present_count",
        "proof_schema_valid_count",
        "normalized_schema_pass_count",
        "stage153_request_ready_count",
    ]
    matrix = cases.set_index("case_id")[cols].copy()
    fig, ax = plt.subplots(figsize=(13, 6.5))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Delivery role presence by negative case")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_reason_heatmap(failure_reasons: pd.DataFrame) -> None:
    matrix = failure_reasons.pivot(index="case_id", columns="reason", values="hit_ratio").fillna(0)
    fig, ax = plt.subplots(figsize=(13, 6.8))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1)
    ax.set_title("Failure reason hit ratio by negative case")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, f"{data[row, col]:.0%}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(REASON_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate_matrix(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]].copy()
    fig, ax = plt.subplots(figsize=(8.5, max(5.0, len(matrix) * 0.5)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage155 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        ax.text(0, row, int(data[row, 0]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    requests = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    template_index = _read_csv(STAGE154_TEMPLATE_INDEX_IN)
    stage153 = _row(STAGE153_SUMMARY_IN)
    stage154 = _row(STAGE154_SUMMARY_IN)
    if requests.empty or template_index.empty or not stage153 or not stage154:
        raise RuntimeError("missing Stage152/153/154 inputs")
    schema = _load_json(STAGE154_PROOF_SCHEMA_IN)
    _build_negative_drops(requests, template_index, schema)
    request_case_audit = _audit_negative_drops(requests, schema)
    cases = _case_summary(request_case_audit)
    failure_reasons = _failure_reason_matrix(request_case_audit)
    decision = "stage155_authoritative_minute_ohlcv_negative_delivery_shapes_blocked_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "deliver_real_authoritative_minute_ohlcv_package_or_build_stage156_operator_release_verdict",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_feature_build_allowed": _int(stage153, "stage154_feature_build_allowed"),
        "stage154_template_count": _int(stage154, "proof_template_count"),
        "case_count": int(len(cases)),
        "request_case_audit_count": int(len(request_case_audit)),
        "case_expectation_pass_count": int(cases["expectation_pass"].sum()),
        "unexpected_ready_count": int(request_case_audit["stage153_request_ready"].sum()),
        "strategy_rule_allowed_count": int(request_case_audit["strategy_rule_allowed"].sum()),
        "proof_schema_valid_request_count": int(request_case_audit["proof_schema_valid"].sum()),
        "normalized_schema_pass_request_count": int(request_case_audit["normalized_schema_pass"].sum()),
        "forbidden_marker_request_count": int((request_case_audit["forbidden_marker_count"] > 0).sum()),
        "negative_drop_written_under_incoming": int(str(NEGATIVE_DIR.resolve()).startswith(str((REPO_DIR / "incoming").resolve()))),
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage153.get("end_equity", np.nan)),
        "total_return_pct": float(stage153.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage153.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage153.get("sharpe", np.nan)),
        "total_slippage": float(stage153.get("total_slippage", np.nan)),
        "total_trade_count": float(stage153.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage153.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage153.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(cases, CASE_SUMMARY_OUT)
    _write_csv(request_case_audit, REQUEST_CASE_AUDIT_OUT)
    _write_csv(failure_reasons, FAILURE_REASON_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, cases, failure_reasons, gate)
    _plot_path(curve, summary)
    _plot_case_blocked(cases)
    _plot_role_heatmap(cases)
    _plot_reason_heatmap(failure_reasons)
    _plot_gate_matrix(gate)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage152_request_manifest_template": str(STAGE152_REQUEST_TEMPLATE_IN),
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage154_summary": str(STAGE154_SUMMARY_IN),
                "stage154_proof_schema": str(STAGE154_PROOF_SCHEMA_IN),
                "stage154_template_index": str(STAGE154_TEMPLATE_INDEX_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_summary": str(CASE_SUMMARY_OUT),
                "request_case_audit": str(REQUEST_CASE_AUDIT_OUT),
                "failure_reason_matrix": str(FAILURE_REASON_OUT),
                "gate_status": str(GATE_OUT),
                "negative_drop_dir": str(NEGATIVE_DIR),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CASE_CHART_OUT),
                    str(ROLE_CHART_OUT),
                    str(REASON_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://json-schema.org/docs",
                "https://parquet.apache.org/docs/file-format/metadata/",
                "https://csrc.nist.gov/pubs/fips/180-4/upd1/final",
            ],
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
