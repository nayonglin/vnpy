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
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO  # noqa: E402


MODEL_TAG = "stage541_single_product_opportunity_map_v1"
OUTPUT_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
SLEEVE_CAPITAL = 115_000.0
RISK_MULTIPLIER = 0.50
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
CORE_BAD_WINDOW_1 = (pd.Timestamp("2021-09-16"), pd.Timestamp("2022-02-11"))
CORE_BAD_WINDOW_2 = (pd.Timestamp("2022-03-09"), pd.Timestamp("2022-12-07"))
CORE = "stage526_r080_pc25_maxpos4"

FULL_MARKET_UNIVERSE_IN = OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE526_POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"

SINGLE_UNIVERSE_DIR = OUTPUT_DIR / f"{OUTPUT_PREFIX}_single_universes_{MODEL_TAG}"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class ProductSpec:
    product_vt_symbol: str
    universe_path: Path
    is_core_product: bool
    exchange: str
    product: str


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


def _product_from_contract(vt_symbol: object) -> str:
    return s513._product_from_contract(vt_symbol)


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


def _load_core_products() -> set[str]:
    frame = pd.read_csv(STAGE526_POSITIONS_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    return set(frame.loc[pd.to_numeric(frame["end_pos"], errors="coerce").fillna(0.0).abs() > 0, "product_vt_symbol"].astype(str))


def _load_core_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE526_DAILY_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq("r080_pc25_maxpos4")].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["core_total_net_pnl"] = pd.to_numeric(frame["total_net_pnl"], errors="coerce").fillna(0.0)
    frame["core_account_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce").fillna(ACCOUNT_CAPITAL)
    return frame[["date", "core_total_net_pnl", "core_account_equity"]].dropna(subset=["date"]).sort_values("date")


def _build_product_specs() -> tuple[list[ProductSpec], pd.DataFrame]:
    if not FULL_MARKET_UNIVERSE_IN.exists():
        raise FileNotFoundError(FULL_MARKET_UNIVERSE_IN)
    SINGLE_UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(FULL_MARKET_UNIVERSE_IN, encoding="utf-8-sig")
    universe["product_vt_symbol"] = universe["product_vt_symbol"].astype(str)
    if "eligible" in universe.columns:
        universe = universe[pd.to_numeric(universe["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    core_products = _load_core_products()
    specs: list[ProductSpec] = []
    for row in universe.sort_values(["exchange", "product_vt_symbol"]).itertuples(index=False):
        product_vt_symbol = str(row.product_vt_symbol)
        product = str(getattr(row, "product", product_vt_symbol.split(".")[0]))
        path = SINGLE_UNIVERSE_DIR / f"{product_vt_symbol.replace('.', '_')}.csv"
        single = universe[universe["product_vt_symbol"].eq(product_vt_symbol)].copy()
        single.to_csv(path, index=False, encoding="utf-8-sig")
        specs.append(
            ProductSpec(
                product_vt_symbol=product_vt_symbol,
                universe_path=path,
                is_core_product=product_vt_symbol in core_products,
                exchange=str(getattr(row, "exchange", product_vt_symbol.split(".")[-1])),
                product=product,
            )
        )
    return specs, universe


def _metadata(universe_path: Path) -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(universe_path))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _run_product(spec: ProductSpec) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    metadata = _metadata(spec.universe_path)
    identity_map = s519._product_identity_cluster_map(metadata)
    overrides = {
        **s513._c3_overrides(START_DT),
        **s519._product_cap_overrides(1.0, identity_map),
        "product_universe_csv_path": str(spec.universe_path),
        "max_concurrent_positions": 1,
        "max_single_trade_capital_usage_ratio": 0.70,
        "enable_same_direction_correlation_gate": False,
        "enable_ai_product_pool_filter": False,
    }
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
        risk_ratio=BASE_RISK_RATIO * RISK_MULTIPLIER,
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
        dates = _load_core_daily()["date"].copy()
        daily = pd.DataFrame(
            {
                "date": dates,
                "net_pnl": 0.0,
                "trade_count": 0.0,
                "slippage": 0.0,
                "commission": 0.0,
                "turnover": 0.0,
                "empty_engine_result": 1,
            }
        )
    else:
        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["empty_engine_result"] = 0
    daily["sleeve_equity"] = SLEEVE_CAPITAL + daily["net_pnl"].cumsum()
    daily["product_vt_symbol"] = spec.product_vt_symbol
    daily["is_core_product"] = int(spec.is_core_product)
    daily["exchange"] = spec.exchange
    daily["product"] = spec.product

    positions = build_positions_df(engine)
    if positions.empty:
        positions = pd.DataFrame()
    else:
        positions["product_vt_symbol"] = spec.product_vt_symbol
        positions["is_core_product"] = int(spec.is_core_product)
        positions["exchange"] = spec.exchange
        positions["product"] = spec.product
        positions["variant"] = spec.product_vt_symbol
        positions["combo_variant"] = spec.product_vt_symbol
    margin_daily = pd.DataFrame()
    if not positions.empty:
        margin_daily, _product_margin = s513._position_margin(positions, metadata)
        margin_daily["product_vt_symbol"] = spec.product_vt_symbol
    return daily, positions, margin_daily


def _summarize(
    daily: pd.DataFrame,
    margin_daily: pd.DataFrame,
    core_daily: pd.DataFrame,
    universe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    features = universe.set_index("product_vt_symbol")
    for product, frame in daily.groupby("product_vt_symbol", sort=False):
        ordered = frame.sort_values("date").copy()
        equity = pd.Series(ordered["sleeve_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        net_pnl = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
        merged = ordered[["date", "net_pnl"]].merge(core_daily, on="date", how="left")
        product_corr = merged["net_pnl"].corr(merged["core_total_net_pnl"]) if merged["net_pnl"].std() > 0 else 0.0
        if pd.isna(product_corr):
            product_corr = 0.0
        margin = margin_daily[margin_daily["product_vt_symbol"].eq(product)].copy()
        margin["c3_margin_exact"] = pd.to_numeric(margin.get("c3_margin_exact", 0.0), errors="coerce").fillna(0.0)
        margin_by_date = margin[["date", "c3_margin_exact"]].drop_duplicates("date") if not margin.empty else pd.DataFrame(columns=["date", "c3_margin_exact"])
        margin_merged = ordered[["date", "sleeve_equity"]].merge(margin_by_date, on="date", how="left")
        margin_merged["c3_margin_exact"] = pd.to_numeric(margin_merged.get("c3_margin_exact", 0.0), errors="coerce").fillna(0.0)
        broker_ratio = (
            margin_merged["c3_margin_exact"].to_numpy(dtype=float)
            * BROKER_MARGIN_MULTIPLIER
            / np.maximum(margin_merged["sleeve_equity"].to_numpy(dtype=float), 1.0)
            * 100.0
        )
        ordered["year"] = pd.to_datetime(ordered["date"]).dt.year
        for year, group in ordered.groupby("year", sort=True):
            annual_rows.append(
                {
                    "product_vt_symbol": product,
                    "year": int(year),
                    "is_core_product": int(group["is_core_product"].iloc[0]),
                    "net_pnl": float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum()),
                    "trade_count": float(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).sum()),
                    "slippage": float(pd.to_numeric(group["slippage"], errors="coerce").fillna(0.0).sum()),
                    "active_days": int((pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).abs() > 1e-12).sum()),
                }
            )
        bad1 = ordered[(ordered["date"] >= CORE_BAD_WINDOW_1[0]) & (ordered["date"] <= CORE_BAD_WINDOW_1[1])]
        bad2 = ordered[(ordered["date"] >= CORE_BAD_WINDOW_2[0]) & (ordered["date"] <= CORE_BAD_WINDOW_2[1])]
        f = features.loc[product].to_dict() if product in features.index else {}
        annual_product = pd.DataFrame([row for row in annual_rows if row["product_vt_symbol"] == product])
        active_years = annual_product[annual_product["trade_count"] > 0]
        positive_active_years = int((active_years["net_pnl"] > 0.0).sum()) if not active_years.empty else 0
        active_year_count = int(len(active_years))
        total_pnl = float(net_pnl.sum())
        summary_rows.append(
            {
                "product_vt_symbol": product,
                "exchange": str(ordered["exchange"].iloc[0]),
                "product": str(ordered["product"].iloc[0]),
                "is_core_product": int(ordered["is_core_product"].iloc[0]),
                "end_equity": float(equity.iloc[-1]) if not equity.empty else SLEEVE_CAPITAL,
                "total_pnl": total_pnl,
                "total_return_pct": total_pnl / SLEEVE_CAPITAL * 100.0,
                "max_dd_pct": _max_drawdown_pct(equity),
                "ulcer_pct": _ulcer_pct(equity),
                "sharpe": _sharpe(equity),
                "trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
                "slippage": float(pd.to_numeric(ordered["slippage"], errors="coerce").fillna(0.0).sum()),
                "active_days": int((net_pnl.abs() > 1e-12).sum()),
                "active_year_count": active_year_count,
                "positive_active_years": positive_active_years,
                "positive_active_year_rate_pct": positive_active_years / active_year_count * 100.0 if active_year_count else 0.0,
                "worst_active_year_pnl": float(active_years["net_pnl"].min()) if not active_years.empty else 0.0,
                "best_active_year_pnl": float(active_years["net_pnl"].max()) if not active_years.empty else 0.0,
                "core_daily_pnl_corr": float(product_corr),
                "bad_window_2021_2022_pnl": float(pd.to_numeric(bad1["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "bad_window_2022_pnl": float(pd.to_numeric(bad2["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "max_broker10_margin_to_sleeve_equity_pct": float(np.max(broker_ratio)) if len(broker_ratio) else 0.0,
                "days_over_100pct": int(np.sum(broker_ratio > 100.0 + 1e-9)) if len(broker_ratio) else 0,
                "estimated_margin_per_contract": _safe_float(f.get("estimated_margin_per_contract", 0.0)),
                "recent_median_volume": _safe_float(f.get("recent_median_volume", 0.0)),
                "recent_bar_coverage_ratio": _safe_float(f.get("recent_bar_coverage_ratio", 0.0)),
                "market_trend_efficiency_60d_median": _safe_float(f.get("market_trend_efficiency_60d_median", f.get("market_trend_efficiency_60d", 0.0))),
                "market_trend_efficiency_120d_median": _safe_float(f.get("market_trend_efficiency_120d_median", f.get("market_trend_efficiency_120d", 0.0))),
            }
        )
    summary = pd.DataFrame(summary_rows)
    annual = pd.DataFrame(annual_rows)
    if not summary.empty:
        summary["candidate_materiality_pass"] = (
            (summary["is_core_product"].eq(0))
            & (summary["total_pnl"] >= max(ACCOUNT_CAPITAL * 0.01, SLEEVE_CAPITAL * 0.10))
            & (summary["positive_active_years"] >= 3)
            & (summary["core_daily_pnl_corr"].abs() <= 0.30)
            & (summary["max_broker10_margin_to_sleeve_equity_pct"] <= 80.0)
            & (summary["active_year_count"] >= 3)
        ).astype(int)
        summary["opportunity_score"] = (
            summary["total_return_pct"]
            + summary["positive_active_years"] * 5.0
            - summary["core_daily_pnl_corr"].abs() * 20.0
            - np.maximum(summary["max_broker10_margin_to_sleeve_equity_pct"] - 80.0, 0.0) * 0.5
            + np.maximum(summary["bad_window_2022_pnl"], 0.0) / SLEEVE_CAPITAL * 10.0
        )
        summary.sort_values(["candidate_materiality_pass", "opportunity_score", "total_pnl"], ascending=[False, False, False], inplace=True)
    return summary, annual


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    noncore = summary[summary["is_core_product"].eq(0)].copy()
    candidates = noncore[noncore["candidate_materiality_pass"].eq(1)].copy()
    return {
        "stage": "Stage541",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "single_product_candidates_found_for_next_sleeve_test" if not candidates.empty else "single_product_map_no_material_noncore_candidate",
        "diagnostic_scope": "57 eligible products run one-by-one with 115k sleeve, risk050, true next-real-open execution; product-level opportunity map only, not a promoted universe.",
        "candidate_definition": "non-core, total_pnl >= max(1% account, 10% sleeve), positive active years >=3, abs corr to Stage526 daily pnl <=0.30, broker10 sleeve margin <=80%, active years >=3.",
        "coverage": {
            "products": int(len(summary)),
            "core_products": int(summary["is_core_product"].sum()) if not summary.empty else 0,
            "noncore_products": int((summary["is_core_product"] == 0).sum()) if not summary.empty else 0,
            "material_candidates": int(len(candidates)),
            "profitable_noncore_products": int((noncore["total_pnl"] > 0.0).sum()) if not noncore.empty else 0,
        },
        "top_noncore": noncore.head(12).to_dict(orient="records"),
        "material_candidates": candidates.to_dict(orient="records"),
        "next_step": "If material candidates exist, predeclare a non-replacing sleeve basket and run A/C. If not, stop product-sleeve tuning and move to ex-ante feature/data sources.",
    }


def _plot(summary: pd.DataFrame, annual: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_scatter, ax_bar, ax_heat, ax_margin = axes.flatten()
    noncore = summary[summary["is_core_product"].eq(0)].copy()
    core = summary[summary["is_core_product"].eq(1)].copy()
    ax_scatter.scatter(
        noncore["core_daily_pnl_corr"],
        noncore["total_return_pct"],
        s=np.maximum(noncore["positive_active_years"], 1) * 25,
        c=noncore["max_broker10_margin_to_sleeve_equity_pct"],
        cmap="viridis_r",
        alpha=0.75,
        label="non-core",
    )
    ax_scatter.scatter(core["core_daily_pnl_corr"], core["total_return_pct"], s=28, c="#111827", alpha=0.55, label="core ref")
    ax_scatter.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.axvline(0.30, color="#64748b", linestyle=":", linewidth=1)
    ax_scatter.axvline(-0.30, color="#64748b", linestyle=":", linewidth=1)
    ax_scatter.set_title("单品种收益 vs Stage526日PnL相关性")
    ax_scatter.set_xlabel("corr")
    ax_scatter.set_ylabel("115k sleeve return %")
    ax_scatter.legend(fontsize=7)
    ax_scatter.grid(alpha=0.25)

    top = noncore.sort_values("total_pnl", ascending=False).head(12).copy()
    colors = ["#059669" if value > 0 else "#dc2626" for value in top["total_pnl"]]
    ax_bar.barh(top["product_vt_symbol"], top["total_pnl"], color=colors)
    ax_bar.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_bar.set_title("非核心产品 standalone PnL Top12")
    ax_bar.grid(axis="x", alpha=0.25)

    heat_products = top["product_vt_symbol"].tolist()
    annual_view = annual[annual["product_vt_symbol"].isin(heat_products)].copy()
    pivot = annual_view.pivot_table(index="product_vt_symbol", columns="year", values="net_pnl", aggfunc="sum").reindex(heat_products)
    im = ax_heat.imshow(pivot.fillna(0.0).to_numpy(dtype=float), aspect="auto", cmap="RdYlGn")
    ax_heat.set_yticks(range(len(pivot.index)))
    ax_heat.set_yticklabels(pivot.index, fontsize=8)
    ax_heat.set_xticks(range(len(pivot.columns)))
    ax_heat.set_xticklabels(pivot.columns, rotation=45, fontsize=8)
    ax_heat.set_title("Top非核心产品年度PnL热力图")
    fig.colorbar(im, ax=ax_heat, fraction=0.046, pad=0.04)

    ax_margin.scatter(
        noncore["estimated_margin_per_contract"],
        noncore["total_pnl"],
        c=noncore["positive_active_years"],
        cmap="plasma",
        alpha=0.75,
    )
    ax_margin.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_margin.set_title("合约估算保证金 vs 产品PnL")
    ax_margin.set_xlabel("estimated margin per contract")
    ax_margin.set_ylabel("total pnl")
    ax_margin.grid(alpha=0.25)
    fig.suptitle("Stage541 single-product opportunity map", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, annual: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_noncore = summary[summary["is_core_product"].eq(0)].head(20)
    core_ref = summary[summary["is_core_product"].eq(1)].sort_values("total_pnl", ascending=False).head(12)
    material = summary[summary["candidate_materiality_pass"].eq(1)]
    annual_top = annual[annual["product_vt_symbol"].isin(top_noncore["product_vt_symbol"].head(12))]
    annual_pivot = annual_top.pivot_table(index="product_vt_symbol", columns="year", values="net_pnl", aggfunc="sum").reset_index()
    columns = [
        "product_vt_symbol",
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "trade_count",
        "positive_active_years",
        "active_year_count",
        "core_daily_pnl_corr",
        "bad_window_2022_pnl",
        "max_broker10_margin_to_sleeve_equity_pct",
        "candidate_materiality_pass",
        "opportunity_score",
    ]
    lines = [
        "# Stage541 单品种机会地图",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：产品选择诊断；不是晋级版本，不直接按历史收益建池。",
        "- 口径：每个产品单独用 `115000` sleeve、`risk_multiplier=0.50`、真实下一窗口成交、最大持仓产品数1运行。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 非核心产品Top",
        "",
        _md_table(top_noncore[columns], max_rows=20),
        "",
        "## 材料性候选",
        "",
        _md_table(material[columns], max_rows=20),
        "",
        "## 核心产品参考",
        "",
        _md_table(core_ref[columns], max_rows=12),
        "",
        "## 非核心Top年度PnL",
        "",
        _md_table(annual_pivot, max_rows=20),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    specs, universe = _build_product_specs()
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    for index, spec in enumerate(specs, start=1):
        print(f"[stage541] {index:02d}/{len(specs)} {spec.product_vt_symbol}", flush=True)
        daily, positions, margin_daily = _run_product(spec)
        daily_frames.append(daily)
        if not positions.empty:
            position_frames.append(positions)
        if not margin_daily.empty:
            margin_frames.append(margin_daily)
    daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    margin_daily = pd.concat(margin_frames, ignore_index=True, sort=False) if margin_frames else pd.DataFrame()
    core_daily = _load_core_daily()
    summary, annual = _summarize(daily, margin_daily, core_daily, universe)
    decision = _decision(summary)
    _plot(summary, annual)
    _write_report(summary, annual, decision)

    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
