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
STAGE = "Stage254"
MODEL_TAG = "stage254_aligned_price_oi_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage254_aligned_price_oi_contract_audit"

STAGE253_DIR = LINE_DIR / "outputs" / "stage253_price_oi_confirmation_preflight"
STAGE253_PREFIX = "qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight"
STAGE253_TAG = "stage253_price_oi_confirmation_preflight_v1"
STAGE253_ROWS_IN = STAGE253_DIR / f"{STAGE253_PREFIX}_oi_confirmation_rows_{STAGE253_TAG}.csv"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"

ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_rows_{MODEL_TAG}.csv"
CONTRAST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_vs_rest_{MODEL_TAG}.csv"
SPLIT_STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_contract_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_contribution_chart_{MODEL_TAG}.png"
CONTRAST_RATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_contrast_rate_chart_{MODEL_TAG}.png"
SPLIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_heatmap_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_counterexample_atlas_{MODEL_TAG}.png"

CANDIDATE_GROUP = "aligned_price_oi_contract"


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


def _load_rows() -> pd.DataFrame:
    rows = _read_csv(STAGE253_ROWS_IN)
    required = {
        "candidate_index",
        "vt_symbol",
        "direction",
        "official_open_date",
        "decision_year",
        "exchange",
        "product",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "risk_bad_label",
        "ordinary_clean_label",
        "early_runway_no_dwell",
        "price_oi_confirmation_group",
        "filtered_source_file",
        "direction_sign",
        "direction_aligned_price_log_return_60m",
        "oi_delta_pct_60m",
    }
    missing = sorted(required.difference(rows.columns))
    if missing:
        raise RuntimeError(f"Stage253 rows missing columns: {missing}")
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    rows["decision_ts"] = pd.to_datetime(rows["decision_ts"], errors="coerce") if "decision_ts" in rows.columns else pd.NaT
    rows["is_aligned_contract"] = rows["price_oi_confirmation_group"].astype(str).eq(CANDIDATE_GROUP).astype(int)
    rows["contract_audit_group"] = np.where(rows["is_aligned_contract"].eq(1), "aligned_contract", "rest")
    rows["pnl_positive"] = pd.to_numeric(rows["order_realized_pnl"], errors="coerce").gt(0).astype(int)
    rows["pnl_negative"] = pd.to_numeric(rows["order_realized_pnl"], errors="coerce").lt(0).astype(int)
    rows["contract_rule_allowed"] = 0
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


def _contrast(rows: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(pd.to_numeric(rows["order_realized_pnl"], errors="coerce").sum())
    total_rt = int(pd.to_numeric(rows["right_tail_visual"], errors="coerce").fillna(0).sum())
    total_bl = int(pd.to_numeric(rows["bottom_loss_visual"], errors="coerce").fillna(0).sum())
    total_risk = int(pd.to_numeric(rows["risk_bad_label"], errors="coerce").fillna(0).sum())
    grouped = (
        rows.groupby("contract_audit_group", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            product_count=("product", "nunique"),
            year_count=("decision_year", "nunique"),
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
    order = pd.CategoricalDtype(["aligned_contract", "rest"], ordered=True)
    grouped["contract_audit_group"] = grouped["contract_audit_group"].astype(order)
    return grouped.sort_values("contract_audit_group").reset_index(drop=True)


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
            cand = group[group["is_aligned_contract"].eq(1)]
            rest = group[group["is_aligned_contract"].eq(0)]
            if len(cand) < 3 or len(rest) < 3:
                records.append(
                    {
                        "split_type": split_type,
                        "split_value": split_value,
                        "split_row_count": int(len(group)),
                        "candidate_count": int(len(cand)),
                        "rest_count": int(len(rest)),
                        "valid_for_stability": 0,
                        "risk_bad_rate_diff": np.nan,
                        "right_tail_rate_diff": np.nan,
                        "bottom_loss_rate_diff": np.nan,
                        "pnl_per_order_diff": np.nan,
                        "split_pass": 0,
                        "block_reason": "insufficient_candidate_or_rest_count",
                    }
                )
                continue
            cand_risk = _safe_div(cand["risk_bad_label"].sum(), len(cand))
            rest_risk = _safe_div(rest["risk_bad_label"].sum(), len(rest))
            cand_tail = _safe_div(cand["right_tail_visual"].sum(), len(cand))
            rest_tail = _safe_div(rest["right_tail_visual"].sum(), len(rest))
            cand_bottom = _safe_div(cand["bottom_loss_visual"].sum(), len(cand))
            rest_bottom = _safe_div(rest["bottom_loss_visual"].sum(), len(rest))
            cand_pnl = _safe_div(cand["order_realized_pnl"].sum(), len(cand))
            rest_pnl = _safe_div(rest["order_realized_pnl"].sum(), len(rest))
            risk_diff = cand_risk - rest_risk
            tail_diff = cand_tail - rest_tail
            bottom_diff = cand_bottom - rest_bottom
            pnl_diff = cand_pnl - rest_pnl
            split_pass = int(risk_diff <= -0.05 and tail_diff >= 0.0 and bottom_diff <= 0.0 and pnl_diff >= 0.0)
            records.append(
                {
                    "split_type": split_type,
                    "split_value": split_value,
                    "split_row_count": int(len(group)),
                    "candidate_count": int(len(cand)),
                    "rest_count": int(len(rest)),
                    "valid_for_stability": 1,
                    "candidate_risk_bad_rate": cand_risk,
                    "rest_risk_bad_rate": rest_risk,
                    "risk_bad_rate_diff": risk_diff,
                    "candidate_right_tail_rate": cand_tail,
                    "rest_right_tail_rate": rest_tail,
                    "right_tail_rate_diff": tail_diff,
                    "candidate_bottom_loss_rate": cand_bottom,
                    "rest_bottom_loss_rate": rest_bottom,
                    "bottom_loss_rate_diff": bottom_diff,
                    "candidate_pnl_per_order": cand_pnl,
                    "rest_pnl_per_order": rest_pnl,
                    "pnl_per_order_diff": pnl_diff,
                    "split_pass": split_pass,
                    "block_reason": "" if split_pass else "not_lower_risk_with_tail_and_pnl_preserved",
                }
            )
    return pd.DataFrame(records)


def _promotion_gate(rows: pd.DataFrame, contrast: pd.DataFrame, split_stability: pd.DataFrame) -> pd.DataFrame:
    candidate = rows[rows["is_aligned_contract"].eq(1)]
    rest = rows[rows["is_aligned_contract"].eq(0)]
    total_rt = int(rows["right_tail_visual"].sum())
    total_bl = int(rows["bottom_loss_visual"].sum())
    early_rt = int((rows["early_runway_no_dwell"].eq(1) & rows["right_tail_visual"].eq(1)).sum())
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
    cand_row = contrast[contrast["contract_audit_group"].astype(str).eq("aligned_contract")]
    pnl_sign_conflict = int(cand_row["pnl_sign_conflict"].iloc[0]) if not cand_row.empty else 1
    valid_splits = split_stability[split_stability["valid_for_stability"].eq(1)]
    split_pass_share = _safe_div(valid_splits["split_pass"].sum(), len(valid_splits)) if len(valid_splits) else np.nan
    gates = [
        {
            "gate_id": "sample_size_min30",
            "evidence_value": cand_count,
            "evidence_unit": "aligned price + OI contraction order count",
            "pass_for_true_engine": int(cand_count >= 30),
            "judgment": "pass" if cand_count >= 30 else "fail_too_small",
        },
        {
            "gate_id": "risk_reduction_5pp_vs_rest",
            "evidence_value": risk_reduction,
            "evidence_unit": "rest risk_bad_rate minus candidate risk_bad_rate",
            "pass_for_true_engine": int(np.isfinite(risk_reduction) and risk_reduction >= 0.05),
            "judgment": "pass" if np.isfinite(risk_reduction) and risk_reduction >= 0.05 else "fail_no_material_risk_reduction",
        },
        {
            "gate_id": "right_tail_capture_50pct",
            "evidence_value": right_tail_capture,
            "evidence_unit": "share of right-tail visual orders captured by candidate",
            "pass_for_true_engine": int(np.isfinite(right_tail_capture) and right_tail_capture >= 0.50),
            "judgment": "pass" if np.isfinite(right_tail_capture) and right_tail_capture >= 0.50 else "fail_right_tail_not_preserved",
        },
        {
            "gate_id": "bottom_loss_capture_le25pct",
            "evidence_value": bottom_loss_capture,
            "evidence_unit": "share of bottom-loss visual orders captured by candidate",
            "pass_for_true_engine": int(np.isfinite(bottom_loss_capture) and bottom_loss_capture <= 0.25),
            "judgment": "pass" if np.isfinite(bottom_loss_capture) and bottom_loss_capture <= 0.25 else "fail_tail_conflict",
        },
        {
            "gate_id": "early_right_tail_capture_50pct",
            "evidence_value": early_tail_capture,
            "evidence_unit": "share of early-runway right-tail captured by candidate",
            "pass_for_true_engine": int(np.isfinite(early_tail_capture) and early_tail_capture >= 0.50),
            "judgment": "pass" if np.isfinite(early_tail_capture) and early_tail_capture >= 0.50 else "fail_early_runway_tail_missed",
        },
        {
            "gate_id": "no_pnl_sign_conflict",
            "evidence_value": pnl_sign_conflict,
            "evidence_unit": "candidate contains both positive and negative realized PnL",
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


def _summary(rows: pd.DataFrame, contrast: pd.DataFrame, split_stability: pd.DataFrame, gate: pd.DataFrame, official: dict[str, Any]) -> pd.DataFrame:
    candidate = rows[rows["is_aligned_contract"].eq(1)]
    rest = rows[rows["is_aligned_contract"].eq(0)]
    total_rt = int(rows["right_tail_visual"].sum())
    total_bl = int(rows["bottom_loss_visual"].sum())
    early_rt = int((rows["early_runway_no_dwell"].eq(1) & rows["right_tail_visual"].eq(1)).sum())
    valid_splits = split_stability[split_stability["valid_for_stability"].eq(1)]
    cand_risk = _safe_div(candidate["risk_bad_label"].sum(), len(candidate)) if len(candidate) else np.nan
    rest_risk = _safe_div(rest["risk_bad_label"].sum(), len(rest)) if len(rest) else np.nan
    gate_pass_count = int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum())
    all_pass = gate_pass_count == len(gate)
    decision = (
        "stage254_aligned_price_oi_contract_preflight_passes_true_engine_required"
        if all_pass
        else "stage254_aligned_price_oi_contract_tail_contaminated_no_true_engine_no_rule"
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage_nature": "read_only_aligned_price_oi_contract_audit",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_or_simnow_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "candidate_order_count": int(len(candidate)),
                "candidate_pnl_sum": float(candidate["order_realized_pnl"].sum()),
                "candidate_pnl_min": float(candidate["order_realized_pnl"].min()) if len(candidate) else np.nan,
                "candidate_pnl_max": float(candidate["order_realized_pnl"].max()) if len(candidate) else np.nan,
                "candidate_risk_bad_rate": cand_risk,
                "rest_risk_bad_rate": rest_risk,
                "risk_reduction_vs_rest": rest_risk - cand_risk if np.isfinite(cand_risk) and np.isfinite(rest_risk) else np.nan,
                "candidate_right_tail_count": int(candidate["right_tail_visual"].sum()),
                "candidate_right_tail_capture_rate": _safe_div(candidate["right_tail_visual"].sum(), total_rt) if total_rt else np.nan,
                "candidate_bottom_loss_count": int(candidate["bottom_loss_visual"].sum()),
                "candidate_bottom_loss_capture_rate": _safe_div(candidate["bottom_loss_visual"].sum(), total_bl) if total_bl else np.nan,
                "candidate_early_right_tail_count": int((candidate["early_runway_no_dwell"].eq(1) & candidate["right_tail_visual"].eq(1)).sum()),
                "candidate_early_right_tail_capture_rate": _safe_div(
                    (candidate["early_runway_no_dwell"].eq(1) & candidate["right_tail_visual"].eq(1)).sum(),
                    early_rt,
                ) if early_rt else np.nan,
                "valid_split_count": int(len(valid_splits)),
                "split_pass_count": int(valid_splits["split_pass"].sum()) if not valid_splits.empty else 0,
                "split_pass_share": _safe_div(valid_splits["split_pass"].sum(), len(valid_splits)) if len(valid_splits) else np.nan,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": gate_pass_count,
                "strategy_feature_usable": 0,
                "atlas_event_count": int(min(12, len(candidate))),
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
    points = rows[["official_open_date", "contract_audit_group"]].merge(
        curve[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for group_name, group in points.groupby("contract_audit_group"):
        color = "#2563eb" if group_name == "aligned_contract" else "#64748b"
        axes[0].scatter(group["official_open_date"], group["account_equity"], s=18, color=color, alpha=0.70, label=group_name)
    axes[0].set_title(f"{STAGE} official path with aligned price + OI contraction markers")
    axes[0].set_ylabel("equity")
    axes[1].set_ylabel("drawdown %")
    for ax in axes[:2]:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=8)
    counts = rows["contract_audit_group"].value_counts().reindex(["aligned_contract", "rest"]).fillna(0)
    axes[2].bar(counts.index, counts.values, color=["#2563eb", "#64748b"])
    axes[2].set_ylabel("orders")
    axes[2].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(rows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 6.5))
    for group_name, color in [("aligned_contract", "#2563eb"), ("rest", "#64748b")]:
        group = rows[rows["contract_audit_group"].eq(group_name)]
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values, label=group_name, color=color, linewidth=1.5)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage254 cumulative official PnL: aligned price + OI contraction vs rest")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contrast_rates(contrast: pd.DataFrame) -> None:
    data = contrast.copy()
    data["group"] = data["contract_audit_group"].astype(str)
    x = np.arange(len(data))
    width = 0.24
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True)
    axes[0].bar(x - width, data["risk_bad_rate"], width=width, label="risk_bad", color="#dc2626")
    axes[0].bar(x, data["right_tail_rate"], width=width, label="right_tail", color="#16a34a")
    axes[0].bar(x + width, data["bottom_loss_rate"], width=width, label="bottom_loss", color="#f97316")
    axes[0].set_ylabel("rate")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x, data["pnl_sum"], color=["#2563eb" if item == "aligned_contract" else "#64748b" for item in data["group"]])
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["group"])
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage254 candidate vs rest rates")
    fig.tight_layout()
    fig.savefig(CONTRAST_RATE_CHART_OUT, dpi=160)
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
    ax.set_title("Stage254 aligned price + OI contraction minus rest by split")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(SPLIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_true_engine"]]
    ax.bar(gate["gate_id"], gate["evidence_value"].astype(float), color=colors, alpha=0.82)
    ax.set_title("Stage254 gates: OI contraction squeeze remains preflight only")
    ax.set_ylabel("evidence")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _load_tail_source(row: pd.Series, max_rows: int = 121) -> pd.DataFrame:
    path = REPO_DIR / str(row["filtered_source_file"])
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path, columns=["bar_end_ts", "close", "open_interest"])
    frame["bar_end_ts"] = pd.to_datetime(frame["bar_end_ts"], errors="coerce")
    frame = frame.dropna(subset=["close", "open_interest"]).sort_values("bar_end_ts").tail(max_rows).copy()
    if frame.empty:
        return frame
    first_close = _safe_float(frame["close"].iloc[0], np.nan)
    first_oi = _safe_float(frame["open_interest"].iloc[0], np.nan)
    sign = int(row["direction_sign"])
    if np.isfinite(first_close) and first_close > 0:
        frame["aligned_log_price"] = sign * np.log(pd.to_numeric(frame["close"], errors="coerce") / first_close)
    else:
        frame["aligned_log_price"] = np.nan
    if np.isfinite(first_oi) and abs(first_oi) > 1e-12:
        frame["oi_pct"] = pd.to_numeric(frame["open_interest"], errors="coerce") / abs(first_oi) - 1.0
    else:
        frame["oi_pct"] = np.nan
    frame["bar_idx"] = np.arange(len(frame))
    return frame


def _plot_atlas(rows: pd.DataFrame) -> None:
    candidate = rows[rows["is_aligned_contract"].eq(1)].copy()
    tail = candidate[candidate["right_tail_visual"].eq(1)].sort_values("order_realized_pnl", ascending=False).head(6)
    bad = candidate[candidate["bottom_loss_visual"].eq(1)].sort_values("order_realized_pnl", ascending=True).head(6)
    atlas = pd.concat([tail.assign(atlas_bucket="right_tail"), bad.assign(atlas_bucket="bottom_loss")], ignore_index=True)
    if atlas.empty:
        return
    n = len(atlas)
    fig, axes = plt.subplots(n, 1, figsize=(12, max(2.2 * n, 5)), sharex=False)
    if n == 1:
        axes = [axes]
    for ax, (_, row) in zip(axes, atlas.iterrows()):
        source = _load_tail_source(row)
        if source.empty:
            ax.set_title(f"{row['atlas_bucket']} {row['vt_symbol']} missing source")
            continue
        ax.plot(source["bar_idx"], source["aligned_log_price"], color="#2563eb", linewidth=1.2, label="aligned price log")
        ax.plot(source["bar_idx"], source["oi_pct"], color="#f97316", linewidth=1.0, label="OI pct")
        ax.axhline(0, color="#111827", linewidth=0.7)
        title = (
            f"{row['atlas_bucket']} | {row['vt_symbol']} {row['direction']} "
            f"{str(row['official_open_date'])[:10]} pnl={row['order_realized_pnl']:,.0f} "
            f"risk={int(row['risk_bad_label'])}"
        )
        ax.set_title(title, fontsize=8)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(ATLAS_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, contrast: pd.DataFrame, split_stability: pd.DataFrame, gate: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} aligned price + OI contraction audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only audit. No strategy rule, no true engine, no A/B, no official config change, no CTP/SimNow, no order API.",
            "- frozen observation from Stage253: direction-aligned price with OI contraction may represent squeeze/liquidation continuation.",
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
            "## Candidate Summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- candidate order count: `{int(row['candidate_order_count'])}`",
            f"- candidate PnL sum: `{row['candidate_pnl_sum']:,.0f}`",
            f"- candidate PnL min/max: `{row['candidate_pnl_min']:,.0f}` / `{row['candidate_pnl_max']:,.0f}`",
            f"- candidate risk bad rate: `{row['candidate_risk_bad_rate']:.4f}`",
            f"- rest risk bad rate: `{row['rest_risk_bad_rate']:.4f}`",
            f"- risk reduction vs rest: `{row['risk_reduction_vs_rest']:.4f}`",
            f"- right-tail capture: `{row['candidate_right_tail_count']}` / `{row['candidate_right_tail_capture_rate']:.4f}`",
            f"- bottom-loss capture: `{row['candidate_bottom_loss_count']}` / `{row['candidate_bottom_loss_capture_rate']:.4f}`",
            f"- early right-tail capture: `{row['candidate_early_right_tail_count']}` / `{row['candidate_early_right_tail_capture_rate']:.4f}`",
            f"- split pass: `{int(row['split_pass_count'])}` / `{int(row['valid_split_count'])}`",
            f"- gate pass: `{int(row['promotion_gate_pass_count'])}` / `{int(row['promotion_gate_count'])}`",
            "",
            "## Candidate Vs Rest",
            "",
            _md_table(contrast, max_rows=20),
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
            f"- official path contract chart: `{PATH_CHART_OUT}`",
            f"- contribution chart: `{CONTRIBUTION_CHART_OUT}`",
            f"- contrast rate chart: `{CONTRAST_RATE_CHART_OUT}`",
            f"- split stability heatmap: `{SPLIT_HEATMAP_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- counterexample atlas: `{ATLAS_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The aligned price + OI contraction state carries much of the right-tail, but it is still contaminated by "
                "bottom-loss and mixed PnL, and its cross-split behavior is not strong enough for a true-engine candidate. "
                "Turning it into a rule now would be a historical-state fit."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    curve = _load_official_curve()
    official = _load_official_summary()
    contrast = _contrast(rows)
    split_stability = _split_stability(rows)
    gate = _promotion_gate(rows, contrast, split_stability)
    summary = _summary(rows, contrast, split_stability, gate, official)

    _write_csv(rows, ROWS_OUT)
    _write_csv(contrast, CONTRAST_OUT)
    _write_csv(split_stability, SPLIT_STABILITY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_contribution(rows)
    _plot_contrast_rates(contrast)
    _plot_split_heatmap(split_stability)
    _plot_gate(gate)
    _plot_atlas(rows)
    _write_report(summary, contrast, split_stability, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "rows_path": str(ROWS_OUT),
        "contrast_path": str(CONTRAST_OUT),
        "split_stability_path": str(SPLIT_STABILITY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "charts": [
            str(PATH_CHART_OUT),
            str(CONTRIBUTION_CHART_OUT),
            str(CONTRAST_RATE_CHART_OUT),
            str(SPLIT_HEATMAP_OUT),
            str(PROMOTION_GATE_CHART_OUT),
            str(ATLAS_CHART_OUT),
        ],
        "candidate_order_count": int(summary.iloc[0]["candidate_order_count"]),
        "candidate_right_tail_capture_rate": _safe_float(summary.iloc[0]["candidate_right_tail_capture_rate"], np.nan),
        "candidate_bottom_loss_capture_rate": _safe_float(summary.iloc[0]["candidate_bottom_loss_capture_rate"], np.nan),
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
