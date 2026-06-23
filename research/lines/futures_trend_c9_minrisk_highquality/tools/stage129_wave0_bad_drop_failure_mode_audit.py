from __future__ import annotations

from datetime import datetime
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
from jsonschema import Draft202012Validator


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage129"
MODEL_TAG = "stage129_wave0_bad_drop_failure_mode_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage129_wave0_bad_drop_failure_mode_audit"
BAD_DROP_ROOT = OUTPUT_DIR / "bad_drops"

STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
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
STAGE128_TOOL = LINE_DIR / "tools" / "stage128_wave0_full_intake_supergate.py"
STAGE128_OUT_DIR = LINE_DIR / "outputs" / "stage128_wave0_full_intake_supergate"
STAGE128_PREFIX = "qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate"
STAGE128_MODEL = "stage128_wave0_full_intake_supergate_v1"
STAGE128_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_summary_{STAGE128_MODEL}.csv"
STAGE128_CASE_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_case_summary_{STAGE128_MODEL}.csv"
STAGE128_STEP_SUMMARY = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_step_summary_{STAGE128_MODEL}.csv"
STAGE128_GATE_STATUS = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_supergate_status_{STAGE128_MODEL}.csv"
STAGE128_REQUEST_AUDIT = STAGE128_OUT_DIR / f"{STAGE128_PREFIX}_request_supergate_audit_{STAGE128_MODEL}.csv"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_case_summary_{MODEL_TAG}.csv"
STEP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_step_summary_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_gate_status_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_request_audit_{MODEL_TAG}.csv"
INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_drop_file_inventory_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_expectation_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_bad_drop_failure_status_{MODEL_TAG}.png"
CASE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_drop_supergate_matrix_{MODEL_TAG}.png"
EXPECTATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expected_vs_observed_failure_modes_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_failure_mode_matrix_{MODEL_TAG}.png"

DECISION = "stage129_bad_drop_failure_modes_blocked_no_strategy"


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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage128 = _read_csv(STAGE128_SUMMARY)
    if not stage128.empty:
        row = stage128.iloc[0]
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


def _request_meta() -> pd.DataFrame:
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
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
    template_index = _read_csv(STAGE126_TEMPLATE_INDEX_IN)
    if template_index.empty:
        raise RuntimeError(f"missing Stage126 template index: {STAGE126_TEMPLATE_INDEX_IN}")
    template_index = template_index[["request_id", "template_path"]].copy()
    proof_rows = proof_rows.merge(template_index, on="request_id", how="left")
    return proof_rows.sort_values(["trading_day", "request_id"]).reset_index(drop=True)


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


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _target_path(drop_dir: Path, row: pd.Series) -> Path:
    return drop_dir / _clean(row["recommended_relative_path"])


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_template(path: Path, template_path: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(template_path), path)


def _build_bad_drops(requests: pd.DataFrame) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    _reset_dir(BAD_DROP_ROOT)
    case_specs = [
        {
            "failure_case_id": "template_proof_only_drop",
            "failure_mode": "template JSON copied into delivery proof paths",
            "expected_stage127_bridge_ready_count": 0,
            "expected_schema_valid_count": 0,
            "expected_identity_match_count": 41,
            "expected_span_cover_count": 41,
            "expected_stage125_proof_ready_count": 0,
        },
        {
            "failure_case_id": "valid_schema_proof_only_drop",
            "failure_mode": "schema-valid proof files only; raw/parquet/checksum absent",
            "expected_stage127_bridge_ready_count": 41,
            "expected_schema_valid_count": 41,
            "expected_identity_match_count": 41,
            "expected_span_cover_count": 41,
            "expected_stage125_proof_ready_count": 41,
        },
        {
            "failure_case_id": "valid_schema_wrong_request_drop",
            "failure_mode": "schema-valid proof files with request_id mismatched to path contract",
            "expected_stage127_bridge_ready_count": 0,
            "expected_schema_valid_count": 41,
            "expected_identity_match_count": 0,
            "expected_span_cover_count": 41,
            "expected_stage125_proof_ready_count": 41,
        },
        {
            "failure_case_id": "valid_schema_undercovered_span_drop",
            "failure_mode": "schema-valid proof files that under-cover request end by one minute",
            "expected_stage127_bridge_ready_count": 0,
            "expected_schema_valid_count": 41,
            "expected_identity_match_count": 41,
            "expected_span_cover_count": 0,
            "expected_stage125_proof_ready_count": 41,
        },
        {
            "failure_case_id": "synthetic_flag_schema_drop",
            "failure_mode": "synthetic/smoke metadata embedded in otherwise populated proof files",
            "expected_stage127_bridge_ready_count": 0,
            "expected_schema_valid_count": 0,
            "expected_identity_match_count": 41,
            "expected_span_cover_count": 41,
            "expected_stage125_proof_ready_count": 0,
        },
    ]
    schema = json.loads(STAGE126_SCHEMA_IN.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    request_count = len(requests)
    if request_count != 41:
        raise RuntimeError(f"expected 41 W0 proof requests, got {request_count}")
    rows: list[dict[str, Any]] = []
    request_ids = requests["request_id"].astype(str).tolist()
    for spec in case_specs:
        drop_dir = BAD_DROP_ROOT / spec["failure_case_id"]
        _reset_dir(drop_dir)
        for idx, row in requests.iterrows():
            target = _target_path(drop_dir, row)
            if spec["failure_case_id"] == "template_proof_only_drop":
                _copy_template(target, _clean(row["template_path"]))
                payload = json.loads(target.read_text(encoding="utf-8"))
            else:
                payload = _valid_payload_for(row)
                if spec["failure_case_id"] == "valid_schema_wrong_request_drop":
                    payload["request_id"] = request_ids[(idx + 1) % request_count]
                elif spec["failure_case_id"] == "valid_schema_undercovered_span_drop":
                    payload["last_ts_event"] = (
                        pd.Timestamp(row["request_end"]) - pd.Timedelta(minutes=1)
                    ).strftime("%Y-%m-%d %H:%M:%S")
                elif spec["failure_case_id"] == "synthetic_flag_schema_drop":
                    payload["vendor"] = "synthetic_vendor"
                    payload["dataset"] = "synthetic_smoke_fixture"
                    payload["synthetic_fixture"] = True
                _write_payload(target, payload)
            schema_errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
            rows.append(
                {
                    "failure_case_id": spec["failure_case_id"],
                    "failure_mode": spec["failure_mode"],
                    "drop_dir": str(drop_dir),
                    "request_id": _clean(row["request_id"]),
                    "proof_file": str(target),
                    "proof_bytes": int(target.stat().st_size),
                    "payload_request_id": _clean(payload.get("request_id")),
                    "payload_batch_id": _clean(payload.get("batch_id")),
                    "payload_vt_symbol": _clean(payload.get("vt_symbol")),
                    "payload_first_ts_event": _clean(payload.get("first_ts_event")),
                    "payload_last_ts_event": _clean(payload.get("last_ts_event")),
                    "payload_row_count": payload.get("row_count"),
                    "payload_synthetic_fixture": payload.get("synthetic_fixture"),
                    "payload_template_only_not_real_proof": payload.get("template_only_not_real_proof", False),
                    "generated_schema_valid": int(len(schema_errors) == 0),
                    "first_generated_schema_error": schema_errors[0].message if schema_errors else "",
                }
            )
        spec["drop_dir"] = str(drop_dir)
        spec["expected_full_supergate_ready"] = 0
        spec["expected_strategy_use_allowed_now"] = 0
    return case_specs, pd.DataFrame(rows)


def _run_stage128(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    command = [
        sys.executable,
        str(STAGE128_TOOL),
        "--drop-dir",
        str(case["drop_dir"]),
        "--expected-stage112-intake",
        "0",
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
    }
    for frame in frames.values():
        if not frame.empty:
            frame.insert(0, "failure_case_id", case["failure_case_id"])
            frame.insert(1, "failure_mode", case["failure_mode"])
    run_row = {
        "failure_case_id": case["failure_case_id"],
        "failure_mode": case["failure_mode"],
        "stage128_command": " ".join(command),
        "stage128_returncode": int(completed.returncode),
        "stage128_stdout_tail": completed.stdout[-500:],
        "stage128_stderr_tail": completed.stderr[-500:],
    }
    return run_row, frames


def _restore_stage128_default() -> dict[str, Any]:
    command = [sys.executable, str(STAGE128_TOOL)]
    completed = subprocess.run(
        command,
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


def _case_expectation_frame(cases: list[dict[str, Any]], case_summary: pd.DataFrame, request_audit: pd.DataFrame) -> pd.DataFrame:
    expectations = pd.DataFrame(cases)
    actual_rows: list[dict[str, Any]] = []
    for case_id, group in request_audit.groupby("failure_case_id") if not request_audit.empty else []:
        actual_rows.append(
            {
                "failure_case_id": case_id,
                "actual_schema_valid_count": int(pd.to_numeric(group.get("schema_valid", 0), errors="coerce").fillna(0).sum()),
                "actual_identity_match_count": int(pd.to_numeric(group.get("request_identity_match", 0), errors="coerce").fillna(0).sum()),
                "actual_span_cover_count": int(pd.to_numeric(group.get("request_span_cover", 0), errors="coerce").fillna(0).sum()),
                "actual_stage127_bridge_ready_count": int(pd.to_numeric(group.get("proof_schema_bridge_ready", 0), errors="coerce").fillna(0).sum()),
                "actual_stage125_proof_ready_count": int(pd.to_numeric(group.get("proof_required_fields_present", 0), errors="coerce").fillna(0).sum()),
                "actual_full_supergate_request_ready_count": int(pd.to_numeric(group.get("full_supergate_request_ready", 0), errors="coerce").fillna(0).sum()),
            }
        )
    actual = pd.DataFrame(actual_rows)
    result = expectations.merge(actual, on="failure_case_id", how="left")
    if not case_summary.empty:
        keep = [
            "failure_case_id",
            "stage127_bridge_ready_count",
            "stage125_ready_for_stage123",
            "stage123_final_stage112_ready_count",
            "stage123_final_strategy_allowed_count",
            "final_supergate_ready",
            "strategy_use_allowed_now",
        ]
        result = result.merge(case_summary[[column for column in keep if column in case_summary.columns]], on="failure_case_id", how="left")
    compare_pairs = [
        ("expected_schema_valid_count", "actual_schema_valid_count"),
        ("expected_identity_match_count", "actual_identity_match_count"),
        ("expected_span_cover_count", "actual_span_cover_count"),
        ("expected_stage127_bridge_ready_count", "actual_stage127_bridge_ready_count"),
        ("expected_stage125_proof_ready_count", "actual_stage125_proof_ready_count"),
        ("expected_full_supergate_ready", "final_supergate_ready"),
        ("expected_strategy_use_allowed_now", "strategy_use_allowed_now"),
    ]
    for expected, actual_col in compare_pairs:
        if expected in result.columns and actual_col in result.columns:
            result[f"{expected}_matched"] = (
                pd.to_numeric(result[expected], errors="coerce").fillna(-999).astype(int)
                == pd.to_numeric(result[actual_col], errors="coerce").fillna(-998).astype(int)
            ).astype(int)
    match_cols = [column for column in result.columns if column.endswith("_matched")]
    result["expectation_all_matched"] = result[match_cols].min(axis=1).astype(int) if match_cols else 0
    result["unexpected_pass"] = (
        pd.to_numeric(result.get("final_supergate_ready", 0), errors="coerce").fillna(0).astype(int)
        | pd.to_numeric(result.get("strategy_use_allowed_now", 0), errors="coerce").fillna(0).astype(int)
    )
    return result


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, expectation: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage129 bad-drop failure modes over official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1F5D4A", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.26)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    if not request_audit.empty:
        palette = ["#B91C1C", "#A16207", "#0369A1", "#7C3AED", "#0F766E"]
        for idx, (case_id, group) in enumerate(request_audit.groupby("failure_case_id")):
            points = _nearest_curve_points(curve, group["trading_day"])
            color = palette[idx % len(palette)]
            marker = "o" if idx % 2 == 0 else "x"
            axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color=color, marker=marker, s=28, alpha=0.45, label=case_id)
            axes[1].scatter(points["date"], points["drawdown_pct"], color=color, marker=marker, s=28, alpha=0.45)
            axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color=color, marker=marker, s=28, alpha=0.45)
        axes[0].legend(loc="upper left", fontsize=7)
    cols = [
        "actual_stage127_bridge_ready_count",
        "actual_stage125_proof_ready_count",
        "final_supergate_ready",
        "unexpected_pass",
    ]
    chart = expectation.set_index("failure_case_id")[[column for column in cols if column in expectation.columns]].copy()
    if not chart.empty:
        chart.plot(kind="bar", ax=axes[3], color=["#3B5BDB", "#0F766E", "#15803D", "#B91C1C"])
        axes[3].set_ylim(0, max(42, float(chart.to_numpy().max()) + 2))
    axes[3].set_ylabel("count / flag")
    axes[3].set_title("Bad-drop observed gate outcomes")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_matrix(expectation: pd.DataFrame, step_summary: pd.DataFrame) -> None:
    columns = [
        "stage128_commands_ok",
        "actual_schema_valid_any",
        "actual_schema_valid_all",
        "actual_identity_match_all",
        "actual_span_cover_all",
        "actual_stage127_bridge_all",
        "stage125_ready_for_stage123",
        "stage123_final_stage112_ready_count",
        "final_supergate_ready",
        "unexpected_pass",
    ]
    matrix = expectation.set_index("failure_case_id").copy()
    command_ok = (
        step_summary.assign(ok=step_summary["returncode"].eq(0).astype(int))
        .groupby("failure_case_id")["ok"]
        .min()
        if not step_summary.empty and "returncode" in step_summary.columns
        else pd.Series(dtype=int)
    )
    matrix["stage128_commands_ok"] = command_ok
    matrix["actual_schema_valid_any"] = pd.to_numeric(matrix.get("actual_schema_valid_count", 0), errors="coerce").fillna(0).gt(0).astype(int)
    matrix["actual_schema_valid_all"] = pd.to_numeric(matrix.get("actual_schema_valid_count", 0), errors="coerce").fillna(0).eq(41).astype(int)
    matrix["actual_identity_match_all"] = pd.to_numeric(matrix.get("actual_identity_match_count", 0), errors="coerce").fillna(0).eq(41).astype(int)
    matrix["actual_span_cover_all"] = pd.to_numeric(matrix.get("actual_span_cover_count", 0), errors="coerce").fillna(0).eq(41).astype(int)
    matrix["actual_stage127_bridge_all"] = pd.to_numeric(matrix.get("actual_stage127_bridge_ready_count", 0), errors="coerce").fillna(0).eq(41).astype(int)
    for column in columns:
        if column not in matrix.columns:
            matrix[column] = 0
    data = matrix[columns].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13.5, 5.2))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage129 bad-drop supergate matrix")
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, int(data[y, x]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CASE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_expectation(expectation: pd.DataFrame) -> None:
    columns = [
        "expected_schema_valid_count",
        "actual_schema_valid_count",
        "expected_identity_match_count",
        "actual_identity_match_count",
        "expected_span_cover_count",
        "actual_span_cover_count",
        "expected_stage127_bridge_ready_count",
        "actual_stage127_bridge_ready_count",
        "expected_stage125_proof_ready_count",
        "actual_stage125_proof_ready_count",
        "expected_full_supergate_ready",
        "final_supergate_ready",
    ]
    chart = expectation.set_index("failure_case_id")[[column for column in columns if column in expectation.columns]].copy()
    fig, ax = plt.subplots(figsize=(15, 6.5))
    chart.plot(kind="bar", ax=ax, width=0.82)
    ax.set_title("Stage129 expected vs observed bad-drop failure modes")
    ax.set_ylabel("request count / flag")
    ax.set_ylim(0, 44)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(EXPECTATION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_matrix(request_audit: pd.DataFrame) -> None:
    if request_audit.empty:
        return
    columns = [
        "schema_valid",
        "request_identity_match",
        "request_span_cover",
        "proof_schema_bridge_ready",
        "proof_required_fields_present",
        "preflight_request_ready",
        "full_supergate_request_ready",
        "strategy_use_allowed_now",
    ]
    available = [column for column in columns if column in request_audit.columns]
    sample = request_audit.copy().sort_values(["failure_case_id", "trading_day", "request_id"]).reset_index(drop=True)
    data = sample[available].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig_height = max(8.0, min(30.0, len(sample) * 0.12))
    fig, ax = plt.subplots(figsize=(12.5, fig_height))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage129 request-level failure matrix")
    ax.set_xticks(np.arange(len(available)))
    ax.set_xticklabels(available, rotation=35, ha="right")
    labels = []
    for idx, row in sample.iterrows():
        if idx % 7 == 0:
            labels.append(f"{row['failure_case_id']} | {row['request_id']}")
        else:
            labels.append("")
    ax.set_yticks(np.arange(len(sample)))
    ax.set_yticklabels(labels, fontsize=5)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, expectation: pd.DataFrame, case_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 bad-drop failure-mode audit",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: generated local bad-drop fixtures, Stage128 orchestration, and visual QA only; no strategy rule, true engine, A/B, CTP, order API, or external download.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Failure Expectations",
        "",
        _md_table(expectation),
        "",
        "## Stage128 Case Summary",
        "",
        _md_table(case_summary),
        "",
        "## Gate Status",
        "",
        _md_table(gates, max_rows=40),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CASE_MATRIX_CHART_OUT.name}`",
        f"- `{EXPECTATION_CHART_OUT.name}`",
        f"- `{REQUEST_MATRIX_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    requests = _request_meta()
    cases, inventory = _build_bad_drops(requests)

    run_rows: list[dict[str, Any]] = []
    summary_frames: list[pd.DataFrame] = []
    case_frames: list[pd.DataFrame] = []
    step_frames: list[pd.DataFrame] = []
    gate_frames: list[pd.DataFrame] = []
    request_frames: list[pd.DataFrame] = []
    restore_info: dict[str, Any] = {}
    try:
        for case in cases:
            run_row, frames = _run_stage128(case)
            run_rows.append(run_row)
            if not frames["summary"].empty:
                summary_frames.append(frames["summary"])
            if not frames["case_summary"].empty:
                case_frames.append(frames["case_summary"])
            if not frames["step_summary"].empty:
                step_frames.append(frames["step_summary"])
            if not frames["gates"].empty:
                gate_frames.append(frames["gates"])
            if not frames["request_audit"].empty:
                request_frames.append(frames["request_audit"])
    finally:
        restore_info = _restore_stage128_default()

    stage128_summaries = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    case_summary = pd.concat(case_frames, ignore_index=True) if case_frames else pd.DataFrame()
    step_summary = pd.concat(step_frames, ignore_index=True) if step_frames else pd.DataFrame()
    gates = pd.concat(gate_frames, ignore_index=True) if gate_frames else pd.DataFrame()
    request_audit = pd.concat(request_frames, ignore_index=True) if request_frames else pd.DataFrame()
    run_summary = pd.DataFrame(run_rows)
    if not case_summary.empty:
        case_summary = case_summary.merge(run_summary[["failure_case_id", "stage128_returncode"]], on="failure_case_id", how="left")
    expectation = _case_expectation_frame(cases, case_summary, request_audit)

    stage128_returncode_zero = int(run_summary["stage128_returncode"].eq(0).all()) if not run_summary.empty else 0
    all_commands_returncode_zero = int(step_summary["returncode"].eq(0).all()) if not step_summary.empty and "returncode" in step_summary.columns else 0
    unexpected_pass_count = int(pd.to_numeric(expectation["unexpected_pass"], errors="coerce").fillna(0).sum()) if not expectation.empty else 0
    blocked_case_count = int(len(expectation) - unexpected_pass_count)
    expectation_matched_count = int(pd.to_numeric(expectation["expectation_all_matched"], errors="coerce").fillna(0).sum()) if not expectation.empty else 0
    proof_file_count = int(len(inventory))
    full_ready_count = int(pd.to_numeric(case_summary.get("final_supergate_ready", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    strategy_allowed_count = int(pd.to_numeric(case_summary.get("strategy_use_allowed_now", 0), errors="coerce").fillna(0).sum()) if not case_summary.empty else 0
    decision = DECISION
    if unexpected_pass_count > 0 or strategy_allowed_count > 0 or restore_info.get("stage128_default_restored", 0) != 1:
        decision = "stage129_bad_drop_failure_mode_audit_failed"

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
                "failure_case_count": len(cases),
                "generated_bad_drop_file_count": proof_file_count,
                "generated_proof_file_count": proof_file_count,
                "stage128_cli_run_count": len(run_summary),
                "stage128_returncode_zero": stage128_returncode_zero,
                "stage128_all_inner_commands_returncode_zero": all_commands_returncode_zero,
                "stage128_default_restored": int(restore_info.get("stage128_default_restored", 0)),
                "stage128_default_restore_returncode": int(restore_info.get("stage128_default_restore_returncode", -1)),
                "blocked_case_count": blocked_case_count,
                "unexpected_pass_count": unexpected_pass_count,
                "expectation_matched_count": expectation_matched_count,
                "expectation_case_count": len(expectation),
                "full_supergate_ready_count": full_ready_count,
                "strategy_allowed_count": strategy_allowed_count,
                "proof_schema_bridge_ready_case_count": int(
                    pd.to_numeric(expectation.get("actual_stage127_bridge_ready_count", 0), errors="coerce").fillna(0).eq(41).sum()
                )
                if not expectation.empty
                else 0,
                "stage125_proof_ready_case_count": int(
                    pd.to_numeric(expectation.get("actual_stage125_proof_ready_count", 0), errors="coerce").fillna(0).eq(41).sum()
                )
                if not expectation.empty
                else 0,
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
    _write_csv(inventory, INVENTORY_OUT)
    _write_csv(expectation, EXPECTATION_OUT)
    if not stage128_summaries.empty:
        _write_csv(stage128_summaries, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_summary_by_case_{MODEL_TAG}.csv")
    if not run_summary.empty:
        _write_csv(run_summary, OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_command_run_summary_{MODEL_TAG}.csv")

    _plot_official_path(curve, request_audit, expectation)
    _plot_case_matrix(expectation, step_summary)
    _plot_expectation(expectation)
    _plot_request_matrix(request_audit)
    _write_report(summary, expectation, case_summary, gates)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "cases": cases,
            "restore_info": restore_info,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_summary": str(CASE_SUMMARY_OUT),
                "step_summary": str(STEP_SUMMARY_OUT),
                "gates": str(GATE_STATUS_OUT),
                "request_audit": str(REQUEST_AUDIT_OUT),
                "inventory": str(INVENTORY_OUT),
                "expectation": str(EXPECTATION_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CASE_MATRIX_CHART_OUT),
                    str(EXPECTATION_CHART_OUT),
                    str(REQUEST_MATRIX_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
