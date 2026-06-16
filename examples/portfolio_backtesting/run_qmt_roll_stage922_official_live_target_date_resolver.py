from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from build_qmt_roll_stage173_forward_main_contract_data_update import STATUS_PATH as STAGE173_STATUS_PATH
from build_qmt_roll_stage173_forward_main_contract_data_update import SUMMARY_PATH as STAGE173_SUMMARY_PATH
from main_contract_mapping import ALL_FUTURES_MAPPING_PATH
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage922_official_live_target_date_resolver_v1"
OUTPUT_PREFIX = "qmt_roll_stage922_official_live_target_date_resolver"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "evidence_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


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


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    dt = pd.to_datetime(text, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.date().isoformat()


def _latest_status_bar_date(status: pd.DataFrame) -> str:
    if status.empty or "max_date" not in status.columns:
        return ""
    dates = pd.to_datetime(status["max_date"], errors="coerce").dropna()
    if dates.empty:
        return ""
    return dates.max().date().isoformat()


def _status_contract_coverage(status: pd.DataFrame, target_date: str) -> dict[str, Any]:
    if status.empty or not target_date or "max_date" not in status.columns:
        return {"contract_count": 0, "target_date_contract_count": 0, "coverage_ratio": 0.0}
    max_dates = pd.to_datetime(status["max_date"], errors="coerce").dt.date.astype(str)
    contract_count = int(len(status))
    target_count = int((max_dates == target_date).sum())
    return {
        "contract_count": contract_count,
        "target_date_contract_count": target_count,
        "coverage_ratio": float(target_count / contract_count) if contract_count else 0.0,
    }


def _known_trading_dates() -> list[pd.Timestamp]:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        return []
    try:
        frame = pd.read_csv(ALL_FUTURES_MAPPING_PATH, usecols=["date"], encoding="utf-8-sig")
    except Exception:
        frame = pd.read_csv(ALL_FUTURES_MAPPING_PATH, usecols=["date"])
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().drop_duplicates().sort_values()
    return [pd.Timestamp(d).normalize() for d in dates.tolist()]


def _previous_weekday(day: pd.Timestamp) -> pd.Timestamp:
    current = day.normalize()
    while current.weekday() >= 5:
        current -= pd.Timedelta(days=1)
    return current


def _wall_clock_cutoff_date(as_of: datetime, data_ready_time: str) -> pd.Timestamp:
    ready_minutes = _parse_time_minutes(data_ready_time)
    as_of_minutes = as_of.hour * 60 + as_of.minute
    day = pd.Timestamp(as_of.date()).normalize()
    if as_of.weekday() < 5 and as_of_minutes < ready_minutes:
        day -= pd.Timedelta(days=1)
    return _previous_weekday(day)


def _resolve_latest_completed(as_of: datetime, data_ready_time: str) -> tuple[str, dict[str, Any]]:
    cutoff = _wall_clock_cutoff_date(as_of, data_ready_time)
    trading_dates = _known_trading_dates()
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
        "wall_clock_cutoff_date": cutoff.date().isoformat(),
        "trading_calendar_source": source,
        "known_trading_date_count": len(trading_dates),
        "known_trading_date_max": trading_dates[-1].date().isoformat() if trading_dates else "",
    }
    return resolved.date().isoformat(), evidence


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], evidence: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage922 Official Live Target Date Resolver",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
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
            "- Stage922 resolves the latest completed trading day for unattended controller runs.",
            "- It never treats the date guess as a signal. Stage909 must still update data and prove the official shadow `analysis_end` matches the resolved date.",
            "- If the resolved date is ahead of local bars or the current official summary, Phase D remains fail-closed until the refresh succeeds.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live latest completed trading day resolver.")
    parser.add_argument("--as-of", default="", help="Optional local timestamp, e.g. 2026-06-16T00:40:00.")
    parser.add_argument("--data-ready-time", default="16:30", help="Local day-session daily-bar ready time.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    as_of = _parse_as_of(args.as_of)
    resolved_target_date, resolver_evidence = _resolve_latest_completed(as_of, args.data_ready_time)

    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    stage173_summary = _read_json(STAGE173_SUMMARY_PATH)
    stage173_status = _read_csv_maybe(STAGE173_STATUS_PATH)
    status_bar_date = _latest_status_bar_date(stage173_status)
    official_analysis_end = _date_text(official_summary.get("analysis_end", ""))
    official_analysis_start = _date_text(official_summary.get("analysis_start", ""))
    official_latest_available = _date_text(official_summary.get("latest_available_data_date", ""))
    stage173_max_saved = _date_text(stage173_summary.get("max_saved_date", ""))
    mapping_combined_max = _date_text((stage173_summary.get("mapping_update") or {}).get("combined_max_date", ""))
    coverage = _status_contract_coverage(stage173_status, resolved_target_date)
    target_before_shadow_start = bool(
        resolved_target_date
        and pd.Timestamp(resolved_target_date).normalize()
        < pd.Timestamp(OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE).normalize()
    )

    requires_shadow_refresh = int(
        resolved_target_date
        and not target_before_shadow_start
        and (official_analysis_end != resolved_target_date or official_latest_available != resolved_target_date)
        or (
            resolved_target_date
            and not target_before_shadow_start
            and official_analysis_start != OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
        )
    )
    requires_data_update = int(
        resolved_target_date
        and (stage173_max_saved != resolved_target_date or status_bar_date != resolved_target_date)
    )
    if target_before_shadow_start:
        resolver_status = "target_date_before_live_shadow_start_waiting_fail_closed"
    elif not resolved_target_date:
        resolver_status = "target_date_resolver_blocked_fail_closed"
    elif requires_shadow_refresh or requires_data_update:
        resolver_status = "target_date_resolved_requires_refresh_fail_closed"
    else:
        resolver_status = "target_date_resolved_local_shadow_ready_fail_closed"

    summary = {
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
        "official_live_shadow_analysis_start_date": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
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
            "official_summary": str(OFFICIAL_LIVE_SUMMARY_PATH),
            "stage173_summary": str(STAGE173_SUMMARY_PATH),
            "stage173_status": str(STAGE173_STATUS_PATH),
            "main_contract_mapping": str(ALL_FUTURES_MAPPING_PATH),
        },
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "No. Stage922 only resolves an execution date; it does not change strategy logic.",
            "continue_before": "Yes. Unattended automation needs target-date handling without manual plist edits.",
            "overfit_after": "No. A resolved date must still pass Stage909 data/shadow validation.",
            "continue_after": "Yes. Keep fail-closed until Stage909 and reconciliation prove the date is executable.",
        },
    }
    evidence_rows = [
        {"field": "as_of", "value": resolver_evidence.get("as_of", "")},
        {"field": "data_ready_time", "value": resolver_evidence.get("data_ready_time", "")},
        {"field": "wall_clock_cutoff_date", "value": resolver_evidence.get("wall_clock_cutoff_date", "")},
        {"field": "trading_calendar_source", "value": resolver_evidence.get("trading_calendar_source", "")},
        {"field": "known_trading_date_max", "value": resolver_evidence.get("known_trading_date_max", "")},
        {"field": "resolved_target_date", "value": resolved_target_date},
        {"field": "official_live_shadow_analysis_start_date", "value": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE},
        {"field": "target_before_shadow_start", "value": int(target_before_shadow_start)},
        {"field": "official_summary_analysis_start", "value": official_analysis_start},
        {"field": "official_summary_analysis_end", "value": official_analysis_end},
        {"field": "official_latest_available_data_date", "value": official_latest_available},
        {"field": "stage173_max_saved_date", "value": stage173_max_saved},
        {"field": "stage173_status_bar_max_date", "value": status_bar_date},
        {"field": "stage173_mapping_combined_max_date", "value": mapping_combined_max},
        {"field": "target_contract_coverage_ratio", "value": coverage.get("coverage_ratio", 0.0)},
    ]
    evidence_df = pd.DataFrame(evidence_rows)
    evidence_df.to_csv(paths["evidence_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, evidence_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
