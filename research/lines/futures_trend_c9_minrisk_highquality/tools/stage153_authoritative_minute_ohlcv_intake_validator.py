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
import pyarrow.parquet as pq


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage153"
MODEL_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"

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
STAGE152_SUMMARY_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_summary_{STAGE152_TAG}.csv"
STAGE152_FIELD_SCHEMA_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_field_schema_{STAGE152_TAG}.csv"
STAGE152_WINDOW_CONTRACT_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_required_window_contract_{STAGE152_TAG}.csv"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_file_audit_{MODEL_TAG}.csv"
PROOF_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_json_audit_{MODEL_TAG}.csv"
SCHEMA_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_schema_audit_{MODEL_TAG}.csv"
WINDOW_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_coverage_audit_{MODEL_TAG}.csv"
FAILURE_QUEUE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_failure_queue_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_intake_status_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_role_presence_heatmap_{MODEL_TAG}.png"
SCHEMA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_canonical_schema_readiness_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_coverage_heatmap_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

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
PROOF_REQUIRED_FIELDS = [
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
FORBIDDEN_PROVENANCE_MARKERS = [
    "synthetic",
    "smoke",
    "fixture",
    "stage131",
    "positive_drop",
    "template_only",
    "<",
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
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _resolve_path(path_text: Any) -> Path:
    path = Path("" if pd.isna(path_text) else str(path_text))
    return path if path.is_absolute() else REPO_DIR / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validator records exact failure reason.
        return {}, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, "proof_json_not_object"
    return payload, ""


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


def _audit_proof(row: pd.Series, raw_path: Path, proof_path: Path, raw_sha256: str | None) -> dict[str, Any]:
    base = {
        "request_id": row["request_id"],
        "proof_path": str(proof_path),
        "proof_file_present": int(proof_path.exists()),
        "proof_json_valid": 0,
        "proof_required_field_count": len(PROOF_REQUIRED_FIELDS),
        "proof_required_field_present_count": 0,
        "proof_missing_fields": ",".join(PROOF_REQUIRED_FIELDS),
        "proof_identity_match": 0,
        "proof_time_span_cover_request": 0,
        "proof_raw_sha256_match": 0,
        "proof_no_trade_policy_declared": 0,
        "proof_synthetic_or_adjusted_flag_clean": 0,
        "proof_forbidden_marker_count": 0,
        "proof_forbidden_markers": "",
        "proof_error": "",
    }
    if not proof_path.exists():
        base["proof_error"] = "missing_proof_file"
        return base
    payload, error = _load_json(proof_path)
    if error:
        base["proof_error"] = error
        marker_count, markers = _forbidden_marker_count(payload, [proof_path])
        base["proof_forbidden_marker_count"] = marker_count
        base["proof_forbidden_markers"] = markers
        return base
    present_fields = [field for field in PROOF_REQUIRED_FIELDS if payload.get(field) not in (None, "", [])]
    missing_fields = [field for field in PROOF_REQUIRED_FIELDS if field not in present_fields]
    marker_count, markers = _forbidden_marker_count(payload, [proof_path, raw_path])
    start = pd.to_datetime(payload.get("request_start_ts"), errors="coerce")
    end = pd.to_datetime(payload.get("request_end_ts"), errors="coerce")
    expected_start = pd.to_datetime(row.get("request_start_ts"), errors="coerce")
    expected_end = pd.to_datetime(row.get("request_end_ts"), errors="coerce")
    synthetic_flag = payload.get("synthetic_or_adjusted_flag")
    synthetic_clean = int(str(synthetic_flag).strip().lower() in {"0", "false", "no", "clean"})
    base.update(
        {
            "proof_json_valid": 1,
            "proof_required_field_present_count": len(present_fields),
            "proof_missing_fields": ",".join(missing_fields),
            "proof_identity_match": int(
                str(payload.get("request_id", "")) == str(row["request_id"])
                and str(payload.get("exchange", "")) == str(row["exchange"])
                and str(payload.get("vt_symbol", "")) == str(row["vt_symbol"])
            ),
            "proof_time_span_cover_request": int(
                pd.notna(start)
                and pd.notna(end)
                and pd.notna(expected_start)
                and pd.notna(expected_end)
                and start <= expected_start
                and end >= expected_end
            ),
            "proof_raw_sha256_match": int(bool(raw_sha256) and str(payload.get("raw_sha256", "")).lower() == raw_sha256),
            "proof_no_trade_policy_declared": int(bool(str(payload.get("no_trade_bar_policy", "")).strip())),
            "proof_synthetic_or_adjusted_flag_clean": synthetic_clean,
            "proof_forbidden_marker_count": marker_count,
            "proof_forbidden_markers": markers,
        }
    )
    return base


def _audit_schema(row: pd.Series, normalized_path: Path) -> dict[str, Any]:
    base = {
        "request_id": row["request_id"],
        "normalized_path": str(normalized_path),
        "normalized_file_present": int(normalized_path.exists()),
        "parquet_readable": 0,
        "row_count": 0,
        "required_column_count": len(NORMALIZED_REQUIRED_COLUMNS),
        "required_column_present_count": 0,
        "missing_required_columns": ",".join(NORMALIZED_REQUIRED_COLUMNS),
        "optional_turnover_present": 0,
        "optional_open_interest_present": 0,
        "normalized_schema_pass": 0,
        "schema_error": "",
    }
    if not normalized_path.exists():
        base["schema_error"] = "missing_normalized_file"
        return base
    try:
        parquet_file = pq.ParquetFile(normalized_path)
        columns = list(parquet_file.schema.names)
        row_count = int(parquet_file.metadata.num_rows)
    except Exception as exc:  # noqa: BLE001 - validator records exact failure reason.
        base["schema_error"] = f"{type(exc).__name__}: {exc}"
        return base
    present = [column for column in NORMALIZED_REQUIRED_COLUMNS if column in columns]
    missing = [column for column in NORMALIZED_REQUIRED_COLUMNS if column not in columns]
    base.update(
        {
            "parquet_readable": 1,
            "row_count": row_count,
            "required_column_present_count": len(present),
            "missing_required_columns": ",".join(missing),
            "optional_turnover_present": int("turnover" in columns),
            "optional_open_interest_present": int("open_interest" in columns),
            "normalized_schema_pass": int(len(missing) == 0 and row_count > 0),
        }
    )
    return base


def _audit_requests(requests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    request_records: list[dict[str, Any]] = []
    proof_records: list[dict[str, Any]] = []
    schema_records: list[dict[str, Any]] = []
    loaded_bars: dict[str, pd.DataFrame] = {}
    for _, row in requests.iterrows():
        raw_path = _resolve_path(row["expected_raw_file"])
        normalized_path = _resolve_path(row["expected_normalized_file"])
        proof_path = _resolve_path(row["expected_proof_file"])
        raw_present = raw_path.exists()
        raw_sha = _sha256(raw_path) if raw_present else None
        raw_size = raw_path.stat().st_size if raw_present else 0
        proof_audit = _audit_proof(row, raw_path, proof_path, raw_sha)
        schema_audit = _audit_schema(row, normalized_path)
        proof_records.append(proof_audit)
        schema_records.append(schema_audit)
        request_ready = int(
            raw_present
            and proof_audit["proof_json_valid"] == 1
            and proof_audit["proof_required_field_present_count"] == len(PROOF_REQUIRED_FIELDS)
            and proof_audit["proof_identity_match"] == 1
            and proof_audit["proof_time_span_cover_request"] == 1
            and proof_audit["proof_raw_sha256_match"] == 1
            and proof_audit["proof_no_trade_policy_declared"] == 1
            and proof_audit["proof_synthetic_or_adjusted_flag_clean"] == 1
            and proof_audit["proof_forbidden_marker_count"] == 0
            and schema_audit["normalized_schema_pass"] == 1
        )
        if request_ready:
            try:
                bars = pd.read_parquet(
                    normalized_path,
                    columns=list(dict.fromkeys(NORMALIZED_REQUIRED_COLUMNS + ["turnover", "open_interest"])),
                )
                loaded_bars[str(row["request_id"])] = bars
            except Exception:
                request_ready = 0
        request_records.append(
            {
                "request_id": row["request_id"],
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "request_date": row["request_date"],
                "expected_raw_file": str(raw_path),
                "expected_normalized_file": str(normalized_path),
                "expected_proof_file": str(proof_path),
                "raw_file_present": int(raw_present),
                "raw_file_size": int(raw_size),
                "raw_sha256": raw_sha or "",
                "proof_file_present": int(proof_path.exists()),
                "normalized_file_present": int(normalized_path.exists()),
                "proof_json_valid": int(proof_audit["proof_json_valid"]),
                "proof_raw_sha256_match": int(proof_audit["proof_raw_sha256_match"]),
                "proof_identity_match": int(proof_audit["proof_identity_match"]),
                "proof_forbidden_marker_count": int(proof_audit["proof_forbidden_marker_count"]),
                "normalized_schema_pass": int(schema_audit["normalized_schema_pass"]),
                "request_ready": request_ready,
                "stage154_feature_build_allowed": 0,
            }
        )
    return pd.DataFrame(request_records), pd.DataFrame(proof_records), pd.DataFrame(schema_records), loaded_bars


def _map_windows_to_requests(windows: pd.DataFrame, requests: pd.DataFrame) -> pd.DataFrame:
    keys = ["exchange", "product", "vt_symbol", "request_date"]
    request_key = requests[keys + ["request_id"]].drop_duplicates()
    mapped = windows.merge(request_key, how="left", on=keys)
    mapped["request_id"] = mapped["request_id"].fillna("")
    return mapped


def _window_coverage(
    windows: pd.DataFrame,
    request_audit: pd.DataFrame,
    proof_audit: pd.DataFrame,
    loaded_bars: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    request_ready = request_audit.set_index("request_id")["request_ready"].to_dict()
    proof_no_trade = proof_audit.set_index("request_id")["proof_no_trade_policy_declared"].to_dict()
    proof_span = proof_audit.set_index("request_id")["proof_time_span_cover_request"].to_dict()
    records: list[dict[str, Any]] = []
    for _, row in windows.iterrows():
        request_id = str(row.get("request_id", ""))
        bars = loaded_bars.get(request_id)
        observed_count = 0
        duplicate_count = 0
        sequence_gap_count = int(row.get("estimated_required_1m_bars", 0))
        real_volume_positive_count = 0
        if bars is not None and not bars.empty:
            bar_frame = bars.copy()
            bar_frame["bar_start_ts"] = pd.to_datetime(bar_frame["bar_start_ts"], errors="coerce")
            start = pd.to_datetime(row["window_start_ts"], errors="coerce")
            end = pd.to_datetime(row["window_end_ts"], errors="coerce")
            mask = (
                bar_frame["bar_start_ts"].notna()
                & bar_frame["bar_start_ts"].ge(start)
                & bar_frame["bar_start_ts"].le(end)
                & bar_frame["vt_symbol"].astype(str).eq(str(row["vt_symbol"]))
            )
            window_bars = bar_frame.loc[mask].copy()
            observed_count = int(len(window_bars))
            if observed_count > 0:
                duplicate_count = int(window_bars["bar_start_ts"].duplicated().sum())
                unique_slots = int(window_bars["bar_start_ts"].nunique())
                sequence_gap_count = max(int(row.get("estimated_required_1m_bars", 0)) - unique_slots, 0)
                real_volume_positive_count = int(pd.to_numeric(window_bars["volume"], errors="coerce").fillna(0).gt(0).sum())
        coverage_pass = int(
            request_ready.get(request_id, 0) == 1
            and proof_no_trade.get(request_id, 0) == 1
            and proof_span.get(request_id, 0) == 1
            and observed_count > 0
            and duplicate_count == 0
            and real_volume_positive_count > 0
        )
        records.append(
            {
                "window_id": row["window_id"],
                "request_id": request_id,
                "vt_symbol": row["vt_symbol"],
                "exchange": row["exchange"],
                "product": row["product"],
                "window_type": row["window_type"],
                "window_start_ts": row["window_start_ts"],
                "window_end_ts": row["window_end_ts"],
                "priority_class": row["priority_class"],
                "right_tail_visual": int(row["right_tail_visual"]),
                "bottom_loss_visual": int(row["bottom_loss_visual"]),
                "maxdd_context": int(row["maxdd_context"]),
                "low_resolution_zone": int(row["low_resolution_zone"]),
                "estimated_required_1m_bars": int(row["estimated_required_1m_bars"]),
                "observed_bar_count": observed_count,
                "sequence_gap_count": sequence_gap_count,
                "duplicate_bar_count": duplicate_count,
                "real_volume_positive_bar_count": real_volume_positive_count,
                "coverage_pass": coverage_pass,
                "rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _failure_queue(
    requests: pd.DataFrame,
    request_audit: pd.DataFrame,
    proof_audit: pd.DataFrame,
    schema_audit: pd.DataFrame,
    window_coverage: pd.DataFrame,
) -> pd.DataFrame:
    request_count = int(len(requests))
    missing_raw = request_count - int(request_audit["raw_file_present"].sum())
    missing_proof = request_count - int(request_audit["proof_file_present"].sum())
    missing_norm = request_count - int(request_audit["normalized_file_present"].sum())
    bad_proof = request_count - int(proof_audit["proof_json_valid"].sum())
    bad_schema = request_count - int(schema_audit["normalized_schema_pass"].sum())
    uncovered_windows = int(len(window_coverage)) - int(window_coverage["coverage_pass"].sum())
    rows = [
        (1, "deliver_raw_files", missing_raw, "Place immutable licensed raw files at every expected_raw_file path."),
        (2, "deliver_proof_json", missing_proof, "Provide proof JSON with vendor, license, query, session, no-trade policy, and raw SHA256."),
        (3, "deliver_normalized_parquet", missing_norm, "Provide canonical normalized Parquet files with required OHLCV columns."),
        (4, "fix_proof_validation", bad_proof, "Repair malformed or incomplete proof JSON before any schema/window coverage work."),
        (5, "fix_normalized_schema", bad_schema, "Repair unreadable, empty, or non-canonical normalized Parquet files."),
        (6, "verify_window_coverage", uncovered_windows, "Cover every Stage152 required window, including right-tail and bottom-loss windows."),
        (7, "rerun_stage153", int(uncovered_windows > 0 or missing_raw > 0 or missing_proof > 0 or missing_norm > 0), "Rerun this validator after files are delivered."),
    ]
    return pd.DataFrame(
        [
            {
                "priority": priority,
                "action_id": action_id,
                "blocking_count": count,
                "ready_now": int(count == 0),
                "action": action,
            }
            for priority, action_id, count, action in rows
        ]
    )


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage152_contract_loaded", summary["stage152_contract_loaded"], 1, "contract_hard"),
        ("request_audit_generated", summary["request_audit_ready"], 1, "audit_hard"),
        ("all_raw_files_present", summary["raw_file_present_count"], summary["request_count"], "data_hard"),
        ("all_proof_files_present", summary["proof_file_present_count"], summary["request_count"], "data_hard"),
        ("all_normalized_files_present", summary["normalized_file_present_count"], summary["request_count"], "data_hard"),
        ("all_proof_json_valid", summary["proof_json_valid_count"], summary["request_count"], "provenance_hard"),
        ("all_raw_sha256_match", summary["proof_raw_sha256_match_count"], summary["request_count"], "provenance_hard"),
        ("all_normalized_schema_pass", summary["normalized_schema_pass_count"], summary["request_count"], "schema_hard"),
        ("all_required_windows_covered", summary["window_coverage_pass_count"], summary["required_window_count"], "coverage_hard"),
        ("right_tail_windows_covered", summary["right_tail_window_coverage_pass_count"], summary["right_tail_required_window_count"], "coverage_hard"),
        ("bottom_loss_windows_covered", summary["bottom_loss_window_coverage_pass_count"], summary["bottom_loss_required_window_count"], "coverage_hard"),
        ("maxdd_windows_covered", summary["maxdd_window_coverage_pass_count"], summary["maxdd_required_window_count"], "coverage_hard"),
        ("forbidden_provenance_marker_count", summary["forbidden_provenance_marker_count"], 0, "anti_fixture_hard"),
        ("stage154_feature_build_allowed", summary["stage154_feature_build_allowed"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
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
    request_audit: pd.DataFrame,
    proof_audit: pd.DataFrame,
    schema_audit: pd.DataFrame,
    window_coverage: pd.DataFrame,
    failure_queue: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    request_cols = [
        "request_id",
        "exchange",
        "vt_symbol",
        "raw_file_present",
        "proof_file_present",
        "normalized_file_present",
        "proof_json_valid",
        "normalized_schema_pass",
        "request_ready",
    ]
    window_cols = [
        "window_id",
        "request_id",
        "vt_symbol",
        "window_type",
        "priority_class",
        "observed_bar_count",
        "sequence_gap_count",
        "coverage_pass",
    ]
    lines = [
        f"# {STAGE} 权威分钟 OHLCV 到货验收器",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只验收 Stage152 数据合同，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Databento OHLCV 文档说明 OHLCV 是从成交聚合而来；其 resampling 资料还说明多数 vendor 只在有成交区间发布 bar。因此 Stage153 不能把 sequence gap 直接当 alpha，必须结合 proof 里的 no-trade policy。",
        "- Apache Parquet 官方文档强调 Parquet 文件有独立 metadata/schema；Stage153 因此优先读取 Parquet metadata 做 schema 和 row count 验收，避免先把不可信文件加载成策略特征。",
        "- IBKR historical bars 文档提示 futures session 可能跨自然日；Stage153 因此把 request_start/end、timezone 和 session_calendar 作为 proof 硬字段。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Request Audit Sample",
        "",
        _md_table(request_audit[request_cols], max_rows=20),
        "",
        "## Proof Audit Sample",
        "",
        _md_table(proof_audit, max_rows=20),
        "",
        "## Schema Audit Sample",
        "",
        _md_table(schema_audit, max_rows=20),
        "",
        "## Window Coverage Sample",
        "",
        _md_table(window_coverage[window_cols], max_rows=20),
        "",
        "## Operator Failure Queue",
        "",
        _md_table(failure_queue),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{ROLE_CHART_OUT.name}`",
        f"- `{SCHEMA_CHART_OUT.name}`",
        f"- `{WINDOW_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage153 authoritative 1m OHLCV intake status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["requests", "raw", "proof", "parquet", "windows", "release"]
    values = [
        row["request_count"],
        row["raw_file_present_count"],
        row["proof_file_present_count"],
        row["normalized_file_present_count"],
        row["window_coverage_pass_count"],
        row["stage154_feature_build_allowed"],
    ]
    colors = ["#3657D6", "#B91C1C", "#B91C1C", "#B91C1C", "#B91C1C", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("No real authorized files accepted; downstream feature build remains blocked")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_role_heatmap(request_audit: pd.DataFrame) -> None:
    role_cols = ["raw_file_present", "proof_file_present", "normalized_file_present", "request_ready"]
    matrix = request_audit.groupby("exchange", dropna=False)[role_cols].sum().sort_index()
    fig, ax = plt.subplots(figsize=(9, max(4.5, len(matrix) * 0.8)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Stage153 request role presence by exchange")
    ax.set_xticks(np.arange(len(role_cols)))
    ax.set_xticklabels(role_cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_schema_matrix(schema: pd.DataFrame, schema_audit: pd.DataFrame) -> None:
    frame = schema[["field", "hard_gate"]].copy()
    observed_count = int(schema_audit["normalized_schema_pass"].sum()) if not schema_audit.empty else 0
    normalized_columns = set(NORMALIZED_REQUIRED_COLUMNS)
    proof_fields = set(PROOF_REQUIRED_FIELDS)
    frame["normalized_required_column"] = frame["field"].isin(normalized_columns).astype(int)
    frame["proof_required_field"] = frame["field"].isin(proof_fields).astype(int)
    frame["accepted_request_observed"] = int(observed_count > 0)
    matrix = frame.set_index("field")[["hard_gate", "normalized_required_column", "proof_required_field", "accepted_request_observed"]]
    fig, ax = plt.subplots(figsize=(10, max(5.2, len(matrix) * 0.38)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Canonical schema contract vs accepted data readiness")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=7)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(SCHEMA_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_window_heatmap(window_coverage: pd.DataFrame) -> None:
    priority_order = ["right_tail", "bottom_loss", "maxdd_context", "low_resolution", "ordinary"]
    total = pd.crosstab(window_coverage["window_type"], window_coverage["priority_class"]).reindex(columns=priority_order, fill_value=0)
    passed = pd.crosstab(
        window_coverage["window_type"],
        window_coverage["priority_class"],
        values=window_coverage["coverage_pass"],
        aggfunc="sum",
    ).reindex(index=total.index, columns=priority_order, fill_value=0)
    ratio = passed.divide(total.replace(0, np.nan)).fillna(0)
    fig, ax = plt.subplots(figsize=(12, 5.6))
    data = ratio.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Required window coverage pass ratio")
    ax.set_xticks(np.arange(len(ratio.columns)))
    ax.set_xticklabels(ratio.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(ratio.index)))
    ax.set_yticklabels(ratio.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, f"{int(passed.iloc[row, col])}/{int(total.iloc[row, col])}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate_matrix(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]].copy()
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.45)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage153 gate status")
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
    stage152 = _row(STAGE152_SUMMARY_IN)
    if not stage152:
        raise RuntimeError(f"missing Stage152 summary input: {STAGE152_SUMMARY_IN}")
    schema = _read_csv(STAGE152_FIELD_SCHEMA_IN)
    requests = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    windows = _read_csv(STAGE152_WINDOW_CONTRACT_IN)
    if schema.empty or requests.empty or windows.empty:
        raise RuntimeError("missing Stage152 contract inputs")

    request_audit, proof_audit, schema_audit, loaded_bars = _audit_requests(requests)
    mapped_windows = _map_windows_to_requests(windows, requests)
    window_coverage = _window_coverage(mapped_windows, request_audit, proof_audit, loaded_bars)
    failure_queue = _failure_queue(requests, request_audit, proof_audit, schema_audit, window_coverage)

    decision = "stage153_authoritative_minute_ohlcv_intake_blocks_missing_real_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "deliver_real_authoritative_minute_ohlcv_files_then_rerun_stage153",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage152_contract_loaded": 1,
        "request_audit_ready": 1,
        "request_count": int(len(requests)),
        "required_window_count": int(len(window_coverage)),
        "raw_file_present_count": int(request_audit["raw_file_present"].sum()),
        "proof_file_present_count": int(request_audit["proof_file_present"].sum()),
        "normalized_file_present_count": int(request_audit["normalized_file_present"].sum()),
        "proof_json_valid_count": int(proof_audit["proof_json_valid"].sum()),
        "proof_raw_sha256_match_count": int(proof_audit["proof_raw_sha256_match"].sum()),
        "proof_identity_match_count": int(proof_audit["proof_identity_match"].sum()),
        "proof_no_trade_policy_declared_count": int(proof_audit["proof_no_trade_policy_declared"].sum()),
        "normalized_schema_pass_count": int(schema_audit["normalized_schema_pass"].sum()),
        "request_ready_count": int(request_audit["request_ready"].sum()),
        "window_coverage_pass_count": int(window_coverage["coverage_pass"].sum()),
        "right_tail_required_window_count": int(window_coverage["right_tail_visual"].sum()),
        "bottom_loss_required_window_count": int(window_coverage["bottom_loss_visual"].sum()),
        "maxdd_required_window_count": int(window_coverage["maxdd_context"].sum()),
        "low_resolution_required_window_count": int(window_coverage["low_resolution_zone"].sum()),
        "right_tail_window_coverage_pass_count": int(
            window_coverage.loc[window_coverage["right_tail_visual"].eq(1), "coverage_pass"].sum()
        ),
        "bottom_loss_window_coverage_pass_count": int(
            window_coverage.loc[window_coverage["bottom_loss_visual"].eq(1), "coverage_pass"].sum()
        ),
        "maxdd_window_coverage_pass_count": int(
            window_coverage.loc[window_coverage["maxdd_context"].eq(1), "coverage_pass"].sum()
        ),
        "low_resolution_window_coverage_pass_count": int(
            window_coverage.loc[window_coverage["low_resolution_zone"].eq(1), "coverage_pass"].sum()
        ),
        "forbidden_provenance_marker_count": int(proof_audit["proof_forbidden_marker_count"].sum()),
        "stage154_feature_build_allowed": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage152.get("end_equity", np.nan)),
        "total_return_pct": float(stage152.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage152.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage152.get("sharpe", np.nan)),
        "total_slippage": float(stage152.get("total_slippage", np.nan)),
        "total_trade_count": float(stage152.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage152.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage152.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(request_audit, REQUEST_AUDIT_OUT)
    _write_csv(proof_audit, PROOF_AUDIT_OUT)
    _write_csv(schema_audit, SCHEMA_AUDIT_OUT)
    _write_csv(window_coverage, WINDOW_COVERAGE_OUT)
    _write_csv(failure_queue, FAILURE_QUEUE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, request_audit, proof_audit, schema_audit, window_coverage, failure_queue, gate)

    _plot_path(curve, summary)
    _plot_role_heatmap(request_audit)
    _plot_schema_matrix(schema, schema_audit)
    _plot_window_heatmap(window_coverage)
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
                "stage152_summary": str(STAGE152_SUMMARY_IN),
                "stage152_field_schema": str(STAGE152_FIELD_SCHEMA_IN),
                "stage152_required_window_contract": str(STAGE152_WINDOW_CONTRACT_IN),
                "stage152_request_manifest_template": str(STAGE152_REQUEST_TEMPLATE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "request_file_audit": str(REQUEST_AUDIT_OUT),
                "proof_json_audit": str(PROOF_AUDIT_OUT),
                "normalized_schema_audit": str(SCHEMA_AUDIT_OUT),
                "window_coverage_audit": str(WINDOW_COVERAGE_OUT),
                "operator_failure_queue": str(FAILURE_QUEUE_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(ROLE_CHART_OUT),
                    str(SCHEMA_CHART_OUT),
                    str(WINDOW_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://databento.com/docs/schemas-and-data-formats/ohlcv",
                "https://databento.com/docs/examples/basics-historical/ohlcv-resampling",
                "https://parquet.apache.org/docs/file-format/",
                "https://interactivebrokers.github.io/tws-api/historical_bars.html",
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
                "stage154_feature_build_allowed": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
