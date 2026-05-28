from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage395_stage079_product_direction_failure_cooldown as s095
from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage397_stage079_active_breadth_cap3_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage397_stage079_active_breadth_cap3_true_engine"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
PROMOTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


@dataclass(frozen=True)
class Profile:
    variant: str
    label: str
    overrides: dict[str, Any]
    note: str


PROFILES: tuple[Profile, ...] = (
    Profile(
        BASELINE_VARIANT,
        "Stage079真实引擎基准：50万C3下单+11.5万现金",
        {},
        "C3真实引擎日权益外加11.5万现金，作为唯一硬约束基准。",
    ),
    Profile(
        "active_breadth_cap3_true_engine",
        "真实引擎：Stage079最大并发活跃品种限制为3",
        {"max_concurrent_positions": 3},
        "Stage096广度/拥挤度诊断后的固定候选；只验证整数并发上限3，不扫2/4/5。",
    ),
)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s095._md_table(frame, max_rows=max_rows)


def _calendar_equity(daily: pd.DataFrame, variant: str) -> pd.Series:
    frame = daily[daily["variant"].eq(variant) & daily["slippage_multiplier"].eq(1.0)].copy()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _as_candidate(profile: Profile, equity: pd.Series) -> Any:
    return s095.s087.Candidate(
        variant=profile.variant,
        label=profile.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="true_engine_active_breadth_cap",
        eligible_for_promotion=True,
        note=profile.note,
    )


def _cost_stress(cost_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in sorted(cost_daily["slippage_multiplier"].unique()):
        one = cost_daily[cost_daily["slippage_multiplier"].eq(multiplier)]
        for profile in PROFILES:
            frame = one[one["variant"].eq(profile.variant)].sort_values("date")
            equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
            calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
            equity = equity.reindex(calendar).ffill().dropna()
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s095.s087._max_drawdown(nav)
            if profile.variant == BASELINE_VARIANT:
                baseline_dd[float(multiplier)] = max_dd
            rows.append(
                {
                    "variant": profile.variant,
                    "label": profile.label,
                    "slippage_multiplier": float(multiplier),
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


def _plot_equity_drawdown(daily: pd.DataFrame) -> None:
    one = daily[daily["slippage_multiplier"].eq(1.0)].copy()
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for profile in PROFILES:
        frame = one[one["variant"].eq(profile.variant)].sort_values("date")
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
        equity = equity.reindex(calendar).ffill().dropna()
        nav = equity / ACCOUNT_CAPITAL
        dd = nav / nav.cummax() - 1.0
        axes[0].plot(equity.index, nav, label=profile.variant, linewidth=1.4)
        axes[1].plot(dd.index, dd * 100.0, label=profile.variant, linewidth=1.1)
    axes[0].set_title("Stage097 active breadth cap3 account NAV")
    axes[0].set_ylabel("NAV")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=8)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    promotion: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_summary = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "total_trade_count",
        "win_ratio",
    ]
    focus_horizon = [
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
    focus_score = ["variant", "score_90d", "score_180d", "short_holding_score"]
    focus_cost = ["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "not_worse_than_stage079_stress"]
    focus_promotion = [
        "variant",
        "promotion_pass",
        "score90_improve_ge10pct",
        "score180_improve_ge10pct",
        "improved_5of8_each",
        "failed_constraints",
    ]
    report = [
        "# Stage097 Stage079活跃品种广度上限真实引擎验证",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：Stage096只读诊断后的固定候选；不改入场信号、不改品种池、不扫并发上限。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随研究和CTA实践支持从风险预算、分散度和拥挤度处理组合体验；但这类约束必须用真实引擎验证收益保留。",
        "- Stage096显示高活跃品种广度启动日更容易触发3/6个月DD20，因此本阶段只验证一个粗整数结构：最大并发活跃品种=3。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期硬指标",
        "",
        _md_table(summary[focus_summary]),
        "",
        "## 3个月/6个月任意启动体验",
        "",
        _md_table(horizon[focus_horizon].sort_values(["variant", "horizon_days"])),
        "",
        "## 持有体验评分",
        "",
        _md_table(score[focus_score].drop_duplicates("variant")),
        "",
        "## 成本压力",
        "",
        _md_table(cost[focus_cost].sort_values(["variant", "slippage_multiplier"])),
        "",
        "## 晋级闸门",
        "",
        _md_table(promotion[focus_promotion]),
        "",
        "## 反过拟合说明",
        "",
        "- 候选来自 Stage096 的启动日前状态桶，不使用未来收益下单。",
        "- 只验证 `max_concurrent_positions=3` 一个粗整数，不扫2/4/5，也不通过提高单笔风险补收益。",
        "- 若硬指标或3/6个月体验门禁失败，本路线不继续做并发数字救援。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    normal_daily_parts: list[pd.DataFrame] = []
    cost_daily_parts: list[pd.DataFrame] = []
    normal_stats: dict[str, dict[str, Any]] = {}

    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for profile in PROFILES:
            stage095_profile = s095.Profile(profile.variant, profile.label, profile.overrides, profile.note)
            analysis_df, statistics, _ = s095._run_engine(stage095_profile, multiplier)
            daily = s095._daily_equity(stage095_profile, analysis_df, multiplier)
            cost_daily_parts.append(daily)
            if multiplier == 1.0:
                normal_daily_parts.append(daily)
                normal_stats[profile.variant] = statistics

    normal_daily = pd.concat(normal_daily_parts, ignore_index=True)
    cost_daily = pd.concat(cost_daily_parts, ignore_index=True)

    candidates = [_as_candidate(profile, _calendar_equity(normal_daily, profile.variant)) for profile in PROFILES]
    summary = pd.DataFrame([s095.s087._stats(candidate) for candidate in candidates])
    for profile in PROFILES:
        stats = normal_stats.get(profile.variant, {})
        mask = summary["variant"].eq(profile.variant)
        summary.loc[mask, "total_slippage"] = float(stats.get("total_slippage", 0.0) or 0.0)
        summary.loc[mask, "total_commission"] = float(stats.get("total_commission", 0.0) or 0.0)
        summary.loc[mask, "total_trade_count"] = int(stats.get("total_trade_count", 0) or 0)
        summary.loc[mask, "win_ratio"] = float(stats.get("win_ratio", 0.0) or 0.0)

    horizon = pd.DataFrame(
        [s095.s087._horizon_metrics(candidate, horizon_days) for candidate in candidates for horizon_days in (90, 180)]
    )
    score = s095.s087._score_horizons(horizon)
    cost = _cost_stress(cost_daily)
    constraints = s095.s087._constraints(summary, cost)
    promotion = s095.s087._promotion(score, horizon, constraints)

    promoted = promotion[promotion["promotion_pass"].eq(1)]
    decision = {
        "stage": "Stage097",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promote" if not promoted.empty else "no_promotion",
        "promoted_variants": promoted["variant"].tolist(),
        "best_by_short_holding_score": promotion.iloc[0]["variant"] if not promotion.empty else "",
        "normal_cost_chart": str(CHART_PATH),
        "note": "真实引擎验证；若无promotion，则活跃品种广度上限只保留为诊断经验。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    promotion.to_csv(PROMOTION_PATH, index=False, encoding="utf-8-sig")
    normal_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_equity_drawdown(normal_daily)
    _write_report(summary, horizon, score, cost, promotion, decision)

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage397] report={REPORT_PATH}", flush=True)
    print(f"[stage397] chart={CHART_PATH}", flush=True)


if __name__ == "__main__":
    main()
