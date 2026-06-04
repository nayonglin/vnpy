from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
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
MODEL_TAG = "stage646_cj_warehouse_master_pit_append_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage646_cj_warehouse_master_pit_append_gate"

STAGE645_FETCH_LEDGER = (
    OUTPUT_DIR
    / "qmt_roll_stage645_cj_czce_official_warehouse_source_probe_fetch_ledger_stage645_cj_czce_official_warehouse_source_probe_v1.csv"
)
MASTER_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_cj_czce_warehouse_master_pit_ledger.csv"

APPEND_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_append_rows_{MODEL_TAG}.csv"
DUPLICATE_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_duplicate_rows_{MODEL_TAG}.csv"
REJECTED_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rejected_rows_{MODEL_TAG}.csv"
PRODUCT_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_SOURCE_ROWS = 6
REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_EPISODES = 3

REFERENCES = [
    "Point-in-time data and look-ahead bias: https://www.pfolio.io/academy/look-ahead-bias",
    "AKShare CZCE warehouse receipt function: https://deepwiki.com/akfamily/akshare/4.2-futures-and-commodities",
    "AKShare GitHub: https://github.com/akfamily/akshare",
    "CZCE warehouse receipt daily page: https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
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
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


def _read_csv(path: Path, required: bool = False) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _parse_received_at_cst(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    cleaned = text.replace(" CST", "")
    try:
        cst = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
    except ValueError:
        return "", ""
    utc = cst.astimezone(timezone.utc)
    return cst.strftime("%Y-%m-%d"), utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_id(row: pd.Series) -> str:
    payload = "||".join(
        [
            str(row.get("product_vt_symbol", "")),
            str(row.get("official_date", "")),
            str(row.get("source_url", "")),
            str(row.get("raw_sha256", "")),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    required_defaults: dict[str, Any] = {
        "line_id": LINE_ID,
        "product_vt_symbol": "",
        "product_family": "watch_jujube",
        "source_name": "",
        "source_authority": "",
        "source_class": "official_exchange_daily_warehouse_receipt",
        "source_url": "",
        "probe_date": "",
        "official_date": "",
        "received_at_cst": "",
        "received_pit_date": "",
        "received_at_utc": "",
        "fetch_status": "",
        "cj_rows": 0,
        "warehouse_count": 0,
        "total_receipts": 0.0,
        "daily_change": 0.0,
        "effective_forecast": 0.0,
        "raw_sha256": "",
        "raw_sha256_present": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "selector_allowed_now": 0,
        "paper_or_whitelist_allowed_now": 0,
        "trading_whitelist_allowed_now": 0,
    }
    for column, default in required_defaults.items():
        if column not in normalized.columns:
            normalized[column] = default

    if "official_date" not in frame.columns or _str(normalized, "official_date").eq("").all():
        normalized["official_date"] = _str(normalized, "probe_date").str.replace("-", "", regex=False)
    normalized["official_date"] = _str(normalized, "official_date").str.replace("-", "", regex=False).str.slice(0, 8)

    parsed = normalized["received_at_cst"].map(_parse_received_at_cst)
    if "received_pit_date" not in frame.columns or _str(normalized, "received_pit_date").eq("").all():
        normalized["received_pit_date"] = parsed.map(lambda item: item[0])
    if "received_at_utc" not in frame.columns or _str(normalized, "received_at_utc").eq("").all():
        normalized["received_at_utc"] = parsed.map(lambda item: item[1])

    for column in [
        "line_id",
        "product_vt_symbol",
        "product_family",
        "source_name",
        "source_authority",
        "source_class",
        "source_url",
        "official_date",
        "received_at_cst",
        "received_pit_date",
        "received_at_utc",
        "fetch_status",
        "raw_sha256",
    ]:
        normalized[column] = _str(normalized, column)

    for column in [
        "cj_rows",
        "warehouse_count",
        "total_receipts",
        "daily_change",
        "effective_forecast",
        "raw_sha256_present",
        "usable_for_forward_monitor",
        "usable_for_history_selector",
        "selector_allowed_now",
        "paper_or_whitelist_allowed_now",
        "trading_whitelist_allowed_now",
    ]:
        normalized[column] = _num(normalized, column)

    normalized["row_id"] = normalized.apply(_row_id, axis=1)
    normalized["dedupe_key"] = (
        normalized["product_vt_symbol"]
        + "||"
        + normalized["official_date"]
        + "||"
        + normalized["source_url"]
        + "||"
        + normalized["raw_sha256"]
    )
    normalized["master_appended_at_cst"] = _fmt_cst(_now_cst())
    normalized["master_model_tag"] = MODEL_TAG
    return normalized


def _build_append_sets(
    fetch_ledger: pd.DataFrame, existing_master: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = _normalize(fetch_ledger)
    reject_reasons: list[list[str]] = []
    for _, row in frame.iterrows():
        reasons: list[str] = []
        if row["line_id"] != LINE_ID:
            reasons.append("wrong_line_id")
        if row["product_vt_symbol"] != "CJ.CZCE":
            reasons.append("not_cj_product")
        if row["fetch_status"] != "ok":
            reasons.append("fetch_status_not_ok")
        if not row["source_url"]:
            reasons.append("missing_source_url")
        if not row["official_date"] or len(str(row["official_date"])) != 8:
            reasons.append("invalid_official_date")
        if not row["received_at_cst"] or not row["received_at_utc"] or not row["received_pit_date"]:
            reasons.append("missing_received_at")
        if not row["raw_sha256"]:
            reasons.append("missing_raw_sha256")
        if int(row["raw_sha256_present"]) != 1:
            reasons.append("raw_sha256_present_not_1")
        if int(row["usable_for_forward_monitor"]) != 1:
            reasons.append("forward_monitor_not_enabled")
        if int(row["usable_for_history_selector"]) != 0:
            reasons.append("history_selector_not_locked")
        if int(row["selector_allowed_now"]) != 0:
            reasons.append("selector_not_locked")
        if int(row["paper_or_whitelist_allowed_now"]) != 0:
            reasons.append("paper_or_whitelist_not_locked")
        if int(row["trading_whitelist_allowed_now"]) != 0:
            reasons.append("trading_whitelist_not_locked")
        if float(row["total_receipts"]) <= 0:
            reasons.append("total_receipts_not_positive")
        if float(row["cj_rows"]) <= 0:
            reasons.append("missing_cj_rows")
        if "official" not in row["source_authority"]:
            reasons.append("source_authority_not_official_wrapped")
        reject_reasons.append(reasons)

    frame["reject_reason"] = [";".join(item) for item in reject_reasons]
    eligible = frame[frame["reject_reason"].eq("")].copy()
    rejected = frame[~frame["reject_reason"].eq("")].copy()

    existing = _normalize(existing_master) if not existing_master.empty else pd.DataFrame(columns=frame.columns)
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
        combined = _normalize(combined)
        combined = combined.drop_duplicates("dedupe_key", keep="first")
        combined = combined.sort_values(["official_date", "received_at_utc", "source_url"]).reset_index(drop=True)
    return append_rows, duplicate_rows, rejected, combined


def _product_progress(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame()
    frame = _normalize(master)
    progress = frame.groupby(["product_family", "product_vt_symbol"], as_index=False).agg(
        master_rows=("dedupe_key", "count"),
        official_dates=("official_date", "nunique"),
        collection_pit_dates=("received_pit_date", "nunique"),
        latest_official_date=("official_date", "max"),
        latest_total_receipts=("total_receipts", "last"),
        latest_effective_forecast=("effective_forecast", "last"),
        raw_hash_rows=("raw_sha256_present", "sum"),
        selector_rows=("usable_for_history_selector", "sum"),
        paper_or_whitelist_rows=("paper_or_whitelist_allowed_now", "sum"),
        trading_whitelist_rows=("trading_whitelist_allowed_now", "sum"),
    )
    progress["progress_pct_to_selector_by_collection_date"] = (
        np.minimum(progress["collection_pit_dates"] / REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR, 1.0) * 100
    ).round(4)
    progress["status"] = np.where(
        progress["collection_pit_dates"].ge(REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR),
        "collection_pit_threshold_met_still_needs_episode_tca",
        "official_dates_backfill_locked_collection_pit_accumulating",
    )
    return progress


def _gates(
    fetch_ledger: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
    combined: pd.DataFrame,
    progress: pd.DataFrame,
    second_append_rows: pd.DataFrame,
    second_duplicate_rows: pd.DataFrame,
) -> pd.DataFrame:
    if progress.empty:
        official_dates = 0
        collection_dates = 0
        selector_rows = 0
        paper_rows = 0
        trading_rows = 0
    else:
        row = progress.iloc[0]
        official_dates = int(row["official_dates"])
        collection_dates = int(row["collection_pit_dates"])
        selector_rows = int(row["selector_rows"])
        paper_rows = int(row["paper_or_whitelist_rows"])
        trading_rows = int(row["trading_whitelist_rows"])
    raw_hash_rows = int(_num(combined, "raw_sha256_present").sum()) if not combined.empty else 0
    rows = [
        {
            "gate": "stage645_fetch_ledger_present",
            "passed": int(len(fetch_ledger) >= REQUIRED_SOURCE_ROWS),
            "current": len(fetch_ledger),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Stage645 fetch ledger is the only input.",
        },
        {
            "gate": "append_or_duplicate_ok",
            "passed": int(len(append_rows) > 0 or (len(duplicate_rows) >= REQUIRED_SOURCE_ROWS and rejected.empty)),
            "current": f"append={len(append_rows)}, duplicate={len(duplicate_rows)}",
            "required": "append>0 or duplicate>=6",
            "note": "First run appends; later reruns must become duplicates.",
        },
        {
            "gate": "rejected_rows_zero",
            "passed": int(rejected.empty),
            "current": len(rejected),
            "required": 0,
            "note": "Rows missing hash/time/schema/lock discipline must be rejected.",
        },
        {
            "gate": "idempotent_rerun_no_new_rows",
            "passed": int(second_append_rows.empty),
            "current": len(second_append_rows),
            "required": 0,
            "note": "Internal rerun against just-written master must not append again.",
        },
        {
            "gate": "idempotent_duplicate_rows_present",
            "passed": int(len(second_duplicate_rows) >= REQUIRED_SOURCE_ROWS),
            "current": len(second_duplicate_rows),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Internal rerun should recognize all Stage645 rows as duplicates.",
        },
        {
            "gate": "master_rows_present",
            "passed": int(len(combined) >= REQUIRED_SOURCE_ROWS),
            "current": len(combined),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Stable master ledger should retain CJ warehouse source rows.",
        },
        {
            "gate": "official_dates_retained",
            "passed": int(official_dates >= REQUIRED_SOURCE_ROWS),
            "current": official_dates,
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Official warehouse dates are retained as event dates.",
        },
        {
            "gate": "raw_hash_rows_present",
            "passed": int(raw_hash_rows >= REQUIRED_SOURCE_ROWS),
            "current": raw_hash_rows,
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "All master rows must retain raw source hashes.",
        },
        {
            "gate": "collection_pit_dates_reach_20",
            "passed": int(collection_dates >= REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR),
            "current": collection_dates,
            "required": f">={REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR}",
            "note": "Historical official dates do not count as forward collection PIT dates.",
        },
        {
            "gate": "independent_episodes_reach_3",
            "passed": 0,
            "current": 0,
            "required": f">={REQUIRED_EPISODES}",
            "note": "No CJ outcome episodes yet.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "Master rows must not enter selector before PIT threshold.",
        },
        {
            "gate": "paper_trading_whitelist_rows_zero",
            "passed": int(paper_rows == 0 and trading_rows == 0),
            "current": f"paper={paper_rows}, trading={trading_rows}",
            "required": "0/0",
            "note": "No paper or trading whitelist rows allowed.",
        },
        {
            "gate": "fail_closed_discipline",
            "passed": 1,
            "current": "selector_locked",
            "required": "selector_locked",
            "note": "Appending PIT source evidence does not promote trading.",
        },
    ]
    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 50) -> str:
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


def _write_chart(
    combined: pd.DataFrame,
    progress: pd.DataFrame,
    gates: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
    second_append_rows: pd.DataFrame,
) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Stage646 CJ warehouse master PIT gate: official dates kept, collection PIT locked", fontsize=14, weight="bold")

    frame = _normalize(combined) if not combined.empty else pd.DataFrame()
    ax = axes[0, 0]
    if frame.empty:
        ax.text(0.5, 0.5, "No master rows", ha="center", va="center")
        ax.set_axis_off()
    else:
        view = frame.sort_values("official_date")
        ax.bar(view["official_date"], view["total_receipts"], color="#4a90e2", label="warehouse receipts")
        ax.plot(view["official_date"], view["effective_forecast"], color="#f5a623", marker="o", label="effective forecast")
        ax.set_title("Official CZCE warehouse dates retained in master")
        ax.set_ylabel("contracts / receipts")
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=8)

    ax = axes[0, 1]
    if progress.empty:
        ax.text(0.5, 0.5, "No progress", ha="center", va="center")
        ax.set_axis_off()
    else:
        row = progress.iloc[0]
        metrics = pd.Series(
            {
                "official dates": row["official_dates"],
                "collection PIT dates": row["collection_pit_dates"],
                "raw hashes": row["raw_hash_rows"],
                "selector rows": row["selector_rows"],
            }
        )
        colors = ["#66bb6a", "#f0ad4e", "#66bb6a", "#d9534f"]
        ax.bar(metrics.index, metrics.values, color=colors)
        ax.axhline(REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR, color="#d9534f", linestyle="--", linewidth=1, label="20 collection PIT selector gate")
        ax.set_title("Source depth: official date is not collection PIT")
        ax.tick_params(axis="x", rotation=20)
        ax.legend(fontsize=8)
        for idx, value in enumerate(metrics.values):
            ax.text(idx, max(float(value), 0.1), f"{int(value)}", ha="center", va="bottom", fontsize=8)

    ax = axes[1, 0]
    result = pd.DataFrame(
        {
            "bucket": ["append rows", "already duplicate rows", "rejected rows", "rerun new rows"],
            "count": [len(append_rows), len(duplicate_rows), len(rejected), len(second_append_rows)],
        }
    )
    ax.bar(result["bucket"], result["count"], color=["#66bb6a", "#f0ad4e", "#d9534f", "#888888"])
    ax.set_title("Append and idempotency result")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=15)
    for idx, value in enumerate(result["count"]):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom")

    ax = axes[1, 1]
    colors = ["#66bb6a" if int(item) == 1 else "#d9534f" for item in gates["passed"]]
    ax.barh(gates["gate"], [1.0] * len(gates), color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates")
    ax.tick_params(axis="y", labelsize=8)
    for idx, row in gates.iterrows():
        ax.text(0.02, idx, "PASS" if row["passed"] else "FAIL", va="center", ha="left", fontsize=8, color="white", weight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    fetch_ledger: pd.DataFrame,
    append_rows: pd.DataFrame,
    duplicate_rows: pd.DataFrame,
    rejected: pd.DataFrame,
    combined: pd.DataFrame,
    progress: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage646 CJ Warehouse Master PIT Append Gate Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- input_fetch_ledger: `{STAGE645_FETCH_LEDGER}`",
        f"- stable_master_ledger: `{MASTER_LEDGER_PATH}`",
        "- stage nature: master PIT append gate only; no strategy replay, no selector, no paper, no whitelist, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "- PIT discipline requires using when the data was collected/available, not merely the historical official date inside the file.",
        "- Therefore this stage keeps `official_date` for source/event context, but counts selector readiness by `received_pit_date`.",
        "- AKShare/CZCE gives executable warehouse receipt rows; the master ledger adds timestamp/hash/dedupe/fail-closed controls that the raw source wrapper does not provide by itself.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- input rows: `{len(fetch_ledger)}`",
        f"- append rows: `{len(append_rows)}`",
        f"- duplicate rows: `{len(duplicate_rows)}`",
        f"- rejected rows: `{len(rejected)}`",
        f"- master rows: `{len(combined)}`",
        f"- official dates in master: `{decision['official_dates']}`",
        f"- collection PIT dates in master: `{decision['collection_pit_dates']}`",
        f"- raw hash rows in master: `{decision['raw_hash_rows']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/trading whitelist rows: `{decision['paper_or_whitelist_rows']}/{decision['trading_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Product Progress",
        "",
        _md_table(progress),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Master Ledger Preview",
        "",
        _md_table(
            combined,
            [
                "official_date",
                "received_pit_date",
                "product_vt_symbol",
                "total_receipts",
                "daily_change",
                "effective_forecast",
                "raw_sha256_present",
                "usable_for_history_selector",
                "selector_allowed_now",
            ],
        ),
        "",
        "## Rejected Rows",
        "",
        _md_table(rejected[["row_id", "official_date", "product_vt_symbol", "fetch_status", "reject_reason"]] if not rejected.empty else rejected),
        "",
        "## Interpretation",
        "",
        "- This stage deliberately tightens Stage645: six official warehouse dates are retained, but they were collected in one run, so they count as one collection PIT date.",
        "- Idempotency is closed: rerunning the same Stage645 ledger against the just-written master appends zero new rows.",
        "- The branch remains monitor-only. More historical official dates can help parser validation, but cannot unlock selector until forward collection dates accumulate.",
        "",
        "## Next Steps",
        "",
        "- Run the CJ collector on new natural days only; do not backfill into selector samples.",
        "- After at least 20 collection PIT dates, run a fixed 20/63/126 outcome schedule.",
        "- Keep searching for an independent monthly/seasonal official source; warehouse receipts alone are not sufficient alpha evidence.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fetch_ledger = _read_csv(STAGE645_FETCH_LEDGER, required=True)
    existing_master = _read_csv(MASTER_LEDGER_PATH)
    append_rows, duplicate_rows, rejected, combined = _build_append_sets(fetch_ledger, existing_master)
    combined.to_csv(MASTER_LEDGER_PATH, index=False, encoding="utf-8-sig")

    second_append_rows, second_duplicate_rows, second_rejected, second_combined = _build_append_sets(fetch_ledger, combined)
    if len(second_combined) != len(combined):
        raise RuntimeError("internal idempotency rerun changed master row count")

    append_rows.to_csv(APPEND_ROWS_PATH, index=False, encoding="utf-8-sig")
    duplicate_rows.to_csv(DUPLICATE_ROWS_PATH, index=False, encoding="utf-8-sig")
    rejected.to_csv(REJECTED_ROWS_PATH, index=False, encoding="utf-8-sig")

    progress = _product_progress(combined)
    gates = _gates(fetch_ledger, append_rows, duplicate_rows, rejected, combined, progress, second_append_rows, second_duplicate_rows)
    progress.to_csv(PRODUCT_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    if progress.empty:
        official_dates = 0
        collection_dates = 0
        selector_rows = 0
        paper_rows = 0
        trading_rows = 0
    else:
        row = progress.iloc[0]
        official_dates = int(row["official_dates"])
        collection_dates = int(row["collection_pit_dates"])
        selector_rows = int(row["selector_rows"])
        paper_rows = int(row["paper_or_whitelist_rows"])
        trading_rows = int(row["trading_whitelist_rows"])
    raw_hash_rows = int(_num(combined, "raw_sha256_present").sum()) if not combined.empty else 0

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "cj_warehouse_master_pit_append_gate_written_collection_pit_one_selector_locked",
        "input_rows": int(len(fetch_ledger)),
        "append_rows": int(len(append_rows)),
        "duplicate_rows": int(len(duplicate_rows)),
        "rejected_rows": int(len(rejected)),
        "idempotent_rerun_append_rows": int(len(second_append_rows)),
        "idempotent_rerun_duplicate_rows": int(len(second_duplicate_rows)),
        "idempotent_rerun_rejected_rows": int(len(second_rejected)),
        "master_rows": int(len(combined)),
        "official_dates": official_dates,
        "collection_pit_dates": collection_dates,
        "required_collection_pit_dates_for_selector": REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR,
        "raw_hash_rows": raw_hash_rows,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "trading_whitelist_rows": trading_rows,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "master_ledger_path": str(MASTER_LEDGER_PATH),
        "chart_path": str(CHART_PATH),
    }

    _write_chart(combined, progress, gates, append_rows, duplicate_rows, rejected, second_append_rows)
    _write_report(generated_at, fetch_ledger, append_rows, duplicate_rows, rejected, combined, progress, gates, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
