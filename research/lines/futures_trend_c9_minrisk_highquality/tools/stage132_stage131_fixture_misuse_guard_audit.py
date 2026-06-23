from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage132"
MODEL_TAG = "stage132_stage131_fixture_misuse_guard_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage132_stage131_fixture_misuse_guard_audit"
SHADOW_INTAKE_ROOT = OUTPUT_DIR / "shadow_authorized_microstructure_intake"

STAGE112_TOOL = LINE_DIR / "tools" / "stage112_authorized_microstructure_data_drop_validator.py"
STAGE113_TOOL = LINE_DIR / "tools" / "stage113_microstructure_required_window_coverage.py"

STAGE131_DIR = LINE_DIR / "outputs" / "stage131_wave0_positive_drop_supergate_audit"
STAGE131_INVENTORY_IN = (
    STAGE131_DIR
    / "qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_drop_file_inventory_"
    "stage131_wave0_positive_drop_supergate_audit_v1.csv"
)
STAGE131_REQUEST_AUDIT_IN = (
    STAGE131_DIR
    / "qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_request_audit_"
    "stage131_wave0_positive_drop_supergate_audit_v1.csv"
)
STAGE131_SUMMARY_IN = (
    STAGE131_DIR
    / "qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_summary_"
    "stage131_wave0_positive_drop_supergate_audit_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SHADOW_MANIFEST_OUT = SHADOW_INTAKE_ROOT / "manifest.csv"
SHADOW_MANIFEST_COPY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_manifest_{MODEL_TAG}.csv"
STAGE112_SHADOW_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_inventory_{MODEL_TAG}.csv"
STAGE112_SHADOW_FILE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_file_audit_{MODEL_TAG}.csv"
STAGE112_SHADOW_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_acceptance_gate_{MODEL_TAG}.csv"
STAGE112_SHADOW_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage112_shadow_coverage_requirements_{MODEL_TAG}.csv"
STAGE113_SHADOW_FILE_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage113_shadow_file_index_{MODEL_TAG}.csv"
STAGE113_SHADOW_COVERAGE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage113_shadow_coverage_audit_{MODEL_TAG}.csv"
STAGE113_SHADOW_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage113_shadow_coverage_gate_{MODEL_TAG}.csv"
BOUNDARY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixture_boundary_audit_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_misuse_expectation_audit_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_fixture_block_status_{MODEL_TAG}.png"
MISUSE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_misuse_guard_matrix_{MODEL_TAG}.png"
BOUNDARY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixture_boundary_chart_{MODEL_TAG}.png"
SHADOW_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_intake_gate_chart_{MODEL_TAG}.png"

DECISION = "stage132_stage131_fixture_blocked_from_stage112_113_no_strategy"


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
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _baseline_metrics() -> dict[str, float]:
    stage131 = _read_csv(STAGE131_SUMMARY_IN)
    if not stage131.empty:
        row = stage131.iloc[0]
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
    curve = _load_curve()
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


def _path_inside(child: Path, parent: Path) -> int:
    try:
        child.resolve().relative_to(parent.resolve())
        return 1
    except ValueError:
        return 0


def _select_stage131_files() -> dict[str, Any]:
    inventory = _read_csv(STAGE131_INVENTORY_IN)
    if inventory.empty:
        raise RuntimeError(f"missing Stage131 inventory: {STAGE131_INVENTORY_IN}")
    parquet = inventory[inventory["artifact_role"].astype(str).eq("normalized_parquet")].sort_values("request_id").iloc[0]
    request_id = _clean(parquet["request_id"])
    raw = inventory[
        inventory["artifact_role"].astype(str).eq("raw")
        & inventory["request_id"].astype(str).eq(request_id)
    ].iloc[0]
    return {
        "request_id": request_id,
        "parquet_path": Path(_clean(parquet["path"])).resolve(),
        "raw_path": Path(_clean(raw["path"])).resolve(),
        "raw_sha256": _clean(raw["sha256"]) or _sha256_file(Path(_clean(raw["path"]))),
    }


def _build_shadow_manifest(stage112_module) -> pd.DataFrame:
    if SHADOW_INTAKE_ROOT.exists():
        shutil.rmtree(SHADOW_INTAKE_ROOT)
    SHADOW_INTAKE_ROOT.mkdir(parents=True, exist_ok=True)
    selected = _select_stage131_files()
    risk = _read_csv(stage112_module.STAGE108_RISK_IN)
    right_tail_required = int(pd.to_numeric(risk.get("right_tail_visual", 0), errors="coerce").fillna(0).sum())
    bottom_loss_required = int(pd.to_numeric(risk.get("bottom_loss_visual", 0), errors="coerce").fillna(0).sum())
    manifest = pd.DataFrame(
        [
            {
                "dataset_id": "stage131_contract_positive_fixture_misuse_probe",
                "schema_type": "authorized_mbp10_l2",
                "source_vendor": "authorized_research_feed_vendor",
                "source_license": "research_allowed_contract_id",
                "exchange": "DCE",
                "symbol": "lh",
                "vt_symbol": "lh2411.DCE",
                "start_ts": "2020-01-01 00:00:00+08:00",
                "end_ts": "2026-12-31 23:59:59+08:00",
                "timezone": "Asia/Shanghai",
                "data_file": str(selected["parquet_path"]),
                "raw_file": str(selected["raw_path"]),
                "raw_sha256": selected["raw_sha256"],
                "schema_hash": "stage131_contract_positive_fixture_schema_hash",
                "query_params": "stage132 misuse probe; deliberately points at Stage131 positive fixture",
                "timestamp_ready_order_coverage_pct": 100.0,
                "right_tail_covered_count": right_tail_required,
                "bottom_loss_covered_count": bottom_loss_required,
                "sequence_gap_count": 0,
                "coverage_proof": "stage131_local_contract_positive_gap_zero",
                "notes": "stage131 positive_drop contract_positive fixture must never become Stage112 or Stage113 rule data",
            }
        ]
    )
    _write_csv(manifest, SHADOW_MANIFEST_OUT)
    _write_csv(manifest, SHADOW_MANIFEST_COPY_OUT)
    return manifest


def _run_stage112_shadow(stage112_module) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_roots = list(stage112_module.INTAKE_ROOTS)
    try:
        stage112_module.INTAKE_ROOTS = [SHADOW_INTAKE_ROOT]
        risk = _read_csv(stage112_module.STAGE108_RISK_IN)
        inventory, files = stage112_module._scan_intake_roots(risk)
        coverage = stage112_module._coverage_requirements(risk, inventory)
        gate = stage112_module._acceptance_gate(inventory, files, coverage)
    finally:
        stage112_module.INTAKE_ROOTS = original_roots
    return inventory, files, coverage, gate


def _run_stage113_shadow(stage113_module) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_roots = list(stage113_module.INTAKE_ROOTS)
    try:
        stage113_module.INTAKE_ROOTS = [SHADOW_INTAKE_ROOT]
        windows = stage113_module._build_required_windows()
        file_index = stage113_module._scan_intake_files()
        coverage_audit = stage113_module._coverage_audit(windows, file_index)
        candidate_summary = stage113_module._candidate_summary(windows, coverage_audit)
        gate = stage113_module._coverage_gate(windows, candidate_summary, coverage_audit, file_index)
    finally:
        stage113_module.INTAKE_ROOTS = original_roots
    return file_index, coverage_audit, gate


def _boundary_audit(stage112_module, stage113_module) -> pd.DataFrame:
    selected = _select_stage131_files()
    rows = []
    default_roots = list(stage112_module.INTAKE_ROOTS)
    for root in default_roots:
        root_path = Path(root)
        rows.append(
            {
                "boundary_check": f"stage131_parquet_not_under_{root_path.name}",
                "path": str(selected["parquet_path"]),
                "root": str(root_path),
                "pass_now": int(_path_inside(selected["parquet_path"], root_path) == 0),
                "observed": "outside_fixed_root" if _path_inside(selected["parquet_path"], root_path) == 0 else "inside_fixed_root",
            }
        )
        rows.append(
            {
                "boundary_check": f"stage131_raw_not_under_{root_path.name}",
                "path": str(selected["raw_path"]),
                "root": str(root_path),
                "pass_now": int(_path_inside(selected["raw_path"], root_path) == 0),
                "observed": "outside_fixed_root" if _path_inside(selected["raw_path"], root_path) == 0 else "inside_fixed_root",
            }
        )
    rows.append(
        {
            "boundary_check": "stage112_marker_guard_contains_stage131",
            "path": "OLD_SOURCE_MARKERS",
            "root": str(STAGE112_TOOL),
            "pass_now": int("stage131" in getattr(stage112_module, "OLD_SOURCE_MARKERS")),
            "observed": ";".join(getattr(stage112_module, "OLD_SOURCE_MARKERS")),
        }
    )
    rows.append(
        {
            "boundary_check": "stage113_marker_guard_contains_stage131",
            "path": "LOCAL_FIXTURE_MARKERS",
            "root": str(STAGE113_TOOL),
            "pass_now": int("stage131" in getattr(stage113_module, "LOCAL_FIXTURE_MARKERS")),
            "observed": ";".join(getattr(stage113_module, "LOCAL_FIXTURE_MARKERS")),
        }
    )
    return pd.DataFrame(rows)


def _expectation_frame(
    stage112_files: pd.DataFrame,
    stage112_gate: pd.DataFrame,
    stage113_file_index: pd.DataFrame,
    stage113_coverage_gate: pd.DataFrame,
    boundary: pd.DataFrame,
) -> pd.DataFrame:
    stage112_marker_blocked = int(stage112_files.get("old_source_marker", pd.Series(dtype=str)).map(_clean).ne("").sum()) if not stage112_files.empty else 0
    stage112_basic_pass = int(pd.to_numeric(stage112_files.get("basic_intake_pass", 0), errors="coerce").fillna(0).sum()) if not stage112_files.empty else 0
    stage112_rule_ready = int(pd.to_numeric(stage112_files.get("rule_research_ready", 0), errors="coerce").fillna(0).sum()) if not stage112_files.empty else 0
    stage113_marker_blocked = int(stage113_file_index.get("read_error", pd.Series(dtype=str)).astype(str).str.contains("blocked_local_fixture_marker", regex=False).sum()) if not stage113_file_index.empty else 0
    stage113_indexed_files = int(pd.to_numeric(stage113_file_index.get("file_exists", 0), errors="coerce").fillna(0).sum()) if not stage113_file_index.empty else 0
    stage113_coverage_pass = int(pd.to_numeric(stage113_coverage_gate.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not stage113_coverage_gate.empty else 0
    boundary_pass = int(pd.to_numeric(boundary.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not boundary.empty else 0
    rows = [
        ("stage112_fixture_marker_detected", ">=1", stage112_marker_blocked, int(stage112_marker_blocked >= 1)),
        ("stage112_basic_intake_blocked", "0", stage112_basic_pass, int(stage112_basic_pass == 0)),
        ("stage112_rule_ready_blocked", "0", stage112_rule_ready, int(stage112_rule_ready == 0)),
        ("stage113_fixture_marker_detected", ">=1", stage113_marker_blocked, int(stage113_marker_blocked >= 1)),
        ("stage113_file_index_blocked", "0", stage113_indexed_files, int(stage113_indexed_files == 0)),
        ("stage113_coverage_blocked", "0", stage113_coverage_pass, int(stage113_coverage_pass == 0)),
        ("fixed_root_boundary_passed", f"{len(boundary)}/{len(boundary)}", boundary_pass, int(boundary_pass == len(boundary) and len(boundary) > 0)),
    ]
    return pd.DataFrame(
        [
            {
                "expectation_id": item,
                "required": required,
                "observed": observed,
                "pass_now": pass_now,
            }
            for item, required, observed, pass_now in rows
        ]
    )


def _plot_official_path(curve: pd.DataFrame, request_audit: pd.DataFrame, expectation: pd.DataFrame) -> None:
    request_audit = request_audit.copy()
    request_audit["trading_day"] = pd.to_datetime(request_audit["trading_day"], errors="coerce")
    points = _nearest_curve_points(curve, request_audit["trading_day"])
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    fig.suptitle("Stage132 Stage131 fixture is blocked before downstream rule data", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1F5D4A", linewidth=1.2)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color="#B91C1C", s=36, alpha=0.7, label="Stage131 fixture blocked")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.25)
    axes[1].scatter(points["date"], points["drawdown_pct"], color="#B91C1C", s=34, alpha=0.7)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.8)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color="#B91C1C", s=34, alpha=0.7)
    axes[2].set_ylabel("broker10 %")
    for axis in axes:
        axis.grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_misuse_matrix(expectation: pd.DataFrame) -> None:
    data = expectation.set_index("expectation_id")[["pass_now"]].astype(float)
    fig, ax = plt.subplots(figsize=(9, 5.8))
    image = ax.imshow(data.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index, fontsize=8)
    for row, value in enumerate(data["pass_now"]):
        ax.text(0, row, "P" if int(value) else "F", ha="center", va="center", fontsize=8)
    ax.set_title("Stage132 misuse guard expectations")
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(MISUSE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_boundary(boundary: pd.DataFrame) -> None:
    data = boundary.copy()
    fig, ax = plt.subplots(figsize=(11, max(4.8, len(data) * 0.42)))
    colors = data["pass_now"].map({1: "#15803D", 0: "#B91C1C"}).fillna("#64748B")
    ax.barh(data["boundary_check"], data["pass_now"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass")
    ax.set_title("Stage132 fixture boundary checks")
    for idx, row in enumerate(data.itertuples(index=False)):
        ax.text(0.04, idx, str(row.observed)[:80], color="white", va="center", fontsize=7)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BOUNDARY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_shadow_gate(stage112_gate: pd.DataFrame, stage113_gate: pd.DataFrame) -> None:
    left = stage112_gate[["gate_id", "pass_now"]].copy()
    left["source"] = "stage112_shadow"
    right = stage113_gate[["gate_id", "pass_now"]].copy()
    right["source"] = "stage113_shadow"
    combined = pd.concat([left, right], ignore_index=True)
    combined["label"] = combined["source"] + "::" + combined["gate_id"].astype(str)
    values = pd.to_numeric(combined["pass_now"], errors="coerce").fillna(0).clip(upper=1).to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, max(6, len(combined) * 0.34)))
    image = ax.imshow(values.reshape(-1, 1), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0])
    ax.set_xticklabels(["pass"])
    ax.set_yticks(np.arange(len(combined)))
    ax.set_yticklabels(combined["label"], fontsize=8)
    for y, value in enumerate(values):
        ax.text(0, y, "P" if int(value) else "F", ha="center", va="center", fontsize=8)
    ax.set_title("Stage132 shadow intake downstream gate status")
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(SHADOW_GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    expectation: pd.DataFrame,
    boundary: pd.DataFrame,
    stage112_files: pd.DataFrame,
    stage113_file_index: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage132 Stage131 fixture misuse guard audit",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: downstream misuse guard only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.",
        "- scope: Stage112 marker guard, Stage113 file-index guard, fixed-root boundary, visual QA.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Expectation Audit",
        "",
        _md_table(expectation),
        "",
        "## Boundary Audit",
        "",
        _md_table(boundary),
        "",
        "## Stage112 Shadow File Audit",
        "",
        _md_table(stage112_files, max_rows=20),
        "",
        "## Stage113 Shadow File Index",
        "",
        _md_table(stage113_file_index, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{MISUSE_MATRIX_CHART_OUT.name}`",
        f"- `{BOUNDARY_CHART_OUT.name}`",
        f"- `{SHADOW_GATE_CHART_OUT.name}`",
        "",
        "## Judgment",
        "",
        (
            "Stage131 proves the positive W0 supergate path, but its files are local contract-positive fixtures. "
            "Stage132 confirms those files are outside fixed authorized roots by default and are blocked by marker guards "
            "even when a shadow manifest points at them with authorized-looking metadata."
        ),
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    request_audit = _read_csv(STAGE131_REQUEST_AUDIT_IN)
    stage112_module = _load_module("stage112_guard_module", STAGE112_TOOL)
    stage113_module = _load_module("stage113_guard_module", STAGE113_TOOL)
    shadow_manifest = _build_shadow_manifest(stage112_module)
    stage112_inventory, stage112_files, stage112_coverage, stage112_gate = _run_stage112_shadow(stage112_module)
    stage113_file_index, stage113_coverage_audit, stage113_gate = _run_stage113_shadow(stage113_module)
    boundary = _boundary_audit(stage112_module, stage113_module)
    expectation = _expectation_frame(stage112_files, stage112_gate, stage113_file_index, stage113_gate, boundary)
    expectation_pass = int(pd.to_numeric(expectation["pass_now"], errors="coerce").fillna(0).sum())
    decision = DECISION if expectation_pass == len(expectation) else "stage132_stage131_fixture_misuse_guard_failed"
    metrics = _baseline_metrics()
    stage112_marker_count = int(stage112_files.get("old_source_marker", pd.Series(dtype=str)).map(_clean).ne("").sum()) if not stage112_files.empty else 0
    stage113_marker_count = int(stage113_file_index.get("read_error", pd.Series(dtype=str)).astype(str).str.contains("blocked_local_fixture_marker", regex=False).sum()) if not stage113_file_index.empty else 0
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
                "shadow_manifest_row_count": len(shadow_manifest),
                "stage112_fixture_marker_blocked_count": stage112_marker_count,
                "stage112_basic_intake_pass_count": int(pd.to_numeric(stage112_files.get("basic_intake_pass", 0), errors="coerce").fillna(0).sum()) if not stage112_files.empty else 0,
                "stage112_rule_ready_count": int(pd.to_numeric(stage112_files.get("rule_research_ready", 0), errors="coerce").fillna(0).sum()) if not stage112_files.empty else 0,
                "stage113_fixture_marker_blocked_count": stage113_marker_count,
                "stage113_indexed_file_count": int(pd.to_numeric(stage113_file_index.get("file_exists", 0), errors="coerce").fillna(0).sum()) if not stage113_file_index.empty else 0,
                "stage113_coverage_gate_pass_count": int(pd.to_numeric(stage113_gate.get("pass_now", 0), errors="coerce").fillna(0).sum()) if not stage113_gate.empty else 0,
                "expectation_pass_count": expectation_pass,
                "expectation_count": len(expectation),
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(stage112_inventory, STAGE112_SHADOW_INVENTORY_OUT)
    _write_csv(stage112_files, STAGE112_SHADOW_FILE_AUDIT_OUT)
    _write_csv(stage112_gate, STAGE112_SHADOW_GATE_OUT)
    _write_csv(stage112_coverage, STAGE112_SHADOW_COVERAGE_OUT)
    _write_csv(stage113_file_index, STAGE113_SHADOW_FILE_INDEX_OUT)
    _write_csv(stage113_coverage_audit, STAGE113_SHADOW_COVERAGE_AUDIT_OUT)
    _write_csv(stage113_gate, STAGE113_SHADOW_GATE_OUT)
    _write_csv(boundary, BOUNDARY_AUDIT_OUT)
    _write_csv(expectation, EXPECTATION_OUT)

    _plot_official_path(curve, request_audit, expectation)
    _plot_misuse_matrix(expectation)
    _plot_boundary(boundary)
    _plot_shadow_gate(stage112_gate, stage113_gate)
    _write_report(summary, expectation, boundary, stage112_files, stage113_file_index)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "shadow_intake_root": str(SHADOW_INTAKE_ROOT),
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "shadow_manifest": str(SHADOW_MANIFEST_COPY_OUT),
                "stage112_file_audit": str(STAGE112_SHADOW_FILE_AUDIT_OUT),
                "stage113_file_index": str(STAGE113_SHADOW_FILE_INDEX_OUT),
                "boundary_audit": str(BOUNDARY_AUDIT_OUT),
                "expectation": str(EXPECTATION_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(MISUSE_MATRIX_CHART_OUT),
                    str(BOUNDARY_CHART_OUT),
                    str(SHADOW_GATE_CHART_OUT),
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
