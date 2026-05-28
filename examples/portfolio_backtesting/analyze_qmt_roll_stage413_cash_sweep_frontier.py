from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage387_stage079_short_holding_candidates as s387


OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage413_cash_sweep_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage413_cash_sweep_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

STAGE403_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
REQUIRED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_yield_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SCENARIOS = (0.0, 0.005, 0.009, 0.01, 0.012, 0.015, 0.02, 0.03, 0.05)
GRID_YIELDS = np.arange(0.0, 0.2001, 0.0025)
REALISTIC_MAX_YIELD = 0.012

LARGER_IS_BETTER = {"return_p05_pct", "return_median_pct", "positive_return_rate", "max_dd_worst_pct"}
SMALLER_IS_BETTER = {
    "annualized_below_5pct_rate",
    "dd20_breach_rate",
    "dd30_breach_rate",
    "ulcer_p95_pct",
    "longest_underwater_p95_days",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
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


def _load_stage403_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[
        frame["window_name"].eq("start_2020") & frame["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])
    ].copy()
    for col in ["combo_slippage", "equity"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame.sort_values(["variant", "date"])


def _variant_series(frame: pd.DataFrame, variant: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    daily = frame[frame["variant"].eq(variant)].sort_values("date").drop_duplicates("date", keep="last")
    daily = daily.set_index("date").reindex(calendar)
    daily["equity"] = pd.to_numeric(daily["equity"], errors="coerce").ffill()
    daily["combo_slippage"] = pd.to_numeric(daily["combo_slippage"], errors="coerce").fillna(0.0)
    daily["variant"] = variant
    return daily


def _cash_yield_series(cash: float, calendar: pd.DatetimeIndex, annual_yield: float) -> pd.Series:
    days = (calendar - calendar[0]).days.to_numpy(dtype=float)
    values = cash * np.power(1.0 + annual_yield, days / 365.0)
    return pd.Series(values, index=calendar)


def _candidate(variant: str, label: str, equity: pd.Series, yield_rate: float) -> s387.Candidate:
    candidate = s387.Candidate(
        variant=variant,
        label=label,
        equity=equity.astype(float),
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="cash_sweep_frontier",
        eligible_for_promotion=True,
        note=f"Stage103核心权益 + 11.5万现金年化{yield_rate * 100:.2f}%。",
    )
    candidate.equity.attrs["yield_rate"] = yield_rate
    return candidate


def _build_candidates(stage079: pd.Series, stage103: pd.Series, calendar: pd.DatetimeIndex) -> list[s387.Candidate]:
    stage103_core = stage103 - STAGE079_CASH
    candidates = [
        _candidate(BASELINE_VARIANT, "Stage079基准", stage079, 0.0),
        _candidate(STAGE103_VARIANT, "Stage103 broker10_guard", stage103, 0.0),
    ]
    for y in SCENARIOS:
        variant = f"stage103_cash_sweep_{int(round(y * 10000)):04d}bp"
        label = f"Stage103+现金年化{y * 100:.2f}%"
        candidates.append(_candidate(variant, label, stage103_core + _cash_yield_series(STAGE079_CASH, calendar, y), y))
    return candidates


def _cost_stress(candidates: list[s387.Candidate], daily079: pd.DataFrame, daily103: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline = {c.variant: c for c in candidates}[BASELINE_VARIANT].equity
    cum_slip079 = daily079["combo_slippage"].cumsum()
    cum_slip103 = daily103["combo_slippage"].cumsum()
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        stressed079 = baseline - (multiplier - 1.0) * cum_slip079.reindex(baseline.index).ffill().fillna(0.0)
        baseline_nav = s387._nav(stressed079)
        base_dd = s387._max_drawdown(baseline_nav)
        baseline_dd[multiplier] = base_dd
        for candidate in candidates:
            if candidate.variant == BASELINE_VARIANT:
                stressed = stressed079
            else:
                stressed = candidate.equity - (multiplier - 1.0) * cum_slip103.reindex(candidate.equity.index).ffill().fillna(0.0)
            nav = s387._nav(stressed)
            rows.append(
                {
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "yield_rate": float(candidate.equity.attrs.get("yield_rate", 0.0)),
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": s387._max_drawdown(nav),
                    "baseline_stage079_max_dd_pct": base_dd,
                    "not_worse_than_stage079_stress": int(s387._max_drawdown(nav) >= base_dd - 1e-9),
                }
            )
    return pd.DataFrame(rows)


def _objective_improved_counts(horizon: pd.DataFrame) -> pd.DataFrame:
    baseline = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    for _, row in horizon.iterrows():
        horizon_days = int(row["horizon_days"])
        base = baseline.loc[horizon_days]
        improved = 0
        target_hits = 0
        target = s387.HORIZON_TARGETS[horizon_days]
        for metric in sorted(LARGER_IS_BETTER):
            improved += int(_safe_float(row[metric]) > _safe_float(base[metric]))
            target_hits += int(_safe_float(row[metric]) >= _safe_float(target[metric]))
        for metric in sorted(SMALLER_IS_BETTER):
            improved += int(_safe_float(row[metric]) < _safe_float(base[metric]))
            target_hits += int(_safe_float(row[metric]) <= _safe_float(target[metric]))
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
                "objective_target_hit_9_count": target_hits,
            }
        )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_wide = score.pivot_table(index=["variant", "label"], columns="horizon_days", values="experience_score").reset_index()
    score_wide.columns = ["variant", "label", "score_90d", "score_180d"]
    counts = _objective_improved_counts(horizon).pivot_table(
        index=["variant", "label"], columns="horizon_days", values=["objective_improved_8_count", "objective_target_hit_9_count"]
    )
    counts.columns = [f"{a}_{b}d" for a, b in counts.columns]
    counts = counts.reset_index()
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        variant = row["variant"]
        c = cost[cost["variant"].eq(variant)]
        checks = {
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= -30.0,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
        }
        rows.append(
            {
                "variant": variant,
                "label": row["label"],
                "yield_rate": float(row.get("yield_rate", 0.0)),
                "hard_pass": int(all(checks.values())),
                "failed_hard_checks": ",".join([key for key, value in checks.items() if not value]),
            }
        )
    gate = pd.DataFrame(rows).merge(score_wide, on=["variant", "label"], how="left").merge(counts, on=["variant", "label"], how="left")
    gate["score90_improve_ge10pct"] = (gate["score_90d"] >= 110.0).astype(int)
    gate["score180_improve_ge10pct"] = (gate["score_180d"] >= 110.0).astype(int)
    gate["improved_5of8_each"] = (
        (gate["objective_improved_8_count_90d"] >= 5) & (gate["objective_improved_8_count_180d"] >= 5)
    ).astype(int)
    gate["target_pass"] = (
        gate["hard_pass"].eq(1)
        & gate["score90_improve_ge10pct"].eq(1)
        & gate["score180_improve_ge10pct"].eq(1)
        & gate["improved_5of8_each"].eq(1)
    ).astype(int)
    gate["ideal_all_targets_hit"] = (
        (gate["objective_target_hit_9_count_90d"] >= 9) & (gate["objective_target_hit_9_count_180d"] >= 9)
    ).astype(int)
    gate["realistic_yield"] = (gate["yield_rate"] <= REALISTIC_MAX_YIELD + 1e-12).astype(int)
    return gate.sort_values(["target_pass", "score_90d", "score_180d"], ascending=False)


def _frontier(calendar: pd.DatetimeIndex, stage079: pd.Series, stage103: pd.Series, daily079: pd.DataFrame, daily103: pd.DataFrame) -> pd.DataFrame:
    stage103_core = stage103 - STAGE079_CASH
    rows: list[dict[str, Any]] = []
    for y in GRID_YIELDS:
        candidate = _candidate(
            f"grid_{int(round(y * 10000)):04d}bp",
            f"grid {y * 100:.2f}%",
            stage103_core + _cash_yield_series(STAGE079_CASH, calendar, float(y)),
            float(y),
        )
        summary = pd.DataFrame([s387._stats(_candidate(BASELINE_VARIANT, "Stage079", stage079, 0.0)), s387._stats(candidate)])
        horizon = pd.DataFrame(
            [
                s387._horizon_metrics(_candidate(BASELINE_VARIANT, "Stage079", stage079, 0.0), days)
                for days in (90, 180)
            ]
            + [s387._horizon_metrics(candidate, days) for days in (90, 180)]
        )
        score = s387._score_horizons(horizon)
        cost = _cost_stress([_candidate(BASELINE_VARIANT, "Stage079", stage079, 0.0), candidate], daily079, daily103)
        gate = _gate(summary.assign(yield_rate=[0.0, float(y)]), horizon, score, cost)
        row = gate[gate["variant"].eq(candidate.variant)].iloc[0].to_dict()
        h90 = horizon[(horizon["variant"].eq(candidate.variant)) & (horizon["horizon_days"].eq(90))].iloc[0]
        h180 = horizon[(horizon["variant"].eq(candidate.variant)) & (horizon["horizon_days"].eq(180))].iloc[0]
        row.update(
            {
                "yield_rate": float(y),
                "yield_pct": float(y * 100.0),
                "return_p05_90d": _safe_float(h90["return_p05_pct"]),
                "positive_rate_90d": _safe_float(h90["positive_return_rate"]),
                "below5_rate_90d": _safe_float(h90["annualized_below_5pct_rate"]),
                "dd20_rate_90d": _safe_float(h90["dd20_breach_rate"]),
                "ulcer_p95_90d": _safe_float(h90["ulcer_p95_pct"]),
                "uw_p95_90d": _safe_float(h90["longest_underwater_p95_days"]),
                "return_p05_180d": _safe_float(h180["return_p05_pct"]),
                "positive_rate_180d": _safe_float(h180["positive_return_rate"]),
                "below5_rate_180d": _safe_float(h180["annualized_below_5pct_rate"]),
                "dd20_rate_180d": _safe_float(h180["dd20_breach_rate"]),
                "ulcer_p95_180d": _safe_float(h180["ulcer_p95_pct"]),
                "uw_p95_180d": _safe_float(h180["longest_underwater_p95_days"]),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _required_yields(frontier: pd.DataFrame) -> pd.DataFrame:
    requirements = {
        "target_pass_gate": lambda f: f["target_pass"].eq(1),
        "ideal_all_targets": lambda f: f["ideal_all_targets_hit"].eq(1),
        "90d_p05_gt_minus8": lambda f: f["return_p05_90d"] > -8.0,
        "90d_positive_ge80": lambda f: f["positive_rate_90d"] >= 0.80,
        "90d_below5_le22": lambda f: f["below5_rate_90d"] <= 0.22,
        "90d_dd20_le12": lambda f: f["dd20_rate_90d"] <= 0.12,
        "90d_ulcer_le15": lambda f: f["ulcer_p95_90d"] <= 15.0,
        "90d_uw_le80": lambda f: f["uw_p95_90d"] <= 80.0,
        "180d_p05_gt0": lambda f: f["return_p05_180d"] > 0.0,
        "180d_positive_ge95": lambda f: f["positive_rate_180d"] >= 0.95,
        "180d_below5_le6": lambda f: f["below5_rate_180d"] <= 0.06,
        "180d_dd20_le25": lambda f: f["dd20_rate_180d"] <= 0.25,
        "180d_ulcer_le17": lambda f: f["ulcer_p95_180d"] <= 17.0,
        "180d_uw_le150": lambda f: f["uw_p95_180d"] <= 150.0,
    }
    rows: list[dict[str, Any]] = []
    for name, predicate in requirements.items():
        hit = frontier[predicate(frontier)].sort_values("yield_rate")
        if hit.empty:
            rows.append({"requirement": name, "required_yield_pct": np.nan, "found_within_20pct": 0, "realistic_1p2pct_or_less": 0})
        else:
            y = float(hit.iloc[0]["yield_pct"])
            rows.append(
                {
                    "requirement": name,
                    "required_yield_pct": y,
                    "found_within_20pct": 1,
                    "realistic_1p2pct_or_less": int(y <= REALISTIC_MAX_YIELD * 100.0 + 1e-12),
                }
            )
    return pd.DataFrame(rows)


def _plot(gate: pd.DataFrame, frontier: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    plot = frontier.copy()
    axes[0, 0].plot(plot["yield_pct"], plot["score_90d"], label="90d")
    axes[0, 0].plot(plot["yield_pct"], plot["score_180d"], label="180d")
    axes[0, 0].axhline(110.0, color="red", linestyle="--", linewidth=1)
    axes[0, 0].axvline(REALISTIC_MAX_YIELD * 100.0, color="gray", linestyle="--", linewidth=1)
    axes[0, 0].set_title("Cash sweep experience score frontier")
    axes[0, 0].set_xlabel("Annual cash yield %")
    axes[0, 0].legend()

    axes[0, 1].plot(plot["yield_pct"], plot["return_p05_90d"], label="90d p05")
    axes[0, 1].plot(plot["yield_pct"], plot["return_p05_180d"], label="180d p05")
    axes[0, 1].axhline(-8.0, color="#1f77b4", linestyle="--", linewidth=1)
    axes[0, 1].axhline(0.0, color="#ff7f0e", linestyle="--", linewidth=1)
    axes[0, 1].axvline(REALISTIC_MAX_YIELD * 100.0, color="gray", linestyle="--", linewidth=1)
    axes[0, 1].set_title("Lower-tail return frontier")
    axes[0, 1].legend()

    axes[1, 0].plot(plot["yield_pct"], plot["positive_rate_90d"], label="90d positive")
    axes[1, 0].plot(plot["yield_pct"], plot["positive_rate_180d"], label="180d positive")
    axes[1, 0].axhline(0.80, color="#1f77b4", linestyle="--", linewidth=1)
    axes[1, 0].axhline(0.95, color="#ff7f0e", linestyle="--", linewidth=1)
    axes[1, 0].axvline(REALISTIC_MAX_YIELD * 100.0, color="gray", linestyle="--", linewidth=1)
    axes[1, 0].set_title("Positive rate frontier")
    axes[1, 0].legend()

    scenario = gate[gate["variant"].str.contains("cash_sweep")].sort_values("yield_rate")
    scenario_x = np.arange(len(scenario))
    scenario_labels = [f"{y * 100.0:.2f}%" for y in scenario["yield_rate"]]
    axes[1, 1].bar(scenario_x, scenario["target_pass"], color="#4c78a8")
    axes[1, 1].set_xticks(scenario_x, scenario_labels, rotation=35, ha="right", fontsize=8)
    axes[1, 1].set_title("Scenario target pass")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    gate: pd.DataFrame,
    frontier: pd.DataFrame,
    required: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage113 现金管理收益前沿审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：边界审计；不新增交易信号，不占用额外保证金，不增加总资金。",
        "- 外部约束：2026年5月国内货币基金/现金管理收益大多约0.9%-1.2%，2%属于偏乐观假设。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 场景门禁",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "yield_rate",
                    "hard_pass",
                    "target_pass",
                    "ideal_all_targets_hit",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "objective_target_hit_9_count_90d",
                    "objective_target_hit_9_count_180d",
                    "realistic_yield",
                    "failed_hard_checks",
                ]
            ]
        ),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[["variant", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "yield_rate"]]),
        "",
        "## 3/6个月体验",
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
                    "dd20_breach_rate",
                    "ulcer_p95_pct",
                    "longest_underwater_p95_days",
                ]
            ]
        ),
        "",
        "## 达标所需现金收益率",
        "",
        _md_table(required),
        "",
        "## 前沿抽样",
        "",
        _md_table(frontier[frontier["yield_pct"].isin([0.0, 1.0, 2.0, 5.0, 10.0, 20.0])], max_rows=20),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段没有优化交易规则，只审计现金管理收益的物理上限。",
        "- 不用回测结果反推应该选择的收益率；收益率必须来自外部可获得现金管理工具。",
        "- 若现实收益率只能在约0.9%-1.2%，则现金管理只能作为低风险小增强，不能承担达成理想3/6个月目标的任务。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = _load_stage403_daily()
    calendar = pd.date_range(raw["date"].min(), raw["date"].max(), freq="D")
    daily079 = _variant_series(raw, BASELINE_VARIANT, calendar)
    daily103 = _variant_series(raw, STAGE103_VARIANT, calendar)
    stage079 = daily079["equity"].astype(float)
    stage103 = daily103["equity"].astype(float)
    candidates = _build_candidates(stage079, stage103, calendar)
    summary_rows = []
    for candidate in candidates:
        row = s387._stats(candidate)
        row["yield_rate"] = float(candidate.equity.attrs.get("yield_rate", 0.0))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    horizon = pd.DataFrame([s387._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s387._score_horizons(horizon)
    cost = _cost_stress(candidates, daily079, daily103)
    gate = _gate(summary, horizon, score, cost)
    frontier = _frontier(calendar, stage079, stage103, daily079, daily103)
    required = _required_yields(frontier)

    realistic = gate[gate["realistic_yield"].eq(1) & gate["target_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    best_realistic = gate[gate["realistic_yield"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT])].iloc[0]
    best_any = gate[~gate["variant"].isin([BASELINE_VARIANT])].iloc[0]
    ideal_hit = gate[gate["ideal_all_targets_hit"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT])]
    decision = {
        "stage": "Stage113",
        "line_id": LINE_ID,
        "decision": "cash_sweep_small_enhancement_not_full_solution",
        "realistic_yield_max": REALISTIC_MAX_YIELD,
        "realistic_target_pass_variants": realistic["variant"].tolist(),
        "best_realistic_variant": str(best_realistic["variant"]),
        "best_realistic_score_90d": _safe_float(best_realistic["score_90d"]),
        "best_realistic_score_180d": _safe_float(best_realistic["score_180d"]),
        "best_any_scenario_variant": str(best_any["variant"]),
        "ideal_hit_variants": ideal_hit["variant"].tolist(),
        "required_yield_table": required.to_dict(orient="records"),
        "chart": str(CHART_PATH),
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(FRONTIER_PATH.with_name(f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"), index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    required.to_csv(REQUIRED_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(gate, frontier)
    _write_report(summary, horizon, score, gate, frontier, required, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
