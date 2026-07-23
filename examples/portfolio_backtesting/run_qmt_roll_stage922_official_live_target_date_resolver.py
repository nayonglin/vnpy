from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from qmt_roll_official_live_lightweight_context import (
    ALL_FUTURES_MAPPING_PATH,
    CONTROL_OUTPUT_DIR,
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    SIGNAL_INPUT_DIR,
    STAGE173_STATUS_PATH,
    STAGE173_SUMMARY_PATH,
)


MODEL_TAG = "stage922_official_live_target_date_resolver_v1"
OUTPUT_PREFIX = "qmt_roll_stage922_official_live_target_date_resolver"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "evidence_csv": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_evidence_{run_id}_{MODEL_TAG}.csv"
        ),
        "summary_json": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json"
        ),
        "report_md": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md"
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error_type": type(exc).__name__}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_as_of(value: str) -> datetime:
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _parse_time_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_text(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else ""


def _latest_status_bar_date(rows: list[dict[str, str]]) -> str:
    dates = [
        parsed
        for row in rows
        if (parsed := _parse_date(row.get("max_date"))) is not None
    ]
    return max(dates).isoformat() if dates else ""


def _status_contract_coverage(
    rows: list[dict[str, str]],
    target_date: str,
) -> dict[str, int | float]:
    contract_count = len(rows)
    target_count = sum(
        _date_text(row.get("max_date")) == target_date for row in rows
    )
    return {
        "contract_count": contract_count,
        "target_date_contract_count": target_count,
        "coverage_ratio": (
            float(target_count / contract_count) if contract_count else 0.0
        ),
    }


def _known_trading_dates(path: Path = ALL_FUTURES_MAPPING_PATH) -> list[date]:
    if not path.exists():
        return []
    observed: set[date] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = _parse_date(row.get("date"))
            if parsed is not None:
                observed.add(parsed)
    return sorted(observed)


def _previous_weekday(day: date) -> date:
    current = day
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def _wall_clock_cutoff_date(
    as_of: datetime,
    data_ready_time: str,
) -> datetime:
    ready_minutes = _parse_time_minutes(data_ready_time)
    as_of_minutes = as_of.hour * 60 + as_of.minute
    day = as_of.date()
    if day.weekday() < 5 and as_of_minutes < ready_minutes:
        day -= timedelta(days=1)
    cutoff = _previous_weekday(day)
    return datetime.combine(cutoff, datetime.min.time())


def _resolve_latest_completed(
    as_of: datetime,
    data_ready_time: str,
    mapping_path: Path = ALL_FUTURES_MAPPING_PATH,
) -> tuple[str, dict[str, Any]]:
    cutoff = _wall_clock_cutoff_date(as_of, data_ready_time).date()
    trading_dates = _known_trading_dates(mapping_path)
    eligible = [day for day in trading_dates if day <= cutoff]
    if eligible:
        resolved = max(eligible)
        source = "main_contract_mapping_trading_calendar"
    else:
        resolved = _previous_weekday(cutoff)
        source = "weekday_fallback"
    evidence = {
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "data_ready_time": data_ready_time,
        "wall_clock_cutoff_date": cutoff.isoformat(),
        "trading_calendar_source": source,
        "known_trading_date_count": len(trading_dates),
        "known_trading_date_max": (
            trading_dates[-1].isoformat() if trading_dates else ""
        ),
    }
    return resolved.isoformat(), evidence


def build_target_date_resolution(
    *,
    as_of: datetime,
    data_ready_time: str,
    official_summary_path: Path = OFFICIAL_LIVE_SUMMARY_PATH,
    stage173_summary_path: Path = STAGE173_SUMMARY_PATH,
    stage173_status_path: Path = STAGE173_STATUS_PATH,
    mapping_path: Path = ALL_FUTURES_MAPPING_PATH,
) -> dict[str, Any]:
    resolved_target_date, resolver_evidence = _resolve_latest_completed(
        as_of,
        data_ready_time,
        mapping_path,
    )
    official_summary = _read_json(official_summary_path)
    stage173_summary = _read_json(stage173_summary_path)
    stage173_status = _read_csv_rows(stage173_status_path)
    status_bar_date = _latest_status_bar_date(stage173_status)
    official_analysis_end = _date_text(official_summary.get("analysis_end", ""))
    official_analysis_start = _date_text(
        official_summary.get("analysis_start", "")
    )
    official_latest_available = _date_text(
        official_summary.get("latest_available_data_date", "")
    )
    stage173_max_saved = _date_text(stage173_summary.get("max_saved_date", ""))
    mapping_combined_max = _date_text(
        (stage173_summary.get("mapping_update") or {}).get(
            "combined_max_date",
            "",
        )
    )
    coverage = _status_contract_coverage(
        stage173_status,
        resolved_target_date,
    )
    resolved_date = _parse_date(resolved_target_date)
    shadow_start = _parse_date(OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE)
    target_before_shadow_start = bool(
        resolved_date is not None
        and shadow_start is not None
        and resolved_date < shadow_start
    )

    requires_shadow_refresh = int(
        bool(resolved_target_date)
        and not target_before_shadow_start
        and (
            official_analysis_end != resolved_target_date
            or official_latest_available != resolved_target_date
            or official_analysis_start
            != OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
        )
    )
    requires_data_update = int(
        bool(resolved_target_date)
        and (
            stage173_max_saved != resolved_target_date
            or status_bar_date != resolved_target_date
        )
    )
    if target_before_shadow_start:
        resolver_status = (
            "target_date_before_live_shadow_start_waiting_fail_closed"
        )
    elif not resolved_target_date:
        resolver_status = "target_date_resolver_blocked_fail_closed"
    elif requires_shadow_refresh or requires_data_update:
        resolver_status = "target_date_resolved_requires_refresh_fail_closed"
    else:
        resolver_status = "target_date_resolved_local_shadow_ready_fail_closed"

    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "resolver_status": resolver_status,
        "resolved_target_date": resolved_target_date,
        "requires_shadow_refresh": requires_shadow_refresh,
        "requires_data_update": requires_data_update,
        "auto_submit_permitted": 0,
        "order_api_called_count": 0,
        "official_live_shadow_analysis_start_date": (
            OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
        ),
        "target_before_shadow_start": int(target_before_shadow_start),
        "official_summary_analysis_start": official_analysis_start,
        "official_summary_analysis_end": official_analysis_end,
        "official_latest_available_data_date": official_latest_available,
        "stage173_max_saved_date": stage173_max_saved,
        "stage173_status_bar_max_date": status_bar_date,
        "stage173_mapping_combined_max_date": mapping_combined_max,
        "stage173_target_contract_coverage": coverage,
        "resolver_evidence": resolver_evidence,
        "source_files": {
            "official_summary": str(official_summary_path),
            "stage173_summary": str(stage173_summary_path),
            "stage173_status": str(stage173_status_path),
            "main_contract_mapping": str(mapping_path),
        },
        "judgement": {
            "overfit_before": (
                "No. Stage922 only resolves an execution date; it does not "
                "change strategy logic."
            ),
            "continue_before": (
                "Yes. Unattended automation needs target-date handling "
                "without manual plist edits."
            ),
            "overfit_after": (
                "No. A resolved date must still pass Stage909 data/shadow "
                "validation."
            ),
            "continue_after": (
                "Yes. Keep fail-closed until Stage909 and reconciliation "
                "prove the date is executable."
            ),
        },
    }


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _to_markdown(
    rows: list[dict[str, Any]],
    columns: list[str],
) -> str:
    if not rows:
        return "_empty_"
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join(_markdown_cell(row.get(column, "")) for column in columns)
        + " |"
        for row in rows
    ]
    return "\n".join((header, divider, *body))


def _build_report(
    summary: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> str:
    return "\n".join(
        [
            "# Stage922 Official Live Target Date Resolver",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            (
                f"- Official live: `{summary['official_live_version']}` / "
                f"`{summary['official_live_alias']}`"
            ),
            f"- Resolver status: `{summary['resolver_status']}`",
            f"- Resolved target date: `{summary['resolved_target_date']}`",
            f"- Requires shadow refresh: `{summary['requires_shadow_refresh']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Evidence",
            "",
            _to_markdown(evidence, ["field", "value"]),
            "",
            "## Notes",
            "",
            (
                "- Stage922 resolves the latest completed trading day for "
                "unattended controller runs."
            ),
            (
                "- It never treats the date guess as a signal. Stage909 must "
                "still update data and prove the official shadow `analysis_end` "
                "matches the resolved date."
            ),
            (
                "- If the resolved date is ahead of local bars or the current "
                "official summary, Phase D remains fail-closed until the "
                "refresh succeeds."
            ),
            "",
        ]
    )


def _evidence_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    resolver_evidence = summary["resolver_evidence"]
    coverage = summary["stage173_target_contract_coverage"]
    return [
        {"field": "as_of", "value": resolver_evidence.get("as_of", "")},
        {
            "field": "data_ready_time",
            "value": resolver_evidence.get("data_ready_time", ""),
        },
        {
            "field": "wall_clock_cutoff_date",
            "value": resolver_evidence.get("wall_clock_cutoff_date", ""),
        },
        {
            "field": "trading_calendar_source",
            "value": resolver_evidence.get("trading_calendar_source", ""),
        },
        {
            "field": "known_trading_date_max",
            "value": resolver_evidence.get("known_trading_date_max", ""),
        },
        {
            "field": "resolved_target_date",
            "value": summary["resolved_target_date"],
        },
        {
            "field": "official_live_shadow_analysis_start_date",
            "value": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
        },
        {
            "field": "target_before_shadow_start",
            "value": summary["target_before_shadow_start"],
        },
        {
            "field": "official_summary_analysis_start",
            "value": summary["official_summary_analysis_start"],
        },
        {
            "field": "official_summary_analysis_end",
            "value": summary["official_summary_analysis_end"],
        },
        {
            "field": "official_latest_available_data_date",
            "value": summary["official_latest_available_data_date"],
        },
        {
            "field": "stage173_max_saved_date",
            "value": summary["stage173_max_saved_date"],
        },
        {
            "field": "stage173_status_bar_max_date",
            "value": summary["stage173_status_bar_max_date"],
        },
        {
            "field": "stage173_mapping_combined_max_date",
            "value": summary["stage173_mapping_combined_max_date"],
        },
        {
            "field": "target_contract_coverage_ratio",
            "value": coverage.get("coverage_ratio", 0.0),
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Official-live latest completed trading day resolver."
    )
    parser.add_argument(
        "--as-of",
        default="",
        help="Optional local timestamp, e.g. 2026-06-16T00:40:00.",
    )
    parser.add_argument(
        "--data-ready-time",
        default="16:30",
        help="Local day-session daily-bar ready time.",
    )
    args = parser.parse_args()

    CONTROL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    summary = build_target_date_resolution(
        as_of=_parse_as_of(args.as_of),
        data_ready_time=args.data_ready_time,
    )
    summary["outputs"] = {
        key: str(value.resolve()) for key, value in paths.items()
    }
    evidence = _evidence_rows(summary)
    with paths["evidence_csv"].open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(evidence)
    paths["summary_json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    paths["report_md"].write_text(
        _build_report(summary, evidence),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
