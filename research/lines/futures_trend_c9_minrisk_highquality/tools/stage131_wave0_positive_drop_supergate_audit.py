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
STAGE = "Stage131"
MODEL_TAG = "stage131_wave0_positive_drop_supergate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage131_wave0_positive_drop_supergate_audit"
POSITIVE_DROP_ROOT = OUTPUT_DIR / "positive_drop"

STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
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
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_case_summary_{MODEL_TAG}.csv"
STEP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_step_summary_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_gate_status_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_request_audit_{MODEL_TAG}.csv"
STAGE123_GATE_DETAIL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage123_gate_detail_{MODEL_TAG}.csv"
INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_drop_file_inventory_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_expectation_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_positive_supergate_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_request_supergate_matrix_{MODEL_TAG}.png"
GATE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_gate_matrix_{MODEL_TAG}.png"
INVENTORY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positive_inventory_burden_{MODEL_TAG}.png"

MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"
POSITIVE_CASE_ID = "contract_positive_fixture_drop"
DECISION = "stage131_positive_drop_supergate_passed_strategy_still_locked"


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


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
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


def _delivery_contract() -> pd.DataFrame:
    contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    if contract.empty:
        raise RuntimeError(f"missing Stage124 delivery contract: {STAGE124_FILE_CONTRACT_IN}")
    rows = []
    for request_id, group in contract.groupby("request_id"):
        roles = group.set_index("artifact_role")
        proof = roles.loc["proof"]
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
                "raw_relative_path": _clean(roles.loc["raw", "recommended_relative_path"]).replace("<vendor_raw_ext>", "raw"),
                "parquet_relative_path": _clean(roles.loc["normalized_parquet", "recommended_relative_path"]),
                "proof_relative_path": _clean(proof["recommended_relative_path"]),
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


def _required_fields(row: pd.Series, contract: pd.DataFrame) -> list[str]:
    required_column = "required_for_mbo" if _clean(row["required_schema_request"]) == MBO else "required_for_mbp10"
    return contract.loc[contract[required_column].eq(1), "canonical_field"].astype(str).tolist()


def _array_for_field(field: str, row: pd.Series, row_count: int) -> pa.Array:
    start = pd.Timestamp(row["request_start"])
    end = pd.Timestamp(row["request_end"])
    if row_count <= 1:
        event_times = [start.to_pydatetime()]
        recv_times = [(start + pd.Timedelta(milliseconds=10)).to_pydatetime()]
    else:
        event_times = [ts.to_pydatetime() for ts in pd.date_range(start, end, periods=row_count)]
        recv_times = [(pd.Timestamp(ts) + pd.Timedelta(milliseconds=10)).to_pydatetime() for ts in event_times]
    if field == "ts_event":
        return pa.array(event_times, type=pa.timestamp("ns"))
    if field == "ts_recv":
        return pa.array(recv_times, type=pa.timestamp("ns"))
    if field == "sequence":
        return pa.array(list(range(1, row_count + 1)), type=pa.int64())
    if field == "action":
        return pa.array(["add"] * row_count, type=pa.string())
    if field == "side":
        return pa.array(["bid" if idx % 2 == 0 else "ask" for idx in range(row_count)], type=pa.string())
    if field == "order_id":
        return pa.array([f"{_clean(row['request_id'])}_order_{idx + 1}" for idx in range(row_count)], type=pa.string())
    if field == "price" or "price" in field:
        return pa.array([100.0 + idx * 0.2 for idx in range(row_count)], type=pa.float64())
    if field == "size" or "size" in field:
        return pa.array([10 + idx for idx in range(row_count)], type=pa.int64())
    return pa.array([1 + idx for idx in range(row_count)], type=pa.int64())


def _write_parquet(path: Path, row: pd.Series, fields: list[str], row_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = [_array_for_field(field, row, row_count) for field in fields]
    pq.write_table(pa.table(arrays, names=fields), path)


def _write_raw(path: Path, row: pd.Series, row_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": STAGE,
        "fixture_type": "contract_positive_fixture",
        "request_id": _clean(row["request_id"]),
        "vt_symbol": _clean(row["vt_symbol"]),
        "request_start": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S"),
        "request_end": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": row_count,
    }
    path.write_bytes((json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))


def _proof_payload(row: pd.Series, raw_path: Path, parquet_path: Path, row_count: int) -> dict[str, Any]:
    return {
        "request_id": _clean(row["request_id"]),
        "batch_id": _clean(row["batch_id"]),
        "vt_symbol": _clean(row["vt_symbol"]),
        "required_schema_request": _clean(row["required_schema_request"]),
        "vendor": "authorized_research_feed_vendor",
        "license_id": "research_license_contract_001",
        "dataset": "authorized_depth_feed_w0_contract_positive_v1",
        "schema_hash": _sha256_text(_clean(row["required_schema_request"]))[:64],
        "field_dictionary_version": "stage120_canonical_contract_v1",
        "ts_event_timezone": "Asia/Shanghai",
        "ts_recv_timezone": "Asia/Shanghai",
        "first_ts_event": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S"),
        "last_ts_event": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": row_count,
        "sequence_gap_count": 0,
        "capture_continuity_proof": "stage131_local_contract_positive_gap_zero",
        "synthetic_fixture": False,
        "raw_sha256": _sha256_file(raw_path),
        "normalized_parquet_sha256": _sha256_file(parquet_path),
        "proof_created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template_only_not_real_proof": False,
    }


def _build_positive_drop() -> tuple[Path, pd.DataFrame]:
    drop_dir = POSITIVE_DROP_ROOT / POSITIVE_CASE_ID
    _reset_dir(drop_dir)
    requests = _delivery_contract()
    contract = _schema_contract()
    checksum_lines: list[str] = []
    inventory_rows: list[dict[str, Any]] = []
    for _, row in requests.iterrows():
        row_count = 2
        raw_path = drop_dir / _clean(row["raw_relative_path"])
        parquet_path = drop_dir / _clean(row["parquet_relative_path"])
        proof_path = drop_dir / _clean(row["proof_relative_path"])
        fields = _required_fields(row, contract)
        _write_raw(raw_path, row, row_count)
        _write_parquet(parquet_path, row, fields, row_count)
        _write_json(proof_path, _proof_payload(row, raw_path, parquet_path, row_count))
        checksum_lines.append(f"{_sha256_file(raw_path)}  {_clean(row['raw_relative_path'])}")
        for role, path in [("raw", raw_path), ("normalized_parquet", parquet_path), ("proof", proof_path)]:
            inventory_rows.append(
                {
                    "positive_case_id": POSITIVE_CASE_ID,
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
            "positive_case_id": POSITIVE_CASE_ID,
            "request_id": "",
            "artifact_role": "checksum_manifest",
            "path": str(checksum_path),
            "bytes": int(checksum_path.stat().st_size),
            "sha256": _sha256_file(checksum_path),
        }
    )
    return drop_dir, pd.DataFrame(inventory_rows)


def _run_stage128_positive(drop_dir: Path) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    command = [
        sys.executable,
        str(STAGE128_TOOL),
        "--drop-dir",
        str(drop_dir),
        "--expected-stage112-intake",
        "1",
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
            frame.insert(0, "positive_case_id", POSITIVE_CASE_ID)
    run_row = {
        "positive_case_id": POSITIVE_CASE_ID,
        "stage128_command": " ".join(command),
        "stage128_returncode": int(completed.returncode),
        "stage128_stdout_tail": completed.stdout[-500:],
        "stage128_stderr_tail": completed.stderr[-500:],
    }
    return run_row, frames


def _restore_stage128_default() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(STAGE128_TOOL)],
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


def _observed_gate(stage123_gate_detail: pd.DataFrame, gate_id: str) -> int:
    if stage123_gate_detail.empty:
        return 0
    rows = stage123_gate_detail[
        stage123_gate_detail["stage_step"].astype(str).eq("chain")
        & stage123_gate_detail["gate_id"].astype(str).eq(gate_id)
    ]
    if rows.empty:
        return 0
    return int(pd.to_numeric(rows.iloc[0]["observed"], errors="coerce"))


def _expectation_frame(case_summary: pd.DataFrame, stage123_gate_detail: pd.DataFrame) -> pd.DataFrame:
    row = case_summary.iloc[0] if not case_summary.empty else pd.Series(dtype=object)
    data = {
        "positive_case_id": POSITIVE_CASE_ID,
        "expected_stage127_bridge_ready_count": 41,
        "actual_stage127_bridge_ready_count": int(pd.to_numeric(row.get("stage127_bridge_ready_count", 0), errors="coerce")),
        "expected_stage125_ready_for_stage123": 1,
        "actual_stage125_ready_for_stage123": int(pd.to_numeric(row.get("stage125_ready_for_stage123", 0), errors="coerce")),
        "expected_stage117_stage112_intake": 1,
        "actual_stage117_stage112_intake": _observed_gate(stage123_gate_detail, "stage117_stage112_intake"),
        "expected_stage120_real_schema_contract_pass": 1,
        "actual_stage120_real_schema_contract_pass": _observed_gate(stage123_gate_detail, "stage120_real_schema_contract_pass"),
        "expected_stage123_final_stage112_ready_count": 1,
        "actual_stage123_final_stage112_ready_count": int(pd.to_numeric(row.get("stage123_final_stage112_ready_count", 0), errors="coerce")),
        "expected_full_supergate_ready": 1,
        "actual_full_supergate_ready": int(pd.to_numeric(row.get("final_supergate_ready", 0), errors="coerce")),
        "expected_strategy_allowed": 0,
        "actual_strategy_allowed": int(pd.to_numeric(row.get("strategy_use_allowed_now", 0), errors="coerce")),
    }
    result = pd.DataFrame([data])
    pairs = [
        ("expected_stage127_bridge_ready_count", "actual_stage127_bridge_ready_count"),
        ("expected_stage125_ready_for_stage123", "actual_stage125_ready_for_stage123"),
        ("expected_stage117_stage112_intake", "actual_stage117_stage112_intake"),
        ("expected_stage120_real_schema_contract_pass", "actual_stage120_real_schema_contract_pass"),
        ("expected_stage123_final_stage112_ready_count", "actual_stage123_final_stage112_ready_count"),
        ("expected_full_supergate_ready", "actual_full_supergate_ready"),
        ("expected_strategy_allowed", "actual_strategy_allowed"),
    ]
    for expected, actual in pairs:
        result[f"{expected}_matched"] = (
            pd.to_numeric(result[expected], errors="coerce").fillna(-999).astype(int)
            == pd.to_numeric(result[actual], errors="coerce").fillna(-998).astype(int)
        ).astype(int)
    match_cols = [column for column in result.columns if column.endswith("_matched")]
    result["expectation_all_matched"] = result[match_cols].min(axis=1).astype(int)
    return result


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, case_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage131 contract-positive W0 fixture over official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1F5D4A", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.26)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not request_audit.empty:
        points = _nearest_curve_points(curve, request_audit["trading_day"])
        ready = pd.to_numeric(request_audit["full_supergate_request_ready"], errors="coerce").fillna(0).reset_index(drop=True)
        colors = np.where(ready.eq(1), "#15803D", "#B91C1C")
        for axis, column in zip(
            axes[:3],
            ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"],
        ):
            y = points[column] / 1_000_000 if column == "account_equity" else points[column]
            axis.scatter(points["date"], y, color=colors, marker="o", s=38, alpha=0.65, label="W0 request ready")
        axes[0].legend(loc="upper left", fontsize=8)
    metrics = [
        "stage127_bridge_ready_count",
        "stage125_ready_for_stage123",
        "stage123_final_stage112_ready_count",
        "final_supergate_ready",
        "strategy_use_allowed_now",
    ]
    if not case_summary.empty:
        plot = case_summary.set_index("entry_case_id")[[column for column in metrics if column in case_summary.columns]]
        plot.plot(kind="bar", ax=axes[3], color=["#3B5BDB", "#0F766E", "#A16207", "#15803D", "#B91C1C"])
        axes[3].set_ylim(0, max(1.2, float(plot.to_numpy().max()) + 0.5))
    axes[3].set_ylabel("count / flag")
    axes[3].set_title("Positive fixture supergate reaches intake, strategy remains locked")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_matrix(request_audit: pd.DataFrame) -> None:
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
    data = request_audit[available].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, 10))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage131 positive request supergate matrix")
    ax.set_xticks(np.arange(len(available)))
    ax.set_xticklabels(available, rotation=35, ha="right")
    y_labels = [rid if idx % 4 == 0 else "" for idx, rid in enumerate(request_audit["request_id"])]
    ax.set_yticks(np.arange(len(request_audit)))
    ax.set_yticklabels(y_labels, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate_matrix(gates: pd.DataFrame, stage123_gate_detail: pd.DataFrame) -> None:
    stage128_gates = gates[["gate_id", "pass_now"]].copy() if not gates.empty else pd.DataFrame(columns=["gate_id", "pass_now"])
    stage128_gates["source"] = "stage128"
    chain = stage123_gate_detail[stage123_gate_detail["stage_step"].astype(str).eq("chain")][["gate_id", "pass_now"]].copy() if not stage123_gate_detail.empty else pd.DataFrame(columns=["gate_id", "pass_now"])
    chain["source"] = "stage123_chain"
    combined = pd.concat([stage128_gates, chain], ignore_index=True)
    combined["label"] = combined["source"] + "::" + combined["gate_id"].astype(str)
    fig, ax = plt.subplots(figsize=(10, max(5, len(combined) * 0.34)))
    values = pd.to_numeric(combined["pass_now"], errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    image = ax.imshow(values.reshape(-1, 1), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(combined)))
    ax.set_yticklabels(combined["label"], fontsize=8)
    for y, value in enumerate(values):
        ax.text(0, y, "P" if int(value) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage131 positive fixture gate matrix")
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(GATE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_inventory(inventory: pd.DataFrame) -> None:
    chart = inventory.groupby("artifact_role").agg(file_count=("path", "count"), total_bytes=("bytes", "sum")).reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(chart["artifact_role"], chart["file_count"], color="#0F766E")
    axes[0].set_title("Positive fixture file count")
    axes[0].set_ylabel("files")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(chart["artifact_role"], chart["total_bytes"] / 1024, color="#0369A1")
    axes[1].set_title("Positive fixture bytes")
    axes[1].set_ylabel("KiB")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(INVENTORY_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, expectation: pd.DataFrame, case_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = [
        f"# {STAGE} positive W0 drop supergate audit",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{row['decision']}`",
        "- scope: local contract-positive fixture, Stage128 supergate, default restore, and visual QA only; no strategy rule, true-engine run, A/B, CTP, order API, or external download.",
        "- fixture note: this proves the accept path can turn green, but it is not real vendor market data and remains locked from strategy use.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Expectation Audit",
        "",
        _md_table(expectation),
        "",
        "## Case Summary",
        "",
        _md_table(case_summary),
        "",
        "## Supergate Status",
        "",
        _md_table(gates),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{REQUEST_MATRIX_CHART_OUT.name}`",
        f"- `{GATE_MATRIX_CHART_OUT.name}`",
        f"- `{INVENTORY_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    drop_dir, inventory = _build_positive_drop()
    run_row: dict[str, Any] = {}
    frames: dict[str, pd.DataFrame] = {}
    try:
        run_row, frames = _run_stage128_positive(drop_dir)
    finally:
        restore_info = _restore_stage128_default()

    stage128_summary = frames.get("summary", pd.DataFrame())
    case_summary = frames.get("case_summary", pd.DataFrame())
    step_summary = frames.get("step_summary", pd.DataFrame())
    gates = frames.get("gates", pd.DataFrame())
    request_audit = frames.get("request_audit", pd.DataFrame())
    stage123_gates = frames.get("stage123_gate_detail", pd.DataFrame())
    expectation = _expectation_frame(case_summary, stage123_gates)

    stage128_returncode_zero = int(run_row.get("stage128_returncode", -1) == 0)
    all_commands_returncode_zero = int(step_summary["returncode"].eq(0).all()) if not step_summary.empty and "returncode" in step_summary.columns else 0
    expectation_matched_count = int(expectation["expectation_all_matched"].sum()) if not expectation.empty else 0
    positive_ready_count = int(pd.to_numeric(case_summary.get("final_supergate_ready", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    strategy_allowed_count = int(pd.to_numeric(case_summary.get("strategy_use_allowed_now", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    request_ready_count = int(pd.to_numeric(request_audit.get("full_supergate_request_ready", 0), errors="coerce").fillna(0).sum()) if not request_audit.empty else 0
    decision = DECISION
    if (
        stage128_returncode_zero != 1
        or all_commands_returncode_zero != 1
        or expectation_matched_count != len(expectation)
        or positive_ready_count != 1
        or strategy_allowed_count != 0
        or int(restore_info.get("stage128_default_restored", 0)) != 1
    ):
        decision = "stage131_positive_drop_supergate_audit_failed"

    stage128_row = stage128_summary.iloc[0] if not stage128_summary.empty else pd.Series(dtype=object)
    for metric in [
        "end_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "closed_lot_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
    ]:
        value = pd.to_numeric(pd.Series([stage128_row.get(metric, np.nan)]), errors="coerce").iloc[0]
        if pd.notna(value):
            metrics[metric] = float(value)
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
                "positive_case_id": POSITIVE_CASE_ID,
                "positive_drop_dir": str(drop_dir),
                "contract_positive_fixture": 1,
                "generated_positive_file_count": int(len(inventory)),
                "stage128_returncode_zero": stage128_returncode_zero,
                "stage128_all_inner_commands_returncode_zero": all_commands_returncode_zero,
                "stage128_positive_decision": _clean(stage128_row.get("decision", "")),
                "stage128_default_restored": int(restore_info.get("stage128_default_restored", 0)),
                "stage128_default_restore_returncode": int(restore_info.get("stage128_default_restore_returncode", -1)),
                "expectation_matched_count": expectation_matched_count,
                "expectation_case_count": len(expectation),
                "positive_full_supergate_ready_count": positive_ready_count,
                "positive_request_ready_count": request_ready_count,
                "positive_request_count": len(request_audit),
                "strategy_allowed_count": strategy_allowed_count,
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
    if run_row:
        _write_csv(pd.DataFrame([run_row]), OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_command_run_summary_{MODEL_TAG}.csv")
    if not stage128_summary.empty:
        _write_csv(stage128_summary, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_positive_summary_{MODEL_TAG}.csv")

    _plot_official_path(curve, request_audit, case_summary)
    _plot_request_matrix(request_audit)
    _plot_gate_matrix(gates, stage123_gates)
    _plot_inventory(inventory)
    _write_report(summary, expectation, case_summary, gates)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "positive_drop_dir": str(drop_dir),
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
                    str(REQUEST_MATRIX_CHART_OUT),
                    str(GATE_MATRIX_CHART_OUT),
                    str(INVENTORY_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "real_w0_data_delivered": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
