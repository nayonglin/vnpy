from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve()
TOOL_DIR = SCRIPT_PATH.parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stage069_initial_entry_dual_anchor_price_basis_audit as s069


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage070"
MODEL_TAG = "stage070_initial_entry_price_proxy_anchor_batch_refill_v1"
OUTPUT_PREFIX = "qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill"

REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage070_initial_entry_price_proxy_anchor_batch_refill"
RAW_TICK_DIR = OUTPUT_DIR / "raw_tick"
STAGE069_RAW_TICK_DIR = (
    LINE_DIR / "outputs" / "stage069_initial_entry_dual_anchor_price_basis_audit" / "raw_tick" / "price_proxy_anchor"
)


def _configure_stage069_module() -> None:
    s069.STAGE = STAGE
    s069.MODEL_TAG = MODEL_TAG
    s069.OUTPUT_PREFIX = OUTPUT_PREFIX
    s069.OUTPUT_DIR = OUTPUT_DIR
    s069.RAW_TICK_DIR = RAW_TICK_DIR

    s069.DUAL_ANCHOR_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dual_anchor_plan_{MODEL_TAG}.csv"
    s069.DOWNLOAD_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
    s069.ANCHOR_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_price_features_{MODEL_TAG}.csv"
    s069.TRADE_COMPARISON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_anchor_comparison_{MODEL_TAG}.csv"
    s069.COVERAGE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
    s069.SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s069.DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    s069.REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s069.PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_price_basis_chart_{MODEL_TAG}.png"
    s069.SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scan_vs_proxy_delta_scatter_{MODEL_TAG}.png"
    s069.STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_status_chart_{MODEL_TAG}.png"
    s069.ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dual_anchor_tick_atlas_{MODEL_TAG}.png"

    s069.MAX_EVENTS = int(os.getenv("STAGE070_MAX_EVENTS", "60"))
    s069.MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE070_MAX_SECONDS_PER_EVENT", "45"))
    s069.TICK_DATA_LENGTH = int(os.getenv("STAGE070_TICK_DATA_LENGTH", "12000"))
    s069.DOWNLOAD_WINDOW_MINUTES = int(os.getenv("STAGE070_DOWNLOAD_WINDOW_MINUTES", "3"))
    s069.ENABLE_TQSDK = os.getenv("STAGE070_ENABLE_TQSDK", "1").strip() == "1"
    s069.DOWNLOAD_ROLES = {
        item.strip()
        for item in os.getenv("STAGE070_DOWNLOAD_ROLES", "price_proxy_anchor").split(",")
        if item.strip()
    }


def _reuse_stage069_proxy_ticks(plan: pd.DataFrame) -> pd.DataFrame:
    if not STAGE069_RAW_TICK_DIR.exists():
        return plan
    updated = plan.copy()
    for idx, row in updated[updated["anchor_role"].eq("price_proxy_anchor")].iterrows():
        if Path(str(row["tick_path"])).exists():
            continue
        trade_id = str(row["official_open_trade_id"]).replace(".", "_")
        matches = sorted(STAGE069_RAW_TICK_DIR.rglob(f"*{trade_id}_price_proxy_anchor_tick_backtest.csv"))
        if not matches:
            continue
        updated.at[idx, "tick_path"] = str(matches[0])
        updated.at[idx, "reuse_external_tick_path"] = False
    return updated


def _decision_for_stage070(
    plan: pd.DataFrame,
    anchor_features: pd.DataFrame,
    comparison: pd.DataFrame,
    coverage: pd.DataFrame,
    official_metrics: dict[str, object],
) -> dict[str, object]:
    decision = s069._build_decision(plan, anchor_features, comparison, coverage, official_metrics)
    proxy_rows = anchor_features[anchor_features["anchor_role"].eq("price_proxy_anchor")]
    scan_rows = anchor_features[anchor_features["anchor_role"].eq("event_scan_anchor")]
    proxy_ready = int(proxy_rows["anchor_ready"].sum()) if not proxy_rows.empty else 0
    proxy_exact = int(proxy_rows["price_exact_any"].sum()) if not proxy_rows.empty else 0
    scan_ready = int(scan_rows["anchor_ready"].sum()) if not scan_rows.empty else 0
    exact_ratio = float(proxy_exact / proxy_ready) if proxy_ready else 0.0
    if proxy_ready >= 20 and exact_ratio >= 0.95:
        stage_decision = "stage070_price_proxy_anchor_batch_exact_partial_coverage_no_rule"
        next_step = "continue_chronological_proxy_anchor_refill_then_full_basis_stability_audit"
    elif proxy_ready > 5:
        stage_decision = "stage070_price_proxy_anchor_batch_mixed_partial_coverage_no_rule"
        next_step = "inspect_proxy_anchor_mismatches_before_further_download_or_tca_features"
    else:
        stage_decision = "stage070_price_proxy_anchor_batch_refill_insufficient_progress_no_rule"
        next_step = "fix_download_or_credentials_then_retry_chronological_proxy_anchor_refill"
    decision.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "decision": stage_decision,
            "next_step": next_step,
            "stage070_batch_policy": "chronological_first_n_initial_entries_not_pnl_selected",
            "stage070_max_events": s069.MAX_EVENTS,
            "proxy_anchor_exact_ratio": exact_ratio,
            "scan_anchor_ready_count": scan_ready,
            "proxy_anchor_ready_count": proxy_ready,
            "proxy_price_exact_count": proxy_exact,
            "outputs": {
                "dual_anchor_plan": s069.DUAL_ANCHOR_PLAN_OUT,
                "download_status": s069.DOWNLOAD_STATUS_OUT,
                "anchor_features": s069.ANCHOR_FEATURES_OUT,
                "trade_comparison": s069.TRADE_COMPARISON_OUT,
                "coverage_summary": s069.COVERAGE_SUMMARY_OUT,
                "path_chart": s069.PATH_CHART_OUT,
                "scatter": s069.SCATTER_OUT,
                "status_chart": s069.STATUS_CHART_OUT,
                "atlas": s069.ATLAS_OUT,
            },
        }
    )
    return decision


def main() -> None:
    _configure_stage069_module()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    plan = s069._build_dual_anchor_plan()
    plan = _reuse_stage069_proxy_ticks(plan)
    s069._write_csv(plan, s069.DUAL_ANCHOR_PLAN_OUT)

    status = s069._download_or_check(plan)
    s069._write_csv(status, s069.DOWNLOAD_STATUS_OUT)

    anchor_features = s069._build_anchor_features(plan)
    s069._write_csv(anchor_features, s069.ANCHOR_FEATURES_OUT)

    comparison = s069._build_trade_comparison(anchor_features)
    coverage = s069._coverage_summary(anchor_features, comparison, status)
    s069._write_csv(comparison, s069.TRADE_COMPARISON_OUT)
    s069._write_csv(coverage, s069.COVERAGE_SUMMARY_OUT)

    official_metrics = s069._official_metrics()
    decision = _decision_for_stage070(plan, anchor_features, comparison, coverage, official_metrics)
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": s069.OFFICIAL_LIVE_VERSION,
        "official_live_alias": s069.OFFICIAL_LIVE_ALIAS,
        "decision": decision["decision"],
        "base_trade_count": decision["base_trade_count"],
        "anchor_plan_rows": decision["anchor_plan_rows"],
        "scan_anchor_ready_count": decision["scan_anchor_ready_count"],
        "proxy_anchor_ready_count": decision["proxy_anchor_ready_count"],
        "scan_price_exact_count": decision["scan_price_exact_count"],
        "proxy_price_exact_count": decision["proxy_price_exact_count"],
        "paired_ready_count": decision["paired_ready_count"],
        "proxy_improves_abs_delta_count": decision["proxy_improves_abs_delta_count"],
        "proxy_anchor_exact_ratio": decision["proxy_anchor_exact_ratio"],
        "stage070_max_events": s069.MAX_EVENTS,
        "end_equity": official_metrics.get("end_equity"),
        "total_return_pct": official_metrics.get("total_return_pct"),
        "max_drawdown_pct": official_metrics.get("max_drawdown_pct"),
        "sharpe": official_metrics.get("sharpe"),
        "total_slippage": official_metrics.get("total_slippage"),
        "total_trade_count": official_metrics.get("total_trade_count"),
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
    }
    s069._write_csv(pd.DataFrame([summary]), s069.SUMMARY_OUT)
    s069.DECISION_OUT.write_text(
        json.dumps(s069._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    s069._plot_path(comparison)
    s069._plot_scatter(comparison)
    s069._plot_status(anchor_features, status)
    s069._plot_atlas(anchor_features, comparison)
    s069._write_report(decision, coverage, comparison)
    print(json.dumps(s069._json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
