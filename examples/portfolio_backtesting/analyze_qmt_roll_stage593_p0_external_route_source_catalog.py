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


MODEL_TAG = "stage593_p0_external_route_source_catalog_v1"
OUTPUT_PREFIX = "qmt_roll_stage593_p0_external_route_source_catalog"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE592_PRODUCT_BUDGET = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_product_budget_stage592_breadth_selector_structure_audit_v1.csv"
STAGE592_NEXT_ACTIONS = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_next_actions_stage592_breadth_selector_structure_audit_v1.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / "qmt_roll_stage571_external_selector_source_priority_audit_source_priority_stage571_external_selector_source_priority_audit_v1.csv"
STAGE561_GATES = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_gates_stage561_selector_predictive_audit_protocol_v1.csv"

SOURCE_CATALOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_catalog_{MODEL_TAG}.csv"
PRODUCT_ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_route_matrix_{MODEL_TAG}.csv"
LEDGER_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_contract_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MISSING_EVENT_PRODUCTS = ["v.DCE", "ao.SHFE", "lu.INE"]
MISSING_BASIS_SUBSTITUTE_PRODUCTS = ["ao.SHFE", "lu.INE"]
MISSING_GAP_PRODUCTS = sorted(set(MISSING_EVENT_PRODUCTS + MISSING_BASIS_SUBSTITUTE_PRODUCTS))
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20

LEDGER_REQUIRED_FIELDS = [
    "run_id",
    "received_at_local",
    "received_at_utc",
    "line_id",
    "route",
    "product_vt_symbol",
    "product_code",
    "exchange",
    "product_family",
    "source_name",
    "source_url",
    "published_at",
    "headline",
    "summary",
    "raw_text_hash",
    "raw_text_excerpt",
    "event_type",
    "sentiment_label",
    "sentiment_score",
    "relevance_score",
    "direction_hint",
    "mapper_version",
    "product_mapping_method",
    "status",
    "source_age_hours",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "point_in_time_rule",
    "notes",
]


SOURCE_CATALOG = [
    {
        "product_vt_symbol": "v.DCE",
        "route": "inventory",
        "gap_target": "support_existing_route",
        "source_name": "DCE PVC warehouse receipt / warrant data",
        "source_url": "https://www.dce.com.cn/",
        "source_url_quality": "generic_official_entry",
        "official_source": 1,
        "exact_product_page": 0,
        "cadence": "trading_day_or_exchange_publish_day",
        "parser_status": "existing_inventory_ready_but_exact_url_not_frozen_here",
        "forward_ledger_usable": 1,
        "history_selector_usable": 0,
        "notes": "Stage588 already marks inventory ready for v; this row keeps it as support route, not as new alpha.",
    },
    {
        "product_vt_symbol": "v.DCE",
        "route": "sentiment_news_manual_event",
        "gap_target": "event_ready",
        "source_name": "DCE PVC announcements / delivery warehouse notices",
        "source_url": "https://www.dce.com.cn/",
        "source_url_quality": "generic_official_entry",
        "official_source": 1,
        "exact_product_page": 0,
        "cadence": "event_driven",
        "parser_status": "not_wired_exact_notice_locator_required",
        "forward_ledger_usable": 0,
        "history_selector_usable": 0,
        "notes": "Web search found third-party PVC warrant reports but no exact official daily PVC event endpoint; do not count as ready.",
    },
    {
        "product_vt_symbol": "ao.SHFE",
        "route": "inventory_or_warrant_substitute",
        "gap_target": "basis_or_substitute_route",
        "source_name": "SHFE warehouse receipt daily report entry",
        "source_url": "https://www.shfe.com.cn/index.html",
        "source_url_quality": "official_entry_with_warehouse_daily_link",
        "official_source": 1,
        "exact_product_page": 0,
        "cadence": "trading_day_or_exchange_publish_day",
        "parser_status": "not_wired",
        "forward_ledger_usable": 0,
        "history_selector_usable": 0,
        "notes": "Search result confirms SHFE site exposes 仓单日报; parser must freeze exact data endpoint before readiness.",
    },
    {
        "product_vt_symbol": "ao.SHFE",
        "route": "contract_delivery_context",
        "gap_target": "basis_or_substitute_route",
        "source_name": "SHFE Alumina futures contract appendix",
        "source_url": "https://www.shfe.com.cn/products/futures/metal/nonferrousmetal/ao_f/appendix/202306/t20230616_800368.html",
        "source_url_quality": "exact_official_product_page",
        "official_source": 1,
        "exact_product_page": 1,
        "cadence": "static_or_rule_change",
        "parser_status": "manual_reference_ready_not_alpha",
        "forward_ledger_usable": 1,
        "history_selector_usable": 0,
        "notes": "Good for product mapping, delivery unit and route validation; not a daily predictor.",
    },
    {
        "product_vt_symbol": "ao.SHFE",
        "route": "sentiment_news_manual_event",
        "gap_target": "event_ready",
        "source_name": "SHFE announcements and risk notices for alumina",
        "source_url": "https://www.shfe.com.cn/index.html",
        "source_url_quality": "generic_official_entry",
        "official_source": 1,
        "exact_product_page": 0,
        "cadence": "event_driven",
        "parser_status": "not_wired_exact_notice_locator_required",
        "forward_ledger_usable": 0,
        "history_selector_usable": 0,
        "notes": "Must capture published_at, received_at and raw hash before counting as event_ready.",
    },
    {
        "product_vt_symbol": "lu.INE",
        "route": "inventory_or_warrant_substitute",
        "gap_target": "basis_or_substitute_route",
        "source_name": "INE inventory weekly / delivery services entry",
        "source_url": "https://www.ine.cn/index.html",
        "source_url_quality": "official_entry_with_inventory_weekly_link",
        "official_source": 1,
        "exact_product_page": 0,
        "cadence": "weekly_or_exchange_publish_day",
        "parser_status": "not_wired",
        "forward_ledger_usable": 0,
        "history_selector_usable": 0,
        "notes": "Search result shows INE homepage exposes 库存周报; exact endpoint must be frozen and hashed.",
    },
    {
        "product_vt_symbol": "lu.INE",
        "route": "contract_delivery_context",
        "gap_target": "basis_or_substitute_route",
        "source_name": "INE Low Sulfur Fuel Oil futures contract",
        "source_url": "https://www.ine.com.cn/eng/market/futures/energy/lu/contract/",
        "source_url_quality": "exact_official_product_page",
        "official_source": 1,
        "exact_product_page": 1,
        "cadence": "static_or_rule_change",
        "parser_status": "manual_reference_ready_not_alpha",
        "forward_ledger_usable": 1,
        "history_selector_usable": 0,
        "notes": "Useful for product contract metadata and mapping; not a daily selector.",
    },
    {
        "product_vt_symbol": "lu.INE",
        "route": "delivery_rules_context",
        "gap_target": "basis_or_substitute_route",
        "source_name": "INE delivery rules for low sulfur fuel oil",
        "source_url": "https://www.ine.cn/regulation/ineregulation/rules/202308/t20230811_814259.html",
        "source_url_quality": "exact_official_rule_page",
        "official_source": 1,
        "exact_product_page": 1,
        "cadence": "static_or_rule_change",
        "parser_status": "manual_reference_ready_not_alpha",
        "forward_ledger_usable": 1,
        "history_selector_usable": 0,
        "notes": "Validates standard warrant / delivery semantics; not a standalone signal.",
    },
    {
        "product_vt_symbol": "lu.INE",
        "route": "standard_warrant_context",
        "gap_target": "basis_or_substitute_route",
        "source_name": "INE standard warrant management system guide",
        "source_url": "https://www.ine.cn/services/delivery/standardwarrantms/202404/W020240517500690551744.pdf",
        "source_url_quality": "exact_official_document",
        "official_source": 1,
        "exact_product_page": 1,
        "cadence": "static_or_rule_change",
        "parser_status": "manual_reference_ready_not_alpha",
        "forward_ledger_usable": 1,
        "history_selector_usable": 0,
        "notes": "Confirms warrant process; future live monitor still needs daily/weekly data endpoint.",
    },
    {
        "product_vt_symbol": "lu.INE",
        "route": "sentiment_news_manual_event",
        "gap_target": "event_ready",
        "source_name": "INE public notices and LSFO rule/news events",
        "source_url": "https://www.ine.cn/publicnotice/notice/202506/t20250627_828192.html",
        "source_url_quality": "exact_official_event_example",
        "official_source": 1,
        "exact_product_page": 1,
        "cadence": "event_driven",
        "parser_status": "example_ready_not_monitor_wired",
        "forward_ledger_usable": 0,
        "history_selector_usable": 0,
        "notes": "Good example of LSFO official event; needs crawler/search monitor before event_ready.",
    },
]


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
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def _gate_value(gates: pd.DataFrame, gate: str, field: str = "current", default: str = "") -> str:
    rows = gates[gates["gate"].astype(str).eq(gate)] if "gate" in gates.columns else pd.DataFrame()
    if rows.empty or field not in rows.columns:
        return default
    return str(rows[field].iloc[0])


def _parse_first_float(text: str, default: float = np.nan) -> float:
    import re

    match = re.search(r"-?\d+(?:\.\d+)?", str(text))
    if not match:
        return default
    return float(match.group(0))


def _build_source_catalog() -> pd.DataFrame:
    source = pd.DataFrame(SOURCE_CATALOG)
    product_budget = _read_csv(STAGE592_PRODUCT_BUDGET)
    source = source.merge(
        product_budget[
            [
                "product_vt_symbol",
                "product_family",
                "total_pnl",
                "positive_year_rate_pct",
                "abs_core_daily_pnl_corr",
                "two_route_ready",
                "event_ready",
                "primary_gap",
                "evidence_score_0_100",
            ]
        ],
        on="product_vt_symbol",
        how="left",
    )
    source["exact_and_official"] = (source["official_source"].eq(1) & source["exact_product_page"].eq(1)).astype(int)
    source["auto_monitor_ready"] = source["parser_status"].astype(str).str.contains("existing_").astype(int)
    source["manual_reference_only"] = source["parser_status"].astype(str).str.contains("manual_reference").astype(int)
    source["can_close_gap_now"] = (
        source["forward_ledger_usable"].eq(1)
        & source["auto_monitor_ready"].eq(1)
        & source["history_selector_usable"].eq(0)
    ).astype(int)
    return source


def _build_product_route_matrix(source: pd.DataFrame) -> pd.DataFrame:
    product_budget = _read_csv(STAGE592_PRODUCT_BUDGET)
    rows: list[dict[str, Any]] = []
    for _, product in product_budget.iterrows():
        product_symbol = str(product["product_vt_symbol"])
        subset = source[source["product_vt_symbol"].eq(product_symbol)]
        event_rows = subset[subset["gap_target"].eq("event_ready")]
        basis_rows = subset[subset["gap_target"].eq("basis_or_substitute_route")]
        rows.append(
            {
                "product_vt_symbol": product_symbol,
                "product_family": product["product_family"],
                "current_two_route_ready": int(product.get("two_route_ready", 0)),
                "current_event_ready": int(product.get("event_ready", 0)),
                "current_primary_gap": product.get("primary_gap", ""),
                "catalog_rows": int(len(subset)),
                "exact_official_rows": int(subset["exact_and_official"].sum()) if not subset.empty else 0,
                "auto_monitor_ready_rows": int(subset["auto_monitor_ready"].sum()) if not subset.empty else 0,
                "event_catalogued": int(len(event_rows) > 0),
                "event_auto_monitor_ready": int(event_rows["auto_monitor_ready"].sum() > 0) if not event_rows.empty else 0,
                "basis_substitute_catalogued": int(len(basis_rows) > 0),
                "basis_substitute_auto_monitor_ready": int(basis_rows["auto_monitor_ready"].sum() > 0) if not basis_rows.empty else 0,
                "post_stage593_event_ready": int(product.get("event_ready", 0)),
                "post_stage593_two_route_ready": int(product.get("two_route_ready", 0)),
                "stage593_role": "catalog_ready_parser_needed" if len(subset) > 0 else "no_catalog_source",
            }
        )
    return pd.DataFrame(rows)


def _build_ledger_contract() -> pd.DataFrame:
    rows = []
    for field in LEDGER_REQUIRED_FIELDS:
        if field in {"received_at_local", "received_at_utc"}:
            rule = "must be capture time when source is first persisted; selector may only use rows with received_at <= eval_time"
        elif field == "published_at":
            rule = "must be source-published timestamp when available; if absent, mark status=published_at_missing and do not score alpha"
        elif field == "source_url":
            rule = "must be exact URL for event/document/data endpoint, not only homepage, before event_ready"
        elif field == "raw_text_hash":
            rule = "sha256 over raw captured payload or normalized excerpt; required to prevent silent edits"
        elif field == "usable_for_history_selector":
            rule = "must remain 0 for forward-collected events until an independent history route is built"
        elif field == "usable_for_forward_monitor":
            rule = "1 only after exact source URL, timestamp and raw hash are present"
        else:
            rule = "required ledger field"
        rows.append(
            {
                "field": field,
                "required": 1,
                "point_in_time_rule": rule,
                "stage293_status": "contract_frozen",
            }
        )
    return pd.DataFrame(rows)


def _build_gates(source: pd.DataFrame, product_route: pd.DataFrame, ledger_contract: pd.DataFrame) -> pd.DataFrame:
    stage561 = _read_csv(STAGE561_GATES)
    forward_runs = _parse_first_float(_gate_value(stage561, "forward_runs_ready", "current", "0"))
    forward_dates = _parse_first_float(_gate_value(stage561, "forward_dates_ready", "current", "0"))
    missing_event_catalogued = int(product_route[product_route["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS)]["event_catalogued"].sum())
    missing_event_auto = int(product_route[product_route["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS)]["event_auto_monitor_ready"].sum())
    missing_basis_catalogued = int(product_route[product_route["product_vt_symbol"].isin(MISSING_BASIS_SUBSTITUTE_PRODUCTS)]["basis_substitute_catalogued"].sum())
    missing_basis_auto = int(product_route[product_route["product_vt_symbol"].isin(MISSING_BASIS_SUBSTITUTE_PRODUCTS)]["basis_substitute_auto_monitor_ready"].sum())
    exact_official_by_missing = source[source["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS + MISSING_BASIS_SUBSTITUTE_PRODUCTS)]
    exact_products = int(exact_official_by_missing[exact_official_by_missing["exact_and_official"].eq(1)]["product_vt_symbol"].nunique())

    missing_gap_catalogued = int(product_route[product_route["product_vt_symbol"].isin(MISSING_GAP_PRODUCTS)]["catalog_rows"].gt(0).sum())
    gates = [
        {
            "gate": "missing_gap_products_catalogued",
            "actual": f"{missing_gap_catalogued}/3 gap products",
            "threshold": "v/ao/lu all have at least one source row",
            "passed": int(missing_gap_catalogued == len(MISSING_GAP_PRODUCTS)),
            "hard_gate": 1,
            "judgement": "source catalog covers current missing-gap products; y/c only need tie-break.",
        },
        {
            "gate": "event_gap_catalogued",
            "actual": f"{missing_event_catalogued}/3 missing-event products",
            "threshold": "v/ao/lu all have event source candidates",
            "passed": int(missing_event_catalogued == 3),
            "hard_gate": 1,
            "judgement": "event source candidates exist, but parser readiness is separate.",
        },
        {
            "gate": "event_auto_monitor_ready",
            "actual": f"{missing_event_auto}/3 missing-event products",
            "threshold": "all missing-event products have exact auto monitor",
            "passed": int(missing_event_auto == 3),
            "hard_gate": 1,
            "judgement": "catalog is not enough; automated exact-source monitor is not ready.",
        },
        {
            "gate": "basis_substitute_catalogued",
            "actual": f"{missing_basis_catalogued}/2 missing-basis products",
            "threshold": "ao/lu both have basis or substitute source candidates",
            "passed": int(missing_basis_catalogued == 2),
            "hard_gate": 1,
            "judgement": "ao/lu can use exchange inventory/warrant context as substitute route candidates.",
        },
        {
            "gate": "basis_substitute_auto_monitor_ready",
            "actual": f"{missing_basis_auto}/2 missing-basis products",
            "threshold": "ao/lu exact data monitor wired",
            "passed": int(missing_basis_auto == 2),
            "hard_gate": 1,
            "judgement": "exact SHFE/INE daily-weekly data endpoints are not wired.",
        },
        {
            "gate": "exact_official_source_depth",
            "actual": f"{exact_products}/3 products with exact official rows among v/ao/lu",
            "threshold": "v/ao/lu all have exact official rows",
            "passed": int(exact_products == 3),
            "hard_gate": 1,
            "judgement": "ao/lu have exact official pages; v still mostly generic entry in this catalog.",
        },
        {
            "gate": "ledger_contract_frozen",
            "actual": f"{len(ledger_contract)} required fields",
            "threshold": f"{len(LEDGER_REQUIRED_FIELDS)} required fields",
            "passed": int(len(ledger_contract) == len(LEDGER_REQUIRED_FIELDS)),
            "hard_gate": 1,
            "judgement": "point-in-time ledger schema is reusable from Stage572.",
        },
        {
            "gate": "history_selector_disabled",
            "actual": f"{int(source['history_selector_usable'].sum())} history-usable rows",
            "threshold": "0 until independent history source exists",
            "passed": int(source["history_selector_usable"].sum() == 0),
            "hard_gate": 1,
            "judgement": "prevents turning forward-collected sources into retroactive selector backtests.",
        },
        {
            "gate": "forward_sample_depth",
            "actual": f"runs={forward_runs:.0f}, dates={forward_dates:.0f}",
            "threshold": f"runs>={MIN_FORWARD_RUNS}, dates>={MIN_FORWARD_DATES}",
            "passed": int(forward_runs >= MIN_FORWARD_RUNS and forward_dates >= MIN_FORWARD_DATES),
            "hard_gate": 1,
            "judgement": "source catalog does not replace Stage561 sample-depth gate.",
        },
        {
            "gate": "paper_selector_allowed",
            "actual": "false",
            "threshold": "only after auto monitors + 20/20 forward samples + fixed labels",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "this stage explicitly blocks PnL replay of the catalog.",
        },
    ]
    return pd.DataFrame(gates)


def _build_next_actions(source: pd.DataFrame, product_route: pd.DataFrame, gates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, route in product_route.iterrows():
        product = route["product_vt_symbol"]
        if product in MISSING_EVENT_PRODUCTS and int(route["event_auto_monitor_ready"]) == 0:
            rows.append(
                {
                    "target": product,
                    "priority": 90 if product == "v.DCE" else 80,
                    "gap": "event_auto_monitor_not_ready",
                    "action": "freeze exact official/event source locator, then persist source_url/published_at/received_at/raw_hash rows",
                    "done_condition": "Stage588 event_ready=1 for this product and Stage561 forward sample remains valid",
                }
            )
        if product in MISSING_BASIS_SUBSTITUTE_PRODUCTS and int(route["basis_substitute_auto_monitor_ready"]) == 0:
            rows.append(
                {
                    "target": product,
                    "priority": 85,
                    "gap": "basis_or_substitute_auto_monitor_not_ready",
                    "action": "wire exact SHFE/INE inventory or warrant endpoint; hash raw payload and mark as forward-only",
                    "done_condition": "Stage588 two_route_ready=1 for this product without using historical backfill",
                }
            )
    failed = gates[(gates["hard_gate"].eq(1)) & (gates["passed"].eq(0))]
    for _, gate in failed.iterrows():
        rows.append(
            {
                "target": gate["gate"],
                "priority": 70,
                "gap": gate["actual"],
                "action": gate["judgement"],
                "done_condition": gate["threshold"],
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["target", "priority", "gap", "action", "done_condition"])
    return out.sort_values(["priority", "target"], ascending=[False, True]).reset_index(drop=True)


def _plot(source: pd.DataFrame, product_route: pd.DataFrame, gates: pd.DataFrame) -> None:
    product_budget = _read_csv(STAGE592_PRODUCT_BUDGET)
    source_priority = _read_csv(STAGE571_SOURCE_PRIORITY)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("Stage593 P0 External Route Source Catalog", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    products = product_budget["product_vt_symbol"].tolist()
    scores = _num(product_budget, "evidence_score_0_100").tolist()
    colors = ["#2ca02c" if p not in MISSING_EVENT_PRODUCTS + MISSING_BASIS_SUBSTITUTE_PRODUCTS else "#d62728" for p in products]
    ax.bar(products, scores, color=colors)
    ax.set_title("Current P0 evidence score")
    ax.set_ylabel("score")
    ax.set_ylim(0, 105)
    ax.tick_params(axis="x", rotation=25)

    ax = axes[0, 1]
    matrix = product_route.set_index("product_vt_symbol")
    cols = ["catalog_rows", "exact_official_rows", "auto_monitor_ready_rows"]
    x = np.arange(len(matrix.index))
    width = 0.25
    for idx, col in enumerate(cols):
        ax.bar(x + (idx - 1) * width, matrix[col].values, width, label=col)
    ax.set_xticks(x)
    ax.set_xticklabels(matrix.index.tolist(), rotation=25)
    ax.set_title("Catalog depth vs monitor readiness (gap focus)")
    ax.set_ylabel("rows")
    ax.legend(fontsize=8)

    ax = axes[0, 2]
    route_summary = source.groupby("route", as_index=False).agg(
        rows=("product_vt_symbol", "count"),
        exact=("exact_and_official", "sum"),
        monitor=("auto_monitor_ready", "sum"),
    )
    x = np.arange(len(route_summary))
    ax.bar(x - width, route_summary["rows"], width, label="rows", color="#9ecae9")
    ax.bar(x, route_summary["exact"], width, label="exact official", color="#3182bd")
    ax.bar(x + width, route_summary["monitor"], width, label="auto monitor", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels(route_summary["route"].tolist(), rotation=25, ha="right")
    ax.set_title("Route source quality")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    source_priority = source_priority[source_priority["source_route"].isin(["basis", "inventory", "sentiment_news_manual_event"])]
    ax.bar(source_priority["source_route"], _num(source_priority, "latest_forward_ready_products"), color="#54a24b", label="forward-ready products")
    ax.bar(source_priority["source_route"], _num(source_priority, "history_ready_products"), color="#e45756", label="history-ready products")
    ax.set_title("Existing source readiness from Stage571")
    ax.set_ylabel("products")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    gate_counts = [
        int(gates[(gates["hard_gate"].eq(1)) & (gates["passed"].eq(1))].shape[0]),
        int(gates[(gates["hard_gate"].eq(1)) & (gates["passed"].eq(0))].shape[0]),
    ]
    ax.bar(["hard pass", "hard fail"], gate_counts, color=["#2ca02c", "#d62728"])
    ax.set_title("Stage593 hard gates")
    for idx, value in enumerate(gate_counts):
        ax.text(idx, value + 0.1, str(value), ha="center")

    ax = axes[1, 2]
    statuses = source["parser_status"].value_counts()
    y = np.arange(len(statuses))
    ax.barh(y, statuses.values, color="#f58518")
    ax.set_yticks(y)
    ax.set_yticklabels(statuses.index.astype(str), fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Parser status")
    ax.set_xlabel("rows")
    for idx, value in enumerate(statuses.values):
        ax.text(value + 0.05, idx, str(value), va="center", fontsize=9)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(source: pd.DataFrame, product_route: pd.DataFrame, ledger_contract: pd.DataFrame, gates: pd.DataFrame, next_actions: pd.DataFrame, decision: dict[str, Any]) -> None:
    hard = gates[gates["hard_gate"].eq(1)]
    failed = hard[hard["passed"].eq(0)]
    text = f"""# Stage593 P0 External Route Source Catalog Report

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- generated_at：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- decision：`{decision['decision']}`
- promotion_allowed：`{decision['promotion_allowed']}`
- paper_selector_allowed：`{decision['paper_selector_allowed']}`
- trading_whitelist_allowed：`{decision['trading_whitelist_allowed']}`
- hard_gates：`{decision['hard_gates_passed']}/{decision['hard_gates_total']}`

## External Research Judgment

- SHFE/INE 官方站点能提供氧化铝、低硫燃料油的合约、交割、仓单/库存入口和公告样例，这些适合做 forward monitor 和产品映射。
- DCE/PVC 的官方泛入口存在，但本阶段没有冻结到精确 PVC 事件/仓单 URL；第三方 PVC 仓单新闻只能作为发现线索，不能计入 event_ready。
- 所有事件/舆情数据必须写入 `received_at/source_url/published_at/raw_text_hash` 账本，且 `usable_for_history_selector=0`，直到独立历史源被证明。

## Source Catalog

{_md_table(source, [
    'product_vt_symbol',
    'route',
    'gap_target',
    'source_name',
    'source_url_quality',
    'official_source',
    'exact_product_page',
    'parser_status',
    'forward_ledger_usable',
    'history_selector_usable',
])}

## Product Route Matrix

{_md_table(product_route)}

## Ledger Contract

{_md_table(ledger_contract, max_rows=40)}

## Gates

{_md_table(gates)}

## Failed Hard Gates

{_md_table(failed, ['gate', 'actual', 'threshold', 'judgement'])}

## Next Actions

{_md_table(next_actions, max_rows=40)}

## Interpretation

- Stage593 把缺口源找到了，但没有把源提升为 selector alpha。
- `ao/lu` 有官方合约/交割/仓单上下文，可作为替代 route 的数据工程入口；但日/周数据 endpoint 还没自动化。
- `v` 的事件源仍最弱：必须冻结 DCE 精确公告/仓单 endpoint，不能用第三方新闻替代。
- 当前可以做的是 forward collection，不可以做 P0 收益回测或交易白名单。

## Files

- source_catalog：`{SOURCE_CATALOG_PATH}`
- product_route_matrix：`{PRODUCT_ROUTE_MATRIX_PATH}`
- ledger_contract：`{LEDGER_CONTRACT_PATH}`
- gates：`{GATES_PATH}`
- next_actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _build_source_catalog()
    product_route = _build_product_route_matrix(source)
    ledger_contract = _build_ledger_contract()
    gates = _build_gates(source, product_route, ledger_contract)
    next_actions = _build_next_actions(source, product_route, gates)

    hard = gates[gates["hard_gate"].eq(1)]
    hard_pass = int(hard["passed"].sum())
    hard_total = int(len(hard))
    promotion_allowed = False
    paper_selector_allowed = False
    trading_whitelist_allowed = False
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "p0_external_route_catalog_ready_parser_and_forward_depth_blocked",
        "promotion_allowed": promotion_allowed,
        "paper_selector_allowed": paper_selector_allowed,
        "trading_whitelist_allowed": trading_whitelist_allowed,
        "source_catalog_rows": int(len(source)),
        "p0_products_with_catalog_rows": int(product_route[product_route["catalog_rows"].gt(0)]["product_vt_symbol"].nunique()),
        "missing_event_products_catalogued": int(product_route[product_route["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS)]["event_catalogued"].sum()),
        "missing_event_products_auto_monitor_ready": int(product_route[product_route["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS)]["event_auto_monitor_ready"].sum()),
        "missing_basis_products_catalogued": int(product_route[product_route["product_vt_symbol"].isin(MISSING_BASIS_SUBSTITUTE_PRODUCTS)]["basis_substitute_catalogued"].sum()),
        "missing_basis_products_auto_monitor_ready": int(product_route[product_route["product_vt_symbol"].isin(MISSING_BASIS_SUBSTITUTE_PRODUCTS)]["basis_substitute_auto_monitor_ready"].sum()),
        "hard_gates_passed": hard_pass,
        "hard_gates_total": hard_total,
        "failed_hard_gates": hard.loc[hard["passed"].eq(0), "gate"].astype(str).tolist(),
        "main_judgement": "P0外生源目录和账本合同已可执行化，但缺精确endpoint自动采集与20/20 forward样本，禁止收益回测化selector。",
    }

    source.to_csv(SOURCE_CATALOG_PATH, index=False, encoding="utf-8-sig")
    product_route.to_csv(PRODUCT_ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    ledger_contract.to_csv(LEDGER_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(source, product_route, ledger_contract, gates, next_actions, decision)
    _plot(source, product_route, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
