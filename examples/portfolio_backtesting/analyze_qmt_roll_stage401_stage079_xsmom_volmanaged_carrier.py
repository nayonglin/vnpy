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

MODEL_TAG = "stage401_stage079_xsmom_volmanaged_carrier_v1"
OUTPUT_PREFIX = "qmt_roll_stage401_stage079_xsmom_volmanaged_carrier"
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
SCALE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scale_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    target_vol: float
    vol_lookback_days: int
    momentum_lookback_days: int | None
    executable_ready: bool
    candidate_class: str
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        BASELINE_VARIANT,
        "Stage079基准",
        0.0,
        0,
        None,
        True,
        "baseline",
        "50万C3下单+11.5万现金。",
    ),
    VariantSpec(
        "xsmom_vt10_q",
        "诊断：xsmom 10%年化波动目标，63日波动",
        0.10,
        63,
        None,
        False,
        "vol_target_xsmom_diagnostic",
        "固定10%年化波动目标；不加自身动量门控，用于机制拆解。",
    ),
    VariantSpec(
        "xsmom_vt10_q_momq",
        "诊断候选：xsmom 10%年化波动目标 + 63日自身动量为正",
        0.10,
        63,
        63,
        False,
        "vol_target_xsmom_with_own_momentum_diagnostic",
        "固定季度波动和季度自身动量；只用历史日PnL，不看同日、不看未来。",
    ),
    VariantSpec(
        "xsmom_vt10_h_momq",
        "稳健性对照：xsmom 10%年化波动目标，126日波动 + 63日自身动量为正",
        0.10,
        126,
        63,
        False,
        "vol_target_xsmom_with_own_momentum_diagnostic",
        "半年波动估计 + 季度自身动量，用于判断季度波动是否偶然。",
    ),
)


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage401", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage401"] = module
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


def _build_scale_map(full: pd.DataFrame, spec: VariantSpec) -> pd.Series:
    if spec.variant == BASELINE_VARIANT:
        return pd.Series(0.0, index=full["date"])
    ret = full["daily_pnl"].astype(float) / ACCOUNT_CAPITAL
    vol = ret.rolling(spec.vol_lookback_days, min_periods=spec.vol_lookback_days).std() * math.sqrt(252.0)
    scale = (spec.target_vol / vol.shift(1)).replace([np.inf, -np.inf], np.nan).clip(lower=0.0, upper=1.0).fillna(0.0)
    if spec.momentum_lookback_days is not None:
        own_momentum = (
            full["daily_pnl"].astype(float).rolling(spec.momentum_lookback_days, min_periods=spec.momentum_lookback_days).sum().shift(1)
            > 0.0
        )
        scale = scale * own_momentum.fillna(False).astype(float)
    return pd.Series(scale.to_numpy(dtype=float), index=full["date"])


def _equity_from_frame(
    frame: pd.DataFrame,
    scale_by_date: pd.Series,
    slippage_multiplier: float = 1.0,
) -> pd.Series:
    scale = frame["date"].map(scale_by_date).fillna(0.0).to_numpy(dtype=float)
    pnl = frame["c3_net_pnl"].to_numpy(dtype=float) + scale * frame["daily_pnl"].to_numpy(dtype=float)
    slippage = frame["c3_slippage"].to_numpy(dtype=float) + scale * frame["slippage_cost"].to_numpy(dtype=float)
    stressed = pnl - (float(slippage_multiplier) - 1.0) * slippage
    equity = FUTURES_CAPITAL + np.cumsum(stressed) + STAGE079_CASH
    return pd.Series(equity, index=frame["date"])


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
        candidate_class=spec.candidate_class,
        eligible_for_promotion=spec.executable_ready,
        note=spec.note,
    )


def _scale_stats(full: pd.DataFrame, scale_maps: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        scale = full["date"].map(scale_maps[spec.variant]).fillna(0.0).to_numpy(dtype=float)
        rows.append(
            {
                "variant": spec.variant,
                "target_vol": spec.target_vol,
                "vol_lookback_days": spec.vol_lookback_days,
                "momentum_lookback_days": spec.momentum_lookback_days or 0,
                "mean_scale": float(np.mean(scale)),
                "median_scale": float(np.median(scale)),
                "p90_scale": float(np.quantile(scale, 0.90)),
                "active_day_rate": float(np.mean(scale > 1e-12)),
                "ytd_2026_mean_scale": float(np.mean(scale[full["date"].ge(pd.Timestamp("2026-01-01")).to_numpy()]))
                if full["date"].ge(pd.Timestamp("2026-01-01")).any()
                else 0.0,
                "diagnostic_total_slippage": float(full["c3_slippage"].sum() + np.sum(scale * full["slippage_cost"].to_numpy(dtype=float))),
                "diagnostic_weighted_sat_trade_count": float(np.sum(scale * full["trade_count"].to_numpy(dtype=float))),
                "c3_trade_count": float(full["c3_trade_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _cost_stress(full: pd.DataFrame, scale_maps: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in VARIANTS:
            equity = _calendarize(_equity_from_frame(full, scale_maps[spec.variant], multiplier))
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


def _fresh_start(combo: pd.DataFrame, margin: pd.DataFrame, scale_maps: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        m = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            scale_by_date = scale_maps[spec.variant]
            scale = frame["date"].map(scale_by_date).fillna(0.0).to_numpy(dtype=float)
            equity = _equity_from_frame(frame, scale_by_date, 1.0)
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if m.empty:
                max_margin_to_equity = 0.0
                reject_days = 0
            else:
                margin_scale = m["date"].map(scale_by_date).fillna(0.0).to_numpy(dtype=float)
                total_margin = m["c3_margin"].to_numpy(dtype=float) + margin_scale * m["satellite_margin"].to_numpy(dtype=float)
                equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
                margin_equity = total_margin / equity_on_margin_dates * 100.0
                max_margin_to_equity = float(np.nanmax(margin_equity)) if len(margin_equity) else 0.0
                reject_days = int(np.sum(margin_equity > 100.0))
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "start_date": str(frame["date"].min().date()),
                    "end_date": str(frame["date"].max().date()),
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "mean_scale": float(np.mean(scale)),
                    "max_margin_to_equity_pct": max_margin_to_equity,
                    "reject_days": reject_days,
                }
            )
    return pd.DataFrame(rows)


def _objective_improved_counts(horizon: pd.DataFrame) -> pd.DataFrame:
    larger_is_better = {
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "max_dd_worst_pct",
    }
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
        improved_metrics: list[str] = []
        for metric in sorted(larger_is_better):
            if _safe_float(row[metric]) > _safe_float(base[metric]):
                improved += 1
                improved_metrics.append(metric)
        for metric in sorted(smaller_is_better):
            if _safe_float(row[metric]) < _safe_float(base[metric]):
                improved += 1
                improved_metrics.append(metric)
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
                "objective_improved_8_metrics": ",".join(improved_metrics),
            }
        )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    objective_improved = _objective_improved_counts(horizon)
    improved_p = objective_improved.pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count"
    ).reset_index()
    improved_p.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
    improved_metrics_p = objective_improved.pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_metrics"
    ).reset_index()
    improved_metrics_p.columns = ["variant", "label", "objective_improved_8_metrics_90d", "objective_improved_8_metrics_180d"]
    fresh_failures = (
        fresh[fresh["dd30_pass"].eq(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    executable_by_variant = {spec.variant: spec.executable_ready for spec in VARIANTS}
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "executable_ready": int(executable_by_variant.get(str(row["variant"]), False)),
                **{name: int(flag) for name, flag in checks.items()},
                "metric_hard_pass": int(all(checks.values())),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "failed_metric_checks": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    result = (
        pd.DataFrame(rows)
        .merge(score_one, on=["variant", "label"], how="left")
        .merge(improved_p, on=["variant", "label"], how="left")
        .merge(improved_metrics_p, on=["variant", "label"], how="left")
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
    result["diagnostic_next_validation_pass"] = (
        result["metric_hard_pass"].eq(1) & result["target_pass_3m6m"].eq(1)
    ).astype(int)
    result["formal_promotion_pass"] = (
        result["diagnostic_next_validation_pass"].eq(1) & result["executable_ready"].eq(1)
    ).astype(int)
    return result.sort_values(["formal_promotion_pass", "diagnostic_next_validation_pass", "short_holding_score"], ascending=[False, False, False])


def _plot(daily: pd.DataFrame, scale_stats: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage401] skip chart: {exc}", flush=True)
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    selected = ["stage079", "xsmom_vt10_q", "xsmom_vt10_q_momq", "xsmom_vt10_h_momq"]
    for variant in selected:
        frame = daily[daily["variant"].eq(variant)].sort_values("date")
        if frame.empty:
            continue
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        nav = equity / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.2)
        dd = nav / nav.cummax() - 1.0
        axes[1, 0].plot(dd.index, dd * 100.0, label=variant, linewidth=1.1)

    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].set_ylabel("NAV")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].set_title("Full-period drawdown")
    axes[1, 0].set_ylabel("Drawdown %")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=8)

    best = daily[daily["variant"].eq("xsmom_vt10_q_momq")].sort_values("date")
    if not best.empty:
        axes[0, 1].plot(pd.to_datetime(best["date"]), best["xsmom_scale"], color="tab:green", linewidth=1.0)
    axes[0, 1].set_title("xsmom_vt10_q_momq scale")
    axes[0, 1].set_ylabel("Scale")

    scale_view = scale_stats[scale_stats["variant"].ne(BASELINE_VARIANT)]
    axes[1, 1].bar(scale_view["variant"], scale_view["mean_scale"], color=["tab:blue", "tab:green", "tab:orange"])
    axes[1, 1].set_title("Mean diagnostic xsmom scale")
    axes[1, 1].tick_params(axis="x", rotation=20)

    fig.suptitle("Stage101/401 Stage079 xsmom volatility-managed carrier", y=0.99)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    fresh: pd.DataFrame,
    gate: pd.DataFrame,
    scale_stats: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage101 Stage079 xsmom波动管理承载诊断",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读诊断；复用Stage352 xsmom overlay日PnL、滑点和保证金，以历史波动和自身动量决定承载强度。",
        "- 候选假设：xsmom源有效，但裸承载冷启动不稳；用常见波动目标和自身动量门控，可能降低坏时段暴露且保留右尾。",
        "- A/B/C：A=Stage079；B=xsmom波动管理源独立诊断不单列资金账户；C=Stage079账户口径 + xsmom波动管理承载。",
        "- 注意：本阶段仍不是逐笔真实手数重建，不能直接实盘晋级；若通过，只能进入下一阶段真实引擎验证。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- `Time series momentum and volatility scaling` 指出期货时间序列动量表现与波动缩放关系很强。",
        "- Moreira/Muir 的波动管理框架支持高波动时减风险，但后续实时表现研究提醒：波动管理不应被自动视为稳健alpha。",
        "- 因此本阶段采用粗、常见、点时化规则：10%年化波动目标、63/126交易日波动估计、63日自身动量为正；不继续扫目标波动或窗口小数。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期核心指标",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                    "annual_cold_start_dd30_pass_rate",
                    "quarter_cold_start_dd30_pass_rate",
                ]
            ]
        ),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(
            horizon[
                [
                    "variant",
                    "horizon_days",
                    "return_p05_pct",
                    "return_median_pct",
                    "positive_return_rate",
                    "annualized_below_5pct_rate",
                    "max_dd_worst_pct",
                    "dd20_breach_rate",
                    "dd30_breach_rate",
                    "ulcer_p95_pct",
                    "longest_underwater_p95_days",
                ]
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 体验评分",
        "",
        "- 注：下表 `improved_metric_count` 是6个加权评分组件的改善数；正式晋级闸门使用后文用户目标8项改善计数。",
        "",
        _md_table(
            score[
                [
                    "variant",
                    "horizon_days",
                    "experience_score",
                    "improved_metric_count",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                ]
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 冷启动窗口",
        "",
        _md_table(
            fresh[["window_name", "variant", "total_return_pct", "max_dd_pct", "dd30_pass", "mean_scale", "max_margin_to_equity_pct", "reject_days"]]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ]
        ),
        "",
        "## 承载强度统计",
        "",
        _md_table(scale_stats),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass",
                    "target_pass_3m6m",
                    "diagnostic_next_validation_pass",
                    "executable_ready",
                    "formal_promotion_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "objective_improved_8_metrics_90d",
                    "objective_improved_8_metrics_180d",
                    "fresh_start_failed_windows",
                    "failed_metric_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 候选规则只使用历史xsmom自身PnL的滚动波动和滚动收益，且全部shift一日，避免同日/未来信息。",
        "- 10%年化波动目标与63/126日窗口属于常见风险预算尺度；本阶段不继续调8%、12%、15%或42/84日窗口。",
        "- 通过项只能晋级真实引擎验证，不能直接视为最终策略，因为日PnL层缩放尚未处理整数手、真实成交、开平仓恢复和保证金离散。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = _load_combo_daily()
    margin = _load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    if full.empty:
        raise RuntimeError("missing start_2020 in Stage352 combo daily")

    scale_maps = {spec.variant: _build_scale_map(full, spec) for spec in VARIANTS}
    scale_stats = _scale_stats(full, scale_maps)

    candidates: list[Any] = []
    daily_parts: list[pd.DataFrame] = []
    for spec in VARIANTS:
        equity = _calendarize(_equity_from_frame(full, scale_maps[spec.variant], 1.0))
        candidates.append(_candidate(spec, equity))
        raw_scale = full["date"].map(scale_maps[spec.variant]).fillna(0.0)
        raw_daily = pd.DataFrame(
            {
                "date": full["date"],
                "variant": spec.variant,
                "label": spec.label,
                "xsmom_scale": raw_scale.to_numpy(dtype=float),
                "equity": _equity_from_frame(full, scale_maps[spec.variant], 1.0).to_numpy(dtype=float),
            }
        )
        daily_parts.append(raw_daily)

    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s087._score_horizons(horizon)
    fresh = _fresh_start(combo, margin, scale_maps)
    cost = _cost_stress(full, scale_maps)
    gate = _gate(summary, horizon, score, cost, fresh)
    daily = pd.concat(daily_parts, ignore_index=True)

    next_validation = gate[gate["diagnostic_next_validation_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    formal = gate[gate["formal_promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    decision = {
        "stage": "Stage101",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "formal_promotion_candidate"
        if len(formal)
        else ("diagnostic_next_validation_candidate" if len(next_validation) else "no_promotion"),
        "formal_promoted_variants": formal["variant"].tolist(),
        "next_validation_variants": next_validation["variant"].tolist(),
        "best_by_short_holding_score": gate.iloc[0]["variant"] if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "xsmom_vt10_q_momq通过指标层硬约束、冷启动和3/6个月体验，但仍是日PnL层诊断，值得晋级真实引擎验证，不能直接替代Stage079。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    scale_stats.to_csv(SCALE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily, scale_stats)
    _write_report(summary, horizon, score, cost, fresh, gate, scale_stats, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
