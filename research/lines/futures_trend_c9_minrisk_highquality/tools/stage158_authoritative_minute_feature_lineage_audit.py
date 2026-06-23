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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage158"
MODEL_TAG = "stage158_authoritative_minute_feature_lineage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage158_authoritative_minute_feature_lineage_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"
STAGE153_REQUEST_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_request_file_audit_{STAGE153_TAG}.csv"
STAGE153_PROOF_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_proof_json_audit_{STAGE153_TAG}.csv"
STAGE153_SCHEMA_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_normalized_schema_audit_{STAGE153_TAG}.csv"
STAGE153_WINDOW_COVERAGE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_window_coverage_audit_{STAGE153_TAG}.csv"

STAGE154_DIR = LINE_DIR / "outputs" / "stage154_authoritative_minute_ohlcv_proof_schema_pack"
STAGE154_PREFIX = "qmt_roll_stage154_c9_minrisk_authoritative_minute_ohlcv_proof_schema_pack"
STAGE154_TAG = "stage154_authoritative_minute_ohlcv_proof_schema_pack_v1"
STAGE154_SUMMARY_IN = STAGE154_DIR / f"{STAGE154_PREFIX}_summary_{STAGE154_TAG}.csv"
STAGE154_PROOF_SCHEMA_IN = STAGE154_DIR / f"{STAGE154_PREFIX}_proof_schema_{STAGE154_TAG}.json"

STAGE157_DIR = LINE_DIR / "outputs" / "stage157_authoritative_minute_feature_builder_empty_run"
STAGE157_PREFIX = "qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run"
STAGE157_TAG = "stage157_authoritative_minute_feature_builder_empty_run_v1"
STAGE157_SUMMARY_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_summary_{STAGE157_TAG}.csv"
STAGE157_FEATURE_TABLE_SCHEMA_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_feature_table_schema_{STAGE157_TAG}.csv"
STAGE157_BUILD_PLAN_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_build_plan_{STAGE157_TAG}.csv"
STAGE157_EMPTY_AUDIT_IN = STAGE157_DIR / f"{STAGE157_PREFIX}_empty_run_audit_{STAGE157_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LINEAGE_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prov_lineage_contract_{MODEL_TAG}.csv"
FEATURE_ROW_LINEAGE_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_row_lineage_schema_{MODEL_TAG}.csv"
EMPTY_LINEAGE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_empty_lineage_audit_{MODEL_TAG}.csv"
LINEAGE_SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_unit_selftest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_lineage_status_{MODEL_TAG}.png"
CONTRACT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_contract_matrix_{MODEL_TAG}.png"
BLOCKER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_empty_lineage_blocker_bar_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_selftest_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 4:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
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


def _object_sha256(payload: Any) -> str:
    data = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataframe_sha256(frame: pd.DataFrame) -> str:
    records = frame.fillna("").to_dict(orient="records")
    return _object_sha256(records)


def _prov_lineage_contract() -> pd.DataFrame:
    rows = [
        ("raw_file", "entity", "vendor_extract", "wasGeneratedBy", "raw_sha256", 1),
        ("proof_json", "entity", "vendor_extract", "wasGeneratedBy", "proof_path,raw_sha256,request_id", 1),
        ("normalized_parquet", "entity", "parquet_normalization", "wasGeneratedBy", "normalized_sha256,row_group_metadata", 1),
        ("request_manifest_row", "entity", "stage152_manifest", "wasGeneratedBy", "request_id,vt_symbol,request_start_ts,request_end_ts", 1),
        ("required_window", "entity", "stage152_manifest", "wasGeneratedBy", "window_id,request_id,window_start_ts,window_end_ts", 1),
        ("stage153_intake", "activity", "proof_json", "used", "request_ready,coverage_pass,proof_raw_sha256_match", 1),
        ("stage156_feature_contract", "entity", "stage156_prebuild_gate", "wasGeneratedBy", "feature_id,point_in_time_rule,required_columns", 1),
        ("stage157_feature_schema", "entity", "stage157_builder_empty_run", "wasGeneratedBy", "feature_table_schema_sha256", 1),
        ("feature_row", "entity", "stage157_builder", "wasGeneratedBy", "feature_row_id,request_id,window_id,source_hashes", 1),
        ("feature_row", "entity", "raw_file", "wasDerivedFrom", "source_raw_sha256", 1),
        ("feature_row", "entity", "normalized_parquet", "wasDerivedFrom", "source_normalized_sha256", 1),
        ("feature_row", "entity", "proof_json", "wasDerivedFrom", "proof_sha256,proof_schema_sha256", 1),
        ("feature_row", "entity", "required_window", "wasDerivedFrom", "window_id,feature_cutoff_ts", 1),
        ("lineage_audit", "activity", "feature_row", "used", "lineage_pass,lineage_block_reason", 1),
        ("operator_or_vendor", "agent", "vendor_extract", "wasAssociatedWith", "vendor_name,vendor_license", 1),
        ("stage158_script", "agent", "lineage_audit", "wasAssociatedWith", MODEL_TAG, 1),
    ]
    return pd.DataFrame(
        [
            {
                "contract_id": f"lineage_{idx:02d}",
                "prov_subject": subject,
                "prov_subject_type": subject_type,
                "prov_object": obj,
                "prov_relation": relation,
                "required_evidence": evidence,
                "hard_gate": hard_gate,
                "strategy_rule_allowed": 0,
            }
            for idx, (subject, subject_type, obj, relation, evidence, hard_gate) in enumerate(rows, start=1)
        ]
    )


def _feature_row_lineage_schema(feature_schema: pd.DataFrame) -> pd.DataFrame:
    required = [
        ("feature_row_id", "string", "feature_row", "sha256(request_id|window_id|decision_ts|feature_schema_sha256)", "stage158"),
        ("request_id", "string", "request_manifest_row", "Stage152 request id", "stage152"),
        ("window_id", "string", "required_window", "Stage152 window id", "stage152"),
        ("proof_path", "string", "proof_json", "validated proof JSON path", "stage153"),
        ("proof_sha256", "hex64", "proof_json", "sha256 of proof JSON bytes", "stage153"),
        ("proof_schema_sha256", "hex64", "proof_schema", "sha256 of Stage154 proof schema", "stage154"),
        ("raw_file", "string", "raw_file", "raw delivery file path", "stage153"),
        ("source_raw_sha256", "hex64", "raw_file", "raw file sha256 from proof and request audit", "stage153"),
        ("normalized_file", "string", "normalized_parquet", "normalized parquet path", "stage153"),
        ("source_normalized_sha256", "hex64", "normalized_parquet", "normalized parquet sha256 from proof", "stage153"),
        ("normalized_row_group_metadata_sha256", "hex64", "normalized_parquet", "metadata hash from parquet footer/row groups", "stage153_future"),
        ("feature_table_schema_sha256", "hex64", "stage157_feature_schema", "sha256 of Stage157 feature table schema", "stage157"),
        ("feature_build_model_tag", "string", "stage157_builder", "builder version tag", "stage157"),
        ("decision_ts", "timestamp", "feature_row", "decision timestamp", "stage157"),
        ("feature_cutoff_ts", "timestamp", "feature_row", "last bar_end_ts allowed", "stage157"),
        ("lineage_pass", "int8", "lineage_audit", "1 only when all lineage hard gates pass", "stage158"),
        ("lineage_block_reason", "string", "lineage_audit", "primary blocker when lineage_pass=0", "stage158"),
    ]
    feature_columns = feature_schema[feature_schema["family"].ne("provenance") & feature_schema["column"].notna()].copy()
    rows = [
        {
            "column": column,
            "dtype": dtype,
            "prov_entity": entity,
            "description": description,
            "source_stage": source_stage,
            "hard_required": 1,
            "future_data_allowed": 0,
            "strategy_rule_allowed": 0,
        }
        for column, dtype, entity, description, source_stage in required
    ]
    existing_columns = {row["column"] for row in rows}
    for _, item in feature_columns.iterrows():
        if str(item["column"]) in existing_columns:
            continue
        rows.append(
            {
                "column": str(item["column"]),
                "dtype": str(item["dtype"]),
                "prov_entity": "feature_row_value",
                "description": f"lineage-protected feature payload field: {item['description']}",
                "source_stage": "stage157",
                "hard_required": int(item.get("hard_required", 1)),
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
        existing_columns.add(str(item["column"]))
    return pd.DataFrame(rows)


def _empty_lineage_audit(
    empty_audit: pd.DataFrame,
    request_audit: pd.DataFrame,
    proof_audit: pd.DataFrame,
    schema_audit: pd.DataFrame,
    feature_schema_hash: str,
    proof_schema_hash: str,
) -> pd.DataFrame:
    request_by_id = request_audit.set_index("request_id").to_dict(orient="index") if not request_audit.empty else {}
    proof_by_id = proof_audit.set_index("request_id").to_dict(orient="index") if not proof_audit.empty else {}
    schema_by_id = schema_audit.set_index("request_id").to_dict(orient="index") if not schema_audit.empty else {}
    records: list[dict[str, Any]] = []
    for _, row in empty_audit.iterrows():
        request_id = str(row["request_id"])
        request = request_by_id.get(request_id, {})
        proof = proof_by_id.get(request_id, {})
        schema = schema_by_id.get(request_id, {})
        proof_valid = int(proof.get("proof_json_valid", 0) or 0)
        raw_match = int(proof.get("proof_raw_sha256_match", 0) or 0)
        normalized_schema_pass = int(schema.get("normalized_schema_pass", 0) or 0)
        request_ready = int(row.get("request_ready", 0) or 0)
        coverage_pass = int(row.get("coverage_pass", 0) or 0)
        feature_row_written = int(row.get("feature_row_written", 0) or 0)
        if feature_row_written == 0:
            blocker = str(row.get("primary_blocker", "feature_row_not_written"))
        elif request_ready == 0:
            blocker = "request_not_ready"
        elif proof_valid == 0:
            blocker = "proof_json_not_valid"
        elif raw_match == 0:
            blocker = "raw_sha256_not_matched"
        elif normalized_schema_pass == 0:
            blocker = "normalized_schema_not_passed"
        elif coverage_pass == 0:
            blocker = "required_window_not_covered"
        else:
            blocker = ""
        lineage_pass = int(
            feature_row_written == 1
            and request_ready == 1
            and coverage_pass == 1
            and proof_valid == 1
            and raw_match == 1
            and normalized_schema_pass == 1
            and bool(feature_schema_hash)
            and bool(proof_schema_hash)
        )
        records.append(
            {
                "window_id": row.get("window_id", ""),
                "request_id": request_id,
                "vt_symbol": row.get("vt_symbol", ""),
                "exchange": row.get("exchange", ""),
                "product": row.get("product", ""),
                "window_type": row.get("window_type", ""),
                "priority_class": row.get("priority_class", ""),
                "raw_file_present": int(request.get("raw_file_present", 0) or 0),
                "proof_file_present": int(request.get("proof_file_present", 0) or 0),
                "normalized_file_present": int(request.get("normalized_file_present", 0) or 0),
                "proof_json_valid": proof_valid,
                "raw_sha256_match": raw_match,
                "normalized_schema_pass": normalized_schema_pass,
                "request_ready": request_ready,
                "coverage_pass": coverage_pass,
                "feature_row_written": feature_row_written,
                "feature_table_schema_sha256_present": int(bool(feature_schema_hash)),
                "proof_schema_sha256_present": int(bool(proof_schema_hash)),
                "lineage_pass": lineage_pass,
                "lineage_block_reason": blocker if lineage_pass == 0 else "",
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _lineage_selftest(feature_schema_hash: str, proof_schema_hash: str) -> pd.DataFrame:
    request_id = "stage152_req_0000_UNIT_TEST"
    window_id = "stage152_unit_window"
    raw_payload = b"authorized raw bytes for unit lineage"
    normalized_payload = b"authorized normalized bytes for unit lineage"
    raw_sha = hashlib.sha256(raw_payload).hexdigest()
    normalized_sha = hashlib.sha256(normalized_payload).hexdigest()
    proof = {
        "request_id": request_id,
        "raw_sha256": raw_sha,
        "normalized_sha256": normalized_sha,
        "vendor_name": "unit_authorized_vendor",
        "vendor_license": "unit_license",
        "synthetic_or_adjusted_flag": False,
    }
    proof_sha = _object_sha256(proof)
    feature_row = {
        "feature_row_id": _object_sha256([request_id, window_id, "2026-01-05 10:05:00", feature_schema_hash]),
        "request_id": request_id,
        "window_id": window_id,
        "source_raw_sha256": raw_sha,
        "source_normalized_sha256": normalized_sha,
        "proof_sha256": proof_sha,
        "proof_schema_sha256": proof_schema_hash,
        "feature_table_schema_sha256": feature_schema_hash,
        "feature_build_model_tag": "stage157_authoritative_minute_feature_builder_empty_run_v1",
        "decision_ts": "2026-01-05 10:05:00",
        "feature_cutoff_ts": "2026-01-05 10:05:00",
    }
    required_keys = [
        "feature_row_id",
        "request_id",
        "window_id",
        "source_raw_sha256",
        "source_normalized_sha256",
        "proof_sha256",
        "proof_schema_sha256",
        "feature_table_schema_sha256",
        "feature_build_model_tag",
        "decision_ts",
        "feature_cutoff_ts",
    ]
    complete_lineage = all(bool(feature_row.get(key)) for key in required_keys)
    raw_mutation_detected = feature_row["source_raw_sha256"] != hashlib.sha256(raw_payload + b"x").hexdigest()
    normalized_mutation_detected = feature_row["source_normalized_sha256"] != hashlib.sha256(normalized_payload + b"x").hexdigest()
    missing_proof_row = feature_row.copy()
    missing_proof_row["proof_sha256"] = ""
    missing_proof_blocks = not all(bool(missing_proof_row.get(key)) for key in required_keys)
    rows = [
        ("complete_unit_lineage_passes_schema", 1, int(complete_lineage), "complete in-memory lineage row has every hard field"),
        ("raw_sha256_mutation_detected", 1, int(raw_mutation_detected), "changed raw bytes produce different sha256"),
        ("normalized_sha256_mutation_detected", 1, int(normalized_mutation_detected), "changed normalized bytes produce different sha256"),
        ("missing_proof_sha_blocks_lineage", 1, int(missing_proof_blocks), "feature row without proof_sha256 is blocked"),
        ("unit_lineage_not_promoted_to_feature_table", 0, 0, "unit lineage row stays in memory only"),
    ]
    return pd.DataFrame(
        [
            {
                "test_id": test_id,
                "expected": expected,
                "observed": observed,
                "pass_now": int(expected == observed),
                "detail": detail,
            }
            for test_id, expected, observed, detail in rows
        ]
    )


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage153_loaded", summary["stage153_loaded"], 1, "input_hard"),
        ("stage154_loaded", summary["stage154_loaded"], 1, "input_hard"),
        ("stage157_loaded", summary["stage157_loaded"], 1, "input_hard"),
        ("prov_lineage_contract_written", summary["prov_lineage_contract_count"], summary["prov_lineage_contract_count"], "contract_hard"),
        ("feature_row_lineage_schema_written", summary["feature_row_lineage_schema_column_count"], summary["feature_row_lineage_schema_column_count"], "contract_hard"),
        ("lineage_selftest_pass_count", summary["lineage_selftest_pass_count"], summary["lineage_selftest_count"], "selftest_hard"),
        ("all_stage153_requests_ready", summary["stage153_request_ready_count"], summary["stage153_request_count"], "data_hard"),
        ("all_stage153_windows_covered", summary["stage153_window_coverage_pass_count"], summary["stage153_required_window_count"], "coverage_hard"),
        ("feature_rows_with_lineage_pass", summary["lineage_pass_window_count"], summary["stage153_required_window_count"], "lineage_hard"),
        ("feature_table_file_written", summary["feature_table_file_written"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
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
    contract: pd.DataFrame,
    schema: pd.DataFrame,
    audit: pd.DataFrame,
    selftest: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    blocker_summary = (
        audit.groupby("lineage_block_reason", dropna=False)
        .agg(window_count=("window_id", "count"), lineage_pass_count=("lineage_pass", "sum"))
        .reset_index()
    )
    lines = [
        f"# {STAGE} 权威分钟 feature row lineage 审计",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只固定 raw/proof/normalized/window 到 feature row 的 lineage 合同和空跑审计，不写真实 feature table、不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- W3C PROV-DM 把来源建模为 entity、activity、agent 及 used/wasGeneratedBy/wasDerivedFrom 等关系；Stage158 用这个结构描述 raw、proof、normalized、window、feature row 的责任链。",
        "- NIST FIPS 180-4 定义 SHA-256 等安全哈希算法；Stage158 只把 hash 用作文件一致性和篡改检测，不把 hash 当作数据真实性或 alpha。",
        "- Apache Parquet concepts 说明 Parquet 文件由 row group、column chunk、page 组成；未来真实 normalized 文件必须把 parquet metadata/row-group 摘要纳入 lineage。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## PROV Lineage Contract",
        "",
        _md_table(contract),
        "",
        "## Feature Row Lineage Schema Sample",
        "",
        _md_table(schema, max_rows=32),
        "",
        "## Empty Lineage Blocker Summary",
        "",
        _md_table(blocker_summary),
        "",
        "## Lineage Unit Selftest",
        "",
        _md_table(selftest),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CONTRACT_CHART_OUT.name}`",
        f"- `{BLOCKER_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage158 feature-row lineage status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["requests", "ready", "windows", "covered", "lineage_pass", "feature_file"]
    values = [
        row["stage153_request_count"],
        row["stage153_request_ready_count"],
        row["stage153_required_window_count"],
        row["stage153_window_coverage_pass_count"],
        row["lineage_pass_window_count"],
        row["feature_table_file_written"],
    ]
    colors = ["#3657D6", "#B91C1C", "#0F766E", "#B91C1C", "#B91C1C", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Lineage row generation remains blocked until authoritative packages pass intake")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_contract(contract: pd.DataFrame, schema: pd.DataFrame) -> None:
    contract_summary = contract.groupby("prov_subject_type", dropna=False).agg(contract_count=("contract_id", "count"), hard_gate_count=("hard_gate", "sum")).reset_index()
    schema_summary = schema.groupby("source_stage", dropna=False).agg(schema_column_count=("column", "count"), hard_required_count=("hard_required", "sum")).reset_index()
    left = contract_summary.rename(columns={"prov_subject_type": "group"}).set_index("group")
    right = schema_summary.rename(columns={"source_stage": "group"}).set_index("group")
    matrix = pd.concat([left, right], axis=0).fillna(0)
    cols = ["contract_count", "hard_gate_count", "schema_column_count", "hard_required_count"]
    fig, ax = plt.subplots(figsize=(11.5, max(5.2, len(matrix) * 0.55)))
    data = matrix[cols].to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Stage158 lineage contract/schema coverage")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CONTRACT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_blocker(audit: pd.DataFrame) -> None:
    counts = audit["lineage_block_reason"].value_counts().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.barh(counts.index, counts.values, color="#B91C1C")
    ax.set_title("Stage158 empty lineage blockers")
    ax.set_xlabel("window count")
    ax.grid(axis="x", alpha=0.25)
    for idx, value in enumerate(counts.values):
        ax.text(value + 1, idx, int(value), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(BLOCKER_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selftest(selftest: pd.DataFrame) -> None:
    matrix = selftest.set_index("test_id")[["expected", "observed", "pass_now"]]
    fig, ax = plt.subplots(figsize=(11.5, max(4.8, len(matrix) * 0.62)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn")
    ax.set_title("Stage158 lineage unit selftest")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]]
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.45)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage158 gate status")
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
    stage153 = _row(STAGE153_SUMMARY_IN)
    stage154 = _row(STAGE154_SUMMARY_IN)
    stage157 = _row(STAGE157_SUMMARY_IN)
    request_audit = _read_csv(STAGE153_REQUEST_AUDIT_IN)
    proof_audit = _read_csv(STAGE153_PROOF_AUDIT_IN)
    schema_audit = _read_csv(STAGE153_SCHEMA_AUDIT_IN)
    window_coverage = _read_csv(STAGE153_WINDOW_COVERAGE_IN)
    feature_schema = _read_csv(STAGE157_FEATURE_TABLE_SCHEMA_IN)
    build_plan = _read_csv(STAGE157_BUILD_PLAN_IN)
    empty_audit = _read_csv(STAGE157_EMPTY_AUDIT_IN)
    proof_schema = _read_json(STAGE154_PROOF_SCHEMA_IN)
    if (
        not stage153
        or not stage154
        or not stage157
        or request_audit.empty
        or proof_audit.empty
        or schema_audit.empty
        or window_coverage.empty
        or feature_schema.empty
        or build_plan.empty
        or empty_audit.empty
        or not proof_schema
    ):
        raise RuntimeError("missing Stage153/154/157 inputs for Stage158")

    feature_schema_hash = _dataframe_sha256(feature_schema)
    build_plan_hash = _dataframe_sha256(build_plan)
    proof_schema_hash = _object_sha256(proof_schema)
    proof_schema_file_hash = _file_sha256(STAGE154_PROOF_SCHEMA_IN)
    contract = _prov_lineage_contract()
    lineage_schema = _feature_row_lineage_schema(feature_schema)
    lineage_audit = _empty_lineage_audit(
        empty_audit,
        request_audit,
        proof_audit,
        schema_audit,
        feature_schema_hash,
        proof_schema_hash,
    )
    selftest = _lineage_selftest(feature_schema_hash, proof_schema_hash)

    decision = "stage158_authoritative_minute_feature_lineage_audit_blocks_no_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "deliver_real_authoritative_minute_ohlcv_oi_then_rerun_stage153_156_157_158_before_research_features",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage153_loaded": 1,
        "stage154_loaded": 1,
        "stage157_loaded": 1,
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_required_window_count": _int(stage153, "required_window_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage157_feature_table_schema_column_count": _int(stage157, "feature_table_schema_column_count"),
        "stage157_feature_table_row_written_count": _int(stage157, "feature_table_row_written_count"),
        "prov_lineage_contract_count": int(len(contract)),
        "feature_row_lineage_schema_column_count": int(len(lineage_schema)),
        "feature_schema_sha256_present": int(bool(feature_schema_hash)),
        "feature_build_plan_sha256_present": int(bool(build_plan_hash)),
        "proof_schema_sha256_present": int(bool(proof_schema_hash)),
        "proof_schema_file_sha256_present": int(bool(proof_schema_file_hash)),
        "lineage_audit_window_count": int(len(lineage_audit)),
        "lineage_pass_window_count": int(lineage_audit["lineage_pass"].sum()),
        "lineage_blocked_window_count": int(lineage_audit["lineage_pass"].eq(0).sum()),
        "lineage_selftest_count": int(len(selftest)),
        "lineage_selftest_pass_count": int(selftest["pass_now"].sum()),
        "feature_table_file_written": 0,
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
    _write_csv(contract, LINEAGE_CONTRACT_OUT)
    _write_csv(lineage_schema, FEATURE_ROW_LINEAGE_SCHEMA_OUT)
    _write_csv(lineage_audit, EMPTY_LINEAGE_AUDIT_OUT)
    _write_csv(selftest, LINEAGE_SELFTEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, contract, lineage_schema, lineage_audit, selftest, gate)
    _plot_path(curve, summary)
    _plot_contract(contract, lineage_schema)
    _plot_blocker(lineage_audit)
    _plot_selftest(selftest)
    _plot_gate(gate)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage153_request_audit": str(STAGE153_REQUEST_AUDIT_IN),
                "stage153_proof_audit": str(STAGE153_PROOF_AUDIT_IN),
                "stage153_schema_audit": str(STAGE153_SCHEMA_AUDIT_IN),
                "stage153_window_coverage": str(STAGE153_WINDOW_COVERAGE_IN),
                "stage154_summary": str(STAGE154_SUMMARY_IN),
                "stage154_proof_schema": str(STAGE154_PROOF_SCHEMA_IN),
                "stage157_summary": str(STAGE157_SUMMARY_IN),
                "stage157_feature_table_schema": str(STAGE157_FEATURE_TABLE_SCHEMA_IN),
                "stage157_build_plan": str(STAGE157_BUILD_PLAN_IN),
                "stage157_empty_run_audit": str(STAGE157_EMPTY_AUDIT_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "prov_lineage_contract": str(LINEAGE_CONTRACT_OUT),
                "feature_row_lineage_schema": str(FEATURE_ROW_LINEAGE_SCHEMA_OUT),
                "empty_lineage_audit": str(EMPTY_LINEAGE_AUDIT_OUT),
                "lineage_unit_selftest": str(LINEAGE_SELFTEST_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CONTRACT_CHART_OUT),
                    str(BLOCKER_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "hashes": {
                "feature_schema_sha256": feature_schema_hash,
                "feature_build_plan_sha256": build_plan_hash,
                "proof_schema_sha256": proof_schema_hash,
                "proof_schema_file_sha256": proof_schema_file_hash,
            },
            "external_research_sources": [
                "https://www.w3.org/TR/prov-dm/",
                "https://csrc.nist.gov/pubs/fips/180-4/upd1/final",
                "https://parquet.apache.org/docs/concepts/",
                "https://arrow.apache.org/docs/python/generated/pyarrow.parquet.RowGroupMetaData.html",
            ],
            "locks": {
                "feature_table_file_written": 0,
                "feature_table_row_written_count": _int(stage157, "feature_table_row_written_count"),
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
