from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
MODEL_TAG = "stage630_p2_master_pit_append_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage630_p2_master_pit_append_gate"

STAGE629_MODEL_TAG = "stage629_p2_public_source_monitor_run_v1"
STAGE629_PREFIX = "qmt_roll_stage629_p2_public_source_monitor_run"
RUN_LEDGER_PATH = OUTPUT_DIR / f"{STAGE629_PREFIX}_run_ledger_{STAGE629_MODEL_TAG}.csv"

MASTER_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_p2_public_source_master_pit_ledger.csv"
APPEND_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_append_rows_{MODEL_TAG}.csv"
REJECTED_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rejected_rows_{MODEL_TAG}.csv"
PRODUCT_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_progress_{MODEL_TAG}.csv"
SOURCE_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_MONTHS_FOR_SELECTOR = 12
REQUIRED_PRODUCTS = 3
REQUIRED_EVENT_PRODUCTS = 2

REQUIRED_FIELDS = [
    "run_id",
    "row_id",
    "received_at_local",
    "received_at_utc",
    "line_id",
    "product_vt_symbol",
    "product_family",
    "source_name",
    "source_url",
    "final_url",
    "source_authority",
    "source_class",
    "route",
    "event_family",
    "event_type",
    "monitor_frequency",
    "fetch_status",
    "combined_response_bytes",
    "any_raw_hash_present",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "event_signal_ready",
    "paper_or_whitelist_allowed",
    "raw_sha256",
    "linked_text_sha256",
    "product_mapping_method",
    "point_in_time_rule",
]

REFERENCES = [
    "Glassnode PIT metrics: https://docs.glassnode.com/data/point-in-time-metrics",
    "Glassnode look-ahead/PIT article: https://insights.glassnode.com/why-use-point-in-time-data/",
    "vBase audit timestamp/hash trail: https://docs.vbase.com/overview/what-vbase-verifies",
    "Convexly audit chain verifier: https://www.convexly.app/research/verify",
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_ledger(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for field in REQUIRED_FIELDS:
        if field not in normalized.columns:
            normalized[field] = ""

    normalized["line_id"] = _str(normalized, "line_id")
    normalized["product_vt_symbol"] = _str(normalized, "product_vt_symbol")
    normalized["product_family"] = _str(normalized, "product_family")
    normalized["source_name"] = _str(normalized, "source_name")
    normalized["source_url"] = _str(normalized, "source_url")
    normalized["final_url"] = _str(normalized, "final_url")
    normalized["received_at_utc"] = _str(normalized, "received_at_utc")
    normalized["received_at_local"] = _str(normalized, "received_at_local")
    normalized["raw_sha256"] = _str(normalized, "raw_sha256")
    normalized["linked_text_sha256"] = _str(normalized, "linked_text_sha256")
    normalized["hash_combo"] = normalized["raw_sha256"] + "|" + normalized["linked_text_sha256"]
    normalized["pit_date"] = normalized["received_at_utc"].str.slice(0, 10)
    normalized["pit_month"] = normalized["received_at_utc"].str.slice(0, 7)
    normalized["dedupe_key"] = (
        normalized["product_vt_symbol"]
        + "||"
        + normalized["source_url"]
        + "||"
        + normalized["received_at_utc"]
        + "||"
        + normalized["hash_combo"]
    )
    normalized["master_appended_at_cst"] = _fmt_cst(_now_cst())
    normalized["master_model_tag"] = MODEL_TAG
    return normalized


def _build_append_sets(run_ledger: pd.DataFrame, existing_master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = _normalize_ledger(run_ledger)
    reject_reasons: list[list[str]] = []
    for _, row in frame.iterrows():
        reasons: list[str] = []
        if row["line_id"] != LINE_ID:
            reasons.append("wrong_line_id")
        if not row["source_url"] or not row["final_url"]:
            reasons.append("missing_source_or_final_url")
        if not row["received_at_utc"] or not row["received_at_local"]:
            reasons.append("missing_received_at")
        if not row["raw_sha256"] and not row["linked_text_sha256"]:
            reasons.append("missing_raw_hash")
        if int(float(row.get("any_raw_hash_present", 0) or 0)) != 1:
            reasons.append("any_raw_hash_present_not_1")
        if int(float(row.get("usable_for_forward_monitor", 0) or 0)) != 1:
            reasons.append("not_usable_for_forward_monitor")
        if int(float(row.get("usable_for_history_selector", 0) or 0)) != 0:
            reasons.append("history_selector_not_locked")
        if int(float(row.get("event_signal_ready", 0) or 0)) != 0:
            reasons.append("event_signal_not_locked")
        if int(float(row.get("paper_or_whitelist_allowed", 0) or 0)) != 0:
            reasons.append("paper_or_whitelist_not_locked")
        reject_reasons.append(reasons)

    frame["reject_reason"] = [";".join(item) for item in reject_reasons]
    eligible = frame[frame["reject_reason"].eq("")].copy()
    rejected = frame[~frame["reject_reason"].eq("")].copy()

    existing = _normalize_ledger(existing_master) if not existing_master.empty else pd.DataFrame(columns=frame.columns)
    existing_keys = set(_str(existing, "dedupe_key")) if not existing.empty else set()
    eligible["already_in_master"] = eligible["dedupe_key"].isin(existing_keys).astype(int)
    append_rows = eligible[eligible["already_in_master"].eq(0)].copy()
    duplicate_rows = eligible[eligible["already_in_master"].eq(1)].copy()

    if existing.empty:
        combined = append_rows.copy()
    elif append_rows.empty:
        combined = existing.copy()
    else:
        combined = pd.concat([existing, append_rows], ignore_index=True, sort=False)
    if not combined.empty:
        combined = combined.drop_duplicates("dedupe_key", keep="first")
        combined = combined.sort_values(["received_at_utc", "product_family", "product_vt_symbol", "source_name"]).reset_index(drop=True)
    return append_rows, duplicate_rows, rejected, combined


def _split_product_progress(master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if master.empty:
        return pd.DataFrame(
            columns=[
                "product_family",
                "product_vt_symbol",
                "weighted_rows",
                "pit_dates",
                "pit_months",
                "event_monitor_rows",
                "raw_hash_rows",
                "selector_rows",
                "paper_or_whitelist_rows",
                "progress_pct",
                "status",
            ]
        )

    for _, row in master.iterrows():
        products = [item.strip() for item in str(row["product_vt_symbol"]).split(",") if item.strip()]
        if not products:
            continue
        weight = 1.0 / len(products)
        for product in products:
            rows.append(
                {
                    "product_family": row["product_family"],
                    "product_vt_symbol": product,
                    "weight": weight,
                    "pit_date": row["pit_date"],
                    "pit_month": row["pit_month"],
                    "event_monitor": int(str(row.get("event_auto_monitor_validated", "0") or "0") == "1"),
                    "raw_hash": int(bool(row["raw_sha256"] or row["linked_text_sha256"])),
                    "selector": int(float(row.get("usable_for_history_selector", 0) or 0)),
                    "paper_or_whitelist": int(float(row.get("paper_or_whitelist_allowed", 0) or 0)),
                }
            )
    split = pd.DataFrame(rows)
    if split.empty:
        return pd.DataFrame()

    progress = (
        split.groupby(["product_family", "product_vt_symbol"], as_index=False)
        .agg(
            weighted_rows=("weight", "sum"),
            pit_dates=("pit_date", "nunique"),
            pit_months=("pit_month", "nunique"),
            event_monitor_rows=("event_monitor", "sum"),
            raw_hash_rows=("raw_hash", "sum"),
            selector_rows=("selector", "sum"),
            paper_or_whitelist_rows=("paper_or_whitelist", "sum"),
        )
        .sort_values(["product_family", "product_vt_symbol"])
        .reset_index(drop=True)
    )
    progress["progress_pct"] = (
        np.minimum(progress["pit_dates"] / REQUIRED_PIT_DATES_FOR_SELECTOR, 1.0) * 45
        + np.minimum(progress["pit_months"] / REQUIRED_MONTHS_FOR_SELECTOR, 1.0) * 25
        + (progress["event_monitor_rows"].gt(0).astype(float)) * 15
        + (progress["raw_hash_rows"].gt(0).astype(float)) * 15
    ).round(4)
    progress["status"] = np.where(
        (progress["pit_dates"].ge(REQUIRED_PIT_DATES_FOR_SELECTOR))
        & (progress["pit_months"].ge(REQUIRED_MONTHS_FOR_SELECTOR)),
        "pit_date_threshold_met_still_needs_episode_tca",
        "accumulating_pit_evidence_selector_locked",
    )
    return progress


def _source_progress(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame(columns=["source_name", "source_authority", "rows", "pit_dates", "raw_hash_rows", "total_bytes"])
    source = (
        master.groupby(["source_name", "source_authority", "source_class", "route"], as_index=False)
        .agg(
            rows=("dedupe_key", "count"),
            pit_dates=("pit_date", "nunique"),
            raw_hash_rows=("hash_combo", lambda series: int(series.astype(str).ne("|").sum())),
            total_bytes=("combined_response_bytes", lambda series: float(pd.to_numeric(series, errors="coerce").fillna(0).sum())),
        )
        .sort_values(["rows", "source_name"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return source


def _gates(
    run_ledger: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
    combined: pd.DataFrame,
    progress: pd.DataFrame,
) -> pd.DataFrame:
    covered_products = int(progress["product_vt_symbol"].nunique()) if not progress.empty else 0
    event_products = int(progress.loc[progress["event_monitor_rows"].gt(0), "product_vt_symbol"].nunique()) if not progress.empty else 0
    min_pit_dates = int(progress["pit_dates"].min()) if not progress.empty else 0
    max_selector_rows = int(progress["selector_rows"].max()) if not progress.empty else 0
    max_paper_rows = int(progress["paper_or_whitelist_rows"].max()) if not progress.empty else 0

    rows = [
        {
            "gate": "run_ledger_present",
            "passed": int(not run_ledger.empty),
            "current": len(run_ledger),
            "required": ">0",
            "note": "stage629 run ledger is the only input for this append gate.",
        },
        {
            "gate": "append_or_idempotent_duplicate_ok",
            "passed": int((len(append_rows) > 0) or (len(duplicate_rows) > 0 and len(rejected) == 0)),
            "current": f"append={len(append_rows)}, duplicate={len(duplicate_rows)}",
            "required": "append>0 or duplicate>0",
            "note": "new PIT rows append once; duplicate reruns should not inflate the master ledger.",
        },
        {
            "gate": "rejected_rows_zero",
            "passed": int(rejected.empty),
            "current": len(rejected),
            "required": 0,
            "note": "rows missing hash/source/time or lock discipline must be rejected.",
        },
        {
            "gate": "products_covered",
            "passed": int(covered_products >= REQUIRED_PRODUCTS),
            "current": covered_products,
            "required": REQUIRED_PRODUCTS,
            "note": "ag/CY/SR should be covered in the master PIT ledger.",
        },
        {
            "gate": "event_products_covered",
            "passed": int(event_products >= REQUIRED_EVENT_PRODUCTS),
            "current": event_products,
            "required": REQUIRED_EVENT_PRODUCTS,
            "note": "CY/SR event monitors should be represented; ag event source remains missing.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(max_selector_rows == 0),
            "current": max_selector_rows,
            "required": 0,
            "note": "PIT monitor rows must not enter history selector.",
        },
        {
            "gate": "paper_whitelist_rows_zero",
            "passed": int(max_paper_rows == 0),
            "current": max_paper_rows,
            "required": 0,
            "note": "no paper or trading whitelist rows are allowed.",
        },
        {
            "gate": "pit_dates_below_selector_threshold",
            "passed": int(min_pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": min_pit_dates,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "fail-closed discipline: one date is not enough for selector.",
        },
        {
            "gate": "master_written",
            "passed": int(MASTER_LEDGER_PATH.exists() and not combined.empty),
            "current": str(MASTER_LEDGER_PATH.exists()),
            "required": "true",
            "note": "stable master PIT ledger should exist for future append runs.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(
    progress: pd.DataFrame,
    source: pd.DataFrame,
    gates: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage630 P2 master PIT append gate: evidence accumulates, selector locked", fontsize=16)

    ax = axes[0, 0]
    if progress.empty:
        ax.text(0.5, 0.5, "No product progress", ha="center", va="center")
        ax.set_axis_off()
    else:
        x = np.arange(len(progress))
        ax.bar(x - 0.2, progress["pit_dates"], width=0.2, label="PIT dates")
        ax.bar(x, progress["pit_months"], width=0.2, label="PIT months")
        ax.bar(x + 0.2, progress["event_monitor_rows"], width=0.2, label="event rows")
        ax.axhline(REQUIRED_PIT_DATES_FOR_SELECTOR, color="tab:red", linestyle="--", linewidth=1, label="20 date selector gate")
        ax.set_xticks(x)
        ax.set_xticklabels(progress["product_vt_symbol"], rotation=0)
        ax.set_title("Product PIT progress")
        ax.set_ylabel("count")
        ax.legend(loc="upper left", fontsize=8)

    ax = axes[0, 1]
    if source.empty:
        ax.text(0.5, 0.5, "No source rows", ha="center", va="center")
        ax.set_axis_off()
    else:
        view = source.sort_values("total_bytes", ascending=True)
        y = np.arange(len(view))
        ax.barh(y, view["total_bytes"], color="tab:green")
        ax.set_yticks(y)
        ax.set_yticklabels(view["source_name"], fontsize=8)
        ax.set_title("Master bytes by source")
        ax.set_xlabel("combined response bytes")
        for yi, value in zip(y, view["raw_hash_rows"]):
            ax.text(0, yi, f" hash {int(value)}", va="center", ha="left", fontsize=8)

    ax = axes[1, 0]
    append_reject = pd.DataFrame(
        {
            "bucket": ["new append rows", "rejected rows", "already duplicate rows"],
            "count": [
                len(append_rows),
                len(rejected),
                len(duplicate_rows),
            ],
        }
    )
    colors = ["tab:green", "tab:red", "tab:orange"]
    ax.bar(append_reject["bucket"], append_reject["count"], color=colors)
    ax.set_title("Append gate result")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=15)
    for idx, value in enumerate(append_reject["count"]):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom")

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Gates: green includes fail-closed locks")
    ax.set_xlabel("passed")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    run_ledger: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
    combined: pd.DataFrame,
    progress: pd.DataFrame,
    source: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage630 P2 Master PIT Append Gate Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- input_run_ledger: `{RUN_LEDGER_PATH}`",
        f"- stable_master_ledger: `{MASTER_LEDGER_PATH}`",
        "",
        "## External Research Judgement",
        "",
        "PIT data is only useful for strategy research when the ledger preserves what was available at collection time and keeps revised/backfilled data out of historical selector logic. The append gate therefore stores timestamp, source URL, final URL, raw hash, status and lock fields before any future predictive audit.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- input rows: `{len(run_ledger)}`",
        f"- append rows: `{len(append_rows)}`",
        f"- duplicate rows: `{len(duplicate_rows)}`",
        f"- rejected rows: `{len(rejected)}`",
        f"- master rows: `{len(combined)}`",
        f"- products covered: `{decision['products_covered']}`",
        f"- min PIT dates: `{decision['min_pit_dates']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        "",
        "## Product Progress",
        "",
        _md_table(progress),
        "",
        "## Source Progress",
        "",
        _md_table(source),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Rejected Rows",
        "",
        _md_table(rejected[["row_id", "product_vt_symbol", "source_name", "reject_reason"]] if not rejected.empty else rejected),
        "",
        "## Interpretation",
        "",
        "- This stage advances source evidence accumulation, not alpha selection.",
        "- One PIT date is intentionally insufficient for selector or paper.",
        "- ag still lacks event-oriented monitor evidence; CY/SR have event/source evidence but no episode, predictive audit or TCA.",
        "- Rerunning the same Stage629 ledger should not inflate the master ledger because dedupe keys include received_at and raw hashes.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_ledger = _read_csv(RUN_LEDGER_PATH)
    if run_ledger.empty:
        raise FileNotFoundError(f"missing or empty run ledger: {RUN_LEDGER_PATH}")
    existing_master = _read_csv(MASTER_LEDGER_PATH)

    append_rows, duplicate_rows, rejected, combined = _build_append_sets(run_ledger, existing_master)
    combined.to_csv(MASTER_LEDGER_PATH, index=False, encoding="utf-8-sig")
    append_rows.to_csv(APPEND_ROWS_PATH, index=False, encoding="utf-8-sig")
    rejected.to_csv(REJECTED_ROWS_PATH, index=False, encoding="utf-8-sig")

    progress = _split_product_progress(combined)
    source = _source_progress(combined)
    gates = _gates(run_ledger, append_rows, duplicate_rows, rejected, combined, progress)
    progress.to_csv(PRODUCT_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    source.to_csv(SOURCE_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    selector_rows = int(progress["selector_rows"].max()) if not progress.empty else 0
    paper_rows = int(progress["paper_or_whitelist_rows"].max()) if not progress.empty else 0
    min_pit_dates = int(progress["pit_dates"].min()) if not progress.empty else 0
    products_covered = int(progress["product_vt_symbol"].nunique()) if not progress.empty else 0
    hard_gates_passed = int(gates["passed"].sum())
    hard_gates_total = int(len(gates))
    promotion_allowed = False
    paper_selector_allowed = False
    trading_whitelist_allowed = False

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "p2_master_pit_append_gate_written_selector_locked",
        "promotion_allowed": promotion_allowed,
        "paper_selector_allowed": paper_selector_allowed,
        "trading_whitelist_allowed": trading_whitelist_allowed,
        "input_rows": int(len(run_ledger)),
        "append_rows": int(len(append_rows)),
        "duplicate_rows": int(len(duplicate_rows)),
        "rejected_rows": int(len(rejected)),
        "master_rows": int(len(combined)),
        "products_covered": products_covered,
        "min_pit_dates": min_pit_dates,
        "required_pit_dates_for_selector": REQUIRED_PIT_DATES_FOR_SELECTOR,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "summary": "Stage629 raw-hash monitor rows were appended to a stable master PIT ledger with dedupe and fail-closed selector locks.",
    }

    _write_chart(progress, source, gates, append_rows, duplicate_rows, rejected)
    _write_report(generated_at, run_ledger, append_rows, duplicate_rows, rejected, combined, progress, source, gates, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
