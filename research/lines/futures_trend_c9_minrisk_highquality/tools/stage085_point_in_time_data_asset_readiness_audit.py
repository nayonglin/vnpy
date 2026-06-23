from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import zipfile
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage085"
MODEL_TAG = "stage085_point_in_time_data_asset_readiness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage085_c9_minrisk_point_in_time_data_asset_readiness_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage013_minrisk_clean_restore_true_engine as s013
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage085_point_in_time_data_asset_readiness_audit"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE027_DIR = LINE_DIR / "outputs" / "stage027_supply_demand_inventory_forensics"
STAGE028_DIR = LINE_DIR / "outputs" / "stage028_member_rank_position_forensics"
STAGE060_DIR = LINE_DIR / "outputs" / "stage060_relative_basis_shock_audit"
STAGE065_DIR = LINE_DIR / "outputs" / "stage065_tick_microstructure_asset_audit"
STAGE066_DIR = LINE_DIR / "outputs" / "stage066_tick_microstructure_expansion_attempt"
STAGE068_DIR = LINE_DIR / "outputs" / "stage068_initial_entry_tick_coverage_audit"
STAGE076_DIR = LINE_DIR / "outputs" / "stage076_data_exit_route_scorecard_audit"
STAGE080_DIR = LINE_DIR / "outputs" / "stage080_tick_transform_mismatch_attribution"
STAGE084_DIR = LINE_DIR / "outputs" / "stage084_fixed_capital_multistart_boundary_audit"

BACKTEST_OUTPUTS = EXAMPLE_DIR / "backtest_outputs"
DOWNLOADED_FUTURES = EXAMPLE_DIR / "downloaded_futures"
MEMBER_CACHE = BACKTEST_OUTPUTS / "external_domestic_member_rank_cache"
SUPPLY_CACHE = BACKTEST_OUTPUTS / "external_supply_demand_cache"
CFTC_CACHE = BACKTEST_OUTPUTS / "external_cftc_cot_cache"

CAPITAL = 150_000.0

CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

ROUTE_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_{MODEL_TAG}.csv"
ASSET_CATALOG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_catalog_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_data_gate_chart_{MODEL_TAG}.png"
ROUTE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_gate_heatmap_{MODEL_TAG}.png"
ASSET_CATALOG_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_catalog_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s013._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s013._safe_float(value, default=default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s013._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _latest_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_csv(CURVE_IN)
    if data.empty:
        raise RuntimeError(f"missing official curve: {CURVE_IN}")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "net_pnl",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    return data


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = pd.to_numeric(curve["account_equity"], errors="coerce")
    daily_ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = float(daily_ret.mean() / daily_ret.std(ddof=0) * np.sqrt(252)) if not daily_ret.empty and daily_ret.std(ddof=0) > 0 else np.nan
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": sharpe,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()
        ),
    }


def _file_record(path: Path, family: str) -> dict[str, Any]:
    rel = path.relative_to(REPO_DIR) if path.exists() and path.is_relative_to(REPO_DIR) else path
    size = path.stat().st_size if path.exists() else 0
    suffix = path.suffix.lower()
    rows = np.nan
    columns = ""
    min_date = ""
    max_date = ""
    if suffix == ".csv" and path.exists() and size < 80_000_000:
        try:
            sample = pd.read_csv(path, encoding="utf-8-sig", nrows=2000)
            rows = sum(1 for _ in path.open("rb")) - 1 if size < 20_000_000 else np.nan
            columns = ",".join(sample.columns.astype(str).tolist()[:20])
            for date_col in ["date", "datetime", "trading_day", "bar_datetime", "tick_datetime"]:
                if date_col in sample.columns:
                    parsed = pd.to_datetime(sample[date_col], errors="coerce")
                    if parsed.notna().any():
                        min_date = parsed.min().strftime("%Y-%m-%d")
                        max_date = parsed.max().strftime("%Y-%m-%d")
                    break
        except Exception as exc:  # pragma: no cover - defensive cataloging
            columns = f"read_error:{type(exc).__name__}"
    elif suffix == ".zip" and path.exists():
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
            columns = f"zip_members={len(names)}"
            rows = len(names)
        except Exception as exc:  # pragma: no cover
            columns = f"zip_error:{type(exc).__name__}"
    return {
        "family": family,
        "path": str(rel),
        "suffix": suffix,
        "size_bytes": int(size),
        "sample_rows_or_members": rows,
        "sample_columns_or_note": columns,
        "sample_min_date": min_date,
        "sample_max_date": max_date,
    }


def _catalog_assets() -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    roots = [
        (MEMBER_CACHE, "member_rank_cache"),
        (SUPPLY_CACHE, "basis_warehouse_cache"),
        (CFTC_CACHE, "cftc_cot_cache"),
    ]
    for root, family in roots:
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    records.append(_file_record(path, family))

    downloaded_families = {
        "tqsdk_stage449_459_861_minute": ["tqsdk_stage459", "stage449", "stage861", "stage448"],
        "tqsdk_tick_or_gap_backfill": ["tick", "stage900", "stage856", "stage859", "stage491", "stage498"],
    }
    if DOWNLOADED_FUTURES.exists():
        for family, needles in downloaded_families.items():
            matched = []
            for path in DOWNLOADED_FUTURES.rglob("*"):
                if not path.is_file():
                    continue
                lower = str(path).lower()
                if any(needle.lower() in lower for needle in needles):
                    matched.append(path)
            for path in sorted(matched)[:120]:
                records.append(_file_record(path, family))
            if len(matched) > 120:
                records.append(
                    {
                        "family": family,
                        "path": f"{DOWNLOADED_FUTURES.relative_to(REPO_DIR)}/... truncated",
                        "suffix": "multiple",
                        "size_bytes": int(sum(path.stat().st_size for path in matched[:120])),
                        "sample_rows_or_members": len(matched),
                        "sample_columns_or_note": f"catalog truncated at 120 of {len(matched)} files",
                        "sample_min_date": "",
                        "sample_max_date": "",
                    }
                )

    return pd.DataFrame(records)


def _stage_value(path: Path, column: str, default: Any = np.nan) -> Any:
    data = _read_csv(path)
    if data.empty or column not in data.columns:
        return default
    return data.iloc[0][column]


def _count_files(family: str, catalog: pd.DataFrame) -> int:
    if catalog.empty:
        return 0
    return int(catalog["family"].eq(family).sum())


def _route_records(asset_catalog: pd.DataFrame) -> list[dict[str, Any]]:
    stage065 = _latest_existing(
        STAGE065_DIR / "qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_summary_stage065_tick_microstructure_asset_audit_v1.csv"
    )
    stage066 = _latest_existing(
        STAGE066_DIR
        / "qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_summary_stage066_tick_microstructure_expansion_attempt_v1.csv"
    )
    stage068 = _latest_existing(
        STAGE068_DIR / "qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_summary_stage068_initial_entry_tick_coverage_audit_v1.csv"
    )
    stage076 = _latest_existing(
        STAGE076_DIR / "qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_summary_stage076_data_exit_route_scorecard_audit_v1.csv"
    )
    stage080 = _latest_existing(
        STAGE080_DIR / "qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_summary_stage080_tick_transform_mismatch_attribution_v1.csv"
    )
    stage084 = _latest_existing(
        STAGE084_DIR / "qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit_summary_stage084_fixed_capital_multistart_boundary_audit_v1.csv"
    )
    member_source = _latest_existing(
        STAGE028_DIR / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_source_summary_stage028_member_rank_position_forensics_v1.csv"
    )
    supply_features = _latest_existing(
        STAGE027_DIR / "qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_combined_external_signals_stage027_supply_demand_inventory_forensics_v1.csv"
    )
    basis_summary = _latest_existing(
        STAGE060_DIR / "qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_summary_stage060_relative_basis_shock_audit_v1.csv"
    )

    member_df = _read_csv(member_source) if member_source else pd.DataFrame()
    member_products = int(member_df["product"].nunique()) if not member_df.empty and "product" in member_df.columns else 0
    member_start = str(member_df["start_date"].min()) if not member_df.empty and "start_date" in member_df.columns else ""
    member_end = str(member_df["end_date"].max()) if not member_df.empty and "end_date" in member_df.columns else ""
    member_ready_days = int(pd.to_numeric(member_df.get("ready_days", pd.Series(dtype=float)), errors="coerce").sum()) if not member_df.empty else 0

    supply_df = _read_csv(supply_features) if supply_features else pd.DataFrame()
    supply_rows = int(len(supply_df)) if not supply_df.empty else 0
    supply_products = int(supply_df["product"].nunique()) if not supply_df.empty and "product" in supply_df.columns else 0

    def route(
        *,
        route_id: str,
        domain: str,
        data_family: str,
        local_asset_count: int,
        coverage_ready_count: float,
        coverage_total_count: float,
        prior_stage: str,
        prior_decision: str,
        point_in_time: int,
        preentry_or_event_time_visible: int,
        same_source_or_authorized: int,
        full_coverage: int,
        not_outcome_label: int,
        prior_not_closed: int,
        right_tail_protected: int,
        next_action: str,
        evidence_note: str,
    ) -> dict[str, Any]:
        coverage_pct = (
            float(coverage_ready_count) / float(coverage_total_count) * 100.0
            if coverage_total_count and np.isfinite(coverage_total_count)
            else np.nan
        )
        gate_values = [
            point_in_time,
            preentry_or_event_time_visible,
            same_source_or_authorized,
            full_coverage,
            not_outcome_label,
            prior_not_closed,
            right_tail_protected,
        ]
        rule_allowed = int(all(int(x) == 1 for x in gate_values))
        return {
            "route_id": route_id,
            "domain": domain,
            "data_family": data_family,
            "local_asset_count": local_asset_count,
            "coverage_ready_count": coverage_ready_count,
            "coverage_total_count": coverage_total_count,
            "coverage_pct": coverage_pct,
            "prior_stage": prior_stage,
            "prior_decision": prior_decision,
            "point_in_time": point_in_time,
            "preentry_or_event_time_visible": preentry_or_event_time_visible,
            "same_source_or_authorized": same_source_or_authorized,
            "full_coverage": full_coverage,
            "not_outcome_label": not_outcome_label,
            "prior_not_closed": prior_not_closed,
            "right_tail_protected": right_tail_protected,
            "rule_candidate_allowed": rule_allowed,
            "next_action": next_action,
            "evidence_note": evidence_note,
        }

    rows = [
        route(
            route_id="R1_authorized_orderbook_quote_depth",
            domain="microstructure",
            data_family="authorized_vendor_or_raw_exchange_tick_quote_depth",
            local_asset_count=0,
            coverage_ready_count=0,
            coverage_total_count=219,
            prior_stage="Stage080",
            prior_decision=str(_stage_value(stage080, "decision", "")) if stage080 else "",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=0,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=1,
            right_tail_protected=0,
            next_action="obtain_authorized_vendor_or_exchange_tick_quote_depth_then_fixed_full_coverage_audit",
            evidence_note="Tq dur0 tick exists but Stage080 rejects it as same-source transform; no authorized/raw exchange depth asset is present locally.",
        ),
        route(
            route_id="R2_reentry_tq_tick_microstructure_tca_only",
            domain="microstructure",
            data_family="tqsdk_reentry_tick",
            local_asset_count=_count_files("tqsdk_tick_or_gap_backfill", asset_catalog),
            coverage_ready_count=_safe_float(_stage_value(stage066, "microstructure_ready_count", 0), 0),
            coverage_total_count=_safe_float(_stage_value(stage066, "input_reentry_event_count", 54), 54),
            prior_stage="Stage066/067",
            prior_decision=str(_stage_value(stage066, "decision", "")) if stage066 else "",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=0,
            full_coverage=1,
            not_outcome_label=1,
            prior_not_closed=0,
            right_tail_protected=0,
            next_action="keep_as_tca_forward_watch_only_do_not_rule_without_authorized_source",
            evidence_note="Reentry tick coverage reached 54/54, but Stage067 stability failed and Stage080 rejects Tq as same-source rule source.",
        ),
        route(
            route_id="R3_initial_entry_tq_tick_coverage",
            domain="microstructure",
            data_family="tqsdk_initial_entry_tick",
            local_asset_count=_count_files("tqsdk_tick_or_gap_backfill", asset_catalog),
            coverage_ready_count=_safe_float(_stage_value(stage068, "microstructure_ready_count", 0), 0),
            coverage_total_count=_safe_float(_stage_value(stage068, "planned_initial_entry_count", 219), 219),
            prior_stage="Stage068/080",
            prior_decision=str(_stage_value(stage068, "decision", "")) if stage068 else "",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=0,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=1,
            right_tail_protected=0,
            next_action="do_not_expand_tq_for_rules_until_same_source_or_authorized_quote_depth_is_available",
            evidence_note="Initial-entry tick coverage was 5/219 at Stage068 and Tq transform is not same-source.",
        ),
        route(
            route_id="R4_stage449_raw_generation_open_quote",
            domain="execution_source",
            data_family="stage449_raw_generation_fields",
            local_asset_count=_count_files("tqsdk_stage449_459_861_minute", asset_catalog),
            coverage_ready_count=_safe_float(_stage_value(stage076, "same_source_price_authority_count", 219), 219),
            coverage_total_count=219,
            prior_stage="Stage074-077",
            prior_decision="stage077_r2_requires_same_source_tick_transform_no_rule",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=1,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=1,
            right_tail_protected=0,
            next_action="locate_stage449_generation_raw_tick_or_quote_fields_not_zero_volume_proxy_bars",
            evidence_note="Stage449/raw price authority explains official opens, but bars are zero-volume/OHLC-flat and no tick/orderbook fields were found.",
        ),
        route(
            route_id="R5_member_rank_position_point_in_time",
            domain="external_preentry",
            data_family="domestic_member_rank",
            local_asset_count=_count_files("member_rank_cache", asset_catalog),
            coverage_ready_count=member_ready_days,
            coverage_total_count=np.nan,
            prior_stage="Stage028/062/063",
            prior_decision="stage062_member_rank_data_engineering_first_no_rule",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=0,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=1,
            right_tail_protected=0,
            next_action="backfill_official_or_authorized_member_rank_2020_2022_and_exchange_gaps_before_rule_audit",
            evidence_note=f"Local cache has {member_products} products, {member_start}-{member_end}; prior DCE/CZCE/SHFE/GFEX route coverage remains incomplete.",
        ),
        route(
            route_id="R6_basis_warehouse_inventory_point_in_time",
            domain="external_preentry",
            data_family="basis_warehouse_inventory",
            local_asset_count=_count_files("basis_warehouse_cache", asset_catalog),
            coverage_ready_count=supply_rows,
            coverage_total_count=np.nan,
            prior_stage="Stage027/060",
            prior_decision="stage027_supply_demand_inventory_no_trade_rule",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=0,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=0,
            right_tail_protected=0,
            next_action="replace_or_validate_third_party_cache_with_official_granular_warehouse_inventory_basis_before_rule",
            evidence_note=f"Supply/basis cache exists and has {supply_rows} bound rows over {supply_products} products, but prior direct rule tests cut right tail or failed.",
        ),
        route(
            route_id="R7_cftc_cot_cross_market_context",
            domain="external_preentry",
            data_family="cftc_cot",
            local_asset_count=_count_files("cftc_cot_cache", asset_catalog),
            coverage_ready_count=_count_files("cftc_cot_cache", asset_catalog),
            coverage_total_count=7,
            prior_stage="not_bound_to_c9",
            prior_decision="not_yet_point_mapped_to_domestic_contracts",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=1,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=1,
            right_tail_protected=0,
            next_action="only_consider_after_domestic_contract_mapping_and_frequency_lag_spec_are_predeclared",
            evidence_note="CFTC zip cache exists for 2020-2026 but does not map directly to domestic commodity contracts or minute entry timing.",
        ),
        route(
            route_id="R8_stage496_product_trend_tstat",
            domain="external_preentry",
            data_family="completed_preclose_product_trend",
            local_asset_count=_count_files("tqsdk_stage449_459_861_minute", asset_catalog),
            coverage_ready_count=np.nan,
            coverage_total_count=np.nan,
            prior_stage="Stage049/052",
            prior_decision="stage052_product_trend_tstat_reaudit_no_rule",
            point_in_time=1,
            preentry_or_event_time_visible=1,
            same_source_or_authorized=1,
            full_coverage=0,
            not_outcome_label=1,
            prior_not_closed=0,
            right_tail_protected=0,
            next_action="keep_as_data_asset_only_do_not_rule_without_new_full_coverage_spec",
            evidence_note="Stage052 re-audit found insufficient completed-preclose coverage and adverse upper-bound behavior.",
        ),
        route(
            route_id="R9_account_layer_without_new_data",
            domain="account_layer",
            data_family="official_daily_curve_only",
            local_asset_count=1,
            coverage_ready_count=_safe_float(_stage_value(stage084, "mature_start_count", 90), 90),
            coverage_total_count=_safe_float(_stage_value(stage084, "monthly_start_count", 102), 102),
            prior_stage="Stage083/084",
            prior_decision=str(_stage_value(stage084, "decision", "")) if stage084 else "",
            point_in_time=1,
            preentry_or_event_time_visible=0,
            same_source_or_authorized=1,
            full_coverage=1,
            not_outcome_label=1,
            prior_not_closed=0,
            right_tail_protected=0,
            next_action="closed_stop_scanning_account_curve_without_new_data",
            evidence_note="Stage083/084 close volatility gate and fixed capital structures; no new minute or external information.",
        ),
    ]
    return rows


def _route_scorecard(asset_catalog: pd.DataFrame) -> pd.DataFrame:
    data = pd.DataFrame(_route_records(asset_catalog))
    gate_cols = [
        "point_in_time",
        "preentry_or_event_time_visible",
        "same_source_or_authorized",
        "full_coverage",
        "not_outcome_label",
        "prior_not_closed",
        "right_tail_protected",
    ]
    data["gate_pass_count"] = data[gate_cols].sum(axis=1)
    data["gate_total_count"] = len(gate_cols)
    data["readiness_score_pct"] = data["gate_pass_count"] / data["gate_total_count"] * 100.0
    return data.sort_values(["rule_candidate_allowed", "readiness_score_pct", "coverage_pct"], ascending=[False, False, False]).reset_index(drop=True)


def _summary(route_scorecard: pd.DataFrame, asset_catalog: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    official = _official_metrics(curve)
    allowed_count = int(route_scorecard["rule_candidate_allowed"].sum())
    top = route_scorecard.sort_values("readiness_score_pct", ascending=False).head(1)
    top_route = str(top.iloc[0]["route_id"]) if not top.empty else ""
    decision = "stage085_no_rule_ready_data_source_get_authorized_or_official_point_in_time_data"
    if allowed_count > 0:
        decision = "stage085_data_source_ready_for_frozen_readonly_candidate"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": official["end_equity"],
                "total_return_pct": official["total_return_pct"],
                "max_drawdown_pct": official["max_drawdown_pct"],
                "sharpe": official["sharpe"],
                "total_slippage": official["total_slippage"],
                "total_trade_count": official["total_trade_count"],
                "max_broker10_margin_to_equity_pct": official["max_broker10_margin_to_equity_pct"],
                "asset_family_count": int(asset_catalog["family"].nunique()) if not asset_catalog.empty else 0,
                "asset_file_count": int(len(asset_catalog)),
                "route_count": int(len(route_scorecard)),
                "rule_candidate_allowed_route_count": allowed_count,
                "top_route_by_readiness": top_route,
                "top_readiness_score_pct": float(top.iloc[0]["readiness_score_pct"]) if not top.empty else np.nan,
                "authorized_orderbook_local_asset_count": int(
                    route_scorecard.loc[
                        route_scorecard["route_id"].eq("R1_authorized_orderbook_quote_depth"), "local_asset_count"
                    ].iloc[0]
                ),
                "member_rank_cache_file_count": _count_files("member_rank_cache", asset_catalog),
                "basis_warehouse_cache_file_count": _count_files("basis_warehouse_cache", asset_catalog),
                "cftc_cache_file_count": _count_files("cftc_cot_cache", asset_catalog),
                "decision": decision,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, summary: pd.Series, route_scorecard: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [2, 1.1, 1.0]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", linewidth=1.25, label="official C9/15w")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.0, label="broker10 %")
    axes[2].axhline(100.0, color="#991b1b", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    title = (
        f"Stage085 official path remains baseline | route_allowed "
        f"{int(summary['rule_candidate_allowed_route_count'])}/{int(summary['route_count'])} | "
        f"decision {summary['decision']}"
    )
    axes[0].set_title(title)
    note = "\n".join(
        route_scorecard[["route_id", "rule_candidate_allowed", "readiness_score_pct"]]
        .head(5)
        .assign(readiness_score_pct=lambda d: d["readiness_score_pct"].map(lambda x: f"{x:.0f}%"))
        .astype(str)
        .agg(" ".join, axis=1)
        .tolist()
    )
    axes[0].text(0.01, 0.04, note, transform=axes[0].transAxes, fontsize=8, va="bottom", ha="left",
                 bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.75, "edgecolor": "#cbd5e1"})
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_heatmap(route_scorecard: pd.DataFrame) -> None:
    gate_cols = [
        "point_in_time",
        "preentry_or_event_time_visible",
        "same_source_or_authorized",
        "full_coverage",
        "not_outcome_label",
        "prior_not_closed",
        "right_tail_protected",
        "rule_candidate_allowed",
    ]
    data = route_scorecard.set_index("route_id")[gate_cols].astype(float)
    fig, ax = plt.subplots(figsize=(14, max(5, 0.42 * len(data.index) + 2)))
    im = ax.imshow(data.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(gate_cols)))
    ax.set_xticklabels(gate_cols, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            val = int(data.iloc[y, x])
            ax.text(x, y, str(val), ha="center", va="center", fontsize=8)
    ax.set_title("Stage085 route gate heatmap: 1=pass, 0=blocked")
    fig.colorbar(im, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(ROUTE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_asset_catalog(asset_catalog: pd.DataFrame) -> None:
    if asset_catalog.empty:
        return
    grouped = (
        asset_catalog.groupby("family", as_index=False)
        .agg(file_count=("path", "count"), size_mb=("size_bytes", lambda s: float(s.sum()) / 1_000_000.0))
        .sort_values("file_count", ascending=False)
    )
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    axes[0].barh(grouped["family"], grouped["file_count"], color="#2563eb")
    axes[0].invert_yaxis()
    axes[0].set_xlabel("file count")
    axes[0].set_title("Local data asset count")
    axes[1].barh(grouped["family"], grouped["size_mb"], color="#16a34a")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("size MB")
    axes[1].set_title("Local data asset size")
    for ax in axes:
        ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ASSET_CATALOG_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(route_scorecard: pd.DataFrame) -> None:
    data = route_scorecard.copy()
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = np.where(data["rule_candidate_allowed"].eq(1), "#16a34a", "#dc2626")
    ax.barh(data["route_id"], data["readiness_score_pct"], color=colors, alpha=0.85)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("readiness score %")
    ax.set_title("Stage085 next-action priorities")
    for idx, row in data.iterrows():
        ax.text(
            min(float(row["readiness_score_pct"]) + 1, 98),
            idx,
            str(row["next_action"])[:80],
            va="center",
            fontsize=8,
        )
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, route_scorecard: pd.DataFrame, asset_catalog: pd.DataFrame) -> None:
    row = summary.iloc[0]
    family_summary = (
        asset_catalog.groupby("family", as_index=False)
        .agg(file_count=("path", "count"), size_mb=("size_bytes", lambda s: float(s.sum()) / 1_000_000.0))
        .sort_values("file_count", ascending=False)
        if not asset_catalog.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage085 点时化数据资产 readiness 审计",
        "",
        f"- 生成时间：`{row['created_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读数据源闸门审计；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API。",
        "- 固定范围：盘口/quote/depth、Stage449/raw 生成端、会员持仓、仓单/库存/基差、CFTC COT、Stage496/861、账户层既有路径。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Route Scorecard",
        "",
        _md_table(route_scorecard),
        "",
        "## Asset Family Summary",
        "",
        _md_table(family_summary),
        "",
        "## Visual Outputs",
        "",
        f"- official path/data gate chart：`{OFFICIAL_PATH_CHART_OUT}`",
        f"- route gate heatmap：`{ROUTE_HEATMAP_OUT}`",
        f"- asset catalog chart：`{ASSET_CATALOG_CHART_OUT}`",
        f"- next action chart：`{NEXT_ACTION_CHART_OUT}`",
        "",
        "## Decision",
        "",
        f"- 决策：`{row['decision']}`",
        "- 主结论：本地有不少数据资产，但没有一个 route 同时通过同源/授权、覆盖、右尾保护和既有失败边界四类 gate。",
        "- 过拟合反思：本阶段不生成规则，避免从历史亏损 cohort、maxDD episode 或账户曲线反推；若绕过数据 gate 继续扫阈值就是过拟合。",
        "- 继续价值：有，但价值集中到数据工程。优先级是取得授权盘口/quote/depth 或找到 Stage449/raw 真实 open/quote 字段；会员持仓/仓单/基差也要先补官方/授权覆盖和点时化。",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _prepare_official_curve()
    asset_catalog = _catalog_assets()
    route_scorecard = _route_scorecard(asset_catalog)
    summary = _summary(route_scorecard, asset_catalog, curve)

    _write_csv(asset_catalog, ASSET_CATALOG_OUT)
    _write_csv(route_scorecard, ROUTE_SCORECARD_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_official_path(curve, summary.iloc[0], route_scorecard)
    _plot_route_heatmap(route_scorecard)
    _plot_asset_catalog(asset_catalog)
    _plot_next_action(route_scorecard)
    _write_report(summary, route_scorecard, asset_catalog)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
