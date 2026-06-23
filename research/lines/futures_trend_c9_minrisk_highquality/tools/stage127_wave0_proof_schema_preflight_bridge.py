from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage127"
MODEL_TAG = "stage127_wave0_proof_schema_preflight_bridge_v1"
OUTPUT_PREFIX = "qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage127_wave0_proof_schema_preflight_bridge"
DEFAULT_DROP_DIR = (
    LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit" / "empty_drop"
)

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE125_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage125_wave0_receipt_preflight_audit"
    / "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_summary_"
    "stage125_wave0_receipt_preflight_audit_v1.csv"
)
STAGE126_DIR = LINE_DIR / "outputs" / "stage126_wave0_proof_json_schema_package"
STAGE126_SCHEMA_IN = (
    STAGE126_DIR
    / "qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_schema_"
    "stage126_wave0_proof_json_schema_package_v1.json"
)
STAGE126_TEMPLATE_INDEX_IN = (
    STAGE126_DIR
    / "qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_template_index_"
    "stage126_wave0_proof_json_schema_package_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_schema_bridge_audit_{MODEL_TAG}.csv"
TEMPLATE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_template_schema_block_audit_{MODEL_TAG}.csv"
SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_integration_selftest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_schema_bridge_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_schema_bridge_status_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_schema_bridge_matrix_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_integration_selftest_chart_{MODEL_TAG}.png"
TEMPLATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_template_schema_block_chart_{MODEL_TAG}.png"

DECISION = "stage127_proof_schema_preflight_bridge_ready_templates_blocked_no_real_data"
REQUEST_RE = re.compile(r"stage114_req_\d{4}")


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


def _request_id_for_path(path: Path) -> str:
    match = REQUEST_RE.search(str(path))
    return match.group(0) if match else ""


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_placeholder(item) for item in value)
    return isinstance(value, str) and "<" in value and ">" in value


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage125 = _read_csv(STAGE125_SUMMARY_IN)
    if not stage125.empty:
        row = stage125.iloc[0]
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


def _load_schema() -> tuple[dict[str, Any], Draft202012Validator, int]:
    schema = json.loads(STAGE126_SCHEMA_IN.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema, Draft202012Validator(schema), 1


def _request_meta(file_contract: pd.DataFrame) -> pd.DataFrame:
    if file_contract.empty:
        raise RuntimeError(f"missing Stage124 file contract: {STAGE124_FILE_CONTRACT_IN}")
    proof_rows = file_contract[file_contract["artifact_role"].astype(str).eq("proof")].copy()
    if proof_rows.empty:
        raise RuntimeError("Stage124 file contract has no proof rows")
    columns = [
        "request_id",
        "batch_id",
        "exchange",
        "product",
        "vt_symbol",
        "trading_day",
        "request_start",
        "request_end",
        "required_schema_request",
        "recommended_relative_path",
    ]
    proof_rows = proof_rows[columns].copy()
    for column in ["trading_day", "request_start", "request_end"]:
        proof_rows[column] = pd.to_datetime(proof_rows[column], errors="coerce")
    return proof_rows.sort_values(["trading_day", "request_id"]).reset_index(drop=True)


def _scan_proofs(drop_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    files = sorted(path for path in drop_dir.rglob("*") if path.is_file()) if drop_dir.exists() else []
    for path in files:
        is_proof = path.suffix.lower() == ".json" and ("proof" in str(path).lower())
        if not is_proof:
            continue
        rows.append(
            {
                "request_id": _request_id_for_path(path),
                "proof_file": str(path),
                "relative_path": str(path.relative_to(drop_dir)) if path.is_relative_to(drop_dir) else str(path),
                "bytes": int(path.stat().st_size),
            }
        )
    return pd.DataFrame(rows)


def _read_json_file(path_text: str) -> tuple[dict[str, Any] | None, str]:
    if not path_text:
        return None, "proof_missing"
    try:
        return json.loads(Path(path_text).read_text(encoding="utf-8")), ""
    except Exception as exc:
        return None, type(exc).__name__


def _validate_payload(validator: Draft202012Validator, payload: dict[str, Any] | None) -> tuple[int, list[str]]:
    if payload is None:
        return 0, ["proof_missing_or_unreadable"]
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    return int(len(errors) == 0), [error.message for error in errors]


def _contract_match(row: pd.Series, payload: dict[str, Any] | None) -> tuple[int, list[str]]:
    if payload is None:
        return 0, ["proof_missing_or_unreadable"]
    checks = {
        "request_id": _clean(payload.get("request_id")) == _clean(row["request_id"]),
        "batch_id": _clean(payload.get("batch_id")) == _clean(row["batch_id"]),
        "vt_symbol": _clean(payload.get("vt_symbol")) == _clean(row["vt_symbol"]),
        "required_schema_request": _clean(payload.get("required_schema_request")) == _clean(row["required_schema_request"]),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return int(not failures), failures


def _span_cover(row: pd.Series, payload: dict[str, Any] | None) -> tuple[int, str]:
    if payload is None:
        return 0, "proof_missing_or_unreadable"
    first_ts = pd.to_datetime(payload.get("first_ts_event"), errors="coerce")
    last_ts = pd.to_datetime(payload.get("last_ts_event"), errors="coerce")
    request_start = pd.to_datetime(row["request_start"], errors="coerce")
    request_end = pd.to_datetime(row["request_end"], errors="coerce")
    if pd.isna(first_ts) or pd.isna(last_ts) or pd.isna(request_start) or pd.isna(request_end):
        return 0, "timestamp_parse_failed"
    if first_ts <= request_start and last_ts >= request_end:
        return 1, ""
    return 0, f"span_undercoverage:first={first_ts},last={last_ts},required={request_start}->{request_end}"


def _audit_requests(
    request_meta: pd.DataFrame,
    proof_inventory: pd.DataFrame,
    validator: Draft202012Validator,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in request_meta.iterrows():
        request_id = _clean(row["request_id"])
        proofs = proof_inventory[proof_inventory["request_id"].eq(request_id)] if not proof_inventory.empty else pd.DataFrame()
        proof_count = len(proofs)
        proof_file = _clean(proofs["proof_file"].iloc[0]) if proof_count > 0 else ""
        payload, read_error = _read_json_file(proof_file)
        schema_valid, schema_errors = _validate_payload(validator, payload)
        identity_match, identity_failures = _contract_match(row, payload)
        span_cover, span_error = _span_cover(row, payload)
        placeholder_free = int(payload is not None and not _has_placeholder(payload))
        template_flag_clear = int(payload is not None and not bool(payload.get("template_only_not_real_proof", False)))
        bridge_ready = int(
            proof_count == 1
            and schema_valid == 1
            and identity_match == 1
            and span_cover == 1
            and placeholder_free == 1
            and template_flag_clear == 1
        )
        rows.append(
            {
                "request_id": request_id,
                "batch_id": _clean(row["batch_id"]),
                "exchange": _clean(row["exchange"]),
                "product": _clean(row["product"]),
                "vt_symbol": _clean(row["vt_symbol"]),
                "trading_day": pd.Timestamp(row["trading_day"]).strftime("%Y-%m-%d") if pd.notna(row["trading_day"]) else "",
                "request_start": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["request_start"]) else "",
                "request_end": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["request_end"]) else "",
                "required_schema_request": _clean(row["required_schema_request"]),
                "recommended_relative_path": _clean(row["recommended_relative_path"]),
                "observed_proof_count": proof_count,
                "proof_file": proof_file,
                "proof_json_readable": int(payload is not None),
                "read_error": read_error,
                "schema_valid": schema_valid,
                "schema_error_count": len(schema_errors),
                "first_schema_error": schema_errors[0] if schema_errors else "",
                "request_identity_match": identity_match,
                "identity_failures": ";".join(identity_failures),
                "request_span_cover": span_cover,
                "span_error": span_error,
                "placeholder_free": placeholder_free,
                "template_flag_clear": template_flag_clear,
                "proof_schema_bridge_ready": bridge_ready,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def _audit_templates(template_index: pd.DataFrame, validator: Draft202012Validator) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in template_index.iterrows():
        path = Path(_clean(row.get("template_path")))
        payload, read_error = _read_json_file(str(path))
        schema_valid, schema_errors = _validate_payload(validator, payload)
        rows.append(
            {
                "request_id": _clean(row.get("request_id")),
                "template_path": str(path),
                "template_json_readable": int(payload is not None),
                "read_error": read_error,
                "placeholder_present": int(payload is not None and _has_placeholder(payload)),
                "template_schema_valid": schema_valid,
                "template_schema_blocked": int(schema_valid == 0),
                "schema_error_count": len(schema_errors),
                "first_schema_error": schema_errors[0] if schema_errors else "",
            }
        )
    return pd.DataFrame(rows)


def _valid_payload_for(row: pd.Series) -> dict[str, Any]:
    return {
        "request_id": _clean(row["request_id"]),
        "batch_id": _clean(row["batch_id"]),
        "vt_symbol": _clean(row["vt_symbol"]),
        "required_schema_request": _clean(row["required_schema_request"]),
        "vendor": "authorized_research_feed_vendor",
        "license_id": "research_license_contract_001",
        "dataset": "authorized_depth_feed_w0_v1",
        "schema_hash": "a" * 64,
        "field_dictionary_version": "stage120_canonical_contract_v1",
        "ts_event_timezone": "Asia/Shanghai",
        "ts_recv_timezone": "Asia/Shanghai",
        "first_ts_event": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S"),
        "last_ts_event": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": 1,
        "sequence_gap_count": 0,
        "capture_continuity_proof": "continuity_audit_packet_001",
        "synthetic_fixture": False,
        "raw_sha256": "b" * 64,
        "normalized_parquet_sha256": "c" * 64,
        "proof_created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template_only_not_real_proof": False,
    }


def _payload_bridge_ready(
    row: pd.Series,
    payload: dict[str, Any],
    validator: Draft202012Validator,
) -> tuple[int, int, int, int, int]:
    schema_valid, _ = _validate_payload(validator, payload)
    identity_match, _ = _contract_match(row, payload)
    span_cover, _ = _span_cover(row, payload)
    placeholder_free = int(not _has_placeholder(payload))
    bridge_ready = int(schema_valid and identity_match and span_cover and placeholder_free)
    return schema_valid, identity_match, span_cover, placeholder_free, bridge_ready


def _integration_selftests(
    request_meta: pd.DataFrame,
    template_audit: pd.DataFrame,
    validator: Draft202012Validator,
) -> pd.DataFrame:
    first = request_meta.iloc[0]
    positive = _valid_payload_for(first)
    request_mismatch = dict(positive)
    request_mismatch["request_id"] = "stage114_req_9999"
    span_undercoverage = dict(positive)
    span_undercoverage["first_ts_event"] = pd.Timestamp(first["request_start"]).strftime("%Y-%m-%d %H:%M:%S")
    span_undercoverage["last_ts_event"] = (pd.Timestamp(first["request_end"]) - pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    synthetic_negative = dict(positive)
    synthetic_negative["synthetic_fixture"] = True
    template_row = template_audit.iloc[0]
    template_payload, _ = _read_json_file(_clean(template_row["template_path"]))
    cases = [
        ("positive_contract_valid_in_memory", positive, 1, "schema and request contract should pass"),
        ("request_id_mismatch_negative", request_mismatch, 0, "schema alone passes but contract identity must block"),
        ("time_span_undercoverage_negative", span_undercoverage, 0, "schema alone passes but request span must block"),
        ("synthetic_fixture_true_negative", synthetic_negative, 0, "schema const false must block synthetic data"),
        ("placeholder_template_negative", template_payload or {}, 0, "template placeholders must block"),
    ]
    rows = []
    for case_id, payload, expected_bridge_ready, notes in cases:
        schema_valid, identity_match, span_cover, placeholder_free, bridge_ready = _payload_bridge_ready(first, payload, validator)
        rows.append(
            {
                "case_id": case_id,
                "expected_bridge_ready": expected_bridge_ready,
                "actual_bridge_ready": bridge_ready,
                "pass_selftest": int(bridge_ready == expected_bridge_ready),
                "schema_valid": schema_valid,
                "request_identity_match": identity_match,
                "request_span_cover": span_cover,
                "placeholder_free": placeholder_free,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def _stage125_previous_ready() -> int:
    summary = _read_csv(STAGE125_SUMMARY_IN)
    if summary.empty:
        return 0
    return int(summary.iloc[0].get("ready_for_stage123", 0))


def _build_gates(
    request_audit: pd.DataFrame,
    template_audit: pd.DataFrame,
    selftests: pd.DataFrame,
    schema_check_pass: int,
    stage125_ready: int,
) -> pd.DataFrame:
    request_count = len(request_audit)
    template_count = len(template_audit)
    template_blocked = int(template_audit["template_schema_blocked"].sum()) if not template_audit.empty else 0
    observed_proofs = int(request_audit["observed_proof_count"].clip(upper=1).sum()) if not request_audit.empty else 0
    schema_valid = int(request_audit["schema_valid"].sum()) if not request_audit.empty else 0
    identity_match = int(request_audit["request_identity_match"].sum()) if not request_audit.empty else 0
    span_cover = int(request_audit["request_span_cover"].sum()) if not request_audit.empty else 0
    bridge_ready = int(request_audit["proof_schema_bridge_ready"].sum()) if not request_audit.empty else 0
    selftest_pass = int(selftests["pass_selftest"].sum()) if not selftests.empty else 0
    rows = [
        {
            "gate_id": "stage126_schema_available_and_valid",
            "observed": schema_check_pass,
            "required": 1,
            "pass_now": schema_check_pass,
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage124_request_contract_available",
            "observed": request_count,
            "required": "41",
            "pass_now": int(request_count == 41),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage126_templates_schema_blocked",
            "observed": f"{template_blocked}/{template_count}",
            "required": f"{template_count}/{template_count}",
            "pass_now": int(template_count > 0 and template_blocked == template_count),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "integration_selftests_pass",
            "observed": f"{selftest_pass}/{len(selftests)}",
            "required": f"{len(selftests)}/{len(selftests)}",
            "pass_now": int(len(selftests) > 0 and selftest_pass == len(selftests)),
            "severity": "planning_hard",
        },
        {
            "gate_id": "real_proof_files_observed",
            "observed": f"{observed_proofs}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(request_count > 0 and observed_proofs == request_count),
            "severity": "data_hard",
        },
        {
            "gate_id": "real_proofs_schema_valid",
            "observed": f"{schema_valid}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(request_count > 0 and schema_valid == request_count),
            "severity": "data_hard",
        },
        {
            "gate_id": "real_proofs_request_identity_match",
            "observed": f"{identity_match}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(request_count > 0 and identity_match == request_count),
            "severity": "data_hard",
        },
        {
            "gate_id": "real_proofs_request_span_cover",
            "observed": f"{span_cover}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(request_count > 0 and span_cover == request_count),
            "severity": "data_hard",
        },
        {
            "gate_id": "proof_schema_bridge_ready",
            "observed": f"{bridge_ready}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(request_count > 0 and bridge_ready == request_count),
            "severity": "final_hard",
        },
        {
            "gate_id": "stage125_previous_ready_for_stage123",
            "observed": stage125_ready,
            "required": 1,
            "pass_now": int(stage125_ready == 1),
            "severity": "final_hard",
        },
        {
            "gate_id": "ready_for_stage123",
            "observed": 0,
            "required": 1,
            "pass_now": 0,
            "severity": "final_hard",
        },
    ]
    return pd.DataFrame(rows)


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, gates: pd.DataFrame) -> None:
    chart = request_audit.copy()
    points = _nearest_curve_points(curve, chart["trading_day"])
    colors = chart["proof_schema_bridge_ready"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#B91C1C")
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage127 official path with proof schema bridge status", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.3)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=colors, s=34, alpha=0.65)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].scatter(points["date"], points["drawdown_pct"], color=colors, s=34, alpha=0.65)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=colors, s=34, alpha=0.65)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    counts = gates.groupby("severity")["pass_now"].agg(["sum", "count"]).reset_index()
    counts["fail"] = counts["count"] - counts["sum"]
    x = np.arange(len(counts))
    axes[3].bar(x, counts["sum"], color="#15803D", label="pass")
    axes[3].bar(x, counts["fail"], bottom=counts["sum"], color="#B91C1C", label="fail")
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(counts["severity"], rotation=20, ha="right")
    axes[3].set_ylabel("gate count")
    axes[3].legend(loc="upper right")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_matrix(request_audit: pd.DataFrame) -> None:
    columns = [
        "observed_proof_count",
        "proof_json_readable",
        "schema_valid",
        "request_identity_match",
        "request_span_cover",
        "placeholder_free",
        "template_flag_clear",
        "proof_schema_bridge_ready",
        "strategy_use_allowed_now",
    ]
    matrix = request_audit[columns].copy()
    matrix["observed_proof_count"] = matrix["observed_proof_count"].clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 10))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage127 request proof schema bridge matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    y_labels = [rid if idx % 4 == 0 else "" for idx, rid in enumerate(request_audit["request_id"])]
    ax.set_yticks(np.arange(len(request_audit)))
    ax.set_yticklabels(y_labels, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selftest(selftests: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(selftests))
    ax.bar(x - 0.2, selftests["expected_bridge_ready"], width=0.38, label="expected", color="#4C6EF5")
    ax.bar(x + 0.2, selftests["actual_bridge_ready"], width=0.38, label="actual", color="#2F9E44")
    for idx, passed in enumerate(selftests["pass_selftest"]):
        ax.text(idx, 1.08, "PASS" if passed else "FAIL", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(selftests["case_id"], rotation=22, ha="right")
    ax.set_ylim(0, 1.25)
    ax.set_ylabel("bridge ready")
    ax.set_title("Stage127 schema bridge integration selftests")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_template_block(template_audit: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    counts = pd.Series(
        {
            "blocked": int(template_audit["template_schema_blocked"].sum()),
            "valid": int(template_audit["template_schema_valid"].sum()),
            "placeholder": int(template_audit["placeholder_present"].sum()),
        }
    )
    axes[0].bar(counts.index, counts.values, color=["#B91C1C", "#15803D", "#3B5BDB"])
    axes[0].set_title("Template schema status")
    axes[0].set_ylabel("count")
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].hist(template_audit["schema_error_count"], bins=range(0, int(template_audit["schema_error_count"].max()) + 2), color="#7C3AED", alpha=0.75)
    axes[1].set_title("Template schema error count")
    axes[1].set_xlabel("errors per template")
    axes[1].set_ylabel("templates")
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(TEMPLATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    gates: pd.DataFrame,
    selftests: pd.DataFrame,
    request_audit: pd.DataFrame,
    template_audit: pd.DataFrame,
) -> None:
    report = [
        f"# {STAGE} W0 proof schema preflight bridge",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{DECISION}`",
        "- scope: schema integration and request-contract overlay only; no strategy rule, true-engine run, order API, CTP connection, or external data download.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Gate Status",
        "",
        _md_table(gates),
        "",
        "## Integration Selftests",
        "",
        _md_table(selftests),
        "",
        "## Request Audit Sample",
        "",
        _md_table(request_audit.head(8)),
        "",
        "## Template Audit Sample",
        "",
        _md_table(template_audit.head(8)),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{REQUEST_MATRIX_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{TEMPLATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main(drop_dir: Path | None = None, case_id: str = "empty_drop_schema_bridge") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    resolved_drop = (drop_dir or DEFAULT_DROP_DIR).resolve()
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    template_index = _read_csv(STAGE126_TEMPLATE_INDEX_IN)
    if template_index.empty:
        raise RuntimeError(f"missing Stage126 template index: {STAGE126_TEMPLATE_INDEX_IN}")
    _, validator, schema_check_pass = _load_schema()
    request_meta = _request_meta(file_contract)
    proof_inventory = _scan_proofs(resolved_drop)
    request_audit = _audit_requests(request_meta, proof_inventory, validator)
    template_audit = _audit_templates(template_index, validator)
    selftests = _integration_selftests(request_meta, template_audit, validator)
    stage125_ready = _stage125_previous_ready()
    gates = _build_gates(request_audit, template_audit, selftests, schema_check_pass, stage125_ready)

    request_count = len(request_audit)
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "case_id": case_id,
                "drop_dir": str(resolved_drop),
                "decision": DECISION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "request_count": request_count,
                "observed_proof_file_count": int(request_audit["observed_proof_count"].clip(upper=1).sum()),
                "schema_valid_request_count": int(request_audit["schema_valid"].sum()),
                "request_identity_match_count": int(request_audit["request_identity_match"].sum()),
                "request_span_cover_count": int(request_audit["request_span_cover"].sum()),
                "placeholder_free_request_count": int(request_audit["placeholder_free"].sum()),
                "proof_schema_bridge_ready_count": int(request_audit["proof_schema_bridge_ready"].sum()),
                "template_count": len(template_audit),
                "template_schema_blocked_count": int(template_audit["template_schema_blocked"].sum()),
                "template_schema_valid_count": int(template_audit["template_schema_valid"].sum()),
                "integration_selftest_count": len(selftests),
                "integration_selftest_pass_count": int(selftests["pass_selftest"].sum()),
                "stage125_previous_ready_for_stage123": stage125_ready,
                "ready_for_stage125": 0,
                "ready_for_stage123": 0,
                "real_w0_data_delivered": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "gate_pass_count": int(gates["pass_now"].sum()),
                "gate_count": len(gates),
                "data_hard_gate_pass_count": int(gates.loc[gates["severity"].eq("data_hard"), "pass_now"].sum()),
                "data_hard_gate_count": int(gates["severity"].eq("data_hard").sum()),
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(request_audit, REQUEST_AUDIT_OUT)
    _write_csv(template_audit, TEMPLATE_AUDIT_OUT)
    _write_csv(selftests, SELFTEST_OUT)
    _write_csv(gates, GATE_STATUS_OUT)
    _plot_official_path(curve, request_audit, gates)
    _plot_request_matrix(request_audit)
    _plot_selftest(selftests)
    _plot_template_block(template_audit)
    _write_report(summary, gates, selftests, request_audit, template_audit)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "case_id": case_id,
            "drop_dir": str(resolved_drop),
            "decision": DECISION,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "request_audit": str(REQUEST_AUDIT_OUT),
                "template_audit": str(TEMPLATE_AUDIT_OUT),
                "selftests": str(SELFTEST_OUT),
                "gates": str(GATE_STATUS_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(REQUEST_MATRIX_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(TEMPLATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "ready_for_stage125": 0,
                "ready_for_stage123": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage127 W0 proof schema bridge preflight.")
    parser.add_argument("--drop-dir", default=str(DEFAULT_DROP_DIR), help="Drop directory to scan for proof JSON files.")
    parser.add_argument("--case-id", default="empty_drop_schema_bridge", help="Case id for output summary.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(Path(args.drop_dir), args.case_id)
