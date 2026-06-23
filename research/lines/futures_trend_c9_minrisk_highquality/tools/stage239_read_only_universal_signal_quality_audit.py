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
STAGE = "Stage239"
MODEL_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"

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
STAGE177_CONTRACT_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_extension_window_contract_{STAGE177_TAG}.csv"

STAGE238_DIR = LINE_DIR / "outputs" / "stage238_formal_feature_gate"
STAGE238_PREFIX = "qmt_roll_stage238_c9_minrisk_formal_feature_gate"
STAGE238_TAG = "stage238_formal_feature_gate_v1"
STAGE238_FORMAL_TABLE_IN = STAGE238_DIR / f"{STAGE238_PREFIX}_formal_feature_table_{STAGE238_TAG}.csv"
STAGE238_SUMMARY_IN = STAGE238_DIR / f"{STAGE238_PREFIX}_summary_{STAGE238_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
JOINED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_signal_label_audit_{MODEL_TAG}.csv"
FEATURE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_rank_correlation_audit_{MODEL_TAG}.csv"
QUINTILE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quintile_audit_{MODEL_TAG}.csv"
STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_stability_audit_{MODEL_TAG}.csv"
LABEL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_distribution_audit_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_signal_audit_status_{MODEL_TAG}.png"
RISK_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_bad_rate_by_quality_quintile_{MODEL_TAG}.png"
TAIL_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_right_tail_rate_by_quality_quintile_{MODEL_TAG}.png"
STABILITY_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_matrix_{MODEL_TAG}.png"
FEATURE_DELTA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_top_bottom_delta_summary_{MODEL_TAG}.png"
LABEL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_distribution_{MODEL_TAG}.png"


FEATURE_SPECS: list[dict[str, Any]] = [
    {
        "feature_id": "bar_return_1m",
        "audit_feature_id": "aligned_bar_return_1m",
        "source_column": "candidate_bar_return_1m",
        "direction_adjusted": 1,
        "expected_quality_direction": 1,
        "economic_hypothesis": "入场前最近一分钟收益与交易方向同向，代表即时趋势仍在接力。",
    },
    {
        "feature_id": "range_ratio_1m",
        "audit_feature_id": "low_range_ratio_1m",
        "source_column": "candidate_range_ratio_1m",
        "direction_adjusted": 0,
        "expected_quality_direction": -1,
        "economic_hypothesis": "同一根入场前分钟的无方向振幅越低，短噪声/滑点地板越低。",
    },
    {
        "feature_id": "directional_efficiency_30m",
        "audit_feature_id": "directional_efficiency_30m",
        "source_column": "candidate_directional_efficiency_30m",
        "direction_adjusted": 0,
        "expected_quality_direction": 1,
        "economic_hypothesis": "前置三十分钟方向效率越高，趋势持续上下文越干净。",
    },
    {
        "feature_id": "realized_volatility_30m",
        "audit_feature_id": "low_realized_volatility_30m",
        "source_column": "candidate_realized_volatility_30m",
        "direction_adjusted": 0,
        "expected_quality_direction": -1,
        "economic_hypothesis": "前置三十分钟已实现波动越低，单位风险噪声越低。",
    },
    {
        "feature_id": "volume_participation_30m",
        "audit_feature_id": "volume_participation_30m",
        "source_column": "candidate_volume_participation_30m",
        "direction_adjusted": 0,
        "expected_quality_direction": 1,
        "economic_hypothesis": "前置三十分钟成交参与越充分，信号不是孤立报价跳动。",
    },
    {
        "feature_id": "volume_zscore_60m",
        "audit_feature_id": "volume_zscore_60m",
        "source_column": "candidate_volume_zscore_60m",
        "direction_adjusted": 0,
        "expected_quality_direction": 1,
        "economic_hypothesis": "相对六十分钟基线的成交惊喜越高，信息到达概率越高。",
    },
    {
        "feature_id": "turnover_vwap_gap_30m",
        "audit_feature_id": "aligned_turnover_vwap_gap_30m",
        "source_column": "candidate_turnover_vwap_gap_30m",
        "direction_adjusted": 1,
        "expected_quality_direction": 1,
        "economic_hypothesis": "入场前价格相对成交额 VWAP 的偏离与交易方向一致，代表执行压力同向。",
    },
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


def _rank_corr(left: pd.Series, right: pd.Series) -> float:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    mask = left_num.notna() & right_num.notna()
    if int(mask.sum()) < 3:
        return np.nan
    left_valid = left_num[mask]
    right_valid = right_num[mask]
    if left_valid.nunique(dropna=True) < 2 or right_valid.nunique(dropna=True) < 2:
        return np.nan
    return float(left_valid.rank(method="average").corr(right_valid.rank(method="average"), method="pearson"))


def _quality_quintile(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    result = pd.Series(np.nan, index=series.index, dtype="float64")
    mask = values.notna()
    if int(mask.sum()) == 0:
        return result
    pct = values[mask].rank(method="average", pct=True)
    quintile = np.ceil((pct * 5).clip(lower=0, upper=5)).astype(int)
    quintile = quintile.clip(lower=1, upper=5)
    result.loc[mask] = quintile.astype(float)
    return result


def _rate(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _mean_or_nan(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def _prepare_joined(formal: pd.DataFrame, contract: pd.DataFrame) -> pd.DataFrame:
    if formal["extension_window_id"].duplicated().any():
        raise RuntimeError("Stage238 formal table extension_window_id is not unique")
    if contract["extension_window_id"].duplicated().any():
        raise RuntimeError("Stage177 extension contract extension_window_id is not unique")
    contract_columns = [
        "extension_window_id",
        "candidate_index",
        "official_open_trade_id",
        "direction",
        "official_open_date",
        "priority_class",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "low_resolution_zone",
        "event_time_missing",
        "resolution_bucket",
        "anchor_event_time",
        "anchor_event_time_source",
        "feature_cutoff_rule",
        "delivery_ready",
        "feature_table_row_allowed_now",
        "strategy_rule_allowed",
    ]
    joined = formal.merge(contract[contract_columns], on="extension_window_id", how="left", validate="one_to_one")
    joined["decision_ts"] = pd.to_datetime(joined["decision_ts"], errors="coerce")
    joined["decision_year"] = joined["decision_ts"].dt.year.astype("Int64")
    joined["direction_sign"] = np.where(joined["direction"].astype(str).str.lower().eq("short"), -1.0, 1.0)
    for column in ["right_tail_visual", "bottom_loss_visual", "maxdd_context", "low_resolution_zone", "event_time_missing"]:
        joined[column] = pd.to_numeric(joined[column], errors="coerce").fillna(0).astype(int)
    joined["risk_bad_label"] = ((joined["bottom_loss_visual"] == 1) | (joined["maxdd_context"] == 1)).astype(int)
    joined["right_tail_label"] = (joined["right_tail_visual"] == 1).astype(int)
    joined["low_resolution_label"] = (joined["low_resolution_zone"] == 1).astype(int)
    joined["event_time_missing_label"] = (joined["event_time_missing"] == 1).astype(int)
    joined["ordinary_clean_label"] = (
        joined["priority_class"].astype(str).eq("ordinary")
        & joined["risk_bad_label"].eq(0)
        & joined["right_tail_label"].eq(0)
        & joined["low_resolution_label"].eq(0)
        & joined["event_time_missing_label"].eq(0)
    ).astype(int)
    joined["runway_ready_label"] = joined["resolution_bucket"].astype(str).eq("gt_five_bar_runway").astype(int)
    joined["label_trading_rule_allowed"] = 0
    joined["audit_strategy_rule_allowed"] = 0
    for spec in FEATURE_SPECS:
        source = spec["source_column"]
        audit_id = spec["audit_feature_id"]
        raw = pd.to_numeric(joined[source], errors="coerce")
        audit_value = raw * joined["direction_sign"] if spec["direction_adjusted"] else raw
        quality_value = audit_value * float(spec["expected_quality_direction"])
        joined[f"audit_value_{audit_id}"] = audit_value
        joined[f"quality_value_{audit_id}"] = quality_value
        joined[f"quality_quintile_{audit_id}"] = _quality_quintile(quality_value)
    return joined


def _build_label_distribution(joined: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    label_specs = {
        "risk_bad_label": "bottom_loss_visual OR maxdd_context",
        "right_tail_label": "right_tail_visual",
        "ordinary_clean_label": "ordinary priority and no risk/right-tail/low-resolution/missing",
        "low_resolution_label": "low_resolution_zone",
        "event_time_missing_label": "event_time_missing",
        "runway_ready_label": "resolution_bucket == gt_five_bar_runway",
    }
    for label_id, description in label_specs.items():
        values = pd.to_numeric(joined[label_id], errors="coerce").fillna(0).astype(int)
        records.append(
            {
                "label_id": label_id,
                "description": description,
                "positive_count": int(values.sum()),
                "negative_count": int((values == 0).sum()),
                "positive_rate": float(values.mean()),
                "trading_rule_allowed": 0,
            }
        )
    for column in ["priority_class", "resolution_bucket", "exchange", "direction"]:
        counts = joined[column].astype(str).value_counts(dropna=False).sort_index()
        for value, count in counts.items():
            records.append(
                {
                    "label_id": f"{column}={value}",
                    "description": f"distribution of {column}",
                    "positive_count": int(count),
                    "negative_count": int(len(joined) - count),
                    "positive_rate": float(count / len(joined)) if len(joined) else np.nan,
                    "trading_rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _build_quintile_and_summary(joined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    quintile_records: list[dict[str, Any]] = []
    summary_records: list[dict[str, Any]] = []
    for spec in FEATURE_SPECS:
        feature_id = spec["feature_id"]
        audit_id = spec["audit_feature_id"]
        q_col = f"quality_quintile_{audit_id}"
        quality_col = f"quality_value_{audit_id}"
        audit_col = f"audit_value_{audit_id}"
        for quintile in range(1, 6):
            group = joined[joined[q_col].eq(float(quintile))]
            quintile_records.append(
                {
                    "feature_id": feature_id,
                    "audit_feature_id": audit_id,
                    "quality_quintile": quintile,
                    "row_count": int(len(group)),
                    "quality_value_mean": _mean_or_nan(group[quality_col]),
                    "audit_value_mean": _mean_or_nan(group[audit_col]),
                    "risk_bad_count": int(pd.to_numeric(group["risk_bad_label"], errors="coerce").fillna(0).sum()),
                    "risk_bad_rate": _rate(group["risk_bad_label"]),
                    "right_tail_count": int(pd.to_numeric(group["right_tail_label"], errors="coerce").fillna(0).sum()),
                    "right_tail_rate": _rate(group["right_tail_label"]),
                    "ordinary_clean_count": int(
                        pd.to_numeric(group["ordinary_clean_label"], errors="coerce").fillna(0).sum()
                    ),
                    "ordinary_clean_rate": _rate(group["ordinary_clean_label"]),
                    "low_resolution_count": int(
                        pd.to_numeric(group["low_resolution_label"], errors="coerce").fillna(0).sum()
                    ),
                    "low_resolution_rate": _rate(group["low_resolution_label"]),
                    "strategy_rule_allowed": 0,
                }
            )
        feature_quintiles = pd.DataFrame([record for record in quintile_records if record["audit_feature_id"] == audit_id])
        q1 = feature_quintiles[feature_quintiles["quality_quintile"].eq(1)].iloc[0]
        q5 = feature_quintiles[feature_quintiles["quality_quintile"].eq(5)].iloc[0]
        rates = feature_quintiles[feature_quintiles["row_count"].gt(0)].copy()
        risk_quintile_corr = _rank_corr(rates["quality_quintile"], rates["risk_bad_rate"])
        tail_quintile_corr = _rank_corr(rates["quality_quintile"], rates["right_tail_rate"])
        clean_quintile_corr = _rank_corr(rates["quality_quintile"], rates["ordinary_clean_rate"])
        aggregate_risk_corr = _rank_corr(joined[quality_col], joined["risk_bad_label"])
        aggregate_tail_corr = _rank_corr(joined[quality_col], joined["right_tail_label"])
        aggregate_clean_corr = _rank_corr(joined[quality_col], joined["ordinary_clean_label"])
        q5_minus_q1_risk = float(q5["risk_bad_rate"] - q1["risk_bad_rate"])
        q5_minus_q1_tail = float(q5["right_tail_rate"] - q1["right_tail_rate"])
        q5_minus_q1_clean = float(q5["ordinary_clean_rate"] - q1["ordinary_clean_rate"])
        aggregate_risk_direction_pass = int(np.isfinite(aggregate_risk_corr) and aggregate_risk_corr <= 0 and q5_minus_q1_risk <= 0)
        aggregate_tail_direction_pass = int(np.isfinite(aggregate_tail_corr) and aggregate_tail_corr >= 0 and q5_minus_q1_tail >= 0)
        aggregate_clean_direction_pass = int(np.isfinite(aggregate_clean_corr) and aggregate_clean_corr >= 0 and q5_minus_q1_clean >= 0)
        summary_records.append(
            {
                "feature_id": feature_id,
                "audit_feature_id": audit_id,
                "source_column": spec["source_column"],
                "direction_adjusted": int(spec["direction_adjusted"]),
                "expected_quality_direction": int(spec["expected_quality_direction"]),
                "economic_hypothesis": spec["economic_hypothesis"],
                "valid_value_count": int(pd.to_numeric(joined[quality_col], errors="coerce").notna().sum()),
                "quality_unique_value_count": int(pd.to_numeric(joined[quality_col], errors="coerce").nunique(dropna=True)),
                "nonempty_quality_quintile_count": int(feature_quintiles["row_count"].gt(0).sum()),
                "quality_rank_corr_vs_risk_bad": aggregate_risk_corr,
                "quality_rank_corr_vs_right_tail": aggregate_tail_corr,
                "quality_rank_corr_vs_ordinary_clean": aggregate_clean_corr,
                "quintile_corr_vs_risk_bad_rate": risk_quintile_corr,
                "quintile_corr_vs_right_tail_rate": tail_quintile_corr,
                "quintile_corr_vs_ordinary_clean_rate": clean_quintile_corr,
                "q5_minus_q1_risk_bad_rate": q5_minus_q1_risk,
                "q5_minus_q1_right_tail_rate": q5_minus_q1_tail,
                "q5_minus_q1_ordinary_clean_rate": q5_minus_q1_clean,
                "aggregate_risk_direction_pass": aggregate_risk_direction_pass,
                "aggregate_tail_direction_pass": aggregate_tail_direction_pass,
                "aggregate_clean_direction_pass": aggregate_clean_direction_pass,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(quintile_records), pd.DataFrame(summary_records)


def _build_stability(joined: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    split_specs = [
        ("decision_year", "year", 8),
        ("exchange", "exchange", 8),
        ("direction", "direction", 8),
    ]
    for spec in FEATURE_SPECS:
        feature_id = spec["feature_id"]
        audit_id = spec["audit_feature_id"]
        quality_col = f"quality_value_{audit_id}"
        for split_column, split_type, min_rows in split_specs:
            for split_value, group in joined.groupby(split_column, dropna=False):
                row_count = int(len(group))
                risk_corr = _rank_corr(group[quality_col], group["risk_bad_label"])
                tail_corr = _rank_corr(group[quality_col], group["right_tail_label"])
                clean_corr = _rank_corr(group[quality_col], group["ordinary_clean_label"])
                valid_for_risk = int(row_count >= min_rows and np.isfinite(risk_corr))
                valid_for_tail = int(row_count >= min_rows and np.isfinite(tail_corr))
                valid_for_clean = int(row_count >= min_rows and np.isfinite(clean_corr))
                records.append(
                    {
                        "feature_id": feature_id,
                        "audit_feature_id": audit_id,
                        "split_type": split_type,
                        "split_value": "" if pd.isna(split_value) else str(split_value),
                        "row_count": row_count,
                        "min_rows_required": min_rows,
                        "risk_bad_count": int(pd.to_numeric(group["risk_bad_label"], errors="coerce").fillna(0).sum()),
                        "right_tail_count": int(pd.to_numeric(group["right_tail_label"], errors="coerce").fillna(0).sum()),
                        "ordinary_clean_count": int(
                            pd.to_numeric(group["ordinary_clean_label"], errors="coerce").fillna(0).sum()
                        ),
                        "quality_rank_corr_vs_risk_bad": risk_corr,
                        "quality_rank_corr_vs_right_tail": tail_corr,
                        "quality_rank_corr_vs_ordinary_clean": clean_corr,
                        "risk_direction_good": int(risk_corr <= 0) if valid_for_risk else np.nan,
                        "tail_direction_good": int(tail_corr >= 0) if valid_for_tail else np.nan,
                        "clean_direction_good": int(clean_corr >= 0) if valid_for_clean else np.nan,
                        "valid_for_risk": valid_for_risk,
                        "valid_for_tail": valid_for_tail,
                        "valid_for_clean": valid_for_clean,
                        "strategy_rule_allowed": 0,
                    }
                )
    return pd.DataFrame(records)


def _attach_stability_summary(feature_summary: pd.DataFrame, stability: pd.DataFrame) -> pd.DataFrame:
    result = feature_summary.copy()
    for split_type in ["year", "exchange", "direction"]:
        subset = stability[stability["split_type"].eq(split_type)]
        risk = subset[subset["valid_for_risk"].eq(1)].groupby("audit_feature_id")["risk_direction_good"].agg(["count", "sum"])
        tail = subset[subset["valid_for_tail"].eq(1)].groupby("audit_feature_id")["tail_direction_good"].agg(["count", "sum"])
        clean = subset[subset["valid_for_clean"].eq(1)].groupby("audit_feature_id")["clean_direction_good"].agg(["count", "sum"])
        for metric_id, table in [("risk", risk), ("tail", tail), ("clean", clean)]:
            table = table.rename(
                columns={
                    "count": f"{split_type}_{metric_id}_valid_split_count",
                    "sum": f"{split_type}_{metric_id}_good_split_count",
                }
            )
            result = result.merge(table, on="audit_feature_id", how="left")
            count_col = f"{split_type}_{metric_id}_valid_split_count"
            good_col = f"{split_type}_{metric_id}_good_split_count"
            share_col = f"{split_type}_{metric_id}_good_split_share"
            result[count_col] = pd.to_numeric(result[count_col], errors="coerce").fillna(0).astype(int)
            result[good_col] = pd.to_numeric(result[good_col], errors="coerce").fillna(0).astype(int)
            result[share_col] = np.where(result[count_col] > 0, result[good_col] / result[count_col], np.nan)
    result["universal_structure_watch_only"] = (
        result["aggregate_risk_direction_pass"].eq(1)
        & result["aggregate_tail_direction_pass"].eq(1)
        & result["year_risk_valid_split_count"].ge(4)
        & result["year_risk_good_split_share"].ge(0.60)
        & result["exchange_risk_valid_split_count"].ge(3)
        & result["exchange_risk_good_split_share"].ge(0.60)
    ).astype(int)
    result["strategy_rule_allowed"] = 0
    result["true_engine_allowed"] = 0
    result["ab_allowed"] = 0
    return result


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gate_rows = [
        ("stage238_formal_table_exists", int(STAGE238_FORMAL_TABLE_IN.exists()), "Stage238 formal feature table exists"),
        ("stage177_label_contract_exists", int(STAGE177_CONTRACT_IN.exists()), "Stage177 extension label contract exists"),
        ("curve_exists", int(CURVE_IN.exists()), "official curve exists for visual audit"),
        ("join_one_to_one_pass", int(summary["join_one_to_one_pass"]), "219 formal rows bind to 219 label rows"),
        ("all_candidate_features_present", int(summary["candidate_feature_missing_count"] == 0), "all 7 candidate columns present"),
        ("label_trading_rule_allowed", 0, "labels are historical visual/path context only"),
        ("strategy_feature_usable", 0, "Stage238 lock remains in force"),
        ("strategy_rule_created", 0, "read-only audit writes no strategy rule"),
        ("true_engine_run", 0, "read-only audit runs no true engine"),
        ("ab_triggered", 0, "read-only audit triggers no A/B"),
        ("official_config_changed", 0, "official config is untouched"),
        ("order_api_called", 0, "no CTP/SimNow/order API call"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "pass": passed,
                "description": description,
            }
            for gate_id, passed, description in gate_rows
        ]
    )


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage239 is read-only signal-quality audit")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"joined={summary['joined_row_count']} | "
        f"features={summary['candidate_feature_count']} | "
        f"risk_bad={summary['risk_bad_label_count']} | right_tail={summary['right_tail_label_count']} | "
        f"watch_only={summary['universal_structure_watch_only_count']} | strategy_rule=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_heatmap(pivot: pd.DataFrame, title: str, path: Path, cmap: str, vmin: float = 0.0, vmax: float = 1.0) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(idx) for idx in pivot.index], fontsize=8)
    ax.set_title(title)
    ax.set_xlabel("quality quintile; Q5 is predeclared higher quality")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_stability(stability: pd.DataFrame) -> None:
    subset = stability[
        stability["split_type"].isin(["year", "exchange"])
        & stability["valid_for_risk"].eq(1)
    ].copy()
    subset["split_label"] = subset["split_type"] + "=" + subset["split_value"].astype(str)
    pivot = subset.pivot_table(
        index="split_label",
        columns="audit_feature_id",
        values="risk_direction_good",
        aggfunc="mean",
    )
    order = sorted([idx for idx in pivot.index if idx.startswith("year=")]) + sorted(
        [idx for idx in pivot.index if idx.startswith("exchange=")]
    )
    pivot = pivot.reindex(order)
    fig, ax = plt.subplots(figsize=(12, max(4.5, 0.34 * max(1, len(pivot.index)))))
    data = pivot.to_numpy(dtype=float)
    masked = np.ma.masked_invalid(data)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad(color="#d9d9d9")
    image = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns], rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(idx) for idx in pivot.index], fontsize=8)
    ax.set_title("Risk-bad direction stability by year/exchange; green means higher quality had lower risk label")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:.0f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(STABILITY_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_feature_delta(feature_summary: pd.DataFrame) -> None:
    plot_frame = feature_summary.set_index("audit_feature_id")[
        ["q5_minus_q1_risk_bad_rate", "q5_minus_q1_right_tail_rate", "q5_minus_q1_ordinary_clean_rate"]
    ].copy()
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    x = np.arange(len(plot_frame.index))
    width = 0.24
    ax.bar(x - width, plot_frame["q5_minus_q1_risk_bad_rate"], width, label="risk_bad Q5-Q1", color="#d62728")
    ax.bar(x, plot_frame["q5_minus_q1_right_tail_rate"], width, label="right_tail Q5-Q1", color="#2ca02c")
    ax.bar(x + width, plot_frame["q5_minus_q1_ordinary_clean_rate"], width, label="ordinary_clean Q5-Q1", color="#1f77b4")
    ax.axhline(0, color="#111111", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(plot_frame.index, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("rate delta")
    ax.set_title("Top-vs-bottom quality quintile deltas; descriptive only, no threshold selected")
    ax.legend(loc="best", fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FEATURE_DELTA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_label_distribution(label_distribution: pd.DataFrame) -> None:
    labels = ["risk_bad_label", "right_tail_label", "ordinary_clean_label", "low_resolution_label", "runway_ready_label"]
    plot_frame = label_distribution[label_distribution["label_id"].isin(labels)].set_index("label_id")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(plot_frame.index, plot_frame["positive_count"], color=["#d62728", "#2ca02c", "#1f77b4", "#ff7f0e", "#9467bd"])
    for idx, value in enumerate(plot_frame["positive_count"].tolist()):
        ax.text(idx, value + 1, str(int(value)), ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("positive count")
    ax.set_title("Stage177 label/context distribution bound to Stage238 formal rows")
    ax.tick_params(axis="x", labelrotation=25)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(LABEL_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: dict[str, Any],
    feature_summary: pd.DataFrame,
    quintile: pd.DataFrame,
    stability: pd.DataFrame,
    label_distribution: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    top_columns = [
        "feature_id",
        "audit_feature_id",
        "quality_unique_value_count",
        "nonempty_quality_quintile_count",
        "quality_rank_corr_vs_risk_bad",
        "quality_rank_corr_vs_right_tail",
        "q5_minus_q1_risk_bad_rate",
        "q5_minus_q1_right_tail_rate",
        "year_risk_good_split_share",
        "exchange_risk_good_split_share",
        "universal_structure_watch_only",
    ]
    report = f"""# {STAGE} Read-only Universal Signal Quality Audit

## Decision

- decision: `{summary['decision']}`
- joined_row_count: `{summary['joined_row_count']}`
- candidate_feature_count: `{summary['candidate_feature_count']}`
- risk_bad_label_count: `{summary['risk_bad_label_count']}`
- right_tail_label_count: `{summary['right_tail_label_count']}`
- universal_structure_watch_only_count: `{summary['universal_structure_watch_only_count']}`
- strategy_rule_created: `0`
- true_engine_run: `0`
- ab_triggered: `0`

## Method

- 输入只来自 Stage238 formal feature table 与 Stage177 extension label contract。
- 标签只用于只读归因：`risk_bad_label = bottom_loss_visual OR maxdd_context`，`right_tail_label = right_tail_visual`。
- 每个特征先按第一性假设固定质量方向，再分成 5 个等频 rank quintile；不扫阈值、不按年份/品种/方向补丁。
- Spearman/Rank-IC 只用于单调结构审计，不直接生成策略规则。

## Feature Summary

{_md_table(feature_summary[top_columns], max_rows=None)}

## Label Distribution

{_md_table(label_distribution.head(12), max_rows=None)}

## Gate Status

{_md_table(gate_status, max_rows=None)}

## Key Files

- joined: `{JOINED_OUT.relative_to(REPO_DIR)}`
- feature_summary: `{FEATURE_SUMMARY_OUT.relative_to(REPO_DIR)}`
- quintile: `{QUINTILE_OUT.relative_to(REPO_DIR)}`
- stability: `{STABILITY_OUT.relative_to(REPO_DIR)}`
- report: `{REPORT_OUT.relative_to(REPO_DIR)}`

## Visuals

- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`
- `{RISK_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{TAIL_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{STABILITY_HEATMAP_OUT.relative_to(REPO_DIR)}`
- `{FEATURE_DELTA_CHART_OUT.relative_to(REPO_DIR)}`
- `{LABEL_CHART_OUT.relative_to(REPO_DIR)}`

## Notes

- 本阶段不使用最终盈亏训练规则，只审计历史视觉/路径上下文与点时化分钟特征是否存在稳定排序结构。
- 如果某个特征进入 `universal_structure_watch_only=1`，也只是下一阶段人工复核/真引擎设计线索，不是正式候选。
- `strategy_rule_allowed`、`true_engine_allowed`、`ab_allowed` 继续保持 `0`。
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    formal = _read_csv(STAGE238_FORMAL_TABLE_IN)
    contract = _read_csv(STAGE177_CONTRACT_IN)
    stage238_summary = _row(STAGE238_SUMMARY_IN)

    missing_columns = [spec["source_column"] for spec in FEATURE_SPECS if spec["source_column"] not in formal.columns]
    joined = _prepare_joined(formal, contract)
    joined_row_count = int(len(joined))
    join_one_to_one_pass = int(joined_row_count == len(formal) == len(contract) == 219 and joined["priority_class"].notna().all())

    label_distribution = _build_label_distribution(joined)
    quintile, feature_summary = _build_quintile_and_summary(joined)
    stability = _build_stability(joined)
    feature_summary = _attach_stability_summary(feature_summary, stability)

    universal_watch_count = int(feature_summary["universal_structure_watch_only"].sum())
    decision = (
        "stage239_read_only_universal_signal_quality_structure_watch_only_no_rule"
        if universal_watch_count > 0
        else "stage239_read_only_universal_signal_quality_no_stable_structure_no_rule"
    )

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "joined_row_count": joined_row_count,
        "formal_input_row_count": int(len(formal)),
        "label_contract_row_count": int(len(contract)),
        "join_one_to_one_pass": join_one_to_one_pass,
        "candidate_feature_count": len(FEATURE_SPECS),
        "candidate_feature_missing_count": len(missing_columns),
        "missing_candidate_columns": ";".join(missing_columns),
        "risk_bad_label_count": int(joined["risk_bad_label"].sum()),
        "right_tail_label_count": int(joined["right_tail_label"].sum()),
        "ordinary_clean_label_count": int(joined["ordinary_clean_label"].sum()),
        "low_resolution_label_count": int(joined["low_resolution_label"].sum()),
        "event_time_missing_label_count": int(joined["event_time_missing_label"].sum()),
        "runway_ready_label_count": int(joined["runway_ready_label"].sum()),
        "feature_quintile_row_count": int(len(quintile)),
        "feature_stability_row_count": int(len(stability)),
        "universal_structure_watch_only_count": universal_watch_count,
        "strategy_feature_usable": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "official_config_changed": 0,
        "ctp_or_simnow_connected": 0,
        "order_api_called": 0,
        "stage238_strategy_feature_usable": _int(stage238_summary, "strategy_feature_usable", 0),
        "stage238_formal_feature_table_row_written_count": _int(
            stage238_summary, "formal_feature_table_row_written_count", len(formal)
        ),
        "official_curve_initial_equity": float(curve["account_equity"].iloc[0]),
        "official_curve_final_equity": float(curve["account_equity"].iloc[-1]),
        "official_curve_total_return_pct": float((curve["account_equity"].iloc[-1] / curve["account_equity"].iloc[0] - 1) * 100),
        "official_curve_max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "official_curve_broker10_peak_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        "feature_summary_file_written": 1,
        "quintile_audit_file_written": 1,
        "stability_audit_file_written": 1,
        "label_distribution_file_written": 1,
        "visual_file_count": 6,
    }

    gate_status = _gate_status(summary)
    summary_frame = pd.DataFrame([summary])
    _write_csv(summary_frame, SUMMARY_OUT)
    _write_csv(joined, JOINED_OUT)
    _write_csv(feature_summary, FEATURE_SUMMARY_OUT)
    _write_csv(quintile, QUINTILE_OUT)
    _write_csv(stability, STABILITY_OUT)
    _write_csv(label_distribution, LABEL_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, feature_summary, quintile, stability, label_distribution, gate_status)

    risk_pivot = quintile.pivot(index="audit_feature_id", columns="quality_quintile", values="risk_bad_rate")
    tail_pivot = quintile.pivot(index="audit_feature_id", columns="quality_quintile", values="right_tail_rate")
    _plot_official_path(curve, summary)
    _plot_heatmap(risk_pivot, "Risk-bad label rate by predeclared quality quintile", RISK_HEATMAP_OUT, "Reds")
    _plot_heatmap(tail_pivot, "Right-tail label rate by predeclared quality quintile", TAIL_HEATMAP_OUT, "Greens")
    _plot_stability(stability)
    _plot_feature_delta(feature_summary)
    _plot_label_distribution(label_distribution)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
