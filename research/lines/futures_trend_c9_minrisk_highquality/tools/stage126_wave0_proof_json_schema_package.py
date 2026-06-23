from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage126"
MODEL_TAG = "stage126_wave0_proof_json_schema_package_v1"
OUTPUT_PREFIX = "qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage126_wave0_proof_json_schema_package"
TEMPLATE_DIR = OUTPUT_DIR / "proof_templates"

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
STAGE124_PROOF_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_proof_field_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE125_DIR = LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit"
STAGE125_SUMMARY_IN = (
    STAGE125_DIR
    / "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_summary_"
    "stage125_wave0_receipt_preflight_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PROOF_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_schema_{MODEL_TAG}.json"
TEMPLATE_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_template_index_{MODEL_TAG}.csv"
VALIDATION_SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_selftest_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_schema_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_proof_schema_status_{MODEL_TAG}.png"
FIELD_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_field_schema_matrix_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_template_readiness_matrix_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_selftest_chart_{MODEL_TAG}.png"

DECISION = "stage126_wave0_proof_json_schema_package_built_templates_blocked_no_real_data"
MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"
REQUIRED_PROOF_FIELDS = [
    "request_id",
    "batch_id",
    "vt_symbol",
    "required_schema_request",
    "vendor",
    "license_id",
    "dataset",
    "schema_hash",
    "field_dictionary_version",
    "ts_event_timezone",
    "ts_recv_timezone",
    "first_ts_event",
    "last_ts_event",
    "row_count",
    "sequence_gap_count",
    "capture_continuity_proof",
    "synthetic_fixture",
]
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
HEX64_PATTERN = r"^[A-Fa-f0-9]{64}$"


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


def _safe_symbol(symbol: str) -> str:
    return symbol.replace(".", "_").replace("/", "_").replace(" ", "_")


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


def _proof_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://local.vnpy/research/futures_trend_c9_minrisk_highquality/stage126/proof.schema.json",
        "title": "Stage126 W0 authorized proof JSON schema",
        "description": (
            "Schema for request-specific W0 proof JSON files. It validates delivery "
            "metadata and anti-synthetic locks only; market authenticity still requires "
            "Stage117, Stage120, Stage125, and Stage123 gates."
        ),
        "type": "object",
        "additionalProperties": True,
        "required": REQUIRED_PROOF_FIELDS,
        "properties": {
            "request_id": {"type": "string", "pattern": r"^stage114_req_\d{4}$"},
            "batch_id": {"type": "string", "pattern": r"^stage114_batch_\d{3}$"},
            "vt_symbol": {"type": "string", "minLength": 3},
            "required_schema_request": {"type": "string", "enum": [MBP10, MBO]},
            "vendor": {
                "type": "string",
                "minLength": 1,
                "not": {"pattern": r"^[sS][yY][nN][tT][hH][eE][tT][iI][cC]"},
            },
            "license_id": {"type": "string", "minLength": 1},
            "dataset": {
                "type": "string",
                "minLength": 1,
                "not": {
                    "pattern": (
                        r"[sS][yY][nN][tT][hH][eE][tT][iI][cC]|"
                        r"[sS][mM][oO][kK][eE]"
                    )
                },
            },
            "schema_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "field_dictionary_version": {"type": "string", "minLength": 1},
            "ts_event_timezone": {"type": "string", "minLength": 1},
            "ts_recv_timezone": {"type": "string", "minLength": 1},
            "first_ts_event": {"type": "string", "pattern": TIMESTAMP_PATTERN},
            "last_ts_event": {"type": "string", "pattern": TIMESTAMP_PATTERN},
            "row_count": {"type": "integer", "minimum": 1},
            "sequence_gap_count": {"type": "integer", "const": 0},
            "capture_continuity_proof": {"type": "string", "minLength": 1},
            "synthetic_fixture": {"type": "boolean", "const": False},
            "raw_sha256": {"type": "string", "pattern": HEX64_PATTERN},
            "normalized_parquet_sha256": {"type": "string", "pattern": HEX64_PATTERN},
            "proof_created_at": {"type": "string", "pattern": TIMESTAMP_PATTERN},
            "template_only_not_real_proof": {"type": "boolean", "const": False},
        },
    }


def _request_rows(file_contract: pd.DataFrame) -> pd.DataFrame:
    if file_contract.empty:
        raise RuntimeError(f"missing Stage124 file contract: {STAGE124_FILE_CONTRACT_IN}")
    proof_rows = file_contract[file_contract["artifact_role"].astype(str) == "proof"].copy()
    if proof_rows.empty:
        raise RuntimeError("Stage124 file contract has no proof rows")
    proof_rows["trading_day"] = pd.to_datetime(proof_rows["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d")
    proof_rows["request_start"] = pd.to_datetime(proof_rows["request_start"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    proof_rows["request_end"] = pd.to_datetime(proof_rows["request_end"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    proof_rows = proof_rows.sort_values(["trading_day", "request_id"]).reset_index(drop=True)
    return proof_rows


def _template_name(row: pd.Series) -> str:
    symbol = _safe_symbol(_clean(row["vt_symbol"]))
    trading_day = _clean(row["trading_day"]).replace("-", "")
    schema = "mbo_l3" if _clean(row["required_schema_request"]) == MBO else "mbp10_l2"
    return f"{row['request_id']}__{symbol}__{trading_day}__{schema}__proof_template.json"


def _proof_template(row: pd.Series) -> dict[str, Any]:
    return {
        "_template_notice": "Template only. Replace all placeholder values and set row_count above zero.",
        "request_id": _clean(row["request_id"]),
        "batch_id": _clean(row["batch_id"]),
        "vt_symbol": _clean(row["vt_symbol"]),
        "required_schema_request": _clean(row["required_schema_request"]),
        "vendor": "<AUTHORIZED_VENDOR>",
        "license_id": "<PRODUCTION_OR_RESEARCH_LICENSE_ID>",
        "dataset": "<AUTHORIZED_DATASET_NAME_AND_VERSION>",
        "schema_hash": "<64_HEX_SCHEMA_HASH>",
        "field_dictionary_version": "<FIELD_DICTIONARY_VERSION>",
        "ts_event_timezone": "Asia/Shanghai",
        "ts_recv_timezone": "Asia/Shanghai",
        "first_ts_event": _clean(row["request_start"]),
        "last_ts_event": _clean(row["request_end"]),
        "row_count": 0,
        "sequence_gap_count": 0,
        "capture_continuity_proof": "<CONTINUITY_PROOF_ID_OR_PATH>",
        "synthetic_fixture": False,
        "raw_sha256": "<64_HEX_RAW_SHA256>",
        "normalized_parquet_sha256": "<64_HEX_NORMALIZED_PARQUET_SHA256>",
        "proof_created_at": "<YYYY-MM-DD HH:MM:SS>",
        "template_only_not_real_proof": True,
    }


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_placeholder(item) for item in value)
    return isinstance(value, str) and "<" in value and ">" in value


def _validate_payload(validator: Draft202012Validator, payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    return len(errors) == 0, [error.message for error in errors]


def _write_templates(requests: pd.DataFrame, validator: Draft202012Validator) -> pd.DataFrame:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in TEMPLATE_DIR.glob("*.json"):
        stale.unlink()
    rows: list[dict[str, Any]] = []
    for _, row in requests.iterrows():
        template = _proof_template(row)
        template_path = TEMPLATE_DIR / _template_name(row)
        template_path.write_text(
            json.dumps(_json_safe(template), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        valid_now, errors = _validate_payload(validator, template)
        rows.append(
            {
                "request_id": _clean(row["request_id"]),
                "batch_id": _clean(row["batch_id"]),
                "exchange": _clean(row["exchange"]),
                "product": _clean(row["product"]),
                "vt_symbol": _clean(row["vt_symbol"]),
                "trading_day": _clean(row["trading_day"]),
                "request_start": _clean(row["request_start"]),
                "request_end": _clean(row["request_end"]),
                "required_schema_request": _clean(row["required_schema_request"]),
                "recommended_delivery_relative_path": _clean(row["recommended_relative_path"]),
                "template_path": str(template_path),
                "template_generated": 1,
                "placeholder_present": int(_has_placeholder(template)),
                "template_validation_pass": int(valid_now),
                "template_validation_blocked": int(not valid_now),
                "template_error_count": len(errors),
                "first_template_error": errors[0] if errors else "",
                "real_proof_present": 0,
                "ready_for_stage125": 0,
                "ready_for_stage123": 0,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def _positive_payload(first: pd.Series) -> dict[str, Any]:
    return {
        "request_id": _clean(first["request_id"]),
        "batch_id": _clean(first["batch_id"]),
        "vt_symbol": _clean(first["vt_symbol"]),
        "required_schema_request": _clean(first["required_schema_request"]),
        "vendor": "authorized_research_feed_vendor",
        "license_id": "research_license_contract_001",
        "dataset": "authorized_depth_feed_w0_v1",
        "schema_hash": "a" * 64,
        "field_dictionary_version": "stage120_canonical_contract_v1",
        "ts_event_timezone": "Asia/Shanghai",
        "ts_recv_timezone": "Asia/Shanghai",
        "first_ts_event": _clean(first["request_start"]),
        "last_ts_event": _clean(first["request_end"]),
        "row_count": 1,
        "sequence_gap_count": 0,
        "capture_continuity_proof": "continuity_audit_packet_001",
        "synthetic_fixture": False,
        "raw_sha256": "b" * 64,
        "normalized_parquet_sha256": "c" * 64,
        "proof_created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template_only_not_real_proof": False,
    }


def _validation_selftests(
    requests: pd.DataFrame, template_index: pd.DataFrame, validator: Draft202012Validator
) -> pd.DataFrame:
    first = requests.iloc[0]
    positive = _positive_payload(first)
    missing_vendor = dict(positive)
    missing_vendor.pop("vendor", None)
    synthetic_flag = dict(positive)
    synthetic_flag["synthetic_fixture"] = True
    first_template_path = Path(template_index.iloc[0]["template_path"])
    placeholder_template = json.loads(first_template_path.read_text(encoding="utf-8"))
    cases = [
        ("positive_valid_in_memory", positive, 1, "valid structure only, not market authenticity"),
        ("missing_required_vendor_negative", missing_vendor, 0, "required field must block"),
        ("synthetic_flag_true_negative", synthetic_flag, 0, "synthetic fixture must block"),
        ("placeholder_template_negative", placeholder_template, 0, "templates cannot masquerade as proof"),
    ]
    rows: list[dict[str, Any]] = []
    for case_id, payload, expected_valid, notes in cases:
        actual_valid, errors = _validate_payload(validator, payload)
        rows.append(
            {
                "case_id": case_id,
                "expected_valid": expected_valid,
                "actual_valid": int(actual_valid),
                "pass_selftest": int(actual_valid == bool(expected_valid)),
                "error_count": len(errors),
                "first_error": errors[0] if errors else "",
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def _field_matrix(schema: dict[str, Any], proof_contract: pd.DataFrame) -> pd.DataFrame:
    contract_required = set()
    if not proof_contract.empty:
        required_rows = proof_contract[pd.to_numeric(proof_contract["required_for_real_w0"], errors="coerce") == 1]
        contract_required = set(required_rows["proof_json_field"].astype(str))
    rows = []
    for field in REQUIRED_PROOF_FIELDS:
        props = schema["properties"].get(field, {})
        rows.append(
            {
                "proof_json_field": field,
                "required_in_schema": 1,
                "required_in_stage124_contract": int(field in contract_required or field in {"synthetic_fixture"}),
                "type_rule": int("type" in props),
                "pattern_rule": int("pattern" in props),
                "enum_rule": int("enum" in props),
                "const_rule": int("const" in props),
                "minimum_rule": int("minimum" in props or "minLength" in props),
                "anti_synthetic_rule": int("not" in props or field == "synthetic_fixture"),
            }
        )
    return pd.DataFrame(rows)


def _gate_status(
    requests: pd.DataFrame,
    proof_contract: pd.DataFrame,
    template_index: pd.DataFrame,
    validation_selftests: pd.DataFrame,
    schema_check_pass: int,
    stage125_summary: pd.DataFrame,
) -> pd.DataFrame:
    request_count = int(requests["request_id"].nunique())
    template_count = len(template_index)
    placeholder_count = int(template_index["placeholder_present"].sum())
    template_block_count = int(template_index["template_validation_blocked"].sum())
    selftest_pass_count = int(validation_selftests["pass_selftest"].sum())
    stage125_ready = 0
    if not stage125_summary.empty:
        stage125_ready = int(stage125_summary.iloc[0].get("ready_for_stage123", 0))
    contract_required_count = 0
    if not proof_contract.empty:
        contract_required_count = int(
            pd.to_numeric(proof_contract["required_for_real_w0"], errors="coerce").fillna(0).sum()
        )
    rows = [
        {
            "gate_id": "stage124_file_contract_requests",
            "observed": request_count,
            "required": ">=41",
            "pass_now": int(request_count >= 41),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage124_proof_contract_required_fields",
            "observed": contract_required_count,
            "required": ">=12",
            "pass_now": int(contract_required_count >= 12),
            "severity": "planning_hard",
        },
        {
            "gate_id": "draft202012_schema_valid",
            "observed": schema_check_pass,
            "required": 1,
            "pass_now": schema_check_pass,
            "severity": "planning_hard",
        },
        {
            "gate_id": "proof_templates_generated",
            "observed": f"{template_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(template_count == request_count and request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "placeholder_templates_not_real",
            "observed": f"{placeholder_count}/{template_count}",
            "required": f"{template_count}/{template_count}",
            "pass_now": int(placeholder_count == template_count and template_count > 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "placeholder_templates_schema_blocked",
            "observed": f"{template_block_count}/{template_count}",
            "required": f"{template_count}/{template_count}",
            "pass_now": int(template_block_count == template_count and template_count > 0),
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "validation_selftests_pass",
            "observed": f"{selftest_pass_count}/{len(validation_selftests)}",
            "required": f"{len(validation_selftests)}/{len(validation_selftests)}",
            "pass_now": int(selftest_pass_count == len(validation_selftests) and len(validation_selftests) > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "real_proof_present",
            "observed": "0/41",
            "required": "41/41",
            "pass_now": 0,
            "severity": "data_hard",
        },
        {
            "gate_id": "stage125_previous_ready_for_stage123",
            "observed": stage125_ready,
            "required": 1,
            "pass_now": int(stage125_ready == 1),
            "severity": "data_hard",
        },
        {
            "gate_id": "ready_for_stage125",
            "observed": "0/41",
            "required": "41/41 real proof files",
            "pass_now": 0,
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, requests: pd.DataFrame, gate_status: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(13, 10), sharex=False)
    fig.suptitle("Stage126 official path with W0 proof-schema status", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"], color="#2f6b52", linewidth=1.6)
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b94a48", alpha=0.35)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#6d5bd0", linewidth=1.2)
    axes[2].axhline(100, color="#2b2b2b", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(alpha=0.25)
    markers = _nearest_curve_points(curve, pd.to_datetime(requests["request_start"], errors="coerce"))
    axes[0].scatter(markers["date"], markers["account_equity"], s=16, color="#111111", alpha=0.55, label="W0 requests")
    axes[1].scatter(markers["date"], markers["drawdown_pct"], s=14, color="#111111", alpha=0.45)
    axes[2].scatter(markers["date"], markers["broker10_margin_to_equity_pct"], s=14, color="#111111", alpha=0.45)
    axes[0].legend(loc="upper left")
    gate_counts = gate_status.groupby("severity")["pass_now"].agg(["sum", "count"]).reset_index()
    gate_counts["fail"] = gate_counts["count"] - gate_counts["sum"]
    x = np.arange(len(gate_counts))
    axes[3].bar(x, gate_counts["sum"], label="pass", color="#2f6b52")
    axes[3].bar(x, gate_counts["fail"], bottom=gate_counts["sum"], label="fail", color="#b94a48")
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(gate_counts["severity"], rotation=20, ha="right")
    axes[3].set_ylabel("gate count")
    axes[3].legend(loc="upper right")
    axes[3].grid(axis="y", alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_field_matrix(field_matrix: pd.DataFrame) -> None:
    columns = [
        "required_in_schema",
        "required_in_stage124_contract",
        "type_rule",
        "pattern_rule",
        "enum_rule",
        "const_rule",
        "minimum_rule",
        "anti_synthetic_rule",
    ]
    data = field_matrix[columns].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, 8))
    image = ax.imshow(data, aspect="auto", cmap="YlGn", vmin=0, vmax=1)
    ax.set_title("Stage126 proof field schema matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(field_matrix)))
    ax.set_yticklabels(field_matrix["proof_json_field"])
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8, color="#1d1d1d")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(FIELD_MATRIX_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_request_matrix(template_index: pd.DataFrame) -> None:
    columns = [
        "template_generated",
        "placeholder_present",
        "template_validation_blocked",
        "real_proof_present",
        "ready_for_stage125",
        "ready_for_stage123",
        "strategy_use_allowed_now",
    ]
    data = template_index[columns].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, 10))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage126 request template readiness matrix", pad=18)
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    y_labels = [rid if index % 4 == 0 else "" for index, rid in enumerate(template_index["request_id"])]
    ax.set_yticks(np.arange(len(template_index)))
    ax.set_yticklabels(y_labels, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_selftest(validation_selftests: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(validation_selftests))
    ax.bar(x - 0.18, validation_selftests["expected_valid"], width=0.36, label="expected_valid", color="#5c7cfa")
    ax.bar(x + 0.18, validation_selftests["actual_valid"], width=0.36, label="actual_valid", color="#2f9e44")
    for index, value in enumerate(validation_selftests["pass_selftest"]):
        ax.text(index, 1.08, "PASS" if value else "FAIL", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, 1.25)
    ax.set_xticks(x)
    ax.set_xticklabels(validation_selftests["case_id"], rotation=20, ha="right")
    ax.set_ylabel("valid flag")
    ax.set_title("Stage126 JSON schema validation selftests")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    gate_status: pd.DataFrame,
    validation_selftests: pd.DataFrame,
    template_index: pd.DataFrame,
    proof_schema_hash: str,
) -> None:
    report = [
        f"# {STAGE} W0 proof JSON schema package",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{DECISION}`",
        f"- proof_schema_hash: `{proof_schema_hash}`",
        "- scope: data-contract hardening only; no strategy rule, true-engine run, order API, or CTP connection.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Gate Status",
        "",
        _md_table(gate_status),
        "",
        "## Validation Selftests",
        "",
        _md_table(validation_selftests),
        "",
        "## Template Index Sample",
        "",
        _md_table(template_index.head(8)),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{FIELD_MATRIX_CHART_OUT.name}`",
        f"- `{REQUEST_MATRIX_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    proof_contract = _read_csv(STAGE124_PROOF_CONTRACT_IN)
    stage125_summary = _read_csv(STAGE125_SUMMARY_IN)
    requests = _request_rows(file_contract)

    schema = _proof_schema()
    Draft202012Validator.check_schema(schema)
    schema_check_pass = 1
    proof_schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest()
    _write_json(PROOF_SCHEMA_OUT, schema)
    validator = Draft202012Validator(schema)

    template_index = _write_templates(requests, validator)
    validation_selftests = _validation_selftests(requests, template_index, validator)
    field_matrix = _field_matrix(schema, proof_contract)
    gate_status = _gate_status(requests, proof_contract, template_index, validation_selftests, schema_check_pass, stage125_summary)

    gate_pass_count = int(gate_status["pass_now"].sum())
    gate_count = len(gate_status)
    data_hard = gate_status[gate_status["severity"].eq("data_hard")]
    data_hard_gate_pass_count = int(data_hard["pass_now"].sum())
    data_hard_gate_count = len(data_hard)
    stage125_previous_ready = 0
    if not stage125_summary.empty:
        stage125_previous_ready = int(stage125_summary.iloc[0].get("ready_for_stage123", 0))

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": DECISION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "request_count": int(requests["request_id"].nunique()),
                "proof_template_count": len(template_index),
                "proof_schema_required_field_count": len(REQUIRED_PROOF_FIELDS),
                "proof_schema_property_count": len(schema["properties"]),
                "proof_schema_hash": proof_schema_hash,
                "schema_check_pass": schema_check_pass,
                "validation_selftest_count": len(validation_selftests),
                "validation_selftest_pass_count": int(validation_selftests["pass_selftest"].sum()),
                "template_placeholder_count": int(template_index["placeholder_present"].sum()),
                "template_schema_valid_count": int(template_index["template_validation_pass"].sum()),
                "template_schema_blocked_count": int(template_index["template_validation_blocked"].sum()),
                "real_proof_present_count": 0,
                "schema_package_ready_for_vendor": 1,
                "stage125_previous_ready_for_stage123": stage125_previous_ready,
                "ready_for_stage125": 0,
                "ready_for_stage123": 0,
                "real_w0_data_delivered": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "gate_pass_count": gate_pass_count,
                "gate_count": gate_count,
                "data_hard_gate_pass_count": data_hard_gate_pass_count,
                "data_hard_gate_count": data_hard_gate_count,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(template_index, TEMPLATE_INDEX_OUT)
    _write_csv(validation_selftests, VALIDATION_SELFTEST_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)

    _plot_official_path(curve, requests, gate_status)
    _plot_field_matrix(field_matrix)
    _plot_request_matrix(template_index)
    _plot_selftest(validation_selftests)
    _write_report(summary, gate_status, validation_selftests, template_index, proof_schema_hash)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": DECISION,
            "proof_schema": str(PROOF_SCHEMA_OUT),
            "proof_schema_hash": proof_schema_hash,
            "template_index": str(TEMPLATE_INDEX_OUT),
            "template_dir": str(TEMPLATE_DIR),
            "validation_selftests": str(VALIDATION_SELFTEST_OUT),
            "gate_status": str(GATE_STATUS_OUT),
            "summary": str(SUMMARY_OUT),
            "charts": [
                str(PATH_CHART_OUT),
                str(FIELD_MATRIX_CHART_OUT),
                str(REQUEST_MATRIX_CHART_OUT),
                str(SELFTEST_CHART_OUT),
            ],
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


if __name__ == "__main__":
    main()
