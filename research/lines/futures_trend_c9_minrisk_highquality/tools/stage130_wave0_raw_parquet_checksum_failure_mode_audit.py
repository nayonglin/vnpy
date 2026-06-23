from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage130"
MODEL_TAG = "stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage130_wave0_raw_parquet_checksum_failure_mode_audit"
BAD_DROP_ROOT = OUTPUT_DIR / "bad_drops"

STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE126_DIR = LINE_DIR / "outputs" / "stage126_wave0_proof_json_schema_package"
STAGE126_SCHEMA_IN = (
    STAGE126_DIR
    / "qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_schema_"
    "stage126_wave0_proof_json_schema_package_v1.json"
)
STAGE120_CONTRACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage120_wave0_schema_contract_audit"
    / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_canonical_field_contract_"
    "stage120_wave0_schema_contract_audit_v1.csv"
)

STAGE128_TOOL = LINE_DIR / "tools" / "stage128_wave0_full_intake_supergate.py"
STAGE128_OUT_DIR = LINE_DIR / "outputs" / "stage128_wave0_full_intake_supergate"
STAGE128_PREFIX = "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate"
STAGE128_MODEL = "stage128_wave0_full_intake_supergate_v1"
STAGE128_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_summary_{STAGE128_MODEL}.csv"
STAGE128_CASE_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_case_summary_{STAGE128_MODEL}.csv"
STAGE128_STEP_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_step_summary_{STAGE128_MODEL}.csv"
STAGE128_GATE_STATUS = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_supergate_status_{STAGE128_MODEL}.csv"
STAGE128_REQUEST_AUDIT = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_request_supergate_audit_{STAGE128_MODEL}.csv"
STAGE128_STAGE123_GATE_DETAIL = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_stage123_gate_detail_{STAGE128_MODEL}.csv"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_case_summary_{MODEL_TAG}.csv"
STEP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_step_summary_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_gate_status_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_request_audit_{MODEL_TAG}.csv"
STAGE123_GATE_DETAIL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage123_gate_detail_{MODEL_TAG}.csv"
INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_drop_file_inventory_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_expectation_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_raw_parquet_failure_status_{MODEL_TAG}.png"
CASE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_parquet_supergate_matrix_{MODEL_TAG}.png"
EXPECTATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expected_vs_observed_raw_parquet_failures_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_receipt_failure_matrix_{MODEL_TAG}.png"

MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"
DECISION = "stage130_raw_parquet_checksum_failure_modes_blocked_no_strategy"


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
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage128 = _read_csv(STAGE128_SUMMARY)
    if not stage128.empty:
        row = stage128.iloc[0]
        return {
            "end_equity": float(row.get("end_equity", np.nan)),
            "total_return_pct": float(row.get("total_return_pct", np.nan)),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", np.nan)),
            "sharpe": float(row.get("sharpe", np.nan)),
            "total_slippage": float(row.get("total_slippage", np.nan)),
            "total_trade_count": float(row.get("total_trade_count", np.nan)),
            "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
            "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", np.nan)),
        }
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
    return {
        "end_equity": end_equity,
        "total_return_pct": (end_equity / first_equity - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _delivery_contract() -> pd.DataFrame:
    contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    if contract.empty:
        raise RuntimeError(f"missing Stage124 delivery contract: {STAGE124_FILE_CONTRACT_IN}")
    rows = []
    for request_id, group in contract.groupby("request_id"):
        roles = group.set_index("artifact_role")
        proof = roles.loc["proof"]
        raw_rel = _clean(roles.loc["raw", "recommended_relative_path"]).replace("<vendor_raw_ext>", "raw")
        parquet_rel = _clean(roles.loc["normalized_parquet", "recommended_relative_path"])
        proof_rel = _clean(proof["recommended_relative_path"])
        rows.append(
            {
                "request_id": request_id,
                "batch_id": _clean(proof["batch_id"]),
                "exchange": _clean(proof["exchange"]),
                "product": _clean(proof["product"]),
                "vt_symbol": _clean(proof["vt_symbol"]),
                "trading_day": pd.to_datetime(proof["trading_day"], errors="coerce"),
                "request_start": pd.to_datetime(proof["request_start"], errors="coerce"),
                "request_end": pd.to_datetime(proof["request_end"], errors="coerce"),
                "required_schema_request": _clean(proof["required_schema_request"]),
                "raw_relative_path": raw_rel,
                "parquet_relative_path": parquet_rel,
                "proof_relative_path": proof_rel,
            }
        )
    result = pd.DataFrame(rows).sort_values(["trading_day", "request_id"]).reset_index(drop=True)
    if len(result) != 41:
        raise RuntimeError(f"expected 41 W0 requests, got {len(result)}")
    return result


def _schema_contract() -> pd.DataFrame:
    contract = _read_csv(STAGE120_CONTRACT_IN)
    if contract.empty:
        raise RuntimeError(f"missing Stage120 schema contract: {STAGE120_CONTRACT_IN}")
    return contract


def _required_fields(row: pd.Series, contract: pd.DataFrame, mode: str) -> list[str]:
    if mode == "missing_universal":
        return ["sequence", "dummy_depth_proxy"]
    if mode == "missing_canonical_depth":
        return ["ts_event", "ts_recv", "sequence"]
    required_column = "required_for_mbo" if _clean(row["required_schema_request"]) == MBO else "required_for_mbp10"
    return contract.loc[contract[required_column].eq(1), "canonical_field"].astype(str).tolist()


def _array_for_field(field: str, row: pd.Series, row_count: int) -> pa.Array:
    if row_count <= 0:
        if field in {"ts_event", "ts_recv"}:
            return pa.array([], type=pa.timestamp("ns"))
        if field in {"action", "side", "order_id", "dummy_depth_proxy"}:
            return pa.array([], type=pa.string())
        if "price" in field or field == "price":
            return pa.array([], type=pa.float64())
        return pa.array([], type=pa.int64())
    if field == "ts_event":
        values = [pd.Timestamp(row["request_start"]).to_pydatetime()]
        return pa.array(values, type=pa.timestamp("ns"))
    if field == "ts_recv":
        values = [(pd.Timestamp(row["request_start"]) + pd.Timedelta(milliseconds=10)).to_pydatetime()]
        return pa.array(values, type=pa.timestamp("ns"))
    if field == "action":
        return pa.array(["add"], type=pa.string())
    if field == "side":
        return pa.array(["bid"], type=pa.string())
    if field == "order_id":
        return pa.array([f"{_clean(row['request_id'])}_order_1"], type=pa.string())
    if field == "dummy_depth_proxy":
        return pa.array(["not_a_canonical_market_depth_field"], type=pa.string())
    if "price" in field or field == "price":
        return pa.array([100.0], type=pa.float64())
    return pa.array([1], type=pa.int64())


def _write_parquet(path: Path, row: pd.Series, fields: list[str], row_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = [_array_for_field(field, row, row_count) for field in fields]
    table = pa.table(arrays, names=fields)
    pq.write_table(table, path)


def _write_raw(path: Path, row: pd.Series, case_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        f"stage130 local bad-drop raw bytes\n"
        f"case_id={case_id}\n"
        f"request_id={_clean(row['request_id'])}\n"
        f"vt_symbol={_clean(row['vt_symbol'])}\n"
        f"request_start={pd.Timestamp(row['request_start']).strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    path.write_bytes(payload.encode("utf-8"))


def _proof_payload(row: pd.Series, raw_path: Path, parquet_path: Path, row_count_claim: int = 1) -> dict[str, Any]:
    return {
        "request_id": _clean(row["request_id"]),
        "batch_id": _clean(row["batch_id"]),
        "vt_symbol": _clean(row["vt_symbol"]),
        "required_schema_request": _clean(row["required_schema_request"]),
        "vendor": "authorized_research_feed_vendor",
        "license_id": "research_license_contract_001",
        "dataset": "authorized_depth_feed_w0_v1",
        "schema_hash": _sha256_text(_clean(row["required_schema_request"]))[:64],
        "field_dictionary_version": "stage120_canonical_contract_v1",
        "ts_event_timezone": "Asia/Shanghai",
        "ts_recv_timezone": "Asia/Shanghai",
        "first_ts_event": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S"),
        "last_ts_event": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": row_count_claim,
        "sequence_gap_count": 0,
        "capture_continuity_proof": "continuity_audit_packet_001",
        "synthetic_fixture": False,
        "raw_sha256": _sha256_file(raw_path) if raw_path.exists() else "b" * 64,
        "normalized_parquet_sha256": _sha256_file(parquet_path) if parquet_path.exists() else "c" * 64,
        "proof_created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template_only_not_real_proof": False,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_case(
    case: dict[str, Any],
    requests: pd.DataFrame,
    contract: pd.DataFrame,
) -> list[dict[str, Any]]:
    case_id = case["failure_case_id"]
    drop_dir = BAD_DROP_ROOT / case_id
    _reset_dir(drop_dir)
    checksum_lines = []
    inventory_rows = []
    for _, row in requests.iterrows():
        raw_path = drop_dir / _clean(row["raw_relative_path"])
        parquet_path = drop_dir / _clean(row["parquet_relative_path"])
        proof_path = drop_dir / _clean(row["proof_relative_path"])
        _write_raw(raw_path, row, case_id)
        parquet_mode = case.get("parquet_mode", "complete")
        parquet_row_count = int(case.get("parquet_row_count", 1))
        if parquet_mode == "invalid_bytes":
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_path.write_text("not a parquet file\n", encoding="utf-8")
        else:
            fields = _required_fields(row, contract, parquet_mode)
            _write_parquet(parquet_path, row, fields, parquet_row_count)
        proof = _proof_payload(row, raw_path, parquet_path, row_count_claim=int(case.get("proof_row_count", 1)))
        _write_json(proof_path, proof)
        if case_id == "duplicate_raw_role_drop":
            duplicate_path = raw_path.with_name(raw_path.name.replace("__raw.raw", "__raw_duplicate.raw"))
            _write_raw(duplicate_path, row, case_id)
            inventory_rows.append(
                {
                    "failure_case_id": case_id,
                    "request_id": _clean(row["request_id"]),
                    "artifact_role": "raw_duplicate",
                    "path": str(duplicate_path),
                    "bytes": int(duplicate_path.stat().st_size),
                    "sha256": _sha256_file(duplicate_path),
                }
            )
        digest = "0" * 64 if case_id == "checksum_digest_mismatch_drop" else _sha256_file(raw_path)
        checksum_lines.append(f"{digest}  {_clean(row['raw_relative_path'])}")
        for role, path in [("raw", raw_path), ("normalized_parquet", parquet_path), ("proof", proof_path)]:
            inventory_rows.append(
                {
                    "failure_case_id": case_id,
                    "request_id": _clean(row["request_id"]),
                    "artifact_role": role,
                    "path": str(path),
                    "bytes": int(path.stat().st_size),
                    "sha256": _sha256_file(path),
                }
            )
    checksum_path = drop_dir / "SHA256SUMS"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    inventory_rows.append(
        {
            "failure_case_id": case_id,
            "request_id": "",
            "artifact_role": "checksum_manifest",
            "path": str(checksum_path),
            "bytes": int(checksum_path.stat().st_size),
            "sha256": _sha256_file(checksum_path),
        }
    )
    case["drop_dir"] = str(drop_dir)
    return inventory_rows


def _case_specs() -> list[dict[str, Any]]:
    return [
        {
            "failure_case_id": "checksum_digest_mismatch_drop",
            "failure_mode": "raw/parquet/proof complete, but SHA256SUMS digests do not match raw bytes",
            "expected_stage125_ready_for_stage123": 0,
            "expected_stage117_stage112_intake": 1,
            "expected_stage120_real_schema_contract_pass": 1,
            "expected_stage123_final_stage112_ready_count": 1,
            "expected_full_supergate_ready": 0,
        },
        {
            "failure_case_id": "duplicate_raw_role_drop",
            "failure_mode": "raw/parquet/proof complete, but each request has duplicate raw role files",
            "expected_stage125_ready_for_stage123": 0,
            "expected_stage117_stage112_intake": 1,
            "expected_stage120_real_schema_contract_pass": 1,
            "expected_stage123_final_stage112_ready_count": 1,
            "expected_full_supergate_ready": 0,
        },
        {
            "failure_case_id": "invalid_parquet_bytes_drop",
            "failure_mode": "parquet role files exist but are not readable Parquet",
            "parquet_mode": "invalid_bytes",
            "expected_stage125_ready_for_stage123": 1,
            "expected_stage117_stage112_intake": 0,
            "expected_stage120_real_schema_contract_pass": 0,
            "expected_stage123_final_stage112_ready_count": 0,
            "expected_full_supergate_ready": 0,
        },
        {
            "failure_case_id": "parquet_missing_universal_fields_drop",
            "failure_mode": "readable Parquet lacks ts_event and ts_recv",
            "parquet_mode": "missing_universal",
            "expected_stage125_ready_for_stage123": 1,
            "expected_stage117_stage112_intake": 0,
            "expected_stage120_real_schema_contract_pass": 0,
            "expected_stage123_final_stage112_ready_count": 0,
            "expected_full_supergate_ready": 0,
        },
        {
            "failure_case_id": "parquet_missing_canonical_depth_fields_drop",
            "failure_mode": "readable Parquet has universal timestamps but lacks MBP/MBO canonical depth fields",
            "parquet_mode": "missing_canonical_depth",
            "expected_stage125_ready_for_stage123": 1,
            "expected_stage117_stage112_intake": 1,
            "expected_stage120_real_schema_contract_pass": 0,
            "expected_stage123_final_stage112_ready_count": 0,
            "expected_full_supergate_ready": 0,
        },
        {
            "failure_case_id": "zero_row_schema_complete_drop",
            "failure_mode": "schema-complete Parquet has zero physical rows while proof claims row_count>0",
            "parquet_row_count": 0,
            "proof_row_count": 1,
            "expected_stage125_ready_for_stage123": 1,
            "expected_stage117_stage112_intake": 0,
            "expected_stage120_real_schema_contract_pass": 1,
            "expected_stage123_final_stage112_ready_count": 0,
            "expected_full_supergate_ready": 0,
        },
    ]


def _build_bad_drops() -> tuple[list[dict[str, Any]], pd.DataFrame]:
    _reset_dir(BAD_DROP_ROOT)
    requests = _delivery_contract()
    contract = _schema_contract()
    cases = _case_specs()
    inventory_rows = []
    for case in cases:
        inventory_rows.extend(_build_case(case, requests, contract))
    return cases, pd.DataFrame(inventory_rows)


def _run_stage128(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    command = [
        sys.executable,
        str(STAGE128_TOOL),
        "--drop-dir",
        str(case["drop_dir"]),
        "--expected-stage112-intake",
        "0",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
    )
    frames = {
        "summary": _read_csv(STAGE128_SUMMARY),
        "case_summary": _read_csv(STAGE128_CASE_SUMMARY),
        "step_summary": _read_csv(STAGE128_STEP_SUMMARY),
        "gates": _read_csv(STAGE128_GATE_STATUS),
        "request_audit": _read_csv(STAGE128_REQUEST_AUDIT),
        "stage123_gate_detail": _read_csv(STAGE128_STAGE123_GATE_DETAIL),
    }
    for frame in frames.values():
        if not frame.empty:
            frame.insert(0, "failure_case_id", case["failure_case_id"])
            frame.insert(1, "failure_mode", case["failure_mode"])
    run_row = {
        "failure_case_id": case["failure_case_id"],
        "failure_mode": case["failure_mode"],
        "stage128_command": " ".join(command),
        "stage128_returncode": int(completed.returncode),
        "stage128_stdout_tail": completed.stdout[-500:],
        "stage128_stderr_tail": completed.stderr[-500:],
    }
    return run_row, frames


def _restore_stage128_default() -> dict[str, Any]:
    command = [sys.executable, str(STAGE128_TOOL)]
    completed = subprocess.run(
        command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
    )
    restored_summary = _read_csv(STAGE128_SUMMARY)
    restored_case_summary = _read_csv(STAGE128_CASE_SUMMARY)
    restored = int(
        completed.returncode == 0
        and not restored_summary.empty
        and int(restored_summary.iloc[0].get("cli_mode", -1)) == 0
        and int(restored_summary.iloc[0].get("negative_selftest_pass", 0)) == 1
        and int(restored_summary.iloc[0].get("stage123_125_127_default_restored", 0)) == 1
        and not restored_case_summary.empty
        and set(restored_case_summary["entry_case_id"].astype(str)) == {"empty_drop_supergate", "synthetic_fixture_supergate"}
    )
    return {
        "stage128_default_restore_returncode": int(completed.returncode),
        "stage128_default_restore_stdout_tail": completed.stdout[-500:],
        "stage128_default_restore_stderr_tail": completed.stderr[-500:],
        "stage128_default_restored": restored,
    }


def _gate_observed(stage123_gate_detail: pd.DataFrame, case_id: str, gate_id: str) -> int:
    if stage123_gate_detail.empty:
        return 0
    rows = stage123_gate_detail[
        stage123_gate_detail["failure_case_id"].astype(str).eq(case_id)
        & stage123_gate_detail["gate_id"].astype(str).eq(gate_id)
        & stage123_gate_detail["stage_step"].astype(str).eq("chain")
    ]
    if rows.empty:
        return 0
    return int(pd.to_numeric(rows.iloc[0]["observed"], errors="coerce"))


def _expectation_frame(cases: list[dict[str, Any]], case_summary: pd.DataFrame, stage123_gate_detail: pd.DataFrame) -> pd.DataFrame:
    expectation = pd.DataFrame(cases)
    rows = []
    for case_id in expectation["failure_case_id"]:
        case_rows = case_summary[case_summary["failure_case_id"].astype(str).eq(case_id)] if not case_summary.empty else pd.DataFrame()
        row = case_rows.iloc[0] if not case_rows.empty else pd.Series(dtype=object)
        rows.append(
            {
                "failure_case_id": case_id,
                "actual_stage125_ready_for_stage123": int(pd.to_numeric(row.get("stage125_ready_for_stage123", 0), errors="coerce")),
                "actual_stage117_stage112_intake": _gate_observed(stage123_gate_detail, case_id, "stage117_stage112_intake"),
                "actual_stage120_real_schema_contract_pass": _gate_observed(stage123_gate_detail, case_id, "stage120_real_schema_contract_pass"),
                "actual_stage123_final_stage112_ready_count": int(pd.to_numeric(row.get("stage123_final_stage112_ready_count", 0), errors="coerce")),
                "actual_full_supergate_ready": int(pd.to_numeric(row.get("final_supergate_ready", 0), errors="coerce")),
                "actual_strategy_use_allowed_now": int(pd.to_numeric(row.get("strategy_use_allowed_now", 0), errors="coerce")),
            }
        )
    actual = pd.DataFrame(rows)
    result = expectation.merge(actual, on="failure_case_id", how="left")
    pairs = [
        ("expected_stage125_ready_for_stage123", "actual_stage125_ready_for_stage123"),
        ("expected_stage117_stage112_intake", "actual_stage117_stage112_intake"),
        ("expected_stage120_real_schema_contract_pass", "actual_stage120_real_schema_contract_pass"),
        ("expected_stage123_final_stage112_ready_count", "actual_stage123_final_stage112_ready_count"),
        ("expected_full_supergate_ready", "actual_full_supergate_ready"),
    ]
    for expected, actual_col in pairs:
        result[f"{expected}_matched"] = (
            pd.to_numeric(result[expected], errors="coerce").fillna(-999).astype(int)
            == pd.to_numeric(result[actual_col], errors="coerce").fillna(-998).astype(int)
        ).astype(int)
    match_cols = [column for column in result.columns if column.endswith("_matched")]
    result["expectation_all_matched"] = result[match_cols].min(axis=1).astype(int)
    result["unexpected_pass"] = (
        pd.to_numeric(result["actual_full_supergate_ready"], errors="coerce").fillna(0).astype(int)
        | pd.to_numeric(result["actual_strategy_use_allowed_now"], errors="coerce").fillna(0).astype(int)
    )
    return result


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, expectation: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage130 raw/parquet/checksum failure modes over official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1F5D4A", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.26)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not request_audit.empty:
        palette = ["#B91C1C", "#A16207", "#0369A1", "#7C3AED", "#0F766E", "#BE123C"]
        for idx, (case_id, group) in enumerate(request_audit.groupby("failure_case_id")):
            points = _nearest_curve_points(curve, group["trading_day"])
            color = palette[idx % len(palette)]
            marker = "o" if idx % 2 == 0 else "x"
            axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=color, marker=marker, s=24, alpha=0.42, label=case_id)
            axes[1].scatter(points["date"], points["drawdown_pct"], color=color, marker=marker, s=24, alpha=0.42)
            axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=color, marker=marker, s=24, alpha=0.42)
        axes[0].legend(loc="upper left", fontsize=6)
    cols = [
        "actual_stage125_ready_for_stage123",
        "actual_stage117_stage112_intake",
        "actual_stage120_real_schema_contract_pass",
        "actual_stage123_final_stage112_ready_count",
        "actual_full_supergate_ready",
        "unexpected_pass",
    ]
    chart = expectation.set_index("failure_case_id")[cols].copy()
    chart.plot(kind="bar", ax=axes[3], color=["#0F766E", "#3B5BDB", "#7C3AED", "#A16207", "#15803D", "#B91C1C"])
    axes[3].set_ylim(0, 1.2)
    axes[3].set_ylabel("flag")
    axes[3].set_title("Observed case-level gates")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_matrix(expectation: pd.DataFrame, step_summary: pd.DataFrame) -> None:
    columns = [
        "stage128_commands_ok",
        "actual_stage125_ready_for_stage123",
        "actual_stage117_stage112_intake",
        "actual_stage120_real_schema_contract_pass",
        "actual_stage123_final_stage112_ready_count",
        "actual_full_supergate_ready",
        "actual_strategy_use_allowed_now",
        "unexpected_pass",
        "expectation_all_matched",
    ]
    matrix = expectation.set_index("failure_case_id").copy()
    command_ok = (
        step_summary.assign(ok=step_summary["returncode"].eq(0).astype(int))
        .groupby("failure_case_id")["ok"]
        .min()
        if not step_summary.empty and "returncode" in step_summary.columns
        else pd.Series(dtype=int)
    )
    matrix["stage128_commands_ok"] = command_ok
    for column in columns:
        if column not in matrix.columns:
            matrix[column] = 0
    data = matrix[columns].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13.5, 5.6))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage130 raw/parquet/checksum supergate matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, int(data[y, x]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CASE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_expectation(expectation: pd.DataFrame) -> None:
    columns = [
        "expected_stage125_ready_for_stage123",
        "actual_stage125_ready_for_stage123",
        "expected_stage117_stage112_intake",
        "actual_stage117_stage112_intake",
        "expected_stage120_real_schema_contract_pass",
        "actual_stage120_real_schema_contract_pass",
        "expected_stage123_final_stage112_ready_count",
        "actual_stage123_final_stage112_ready_count",
        "expected_full_supergate_ready",
        "actual_full_supergate_ready",
    ]
    chart = expectation.set_index("failure_case_id")[columns].copy()
    fig, ax = plt.subplots(figsize=(15, 6.8))
    chart.plot(kind="bar", ax=ax, width=0.82)
    ax.set_title("Stage130 expected vs observed raw/parquet/checksum failures")
    ax.set_ylabel("flag")
    ax.set_ylim(0, 1.25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(EXPECTATION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_matrix(request_audit: pd.DataFrame) -> None:
    if request_audit.empty:
        return
    columns = [
        "proof_schema_bridge_ready",
        "role_complete",
        "checksum_match",
        "proof_required_fields_present",
        "preflight_request_ready",
        "stage127_125_request_ready",
        "full_supergate_request_ready",
        "strategy_use_allowed_now",
    ]
    available = [column for column in columns if column in request_audit.columns]
    sample = request_audit.sort_values(["failure_case_id", "trading_day", "request_id"]).reset_index(drop=True)
    data = sample[available].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig_height = max(8.0, min(32.0, len(sample) * 0.105))
    fig, ax = plt.subplots(figsize=(12, fig_height))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage130 request-level receipt/full-supergate matrix")
    ax.set_xticks(np.arange(len(available)))
    ax.set_xticklabels(available, rotation=35, ha="right")
    labels = [
        f"{row['failure_case_id']} | {row['request_id']}" if idx % 8 == 0 else ""
        for idx, row in sample.iterrows()
    ]
    ax.set_yticks(np.arange(len(sample)))
    ax.set_yticklabels(labels, fontsize=5)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, expectation: pd.DataFrame, case_summary: pd.DataFrame, stage123_gates: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} raw/parquet/checksum failure-mode audit",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: local bad-drop fixtures, Stage117 parquet-row hard gate patch, Stage128 orchestration, and visual QA only; no strategy rule, true engine, A/B, CTP, order API, or external download.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Failure Expectations",
        "",
        _md_table(expectation),
        "",
        "## Stage128 Case Summary",
        "",
        _md_table(case_summary),
        "",
        "## Stage123 Gate Detail Sample",
        "",
        _md_table(stage123_gates, max_rows=60),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CASE_MATRIX_CHART_OUT.name}`",
        f"- `{EXPECTATION_CHART_OUT.name}`",
        f"- `{REQUEST_MATRIX_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    cases, inventory = _build_bad_drops()

    run_rows: list[dict[str, Any]] = []
    summary_frames: list[pd.DataFrame] = []
    case_frames: list[pd.DataFrame] = []
    step_frames: list[pd.DataFrame] = []
    gate_frames: list[pd.DataFrame] = []
    request_frames: list[pd.DataFrame] = []
    stage123_gate_frames: list[pd.DataFrame] = []
    try:
        for case in cases:
            run_row, frames = _run_stage128(case)
            run_rows.append(run_row)
            if not frames["summary"].empty:
                summary_frames.append(frames["summary"])
            if not frames["case_summary"].empty:
                case_frames.append(frames["case_summary"])
            if not frames["step_summary"].empty:
                step_frames.append(frames["step_summary"])
            if not frames["gates"].empty:
                gate_frames.append(frames["gates"])
            if not frames["request_audit"].empty:
                request_frames.append(frames["request_audit"])
            if not frames["stage123_gate_detail"].empty:
                stage123_gate_frames.append(frames["stage123_gate_detail"])
    finally:
        restore_info = _restore_stage128_default()

    stage128_summaries = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    case_summary = pd.concat(case_frames, ignore_index=True) if case_frames else pd.DataFrame()
    step_summary = pd.concat(step_frames, ignore_index=True) if step_frames else pd.DataFrame()
    gates = pd.concat(gate_frames, ignore_index=True) if gate_frames else pd.DataFrame()
    request_audit = pd.concat(request_frames, ignore_index=True) if request_frames else pd.DataFrame()
    stage123_gates = pd.concat(stage123_gate_frames, ignore_index=True) if stage123_gate_frames else pd.DataFrame()
    run_summary = pd.DataFrame(run_rows)
    if not case_summary.empty:
        case_summary = case_summary.merge(run_summary[["failure_case_id", "stage128_returncode"]], on="failure_case_id", how="left")
    expectation = _expectation_frame(cases, case_summary, stage123_gates)

    stage128_returncode_zero = int(run_summary["stage128_returncode"].eq(0).all()) if not run_summary.empty else 0
    all_commands_returncode_zero = int(step_summary["returncode"].eq(0).all()) if not step_summary.empty and "returncode" in step_summary.columns else 0
    unexpected_pass_count = int(pd.to_numeric(expectation["unexpected_pass"], errors="coerce").fillna(0).sum()) if not expectation.empty else 0
    expectation_matched_count = int(pd.to_numeric(expectation["expectation_all_matched"], errors="coerce").fillna(0).sum()) if not expectation.empty else 0
    full_ready_count = int(pd.to_numeric(case_summary.get("final_supergate_ready", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    strategy_allowed_count = int(pd.to_numeric(case_summary.get("strategy_use_allowed_now", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    decision = DECISION
    if unexpected_pass_count > 0 or strategy_allowed_count > 0 or restore_info.get("stage128_default_restored", 0) != 1:
        decision = "stage130_raw_parquet_checksum_failure_mode_audit_failed"

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "failure_case_count": len(cases),
                "generated_bad_drop_file_count": int(len(inventory)),
                "stage117_parquet_row_count_gate_added": 1,
                "stage128_cli_run_count": len(run_summary),
                "stage128_returncode_zero": stage128_returncode_zero,
                "stage128_all_inner_commands_returncode_zero": all_commands_returncode_zero,
                "stage128_default_restored": int(restore_info.get("stage128_default_restored", 0)),
                "stage128_default_restore_returncode": int(restore_info.get("stage128_default_restore_returncode", -1)),
                "blocked_case_count": len(expectation) - unexpected_pass_count,
                "unexpected_pass_count": unexpected_pass_count,
                "expectation_matched_count": expectation_matched_count,
                "expectation_case_count": len(expectation),
                "full_supergate_ready_count": full_ready_count,
                "strategy_allowed_count": strategy_allowed_count,
                "stage125_ready_case_count": int(pd.to_numeric(expectation.get("actual_stage125_ready_for_stage123", 0), errors="coerce").fillna(0).sum()) if not expectation.empty else 0,
                "stage117_ready_case_count": int(pd.to_numeric(expectation.get("actual_stage117_stage112_intake", 0), errors="coerce").fillna(0).sum()) if not expectation.empty else 0,
                "stage120_ready_case_count": int(pd.to_numeric(expectation.get("actual_stage120_real_schema_contract_pass", 0), errors="coerce").fillna(0).sum()) if not expectation.empty else 0,
                "stage123_ready_case_count": int(pd.to_numeric(expectation.get("actual_stage123_final_stage112_ready_count", 0), errors="coerce").fillna(0).sum()) if not expectation.empty else 0,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summary, CASE_SUMMARY_OUT)
    _write_csv(step_summary, STEP_SUMMARY_OUT)
    _write_csv(gates, GATE_STATUS_OUT)
    _write_csv(request_audit, REQUEST_AUDIT_OUT)
    _write_csv(stage123_gates, STAGE123_GATE_DETAIL_OUT)
    _write_csv(inventory, INVENTORY_OUT)
    _write_csv(expectation, EXPECTATION_OUT)
    if not stage128_summaries.empty:
        _write_csv(stage128_summaries, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_summary_by_case_{MODEL_TAG}.csv")
    if not run_summary.empty:
        _write_csv(run_summary, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_command_run_summary_{MODEL_TAG}.csv")

    _plot_official_path(curve, request_audit, expectation)
    _plot_case_matrix(expectation, step_summary)
    _plot_expectation(expectation)
    _plot_request_matrix(request_audit)
    _write_report(summary, expectation, case_summary, stage123_gates)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "cases": cases,
            "restore_info": restore_info,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_summary": str(CASE_SUMMARY_OUT),
                "step_summary": str(STEP_SUMMARY_OUT),
                "gates": str(GATE_STATUS_OUT),
                "request_audit": str(REQUEST_AUDIT_OUT),
                "stage123_gate_detail": str(STAGE123_GATE_DETAIL_OUT),
                "inventory": str(INVENTORY_OUT),
                "expectation": str(EXPECTATION_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CASE_MATRIX_CHART_OUT),
                    str(EXPECTATION_CHART_OUT),
                    str(REQUEST_MATRIX_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
