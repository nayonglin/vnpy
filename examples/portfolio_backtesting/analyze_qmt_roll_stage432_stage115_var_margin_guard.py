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
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage415_stage103_cffex_index_true_overlay as s415  # noqa: E402
import analyze_qmt_roll_stage431_stage115_margin_light_index_overlay as s431  # noqa: E402


MODEL_TAG = "stage432_stage115_var_margin_guard_v1"
OUTPUT_PREFIX = "qmt_roll_stage432_stage115_var_margin_guard"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
BROKER10_MULTIPLIER = s405.BROKER10_MULTIPLIER

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
RESERVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_base_loss_reserve_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


VARIANTS: tuple[s405.VariantSpec, ...] = (
    s405.VariantSpec(
        BASELINE_VARIANT,
        "A Stage079基准",
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
        "stage103_plus_cffex_index_best1_tsmom60_guard",
        "C1 Stage115股指60日最强动量1手",
        "stage115_reference",
        "index_tsmom_best1",
        60,
        1,
        0,
        "Stage115原始固定形状，作为参照。",
    ),
    s405.VariantSpec(
        "stage103_plus_cffex_index_best1_tsmom60_var99_guard",
        "C2 Stage115 + 99%单日亏损准备金闸门",
        "var_margin_guard_scout",
        "index_tsmom_best1_var99",
        60,
        1,
        0,
        "仍取四个股指60日TSMOM最强一手，但开仓前要求10%保证金压力+上一日已知Stage103滚动252日99%单日亏损准备金不超过账户权益。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s431._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s431._md_table(frame, max_rows=max_rows)


def _select_index_rows(spec: s405.VariantSpec, rows: list[Any]) -> list[Any]:
    active = [row for row in rows if int(np.sign(float(getattr(row, "position", 0.0)))) != 0]
    if not active:
        return []
    if spec.direction in {"index_tsmom_best1", "index_tsmom_best1_var99"}:
        return [max(active, key=lambda row: abs(float(getattr(row, "momentum", 0.0))))]
    return []


def _build_base_loss_reserve(full_frame: pd.DataFrame, xsmom_full: pd.DataFrame) -> tuple[dict[pd.Timestamp, float], pd.DataFrame]:
    base = full_frame[["date", "c3_net_pnl"]].copy()
    xsmom = xsmom_full[["date", "satellite_daily_pnl"]].copy() if not xsmom_full.empty else pd.DataFrame()
    merged = base.merge(xsmom, on="date", how="left")
    merged["satellite_daily_pnl"] = pd.to_numeric(merged.get("satellite_daily_pnl", 0.0), errors="coerce").fillna(0.0)
    merged["base_daily_pnl"] = merged["c3_net_pnl"].astype(float) + merged["satellite_daily_pnl"].astype(float)
    merged["prior_loss"] = (-merged["base_daily_pnl"]).clip(lower=0.0).shift(1)
    merged["loss_reserve_var99_252d"] = (
        merged["prior_loss"].rolling(252, min_periods=1).quantile(0.99).fillna(0.0).astype(float)
    )
    reserve_by_date = {
        pd.Timestamp(row.date).normalize(): float(row.loss_reserve_var99_252d)
        for row in merged.itertuples(index=False)
    }
    return reserve_by_date, merged


def _simulate_index_overlay(
    spec: s405.VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    index_panel: pd.DataFrame,
    reserve_by_date: dict[pd.Timestamp, float],
) -> pd.DataFrame:
    if spec.direction not in {"index_tsmom_best1", "index_tsmom_best1_var99"}:
        return s405._empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    index = index_panel[
        index_panel["horizon_days"].eq(spec.lookback_days) & index_panel["date"].between(start, end)
    ].copy()
    if index.empty:
        return s405._empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = xsmom_sat.set_index("date") if not xsmom_sat.empty else pd.DataFrame()
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()

    by_date: dict[pd.Timestamp, list[Any]] = {}
    for row in index.itertuples(index=False):
        by_date.setdefault(pd.Timestamp(row.date).normalize(), []).append(row)

    prev_positions: dict[str, int] = {}
    prev_contract_specs: dict[str, tuple[str, float]] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL

    for date in window_frame["date"].sort_values():
        date = pd.Timestamp(date).normalize()
        targets: dict[str, int] = {}
        contract_specs: dict[str, tuple[str, float]] = {}
        proposed_margin = 0.0
        pnl = 0.0
        selected_rows = _select_index_rows(spec, list(by_date.get(date, [])))
        desired_count = len(selected_rows)

        for index_row in selected_rows:
            lots = int(np.sign(float(getattr(index_row, "position", 0.0))))
            if lots == 0:
                continue
            contract = str(getattr(index_row, "main_contract_vt", ""))
            if not contract:
                continue
            margin_per_contract = float(getattr(index_row, "margin_per_contract", 0.0))
            if margin_per_contract <= 0.0:
                continue
            targets[contract] = lots
            contract_specs[contract] = (
                str(getattr(index_row, "product", "")),
                float(getattr(index_row, "tick_value", 0.0)),
            )
            proposed_margin += margin_per_contract
            close = float(getattr(index_row, "close", 0.0))
            product_return = float(getattr(index_row, "product_return", 0.0))
            if product_return <= -0.999999 or close <= 0.0:
                continue
            prev_close = close / (1.0 + product_return) if abs(product_return) > 1e-12 else close
            pnl += lots * prev_close * product_return * float(getattr(index_row, "contract_multiplier", 0.0))

        reserve = float(reserve_by_date.get(date, 0.0)) if spec.direction == "index_tsmom_best1_var99" else 0.0
        required_margin = (
            float(c3_margin.get(date, 0.0)) + float(xsmom_margin.get(date, 0.0)) + proposed_margin
        ) * BROKER10_MULTIPLIER + reserve
        margin_gate_skipped = int(bool(targets) and required_margin > prev_equity)
        if margin_gate_skipped:
            targets = {}
            contract_specs = {}
            proposed_margin = 0.0
            pnl = 0.0

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            _product, tick_value = contract_specs.get(contract, prev_contract_specs.get(contract, ("", 0.0)))
            slippage_cost += delta * tick_value

        overlay_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": spec.variant,
                "overlay_daily_pnl": overlay_daily_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": proposed_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len(targets),
                "overlay_desired_product_count": desired_count,
                "overlay_rebalance": 1,
                "overlay_margin_gate_skipped": margin_gate_skipped,
                "overlay_var99_reserve": reserve,
                "overlay_var99_required_margin": required_margin,
            }
        )
        prev_positions = targets
        prev_contract_specs = contract_specs
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _returns_by_variant(full_daily: pd.DataFrame) -> pd.DataFrame:
    return s431._returns_by_variant(full_daily)


def _top_edge_day_ablation(returns: pd.DataFrame) -> pd.DataFrame:
    old_variants = s431.VARIANTS
    s431.VARIANTS = VARIANTS
    try:
        return s431._top_edge_day_ablation(returns)
    finally:
        s431.VARIANTS = old_variants


def _plot(summary: pd.DataFrame, score: pd.DataFrame, margin_audit: pd.DataFrame, topday: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage432] skip chart: {exc}", flush=True)
        return

    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "Best1", "Var99"]
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
    colors = ["#666666", "#2f6f9f", "#d95f02", "#1b9e77"]

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
    axes[1, 1].set_title("Margin and top-day fragility")
    axes[1, 1].legend(fontsize=8)

    for ax in axes.flat:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    fig.suptitle("Stage132 Stage115 var-margin guard audit", fontsize=14)
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
    reserve: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    broker10 = margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)]
    reserve_stats = pd.DataFrame(
        [
            {
                "reserve_p50": float(reserve["loss_reserve_var99_252d"].median()),
                "reserve_p90": float(reserve["loss_reserve_var99_252d"].quantile(0.90)),
                "reserve_p99": float(reserve["loss_reserve_var99_252d"].quantile(0.99)),
                "reserve_max": float(reserve["loss_reserve_var99_252d"].max()),
            }
        ]
    )
    lines = [
        "# Stage132 Stage115 VAR保证金闸门审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定结构只读审计；不改 Stage079/Stage103，不扫窗口、不扫阈值、不扫保证金小数。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage115最强动量1手；C2=同一Stage115信号+上一日已知Stage103滚动252日99%单日亏损准备金闸门。",
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
                    "metric_hard_pass_stage079",
                    "target_pass_3m6m_vs_stage079",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_stage079_metric_checks",
                    "broker10_reject_windows",
                    "broker10_relative_worse_than_stage103_windows",
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
        "## 准备金尺度",
        "",
        _md_table(reserve_stats),
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
                    "overlay_turnover",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段固定为一个风险预算原则：上一日已知的Stage103滚动252日99%单日亏损准备金。没有扫描分位数、窗口、单指数、股指动量窗口或保证金倍数。",
        "- 若该原则仍不能同时解决绝对保证金和贡献日集中问题，则 Stage115 股指TSMOM救援路线应正式封止，避免围绕高分样本继续救小参数。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s405.VARIANTS
    old_s431_variants = s431.VARIANTS
    s405.VARIANTS = VARIANTS
    s431.VARIANTS = VARIANTS
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full_frame)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()
        index_panel = s415._build_index_panel()

        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []
        reserve_by_date: dict[pd.Timestamp, float] = {}
        reserve_frame = pd.DataFrame()

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            if window_name == "start_2020":
                reserve_by_date, reserve_frame = _build_base_loss_reserve(frame, xsmom)

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            xsmom = xsmom_by_window[window_name]
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = s405._empty_overlay(window_name, spec.variant)
                else:
                    overlay = _simulate_index_overlay(spec, window_name, frame, margin_frame, xsmom, index_panel, reserve_by_date)
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
        returns = _returns_by_variant(full_daily)
        topday = _top_edge_day_ablation(returns)
    finally:
        s405.VARIANTS = old_variants
        s431.VARIANTS = old_s431_variants

    candidate_gate = gate[~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])].copy()
    research_ready = candidate_gate[candidate_gate["research_promotion_pass"].eq(1)]
    execution_ready = candidate_gate[candidate_gate["execution_relative_pass"].eq(1)]
    abs_ready = candidate_gate[candidate_gate["deployment_absolute_margin_pass"].eq(1)]
    var_ready = [
        variant
        for variant in abs_ready["variant"].tolist()
        if variant == "stage103_plus_cffex_index_best1_tsmom60_var99_guard"
    ]
    top1_var = topday[
        topday["variant"].eq("stage103_plus_cffex_index_best1_tsmom60_var99_guard")
        & topday["comparator_variant"].eq(STAGE103_VARIANT)
        & topday["removed_top_positive_edge_days"].eq(1)
    ]
    top1_edge_after = float(top1_var["adjusted_return_delta_pp"].iloc[0]) if not top1_var.empty else np.nan
    decision_key = "var99_candidate_promoted" if var_ready and top1_edge_after >= 0.0 else "no_var99_promotion"
    decision = {
        "stage": "Stage132",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_key,
        "research_ready_variants": research_ready["variant"].tolist(),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "absolute_margin_ready_variants": abs_ready["variant"].tolist(),
        "var99_ready_variants": var_ready,
        "var99_top1_ablation_edge_after_pp_vs_stage103": top1_edge_after,
        "reserve_rule": "previous-day rolling 252 trading day 99% one-day Stage103 base loss reserve",
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "judgement": "只有在绝对保证金过线且剔除最大1个相对贡献日后仍不弱于Stage103时，才允许Stage115 VAR闸门版本晋级。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    reserve_frame.to_csv(RESERVE_PATH, index=False, encoding="utf-8-sig")
    _plot(summary, score, margin_audit, topday)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, gate, topday, reserve_frame, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
