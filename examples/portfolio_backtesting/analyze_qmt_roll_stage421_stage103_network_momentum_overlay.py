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
import analyze_qmt_roll_stage419_stage103_basis_momentum_overlay as s419  # noqa: E402


MODEL_TAG = "stage421_stage103_network_momentum_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage421_stage103_network_momentum_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
CORR_LOOKBACK = 252
TARGET_DD_PCT = -30.0

NETWORK20_VARIANT = "stage103_plus_network_mom20_corr252_weekly_guard"
NETWORK60_VARIANT = "stage103_plus_network_mom60_corr252_monthly_guard"

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_network_scores_{MODEL_TAG}.csv"
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


VARIANTS: tuple[s405.VariantSpec, ...] = (
    s405.VariantSpec(
        BASELINE_VARIANT,
        "A Stage079 baseline",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
    ),
    s405.VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前主执行相对候选。",
    ),
    s405.VariantSpec(
        NETWORK20_VARIANT,
        "C1 Stage103+network momentum 20d/252corr weekly",
        "network_momentum_overlay",
        "momentum",
        20,
        3,
        5,
        "过去252日正相关网络加权的20日领先品种动量，周频再平衡，强者多、弱者空，各3个品种。",
    ),
    s405.VariantSpec(
        NETWORK60_VARIANT,
        "C2 Stage103+network momentum 60d/252corr monthly",
        "network_momentum_overlay",
        "momentum",
        60,
        3,
        20,
        "过去252日正相关网络加权的60日领先品种动量，月频再平衡，强者多、弱者空，各3个品种。",
    ),
)


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


def _safe_metric(value: Any, default: float = 0.0) -> float:
    return s405._safe_metric(value, default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s405._md_table(frame, max_rows)


def _candidate(spec: s405.VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.role,
        eligible_for_promotion=spec.variant != BASELINE_VARIANT,
        note=spec.note,
    )


def _network_score_table(returns: pd.DataFrame, signal_lookback: int) -> pd.DataFrame:
    one_plus = 1.0 + returns.fillna(0.0)
    leader_momentum = one_plus.rolling(signal_lookback, min_periods=signal_lookback).apply(np.prod, raw=True).shift(1) - 1.0
    scores = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    columns = list(returns.columns)
    for idx in range(CORR_LOOKBACK, len(returns)):
        date = returns.index[idx]
        corr = returns.iloc[idx - CORR_LOOKBACK : idx].corr().reindex(index=columns, columns=columns)
        mom = leader_momentum.iloc[idx].reindex(columns)
        for product in columns:
            weights = corr[product].drop(labels=[product], errors="ignore").clip(lower=0.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            if weights.sum() <= 1e-12:
                continue
            aligned_mom = mom.reindex(weights.index).replace([np.inf, -np.inf], np.nan)
            valid = aligned_mom.notna()
            if not bool(valid.any()):
                continue
            valid_weights = weights.loc[valid]
            if valid_weights.sum() <= 1e-12:
                continue
            scores.loc[date, product] = float((aligned_mom.loc[valid] * valid_weights).sum() / valid_weights.sum())
    return scores


def _build_rank_tables(price_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = (
        price_frame.pivot_table(index="date", columns="product_vt_symbol", values="product_return", aggfunc="last")
        .sort_index()
        .fillna(0.0)
    )
    result = {
        BASELINE_VARIANT: pd.DataFrame(),
        STAGE103_VARIANT: pd.DataFrame(),
        NETWORK20_VARIANT: _network_score_table(returns, 20),
        NETWORK60_VARIANT: _network_score_table(returns, 60),
    }
    feature_parts = []
    for variant, table in result.items():
        if table.empty:
            continue
        long = table.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="network_score")
        long["variant"] = variant
        feature_parts.append(long)
    if feature_parts:
        pd.concat(feature_parts, ignore_index=True).to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    return result


def _patch_variant_globals() -> None:
    s405.VARIANTS = VARIANTS
    s419.VARIANTS = VARIANTS


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(TARGET_DD_PCT, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "Net20", "Net60"]
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
    for variant, frame in pw.groupby("candidate_variant"):
        axes[1, 1].plot(frame["window_days"], frame["return_win_rate"], marker="o", label=variant)
    axes[1, 1].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Rolling return win rate vs Stage103")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].legend(fontsize=7)
    fig.suptitle("Stage121 network momentum overlay", fontsize=14)
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
        "# Stage121 Stage103 Network Momentum Overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：文献驱动固定结构；不改 Stage079/Stage103/C3 规则，不增加账户资金，不扫品种、阈值或坏窗口。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage103+20日network momentum；C2=Stage103+60日network momentum。",
        "- 候选假设：商品趋势有跨品种 lead-lag / spillover，相关网络中的领先品种动量可能比单品种动量更早反映趋势扩散或衰竭。",
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
        _md_table(
            score[
                [
                    "variant",
                    "horizon_days",
                    "experience_score",
                    "improved_metric_count",
                    "target_hit_count",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
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
                    "target_pass_3m6m_vs_stage079",
                    "metric_incremental_pass_stage103",
                    "execution_relative_pass",
                    "research_promotion_pass",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                    "fresh_start_failed_windows",
                    "broker10_relative_worse_than_stage103_windows",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "not_worse_than_stage079_stress", "not_worse_than_stage103_stress"]]),
        "",
        "## 任意启动相对Stage103",
        "",
        _md_table(pairwise),
        "",
        "## 顶部贡献日剔除",
        "",
        _md_table(topday),
        "",
        "## 冷启动窗口",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "overlay_slippage",
                    "overlay_turnover",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## Stage104坏窗口贡献",
        "",
        _md_table(bad_windows),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段不使用坏窗口日期、品种黑名单或结果后阈值补丁。",
        "- 252日相关网络、20/60日动量、top/bottom各3、周频/月频均为预声明粗结构。",
        "- 若候选只在全周期好看但冷启动、成本或相对Stage103鲁棒性失败，则不晋级。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _patch_variant_globals()
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full_frame)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    rank_tables = _build_rank_tables(price_frame)
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    xsmom_by_window: dict[str, pd.DataFrame] = {}
    overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    overlay_full_by_variant: dict[str, pd.DataFrame] = {}
    candidates: list[Any] = []
    full_daily_parts: list[pd.DataFrame] = []

    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
        xsmom_by_window[window_name] = xsmom
        for spec in VARIANTS:
            if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                overlay = s405._empty_overlay(window_name, spec.variant)
            else:
                overlay = s405._simulate_overlay(spec, window_name, frame, margin_frame, xsmom, price_frame, rank_tables[spec.variant])
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
    overlay_all = pd.concat([frame for frame in overlay_by_window_variant.values() if not frame.empty], ignore_index=True)
    summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s402.s087._score_horizons(horizon)
    margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
    fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
    cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
    bad_windows = s405._bad_window_contribution({spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS})
    gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
    pairwise = s419._rolling_pairwise(full_daily)
    topday = s419._top_edge_day_ablation(full_daily)

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    best = gate.iloc[0] if not gate.empty else None
    decision_code = "execution_relative_candidate" if len(execution_ready) else ("research_candidate_only" if len(research_ready) else "no_new_promotion")
    decision = {
        "stage": "Stage121",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best["variant"]) if best is not None else "",
        "chart": str(CHART_PATH),
        "judgement": "network momentum若不能同时通过Stage079硬闸门、3/6个月体验和相对Stage103鲁棒性，则只保留为研究经验。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, score, pairwise)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
