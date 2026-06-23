from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage119"
MODEL_TAG = "stage119_wave0_drop_manifest_builder_v1"
OUTPUT_PREFIX = "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage119_wave0_drop_manifest_builder"
EMPTY_DROP_DIR = OUTPUT_DIR / "empty_drop"
SYNTHETIC_DROP_DIR = LINE_DIR / "outputs" / "stage118_wave0_verifier_selftest" / "synthetic_fixture"

STAGE117_TOOL = LINE_DIR / "tools" / "stage117_wave0_delivery_verifier.py"
STAGE116_MANIFEST_IN = (
    LINE_DIR
    / "outputs"
    / "stage116_wave0_pipeline_intake_packet"
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_REQUEST_PACKET_IN = (
    LINE_DIR
    / "outputs"
    / "stage116_wave0_pipeline_intake_packet"
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_packet_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage116_wave0_pipeline_intake_packet"
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_summary_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
FILE_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_inventory_{MODEL_TAG}.csv"
MATCH_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_match_status_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage117_gate_status_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage117_request_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_builder_status_{MODEL_TAG}.png"
MATCH_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_match_matrix_{MODEL_TAG}.png"
GATE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_matrix_{MODEL_TAG}.png"
INVENTORY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_chart_{MODEL_TAG}.png"

DECISION = "stage119_drop_builder_selftest_passed_no_real_data_no_strategy"
REQUEST_RE = re.compile(r"stage114_req_\d{4}")
RAW_SUFFIXES = {".raw", ".dbn", ".dat", ".bin", ".gz", ".zip"}
DEFAULT_CASE_ORDER = ["empty_drop_negative", "synthetic_drop_positive"]


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


def _load_verifier_module():
    spec = importlib.util.spec_from_file_location("stage117_wave0_delivery_verifier", STAGE117_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import verifier: {STAGE117_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _role_for_file(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = "".join(path.suffixes).lower()
    if path.suffix.lower() == ".parquet" or "parquet" in parts:
        return "parquet"
    if path.suffix.lower() == ".json" and ("proof" in parts or "proof" in name):
        return "proof"
    if "raw" in parts or path.suffix.lower() in RAW_SUFFIXES or suffix.endswith(".csv.gz"):
        return "raw"
    return "ignored"


def _scan_drop(drop_dir: Path, case_id: str) -> pd.DataFrame:
    rows = []
    if drop_dir.exists():
        files = sorted(path for path in drop_dir.rglob("*") if path.is_file())
    else:
        files = []
    for path in files:
        match = REQUEST_RE.search(str(path))
        request_id = match.group(0) if match else ""
        rows.append(
            {
                "case_id": case_id,
                "drop_dir": str(drop_dir),
                "path": str(path),
                "request_id": request_id,
                "file_role": _role_for_file(path),
                "suffix": "".join(path.suffixes).lower(),
                "bytes": int(path.stat().st_size),
            }
        )
    return pd.DataFrame(rows)


def _choose_file(inventory: pd.DataFrame, request_id: str, role: str) -> str:
    if inventory.empty:
        return ""
    frame = inventory[(inventory["request_id"].eq(request_id)) & (inventory["file_role"].eq(role))].sort_values("path")
    return "" if frame.empty else str(frame.iloc[0]["path"])


def _read_proof(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parquet_metadata(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {"fields": [], "row_count": np.nan, "readable": 0}
    path = Path(path_text)
    if not path.exists():
        return {"fields": [], "row_count": np.nan, "readable": 0}
    try:
        metadata = pq.read_metadata(path)
        return {"fields": list(metadata.schema.names), "row_count": int(metadata.num_rows), "readable": 1}
    except Exception:
        return {"fields": [], "row_count": np.nan, "readable": 0}


def _build_manifest_from_drop(drop_dir: Path, case_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    template = _read_csv(STAGE116_MANIFEST_IN)
    if template.empty:
        raise RuntimeError("missing Stage116 manifest template")
    inventory = _scan_drop(drop_dir, case_id)
    manifest_rows = []
    match_rows = []
    for _, row in template.iterrows():
        request_id = str(row["request_id"])
        raw_path = _choose_file(inventory, request_id, "raw")
        parquet_path = _choose_file(inventory, request_id, "parquet")
        proof_path = _choose_file(inventory, request_id, "proof")
        proof = _read_proof(proof_path)
        parquet_meta = _parquet_metadata(parquet_path)

        raw_sha = _sha256_file(Path(raw_path)) if raw_path and Path(raw_path).exists() else ""
        fields = parquet_meta["fields"]
        schema_hash = _sha256_text(";".join(fields)) if fields else ""
        row_count = proof.get("row_count", parquet_meta["row_count"])
        first_ts_event = proof.get("first_ts_event", "")
        last_ts_event = proof.get("last_ts_event", "")
        sequence_gap_count = proof.get("sequence_gap_count", "")
        synthetic_fixture = bool(proof.get("synthetic_fixture", False))

        output = row.to_dict()
        output.update(
            {
                "vendor": proof.get("vendor", "synthetic_selftest" if synthetic_fixture else ""),
                "license_id": proof.get("license_id", "synthetic_no_market_data" if synthetic_fixture else ""),
                "dataset": proof.get("dataset", "stage119_drop_builder_fixture" if synthetic_fixture else ""),
                "schema_delivered": row.get("required_schema_request", "") if parquet_path else "",
                "raw_file": raw_path,
                "raw_sha256": raw_sha,
                "normalized_parquet_file": parquet_path,
                "proof_file": proof_path,
                "schema_hash": proof.get("schema_hash", schema_hash),
                "field_dictionary_version": proof.get("field_dictionary_version", "synthetic_stage119_drop_builder_v1" if synthetic_fixture else ""),
                "ts_event_timezone": proof.get("ts_event_timezone", "Asia/Shanghai" if synthetic_fixture else ""),
                "ts_recv_timezone": proof.get("ts_recv_timezone", "Asia/Shanghai" if synthetic_fixture else ""),
                "first_ts_event": first_ts_event,
                "last_ts_event": last_ts_event,
                "row_count": row_count,
                "sequence_gap_count": sequence_gap_count,
                "capture_continuity_proof": proof.get(
                    "capture_continuity_proof",
                    "synthetic_sequence_gap_zero_proof" if synthetic_fixture and sequence_gap_count == 0 else "",
                ),
                "acceptance_status": "drop_builder_matched" if raw_path and parquet_path and proof_path else "drop_builder_incomplete",
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
                "notes": "synthetic builder selftest only; not real market data" if synthetic_fixture else "",
            }
        )
        manifest_rows.append(output)
        match_rows.append(
            {
                "case_id": case_id,
                "request_id": request_id,
                "raw_matched": int(bool(raw_path)),
                "parquet_matched": int(bool(parquet_path)),
                "proof_matched": int(bool(proof_path)),
                "all_three_matched": int(bool(raw_path and parquet_path and proof_path)),
                "parquet_readable": int(parquet_meta["readable"]),
                "raw_file": raw_path,
                "parquet_file": parquet_path,
                "proof_file": proof_path,
            }
        )
    manifest = pd.DataFrame(manifest_rows)
    match_status = pd.DataFrame(match_rows)
    manifest_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{case_id}_built_manifest_{MODEL_TAG}.csv"
    _write_csv(manifest, manifest_path)
    manifest["built_manifest_path"] = str(manifest_path)
    return manifest, inventory, match_status


def _run_verifier_case(verifier, case_id: str, manifest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    request_packet = _read_csv(STAGE116_REQUEST_PACKET_IN)
    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    manifest_path = Path(str(manifest["built_manifest_path"].iloc[0]))
    for frame in [request_packet, manifest]:
        for column in ["trading_day", "request_start", "request_end", "first_ts_event", "last_ts_event"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
    request_status, _, issues = verifier._build_request_status(request_packet, manifest, manifest_path)
    gate_status = verifier._build_gate_status(request_status, manifest)
    summary = verifier._build_summary(
        request_status,
        gate_status,
        issues,
        stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object),
        manifest_path,
    )
    for frame in [summary, request_status, gate_status]:
        frame["case_id"] = case_id
    return summary, request_status, gate_status


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _case_color_map(case_ids: list[str]) -> dict[str, str]:
    palette = ["#B91C1C", "#15803D", "#0369A1", "#7C2D12", "#6D28D9", "#A16207", "#0F766E"]
    defaults = {"empty_drop_negative": "#B91C1C", "synthetic_drop_positive": "#15803D"}
    return {case_id: defaults.get(case_id, palette[idx % len(palette)]) for idx, case_id in enumerate(case_ids)}


def _ordered_cases(frame: pd.DataFrame) -> list[str]:
    observed = [str(case_id) for case_id in frame["case_id"].dropna().unique()]
    ordered = [case_id for case_id in DEFAULT_CASE_ORDER if case_id in observed]
    ordered.extend(case_id for case_id in observed if case_id not in ordered)
    return ordered


def _plot_official_path(curve: pd.DataFrame, request_status: pd.DataFrame) -> None:
    case_ids = _ordered_cases(request_status)
    colors = _case_color_map(case_ids)
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    for idx, case_id in enumerate(case_ids):
        case_rows = request_status[request_status["case_id"].eq(case_id)]
        points = _nearest_curve_points(curve, case_rows["trading_day"])
        offset = (idx - (len(case_ids) - 1) / 2) * 0.35
        axes[0].scatter(points["date"], points["account_equity"] / 1_000_000 + offset, color=colors[case_id], s=38, alpha=0.65, label=case_id)
        axes[1].scatter(points["date"], points["drawdown_pct"] + offset, color=colors[case_id], s=38, alpha=0.65)
        axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"] + offset, color=colors[case_id], s=38, alpha=0.65)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Stage119 drop builder selftest on official path; synthetic positive is not real W0")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_match_matrix(match_status: pd.DataFrame) -> None:
    case_ids = _ordered_cases(match_status)
    pivot = (
        match_status.groupby("case_id")[["raw_matched", "parquet_matched", "proof_matched", "all_three_matched"]]
        .sum()
        .reindex(case_ids)
        .fillna(0)
    )
    fig, ax = plt.subplots(figsize=(10, 4.8))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, str(int(pivot.iloc[y, x])), ha="center", va="center", color="#111827")
    ax.set_title("Stage119 W0 drop matched request counts")
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(MATCH_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_matrix(gate_status: pd.DataFrame) -> None:
    pivot = gate_status.pivot_table(index="gate_id", columns="case_id", values="pass_now", aggfunc="max", fill_value=0)
    pivot = pivot[_ordered_cases(gate_status)]
    fig, ax = plt.subplots(figsize=(8, 9))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, "P" if int(pivot.iloc[y, x]) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage119 builder -> Stage117 gate matrix")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(GATE_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_inventory(inventory: pd.DataFrame) -> None:
    if inventory.empty:
        chart = pd.DataFrame({"case_id": ["empty_drop_negative", "synthetic_drop_positive"], "file_role": ["none", "none"], "count": [0, 0]})
    else:
        chart = inventory.groupby(["case_id", "file_role"]).size().reset_index(name="count")
    pivot = chart.pivot_table(index="case_id", columns="file_role", values="count", fill_value=0)
    pivot = pivot.reindex(_ordered_cases(chart)).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax, color={"raw": "#0F766E", "parquet": "#0369A1", "proof": "#A16207", "ignored": "#94A3B8", "none": "#CBD5E1"})
    ax.set_ylabel("file count")
    ax.set_title("Stage119 drop inventory by role")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(INVENTORY_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, case_summary: pd.DataFrame, match_status: pd.DataFrame, gate_status: pd.DataFrame) -> None:
    row = summary.iloc[0]
    match_agg = (
        match_status.groupby("case_id")[["raw_matched", "parquet_matched", "proof_matched", "all_three_matched", "parquet_readable"]]
        .sum()
        .reset_index()
    )
    report = f"""# Stage119 W0 drop manifest builder

## Decision

- decision: `{row['decision']}`
- nature: drop scanner and manifest builder selftest; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- synthetic drop: `{SYNTHETIC_DROP_DIR}`

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

## Case Summary

{_md_table(case_summary)}

## Match Summary

{_md_table(match_agg)}

## Gate Status

{_md_table(gate_status[['case_id', 'gate_id', 'observed', 'required', 'pass_now', 'severity']], max_rows=40)}

## Visual Outputs

- official path builder status: `{PATH_CHART_OUT}`
- match matrix: `{MATCH_MATRIX_CHART_OUT}`
- gate matrix: `{GATE_MATRIX_CHART_OUT}`
- inventory chart: `{INVENTORY_CHART_OUT}`

## Judgment

The builder can reconstruct a Stage117-compatible manifest from a request_id-keyed synthetic drop and leaves an empty drop blocked. This is a drop-processing tool test only; real W0 remains undelivered.
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Stage117-compatible W0 delivery manifest from a request_id-keyed drop directory."
    )
    parser.add_argument(
        "--drop-dir",
        type=Path,
        default=None,
        help="Optional W0 drop directory to scan. If omitted, built-in empty and synthetic selftests are run.",
    )
    parser.add_argument("--case-id", default="cli_drop", help="Case id used in outputs for --drop-dir.")
    parser.add_argument(
        "--expected-stage112-intake",
        type=int,
        choices=[0, 1],
        default=0,
        help="Expected Stage112 intake flag for the CLI drop case, used for selftest pass/fail.",
    )
    parser.add_argument(
        "--skip-synthetic-selftest",
        action="store_true",
        help="When --drop-dir is used, skip the Stage118 synthetic positive companion case.",
    )
    return parser.parse_args()


def _is_synthetic_drop(case_id: str, drop_dir: Path) -> bool:
    try:
        same_path = drop_dir.resolve() == SYNTHETIC_DROP_DIR.resolve()
    except FileNotFoundError:
        same_path = False
    return same_path or "synthetic" in case_id.lower()


def main(
    drop_dir: Path | None = None,
    case_id: str = "cli_drop",
    expected_stage112_intake: int = 0,
    include_synthetic_selftest: bool = True,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EMPTY_DROP_DIR.mkdir(parents=True, exist_ok=True)
    verifier = _load_verifier_module()

    cli_mode = drop_dir is not None
    if drop_dir is not None:
        drop_dir = drop_dir.expanduser().resolve()
    if cli_mode:
        cases = [(case_id, drop_dir, expected_stage112_intake)]
        if include_synthetic_selftest and not _is_synthetic_drop(case_id, drop_dir):
            cases.append(("synthetic_drop_positive", SYNTHETIC_DROP_DIR, 1))
    else:
        cases = [
            ("empty_drop_negative", EMPTY_DROP_DIR, 0),
            ("synthetic_drop_positive", SYNTHETIC_DROP_DIR, 1),
        ]
    manifests = []
    inventories = []
    matches = []
    summaries = []
    request_statuses = []
    gates = []
    case_rows = []
    for case_id, drop_dir, expected_stage112 in cases:
        synthetic_like_case = int(_is_synthetic_drop(case_id, drop_dir))
        real_candidate_case = int(cli_mode and not synthetic_like_case)
        manifest, inventory, match_status = _build_manifest_from_drop(drop_dir, case_id)
        summary, request_status, gate_status = _run_verifier_case(verifier, case_id, manifest)
        observed_stage112 = int(summary.iloc[0]["stage112_intake_allowed_now"])
        hard_accept = int(summary.iloc[0]["w0_hard_accept_request_count"])
        all_three = int(match_status["all_three_matched"].sum())
        case_rows.append(
            {
                "case_id": case_id,
                "drop_dir": str(drop_dir),
                "built_manifest_path": str(manifest["built_manifest_path"].iloc[0]),
                "file_count": int(len(inventory)),
                "raw_match_count": int(match_status["raw_matched"].sum()),
                "parquet_match_count": int(match_status["parquet_matched"].sum()),
                "proof_match_count": int(match_status["proof_matched"].sum()),
                "all_three_match_count": all_three,
                "hard_accept_request_count": hard_accept,
                "expected_stage112_intake_allowed": expected_stage112,
                "observed_stage112_intake_allowed": observed_stage112,
                "synthetic_like_case": synthetic_like_case,
                "real_candidate_case": real_candidate_case,
                "test_pass": int(observed_stage112 == expected_stage112),
            }
        )
        manifests.append(manifest)
        inventories.append(inventory)
        matches.append(match_status)
        summaries.append(summary)
        request_statuses.append(request_status)
        gates.append(gate_status)

    case_summary = pd.DataFrame(case_rows)
    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    base = stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object)
    selftest_pass_count = int(case_summary["test_pass"].sum())
    request_count = int(len(_read_csv(STAGE116_MANIFEST_IN)))
    real_cases = case_summary[case_summary["real_candidate_case"].eq(1)] if "real_candidate_case" in case_summary.columns else pd.DataFrame()
    real_drop_scanned = int(len(real_cases) > 0)
    real_data_delivered = int(
        len(real_cases) > 0
        and int(real_cases["observed_stage112_intake_allowed"].max()) == 1
        and int(real_cases["hard_accept_request_count"].max()) == request_count
    )
    real_stage112_allowed = int(len(real_cases) > 0 and int(real_cases["observed_stage112_intake_allowed"].max()) == 1)
    empty_stage112_allowed = (
        int(case_summary.loc[case_summary["case_id"].eq("empty_drop_negative"), "observed_stage112_intake_allowed"].iloc[0])
        if case_summary["case_id"].eq("empty_drop_negative").any()
        else 0
    )
    synthetic_stage112_allowed = (
        int(case_summary.loc[case_summary["case_id"].eq("synthetic_drop_positive"), "observed_stage112_intake_allowed"].iloc[0])
        if case_summary["case_id"].eq("synthetic_drop_positive").any()
        else 0
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": DECISION if selftest_pass_count == len(case_summary) else "stage119_drop_builder_selftest_failed",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "case_count": int(len(case_summary)),
                "selftest_pass_count": selftest_pass_count,
                "selftest_fail_count": int(len(case_summary) - selftest_pass_count),
                "empty_drop_stage112_allowed": empty_stage112_allowed,
                "synthetic_drop_stage112_allowed": synthetic_stage112_allowed,
                "real_w0_drop_scanned": real_drop_scanned,
                "real_w0_data_delivered": real_data_delivered,
                "real_stage112_intake_allowed_now": real_stage112_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(base.get("end_equity", np.nan)),
                "total_return_pct": float(base.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(base.get("max_drawdown_pct", np.nan)),
                "sharpe": float(base.get("sharpe", np.nan)),
                "total_slippage": float(base.get("total_slippage", np.nan)),
                "total_trade_count": float(base.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(base.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(base.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )
    inventory = pd.concat(inventories, ignore_index=True) if inventories else pd.DataFrame()
    match_status = pd.concat(matches, ignore_index=True)
    request_status = pd.concat(request_statuses, ignore_index=True)
    gate_status = pd.concat(gates, ignore_index=True)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summary, CASE_SUMMARY_OUT)
    _write_csv(inventory, FILE_INVENTORY_OUT)
    _write_csv(match_status, MATCH_STATUS_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_csv(request_status, REQUEST_STATUS_OUT)

    curve = _load_curve()
    _plot_official_path(curve, request_status)
    _plot_match_matrix(match_status)
    _plot_gate_matrix(gate_status)
    _plot_inventory(inventory)
    _write_report(summary, case_summary, match_status, gate_status)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": SUMMARY_OUT,
        "case_summary_path": CASE_SUMMARY_OUT,
        "file_inventory_path": FILE_INVENTORY_OUT,
        "match_status_path": MATCH_STATUS_OUT,
        "gate_status_path": GATE_STATUS_OUT,
        "request_status_path": REQUEST_STATUS_OUT,
        "report_path": REPORT_OUT,
        "charts": [
            PATH_CHART_OUT,
            MATCH_MATRIX_CHART_OUT,
            GATE_MATRIX_CHART_OUT,
            INVENTORY_CHART_OUT,
        ],
        "real_w0_drop_scanned": real_drop_scanned,
        "real_w0_data_delivered": real_data_delivered,
        "real_stage112_intake_allowed_now": real_stage112_allowed,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    args = _parse_args()
    main(
        drop_dir=args.drop_dir,
        case_id=args.case_id,
        expected_stage112_intake=args.expected_stage112_intake,
        include_synthetic_selftest=not args.skip_synthetic_selftest,
    )
