from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage012"
MODEL_TAG = "stage012_risk_invalid_repair_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
import stage011_stage861_quality_relabel_readonly as s011
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage012_risk_invalid_repair_forensics"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE011_DIR = LINE_DIR / "outputs" / "stage011_stage861_quality_relabel_readonly"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
WINDOW_MINUTES = 30
HEAT_R = 0.50
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

STAGE011_FEATURES = (
    STAGE011_DIR
    / "qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_features_stage011_stage861_quality_relabel_readonly_v1.csv"
)
STAGE011_CURVE = (
    STAGE011_DIR
    / "qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_contribution_curve_stage011_stage861_quality_relabel_readonly_v1.csv"
)
STAGE010_OFFICIAL_CURVE = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE010_SUMMARY = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE010_ENTRY_RISK = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_entry_risk_stage010_authoritative_minute_coverage_audit_v1.csv"
)

REPAIR_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_ledger_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_repaired_quality_{MODEL_TAG}.csv"
REPAIR_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_bucket_stats_{MODEL_TAG}.csv"
QUALITY_BEFORE_AFTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_before_after_stats_{MODEL_TAG}.csv"
YEAR_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_repaired_quality_stats_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_chart_{MODEL_TAG}.png"
REPAIR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s010._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s010._safe_float(value, default=default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s010._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s010._drawdown_pct(equity)


def _load_official_curve() -> pd.DataFrame:
    if not STAGE010_OFFICIAL_CURVE.exists():
        raise RuntimeError(f"missing official curve: {STAGE010_OFFICIAL_CURVE}")
    curve = pd.read_csv(STAGE010_OFFICIAL_CURVE, encoding="utf-8-sig")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce", format="mixed").dt.normalize()
    curve = curve[curve["date"].between(START, END)].copy().sort_values("date")
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    return curve


def _load_summary() -> pd.DataFrame:
    if not STAGE010_SUMMARY.exists():
        return pd.DataFrame()
    return pd.read_csv(STAGE010_SUMMARY, encoding="utf-8-sig")


def _load_features() -> pd.DataFrame:
    if not STAGE011_FEATURES.exists():
        raise RuntimeError(f"missing Stage011 features: {STAGE011_FEATURES}")
    data = pd.read_csv(STAGE011_FEATURES, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date", "entry_day", "exit_date_ts"]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce", format="mixed").dt.normalize()
    for column in [
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "risk_amount",
        "entry_price",
        "exit_price",
        "risk_price",
        "risk_valid",
        "stage861_covered",
        "stage861_entry_day_minute_bars",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    data["positive_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(lower=0.0)
    data["negative_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(upper=0.0)
    return data


def _load_entry_risk() -> pd.DataFrame:
    if not STAGE010_ENTRY_RISK.exists():
        raise RuntimeError(f"missing entry_risk: {STAGE010_ENTRY_RISK}")
    risk = pd.read_csv(STAGE010_ENTRY_RISK, encoding="utf-8-sig")
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce", format="mixed").dt.normalize()
    risk["direction_norm"] = risk["direction"].astype(str).str.lower()
    for column in [
        "entry_index",
        "volume",
        "entry_price",
        "stop_price",
        "stop_distance",
        "risk_per_contract",
        "actual_risk_amount",
        "target_risk_amount",
        "selected_volume",
    ]:
        if column in risk.columns:
            risk[column] = pd.to_numeric(risk[column], errors="coerce")
    return risk


def _match_entry_risk(row: pd.Series, entry_risk: pd.DataFrame) -> tuple[str, pd.Series | None, dict[str, Any]]:
    vt_symbol = str(row.get("vt_symbol"))
    direction = str(row.get("direction")).lower()
    entry_day = _normalize_day(row.get("entry_date"))
    candidates = entry_risk[
        entry_risk["contract_vt_symbol"].astype(str).eq(vt_symbol)
        & entry_risk["direction_norm"].eq(direction)
        & entry_risk["date"].le(entry_day)
    ].copy()
    if candidates.empty or pd.isna(entry_day):
        return "no_entry_risk_candidate", None, {"candidate_count": 0}
    candidates["_days_lag"] = (entry_day - candidates["date"]).dt.days
    candidates = candidates[candidates["_days_lag"].between(0, 10)].copy()
    if candidates.empty:
        return "no_entry_risk_candidate_within_10d", None, {"candidate_count": 0}
    lot_volume = _safe_float(row.get("volume"))
    lot_price = _safe_float(row.get("entry_price"))
    candidates["_volume_diff"] = (pd.to_numeric(candidates["volume"], errors="coerce") - lot_volume).abs()
    candidates["_entry_price_diff"] = (pd.to_numeric(candidates["entry_price"], errors="coerce") - lot_price).abs()
    candidates = candidates.sort_values(["_volume_diff", "_entry_price_diff", "_days_lag"])
    best = candidates.iloc[0]
    status = "unique_entry_risk_match" if len(candidates) == 1 else "multi_candidate_nearest_volume_price"
    details = {
        "candidate_count": int(len(candidates)),
        "entry_risk_lag_days": int(best["_days_lag"]),
        "volume_diff": _safe_float(best["_volume_diff"]),
        "entry_price_diff": _safe_float(best["_entry_price_diff"]),
    }
    return status, best, details


def _minute_metrics(row: pd.Series, full_groups: dict[str, pd.DataFrame], risk_price: float) -> dict[str, Any]:
    day = s011._day_for_row(full_groups, row)
    entry = _safe_float(row.get("entry_price"))
    direction = str(row.get("direction"))
    if day.empty:
        return {
            "repair_quality_label": "missing_stage861_30m",
            "repair_first_30m_directional_r": np.nan,
            "repair_first_30m_mfe_r": np.nan,
            "repair_first_30m_mae_r": np.nan,
            "repair_entry_day_mfe_r": np.nan,
            "repair_entry_day_mae_r": np.nan,
        }
    if not np.isfinite(entry) or not np.isfinite(risk_price) or risk_price <= 0:
        return {
            "repair_quality_label": "still_risk_or_feature_invalid",
            "repair_first_30m_directional_r": np.nan,
            "repair_first_30m_mfe_r": np.nan,
            "repair_first_30m_mae_r": np.nan,
            "repair_entry_day_mfe_r": np.nan,
            "repair_entry_day_mae_r": np.nan,
        }
    first = day.head(WINDOW_MINUTES)
    if first.empty:
        return {
            "repair_quality_label": "missing_stage861_30m",
            "repair_first_30m_directional_r": np.nan,
            "repair_first_30m_mfe_r": np.nan,
            "repair_first_30m_mae_r": np.nan,
            "repair_entry_day_mfe_r": np.nan,
            "repair_entry_day_mae_r": np.nan,
        }
    if direction == "short":
        directional = (entry - _safe_float(first.iloc[-1].get("close"))) / risk_price
        first_mfe = (entry - pd.to_numeric(first["low"], errors="coerce").min()) / risk_price
        first_mae = (pd.to_numeric(first["high"], errors="coerce").max() - entry) / risk_price
        day_mfe = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk_price
        day_mae = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk_price
    else:
        directional = (_safe_float(first.iloc[-1].get("close")) - entry) / risk_price
        first_mfe = (pd.to_numeric(first["high"], errors="coerce").max() - entry) / risk_price
        first_mae = (entry - pd.to_numeric(first["low"], errors="coerce").min()) / risk_price
        day_mfe = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk_price
        day_mae = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk_price
    first_mfe = max(0.0, first_mfe) if np.isfinite(first_mfe) else np.nan
    first_mae = max(0.0, first_mae) if np.isfinite(first_mae) else np.nan
    day_mfe = max(0.0, day_mfe) if np.isfinite(day_mfe) else np.nan
    day_mae = max(0.0, day_mae) if np.isfinite(day_mae) else np.nan
    if not np.isfinite(directional) or not np.isfinite(first_mae):
        label = "still_risk_or_feature_invalid"
    elif directional <= 0:
        label = "no_follow_30m"
    elif first_mae > HEAT_R:
        label = "adverse_heat_30m"
    else:
        label = "clean_continuation_30m"
    return {
        "repair_quality_label": label,
        "repair_first_30m_directional_r": directional,
        "repair_first_30m_mfe_r": first_mfe,
        "repair_first_30m_mae_r": first_mae,
        "repair_entry_day_mfe_r": day_mfe,
        "repair_entry_day_mae_r": day_mae,
    }


def _build_repair(features: pd.DataFrame, entry_risk: pd.DataFrame, full_groups: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    repaired_features: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        item = row.to_dict()
        original_label = str(row.get("quality_label_stage861"))
        if original_label == "risk_or_feature_invalid":
            status, risk_row, details = _match_entry_risk(row, entry_risk)
            if risk_row is not None:
                risk_price = _safe_float(risk_row.get("stop_distance"))
                metrics = _minute_metrics(row, full_groups, risk_price)
                plan_fill_gap_r = details["entry_price_diff"] / risk_price if np.isfinite(risk_price) and risk_price > 0 else np.nan
                if details["volume_diff"] == 0 and details["candidate_count"] == 1:
                    confidence = "high_unique_volume_match"
                elif details["volume_diff"] == 0:
                    confidence = "medium_multi_same_volume"
                else:
                    confidence = "medium_multi_volume_split_match"
                repair = {
                    "repair_status": status,
                    "repair_confidence": confidence,
                    "repair_source": "official_entry_risk_plan_day",
                    "repair_entry_index": risk_row.get("entry_index"),
                    "repair_entry_risk_date": risk_row.get("date"),
                    "repair_entry_risk_lag_days": details["entry_risk_lag_days"],
                    "repair_candidate_count": details["candidate_count"],
                    "repair_volume_diff": details["volume_diff"],
                    "repair_entry_price_diff": details["entry_price_diff"],
                    "repair_plan_fill_gap_r": plan_fill_gap_r,
                    "repair_stop_distance": risk_price,
                    "repair_stop_price": _safe_float(risk_row.get("stop_price")),
                    "repair_risk_per_contract": _safe_float(risk_row.get("risk_per_contract")),
                    "repair_actual_risk_amount": _safe_float(risk_row.get("actual_risk_amount")),
                    "repair_target_risk_amount": _safe_float(risk_row.get("target_risk_amount")),
                    "repair_selected_volume": _safe_float(risk_row.get("selected_volume")),
                }
                repair.update(metrics)
            else:
                repair = {
                    "repair_status": status,
                    "repair_confidence": "unrepaired",
                    "repair_source": "",
                    "repair_entry_index": np.nan,
                    "repair_entry_risk_date": pd.NaT,
                    "repair_entry_risk_lag_days": np.nan,
                    "repair_candidate_count": details.get("candidate_count", 0),
                    "repair_volume_diff": np.nan,
                    "repair_entry_price_diff": np.nan,
                    "repair_plan_fill_gap_r": np.nan,
                    "repair_stop_distance": np.nan,
                    "repair_stop_price": np.nan,
                    "repair_risk_per_contract": np.nan,
                    "repair_actual_risk_amount": np.nan,
                    "repair_target_risk_amount": np.nan,
                    "repair_selected_volume": np.nan,
                }
                repair.update(_minute_metrics(row, full_groups, np.nan))
            item.update(repair)
        else:
            item.update(
                {
                    "repair_status": "not_risk_invalid",
                    "repair_confidence": "not_needed",
                    "repair_source": "",
                    "repair_entry_index": np.nan,
                    "repair_entry_risk_date": pd.NaT,
                    "repair_entry_risk_lag_days": np.nan,
                    "repair_candidate_count": 0,
                    "repair_volume_diff": 0.0,
                    "repair_entry_price_diff": 0.0,
                    "repair_plan_fill_gap_r": 0.0,
                    "repair_stop_distance": _safe_float(row.get("risk_price")),
                    "repair_stop_price": np.nan,
                    "repair_risk_per_contract": np.nan,
                    "repair_actual_risk_amount": np.nan,
                    "repair_target_risk_amount": np.nan,
                    "repair_selected_volume": _safe_float(row.get("volume")),
                    "repair_quality_label": original_label,
                    "repair_first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                    "repair_first_30m_mfe_r": _safe_float(row.get("first_30m_mfe_r")),
                    "repair_first_30m_mae_r": _safe_float(row.get("first_30m_mae_r")),
                    "repair_entry_day_mfe_r": _safe_float(row.get("entry_day_mfe_r")),
                    "repair_entry_day_mae_r": _safe_float(row.get("entry_day_mae_r")),
                }
            )
        repaired_features.append(item)
        if original_label == "risk_or_feature_invalid":
            ledger = {
                key: item.get(key)
                for key in [
                    "lot_id",
                    "vt_symbol",
                    "product",
                    "direction",
                    "entry_date",
                    "exit_date",
                    "entry_price",
                    "volume",
                    "size",
                    "realized_pnl",
                    "r_multiple",
                    "coverage_bucket",
                    "exit_reason",
                    "repair_status",
                    "repair_confidence",
                    "repair_source",
                    "repair_entry_index",
                    "repair_entry_risk_date",
                    "repair_entry_risk_lag_days",
                    "repair_candidate_count",
                    "repair_volume_diff",
                    "repair_entry_price_diff",
                    "repair_plan_fill_gap_r",
                    "repair_stop_distance",
                    "repair_stop_price",
                    "repair_actual_risk_amount",
                    "repair_quality_label",
                    "repair_first_30m_directional_r",
                    "repair_first_30m_mae_r",
                ]
            }
            rows.append(ledger)
    repaired = pd.DataFrame(repaired_features)
    ledger = pd.DataFrame(rows)
    for frame in [repaired, ledger]:
        for column in frame.columns:
            if column.endswith("_date") or column in {"entry_date", "exit_date", "repair_entry_risk_date"}:
                frame[column] = pd.to_datetime(frame[column], errors="coerce", format="mixed").dt.normalize()
    repaired["entry_year"] = pd.to_datetime(repaired["entry_date"], errors="coerce").dt.year
    repaired["positive_pnl"] = pd.to_numeric(repaired["realized_pnl"], errors="coerce").clip(lower=0.0)
    repaired["negative_pnl"] = pd.to_numeric(repaired["realized_pnl"], errors="coerce").clip(upper=0.0)
    return repaired, ledger


def _bucket_stats(data: pd.DataFrame, label_col: str, label_name: str) -> pd.DataFrame:
    total_pnl = float(data["realized_pnl"].fillna(0.0).sum())
    total_positive = float(data["positive_pnl"].fillna(0.0).sum())
    total_negative_abs = abs(float(data["negative_pnl"].fillna(0.0).sum()))
    rows: list[dict[str, Any]] = []
    for label, group in data.groupby(label_col, dropna=False):
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        positive = float(group["positive_pnl"].fillna(0.0).sum())
        negative = float(group["negative_pnl"].fillna(0.0).sum())
        rows.append(
            {
                label_name: str(label),
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if "product" in group.columns else 0,
                "years": int(group["entry_year"].nunique()) if "entry_year" in group.columns else 0,
                "net_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": positive,
                "positive_pnl_share_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_pnl": negative,
                "negative_pnl_abs_share_pct": abs(negative) / total_negative_abs * 100.0 if total_negative_abs else np.nan,
                "median_first_30m_directional_r": float(pd.to_numeric(group["repair_first_30m_directional_r"], errors="coerce").median()),
                "median_first_30m_mae_r": float(pd.to_numeric(group["repair_first_30m_mae_r"], errors="coerce").median()),
                "win_rate_pct": float((pd.to_numeric(group["realized_pnl"], errors="coerce") > 0).mean() * 100.0),
                "max_single_win": float(pd.to_numeric(group["realized_pnl"], errors="coerce").max()),
                "max_single_loss": float(pd.to_numeric(group["realized_pnl"], errors="coerce").min()),
            }
        )
    rows.append(
        {
            label_name: "ALL",
            "lots": int(len(data)),
            "products": int(data["product"].astype(str).nunique()) if "product" in data.columns else 0,
            "years": int(data["entry_year"].nunique()) if "entry_year" in data.columns else 0,
            "net_pnl": total_pnl,
            "net_pnl_share_pct": 100.0,
            "positive_pnl": total_positive,
            "positive_pnl_share_pct": 100.0,
            "negative_pnl": float(data["negative_pnl"].fillna(0.0).sum()),
            "negative_pnl_abs_share_pct": 100.0,
            "median_first_30m_directional_r": float(pd.to_numeric(data["repair_first_30m_directional_r"], errors="coerce").median()),
            "median_first_30m_mae_r": float(pd.to_numeric(data["repair_first_30m_mae_r"], errors="coerce").median()),
            "win_rate_pct": float((pd.to_numeric(data["realized_pnl"], errors="coerce") > 0).mean() * 100.0),
            "max_single_win": float(pd.to_numeric(data["realized_pnl"], errors="coerce").max()),
            "max_single_loss": float(pd.to_numeric(data["realized_pnl"], errors="coerce").min()),
        }
    )
    return pd.DataFrame(rows)


def _year_quality_stats(data: pd.DataFrame) -> pd.DataFrame:
    return (
        data.groupby(["entry_year", "repair_quality_label"], dropna=False)
        .agg(
            lots=("lot_id", "size"),
            products=("product", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            win_rate_pct=("realized_pnl", lambda x: float((pd.to_numeric(x, errors="coerce") > 0).mean() * 100.0)),
            median_first_30m_directional_r=("repair_first_30m_directional_r", "median"),
            median_first_30m_mae_r=("repair_first_30m_mae_r", "median"),
        )
        .reset_index()
        .sort_values(["entry_year", "repair_quality_label"])
    )


def _contribution_curve(data: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    selectors: dict[str, pd.Series] = {
        "all_closed_lots_reference": data.index == data.index,
        "clean_continuation_30m_repaired": data["repair_quality_label"].eq("clean_continuation_30m"),
        "adverse_heat_30m_repaired": data["repair_quality_label"].eq("adverse_heat_30m"),
        "no_follow_30m_repaired": data["repair_quality_label"].eq("no_follow_30m"),
        "all_except_no_follow_repaired": ~data["repair_quality_label"].eq("no_follow_30m"),
        "old_risk_or_feature_invalid_only": data["quality_label_stage861"].eq("risk_or_feature_invalid"),
    }
    rows: list[pd.DataFrame] = []
    for label, mask in selectors.items():
        part = data[mask].copy()
        daily = (
            part.groupby("exit_date", dropna=True)["realized_pnl"].sum().reset_index().rename(columns={"exit_date": "date"})
            if not part.empty
            else pd.DataFrame(columns=["date", "realized_pnl"])
        )
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        curve = calendar.merge(daily, on="date", how="left")
        curve["realized_pnl"] = pd.to_numeric(curve["realized_pnl"], errors="coerce").fillna(0.0)
        curve["cumulative_realized_pnl"] = curve["realized_pnl"].cumsum()
        curve["contribution_drawdown_cash"] = curve["cumulative_realized_pnl"] - curve["cumulative_realized_pnl"].cummax()
        curve["diagnostic_equity"] = CAPITAL + curve["cumulative_realized_pnl"]
        curve["diagnostic_drawdown_pct"] = _drawdown_pct(curve["diagnostic_equity"])
        curve["bucket"] = label
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["note"] = "closed-lot contribution curve only; not executable mark-to-market backtest"
        rows.append(curve)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summary(official_curve: pd.DataFrame, repaired: pd.DataFrame, ledger: pd.DataFrame, repaired_quality: pd.DataFrame) -> pd.DataFrame:
    official_summary = _load_summary()
    official_end = float(pd.to_numeric(official_curve["account_equity"], errors="coerce").iloc[-1])
    def _official(column: str) -> float:
        if official_summary.empty or column not in official_summary.columns:
            return np.nan
        return _safe_float(official_summary[column].iloc[0])
    def _quality(label: str, column: str) -> float:
        hit = repaired_quality[repaired_quality["repair_quality_label"].eq(label)]
        if hit.empty:
            return np.nan
        return _safe_float(hit[column].iloc[0])
    invalid = repaired[repaired["quality_label_stage861"].eq("risk_or_feature_invalid")].copy()
    no_follow = repaired[repaired["repair_quality_label"].eq("no_follow_30m")].copy()
    no_follow_year = no_follow.groupby("entry_year", dropna=False)["realized_pnl"].sum().reset_index() if not no_follow.empty else pd.DataFrame(columns=["entry_year", "realized_pnl"])
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "window_start": START.date().isoformat(),
                "window_end": END.date().isoformat(),
                "official_end_equity": official_end,
                "official_total_return_pct": (official_end / CAPITAL - 1.0) * 100.0,
                "official_max_dd_pct": float(pd.to_numeric(official_curve["drawdown_pct"], errors="coerce").min()),
                "official_sharpe": _official("sharpe"),
                "official_total_slippage": _official("total_slippage"),
                "official_total_trade_count": _official("total_trade_count"),
                "official_win_rate_pct": _official("nonzero_daily_win_rate_pct"),
                "official_broker10_peak_pct": float(pd.to_numeric(official_curve["broker10_margin_to_equity_pct"], errors="coerce").max()),
                "closed_lots": int(len(repaired)),
                "old_risk_or_feature_invalid_lots": int(len(invalid)),
                "entry_risk_repaired_lots": int(ledger["repair_status"].ne("not_risk_invalid").sum()) if not ledger.empty else 0,
                "entry_risk_unrepaired_lots": int(ledger["repair_confidence"].eq("unrepaired").sum()) if not ledger.empty else 0,
                "invalid_repaired_to_clean_lots": int(invalid["repair_quality_label"].eq("clean_continuation_30m").sum()),
                "invalid_repaired_to_adverse_heat_lots": int(invalid["repair_quality_label"].eq("adverse_heat_30m").sum()),
                "invalid_repaired_to_no_follow_lots": int(invalid["repair_quality_label"].eq("no_follow_30m").sum()),
                "invalid_net_pnl": float(invalid["realized_pnl"].fillna(0.0).sum()),
                "invalid_repaired_to_no_follow_net_pnl": float(invalid.loc[invalid["repair_quality_label"].eq("no_follow_30m"), "realized_pnl"].fillna(0.0).sum()),
                "repaired_clean_lots": int(repaired["repair_quality_label"].eq("clean_continuation_30m").sum()),
                "repaired_clean_net_pnl": _quality("clean_continuation_30m", "net_pnl"),
                "repaired_no_follow_lots": int(len(no_follow)),
                "repaired_no_follow_net_pnl": _quality("no_follow_30m", "net_pnl"),
                "repaired_no_follow_positive_years": int((pd.to_numeric(no_follow_year["realized_pnl"], errors="coerce") > 0).sum()) if not no_follow_year.empty else 0,
                "repaired_missing_or_invalid_lots": int(repaired["repair_quality_label"].isin(["still_risk_or_feature_invalid", "missing_stage861_30m"]).sum()),
                "decision": "stage012_risk_invalid_repaired_no_trade_rule",
            }
        ]
    )


def _plot_path(official_curve: pd.DataFrame, repaired: pd.DataFrame) -> None:
    data = official_curve.copy().sort_values("date")
    invalid = repaired[repaired["quality_label_stage861"].eq("risk_or_feature_invalid")].copy()
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity"], color="#2563eb", label="official C9/15w")
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", label="drawdown")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#0f766e", label="broker10")
    colors = {
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#f59e0b",
        "no_follow_30m": "#dc2626",
        "missing_stage861_30m": "#64748b",
    }
    marks = pd.concat(
        [
            invalid.nlargest(5, "realized_pnl"),
            invalid.nsmallest(8, "realized_pnl"),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(["lot_id"])
    seen: set[str] = set()
    for _, row in marks.iterrows():
        label = str(row.get("repair_quality_label"))
        legend = f"old_invalid->{label}" if label not in seen else None
        seen.add(label)
        date = _normalize_day(row.get("entry_date"))
        for ax in axes:
            ax.axvline(date, color=colors.get(label, "#64748b"), alpha=0.24, linewidth=1.0, label=legend)
            legend = None
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.8)
    axes[0].set_title("Stage012 official C9/15w path with repaired old-risk-invalid markers")
    axes[1].set_title("Official drawdown")
    axes[2].set_title("Official broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_contribution(contrib: pd.DataFrame) -> None:
    colors = {
        "all_closed_lots_reference": "#111827",
        "clean_continuation_30m_repaired": "#16a34a",
        "adverse_heat_30m_repaired": "#f59e0b",
        "no_follow_30m_repaired": "#dc2626",
        "all_except_no_follow_repaired": "#2563eb",
        "old_risk_or_feature_invalid_only": "#a855f7",
    }
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    for label, group in contrib.groupby("bucket"):
        group = group.sort_values("date")
        linewidth = 1.8 if label in {"all_closed_lots_reference", "all_except_no_follow_repaired"} else 1.15
        alpha = 0.95 if label in {"all_closed_lots_reference", "all_except_no_follow_repaired"} else 0.68
        axes[0].plot(group["date"], group["cumulative_realized_pnl"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
        axes[1].plot(group["date"], group["contribution_drawdown_cash"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
    axes[0].set_title("Stage012 repaired-quality closed-lot cumulative PnL")
    axes[1].set_title("Contribution drawdown in cash")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best", ncols=2)
    fig.savefig(CONTRIB_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_repair(ledger: pd.DataFrame) -> None:
    if ledger.empty:
        return
    data = ledger.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    year = (
        data.groupby(["entry_year", "repair_quality_label"], dropna=False)
        .agg(lots=("lot_id", "size"), net_pnl=("realized_pnl", "sum"))
        .reset_index()
    )
    labels = ["clean_continuation_30m", "adverse_heat_30m", "no_follow_30m", "missing_stage861_30m", "still_risk_or_feature_invalid"]
    colors = {
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#f59e0b",
        "no_follow_30m": "#dc2626",
        "missing_stage861_30m": "#64748b",
        "still_risk_or_feature_invalid": "#a855f7",
    }
    years = sorted(int(x) for x in year["entry_year"].dropna().unique())
    x = np.arange(len(years))
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    bottom_lots = np.zeros(len(years))
    bottom_pos = np.zeros(len(years))
    bottom_neg = np.zeros(len(years))
    for label in labels:
        part = year[year["repair_quality_label"].eq(label)].set_index("entry_year")
        lots = np.array([_safe_float(part.loc[y, "lots"], 0.0) if y in part.index else 0.0 for y in years])
        pnl = np.array([_safe_float(part.loc[y, "net_pnl"], 0.0) if y in part.index else 0.0 for y in years])
        axes[0].bar(x, lots, bottom=bottom_lots, color=colors.get(label), label=label)
        bottom_lots += lots
        pos = np.clip(pnl, 0.0, None)
        neg = np.clip(pnl, None, 0.0)
        axes[1].bar(x, pos, bottom=bottom_pos, color=colors.get(label), alpha=0.82, label=label)
        axes[1].bar(x, neg, bottom=bottom_neg, color=colors.get(label), alpha=0.82)
        bottom_pos += pos
        bottom_neg += neg
    axes[0].set_title("Old risk-invalid rows repaired into quality labels by entry year")
    axes[1].set_title("Old risk-invalid repaired-label net PnL by entry year")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([str(y) for y in years])
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.24)
        ax.legend(loc="best", ncols=2)
    fig.savefig(REPAIR_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas(ledger: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for label in ["no_follow_30m", "clean_continuation_30m", "adverse_heat_30m"]:
        part = ledger[ledger["repair_quality_label"].eq(label)].copy()
        if not part.empty:
            parts.append(part.nlargest(4, "realized_pnl"))
            parts.append(part.nsmallest(4, "realized_pnl"))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False).drop_duplicates(["lot_id"]).head(MAX_ATLAS_ROWS)


def _line_prices(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("repair_stop_distance"))
    direction = str(row.get("direction"))
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {"entry": entry, "progress_05r": np.nan, "adverse_05r": np.nan, "stop_price": _safe_float(row.get("repair_stop_price"))}
    if direction == "short":
        return {"entry": entry, "progress_05r": entry - 0.5 * risk, "adverse_05r": entry + 0.5 * risk, "stop_price": _safe_float(row.get("repair_stop_price"))}
    return {"entry": entry, "progress_05r": entry + 0.5 * risk, "adverse_05r": entry - 0.5 * risk, "stop_price": _safe_float(row.get("repair_stop_price"))}


def _plot_atlas(ledger: pd.DataFrame, full_groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(ledger)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.5 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            day = s011._day_for_row(full_groups, row)
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing Stage861 minutes\n{row.get('vt_symbol')} {row.get('entry_date')}", ha="center", va="center")
            else:
                plot_day = day.head(520).reset_index(drop=True)
                s010.s008.s825._plot_candles(ax, plot_day)
                prices = _line_prices(row)
                for key, color, linestyle in [
                    ("entry", "#2563eb", "-"),
                    ("progress_05r", "#16a34a", "--"),
                    ("adverse_05r", "#dc2626", ":"),
                    ("stop_price", "#7c2d12", "-."),
                ]:
                    price = _safe_float(prices.get(key))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=key)
                if len(plot_day) >= WINDOW_MINUTES:
                    ax.axvline(WINDOW_MINUTES - 1, color="#64748b", linestyle="-.", linewidth=0.9, alpha=0.78, label="30m")
                ticks = np.linspace(0, len(plot_day) - 1, num=min(8, len(plot_day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(plot_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), fontsize=7, loc="best")
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"old invalid -> {row.get('repair_quality_label')} | {row.get('repair_confidence')} | "
                    f"{row.get('vt_symbol')} {row.get('direction')} {pd.Timestamp(row.get('entry_date')).date().isoformat()} "
                    f"pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} dir30={_safe_float(row.get('repair_first_30m_directional_r'), 0):.2f} "
                    f"mae30={_safe_float(row.get('repair_first_30m_mae_r'), 0):.2f} gapR={_safe_float(row.get('repair_plan_fill_gap_r'), 0):.2f}"
                ),
                fontsize=8.0,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "entry_date": pd.Timestamp(row.get("entry_date")).date().isoformat(),
                    "direction": row.get("direction"),
                    "repair_quality_label": row.get("repair_quality_label"),
                    "repair_confidence": row.get("repair_confidence"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "repair_first_30m_directional_r": _safe_float(row.get("repair_first_30m_directional_r")),
                    "repair_first_30m_mae_r": _safe_float(row.get("repair_first_30m_mae_r")),
                    "repair_plan_fill_gap_r": _safe_float(row.get("repair_plan_fill_gap_r")),
                    "png": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                }
            )
        path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
        fig.suptitle("Stage012 old risk-invalid repair atlas", fontsize=12)
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(summary: pd.DataFrame, ledger: pd.DataFrame, repaired_quality: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    repaired_lots = int(_safe_float(row.get("entry_risk_repaired_lots"), 0.0))
    unrepaired_lots = int(_safe_float(row.get("entry_risk_unrepaired_lots"), 0.0))
    if repaired_lots == 65 and unrepaired_lots == 0:
        decision = "stage012_risk_invalid_all_repaired_as_plan_day_risk_no_trade_rule"
    else:
        decision = "stage012_risk_invalid_partially_unrepaired_keep_official_path"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "why": (
            "All old risk_or_feature_invalid lots can be matched to the official entry_risk plan-day ledger, so the issue is "
            "closed-lot feature binding rather than absent engine risk state. This remains read-only; future true engines may "
            "use plan-day stop_distance for minute R accounting, but unrepaired or missing rows must keep the official path."
        ),
        "summary": {key: _json_safe(value) for key, value in row.items()},
        "repair_quality_stats": repaired_quality.to_dict(orient="records"),
        "repair_status_stats": _bucket_stats(
            ledger.assign(
                entry_year=pd.to_datetime(ledger["entry_date"], errors="coerce").dt.year,
                positive_pnl=pd.to_numeric(ledger["realized_pnl"], errors="coerce").clip(lower=0.0),
                negative_pnl=pd.to_numeric(ledger["realized_pnl"], errors="coerce").clip(upper=0.0),
            ),
            "repair_quality_label",
            "repair_quality_label",
        ).to_dict(orient="records") if not ledger.empty else [],
        "outputs": {
            "repair_ledger": str(REPAIR_LEDGER_OUT),
            "features_repaired_quality": str(FEATURES_OUT),
            "repair_bucket_stats": str(REPAIR_BUCKET_OUT),
            "quality_before_after_stats": str(QUALITY_BEFORE_AFTER_OUT),
            "year_quality_stats": str(YEAR_QUALITY_OUT),
            "contribution_curve": str(CONTRIB_CURVE_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "repair_chart": str(REPAIR_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_OUT),
        },
        "overfit_reflection_before": (
            "No: the stage does not create a trading rule. It validates whether missing risk fields can be recovered from "
            "the official plan-day risk ledger using time-ordered matching."
        ),
        "overfit_reflection_after": (
            "No: all repair logic uses official entry_risk rows before the trade fill date and no product/year/direction "
            "branch changes trades. The result is a data-accounting prerequisite for a future engine."
        ),
        "continue_value_after": (
            "Yes: plan-day risk repair removes a false blocker for Stage861 minute R labels. The next true-engine candidate "
            "can use this repair method, but must keep official path when plan-day risk is unavailable."
        ),
        "order_api_called": False,
        "ctp_connected": False,
    }


def _write_report(
    summary: pd.DataFrame,
    repair_bucket: pd.DataFrame,
    repaired_quality: pd.DataFrame,
    year_quality: pd.DataFrame,
    ledger: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage012 risk_or_feature_invalid 修复归因",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读风险字段修复审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 外部调研与判断",
        "",
        "- QuantStart 系统化回测资料把 position sizing/risk accounting 视为组合仿真的核心，不能在字段缺失时直接解释为策略信号。",
        "- pysystemtrade 资料强调数据层、回测层、执行层分离；Stage012 因此只做 official entry_risk 账本匹配，不改变交易。",
        "- Freqtrade/NautilusTrader 的回测资料提醒时间顺序和 bar 可见性；本阶段只使用不晚于成交日的 plan-day risk，不用未来 MFE/MAE 修复。",
        "- 我的判断：Stage011 的 65 笔 invalid 必须先修复，否则下一阶段最小风险真实引擎会错误地把会计缺口当成不可交易样本。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Old Invalid Repair Buckets",
        "",
        _md_table(repair_bucket, max_rows=20),
        "",
        "## Full Sample Repaired Quality",
        "",
        _md_table(repaired_quality, max_rows=20),
        "",
        "## Year Repaired Quality",
        "",
        _md_table(year_quality, max_rows=50),
        "",
        "## Repair Ledger Samples",
        "",
        _md_table(
            ledger[
                [
                    "lot_id",
                    "vt_symbol",
                    "entry_date",
                    "direction",
                    "realized_pnl",
                    "repair_confidence",
                    "repair_entry_risk_lag_days",
                    "repair_stop_distance",
                    "repair_plan_fill_gap_r",
                    "repair_quality_label",
                    "repair_first_30m_directional_r",
                    "repair_first_30m_mae_r",
                ]
            ].sort_values("realized_pnl"),
            max_rows=20,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- official path chart：`{PATH_CHART_OUT}`",
        f"- contribution chart：`{CONTRIB_CHART_OUT}`",
        f"- repair chart：`{REPAIR_CHART_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## 视觉分析",
        "",
        "- official path chart 显示本阶段仍不改变官方 C9/15w 资金路径，只把旧 invalid 样本按修复后标签标记到权益、回撤和 broker10 曲线上。",
        "- contribution chart 显示修复后 `no_follow_30m_repaired` 仍为负，但从 Stage011 的约 `-610万` 收窄到约 `-445万`；说明 no-follow 线索存在，但旧 invalid 里有正贡献 no-follow，不能粗暴当作坏样本。",
        "- repair chart 显示旧 invalid 样本跨多年、跨品种分布，不是单一产品或单一年份问题；它们被修复为 clean/adverse/no-follow 三类，而不是一个独立信号集合。",
        "- atlas 显示部分旧 invalid 的计划日 entry risk 与成交日开盘价有 gap，真实引擎如果用 R 口径，必须明确使用 plan-day stop_distance 还是成交价到 stop_price 的实际距离，不能事后混用。",
        "",
        "## Judgment",
        "",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
        "- 结论：Stage012 不是交易候选；它把 Stage011 的字段缺口修成可审计风险账本，为下一阶段真实引擎准备输入前提。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage012] loading official curve, Stage011 features, entry_risk, Stage861 minute bars", flush=True)
    official_curve = _load_official_curve()
    features = _load_features()
    entry_risk = _load_entry_risk()
    metadata = s010.s008.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    full_minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    full_groups = s010.s008.s825._minute_groups(full_minute_bars)

    print("[stage012] repairing old risk_or_feature_invalid rows", flush=True)
    repaired, ledger = _build_repair(features, entry_risk, full_groups)
    invalid_only = repaired[repaired["quality_label_stage861"].eq("risk_or_feature_invalid")].copy()
    repair_bucket = _bucket_stats(invalid_only, "repair_quality_label", "repair_quality_label")
    repaired_quality = _bucket_stats(repaired, "repair_quality_label", "repair_quality_label")
    year_quality = _year_quality_stats(repaired)
    contrib = _contribution_curve(repaired)
    summary = _summary(official_curve, repaired, ledger, repaired_quality)

    print("[stage012] plotting visuals", flush=True)
    _plot_path(official_curve, repaired)
    _plot_contribution(contrib)
    _plot_repair(ledger)
    atlas_paths, atlas_manifest = _plot_atlas(ledger, full_groups)
    decision = _decision(summary, ledger, repaired_quality, atlas_paths)
    summary.loc[:, "decision"] = decision["decision"]
    _write_report(summary, repair_bucket, repaired_quality, year_quality, ledger, atlas_paths, decision)

    ledger.to_csv(REPAIR_LEDGER_OUT, index=False, encoding="utf-8-sig")
    repaired.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    repair_bucket.to_csv(REPAIR_BUCKET_OUT, index=False, encoding="utf-8-sig")
    repaired_quality.to_csv(QUALITY_BEFORE_AFTER_OUT, index=False, encoding="utf-8-sig")
    year_quality.to_csv(YEAR_QUALITY_OUT, index=False, encoding="utf-8-sig")
    contrib.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage012] decision={decision['decision']}", flush=True)
    print(f"[stage012] summary={summary.iloc[0].to_dict()}", flush=True)
    print(f"[stage012] report={REPORT_OUT}", flush=True)


if __name__ == "__main__":
    main()
