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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402


MODEL_TAG = "stage532_stage526_corr_gate_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage532_stage526_corr_gate_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CONTROL_VARIANT = "r080_pc25_maxpos4_control"
CORR_VARIANT = "r080_pc25_maxpos4_corr20_f50"
NO_CORR_VARIANT = "r080_pc25_maxpos4_no_corr_gate"
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
CANDIDATE_SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_snapshots_{MODEL_TAG}.csv"
GATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_summary_{MODEL_TAG}.csv"
COST_FAILURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_failure_windows_{MODEL_TAG}.csv"
EDGE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_edge_daily_{MODEL_TAG}.csv"
PRODUCT_ATTR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_product_attr_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    overrides: dict[str, Any]
    note: str


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


def _variants(identity_map: str) -> tuple[VariantSpec, ...]:
    pc25_maxpos4 = {**s519._product_cap_overrides(0.25, identity_map), "max_concurrent_positions": 4}
    corr_gate = {
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": 0.60,
        "same_direction_correlation_gate_full": 0.80,
        "same_direction_correlation_gate_weight_floor": 0.50,
    }
    no_corr_gate = {"enable_same_direction_correlation_gate": False}
    return (
        VariantSpec(
            CONTROL_VARIANT,
            "control: Stage526 current corr20 floor35 + pc25 + maxpos4",
            0.80,
            dict(pc25_maxpos4),
            "Stage526主研究候选复刻；继承C3 override的同向相关性门控 floor0.35。",
        ),
        VariantSpec(
            CORR_VARIANT,
            "C1: relax same-direction corr20 floor35 -> floor50",
            0.80,
            {**pc25_maxpos4, **corr_gate},
            "只把已有同方向20日相关性拥挤门控下限从0.35放宽到0.50；冻结0.60-0.80，不扫阈值。",
        ),
        VariantSpec(
            NO_CORR_VARIANT,
            "C2: disable same-direction corr20 gate",
            0.80,
            {**pc25_maxpos4, **no_corr_gate},
            "完全关闭同向相关性门控，用于判断当前候选是否需要该模块。",
        ),
    )


def _run_variant_with_candidates(
    spec: VariantSpec,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s517.s506._patch_stage506_raw_roots()
    overrides = s513._c3_overrides(s517.START_DT)
    preload_start = max(s517.PRELOAD_START_DT, s517.START_DT - timedelta(days=365))
    _, open_map = s517.s506.s501._seed_proxy_maps()
    engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s517.Interval.DAILY,
        start=preload_start,
        end=s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=s517.C3_CAPITAL,
    )
    setting = s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s517.BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = s517.C3_CAPITAL
    setting.update(spec.overrides)
    engine.add_strategy(s517.QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= s517.START_DT.date()) & (daily.index <= s517.END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = s517.C3_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["note"] = spec.note

    strategy = getattr(engine, "strategy", None)
    daily["portfolio_margin_deleverage_count"] = int(getattr(strategy, "portfolio_margin_deleverage_count", 0) or 0)
    daily["risk_cluster_heat_deleverage_count"] = int(getattr(strategy, "risk_cluster_heat_deleverage_count", 0) or 0)
    daily["portfolio_drawdown_deleverage_count"] = int(getattr(strategy, "portfolio_drawdown_deleverage_count", 0) or 0)

    positions = s517.build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier

    candidates = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []) if strategy else [])
    if not candidates.empty:
        candidates["variant"] = spec.variant
        candidates["label"] = spec.label
        candidates["risk_multiplier"] = spec.risk_multiplier
        candidates["date"] = pd.to_datetime(candidates.get("date"), errors="coerce").dt.normalize()
    return daily, positions, candidates


def _summary_and_cost(combo_daily: pd.DataFrame, specs: tuple[VariantSpec, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec_map = {spec.variant: spec for spec in specs}
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(frame, cost_multiplier)
            row = s516._metrics_from_equity(
                equity,
                frame,
                variant=variant,
                label=spec.label,
                cost_multiplier=cost_multiplier,
            )
            row.update({"risk_multiplier": spec.risk_multiplier, "note": spec.note})
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_dd_window(equity: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown_pct(equity)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(equity.loc[:trough].idxmax())
    return peak.normalize(), trough.normalize(), float(dd.loc[trough])


def _cost_failure_windows(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date").copy()
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(ordered, cost_multiplier)
            peak, trough, max_dd = _max_dd_window(equity)
            window = ordered[ordered["date"].between(peak, trough)].copy()
            start_eq = float(equity.loc[peak]) if peak in equity.index else float(equity.iloc[0])
            end_eq = float(equity.loc[trough]) if trough in equity.index else float(equity.iloc[-1])
            rows.append(
                {
                    "variant": variant,
                    "label": str(ordered["label"].iloc[0]),
                    "cost_multiplier": cost_multiplier,
                    "peak_date": peak.date().isoformat(),
                    "trough_date": trough.date().isoformat(),
                    "window_days": int(len(window)),
                    "max_dd_pct": max_dd,
                    "window_return_pct": (end_eq / max(start_eq, 1e-9) - 1.0) * 100.0,
                    "window_total_net_pnl": float(window["total_net_pnl"].sum()) if len(window) else 0.0,
                    "window_c3_net_pnl": float(window["net_pnl"].sum()) if len(window) else 0.0,
                    "window_xsmom_net_pnl": float(window["xsmom_true_daily_pnl"].sum()) if len(window) else 0.0,
                    "window_total_slippage": float(window["total_slippage"].sum()) if len(window) else 0.0,
                    "window_trade_count": float(window["trade_count"].sum()) if len(window) else 0.0,
                    "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()) if len(window) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _rolling_delta(rolling: pd.DataFrame) -> pd.DataFrame:
    control = rolling[rolling["variant"].eq(CONTROL_VARIANT)].copy()
    if control.empty:
        return pd.DataFrame()
    baseline = control.set_index("holding_days")
    rows: list[dict[str, Any]] = []
    for row in rolling.itertuples(index=False):
        horizon = int(row.holding_days)
        if horizon not in baseline.index:
            continue
        base = baseline.loc[horizon]
        rows.append(
            {
                "variant": str(row.variant),
                "label": str(row.label),
                "holding_days": horizon,
                "p05_return_pct": float(row.p05_return_pct),
                "p05_delta_vs_control": float(row.p05_return_pct) - float(base["p05_return_pct"]),
                "median_return_pct": float(row.median_return_pct),
                "median_delta_vs_control": float(row.median_return_pct) - float(base["median_return_pct"]),
                "positive_rate_pct": float(row.positive_rate_pct),
                "positive_rate_delta_vs_control": float(row.positive_rate_pct) - float(base["positive_rate_pct"]),
                "min_window_dd_pct": float(row.min_window_dd_pct),
                "min_window_dd_delta_vs_control": float(row.min_window_dd_pct) - float(base["min_window_dd_pct"]),
            }
        )
    return pd.DataFrame(rows)


def _gate_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    frame = candidates.copy()
    numeric = [
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "selected_volume",
        "selected_volume_ungated",
    ]
    for column in numeric:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    if "candidate_status" not in frame.columns:
        frame["candidate_status"] = ""
    enabled = frame["same_direction_correlation_gate_enabled"].gt(0)
    scaled = enabled & frame["same_direction_correlation_gate_weight"].lt(0.999999)
    zeroed = enabled & frame["selected_volume"].eq(0) & frame["selected_volume_ungated"].gt(0)
    rows: list[dict[str, Any]] = []
    for variant, one in frame.groupby("variant", sort=False):
        one_enabled = one[one["same_direction_correlation_gate_enabled"].gt(0)]
        one_scaled = one[
            one["same_direction_correlation_gate_enabled"].gt(0)
            & one["same_direction_correlation_gate_weight"].lt(0.999999)
        ]
        one_opened = one[one["candidate_status"].astype(str).eq("opened")]
        rows.append(
            {
                "variant": variant,
                "candidate_rows": int(len(one)),
                "opened_rows": int(len(one_opened)),
                "gate_enabled_rows": int(len(one_enabled)),
                "gate_scaled_rows": int(len(one_scaled)),
                "gate_zeroed_rows": int((zeroed & frame["variant"].eq(variant)).sum()),
                "scaled_opened_rows": int(len(one_scaled[one_scaled["candidate_status"].astype(str).eq("opened")])),
                "mean_gate_weight_enabled": float(one_enabled["same_direction_correlation_gate_weight"].mean()) if len(one_enabled) else 1.0,
                "min_gate_weight_enabled": float(one_enabled["same_direction_correlation_gate_weight"].min()) if len(one_enabled) else 1.0,
                "mean_scaled_max_corr": float(one_scaled["same_direction_correlation_max_corr"].mean()) if len(one_scaled) else 0.0,
                "max_scaled_max_corr": float(one_scaled["same_direction_correlation_max_corr"].max()) if len(one_scaled) else 0.0,
                "mean_scaled_active_count": float(one_scaled["same_direction_correlation_active_count"].mean()) if len(one_scaled) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _edge_daily(combo_daily: pd.DataFrame) -> pd.DataFrame:
    control = combo_daily[combo_daily["variant"].eq(CONTROL_VARIANT)][["date", "total_net_pnl", "account_equity"]].copy()
    if control.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for variant, candidate in combo_daily[~combo_daily["variant"].eq(CONTROL_VARIANT)].groupby("variant", sort=False):
        candidate = candidate[["date", "total_net_pnl", "account_equity"]].copy()
        merged = control.merge(candidate, on="date", how="inner", suffixes=("_control", "_candidate"))
        merged["variant"] = variant
        merged["edge_pnl"] = merged["total_net_pnl_candidate"] - merged["total_net_pnl_control"]
        merged["edge_cum"] = merged["edge_pnl"].cumsum()
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _product_bad_window_attr(product_margin: pd.DataFrame, cost_failure: pd.DataFrame) -> pd.DataFrame:
    if product_margin.empty or cost_failure.empty:
        return pd.DataFrame()
    product = product_margin.copy()
    product["date"] = pd.to_datetime(product["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "holding_pnl", "trading_pnl", "c3_margin_exact"]:
        if column not in product.columns:
            product[column] = 0.0
        product[column] = pd.to_numeric(product[column], errors="coerce").fillna(0.0)
    rows: list[pd.DataFrame] = []
    for window in cost_failure[cost_failure["cost_multiplier"].eq(3.0)].itertuples(index=False):
        start = pd.Timestamp(window.peak_date)
        end = pd.Timestamp(window.trough_date)
        frame = product[
            product["variant"].eq(window.variant)
            & product["date"].between(start, end)
        ].copy()
        if frame.empty:
            continue
        grouped = (
            frame.groupby("product_vt_symbol", as_index=False)
            .agg(
                net_pnl=("net_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                max_c3_margin=("c3_margin_exact", "max"),
                active_days=("c3_margin_exact", lambda item: int((item > 0.0).sum())),
            )
            .sort_values("net_pnl", ascending=True)
        )
        grouped["variant"] = window.variant
        grouped["cost_multiplier"] = float(window.cost_multiplier)
        grouped["peak_date"] = window.peak_date
        grouped["trough_date"] = window.trough_date
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling_delta: pd.DataFrame, gate_summary: pd.DataFrame) -> dict[str, Any]:
    control_row = summary[summary["variant"].eq(CONTROL_VARIANT)]
    if control_row.empty:
        raise RuntimeError("missing control summary")
    control = control_row.iloc[0]
    control_cost = cost[cost["variant"].eq(CONTROL_VARIANT)].set_index("cost_multiplier")
    control_3x_dd = _safe_float(control_cost.loc[3.0, "max_dd_pct"]) if 3.0 in control_cost.index else 0.0
    candidate_results: list[dict[str, Any]] = []
    for _, candidate in summary[~summary["variant"].eq(CONTROL_VARIANT)].iterrows():
        variant = str(candidate["variant"])
        candidate_cost = cost[cost["variant"].eq(variant)].set_index("cost_multiplier")
        candidate_2x_dd = _safe_float(candidate_cost.loc[2.0, "max_dd_pct"]) if 2.0 in candidate_cost.index else 0.0
        candidate_3x_dd = _safe_float(candidate_cost.loc[3.0, "max_dd_pct"]) if 3.0 in candidate_cost.index else 0.0
        h63 = rolling_delta[rolling_delta["variant"].eq(variant) & rolling_delta["holding_days"].eq(63)]
        h126 = rolling_delta[rolling_delta["variant"].eq(variant) & rolling_delta["holding_days"].eq(126)]
        h63_delta = _safe_float(h63["p05_delta_vs_control"].iloc[0]) if not h63.empty else 0.0
        h126_delta = _safe_float(h126["p05_delta_vs_control"].iloc[0]) if not h126.empty else 0.0
        hard_pass = int(
            int(candidate["dd40_pass"]) == 1
            and int(candidate["broker10_100_pass"]) == 1
            and candidate_2x_dd >= -40.0
        )
        replacement_pass = int(
            hard_pass
            and _safe_float(candidate["total_return_pct"]) >= _safe_float(control["total_return_pct"]) * 0.95
            and _safe_float(candidate["max_dd_pct"]) >= _safe_float(control["max_dd_pct"]) - 1e-9
            and _safe_float(candidate["ulcer_pct"]) <= _safe_float(control["ulcer_pct"]) + 1e-9
            and h63_delta >= 0.0
            and h126_delta >= 0.0
        )
        stress_upgrade = int(candidate_3x_dd > control_3x_dd and candidate_3x_dd >= -40.0)
        gate = gate_summary[gate_summary["variant"].eq(variant)].to_dict(orient="records")
        candidate_results.append(
            {
                "variant": variant,
                "replacement_pass": replacement_pass,
                "hard_pass": hard_pass,
                "stress_upgrade": stress_upgrade,
                "return_retention_vs_control_pct": _safe_float(candidate["total_return_pct"])
                / max(_safe_float(control["total_return_pct"]), 1e-9)
                * 100.0,
                "total_return_pct": _safe_float(candidate["total_return_pct"]),
                "max_dd_pct": _safe_float(candidate["max_dd_pct"]),
                "ulcer_pct": _safe_float(candidate["ulcer_pct"]),
                "cost2x_max_dd_pct": candidate_2x_dd,
                "cost3x_max_dd_pct": candidate_3x_dd,
                "h63_p05_delta_vs_control": h63_delta,
                "h126_p05_delta_vs_control": h126_delta,
                "broker10_max_pct": _safe_float(candidate["max_broker10_margin_to_equity_pct"]),
                "days_over_100pct": int(candidate["days_over_100pct"]),
                "gate_summary": gate[0] if gate else {},
            }
        )
    best = max(
        candidate_results,
        key=lambda item: (
            int(item["replacement_pass"]),
            int(item["hard_pass"]),
            int(item["stress_upgrade"]),
            float(item["cost3x_max_dd_pct"]),
            float(item["total_return_pct"]),
        ),
    )
    if int(best["replacement_pass"]) == 1:
        label = f"corr_gate_ablation_replacement_candidate_found:{best['variant']}"
    elif int(best["stress_upgrade"]) == 1:
        label = f"corr_gate_ablation_stress_upgrade_only:{best['variant']}"
    else:
        label = "corr_gate_ablation_no_promotion_keep_stage526_candidate"
    return {
        "stage": "Stage232",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "control_variant": CONTROL_VARIANT,
        "best_candidate_variant": best.get("variant"),
        "replacement_pass": int(best["replacement_pass"]),
        "hard_pass": int(best["hard_pass"]),
        "stress_upgrade": int(best["stress_upgrade"]),
        "return_retention_vs_control_pct": float(best["return_retention_vs_control_pct"]),
        "control_total_return_pct": _safe_float(control["total_return_pct"]),
        "candidate_total_return_pct": float(best["total_return_pct"]),
        "control_max_dd_pct": _safe_float(control["max_dd_pct"]),
        "candidate_max_dd_pct": float(best["max_dd_pct"]),
        "control_ulcer_pct": _safe_float(control["ulcer_pct"]),
        "candidate_ulcer_pct": float(best["ulcer_pct"]),
        "control_3x_max_dd_pct": control_3x_dd,
        "candidate_3x_max_dd_pct": float(best["cost3x_max_dd_pct"]),
        "h63_p05_delta_vs_control": float(best["h63_p05_delta_vs_control"]),
        "h126_p05_delta_vs_control": float(best["h126_p05_delta_vs_control"]),
        "candidate_broker10_max_pct": float(best["broker10_max_pct"]),
        "candidate_days_over_100pct": int(best["days_over_100pct"]),
        "gate_summary": best.get("gate_summary", {}),
        "candidate_results": candidate_results,
    }


def _plot(
    combo_daily: pd.DataFrame,
    cost: pd.DataFrame,
    rolling_delta: pd.DataFrame,
    gate_summary: pd.DataFrame,
    edge: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_nav, ax_dd, ax_hold, ax_edge = axes.flatten()
    color_map = {CONTROL_VARIANT: "#0f766e", CORR_VARIANT: "#dc2626", NO_CORR_VARIANT: "#2563eb"}
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        dates = pd.to_datetime(ordered["date"])
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=dates)
        ax_nav.plot(dates, equity / s516.ACCOUNT_CAPITAL, label=variant, linewidth=1.05, color=color_map.get(variant))
        ax_dd.plot(dates, _drawdown_pct(equity), label=variant, linewidth=0.95, color=color_map.get(variant))
    ax_nav.set_title("NAV: Stage526 corr gate ablation")
    ax_nav.grid(alpha=0.25)
    ax_nav.legend(fontsize=8)
    ax_dd.set_title("Underwater drawdown")
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.grid(alpha=0.25)

    focus = rolling_delta[
        ~rolling_delta["variant"].eq(CONTROL_VARIANT) & rolling_delta["holding_days"].isin([63, 126])
    ].copy()
    if not focus.empty:
        x = np.arange(len(focus))
        ax_hold.bar(
            x,
            focus["p05_delta_vs_control"],
            color=[color_map.get(str(item), "#dc2626") for item in focus["variant"]],
            alpha=0.85,
        )
        ax_hold.axhline(0, color="#111827", linewidth=1)
        ax_hold.set_xticks(x)
        ax_hold.set_xticklabels(
            [f"{str(v).replace('r080_pc25_maxpos4_', '')}\n{h}d" for v, h in zip(focus["variant"], focus["holding_days"])],
            fontsize=7,
        )
    ax_hold.set_title("p05 return delta vs control")
    ax_hold.grid(axis="y", alpha=0.25)

    if not edge.empty:
        for variant, frame in edge.groupby("variant", sort=False):
            ax_edge.plot(
                pd.to_datetime(frame["date"]),
                frame["edge_cum"],
                color=color_map.get(str(variant), "#7c3aed"),
                linewidth=1.0,
                label=str(variant),
            )
        ax_edge.axhline(0, color="#111827", linewidth=1)
        ax_edge.legend(fontsize=7)
    ax_edge.set_title("Cumulative daily PnL edge vs control")
    ax_edge.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    rolling_delta: pd.DataFrame,
    windows: pd.DataFrame,
    gate_summary: pd.DataFrame,
    cost_failure: pd.DataFrame,
    product_attr: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_view = summary.sort_values("variant")
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    hold_view = rolling[rolling["holding_days"].isin([63, 126, 252, 504])].sort_values(["variant", "holding_days"])
    delta_view = rolling_delta[rolling_delta["holding_days"].isin([63, 126])].sort_values(["variant", "holding_days"])
    product_view = product_attr.sort_values(["variant", "net_pnl"], ascending=[True, True]).groupby("variant").head(8)
    lines = [
        "# Stage232 Stage526同向相关性门控强度/关闭反证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：A/C 最小真实引擎验证；固定 Stage526 候选，对继承的同向相关性门控做强度放宽与关闭反证。",
        "- A/B触发判断：触发 A/C。该模块若通过，可能改变当前候选的入场侧风险治理。",
        "- 运行前过拟合判断：否。只测两个机制性反证：`floor0.35 -> 0.50` 和 `disable`，不扫阈值。",
        "- 运行前继续价值判断：是。该变量比简单并发数更接近同质化风险，但也可能误伤同向趋势扩散。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随/CTA框架通常强调跨市场分散、风险预算和相关性管理；但相关性约束容易误伤趋势扩散，因此必须以真实引擎和多窗口验证。",
        "- GitHub 趋势框架多以波动过滤、前月合约执行和多市场组合为工程基础；本阶段不引入外部复杂模型，只验证本仓库已有相关性门控强度。",
        "",
        "## 预声明晋级门槛",
        "",
        "- 正常成本：DD40、broker10 exact <= 100%。",
        "- 2x成本：DD40。",
        "- 相对 control：总收益不少于95%，最大回撤不劣化，Ulcer不劣化。",
        "- 任意启动体验：63日和126日 p05 收益不劣化。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision.get('decision', '')}`。",
        f"- 收益保留 vs control：`{decision.get('return_retention_vs_control_pct', 0.0):.4f}%`。",
        f"- 3x成本最大回撤：control `{decision.get('control_3x_max_dd_pct', 0.0):.4f}%`，candidate `{decision.get('candidate_3x_max_dd_pct', 0.0):.4f}%`。",
        "",
        "## 全周期 1x 成本",
        "",
        _md_table(
            summary_view[
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "longest_underwater_days",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                ]
            ]
        ),
        "",
        "## 门控触发摘要",
        "",
        _md_table(gate_summary),
        "",
        "## 任意启动持有体验",
        "",
        _md_table(
            hold_view[
                [
                    "variant",
                    "holding_days",
                    "min_return_pct",
                    "p05_return_pct",
                    "p10_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ]
        ),
        "",
        "## 3/6个月左尾相对control",
        "",
        _md_table(delta_view),
        "",
        "## 多起点/分段",
        "",
        _md_table(
            windows[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ].sort_values(["variant", "window_name"]),
            max_rows=80,
        ),
        "",
        "## 1x/2x/3x最大回撤窗口",
        "",
        _md_table(cost_failure, max_rows=40),
        "",
        "## 3x失败窗口产品归因",
        "",
        _md_table(
            product_view[
                [
                    "variant",
                    "product_vt_symbol",
                    "net_pnl",
                    "holding_pnl",
                    "trading_pnl",
                    "max_c3_margin",
                    "active_days",
                ]
            ],
            max_rows=32,
        ),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"[stage532] running {spec.variant}", flush=True)
        daily, positions, candidates = _run_variant_with_candidates(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
        if not candidates.empty:
            candidate_frames.append(candidates)

    c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    candidates = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = s517._combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily, specs)
    rolling = s516._rolling_holding(combo_daily)
    rolling_delta = _rolling_delta(rolling)
    windows = s516._window_metrics(combo_daily)
    cost_failure = _cost_failure_windows(combo_daily)
    product_attr = _product_bad_window_attr(product_margin, cost_failure)
    gate_summary = _gate_summary(candidates)
    edge = _edge_daily(combo_daily)
    decision = _decision(summary, cost, rolling_delta, gate_summary)

    _plot(combo_daily, cost, rolling_delta, gate_summary, edge)
    _write_report(summary, cost, rolling, rolling_delta, windows, gate_summary, cost_failure, product_attr, decision)

    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(CANDIDATE_SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    gate_summary.to_csv(GATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost_failure.to_csv(COST_FAILURE_PATH, index=False, encoding="utf-8-sig")
    edge.to_csv(EDGE_DAILY_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(PRODUCT_ATTR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
