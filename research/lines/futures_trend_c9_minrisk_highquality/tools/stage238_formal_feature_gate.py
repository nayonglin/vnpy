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
STAGE = "Stage238"
MODEL_TAG = "stage238_formal_feature_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage238_c9_minrisk_formal_feature_gate"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage238_formal_feature_gate"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE156_DIR = LINE_DIR / "outputs" / "stage156_authoritative_minute_feature_prebuild_gate"
STAGE156_PREFIX = "qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate"
STAGE156_TAG = "stage156_authoritative_minute_feature_prebuild_gate_v1"
STAGE156_FEATURE_CONTRACT_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_feature_contract_{STAGE156_TAG}.csv"

STAGE181_DIR = LINE_DIR / "outputs" / "stage181_cutoff_filtered_minute_feature_materializer"
STAGE181_PREFIX = "qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer"
STAGE181_TAG = "stage181_cutoff_filtered_minute_feature_materializer_v1"
STAGE181_SUMMARY_IN = STAGE181_DIR / f"{STAGE181_PREFIX}_summary_{STAGE181_TAG}.csv"
STAGE181_VALUE_IN = STAGE181_DIR / f"{STAGE181_PREFIX}_feature_value_audit_{STAGE181_TAG}.csv"
STAGE181_READINESS_IN = STAGE181_DIR / f"{STAGE181_PREFIX}_feature_readiness_audit_{STAGE181_TAG}.csv"
STAGE181_FORMULA_IN = STAGE181_DIR / f"{STAGE181_PREFIX}_formula_implementation_audit_{STAGE181_TAG}.csv"
STAGE181_LINEAGE_IN = STAGE181_DIR / f"{STAGE181_PREFIX}_lineage_audit_{STAGE181_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FORMAL_TABLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_formal_feature_table_{MODEL_TAG}.parquet"
FORMAL_TABLE_CSV_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_formal_feature_table_{MODEL_TAG}.csv"
FEATURE_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_gate_audit_{MODEL_TAG}.csv"
ROW_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_row_gate_audit_{MODEL_TAG}.csv"
NORMALIZATION_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalization_contract_{MODEL_TAG}.csv"
DISTRIBUTION_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_distribution_audit_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_formal_gate_status_{MODEL_TAG}.png"
ROW_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_formal_row_gate_matrix_{MODEL_TAG}.png"
FEATURE_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_gate_matrix_{MODEL_TAG}.png"
CANDIDATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_feature_audit_heatmap_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_role_counts_{MODEL_TAG}.png"

STRATEGY_CANDIDATE_FEATURES = {
    "bar_return_1m": "direction_context",
    "range_ratio_1m": "risk_noise_floor",
    "directional_efficiency_30m": "trend_persistence",
    "realized_volatility_30m": "risk_budget_denominator",
    "volume_participation_30m": "participation_quality",
    "volume_zscore_60m": "participation_surprise",
    "turnover_vwap_gap_30m": "execution_pressure",
}

DIAGNOSTIC_ONLY_FEATURES = {
    "true_range_median_30m": "price_scale_dependent_until_ratio_normalized",
    "open_interest_delta_60m": "contract_scale_dependent_until_oi_base_normalized",
    "closed_bar_count_coverage": "data_quality_gate_not_alpha",
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
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _feature_hash(row: pd.Series, feature_ids: list[str]) -> str:
    payload = {
        feature_id: None if pd.isna(row.get(f"candidate_{feature_id}")) else float(row.get(f"candidate_{feature_id}"))
        for feature_id in feature_ids
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _diagnostic_robust_z(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    median = float(values.median()) if values.notna().any() else 0.0
    q75 = float(values.quantile(0.75)) if values.notna().any() else 0.0
    q25 = float(values.quantile(0.25)) if values.notna().any() else 0.0
    iqr = q75 - q25
    if not np.isfinite(iqr) or iqr == 0:
        return pd.Series(0.0, index=series.index)
    return ((values - median) / iqr).clip(-5, 5).fillna(0.0)


def _build_feature_gate(contract: pd.DataFrame, readiness: pd.DataFrame, formula: pd.DataFrame) -> pd.DataFrame:
    ready = readiness.groupby("feature_id", dropna=False).agg(
        ready_request_count=("feature_ready", "sum"),
        finite_value_count=("feature_value", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
        future_data_allowed_sum=("future_data_allowed", "sum"),
        strategy_rule_allowed_sum=("strategy_rule_allowed", "sum"),
    )
    formula_by_id = formula.set_index("feature_id", drop=False)
    records: list[dict[str, Any]] = []
    for _, feature in contract.iterrows():
        feature_id = str(feature["feature_id"])
        ready_row = ready.loc[feature_id] if feature_id in ready.index else pd.Series(dtype=float)
        formula_row = formula_by_id.loc[feature_id] if feature_id in formula_by_id.index else pd.Series(dtype=object)
        strategy_candidate = int(feature_id in STRATEGY_CANDIDATE_FEATURES)
        diagnostic_only = int(feature_id in DIAGNOSTIC_ONLY_FEATURES)
        ready_count = int(ready_row.get("ready_request_count", 0))
        finite_count = int(ready_row.get("finite_value_count", 0))
        no_label = int(feature.get("contains_final_pnl_label", 1) == 0 and formula_row.get("contains_final_pnl_label", 1) == 0)
        no_patch = int(
            feature.get("contains_product_or_year_patch", 1) == 0
            and formula_row.get("contains_product_or_year_patch", 1) == 0
        )
        no_future = int(ready_row.get("future_data_allowed_sum", 1) == 0)
        no_rule = int(ready_row.get("strategy_rule_allowed_sum", 1) == 0)
        formal_pass = int(ready_count == 219 and finite_count == 219 and no_label and no_patch and no_future and no_rule)
        strategy_candidate_allowed_now = int(formal_pass and strategy_candidate)
        block_reason = ""
        if not formal_pass:
            block_reason = "readiness_or_provenance_gate_failed"
        elif diagnostic_only:
            block_reason = DIAGNOSTIC_ONLY_FEATURES[feature_id]
        records.append(
            {
                "feature_id": feature_id,
                "family": feature["family"],
                "economic_role": feature["economic_role"],
                "formal_feature_table_admitted": formal_pass,
                "strategy_candidate_allowed_now": strategy_candidate_allowed_now,
                "diagnostic_only": diagnostic_only,
                "candidate_role": STRATEGY_CANDIDATE_FEATURES.get(feature_id, ""),
                "ready_request_count": ready_count,
                "finite_value_count": finite_count,
                "required_request_count": 219,
                "no_future_data": no_future,
                "no_final_pnl_label": no_label,
                "no_product_or_year_patch": no_patch,
                "no_strategy_rule_side_effect": no_rule,
                "threshold_frozen_in_contract": int(feature["threshold_frozen"]),
                "strategy_rule_allowed": 0,
                "true_engine_allowed": 0,
                "ab_allowed": 0,
                "block_reason": block_reason,
            }
        )
    return pd.DataFrame(records)


def _build_formal_table(values: pd.DataFrame, lineage: pd.DataFrame, feature_gate: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_ids = feature_gate["feature_id"].astype(str).tolist()
    candidate_ids = feature_gate.loc[feature_gate["strategy_candidate_allowed_now"].eq(1), "feature_id"].astype(str).tolist()
    diagnostic_ids = feature_gate.loc[feature_gate["diagnostic_only"].eq(1), "feature_id"].astype(str).tolist()
    lineage_view = lineage[
        [
            "request_id",
            "lineage_pass",
            "source_cutoff_rule",
            "cutoff_guard_pass",
            "duplicate_bar_count",
            "observed_closed_bars",
            "formal_feature_table_row_written",
            "strategy_rule_allowed",
        ]
    ].copy()
    data = values.merge(lineage_view, on="request_id", how="left", suffixes=("", "_lineage"))
    rows: list[dict[str, Any]] = []
    row_gate_rows: list[dict[str, Any]] = []
    for _, row in data.sort_values(["exchange", "product", "decision_ts", "request_id"]).iterrows():
        all_feature_ready = int(all(int(row.get(f"{feature_id}__ready", 0)) == 1 for feature_id in feature_ids))
        candidate_ready_count = int(sum(int(row.get(f"{feature_id}__ready", 0)) for feature_id in candidate_ids))
        diagnostic_ready_count = int(sum(int(row.get(f"{feature_id}__ready", 0)) for feature_id in diagnostic_ids))
        cutoff_pass = int(row.get("cutoff_guard_pass", 0))
        lineage_pass = int(row.get("lineage_pass", 0))
        duplicate_bar_count = int(row.get("duplicate_bar_count", 0))
        formal_row_ready = int(
            cutoff_pass == 1
            and lineage_pass == 1
            and duplicate_bar_count == 0
            and all_feature_ready == 1
            and candidate_ready_count == len(candidate_ids)
            and diagnostic_ready_count == len(diagnostic_ids)
        )
        formal_row = {
            "request_id": row["request_id"],
            "extension_window_id": row["extension_window_id"],
            "exchange": row["exchange"],
            "product": row["product"],
            "vt_symbol": row["vt_symbol"],
            "decision_ts": row["decision_ts"],
            "feature_cutoff_ts": row["feature_cutoff_ts"],
            "source_cutoff_rule": row["source_cutoff_rule"],
            "filtered_source_file": row["filtered_source_file"],
            "filtered_source_sha256": row["filtered_source_sha256"],
            "observed_closed_bars": int(row["observed_closed_bars"]),
            "nonzero_volume_count": int(row["nonzero_volume_count"]),
            "duplicate_bar_count": duplicate_bar_count,
            "cutoff_guard_pass": cutoff_pass,
            "lineage_pass": lineage_pass,
            "all_feature_ready": all_feature_ready,
            "candidate_ready_count": candidate_ready_count,
            "candidate_feature_count": len(candidate_ids),
            "diagnostic_ready_count": diagnostic_ready_count,
            "diagnostic_feature_count": len(diagnostic_ids),
            "formal_row_ready": formal_row_ready,
            "formal_feature_table_row_written": 1,
            "strategy_feature_usable": 0,
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
        }
        for feature_id in feature_ids:
            formal_row[f"raw_{feature_id}"] = row[feature_id]
            formal_row[f"raw_{feature_id}__ready"] = int(row[f"{feature_id}__ready"])
        for feature_id in candidate_ids:
            formal_row[f"candidate_{feature_id}"] = row[feature_id]
        for feature_id in diagnostic_ids:
            formal_row[f"diagnostic_{feature_id}"] = row[feature_id]
        formal_row["candidate_feature_vector_sha256"] = _feature_hash(pd.Series(formal_row), candidate_ids)
        rows.append(formal_row)
        row_gate_rows.append(
            {
                "request_id": row["request_id"],
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "decision_ts": row["decision_ts"],
                "cutoff_guard_pass": cutoff_pass,
                "lineage_pass": lineage_pass,
                "duplicate_bar_count": duplicate_bar_count,
                "all_feature_ready": all_feature_ready,
                "candidate_ready_count": candidate_ready_count,
                "candidate_feature_count": len(candidate_ids),
                "diagnostic_ready_count": diagnostic_ready_count,
                "diagnostic_feature_count": len(diagnostic_ids),
                "formal_row_ready": formal_row_ready,
                "strategy_feature_usable": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(row_gate_rows)


def _normalization_contract(feature_gate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, feature in feature_gate.iterrows():
        feature_id = str(feature["feature_id"])
        strategy_allowed = int(feature["strategy_candidate_allowed_now"])
        rows.append(
            {
                "feature_id": feature_id,
                "strategy_candidate_allowed_now": strategy_allowed,
                "diagnostic_only": int(feature["diagnostic_only"]),
                "production_transform": "identity_in_natural_dimensionless_units" if strategy_allowed else "blocked_from_strategy_candidate",
                "full_sample_fitted_scale_allowed": 0,
                "label_aware_scale_allowed": 0,
                "future_distribution_fit_allowed": 0,
                "diagnostic_robust_z_for_chart_only": int(strategy_allowed),
                "chart_transform": "median_iqr_robust_z_clipped_5_for_visual_only" if strategy_allowed else "not_plotted_as_candidate",
                "reason": feature["block_reason"],
            }
        )
    return pd.DataFrame(rows)


def _distribution_audit(formal: pd.DataFrame, feature_gate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, feature in feature_gate.iterrows():
        feature_id = str(feature["feature_id"])
        series = pd.to_numeric(formal[f"raw_{feature_id}"], errors="coerce")
        rows.append(
            {
                "feature_id": feature_id,
                "strategy_candidate_allowed_now": int(feature["strategy_candidate_allowed_now"]),
                "diagnostic_only": int(feature["diagnostic_only"]),
                "count": int(series.notna().sum()),
                "min": float(series.min()),
                "p05": float(series.quantile(0.05)),
                "median": float(series.median()),
                "p95": float(series.quantile(0.95)),
                "max": float(series.max()),
                "distribution_used_for_strategy": 0,
                "distribution_used_for_visual_audit": int(feature["strategy_candidate_allowed_now"]),
            }
        )
    return pd.DataFrame(rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("stage181_audit_rows_loaded", summary["stage181_feature_audit_row_written_count"], 219, "dependency_hard"),
        ("stage181_ready_cells_loaded", summary["stage181_feature_ready_cell_count"], 2190, "dependency_hard"),
        ("formal_feature_table_rows", summary["formal_feature_table_row_written_count"], 219, "formal_gate_hard"),
        ("formal_row_ready_count", summary["formal_row_ready_count"], 219, "formal_gate_hard"),
        ("feature_gate_admitted_count", summary["formal_feature_admitted_count"], 10, "feature_gate_hard"),
        ("strategy_candidate_feature_count", summary["strategy_candidate_feature_count"], 7, "strategy_gate_hard"),
        ("diagnostic_only_feature_count", summary["diagnostic_only_feature_count"], 3, "strategy_gate_hard"),
        ("strategy_feature_usable", summary["strategy_feature_usable"], 0, "strategy_lock_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_lock_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_lock_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_lock_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_lock_hard"),
        ("official_config_changed", summary["official_config_changed"], 0, "execution_lock_hard"),
    ]
    rows = []
    for gate_id, observed, required, severity in gates:
        observed_int = int(observed)
        required_int = int(required)
        pass_now = int(observed_int == required_int)
        rows.append(
            {
                "gate_id": gate_id,
                "observed": observed_int,
                "required": required_int,
                "pass_now": pass_now,
                "severity": severity,
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_title("Official path unchanged; Stage238 writes a locked formal feature gate")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["formal rows", "ready rows", "candidate features", "rules"]
    values = [
        summary["formal_feature_table_row_written_count"],
        summary["formal_row_ready_count"],
        summary["strategy_candidate_feature_count"],
        summary["strategy_rule_created"],
    ]
    axes[3].bar(labels, values, color=["#0F766E", "#3657D6", "#B45309", "#991B1B"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_row_gate(row_gate: pd.DataFrame) -> None:
    cols = ["cutoff_guard_pass", "lineage_pass", "all_feature_ready", "formal_row_ready", "strategy_feature_usable"]
    view = row_gate.set_index("request_id")[cols].copy()
    fig, ax = plt.subplots(figsize=(11, max(5.0, len(view) * 0.55)))
    data = view.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage238 formal row gate matrix")
    ax.set_xticks(np.arange(len(view.columns)))
    ax.set_xticklabels(view.columns, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(view.index)))
    ax.set_yticklabels(view.index, fontsize=7)
    fig.tight_layout()
    fig.savefig(ROW_GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_feature_gate(feature_gate: pd.DataFrame) -> None:
    cols = [
        "formal_feature_table_admitted",
        "strategy_candidate_allowed_now",
        "diagnostic_only",
        "no_future_data",
        "no_final_pnl_label",
        "no_product_or_year_patch",
    ]
    view = feature_gate.set_index("feature_id")[cols].copy()
    fig, ax = plt.subplots(figsize=(11, 5.8))
    data = view.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage238 feature gate matrix")
    ax.set_xticks(np.arange(len(view.columns)))
    ax.set_xticklabels(view.columns, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(view.index)))
    ax.set_yticklabels(view.index, fontsize=8)
    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            ax.text(c, r, int(data[r, c]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FEATURE_GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_candidate_heatmap(formal: pd.DataFrame, feature_gate: pd.DataFrame) -> None:
    candidate_ids = feature_gate.loc[feature_gate["strategy_candidate_allowed_now"].eq(1), "feature_id"].astype(str).tolist()
    matrix = formal.set_index("request_id")[[f"candidate_{feature_id}" for feature_id in candidate_ids]].copy()
    matrix.columns = candidate_ids
    normalized = matrix.apply(_diagnostic_robust_z, axis=0).fillna(0.0)
    fig, ax = plt.subplots(figsize=(12, max(5.0, len(normalized) * 0.55)))
    data = normalized.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap=plt.get_cmap("PiYG"), vmin=-5, vmax=5)
    ax.set_title("Stage238 candidate feature heatmap (diagnostic robust-z only)")
    ax.set_xticks(np.arange(len(normalized.columns)))
    ax.set_xticklabels(normalized.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(normalized.index)))
    ax.set_yticklabels(normalized.index, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(CANDIDATE_HEATMAP_OUT, dpi=170)
    plt.close(fig)


def _plot_role_counts(feature_gate: pd.DataFrame) -> None:
    counts = pd.Series(
        {
            "formal admitted": int(feature_gate["formal_feature_table_admitted"].sum()),
            "strategy candidates": int(feature_gate["strategy_candidate_allowed_now"].sum()),
            "diagnostic only": int(feature_gate["diagnostic_only"].sum()),
            "strategy usable now": 0,
        }
    )
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(counts.index, counts.values, color=["#0F766E", "#3657D6", "#B45309", "#991B1B"])
    ax.set_title("Stage238 feature role counts")
    ax.set_ylabel("feature count")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    feature_gate: pd.DataFrame,
    row_gate: pd.DataFrame,
    normalization: pd.DataFrame,
    distribution: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    lines = [
        "# Stage238 Formal Feature Gate",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- This stage writes a locked formal feature table from Stage181 audit rows, but it does not allow strategy use, create rules, run true engine, trigger A/B, or touch execution config.",
        "- Strategy candidates are limited to dimensionless, point-in-time features; scale-dependent and data-quality fields remain diagnostic-only.",
        "- Diagnostic robust-z values are used only for the heatmap, not for strategy or production scaling.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feature Gate Audit",
        "",
        _md_table(feature_gate),
        "",
        "## Row Gate Audit",
        "",
        _md_table(row_gate, max_rows=80),
        "",
        "## Normalization Contract",
        "",
        _md_table(normalization),
        "",
        "## Distribution Audit",
        "",
        _md_table(distribution),
        "",
        "## Gate Status",
        "",
        _md_table(gate_status),
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    stage181 = _row(STAGE181_SUMMARY_IN)
    contract = _read_csv(STAGE156_FEATURE_CONTRACT_IN)
    values = _read_csv(STAGE181_VALUE_IN)
    readiness = _read_csv(STAGE181_READINESS_IN)
    formula = _read_csv(STAGE181_FORMULA_IN)
    lineage = _read_csv(STAGE181_LINEAGE_IN)

    feature_gate = _build_feature_gate(contract, readiness, formula)
    formal, row_gate = _build_formal_table(values, lineage, feature_gate)
    normalization = _normalization_contract(feature_gate)
    distribution = _distribution_audit(formal, feature_gate)

    formal_feature_admitted_count = int(feature_gate["formal_feature_table_admitted"].sum())
    strategy_candidate_count = int(feature_gate["strategy_candidate_allowed_now"].sum())
    diagnostic_count = int(feature_gate["diagnostic_only"].sum())
    formal_row_ready_count = int(row_gate["formal_row_ready"].sum())
    decision = "stage238_formal_feature_gate_written_strategy_locked_no_rule"
    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "stage239_read_only_universal_signal_quality_audit_no_true_engine",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "stage181_feature_audit_row_written_count": _int(stage181, "feature_audit_row_written_count"),
        "stage181_feature_ready_cell_count": _int(stage181, "feature_ready_cell_count"),
        "stage181_formal_feature_table_row_written_count": _int(stage181, "formal_feature_table_row_written_count"),
        "input_feature_count": int(len(contract)),
        "formal_feature_admitted_count": formal_feature_admitted_count,
        "strategy_candidate_feature_count": strategy_candidate_count,
        "diagnostic_only_feature_count": diagnostic_count,
        "formal_feature_table_row_written_count": int(len(formal)),
        "formal_row_ready_count": formal_row_ready_count,
        "formal_row_ready_ratio": float(formal_row_ready_count / len(formal)) if len(formal) else 0.0,
        "normalization_contract_row_count": int(len(normalization)),
        "distribution_audit_row_count": int(len(distribution)),
        "feature_table_file_written": 1,
        "feature_table_file_count": 2,
        "strategy_feature_usable": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "side_effect_count": int(len(formal)),
        "end_equity": float(stage181.get("end_equity", np.nan)),
        "total_return_pct": float(stage181.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage181.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage181.get("sharpe", np.nan)),
        "total_slippage": float(stage181.get("total_slippage", np.nan)),
        "total_trade_count": float(stage181.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage181.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage181.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate_status = _gate_status(summary_dict)

    formal.to_parquet(FORMAL_TABLE_OUT, index=False)
    _write_csv(formal, FORMAL_TABLE_CSV_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(feature_gate, FEATURE_GATE_OUT)
    _write_csv(row_gate, ROW_GATE_OUT)
    _write_csv(normalization, NORMALIZATION_CONTRACT_OUT)
    _write_csv(distribution, DISTRIBUTION_AUDIT_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_report(summary, feature_gate, row_gate, normalization, distribution, gate_status)
    _plot_path(curve, summary_dict)
    _plot_row_gate(row_gate)
    _plot_feature_gate(feature_gate)
    _plot_candidate_heatmap(formal, feature_gate)
    _plot_role_counts(feature_gate)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "summary": summary_dict,
            "inputs": {
                "stage156_feature_contract": str(STAGE156_FEATURE_CONTRACT_IN),
                "stage181_summary": str(STAGE181_SUMMARY_IN),
                "stage181_feature_value_audit": str(STAGE181_VALUE_IN),
                "stage181_feature_readiness_audit": str(STAGE181_READINESS_IN),
                "stage181_formula_implementation_audit": str(STAGE181_FORMULA_IN),
                "stage181_lineage_audit": str(STAGE181_LINEAGE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "formal_feature_table": str(FORMAL_TABLE_OUT),
                "formal_feature_table_csv": str(FORMAL_TABLE_CSV_OUT),
                "feature_gate_audit": str(FEATURE_GATE_OUT),
                "row_gate_audit": str(ROW_GATE_OUT),
                "normalization_contract": str(NORMALIZATION_CONTRACT_OUT),
                "feature_distribution_audit": str(DISTRIBUTION_AUDIT_OUT),
                "gate_status": str(GATE_STATUS_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(ROW_GATE_CHART_OUT),
                    str(FEATURE_GATE_CHART_OUT),
                    str(CANDIDATE_HEATMAP_OUT),
                    str(ROLE_CHART_OUT),
                ],
            },
            "locks": {
                "source_stage_allowed": "Stage181 audit outputs only",
                "feature_cutoff_rule": "bar_end_ts <= decision_ts inherited from Stage180/181",
                "strategy_feature_usable": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "official_config_changed": 0,
                "production_full_sample_scaler_allowed": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary_dict), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
