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
STAGE = "Stage179"
MODEL_TAG = "stage179_predecision_lookback_point_in_time_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage179_c9_minrisk_predecision_lookback_point_in_time_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage179_predecision_lookback_point_in_time_validator"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE177_DIR = LINE_DIR / "outputs" / "stage177_predecision_lookback_extension_manifest"
STAGE177_PREFIX = "qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest"
STAGE177_TAG = "stage177_predecision_lookback_extension_manifest_v1"
STAGE177_SUMMARY_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_summary_{STAGE177_TAG}.csv"
STAGE177_REQUEST_MANIFEST_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_request_manifest_{STAGE177_TAG}.csv"
STAGE177_EXTENSION_WINDOWS_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_extension_window_contract_{STAGE177_TAG}.csv"

STAGE178_DIR = LINE_DIR / "outputs" / "stage178_predecision_lookback_tick_aggregate_delivery_batch"
STAGE178_PREFIX = "qmt_roll_stage178_c9_minrisk_predecision_lookback_tick_aggregate_delivery_batch"
STAGE178_TAG = "stage178_predecision_lookback_tick_aggregate_delivery_batch_v1"
STAGE178_SUMMARY_IN = STAGE178_DIR / f"{STAGE178_PREFIX}_summary_{STAGE178_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_file_audit_{MODEL_TAG}.csv"
PROOF_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proof_json_audit_{MODEL_TAG}.csv"
NORMALIZED_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_schema_audit_{MODEL_TAG}.csv"
WINDOW_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_point_in_time_window_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_validator_status_{MODEL_TAG}.png"
REQUEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_ready_by_exchange_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predecision_coverage_distribution_{MODEL_TAG}.png"
LEAKAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_post_decision_tail_audit_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUIRED_NORMALIZED_COLUMNS = [
    "exchange",
    "vt_symbol",
    "bar_start_ts",
    "bar_end_ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
    "open_interest",
    "tick_count",
    "source_method",
]

REQUIRED_PROOF_FIELDS = [
    "request_id",
    "vendor_name",
    "vendor_license",
    "dataset_id",
    "query_params",
    "raw_file",
    "raw_sha256",
    "schema_hash",
    "normalization_version",
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


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>"))
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path, required=False)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if np.isnan(number) or np.isinf(number) else number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _resolve_path(path_text: Any) -> Path:
    path = Path(str(path_text))
    return path if path.is_absolute() else REPO_DIR / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _load_proof(path: Path) -> tuple[dict[str, Any], str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, repr(exc)[:500]


def _audit_requests(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in manifest.iterrows():
        raw_path = _resolve_path(row["expected_raw_file"])
        normalized_path = _resolve_path(row["expected_normalized_file"])
        proof_path = _resolve_path(row["expected_proof_file"])
        rows.append(
            {
                "request_id": row["request_id"],
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "decision_date": row["decision_date"],
                "expected_raw_file": row["expected_raw_file"],
                "expected_normalized_file": row["expected_normalized_file"],
                "expected_proof_file": row["expected_proof_file"],
                "raw_file_present": int(raw_path.exists()),
                "raw_file_size": raw_path.stat().st_size if raw_path.exists() else 0,
                "normalized_file_present": int(normalized_path.exists()),
                "proof_file_present": int(proof_path.exists()),
                "triplet_present": int(raw_path.exists() and normalized_path.exists() and proof_path.exists()),
            }
        )
    return pd.DataFrame(rows)


def _audit_proof(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in manifest.iterrows():
        raw_path = _resolve_path(row["expected_raw_file"])
        proof_path = _resolve_path(row["expected_proof_file"])
        proof, error = ({}, "missing_proof") if not proof_path.exists() else _load_proof(proof_path)
        missing = [field for field in REQUIRED_PROOF_FIELDS if field not in proof]
        raw_sha = _sha256(raw_path) if raw_path.exists() else ""
        identity_match = (
            str(proof.get("request_id", "")) == str(row["request_id"])
            and str(proof.get("exchange", "")) == str(row["exchange"])
            and str(proof.get("vt_symbol", "")) == str(row["vt_symbol"])
        )
        synthetic_clean = proof.get("synthetic_or_adjusted_flag") is False
        template_clean = proof.get("template_only_not_real_proof") is False
        rows.append(
            {
                "request_id": row["request_id"],
                "proof_path": str(proof_path.relative_to(REPO_DIR)) if proof_path.exists() else str(proof_path),
                "proof_file_present": int(proof_path.exists()),
                "proof_json_valid": int(bool(proof) and not error),
                "proof_required_field_count": len(REQUIRED_PROOF_FIELDS),
                "proof_required_field_present_count": len(REQUIRED_PROOF_FIELDS) - len(missing),
                "proof_missing_fields": ",".join(missing),
                "proof_raw_sha256_match": int(bool(raw_sha) and str(proof.get("raw_sha256", "")) == raw_sha),
                "proof_identity_match": int(identity_match),
                "proof_synthetic_or_adjusted_flag_clean": int(synthetic_clean),
                "proof_template_only_clean": int(template_clean),
                "proof_error": error,
            }
        )
    return pd.DataFrame(rows)


def _audit_normalized(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in manifest.iterrows():
        normalized_path = _resolve_path(row["expected_normalized_file"])
        row_count = 0
        present_cols: set[str] = set()
        error = ""
        if normalized_path.exists():
            try:
                frame = pd.read_parquet(normalized_path)
                row_count = int(len(frame))
                present_cols = set(frame.columns)
            except Exception as exc:
                error = repr(exc)[:500]
        missing_cols = [column for column in REQUIRED_NORMALIZED_COLUMNS if column not in present_cols]
        rows.append(
            {
                "request_id": row["request_id"],
                "normalized_path": str(normalized_path.relative_to(REPO_DIR)) if normalized_path.exists() else str(normalized_path),
                "normalized_file_present": int(normalized_path.exists()),
                "parquet_readable": int(normalized_path.exists() and not error),
                "row_count": row_count,
                "required_column_count": len(REQUIRED_NORMALIZED_COLUMNS),
                "required_column_present_count": len(REQUIRED_NORMALIZED_COLUMNS) - len(missing_cols),
                "missing_required_columns": ",".join(missing_cols),
                "normalized_schema_pass": int(normalized_path.exists() and not error and not missing_cols and row_count > 0),
                "schema_error": error,
            }
        )
    return pd.DataFrame(rows)


def _audit_windows(manifest: pd.DataFrame, extension_windows: pd.DataFrame) -> pd.DataFrame:
    normalized_cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    request_map = manifest.set_index("request_id").to_dict(orient="index")
    for _, window in extension_windows.iterrows():
        request_id = str(window["source_stage152_request_id"])
        # Stage177 extension windows carry the source Stage152 request id. Map via extension_window_ids when request ids differ.
        hit = manifest[manifest["extension_window_ids"].astype(str).str.contains(str(window["extension_window_id"]), regex=False)]
        stage177_request_id = str(hit.iloc[0]["request_id"]) if not hit.empty else request_id
        request = request_map.get(stage177_request_id)
        if not request:
            continue
        normalized_path = _resolve_path(request["expected_normalized_file"])
        if stage177_request_id not in normalized_cache:
            if normalized_path.exists():
                try:
                    bars = pd.read_parquet(normalized_path)
                    bars["bar_start_ts_dt"] = pd.to_datetime(bars["bar_start_ts"], errors="coerce")
                    bars["bar_end_ts_dt"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
                    normalized_cache[stage177_request_id] = bars
                except Exception:
                    normalized_cache[stage177_request_id] = pd.DataFrame()
            else:
                normalized_cache[stage177_request_id] = pd.DataFrame()
        bars = normalized_cache[stage177_request_id]
        start = pd.Timestamp(window["extension_start_ts"])
        decision_ts = pd.Timestamp(window["decision_ts"])
        target = int(window["target_min_predecision_closed_bars"])
        observed = pd.DataFrame()
        post_decision = pd.DataFrame()
        duplicate_count = 0
        positive_volume = 0
        if not bars.empty:
            same_symbol = bars["vt_symbol"].astype(str).eq(str(window["vt_symbol"]))
            observed = bars[same_symbol & bars["bar_end_ts_dt"].ge(start) & bars["bar_end_ts_dt"].le(decision_ts)].copy()
            post_decision = bars[same_symbol & bars["bar_end_ts_dt"].gt(decision_ts)].copy()
            duplicate_count = int(observed["bar_start_ts"].duplicated().sum()) if "bar_start_ts" in observed else 0
            positive_volume = int(pd.to_numeric(observed.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum())
        coverage_pass = int(len(observed) >= target and positive_volume >= 60 and duplicate_count == 0)
        direct_file_safe = int(coverage_pass == 1 and len(post_decision) == 0)
        filtered_ready = int(coverage_pass == 1)
        rows.append(
            {
                "request_id": stage177_request_id,
                "extension_window_id": window["extension_window_id"],
                "source_stage152_window_id": window["source_stage152_window_id"],
                "vt_symbol": window["vt_symbol"],
                "exchange": window["exchange"],
                "product": window["product"],
                "priority_class": window["priority_class"],
                "decision_ts": window["decision_ts"],
                "extension_start_ts": window["extension_start_ts"],
                "target_min_predecision_closed_bars": target,
                "observed_predecision_closed_bar_count": int(len(observed)),
                "positive_volume_bar_count": positive_volume,
                "duplicate_bar_count": duplicate_count,
                "post_decision_bar_count": int(len(post_decision)),
                "last_predecision_bar_end_ts": "" if observed.empty else pd.Timestamp(observed["bar_end_ts_dt"].max()).strftime("%Y-%m-%d %H:%M:%S"),
                "first_post_decision_bar_end_ts": "" if post_decision.empty else pd.Timestamp(post_decision["bar_end_ts_dt"].min()).strftime("%Y-%m-%d %H:%M:%S"),
                "cutoff_filtered_coverage_pass": coverage_pass,
                "filtered_feature_materialization_allowed": filtered_ready,
                "direct_normalized_file_feature_use_allowed": direct_file_safe,
                "feature_table_row_written": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _merge_request_ready(requests: pd.DataFrame, proofs: pd.DataFrame, normalized: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    frame = requests.merge(
        proofs[
            [
                "request_id",
                "proof_json_valid",
                "proof_raw_sha256_match",
                "proof_identity_match",
                "proof_synthetic_or_adjusted_flag_clean",
                "proof_template_only_clean",
            ]
        ],
        on="request_id",
        how="left",
    ).merge(normalized[["request_id", "normalized_schema_pass", "row_count"]], on="request_id", how="left")
    window_summary = (
        windows.groupby("request_id")
        .agg(
            point_in_time_window_count=("extension_window_id", "count"),
            cutoff_filtered_coverage_pass_count=("cutoff_filtered_coverage_pass", "sum"),
            filtered_feature_materialization_allowed_count=("filtered_feature_materialization_allowed", "sum"),
            direct_normalized_file_feature_use_allowed_count=("direct_normalized_file_feature_use_allowed", "sum"),
            post_decision_bar_count=("post_decision_bar_count", "sum"),
        )
        .reset_index()
    )
    frame = frame.merge(window_summary, on="request_id", how="left")
    for column in [
        "proof_json_valid",
        "proof_raw_sha256_match",
        "proof_identity_match",
        "proof_synthetic_or_adjusted_flag_clean",
        "proof_template_only_clean",
        "normalized_schema_pass",
        "point_in_time_window_count",
        "cutoff_filtered_coverage_pass_count",
        "filtered_feature_materialization_allowed_count",
        "direct_normalized_file_feature_use_allowed_count",
        "post_decision_bar_count",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    frame["stage179_filtered_ready"] = (
        frame["triplet_present"].eq(1)
        & frame["proof_json_valid"].eq(1)
        & frame["proof_raw_sha256_match"].eq(1)
        & frame["proof_identity_match"].eq(1)
        & frame["proof_synthetic_or_adjusted_flag_clean"].eq(1)
        & frame["proof_template_only_clean"].eq(1)
        & frame["normalized_schema_pass"].eq(1)
        & frame["point_in_time_window_count"].gt(0)
        & frame["cutoff_filtered_coverage_pass_count"].eq(frame["point_in_time_window_count"])
    ).astype(int)
    frame["stage179_direct_file_ready"] = (
        frame["stage179_filtered_ready"].eq(1)
        & frame["direct_normalized_file_feature_use_allowed_count"].eq(frame["point_in_time_window_count"])
    ).astype(int)
    return frame


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("stage177_manifest_loaded", summary["stage177_extension_request_count"], summary["stage177_extension_request_count"], "dependency_hard"),
        ("stage178_written_loaded", summary["stage178_delivery_success_count"], summary["stage178_delivery_success_count"], "dependency_hard"),
        ("present_triplet_count", summary["present_triplet_count"], summary["stage178_delivery_success_count"], "delivery_hard"),
        ("proof_hash_identity_schema_ready", summary["proof_hash_schema_identity_ready_count"], summary["stage178_delivery_success_count"], "lineage_hard"),
        ("cutoff_filtered_windows_ready", summary["cutoff_filtered_coverage_pass_count"], summary["present_window_count"], "point_in_time_hard"),
        ("direct_file_windows_safe", summary["direct_file_feature_use_allowed_count"], summary["present_window_count"], "leakage_hard"),
        ("filtered_feature_materialization_allowed", summary["filtered_request_ready_count"], summary["stage178_delivery_success_count"], "feature_source_soft"),
        ("feature_table_row_written", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
    ]
    rows = []
    for gate_id, observed, required, severity in gates:
        observed_int = int(observed)
        required_int = int(required)
        rows.append(
            {
                "gate_id": gate_id,
                "observed": observed_int,
                "required": required_int,
                "pass_now": int(observed_int == required_int),
                "severity": severity,
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, requests: pd.DataFrame, proofs: pd.DataFrame, normalized: pd.DataFrame, windows: pd.DataFrame, gate: pd.DataFrame) -> None:
    lines = [
        "# Stage179 Predecision Lookback Point-in-Time Validator",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- This stage validates Stage177/178 lookback delivery. It writes no feature table and creates no strategy rule.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Request File Audit",
        "",
        _md_table(
            requests[
                [
                    "request_id",
                    "exchange",
                    "vt_symbol",
                    "triplet_present",
                    "stage179_filtered_ready",
                    "stage179_direct_file_ready",
                    "post_decision_bar_count",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## Proof Audit Sample",
        "",
        _md_table(proofs[proofs["proof_file_present"].eq(1)], max_rows=20),
        "",
        "## Normalized Audit Sample",
        "",
        _md_table(normalized[normalized["normalized_file_present"].eq(1)], max_rows=20),
        "",
        "## Point-in-Time Window Audit",
        "",
        _md_table(windows[windows["filtered_feature_materialization_allowed"].eq(1)], max_rows=30),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_title("Official path unchanged; Stage179 validates predecision lookback delivery")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["triplets", "filtered ready", "direct safe", "feature rows"]
    values = [
        summary["present_triplet_count"],
        summary["filtered_request_ready_count"],
        summary["direct_file_request_ready_count"],
        summary["feature_table_row_written_count"],
    ]
    axes[3].bar(labels, values, color=["#3657D6", "#0F766E", "#B45309", "#111827"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_requests(requests: pd.DataFrame) -> None:
    present = requests[requests["triplet_present"].eq(1)].copy()
    grouped = (
        present.groupby("exchange")
        .agg(
            triplets=("request_id", "count"),
            filtered_ready=("stage179_filtered_ready", "sum"),
            direct_ready=("stage179_direct_file_ready", "sum"),
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(12, 5.5))
    if grouped.empty:
        ax.text(0.5, 0.5, "No present triplets", ha="center", va="center")
        ax.axis("off")
    else:
        x = np.arange(len(grouped.index))
        width = 0.25
        for idx, col in enumerate(["triplets", "filtered_ready", "direct_ready"]):
            ax.bar(x + (idx - 1) * width, grouped[col], width=width, label=col)
        ax.set_xticks(x)
        ax.set_xticklabels(grouped.index)
        ax.set_title("Stage179 request readiness by exchange")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(REQUEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_coverage(windows: pd.DataFrame) -> None:
    present = windows[windows["observed_predecision_closed_bar_count"].gt(0)].copy()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    if present.empty:
        ax.text(0.5, 0.5, "No present windows", ha="center", va="center")
        ax.axis("off")
    else:
        x = np.arange(len(present))
        ax.bar(x, present["observed_predecision_closed_bar_count"], color="#0F766E", label="observed")
        ax.axhline(61, color="#991B1B", linestyle="--", linewidth=1.0, label="target 61")
        ax.set_xticks(x)
        ax.set_xticklabels(present["request_id"].tolist(), rotation=25, ha="right", fontsize=8)
        ax.set_title("Predecision closed-bar coverage for present Stage177 requests")
        ax.set_ylabel("closed 1m bars")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_leakage(windows: pd.DataFrame) -> None:
    present = windows[windows["observed_predecision_closed_bar_count"].gt(0)].copy()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    if present.empty:
        ax.text(0.5, 0.5, "No present windows", ha="center", va="center")
        ax.axis("off")
    else:
        x = np.arange(len(present))
        ax.bar(x, present["post_decision_bar_count"], color="#B45309", label="post-decision bars in normalized file")
        ax.set_xticks(x)
        ax.set_xticklabels(present["request_id"].tolist(), rotation=25, ha="right", fontsize=8)
        ax.set_title("Direct normalized-file leakage tail audit")
        ax.set_ylabel("bars after decision_ts")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(LEAKAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, max(5.5, len(gate) * 0.45)))
    matrix = gate.set_index("gate_id")[["pass_now"]]
    data = matrix.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage179 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for r in range(data.shape[0]):
        ax.text(0, r, int(data[r, 0]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    stage177 = _row(STAGE177_SUMMARY_IN)
    stage178 = _row(STAGE178_SUMMARY_IN)
    manifest = _read_csv(STAGE177_REQUEST_MANIFEST_IN)
    extension_windows = _read_csv(STAGE177_EXTENSION_WINDOWS_IN)
    request_file = _audit_requests(manifest)
    proof = _audit_proof(manifest)
    normalized = _audit_normalized(manifest)
    windows = _audit_windows(manifest, extension_windows)
    request_ready = _merge_request_ready(request_file, proof, normalized, windows)

    present_window_count = int(windows["observed_predecision_closed_bar_count"].gt(0).sum()) if not windows.empty else 0
    proof_ready = request_ready[
        request_ready["proof_json_valid"].eq(1)
        & request_ready["proof_raw_sha256_match"].eq(1)
        & request_ready["proof_identity_match"].eq(1)
        & request_ready["proof_synthetic_or_adjusted_flag_clean"].eq(1)
        & request_ready["proof_template_only_clean"].eq(1)
        & request_ready["normalized_schema_pass"].eq(1)
    ]
    direct_safe_count = int(request_ready["stage179_direct_file_ready"].sum())
    filtered_ready_count = int(request_ready["stage179_filtered_ready"].sum())
    post_decision_total = int(windows["post_decision_bar_count"].sum()) if not windows.empty else 0
    if filtered_ready_count > 0 and direct_safe_count < filtered_ready_count:
        decision = "stage179_point_in_time_validator_accepts_filtered_requests_blocks_direct_file_use_no_rule"
        next_best_action = "stage180_build_cutoff_filtered_feature_source_or_patch_stage178_end_exclusive_before_feature_table"
    elif filtered_ready_count > 0:
        decision = "stage179_point_in_time_validator_accepts_direct_requests_wait_feature_table_gate_no_rule"
        next_best_action = "stage180_cutoff_filtered_feature_source_then_feature_lineage"
    else:
        decision = "stage179_point_in_time_validator_blocks_stage178_delivery_no_rule"
        next_best_action = "repair_stage178_delivery_or_source_route_before_feature_table"

    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": next_best_action,
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage177_extension_request_count": _int(stage177, "extension_request_count"),
        "stage177_entry_window_count": _int(stage177, "entry_window_count"),
        "stage178_delivery_success_count": _int(stage178, "delivery_success_count"),
        "request_count": int(len(manifest)),
        "present_triplet_count": int(request_ready["triplet_present"].sum()),
        "raw_file_present_count": int(request_ready["raw_file_present"].sum()),
        "normalized_file_present_count": int(request_ready["normalized_file_present"].sum()),
        "proof_file_present_count": int(request_ready["proof_file_present"].sum()),
        "proof_hash_schema_identity_ready_count": int(len(proof_ready)),
        "present_window_count": present_window_count,
        "cutoff_filtered_coverage_pass_count": int(windows["cutoff_filtered_coverage_pass"].sum()) if not windows.empty else 0,
        "filtered_request_ready_count": filtered_ready_count,
        "filtered_feature_materialization_allowed_count": filtered_ready_count,
        "direct_file_request_ready_count": direct_safe_count,
        "direct_file_feature_use_allowed_count": int(windows["direct_normalized_file_feature_use_allowed"].sum()) if not windows.empty else 0,
        "post_decision_bar_count": post_decision_total,
        "max_observed_predecision_closed_bar_count": int(windows["observed_predecision_closed_bar_count"].max()) if not windows.empty else 0,
        "min_observed_predecision_closed_bar_count": int(windows.loc[windows["observed_predecision_closed_bar_count"].gt(0), "observed_predecision_closed_bar_count"].min()) if present_window_count else 0,
        "target_min_predecision_closed_bars": int(extension_windows["target_min_predecision_closed_bars"].max()) if not extension_windows.empty else 61,
        "feature_cutoff_rule": "bar_end_ts <= decision_ts",
        "feature_table_row_written_count": 0,
        "feature_table_file_written": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage178.get("end_equity", np.nan)),
        "total_return_pct": float(stage178.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage178.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage178.get("sharpe", np.nan)),
        "total_slippage": float(stage178.get("total_slippage", np.nan)),
        "total_trade_count": float(stage178.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage178.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage178.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(request_ready, REQUEST_AUDIT_OUT)
    _write_csv(proof, PROOF_AUDIT_OUT)
    _write_csv(normalized, NORMALIZED_AUDIT_OUT)
    _write_csv(windows, WINDOW_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, request_ready, proof, normalized, windows, gate)
    _plot_path(curve, summary_dict)
    _plot_requests(request_ready)
    _plot_coverage(windows)
    _plot_leakage(windows)
    _plot_gate(gate)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "summary": summary_dict,
            "inputs": {
                "stage177_summary": str(STAGE177_SUMMARY_IN),
                "stage177_request_manifest": str(STAGE177_REQUEST_MANIFEST_IN),
                "stage177_extension_window_contract": str(STAGE177_EXTENSION_WINDOWS_IN),
                "stage178_summary": str(STAGE178_SUMMARY_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "request_file_audit": str(REQUEST_AUDIT_OUT),
                "proof_json_audit": str(PROOF_AUDIT_OUT),
                "normalized_schema_audit": str(NORMALIZED_AUDIT_OUT),
                "point_in_time_window_audit": str(WINDOW_AUDIT_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(REQUEST_CHART_OUT), str(COVERAGE_CHART_OUT), str(LEAKAGE_CHART_OUT), str(GATE_CHART_OUT)],
            },
            "locks": {
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
                "feature_table_row_written_count": 0,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "current_package_promotion_allowed": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary_dict), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
