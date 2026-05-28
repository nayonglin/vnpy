from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage425_stage103_open_interest_confirmation_overlay as s425  # noqa: E402


MODEL_TAG = "stage435_stage103_commodity_skewness_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage435_stage103_commodity_skewness_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
TARGET_DD_PCT = s405.TARGET_DD_PCT
SKEW_LOOKBACK_DAYS = 252
REBALANCE_EVERY = 20

SKEW_BEST1_VARIANT = "stage103_plus_low_skew252_monthly_best1_guard"
SKEW_TOP3_VARIANT = "stage103_plus_low_skew252_monthly_top3_guard"

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    role: str
    direction: str
    lookback_days: int
    top_n: int
    rebalance_every: int
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        BASELINE_VARIANT,
        "A Stage079 baseline",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
    ),
    VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前主执行相对候选。",
    ),
    VariantSpec(
        SKEW_BEST1_VARIANT,
        "C1 Stage103+低偏度252日monthly best1",
        "commodity_skewness_overlay",
        "reversal",
        SKEW_LOOKBACK_DAYS,
        1,
        REBALANCE_EVERY,
        "过去252交易日日收益偏度最低者做多、最高者做空，每20个交易日再平衡，每侧1个品种，每品种1手，沿用10%保证金闸门。",
    ),
    VariantSpec(
        SKEW_TOP3_VARIANT,
        "C2 Stage103+低偏度252日monthly top3",
        "commodity_skewness_overlay",
        "reversal",
        SKEW_LOOKBACK_DAYS,
        3,
        REBALANCE_EVERY,
        "过去252交易日日收益偏度最低者做多、最高者做空，每20个交易日再平衡，每侧3个品种，每品种1手，沿用10%保证金闸门。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s405._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s405._md_table(frame, max_rows=max_rows)


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.role,
        eligible_for_promotion=spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT},
        note=spec.note,
    )


def _build_skewness_rank_tables(price_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = (
        price_frame.pivot_table(index="date", columns="product_vt_symbol", values="product_return", aggfunc="last")
        .sort_index()
        .fillna(0.0)
    )
    skew = returns.rolling(SKEW_LOOKBACK_DAYS, min_periods=SKEW_LOOKBACK_DAYS).skew().shift(1)
    feature = skew.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="skew252")
    feature["date"] = pd.to_datetime(feature["date"], errors="coerce").dt.normalize()
    feature["has_skew_signal"] = feature["skew252"].notna().astype(int)
    feature.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    return {
        BASELINE_VARIANT: pd.DataFrame(),
        STAGE103_VARIANT: pd.DataFrame(),
        SKEW_BEST1_VARIANT: skew,
        SKEW_TOP3_VARIANT: skew,
    }


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "+skew best1", "+skew top3"]
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=6)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(TARGET_DD_PCT, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=6)

    x = np.arange(len(variants))
    s90 = score[score["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    s180 = score[score["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - 0.18, s90["experience_score"].to_numpy(dtype=float), 0.36, label="90d score")
    axes[0, 1].bar(x + 0.18, s180["experience_score"].to_numpy(dtype=float), 0.36, label="180d score")
    axes[0, 1].axhline(110.0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 1].set_title("Short holding scores")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    axes[0, 1].legend(fontsize=8)

    pw = pairwise[
        pairwise["comparator_variant"].eq(STAGE103_VARIANT) & pairwise["window_days"].isin([90, 180, 252, 504])
    ]
    for variant, frame in pw.groupby("candidate_variant", sort=False):
        axes[1, 1].plot(frame["window_days"], frame["return_win_rate"], marker="o", label=variant)
    axes[1, 1].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Rolling return win rate vs Stage103")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].legend(fontsize=6)

    fig.suptitle("Stage135 commodity skewness overlay", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    fresh: pd.DataFrame,
    cost: pd.DataFrame,
    margin_audit: pd.DataFrame,
    bad_windows: pd.DataFrame,
    gate: pd.DataFrame,
    pairwise: pd.DataFrame,
    topday: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage135 Stage103商品期货偏度异象overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：外部先验驱动的低自由度结构验证；不改C3、Stage079、Stage103交易规则，不增加账户资金。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage103+低偏度252日monthly best1；C2=Stage103+低偏度252日monthly top3。",
        "- 候选假设：商品期货存在正偏度彩票偏好，高偏度品种未来收益较弱；因此做多过去252日低偏度品种、做空高偏度品种，可能提供不同于趋势的收益源。",
        "- 固定口径：252交易日偏度、shift一日；每20个交易日再平衡；每品种1手；沿用10%经纪商保证金闸门；不按坏窗口调日期或品种。",
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
            ]
        ),
        "",
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## Stage104底部5%坏窗口贡献",
        "",
        _md_table(bad_windows),
        "",
        "## 任意启动滚动胜率",
        "",
        _md_table(pairwise),
        "",
        "## 最大贡献日剔除",
        "",
        _md_table(topday, max_rows=80),
        "",
        "## 多起点与10%保证金缓冲",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "overlay_turnover",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=120,
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
                    "stage079_max_dd_pct",
                    "stage103_max_dd_pct",
                    "not_worse_than_stage079_stress",
                    "not_worse_than_stage103_stress",
                ]
            ]
        ),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "short_score_not_lower_than_stage103",
                    "bad_window_not_worse_than_stage103",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只测试文献先验驱动的252日偏度，不按本地坏窗口、年份、品种或结果调窗口、阈值、top_n相邻小数。",
        "- `best1` 是最小可执行承载，`top3` 是文献型横截面组合承载；若两者不能通过冷启动、成本和任意启动审计，则不继续救。",
        "- 若失败，不继续扫 `63/126/504`、周频/月频、top_n、偏度阈值、日期或品种过滤。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full_frame)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    rank_tables = _build_skewness_rank_tables(price_frame)
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    old_s405_variants = s405.VARIANTS
    old_s425_variants = s425.VARIANTS
    s405.VARIANTS = VARIANTS
    s425.VARIANTS = VARIANTS
    try:
        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates(
                "date", keep="last"
            )
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = s405._empty_overlay(window_name, spec.variant)
                else:
                    overlay = s405._simulate_overlay(
                        spec, window_name, frame, margin_frame, xsmom, price_frame, rank_tables[spec.variant]
                    )
                overlay_by_window_variant[(window_name, spec.variant)] = overlay
                use_xsmom = s405._empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom
                daily = s405._combine_daily(frame, use_xsmom, overlay, spec.variant, 1.0)
                daily["window_name"] = window_name
                daily_by_window_variant[(window_name, spec.variant)] = daily
                if window_name == "start_2020":
                    overlay_full_by_variant[spec.variant] = overlay

        for spec in VARIANTS:
            daily = daily_by_window_variant[("start_2020", spec.variant)]
            full_daily_parts.append(daily)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            candidates.append(_candidate(spec, equity))

        full_daily = pd.concat(full_daily_parts, ignore_index=True)
        overlay_all = pd.concat(
            [frame for frame in overlay_by_window_variant.values() if not frame.empty],
            ignore_index=True,
        )
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
        score = s402.s087._score_horizons(horizon)
        margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
        fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
        bad_windows = s405._bad_window_contribution(
            {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
        )
        gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
        pairwise = s425._rolling_pairwise(full_daily)
        topday = s425._top_edge_day_ablation(full_daily)
    finally:
        s405.VARIANTS = old_s405_variants
        s425.VARIANTS = old_s425_variants

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    pairwise_vs_stage103 = pairwise[pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    weak_pairwise = pairwise_vs_stage103[
        (pairwise_vs_stage103["window_days"].isin([90, 180, 252, 504]))
        & (pairwise_vs_stage103["return_win_rate"].fillna(0.0) < 0.5)
    ]
    fragile_after_one_day = topday[
        topday["comparator_variant"].eq(STAGE103_VARIANT)
        & topday["removed_top_positive_edge_days"].eq(1)
        & (topday["adjusted_return_delta_pp"] < 0.0)
    ]
    best_gate = gate.iloc[0] if not gate.empty else None
    if len(execution_ready) and weak_pairwise.empty and fragile_after_one_day.empty:
        decision_code = "execution_relative_candidate"
    elif len(execution_ready):
        decision_code = "fixed_path_pass_but_robustness_gap_do_not_promote"
    elif len(research_ready):
        decision_code = "research_candidate_only"
    else:
        decision_code = "no_new_promotion"

    decision = {
        "stage": "Stage135",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "judgement": "若低偏度/高偏度overlay不能同时改善Stage079目标并相对Stage103保持稳健，则停止该方向，不继续扫偏度窗口、top_n或日期品种补丁。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, score, pairwise)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
