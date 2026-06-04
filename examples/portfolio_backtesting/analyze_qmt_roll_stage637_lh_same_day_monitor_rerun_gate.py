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
MODEL_TAG = "stage637_lh_same_day_monitor_rerun_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage637_lh_same_day_monitor_rerun_gate"

STAGE635_FETCH_LEDGER = (
    OUTPUT_DIR / "qmt_roll_stage635_lh_monthly_source_fetch_probe_fetch_ledger_stage635_lh_monthly_source_fetch_probe_v1.csv"
)
MASTER_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_lh_monthly_official_source_master_pit_ledger.csv"

RERUN_CANDIDATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rerun_candidate_{MODEL_TAG}.csv"
CLASSIFICATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_classification_{MODEL_TAG}.csv"
PRODUCT_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_SOURCE_ROWS = 2

REFERENCES = [
    "QuantConnect custom data look-ahead guidance: https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/reconciliation",
    "FactSet point-in-time database white paper: https://www.insight.factset.com/hubfs/Resources%20Section/White%20Papers/ID11996_point_in_time.pdf",
    "pyauth/tsp-client timestamp/hash attestation reference: https://github.com/pyauth/tsp-client",
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


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in [
        "line_id",
        "product_vt_symbol",
        "product_family",
        "source_name",
        "source_url",
        "final_url",
        "source_class",
        "received_at_local",
        "received_at_utc",
        "raw_sha256",
    ]:
        normalized[column] = _str(normalized, column)
    normalized["pit_date"] = normalized["received_at_utc"].str.slice(0, 10)
    normalized["pit_month"] = normalized["received_at_utc"].str.slice(0, 7)
    normalized["exact_dedupe_key"] = (
        normalized["product_vt_symbol"]
        + "||"
        + normalized["source_url"]
        + "||"
        + normalized["received_at_utc"]
        + "||"
        + normalized["raw_sha256"]
    )
    normalized["daily_source_key"] = (
        normalized["product_vt_symbol"]
        + "||"
        + normalized["source_url"]
        + "||"
        + normalized["pit_date"]
    )
    normalized["daily_hash_key"] = normalized["daily_source_key"] + "||" + normalized["raw_sha256"]
    return normalized


def _make_same_day_rerun_candidate(fetch_ledger: pd.DataFrame, generated_at: datetime) -> pd.DataFrame:
    frame = _normalize(fetch_ledger)
    # Simulate a same-calendar-day monitor rerun with a fresh collection timestamp.
    # It should not increase PIT sample depth even if exact received_at differs.
    rerun_utc = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rerun_local = _fmt_cst(generated_at)
    frame["received_at_local_original"] = frame["received_at_local"]
    frame["received_at_utc_original"] = frame["received_at_utc"]
    frame["received_at_local"] = rerun_local
    frame["received_at_utc"] = rerun_utc
    frame["row_id"] = _str(frame, "row_id") + "_same_day_rerun_candidate"
    return _normalize(frame)


def _classify(candidate: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    candidate = _normalize(candidate)
    master = _normalize(master)
    exact_keys = set(_str(master, "exact_dedupe_key")) if not master.empty else set()
    daily_source_keys = set(_str(master, "daily_source_key")) if not master.empty else set()
    daily_hash_keys = set(_str(master, "daily_hash_key")) if not master.empty else set()

    frame = candidate.copy()
    frame["exact_duplicate"] = frame["exact_dedupe_key"].isin(exact_keys).astype(int)
    frame["same_day_source_duplicate"] = frame["daily_source_key"].isin(daily_source_keys).astype(int)
    frame["same_day_hash_duplicate"] = frame["daily_hash_key"].isin(daily_hash_keys).astype(int)
    frame["strict_daily_append_allowed"] = (
        frame["exact_duplicate"].eq(0)
        & frame["same_day_source_duplicate"].eq(0)
        & _num(frame, "active_fetch_validated").eq(1)
        & _num(frame, "raw_sha256_present").eq(1)
        & _num(frame, "usable_for_history_selector").eq(0)
        & _num(frame, "paper_or_whitelist_allowed").eq(0)
    ).astype(int)
    frame["strict_selector_sample_allowed"] = 0
    frame["classification"] = np.select(
        [
            frame["exact_duplicate"].eq(1),
            frame["same_day_hash_duplicate"].eq(1),
            frame["same_day_source_duplicate"].eq(1),
            frame["strict_daily_append_allowed"].eq(1),
        ],
        [
            "exact_duplicate_hold",
            "same_day_same_hash_hold",
            "same_day_source_revision_hold",
            "new_pit_date_append_candidate",
        ],
        default="reject_or_manual_review",
    )
    frame["classification_note"] = np.where(
        frame["classification"].str.contains("same_day|exact", regex=True),
        "same day rerun cannot increase PIT date count or selector sample count",
        "new date append still needs master gate checks",
    )
    return frame


def _product_progress(master: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    master = _normalize(master)
    if master.empty:
        return pd.DataFrame()
    progress = master.groupby(["product_family", "product_vt_symbol"], as_index=False).agg(
        master_rows=("exact_dedupe_key", "count"),
        pit_dates=("pit_date", "nunique"),
        pit_months=("pit_month", "nunique"),
        source_classes=("source_class", "nunique"),
    )
    progress["same_day_rerun_candidate_rows"] = len(classification)
    progress["strict_daily_append_allowed_rows"] = int(_num(classification, "strict_daily_append_allowed").sum())
    progress["strict_selector_sample_allowed_rows"] = int(_num(classification, "strict_selector_sample_allowed").sum())
    progress["same_day_hold_rows"] = int(classification["classification"].astype(str).str.contains("same_day|exact", regex=True).sum())
    progress["pit_dates_after_strict_rerun"] = progress["pit_dates"] + progress["strict_daily_append_allowed_rows"].clip(upper=1)
    progress["status"] = "same_day_rerun_locked_selector_locked"
    return progress


def _gates(fetch_ledger: pd.DataFrame, master: pd.DataFrame, classification: pd.DataFrame, progress: pd.DataFrame) -> pd.DataFrame:
    strict_append = int(_num(classification, "strict_daily_append_allowed").sum()) if not classification.empty else 0
    selector_sample = int(_num(classification, "strict_selector_sample_allowed").sum()) if not classification.empty else 0
    same_day_hold = int(classification["classification"].astype(str).str.contains("same_day|exact", regex=True).sum()) if not classification.empty else 0
    pit_dates = int(progress["pit_dates"].max()) if not progress.empty else 0
    pit_after = int(progress["pit_dates_after_strict_rerun"].max()) if not progress.empty else 0
    rows = [
        {
            "gate": "stage635_fetch_ledger_present",
            "passed": int(len(fetch_ledger) >= REQUIRED_SOURCE_ROWS),
            "current": len(fetch_ledger),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Same-day rerun candidate is derived from Stage635 fetch rows.",
        },
        {
            "gate": "master_ledger_present",
            "passed": int(len(master) >= REQUIRED_SOURCE_ROWS),
            "current": len(master),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Stage636 master ledger must exist before rerun guard.",
        },
        {
            "gate": "rerun_candidate_rows_present",
            "passed": int(len(classification) >= REQUIRED_SOURCE_ROWS),
            "current": len(classification),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "We need both MOA and NAHS candidate rows.",
        },
        {
            "gate": "strict_daily_append_zero_for_same_day",
            "passed": int(strict_append == 0),
            "current": strict_append,
            "required": 0,
            "note": "Same-day reruns must not append new master rows.",
        },
        {
            "gate": "same_day_hold_rows_present",
            "passed": int(same_day_hold >= REQUIRED_SOURCE_ROWS),
            "current": same_day_hold,
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Same-day candidate rows should be held as duplicates/revisions.",
        },
        {
            "gate": "selector_sample_zero_for_same_day",
            "passed": int(selector_sample == 0),
            "current": selector_sample,
            "required": 0,
            "note": "Same-day reruns cannot count as selector samples.",
        },
        {
            "gate": "pit_date_count_unchanged",
            "passed": int(pit_after == pit_dates),
            "current": f"before={pit_dates},after={pit_after}",
            "required": "unchanged",
            "note": "Rerun guard must not increase unique PIT dates.",
        },
        {
            "gate": "pit_dates_below_selector_threshold",
            "passed": int(pit_after < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": pit_after,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "Selector remains locked.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(classification: pd.DataFrame, progress: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage637 lh same-day monitor rerun gate: same day does not inflate PIT samples", fontsize=15)

    ax = axes[0, 0]
    counts = classification["classification"].value_counts().rename_axis("classification").reset_index(name="count")
    ax.bar(counts["classification"], counts["count"], color="tab:orange")
    ax.set_title("Same-day rerun classification")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=15)
    for idx, value in enumerate(counts["count"]):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom")

    ax = axes[0, 1]
    if progress.empty:
        ax.text(0.5, 0.5, "No progress", ha="center", va="center")
        ax.set_axis_off()
    else:
        labels = ["current PIT dates", "after strict rerun", "selector threshold"]
        values = [
            int(progress["pit_dates"].max()),
            int(progress["pit_dates_after_strict_rerun"].max()),
            REQUIRED_PIT_DATES_FOR_SELECTOR,
        ]
        ax.bar(labels, values, color=["tab:blue", "tab:green", "tab:red"])
        ax.set_title("PIT date count must not change on same-day rerun")
        ax.set_ylabel("dates")
        ax.tick_params(axis="x", rotation=12)
        for idx, value in enumerate(values):
            ax.text(idx, value, str(value), ha="center", va="bottom")

    ax = axes[1, 0]
    if classification.empty:
        ax.text(0.5, 0.5, "No candidates", ha="center", va="center")
        ax.set_axis_off()
    else:
        metrics = ["exact_duplicate", "same_day_source_duplicate", "same_day_hash_duplicate", "strict_daily_append_allowed"]
        values = [int(_num(classification, metric).sum()) for metric in metrics]
        ax.bar(metrics, values, color=["tab:gray", "tab:orange", "tab:purple", "tab:green"])
        ax.set_title("Exact vs daily dedupe checks")
        ax.set_ylabel("rows")
        ax.tick_params(axis="x", rotation=18)
        for idx, value in enumerate(values):
            ax.text(idx, value, str(value), ha="center", va="bottom")

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green means rerun lock works")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    candidate: pd.DataFrame,
    classification: pd.DataFrame,
    progress: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage637 lh Same-Day Monitor Rerun Gate Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: same-day rerun guard audit; no network fetch, no master append, no selector, no paper, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "Point-in-time data should represent what was actually available to the strategy at a collection time. Re-running the same source repeatedly on the same calendar date can create more rows without creating more independent information dates, so selector sample depth must be based on PIT dates rather than raw row count.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- rerun candidate rows: `{len(candidate)}`",
        f"- strict daily append rows: `{decision['strict_daily_append_rows']}`",
        f"- same-day hold rows: `{decision['same_day_hold_rows']}`",
        f"- selector sample rows: `{decision['selector_sample_rows']}`",
        f"- PIT dates before: `{decision['pit_dates_before']}`",
        f"- PIT dates after strict rerun: `{decision['pit_dates_after_strict_rerun']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Classification",
        "",
        _md_table(
            classification,
            columns=[
                "source_name",
                "source_class",
                "received_at_utc_original",
                "received_at_utc",
                "exact_duplicate",
                "same_day_source_duplicate",
                "same_day_hash_duplicate",
                "strict_daily_append_allowed",
                "strict_selector_sample_allowed",
                "classification",
                "classification_note",
            ],
        ),
        "",
        "## Product Progress",
        "",
        _md_table(progress),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- `lh.DCE` 同日重复采集不能增加 master 行，也不能增加 selector 样本数。",
        "- 这补上 Stage636 exact dedupe 的剩余风险：即使 received_at 不同，只要是同一 source 同一 PIT 日期，也要 hold。",
        "- 后续真正有价值的是新自然日采集，而不是同日重复运行。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fetch_ledger = _read_csv(STAGE635_FETCH_LEDGER)
    master = _read_csv(MASTER_LEDGER_PATH)
    if fetch_ledger.empty:
        raise FileNotFoundError(f"missing or empty fetch ledger: {STAGE635_FETCH_LEDGER}")
    if master.empty:
        raise FileNotFoundError(f"missing or empty master ledger: {MASTER_LEDGER_PATH}")

    candidate = _make_same_day_rerun_candidate(fetch_ledger, generated_at)
    classification = _classify(candidate, master)
    progress = _product_progress(master, classification)
    gates = _gates(fetch_ledger, master, classification, progress)

    candidate.to_csv(RERUN_CANDIDATE_PATH, index=False, encoding="utf-8-sig")
    classification.to_csv(CLASSIFICATION_PATH, index=False, encoding="utf-8-sig")
    progress.to_csv(PRODUCT_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    strict_daily_append_rows = int(_num(classification, "strict_daily_append_allowed").sum())
    same_day_hold_rows = int(classification["classification"].astype(str).str.contains("same_day|exact", regex=True).sum())
    selector_sample_rows = int(_num(classification, "strict_selector_sample_allowed").sum())
    pit_dates_before = int(progress["pit_dates"].max()) if not progress.empty else 0
    pit_dates_after = int(progress["pit_dates_after_strict_rerun"].max()) if not progress.empty else 0
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "lh_same_day_monitor_rerun_locked_selector_locked",
        "rerun_candidate_rows": int(len(candidate)),
        "strict_daily_append_rows": strict_daily_append_rows,
        "same_day_hold_rows": same_day_hold_rows,
        "selector_sample_rows": selector_sample_rows,
        "pit_dates_before": pit_dates_before,
        "pit_dates_after_strict_rerun": pit_dates_after,
        "required_pit_dates_for_selector": REQUIRED_PIT_DATES_FOR_SELECTOR,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "classification_path": str(CLASSIFICATION_PATH),
        "chart_path": str(CHART_PATH),
    }

    _write_chart(classification, progress, gates)
    _write_report(generated_at, candidate, classification, progress, gates, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
