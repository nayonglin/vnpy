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
MODEL_TAG = "stage639_economic_driver_source_gap_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage639_economic_driver_source_gap_board"

STAGE541_ANNUAL = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv"
STAGE638_PRODUCT_LADDER = OUTPUT_DIR / "qmt_roll_stage638_annual_independent_trend_slot_audit_product_ladder_stage638_annual_independent_trend_slot_audit_v1.csv"
STAGE638_ANNUAL = OUTPUT_DIR / "qmt_roll_stage638_annual_independent_trend_slot_audit_annual_slot_opportunity_stage638_annual_independent_trend_slot_audit_v1.csv"
STAGE629_ROUTE_STATUS = OUTPUT_DIR / "qmt_roll_stage629_p2_public_source_monitor_run_route_status_stage629_p2_public_source_monitor_run_v1.csv"
STAGE635_LH_FETCH = OUTPUT_DIR / "qmt_roll_stage635_lh_monthly_source_fetch_probe_fetch_ledger_stage635_lh_monthly_source_fetch_probe_v1.csv"
STAGE620_CONTRACT = OUTPUT_DIR / "qmt_roll_stage620_forward_source_collector_contract_collector_contract_stage620_forward_source_collector_contract_v1.csv"
STAGE624_EVENT_LEDGER = OUTPUT_DIR / "qmt_roll_stage624_manual_public_event_ledger_bootstrap_event_ledger_stage624_manual_public_event_ledger_bootstrap_v1.csv"

FAMILY_BOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_driver_board_{MODEL_TAG}.csv"
SOURCE_BACKLOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_backlog_{MODEL_TAG}.csv"
TOP6_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_top6_detail_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_FAMILIES = ["energy_oil", "base_metals", "grains_oilseeds", "petrochem"]
TOP_N = 6
CURRENT_EFFECTIVE_SLOTS = 4
TARGET_EFFECTIVE_SLOTS = 7

REFERENCES = [
    "EIA Petroleum & Other Liquids / Weekly Petroleum Status Report: https://www.eia.gov/petroleum/index.php",
    "EIA petroleum data summary: https://www.eia.gov/petroleum/data.php/summary",
    "LME warehouse and stock reports: https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports",
    "USDA WASDE official report: https://www.usda.gov/oce/commodity/wasde/",
    "USDA Historical WASDE data: https://www.usda.gov/historical-wasde-report-data-3",
    "SHFE Daily Data: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
]

SOURCE_CANDIDATES: list[dict[str, Any]] = [
    {
        "product_family": "energy_oil",
        "driver_axis": "global_crude_refined_products_inventory",
        "source_name": "EIA Weekly Petroleum Status Report",
        "source_authority": "official_public_eia",
        "source_url": "https://www.eia.gov/petroleum/supply/weekly/",
        "monitor_frequency": "weekly",
        "expected_fields": "crude_stocks,product_stocks,refinery_runs,imports_exports",
        "china_directness": "global_macro_not_china_direct",
        "route_status": "source_contract_candidate_not_fetched",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "energy_oil",
        "driver_axis": "domestic_exchange_warehouse_member",
        "source_name": "SHFE/INE daily data and warehouse warrant route",
        "source_authority": "official_public_exchange",
        "source_url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
        "monitor_frequency": "daily",
        "expected_fields": "warehouse_warrant,member_rank,contract_reference",
        "china_directness": "domestic_exchange_context",
        "route_status": "endpoint_discovery_required_for_lu_fu_bu",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "base_metals",
        "driver_axis": "global_exchange_inventory",
        "source_name": "LME warehouse and stock reports",
        "source_authority": "official_public_lme",
        "source_url": "https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports",
        "monitor_frequency": "daily_or_monthly_by_report",
        "expected_fields": "closing_stocks,on_warrant,cancelled_warrants",
        "china_directness": "global_base_metal_context",
        "route_status": "source_contract_candidate_not_fetched",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "base_metals",
        "driver_axis": "domestic_exchange_warehouse_member",
        "source_name": "SHFE Daily Data",
        "source_authority": "official_public_exchange",
        "source_url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
        "monitor_frequency": "daily",
        "expected_fields": "warehouse_stock,member_rank,settlement_context",
        "china_directness": "domestic_exchange_context",
        "route_status": "source_contract_candidate_not_fetched",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "grains_oilseeds",
        "driver_axis": "global_supply_demand",
        "source_name": "USDA WASDE",
        "source_authority": "official_public_usda",
        "source_url": "https://www.usda.gov/oce/commodity/wasde/",
        "monitor_frequency": "monthly",
        "expected_fields": "corn,soybeans,oilseeds,supply_use,ending_stocks",
        "china_directness": "global_macro_partial_china_mapping",
        "route_status": "source_contract_candidate_not_fetched",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "grains_oilseeds",
        "driver_axis": "domestic_dce_inventory_member",
        "source_name": "DCE authorized API / vendor market data route",
        "source_authority": "authorized_exchange_api_candidate",
        "source_url": "https://pypi.org/project/dceapi/",
        "monitor_frequency": "daily_or_event",
        "expected_fields": "warehouse_receipt,member_rank,delivery_notice",
        "china_directness": "domestic_exchange_context",
        "route_status": "authorization_required",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "petrochem",
        "driver_axis": "energy_feedstock_macro",
        "source_name": "EIA petroleum data for feedstock context",
        "source_authority": "official_public_eia",
        "source_url": "https://www.eia.gov/petroleum/data.php/summary",
        "monitor_frequency": "weekly_monthly",
        "expected_fields": "crude_products_supply,stocks,refinery_runs",
        "china_directness": "global_macro_indirect",
        "route_status": "source_contract_candidate_not_fetched",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
    {
        "product_family": "petrochem",
        "driver_axis": "domestic_inventory_basis_third_party",
        "source_name": "AKShare/100ppi/Eastmoney chemical basis and inventory route",
        "source_authority": "third_party_forward",
        "source_url": "https://www.100ppi.com/sf/",
        "monitor_frequency": "daily",
        "expected_fields": "basis,inventory,spot_price",
        "china_directness": "domestic_third_party_not_official",
        "route_status": "third_party_monitor_only_not_selector",
        "active_fetch_validated": 0,
        "pit_dates": 0,
        "selector_allowed": 0,
    },
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


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


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    annual = _read_csv(STAGE541_ANNUAL)
    ladder = _read_csv(STAGE638_PRODUCT_LADDER)
    stage638_annual = _read_csv(STAGE638_ANNUAL)
    annual["product_vt_symbol"] = _str(annual, "product_vt_symbol")
    ladder["product_vt_symbol"] = _str(ladder, "product_vt_symbol")
    ladder["product_family"] = _str(ladder, "product_family")
    ladder["structural_bucket"] = _str(ladder, "structural_bucket")
    ladder["ladder_bucket"] = _str(ladder, "ladder_bucket")
    for column in ["year", "is_core_product", "trade_count"]:
        annual[column] = _num(annual, column).astype(int)
    annual["net_pnl"] = _num(annual, "net_pnl")
    return annual, ladder, stage638_annual


def _existing_source_evidence() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_path, product_col, status_col, family_col in [
        (STAGE629_ROUTE_STATUS, "product_vt_symbol", "fetch_status", "product_family"),
        (STAGE635_LH_FETCH, "product_vt_symbol", "fetch_status", "product_family"),
        (STAGE620_CONTRACT, "product_vt_symbol", "repair_action", "product_family"),
        (STAGE624_EVENT_LEDGER, "product_vt_symbol", "status", "product_family"),
    ]:
        frame = _read_csv(source_path, required=False)
        if frame.empty:
            continue
        frame["product_vt_symbol"] = _str(frame, product_col)
        frame["product_family"] = _str(frame, family_col)
        frame["status_value"] = _str(frame, status_col)
        frame["source_file"] = source_path.name
        for _, row in frame.iterrows():
            families = [item.strip() for item in str(row["product_family"]).split(",") if item.strip()]
            products = [item.strip() for item in str(row["product_vt_symbol"]).split(",") if item.strip()]
            if not families:
                families = [""]
            rows.append(
                {
                    "source_file": row["source_file"],
                    "product_family": families[0],
                    "product_vt_symbol": ",".join(products),
                    "status_value": row["status_value"],
                    "source_authority": str(row.get("source_authority", "")),
                    "source_class": str(row.get("source_class", "")),
                    "source_name": str(row.get("source_name", "")),
                    "active_fetch_validated": int(float(row.get("active_fetch_validated", 0) or 0)),
                    "usable_for_forward_monitor": int(float(row.get("usable_for_forward_monitor", 0) or 0)),
                    "usable_for_history_selector": int(float(row.get("usable_for_history_selector", 0) or 0)),
                    "paper_or_whitelist_allowed": int(float(row.get("paper_or_whitelist_allowed", 0) or 0)),
                }
            )
    return pd.DataFrame(rows)


def _build_top6_detail(annual: pd.DataFrame, ladder: pd.DataFrame) -> pd.DataFrame:
    ladder_cols = [
        "product_vt_symbol",
        "product_family",
        "structural_bucket",
        "ladder_bucket",
        "total_pnl",
        "candidate_materiality_pass",
        "max_abs_corr_to_p0",
        "tail_abs_corr_to_p0_composite",
        "watch_corr_pass",
        "deployable_new_slot_now",
    ]
    ladder_view = ladder[[column for column in ladder_cols if column in ladder.columns]].copy()
    frame = annual[annual["is_core_product"].eq(0)].merge(ladder_view, on="product_vt_symbol", how="left")
    frame["product_family"] = _str(frame, "product_family")
    frame["structural_bucket"] = _str(frame, "structural_bucket")
    frame = frame[frame["product_family"].ne("")].copy()
    top_rows: list[pd.DataFrame] = []
    for year, group in frame.groupby("year"):
        ranked = group.sort_values("net_pnl", ascending=False).head(TOP_N).copy()
        ranked["annual_top_rank"] = np.arange(1, len(ranked) + 1)
        top_rows.append(ranked)
    return pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()


def _build_source_backlog(existing_source: pd.DataFrame) -> pd.DataFrame:
    source = pd.DataFrame(SOURCE_CANDIDATES)
    if existing_source.empty:
        source["existing_rows"] = 0
        source["existing_active_fetch_rows"] = 0
        source["existing_forward_monitor_rows"] = 0
        source["existing_history_selector_rows"] = 0
    else:
        grouped = (
            existing_source.groupby("product_family", as_index=False)
            .agg(
                existing_rows=("source_file", "count"),
                existing_active_fetch_rows=("active_fetch_validated", "sum"),
                existing_forward_monitor_rows=("usable_for_forward_monitor", "sum"),
                existing_history_selector_rows=("usable_for_history_selector", "sum"),
                existing_paper_rows=("paper_or_whitelist_allowed", "sum"),
            )
        )
        source = source.merge(grouped, on="product_family", how="left")
        for column in [
            "existing_rows",
            "existing_active_fetch_rows",
            "existing_forward_monitor_rows",
            "existing_history_selector_rows",
            "existing_paper_rows",
        ]:
            source[column] = _num(source, column).astype(int)
    source["promotion_allowed"] = 0
    source["paper_allowed_now"] = 0
    source["trading_whitelist_allowed_now"] = 0
    return source


def _build_family_board(top6: pd.DataFrame, ladder: pd.DataFrame, source_backlog: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    ladder_family = ladder.groupby("product_family")
    for family in TARGET_FAMILIES:
        hits = top6[top6["product_family"].eq(family)].copy()
        products = sorted(set(hits["product_vt_symbol"].dropna().astype(str)))
        ladder_group = ladder_family.get_group(family) if family in ladder_family.groups else pd.DataFrame()
        source_rows = source_backlog[source_backlog["product_family"].eq(family)]
        annual_years = int(hits["year"].nunique()) if "year" in hits.columns else 0
        p0_hits = int(hits["structural_bucket"].eq("p0_reference_existing_slot").sum())
        high_corr_hits = int(hits["structural_bucket"].eq("reject_high_core_corr").sum())
        data_liq_reject_hits = int(hits["structural_bucket"].eq("reject_data_or_liquidity").sum())
        worklist_hits = int(
            hits["structural_bucket"].isin(
                ["p1_existing_worklist_source_tca_blocked", "p2_existing_forward_monitor", "observe_low_corr_but_weak_trend"]
            ).sum()
        )
        deployable_hits = int(_num(hits, "deployable_new_slot_now").sum()) if not hits.empty else 0
        total_pnl = float(hits["net_pnl"].sum()) if not hits.empty else 0.0
        avg_corr = float(_num(ladder_group, "max_abs_corr_to_p0", np.nan).mean()) if not ladder_group.empty else np.nan
        best_product = ""
        best_product_pnl = 0.0
        if not hits.empty:
            best = hits.sort_values("net_pnl", ascending=False).iloc[0]
            best_product = str(best["product_vt_symbol"])
            best_product_pnl = float(best["net_pnl"])
        if p0_hits > 0 and high_corr_hits + data_liq_reject_hits >= worklist_hits:
            judgement = "mostly_p0_or_high_corr_duplicate_not_new_slot"
        elif worklist_hits > 0:
            judgement = "some_monitor_relevance_but_not_annual_coverage"
        else:
            judgement = "source_candidate_only_no_selector"
        rows.append(
            {
                "product_family": family,
                "annual_top6_years_present": annual_years,
                "annual_top6_hits": int(len(hits)),
                "annual_top6_pnl_sum": total_pnl,
                "top6_products_seen": ",".join(products),
                "best_top6_product": best_product,
                "best_top6_product_pnl": best_product_pnl,
                "p0_reference_hits": p0_hits,
                "high_corr_reject_hits": high_corr_hits,
                "data_liquidity_reject_hits": data_liq_reject_hits,
                "worklist_monitor_hits": worklist_hits,
                "deployable_hits": deployable_hits,
                "family_products_in_ladder": int(ladder_group["product_vt_symbol"].nunique()) if not ladder_group.empty else 0,
                "candidate_source_rows": int(len(source_rows)),
                "official_source_candidate_rows": int(source_rows["source_authority"].astype(str).str.contains("official").sum()) if not source_rows.empty else 0,
                "active_fetch_validated_rows": int(_num(source_rows, "active_fetch_validated").sum()) if not source_rows.empty else 0,
                "pit_dates": int(_num(source_rows, "pit_dates").max()) if not source_rows.empty else 0,
                "existing_source_rows": int(_num(source_rows, "existing_rows").max()) if not source_rows.empty else 0,
                "existing_active_fetch_rows": int(_num(source_rows, "existing_active_fetch_rows").max()) if not source_rows.empty else 0,
                "existing_history_selector_rows": int(_num(source_rows, "existing_history_selector_rows").max()) if not source_rows.empty else 0,
                "avg_max_abs_corr_to_p0": avg_corr,
                "driver_judgement": judgement,
                "promotion_allowed": 0,
                "paper_allowed_now": 0,
                "trading_whitelist_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def _build_gates(family_board: pd.DataFrame, source_backlog: pd.DataFrame) -> pd.DataFrame:
    top_year_families = int(family_board["annual_top6_years_present"].gt(0).sum())
    source_candidate_families = int(family_board["candidate_source_rows"].gt(0).sum())
    active_fetch_families = int(family_board["active_fetch_validated_rows"].gt(0).sum())
    selector_rows = int(_num(family_board, "existing_history_selector_rows").sum())
    deployable = int(_num(family_board, "promotion_allowed").sum())
    paper = int(_num(family_board, "paper_allowed_now").sum())
    whitelist = int(_num(family_board, "trading_whitelist_allowed_now").sum())
    rows = [
        {
            "gate": "target_families_have_annual_hits",
            "passed": int(top_year_families == len(TARGET_FAMILIES)),
            "current": f"{top_year_families}/{len(TARGET_FAMILIES)}",
            "required": "all target families",
            "note": "Each repeated family has appeared in annual oracle top6.",
        },
        {
            "gate": "source_candidates_defined",
            "passed": int(source_candidate_families == len(TARGET_FAMILIES)),
            "current": f"{source_candidate_families}/{len(TARGET_FAMILIES)}",
            "required": "all target families",
            "note": "Every target family has at least one source candidate from external research.",
        },
        {
            "gate": "active_fetch_not_validated_yet",
            "passed": int(active_fetch_families == 0),
            "current": f"{active_fetch_families}/{len(TARGET_FAMILIES)}",
            "required": "0 for this stage",
            "note": "This board is a source gap map, not a fetch-validation stage.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "No history selector is unlocked by source candidates.",
        },
        {
            "gate": "mostly_duplicate_or_unvalidated",
            "passed": int(
                family_board["driver_judgement"].isin(
                    ["mostly_p0_or_high_corr_duplicate_not_new_slot", "source_candidate_only_no_selector"]
                ).sum()
                >= 3
            ),
            "current": ",".join(family_board["driver_judgement"].tolist()),
            "required": "no direct new slot",
            "note": "Most annual winner families are P0 duplicates/high corr or unvalidated sources.",
        },
        {
            "gate": "deployable_new_slot_zero",
            "passed": int(deployable == 0),
            "current": deployable,
            "required": 0,
            "note": "No family can become a deployable risk slot yet.",
        },
        {
            "gate": "paper_and_whitelist_zero",
            "passed": int(paper == 0 and whitelist == 0),
            "current": f"paper={paper},whitelist={whitelist}",
            "required": "0/0",
            "note": "No paper or trading whitelist rows are generated.",
        },
        {
            "gate": "target_effective_slots_still_not_met",
            "passed": int(CURRENT_EFFECTIVE_SLOTS < TARGET_EFFECTIVE_SLOTS and deployable == 0),
            "current": f"{CURRENT_EFFECTIVE_SLOTS}/{TARGET_EFFECTIVE_SLOTS}",
            "required": "fail closed",
            "note": "Effective risk-slot target is still unmet.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(family_board: pd.DataFrame, source_backlog: pd.DataFrame, top6: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage639 economic driver source gap board: sources identified, selector locked", fontsize=16)

    ax = axes[0, 0]
    x = np.arange(len(family_board))
    ax.bar(x - 0.24, family_board["p0_reference_hits"], width=0.16, label="P0 hits", color="#2b6cb0")
    ax.bar(x - 0.08, family_board["high_corr_reject_hits"], width=0.16, label="high corr", color="#e53e3e")
    ax.bar(x + 0.08, family_board["data_liquidity_reject_hits"], width=0.16, label="data/liquidity", color="#4a5568")
    ax.bar(x + 0.24, family_board["worklist_monitor_hits"], width=0.16, label="worklist/monitor", color="#9f7aea")
    ax.set_xticks(x)
    ax.set_xticklabels(family_board["product_family"], rotation=30, ha="right")
    ax.set_title("Annual top6 hit structure by family")
    ax.set_ylabel("top6 hits")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    ax.bar(x - 0.2, family_board["candidate_source_rows"], width=0.2, label="source candidates", color="#3182ce")
    ax.bar(x, family_board["official_source_candidate_rows"], width=0.2, label="official candidates", color="#38a169")
    ax.bar(x + 0.2, family_board["active_fetch_validated_rows"], width=0.2, label="active fetch validated", color="#dd6b20")
    ax.set_xticks(x)
    ax.set_xticklabels(family_board["product_family"], rotation=30, ha="right")
    ax.set_title("Source readiness gap")
    ax.set_ylabel("rows")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    scatter = family_board.copy()
    sizes = 80 + scatter["annual_top6_hits"].astype(float) * 30
    colors = ["#e53e3e" if "duplicate" in item else "#dd6b20" for item in scatter["driver_judgement"]]
    ax.scatter(scatter["avg_max_abs_corr_to_p0"], scatter["annual_top6_pnl_sum"], s=sizes, c=colors, alpha=0.75, edgecolor="white")
    for _, row in scatter.iterrows():
        ax.text(row["avg_max_abs_corr_to_p0"], row["annual_top6_pnl_sum"], row["product_family"], fontsize=9)
    ax.axvline(0.15, color="tab:orange", linestyle="--", linewidth=1)
    ax.set_title("Opportunity vs core-correlation: large opportunity is often not independent")
    ax.set_xlabel("avg max abs corr to P0")
    ax.set_ylabel("annual top6 pnl sum")

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    family_board: pd.DataFrame,
    source_backlog: pd.DataFrame,
    top6_detail: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage639 Economic Driver Source Gap Board Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: economic-driver/source feasibility board; no fetch, no strategy replay, no selector, no paper, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "Stage338 证明年度机会存在，但年度赢家多落在 P0 既有槽或高相关拒绝桶。本阶段把 `energy_oil/base_metals/grains_oilseeds/petrochem` 拆成经济驱动和可实盘采集源：EIA/LME/USDA/SHFE 等官方源可以形成 source contract 候选，但当前还没有 active fetch/PIT 样本/selector 预测力/TCA。因此这些家族只能进入 source backlog，不能成为新增风险槽。",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- target families: `{decision['target_families']}`",
        f"- source candidate rows: `{decision['source_candidate_rows']}`",
        f"- official source candidate rows: `{decision['official_source_candidate_rows']}`",
        f"- active fetch validated source rows: `{decision['active_fetch_validated_rows']}`",
        f"- deployable new slots: `{decision['deployable_new_slots']}`",
        f"- paper rows: `{decision['paper_rows']}`",
        f"- trading whitelist rows: `{decision['trading_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Family Driver Board",
        "",
        _md_table(
            family_board,
            columns=[
                "product_family",
                "annual_top6_years_present",
                "annual_top6_hits",
                "annual_top6_pnl_sum",
                "top6_products_seen",
                "p0_reference_hits",
                "high_corr_reject_hits",
                "data_liquidity_reject_hits",
                "worklist_monitor_hits",
                "candidate_source_rows",
                "official_source_candidate_rows",
                "active_fetch_validated_rows",
                "avg_max_abs_corr_to_p0",
                "driver_judgement",
            ],
        ),
        "",
        "## Source Backlog",
        "",
        _md_table(
            source_backlog,
            columns=[
                "product_family",
                "driver_axis",
                "source_name",
                "source_authority",
                "monitor_frequency",
                "china_directness",
                "route_status",
                "active_fetch_validated",
                "pit_dates",
                "selector_allowed",
            ],
        ),
        "",
        "## Annual Top6 Detail",
        "",
        _md_table(
            top6_detail.sort_values(["year", "annual_top_rank"]),
            columns=[
                "year",
                "annual_top_rank",
                "product_vt_symbol",
                "product_family",
                "net_pnl",
                "structural_bucket",
                "ladder_bucket",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
            ],
            max_rows=50,
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- `energy_oil/base_metals/grains_oilseeds/petrochem` 都有年度 top6 机会，也都能找到公开或授权 source 候选。",
        "- 但 source 候选不等于 selector：当前 active fetch validated 仍为 `0`，PIT 日期仍为 `0`，历史 selector 行仍为 `0`。",
        "- 多数年度机会与 P0 或高相关桶重叠，不能降低独立单槽风险。",
        "- 下一步如果继续，只能先做 source contract/fetch probe，而不是加入交易池。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    annual, ladder, _stage638_annual = _load()
    existing_source = _existing_source_evidence()
    top6_detail = _build_top6_detail(annual, ladder)
    source_backlog = _build_source_backlog(existing_source)
    family_board = _build_family_board(top6_detail, ladder, source_backlog)
    gates = _build_gates(family_board, source_backlog)

    decision = {
        "model_tag": MODEL_TAG,
        "decision": "economic_driver_source_gap_mapped_selector_locked",
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "target_families": len(TARGET_FAMILIES),
        "source_candidate_rows": int(len(source_backlog)),
        "official_source_candidate_rows": int(source_backlog["source_authority"].astype(str).str.contains("official").sum()),
        "active_fetch_validated_rows": int(_num(source_backlog, "active_fetch_validated").sum()),
        "families_with_annual_hits": int(family_board["annual_top6_years_present"].gt(0).sum()),
        "families_with_source_candidates": int(family_board["candidate_source_rows"].gt(0).sum()),
        "families_with_active_fetch": int(family_board["active_fetch_validated_rows"].gt(0).sum()),
        "deployable_new_slots": int(_num(family_board, "promotion_allowed").sum()),
        "paper_rows": int(_num(family_board, "paper_allowed_now").sum()),
        "trading_whitelist_rows": int(_num(family_board, "trading_whitelist_allowed_now").sum()),
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "family_board_path": str(FAMILY_BOARD_PATH),
        "source_backlog_path": str(SOURCE_BACKLOG_PATH),
        "top6_detail_path": str(TOP6_DETAIL_PATH),
        "chart_path": str(CHART_PATH),
    }

    family_board.to_csv(FAMILY_BOARD_PATH, index=False, encoding="utf-8-sig")
    source_backlog.to_csv(SOURCE_BACKLOG_PATH, index=False, encoding="utf-8-sig")
    top6_detail.to_csv(TOP6_DETAIL_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(generated_at, family_board, source_backlog, top6_detail, gates, decision)
    _write_chart(family_board, source_backlog, top6_detail, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
