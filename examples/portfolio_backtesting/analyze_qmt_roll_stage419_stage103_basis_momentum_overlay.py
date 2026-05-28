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
import analyze_qmt_roll_stage368_curve_slope_dynamics_feasibility as s368  # noqa: E402
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage418_stage103_commodity_momentum_leg_decomposition as s418  # noqa: E402


MODEL_TAG = "stage419_stage103_basis_momentum_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage419_stage103_basis_momentum_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
PRICE_MOM_LOOKBACK = 60

BM105_VARIANT = "stage103_plus_basis_mom105_monthly_guard"
BM252_VARIANT = "stage103_plus_basis_mom252_monthly_guard"
BM105_MOM60_VARIANT = "stage103_plus_basis_mom105_price_mom60_blend_guard"
BM252_MOM60_VARIANT = "stage103_plus_basis_mom252_price_mom60_blend_guard"

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_basis_features_{MODEL_TAG}.csv"
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
        BM105_VARIANT,
        "C1 basis momentum 105d monthly",
        "basis_momentum_overlay",
        "basis_momentum",
        105,
        3,
        20,
        "近5个月期限结构斜率变化动量，月频再平衡，强者多、弱者空，各3个品种。",
    ),
    s405.VariantSpec(
        BM252_VARIANT,
        "C2 basis momentum 252d monthly",
        "basis_momentum_overlay",
        "basis_momentum",
        252,
        3,
        20,
        "近12个月期限结构斜率变化动量，月频再平衡，强者多、弱者空，各3个品种。",
    ),
    s405.VariantSpec(
        BM105_MOM60_VARIANT,
        "C3 basis105 + price momentum60 rank blend",
        "basis_price_momentum_overlay",
        "basis_price_blend",
        105,
        3,
        20,
        "近5个月basis-momentum与60日价格动量的等权横截面rank blend，月频再平衡。",
    ),
    s405.VariantSpec(
        BM252_MOM60_VARIANT,
        "C4 basis252 + price momentum60 rank blend",
        "basis_price_momentum_overlay",
        "basis_price_blend",
        252,
        3,
        20,
        "近12个月basis-momentum与60日价格动量的等权横截面rank blend，月频再平衡。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s418._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s418._md_table(frame, max_rows)


def _candidate_variants() -> list[str]:
    return [spec.variant for spec in VARIANTS if spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT}]


def _load_basis_features() -> pd.DataFrame:
    if s368.CURVE_FEATURE_PATH.exists():
        features = pd.read_csv(s368.CURVE_FEATURE_PATH, encoding="utf-8-sig")
    else:
        products = s368._read_products()
        contract_rows = s368._load_contract_curve_rows(products)
        features = s368._select_daily_curves(contract_rows)
    if features.empty:
        return features
    features["date"] = pd.to_datetime(features["date"], errors="coerce").dt.normalize()
    features["curve_slope"] = pd.to_numeric(features["curve_slope"], errors="coerce")
    features = features.dropna(subset=["date", "product_vt_symbol", "curve_slope"]).copy()
    features = features.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    return features


def _build_rank_tables(features: pd.DataFrame, price_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if features.empty:
        return {spec.variant: pd.DataFrame() for spec in VARIANTS}
    slope = features.pivot_table(index="date", columns="product_vt_symbol", values="curve_slope", aggfunc="last")
    slope = slope.sort_index()
    basis_tables: dict[int, pd.DataFrame] = {}
    for lookback in sorted({spec.lookback_days for spec in VARIANTS if spec.lookback_days > 0}):
        basis_tables[lookback] = -(slope - slope.shift(lookback)).shift(1)

    price_mom = s405._build_rank_tables(price_frame, {PRICE_MOM_LOOKBACK})[PRICE_MOM_LOOKBACK]
    rank_tables: dict[str, pd.DataFrame] = {}
    for spec in VARIANTS:
        if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
            rank_tables[spec.variant] = pd.DataFrame()
            continue
        basis_score = basis_tables[spec.lookback_days]
        if spec.direction == "basis_momentum":
            rank_tables[spec.variant] = basis_score
            continue
        basis_rank = basis_score.rank(axis=1, pct=True)
        price_rank = price_mom.reindex(index=basis_rank.index, columns=basis_rank.columns).rank(axis=1, pct=True)
        rank_tables[spec.variant] = basis_rank + price_rank
    return rank_tables


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
    shorts = [product for product, _value in ordered[: spec.top_n]]
    longs = [product for product, _value in ordered[-spec.top_n :]]
    return {**{product: -1 for product in shorts}, **{product: 1 for product in longs}}


def _rolling_pairwise(full_daily: pd.DataFrame) -> pd.DataFrame:
    windows = (90, 180, 252, 504)
    by_variant = {
        variant: s418._calendarize_daily(frame[frame["window_name"].eq("start_2020")])
        for variant, frame in full_daily.groupby("variant")
    }
    rows: list[dict[str, Any]] = []
    for candidate_variant in _candidate_variants():
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        for comparator_variant in [BASELINE_VARIANT, STAGE103_VARIANT]:
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
                    c_dd = float(s418._drawdown(c_nav).min() * 100.0)
                    b_dd = float(s418._drawdown(b_nav).min() * 100.0)
                    c_ulcer = s418._ulcer(c_nav)
                    b_ulcer = s418._ulcer(b_nav)
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
    remove_counts = (0, 1, 3, 5, 10, 20)
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    by_variant = {variant: s418._calendarize_daily(frame) for variant, frame in full.groupby("variant")}
    rows: list[dict[str, Any]] = []
    for candidate_variant in _candidate_variants():
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        c_pnl = candidate["equity"].diff().fillna(candidate["equity"].iloc[0] - ACCOUNT_CAPITAL)
        for comparator_variant in [BASELINE_VARIANT, STAGE103_VARIANT]:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            b_pnl = comparator["equity"].diff().fillna(comparator["equity"].iloc[0] - ACCOUNT_CAPITAL)
            edge = (c_pnl - b_pnl).sort_values(ascending=False)
            b_nav = comparator["equity"].to_numpy(dtype=float) / ACCOUNT_CAPITAL
            b_return = (float(b_nav[-1]) - 1.0) * 100.0
            b_maxdd = float(s418._drawdown(b_nav).min() * 100.0)
            b_ulcer = s418._ulcer(b_nav)
            for n in remove_counts:
                adjusted_pnl = c_pnl.copy()
                if n > 0:
                    adjusted_pnl.loc[edge.head(n).index] -= edge.head(n)
                adjusted_equity = ACCOUNT_CAPITAL + adjusted_pnl.cumsum()
                nav = adjusted_equity.to_numpy(dtype=float) / ACCOUNT_CAPITAL
                adjusted_return = (float(nav[-1]) - 1.0) * 100.0
                adjusted_maxdd = float(s418._drawdown(nav).min() * 100.0)
                adjusted_ulcer = s418._ulcer(nav)
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


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "BM105", "BM252", "BM105+Mom", "BM252+Mom"]
    full = full_daily[full_daily["window_name"].eq("start_2020")]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=0.95)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.85)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=6)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=6)

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
    axes[1, 1].legend(fontsize=6)
    fig.suptitle("Stage119 basis momentum overlay", fontsize=14)
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
        "# Stage119 Stage103 Basis-Momentum期限结构Overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：文献驱动固定结构；不改 Stage079/Stage103/C3 规则，不增加账户资金，不扫品种、阈值或坏窗口。",
        "- A/B/C：A=Stage079；C0=Stage103；C1/C2=basis-momentum；C3/C4=basis-momentum与60日价格动量等权rank blend。",
        "- 外部判断：basis-momentum 与 momentum+term-structure 双信号都有文献支持；本阶段只验证固定 5个月/12个月期限结构变化，不做结果导向微调。",
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
            max_rows=140,
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
        "- 本阶段使用外部文献给出的 5个月/12个月 basis-momentum 结构和固定 60日价格动量辅助，不因历史坏窗口调阈值。",
        "- 若失败，不继续扫 basis lookback、rank blend 权重、top_n、日期、品种或保证金小数。",
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
        features = _load_basis_features()
        rank_tables = _build_rank_tables(features, price_frame)
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

    if not features.empty:
        features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")

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
        "stage": "Stage119",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "judgement": "basis-momentum若不能通过冷启动、成本压力和相对Stage103任意启动胜率，则不晋级，不继续救参数。",
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
