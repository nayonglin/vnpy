from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage099"
MODEL_TAG = "stage099_finer_source_feasibility_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(EXAMPLE_DIR), str(TOOLS_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from stage089_external_raw_backfill_manifest_probe import (  # noqa: E402
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _write_csv,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE098_DIR = LINE_DIR / "outputs" / "stage098_external_granularity_diagnostic"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage099_finer_source_feasibility_manifest"

STAGE098_SUMMARY_IN = (
    STAGE098_DIR
    / "qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_summary_"
    "stage098_external_granularity_diagnostic_v1.csv"
)
STAGE098_GATE_IN = (
    STAGE098_DIR
    / "qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_granularity_gate_"
    "stage098_external_granularity_diagnostic_v1.csv"
)

MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
PRIORITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_priority_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_CONTEXT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_context_chart_{MODEL_TAG}.png"
FEASIBILITY_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feasibility_heatmap_{MODEL_TAG}.png"
PRIORITY_QUADRANT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_priority_quadrant_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"


LEVEL_SCORE = {
    "none": 0.0,
    "unknown": 0.0,
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
}

INVERSE_RISK_SCORE = {
    "unknown": 1.0,
    "high": 1.0,
    "medium": 2.0,
    "low": 3.0,
}

ROUTE_COLORS = {
    "data_engineering": "#2563eb",
    "procurement_required": "#dc2626",
    "immediate_research": "#0f766e",
    "watch_only": "#64748b",
}


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _source_manifest() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "route_id": "member_category_seat_structure",
            "route_family": "external_position_structure",
            "first_principle_question": (
                "Is a trend entry supported by the right class of risk taker, not just by product-total volume?"
            ),
            "point_in_time_fields_required": (
                "trade_date, exchange, product, contract_month, member_or_seat_id, member_category, rank_type, "
                "volume, long_oi, short_oi, net_oi, publish_timestamp, raw_hash"
            ),
            "entry_time_visibility": "prior_session_or_exchange_publication_time_only",
            "current_repo_status": "current cache has product-total CZCE member rank only; category/seat coverage absent",
            "external_reference": (
                "CZCE member rank; SHFE daily ranking standard; CFTC COT category model as role-separation reference"
            ),
            "acquisition_path": "official historical files where public, otherwise authorized vendor such as member-rank API",
            "expected_granularity_gain": "high",
            "minute_k_alignment": "low",
            "coverage_expectation": "medium",
            "permission_cost_risk": "medium",
            "implementation_risk": "medium",
            "overfit_risk": "medium",
            "right_tail_gate": (
                "must show role/category state separates right-tail from bottom-loss across years without excluding "
                "known large winners"
            ),
            "priority_bucket": "data_engineering",
            "recommended_next_action": "build source inventory and permission check; no strategy feature before coverage audit",
        },
        {
            "route_id": "contract_month_oi_migration",
            "route_family": "contract_curve_structure",
            "first_principle_question": (
                "Is risk moving from nearby to deferred contracts in a way that changes trend persistence or squeeze risk?"
            ),
            "point_in_time_fields_required": (
                "trade_date, exchange, product, contract, delivery_month, open_interest, volume, dominant_rank, "
                "roll_distance_days, spread_to_near, publish_timestamp, raw_hash"
            ),
            "entry_time_visibility": "prior_session_exchange_daily_data",
            "current_repo_status": "product-total OI route failed earlier; contract-month migration table not yet bound here",
            "external_reference": "exchange daily contract OI files; AKShare futures wrappers; vendor continuous contract panels",
            "acquisition_path": "prefer official exchange daily contract data, with vendor fallback for historical completeness",
            "expected_granularity_gain": "medium",
            "minute_k_alignment": "low",
            "coverage_expectation": "high",
            "permission_cost_risk": "low",
            "implementation_risk": "medium",
            "overfit_risk": "medium",
            "right_tail_gate": (
                "must preserve dominant right-tail lots and avoid product/year/month rescue after migration labels are fixed"
            ),
            "priority_bucket": "data_engineering",
            "recommended_next_action": "only useful as data audit; do not revive product-total OI confirmation thresholds",
        },
        {
            "route_id": "inventory_basis_term_structure",
            "route_family": "physical_market_structure",
            "first_principle_question": (
                "Is the trend backed by physical tightness or looseness visible before entry, not by price path alone?"
            ),
            "point_in_time_fields_required": (
                "trade_date, product, exchange_inventory, warehouse_receipt, spot_price, near_future_price, "
                "deferred_future_price, basis, curve_slope, source_timestamp, raw_hash"
            ),
            "entry_time_visibility": "prior_session_publication_time_or_vendor_timestamp",
            "current_repo_status": "warehouse values are parsed for limited official sources; basis/spot/term link absent",
            "external_reference": "exchange warehouse receipt pages; commodity spot/basis vendor feeds; CME/CFTC OI notes as context",
            "acquisition_path": "combine official inventory files with licensed spot/basis panel; keep publication calendar explicit",
            "expected_granularity_gain": "medium",
            "minute_k_alignment": "low",
            "coverage_expectation": "medium",
            "permission_cost_risk": "medium",
            "implementation_risk": "high",
            "overfit_risk": "medium",
            "right_tail_gate": "must pass fixed product-family audit without basis/warehouse weight tuning",
            "priority_bucket": "data_engineering",
            "recommended_next_action": "manifest only until spot/basis timestamps and publication lags are verifiable",
        },
        {
            "route_id": "authorized_quote_depth_orderflow",
            "route_family": "microstructure",
            "first_principle_question": (
                "At the intended minute of entry, is liquidity accepting risk or merely printing noisy last trades?"
            ),
            "point_in_time_fields_required": (
                "event_timestamp, exchange_timestamp, contract, bid1, ask1, bid_size1, ask_size1, multi_level_depth, "
                "last_price, last_volume, aggressor_side, spread, queue_imbalance, raw_packet_hash"
            ),
            "entry_time_visibility": "same_minute_or_subminute_at_order_time",
            "current_repo_status": "local Tq tick/proxy routes were not rule-ready; authorized raw quote/depth is not present",
            "external_reference": "authorized exchange/vendor quote, depth and trade feeds",
            "acquisition_path": "requires licensed vendor or exchange raw tick/depth archive and storage budget",
            "expected_granularity_gain": "high",
            "minute_k_alignment": "high",
            "coverage_expectation": "unknown",
            "permission_cost_risk": "high",
            "implementation_risk": "high",
            "overfit_risk": "medium",
            "right_tail_gate": "must protect known right-tail entries before any queue/orderflow field becomes actionable",
            "priority_bucket": "procurement_required",
            "recommended_next_action": "do not block current research on procurement; keep as highest-value paid-data route",
        },
        {
            "route_id": "same_source_executable_minute_bars",
            "route_family": "execution_data",
            "first_principle_question": (
                "Can the exact executable minute stream used by the signal be replayed without proxy timestamps?"
            ),
            "point_in_time_fields_required": (
                "bar_datetime, trading_day, contract, open, high, low, close, volume, turnover, open_interest, "
                "source_session, executable_flag, raw_hash"
            ),
            "entry_time_visibility": "same_minute_or_next_tradable_minute",
            "current_repo_status": "Stage045 timestamp-ready subset is calibrated; fallback/no-proxy samples remain outside replay",
            "external_reference": "same vendor/source used by production signal generation or broker-side execution ledger",
            "acquisition_path": "recover production minute source or broker replay export; avoid mixing Stage861/Tq proxy semantics",
            "expected_granularity_gain": "medium",
            "minute_k_alignment": "high",
            "coverage_expectation": "medium",
            "permission_cost_risk": "medium",
            "implementation_risk": "medium",
            "overfit_risk": "low",
            "right_tail_gate": "must increase timestamp-ready coverage without changing official fallback sample behavior",
            "priority_bucket": "data_engineering",
            "recommended_next_action": "use only to enlarge replay-safe sample, not as ready/missing trade condition",
        },
        {
            "route_id": "stage045_timestamp_ready_replay_new_candidate",
            "route_family": "internal_minute_replay",
            "first_principle_question": (
                "Can a predeclared minute-level rule reduce early risk only when market proves executable acceptance?"
            ),
            "point_in_time_fields_required": (
                "existing Stage045 timestamp-ready replay fields, official C9 event semantics, entry minute bars, "
                "C2 stop/retry state, fallback/no-proxy flag"
            ),
            "entry_time_visibility": "only timestamp_ready=1 subset; fallback/no-proxy remains official path",
            "current_repo_status": "available now, but previous no-follow, hard-exit, min-risk and breakeven shapes are closed",
            "external_reference": "internal calibrated replay, not an external data route",
            "acquisition_path": "no new procurement; design a different first-principles preflight before true engine",
            "expected_granularity_gain": "low",
            "minute_k_alignment": "high",
            "coverage_expectation": "medium",
            "permission_cost_risk": "low",
            "implementation_risk": "low",
            "overfit_risk": "medium",
            "right_tail_gate": (
                "preflight visual atlas must show the rule would not cut OI309, jm2509, au2412, ru2501-like right tails"
            ),
            "priority_bucket": "immediate_research",
            "recommended_next_action": "next Stage100 should be read-only preflight for a new non-closed minute candidate",
        },
    ]
    manifest = pd.DataFrame(rows)
    manifest["direct_rule_allowed"] = 0
    manifest["true_engine_allowed"] = 0
    manifest["ab_allowed"] = 0
    manifest["order_api_allowed"] = 0
    manifest["ctp_connected"] = 0
    manifest["point_in_time_required"] = 1
    manifest["stage099_manifest_only"] = 1
    return manifest


def _priority_matrix(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in manifest.iterrows():
        data_ready_now = 3.0 if row["route_id"] == "stage045_timestamp_ready_replay_new_candidate" else 1.0
        if row["route_id"] == "same_source_executable_minute_bars":
            data_ready_now = 2.0
        point_in_time_feasible = 2.0
        if row["route_id"] == "authorized_quote_depth_orderflow":
            point_in_time_feasible = 1.0
        if row["route_id"] == "stage045_timestamp_ready_replay_new_candidate":
            point_in_time_feasible = 3.0
        rows.append(
            {
                "route_id": row["route_id"],
                "priority_bucket": row["priority_bucket"],
                "data_ready_now": data_ready_now,
                "point_in_time_feasible": point_in_time_feasible,
                "expected_granularity_gain": LEVEL_SCORE[str(row["expected_granularity_gain"])],
                "minute_k_alignment": LEVEL_SCORE[str(row["minute_k_alignment"])],
                "coverage_expectation": LEVEL_SCORE[str(row["coverage_expectation"])],
                "low_permission_friction": INVERSE_RISK_SCORE[str(row["permission_cost_risk"])],
                "low_implementation_friction": INVERSE_RISK_SCORE[str(row["implementation_risk"])],
                "low_overfit_risk": INVERSE_RISK_SCORE[str(row["overfit_risk"])],
            }
        )
    matrix = pd.DataFrame(rows)
    matrix["engineering_readiness_score_not_strategy_score"] = (
        matrix["data_ready_now"]
        + matrix["point_in_time_feasible"]
        + matrix["coverage_expectation"]
        + matrix["low_permission_friction"]
        + matrix["low_implementation_friction"]
        + matrix["low_overfit_risk"]
    )
    matrix["information_value_score_not_strategy_score"] = (
        matrix["expected_granularity_gain"] + matrix["minute_k_alignment"] + matrix["point_in_time_feasible"]
    )
    matrix["immediate_research_rank"] = matrix["engineering_readiness_score_not_strategy_score"].rank(
        ascending=False, method="first"
    )
    return matrix.sort_values("immediate_research_rank")


def _promotion_gate(manifest: pd.DataFrame, stage098_gate: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "stage098_product_total_route_closed",
            "evidence": "all Stage098 granularity gates failed rule promotion",
            "pass_for_rule_promotion": 0,
            "next_unlock_condition": "new finer point-in-time source or return to calibrated minute replay",
        },
        {
            "gate_id": "finer_source_manifest_has_no_rule",
            "evidence": f"{int(manifest['direct_rule_allowed'].sum())} direct-rule routes allowed",
            "pass_for_rule_promotion": 0,
            "next_unlock_condition": "complete raw coverage, timestamp, schema and right-tail visual gates",
        },
        {
            "gate_id": "true_engine_blocked",
            "evidence": f"{int(manifest['true_engine_allowed'].sum())} true-engine routes allowed",
            "pass_for_rule_promotion": 0,
            "next_unlock_condition": "predeclared candidate passes read-only visual atlas without right-tail damage",
        },
        {
            "gate_id": "ab_and_execution_blocked",
            "evidence": f"{int(manifest['ab_allowed'].sum())} A/B routes, {int(manifest['order_api_allowed'].sum())} order routes",
            "pass_for_rule_promotion": 0,
            "next_unlock_condition": "not applicable in Stage099",
        },
    ]
    gate = pd.DataFrame(rows)
    gate["stage098_failed_gate_count"] = 0
    if not stage098_gate.empty and "rule_allowed" in stage098_gate.columns:
        gate["stage098_failed_gate_count"] = int(pd.to_numeric(stage098_gate["rule_allowed"], errors="coerce").eq(0).sum())
    gate["manifest_only"] = 1
    return gate


def _summary(
    curve: pd.DataFrame,
    manifest: pd.DataFrame,
    matrix: pd.DataFrame,
    gate: pd.DataFrame,
    stage098_summary: pd.DataFrame,
) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    immediate = matrix.sort_values("immediate_research_rank").iloc[0]
    data_engineering_routes = int(manifest["priority_bucket"].eq("data_engineering").sum())
    procurement_routes = int(manifest["priority_bucket"].eq("procurement_required").sum())
    immediate_routes = int(manifest["priority_bucket"].eq("immediate_research").sum())
    prior_decision = ""
    if not stage098_summary.empty and "decision" in stage098_summary.columns:
        prior_decision = str(stage098_summary.iloc[0]["decision"])
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage099_finer_source_manifest_built_no_rule",
                "prior_stage_decision": prior_decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "route_count": int(len(manifest)),
                "data_engineering_route_count": data_engineering_routes,
                "procurement_required_route_count": procurement_routes,
                "immediate_research_route_count": immediate_routes,
                "direct_rule_allowed_count": int(manifest["direct_rule_allowed"].sum()),
                "true_engine_allowed_count": int(manifest["true_engine_allowed"].sum()),
                "ab_allowed_count": int(manifest["ab_allowed"].sum()),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_rule_promotion"], errors="coerce").sum()),
                "recommended_next_route": str(immediate["route_id"]),
                "recommended_next_action": str(
                    manifest.loc[manifest["route_id"].eq(immediate["route_id"]), "recommended_next_action"].iloc[0]
                ),
                "manifest_only": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_context(curve: pd.DataFrame, summary: pd.Series, matrix: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2.0, 1.0, 1.25]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.4)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.1)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)

    display = matrix.sort_values("immediate_research_rank").copy()
    colors = [ROUTE_COLORS.get(bucket, "#64748b") for bucket in display["priority_bucket"]]
    axes[2].barh(
        display["route_id"],
        display["engineering_readiness_score_not_strategy_score"],
        color=colors,
        alpha=0.86,
    )
    axes[2].invert_yaxis()
    axes[2].set_xlabel("engineering readiness, not a strategy score")
    axes[2].grid(True, axis="x", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} finer-source manifest | routes {int(summary['route_count'])} | rule_allowed=0 | true_engine=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_CONTEXT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_feasibility_heatmap(matrix: pd.DataFrame) -> None:
    columns = [
        "data_ready_now",
        "point_in_time_feasible",
        "expected_granularity_gain",
        "minute_k_alignment",
        "coverage_expectation",
        "low_permission_friction",
        "low_implementation_friction",
        "low_overfit_risk",
    ]
    display = matrix.sort_values("immediate_research_rank").set_index("route_id")
    values = display[columns].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13, 6))
    im = ax.imshow(values, aspect="auto", cmap="YlGnBu", vmin=0, vmax=3)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=30, ha="right")
    ax.set_yticks(range(len(display.index)))
    ax.set_yticklabels(display.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title("Stage099 source feasibility heatmap; categorical engineering scores only")
    fig.colorbar(im, ax=ax, label="0 low/unknown, 3 high")
    fig.tight_layout()
    fig.savefig(FEASIBILITY_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_priority_quadrant(matrix: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    for _, row in matrix.iterrows():
        friction = 6.0 - (row["low_permission_friction"] + row["low_implementation_friction"])
        info_value = row["information_value_score_not_strategy_score"]
        ax.scatter(
            friction,
            info_value,
            s=90 + 35 * row["expected_granularity_gain"],
            color=ROUTE_COLORS.get(str(row["priority_bucket"]), "#64748b"),
            alpha=0.82,
        )
        ax.text(friction + 0.05, info_value + 0.03, str(row["route_id"]), fontsize=8)
    ax.axvline(3.0, color="#94a3b8", linewidth=1, linestyle="--")
    ax.axhline(6.0, color="#94a3b8", linewidth=1, linestyle="--")
    ax.set_xlabel("acquisition and implementation friction")
    ax.set_ylabel("information value, not a strategy score")
    ax.set_title("Stage099 route priority: immediate replay vs paid/finer data routes")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PRIORITY_QUADRANT_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    x = np.arange(len(gate))
    passed = pd.to_numeric(gate["pass_for_rule_promotion"], errors="coerce").fillna(0)
    failed = 1 - passed
    ax.bar(x, failed, color="#dc2626", alpha=0.85, label="blocked")
    ax.bar(x, passed, bottom=failed, color="#0f766e", alpha=0.85, label="pass")
    ax.set_xticks(x)
    ax.set_xticklabels(gate["gate_id"], rotation=20, ha="right")
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("gate state")
    ax.set_title("Stage099 promotion gates: no route is rule-ready")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    manifest: pd.DataFrame,
    matrix: pd.DataFrame,
    gate: pd.DataFrame,
    stage098_gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} finer source feasibility manifest",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: source feasibility manifest only; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            f"- recommended next route: `{row['recommended_next_route']}`",
            f"- recommended next action: {row['recommended_next_action']}",
            "",
            "## Baseline path",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- win rate: `{row['win_rate_pct']:.4f}%`",
            "",
            "## Route Counts",
            "",
            f"- route count: `{int(row['route_count'])}`",
            f"- data engineering routes: `{int(row['data_engineering_route_count'])}`",
            f"- procurement required routes: `{int(row['procurement_required_route_count'])}`",
            f"- immediate research routes: `{int(row['immediate_research_route_count'])}`",
            f"- direct rule allowed count: `{int(row['direct_rule_allowed_count'])}`",
            f"- true engine allowed count: `{int(row['true_engine_allowed_count'])}`",
            f"- A/B allowed count: `{int(row['ab_allowed_count'])}`",
            "",
            "## Stage098 Gate Context",
            "",
            _md_table(stage098_gate, max_rows=20),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Source Manifest",
            "",
            _md_table(
                manifest[
                    [
                        "route_id",
                        "route_family",
                        "expected_granularity_gain",
                        "minute_k_alignment",
                        "coverage_expectation",
                        "permission_cost_risk",
                        "implementation_risk",
                        "overfit_risk",
                        "priority_bucket",
                        "direct_rule_allowed",
                        "true_engine_allowed",
                        "recommended_next_action",
                    ]
                ],
                max_rows=20,
            ),
            "",
            "## Priority Matrix",
            "",
            _md_table(matrix, max_rows=20),
            "",
            "## Visual outputs",
            "",
            f"- official context chart: `{OFFICIAL_CONTEXT_CHART_OUT}`",
            f"- feasibility heatmap: `{FEASIBILITY_HEATMAP_OUT}`",
            f"- priority quadrant: `{PRIORITY_QUADRANT_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The current product-total external route remains closed for direct rule use. "
                "Finer data can be useful only after raw coverage, point-in-time publication, schema and right-tail gates. "
                "Without new authorized data, the next practical research step is a read-only Stage100 preflight on the "
                "already calibrated timestamp-ready replay subset with a different first-principles minute candidate."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    stage098_summary = _read_csv(STAGE098_SUMMARY_IN, required=False)
    stage098_gate = _read_csv(STAGE098_GATE_IN, required=False)
    manifest = _source_manifest()
    matrix = _priority_matrix(manifest)
    gate = _promotion_gate(manifest, stage098_gate)
    summary = _summary(curve, manifest, matrix, gate, stage098_summary)

    _write_csv(manifest, MANIFEST_OUT)
    _write_csv(matrix, PRIORITY_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_official_context(curve, summary.iloc[0], matrix)
    _plot_feasibility_heatmap(matrix)
    _plot_priority_quadrant(matrix)
    _plot_gate(gate)
    _write_report(summary, manifest, matrix, gate, stage098_gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "recommended_next_route": str(summary.iloc[0]["recommended_next_route"]),
        "recommended_next_action": str(summary.iloc[0]["recommended_next_action"]),
        "manifest_path": str(MANIFEST_OUT),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "charts": [
            str(OFFICIAL_CONTEXT_CHART_OUT),
            str(FEASIBILITY_HEATMAP_OUT),
            str(PRIORITY_QUADRANT_OUT),
            str(PROMOTION_GATE_CHART_OUT),
        ],
        "direct_rule_allowed_count": int(summary.iloc[0]["direct_rule_allowed_count"]),
        "true_engine_allowed_count": int(summary.iloc[0]["true_engine_allowed_count"]),
        "ab_allowed_count": int(summary.iloc[0]["ab_allowed_count"]),
        "manifest_only": 1,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
