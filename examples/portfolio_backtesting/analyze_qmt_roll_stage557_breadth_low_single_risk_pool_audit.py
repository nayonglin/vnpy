from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO  # noqa: E402


MODEL_TAG = "stage557_breadth_low_single_risk_pool_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage557_breadth_low_single_risk_pool_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = s551.ACCOUNT_CAPITAL
SLEEVE_CAPITAL = s551.SLEEVE_CAPITAL
CONTROL = s551.CONTROL
START_TRADE_DT = datetime(2021, 1, 1)
BROKER_MARGIN_MULTIPLIER = s551.BROKER_MARGIN_MULTIPLIER
COST_MULTIPLIERS = s551.COST_MULTIPLIERS

STAGE256_TOP6 = "dynamic_prevtop6_r050_pc15_maxpos3"
STAGE556_TAG = "stage556_stage252_whitelist_guard_fixed_replay_v1"
STAGE556_PREFIX = "qmt_roll_stage556_stage252_whitelist_guard_fixed_replay"
STAGE556_COMBINED_DAILY_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_combined_daily_{STAGE556_TAG}.csv"
STAGE556_SUMMARY_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_summary_{STAGE556_TAG}.csv"
STAGE556_COST_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_cost_stress_{STAGE556_TAG}.csv"
STAGE556_ROLLING_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_rolling_holding_{STAGE556_TAG}.csv"
STAGE556_WINDOW_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_window_metrics_{STAGE556_TAG}.csv"
STAGE556_SATELLITE_DAILY_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_satellite_daily_{STAGE556_TAG}.csv"

UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_noncore_commodity_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_eligibility_{MODEL_TAG}.csv"
SELECTION_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_selection_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_margin_daily_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_FAMILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_family_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
ENTRY_SNAPSHOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_snapshots_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class BreadthSpec:
    variant: str
    selector_mode: str
    label: str
    risk_multiplier: float
    family_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    corr_start: float
    corr_full: float
    corr_floor: float
    note: str


SPECS: tuple[BreadthSpec, ...] = (
    BreadthSpec(
        "breadth_all_noncore_r020_famcap20_corr5075_maxpos8",
        "all_noncore",
        "Stage526 + all noncore breadth sleeve r020 familycap20 corr50/75 maxpos8",
        0.20,
        0.20,
        8,
        0.20,
        0.50,
        0.75,
        0.40,
        "不做年度选品，所有非核心商品都可新开仓；单笔/同族风险压低，验证纯扩池是否能自然抓到年度趋势。",
    ),
    BreadthSpec(
        "breadth_prevpos_r020_famcap20_corr5075_maxpos8",
        "prev_year_positive",
        "Stage526 + prev-year positive breadth sleeve r020 familycap20 corr50/75 maxpos8",
        0.20,
        0.20,
        8,
        0.20,
        0.50,
        0.75,
        0.40,
        "只允许上一年单品种真实账本为正的非核心商品新开仓；不限制TopN，验证宽池选品是否优于纯扩池。",
    ),
    BreadthSpec(
        "breadth_prevpos_r015_famcap15_corr5075_maxpos10",
        "prev_year_positive",
        "Stage526 + conservative prev-year positive breadth sleeve r015 familycap15 corr50/75 maxpos10",
        0.15,
        0.15,
        10,
        0.15,
        0.50,
        0.75,
        0.40,
        "更低单笔风险和同族cap，允许更多并发；验证分散体验是否能改善3/6个月持有感受。",
    ),
)


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _as_float(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(frame.get(column, default), errors="coerce").fillna(default).astype(float)


def _product_family_map(universe: pd.DataFrame, family: pd.DataFrame) -> dict[str, str]:
    frame = universe[["product_vt_symbol", "exchange"]].copy()
    fmap = family[["product_vt_symbol", "product_family"]].drop_duplicates("product_vt_symbol")
    frame = frame.merge(fmap, on="product_vt_symbol", how="left")
    frame["product_family"] = frame["product_family"].fillna(frame["exchange"].astype(str))
    return dict(zip(frame["product_vt_symbol"].astype(str), frame["product_family"].astype(str)))


def _family_cluster_map(universe: pd.DataFrame, family: pd.DataFrame) -> str:
    mapping = _product_family_map(universe, family)
    rows: set[str] = set()
    for product_vt_symbol, cluster in mapping.items():
        if "." not in product_vt_symbol:
            continue
        symbol, exchange = product_vt_symbol.split(".", 1)
        rows.add(f"{product_vt_symbol}={cluster}")
        rows.add(f"{symbol.lower()}.{exchange.upper()}={cluster}")
        rows.add(f"{symbol.upper()}.{exchange.upper()}={cluster}")
    return ",".join(sorted(rows))


def _build_universe_and_eligibility() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    universe, summary, annual, family = s551._load_inputs()
    noncore = s551._noncore_commodity_products(universe, summary)
    universe_out = universe[universe["product_vt_symbol"].isin(noncore)].copy()
    universe_out.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe_out.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")

    family_map = _product_family_map(universe_out, family)
    base_products = summary[summary["product_vt_symbol"].isin(noncore)][
        ["product_vt_symbol", "exchange", "product", "core_daily_pnl_corr"]
    ].copy()
    rows: list[dict[str, Any]] = []
    eligibility_rows: list[dict[str, Any]] = []

    for spec in SPECS:
        for year in s551.YEARS:
            prev_year = int(year) - 1
            previous = annual[
                annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(prev_year)
            ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "prev_year_pnl"})
            current = annual[
                annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(year)
            ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "future_year_single_product_pnl"})
            table = base_products.merge(previous, on="product_vt_symbol", how="left").merge(
                current, on="product_vt_symbol", how="left"
            )
            table["prev_year_pnl"] = _as_float(table, "prev_year_pnl")
            table["future_year_single_product_pnl"] = _as_float(table, "future_year_single_product_pnl")
            table["product_family"] = table["product_vt_symbol"].astype(str).map(family_map).fillna(table["exchange"].astype(str))
            table["core_daily_pnl_corr"] = _as_float(table, "core_daily_pnl_corr")
            if spec.selector_mode == "all_noncore":
                selected = table.sort_values(["product_vt_symbol"]).copy()
            elif spec.selector_mode == "prev_year_positive":
                selected = table[table["prev_year_pnl"] > 0.0].sort_values(
                    ["prev_year_pnl", "product_vt_symbol"], ascending=[False, True]
                ).copy()
            else:
                raise ValueError(f"unknown selector mode: {spec.selector_mode}")

            products = selected["product_vt_symbol"].astype(str).tolist()
            family_counts = selected["product_family"].astype(str).value_counts()
            rows.append(
                {
                    "variant": spec.variant,
                    "selector_mode": spec.selector_mode,
                    "year": int(year),
                    "prev_year": prev_year,
                    "selected_count": int(len(selected)),
                    "family_count": int(selected["product_family"].nunique()) if not selected.empty else 0,
                    "family_max_count": int(family_counts.max()) if not family_counts.empty else 0,
                    "selected_products": ",".join(products),
                    "selected_families": ",".join(sorted(selected["product_family"].dropna().astype(str).unique())),
                    "prev_year_pnl_sum": float(selected["prev_year_pnl"].sum()) if not selected.empty else 0.0,
                    "future_year_single_product_pnl_sum": float(selected["future_year_single_product_pnl"].sum())
                    if not selected.empty
                    else 0.0,
                    "positive_selected_count": int((selected["future_year_single_product_pnl"] > 0.0).sum())
                    if not selected.empty
                    else 0,
                    "oracle6_overlap": int(selected["product_vt_symbol"].isin(s551.ORACLE6).sum()) if not selected.empty else 0,
                    "avg_abs_core_corr": float(selected["core_daily_pnl_corr"].abs().mean()) if not selected.empty else 0.0,
                    "max_abs_core_corr": float(selected["core_daily_pnl_corr"].abs().max()) if not selected.empty else 0.0,
                }
            )
            if spec.selector_mode != "all_noncore":
                for rank, row in enumerate(selected.itertuples(index=False), start=1):
                    eligibility_rows.append(
                        {
                            "strategy": spec.variant,
                            "eval_date": f"{int(year)}-01-01",
                            "product_vt_symbol": str(row.product_vt_symbol),
                            "score": float(len(selected) - rank + 1),
                            "score_rank": int(rank),
                            "rank": int(rank),
                            "top_n": int(len(selected)),
                            "selector_mode": spec.selector_mode,
                            "source_prev_year": prev_year,
                            "prev_year_pnl": float(row.prev_year_pnl),
                            "product_family": str(row.product_family),
                        }
                    )

    selection = pd.DataFrame(rows)
    eligibility = pd.DataFrame(eligibility_rows)
    selection.to_csv(SELECTION_AUDIT_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    return universe_out, family, selection


def _sleeve_overrides(spec: BreadthSpec, family_cluster_map: str) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        **s513._c3_overrides(START_TRADE_DT),
        "product_universe_csv_path": str(UNIVERSE_PATH),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        "enable_risk_cluster_margin_cap": True,
        "risk_cluster_margin_cap_ratio": float(spec.family_cap_ratio),
        "risk_cluster_target_clusters": "",
        "risk_cluster_map": family_cluster_map,
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": float(spec.corr_start),
        "same_direction_correlation_gate_full": float(spec.corr_full),
        "same_direction_correlation_gate_weight_floor": float(spec.corr_floor),
        "enable_ai_product_pool_filter": False,
    }
    if spec.selector_mode != "all_noncore":
        overrides.update(
            {
                "enable_ai_product_pool_filter": True,
                "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
                "ai_product_pool_strategy": spec.variant,
                "ai_product_pool_use_next_trade_date_for_entry": True,
            }
        )
    return overrides


def _run_breadth_sleeve(
    spec: BreadthSpec,
    metadata: dict[str, Any],
    family_cluster_map: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    preload_start = max(PRELOAD_START_DT, START_TRADE_DT - timedelta(days=365))
    _, open_map = s506.s501._seed_proxy_maps()
    engine = s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=SLEEVE_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=_sleeve_overrides(spec, family_cluster_map),
    )
    setting.update(
        {
            "capital_base": SLEEVE_CAPITAL,
            "sizing_equity_cap": SLEEVE_CAPITAL,
            "max_capital_usage_ratio": 0.95,
            "enable_incremental_margin_budget_gate": True,
            "incremental_margin_budget_gate_usage_ratio": 0.95,
            "incremental_margin_budget_gate_min_openable_candidates": 1,
            "incremental_margin_budget_gate_protected_selection_rank": 0,
        }
    )
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty sleeve daily: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= s551.START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["sleeve_equity"] = SLEEVE_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["selector_mode"] = spec.selector_mode
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["family_cap_ratio"] = spec.family_cap_ratio
    daily["max_concurrent_positions"] = spec.max_concurrent_positions
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["corr_start"] = spec.corr_start
    daily["corr_full"] = spec.corr_full
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if not positions.empty:
        positions["variant"] = spec.variant
        positions["combo_variant"] = spec.variant
        positions["label"] = spec.label
        positions["selector_mode"] = spec.selector_mode
        positions["risk_multiplier"] = spec.risk_multiplier
        positions["family_cap_ratio"] = spec.family_cap_ratio
        positions["max_concurrent_positions"] = spec.max_concurrent_positions

    snapshots = pd.DataFrame(getattr(engine.strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
        snapshots["selector_mode"] = spec.selector_mode
        snapshots["risk_multiplier"] = spec.risk_multiplier
        snapshots["family_cap_ratio"] = spec.family_cap_ratio
    return daily, positions, snapshots


def _combine_with_core(
    control_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    satellite_margin_daily: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = [control_daily.copy()]
    spec_map = {spec.variant: spec for spec in SPECS}
    for variant, sat in satellite_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        core = control_daily.copy().sort_values("date")
        sat_part = sat[["date", "net_pnl", "slippage", "trade_count", "sleeve_equity"]].rename(
            columns={
                "net_pnl": "satellite_net_pnl",
                "slippage": "satellite_slippage",
                "trade_count": "satellite_trade_count",
            }
        )
        margin_source = satellite_margin_daily[satellite_margin_daily["variant"].eq(variant)].copy()
        if margin_source.empty:
            margin_part = pd.DataFrame(
                columns=["date", "satellite_margin_exact", "satellite_active_contracts", "satellite_active_products"]
            )
        else:
            margin_part = margin_source[["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]].rename(
                columns={
                    "c3_margin_exact": "satellite_margin_exact",
                    "c3_active_contracts": "satellite_active_contracts",
                    "c3_active_products": "satellite_active_products",
                }
            )
        merged = core.merge(sat_part, on="date", how="left").merge(margin_part, on="date", how="left")
        for column in [
            "satellite_net_pnl",
            "satellite_slippage",
            "satellite_trade_count",
            "satellite_margin_exact",
            "satellite_active_contracts",
            "satellite_active_products",
        ]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["core_total_net_pnl"] = pd.to_numeric(merged["total_net_pnl"], errors="coerce").fillna(0.0)
        merged["core_total_slippage"] = pd.to_numeric(merged["total_slippage"], errors="coerce").fillna(0.0)
        merged["core_total_margin_exact"] = pd.to_numeric(merged["total_margin_exact"], errors="coerce").fillna(0.0)
        merged["total_net_pnl"] = merged["core_total_net_pnl"] + merged["satellite_net_pnl"]
        merged["total_slippage"] = merged["core_total_slippage"] + merged["satellite_slippage"]
        merged["trade_count"] = pd.to_numeric(merged["trade_count"], errors="coerce").fillna(0.0) + merged[
            "satellite_trade_count"
        ]
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["core_total_margin_exact"] + merged["satellite_margin_exact"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        merged["variant"] = variant
        merged["combo_variant"] = variant
        merged["label"] = spec.label
        merged["selector_mode"] = spec.selector_mode
        merged["risk_multiplier"] = spec.risk_multiplier
        merged["family_cap_ratio"] = spec.family_cap_ratio
        merged["max_concurrent_positions"] = spec.max_concurrent_positions
        merged["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _load_stage256_reference() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = _read_csv(STAGE556_COMBINED_DAILY_IN)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["variant"].isin([CONTROL, STAGE256_TOP6])].copy()
    summary = _read_csv(STAGE556_SUMMARY_IN)
    summary = summary[summary["variant"].isin([CONTROL, STAGE256_TOP6])].copy()
    cost = _read_csv(STAGE556_COST_IN)
    cost = cost[cost["variant"].isin([CONTROL, STAGE256_TOP6])].copy()
    rolling = _read_csv(STAGE556_ROLLING_IN)
    rolling = rolling[rolling["variant"].isin([CONTROL, STAGE256_TOP6])].copy()
    window = _read_csv(STAGE556_WINDOW_IN)
    window = window[window["variant"].isin([CONTROL, STAGE256_TOP6])].copy()
    sat = _read_csv(STAGE556_SATELLITE_DAILY_IN)
    sat["date"] = pd.to_datetime(sat["date"], errors="coerce").dt.normalize()
    sat = sat[sat["variant"].eq(STAGE256_TOP6)].copy()
    return daily, summary, cost, rolling, window, sat


def _entry_summary(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty:
        return pd.DataFrame()
    frame = snapshots.copy()
    for column in [
        "selected_volume",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "remaining_position_slots",
        "risk_cluster_selected_volume_before",
        "risk_cluster_selected_volume",
    ]:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    status = frame.get("candidate_status", pd.Series("", index=frame.index)).astype(str)
    reason = frame.get("skip_reason", pd.Series("", index=frame.index)).astype(str)
    frame["_is_ai_blocked"] = reason.eq("ai_product_pool_blocked").astype(int)
    frame["_is_cluster_capped"] = (
        frame["risk_cluster_selected_volume_before"] > frame["risk_cluster_selected_volume"]
    ).astype(int)
    rows: list[dict[str, Any]] = []
    for variant, group in frame.groupby("variant", sort=False):
        group_status = status.loc[group.index]
        group_reason = reason.loc[group.index]
        rows.append(
            {
                "variant": variant,
                "candidate_count": int(len(group)),
                "open_candidate_count": int((group_status == "open").sum()),
                "sizing_zero_count": int((group_reason == "sizing_zero_volume").sum()),
                "concurrent_limit_count": int((group_reason == "concurrent_limit").sum()),
                "ai_blocked_count": int(group["_is_ai_blocked"].sum()),
                "cluster_capped_count": int(group["_is_cluster_capped"].sum()),
                "avg_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].mean()),
                "p10_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].quantile(0.10)),
                "max_same_direction_corr": float(group["same_direction_correlation_max_corr"].max()),
                "avg_same_direction_corr": float(group["same_direction_correlation_avg_corr"].mean()),
                "selected_volume_sum": float(group["selected_volume"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _family_harvest(product_harvest: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    if product_harvest.empty:
        return pd.DataFrame()
    fmap = family[["product_vt_symbol", "product_family"]].drop_duplicates("product_vt_symbol")
    frame = product_harvest.merge(fmap, on="product_vt_symbol", how="left")
    frame["product_family"] = frame["product_family"].fillna("unknown")
    return (
        frame.groupby(["variant", "year", "product_family"], as_index=False)
        .agg(
            satellite_family_net_pnl=("satellite_product_net_pnl", "sum"),
            active_days=("active_days", "sum"),
            max_margin=("max_margin", "max"),
            product_count=("product_vt_symbol", "nunique"),
        )
        .sort_values(["variant", "year", "satellite_family_net_pnl"], ascending=[True, True, False])
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    product_harvest: pd.DataFrame,
    selection: pd.DataFrame,
    entry_summary: pd.DataFrame,
) -> dict[str, Any]:
    summary_map = {str(row["variant"]): row for _, row in summary.iterrows()}
    control = summary_map[CONTROL]
    top6 = summary_map.get(STAGE256_TOP6, {})
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")
    rolling_pivot = rolling.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    r63_control = _safe_float(rolling_pivot.loc[CONTROL, 63]) if CONTROL in rolling_pivot.index and 63 in rolling_pivot else 0.0
    r126_control = _safe_float(rolling_pivot.loc[CONTROL, 126]) if CONTROL in rolling_pivot.index and 126 in rolling_pivot else 0.0
    r63_top6 = _safe_float(rolling_pivot.loc[STAGE256_TOP6, 63]) if STAGE256_TOP6 in rolling_pivot.index and 63 in rolling_pivot else 0.0
    r126_top6 = _safe_float(rolling_pivot.loc[STAGE256_TOP6, 126]) if STAGE256_TOP6 in rolling_pivot.index and 126 in rolling_pivot else 0.0

    sat_map = {
        str(row["variant"]): row
        for _, row in satellite_summary.iterrows()
    }
    entry_map = {
        str(row["variant"]): row
        for _, row in entry_summary.iterrows()
    } if not entry_summary.empty else {}

    ranked: list[dict[str, Any]] = []
    for spec in SPECS:
        row = summary_map.get(spec.variant)
        if row is None:
            continue
        two_dd = _safe_float(cost2.loc[spec.variant, "max_dd_pct"]) if spec.variant in cost2.index else 0.0
        three_dd = _safe_float(cost3.loc[spec.variant, "max_dd_pct"]) if spec.variant in cost3.index else 0.0
        h63 = _safe_float(rolling_pivot.loc[spec.variant, 63]) if spec.variant in rolling_pivot.index and 63 in rolling_pivot else 0.0
        h126 = _safe_float(rolling_pivot.loc[spec.variant, 126]) if spec.variant in rolling_pivot.index and 126 in rolling_pivot else 0.0
        sat = sat_map.get(spec.variant, {})
        entry = entry_map.get(spec.variant, {})
        satellite_pnl = _safe_float(sat.get("sleeve_total_pnl", 0.0))
        product_part = product_harvest[product_harvest["variant"].eq(spec.variant)].copy()
        total_abs_product_pnl = float(product_part["satellite_product_net_pnl"].abs().sum()) if not product_part.empty else 0.0
        top_product_share = (
            float(product_part["satellite_product_net_pnl"].abs().max() / total_abs_product_pnl * 100.0)
            if total_abs_product_pnl > 1e-9 and not product_part.empty
            else 0.0
        )
        selector_rows = selection[selection["variant"].eq(spec.variant)]
        avg_selected_count = float(selector_rows["selected_count"].mean()) if not selector_rows.empty else 0.0
        avg_family_count = float(selector_rows["family_count"].mean()) if not selector_rows.empty else 0.0
        no_degrade_vs_stage526 = bool(
            _safe_float(row["total_return_pct"]) >= _safe_float(control["total_return_pct"])
            and _safe_float(row["max_dd_pct"]) >= _safe_float(control["max_dd_pct"])
            and _safe_float(row["ulcer_pct"]) <= _safe_float(control["ulcer_pct"])
            and _safe_float(row["max_broker10_margin_to_equity_pct"]) <= 100.0
            and int(row["days_over_100pct"]) == 0
            and two_dd >= -40.0
            and h63 >= r63_control
            and h126 >= r126_control
        )
        top6_available = bool(len(top6) > 0) if hasattr(top6, "__len__") else bool(top6)
        better_than_top6_experience = bool(
            (not top6_available)
            or (
                h63 >= r63_top6
                and h126 >= r126_top6
                and _safe_float(row["max_dd_pct"]) >= _safe_float(top6.get("max_dd_pct", -999.0))
            )
        )
        materiality_pass = bool(
            satellite_pnl >= max(ACCOUNT_CAPITAL * 0.01, SLEEVE_CAPITAL * 0.10)
            and (h63 - r63_control) >= 0.25
            and (h126 - r126_control) >= 0.25
        )
        broad_direction_pass = bool(no_degrade_vs_stage526 and satellite_pnl > 0.0 and better_than_top6_experience)
        soft_score = (
            (_safe_float(row["total_return_pct"]) - _safe_float(control["total_return_pct"]))
            + (_safe_float(row["max_dd_pct"]) - _safe_float(control["max_dd_pct"])) * 20.0
            + (_safe_float(control["ulcer_pct"]) - _safe_float(row["ulcer_pct"])) * 15.0
            + (h63 - r63_control) * 8.0
            + (h126 - r126_control) * 8.0
            + satellite_pnl / ACCOUNT_CAPITAL * 100.0
            - top_product_share * 0.05
        )
        ranked.append(
            {
                "variant": spec.variant,
                "selector_mode": spec.selector_mode,
                "total_return_pct": _safe_float(row["total_return_pct"]),
                "return_vs_stage526_pct": _safe_float(row["return_vs_stage526_pct"]),
                "max_dd_pct": _safe_float(row["max_dd_pct"]),
                "ulcer_pct": _safe_float(row["ulcer_pct"]),
                "sharpe": _safe_float(row["sharpe"]),
                "two_x_max_dd_pct": two_dd,
                "three_x_max_dd_pct": three_dd,
                "holding63_p05_return_pct": h63,
                "holding126_p05_return_pct": h126,
                "holding63_p05_improvement_vs_stage526_pp": h63 - r63_control,
                "holding126_p05_improvement_vs_stage526_pp": h126 - r126_control,
                "holding63_p05_improvement_vs_top6_pp": h63 - r63_top6,
                "holding126_p05_improvement_vs_top6_pp": h126 - r126_top6,
                "satellite_total_pnl": satellite_pnl,
                "avg_selected_count": avg_selected_count,
                "avg_family_count": avg_family_count,
                "top_product_abs_share_pct": top_product_share,
                "candidate_count": int(_safe_float(entry.get("candidate_count", 0.0))),
                "cluster_capped_count": int(_safe_float(entry.get("cluster_capped_count", 0.0))),
                "avg_corr_gate_weight": _safe_float(entry.get("avg_corr_gate_weight", 1.0), 1.0),
                "no_degrade_vs_stage526": int(no_degrade_vs_stage526),
                "better_than_stage256_top6_experience": int(better_than_top6_experience),
                "materiality_pass": int(materiality_pass),
                "broad_direction_pass": int(broad_direction_pass),
                "soft_score": soft_score,
            }
        )
    ranked = sorted(
        ranked,
        key=lambda item: (
            item["broad_direction_pass"],
            item["no_degrade_vs_stage526"],
            item["materiality_pass"],
            item["soft_score"],
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else {}
    return {
        "stage": "Stage257",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "breadth_low_single_risk_next_validation_candidate"
        if best and int(best.get("broad_direction_pass", 0)) == 1
        else "breadth_low_single_risk_not_promotion",
        "baseline": CONTROL,
        "stage256_reference": STAGE256_TOP6,
        "hypothesis": (
            "减少单笔风险、扩大非核心商品池，并用同产品族cap与同向相关性闸门控制集中风险。"
            "目标不是命中固定Oracle产品，而是每年让一部分独立趋势自然贡献。"
        ),
        "predeclared_profiles": [_json_safe(spec.__dict__) for spec in SPECS],
        "pass_definition": (
            "方向通过要求：相对Stage526正常成本收益/回撤/Ulcer/3月p05/6月p05不劣化、2x成本回撤仍在-40%以内、"
            "broker10保证金不穿100%、卫星PnL为正，并且3/6个月体验和回撤不弱于Stage256修复后top6。"
        ),
        "best_variant": _json_safe(best),
        "ranked": _json_safe(ranked),
        "professional_judgement": (
            "如果宽池能胜出，说明选品不必靠年度TopN，组合结构更本质；"
            "如果只是不劣化但收益材料性不足，说明扩池可作为监控/经验，但还不能替代Stage526主候选。"
        ),
        "next_step": (
            "若通过，下一步只做语义/材料性/单年单族剔除，不扫risk/cap/corr小数；"
            "若失败，停止宽池风险结构救参，转向真正外生forward状态或执行层降摩擦。"
        ),
    }


def _plot(
    comparison_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    family_harvest: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    color_map = {
        CONTROL: "#111827",
        STAGE256_TOP6: "#7c3aed",
        "breadth_all_noncore_r020_famcap20_corr5075_maxpos8": "#2563eb",
        "breadth_prevpos_r020_famcap20_corr5075_maxpos8": "#059669",
        "breadth_prevpos_r015_famcap15_corr5075_maxpos10": "#dc2626",
    }
    fig, axes = plt.subplots(3, 2, figsize=(18, 13))
    ax_equity, ax_dd, ax_sat, ax_hold, ax_family, ax_cost = axes.flatten()

    for variant, frame in comparison_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(ordered["date"], ordered["account_equity"], label=variant, linewidth=0.85, color=color_map.get(variant))
        dd = s551._drawdown_pct(pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"])))
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.75, color=color_map.get(variant))
    ax_equity.set_title("账户权益：Stage526 / Stage256 top6 / 低单笔风险扩池")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=6)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(ordered["date"], ordered["net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("卫星仓累计PnL")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=6)

    hold = rolling[rolling["holding_days"].isin([63, 126])].copy()
    hold_pivot = hold.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    order = [CONTROL, STAGE256_TOP6] + [spec.variant for spec in SPECS]
    hold_pivot = hold_pivot.reindex(order)
    hold_pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("任意启动持有3/6个月 p05收益")
    ax_hold.set_xlabel("%")
    ax_hold.grid(axis="x", alpha=0.25)

    family_view = family_harvest.copy()
    if not family_view.empty:
        family_view = (
            family_view.groupby(["variant", "product_family"], as_index=False)["satellite_family_net_pnl"]
            .sum()
            .sort_values(["variant", "satellite_family_net_pnl"], ascending=[True, False])
        )
        top_families = family_view.groupby("product_family")["satellite_family_net_pnl"].sum().abs().sort_values(ascending=False).head(8).index
        family_view = family_view[family_view["product_family"].isin(top_families)]
        fam_pivot = family_view.pivot(index="product_family", columns="variant", values="satellite_family_net_pnl").fillna(0.0)
        fam_pivot = fam_pivot.reindex(columns=[spec.variant for spec in SPECS])
        fam_pivot.plot(kind="barh", ax=ax_family, color=[color_map.get(v) for v in fam_pivot.columns])
    ax_family.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_family.set_title("扩池卫星：产品族累计PnL")
    ax_family.grid(axis="x", alpha=0.25)

    cost_view = cost.pivot(index="variant", columns="cost_multiplier", values="max_dd_pct")
    cost_view = cost_view.reindex(order)
    cost_view.plot(kind="barh", ax=ax_cost, color=["#0f172a", "#ea580c", "#b91c1c"])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("1x/2x/3x成本压力最大回撤")
    ax_cost.set_xlabel("%")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage257 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    window: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    selection: pd.DataFrame,
    product_harvest: pd.DataFrame,
    family_harvest: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    decision_rank = pd.DataFrame(decision.get("ranked", []))
    view = summary.copy()
    if not decision_rank.empty:
        rank_merge_cols = [
            "holding63_p05_improvement_vs_stage526_pp",
            "holding126_p05_improvement_vs_stage526_pp",
            "holding63_p05_improvement_vs_top6_pp",
            "holding126_p05_improvement_vs_top6_pp",
            "satellite_total_pnl",
            "top_product_abs_share_pct",
            "no_degrade_vs_stage526",
            "better_than_stage256_top6_experience",
            "materiality_pass",
            "broad_direction_pass",
            "soft_score",
        ]
        view = view.drop(columns=[column for column in rank_merge_cols if column in view.columns], errors="ignore")
        view = view.merge(
            decision_rank[
                ["variant", *rank_merge_cols]
            ],
            on="variant",
            how="left",
        )
    lines = [
        "# Stage257 低单笔风险扩池/相关簇约束审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- A：`{CONTROL}`。",
        f"- C0参考：Stage256修复后年度top6 `{STAGE256_TOP6}`。",
        "- 新增实验：只做三个粗档，不扫小数；核心Stage526不动，扩池作为115000卫星仓。",
        "- 规则：非核心商品宽池；单笔资金占用更低；同产品族保证金cap；20日同向相关性闸门；年度宽池版本只用上一年已知单品种账本为正。",
        "- 反过拟合判断：本阶段没有按结果挑品种，也没有调入场/出场；`future_year_single_product_pnl_sum`只做事后解释，不参与交易。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 账户总览",
        "",
        s551._md_table(
            view[
                [
                    "variant",
                    "total_return_pct",
                    "return_vs_stage526_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "satellite_cumulative_pnl",
                    "holding63_p05_improvement_vs_stage526_pp",
                    "holding126_p05_improvement_vs_stage526_pp",
                    "holding63_p05_improvement_vs_top6_pp",
                    "holding126_p05_improvement_vs_top6_pp",
                    "no_degrade_vs_stage526",
                    "better_than_stage256_top6_experience",
                    "materiality_pass",
                    "broad_direction_pass",
                    "total_trade_count",
                ]
            ].sort_values("return_vs_stage526_pct", ascending=False)
        ),
        "",
        "## 成本压力",
        "",
        s551._md_table(cost[["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "ulcer_pct", "sharpe"]]),
        "",
        "## B卫星仓 standalone",
        "",
        s551._md_table(satellite_summary),
        "",
        "## 任意启动3/6个月体验",
        "",
        s551._md_table(
            rolling[rolling["holding_days"].isin([63, 126])][
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "p10_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ]
        ),
        "",
        "## 年度宽池选择审计",
        "",
        s551._md_table(selection, max_rows=120),
        "",
        "## 多窗口",
        "",
        s551._md_table(
            window[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 卫星产品贡献",
        "",
        s551._md_table(product_harvest, max_rows=120),
        "",
        "## 卫星产品族贡献",
        "",
        s551._md_table(family_harvest, max_rows=120),
        "",
        "## 入场与风险闸门诊断",
        "",
        s551._md_table(entry_summary),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    universe, family, selection = _build_universe_and_eligibility()
    family_cluster_map = _family_cluster_map(universe, family)
    supported_symbols = load_product_universe_symbols(str(UNIVERSE_PATH))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    satellite_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in SPECS:
        print(f"[stage557] running {spec.variant}", flush=True)
        daily, positions, snapshots = _run_breadth_sleeve(spec, metadata, family_cluster_map)
        satellite_frames.append(daily)
        if not positions.empty:
            position_frames.append(positions)
        if not snapshots.empty:
            snapshot_frames.append(snapshots)

    satellite_daily = pd.concat(satellite_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    snapshots = pd.concat(snapshot_frames, ignore_index=True, sort=False) if snapshot_frames else pd.DataFrame()
    if not snapshots.empty:
        snapshots.to_csv(ENTRY_SNAPSHOTS_PATH, index=False, encoding="utf-8-sig")
    entry_summary = _entry_summary(snapshots)

    full_metadata = s551._metadata_for_full_universe()
    satellite_margin_daily, satellite_product_margin = s513._position_margin(positions, full_metadata)
    product_harvest = s551._satellite_product_harvest(satellite_product_margin)
    family_harvest = _family_harvest(product_harvest, family)
    satellite_summary = s551._satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    control_daily = s551._load_control_daily()
    combo_daily = _combine_with_core(control_daily, satellite_daily, satellite_margin_daily)

    new_summary, new_cost = s551._summary_and_cost(combo_daily)
    new_rolling = s516._rolling_holding(combo_daily)
    new_window = s551._window_metrics(combo_daily)

    old_daily, old_summary, old_cost, old_rolling, old_window, old_satellite = _load_stage256_reference()
    new_variants = [spec.variant for spec in SPECS]
    summary = pd.concat(
        [
            old_summary[old_summary["variant"].isin([CONTROL, STAGE256_TOP6])],
            new_summary[new_summary["variant"].isin(new_variants)],
        ],
        ignore_index=True,
        sort=False,
    )
    cost = pd.concat(
        [
            old_cost[old_cost["variant"].isin([CONTROL, STAGE256_TOP6])],
            new_cost[new_cost["variant"].isin(new_variants)],
        ],
        ignore_index=True,
        sort=False,
    )
    rolling = pd.concat(
        [
            old_rolling[old_rolling["variant"].isin([CONTROL, STAGE256_TOP6])],
            new_rolling[new_rolling["variant"].isin(new_variants)],
        ],
        ignore_index=True,
        sort=False,
    )
    window = pd.concat(
        [
            old_window[old_window["variant"].isin([CONTROL, STAGE256_TOP6])],
            new_window[new_window["variant"].isin(new_variants)],
        ],
        ignore_index=True,
        sort=False,
    )
    comparison_daily = pd.concat(
        [
            old_daily[old_daily["variant"].isin([CONTROL, STAGE256_TOP6])],
            combo_daily[combo_daily["variant"].isin(new_variants)],
        ],
        ignore_index=True,
        sort=False,
    )
    comparison_satellite = pd.concat([old_satellite, satellite_daily], ignore_index=True, sort=False)

    comparison_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    satellite_margin_daily.to_csv(SATELLITE_MARGIN_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    family_harvest.to_csv(SATELLITE_FAMILY_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")

    decision = _decision(summary, cost, rolling, satellite_summary, product_harvest, selection, entry_summary)
    _plot(comparison_daily, comparison_satellite, summary, cost, rolling, family_harvest, decision)
    _write_report(summary, cost, rolling, window, satellite_summary, selection, product_harvest, family_harvest, entry_summary, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
