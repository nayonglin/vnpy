from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage572_real_sentiment_event_ledger_bootstrap_v1"
OUTPUT_PREFIX = "qmt_roll_stage572_real_sentiment_event_ledger_bootstrap"
LINE_ID = "futures_trend_drawdown30_preserve_return"

REAL_LEDGER_PATH = LEDGER_DIR / f"sentiment_news_manual_event_forward_ledger_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
STAGE561_GATES_PATH = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_gates_stage561_selector_predictive_audit_protocol_v1.csv"

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")

SENTIMENT_COLUMNS = [
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

POINT_IN_TIME_RULE = (
    "Only rows already persisted by received_at_local can be used at selector_eval_time; "
    "never backfill this event into historical selector tests."
)


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gate(group: str, name: str, passed: bool, actual: str, threshold: str, reason: str) -> dict[str, Any]:
    return {
        "gate_group": group,
        "gate": name,
        "passed": int(bool(passed)),
        "actual": actual,
        "threshold": threshold,
        "reason": reason,
    }


def _source_age_hours(received_at_local: str, published_at: str) -> float:
    received = pd.to_datetime(received_at_local)
    published = pd.to_datetime(published_at)
    return float((received - published).total_seconds() / 3600.0)


def _event_rows(now_local: datetime) -> pd.DataFrame:
    received_at_local = now_local.isoformat()
    received_at_utc = now_local.astimezone(UTC_TZ).isoformat()
    run_id = f"stage572_{now_local.strftime('%Y%m%d_%H%M%S')}"
    source_url = "https://esmis.nal.usda.gov/sites/default/release-files/795928/prog2226.txt"
    published_at = "2026-06-01T16:00:00-04:00"
    source_name = "USDA NASS Crop Progress"
    mapper_version = "manual_event_mapper_cn_futures_v1"
    product_mapping_method = "keyword_manual_usda_crop_to_cn_futures"

    seeds = [
        {
            "event_id": "usda_crop_progress_20260601_corn",
            "product_vt_symbol": "c.DCE",
            "product_code": "c",
            "exchange": "DCE",
            "product_family": "grains_oilseeds",
            "headline": "USDA Crop Progress Jun 01 2026: corn progress and first condition rating",
            "summary": "USDA reported U.S. corn planting at 93%, emergence at 76%, and good/excellent condition at 67% for the week ending 2026-05-31.",
            "raw_text_excerpt": "Corn: planted 93%, emerged 76%, good/excellent 67%.",
            "event_type": "supply_weather",
            "sentiment_label": "bearish",
            "sentiment_score": -0.25,
            "relevance_score": 0.65,
            "direction_hint": "short",
            "notes": "Progress and condition are not a trade signal; keep as forward monitor only.",
        },
        {
            "event_id": "usda_crop_progress_20260601_soybean_meal",
            "product_vt_symbol": "m.DCE",
            "product_code": "m",
            "exchange": "DCE",
            "product_family": "grains_oilseeds",
            "headline": "USDA Crop Progress Jun 01 2026: soybean progress and first condition rating",
            "summary": "USDA reported U.S. soybeans planted at 87%, emerged at 65%, and good/excellent condition at 66% for the week ending 2026-05-31.",
            "raw_text_excerpt": "Soybeans: planted 87%, emerged 65%, good/excellent 66%.",
            "event_type": "supply_weather",
            "sentiment_label": "bearish",
            "sentiment_score": -0.20,
            "relevance_score": 0.50,
            "direction_hint": "short",
            "notes": "Mapped to soybean meal as soybean-chain supply monitor; not a standalone selector.",
        },
        {
            "event_id": "usda_crop_progress_20260601_soybean_oil",
            "product_vt_symbol": "y.DCE",
            "product_code": "y",
            "exchange": "DCE",
            "product_family": "grains_oilseeds",
            "headline": "USDA Crop Progress Jun 01 2026: soybean progress and first condition rating",
            "summary": "USDA reported U.S. soybeans planted at 87%, emerged at 65%, and good/excellent condition at 66% for the week ending 2026-05-31.",
            "raw_text_excerpt": "Soybeans: planted 87%, emerged 65%, good/excellent 66%.",
            "event_type": "supply_weather",
            "sentiment_label": "bearish",
            "sentiment_score": -0.20,
            "relevance_score": 0.50,
            "direction_hint": "short",
            "notes": "Mapped to soybean oil as soybean-chain supply monitor; not a standalone selector.",
        },
    ]

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        captured_text = "|".join(
            [
                source_name,
                source_url,
                published_at,
                seed["event_id"],
                seed["headline"],
                seed["summary"],
                seed["raw_text_excerpt"],
            ]
        )
        rows.append(
            {
                "run_id": run_id,
                "received_at_local": received_at_local,
                "received_at_utc": received_at_utc,
                "line_id": LINE_ID,
                "route": "manual_event",
                "product_vt_symbol": seed["product_vt_symbol"],
                "product_code": seed["product_code"],
                "exchange": seed["exchange"],
                "product_family": seed["product_family"],
                "source_name": source_name,
                "source_url": source_url,
                "published_at": published_at,
                "headline": seed["headline"],
                "summary": seed["summary"],
                "raw_text_hash": _sha256(captured_text),
                "raw_text_excerpt": seed["raw_text_excerpt"],
                "event_type": seed["event_type"],
                "sentiment_label": seed["sentiment_label"],
                "sentiment_score": seed["sentiment_score"],
                "relevance_score": seed["relevance_score"],
                "direction_hint": seed["direction_hint"],
                "mapper_version": mapper_version,
                "product_mapping_method": product_mapping_method,
                "status": "ok",
                "source_age_hours": _source_age_hours(received_at_local, published_at),
                "usable_for_forward_monitor": 1,
                "usable_for_history_selector": 0,
                "point_in_time_rule": POINT_IN_TIME_RULE,
                "notes": seed["notes"],
            }
        )
    return pd.DataFrame(rows, columns=SENTIMENT_COLUMNS)


def _build_summaries(ledger: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_summary = (
        ledger.groupby(["route", "source_name", "published_at", "sentiment_label", "event_type"], as_index=False)
        .agg(
            rows=("product_vt_symbol", "size"),
            products=("product_vt_symbol", lambda item: ",".join(sorted(set(map(str, item))))),
            avg_relevance=("relevance_score", "mean"),
            avg_sentiment=("sentiment_score", "mean"),
            max_source_age_hours=("source_age_hours", "max"),
        )
        .sort_values(["route", "source_name"])
    )
    product_summary = (
        ledger.groupby(["product_vt_symbol", "product_family", "sentiment_label", "direction_hint"], as_index=False)
        .agg(
            event_rows=("route", "size"),
            avg_relevance=("relevance_score", "mean"),
            avg_sentiment=("sentiment_score", "mean"),
            usable_forward=("usable_for_forward_monitor", "sum"),
            usable_history=("usable_for_history_selector", "sum"),
        )
        .sort_values(["product_family", "product_vt_symbol"])
    )
    return event_summary, product_summary


def _parse_stage561_count(gates: pd.DataFrame, gate: str, fallback: int = 0) -> int:
    if gates.empty or "gate" not in gates.columns:
        return fallback
    row = gates[gates["gate"].astype(str).eq(gate)]
    if row.empty:
        return fallback
    for column in ["current", "actual", "value"]:
        if column in row.columns:
            value = str(row.iloc[0].get(column, ""))
            try:
                return int(float(value.split("/")[0].strip()))
            except ValueError:
                continue
    return fallback


def _predictive_sample_progress() -> tuple[int, int]:
    if not STAGE561_GATES_PATH.exists():
        return 0, 0
    gates = pd.read_csv(STAGE561_GATES_PATH, encoding="utf-8-sig")
    return (
        _parse_stage561_count(gates, "forward_runs_ready", 0),
        _parse_stage561_count(gates, "forward_dates_ready", 0),
    )


def _build_gates(ledger: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in SENTIMENT_COLUMNS if column not in ledger.columns]
    source_urls_ok = bool(ledger["source_url"].fillna("").astype(str).str.startswith("https://").all())
    hashes_ok = bool(ledger["raw_text_hash"].fillna("").astype(str).str.fullmatch(r"[0-9a-f]{64}").all())
    pit_ok = bool(ledger["point_in_time_rule"].fillna("").astype(str).str.contains("received_at").all())
    received_ok = bool(pd.to_datetime(ledger["received_at_local"], errors="coerce").notna().all())
    published_ok = bool(pd.to_datetime(ledger["published_at"], errors="coerce").notna().all())
    forward_ok = bool(pd.to_numeric(ledger["usable_for_forward_monitor"], errors="coerce").fillna(0).eq(1).all())
    history_disabled = bool(pd.to_numeric(ledger["usable_for_history_selector"], errors="coerce").fillna(0).eq(0).all())
    product_mapping_ok = bool(ledger["product_mapping_method"].fillna("").astype(str).ne("").all())
    products = int(ledger["product_vt_symbol"].nunique())
    sources = int(ledger["source_url"].nunique())
    forward_runs, forward_dates = _predictive_sample_progress()
    real_ledger_ok = len(ledger) > 0

    return pd.DataFrame(
        [
            _gate("ledger_qualification", "real_ledger_exists", real_ledger_ok, str(len(ledger)), ">=1 row", "Stage272 sentiment/news hard gap needs a real received_at ledger."),
            _gate("ledger_qualification", "schema_complete", not missing, f"missing={missing}", "all Stage559 sentiment columns", "Keep the ledger compatible with the existing contract."),
            _gate("ledger_qualification", "received_at_parseable", received_ok, str(received_ok), "true", "Trading decisions must use the actual persisted time."),
            _gate("ledger_qualification", "published_at_parseable", published_ok, str(published_ok), "true", "Source claimed time is tracked separately from received_at."),
            _gate("ledger_qualification", "source_url_present", source_urls_ok, str(source_urls_ok), "https source URL", "Events must be traceable."),
            _gate("ledger_qualification", "raw_text_hash_present", hashes_ok, str(hashes_ok), "sha256 per row", "Source snapshots must be change-auditable."),
            _gate("ledger_qualification", "product_mapping_present", product_mapping_ok, str(product_mapping_ok), "non-empty method", "Events must map to tradable products."),
            _gate("ledger_qualification", "forward_monitor_enabled", forward_ok, str(forward_ok), "all rows = 1", "Rows can enter paper monitoring after received_at."),
            _gate("ledger_qualification", "history_selector_disabled", history_disabled, str(history_disabled), "all rows = 0", "Do not backfill this event into historical selector tests."),
            _gate("ledger_qualification", "point_in_time_rule_present", pit_ok, str(pit_ok), "mentions received_at", "Avoid look-ahead leakage."),
            _gate("ledger_qualification", "minimum_product_rows", products >= 3, str(products), ">=3 mapped products", "The bootstrap should test multi-product mapping."),
            _gate("ledger_qualification", "minimum_source_count", sources >= 1, str(sources), ">=1 source", "At least one real source is needed."),
            _gate("predictive_readiness", "forward_runs_ready", forward_runs >= 20, str(forward_runs), ">=20", "The selector audit still needs distinct qualified forward samples."),
            _gate("predictive_readiness", "forward_dates_ready", forward_dates >= 20, str(forward_dates), ">=20", "Same-day repeated runs cannot replace cross-date observations."),
            _gate(
                "predictive_readiness",
                "ready_for_selector_audit",
                real_ledger_ok and forward_runs >= 20 and forward_dates >= 20,
                f"ledger={int(real_ledger_ok)}, runs={forward_runs}, dates={forward_dates}",
                "ledger>=1 + runs>=20 + dates>=20",
                "Ledger bootstrap alone is not enough to run predictive IC/bucket tests.",
            ),
        ]
    )


def _plot_chart(ledger: pd.DataFrame, product_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("Stage572 real event ledger bootstrap", fontsize=15)

    ax = axes[0, 0]
    status_counts = ledger.groupby(["route", "status"]).size().reset_index(name="rows")
    labels = status_counts["route"] + "/" + status_counts["status"]
    ax.bar(labels, status_counts["rows"], color="#4c78a8")
    ax.set_title("Ledger rows by route/status")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=15)

    ax = axes[0, 1]
    labels = product_summary["product_vt_symbol"].astype(str)
    colors = ["#e45756" if val < 0 else "#54a24b" for val in product_summary["avg_sentiment"]]
    ax.bar(labels, product_summary["avg_sentiment"], color=colors)
    ax.axhline(0, color="#222222", linewidth=0.8)
    ax.set_title("Mapped products and sentiment score")
    ax.set_ylabel("score (-1 to 1)")

    ax = axes[1, 0]
    ax.bar(product_summary["product_vt_symbol"], product_summary["avg_relevance"], color="#72b7b2")
    ax.set_ylim(0, 1)
    ax.set_title("Product relevance score")
    ax.set_ylabel("0-1 relevance")

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_view["label"] = gate_view["gate_group"].astype(str).str.replace("_", " ") + ": " + gate_view["gate"].astype(str)
    colors = gate_view["passed"].map({1: "#54a24b", 0: "#e45756"}).tolist()
    display_width = gate_view["passed"].replace({0: 0.04})
    ax.barh(gate_view["label"], display_width, color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Ledger gates and predictive blockers")
    ax.set_xlabel("pass=1")
    ax.invert_yaxis()

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    ledger: pd.DataFrame,
    event_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: str,
) -> None:
    passed = int(gates["passed"].sum())
    total = int(len(gates))
    ledger_passed = int(gates.loc[gates["gate_group"].eq("ledger_qualification"), "passed"].sum())
    ledger_total = int(gates["gate_group"].eq("ledger_qualification").sum())
    predictive_passed = int(gates.loc[gates["gate_group"].eq("predictive_readiness"), "passed"].sum())
    predictive_total = int(gates["gate_group"].eq("predictive_readiness").sum())
    report = f"""# Stage572 Real Sentiment/Event Ledger Bootstrap

生成时间：{datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")}

## Decision

`{decision}`

## Key Takeaways

- This stage creates the first real `manual_event` ledger file with actual `received_at` timestamps.
- It uses USDA NASS Crop Progress released on 2026-06-01 and maps the event to `c.DCE`, `m.DCE`, and `y.DCE`.
- All rows are forward-monitor only: `usable_for_forward_monitor=1`, `usable_for_history_selector=0`.
- This fixes the minimum sentiment/news/manual event ledger gap, but does not make the selector predictive-audit ready because forward sample depth is still far below `20/20`.
- Ledger qualification gates: `{ledger_passed}/{ledger_total}`; predictive readiness gates: `{predictive_passed}/{predictive_total}`; total gates: `{passed}/{total}`.

## Gates

{_md_table(gates, max_rows=40)}

## Event Summary

{_md_table(event_summary, max_rows=20)}

## Product Summary

{_md_table(product_summary, max_rows=20)}

## Ledger Preview

{_md_table(ledger[["received_at_local", "route", "product_vt_symbol", "source_name", "sentiment_label", "sentiment_score", "relevance_score", "usable_for_history_selector"]], max_rows=20)}

## Outputs

- real ledger: `{REAL_LEDGER_PATH}`
- event summary: `{EVENT_SUMMARY_PATH}`
- product summary: `{PRODUCT_SUMMARY_PATH}`
- gates: `{GATES_PATH}`
- decision: `{DECISION_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    now_local = datetime.now(LOCAL_TZ).replace(microsecond=0)

    ledger = _event_rows(now_local)
    event_summary, product_summary = _build_summaries(ledger)
    gates = _build_gates(ledger)
    decision = "real_event_ledger_started_predictive_audit_still_blocked"

    ledger.to_csv(REAL_LEDGER_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    _plot_chart(ledger, product_summary, gates)
    _write_report(ledger, event_summary, product_summary, gates, decision)

    decision_payload = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "passed_gates": int(gates["passed"].sum()),
        "total_gates": int(len(gates)),
        "real_ledger_rows": int(len(ledger)),
        "mapped_products": sorted(ledger["product_vt_symbol"].unique().tolist()),
        "usable_for_history_selector_rows": int(pd.to_numeric(ledger["usable_for_history_selector"], errors="coerce").fillna(0).sum()),
        "key_takeaways": [
            "Created first real received_at manual_event ledger from an official USDA source.",
            "Rows are forward-monitor only and cannot be backfilled into historical selector tests.",
            "Mapped products are c.DCE, m.DCE, and y.DCE; this is a source-led event mapping, not an alpha claim.",
            "Predictive audit remains blocked by external forward sample depth and future label maturity.",
        ],
        "outputs": {
            "real_ledger": str(REAL_LEDGER_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
