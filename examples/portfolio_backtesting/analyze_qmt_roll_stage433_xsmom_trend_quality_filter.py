from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402


MODEL_TAG = "stage433_xsmom_trend_quality_filter_v1"
OUTPUT_PREFIX = "qmt_roll_stage433_xsmom_trend_quality_filter"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s403.BASELINE_VARIANT
STAGE103_VARIANT = s403.GUARD_VARIANT
BROKER10_MULTIPLIER = s403.BROKER10_MULTIPLIER
TARGET_DD_PCT = s403.TARGET_DD_PCT

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SATELLITE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_panel_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


VARIANTS: tuple[s403.AuditVariant, ...] = (
    s403.AuditVariant(BASELINE_VARIANT, "A Stage079基准", "baseline", "50万C3下单+11.5万现金。"),
    s403.AuditVariant(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "broker10_guard",
        "当前主执行相对候选，固定xsmom整篮子和10%保证金闸门。",
    ),
    s403.AuditVariant(
        "xsmom_fip63_positive_broker10_guard",
        "C1 xsmom 63日方向一致性>50%",
        "fip63_positive",
        "只执行上一日以前63日内同方向日数占比>=50%的xsmom信号，仍沿用Stage103保证金闸门。",
    ),
    s403.AuditVariant(
        "xsmom_fip63_tophalf_broker10_guard",
        "C2 xsmom 63日方向一致性Top半数",
        "fip63_tophalf",
        "每天只执行xsmom信号中方向一致性最高的半数，动态排序不设小数收益阈值，仍沿用Stage103保证金闸门。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s403._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s403._md_table(frame, max_rows=max_rows)


def _candidate(spec: s403.AuditVariant, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=s402.ACCOUNT_CAPITAL,
        candidate_class="xsmom_trend_quality_filter" if spec.variant != BASELINE_VARIANT else "baseline",
        eligible_for_promotion=True,
        note=spec.note,
    )


def _build_quality_panel(price_frame: pd.DataFrame) -> pd.DataFrame:
    panel = (
        price_frame[["date", "product_vt_symbol", "product_return"]]
        .dropna(subset=["date", "product_vt_symbol"])
        .drop_duplicates(["date", "product_vt_symbol"], keep="last")
        .sort_values(["product_vt_symbol", "date"])
        .copy()
    )
    panel["product_return"] = pd.to_numeric(panel["product_return"], errors="coerce").fillna(0.0)
    pieces: list[pd.DataFrame] = []
    for product, group in panel.groupby("product_vt_symbol", sort=False):
        g = group.copy()
        ret = g["product_return"].astype(float)
        g["fip63_long"] = (ret > 0.0).rolling(63, min_periods=63).mean().shift(1)
        g["fip63_short"] = (ret < 0.0).rolling(63, min_periods=63).mean().shift(1)
        g["absret63_sum"] = ret.abs().rolling(63, min_periods=63).sum().shift(1)
        g["absret63_max"] = ret.abs().rolling(63, min_periods=63).max().shift(1)
        g["jump_share63"] = np.where(g["absret63_sum"] > 0.0, g["absret63_max"] / g["absret63_sum"], np.nan)
        g["product_vt_symbol"] = product
        pieces.append(g)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def _quality_lookup(quality_panel: pd.DataFrame) -> dict[tuple[pd.Timestamp, str], tuple[float, float, float]]:
    lookup: dict[tuple[pd.Timestamp, str], tuple[float, float, float]] = {}
    for row in quality_panel.itertuples(index=False):
        lookup[(pd.Timestamp(row.date).normalize(), str(row.product_vt_symbol))] = (
            float(row.fip63_long) if pd.notna(row.fip63_long) else float("nan"),
            float(row.fip63_short) if pd.notna(row.fip63_short) else float("nan"),
            float(row.jump_share63) if pd.notna(row.jump_share63) else float("nan"),
        )
    return lookup


def _filter_desired_by_quality(
    date: pd.Timestamp,
    desired: list[tuple[str, str, int, float]],
    mode: str,
    quality: dict[tuple[pd.Timestamp, str], tuple[float, float, float]],
) -> tuple[list[tuple[str, str, int, float]], float]:
    if mode == "broker10_guard":
        return desired, float("nan")
    scored: list[tuple[float, tuple[str, str, int, float]]] = []
    for item in desired:
        _contract, product, direction, _margin = item
        long_score, short_score, _jump_share = quality.get((date, product), (float("nan"), float("nan"), float("nan")))
        score = long_score if direction > 0 else short_score
        if math.isnan(score):
            continue
        scored.append((score, item))
    if not scored:
        return [], float("nan")
    if mode == "fip63_positive":
        selected = [item for score, item in scored if score >= 0.50]
        avg_score = float(np.mean([score for score, _item in scored])) if scored else float("nan")
        return selected, avg_score
    if mode == "fip63_tophalf":
        keep = int(math.ceil(len(scored) / 2.0))
        ranked = sorted(scored, key=lambda pair: (pair[0], -pair[1][3]), reverse=True)
        selected_scored = ranked[:keep]
        return [item for _score, item in selected_scored], float(np.mean([score for score, _item in selected_scored]))
    return desired, float("nan")


def _simulate_quality_satellite(
    spec: s403.AuditVariant,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
    quality: dict[tuple[pd.Timestamp, str], tuple[float, float, float]],
) -> pd.DataFrame:
    if spec.mode == "broker10_guard":
        return s403._simulate_guarded_round_half(window_name, window_frame, margin_frame, price_frame, signals, scale_by_date)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return s403._empty_satellite(window_name)

    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
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
    prev_equity = s402.ACCOUNT_CAPITAL

    for signal_row in window_signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        scale = float(scale_by_date.get(date, 0.0))
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        desired_raw = s402._desired_contracts(signal_row, price_by_product)
        desired, avg_fip63 = _filter_desired_by_quality(date, desired_raw, spec.mode, quality)
        targets, required_min1_margin = s402._target_lots("round_half", scale, desired)

        proposed_margin = 0.0
        for contract in targets:
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                proposed_margin += s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        c3_margin = float(c3_margin_by_date.get(date, 0.0))
        margin_gate_skipped = int(bool(targets) and (c3_margin + proposed_margin) * BROKER10_MULTIPLIER > prev_equity)
        if margin_gate_skipped:
            targets = {}
            proposed_margin = 0.0

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

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
                slippage_cost += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        sat_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "satellite_daily_pnl": sat_daily_pnl,
                "satellite_slippage_cost": slippage_cost,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "held_contract_count": len(targets),
                "desired_signal_count": len(desired_raw),
                "quality_selected_signal_count": len(desired),
                "required_min1_margin": required_min1_margin,
                "stage101_scale": scale,
                "avg_selected_fip63": avg_fip63,
                "margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + sat_daily_pnl

    return pd.DataFrame(rows)


def _returns_by_variant(full_daily: pd.DataFrame) -> pd.DataFrame:
    curves = full_daily.pivot_table(index="date", columns="variant", values="equity", aggfunc="last").sort_index()
    calendar = pd.date_range(curves.index.min(), curves.index.max(), freq="D")
    curves = curves.reindex(calendar).ffill().dropna(how="all")
    return curves.pct_change().fillna(0.0)


def _metrics_from_returns(returns: np.ndarray) -> dict[str, float]:
    equity = s402.ACCOUNT_CAPITAL * np.cumprod(1.0 + returns)
    nav = equity / s402.ACCOUNT_CAPITAL
    peak = np.maximum.accumulate(nav)
    dd = nav / peak - 1.0
    std = np.std(returns, ddof=1)
    sharpe = float(np.mean(returns) / std * math.sqrt(365.0)) if std > 0 else 0.0
    return {
        "total_return_pct": float((nav[-1] - 1.0) * 100.0),
        "max_dd_pct": float(dd.min() * 100.0),
        "sharpe": sharpe,
        "ulcer_pct": float(np.sqrt(np.mean(np.square(np.minimum(dd * 100.0, 0.0))))),
    }


def _top_edge_day_ablation(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidate_variants = [
        "xsmom_fip63_positive_broker10_guard",
        "xsmom_fip63_tophalf_broker10_guard",
    ]
    comparators = [BASELINE_VARIANT, STAGE103_VARIANT]
    for variant in candidate_variants:
        if variant not in returns.columns:
            continue
        for comparator in comparators:
            if comparator not in returns.columns:
                continue
            edge = returns[variant] - returns[comparator]
            positive_edge = edge[edge > 0].sort_values(ascending=False)
            comp_metrics = _metrics_from_returns(returns[comparator].to_numpy(dtype=float))
            for top_n in [0, 1, 3, 5, 10, 20]:
                adjusted = returns[variant].copy()
                removed_edge_return_sum_pp = 0.0
                if top_n > 0:
                    remove_dates = positive_edge.head(top_n).index
                    removed_edge_return_sum_pp = float(positive_edge.head(top_n).sum() * 100.0)
                    adjusted.loc[remove_dates] = returns.loc[remove_dates, comparator]
                metrics = _metrics_from_returns(adjusted.to_numpy(dtype=float))
                rows.append(
                    {
                        "variant": variant,
                        "comparator_variant": comparator,
                        "removed_top_positive_edge_days": top_n,
                        "removed_edge_return_sum_pp": removed_edge_return_sum_pp,
                        "candidate_adjusted_total_return_pct": metrics["total_return_pct"],
                        "candidate_adjusted_max_dd_pct": metrics["max_dd_pct"],
                        "candidate_adjusted_sharpe": metrics["sharpe"],
                        "candidate_adjusted_ulcer_pct": metrics["ulcer_pct"],
                        "comparator_total_return_pct": comp_metrics["total_return_pct"],
                        "comparator_max_dd_pct": comp_metrics["max_dd_pct"],
                        "comparator_sharpe": comp_metrics["sharpe"],
                        "comparator_ulcer_pct": comp_metrics["ulcer_pct"],
                        "adjusted_return_delta_pp": metrics["total_return_pct"] - comp_metrics["total_return_pct"],
                        "adjusted_maxdd_delta_pp": metrics["max_dd_pct"] - comp_metrics["max_dd_pct"],
                        "adjusted_ulcer_delta_pp": metrics["ulcer_pct"] - comp_metrics["ulcer_pct"],
                    }
                )
    return pd.DataFrame(rows)


def _plot(summary: pd.DataFrame, score: pd.DataFrame, margin_audit: pd.DataFrame, topday: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage433] skip chart: {exc}", flush=True)
        return

    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "FIP>=50", "FIP top half"]
    summary_i = summary.set_index("variant").reindex(variants)
    score_i = score.drop_duplicates("variant").set_index("variant").reindex(variants)
    broker10 = (
        margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)]
        .groupby("variant")
        .agg(max_margin_to_equity_pct=("max_margin_to_equity_pct", "max"), reject_days=("reject_days_over_100pct", "sum"))
        .reindex(variants)
    )
    top1 = (
        topday[
            topday["comparator_variant"].eq(STAGE103_VARIANT)
            & topday["removed_top_positive_edge_days"].eq(1)
        ]
        .set_index("variant")
        .reindex(variants)
    )

    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    x = np.arange(len(variants))
    colors = ["#666666", "#2f6f9f", "#1b9e77", "#d95f02"]
    axes[0, 0].bar(x, summary_i["total_return_pct"].to_numpy(dtype=float), color=colors)
    axes[0, 0].axhline(float(summary_i.loc[BASELINE_VARIANT, "total_return_pct"]), color="#aa0000", linestyle="--", linewidth=1.0)
    axes[0, 0].set_title("Total return")
    axes[0, 0].set_ylabel("%")

    axes[0, 1].bar(x, summary_i["max_dd_pct"].to_numpy(dtype=float), color=colors)
    axes[0, 1].axhline(-30.0, color="#aa0000", linestyle="--", linewidth=1.0)
    axes[0, 1].set_title("Max drawdown")
    axes[0, 1].set_ylabel("%")

    width = 0.35
    axes[1, 0].bar(x - width / 2, score_i["score_90d"].to_numpy(dtype=float), width, label="90d", color="#8da0cb")
    axes[1, 0].bar(x + width / 2, score_i["score_180d"].to_numpy(dtype=float), width, label="180d", color="#66c2a5")
    axes[1, 0].axhline(110.0, color="#aa0000", linestyle="--", linewidth=1.0)
    axes[1, 0].set_title("Short holding score")
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].bar(x - width / 2, broker10["max_margin_to_equity_pct"].to_numpy(dtype=float), width, label="max margin/equity", color="#a6d854")
    axes[1, 1].bar(x + width / 2, top1["adjusted_return_delta_pp"].fillna(0.0).to_numpy(dtype=float), width, label="top1 ablated edge vs Stage103", color="#fc8d62")
    axes[1, 1].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[1, 1].axhline(0.0, color="#aa0000", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Margin and top-day edge")
    axes[1, 1].legend(fontsize=8)

    for ax in axes.flat:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    fig.suptitle("Stage133 xsmom trend-quality filter audit", fontsize=14)
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
    gate: pd.DataFrame,
    topday: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    broker10 = margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)]
    lines = [
        "# Stage133 xsmom趋势质量过滤审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定结构只读审计；不改Stage079/C3，不扫小数阈值。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=63日方向一致性>=50%；C2=每日方向一致性Top半数。",
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
        "## 体验评分与晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass",
                    "target_pass_3m6m",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_metric_checks",
                    "broker10_reject_windows",
                    "broker10_relative_worse_windows",
                ]
            ]
        ),
        "",
        "## 1.10x 保证金审计",
        "",
        _md_table(
            broker10[
                [
                    "window_name",
                    "variant",
                    "max_margin_to_equity_pct",
                    "reject_days_over_100pct",
                    "required_extra_cash_for_no_reject",
                    "first_reject_date",
                ]
            ],
            max_rows=80,
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
        "## 顶部相对贡献日剔除",
        "",
        _md_table(
            topday[
                [
                    "variant",
                    "comparator_variant",
                    "removed_top_positive_edge_days",
                    "candidate_adjusted_total_return_pct",
                    "adjusted_return_delta_pp",
                    "adjusted_maxdd_delta_pp",
                    "adjusted_ulcer_delta_pp",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 多起点摘要",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "satellite_turnover",
                    "margin_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 63日来自 Stage101/Stage103 已冻结的xsmom承载窗口，不是本阶段重新扫描。",
        "- `>=50%` 是方向一致性的自然中位边界；`Top半数` 是动态横截面排序，不设置收益拟合阈值。",
        "- 若趋势质量过滤没有改善短持有体验或损害长期收益，不继续调 `55%/60%`、`20/126日` 或Top比例。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s403.VARIANTS
    s403.VARIANTS = VARIANTS
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()
        quality_panel = _build_quality_panel(price_frame)
        quality = _quality_lookup(quality_panel)

        satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        satellite_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            for spec in VARIANTS:
                if spec.variant == BASELINE_VARIANT:
                    sat = s403._empty_satellite(window_name)
                else:
                    sat = _simulate_quality_satellite(
                        spec, window_name, frame, margin_frame, price_frame, signals, scale_by_date, quality
                    )
                satellite_by_window_variant[(window_name, spec.variant)] = sat
                daily = s402._combine_daily(frame, sat, spec.variant, 1.0)
                daily["window_name"] = window_name
                daily_by_window_variant[(window_name, spec.variant)] = daily
                if window_name == "start_2020":
                    satellite_full_by_variant[spec.variant] = sat

        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            daily = daily_by_window_variant[("start_2020", spec.variant)]
            daily_parts.append(daily)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            candidates.append(_candidate(spec, equity))

        daily_all = pd.concat(daily_parts, ignore_index=True)
        satellite_all = pd.concat(
            [
                frame.assign(variant=variant)
                for (_window_name, variant), frame in satellite_by_window_variant.items()
                if variant != BASELINE_VARIANT and not frame.empty
            ],
            ignore_index=True,
        )
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
        score = s402.s087._score_horizons(horizon)
        margin_audit = s403._margin_audit(combo, margin, satellite_by_window_variant, daily_by_window_variant)
        fresh = s403._fresh_start(combo, margin, satellite_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s403._cost_stress(full_frame, satellite_full_by_variant)
        gate = s403._gate(summary, horizon, score, cost, fresh, margin_audit)
        returns = _returns_by_variant(daily_all)
        topday = _top_edge_day_ablation(returns)
    finally:
        s403.VARIANTS = old_variants

    quality_candidates = gate[gate["variant"].isin([VARIANTS[2].variant, VARIANTS[3].variant])].copy()
    research_ready = quality_candidates[quality_candidates["research_promotion_pass"].eq(1)]
    execution_ready = quality_candidates[quality_candidates["execution_relative_pass"].eq(1)]
    abs_ready = quality_candidates[quality_candidates["deployment_absolute_margin_pass"].eq(1)]
    best = quality_candidates.iloc[0] if not quality_candidates.empty else None
    decision_key = "trend_quality_candidate_found" if len(execution_ready) else "no_trend_quality_promotion"
    decision = {
        "stage": "Stage133",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_key,
        "research_ready_variants": research_ready["variant"].tolist(),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "absolute_margin_ready_variants": abs_ready["variant"].tolist(),
        "best_quality_variant_by_gate_order": str(best["variant"]) if best is not None else "",
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "judgement": "趋势质量过滤若不能在不损害Stage079硬约束的前提下改善短持有体验，则停止该方向，不继续调方向一致性阈值或窗口。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_all.to_csv(SATELLITE_PATH, index=False, encoding="utf-8-sig")
    quality_panel.to_csv(QUALITY_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    _plot(summary, score, margin_audit, topday)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, gate, topday, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
