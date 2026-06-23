from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional runtime dependency
    pq = None


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage266"
MODEL_TAG = "stage266_authorized_w0_real_package_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage266_authorized_w0_real_package_validator"

STAGE117_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"
STAGE120_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"
STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE135_DIR = LINE_DIR / "outputs" / "stage135_wave0_real_drop_operator_pack"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE263_DIR = LINE_DIR / "outputs" / "stage263_external_data_arrival_supergate_audit"
STAGE264_DIR = LINE_DIR / "outputs" / "stage264_external_data_inbox_arrival_monitor"

STAGE117_PREFIX = "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier"
STAGE120_PREFIX = "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit"
STAGE124_PREFIX = "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package"
STAGE135_PREFIX = "qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE263_PREFIX = "qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit"
STAGE264_PREFIX = "qmt_roll_stage264_c9_minrisk_external_data_inbox_arrival_monitor"

STAGE117_TAG = "stage117_wave0_delivery_verifier_v1"
STAGE120_TAG = "stage120_wave0_schema_contract_audit_v1"
STAGE124_TAG = "stage124_wave0_delivery_handoff_package_v1"
STAGE135_TAG = "stage135_wave0_real_drop_operator_pack_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE263_TAG = "stage263_external_data_arrival_supergate_audit_v1"
STAGE264_TAG = "stage264_external_data_inbox_arrival_monitor_v1"

STAGE117_REQUEST_STATUS_IN = STAGE117_DIR / f"{STAGE117_PREFIX}_w0_request_delivery_status_{STAGE117_TAG}.csv"
STAGE120_FIELD_CONTRACT_IN = STAGE120_DIR / f"{STAGE120_PREFIX}_canonical_field_contract_{STAGE120_TAG}.csv"
STAGE124_FILE_CONTRACT_IN = STAGE124_DIR / f"{STAGE124_PREFIX}_delivery_file_contract_{STAGE124_TAG}.csv"
STAGE124_PROOF_CONTRACT_IN = STAGE124_DIR / f"{STAGE124_PREFIX}_proof_field_contract_{STAGE124_TAG}.csv"
STAGE135_DROP_DIRS_IN = STAGE135_DIR / f"{STAGE135_PREFIX}_candidate_drop_dir_audit_{STAGE135_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE263_ROUTE_IN = STAGE263_DIR / f"{STAGE263_PREFIX}_route_supergate_{STAGE263_TAG}.csv"
STAGE264_PACKAGE_INVENTORY_IN = STAGE264_DIR / f"{STAGE264_PREFIX}_package_inventory_{STAGE264_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DROP_ROOT_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drop_root_inventory_{MODEL_TAG}.csv"
FILE_ROLE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_role_audit_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_package_audit_{MODEL_TAG}.csv"
PARQUET_SCHEMA_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_parquet_schema_audit_{MODEL_TAG}.csv"
PROOF_HASH_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_hash_audit_{MODEL_TAG}.csv"
PACKAGE_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_gate_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_w0_validator_status_{MODEL_TAG}.png"
DROP_ROOT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drop_root_matrix_{MODEL_TAG}.png"
FILE_ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_role_coverage_chart_{MODEL_TAG}.png"
REQUEST_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_hard_accept_heatmap_{MODEL_TAG}.png"
SCHEMA_PROOF_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_proof_gate_chart_{MODEL_TAG}.png"
PACKAGE_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_gate_chart_{MODEL_TAG}.png"

EXPECTED_W0_REQUEST_COUNT = 41
EXPECTED_W0_FILE_COUNT = 123
EXPECTED_ROUTE_WINDOW_COUNT = 485
FORBIDDEN_MARKERS = [
    "dry_run",
    "dry-run",
    "readonly",
    "read_only",
    "adapter",
    "synthetic",
    "fixture",
    "backtest_ledger",
    "paper",
]


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
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


def _get(row: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in row and not pd.isna(row[key]):
            return row[key]
    return default


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


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    arm = stage251_summary.get("arm", pd.Series(dtype=str)).astype(str)
    official = stage251_summary[arm.eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _official_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    arm = curve.get("arm", pd.Series(dtype=str)).astype(str)
    official = curve[arm.eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    for column in ["account_equity", "drawdown_pct"]:
        official[column] = pd.to_numeric(official[column], errors="coerce")
    return official[official["date"].notna()].sort_values("date").reset_index(drop=True)


def _load_inputs() -> dict[str, Any]:
    return {
        "stage117_request_status": _read_csv(STAGE117_REQUEST_STATUS_IN),
        "stage120_field_contract": _read_csv(STAGE120_FIELD_CONTRACT_IN),
        "stage124_file_contract": _read_csv(STAGE124_FILE_CONTRACT_IN),
        "stage124_proof_contract": _read_csv(STAGE124_PROOF_CONTRACT_IN),
        "stage135_drop_dirs": _read_csv(STAGE135_DROP_DIRS_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage263_route": _read_csv(STAGE263_ROUTE_IN, required=False),
        "stage264_package_inventory": _read_csv(STAGE264_PACKAGE_INVENTORY_IN, required=False),
    }


def _safe_rglob(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted([path for path in root.rglob("*") if path.is_file()], key=lambda item: str(item))


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _forbidden_marker_hit(path: Path | str) -> str:
    text = str(path).lower()
    hits = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    return ",".join(hits)


def _flatten_json(payload: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_key = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(_flatten_json(value, next_key))
            else:
                out[next_key] = value
                out[str(key)] = value
    return out


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return _flatten_json(payload)


def _drop_roots(stage135_drop_dirs: pd.DataFrame) -> list[Path]:
    roots = [Path(str(row["drop_dir"])) for _, row in stage135_drop_dirs.iterrows()]
    return roots if roots else [LINE_DIR / "incoming" / "w0_real_drop"]


def _file_cache(roots: list[Path]) -> dict[str, list[Path]]:
    return {str(root): _safe_rglob(root) for root in roots}


def _match_role_file(root: Path, contract_row: dict[str, Any], files: list[Path]) -> Path | None:
    request_id = str(contract_row["request_id"])
    role = str(contract_row["artifact_role"])
    recommended = str(contract_row["recommended_relative_path"])
    exact_allowed = "<" not in recommended and ">" not in recommended
    exact_path = root / recommended
    if exact_allowed and exact_path.exists() and exact_path.is_file():
        return exact_path

    candidates = [path for path in files if request_id.lower() in str(path).lower()]
    if role == "normalized_parquet":
        matches = [path for path in candidates if path.suffix.lower() == ".parquet" and "normalized" in str(path).lower()]
        if not matches:
            matches = [path for path in candidates if path.suffix.lower() == ".parquet"]
    elif role == "proof":
        matches = [path for path in candidates if path.suffix.lower() == ".json" and "proof" in str(path).lower()]
    else:
        matches = [
            path
            for path in candidates
            if "raw" in str(path).lower() and path.suffix.lower() not in {".parquet", ".json"}
        ]
    return sorted(matches, key=lambda item: str(item))[0] if matches else None


def _file_role_audit(inputs: dict[str, Any], roots: list[Path], files_by_root: dict[str, list[Path]]) -> pd.DataFrame:
    contract = inputs["stage124_file_contract"]
    rows: list[dict[str, Any]] = []
    for root in roots:
        files = files_by_root[str(root)]
        for _, item in contract.iterrows():
            role = item.to_dict()
            match = _match_role_file(root, role, files)
            expected_path = root / str(role["recommended_relative_path"]).replace("<vendor_raw_ext>", "vendor_raw_ext")
            matched_path = str(match) if match is not None else ""
            rows.append(
                {
                    "drop_root": str(root),
                    "request_id": str(role["request_id"]),
                    "batch_id": str(role["batch_id"]),
                    "vt_symbol": str(role["vt_symbol"]),
                    "exchange": str(role["exchange"]),
                    "product": str(role["product"]),
                    "trading_day": str(role["trading_day"]),
                    "required_schema_request": str(role["required_schema_request"]),
                    "artifact_role": str(role["artifact_role"]),
                    "required_now": _to_int(role["required_now"]),
                    "recommended_relative_path": str(role["recommended_relative_path"]),
                    "expected_path": str(expected_path),
                    "matched_path": matched_path,
                    "exists": int(match is not None and match.exists() and match.is_file()),
                    "matched_bytes": int(match.stat().st_size) if match is not None and match.exists() else 0,
                    "forbidden_marker_hit": _forbidden_marker_hit(matched_path or root),
                    "role_present": int(match is not None and match.exists() and match.is_file()),
                }
            )
    return pd.DataFrame(rows)


def _drop_root_inventory(roots: list[Path], files_by_root: dict[str, list[Path]], file_role: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for root in roots:
        files = files_by_root[str(root)]
        roles = file_role[file_role["drop_root"].eq(str(root))]
        request_counts = roles.pivot_table(index="request_id", columns="artifact_role", values="role_present", aggfunc="max", fill_value=0)
        if request_counts.empty:
            request_complete = 0
            request_any = 0
        else:
            for column in ["raw", "normalized_parquet", "proof"]:
                if column not in request_counts.columns:
                    request_counts[column] = 0
            request_complete = int((request_counts[["raw", "normalized_parquet", "proof"]].sum(axis=1) == 3).sum())
            request_any = int((request_counts[["raw", "normalized_parquet", "proof"]].sum(axis=1) > 0).sum())
        role_counts = roles.groupby("artifact_role")["role_present"].sum().to_dict()
        forbidden_count = int((roles["forbidden_marker_hit"].astype(str).str.len() > 0).sum()) if not roles.empty else 0
        rows.append(
            {
                "drop_root": str(root),
                "exists": int(root.exists() and root.is_dir()),
                "total_file_count": len(files),
                "total_bytes": int(sum(path.stat().st_size for path in files)),
                "expected_file_count": EXPECTED_W0_FILE_COUNT,
                "known_role_file_count": int(roles["role_present"].sum()) if not roles.empty else 0,
                "raw_file_count": int(role_counts.get("raw", 0)),
                "normalized_parquet_file_count": int(role_counts.get("normalized_parquet", 0)),
                "proof_file_count": int(role_counts.get("proof", 0)),
                "request_count_with_any_role": request_any,
                "request_role_complete_count": request_complete,
                "expected_request_count": EXPECTED_W0_REQUEST_COUNT,
                "forbidden_marker_count": forbidden_count,
                "candidate_ready_for_stage112": int(
                    root.exists()
                    and request_complete >= EXPECTED_W0_REQUEST_COUNT
                    and int(role_counts.get("raw", 0)) >= EXPECTED_W0_REQUEST_COUNT
                    and int(role_counts.get("normalized_parquet", 0)) >= EXPECTED_W0_REQUEST_COUNT
                    and int(role_counts.get("proof", 0)) >= EXPECTED_W0_REQUEST_COUNT
                    and forbidden_count == 0
                ),
            }
        )
    return pd.DataFrame(rows)


def _schema_fields_for_request(field_contract: pd.DataFrame, schema_request: str) -> pd.DataFrame:
    schema_lower = schema_request.lower()
    if "mbp" in schema_lower:
        required = field_contract[field_contract["required_for_mbp10"].map(_to_int).eq(1)]
    elif "mbo" in schema_lower:
        required = field_contract[field_contract["required_for_mbo"].map(_to_int).eq(1)]
    else:
        required = field_contract[field_contract["hard_required_any_schema"].map(_to_int).eq(1)]
    return required.copy()


def _parquet_columns(path: Path) -> tuple[int, int, set[str], str]:
    if not path.exists() or not path.is_file():
        return 0, 0, set(), "missing"
    if pq is None:
        return 0, 0, set(), "pyarrow_unavailable"
    try:
        parquet = pq.ParquetFile(str(path))
        names = {str(name) for name in parquet.schema_arrow.names}
        return 1, int(parquet.metadata.num_rows), names, ""
    except Exception as exc:  # pragma: no cover - depends on delivered files
        return 0, 0, set(), f"{type(exc).__name__}: {exc}"


def _field_present(row: pd.Series, columns: set[str]) -> bool:
    lowered = {column.lower() for column in columns}
    aliases = [str(row["canonical_field"])]
    aliases += [part.strip() for part in str(row.get("accepted_aliases", "")).split(",") if part.strip()]
    return any(alias.lower() in lowered for alias in aliases)


def _parquet_schema_audit(inputs: dict[str, Any], file_role: pd.DataFrame) -> pd.DataFrame:
    field_contract = inputs["stage120_field_contract"]
    parquet_roles = file_role[file_role["artifact_role"].eq("normalized_parquet")]
    rows: list[dict[str, Any]] = []
    for _, item in parquet_roles.iterrows():
        path = Path(str(item["matched_path"])) if str(item["matched_path"]) else Path("")
        readable, row_count, columns, error = _parquet_columns(path)
        required = _schema_fields_for_request(field_contract, str(item["required_schema_request"]))
        missing: list[str] = []
        if readable:
            missing = [str(row["canonical_field"]) for _, row in required.iterrows() if not _field_present(row, columns)]
        else:
            missing = required["canonical_field"].astype(str).tolist()
        rows.append(
            {
                "drop_root": str(item["drop_root"]),
                "request_id": str(item["request_id"]),
                "vt_symbol": str(item["vt_symbol"]),
                "required_schema_request": str(item["required_schema_request"]),
                "parquet_path": str(item["matched_path"]),
                "exists": _to_int(item["exists"]),
                "parquet_readable": readable,
                "parquet_row_count": row_count,
                "required_field_count": int(len(required)),
                "present_required_field_count": int(len(required) - len(missing)),
                "missing_required_fields": ",".join(missing),
                "parquet_schema_pass": int(readable and row_count > 0 and not missing),
                "parquet_read_error": error,
            }
        )
    return pd.DataFrame(rows)


def _proof_field_pass(field: str, value: Any) -> int:
    text = "" if pd.isna(value) else str(value).strip()
    lowered = text.lower()
    if field in {"vendor", "dataset"}:
        return int(bool(text) and "synthetic" not in lowered and "smoke" not in lowered)
    if field == "row_count":
        return int(_to_int(value) > 0)
    if field == "sequence_gap_count":
        return int(_to_int(value, default=-1) == 0)
    return int(bool(text))


def _parse_ts(value: Any) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(value, errors="coerce")


def _proof_hash_audit(inputs: dict[str, Any], file_role: pd.DataFrame) -> pd.DataFrame:
    proof_contract = inputs["stage124_proof_contract"]
    request_status = inputs["stage117_request_status"]
    required_proof_fields = proof_contract[proof_contract["required_for_real_w0"].map(_to_int).eq(1)]["proof_json_field"].astype(str).tolist()
    by_role = file_role.pivot_table(index=["drop_root", "request_id"], columns="artifact_role", values="matched_path", aggfunc="first", fill_value="")
    rows: list[dict[str, Any]] = []
    request_meta = request_status.set_index("request_id").to_dict(orient="index")
    for (drop_root, request_id), role_paths in by_role.iterrows():
        proof_path = Path(str(role_paths.get("proof", ""))) if str(role_paths.get("proof", "")) else Path("")
        raw_path = Path(str(role_paths.get("raw", ""))) if str(role_paths.get("raw", "")) else Path("")
        parquet_path = Path(str(role_paths.get("normalized_parquet", ""))) if str(role_paths.get("normalized_parquet", "")) else Path("")
        proof = _read_json(proof_path)
        missing = [field for field in required_proof_fields if not _proof_field_pass(field, proof.get(field, ""))]
        raw_sha_expected = str(proof.get("raw_sha256", proof.get("raw_file_sha256", ""))).strip()
        parquet_sha_expected = str(proof.get("normalized_parquet_sha256", proof.get("parquet_sha256", ""))).strip()
        raw_sha_actual = ""
        parquet_sha_actual = ""
        try:
            if raw_path.exists() and raw_path.is_file():
                raw_sha_actual = _sha256(raw_path)
            if parquet_path.exists() and parquet_path.is_file():
                parquet_sha_actual = _sha256(parquet_path)
        except OSError:
            pass
        raw_hash_match = int(bool(raw_sha_expected) and bool(raw_sha_actual) and raw_sha_expected == raw_sha_actual)
        parquet_hash_match = int((not parquet_sha_expected) or (bool(parquet_sha_actual) and parquet_sha_expected == parquet_sha_actual))
        meta = request_meta.get(str(request_id), {})
        request_start = _parse_ts(meta.get("request_start"))
        request_end = _parse_ts(meta.get("request_end"))
        first_ts = _parse_ts(proof.get("first_ts_event"))
        last_ts = _parse_ts(proof.get("last_ts_event"))
        time_span_ok = int(
            pd.notna(first_ts)
            and pd.notna(last_ts)
            and pd.notna(request_start)
            and pd.notna(request_end)
            and first_ts <= request_start
            and last_ts >= request_end
        )
        sequence_gap_zero = int(_to_int(proof.get("sequence_gap_count"), default=-1) == 0)
        row_count_positive = int(_to_int(proof.get("row_count")) > 0)
        rows.append(
            {
                "drop_root": str(drop_root),
                "request_id": str(request_id),
                "proof_path": str(proof_path) if str(proof_path) != "." else "",
                "raw_path": str(raw_path) if str(raw_path) != "." else "",
                "parquet_path": str(parquet_path) if str(parquet_path) != "." else "",
                "proof_exists": int(proof_path.exists() and proof_path.is_file()),
                "required_proof_field_count": len(required_proof_fields),
                "present_required_proof_field_count": len(required_proof_fields) - len(missing),
                "missing_required_proof_fields": ",".join(missing),
                "raw_sha256_present": int(bool(raw_sha_expected)),
                "raw_sha256_match": raw_hash_match,
                "parquet_sha256_match_or_not_required": parquet_hash_match,
                "row_count_positive": row_count_positive,
                "sequence_gap_zero": sequence_gap_zero,
                "time_span_ok": time_span_ok,
                "proof_value_pass": int(
                    proof_path.exists()
                    and not missing
                    and raw_hash_match
                    and parquet_hash_match
                    and row_count_positive
                    and sequence_gap_zero
                    and time_span_ok
                ),
            }
        )
    return pd.DataFrame(rows)


def _request_package_audit(
    inputs: dict[str, Any],
    roots: list[Path],
    file_role: pd.DataFrame,
    parquet_schema: pd.DataFrame,
    proof_hash: pd.DataFrame,
) -> pd.DataFrame:
    request_status = inputs["stage117_request_status"]
    rows: list[dict[str, Any]] = []
    for root in roots:
        roles = file_role[file_role["drop_root"].eq(str(root))]
        schema = parquet_schema[parquet_schema["drop_root"].eq(str(root))]
        proof = proof_hash[proof_hash["drop_root"].eq(str(root))]
        role_pivot = roles.pivot_table(index="request_id", columns="artifact_role", values="role_present", aggfunc="max", fill_value=0)
        schema_map = schema.set_index("request_id").to_dict(orient="index") if not schema.empty else {}
        proof_map = proof.set_index("request_id").to_dict(orient="index") if not proof.empty else {}
        for _, request in request_status.iterrows():
            request_id = str(request["request_id"])
            role_row = role_pivot.loc[request_id].to_dict() if request_id in role_pivot.index else {}
            raw_exists = _to_int(role_row.get("raw"))
            parquet_exists = _to_int(role_row.get("normalized_parquet"))
            proof_exists = _to_int(role_row.get("proof"))
            schema_row = schema_map.get(request_id, {})
            proof_row = proof_map.get(request_id, {})
            role_complete = int(raw_exists and parquet_exists and proof_exists)
            hard_accept = int(
                role_complete
                and _to_int(schema_row.get("parquet_schema_pass"))
                and _to_int(proof_row.get("proof_value_pass"))
            )
            issue_codes = []
            if not raw_exists:
                issue_codes.append("raw_file_missing")
            if not parquet_exists:
                issue_codes.append("normalized_parquet_file_missing")
            if not proof_exists:
                issue_codes.append("proof_file_missing")
            if not _to_int(schema_row.get("parquet_schema_pass")):
                issue_codes.append("parquet_schema_not_passed")
            if not _to_int(proof_row.get("proof_value_pass")):
                issue_codes.append("proof_hash_or_span_not_passed")
            rows.append(
                {
                    "drop_root": str(root),
                    "request_id": request_id,
                    "batch_id": str(request["batch_id"]),
                    "vt_symbol": str(request["vt_symbol"]),
                    "exchange": str(request["exchange"]),
                    "product": str(request["product"]),
                    "trading_day": str(request["trading_day"]),
                    "request_start": str(request["request_start"]),
                    "request_end": str(request["request_end"]),
                    "window_count": _to_int(request["window_count"]),
                    "raw_exists": raw_exists,
                    "parquet_exists": parquet_exists,
                    "proof_exists": proof_exists,
                    "role_complete": role_complete,
                    "parquet_schema_pass": _to_int(schema_row.get("parquet_schema_pass")),
                    "proof_value_pass": _to_int(proof_row.get("proof_value_pass")),
                    "raw_sha256_match": _to_int(proof_row.get("raw_sha256_match")),
                    "sequence_gap_zero": _to_int(proof_row.get("sequence_gap_zero")),
                    "time_span_ok": _to_int(proof_row.get("time_span_ok")),
                    "hard_accept": hard_accept,
                    "issue_count": len(issue_codes),
                    "issue_codes": ";".join(issue_codes),
                }
            )
    return pd.DataFrame(rows)


def _package_gate(
    root_inventory: pd.DataFrame,
    request_audit: pd.DataFrame,
    parquet_schema: pd.DataFrame,
    proof_hash: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, root_row in root_inventory.iterrows():
        root = str(root_row["drop_root"])
        requests = request_audit[request_audit["drop_root"].eq(root)]
        schema = parquet_schema[parquet_schema["drop_root"].eq(root)]
        proof = proof_hash[proof_hash["drop_root"].eq(root)]
        gate_items = [
            ("validator_only_no_order_api", 1, 1, "read-only validator; no CTP/SimNow/order API"),
            ("drop_root_exists", 1, _to_int(root_row["exists"]), "candidate W0 drop root exists"),
            ("no_forbidden_marker", 1, int(_to_int(root_row["forbidden_marker_count"]) == 0), "reject smoke/read-only/adapter/synthetic markers"),
            ("all_123_file_roles_present", EXPECTED_W0_FILE_COUNT, _to_int(root_row["known_role_file_count"]), "raw/parquet/proof files for all 41 W0 requests"),
            ("all_41_request_roles_complete", EXPECTED_W0_REQUEST_COUNT, _to_int(root_row["request_role_complete_count"]), "each W0 request has raw + normalized parquet + proof"),
            ("all_parquet_readable", EXPECTED_W0_REQUEST_COUNT, int(schema["parquet_readable"].sum()) if not schema.empty else 0, "Parquet footer/schema is readable"),
            ("all_parquet_schema_pass", EXPECTED_W0_REQUEST_COUNT, int(schema["parquet_schema_pass"].sum()) if not schema.empty else 0, "Stage120 canonical fields or aliases present"),
            ("all_proof_values_pass", EXPECTED_W0_REQUEST_COUNT, int(proof["proof_value_pass"].sum()) if not proof.empty else 0, "Stage124 proof fields, raw hash, sequence and time span pass"),
            ("all_raw_sha256_match", EXPECTED_W0_REQUEST_COUNT, int(proof["raw_sha256_match"].sum()) if not proof.empty else 0, "raw file hash matches proof"),
            ("all_w0_requests_hard_accept", EXPECTED_W0_REQUEST_COUNT, int(requests["hard_accept"].sum()) if not requests.empty else 0, "Stage117-style hard accept on all W0 requests"),
            ("stage112_113_release_allowed", 1, 0, "package validation alone does not release strategy intake"),
            ("strategy_rule_or_true_engine_allowed", 1, 0, "data validation does not create a rule"),
        ]
        for gate_id, required, observed, reason in gate_items:
            rows.append(
                {
                    "drop_root": root,
                    "gate_id": gate_id,
                    "required": required,
                    "observed": observed,
                    "pass_now": int(observed >= required),
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _accepted_package_count(package_gate: pd.DataFrame) -> int:
    if package_gate.empty:
        return 0
    data_gates = package_gate[~package_gate["gate_id"].isin({"stage112_113_release_allowed", "strategy_rule_or_true_engine_allowed"})]
    return int(data_gates.groupby("drop_root")["pass_now"].min().sum())


def _next_action(root_inventory: pd.DataFrame, package_gate: pd.DataFrame) -> pd.DataFrame:
    accepted_count = _accepted_package_count(package_gate)
    root_with_files = int((root_inventory["total_file_count"] > 0).sum()) if not root_inventory.empty else 0
    rows = [
        {
            "priority": 1,
            "action_id": "accepted_w0_package_then_run_stage112_113_141",
            "condition_now": int(accepted_count > 0),
            "action": "Use accepted authorized W0 package for Stage112/113 intake and then Stage141 promotion gates.",
            "allowed_now": int(accepted_count > 0),
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 2,
            "action_id": "partial_w0_package_fix_roles_schema_proof_hash",
            "condition_now": int(root_with_files > 0 and accepted_count == 0),
            "action": "Keep partial W0 package quarantined and fix failed file/schema/proof/hash gates.",
            "allowed_now": int(root_with_files > 0 and accepted_count == 0),
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 3,
            "action_id": "empty_w0_inbox_wait_real_authorized_drop",
            "condition_now": int(root_with_files == 0),
            "action": "No authorized W0 files detected. Keep monitoring; do not resume local OHLCV/OI parameter rules.",
            "allowed_now": int(root_with_files == 0),
            "strategy_rule_allowed": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    inputs: dict[str, Any],
    root_inventory: pd.DataFrame,
    file_role: pd.DataFrame,
    request_audit: pd.DataFrame,
    parquet_schema: pd.DataFrame,
    proof_hash: pd.DataFrame,
    package_gate: pd.DataFrame,
) -> pd.DataFrame:
    official = _official_summary(inputs["stage251_summary"])
    route = inputs["stage263_route"]
    orderflow_route = route[route.get("route_id", pd.Series(dtype=str)).astype(str).eq("authorized_orderflow_mbp10_mbo_w0_chain")]
    route_row = _row(orderflow_route)
    accepted_count = _accepted_package_count(package_gate)
    best_complete = int(root_inventory["request_role_complete_count"].max()) if not root_inventory.empty else 0
    best_known = int(root_inventory["known_role_file_count"].max()) if not root_inventory.empty else 0
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage266_authorized_w0_validator_no_real_package_no_rule",
        "stage_nature": "read_only_authorized_w0_real_package_validator",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "drop_root_candidate_count": int(len(root_inventory)),
        "drop_root_exists_count": int(root_inventory["exists"].sum()) if not root_inventory.empty else 0,
        "drop_root_with_files_count": int((root_inventory["total_file_count"] > 0).sum()) if not root_inventory.empty else 0,
        "accepted_w0_package_count": accepted_count,
        "expected_request_count_per_package": EXPECTED_W0_REQUEST_COUNT,
        "expected_file_count_per_package": EXPECTED_W0_FILE_COUNT,
        "expected_route_window_count": _to_int(_get(route_row, "primary_expected_count", default=EXPECTED_ROUTE_WINDOW_COUNT), EXPECTED_ROUTE_WINDOW_COUNT),
        "ready_route_window_count": _to_int(_get(route_row, "primary_ready_count")),
        "missing_route_window_count": _to_int(_get(route_row, "primary_missing_count", default=EXPECTED_ROUTE_WINDOW_COUNT), EXPECTED_ROUTE_WINDOW_COUNT),
        "best_known_role_file_count": best_known,
        "best_request_role_complete_count": best_complete,
        "raw_file_pass_count": int(file_role[file_role["artifact_role"].eq("raw")]["role_present"].sum()) if not file_role.empty else 0,
        "parquet_file_pass_count": int(file_role[file_role["artifact_role"].eq("normalized_parquet")]["role_present"].sum()) if not file_role.empty else 0,
        "proof_file_pass_count": int(file_role[file_role["artifact_role"].eq("proof")]["role_present"].sum()) if not file_role.empty else 0,
        "request_hard_accept_count": int(request_audit["hard_accept"].sum()) if not request_audit.empty else 0,
        "parquet_schema_audit_count": int(len(parquet_schema)),
        "parquet_schema_pass_count": int(parquet_schema["parquet_schema_pass"].sum()) if not parquet_schema.empty else 0,
        "proof_hash_audit_count": int(len(proof_hash)),
        "proof_value_pass_count": int(proof_hash["proof_value_pass"].sum()) if not proof_hash.empty else 0,
        "raw_sha256_match_count": int(proof_hash["raw_sha256_match"].sum()) if not proof_hash.empty else 0,
        "canonical_field_contract_count": int(len(inputs["stage120_field_contract"])),
        "proof_required_field_count": int(inputs["stage124_proof_contract"]["required_for_real_w0"].map(_to_int).sum()),
        "package_gate_count": int(len(package_gate)),
        "package_gate_pass_count": int(package_gate["pass_now"].sum()) if not package_gate.empty else 0,
        "stage112_113_release_allowed_now": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "official_end_equity": _to_float(_get(official, "end_equity")),
        "official_total_return_pct": _to_float(_get(official, "total_return_pct")),
        "official_max_dd_pct": _to_float(_get(official, "max_dd_pct", "max_drawdown_pct")),
        "official_sharpe": _to_float(_get(official, "sharpe")),
        "official_total_slippage": _to_float(_get(official, "total_slippage")),
        "official_total_trade_count": _to_float(_get(official, "total_trade_count")),
        "official_win_rate_pct": _to_float(_get(official, "nonzero_daily_win_rate_pct", "closed_lot_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(_get(official, "max_broker10_margin_to_equity_pct")),
        "visual_file_count": 6,
    }
    return pd.DataFrame([row])


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = _row(summary)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#2f6f73", linewidth=1.8)
    ax1.set_ylabel("Equity")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b5533c", alpha=0.25)
    ax2.set_ylabel("Drawdown %")
    ax1.set_title(
        "Stage266 authorized W0 validator | "
        f"accepted {row['accepted_w0_package_count']} | "
        f"W0 hard accept {row['request_hard_accept_count']}/{row['drop_root_candidate_count'] * EXPECTED_W0_REQUEST_COUNT}"
    )
    ax1.text(
        0.015,
        0.95,
        "Validator only: no strategy rule / no true engine / no order API",
        transform=ax1.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_drop_root(root_inventory: pd.DataFrame) -> None:
    columns = ["exists", "raw_file_count", "normalized_parquet_file_count", "proof_file_count", "request_role_complete_count"]
    data = root_inventory.set_index("drop_root")[columns].copy()
    labels = [Path(index).name for index in data.index]
    fig, ax = plt.subplots(figsize=(11, max(3.5, len(data) * 0.45 + 1.8)))
    ax.imshow(data.to_numpy(dtype=float), cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(int(data.iloc[i, j])), ha="center", va="center", fontsize=8, color="#111111")
    ax.set_title("W0 candidate drop root inventory")
    fig.tight_layout()
    fig.savefig(DROP_ROOT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_file_role(file_role: pd.DataFrame) -> None:
    role_counts = file_role.groupby(["drop_root", "artifact_role"])["role_present"].sum().reset_index()
    pivot = role_counts.pivot(index="drop_root", columns="artifact_role", values="role_present").fillna(0)
    for column in ["raw", "normalized_parquet", "proof"]:
        if column not in pivot.columns:
            pivot[column] = 0
    pivot = pivot[["raw", "normalized_parquet", "proof"]]
    labels = [Path(index).name for index in pivot.index]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(pivot))
    width = 0.25
    colors = {"raw": "#5b8c85", "normalized_parquet": "#d6a04a", "proof": "#7d6aa3"}
    for idx, column in enumerate(pivot.columns):
        ax.bar(x + (idx - 1) * width, pivot[column].to_numpy(dtype=float), width=width, label=column, color=colors[column])
    ax.axhline(EXPECTED_W0_REQUEST_COUNT, color="#b5533c", linestyle="--", linewidth=1.2, label="41 per role")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Role files")
    ax.set_title("W0 file role coverage by drop root")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FILE_ROLE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_request_heatmap(request_audit: pd.DataFrame) -> None:
    pivot = request_audit.pivot_table(index="request_id", columns="drop_root", values="hard_accept", aggfunc="max", fill_value=0)
    labels = [Path(column).name for column in pivot.columns]
    fig, ax = plt.subplots(figsize=(10, max(7, len(pivot) * 0.16 + 2)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=6)
    ax.set_title("Stage117-style W0 hard accept heatmap")
    fig.tight_layout()
    fig.savefig(REQUEST_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_proof(parquet_schema: pd.DataFrame, proof_hash: pd.DataFrame) -> None:
    schema_pass = parquet_schema.groupby("drop_root")["parquet_schema_pass"].sum()
    proof_pass = proof_hash.groupby("drop_root")["proof_value_pass"].sum()
    hash_pass = proof_hash.groupby("drop_root")["raw_sha256_match"].sum()
    roots = sorted(set(schema_pass.index).union(proof_pass.index).union(hash_pass.index))
    labels = [Path(root).name for root in roots]
    data = pd.DataFrame(
        {
            "parquet_schema_pass": [schema_pass.get(root, 0) for root in roots],
            "proof_value_pass": [proof_pass.get(root, 0) for root in roots],
            "raw_sha256_match": [hash_pass.get(root, 0) for root in roots],
        },
        index=labels,
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(data))
    width = 0.25
    for idx, column in enumerate(data.columns):
        ax.bar(x + (idx - 1) * width, data[column].to_numpy(dtype=float), width=width, label=column)
    ax.axhline(EXPECTED_W0_REQUEST_COUNT, color="#b5533c", linestyle="--", linewidth=1.2, label="41 pass threshold")
    ax.set_xticks(x)
    ax.set_xticklabels(data.index, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Passing request count")
    ax.set_title("Schema / proof / hash gate coverage")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SCHEMA_PROOF_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_package_gate(package_gate: pd.DataFrame) -> None:
    pivot = package_gate.pivot_table(index="drop_root", columns="gate_id", values="pass_now", aggfunc="max", fill_value=0)
    labels = [Path(index).name for index in pivot.index]
    fig, ax = plt.subplots(figsize=(13, max(3.5, len(pivot) * 0.45 + 1.8)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=7)
    ax.set_title("Authorized W0 package hard gate")
    fig.tight_layout()
    fig.savefig(PACKAGE_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _report(
    summary: pd.DataFrame,
    root_inventory: pd.DataFrame,
    file_role: pd.DataFrame,
    request_audit: pd.DataFrame,
    parquet_schema: pd.DataFrame,
    proof_hash: pd.DataFrame,
    package_gate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> str:
    row = _row(summary)
    role_view = file_role.groupby(["drop_root", "artifact_role"])["role_present"].sum().reset_index()
    request_view = request_audit.groupby("drop_root")[["role_complete", "parquet_schema_pass", "proof_value_pass", "hard_accept"]].sum().reset_index()
    return f"""# Stage266 authorized W0 real package validator

## Decision

`{row['decision']}`

This stage is a read-only validator for authorized W0 MBO/MBP10 real package drops. It validates candidate drop roots, Stage124 file roles, Stage120 parquet schemas, Stage124 proof fields, raw hashes, request time-span continuity, and Stage117-style hard accept status. It does not create a strategy rule, run true engine, trigger A/B, change official config, connect CTP/SimNow, or call any order API.

## External research judgment

The validation design follows data-contract practice from columnar market-data delivery: Apache Parquet stores schema metadata with the file, PyArrow can inspect Parquet schema/row metadata without treating filenames as proof, Databento MBO/MBP10 definitions justify separating L3 order events from L2 price-depth ladders, and Frictionless Table Schema supports explicit field constraints. For this line, a W0 package is usable only after raw bytes, normalized parquet, proof JSON, license/source metadata, hash continuity, and request-window coverage all pass.

Sources:
- https://parquet.apache.org/docs/file-format/
- https://arrow.apache.org/docs/python/parquet.html
- https://databento.com/docs/schemas-and-data-formats/mbo
- https://databento.com/docs/schemas-and-data-formats/mbp-10
- https://frictionlessdata.io/specs/table-schema/

## Summary

- Official A unchanged: equity `{row['official_end_equity']:.2f}`, return `{row['official_total_return_pct']:.4f}%`, maxDD `{row['official_max_dd_pct']:.4f}%`, Sharpe `{row['official_sharpe']:.4f}`, slippage `{row['official_total_slippage']:.0f}`, trades `{row['official_total_trade_count']:.0f}`, win rate `{row['official_win_rate_pct']:.4f}%`.
- Drop root candidates: `{row['drop_root_candidate_count']}`; existing roots `{row['drop_root_exists_count']}`; roots with files `{row['drop_root_with_files_count']}`; accepted W0 packages `{row['accepted_w0_package_count']}`.
- Expected per package: `{row['expected_request_count_per_package']}` W0 requests, `{row['expected_file_count_per_package']}` role files, `{row['expected_route_window_count']}` route windows.
- Current best coverage: role files `{row['best_known_role_file_count']}/{row['expected_file_count_per_package']}`, complete requests `{row['best_request_role_complete_count']}/{row['expected_request_count_per_package']}`, route windows `{row['ready_route_window_count']}/{row['expected_route_window_count']}`.
- Role files observed across roots: raw `{row['raw_file_pass_count']}`, parquet `{row['parquet_file_pass_count']}`, proof `{row['proof_file_pass_count']}`.
- Request hard accept count: `{row['request_hard_accept_count']}`.
- Parquet schema pass: `{row['parquet_schema_pass_count']}/{row['parquet_schema_audit_count']}`.
- Proof/hash pass: proof values `{row['proof_value_pass_count']}/{row['proof_hash_audit_count']}`, raw hash matches `{row['raw_sha256_match_count']}`.
- Package gate pass: `{row['package_gate_pass_count']}/{row['package_gate_count']}`.

## Drop root inventory

{_md_table(root_inventory, max_rows=20)}

## File role coverage

{_md_table(role_view, max_rows=30)}

## Request coverage

{_md_table(request_view, max_rows=20)}

## Parquet schema sample

{_md_table(parquet_schema[['drop_root', 'request_id', 'exists', 'parquet_readable', 'parquet_row_count', 'present_required_field_count', 'required_field_count', 'parquet_schema_pass', 'parquet_read_error']], max_rows=20)}

## Proof and hash sample

{_md_table(proof_hash[['drop_root', 'request_id', 'proof_exists', 'present_required_proof_field_count', 'required_proof_field_count', 'raw_sha256_present', 'raw_sha256_match', 'sequence_gap_zero', 'time_span_ok', 'proof_value_pass']], max_rows=20)}

## Package gate

{_md_table(package_gate, max_rows=70)}

## Next action

{_md_table(next_action, max_rows=20)}
"""


def main() -> None:
    inputs = _load_inputs()
    roots = _drop_roots(inputs["stage135_drop_dirs"])
    files_by_root = _file_cache(roots)
    curve = _official_curve(inputs["stage251_curve"])
    file_role = _file_role_audit(inputs, roots, files_by_root)
    root_inventory = _drop_root_inventory(roots, files_by_root, file_role)
    parquet_schema = _parquet_schema_audit(inputs, file_role)
    proof_hash = _proof_hash_audit(inputs, file_role)
    request_audit = _request_package_audit(inputs, roots, file_role, parquet_schema, proof_hash)
    package_gate = _package_gate(root_inventory, request_audit, parquet_schema, proof_hash)
    next_action = _next_action(root_inventory, package_gate)
    summary = _summary(inputs, root_inventory, file_role, request_audit, parquet_schema, proof_hash, package_gate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(root_inventory, DROP_ROOT_INVENTORY_OUT)
    _write_csv(file_role, FILE_ROLE_AUDIT_OUT)
    _write_csv(request_audit, REQUEST_AUDIT_OUT)
    _write_csv(parquet_schema, PARQUET_SCHEMA_AUDIT_OUT)
    _write_csv(proof_hash, PROOF_HASH_AUDIT_OUT)
    _write_csv(package_gate, PACKAGE_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_official_path(curve, summary)
    _plot_drop_root(root_inventory)
    _plot_file_role(file_role)
    _plot_request_heatmap(request_audit)
    _plot_schema_proof(parquet_schema, proof_hash)
    _plot_package_gate(package_gate)

    report_text = _report(summary, root_inventory, file_role, request_audit, parquet_schema, proof_hash, package_gate, next_action)
    _write_text(REPORT_OUT, report_text)
    _write_json(
        DECISION_OUT,
        {
            "summary": _row(summary),
            "package_gate": package_gate.to_dict(orient="records"),
            "outputs": {
                "summary": SUMMARY_OUT,
                "drop_root_inventory": DROP_ROOT_INVENTORY_OUT,
                "file_role_audit": FILE_ROLE_AUDIT_OUT,
                "request_package_audit": REQUEST_AUDIT_OUT,
                "parquet_schema_audit": PARQUET_SCHEMA_AUDIT_OUT,
                "proof_hash_audit": PROOF_HASH_AUDIT_OUT,
                "package_gate": PACKAGE_GATE_OUT,
                "next_action": NEXT_ACTION_OUT,
                "report": REPORT_OUT,
                "charts": [
                    PATH_CHART_OUT,
                    DROP_ROOT_CHART_OUT,
                    FILE_ROLE_CHART_OUT,
                    REQUEST_HEATMAP_OUT,
                    SCHEMA_PROOF_CHART_OUT,
                    PACKAGE_GATE_CHART_OUT,
                ],
            },
        },
    )
    print(json.dumps(_row(summary), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
