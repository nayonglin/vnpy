from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage842_stage841_structural_break_taxonomy as s842
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage862"
MODEL_TAG = "stage862_stage861_rule_hypothesis_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage862_stage861_rule_hypothesis_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE847_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"
STAGE847_TAG = "stage847_stage830_c4_stop_retry_engine_v1"

ENTRY_FEATURES_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_entry_lot_features_{STAGE861_TAG}.csv"
FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"
ENTRY_ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_entry_atlas_manifest_{STAGE861_TAG}.csv"
PRESSURE_FEATURES_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_pressure_key_date_features_{STAGE861_TAG}.csv"
STAGE861_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_summary_{STAGE861_TAG}.csv"
STAGE847_COMPARISON_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_comparison_{STAGE847_TAG}.csv"
STAGE847_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_summary_{STAGE847_TAG}.csv"

COHORT_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_stats_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
PROXY_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_yearly_{MODEL_TAG}.csv"
STRUCTURE_RULE_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structure_rule_stats_{MODEL_TAG}.csv"
STRUCTURE_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structure_yearly_{MODEL_TAG}.csv"
HYPOTHESIS_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hypothesis_summary_{MODEL_TAG}.csv"
VISUAL_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_review_manifest_{MODEL_TAG}.csv"
VISUAL_ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_review_page{{page:03d}}_{MODEL_TAG}.png"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PER_PAGE = 4
MAX_VISUAL_ROWS = 24
OPENING_RANGE_BARS = 15


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _load_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"Missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _prepare_entry_features() -> pd.DataFrame:
    data = _load_csv(ENTRY_FEATURES_PATH).copy()
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "risk_pct",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "entry_day_close_return_pct",
        "opening_range_breakout_confirmed",
        "confirm_fast_15m_1r",
        "confirm_fast_30m_1r",
        "confirm_fast_60m_1r",
        "fail_fast_30m_05r",
        "reentry_cross_count_after_05r_stop",
        "big_winner",
        "winner",
        "entry_day_minute_bars",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["covered_entry_day"] = data["entry_day_minute_bars"].fillna(0).gt(0).astype(int)
    data["winner"] = data["realized_pnl"].fillna(0).gt(0).astype(int)
    data["big_winner"] = data.get("big_winner", 0)
    data["big_winner"] = pd.to_numeric(data["big_winner"], errors="coerce").fillna(0).astype(int)
    for column in [
        "entry_day_first_0p5r_outcome",
        "entry_day_first_1p0r_outcome",
        "entry_day_first_2p0r_outcome",
    ]:
        data[column] = data[column].fillna("missing").astype(str)
    manifest = _load_csv(ENTRY_ATLAS_MANIFEST_PATH, required=False)
    if not manifest.empty and "lot_id" in manifest.columns:
        manifest = manifest[["lot_id", "chart_page"]].drop_duplicates("lot_id")
        manifest["lot_id"] = pd.to_numeric(manifest["lot_id"], errors="coerce")
        data = data.merge(manifest, on="lot_id", how="left", suffixes=("", "_stage861"))
        data = data.rename(columns={"chart_page": "stage861_entry_atlas_page"})
    else:
        data["stage861_entry_atlas_page"] = np.nan
    return data


def _load_full_minute_bars() -> pd.DataFrame:
    data = _load_csv(FULL_MINUTE_BARS_PATH)
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" not in data.columns:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    else:
        data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).reset_index(drop=True)


def _proxy_tables(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    risk = pd.to_numeric(features["risk_amount"], errors="coerce").fillna(0.0)
    first_stop = features["entry_day_first_0p5r_outcome"].eq("stop_first") & risk.gt(0)
    recovered = first_stop & pd.to_numeric(features["reentry_cross_count_after_05r_stop"], errors="coerce").fillna(0).gt(0)
    no_reentry = first_stop & ~recovered
    stop_cash = -0.5 * risk

    proxy_specs: list[dict[str, Any]] = []
    p1 = original.copy()
    p1.loc[first_stop] = stop_cash.loc[first_stop]
    proxy_specs.append(
        {
            "proxy_id": "P1_stop05_no_retry",
            "family": "stop",
            "rule_text": "If 0.5R adverse is touched on entry day, exit at -0.5R and do not retry.",
            "affected": first_stop,
            "adjusted": p1,
            "live_feasible": "yes",
            "judgment": "not_promoted_right_tail_damage",
        }
    )

    p2 = original.copy()
    p2.loc[recovered] = original.loc[recovered] + stop_cash.loc[recovered]
    p2.loc[no_reentry] = stop_cash.loc[no_reentry]
    proxy_specs.append(
        {
            "proxy_id": "P2_stop05_retry_on_entry_reclaim",
            "family": "stop_retry",
            "rule_text": "Exit at -0.5R, then allow one retry only after entry price is reclaimed.",
            "affected": first_stop,
            "adjusted": p2,
            "live_feasible": "partly_needs_engine",
            "judgment": "building_block_not_standalone_after_stage847",
        }
    )

    or_not = ~pd.to_numeric(features["opening_range_breakout_confirmed"], errors="coerce").fillna(0).eq(1)
    p3 = original.copy()
    p3.loc[or_not] = 0.0
    proxy_specs.append(
        {
            "proxy_id": "P3_block_or15_no_breakout",
            "family": "entry_filter",
            "rule_text": "Block entries without signal-side OR15 breakout.",
            "affected": or_not,
            "adjusted": p3,
            "live_feasible": "yes_but_semantics_rejected_before",
            "judgment": "not_promoted_stage834_semantic_conflict",
        }
    )

    no60 = ~pd.to_numeric(features["confirm_fast_60m_1r"], errors="coerce").fillna(0).eq(1)
    p4 = original.copy()
    p4.loc[no60] = 0.0
    proxy_specs.append(
        {
            "proxy_id": "P4_block_no60m_1r_confirm",
            "family": "fast_confirmation",
            "rule_text": "Block entries that do not reach +1R in first 60 minutes.",
            "affected": no60,
            "adjusted": p4,
            "live_feasible": "no_post_entry_hindsight",
            "judgment": "rejected_right_tail_damage",
        }
    )

    p5 = original.copy()
    p5.loc[no_reentry] = 0.0
    proxy_specs.append(
        {
            "proxy_id": "P5_hindsight_block_stop_no_reentry",
            "family": "hindsight_ceiling",
            "rule_text": "Remove stop-first lots that never reclaim entry during the day.",
            "affected": no_reentry,
            "adjusted": p5,
            "live_feasible": "no_eod_hindsight",
            "judgment": "diagnostic_only_supports_retry_skeleton",
        }
    )

    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    base_total = float(original.sum())
    for spec in proxy_specs:
        affected = spec["affected"].fillna(False)
        adjusted = pd.to_numeric(spec["adjusted"], errors="coerce").fillna(original)
        delta = adjusted - original
        aff = features[affected].copy()
        winners = features[affected & original.gt(0)]
        losers = features[affected & original.lt(0)]
        big = features[affected & features["big_winner"].eq(1)]
        rows.append(
            {
                "proxy_id": spec["proxy_id"],
                "family": spec["family"],
                "rule_text": spec["rule_text"],
                "live_feasible": spec["live_feasible"],
                "judgment": spec["judgment"],
                "all_lots": int(len(features)),
                "affected_lots": int(affected.sum()),
                "affected_lot_pct": float(affected.mean() * 100.0),
                "affected_original_pnl": float(original[affected].sum()),
                "affected_adjusted_pnl": float(adjusted[affected].sum()),
                "gross_proxy_delta": float(delta.sum()),
                "base_total_pnl": base_total,
                "proxy_total_pnl": float(adjusted.sum()),
                "affected_winner_lots": int(len(winners)),
                "affected_loser_lots": int(len(losers)),
                "affected_big_winner_lots": int(len(big)),
                "winner_delta": float(delta[winners.index].sum()) if len(winners) else 0.0,
                "loser_delta": float(delta[losers.index].sum()) if len(losers) else 0.0,
                "big_winner_delta": float(delta[big.index].sum()) if len(big) else 0.0,
                "median_delta": float(delta[affected].median()) if len(aff) else 0.0,
            }
        )
        tmp = features[["lot_id", "entry_year"]].copy()
        tmp["delta"] = delta
        tmp["affected"] = affected.astype(int)
        tmp["original"] = original
        tmp["big_winner"] = features["big_winner"]
        for year, group in tmp.groupby("entry_year", dropna=False):
            yearly_rows.append(
                {
                    "proxy_id": spec["proxy_id"],
                    "entry_year": int(year) if pd.notna(year) else 0,
                    "lots": int(len(group)),
                    "affected_lots": int(group["affected"].sum()),
                    "gross_proxy_delta": float(group["delta"].sum()),
                    "winner_delta": float(group.loc[group["original"].gt(0), "delta"].sum()),
                    "loser_delta": float(group.loc[group["original"].lt(0), "delta"].sum()),
                    "big_winner_delta": float(group.loc[group["big_winner"].eq(1), "delta"].sum()),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(yearly_rows)


def _structure_taxonomy(features: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s825._minute_groups(minute_bars)
    taxonomy = pd.DataFrame([s842._lot_taxonomy(row, minute_by_symbol) for _, row in features.iterrows()])
    data = features.merge(taxonomy, on="lot_id", how="left")
    for spec in s842.RULE_SPECS:
        trigger_col = spec["trigger_col"]
        price_col = spec["price_col"]
        rule_id = spec["rule_id"]
        pnl_col = f"{rule_id}_exit_pnl"
        delta_col = f"{rule_id}_delta_vs_baseline"
        data[pnl_col] = np.where(
            pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1),
            data.apply(lambda row: s842._pnl_at_exit(row, row.get(price_col)), axis=1),
            np.nan,
        )
        data[delta_col] = pd.to_numeric(data[pnl_col], errors="coerce") - pd.to_numeric(
            data["realized_pnl"], errors="coerce"
        )
    return data


def _structure_rule_stats(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    base_total = float(pd.to_numeric(data["realized_pnl"], errors="coerce").sum())
    for spec in s842.RULE_SPECS:
        rule_id = spec["rule_id"]
        trigger_col = spec["trigger_col"]
        delta_col = f"{rule_id}_delta_vs_baseline"
        triggered = data[pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1)].copy()
        winners = triggered[pd.to_numeric(triggered["realized_pnl"], errors="coerce").gt(0)]
        losers = triggered[pd.to_numeric(triggered["realized_pnl"], errors="coerce").lt(0)]
        big = triggered[triggered["big_winner"].eq(1)]
        delta = pd.to_numeric(triggered.get(delta_col), errors="coerce").fillna(0.0)
        rows.append(
            {
                "rule_id": rule_id,
                "rule_text": spec["rule_text"],
                "triggered_lots": int(len(triggered)),
                "triggered_lot_pct": float(len(triggered) / len(data) * 100.0) if len(data) else 0.0,
                "triggered_baseline_pnl": float(pd.to_numeric(triggered["realized_pnl"], errors="coerce").sum()),
                "gross_delta_vs_baseline": float(delta.sum()),
                "all_lots_baseline_pnl": base_total,
                "all_lots_after_overlay_gross_pnl": float(base_total + delta.sum()),
                "winner_triggered_lots": int(len(winners)),
                "winner_delta": float(pd.to_numeric(winners.get(delta_col), errors="coerce").fillna(0.0).sum()),
                "loser_triggered_lots": int(len(losers)),
                "loser_delta": float(pd.to_numeric(losers.get(delta_col), errors="coerce").fillna(0.0).sum()),
                "big_winner_triggered_lots": int(len(big)),
                "big_winner_delta": float(pd.to_numeric(big.get(delta_col), errors="coerce").fillna(0.0).sum()),
                "judgment": "not_promoted_full_coverage_negative_or_right_tail_damage",
            }
        )
        tmp = data[["lot_id", "entry_year", "realized_pnl", "big_winner"]].copy()
        tmp["triggered"] = pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int)
        tmp["delta"] = pd.to_numeric(data.get(delta_col), errors="coerce").fillna(0.0)
        for year, group in tmp.groupby("entry_year", dropna=False):
            yearly_rows.append(
                {
                    "rule_id": rule_id,
                    "entry_year": int(year) if pd.notna(year) else 0,
                    "lots": int(len(group)),
                    "triggered_lots": int(group["triggered"].sum()),
                    "gross_delta_vs_baseline": float(group["delta"].sum()),
                    "winner_delta": float(group.loc[group["realized_pnl"].gt(0), "delta"].sum()),
                    "loser_delta": float(group.loc[group["realized_pnl"].lt(0), "delta"].sum()),
                    "big_winner_delta": float(group.loc[group["big_winner"].eq(1), "delta"].sum()),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("gross_delta_vs_baseline", ascending=False).reset_index(drop=True)
    return result, pd.DataFrame(yearly_rows)


def _cohort_stats(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = [
        ("entry_day_first_0p5r_outcome", "all"),
        ("entry_day_first_1p0r_outcome", "all"),
        ("recovery_after_stop_shape_stage842", "stop05 taxonomy"),
        ("opening_range_breakout_confirmed", "OR15"),
        ("confirm_fast_60m_1r", "60m confirm"),
        ("direction", "direction"),
        ("entry_year", "year"),
    ]
    for column, family in specs:
        if column not in data.columns:
            continue
        for value, group in data.groupby(column, dropna=False):
            pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
            rows.append(
                {
                    "family": family,
                    "bucket_col": column,
                    "bucket": str(value),
                    "lots": int(len(group)),
                    "pnl_sum": float(pnl.sum()),
                    "abs_pnl_sum": float(pnl.abs().sum()),
                    "win_rate_pct": float(group["winner"].mean() * 100.0) if len(group) else np.nan,
                    "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                    "big_winner_lots": int(group["big_winner"].sum()),
                    "stage861_pages": ",".join(
                        sorted(
                            {
                                str(int(page))
                                for page in pd.to_numeric(group["stage861_entry_atlas_page"], errors="coerce").dropna()
                                if np.isfinite(page)
                            }
                        )[:10]
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["family", "pnl_sum"], ascending=[True, True]).reset_index(drop=True)


def _load_stage847_context() -> dict[str, Any]:
    comparison = _load_csv(STAGE847_COMPARISON_PATH, required=False)
    summary = _load_csv(STAGE847_SUMMARY_PATH, required=False)
    out: dict[str, Any] = {}
    if not comparison.empty:
        row = comparison[comparison["arm"].astype(str).eq("stage847_stage819_c4_05r_stop_retry_once")]
        if not row.empty:
            item = row.iloc[0]
            out.update(
                {
                    "stage847_end_equity_delta_vs_c4": _safe_float(item.get("end_equity_delta_vs_C4")),
                    "stage847_max_dd_delta_vs_c4": _safe_float(item.get("max_dd_delta_vs_C4")),
                    "stage847_sharpe_delta_vs_c4": _safe_float(item.get("sharpe_delta_vs_C4")),
                    "stage847_total_trade_count": _safe_float(item.get("total_trade_count")),
                    "stage847_max_broker10": _safe_float(item.get("max_broker10_margin_to_equity_pct")),
                }
            )
    if not summary.empty:
        row = summary[summary["arm"].astype(str).eq("stage847_stage819_c4_05r_stop_retry_once")]
        if not row.empty:
            item = row.iloc[0]
            out.update(
                {
                    "stage847_end_equity": _safe_float(item.get("end_equity")),
                    "stage847_total_return_pct": _safe_float(item.get("total_return_pct")),
                    "stage847_max_dd_pct": _safe_float(item.get("max_dd_pct")),
                    "stage847_sharpe": _safe_float(item.get("sharpe")),
                    "stage847_total_slippage": _safe_float(item.get("total_slippage")),
                }
            )
    return out


def _hypothesis_summary(
    proxy_summary: pd.DataFrame,
    structure_stats: pd.DataFrame,
    cohort_stats: pd.DataFrame,
    stage847: dict[str, Any],
) -> pd.DataFrame:
    def row_for_proxy(proxy_id: str) -> dict[str, Any]:
        found = proxy_summary[proxy_summary["proxy_id"].eq(proxy_id)]
        return found.iloc[0].to_dict() if not found.empty else {}

    def row_for_structure(rule_id: str) -> dict[str, Any]:
        found = structure_stats[structure_stats["rule_id"].eq(rule_id)]
        return found.iloc[0].to_dict() if not found.empty else {}

    def cohort(col: str, bucket: str) -> dict[str, Any]:
        found = cohort_stats[cohort_stats["bucket_col"].eq(col) & cohort_stats["bucket"].eq(bucket)]
        return found.iloc[0].to_dict() if not found.empty else {}

    p2 = row_for_proxy("P2_stop05_retry_on_entry_reclaim")
    p3 = row_for_proxy("P3_block_or15_no_breakout")
    p4 = row_for_proxy("P4_block_no60m_1r_confirm")
    p5 = row_for_proxy("P5_hindsight_block_stop_no_reentry")
    s3 = row_for_structure("S3_two_stop_side_closes_before_reclaim")
    no_recovery = cohort("recovery_after_stop_shape_stage842", "no_same_day_recovery")
    no_stop = cohort("recovery_after_stop_shape_stage842", "no_stop05_hit")

    rows = [
        {
            "hypothesis_id": "H1_stop05_retry_reclaim_budget_locked",
            "hypothesis_text": (
                "Keep 0.5R real-time stop and retry only after entry reclaim, but future engine must freeze the released "
                "risk budget and cap second-failure reuse."
            ),
            "evidence_type": "lot_proxy_plus_existing_engine",
            "support_metric": _safe_float(p2.get("gross_proxy_delta"), 0.0),
            "right_tail_damage": _safe_float(p2.get("big_winner_delta"), 0.0),
            "affected_lots": int(p2.get("affected_lots", 0) or 0),
            "stage847_context": (
                f"C9 vs C4 equity +{_safe_float(stage847.get('stage847_end_equity_delta_vs_c4'), 0.0):,.0f}, "
                f"maxDD delta {_safe_float(stage847.get('stage847_max_dd_delta_vs_c4'), np.nan):.4f}pp"
            ),
            "decision": "watch_as_building_block_not_standalone",
            "next_action": "If continued, design a frozen real engine with risk-budget lock; do not rescan R or retry count.",
        },
        {
            "hypothesis_id": "H2_or15_entry_filter",
            "hypothesis_text": "Block entries without signal-side OR15 breakout.",
            "evidence_type": "lot_proxy_conflicts_with_prior_engine_semantics",
            "support_metric": _safe_float(p3.get("gross_proxy_delta"), 0.0),
            "right_tail_damage": _safe_float(p3.get("big_winner_delta"), 0.0),
            "affected_lots": int(p3.get("affected_lots", 0) or 0),
            "stage847_context": "Stage834 already rejected OR15 close/hold semantics; full Stage861 still damages winners.",
            "decision": "reject_no_engine",
            "next_action": "Do not revive OR length, hold bars, or OR-side stop scans.",
        },
        {
            "hypothesis_id": "H3_60m_1r_fast_confirmation",
            "hypothesis_text": "Require +1R within first 60 minutes.",
            "evidence_type": "right_tail_damage",
            "support_metric": _safe_float(p4.get("gross_proxy_delta"), 0.0),
            "right_tail_damage": _safe_float(p4.get("big_winner_delta"), 0.0),
            "affected_lots": int(p4.get("affected_lots", 0) or 0),
            "stage847_context": "Top winner atlas shows many delayed launches; fast confirmation is too crude.",
            "decision": "reject_no_engine",
            "next_action": "Do not scan 15/30/60/120 minute confirmation windows.",
        },
        {
            "hypothesis_id": "H4_structural_break_after_stop",
            "hypothesis_text": "After 0.5R stop, exit/reject on two stop-side closes or adverse OR break before reclaim.",
            "evidence_type": "full_coverage_structure_retest",
            "support_metric": _safe_float(s3.get("gross_delta_vs_baseline"), 0.0),
            "right_tail_damage": _safe_float(s3.get("big_winner_delta"), 0.0),
            "affected_lots": int(s3.get("triggered_lots", 0) or 0),
            "stage847_context": "Stage842 subset signal turns negative under full Stage861 minute coverage.",
            "decision": "reject_no_engine",
            "next_action": "Stop S1-S4 structural-break branch unless a new first-principle feature is introduced.",
        },
        {
            "hypothesis_id": "H5_no_same_day_recovery_after_stop",
            "hypothesis_text": "Stop-first lots with no same-day recovery are the clean left-tail bucket.",
            "evidence_type": "taxonomy_bucket",
            "support_metric": _safe_float(no_recovery.get("pnl_sum"), 0.0),
            "right_tail_damage": 0.0,
            "affected_lots": int(no_recovery.get("lots", 0) or 0),
            "stage847_context": "This is not live-feasible by itself because same-day non-recovery is known only at close.",
            "decision": "diagnostic_only_supports_H1",
            "next_action": "Use it only to justify retry-on-reclaim semantics, not as a standalone EOD hindsight rule.",
        },
        {
            "hypothesis_id": "H6_do_not_delay_clean_winners",
            "hypothesis_text": "No 0.5R adverse touch is the cleanest right-tail bucket; avoid filters that delay or block it.",
            "evidence_type": "taxonomy_bucket",
            "support_metric": _safe_float(no_stop.get("pnl_sum"), 0.0),
            "right_tail_damage": 0.0,
            "affected_lots": int(no_stop.get("lots", 0) or 0),
            "stage847_context": "Visual pages show slow and delayed right-tail launches, so entry filters should be suspect.",
            "decision": "design_constraint",
            "next_action": "Future rules must prove they do not cut target_first/no-stop winners.",
        },
    ]
    return pd.DataFrame(rows)


def _select_visual_rows(data: pd.DataFrame, proxy_summary: pd.DataFrame, structure_stats: pd.DataFrame) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    selections = [
        (
            "top_right_tail_do_not_filter",
            data[data["recovery_after_stop_shape_stage842"].eq("no_stop05_hit")]
            .sort_values("realized_pnl", ascending=False)
            .head(4),
        ),
        (
            "clean_left_tail_no_same_day_recovery",
            data[data["recovery_after_stop_shape_stage842"].eq("no_same_day_recovery")]
            .sort_values("realized_pnl")
            .head(4),
        ),
        (
            "stop_then_reached_1r_recoverable",
            data[data["recovery_after_stop_shape_stage842"].eq("post_stop_reached_1r")]
            .sort_values("realized_pnl", ascending=False)
            .head(4),
        ),
        (
            "structural_s3_damaged_winners",
            data[
                pd.to_numeric(data["rule_s3_two_stop_side_closes_before_reclaim"], errors="coerce")
                .fillna(0)
                .eq(1)
                & data["realized_pnl"].gt(0)
            ]
            .sort_values("realized_pnl", ascending=False)
            .head(4),
        ),
        (
            "or15_filter_would_block_winners",
            data[
                ~pd.to_numeric(data["opening_range_breakout_confirmed"], errors="coerce").fillna(0).eq(1)
                & data["realized_pnl"].gt(0)
            ]
            .sort_values("realized_pnl", ascending=False)
            .head(4),
        ),
        (
            "no60_confirm_would_block_big_winners",
            data[
                ~pd.to_numeric(data["confirm_fast_60m_1r"], errors="coerce").fillna(0).eq(1)
                & data["big_winner"].eq(1)
            ]
            .sort_values("realized_pnl", ascending=False)
            .head(4),
        ),
    ]
    for reason, frame in selections:
        if frame.empty:
            continue
        part = frame.copy()
        part["visual_reason"] = reason
        pieces.append(part)
    if not pieces:
        return pd.DataFrame()
    selected = pd.concat(pieces, ignore_index=True, sort=False)
    selected = selected.drop_duplicates("lot_id", keep="first").head(MAX_VISUAL_ROWS)
    return selected.reset_index(drop=True)


def _plot_lot(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").reset_index(drop=True) if not bars.empty else pd.DataFrame()
    record = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "visual_reason": row.get("visual_reason", ""),
        "stage861_entry_atlas_page": _safe_float(row.get("stage861_entry_atlas_page")),
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
        return record

    s825._plot_candles(ax, day.head(360))
    window = day.head(360).copy().reset_index(drop=True)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    sign = _direction_sign(direction)
    if np.isfinite(entry_price):
        ax.axhline(entry_price, color="#2563eb", linewidth=0.95)
    if np.isfinite(entry_price) and np.isfinite(risk_pct) and risk_pct > 0:
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#dc2626", linewidth=0.9, linestyle="--")
        ax.axhline(entry_price * (1.0 + sign * 0.5 * risk_pct), color="#16a34a", linewidth=0.8, linestyle=":")
        ax.axhline(entry_price * (1.0 + sign * risk_pct), color="#16a34a", linewidth=0.85)
    if len(window) >= OPENING_RANGE_BARS:
        opening = window.head(OPENING_RANGE_BARS)
        ax.axhline(float(opening["high"].max()), color="#7c3aed", linewidth=0.7, linestyle="--", alpha=0.7)
        ax.axhline(float(opening["low"].min()), color="#7c3aed", linewidth=0.7, linestyle="--", alpha=0.7)
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)
    marker_cols = [
        ("first_stop05_idx", "#dc2626", "-"),
        ("first_reclaim_entry_idx", "#2563eb", ":"),
        ("two_stop_side_closes_idx", "#9333ea", "--"),
        ("first_adverse_or15_touch_idx", "#111827", "--"),
    ]
    for column, color, style in marker_cols:
        idx = row.get(column)
        if pd.notna(idx) and int(idx) < len(window):
            ax.axvline(int(idx), color=color, linewidth=0.95, linestyle=style, alpha=0.85)
    ticks = np.linspace(0, len(window) - 1, num=min(8, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.grid(True, alpha=0.18)
    title = (
        f"{row.get('visual_reason','')} | lot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f} "
        f"recover={row.get('recovery_after_stop_shape_stage842','')} "
        f"first05={row.get('entry_day_first_0p5r_outcome','')} "
        f"OR={_safe_float(row.get('opening_range_breakout_confirmed'), np.nan):.0f} "
        f"c60={_safe_float(row.get('confirm_fast_60m_1r'), np.nan):.0f} "
        f"stage861_page={_safe_float(row.get('stage861_entry_atlas_page'), np.nan):.0f}"
    )
    ax.set_title(title, loc="left", fontsize=8.1)
    return record


def _plot_visual_atlas(selected: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            record = _plot_lot(ax, row, minute_by_symbol)
            record["visual_page"] = page
            record["realized_pnl"] = _safe_float(row.get("realized_pnl"))
            record["r_multiple"] = _safe_float(row.get("r_multiple"))
            record["recovery_after_stop_shape"] = row.get("recovery_after_stop_shape_stage842", "")
            rows.append(record)
        fig.suptitle(
            "Stage862 visual audit: blue=entry red=0.5R stop green=favorable purple=OR15 black/adverse markers",
            fontsize=13,
        )
        path = Path(str(VISUAL_ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    cohort_stats: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    structure_stats: pd.DataFrame,
    structure_yearly: pd.DataFrame,
    hypothesis_summary: pd.DataFrame,
    pressure_features: pd.DataFrame,
    visual_paths: list[Path],
) -> None:
    lines = [
        "# Stage862 Stage861 Rule Hypothesis Audit",
        "",
        "## Scope",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- source candidate: `{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- Stage862 is read-only: it does not change Stage819/Stage372, does not connect CTP, and does not submit orders.",
        "- Goal: combine full Stage861 minute data and visual atlas evidence into a small set of rule hypotheses.",
        "",
        "## External Research Judgment",
        "",
        "- Public intraday ORB examples support only broad shapes such as opening range, stop, retry, and intraday exit.",
        "- Backtesting references warn that same-bar stop/target ordering and bar granularity matter; therefore any promoted rule must be implemented as minute-by-minute engine logic.",
        "- Judgment: no public parameter is copied. Stage862 rejects parameter scans and only classifies low-freedom rule shapes.",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Hypothesis Decisions",
        "",
        _md_table(hypothesis_summary, max_rows=20),
        "",
        "## Cohort Evidence",
        "",
        _md_table(cohort_stats.head(80), max_rows=80),
        "",
        "## Lot-Level Proxy Evidence",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Proxy Yearly Stability",
        "",
        _md_table(proxy_yearly.head(80), max_rows=80),
        "",
        "## Full-Coverage Structural Rule Retest",
        "",
        _md_table(structure_stats, max_rows=20),
        "",
        "## Structural Yearly Stability",
        "",
        _md_table(structure_yearly.head(80), max_rows=80),
        "",
        "## Pressure Key Date Reminder",
        "",
        _md_table(pressure_features.head(30), max_rows=30),
        "",
        "## Visual Audit Pages",
        "",
        *[f"- visual page: `{path}`" for path in visual_paths],
        "",
        "## Decision",
        "",
        "- Decision: `stage862_stop_retry_budget_lock_watch_structural_filters_rejected_no_engine`.",
        "- Keep H1 only as a building block: real-time 0.5R stop + retry on reclaim remains the only live-feasible positive lot-level shape, but Stage847/C9 already proved it is not enough as a standalone engine because max drawdown worsened versus C4.",
        "- Reject OR15 and fast-confirmation filters: they look attractive in isolated proxies but damage delayed right-tail winners and conflict with prior engine semantics.",
        "- Reject S1-S4 structural-break exits: after Stage861 full coverage, the earlier subset signal is no longer positive and damages big winners.",
        "- Next valid work is a frozen engine design that combines H1 with risk-budget lock / second-failure discipline. Do not scan R multiples, OR minutes, confirmation windows, retry counts, product names, directions, or years.",
        "",
        "## Overfit Reflection",
        "",
        "- Before run: no. The run audits full Stage861 coverage and fixed previously known rule shapes.",
        "- After run: no for the audit itself. A future rule would become overfit if it is built from a specific page, year, product, direction, or decimal threshold.",
        "",
        "## Continue-Value Reflection",
        "",
        "- Before run: yes. Stage861 made full evidence available; the next necessary step was hypothesis triage.",
        "- After run: yes, but narrower. Most filters are now rejected; continuing value is only in a frozen H1-derived engine with budget lock and second-failure handling.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    features = _prepare_entry_features()
    minute_bars = _load_full_minute_bars()
    pressure_features = _load_csv(PRESSURE_FEATURES_PATH)
    stage861_summary = _load_csv(STAGE861_SUMMARY_PATH)
    stage847_context = _load_stage847_context()

    proxy_summary, proxy_yearly = _proxy_tables(features)
    structure_data = _structure_taxonomy(features, minute_bars)
    structure_stats, structure_yearly = _structure_rule_stats(structure_data)
    cohort_stats = _cohort_stats(structure_data)
    hypothesis_summary = _hypothesis_summary(proxy_summary, structure_stats, cohort_stats, stage847_context)
    selected = _select_visual_rows(structure_data, proxy_summary, structure_stats)
    visual_paths, visual_manifest = _plot_visual_atlas(selected, minute_bars)

    no_recovery = cohort_stats[
        cohort_stats["bucket_col"].eq("recovery_after_stop_shape_stage842")
        & cohort_stats["bucket"].eq("no_same_day_recovery")
    ]
    no_stop = cohort_stats[
        cohort_stats["bucket_col"].eq("recovery_after_stop_shape_stage842")
        & cohort_stats["bucket"].eq("no_stop05_hit")
    ]
    p2 = proxy_summary[proxy_summary["proxy_id"].eq("P2_stop05_retry_on_entry_reclaim")]
    s3 = structure_stats[structure_stats["rule_id"].eq("S3_two_stop_side_closes_before_reclaim")]
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "decision": "stage862_stop_retry_budget_lock_watch_structural_filters_rejected_no_engine",
                "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
                "input_stage861_entry_lots": int(len(features)),
                "input_stage861_full_minute_bars": int(len(minute_bars)),
                "stage861_entry_day_coverage_rate": _safe_float(
                    stage861_summary.iloc[0].get("entry_day_coverage_rate") if not stage861_summary.empty else np.nan
                ),
                "base_lot_pnl": float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "p2_stop_retry_proxy_delta": _safe_float(p2.iloc[0].get("gross_proxy_delta") if not p2.empty else np.nan),
                "p2_big_winner_delta": _safe_float(p2.iloc[0].get("big_winner_delta") if not p2.empty else np.nan),
                "no_same_day_recovery_lots": int(no_recovery.iloc[0].get("lots", 0)) if not no_recovery.empty else 0,
                "no_same_day_recovery_pnl": _safe_float(no_recovery.iloc[0].get("pnl_sum") if not no_recovery.empty else np.nan),
                "no_stop05_hit_lots": int(no_stop.iloc[0].get("lots", 0)) if not no_stop.empty else 0,
                "no_stop05_hit_pnl": _safe_float(no_stop.iloc[0].get("pnl_sum") if not no_stop.empty else np.nan),
                "s3_full_coverage_delta": _safe_float(
                    s3.iloc[0].get("gross_delta_vs_baseline") if not s3.empty else np.nan
                ),
                "s3_big_winner_delta": _safe_float(s3.iloc[0].get("big_winner_delta") if not s3.empty else np.nan),
                "stage847_c9_end_equity_delta_vs_c4": _safe_float(
                    stage847_context.get("stage847_end_equity_delta_vs_c4")
                ),
                "stage847_c9_max_dd_delta_vs_c4": _safe_float(stage847_context.get("stage847_max_dd_delta_vs_c4")),
                "visual_review_pages": int(len(visual_paths)),
                "new_rule_allowed": 0,
                "engine_allowed": 0,
                "ab_allowed": 0,
            }
        ]
    )

    cohort_stats.to_csv(COHORT_STATS_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(PROXY_YEARLY_PATH, index=False, encoding="utf-8-sig")
    structure_stats.to_csv(STRUCTURE_RULE_STATS_PATH, index=False, encoding="utf-8-sig")
    structure_yearly.to_csv(STRUCTURE_YEARLY_PATH, index=False, encoding="utf-8-sig")
    hypothesis_summary.to_csv(HYPOTHESIS_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    visual_manifest.to_csv(VISUAL_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_report(
        summary,
        cohort_stats,
        proxy_summary,
        proxy_yearly,
        structure_stats,
        structure_yearly,
        hypothesis_summary,
        pressure_features,
        visual_paths,
    )

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": str(summary.iloc[0]["decision"]),
        "metrics": summary.iloc[0].to_dict(),
        "inputs": {
            "stage861_entry_features": str(ENTRY_FEATURES_PATH),
            "stage861_full_minute_bars": str(FULL_MINUTE_BARS_PATH),
            "stage861_entry_atlas_manifest": str(ENTRY_ATLAS_MANIFEST_PATH),
            "stage847_comparison": str(STAGE847_COMPARISON_PATH),
        },
        "outputs": {
            "cohort_stats": str(COHORT_STATS_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "proxy_yearly": str(PROXY_YEARLY_PATH),
            "structure_rule_stats": str(STRUCTURE_RULE_STATS_PATH),
            "structure_yearly": str(STRUCTURE_YEARLY_PATH),
            "hypothesis_summary": str(HYPOTHESIS_SUMMARY_PATH),
            "visual_manifest": str(VISUAL_MANIFEST_PATH),
            "visual_paths": [str(path) for path in visual_paths],
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "allow_new_rule": False,
        "allow_engine": False,
        "allow_ab": False,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision["metrics"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
