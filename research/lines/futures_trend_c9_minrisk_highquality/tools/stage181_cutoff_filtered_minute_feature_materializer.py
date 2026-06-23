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
STAGE = "Stage181"
MODEL_TAG = "stage181_cutoff_filtered_minute_feature_materializer_v1"
OUTPUT_PREFIX = "qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage181_cutoff_filtered_minute_feature_materializer"

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

STAGE180_DIR = LINE_DIR / "outputs" / "stage180_cutoff_filtered_predecision_feature_source"
STAGE180_PREFIX = "qmt_roll_stage180_c9_minrisk_cutoff_filtered_predecision_feature_source"
STAGE180_TAG = "stage180_cutoff_filtered_predecision_feature_source_v1"
STAGE180_SUMMARY_IN = STAGE180_DIR / f"{STAGE180_PREFIX}_summary_{STAGE180_TAG}.csv"
STAGE180_SOURCE_MANIFEST_IN = STAGE180_DIR / f"{STAGE180_PREFIX}_filtered_source_manifest_{STAGE180_TAG}.csv"
STAGE180_LINEAGE_IN = STAGE180_DIR / f"{STAGE180_PREFIX}_filtered_source_lineage_{STAGE180_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FEATURE_VALUE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_value_audit_{MODEL_TAG}.csv"
FEATURE_READINESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_readiness_audit_{MODEL_TAG}.csv"
FORMULA_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_formula_implementation_audit_{MODEL_TAG}.csv"
LINEAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_materializer_status_{MODEL_TAG}.png"
READINESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_readiness_matrix_{MODEL_TAG}.png"
VALUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_value_heatmap_{MODEL_TAG}.png"
LINEAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_cutoff_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

FEATURE_MIN_BARS = {
    "bar_return_1m": 2,
    "range_ratio_1m": 2,
    "directional_efficiency_30m": 31,
    "realized_volatility_30m": 31,
    "true_range_median_30m": 31,
    "volume_participation_30m": 30,
    "volume_zscore_60m": 60,
    "open_interest_delta_60m": 61,
    "turnover_vwap_gap_30m": 30,
    "closed_bar_count_coverage": 60,
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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _finite(value: float | int | np.floating) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _price_tick_proxy(bars: pd.DataFrame) -> float:
    values = pd.concat([bars["open"], bars["high"], bars["low"], bars["close"]], ignore_index=True)
    unique = np.sort(pd.to_numeric(values, errors="coerce").dropna().unique())
    if len(unique) < 2:
        return 1e-12
    diffs = np.diff(unique)
    positive = diffs[diffs > 0]
    if len(positive) == 0:
        return 1e-12
    return float(max(np.nanmin(positive), 1e-12))


def _turnover_multiplier_proxy(bars: pd.DataFrame) -> float:
    denom = pd.to_numeric(bars["close"], errors="coerce") * pd.to_numeric(bars["volume"], errors="coerce")
    ratio = pd.to_numeric(bars["turnover"], errors="coerce") / denom.replace(0, np.nan)
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    ratio = ratio[ratio > 0]
    if ratio.empty:
        return np.nan
    return float(ratio.median())


def _ready_record(
    manifest: pd.Series,
    feature: pd.Series,
    value: float,
    ready: int,
    observed_bars: int,
    reason: str,
    implementation: str,
) -> dict[str, Any]:
    feature_id = str(feature["feature_id"])
    return {
        "request_id": manifest["request_id"],
        "extension_window_id": manifest["extension_window_id"],
        "exchange": manifest["exchange"],
        "product": manifest["product"],
        "vt_symbol": manifest["vt_symbol"],
        "decision_ts": manifest["decision_ts"],
        "feature_id": feature_id,
        "family": feature["family"],
        "contract_formula": feature["formula"],
        "implementation_formula": implementation,
        "minimum_closed_bars_required": FEATURE_MIN_BARS[feature_id],
        "observed_closed_bars": observed_bars,
        "feature_value": value,
        "feature_ready": int(ready),
        "block_reason": reason,
        "feature_table_write_allowed_now": int(feature["feature_table_write_allowed_now"]),
        "future_data_allowed": 0,
        "strategy_rule_allowed": 0,
        "materialized_for_point_in_time_audit": 1,
    }


def _compute_feature_values(manifest: pd.DataFrame, contract: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    value_rows: list[dict[str, Any]] = []
    ready_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    features = contract.set_index("feature_id", drop=False)
    for _, item in manifest.sort_values(["exchange", "request_id"]).iterrows():
        source_path = _resolve_path(item["filtered_source_file"])
        bars = pd.read_parquet(source_path)
        bars["bar_end_ts_dt"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
        bars = bars[bars["bar_end_ts_dt"].notna()].sort_values("bar_end_ts_dt").reset_index(drop=True)
        decision_ts = pd.Timestamp(item["decision_ts"])
        cutoff_guard = int((bars["bar_end_ts_dt"] <= decision_ts).all()) if not bars.empty else 0
        duplicate_bar_count = int(bars["bar_end_ts"].duplicated().sum()) if "bar_end_ts" in bars else 0
        same_symbol_count = int(bars["vt_symbol"].astype(str).eq(str(item["vt_symbol"])).sum()) if "vt_symbol" in bars else 0
        observed_bars = int(len(bars))
        nonzero_volume_count = int(pd.to_numeric(bars["volume"], errors="coerce").fillna(0).gt(0).sum()) if "volume" in bars else 0
        last_bar_end_ts = "" if bars.empty else pd.Timestamp(bars["bar_end_ts_dt"].max()).strftime("%Y-%m-%d %H:%M:%S")
        tick_proxy = _price_tick_proxy(bars) if not bars.empty else np.nan
        multiplier_proxy = _turnover_multiplier_proxy(bars) if not bars.empty else np.nan

        close = pd.to_numeric(bars["close"], errors="coerce")
        high = pd.to_numeric(bars["high"], errors="coerce")
        low = pd.to_numeric(bars["low"], errors="coerce")
        volume = pd.to_numeric(bars["volume"], errors="coerce")
        turnover = pd.to_numeric(bars["turnover"], errors="coerce")
        open_interest = pd.to_numeric(bars["open_interest"], errors="coerce")

        values: dict[str, float] = {}
        readiness: dict[str, int] = {}
        reasons: dict[str, str] = {}
        implementations: dict[str, str] = {}

        if observed_bars >= 2 and close.iloc[-2] != 0 and pd.notna(close.iloc[-2]) and pd.notna(close.iloc[-1]):
            values["bar_return_1m"] = float(close.iloc[-1] / close.iloc[-2] - 1)
            readiness["bar_return_1m"] = int(_finite(values["bar_return_1m"]))
            reasons["bar_return_1m"] = "" if readiness["bar_return_1m"] else "non_finite_value"
        else:
            values["bar_return_1m"] = np.nan
            readiness["bar_return_1m"] = 0
            reasons["bar_return_1m"] = "need_two_closed_bars"
        implementations["bar_return_1m"] = "last_close / previous_close - 1"

        if observed_bars >= 2 and pd.notna(high.iloc[-1]) and pd.notna(low.iloc[-1]) and pd.notna(close.iloc[-2]):
            denom = max(abs(float(close.iloc[-2])), float(tick_proxy))
            values["range_ratio_1m"] = float((high.iloc[-1] - low.iloc[-1]) / denom) if denom > 0 else np.nan
            readiness["range_ratio_1m"] = int(_finite(values["range_ratio_1m"]))
            reasons["range_ratio_1m"] = "" if readiness["range_ratio_1m"] else "non_finite_value"
        else:
            values["range_ratio_1m"] = np.nan
            readiness["range_ratio_1m"] = 0
            reasons["range_ratio_1m"] = "need_two_closed_bars"
        implementations["range_ratio_1m"] = "(last_high - last_low) / max(abs(previous_close), tick_size_proxy)"

        if observed_bars >= 31:
            close31 = close.tail(31)
            denominator = float(close31.diff().abs().dropna().sum())
            numerator = float(abs(close31.iloc[-1] - close31.iloc[0]))
            values["directional_efficiency_30m"] = 0.0 if denominator == 0 else numerator / denominator
            readiness["directional_efficiency_30m"] = int(_finite(values["directional_efficiency_30m"]))
            reasons["directional_efficiency_30m"] = "" if readiness["directional_efficiency_30m"] else "non_finite_value"
        else:
            values["directional_efficiency_30m"] = np.nan
            readiness["directional_efficiency_30m"] = 0
            reasons["directional_efficiency_30m"] = "need_31_closed_bars"
        implementations["directional_efficiency_30m"] = "abs(close_t - close_t_minus_30) / sum(abs(diff(close))) over last 31 closes"

        if observed_bars >= 31 and (close.tail(31) > 0).all():
            log_returns = np.log(close.tail(31)).diff().dropna()
            values["realized_volatility_30m"] = float(log_returns.std(ddof=1))
            readiness["realized_volatility_30m"] = int(_finite(values["realized_volatility_30m"]))
            reasons["realized_volatility_30m"] = "" if readiness["realized_volatility_30m"] else "non_finite_value"
        else:
            values["realized_volatility_30m"] = np.nan
            readiness["realized_volatility_30m"] = 0
            reasons["realized_volatility_30m"] = "need_31_positive_closed_closes"
        implementations["realized_volatility_30m"] = "std(log(close).diff(), ddof=1) over last 31 closed bars"

        if observed_bars >= 31:
            prev_close = close.shift(1)
            true_range = pd.concat(
                [
                    high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            tr30 = true_range.tail(30).dropna()
            values["true_range_median_30m"] = float(tr30.median()) if len(tr30) == 30 else np.nan
            readiness["true_range_median_30m"] = int(_finite(values["true_range_median_30m"]))
            reasons["true_range_median_30m"] = "" if readiness["true_range_median_30m"] else "need_30_valid_true_ranges"
        else:
            values["true_range_median_30m"] = np.nan
            readiness["true_range_median_30m"] = 0
            reasons["true_range_median_30m"] = "need_31_closed_bars"
        implementations["true_range_median_30m"] = "median(max(high-low, abs(high-prev_close), abs(low-prev_close))) over last 30 ranges"

        if observed_bars >= 30:
            volume30 = volume.tail(30)
            values["volume_participation_30m"] = float(volume30.gt(0).mean())
            readiness["volume_participation_30m"] = int(_finite(values["volume_participation_30m"]))
            reasons["volume_participation_30m"] = "" if readiness["volume_participation_30m"] else "non_finite_value"
        else:
            values["volume_participation_30m"] = np.nan
            readiness["volume_participation_30m"] = 0
            reasons["volume_participation_30m"] = "need_30_closed_bars"
        implementations["volume_participation_30m"] = "nonzero minute share over last 30 closed bars; volume_sum_30m retained as diagnostic"

        if observed_bars >= 60:
            volume60 = volume.tail(60)
            volume30 = volume.tail(30)
            std60 = float(volume60.std(ddof=1))
            values["volume_zscore_60m"] = 0.0 if std60 == 0 else float((volume30.mean() - volume60.mean()) / std60)
            readiness["volume_zscore_60m"] = int(_finite(values["volume_zscore_60m"]))
            reasons["volume_zscore_60m"] = "" if readiness["volume_zscore_60m"] else "non_finite_value"
        else:
            values["volume_zscore_60m"] = np.nan
            readiness["volume_zscore_60m"] = 0
            reasons["volume_zscore_60m"] = "need_60_closed_bars"
        implementations["volume_zscore_60m"] = "(mean(volume_last30) - mean(volume_last60)) / std(volume_last60, ddof=1)"

        if observed_bars >= 61 and pd.notna(open_interest.iloc[-1]) and pd.notna(open_interest.iloc[-61]):
            values["open_interest_delta_60m"] = float(open_interest.iloc[-1] - open_interest.iloc[-61])
            readiness["open_interest_delta_60m"] = int(_finite(values["open_interest_delta_60m"]))
            reasons["open_interest_delta_60m"] = "" if readiness["open_interest_delta_60m"] else "non_finite_value"
        else:
            values["open_interest_delta_60m"] = np.nan
            readiness["open_interest_delta_60m"] = 0
            reasons["open_interest_delta_60m"] = "need_61_closed_bars_with_open_interest"
        implementations["open_interest_delta_60m"] = "last_open_interest - open_interest_60_closed_bars_ago"

        if observed_bars >= 30 and _finite(multiplier_proxy) and multiplier_proxy > 0:
            volume30 = volume.tail(30)
            turnover30 = turnover.tail(30)
            denom = float(volume30.sum() * multiplier_proxy)
            vwap30 = float(turnover30.sum() / denom) if denom > 0 else np.nan
            values["turnover_vwap_gap_30m"] = float(close.iloc[-1] / vwap30 - 1) if _finite(vwap30) and vwap30 > 0 else np.nan
            readiness["turnover_vwap_gap_30m"] = int(_finite(values["turnover_vwap_gap_30m"]))
            reasons["turnover_vwap_gap_30m"] = "" if readiness["turnover_vwap_gap_30m"] else "non_finite_value"
        else:
            values["turnover_vwap_gap_30m"] = np.nan
            readiness["turnover_vwap_gap_30m"] = 0
            reasons["turnover_vwap_gap_30m"] = "need_30_closed_bars_with_positive_turnover_multiplier"
        implementations["turnover_vwap_gap_30m"] = "last_close / (sum(turnover_last30) / (sum(volume_last30) * inferred_multiplier)) - 1"

        values["closed_bar_count_coverage"] = float(observed_bars)
        readiness["closed_bar_count_coverage"] = int(observed_bars >= 60 and duplicate_bar_count == 0 and nonzero_volume_count >= 60)
        reasons["closed_bar_count_coverage"] = "" if readiness["closed_bar_count_coverage"] else "coverage_or_duplicate_gate_failed"
        implementations["closed_bar_count_coverage"] = "unique closed bar count with duplicate and nonzero-volume guards"

        row_ready = int(
            bool(cutoff_guard)
            and duplicate_bar_count == 0
            and observed_bars >= 61
            and all(int(readiness.get(feature_id, 0)) == 1 for feature_id in contract["feature_id"].astype(str))
        )
        value_row: dict[str, Any] = {
            "request_id": item["request_id"],
            "extension_window_id": item["extension_window_id"],
            "exchange": item["exchange"],
            "product": item["product"],
            "vt_symbol": item["vt_symbol"],
            "decision_ts": item["decision_ts"],
            "feature_cutoff_ts": last_bar_end_ts,
            "filtered_source_file": item["filtered_source_file"],
            "filtered_source_sha256": item["filtered_source_sha256"],
            "observed_closed_bars": observed_bars,
            "nonzero_volume_count": nonzero_volume_count,
            "duplicate_bar_count": duplicate_bar_count,
            "same_symbol_row_count": same_symbol_count,
            "cutoff_guard_pass": cutoff_guard,
            "tick_size_proxy": tick_proxy,
            "turnover_multiplier_proxy": multiplier_proxy,
            "volume_sum_30m": float(volume.tail(30).sum()) if observed_bars >= 30 else np.nan,
            "volume_sum_60m": float(volume.tail(60).sum()) if observed_bars >= 60 else np.nan,
            "row_ready_for_point_in_time_audit": row_ready,
            "feature_table_row_written": 0,
            "feature_table_write_allowed_now": int(contract["feature_table_write_allowed_now"].max()),
            "strategy_feature_usable": 0,
            "strategy_rule_allowed": 0,
            "true_engine_allowed": 0,
            "ab_allowed": 0,
        }
        for feature_id in contract["feature_id"].astype(str):
            value_row[feature_id] = values[feature_id]
            value_row[f"{feature_id}__ready"] = readiness[feature_id]
            ready_rows.append(
                _ready_record(
                    item,
                    features.loc[feature_id],
                    values[feature_id],
                    readiness[feature_id],
                    observed_bars,
                    reasons[feature_id],
                    implementations[feature_id],
                )
            )
        value_rows.append(value_row)
        lineage_rows.append(
            {
                "request_id": item["request_id"],
                "extension_window_id": item["extension_window_id"],
                "source_stage": "Stage180",
                "materializer_stage": STAGE,
                "filtered_source_file": item["filtered_source_file"],
                "filtered_source_sha256": item["filtered_source_sha256"],
                "decision_ts": item["decision_ts"],
                "feature_cutoff_ts": last_bar_end_ts,
                "source_cutoff_rule": "bar_end_ts <= decision_ts",
                "cutoff_guard_pass": cutoff_guard,
                "duplicate_bar_count": duplicate_bar_count,
                "observed_closed_bars": observed_bars,
                "feature_value_audit_row_written": 1,
                "formal_feature_table_row_written": 0,
                "strategy_rule_allowed": 0,
                "lineage_pass": row_ready,
            }
        )
    return pd.DataFrame(value_rows), pd.DataFrame(ready_rows), pd.DataFrame(lineage_rows)


def _formula_audit(contract: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    grouped = readiness.groupby("feature_id", dropna=False)
    for _, feature in contract.iterrows():
        feature_id = str(feature["feature_id"])
        impl = ""
        ready_count = 0
        value_count = 0
        if feature_id in grouped.groups:
            part = grouped.get_group(feature_id)
            ready_count = int(part["feature_ready"].sum())
            value_count = int(part["feature_value"].notna().sum())
            impl = str(part["implementation_formula"].iloc[0])
        records.append(
            {
                "feature_id": feature_id,
                "family": feature["family"],
                "contract_formula": feature["formula"],
                "implementation_formula": impl,
                "minimum_closed_bars_required": FEATURE_MIN_BARS[feature_id],
                "ready_request_count": ready_count,
                "finite_value_count": value_count,
                "feature_table_write_allowed_now": int(feature["feature_table_write_allowed_now"]),
                "contains_final_pnl_label": int(feature["contains_final_pnl_label"]),
                "contains_product_or_year_patch": int(feature["contains_product_or_year_patch"]),
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage180_filtered_source_ready_loaded", summary["stage180_cutoff_filtered_source_ready_count"], summary["stage180_filtered_source_written_count"], "dependency_hard"),
        ("feature_contract_loaded", summary["feature_contract_count"], 10, "contract_hard"),
        ("source_cutoff_guard_pass", summary["source_cutoff_guard_pass_count"], summary["feature_audit_row_written_count"], "point_in_time_hard"),
        ("lineage_pass", summary["lineage_pass_count"], summary["feature_audit_row_written_count"], "lineage_hard"),
        ("feature_ready_cell_count", summary["feature_ready_cell_count"], summary["feature_total_cell_count"], "audit_hard"),
        ("formal_feature_table_row_written", summary["formal_feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_feature_usable", summary["strategy_feature_usable"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
    ]
    records: list[dict[str, Any]] = []
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


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_title("Official path unchanged; Stage181 materializes audit-only predecision features")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["audit rows", "ready cells", "formal rows", "rules"]
    values = [
        summary["feature_audit_row_written_count"],
        summary["feature_ready_cell_count"],
        summary["formal_feature_table_row_written_count"],
        summary["strategy_rule_created"],
    ]
    axes[3].bar(labels, values, color=["#0F766E", "#3657D6", "#111827", "#991B1B"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_readiness(readiness: pd.DataFrame) -> None:
    matrix = readiness.pivot(index="request_id", columns="feature_id", values="feature_ready").fillna(0)
    fig, ax = plt.subplots(figsize=(13, max(4.8, len(matrix) * 0.6)))
    data = matrix.to_numpy(dtype=float) if not matrix.empty else np.zeros((1, 1))
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage181 feature readiness on cutoff-filtered sources")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            ax.text(c, r, int(data[r, c]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(READINESS_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_values(values: pd.DataFrame, contract: pd.DataFrame) -> None:
    features = contract["feature_id"].astype(str).tolist()
    raw = values.set_index("request_id")[features].copy()
    normalized = raw.copy()
    for column in normalized.columns:
        series = pd.to_numeric(normalized[column], errors="coerce")
        if series.notna().sum() <= 1:
            normalized[column] = 0.0
            continue
        spread = float(series.std(ddof=0))
        normalized[column] = 0.0 if spread == 0 else (series - float(series.mean())) / spread
    normalized = normalized.fillna(0.0)
    fig, ax = plt.subplots(figsize=(13, max(4.8, len(normalized) * 0.6)))
    data = normalized.to_numpy(dtype=float) if not normalized.empty else np.zeros((1, 1))
    vmax = max(1.0, float(np.nanmax(np.abs(data))) if data.size else 1.0)
    image = ax.imshow(data, aspect="auto", cmap=plt.get_cmap("PiYG"), vmin=-vmax, vmax=vmax)
    ax.set_title("Stage181 standardized feature value heatmap (audit only)")
    ax.set_xticks(np.arange(len(normalized.columns)))
    ax.set_xticklabels(normalized.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(normalized.index)))
    ax.set_yticklabels(normalized.index, fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(VALUE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_lineage(lineage: pd.DataFrame) -> None:
    matrix = lineage.copy()
    matrix["formal_feature_table_block_pass"] = (matrix["formal_feature_table_row_written"].astype(int) == 0).astype(int)
    matrix["strategy_rule_block_pass"] = (matrix["strategy_rule_allowed"].astype(int) == 0).astype(int)
    cols = ["cutoff_guard_pass", "lineage_pass", "feature_value_audit_row_written", "formal_feature_table_block_pass", "strategy_rule_block_pass"]
    view = matrix.set_index("request_id")[cols]
    fig, ax = plt.subplots(figsize=(10, max(4.8, len(view) * 0.6)))
    data = view.to_numpy(dtype=float) if not view.empty else np.zeros((1, 1))
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage181 lineage and cutoff matrix")
    ax.set_xticks(np.arange(len(view.columns)))
    ax.set_xticklabels(view.columns, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(view.index)))
    ax.set_yticklabels(view.index, fontsize=8)
    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            ax.text(c, r, int(data[r, c]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(LINEAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, max(5.5, len(gate) * 0.45)))
    matrix = gate.set_index("gate_id")[["pass_now"]]
    data = matrix.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_title("Stage181 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for r in range(data.shape[0]):
        ax.text(0, r, int(data[r, 0]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    values: pd.DataFrame,
    readiness: pd.DataFrame,
    formula: pd.DataFrame,
    lineage: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        "# Stage181 Cutoff-Filtered Minute Feature Materializer",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- This stage materializes audit-only feature values from Stage180 cutoff-filtered sources. It writes no formal feature table and creates no strategy rule.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feature Value Audit",
        "",
        _md_table(values),
        "",
        "## Feature Readiness Audit",
        "",
        _md_table(readiness, max_rows=80),
        "",
        "## Formula Implementation Audit",
        "",
        _md_table(formula),
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    stage180 = _row(STAGE180_SUMMARY_IN)
    contract = _read_csv(STAGE156_FEATURE_CONTRACT_IN)
    manifest = _read_csv(STAGE180_SOURCE_MANIFEST_IN)
    _ = _read_csv(STAGE180_LINEAGE_IN)
    manifest = manifest[manifest["cutoff_filtered_source_ready"].eq(1)].copy()
    values, readiness, lineage = _compute_feature_values(manifest, contract)
    formula = _formula_audit(contract, readiness)

    feature_total_cell_count = int(len(readiness))
    feature_ready_cell_count = int(readiness["feature_ready"].sum()) if not readiness.empty else 0
    lineage_pass_count = int(lineage["lineage_pass"].sum()) if not lineage.empty else 0
    source_cutoff_guard_pass_count = int(values["cutoff_guard_pass"].sum()) if not values.empty else 0
    formal_feature_table_row_written_count = int(values["feature_table_row_written"].sum()) if not values.empty else 0
    decision = "stage181_cutoff_filtered_minute_feature_audit_ready_no_formal_feature_table_no_rule"
    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "stage182_expand_stage177_delivery_or_define_audit_to_formal_feature_gate_without_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage180_filtered_source_written_count": _int(stage180, "filtered_source_written_count"),
        "stage180_cutoff_filtered_source_ready_count": _int(stage180, "cutoff_filtered_source_ready_count"),
        "stage180_post_decision_removed_count": _int(stage180, "post_decision_removed_count"),
        "feature_contract_count": int(len(contract)),
        "feature_contract_write_allowed_now_sum": int(contract["feature_table_write_allowed_now"].sum()),
        "feature_audit_row_written_count": int(len(values)),
        "feature_readiness_row_count": int(len(readiness)),
        "feature_total_cell_count": feature_total_cell_count,
        "feature_ready_cell_count": feature_ready_cell_count,
        "feature_ready_ratio": float(feature_ready_cell_count / feature_total_cell_count) if feature_total_cell_count else 0.0,
        "source_cutoff_guard_pass_count": source_cutoff_guard_pass_count,
        "lineage_pass_count": lineage_pass_count,
        "formal_feature_table_row_written_count": formal_feature_table_row_written_count,
        "feature_table_file_written": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage180.get("end_equity", np.nan)),
        "total_return_pct": float(stage180.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage180.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage180.get("sharpe", np.nan)),
        "total_slippage": float(stage180.get("total_slippage", np.nan)),
        "total_trade_count": float(stage180.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage180.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage180.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(values, FEATURE_VALUE_AUDIT_OUT)
    _write_csv(readiness, FEATURE_READINESS_OUT)
    _write_csv(formula, FORMULA_AUDIT_OUT)
    _write_csv(lineage, LINEAGE_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, values, readiness, formula, lineage, gate)
    _plot_path(curve, summary_dict)
    _plot_readiness(readiness)
    _plot_values(values, contract)
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
                "stage156_feature_contract": str(STAGE156_FEATURE_CONTRACT_IN),
                "stage180_summary": str(STAGE180_SUMMARY_IN),
                "stage180_filtered_source_manifest": str(STAGE180_SOURCE_MANIFEST_IN),
                "stage180_lineage": str(STAGE180_LINEAGE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "feature_value_audit": str(FEATURE_VALUE_AUDIT_OUT),
                "feature_readiness_audit": str(FEATURE_READINESS_OUT),
                "formula_implementation_audit": str(FORMULA_AUDIT_OUT),
                "lineage_audit": str(LINEAGE_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(READINESS_CHART_OUT), str(VALUE_CHART_OUT), str(LINEAGE_CHART_OUT), str(GATE_CHART_OUT)],
            },
            "locks": {
                "source_stage_allowed": "Stage180 cutoff-filtered sources only",
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
                "formal_feature_table_row_written_count": formal_feature_table_row_written_count,
                "feature_table_file_written": 0,
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
