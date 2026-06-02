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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO  # noqa: E402


MODEL_TAG = "stage539_low_risk_expanded_universe_scout_v1"
OUTPUT_PREFIX = "qmt_roll_stage539_low_risk_expanded_universe_scout"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
CONTROL = "stage526_r080_pc25_maxpos4"

STRUCTURAL_UNIVERSE_IN = OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
FULL_MARKET_PREDICTIONS_IN = (
    OUTPUT_DIR / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)
EXPANDED_UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expanded_universe_{MODEL_TAG}.csv"
EXPANDED_ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"
STAGE526_COST_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_cost_stress_{STAGE526_TAG}.csv"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE526_POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
ENTRY_SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_snapshots_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
ANNUAL_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_product_harvest_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    ai_strategy: str
    ai_top_n: int
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        "exp24_all_r080_pc25_maxpos4",
        "expanded24 all products risk080 pc25 maxpos4",
        0.80,
        0.25,
        4,
        0.70,
        "",
        0,
        "纯扩池隔离组：沿用Stage526接近的风险/单品种cap/持仓槽位，只观察结构扩池是否破坏或增强原alpha。",
    ),
    VariantSpec(
        "exp24_all_r050_pc20_maxpos6",
        "expanded24 all products risk050 pc20 maxpos6",
        0.50,
        0.20,
        6,
        0.25,
        "",
        0,
        "结构扩池但不做动态品种选择，用来验证“全加”是否带来相关性和噪音。",
    ),
    VariantSpec(
        "exp24_ai12_r060_pc20_maxpos6",
        "expanded24 AI top12 risk060 pc20 maxpos6",
        0.60,
        0.20,
        6,
        0.25,
        "stage539_ai12_entry_filter",
        12,
        "低单笔风险 + 结构扩池 + AI动态top12 + 原同向相关性门控。",
    ),
    VariantSpec(
        "exp24_ai12_r070_pc20_maxpos6",
        "expanded24 AI top12 risk070 pc20 maxpos6",
        0.70,
        0.20,
        6,
        0.25,
        "stage539_ai12_entry_filter",
        12,
        "同一选择器下提高风险预算，测试收益保留边界。",
    ),
    VariantSpec(
        "exp24_simple12_r060_pc20_maxpos6",
        "expanded24 simple top12 risk060 pc20 maxpos6",
        0.60,
        0.20,
        6,
        0.25,
        "stage539_simple12_entry_filter",
        12,
        "用非机器学习简单趋势适配分数复核AI选择器是否过拟合。",
    ),
    VariantSpec(
        "exp24_ai12_r060_pc15_maxpos8",
        "expanded24 AI top12 risk060 pc15 maxpos8",
        0.60,
        0.15,
        8,
        0.22,
        "stage539_ai12_entry_filter",
        12,
        "更低单品种cap、更多持仓槽位，检验更分散的表达是否改善持有体验。",
    ),
    VariantSpec(
        "static18_r060_pc20_maxpos6",
        "static18 risk060 pc20 maxpos6",
        0.60,
        0.20,
        6,
        0.25,
        "stage539_static18_entry_filter",
        0,
        "降单笔风险隔离组：只允许Stage78静态强池+fu，不引入扩池新产品，用来拆分降风险和扩池的影响。",
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _build_expanded_universe() -> pd.DataFrame:
    if not STRUCTURAL_UNIVERSE_IN.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_IN)
    universe = pd.read_csv(STRUCTURAL_UNIVERSE_IN, encoding="utf-8-sig")
    universe["product_vt_symbol"] = universe["product_vt_symbol"].astype(str)
    universe["eligible"] = 1
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe.to_csv(EXPANDED_UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    return universe


def _build_stage539_eligibility(universe: pd.DataFrame) -> pd.DataFrame:
    if not FULL_MARKET_PREDICTIONS_IN.exists():
        raise FileNotFoundError(FULL_MARKET_PREDICTIONS_IN)
    eligible_products = set(universe["product_vt_symbol"].astype(str))
    pre_products = sorted(
        set(universe.loc[pd.to_numeric(universe["is_static_strategy_product"], errors="coerce").fillna(0).astype(int).eq(1), "product_vt_symbol"].astype(str))
        | {"fu.SHFE"}
    )
    pre_products = [product for product in pre_products if product in eligible_products]
    rows: list[dict[str, Any]] = []
    for strategy in ("stage539_ai12_entry_filter", "stage539_simple12_entry_filter", "stage539_static18_entry_filter"):
        for rank, product in enumerate(pre_products, start=1):
            rows.append(
                {
                    "strategy": strategy,
                    "score_type": "static_plus_fu_pre_2022_boundary",
                    "eval_date": "2019-12-31",
                    "product_vt_symbol": product,
                    "score": 0.0,
                    "score_rank": rank,
                    "top_n": len(pre_products),
                }
            )

    predictions = pd.read_csv(FULL_MARKET_PREDICTIONS_IN, encoding="utf-8-sig")
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.normalize()
    predictions = predictions[predictions["product_vt_symbol"].astype(str).isin(eligible_products)].copy()
    eval_dates = sorted(predictions["eval_date"].dropna().unique())
    for eval_date in eval_dates:
        for rank, product in enumerate(pre_products, start=1):
            rows.append(
                {
                    "strategy": "stage539_static18_entry_filter",
                    "score_type": "static18_constant_boundary",
                    "eval_date": pd.Timestamp(eval_date).date().isoformat(),
                    "product_vt_symbol": product,
                    "score": 0.0,
                    "score_rank": rank,
                    "top_n": len(pre_products),
                }
            )
    specs = (
        ("stage539_ai12_entry_filter", "ai_probability", "predicted_product_suitability_probability"),
        ("stage539_simple12_entry_filter", "simple_score", "simple_trend_suitability_score"),
    )
    for strategy, score_type, score_column in specs:
        frame = predictions.dropna(subset=["eval_date"]).copy()
        frame[score_column] = pd.to_numeric(frame[score_column], errors="coerce").fillna(0.0)
        frame.sort_values(["eval_date", score_column, "product_vt_symbol"], ascending=[True, False, True], inplace=True)
        frame["score_rank"] = frame.groupby("eval_date")[score_column].rank(method="first", ascending=False)
        selected = frame[frame["score_rank"] <= 12].copy()
        for record in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": strategy,
                    "score_type": score_type,
                    "eval_date": pd.Timestamp(record.eval_date).date().isoformat(),
                    "product_vt_symbol": str(record.product_vt_symbol),
                    "score": float(getattr(record, score_column)),
                    "score_rank": int(record.score_rank),
                    "top_n": 12,
                }
            )
    eligibility = pd.DataFrame(rows)
    eligibility.sort_values(["strategy", "eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    eligibility.to_csv(EXPANDED_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    return eligibility


def _metadata_for_universe(universe_path: Path) -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(universe_path))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _variant_overrides(spec: VariantSpec, identity_map: str) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        **s519._product_cap_overrides(spec.product_cap_ratio, identity_map),
        "product_universe_csv_path": str(EXPANDED_UNIVERSE_PATH),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": 0.60,
        "same_direction_correlation_gate_full": 0.80,
        "same_direction_correlation_gate_weight_floor": 0.35,
    }
    if spec.ai_strategy:
        overrides.update(
            {
                "enable_ai_product_pool_filter": True,
                "ai_product_pool_eligibility_path": str(EXPANDED_ELIGIBILITY_PATH),
                "ai_product_pool_strategy": spec.ai_strategy,
            }
        )
    else:
        overrides.update({"enable_ai_product_pool_filter": False})
    return overrides


def _run_variant(spec: VariantSpec, metadata: dict[str, Any], identity_map: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    base_overrides = s513._c3_overrides(START_DT)
    overrides = {**base_overrides, **_variant_overrides(spec, identity_map)}
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
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = C3_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["product_cap_ratio"] = spec.product_cap_ratio
    daily["max_concurrent_positions"] = spec.max_concurrent_positions
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["ai_strategy"] = spec.ai_strategy
    daily["ai_top_n"] = spec.ai_top_n
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier
    positions["product_cap_ratio"] = spec.product_cap_ratio
    positions["max_concurrent_positions"] = spec.max_concurrent_positions
    positions["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    positions["ai_strategy"] = spec.ai_strategy
    positions["note"] = spec.note

    strategy = getattr(engine, "strategy", None)
    snapshots = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
        snapshots["risk_multiplier"] = spec.risk_multiplier
        snapshots["product_cap_ratio"] = spec.product_cap_ratio
        snapshots["max_concurrent_positions"] = spec.max_concurrent_positions
        snapshots["ai_strategy"] = spec.ai_strategy
    return daily, positions, snapshots


def _load_control_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE526_DAILY_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["variant"] = CONTROL
    frame["combo_variant"] = CONTROL
    frame["label"] = "Stage526 control r080 pc25 maxpos4"
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["note"] = "已验证正常成本候选评审基准。"
    return frame


def _load_control_positions() -> pd.DataFrame:
    frame = pd.read_csv(STAGE526_POSITIONS_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["variant"] = CONTROL
    frame["combo_variant"] = CONTROL
    frame["label"] = "Stage526 control r080 pc25 maxpos4"
    return frame


def _combine_summary_and_cost(combo_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].dropna().iloc[0]) if "label" in frame and not frame["label"].dropna().empty else variant
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(frame, cost_multiplier)
            row = s516._metrics_from_equity(equity, frame, variant=variant, label=label, cost_multiplier=cost_multiplier)
            row["return_vs_stage526_pct"] = (
                _safe_float(row["total_return_pct"]) / 3699.9195121951216 * 100.0
                if 3699.9195121951216 > 0
                else 0.0
            )
            row["note"] = str(frame["note"].dropna().iloc[0]) if "note" in frame and not frame["note"].dropna().empty else ""
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _annual_product_harvest(product_margin: pd.DataFrame, combo_daily: pd.DataFrame) -> pd.DataFrame:
    pm = product_margin.copy()
    pm["date"] = pd.to_datetime(pm["date"], errors="coerce").dt.normalize()
    pm["year"] = pm["date"].dt.year
    pm["net_pnl"] = pd.to_numeric(pm.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    product_year = (
        pm.groupby(["variant", "year", "product_vt_symbol"], as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), active_days=("active_product", "sum"))
        .sort_values(["variant", "year", "net_pnl"], ascending=[True, True, False])
    )
    combo = combo_daily.copy()
    combo["year"] = pd.to_datetime(combo["date"], errors="coerce").dt.year
    combo_year = combo.groupby(["variant", "year"], as_index=False).agg(combo_net_pnl=("total_net_pnl", "sum"))
    rows: list[dict[str, Any]] = []
    for (variant, year), frame in product_year.groupby(["variant", "year"], sort=False):
        positives = frame[frame["net_pnl"] > 0].copy()
        negatives = frame[frame["net_pnl"] < 0].copy()
        positive_sum = float(positives["net_pnl"].sum())
        top_product = str(positives.iloc[0]["product_vt_symbol"]) if not positives.empty else ""
        top_pnl = float(positives.iloc[0]["net_pnl"]) if not positives.empty else 0.0
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "combo_net_pnl": float(combo_year[(combo_year["variant"].eq(variant)) & (combo_year["year"].eq(year))]["combo_net_pnl"].iloc[0])
                if not combo_year[(combo_year["variant"].eq(variant)) & (combo_year["year"].eq(year))].empty
                else 0.0,
                "c3_product_net_pnl": float(frame["net_pnl"].sum()),
                "positive_product_count": int(len(positives)),
                "negative_product_count": int(len(negatives)),
                "positive_product_pnl": positive_sum,
                "negative_product_pnl": float(negatives["net_pnl"].sum()),
                "top_positive_product": top_product,
                "top_positive_product_pnl": top_pnl,
                "top_positive_share_of_positive_pnl_pct": top_pnl / positive_sum * 100.0 if positive_sum > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "year"])


def _entry_summary(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty:
        return pd.DataFrame()
    frame = snapshots.copy()
    numeric_cols = [
        "ai_product_pool_allowed",
        "selected_volume",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for variant, group in frame.groupby("variant", sort=False):
        rows.append(
            {
                "variant": variant,
                "candidate_count": int(len(group)),
                "open_candidate_count": int((group["candidate_status"].astype(str) == "open").sum()) if "candidate_status" in group else 0,
                "ai_blocked_count": int((group.get("skip_reason", "").astype(str) == "ai_product_pool_blocked").sum()) if "skip_reason" in group else 0,
                "sizing_zero_count": int((group.get("skip_reason", "").astype(str) == "sizing_zero_volume").sum()) if "skip_reason" in group else 0,
                "avg_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].mean()),
                "p10_corr_gate_weight": float(group["same_direction_correlation_gate_weight"].quantile(0.10)),
                "max_same_direction_corr": float(group["same_direction_correlation_max_corr"].max()),
                "avg_same_direction_corr": float(group["same_direction_correlation_avg_corr"].mean()),
                "selected_volume_sum": float(group["selected_volume"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, annual: pd.DataFrame, rolling: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")
    r63 = rolling[rolling["holding_days"].eq(63)].set_index("variant")
    r126 = rolling[rolling["holding_days"].eq(126)].set_index("variant")
    rows: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        variant = str(item["variant"])
        two_dd = _safe_float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0
        three_dd = _safe_float(cost3.loc[variant, "max_dd_pct"]) if variant in cost3.index else 0.0
        years = annual[annual["variant"].eq(variant)].copy()
        positive_year_rate = float((years["combo_net_pnl"] > 0).mean() * 100.0) if not years.empty else 0.0
        min_positive_product_count = int(years["positive_product_count"].min()) if not years.empty else 0
        h63_p05 = _safe_float(r63.loc[variant, "p05_return_pct"]) if variant in r63.index else 0.0
        h126_p05 = _safe_float(r126.loc[variant, "p05_return_pct"]) if variant in r126.index else 0.0
        hard_pass = bool(
            _safe_float(item["max_dd_pct"]) >= -40.0
            and _safe_float(item["max_broker10_margin_to_equity_pct"]) <= 100.0
            and int(item["days_over_100pct"]) == 0
            and two_dd >= -40.0
            and _safe_float(item["return_retention_vs_stage079_pct"]) >= 70.0
        )
        improvement_score = (
            _safe_float(item["return_retention_vs_stage079_pct"])
            + max(0.0, three_dd + 40.0) * 5.0
            + max(0.0, h63_p05 + 18.21691693788374)
            + max(0.0, h126_p05 + 10.970007402179235)
            + max(0.0, positive_year_rate - 85.0) * 0.2
        )
        rows.append(
            {
                **item,
                "two_x_max_dd_pct": two_dd,
                "three_x_max_dd_pct": three_dd,
                "positive_year_rate_pct": positive_year_rate,
                "min_positive_product_count": min_positive_product_count,
                "holding63_p05_return_pct": h63_p05,
                "holding126_p05_return_pct": h126_p05,
                "hard_pass": int(hard_pass),
                "improvement_score": improvement_score,
            }
        )
    ranked = sorted(rows, key=lambda item: (item["hard_pass"], item["improvement_score"]), reverse=True)
    hard = [item for item in ranked if item["hard_pass"] and item["variant"] != CONTROL]
    if hard:
        label = "expanded_low_risk_candidate_found_requires_robustness"
    else:
        label = "expanded_low_risk_scout_no_promotion_yet"
    return {
        "stage": "Stage539",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "baseline": CONTROL,
        "best_variant": ranked[0] if ranked else {},
        "hard_pass_expanded_variants": hard,
        "ranked": ranked,
        "pass_definition": "DD40 + broker100 + 2x成本DD40 + Stage079收益保留>=70%。若只靠未来可知结构全池胜出，不直接promotion。",
        "next_step": "若有扩池候选过硬闸门，再补多起点、年度剔除、贡献集中度、3x成本与真实券商保证金；若无，则回到Stage526监控或重新定义点时化品种选择器。",
    }


def _plot(summary: pd.DataFrame, cost: pd.DataFrame, annual: pd.DataFrame, rolling: pd.DataFrame, combo_daily: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_equity, ax_scatter, ax_year, ax_hold = axes.flatten()
    keep = [CONTROL]
    best = str(decision.get("best_variant", {}).get("variant", ""))
    if best and best not in keep:
        keep.append(best)
    for variant in summary.sort_values("improvement_score" if "improvement_score" in summary.columns else "total_return_pct", ascending=False)["variant"].tolist():
        if variant not in keep and len(keep) < 4:
            keep.append(variant)
    color_map = {
        CONTROL: "#111827",
        "exp24_all_r050_pc20_maxpos6": "#64748b",
        "exp24_ai12_r060_pc20_maxpos6": "#2563eb",
        "exp24_ai12_r070_pc20_maxpos6": "#dc2626",
        "exp24_simple12_r060_pc20_maxpos6": "#059669",
        "exp24_ai12_r060_pc15_maxpos8": "#7c3aed",
    }
    for variant, frame in combo_daily[combo_daily["variant"].isin(keep)].groupby("variant", sort=False):
        frame = frame.sort_values("date")
        ax_equity.plot(frame["date"], frame["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_equity.set_title("权益曲线：Stage526 vs 扩池候选")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)

    ax_scatter.scatter(
        summary["return_retention_vs_stage079_pct"],
        summary["max_broker10_margin_to_equity_pct"],
        s=np.maximum(summary["total_return_pct"], 1.0) / 14.0,
        c=[color_map.get(v, "#94a3b8") for v in summary["variant"]],
        alpha=0.80,
    )
    for row in summary.itertuples(index=False):
        ax_scatter.annotate(str(row.variant).replace("exp24_", ""), (row.return_retention_vs_stage079_pct, row.max_broker10_margin_to_equity_pct), fontsize=7)
    ax_scatter.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.axvline(70, color="#64748b", linestyle=":", linewidth=1)
    ax_scatter.set_title("收益保留 vs broker10保证金")
    ax_scatter.set_xlabel("相对Stage079收益保留%")
    ax_scatter.set_ylabel("最大broker10保证金/权益%")
    ax_scatter.grid(alpha=0.25)

    annual_keep = annual[annual["variant"].isin(keep)].copy()
    pivot = annual_keep.pivot(index="year", columns="variant", values="positive_product_count")
    pivot.plot(kind="bar", ax=ax_year, color=[color_map.get(col, "#94a3b8") for col in pivot.columns])
    ax_year.set_title("每年正贡献产品数")
    ax_year.set_ylabel("产品数")
    ax_year.grid(axis="y", alpha=0.25)
    ax_year.legend(fontsize=7)

    h = rolling[(rolling["variant"].isin(keep)) & (rolling["holding_days"].isin([63, 126]))].copy()
    pivot_h = h.pivot(index="variant", columns="holding_days", values="p05_return_pct").reindex(keep)
    pivot_h.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("3/6个月p05收益")
    ax_hold.set_xlabel("%")
    ax_hold.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    annual: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
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
            "return_retention_vs_stage079_pct",
            "return_vs_stage526_pct",
            "max_dd_pct",
            "max_dd_pct_2x",
            "max_dd_pct_3x",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "total_trade_count",
        ]
    ].sort_values("return_retention_vs_stage079_pct", ascending=False)
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
    annual_view = annual.groupby("variant", as_index=False).agg(
        positive_year_rate_pct=("combo_net_pnl", lambda x: float((x > 0).mean() * 100.0)),
        min_positive_product_count=("positive_product_count", "min"),
        median_positive_product_count=("positive_product_count", "median"),
        max_top_positive_share_pct=("top_positive_share_of_positive_pnl_pct", "max"),
    )
    lines = [
        "# Stage539 低单笔风险扩池与相关性预算scout",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：A/C结构scout；不改入场/出场alpha，固定使用真实下一窗口成交、exact position margin、xsmom真实承载。",
        "- 反过拟合边界：扩池品种来自既有结构预筛；动态top12在2022前只允许Stage78静态池+fu，避免用未来可见全池污染早期。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 总览",
        "",
        _md_table(view),
        "",
        "## 3/6个月持有体验",
        "",
        _md_table(hold_view, max_rows=20),
        "",
        "## 年度趋势捕捉与集中度",
        "",
        _md_table(annual_view),
        "",
        "## 入场候选与相关性门控诊断",
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
    universe = _build_expanded_universe()
    _build_stage539_eligibility(universe)
    expanded_metadata = _metadata_for_universe(EXPANDED_UNIVERSE_PATH)
    identity_map = s519._product_identity_cluster_map(expanded_metadata)

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in VARIANTS:
        print(f"[stage539] running {spec.variant}", flush=True)
        daily, positions, snapshots = _run_variant(spec, expanded_metadata, identity_map)
        daily_frames.append(daily)
        position_frames.append(positions)
        if not snapshots.empty:
            snapshot_frames.append(snapshots)

    expanded_c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    expanded_positions = pd.concat(position_frames, ignore_index=True, sort=False)
    expanded_margin_daily, expanded_product_margin = s513._position_margin(expanded_positions, expanded_metadata)
    xsmom_daily = s513._load_xsmom_daily()
    expanded_combo_daily = s517._combine_daily(expanded_c3_daily, expanded_margin_daily, xsmom_daily)

    control_daily = _load_control_daily()
    control_positions = _load_control_positions()
    control_metadata = s513._metadata()
    _control_margin_daily, control_product_margin = s513._position_margin(control_positions, control_metadata)

    combo_daily = pd.concat([control_daily, expanded_combo_daily], ignore_index=True, sort=False)
    product_margin = pd.concat([control_product_margin, expanded_product_margin], ignore_index=True, sort=False)
    positions = pd.concat([control_positions, expanded_positions], ignore_index=True, sort=False)
    snapshots = pd.concat(snapshot_frames, ignore_index=True, sort=False) if snapshot_frames else pd.DataFrame()

    summary, cost = _combine_summary_and_cost(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    annual = _annual_product_harvest(product_margin, combo_daily)
    entry_summary = _entry_summary(snapshots)
    decision = _decision(summary, cost, annual, rolling)
    summary["hard_pass"] = summary["variant"].map({item["variant"]: item["hard_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["improvement_score"] = summary["variant"].map({item["variant"]: item["improvement_score"] for item in decision["ranked"]}).fillna(0.0)

    _plot(summary, cost, annual, rolling, combo_daily, decision)
    _write_report(summary, cost, rolling, annual, entry_summary, decision)

    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    snapshots.to_csv(ENTRY_SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
