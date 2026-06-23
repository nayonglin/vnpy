from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage154"
MODEL_TAG = "stage154_authoritative_minute_ohlcv_proof_schema_pack_v1"
OUTPUT_PREFIX = "qmt_roll_stage154_c9_minrisk_authoritative_minute_ohlcv_proof_schema_pack"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage154_authoritative_minute_ohlcv_proof_schema_pack"
TEMPLATE_DIR = OUTPUT_DIR / "proof_templates"

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

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"
STAGE153_GATE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_gate_status_{STAGE153_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PROOF_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_schema_{MODEL_TAG}.json"
PROOF_FIELD_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_field_contract_{MODEL_TAG}.csv"
TEMPLATE_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_template_index_{MODEL_TAG}.csv"
VALIDATION_SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_selftest_{MODEL_TAG}.csv"
ANTI_MISUSE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anti_misuse_guard_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_proof_pack_status_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_field_contract_matrix_{MODEL_TAG}.png"
TEMPLATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_template_count_by_exchange_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_selftest_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
HEX64_PATTERN = r"^[A-Fa-f0-9]{64}$"
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
    "template_only_not_real_proof",
]
STAGE153_REQUIRED_FIELDS = {
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
}


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


def _safe_slug(text: Any) -> str:
    return str(text).replace(".", "_").replace("/", "_").replace(" ", "_").replace(":", "")


def _build_proof_schema(exchanges: list[str]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://local.vnpy/research/stage154/authoritative-minute-ohlcv-proof.schema.json",
        "title": "Stage154 authoritative minute OHLCV delivery proof",
        "type": "object",
        "additionalProperties": False,
        "required": PROOF_REQUIRED_FIELDS,
        "properties": {
            "request_id": {"type": "string", "pattern": r"^stage152_req_\d{4}_.+"},
            "vendor_name": {"type": "string", "minLength": 1},
            "vendor_license": {"type": "string", "minLength": 1},
            "dataset_id": {"type": "string", "minLength": 1},
            "query_params": {
                "type": "object",
                "additionalProperties": True,
                "required": ["symbols", "interval", "start_ts", "end_ts", "timezone", "adjustment", "source_endpoint"],
                "properties": {
                    "symbols": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                    "interval": {"const": "1m"},
                    "start_ts": {"type": "string", "pattern": TIMESTAMP_PATTERN},
                    "end_ts": {"type": "string", "pattern": TIMESTAMP_PATTERN},
                    "timezone": {"const": "Asia/Shanghai"},
                    "adjustment": {"const": "none"},
                    "source_endpoint": {"type": "string", "minLength": 1},
                },
            },
            "raw_file": {"type": "string", "minLength": 1},
            "raw_file_size_bytes": {"type": "integer", "minimum": 1},
            "raw_sha256": {"type": "string", "pattern": HEX64_PATTERN},
            "normalized_file": {"type": "string", "minLength": 1},
            "normalized_sha256": {"type": "string", "pattern": HEX64_PATTERN},
            "schema_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "exchange": {"type": "string", "enum": exchanges},
            "vt_symbol": {"type": "string", "minLength": 1},
            "request_start_ts": {"type": "string", "pattern": TIMESTAMP_PATTERN},
            "request_end_ts": {"type": "string", "pattern": TIMESTAMP_PATTERN},
            "timezone": {"const": "Asia/Shanghai"},
            "session_calendar": {
                "type": "object",
                "additionalProperties": True,
                "required": ["calendar_id", "trading_day_convention", "night_session_policy"],
                "properties": {
                    "calendar_id": {"type": "string", "minLength": 1},
                    "trading_day_convention": {"type": "string", "minLength": 1},
                    "night_session_policy": {"type": "string", "minLength": 1},
                },
            },
            "no_trade_bar_policy": {
                "type": "object",
                "additionalProperties": True,
                "required": ["policy", "meaning", "sequence_gap_interpretation"],
                "properties": {
                    "policy": {
                        "type": "string",
                        "enum": [
                            "sparse_trade_bars_only",
                            "explicit_zero_volume_bars",
                            "vendor_declared_no_trade_policy",
                        ],
                    },
                    "meaning": {"type": "string", "minLength": 1},
                    "sequence_gap_interpretation": {"type": "string", "minLength": 1},
                },
            },
            "coverage_claims": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "required_window_count",
                    "right_tail_window_coverage",
                    "bottom_loss_window_coverage",
                    "maxdd_window_coverage",
                    "sequence_gap_count",
                    "duplicate_bar_count",
                ],
                "properties": {
                    "required_window_count": {"type": "integer", "minimum": 1},
                    "right_tail_window_coverage": {"type": "number", "minimum": 0, "maximum": 1},
                    "bottom_loss_window_coverage": {"type": "number", "minimum": 0, "maximum": 1},
                    "maxdd_window_coverage": {"type": "number", "minimum": 0, "maximum": 1},
                    "sequence_gap_count": {"type": "integer", "minimum": 0},
                    "duplicate_bar_count": {"type": "integer", "minimum": 0},
                },
            },
            "synthetic_or_adjusted_flag": {"const": False},
            "template_only_not_real_proof": {"const": False},
            "operator_notes": {"type": "string"},
        },
    }


def _build_field_contract(schema: dict[str, Any]) -> pd.DataFrame:
    records = []
    properties = schema["properties"]
    for field, spec in properties.items():
        expected_type = spec.get("type", "const" if "const" in spec else "object")
        validation = []
        if "const" in spec:
            validation.append(f"const={spec['const']}")
        if "enum" in spec:
            validation.append("enum=" + ",".join(str(item) for item in spec["enum"]))
        if "pattern" in spec:
            validation.append(f"pattern={spec['pattern']}")
        if "minimum" in spec:
            validation.append(f"minimum={spec['minimum']}")
        if "minLength" in spec:
            validation.append(f"minLength={spec['minLength']}")
        records.append(
            {
                "field": field,
                "expected_type": expected_type,
                "required_by_stage154_schema": int(field in schema["required"]),
                "hard_gate": int(field in schema["required"]),
                "also_required_by_stage153": int(field in STAGE153_REQUIRED_FIELDS),
                "validation": "; ".join(validation),
                "real_delivery_rule": "must be completed by vendor/operator; placeholders fail schema",
            }
        )
    return pd.DataFrame(records)


def _template_payload(row: pd.Series, window_count: int) -> dict[str, Any]:
    return {
        "request_id": row["request_id"],
        "vendor_name": "<licensed_vendor_name>",
        "vendor_license": "<license_or_contract_reference>",
        "dataset_id": "<vendor_dataset_id>",
        "query_params": {
            "symbols": [row["vt_symbol"]],
            "interval": "1m",
            "start_ts": row["request_start_ts"],
            "end_ts": row["request_end_ts"],
            "timezone": "Asia/Shanghai",
            "adjustment": "none",
            "source_endpoint": "<vendor_api_endpoint_or_exchange_source>",
        },
        "raw_file": row["expected_raw_file"],
        "raw_file_size_bytes": 0,
        "raw_sha256": "<raw_sha256_hex64>",
        "normalized_file": row["expected_normalized_file"],
        "normalized_sha256": "<normalized_sha256_hex64>",
        "schema_hash": "<schema_hash_hex64>",
        "exchange": row["exchange"],
        "vt_symbol": row["vt_symbol"],
        "request_start_ts": row["request_start_ts"],
        "request_end_ts": row["request_end_ts"],
        "timezone": "Asia/Shanghai",
        "session_calendar": {
            "calendar_id": "<domestic_futures_calendar_id>",
            "trading_day_convention": "<night_session_stitching_rule>",
            "night_session_policy": "<vendor_night_session_policy>",
        },
        "no_trade_bar_policy": {
            "policy": "<sparse_trade_bars_only|explicit_zero_volume_bars|vendor_declared_no_trade_policy>",
            "meaning": "<how to interpret absent minute bars>",
            "sequence_gap_interpretation": "<why sequence gaps are or are not data gaps>",
        },
        "coverage_claims": {
            "required_window_count": int(window_count),
            "right_tail_window_coverage": 0.0,
            "bottom_loss_window_coverage": 0.0,
            "maxdd_window_coverage": 0.0,
            "sequence_gap_count": 0,
            "duplicate_bar_count": 0,
        },
        "synthetic_or_adjusted_flag": True,
        "template_only_not_real_proof": True,
        "operator_notes": "Template only. Replace every placeholder and set both flags to false before delivery.",
    }


def _build_templates(requests: pd.DataFrame, windows: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    validator = Draft202012Validator(schema)
    window_count_by_request = windows.groupby("request_id", dropna=False)["window_id"].count().to_dict()
    records: list[dict[str, Any]] = []
    for _, row in requests.iterrows():
        request_id = str(row["request_id"])
        payload = _template_payload(row, int(window_count_by_request.get(request_id, row.get("required_window_count", 0))))
        path = TEMPLATE_DIR / f"{request_id}.proof.template.json"
        _write_json(path, payload)
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
        records.append(
            {
                "request_id": request_id,
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "request_date": row["request_date"],
                "required_window_count": int(row["required_window_count"]),
                "template_path": str(path),
                "template_written": 1,
                "template_schema_valid": int(len(errors) == 0),
                "template_blocked_reason": "placeholder_and_template_only_flags" if errors else "",
                "expected_proof_file": row["expected_proof_file"],
            }
        )
    return pd.DataFrame(records)


def _completed_positive_payload(request: pd.Series) -> dict[str, Any]:
    return {
        "request_id": request["request_id"],
        "vendor_name": "authorized_vendor",
        "vendor_license": "license_research_use_20260620",
        "dataset_id": "authoritative_1m_ohlcv",
        "query_params": {
            "symbols": [request["vt_symbol"]],
            "interval": "1m",
            "start_ts": request["request_start_ts"],
            "end_ts": request["request_end_ts"],
            "timezone": "Asia/Shanghai",
            "adjustment": "none",
            "source_endpoint": "vendor_historical_ohlcv_endpoint",
        },
        "raw_file": request["expected_raw_file"],
        "raw_file_size_bytes": 1,
        "raw_sha256": "a" * 64,
        "normalized_file": request["expected_normalized_file"],
        "normalized_sha256": "b" * 64,
        "schema_hash": "c" * 64,
        "exchange": request["exchange"],
        "vt_symbol": request["vt_symbol"],
        "request_start_ts": request["request_start_ts"],
        "request_end_ts": request["request_end_ts"],
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
            "required_window_count": int(request["required_window_count"]),
            "right_tail_window_coverage": 1.0,
            "bottom_loss_window_coverage": 1.0,
            "maxdd_window_coverage": 1.0,
            "sequence_gap_count": 0,
            "duplicate_bar_count": 0,
        },
        "synthetic_or_adjusted_flag": False,
        "template_only_not_real_proof": False,
        "operator_notes": "Schema selftest only; not a delivered proof file.",
    }


def _validation_selftests(schema: dict[str, Any], first_request: pd.Series, first_template: dict[str, Any]) -> pd.DataFrame:
    schema_meta_valid = 1
    schema_meta_error = ""
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - recorded as selftest evidence.
        schema_meta_valid = 0
        schema_meta_error = f"{type(exc).__name__}: {exc}"
    validator = Draft202012Validator(schema)
    positive = _completed_positive_payload(first_request)
    cases = [
        ("schema_meta_valid", {}, 1, schema_meta_valid, schema_meta_error),
        ("positive_completed_proof_schema_valid", positive, 1, None, ""),
        ("template_placeholder_blocked", first_template, 0, None, ""),
        ("missing_raw_sha256_blocked", {key: value for key, value in positive.items() if key != "raw_sha256"}, 0, None, ""),
        ("bad_hash_blocked", {**positive, "raw_sha256": "abc"}, 0, None, ""),
        ("synthetic_flag_blocked", {**positive, "synthetic_or_adjusted_flag": True}, 0, None, ""),
        ("template_only_blocked", {**positive, "template_only_not_real_proof": True}, 0, None, ""),
        ("bad_timezone_blocked", {**positive, "timezone": "UTC"}, 0, None, ""),
        (
            "bad_no_trade_policy_blocked",
            {**positive, "no_trade_bar_policy": {**positive["no_trade_bar_policy"], "policy": "unknown_policy"}},
            0,
            None,
            "",
        ),
    ]
    records = []
    for case_id, payload, expect_valid, forced_valid, forced_error in cases:
        if forced_valid is not None:
            observed_valid = int(forced_valid)
            error_count = 0 if observed_valid else 1
            first_error = forced_error
        else:
            errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
            observed_valid = int(len(errors) == 0)
            error_count = len(errors)
            first_error = errors[0].message if errors else ""
        records.append(
            {
                "case_id": case_id,
                "expect_valid": int(expect_valid),
                "observed_valid": observed_valid,
                "pass_now": int(observed_valid == int(expect_valid)),
                "error_count": int(error_count),
                "first_error": first_error,
            }
        )
    return pd.DataFrame(records)


def _anti_misuse_guard(template_index: pd.DataFrame, stage153_summary: dict[str, Any]) -> pd.DataFrame:
    incoming_root = REPO_DIR / "incoming"
    template_dir_under_incoming = str(TEMPLATE_DIR.resolve()).startswith(str(incoming_root.resolve()))
    placeholder_count = 0
    for path_text in template_index["template_path"]:
        text = Path(path_text).read_text(encoding="utf-8")
        if "<" in text and "template_only_not_real_proof" in text:
            placeholder_count += 1
    rows = [
        ("template_dir_separate_from_incoming", int(not template_dir_under_incoming), 1, "anti_operator_error_hard"),
        ("template_file_count", int(len(template_index)), int(len(template_index)), "artifact_hard"),
        ("template_schema_valid_count", int(template_index["template_schema_valid"].sum()), 0, "anti_misuse_hard"),
        ("template_placeholder_marker_count", placeholder_count, int(len(template_index)), "anti_misuse_hard"),
        ("stage153_request_ready_count", _int(stage153_summary, "request_ready_count"), 0, "downstream_hard"),
        ("stage153_feature_build_allowed", _int(stage153_summary, "stage154_feature_build_allowed"), 0, "strategy_hard"),
        ("strategy_rule_created", 0, 0, "strategy_hard"),
        ("true_engine_run", 0, 0, "strategy_hard"),
        ("side_effect_count", 0, 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "guard_id": guard_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required),
                "severity": severity,
            }
            for guard_id, observed, required, severity in rows
        ]
    )


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("proof_schema_written", summary["proof_schema_ready"], 1, "schema_hard"),
        ("proof_schema_meta_valid", summary["schema_meta_valid"], 1, "schema_hard"),
        ("proof_template_count", summary["proof_template_count"], summary["request_count"], "artifact_hard"),
        ("template_schema_valid_count", summary["template_schema_valid_count"], 0, "anti_misuse_hard"),
        ("validation_selftest_pass_count", summary["validation_selftest_pass_count"], summary["validation_selftest_count"], "selftest_hard"),
        ("anti_misuse_guard_pass_count", summary["anti_misuse_guard_pass_count"], summary["anti_misuse_guard_count"], "anti_misuse_hard"),
        ("stage153_request_ready_count", summary["stage153_request_ready_count"], 0, "downstream_hard"),
        ("stage153_feature_build_allowed", summary["stage153_feature_build_allowed"], 0, "downstream_hard"),
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
    field_contract: pd.DataFrame,
    template_index: pd.DataFrame,
    selftest: pd.DataFrame,
    anti_misuse: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    template_cols = [
        "request_id",
        "exchange",
        "vt_symbol",
        "template_written",
        "template_schema_valid",
        "template_blocked_reason",
    ]
    lines = [
        f"# {STAGE} 权威分钟 OHLCV proof schema pack",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只生成 proof schema 与模板，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- JSON Schema Draft 2020-12 是结构化 JSON 校验标准，适合把 vendor/license/query/session/no-trade policy 这些 provenance 字段固化成机器可验合同。",
        "- JSON Schema 官方 structuring 文档建议用 schema 组织复杂字段；本阶段把 `query_params`、`session_calendar`、`no_trade_bar_policy`、`coverage_claims` 拆成嵌套对象，避免只靠自由文本。",
        "- Python jsonschema 的 Draft202012Validator 可直接做本地自测；模板故意 schema-invalid，真实交付必须补完 hash、license、session 与 no-trade policy 后才能过 Stage153。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Proof Field Contract",
        "",
        _md_table(field_contract),
        "",
        "## Template Index Sample",
        "",
        _md_table(template_index[template_cols], max_rows=20),
        "",
        "## Validation Selftest",
        "",
        _md_table(selftest),
        "",
        "## Anti Misuse Guard",
        "",
        _md_table(anti_misuse),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{FIELD_CHART_OUT.name}`",
        f"- `{TEMPLATE_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage154 proof schema/template pack status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["schema", "templates", "template_valid", "selftests", "stage153_release", "rule"]
    values = [
        row["proof_schema_ready"],
        row["proof_template_count"],
        row["template_schema_valid_count"],
        row["validation_selftest_pass_count"],
        row["stage153_feature_build_allowed"],
        row["strategy_rule_created"],
    ]
    colors = ["#0F766E", "#3657D6", "#B91C1C", "#0F766E", "#111827", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Templates are intentionally blocked until real vendor proof is completed")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_field_matrix(field_contract: pd.DataFrame) -> None:
    matrix = field_contract.set_index("field")[
        ["required_by_stage154_schema", "hard_gate", "also_required_by_stage153"]
    ].copy()
    fig, ax = plt.subplots(figsize=(9.5, max(5.2, len(matrix) * 0.42)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Proof field contract matrix")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(FIELD_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_template_counts(template_index: pd.DataFrame) -> None:
    data = (
        template_index.groupby("exchange", dropna=False)
        .agg(template_count=("request_id", "count"), template_schema_valid_count=("template_schema_valid", "sum"))
        .reset_index()
        .sort_values("template_count", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(data["exchange"], data["template_count"], color="#3657D6", label="templates")
    ax.barh(data["exchange"], data["template_schema_valid_count"], color="#B91C1C", label="schema-valid templates")
    ax.set_title("Stage154 proof templates by exchange")
    ax.set_xlabel("count")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    for i, (_, row) in enumerate(data.iterrows()):
        ax.text(row["template_count"] + 0.4, i, int(row["template_count"]), va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(TEMPLATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selftest(selftest: pd.DataFrame) -> None:
    data = selftest.sort_values("case_id", ascending=True)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    colors = np.where(data["pass_now"].eq(1), "#0F766E", "#B91C1C")
    ax.barh(data["case_id"], data["pass_now"], color=colors)
    ax.set_title("Proof schema validation selftests")
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("pass_now")
    ax.grid(axis="x", alpha=0.25)
    for i, (_, row) in enumerate(data.iterrows()):
        ax.text(0.04, i, f"expect={int(row['expect_valid'])}, observed={int(row['observed_valid'])}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate_matrix(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]].copy()
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.48)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage154 gate status")
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
    stage153 = _row(STAGE153_SUMMARY_IN)
    if not stage152 or not stage153:
        raise RuntimeError("missing Stage152 or Stage153 summary input")
    requests = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    windows = _read_csv(STAGE152_WINDOW_CONTRACT_IN)
    if requests.empty or windows.empty:
        raise RuntimeError("missing Stage152 request/window inputs")
    schema = _build_proof_schema(sorted(requests["exchange"].dropna().astype(str).unique().tolist()))
    field_contract = _build_field_contract(schema)
    _write_json(PROOF_SCHEMA_OUT, schema)
    template_index = _build_templates(requests, windows.merge(requests[["request_id", "exchange", "product", "vt_symbol", "request_date"]], on=["exchange", "product", "vt_symbol", "request_date"], how="left"), schema)
    first_template = json.loads(Path(template_index.iloc[0]["template_path"]).read_text(encoding="utf-8"))
    selftest = _validation_selftests(schema, requests.iloc[0], first_template)
    anti_misuse = _anti_misuse_guard(template_index, stage153)
    schema_meta_valid = int(selftest.loc[selftest["case_id"].eq("schema_meta_valid"), "observed_valid"].iloc[0])
    decision = "stage154_authoritative_minute_ohlcv_proof_schema_pack_ready_templates_blocked_no_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "complete_real_proof_raw_normalized_delivery_then_rerun_stage153",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "proof_schema_ready": 1,
        "schema_meta_valid": schema_meta_valid,
        "proof_required_field_count": int(len(PROOF_REQUIRED_FIELDS)),
        "proof_field_contract_count": int(len(field_contract)),
        "request_count": int(len(requests)),
        "proof_template_count": int(len(template_index)),
        "template_written_count": int(template_index["template_written"].sum()),
        "template_schema_valid_count": int(template_index["template_schema_valid"].sum()),
        "validation_selftest_count": int(len(selftest)),
        "validation_selftest_pass_count": int(selftest["pass_now"].sum()),
        "anti_misuse_guard_count": int(len(anti_misuse)),
        "anti_misuse_guard_pass_count": int(anti_misuse["pass_now"].sum()),
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage153_feature_build_allowed": _int(stage153, "stage154_feature_build_allowed"),
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
    _write_csv(field_contract, PROOF_FIELD_CONTRACT_OUT)
    _write_csv(template_index, TEMPLATE_INDEX_OUT)
    _write_csv(selftest, VALIDATION_SELFTEST_OUT)
    _write_csv(anti_misuse, ANTI_MISUSE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, field_contract, template_index, selftest, anti_misuse, gate)

    _plot_path(curve, summary)
    _plot_field_matrix(field_contract)
    _plot_template_counts(template_index)
    _plot_selftest(selftest)
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
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage153_gate_status": str(STAGE153_GATE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "proof_schema": str(PROOF_SCHEMA_OUT),
                "proof_field_contract": str(PROOF_FIELD_CONTRACT_OUT),
                "proof_template_index": str(TEMPLATE_INDEX_OUT),
                "proof_template_dir": str(TEMPLATE_DIR),
                "validation_selftest": str(VALIDATION_SELFTEST_OUT),
                "anti_misuse_guard": str(ANTI_MISUSE_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(FIELD_CHART_OUT),
                    str(TEMPLATE_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://json-schema.org/draft/2020-12",
                "https://json-schema.org/docs",
                "https://json-schema.org/understanding-json-schema/structuring",
                "https://python-jsonschema.readthedocs.io/en/stable/validate/",
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
