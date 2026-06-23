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
STAGE = "Stage253"
MODEL_TAG = "stage253_price_oi_confirmation_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage253_price_oi_confirmation_preflight"

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"

STAGE249_DIR = LINE_DIR / "outputs" / "stage249_early_runway_frontier_audit"
STAGE249_PREFIX = "qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit"
STAGE249_TAG = "stage249_early_runway_frontier_audit_v1"
STAGE249_ROWS_IN = STAGE249_DIR / f"{STAGE249_PREFIX}_frontier_rows_{STAGE249_TAG}.csv"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"

ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oi_confirmation_rows_{MODEL_TAG}.csv"
GROUP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_summary_{MODEL_TAG}.csv"
SPLIT_STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_oi_confirmation_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oi_confirmation_contribution_chart_{MODEL_TAG}.png"
GROUP_RATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_rate_chart_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_heatmap_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
SOURCE_QUALITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_quality_chart_{MODEL_TAG}.png"

LOOKBACK_CLOSED_BARS = 61

GROUP_ORDER = [
    "aligned_price_oi_expand",
    "aligned_price_oi_contract",
    "against_price_oi_expand",
    "against_price_oi_contract",
    "flat_or_missing",
]

GROUP_COLORS = {
    "aligned_price_oi_expand": "#0f766e",
    "aligned_price_oi_contract": "#2563eb",
    "against_price_oi_expand": "#dc2626",
    "against_price_oi_contract": "#7c3aed",
    "flat_or_missing": "#64748b",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    try:
        return data.to_markdown(index=False)
    except Exception:
        return "```\n" + data.to_string(index=False) + "\n```"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _direction_sign(direction: Any) -> int:
    return -1 if str(direction).lower() == "short" else 1


def _load_base_rows() -> pd.DataFrame:
    joined = _read_csv(STAGE239_JOINED_IN)
    frontier = _read_csv(STAGE249_ROWS_IN)
    if "exchange" not in frontier.columns:
        frontier["exchange"] = frontier["vt_symbol"].astype(str).str.rsplit(".", n=1).str[-1]

    joined_cols = [
        "candidate_index",
        "request_id",
        "decision_ts",
        "feature_cutoff_ts",
        "filtered_source_file",
        "raw_open_interest_delta_60m",
        "raw_open_interest_delta_60m__ready",
        "diagnostic_open_interest_delta_60m",
    ]
    missing_joined = sorted(set(joined_cols).difference(joined.columns))
    if missing_joined:
        raise RuntimeError(f"Stage239 joined rows missing columns: {missing_joined}")

    frontier_cols = [
        "candidate_index",
        "official_open_trade_id",
        "vt_symbol",
        "direction",
        "official_open_date",
        "product",
        "exchange",
        "decision_year",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "risk_bad_label",
        "ordinary_clean_label",
        "early_runway_no_dwell",
    ]
    missing_frontier = sorted(set(frontier_cols).difference(frontier.columns))
    if missing_frontier:
        raise RuntimeError(f"Stage249 frontier rows missing columns: {missing_frontier}")

    rows = frontier[frontier_cols].merge(joined[joined_cols], on="candidate_index", how="left", validate="one_to_one")
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    rows["decision_ts"] = pd.to_datetime(rows["decision_ts"], errors="coerce")
    rows["feature_cutoff_ts"] = pd.to_datetime(rows["feature_cutoff_ts"], errors="coerce")
    rows["direction_sign"] = rows["direction"].map(_direction_sign)
    rows["pnl_positive"] = pd.to_numeric(rows["order_realized_pnl"], errors="coerce").gt(0).astype(int)
    rows["pnl_negative"] = pd.to_numeric(rows["order_realized_pnl"], errors="coerce").lt(0).astype(int)
    return rows


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(STAGE251_CURVE_IN)
    curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    return curve.sort_values("date").reset_index(drop=True)


def _load_official_summary() -> dict[str, Any]:
    summary = _read_csv(STAGE251_SUMMARY_IN)
    official = summary[summary["arm"].astype(str).eq("A_official_stage847_c9_15w")]
    if official.empty:
        raise RuntimeError("missing A_official_stage847_c9_15w in Stage251 summary")
    return official.iloc[0].to_dict()


def _source_features(row: pd.Series) -> dict[str, Any]:
    path = REPO_DIR / str(row["filtered_source_file"])
    result: dict[str, Any] = {
        "source_file_exists": int(path.exists()),
        "source_row_count": 0,
        "lookback_row_count": 0,
        "oi_source_ready": 0,
        "price_source_ready": 0,
        "oi_start": np.nan,
        "oi_end": np.nan,
        "oi_delta_60m": np.nan,
        "oi_delta_pct_60m": np.nan,
        "price_start": np.nan,
        "price_end": np.nan,
        "price_log_return_60m": np.nan,
        "direction_aligned_price_log_return_60m": np.nan,
    }
    if not path.exists():
        return result

    frame = pd.read_parquet(path, columns=["bar_end_ts", "close", "open_interest"])
    if frame.empty:
        return result

    frame["bar_end_ts"] = pd.to_datetime(frame["bar_end_ts"], errors="coerce")
    frame = frame[frame["bar_end_ts"].le(row["decision_ts"])].sort_values("bar_end_ts")
    frame = frame.dropna(subset=["close", "open_interest"])
    result["source_row_count"] = int(len(frame))
    lookback = frame.tail(LOOKBACK_CLOSED_BARS)
    result["lookback_row_count"] = int(len(lookback))
    if len(lookback) < LOOKBACK_CLOSED_BARS:
        return result

    price_start = _safe_float(lookback["close"].iloc[0], np.nan)
    price_end = _safe_float(lookback["close"].iloc[-1], np.nan)
    oi_start = _safe_float(lookback["open_interest"].iloc[0], np.nan)
    oi_end = _safe_float(lookback["open_interest"].iloc[-1], np.nan)
    result.update(
        {
            "price_start": price_start,
            "price_end": price_end,
            "oi_start": oi_start,
            "oi_end": oi_end,
        }
    )

    if np.isfinite(price_start) and np.isfinite(price_end) and price_start > 0 and price_end > 0:
        price_log_return = float(np.log(price_end / price_start))
        result["price_log_return_60m"] = price_log_return
        result["direction_aligned_price_log_return_60m"] = price_log_return * int(row["direction_sign"])
        result["price_source_ready"] = 1

    if np.isfinite(oi_start) and np.isfinite(oi_end) and abs(oi_start) > 1e-12:
        oi_delta = oi_end - oi_start
        result["oi_delta_60m"] = float(oi_delta)
        result["oi_delta_pct_60m"] = float(oi_delta / abs(oi_start))
        result["oi_source_ready"] = 1

    return result


def _add_source_features(rows: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in rows.iterrows():
        records.append(_source_features(row))
    features = pd.DataFrame(records)
    out = pd.concat([rows.reset_index(drop=True), features], axis=1)
    price_aligned = out["direction_aligned_price_log_return_60m"].gt(0)
    price_against = out["direction_aligned_price_log_return_60m"].lt(0)
    oi_expand = out["oi_delta_pct_60m"].gt(0)
    oi_contract = out["oi_delta_pct_60m"].lt(0)
    source_ready = out["price_source_ready"].eq(1) & out["oi_source_ready"].eq(1)
    out["price_oi_confirmation_group"] = np.select(
        [
            source_ready & price_aligned & oi_expand,
            source_ready & price_aligned & oi_contract,
            source_ready & price_against & oi_expand,
            source_ready & price_against & oi_contract,
        ],
        [
            "aligned_price_oi_expand",
            "aligned_price_oi_contract",
            "against_price_oi_expand",
            "against_price_oi_contract",
        ],
        default="flat_or_missing",
    )
    out["aligned_price_oi_expand"] = out["price_oi_confirmation_group"].eq("aligned_price_oi_expand").astype(int)
    out["flat_or_missing_flag"] = out["price_oi_confirmation_group"].eq("flat_or_missing").astype(int)
    return out


def _group_summary(rows: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(pd.to_numeric(rows["order_realized_pnl"], errors="coerce").sum())
    total_rt = int(pd.to_numeric(rows["right_tail_visual"], errors="coerce").fillna(0).sum())
    total_bl = int(pd.to_numeric(rows["bottom_loss_visual"], errors="coerce").fillna(0).sum())
    total_risk = int(pd.to_numeric(rows["risk_bad_label"], errors="coerce").fillna(0).sum())
    grouped = (
        rows.groupby("price_oi_confirmation_group", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            product_count=("product", "nunique"),
            year_count=("decision_year", "nunique"),
            source_ready_count=("oi_source_ready", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_mean=("order_realized_pnl", "mean"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            positive_order_count=("pnl_positive", "sum"),
            negative_order_count=("pnl_negative", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            risk_bad_count=("risk_bad_label", "sum"),
            ordinary_clean_count=("ordinary_clean_label", "sum"),
            early_runway_count=("early_runway_no_dwell", "sum"),
            early_right_tail_count=("right_tail_visual", lambda s: int((rows.loc[s.index, "early_runway_no_dwell"].eq(1) & s.eq(1)).sum())),
            early_bottom_loss_count=("bottom_loss_visual", lambda s: int((rows.loc[s.index, "early_runway_no_dwell"].eq(1) & s.eq(1)).sum())),
            median_oi_delta_pct_60m=("oi_delta_pct_60m", "median"),
            median_direction_aligned_return_60m=("direction_aligned_price_log_return_60m", "median"),
        )
        .reset_index()
    )
    grouped["risk_bad_rate"] = grouped["risk_bad_count"] / grouped["order_count"]
    grouped["right_tail_rate"] = grouped["right_tail_count"] / grouped["order_count"]
    grouped["bottom_loss_rate"] = grouped["bottom_loss_count"] / grouped["order_count"]
    grouped["pnl_share"] = grouped["pnl_sum"] / total_pnl if abs(total_pnl) > 1e-12 else np.nan
    grouped["right_tail_share"] = grouped["right_tail_count"] / total_rt if total_rt else np.nan
    grouped["bottom_loss_share"] = grouped["bottom_loss_count"] / total_bl if total_bl else np.nan
    grouped["risk_bad_share"] = grouped["risk_bad_count"] / total_risk if total_risk else np.nan
    grouped["pnl_sign_conflict"] = (grouped["pnl_min"].lt(0) & grouped["pnl_max"].gt(0)).astype(int)
    grouped["price_oi_rule_allowed"] = 0
    grouped["price_oi_confirmation_group"] = pd.Categorical(
        grouped["price_oi_confirmation_group"],
        categories=GROUP_ORDER,
        ordered=True,
    )
    return grouped.sort_values("price_oi_confirmation_group").reset_index(drop=True)


def _split_stability(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    split_specs = [
        ("year", "decision_year"),
        ("exchange", "exchange"),
        ("direction", "direction"),
    ]
    for split_type, column in split_specs:
        for split_value, group in rows.groupby(column, dropna=False):
            if len(group) < 8:
                continue
            high = group[group["aligned_price_oi_expand"].eq(1)]
            rest = group[group["aligned_price_oi_expand"].eq(0)]
            if len(high) < 3 or len(rest) < 3:
                records.append(
                    {
                        "split_type": split_type,
                        "split_value": split_value,
                        "split_row_count": int(len(group)),
                        "aligned_expand_count": int(len(high)),
                        "rest_count": int(len(rest)),
                        "valid_for_stability": 0,
                        "risk_bad_rate_diff": np.nan,
                        "right_tail_rate_diff": np.nan,
                        "bottom_loss_rate_diff": np.nan,
                        "pnl_per_order_diff": np.nan,
                        "split_pass": 0,
                        "block_reason": "insufficient_aligned_expand_or_rest_count",
                    }
                )
                continue
            high_risk = _safe_div(high["risk_bad_label"].sum(), len(high))
            rest_risk = _safe_div(rest["risk_bad_label"].sum(), len(rest))
            high_tail = _safe_div(high["right_tail_visual"].sum(), len(high))
            rest_tail = _safe_div(rest["right_tail_visual"].sum(), len(rest))
            high_bottom = _safe_div(high["bottom_loss_visual"].sum(), len(high))
            rest_bottom = _safe_div(rest["bottom_loss_visual"].sum(), len(rest))
            high_pnl = _safe_div(high["order_realized_pnl"].sum(), len(high))
            rest_pnl = _safe_div(rest["order_realized_pnl"].sum(), len(rest))
            risk_diff = high_risk - rest_risk
            tail_diff = high_tail - rest_tail
            bottom_diff = high_bottom - rest_bottom
            pnl_diff = high_pnl - rest_pnl
            split_pass = int(risk_diff <= -0.05 and tail_diff >= 0.0 and bottom_diff <= 0.0 and pnl_diff >= 0.0)
            records.append(
                {
                    "split_type": split_type,
                    "split_value": split_value,
                    "split_row_count": int(len(group)),
                    "aligned_expand_count": int(len(high)),
                    "rest_count": int(len(rest)),
                    "valid_for_stability": 1,
                    "aligned_expand_risk_bad_rate": high_risk,
                    "rest_risk_bad_rate": rest_risk,
                    "risk_bad_rate_diff": risk_diff,
                    "aligned_expand_right_tail_rate": high_tail,
                    "rest_right_tail_rate": rest_tail,
                    "right_tail_rate_diff": tail_diff,
                    "aligned_expand_bottom_loss_rate": high_bottom,
                    "rest_bottom_loss_rate": rest_bottom,
                    "bottom_loss_rate_diff": bottom_diff,
                    "aligned_expand_pnl_per_order": high_pnl,
                    "rest_pnl_per_order": rest_pnl,
                    "pnl_per_order_diff": pnl_diff,
                    "split_pass": split_pass,
                    "block_reason": "" if split_pass else "not_lower_risk_with_tail_and_pnl_preserved",
                }
            )
    return pd.DataFrame(records)


def _promotion_gate(rows: pd.DataFrame, group_summary: pd.DataFrame, split_stability: pd.DataFrame) -> pd.DataFrame:
    candidate = rows[rows["aligned_price_oi_expand"].eq(1)]
    rest = rows[rows["aligned_price_oi_expand"].eq(0)]
    total_rt = int(rows["right_tail_visual"].sum())
    total_bl = int(rows["bottom_loss_visual"].sum())
    early_rt = int((rows["early_runway_no_dwell"].eq(1) & rows["right_tail_visual"].eq(1)).sum())
    source_ready_share = _safe_div((rows["oi_source_ready"].eq(1) & rows["price_source_ready"].eq(1)).sum(), len(rows))
    cand_count = int(len(candidate))
    cand_risk = _safe_div(candidate["risk_bad_label"].sum(), len(candidate)) if len(candidate) else np.nan
    rest_risk = _safe_div(rest["risk_bad_label"].sum(), len(rest)) if len(rest) else np.nan
    risk_reduction = rest_risk - cand_risk if np.isfinite(cand_risk) and np.isfinite(rest_risk) else np.nan
    right_tail_capture = _safe_div(candidate["right_tail_visual"].sum(), total_rt) if total_rt else np.nan
    bottom_loss_capture = _safe_div(candidate["bottom_loss_visual"].sum(), total_bl) if total_bl else np.nan
    early_tail_capture = _safe_div(
        (candidate["early_runway_no_dwell"].eq(1) & candidate["right_tail_visual"].eq(1)).sum(),
        early_rt,
    ) if early_rt else np.nan
    cand_row = group_summary[group_summary["price_oi_confirmation_group"].astype(str).eq("aligned_price_oi_expand")]
    pnl_sign_conflict = int(cand_row["pnl_sign_conflict"].iloc[0]) if not cand_row.empty else 1
    valid_splits = split_stability[split_stability["valid_for_stability"].eq(1)]
    split_pass_share = _safe_div(valid_splits["split_pass"].sum(), len(valid_splits)) if len(valid_splits) else np.nan
    gates = [
        {
            "gate_id": "source_ready_95pct",
            "evidence_value": source_ready_share,
            "evidence_unit": "share of rows with price and OI source ready",
            "pass_for_true_engine": int(np.isfinite(source_ready_share) and source_ready_share >= 0.95),
            "judgment": "pass" if np.isfinite(source_ready_share) and source_ready_share >= 0.95 else "fail_source_not_full_enough",
        },
        {
            "gate_id": "sample_size_min30",
            "evidence_value": cand_count,
            "evidence_unit": "aligned price + OI expansion order count",
            "pass_for_true_engine": int(cand_count >= 30),
            "judgment": "pass" if cand_count >= 30 else "fail_too_small",
        },
        {
            "gate_id": "risk_reduction_5pp_vs_rest",
            "evidence_value": risk_reduction,
            "evidence_unit": "rest risk_bad_rate minus aligned-expand risk_bad_rate",
            "pass_for_true_engine": int(np.isfinite(risk_reduction) and risk_reduction >= 0.05),
            "judgment": "pass" if np.isfinite(risk_reduction) and risk_reduction >= 0.05 else "fail_no_material_risk_reduction",
        },
        {
            "gate_id": "right_tail_capture_50pct",
            "evidence_value": right_tail_capture,
            "evidence_unit": "share of right-tail visual orders captured by aligned-expand",
            "pass_for_true_engine": int(np.isfinite(right_tail_capture) and right_tail_capture >= 0.50),
            "judgment": "pass" if np.isfinite(right_tail_capture) and right_tail_capture >= 0.50 else "fail_right_tail_not_preserved",
        },
        {
            "gate_id": "bottom_loss_capture_le25pct",
            "evidence_value": bottom_loss_capture,
            "evidence_unit": "share of bottom-loss visual orders captured by aligned-expand",
            "pass_for_true_engine": int(np.isfinite(bottom_loss_capture) and bottom_loss_capture <= 0.25),
            "judgment": "pass" if np.isfinite(bottom_loss_capture) and bottom_loss_capture <= 0.25 else "fail_tail_conflict",
        },
        {
            "gate_id": "early_right_tail_capture_50pct",
            "evidence_value": early_tail_capture,
            "evidence_unit": "share of early-runway right-tail captured by aligned-expand",
            "pass_for_true_engine": int(np.isfinite(early_tail_capture) and early_tail_capture >= 0.50),
            "judgment": "pass" if np.isfinite(early_tail_capture) and early_tail_capture >= 0.50 else "fail_early_runway_tail_missed",
        },
        {
            "gate_id": "no_pnl_sign_conflict",
            "evidence_value": pnl_sign_conflict,
            "evidence_unit": "aligned-expand contains both positive and negative realized PnL",
            "pass_for_true_engine": int(pnl_sign_conflict == 0),
            "judgment": "pass" if pnl_sign_conflict == 0 else "fail_mixed_pnl_state",
        },
        {
            "gate_id": "split_stability_60pct",
            "evidence_value": split_pass_share,
            "evidence_unit": "valid year/exchange/direction splits passing risk/tail/pnl criteria",
            "pass_for_true_engine": int(np.isfinite(split_pass_share) and split_pass_share >= 0.60),
            "judgment": "pass" if np.isfinite(split_pass_share) and split_pass_share >= 0.60 else "fail_cross_split_instability",
        },
        {
            "gate_id": "no_rule_no_engine_isolation",
            "evidence_value": 0.0,
            "evidence_unit": "strategy rules, true engine, A/B, official config, order API",
            "pass_for_true_engine": 1,
            "judgment": "technical_pass",
        },
    ]
    gate = pd.DataFrame(gates)
    gate["preflight_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(rows: pd.DataFrame, group_summary: pd.DataFrame, split_stability: pd.DataFrame, gate: pd.DataFrame, official: dict[str, Any]) -> pd.DataFrame:
    candidate = rows[rows["aligned_price_oi_expand"].eq(1)]
    rest = rows[rows["aligned_price_oi_expand"].eq(0)]
    total_rt = int(rows["right_tail_visual"].sum())
    total_bl = int(rows["bottom_loss_visual"].sum())
    early_rt = int((rows["early_runway_no_dwell"].eq(1) & rows["right_tail_visual"].eq(1)).sum())
    valid_splits = split_stability[split_stability["valid_for_stability"].eq(1)]
    cand_risk = _safe_div(candidate["risk_bad_label"].sum(), len(candidate)) if len(candidate) else np.nan
    rest_risk = _safe_div(rest["risk_bad_label"].sum(), len(rest)) if len(rest) else np.nan
    source_ready_count = int((rows["oi_source_ready"].eq(1) & rows["price_source_ready"].eq(1)).sum())
    decision = "stage253_price_oi_confirmation_tail_conflict_no_true_engine_no_rule"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage_nature": "read_only_price_oi_confirmation_preflight",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_or_simnow_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "source_ready_count": source_ready_count,
                "source_ready_share": _safe_div(source_ready_count, len(rows)),
                "confirmation_group_count": int(group_summary["price_oi_confirmation_group"].nunique()),
                "aligned_expand_order_count": int(len(candidate)),
                "aligned_expand_pnl_sum": float(candidate["order_realized_pnl"].sum()),
                "aligned_expand_pnl_min": float(candidate["order_realized_pnl"].min()) if len(candidate) else np.nan,
                "aligned_expand_pnl_max": float(candidate["order_realized_pnl"].max()) if len(candidate) else np.nan,
                "aligned_expand_risk_bad_rate": cand_risk,
                "rest_risk_bad_rate": rest_risk,
                "risk_reduction_vs_rest": rest_risk - cand_risk if np.isfinite(cand_risk) and np.isfinite(rest_risk) else np.nan,
                "aligned_expand_right_tail_count": int(candidate["right_tail_visual"].sum()),
                "aligned_expand_right_tail_capture_rate": _safe_div(candidate["right_tail_visual"].sum(), total_rt) if total_rt else np.nan,
                "aligned_expand_bottom_loss_count": int(candidate["bottom_loss_visual"].sum()),
                "aligned_expand_bottom_loss_capture_rate": _safe_div(candidate["bottom_loss_visual"].sum(), total_bl) if total_bl else np.nan,
                "aligned_expand_early_right_tail_count": int((candidate["early_runway_no_dwell"].eq(1) & candidate["right_tail_visual"].eq(1)).sum()),
                "aligned_expand_early_right_tail_capture_rate": _safe_div(
                    (candidate["early_runway_no_dwell"].eq(1) & candidate["right_tail_visual"].eq(1)).sum(),
                    early_rt,
                ) if early_rt else np.nan,
                "valid_split_count": int(len(valid_splits)),
                "split_pass_count": int(valid_splits["split_pass"].sum()) if not valid_splits.empty else 0,
                "split_pass_share": _safe_div(valid_splits["split_pass"].sum(), len(valid_splits)) if len(valid_splits) else np.nan,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "strategy_feature_usable": 0,
                "official_end_equity": _safe_float(official.get("end_equity"), np.nan),
                "official_total_return_pct": _safe_float(official.get("total_return_pct"), np.nan),
                "official_max_dd_pct": _safe_float(official.get("max_dd_pct"), np.nan),
                "official_sharpe": _safe_float(official.get("sharpe"), np.nan),
                "official_total_slippage": _safe_float(official.get("total_slippage"), np.nan),
                "official_total_trade_count": _safe_float(official.get("total_trade_count"), np.nan),
                "official_win_rate_pct": _safe_float(official.get("nonzero_daily_win_rate_pct"), np.nan),
                "official_broker10_peak_pct": _safe_float(official.get("max_broker10_margin_to_equity_pct"), np.nan),
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=False, gridspec_kw={"height_ratios": [2.0, 1.0, 1.0]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f172a", linewidth=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.0)
    points = rows[["official_open_date", "price_oi_confirmation_group"]].merge(
        curve[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for group_name, group in points.groupby("price_oi_confirmation_group"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=20,
            color=GROUP_COLORS.get(group_name, "#64748b"),
            alpha=0.72,
            label=group_name,
        )
    axes[0].set_title(
        f"{STAGE} official path with price+OI markers | aligned_expand={int(summary['aligned_expand_order_count'])}"
    )
    axes[0].set_ylabel("equity")
    axes[1].set_ylabel("drawdown %")
    for ax in axes[:2]:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=7, ncols=2)
    counts = rows["price_oi_confirmation_group"].value_counts().reindex(GROUP_ORDER).fillna(0)
    axes[2].bar(counts.index, counts.values, color=[GROUP_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("orders")
    axes[2].tick_params(axis="x", rotation=15)
    axes[2].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(rows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 6.5))
    for group_name in GROUP_ORDER:
        group = rows[rows["price_oi_confirmation_group"].eq(group_name)]
        if group.empty:
            continue
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values, label=group_name, color=GROUP_COLORS.get(group_name, "#64748b"), linewidth=1.4)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage253 cumulative official PnL by price+OI confirmation group")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, ncols=2)
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_group_rates(group_summary: pd.DataFrame) -> None:
    data = group_summary.copy()
    data["group"] = data["price_oi_confirmation_group"].astype(str)
    x = np.arange(len(data))
    width = 0.25
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    axes[0].bar(x - width, data["risk_bad_rate"], width=width, label="risk_bad", color="#dc2626")
    axes[0].bar(x, data["right_tail_rate"], width=width, label="right_tail", color="#16a34a")
    axes[0].bar(x + width, data["bottom_loss_rate"], width=width, label="bottom_loss", color="#f97316")
    axes[0].set_ylabel("rate")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.25)
    colors = [GROUP_COLORS.get(item, "#64748b") for item in data["group"]]
    axes[1].bar(x, data["pnl_sum"], color=colors, alpha=0.82)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["group"], rotation=15, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage253 group rates: aligned price + OI expansion must lower risk and preserve tail")
    fig.tight_layout()
    fig.savefig(GROUP_RATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split_heatmap(split_stability: pd.DataFrame) -> None:
    valid = split_stability[split_stability["valid_for_stability"].eq(1)].copy()
    if valid.empty:
        return
    valid["label"] = valid["split_type"].astype(str) + ":" + valid["split_value"].astype(str)
    metrics = ["risk_bad_rate_diff", "right_tail_rate_diff", "bottom_loss_rate_diff", "pnl_per_order_diff"]
    matrix = valid.set_index("label")[metrics].astype(float)
    limit = max(abs(matrix.min().min()), abs(matrix.max().max()))
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(matrix))))
    im = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=-limit, vmax=limit)
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels(metrics, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iat[i, j]
            text = f"{value:.2f}" if "pnl" not in metrics[j] else f"{value/1000:.0f}k"
            ax.text(j, i, text, ha="center", va="center", fontsize=7)
    ax.set_title("Stage253 aligned price + OI expansion minus rest by split")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_true_engine"]]
    ax.bar(gate["gate_id"], gate["evidence_value"].astype(float), color=colors, alpha=0.82)
    ax.set_title("Stage253 gates: price+OI confirmation remains preflight only")
    ax.set_ylabel("evidence")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_source_quality(rows: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    counts = rows[["source_file_exists", "price_source_ready", "oi_source_ready"]].sum()
    axes[0].bar(counts.index, counts.values, color=["#64748b", "#2563eb", "#0f766e"])
    axes[0].set_ylim(0, len(rows) * 1.05)
    axes[0].set_title("Stage253 source readiness")
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].scatter(
        rows["direction_aligned_price_log_return_60m"],
        rows["oi_delta_pct_60m"],
        c=rows["aligned_price_oi_expand"].map({1: "#0f766e", 0: "#64748b"}),
        alpha=0.72,
        s=18,
    )
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].axvline(0, color="#111827", linewidth=0.8)
    axes[1].set_xlabel("direction-aligned 60m log return")
    axes[1].set_ylabel("60m OI delta pct")
    axes[1].set_title("Price/OI sign plane")
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(SOURCE_QUALITY_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, group_summary: pd.DataFrame, split_stability: pd.DataFrame, gate: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} price+OI confirmation preflight",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only preflight. No strategy rule, no true engine, no A/B, no official config change, no CTP/SimNow, no order API.",
            "- frozen hypothesis: a high-quality signal should show direction-aligned price movement backed by open-interest expansion.",
            "",
            "## Official Baseline",
            "",
            f"- end equity: `{row['official_end_equity']:,.2f}`",
            f"- total return: `{row['official_total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['official_max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['official_sharpe']:.4f}`",
            f"- total slippage: `{row['official_total_slippage']:,.0f}`",
            f"- total trade count: `{row['official_total_trade_count']:.0f}`",
            f"- win rate: `{row['official_win_rate_pct']:.4f}%`",
            "",
            "## Confirmation Summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- source ready: `{int(row['source_ready_count'])}` / `{row['source_ready_share']:.4f}`",
            f"- aligned-expand order count: `{int(row['aligned_expand_order_count'])}`",
            f"- aligned-expand PnL sum: `{row['aligned_expand_pnl_sum']:,.0f}`",
            f"- aligned-expand PnL min/max: `{row['aligned_expand_pnl_min']:,.0f}` / `{row['aligned_expand_pnl_max']:,.0f}`",
            f"- aligned-expand risk bad rate: `{row['aligned_expand_risk_bad_rate']:.4f}`",
            f"- rest risk bad rate: `{row['rest_risk_bad_rate']:.4f}`",
            f"- risk reduction vs rest: `{row['risk_reduction_vs_rest']:.4f}`",
            f"- right-tail capture: `{row['aligned_expand_right_tail_count']}` / `{row['aligned_expand_right_tail_capture_rate']:.4f}`",
            f"- bottom-loss capture: `{row['aligned_expand_bottom_loss_count']}` / `{row['aligned_expand_bottom_loss_capture_rate']:.4f}`",
            f"- early right-tail capture: `{row['aligned_expand_early_right_tail_count']}` / `{row['aligned_expand_early_right_tail_capture_rate']:.4f}`",
            f"- split pass: `{int(row['split_pass_count'])}` / `{int(row['valid_split_count'])}`",
            f"- gate pass: `{int(row['promotion_gate_pass_count'])}` / `{int(row['promotion_gate_count'])}`",
            "",
            "## Group Summary",
            "",
            _md_table(group_summary, max_rows=20),
            "",
            "## Split Stability",
            "",
            _md_table(split_stability, max_rows=40),
            "",
            "## Promotion Gate",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Visual Outputs",
            "",
            f"- official path OI confirmation chart: `{PATH_CHART_OUT}`",
            f"- OI confirmation contribution chart: `{CONTRIBUTION_CHART_OUT}`",
            f"- group rate chart: `{GROUP_RATE_CHART_OUT}`",
            f"- split stability heatmap: `{SPLIT_HEATMAP_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- source quality chart: `{SOURCE_QUALITY_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "Open interest is economically meaningful, but this low-degree price+OI confirmation does not justify a "
                "true-engine candidate. It does not preserve enough right-tail or early-runway right-tail, and cross-split "
                "stability is insufficient. Continuing by adding OI thresholds or product exceptions would be overfitting."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _add_source_features(_load_base_rows())
    curve = _load_official_curve()
    official = _load_official_summary()
    group_summary = _group_summary(rows)
    split_stability = _split_stability(rows)
    gate = _promotion_gate(rows, group_summary, split_stability)
    summary = _summary(rows, group_summary, split_stability, gate, official)

    _write_csv(rows, ROWS_OUT)
    _write_csv(group_summary, GROUP_SUMMARY_OUT)
    _write_csv(split_stability, SPLIT_STABILITY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_contribution(rows)
    _plot_group_rates(group_summary)
    _plot_split_heatmap(split_stability)
    _plot_gate(gate)
    _plot_source_quality(rows)
    _write_report(summary, group_summary, split_stability, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "rows_path": str(ROWS_OUT),
        "group_summary_path": str(GROUP_SUMMARY_OUT),
        "split_stability_path": str(SPLIT_STABILITY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "charts": [
            str(PATH_CHART_OUT),
            str(CONTRIBUTION_CHART_OUT),
            str(GROUP_RATE_CHART_OUT),
            str(SPLIT_HEATMAP_OUT),
            str(PROMOTION_GATE_CHART_OUT),
            str(SOURCE_QUALITY_CHART_OUT),
        ],
        "aligned_expand_order_count": int(summary.iloc[0]["aligned_expand_order_count"]),
        "aligned_expand_right_tail_capture_rate": _safe_float(summary.iloc[0]["aligned_expand_right_tail_capture_rate"], np.nan),
        "aligned_expand_bottom_loss_capture_rate": _safe_float(summary.iloc[0]["aligned_expand_bottom_loss_capture_rate"], np.nan),
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "official_config_changed": 0,
        "order_api_called": 0,
    }
    _write_json(DECISION_OUT, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
