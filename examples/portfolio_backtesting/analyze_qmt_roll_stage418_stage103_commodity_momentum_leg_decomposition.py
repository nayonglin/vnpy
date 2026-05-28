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
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402


MODEL_TAG = "stage418_stage103_commodity_momentum_leg_decomposition_v1"
OUTPUT_PREFIX = "qmt_roll_stage418_stage103_commodity_momentum_leg_decomposition"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL

MOM60_BOTH_VARIANT = "stage103_plus_mom60_weekly_both_guard"
MOM60_LONG_VARIANT = "stage103_plus_mom60_weekly_long_only_guard"
MOM60_SHORT_VARIANT = "stage103_plus_mom60_weekly_short_only_guard"
MOM120_BOTH_VARIANT = "stage103_plus_mom120_monthly_both_guard"
MOM120_LONG_VARIANT = "stage103_plus_mom120_monthly_long_only_guard"
MOM120_SHORT_VARIANT = "stage103_plus_mom120_monthly_short_only_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
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
        MOM60_BOTH_VARIANT,
        "C1 mom60 weekly both",
        "positive_control",
        "momentum_both",
        60,
        3,
        5,
        "Stage106同形状正向对照：近60日横截面动量，周频再平衡，买强卖弱各3个品种。",
    ),
    s405.VariantSpec(
        MOM60_LONG_VARIANT,
        "C2 mom60 weekly long only",
        "momentum_leg_decomposition",
        "momentum_long_only",
        60,
        3,
        5,
        "近60日横截面动量只保留强者多头腿，周频再平衡。",
    ),
    s405.VariantSpec(
        MOM60_SHORT_VARIANT,
        "C3 mom60 weekly short only",
        "momentum_leg_decomposition",
        "momentum_short_only",
        60,
        3,
        5,
        "近60日横截面动量只保留弱者空头腿，周频再平衡。",
    ),
    s405.VariantSpec(
        MOM120_BOTH_VARIANT,
        "C4 mom120 monthly both",
        "positive_control",
        "momentum_both",
        120,
        3,
        20,
        "Stage106同形状正向对照：近120日横截面动量，月频再平衡，买强卖弱各3个品种。",
    ),
    s405.VariantSpec(
        MOM120_LONG_VARIANT,
        "C5 mom120 monthly long only",
        "momentum_leg_decomposition",
        "momentum_long_only",
        120,
        3,
        20,
        "近120日横截面动量只保留强者多头腿，月频再平衡。",
    ),
    s405.VariantSpec(
        MOM120_SHORT_VARIANT,
        "C6 mom120 monthly short only",
        "momentum_leg_decomposition",
        "momentum_short_only",
        120,
        3,
        20,
        "近120日横截面动量只保留弱者空头腿，月频再平衡。",
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


def _select_products(rank_row: pd.Series, price_by_product: dict[str, Any], spec: s405.VariantSpec) -> dict[str, int]:
    if spec.direction == "none":
        return {}
    available: dict[str, float] = {}
    for product, value in rank_row.dropna().items():
        price_row = price_by_product.get(str(product))
        if price_row is None:
            continue
        if s402._safe_float(getattr(price_row, "margin_per_contract", 0.0)) <= 0.0:
            continue
        if s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) <= 0.0:
            continue
        available[str(product)] = float(value)
    if len(available) < spec.top_n * 2:
        return {}

    ordered = sorted(available.items(), key=lambda item: item[1])
    losers = [product for product, _value in ordered[: spec.top_n]]
    winners = [product for product, _value in ordered[-spec.top_n :]]
    if spec.direction in {"momentum", "momentum_both"}:
        return {**{product: -1 for product in losers}, **{product: 1 for product in winners}}
    if spec.direction == "momentum_long_only":
        return {product: 1 for product in winners}
    if spec.direction == "momentum_short_only":
        return {product: -1 for product in losers}
    raise ValueError(f"unsupported direction: {spec.direction}")


def _calendarize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values("date").drop_duplicates("date", keep="last")
    calendar = pd.DataFrame({"date": pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")})
    merged = calendar.merge(daily, on="date", how="left")
    merged["equity"] = pd.to_numeric(merged["equity"], errors="coerce").ffill()
    for col in ["trade_count", "combo_slippage"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    return merged.dropna(subset=["equity"])


def _drawdown(nav: np.ndarray) -> np.ndarray:
    return nav / np.maximum.accumulate(nav) - 1.0


def _ulcer(nav: np.ndarray) -> float:
    dd = np.minimum(_drawdown(nav) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _rolling_pairwise(full_daily: pd.DataFrame) -> pd.DataFrame:
    windows = (90, 180, 252, 504)
    candidate_variants = [
        MOM60_BOTH_VARIANT,
        MOM60_LONG_VARIANT,
        MOM60_SHORT_VARIANT,
        MOM120_BOTH_VARIANT,
        MOM120_LONG_VARIANT,
        MOM120_SHORT_VARIANT,
    ]
    comparators = [BASELINE_VARIANT, STAGE103_VARIANT]
    by_variant = {
        variant: _calendarize_daily(frame[frame["window_name"].eq("start_2020")])
        for variant, frame in full_daily.groupby("variant")
    }
    rows: list[dict[str, Any]] = []
    for candidate_variant in candidate_variants:
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        for comparator_variant in comparators:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            common = candidate[["equity"]].rename(columns={"equity": "candidate_equity"}).join(
                comparator[["equity"]].rename(columns={"equity": "comparator_equity"}),
                how="inner",
            )
            for window_days in windows:
                return_deltas: list[float] = []
                maxdd_not_worse: list[int] = []
                ulcer_not_worse: list[int] = []
                for start_date in common.index:
                    end_date = start_date + pd.Timedelta(days=window_days)
                    if end_date > common.index.max():
                        continue
                    sub = common.loc[start_date:end_date]
                    if len(sub) < 2:
                        continue
                    c_nav = sub["candidate_equity"].to_numpy(dtype=float) / float(sub["candidate_equity"].iloc[0])
                    b_nav = sub["comparator_equity"].to_numpy(dtype=float) / float(sub["comparator_equity"].iloc[0])
                    c_ret = (float(c_nav[-1]) - 1.0) * 100.0
                    b_ret = (float(b_nav[-1]) - 1.0) * 100.0
                    c_dd = float(_drawdown(c_nav).min() * 100.0)
                    b_dd = float(_drawdown(b_nav).min() * 100.0)
                    c_ulcer = _ulcer(c_nav)
                    b_ulcer = _ulcer(b_nav)
                    return_deltas.append(c_ret - b_ret)
                    maxdd_not_worse.append(int(c_dd >= b_dd - 1e-12))
                    ulcer_not_worse.append(int(c_ulcer <= b_ulcer + 1e-12))
                deltas = np.asarray(return_deltas, dtype=float)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "window_days": window_days,
                        "count": int(len(deltas)),
                        "return_win_rate": float(np.mean(deltas >= -1e-12)) if len(deltas) else np.nan,
                        "return_delta_median_pp": float(np.median(deltas)) if len(deltas) else np.nan,
                        "return_delta_p05_pp": float(np.percentile(deltas, 5)) if len(deltas) else np.nan,
                        "maxdd_not_worse_rate": float(np.mean(maxdd_not_worse)) if maxdd_not_worse else np.nan,
                        "ulcer_not_worse_rate": float(np.mean(ulcer_not_worse)) if ulcer_not_worse else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def _top_edge_day_ablation(full_daily: pd.DataFrame) -> pd.DataFrame:
    candidate_variants = [
        MOM60_BOTH_VARIANT,
        MOM60_LONG_VARIANT,
        MOM60_SHORT_VARIANT,
        MOM120_BOTH_VARIANT,
        MOM120_LONG_VARIANT,
        MOM120_SHORT_VARIANT,
    ]
    comparators = [BASELINE_VARIANT, STAGE103_VARIANT]
    remove_counts = (0, 1, 3, 5, 10, 20)
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    by_variant = {variant: _calendarize_daily(frame) for variant, frame in full.groupby("variant")}
    rows: list[dict[str, Any]] = []
    for candidate_variant in candidate_variants:
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        c_pnl = candidate["equity"].diff().fillna(candidate["equity"].iloc[0] - ACCOUNT_CAPITAL)
        for comparator_variant in comparators:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            b_pnl = comparator["equity"].diff().fillna(comparator["equity"].iloc[0] - ACCOUNT_CAPITAL)
            edge = (c_pnl - b_pnl).sort_values(ascending=False)
            b_nav = comparator["equity"].to_numpy(dtype=float) / ACCOUNT_CAPITAL
            b_return = (float(b_nav[-1]) - 1.0) * 100.0
            b_maxdd = float(_drawdown(b_nav).min() * 100.0)
            b_ulcer = _ulcer(b_nav)
            for n in remove_counts:
                adjusted_pnl = c_pnl.copy()
                if n > 0:
                    adjusted_pnl.loc[edge.head(n).index] -= edge.head(n)
                adjusted_equity = ACCOUNT_CAPITAL + adjusted_pnl.cumsum()
                nav = adjusted_equity.to_numpy(dtype=float) / ACCOUNT_CAPITAL
                adjusted_return = (float(nav[-1]) - 1.0) * 100.0
                adjusted_maxdd = float(_drawdown(nav).min() * 100.0)
                adjusted_ulcer = _ulcer(nav)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "removed_top_positive_edge_days": n,
                        "removed_edge_pnl": float(edge.head(n).sum()) if n > 0 else 0.0,
                        "candidate_adjusted_total_return_pct": adjusted_return,
                        "candidate_adjusted_max_dd_pct": adjusted_maxdd,
                        "candidate_adjusted_ulcer_pct": adjusted_ulcer,
                        "comparator_total_return_pct": b_return,
                        "comparator_max_dd_pct": b_maxdd,
                        "comparator_ulcer_pct": b_ulcer,
                        "adjusted_return_delta_pp": adjusted_return - b_return,
                        "adjusted_maxdd_delta_pp": adjusted_maxdd - b_maxdd,
                        "adjusted_ulcer_delta_pp": adjusted_ulcer - b_ulcer,
                    }
                )
    return pd.DataFrame(rows)


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame, cost: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "60Both", "60Long", "60Short", "120Both", "120Long", "120Short"]
    full = full_daily[full_daily["window_name"].eq("start_2020")]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=0.9)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.8)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=5)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=5)

    x = np.arange(len(variants))
    s90 = score[score["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    s180 = score[score["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - 0.18, s90["experience_score"].to_numpy(dtype=float), 0.36, label="90d score")
    axes[0, 1].bar(x + 0.18, s180["experience_score"].to_numpy(dtype=float), 0.36, label="180d score")
    axes[0, 1].axhline(110.0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 1].set_title("Short holding scores")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    pw = pairwise[
        pairwise["comparator_variant"].eq(STAGE103_VARIANT) & pairwise["window_days"].isin([90, 180, 252, 504])
    ]
    for variant, frame in pw.groupby("candidate_variant"):
        axes[1, 1].plot(frame["window_days"], frame["return_win_rate"], marker="o", label=variant)
    axes[1, 1].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Return win rate vs Stage103")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].legend(fontsize=5)
    fig.suptitle("Stage118 commodity momentum leg decomposition", fontsize=14)
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
        "# Stage118 Stage103商品动量多空腿拆解审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定结构拆解；不改 Stage079、Stage103、C3 规则，不增加账户资金，不扫动量窗口/top_n/再平衡频率。",
        "- A/B/C：A=Stage079；C0=Stage103；C1/C4=Stage106商品动量双腿对照；C2/C5=只保留强者多头腿；C3/C6=只保留弱者空头腿。",
        "- 外部判断：商品期货横截面动量有文献支持，但长短腿可能不对称；因此本阶段只做腿部结构审计，不能用结果继续救小参数。",
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
        "## 任意启动收益/风险相对胜率",
        "",
        _md_table(pairwise),
        "",
        "## 顶部相对贡献日剔除",
        "",
        _md_table(topday),
        "",
        "## Stage104底部5%坏窗口贡献",
        "",
        _md_table(bad_windows),
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
            max_rows=160,
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
        "## 反过拟合说明",
        "",
        "- 本阶段没有根据坏窗口添加过滤条件，没有调窗口、top_n、再平衡频率、资金小数或品种名单。",
        "- 若多头腿或空头腿不能同时通过冷启动、成本压力和相对 Stage103 稳健性，则商品动量腿部拆解子路线停止；只保留为 paper 经验。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s405.VARIANTS
    old_select_products = s405._select_products
    s405.VARIANTS = VARIANTS
    s405._select_products = _select_products
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full_frame)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        ranks = s405._build_rank_tables(price_frame, {spec.lookback_days for spec in VARIANTS if spec.lookback_days > 0})
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
                        spec, window_name, frame, margin_frame, xsmom, price_frame, ranks[spec.lookback_days]
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
            candidates.append(s405._candidate(spec, equity))

        full_daily = pd.concat(full_daily_parts, ignore_index=True)
        overlay_all = pd.concat([frame for frame in overlay_by_window_variant.values() if not frame.empty], ignore_index=True)
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame(
            [s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)]
        )
        score = s402.s087._score_horizons(horizon)
        margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
        fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
        bad_windows = s405._bad_window_contribution(
            {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
        )
        gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
        pairwise = _rolling_pairwise(full_daily)
        topday = _top_edge_day_ablation(full_daily)
    finally:
        s405.VARIANTS = old_variants
        s405._select_products = old_select_products

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    pairwise_vs_stage103 = pairwise[pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    weak_pairwise = pairwise_vs_stage103[
        (pairwise_vs_stage103["window_days"].isin([90, 180, 252, 504]))
        & (pairwise_vs_stage103["return_win_rate"].fillna(0.0) < 0.5)
    ]
    topday_vs_stage103 = topday[topday["comparator_variant"].eq(STAGE103_VARIANT)]
    fragile_after_one_day = topday_vs_stage103[
        (topday_vs_stage103["removed_top_positive_edge_days"].eq(1))
        & (topday_vs_stage103["adjusted_return_delta_pp"] < 0.0)
    ]
    best_gate = gate.iloc[0] if not gate.empty else None
    decision_code = (
        "execution_relative_candidate"
        if len(execution_ready) and weak_pairwise.empty and fragile_after_one_day.empty
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion")
    )
    if len(execution_ready) and (not weak_pairwise.empty or not fragile_after_one_day.empty):
        decision_code = "fixed_path_pass_but_robustness_gap_do_not_promote"
    decision = {
        "stage": "Stage118",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "judgement": "商品动量腿部拆解若无法通过相对Stage103任意启动收益胜率与顶部贡献日剔除，则不晋级，只保留paper经验。",
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
    _plot(full_daily, score, pairwise, cost)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
