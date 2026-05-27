from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage365_smoothness_frontier_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage365_smoothness_frontier_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TARGET_MAX_DD_PCT = -30.0
STRICT_RETURN_RETENTION_PCT = 80.0
RESEARCH_RETURN_RETENTION_PCT = 65.0
TRADING_DAYS_PER_YEAR = 252.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_windows_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Candidate:
    variant: str
    label: str
    category: str
    source_stage: str
    start_capital: float
    notes: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _load_csv(name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _prepare_curve(
    frame: pd.DataFrame,
    balance_col: str,
    start_capital: float,
    candidate: Candidate,
    date_col: str = "date",
) -> pd.DataFrame:
    curve = frame[[date_col, balance_col]].copy()
    curve.columns = ["date", "balance"]
    curve["date"] = pd.to_datetime(curve["date"]).dt.normalize()
    curve = curve.dropna(subset=["date", "balance"]).sort_values("date")
    curve["balance"] = pd.to_numeric(curve["balance"], errors="coerce")
    curve = curve.dropna(subset=["balance"])
    if curve.empty:
        raise ValueError(f"empty curve: {candidate.variant}")

    first_date = curve["date"].iloc[0] - pd.Timedelta(days=1)
    start_row = pd.DataFrame([{"date": first_date, "balance": float(start_capital)}])
    curve = pd.concat([start_row, curve], ignore_index=True)
    curve["variant"] = candidate.variant
    curve["label"] = candidate.label
    curve["category"] = candidate.category
    curve["source_stage"] = candidate.source_stage
    curve["start_capital"] = float(start_capital)
    curve["nav"] = curve["balance"] / float(start_capital)
    return curve


def _load_official78() -> pd.DataFrame:
    candidate = Candidate(
        variant="A_official78_1_50w",
        label="正式78-1 50万",
        category="formal_baseline",
        source_stage="official_stage78_1",
        start_capital=500_000.0,
        notes="正式78-1原始权益曲线，用于回答是否比78-1更平滑。",
    )
    df = _load_csv("qmt_roll_official_stage78_1_daily_equity.csv")
    return _prepare_curve(df, "balance", candidate.start_capital, candidate)


def _load_c3_baseline() -> pd.DataFrame:
    candidate = Candidate(
        variant="B_c3_current_50w",
        label="C3当前研究基准 50万",
        category="research_baseline",
        source_stage="stage336",
        start_capital=500_000.0,
        notes="C_pressure040叠加供需强逆风后的当前研究基准。",
    )
    df = _load_csv("qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv")
    sub = df[(df["profile"].eq("c3_active100_cash0")) & (df["window_name"].eq("start_2020"))].copy()
    return _prepare_curve(sub, "balance", candidate.start_capital, candidate)


def _load_c3_cash_deployment() -> pd.DataFrame:
    candidate = Candidate(
        variant="D_c3_50w_plus_115k_external_cash",
        label="C3 50万下单 + 11.5万外部现金",
        category="deployment_boundary",
        source_stage="stage055",
        start_capital=615_000.0,
        notes="不改交易路径，只在账户层增加不参与下单现金。",
    )
    df = _load_csv("qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv")
    sub = df[(df["profile"].eq("c3_active100_cash0")) & (df["window_name"].eq("start_2020"))].copy()
    sub["deployment_balance"] = pd.to_numeric(sub["balance"], errors="coerce") + 115_000.0
    return _prepare_curve(sub, "deployment_balance", candidate.start_capital, candidate)


def _load_variant_curve(
    file_name: str,
    variant: str,
    label: str,
    category: str,
    source_stage: str,
    start_capital: float = 500_000.0,
    notes: str = "",
) -> pd.DataFrame:
    candidate = Candidate(variant=variant, label=label, category=category, source_stage=source_stage, start_capital=start_capital, notes=notes)
    df = _load_csv(file_name)
    sub = df[df["variant"].eq(variant)].copy()
    return _prepare_curve(sub, "balance", start_capital, candidate)


def _load_xsmom_overlay() -> pd.DataFrame:
    candidate = Candidate(
        variant="R_xsmom_overlay_3w_cash",
        label="C3原路径 + xsmom overlay + 3万现金",
        category="real_engine_failed_candidate",
        source_stage="stage352",
        start_capital=530_000.0,
        notes="全周期正常成本好看，但多起点和滑点压力已反证。",
    )
    df = _load_csv("qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv")
    sub = df[df["window_name"].eq("start_2020")].copy()
    return _prepare_curve(sub, "account_balance", candidate.start_capital, candidate)


def _load_time_scale_blend(blend_variant: str, weights: dict[str, float], label: str) -> pd.DataFrame:
    candidate = Candidate(
        variant=blend_variant,
        label=label,
        category="netvalue_failed_candidate",
        source_stage="stage356",
        start_capital=500_000.0,
        notes="同源趋势周期净值层组合，多窗口已反证，仅纳入平滑度对照。",
    )
    df = _load_csv("qmt_roll_stage356_c3_time_scale_diversification_scout_curves_stage356_c3_time_scale_diversification_scout_v1.csv")
    sub = df[df["window_name"].eq("start_2020")].copy()
    pivot = sub.pivot_table(index="date", columns="variant", values="normalized_nav", aggfunc="last").sort_index()
    missing = [name for name in weights if name not in pivot.columns]
    if missing:
        raise ValueError(f"missing time scale legs: {missing}")
    total_weight = sum(weights.values())
    nav = sum(pivot[name].ffill().fillna(1.0) * (weight / total_weight) for name, weight in weights.items())
    out = pd.DataFrame({"date": pd.to_datetime(nav.index), "balance": nav.to_numpy(dtype=float) * candidate.start_capital})
    return _prepare_curve(out, "balance", candidate.start_capital, candidate)


def _all_curves() -> pd.DataFrame:
    frames: list[pd.DataFrame] = [
        _load_official78(),
        _load_c3_baseline(),
        _load_c3_cash_deployment(),
        _load_variant_curve(
            "qmt_roll_stage345_cross_sectional_momentum_satellite_combo_daily_stage345_cross_sectional_momentum_satellite_v1.csv",
            "c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps",
            "C3 92.5% + xsmom 7.5%",
            "netvalue_untradable_candidate",
            "stage345",
            notes="净值层最接近保收益候选；Stage046显示3.75万期货腿不可直接承载。",
        ),
        _load_variant_curve(
            "qmt_roll_stage345_cross_sectional_momentum_satellite_combo_daily_stage345_cross_sectional_momentum_satellite_v1.csv",
            "c3_95_xsmom_mom_6m_skip1m_5_cost20bps",
            "C3 95% + xsmom 6m 5%",
            "netvalue_untradable_candidate",
            "stage345",
            notes="净值层动量卫星对照。",
        ),
        _load_xsmom_overlay(),
        _load_variant_curve(
            "qmt_roll_stage364_seasonality_satellite_screen_combo_daily_stage364_seasonality_satellite_screen_v1.csv",
            "C_c3_90_seasonality_10_cost20bps",
            "C3 90% + 月度季节性 10%",
            "netvalue_failed_candidate",
            "stage364",
            notes="季节性独立腿为负收益，组合主要靠稀释降回撤。",
        ),
        _load_variant_curve(
            "qmt_roll_stage364_seasonality_satellite_screen_combo_daily_stage364_seasonality_satellite_screen_v1.csv",
            "C_c3_80_seasonality_20_cost20bps",
            "C3 80% + 月度季节性 20%",
            "netvalue_failed_candidate",
            "stage364",
            notes="更强稀释口径，用于检查平滑收益牺牲边界。",
        ),
        _load_variant_curve(
            "qmt_roll_stage343_carry_satellite_screen_combo_daily_stage343_carry_satellite_screen_v1.csv",
            "c3_90_carry_10_cost20bps",
            "C3 90% + Carry 10%",
            "netvalue_failed_candidate",
            "stage343",
            notes="Carry独立腿已反证，纳入对照。",
        ),
        _load_time_scale_blend(
            "T_timescale_base80_slow20",
            {"C3_base_5_10_20_40": 0.80, "C3_slow_10_20_40_80": 0.20},
            "C3 80% + 慢周期 20%",
        ),
        _load_time_scale_blend(
            "T_timescale_base80_fast20",
            {"C3_base_5_10_20_40": 0.80, "C3_fast_3_6_12_24": 0.20},
            "C3 80% + 快周期 20%",
        ),
    ]
    return pd.concat(frames, ignore_index=True)


def _max_streak(mask: np.ndarray) -> int:
    best = 0
    current = 0
    for flag in mask:
        if bool(flag):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _curve_metrics(group: pd.DataFrame) -> dict[str, Any]:
    group = group.sort_values("date").copy()
    balance = group["balance"].to_numpy(dtype=float)
    dates = pd.to_datetime(group["date"])
    start_capital = float(group["start_capital"].iloc[0])
    high = np.maximum.accumulate(balance)
    dd = np.divide(balance - high, high, out=np.zeros_like(balance), where=high != 0.0) * 100.0
    returns = pd.Series(balance).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0
    total_return = (float(balance[-1]) / start_capital - 1.0) * 100.0
    years = max(1e-9, (dates.iloc[-1] - dates.iloc[0]).days / 365.25)
    cagr = ((float(balance[-1]) / start_capital) ** (1.0 / years) - 1.0) * 100.0 if balance[-1] > 0 else -100.0
    max_dd = float(dd.min())
    ulcer_index = float(np.sqrt(np.mean(np.square(np.minimum(dd, 0.0)))))
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else np.nan

    below_high = balance < (high - 1e-9)
    longest_underwater = _max_streak(below_high)

    last_high_index = 0
    longest_days_without_new_high = 0
    for idx, is_new_high in enumerate(balance >= (high - 1e-9)):
        if is_new_high and balance[idx] >= high[idx] - 1e-9:
            last_high_index = idx
        longest_days_without_new_high = max(longest_days_without_new_high, idx - last_high_index)

    series = pd.Series(balance, index=dates)
    rolling_252 = series.pct_change(252) * 100.0
    rolling_504 = series.pct_change(504) * 100.0
    rolling_756 = series.pct_change(756) * 100.0
    return {
        "variant": group["variant"].iloc[0],
        "label": group["label"].iloc[0],
        "category": group["category"].iloc[0],
        "source_stage": group["source_stage"].iloc[0],
        "start_date": dates.iloc[0].date().isoformat(),
        "end_date": dates.iloc[-1].date().isoformat(),
        "start_capital": start_capital,
        "end_balance": float(balance[-1]),
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "max_dd_pct": max_dd,
        "ulcer_index_pct": ulcer_index,
        "calmar": calmar,
        "sharpe": sharpe,
        "longest_underwater_trading_days": longest_underwater,
        "longest_days_without_new_high": int(longest_days_without_new_high),
        "worst_252d_return_pct": float(rolling_252.min(skipna=True)),
        "worst_504d_return_pct": float(rolling_504.min(skipna=True)),
        "worst_756d_return_pct": float(rolling_756.min(skipna=True)),
        "rolling_504_nonpositive_ratio_pct": float((rolling_504.dropna() <= 0.0).mean() * 100.0),
        "daily_return_std_pct": float(np.std(returns, ddof=1) * 100.0) if len(returns) > 1 else 0.0,
    }


def _annual_returns(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    group["daily_return"] = group["balance"].pct_change().fillna(0.0)
    annual = (1.0 + group.groupby(group["date"].dt.year)["daily_return"].apply(lambda s: (1.0 + s).prod() - 1.0)) - 1.0
    rows = []
    for year, ret in annual.items():
        rows.append(
            {
                "variant": group["variant"].iloc[0],
                "label": group["label"].iloc[0],
                "year": int(year),
                "annual_return_pct": float(ret * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _rolling_windows(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    series = pd.Series(group["balance"].to_numpy(dtype=float), index=pd.to_datetime(group["date"]))
    rows = []
    for window in (252, 504, 756):
        rolling = series.pct_change(window) * 100.0
        if rolling.dropna().empty:
            continue
        min_date = rolling.idxmin()
        rows.append(
            {
                "variant": group["variant"].iloc[0],
                "label": group["label"].iloc[0],
                "window_trading_days": window,
                "worst_return_pct": float(rolling.min(skipna=True)),
                "worst_end_date": pd.Timestamp(min_date).date().isoformat(),
                "nonpositive_ratio_pct": float((rolling.dropna() <= 0.0).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _add_relative_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    summary = summary.copy()
    c3_return = _safe_float(summary.loc[summary["variant"].eq("B_c3_current_50w"), "total_return_pct"].iloc[0])
    official_return = _safe_float(summary.loc[summary["variant"].eq("A_official78_1_50w"), "total_return_pct"].iloc[0])
    c3_ulcer = _safe_float(summary.loc[summary["variant"].eq("B_c3_current_50w"), "ulcer_index_pct"].iloc[0])
    c3_underwater = _safe_float(summary.loc[summary["variant"].eq("B_c3_current_50w"), "longest_underwater_trading_days"].iloc[0])
    summary["return_retention_vs_c3_pct"] = summary["total_return_pct"] / c3_return * 100.0
    summary["return_retention_vs_official78_pct"] = summary["total_return_pct"] / official_return * 100.0
    summary["ulcer_reduction_vs_c3_pct"] = (1.0 - summary["ulcer_index_pct"] / c3_ulcer) * 100.0
    summary["underwater_reduction_vs_c3_pct"] = (1.0 - summary["longest_underwater_trading_days"] / c3_underwater) * 100.0
    summary["hard_dd_pass"] = summary["max_dd_pct"] >= TARGET_MAX_DD_PCT
    summary["strict_return_pass"] = summary["return_retention_vs_c3_pct"] >= STRICT_RETURN_RETENTION_PCT
    summary["research_return_pass"] = summary["return_retention_vs_c3_pct"] >= RESEARCH_RETURN_RETENTION_PCT
    summary["smoothness_pass"] = (summary["ulcer_reduction_vs_c3_pct"] >= 10.0) | (
        summary["underwater_reduction_vs_c3_pct"] >= 10.0
    )
    summary["strict_candidate_pass"] = summary["hard_dd_pass"] & summary["strict_return_pass"]
    summary["smooth_lower_return_candidate"] = summary["hard_dd_pass"] & summary["smoothness_pass"] & summary["research_return_pass"]
    return summary


def _rank_summary(summary: pd.DataFrame) -> pd.DataFrame:
    summary = summary.copy()
    summary["smoothness_rank"] = (
        summary["ulcer_index_pct"].rank(method="min", ascending=True)
        + summary["longest_underwater_trading_days"].rank(method="min", ascending=True)
        + summary["worst_504d_return_pct"].rank(method="min", ascending=False)
        + summary["max_dd_pct"].rank(method="min", ascending=False)
    )
    summary = summary.sort_values(
        ["strict_candidate_pass", "smooth_lower_return_candidate", "smoothness_rank", "return_retention_vs_c3_pct"],
        ascending=[False, False, True, False],
    )
    return summary


def _build_report(summary: pd.DataFrame, annual: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> str:
    display_cols = [
        "variant",
        "label",
        "category",
        "total_return_pct",
        "return_retention_vs_c3_pct",
        "max_dd_pct",
        "ulcer_index_pct",
        "longest_underwater_trading_days",
        "worst_504d_return_pct",
        "rolling_504_nonpositive_ratio_pct",
        "sharpe",
        "strict_candidate_pass",
        "smooth_lower_return_candidate",
    ]
    top = summary[display_cols].copy()
    for col in top.select_dtypes(include=[np.number]).columns:
        top[col] = top[col].map(lambda x: round(float(x), 4))

    annual_pivot = annual.pivot_table(index="variant", columns="year", values="annual_return_pct", aggfunc="last")
    annual_pivot = annual_pivot.reset_index()
    for col in annual_pivot.columns:
        if col != "variant":
            annual_pivot[col] = annual_pivot[col].map(lambda x: round(float(x), 2) if pd.notna(x) else x)
    annual_pivot.columns = [str(col) for col in annual_pivot.columns]

    rolling_show = rolling.copy()
    for col in rolling_show.select_dtypes(include=[np.number]).columns:
        rolling_show[col] = rolling_show[col].map(lambda x: round(float(x), 4))

    lines = [
        "# Stage365 平滑度前沿横向审计",
        "",
        "## 调研与判断",
        "",
        "- 外部口径：最大回撤只看单一最坏峰谷；Ulcer Index 同时惩罚回撤深度和持续时间；Calmar 用年化收益除以最大回撤。",
        "- 本阶段判断：用户关心的“全周期更平滑”和“两年几乎没增长”，不能只看最大回撤，必须同时看 Ulcer Index、最长水下交易日、最差两年滚动收益和两年滚动非正收益占比。",
        "- 本阶段不新增交易规则、不调参数，只读取已有候选权益曲线做横向审计。",
        "",
        "## 总结",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 严格候选数量：`{decision['strict_candidate_count']}`。",
        f"- 更平滑但收益下降的研究候选数量：`{decision['smooth_lower_return_candidate_count']}`。",
        f"- 当前最优严格候选：`{decision.get('best_strict_candidate') or '-'}`。",
        f"- 当前最平滑可研究候选：`{decision.get('best_smooth_candidate') or '-'}`。",
        "",
        "## 横向指标",
        "",
        to_markdown_table(top),
        "",
        "## 年度收益",
        "",
        to_markdown_table(annual_pivot),
        "",
        "## 滚动窗口最差收益",
        "",
        to_markdown_table(rolling_show),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。原因是本阶段只审计既有曲线，不新增规则、不搜索阈值。",
        "- 运行后判断：不是过拟合。原因是排序只用于发现路径质量，不把排序结果直接升格为交易规则。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。原因是目标已经从单纯30%回撤扩展到收益/回撤/平滑度三维，需要统一审计。",
        "- 运行后判断：有价值，但必须区分部署候选、净值层候选和真实可交易候选。若最平滑结果主要来自稀释或不可承载卫星，不能直接晋级。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    curves = _all_curves()
    curves.to_csv(CURVES_PATH, index=False)

    summary = pd.DataFrame([_curve_metrics(group) for _, group in curves.groupby("variant", sort=False)])
    summary = _add_relative_metrics(summary)
    summary = _rank_summary(summary)
    annual = pd.concat([_annual_returns(group) for _, group in curves.groupby("variant", sort=False)], ignore_index=True)
    rolling = pd.concat([_rolling_windows(group) for _, group in curves.groupby("variant", sort=False)], ignore_index=True)

    strict = summary[summary["strict_candidate_pass"]].copy()
    smooth = summary[summary["smooth_lower_return_candidate"]].copy()
    best_strict = None if strict.empty else str(strict.iloc[0]["variant"])
    best_smooth = None if smooth.empty else str(smooth.sort_values(["smoothness_rank", "return_retention_vs_c3_pct"], ascending=[True, False]).iloc[0]["variant"])
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "smoothness_candidates_found_but_require_status_split"
        if not strict.empty or not smooth.empty
        else "no_smoothness_candidate",
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "strict_return_retention_pct": STRICT_RETURN_RETENTION_PCT,
        "research_return_retention_pct": RESEARCH_RETURN_RETENTION_PCT,
        "strict_candidate_count": int(len(strict)),
        "smooth_lower_return_candidate_count": int(len(smooth)),
        "best_strict_candidate": best_strict,
        "best_smooth_candidate": best_smooth,
        "strict_candidates": strict["variant"].tolist(),
        "smooth_lower_return_candidates": smooth["variant"].tolist(),
        "outputs": {
            "summary": SUMMARY_PATH.name,
            "annual": ANNUAL_PATH.name,
            "rolling": ROLLING_PATH.name,
            "curves": CURVES_PATH.name,
            "report": REPORT_PATH.name,
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False)
    annual.to_csv(ANNUAL_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, annual, rolling, decision), encoding="utf-8")

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
