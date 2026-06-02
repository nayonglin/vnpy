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


MODEL_TAG = "stage551_annual_persistence_sleeve_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage551_annual_persistence_sleeve_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
SLEEVE_CAPITAL = 115_000.0
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
STAGE526_RETURN_PCT = 3_699.9195121951216
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
CONTROL = "stage526_r080_pc25_maxpos4"
FINANCIAL_EXCHANGES = {"CFFEX"}
ORACLE6 = {"al.SHFE", "ao.SHFE", "c.DCE", "lu.INE", "v.DCE", "y.DCE"}
YEARS = list(range(max(2021, START_DT.year + 1), END_DT.year + 1))

FULL_UNIVERSE_IN = OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"

STAGE541_TAG = "stage541_single_product_opportunity_map_v1"
STAGE541_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
STAGE541_SUMMARY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_summary_{STAGE541_TAG}.csv"
STAGE541_ANNUAL_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_annual_{STAGE541_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"

UNIVERSE_DIR = OUTPUT_DIR / f"{OUTPUT_PREFIX}_universes_{MODEL_TAG}"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_margin_daily_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
SELECTION_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_selection_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class SleeveSpec:
    variant: str
    selector_mode: str
    label: str
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    note: str


SLEEVE_SPECS: tuple[SleeveSpec, ...] = (
    SleeveSpec(
        "annual_prevpos_r030_pc15_maxpos3",
        "prev_year_positive",
        "Stage526 + annual prev-year positive sleeve r030 pc15 maxpos3",
        0.30,
        0.15,
        3,
        0.30,
        "上一年单品种真实账本为正的非核心商品；低风险粗档。",
    ),
    SleeveSpec(
        "annual_prevpos_r050_pc15_maxpos3",
        "prev_year_positive",
        "Stage526 + annual prev-year positive sleeve r050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "上一年单品种真实账本为正的非核心商品；主风险粗档。",
    ),
    SleeveSpec(
        "annual_prevtop6_r030_pc15_maxpos3",
        "prev_year_top6",
        "Stage526 + annual prev-year top6 sleeve r030 pc15 maxpos3",
        0.30,
        0.15,
        3,
        0.30,
        "上一年单品种真实账本前6名；低风险集中对照。",
    ),
    SleeveSpec(
        "annual_prevtop6_r050_pc15_maxpos3",
        "prev_year_top6",
        "Stage526 + annual prev-year top6 sleeve r050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "上一年单品种真实账本前6名；主风险集中对照。",
    ),
)


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("ytd_2026", "2026起点至今", datetime(2026, 1, 1), END_DT),
    ("phase_2021_2022", "2021-2022弱窗口", datetime(2021, 1, 1), datetime(2022, 12, 31)),
    ("phase_2022_2023", "2022-2023独立段", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立段", datetime(2024, 1, 1), datetime(2025, 12, 31)),
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


def _longest_underwater_days(equity: pd.Series) -> int:
    longest = 0
    current = 0
    for value in _drawdown_pct(equity).to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


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
    frame["note"] = "Stage238/240 normal-cost execution candidate; kept unchanged as core."
    return frame.dropna(subset=["date"]).sort_values("date")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [FULL_UNIVERSE_IN, STAGE541_SUMMARY_IN, STAGE541_ANNUAL_IN, STAGE544_FAMILY_MAP_IN]:
        if not path.exists():
            raise FileNotFoundError(path)
    universe = pd.read_csv(FULL_UNIVERSE_IN, encoding="utf-8-sig")
    summary = pd.read_csv(STAGE541_SUMMARY_IN, encoding="utf-8-sig")
    annual = pd.read_csv(STAGE541_ANNUAL_IN, encoding="utf-8-sig")
    family = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")

    for frame in [universe, summary, annual, family]:
        if "product_vt_symbol" in frame.columns:
            frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    universe["eligible"] = pd.to_numeric(universe.get("eligible", 0), errors="coerce").fillna(0).astype(int)
    summary["is_core_product"] = pd.to_numeric(summary["is_core_product"], errors="coerce").fillna(0).astype(int)
    annual["is_core_product"] = pd.to_numeric(annual["is_core_product"], errors="coerce").fillna(0).astype(int)
    annual["year"] = pd.to_numeric(annual["year"], errors="coerce").fillna(0).astype(int)
    for column in ["net_pnl", "trade_count", "slippage", "active_days"]:
        annual[column] = pd.to_numeric(annual.get(column, 0.0), errors="coerce").fillna(0.0)
    return universe, summary, annual, family


def _noncore_commodity_products(universe: pd.DataFrame, summary: pd.DataFrame) -> set[str]:
    eligible = set(universe[universe["eligible"].eq(1)]["product_vt_symbol"].astype(str))
    frame = summary[summary["is_core_product"].eq(0)].copy()
    frame = frame[~frame["exchange"].astype(str).str.upper().isin(FINANCIAL_EXCHANGES)].copy()
    return set(frame["product_vt_symbol"].astype(str)) & eligible


def _annual_selection_rows(
    specs: tuple[SleeveSpec, ...],
    universe: pd.DataFrame,
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    family: pd.DataFrame,
) -> pd.DataFrame:
    noncore = _noncore_commodity_products(universe, summary)
    family_map = family[["product_vt_symbol", "product_family"]].drop_duplicates("product_vt_symbol")
    base_products = summary[summary["product_vt_symbol"].isin(noncore)][["product_vt_symbol", "exchange", "product"]].copy()
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        prev_year = year - 1
        previous = annual[
            annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(prev_year)
        ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "prev_year_pnl"})
        current = annual[
            annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(year)
        ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "future_year_single_product_pnl"})
        table = (
            base_products.merge(previous, on="product_vt_symbol", how="left")
            .merge(current, on="product_vt_symbol", how="left")
            .merge(family_map, on="product_vt_symbol", how="left")
        )
        table["prev_year_pnl"] = pd.to_numeric(table["prev_year_pnl"], errors="coerce").fillna(0.0)
        table["future_year_single_product_pnl"] = pd.to_numeric(
            table["future_year_single_product_pnl"], errors="coerce"
        ).fillna(0.0)
        table["product_family"] = table["product_family"].fillna(table["exchange"].astype(str))
        for spec in specs:
            if spec.selector_mode == "prev_year_positive":
                selected = table[table["prev_year_pnl"] > 0.0].copy()
                selected = selected.sort_values(["prev_year_pnl", "product_vt_symbol"], ascending=[False, True])
            elif spec.selector_mode == "prev_year_top6":
                selected = table.sort_values(["prev_year_pnl", "product_vt_symbol"], ascending=[False, True]).head(6).copy()
            else:
                raise ValueError(f"unknown selector mode: {spec.selector_mode}")
            rows.append(
                {
                    "variant": spec.variant,
                    "selector_mode": spec.selector_mode,
                    "year": year,
                    "prev_year": prev_year,
                    "selected_count": int(len(selected)),
                    "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                    "family_count": int(selected["product_family"].nunique()) if not selected.empty else 0,
                    "selected_families": ",".join(sorted(selected["product_family"].dropna().astype(str).unique())),
                    "prev_year_pnl_sum": float(selected["prev_year_pnl"].sum()) if not selected.empty else 0.0,
                    "future_year_single_product_pnl_sum": float(selected["future_year_single_product_pnl"].sum())
                    if not selected.empty
                    else 0.0,
                    "positive_selected_count": int((selected["future_year_single_product_pnl"] > 0.0).sum())
                    if not selected.empty
                    else 0,
                    "oracle6_overlap": int(selected["product_vt_symbol"].isin(ORACLE6).sum()) if not selected.empty else 0,
                }
            )
    return pd.DataFrame(rows)


def _write_universe_csv(
    universe: pd.DataFrame,
    variant: str,
    year: int,
    products: list[str],
) -> Path:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    selected = universe[universe["product_vt_symbol"].isin(products)].copy()
    if selected.empty:
        raise RuntimeError(f"empty annual universe: {variant} {year}")
    selected = selected.sort_values(["exchange", "product_vt_symbol"])
    path = UNIVERSE_DIR / f"{variant}_{year}_universe.csv"
    selected.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _sleeve_overrides(spec: SleeveSpec, universe_path: Path, identity_map: str, year_start: datetime) -> dict[str, Any]:
    return {
        **s513._c3_overrides(year_start),
        **s519._product_cap_overrides(spec.product_cap_ratio, identity_map),
        "product_universe_csv_path": str(universe_path),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": 0.60,
        "same_direction_correlation_gate_full": 0.80,
        "same_direction_correlation_gate_weight_floor": 0.50,
        "enable_ai_product_pool_filter": False,
    }


def _run_sleeve_year(
    spec: SleeveSpec,
    year: int,
    products: list[str],
    universe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    year_start = datetime(year, 1, 1)
    year_end = min(datetime(year, 12, 31), END_DT)
    universe_path = _write_universe_csv(universe, spec.variant, year, products)
    supported_symbols = load_product_universe_symbols(str(universe_path))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    identity_map = s519._product_identity_cluster_map(metadata)

    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    preload_start = max(PRELOAD_START_DT, year_start - timedelta(days=365))
    _, open_map = s506.s501._seed_proxy_maps()
    engine = s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=year_end,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=SLEEVE_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=_sleeve_overrides(spec, universe_path, identity_map, year_start),
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
        raise RuntimeError(f"empty sleeve daily: {spec.variant} {year}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= year_start.date()) & (daily.index <= year_end.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["selector_mode"] = spec.selector_mode
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["product_cap_ratio"] = spec.product_cap_ratio
    daily["max_concurrent_positions"] = spec.max_concurrent_positions
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["year"] = year
    daily["selected_products"] = ",".join(products)
    daily["selected_count"] = len(products)
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if positions.empty:
        positions = pd.DataFrame()
    else:
        positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
        positions = positions[positions["date"].between(pd.Timestamp(year_start), pd.Timestamp(year_end))].copy()
        positions["variant"] = spec.variant
        positions["combo_variant"] = spec.variant
        positions["label"] = spec.label
        positions["selector_mode"] = spec.selector_mode
        positions["risk_multiplier"] = spec.risk_multiplier
        positions["product_cap_ratio"] = spec.product_cap_ratio
        positions["max_concurrent_positions"] = spec.max_concurrent_positions
        positions["year"] = year
        positions["selected_products"] = ",".join(products)

    snapshots = pd.DataFrame(getattr(engine.strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
        snapshots["selector_mode"] = spec.selector_mode
        snapshots["risk_multiplier"] = spec.risk_multiplier
        snapshots["year"] = year
    return daily, positions, snapshots


def _stitch_satellite_daily(raw_daily: pd.DataFrame, control_dates: pd.Series) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base_dates = pd.DataFrame({"date": pd.to_datetime(control_dates).drop_duplicates().sort_values().to_list()})
    for spec in SLEEVE_SPECS:
        part = raw_daily[raw_daily["variant"].eq(spec.variant)].copy()
        if part.empty:
            grouped = pd.DataFrame(columns=["date", "net_pnl", "slippage", "commission", "turnover", "trade_count"])
        else:
            grouped = (
                part.groupby("date", as_index=False)
                .agg(
                    net_pnl=("net_pnl", "sum"),
                    slippage=("slippage", "sum"),
                    commission=("commission", "sum"),
                    turnover=("turnover", "sum"),
                    trade_count=("trade_count", "sum"),
                )
                .sort_values("date")
            )
        merged = base_dates.merge(grouped, on="date", how="left")
        for column in ["net_pnl", "slippage", "commission", "turnover", "trade_count"]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["sleeve_equity"] = SLEEVE_CAPITAL + merged["net_pnl"].cumsum()
        merged["variant"] = spec.variant
        merged["combo_variant"] = spec.variant
        merged["label"] = spec.label
        merged["selector_mode"] = spec.selector_mode
        merged["risk_multiplier"] = spec.risk_multiplier
        merged["product_cap_ratio"] = spec.product_cap_ratio
        merged["max_concurrent_positions"] = spec.max_concurrent_positions
        merged["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _metadata_for_full_universe() -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(FULL_UNIVERSE_IN))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _combine_with_core(
    control_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    satellite_margin_daily: pd.DataFrame,
) -> pd.DataFrame:
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
        merged["product_cap_ratio"] = spec.product_cap_ratio
        merged["max_concurrent_positions"] = spec.max_concurrent_positions
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _stressed_equity(frame: pd.DataFrame, cost_multiplier: float) -> pd.Series:
    ordered = frame.sort_values("date").copy()
    slippage = pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).cumsum()
    additional = slippage * max(0.0, float(cost_multiplier) - 1.0)
    equity = ordered["account_equity"].astype(float) - additional
    return pd.Series(equity.to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))


def _metrics_from_equity(
    equity: pd.Series,
    frame: pd.DataFrame,
    *,
    variant: str,
    label: str,
    cost_multiplier: float,
) -> dict[str, Any]:
    ordered = frame.sort_values("date").copy()
    margin_ratio = (
        ordered["broker10_total_margin_exact"].astype(float).to_numpy()
        / np.maximum(equity.to_numpy(dtype=float), 1e-9)
        * 100.0
    )
    total_profit = float(equity.iloc[-1] - ACCOUNT_CAPITAL) if not equity.empty else 0.0
    nonzero_pnl = pd.to_numeric(ordered["total_net_pnl"], errors="coerce").fillna(0.0)
    nonzero_pnl = nonzero_pnl[nonzero_pnl.abs() > 1e-12]
    total_trade_count = float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum())
    if "xsmom_true_held_contract_count" in ordered.columns:
        total_trade_count += float(
            pd.to_numeric(ordered["xsmom_true_held_contract_count"], errors="coerce")
            .fillna(0.0)
            .diff()
            .abs()
            .fillna(0.0)
            .sum()
        )
    return {
        "variant": variant,
        "label": label,
        "cost_multiplier": cost_multiplier,
        "end_equity": float(equity.iloc[-1]) if not equity.empty else ACCOUNT_CAPITAL,
        "total_return_pct": total_profit / ACCOUNT_CAPITAL * 100.0,
        "return_vs_stage526_pct": (total_profit / ACCOUNT_CAPITAL * 100.0) / STAGE526_RETURN_PCT * 100.0,
        "return_retention_vs_stage079_pct": (total_profit / ACCOUNT_CAPITAL * 100.0)
        / BASELINE_STAGE079_RETURN_PCT
        * 100.0,
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "sharpe": _sharpe(equity),
        "longest_underwater_days": _longest_underwater_days(equity),
        "max_broker10_margin_to_equity_pct": float(np.max(margin_ratio)) if len(margin_ratio) else 0.0,
        "p95_broker10_margin_to_equity_pct": float(np.quantile(margin_ratio, 0.95)) if len(margin_ratio) else 0.0,
        "days_over_100pct": int(np.sum(margin_ratio > 100.0 + 1e-9)),
        "days_over_90pct": int(np.sum(margin_ratio > 90.0 + 1e-9)),
        "total_slippage": float(pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).sum()),
        "total_trade_count": total_trade_count,
        "nonzero_daily_win_rate_pct": float((nonzero_pnl > 0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "dd40_pass": int(_max_drawdown_pct(equity) >= -40.0),
        "broker10_100_pass": int(np.all(margin_ratio <= 100.0 + 1e-9)) if len(margin_ratio) else 1,
    }


def _summary_and_cost(combo_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].dropna().iloc[0]) if not frame["label"].dropna().empty else variant
        for cost_multiplier in COST_MULTIPLIERS:
            equity = _stressed_equity(frame, cost_multiplier)
            row = _metrics_from_equity(equity, frame, variant=variant, label=label, cost_multiplier=cost_multiplier)
            row["note"] = str(frame["note"].dropna().iloc[0]) if "note" in frame and not frame["note"].dropna().empty else ""
            row["satellite_cumulative_pnl"] = (
                float(pd.to_numeric(frame.get("satellite_net_pnl", 0.0), errors="coerce").fillna(0.0).sum())
                if variant != CONTROL
                else 0.0
            )
            row["max_satellite_margin_exact"] = (
                float(pd.to_numeric(frame.get("satellite_margin_exact", 0.0), errors="coerce").fillna(0.0).max())
                if variant != CONTROL
                else 0.0
            )
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _window_metrics(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].dropna().iloc[0]) if not frame["label"].dropna().empty else variant
        ordered = frame.sort_values("date")
        for window_name, display_label, start, end in WINDOWS:
            sliced = ordered[ordered["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
            if sliced.empty:
                continue
            equity = pd.Series(sliced["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(sliced["date"]))
            base = float(equity.iloc[0])
            total_return = float(equity.iloc[-1] / base - 1.0) * 100.0 if base > 0.0 else 0.0
            margin_ratio = pd.to_numeric(sliced["broker10_margin_to_equity_pct"], errors="coerce").fillna(0.0)
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "window_name": window_name,
                    "display_label": display_label,
                    "start": pd.Timestamp(start).date().isoformat(),
                    "end": pd.Timestamp(end).date().isoformat(),
                    "holding_days": int(len(sliced)),
                    "window_return_pct": total_return,
                    "window_max_dd_pct": _max_drawdown_pct(equity),
                    "window_ulcer_pct": _ulcer_pct(equity),
                    "window_sharpe": _sharpe(equity),
                    "window_max_broker10_margin_to_equity_pct": float(margin_ratio.max()),
                    "window_days_over_100pct": int((margin_ratio > 100.0).sum()),
                }
            )
    return pd.DataFrame(rows)


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
                "selector_mode": str(ordered["selector_mode"].dropna().iloc[0]),
                "sleeve_end_equity": float(equity.iloc[-1]) if not equity.empty else SLEEVE_CAPITAL,
                "sleeve_total_pnl": float(equity.iloc[-1] - SLEEVE_CAPITAL) if not equity.empty else 0.0,
                "sleeve_return_pct": float(equity.iloc[-1] - SLEEVE_CAPITAL) / SLEEVE_CAPITAL * 100.0
                if not equity.empty
                else 0.0,
                "sleeve_max_dd_pct": _max_drawdown_pct(equity),
                "sleeve_ulcer_pct": _ulcer_pct(equity),
                "sleeve_sharpe": _sharpe(equity),
                "sleeve_trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
                "sleeve_slippage": float(pd.to_numeric(ordered["slippage"], errors="coerce").fillna(0.0).sum()),
                "max_sleeve_margin_exact": max_margin,
                "max_broker10_sleeve_margin_to_sleeve_equity_pct": max_margin
                * BROKER_MARGIN_MULTIPLIER
                / max(float(equity.min()), 1.0)
                * 100.0
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
    if product_margin.empty:
        return pd.DataFrame()
    frame = product_margin.copy()
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
    promotion_candidates = [item for item in ranked if item["promotion_pass"]]
    no_degrade_candidates = [item for item in ranked if item["no_degrade_pass"]]
    return {
        "stage": "Stage251",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "annual_persistence_sleeve_promotion_candidate_found"
        if promotion_candidates
        else "annual_persistence_sleeve_not_promotion",
        "baseline": CONTROL,
        "execution_semantics": (
            "年度卫星仓每年用上一年已知单品种真实账本选品；年初从空仓启动；核心Stage526不替换。"
            "这是低自由度可执行近似，但尚未实现跨年持仓连续动态宇宙。"
        ),
        "pass_definition": (
            "硬不劣化：C相对Stage526总收益不低、最大回撤不差、Ulcer不升、broker10<=100且无穿越、"
            "2x成本回撤不差、63/126日p05不差，且卫星PnL为正。晋级还要求卫星PnL至少1%账户资金或10% sleeve资金，"
            "且63/126日p05各改善>=0.25pp。"
        ),
        "best_variant": ranked[0] if ranked else {},
        "promotion_candidates": promotion_candidates,
        "no_degrade_candidates": no_degrade_candidates,
        "ranked": ranked,
        "next_step": (
            "若未晋级，停止年度延续选品的risk/cap/topN小数救援；保留年度机会几何为经验，"
            "下一步转向更强外生点时化状态或低保证金独立收益源。"
        ),
    }


def _plot(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    combo_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    selection_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(3, 2, figsize=(17, 13))
    ax_equity, ax_dd, ax_sat, ax_hold, ax_annual, ax_cost = axes.flatten()
    color_map = {
        CONTROL: "#111827",
        "annual_prevpos_r030_pc15_maxpos3": "#2563eb",
        "annual_prevpos_r050_pc15_maxpos3": "#dc2626",
        "annual_prevtop6_r030_pc15_maxpos3": "#059669",
        "annual_prevtop6_r050_pc15_maxpos3": "#7c3aed",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(
            ordered["date"],
            ordered["account_equity"],
            label=variant,
            linewidth=0.9,
            color=color_map.get(variant),
        )
        dd = _drawdown_pct(pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"])))
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
    ax_equity.set_title("账户权益：Stage526核心不动 + 年度延续卫星")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(
            ordered["date"],
            ordered["net_pnl"].cumsum(),
            label=variant,
            linewidth=0.9,
            color=color_map.get(variant),
        )
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

    annual = selection_audit.copy()
    annual["future_year_single_product_pnl_sum"] = pd.to_numeric(
        annual["future_year_single_product_pnl_sum"], errors="coerce"
    ).fillna(0.0)
    annual_pivot = annual.pivot_table(
        index="year",
        columns="variant",
        values="future_year_single_product_pnl_sum",
        aggfunc="first",
        fill_value=0.0,
    )
    annual_pivot = annual_pivot.reindex(columns=[spec.variant for spec in SLEEVE_SPECS])
    annual_pivot.plot(kind="bar", ax=ax_annual, color=[color_map.get(v) for v in annual_pivot.columns])
    ax_annual.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_annual.set_title("年度选品的下一年单品种账本PnL提示")
    ax_annual.set_ylabel("PnL")
    ax_annual.legend(fontsize=7)
    ax_annual.grid(axis="y", alpha=0.25)

    cost_view = cost[cost["cost_multiplier"].isin(COST_MULTIPLIERS)].pivot(
        index="variant", columns="cost_multiplier", values="max_dd_pct"
    )
    cost_view = cost_view.reindex([CONTROL] + [spec.variant for spec in SLEEVE_SPECS])
    cost_view.plot(kind="barh", ax=ax_cost, color=["#0f172a", "#ea580c", "#b91c1c"])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("1x/2x/3x成本压力最大回撤")
    ax_cost.set_xlabel("%")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage251 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    window: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    selection_audit: pd.DataFrame,
    product_harvest: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct", "return_retention_vs_stage079_pct"]].rename(
        columns={"max_dd_pct": "max_dd_pct_2x", "return_retention_vs_stage079_pct": "retention_2x"}
    )
    cost3 = cost[cost["cost_multiplier"].eq(3.0)][["variant", "max_dd_pct"]].rename(
        columns={"max_dd_pct": "max_dd_pct_3x"}
    )
    view = summary.merge(cost2, on="variant", how="left").merge(cost3, on="variant", how="left")
    decision_rank = pd.DataFrame(decision.get("ranked", []))
    if not decision_rank.empty:
        rank_cols = [
            "variant",
            "holding63_p05_improvement_pp",
            "holding126_p05_improvement_pp",
            "satellite_total_pnl",
            "soft_score",
        ]
        view = view.merge(decision_rank[rank_cols], on="variant", how="left")
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
            "holding63_p05_improvement_pp",
            "holding126_p05_improvement_pp",
            "no_degrade_pass",
            "materiality_pass",
            "promotion_pass",
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
            "worst_return_start",
            "worst_return_end",
        ]
    ]
    window_view = window[
        [
            "variant",
            "window_name",
            "window_return_pct",
            "window_max_dd_pct",
            "window_ulcer_pct",
            "window_max_broker10_margin_to_equity_pct",
            "window_days_over_100pct",
        ]
    ]
    lines = [
        "# Stage251 年度延续选品卫星仓真实回放审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 阶段性质：A/C部署结构审计。A=`{CONTROL}`；B=年度选品卫星仓 standalone；C=Stage526核心完全保留 + 年度选品卫星仓。",
        "- 候选假设：减少单笔风险、扩大非核心商品池，并用上一年真实单品种账本做年度延续选择；同向相关性门控和单产品cap限制相关暴露。",
        "- 反过拟合边界：只用上一年已知账本，不用 Oracle6、不用当年收益、不扫 TopN 小数；只跑 `prev_year_positive/top6` 与 `risk030/050` 粗档。",
        f"- 执行语义：{decision['execution_semantics']}",
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
        "## 年度选品审计",
        "",
        _md_table(selection_audit, max_rows=80),
        "",
        "## 任意启动3/6个月持有体验",
        "",
        _md_table(hold_view),
        "",
        "## 多窗口",
        "",
        _md_table(window_view, max_rows=80),
        "",
        "## 卫星产品年度贡献",
        "",
        _md_table(product_harvest, max_rows=80),
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
    universe, summary_in, annual_in, family_in = _load_inputs()
    selection_audit = _annual_selection_rows(SLEEVE_SPECS, universe, summary_in, annual_in, family_in)
    control_daily = _load_control_daily()
    control_dates = control_daily["date"]

    satellite_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in SLEEVE_SPECS:
        rows = selection_audit[selection_audit["variant"].eq(spec.variant)].sort_values("year")
        for row in rows.itertuples(index=False):
            products = [item for item in str(row.selected_products).split(",") if item]
            if not products:
                continue
            print(f"[stage551] running {spec.variant} year={row.year} products={','.join(products)}", flush=True)
            daily, positions, snapshots = _run_sleeve_year(spec, int(row.year), products, universe)
            satellite_frames.append(daily)
            if not positions.empty:
                position_frames.append(positions)
            if not snapshots.empty:
                snapshot_frames.append(snapshots)

    raw_satellite_daily = pd.concat(satellite_frames, ignore_index=True, sort=False) if satellite_frames else pd.DataFrame()
    satellite_daily = _stitch_satellite_daily(raw_satellite_daily, control_dates)
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    metadata_all = _metadata_for_full_universe()
    if positions.empty:
        satellite_margin_daily = pd.DataFrame(columns=["variant", "combo_variant", "date", "c3_margin_exact"])
        satellite_product_margin = pd.DataFrame()
    else:
        satellite_margin_daily, satellite_product_margin = s513._position_margin(positions, metadata_all)
    combo_daily = _combine_with_core(control_daily, satellite_daily, satellite_margin_daily)

    summary, cost = _summary_and_cost(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    window = _window_metrics(combo_daily)
    satellite_summary = _satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    product_harvest = _satellite_product_harvest(satellite_product_margin)
    snapshots = pd.concat(snapshot_frames, ignore_index=True, sort=False) if snapshot_frames else pd.DataFrame()
    entry_summary = _entry_summary(snapshots)
    decision = _decision(summary, cost, rolling, satellite_summary)
    summary["no_degrade_pass"] = summary["variant"].map({item["variant"]: item["no_degrade_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["materiality_pass"] = summary["variant"].map({item["variant"]: item["materiality_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["promotion_pass"] = summary["variant"].map({item["variant"]: item["promotion_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["soft_score"] = summary["variant"].map({item["variant"]: item["soft_score"] for item in decision["ranked"]}).fillna(0.0)

    _plot(summary, cost, rolling, combo_daily, satellite_daily, selection_audit, decision)
    _write_report(
        summary,
        cost,
        rolling,
        window,
        satellite_summary,
        selection_audit,
        product_harvest,
        entry_summary,
        decision,
    )

    combo_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    satellite_margin_daily.to_csv(SATELLITE_MARGIN_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    selection_audit.to_csv(SELECTION_AUDIT_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
