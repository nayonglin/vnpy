from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage125"
MODEL_TAG = "stage125_wave0_receipt_preflight_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage125_wave0_receipt_preflight_audit"
EMPTY_DROP_DIR = OUTPUT_DIR / "empty_drop"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_SUMMARY_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_summary_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
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

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FILE_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_inventory_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_receipt_status_{MODEL_TAG}.csv"
PROOF_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_json_audit_{MODEL_TAG}.csv"
CHECKSUM_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checksum_manifest_audit_{MODEL_TAG}.csv"
UNKNOWN_FILE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unknown_file_inventory_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_receipt_preflight_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_receipt_status_{MODEL_TAG}.png"
ROLE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_role_completeness_matrix_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_role_matrix_{MODEL_TAG}.png"
ISSUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_issue_bar_chart_{MODEL_TAG}.png"

DECISION = "stage125_wave0_receipt_preflight_empty_drop_blocked_no_real_data_no_strategy"
CLI_DECISION = "stage125_wave0_receipt_preflight_cli_completed_no_strategy"
REQUEST_RE = re.compile(r"stage114_req_\d{4}")
RAW_SUFFIXES = {".raw", ".dbn", ".dat", ".bin", ".gz", ".zip"}
ROLE_ORDER = ["raw", "normalized_parquet", "proof"]
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


def _role_for_file(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = "".join(path.suffixes).lower()
    if path.suffix.lower() == ".parquet" or "parquet" in parts or "normalized" in name:
        return "normalized_parquet"
    if path.suffix.lower() == ".json" and ("proof" in parts or "proof" in name):
        return "proof"
    if "raw" in parts or "raw" in name or path.suffix.lower() in RAW_SUFFIXES or suffix.endswith(".csv.gz"):
        return "raw"
    return "ignored"


def _request_id_for_path(path: Path) -> str:
    match = REQUEST_RE.search(str(path))
    return match.group(0) if match else ""


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


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage124 = _read_csv(STAGE124_SUMMARY_IN)
    if not stage124.empty:
        row = stage124.iloc[0]
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


def _scan_drop(drop_dir: Path) -> pd.DataFrame:
    files = sorted(path for path in drop_dir.rglob("*") if path.is_file()) if drop_dir.exists() else []
    rows = []
    for path in files:
        role = _role_for_file(path)
        request_id = _request_id_for_path(path)
        sha256 = _sha256_file(path) if role == "raw" else ""
        rows.append(
            {
                "drop_dir": str(drop_dir),
                "path": str(path),
                "relative_path": str(path.relative_to(drop_dir)) if path.is_relative_to(drop_dir) else str(path),
                "request_id": request_id,
                "artifact_role": role,
                "suffix": "".join(path.suffixes).lower(),
                "bytes": int(path.stat().st_size),
                "sha256": sha256,
            }
        )
    return pd.DataFrame(rows)


def _load_checksum_manifest(drop_dir: Path) -> pd.DataFrame:
    candidates = []
    if drop_dir.exists():
        for path in sorted(drop_dir.rglob("*")):
            if not path.is_file():
                continue
            name = path.name.lower()
            if name.startswith("sha256") or name.endswith(".sha256") or "sha256sums" in name:
                candidates.append(path)
    rows = []
    for path in candidates:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line_no, line in enumerate(lines, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = text.split()
            digest = parts[0] if parts else ""
            rel_path = " ".join(parts[1:]).strip("* ") if len(parts) > 1 else ""
            request_id = _request_id_for_path(Path(rel_path))
            is_placeholder = int(digest.upper().startswith("SHA256_PLACEHOLDER") or digest == "")
            is_sha256 = int(bool(re.fullmatch(r"[A-Fa-f0-9]{64}", digest)))
            rows.append(
                {
                    "checksum_manifest_path": str(path),
                    "line_no": line_no,
                    "digest": digest,
                    "relative_path": rel_path,
                    "request_id": request_id,
                    "is_placeholder": is_placeholder,
                    "is_sha256": is_sha256,
                }
            )
    return pd.DataFrame(rows)


def _audit_proof_file(path_text: str, required_fields: list[str]) -> dict[str, Any]:
    if not path_text:
        return {
            "proof_json_readable": 0,
            "proof_required_fields_present": 0,
            "proof_missing_fields": ";".join(required_fields),
            "proof_synthetic_block": 1,
            "proof_error": "proof_missing",
        }
    path = Path(path_text)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "proof_json_readable": 0,
            "proof_required_fields_present": 0,
            "proof_missing_fields": ";".join(required_fields),
            "proof_synthetic_block": 1,
            "proof_error": type(exc).__name__,
        }
    missing = [field for field in required_fields if _clean(data.get(field)) == ""]
    sequence_gap_zero = int(_clean(data.get("sequence_gap_count")) in {"0", "0.0"})
    row_count_positive = int(pd.to_numeric(pd.Series([data.get("row_count")]), errors="coerce").fillna(0).iloc[0] > 0)
    synthetic_text = " ".join(
        [
            _clean(data.get("vendor")),
            _clean(data.get("dataset")),
            _clean(data.get("notes")),
            str(data.get("synthetic_fixture", "")),
        ]
    ).lower()
    synthetic_block = int("synthetic" not in synthetic_text and "smoke" not in synthetic_text and str(data.get("synthetic_fixture", "")).lower() not in {"true", "1"})
    all_present = int(len(missing) == 0 and sequence_gap_zero and row_count_positive and synthetic_block)
    return {
        "proof_json_readable": 1,
        "proof_required_fields_present": all_present,
        "proof_missing_fields": ";".join(missing),
        "proof_synthetic_block": synthetic_block,
        "proof_error": "" if all_present else "proof_field_rule_failed",
    }


def _build_request_status(
    file_contract: pd.DataFrame,
    proof_contract: pd.DataFrame,
    inventory: pd.DataFrame,
    checksum_manifest: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_proof_fields = (
        proof_contract.loc[proof_contract["required_for_real_w0"].eq(1), "proof_json_field"].astype(str).tolist()
    )
    request_rows = []
    proof_rows = []
    request_meta = (
        file_contract.drop_duplicates("request_id")
        [
            [
                "request_id",
                "batch_id",
                "exchange",
                "product",
                "vt_symbol",
                "trading_day",
                "request_start",
                "request_end",
                "required_schema_request",
            ]
        ]
        .copy()
    )
    for _, row in request_meta.iterrows():
        request_id = row["request_id"]
        inv = inventory[inventory["request_id"].eq(request_id)] if not inventory.empty else pd.DataFrame()
        counts = {
            role: int(inv["artifact_role"].eq(role).sum()) if not inv.empty else 0
            for role in ROLE_ORDER
        }
        raw_path = _clean(inv.loc[inv["artifact_role"].eq("raw"), "path"].iloc[0]) if counts["raw"] > 0 else ""
        proof_path = _clean(inv.loc[inv["artifact_role"].eq("proof"), "path"].iloc[0]) if counts["proof"] > 0 else ""
        raw_sha = _clean(inv.loc[inv["artifact_role"].eq("raw"), "sha256"].iloc[0]) if counts["raw"] > 0 else ""
        checksum_rows = checksum_manifest[checksum_manifest["request_id"].eq(request_id)] if not checksum_manifest.empty else pd.DataFrame()
        checksum_manifest_present = int(not checksum_rows.empty)
        checksum_placeholder = int(checksum_rows["is_placeholder"].sum()) if not checksum_rows.empty else 0
        checksum_sha256_valid = int(checksum_rows["is_sha256"].sum()) if not checksum_rows.empty else 0
        checksum_match = 0
        if raw_sha and not checksum_rows.empty:
            checksum_match = int(checksum_rows["digest"].astype(str).str.lower().eq(raw_sha.lower()).any())
        proof_audit = _audit_proof_file(proof_path, required_proof_fields)
        missing_roles = [role for role in ROLE_ORDER if counts[role] == 0]
        duplicate_roles = [role for role in ROLE_ORDER if counts[role] > 1]
        role_complete = int(all(counts[role] == 1 for role in ROLE_ORDER))
        checksum_ready = int(counts["raw"] == 1 and checksum_manifest_present and checksum_placeholder == 0 and checksum_sha256_valid > 0 and checksum_match == 1)
        proof_ready = int(counts["proof"] == 1 and proof_audit["proof_required_fields_present"] == 1)
        request_ready = int(role_complete and checksum_ready and proof_ready)
        request_rows.append(
            {
                **row.to_dict(),
                "raw_count": counts["raw"],
                "normalized_parquet_count": counts["normalized_parquet"],
                "proof_count": counts["proof"],
                "role_complete": role_complete,
                "missing_roles": ";".join(missing_roles),
                "duplicate_roles": ";".join(duplicate_roles),
                "raw_sha256": raw_sha,
                "checksum_manifest_present": checksum_manifest_present,
                "checksum_placeholder_count": checksum_placeholder,
                "checksum_sha256_valid_count": checksum_sha256_valid,
                "checksum_match": checksum_match,
                "proof_json_readable": proof_audit["proof_json_readable"],
                "proof_required_fields_present": proof_audit["proof_required_fields_present"],
                "proof_missing_fields": proof_audit["proof_missing_fields"],
                "proof_synthetic_block": proof_audit["proof_synthetic_block"],
                "preflight_request_ready": request_ready,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
            }
        )
        proof_rows.append(
            {
                "request_id": request_id,
                "proof_file": proof_path,
                **proof_audit,
                "required_field_count": len(required_proof_fields),
            }
        )
    return pd.DataFrame(request_rows), pd.DataFrame(proof_rows)


def _build_gates(
    file_contract: pd.DataFrame,
    proof_contract: pd.DataFrame,
    inventory: pd.DataFrame,
    request_status: pd.DataFrame,
    checksum_manifest: pd.DataFrame,
    unknown_files: pd.DataFrame,
    cli_mode: bool,
) -> pd.DataFrame:
    expected_files = len(file_contract)
    expected_requests = request_status["request_id"].nunique()
    observed_known = int(inventory["artifact_role"].isin(ROLE_ORDER).sum()) if not inventory.empty else 0
    complete_requests = int(request_status["preflight_request_ready"].sum()) if not request_status.empty else 0
    role_complete = int(request_status["role_complete"].sum()) if not request_status.empty else 0
    checksum_ready = int(request_status["checksum_match"].sum()) if not request_status.empty else 0
    proof_ready = int(request_status["proof_required_fields_present"].sum()) if not request_status.empty else 0
    duplicate_request_roles = int(request_status["duplicate_roles"].astype(str).str.len().gt(0).sum()) if not request_status.empty else 0
    unknown_count = int(len(unknown_files))
    gates = [
        {
            "gate_id": "stage124_file_contract_available",
            "observed": f"{expected_files}",
            "required": "123",
            "pass_now": int(expected_files == 123),
            "severity": "planning_hard",
        },
        {
            "gate_id": "stage124_proof_contract_available",
            "observed": f"{int(proof_contract['required_for_real_w0'].sum())} required fields",
            "required": ">=12",
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
            "gate_id": "receipt_known_file_count",
            "observed": f"{observed_known}/{expected_files}",
            "required": f"{expected_files}/{expected_files}",
            "pass_now": int(observed_known == expected_files and expected_files > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "receipt_request_roles_complete",
            "observed": f"{role_complete}/{expected_requests}",
            "required": f"{expected_requests}/{expected_requests}",
            "pass_now": int(role_complete == expected_requests and expected_requests > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "receipt_no_duplicate_roles",
            "observed": str(duplicate_request_roles),
            "required": "0",
            "pass_now": int(duplicate_request_roles == 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "receipt_unknown_files_zero",
            "observed": str(unknown_count),
            "required": "0",
            "pass_now": int(unknown_count == 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "receipt_checksum_manifest_ready",
            "observed": f"{checksum_ready}/{expected_requests}; checksum_lines={len(checksum_manifest)}",
            "required": f"{expected_requests}/{expected_requests}",
            "pass_now": int(checksum_ready == expected_requests and expected_requests > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "receipt_proof_json_ready",
            "observed": f"{proof_ready}/{expected_requests}",
            "required": f"{expected_requests}/{expected_requests}",
            "pass_now": int(proof_ready == expected_requests and expected_requests > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "preflight_ready_for_stage123",
            "observed": f"{complete_requests}/{expected_requests}",
            "required": f"{expected_requests}/{expected_requests}",
            "pass_now": int(complete_requests == expected_requests and cli_mode and expected_requests > 0),
            "severity": "final_hard",
        },
    ]
    return pd.DataFrame(gates)


def _plot_official_path(curve: pd.DataFrame, request_status: pd.DataFrame) -> None:
    chart = request_status.copy()
    chart["trading_day"] = pd.to_datetime(chart["trading_day"], errors="coerce")
    points = _nearest_curve_points(curve, chart["trading_day"])
    points = points.join(chart[["preflight_request_ready"]].reset_index(drop=True))
    colors = points["preflight_request_ready"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#B91C1C")
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=colors, s=42, alpha=0.7)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[1].scatter(points["date"], points["drawdown_pct"], color=colors, s=42, alpha=0.7)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=colors, s=42, alpha=0.7)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle("Stage125 W0 receipt preflight on official path; red means not ready for Stage123")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_role_matrix(file_contract: pd.DataFrame, request_status: pd.DataFrame) -> None:
    expected = file_contract.groupby("artifact_role").size().reindex(ROLE_ORDER).fillna(0)
    observed = pd.Series(
        {
            "raw": int(request_status["raw_count"].clip(upper=1).sum()),
            "normalized_parquet": int(request_status["normalized_parquet_count"].clip(upper=1).sum()),
            "proof": int(request_status["proof_count"].clip(upper=1).sum()),
        }
    ).reindex(ROLE_ORDER)
    matrix = pd.DataFrame({"expected": expected, "observed_unique": observed})
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    image = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns)
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(len(matrix.index)):
        for x in range(len(matrix.columns)):
            ax.text(x, y, str(int(matrix.iloc[y, x])), ha="center", va="center", color="#111827")
    ax.set_title("Stage125 receipt role completeness")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(ROLE_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_request_matrix(request_status: pd.DataFrame) -> None:
    matrix = request_status.set_index("request_id")[["raw_count", "normalized_parquet_count", "proof_count"]].copy()
    matrix = matrix.clip(upper=1)
    fig, ax = plt.subplots(figsize=(8, 12))
    image = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(["raw", "parquet", "proof"], rotation=20, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=6)
    ax.set_title("Stage125 request role matrix")
    fig.colorbar(image, ax=ax, shrink=0.7)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_issue_chart(gates: pd.DataFrame) -> None:
    data_gates = gates[gates["severity"].isin(["data_hard", "final_hard"])].copy()
    data_gates["fail"] = 1 - data_gates["pass_now"].astype(int)
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = data_gates["pass_now"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#B91C1C")
    ax.bar(data_gates["gate_id"], data_gates["fail"], color=colors)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("fail=1")
    ax.set_title("Stage125 receipt preflight blockers")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ISSUE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, gates: pd.DataFrame, request_status: pd.DataFrame, unknown_files: pd.DataFrame) -> None:
    row = summary.iloc[0]
    role_summary = request_status[
        ["raw_count", "normalized_parquet_count", "proof_count", "role_complete", "checksum_match", "proof_required_fields_present", "preflight_request_ready"]
    ].sum().reset_index()
    role_summary.columns = ["metric", "count"]
    blockers = gates[gates["pass_now"].eq(0)].copy()
    report = f"""# Stage125 W0 receipt preflight audit

## Decision

- decision: `{row['decision']}`
- nature: receipt preflight only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- scanned drop: `{row['drop_dir']}`
- next full validation: `{STAGE123_REAL_COMMAND}`

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## Receipt Summary

{_md_table(summary)}

## Request Status Summary

{_md_table(role_summary)}

## Blockers

{_md_table(blockers)}

## Unknown Files

{_md_table(unknown_files, max_rows=20)}

## Visual Outputs

- official path receipt status: `{PATH_CHART_OUT}`
- role completeness matrix: `{ROLE_MATRIX_CHART_OUT}`
- request role matrix: `{REQUEST_MATRIX_CHART_OUT}`
- issue chart: `{ISSUE_CHART_OUT}`

## Judgment

This is a preflight receipt screen before Stage123. It catches missing roles, duplicate role files, unknown files, checksum placeholders, and proof JSON defects. Passing this preflight still does not authorize strategy research; Stage123, Stage112, and Stage113 must pass next.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight audit a W0 delivery drop against the Stage124 file contract.")
    parser.add_argument("--drop-dir", type=Path, default=None, help="Real W0 drop directory. Omit to run the empty-drop negative preflight.")
    parser.add_argument("--case-id", default="empty_drop_preflight", help="Case id for output summary.")
    return parser.parse_args()


def main(drop_dir: Path | None = None, case_id: str = "empty_drop_preflight") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if drop_dir is None:
        drop_dir = EMPTY_DROP_DIR
        case_id = "empty_drop_preflight"
    drop_dir = drop_dir.expanduser().resolve()
    drop_dir.mkdir(parents=True, exist_ok=True)
    cli_mode = case_id != "empty_drop_preflight"

    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    proof_contract = _read_csv(STAGE124_PROOF_CONTRACT_IN)
    if file_contract.empty or proof_contract.empty:
        raise RuntimeError("missing Stage124 delivery contracts; run Stage124 first")
    for frame in [file_contract]:
        for column in ["trading_day", "request_start", "request_end"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    inventory = _scan_drop(drop_dir)
    known_inventory = inventory[inventory["artifact_role"].isin(ROLE_ORDER)].copy() if not inventory.empty else pd.DataFrame()
    unknown_files = inventory[(inventory["artifact_role"].eq("ignored")) | (inventory["request_id"].eq(""))].copy() if not inventory.empty else pd.DataFrame()
    checksum_manifest = _load_checksum_manifest(drop_dir)
    request_status, proof_audit = _build_request_status(file_contract, proof_contract, known_inventory, checksum_manifest)
    gates = _build_gates(file_contract, proof_contract, known_inventory, request_status, checksum_manifest, unknown_files, cli_mode)

    expected_files = int(len(file_contract))
    observed_known = int(len(known_inventory))
    complete_requests = int(request_status["preflight_request_ready"].sum())
    request_count = int(request_status["request_id"].nunique())
    ready_for_stage123 = int(gates.loc[gates["gate_id"].eq("preflight_ready_for_stage123"), "pass_now"].iloc[0])
    decision = CLI_DECISION if cli_mode else DECISION
    if ready_for_stage123:
        decision = "stage125_wave0_receipt_preflight_ready_for_stage123_no_strategy"
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "case_id": case_id,
                "decision": decision,
                "drop_dir": str(drop_dir),
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "expected_file_count": expected_files,
                "observed_known_file_count": observed_known,
                "unknown_file_count": int(len(unknown_files)),
                "request_count": request_count,
                "role_complete_request_count": int(request_status["role_complete"].sum()),
                "checksum_match_request_count": int(request_status["checksum_match"].sum()),
                "proof_ready_request_count": int(request_status["proof_required_fields_present"].sum()),
                "preflight_ready_request_count": complete_requests,
                "checksum_manifest_line_count": int(len(checksum_manifest)),
                "checksum_placeholder_line_count": int(checksum_manifest["is_placeholder"].sum()) if not checksum_manifest.empty else 0,
                "gate_pass_count": int(gates["pass_now"].sum()),
                "gate_count": int(len(gates)),
                "data_hard_gate_pass_count": int(gates.loc[gates["severity"].eq("data_hard"), "pass_now"].sum()),
                "data_hard_gate_count": int(gates["severity"].eq("data_hard").sum()),
                "ready_for_stage123": ready_for_stage123,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(inventory, FILE_INVENTORY_OUT)
    _write_csv(request_status, REQUEST_STATUS_OUT)
    _write_csv(proof_audit, PROOF_AUDIT_OUT)
    _write_csv(checksum_manifest, CHECKSUM_AUDIT_OUT)
    _write_csv(unknown_files, UNKNOWN_FILE_OUT)
    _write_csv(gates, GATE_STATUS_OUT)

    _plot_official_path(curve, request_status)
    _plot_role_matrix(file_contract, request_status)
    _plot_request_matrix(request_status)
    _plot_issue_chart(gates)
    _write_report(summary, gates, request_status, unknown_files)

    output = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "summary_path": SUMMARY_OUT,
        "file_inventory_path": FILE_INVENTORY_OUT,
        "request_status_path": REQUEST_STATUS_OUT,
        "proof_audit_path": PROOF_AUDIT_OUT,
        "checksum_audit_path": CHECKSUM_AUDIT_OUT,
        "unknown_file_inventory_path": UNKNOWN_FILE_OUT,
        "gate_status_path": GATE_STATUS_OUT,
        "report_path": REPORT_OUT,
        "charts": [PATH_CHART_OUT, ROLE_MATRIX_CHART_OUT, REQUEST_MATRIX_CHART_OUT, ISSUE_CHART_OUT],
        "drop_dir": drop_dir,
        "expected_file_count": expected_files,
        "observed_known_file_count": observed_known,
        "preflight_ready_request_count": complete_requests,
        "ready_for_stage123": ready_for_stage123,
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
    args = _parse_args()
    main(drop_dir=args.drop_dir, case_id=args.case_id)
