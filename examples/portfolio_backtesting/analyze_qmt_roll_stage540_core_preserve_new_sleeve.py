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
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO  # noqa: E402


MODEL_TAG = "stage540_core_preserve_new_sleeve_v1"
OUTPUT_PREFIX = "qmt_roll_stage540_core_preserve_new_sleeve"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
SLEEVE_CAPITAL = 115_000.0
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
STAGE526_RETURN_PCT = 3_699.9195121951216
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
CONTROL = "stage526_r080_pc25_maxpos4"

STRUCTURAL_UNIVERSE_IN = OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
NEW_UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_new_product_universe_{MODEL_TAG}.csv"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE526_POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class SleeveSpec:
    variant: str
    label: str
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    note: str


SLEEVE_SPECS: tuple[SleeveSpec, ...] = (
    SleeveSpec(
        "core_plus_new5_r030_pc15_maxpos2",
        "Stage526 + new5 sleeve risk030 pc15 maxpos2",
        0.30,
        0.15,
        2,
        0.30,
        "核心Stage526完全保留；新增结构品种只用11.5万现金缓冲做低风险卫星仓。",
    ),
    SleeveSpec(
        "core_plus_new5_r050_pc15_maxpos2",
        "Stage526 + new5 sleeve risk050 pc15 maxpos2",
        0.50,
        0.15,
        2,
        0.35,
        "同一卫星池提高粗档风险，检验是否有可用趋势收益。",
    ),
    SleeveSpec(
        "core_plus_new5_r050_pc10_maxpos3",
        "Stage526 + new5 sleeve risk050 pc10 maxpos3",
        0.50,
        0.10,
        3,
        0.30,
        "更低单品种cap、更高广度，检验相关性预算和分散表达。",
    ),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(_drawdown_pct(equity).min())


def _ulcer_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(252.0))


def _product_from_contract(vt_symbol: object) -> str:
    return s513._product_from_contract(vt_symbol)


def _load_control_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE526_DAILY_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["variant"] = CONTROL
    frame["combo_variant"] = CONTROL
    frame["label"] = "Stage526 control r080 pc25 maxpos4"
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["note"] = "Stage238 normal-cost promotion candidate; kept unchanged as core."
    return frame.dropna(subset=["date"]).sort_values("date")


def _load_control_positions() -> pd.DataFrame:
    frame = pd.read_csv(STAGE526_POSITIONS_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["variant"] = CONTROL
    frame["combo_variant"] = CONTROL
    frame["label"] = "Stage526 control r080 pc25 maxpos4"
    return frame


def _build_new_product_universe() -> tuple[pd.DataFrame, list[str], list[str]]:
    if not STRUCTURAL_UNIVERSE_IN.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_IN)
    structural = pd.read_csv(STRUCTURAL_UNIVERSE_IN, encoding="utf-8-sig")
    structural["product_vt_symbol"] = structural["product_vt_symbol"].astype(str)
    if "structural_prefilter_kept" in structural.columns:
        structural = structural[pd.to_numeric(structural["structural_prefilter_kept"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    if "eligible" in structural.columns:
        structural = structural[pd.to_numeric(structural["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()

    control_positions = _load_control_positions()
    control_positions["product_vt_symbol"] = control_positions["vt_symbol"].map(_product_from_contract)
    core_products = sorted(set(control_positions.loc[control_positions["end_pos"].abs() > 0, "product_vt_symbol"].astype(str)))
    new_products = sorted(set(structural["product_vt_symbol"].astype(str)) - set(core_products))
    new_universe = structural[structural["product_vt_symbol"].isin(new_products)].copy()
    new_universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    new_universe.to_csv(NEW_UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    return new_universe, core_products, new_products


def _metadata_for_new_universe() -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(NEW_UNIVERSE_PATH))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _sleeve_overrides(spec: SleeveSpec, identity_map: str) -> dict[str, Any]:
    return {
        **s519._product_cap_overrides(spec.product_cap_ratio, identity_map),
        "product_universe_csv_path": str(NEW_UNIVERSE_PATH),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": 0.60,
        "same_direction_correlation_gate_full": 0.80,
        "same_direction_correlation_gate_weight_floor": 0.50,
        "enable_ai_product_pool_filter": False,
    }


def _run_sleeve(spec: SleeveSpec, metadata: dict[str, Any], identity_map: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    base_overrides = s513._c3_overrides(START_DT)
    overrides = {**base_overrides, **_sleeve_overrides(spec, identity_map)}
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
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
        strategy_overrides=overrides,
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
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["sleeve_equity"] = SLEEVE_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["product_cap_ratio"] = spec.product_cap_ratio
    daily["max_concurrent_positions"] = spec.max_concurrent_positions
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty sleeve positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier
    positions["product_cap_ratio"] = spec.product_cap_ratio
    positions["max_concurrent_positions"] = spec.max_concurrent_positions

    snapshots = pd.DataFrame(getattr(engine.strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
    return daily, positions, snapshots


def _combine_with_core(control_daily: pd.DataFrame, satellite_daily: pd.DataFrame, satellite_margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = [control_daily.copy()]
    spec_map = {spec.variant: spec for spec in SLEEVE_SPECS}
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
        margin_part = satellite_margin_daily[satellite_margin_daily["variant"].eq(variant)][
            ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
        ].rename(
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
        merged["trade_count"] = pd.to_numeric(merged["trade_count"], errors="coerce").fillna(0.0) + merged["satellite_trade_count"]
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["core_total_margin_exact"] + merged["satellite_margin_exact"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        merged["variant"] = variant
        merged["combo_variant"] = variant
        merged["label"] = spec.label
        merged["risk_multiplier"] = spec.risk_multiplier
        merged["product_cap_ratio"] = spec.product_cap_ratio
        merged["max_concurrent_positions"] = spec.max_concurrent_positions
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summary_and_cost(combo_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].dropna().iloc[0]) if "label" in frame and not frame["label"].dropna().empty else variant
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(frame, cost_multiplier)
            row = s516._metrics_from_equity(equity, frame, variant=variant, label=label, cost_multiplier=cost_multiplier)
            row["return_vs_stage526_pct"] = (
                _safe_float(row["total_return_pct"]) / STAGE526_RETURN_PCT * 100.0 if STAGE526_RETURN_PCT > 0.0 else 0.0
            )
            row["note"] = str(frame["note"].dropna().iloc[0]) if "note" in frame and not frame["note"].dropna().empty else ""
            if variant != CONTROL:
                row["satellite_cumulative_pnl"] = float(pd.to_numeric(frame.get("satellite_net_pnl", 0.0), errors="coerce").fillna(0.0).sum())
                row["max_satellite_margin_exact"] = float(pd.to_numeric(frame.get("satellite_margin_exact", 0.0), errors="coerce").fillna(0.0).max())
            else:
                row["satellite_cumulative_pnl"] = 0.0
                row["max_satellite_margin_exact"] = 0.0
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _satellite_standalone_summary(satellite_daily: pd.DataFrame, satellite_margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date").copy()
        equity = pd.Series(ordered["sleeve_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        margin = satellite_margin_daily[satellite_margin_daily["variant"].eq(variant)].copy()
        margin["c3_margin_exact"] = pd.to_numeric(margin.get("c3_margin_exact", 0.0), errors="coerce").fillna(0.0)
        max_margin = float(margin["c3_margin_exact"].max()) if not margin.empty else 0.0
        rows.append(
            {
                "variant": variant,
                "sleeve_end_equity": float(equity.iloc[-1]) if not equity.empty else SLEEVE_CAPITAL,
                "sleeve_total_pnl": float(equity.iloc[-1] - SLEEVE_CAPITAL) if not equity.empty else 0.0,
                "sleeve_return_pct": (float(equity.iloc[-1] - SLEEVE_CAPITAL) / SLEEVE_CAPITAL * 100.0) if not equity.empty else 0.0,
                "sleeve_max_dd_pct": _max_drawdown_pct(equity),
                "sleeve_ulcer_pct": _ulcer_pct(equity),
                "sleeve_sharpe": _sharpe(equity),
                "sleeve_trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
                "sleeve_slippage": float(pd.to_numeric(ordered["slippage"], errors="coerce").fillna(0.0).sum()),
                "max_sleeve_margin_exact": max_margin,
                "max_broker10_sleeve_margin_to_sleeve_equity_pct": max_margin * BROKER_MARGIN_MULTIPLIER / max(float(equity.min()), 1.0) * 100.0
                if not equity.empty
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


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
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for variant, group in frame.groupby("variant", sort=False):
        status = group.get("candidate_status", pd.Series("", index=group.index)).astype(str)
        reason = group.get("skip_reason", pd.Series("", index=group.index)).astype(str)
        rows.append(
            {
                "variant": variant,
                "candidate_count": int(len(group)),
                "open_candidate_count": int((status == "open").sum()),
                "sizing_zero_count": int((reason == "sizing_zero_volume").sum()),
                "concurrent_limit_count": int((reason == "concurrent_limit").sum()),
                "avg_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].mean()),
                "p10_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].quantile(0.10)),
                "max_same_direction_corr": float(group["same_direction_correlation_max_corr"].max()),
                "selected_volume_sum": float(group["selected_volume"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _satellite_product_harvest(product_margin: pd.DataFrame) -> pd.DataFrame:
    frame = product_margin.copy()
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["year"] = frame["date"].dt.year
    frame["net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    return (
        frame.groupby(["variant", "year", "product_vt_symbol"], as_index=False)
        .agg(
            satellite_product_net_pnl=("net_pnl", "sum"),
            active_days=("active_product", "sum"),
            max_margin=("c3_margin_exact", "max"),
        )
        .sort_values(["variant", "year", "satellite_product_net_pnl"], ascending=[True, True, False])
    )


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, satellite_summary: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")
    r63 = rolling[rolling["holding_days"].eq(63)].set_index("variant")
    r126 = rolling[rolling["holding_days"].eq(126)].set_index("variant")
    control = summary[summary["variant"].eq(CONTROL)].iloc[0].to_dict()
    control_r63 = r63.loc[CONTROL].to_dict() if CONTROL in r63.index else {}
    control_r126 = r126.loc[CONTROL].to_dict() if CONTROL in r126.index else {}
    rows: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        variant = str(item["variant"])
        two_dd = _safe_float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0
        three_dd = _safe_float(cost3.loc[variant, "max_dd_pct"]) if variant in cost3.index else 0.0
        h63_p05 = _safe_float(r63.loc[variant, "p05_return_pct"]) if variant in r63.index else 0.0
        h126_p05 = _safe_float(r126.loc[variant, "p05_return_pct"]) if variant in r126.index else 0.0
        h63_med = _safe_float(r63.loc[variant, "median_return_pct"]) if variant in r63.index else 0.0
        h126_med = _safe_float(r126.loc[variant, "median_return_pct"]) if variant in r126.index else 0.0
        satellite_row = satellite_summary[satellite_summary["variant"].eq(variant)]
        satellite_pnl = float(satellite_row["sleeve_total_pnl"].iloc[0]) if not satellite_row.empty else 0.0
        holding63_improvement = h63_p05 - _safe_float(control_r63.get("p05_return_pct", 0.0))
        holding126_improvement = h126_p05 - _safe_float(control_r126.get("p05_return_pct", 0.0))
        no_degrade_pass = bool(
            variant != CONTROL
            and _safe_float(item["total_return_pct"]) >= _safe_float(control["total_return_pct"])
            and _safe_float(item["max_dd_pct"]) >= _safe_float(control["max_dd_pct"])
            and _safe_float(item["ulcer_pct"]) <= _safe_float(control["ulcer_pct"])
            and _safe_float(item["max_broker10_margin_to_equity_pct"]) <= 100.0
            and int(item["days_over_100pct"]) == 0
            and two_dd >= _safe_float(cost2.loc[CONTROL, "max_dd_pct"])
            and h63_p05 >= _safe_float(control_r63.get("p05_return_pct", -999.0))
            and h126_p05 >= _safe_float(control_r126.get("p05_return_pct", -999.0))
            and satellite_pnl > 0.0
        )
        materiality_pass = bool(
            variant != CONTROL
            and satellite_pnl >= max(ACCOUNT_CAPITAL * 0.01, SLEEVE_CAPITAL * 0.10)
            and holding63_improvement >= 0.25
            and holding126_improvement >= 0.25
        )
        promotion_pass = bool(no_degrade_pass and materiality_pass)
        soft_score = (
            (_safe_float(item["total_return_pct"]) - _safe_float(control["total_return_pct"]))
            + (_safe_float(item["max_dd_pct"]) - _safe_float(control["max_dd_pct"])) * 20.0
            + (_safe_float(control["ulcer_pct"]) - _safe_float(item["ulcer_pct"])) * 15.0
            + holding63_improvement * 5.0
            + holding126_improvement * 5.0
            + satellite_pnl / ACCOUNT_CAPITAL * 100.0
        )
        rows.append(
            {
                **item,
                "two_x_max_dd_pct": two_dd,
                "three_x_max_dd_pct": three_dd,
                "holding63_p05_return_pct": h63_p05,
                "holding126_p05_return_pct": h126_p05,
                "holding63_median_return_pct": h63_med,
                "holding126_median_return_pct": h126_med,
                "holding63_p05_improvement_pp": holding63_improvement,
                "holding126_p05_improvement_pp": holding126_improvement,
                "satellite_total_pnl": satellite_pnl,
                "no_degrade_pass": int(no_degrade_pass),
                "materiality_pass": int(materiality_pass),
                "promotion_pass": int(promotion_pass),
                "soft_score": soft_score,
            }
        )
    ranked = sorted(rows, key=lambda item: (item["promotion_pass"], item["no_degrade_pass"], item["soft_score"]), reverse=True)
    no_degrade_candidates = [item for item in ranked if item["no_degrade_pass"]]
    promotion_candidates = [item for item in ranked if item["promotion_pass"]]
    return {
        "stage": "Stage540",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "core_preserve_new_sleeve_promotion_candidate_found" if promotion_candidates else "core_preserve_new_sleeve_micro_pass_not_promotion",
        "baseline": CONTROL,
        "pass_definition": "硬不劣化：C相对Stage526总收益不低、最大回撤不差、Ulcer不升、broker10<=100且无穿越、2x成本回撤不差、63/126日p05不差，且卫星仓自身PnL为正。晋级还要求材料性：卫星PnL至少1%账户资金或10% sleeve资金，且63/126日p05各改善>=0.25pp。",
        "best_variant": ranked[0] if ranked else {},
        "no_degrade_candidates": no_degrade_candidates,
        "promotion_candidates": promotion_candidates,
        "ranked": ranked,
        "next_step": "若只有微弱硬不劣化，不晋级、不扫new5 sleeve风险小数；保留非挤占式品种选择原则，下一步转向更长OOS、真实监控或更强事前结构筛选。",
    }


def _plot(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    combo_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_equity, ax_dd, ax_sat, ax_hold = axes.flatten()
    color_map = {
        CONTROL: "#111827",
        "core_plus_new5_r030_pc15_maxpos2": "#2563eb",
        "core_plus_new5_r050_pc15_maxpos2": "#dc2626",
        "core_plus_new5_r050_pc10_maxpos3": "#059669",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(ordered["date"], ordered["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        dd = _drawdown_pct(pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"])))
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
    ax_equity.set_title("账户权益：Stage526核心不动 + new5卫星")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(ordered["date"], ordered["net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("卫星仓累计PnL")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=7)

    h = rolling[rolling["holding_days"].isin([63, 126])].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    pivot = pivot.reindex([CONTROL] + [spec.variant for spec in SLEEVE_SPECS])
    pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("任意启动持有3/6个月 p05收益")
    ax_hold.set_xlabel("%")
    ax_hold.grid(axis="x", alpha=0.25)
    fig.suptitle(f"Stage540 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    product_harvest: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
    core_products: list[str],
    new_products: list[str],
) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct", "return_retention_vs_stage079_pct"]].rename(
        columns={"max_dd_pct": "max_dd_pct_2x", "return_retention_vs_stage079_pct": "retention_2x"}
    )
    cost3 = cost[cost["cost_multiplier"].eq(3.0)][["variant", "max_dd_pct"]].rename(columns={"max_dd_pct": "max_dd_pct_3x"})
    view = summary.merge(cost2, on="variant", how="left").merge(cost3, on="variant", how="left")
    view = view[
        [
            "variant",
            "total_return_pct",
            "return_vs_stage526_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "max_dd_pct_2x",
            "max_dd_pct_3x",
            "ulcer_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "satellite_cumulative_pnl",
            "total_trade_count",
        ]
    ].sort_values("return_vs_stage526_pct", ascending=False)
    hold_view = rolling[rolling["holding_days"].isin([63, 126])][
        [
            "variant",
            "holding_days",
            "p05_return_pct",
            "median_return_pct",
            "positive_rate_pct",
            "min_window_dd_pct",
            "p10_window_dd_pct",
        ]
    ]
    product_view = product_harvest.sort_values(["variant", "year", "satellite_product_net_pnl"], ascending=[True, True, False])
    lines = [
        "# Stage540 核心不替换的新产品卫星仓审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 阶段性质：A/C部署结构审计。A=`{CONTROL}`；B=新产品卫星仓 standalone；C=Stage526核心完全保留 + new5卫星仓。",
        "- 反过拟合边界：新增品种来自Stage539之前的结构预筛，核心产品由Stage526实际持仓反推后剔除；只跑3个粗档，禁止事后按历史赢家调小数。",
        f"- 核心产品数：`{len(core_products)}`；新增卫星产品：`{', '.join(new_products)}`。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## C账户总览",
        "",
        _md_table(view),
        "",
        "## B卫星仓 standalone",
        "",
        _md_table(satellite_summary),
        "",
        "## 任意启动3/6个月持有体验",
        "",
        _md_table(hold_view),
        "",
        "## 卫星产品年度贡献",
        "",
        _md_table(product_view, max_rows=60),
        "",
        "## 入场与相关性门控诊断",
        "",
        _md_table(entry_summary),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    new_universe, core_products, new_products = _build_new_product_universe()
    if new_universe.empty:
        raise RuntimeError("new product universe is empty")
    metadata = _metadata_for_new_universe()
    identity_map = s519._product_identity_cluster_map(metadata)

    satellite_daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in SLEEVE_SPECS:
        print(f"[stage540] running {spec.variant}", flush=True)
        daily, positions, snapshots = _run_sleeve(spec, metadata, identity_map)
        satellite_daily_frames.append(daily)
        position_frames.append(positions)
        if not snapshots.empty:
            snapshot_frames.append(snapshots)

    satellite_daily = pd.concat(satellite_daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    satellite_margin_daily, satellite_product_margin = s513._position_margin(positions, metadata)
    control_daily = _load_control_daily()
    combo_daily = _combine_with_core(control_daily, satellite_daily, satellite_margin_daily)

    summary, cost = _summary_and_cost(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    satellite_summary = _satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    product_harvest = _satellite_product_harvest(satellite_product_margin)
    snapshots = pd.concat(snapshot_frames, ignore_index=True, sort=False) if snapshot_frames else pd.DataFrame()
    entry_summary = _entry_summary(snapshots)
    decision = _decision(summary, cost, rolling, satellite_summary)
    summary["no_degrade_pass"] = summary["variant"].map({item["variant"]: item["no_degrade_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["materiality_pass"] = summary["variant"].map({item["variant"]: item["materiality_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["promotion_pass"] = summary["variant"].map({item["variant"]: item["promotion_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["soft_score"] = summary["variant"].map({item["variant"]: item["soft_score"] for item in decision["ranked"]}).fillna(0.0)

    _plot(summary, rolling, combo_daily, satellite_daily, decision)
    _write_report(summary, cost, rolling, satellite_summary, product_harvest, entry_summary, decision, core_products, new_products)

    combo_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
