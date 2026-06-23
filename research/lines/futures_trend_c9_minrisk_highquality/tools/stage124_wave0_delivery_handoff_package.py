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
STAGE = "Stage124"
MODEL_TAG = "stage124_wave0_delivery_handoff_package_v1"
OUTPUT_PREFIX = "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE116_DIR = LINE_DIR / "outputs" / "stage116_wave0_pipeline_intake_packet"
STAGE116_REQUEST_PACKET_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_packet_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_MANIFEST_TEMPLATE_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE120_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"
STAGE120_CONTRACT_IN = (
    STAGE120_DIR
    / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_canonical_field_contract_"
    "stage120_wave0_schema_contract_audit_v1.csv"
)
STAGE120_REQUEST_SCHEMA_IN = (
    STAGE120_DIR
    / "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_w0_request_schema_status_"
    "stage120_wave0_schema_contract_audit_v1.csv"
)
STAGE123_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage123_wave0_intake_chain_checkpoint"
    / "qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_summary_"
    "stage123_wave0_intake_chain_checkpoint_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FILE_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_file_contract_{MODEL_TAG}.csv"
PROOF_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_field_contract_{MODEL_TAG}.csv"
READINESS_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_gate_status_{MODEL_TAG}.csv"
DATA_PACKAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_datapackage_descriptor_{MODEL_TAG}.json"
SHA256_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_SHA256SUMS_template_{MODEL_TAG}.txt"
HANDOFF_README_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_W0_DELIVERY_README_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_delivery_contract_{MODEL_TAG}.png"
ARTIFACT_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_readiness_matrix_{MODEL_TAG}.png"
BATCH_BURDEN_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_artifact_burden_{MODEL_TAG}.png"
SCHEMA_GROUP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_group_requirement_matrix_{MODEL_TAG}.png"

DECISION = "stage124_wave0_delivery_handoff_package_built_no_real_data_no_strategy"
WAVE_ID = "W0_pipeline_smoke"
MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"
STAGE123_REAL_COMMAND = (
    ".py311/bin/python "
    "research/lines/futures_trend_c9_minrisk_highquality/tools/"
    "stage123_wave0_intake_chain_checkpoint.py "
    "--drop-dir <real_drop_dir> --case-id real_w0_drop "
    "--expected-stage112-intake 1 --no-restore"
)


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


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "daily_return"]:
        if column in curve.columns:
            curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage123 = _read_csv(STAGE123_SUMMARY_IN)
    if not stage123.empty:
        row = stage123.iloc[0]
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


def _schema_short(schema: str) -> str:
    return "mbo_l3" if schema == MBO else "mbp10_l2"


def _safe_symbol(symbol: str) -> str:
    return symbol.replace(".", "_").replace("/", "_").replace(" ", "_")


def _request_base_path(row: pd.Series) -> str:
    trading_day = pd.Timestamp(row["trading_day"]).strftime("%Y%m%d")
    schema = _schema_short(_clean(row["required_schema_request"]))
    symbol = _safe_symbol(_clean(row["vt_symbol"]))
    return f"{WAVE_ID}/{row['batch_id']}/{row['request_id']}/{row['request_id']}__{symbol}__{trading_day}__{schema}"


def _build_file_contract(requests: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    role_specs = [
        {
            "artifact_role": "raw",
            "stage119_detect_rule": "path contains request_id and either a raw directory/name or raw suffix",
            "expected_suffix": "<vendor_raw_ext>",
            "manifest_column": "raw_file",
            "integrity_requirement": "raw_sha256 must match delivered file bytes",
            "stage117_hard_gate": "raw_file_exists; raw_sha256_match",
            "stage120_hard_gate": "",
        },
        {
            "artifact_role": "normalized_parquet",
            "stage119_detect_rule": "path contains request_id and file suffix is .parquet",
            "expected_suffix": "parquet",
            "manifest_column": "normalized_parquet_file",
            "integrity_requirement": "Parquet footer readable; schema_hash and canonical fields auditable",
            "stage117_hard_gate": "parquet_file_exists; parquet_readable; ts_event/ts_recv present",
            "stage120_hard_gate": "canonical schema fields matched",
        },
        {
            "artifact_role": "proof",
            "stage119_detect_rule": "path contains request_id and JSON path/name contains proof",
            "expected_suffix": "json",
            "manifest_column": "proof_file",
            "integrity_requirement": "proof JSON must include timestamp span, row_count, sequence_gap_count=0",
            "stage117_hard_gate": "proof_file_exists; continuity proof present",
            "stage120_hard_gate": "",
        },
    ]
    for _, row in requests.iterrows():
        base = _request_base_path(row)
        for spec in role_specs:
            artifact_role = spec["artifact_role"]
            if artifact_role == "raw":
                rel_path = f"{base}__raw.<vendor_raw_ext>"
            elif artifact_role == "normalized_parquet":
                rel_path = f"{base}__normalized.parquet"
            else:
                rel_path = f"{base}__proof.json"
            rows.append(
                {
                    "wave_id": WAVE_ID,
                    "request_id": row["request_id"],
                    "batch_id": row["batch_id"],
                    "exchange": row["exchange"],
                    "product": row["product"],
                    "vt_symbol": row["vt_symbol"],
                    "trading_day": row["trading_day"],
                    "request_start": row["request_start"],
                    "request_end": row["request_end"],
                    "required_schema_request": row["required_schema_request"],
                    "artifact_role": artifact_role,
                    "required_now": 1,
                    "recommended_relative_path": rel_path,
                    "expected_suffix": spec["expected_suffix"],
                    "stage119_detect_rule": spec["stage119_detect_rule"],
                    "manifest_column": spec["manifest_column"],
                    "integrity_requirement": spec["integrity_requirement"],
                    "stage117_hard_gate": spec["stage117_hard_gate"],
                    "stage120_hard_gate": spec["stage120_hard_gate"],
                    "strategy_use_allowed_now": 0,
                    "rule_preflight_allowed_now": 0,
                }
            )
    return pd.DataFrame(rows)


def _build_proof_contract() -> pd.DataFrame:
    rows = [
        ("vendor", 1, "non-empty; must not start with synthetic", "vendor", "Identifies authorized data provider."),
        ("license_id", 1, "non-empty production/research entitlement id", "license_id", "Blocks unlicensed or ambiguous samples."),
        ("dataset", 1, "non-empty; must not contain synthetic/smoke", "dataset", "Dataset name/version."),
        ("schema_hash", 1, "sha256 of delivered normalized schema/field dictionary", "schema_hash", "Cross-checks schema drift."),
        ("field_dictionary_version", 1, "non-empty version string", "field_dictionary_version", "Documents field semantics."),
        ("ts_event_timezone", 1, "Asia/Shanghai or explicit exchange timezone mapping", "ts_event_timezone", "Prevents time-zone drift."),
        ("ts_recv_timezone", 1, "capture timestamp timezone", "ts_recv_timezone", "Needed for latency and capture ordering."),
        ("first_ts_event", 1, "first event timestamp <= request_start", "first_ts_event", "Stage117 checks request span coverage."),
        ("last_ts_event", 1, "last event timestamp >= request_end", "last_ts_event", "Stage117 checks request span coverage."),
        ("row_count", 1, ">0", "row_count", "Rejects empty normalized files."),
        ("sequence_gap_count", 1, "0", "sequence_gap_count", "No missing sequence proof."),
        (
            "capture_continuity_proof",
            1,
            "non-empty proof id/path/text",
            "capture_continuity_proof",
            "Explains why sequence_gap_count is trusted.",
        ),
        (
            "synthetic_fixture",
            0,
            "absent or false; true is never real W0",
            "notes/vendor/dataset",
            "Synthetic fixtures are anti-selection selftests only.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "proof_json_field": field,
                "required_for_real_w0": required,
                "required_value_or_rule": rule,
                "target_manifest_column": column,
                "notes": notes,
            }
            for field, required, rule, column, notes in rows
        ]
    )


def _build_readiness_gates(
    requests: pd.DataFrame,
    manifest_template: pd.DataFrame,
    contract: pd.DataFrame,
    request_schema: pd.DataFrame,
    file_contract: pd.DataFrame,
    proof_contract: pd.DataFrame,
) -> pd.DataFrame:
    request_count = len(requests)
    expected_file_count = request_count * 3
    stage123_available = int(STAGE123_SUMMARY_IN.exists() and not _read_csv(STAGE123_SUMMARY_IN).empty)
    contract_hash_present = int("contract_hash" in contract.columns and contract["contract_hash"].astype(str).str.len().gt(0).any())
    schema_mapped = int(request_schema["schema_contract_mapped"].sum()) if "schema_contract_mapped" in request_schema.columns else 0
    real_stage112_ready = 0
    gates = [
        {
            "gate_id": "stage116_w0_request_packet_available",
            "observed": f"{request_count}",
            "required": ">0",
            "pass_now": int(request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage116_manifest_template_available",
            "observed": f"{len(manifest_template)}",
            "required": f"{request_count}",
            "pass_now": int(len(manifest_template) == request_count and request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage120_schema_contract_available",
            "observed": f"fields={len(contract)} contract_hash={contract_hash_present}",
            "required": "48 fields with contract_hash",
            "pass_now": int(len(contract) == 48 and contract_hash_present),
            "severity": "planning_hard",
        },
        {
            "gate_id": "request_schema_mapped",
            "observed": f"{schema_mapped}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(schema_mapped == request_count and request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage123_checkpoint_available",
            "observed": str(stage123_available),
            "required": "1",
            "pass_now": stage123_available,
            "severity": "orchestration_hard",
        },
        {
            "gate_id": "delivery_file_contract_generated",
            "observed": f"{len(file_contract)}/{expected_file_count}",
            "required": f"{expected_file_count}/{expected_file_count}",
            "pass_now": int(len(file_contract) == expected_file_count and expected_file_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "proof_field_contract_generated",
            "observed": f"{int(proof_contract['required_for_real_w0'].sum())} required fields",
            "required": ">=12 required fields plus synthetic block",
            "pass_now": int(int(proof_contract["required_for_real_w0"].sum()) >= 12),
            "severity": "planning_hard",
        },
        {
            "gate_id": "strategy_locks_zero",
            "observed": "strategy_use_allowed_now=0; rule_preflight_allowed_now=0",
            "required": "0",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "real_w0_files_present",
            "observed": "0/123",
            "required": "123/123 delivered files",
            "pass_now": 0,
            "severity": "data_hard",
        },
        {
            "gate_id": "real_w0_stage112_ready",
            "observed": str(real_stage112_ready),
            "required": "1 only after Stage123 real drop pass",
            "pass_now": real_stage112_ready,
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(gates)


def _write_sha256_template(file_contract: pd.DataFrame) -> None:
    raw_rows = file_contract[file_contract["artifact_role"].eq("raw")].copy()
    lines = [
        "# Replace SHA256_PLACEHOLDER with the raw file digest for each delivered raw artifact.",
        "# Stage119 computes the raw digest again; Stage117 blocks any mismatch.",
    ]
    for _, row in raw_rows.iterrows():
        lines.append(f"SHA256_PLACEHOLDER  {row['recommended_relative_path']}")
    SHA256_TEMPLATE_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_data_package_descriptor(file_contract: pd.DataFrame, proof_contract: pd.DataFrame, gates: pd.DataFrame) -> None:
    descriptor = {
        "profile": "stage124-w0-delivery-handoff-package-v1",
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "wave_id": WAVE_ID,
        "description": "Machine-usable W0 delivery handoff descriptor; not strategy evidence.",
        "resources": [
            {
                "name": "delivery_file_contract",
                "path": FILE_CONTRACT_OUT.name,
                "format": "csv",
                "row_count": int(len(file_contract)),
            },
            {
                "name": "proof_field_contract",
                "path": PROOF_CONTRACT_OUT.name,
                "format": "csv",
                "row_count": int(len(proof_contract)),
            },
            {
                "name": "readiness_gate_status",
                "path": READINESS_GATE_OUT.name,
                "format": "csv",
                "row_count": int(len(gates)),
            },
            {
                "name": "sha256sums_template",
                "path": SHA256_TEMPLATE_OUT.name,
                "format": "text",
                "row_count": int(file_contract["artifact_role"].eq("raw").sum()),
            },
        ],
        "real_w0_validation_command": STAGE123_REAL_COMMAND,
        "strategy_use_allowed_now": 0,
        "rule_preflight_allowed_now": 0,
    }
    DATA_PACKAGE_OUT.write_text(json.dumps(_json_safe(descriptor), indent=2, ensure_ascii=False), encoding="utf-8")


def _write_handoff_readme(file_contract: pd.DataFrame, proof_contract: pd.DataFrame, gates: pd.DataFrame) -> None:
    role_counts = file_contract.groupby("artifact_role").size().reset_index(name="required_file_count")
    readme = f"""# Stage124 W0 Delivery Handoff Package

## Purpose

This package translates the W0 request packet into a deterministic file-level delivery contract. It is not a trading rule, not a true engine run, and not evidence for a strategy candidate.

## Required Files

{_md_table(role_counts)}

Each request must include:

- one raw vendor artifact whose path includes the `request_id` and a raw role marker;
- one normalized Parquet artifact whose path includes the `request_id` and ends in `.parquet`;
- one proof JSON artifact whose path includes the `request_id` and a proof role marker.

The recommended relative paths are listed in `{FILE_CONTRACT_OUT.name}`. Raw checksums are listed as placeholders in `{SHA256_TEMPLATE_OUT.name}` and must be replaced with real SHA-256 digests at delivery time.

## Proof JSON Fields

{_md_table(proof_contract)}

## Real Drop Validation

After the real W0 files are placed under a drop directory, run:

```bash
{STAGE123_REAL_COMMAND}
```

Stage112/113 remains blocked unless Stage123 reports `final_stage112_ready_count=1`, Stage117 hard accepts all 41 requests, and Stage120 passes the canonical schema contract.

## Readiness Gates

{_md_table(gates)}
"""
    HANDOFF_README_OUT.write_text(readme, encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, requests: pd.DataFrame) -> None:
    request_dates = pd.to_datetime(requests["trading_day"], errors="coerce")
    points = _nearest_curve_points(curve, request_dates)
    points = points.join(requests[["required_schema_request"]].reset_index(drop=True))
    colors = points["required_schema_request"].map({MBP10: "#0F766E", MBO: "#7C2D12"}).fillna("#0369A1")
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=colors, s=42, alpha=0.7)
    axes[0].set_ylabel("equity (m)")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[1].scatter(points["date"], points["drawdown_pct"], color=colors, s=42, alpha=0.7)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=colors, s=42, alpha=0.7)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle("Stage124 W0 delivery contract mapped onto official path; no real W0 delivered")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_artifact_matrix() -> None:
    rows = []
    columns = [
        "recommended_path",
        "stage119_detectable",
        "stage117_manifest_field",
        "integrity_or_proof_required",
        "actual_file_present",
        "strategy_lock_zero",
    ]
    for role in ["raw", "normalized_parquet", "proof"]:
        values = [1, 1, 1, 1, 0, 1]
        rows.append({"artifact_role": role, **dict(zip(columns, values))})
    matrix = pd.DataFrame(rows).set_index("artifact_role")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    image = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(len(matrix.index)):
        for x in range(len(matrix.columns)):
            ax.text(x, y, "P" if int(matrix.iloc[y, x]) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage124 artifact readiness matrix; actual files intentionally still missing")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(ARTIFACT_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_batch_burden(file_contract: pd.DataFrame) -> None:
    pivot = file_contract.pivot_table(index="batch_id", columns="artifact_role", values="request_id", aggfunc="count", fill_value=0)
    pivot = pivot.sort_index()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = {"raw": "#0F766E", "normalized_parquet": "#0369A1", "proof": "#A16207"}
    pivot[["raw", "normalized_parquet", "proof"]].plot(kind="bar", stacked=True, ax=ax, color=colors)
    ax.set_ylabel("required file count")
    ax.set_title("Stage124 W0 delivery burden by batch")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BATCH_BURDEN_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_group_matrix(contract: pd.DataFrame) -> None:
    grouped = (
        contract.groupby("semantic_group")[["required_for_mbp10", "required_for_mbo"]]
        .sum()
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(9, 6.5))
    image = ax.imshow(grouped.to_numpy(), aspect="auto", cmap="PuBuGn")
    ax.set_xticks(range(len(grouped.columns)))
    ax.set_xticklabels(["MBP-10", "MBO L3"], rotation=15, ha="right")
    ax.set_yticks(range(len(grouped.index)))
    ax.set_yticklabels(grouped.index, fontsize=8)
    for y in range(len(grouped.index)):
        for x in range(len(grouped.columns)):
            ax.text(x, y, str(int(grouped.iloc[y, x])), ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage124 canonical schema groups required by W0")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(SCHEMA_GROUP_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, gates: pd.DataFrame, file_contract: pd.DataFrame, proof_contract: pd.DataFrame) -> None:
    row = summary.iloc[0]
    role_counts = file_contract.groupby("artifact_role").size().reset_index(name="required_file_count")
    report = f"""# Stage124 W0 delivery handoff package

## Decision

- decision: `{row['decision']}`
- nature: delivery handoff and readiness package only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- real validation command: `{STAGE123_REAL_COMMAND}`

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## File Contract Summary

{_md_table(role_counts)}

## Readiness Gates

{_md_table(gates)}

## Proof Contract

{_md_table(proof_contract)}

## Visual Outputs

- official path delivery contract: `{PATH_CHART_OUT}`
- artifact readiness matrix: `{ARTIFACT_MATRIX_CHART_OUT}`
- batch artifact burden: `{BATCH_BURDEN_CHART_OUT}`
- schema group requirement matrix: `{SCHEMA_GROUP_CHART_OUT}`

## Judgment

The W0 request packet is now translated into a deterministic delivery contract with raw, normalized Parquet, and proof artifacts for every request. The package is ready for real W0 receipt, but real files are still absent and Stage112/113 remains blocked.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    requests = _read_csv(STAGE116_REQUEST_PACKET_IN)
    manifest_template = _read_csv(STAGE116_MANIFEST_TEMPLATE_IN)
    contract = _read_csv(STAGE120_CONTRACT_IN)
    request_schema = _read_csv(STAGE120_REQUEST_SCHEMA_IN)
    if requests.empty:
        raise RuntimeError(f"missing Stage116 request packet: {STAGE116_REQUEST_PACKET_IN}")
    if manifest_template.empty:
        raise RuntimeError(f"missing Stage116 manifest template: {STAGE116_MANIFEST_TEMPLATE_IN}")
    if contract.empty or request_schema.empty:
        raise RuntimeError("missing Stage120 schema contract outputs")
    for frame in [requests, manifest_template, request_schema]:
        for column in ["trading_day", "request_start", "request_end"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    file_contract = _build_file_contract(requests)
    proof_contract = _build_proof_contract()
    gates = _build_readiness_gates(requests, manifest_template, contract, request_schema, file_contract, proof_contract)
    expected_file_count = int(len(file_contract))
    request_count = int(len(requests))
    batch_count = int(requests["batch_id"].nunique())
    contract_hash = _clean(contract["contract_hash"].iloc[0]) if "contract_hash" in contract.columns and not contract.empty else ""
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
                "request_count": request_count,
                "batch_count": batch_count,
                "expected_delivery_file_count": expected_file_count,
                "expected_raw_file_count": int(file_contract["artifact_role"].eq("raw").sum()),
                "expected_parquet_file_count": int(file_contract["artifact_role"].eq("normalized_parquet").sum()),
                "expected_proof_file_count": int(file_contract["artifact_role"].eq("proof").sum()),
                "proof_required_field_count": int(proof_contract["required_for_real_w0"].sum()),
                "readiness_gate_pass_count": int(gates["pass_now"].sum()),
                "readiness_gate_count": int(len(gates)),
                "data_hard_gate_pass_count": int(gates.loc[gates["severity"].eq("data_hard"), "pass_now"].sum()),
                "data_hard_gate_count": int(gates["severity"].eq("data_hard").sum()),
                "contract_hash": contract_hash,
                "real_w0_files_present": 0,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(file_contract, FILE_CONTRACT_OUT)
    _write_csv(proof_contract, PROOF_CONTRACT_OUT)
    _write_csv(gates, READINESS_GATE_OUT)
    _write_sha256_template(file_contract)
    _write_data_package_descriptor(file_contract, proof_contract, gates)
    _write_handoff_readme(file_contract, proof_contract, gates)

    _plot_official_path(curve, requests)
    _plot_artifact_matrix()
    _plot_batch_burden(file_contract)
    _plot_schema_group_matrix(contract)
    _write_report(summary, gates, file_contract, proof_contract)

    output = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": DECISION,
        "summary_path": SUMMARY_OUT,
        "delivery_file_contract_path": FILE_CONTRACT_OUT,
        "proof_field_contract_path": PROOF_CONTRACT_OUT,
        "readiness_gate_status_path": READINESS_GATE_OUT,
        "datapackage_descriptor_path": DATA_PACKAGE_OUT,
        "sha256_template_path": SHA256_TEMPLATE_OUT,
        "handoff_readme_path": HANDOFF_README_OUT,
        "report_path": REPORT_OUT,
        "charts": [PATH_CHART_OUT, ARTIFACT_MATRIX_CHART_OUT, BATCH_BURDEN_CHART_OUT, SCHEMA_GROUP_CHART_OUT],
        "request_count": request_count,
        "batch_count": batch_count,
        "expected_delivery_file_count": expected_file_count,
        "real_w0_data_delivered": 0,
        "real_stage112_intake_allowed_now": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(output), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(output), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
