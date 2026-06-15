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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage891"
MODEL_TAG = "stage891_stage890_intraday_route_closure_v1"
OUTPUT_PREFIX = "qmt_roll_stage891_stage890_intraday_route_closure"
SOURCE_CANDIDATE = "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"

ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_matrix_{MODEL_TAG}.csv"
SCORECARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scorecard_{MODEL_TAG}.csv"
VISUAL_INDEX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_index_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATHS = {
    "stage861_decision": OUTPUT_DIR
    / "qmt_roll_stage861_stage860_full_visual_atlas_decision_stage861_stage860_full_visual_atlas_v1.json",
    "stage863_decision": OUTPUT_DIR
    / "qmt_roll_stage863_stage847_c10_budget_lock_engine_decision_stage863_stage847_c10_budget_lock_engine_v1.json",
    "stage863_comparison": OUTPUT_DIR
    / "qmt_roll_stage863_stage847_c10_budget_lock_engine_comparison_stage863_stage847_c10_budget_lock_engine_v1.csv",
    "stage876_decision": OUTPUT_DIR
    / "qmt_roll_stage876_stage861_or_extension_chase_audit_decision_stage876_stage861_or_extension_chase_audit_v1.json",
    "stage876_proxy": OUTPUT_DIR
    / "qmt_roll_stage876_stage861_or_extension_chase_audit_proxy_summary_stage876_stage861_or_extension_chase_audit_v1.csv",
    "stage878_decision": OUTPUT_DIR
    / "qmt_roll_stage878_stage861_early_oi_participation_audit_decision_stage878_stage861_early_oi_participation_audit_v1.json",
    "stage879_decision": OUTPUT_DIR
    / "qmt_roll_stage879_stage878_early_oi_guard_engine_decision_stage879_stage878_early_oi_guard_engine_v1.json",
    "stage880_decision": OUTPUT_DIR
    / "qmt_roll_stage880_stage863_session_boundary_audit_decision_stage880_stage863_session_boundary_audit_v1.json",
    "stage881_decision": OUTPUT_DIR
    / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_decision_stage881_stage863_progress_pyramid_proxy_audit_v1.json",
    "stage882_decision": OUTPUT_DIR
    / "qmt_roll_stage882_stage881_progress_pyramid_engine_decision_stage882_stage881_progress_pyramid_engine_v1.json",
    "stage882_comparison": OUTPUT_DIR
    / "qmt_roll_stage882_stage881_progress_pyramid_engine_comparison_stage882_stage881_progress_pyramid_engine_v1.csv",
    "stage883_decision": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_decision_stage883_stage882_progress_pyramid_sleeve1_engine_v1.json",
    "stage883_comparison": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_comparison_stage883_stage882_progress_pyramid_slee1_engine_v1.csv",
    "stage883_comparison_fallback": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_comparison_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv",
    "stage888_decision": OUTPUT_DIR
    / "qmt_roll_stage888_stage887_pyramiding_route_closure_decision_stage888_stage887_pyramiding_route_closure_v1.json",
    "stage889_decision": OUTPUT_DIR
    / "qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_decision_stage889_stage863_c9_loss_shape_coverage_audit_v1.json",
    "stage890_decision": OUTPUT_DIR
    / "qmt_roll_stage890_stage889_first60_volume_triad_audit_decision_stage890_stage889_first60_volume_triad_audit_v1.json",
}

VISUAL_MANIFESTS = {
    "Stage861 entry full-cycle atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage861_stage860_full_visual_atlas_entry_atlas_manifest_stage861_stage860_full_visual_atlas_v1.csv",
        "qmt_roll_stage861_stage860_full_visual_atlas_entry_atlas_page*_stage861_stage860_full_visual_atlas_v1.png",
    ),
    "Stage861 pressure atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage861_stage860_full_visual_atlas_pressure_atlas_manifest_stage861_stage860_full_visual_atlas_v1.csv",
        "qmt_roll_stage861_stage860_full_visual_atlas_pressure_atlas_page*_stage861_stage860_full_visual_atlas_v1.png",
    ),
    "Stage878 early OI atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage878_stage861_early_oi_participation_audit_atlas_manifest_stage878_stage861_early_oi_participation_audit_v1.csv",
        "qmt_roll_stage878_stage861_early_oi_participation_audit_atlas_page*_stage878_stage861_early_oi_participation_audit_v1.png",
    ),
    "Stage879 early OI engine atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage879_stage878_early_oi_guard_engine_atlas_manifest_stage879_stage878_early_oi_guard_engine_v1.csv",
        "qmt_roll_stage879_stage878_early_oi_guard_engine_atlas_page*_stage879_stage878_early_oi_guard_engine_v1.png",
    ),
    "Stage880 session atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage880_stage863_session_boundary_audit_atlas_manifest_stage880_stage863_session_boundary_audit_v1.csv",
        "qmt_roll_stage880_stage863_session_boundary_audit_atlas_page*_stage880_stage863_session_boundary_audit_v1.png",
    ),
    "Stage881 progress proxy atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_manifest_stage881_stage863_progress_pyramid_proxy_audit_v1.csv",
        "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page*_stage881_stage863_progress_pyramid_proxy_audit_v1.png",
    ),
    "Stage882 progress engine atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_manifest_stage882_stage881_progress_pyramid_engine_v1.csv",
        "qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_page*_stage882_stage881_progress_pyramid_engine_v1.png",
    ),
    "Stage883 sleeve engine atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_atlas_manifest_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv",
        "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_atlas_page*_stage883_stage882_progress_pyramid_sleeve1_engine_v1.png",
    ),
    "Stage889 loss-shape atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_atlas_manifest_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv",
        "qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_atlas_page*_stage889_stage863_c9_loss_shape_coverage_audit_v1.png",
    ),
    "Stage890 volume triad atlas": (
        OUTPUT_DIR
        / "qmt_roll_stage890_stage889_first60_volume_triad_audit_atlas_manifest_stage890_stage889_first60_volume_triad_audit_v1.csv",
        "qmt_roll_stage890_stage889_first60_volume_triad_audit_atlas_page*_stage890_stage889_first60_volume_triad_audit_v1.png",
    ),
}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _path(key: str) -> Path:
    if key == "stage883_comparison":
        first = PATHS[key]
        if first.exists():
            return first
        return PATHS["stage883_comparison_fallback"]
    return PATHS[key]


def _pick_row(frame: pd.DataFrame, arm_contains: str) -> pd.Series:
    hit = frame[frame["arm"].astype(str).str.contains(arm_contains, regex=False)]
    if hit.empty:
        raise RuntimeError(f"missing comparison row containing {arm_contains}")
    return hit.iloc[0]


def _best_or_proxy() -> dict[str, Any]:
    proxy = _load_csv(PATHS["stage876_proxy"])
    if "gross_proxy_delta" not in proxy.columns:
        return {
            "proxy_id": "unknown",
            "gross_proxy_delta": np.nan,
            "winner_cut": np.nan,
            "loser_saved": np.nan,
            "positive_delta_years": np.nan,
            "negative_delta_years": np.nan,
        }
    sort_cols = ["gross_proxy_delta"]
    best = proxy.sort_values(sort_cols, ascending=False).iloc[0].to_dict()
    return best


def _build_visual_index() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, (manifest, pattern) in VISUAL_MANIFESTS.items():
        manifest_rows = 0
        if manifest.exists():
            manifest_rows = len(_load_csv(manifest))
        pages = sorted(OUTPUT_DIR.glob(pattern))
        rows.append(
            {
                "visual_scope": scope,
                "manifest_exists": manifest.exists(),
                "manifest_rows": manifest_rows,
                "png_pages": len(pages),
                "first_png": str(pages[0]) if pages else "",
                "manifest_path": str(manifest),
            }
        )
    return pd.DataFrame(rows)


def _build_route_matrix() -> pd.DataFrame:
    s861 = _load_json(PATHS["stage861_decision"])
    s863 = _load_json(PATHS["stage863_decision"])
    cmp863 = _load_csv(PATHS["stage863_comparison"])
    c9 = _pick_row(cmp863, "stage847_stage819_c4_05r_stop_retry_once")
    c4 = _pick_row(cmp863, "stage830_stage819_c2_broker10_100_cap")

    s876 = _load_json(PATHS["stage876_decision"])
    best_or = _best_or_proxy()
    s878 = _load_json(PATHS["stage878_decision"])
    s879 = _load_json(PATHS["stage879_decision"])
    s880 = _load_json(PATHS["stage880_decision"])
    s881 = _load_json(PATHS["stage881_decision"])
    s882 = _load_json(PATHS["stage882_decision"])
    cmp882 = _load_csv(PATHS["stage882_comparison"])
    c16 = _pick_row(cmp882, "stage882_stage819_c9_progress_pyramid_once")
    s883 = _load_json(PATHS["stage883_decision"])
    cmp883 = _load_csv(_path("stage883_comparison"))
    c17 = _pick_row(cmp883, "stage883_stage819_c9_progress_pyramid_sleeve1_once")
    s888 = _load_json(PATHS["stage888_decision"])
    s889 = _load_json(PATHS["stage889_decision"])
    s890 = _load_json(PATHS["stage890_decision"])

    metrics861 = s861["metrics"]
    favorable_oi = s878["favorable_price_oi_up"]
    adverse_proxy = s878["adverse_any_proxy"]
    c15 = s879["candidate_result"]
    best889 = s889["best_proxy"]
    best890 = s890["best_proxy"]

    rows = [
        {
            "stage": "Stage861",
            "route_branch": "data_and_visual_coverage",
            "evidence_kind": "full_cycle_visual_atlas",
            "decision": s861["decision"],
            "rule_or_shape": "full entry-day minute atlas and pressure atlas",
            "positive_evidence": (
                f"entry_coverage={metrics861['entry_day_covered_lots']}/{metrics861['entry_lots']}; "
                f"pressure_coverage={metrics861['pressure_covered_dates']}/{metrics861['pressure_key_dates']}"
            ),
            "negative_evidence": "coverage is evidence infrastructure, not a rule",
            "delta_million": np.nan,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "coverage_complete_no_rule",
        },
        {
            "stage": "Stage863",
            "route_branch": "base_intraday_rule",
            "evidence_kind": "true_engine",
            "decision": s863["decision"],
            "rule_or_shape": "C9 = 0.5R stop + reclaim retry once",
            "positive_evidence": (
                f"vs_C4_equity_delta={c9['end_equity_delta_vs_C4']:.2f}; "
                f"vs_C4_dd_delta={c9['max_dd_delta_vs_C4']:.4f}pp; "
                f"vs_C4_sharpe_delta={c9['sharpe_delta_vs_C4']:.6f}"
            ),
            "negative_evidence": (
                f"broker10={c9['max_broker10_margin_to_equity_pct']:.4f}% "
                f"vs C4 {c4['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "delta_million": c9["end_equity_delta_vs_C4"] / 1_000_000,
            "end_equity_delta_vs_c9": 0.0,
            "max_dd_delta_vs_c9_pp": 0.0,
            "sharpe_delta_vs_c9": 0.0,
            "max_broker10_pct": c9["max_broker10_margin_to_equity_pct"],
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "positive_backbone_but_not_promoted",
        },
        {
            "stage": "Stage876",
            "route_branch": "entry_filter",
            "evidence_kind": "readonly_proxy",
            "decision": s876["decision"],
            "rule_or_shape": "OR15 extension chase filter",
            "positive_evidence": f"best_proxy_delta={best_or.get('gross_proxy_delta', np.nan):.2f}",
            "negative_evidence": (
                f"winner_cut={best_or.get('winner_cut', np.nan):.2f}; "
                f"proxy_id={best_or.get('proxy_id', '')}"
            ),
            "delta_million": best_or.get("gross_proxy_delta", np.nan) / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": best_or.get("winner_cut", np.nan) / 1_000_000,
            "loser_saved_million": best_or.get("loser_saved", np.nan) / 1_000_000,
            "verdict": "entry_filter_rejected",
        },
        {
            "stage": "Stage878",
            "route_branch": "external_participation",
            "evidence_kind": "readonly_proxy",
            "decision": s878["decision"],
            "rule_or_shape": "first60 price/OI participation quadrants",
            "positive_evidence": (
                f"favorable_price_oi_up_lots={favorable_oi['lots']}; "
                f"pnl={favorable_oi['pnl_sum']:.2f}; big_winners={favorable_oi['big_winner_lots']}"
            ),
            "negative_evidence": (
                f"adverse_proxy_winner_cut={adverse_proxy['winner_cut']:.2f}; "
                f"big_winner_cut={adverse_proxy['big_winner_cut']:.2f}"
            ),
            "delta_million": adverse_proxy["gross_proxy_delta"] / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": adverse_proxy["winner_cut"] / 1_000_000,
            "loser_saved_million": adverse_proxy["loser_saved"] / 1_000_000,
            "verdict": "signal_exists_not_exit_rule",
        },
        {
            "stage": "Stage879",
            "route_branch": "external_participation",
            "evidence_kind": "true_engine",
            "decision": s879["decision"],
            "rule_or_shape": "early OI-down no-progress exit at 60th minute",
            "positive_evidence": f"dd_delta_vs_C9={c15['max_dd_delta_vs_C9']:.4f}pp",
            "negative_evidence": (
                f"equity_delta_vs_C9={c15['end_equity_delta_vs_C9']:.2f}; "
                f"sharpe_delta_vs_C9={c15['sharpe_delta_vs_C9']:.6f}; "
                f"broker10={c15['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "delta_million": c15["end_equity_delta_vs_C9"] / 1_000_000,
            "end_equity_delta_vs_c9": c15["end_equity_delta_vs_C9"],
            "max_dd_delta_vs_c9_pp": c15["max_dd_delta_vs_C9"],
            "sharpe_delta_vs_c9": c15["sharpe_delta_vs_C9"],
            "max_broker10_pct": c15["max_broker10_margin_to_equity_pct"],
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "engine_failed_return_sharpe",
        },
        {
            "stage": "Stage880",
            "route_branch": "session_boundary",
            "evidence_kind": "readonly_proxy",
            "decision": s880["decision"],
            "rule_or_shape": "same-session-only retry",
            "positive_evidence": f"cross_session_events={s880['cross_session_reentry_events']}",
            "negative_evidence": (
                f"proxy_delta={s880['same_session_only_proxy_delta']:.2f}; "
                f"winner_cut={s880['same_session_only_winner_cut']:.2f}"
            ),
            "delta_million": s880["same_session_only_proxy_delta"] / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": s880["same_session_only_winner_cut"] / 1_000_000,
            "loser_saved_million": s880["same_session_only_loser_saved"] / 1_000_000,
            "verdict": "session_filter_rejected",
        },
        {
            "stage": "Stage881",
            "route_branch": "right_tail_participation",
            "evidence_kind": "readonly_proxy",
            "decision": s881["decision"],
            "rule_or_shape": "+0.5R progress pyramiding proxy",
            "positive_evidence": (
                f"proxy_delta={s881['pyramid_proxy_delta']:.2f}; "
                f"candidates={s881['pyramid_candidate_lots']}"
            ),
            "negative_evidence": "proxy lacks margin and equity path",
            "delta_million": s881["pyramid_proxy_delta"] / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "proxy_only_requires_engine",
        },
        {
            "stage": "Stage882",
            "route_branch": "right_tail_participation",
            "evidence_kind": "true_engine",
            "decision": s882["decision"],
            "rule_or_shape": "same-volume +0.5R progress pyramiding",
            "positive_evidence": f"equity_delta_vs_C9={c16['end_equity_delta_vs_C9']:.2f}",
            "negative_evidence": (
                f"dd_delta_vs_C9={c16['max_dd_delta_vs_C9']:.4f}pp; "
                f"sharpe_delta_vs_C9={c16['sharpe_delta_vs_C9']:.6f}; "
                f"broker10={c16['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "delta_million": c16["end_equity_delta_vs_C9"] / 1_000_000,
            "end_equity_delta_vs_c9": c16["end_equity_delta_vs_C9"],
            "max_dd_delta_vs_c9_pp": c16["max_dd_delta_vs_C9"],
            "sharpe_delta_vs_c9": c16["sharpe_delta_vs_C9"],
            "max_broker10_pct": c16["max_broker10_margin_to_equity_pct"],
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "engine_failed_survival",
        },
        {
            "stage": "Stage883",
            "route_branch": "right_tail_participation",
            "evidence_kind": "true_engine",
            "decision": s883["decision"],
            "rule_or_shape": "one-lot +0.5R progress sleeve",
            "positive_evidence": (
                f"equity_delta_vs_C9={c17['end_equity_delta_vs_C9']:.2f}; "
                f"dd_delta_vs_C9={c17['max_dd_delta_vs_C9']:.4f}pp"
            ),
            "negative_evidence": (
                f"sharpe_delta_vs_C9={c17['sharpe_delta_vs_C9']:.6f}; "
                f"broker10={c17['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "delta_million": c17["end_equity_delta_vs_C9"] / 1_000_000,
            "end_equity_delta_vs_c9": c17["end_equity_delta_vs_C9"],
            "max_dd_delta_vs_c9_pp": c17["max_dd_delta_vs_C9"],
            "sharpe_delta_vs_c9": c17["sharpe_delta_vs_C9"],
            "max_broker10_pct": c17["max_broker10_margin_to_equity_pct"],
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "engine_failed_broker10_sharpe",
        },
        {
            "stage": "Stage888",
            "route_branch": "right_tail_participation",
            "evidence_kind": "route_closure",
            "decision": s888["decision"],
            "rule_or_shape": "pyramiding/sleeve route closure",
            "positive_evidence": "right-tail participation is real",
            "negative_evidence": "all pressure exit/gate rescues failed or were too costly",
            "delta_million": np.nan,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": np.nan,
            "loser_saved_million": np.nan,
            "verdict": "branch_closed",
        },
        {
            "stage": "Stage889",
            "route_branch": "c9_loss_body",
            "evidence_kind": "readonly_proxy",
            "decision": s889["decision"],
            "rule_or_shape": best889["rule_text"],
            "positive_evidence": f"best_proxy_delta={best889['gross_proxy_delta']:.2f}",
            "negative_evidence": (
                f"positive_years={best889['positive_delta_years']}; "
                f"negative_years={best889['negative_delta_years']}; "
                f"trigger_lots={best889['trigger_lots']}"
            ),
            "delta_million": best889["gross_proxy_delta"] / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": best889["winner_cut"] / 1_000_000,
            "loser_saved_million": best889["loser_saved"] / 1_000_000,
            "verdict": "tiny_proxy_year_fragile",
        },
        {
            "stage": "Stage890",
            "route_branch": "external_participation",
            "evidence_kind": "readonly_proxy",
            "decision": s890["decision"],
            "rule_or_shape": best890["rule_text"],
            "positive_evidence": f"best_proxy_delta={best890['gross_proxy_delta']:.2f}",
            "negative_evidence": (
                f"trigger_lots={best890['trigger_lots']}; "
                f"positive_years={best890['positive_delta_years']}; "
                f"negative_years={best890['negative_delta_years']}"
            ),
            "delta_million": best890["gross_proxy_delta"] / 1_000_000,
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "winner_cut_million": best890["winner_cut"] / 1_000_000,
            "loser_saved_million": best890["loser_saved"] / 1_000_000,
            "verdict": "tiny_sample_no_engine",
        },
    ]
    return pd.DataFrame(rows)


def _build_scorecard(route: pd.DataFrame, visual: pd.DataFrame) -> pd.DataFrame:
    stage863 = route[route["stage"].eq("Stage863")].iloc[0]
    stage879 = route[route["stage"].eq("Stage879")].iloc[0]
    stage882 = route[route["stage"].eq("Stage882")].iloc[0]
    stage883 = route[route["stage"].eq("Stage883")].iloc[0]
    stage889 = route[route["stage"].eq("Stage889")].iloc[0]
    stage890 = route[route["stage"].eq("Stage890")].iloc[0]
    total_visual_pages = int(visual["png_pages"].sum())
    return pd.DataFrame(
        [
            {
                "requirement": "new_line_and_candidate_isolation",
                "status": "proven",
                "evidence": f"line_id={LINE_ID}; source_candidate={SOURCE_CANDIDATE}; guardrails readonly",
                "decision_impact": "research stays isolated from official Stage372 and official candidate config",
            },
            {
                "requirement": "full_cycle_trade_data_and_visual_review",
                "status": "proven",
                "evidence": f"Stage861 has 341/341 entry lots and 19/19 pressure dates; visual pages counted here={total_visual_pages}",
                "decision_impact": "coverage gap is no longer the blocker",
            },
            {
                "requirement": "rule_based_non_ai_intraday_logic",
                "status": "proven",
                "evidence": "tested rules use R stops, reclaim retry, OR15, first60 price/OI/volume, session labels, pressure labels",
                "decision_impact": "all candidates are rule-based and real-time definable before promotion",
            },
            {
                "requirement": "base_rule_improves_C4_without_unacceptable_path_risk",
                "status": "mixed",
                "evidence": (
                    f"Stage863 C9 delta vs C4={stage863['delta_million']:.4f}m, "
                    f"but max broker10={stage863['max_broker10_pct']:.4f}%"
                ),
                "decision_impact": "C9 is the useful backbone, not a direct official replacement",
            },
            {
                "requirement": "extensions_add_return_or_cut_left_tail_without_killing_right_tail",
                "status": "failed",
                "evidence": (
                    f"Stage879 delta={stage879['delta_million']:.4f}m; "
                    f"Stage882 broker10={stage882['max_broker10_pct']:.4f}%; "
                    f"Stage883 sharpe_delta={stage883['sharpe_delta_vs_c9']:.6f}"
                ),
                "decision_impact": "do not promote early-OI guard, pyramiding, or one-lot sleeve",
            },
            {
                "requirement": "minute_K_body_has_remaining_clean_rule",
                "status": "failed",
                "evidence": (
                    f"Stage889 best delta={stage889['delta_million']:.4f}m; "
                    f"Stage890 best delta={stage890['delta_million']:.4f}m with tiny triggers"
                ),
                "decision_impact": "stop small variants on 0.5R/1R/OR15/first60/EOD/volume",
            },
            {
                "requirement": "promotion_or_AB_trigger",
                "status": "not_met",
                "evidence": "no Stage878-890 branch passes true-engine return, Sharpe, drawdown, broker10, and robustness together",
                "decision_impact": "no A/B and no official candidate modification",
            },
        ]
    )


def _plot_summary(route: pd.DataFrame, visual: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(18, 15))

    coverage_labels = ["entry lots", "pressure dates"]
    coverage_rates = [100.0, 100.0]
    axes[0].bar(coverage_labels, coverage_rates, color=["#2f7f6f", "#4575b4"])
    axes[0].set_ylim(0, 110)
    axes[0].set_ylabel("coverage %")
    axes[0].set_title("Stage861 full-cycle minute K coverage")
    for idx, value in enumerate(coverage_rates):
        axes[0].text(idx, value + 2, f"{value:.0f}%", ha="center", fontsize=10)

    deltas = route[route["delta_million"].notna()].copy()
    colors = ["#2ca25f" if x >= 0 else "#de2d26" for x in deltas["delta_million"]]
    axes[1].bar(deltas["stage"], deltas["delta_million"], color=colors)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_ylabel("delta, million")
    axes[1].set_title("Proxy or engine deltas by route evidence")
    axes[1].tick_params(axis="x", rotation=35)

    engines = route[route["evidence_kind"].eq("true_engine")].copy()
    axes[2].scatter(
        engines["max_broker10_pct"],
        engines["sharpe_delta_vs_c9"],
        s=np.maximum(60, np.abs(engines["delta_million"].fillna(0)) * 12),
        c=["#4575b4", "#de2d26", "#fdae61", "#f46d43"][: len(engines)],
        alpha=0.85,
    )
    for _, row in engines.iterrows():
        axes[2].annotate(row["stage"], (row["max_broker10_pct"], row["sharpe_delta_vs_c9"]), xytext=(5, 5), textcoords="offset points")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].axvline(100, color="gray", linestyle="--", linewidth=0.8)
    axes[2].set_xlabel("max broker10 margin/equity %")
    axes[2].set_ylabel("Sharpe delta vs C9")
    axes[2].set_title("True-engine promotion stress: broker10 vs Sharpe")

    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(route: pd.DataFrame, scorecard: pd.DataFrame, visual: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage891 intraday route closure audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- source_candidate: `{SOURCE_CANDIDATE}`",
        "- scope: readonly route-level closure for Stage861/863 and Stage878-890 evidence.",
        "- guardrail: no new trade rule, no engine change, no official Stage372 change, no official candidate config change, no CTP, no order API, no A/B.",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- conclusion: {decision['conclusion']}",
        "",
        "## Route Matrix",
        "",
        _md_table(
            route[
                [
                    "stage",
                    "route_branch",
                    "evidence_kind",
                    "decision",
                    "delta_million",
                    "max_broker10_pct",
                    "sharpe_delta_vs_c9",
                    "verdict",
                ]
            ],
            max_rows=None,
        ),
        "",
        "## Scorecard",
        "",
        _md_table(scorecard, max_rows=None),
        "",
        "## Visual Index",
        "",
        _md_table(visual[["visual_scope", "manifest_exists", "manifest_rows", "png_pages", "first_png"]], max_rows=None),
        "",
        "## Output Files",
        "",
        f"- route matrix: `{ROUTE_MATRIX_PATH}`",
        f"- scorecard: `{SCORECARD_PATH}`",
        f"- visual index: `{VISUAL_INDEX_PATH}`",
        f"- summary chart: `{SUMMARY_CHART_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        "",
        "## Anti-overfit Reflection",
        "",
        "- Before run: no. This audit does not create parameters; it consolidates frozen evidence and guardrails.",
        "- After run: continuing to tune first60, OR15, volume, OI, R multiples, sleeve size, year, product, or direction would be overfitting.",
        "",
        "## Continue-Value Reflection",
        "",
        "- Before run: valuable, because route closure prevents hidden parameter rescue and clarifies remaining evidence gaps.",
        "- After run: the current minute-K route still has research value only as archived evidence and forensic labels. The next useful path is account-level survival or a stronger low-degree exogenous source, not another small intraday variant.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    route = _build_route_matrix()
    visual = _build_visual_index()
    scorecard = _build_scorecard(route, visual)

    route.to_csv(ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    visual.to_csv(VISUAL_INDEX_PATH, index=False, encoding="utf-8-sig")
    scorecard.to_csv(SCORECARD_PATH, index=False, encoding="utf-8-sig")
    _plot_summary(route, visual)

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_candidate": SOURCE_CANDIDATE,
        "decision": "stage891_intraday_route_closed_no_promotable_minute_rule_yet",
        "conclusion": (
            "Full-cycle minute data and K-line visual evidence are complete, C9 remains the only useful "
            "rule backbone, but Stage878-890 extensions do not produce a promotable rule after true-engine "
            "or route-level closure checks."
        ),
        "route_rows": len(route),
        "visual_rows": len(visual),
        "visual_png_pages": int(visual["png_pages"].sum()),
        "scorecard": scorecard.to_dict(orient="records"),
        "outputs": {
            "route_matrix": str(ROUTE_MATRIX_PATH),
            "scorecard": str(SCORECARD_PATH),
            "visual_index": str(VISUAL_INDEX_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "new_rule_created": False,
        },
    }
    _write_report(route, scorecard, visual, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
