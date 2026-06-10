from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DB_PATH = REPO_DIR / ".vntrader" / "database.db"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
sys.path.insert(0, str(REPO_DIR.resolve()))

from main_contract_mapping import ALL_FUTURES_MAPPING_PATH, load_mapping_df  # noqa: E402

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653  # noqa: E402
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402


MODEL_TAG = "stage770_2018_2020_warmup_readiness_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage770_2018_2020_warmup_readiness_forensics"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2020-12-31")
STARTS = (
    pd.Timestamp("2018-01-01"),
    pd.Timestamp("2019-01-01"),
    pd.Timestamp("2020-01-01"),
)

READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_summary_{MODEL_TAG}.csv"
START_FACTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_facts_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE769_START_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage769_2018_trade_count_forensics_start_summary_stage769_2018_trade_count_forensics_v1.csv"
)
STAGE769_PAIR_COMPARE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage769_2018_trade_count_forensics_pair_compare_stage769_2018_trade_count_forensics_v1.csv"
)
STAGE769_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage769_2018_trade_count_forensics_entry_candidates_stage769_2018_trade_count_forensics_v1.csv"
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _preload_for_start(start: pd.Timestamp) -> pd.Timestamp:
    if start < pd.Timestamp("2020-01-01"):
        return (start - pd.Timedelta(days=365)).normalize()
    return pd.Timestamp(s653.s517.PRELOAD_START_DT).normalize()


def _stage757_setting(metadata: dict[str, Any]) -> dict[str, Any]:
    spec = s757._candidate_spec(metadata)
    setting = s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=s513._c3_overrides(s653.s517.START_DT),
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    return setting


def _effective_am_size(setting: dict[str, Any]) -> int:
    floor = int(setting.get("array_manager_size_floor", QmtRollPortfolioStrategy.array_manager_size_floor) or 140)
    ma_extra_long = int(setting.get("ma_extra_long", QmtRollPortfolioStrategy.ma_extra_long))
    donchian_entry_period = int(setting.get("donchian_entry_period", QmtRollPortfolioStrategy.donchian_entry_period))
    return max(ma_extra_long + donchian_entry_period + 20, max(floor, 1))


def _load_mapping(product_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    mapping = load_mapping_df(ALL_FUTURES_MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    mapping = mapping[
        (mapping["date"] >= start)
        & (mapping["date"] <= end)
        & (mapping["continuous_symbol_vt"].isin(product_symbols))
    ].copy()
    mapping = mapping[mapping["main_contract_vt"].astype(str).ne("")].copy()
    return mapping.rename(
        columns={
            "continuous_symbol_vt": "product_vt_symbol",
            "main_contract_vt": "contract_vt_symbol",
        }
    )


def _load_db_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        frame = pd.read_sql_query(
            """
            select symbol || '.' || exchange as contract_vt_symbol,
                   date(datetime) as date
            from dbbardata
            where interval='d' and datetime>=? and datetime<?
            """,
            conn,
            params=(start.strftime("%Y-%m-%d"), (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")),
        )
    finally:
        conn.close()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame = frame.dropna(subset=["date"]).drop_duplicates(["contract_vt_symbol", "date"]).copy()
    return frame.sort_values(["contract_vt_symbol", "date"]).reset_index(drop=True)


def _audit_start(
    *,
    start: pd.Timestamp,
    mapping_all: pd.DataFrame,
    db_days_all: pd.DataFrame,
    am_size: int,
    warmup_days: int,
) -> pd.DataFrame:
    engine_preload_start = _preload_for_start(start)
    count_start = (engine_preload_start - pd.Timedelta(days=warmup_days)).normalize()
    mapping = mapping_all[(mapping_all["date"] >= start) & (mapping_all["date"] <= ANALYSIS_END)].copy()
    db_days = db_days_all[(db_days_all["date"] >= count_start) & (db_days_all["date"] <= ANALYSIS_END)].copy()
    db_days["contract_bar_count_to_date"] = db_days.groupby("contract_vt_symbol", sort=False).cumcount() + 1

    audited = mapping.merge(
        db_days[["contract_vt_symbol", "date", "contract_bar_count_to_date"]],
        on=["contract_vt_symbol", "date"],
        how="left",
    )
    audited["requested_start_month"] = start.strftime("%Y-%m")
    audited["engine_preload_start"] = engine_preload_start.date().isoformat()
    audited["warmup_days"] = int(warmup_days)
    audited["bar_count_start"] = count_start.date().isoformat()
    audited["required_am_size"] = int(am_size)
    audited["year"] = audited["date"].dt.year.astype(int)
    audited["has_target_bar"] = audited["contract_bar_count_to_date"].notna().astype(int)
    audited["contract_bar_count_to_date"] = (
        pd.to_numeric(audited["contract_bar_count_to_date"], errors="coerce").fillna(0).astype(int)
    )
    audited["am_ready"] = (
        audited["has_target_bar"].eq(1) & audited["contract_bar_count_to_date"].ge(am_size)
    ).astype(int)
    return audited[
        [
            "requested_start_month",
            "engine_preload_start",
            "warmup_days",
            "bar_count_start",
            "required_am_size",
            "date",
            "year",
            "product_vt_symbol",
            "contract_vt_symbol",
            "has_target_bar",
            "contract_bar_count_to_date",
            "am_ready",
        ]
    ].sort_values(["requested_start_month", "date", "product_vt_symbol"])


def _year_summary(readiness: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start, year), group in readiness.groupby(["requested_start_month", "year"], sort=True):
        products = int(group["product_vt_symbol"].nunique())
        ready_group = group[group["am_ready"].eq(1)]
        rows.append(
            {
                "requested_start_month": start,
                "year": int(year),
                "mapped_product_days": int(len(group)),
                "target_bar_days": int(group["has_target_bar"].sum()),
                "target_bar_coverage_pct": float(group["has_target_bar"].mean() * 100.0) if len(group) else 0.0,
                "am_ready_days": int(group["am_ready"].sum()),
                "am_ready_pct": float(group["am_ready"].mean() * 100.0) if len(group) else 0.0,
                "products": products,
                "ready_products": int(ready_group["product_vt_symbol"].nunique()) if not ready_group.empty else 0,
                "first_ready_date": pd.Timestamp(ready_group["date"].min()).date().isoformat()
                if not ready_group.empty
                else "",
            }
        )
    return pd.DataFrame(rows)


def _product_year_summary(readiness: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start, year, product), group in readiness.groupby(
        ["requested_start_month", "year", "product_vt_symbol"], sort=True
    ):
        ready_group = group[group["am_ready"].eq(1)]
        rows.append(
            {
                "requested_start_month": start,
                "year": int(year),
                "product_vt_symbol": product,
                "mapped_days": int(len(group)),
                "target_bar_days": int(group["has_target_bar"].sum()),
                "am_ready_days": int(group["am_ready"].sum()),
                "first_ready_date": pd.Timestamp(ready_group["date"].min()).date().isoformat()
                if not ready_group.empty
                else "",
                "contracts": ",".join(sorted(group["contract_vt_symbol"].astype(str).unique())),
            }
        )
    return pd.DataFrame(rows)


def _first_candidates() -> pd.DataFrame:
    if not STAGE769_CANDIDATES_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_csv(STAGE769_CANDIDATES_PATH)
    if frame.empty:
        return frame
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce").dt.tz_localize(None).dt.normalize()
    view = (
        frame.sort_values(["requested_start_month", "datetime", "product_vt_symbol"])
        .groupby("requested_start_month", as_index=False)
        .head(5)
        .copy()
    )
    keep = [
        "requested_start_month",
        "datetime",
        "product_vt_symbol",
        "target_contract",
        "direction",
        "signal",
        "candidate_status",
        "skip_reason",
    ]
    return view[[column for column in keep if column in view.columns]]


def _load_start_facts() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if STAGE769_START_SUMMARY_PATH.exists():
        start_summary = pd.read_csv(STAGE769_START_SUMMARY_PATH)
        start_summary["fact_type"] = "stage769_start_summary"
        frames.append(start_summary)
    if STAGE769_PAIR_COMPARE_PATH.exists():
        pair_compare = pd.read_csv(STAGE769_PAIR_COMPARE_PATH)
        pair_compare["fact_type"] = "stage769_pair_compare"
        frames.append(pair_compare)
    first_candidates = _first_candidates()
    if not first_candidates.empty:
        first_candidates["fact_type"] = "stage769_first_candidates"
        frames.append(first_candidates)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _write_report(
    *,
    year_summary: pd.DataFrame,
    product_year: pd.DataFrame,
    start_facts: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    product_2018 = product_year[
        (product_year["requested_start_month"].eq("2018-01")) & (product_year["year"].eq(2018))
    ].copy()
    lines = [
        "# Stage770 2018/2019/2020 预热与交易笔数法证复盘",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 本阶段只读复盘，不修改策略参数、不下载新数据、不连接 CTP。",
        f"- Stage757 实际 `required_am_size`：`{decision['required_am_size']}`；`warmup_days`：`{decision['warmup_days']}`。",
        "",
        "## 年度预热覆盖",
        "",
        _md_table(year_summary, max_rows=20),
        "",
        "## 2018 起点的 2018 年分品种预热",
        "",
        _md_table(product_2018, max_rows=40),
        "",
        "## Stage769 成交/候选事实",
        "",
        _md_table(start_facts, max_rows=40),
        "",
        "## 结论",
        "",
        f"- 数据问题判断：`{decision['data_issue_judgment']}`",
        f"- 根因判断：`{decision['root_cause']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    setting = _stage757_setting(metadata)
    am_size = _effective_am_size(setting)
    warmup_days = int(setting.get("warmup_days", QmtRollPortfolioStrategy.warmup_days) or 0)
    product_symbols = sorted(metadata["product_symbols"])

    min_mapping_start = min(STARTS)
    min_count_start = min(_preload_for_start(start) - pd.Timedelta(days=warmup_days) for start in STARTS).normalize()
    mapping_all = _load_mapping(product_symbols, min_mapping_start, ANALYSIS_END)
    db_days_all = _load_db_days(min_count_start, ANALYSIS_END)

    readiness = pd.concat(
        [
            _audit_start(
                start=start,
                mapping_all=mapping_all,
                db_days_all=db_days_all,
                am_size=am_size,
                warmup_days=warmup_days,
            )
            for start in STARTS
        ],
        ignore_index=True,
        sort=False,
    )
    year_summary = _year_summary(readiness)
    product_year = _product_year_summary(readiness)
    start_facts = _load_start_facts()

    y2018 = year_summary[
        (year_summary["requested_start_month"].eq("2018-01")) & (year_summary["year"].eq(2018))
    ].iloc[0]
    y2020 = year_summary[
        (year_summary["requested_start_month"].eq("2020-01")) & (year_summary["year"].eq(2020))
    ].iloc[0]
    decision = {
        "stage": "Stage770",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "required_am_size": int(am_size),
        "warmup_days": int(warmup_days),
        "product_count": int(len(product_symbols)),
        "data_issue_judgment": (
            "not_reused_backtest_data_but_2018_is_methodologically_weak: mapped target bars mostly exist, "
            "while real-contract ArrayManager readiness is materially lower than 2020"
        ),
        "root_cause": (
            "current strategy computes indicators on each real dominant contract; after contract rolls, the new real "
            "contract must accumulate the full AM window before any signal is evaluated"
        ),
        "key_numbers": {
            "start_2018_year_2018_target_bar_coverage_pct": float(y2018["target_bar_coverage_pct"]),
            "start_2018_year_2018_am_ready_pct": float(y2018["am_ready_pct"]),
            "start_2018_year_2018_ready_products": int(y2018["ready_products"]),
            "start_2020_year_2020_target_bar_coverage_pct": float(y2020["target_bar_coverage_pct"]),
            "start_2020_year_2020_am_ready_pct": float(y2020["am_ready_pct"]),
            "start_2020_year_2020_ready_products": int(y2020["ready_products"]),
        },
        "overfit_judgment": "low: only audits data/engine readiness and Stage769 trade signatures; no PnL-dependent tuning",
        "continue_value": (
            "yes: next valuable check is an isolated continuous-product-indicator research engine; "
            "do not tune the frozen strategy just to manufacture 2018 trades"
        ),
        "outputs": {
            "readiness": str(READINESS_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "product_year_summary": str(PRODUCT_YEAR_PATH),
            "start_facts": str(START_FACTS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_year.to_csv(PRODUCT_YEAR_PATH, index=False, encoding="utf-8-sig")
    start_facts.to_csv(START_FACTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(year_summary=year_summary, product_year=product_year, start_facts=start_facts, decision=decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
