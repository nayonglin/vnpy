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
STAGE = "Stage180"
MODEL_TAG = "stage180_cutoff_filtered_predecision_feature_source_v1"
OUTPUT_PREFIX = "qmt_roll_stage180_c9_minrisk_cutoff_filtered_predecision_feature_source"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage180_cutoff_filtered_predecision_feature_source"
FILTERED_SOURCE_DIR = OUTPUT_DIR / "filtered_sources"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE179_DIR = LINE_DIR / "outputs" / "stage179_predecision_lookback_point_in_time_validator"
STAGE179_PREFIX = "qmt_roll_stage179_c9_minrisk_predecision_lookback_point_in_time_validator"
STAGE179_TAG = "stage179_predecision_lookback_point_in_time_validator_v1"
STAGE179_SUMMARY_IN = STAGE179_DIR / f"{STAGE179_PREFIX}_summary_{STAGE179_TAG}.csv"
STAGE179_REQUEST_AUDIT_IN = STAGE179_DIR / f"{STAGE179_PREFIX}_request_file_audit_{STAGE179_TAG}.csv"
STAGE179_WINDOW_AUDIT_IN = STAGE179_DIR / f"{STAGE179_PREFIX}_point_in_time_window_audit_{STAGE179_TAG}.csv"

STAGE177_DIR = LINE_DIR / "outputs" / "stage177_predecision_lookback_extension_manifest"
STAGE177_PREFIX = "qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest"
STAGE177_TAG = "stage177_predecision_lookback_extension_manifest_v1"
STAGE177_REQUEST_MANIFEST_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_request_manifest_{STAGE177_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SOURCE_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_filtered_source_manifest_{MODEL_TAG}.csv"
LINEAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_filtered_source_lineage_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_status_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_filtered_rows_by_request_{MODEL_TAG}.png"
TAIL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_post_decision_tail_removed_{MODEL_TAG}.png"
LINEAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_matrix_{MODEL_TAG}.png"
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


def _build_sources(requests179: pd.DataFrame, windows179: pd.DataFrame, manifest177: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ready = requests179[requests179["stage179_filtered_ready"].eq(1)].copy()
    manifest_by_request = manifest177.set_index("request_id").to_dict(orient="index")
    window_by_request = windows179.set_index("request_id").to_dict(orient="index")
    manifest_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    for _, request in ready.sort_values(["exchange", "request_id"]).iterrows():
        request_id = str(request["request_id"])
        manifest = manifest_by_request[request_id]
        window = window_by_request[request_id]
        source_path = _resolve_path(manifest["expected_normalized_file"])
        source_sha = _sha256(source_path)
        bars = pd.read_parquet(source_path)
        bars["bar_start_ts_dt"] = pd.to_datetime(bars["bar_start_ts"], errors="coerce")
        bars["bar_end_ts_dt"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
        decision_ts = pd.Timestamp(window["decision_ts"])
        start_ts = pd.Timestamp(window["extension_start_ts"])
        same_symbol = bars["vt_symbol"].astype(str).eq(str(window["vt_symbol"]))
        filtered = bars[
            same_symbol
            & bars["bar_end_ts_dt"].ge(start_ts)
            & bars["bar_end_ts_dt"].le(decision_ts)
        ].copy()
        post_decision = bars[same_symbol & bars["bar_end_ts_dt"].gt(decision_ts)].copy()
        filtered = filtered.sort_values("bar_end_ts_dt").reset_index(drop=True)
        filtered["stage180_filter_model_tag"] = MODEL_TAG
        filtered["stage180_request_id"] = request_id
        filtered["stage180_extension_window_id"] = window["extension_window_id"]
        filtered["stage180_decision_ts"] = pd.Timestamp(decision_ts).strftime("%Y-%m-%d %H:%M:%S")
        filtered["stage180_feature_cutoff_rule"] = "bar_end_ts <= decision_ts"
        filtered = filtered.drop(columns=["bar_start_ts_dt", "bar_end_ts_dt"], errors="ignore")
        target_name = f"{request_id}.cutoff_filtered_predecision.parquet"
        target_path = FILTERED_SOURCE_DIR / str(request["exchange"]) / str(request["vt_symbol"]).replace(".", "_") / target_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        filtered.to_parquet(target_path, index=False)
        target_sha = _sha256(target_path)
        positive_volume = int(pd.to_numeric(filtered["volume"], errors="coerce").fillna(0).gt(0).sum()) if not filtered.empty else 0
        duplicate_count = int(filtered["bar_start_ts"].duplicated().sum()) if not filtered.empty else 0
        row_count = int(len(filtered))
        pass_now = int(row_count >= int(window["target_min_predecision_closed_bars"]) and positive_volume >= 60 and duplicate_count == 0)
        manifest_rows.append(
            {
                "request_id": request_id,
                "extension_window_id": window["extension_window_id"],
                "exchange": request["exchange"],
                "product": request["product"],
                "vt_symbol": request["vt_symbol"],
                "priority_class": window["priority_class"],
                "decision_ts": window["decision_ts"],
                "extension_start_ts": window["extension_start_ts"],
                "target_min_predecision_closed_bars": int(window["target_min_predecision_closed_bars"]),
                "source_normalized_file": manifest["expected_normalized_file"],
                "source_normalized_sha256": source_sha,
                "filtered_source_file": str(target_path.relative_to(REPO_DIR)),
                "filtered_source_sha256": target_sha,
                "filtered_row_count": row_count,
                "filtered_positive_volume_row_count": positive_volume,
                "filtered_duplicate_bar_count": duplicate_count,
                "post_decision_removed_count": int(len(post_decision)),
                "last_filtered_bar_end_ts": "" if filtered.empty else str(filtered["bar_end_ts"].max()),
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
                "cutoff_filtered_source_ready": pass_now,
                "feature_table_row_written": 0,
                "strategy_rule_allowed": 0,
            }
        )
        lineage_rows.append(
            {
                "request_id": request_id,
                "extension_window_id": window["extension_window_id"],
                "source_stage": "Stage178",
                "validator_stage": "Stage179",
                "filter_stage": STAGE,
                "source_normalized_file": manifest["expected_normalized_file"],
                "source_normalized_sha256": source_sha,
                "filtered_source_file": str(target_path.relative_to(REPO_DIR)),
                "filtered_source_sha256": target_sha,
                "decision_ts": window["decision_ts"],
                "filter_expression": "same vt_symbol AND extension_start_ts <= bar_end_ts <= decision_ts",
                "rows_before_filter": int(len(bars)),
                "rows_after_filter": row_count,
                "post_decision_removed_count": int(len(post_decision)),
                "lineage_pass": pass_now,
                "feature_table_row_written": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(manifest_rows), pd.DataFrame(lineage_rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage179_filtered_ready_loaded", summary["stage179_filtered_request_ready_count"], summary["stage179_filtered_request_ready_count"], "dependency_hard"),
        ("filtered_source_written", summary["filtered_source_written_count"], summary["stage179_filtered_request_ready_count"], "source_hard"),
        ("filtered_source_ready", summary["cutoff_filtered_source_ready_count"], summary["stage179_filtered_request_ready_count"], "point_in_time_hard"),
        ("post_decision_tail_removed_or_absent", summary["post_decision_removed_count"], summary["stage179_post_decision_bar_count"], "leakage_hard"),
        ("lineage_pass", summary["lineage_pass_count"], summary["stage179_filtered_request_ready_count"], "lineage_hard"),
        ("feature_table_row_written", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
    ]
    records = []
    for gate_id, observed, required, severity in rows:
        records.append(
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
        )
    return pd.DataFrame(records)


def _write_report(summary: pd.DataFrame, manifest: pd.DataFrame, lineage: pd.DataFrame, gate: pd.DataFrame) -> None:
    lines = [
        "# Stage180 Cutoff-Filtered Predecision Feature Source",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- This stage writes cutoff-filtered source bars only. It writes no feature table and creates no strategy rule.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Filtered Source Manifest",
        "",
        _md_table(manifest),
        "",
        "## Lineage",
        "",
        _md_table(lineage),
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
    axes[0].set_title("Official path unchanged; Stage180 builds cutoff-filtered source")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["filtered ready", "source written", "tail removed", "feature rows"]
    values = [
        summary["stage179_filtered_request_ready_count"],
        summary["filtered_source_written_count"],
        summary["post_decision_removed_count"],
        summary["feature_table_row_written_count"],
    ]
    axes[3].bar(labels, values, color=["#3657D6", "#0F766E", "#B45309", "#111827"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_sources(manifest: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    if manifest.empty:
        ax.text(0.5, 0.5, "No filtered sources", ha="center", va="center")
        ax.axis("off")
    else:
        x = np.arange(len(manifest))
        ax.bar(x, manifest["filtered_row_count"], color="#0F766E")
        ax.axhline(61, color="#991B1B", linestyle="--", linewidth=1.0)
        ax.set_xticks(x)
        ax.set_xticklabels(manifest["request_id"].tolist(), rotation=25, ha="right", fontsize=8)
        ax.set_title("Cutoff-filtered predecision source rows")
        ax.set_ylabel("rows")
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SOURCE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_tail(manifest: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    if manifest.empty:
        ax.text(0.5, 0.5, "No filtered sources", ha="center", va="center")
        ax.axis("off")
    else:
        x = np.arange(len(manifest))
        ax.bar(x, manifest["post_decision_removed_count"], color="#B45309")
        ax.set_xticks(x)
        ax.set_xticklabels(manifest["request_id"].tolist(), rotation=25, ha="right", fontsize=8)
        ax.set_title("Post-decision bars removed before feature source")
        ax.set_ylabel("removed bars")
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(TAIL_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_lineage(lineage: pd.DataFrame) -> None:
    cols = ["lineage_pass", "feature_table_row_written", "strategy_rule_allowed"]
    fig, ax = plt.subplots(figsize=(9, max(4.5, len(lineage) * 0.55)))
    matrix = lineage[cols].to_numpy(dtype=float) if not lineage.empty else np.zeros((1, len(cols)))
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(lineage)))
    ax.set_yticklabels(lineage["request_id"].tolist() if not lineage.empty else ["none"], fontsize=8)
    ax.set_title("Stage180 lineage matrix")
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            ax.text(c, r, int(matrix[r, c]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(LINEAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, max(5.5, len(gate) * 0.45)))
    matrix = gate.set_index("gate_id")[["pass_now"]]
    data = matrix.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage180 gate status")
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
    FILTERED_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    stage179 = _row(STAGE179_SUMMARY_IN)
    requests179 = _read_csv(STAGE179_REQUEST_AUDIT_IN)
    windows179 = _read_csv(STAGE179_WINDOW_AUDIT_IN)
    manifest177 = _read_csv(STAGE177_REQUEST_MANIFEST_IN)
    source_manifest, lineage = _build_sources(requests179, windows179, manifest177)
    decision = "stage180_cutoff_filtered_predecision_source_ready_no_feature_table_no_rule"
    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "stage181_materialize_stage156_features_on_cutoff_filtered_sources_with_lineage_no_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage179_filtered_request_ready_count": _int(stage179, "filtered_request_ready_count"),
        "stage179_direct_file_request_ready_count": _int(stage179, "direct_file_request_ready_count"),
        "stage179_post_decision_bar_count": _int(stage179, "post_decision_bar_count"),
        "filtered_source_written_count": int(len(source_manifest)),
        "cutoff_filtered_source_ready_count": int(source_manifest["cutoff_filtered_source_ready"].sum()) if not source_manifest.empty else 0,
        "filtered_source_row_count": int(source_manifest["filtered_row_count"].sum()) if not source_manifest.empty else 0,
        "filtered_positive_volume_row_count": int(source_manifest["filtered_positive_volume_row_count"].sum()) if not source_manifest.empty else 0,
        "post_decision_removed_count": int(source_manifest["post_decision_removed_count"].sum()) if not source_manifest.empty else 0,
        "lineage_pass_count": int(lineage["lineage_pass"].sum()) if not lineage.empty else 0,
        "feature_table_row_written_count": 0,
        "feature_table_file_written": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage179.get("end_equity", np.nan)),
        "total_return_pct": float(stage179.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage179.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage179.get("sharpe", np.nan)),
        "total_slippage": float(stage179.get("total_slippage", np.nan)),
        "total_trade_count": float(stage179.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage179.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage179.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(source_manifest, SOURCE_MANIFEST_OUT)
    _write_csv(lineage, LINEAGE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, source_manifest, lineage, gate)
    _plot_path(curve, summary_dict)
    _plot_sources(source_manifest)
    _plot_tail(source_manifest)
    _plot_lineage(lineage)
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
                "stage179_summary": str(STAGE179_SUMMARY_IN),
                "stage179_request_audit": str(STAGE179_REQUEST_AUDIT_IN),
                "stage179_window_audit": str(STAGE179_WINDOW_AUDIT_IN),
                "stage177_request_manifest": str(STAGE177_REQUEST_MANIFEST_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "filtered_source_manifest": str(SOURCE_MANIFEST_OUT),
                "filtered_source_lineage": str(LINEAGE_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "filtered_sources_dir": str(FILTERED_SOURCE_DIR),
                "charts": [str(PATH_CHART_OUT), str(SOURCE_CHART_OUT), str(TAIL_CHART_OUT), str(LINEAGE_CHART_OUT), str(GATE_CHART_OUT)],
            },
            "locks": {
                "feature_cutoff_rule": "same vt_symbol AND extension_start_ts <= bar_end_ts <= decision_ts",
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
