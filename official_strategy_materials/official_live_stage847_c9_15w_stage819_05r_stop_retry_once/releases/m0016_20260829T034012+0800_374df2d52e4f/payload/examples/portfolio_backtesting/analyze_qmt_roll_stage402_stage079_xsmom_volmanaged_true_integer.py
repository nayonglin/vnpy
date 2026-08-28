from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
from analyze_qmt_roll_stage346_xsmom_integer_feasibility import (  # noqa: E402
    _build_price_frame,
    _load_signal_daily,
    _safe_float,
)


MODEL_TAG = "stage402_stage079_xsmom_volmanaged_true_integer_v1"
OUTPUT_PREFIX = "qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer"
LINE_ID = "futures_trend_drawdown30_preserve_return"

COMBO_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)
MARGIN_PATH = (
    OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)

FUTURES_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
TARGET_DD_PCT = -30.0
BASELINE_VARIANT = "stage079"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SATELLITE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    mode: str
    executable_ready: bool
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(BASELINE_VARIANT, "Stage079基准", "baseline", True, "50万C3下单+11.5万现金。"),
    VariantSpec(
        "xsmom_vt10_q_momq_round_half_true",
        "真实整数：scale>=0.5时执行xsmom整篮子最低1手",
        "round_half",
        True,
        "把Stage101连续scale按自然四舍五入口径落到整篮子最低1手。",
    ),
    VariantSpec(
        "xsmom_vt10_q_momq_cheapest_budget_true",
        "真实整数：按scale预算选择低保证金xsmom信号子集",
        "cheapest_budget",
        True,
        "把Stage101连续scale转成当日min1保证金预算，并按低保证金优先执行子集。",
    ),
)


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage402", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage402"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_metric(value: Any, default: float = 0.0) -> float:
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
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_combo_daily() -> pd.DataFrame:
    frame = pd.read_csv(COMBO_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["c3_net_pnl", "c3_trade_count", "c3_slippage", "daily_pnl", "slippage_cost", "trade_count"]:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _load_margin() -> pd.DataFrame:
    frame = pd.read_csv(MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["account_balance", "c3_margin", "satellite_margin", "total_margin"]:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _split_products(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split(",") if item]


def _build_stage101_scale(full: pd.DataFrame) -> pd.Series:
    ret = full["daily_pnl"].astype(float) / ACCOUNT_CAPITAL
    vol = (ret.rolling(63, min_periods=63).std() * math.sqrt(252.0)).shift(1)
    base_scale = (0.10 / vol).replace([np.inf, -np.inf], np.nan).clip(lower=0.0, upper=1.0).fillna(0.0)
    own_momentum = (full["daily_pnl"].astype(float).rolling(63, min_periods=63).sum().shift(1) > 0.0).astype(float)
    return pd.Series((base_scale * own_momentum).to_numpy(dtype=float), index=full["date"])


def _desired_contracts(signal_row: Any, price_by_product: dict[str, Any]) -> list[tuple[str, str, int, float]]:
    desired_products: list[tuple[str, int]] = [
        *((product, 1) for product in _split_products(getattr(signal_row, "long_products", None))),
        *((product, -1) for product in _split_products(getattr(signal_row, "short_products", None))),
    ]
    desired: list[tuple[str, str, int, float]] = []
    for product, direction in desired_products:
        price_row = price_by_product.get(product)
        if price_row is None:
            continue
        contract = str(getattr(price_row, "main_contract_vt", ""))
        margin = _safe_float(getattr(price_row, "margin_per_contract", 0.0))
        if contract and margin > 0.0:
            desired.append((contract, product, direction, margin))
    return desired


def _target_lots(mode: str, scale: float, desired: list[tuple[str, str, int, float]]) -> tuple[dict[str, int], float]:
    required_min1_margin = float(sum(item[3] for item in desired))
    if not desired or scale <= 0.0:
        return {}, required_min1_margin
    if mode == "round_half":
        if scale >= 0.5:
            return {contract: direction for contract, _product, direction, _margin in desired}, required_min1_margin
        return {}, required_min1_margin
    if mode == "cheapest_budget":
        budget = scale * required_min1_margin
        used = 0.0
        targets: dict[str, int] = {}
        for contract, _product, direction, margin in sorted(desired, key=lambda item: item[3]):
            if used + margin <= budget + 1e-9:
                targets[contract] = direction
                used += margin
        return targets, required_min1_margin
    return {}, required_min1_margin


def _simulate_satellite(
    window_name: str,
    mode: str,
    window_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
) -> pd.DataFrame:
    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "window_name",
                "satellite_daily_pnl",
                "satellite_slippage_cost",
                "satellite_margin",
                "satellite_turnover_contracts",
                "held_contract_count",
                "desired_signal_count",
                "required_min1_margin",
                "stage101_scale",
            ]
        )
    price_by_date_product = {
        (row.date, row.product_vt_symbol): row
        for row in price_frame[price_frame["date"].between(start, end)].itertuples(index=False)
    }
    contract_to_product = (
        price_frame[price_frame["date"].between(start, end)]
        .drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    prev_positions: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for signal_row in window_signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        scale = float(scale_by_date.get(date, 0.0))
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        desired = _desired_contracts(signal_row, price_by_product)
        targets, required_min1_margin = _target_lots(mode, scale, desired)

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * _safe_float(getattr(price_row, "prev_main_close", 0.0)) * _safe_float(
                getattr(price_row, "size", 1.0)
            ) * _safe_float(getattr(price_row, "product_return", 0.0))
            margin += abs(lots) * _safe_float(getattr(price_row, "margin_per_contract", 0.0))

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                slippage_cost += delta * _safe_float(getattr(price_row, "slippage", 0.0)) * _safe_float(
                    getattr(price_row, "size", 1.0)
                )
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "satellite_daily_pnl": pnl - slippage_cost,
                "satellite_slippage_cost": slippage_cost,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "held_contract_count": len(targets),
                "desired_signal_count": len(desired),
                "required_min1_margin": required_min1_margin,
                "stage101_scale": scale,
            }
        )
        prev_positions = targets
    return pd.DataFrame(rows)


def _combine_daily(window_frame: pd.DataFrame, satellite: pd.DataFrame, variant: str, slippage_multiplier: float = 1.0) -> pd.DataFrame:
    merged = window_frame[["date", "window_name", "c3_net_pnl", "c3_trade_count", "c3_slippage"]].copy()
    sat_columns = [
        "date",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "stage101_scale",
    ]
    if satellite.empty:
        satellite = pd.DataFrame(columns=sat_columns)
    for col in sat_columns:
        if col not in satellite.columns:
            satellite[col] = 0.0
    merged = merged.merge(
        satellite[sat_columns],
        on="date",
        how="left",
    )
    for col in [
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "stage101_scale",
    ]:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").fillna(0.0)
    stressed_pnl = (
        merged["c3_net_pnl"]
        + merged["satellite_daily_pnl"]
        - (slippage_multiplier - 1.0) * (merged["c3_slippage"] + merged["satellite_slippage_cost"])
    )
    merged["equity"] = FUTURES_CAPITAL + stressed_pnl.cumsum() + STAGE079_CASH
    merged["variant"] = variant
    merged["trade_count"] = merged["c3_trade_count"] + merged["satellite_turnover_contracts"]
    merged["combo_slippage"] = merged["c3_slippage"] + merged["satellite_slippage_cost"]
    return merged


def _calendarize(equity: pd.Series) -> pd.Series:
    equity = equity.sort_index().dropna()
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="true_integer_xsmom_overlay" if spec.variant != BASELINE_VARIANT else "baseline",
        eligible_for_promotion=spec.executable_ready,
        note=spec.note,
    )


def _objective_improved_counts(horizon: pd.DataFrame) -> pd.DataFrame:
    larger_is_better = {"return_p05_pct", "return_median_pct", "positive_return_rate", "max_dd_worst_pct"}
    smaller_is_better = {
        "annualized_below_5pct_rate",
        "dd20_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    }
    baseline = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    for _, row in horizon.iterrows():
        horizon_days = int(row["horizon_days"])
        base = baseline.loc[horizon_days]
        improved = 0
        metrics: list[str] = []
        for metric in sorted(larger_is_better):
            if _safe_metric(row[metric]) > _safe_metric(base[metric]):
                improved += 1
                metrics.append(metric)
        for metric in sorted(smaller_is_better):
            if _safe_metric(row[metric]) < _safe_metric(base[metric]):
                improved += 1
                metrics.append(metric)
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
                "objective_improved_8_metrics": ",".join(metrics),
            }
        )
    return pd.DataFrame(rows)


def _cost_stress(full_frame: pd.DataFrame, satellite_by_variant: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in VARIANTS:
            satellite = satellite_by_variant.get(spec.variant, pd.DataFrame(columns=["date"]))
            daily = _combine_daily(full_frame, satellite, spec.variant, multiplier)
            equity = _calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if spec.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = max_dd
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _fresh_start(
    combo: pd.DataFrame,
    margin: pd.DataFrame,
    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        m = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            satellite = satellite_by_window_variant.get((window_name, spec.variant), pd.DataFrame(columns=["date"]))
            daily = _combine_daily(frame, satellite, spec.variant, 1.0)
            equity = pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"])
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if m.empty:
                max_margin_to_equity = 0.0
                reject_days = 0
            else:
                sat_margin = satellite.set_index("date")["satellite_margin"] if not satellite.empty else pd.Series(dtype=float)
                total_margin = m["c3_margin"].to_numpy(dtype=float) + sat_margin.reindex(m["date"]).fillna(0.0).to_numpy(dtype=float)
                equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
                margin_equity = total_margin / equity_on_margin_dates * 100.0
                max_margin_to_equity = float(np.nanmax(margin_equity)) if len(margin_equity) else 0.0
                reject_days = int(np.sum(margin_equity > 100.0))
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "satellite_slippage": float(satellite["satellite_slippage_cost"].sum()) if not satellite.empty else 0.0,
                    "satellite_turnover": float(satellite["satellite_turnover_contracts"].sum()) if not satellite.empty else 0.0,
                    "max_satellite_margin": float(satellite["satellite_margin"].max()) if not satellite.empty else 0.0,
                    "max_margin_to_equity_pct": max_margin_to_equity,
                    "reject_days": reject_days,
                }
            )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    objective_improved = _objective_improved_counts(horizon)
    improved_p = objective_improved.pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count"
    ).reset_index()
    improved_p.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    fresh_failures = (
        fresh[fresh["dd30_pass"].eq(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "total_return_not_lower": _safe_metric(row["total_return_pct"]) >= _safe_metric(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_metric(row["max_dd_pct"]) >= _safe_metric(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_metric(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_metric(row["sharpe"]) >= _safe_metric(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_metric(row["ulcer_pct"]) <= _safe_metric(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_metric(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_metric(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_metric(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_metric(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_metric(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "metric_hard_pass": int(all(checks.values())),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "failed_metric_checks": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        improved_p, on=["variant", "label"], how="left"
    )
    result["score90_improve_ge10pct"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= 110.0).astype(int)
    result["objective_improved_5of8_each"] = (
        (result["objective_improved_8_count_90d"] >= 5) & (result["objective_improved_8_count_180d"] >= 5)
    ).astype(int)
    result["target_pass_3m6m"] = (
        result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["objective_improved_5of8_each"].eq(1)
    ).astype(int)
    result["promotion_pass"] = (result["metric_hard_pass"].eq(1) & result["target_pass_3m6m"].eq(1)).astype(int)
    return result.sort_values(["promotion_pass", "short_holding_score"], ascending=[False, False])


def _plot(daily: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage402] skip chart: {exc}", flush=True)
        return
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in daily.groupby("variant"):
        frame = frame.sort_values("date")
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        nav = equity / ACCOUNT_CAPITAL
        axes[0].plot(nav.index, nav, label=variant, linewidth=1.15)
        axes[1].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=1.05)
    axes[0].set_title("Stage102/402 true integer xsmom carrier NAV")
    axes[0].set_ylabel("NAV")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, fresh: pd.DataFrame, cost: pd.DataFrame, gate: pd.DataFrame, decision: dict[str, Any]) -> None:
    report = [
        "# Stage102 Stage079 xsmom波动管理真实整数手验证",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：真实整数手映射验证；固定Stage101 `xsmom_vt10_q_momq`，不调波动目标和窗口。",
        "- A/B/C：A=Stage079；C1=scale>=0.5时执行整篮子最低1手；C2=按scale预算执行低保证金子集。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期核心指标",
        "",
        _md_table(summary[["variant", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "rolling252_dd30_breach_rate", "rolling504_dd30_breach_rate", "annual_cold_start_dd30_pass_rate", "quarter_cold_start_dd30_pass_rate"]]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[["variant", "horizon_days", "return_p05_pct", "return_median_pct", "positive_return_rate", "annualized_below_5pct_rate", "max_dd_worst_pct", "dd20_breach_rate", "dd30_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"]]),
        "",
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## 多起点冷启动",
        "",
        _md_table(fresh[["window_name", "variant", "total_return_pct", "max_dd_pct", "dd30_pass", "satellite_turnover", "max_satellite_margin", "max_margin_to_equity_pct", "reject_days"]]),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 晋级闸门",
        "",
        _md_table(gate[["variant", "metric_hard_pass", "target_pass_3m6m", "promotion_pass", "score_90d", "score_180d", "objective_improved_8_count_90d", "objective_improved_8_count_180d", "fresh_start_failed_windows", "failed_metric_checks"]]),
        "",
        "## 反过拟合说明",
        "",
        "- 固定Stage101规则，只做两个必要的整数手映射；没有继续扫描target_vol、窗口或阈值。",
        "- `round_half` 是最小一手场景下的自然四舍五入；`cheapest_budget` 是保证金预算落地，两者都是可解释执行映射。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = _load_combo_daily()
    margin = _load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = _build_stage101_scale(full)
    price_frame = _build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    signals = _load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    satellite_full_by_variant: dict[str, pd.DataFrame] = {BASELINE_VARIANT: pd.DataFrame(columns=["date"])}
    daily_parts: list[pd.DataFrame] = []
    candidates: list[Any] = []

    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        satellite_by_window_variant[(window_name, BASELINE_VARIANT)] = pd.DataFrame(columns=["date"])
        for spec in VARIANTS:
            if spec.variant == BASELINE_VARIANT:
                continue
            sat = _simulate_satellite(window_name, spec.mode, frame, price_frame, signals, scale_by_date)
            satellite_by_window_variant[(window_name, spec.variant)] = sat
            if window_name == "start_2020":
                satellite_full_by_variant[spec.variant] = sat

    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    for spec in VARIANTS:
        sat = satellite_full_by_variant.get(spec.variant, pd.DataFrame(columns=["date"]))
        daily = _combine_daily(full_frame, sat, spec.variant, 1.0)
        daily_parts.append(daily)
        equity = _calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
        candidates.append(_candidate(spec, equity))

    daily_all = pd.concat(daily_parts, ignore_index=True)
    satellite_all = pd.concat(
        [
            frame.assign(variant=variant)
            for (window_name, variant), frame in satellite_by_window_variant.items()
            if variant != BASELINE_VARIANT and not frame.empty
        ],
        ignore_index=True,
    )
    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s087._score_horizons(horizon)
    fresh = _fresh_start(combo, margin, satellite_by_window_variant)
    cost = _cost_stress(full_frame, satellite_full_by_variant)
    gate = _gate(summary, horizon, score, cost, fresh)

    promoted = gate[gate["promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    decision = {
        "stage": "Stage102",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promotion_candidate" if len(promoted) else "no_promotion",
        "promoted_variants": promoted["variant"].tolist(),
        "best_by_short_holding_score": gate.iloc[0]["variant"] if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "真实整数手映射验证完成；只有promotion_pass=1的版本才可作为Stage079正式优化候选。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_all.to_csv(SATELLITE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily_all)
    _write_report(summary, horizon, score, fresh, cost, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
