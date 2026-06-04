from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage588_p0_selector_evidence_priority_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage588_p0_selector_evidence_priority_audit"

STAGE582_TAG = "stage582_breadth_selector_operational_gate_v1"
STAGE582_PREFIX = "qmt_roll_stage582_breadth_selector_operational_gate"
STAGE561_TAG = "stage561_selector_predictive_audit_protocol_v1"
STAGE561_PREFIX = "qmt_roll_stage561_selector_predictive_audit_protocol"
STAGE571_TAG = "stage571_external_selector_source_priority_audit_v1"
STAGE571_PREFIX = "qmt_roll_stage571_external_selector_source_priority_audit"

WATCHLIST_PATH = OUTPUT_DIR / f"{STAGE582_PREFIX}_watchlist_{STAGE582_TAG}.csv"
ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{STAGE582_PREFIX}_route_matrix_{STAGE582_TAG}.csv"
STAGE582_GATES_PATH = OUTPUT_DIR / f"{STAGE582_PREFIX}_gates_{STAGE582_TAG}.csv"
STAGE561_GATES_PATH = OUTPUT_DIR / f"{STAGE561_PREFIX}_gates_{STAGE561_TAG}.csv"
STAGE571_SOURCE_PRIORITY_PATH = OUTPUT_DIR / f"{STAGE571_PREFIX}_source_priority_{STAGE571_TAG}.csv"
STAGE571_DATA_GAPS_PATH = OUTPUT_DIR / f"{STAGE571_PREFIX}_data_gaps_{STAGE571_TAG}.csv"

EVIDENCE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_matrix_{MODEL_TAG}.csv"
PRODUCT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_actions_{MODEL_TAG}.csv"
ROUTE_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_gaps_{MODEL_TAG}.csv"
FAMILY_TIEBREAK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_tiebreak_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_P0_PRODUCTS = 5
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_ROUTES_PER_P0 = 2
MAX_AVG_PAIRWISE_ABS_CORR = 0.20
MAX_PAIRWISE_ABS_CORR = 0.50
MAX_CORE_CORR_WATCH = 0.10


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _gate_value(gates: pd.DataFrame, gate: str, columns: list[str]) -> str:
    if gates.empty or "gate" not in gates.columns:
        return ""
    row = gates[gates["gate"].astype(str).eq(gate)]
    if row.empty:
        return ""
    for column in columns:
        if column in row.columns:
            return str(row.iloc[0].get(column, ""))
    return ""


def _parse_int(value: Any, default: int = 0) -> int:
    text = str(value)
    try:
        return int(float(text.split("/")[0].strip()))
    except (TypeError, ValueError):
        return default


def _source_action(product: str, route: str, family: str) -> str:
    if route == "basis" and product == "lu.INE":
        return "Add forward-only substitute: INE low-sulfur fuel oil spot-basis or bunker/fuel-oil spread route; no historical backfill."
    if route == "basis" and product == "ao.SHFE":
        return "Add forward-only alumina spot-basis route from a timestamped source; otherwise mark basis unavailable and do not penalize by backfill."
    if route == "sentiment_news_manual_event" and product == "v.DCE":
        return "Collect PVC/chlor-alkali operating-rate, policy, inventory, or industry-news event rows with received_at/source_url/raw_hash."
    if route == "sentiment_news_manual_event" and product == "lu.INE":
        return "Collect low-sulfur fuel oil/bunker/crude-crack/marine-fuel event rows with received_at/source_url/raw_hash."
    if route == "sentiment_news_manual_event" and product == "ao.SHFE":
        return "Collect alumina/bauxite/smelter/export-policy event rows with received_at/source_url/raw_hash."
    return f"Collect {route} route for {product} ({family}) with true received_at and raw hash."


def build_evidence() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    watch = _read_csv(WATCHLIST_PATH)
    route_matrix = _read_csv(ROUTE_MATRIX_PATH)
    stage561_gates = _read_csv(STAGE561_GATES_PATH)
    stage571_source = _read_csv(STAGE571_SOURCE_PRIORITY_PATH)
    stage571_gaps = _read_csv(STAGE571_DATA_GAPS_PATH)

    for column in [
        "basis_ready",
        "inventory_ready",
        "sentiment_news_manual_event_ready",
        "route_ready_count",
        "total_pnl",
        "abs_core_daily_pnl_corr",
        "max_abs_pairwise_corr_in_p0",
        "positive_year_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
    ]:
        watch[column] = _num(watch, column)

    family_counts = watch.groupby("product_family", dropna=False)["product_vt_symbol"].transform("count")
    watch["family_duplicate_count"] = family_counts.astype(int)
    watch["same_family_tiebreak_required"] = (watch["family_duplicate_count"] > 1).astype(int)
    watch["two_route_ready"] = watch["route_ready_count"].ge(MIN_ROUTES_PER_P0).astype(int)
    watch["event_ready"] = watch["sentiment_news_manual_event_ready"].ge(1).astype(int)
    watch["core_corr_watch_flag"] = watch["abs_core_daily_pnl_corr"].gt(MAX_CORE_CORR_WATCH).astype(int)
    watch["evidence_score_0_100"] = (
        watch["basis_ready"].clip(0, 1) * 25.0
        + watch["inventory_ready"].clip(0, 1) * 25.0
        + watch["event_ready"] * 25.0
        + watch["two_route_ready"] * 15.0
        + (1 - watch["same_family_tiebreak_required"]) * 5.0
        + (1 - watch["core_corr_watch_flag"]) * 5.0
    )

    def role(row: pd.Series) -> str:
        if row["route_ready_count"] >= 3 and row["same_family_tiebreak_required"]:
            return "complete_routes_but_family_tiebreak_required"
        if row["route_ready_count"] >= 3:
            return "complete_routes_forward_label_collection"
        if row["route_ready_count"] >= 2:
            return "minimum_routes_missing_event_coverage"
        return "source_gap_first"

    def primary_gap(row: pd.Series) -> str:
        gaps: list[str] = []
        if row["basis_ready"] < 1:
            gaps.append("basis_or_substitute_route")
        if row["inventory_ready"] < 1:
            gaps.append("inventory")
        if row["event_ready"] < 1:
            gaps.append("sentiment_news_manual_event")
        if row["same_family_tiebreak_required"]:
            gaps.append("same_family_tiebreak")
        if row["core_corr_watch_flag"]:
            gaps.append("core_corr_watch")
        return ",".join(gaps) if gaps else "forward_sample_depth_only"

    watch["current_selector_role"] = watch.apply(role, axis=1)
    watch["primary_gap"] = watch.apply(primary_gap, axis=1)
    watch["promotion_allowed"] = 0
    watch["paper_selector_audit_allowed"] = 0
    watch["trading_whitelist_allowed"] = 0

    evidence_columns = [
        "product_vt_symbol",
        "product_family",
        "total_pnl",
        "positive_year_rate_pct",
        "abs_core_daily_pnl_corr",
        "max_abs_pairwise_corr_in_p0",
        "basis_ready",
        "inventory_ready",
        "sentiment_news_manual_event_ready",
        "route_ready_count",
        "two_route_ready",
        "event_ready",
        "same_family_tiebreak_required",
        "core_corr_watch_flag",
        "evidence_score_0_100",
        "current_selector_role",
        "primary_gap",
        "promotion_allowed",
        "paper_selector_audit_allowed",
        "trading_whitelist_allowed",
    ]
    evidence = watch[evidence_columns].sort_values(["evidence_score_0_100", "total_pnl"], ascending=[False, False])

    product_actions = evidence[
        [
            "product_vt_symbol",
            "product_family",
            "current_selector_role",
            "primary_gap",
            "evidence_score_0_100",
            "total_pnl",
            "abs_core_daily_pnl_corr",
        ]
    ].copy()
    product_actions["next_action"] = product_actions.apply(
        lambda row: (
            "Freeze y/c same-family tie-break before any paper sleeve."
            if "same_family_tiebreak" in str(row["primary_gap"])
            else (
                "Collect missing route rows first; do not run selector PnL replay."
                if "basis_or_substitute_route" in str(row["primary_gap"])
                or "sentiment_news_manual_event" in str(row["primary_gap"])
                else "Only accumulate forward labels until 20/20 sample-depth gate passes."
            )
        ),
        axis=1,
    )

    route_gap_rows: list[dict[str, Any]] = []
    for _, row in evidence.iterrows():
        product = str(row["product_vt_symbol"])
        family = str(row["product_family"])
        route_status = {
            "basis": int(row["basis_ready"]),
            "inventory": int(row["inventory_ready"]),
            "sentiment_news_manual_event": int(row["sentiment_news_manual_event_ready"]),
        }
        for route, ready in route_status.items():
            if ready:
                continue
            route_gap_rows.append(
                {
                    "product_vt_symbol": product,
                    "product_family": family,
                    "missing_route": route,
                    "blocks_min_two_route_gate": int(route != "sentiment_news_manual_event" and row["route_ready_count"] < 2),
                    "blocks_event_coverage_gate": int(route == "sentiment_news_manual_event"),
                    "recommended_action": _source_action(product, route, family),
                }
            )
    route_gaps = pd.DataFrame(route_gap_rows)

    family_rows: list[dict[str, Any]] = []
    for family, group in evidence.groupby("product_family", dropna=False):
        products = sorted(group["product_vt_symbol"].astype(str).tolist())
        need_tiebreak = len(products) > 1
        family_rows.append(
            {
                "product_family": family,
                "p0_products": ",".join(products),
                "p0_count": len(products),
                "same_family_tiebreak_required": int(need_tiebreak),
                "predeclared_rule_required": (
                    "Until PIT selector score exists, do not let more than one same-family same-direction P0 consume full sleeve risk."
                    if need_tiebreak
                    else ""
                ),
            }
        )
    family_tiebreak = pd.DataFrame(family_rows).sort_values(["same_family_tiebreak_required", "p0_count"], ascending=False)

    forward_runs = _parse_int(_gate_value(stage561_gates, "forward_runs_ready", ["current", "actual", "value"]))
    forward_dates = _parse_int(_gate_value(stage561_gates, "forward_dates_ready", ["current", "actual", "value"]))
    avg_pair_corr = float(evidence["max_abs_pairwise_corr_in_p0"].replace(0, np.nan).dropna().mean() or 0.0)
    max_pair_corr = float(evidence["max_abs_pairwise_corr_in_p0"].max() or 0.0)
    products_two_routes = int(evidence["two_route_ready"].sum())
    products_event = int(evidence["event_ready"].sum())
    tiebreak_families = int(family_tiebreak["same_family_tiebreak_required"].sum()) if not family_tiebreak.empty else 0

    gate_rows = [
        {
            "gate": "p0_pool_exists",
            "passed": int(len(evidence) >= MIN_P0_PRODUCTS),
            "actual": str(len(evidence)),
            "required": str(MIN_P0_PRODUCTS),
            "severity": "hard",
            "reason": "P0 low-correlation material pool must exist before selector collection.",
        },
        {
            "gate": "pairwise_corr_not_crowded",
            "passed": int(avg_pair_corr <= MAX_AVG_PAIRWISE_ABS_CORR and max_pair_corr <= MAX_PAIRWISE_ABS_CORR),
            "actual": f"avg_product_max={avg_pair_corr:.4f}, max={max_pair_corr:.4f}",
            "required": f"avg<={MAX_AVG_PAIRWISE_ABS_CORR}, max<={MAX_PAIRWISE_ABS_CORR}",
            "severity": "hard",
            "reason": "P0 pool should not be hidden high-correlation concentration.",
        },
        {
            "gate": "each_p0_has_two_external_routes",
            "passed": int(products_two_routes == len(evidence)),
            "actual": f"{products_two_routes}/{len(evidence)}",
            "required": f"{len(evidence)}/{len(evidence)}",
            "severity": "hard",
            "reason": "Every product needs at least two point-in-time external routes before selector audit.",
        },
        {
            "gate": "each_p0_has_real_event_coverage",
            "passed": int(products_event == len(evidence)),
            "actual": f"{products_event}/{len(evidence)}",
            "required": f"{len(evidence)}/{len(evidence)}",
            "severity": "soft",
            "reason": "Sentiment/event route cannot be inferred from templates or hindsight stories.",
        },
        {
            "gate": "same_family_tiebreak_frozen",
            "passed": int(tiebreak_families == 0),
            "actual": str(tiebreak_families),
            "required": "0",
            "severity": "hard",
            "reason": "Same-family P0 products need a predeclared tie-break before any sleeve replay.",
        },
        {
            "gate": "forward_runs_ready",
            "passed": int(forward_runs >= MIN_FORWARD_RUNS),
            "actual": str(forward_runs),
            "required": str(MIN_FORWARD_RUNS),
            "severity": "hard",
            "reason": "Selector IC audit needs enough distinct forward runs.",
        },
        {
            "gate": "forward_dates_ready",
            "passed": int(forward_dates >= MIN_FORWARD_DATES),
            "actual": str(forward_dates),
            "required": str(MIN_FORWARD_DATES),
            "severity": "hard",
            "reason": "Same-day reruns cannot inflate sample depth.",
        },
        {
            "gate": "history_backfill_disabled",
            "passed": 1,
            "actual": "disabled",
            "required": "disabled",
            "severity": "hard",
            "reason": "Forward snapshots must not be reclassified into 2020-2026 historical selector data.",
        },
    ]
    gates = pd.DataFrame(gate_rows)
    hard_passed = int(gates[gates["severity"].eq("hard")]["passed"].sum())
    hard_total = int((gates["severity"] == "hard").sum())
    promotion_allowed = bool(hard_passed == hard_total and products_event == len(evidence))

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "decision": "p0_selector_evidence_priority_not_ready",
        "promotion_allowed": promotion_allowed,
        "paper_selector_audit_allowed": False,
        "trading_whitelist_allowed": False,
        "p0_products": int(len(evidence)),
        "products_with_two_or_more_routes": products_two_routes,
        "products_with_real_event_coverage": products_event,
        "route_gap_rows": int(len(route_gaps)),
        "same_family_tiebreak_families": tiebreak_families,
        "forward_runs": forward_runs,
        "forward_dates": forward_dates,
        "gates_passed": int(gates["passed"].sum()),
        "gates_total": int(len(gates)),
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "source_priority_rows": int(len(stage571_source)),
        "data_gap_rows": int(len(stage571_gaps)),
        "next_actions": [
            "Collect v.DCE, lu.INE, ao.SHFE real event/news/manual-event ledgers with received_at/source_url/raw_hash.",
            "Add forward-only basis or substitute route for lu.INE and ao.SHFE; do not backfill history.",
            "Freeze y.DCE/c.DCE same-family tie-break before any future paper sleeve.",
            "Continue distinct-date forward collection until Stage561 reaches 20 runs / 20 dates.",
        ],
    }
    return evidence, product_actions, route_gaps, family_tiebreak, gates, decision


def write_outputs(
    evidence: pd.DataFrame,
    product_actions: pd.DataFrame,
    route_gaps: pd.DataFrame,
    family_tiebreak: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    evidence.to_csv(EVIDENCE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    product_actions.to_csv(PRODUCT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    route_gaps.to_csv(ROUTE_GAPS_PATH, index=False, encoding="utf-8-sig")
    family_tiebreak.to_csv(FAMILY_TIEBREAK_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ordered = evidence.sort_values("evidence_score_0_100", ascending=True)
    y = np.arange(len(ordered))
    axes[0, 0].barh(y, ordered["basis_ready"], label="basis", color="#2f80ed")
    axes[0, 0].barh(y, ordered["inventory_ready"], left=ordered["basis_ready"], label="inventory", color="#27ae60")
    axes[0, 0].barh(
        y,
        ordered["sentiment_news_manual_event_ready"],
        left=ordered["basis_ready"] + ordered["inventory_ready"],
        label="event",
        color="#f2994a",
    )
    axes[0, 0].set_yticks(y)
    axes[0, 0].set_yticklabels(ordered["product_vt_symbol"])
    axes[0, 0].set_xlim(0, 3)
    axes[0, 0].set_title("P0 point-in-time route readiness")
    axes[0, 0].legend(loc="lower right")

    scatter = axes[0, 1].scatter(
        evidence["abs_core_daily_pnl_corr"],
        evidence["total_pnl"],
        s=120 + evidence["route_ready_count"] * 90,
        c=evidence["evidence_score_0_100"],
        cmap="viridis",
        edgecolor="#222222",
    )
    for _, row in evidence.iterrows():
        axes[0, 1].annotate(row["product_vt_symbol"], (row["abs_core_daily_pnl_corr"], row["total_pnl"]), fontsize=9)
    axes[0, 1].axvline(MAX_CORE_CORR_WATCH, color="#b00020", linestyle="--", linewidth=1)
    x_max = max(float(evidence["abs_core_daily_pnl_corr"].max()) * 1.12, MAX_CORE_CORR_WATCH * 1.25)
    y_max = float(evidence["total_pnl"].max()) * 1.08
    y_min = min(float(evidence["total_pnl"].min()) * 0.90, 0.0)
    axes[0, 1].set_xlim(0, x_max)
    axes[0, 1].set_ylim(y_min, y_max)
    axes[0, 1].set_title("Opportunity vs core correlation")
    axes[0, 1].set_xlabel("abs core daily pnl corr")
    axes[0, 1].set_ylabel("historical noncore product pnl")
    fig.colorbar(scatter, ax=axes[0, 1], label="evidence score")

    route_counts = pd.DataFrame(
        {
            "route": ["basis", "inventory", "event"],
            "ready_products": [
                int(evidence["basis_ready"].sum()),
                int(evidence["inventory_ready"].sum()),
                int(evidence["sentiment_news_manual_event_ready"].sum()),
            ],
            "required_products": [len(evidence), len(evidence), len(evidence)],
        }
    )
    x = np.arange(len(route_counts))
    axes[1, 0].bar(x - 0.18, route_counts["ready_products"], width=0.36, label="ready", color="#27ae60")
    axes[1, 0].bar(x + 0.18, route_counts["required_products"], width=0.36, label="required", color="#bdbdbd")
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(route_counts["route"])
    axes[1, 0].set_ylim(0, max(len(evidence), 1) + 1)
    axes[1, 0].set_title("Route coverage gap")
    axes[1, 0].legend()

    gate_plot = gates.copy()
    gate_plot["plot_value"] = np.where(gate_plot["passed"].astype(int).eq(1), 1, -1)
    colors = np.where(gate_plot["passed"].astype(int).eq(1), "#27ae60", "#c0392b")
    axes[1, 1].barh(np.arange(len(gate_plot)), gate_plot["plot_value"], color=colors)
    axes[1, 1].set_yticks(np.arange(len(gate_plot)))
    axes[1, 1].set_yticklabels(gate_plot["gate"], fontsize=8)
    axes[1, 1].axvline(0, color="#333333", linewidth=1)
    axes[1, 1].set_xlim(-1.05, 1.05)
    axes[1, 1].set_title("Promotion gates")
    axes[1, 1].set_xlabel("fail=-1, pass=1")

    fig.suptitle("Stage588 P0 selector evidence priority audit", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)

    report = f"""# Stage588 P0 selector evidence priority audit

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- created_at: `{decision['created_at']}`
- decision: `{decision['decision']}`
- promotion_allowed: `{decision['promotion_allowed']}`
- paper_selector_audit_allowed: `{decision['paper_selector_audit_allowed']}`
- trading_whitelist_allowed: `{decision['trading_whitelist_allowed']}`

## Summary

This is a read-only evidence audit for the low-single-risk breadth selector route. It does not change Stage526/Stage079, does not run a PnL replay, and does not create a trade whitelist.

Key result: P0 products exist and are not correlation-crowded, but the selector is still not ready. Current proof is insufficient because only `{decision['products_with_two_or_more_routes']}/{decision['p0_products']}` P0 products have at least two point-in-time external routes, only `{decision['products_with_real_event_coverage']}/{decision['p0_products']}` have real event/news coverage, same-family tie-break is not frozen, and forward sample depth is `{decision['forward_runs']}/{MIN_FORWARD_RUNS}` runs and `{decision['forward_dates']}/{MIN_FORWARD_DATES}` dates.

## Evidence Matrix

{_md_table(evidence, max_rows=10)}

## Product Actions

{_md_table(product_actions, max_rows=10)}

## Route Gaps

{_md_table(route_gaps, max_rows=20)}

## Family Tie-Break

{_md_table(family_tiebreak, max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Next Actions

1. Collect `v.DCE`, `lu.INE`, `ao.SHFE` real event/news/manual-event rows with `received_at`, `source_url`, and `raw_hash`.
2. Add forward-only basis or substitute routes for `lu.INE` and `ao.SHFE`; never backfill them into historical selector tests.
3. Freeze the `y.DCE` / `c.DCE` same-family tie-break before any future paper sleeve.
4. Continue distinct-date forward collection until Stage561 reaches `20` runs / `20` dates, then run the already frozen IC/bucket protocol once.

## Output Files

- evidence_matrix: `{EVIDENCE_MATRIX_PATH}`
- product_actions: `{PRODUCT_ACTIONS_PATH}`
- route_gaps: `{ROUTE_GAPS_PATH}`
- family_tiebreak: `{FAMILY_TIEBREAK_PATH}`
- gates: `{GATES_PATH}`
- decision: `{DECISION_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence, product_actions, route_gaps, family_tiebreak, gates, decision = build_evidence()
    write_outputs(evidence, product_actions, route_gaps, family_tiebreak, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
