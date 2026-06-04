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


MODEL_TAG = "stage571_external_selector_source_priority_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage571_external_selector_source_priority_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE547_TAG = "stage547_noncore_basis_monthly_selector_diagnostic_v1"
STAGE547_PREFIX = "qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic"
STAGE558_TAG = "stage558_external_state_selector_readiness_audit_v1"
STAGE558_PREFIX = "qmt_roll_stage558_external_state_selector_readiness_audit"
STAGE560_TAG = "stage560_forward_collection_run_gate_v1"
STAGE560_PREFIX = "qmt_roll_stage560_forward_collection_run_gate"
STAGE561_TAG = "stage561_selector_predictive_audit_protocol_v1"
STAGE561_PREFIX = "qmt_roll_stage561_selector_predictive_audit_protocol"
STAGE550_TAG = "stage550_product_opportunity_geometry_audit_v1"
STAGE550_PREFIX = "qmt_roll_stage550_product_opportunity_geometry_audit"

STAGE547_SUMMARY = OUTPUT_DIR / f"{STAGE547_PREFIX}_summary_{STAGE547_TAG}.csv"
STAGE558_ROUTE = OUTPUT_DIR / f"{STAGE558_PREFIX}_route_readiness_{STAGE558_TAG}.csv"
STAGE558_GATES = OUTPUT_DIR / f"{STAGE558_PREFIX}_readiness_gates_{STAGE558_TAG}.csv"
STAGE558_SENTIMENT = OUTPUT_DIR / f"{STAGE558_PREFIX}_sentiment_ledger_inventory_{STAGE558_TAG}.csv"
STAGE560_RUN_QUALITY = OUTPUT_DIR / f"{STAGE560_PREFIX}_run_quality_{STAGE560_TAG}.csv"
STAGE560_COLLECTION_GATE = OUTPUT_DIR / f"{STAGE560_PREFIX}_collection_gate_{STAGE560_TAG}.csv"
STAGE560_ROUTE_HEALTH = OUTPUT_DIR / f"{STAGE560_PREFIX}_route_latest_health_{STAGE560_TAG}.csv"
STAGE561_GATES = OUTPUT_DIR / f"{STAGE561_PREFIX}_gates_{STAGE561_TAG}.csv"
STAGE561_FEATURE_SPEC = OUTPUT_DIR / f"{STAGE561_PREFIX}_feature_spec_{STAGE561_TAG}.csv"
STAGE561_TEST_PLAN = OUTPUT_DIR / f"{STAGE561_PREFIX}_test_plan_{STAGE561_TAG}.csv"
STAGE550_FEATURE_IC = OUTPUT_DIR / f"{STAGE550_PREFIX}_feature_ic_{STAGE550_TAG}.csv"

SOURCE_PRIORITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_priority_{MODEL_TAG}.csv"
DATA_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_gaps_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
FEATURE_PRIOR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_prior_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_SENTIMENT_LEDGERS = 1
MIN_FORWARD_PRODUCTS = 20


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


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
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _gate_lookup(gates: pd.DataFrame, gate: str, current_col: str = "current") -> str:
    row = gates[gates["gate"].astype(str).eq(gate)]
    if row.empty:
        return ""
    col = current_col if current_col in row.columns else "value"
    return str(row.iloc[0].get(col, ""))


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(float(str(value).split("/")[0].strip()))
    except (TypeError, ValueError):
        return default


def _sentiment_ledger_stats(sentiment: pd.DataFrame) -> dict[str, Any]:
    candidate = sentiment[_num(sentiment, "is_candidate_ledger").ge(1)].copy() if not sentiment.empty else pd.DataFrame()
    rows = int(_num(candidate, "rows").sum()) if not candidate.empty else 0
    products: set[str] = set()
    received_dates: set[str] = set()
    for path_text in candidate.get("path", pd.Series(dtype=str)).astype(str):
        path = Path(path_text)
        if not path.is_absolute():
            repo_relative = PROJECT_DIR.parent.parent / path
            path = repo_relative if repo_relative.exists() else PROJECT_DIR / path
        if not path.exists():
            continue
        try:
            ledger = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if "product_vt_symbol" in ledger.columns:
            products.update(str(item) for item in ledger["product_vt_symbol"].dropna().unique())
        if "received_at_local" in ledger.columns:
            dates = pd.to_datetime(ledger["received_at_local"], errors="coerce").dropna()
            received_dates.update(date.date().isoformat() for date in dates)
    return {
        "candidate_ledgers": int(len(candidate)),
        "rows": rows,
        "mapped_products": int(len(products)),
        "received_dates": int(len(received_dates)),
    }


def _best_basis_diagnostic() -> dict[str, Any]:
    if not STAGE547_SUMMARY.exists():
        return {
            "best_basis_mode": "",
            "basis_best_edge": 0.0,
            "basis_best_positive_rate_pct": 0.0,
            "basis_oracle_capture_pct": 0.0,
            "basis_diagnostic_pass": 0,
        }
    summary = _read_csv(STAGE547_SUMMARY)
    # Prefer the stricter quarterly-purged rows if the column exists.
    frame = summary.copy()
    if "sample_type" in frame.columns and frame["sample_type"].astype(str).eq("quarterly_purged").any():
        frame = frame[frame["sample_type"].astype(str).eq("quarterly_purged")].copy()
    edge_col = "avg_edge_vs_all_future60"
    if edge_col not in frame.columns:
        edge_col = "edge_vs_all_future60" if "edge_vs_all_future60" in frame.columns else ""
    if not edge_col:
        return {
            "best_basis_mode": "",
            "basis_best_edge": 0.0,
            "basis_best_positive_rate_pct": 0.0,
            "basis_oracle_capture_pct": 0.0,
            "basis_diagnostic_pass": 0,
        }
    frame[edge_col] = _num(frame, edge_col)
    best = frame.sort_values(edge_col, ascending=False).iloc[0]
    positive_rate = best.get(
        "future60_positive_month_rate_pct",
        best.get("positive_month_rate_future60_pct", best.get("positive_rate_pct", 0.0)),
    )
    oracle_capture = best.get(
        "oracle_capture_pct",
        best.get("oracle6_capture_pct", best.get("selected_vs_oracle_capture_ratio_60d", 0.0)),
    )
    positive_rate = float(positive_rate or 0.0)
    oracle_capture = float(oracle_capture or 0.0)
    if abs(oracle_capture) <= 1.0:
        oracle_capture *= 100.0
    return {
        "best_basis_mode": str(best.get("mode", best.get("selector", ""))),
        "basis_best_edge": float(best.get(edge_col, 0.0)),
        "basis_best_positive_rate_pct": positive_rate,
        "basis_oracle_capture_pct": oracle_capture,
        "basis_diagnostic_pass": int(float(best.get("diagnostic_pass", 0) or 0)),
    }


def build_feature_prior() -> pd.DataFrame:
    feature = _read_csv(STAGE550_FEATURE_IC)
    feature = feature[feature["horizon_days"].eq(60)].copy() if "horizon_days" in feature.columns else feature.copy()
    for col in ["mean_spearman_ic", "positive_ic_rate_pct", "t_like"]:
        feature[col] = _num(feature, col)
    feature["strength"] = np.select(
        [
            feature["mean_spearman_ic"].ge(0.15),
            feature["mean_spearman_ic"].ge(0.10),
            feature["mean_spearman_ic"].ge(0.05),
        ],
        ["strong_prior", "weak_positive_prior", "monitor_only"],
        default="insufficient",
    )
    feature["allowed_as_alpha_now"] = 0
    feature["reason"] = "existing historical prior only; Stage543/544 did not produce deployable selector"
    return feature.sort_values("mean_spearman_ic", ascending=False)


def build_source_priority() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    route = _read_csv(STAGE560_ROUTE_HEALTH)
    protocol_gates = _read_csv(STAGE561_GATES)
    collection_gates = _read_csv(STAGE560_COLLECTION_GATE)
    sentiment = _read_csv(STAGE558_SENTIMENT)
    basis_diag = _best_basis_diagnostic()

    qualified_runs = _parse_int(_gate_lookup(protocol_gates, "forward_runs_ready"))
    qualified_dates = _parse_int(_gate_lookup(protocol_gates, "forward_dates_ready"))
    sentiment_stats = _sentiment_ledger_stats(sentiment)
    sentiment_ledgers = int(sentiment_stats["candidate_ledgers"])

    source_rows: list[dict[str, Any]] = []
    for route_name in ["basis", "inventory", "member_detail", "warehouse"]:
        r = route[route["route"].astype(str).eq(route_name)]
        if r.empty:
            latest_forward = 0
            history_ready = 0
            raw_hash_ok_rate = 0.0
        else:
            latest_forward = int(r.iloc[0].get("latest_forward_ready_products", r.iloc[0].get("forward_ready_products", 0)))
            history_ready = int(r.iloc[0].get("latest_history_ready_products", r.iloc[0].get("history_ready_products", 0)))
            raw_hash_ok_rate = float(r.iloc[0].get("raw_hash_ok_rate", 0.0) or 0.0)

        if route_name == "basis":
            action = "continue_forward_collection_monitor_only"
            role = "candidate_feature_after_20_date_gate"
            standalone_status = "historical_basis_selector_failed"
            predictive_note = (
                f"best monthly basis edge={basis_diag['basis_best_edge']:.4f}, "
                f"positive_rate={basis_diag['basis_best_positive_rate_pct']:.4f}%, "
                f"oracle_capture={basis_diag['basis_oracle_capture_pct']:.4f}%"
            )
        elif route_name == "inventory":
            action = "continue_forward_collection_then_joint_test_with_basis"
            role = "candidate_feature_after_20_date_gate"
            standalone_status = "no_standalone_predictive_audit_yet"
            predictive_note = "coverage usable but not enough forward observations; no history selector backfill"
        elif route_name in {"member_detail", "warehouse"}:
            action = "deprioritize_until_source_recovers"
            role = "blocked_source"
            standalone_status = "no_forward_coverage"
            predictive_note = "0 forward-ready products; cannot be hard dependency"
        else:
            action = "unknown"
            role = "unknown"
            standalone_status = "unknown"
            predictive_note = ""

        coverage_score = min(latest_forward / MIN_FORWARD_PRODUCTS, 1.0) * 40.0
        sample_score = min(qualified_dates / MIN_FORWARD_DATES, 1.0) * 20.0
        history_penalty = -15.0 if history_ready == 0 else 0.0
        source_health = raw_hash_ok_rate * 10.0
        standalone_penalty = -10.0 if "failed" in standalone_status or "no_standalone" in standalone_status else 0.0
        priority_score = max(0.0, coverage_score + sample_score + source_health + history_penalty + standalone_penalty)

        source_rows.append(
            {
                "source_route": route_name,
                "role": role,
                "latest_forward_ready_products": latest_forward,
                "history_ready_products": history_ready,
                "qualified_forward_runs": qualified_runs,
                "qualified_forward_dates": qualified_dates,
                "raw_hash_ok_rate": raw_hash_ok_rate,
                "standalone_predictive_status": standalone_status,
                "priority_score": priority_score,
                "recommended_action": action,
                "predictive_note": predictive_note,
            }
        )

    source_rows.append(
        {
            "source_route": "sentiment_news_manual_event",
            "role": "forward_monitor_started_not_alpha",
            "latest_forward_ready_products": int(sentiment_stats["mapped_products"]),
            "history_ready_products": 0,
            "qualified_forward_runs": qualified_runs,
            "qualified_forward_dates": qualified_dates,
            "raw_hash_ok_rate": float(sentiment_ledgers >= 1),
            "standalone_predictive_status": (
                "real_received_at_ledger_started_forward_monitor_only"
                if sentiment_ledgers >= 1
                else "missing_real_received_at_ledger"
            ),
            "priority_score": 12.0 if sentiment_ledgers >= 1 else 0.0,
            "recommended_action": (
                "continue_forward_event_collection_until_20_date_gate"
                if sentiment_ledgers >= 1
                else "create_real_event_ledger_before_any_sentiment_backtest"
            ),
            "predictive_note": (
                f"candidate_ledgers={sentiment_ledgers}, rows={sentiment_stats['rows']}, "
                f"mapped_products={sentiment_stats['mapped_products']}, dates={sentiment_stats['received_dates']}; "
                "usable for forward monitor only until sample-depth and label-maturity gates pass"
            ),
        }
    )
    source_rows.append(
        {
            "source_route": "market_state_guardrail",
            "role": "risk_guardrail_not_alpha",
            "latest_forward_ready_products": 37,
            "history_ready_products": 37,
            "qualified_forward_runs": qualified_runs,
            "qualified_forward_dates": qualified_dates,
            "raw_hash_ok_rate": 1.0,
            "standalone_predictive_status": "weak_prior_not_deployable_selector",
            "priority_score": 35.0,
            "recommended_action": "use_as_guardrail_or_feature_prior_only",
            "predictive_note": "hist_drawdown_120d / core_corr have weak IC, but Stage543/544 did not pass",
        }
    )
    source_rows.append(
        {
            "source_route": "stage256_upper_bound",
            "role": "evaluation_upper_bound_not_feature",
            "latest_forward_ready_products": 0,
            "history_ready_products": 0,
            "qualified_forward_runs": qualified_runs,
            "qualified_forward_dates": qualified_dates,
            "raw_hash_ok_rate": 0.0,
            "standalone_predictive_status": "hindsight_or_historical_whitelist_not_deployable",
            "priority_score": 0.0,
            "recommended_action": "use_only_as_target_gap_for_selector_research",
            "predictive_note": "Stage271 showed small holding-experience improvement but deployability gate fails",
        }
    )

    priority = pd.DataFrame(source_rows).sort_values("priority_score", ascending=False)

    gap_rows = [
        {
            "gap": "qualified_forward_sample_depth",
            "current": f"{qualified_runs} runs / {qualified_dates} dates",
            "required": f"{MIN_FORWARD_RUNS} runs / {MIN_FORWARD_DATES} dates",
            "action": "collect distinct-date Stage549 snapshots; same-day reruns cannot count",
            "blocks_predictive_audit": 1,
        },
        {
            "gap": "sentiment_news_real_ledger",
            "current": (
                f"{sentiment_ledgers} candidate ledgers / "
                f"{sentiment_stats['mapped_products']} mapped products"
            ),
            "required": ">=1 real ledger",
            "action": "continue distinct-date event collection; do not backfill into historical selector tests",
            "blocks_predictive_audit": int(sentiment_ledgers < MIN_SENTIMENT_LEDGERS),
        },
        {
            "gap": "history_selector_backfill",
            "current": "0 history-ready products/routes",
            "required": "disabled unless true PIT history exists",
            "action": "do not backfill external snapshots into 2020-2026 selector回测",
            "blocks_predictive_audit": 1,
        },
        {
            "gap": "member_detail_warehouse_source",
            "current": "0/37 forward-ready",
            "required": f">={MIN_FORWARD_PRODUCTS} products if used",
            "action": "keep out of hard selector until source/API recovers",
            "blocks_predictive_audit": 0,
        },
        {
            "gap": "basis_standalone_predictive_power",
            "current": f"best edge {basis_diag['basis_best_edge']:.4f}, pass={basis_diag['basis_diagnostic_pass']}",
            "required": "pass fixed diagnostic gates",
            "action": "basis only as joint feature/monitor, not standalone selector",
            "blocks_predictive_audit": 0,
        },
    ]
    gaps = pd.DataFrame(gap_rows)

    gate_rows = [
        {
            "gate": "basis_forward_usable",
            "passed": int(priority.loc[priority["source_route"].eq("basis"), "latest_forward_ready_products"].iloc[0] >= MIN_FORWARD_PRODUCTS),
            "actual": int(priority.loc[priority["source_route"].eq("basis"), "latest_forward_ready_products"].iloc[0]),
            "threshold": f">={MIN_FORWARD_PRODUCTS}",
        },
        {
            "gate": "inventory_forward_usable",
            "passed": int(priority.loc[priority["source_route"].eq("inventory"), "latest_forward_ready_products"].iloc[0] >= MIN_FORWARD_PRODUCTS),
            "actual": int(priority.loc[priority["source_route"].eq("inventory"), "latest_forward_ready_products"].iloc[0]),
            "threshold": f">={MIN_FORWARD_PRODUCTS}",
        },
        {
            "gate": "enough_forward_runs",
            "passed": int(qualified_runs >= MIN_FORWARD_RUNS),
            "actual": qualified_runs,
            "threshold": MIN_FORWARD_RUNS,
        },
        {
            "gate": "enough_forward_dates",
            "passed": int(qualified_dates >= MIN_FORWARD_DATES),
            "actual": qualified_dates,
            "threshold": MIN_FORWARD_DATES,
        },
        {
            "gate": "sentiment_real_ledger_ready",
            "passed": int(sentiment_ledgers >= MIN_SENTIMENT_LEDGERS),
            "actual": sentiment_ledgers,
            "threshold": MIN_SENTIMENT_LEDGERS,
        },
        {
            "gate": "history_backfill_allowed",
            "passed": 0,
            "actual": "0 history-ready routes",
            "threshold": "true point-in-time historical ledger",
        },
        {
            "gate": "basis_standalone_selector_pass",
            "passed": int(basis_diag["basis_diagnostic_pass"]),
            "actual": f"edge={basis_diag['basis_best_edge']:.4f}",
            "threshold": "fixed Stage247 selector gates",
        },
        {
            "gate": "ready_for_predictive_audit",
            "passed": int(qualified_runs >= MIN_FORWARD_RUNS and qualified_dates >= MIN_FORWARD_DATES and sentiment_ledgers >= 1),
            "actual": f"runs={qualified_runs}, dates={qualified_dates}, sentiment={sentiment_ledgers}",
            "threshold": "20/20 + sentiment ledger",
        },
    ]
    gates = pd.DataFrame(gate_rows)
    return priority, gaps, gates


def _make_chart(priority: pd.DataFrame, gaps: pd.DataFrame, gates: pd.DataFrame, feature: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage571 external selector source priority and data gaps", fontsize=14)

    ax = axes[0, 0]
    sample = gates[gates["gate"].isin(["enough_forward_runs", "enough_forward_dates", "sentiment_real_ledger_ready"])].copy()
    sample["actual_num"] = pd.to_numeric(sample["actual"], errors="coerce").fillna(0.0)
    sample["threshold_num"] = pd.to_numeric(sample["threshold"], errors="coerce").fillna(1.0)
    labels = sample["gate"].str.replace("_", "\n")
    x = np.arange(len(sample))
    ax.bar(x - 0.18, sample["actual_num"], width=0.36, label="current", color="#4C78A8")
    ax.bar(x + 0.18, sample["threshold_num"], width=0.36, label="required", color="#F58518", alpha=0.75)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Hard sample-depth blockers")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0, 1]
    routes = priority[priority["source_route"].isin(["basis", "inventory", "member_detail", "warehouse"])].copy()
    ax.bar(routes["source_route"], routes["latest_forward_ready_products"], label="forward-ready", color="#54A24B")
    ax.bar(routes["source_route"], routes["history_ready_products"], label="history-ready", color="#B279A2")
    ax.axhline(MIN_FORWARD_PRODUCTS, color="black", linestyle="--", linewidth=1)
    ax.set_title("Route coverage")
    ax.set_ylabel("products")
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    pview = priority.copy().sort_values("priority_score")
    colors = np.where(pview["priority_score"].ge(45), "#54A24B", np.where(pview["priority_score"].gt(0), "#F2CF5B", "#E45756"))
    ax.barh(pview["source_route"], pview["priority_score"], color=colors)
    ax.set_title("Source priority score")
    ax.set_xlabel("0-70 rough score")
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 1]
    fview = feature.head(10).iloc[::-1].copy()
    colors = np.where(fview["mean_spearman_ic"].ge(0.15), "#54A24B", np.where(fview["mean_spearman_ic"].ge(0.10), "#F2CF5B", "#BAB0AC"))
    ax.barh(fview["feature"], fview["mean_spearman_ic"], color=colors)
    ax.axvline(0.10, color="#F2CF5B", linestyle="--", linewidth=1)
    ax.axvline(0.15, color="#54A24B", linestyle="--", linewidth=1)
    ax.set_title("Existing feature prior, not deployable")
    ax.set_xlabel("mean Spearman IC")
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _make_report(priority: pd.DataFrame, gaps: pd.DataFrame, gates: pd.DataFrame, feature: pd.DataFrame, decision: dict[str, Any]) -> str:
    lines = [
        "# Stage571 External Selector Source Priority Audit",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Decision",
        "",
        f"`{decision['decision']}`",
        "",
        "## Key Takeaways",
        "",
        *[f"- {item}" for item in decision["key_takeaways"]],
        "",
        "## Source Priority",
        "",
        _md_table(
            priority,
            [
                "source_route",
                "role",
                "latest_forward_ready_products",
                "history_ready_products",
                "qualified_forward_dates",
                "priority_score",
                "recommended_action",
            ],
        ),
        "",
        "## Data Gaps",
        "",
        _md_table(gaps),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Feature Prior",
        "",
        _md_table(feature, ["feature", "mean_spearman_ic", "positive_ic_rate_pct", "strength", "reason"], max_rows=12),
        "",
        "## Outputs",
        "",
        f"- chart: `{CHART_PATH}`",
        f"- source priority: `{SOURCE_PRIORITY_PATH}`",
        f"- data gaps: `{DATA_GAPS_PATH}`",
        f"- gates: `{GATES_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    feature = build_feature_prior()
    priority, gaps, gates = build_source_priority()
    passed = int(gates["passed"].sum())
    total = int(len(gates))
    enough_runs = int(gates[gates["gate"].eq("enough_forward_runs")]["passed"].iloc[0]) == 1
    enough_dates = int(gates[gates["gate"].eq("enough_forward_dates")]["passed"].iloc[0]) == 1
    sentiment_ready = int(gates[gates["gate"].eq("sentiment_real_ledger_ready")]["passed"].iloc[0]) == 1
    if int(gates[gates["gate"].eq("ready_for_predictive_audit")]["passed"].iloc[0]) == 1:
        decision_code = "selector_predictive_audit_can_start"
    elif sentiment_ready and not (enough_runs and enough_dates):
        decision_code = "basis_inventory_sentiment_forward_monitor_sample_depth_blocked"
    else:
        decision_code = "basis_inventory_forward_monitor_only_sentiment_ledger_missing"

    basis = priority[priority["source_route"].eq("basis")].iloc[0]
    inventory = priority[priority["source_route"].eq("inventory")].iloc[0]
    sentiment = priority[priority["source_route"].eq("sentiment_news_manual_event")].iloc[0]
    key_takeaways = [
        (
            f"Hard gates passed {passed}/{total}; predictive audit remains blocked by forward sample depth, "
            f"not by the real sentiment ledger." if sentiment_ready
            else f"Hard gates passed {passed}/{total}; predictive audit remains blocked by forward sample depth and sentiment ledger."
        ),
        f"Basis is the best current external route by coverage: {int(basis['latest_forward_ready_products'])}/37 forward-ready, but standalone basis selector previously failed.",
        f"Inventory is usable for forward collection: {int(inventory['latest_forward_ready_products'])}/37 forward-ready, but has no standalone predictive audit yet.",
        "Member_detail and warehouse have 0/37 forward-ready products and cannot be hard dependencies.",
        (
            f"News/sentiment has started a real received_at ledger with {int(sentiment['latest_forward_ready_products'])} mapped products; it remains forward-monitor only until 20/20 samples mature."
            if sentiment_ready
            else "News/sentiment still has no real received_at ledger; it must be built before any sentiment backtest."
        ),
    ]
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision_code,
        "passed_gates": passed,
        "total_gates": total,
        "key_takeaways": key_takeaways,
        "outputs": {
            "source_priority": str(SOURCE_PRIORITY_PATH),
            "data_gaps": str(DATA_GAPS_PATH),
            "gates": str(GATES_PATH),
            "feature_prior": str(FEATURE_PRIOR_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    SOURCE_PRIORITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    priority.to_csv(SOURCE_PRIORITY_PATH, index=False, encoding="utf-8-sig")
    gaps.to_csv(DATA_GAPS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    feature.to_csv(FEATURE_PRIOR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_make_report(priority, gaps, gates, feature, decision), encoding="utf-8")
    _make_chart(priority, gaps, gates, feature)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
