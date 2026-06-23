from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage117"
MODEL_TAG = "stage117_wave0_delivery_verifier_v1"
OUTPUT_PREFIX = "qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage117_wave0_delivery_verifier"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE116_DIR = LINE_DIR / "outputs" / "stage116_wave0_pipeline_intake_packet"
STAGE116_SUMMARY_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_summary_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_REQUEST_PACKET_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_packet_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
DEFAULT_MANIFEST_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_request_delivery_status_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_delivery_gate_status_{MODEL_TAG}.csv"
ISSUE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_delivery_issues_{MODEL_TAG}.csv"
FILE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_file_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_delivery_status_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_chart_{MODEL_TAG}.png"
COMPLETENESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_completeness_matrix_{MODEL_TAG}.png"
REQUEST_TIMELINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_timeline_status_{MODEL_TAG}.png"

DECISION = "stage117_wave0_delivery_missing_no_data_no_rule"
ACCEPT_DECISION = "stage117_wave0_delivery_accepted_stage112_intake_only_no_strategy"
WAVE_ID = "W0_pipeline_smoke"

REQUIRED_MANIFEST_COLUMNS = [
    "wave_id",
    "request_id",
    "batch_id",
    "vendor",
    "license_id",
    "dataset",
    "required_schema_request",
    "schema_delivered",
    "exchange",
    "product",
    "vt_symbol",
    "trading_day",
    "request_start",
    "request_end",
    "covered_window_ids",
    "raw_file",
    "raw_sha256",
    "normalized_parquet_file",
    "proof_file",
    "schema_hash",
    "field_dictionary_version",
    "ts_event_timezone",
    "ts_recv_timezone",
    "first_ts_event",
    "last_ts_event",
    "row_count",
    "sequence_gap_count",
    "capture_continuity_proof",
    "acceptance_status",
    "strategy_use_allowed_now",
    "rule_preflight_allowed_now",
]

REQUIRED_PARQUET_FIELDS = {"ts_event", "ts_recv"}


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


def _resolve_path(value: Any, manifest_dir: Path) -> Path | None:
    text = _clean(value)
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (manifest_dir / path).resolve()
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_audit(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "parquet_readable": 0,
            "parquet_schema_fields": "",
            "parquet_missing_required_fields": "ts_event;ts_recv",
            "parquet_row_count": np.nan,
            "parquet_error": "normalized_parquet_file_missing",
        }
    if not path.exists():
        return {
            "parquet_readable": 0,
            "parquet_schema_fields": "",
            "parquet_missing_required_fields": "ts_event;ts_recv",
            "parquet_row_count": np.nan,
            "parquet_error": "normalized_parquet_file_not_found",
        }
    try:
        import pyarrow.parquet as pq

        metadata = pq.read_metadata(path)
        fields = list(metadata.schema.names)
        missing = sorted(REQUIRED_PARQUET_FIELDS.difference(fields))
        return {
            "parquet_readable": 1,
            "parquet_schema_fields": ";".join(fields),
            "parquet_missing_required_fields": ";".join(missing),
            "parquet_row_count": int(metadata.num_rows),
            "parquet_error": "",
        }
    except Exception as exc:  # pragma: no cover - depends on delivered files and local parquet backend.
        return {
            "parquet_readable": 0,
            "parquet_schema_fields": "",
            "parquet_missing_required_fields": "ts_event;ts_recv",
            "parquet_row_count": np.nan,
            "parquet_error": type(exc).__name__,
        }


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


def _load_inputs(manifest_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    request_packet = _read_csv(STAGE116_REQUEST_PACKET_IN)
    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    manifest = _read_csv(manifest_path)
    if request_packet.empty:
        raise RuntimeError("missing Stage116 W0 request packet")
    if manifest.empty:
        raise RuntimeError(f"manifest is empty or missing: {manifest_path}")
    for frame in [request_packet, manifest]:
        for column in ["trading_day", "request_start", "request_end", "first_ts_event", "last_ts_event"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return request_packet, manifest, stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object)


def _build_request_status(request_packet: pd.DataFrame, manifest: pd.DataFrame, manifest_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest_columns = set(manifest.columns)
    missing_columns = [column for column in REQUIRED_MANIFEST_COLUMNS if column not in manifest_columns]
    manifest_dir = manifest_path.parent
    status_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []

    merged = request_packet.merge(
        manifest,
        on="request_id",
        how="left",
        suffixes=("_expected", "_manifest"),
        indicator=True,
    )

    for missing_column in missing_columns:
        issue_rows.append(
            {
                "request_id": "",
                "severity": "manifest_hard",
                "issue_code": "manifest_missing_column",
                "detail": missing_column,
            }
        )

    for _, row in merged.iterrows():
        request_id = _clean(row.get("request_id"))
        row_issues: list[str] = []

        missing_manifest_row = row["_merge"] != "both"
        if missing_manifest_row:
            row_issues.append("missing_manifest_row")

        raw_file = _resolve_path(row.get("raw_file"), manifest_dir)
        parquet_file = _resolve_path(row.get("normalized_parquet_file"), manifest_dir)
        proof_file = _resolve_path(row.get("proof_file"), manifest_dir)
        expected_sha = _clean(row.get("raw_sha256")).lower()
        actual_sha = ""

        raw_exists = int(raw_file is not None and raw_file.exists())
        parquet_exists = int(parquet_file is not None and parquet_file.exists())
        proof_exists = int(proof_file is not None and proof_file.exists())

        if raw_file is None:
            row_issues.append("raw_file_missing")
        elif not raw_file.exists():
            row_issues.append("raw_file_not_found")
        else:
            actual_sha = _sha256_file(raw_file)
        if not expected_sha:
            row_issues.append("raw_sha256_missing")
        elif actual_sha and actual_sha != expected_sha:
            row_issues.append("raw_sha256_mismatch")

        if parquet_file is None:
            row_issues.append("normalized_parquet_file_missing")
        elif not parquet_file.exists():
            row_issues.append("normalized_parquet_file_not_found")
        parquet_audit = _parquet_audit(parquet_file)
        if not parquet_audit["parquet_readable"]:
            row_issues.append("parquet_not_readable")
        if _clean(parquet_audit["parquet_missing_required_fields"]):
            row_issues.append("parquet_missing_required_fields")
        parquet_row_count = pd.to_numeric(
            pd.Series([parquet_audit.get("parquet_row_count")]),
            errors="coerce",
        ).iloc[0]
        parquet_row_count_positive = int(pd.notna(parquet_row_count) and float(parquet_row_count) > 0)
        if not parquet_row_count_positive:
            row_issues.append("parquet_row_count_not_positive")

        if proof_file is None:
            row_issues.append("proof_file_missing")
        elif not proof_file.exists():
            row_issues.append("proof_file_not_found")
        if not _clean(row.get("schema_hash")):
            row_issues.append("schema_hash_missing")
        if not _clean(row.get("field_dictionary_version")):
            row_issues.append("field_dictionary_version_missing")
        if not _clean(row.get("ts_event_timezone")):
            row_issues.append("ts_event_timezone_missing")
        if not _clean(row.get("ts_recv_timezone")):
            row_issues.append("ts_recv_timezone_missing")
        if not _clean(row.get("capture_continuity_proof")):
            row_issues.append("capture_continuity_proof_missing")

        sequence_gap_count = pd.to_numeric(pd.Series([row.get("sequence_gap_count")]), errors="coerce").iloc[0]
        sequence_gap_zero = int(pd.notna(sequence_gap_count) and float(sequence_gap_count) == 0.0)
        if not sequence_gap_zero:
            row_issues.append("sequence_gap_zero_not_proven")

        row_count = pd.to_numeric(pd.Series([row.get("row_count")]), errors="coerce").iloc[0]
        row_count_positive = int(pd.notna(row_count) and float(row_count) > 0)
        if not row_count_positive:
            row_issues.append("row_count_not_positive")

        strategy_values = [
            row.get(column)
            for column in ["strategy_use_allowed_now", "strategy_use_allowed_now_manifest", "strategy_use_allowed_now_expected"]
            if column in row.index
        ]
        preflight_values = [
            row.get(column)
            for column in ["rule_preflight_allowed_now", "rule_preflight_allowed_now_manifest", "rule_preflight_allowed_now_expected"]
            if column in row.index
        ]
        strategy_series = pd.to_numeric(pd.Series(strategy_values), errors="coerce").dropna()
        preflight_series = pd.to_numeric(pd.Series(preflight_values), errors="coerce").dropna()
        strategy_locked = int(
            not strategy_series.empty
            and not preflight_series.empty
            and strategy_series.eq(0).all()
            and preflight_series.eq(0).all()
        )
        if not strategy_locked:
            row_issues.append("strategy_lock_not_zero")

        request_start = pd.to_datetime(row.get("request_start_expected"), errors="coerce")
        request_end = pd.to_datetime(row.get("request_end_expected"), errors="coerce")
        first_ts = pd.to_datetime(row.get("first_ts_event"), errors="coerce")
        last_ts = pd.to_datetime(row.get("last_ts_event"), errors="coerce")
        time_span_ok = int(pd.notna(first_ts) and pd.notna(last_ts) and pd.notna(request_start) and pd.notna(request_end) and first_ts <= request_start and last_ts >= request_end)
        if not time_span_ok:
            row_issues.append("time_span_not_proven")

        file_rows.append(
            {
                "request_id": request_id,
                "raw_file": "" if raw_file is None else str(raw_file),
                "raw_exists": raw_exists,
                "raw_sha256_expected": expected_sha,
                "raw_sha256_actual": actual_sha,
                "raw_sha256_match": int(bool(expected_sha and actual_sha and expected_sha == actual_sha)),
                "normalized_parquet_file": "" if parquet_file is None else str(parquet_file),
                "parquet_exists": parquet_exists,
                **parquet_audit,
                "proof_file": "" if proof_file is None else str(proof_file),
                "proof_exists": proof_exists,
            }
        )

        for issue in sorted(set(row_issues)):
            issue_rows.append(
                {
                    "request_id": request_id,
                    "severity": "data_hard" if issue not in {"strategy_lock_not_zero"} else "anti_selection_hard",
                    "issue_code": issue,
                    "detail": "",
                }
            )

        hard_pass = int(
            not missing_manifest_row
            and raw_exists
            and parquet_exists
            and proof_exists
            and bool(expected_sha and actual_sha and expected_sha == actual_sha)
            and parquet_audit["parquet_readable"]
            and not _clean(parquet_audit["parquet_missing_required_fields"])
            and parquet_row_count_positive
            and sequence_gap_zero
            and row_count_positive
            and strategy_locked
            and time_span_ok
            and not missing_columns
        )
        status_rows.append(
            {
                "request_id": request_id,
                "batch_id": row.get("batch_id_expected", row.get("batch_id")),
                "vt_symbol": row.get("vt_symbol_expected", row.get("vt_symbol")),
                "exchange": row.get("exchange_expected", row.get("exchange")),
                "product": row.get("product_expected", row.get("product")),
                "year": row.get("year"),
                "trading_day": pd.to_datetime(row.get("trading_day_expected", row.get("trading_day")), errors="coerce"),
                "request_start": request_start,
                "request_end": request_end,
                "window_count": pd.to_numeric(row.get("window_count"), errors="coerce"),
                "raw_exists": raw_exists,
                "parquet_exists": parquet_exists,
                "proof_exists": proof_exists,
                "raw_sha256_match": int(bool(expected_sha and actual_sha and expected_sha == actual_sha)),
                "parquet_readable": int(parquet_audit["parquet_readable"]),
                "parquet_required_fields_present": int(not _clean(parquet_audit["parquet_missing_required_fields"])),
                "parquet_row_count_positive": parquet_row_count_positive,
                "sequence_gap_zero": sequence_gap_zero,
                "row_count_positive": row_count_positive,
                "time_span_ok": time_span_ok,
                "strategy_lock_zero": strategy_locked,
                "hard_accept": hard_pass,
                "issue_count": len(set(row_issues)),
                "issue_codes": ";".join(sorted(set(row_issues))),
            }
        )

    return pd.DataFrame(status_rows), pd.DataFrame(file_rows), pd.DataFrame(issue_rows)


def _build_gate_status(request_status: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    request_count = len(request_status)
    all_requests_hard_accept = int(request_status["hard_accept"].sum() == request_count and request_count > 0)
    gates = [
        ("manifest_nonempty", len(manifest), ">0", int(len(manifest) > 0), "manifest_hard"),
        ("request_count_matches_w0_packet", f"{manifest['request_id'].nunique()}/{request_count}", f"{request_count}/{request_count}", int(manifest["request_id"].nunique() == request_count), "manifest_hard"),
        ("request_id_unique", f"{manifest['request_id'].nunique()}/{len(manifest)}", f"{len(manifest)}/{len(manifest)}", int(manifest["request_id"].nunique() == len(manifest)), "manifest_hard"),
        ("strategy_locks_zero", f"{int(request_status['strategy_lock_zero'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["strategy_lock_zero"].sum() == request_count), "anti_selection_hard"),
        ("raw_files_exist", f"{int(request_status['raw_exists'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["raw_exists"].sum() == request_count), "data_hard"),
        ("parquet_files_exist", f"{int(request_status['parquet_exists'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["parquet_exists"].sum() == request_count), "data_hard"),
        ("proof_files_exist", f"{int(request_status['proof_exists'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["proof_exists"].sum() == request_count), "data_hard"),
        ("raw_sha256_match", f"{int(request_status['raw_sha256_match'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["raw_sha256_match"].sum() == request_count), "data_hard"),
        ("parquet_readable", f"{int(request_status['parquet_readable'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["parquet_readable"].sum() == request_count), "data_hard"),
        ("parquet_required_fields_present", f"{int(request_status['parquet_required_fields_present'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["parquet_required_fields_present"].sum() == request_count), "data_hard"),
        ("parquet_row_count_positive", f"{int(request_status['parquet_row_count_positive'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["parquet_row_count_positive"].sum() == request_count), "data_hard"),
        ("sequence_gap_zero", f"{int(request_status['sequence_gap_zero'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["sequence_gap_zero"].sum() == request_count), "data_hard"),
        ("row_count_positive", f"{int(request_status['row_count_positive'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["row_count_positive"].sum() == request_count), "data_hard"),
        ("time_span_covers_request", f"{int(request_status['time_span_ok'].sum())}/{request_count}", f"{request_count}/{request_count}", int(request_status["time_span_ok"].sum() == request_count), "data_hard"),
        ("all_requests_hard_accept", f"{int(request_status['hard_accept'].sum())}/{request_count}", f"{request_count}/{request_count}", all_requests_hard_accept, "data_hard"),
        ("stage112_intake_allowed", str(all_requests_hard_accept), "all hard gates pass first", all_requests_hard_accept, "data_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": pass_now,
                "severity": severity,
            }
            for gate_id, observed, required, pass_now, severity in gates
        ]
    )


def _build_summary(
    request_status: pd.DataFrame,
    gate_status: pd.DataFrame,
    issue_frame: pd.DataFrame,
    stage116_summary: pd.Series,
    manifest_path: Path,
) -> pd.DataFrame:
    request_count = len(request_status)
    accepted_count = int(request_status["hard_accept"].sum()) if request_count else 0
    accepted_window_count = int(pd.to_numeric(request_status.loc[request_status["hard_accept"].eq(1), "window_count"], errors="coerce").fillna(0).sum())
    total_window_count = int(pd.to_numeric(request_status["window_count"], errors="coerce").fillna(0).sum()) if request_count else 0
    data_gate_count = int(gate_status["severity"].eq("data_hard").sum())
    data_gate_pass_count = int(gate_status.loc[gate_status["severity"].eq("data_hard"), "pass_now"].sum())
    stage112_intake_allowed_now = int(
        gate_status.loc[gate_status["gate_id"].eq("stage112_intake_allowed"), "pass_now"].sum()
    )
    decision = ACCEPT_DECISION if stage112_intake_allowed_now else DECISION
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "manifest_path": str(manifest_path),
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "wave_id": WAVE_ID,
        "w0_request_count": request_count,
        "w0_hard_accept_request_count": accepted_count,
        "w0_total_window_count": total_window_count,
        "w0_hard_accept_window_count": accepted_window_count,
        "w0_hard_accept_window_coverage_pct": 0.0 if total_window_count == 0 else accepted_window_count / total_window_count * 100.0,
        "raw_file_exist_count": int(request_status["raw_exists"].sum()) if request_count else 0,
        "parquet_file_exist_count": int(request_status["parquet_exists"].sum()) if request_count else 0,
        "proof_file_exist_count": int(request_status["proof_exists"].sum()) if request_count else 0,
        "sha256_match_count": int(request_status["raw_sha256_match"].sum()) if request_count else 0,
        "parquet_readable_count": int(request_status["parquet_readable"].sum()) if request_count else 0,
        "parquet_row_count_positive_count": int(request_status["parquet_row_count_positive"].sum()) if request_count else 0,
        "sequence_gap_zero_count": int(request_status["sequence_gap_zero"].sum()) if request_count else 0,
        "time_span_ok_count": int(request_status["time_span_ok"].sum()) if request_count else 0,
        "issue_count": int(len(issue_frame)),
        "gate_count": int(len(gate_status)),
        "gate_pass_count": int(gate_status["pass_now"].sum()),
        "data_gate_count": data_gate_count,
        "data_gate_pass_count": data_gate_pass_count,
        "stage112_intake_allowed_now": stage112_intake_allowed_now,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(stage116_summary.get("end_equity", np.nan)),
        "total_return_pct": float(stage116_summary.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage116_summary.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage116_summary.get("sharpe", np.nan)),
        "total_slippage": float(stage116_summary.get("total_slippage", np.nan)),
        "total_trade_count": float(stage116_summary.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage116_summary.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage116_summary.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    return pd.DataFrame([row])


def _plot_official_path(curve: pd.DataFrame, request_status: pd.DataFrame) -> None:
    points = _nearest_curve_points(curve, request_status["trading_day"])
    points = points.join(request_status[["hard_accept", "issue_count"]].reset_index(drop=True))
    colors = np.where(points["hard_accept"].eq(1), "#15803D", "#B91C1C")
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.2)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=colors, s=70, alpha=0.75, label="W0 delivery status")
    axes[0].set_ylabel("equity (m)")
    axes[0].legend(loc="upper left")
    axes[0].grid(alpha=0.25)

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.1)
    axes[1].scatter(points["date"], points["drawdown_pct"], color=colors, s=65, alpha=0.75)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)

    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=colors, s=65, alpha=0.75)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(alpha=0.25)
    fig.suptitle("Stage117 W0 delivery status on official path; red means data not accepted")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gates(gate_status: pd.DataFrame) -> None:
    chart = gate_status.copy()
    chart["label"] = chart["gate_id"]
    colors = chart["pass_now"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#64748B")
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.barh(chart["label"], np.ones(len(chart)), color=colors)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("gate present; color indicates pass/fail")
    ax.set_title("Stage117 W0 delivery gates")
    for y, pass_now in enumerate(chart["pass_now"]):
        ax.text(0.5, y, "PASS" if int(pass_now) == 1 else "FAIL", ha="center", va="center", color="white", fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_completeness(request_status: pd.DataFrame) -> None:
    columns = [
        "raw_exists",
        "raw_sha256_match",
        "parquet_exists",
        "parquet_readable",
        "parquet_required_fields_present",
        "parquet_row_count_positive",
        "proof_exists",
        "sequence_gap_zero",
        "row_count_positive",
        "time_span_ok",
        "hard_accept",
    ]
    matrix = request_status[columns].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(14, 9))
    image = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    ax.set_yticks(range(len(request_status)))
    ax.set_yticklabels(request_status["request_id"], fontsize=6)
    ax.set_title("Stage117 W0 request file/proof completeness")
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(COMPLETENESS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_request_timeline(request_status: pd.DataFrame) -> None:
    chart = request_status.sort_values(["trading_day", "request_id"]).copy()
    colors = chart["hard_accept"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#64748B")
    sizes = 30 + chart["issue_count"].clip(lower=0, upper=20) * 5
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.scatter(chart["trading_day"], chart["window_count"], c=colors, s=sizes, alpha=0.75)
    ax.set_ylabel("window_count")
    ax.set_title("Stage117 W0 request timeline; all failed points remain data-only")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(REQUEST_TIMELINE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    gate_status: pd.DataFrame,
    request_status: pd.DataFrame,
    issue_frame: pd.DataFrame,
    file_audit: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    issue_summary = (
        issue_frame.groupby("issue_code", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        if not issue_frame.empty
        else pd.DataFrame(columns=["issue_code", "count"])
    )
    report = f"""# Stage117 W0 delivery verifier

## Decision

- decision: `{row['decision']}`
- nature: read-only W0 delivery verifier; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- manifest: `{row['manifest_path']}`

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## Summary

{_md_table(summary)}

## Gate Status

{_md_table(gate_status)}

## Issue Summary

{_md_table(issue_summary)}

## Request Status Sample

{_md_table(request_status[['request_id', 'vt_symbol', 'trading_day', 'raw_exists', 'parquet_exists', 'proof_exists', 'raw_sha256_match', 'sequence_gap_zero', 'time_span_ok', 'hard_accept', 'issue_count']], max_rows=20)}

## File Audit Sample

{_md_table(file_audit[['request_id', 'raw_exists', 'raw_sha256_match', 'parquet_exists', 'parquet_readable', 'proof_exists']], max_rows=20)}

## Visual Outputs

- official path delivery status: `{PATH_CHART_OUT}`
- gate status chart: `{GATE_CHART_OUT}`
- file completeness matrix: `{COMPLETENESS_CHART_OUT}`
- request timeline status: `{REQUEST_TIMELINE_CHART_OUT}`

## Judgment

W0 delivery is not accepted. The verifier is ready, but the default manifest still has no raw/data/proof files and no integrity or continuity evidence. Stage112 intake, true engine, A/B, formal candidate and microstructure preflight remain blocked.
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    manifest_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_MANIFEST_IN
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    request_packet, manifest, stage116_summary = _load_inputs(manifest_path)
    request_status, file_audit, issues = _build_request_status(request_packet, manifest, manifest_path)
    gate_status = _build_gate_status(request_status, manifest)
    summary = _build_summary(request_status, gate_status, issues, stage116_summary, manifest_path)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(request_status, REQUEST_STATUS_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_csv(issues, ISSUE_OUT)
    _write_csv(file_audit, FILE_AUDIT_OUT)

    _plot_official_path(curve, request_status)
    _plot_gates(gate_status)
    _plot_completeness(request_status)
    _plot_request_timeline(request_status)
    _write_report(summary, gate_status, request_status, issues, file_audit)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "manifest_path": manifest_path,
        "summary_path": SUMMARY_OUT,
        "request_status_path": REQUEST_STATUS_OUT,
        "gate_status_path": GATE_STATUS_OUT,
        "issue_path": ISSUE_OUT,
        "file_audit_path": FILE_AUDIT_OUT,
        "report_path": REPORT_OUT,
        "charts": [
            PATH_CHART_OUT,
            GATE_CHART_OUT,
            COMPLETENESS_CHART_OUT,
            REQUEST_TIMELINE_CHART_OUT,
        ],
        "stage112_intake_allowed_now": int(summary.iloc[0]["stage112_intake_allowed_now"]),
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
