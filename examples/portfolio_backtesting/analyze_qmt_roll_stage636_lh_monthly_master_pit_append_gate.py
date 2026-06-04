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
MODEL_TAG = "stage636_lh_monthly_master_pit_append_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage636_lh_monthly_master_pit_append_gate"

STAGE635_FETCH_LEDGER = (
    OUTPUT_DIR / "qmt_roll_stage635_lh_monthly_source_fetch_probe_fetch_ledger_stage635_lh_monthly_source_fetch_probe_v1.csv"
)
MASTER_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_lh_monthly_official_source_master_pit_ledger.csv"

APPEND_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_append_rows_{MODEL_TAG}.csv"
DUPLICATE_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_duplicate_rows_{MODEL_TAG}.csv"
REJECTED_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rejected_rows_{MODEL_TAG}.csv"
PRODUCT_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_progress_{MODEL_TAG}.csv"
SOURCE_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_MONTHS_FOR_SELECTOR = 12
REQUIRED_SOURCE_ROWS = 2

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
    "release_period",
    "monitor_frequency",
    "http_status",
    "fetch_status",
    "response_bytes",
    "raw_sha256",
    "raw_sha256_present",
    "keyword_hit_count",
    "expected_field_count",
    "extracted_expected_field_count",
    "extracted_fields_json",
    "active_fetch_validated",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "event_signal_ready",
    "paper_or_whitelist_allowed",
    "point_in_time_rule",
]

REFERENCES = [
    "MOA live hog monthly data example: https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/",
    "NAHS monthly livestock/feed price bulletin: https://www.nahs.org.cn/jcyj/scxs/202605/t20260519_472251.htm",
    "Glassnode point-in-time metrics concept: https://docs.glassnode.com/data/point-in-time-metrics",
    "vBase timestamp/hash verification concept: https://docs.vbase.com/overview/what-vbase-verifies",
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for field in REQUIRED_FIELDS:
        if field not in normalized.columns:
            normalized[field] = ""

    for column in [
        "line_id",
        "product_vt_symbol",
        "product_family",
        "source_name",
        "source_url",
        "final_url",
        "source_authority",
        "source_class",
        "release_period",
        "received_at_local",
        "received_at_utc",
        "raw_sha256",
        "extracted_fields_json",
    ]:
        normalized[column] = _str(normalized, column)

    normalized["pit_date"] = normalized["received_at_utc"].str.slice(0, 10)
    normalized["pit_month"] = normalized["received_at_utc"].str.slice(0, 7)
    normalized["dedupe_key"] = (
        normalized["product_vt_symbol"]
        + "||"
        + normalized["source_url"]
        + "||"
        + normalized["received_at_utc"]
        + "||"
        + normalized["raw_sha256"]
    )
    normalized["master_appended_at_cst"] = _fmt_cst(_now_cst())
    normalized["master_model_tag"] = MODEL_TAG
    return normalized


def _field_json_valid(value: str) -> bool:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and len(parsed) >= 2


def _build_append_sets(fetch_ledger: pd.DataFrame, existing_master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = _normalize(fetch_ledger)
    reject_reasons: list[list[str]] = []
    for _, row in frame.iterrows():
        reasons: list[str] = []
        if row["line_id"] != LINE_ID:
            reasons.append("wrong_line_id")
        if row["product_vt_symbol"] != "lh.DCE":
            reasons.append("not_lh_product")
        if not row["source_url"] or not row["final_url"]:
            reasons.append("missing_source_or_final_url")
        if not row["received_at_utc"] or not row["received_at_local"]:
            reasons.append("missing_received_at")
        if not row["raw_sha256"]:
            reasons.append("missing_raw_sha256")
        if int(float(row.get("raw_sha256_present", 0) or 0)) != 1:
            reasons.append("raw_sha256_present_not_1")
        if int(float(row.get("active_fetch_validated", 0) or 0)) != 1:
            reasons.append("active_fetch_not_validated")
        if int(float(row.get("usable_for_forward_monitor", 0) or 0)) != 1:
            reasons.append("forward_monitor_not_enabled")
        if int(float(row.get("usable_for_history_selector", 0) or 0)) != 0:
            reasons.append("history_selector_not_locked")
        if int(float(row.get("event_signal_ready", 0) or 0)) != 0:
            reasons.append("event_signal_not_locked")
        if int(float(row.get("paper_or_whitelist_allowed", 0) or 0)) != 0:
            reasons.append("paper_or_whitelist_not_locked")
        if int(float(row.get("extracted_expected_field_count", 0) or 0)) < 2:
            reasons.append("insufficient_extracted_fields")
        if not _field_json_valid(str(row.get("extracted_fields_json", ""))):
            reasons.append("invalid_extracted_fields_json")
        if "monthly" not in row["source_class"]:
            reasons.append("not_monthly_source_class")
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
        combined = combined.sort_values(["received_at_utc", "source_name"]).reset_index(drop=True)
    return append_rows, duplicate_rows, rejected, combined


def _product_progress(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame()
    frame = _normalize(master)
    frame["active_fetch_validated"] = _num(frame, "active_fetch_validated")
    frame["raw_sha256_present"] = _num(frame, "raw_sha256_present")
    frame["extracted_expected_field_count"] = _num(frame, "extracted_expected_field_count")
    frame["usable_for_history_selector"] = _num(frame, "usable_for_history_selector")
    frame["paper_or_whitelist_allowed"] = _num(frame, "paper_or_whitelist_allowed")
    progress = frame.groupby(["product_family", "product_vt_symbol"], as_index=False).agg(
        master_rows=("dedupe_key", "count"),
        pit_dates=("pit_date", "nunique"),
        pit_months=("pit_month", "nunique"),
        source_classes=("source_class", "nunique"),
        active_fetch_validated_rows=("active_fetch_validated", "sum"),
        raw_hash_rows=("raw_sha256_present", "sum"),
        extracted_expected_field_rows=("extracted_expected_field_count", "sum"),
        selector_rows=("usable_for_history_selector", "sum"),
        paper_or_whitelist_rows=("paper_or_whitelist_allowed", "sum"),
    )
    progress["progress_pct"] = (
        np.minimum(progress["pit_dates"] / REQUIRED_PIT_DATES_FOR_SELECTOR, 1.0) * 50
        + np.minimum(progress["pit_months"] / REQUIRED_MONTHS_FOR_SELECTOR, 1.0) * 25
        + np.minimum(progress["source_classes"] / REQUIRED_SOURCE_ROWS, 1.0) * 15
        + np.minimum(progress["raw_hash_rows"] / REQUIRED_SOURCE_ROWS, 1.0) * 10
    ).round(4)
    progress["status"] = np.where(
        progress["pit_dates"].ge(REQUIRED_PIT_DATES_FOR_SELECTOR) & progress["pit_months"].ge(REQUIRED_MONTHS_FOR_SELECTOR),
        "pit_threshold_met_still_needs_episode_tca",
        "accumulating_lh_pit_evidence_selector_locked",
    )
    return progress


def _source_progress(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame()
    frame = _normalize(master)
    frame["response_bytes"] = _num(frame, "response_bytes")
    frame["extracted_expected_field_count"] = _num(frame, "extracted_expected_field_count")
    source = frame.groupby(["source_name", "source_authority", "source_class"], as_index=False).agg(
        rows=("dedupe_key", "count"),
        pit_dates=("pit_date", "nunique"),
        raw_hash_rows=("raw_sha256", lambda series: int(series.astype(str).str.len().gt(0).sum())),
        total_bytes=("response_bytes", "sum"),
        extracted_expected_field_rows=("extracted_expected_field_count", "sum"),
    )
    return source.sort_values(["rows", "source_name"], ascending=[False, True]).reset_index(drop=True)


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
    master_rows = int(len(combined))
    active_fetch_rows = int(_num(combined, "active_fetch_validated").sum()) if not combined.empty else 0
    raw_hash_rows = int(_num(combined, "raw_sha256_present").sum()) if not combined.empty else 0
    extracted_rows = int(_num(combined, "extracted_expected_field_count").sum()) if not combined.empty else 0
    pit_dates = int(progress["pit_dates"].max()) if not progress.empty else 0
    selector_rows = int(progress["selector_rows"].max()) if not progress.empty else 0
    paper_rows = int(progress["paper_or_whitelist_rows"].max()) if not progress.empty else 0
    rows = [
        {
            "gate": "stage635_fetch_ledger_present",
            "passed": int(len(fetch_ledger) >= REQUIRED_SOURCE_ROWS),
            "current": len(fetch_ledger),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Stage635 official monthly fetch rows are the only input.",
        },
        {
            "gate": "append_or_duplicate_ok",
            "passed": int(len(append_rows) > 0 or (len(duplicate_rows) >= REQUIRED_SOURCE_ROWS and rejected.empty)),
            "current": f"append={len(append_rows)},duplicate={len(duplicate_rows)}",
            "required": "append>0 or duplicate>=2",
            "note": "First run appends; later reruns must become duplicates.",
        },
        {
            "gate": "rejected_rows_zero",
            "passed": int(rejected.empty),
            "current": len(rejected),
            "required": 0,
            "note": "Rows missing hash/time/schema or lock discipline must be rejected.",
        },
        {
            "gate": "idempotent_rerun_no_new_rows",
            "passed": int(second_append_rows.empty),
            "current": len(second_append_rows),
            "required": 0,
            "note": "Internal rerun against the just-written master must not append again.",
        },
        {
            "gate": "idempotent_rerun_duplicate_rows_present",
            "passed": int(len(second_duplicate_rows) >= REQUIRED_SOURCE_ROWS),
            "current": len(second_duplicate_rows),
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Internal rerun should recognize both Stage635 rows as duplicates.",
        },
        {
            "gate": "master_rows_present",
            "passed": int(master_rows >= REQUIRED_SOURCE_ROWS),
            "current": master_rows,
            "required": f">={REQUIRED_SOURCE_ROWS}",
            "note": "Stable master ledger should hold at least the two official monthly rows.",
        },
        {
            "gate": "active_fetch_and_hash_rows_present",
            "passed": int(active_fetch_rows >= REQUIRED_SOURCE_ROWS and raw_hash_rows >= REQUIRED_SOURCE_ROWS),
            "current": f"fetch={active_fetch_rows},hash={raw_hash_rows}",
            "required": f">={REQUIRED_SOURCE_ROWS}/>={REQUIRED_SOURCE_ROWS}",
            "note": "Master rows must retain validated fetch and raw hash evidence.",
        },
        {
            "gate": "field_schema_rows_present",
            "passed": int(extracted_rows >= 4),
            "current": extracted_rows,
            "required": ">=4",
            "note": "Parsed field JSON exists for audit, not selector use.",
        },
        {
            "gate": "pit_dates_below_selector_threshold",
            "passed": int(pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": pit_dates,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "Fail-closed: one date cannot unlock selector.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "Master PIT rows must not enter history selector.",
        },
        {
            "gate": "paper_whitelist_rows_zero",
            "passed": int(paper_rows == 0),
            "current": paper_rows,
            "required": 0,
            "note": "No paper or trading whitelist rows are allowed.",
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
    second_append_rows: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage636 lh monthly master PIT append gate: evidence accumulates, selector locked", fontsize=15)

    ax = axes[0, 0]
    if progress.empty:
        ax.text(0.5, 0.5, "No product progress", ha="center", va="center")
        ax.set_axis_off()
    else:
        metrics = ["pit_dates", "pit_months", "source_classes", "active_fetch_validated_rows", "raw_hash_rows"]
        x = np.arange(len(metrics))
        values = [float(progress.iloc[0][metric]) for metric in metrics]
        ax.bar(x, values, color=["tab:blue", "tab:orange", "tab:green", "tab:purple", "tab:cyan"])
        ax.axhline(REQUIRED_PIT_DATES_FOR_SELECTOR, color="tab:red", linestyle="--", linewidth=1, label="20 date selector gate")
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, rotation=20, ha="right")
        ax.set_title("lh PIT progress")
        ax.set_ylabel("count")
        ax.legend(loc="upper right", fontsize=8)

    ax = axes[0, 1]
    if source.empty:
        ax.text(0.5, 0.5, "No source rows", ha="center", va="center")
        ax.set_axis_off()
    else:
        view = source.sort_values("total_bytes", ascending=True)
        y = np.arange(len(view))
        ax.barh(y, view["total_bytes"], color="tab:green")
        ax.set_yticks(y)
        ax.set_yticklabels(view["source_class"], fontsize=8)
        ax.set_title("Master bytes by source class")
        ax.set_xlabel("response bytes")
        for yi, row in zip(y, view.itertuples()):
            ax.text(0, yi, f"hash {int(row.raw_hash_rows)} fields {int(row.extracted_expected_field_rows)}", va="center", ha="left", fontsize=8)

    ax = axes[1, 0]
    result = pd.DataFrame(
        {
            "bucket": ["new append rows", "already duplicate rows", "rejected rows", "rerun new rows"],
            "count": [len(append_rows), len(duplicate_rows), len(rejected), len(second_append_rows)],
        }
    )
    ax.bar(result["bucket"], result["count"], color=["tab:green", "tab:orange", "tab:red", "tab:gray"])
    ax.set_title("Append and idempotency result")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=15)
    for idx, value in enumerate(result["count"]):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom")

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes selector locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

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
    source: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage636 lh Monthly Master PIT Append Gate Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- input_fetch_ledger: `{STAGE635_FETCH_LEDGER}`",
        f"- stable_master_ledger: `{MASTER_LEDGER_PATH}`",
        "- stage nature: append gate only; no strategy replay, no selector, no paper, no whitelist, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "PIT source data can only support future selector research if the ledger preserves collection time, source URL, final URL, raw hash, status and lock fields. The master gate therefore rejects missing hash/schema/time rows and confirms idempotency before any predictive audit.",
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
        f"- active fetch rows in master: `{decision['active_fetch_rows']}`",
        f"- raw hash rows in master: `{decision['raw_hash_rows']}`",
        f"- PIT dates: `{decision['pit_dates']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
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
        "- `lh.DCE` 官方月度源证据已进入稳定 master PIT ledger，但只有 `1` 个 received_at 日期。",
        "- 内部幂等复跑没有新增行，说明重复运行不会膨胀 PIT 样本。",
        "- 这仍不是 selector 或 alpha：需要至少 `20` 个 received_at 日期、`12` 个月跨度、独立 episode、预测力审计和 live TCA。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fetch_ledger = _read_csv(STAGE635_FETCH_LEDGER)
    if fetch_ledger.empty:
        raise FileNotFoundError(f"missing or empty fetch ledger: {STAGE635_FETCH_LEDGER}")
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
    source = _source_progress(combined)
    gates = _gates(fetch_ledger, append_rows, duplicate_rows, rejected, combined, progress, second_append_rows, second_duplicate_rows)
    progress.to_csv(PRODUCT_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    source.to_csv(SOURCE_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    active_fetch_rows = int(_num(combined, "active_fetch_validated").sum()) if not combined.empty else 0
    raw_hash_rows = int(_num(combined, "raw_sha256_present").sum()) if not combined.empty else 0
    pit_dates = int(progress["pit_dates"].max()) if not progress.empty else 0
    selector_rows = int(progress["selector_rows"].max()) if not progress.empty else 0
    paper_rows = int(progress["paper_or_whitelist_rows"].max()) if not progress.empty else 0

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "lh_monthly_master_pit_append_gate_written_selector_locked",
        "input_rows": int(len(fetch_ledger)),
        "append_rows": int(len(append_rows)),
        "duplicate_rows": int(len(duplicate_rows)),
        "rejected_rows": int(len(rejected)),
        "idempotent_rerun_append_rows": int(len(second_append_rows)),
        "idempotent_rerun_duplicate_rows": int(len(second_duplicate_rows)),
        "idempotent_rerun_rejected_rows": int(len(second_rejected)),
        "master_rows": int(len(combined)),
        "active_fetch_rows": active_fetch_rows,
        "raw_hash_rows": raw_hash_rows,
        "pit_dates": pit_dates,
        "required_pit_dates_for_selector": REQUIRED_PIT_DATES_FOR_SELECTOR,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "master_ledger_path": str(MASTER_LEDGER_PATH),
        "chart_path": str(CHART_PATH),
    }

    _write_chart(progress, source, gates, append_rows, duplicate_rows, rejected, second_append_rows)
    _write_report(generated_at, fetch_ledger, append_rows, duplicate_rows, rejected, combined, progress, source, gates, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
