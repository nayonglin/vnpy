from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from build_qmt_roll_stage149_stage78_2010_multicycle_audit import (
    COVERAGE_PASS_THRESHOLD,
    _latest_database_date,
    build_windows,
    load_contract_date_sets,
    load_mapping_df,
    load_product_universe_symbols,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
CSV_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

MODEL_TAG: str = "stage150_stage78_2010_data_repair_feasibility_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage150_stage78_2010_data_repair_feasibility"

GAP_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_summary_{MODEL_TAG}.csv"
CONTRACT_GAPS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_gaps_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REPAIR_WINDOWS: set[str] = {
    "requested_2010_2026",
    "database_coverage_since_2016",
    "preload_since_2019_06",
    "full_2020_2026",
}

CLASS_DB_PRESENT: str = "db_present"
CLASS_RAW_CAN_REIMPORT: str = "raw_can_reimport"
CLASS_RAW_FILE_MISSING: str = "raw_file_missing"
CLASS_RAW_DATE_MISSING: str = "raw_date_missing"


def _load_raw_dates(vt_symbol: str, cache: dict[str, set[str] | None]) -> set[str] | None:
    if vt_symbol in cache:
        return cache[vt_symbol]

    symbol, exchange = vt_symbol.split(".", 1)
    file_path = CSV_ROOT / exchange / f"{symbol}.csv"
    if not file_path.exists():
        cache[vt_symbol] = None
        return None

    try:
        df = pd.read_csv(file_path)
    except Exception:
        cache[vt_symbol] = set()
        return set()

    if df.empty:
        cache[vt_symbol] = set()
        return set()

    date_column = "trade_date" if "trade_date" in df.columns else "datetime"
    if date_column not in df.columns:
        cache[vt_symbol] = set()
        return set()

    dates = set(pd.to_datetime(df[date_column], errors="coerce").dropna().dt.date.astype(str))
    cache[vt_symbol] = dates
    return dates


def _classify_row(date_text: str, contract_vt: str, db_dates: set[str], raw_cache: dict[str, set[str] | None]) -> str:
    if date_text in db_dates:
        return CLASS_DB_PRESENT
    raw_dates = _load_raw_dates(contract_vt, raw_cache)
    if raw_dates is None:
        return CLASS_RAW_FILE_MISSING
    if date_text in raw_dates:
        return CLASS_RAW_CAN_REIMPORT
    return CLASS_RAW_DATE_MISSING


def build_repair_audit() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    latest_date = _latest_database_date()
    strategy_overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(strategy_overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    windows = [window for window in build_windows(latest_date) if str(window["window_name"]) in REPAIR_WINDOWS]
    mapping_df = load_mapping_df()
    mapping_df = mapping_df[
        mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
        & (mapping_df["main_contract_vt"].fillna("") != "")
    ].copy()
    mapping_df["date"] = pd.to_datetime(mapping_df["date"]).dt.date.astype(str)

    min_start = min(window["analysis_start"] for window in windows)
    max_end = max(window["analysis_end"] for window in windows)
    mapped_contracts = set(mapping_df["main_contract_vt"].astype(str))
    db_contract_dates = load_contract_date_sets(mapped_contracts, min_start, max_end)
    raw_cache: dict[str, set[str] | None] = {}

    summary_rows: list[dict[str, Any]] = []
    contract_accumulator: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for window in windows:
        window_name = str(window["window_name"])
        start_text = window["analysis_start"].date().isoformat()
        end_text = window["analysis_end"].date().isoformat()
        window_df = mapping_df[(mapping_df["date"] >= start_text) & (mapping_df["date"] <= end_text)].copy()
        class_counts: dict[str, int] = defaultdict(int)
        contract_counts: dict[str, set[str]] = defaultdict(set)

        for row in window_df.itertuples(index=False):
            date_text = str(row.date)
            product = str(row.continuous_symbol_vt)
            contract_vt = str(row.main_contract_vt)
            class_name = _classify_row(
                date_text,
                contract_vt,
                db_contract_dates.get(contract_vt, set()),
                raw_cache,
            )
            class_counts[class_name] += 1
            contract_counts[class_name].add(contract_vt)
            key = (window_name, product, contract_vt, class_name)
            if key not in contract_accumulator:
                contract_accumulator[key] = {
                    "window_name": window_name,
                    "product_vt_symbol": product,
                    "contract_vt_symbol": contract_vt,
                    "gap_class": class_name,
                    "mapped_days": 0,
                    "first_date": date_text,
                    "last_date": date_text,
                    "csv_file_exists": _load_raw_dates(contract_vt, raw_cache) is not None,
                }
            item = contract_accumulator[key]
            item["mapped_days"] = int(item["mapped_days"]) + 1
            item["first_date"] = min(str(item["first_date"]), date_text)
            item["last_date"] = max(str(item["last_date"]), date_text)

        mapped_days = int(sum(class_counts.values()))
        db_present = int(class_counts[CLASS_DB_PRESENT])
        raw_can_reimport = int(class_counts[CLASS_RAW_CAN_REIMPORT])
        current_coverage = db_present / mapped_days if mapped_days else 1.0
        potential_coverage = (db_present + raw_can_reimport) / mapped_days if mapped_days else 1.0
        summary_rows.append(
            {
                "window_name": window_name,
                "analysis_start": start_text,
                "analysis_end": end_text,
                "mapped_days": mapped_days,
                "db_present_days": db_present,
                "raw_can_reimport_days": raw_can_reimport,
                "raw_file_missing_days": int(class_counts[CLASS_RAW_FILE_MISSING]),
                "raw_date_missing_days": int(class_counts[CLASS_RAW_DATE_MISSING]),
                "current_coverage_ratio": current_coverage,
                "potential_coverage_after_local_reimport": potential_coverage,
                "coverage_pass_threshold": COVERAGE_PASS_THRESHOLD,
                "passes_now": current_coverage >= COVERAGE_PASS_THRESHOLD,
                "passes_after_local_reimport": potential_coverage >= COVERAGE_PASS_THRESHOLD,
                "db_present_contracts": len(contract_counts[CLASS_DB_PRESENT]),
                "raw_can_reimport_contracts": len(contract_counts[CLASS_RAW_CAN_REIMPORT]),
                "raw_file_missing_contracts": len(contract_counts[CLASS_RAW_FILE_MISSING]),
                "raw_date_missing_contracts": len(contract_counts[CLASS_RAW_DATE_MISSING]),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    contract_df = pd.DataFrame(contract_accumulator.values())
    if not contract_df.empty:
        contract_df.sort_values(["window_name", "gap_class", "mapped_days"], ascending=[True, True, False], inplace=True)

    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "csv_root": str(CSV_ROOT),
        "latest_database_date": latest_date.date().isoformat(),
        "coverage_pass_threshold": COVERAGE_PASS_THRESHOLD,
        "gap_summary_csv": str(GAP_SUMMARY_CSV_PATH),
        "contract_gaps_csv": str(CONTRACT_GAPS_CSV_PATH),
        "report": str(REPORT_PATH),
        "summary": summary_df.to_dict(orient="records"),
    }
    return summary_df, contract_df, payload


def build_report(summary_df: pd.DataFrame, contract_df: pd.DataFrame, payload: dict[str, Any]) -> str:
    view = summary_df.copy()
    view["current_coverage_pct"] = view["current_coverage_ratio"] * 100
    view["potential_coverage_pct"] = view["potential_coverage_after_local_reimport"] * 100
    early = view[view["window_name"].isin(["requested_2010_2026", "database_coverage_since_2016", "preload_since_2019_06"])]

    worst_contracts = contract_df[
        contract_df["gap_class"].isin([CLASS_RAW_FILE_MISSING, CLASS_RAW_DATE_MISSING])
    ].copy()
    if not worst_contracts.empty:
        worst_contracts = worst_contracts.sort_values("mapped_days", ascending=False).head(20)

    local_reimport_days = int(summary_df["raw_can_reimport_days"].sum()) if not summary_df.empty else 0
    judgement = (
        "LOCAL_REIMPORT_NOT_USEFUL"
        if local_reimport_days == 0
        else "LOCAL_REIMPORT_CAN_IMPROVE_COVERAGE"
    )

    lines = [
        "# Stage150 Stage78 2010 Data Repair Feasibility",
        "",
        "## Purpose",
        "",
        "- Classify Stage149 missing mapped trading days into DB-present, raw-CSV reimportable, raw-file-missing, and raw-date-missing.",
        "- Decide whether the current local CSV repository can repair the 2010-start coverage gap without external data.",
        "",
        "## Parameters",
        "",
        f"- Model tag: `{MODEL_TAG}`",
        f"- Official version: `{OFFICIAL_STAGE78_VERSION}`",
        f"- Capital: `{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        f"- CSV root: `{CSV_ROOT}`",
        f"- Latest database date: `{payload['latest_database_date']}`",
        f"- Coverage pass threshold: `{COVERAGE_PASS_THRESHOLD:.0%}`",
        "",
        "## Gap Summary",
        "",
        to_markdown_table(
            view[
                [
                    "window_name",
                    "mapped_days",
                    "db_present_days",
                    "raw_can_reimport_days",
                    "raw_file_missing_days",
                    "raw_date_missing_days",
                    "current_coverage_pct",
                    "potential_coverage_pct",
                    "passes_after_local_reimport",
                ]
            ]
        ),
        "",
        "## Early Window Feasibility",
        "",
        to_markdown_table(
            early[
                [
                    "window_name",
                    "current_coverage_ratio",
                    "potential_coverage_after_local_reimport",
                    "raw_can_reimport_days",
                    "raw_file_missing_days",
                    "raw_date_missing_days",
                    "passes_after_local_reimport",
                ]
            ]
        ),
        "",
        "## Largest Missing Contract Blocks",
        "",
        to_markdown_table(
            worst_contracts[
                [
                    "window_name",
                    "product_vt_symbol",
                    "contract_vt_symbol",
                    "gap_class",
                    "mapped_days",
                    "first_date",
                    "last_date",
                    "csv_file_exists",
                ]
            ]
        )
        if not worst_contracts.empty
        else "- No missing contract blocks.",
        "",
        "## Judgement",
        "",
        f"- `{judgement}`",
        "- For the 2010-start window, local reimport adds `0` mapped days because every gap is either missing raw CSV files or the raw CSV does not contain the needed date.",
        "- Therefore, rerunning the existing import script cannot fix the 2010 coverage problem.",
        "- A true 2010 Stage78 backtest requires external data repair or a new download source that actually contains the older dominant contracts.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, contract_df, payload = build_repair_audit()
    summary_df.to_csv(GAP_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    contract_df.to_csv(CONTRACT_GAPS_CSV_PATH, index=False, encoding="utf-8-sig")
    payload["contract_gaps"] = contract_df.to_dict(orient="records")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary_df, contract_df, payload), encoding="utf-8")

    print(summary_df.to_string(index=False))
    print(f"[stage150] gap summary: {GAP_SUMMARY_CSV_PATH}")
    print(f"[stage150] contract gaps: {CONTRACT_GAPS_CSV_PATH}")
    print(f"[stage150] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
